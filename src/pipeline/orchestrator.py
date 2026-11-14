"""Minimal Evidence-Derived Pipeline Orchestration & Agent 03 Release Gate (Agent 11).

Owned by: Agent 11 — Orchestration & QA
Architecture Version: v1.1.0
Schema Version: 1.0.0 / v1.1.0

Enforces the current pipeline progression strictly from persisted artifacts, schemas,
and runtime evidence (never manually asserted):

    Agent 01 ingestion (INGESTION_READY)
      -> Agent 02 entrance contracts (QUALITATIVE_CONTRACT_READY)
      -> Agent 07 GPU hardware preflight (GPU_PREFLIGHT_READY) + live GPU benchmark
      -> Coder A (CODER_A_COMPLETE) & independent Coder B (CODER_B_COMPLETE)
      -> Dual-coder structural/provenance/missingness validation (DUAL_CODER_VALIDATED)
      -> Agent 03 Hard Release Gate (AGENT_03_RELEASE_READY -> READY | BLOCKED)
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple

import pandas as pd
from pydantic import BaseModel, Field

from src.contracts import (
    CanonicalAlternativeCrosswalk,
    CodingResult,
    CrosswalkStatus,
    FORBIDDEN_RECONCILIATION_METHODS,
    MissingnessState,
    PreferenceCell,
    PreferenceUncertaintySet,
    ResponseEpistemicStatus,
    UncertaintyClass,
)
from src.freshness_checker import FreshnessChecker
from src.hardcoding_scanner import HardcodingScanner, verify_gate_1
from src.ingest.ingestion import ACTIVE_RUN_ID, EXPECTED_RAW_SHA256
from src.nlp.prompts import PromptBuilder, assert_coder_input_isolation
from src.nlp.schemas import NormalizedResponseInput, ResponseStatusLabel
from src.nlp.subtopic_extraction import QuestionCorpusCoder
from src.nlp.value_extraction import ValueExtractor
from src.registry.question_registry import QuestionRegistry
from src.runtime.model_runtime import (
    CoderModelSpec,
    DualCoderRuntimeManager,
    ExecutionMode,
    ExecutionProfile,
    GPURuntimeConfig,
    validate_model_family_diversity,
)


class PipelineState(str, Enum):
    """Machine-readable orchestration states derived strictly from repository evidence."""

    INGESTION_READY = "INGESTION_READY"
    QUALITATIVE_CONTRACT_READY = "QUALITATIVE_CONTRACT_READY"
    GPU_PREFLIGHT_READY = "GPU_PREFLIGHT_READY"
    CODER_A_COMPLETE = "CODER_A_COMPLETE"
    CODER_B_COMPLETE = "CODER_B_COMPLETE"
    DUAL_CODER_VALIDATED = "DUAL_CODER_VALIDATED"
    AGENT_03_RELEASE_READY = "AGENT_03_RELEASE_READY"
    AGENT_04_RELEASE_READY = "AGENT_04_RELEASE_READY"


class Agent03ReleaseDecision(str, Enum):
    """Hard release gate verdict for downstream Agent 03 execution."""

    READY = "READY"
    BLOCKED = "BLOCKED"


class Agent04ReleaseDecision(str, Enum):
    """Hard release gate verdict for downstream Agent 04 execution (ADR-0008 enforced)."""

    READY = "READY"
    BLOCKED = "BLOCKED"


class CoderExecutionSummary(BaseModel):
    """Evidence-backed execution summary for an individual qualitative coder."""

    coder_id: Literal["coder_a", "coder_b"]
    execution_status: Literal["PASS", "FAIL", "NOT_EXECUTED", "UNVERIFIED"] = "NOT_EXECUTED"
    execution_profile: Optional[str] = None
    production_eligible: bool = False
    synthetic_or_test_execution: bool = True
    model_family: Optional[str] = None
    base_model: Optional[str] = None
    model_repo: Optional[str] = None
    model_revision: Optional[str] = None
    quantization: Optional[str] = None
    serving_engine: Optional[str] = None
    model_load_succeeded: bool = False
    gpu_resident: bool = False
    inference_occurred: bool = False
    responses_attempted: int = 0
    responses_completed: int = 0
    responses_failed: int = 0
    output_artifact_path: Optional[str] = None
    checkpoint_paths: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


class DualCoderValidationReport(BaseModel):
    """Validation result covering structural, provenance, missingness, and independence invariants."""

    status: Literal["PASS", "FAIL", "BLOCKED"] = "BLOCKED"
    checks: Dict[str, bool] = Field(default_factory=dict)
    violations: List[str] = Field(default_factory=list)


class PipelineEvaluationReport(BaseModel):
    """Complete evidence-derived orchestration & Agent 03 / Agent 04 release gate report."""

    run_id: str
    evaluated_at_utc: str
    states: Dict[str, bool]
    highest_verified_state: Optional[str] = None
    agent_01_gate_1: Literal["PASS", "FAIL"] = "FAIL"
    agent_02_entrance_gate: Literal["PASS", "FAIL"] = "FAIL"
    agent_07_persisted: bool = False
    live_gpu_hardware_preflight: Literal["PASS", "FAIL"] = "FAIL"
    live_gpu_runtime_benchmark: Literal["PASS", "FAIL", "NOT_EXECUTED", "INCOMPLETE"] = "NOT_EXECUTED"
    coder_a: CoderExecutionSummary
    coder_b: CoderExecutionSummary
    dual_coder_validation: DualCoderValidationReport
    hardcoding_scan_passed: bool = False
    freshness_checks_passed: bool = False
    agent_03_release_checklist: Dict[str, bool] = Field(default_factory=dict)
    agent_03_release_decision: Agent03ReleaseDecision = Agent03ReleaseDecision.BLOCKED
    agent_04_release_checklist: Dict[str, bool] = Field(default_factory=dict)
    agent_04_release_decision: Agent04ReleaseDecision = Agent04ReleaseDecision.BLOCKED
    agent_04_blocking_reasons: List[str] = Field(default_factory=list)
    blocking_reasons: List[str] = Field(default_factory=list)


NON_PREFERENCE_EPISTEMIC_STATUSES = {
    ResponseEpistemicStatus.RAW_BLANK.value,
    ResponseEpistemicStatus.EXPLICIT_NO_OPINION.value,
    ResponseEpistemicStatus.EXPLICIT_INSUFFICIENT_EXPERIENCE.value,
    ResponseEpistemicStatus.EXPLICIT_INSUFFICIENT_INFORMATION.value,
    ResponseEpistemicStatus.PUNCTUATION_UNINTERPRETABLE.value,
    ResponseEpistemicStatus.NO_ADDITIONAL_REMARKS.value,
}


def _check_agent_07_persisted(root: Path, run_id: str) -> bool:
    required_paths = [
        root / "src" / "runtime" / "model_runtime.py",
        root / "src" / "model_runtime.py",
        root / "notebooks" / "07_gpu_runtime.ipynb",
        root / "notebooks" / "01_gpu_coders.ipynb",
        root / "tests" / "test_runtime.py",
        root / "runs" / run_id / "gpu_runtime_config.json",
    ]
    return all(p.is_file() for p in required_paths)


def _check_gpu_preflight_and_benchmark(
    root: Path,
    run_id: str,
) -> Tuple[bool, Literal["PASS", "FAIL"], Literal["PASS", "FAIL", "NOT_EXECUTED", "INCOMPLETE"], Optional[GPURuntimeConfig], List[str]]:
    notes: List[str] = []
    cfg_path = root / "runs" / run_id / "gpu_runtime_config.json"
    if not cfg_path.is_file():
        return False, "FAIL", "NOT_EXECUTED", None, [f"Missing {cfg_path.relative_to(root)}"]

    try:
        cfg = GPURuntimeConfig.load(cfg_path)
    except Exception as exc:
        return False, "FAIL", "NOT_EXECUTED", None, [f"Invalid GPU runtime config: {exc}"]

    hw = cfg.measured_hardware or {}
    preflight_ok = (
        bool(hw.get("gpu_available") is True)
        and float(hw.get("gpu_total_vram_mb", 0.0)) > 0.0
        and cfg.live_gpu_benchmark_status != "NOT_EXECUTED_NO_GPU"
    )
    preflight_status: Literal["PASS", "FAIL"] = "PASS" if preflight_ok else "FAIL"
    if not preflight_ok:
        notes.append("No live GPU hardware preflight recorded in gpu_runtime_config.json")

    bench_path = root / "runs" / run_id / "gpu_runtime_benchmark.json"
    if not bench_path.is_file():
        return preflight_ok, preflight_status, "NOT_EXECUTED", cfg, notes

    try:
        bench = json.loads(bench_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return preflight_ok, preflight_status, "FAIL", cfg, notes + [f"Corrupt gpu_runtime_benchmark.json: {exc}"]

    bench_hw = bench.get("measured_hardware") or {}
    if bench.get("live_gpu_benchmark_status") != "EXECUTED_LIVE_GPU" or bench_hw.get("gpu_available") is not True:
        return preflight_ok, preflight_status, "INCOMPLETE", cfg, notes + ["gpu_runtime_benchmark.json lacks live GPU execution flag"]

    stages = bench.get("stages") or {}
    required_stages = [
        "1_coder_a_alone",
        "2_coder_b_alone",
        "3_both_servers_resident",
        "4_simultaneous_structured_request",
        "5_bounded_concurrent_requests",
    ]
    if any(s not in stages for s in required_stages):
        return preflight_ok, preflight_status, "INCOMPLETE", cfg, notes + ["gpu_runtime_benchmark.json missing required benchmark stages"]

    s3 = stages["3_both_servers_resident"]
    if not s3.get("both_healthy"):
        return preflight_ok, preflight_status, "FAIL", cfg, notes + ["Stage 3 both_servers_resident failed health check"]

    for s_key in ["1_coder_a_alone", "2_coder_b_alone", "4_simultaneous_structured_request", "5_bounded_concurrent_requests"]:
        if float(stages[s_key].get("schema_valid_output_rate", 0.0)) < 1.0:
            return preflight_ok, preflight_status, "FAIL", cfg, notes + [f"Benchmark stage {s_key} schema_valid_output_rate < 1.0"]

    return preflight_ok, preflight_status, "PASS", cfg, notes


def _load_coder_output_artifact(
    root: Path,
    run_id: str,
    coder_id: Literal["coder_a", "coder_b"],
) -> Tuple[Optional[Dict[str, Any]], Optional[str], List[str]]:
    """Locate persisted real coder execution artifacts if present on disk."""
    candidates = [
        root / "data" / "processed" / f"{coder_id}_outputs.json",
        root / "runs" / run_id / f"{coder_id}_outputs.json",
    ]
    for path in candidates:
        if path.is_file():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                return payload, str(path.relative_to(root)), []
            except Exception as exc:
                return None, str(path.relative_to(root)), [f"Failed to parse {path.name}: {exc}"]

    # Also check themes_codebook.json if it embeds per-coder records
    codebook_path = root / "data" / "processed" / "themes_codebook.json"
    if codebook_path.is_file():
        try:
            cb = json.loads(codebook_path.read_text(encoding="utf-8"))
            key = f"{coder_id}_outputs"
            if isinstance(cb.get(key), dict):
                return cb[key], str(codebook_path.relative_to(root)), []
        except Exception as exc:
            return None, str(codebook_path.relative_to(root)), [f"Failed to inspect themes_codebook.json: {exc}"]

    return None, None, []


def _find_coder_checkpoints(root: Path, run_id: str, cfg: Optional[GPURuntimeConfig], coder_id: str) -> List[str]:
    ckpt_rel = (cfg.checkpoint_root or cfg.checkpoint_dir) if cfg else ".checkpoints/gpu_coder_wal"
    ckpt_dir = Path(ckpt_rel).expanduser()
    if not ckpt_dir.is_absolute():
        ckpt_dir = root / ckpt_dir
    if not ckpt_dir.is_dir():
        return []
    found: List[str] = []
    candidates = sorted(
        {
            *ckpt_dir.glob(f"{run_id}_checkpoint_wal.jsonl"),
            *(ckpt_dir / run_id / "production").glob("*.jsonl"),
            *(ckpt_dir / run_id).glob("checkpoint_wal.jsonl"),
        }
    )
    for p in candidates:
        if not p.is_file():
            continue
        try:
            lines = [ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
            for ln in lines:
                rec = json.loads(ln)
                rec_prof = rec.get("execution_profile", ExecutionProfile.PRODUCTION.value)
                if (
                    rec.get("coder_id") == coder_id
                    and rec_prof == ExecutionProfile.PRODUCTION.value
                    and not str(rec.get("participant_id", "")).startswith("BENCH_")
                ):
                    try:
                        found.append(str(p.relative_to(root)))
                    except ValueError:
                        found.append(str(p))
                    break
        except Exception:
            continue
    return found


def _summarize_coder_execution(
    root: Path,
    run_id: str,
    cfg: Optional[GPURuntimeConfig],
    coder_id: Literal["coder_a", "coder_b"],
    expected_usable_primary_count: int,
    norm_df: Optional[pd.DataFrame] = None,
) -> Tuple[CoderExecutionSummary, Optional[Dict[str, Any]]]:
    payload, artifact_path, parse_notes = _load_coder_output_artifact(root, run_id, coder_id)
    ckpts = _find_coder_checkpoints(root, run_id, cfg, coder_id)

    spec = (cfg.coder_a_spec if coder_id == "coder_a" else cfg.coder_b_spec) if cfg else None
    summary = CoderExecutionSummary(
        coder_id=coder_id,
        model_family=spec.model_family if spec else None,
        base_model=spec.base_model if spec else None,
        model_repo=spec.model_repo if spec else None,
        model_revision=spec.model_revision if spec else None,
        quantization=spec.quantization if spec else None,
        serving_engine=spec.serving_engine if spec else None,
        output_artifact_path=artifact_path,
        checkpoint_paths=ckpts,
        notes=list(parse_notes),
    )

    if payload is None:
        summary.execution_status = "NOT_EXECUTED" if not ckpts else "UNVERIFIED"
        summary.notes.append(f"No persisted {coder_id} output artifact found for run {run_id}.")
        return summary, None

    meta = payload.get("execution_metadata") or {}
    top_profile = payload.get("execution_profile")
    meta_profile = meta.get("execution_profile")
    summary.execution_profile = str(meta_profile if meta_profile is not None else (top_profile or "")) or None

    top_eligible = payload.get("production_eligible") if "production_eligible" in payload else None
    meta_eligible = meta.get("production_eligible") if "production_eligible" in meta else None
    summary.production_eligible = bool(meta_eligible if meta_eligible is not None else (top_eligible is True))

    top_synth = payload.get("synthetic_or_test_execution") if "synthetic_or_test_execution" in payload else None
    meta_synth = meta.get("synthetic_or_test_execution") if "synthetic_or_test_execution" in meta else None
    resolved_synth = meta_synth if meta_synth is not None else top_synth
    summary.synthetic_or_test_execution = True if resolved_synth is None else bool(resolved_synth)

    summary.model_family = meta.get("model_family", summary.model_family)
    summary.base_model = meta.get("base_model", summary.base_model)
    summary.model_repo = meta.get("model_repo", summary.model_repo)
    summary.model_revision = meta.get("model_revision", summary.model_revision)
    summary.quantization = meta.get("quantization", summary.quantization)
    summary.serving_engine = meta.get("serving_engine", summary.serving_engine)
    summary.model_load_succeeded = bool(meta.get("model_load_succeeded", False))
    summary.gpu_resident = bool(meta.get("gpu_resident", False))
    summary.inference_occurred = bool(meta.get("inference_occurred", False))

    responses = payload.get("responses") or payload.get("coding_results") or []
    summary.responses_attempted = int(meta.get("responses_attempted", len(responses)))
    summary.responses_completed = int(meta.get("responses_completed", len(responses)))
    summary.responses_failed = int(meta.get("responses_failed", 0))

    if payload.get("run_id") != run_id:
        summary.execution_status = "FAIL"
        summary.notes.append(f"Run ID mismatch: expected {run_id}, found {payload.get('run_id')}")
        return summary, payload

    profile_consistent = (
        (top_profile is None or meta_profile is None or top_profile == meta_profile)
        and (top_eligible is None or meta_eligible is None or bool(top_eligible) == bool(meta_eligible))
        and (top_synth is None or meta_synth is None or bool(top_synth) == bool(meta_synth))
    )
    profile_eligible_ok = (
        profile_consistent
        and summary.execution_profile == ExecutionProfile.PRODUCTION.value
        and summary.production_eligible is True
        and summary.synthetic_or_test_execution is False
    )
    if not profile_eligible_ok:
        summary.notes.append(
            f"Artifact not production-eligible (execution_profile={summary.execution_profile}, "
            f"production_eligible={summary.production_eligible}, "
            f"synthetic_or_test_execution={summary.synthetic_or_test_execution})."
        )

    real_exec_ok = (
        profile_eligible_ok
        and summary.model_load_succeeded
        and summary.gpu_resident
        and summary.inference_occurred
        and summary.responses_completed > 0
        and summary.responses_failed == 0
        and meta.get("execution_mode") != ExecutionMode.CPU_FALLBACK.value
    )

    coding_records = payload.get("coding_results") or []
    observed_usable_primary_coords = {
        (str(rec.get("participant_id")), str(rec.get("question_id")))
        for rec in coding_records
        if rec.get("missingness_state") == MissingnessState.OBSERVED_USABLE.value
        and str(rec.get("question_id", "")) != "Q14"
    }
    if expected_usable_primary_count > 0:
        if summary.responses_completed < expected_usable_primary_count:
            real_exec_ok = False
            summary.notes.append(
                f"Incomplete coverage: completed {summary.responses_completed} < {expected_usable_primary_count} usable responses"
            )
        if len(observed_usable_primary_coords) < expected_usable_primary_count:
            real_exec_ok = False
            summary.notes.append(
                f"Incomplete coding_results primary coverage: {len(observed_usable_primary_coords)} < {expected_usable_primary_count} usable primary coordinates"
            )
    if norm_df is not None and not norm_df.empty:
        if "is_primary_question" in norm_df.columns:
            mask = (norm_df["missingness_state"] == MissingnessState.OBSERVED_USABLE.value) & (
                norm_df["is_primary_question"] == True
            )
        else:
            mask = (norm_df["missingness_state"] == MissingnessState.OBSERVED_USABLE.value) & (
                norm_df["question_id"] != "Q14"
            )
        expected_coords = {
            (str(r["participant_id"]), str(r["question_id"]))
            for _, r in norm_df[mask].iterrows()
        }
        missing_coords = sorted(expected_coords - observed_usable_primary_coords)
        if missing_coords:
            real_exec_ok = False
            summary.notes.append(
                f"Missing {len(missing_coords)} expected usable primary coordinate(s), e.g. {missing_coords[:3]}"
            )

    summary.execution_status = "PASS" if real_exec_ok else "UNVERIFIED"
    if not real_exec_ok and not summary.notes:
        summary.notes.append("Persisted payload did not prove live GPU model load and inference completion.")
    return summary, payload


def validate_dual_coder_outputs(
    *,
    normalized_df: pd.DataFrame,
    question_specs: Dict[str, Any],
    coder_a_payload: Optional[Dict[str, Any]],
    coder_b_payload: Optional[Dict[str, Any]],
) -> DualCoderValidationReport:
    """Validate real Coder A and Coder B outputs against Section 8 invariants A-H."""
    if coder_a_payload is None or coder_b_payload is None:
        return DualCoderValidationReport(
            status="BLOCKED",
            checks={},
            violations=["Both Coder A and Coder B persisted output artifacts are required before dual-coder validation."],
        )

    violations: List[str] = []
    valid_participants = set(normalized_df["participant_id"].astype(str))
    valid_questions = set(normalized_df["question_id"].astype(str))
    row_by_pair: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for _, row in normalized_df.iterrows():
        row_by_pair[(str(row["participant_id"]), str(row["question_id"]))] = row.to_dict()

    # Check A: Structural integrity (participants, Q01-Q13 primary vs Q14 optional, no fabricated coordinates or duplicates)
    structural_ok = True
    seen_coding_keys: set[Tuple[str, str, str, str]] = set()
    for label, payload in [("coder_a", coder_a_payload), ("coder_b", coder_b_payload)]:
        for rec in payload.get("coding_results", []):
            pid = str(rec.get("participant_id", ""))
            qid = str(rec.get("question_id", ""))
            sid = str(rec.get("subtopic_id", ""))
            if pid not in valid_participants or qid not in valid_questions:
                structural_ok = False
                violations.append(f"[A] {label}: fabricated coordinate ({pid}, {qid})")
            key = (label, pid, qid, sid)
            if key in seen_coding_keys:
                structural_ok = False
                violations.append(f"[A] {label}: duplicate coding entry for {key}")
            seen_coding_keys.add(key)
    for i in range(1, 14):
        qid = f"Q{i:02d}"
        if qid not in question_specs or not getattr(question_specs[qid], "is_primary_question", True):
            structural_ok = False
            violations.append(f"[A] {qid} missing or not marked primary")
    if "Q14" in question_specs and getattr(question_specs["Q14"], "question_scope", None) != "optional_contextual_remarks":
        structural_ok = False
        violations.append("[A] Q14 must remain optional_contextual_remarks")

    # Check B: Evidence provenance (substantive coding traces to participant, question, response, valid offsets)
    provenance_ok = True
    for label, payload in [("coder_a", coder_a_payload), ("coder_b", coder_b_payload)]:
        spans_by_id = {sp["span_id"]: sp for sp in payload.get("evidence_spans", []) if "span_id" in sp}
        for rec in payload.get("coding_results", []):
            if rec.get("missingness_state") == MissingnessState.OBSERVED_USABLE.value:
                span_ids = rec.get("evidence_span_ids") or []
                if not span_ids:
                    provenance_ok = False
                    violations.append(f"[B] {label}: usable coding {rec.get('coding_id')} lacks evidence_span_ids")
                    continue
                row = row_by_pair.get((str(rec.get("participant_id")), str(rec.get("question_id"))), {})
                src_text = str(row.get("source_text") or row.get("raw_value") or "")
                for sp_id in span_ids:
                    sp = spans_by_id.get(sp_id)
                    if not sp:
                        provenance_ok = False
                        violations.append(f"[B] {label}: unresolved evidence_span_id {sp_id}")
                        continue
                    c_start, c_end = int(sp.get("char_start", -1)), int(sp.get("char_end", -1))
                    quote = str(sp.get("verbatim_quote", ""))
                    if c_start < 0 or c_end > len(src_text) or src_text[c_start:c_end] != quote:
                        provenance_ok = False
                        violations.append(f"[B] {label}: span {sp_id} offset mismatch against source_text")

    # Check C: Missingness integrity (no synthetic preference on blanks / explicit no opinion / insufficient experience / punctuation / ambiguous)
    missingness_ok = True
    for label, payload in [("coder_a", coder_a_payload), ("coder_b", coder_b_payload)]:
        for rec in payload.get("coding_results", []):
            row = row_by_pair.get((str(rec.get("participant_id")), str(rec.get("question_id"))), {})
            ep_status = str(row.get("epistemic_status", ""))
            probs = rec.get("alternative_probabilities") or {}
            if ep_status in NON_PREFERENCE_EPISTEMIC_STATUSES and probs:
                missingness_ok = False
                violations.append(
                    f"[C] {label}: synthetic preference generated for non-preference cell ({rec.get('participant_id')}, {rec.get('question_id')}, {ep_status})"
                )
            if ep_status == ResponseEpistemicStatus.AMBIGUOUS.value and rec.get("missingness_state") == MissingnessState.OBSERVED_USABLE.value and probs:
                # Ambiguous cells must not fabricate preference without explicit semantic disambiguation trace
                if not rec.get("semantic_disambiguation_evidence"):
                    missingness_ok = False
                    violations.append(
                        f"[C] {label}: ambiguous cell ({rec.get('participant_id')}, {rec.get('question_id')}) became preference without disambiguation"
                    )

    # Check D: Bottom-up subtopic discovery (evidence-backed, not mere question prompt echo)
    subtopic_ok = True
    prompt_texts = {
        qid: {
            str(getattr(spec, "canonical_prompt_en", "")).strip().lower(),
            *[str(v).strip().lower() for v in getattr(spec, "column_headers_by_lang", {}).values()],
        }
        for qid, spec in question_specs.items()
    }
    for label, payload in [("coder_a", coder_a_payload), ("coder_b", coder_b_payload)]:
        subtopics = payload.get("discovered_subtopics", [])
        if not subtopics:
            subtopic_ok = False
            violations.append(f"[D] {label}: no discovered_subtopics present")
        for st in subtopics:
            qid = str(st.get("question_id", ""))
            st_label = str(st.get("proposed_label_en", "")).strip().lower()
            if st_label in prompt_texts.get(qid, set()):
                subtopic_ok = False
                violations.append(f"[D] {label}: subtopic '{st_label}' merely paraphrases/echoes question wording for {qid}")
            if not st.get("supporting_participant_ids") and not st.get("supporting_span_ids"):
                subtopic_ok = False
                violations.append(f"[D] {label}: subtopic {st.get('subtopic_id') or st_label} lacks respondent evidence links")

    # Check E: Open organisational values grounded in evidence spans
    values_ok = True
    for label, payload in [("coder_a", coder_a_payload), ("coder_b", coder_b_payload)]:
        for val in payload.get("value_assignments", []):
            if not val.get("evidence_span_ids"):
                values_ok = False
                violations.append(f"[E] {label}: value {val.get('value_id')} lacks evidence_span_ids")

    # Check F: Goods applicability respected (DISABLED questions must keep economic_good_class = None)
    goods_ok = True
    for label, payload in [("coder_a", coder_a_payload), ("coder_b", coder_b_payload)]:
        for rec in payload.get("coding_results", []):
            qid = str(rec.get("question_id", ""))
            spec = question_specs.get(qid)
            if spec and getattr(spec, "economic_good_classification_policy", None) == "DISABLED":
                if rec.get("economic_good_class") not in (None, "", "NOT_APPLICABLE"):
                    goods_ok = False
                    violations.append(f"[F] {label}: economic_good_class set on DISABLED question {qid}")

    # Check G: Quantity separation & simplex normalization
    quantity_ok = True
    for label, payload in [("coder_a", coder_a_payload), ("coder_b", coder_b_payload)]:
        for rec in payload.get("coding_results", []):
            if rec.get("missingness_state") == MissingnessState.OBSERVED_USABLE.value:
                probs = rec.get("alternative_probabilities") or {}
                if not probs or abs(sum(float(v) for v in probs.values()) - 1.0) > 1e-4:
                    quantity_ok = False
                    violations.append(f"[G] {label}: simplex violation on {rec.get('coding_id')}")
                for req_field in ("semantic_importance", "coder_confidence", "coder_agreement"):
                    if rec.get(req_field) is None or req_field in probs:
                        quantity_ok = False
                        violations.append(f"[G] {label}: missing or conflated orthogonal metric '{req_field}' on {rec.get('coding_id')}")

    # Check H: Coder A / Coder B model-family independence & profile consistency
    independence_ok = True
    meta_a = coder_a_payload.get("execution_metadata") or {}
    meta_b = coder_b_payload.get("execution_metadata") or {}
    prof_a = str(meta_a.get("execution_profile") or coder_a_payload.get("execution_profile") or ExecutionProfile.PRODUCTION.value)
    prof_b = str(meta_b.get("execution_profile") or coder_b_payload.get("execution_profile") or ExecutionProfile.PRODUCTION.value)
    if prof_a != prof_b:
        independence_ok = False
        violations.append(f"[H] Coder A profile '{prof_a}' != Coder B profile '{prof_b}'")
    try:
        spec_a = CoderModelSpec(
            coder_id="coder_a",
            model_family=str(meta_a.get("model_family", "")),
            model_repo=str(meta_a.get("model_repo", "")),
            model_revision=str(meta_a.get("model_revision", "main")),
            quantization=str(meta_a.get("quantization", "")),
            port=8001,
        )
        spec_b = CoderModelSpec(
            coder_id="coder_b",
            model_family=str(meta_b.get("model_family", "")),
            model_repo=str(meta_b.get("model_repo", "")),
            model_revision=str(meta_b.get("model_revision", "main")),
            quantization=str(meta_b.get("quantization", "")),
            port=8002,
        )
        validate_model_family_diversity(spec_a, spec_b, execution_profile=prof_a)
    except Exception as exc:
        independence_ok = False
        violations.append(f"[H] Independence check failed: {exc}")

    if meta_a.get("prompt_hash") and meta_a.get("prompt_hash") == meta_b.get("prompt_hash"):
        independence_ok = False
        violations.append("[H] Coder A and Coder B prompt_hash values must remain independent")

    checks = {
        "A_structural_integrity": structural_ok,
        "B_evidence_provenance": provenance_ok,
        "C_missingness_integrity": missingness_ok,
        "D_subtopic_discovery": subtopic_ok,
        "E_organisational_values": values_ok,
        "F_goods_classification": goods_ok,
        "G_quantity_separation": quantity_ok,
        "H_model_family_independence": independence_ok,
    }
    return DualCoderValidationReport(
        status="PASS" if all(checks.values()) else "FAIL",
        checks=checks,
        violations=violations,
    )


def _evaluate_agent_04_gate(
    *,
    root: Path,
    run_id: str,
    agent03_ready: bool,
    freshness_ok: bool,
    hardcoding_ok: bool,
) -> Tuple[Dict[str, bool], List[str]]:
    """Evaluate the 9 ADR-0008 release-gate conditions required before Agent 04 may execute."""
    reasons: List[str] = []

    # 1. Agent 03 Release Gate
    c1_agent03_ready = bool(agent03_ready)
    if not c1_agent03_ready:
        reasons.append("Agent 03 release gate is BLOCKED; prerequisite dual-coder outputs are not verified.")

    # 2. ADR-0008 Approved
    adr8_path = root / "docs" / "DECISIONS" / "ADR-0008-dual-coder-preference-reconciliation-and-uncertainty.md"
    c2_adr8_approved = False
    if adr8_path.is_file():
        adr8_text = adr8_path.read_text(encoding="utf-8")
        c2_adr8_approved = bool(re.search(r"\*\*Status\*\*:\s*`APPROVED`", adr8_text))
    if not c2_adr8_approved:
        reasons.append("ADR-0008 is missing or not marked Status: APPROVED.")

    # 3. Shared Contracts Aligned with ADR-0008
    c3_contracts_aligned = False
    interfaces_path = root / "schemas" / "interfaces.json"
    if interfaces_path.is_file():
        try:
            iface_data = json.loads(interfaces_path.read_text(encoding="utf-8"))
            ifaces = iface_data.get("interfaces", {})
            coding_opt = {f["name"]: f.get("type", "") for f in ifaces.get("CodingResult", {}).get("optional_fields", [])}
            reconcil_type_str = str(coding_opt.get("reconciliation_method", ""))
            json_ok = (
                "CONFIDENCE_WEIGHTED_DISTRIBUTION" not in reconcil_type_str
                and "CONFIDENCE_WEIGHTED_DISTRIBUTION" in iface_data.get("forbidden_reconciliation_methods", [])
                and "CanonicalAlternativeCrosswalk" in ifaces
                and "PreferenceUncertaintySet" in ifaces
            )
            coding_annot = str(CodingResult.__annotations__.get("reconciliation_method", ""))
            runtime_ok = (
                "CONFIDENCE_WEIGHTED_DISTRIBUTION" in FORBIDDEN_RECONCILIATION_METHODS
                and "CONFIDENCE_WEIGHTED_DISTRIBUTION" not in coding_annot
                and CanonicalAlternativeCrosswalk is not None
                and PreferenceUncertaintySet is not None
            )
            c3_contracts_aligned = json_ok and runtime_ok
        except Exception:
            c3_contracts_aligned = False
    if not c3_contracts_aligned:
        reasons.append("Shared contracts (src/contracts.py / schemas/interfaces.json) are not aligned with ADR-0008.")

    # 4. ADR-0008 Contract Tests Present
    c4_tests_present = (root / "tests" / "test_contracts_adr0008.py").is_file()
    if not c4_tests_present:
        reasons.append("Missing ADR-0008 contract verification suite tests/test_contracts_adr0008.py.")

    # 5. ISSUE-005 Synced in docs/OPEN_ISSUES.md
    open_issues_path = root / "docs" / "OPEN_ISSUES.md"
    c5_issue005_synced = False
    if open_issues_path.is_file():
        oi_text = open_issues_path.read_text(encoding="utf-8")
        c5_issue005_synced = bool(re.search(r"\|\s*`ISSUE-005`\s*\|[^\n]*\|\s*`RESOLVED`\s*\|", oi_text))
    if not c5_issue005_synced:
        reasons.append("ISSUE-005 remains OPEN in docs/OPEN_ISSUES.md (requires Agent 10 governance sync after ADR-0008 review).")

    # 6. Agent 03 Canonical Outputs Exist & QA Passes
    proc_dir = root / "data" / "processed"
    rec_dir = proc_dir / "reconciliation"
    themes_path = proc_dir / "themes_codebook.json"
    options_path = proc_dir / "candidate_options.json"
    rec_evidence_path = rec_dir / "reconciled_evidence.json"
    qa_report_path = rec_dir / "reconciliation_qa_report.json"

    c6_outputs_exist = all(p.is_file() for p in (themes_path, options_path, rec_evidence_path, qa_report_path))
    if c6_outputs_exist:
        try:
            qa_payload = json.loads(qa_report_path.read_text(encoding="utf-8"))
            c6_outputs_exist = bool(
                qa_payload.get("all_reconciliation_invariants_passed") is True
                and qa_payload.get("run_id") == run_id
            )
            if not c6_outputs_exist:
                reasons.append("Agent 03 reconciliation_qa_report.json did not pass all invariants for active run.")
        except Exception as exc:
            c6_outputs_exist = False
            reasons.append(f"Corrupt reconciliation_qa_report.json: {exc}")
    else:
        reasons.append("Canonical Agent 03 reconciliation outputs missing under data/processed/.")

    # 7. Agent 03 Crosswalks & Uncertainty Sets Conform to ADR-0008
    c7_crosswalk_and_sets_valid = False
    valid_u_classes = {u.value for u in UncertaintyClass}
    valid_cw_statuses = {c.value for c in CrosswalkStatus}
    if rec_evidence_path.is_file():
        try:
            ev_payload = json.loads(rec_evidence_path.read_text(encoding="utf-8"))
            records = ev_payload.get("preference_reconciliation_records")
            if records is None and isinstance(ev_payload.get("records"), list):
                records = ev_payload.get("records")
            if isinstance(records, list) and len(records) > 0:
                all_valid = True
                for idx, rec in enumerate(records):
                    if rec.get("reconciliation_method") in FORBIDDEN_RECONCILIATION_METHODS or rec.get("reconciliation_rule") in FORBIDDEN_RECONCILIATION_METHODS:
                        all_valid = False
                        reasons.append(f"Record {idx} uses forbidden reconciliation rule/method.")
                        break
                    u_cls = rec.get("uncertainty_class")
                    u_set = rec.get("preference_uncertainty_set")
                    cw_obj = rec.get("canonical_alternative_crosswalk") or rec.get("alternative_alignment") or {}
                    cw_status = rec.get("crosswalk_status") or (cw_obj.get("crosswalk_status") if isinstance(cw_obj, dict) else None)
                    if u_cls not in valid_u_classes or not isinstance(u_set, dict) or cw_status not in valid_cw_statuses:
                        all_valid = False
                        reasons.append(
                            f"Agent 03 reconciled_evidence.json record {idx} lacks ADR-0008 uncertainty_class / "
                            "preference_uncertainty_set / Level 2 crosswalk_status (CPU schema adaptation pending)."
                        )
                        break
                    try:
                        PreferenceUncertaintySet(**u_set)
                    except Exception as exc:
                        all_valid = False
                        reasons.append(f"Record {idx} invalid preference_uncertainty_set: {exc}")
                        break
                    if u_cls != UncertaintyClass.NONE_CONSENSUS.value and rec.get("resolved_point_distribution") is not None:
                        all_valid = False
                        reasons.append(f"Record {idx} sets resolved_point_distribution despite uncertainty_class={u_cls}.")
                        break
                c7_crosswalk_and_sets_valid = all_valid
            else:
                reasons.append("reconciled_evidence.json lacks preference_reconciliation_records.")
        except Exception as exc:
            reasons.append(f"Failed to validate reconciled_evidence.json against ADR-0008: {exc}")
    else:
        reasons.append("Agent 03 reconciled_evidence.json missing; ADR-0008 crosswalk/uncertainty-set verification cannot pass.")

    # 8. Canonical Agent 03 Artifacts Registered in Manifest
    c8_manifest_registered = False
    manifest_path = root / "runs" / run_id / "manifest.json"
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            artifacts = manifest.get("artifacts") or {}
            themes_rec = artifacts.get("themes_codebook_v1") or artifacts.get("themes_codebook")
            opts_rec = artifacts.get("candidate_options_v1") or artifacts.get("candidate_options")
            ev_rec = artifacts.get("reconciled_evidence_v1") or artifacts.get("reconciled_evidence")
            c8_manifest_registered = all(
                isinstance(rec, dict) and rec.get("validation_status") == "valid"
                for rec in (themes_rec, opts_rec, ev_rec)
            )
        except Exception:
            c8_manifest_registered = False
    if not c8_manifest_registered:
        reasons.append("Agent 03 artifacts (themes_codebook_v1, candidate_options_v1, reconciled_evidence_v1) are not registered in manifest.json.")

    # 9. Freshness & Hardcoding Scan Pass
    c9_fresh_and_clean = bool(freshness_ok and hardcoding_ok)
    if not c9_fresh_and_clean:
        reasons.append("Freshness checks or hardcoding scan failed.")

    checklist = {
        "1_agent_03_release_ready": c1_agent03_ready,
        "2_adr_0008_approved": c2_adr8_approved,
        "3_shared_contracts_adr0008_aligned": c3_contracts_aligned,
        "4_adr_0008_contract_tests_present": c4_tests_present,
        "5_open_issues_issue_005_synced": c5_issue005_synced,
        "6_agent_03_outputs_exist": c6_outputs_exist,
        "7_agent_03_crosswalk_and_uncertainty_sets_valid": c7_crosswalk_and_sets_valid,
        "8_agent_03_artifacts_registered_in_manifest": c8_manifest_registered,
        "9_freshness_and_hardcoding_pass": c9_fresh_and_clean,
    }
    return checklist, list(dict.fromkeys(reasons))


class PipelineOrchestrator:
    """Agent 11 deterministic state-machine and Agent 03 / Agent 04 release-gate evaluator."""

    def __init__(self, base_dir: Optional[Path | str] = None, run_id: str = ACTIVE_RUN_ID):
        self.base_dir = (Path(base_dir) if base_dir else Path.cwd()).resolve()
        self.run_id = run_id

    def evaluate(self, write_log: bool = False) -> PipelineEvaluationReport:
        root = self.base_dir
        blocking_reasons: List[str] = []

        # 1. Ingestion Gate (Agent 01 Gate 1)
        gate1 = verify_gate_1(base_dir=root, run_id=self.run_id)
        ingestion_ready = gate1["status"] == "PASS"
        if not ingestion_ready:
            blocking_reasons.append("Agent 01 Gate 1 did not pass (raw source, registry, or normalized answers failed).")

        # 2. Qualitative Entrance Contracts (Agent 02 Gate 2)
        agent07_persisted = _check_agent_07_persisted(root, self.run_id)
        cfg_path = root / "runs" / self.run_id / "gpu_runtime_config.json"
        if cfg_path.is_file():
            try:
                cfg_for_gate = GPURuntimeConfig.load(cfg_path)
            except Exception:
                cfg_for_gate = GPURuntimeConfig(run_id=self.run_id)
        else:
            cfg_for_gate = GPURuntimeConfig(run_id=self.run_id)

        mgr = DualCoderRuntimeManager(config=cfg_for_gate)
        gate2_ok, gate2_msg = mgr.verify_full_survey_coding_gates(root)
        contracts_importable = (
            ResponseStatusLabel is ResponseEpistemicStatus
            and QuestionCorpusCoder is not None
            and ValueExtractor is not None
            and NormalizedResponseInput is not None
            and PromptBuilder is not None
            and assert_coder_input_isolation is not None
        )
        qualitative_contract_ready = bool(ingestion_ready and gate2_ok and contracts_importable)
        if not qualitative_contract_ready:
            blocking_reasons.append(f"Agent 02 entrance contracts not ready: {gate2_msg}")

        # 3. GPU Hardware Preflight & Live 5-Stage Benchmark
        gpu_preflight_ok, preflight_status, benchmark_status, cfg_loaded, gpu_notes = _check_gpu_preflight_and_benchmark(
            root, self.run_id
        )
        if not agent07_persisted:
            blocking_reasons.append("Agent 07 implementation files missing from repository.")
        if not gpu_preflight_ok:
            blocking_reasons.extend(gpu_notes or ["Live GPU hardware preflight has not passed."])
        if benchmark_status != "PASS":
            blocking_reasons.append(
                f"Live 5-stage GPU runtime benchmark in notebooks/07_gpu_runtime.ipynb is {benchmark_status} (no persisted runs/{self.run_id}/gpu_runtime_benchmark.json)."
            )

        # 4. Coder A & Coder B Actual Execution Evidence
        norm_df = pd.DataFrame()
        usable_primary_count = 0
        answers_path = root / "data" / "normalized" / "answers_normalized.parquet"
        if answers_path.is_file():
            try:
                norm_df = pd.read_parquet(answers_path)
                if "is_primary_question" in norm_df.columns:
                    usable_primary_count = int(
                        ((norm_df["missingness_state"] == "observed_usable") & (norm_df["is_primary_question"] == True)).sum()
                    )
                else:
                    usable_primary_count = int(
                        ((norm_df["missingness_state"] == "observed_usable") & (norm_df["question_id"] != "Q14")).sum()
                    )
            except Exception:
                norm_df = pd.DataFrame()

        coder_a_summary, coder_a_payload = _summarize_coder_execution(
            root, self.run_id, cfg_loaded, "coder_a", usable_primary_count, norm_df=norm_df
        )
        coder_b_summary, coder_b_payload = _summarize_coder_execution(
            root, self.run_id, cfg_loaded, "coder_b", usable_primary_count, norm_df=norm_df
        )
        coder_a_complete = coder_a_summary.execution_status == "PASS"
        coder_b_complete = coder_b_summary.execution_status == "PASS"
        if not coder_a_complete:
            blocking_reasons.append(
                f"Coder A execution is {coder_a_summary.execution_status} (no persisted real Coder A GPU output for {self.run_id})."
            )
        if not coder_b_complete:
            blocking_reasons.append(
                f"Coder B execution is {coder_b_summary.execution_status} (no persisted real independent Coder B GPU output for {self.run_id})."
            )

        # 5. Dual-Coder Validation (Section 8 A-H)
        question_specs: Dict[str, Any] = {}
        if not norm_df.empty and (root / "data" / "raw" / "survey_raw.csv").is_file():
            reg = QuestionRegistry(raw_csv_path=root / "data" / "raw" / "survey_raw.csv")
            question_specs = reg.build_from_answers(norm_df)

        if coder_a_complete and coder_b_complete and not norm_df.empty:
            dual_val = validate_dual_coder_outputs(
                normalized_df=norm_df,
                question_specs=question_specs,
                coder_a_payload=coder_a_payload,
                coder_b_payload=coder_b_payload,
            )
        else:
            dual_val = DualCoderValidationReport(
                status="BLOCKED",
                checks={},
                violations=["Dual-coder validation blocked until both Coder A and Coder B complete live execution."],
            )
        dual_coder_validated = dual_val.status == "PASS"
        if not dual_coder_validated:
            blocking_reasons.extend(dual_val.violations)

        # 6. Hardcoding & Freshness Gates
        scanner = HardcodingScanner(base_dir=root)
        hardcoding_ok = len(scanner.scan_codebase(["src", "notebooks"])) == 0
        if not hardcoding_ok:
            blocking_reasons.append("Hardcoding scanner detected violations.")

        freshness_report = FreshnessChecker(base_dir=root, run_id=self.run_id).run_all_checks()
        freshness_ok = freshness_report.issues_found == 0
        if not freshness_ok:
            blocking_reasons.append(f"Freshness checker reported {freshness_report.issues_found} issue(s).")

        # 7. Section 15 Agent 03 Hard Release Gate (All 13 Requirements)
        checklist = {
            "1_agent_01_real_ingestion_pass": ingestion_ready,
            "2_agent_02_entrance_contracts_pass": qualitative_contract_ready,
            "3_agent_07_persisted_in_git": agent07_persisted,
            "4_live_gpu_benchmark_executed": benchmark_status == "PASS",
            "5_coder_a_executed": coder_a_complete,
            "6_coder_b_executed_independently": coder_b_complete,
            "7_real_coder_a_output_exists": coder_a_payload is not None and coder_a_complete,
            "8_real_coder_b_output_exists": coder_b_payload is not None and coder_b_complete,
            "9_dual_outputs_schema_valid": dual_val.checks.get("A_structural_integrity", False) and dual_val.checks.get("G_quantity_separation", False),
            "10_dual_outputs_provenance_valid": dual_val.checks.get("B_evidence_provenance", False),
            "11_missingness_no_synthetic_preference": dual_val.checks.get("C_missingness_integrity", False),
            "12_agent_11_orchestration_and_freshness_pass": (
                freshness_ok
                and (root / "src" / "pipeline" / "orchestrator.py").is_file()
                and (root / "notebooks" / "00_control_plane.ipynb").is_file()
                and (root / "notebooks" / "04_validation.ipynb").is_file()
            ),
            "13_hardcoding_gate_pass": hardcoding_ok,
        }
        agent03_ready = all(checklist.values())

        agent04_checklist, agent04_blocking_reasons = _evaluate_agent_04_gate(
            root=root,
            run_id=self.run_id,
            agent03_ready=agent03_ready,
            freshness_ok=freshness_ok,
            hardcoding_ok=hardcoding_ok,
        )
        agent04_ready = all(agent04_checklist.values())

        states = {
            PipelineState.INGESTION_READY.value: ingestion_ready,
            PipelineState.QUALITATIVE_CONTRACT_READY.value: qualitative_contract_ready,
            PipelineState.GPU_PREFLIGHT_READY.value: gpu_preflight_ok,
            PipelineState.CODER_A_COMPLETE.value: coder_a_complete,
            PipelineState.CODER_B_COMPLETE.value: coder_b_complete,
            PipelineState.DUAL_CODER_VALIDATED.value: dual_coder_validated,
            PipelineState.AGENT_03_RELEASE_READY.value: agent03_ready,
            PipelineState.AGENT_04_RELEASE_READY.value: agent04_ready,
        }

        highest: Optional[str] = None
        for st in (
            PipelineState.INGESTION_READY,
            PipelineState.QUALITATIVE_CONTRACT_READY,
            PipelineState.GPU_PREFLIGHT_READY,
            PipelineState.CODER_A_COMPLETE,
            PipelineState.CODER_B_COMPLETE,
            PipelineState.DUAL_CODER_VALIDATED,
            PipelineState.AGENT_03_RELEASE_READY,
            PipelineState.AGENT_04_RELEASE_READY,
        ):
            if states[st.value]:
                highest = st.value
            else:
                break

        report = PipelineEvaluationReport(
            run_id=self.run_id,
            evaluated_at_utc=datetime.now(timezone.utc).isoformat(),
            states=states,
            highest_verified_state=highest,
            agent_01_gate_1="PASS" if ingestion_ready else "FAIL",
            agent_02_entrance_gate="PASS" if qualitative_contract_ready else "FAIL",
            agent_07_persisted=agent07_persisted,
            live_gpu_hardware_preflight=preflight_status,
            live_gpu_runtime_benchmark=benchmark_status,
            coder_a=coder_a_summary,
            coder_b=coder_b_summary,
            dual_coder_validation=dual_val,
            hardcoding_scan_passed=hardcoding_ok,
            freshness_checks_passed=freshness_ok,
            agent_03_release_checklist=checklist,
            agent_03_release_decision=(
                Agent03ReleaseDecision.READY if agent03_ready else Agent03ReleaseDecision.BLOCKED
            ),
            agent_04_release_checklist=agent04_checklist,
            agent_04_release_decision=(
                Agent04ReleaseDecision.READY if agent04_ready else Agent04ReleaseDecision.BLOCKED
            ),
            agent_04_blocking_reasons=agent04_blocking_reasons,
            blocking_reasons=list(dict.fromkeys(blocking_reasons)),
        )

        if write_log:
            self.write_execution_log(report)
        return report

    def write_execution_log(self, report: PipelineEvaluationReport) -> Path:
        log_path = self.base_dir / "runs" / self.run_id / "pipeline_execution.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return log_path


def evaluate_pipeline_state(
    base_dir: Optional[Path | str] = None,
    run_id: str = ACTIVE_RUN_ID,
    write_log: bool = False,
) -> PipelineEvaluationReport:
    """Convenience entry point evaluating current repository pipeline state and Agent 03 / Agent 04 gates."""
    return PipelineOrchestrator(base_dir=base_dir, run_id=run_id).evaluate(write_log=write_log)


def main() -> None:
    parser = argparse.ArgumentParser(description="HFG Agent 11 Orchestration & Agent 03 / Agent 04 Release Gates")
    parser.add_argument("--run-id", default=ACTIVE_RUN_ID, help="Active run identifier")
    parser.add_argument("--base-dir", default=None, help="Repository root path")
    parser.add_argument("--write-log", action="store_true", help="Write runs/<run_id>/pipeline_execution.log")
    args = parser.parse_args()

    report = evaluate_pipeline_state(base_dir=args.base_dir, run_id=args.run_id, write_log=args.write_log)
    print(report.model_dump_json(indent=2))
    print(f"\nAGENT_03_RELEASE = {report.agent_03_release_decision.value}")
    print(f"AGENT_04_RELEASE = {report.agent_04_release_decision.value}")


if __name__ == "__main__":
    main()
