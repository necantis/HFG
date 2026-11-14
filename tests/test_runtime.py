"""
Comprehensive Unit, Smoke, Benchmark, Failover, and Restart Tests for Agent 07 — GPU Runtime (`src/runtime/`).

Verifies:
1. Runtime hardware detection (measured vs. simulated high-VRAM and medium-VRAM GPUs).
2. Model-family diversity invariants (Coder A DeepSeek 32B quantized; Coder B Mistral Small 3.1 24B INT4 or
   Gemma 3 27B quantized; Qwen-derived Coder B substitutes strictly blocked).
3. Configurable memory fractions (`gpu_runtime_config.json`) derived from empirical measurements with explicit
   VRAM headroom (not treating 0.44/0.44 as mandatory).
4. Separate localhost server endpoints, health polling, bounded context, bounded generation length, and
   bounded concurrency.
5. Structured-output client with probability simplex validation (`sum(p_k) = 1.0 +/- 1e-4`).
6. 5-stage runtime benchmark suite:
   - Stage 1: Coder A alone
   - Stage 2: Coder B alone
   - Stage 3: Both servers resident
   - Stage 4: One simultaneous structured request to each
   - Stage 5: Bounded concurrent requests & recovery after failed request
7. Atomic question checkpoint integrity across:
   - model crash
   - simulated Colab disconnect / truncated WAL line
   - runtime restart
   - switch from concurrent to sequential mode
8. Gate 1 & Gate 2 pre-execution guard preventing premature full-survey qualitative coding.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
from pathlib import Path
from types import SimpleNamespace
import pytest

from src.hardcoding_scanner import HardcodingScanner
from src.runtime import (
    ALTERNATIVE_CODER_B_GEMMA_SPEC,
    AtomicQuestionCheckpointStore,
    CheckpointMismatchError,
    CoderModelSpec,
    DEFAULT_CODER_A_CANDIDATES,
    DEFAULT_CODER_A_SPEC,
    DEFAULT_CODER_B_MISTRAL_CANDIDATES,
    DEFAULT_CODER_B_MISTRAL_SPEC,
    DEFAULT_SMOKE_CODER_A_SPEC,
    DEFAULT_SMOKE_CODER_B_SPEC,
    DualCoderExecutionError,
    DualCoderRuntimeManager,
    ExecutionMode,
    ExecutionProfile,
    GPURuntimeConfig,
    HardwareProfile,
    PINNED_PRODUCTION_CODER_A_REPO,
    PINNED_PRODUCTION_CODER_A_REVISION,
    PINNED_PRODUCTION_CODER_B_REPO,
    PINNED_PRODUCTION_CODER_B_REVISION,
    QuestionCheckpointRecord,
    SchemaStatus,
    build_and_save_runtime_config,
    derive_memory_budget_from_measurements,
    detect_hardware_profile,
    resolve_and_verify_coder_spec,
    resolve_dual_coder_specs,
    run_dual_coder_production,
    run_runtime_benchmark_suite,
    select_profile_dataframe,
    select_safe_execution_mode,
    strip_reasoning_tokens,
    validate_model_family_diversity,
    validate_structured_coding_response,
)
from src.runtime.model_runtime import LocalCoderServerProcess


def _find_free_port_pair() -> tuple[int, int]:
    sockets = []
    ports = []
    for _ in range(2):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 0))
        ports.append(s.getsockname()[1])
        sockets.append(s)
    for s in sockets:
        s.close()
    return ports[0], ports[1]


def _make_test_config(tmp_path: Path, mode: ExecutionMode = ExecutionMode.CONCURRENT_DUAL_SERVER) -> GPURuntimeConfig:
    port_a, port_b = _find_free_port_pair()
    spec_a = CoderModelSpec(
        coder_id="coder_a",
        model_family=DEFAULT_CODER_A_SPEC.model_family,
        base_model=DEFAULT_CODER_A_SPEC.base_model,
        model_repo=DEFAULT_CODER_A_SPEC.model_repo,
        model_revision=DEFAULT_CODER_A_SPEC.model_revision,
        quantization=DEFAULT_CODER_A_SPEC.quantization,
        serving_engine=DEFAULT_CODER_A_SPEC.serving_engine,
        remote_repo_validated=DEFAULT_CODER_A_SPEC.remote_repo_validated,
        port=port_a,
        gpu_memory_fraction=0.40,
        max_model_len=8192,
        max_output_tokens=2048,
    )
    spec_b = CoderModelSpec(
        coder_id="coder_b",
        model_family=DEFAULT_CODER_B_MISTRAL_SPEC.model_family,
        base_model=DEFAULT_CODER_B_MISTRAL_SPEC.base_model,
        model_repo=DEFAULT_CODER_B_MISTRAL_SPEC.model_repo,
        model_revision=DEFAULT_CODER_B_MISTRAL_SPEC.model_revision,
        quantization=DEFAULT_CODER_B_MISTRAL_SPEC.quantization,
        serving_engine=DEFAULT_CODER_B_MISTRAL_SPEC.serving_engine,
        remote_repo_validated=DEFAULT_CODER_B_MISTRAL_SPEC.remote_repo_validated,
        port=port_b,
        gpu_memory_fraction=0.36,
        max_model_len=8192,
        max_output_tokens=2048,
    )
    return GPURuntimeConfig(
        run_id="run_20261111_002",
        execution_mode=mode,
        gpu_memory_fraction=0.76,
        coder_a_memory_fraction=0.40,
        coder_b_memory_fraction=0.36,
        reserved_vram_headroom_mb=6144.0,
        reserved_vram_headroom_fraction=0.12,
        coder_a_port=port_a,
        coder_b_port=port_b,
        coder_a_spec=spec_a,
        coder_b_spec=spec_b,
        checkpoint_dir=str(tmp_path / "checkpoints"),
    )


def test_hardware_detection_records_actual_runtime_environment():
    hw = detect_hardware_profile()
    assert hw.cpu_logical_cores >= 1
    assert hw.system_ram_total_mb > 0.0
    assert isinstance(hw.gpu_available, bool)
    if not hw.gpu_available:
        assert hw.gpu_total_vram_mb == 0.0
        assert "NONE" in hw.gpu_device_name


def test_model_family_diversity_enforced():
    # Valid: DeepSeek 32B + Mistral Small 3.1 24B INT4
    validate_model_family_diversity(DEFAULT_CODER_A_SPEC, DEFAULT_CODER_B_MISTRAL_SPEC)
    # Valid: DeepSeek 32B + Gemma 3 27B quantized
    validate_model_family_diversity(DEFAULT_CODER_A_SPEC, ALTERNATIVE_CODER_B_GEMMA_SPEC)

    # Invalid: Substituting a Qwen-derived model for Coder B must be blocked
    qwen_coder_b = CoderModelSpec(
        coder_id="coder_b",
        model_family="qwen2.5",
        model_repo="Qwen/Qwen2.5-32B-Instruct-AWQ",
        model_revision="main",
        quantization="AWQ-INT4",
        port=8002,
    )
    with pytest.raises(ValueError, match="Model-family diversity violation"):
        validate_model_family_diversity(DEFAULT_CODER_A_SPEC, qwen_coder_b)

    # Invalid: Disguised Qwen repo under allowed family label must also be blocked
    disguised_qwen_b = CoderModelSpec(
        coder_id="coder_b",
        model_family="mistral",
        model_repo="Qwen/Qwen2.5-14B-Instruct-GPTQ-Int4",
        model_revision="main",
        quantization="GPTQ-INT4",
        port=8002,
    )
    with pytest.raises(ValueError, match="Model-family diversity violation"):
        validate_model_family_diversity(DEFAULT_CODER_A_SPEC, disguised_qwen_b)


def test_derive_memory_budget_from_measurements_across_vram_tiers():
    # Tier 1: High-VRAM GPU (e.g., 96 GB Blackwell) -> CONCURRENT_DUAL_SERVER with non-0.44 derived fractions
    hw_96gb = HardwareProfile(
        measured_at_utc="2026-11-12T00:00:00Z",
        hostname="gpu-node",
        os_platform="Linux",
        cpu_model="Xeon",
        cpu_logical_cores=16,
        system_ram_total_mb=65536.0,
        system_ram_available_mb=60000.0,
        gpu_available=True,
        gpu_count=1,
        gpu_device_name="NVIDIA RTX PRO 6000 Blackwell Server Edition",
        gpu_total_vram_mb=98304.0,
        gpu_free_vram_mb=96000.0,
        gpu_used_vram_mb=2304.0,
    )
    budget_96 = derive_memory_budget_from_measurements(
        hardware=hw_96gb,
        coder_a_measured_vram_mb=18500.0,
        coder_b_measured_vram_mb=14500.0,
        coder_a_kv_cache_mb=8192.0,
        coder_b_kv_cache_mb=8192.0,
    )
    assert budget_96["execution_mode"] == ExecutionMode.CONCURRENT_DUAL_SERVER.value
    assert budget_96["concurrent_feasible"] is True
    assert budget_96["coder_a_memory_fraction"] != 0.44
    assert budget_96["coder_b_memory_fraction"] != 0.44
    assert budget_96["reserved_vram_headroom_mb"] >= 6144.0

    # Tier 2: Single-GPU Medium VRAM (e.g., 40 GB A100) -> SEQUENTIAL_FALLBACK
    hw_40gb = HardwareProfile(
        measured_at_utc="2026-11-12T00:00:00Z",
        hostname="colab-a100",
        os_platform="Linux",
        cpu_model="Xeon",
        cpu_logical_cores=12,
        system_ram_total_mb=81920.0,
        system_ram_available_mb=75000.0,
        gpu_available=True,
        gpu_count=1,
        gpu_device_name="NVIDIA A100-SXM4-40GB",
        gpu_total_vram_mb=40960.0,
        gpu_free_vram_mb=40500.0,
        gpu_used_vram_mb=460.0,
    )
    budget_40 = derive_memory_budget_from_measurements(
        hardware=hw_40gb,
        coder_a_measured_vram_mb=18500.0,
        coder_b_measured_vram_mb=14500.0,
        coder_a_kv_cache_mb=6144.0,
        coder_b_kv_cache_mb=6144.0,
    )
    assert budget_40["execution_mode"] == ExecutionMode.SEQUENTIAL_FALLBACK.value
    assert budget_40["concurrent_feasible"] is False
    assert budget_40["single_gpu_feasible"] is True

    # Tier 3: CPU-only host -> CPU_FALLBACK
    hw_cpu = HardwareProfile(
        measured_at_utc="2026-11-12T00:00:00Z",
        hostname="cpu-host",
        os_platform="Linux",
        cpu_model="Xeon",
        cpu_logical_cores=2,
        system_ram_total_mb=8192.0,
        system_ram_available_mb=7000.0,
        gpu_available=False,
        gpu_count=0,
        gpu_device_name="NONE (CPU-Only Host)",
        gpu_total_vram_mb=0.0,
        gpu_free_vram_mb=0.0,
        gpu_used_vram_mb=0.0,
    )
    budget_cpu = derive_memory_budget_from_measurements(
        hardware=hw_cpu,
        coder_a_measured_vram_mb=18500.0,
        coder_b_measured_vram_mb=14500.0,
    )
    assert budget_cpu["execution_mode"] == ExecutionMode.CPU_FALLBACK.value
    assert budget_cpu["concurrent_feasible"] is False


def test_configurable_gpu_runtime_config_save_and_load(tmp_path):
    cfg = _make_test_config(tmp_path)
    cfg_path = tmp_path / "gpu_runtime_config.json"
    cfg.save(cfg_path)

    loaded = GPURuntimeConfig.load(cfg_path)
    assert loaded.run_id == "run_20261111_002"
    assert loaded.coder_a_memory_fraction == 0.40
    assert loaded.coder_b_memory_fraction == 0.36
    assert loaded.runtime_implementation_status == "VALID"
    assert loaded.live_gpu_benchmark_status == "NOT_EXECUTED_NO_GPU"
    assert loaded.production_dual_model_validation is False
    assert loaded.coder_a_spec.model_family == "deepseek"
    assert loaded.coder_a_spec.base_model == "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B"
    assert loaded.coder_a_spec.serving_engine == "vllm_openai_server"
    assert loaded.coder_a_spec.remote_repo_validated is False
    assert loaded.coder_b_spec.model_family == "mistral"
    assert loaded.coder_b_spec.base_model == "mistralai/Mistral-Small-3.1-24B-Instruct-2503"
    assert loaded.coder_b_spec.serving_engine == "vllm_openai_server"
    assert loaded.coder_b_spec.remote_repo_validated is False

    # Verify excessive memory fraction without headroom is rejected
    cfg.coder_a_memory_fraction = 0.55
    cfg.coder_b_memory_fraction = 0.40
    cfg.reserved_vram_headroom_fraction = 0.12
    with pytest.raises(ValueError, match="exceed available budget"):
        cfg.validate_config()


def test_5_stage_runtime_benchmark_suite(tmp_path):
    cfg = _make_test_config(tmp_path)
    report = run_runtime_benchmark_suite(config=cfg, bounded_concurrency_requests=4)

    assert "stages" in report
    stages = report["stages"]
    assert "1_coder_a_alone" in stages
    assert "2_coder_b_alone" in stages
    assert "3_both_servers_resident" in stages
    assert "4_simultaneous_structured_request" in stages
    assert "5_bounded_concurrent_requests" in stages

    assert stages["1_coder_a_alone"]["schema_valid_output_rate"] == 1.0
    assert stages["2_coder_b_alone"]["schema_valid_output_rate"] == 1.0
    assert stages["3_both_servers_resident"]["both_healthy"] is True
    assert stages["4_simultaneous_structured_request"]["schema_valid_output_rate"] == 1.0
    assert stages["5_bounded_concurrent_requests"]["schema_valid_output_rate"] == 1.0
    assert stages["5_bounded_concurrent_requests"]["recovery_after_failed_request_passed"] is True
    assert stages["5_bounded_concurrent_requests"]["model_failure_isolation_verified"] is True


def test_bounded_context_and_generation_length_enforced(tmp_path):
    cfg = _make_test_config(tmp_path)
    cfg.max_context_length = 256
    cfg.max_generation_length = 64
    mgr = DualCoderRuntimeManager(config=cfg)
    try:
        mgr.server_a.start()
        huge_prompt = "X" * 2000  # ~500 tokens > 256 max_context_length
        res = mgr.execute_structured_request(
            coder_id="coder_a",
            question_id="Q01",
            participant_id="P_OVERFLOW",
            prompt_text=huge_prompt,
            source_text="Short quote.",
        )
        assert res.schema_status == SchemaStatus.REQUEST_FAILED
        assert "exceed bounded context limit" in (res.error_message or "")
    finally:
        mgr.shutdown()


def test_checkpoint_integrity_and_survival_across_crash_disconnect_restart_and_mode_switch(tmp_path):
    """
    Verify that completed valid question checkpoints record all 14 required fields and survive:
    1. Model crash
    2. Colab disconnect (simulated via truncated trailing WAL line and fresh process instantiation)
    3. Runtime restart
    4. Switch from concurrent to sequential mode
    """
    cfg = _make_test_config(tmp_path, mode=ExecutionMode.CONCURRENT_DUAL_SERVER)
    mgr = DualCoderRuntimeManager(config=cfg)

    try:
        # 1. Code Q01 in CONCURRENT_DUAL_SERVER mode
        q01_res = mgr.code_question_dual(
            question_id="Q01",
            participant_id="PARTICIPANT_001",
            prompt_text="Extract subtopics for Q01.",
            source_text="Les poles sont pertinents pour structurer la recherche.",
        )
        assert q01_res["coder_a"].schema_status == SchemaStatus.VALID
        assert q01_res["coder_b"].schema_status == SchemaStatus.VALID
        assert q01_res["coder_a"].from_checkpoint is False

        # Verify all required fields in persisted QuestionCheckpointRecord
        records = mgr.checkpoint_store.all_records()
        assert len(records) == 2
        for rec in records:
            rec.validate_record()
            d = rec.to_dict()
            for required_field in [
                "run_id",
                "question_id",
                "coder_id",
                "prompt_hash",
                "source_hash",
                "model_repo",
                "model_revision",
                "quantization",
                "generation_config",
                "raw_response",
                "parsed_response",
                "schema_status",
                "runtime_sec",
                "peak_vram_mb",
            ]:
                assert required_field in d

        # 2. Simulate model crash on Coder B + Colab disconnect (corrupt trailing bytes in WAL)
        mgr.server_b.simulated_crash = True
        mgr.shutdown()
        with open(mgr.checkpoint_store.wal_path, "ab") as wal_f:
            wal_f.write(b'{"truncated_disconnect_line": true')

        # 3. Simulate runtime restart with a brand-new manager & store instance
        restarted_store = AtomicQuestionCheckpointStore(
            checkpoint_dir=cfg.checkpoint_dir,
            run_id=cfg.run_id,
        )
        assert len(restarted_store.all_records()) == 2
        assert restarted_store.list_completed_questions() == ["Q01"]

        # 4. Switch mode from CONCURRENT_DUAL_SERVER to SEQUENTIAL_FALLBACK and re-request Q01 + new Q02
        cfg_seq = _make_test_config(tmp_path, mode=ExecutionMode.SEQUENTIAL_FALLBACK)
        mgr_restarted = DualCoderRuntimeManager(config=cfg_seq, checkpoint_store=restarted_store)

        # Q01 must be served immediately from checkpoint without re-running inference!
        q01_cached = mgr_restarted.code_question_dual(
            question_id="Q01",
            participant_id="PARTICIPANT_001",
            prompt_text="Extract subtopics for Q01.",
            source_text="Les poles sont pertinents pour structurer la recherche.",
        )
        assert q01_cached["coder_a"].from_checkpoint is True
        assert q01_cached["coder_b"].from_checkpoint is True

        # Q02 executes cleanly in sequential mode and adds 2 new checkpoints
        q02_res = mgr_restarted.code_question_dual(
            question_id="Q02",
            participant_id="PARTICIPANT_001",
            prompt_text="Extract subtopics for Q02.",
            source_text="Les personnes identifiees couvrent bien les domaines.",
        )
        assert q02_res["coder_a"].schema_status == SchemaStatus.VALID
        assert q02_res["coder_b"].schema_status == SchemaStatus.VALID
        assert q02_res["coder_a"].from_checkpoint is False
        assert restarted_store.list_completed_questions() == ["Q01", "Q02"]
    finally:
        mgr.shutdown()


def test_automatic_sequential_fallback_on_concurrent_instability(tmp_path):
    cfg = _make_test_config(tmp_path, mode=ExecutionMode.CONCURRENT_DUAL_SERVER)
    cfg.max_retries_per_request = 0
    mgr = DualCoderRuntimeManager(config=cfg)
    try:
        # Pre-populate Q01 checkpoint
        res_q01 = mgr.code_question_dual(
            question_id="Q01",
            participant_id="P01",
            prompt_text="Prompt Q01",
            source_text="Quote Q01",
        )
        assert res_q01["coder_a"].schema_status == SchemaStatus.VALID

        # Inject a failure on Coder B during concurrent execution of Q02 -> triggers automatic sequential fallback
        mgr.server_b.inject_transient_failures(count=1)
        res_q02 = mgr.code_question_dual(
            question_id="Q02",
            participant_id="P01",
            prompt_text="Prompt Q02",
            source_text="Quote Q02",
        )
        assert mgr.config.execution_mode == ExecutionMode.SEQUENTIAL_FALLBACK
        assert len(mgr.fallback_events) == 1
        assert res_q02["coder_a"].schema_status == SchemaStatus.VALID
        assert res_q02["coder_b"].schema_status == SchemaStatus.VALID
        # Verify Q01 checkpoint was NOT invalidated by fallback
        assert mgr.checkpoint_store.list_completed_questions() == ["Q01", "Q02"]
    finally:
        mgr.shutdown()


def test_full_survey_coding_gate_protection(tmp_path):
    cfg = _make_test_config(tmp_path)
    mgr = DualCoderRuntimeManager(config=cfg)

    # Neither Gate 1 nor Gate 2 exists in tmp_path
    ok, msg = mgr.verify_full_survey_coding_gates(tmp_path)
    assert ok is False
    assert "BLOCKED_BY_GATE_1" in msg

    # Create Gate 1 artifact only
    norm_file = tmp_path / "data" / "normalized" / "answers_normalized.parquet"
    norm_file.parent.mkdir(parents=True, exist_ok=True)
    norm_file.write_text("dummy_parquet", encoding="utf-8")

    ok2, msg2 = mgr.verify_full_survey_coding_gates(tmp_path)
    assert ok2 is False
    assert "BLOCKED_BY_GATE_2" in msg2

    # Create Gate 2 module
    nlp_file = tmp_path / "src" / "nlp" / "subtopic_extraction.py"
    nlp_file.parent.mkdir(parents=True, exist_ok=True)
    nlp_file.write_text("# Agent 02 module", encoding="utf-8")

    ok3, msg3 = mgr.verify_full_survey_coding_gates(tmp_path)
    assert ok3 is True
    assert msg3 == "AUTHORIZED"


def test_strip_reasoning_tokens_removes_think_blocks_and_fences():
    from src.nlp.repair import repair_json_string_with_audit

    raw = (
        "<think>First let me reason about {\"decoy\": 123} carefully.\n"
        "Multiple lines of thought.</think>\n"
        "```json\n"
        "{\"question_id\": \"Q01\", \"ok\": true}\n"
        "```"
    )
    cleaned = strip_reasoning_tokens(raw)
    assert "<think>" not in cleaned
    assert "decoy" not in cleaned
    parsed, _audit = repair_json_string_with_audit(cleaned)
    assert parsed == {"question_id": "Q01", "ok": True}


def test_resolve_and_verify_coder_spec_and_family_diversity():
    class _FakeHfApi:
        def __init__(self, fail_repos: set[str]):
            self.fail_repos = fail_repos

        def model_info(self, repo_id: str):
            if repo_id in self.fail_repos:
                raise RuntimeError(f"404 Not Found: {repo_id}")
            return SimpleNamespace(sha="deadbeef" * 5, gated=False)

    # Fallback to second candidate when first is unavailable, pinning resolved commit SHA
    fake_api = _FakeHfApi(fail_repos={DEFAULT_CODER_A_SPEC.model_repo, DEFAULT_CODER_B_MISTRAL_SPEC.model_repo})
    resolved_a, audit_a = resolve_and_verify_coder_spec(
        DEFAULT_CODER_A_SPEC,
        DEFAULT_CODER_A_CANDIDATES,
        verify_remote=True,
        api_client=fake_api,
    )
    assert resolved_a.remote_repo_validated is True
    assert resolved_a.model_repo == DEFAULT_CODER_A_CANDIDATES[1].model_repo
    assert resolved_a.model_revision == "deadbeef" * 5
    assert audit_a[0]["status"] == "UNAVAILABLE"
    assert audit_a[1]["status"] == "VERIFIED"

    # Qwen candidate injected into Coder B pool must be rejected before probing HF
    qwen_intruder = CoderModelSpec(
        coder_id="coder_b",
        model_family="mistral",
        base_model="Qwen/Qwen2.5-32B",
        model_repo="Qwen/Qwen2.5-32B-Instruct-AWQ",
        model_revision="main",
        quantization="AWQ-INT4",
        port=8002,
    )
    resolved_b, audit_b = resolve_and_verify_coder_spec(
        qwen_intruder,
        DEFAULT_CODER_B_MISTRAL_CANDIDATES,
        verify_remote=True,
        api_client=fake_api,
    )
    assert audit_b[0]["status"] == "REJECTED_DIVERSITY"
    assert "qwen" not in resolved_b.model_repo.lower()
    assert resolved_b.remote_repo_validated is True

    # Offline resolve_dual_coder_specs preserves remote_repo_validated=False honestly
    cfg_offline = GPURuntimeConfig(run_id="run_20261111_002")
    resolve_dual_coder_specs(cfg_offline, verify_remote=False)
    assert cfg_offline.coder_a_spec.remote_repo_validated is False
    assert cfg_offline.coder_b_spec.remote_repo_validated is False


def test_real_gpu_guard_never_falls_back_to_mock_server(tmp_path):
    hw_gpu = HardwareProfile(
        measured_at_utc="2026-11-12T00:00:00Z",
        hostname="colab-blackwell",
        os_platform="Linux",
        cpu_model="Xeon",
        cpu_logical_cores=16,
        system_ram_total_mb=131072.0,
        system_ram_available_mb=120000.0,
        gpu_available=True,
        gpu_count=1,
        gpu_device_name="NVIDIA RTX PRO 6000 Blackwell Server Edition",
        gpu_total_vram_mb=97887.0,
        gpu_free_vram_mb=97251.0,
        gpu_used_vram_mb=636.0,
    )
    cfg = _make_test_config(tmp_path, mode=ExecutionMode.CONCURRENT_DUAL_SERVER)
    mgr = DualCoderRuntimeManager(config=cfg, hardware=hw_gpu, use_mock_server=None)
    assert mgr.server_a.use_mock_server is False
    assert mgr.server_b.use_mock_server is False
    assert mgr.server_a.server_backend == "vllm_openai_server"
    assert mgr.server_b.server_backend == "vllm_openai_server"


def _prepare_isolated_hfg_workspace(tmp_path: Path) -> Path:
    """Create an isolated HFG workspace in tmp_path reusing tracked code/docs and raw/normalized survey data."""
    repo_root = Path(__file__).resolve().parent.parent
    for d in ("src", "notebooks", "docs", "tests", "schemas"):
        if (repo_root / d).exists():
            os.symlink(repo_root / d, tmp_path / d)
    for f in ("AGENTS.md", "pyproject.toml", "README.md"):
        if (repo_root / f).exists():
            os.symlink(repo_root / f, tmp_path / f)

    shutil.copytree(repo_root / "data" / "raw", tmp_path / "data" / "raw")
    norm_src = repo_root / "data" / "normalized"
    if (norm_src / "answers_normalized.parquet").is_file():
        shutil.copytree(norm_src, tmp_path / "data" / "normalized")
    else:
        from src.ingest.ingestion import IngestionPipeline

        IngestionPipeline(
            raw_csv_path=tmp_path / "data" / "raw" / "survey_raw.csv",
            output_dir=tmp_path / "data" / "normalized",
            run_id="run_20261111_002",
        ).run()

    run_dir = tmp_path / "runs" / "run_20261111_002"
    run_dir.mkdir(parents=True, exist_ok=True)
    for meta in ("manifest.json", "RUN_CARD.md"):
        src_meta = repo_root / "runs" / "run_20261111_002" / meta
        if src_meta.is_file():
            shutil.copy2(src_meta, run_dir / meta)
    return tmp_path


def test_end_to_end_dual_coder_runner_wal_fallback_and_orchestrator(tmp_path, monkeypatch):
    import pandas as pd
    from src.pipeline.orchestrator import Agent03ReleaseDecision, PipelineOrchestrator, validate_dual_coder_outputs
    from src.registry.question_registry import QuestionRegistry

    ws = _prepare_isolated_hfg_workspace(tmp_path)
    cfg = _make_test_config(ws, mode=ExecutionMode.CONCURRENT_DUAL_SERVER)
    cfg.checkpoint_dir = ".checkpoints/gpu_coder_wal"

    # Part A: Mock production pass -> must satisfy all Checks A-H, flat WAL, and honest BLOCKED gate
    res_mock = run_dual_coder_production(
        base_dir=ws,
        run_id="run_20261111_002",
        require_live_gpu=False,
        allow_mock_for_test=True,
        config=cfg,
    )
    assert res_mock["status"] == "PASS"
    assert res_mock["coder_a_metadata"]["responses_completed"] >= 128
    assert res_mock["coder_b_metadata"]["responses_completed"] >= 128
    assert res_mock["coder_a_metadata"]["prompt_hash"] != res_mock["coder_b_metadata"]["prompt_hash"]
    assert res_mock["coder_a_metadata"]["source_evidence_hash"] == res_mock["coder_b_metadata"]["source_evidence_hash"]
    assert res_mock["coder_a_metadata"]["gpu_resident"] is False  # Truthful on CPU/mock!
    assert Path(res_mock["checkpoint_wal_path"]).is_file()

    norm_df = pd.read_parquet(ws / "data" / "normalized" / "answers_normalized.parquet")
    q_specs = QuestionRegistry(raw_csv_path=ws / "data" / "raw" / "survey_raw.csv").build_from_answers(norm_df)
    payload_a = json.loads(Path(res_mock["coder_a_output_path"]).read_text(encoding="utf-8"))
    payload_b = json.loads(Path(res_mock["coder_b_output_path"]).read_text(encoding="utf-8"))
    val = validate_dual_coder_outputs(
        normalized_df=norm_df,
        question_specs=q_specs,
        coder_a_payload=payload_a,
        coder_b_payload=payload_b,
    )
    assert val.status == "PASS"
    assert all(val.checks.values())

    # Honest orchestrator check: mock CPU execution must keep AGENT_03_RELEASE = BLOCKED
    cfg.save(ws / "runs" / "run_20261111_002" / "gpu_runtime_config.json")
    orch_mock = PipelineOrchestrator(base_dir=ws, run_id="run_20261111_002").evaluate()
    assert orch_mock.agent_03_release_decision == Agent03ReleaseDecision.BLOCKED

    # Part B: Re-run using same WAL must serve all LLM completions from checkpoints cleanly
    res_resumed = run_dual_coder_production(
        base_dir=ws,
        run_id="run_20261111_002",
        require_live_gpu=False,
        allow_mock_for_test=True,
        config=cfg,
    )
    assert res_resumed["coder_a_metadata"]["checkpoint_hits"] > 0
    assert res_resumed["coder_b_metadata"]["checkpoint_hits"] > 0

    # Part C: Simulated live Blackwell 96GB GPU path (exercises replace() on frozen specs,
    # gpu_runtime_benchmark.json creation, require_live_gpu=True, and READY gate in isolated workspace)
    shutil.rmtree(ws / ".checkpoints", ignore_errors=True)
    hw_96gb = HardwareProfile(
        measured_at_utc="2026-11-12T00:00:00Z",
        hostname="colab-blackwell",
        os_platform="Linux",
        cpu_model="Xeon",
        cpu_logical_cores=16,
        system_ram_total_mb=131072.0,
        system_ram_available_mb=120000.0,
        gpu_available=True,
        gpu_count=1,
        gpu_device_name="NVIDIA RTX PRO 6000 Blackwell Server Edition",
        gpu_total_vram_mb=97887.0,
        gpu_free_vram_mb=97251.0,
        gpu_used_vram_mb=636.0,
    )

    class _MockHfOk:
        def model_info(self, repo_id: str):
            return SimpleNamespace(sha="cafebabe" * 5, gated=False)

    orig_start = LocalCoderServerProcess.start
    orig_exec_core = DualCoderRuntimeManager._execute_chat_completion_core

    def _simulated_real_gpu_start(self):
        self.use_mock_server = True
        try:
            return orig_start(self)
        finally:
            self.use_mock_server = False

    def _exec_core_with_mock_meta(self, *args, **kwargs):
        if kwargs.get("hfg_metadata") and not kwargs.get("extra_payload"):
            kwargs["extra_payload"] = {"hfg_metadata": kwargs["hfg_metadata"]}
        return orig_exec_core(self, *args, **kwargs)

    monkeypatch.setattr(LocalCoderServerProcess, "_start_real_gpu_server", _simulated_real_gpu_start)
    monkeypatch.setattr(DualCoderRuntimeManager, "_execute_chat_completion_core", _exec_core_with_mock_meta)
    live_cfg, live_bench, live_cfg_path = build_and_save_runtime_config(
        base_dir=ws,
        run_id="run_20261111_002",
        resolve_remote_models=True,
        use_mock_server=None,
        bounded_concurrency_requests=4,
        hardware=hw_96gb,
        api_client=_MockHfOk(),
    )
    assert live_cfg.live_gpu_benchmark_status == "EXECUTED_LIVE_GPU"
    assert live_cfg.execution_mode == ExecutionMode.CONCURRENT_DUAL_SERVER
    assert live_cfg.coder_a_spec.remote_repo_validated is True
    assert live_cfg.coder_b_spec.remote_repo_validated is True
    assert (ws / "runs" / "run_20261111_002" / "gpu_runtime_benchmark.json").is_file()
    assert live_bench["stages"]["5_bounded_concurrent_requests"]["model_failure_isolation_verified"] is True

    # Also simulate one concurrent fault during Coder B startup/pass in require_live_gpu=True mode
    crash_once = {"done": False}

    def _flaky_coder_b_start(self):
        if self.spec.coder_id == "coder_b" and not crash_once["done"]:
            crash_once["done"] = True
            self.inject_transient_failures(count=1)
        return orig_start(self)

    monkeypatch.setattr(LocalCoderServerProcess, "start", _flaky_coder_b_start)
    # Force fallback test on 1 request retry=0 so concurrent triggers fallback -> sequential completes!
    live_cfg.max_retries_per_request = 0
    live_cfg.save(live_cfg_path)

    res_live = run_dual_coder_production(
        base_dir=ws,
        run_id="run_20261111_002",
        require_live_gpu=True,
        hardware=hw_96gb,
        resolve_remote_models=False,
    )
    assert res_live["status"] == "PASS"
    assert res_live["coder_a_metadata"]["gpu_resident"] is True
    assert res_live["coder_b_metadata"]["gpu_resident"] is True
    assert res_live["execution_mode_final"] == ExecutionMode.SEQUENTIAL_FALLBACK.value
    assert len(res_live["fallback_events"]) >= 1

    orch_live = PipelineOrchestrator(base_dir=ws, run_id="run_20261111_002").evaluate()
    assert orch_live.agent_03_release_decision == Agent03ReleaseDecision.READY, orch_live.blocking_reasons


def test_generated_notebooks_valid_and_no_root_duplicates():
    repo_root = Path(__file__).resolve().parent.parent
    # Zero root .ipynb duplicates
    assert list(repo_root.glob("*.ipynb")) == []

    nb07_path = repo_root / "notebooks" / "07_gpu_runtime.ipynb"
    nb01_path = repo_root / "notebooks" / "01_gpu_coders.ipynb"
    assert nb07_path.is_file()
    assert nb01_path.is_file()

    nb07 = json.loads(nb07_path.read_text(encoding="utf-8"))
    nb01 = json.loads(nb01_path.read_text(encoding="utf-8"))
    assert nb07["nbformat"] == 4 and len(nb07["cells"]) >= 4
    assert nb01["nbformat"] == 4 and len(nb01["cells"]) >= 4

    nb07_src = "\n".join("".join(c["source"]) for c in nb07["cells"])
    nb01_src = "\n".join("".join(c["source"]) for c in nb01["cells"])
    assert "resolve_dual_coder_specs" in nb07_src
    assert "build_and_save_runtime_config" in nb07_src
    assert "run_dual_coder_production" in nb01_src
    assert "PipelineOrchestrator" in nb01_src
    assert "HFG_EXECUTION_PROFILE" in nb01_src
    assert "ExecutionProfile.PRODUCTION.value" in nb01_src
    assert "HFG_CHECKPOINT_ROOT" in nb01_src
    assert "execution_profile=EXECUTION_PROFILE" in nb01_src
    assert "checkpoint_root=CHECKPOINT_ROOT" in nb01_src

    scanner = HardcodingScanner(base_dir=repo_root)
    assert scanner.scan_file(nb07_path) == []
    assert scanner.scan_file(nb01_path) == []


def test_json_recovery_ladder_repair_and_semantic_drift_rejection(tmp_path, monkeypatch):
    """Verify bounded recovery ladder: Expecting ',' delimiter -> validation-aware retry -> compact retry -> model-based syntax repair & semantic drift rejection."""
    import io
    import urllib.request

    cfg = _make_test_config(tmp_path, mode=ExecutionMode.SEQUENTIAL_FALLBACK)
    mgr = DualCoderRuntimeManager(config=cfg, use_mock_server=True)
    mgr.server_b.start()
    try:
        valid_obj = {
            "question_id": "Q06",
            "participant_id": "PARTICIPANT_002",
            "coder_id": "coder_b",
            "missingness_state": "observed_usable",
            "coded_spans": [
                {
                    "subtopic_label_en": "pole_collaboration",
                    "verbatim_quote": "Les poles doivent collaborer.",
                    "char_start": 0,
                    "char_end": 28,
                    "alternative_probabilities": {"pole_level": 0.75, "prof_level": 0.25},
                    "semantic_importance": 0.85,
                    "coder_confidence": 0.9,
                }
            ],
            "rationale_summary": "Supports voluntary pole collaboration.",
        }
        malformed_missing_comma = json.dumps(valid_obj, indent=2).replace(
            '"semantic_importance": 0.85,',
            '"semantic_importance": 0.85',
        )

        # Case 1: Attempts 1-3 emit missing comma; Attempt 4 (model-based syntax repair) emits valid repaired JSON
        observed_requests = []

        class _FakeHTTPResp:
            def __init__(self, body: dict):
                self._bytes = json.dumps(body).encode("utf-8")

            def read(self):
                return self._bytes

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        def _fake_urlopen_repair_ok(req, timeout=None):
            pl = json.loads(req.data.decode("utf-8"))
            observed_requests.append(pl)
            is_repair = bool((pl.get("hfg_metadata") or {}).get("repair_mode"))
            content = json.dumps(valid_obj) if is_repair else malformed_missing_comma
            return _FakeHTTPResp(
                {
                    "choices": [{"index": 0, "message": {"content": content}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 120, "completion_tokens": 85},
                }
            )

        monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen_repair_ok)
        res = mgr.execute_json_chat_completion(
            coder_id="coder_b",
            question_id="Q06",
            participant_id="PARTICIPANT_002",
            system_prompt="System prompt",
            user_prompt="Full prompt for Q06",
            compact_user_prompt="COMPACT_PROMPT_MARKER for Q06",
            schema_hint="question_id, participant_id, coded_spans",
            source_hash="src_hash_q06_p002",
            validator_fn=validate_structured_coding_response,
            hfg_metadata={"response_id": "RESP_002_Q06"},
        )
        assert res.schema_status == SchemaStatus.VALID
        assert res.repair_attempted is True
        assert len(observed_requests) == 4
        # Verify changed seeds across attempts 1, 2, 3, and repair
        seeds = [r["seed"] for r in observed_requests]
        assert len(set(seeds)) == 4
        # Attempt 2 includes exact parser error and JSON-only instruction
        assert "Expecting ',' delimiter" in observed_requests[1]["messages"][1]["content"]
        assert "ONE valid JSON object only" in observed_requests[1]["messages"][1]["content"]
        # Attempt 3 uses compact prompt
        assert "COMPACT_PROMPT_MARKER" in observed_requests[2]["messages"][1]["content"]
        # Attempt 4 is model-based syntax repair containing malformed JSON & parser error
        assert "Repair ONLY the JSON syntax" in observed_requests[3]["messages"][1]["content"]
        assert "Expecting ',' delimiter" in observed_requests[3]["messages"][1]["content"]
        assert mgr.checkpoint_store.list_failed_items("coder_b") == []

        # Case 2: Model-based repair alters analytical meaning (flips probability argmax) -> MUST BE REJECTED
        drifted_obj = json.loads(json.dumps(valid_obj))
        drifted_obj["coded_spans"][0]["alternative_probabilities"] = {"pole_level": 0.15, "prof_level": 0.85}
        observed_requests.clear()

        def _fake_urlopen_repair_drift(req, timeout=None):
            pl = json.loads(req.data.decode("utf-8"))
            observed_requests.append(pl)
            is_repair = bool((pl.get("hfg_metadata") or {}).get("repair_mode"))
            content = json.dumps(drifted_obj) if is_repair else malformed_missing_comma
            return _FakeHTTPResp(
                {
                    "choices": [{"index": 0, "message": {"content": content}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 120, "completion_tokens": 85},
                }
            )

        monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen_repair_drift)
        res_drift = mgr.execute_json_chat_completion(
            coder_id="coder_b",
            question_id="Q06",
            participant_id="PARTICIPANT_003",
            system_prompt="System prompt",
            user_prompt="Full prompt for Q06 P003",
            compact_user_prompt="COMPACT_PROMPT_MARKER for Q06 P003",
            schema_hint="question_id, participant_id, coded_spans",
            source_hash="src_hash_q06_p003",
            validator_fn=validate_structured_coding_response,
            hfg_metadata={"response_id": "RESP_003_Q06"},
        )
        assert res_drift.schema_status != SchemaStatus.VALID
        assert "Model-based repair rejected" in (res_drift.error_message or "")
        assert res_drift.error_class == "RepairSemanticDriftError"
        failed_items = mgr.checkpoint_store.list_failed_items("coder_b")
        assert len(failed_items) == 1
        assert failed_items[0]["participant_id"] == "PARTICIPANT_003"
        assert "raw_response" not in failed_items[0]
    finally:
        mgr.shutdown()


def test_finish_reason_length_token_exhaustion_recovery(tmp_path, monkeypatch):
    """Verify finish_reason=length triggers bounded max_tokens increase, concise compact prompt, and token logging."""
    import urllib.request

    cfg = _make_test_config(tmp_path, mode=ExecutionMode.SEQUENTIAL_FALLBACK)
    cfg.max_generation_length = 2048
    mgr = DualCoderRuntimeManager(config=cfg, use_mock_server=True)
    mgr.server_b.start()
    try:
        calls = []
        valid_obj = {
            "question_id": "Q06",
            "participant_id": "PARTICIPANT_002",
            "coder_id": "coder_b",
            "missingness_state": "observed_usable",
            "coded_spans": [
                {
                    "subtopic_label_en": "pole_collaboration",
                    "verbatim_quote": "Les poles doivent collaborer.",
                    "char_start": 0,
                    "char_end": 28,
                    "alternative_probabilities": {"pole_level": 0.7, "prof_level": 0.3},
                    "semantic_importance": 0.8,
                    "coder_confidence": 0.9,
                }
            ],
            "rationale_summary": "Concise summary.",
        }

        class _FakeHTTPResp:
            def __init__(self, body: dict):
                self._bytes = json.dumps(body).encode("utf-8")

            def read(self):
                return self._bytes

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        def _fake_urlopen_length(req, timeout=None):
            pl = json.loads(req.data.decode("utf-8"))
            calls.append(pl)
            if len(calls) == 1:
                return _FakeHTTPResp(
                    {
                        "choices": [{"index": 0, "message": {"content": '{"question_id": "Q06"'}, "finish_reason": "length"}],
                        "usage": {"prompt_tokens": 350, "completion_tokens": 1024},
                    }
                )
            return _FakeHTTPResp(
                {
                    "choices": [{"index": 0, "message": {"content": json.dumps(valid_obj)}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 210, "completion_tokens": 140},
                }
            )

        monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen_length)
        res = mgr.execute_json_chat_completion(
            coder_id="coder_b",
            question_id="Q06",
            participant_id="PARTICIPANT_002",
            system_prompt="System",
            user_prompt="Verbose prompt",
            compact_user_prompt="COMPACT_CONCISE_PROMPT",
            source_hash="src_len_test",
            validator_fn=validate_structured_coding_response,
            max_tokens=1024,
            max_tokens_cap=2048,
        )
        assert res.schema_status == SchemaStatus.VALID
        assert res.input_tokens == 210
        assert res.output_tokens == 140
        assert len(calls) == 2
        assert calls[0]["max_tokens"] == 1024
        assert calls[1]["max_tokens"] == 1536  # 1.5x bounded bump within max_tokens_cap=2048
        assert "finish_reason=length" in calls[1]["messages"][1]["content"]
        assert "COMPACT_CONCISE_PROMPT" in calls[1]["messages"][1]["content"]
    finally:
        mgr.shutdown()


def test_wal_preservation_and_resumable_failure_isolation(tmp_path, monkeypatch):
    """Prove failure on one coordinate preserves all prior WAL checkpoints, leaves failed coordinate unresolved, and resumes without recomputing completed items."""
    from tests.test_runtime import _prepare_isolated_hfg_workspace

    ws = _prepare_isolated_hfg_workspace(tmp_path)
    cfg = _make_test_config(ws, mode=ExecutionMode.SEQUENTIAL_FALLBACK)
    cfg.checkpoint_dir = ".checkpoints/gpu_coder_wal"

    # Inject permanent malformed JSON ONLY for coder_b on PARTICIPANT_002 / Q06 during first run
    orig_exec_core = DualCoderRuntimeManager._execute_chat_completion_core
    fail_once_state = {"block_p2_q06": True, "live_calls_run2": []}

    def _patched_exec_core(self, *args, **kwargs):
        cid = kwargs.get("coder_id")
        qid = kwargs.get("question_id")
        pid = kwargs.get("participant_id")
        if fail_once_state["block_p2_q06"] and cid == "coder_b" and qid == "Q06" and pid == "PARTICIPANT_002":
            # Simulate exhausted invalid JSON returning privacy-safe diagnostic without touching other WAL items
            diag = {
                "coder_id": cid,
                "participant_id": pid,
                "question_id": qid,
                "attempt_number": 3,
                "finish_reason": "stop",
                "input_tokens": 500,
                "output_tokens": 900,
                "configured_max_tokens": 2048,
                "parse_error_position": {"line": 140, "column": 8, "char": 8268},
                "response_length": 8300,
                "response_sha256": "deadbeef" * 8,
                "error_class": "JSONDecodeError",
                "error_message": "Expecting ',' delimiter: line 140 column 8 (char 8268)",
            }
            self.checkpoint_store.record_failure(diag, mark_unresolved=True)
            from src.runtime.model_runtime import StructuredCoderResponse
            return StructuredCoderResponse(
                coder_id=cid,
                question_id=qid,
                participant_id=pid,
                schema_status=SchemaStatus.INVALID_JSON,
                raw_response="",
                parsed_response=None,
                error_message="JSON parse error: Expecting ',' delimiter: line 140 column 8 (char 8268)",
                runtime_sec=0.1,
                peak_vram_mb=1000.0,
                input_tokens=500,
                output_tokens=900,
                finish_reason="stop",
                error_class="JSONDecodeError",
                parse_error_position={"line": 140, "column": 8, "char": 8268},
                attempts_made=3,
                repair_attempted=True,
            )
        if not fail_once_state["block_p2_q06"]:
            # Track non-checkpoint calls on resume
            cached = self.checkpoint_store.get(
                run_id=self.config.run_id,
                question_id=qid,
                coder_id=cid,
                prompt_hash=kwargs.get("prompt_hash", ""),
                source_hash=kwargs.get("source_hash", ""),
                participant_id=pid,
            )
            if cached is None:
                fail_once_state["live_calls_run2"].append((cid, qid, pid))
        return orig_exec_core(self, *args, **kwargs)

    monkeypatch.setattr(DualCoderRuntimeManager, "_execute_chat_completion_core", _patched_exec_core)

    with pytest.raises(DualCoderExecutionError, match="PARTICIPANT_002, Q06"):
        run_dual_coder_production(
            base_dir=ws,
            run_id="run_20261111_002",
            require_live_gpu=False,
            allow_mock_for_test=True,
            config=cfg,
        )

    # Final production outputs must NOT exist while required coordinate is unresolved
    assert not (ws / "data" / "processed" / "coder_b_outputs.json").is_file()

    store = AtomicQuestionCheckpointStore(ws / cfg.checkpoint_dir, run_id="run_20261111_002")
    coder_a_records = [r for r in store.all_records() if r.coder_id == "coder_a"]
    coder_b_records = [r for r in store.all_records() if r.coder_id == "coder_b"]
    assert len(coder_a_records) > 0
    assert len(coder_b_records) > 0
    # Failed coordinate must NOT be marked complete in WAL
    assert not any(r.question_id == "Q06" and r.participant_id == "PARTICIPANT_002" for r in coder_b_records)
    # Failed item diagnostic must be persisted without raw text
    failed = store.list_failed_items("coder_b")
    assert len(failed) == 1
    assert failed[0]["question_id"] == "Q06" and failed[0]["participant_id"] == "PARTICIPANT_002"

    # Resume: lift failure injection -> completed Coder A and earlier Coder B items are NOT recomputed
    fail_once_state["block_p2_q06"] = False
    res_resume = run_dual_coder_production(
        base_dir=ws,
        run_id="run_20261111_002",
        require_live_gpu=False,
        allow_mock_for_test=True,
        config=cfg,
    )
    assert res_resume["status"] == "PASS"
    # None of Coder A's completed items were rerun!
    assert not any(cid == "coder_a" for cid, _, _ in fail_once_state["live_calls_run2"])
    # Coder B resumed directly at (Q06, PARTICIPANT_002) without rerunning Q01 or earlier Q06 items
    assert ("coder_b", "Q06", "PARTICIPANT_002") in fail_once_state["live_calls_run2"]
    assert not any(cid == "coder_b" and qid == "Q01" for cid, qid, _ in fail_once_state["live_calls_run2"])
    store_after = AtomicQuestionCheckpointStore(ws / cfg.checkpoint_dir, run_id="run_20261111_002")
    assert store_after.list_failed_items("coder_b") == []


def test_smoke_tiny_profile_diagnostics_family_isolation_and_orchestrator_block(tmp_path):
    """Verify smoke_tiny exercises lightweight independent models, self-diagnostics, non-production flags, and keeps Agent 03 BLOCKED."""
    from src.pipeline.orchestrator import Agent03ReleaseDecision, PipelineOrchestrator

    ws = _prepare_isolated_hfg_workspace(tmp_path)
    res = run_dual_coder_production(
        base_dir=ws,
        run_id="run_20261111_002",
        execution_profile="smoke_tiny",
        require_live_gpu=False,
        allow_mock_for_test=True,
    )
    assert res["status"] == "PASS"
    assert res["execution_profile"] == "smoke_tiny"
    assert res["production_eligible"] is False
    assert res["synthetic_or_test_execution"] is True
    assert res["coder_a_metadata"]["model_repo"] == DEFAULT_SMOKE_CODER_A_SPEC.model_repo
    assert res["coder_b_metadata"]["model_repo"] == DEFAULT_SMOKE_CODER_B_SPEC.model_repo
    assert "profiles/smoke_tiny" in res["coder_a_output_path"]
    assert "profiles/smoke_tiny" in res["coder_b_output_path"]
    assert not (ws / "data" / "processed" / "coder_a_outputs.json").exists()
    assert not (ws / "data" / "processed" / "coder_b_outputs.json").exists()

    diag = res["smoke_diagnostics"]
    assert all(diag.values()), f"Expected all smoke_tiny diagnostics to pass: {diag}"

    # Qwen/DeepSeek on Coder B remains strictly forbidden even in smoke_tiny
    qwen_smoke_b = CoderModelSpec(
        coder_id="coder_b",
        model_family="qwen2.5",
        model_repo="Qwen/Qwen2.5-1.5B-Instruct",
        model_revision="main",
        quantization="FP16",
        port=8002,
    )
    with pytest.raises(ValueError, match="Model-family diversity violation"):
        validate_model_family_diversity(
            DEFAULT_SMOKE_CODER_A_SPEC,
            qwen_smoke_b,
            execution_profile="smoke_tiny",
        )

    orch = PipelineOrchestrator(base_dir=ws, run_id="run_20261111_002").evaluate()
    assert orch.agent_03_release_decision == Agent03ReleaseDecision.BLOCKED


def test_pilot_subset_profile_coverage_pinned_revisions_and_orchestrator_block(tmp_path):
    """Verify pilot_subset uses pinned production models/SHAs, covers all 7 edge-case categories, defaults sequential, and keeps Agent 03 BLOCKED."""
    import pandas as pd
    from src.pipeline.orchestrator import Agent03ReleaseDecision, PipelineOrchestrator

    ws = _prepare_isolated_hfg_workspace(tmp_path)
    norm_df = pd.read_parquet(ws / "data" / "normalized" / "answers_normalized.parquet")
    subset_df = select_profile_dataframe(norm_df, ExecutionProfile.PILOT_SUBSET)

    assert not subset_df[(subset_df["participant_id"] == "PARTICIPANT_002") & (subset_df["question_id"] == "Q06")].empty
    statuses = set(subset_df["epistemic_status"].astype(str))
    for req_status in (
        "substantive",
        "raw_blank",
        "explicit_no_opinion",
        "explicit_insufficient_experience",
        "ambiguous",
    ):
        assert req_status in statuses, f"Missing mandatory pilot_subset status: {req_status}"

    res = run_dual_coder_production(
        base_dir=ws,
        run_id="run_20261111_002",
        execution_profile="pilot_subset",
        require_live_gpu=False,
        allow_mock_for_test=True,
    )
    assert res["status"] == "PASS"
    assert res["execution_profile"] == "pilot_subset"
    assert res["production_eligible"] is False
    assert res["synthetic_or_test_execution"] is False
    assert res["execution_mode_final"] == ExecutionMode.SEQUENTIAL_FALLBACK.value
    assert res["coder_a_metadata"]["model_repo"] == PINNED_PRODUCTION_CODER_A_REPO
    assert res["coder_a_metadata"]["model_revision"] == PINNED_PRODUCTION_CODER_A_REVISION
    assert res["coder_b_metadata"]["model_repo"] == PINNED_PRODUCTION_CODER_B_REPO
    assert res["coder_b_metadata"]["model_revision"] == PINNED_PRODUCTION_CODER_B_REVISION
    assert "profiles/pilot_subset" in res["coder_a_output_path"]
    assert not (ws / "data" / "processed" / "coder_a_outputs.json").exists()

    payload_a = json.loads(Path(res["coder_a_output_path"]).read_text(encoding="utf-8"))
    assert payload_a["execution_profile"] == "pilot_subset"
    assert payload_a["production_eligible"] is False
    assert payload_a["synthetic_or_test_execution"] is False
    non_usable = [r for r in payload_a["coding_results"] if r["missingness_state"] != "observed_usable"]
    assert len(non_usable) >= 3
    assert all(r["alternative_probabilities"] == {} for r in non_usable)

    orch = PipelineOrchestrator(base_dir=ws, run_id="run_20261111_002").evaluate()
    assert orch.agent_03_release_decision == Agent03ReleaseDecision.BLOCKED


def test_production_profile_default_and_safe_sequential_selection(tmp_path):
    """Verify production remains default profile and uses SEQUENTIAL_FALLBACK unless a live concurrent benchmark proves safety."""
    import inspect

    sig = inspect.signature(run_dual_coder_production)
    assert sig.parameters["execution_profile"].default == ExecutionProfile.PRODUCTION.value

    cfg_concurrent = _make_test_config(tmp_path, mode=ExecutionMode.CONCURRENT_DUAL_SERVER)
    cfg_concurrent.derived_from_benchmark = False
    assert (
        select_safe_execution_mode(
            cfg_concurrent,
            bench_path=tmp_path / "missing_benchmark.json",
            execution_profile=ExecutionProfile.PRODUCTION,
        )
        == ExecutionMode.SEQUENTIAL_FALLBACK
    )

    # Even with derived_from_benchmark=True, a sequential benchmark keeps SEQUENTIAL_FALLBACK
    bench_seq = tmp_path / "bench_seq.json"
    bench_seq.write_text(
        json.dumps(
            {
                "live_gpu_benchmark_status": "EXECUTED_LIVE_GPU",
                "measured_hardware": {"gpu_available": True},
                "derived_memory_budget": {"execution_mode": "SEQUENTIAL_FALLBACK", "concurrent_feasible": False},
            }
        ),
        encoding="utf-8",
    )
    cfg_concurrent.derived_from_benchmark = True
    assert (
        select_safe_execution_mode(
            cfg_concurrent,
            bench_path=bench_seq,
            execution_profile=ExecutionProfile.PRODUCTION,
        )
        == ExecutionMode.SEQUENTIAL_FALLBACK
    )

    # Full production mock run without an explicit config override defaults safely to SEQUENTIAL_FALLBACK
    ws = _prepare_isolated_hfg_workspace(tmp_path)
    res_prod = run_dual_coder_production(
        base_dir=ws,
        run_id="run_20261111_002",
        require_live_gpu=False,
        allow_mock_for_test=True,
    )
    assert res_prod["execution_profile"] == "production"
    assert res_prod["production_eligible"] is True
    assert res_prod["synthetic_or_test_execution"] is False
    assert res_prod["execution_mode_final"] == ExecutionMode.SEQUENTIAL_FALLBACK.value
    assert (ws / "data" / "processed" / "coder_a_outputs.json").is_file()
    assert (ws / "data" / "processed" / "coder_b_outputs.json").is_file()


def test_checkpoint_namespace_isolation_and_mismatch_rejection(tmp_path):
    """Verify separate namespaces across profiles and strict rejection on model/revision/quantization/profile mismatch."""
    ckpt_root = tmp_path / "shared_checkpoints"

    smoke_store = AtomicQuestionCheckpointStore(ckpt_root, run_id="run_20261111_002", execution_profile="smoke_tiny")
    smoke_rec = QuestionCheckpointRecord(
        run_id="run_20261111_002",
        execution_profile="smoke_tiny",
        question_id="Q06",
        participant_id="PARTICIPANT_002",
        coder_id="coder_a",
        prompt_hash="ph_smoke",
        source_hash="sh_smoke",
        model_repo=DEFAULT_SMOKE_CODER_A_SPEC.model_repo,
        model_revision="smoke_rev_1",
        quantization=DEFAULT_SMOKE_CODER_A_SPEC.quantization,
        generation_config={"temperature": 0.0},
        raw_response='{"ok": true}',
        parsed_response={"ok": True},
        schema_status=SchemaStatus.VALID.value,
        runtime_sec=0.2,
        peak_vram_mb=2048.0,
    )
    smoke_store.put(smoke_rec)

    pilot_store = AtomicQuestionCheckpointStore(ckpt_root, run_id="run_20261111_002", execution_profile="pilot_subset")
    prod_store = AtomicQuestionCheckpointStore(ckpt_root, run_id="run_20261111_002", execution_profile="production")
    assert pilot_store.all_records() == []
    assert prod_store.all_records() == []

    prod_rec = QuestionCheckpointRecord(
        run_id="run_20261111_002",
        execution_profile="production",
        question_id="Q06",
        participant_id="PARTICIPANT_002",
        coder_id="coder_a",
        prompt_hash="ph_prod",
        source_hash="sh_prod",
        model_repo=PINNED_PRODUCTION_CODER_A_REPO,
        model_revision=PINNED_PRODUCTION_CODER_A_REVISION,
        quantization="AWQ-INT4",
        generation_config={"temperature": 0.0},
        raw_response='{"ok": true}',
        parsed_response={"ok": True},
        schema_status=SchemaStatus.VALID.value,
        runtime_sec=1.2,
        peak_vram_mb=20480.0,
    )
    prod_store.put(prod_rec)

    # Mismatched revision must raise CheckpointMismatchError
    with pytest.raises(CheckpointMismatchError, match="model_revision"):
        prod_store.get(
            run_id="run_20261111_002",
            question_id="Q06",
            coder_id="coder_a",
            prompt_hash="ph_prod",
            source_hash="sh_prod",
            participant_id="PARTICIPANT_002",
            execution_profile="production",
            model_repo=PINNED_PRODUCTION_CODER_A_REPO,
            model_revision="0" * 40,
            quantization="AWQ-INT4",
            raise_on_mismatch=True,
        )

    # Mismatched quantization must raise CheckpointMismatchError
    with pytest.raises(CheckpointMismatchError, match="quantization"):
        prod_store.verify_or_bind_coder_spec(
            "coder_a",
            CoderModelSpec(
                coder_id="coder_a",
                model_family="deepseek",
                model_repo=PINNED_PRODUCTION_CODER_A_REPO,
                model_revision=PINNED_PRODUCTION_CODER_A_REVISION,
                quantization="FP8",
                port=8001,
            ),
        )

    # Mismatched profile lookup against production store must raise CheckpointMismatchError
    with pytest.raises(CheckpointMismatchError, match="execution_profile"):
        prod_store.get(
            run_id="run_20261111_002",
            question_id="Q06",
            coder_id="coder_a",
            prompt_hash="ph_prod",
            source_hash="sh_prod",
            participant_id="PARTICIPANT_002",
            execution_profile="pilot_subset",
            raise_on_mismatch=True,
        )


def test_privacy_safe_failure_diagnostics_redact_raw_content(tmp_path, monkeypatch):
    """Verify failure diagnostics never persist raw prompt, response, or Pydantic input_value respondent text."""
    import urllib.request

    cfg = _make_test_config(tmp_path, mode=ExecutionMode.SEQUENTIAL_FALLBACK)
    mgr = DualCoderRuntimeManager(config=cfg, use_mock_server=True)
    mgr.server_b.start()
    try:
        sentinel_secret = "CONFIDENTIAL_RESPONDENT_TEXT_DO_NOT_LOG"

        class _FakeHTTPResp:
            def __init__(self, body: dict):
                self._bytes = json.dumps(body).encode("utf-8")

            def read(self):
                return self._bytes

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        # Trigger real _record_diag via execute_json_chat_completion returning invalid schema with Pydantic input_value containing sentinel_secret
        bad_payload = {
            "question_id": sentinel_secret,
            "participant_id": "PARTICIPANT_002",
            "coder_id": "coder_b",
            "missingness_state": "observed_usable",
            "coded_spans": [],
            "rationale_summary": sentinel_secret,
        }

        def _fake_urlopen_invalid(req, timeout=None):
            return _FakeHTTPResp(
                {
                    "choices": [{"index": 0, "message": {"content": json.dumps(bad_payload)}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 90, "completion_tokens": 40},
                }
            )

        monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen_invalid)
        res = mgr.execute_json_chat_completion(
            coder_id="coder_b",
            question_id="Q06",
            participant_id="PARTICIPANT_002",
            system_prompt="System prompt",
            user_prompt=f"Prompt with {sentinel_secret}",
            compact_user_prompt=f"Compact with {sentinel_secret}",
            source_hash="src_privacy_test",
            validator_fn=validate_structured_coding_response,
        )
        assert res.schema_status != SchemaStatus.VALID

        mgr.checkpoint_store.record_failure(
            {
                "coder_id": "coder_b",
                "question_id": "Q06",
                "participant_id": "PARTICIPANT_002",
                "raw_response": sentinel_secret,
                "source_text": sentinel_secret,
                "raw_value": sentinel_secret,
                "prompt": sentinel_secret,
                "error_class": "JSONDecodeError",
                "error_message": "Expecting ',' delimiter: line 2 column 4",
            },
            mark_unresolved=True,
        )
        diag_text = mgr.checkpoint_store.failure_diagnostics_path.read_text(encoding="utf-8")
        assert sentinel_secret not in diag_text
        assert "raw_response" not in diag_text
        assert "source_text" not in diag_text
        assert "[REDACTED]" in diag_text

        for failed_item in mgr.checkpoint_store.list_failed_items("coder_b"):
            serialized = json.dumps(failed_item)
            assert sentinel_secret not in serialized
    finally:
        mgr.shutdown()


def test_external_checkpoint_root_resumes_across_fresh_clone(tmp_path, monkeypatch):
    """Simulate Colab VM reset / fresh repo clone sharing an external checkpoint_root and prove resume without recomputation."""
    (tmp_path / "clone_1").mkdir(parents=True, exist_ok=True)
    (tmp_path / "clone_2").mkdir(parents=True, exist_ok=True)
    clone_1 = _prepare_isolated_hfg_workspace(tmp_path / "clone_1")
    clone_2 = _prepare_isolated_hfg_workspace(tmp_path / "clone_2")
    external_ckpts = tmp_path / "gdrive_persistent_checkpoints"

    orig_exec_core = DualCoderRuntimeManager._execute_chat_completion_core
    state = {"inject_failure": True, "live_calls_clone_2": []}

    def _exec_with_interruption(self, *args, **kwargs):
        cid = kwargs.get("coder_id")
        qid = kwargs.get("question_id")
        pid = kwargs.get("participant_id")
        if state["inject_failure"] and cid == "coder_b" and qid == "Q06" and pid == "PARTICIPANT_002":
            from src.runtime.model_runtime import StructuredCoderResponse

            self.checkpoint_store.record_failure(
                {
                    "coder_id": cid,
                    "question_id": qid,
                    "participant_id": pid,
                    "attempt_number": 3,
                    "finish_reason": "stop",
                    "error_class": "JSONDecodeError",
                    "error_message": "Simulated Colab disconnect failure on Q06/P002",
                },
                mark_unresolved=True,
            )
            return StructuredCoderResponse(
                coder_id=cid,
                question_id=qid,
                participant_id=pid,
                schema_status=SchemaStatus.INVALID_JSON,
                raw_response="",
                parsed_response=None,
                error_message="Simulated Colab disconnect failure",
                runtime_sec=0.1,
                peak_vram_mb=0.0,
                input_tokens=500,
                output_tokens=0,
                finish_reason="stop",
                error_class="JSONDecodeError",
                attempts_made=3,
                repair_attempted=True,
            )
        if not state["inject_failure"]:
            cached = self.checkpoint_store.get(
                run_id=self.config.run_id,
                question_id=qid,
                coder_id=cid,
                prompt_hash=kwargs.get("prompt_hash", ""),
                source_hash=kwargs.get("source_hash", ""),
                participant_id=pid,
                execution_profile=self.config.execution_profile,
                raise_on_mismatch=False,
            )
            if cached is None:
                state["live_calls_clone_2"].append((cid, qid, pid))
        return orig_exec_core(self, *args, **kwargs)

    monkeypatch.setattr(DualCoderRuntimeManager, "_execute_chat_completion_core", _exec_with_interruption)

    # First run on clone_1 writes checkpoints into external_ckpts and stops cleanly on injected failure
    with pytest.raises(DualCoderExecutionError, match="PARTICIPANT_002, Q06"):
        run_dual_coder_production(
            base_dir=clone_1,
            run_id="run_20261111_002",
            execution_profile="pilot_subset",
            checkpoint_root=external_ckpts,
            require_live_gpu=False,
            allow_mock_for_test=True,
        )

    ext_store = AtomicQuestionCheckpointStore(
        external_ckpts,
        run_id="run_20261111_002",
        execution_profile="pilot_subset",
    )
    completed_before_resume = {(r.coder_id, r.question_id, r.participant_id) for r in ext_store.all_records()}
    assert len(completed_before_resume) > 0
    assert ("coder_b", "Q06", "PARTICIPANT_002") not in completed_before_resume
    assert len(ext_store.list_failed_items("coder_b")) == 1

    # Fresh clone_2 at a completely different workspace directory resumes from external_ckpts
    state["inject_failure"] = False
    res_clone_2 = run_dual_coder_production(
        base_dir=clone_2,
        run_id="run_20261111_002",
        execution_profile="pilot_subset",
        checkpoint_root=external_ckpts,
        require_live_gpu=False,
        allow_mock_for_test=True,
    )
    assert res_clone_2["status"] == "PASS"
    assert res_clone_2["checkpoint_dir"] == str(external_ckpts.resolve())
    assert res_clone_2["coder_a_metadata"]["checkpoint_hits"] > 0
    assert res_clone_2["coder_b_metadata"]["checkpoint_hits"] > 0
    # Zero redundant LLM executions for coder_a or any previously checkpointed coder_b coordinate!
    assert not any(cid == "coder_a" for cid, _, _ in state["live_calls_clone_2"])
    assert ("coder_b", "Q06", "PARTICIPANT_002") in state["live_calls_clone_2"]
    assert set(state["live_calls_clone_2"]).isdisjoint(completed_before_resume)

    ext_store_after = AtomicQuestionCheckpointStore(
        external_ckpts,
        run_id="run_20261111_002",
        execution_profile="pilot_subset",
    )
    assert ext_store_after.list_failed_items("coder_b") == []

