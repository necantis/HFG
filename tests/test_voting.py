"""Tests for Agent 06 Social Choice, Voting & Collective-Choice Robustness."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from src.contracts import (
    AgreementStatus,
    CanonicalAlternativeCrosswalk,
    CrosswalkStatus,
    GovernanceSolution,
    MissingnessState,
    PreferenceCell,
    PreferenceMatrix,
    PreferenceUncertaintySet,
    ProvenanceMeta,
    ReconciliationStatus,
    SCHEMA_VERSION,
    UncertaintyClass,
    UncertaintyRepresentationType,
)
from src.preference.pareto import ParetoAnalyzer
from src.preference.preference_matrix import PreferenceMatrixBuilder
from src.preference.robust_pareto import RobustParetoEngine
from src.preference.utilities import ParticipantUtilityEngine, UtilityEnsembleSummary
from src.voting.pareto_comparison import build_pareto_voting_comparison
from src.voting.pipeline import run_agent_06_pipeline
from src.voting.social_choice import (
    compute_borda_scores,
    compute_condorcet_minimax_metrics,
    compute_interval_partial_order_stats,
    compute_small_n_sensitivity,
    propagate_social_choice_uncertainty,
)
from src.voting.validation import evaluate_ballot_derivation_legitimacy
from src.voting.voting_baldwin import (
    evaluate_baldwin_voting,
    execute_baldwin_from_ballots,
    validate_baldwin_ballot_file,
)
from src.voting.voting_rrv import (
    evaluate_rrv_voting,
    execute_rrv_from_ballots,
    small_n_quota_diagnostics,
    validate_rrv_ballot_file,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def _prov(rec_id: str, run_id: str = "run_test") -> ProvenanceMeta:
    return ProvenanceMeta(
        record_id=rec_id,
        run_id=run_id,
        dataset_fingerprint="fp_test",
        created_at_utc="2026-11-14T00:00:00+00:00",
        producer_module="tests/test_voting.py",
        producer_agent="agent_06",
    )


def _sol(sid: str, q05_opt: str = "scenario_1") -> GovernanceSolution:
    return GovernanceSolution(
        solution_id=sid,
        label_en=sid,
        question_alternatives={"Q05": q05_opt},
        global_alternative_profile={"Q05_coordination_mechanism": {q05_opt: 1.0}},
        included_question_ids=["Q05"],
        diagnostic_context_question_ids=["Q14"],
        logical_constraints_satisfied=["LC-1"],
        institutional_constraints_satisfied=["IC-1"],
        dependencies_satisfied=["SD-1"],
        feasibility_evaluation_status="STRICTLY_FEASIBLE",
        generation_method="DISCRETE_POLICY_GRID",
        provenance=_prov(f"SOL_{sid}"),
    )


def test_active_ballot_validation_blocks_fabricated_completeness(tmp_path: Path):
    """Do not fabricate complete rankings across null point_utility, partial ID, or crosswalk gaps."""
    cell_gap = PreferenceCell(
        cell_id="C_GAP",
        participant_id="PARTICIPANT_001",
        question_id="Q05",
        subtopic_id="Q05_coordination_mechanism",
        missingness_state=MissingnessState.OBSERVED_USABLE,
        coder_a_distribution={"scenario_1": 1.0},
        coder_b_distribution=None,
        coder_a_probability_interpretation="epistemic_uncertainty_over_preference",
        coder_b_probability_interpretation=None,
        canonical_alternative_crosswalk=CanonicalAlternativeCrosswalk(
            question_id="Q05",
            canonical_subtopic_id="Q05_coordination_mechanism",
            crosswalk_status=CrosswalkStatus.SINGLE_CODER_ONLY,
            comparable=False,
        ),
        uncertainty_class=UncertaintyClass.SINGLE_CODER_PARTIAL_ID_OMISSION,
        preference_uncertainty_set=PreferenceUncertaintySet(
            representation_type=UncertaintyRepresentationType.SINGLE_CODER_PARTIAL_ID,
            discrete_scenarios=[{"coder_a:scenario_1": 1.0}],
            single_coder_active_side="coder_a",
            non_coding_coder_state="EPISTEMICALLY_UNOBSERVED",
            interpretation_variants=["epistemic_uncertainty_over_preference"],
        ),
        reconciliation_status=ReconciliationStatus.RESOLVED_WITH_UNCERTAINTY_SET,
        resolved_point_distribution=None,
        evidence_span_ids=["SP_1"],
        provenance=_prov("C_GAP"),
    )
    cell_miss = PreferenceCell(
        cell_id="C_MISS",
        participant_id="PARTICIPANT_002",
        question_id="Q05",
        subtopic_id="Q05_coordination_mechanism",
        missingness_state=MissingnessState.MISSING_RAW_BLANK,
        uncertainty_class=UncertaintyClass.PRESERVED_MISSINGNESS,
        preference_uncertainty_set=PreferenceUncertaintySet(
            representation_type=UncertaintyRepresentationType.EMPTY_MISSING,
        ),
        reconciliation_status=ReconciliationStatus.PRESERVED_MISSING_OR_NON_PREFERENCE,
        resolved_point_distribution=None,
        evidence_span_ids=[],
        provenance=_prov("C_MISS"),
    )
    matrix = PreferenceMatrix(
        matrix_id="PM_GAP",
        participant_ids=["PARTICIPANT_001", "PARTICIPANT_002"],
        question_ids=["Q05"],
        subtopic_ids=["Q05_coordination_mechanism"],
        subtopic_to_question={"Q05_coordination_mechanism": "Q05"},
        cells=[cell_gap, cell_miss],
        observed_usable_cell_count=1,
        unobserved_missing_cell_count=1,
        infeasible_choice_cell_count=0,
        ambiguous_cell_count=0,
        overall_coder_agreement_mean=1.0,
        overall_coder_confidence_mean=0.9,
        validation_passed=True,
        provenance=_prov("PM_GAP"),
    )
    pu_payload = {
        "participant_utilities": [
            {
                "participant_id": "PARTICIPANT_001",
                "solution_id": "SOL_0001",
                "point_utility": None,
                "min_scenario_utility": 0.2,
                "max_scenario_utility": 0.9,
            }
        ]
    }
    audit = evaluate_ballot_derivation_legitimacy(matrix, pu_payload, {"PARTICIPANT_001": 0.0})
    assert audit["can_derive_complete_strict_rankings_without_fabrication"] is False
    assert audit["can_derive_point_cardinal_ballots_without_fabrication"] is False
    assert audit["null_point_utility_count"] == 1
    assert audit["single_coder_partial_id_primary_count"] == 1
    assert audit["preserved_missing_primary_count"] == 1

    # Also verify external ballot validator rejects synthetic/cluster-weighted ballots
    bad_baldwin = tmp_path / "bad_baldwin.json"
    bad_baldwin.write_text(
        json.dumps({
            "run_id": "run_test",
            "dataset_fingerprint": "fp_test",
            "synthetic_complete_ballots": True,
            "cluster_weighted_ballots": True,
            "ballots": [{"ballot_id": "B1", "ranking": ["A", "B"], "cluster_weight": 2.0}],
        }),
        encoding="utf-8",
    )
    ok_b, err_b, _ = validate_baldwin_ballot_file(
        bad_baldwin,
        run_id="run_test",
        expected_dataset_fingerprint="fp_test",
        authorized_candidate_ids=["A", "B"],
    )
    assert ok_b is False
    assert any("synthetically completed" in e for e in err_b)
    assert any("cluster_weighted_ballots" in e for e in err_b)

    bad_rrv = tmp_path / "bad_rrv.json"
    bad_rrv.write_text(
        json.dumps({
            "run_id": "run_wrong",
            "dataset_fingerprint": "fp_wrong",
            "ballots": [{"ballot_id": "R1", "scores": {"A": 5.0}, "weight": 1.5}],
        }),
        encoding="utf-8",
    )
    ok_r, err_r, _ = validate_rrv_ballot_file(
        bad_rrv,
        run_id="run_test",
        expected_dataset_fingerprint="fp_test",
        authorized_candidate_ids=["A", "B"],
    )
    assert ok_r is False
    assert len(err_r) >= 3


def test_baldwin_conditional_execution_and_not_applicable_gating(tmp_path: Path):
    """Baldwin marks NOT_APPLICABLE / SKIPPED_NO_VALID_INPUT without ballots and runs cleanly on valid ones."""
    audit = {"blocking_reasons": ["point_utility is None"]}
    skipped_res, skipped_env = evaluate_baldwin_voting(
        run_id="run_test",
        dataset_fingerprint="fp_test",
        candidate_ids=["A", "B", "C"],
        ballot_file_path=None,
        ballot_derivation_audit=audit,
    )
    assert skipped_res.execution_status == "SKIPPED_NO_VALID_INPUT"
    assert skipped_env["applicability_status"] == "NOT_APPLICABLE"
    assert skipped_env["synthetic_ballots_fabricated"] is False

    # Valid external ballot fixture where Condorcet winner C beats initial Borda leader A after B is eliminated:
    # 4 voters: A > C > B; 3 voters: B > C > A; 2 voters: C > B > A (9 voters)
    # Round 1 Borda (m=3 -> 2,1,0):
    #   A = 4*2 + 3*0 + 2*0 = 8
    #   B = 4*0 + 3*2 + 2*1 = 8 -> wait let's adjust so C > A after eliminating A or B:
    # 5 voters: C > A > B; 4 voters: A > B > C; 2 voters: B > C > A (11 voters)
    # Round 1: A = 5*1 + 4*2 + 2*0 = 13; C = 5*2 + 4*0 + 2*1 = 12; B = 5*0 + 4*1 + 2*2 = 8 -> B eliminated
    # Round 2 (between A and C): C gets 5 + 2 = 7, A gets 4 -> C wins Baldwin (even though A led Round 1 Borda!)
    ballots = (
        [["C", "A", "B"]] * 5
        + [["A", "B", "C"]] * 4
        + [["B", "C", "A"]] * 2
    )
    ballot_file = tmp_path / "baldwin_ballots.json"
    ballot_file.write_text(
        json.dumps({
            "run_id": "run_test",
            "dataset_fingerprint": "fp_test",
            "candidate_ids": ["A", "B", "C"],
            "ballots": [{"ballot_id": f"B{i+1}", "ranking": r} for i, r in enumerate(ballots)],
        }),
        encoding="utf-8",
    )
    res, env = evaluate_baldwin_voting(
        run_id="run_test",
        dataset_fingerprint="fp_test",
        candidate_ids=["A", "B", "C"],
        ballot_file_path=ballot_file,
        ballot_derivation_audit={"blocking_reasons": []},
    )
    assert res.execution_status == "EXECUTED"
    assert env["applicability_status"] == "APPLICABLE"
    assert res.borda_initial_ranking[0] == "A"
    assert res.elimination_rounds[0]["eliminated_candidate"] == "B"
    assert res.winner_candidate_ids == ["C"]
    assert res.valid_ballot_count == 11


def test_rrv_conditional_execution_and_small_n_proportionality(tmp_path: Path):
    """RRV marks NOT_APPLICABLE without valid score ballots and enforces small-N proportionality when run."""
    skipped_res, skipped_env = evaluate_rrv_voting(
        run_id="run_test",
        dataset_fingerprint="fp_test",
        candidate_ids=["C1", "C2", "C3", "C4"],
        ballot_file_path=None,
        ballot_derivation_audit={"blocking_reasons": ["no score ballot file"]},
        participant_count=11,
        default_committee_size=2,
    )
    assert skipped_res.execution_status == "SKIPPED_NO_VALID_INPUT"
    assert skipped_env["applicability_status"] == "NOT_APPLICABLE"
    assert skipped_env["small_n_quota_context"]["valid_ballot_count"] == 11
    assert skipped_env["small_n_quota_context"]["single_ballot_vote_share"] == pytest.approx(1.0 / 11.0, abs=1e-5)

    # 11-voter RRV test: 7 Majority voters score {M1: 1.0, M2: 1.0, MIN1: 0.0}
    # 4 Minority voters (> Droop 1/(2+1) = 33.3% = 4 ballots!) score {M1: 0.0, M2: 0.0, MIN1: 1.0}
    # Round 1 selects M1 (score 7.0). Majority voters get reweighted to k / (k + 1) = 0.5 -> 7 * 0.5 = 3.5 < 4.0!
    # Round 2 MUST select MIN1 (score 4.0 > 3.5)!
    ballots = (
        [{"M1": 1.0, "M2": 1.0, "MIN1": 0.0}] * 7
        + [{"M1": 0.0, "M2": 0.0, "MIN1": 1.0}] * 4
    )
    rrv_file = tmp_path / "rrv_ballots.json"
    rrv_file.write_text(
        json.dumps({
            "run_id": "run_test",
            "dataset_fingerprint": "fp_test",
            "candidate_ids": ["M1", "M2", "MIN1"],
            "score_scale_min": 0.0,
            "score_scale_max": 1.0,
            "reweighting_constant_k": 1.0,
            "seats_to_fill": 2,
            "ballots": [{"ballot_id": f"R{i+1}", "scores": sc} for i, sc in enumerate(ballots)],
        }),
        encoding="utf-8",
    )
    res, env = evaluate_rrv_voting(
        run_id="run_test",
        dataset_fingerprint="fp_test",
        candidate_ids=["M1", "M2", "MIN1"],
        ballot_file_path=rrv_file,
        ballot_derivation_audit={"blocking_reasons": []},
    )
    assert res.execution_status == "EXECUTED"
    assert env["applicability_status"] == "APPLICABLE"
    assert res.selected_committee_ids == ["M1", "MIN1"]
    assert res.proportionality_satisfaction_metrics["positive_representation_voter_share"] == 1.0
    small_n = env["small_n_proportionality_diagnostics"]
    assert small_n["committee_size"] == 2
    assert small_n["droop_quota_ballots_floor_plus_1"] == 4
    assert small_n["leave_one_ballot_out_distinct_committee_count"] >= 1


def test_condorcet_cycle_smith_set_minimax_and_borda_ties():
    """Verify exact Borda mid-ranks, Condorcet cycles, Smith set, and Simpson-Kramer Minimax."""
    # 3-voter classic cycle on A, B, C, while D loses unanimously to all three:
    # v0: A(0.9) > B(0.7) > C(0.5) > D(0.1)
    # v1: B(0.9) > C(0.7) > A(0.5) > D(0.1)
    # v2: C(0.9) > A(0.7) > B(0.5) > D(0.1)
    U = np.array([
        [0.9, 0.5, 0.7],  # A
        [0.7, 0.9, 0.5],  # B
        [0.5, 0.7, 0.9],  # C
        [0.1, 0.1, 0.1],  # D
    ], dtype=np.float64)
    sids = ["A", "B", "C", "D"]
    borda = compute_borda_scores(U, sids)
    assert borda["scores"]["A"] == pytest.approx(6.0)
    assert borda["scores"]["B"] == pytest.approx(6.0)
    assert borda["scores"]["C"] == pytest.approx(6.0)
    assert borda["scores"]["D"] == pytest.approx(0.0)
    assert set(borda["winner_ids"]) == {"A", "B", "C"}

    cm = compute_condorcet_minimax_metrics(U, sids, compute_smith=True)
    assert cm["condorcet"]["has_condorcet_cycle"] is True
    assert cm["condorcet"]["strict_condorcet_winners"] == []
    assert cm["condorcet"]["weak_condorcet_winners"] == []
    assert cm["condorcet"]["smith_set_ids"] == ["A", "B", "C"]
    assert cm["minimax"]["min_worst_pairwise_defeat"] == 1
    assert set(cm["minimax"]["winner_ids"]) == {"A", "B", "C"}


def test_uncertainty_propagation_small_n_and_pareto_comparison(tmp_path: Path):
    """Verify ADR-0008 scenario propagation, small-N sensitivity, and unconflated Pareto cross-check."""
    sol_ids = ["S_CORE", "S_COND", "S_DOM"]
    # 5 participants where scenarios flip winners between S_CORE and S_COND
    exp_u = np.array([
        [0.85, 0.85, 0.70, 0.60, 0.90],  # S_CORE (Minimax winner, robust core)
        [0.82, 0.82, 0.88, 0.88, 0.55],  # S_COND
        [0.10, 0.10, 0.10, 0.10, 0.10],  # S_DOM
    ], dtype=np.float64)
    mc_u = np.repeat(exp_u[None, :, :], 12, axis=0)
    regimes = []
    for d in range(12):
        if d % 2 == 0:
            mc_u[d, 1] = [0.95, 0.95, 0.92, 0.91, 0.60]  # flips Borda/Minimax winner to S_COND
        regimes.append({
            "draw_index": d,
            "coder_regime": "CODER_A_REGIME" if d % 2 == 0 else "CODER_B_REGIME",
            "overlap_multiplier": 0.5 if d % 2 == 0 else 1.0,
            "interpretation_mode": "EPISTEMIC_CATEGORICAL_ALL_FLAGGED" if d % 3 == 0 else "EXPLICIT_MIXED_ALL_FLAGGED",
            "omission_include_prob": 0.0 if d % 4 == 0 else 1.0,
            "conditional_mode": "ADVERSARIAL_LOW" if d % 2 == 0 else "CHARITABLE_HIGH",
        })

    ens = UtilityEnsembleSummary(
        run_id="run_test",
        matrix_id="PM_T",
        participant_ids=[f"P{i}" for i in range(5)],
        valid_participant_ids=[f"P{i}" for i in range(5)],
        excluded_all_missing_participant_ids=[],
        solution_ids=sol_ids,
        question_ids_evaluated=["Q05"],
        participant_utilities=[],
        expected_utility_matrix=exp_u,
        uniform_subtopic_utility_matrix=exp_u,
        uniform_question_utility_matrix=exp_u,
        ci_lower_matrix=exp_u - 0.15,
        ci_upper_matrix=exp_u + 0.15,
        min_scenario_matrix=exp_u - 0.30,
        max_scenario_matrix=exp_u + 0.30,
        min_coding_gap_matrix=exp_u - 0.25,
        max_coding_gap_matrix=exp_u + 0.25,
        coupled_gap_corner_matrices={"c_lo": exp_u, "c_hi": mc_u[0]},
        mc_draws_utilities=mc_u,
        mc_draw_regimes=regimes,
        derived_barycenter_matrices={"barycenter_lambda_0.50": exp_u},
        interpretation_operator_audit={},
        participant_diagnostics={},
        question_diagnostics={},
    )

    unc = propagate_social_choice_uncertainty(ens)
    assert unc["equal_ballot_weighting_enforced"] is True
    assert unc["cluster_weights_applied"] is False
    assert unc["participants_ranked"] is False
    assert unc["monte_carlo_draws"] == 12
    assert len(unc["monte_carlo_results"]["borda_winner_inclusion_probabilities"]) == 2

    sens = compute_small_n_sensitivity(ens, unc, committee_size_reference=3)
    assert sens["ranked_as_participant"] is False
    assert sens["cluster_weights_applied"] is False
    assert sens["small_n_discreteness"]["valid_ballot_count"] == 5
    # Verify NO participant IDs appear anywhere in sensitivity output
    sens_text = json.dumps(sens)
    assert "PARTICIPANT_" not in sens_text

    # Pareto cross-check with separate 7 welfare criteria
    (tmp_path / "data" / "raw").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "raw" / "survey_raw.csv").write_text("col1\nval1\n", encoding="utf-8")
    mc_cfg = {"monte_carlo_draws": 12, "random_seed": 42, "veto_threshold": 0.35}
    base_pareto = ParetoAnalyzer(tmp_path, run_id="run_test").evaluate(
        matrix_id="PM_T",
        solution_ids=sol_ids,
        valid_participant_ids=[f"P{i}" for i in range(5)],
        excluded_all_missing_participant_ids=[],
        utility_matrix=exp_u,
        mc_config=mc_cfg,
    )
    sols = [_sol(sid) for sid in sol_ids]
    rob_res, counts_bundle = RobustParetoEngine(tmp_path, run_id="run_test").evaluate(
        base_pareto=base_pareto,
        utility_summary=ens,
        solutions=sols,
        mc_config=mc_cfg,
        pareto_mc_config_rel_path="runs/run_test/pareto_mc_config.json",
    )
    cmp = build_pareto_voting_comparison(
        run_id="run_test",
        pareto_payload={"pareto_result": {
            "evaluated_solution_ids": sol_ids,
            "nondominated_solution_ids": base_pareto.nondominated_solution_ids,
            "rankings_by_criterion": base_pareto.rankings_by_criterion,
        }},
        robust_payload={
            "robust_pareto_result": {
                "robustly_nondominated_solution_ids": rob_res.robustly_nondominated_solution_ids,
                "conditionally_nondominated_solution_ids": rob_res.conditionally_nondominated_solution_ids,
                "unresolved_due_to_coding_uncertainty_ids": rob_res.unresolved_due_to_coding_uncertainty_ids,
                "frontier_inclusion_probabilities": rob_res.frontier_inclusion_probabilities,
                "solution_robustness_statuses": {k: v.value for k, v in rob_res.solution_robustness_statuses.items()},
                "criterion_top1_probabilities": rob_res.criterion_top1_probabilities,
            },
            "high_confidence_nondominated_ids": counts_bundle["high_confidence_nondominated_ids"],
        },
        unc_report=unc,
        baldwin_envelope={"applicability_status": "NOT_APPLICABLE", "execution_status": "SKIPPED_NO_VALID_INPUT", "baldwin_result": {}},
        rrv_envelope={"applicability_status": "NOT_APPLICABLE", "execution_status": "SKIPPED_NO_VALID_INPUT", "rrv_result": {}},
    )
    assert cmp["conceptual_distinction_and_interpretation"]["pareto_vs_voting_non_conflation"] is True
    assert cmp["conceptual_distinction_and_interpretation"]["welfare_criteria_combined_into_voting_rule"] is False
    assert len(cmp["separate_welfare_criteria_diagnostics"]) == 7


def test_end_to_end_pipeline_on_synthetic_staged_workspace(tmp_path: Path):
    """Run full Agent 06 pipeline cleanly against a staged synthetic Agent 04 workspace."""
    (tmp_path / "data" / "raw").mkdir(parents=True)
    (tmp_path / "data" / "raw" / "survey_raw.csv").write_text("col1\nval1\n", encoding="utf-8")
    proc_dir = tmp_path / "data" / "processed"
    pref_dir = proc_dir / "preference"
    rec_dir = proc_dir / "reconciliation"
    run_dir = tmp_path / "runs" / "run_syn"
    pref_dir.mkdir(parents=True)
    rec_dir.mkdir(parents=True)
    run_dir.mkdir(parents=True)

    mc_cfg = {
        "schema_version": "1.0.0",
        "run_id": "run_syn",
        "monte_carlo_draws": 15,
        "random_seed": 42,
        "veto_threshold": 0.35,
        "derived_convex_hull_sweep_enabled": True,
        "derived_barycenter_lambdas": [0.25, 0.5, 0.75],
    }
    (run_dir / "pareto_mc_config.json").write_text(json.dumps(mc_cfg), encoding="utf-8")

    # Build minimal reconciled & normalized files for PreferenceMatrix
    import pandas as pd
    norm_dir = tmp_path / "data" / "normalized"
    norm_dir.mkdir(parents=True)
    rows = [
        {"participant_id": f"PARTICIPANT_{i:03d}", "question_id": "Q05"}
        for i in range(1, 5)
    ]
    pd.DataFrame(rows).to_parquet(norm_dir / "answers_normalized.parquet", index=False)

    (proc_dir / "themes_codebook.json").write_text(
        json.dumps({"canonical_subtopics": [{"subtopic_id": "Q05_coordination_mechanism", "question_id": "Q05"}]}),
        encoding="utf-8",
    )
    recs = []
    for i in range(1, 5):
        pid = f"PARTICIPANT_{i:03d}"
        if i <= 2:
            d_a = {"scenario_1": 0.8, "scenario_2": 0.2}
            d_b = {"scenario_1": 0.7, "scenario_2": 0.3}
            cw = CanonicalAlternativeCrosswalk(
                question_id="Q05",
                canonical_subtopic_id="Q05_coordination_mechanism",
                crosswalk_status=CrosswalkStatus.EXACT_KEY_MATCH,
                comparable=True,
                canonical_keys=["scenario_1", "scenario_2"],
                coder_a_to_canonical={"scenario_1": "scenario_1", "scenario_2": "scenario_2"},
                coder_b_to_canonical={"scenario_1": "scenario_1", "scenario_2": "scenario_2"},
            )
            recs.append({
                "record_id": f"PREC_{i}",
                "participant_id": pid,
                "question_id": "Q05",
                "canonical_subtopic_id": "Q05_coordination_mechanism",
                "missingness_state": "observed_usable",
                "uncertainty_class": "DUAL_CODER_DISTRIBUTION_SET",
                "agreement_status": "DISTRIBUTION_DISAGREEMENT",
                "reconciliation_status": "RESOLVED_WITH_UNCERTAINTY_SET",
                "reconciliation_method": "UNCERTAINTY_SET_PRESERVED",
                "coder_a_distribution": d_a,
                "coder_b_distribution": d_b,
                "coder_a_probability_interpretation": "epistemic_uncertainty_over_preference",
                "coder_b_probability_interpretation": "epistemic_uncertainty_over_preference",
                "semantic_importance_a": 0.8,
                "semantic_importance_b": 0.8,
                "coder_confidence_a": 0.9,
                "coder_confidence_b": 0.9,
                "distribution_similarity_1_minus_tvd": 0.9,
                "canonical_alternative_crosswalk": {
                    "question_id": cw.question_id,
                    "canonical_subtopic_id": cw.canonical_subtopic_id,
                    "crosswalk_status": cw.crosswalk_status.value,
                    "comparable": cw.comparable,
                    "canonical_keys": cw.canonical_keys,
                    "coder_a_to_canonical": cw.coder_a_to_canonical,
                    "coder_b_to_canonical": cw.coder_b_to_canonical,
                },
                "preference_uncertainty_set": {
                    "representation_type": "DISCRETE_CODER_SET",
                    "discrete_scenarios": [d_a, d_b],
                    "interpretation_variants": ["epistemic_uncertainty_over_preference"],
                },
                "resolved_point_distribution": None,
                "source_evidence_ids": [f"SP_{i}"],
            })
        else:
            recs.append({
                "record_id": f"PREC_{i}",
                "participant_id": pid,
                "question_id": "Q05",
                "canonical_subtopic_id": "Q05_coordination_mechanism",
                "missingness_state": "observed_usable",
                "uncertainty_class": "SINGLE_CODER_PARTIAL_ID_OMISSION",
                "agreement_status": "SINGLE_CODER_ONLY",
                "reconciliation_status": "RESOLVED_WITH_UNCERTAINTY_SET",
                "reconciliation_method": "SINGLE_CODER_PARTIAL_ID",
                "coder_a_distribution": {"scenario_2": 0.9, "scenario_1": 0.1},
                "coder_b_distribution": None,
                "coder_a_probability_interpretation": "epistemic_uncertainty_over_preference",
                "coder_b_probability_interpretation": None,
                "semantic_importance_a": 0.8,
                "semantic_importance_b": None,
                "coder_confidence_a": 0.9,
                "coder_confidence_b": None,
                "canonical_alternative_crosswalk": {
                    "question_id": "Q05",
                    "canonical_subtopic_id": "Q05_coordination_mechanism",
                    "crosswalk_status": "SINGLE_CODER_ONLY",
                    "comparable": False,
                },
                "preference_uncertainty_set": {
                    "representation_type": "SINGLE_CODER_PARTIAL_ID",
                    "discrete_scenarios": [{"coder_a:scenario_2": 0.9, "coder_a:scenario_1": 0.1}],
                    "single_coder_active_side": "coder_a",
                    "non_coding_coder_state": "EPISTEMICALLY_UNOBSERVED",
                    "interpretation_variants": ["epistemic_uncertainty_over_preference"],
                },
                "resolved_point_distribution": None,
                "source_evidence_ids": [f"SP_{i}"],
            })

    (rec_dir / "reconciled_evidence.json").write_text(
        json.dumps({"preference_reconciliation_records": recs}), encoding="utf-8"
    )
    (rec_dir / "reconciliation_qa_report.json").write_text(
        json.dumps({"all_reconciliation_invariants_passed": True}), encoding="utf-8"
    )

    builder = PreferenceMatrixBuilder(tmp_path, run_id="run_syn")
    matrix, diags = builder.build(verify_manifest=False)
    builder.save(matrix, diags)

    sols = [_sol("SOL_1", "scenario_1"), _sol("SOL_2", "scenario_2")]
    from dataclasses import asdict as _asdict
    (pref_dir / "feasible_alternatives.json").write_text(
        json.dumps({"governance_solutions": [_asdict(s) for s in sols]}, default=str),
        encoding="utf-8",
    )
    ens = ParticipantUtilityEngine(tmp_path, run_id="run_syn").evaluate(matrix, sols, mc_cfg)
    (pref_dir / "participant_utility.json").write_text(
        json.dumps({
            "valid_participant_ids": ens.valid_participant_ids,
            "excluded_all_missing_participant_ids": ens.excluded_all_missing_participant_ids,
            "participant_diagnostics": ens.participant_diagnostics,
            "participant_utilities": [_asdict(pu) for pu in ens.participant_utilities],
        }, default=str),
        encoding="utf-8",
    )
    base_pareto = ParetoAnalyzer(tmp_path, run_id="run_syn").evaluate(
        matrix_id=matrix.matrix_id,
        solution_ids=[s.solution_id for s in sols],
        valid_participant_ids=ens.valid_participant_ids,
        excluded_all_missing_participant_ids=ens.excluded_all_missing_participant_ids,
        utility_matrix=ens.expected_utility_matrix,
        mc_config=mc_cfg,
    )
    (pref_dir / "pareto_results.json").write_text(
        json.dumps({"pareto_result": _asdict(base_pareto)}, default=str),
        encoding="utf-8",
    )
    rob_res, sens_bundle = RobustParetoEngine(tmp_path, run_id="run_syn").evaluate(
        base_pareto=base_pareto,
        utility_summary=ens,
        solutions=sols,
        mc_config=mc_cfg,
        pareto_mc_config_rel_path="runs/run_syn/pareto_mc_config.json",
    )
    (pref_dir / "robust_pareto_results.json").write_text(
        json.dumps({
            "status_counts": sens_bundle["status_counts"],
            "high_confidence_nondominated_ids": sens_bundle["high_confidence_nondominated_ids"],
            "robust_pareto_result": {
                **_asdict(rob_res),
                "solution_robustness_statuses": {k: v.value for k, v in rob_res.solution_robustness_statuses.items()},
            },
        }, default=str),
        encoding="utf-8",
    )
    (pref_dir / "pareto_sensitivity.json").write_text(json.dumps(sens_bundle, default=str), encoding="utf-8")
    (pref_dir / "preference_uncertainty_summary.json").write_text(json.dumps({"ok": True}), encoding="utf-8")
    (pref_dir / "agent_04_qa_report.json").write_text(json.dumps({"all_qa_checks_passed": True}), encoding="utf-8")

    summary = run_agent_06_pipeline(base_dir=tmp_path, run_id="run_syn", verify_manifest=False)
    assert summary["qa_report"]["all_qa_checks_passed"] is True
    assert summary["baldwin_applicability"] == "NOT_APPLICABLE"
    assert summary["rrv_applicability"] == "NOT_APPLICABLE"
    assert (proc_dir / "voting_results.json").is_file()
    assert (proc_dir / "voting" / "agent_06_qa_report.json").is_file()
    assert (proc_dir / "voting" / "task_local_artifact_descriptors.json").is_file()


def test_production_run_20261111_002_voting_outputs_when_staged():
    """Verify staged Agent 06 outputs for run_20261111_002 whenever private runtime data exists."""
    vr_path = REPO_ROOT / "data" / "processed" / "voting_results.json"
    v_dir = REPO_ROOT / "data" / "processed" / "voting"
    qa_path = v_dir / "agent_06_qa_report.json"

    if not (vr_path.is_file() and qa_path.is_file()):
        pytest.skip("Staged Agent 06 runtime artifacts not present in clean CI clone.")

    qa = json.loads(qa_path.read_text(encoding="utf-8"))
    assert qa["all_qa_checks_passed"] is True
    for name, val in qa["qa_checks"].items():
        assert val is True, f"QA check {name} failed"

    vr = json.loads(vr_path.read_text(encoding="utf-8"))
    assert vr["choice_set_count"] == 543
    assert vr["participant_count"] == 11
    assert vr["equal_ballot_weighting_enforced"] is True
    assert vr["cluster_weights_applied"] is False
    assert vr["participants_ranked"] is False
    assert vr["baldwin_result"]["execution_status"] == "SKIPPED_NO_VALID_INPUT"
    assert vr["rrv_result"]["execution_status"] == "SKIPPED_NO_VALID_INPUT"
    assert vr["is_unanimous"] is False
    assert vr["consensus_winner"] is None

    for fname in [
        "voting_input_validation.json",
        "voting_uncertainty.json",
        "baldwin_results.json",
        "rrv_results.json",
        "pareto_voting_comparison.json",
        "voting_sensitivity.json",
        "agent_06_qa_report.json",
        "task_local_artifact_descriptors.json",
    ]:
        assert (v_dir / fname).is_file(), f"Missing Agent 06 output {fname}"

    sens = json.loads((v_dir / "voting_sensitivity.json").read_text(encoding="utf-8"))
    assert sens["small_n_discreteness"]["valid_ballot_count"] == 11
    assert sens["ranked_as_participant"] is False
    assert sens["cluster_weights_applied"] is False
