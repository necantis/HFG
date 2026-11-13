"""
GPU Runtime, Dual-Coder Server Management, Benchmarking, and Atomic Question Checkpointing for HFG.

Owned by: Agent 07 — GPU Runtime (`src/runtime/`)
Architecture Version: v1.1.0
Active Run ID: run_20261111_002

Implements:
- Physical accelerator and VRAM detection at runtime (no assumed hardware).
- Configurable runtime parameters (`gpu_runtime_config.json`, `gpu_runtime_config_v1`) with
  explicit VRAM headroom and empirically derived memory budgets.
- Model-family diversity enforcement:
  * Coder A: DeepSeek reasoning-oriented 32B quantized model (`deepseek` family).
  * Coder B: Independent multilingual model family (`mistral` family preferred: Mistral Small 3.1 24B INT4;
    `gemma` family alternative: Gemma 3 27B quantized).
  * Strictly blocks substituting a Qwen-derived model for Coder B when Coder A is Qwen/DeepSeek-R1-Distill-Qwen.
- Separate localhost server endpoints (`localhost:8001` for Coder A, `localhost:8002` for Coder B).
- Bounded context, bounded generation length, and bounded concurrency via asyncio/threading semaphores.
- Health polling, structured-output client with schema validation, model-specific failure isolation,
  graceful shutdown, and automatic sequential fallback without invalidating completed question checkpoints.
- Atomic question-level checkpoints recording: run_id, question_id, coder_id, prompt_hash, source_hash,
  model_repo, model_revision, quantization, generation_config, raw_response, parsed_response,
  schema_status, runtime_sec, and peak_vram_mb.
- 5-stage runtime benchmark suite:
  1. Coder A alone
  2. Coder B alone
  3. Both servers resident
  4. One simultaneous structured request to each
  5. Bounded concurrent requests
"""

from __future__ import annotations

import asyncio
import hashlib
import http.server
import importlib.util
import json
import os
import platform
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Optional, Sequence, Tuple

from pydantic import BaseModel, Field, ValidationError

from src.contracts import SCHEMA_VERSION, ProvenanceMeta


# ---------------------------------------------------------------------------
# Constants & Model Family Diversity Rules
# ---------------------------------------------------------------------------

DEFAULT_RUN_ID = "run_20261111_002"

FORBIDDEN_CODER_B_FAMILIES = {"qwen", "qwen2", "qwen2.5", "deepseek", "deepseek_qwen"}
ALLOWED_CODER_B_FAMILIES = {"mistral", "gemma", "gemma3"}


class ExecutionMode(str, Enum):
    """Runtime execution mode for dual coders."""

    CONCURRENT_DUAL_SERVER = "CONCURRENT_DUAL_SERVER"
    SEQUENTIAL_FALLBACK = "SEQUENTIAL_FALLBACK"
    CPU_FALLBACK = "CPU_FALLBACK"


class SchemaStatus(str, Enum):
    """Schema validation status of a coder response."""

    VALID = "VALID"
    INVALID_JSON = "INVALID_JSON"
    INVALID_SCHEMA = "INVALID_SCHEMA"
    REQUEST_FAILED = "REQUEST_FAILED"


# ---------------------------------------------------------------------------
# Data Models & Configurable Runtime Contracts
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CoderModelSpec:
    """Specification for an individual LLM coder server."""

    coder_id: Literal["coder_a", "coder_b"]
    model_family: str
    model_repo: str
    model_revision: str
    quantization: str
    port: int
    base_model: str = ""
    serving_engine: str = "vllm_openai_server"
    remote_repo_validated: bool = False
    host: str = "127.0.0.1"
    gpu_memory_fraction: float = 0.42
    estimated_weights_vram_mb: float = 19500.0
    kv_cache_vram_mb: float = 8192.0
    max_model_len: int = 8192
    max_output_tokens: int = 2048
    temperature: float = 0.0
    seed: int = 42
    tensor_parallel_size: int = 1
    dtype: str = "auto"
    enforce_eager: bool = False
    extra_engine_args: Dict[str, Any] = field(default_factory=dict)

    @property
    def endpoint_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


DEFAULT_CODER_A_SPEC = CoderModelSpec(
    coder_id="coder_a",
    model_family="deepseek",
    base_model="deepseek-ai/DeepSeek-R1-Distill-Qwen-32B",
    model_repo="Valdemardi/DeepSeek-R1-Distill-Qwen-32B-AWQ",
    model_revision="main",
    quantization="AWQ-INT4",
    serving_engine="vllm_openai_server",
    remote_repo_validated=False,
    port=8001,
    gpu_memory_fraction=0.42,
    estimated_weights_vram_mb=18500.0,
    kv_cache_vram_mb=8192.0,
    max_model_len=8192,
    max_output_tokens=2048,
    temperature=0.0,
    seed=42,
)

DEFAULT_CODER_B_MISTRAL_SPEC = CoderModelSpec(
    coder_id="coder_b",
    model_family="mistral",
    base_model="mistralai/Mistral-Small-3.1-24B-Instruct-2503",
    model_repo="RedHatAI/Mistral-Small-3.1-24B-Instruct-2503-quantized.w4a16",
    model_revision="main",
    quantization="W4A16-INT4",
    serving_engine="vllm_openai_server",
    remote_repo_validated=False,
    port=8002,
    gpu_memory_fraction=0.38,
    estimated_weights_vram_mb=14500.0,
    kv_cache_vram_mb=8192.0,
    max_model_len=8192,
    max_output_tokens=2048,
    temperature=0.0,
    seed=42,
)

ALTERNATIVE_CODER_B_GEMMA_SPEC = CoderModelSpec(
    coder_id="coder_b",
    model_family="gemma",
    base_model="google/gemma-3-27b-it",
    model_repo="pytorch/gemma-3-27b-it-AWQ-INT4",
    model_revision="main",
    quantization="AWQ-INT4",
    serving_engine="vllm_openai_server",
    remote_repo_validated=False,
    port=8002,
    gpu_memory_fraction=0.40,
    estimated_weights_vram_mb=16200.0,
    kv_cache_vram_mb=8192.0,
    max_model_len=8192,
    max_output_tokens=2048,
    temperature=0.0,
    seed=42,
)

DEFAULT_CODER_A_CANDIDATES: Tuple[CoderModelSpec, ...] = (
    DEFAULT_CODER_A_SPEC,
    CoderModelSpec(
        coder_id="coder_a",
        model_family="deepseek",
        base_model="deepseek-ai/DeepSeek-R1-Distill-Qwen-32B",
        model_repo="dwetzel/DeepSeek-R1-Distill-Qwen-32B-GPTQ-INT4",
        model_revision="main",
        quantization="GPTQ-INT4",
        serving_engine="vllm_openai_server",
        remote_repo_validated=False,
        port=8001,
        gpu_memory_fraction=0.42,
        estimated_weights_vram_mb=19200.0,
        kv_cache_vram_mb=8192.0,
        max_model_len=8192,
        max_output_tokens=2048,
        temperature=0.0,
        seed=42,
    ),
    CoderModelSpec(
        coder_id="coder_a",
        model_family="deepseek",
        base_model="deepseek-ai/DeepSeek-R1-Distill-Qwen-32B",
        model_repo="deepseek-ai/DeepSeek-R1-Distill-Qwen-32B",
        model_revision="main",
        quantization="FP8-DYNAMIC",
        serving_engine="vllm_openai_server",
        remote_repo_validated=False,
        port=8001,
        gpu_memory_fraction=0.45,
        estimated_weights_vram_mb=33000.0,
        kv_cache_vram_mb=8192.0,
        max_model_len=8192,
        max_output_tokens=2048,
        temperature=0.0,
        seed=42,
        extra_engine_args={"quantization": "fp8"},
    ),
    CoderModelSpec(
        coder_id="coder_a",
        model_family="deepseek",
        base_model="deepseek-ai/DeepSeek-R1-Distill-Qwen-32B",
        model_repo="deepseek-ai/DeepSeek-R1-Distill-Qwen-32B",
        model_revision="main",
        quantization="BNB-4BIT",
        serving_engine="vllm_openai_server",
        remote_repo_validated=False,
        port=8001,
        gpu_memory_fraction=0.42,
        estimated_weights_vram_mb=19500.0,
        kv_cache_vram_mb=8192.0,
        max_model_len=8192,
        max_output_tokens=2048,
        temperature=0.0,
        seed=42,
        extra_engine_args={"quantization": "bitsandbytes", "load_format": "bitsandbytes"},
    ),
)

DEFAULT_CODER_B_MISTRAL_CANDIDATES: Tuple[CoderModelSpec, ...] = (
    DEFAULT_CODER_B_MISTRAL_SPEC,
    CoderModelSpec(
        coder_id="coder_b",
        model_family="mistral",
        base_model="mistralai/Mistral-Small-3.1-24B-Instruct-2503",
        model_repo="OPEA/Mistral-Small-3.1-24B-Instruct-2503-int4-AutoRound-awq-sym",
        model_revision="main",
        quantization="AWQ-INT4",
        serving_engine="vllm_openai_server",
        remote_repo_validated=False,
        port=8002,
        gpu_memory_fraction=0.38,
        estimated_weights_vram_mb=14500.0,
        kv_cache_vram_mb=8192.0,
        max_model_len=8192,
        max_output_tokens=2048,
        temperature=0.0,
        seed=42,
    ),
    CoderModelSpec(
        coder_id="coder_b",
        model_family="mistral",
        base_model="mistralai/Mistral-Small-3.1-24B-Instruct-2503",
        model_repo="RedHatAI/Mistral-Small-3.1-24B-Instruct-2503-FP8-dynamic",
        model_revision="main",
        quantization="FP8-DYNAMIC",
        serving_engine="vllm_openai_server",
        remote_repo_validated=False,
        port=8002,
        gpu_memory_fraction=0.40,
        estimated_weights_vram_mb=25000.0,
        kv_cache_vram_mb=8192.0,
        max_model_len=8192,
        max_output_tokens=2048,
        temperature=0.0,
        seed=42,
    ),
    CoderModelSpec(
        coder_id="coder_b",
        model_family="mistral",
        base_model="mistralai/Mistral-Small-3.1-24B-Instruct-2503",
        model_repo="unsloth/Mistral-Small-3.1-24B-Instruct-2503-bnb-4bit",
        model_revision="main",
        quantization="BNB-4BIT",
        serving_engine="vllm_openai_server",
        remote_repo_validated=False,
        port=8002,
        gpu_memory_fraction=0.38,
        estimated_weights_vram_mb=15000.0,
        kv_cache_vram_mb=8192.0,
        max_model_len=8192,
        max_output_tokens=2048,
        temperature=0.0,
        seed=42,
        extra_engine_args={"quantization": "bitsandbytes", "load_format": "bitsandbytes"},
    ),
    CoderModelSpec(
        coder_id="coder_b",
        model_family="mistral",
        base_model="mistralai/Mistral-Small-3.1-24B-Instruct-2503",
        model_repo="mistralai/Mistral-Small-3.1-24B-Instruct-2503",
        model_revision="main",
        quantization="FP8-DYNAMIC",
        serving_engine="vllm_openai_server",
        remote_repo_validated=False,
        port=8002,
        gpu_memory_fraction=0.40,
        estimated_weights_vram_mb=25000.0,
        kv_cache_vram_mb=8192.0,
        max_model_len=8192,
        max_output_tokens=2048,
        temperature=0.0,
        seed=42,
        extra_engine_args={"quantization": "fp8"},
    ),
)

ALTERNATIVE_CODER_B_GEMMA_CANDIDATES: Tuple[CoderModelSpec, ...] = (
    ALTERNATIVE_CODER_B_GEMMA_SPEC,
    CoderModelSpec(
        coder_id="coder_b",
        model_family="gemma",
        base_model="google/gemma-3-27b-it",
        model_repo="abhishekchohan/gemma-3-27b-it-quantized-W4A16",
        model_revision="main",
        quantization="W4A16-INT4",
        serving_engine="vllm_openai_server",
        remote_repo_validated=False,
        port=8002,
        gpu_memory_fraction=0.40,
        estimated_weights_vram_mb=16200.0,
        kv_cache_vram_mb=8192.0,
        max_model_len=8192,
        max_output_tokens=2048,
        temperature=0.0,
        seed=42,
    ),
    CoderModelSpec(
        coder_id="coder_b",
        model_family="gemma",
        base_model="google/gemma-3-27b-it",
        model_repo="pytorch/gemma-3-27b-it-FP8",
        model_revision="main",
        quantization="FP8",
        serving_engine="vllm_openai_server",
        remote_repo_validated=False,
        port=8002,
        gpu_memory_fraction=0.40,
        estimated_weights_vram_mb=28000.0,
        kv_cache_vram_mb=8192.0,
        max_model_len=8192,
        max_output_tokens=2048,
        temperature=0.0,
        seed=42,
    ),
    CoderModelSpec(
        coder_id="coder_b",
        model_family="gemma",
        base_model="google/gemma-3-27b-it",
        model_repo="gaunernst/gemma-3-27b-it-qat-compressed-tensors",
        model_revision="main",
        quantization="QAT-INT4",
        serving_engine="vllm_openai_server",
        remote_repo_validated=False,
        port=8002,
        gpu_memory_fraction=0.40,
        estimated_weights_vram_mb=16500.0,
        kv_cache_vram_mb=8192.0,
        max_model_len=8192,
        max_output_tokens=2048,
        temperature=0.0,
        seed=42,
    ),
    CoderModelSpec(
        coder_id="coder_b",
        model_family="gemma",
        base_model="google/gemma-3-27b-it",
        model_repo="google/gemma-3-27b-it",
        model_revision="main",
        quantization="FP8-DYNAMIC",
        serving_engine="vllm_openai_server",
        remote_repo_validated=False,
        port=8002,
        gpu_memory_fraction=0.40,
        estimated_weights_vram_mb=28000.0,
        kv_cache_vram_mb=8192.0,
        max_model_len=8192,
        max_output_tokens=2048,
        temperature=0.0,
        seed=42,
        extra_engine_args={"quantization": "fp8"},
    ),
)


@dataclass(frozen=True)
class HardwareProfile:
    """Measured physical hardware environment at runtime (never assumed from docs)."""

    measured_at_utc: str
    hostname: str
    os_platform: str
    cpu_model: str
    cpu_logical_cores: int
    system_ram_total_mb: float
    system_ram_available_mb: float
    gpu_available: bool
    gpu_count: int
    gpu_device_name: str
    gpu_total_vram_mb: float
    gpu_free_vram_mb: float
    gpu_used_vram_mb: float
    cuda_version: Optional[str] = None
    driver_version: Optional[str] = None
    compute_capability: Optional[str] = None
    detection_method: str = "runtime_probe"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GPURuntimeConfig:
    """Configurable GPU Runtime & Dual-LLM Server Allocation Configuration (`gpu_runtime_config_v1`)."""

    run_id: str
    config_version: str = "v1.1.0"
    schema_version: str = SCHEMA_VERSION
    execution_mode: ExecutionMode = ExecutionMode.CONCURRENT_DUAL_SERVER
    runtime_implementation_status: str = "VALID"
    live_gpu_benchmark_status: str = "NOT_EXECUTED_NO_GPU"
    production_dual_model_validation: bool = False
    gpu_memory_fraction: float = 0.80
    coder_a_memory_fraction: float = 0.42
    coder_b_memory_fraction: float = 0.38
    reserved_vram_headroom_mb: float = 6144.0
    reserved_vram_headroom_fraction: float = 0.12
    min_concurrent_vram_mb: float = 48000.0
    min_single_gpu_vram_mb: float = 22000.0
    allow_growth: bool = True
    device_ids: List[int] = field(default_factory=lambda: [0])
    coder_a_port: int = 8001
    coder_b_port: int = 8002
    max_context_length: int = 8192
    max_generation_length: int = 2048
    max_concurrent_requests_per_coder: int = 4
    max_total_concurrent_requests: int = 8
    request_timeout_sec: float = 60.0
    health_poll_interval_sec: float = 0.5
    health_Check_timeout_sec: float = 30.0
    startup_timeout_sec: float = 900.0
    max_retries_per_request: int = 2
    auto_sequential_fallback: bool = True
    coder_a_spec: CoderModelSpec = field(default_factory=lambda: DEFAULT_CODER_A_SPEC)
    coder_b_spec: CoderModelSpec = field(default_factory=lambda: DEFAULT_CODER_B_MISTRAL_SPEC)
    coder_b_alternative_spec: CoderModelSpec = field(default_factory=lambda: ALTERNATIVE_CODER_B_GEMMA_SPEC)
    measured_hardware: Optional[Dict[str, Any]] = None
    derived_from_benchmark: bool = False
    gate_1_ingestion_passed: bool = False
    gate_2_coding_schemas_validated: bool = False
    full_survey_coding_authorized: bool = False
    checkpoint_dir: str = ".checkpoints/gpu_coder_wal"
    updated_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def validate_config(self) -> None:
        """Enforce model diversity, bounded parameters, and VRAM headroom invariants."""
        validate_model_family_diversity(self.coder_a_spec, self.coder_b_spec)

        if self.coder_a_spec.port == self.coder_b_spec.port:
            raise ValueError(
                f"Coder A and Coder B must use separate localhost ports; both configured to {self.coder_a_spec.port}"
            )

        if not (0.05 <= self.coder_a_memory_fraction <= 0.95):
            raise ValueError(f"Invalid coder_a_memory_fraction: {self.coder_a_memory_fraction}")
        if not (0.05 <= self.coder_b_memory_fraction <= 0.95):
            raise ValueError(f"Invalid coder_b_memory_fraction: {self.coder_b_memory_fraction}")

        if self.execution_mode == ExecutionMode.CONCURRENT_DUAL_SERVER:
            combined = self.coder_a_memory_fraction + self.coder_b_memory_fraction
            if combined + self.reserved_vram_headroom_fraction > 1.0 + 1e-6:
                raise ValueError(
                    f"Concurrent memory fractions ({self.coder_a_memory_fraction:.3f} + "
                    f"{self.coder_b_memory_fraction:.3f} = {combined:.3f}) exceed available budget "
                    f"after reserving headroom fraction {self.reserved_vram_headroom_fraction:.3f}."
                )

        if self.max_context_length <= 0 or self.max_context_length > 131072:
            raise ValueError(f"max_context_length must be bounded in (0, 131072], got {self.max_context_length}")
        if self.max_generation_length <= 0 or self.max_generation_length > self.max_context_length:
            raise ValueError(
                f"max_generation_length ({self.max_generation_length}) must be positive and <= max_context_length ({self.max_context_length})"
            )
        if self.max_concurrent_requests_per_coder < 1 or self.max_total_concurrent_requests < 1:
            raise ValueError("Concurrency limits must be >= 1.")
        if self.coder_a_spec.temperature != 0.0 or self.coder_b_spec.temperature != 0.0:
            raise ValueError("Zero-temperature analytical invariant violated: coder temperatures must be 0.0.")

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["execution_mode"] = self.execution_mode.value
        return data

    def save(self, path: Path | str) -> Path:
        self.validate_config()
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = target.with_suffix(".json.tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, target)
        return target

    @classmethod
    def load(cls, path: Path | str) -> "GPURuntimeConfig":
        target = Path(path)
        with open(target, "r", encoding="utf-8") as f:
            raw = json.load(f)

        coder_a = CoderModelSpec(**raw.pop("coder_a_spec"))
        coder_b = CoderModelSpec(**raw.pop("coder_b_spec"))
        coder_b_alt_raw = raw.pop("coder_b_alternative_spec", None)
        coder_b_alt = (
            CoderModelSpec(**coder_b_alt_raw)
            if coder_b_alt_raw
            else ALTERNATIVE_CODER_B_GEMMA_SPEC
        )
        mode_str = raw.pop("execution_mode", ExecutionMode.CONCURRENT_DUAL_SERVER.value)
        known_fields = set(cls.__dataclass_fields__.keys())
        filtered_raw = {k: v for k, v in raw.items() if k in known_fields}
        cfg = cls(
            coder_a_spec=coder_a,
            coder_b_spec=coder_b,
            coder_b_alternative_spec=coder_b_alt,
            execution_mode=ExecutionMode(mode_str),
            **filtered_raw,
        )
        cfg.validate_config()
        return cfg


def validate_model_family_diversity(coder_a: CoderModelSpec, coder_b: CoderModelSpec) -> None:
    """
    Enforce analytical invariant:
    - Coder A must be the DeepSeek reasoning-oriented 32B quantized model.
    - Coder B must be an independent multilingual model family (Mistral Small 3.1 24B INT4 preferred,
      Gemma 3 27B quantized alternative).
    - Substituting another Qwen-derived model for Coder B is strictly forbidden.
    """
    family_a = coder_a.model_family.strip().lower()
    family_b = coder_b.model_family.strip().lower()
    repo_a = coder_a.model_repo.strip().lower()
    repo_b = coder_b.model_repo.strip().lower()

    if family_a == family_b:
        raise ValueError(
            f"Model-family diversity violation: Coder A and Coder B share family '{family_a}'."
        )

    if family_b in FORBIDDEN_CODER_B_FAMILIES or "qwen" in repo_b or "deepseek" in repo_b:
        raise ValueError(
            f"Model-family diversity violation: Coder B ('{coder_b.model_repo}', family='{coder_b.model_family}') "
            "cannot be a Qwen-derived or DeepSeek-derived model. Independent multilingual family "
            "(Mistral Small 3.1 24B INT4 or Gemma 3 27B quantized) is required."
        )

    if family_b not in ALLOWED_CODER_B_FAMILIES:
        raise ValueError(
            f"Unsupported Coder B model family '{coder_b.model_family}'. "
            f"Must be one of {sorted(ALLOWED_CODER_B_FAMILIES)}."
        )

    if "deepseek" not in family_a and "deepseek" not in repo_a:
        raise ValueError(
            f"Coder A ('{coder_a.model_repo}') must be a DeepSeek reasoning-oriented 32B quantized model."
        )


def strip_reasoning_tokens(raw_text: str) -> str:
    """Remove `<think>...</think>` reasoning blocks emitted by reasoning LLMs before JSON extraction."""
    if not raw_text:
        return ""
    cleaned = raw_text.strip()
    if "</think>" in cleaned:
        # Preserve text after final closing </think> tag when reasoning block wraps prefix
        cleaned = cleaned.split("</think>")[-1].strip()
    elif "<think>" in cleaned:
        cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.DOTALL).strip()
        if cleaned.startswith("<think>"):
            # Unclosed <think> block: jump to fenced JSON block or top-level schema JSON object if present
            fence_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", cleaned, flags=re.DOTALL)
            if fence_match:
                cleaned = fence_match.group(1).strip()
            else:
                obj_match = re.search(
                    r'(\{\s*"(?:question_id|participant_id|discovered_subtopics|is_substantive|subtopics|coded_spans)".*)',
                    cleaned,
                    flags=re.DOTALL,
                )
                if obj_match:
                    cleaned = obj_match.group(1).strip()
                else:
                    cleaned = cleaned[len("<think>") :].strip()
    return cleaned


def resolve_and_verify_coder_spec(
    primary_spec: CoderModelSpec,
    candidate_specs: Sequence[CoderModelSpec],
    *,
    verify_remote: bool = True,
    verify_tokenizer: bool = False,
    api_client: Any = None,
    tokenizer_loader: Optional[Callable[[str, str], Any]] = None,
) -> Tuple[CoderModelSpec, List[Dict[str, Any]]]:
    """
    Resolve an accessible Hugging Face repository and pin exact immutable commit revision (`sha`).

    Preserves truthfulness:
    - Never sets `remote_repo_validated=True` unless remote verification actually succeeded.
    - Records every attempted candidate and exact fallback reason in `audit_log`.
    - For Coder B, strictly blocks any Qwen/DeepSeek-derived repo.
    """
    ordered: List[CoderModelSpec] = []
    seen_keys: set[Tuple[str, str]] = set()
    for spec in (primary_spec, *candidate_specs):
        key = (spec.model_repo.strip(), spec.quantization.strip())
        if key not in seen_keys:
            seen_keys.add(key)
            ordered.append(spec)

    if not verify_remote:
        audit = [
            {
                "model_repo": ordered[0].model_repo,
                "quantization": ordered[0].quantization,
                "status": "SKIPPED_REMOTE_CHECK",
                "reason": "verify_remote=False",
            }
        ]
        return ordered[0], audit

    if api_client is None:
        from huggingface_hub import HfApi  # type: ignore

        api_client = HfApi()

    if verify_tokenizer and tokenizer_loader is None:
        from transformers import AutoTokenizer  # type: ignore

        def _default_tok_loader(repo: str, rev: str) -> Any:
            return AutoTokenizer.from_pretrained(repo, revision=rev, trust_remote_code=False)

        tokenizer_loader = _default_tok_loader

    audit_log: List[Dict[str, Any]] = []
    for cand in ordered:
        # Enforce family safety before any network check
        if cand.coder_id == "coder_b":
            fam = cand.model_family.strip().lower()
            repo_low = cand.model_repo.strip().lower()
            if fam in FORBIDDEN_CODER_B_FAMILIES or fam not in ALLOWED_CODER_B_FAMILIES or "qwen" in repo_low or "deepseek" in repo_low:
                audit_log.append(
                    {
                        "model_repo": cand.model_repo,
                        "quantization": cand.quantization,
                        "status": "REJECTED_DIVERSITY",
                        "reason": "Coder B candidate violates independent model-family invariant.",
                    }
                )
                continue

        try:
            info = api_client.model_info(cand.model_repo)
            if getattr(info, "gated", False):
                # Test tokenizer or file access if token might allow gated repo
                if not getattr(info, "sha", None):
                    raise RuntimeError(f"Gated repository {cand.model_repo} without accessible SHA.")
            resolved_sha = str(getattr(info, "sha", None) or cand.model_revision or "main")

            if verify_tokenizer and tokenizer_loader is not None:
                tokenizer_loader(cand.model_repo, resolved_sha)

            verified = CoderModelSpec(
                coder_id=cand.coder_id,
                model_family=cand.model_family,
                model_repo=cand.model_repo,
                model_revision=resolved_sha,
                quantization=cand.quantization,
                port=cand.port,
                base_model=cand.base_model,
                serving_engine=cand.serving_engine,
                remote_repo_validated=True,
                host=cand.host,
                gpu_memory_fraction=primary_spec.gpu_memory_fraction,
                estimated_weights_vram_mb=cand.estimated_weights_vram_mb,
                kv_cache_vram_mb=cand.kv_cache_vram_mb,
                max_model_len=primary_spec.max_model_len,
                max_output_tokens=primary_spec.max_output_tokens,
                temperature=0.0,
                seed=primary_spec.seed,
                tensor_parallel_size=cand.tensor_parallel_size,
                dtype=cand.dtype,
                enforce_eager=cand.enforce_eager,
                extra_engine_args=dict(cand.extra_engine_args),
            )
            audit_log.append(
                {
                    "model_repo": verified.model_repo,
                    "quantization": verified.quantization,
                    "resolved_revision": resolved_sha,
                    "status": "VERIFIED",
                    "reason": "Remote Hugging Face model metadata and access verified.",
                }
            )
            return verified, audit_log
        except Exception as exc:
            audit_log.append(
                {
                    "model_repo": cand.model_repo,
                    "quantization": cand.quantization,
                    "status": "UNAVAILABLE",
                    "reason": str(exc),
                }
            )

    raise RuntimeError(
        f"No resolvable candidate found for {primary_spec.coder_id}. Audit log: {json.dumps(audit_log, indent=2)}"
    )


def resolve_dual_coder_specs(
    config: GPURuntimeConfig,
    *,
    verify_remote: bool = True,
    verify_tokenizer: bool = False,
    api_client: Any = None,
    tokenizer_loader: Optional[Callable[[str, str], Any]] = None,
) -> Dict[str, Any]:
    """
    Resolve and validate independent Coder A (DeepSeek 32B) and Coder B (Mistral 24B preferred,
    Gemma 3 27B alternative) specifications cleanly before GPU serving.
    """
    resolved_a, audit_a = resolve_and_verify_coder_spec(
        config.coder_a_spec,
        DEFAULT_CODER_A_CANDIDATES,
        verify_remote=verify_remote,
        verify_tokenizer=verify_tokenizer,
        api_client=api_client,
        tokenizer_loader=tokenizer_loader,
    )
    coder_b_pool = (
        *DEFAULT_CODER_B_MISTRAL_CANDIDATES,
        config.coder_b_alternative_spec,
        *ALTERNATIVE_CODER_B_GEMMA_CANDIDATES,
    )
    resolved_b, audit_b = resolve_and_verify_coder_spec(
        config.coder_b_spec,
        coder_b_pool,
        verify_remote=verify_remote,
        verify_tokenizer=verify_tokenizer,
        api_client=api_client,
        tokenizer_loader=tokenizer_loader,
    )
    validate_model_family_diversity(resolved_a, resolved_b)
    config.coder_a_spec = resolved_a
    config.coder_b_spec = resolved_b
    return {
        "coder_a": resolved_a.to_dict(),
        "coder_b": resolved_b.to_dict(),
        "audit_a": audit_a,
        "audit_b": audit_b,
    }


# ---------------------------------------------------------------------------
# Hardware Detection & Memory Budget Derivation
# ---------------------------------------------------------------------------


def _parse_cpu_model() -> str:
    try:
        if Path("/proc/cpuinfo").is_file():
            for line in Path("/proc/cpuinfo").read_text(encoding="utf-8", errors="ignore").splitlines():
                if "model name" in line.lower():
                    return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return platform.processor() or platform.machine() or "unknown_cpu"


def _parse_system_ram_mb() -> Tuple[float, float]:
    try:
        if Path("/proc/meminfo").is_file():
            mem_total_kb = 0.0
            mem_avail_kb = 0.0
            for line in Path("/proc/meminfo").read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.startswith("MemTotal:"):
                    mem_total_kb = float(line.split()[1])
                elif line.startswith("MemAvailable:"):
                    mem_avail_kb = float(line.split()[1])
            if mem_total_kb > 0:
                return round(mem_total_kb / 1024.0, 2), round(mem_avail_kb / 1024.0, 2)
    except Exception:
        pass
    return 8192.0, 4096.0


def detect_hardware_profile() -> HardwareProfile:
    """
    Detect physical accelerator and available VRAM at runtime without assuming documentation specs.
    Checks `torch.cuda` if installed, then `nvidia-smi`, and falls back cleanly to measured CPU specs.
    """
    now_utc = datetime.now(timezone.utc).isoformat()
    hostname = socket.gethostname()
    os_platform = f"{platform.system()} {platform.release()} ({platform.machine()})"
    cpu_model = _parse_cpu_model()
    cpu_cores = os.cpu_count() or 1
    ram_total_mb, ram_avail_mb = _parse_system_ram_mb()

    # 1. Try nvidia-smi query first (works without importing heavy CUDA libs)
    nvidia_smi = shutil.which("nvidia-smi")
    if nvidia_smi:
        try:
            cmd = [
                nvidia_smi,
                "--query-gpu=name,memory.total,memory.free,memory.used,driver_version,compute_cap",
                "--format=csv,noheader,nounits",
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5, check=True)
            lines = [ln.strip() for ln in res.stdout.strip().splitlines() if ln.strip()]
            if lines:
                parts = [p.strip() for p in lines[0].split(",")]
                if len(parts) >= 6:
                    dev_name = parts[0]
                    total_vram = float(parts[1])
                    free_vram = float(parts[2])
                    used_vram = float(parts[3])
                    driver_ver = parts[4]
                    comp_cap = parts[5]

                    cuda_ver = None
                    try:
                        hdr = subprocess.run([nvidia_smi], capture_output=True, text=True, timeout=5)
                        m = re.search(r"CUDA Version:\s*([0-9\.]+)", hdr.stdout)
                        if m:
                            cuda_ver = m.group(1)
                    except Exception:
                        pass

                    return HardwareProfile(
                        measured_at_utc=now_utc,
                        hostname=hostname,
                        os_platform=os_platform,
                        cpu_model=cpu_model,
                        cpu_logical_cores=cpu_cores,
                        system_ram_total_mb=ram_total_mb,
                        system_ram_available_mb=ram_avail_mb,
                        gpu_available=True,
                        gpu_count=len(lines),
                        gpu_device_name=dev_name,
                        gpu_total_vram_mb=total_vram,
                        gpu_free_vram_mb=free_vram,
                        gpu_used_vram_mb=used_vram,
                        cuda_version=cuda_ver,
                        driver_version=driver_ver,
                        compute_capability=comp_cap,
                        detection_method="nvidia-smi",
                    )
        except Exception:
            pass

    # 2. Try torch.cuda if installed
    try:
        import torch  # type: ignore

        if torch.cuda.is_available() and torch.cuda.device_count() > 0:
            props = torch.cuda.get_device_properties(0)
            total_mb = round(props.total_memory / (1024.0 * 1024.0), 2)
            free_b, total_b = torch.cuda.mem_get_info(0)
            free_mb = round(free_b / (1024.0 * 1024.0), 2)
            used_mb = round(total_mb - free_mb, 2)
            return HardwareProfile(
                measured_at_utc=now_utc,
                hostname=hostname,
                os_platform=os_platform,
                cpu_model=cpu_model,
                cpu_logical_cores=cpu_cores,
                system_ram_total_mb=ram_total_mb,
                system_ram_available_mb=ram_avail_mb,
                gpu_available=True,
                gpu_count=int(torch.cuda.device_count()),
                gpu_device_name=str(props.name),
                gpu_total_vram_mb=total_mb,
                gpu_free_vram_mb=free_mb,
                gpu_used_vram_mb=used_mb,
                cuda_version=str(torch.version.cuda),
                driver_version=None,
                compute_capability=f"{props.major}.{props.minor}",
                detection_method="torch.cuda",
            )
    except Exception:
        pass

    # 3. No physical GPU detected
    return HardwareProfile(
        measured_at_utc=now_utc,
        hostname=hostname,
        os_platform=os_platform,
        cpu_model=cpu_model,
        cpu_logical_cores=cpu_cores,
        system_ram_total_mb=ram_total_mb,
        system_ram_available_mb=ram_avail_mb,
        gpu_available=False,
        gpu_count=0,
        gpu_device_name="NONE (CPU-Only Host)",
        gpu_total_vram_mb=0.0,
        gpu_free_vram_mb=0.0,
        gpu_used_vram_mb=0.0,
        cuda_version=None,
        driver_version=None,
        compute_capability=None,
        detection_method="procfs_cpu_fallback",
    )


def derive_memory_budget_from_measurements(
    hardware: HardwareProfile,
    coder_a_measured_vram_mb: float,
    coder_b_measured_vram_mb: float,
    coder_a_kv_cache_mb: float = 6144.0,
    coder_b_kv_cache_mb: float = 6144.0,
    min_headroom_mb: float = 6144.0,
    min_headroom_fraction: float = 0.12,
) -> Dict[str, Any]:
    """
    Empirically derive GPU memory fractions and execution mode from actual measurements
    rather than treating 0.44/0.44 as mandatory constants.
    """
    total_vram = hardware.gpu_total_vram_mb
    free_vram = hardware.gpu_free_vram_mb

    if not hardware.gpu_available or total_vram <= 0.0:
        return {
            "execution_mode": ExecutionMode.CPU_FALLBACK.value,
            "concurrent_feasible": False,
            "single_gpu_feasible": False,
            "gpu_memory_fraction": 0.0,
            "coder_a_memory_fraction": 0.0,
            "coder_b_memory_fraction": 0.0,
            "reserved_vram_headroom_mb": 0.0,
            "reserved_vram_headroom_fraction": 0.0,
            "coder_a_total_required_mb": round(coder_a_measured_vram_mb + coder_a_kv_cache_mb, 2),
            "coder_b_total_required_mb": round(coder_b_measured_vram_mb + coder_b_kv_cache_mb, 2),
            "combined_required_mb": round(
                coder_a_measured_vram_mb + coder_b_measured_vram_mb + coder_a_kv_cache_mb + coder_b_kv_cache_mb, 2
            ),
            "rationale": (
                f"No physical GPU detected on host ({hardware.gpu_device_name}). "
                "Selected CPU_FALLBACK mode with sequential fallback protections."
            ),
        }

    headroom_mb = max(min_headroom_mb, total_vram * min_headroom_fraction)
    headroom_fraction = round(headroom_mb / total_vram, 4)
    usable_vram_mb = max(0.0, free_vram - headroom_mb)

    req_a_mb = coder_a_measured_vram_mb + coder_a_kv_cache_mb
    req_b_mb = coder_b_measured_vram_mb + coder_b_kv_cache_mb
    combined_req_mb = req_a_mb + req_b_mb

    if combined_req_mb <= usable_vram_mb:
        # Both servers fit concurrently with explicit headroom!
        # Distribute the usable VRAM pool proportionally to each model's requirement
        # so neither vLLM V1 server is starved of CUDA-graph/activation/KV-cache memory.
        max_combined_frac = round(min(1.0 - headroom_fraction, usable_vram_mb / total_vram), 4)
        weight_a = req_a_mb / combined_req_mb if combined_req_mb > 0 else 0.54
        frac_a = round(max_combined_frac * weight_a, 4)
        frac_b = round(max(0.0, max_combined_frac - frac_a), 4)

        return {
            "execution_mode": ExecutionMode.CONCURRENT_DUAL_SERVER.value,
            "concurrent_feasible": True,
            "single_gpu_feasible": True,
            "gpu_memory_fraction": round(frac_a + frac_b, 4),
            "coder_a_memory_fraction": frac_a,
            "coder_b_memory_fraction": frac_b,
            "reserved_vram_headroom_mb": round(total_vram * (1.0 - (frac_a + frac_b)), 2),
            "reserved_vram_headroom_fraction": round(1.0 - (frac_a + frac_b), 4),
            "coder_a_total_required_mb": round(req_a_mb, 2),
            "coder_b_total_required_mb": round(req_b_mb, 2),
            "combined_required_mb": round(combined_req_mb, 2),
            "rationale": (
                f"Concurrent dual-coder resident serving fits within {free_vram:.0f} MB free VRAM "
                f"(combined requirement {combined_req_mb:.0f} MB, headroom {headroom_mb:.0f} MB)."
            ),
        }

    max_single_req = max(req_a_mb, req_b_mb)
    if max_single_req <= usable_vram_mb:
        # Single server fits with headroom -> SEQUENTIAL_FALLBACK
        single_frac = round(min(1.0 - headroom_fraction, max(0.50, (max_single_req * 1.10) / total_vram)), 4)
        return {
            "execution_mode": ExecutionMode.SEQUENTIAL_FALLBACK.value,
            "concurrent_feasible": False,
            "single_gpu_feasible": True,
            "gpu_memory_fraction": single_frac,
            "coder_a_memory_fraction": single_frac,
            "coder_b_memory_fraction": single_frac,
            "reserved_vram_headroom_mb": round(total_vram * (1.0 - single_frac), 2),
            "reserved_vram_headroom_fraction": round(1.0 - single_frac, 4),
            "coder_a_total_required_mb": round(req_a_mb, 2),
            "coder_b_total_required_mb": round(req_b_mb, 2),
            "combined_required_mb": round(combined_req_mb, 2),
            "rationale": (
                f"Combined dual-coder requirement ({combined_req_mb:.0f} MB) exceeds usable VRAM after headroom "
                f"({usable_vram_mb:.0f} MB), but single coder ({max_single_req:.0f} MB) fits safely. "
                "Selected SEQUENTIAL_FALLBACK mode."
            ),
        }

    return {
        "execution_mode": ExecutionMode.CPU_FALLBACK.value,
        "concurrent_feasible": False,
        "single_gpu_feasible": False,
        "gpu_memory_fraction": 0.0,
        "coder_a_memory_fraction": 0.0,
        "coder_b_memory_fraction": 0.0,
        "reserved_vram_headroom_mb": round(headroom_mb, 2),
        "reserved_vram_headroom_fraction": headroom_fraction,
        "coder_a_total_required_mb": round(req_a_mb, 2),
        "coder_b_total_required_mb": round(req_b_mb, 2),
        "combined_required_mb": round(combined_req_mb, 2),
        "rationale": (
            f"Available GPU VRAM ({free_vram:.0f} MB) is insufficient for 32B/24B quantized models "
            f"(single model requires {max_single_req:.0f} MB + {headroom_mb:.0f} MB headroom)."
        ),
    }


# ---------------------------------------------------------------------------
# Structured Output Schemas for Qualitative Coding Smoke & Production Requests
# ---------------------------------------------------------------------------


class CodedSpanOutput(BaseModel):
    """Schema for an extracted evidence span and subtopic probability assignment."""

    subtopic_label_en: str = Field(..., min_length=2)
    verbatim_quote: str = Field(..., min_length=1)
    char_start: int = Field(..., ge=0)
    char_end: int = Field(..., ge=1)
    alternative_probabilities: Dict[str, float] = Field(...)
    semantic_importance: float = Field(..., ge=0.0, le=1.0)
    coder_confidence: float = Field(..., ge=0.0, le=1.0)


class StructuredCodingOutput(BaseModel):
    """Canonical structured JSON output expected from each coder LLM per question."""

    question_id: str = Field(..., pattern=r"^Q\d{2}$")
    participant_id: str = Field(..., min_length=1)
    coder_id: Literal["coder_a", "coder_b"]
    missingness_state: Literal[
        "observed_usable",
        "unobserved_missing",
        "infeasible_choice",
        "ambiguous",
    ]
    coded_spans: List[CodedSpanOutput] = Field(default_factory=list)
    rationale_summary: str = Field(..., min_length=3)

    def validate_simplex_invariants(self, tolerance: float = 1e-4) -> None:
        if self.missingness_state == "observed_usable":
            if not self.coded_spans:
                raise ValueError("observed_usable response must contain at least one coded_span.")
            for idx, span in enumerate(self.coded_spans):
                if span.char_end <= span.char_start:
                    raise ValueError(f"Span {idx} has invalid offsets: {span.char_start}..{span.char_end}")
                total = sum(span.alternative_probabilities.values())
                if abs(total - 1.0) > tolerance:
                    raise ValueError(
                        f"Span {idx} alternative_probabilities must sum to 1.0 (+/- {tolerance}), got {total:.6f}"
                    )
        else:
            if self.coded_spans:
                raise ValueError(f"Non-usable state {self.missingness_state} must have empty coded_spans.")


def validate_structured_coding_response(raw_text: str) -> Tuple[SchemaStatus, Optional[Dict[str, Any]], Optional[str]]:
    """Parse and validate a raw LLM response against StructuredCodingOutput and simplex rules."""
    cleaned = strip_reasoning_tokens(raw_text).strip()
    fence_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", cleaned, re.DOTALL)
    if fence_match:
        cleaned = fence_match.group(1).strip()
    elif not cleaned.startswith("{"):
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end > start:
            cleaned = cleaned[start : end + 1]

    try:
        parsed_json = json.loads(cleaned)
    except Exception as exc:
        return SchemaStatus.INVALID_JSON, None, f"JSON decode error: {exc}"

    try:
        model_obj = StructuredCodingOutput(**parsed_json)
        model_obj.validate_simplex_invariants()
        return SchemaStatus.VALID, model_obj.model_dump(), None
    except (ValidationError, ValueError) as exc:
        return SchemaStatus.INVALID_SCHEMA, parsed_json if isinstance(parsed_json, dict) else None, str(exc)


# ---------------------------------------------------------------------------
# Atomic Question Checkpoint Record & Manager
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class QuestionCheckpointRecord:
    """
    Immutable checkpoint record for every accepted coder response.
    Required fields per Agent 07 specification:
    - run_id
    - question_id
    - coder_id
    - prompt_hash
    - source_hash
    - model_repo
    - model_revision
    - quantization
    - generation_config
    - raw_response
    - parsed_response
    - schema_status
    - runtime_sec
    - peak_vram_mb
    """

    run_id: str
    question_id: str
    coder_id: Literal["coder_a", "coder_b"]
    prompt_hash: str
    source_hash: str
    model_repo: str
    model_revision: str
    quantization: str
    generation_config: Dict[str, Any]
    raw_response: str
    parsed_response: Dict[str, Any]
    schema_status: str
    runtime_sec: float
    peak_vram_mb: float
    participant_id: str = "ALL"
    execution_mode: str = ExecutionMode.CONCURRENT_DUAL_SERVER.value
    recorded_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def checkpoint_key(self) -> str:
        """Content-addressed composite key allowing seamless reuse across concurrent/sequential modes."""
        return (
            f"{self.run_id}::{self.question_id}::{self.participant_id}::"
            f"{self.coder_id}::{self.prompt_hash}::{self.source_hash}"
        )

    def validate_record(self) -> None:
        required_str = [
            ("run_id", self.run_id),
            ("question_id", self.question_id),
            ("coder_id", self.coder_id),
            ("prompt_hash", self.prompt_hash),
            ("source_hash", self.source_hash),
            ("model_repo", self.model_repo),
            ("model_revision", self.model_revision),
            ("quantization", self.quantization),
            ("raw_response", self.raw_response),
            ("schema_status", self.schema_status),
        ]
        for name, val in required_str:
            if not val or not str(val).strip():
                raise ValueError(f"QuestionCheckpointRecord missing required field '{name}'.")
        if self.schema_status != SchemaStatus.VALID.value:
            raise ValueError(
                f"Only schema-valid responses may be committed to atomic question checkpoints (got {self.schema_status})."
            )
        if not isinstance(self.parsed_response, dict) or not self.parsed_response:
            raise ValueError("QuestionCheckpointRecord parsed_response must be a non-empty dict.")
        if not isinstance(self.generation_config, dict):
            raise ValueError("QuestionCheckpointRecord generation_config must be a dict.")
        if self.runtime_sec < 0.0:
            raise ValueError("runtime_sec must be non-negative.")
        if self.peak_vram_mb < 0.0:
            raise ValueError("peak_vram_mb must be non-negative.")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AtomicQuestionCheckpointStore:
    """
    Crash-safe atomic checkpoint store for question-level qualitative coding responses.
    Uses atomic temp-file + fsync + os.replace per question/coder record as well as an
    append-only fsynced JSONL WAL so completed valid questions survive:
    - model crash
    - Colab disconnect
    - runtime restart
    - switch from concurrent to sequential mode
    """

    def __init__(self, checkpoint_dir: Path | str, run_id: str = DEFAULT_RUN_ID):
        self.checkpoint_dir = Path(checkpoint_dir).resolve()
        self.run_id = run_id
        self.records_dir = self.checkpoint_dir / self.run_id / "records"
        self.wal_path = self.checkpoint_dir / self.run_id / "checkpoint_wal.jsonl"
        self.flat_wal_path = self.checkpoint_dir / f"{self.run_id}_checkpoint_wal.jsonl"
        self._lock = threading.Lock()
        self.records_dir.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, QuestionCheckpointRecord] = {}
        self.reload()

    @staticmethod
    def _record_filename(record_key: str) -> str:
        digest = hashlib.sha256(record_key.encode("utf-8")).hexdigest()[:24]
        safe_prefix = re.sub(r"[^a-zA-Z0-9_\-]", "_", record_key)[:48]
        return f"{safe_prefix}_{digest}.json"

    def reload(self) -> int:
        """Reload all valid atomic checkpoints from disk, ignoring any truncated/corrupt temp files."""
        loaded: Dict[str, QuestionCheckpointRecord] = {}

        # 1. Load individual atomic JSON files first
        if self.records_dir.is_dir():
            for fpath in sorted(self.records_dir.glob("*.json")):
                try:
                    raw = json.loads(fpath.read_text(encoding="utf-8"))
                    rec = QuestionCheckpointRecord(**raw)
                    rec.validate_record()
                    loaded[rec.checkpoint_key] = rec
                except Exception:
                    # Corrupt or incomplete file is ignored safely
                    continue

        # 2. Replay WAL entries (both nested and flat run-scoped WAL) if any are missing from records_dir
        for wal_candidate in (self.wal_path, self.flat_wal_path):
            if wal_candidate.is_file():
                try:
                    for line in wal_candidate.read_text(encoding="utf-8", errors="ignore").splitlines():
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            raw = json.loads(line)
                            rec = QuestionCheckpointRecord(**raw)
                            rec.validate_record()
                            loaded[rec.checkpoint_key] = rec
                        except Exception:
                            # Tolerate partial trailing line from sudden power/Colab disconnect
                            continue
                except Exception:
                    pass

        with self._lock:
            self._cache = loaded
        return len(loaded)

    def put(self, record: QuestionCheckpointRecord) -> Path:
        """Atomically persist a validated QuestionCheckpointRecord with fsync."""
        record.validate_record()
        key = record.checkpoint_key
        fname = self._record_filename(key)
        target_path = self.records_dir / fname

        payload_bytes = (json.dumps(record.to_dict(), indent=2, sort_keys=True) + "\n").encode("utf-8")
        wal_line_bytes = (json.dumps(record.to_dict(), sort_keys=True) + "\n").encode("utf-8")

        with self._lock:
            self.records_dir.mkdir(parents=True, exist_ok=True)
            # Atomic write to per-record file via NamedTemporaryFile in same directory
            fd, tmp_name = tempfile.mkstemp(
                prefix=f".tmp_{fname}_",
                dir=str(self.records_dir),
            )
            try:
                with os.fdopen(fd, "wb") as tmp_file:
                    tmp_file.write(payload_bytes)
                    tmp_file.flush()
                    os.fsync(tmp_file.fileno())
                os.replace(tmp_name, target_path)
            finally:
                if os.path.exists(tmp_name):
                    try:
                        os.remove(tmp_name)
                    except OSError:
                        pass

            # Append to both per-run WAL and top-level run-scoped WAL with fsync
            for wal_target in (self.wal_path, self.flat_wal_path):
                wal_target.parent.mkdir(parents=True, exist_ok=True)
                with open(wal_target, "ab") as wal_f:
                    wal_f.write(wal_line_bytes)
                    wal_f.flush()
                    os.fsync(wal_f.fileno())

            self._cache[key] = record

        return target_path

    def get(
        self,
        *,
        run_id: str,
        question_id: str,
        coder_id: str,
        prompt_hash: str,
        source_hash: str,
        participant_id: str = "ALL",
    ) -> Optional[QuestionCheckpointRecord]:
        """Lookup a completed valid checkpoint (mode-independent so concurrent->sequential switch preserves hits)."""
        key = f"{run_id}::{question_id}::{participant_id}::{coder_id}::{prompt_hash}::{source_hash}"
        with self._lock:
            return self._cache.get(key)

    def list_completed_questions(self, coder_id: Optional[str] = None) -> List[str]:
        with self._lock:
            q_ids = {
                rec.question_id
                for rec in self._cache.values()
                if coder_id is None or rec.coder_id == coder_id
            }
        return sorted(q_ids)

    def all_records(self) -> List[QuestionCheckpointRecord]:
        with self._lock:
            return list(self._cache.values())


# ---------------------------------------------------------------------------
# GPU Telemetry & Process Tree Helpers (Real NVIDIA / vLLM Subprocess Support)
# ---------------------------------------------------------------------------


def _collect_process_tree_pids(root_pid: Optional[int]) -> set[int]:
    """Return root_pid and any descendant PIDs by scanning /proc/<pid>/stat safely on Linux."""
    if not root_pid or root_pid <= 0:
        return set()
    pids = {int(root_pid)}
    try:
        parent_map: Dict[int, List[int]] = {}
        proc_dir = Path("/proc")
        if proc_dir.is_dir():
            for entry in proc_dir.iterdir():
                if not entry.name.isdigit():
                    continue
                try:
                    stat_txt = (entry / "stat").read_text(encoding="utf-8", errors="ignore")
                    rparen = stat_txt.rfind(")")
                    if rparen == -1:
                        continue
                    rest = stat_txt[rparen + 2 :].split()
                    if len(rest) >= 2:
                        pid_val = int(entry.name)
                        ppid_val = int(rest[1])
                        parent_map.setdefault(ppid_val, []).append(pid_val)
                except Exception:
                    continue
        queue = [int(root_pid)]
        while queue:
            curr = queue.pop(0)
            for child in parent_map.get(curr, []):
                if child not in pids:
                    pids.add(child)
                    queue.append(child)
    except Exception:
        pass
    return pids


def _query_nvidia_smi_snapshot(device_id: int = 0) -> Dict[str, Any]:
    """Query live total/free/used GPU VRAM (MB) and per-PID compute app memory via nvidia-smi."""
    nvidia_smi = shutil.which("nvidia-smi")
    snapshot: Dict[str, Any] = {
        "available": False,
        "gpu_total_mb": 0.0,
        "gpu_free_mb": 0.0,
        "gpu_used_mb": 0.0,
        "compute_apps": {},
    }
    if not nvidia_smi:
        return snapshot

    try:
        mem_cmd = [
            nvidia_smi,
            "-i",
            str(device_id),
            "--query-gpu=memory.total,memory.free,memory.used",
            "--format=csv,noheader,nounits",
        ]
        res = subprocess.run(mem_cmd, capture_output=True, text=True, timeout=5, check=True)
        lines = [ln.strip() for ln in res.stdout.strip().splitlines() if ln.strip()]
        if lines:
            parts = [float(p.strip()) for p in lines[0].split(",")[:3]]
            snapshot["available"] = True
            snapshot["gpu_total_mb"] = round(parts[0], 2)
            snapshot["gpu_free_mb"] = round(parts[1], 2)
            snapshot["gpu_used_mb"] = round(parts[2], 2)
    except Exception:
        pass

    try:
        app_cmd = [
            nvidia_smi,
            "-i",
            str(device_id),
            "--query-compute-apps=pid,used_memory",
            "--format=csv,noheader,nounits",
        ]
        res_apps = subprocess.run(app_cmd, capture_output=True, text=True, timeout=5, check=True)
        apps: Dict[int, float] = {}
        for ln in res_apps.stdout.strip().splitlines():
            ln = ln.strip()
            if not ln:
                continue
            parts = [p.strip() for p in ln.split(",")]
            if len(parts) >= 2 and parts[0].isdigit():
                try:
                    apps[int(parts[0])] = round(float(parts[1]), 2)
                except ValueError:
                    continue
        snapshot["compute_apps"] = apps
    except Exception:
        pass

    return snapshot


def _parse_kv_cache_from_log(log_text: str) -> Optional[float]:
    """Extract allocated GPU KV-cache memory in MB from vLLM startup logs if reported."""
    if not log_text:
        return None
    patterns = [
        r"Available KV cache memory:\s*([0-9]+(?:\.[0-9]+)?)\s*GiB",
        r"GPU KV cache size:\s*([0-9]+(?:\.[0-9]+)?)\s*GiB",
        r"kv[_\s-]*cache[^\n:]*:\s*([0-9]+(?:\.[0-9]+)?)\s*GiB",
        r"Available KV cache memory:\s*([0-9]+(?:\.[0-9]+)?)\s*MiB",
    ]
    for idx, pat in enumerate(patterns):
        matches = re.findall(pat, log_text, flags=re.IGNORECASE)
        if matches:
            val = float(matches[-1])
            if idx == 3:
                return round(val, 2)
            return round(val * 1024.0, 2)
    return None


# ---------------------------------------------------------------------------
# Localhost Coder HTTP Server Endpoint (Real vLLM Subprocess or Deterministic Test Server)
# ---------------------------------------------------------------------------


class _CoderHTTPRequestHandler(http.server.BaseHTTPRequestHandler):
    """Thread-safe localhost HTTP handler exposing `/health`, `/v1/models`, and `/v1/chat/completions`."""

    server_version = "HFGCoderServer/1.1"

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress noisy stdout logging during benchmarks/tests
        pass

    def do_GET(self) -> None:
        srv: "LocalCoderServerProcess" = self.server.coder_process  # type: ignore[attr-defined]
        if self.path == "/health":
            if srv.is_healthy and not srv.simulated_crash:
                self._send_json(
                    200,
                    {
                        "status": "ok",
                        "coder_id": srv.spec.coder_id,
                        "model_family": srv.spec.model_family,
                        "model_repo": srv.spec.model_repo,
                        "quantization": srv.spec.quantization,
                        "resident_vram_mb": srv.resident_vram_mb,
                        "peak_vram_mb": srv.peak_vram_mb,
                        "kv_cache_vram_mb": srv.kv_cache_vram_mb,
                        "active_requests": srv.active_requests,
                    },
                )
            else:
                self._send_json(503, {"status": "unhealthy", "coder_id": srv.spec.coder_id})
            return

        if self.path == "/v1/models":
            self._send_json(
                200,
                {
                    "object": "list",
                    "data": [
                        {
                            "id": srv.spec.model_repo,
                            "object": "model",
                            "owned_by": srv.spec.model_family,
                            "revision": srv.spec.model_revision,
                            "quantization": srv.spec.quantization,
                        }
                    ],
                },
            )
            return

        self._send_json(404, {"error": "Not found"})

    def do_POST(self) -> None:
        srv: "LocalCoderServerProcess" = self.server.coder_process  # type: ignore[attr-defined]
        if self.path != "/v1/chat/completions":
            self._send_json(404, {"error": "Endpoint not found"})
            return

        if not srv.is_healthy or srv.simulated_crash:
            self._send_json(503, {"error": f"Server {srv.spec.coder_id} is unhealthy or crashed"})
            return

        content_len = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_len).decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw_body)
        except Exception as exc:
            self._send_json(400, {"error": f"Invalid JSON payload: {exc}"})
            return

        # Enforce bounded context & generation length at server boundary
        max_tokens = int(payload.get("max_tokens", srv.spec.max_output_tokens))
        if max_tokens > srv.spec.max_output_tokens:
            self._send_json(
                400,
                {
                    "error": f"Requested max_tokens ({max_tokens}) exceeds server bound ({srv.spec.max_output_tokens})"
                },
            )
            return

        prompt_text = json.dumps(payload.get("messages", []))
        est_input_tokens = max(1, len(prompt_text) // 4)
        if est_input_tokens + max_tokens > srv.spec.max_model_len:
            self._send_json(
                400,
                {
                    "error": (
                        f"Total context length ({est_input_tokens} + {max_tokens}) exceeds "
                        f"bounded max_model_len ({srv.spec.max_model_len})"
                    )
                },
            )
            return

        # Check simulated failure injection (for testing recovery after failed request)
        if payload.get("inject_failure") is True or srv.consume_fail_next_request():
            srv.failed_requests += 1
            self._send_json(500, {"error": "Simulated transient inference failure"})
            return

        with srv._req_lock:
            srv.active_requests += 1
            srv.total_requests += 1
            concurrent_kv_spike = srv.active_requests * 192.0
            current_vram = srv.resident_vram_mb + srv.kv_cache_vram_mb + concurrent_kv_spike
            if current_vram > srv.peak_vram_mb:
                srv.peak_vram_mb = round(current_vram, 2)

        try:
            latency_sec = float(payload.get("simulated_latency_sec", 0.015))
            time.sleep(max(0.002, min(latency_sec, 2.0)))

            meta = payload.get("hfg_metadata", {})
            q_id = str(meta.get("question_id", "Q01"))
            p_id = str(meta.get("participant_id", "PARTICIPANT_001"))
            verbatim = str(meta.get("verbatim_quote", "Governance coordination across poles requires clear mandate."))
            schema_type = str(meta.get("schema_type", "StructuredCodingOutput"))
            force_invalid_json = bool(payload.get("force_invalid_json", False))
            force_invalid_simplex = bool(payload.get("force_invalid_simplex", False))

            if force_invalid_json:
                assistant_content = "{unclosed_json_response"
            elif schema_type == "LLMCorpusDiscoveryResponse":
                sup_rids = list(meta.get("supporting_response_ids") or [f"RESP_{q_id}_001"])
                sup_pids = list(meta.get("supporting_participant_ids") or [p_id])
                eg_policy = str(meta.get("economic_good_policy", "CONDITIONAL"))
                goods_block = (
                    {
                        "goods_applicability": "APPLICABLE",
                        "applicability_domain": "decision_rights",
                        "applicability_rationale": "Addresses allocation of institutional mandate and resources.",
                        "question_frame_override_applied": False,
                        "alternative_good_classes": {
                            "pole_level_coordination": "club_good",
                            "laboratory_autonomy": "private_good",
                        },
                        "imposes_linear_ordering": False,
                    }
                    if eg_policy in {"ENABLED", "CONDITIONAL"}
                    else {
                        "goods_applicability": "NOT_APPLICABLE",
                        "applicability_domain": None,
                        "applicability_rationale": "Question policy DISABLED for economic goods taxonomy.",
                        "question_frame_override_applied": False,
                        "alternative_good_classes": {},
                        "imposes_linear_ordering": False,
                    }
                )
                subtopic_key = f"mandate_allocation_{q_id.lower()}_{srv.spec.coder_id}"
                label_en = (
                    f"Operational Coordination & Resource Mandate ({q_id} - {srv.spec.model_family})"
                    if srv.spec.coder_id == "coder_a"
                    else f"Decentralized Authority & Research Autonomy ({q_id} - {srv.spec.model_family})"
                )
                response_obj = {
                    "question_id": q_id,
                    "discovered_subtopics": [
                        {
                            "subtopic_key": subtopic_key,
                            "proposed_label_en": label_en,
                            "definition": f"Bottom-up governance mechanism emerging in participant answers to {q_id}.",
                            "decision_object": "Institutional coordination authority and resource stewardship",
                            "mechanism": "Shared mandate specification and transparent criteria",
                            "scope": "pole_and_laboratory",
                            "discovered_alternatives": [
                                {
                                    "alternative_id": "pole_level_coordination",
                                    "label_en": "Pole-level coordination",
                                    "description": "Coordinate decisions across shared research poles.",
                                },
                                {
                                    "alternative_id": "laboratory_autonomy",
                                    "label_en": "Laboratory-level autonomy",
                                    "description": "Preserve primary authority at individual laboratories.",
                                },
                            ],
                            "goods_assessment": goods_block,
                            "is_minority_position": False,
                            "supporting_response_ids": sup_rids,
                            "supporting_participant_ids": sup_pids,
                            "rationale": f"Inductively derived across {len(sup_pids)} participant statements by {srv.spec.coder_id}.",
                        }
                    ],
                    "minority_positions_noted": [],
                    "discovery_notes": f"Completed bottom-up discovery via {srv.spec.model_repo}",
                }
                assistant_content = json.dumps(response_obj)
            elif schema_type == "LLMQuestionCodingResponse":
                src_text = str(meta.get("source_text") or verbatim)
                ep_status = str(meta.get("response_status") or "substantive")
                m_state = str(meta.get("missingness_state") or "observed_usable")
                lang = str(meta.get("detected_language") or "fr")
                eg_policy = str(meta.get("economic_good_policy") or "CONDITIONAL")
                st_key = str(meta.get("default_subtopic_key") or f"mandate_allocation_{q_id.lower()}_{srv.spec.coder_id}")
                st_label = str(meta.get("default_subtopic_label") or f"Operational Coordination ({q_id})")

                quote = src_text.strip() if src_text.strip() else src_text
                c_start = src_text.find(quote) if quote else 0
                if c_start < 0:
                    quote = src_text
                    c_start = 0
                c_end = c_start + len(quote)

                is_reportable_non_pref = ep_status in {
                    "explicit_no_opinion",
                    "explicit_insufficient_experience",
                    "explicit_insufficient_information",
                    "ambiguous",
                }
                is_blank_non_rep = ep_status in {
                    "raw_blank",
                    "punctuation_uninterpretable",
                    "no_additional_remarks",
                } or not src_text.strip()

                if is_blank_non_rep:
                    response_obj = {
                        "participant_id": p_id,
                        "question_id": q_id,
                        "response_id": str(meta.get("response_id", "")),
                        "is_substantive": False,
                        "missingness_state": m_state,
                        "response_status": ep_status,
                        "detected_language": lang if lang in {"fr", "de", "en"} else "fr",
                        "evidence_spans": [],
                        "uncertainty_statements": [],
                        "subtopics": [],
                        "values": [],
                        "unmentioned_subtopic_keys": [],
                    }
                elif is_reportable_non_pref:
                    response_obj = {
                        "participant_id": p_id,
                        "question_id": q_id,
                        "response_id": str(meta.get("response_id", "")),
                        "is_substantive": True,
                        "missingness_state": m_state,
                        "response_status": ep_status,
                        "detected_language": lang if lang in {"fr", "de", "en"} else "fr",
                        "evidence_spans": [
                            {
                                "verbatim_quote": quote,
                                "detected_language": lang if lang in {"fr", "de", "en"} else "fr",
                                "language_confidence": 0.99,
                                "char_start": c_start,
                                "char_end": c_end,
                                "span_role": "explicit_uncertainty_or_no_opinion",
                            }
                        ],
                        "uncertainty_statements": [
                            {
                                "verbatim_quote": quote,
                                "detected_language": lang if lang in {"fr", "de", "en"} else "fr",
                                "language_confidence": 0.99,
                                "char_start": c_start,
                                "char_end": c_end,
                                "span_role": "explicit_uncertainty_or_no_opinion",
                            }
                        ],
                        "subtopics": [],
                        "values": [],
                        "unmentioned_subtopic_keys": [st_key],
                    }
                else:
                    dist = (
                        {"pole_level_coordination": 0.65, "laboratory_autonomy": 0.35}
                        if srv.spec.coder_id == "coder_a"
                        else {"pole_level_coordination": 0.55, "laboratory_autonomy": 0.45}
                    )
                    imp = 0.84 if srv.spec.coder_id == "coder_a" else 0.79
                    conf = 0.92 if srv.spec.coder_id == "coder_a" else 0.89
                    good_cls = "club_good" if eg_policy in {"ENABLED", "CONDITIONAL"} else "NOT_APPLICABLE"
                    val_label = (
                        "Institutional Clarity & Subsidiarity"
                        if srv.spec.coder_id == "coder_a"
                        else "Collegial Transparency"
                    )
                    response_obj = {
                        "participant_id": p_id,
                        "question_id": q_id,
                        "response_id": str(meta.get("response_id", "")),
                        "is_substantive": True,
                        "missingness_state": "observed_usable",
                        "response_status": ep_status if ep_status in {"substantive", "mixed_uncertainty_and_preference"} else "substantive",
                        "detected_language": lang if lang in {"fr", "de", "en"} else "fr",
                        "evidence_spans": [
                            {
                                "verbatim_quote": quote,
                                "detected_language": lang if lang in {"fr", "de", "en"} else "fr",
                                "language_confidence": 0.98,
                                "char_start": c_start,
                                "char_end": c_end,
                                "english_working_gloss": f"Statement from {p_id} on {q_id}.",
                                "span_role": "substantive_evidence",
                            }
                        ],
                        "uncertainty_statements": [],
                        "subtopics": [
                            {
                                "subtopic_key": st_key,
                                "proposed_label_en": st_label,
                                "proposed_description": f"Operational governance position expressed by {p_id} for {q_id}.",
                                "decision_object": "Governance mandate and coordination level",
                                "mechanism": "Structured mandate allocation",
                                "scope": "pole_and_laboratory",
                                "candidate_alternative_distribution": dist,
                                "probability_interpretation": "epistemic_uncertainty_over_preference",
                                "semantic_importance": imp,
                                "coder_confidence": conf,
                                "proposed_economic_good_class": good_cls,
                                "evidence_quotes": [quote],
                            }
                        ],
                        "values": [
                            {
                                "original_label": val_label,
                                "value_definition": f"Organisational principle evidenced by {p_id} statement in {q_id}.",
                                "polarity": 0.6,
                                "semantic_importance": imp,
                                "coder_confidence": conf,
                                "evidence_quotes": [quote],
                            }
                        ],
                        "unmentioned_subtopic_keys": [],
                        "coder_rationale": f"Independent coding by {srv.spec.coder_id} ({srv.spec.model_repo}).",
                    }
                assistant_content = json.dumps(response_obj)
            else:
                if srv.spec.coder_id == "coder_a":
                    probs = {"professor": 0.10, "laboratory": 0.65, "pole": 0.20, "institute": 0.05}
                    importance = 0.85
                    confidence = 0.94
                else:
                    probs = {"professor": 0.15, "laboratory": 0.60, "pole": 0.20, "institute": 0.05}
                    importance = 0.82
                    confidence = 0.91

                if force_invalid_simplex:
                    probs = {"professor": 0.50, "laboratory": 0.10}

                response_obj = {
                    "question_id": q_id,
                    "participant_id": p_id,
                    "coder_id": srv.spec.coder_id,
                    "missingness_state": "observed_usable",
                    "coded_spans": [
                        {
                            "subtopic_label_en": f"institutional_coordination_{srv.spec.coder_id}",
                            "verbatim_quote": verbatim,
                            "char_start": 0,
                            "char_end": max(1, len(verbatim)),
                            "alternative_probabilities": probs,
                            "semantic_importance": importance,
                            "coder_confidence": confidence,
                        }
                    ],
                    "rationale_summary": (
                        f"Deterministic structured analysis by {srv.spec.coder_id} "
                        f"({srv.spec.model_family}:{srv.spec.model_repo})."
                    ),
                }
                assistant_content = json.dumps(response_obj)

            est_output_tokens = max(1, len(assistant_content) // 4)
            resp_body = {
                "id": f"chatcmpl-{srv.spec.coder_id}-{srv.total_requests}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": srv.spec.model_repo,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": assistant_content},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": est_input_tokens,
                    "completion_tokens": est_output_tokens,
                    "total_tokens": est_input_tokens + est_output_tokens,
                },
                "runtime_telemetry": {
                    "coder_id": srv.spec.coder_id,
                    "resident_vram_mb": srv.resident_vram_mb,
                    "peak_vram_mb": srv.peak_vram_mb,
                    "kv_cache_vram_mb": srv.kv_cache_vram_mb,
                },
            }
            self._send_json(200, resp_body)
        finally:
            with srv._req_lock:
                srv.active_requests = max(0, srv.active_requests - 1)

    def _send_json(self, status_code: int, data: Dict[str, Any]) -> None:
        raw = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


class _ThreadedHTTPServer(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class LocalCoderServerProcess:
    """
    Manages a localhost HTTP endpoint for a single coder model (`coder_a` or `coder_b`).

    - When `hardware.gpu_available is True` and `use_mock_server` is not explicitly `True`,
      launches a real `vllm.entrypoints.openai.api_server` subprocess on `spec.host:spec.port`,
      polls `/health` and `/v1/models`, measures real `nvidia-smi` VRAM and KV-cache logs,
      and fails fast with diagnostic logs rather than silently falling back to a mock server.
    - On CPU-only hosts or in explicit mock tests (`use_mock_server=True`), launches the
      deterministic thread-safe localhost HTTP server for CI verification.
    """

    def __init__(
        self,
        spec: CoderModelSpec,
        hardware: HardwareProfile,
        *,
        use_mock_server: Optional[bool] = None,
        startup_timeout_sec: float = 900.0,
        log_dir: Optional[Path | str] = None,
    ):
        self.spec = spec
        self.hardware = hardware
        if use_mock_server is not None:
            self.use_mock_server = bool(use_mock_server)
        else:
            self.use_mock_server = not bool(self.hardware.gpu_available)

        self.startup_timeout_sec = max(10.0, float(startup_timeout_sec))
        self.log_dir = Path(log_dir).resolve() if log_dir else (Path.cwd() / ".checkpoints" / "vllm_logs")
        self.log_path: Path = self.log_dir / f"{self.spec.coder_id}_{self.spec.port}.log"
        self.served_model_id: str = self.spec.model_repo
        self.server_backend: str = "mock_http" if self.use_mock_server else "vllm_openai_server"

        self.is_running: bool = False
        self.is_healthy: bool = False
        self.simulated_crash: bool = False
        self.load_time_sec: float = 0.0
        self.resident_vram_mb: float = 0.0
        self.kv_cache_vram_mb: float = 0.0
        self.peak_vram_mb: float = 0.0
        self._baseline_gpu_used_mb: float = 0.0
        self.active_requests: int = 0
        self.total_requests: int = 0
        self.failed_requests: int = 0
        self._fail_next_count: int = 0
        self._req_lock = threading.Lock()
        self._httpd: Optional[_ThreadedHTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._proc: Optional[subprocess.Popen[str]] = None
        self._log_file_handle: Optional[Any] = None

    def inject_transient_failures(self, count: int = 1) -> None:
        with self._req_lock:
            self._fail_next_count = max(0, count)

    def consume_fail_next_request(self) -> bool:
        with self._req_lock:
            if self._fail_next_count > 0:
                self._fail_next_count -= 1
                return True
            return False

    def _tail_log(self, max_lines: int = 200) -> str:
        try:
            if self.log_path.is_file():
                lines = self.log_path.read_text(encoding="utf-8", errors="replace").splitlines()
                return "\n".join(lines[-max_lines:])
        except Exception:
            pass
        return "(no log output captured)"

    def sample_peak_vram_mb(self) -> float:
        """Query live GPU VRAM usage for this server (or return tracked mock peak VRAM)."""
        if self.use_mock_server or not self.hardware.gpu_available:
            return self.peak_vram_mb
        snap = _query_nvidia_smi_snapshot(0)
        if not snap.get("available"):
            return self.peak_vram_mb
        pid = self._proc.pid if self._proc is not None else None
        tree_pids = _collect_process_tree_pids(pid)
        apps: Dict[int, float] = snap.get("compute_apps", {})
        proc_vram = sum(v for p, v in apps.items() if p in tree_pids)
        if proc_vram > 0.0:
            measured = round(proc_vram, 2)
        else:
            measured = round(max(self.resident_vram_mb, float(snap.get("gpu_used_mb", 0.0)) - self._baseline_gpu_used_mb), 2)
        if measured > self.peak_vram_mb:
            self.peak_vram_mb = measured
        return self.peak_vram_mb

    def _build_vllm_command(self) -> List[str]:
        cmd = [
            sys.executable,
            "-m",
            "vllm.entrypoints.openai.api_server",
            "--host",
            self.spec.host,
            "--port",
            str(self.spec.port),
            "--model",
            self.spec.model_repo,
            "--revision",
            self.spec.model_revision,
            "--served-model-name",
            self.spec.model_repo,
            "--gpu-memory-utilization",
            str(self.spec.gpu_memory_fraction),
            "--max-model-len",
            str(self.spec.max_model_len),
            "--dtype",
            str(self.spec.dtype),
            "--seed",
            str(self.spec.seed),
            "--tensor-parallel-size",
            str(self.spec.tensor_parallel_size),
            "--trust-remote-code",
        ]
        if self.spec.enforce_eager:
            cmd.append("--enforce-eager")
        for arg_k, arg_v in (self.spec.extra_engine_args or {}).items():
            flag = str(arg_k) if str(arg_k).startswith("--") else f"--{str(arg_k).replace('_', '-')}"
            if arg_v is True:
                cmd.append(flag)
            elif arg_v not in (False, None):
                cmd.extend([flag, str(arg_v)])
        return cmd

    def _start_real_gpu_server(self) -> float:
        """Spawn real vLLM OpenAI API server subprocess and wait until healthy."""
        if not self.hardware.gpu_available:
            raise RuntimeError("Cannot start real vLLM GPU server without a physical GPU.")
        if importlib.util.find_spec("vllm") is None:
            raise RuntimeError(
                "vLLM (`vllm`) is not installed in this Python environment. "
                "Install `vllm` in Colab before starting live GPU coder servers."
            )

        pre_snap = _query_nvidia_smi_snapshot(0)
        self._baseline_gpu_used_mb = float(pre_snap.get("gpu_used_mb", 0.0))

        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log_file_handle = open(self.log_path, "w", encoding="utf-8")

        cmd = self._build_vllm_command()
        t0 = time.perf_counter()
        self._proc = subprocess.Popen(
            cmd,
            stdout=self._log_file_handle,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )

        deadline = time.perf_counter() + self.startup_timeout_sec
        health_url = f"{self.spec.endpoint_url}/health"
        models_url = f"{self.spec.endpoint_url}/v1/models"
        last_err = "starting"

        while time.perf_counter() < deadline:
            rc = self._proc.poll()
            if rc is not None:
                tail = self._tail_log(200)
                self.stop()
                raise RuntimeError(
                    f"Real vLLM server for {self.spec.coder_id} ({self.spec.model_repo}) "
                    f"exited unexpectedly with exit code {rc}.\nLog tail ({self.log_path}):\n{tail}"
                )

            try:
                with urllib.request.urlopen(health_url, timeout=3.0) as h_resp:
                    if h_resp.status == 200:
                        with urllib.request.urlopen(models_url, timeout=3.0) as m_resp:
                            if m_resp.status == 200:
                                m_body = json.loads(m_resp.read().decode("utf-8"))
                                data_items = m_body.get("data") or []
                                if data_items and isinstance(data_items[0], dict):
                                    self.served_model_id = str(data_items[0].get("id") or self.spec.model_repo)
                                break
            except Exception as exc:
                last_err = str(exc)

            time.sleep(2.0)
        else:
            tail = self._tail_log(200)
            self.stop()
            raise TimeoutError(
                f"Timed out after {self.startup_timeout_sec:.0f}s waiting for vLLM server "
                f"{self.spec.coder_id} ({self.spec.model_repo}) at {self.spec.endpoint_url}. "
                f"Last error: {last_err}\nLog tail ({self.log_path}):\n{tail}"
            )

        post_snap = _query_nvidia_smi_snapshot(0)
        tree_pids = _collect_process_tree_pids(self._proc.pid)
        apps: Dict[int, float] = post_snap.get("compute_apps", {})
        proc_vram = sum(v for p, v in apps.items() if p in tree_pids)
        if proc_vram > 0.0:
            self.resident_vram_mb = round(proc_vram, 2)
        else:
            delta_vram = max(0.0, float(post_snap.get("gpu_used_mb", 0.0)) - self._baseline_gpu_used_mb)
            self.resident_vram_mb = round(delta_vram, 2)

        log_text = ""
        try:
            if self.log_path.is_file():
                log_text = self.log_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            pass
        parsed_kv = _parse_kv_cache_from_log(log_text)
        self.kv_cache_vram_mb = (
            parsed_kv if parsed_kv is not None else round(float(self.spec.kv_cache_vram_mb), 2)
        )
        self.peak_vram_mb = max(self.resident_vram_mb, self.peak_vram_mb)
        self.is_running = True
        self.is_healthy = True
        self.simulated_crash = False
        self.load_time_sec = round(time.perf_counter() - t0, 4)
        return self.load_time_sec

    def start(self) -> float:
        """Start the localhost server endpoint and measure model load time and VRAM footprint."""
        if self.is_running:
            if self._proc is not None and self._proc.poll() is not None:
                self.is_running = False
                self.is_healthy = False
            else:
                return self.load_time_sec

        if not self.use_mock_server:
            return self._start_real_gpu_server()

        t0 = time.perf_counter()
        self._httpd = _ThreadedHTTPServer((self.spec.host, self.spec.port), _CoderHTTPRequestHandler)
        self._httpd.coder_process = self  # type: ignore[attr-defined]
        self._thread = threading.Thread(
            target=self._httpd.serve_forever,
            name=f"hfg-{self.spec.coder_id}-server",
            daemon=True,
        )
        self._thread.start()

        # Mock / CPU-only VRAM tracking (test-only when hardware.gpu_available is simulated)
        if self.hardware.gpu_available and self.hardware.gpu_total_vram_mb > 0:
            allocated_budget_mb = self.hardware.gpu_total_vram_mb * self.spec.gpu_memory_fraction
            self.resident_vram_mb = round(min(self.spec.estimated_weights_vram_mb, allocated_budget_mb * 0.72), 2)
            self.kv_cache_vram_mb = round(max(1024.0, allocated_budget_mb - self.resident_vram_mb), 2)
            self.peak_vram_mb = round(self.resident_vram_mb + self.kv_cache_vram_mb * 0.25, 2)
        else:
            self.resident_vram_mb = 0.0
            self.kv_cache_vram_mb = 0.0
            self.peak_vram_mb = 0.0

        self.is_running = True
        self.is_healthy = True
        self.simulated_crash = False
        self.load_time_sec = round(time.perf_counter() - t0, 4)
        return self.load_time_sec

    def stop(self) -> None:
        """Gracefully shut down the localhost server (vLLM process group or mock HTTP) and release VRAM."""
        self.is_healthy = False
        if self._proc is not None:
            pid = self._proc.pid
            try:
                pgid = os.getpgid(pid)
                os.killpg(pgid, signal.SIGTERM)
            except Exception:
                try:
                    self._proc.terminate()
                except Exception:
                    pass
            try:
                self._proc.wait(timeout=12.0)
            except subprocess.TimeoutExpired:
                try:
                    pgid = os.getpgid(pid)
                    os.killpg(pgid, signal.SIGKILL)
                except Exception:
                    try:
                        self._proc.kill()
                    except Exception:
                        pass
                try:
                    self._proc.wait(timeout=5.0)
                except Exception:
                    pass
            self._proc = None

        if self._log_file_handle is not None:
            try:
                self._log_file_handle.close()
            except Exception:
                pass
            self._log_file_handle = None

        if self._httpd is not None:
            try:
                self._httpd.shutdown()
                self._httpd.server_close()
            except Exception:
                pass
            self._httpd = None
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None
        self.is_running = False
        self.resident_vram_mb = 0.0
        self.kv_cache_vram_mb = 0.0

    def restart(self) -> float:
        """Recover from a crash or unhealthy state by restarting the server endpoint."""
        self.stop()
        return self.start()


# ---------------------------------------------------------------------------
# Dual-Coder Runtime Manager, Health Polling, Structured Client & Fallback
# ---------------------------------------------------------------------------


@dataclass
class StructuredCoderResponse:
    """Result of a structured coding request against a coder endpoint."""

    coder_id: Literal["coder_a", "coder_b"]
    question_id: str
    participant_id: str
    schema_status: SchemaStatus
    raw_response: str
    parsed_response: Optional[Dict[str, Any]]
    error_message: Optional[str]
    runtime_sec: float
    peak_vram_mb: float
    input_tokens: int
    output_tokens: int
    from_checkpoint: bool = False
    execution_mode_used: str = ExecutionMode.CONCURRENT_DUAL_SERVER.value


class DualCoderRuntimeManager:
    """
    Production runtime orchestrator for Agent 07.
    Provides:
    - Hardware preflight
    - Separate localhost server endpoints (`coder_a` and `coder_b`)
    - Bounded context, bounded generation length, bounded concurrency
    - Health polling
    - Structured-output client with schema validation
    - Atomic question checkpoints (`AtomicQuestionCheckpointStore`)
    - Model-specific failure isolation & recovery
    - Graceful shutdown
    - Automatic sequential fallback when concurrent serving is unstable or VRAM-constrained
    """

    def __init__(
        self,
        config: GPURuntimeConfig,
        hardware: Optional[HardwareProfile] = None,
        checkpoint_store: Optional[AtomicQuestionCheckpointStore] = None,
        *,
        use_mock_server: Optional[bool] = None,
        startup_timeout_sec: Optional[float] = None,
        log_dir: Optional[Path | str] = None,
    ):
        self.config = config
        self.config.validate_config()
        self.hardware = hardware or detect_hardware_profile()
        self.checkpoint_store = checkpoint_store or AtomicQuestionCheckpointStore(
            checkpoint_dir=self.config.checkpoint_dir,
            run_id=self.config.run_id,
        )
        timeout = float(startup_timeout_sec if startup_timeout_sec is not None else self.config.startup_timeout_sec)
        self.server_a = LocalCoderServerProcess(
            self.config.coder_a_spec,
            self.hardware,
            use_mock_server=use_mock_server,
            startup_timeout_sec=timeout,
            log_dir=log_dir,
        )
        self.server_b = LocalCoderServerProcess(
            self.config.coder_b_spec,
            self.hardware,
            use_mock_server=use_mock_server,
            startup_timeout_sec=timeout,
            log_dir=log_dir,
        )
        self._sem_a = threading.BoundedSemaphore(self.config.max_concurrent_requests_per_coder)
        self._sem_b = threading.BoundedSemaphore(self.config.max_concurrent_requests_per_coder)
        self._sem_total = threading.BoundedSemaphore(self.config.max_total_concurrent_requests)
        self.fallback_events: List[Dict[str, Any]] = []

    def run_hardware_preflight(self) -> Dict[str, Any]:
        """
        Execute hardware preflight checks:
        1. Detect physical GPU and free VRAM.
        2. Verify model-family diversity.
        3. Determine whether concurrent dual-server, sequential GPU, or CPU fallback mode applies.
        """
        validate_model_family_diversity(self.config.coder_a_spec, self.config.coder_b_spec)
        budget = derive_memory_budget_from_measurements(
            hardware=self.hardware,
            coder_a_measured_vram_mb=self.config.coder_a_spec.estimated_weights_vram_mb,
            coder_b_measured_vram_mb=self.config.coder_b_spec.estimated_weights_vram_mb,
            coder_a_kv_cache_mb=self.config.coder_a_spec.kv_cache_vram_mb,
            coder_b_kv_cache_mb=self.config.coder_b_spec.kv_cache_vram_mb,
            min_headroom_mb=self.config.reserved_vram_headroom_mb,
            min_headroom_fraction=self.config.reserved_vram_headroom_fraction,
        )
        self.config.measured_hardware = self.hardware.to_dict()
        return {
            "preflight_passed": True,
            "hardware": self.hardware.to_dict(),
            "derived_budget": budget,
            "recommended_execution_mode": budget["execution_mode"],
        }

    def poll_health(self, coder_id: Literal["coder_a", "coder_b"], timeout_sec: Optional[float] = None) -> Dict[str, Any]:
        """Poll `/health` on the specified coder localhost server."""
        spec = self.config.coder_a_spec if coder_id == "coder_a" else self.config.coder_b_spec
        srv = self.server_a if coder_id == "coder_a" else self.server_b
        deadline = time.perf_counter() + (timeout_sec or self.config.health_Check_timeout_sec)
        url = f"{spec.endpoint_url}/health"
        last_err = "uninitialized"

        while time.perf_counter() < deadline:
            if not srv.use_mock_server and srv._proc is not None and srv._proc.poll() is not None:
                return {"healthy": False, "status_code": 503, "error": f"Server process exited with code {srv._proc.poll()}"}
            try:
                req = urllib.request.Request(url, method="GET")
                with urllib.request.urlopen(req, timeout=2.0) as resp:
                    raw_body = resp.read().decode("utf-8", errors="replace").strip()
                    if resp.status == 200:
                        if raw_body:
                            body = json.loads(raw_body)
                            if not isinstance(body, dict) or body.get("status", "ok") == "ok":
                                return {"healthy": True, "status_code": 200, "details": body}
                        else:
                            # vLLM's /health returns HTTP 200 with empty body
                            return {"healthy": True, "status_code": 200, "details": {"status": "ok"}}
            except urllib.error.HTTPError as he:
                last_err = f"HTTP {he.code}"
                if time.perf_counter() + self.config.health_poll_interval_sec >= deadline:
                    break
            except Exception as exc:
                last_err = str(exc)
            time.sleep(min(self.config.health_poll_interval_sec, 0.1))

        return {"healthy": False, "status_code": 503, "error": last_err}

    def start_servers(self, mode: Optional[ExecutionMode] = None) -> Dict[str, Any]:
        """Start coder servers according to the active or requested ExecutionMode."""
        target_mode = mode or self.config.execution_mode
        if target_mode == ExecutionMode.CONCURRENT_DUAL_SERVER:
            try:
                t_a = self.server_a.start()
                t_b = self.server_b.start()
                h_a = self.poll_health("coder_a", timeout_sec=min(30.0, self.config.health_Check_timeout_sec))
                h_b = self.poll_health("coder_b", timeout_sec=min(30.0, self.config.health_Check_timeout_sec))
            except Exception as exc:
                if self.config.auto_sequential_fallback:
                    self._trigger_sequential_fallback(
                        f"Exception during concurrent server startup ({exc}); switching to sequential fallback."
                    )
                    return {"mode": self.config.execution_mode.value, "fallback_triggered": True, "reason": str(exc)}
                raise

            if not (h_a["healthy"] and h_b["healthy"]):
                if self.config.auto_sequential_fallback:
                    self._trigger_sequential_fallback("Health check failed during concurrent server startup.")
                    return {"mode": self.config.execution_mode.value, "fallback_triggered": True}
                raise RuntimeError(f"Concurrent server startup failed health check: A={h_a}, B={h_b}")
            return {
                "mode": target_mode.value,
                "coder_a_load_sec": t_a,
                "coder_b_load_sec": t_b,
                "coder_a_health": h_a,
                "coder_b_health": h_b,
            }
        else:
            # In sequential or CPU fallback mode, servers are launched one at a time on demand
            return {"mode": target_mode.value, "on_demand_sequential": True}

    def shutdown(self) -> None:
        """Gracefully shut down both coder endpoints."""
        self.server_a.stop()
        self.server_b.stop()

    def _trigger_sequential_fallback(self, reason: str) -> None:
        """
        Switch runtime from CONCURRENT_DUAL_SERVER to SEQUENTIAL_FALLBACK without invalidating
        any completed question checkpoints.
        """
        prev_mode = self.config.execution_mode
        self.config.execution_mode = ExecutionMode.SEQUENTIAL_FALLBACK
        self.server_a.stop()
        self.server_b.stop()
        self.fallback_events.append(
            {
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "previous_mode": prev_mode.value,
                "new_mode": ExecutionMode.SEQUENTIAL_FALLBACK.value,
                "reason": reason,
                "preserved_checkpoint_count": len(self.checkpoint_store.all_records()),
            }
        )

    @staticmethod
    def compute_hash(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _execute_chat_completion_core(
        self,
        *,
        coder_id: Literal["coder_a", "coder_b"],
        question_id: str,
        participant_id: str,
        system_prompt: str,
        user_prompt: str,
        prompt_hash: str,
        source_hash: str,
        validator_fn: Callable[[str], Tuple[SchemaStatus, Optional[Dict[str, Any]], Optional[str]]],
        max_tokens: Optional[int] = None,
        hfg_metadata: Optional[Dict[str, Any]] = None,
        extra_payload: Optional[Dict[str, Any]] = None,
        auto_recover: bool = True,
        request_json_mode: bool = True,
    ) -> StructuredCoderResponse:
        """Shared bounded, checkpointed, schema-validated localhost chat completion client."""
        cached = self.checkpoint_store.get(
            run_id=self.config.run_id,
            question_id=question_id,
            coder_id=coder_id,
            prompt_hash=prompt_hash,
            source_hash=source_hash,
            participant_id=participant_id,
        )
        if cached is not None:
            return StructuredCoderResponse(
                coder_id=coder_id,
                question_id=question_id,
                participant_id=participant_id,
                schema_status=SchemaStatus(cached.schema_status),
                raw_response=cached.raw_response,
                parsed_response=cached.parsed_response,
                error_message=None,
                runtime_sec=0.0,
                peak_vram_mb=cached.peak_vram_mb,
                input_tokens=0,
                output_tokens=0,
                from_checkpoint=True,
                execution_mode_used=cached.execution_mode,
            )

        spec = self.config.coder_a_spec if coder_id == "coder_a" else self.config.coder_b_spec
        srv = self.server_a if coder_id == "coder_a" else self.server_b
        coder_sem = self._sem_a if coder_id == "coder_a" else self._sem_b

        req_max_tokens = min(max_tokens or spec.max_output_tokens, self.config.max_generation_length)
        est_prompt_tokens = (len(system_prompt) + len(user_prompt)) // 4
        if est_prompt_tokens + req_max_tokens > self.config.max_context_length:
            return StructuredCoderResponse(
                coder_id=coder_id,
                question_id=question_id,
                participant_id=participant_id,
                schema_status=SchemaStatus.REQUEST_FAILED,
                raw_response="",
                parsed_response=None,
                error_message=(
                    f"Input prompt + generation tokens exceed bounded context limit ({self.config.max_context_length})"
                ),
                runtime_sec=0.0,
                peak_vram_mb=srv.peak_vram_mb,
                input_tokens=est_prompt_tokens,
                output_tokens=0,
                from_checkpoint=False,
                execution_mode_used=self.config.execution_mode.value,
            )

        payload: Dict[str, Any] = {
            "model": srv.served_model_id or spec.model_repo,
            "temperature": 0.0,
            "seed": spec.seed,
            "max_tokens": req_max_tokens,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if request_json_mode:
            payload["response_format"] = {"type": "json_object"}
        if srv.use_mock_server and hfg_metadata:
            payload["hfg_metadata"] = hfg_metadata
        if extra_payload:
            payload.update(extra_payload)

        last_error: Optional[str] = None
        last_status = SchemaStatus.REQUEST_FAILED
        last_raw = ""

        with self._sem_total, coder_sem:
            for _attempt in range(self.config.max_retries_per_request + 1):
                if not srv.is_running:
                    srv.start()

                # Refresh model identifier once server has started
                payload["model"] = srv.served_model_id or spec.model_repo
                if _attempt > 0 and last_error and not srv.use_mock_server:
                    payload["seed"] = int(spec.seed) + _attempt
                    payload["messages"] = [
                        {"role": "system", "content": system_prompt},
                        {
                            "role": "user",
                            "content": (
                                f"{user_prompt}\n\n"
                                f"[VALIDATION ERROR ON PREVIOUS ATTEMPT: {last_error}. "
                                "Keep any <think> reasoning under 60 words and output ONLY a valid JSON object "
                                "fixing this exact issue with all required keys.]"
                            ),
                        },
                    ]
                t0 = time.perf_counter()
                try:
                    # Client-side fault injection support so Stage 5 recovery works identically on real vLLM
                    if not srv.use_mock_server and (payload.get("inject_failure") is True or srv.consume_fail_next_request()):
                        srv.failed_requests += 1
                        raise RuntimeError("Simulated transient inference failure")

                    req = urllib.request.Request(
                        f"{spec.endpoint_url}/v1/chat/completions",
                        data=json.dumps(payload).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    try:
                        with urllib.request.urlopen(req, timeout=self.config.request_timeout_sec) as resp:
                            raw_resp_bytes = resp.read()
                    except urllib.error.HTTPError as http_exc:
                        # Some vLLM chat templates or model families reject response_format=json_object with HTTP 400;
                        # retry immediately without response_format rather than dropping an entire coder.
                        if http_exc.code == 400 and "response_format" in payload:
                            payload.pop("response_format", None)
                            retry_req = urllib.request.Request(
                                f"{spec.endpoint_url}/v1/chat/completions",
                                data=json.dumps(payload).encode("utf-8"),
                                headers={"Content-Type": "application/json"},
                                method="POST",
                            )
                            with urllib.request.urlopen(retry_req, timeout=self.config.request_timeout_sec) as retry_resp:
                                raw_resp_bytes = retry_resp.read()
                        else:
                            raise

                    elapsed = round(time.perf_counter() - t0, 4)
                    resp_data = json.loads(raw_resp_bytes.decode("utf-8"))
                    last_raw = resp_data["choices"][0]["message"]["content"]
                    usage = resp_data.get("usage", {})
                    telemetry = resp_data.get("runtime_telemetry", {})
                    live_peak = srv.sample_peak_vram_mb()
                    peak_vram = float(telemetry.get("peak_vram_mb", live_peak))

                    cleaned_raw = strip_reasoning_tokens(last_raw)
                    status, parsed, err = validator_fn(cleaned_raw)
                    if status == SchemaStatus.VALID and parsed is not None:
                        checkpoint_rec = QuestionCheckpointRecord(
                            run_id=self.config.run_id,
                            question_id=question_id,
                            participant_id=participant_id,
                            coder_id=coder_id,
                            prompt_hash=prompt_hash,
                            source_hash=source_hash,
                            model_repo=spec.model_repo,
                            model_revision=spec.model_revision,
                            quantization=spec.quantization,
                            generation_config={
                                "temperature": 0.0,
                                "seed": spec.seed,
                                "max_tokens": req_max_tokens,
                                "max_model_len": spec.max_model_len,
                            },
                            raw_response=last_raw,
                            parsed_response=parsed,
                            schema_status=status.value,
                            runtime_sec=elapsed,
                            peak_vram_mb=peak_vram,
                            execution_mode=self.config.execution_mode.value,
                        )
                        self.checkpoint_store.put(checkpoint_rec)
                        return StructuredCoderResponse(
                            coder_id=coder_id,
                            question_id=question_id,
                            participant_id=participant_id,
                            schema_status=status,
                            raw_response=last_raw,
                            parsed_response=parsed,
                            error_message=None,
                            runtime_sec=elapsed,
                            peak_vram_mb=peak_vram,
                            input_tokens=int(usage.get("prompt_tokens", est_prompt_tokens)),
                            output_tokens=int(usage.get("completion_tokens", max(1, len(last_raw) // 4))),
                            from_checkpoint=False,
                            execution_mode_used=self.config.execution_mode.value,
                        )
                    else:
                        last_status = status
                        last_error = err
                        if auto_recover:
                            payload.pop("force_invalid_json", None)
                            payload.pop("force_invalid_simplex", None)
                            payload.pop("response_format", None)
                except Exception as exc:
                    last_status = SchemaStatus.REQUEST_FAILED
                    last_error = str(exc)
                    if auto_recover:
                        payload.pop("inject_failure", None)
                        health = self.poll_health(coder_id, timeout_sec=2.0)
                        if not health["healthy"]:
                            srv.restart()

        return StructuredCoderResponse(
            coder_id=coder_id,
            question_id=question_id,
            participant_id=participant_id,
            schema_status=last_status,
            raw_response=last_raw,
            parsed_response=None,
            error_message=last_error,
            runtime_sec=0.0,
            peak_vram_mb=srv.peak_vram_mb,
            input_tokens=0,
            output_tokens=0,
            from_checkpoint=False,
            execution_mode_used=self.config.execution_mode.value,
        )

    def execute_structured_request(
        self,
        *,
        coder_id: Literal["coder_a", "coder_b"],
        question_id: str,
        participant_id: str,
        prompt_text: str,
        source_text: str,
        max_tokens: Optional[int] = None,
        extra_payload: Optional[Dict[str, Any]] = None,
        auto_recover: bool = True,
    ) -> StructuredCoderResponse:
        """
        Send a bounded, schema-validated StructuredCodingOutput request to `coder_a` or `coder_b`.
        Checks atomic checkpoints, strips reasoning tokens, isolates failures, and commits valid results.
        """
        prompt_hash = self.compute_hash(prompt_text)
        source_hash = self.compute_hash(source_text)
        return self._execute_chat_completion_core(
            coder_id=coder_id,
            question_id=question_id,
            participant_id=participant_id,
            system_prompt="Respond strictly with schema-valid JSON matching StructuredCodingOutput.",
            user_prompt=prompt_text,
            prompt_hash=prompt_hash,
            source_hash=source_hash,
            validator_fn=validate_structured_coding_response,
            max_tokens=max_tokens,
            hfg_metadata={
                "schema_type": "StructuredCodingOutput",
                "question_id": question_id,
                "participant_id": participant_id,
                "verbatim_quote": source_text,
            },
            extra_payload=extra_payload,
            auto_recover=auto_recover,
        )

    def execute_json_chat_completion(
        self,
        *,
        coder_id: Literal["coder_a", "coder_b"],
        question_id: str,
        participant_id: str,
        system_prompt: str,
        user_prompt: str,
        source_hash: str,
        validator_fn: Callable[[str], Tuple[SchemaStatus, Optional[Dict[str, Any]], Optional[str]]],
        prompt_hash: Optional[str] = None,
        max_tokens: Optional[int] = None,
        hfg_metadata: Optional[Dict[str, Any]] = None,
        auto_recover: bool = True,
    ) -> StructuredCoderResponse:
        """
        Execute a generic schema-validated JSON chat completion against `coder_a` or `coder_b`
        using Agent 07's bounded context, semaphore concurrency, checkpoint WAL, and recovery stack.
        """
        resolved_prompt_hash = prompt_hash or self.compute_hash(f"{system_prompt}\n---\n{user_prompt}")
        return self._execute_chat_completion_core(
            coder_id=coder_id,
            question_id=question_id,
            participant_id=participant_id,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            prompt_hash=resolved_prompt_hash,
            source_hash=source_hash,
            validator_fn=validator_fn,
            max_tokens=max_tokens,
            hfg_metadata=hfg_metadata,
            auto_recover=auto_recover,
        )

    def code_question_dual(
        self,
        *,
        question_id: str,
        participant_id: str,
        prompt_text: str,
        source_text: str,
    ) -> Dict[str, StructuredCoderResponse]:
        """
        Execute dual-coder coding for a question.
        - If in CONCURRENT_DUAL_SERVER mode, dispatches requests to `coder_a` and `coder_b` simultaneously.
        - If concurrent execution fails and `auto_sequential_fallback` is enabled, automatically falls back
          to SEQUENTIAL_FALLBACK without invalidating any completed checkpoint.
        - If in SEQUENTIAL_FALLBACK or CPU_FALLBACK mode, runs `coder_a` then `coder_b` sequentially,
          stopping the first server before starting the second to respect single-model memory budgets.
        """
        if self.config.execution_mode == ExecutionMode.CONCURRENT_DUAL_SERVER:
            self.server_a.start()
            self.server_b.start()

            results: Dict[str, StructuredCoderResponse] = {}

            def _call(cid: Literal["coder_a", "coder_b"]) -> None:
                results[cid] = self.execute_structured_request(
                    coder_id=cid,
                    question_id=question_id,
                    participant_id=participant_id,
                    prompt_text=prompt_text,
                    source_text=source_text,
                )

            t_a = threading.Thread(target=_call, args=("coder_a",))
            t_b = threading.Thread(target=_call, args=("coder_b",))
            t_a.start()
            t_b.start()
            t_a.join()
            t_b.join()

            res_a = results.get("coder_a")
            res_b = results.get("coder_b")
            if (
                res_a is None
                or res_b is None
                or res_a.schema_status != SchemaStatus.VALID
                or res_b.schema_status != SchemaStatus.VALID
            ):
                if self.config.auto_sequential_fallback:
                    self._trigger_sequential_fallback(
                        f"Concurrent dual request failed on {question_id}; falling back to sequential execution."
                    )
                    return self._code_question_sequential(
                        question_id=question_id,
                        participant_id=participant_id,
                        prompt_text=prompt_text,
                        source_text=source_text,
                    )
            return results

        return self._code_question_sequential(
            question_id=question_id,
            participant_id=participant_id,
            prompt_text=prompt_text,
            source_text=source_text,
        )

    def _code_question_sequential(
        self,
        *,
        question_id: str,
        participant_id: str,
        prompt_text: str,
        source_text: str,
    ) -> Dict[str, StructuredCoderResponse]:
        """Run Coder A then Coder B sequentially, ensuring at most one server is resident at a time."""
        self.server_b.stop()
        self.server_a.start()
        res_a = self.execute_structured_request(
            coder_id="coder_a",
            question_id=question_id,
            participant_id=participant_id,
            prompt_text=prompt_text,
            source_text=source_text,
        )
        self.server_a.stop()

        self.server_b.start()
        res_b = self.execute_structured_request(
            coder_id="coder_b",
            question_id=question_id,
            participant_id=participant_id,
            prompt_text=prompt_text,
            source_text=source_text,
        )
        self.server_b.stop()
        return {"coder_a": res_a, "coder_b": res_b}

    def verify_full_survey_coding_gates(self, base_dir: Path | str) -> Tuple[bool, str]:
        """
        Enforce User Request & Architecture Gate Rule:
        Do NOT perform the authoritative full-survey qualitative coding run until:
        1. Agent 01 Gate 1 passes (`data/normalized/answers_normalized.parquet` exists and is registered).
        2. Agent 02 coding schemas are validated (`src/nlp/subtopic_extraction.py` and `src/nlp/value_extraction.py` exist).
        """
        root = Path(base_dir).resolve()
        norm_parquet = root / "data" / "normalized" / "answers_normalized.parquet"
        subtopic_mod = root / "src" / "nlp" / "subtopic_extraction.py"
        subtopic_flat = root / "src" / "subtopic_extraction.py"

        gate_1_ok = norm_parquet.is_file()
        gate_2_ok = subtopic_mod.is_file() or subtopic_flat.is_file()

        self.config.gate_1_ingestion_passed = gate_1_ok
        self.config.gate_2_coding_schemas_validated = gate_2_ok
        self.config.full_survey_coding_authorized = gate_1_ok and gate_2_ok

        if not gate_1_ok:
            return False, "BLOCKED_BY_GATE_1: Agent 01 normalized answers (data/normalized/answers_normalized.parquet) not yet generated."
        if not gate_2_ok:
            return False, "BLOCKED_BY_GATE_2: Agent 02 qualitative coding modules (subtopic_extraction.py) not yet validated."
        return True, "AUTHORIZED"


# ---------------------------------------------------------------------------
# 5-Stage Runtime Benchmark Suite
# ---------------------------------------------------------------------------


def _benchmark_structured_prompt(
    question_id: str,
    participant_id: str,
    coder_id: str,
    source_text: str,
) -> str:
    """Build a concise, deterministic schema prompt so real reasoning/instruct LLMs emit StructuredCodingOutput JSON."""
    quote_len = max(1, len(source_text))
    return (
        f"Analyze the stakeholder response below and output ONLY a valid JSON object matching StructuredCodingOutput.\n"
        f"- question_id: \"{question_id}\"\n"
        f"- participant_id: \"{participant_id}\"\n"
        f"- coder_id: \"{coder_id}\"\n"
        f"- missingness_state: \"observed_usable\"\n"
        f"- coded_spans: array with 1 object containing keys: "
        f"subtopic_label_en (str), verbatim_quote (exact substring \"{source_text}\"), "
        f"char_start (0), char_end ({quote_len}), "
        f"alternative_probabilities (object whose numeric values sum to exactly 1.0, e.g. "
        f"{{\"pole\": 0.7, \"laboratory\": 0.3}}), "
        f"semantic_importance (float 0..1), coder_confidence (float 0..1)\n"
        f"- rationale_summary: non-empty string\n"
        f"Response text: \"{source_text}\"\n"
        f"Output strictly raw JSON with no extra commentary."
    )


def run_runtime_benchmark_suite(
    config: GPURuntimeConfig,
    hardware: Optional[HardwareProfile] = None,
    bounded_concurrency_requests: int = 6,
    *,
    use_mock_server: Optional[bool] = None,
    startup_timeout_sec: Optional[float] = None,
    base_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Execute the 5 mandatory Agent 07 runtime benchmark stages:
    1. Coder A alone
    2. Coder B alone
    3. Both servers resident
    4. One simultaneous structured request to each
    5. Bounded concurrent requests

    Measures and records:
    - model load time
    - actual VRAM after load
    - peak VRAM during inference
    - KV-cache allocation
    - input/output throughput (tokens/sec)
    - schema-valid output rate
    - server health
    - recovery after failed request
    """
    hw = hardware or detect_hardware_profile()
    bench_ckpt_dir = tempfile.mkdtemp(prefix="hfg_bench_ckpt_")
    mgr: Optional[DualCoderRuntimeManager] = None

    try:
        store = AtomicQuestionCheckpointStore(checkpoint_dir=bench_ckpt_dir, run_id=config.run_id)
        mgr = DualCoderRuntimeManager(
            config=config,
            hardware=hw,
            checkpoint_store=store,
            use_mock_server=use_mock_server,
            startup_timeout_sec=startup_timeout_sec,
        )

        stages: Dict[str, Any] = {}
        health_poll_window = min(30.0, config.health_Check_timeout_sec)

        # -------------------------------------------------------------------
        # Stage 1: Coder A alone
        # -------------------------------------------------------------------
        mgr.shutdown()
        load_a_sec = mgr.server_a.start()
        health_a = mgr.poll_health("coder_a", timeout_sec=health_poll_window)
        src_s1 = "Les poles doivent coordonner les ressources de laboratoire."
        res_a_single = mgr.execute_structured_request(
            coder_id="coder_a",
            question_id="Q01",
            participant_id="BENCH_P01",
            prompt_text=_benchmark_structured_prompt("Q01", "BENCH_P01", "coder_a", src_s1),
            source_text=src_s1,
        )
        dur_a = max(res_a_single.runtime_sec, 1e-4)
        stages["1_coder_a_alone"] = {
            "coder_id": "coder_a",
            "model_repo": config.coder_a_spec.model_repo,
            "model_revision": config.coder_a_spec.model_revision,
            "model_family": config.coder_a_spec.model_family,
            "quantization": config.coder_a_spec.quantization,
            "server_backend": mgr.server_a.server_backend,
            "model_load_time_sec": load_a_sec,
            "actual_vram_after_load_mb": mgr.server_a.resident_vram_mb,
            "kv_cache_allocation_mb": mgr.server_a.kv_cache_vram_mb,
            "peak_vram_during_inference_mb": max(res_a_single.peak_vram_mb, mgr.server_a.peak_vram_mb),
            "estimated_weights_vram_mb": config.coder_a_spec.estimated_weights_vram_mb,
            "input_throughput_tok_per_sec": round(res_a_single.input_tokens / dur_a, 2),
            "output_throughput_tok_per_sec": round(res_a_single.output_tokens / dur_a, 2),
            "schema_valid_output_rate": 1.0 if res_a_single.schema_status == SchemaStatus.VALID else 0.0,
            "server_health": health_a["healthy"],
        }
        mgr.server_a.stop()

        # -------------------------------------------------------------------
        # Stage 2: Coder B alone
        # -------------------------------------------------------------------
        load_b_sec = mgr.server_b.start()
        health_b = mgr.poll_health("coder_b", timeout_sec=health_poll_window)
        src_s2 = "Die Koordination zwischen den Polen sollte transparent sein."
        res_b_single = mgr.execute_structured_request(
            coder_id="coder_b",
            question_id="Q02",
            participant_id="BENCH_P01",
            prompt_text=_benchmark_structured_prompt("Q02", "BENCH_P01", "coder_b", src_s2),
            source_text=src_s2,
        )
        dur_b = max(res_b_single.runtime_sec, 1e-4)
        stages["2_coder_b_alone"] = {
            "coder_id": "coder_b",
            "model_repo": config.coder_b_spec.model_repo,
            "model_revision": config.coder_b_spec.model_revision,
            "model_family": config.coder_b_spec.model_family,
            "quantization": config.coder_b_spec.quantization,
            "server_backend": mgr.server_b.server_backend,
            "model_load_time_sec": load_b_sec,
            "actual_vram_after_load_mb": mgr.server_b.resident_vram_mb,
            "kv_cache_allocation_mb": mgr.server_b.kv_cache_vram_mb,
            "peak_vram_during_inference_mb": max(res_b_single.peak_vram_mb, mgr.server_b.peak_vram_mb),
            "estimated_weights_vram_mb": config.coder_b_spec.estimated_weights_vram_mb,
            "input_throughput_tok_per_sec": round(res_b_single.input_tokens / dur_b, 2),
            "output_throughput_tok_per_sec": round(res_b_single.output_tokens / dur_b, 2),
            "schema_valid_output_rate": 1.0 if res_b_single.schema_status == SchemaStatus.VALID else 0.0,
            "server_health": health_b["healthy"],
        }
        mgr.server_b.stop()

        # -------------------------------------------------------------------
        # Stage 3: Both servers resident
        # -------------------------------------------------------------------
        pre_both_snap = _query_nvidia_smi_snapshot(0) if hw.gpu_available and not mgr.server_a.use_mock_server else {}
        t0_both = time.perf_counter()
        mgr.server_a.start()
        mgr.server_b.start()
        both_load_sec = round(time.perf_counter() - t0_both, 4)
        health_a_both = mgr.poll_health("coder_a", timeout_sec=health_poll_window)
        health_b_both = mgr.poll_health("coder_b", timeout_sec=health_poll_window)
        combined_resident_vram = round(mgr.server_a.resident_vram_mb + mgr.server_b.resident_vram_mb, 2)
        combined_kv_cache_vram = round(mgr.server_a.kv_cache_vram_mb + mgr.server_b.kv_cache_vram_mb, 2)
        post_both_snap = _query_nvidia_smi_snapshot(0) if hw.gpu_available and not mgr.server_a.use_mock_server else {}
        stages["3_both_servers_resident"] = {
            "both_load_time_sec": both_load_sec,
            "coder_a_endpoint": config.coder_a_spec.endpoint_url,
            "coder_b_endpoint": config.coder_b_spec.endpoint_url,
            "coder_a_vram_after_load_mb": mgr.server_a.resident_vram_mb,
            "coder_b_vram_after_load_mb": mgr.server_b.resident_vram_mb,
            "actual_combined_vram_after_load_mb": combined_resident_vram,
            "gpu_total_used_vram_mb": float(post_both_snap.get("gpu_used_mb", combined_resident_vram)),
            "gpu_delta_used_vram_mb": round(
                max(0.0, float(post_both_snap.get("gpu_used_mb", 0.0)) - float(pre_both_snap.get("gpu_used_mb", 0.0))),
                2,
            )
            if post_both_snap.get("available")
            else combined_resident_vram,
            "combined_kv_cache_allocation_mb": combined_kv_cache_vram,
            "estimated_combined_weights_vram_mb": round(
                config.coder_a_spec.estimated_weights_vram_mb + config.coder_b_spec.estimated_weights_vram_mb, 2
            ),
            "coder_a_healthy": health_a_both["healthy"],
            "coder_b_healthy": health_b_both["healthy"],
            "both_healthy": bool(health_a_both["healthy"] and health_b_both["healthy"]),
        }

        # -------------------------------------------------------------------
        # Stage 4: One simultaneous structured request to each
        # -------------------------------------------------------------------
        src_s4 = "Shared research infrastructure should be managed at the pole level."
        t0_sim = time.perf_counter()
        results_s4: Dict[str, StructuredCoderResponse] = {}

        def _sim_call(cid: Literal["coder_a", "coder_b"]) -> None:
            results_s4[cid] = mgr.execute_structured_request(
                coder_id=cid,
                question_id="Q03",
                participant_id="BENCH_P02",
                prompt_text=_benchmark_structured_prompt("Q03", "BENCH_P02", cid, src_s4),
                source_text=src_s4,
            )

        t_s4_a = threading.Thread(target=_sim_call, args=("coder_a",))
        t_s4_b = threading.Thread(target=_sim_call, args=("coder_b",))
        t_s4_a.start()
        t_s4_b.start()
        t_s4_a.join()
        t_s4_b.join()

        sim_wall_sec = max(round(time.perf_counter() - t0_sim, 4), 1e-4)
        sim_a = results_s4["coder_a"]
        sim_b = results_s4["coder_b"]
        sim_valid_rate = (
            (1.0 if sim_a.schema_status == SchemaStatus.VALID else 0.0)
            + (1.0 if sim_b.schema_status == SchemaStatus.VALID else 0.0)
        ) / 2.0
        stages["4_simultaneous_structured_request"] = {
            "wall_time_sec": sim_wall_sec,
            "coder_a_runtime_sec": sim_a.runtime_sec,
            "coder_b_runtime_sec": sim_b.runtime_sec,
            "combined_peak_vram_mb": round(sim_a.peak_vram_mb + sim_b.peak_vram_mb, 2),
            "combined_input_throughput_tok_per_sec": round(
                (sim_a.input_tokens + sim_b.input_tokens) / sim_wall_sec, 2
            ),
            "combined_output_throughput_tok_per_sec": round(
                (sim_a.output_tokens + sim_b.output_tokens) / sim_wall_sec, 2
            ),
            "schema_valid_output_rate": sim_valid_rate,
            "coder_a_status": sim_a.schema_status.value,
            "coder_b_status": sim_b.schema_status.value,
        }

        # -------------------------------------------------------------------
        # Stage 5: Bounded concurrent requests & Failure Recovery Check
        # -------------------------------------------------------------------
        mgr.server_a.start()
        mgr.server_b.start()
        batch_responses: List[StructuredCoderResponse] = []
        batch_lock = threading.Lock()

        def _worker(idx: int) -> None:
            cid: Literal["coder_a", "coder_b"] = "coder_a" if idx % 2 == 0 else "coder_b"
            qid = f"Q{(idx % 13) + 1:02d}"
            pid = f"BENCH_CONC_{idx:03d}"
            src_txt = f"Participant {pid} response text on {qid} governance allocation."
            resp = mgr.execute_structured_request(
                coder_id=cid,
                question_id=qid,
                participant_id=pid,
                prompt_text=_benchmark_structured_prompt(qid, pid, cid, src_txt),
                source_text=src_txt,
            )
            with batch_lock:
                batch_responses.append(resp)

        t0_conc = time.perf_counter()
        threads = [threading.Thread(target=_worker, args=(i,)) for i in range(bounded_concurrency_requests)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        conc_wall_sec = max(round(time.perf_counter() - t0_conc, 4), 1e-4)

        valid_count = sum(1 for r in batch_responses if r.schema_status == SchemaStatus.VALID)
        total_in_tok = sum(r.input_tokens for r in batch_responses)
        total_out_tok = sum(r.output_tokens for r in batch_responses)
        peak_vram_conc = round(mgr.server_a.sample_peak_vram_mb() + mgr.server_b.sample_peak_vram_mb(), 2)

        # Test explicit recovery after failed request
        src_rec = "Individual evaluations must remain fair and transparent."
        mgr.server_a.inject_transient_failures(count=1)
        recovery_resp = mgr.execute_structured_request(
            coder_id="coder_a",
            question_id="Q13",
            participant_id="BENCH_RECOVERY_01",
            prompt_text=_benchmark_structured_prompt("Q13", "BENCH_RECOVERY_01", "coder_a", src_rec),
            source_text=src_rec,
            auto_recover=True,
        )

        # Verify model-specific failure isolation on Coder B while Coder A remains healthy
        if mgr.server_b.use_mock_server:
            mgr.server_b.simulated_crash = True
            health_a_during_b_crash = mgr.poll_health("coder_a", timeout_sec=2.0)
            mgr.server_b.restart()
            health_b_after_restart = mgr.poll_health("coder_b", timeout_sec=5.0)
        else:
            mgr.server_b.stop()
            health_a_during_b_crash = mgr.poll_health("coder_a", timeout_sec=5.0)
            mgr.server_b.restart()
            health_b_after_restart = mgr.poll_health("coder_b", timeout_sec=health_poll_window)

        stages["5_bounded_concurrent_requests"] = {
            "total_requests": bounded_concurrency_requests,
            "max_concurrent_requests_per_coder": config.max_concurrent_requests_per_coder,
            "max_total_concurrent_requests": config.max_total_concurrent_requests,
            "wall_time_sec": conc_wall_sec,
            "peak_vram_during_inference_mb": peak_vram_conc,
            "input_throughput_tok_per_sec": round(total_in_tok / conc_wall_sec, 2),
            "output_throughput_tok_per_sec": round(total_out_tok / conc_wall_sec, 2),
            "schema_valid_output_rate": round(valid_count / max(1, len(batch_responses)), 4),
            "recovery_after_failed_request_passed": recovery_resp.schema_status == SchemaStatus.VALID,
            "model_failure_isolation_verified": bool(
                health_a_during_b_crash["healthy"] and health_b_after_restart["healthy"]
            ),
        }

        mgr.shutdown()

        # Derive memory budget from benchmark measurements
        derived_budget = derive_memory_budget_from_measurements(
            hardware=hw,
            coder_a_measured_vram_mb=(
                stages["1_coder_a_alone"]["actual_vram_after_load_mb"]
                if hw.gpu_available and stages["1_coder_a_alone"]["actual_vram_after_load_mb"] > 0.0
                else config.coder_a_spec.estimated_weights_vram_mb
            ),
            coder_b_measured_vram_mb=(
                stages["2_coder_b_alone"]["actual_vram_after_load_mb"]
                if hw.gpu_available and stages["2_coder_b_alone"]["actual_vram_after_load_mb"] > 0.0
                else config.coder_b_spec.estimated_weights_vram_mb
            ),
            coder_a_kv_cache_mb=(
                stages["1_coder_a_alone"]["kv_cache_allocation_mb"]
                if hw.gpu_available and stages["1_coder_a_alone"]["kv_cache_allocation_mb"] > 0.0
                else config.coder_a_spec.kv_cache_vram_mb
            ),
            coder_b_kv_cache_mb=(
                stages["2_coder_b_alone"]["kv_cache_allocation_mb"]
                if hw.gpu_available and stages["2_coder_b_alone"]["kv_cache_allocation_mb"] > 0.0
                else config.coder_b_spec.kv_cache_vram_mb
            ),
            min_headroom_mb=config.reserved_vram_headroom_mb,
            min_headroom_fraction=config.reserved_vram_headroom_fraction,
        )

        gate_root = (base_dir or Path.cwd()).resolve()
        gate_ok, gate_msg = mgr.verify_full_survey_coding_gates(gate_root)

        return {
            "benchmark_version": "v1.1.0",
            "run_id": config.run_id,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "runtime_implementation_status": "VALID",
            "live_gpu_benchmark_status": (
                "EXECUTED_LIVE_GPU" if (hw.gpu_available and not use_mock_server) else "NOT_EXECUTED_NO_GPU"
            ),
            "production_dual_model_validation": False,
            "measured_hardware": hw.to_dict(),
            "coder_a_spec": config.coder_a_spec.to_dict(),
            "coder_b_spec": config.coder_b_spec.to_dict(),
            "stages": stages,
            "derived_memory_budget": derived_budget,
            "upstream_gate_check": {
                "full_survey_coding_authorized": gate_ok,
                "status_message": gate_msg,
            },
        }
    finally:
        if mgr is not None:
            try:
                mgr.shutdown()
            except Exception:
                pass
        shutil.rmtree(bench_ckpt_dir, ignore_errors=True)


def build_and_save_runtime_config(
    base_dir: Optional[Path] = None,
    run_id: str = DEFAULT_RUN_ID,
    *,
    resolve_remote_models: Optional[bool] = None,
    verify_tokenizer: bool = False,
    use_mock_server: Optional[bool] = None,
    startup_timeout_sec: Optional[float] = None,
    bounded_concurrency_requests: int = 6,
    hardware: Optional[HardwareProfile] = None,
    api_client: Any = None,
) -> Tuple[GPURuntimeConfig, Dict[str, Any], Path]:
    """
    Detect runtime hardware, resolve model repositories (when live GPU is present),
    run the 5-stage runtime benchmark, derive memory budgets, and persist
    `runs/<run_id>/gpu_runtime_config.json` (plus `gpu_runtime_benchmark.json` on GPU).

    On CPU-only hosts, preserves `live_gpu_benchmark_status = "NOT_EXECUTED_NO_GPU"`
    and `production_dual_model_validation = False`.
    """
    root = (base_dir or Path.cwd()).resolve()
    hw = hardware or detect_hardware_profile()
    cfg = GPURuntimeConfig(run_id=run_id)
    cfg.measured_hardware = hw.to_dict()

    resolution_audit: Optional[Dict[str, Any]] = None
    is_live_gpu = bool(hw.gpu_available and use_mock_server is not True)

    if is_live_gpu:
        # Derive initial safe preflight fractions before booting dual vLLM servers
        initial_budget = derive_memory_budget_from_measurements(
            hardware=hw,
            coder_a_measured_vram_mb=cfg.coder_a_spec.estimated_weights_vram_mb,
            coder_b_measured_vram_mb=cfg.coder_b_spec.estimated_weights_vram_mb,
            coder_a_kv_cache_mb=cfg.coder_a_spec.kv_cache_vram_mb,
            coder_b_kv_cache_mb=cfg.coder_b_spec.kv_cache_vram_mb,
            min_headroom_mb=cfg.reserved_vram_headroom_mb,
            min_headroom_fraction=cfg.reserved_vram_headroom_fraction,
        )
        cfg.execution_mode = ExecutionMode(initial_budget["execution_mode"])
        if initial_budget["gpu_memory_fraction"] > 0.0:
            cfg.gpu_memory_fraction = initial_budget["gpu_memory_fraction"]
            cfg.coder_a_memory_fraction = initial_budget["coder_a_memory_fraction"]
            cfg.coder_b_memory_fraction = initial_budget["coder_b_memory_fraction"]
            cfg.coder_a_spec = replace(
                cfg.coder_a_spec,
                gpu_memory_fraction=initial_budget["coder_a_memory_fraction"],
            )
            cfg.coder_b_spec = replace(
                cfg.coder_b_spec,
                gpu_memory_fraction=initial_budget["coder_b_memory_fraction"],
            )

        if resolve_remote_models is not False:
            resolution_audit = resolve_dual_coder_specs(
                cfg,
                verify_remote=True,
                verify_tokenizer=verify_tokenizer,
                api_client=api_client,
            )

    benchmark_report = run_runtime_benchmark_suite(
        config=cfg,
        hardware=hw,
        bounded_concurrency_requests=bounded_concurrency_requests,
        use_mock_server=use_mock_server,
        startup_timeout_sec=startup_timeout_sec,
        base_dir=root,
    )
    if resolution_audit is not None:
        benchmark_report["model_resolution_audit"] = resolution_audit

    budget = benchmark_report["derived_memory_budget"]
    cfg.execution_mode = ExecutionMode(budget["execution_mode"])
    if budget["gpu_memory_fraction"] > 0.0:
        cfg.gpu_memory_fraction = budget["gpu_memory_fraction"]
        cfg.coder_a_memory_fraction = budget["coder_a_memory_fraction"]
        cfg.coder_b_memory_fraction = budget["coder_b_memory_fraction"]
        cfg.coder_a_spec = replace(
            cfg.coder_a_spec,
            gpu_memory_fraction=budget["coder_a_memory_fraction"],
        )
        cfg.coder_b_spec = replace(
            cfg.coder_b_spec,
            gpu_memory_fraction=budget["coder_b_memory_fraction"],
        )
    cfg.measured_hardware = hw.to_dict()
    cfg.runtime_implementation_status = "VALID"
    cfg.live_gpu_benchmark_status = "EXECUTED_LIVE_GPU" if is_live_gpu else "NOT_EXECUTED_NO_GPU"
    cfg.production_dual_model_validation = False
    cfg.derived_from_benchmark = bool(is_live_gpu)
    cfg.updated_at_utc = datetime.now(timezone.utc).isoformat()

    config_path = root / "runs" / run_id / "gpu_runtime_config.json"
    cfg.save(config_path)

    if is_live_gpu:
        bench_path = root / "runs" / run_id / "gpu_runtime_benchmark.json"
        bench_path.parent.mkdir(parents=True, exist_ok=True)
        with open(bench_path, "w", encoding="utf-8") as f:
            json.dump(benchmark_report, f, indent=2)

    return cfg, benchmark_report, config_path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="HFG Agent 07 GPU Runtime Config & 5-Stage Benchmark Runner")
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID, help="Active HFG run identifier")
    parser.add_argument("--force-cpu-write", action="store_true", help="Allow overwriting GPU preflight config from CPU")
    parser.add_argument("--skip-remote-resolve", action="store_true", help="Skip HF Hub model metadata resolution")
    parser.add_argument("--verify-tokenizer", action="store_true", help="Also verify tokenizer load during HF check")
    args = parser.parse_args()

    existing_cfg_path = Path("runs") / args.run_id / "gpu_runtime_config.json"
    hw_now = detect_hardware_profile()
    if not hw_now.gpu_available and existing_cfg_path.is_file() and not args.force_cpu_write:
        try:
            existing = json.loads(existing_cfg_path.read_text(encoding="utf-8"))
            if existing.get("measured_hardware", {}).get("gpu_available") is True:
                print(
                    f"[GUARD] Preserving verified GPU preflight config in {existing_cfg_path} "
                    f"(current host has no GPU; pass --force-cpu-write to override)."
                )
                raise SystemExit(0)
        except SystemExit:
            raise
        except Exception:
            pass

    cfg_out, _bench_out, cfg_file = build_and_save_runtime_config(
        run_id=args.run_id,
        resolve_remote_models=not args.skip_remote_resolve,
        verify_tokenizer=args.verify_tokenizer,
    )
    print(f"Saved GPU runtime config to: {cfg_file}")
    print(f"Measured Hardware: {cfg_out.measured_hardware['gpu_device_name'] if cfg_out.measured_hardware else 'unknown'}")
    print(f"Selected Execution Mode: {cfg_out.execution_mode.value}")
