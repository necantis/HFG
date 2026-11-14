"""Agent 04 Production Pipeline Runner, QA Auditor & Task-Local Artifact Descriptor Generator.

Owned by: Agent 04 — Preference, Utility & Pareto
Schema Version: 1.0.0 (Aligned with ADR-0005, ADR-0007, and ADR-0008)

Executes strictly after verifying AGENT_04_RELEASE = READY via PipelineOrchestrator.
Produces task-local outputs under data/processed/ and task-local descriptors in
data/processed/preference/task_local_artifact_descriptors.json (canonical
runs/<run_id>/manifest.json registration remains owned by Agent 11 upon integration).
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.contracts import (
    PROHIBITED_PRUNING_SOURCES,
    RobustParetoStatus,
    SCHEMA_VERSION,
    UncertaintyClass,
)
from src.pipeline.orchestrator import Agent04ReleaseDecision, PipelineOrchestrator
from src.preference.pareto import ParetoAnalyzer, nondominated_mask_exact
from src.preference.preference_matrix import (
    PRIMARY_QUESTION_IDS,
    PreferenceMatrixBuilder,
    compute_sha256,
    get_git_commit_sha,
    load_pareto_mc_config,
    load_preference_matrix,
)
from src.preference.robust_pareto import RobustParetoEngine
from src.preference.solution_space import SolutionSpaceBuilder
from src.preference.utilities import ParticipantUtilityEngine


def run_agent_04_pipeline(
    base_dir: Path | str | None = None,
    run_id: str = "run_20261111_002",
    *,
    enforce_release_gate: bool = True,
) -> dict[str, Any]:
    """Execute the full ADR-0008 Agent 04 preference, utility, and robust Pareto pipeline."""
    t_start = time.time()
    root = (Path(base_dir) if base_dir else Path.cwd()).resolve()

    # ------------------------------------------------------------------
    # 0. Verify AGENT_04_RELEASE = READY (all 9 conditions pass)
    # ------------------------------------------------------------------
    gate_report = None
    if enforce_release_gate:
        gate_report = PipelineOrchestrator(base_dir=root, run_id=run_id).evaluate(write_log=False)
        if gate_report.agent_04_release_decision != Agent04ReleaseDecision.READY:
            raise RuntimeError(
                "AGENT_04_RELEASE = BLOCKED; halting Agent 04 pipeline. Blockers: "
                + "; ".join(gate_report.agent_04_blocking_reasons)
            )
        if not all(gate_report.agent_04_release_checklist.values()):
            raise RuntimeError("Not all 9 Agent 04 release conditions passed.")

    # ------------------------------------------------------------------
    # 1. Load configurable Pareto MC parameters & verify upstream manifest
    # ------------------------------------------------------------------
    mc_config, mc_rel_path, mc_sha = load_pareto_mc_config(root, run_id=run_id)
    pm_builder = PreferenceMatrixBuilder(root, run_id=run_id)
    upstream_manifest = pm_builder.verify_upstream_manifest()

    # ------------------------------------------------------------------
    # 2. Construct & validate PreferenceMatrix (Parquet + JSON round-trip)
    # ------------------------------------------------------------------
    matrix, cell_diags = pm_builder.build(
        simplex_tolerance=float(mc_config.get("simplex_tolerance", 1e-4)),
        config_hash=mc_sha,
        verify_manifest=enforce_release_gate,
    )
    pm_paths = pm_builder.save(matrix, cell_diags)
    roundtrip_matrix = load_preference_matrix(pm_paths["parquet"])
    if len(roundtrip_matrix.cells) != len(matrix.cells):
        raise ValueError("PreferenceMatrix Parquet round-trip cell count mismatch.")

    # ------------------------------------------------------------------
    # 3. Dynamic constraint-only FeasibleAlternative & GovernanceSolution
    # ------------------------------------------------------------------
    sol_builder = SolutionSpaceBuilder(root, run_id=run_id)
    sol_summary = sol_builder.build(matrix, config_hash=mc_sha)
    sol_path = sol_builder.save(sol_summary)

    # ------------------------------------------------------------------
    # 4. ParticipantUtility propagation (ADR-0008 + ISSUE-005)
    # ------------------------------------------------------------------
    util_engine = ParticipantUtilityEngine(root, run_id=run_id)
    util_summary = util_engine.evaluate(
        matrix=matrix,
        solutions=sol_summary.governance_solutions,
        mc_config=mc_config,
        config_hash=mc_sha,
    )
    util_path = util_engine.save(util_summary)

    # ------------------------------------------------------------------
    # 5. Exact Participant-Level Pareto & Sensitivity Weighting Reference
    # ------------------------------------------------------------------
    pareto_analyzer = ParetoAnalyzer(root, run_id=run_id)
    base_pareto = pareto_analyzer.evaluate(
        matrix_id=matrix.matrix_id,
        solution_ids=util_summary.solution_ids,
        valid_participant_ids=util_summary.valid_participant_ids,
        excluded_all_missing_participant_ids=util_summary.excluded_all_missing_participant_ids,
        utility_matrix=util_summary.expected_utility_matrix,
        mc_config=mc_config,
        config_hash=mc_sha,
    )
    # Exact check vs baseline skyline parity
    exact_mask = nondominated_mask_exact(
        util_summary.expected_utility_matrix,
        tol=float(mc_config.get("dominance_tolerance", 1e-9)),
    )
    sens_meta = {
        "uniform_subtopic_frontier_count": int(
            nondominated_mask_exact(
                util_summary.uniform_subtopic_utility_matrix,
                tol=float(mc_config.get("dominance_tolerance", 1e-9)),
            ).sum()
        ),
        "uniform_question_frontier_count": int(
            nondominated_mask_exact(
                util_summary.uniform_question_utility_matrix,
                tol=float(mc_config.get("dominance_tolerance", 1e-9)),
            ).sum()
        ),
    }
    pareto_path = pareto_analyzer.save(base_pareto, extra_metadata=sens_meta)

    # ------------------------------------------------------------------
    # 6. RobustParetoResult (4 mutually exclusive ADR-0008 statuses)
    # ------------------------------------------------------------------
    robust_engine = RobustParetoEngine(root, run_id=run_id)
    robust_res, sens_bundle = robust_engine.evaluate(
        base_pareto=base_pareto,
        utility_summary=util_summary,
        solutions=sol_summary.governance_solutions,
        mc_config=mc_config,
        pareto_mc_config_rel_path=mc_rel_path,
        config_hash=mc_sha,
    )
    robust_paths = robust_engine.save(robust_res, sens_bundle, util_summary)

    # ------------------------------------------------------------------
    # 7. Preference Uncertainty Summary & Machine-Checkable QA Audit
    # ------------------------------------------------------------------
    pref_dir = root / "data" / "processed" / "preference"
    unc_summary_path = pref_dir / "preference_uncertainty_summary.json"
    qa_path = pref_dir / "agent_04_qa_report.json"

    primary_cells = [c for c in matrix.cells if c.question_id in PRIMARY_QUESTION_IDS]
    contextual_cells = [c for c in matrix.cells if c.question_id not in PRIMARY_QUESTION_IDS]
    non_consensus_with_point = [
        c.cell_id
        for c in matrix.cells
        if c.uncertainty_class != UncertaintyClass.NONE_CONSENSUS and c.resolved_point_distribution is not None
    ]
    missing_with_probs = [
        c.cell_id
        for c in matrix.cells
        if (not c.missingness_state.is_usable()) and (c.alternative_probabilities or c.resolved_point_distribution)
    ]
    single_coder_zero_fills = [
        c.cell_id
        for c in matrix.cells
        if c.uncertainty_class
        in (
            UncertaintyClass.SINGLE_CODER_PARTIAL_ID_OMISSION,
            UncertaintyClass.SINGLE_CODER_PARTIAL_ID_GRANULARITY,
        )
        and (
            (c.coder_a_distribution is not None and c.coder_b_distribution is not None)
            or (
                c.preference_uncertainty_set is not None
                and c.preference_uncertainty_set.non_coding_coder_state != "EPISTEMICALLY_UNOBSERVED"
            )
        )
    ]
    uses_conf_weight = [u.utility_id for u in util_summary.participant_utilities if u.uses_coder_confidence_as_weight]
    prohibited_sol_pruning = [
        s.solution_id
        for s in (sol_summary.governance_solutions + sol_summary.pruned_solutions)
        if s.pruned_by_clusters_or_values
        or s.pruned_by_coder_disagreement
        or s.pruned_by_coder_confidence
        or (set(s.pruning_sources_applied) & PROHIBITED_PRUNING_SOURCES)
    ]
    q14_in_solutions = [
        s.solution_id
        for s in sol_summary.governance_solutions
        if "Q14" in s.included_question_ids or "Q14" in s.question_alternatives
    ]
    bucket_sum = sum(sens_bundle["status_counts"].values())
    all_assigned_once = (
        bucket_sum == len(sol_summary.governance_solutions)
        and len(robust_res.solution_robustness_statuses) == len(sol_summary.governance_solutions)
    )

    unc_summary = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "total_cells": len(matrix.cells),
        "primary_q01_q13_cells": len(primary_cells),
        "contextual_q14_cells": len(contextual_cells),
        "uncertainty_class_counts_all": matrix.uncertainty_class_counts,
        "uncertainty_class_counts_primary": {
            uc.value: sum(1 for c in primary_cells if c.uncertainty_class == uc)
            for uc in UncertaintyClass
        },
        "double_count_guard_true_count": sum(
            1 for c in matrix.cells if c.preference_uncertainty_set and c.preference_uncertainty_set.double_count_guard_applied
        ),
        "interpretation_operator_audit": util_summary.interpretation_operator_audit,
        "robust_pareto_status_counts": sens_bundle["status_counts"],
        "derived_scenario_origins_used": [o.value for o in robust_res.derived_scenario_origins_used],
    }
    unc_summary_path.write_text(json.dumps(unc_summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    qa_checks = {
        "1_release_gate_ready_9_of_9": True if not enforce_release_gate else all(gate_report.agent_04_release_checklist.values()),
        "2_all_cells_simplex_validated": matrix.validation_passed and len(matrix.cells) == len(roundtrip_matrix.cells),
        "3_no_unauthorized_point_collapse": len(non_consensus_with_point) == 0,
        "4_strict_missingness_preserved": len(missing_with_probs) == 0,
        "5_single_coder_zero_fill_absent": len(single_coder_zero_fills) == 0,
        "6_zero_coder_confidence_weighting": len(uses_conf_weight) == 0,
        "7_constraint_only_pruning_enforced": len(prohibited_sol_pruning) == 0,
        "8_q01_q13_primary_spine_and_q14_isolated": len(q14_in_solutions) == 0 and all(
            len(s.included_question_ids) == 13 for s in sol_summary.governance_solutions
        ),
        "9_four_state_robust_pareto_mutually_exclusive_exhaustive": all_assigned_once and robust_res.validate_invariants(),
        "10_baseline_skyline_matches_exact": len(base_pareto.nondominated_solution_ids) == int(exact_mask.sum()),
        "11_participants_not_ranked": all(
            not d.get("ranked_as_participant", True) for d in util_summary.participant_diagnostics.values()
        ),
    }
    qa_report = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
        "all_qa_checks_passed": all(qa_checks.values()),
        "qa_checks": qa_checks,
        "execution_duration_seconds": round(time.time() - t_start, 3),
        "counts_summary": {
            "preference_cells": len(matrix.cells),
            "feasible_alternatives": len(sol_summary.feasible_alternatives),
            "feasible_solutions": len(sol_summary.governance_solutions),
            "constraint_pruned_solutions": len(sol_summary.pruned_solutions),
            "participant_utility_records": len(util_summary.participant_utilities),
            "baseline_nondominated_count": len(base_pareto.nondominated_solution_ids),
            "robust_pareto_status_counts": sens_bundle["status_counts"],
        },
    }
    qa_path.write_text(json.dumps(qa_report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if not qa_report["all_qa_checks_passed"]:
        raise RuntimeError(f"Agent 04 QA invariant check failed: {qa_checks}")

    # ------------------------------------------------------------------
    # 8. Task-Local Artifact Descriptors (ADR-0007 §11 compliant)
    # ------------------------------------------------------------------
    commit_sha = get_git_commit_sha(root)
    src_hashes = {
        "pareto_mc_config_v1": mc_sha,
        **{
            aid: meta["sha256"]
            for aid, meta in upstream_manifest.get("verified_inputs", {}).items()
        },
    }
    if not src_hashes.get("reconciled_evidence_v1"):
        rec_p = root / "data" / "processed" / "reconciliation" / "reconciled_evidence.json"
        if rec_p.is_file():
            src_hashes["reconciled_evidence_v1"] = compute_sha256(rec_p)

    artifact_specs = [
        ("preference_matrix_v1", pm_paths["parquet"], "src/preference/preference_matrix.py", len(matrix.cells), ["agent_05", "agent_06", "agent_08", "agent_09"]),
        ("preference_matrix_json_v1", pm_paths["json"], "src/preference/preference_matrix.py", len(matrix.cells), ["agent_05", "agent_08", "agent_09"]),
        ("pareto_mc_config_v1", root / mc_rel_path, "runs/pareto_mc_config", 1, ["agent_04", "agent_09", "agent_11"]),
        ("feasible_alternatives_v1", sol_path, "src/preference/solution_space.py", len(sol_summary.governance_solutions), ["agent_06", "agent_08", "agent_09"]),
        ("participant_utility_v1", util_path, "src/preference/utilities.py", len(util_summary.participant_utilities), ["agent_06", "agent_08", "agent_09"]),
        ("pareto_results_v1", pareto_path, "src/preference/pareto.py", len(base_pareto.evaluated_solution_ids), ["agent_06", "agent_08", "agent_09"]),
        ("robust_pareto_results_v1", robust_paths["robust_pareto"], "src/preference/robust_pareto.py", len(sol_summary.governance_solutions), ["agent_08", "agent_09"]),
        ("pareto_sensitivity_v1", robust_paths["pareto_sensitivity"], "src/preference/robust_pareto.py", len(sens_bundle["pareto_explanations"]), ["agent_08", "agent_09"]),
        ("preference_uncertainty_summary_v1", unc_summary_path, "src/preference/pipeline.py", len(matrix.cells), ["agent_05", "agent_08", "agent_09"]),
        ("agent_04_qa_report_v1", qa_path, "src/preference/pipeline.py", len(qa_checks), ["agent_09", "agent_11"]),
    ]

    descriptors: dict[str, Any] = {}
    for aid, fpath, prod_mod, rec_cnt, consumers in artifact_specs:
        rel = str(fpath.relative_to(root))
        is_cfg = aid == "pareto_mc_config_v1"
        descriptors[aid] = {
            "artifact_id": aid,
            "run_id": run_id,
            "scope": "git_versioned_config" if is_cfg else "task_local_pending_integration_registration",
            "path": rel,
            "sha256": compute_sha256(fpath),
            "byte_size": fpath.stat().st_size,
            "record_count": rec_cnt,
            "schema_version": SCHEMA_VERSION,
            "producing_agent": "agent_04",
            "producing_module": prod_mod,
            "code_commit": commit_sha,
            "source_hashes": src_hashes,
            "validation_status": "valid",
            "privacy_status": "public_config_only" if is_cfg else "private_runtime_artifact_uncommitted",
            "downstream_consumers": consumers,
        }

    desc_path = pref_dir / "task_local_artifact_descriptors.json"
    desc_payload = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "registration_policy": (
            "Task-local artifact descriptors produced by Agent 04. Canonical runs/<run_id>/manifest.json "
            "registration is performed exclusively by Agent 11 after PR review and merge per ADR-0007."
        ),
        "downstream_release_decision": {
            "agent_05_preference_profiles_unblocked": True,
            "agent_06_voting_social_choice_unblocked": True,
            "agent_08_reporting_prerequisite_status": "REQUIRES_AGENT_05_06_COMPLETION",
        },
        "descriptors": descriptors,
    }
    desc_path.write_text(json.dumps(desc_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    return {
        "run_id": run_id,
        "execution_duration_seconds": qa_report["execution_duration_seconds"],
        "matrix_id": matrix.matrix_id,
        "counts": qa_report["counts_summary"],
        "uncertainty_class_counts": matrix.uncertainty_class_counts,
        "qa_report": qa_report,
        "status_counts": sens_bundle["status_counts"],
        "high_confidence_nondominated_count": sens_bundle["high_confidence_nondominated_count"],
        "robust_frontier_solution_ids": robust_res.robust_frontier_solution_ids,
        "baseline_nondominated_ids": base_pareto.nondominated_solution_ids,
        "top_rankings_expected": {
            k: v[:5] for k, v in base_pareto.rankings_by_criterion.items()
        },
        "descriptor_index_path": str(desc_path.relative_to(root)),
        "descriptors": descriptors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Agent 04 ADR-0008 Preference, Utility & Robust Pareto Pipeline")
    parser.add_argument("--run-id", default="run_20261111_002")
    parser.add_argument("--base-dir", default=None)
    args = parser.parse_args()
    summary = run_agent_04_pipeline(base_dir=args.base_dir, run_id=args.run_id, enforce_release_gate=True)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
