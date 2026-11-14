"""ADR-0008 Contract, Crosswalk, Uncertainty-Set, and Agent 04 Gate Verification Tests.

Validates alignment across src/contracts.py, schemas/interfaces.json, and
src/pipeline/orchestrator.py under ADR-0008.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from src.contracts import (
    ADR0008_SUPPORTING_CONTRACT_TYPES,
    ALL_CONTRACT_TYPES,
    AgreementStatus,
    CanonicalAlternativeCrosswalk,
    CodingResult,
    CrosswalkStatus,
    DerivedScenarioOrigin,
    FORBIDDEN_RECONCILIATION_METHODS,
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
    SingleCoderUncertaintyType,
    UncertaintyClass,
    UncertaintyEnvelope,
    UncertaintyRepresentationType,
)
from src.ingest.ingestion import ingest_survey
from src.pipeline.orchestrator import (
    Agent04ReleaseDecision,
    PipelineOrchestrator,
    PipelineState,
    evaluate_pipeline_state,
)
from src.registry.question_registry import QuestionRegistry, build_question_registry
from tests.test_pipeline import _build_valid_dual_coder_payloads

REPO_ROOT = Path(__file__).resolve().parent.parent


def _prov(rec_id: str = "rec_001") -> ProvenanceMeta:
    return ProvenanceMeta(
        record_id=rec_id,
        run_id="run_20261111_002",
        dataset_fingerprint="sha256:test",
        created_at_utc="2026-11-14T00:00:00Z",
        producer_module="tests.test_contracts_adr0008",
        producer_agent="agent_11",
    )


def test_interfaces_json_matches_adr0008_contracts_and_enums():
    iface_path = REPO_ROOT / "schemas" / "interfaces.json"
    data = json.loads(iface_path.read_text(encoding="utf-8"))

    assert data["crosswalk_statuses"] == [e.value for e in CrosswalkStatus]
    assert data["agreement_statuses"] == [e.value for e in AgreementStatus]
    assert data["uncertainty_classes"] == [e.value for e in UncertaintyClass]
    assert data["single_coder_uncertainty_types"] == [e.value for e in SingleCoderUncertaintyType]
    assert data["reconciliation_statuses"] == [e.value for e in ReconciliationStatus]
    assert data["derived_scenario_origins"] == [e.value for e in DerivedScenarioOrigin]
    assert data["uncertainty_representation_types"] == [e.value for e in UncertaintyRepresentationType]
    assert data["robust_pareto_statuses"] == [e.value for e in RobustParetoStatus]
    assert set(data["forbidden_reconciliation_methods"]) == set(FORBIDDEN_RECONCILIATION_METHODS)
    assert set(data["prohibited_pruning_sources"]) == set(PROHIBITED_PRUNING_SOURCES)

    ifaces = data["interfaces"]
    for name in ALL_CONTRACT_TYPES:
        assert name in ifaces
    for name in ADR0008_SUPPORTING_CONTRACT_TYPES:
        assert name in ifaces

    coding_opt = {f["name"]: f["type"] for f in ifaces["CodingResult"]["optional_fields"]}
    assert "CONFIDENCE_WEIGHTED_DISTRIBUTION" not in coding_opt["reconciliation_method"]
    assert "UNCERTAINTY_SET_PRESERVED" in coding_opt["reconciliation_method"]
    assert "NO_VALID_CROSSWALK_UNMERGED" in coding_opt["reconciliation_method"]
    assert "SINGLE_CODER_PARTIAL_ID" in coding_opt["reconciliation_method"]


def test_coding_result_rejects_forbidden_reconciliation_methods():
    for method in sorted(FORBIDDEN_RECONCILIATION_METHODS):
        with pytest.raises(ValueError, match="strictly forbidden by ADR-0008"):
            CodingResult(
                coding_id="cr_bad",
                participant_id="P001",
                question_id="Q06",
                subtopic_id="Q06_ST_01",
                coder_source="reconciled",
                missingness_state=MissingnessState.OBSERVED_USABLE,
                alternative_probabilities={"alt_a": 0.5, "alt_b": 0.5},
                semantic_importance=0.8,
                coder_confidence=0.9,
                coder_agreement=0.7,
                evidence_span_ids=["sp_1"],
                provenance=_prov("cr_bad"),
                reconciliation_method=method,  # type: ignore[arg-type]
            )


def test_preference_cell_forbids_silent_point_collapsing_when_uncertain():
    uset = PreferenceUncertaintySet(
        representation_type=UncertaintyRepresentationType.DISCRETE_CODER_SET,
        discrete_scenarios=[
            {"opt_a": 0.70, "opt_b": 0.30},
            {"opt_a": 0.25, "opt_b": 0.75},
        ],
        lower_bounds={"opt_a": 0.25, "opt_b": 0.30},
        upper_bounds={"opt_a": 0.70, "opt_b": 0.75},
    )

    # Valid uncertainty-preserving cell keeps resolved_point_distribution=None and alternative_probabilities={}
    valid_cell = PreferenceCell(
        cell_id="cell_q06_01",
        participant_id="P001",
        question_id="Q06",
        canonical_subtopic_id="Q06_ST_01",
        missingness_state=MissingnessState.OBSERVED_USABLE,
        coder_a_distribution={"opt_a": 0.70, "opt_b": 0.30},
        coder_b_distribution={"opt_a": 0.25, "opt_b": 0.75},
        agreement_status=AgreementStatus.DISTRIBUTION_DISAGREEMENT,
        uncertainty_class=UncertaintyClass.DUAL_CODER_DISTRIBUTION_SET,
        preference_uncertainty_set=uset,
        reconciliation_status=ReconciliationStatus.RESOLVED_WITH_UNCERTAINTY_SET,
        source_evidence_ids=["sp_a1", "sp_b1"],
        provenance=_prov("cell_q06_01"),
    )
    assert valid_cell.validate_simplex() is True
    assert valid_cell.resolved_point_distribution is None
    assert valid_cell.alternative_probabilities == {}

    # Attempting to supply an averaged point estimate must fail validation
    collapsed_cell = PreferenceCell(
        cell_id="cell_q06_collapsed",
        participant_id="P001",
        question_id="Q06",
        canonical_subtopic_id="Q06_ST_01",
        missingness_state=MissingnessState.OBSERVED_USABLE,
        alternative_probabilities={"opt_a": 0.475, "opt_b": 0.525},
        resolved_point_distribution={"opt_a": 0.475, "opt_b": 0.525},
        uncertainty_class=UncertaintyClass.DUAL_CODER_DISTRIBUTION_SET,
        preference_uncertainty_set=uset,
        reconciliation_status=ReconciliationStatus.RESOLVED_WITH_UNCERTAINTY_SET,
        source_evidence_ids=["sp_a1", "sp_b1"],
        provenance=_prov("cell_q06_collapsed"),
    )
    with pytest.raises(ValueError, match="resolved_point_distribution must be None"):
        collapsed_cell.validate_simplex()


def test_canonical_alternative_crosswalk_statuses_and_guards():
    # Exact / semantic / scenario matches must declare comparable=True and match (question_id, canonical_subtopic_id)
    for st in (
        CrosswalkStatus.EXACT_KEY_MATCH,
        CrosswalkStatus.SEMANTIC_KEY_MATCH,
        CrosswalkStatus.SCENARIO_PREFIX_MATCH,
    ):
        cw = CanonicalAlternativeCrosswalk(
            question_id="Q05",
            canonical_subtopic_id="Q05_ST_GOV",
            crosswalk_status=st,
            comparable=True,
            coder_a_to_canonical={"scenario_1_central": "OPT_CENTRAL"},
            coder_b_to_canonical={"centralized_model": "OPT_CENTRAL"},
            canonical_keys=["OPT_CENTRAL"],
            crosswalk_rule_id="CW_Q05_01",
        )
        assert cw.validate() is True

    # Scope mismatch must fail
    with pytest.raises(ValueError, match="scope_pair"):
        CanonicalAlternativeCrosswalk(
            question_id="Q05",
            canonical_subtopic_id="Q05_ST_GOV",
            crosswalk_status=CrosswalkStatus.EXACT_KEY_MATCH,
            comparable=True,
            scope_pair=("Q06", "Q05_ST_GOV"),
        )

    # PARTIAL_CROSSWALK requires explicit unmapped residual keys or mass
    with pytest.raises(ValueError, match="PARTIAL_CROSSWALK"):
        CanonicalAlternativeCrosswalk(
            question_id="Q08",
            canonical_subtopic_id="Q08_ST_MGMT",
            crosswalk_status=CrosswalkStatus.PARTIAL_CROSSWALK,
            comparable=True,
            canonical_keys=["OPT_A"],
        )

    partial_cw = CanonicalAlternativeCrosswalk(
        question_id="Q08",
        canonical_subtopic_id="Q08_ST_MGMT",
        crosswalk_status=CrosswalkStatus.PARTIAL_CROSSWALK,
        comparable=True,
        coder_a_to_canonical={"a1": "OPT_A"},
        coder_b_to_canonical={"b1": "OPT_A"},
        canonical_keys=["OPT_A"],
        unmapped_keys_b=["b_extra"],
        unmapped_mass_b=0.25,
    )
    assert partial_cw.validate() is True

    # NO_VALID_CROSSWALK forbids merged keys or comparable=True
    with pytest.raises(ValueError, match="NO_VALID_CROSSWALK"):
        CanonicalAlternativeCrosswalk(
            question_id="Q09",
            canonical_subtopic_id="Q09_ST_01",
            crosswalk_status=CrosswalkStatus.NO_VALID_CROSSWALK,
            comparable=False,
            canonical_keys=["ILLEGAL_MERGE"],
        )

    no_cw = CanonicalAlternativeCrosswalk(
        question_id="Q09",
        canonical_subtopic_id="Q09_ST_01",
        crosswalk_status=CrosswalkStatus.NO_VALID_CROSSWALK,
        comparable=False,
        unmapped_keys_a=["frame_x"],
        unmapped_keys_b=["frame_y"],
        unmapped_mass_a=1.0,
        unmapped_mass_b=1.0,
    )
    disjoint_set = PreferenceUncertaintySet(
        representation_type=UncertaintyRepresentationType.DISJOINT_CODER_HYPOTHESES,
        disjoint_coder_hypotheses={
            "coder_a": {"frame_x": 1.0},
            "coder_b": {"frame_y": 1.0},
        },
    )
    disjoint_cell = PreferenceCell(
        cell_id="cell_disjoint",
        participant_id="P002",
        question_id="Q09",
        canonical_subtopic_id="Q09_ST_01",
        missingness_state=MissingnessState.OBSERVED_USABLE,
        coder_a_distribution={"frame_x": 1.0},
        coder_b_distribution={"frame_y": 1.0},
        canonical_alternative_crosswalk=no_cw,
        agreement_status=AgreementStatus.VOCABULARY_MISMATCH,
        uncertainty_class=UncertaintyClass.CROSSWALK_PARTIAL_OR_UNALIGNED,
        preference_uncertainty_set=disjoint_set,
        reconciliation_status=ReconciliationStatus.UNRESOLVED_CROSSWALK,
        provenance=_prov("cell_disjoint"),
    )
    assert disjoint_cell.validate_simplex() is True


def test_missingness_preservation_rejects_fabricated_scenarios_and_point_dists():
    for state in (
        MissingnessState.UNOBSERVED_MISSING,
        MissingnessState.MISSING_NON_SUBSTANTIVE,
        MissingnessState.NOT_MENTIONED_IN_RESPONSE,
    ):
        empty_set = PreferenceUncertaintySet(representation_type=UncertaintyRepresentationType.EMPTY_MISSING)
        ok_cell = PreferenceCell(
            cell_id=f"cell_{state.value}",
            participant_id="P003",
            question_id="Q02",
            canonical_subtopic_id="Q02_ST_01",
            missingness_state=state,
            uncertainty_class=UncertaintyClass.PRESERVED_MISSINGNESS,
            preference_uncertainty_set=empty_set,
            reconciliation_status=ReconciliationStatus.PRESERVED_MISSING_OR_NON_PREFERENCE,
            provenance=_prov(f"cell_{state.value}"),
        )
        assert ok_cell.validate_simplex() is True

        bad_cell = PreferenceCell(
            cell_id=f"bad_{state.value}",
            participant_id="P003",
            question_id="Q02",
            canonical_subtopic_id="Q02_ST_01",
            missingness_state=state,
            resolved_point_distribution={"opt_a": 1.0},
            provenance=_prov(f"bad_{state.value}"),
        )
        with pytest.raises(ValueError, match="must keep resolved_point_distribution=None"):
            bad_cell.validate_simplex()


def test_single_coder_partial_id_forbids_zero_imputation_on_silent_coder():
    for u_cls, sc_type in (
        (
            UncertaintyClass.SINGLE_CODER_PARTIAL_ID_OMISSION,
            SingleCoderUncertaintyType.SINGLE_CODER_PARTICIPANT_OMISSION,
        ),
        (
            UncertaintyClass.SINGLE_CODER_PARTIAL_ID_GRANULARITY,
            SingleCoderUncertaintyType.SINGLE_CODER_SUBTOPIC_GRANULARITY,
        ),
    ):
        sc_set = PreferenceUncertaintySet(
            representation_type=UncertaintyRepresentationType.SINGLE_CODER_PARTIAL_ID,
            discrete_scenarios=[{"opt_a": 0.8, "opt_b": 0.2}],
            single_coder_active_side="coder_a",
            single_coder_uncertainty_type=sc_type,
            non_coding_coder_state="EPISTEMICALLY_UNOBSERVED",
        )
        valid = PreferenceCell(
            cell_id=f"cell_{u_cls.value}",
            participant_id="P004",
            question_id="Q07",
            canonical_subtopic_id="Q07_ST_03",
            missingness_state=MissingnessState.OBSERVED_USABLE,
            coder_a_distribution={"opt_a": 0.8, "opt_b": 0.2},
            coder_b_distribution=None,
            agreement_status=AgreementStatus.SINGLE_CODER_ONLY,
            uncertainty_class=u_cls,
            preference_uncertainty_set=sc_set,
            reconciliation_status=ReconciliationStatus.RESOLVED_WITH_UNCERTAINTY_SET,
            provenance=_prov("sc_ok"),
        )
        assert valid.validate_simplex() is True

        # Silent coder filled with 0.0 distribution violates simplex & partial-ID rule
        zero_filled = PreferenceCell(
            cell_id=f"bad_{u_cls.value}",
            participant_id="P004",
            question_id="Q07",
            canonical_subtopic_id="Q07_ST_03",
            missingness_state=MissingnessState.OBSERVED_USABLE,
            coder_a_distribution={"opt_a": 0.8, "opt_b": 0.2},
            coder_b_distribution={"opt_a": 0.0, "opt_b": 0.0},
            uncertainty_class=u_cls,
            preference_uncertainty_set=sc_set,
            provenance=_prov("sc_zero"),
        )
        with pytest.raises(ValueError):
            zero_filled.validate_simplex()


def test_issue_005_interpretation_divergence_cannot_be_exact_agreement():
    div_set = PreferenceUncertaintySet(
        representation_type=UncertaintyRepresentationType.DISCRETE_CODER_SET,
        discrete_scenarios=[{"opt_a": 0.6, "opt_b": 0.4}],
        interpretation_variants=[
            "epistemic_uncertainty_over_preference",
            "explicit_mixed_preference",
        ],
    )
    ok_cell = PreferenceCell(
        cell_id="cell_interp_div",
        participant_id="P005",
        question_id="Q04",
        canonical_subtopic_id="Q04_ST_01",
        missingness_state=MissingnessState.OBSERVED_USABLE,
        coder_a_distribution={"opt_a": 0.6, "opt_b": 0.4},
        coder_b_distribution={"opt_a": 0.6, "opt_b": 0.4},
        coder_a_probability_interpretation="epistemic_uncertainty_over_preference",
        coder_b_probability_interpretation="explicit_mixed_preference",
        agreement_status=AgreementStatus.DISTRIBUTION_AGREEMENT_INTERP_FLAGGED,
        uncertainty_class=UncertaintyClass.INTERPRETATION_DIVERGENCE,
        preference_uncertainty_set=div_set,
        reconciliation_status=ReconciliationStatus.AGREEMENT_DISTRIBUTION_ONLY_INTERPRETATION_FLAGGED,
        provenance=_prov("cell_interp_div"),
    )
    assert ok_cell.validate_simplex() is True

    illegal_exact = PreferenceCell(
        cell_id="cell_interp_exact",
        participant_id="P005",
        question_id="Q04",
        canonical_subtopic_id="Q04_ST_01",
        missingness_state=MissingnessState.OBSERVED_USABLE,
        coder_a_distribution={"opt_a": 0.6, "opt_b": 0.4},
        coder_b_distribution={"opt_a": 0.6, "opt_b": 0.4},
        coder_a_probability_interpretation="epistemic_uncertainty_over_preference",
        coder_b_probability_interpretation="explicit_mixed_preference",
        agreement_status=AgreementStatus.EXACT_AGREEMENT,
        uncertainty_class=UncertaintyClass.INTERPRETATION_DIVERGENCE,
        preference_uncertainty_set=div_set,
        reconciliation_status=ReconciliationStatus.AGREEMENT_EXACT,
        provenance=_prov("cell_interp_exact"),
    )
    with pytest.raises(ValueError, match="differing probability_interpretation"):
        illegal_exact.validate_simplex()


def test_derived_scenarios_require_derived_origin_and_bounds_check():
    with pytest.raises(ValueError, match="derived scenario_origin"):
        PreferenceUncertaintySet(
            representation_type=UncertaintyRepresentationType.DISCRETE_CODER_SET,
            discrete_scenarios=[{"opt_a": 0.8, "opt_b": 0.2}],
            allows_derived_convex_hull=True,
            derived_scenarios=[
                {
                    "probabilities": {"opt_a": 0.5, "opt_b": 0.5},
                    "scenario_origin": DerivedScenarioOrigin.OBSERVED_CODER_EVIDENCE.value,
                }
            ],
        )

    with pytest.raises(ValueError, match="bounds inverted"):
        PreferenceUncertaintySet(
            representation_type=UncertaintyRepresentationType.DISCRETE_CODER_SET,
            discrete_scenarios=[{"opt_a": 0.8, "opt_b": 0.2}],
            lower_bounds={"opt_a": 0.9},
            upper_bounds={"opt_a": 0.4},
        )


def test_utility_and_pareto_non_pruning_and_4_state_robust_classification():
    # Coder confidence MUST NOT be used as a utility weight
    with pytest.raises(ValueError, match="coder_confidence must NEVER"):
        ParticipantUtility(
            utility_id="u_bad",
            participant_id="P001",
            solution_id="SOL_01",
            preference_matrix_id="PM_01",
            missingness_state=MissingnessState.OBSERVED_USABLE,
            observed_subtopic_count=5,
            total_subtopic_count=6,
            point_utility=0.75,
            utility_ci_lower_95=0.60,
            utility_ci_upper_95=0.90,
            utility_std_error=0.08,
            mean_coder_confidence=0.9,
            mean_coder_agreement=0.85,
            uses_coder_confidence_as_weight=True,
            provenance=_prov("u_bad"),
        )

    # Solutions & FeasibleAlternatives reject cluster/value/disagreement pruning
    with pytest.raises(ValueError, match="pruning by clusters or values is forbidden"):
        FeasibleAlternative(
            alternative_id="FA_BAD",
            question_id="Q07",
            label_en="Alt",
            description_en="Desc",
            subtopic_alternative_allocations={"ST_1": {"opt_a": 1.0}},
            active_subtopic_mask={"ST_1": True},
            supporting_participant_count=10,
            missing_participant_count=2,
            feasibility_status="FEASIBLE",
            empirical_support_uncertainty=UncertaintyEnvelope(point_estimate=0.8),
            pruned_by_clusters_or_values=True,
            provenance=_prov("fa_bad"),
        )

    with pytest.raises(ValueError, match="never clusters, values, coder disagreement, or confidence"):
        GovernanceSolution(
            solution_id="SOL_BAD",
            label_en="Sol",
            question_alternatives={"Q07": "ALT_1"},
            global_alternative_profile={"Q07": {"ALT_1": 1.0}},
            included_question_ids=["Q07"],
            diagnostic_context_question_ids=[],
            logical_constraints_satisfied=[],
            institutional_constraints_satisfied=[],
            dependencies_satisfied=[],
            feasibility_evaluation_status="STRICTLY_FEASIBLE",
            generation_method="COMBINATORIAL_CONSTRAINT_SATISFACTION",
            pruned_by_coder_disagreement=True,
            provenance=_prov("sol_bad"),
        )

    # 4-state RobustParetoResult enforces mutual exclusivity and non-pruning
    with pytest.raises(ValueError, match="mutually exclusive"):
        RobustParetoResult(
            robust_pareto_id="RP_DUP",
            base_pareto_result_id="PR_01",
            monte_carlo_draws=100,
            random_seed=42,
            pareto_mc_config_path=None,
            frontier_inclusion_probabilities={"SOL_1": 1.0, "SOL_2": 0.4},
            robust_frontier_solution_ids=["SOL_1"],
            criterion_top1_probabilities={"utilitarian": {"SOL_1": 0.8, "SOL_2": 0.2}},
            utility_metric_intervals={},
            missing_participant_ids_preserved=[],
            robustly_nondominated_solution_ids=["SOL_1"],
            conditionally_nondominated_solution_ids=["SOL_1"],
            provenance=_prov("rp_dup"),
        )

    valid_rp = RobustParetoResult(
        robust_pareto_id="RP_OK",
        base_pareto_result_id="PR_01",
        monte_carlo_draws=200,
        random_seed=42,
        pareto_mc_config_path=None,
        frontier_inclusion_probabilities={"SOL_1": 1.0, "SOL_2": 0.6, "SOL_3": 0.0, "SOL_4": 0.5},
        robust_frontier_solution_ids=["SOL_1"],
        criterion_top1_probabilities={"utilitarian": {"SOL_1": 0.7}},
        utility_metric_intervals={},
        missing_participant_ids_preserved=["P099"],
        solution_robustness_statuses={
            "SOL_1": RobustParetoStatus.ROBUSTLY_NONDOMINATED,
            "SOL_2": RobustParetoStatus.CONDITIONALLY_NONDOMINATED,
            "SOL_3": RobustParetoStatus.ROBUSTLY_DOMINATED,
            "SOL_4": RobustParetoStatus.UNRESOLVED_DUE_TO_CODING_UNCERTAINTY,
        },
        robustly_nondominated_solution_ids=["SOL_1"],
        conditionally_nondominated_solution_ids=["SOL_2"],
        robustly_dominated_solution_ids=["SOL_3"],
        unresolved_due_to_coding_uncertainty_ids=["SOL_4"],
        conditional_nondominated_regimes={"SOL_2": ["explicit_mixed_preference"]},
        derived_scenario_origins_used=[DerivedScenarioOrigin.OBSERVED_CODER_EVIDENCE],
        provenance=_prov("rp_ok"),
    )
    assert valid_rp.validate_invariants() is True


def test_agent_04_release_gate_blocked_on_current_repo():
    report = evaluate_pipeline_state(base_dir=REPO_ROOT, run_id="run_20261111_002", write_log=False)
    assert report.agent_04_release_decision == Agent04ReleaseDecision.BLOCKED
    assert report.states[PipelineState.AGENT_04_RELEASE_READY.value] is False
    assert report.agent_04_release_checklist["2_adr_0008_approved"] is True
    assert report.agent_04_release_checklist["3_shared_contracts_adr0008_aligned"] is True
    assert report.agent_04_release_checklist["4_adr_0008_contract_tests_present"] is True
    assert report.agent_04_release_checklist["9_freshness_and_hardcoding_pass"] is True
    assert report.agent_04_release_checklist["1_agent_03_release_ready"] is False
    assert report.agent_04_release_checklist["6_agent_03_outputs_exist"] is False
    assert report.agent_04_release_checklist["7_agent_03_crosswalk_and_uncertainty_sets_valid"] is False
    assert report.agent_04_release_checklist["8_agent_03_artifacts_registered_in_manifest"] is False


def test_agent_04_release_gate_requires_all_9_conditions_to_pass(tmp_path):
    for subdir in [
        "src",
        "docs",
        "notebooks",
        "schemas",
        "tests",
        "data/raw",
        "data/normalized",
        "data/processed/reconciliation",
        "runs/run_20261111_002",
    ]:
        (tmp_path / subdir).mkdir(parents=True, exist_ok=True)

    shutil.copy2(REPO_ROOT / "AGENTS.md", tmp_path / "AGENTS.md")
    shutil.copy2(REPO_ROOT / "README.md", tmp_path / "README.md")
    shutil.copy2(REPO_ROOT / "pyproject.toml", tmp_path / "pyproject.toml")
    shutil.copy2(REPO_ROOT / "data" / "raw" / "survey_raw.csv", tmp_path / "data" / "raw" / "survey_raw.csv")
    shutil.copy2(
        REPO_ROOT / "runs" / "run_20261111_002" / "gpu_runtime_config.json",
        tmp_path / "runs" / "run_20261111_002" / "gpu_runtime_config.json",
    )
    shutil.copy2(
        REPO_ROOT / "runs" / "run_20261111_002" / "alternative_crosswalk.json",
        tmp_path / "runs" / "run_20261111_002" / "alternative_crosswalk.json",
    )

    shutil.copytree(REPO_ROOT / "src", tmp_path / "src", dirs_exist_ok=True)
    shutil.copytree(REPO_ROOT / "docs", tmp_path / "docs", dirs_exist_ok=True)
    shutil.copytree(REPO_ROOT / "notebooks", tmp_path / "notebooks", dirs_exist_ok=True)
    shutil.copytree(REPO_ROOT / "schemas", tmp_path / "schemas", dirs_exist_ok=True)
    shutil.copytree(REPO_ROOT / "tests", tmp_path / "tests", dirs_exist_ok=True)

    # Mark ISSUE-005 resolved in temp workspace only
    oi_path = tmp_path / "docs" / "OPEN_ISSUES.md"
    oi_text = oi_path.read_text(encoding="utf-8").replace(
        "| `ISSUE-005` | `HIGH` | Agent 04 | `src/preference/` |",
        "| `ISSUE-005` | `HIGH` | Agent 04 | `src/preference/` |",
    )
    lines = [
        ln.replace("| `OPEN` |", "| `RESOLVED` |") if "`ISSUE-005`" in ln else ln
        for ln in oi_text.splitlines()
    ]
    oi_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Populate manifest with valid Agent 03 entries conforming to ArtifactRecord
    manifest = json.loads((REPO_ROOT / "runs" / "run_20261111_002" / "manifest.json").read_text(encoding="utf-8"))
    for aid, path in (
        ("themes_codebook_v1", "data/processed/themes_codebook.json"),
        ("candidate_options_v1", "data/processed/candidate_options.json"),
        ("reconciled_evidence_v1", "data/processed/reconciliation/reconciled_evidence.json"),
    ):
        manifest["artifacts"][aid] = {
            "artifact_id": aid,
            "run_id": "run_20261111_002",
            "path": path,
            "format": "json",
            "producing_module": "src/evidence/reconciliation.py",
            "producing_agent": "agent_03",
            "creation_timestamp": "2026-11-14T12:00:00+00:00",
            "code_commit": "cfe7c6f43d5213a3ae90e9bccd9c7ea9078110f6",
            "source_hashes": {},
            "schema_version": "v1.1.0",
            "validation_status": "valid",
            "upstream_artifacts": ["norm_answers_v1"],
            "downstream_consumers": ["agent_04"],
            "stale_state": "fresh",
            "authority_level": "canonical_intermediate",
        }
    (tmp_path / "runs" / "run_20261111_002" / "manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

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
    (tmp_path / "runs" / "run_20261111_002" / "gpu_runtime_benchmark.json").write_text(
        json.dumps(bench_payload, indent=2),
        encoding="utf-8",
    )

    reg = QuestionRegistry(raw_csv_path=tmp_path / "data" / "raw" / "survey_raw.csv")
    specs = reg.build_from_answers(df_norm)
    payload_a, payload_b = _build_valid_dual_coder_payloads(df_norm, specs)
    proc_dir = tmp_path / "data" / "processed"
    (proc_dir / "coder_a_outputs.json").write_text(json.dumps(payload_a), encoding="utf-8")
    (proc_dir / "coder_b_outputs.json").write_text(json.dumps(payload_b), encoding="utf-8")
    (proc_dir / "themes_codebook.json").write_text(json.dumps({"themes": []}), encoding="utf-8")
    (proc_dir / "candidate_options.json").write_text(json.dumps({"candidate_options": []}), encoding="utf-8")
    (proc_dir / "reconciliation" / "reconciliation_qa_report.json").write_text(
        json.dumps({"run_id": "run_20261111_002", "all_reconciliation_invariants_passed": True}),
        encoding="utf-8",
    )

    valid_reconciled_record: dict[str, Any] = {
        "record_id": "rec_001",
        "crosswalk_status": CrosswalkStatus.EXACT_KEY_MATCH.value,
        "uncertainty_class": UncertaintyClass.DUAL_CODER_DISTRIBUTION_SET.value,
        "preference_uncertainty_set": {
            "representation_type": UncertaintyRepresentationType.DISCRETE_CODER_SET.value,
            "discrete_scenarios": [{"option_a": 0.7, "option_b": 0.3}, {"option_a": 0.5, "option_b": 0.5}],
        },
        "resolved_point_distribution": None,
    }
    rec_ev_path = proc_dir / "reconciliation" / "reconciled_evidence.json"
    rec_ev_path.write_text(
        json.dumps({"preference_reconciliation_records": [valid_reconciled_record]}),
        encoding="utf-8",
    )

    orch = PipelineOrchestrator(base_dir=tmp_path, run_id="run_20261111_002")
    ready = orch.evaluate(write_log=False)
    assert ready.agent_03_release_checklist["1_agent_01_real_ingestion_pass"] is True
    assert all(ready.agent_04_release_checklist.values())
    assert ready.agent_04_release_decision == Agent04ReleaseDecision.READY
    assert ready.states[PipelineState.AGENT_04_RELEASE_READY.value] is True

    # Invalid uncertainty record with collapsed resolved_point_distribution immediately blocks Agent 04
    bad_record = dict(valid_reconciled_record)
    bad_record["resolved_point_distribution"] = {"option_a": 0.6, "option_b": 0.4}
    rec_ev_path.write_text(
        json.dumps({"preference_reconciliation_records": [bad_record]}),
        encoding="utf-8",
    )
    blocked = orch.evaluate(write_log=False)
    assert blocked.agent_04_release_decision == Agent04ReleaseDecision.BLOCKED
    assert blocked.agent_04_release_checklist["7_agent_03_crosswalk_and_uncertainty_sets_valid"] is False
