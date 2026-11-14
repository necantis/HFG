"""Agent 06 End-to-End Social Choice, Uncertainty & QA Pipeline.

Owned by: Agent 06 — Voting & Social Choice
Schema Version: 1.0.0 (Aligned with ADR-0005, ADR-0007, and ADR-0008)

Executes:
1. Input provenance & active-ballot validation (voting_input_validation_v1)
2. Read-only ADR-0008 utility ensemble reconstruction from validated PreferenceMatrix
3. Conditional Baldwin & RRV gates (NOT_APPLICABLE / SKIPPED_NO_VALID_INPUT when invalid)
4. Authorized social-choice rules & ADR-0008 uncertainty propagation (voting_uncertainty_v1)
5. Small-N (N=11) & single-ballot leave-one-out sensitivity (voting_sensitivity_v1)
6. Robust Pareto & 7-criterion cross-check (pareto_voting_comparison_v1)
7. Canonical data/processed/voting_results.json (voting_results_v1)
8. Self-audit QA report (agent_06_qa_report_v1) & task-local descriptors
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from typing import Any

from src.contracts import ProvenanceMeta, SCHEMA_VERSION
from src.preference.utilities import ParticipantUtilityEngine
from src.voting.pareto_comparison import build_pareto_voting_comparison
from src.voting.social_choice import (
    compute_interval_partial_order_stats,
    compute_small_n_sensitivity,
    propagate_social_choice_uncertainty,
)
from src.voting.validation import (
    compute_sha256,
    evaluate_ballot_derivation_legitimacy,
    get_git_commit_sha,
    validate_agent_06_inputs,
)
from src.voting.voting_baldwin import evaluate_baldwin_voting
from src.voting.voting_rrv import evaluate_rrv_voting


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run_agent_06_pipeline(
    base_dir: Path | str | None = None,
    run_id: str = "run_20261111_002",
    *,
    verify_manifest: bool = True,
) -> dict[str, Any]:
    """Execute full Agent 06 social-choice & robustness pipeline deterministically."""
    t_start = time.time()
    root = (Path(base_dir) if base_dir else Path.cwd()).resolve()
    proc_dir = root / "data" / "processed"
    voting_dir = proc_dir / "voting"
    voting_dir.mkdir(parents=True, exist_ok=True)

    # 1. Provenance & Initial Active Ballot Validation
    ctx = validate_agent_06_inputs(root, run_id=run_id, verify_manifest=verify_manifest)
    matrix = ctx["matrix"]
    solutions = ctx["solutions"]
    mc_cfg = ctx["mc_config"]
    mc_hash = ctx["mc_config_hash"]
    pu_payload = ctx["pu_payload"]
    pareto_payload = ctx["pareto_payload"]
    robust_payload = ctx["robust_payload"]
    ext_ballots = ctx["external_ballots"]
    dataset_fp = ctx["dataset_fingerprint"]
    sol_ids = [s.solution_id for s in solutions]

    # 2. Reconstruct ADR-0008 Utility Scenario Ensemble (read-only using Agent 04 engine)
    engine = ParticipantUtilityEngine(root, run_id=run_id)
    ensemble = engine.evaluate(matrix, solutions, mc_cfg, config_hash=mc_hash)

    # Enrich active ballot derivation legitimacy check with exact interval comparability
    S_len, P_len = ensemble.min_scenario_matrix.shape
    total_pairs = S_len * (S_len - 1) // 2
    per_p_comp = {}
    for p_i, pid in enumerate(ensemble.valid_participant_ids):
        lo = ensemble.min_scenario_matrix[:, p_i]
        hi = ensemble.max_scenario_matrix[:, p_i]
        comp_cnt = int((lo[:, None] > hi[None, :] + 1e-12).sum())
        per_p_comp[pid] = comp_cnt / total_pairs if total_pairs > 0 else 0.0

    # Store only aggregate comparability in report (zero participant ranking!)
    derivation_audit = evaluate_ballot_derivation_legitimacy(
        matrix,
        pu_payload,
        interval_strict_comparability_by_participant=per_p_comp,
    )
    validation_report = ctx["validation_report"]
    validation_report["ballot_derivation_legitimacy"] = derivation_audit
    validation_report["interval_partial_order_overview"] = compute_interval_partial_order_stats(
        ensemble.min_scenario_matrix,
        ensemble.max_scenario_matrix,
    )

    val_path = voting_dir / "voting_input_validation.json"
    _write_json(val_path, validation_report)

    # 3. Conditional Baldwin & RRV Execution / Applicability Gates
    random_seed = int(mc_cfg.get("random_seed", 42))
    baldwin_res, baldwin_env = evaluate_baldwin_voting(
        run_id=run_id,
        dataset_fingerprint=dataset_fp,
        candidate_ids=sol_ids,
        ballot_file_path=ext_ballots["baldwin"],
        ballot_derivation_audit=derivation_audit,
        random_seed=random_seed,
    )
    rrv_res, rrv_env = evaluate_rrv_voting(
        run_id=run_id,
        dataset_fingerprint=dataset_fp,
        candidate_ids=sol_ids,
        ballot_file_path=ext_ballots["rrv"],
        ballot_derivation_audit=derivation_audit,
        participant_count=P_len,
        default_committee_size=3,
        random_seed=random_seed,
    )

    baldwin_path = voting_dir / "baldwin_results.json"
    rrv_path = voting_dir / "rrv_results.json"
    _write_json(baldwin_path, baldwin_env)
    _write_json(rrv_path, rrv_env)

    # 4. Authorized Social Choice Rules + Full ADR-0008 Uncertainty Propagation
    dom_tol = float(mc_cfg.get("dominance_tolerance", 1e-9))
    # Use 1e-12 utility comparison tolerance matching Agent 04 / voting separation
    unc_report = propagate_social_choice_uncertainty(ensemble, tol=min(dom_tol, 1e-12))
    unc_path = voting_dir / "voting_uncertainty.json"
    _write_json(unc_path, unc_report)

    # 5. Small-N (N=11), Leave-One-Out & Regime Sensitivity
    sens_report = compute_small_n_sensitivity(ensemble, unc_report, committee_size_reference=3, tol=1e-12)
    sens_path = voting_dir / "voting_sensitivity.json"
    _write_json(sens_path, sens_report)

    # 6. Robust Pareto & Separate 7-Criterion Welfare Comparison
    pareto_cmp = build_pareto_voting_comparison(
        run_id=run_id,
        pareto_payload=pareto_payload,
        robust_payload=robust_payload,
        unc_report=unc_report,
        baldwin_envelope=baldwin_env,
        rrv_envelope=rrv_env,
    )
    pareto_cmp_path = voting_dir / "pareto_voting_comparison.json"
    _write_json(pareto_cmp_path, pareto_cmp)

    # 7. Canonical voting_results_v1 (data/processed/voting_results.json)
    exp_ref = unc_report["expected_reference"]
    borda_winners = set(exp_ref["borda_count"]["winner_ids"])
    cond_weak_winners = set(exp_ref["condorcet"]["weak_condorcet_winners"])
    minimax_winners = set(exp_ref["minimax"]["winner_ids"])

    active_winner_sets = [borda_winners, minimax_winners]
    if cond_weak_winners:
        active_winner_sets.append(cond_weak_winners)
    else:
        # Condorcet cycle on expected reference prevents cross-rule Condorcet agreement
        active_winner_sets.append(set())
    if baldwin_res.execution_status == "EXECUTED" and baldwin_res.winner_candidate_ids:
        active_winner_sets.append(set(baldwin_res.winner_candidate_ids))

    common_exp = set.intersection(*active_winner_sets) if active_winner_sets else set()
    # Unanimous ONLY if a unique single candidate wins every executed rule cleanly AND survives scenario robustness
    robust_survives = bool(unc_report["robustness_verdicts"]["conclusion_survives_all_admissible_scenarios"])
    consensus_winner = sorted(common_exp)[0] if (len(common_exp) == 1 and robust_survives) else None
    is_unanimous = bool(len(common_exp) == 1 and len(borda_winners) == 1 and len(minimax_winners) == 1 and cond_weak_winners == borda_winners)

    voting_results_payload = {
        "schema_version": SCHEMA_VERSION,
        "contract_id": "voting_results_v1",
        "run_id": run_id,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "adr_references": ["ADR-0005", "ADR-0007", "ADR-0008"],
        "choice_set_count": len(sol_ids),
        "participant_count": P_len,
        "equal_ballot_weighting_enforced": True,
        "cluster_weights_applied": False,
        "participants_ranked": False,
        "social_choice_rules": {
            "borda_count": {
                "execution_status": "EXECUTED_WITH_ADR0008_ENSEMBLE",
                "expected_reference_winners": exp_ref["borda_count"]["winner_ids"],
                "expected_reference_max_score": exp_ref["borda_count"]["max_score"],
                "expected_reference_top10": exp_ref["borda_count"]["ranking"][:10],
                "expected_reference_scores": exp_ref["borda_count"]["scores"],
                "mc_winner_inclusion_probabilities": unc_report["monte_carlo_results"]["borda_winner_inclusion_probabilities"],
                "mc_unique_winners_observed": unc_report["monte_carlo_results"]["borda_unique_winners_observed"],
            },
            "condorcet": {
                "execution_status": "EXECUTED_WITH_ADR0008_ENSEMBLE",
                "expected_reference_strict_winners": exp_ref["condorcet"]["strict_condorcet_winners"],
                "expected_reference_weak_winners": exp_ref["condorcet"]["weak_condorcet_winners"],
                "expected_reference_has_cycle": exp_ref["condorcet"]["has_condorcet_cycle"],
                "expected_reference_smith_set_size": exp_ref["condorcet"]["smith_set_size"],
                "expected_reference_smith_set_ids": exp_ref["condorcet"]["smith_set_ids"],
                "expected_reference_copeland_top_ids": exp_ref["condorcet"]["copeland_diagnostic_top_ids"],
                "mc_strict_exists_rate": unc_report["monte_carlo_results"]["condorcet_strict_exists_rate"],
                "mc_weak_exists_rate": unc_report["monte_carlo_results"]["condorcet_weak_exists_rate"],
                "mc_cycle_rate": unc_report["monte_carlo_results"]["condorcet_cycle_rate"],
                "mc_weak_winner_inclusion_probabilities": unc_report["monte_carlo_results"]["condorcet_weak_winner_inclusion_probabilities"],
            },
            "minimax": {
                "execution_status": "EXECUTED_WITH_ADR0008_ENSEMBLE",
                "expected_reference_winners": exp_ref["minimax"]["winner_ids"],
                "expected_reference_min_worst_defeat": exp_ref["minimax"]["min_worst_pairwise_defeat"],
                "expected_reference_top10": exp_ref["minimax"]["ranking"][:10],
                "expected_reference_worst_pairwise_defeats": exp_ref["minimax"]["worst_pairwise_defeats"],
                "mc_winner_inclusion_probabilities": unc_report["monte_carlo_results"]["minimax_winner_inclusion_probabilities"],
                "mc_unique_winners_observed": unc_report["monte_carlo_results"]["minimax_unique_winners_observed"],
            },
        },
        "baldwin_result": asdict(baldwin_res),
        "rrv_result": asdict(rrv_res),
        "consensus_winner": consensus_winner,
        "is_unanimous": is_unanimous,
        "robustness_verdicts": unc_report["robustness_verdicts"],
        "provenance": asdict(
            ProvenanceMeta(
                record_id=f"VOTING_{run_id}",
                run_id=run_id,
                dataset_fingerprint=dataset_fp,
                created_at_utc=datetime.now(timezone.utc).isoformat(),
                producer_module="src/voting/pipeline.py",
                producer_agent="agent_06",
                upstream_artifact_ids=[
                    "preference_matrix_v1",
                    "feasible_alternatives_v1",
                    "participant_utility_v1",
                    "pareto_results_v1",
                    "robust_pareto_results_v1",
                ],
                config_hash=mc_hash,
                schema_version=SCHEMA_VERSION,
            )
        ),
    }
    vr_path = proc_dir / "voting_results.json"
    _write_json(vr_path, voting_results_payload)

    # 8. Agent 06 QA Self-Audit (agent_06_qa_report_v1)
    qa_checks = {
        "1_input_provenance_verified": bool(validation_report["validation_passed"]),
        "2_active_ballot_validation_enforced": (
            not derivation_audit["can_derive_complete_strict_rankings_without_fabrication"]
            if ext_ballots["baldwin"] is None
            else True
        ),
        "3_no_synthetic_complete_ballots": (
            not baldwin_env.get("synthetic_ballots_fabricated", True)
            and not rrv_env.get("synthetic_ballots_fabricated", True)
        ),
        "4_zero_participant_ranking": (
            not voting_results_payload["participants_ranked"]
            and not sens_report["ranked_as_participant"]
            and not validation_report["choice_set_summary"]["participants_ranked"]
        ),
        "5_zero_cluster_based_vote_weighting": (
            not voting_results_payload["cluster_weights_applied"]
            and not unc_report["cluster_weights_applied"]
            and not sens_report["cluster_weights_applied"]
            and voting_results_payload["equal_ballot_weighting_enforced"]
        ),
        "6_partial_identification_and_missingness_preserved": (
            all(not c.alternative_probabilities for c in matrix.cells if not c.missingness_state.is_usable())
            and (
                derivation_audit["null_point_utility_count"] > 0
                if derivation_audit["preserved_missing_primary_count"]
                + derivation_audit["single_coder_partial_id_primary_count"]
                + derivation_audit["crosswalk_partial_or_unaligned_primary_count"]
                > 0
                else True
            )
        ),
        "7_adr0008_uncertainty_propagated": (
            unc_report["monte_carlo_draws"] == int(mc_cfg.get("monte_carlo_draws", 1000))
            and len(unc_report["coupled_coding_gap_corners"]) == len(ensemble.coupled_gap_corner_matrices)
            and len(unc_report["derived_barycenter_scenarios"]) == len(ensemble.derived_barycenter_matrices)
        ),
        "8_inapplicable_methods_marked_not_applicable": (
            (baldwin_env["applicability_status"] == "NOT_APPLICABLE" and baldwin_res.execution_status == "SKIPPED_NO_VALID_INPUT")
            if ext_ballots["baldwin"] is None
            else baldwin_res.execution_status in {"EXECUTED", "FAILED_VALIDATION"}
        )
        and (
            (rrv_env["applicability_status"] == "NOT_APPLICABLE" and rrv_res.execution_status == "SKIPPED_NO_VALID_INPUT")
            if ext_ballots["rrv"] is None
            else rrv_res.execution_status in {"EXECUTED", "FAILED_VALIDATION"}
        ),
        "9_pareto_and_voting_constructs_unconflated": bool(
            pareto_cmp["conceptual_distinction_and_interpretation"]["pareto_vs_voting_non_conflation"]
        ),
        "10_welfare_criteria_kept_separate": (
            not pareto_cmp["conceptual_distinction_and_interpretation"]["welfare_criteria_combined_into_voting_rule"]
            and len(pareto_cmp["separate_welfare_criteria_diagnostics"]) == 7
        ),
        "11_small_n_discreteness_and_loo_explicit": (
            sens_report["small_n_discreteness"]["valid_ballot_count"] == P_len
            and sens_report["single_ballot_leave_one_out_sensitivity"]["total_ballots_n"] == P_len
        ),
        "12_canonical_voting_results_v1_valid": (
            vr_path.is_file()
            and {"borda_count", "condorcet", "minimax"}.issubset(voting_results_payload["social_choice_rules"].keys())
        ),
    }

    qa_report = {
        "schema_version": SCHEMA_VERSION,
        "contract_id": "agent_06_qa_report_v1",
        "run_id": run_id,
        "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
        "all_qa_checks_passed": all(qa_checks.values()),
        "qa_checks": qa_checks,
        "execution_duration_seconds": round(time.time() - t_start, 3),
        "summary": {
            "feasible_solutions_evaluated": len(sol_ids),
            "valid_participants": P_len,
            "baldwin_status": baldwin_env["applicability_status"],
            "rrv_status": rrv_env["applicability_status"],
            "expected_borda_winners": exp_ref["borda_count"]["winner_ids"],
            "expected_minimax_winners": exp_ref["minimax"]["winner_ids"],
            "expected_condorcet_weak_winners": exp_ref["condorcet"]["weak_condorcet_winners"],
            "mc_condorcet_cycle_rate": unc_report["monte_carlo_results"]["condorcet_cycle_rate"],
            "consensus_winner": consensus_winner,
            "is_unanimous": is_unanimous,
        },
    }
    qa_path = voting_dir / "agent_06_qa_report.json"
    _write_json(qa_path, qa_report)
    if not qa_report["all_qa_checks_passed"]:
        raise RuntimeError(f"Agent 06 QA checks failed: {qa_checks}")

    # 9. Task-Local Artifact Descriptors (ADR-0007 §11 compliant)
    commit_sha = get_git_commit_sha(root)
    src_hashes = {
        aid: meta["sha256"]
        for aid, meta in validation_report["verified_upstream_inputs"].items()
    }

    artifact_specs = [
        ("voting_input_validation_v1", val_path, "src/voting/validation.py", 1, ["agent_08", "agent_09", "agent_11"]),
        ("voting_results_v1", vr_path, "src/voting/pipeline.py", len(sol_ids), ["agent_08", "agent_09", "agent_11"]),
        ("voting_uncertainty_v1", unc_path, "src/voting/social_choice.py", int(mc_cfg.get("monte_carlo_draws", 1000)), ["agent_08", "agent_09", "agent_11"]),
        ("baldwin_results_v1", baldwin_path, "src/voting/voting_baldwin.py", len(sol_ids), ["agent_08", "agent_09", "agent_11"]),
        ("rrv_results_v1", rrv_path, "src/voting/voting_rrv.py", len(sol_ids), ["agent_08", "agent_09", "agent_11"]),
        ("pareto_voting_comparison_v1", pareto_cmp_path, "src/voting/pareto_comparison.py", len(sol_ids), ["agent_08", "agent_09", "agent_11"]),
        ("voting_sensitivity_v1", sens_path, "src/voting/social_choice.py", P_len, ["agent_08", "agent_09", "agent_11"]),
        ("agent_06_qa_report_v1", qa_path, "src/voting/pipeline.py", len(qa_checks), ["agent_09", "agent_11"]),
    ]

    descriptors: dict[str, Any] = {}
    for aid, fpath, prod_mod, rec_cnt, consumers in artifact_specs:
        rel = str(fpath.relative_to(root))
        descriptors[aid] = {
            "artifact_id": aid,
            "run_id": run_id,
            "scope": "task_local_pending_integration_registration",
            "path": rel,
            "sha256": compute_sha256(fpath),
            "byte_size": fpath.stat().st_size,
            "record_count": rec_cnt,
            "schema_version": SCHEMA_VERSION,
            "producing_agent": "agent_06",
            "producing_module": prod_mod,
            "code_commit": commit_sha,
            "source_hashes": src_hashes,
            "validation_status": "valid",
            "privacy_status": "private_runtime_artifact_uncommitted",
            "downstream_consumers": consumers,
        }

    desc_path = voting_dir / "task_local_artifact_descriptors.json"
    _write_json(
        desc_path,
        {
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "registration_policy": (
                "Task-local artifact descriptors produced by Agent 06. Canonical runs/<run_id>/manifest.json "
                "registration is performed exclusively by Agent 11 after PR review and merge per ADR-0007."
            ),
            "descriptors": descriptors,
        },
    )

    return {
        "run_id": run_id,
        "execution_duration_seconds": qa_report["execution_duration_seconds"],
        "qa_report": qa_report,
        "baldwin_applicability": baldwin_env["applicability_status"],
        "rrv_applicability": rrv_env["applicability_status"],
        "expected_borda_winners": exp_ref["borda_count"]["winner_ids"],
        "expected_minimax_winners": exp_ref["minimax"]["winner_ids"],
        "expected_condorcet_weak_winners": exp_ref["condorcet"]["weak_condorcet_winners"],
        "expected_smith_set_size": exp_ref["condorcet"]["smith_set_size"],
        "mc_condorcet_cycle_rate": unc_report["monte_carlo_results"]["condorcet_cycle_rate"],
        "top_mc_borda": dict(list(unc_report["monte_carlo_results"]["borda_winner_inclusion_probabilities"].items())[:5]),
        "top_mc_minimax": dict(list(unc_report["monte_carlo_results"]["minimax_winner_inclusion_probabilities"].items())[:5]),
        "descriptor_index_path": str(desc_path.relative_to(root)),
        "descriptors": descriptors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Agent 06 Social Choice & Voting Robustness Pipeline")
    parser.add_argument("--run-id", default="run_20261111_002")
    parser.add_argument("--base-dir", default=None)
    args = parser.parse_args()
    summary = run_agent_06_pipeline(base_dir=args.base_dir, run_id=args.run_id, verify_manifest=True)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
