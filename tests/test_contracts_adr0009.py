"""ADR-0009 Resource-Good Regimes, Club-Good Operational Contracts & Frontier-B Gate Tests.

Validates alignment across src/contracts.py, schemas/interfaces.json,
runs/run_20261111_002/counterfactual_regime_config.json, and src/pipeline/orchestrator.py
without mutating OBSERVED_DESIGN_FRONTIER (FRONTIER_A).
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from src.contracts import (
    ADR0009_SUPPORTING_CONTRACT_TYPES,
    COUNTERFACTUAL_PROHIBITED_PRUNING_SOURCES,
    FRONTIER_A_NAMESPACE,
    FRONTIER_B_NAMESPACE,
    FRONTIER_NAMESPACES,
    AccessRuleType,
    ClubGoodContract,
    ClubGoodMechanism,
    CounterfactualParetoStatus,
    CounterfactualPreferenceMapping,
    CounterfactualSolutionMetadata,
    CounterfactualUtilityBound,
    CounterfactualUtilityIdentification,
    ExcludabilityLevel,
    ExitPolicyType,
    FinancingRuleType,
    FrontierComparisonResult,
    FrontierNamespace,
    GoodRegimeType,
    MissingnessState,
    PreferenceCell,
    ProvenanceCategory,
    ProvenanceMeta,
    ResourceEligibilityAssessment,
    ResourceEligibilityStatus,
    ResourceRegimeSpec,
    RivalryLevel,
    validate_provenance_boundary,
)
from src.pipeline.orchestrator import (
    Agent08ReportingStatus,
    Agent08TechnicalReleaseDecision,
    PipelineOrchestrator,
    PipelineState,
    ResourceRegimeExpansionReleaseDecision,
    evaluate_pipeline_state,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def _prov(rec_id: str = "adr9_rec") -> ProvenanceMeta:
    return ProvenanceMeta(
        record_id=rec_id,
        run_id="run_20261111_002",
        dataset_fingerprint="sha256:test",
        created_at_utc="2026-11-14T00:00:00Z",
        producer_module="tests.test_contracts_adr0009",
        producer_agent="agent_11",
    )


def _valid_club_mechanism(**overrides: Any) -> ClubGoodMechanism:
    params: dict[str, Any] = {
        "member_contribution_rule": "proportional_overhead_share",
        "non_member_compulsory_contribution": 0.0,
        "member_access": AccessRuleType.MEMBER_PRIORITY,
        "non_member_access": AccessRuleType.RESIDUAL_CAPACITY,
        "member_priority": "Club members hold primary draw entitlement",
        "exit_rule": ExitPolicyType.ALLOWED,
        "capacity_or_congestion_rule": "FIFO capacity allocation above shared pool reserve floor",
        "governance_rule": "Participating PI assembly quorum with ring-fenced ledger",
        "pricing_or_contribution_rule": "Voluntary member fee only; zero compulsory non-member levy",
    }
    params.update(overrides)
    return ClubGoodMechanism(**params)


def test_interfaces_json_matches_adr0009_contracts_and_enums():
    iface_path = REPO_ROOT / "schemas" / "interfaces.json"
    data = json.loads(iface_path.read_text(encoding="utf-8"))

    assert data["frontier_namespaces"] == list(FRONTIER_NAMESPACES)
    assert data["frontier_namespaces"] == [
        "OBSERVED_DESIGN_FRONTIER",
        "RESOURCE_REGIME_EXPANDED_FRONTIER",
    ]
    assert set(data["counterfactual_prohibited_pruning_sources"]) == set(
        COUNTERFACTUAL_PROHIBITED_PRUNING_SOURCES
    )
    assert "GOODS_TAXONOMY" in data["counterfactual_prohibited_pruning_sources"]
    assert "RESOURCE_ELIGIBILITY" in data["counterfactual_prohibited_pruning_sources"]

    assert data["resource_eligibility_statuses"] == [e.value for e in ResourceEligibilityStatus]
    assert data["rivalry_levels"] == [e.value for e in RivalryLevel]
    assert data["excludability_levels"] == [e.value for e in ExcludabilityLevel]
    assert data["financing_rule_types"] == [e.value for e in FinancingRuleType]
    assert data["access_rule_types"] == [e.value for e in AccessRuleType]
    assert data["exit_policy_types"] == [e.value for e in ExitPolicyType]
    assert data["good_regime_types"] == [e.value for e in GoodRegimeType]
    assert data["provenance_categories"] == [e.value for e in ProvenanceCategory]
    assert data["counterfactual_utility_identifications"] == [
        e.value for e in CounterfactualUtilityIdentification
    ]
    assert data["counterfactual_pareto_statuses"] == [e.value for e in CounterfactualParetoStatus]

    ifaces = data["interfaces"]
    for name in ADR0009_SUPPORTING_CONTRACT_TYPES:
        assert name in ifaces

    pref_opt = {f["name"]: f["type"] for f in ifaces["PreferenceCell"]["optional_fields"]}
    assert "provenance_category" in pref_opt
    assert "ProvenanceCategory" in pref_opt["provenance_category"]


def test_resource_eligibility_prevents_forced_labeling_and_enforces_tier_segregation():
    eligible = ResourceEligibilityAssessment(
        subtopic_id="Q11_overhead_allocation_mechanism",
        question_id="Q11",
        eligibility_status=ResourceEligibilityStatus.ELIGIBLE,
        analytical_rationale="Allocable indirect overhead revenue pool.",
        resource_evidence_basis="REVENUE_OVERHEAD_POOL",
        assigned_regime_types=[GoodRegimeType.PRIVATE_GOOD, GoodRegimeType.CLUB_GOOD],
    )
    assert eligible.validate() is True

    # Pure opinions / perceptions can never be marked ELIGIBLE or CONDITIONAL
    with pytest.raises(ValueError, match="must remain INELIGIBLE"):
        ResourceEligibilityAssessment(
            subtopic_id="Q01_pole_relevance",
            question_id="Q01",
            eligibility_status=ResourceEligibilityStatus.ELIGIBLE,
            analytical_rationale="Attempted forced label.",
            resource_evidence_basis="ALLOCABLE_BUDGET_POOL",
            is_pure_opinion_or_perception=True,
        )

    # CONDITIONAL_RESOURCE_ONLY requires explicit segregated sensitivity tier (e.g., Q-G)
    with pytest.raises(ValueError, match="segregated_tier_id"):
        ResourceEligibilityAssessment(
            subtopic_id="Q08_hr_management_level",
            question_id="Q08",
            eligibility_status=ResourceEligibilityStatus.CONDITIONAL_RESOURCE_ONLY,
            analytical_rationale="Shared HR capacity tier.",
            resource_evidence_basis="SHARED_SERVICE_CAPACITY",
            requires_segregated_sensitivity_tier=False,
        )

    # INELIGIBLE / UNKNOWN subtopics reject GoodRegimeType assignments
    with pytest.raises(ValueError, match="cannot receive GoodRegimeType assignments"):
        ResourceEligibilityAssessment(
            subtopic_id="Q07_engagement_level",
            question_id="Q07",
            eligibility_status=ResourceEligibilityStatus.INELIGIBLE,
            analytical_rationale="Legal signing mandate rule.",
            assigned_regime_types=[GoodRegimeType.PUBLIC_GOOD],
        )


def test_resource_regime_spec_rejects_intrinsic_ontological_essence_and_bad_combinations():
    # Multiple regimes for one subtopic are supported (non-ontological)
    spec_private = ResourceRegimeSpec(
        regime_id="REG_Q11_PRIV",
        subtopic_id="Q11_overhead_allocation_mechanism",
        question_id="Q11",
        regime_type=GoodRegimeType.PRIVATE_GOOD,
        rivalry=RivalryLevel.RIVAL,
        excludability=ExcludabilityLevel.EXCLUDABLE,
        financing=FinancingRuleType.INDIVIDUAL,
        access=AccessRuleType.OWNER_ONLY,
        exit_policy=ExitPolicyType.NOT_APPLICABLE,
    )
    spec_club = ResourceRegimeSpec(
        regime_id="REG_Q11_CLUB",
        subtopic_id="Q11_overhead_allocation_mechanism",
        question_id="Q11",
        regime_type=GoodRegimeType.CLUB_GOOD,
        rivalry=RivalryLevel.RIVAL,
        excludability=ExcludabilityLevel.EXCLUDABLE,
        financing=FinancingRuleType.VOLUNTARY_MEMBER,
        access=AccessRuleType.MEMBER_PRIORITY,
        exit_policy=ExitPolicyType.ALLOWED,
        club_good_mechanism=_valid_club_mechanism(),
    )
    assert spec_private.allows_multiple_regimes is True
    assert spec_club.allows_multiple_regimes is True

    # Reject ontological claim
    with pytest.raises(ValueError, match="ontological"):
        ResourceRegimeSpec(
            regime_id="REG_ONTO",
            subtopic_id="Q11_overhead_allocation_mechanism",
            question_id="Q11",
            regime_type=GoodRegimeType.PUBLIC_GOOD,
            rivalry=RivalryLevel.NON_RIVAL,
            excludability=ExcludabilityLevel.NON_EXCLUDABLE,
            financing=FinancingRuleType.COLLECTIVE,
            access=AccessRuleType.OPEN_ACCESS,
            exit_policy=ExitPolicyType.NOT_APPLICABLE,
            is_intrinsic_ontological_label=True,
        )

    # Reject INELIGIBLE subtopic entering regime expansion
    with pytest.raises(ValueError, match="cannot enter resource regime expansion"):
        ResourceRegimeSpec(
            regime_id="REG_INELIG",
            subtopic_id="Q07_engagement_level",
            question_id="Q07",
            regime_type=GoodRegimeType.PUBLIC_GOOD,
            rivalry=RivalryLevel.NON_RIVAL,
            excludability=ExcludabilityLevel.NON_EXCLUDABLE,
            financing=FinancingRuleType.INSTITUTIONAL,
            access=AccessRuleType.OPEN_ACCESS,
            exit_policy=ExitPolicyType.NOT_APPLICABLE,
            eligibility_status=ResourceEligibilityStatus.INELIGIBLE,
        )


def test_club_good_10_field_contract_and_bare_label_rejection():
    assert ClubGoodContract is ClubGoodMechanism

    # Bare CLUB_GOOD label without 10-field ClubGoodMechanism fails immediately
    with pytest.raises(ValueError, match="bare label"):
        ResourceRegimeSpec(
            regime_id="REG_BARE_CLUB",
            subtopic_id="Q11_overhead_allocation_mechanism",
            question_id="Q11",
            regime_type=GoodRegimeType.CLUB_GOOD,
            rivalry=RivalryLevel.RIVAL,
            excludability=ExcludabilityLevel.EXCLUDABLE,
            financing=FinancingRuleType.VOLUNTARY_MEMBER,
            access=AccessRuleType.MEMBER_PRIORITY,
            exit_policy=ExitPolicyType.ALLOWED,
            club_good_mechanism=None,
        )

    # Non-zero non_member_compulsory_contribution rejected
    with pytest.raises(ValueError, match="non_member_compulsory_contribution == 0.0"):
        _valid_club_mechanism(non_member_compulsory_contribution=0.05)

    # Compulsory membership rejected
    with pytest.raises(ValueError, match="VOLUNTARY"):
        _valid_club_mechanism(voluntary_membership=False)

    # Non-member entitlement >= member entitlement rejected
    with pytest.raises(ValueError, match="strictly higher member entitlement"):
        _valid_club_mechanism(
            member_access=AccessRuleType.RESIDUAL_CAPACITY,
            non_member_access=AccessRuleType.MEMBER_PRIORITY,
        )

    # Constrained exit requires explicit governing_constraint_id
    with pytest.raises(ValueError, match="governing_constraint_id"):
        _valid_club_mechanism(exit_rule=ExitPolicyType.CONSTRAINED, governing_constraint_id=None)

    constrained_ok = _valid_club_mechanism(
        exit_rule=ExitPolicyType.CONSTRAINED,
        governing_constraint_id="IC-Q07-Q09-DELEGATION-LIABILITY",
    )
    assert constrained_ok.validate() is True


def test_preference_cell_rejects_non_observed_provenance_boundary():
    obs_cell = PreferenceCell(
        cell_id="C_OBS",
        participant_id="PARTICIPANT_001",
        question_id="Q11",
        canonical_subtopic_id="Q11_overhead_allocation_mechanism",
        missingness_state=MissingnessState.OBSERVED_USABLE,
        alternative_probabilities={"pi": 1.0},
        evidence_span_ids=["SP_1"],
        provenance=_prov("C_OBS"),
    )
    assert obs_cell.provenance_category == ProvenanceCategory.OBSERVED_RESPONDENT_PREFERENCE
    assert obs_cell.validate_simplex() is True

    for forbidden_prov in (
        ProvenanceCategory.INSTITUTIONALLY_DERIVED_MECHANISM,
        ProvenanceCategory.COUNTERFACTUAL_PREFERENCE_ASSUMPTION,
    ):
        with pytest.raises(ValueError, match="OBSERVED_RESPONDENT_PREFERENCE provenance only"):
            PreferenceCell(
                cell_id="C_BAD",
                participant_id="PARTICIPANT_001",
                question_id="Q11",
                provenance_category=forbidden_prov,
                provenance=_prov("C_BAD"),
            )


def test_refusal_to_pay_cannot_become_observed_club_preference():
    # Refusal to pay reclassified as OBSERVED club endorsement must fail
    with pytest.raises(ValueError, match="refusal-to-pay"):
        CounterfactualPreferenceMapping(
            mapping_id="MAP_REFUSAL_BAD",
            participant_id="PARTICIPANT_002",
            question_id="Q11",
            subtopic_id="Q11_overhead_allocation_mechanism",
            source_preference_key="Q11_PROJECT_PI_ALLOCATION",
            target_regime_type=GoodRegimeType.CLUB_GOOD,
            provenance_category=ProvenanceCategory.OBSERVED_RESPONDENT_PREFERENCE,
            evidence_span_ids=["SP_2"],
            is_refusal_to_pay_origin=True,
        )

    # Same fact framed strictly as INSTITUTIONALLY_DERIVED_MECHANISM burden removal is valid
    mech_map = CounterfactualPreferenceMapping(
        mapping_id="MAP_MECH_OK",
        participant_id="PARTICIPANT_002",
        question_id="Q11",
        subtopic_id="Q11_overhead_allocation_mechanism",
        source_preference_key="Q11_PROJECT_PI_ALLOCATION",
        target_regime_type=GoodRegimeType.CLUB_GOOD,
        provenance_category=ProvenanceCategory.INSTITUTIONALLY_DERIVED_MECHANISM,
        mechanism_rule_id="MECH_ZERO_NONMEMBER_LEVY",
        is_refusal_to_pay_origin=True,
    )
    assert mech_map.validate() is True

    # Assumption sweep requires explicit assumption_id
    with pytest.raises(ValueError, match="assumption_id"):
        validate_provenance_boundary(
            provenance_category=ProvenanceCategory.COUNTERFACTUAL_PREFERENCE_ASSUMPTION,
            target_regime_type=GoodRegimeType.CLUB_GOOD,
            assumption_id=None,
        )


def test_partial_utility_bounds_and_fifth_pareto_status_contract():
    # Partial identification forbids fabricated scalar point_utility
    with pytest.raises(ValueError, match="cannot assign non-null point_utility"):
        CounterfactualUtilityBound(
            bound_id="BND_BAD_PT",
            participant_id="PARTICIPANT_001",
            solution_id="SOL_CF_001",
            subtopic_id="Q11_overhead_allocation_mechanism",
            identification_status=CounterfactualUtilityIdentification.PARTIALLY_IDENTIFIED,
            provenance_category=ProvenanceCategory.INSTITUTIONALLY_DERIVED_MECHANISM,
            utility_lower_bound=0.25,
            utility_upper_bound=0.80,
            point_utility=0.525,
            mechanism_rule_id="MECH_BOUND_01",
        )

    valid_bound = CounterfactualUtilityBound(
        bound_id="BND_OK",
        participant_id="PARTICIPANT_001",
        solution_id="SOL_CF_001",
        subtopic_id="Q11_overhead_allocation_mechanism",
        identification_status=CounterfactualUtilityIdentification.PARTIALLY_IDENTIFIED,
        provenance_category=ProvenanceCategory.INSTITUTIONALLY_DERIVED_MECHANISM,
        utility_lower_bound=0.25,
        utility_upper_bound=0.80,
        point_utility=None,
        mechanism_rule_id="MECH_BOUND_01",
        burden_removal_implication="non_member_compulsory_contribution=0.0",
    )
    assert valid_bound.validate() is True
    assert CounterfactualParetoStatus.UNRESOLVED_DUE_TO_COUNTERFACTUAL_UTILITY.value == (
        "UNRESOLVED_DUE_TO_COUNTERFACTUAL_UTILITY"
    )


def test_counterfactual_solution_metadata_and_dual_frontier_isolation():
    club_spec = ResourceRegimeSpec(
        regime_id="REG_CF_Q11",
        subtopic_id="Q11_overhead_allocation_mechanism",
        question_id="Q11",
        regime_type=GoodRegimeType.CLUB_GOOD,
        rivalry=RivalryLevel.RIVAL,
        excludability=ExcludabilityLevel.EXCLUDABLE,
        financing=FinancingRuleType.VOLUNTARY_MEMBER,
        access=AccessRuleType.MEMBER_PRIORITY,
        exit_policy=ExitPolicyType.ALLOWED,
        club_good_mechanism=_valid_club_mechanism(),
    )

    # Counterfactual solutions cannot target FRONTIER_A
    with pytest.raises(ValueError, match="OBSERVED_DESIGN_FRONTIER"):
        CounterfactualSolutionMetadata(
            solution_id="SOL_CF_001",
            frontier_namespace=FrontierNamespace.FRONTIER_A,
            parent_baseline_solution_id="SOL_0001",
            counterfactual_regime_specs={"Q11_overhead_allocation_mechanism": club_spec},
        )

    # Prohibited pruning source (e.g. GOODS_TAXONOMY, RESOURCE_ELIGIBILITY, CLUSTER_ASSIGNMENT) rejected
    with pytest.raises(ValueError, match="prohibited pruning source"):
        CounterfactualSolutionMetadata(
            solution_id="SOL_CF_001",
            frontier_namespace=FrontierNamespace.FRONTIER_B,
            parent_baseline_solution_id="SOL_0001",
            counterfactual_regime_specs={"Q11_overhead_allocation_mechanism": club_spec},
            pruning_sources_applied=["GOODS_TAXONOMY"],
        )

    meta_ok = CounterfactualSolutionMetadata(
        solution_id="SOL_CF_001",
        frontier_namespace=FrontierNamespace.FRONTIER_B,
        parent_baseline_solution_id="SOL_0001",
        counterfactual_regime_specs={"Q11_overhead_allocation_mechanism": club_spec},
        double_count_guards_applied=["DCG_OVERHEAD_POOL"],
        pruning_sources_applied=["INSTITUTIONAL_CONSTRAINT"],
    )
    assert meta_ok.validate() is True

    # FrontierComparisonResult forbids removing any existing FRONTIER_A package
    with pytest.raises(ValueError, match="removed existing FRONTIER_A solution"):
        FrontierComparisonResult(
            comparison_id="CMP_BAD",
            run_id="run_20261111_002",
            frontier_a_feasible_ids=["SOL_0001", "SOL_0002"],
            frontier_b_feasible_ids=["SOL_0001", "SOL_CF_001"],
            frontier_a_pareto_nondominated_ids=["SOL_0001"],
            frontier_a_robust_status_counts={"ROBUSTLY_NONDOMINATED": 10},
            frontier_b_robust_statuses={
                "SOL_0001": CounterfactualParetoStatus.ROBUSTLY_NONDOMINATED,
                "SOL_CF_001": CounterfactualParetoStatus.UNRESOLVED_DUE_TO_COUNTERFACTUAL_UTILITY,
            },
            frontier_a_snapshot_hashes={"pareto_results_v1": "abc"},
        )

    cmp_ok = FrontierComparisonResult(
        comparison_id="CMP_OK",
        run_id="run_20261111_002",
        frontier_a_feasible_ids=["SOL_0001", "SOL_0002"],
        frontier_b_feasible_ids=["SOL_0001", "SOL_0002", "SOL_CF_001"],
        frontier_a_pareto_nondominated_ids=["SOL_0001"],
        frontier_a_robust_status_counts={
            "ROBUSTLY_NONDOMINATED": 10,
            "CONDITIONALLY_NONDOMINATED": 248,
            "UNRESOLVED_DUE_TO_CODING_UNCERTAINTY": 285,
            "ROBUSTLY_DOMINATED": 0,
        },
        frontier_b_robust_statuses={
            "SOL_0001": CounterfactualParetoStatus.ROBUSTLY_NONDOMINATED,
            "SOL_CF_001": CounterfactualParetoStatus.UNRESOLVED_DUE_TO_COUNTERFACTUAL_UTILITY,
        },
        frontier_a_snapshot_hashes={"pareto_results_v1": "abc"},
        added_counterfactual_solution_ids=["SOL_CF_001"],
        answered_sensitivity_questions=["Q-A", "Q-B", "Q-C", "Q-D", "Q-E", "Q-F", "Q-G", "Q-H"],
    )
    assert cmp_ok.validate() is True


def test_run_20261111_002_counterfactual_regime_config_audit():
    cfg_path = REPO_ROOT / "runs" / "run_20261111_002" / "counterfactual_regime_config.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))

    assert cfg["run_id"] == "run_20261111_002"
    assert cfg["adr_reference"] == "ADR-0009"
    assert cfg["active_frontier_a_namespace"] == FRONTIER_A_NAMESPACE
    assert cfg["counterfactual_frontier_b_namespace"] == FRONTIER_B_NAMESPACE
    assert cfg["counterfactual_output_dir"] == "data/processed/preference/counterfactual"
    assert cfg["new_llm_coding_required"] is False
    assert cfg["agent_08_technical_release"] == "READY"
    assert cfg["agent_08_reporting_status"] == "HELD_FOR_RESOURCE_REGIME_SENSITIVITY"

    freeze = cfg["baseline_frontier_freeze"]
    assert freeze["status"] == "PRESERVED_UNMODIFIED"
    assert freeze["feasible_alternatives_count"] == 161
    assert freeze["feasible_governance_solutions_count"] == 543
    assert freeze["baseline_pareto_nondominated_count"] == 326
    assert freeze["participant_utility_records_count"] == 5973
    assert freeze["robust_pareto_status_counts"] == {
        "ROBUSTLY_NONDOMINATED": 10,
        "CONDITIONALLY_NONDOMINATED": 248,
        "UNRESOLVED_DUE_TO_CODING_UNCERTAINTY": 285,
        "ROBUSTLY_DOMINATED": 0,
    }

    summary = cfg["eligibility_summary"]
    assert summary == {
        "total_canonical_subtopics": 84,
        "ELIGIBLE": 11,
        "CONDITIONAL_RESOURCE_ONLY": 1,
        "INELIGIBLE": 72,
        "UNKNOWN": 0,
    }

    subtopics = cfg["subtopic_eligibility"]
    assert len(subtopics) == 84
    for sub_id, entry in subtopics.items():
        assessment = ResourceEligibilityAssessment(
            subtopic_id=sub_id,
            question_id=entry["question_id"],
            eligibility_status=entry["eligibility_status"],
            analytical_rationale=entry["analytical_rationale"],
            resource_evidence_basis=entry.get("resource_evidence_basis"),
            is_pure_opinion_or_perception=bool(entry.get("is_pure_opinion_or_perception", False)),
            requires_segregated_sensitivity_tier=bool(
                entry.get("requires_segregated_sensitivity_tier", False)
            ),
            segregated_tier_id=entry.get("segregated_tier_id"),
            risk_pooling_caveat=entry.get("risk_pooling_caveat"),
            double_count_guard_group_id=entry.get("double_count_guard_group_id"),
        )
        assert assessment.validate() is True
        if entry["question_id"] in {"Q01", "Q02", "Q03", "Q04", "Q05", "Q07", "Q13", "Q14"}:
            assert entry["eligibility_status"] == "INELIGIBLE"

    assert subtopics["Q08_hr_management_level"]["eligibility_status"] == "CONDITIONAL_RESOURCE_ONLY"
    assert subtopics["Q08_hr_management_level"]["segregated_tier_id"] == "Q-G"
    assert set(cfg["double_count_guard_groups"].keys()) == {
        "DCG_FINANCIAL_RESPONSIBILITY",
        "DCG_OVERHEAD_POOL",
        "DCG_BONUS_POOL",
    }
    assert cfg["required_sensitivity_questions"] == ["Q-A", "Q-B", "Q-C", "Q-D", "Q-E", "Q-F", "Q-G", "Q-H"]


def test_frontier_b_gate_blocks_without_staged_frontier_a_and_separates_agent_08_hold(tmp_path):
    # Clean checkout simulation without private data/processed/preference/* -> Frontier-B release BLOCKED
    for subdir in ["src", "docs", "notebooks", "schemas", "tests", "data/raw", "data/normalized", "runs/run_20261111_002"]:
        (tmp_path / subdir).mkdir(parents=True, exist_ok=True)
    for fname in ("AGENTS.md", "README.md", "pyproject.toml"):
        shutil.copy2(REPO_ROOT / fname, tmp_path / fname)
    shutil.copy2(REPO_ROOT / "data" / "raw" / "survey_raw.csv", tmp_path / "data" / "raw" / "survey_raw.csv")
    for fname in (
        "gpu_runtime_config.json",
        "alternative_crosswalk.json",
        "counterfactual_regime_config.json",
        "manifest.json",
    ):
        shutil.copy2(
            REPO_ROOT / "runs" / "run_20261111_002" / fname,
            tmp_path / "runs" / "run_20261111_002" / fname,
        )
    for d in ("src", "docs", "notebooks", "schemas", "tests"):
        shutil.copytree(REPO_ROOT / d, tmp_path / d, dirs_exist_ok=True)

    clean_report = evaluate_pipeline_state(base_dir=tmp_path, run_id="run_20261111_002", write_log=False)
    assert clean_report.resource_regime_expansion_release_decision == ResourceRegimeExpansionReleaseDecision.BLOCKED
    assert clean_report.states[PipelineState.FRONTIER_B_EXPANSION_READY.value] is False
    assert clean_report.resource_regime_expansion_release_checklist["1_adr_0009_approved"] is True
    assert clean_report.resource_regime_expansion_release_checklist["3_shared_contracts_adr0009_aligned"] is True
    assert clean_report.resource_regime_expansion_release_checklist["4_resource_eligibility_rules_defined"] is True
    assert clean_report.resource_regime_expansion_release_checklist["5_club_good_10field_contract_enforced"] is True
    assert clean_report.resource_regime_expansion_release_checklist["6_provenance_and_partial_id_contracts_enforced"] is True
    assert clean_report.resource_regime_expansion_release_checklist["7_dual_frontier_isolation_verified"] is True
    assert clean_report.resource_regime_expansion_release_checklist["9_adr0009_contract_tests_and_hygiene_pass"] is True
    assert clean_report.resource_regime_expansion_release_checklist["2_frontier_a_frozen"] is False
    assert clean_report.resource_regime_expansion_release_checklist["8_no_existing_feasible_alternative_removed"] is False
    assert clean_report.agent_08_technical_release == Agent08TechnicalReleaseDecision.READY
    assert clean_report.agent_08_reporting_status == Agent08ReportingStatus.HELD_FOR_RESOURCE_REGIME_SENSITIVITY

    # Now verify REPO_ROOT truthfully depending on whether private Frontier-A files are staged on disk
    repo_report = evaluate_pipeline_state(base_dir=REPO_ROOT, run_id="run_20261111_002", write_log=False)
    assert repo_report.agent_08_technical_release == Agent08TechnicalReleaseDecision.READY
    assert repo_report.agent_08_reporting_status == Agent08ReportingStatus.HELD_FOR_RESOURCE_REGIME_SENSITIVITY
    frontier_a_staged = (
        (REPO_ROOT / "data" / "processed" / "preference_matrix.parquet").is_file()
        and (REPO_ROOT / "data" / "processed" / "preference" / "feasible_alternatives.json").is_file()
        and (REPO_ROOT / "data" / "processed" / "preference" / "pareto_results.json").is_file()
        and (REPO_ROOT / "data" / "processed" / "preference" / "robust_pareto_results.json").is_file()
    )
    if frontier_a_staged:
        assert repo_report.original_frontier_status == "PRESERVED_UNMODIFIED"
        assert repo_report.resource_regime_expansion_release_decision == ResourceRegimeExpansionReleaseDecision.READY
        assert all(repo_report.resource_regime_expansion_release_checklist.values())
        assert repo_report.states[PipelineState.FRONTIER_B_EXPANSION_READY.value] is True
    else:
        assert repo_report.resource_regime_expansion_release_decision == ResourceRegimeExpansionReleaseDecision.BLOCKED
        assert repo_report.states[PipelineState.FRONTIER_B_EXPANSION_READY.value] is False


def test_frontier_b_gate_transitions_to_ready_with_synthetic_frozen_frontier_a(tmp_path):
    """Prove all 9 Frontier-B conditions reach READY when verified Frontier-A files match manifest SHA-256."""
    for subdir in [
        "src",
        "docs",
        "notebooks",
        "schemas",
        "tests",
        "data/raw",
        "data/normalized",
        "data/processed/preference",
        "runs/run_20261111_002",
    ]:
        (tmp_path / subdir).mkdir(parents=True, exist_ok=True)
    for fname in ("AGENTS.md", "README.md", "pyproject.toml"):
        shutil.copy2(REPO_ROOT / fname, tmp_path / fname)
    shutil.copy2(REPO_ROOT / "data" / "raw" / "survey_raw.csv", tmp_path / "data" / "raw" / "survey_raw.csv")
    for fname in (
        "gpu_runtime_config.json",
        "alternative_crosswalk.json",
        "pareto_mc_config.json",
        "clustering_config.json",
        "counterfactual_regime_config.json",
        "RUN_CARD.md",
    ):
        shutil.copy2(
            REPO_ROOT / "runs" / "run_20261111_002" / fname,
            tmp_path / "runs" / "run_20261111_002" / fname,
        )
    for d in ("src", "docs", "notebooks", "schemas", "tests"):
        shutil.copytree(REPO_ROOT / d, tmp_path / d, dirs_exist_ok=True)

    # Create valid synthetic Frontier-A files with exact expected counts (161, 543, 326, 5973, 10/248/285/0)
    (tmp_path / "data" / "processed" / "preference_matrix.parquet").write_bytes(b"SYNTHETIC_PARQUET_FIXTURE")
    (tmp_path / "data" / "processed" / "preference" / "preference_matrix.json").write_text("{}", encoding="utf-8")
    alts = [{"alternative_id": f"ALT_{i:03d}"} for i in range(161)]
    sols = [{"solution_id": f"SOL_{i:04d}"} for i in range(543)]
    sol_ids = [s["solution_id"] for s in sols]
    (tmp_path / "data" / "processed" / "preference" / "feasible_alternatives.json").write_text(
        json.dumps({"feasible_alternatives": alts, "governance_solutions": sols}),
        encoding="utf-8",
    )
    (tmp_path / "data" / "processed" / "preference" / "participant_utility.json").write_text(
        json.dumps({"utility_record_count": 5973, "participant_utilities": [None] * 5973}),
        encoding="utf-8",
    )
    (tmp_path / "data" / "processed" / "preference" / "pareto_results.json").write_text(
        json.dumps(
            {
                "pareto_result": {
                    "evaluated_solution_ids": sol_ids,
                    "nondominated_solution_ids": sol_ids[:326],
                }
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "data" / "processed" / "preference" / "robust_pareto_results.json").write_text(
        json.dumps(
            {
                "status_counts": {
                    "ROBUSTLY_NONDOMINATED": 10,
                    "CONDITIONALLY_NONDOMINATED": 248,
                    "UNRESOLVED_DUE_TO_CODING_UNCERTAINTY": 285,
                    "ROBUSTLY_DOMINATED": 0,
                }
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "data" / "processed" / "preference" / "agent_04_qa_report.json").write_text(
        json.dumps({"all_qa_checks_passed": True}),
        encoding="utf-8",
    )

    manifest = json.loads(
        (REPO_ROOT / "runs" / "run_20261111_002" / "manifest.json").read_text(encoding="utf-8")
    )
    for aid in (
        "preference_matrix_v1",
        "preference_matrix_json_v1",
        "feasible_alternatives_v1",
        "participant_utility_v1",
        "pareto_results_v1",
        "robust_pareto_results_v1",
        "agent_04_qa_report_v1",
    ):
        rel = manifest["artifacts"][aid]["path"]
        sha = hashlib.sha256((tmp_path / rel).read_bytes()).hexdigest()
        manifest["artifacts"][aid]["source_hashes"] = {rel: sha}
    (tmp_path / "runs" / "run_20261111_002" / "manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    orch = PipelineOrchestrator(base_dir=tmp_path, run_id="run_20261111_002")
    rep = orch.evaluate(write_log=False)
    assert rep.original_frontier_status == "PRESERVED_UNMODIFIED"
    assert all(rep.resource_regime_expansion_release_checklist.values())
    assert rep.resource_regime_expansion_release_decision == ResourceRegimeExpansionReleaseDecision.READY
    assert rep.states[PipelineState.FRONTIER_B_EXPANSION_READY.value] is True
    assert rep.agent_08_technical_release == Agent08TechnicalReleaseDecision.READY
    assert rep.agent_08_reporting_status == Agent08ReportingStatus.HELD_FOR_RESOURCE_REGIME_SENSITIVITY
