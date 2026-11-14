"""Comprehensive Verification Suite for Agent 04 (Preference Matrix, Utilities & Robust Pareto).

Enforces ADR-0005, ADR-0007, ADR-0008, and ISSUE-005 invariants across:
- PreferenceMatrix construction, Parquet/JSON round-trip, and simplex validation;
- Zero unauthorized point collapse & zero 0.0-fill on single-coder silence or missingness;
- Zero coder_confidence usage as preference or utility weight;
- ISSUE-005 interpretation-specific operators (epistemic vs explicit_mixed vs conditional);
- Strict Q01-Q13 primary analytical spine with Q14 contextual isolation;
- Strictly constraint-only solution pruning (prohibiting cluster/value/disagreement pruning);
- Exact skyline vs pairwise dominance parity;
- 4-state mutually exclusive RobustParetoResult classification and derived-scenario tagging;
- Live production pipeline artifact audit (when staged run_20261111_002 inputs exist).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from src.contracts import (
    AgreementStatus,
    CanonicalAlternativeCrosswalk,
    CrosswalkStatus,
    DerivedScenarioOrigin,
    FeasibleAlternative,
    GovernanceSolution,
    MissingnessState,
    PROHIBITED_PRUNING_SOURCES,
    ParticipantUtility,
    PreferenceCell,
    PreferenceMatrix,
    PreferenceUncertaintySet,
    ProvenanceMeta,
    ReconciliationStatus,
    RobustParetoResult,
    RobustParetoStatus,
    UncertaintyClass,
    UncertaintyEnvelope,
    UncertaintyRepresentationType,
)
from src.preference.pareto import ParetoAnalyzer, nondominated_mask_exact, nondominated_mask_skyline
from src.preference.preference_matrix import (
    PRIMARY_QUESTION_IDS,
    PreferenceMatrixBuilder,
    load_pareto_mc_config,
    load_preference_matrix,
)
from src.preference.robust_pareto import RobustParetoEngine
from src.preference.solution_space import SolutionSpaceBuilder
from src.preference.utilities import ParticipantUtilityEngine


REPO_ROOT = Path(__file__).resolve().parents[1]


def _prov(rid: str) -> ProvenanceMeta:
    return ProvenanceMeta(
        record_id=rid,
        run_id="run_test_pref",
        dataset_fingerprint="test_fp",
        created_at_utc="2026-11-14T00:00:00Z",
        producer_module="tests/test_preference.py",
        producer_agent="agent_04",
    )


def _sol(sid: str, prof: dict[str, dict[str, float]], **kwargs) -> GovernanceSolution:
    return GovernanceSolution(
        solution_id=sid,
        label_en=sid,
        question_alternatives={f"Q{i:02d}": "opt" for i in range(1, 14)},
        global_alternative_profile=prof,
        included_question_ids=list(PRIMARY_QUESTION_IDS),
        diagnostic_context_question_ids=["Q14"],
        logical_constraints_satisfied=["LC_OK"],
        institutional_constraints_satisfied=["IC_OK"],
        dependencies_satisfied=["SD_OK"],
        feasibility_evaluation_status="STRICTLY_FEASIBLE",
        generation_method="COMBINATORIAL_CONSTRAINT_SATISFACTION",
        provenance=_prov(sid),
        **kwargs,
    )


def test_pareto_mc_config_loads_and_matches_run_id():
    cfg, rel_path, sha = load_pareto_mc_config(REPO_ROOT, run_id="run_20261111_002")
    assert rel_path == "runs/run_20261111_002/pareto_mc_config.json"
    assert len(sha) == 64
    assert int(cfg["monte_carlo_draws"]) >= 100
    assert int(cfg["random_seed"]) == 42
    assert float(cfg["robust_core_inclusion_threshold"]) == 1.0


def test_skyline_exact_dominance_parity_random_and_ties():
    rng = np.random.default_rng(123)
    for S, P in [(40, 5), (300, 11), (350, 8)]:
        U = rng.uniform(0.0, 1.0, size=(S, P))
        # Inject exact ties and strict dominators
        U[0] = U[1].copy()
        U[2] = np.clip(U[1] + 0.05, 0.0, 1.0)
        exact = nondominated_mask_exact(U, tol=1e-9)
        fast = nondominated_mask_skyline(U, tol=1e-9)
        assert np.array_equal(exact, fast), f"Skyline parity failed for shape ({S}, {P})"
        assert not exact[0] and not exact[1], "Strictly dominated clones must not survive"


def test_constraint_only_pruning_rejects_prohibited_sources():
    with pytest.raises(ValueError, match="prohibited pruning source"):
        FeasibleAlternative(
            alternative_id="BAD_ALT",
            question_id="Q05",
            label_en="bad",
            description_en="bad",
            subtopic_alternative_allocations={"Q05_coordination_mechanism": {"scenario_1": 1.0}},
            active_subtopic_mask={"Q05_coordination_mechanism": True},
            supporting_participant_count=1,
            missing_participant_count=0,
            feasibility_status="PRUNED_INCOMPATIBLE",
            empirical_support_uncertainty=UncertaintyEnvelope(point_estimate=1.0),
            provenance=_prov("BAD_ALT"),
            pruning_sources_applied=["CLUSTER_ASSIGNMENT"],
        )

    for bad_src in sorted(PROHIBITED_PRUNING_SOURCES):
        with pytest.raises(ValueError, match="prohibited pruning source"):
            _sol("BAD_SOL", {}, pruning_sources_applied=[bad_src])


def test_coder_confidence_never_used_as_utility_weight_or_preference(tmp_path: Path):
    """ParticipantUtility must NEVER depend on coder_confidence values."""
    (tmp_path / "data" / "raw").mkdir(parents=True)
    (tmp_path / "data" / "raw" / "survey_raw.csv").write_text("dummy\n", encoding="utf-8")

    # Build two identical PreferenceMatrices differing ONLY in coder_confidence_a/b
    def _make_matrix(conf_a: float, conf_b: float) -> PreferenceMatrix:
        cw = CanonicalAlternativeCrosswalk(
            question_id="Q05",
            canonical_subtopic_id="Q05_coordination_mechanism",
            crosswalk_status=CrosswalkStatus.EXACT_KEY_MATCH,
            comparable=True,
            coder_a_to_canonical={"scenario_1": "scenario_1", "scenario_2": "scenario_2"},
            coder_b_to_canonical={"scenario_1": "scenario_1", "scenario_2": "scenario_2"},
            canonical_keys=["scenario_1", "scenario_2"],
        )
        pus = PreferenceUncertaintySet(
            representation_type=UncertaintyRepresentationType.DISCRETE_CODER_SET,
            discrete_scenarios=[{"scenario_1": 1.0}, {"scenario_2": 1.0}],
            interpretation_variants=["explicit_mixed_preference"],
        )
        cell = PreferenceCell(
            cell_id="C1",
            participant_id="P1",
            question_id="Q05",
            subtopic_id="Q05_coordination_mechanism",
            missingness_state=MissingnessState.OBSERVED_USABLE,
            coder_a_distribution={"scenario_1": 1.0},
            coder_b_distribution={"scenario_2": 1.0},
            coder_a_probability_interpretation="explicit_mixed_preference",
            coder_b_probability_interpretation="explicit_mixed_preference",
            semantic_importance=0.8,
            semantic_importance_a=0.8,
            semantic_importance_b=0.8,
            coder_confidence=(conf_a + conf_b) / 2.0,
            coder_confidence_a=conf_a,
            coder_confidence_b=conf_b,
            canonical_alternative_crosswalk=cw,
            uncertainty_class=UncertaintyClass.DUAL_CODER_DISTRIBUTION_SET,
            preference_uncertainty_set=pus,
            reconciliation_status=ReconciliationStatus.RESOLVED_WITH_UNCERTAINTY_SET,
            resolved_point_distribution=None,
            evidence_span_ids=["SP1"],
            provenance=_prov("C1"),
        )
        cell.validate_simplex()
        return PreferenceMatrix(
            matrix_id="PM_TEST",
            participant_ids=["P1"],
            question_ids=["Q05"],
            subtopic_ids=["Q05_coordination_mechanism"],
            subtopic_to_question={"Q05_coordination_mechanism": "Q05"},
            cells=[cell],
            observed_usable_cell_count=1,
            unobserved_missing_cell_count=0,
            infeasible_choice_cell_count=0,
            ambiguous_cell_count=0,
            overall_coder_agreement_mean=0.0,
            overall_coder_confidence_mean=(conf_a + conf_b) / 2.0,
            validation_passed=True,
            provenance=_prov("PM_TEST"),
        )

    sols = [
        _sol("S_A", {"Q05_coordination_mechanism": {"scenario_1": 1.0}}),
        _sol("S_B", {"Q05_coordination_mechanism": {"scenario_2": 1.0}}),
    ]
    mc_cfg = {"monte_carlo_draws": 100, "random_seed": 7, "veto_threshold": 0.35, "weight_perturbation_sigma": 0.0}

    eng = ParticipantUtilityEngine(tmp_path, run_id="run_test")
    u1 = eng.evaluate(_make_matrix(0.99, 0.10), sols, mc_cfg)
    u2 = eng.evaluate(_make_matrix(0.10, 0.99), sols, mc_cfg)

    assert np.allclose(u1.expected_utility_matrix, u2.expected_utility_matrix)
    assert np.allclose(u1.mc_draws_utilities, u2.mc_draws_utilities)
    assert all(not pu.uses_coder_confidence_as_weight for pu in u1.participant_utilities)
    # Must NOT produce a single collapsed point utility when scenarios diverge 1.0 vs 0.0
    assert all(pu.point_utility is None for pu in u1.participant_utilities)


def test_issue005_distinguishes_epistemic_vs_explicit_mixed_vs_conditional(tmp_path: Path):
    """Numerically equal (0.5, 0.5) distributions must differ operationally by interpretation."""
    (tmp_path / "data" / "raw").mkdir(parents=True)
    (tmp_path / "data" / "raw" / "survey_raw.csv").write_text("dummy\n", encoding="utf-8")

    def _matrix_with_interp(interp: str, uc: UncertaintyClass) -> PreferenceMatrix:
        cw = CanonicalAlternativeCrosswalk(
            question_id="Q11",
            canonical_subtopic_id="Q11_overhead_allocation_mechanism",
            crosswalk_status=CrosswalkStatus.EXACT_KEY_MATCH,
            comparable=True,
            coder_a_to_canonical={"opt_1": "opt_1", "opt_2": "opt_2"},
            coder_b_to_canonical={"opt_1": "opt_1", "opt_2": "opt_2"},
            canonical_keys=["opt_1", "opt_2"],
        )
        pus = PreferenceUncertaintySet(
            representation_type=UncertaintyRepresentationType.SINGLETON,
            discrete_scenarios=[{"opt_1": 0.5, "opt_2": 0.5}],
            interpretation_variants=[interp],
        )
        res_pt = {"opt_1": 0.5, "opt_2": 0.5} if uc == UncertaintyClass.NONE_CONSENSUS else None
        cell = PreferenceCell(
            cell_id="C_INTERP",
            participant_id="P1",
            question_id="Q11",
            subtopic_id="Q11_overhead_allocation_mechanism",
            missingness_state=MissingnessState.OBSERVED_USABLE,
            coder_a_distribution={"opt_1": 0.5, "opt_2": 0.5},
            coder_b_distribution={"opt_1": 0.5, "opt_2": 0.5},
            coder_a_probability_interpretation=interp,  # type: ignore[arg-type]
            coder_b_probability_interpretation=interp,  # type: ignore[arg-type]
            semantic_importance=1.0,
            semantic_importance_a=1.0,
            semantic_importance_b=1.0,
            canonical_alternative_crosswalk=cw,
            uncertainty_class=uc,
            preference_uncertainty_set=pus,
            reconciliation_status=ReconciliationStatus.AGREEMENT_EXACT if res_pt else ReconciliationStatus.RESOLVED_WITH_UNCERTAINTY_SET,
            resolved_point_distribution=res_pt,
            evidence_span_ids=["SP1"],
            provenance=_prov("C_INTERP"),
        )
        return PreferenceMatrix(
            matrix_id="PM_INTERP",
            participant_ids=["P1"],
            question_ids=["Q11"],
            subtopic_ids=["Q11_overhead_allocation_mechanism"],
            subtopic_to_question={"Q11_overhead_allocation_mechanism": "Q11"},
            cells=[cell],
            observed_usable_cell_count=1,
            unobserved_missing_cell_count=0,
            infeasible_choice_cell_count=0,
            ambiguous_cell_count=0,
            overall_coder_agreement_mean=1.0,
            overall_coder_confidence_mean=0.9,
            validation_passed=True,
            provenance=_prov("PM_INTERP"),
        )

    hybrid_sol = _sol("S_HYBRID", {"Q11_overhead_allocation_mechanism": {"opt_1": 0.5, "opt_2": 0.5}})
    vertex_sol = _sol("S_VERTEX", {"Q11_overhead_allocation_mechanism": {"opt_1": 1.0}})
    mc_cfg = {"monte_carlo_draws": 120, "random_seed": 42, "weight_perturbation_sigma": 0.0}

    eng = ParticipantUtilityEngine(tmp_path, run_id="run_test")
    res_ep = eng.evaluate(
        _matrix_with_interp("epistemic_uncertainty_over_preference", UncertaintyClass.NONE_CONSENSUS),
        [hybrid_sol, vertex_sol],
        mc_cfg,
    )
    res_mix = eng.evaluate(
        _matrix_with_interp("explicit_mixed_preference", UncertaintyClass.NONE_CONSENSUS),
        [hybrid_sol, vertex_sol],
        mc_cfg,
    )
    res_cond = eng.evaluate(
        _matrix_with_interp("conditional_or_context_dependent", UncertaintyClass.INTERPRETATION_DIVERGENCE),
        [hybrid_sol, vertex_sol],
        mc_cfg,
    )

    # Under explicit_mixed_preference, exact 50/50 hybrid achieves 1.0 while vertex achieves 0.5 (zero variance)
    assert res_mix.participant_utilities[0].point_utility == pytest.approx(1.0)
    assert res_mix.participant_utilities[1].point_utility == pytest.approx(0.5)
    assert res_mix.participant_utilities[0].utility_std_error == pytest.approx(0.0)
    # Under epistemic_uncertainty_over_preference, vertex draws induce positive variance across [0, 1]
    assert res_ep.participant_utilities[1].utility_std_error > 0.3
    # Under conditional_or_context_dependent without AST prerequisite, point_utility stays None
    assert res_cond.participant_utilities[0].point_utility is None


def test_single_coder_omission_never_imputes_zero_on_missing_cell(tmp_path: Path):
    """Preserving missingness & single-coder silence means no 0.0 utility on missing cells."""
    (tmp_path / "data" / "raw").mkdir(parents=True)
    (tmp_path / "data" / "raw" / "survey_raw.csv").write_text("dummy\n", encoding="utf-8")

    cw_sc = CanonicalAlternativeCrosswalk(
        question_id="Q04",
        canonical_subtopic_id="Q04_ad_hoc_operation",
        crosswalk_status=CrosswalkStatus.SINGLE_CODER_ONLY,
        comparable=False,
    )
    c_sc = PreferenceCell(
        cell_id="C_SC",
        participant_id="P1",
        question_id="Q04",
        subtopic_id="Q04_ad_hoc_operation",
        missingness_state=MissingnessState.OBSERVED_USABLE,
        coder_a_distribution={"Q04_AD_HOC_OPERATION": 1.0},
        coder_b_distribution=None,
        coder_a_probability_interpretation="epistemic_uncertainty_over_preference",
        coder_b_probability_interpretation=None,
        semantic_importance_a=0.8,
        semantic_importance_b=None,
        canonical_alternative_crosswalk=cw_sc,
        uncertainty_class=UncertaintyClass.SINGLE_CODER_PARTIAL_ID_OMISSION,
        preference_uncertainty_set=PreferenceUncertaintySet(
            representation_type=UncertaintyRepresentationType.SINGLE_CODER_PARTIAL_ID,
            discrete_scenarios=[{"coder_a:Q04_AD_HOC_OPERATION": 1.0}],
            single_coder_active_side="coder_a",
            non_coding_coder_state="EPISTEMICALLY_UNOBSERVED",
            interpretation_variants=["epistemic_uncertainty_over_preference"],
        ),
        reconciliation_status=ReconciliationStatus.RESOLVED_WITH_UNCERTAINTY_SET,
        resolved_point_distribution=None,
        evidence_span_ids=["SP_SC"],
        provenance=_prov("C_SC"),
    )
    c_q14 = PreferenceCell(
        cell_id="C_Q14",
        participant_id="P1",
        question_id="Q14",
        subtopic_id="Q14_collaboration_encouragement",
        missingness_state=MissingnessState.OBSERVED_USABLE,
        coder_a_distribution={"opt": 1.0},
        coder_b_distribution={"opt": 1.0},
        uncertainty_class=UncertaintyClass.NONE_CONSENSUS,
        resolved_point_distribution={"opt": 1.0},
        preference_uncertainty_set=PreferenceUncertaintySet(
            representation_type=UncertaintyRepresentationType.SINGLETON,
            discrete_scenarios=[{"opt": 1.0}],
        ),
        evidence_span_ids=["SP_Q14"],
        provenance=_prov("C_Q14"),
    )
    matrix = PreferenceMatrix(
        matrix_id="PM_SC",
        participant_ids=["P1"],
        question_ids=["Q04", "Q14"],
        subtopic_ids=["Q04_ad_hoc_operation", "Q14_collaboration_encouragement"],
        subtopic_to_question={"Q04_ad_hoc_operation": "Q04", "Q14_collaboration_encouragement": "Q14"},
        cells=[c_sc, c_q14],
        observed_usable_cell_count=2,
        unobserved_missing_cell_count=0,
        infeasible_choice_cell_count=0,
        ambiguous_cell_count=0,
        overall_coder_agreement_mean=1.0,
        overall_coder_confidence_mean=0.9,
        validation_passed=True,
        provenance=_prov("PM_SC"),
    )
    sol_match = _sol("S_MATCH", {"Q04_ad_hoc_operation": {"Q04_AD_HOC_OPERATION": 1.0}})
    mc_cfg = {"monte_carlo_draws": 60, "random_seed": 42, "weight_perturbation_sigma": 0.0}
    eng = ParticipantUtilityEngine(tmp_path, run_id="run_test")
    res = eng.evaluate(matrix, [sol_match], mc_cfg)

    # Even when coder B is silent, matched single-coder cell scores 1.0 (NOT diluted by 0.0 for coder B!)
    assert res.expected_utility_matrix[0, 0] == pytest.approx(1.0)
    # Q14 was ignored -> observed_subtopic_count == 1 (only Q04)
    assert res.participant_utilities[0].observed_subtopic_count == 1
    assert res.participant_utilities[0].single_coder_uncertainty_bounded is True


def test_robust_pareto_four_state_classification_synthetic(tmp_path: Path):
    """Verify mutual exclusivity across all 4 ADR-0008 RobustParetoStatus states."""
    from src.preference.utilities import UtilityEnsembleSummary

    (tmp_path / "data" / "raw").mkdir(parents=True)
    (tmp_path / "data" / "raw" / "survey_raw.csv").write_text("dummy\n", encoding="utf-8")

    sol_ids = ["S_CORE", "S_COND", "S_UNRES", "S_DOM"]
    sols = [_sol(sid, {"Q05_coordination_mechanism": {"scenario_1": 1.0}}) for sid in sol_ids]
    # Base utilities: S_CORE dominates S_DOM and S_UNRES, S_COND trades off or is dominated at baseline
    base_u = np.array([
        [0.90, 0.90],  # S_CORE
        [0.85, 0.85],  # S_COND (beats S_CORE in half of MC draws via dual-coder scenario)
        [0.50, 0.50],  # S_UNRES (dominated at baseline, flips nondominated on gap corner)
        [0.10, 0.10],  # S_DOM (always dominated)
    ], dtype=np.float64)

    n_draws = 10
    mc_u = np.repeat(base_u[None, :, :], n_draws, axis=0)
    regimes = []
    for d in range(n_draws):
        if d % 2 == 0:
            mc_u[d, 1] = [0.98, 0.80]  # S_COND beats S_CORE on P0 in CODER_A_REGIME
            c_reg = "CODER_A_REGIME"
        else:
            c_reg = "CODER_B_REGIME"
        regimes.append({
            "draw_index": d,
            "coder_regime": c_reg,
            "overlap_multiplier": 1.0,
            "interpretation_mode": "SAMPLED_INTERPRETATION_VARIANT",
            "omission_include_prob": 1.0,
            "conditional_mode": "UNIFORM_BRACKET",
        })

    # Coupled coding-gap corners: S_UNRES flips nondominated in corner_hi without dominating S_CORE; S_DOM stays dominated
    corner_lo = base_u.copy()
    corner_hi = base_u.copy()
    corner_hi[2] = [0.75, 0.99]  # S_UNRES beats S_CORE on P1 while S_CORE keeps P0 lead

    summary = UtilityEnsembleSummary(
        run_id="run_test",
        matrix_id="PM_TEST",
        participant_ids=["P1", "P2"],
        valid_participant_ids=["P1", "P2"],
        excluded_all_missing_participant_ids=[],
        solution_ids=sol_ids,
        question_ids_evaluated=["Q05"],
        participant_utilities=[],
        expected_utility_matrix=base_u,
        uniform_subtopic_utility_matrix=base_u,
        uniform_question_utility_matrix=base_u,
        ci_lower_matrix=base_u,
        ci_upper_matrix=base_u,
        min_scenario_matrix=base_u,
        max_scenario_matrix=base_u,
        min_coding_gap_matrix=corner_lo,
        max_coding_gap_matrix=corner_hi,
        coupled_gap_corner_matrices={"gap_lo": corner_lo, "gap_hi": corner_hi},
        mc_draws_utilities=mc_u,
        mc_draw_regimes=regimes,
        derived_barycenter_matrices={},
        interpretation_operator_audit={},
        participant_diagnostics={},
        question_diagnostics={},
    )
    mc_cfg = {"monte_carlo_draws": n_draws, "random_seed": 42, "veto_threshold": 0.35}
    base_pareto = ParetoAnalyzer(tmp_path, run_id="run_test").evaluate(
        matrix_id="PM_TEST",
        solution_ids=sol_ids,
        valid_participant_ids=["P1", "P2"],
        excluded_all_missing_participant_ids=[],
        utility_matrix=base_u,
        mc_config=mc_cfg,
    )
    rob_res, counts_bundle = RobustParetoEngine(tmp_path, run_id="run_test").evaluate(
        base_pareto=base_pareto,
        utility_summary=summary,
        solutions=sols,
        mc_config=mc_cfg,
        pareto_mc_config_rel_path="runs/run_test/pareto_mc_config.json",
    )

    assert rob_res.validate_invariants()
    assert counts_bundle["status_counts"] == {
        "ROBUSTLY_NONDOMINATED": 1,
        "CONDITIONALLY_NONDOMINATED": 1,
        "UNRESOLVED_DUE_TO_CODING_UNCERTAINTY": 1,
        "ROBUSTLY_DOMINATED": 1,
    }
    assert rob_res.robustly_nondominated_solution_ids == ["S_CORE"]
    assert rob_res.conditionally_nondominated_solution_ids == ["S_COND"]
    assert rob_res.unresolved_due_to_coding_uncertainty_ids == ["S_UNRES"]
    assert rob_res.robustly_dominated_solution_ids == ["S_DOM"]


def test_production_run_20261111_002_end_to_end_outputs_when_staged():
    """Verify full ADR-0008 Agent 04 outputs on run_20261111_002 whenever runtime artifacts are staged."""
    rec_path = REPO_ROOT / "data" / "processed" / "reconciliation" / "reconciled_evidence.json"
    pm_pq = REPO_ROOT / "data" / "processed" / "preference_matrix.parquet"
    qa_path = REPO_ROOT / "data" / "processed" / "preference" / "agent_04_qa_report.json"
    rob_path = REPO_ROOT / "data" / "processed" / "preference" / "robust_pareto_results.json"
    sol_path = REPO_ROOT / "data" / "processed" / "preference" / "feasible_alternatives.json"

    if not (rec_path.is_file() and pm_pq.is_file() and qa_path.is_file()):
        pytest.skip("Staged production runtime artifacts not present in clean CI clone.")

    qa = json.loads(qa_path.read_text(encoding="utf-8"))
    assert qa["all_qa_checks_passed"] is True
    for name, passed in qa["qa_checks"].items():
        assert passed is True, f"QA check {name} failed"

    # Parquet round-trip verification
    pm = load_preference_matrix(pm_pq)
    assert len(pm.cells) == 284
    assert pm.observed_usable_cell_count == 266
    assert pm.uncertainty_class_counts == {
        "CROSSWALK_PARTIAL_OR_UNALIGNED": 30,
        "DUAL_CODER_DISTRIBUTION_SET": 36,
        "INTERPRETATION_DIVERGENCE": 30,
        "NONE_CONSENSUS": 12,
        "PRESERVED_MISSINGNESS": 18,
        "SINGLE_CODER_PARTIAL_ID_GRANULARITY": 130,
        "SINGLE_CODER_PARTIAL_ID_OMISSION": 28,
    }

    # Verify Q14 strictly isolated & zero prohibited pruning
    sol_data = json.loads(sol_path.read_text(encoding="utf-8"))
    assert sol_data["generation_stats"]["prohibited_pruning_count"] == 0
    assert sol_data["generation_stats"]["contextual_questions_isolated"] == ["Q14"]
    assert sol_data["generation_stats"]["feasible_solution_count"] >= 50
    assert sol_data["generation_stats"]["pruned_solution_count"] > 0

    # Verify 4-state mutual exclusivity
    rob_data = json.loads(rob_path.read_text(encoding="utf-8"))
    rr_dict = rob_data["robust_pareto_result"]
    counts = rob_data["status_counts"]
    assert sum(counts.values()) == sol_data["generation_stats"]["feasible_solution_count"]
    assert rr_dict["pruned_by_clusters_values_or_disagreement"] is False
    all_bucket_ids = (
        rr_dict["robustly_dominated_solution_ids"]
        + rr_dict["robustly_nondominated_solution_ids"]
        + rr_dict["conditionally_nondominated_solution_ids"]
        + rr_dict["unresolved_due_to_coding_uncertainty_ids"]
    )
    assert len(all_bucket_ids) == len(set(all_bucket_ids)) == sum(counts.values())
