"""
Agent 11 Orchestration, Dual-Coder Invariant Validation, Notebook & Release Gate Tests.
"""

from __future__ import annotations

import dataclasses
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

import pandas as pd
import pytest

from src.hardcoding_scanner import HardcodingScanner
from src.ingest.ingestion import ingest_survey
from src.pipeline.orchestrator import (
    Agent03ReleaseDecision,
    PipelineOrchestrator,
    PipelineState,
    evaluate_pipeline_state,
    validate_dual_coder_outputs,
)
from src.registry.question_registry import QuestionRegistry, build_question_registry


REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_norm_and_specs(root: Path):
    norm_df = pd.read_parquet(root / "data" / "normalized" / "answers_normalized.parquet")
    reg = QuestionRegistry(raw_csv_path=root / "data" / "raw" / "survey_raw.csv")
    specs = reg.build_from_answers(norm_df)
    return norm_df, specs


def _build_valid_dual_coder_payloads(norm_df: pd.DataFrame, specs: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, Any]]:
    usable_rows = norm_df[
        (norm_df["missingness_state"] == "observed_usable")
        & (norm_df["question_id"] != "Q14")
    ]

    def _make_payload(
        coder_id: str,
        model_family: str,
        base_model: str,
        model_repo: str,
        quantization: str,
        prompt_hash: str,
    ) -> Dict[str, Any]:
        spans = []
        codings = []
        subtopics = []
        values = []
        seen_subtopics = set()

        for idx, (_, row) in enumerate(usable_rows.iterrows()):
            pid = str(row["participant_id"])
            qid = str(row["question_id"])
            text = str(row.get("source_text") or row.get("raw_value") or "")
            quote_end = min(len(text), max(1, min(12, len(text))))
            quote = text[:quote_end]
            sp_id = f"{coder_id}_sp_{idx:03d}"
            spans.append(
                {
                    "span_id": sp_id,
                    "participant_id": pid,
                    "question_id": qid,
                    "char_start": 0,
                    "char_end": quote_end,
                    "verbatim_quote": quote,
                }
            )
            st_id = f"{qid}_ST_EMPIRICAL"
            if qid not in seen_subtopics:
                seen_subtopics.add(qid)
                subtopics.append(
                    {
                        "subtopic_id": st_id,
                        "question_id": qid,
                        "proposed_label_en": f"Empirical respondent issue {qid}",
                        "supporting_participant_ids": [pid],
                        "supporting_span_ids": [sp_id],
                    }
                )
            good_class = None if specs[qid].economic_good_classification_policy in ("DISABLED", "CONDITIONAL") else "club_good"
            codings.append(
                {
                    "coding_id": f"{coder_id}_c_{idx:03d}",
                    "participant_id": pid,
                    "question_id": qid,
                    "subtopic_id": st_id,
                    "missingness_state": "observed_usable",
                    "alternative_probabilities": {"option_a": 0.7, "option_b": 0.3},
                    "semantic_importance": 0.85,
                    "coder_confidence": 0.9,
                    "coder_agreement": 0.92,
                    "economic_good_class": good_class,
                    "evidence_span_ids": [sp_id],
                }
            )

        # Include explicit non-preference record with empty alternative_probabilities
        non_pref = norm_df[norm_df["epistemic_status"] == "explicit_no_opinion"].iloc[0]
        codings.append(
            {
                "coding_id": f"{coder_id}_nonpref_001",
                "participant_id": str(non_pref["participant_id"]),
                "question_id": str(non_pref["question_id"]),
                "subtopic_id": f"{non_pref['question_id']}_ST_EMPIRICAL",
                "missingness_state": str(non_pref["missingness_state"]),
                "alternative_probabilities": {},
                "semantic_importance": 0.0,
                "coder_confidence": 0.95,
                "coder_agreement": 1.0,
                "economic_good_class": None,
                "evidence_span_ids": [],
            }
        )
        values.append(
            {
                "value_id": f"{coder_id}_val_001",
                "label_en": "transparency_accountability",
                "evidence_span_ids": [spans[0]["span_id"]],
            }
        )
        return {
            "run_id": "run_20261111_002",
            "coder_id": coder_id,
            "execution_profile": "production",
            "production_eligible": True,
            "synthetic_or_test_execution": False,
            "execution_metadata": {
                "execution_profile": "production",
                "production_eligible": True,
                "synthetic_or_test_execution": False,
                "model_family": model_family,
                "base_model": base_model,
                "model_repo": model_repo,
                "model_revision": "main",
                "quantization": quantization,
                "serving_engine": "vllm_openai_server",
                "execution_mode": "CONCURRENT_DUAL_SERVER",
                "model_load_succeeded": True,
                "gpu_resident": True,
                "inference_occurred": True,
                "responses_attempted": len(usable_rows),
                "responses_completed": len(usable_rows),
                "responses_failed": 0,
                "prompt_hash": prompt_hash,
            },
            "evidence_spans": spans,
            "discovered_subtopics": subtopics,
            "value_assignments": values,
            "coding_results": codings,
        }

    payload_a = _make_payload(
        coder_id="coder_a",
        model_family="deepseek",
        base_model="deepseek-ai/DeepSeek-R1-Distill-Qwen-32B",
        model_repo="deepseek-ai/DeepSeek-R1-Distill-Qwen-32B-AWQ",
        quantization="AWQ-INT4",
        prompt_hash="sha256:coder_a_prompt_v1",
    )
    payload_b = _make_payload(
        coder_id="coder_b",
        model_family="mistral",
        base_model="mistralai/Mistral-Small-3.1-24B-Instruct-2503",
        model_repo="mistralai/Mistral-Small-3.1-24B-Instruct-2503-AWQ",
        quantization="INT4-AWQ",
        prompt_hash="sha256:coder_b_prompt_v1",
    )
    return payload_a, payload_b


def test_real_repo_pipeline_state_blocks_agent_03_until_gpu_coding_exists():
    report = evaluate_pipeline_state(base_dir=REPO_ROOT, run_id="run_20261111_002", write_log=False)

    assert report.agent_01_gate_1 == "PASS"
    assert report.agent_02_entrance_gate == "PASS"
    assert report.agent_07_persisted is True
    assert report.live_gpu_hardware_preflight == "PASS"
    assert report.live_gpu_runtime_benchmark == "NOT_EXECUTED"

    assert report.coder_a.execution_status == "NOT_EXECUTED"
    assert report.coder_b.execution_status == "NOT_EXECUTED"
    assert report.dual_coder_validation.status == "BLOCKED"

    assert report.states[PipelineState.INGESTION_READY.value] is True
    assert report.states[PipelineState.QUALITATIVE_CONTRACT_READY.value] is True
    assert report.states[PipelineState.GPU_PREFLIGHT_READY.value] is True
    assert report.states[PipelineState.CODER_A_COMPLETE.value] is False
    assert report.states[PipelineState.CODER_B_COMPLETE.value] is False
    assert report.states[PipelineState.DUAL_CODER_VALIDATED.value] is False
    assert report.states[PipelineState.AGENT_03_RELEASE_READY.value] is False
    assert report.highest_verified_state == PipelineState.GPU_PREFLIGHT_READY.value

    assert report.agent_03_release_decision == Agent03ReleaseDecision.BLOCKED
    joined = "\n".join(report.blocking_reasons)
    assert "5-stage GPU runtime benchmark" in joined
    assert "Coder A" in joined
    assert "Coder B" in joined


def test_validate_dual_coder_outputs_passes_valid_fixture():
    norm_df, specs = _load_norm_and_specs(REPO_ROOT)
    payload_a, payload_b = _build_valid_dual_coder_payloads(norm_df, specs)

    res = validate_dual_coder_outputs(
        normalized_df=norm_df,
        question_specs=specs,
        coder_a_payload=payload_a,
        coder_b_payload=payload_b,
    )
    assert res.status == "PASS"
    assert all(res.checks.values())
    assert res.violations == []


def test_validate_dual_coder_outputs_enforces_invariants_a_through_h():
    norm_df, specs = _load_norm_and_specs(REPO_ROOT)

    # [A] Fabricated coordinate
    pa, pb = _build_valid_dual_coder_payloads(norm_df, specs)
    pa["coding_results"][0]["participant_id"] = "FAKE_PARTICIPANT_999"
    res_a = validate_dual_coder_outputs(normalized_df=norm_df, question_specs=specs, coder_a_payload=pa, coder_b_payload=pb)
    assert res_a.status == "FAIL"
    assert res_a.checks["A_structural_integrity"] is False

    # [B] Offset / verbatim mismatch
    pa, pb = _build_valid_dual_coder_payloads(norm_df, specs)
    pa["evidence_spans"][0]["verbatim_quote"] = "MISMATCHED_FABRICATED_QUOTE"
    res_b = validate_dual_coder_outputs(normalized_df=norm_df, question_specs=specs, coder_a_payload=pa, coder_b_payload=pb)
    assert res_b.status == "FAIL"
    assert res_b.checks["B_evidence_provenance"] is False

    # [C] Synthetic preference on explicit_no_opinion
    pa, pb = _build_valid_dual_coder_payloads(norm_df, specs)
    pb["coding_results"][-1]["alternative_probabilities"] = {"opt_1": 1.0}
    res_c = validate_dual_coder_outputs(normalized_df=norm_df, question_specs=specs, coder_a_payload=pa, coder_b_payload=pb)
    assert res_c.status == "FAIL"
    assert res_c.checks["C_missingness_integrity"] is False

    # [D] Question-wording echo subtopic
    pa, pb = _build_valid_dual_coder_payloads(norm_df, specs)
    qid0 = pa["discovered_subtopics"][0]["question_id"]
    pa["discovered_subtopics"][0]["proposed_label_en"] = specs[qid0].canonical_prompt_en
    res_d = validate_dual_coder_outputs(normalized_df=norm_df, question_specs=specs, coder_a_payload=pa, coder_b_payload=pb)
    assert res_d.status == "FAIL"
    assert res_d.checks["D_subtopic_discovery"] is False

    # [E] Value without supporting span
    pa, pb = _build_valid_dual_coder_payloads(norm_df, specs)
    pa["value_assignments"][0]["evidence_span_ids"] = []
    res_e = validate_dual_coder_outputs(normalized_df=norm_df, question_specs=specs, coder_a_payload=pa, coder_b_payload=pb)
    assert res_e.status == "FAIL"
    assert res_e.checks["E_organisational_values"] is False

    # [F] economic_good_class set on DISABLED question
    pa, pb = _build_valid_dual_coder_payloads(norm_df, specs)
    specs_disabled = dict(specs)
    specs_disabled["Q01"] = dataclasses.replace(specs_disabled["Q01"], economic_good_classification_policy="DISABLED")
    for rec in pa["coding_results"]:
        if rec["question_id"] == "Q01":
            rec["economic_good_class"] = "public_good"
            break
    res_f = validate_dual_coder_outputs(normalized_df=norm_df, question_specs=specs_disabled, coder_a_payload=pa, coder_b_payload=pb)
    assert res_f.status == "FAIL"
    assert res_f.checks["F_goods_classification"] is False

    # [G] Simplex sum != 1.0 & conflated metric
    pa, pb = _build_valid_dual_coder_payloads(norm_df, specs)
    pa["coding_results"][0]["alternative_probabilities"] = {"opt_a": 0.4, "coder_confidence": 0.9}
    res_g = validate_dual_coder_outputs(normalized_df=norm_df, question_specs=specs, coder_a_payload=pa, coder_b_payload=pb)
    assert res_g.status == "FAIL"
    assert res_g.checks["G_quantity_separation"] is False

    # [H] Qwen substitute for Coder B
    pa, pb = _build_valid_dual_coder_payloads(norm_df, specs)
    pb["execution_metadata"]["model_family"] = "qwen"
    pb["execution_metadata"]["model_repo"] = "Qwen/Qwen2.5-32B-Instruct-AWQ"
    res_h = validate_dual_coder_outputs(normalized_df=norm_df, question_specs=specs, coder_a_payload=pa, coder_b_payload=pb)
    assert res_h.status == "FAIL"
    assert res_h.checks["H_model_family_independence"] is False


def test_agent_03_release_gate_transitions_to_ready_only_with_all_13_conditions(tmp_path):
    for subdir in ["src", "docs", "notebooks", "schemas", "tests", "data/raw", "data/normalized", "runs/run_20261111_002"]:
        (tmp_path / subdir).mkdir(parents=True, exist_ok=True)

    shutil.copy2(REPO_ROOT / "AGENTS.md", tmp_path / "AGENTS.md")
    shutil.copy2(REPO_ROOT / "pyproject.toml", tmp_path / "pyproject.toml")
    shutil.copy2(REPO_ROOT / "data" / "raw" / "survey_raw.csv", tmp_path / "data" / "raw" / "survey_raw.csv")
    shutil.copy2(REPO_ROOT / "runs" / "run_20261111_002" / "gpu_runtime_config.json", tmp_path / "runs" / "run_20261111_002" / "gpu_runtime_config.json")
    shutil.copy2(REPO_ROOT / "runs" / "run_20261111_002" / "manifest.json", tmp_path / "runs" / "run_20261111_002" / "manifest.json")

    shutil.copytree(REPO_ROOT / "src", tmp_path / "src", dirs_exist_ok=True)
    shutil.copytree(REPO_ROOT / "docs", tmp_path / "docs", dirs_exist_ok=True)
    shutil.copytree(REPO_ROOT / "notebooks", tmp_path / "notebooks", dirs_exist_ok=True)
    shutil.copytree(REPO_ROOT / "schemas", tmp_path / "schemas", dirs_exist_ok=True)
    shutil.copytree(REPO_ROOT / "tests", tmp_path / "tests", dirs_exist_ok=True)

    df_norm = ingest_survey(
        raw_csv_path=tmp_path / "data" / "raw" / "survey_raw.csv",
        output_parquet=tmp_path / "data" / "normalized" / "answers_normalized.parquet",
        output_json=tmp_path / "data" / "normalized" / "answers_normalized.json",
        run_id="run_20261111_002",
    )
    build_question_registry(
        answers_df_or_path=df_norm,
        raw_csv_path=tmp_path / "data" / "raw" / "survey_raw.csv",
        output_json=tmp_path / "data" / "normalized" / "question_registry.json",
        run_id="run_20261111_002",
    )

    # Write passing 5-stage live GPU benchmark
    bench_path = tmp_path / "runs" / "run_20261111_002" / "gpu_runtime_benchmark.json"
    bench_payload = {
        "run_id": "run_20261111_002",
        "live_gpu_benchmark_status": "EXECUTED_LIVE_GPU",
        "measured_hardware": {"gpu_available": True, "gpu_device_name": "NVIDIA RTX PRO 6000 Blackwell Server Edition"},
        "stages": {
            "1_coder_a_alone": {"schema_valid_output_rate": 1.0},
            "2_coder_b_alone": {"schema_valid_output_rate": 1.0},
            "3_both_servers_resident": {"both_healthy": True},
            "4_simultaneous_structured_request": {"schema_valid_output_rate": 1.0},
            "5_bounded_concurrent_requests": {"schema_valid_output_rate": 1.0},
        },
    }
    bench_path.write_text(json.dumps(bench_payload, indent=2), encoding="utf-8")

    # Write real Coder A & Coder B outputs
    norm_df, specs = _load_norm_and_specs(tmp_path)
    payload_a, payload_b = _build_valid_dual_coder_payloads(norm_df, specs)
    proc_dir = tmp_path / "data" / "processed"
    proc_dir.mkdir(parents=True, exist_ok=True)
    (proc_dir / "coder_a_outputs.json").write_text(json.dumps(payload_a), encoding="utf-8")
    (proc_dir / "coder_b_outputs.json").write_text(json.dumps(payload_b), encoding="utf-8")

    orch = PipelineOrchestrator(base_dir=tmp_path, run_id="run_20261111_002")
    ready_report = orch.evaluate(write_log=True)
    assert ready_report.agent_03_release_decision == Agent03ReleaseDecision.READY
    assert ready_report.highest_verified_state == PipelineState.AGENT_03_RELEASE_READY.value
    assert all(ready_report.agent_03_release_checklist.values())
    assert (tmp_path / "runs" / "run_20261111_002" / "pipeline_execution.log").is_file()

    # Placing smoke_tiny or pilot_subset outputs at canonical paths MUST remain BLOCKED
    for non_prod_profile, synthetic_flag in [("smoke_tiny", True), ("pilot_subset", False)]:
        pa_bad = json.loads(json.dumps(payload_a))
        pb_bad = json.loads(json.dumps(payload_b))
        for p_bad in (pa_bad, pb_bad):
            p_bad["execution_profile"] = non_prod_profile
            p_bad["production_eligible"] = False
            p_bad["synthetic_or_test_execution"] = synthetic_flag
            p_bad["execution_metadata"]["execution_profile"] = non_prod_profile
            p_bad["execution_metadata"]["production_eligible"] = False
            p_bad["execution_metadata"]["synthetic_or_test_execution"] = synthetic_flag
        (proc_dir / "coder_a_outputs.json").write_text(json.dumps(pa_bad), encoding="utf-8")
        (proc_dir / "coder_b_outputs.json").write_text(json.dumps(pb_bad), encoding="utf-8")
        blocked_prof = orch.evaluate(write_log=False)
        assert blocked_prof.agent_03_release_decision == Agent03ReleaseDecision.BLOCKED
        assert blocked_prof.states[PipelineState.CODER_A_COMPLETE.value] is False
        assert blocked_prof.states[PipelineState.CODER_B_COMPLETE.value] is False

    # Missing profile metadata or production_eligible=False or synthetic=True MUST remain BLOCKED
    pa_missing = json.loads(json.dumps(payload_a))
    pa_missing.pop("execution_profile", None)
    pa_missing["execution_metadata"].pop("execution_profile", None)
    (proc_dir / "coder_a_outputs.json").write_text(json.dumps(pa_missing), encoding="utf-8")
    (proc_dir / "coder_b_outputs.json").write_text(json.dumps(payload_b), encoding="utf-8")
    assert orch.evaluate(write_log=False).agent_03_release_decision == Agent03ReleaseDecision.BLOCKED

    # Production payload with missing primary usable coordinate MUST remain BLOCKED
    pa_incomplete = json.loads(json.dumps(payload_a))
    pa_incomplete["coding_results"] = pa_incomplete["coding_results"][1:]
    (proc_dir / "coder_a_outputs.json").write_text(json.dumps(pa_incomplete), encoding="utf-8")
    (proc_dir / "coder_b_outputs.json").write_text(json.dumps(payload_b), encoding="utf-8")
    blocked_incomplete = orch.evaluate(write_log=False)
    assert blocked_incomplete.agent_03_release_decision == Agent03ReleaseDecision.BLOCKED
    assert blocked_incomplete.states[PipelineState.CODER_A_COMPLETE.value] is False

    # Restore valid production payloads before subsequent checks
    (proc_dir / "coder_a_outputs.json").write_text(json.dumps(payload_a), encoding="utf-8")
    (proc_dir / "coder_b_outputs.json").write_text(json.dumps(payload_b), encoding="utf-8")

    # Removing benchmark immediately blocks Agent 03 release
    bench_path.unlink()
    blocked_no_bench = orch.evaluate(write_log=False)
    assert blocked_no_bench.agent_03_release_decision == Agent03ReleaseDecision.BLOCKED
    assert blocked_no_bench.agent_03_release_checklist["4_live_gpu_benchmark_executed"] is False

    # Restoring benchmark and removing Coder B blocks Agent 03 release
    bench_path.write_text(json.dumps(bench_payload, indent=2), encoding="utf-8")
    (proc_dir / "coder_b_outputs.json").unlink()
    blocked_no_coder_b = orch.evaluate(write_log=False)
    assert blocked_no_coder_b.agent_03_release_decision == Agent03ReleaseDecision.BLOCKED
    assert blocked_no_coder_b.states[PipelineState.CODER_A_COMPLETE.value] is True
    assert blocked_no_coder_b.states[PipelineState.CODER_B_COMPLETE.value] is False


@pytest.mark.parametrize("nb_name", ["00_control_plane.ipynb", "04_validation.ipynb"])
def test_agent_11_notebooks_execute_from_notebooks_dir(nb_name):
    nb_path = REPO_ROOT / "notebooks" / nb_name
    assert nb_path.is_file(), f"Missing canonical notebook {nb_path}"
    nb_data = json.loads(nb_path.read_text(encoding="utf-8"))
    code_cells = ["".join(c["source"]) for c in nb_data["cells"] if c["cell_type"] == "code"]
    assert len(code_cells) >= 3

    combined = "\n\n".join(code_cells)
    res = subprocess.run(
        [sys.executable, "-c", combined],
        cwd=str(REPO_ROOT / "notebooks"),
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, f"{nb_name} failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    assert "AGENT_03_RELEASE = BLOCKED" in res.stdout


def test_pipeline_modules_pass_hardcoding_scanner():
    scanner = HardcodingScanner(base_dir=REPO_ROOT)
    hits = scanner.scan_codebase(["src/pipeline", "notebooks/00_control_plane.ipynb", "notebooks/04_validation.ipynb"])
    assert hits == []
