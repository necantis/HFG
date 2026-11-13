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
    CoderModelSpec,
    DEFAULT_CODER_A_CANDIDATES,
    DEFAULT_CODER_A_SPEC,
    DEFAULT_CODER_B_MISTRAL_CANDIDATES,
    DEFAULT_CODER_B_MISTRAL_SPEC,
    DualCoderExecutionError,
    DualCoderRuntimeManager,
    ExecutionMode,
    GPURuntimeConfig,
    HardwareProfile,
    QuestionCheckpointRecord,
    SchemaStatus,
    build_and_save_runtime_config,
    derive_memory_budget_from_measurements,
    detect_hardware_profile,
    resolve_and_verify_coder_spec,
    resolve_dual_coder_specs,
    run_dual_coder_production,
    run_runtime_benchmark_suite,
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

    scanner = HardcodingScanner(base_dir=repo_root)
    assert scanner.scan_file(nb07_path) == []
    assert scanner.scan_file(nb01_path) == []

