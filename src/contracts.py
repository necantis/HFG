"""Canonical data contracts and interface schemas for the HFG multilingual survey analysis system.

Owned by: Agent 00 — System Architect
Schema Version: 1.0.0 (Aligned with Architecture v1.1.0, ADR-0005, and ADR-0006)

Defines all 20 required system interfaces with explicit required fields, optional fields,
missingness representations, uncertainty representations, schema version, and provenance metadata.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Literal

SCHEMA_VERSION: str = "1.0.0"


class MissingnessState(str, Enum):
    """Explicit representation of missingness across ingestion, coding, and PreferenceCell contracts.

    Aligned with ADR-0005 canonical PreferenceCell states while preserving fine-grained
    ingestion and frame-applicability diagnostics.
    """

    OBSERVED_USABLE = "observed_usable"
    UNOBSERVED_MISSING = "unobserved_missing"
    INFEASIBLE_CHOICE = "infeasible_choice"
    AMBIGUOUS = "ambiguous"
    # Fine-grained ingestion / qualitative / module execution sub-states
    MISSING_RAW_BLANK = "missing_raw_blank"
    MISSING_NON_SUBSTANTIVE = "missing_non_substantive"
    NOT_MENTIONED_IN_RESPONSE = "not_mentioned_in_response"
    NOT_APPLICABLE_FRAME = "not_applicable_frame"
    SKIPPED_MISSING_INPUT_FILE = "skipped_missing_input_file"

    def is_usable(self) -> bool:
        return self == MissingnessState.OBSERVED_USABLE

    def to_canonical_cell_state(self) -> str:
        if self in {
            MissingnessState.OBSERVED_USABLE,
            MissingnessState.UNOBSERVED_MISSING,
            MissingnessState.INFEASIBLE_CHOICE,
            MissingnessState.AMBIGUOUS,
        }:
            return self.value
        return MissingnessState.UNOBSERVED_MISSING.value


class AnalyticalFrameType(str, Enum):
    """Question-level analytical frame governing allowed classifications."""

    GOVERNANCE_GOODS_ALLOCATION = "GOVERNANCE_GOODS_ALLOCATION"
    INSTITUTIONAL_DESIGN_DECISION = "INSTITUTIONAL_DESIGN_DECISION"
    PERCEPTION_AND_DIAGNOSTIC = "PERCEPTION_AND_DIAGNOSTIC"
    OPEN_STRATEGIC_PRIORITY = "OPEN_STRATEGIC_PRIORITY"


class EconomicGoodClass(str, Enum):
    """Economic good classification applied ONLY when conceptually appropriate."""

    PRIVATE_GOOD = "private_good"
    CLUB_GOOD = "club_good"
    COMMON_GOOD = "common_good"
    PUBLIC_GOOD = "public_good"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True)
class ProvenanceMeta:
    """Standard provenance metadata attached to every contract instance."""

    record_id: str
    run_id: str
    dataset_fingerprint: str
    created_at_utc: str
    producer_module: str
    producer_agent: str
    upstream_artifact_ids: list[str] = field(default_factory=list)
    config_hash: str = ""
    schema_version: str = SCHEMA_VERSION


@dataclass(frozen=True)
class UncertaintyEnvelope:
    """Explicit uncertainty representation separating confidence, agreement, and intervals."""

    point_estimate: float | None
    ci_lower_95: float | None = None
    ci_upper_95: float | None = None
    std_error: float | None = None
    coder_confidence: float | None = None
    coder_agreement: float | None = None
    distribution_type: Literal[
        "DETERMINISTIC",
        "DUAL_CODER_INTERVAL",
        "MONTE_CARLO_EMPIRICAL",
        "BOOTSTRAP",
    ] = "DUAL_CODER_INTERVAL"


# ---------------------------------------------------------------------------
# 1. RunManifest
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class RunManifest:
    run_id: str
    survey_group_id: str
    dataset_path: str
    dataset_fingerprint: str
    expected_question_count: int
    detected_participant_count: int
    supported_languages: list[Literal["fr", "de", "en"]]
    gpu_device_name: str
    coder_a_model_spec: dict[str, Any]
    coder_b_model_spec: dict[str, Any]
    hardcoding_scan_passed: bool
    provenance: ProvenanceMeta
    # Configurable runtime parameter references (ADR-0005: not immutable constants)
    gpu_runtime_config_path: str | None = None
    pareto_mc_config_path: str | None = None
    monte_carlo_draws: int = 1000
    random_seed: int = 42
    confidence_level: float = 0.95
    # Missingness representation for optional voting inputs
    baldwin_input_state: MissingnessState = MissingnessState.SKIPPED_MISSING_INPUT_FILE
    rrv_input_state: MissingnessState = MissingnessState.SKIPPED_MISSING_INPUT_FILE
    # Optional fields
    baldwin_input_path: str | None = None
    baldwin_input_fingerprint: str | None = None
    rrv_input_path: str | None = None
    rrv_input_fingerprint: str | None = None
    git_commit_sha: str | None = None
    notes: str | None = None
    schema_version: str = SCHEMA_VERSION


# ---------------------------------------------------------------------------
# 2. QuestionSpec
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class QuestionSpec:
    question_id: str
    question_index: int
    column_headers_by_lang: dict[str, str]
    canonical_prompt_en: str
    analytical_frame: AnalyticalFrameType
    economic_good_classification_policy: Literal["ENABLED", "CONDITIONAL", "DISABLED"]
    alternative_classification_scheme: str
    observed_response_count: int
    missing_response_count: int
    missing_participant_ids: list[str]
    provenance: ProvenanceMeta
    # Uncertainty representation
    frame_assignment_source: Literal["DECLARED_CONFIG", "VALIDATED_HEADER"] = "DECLARED_CONFIG"
    # Optional fields
    prompt_fr: str | None = None
    prompt_de: str | None = None
    domain_tags: list[str] = field(default_factory=list)
    compatibility_rule_id: str | None = None
    schema_version: str = SCHEMA_VERSION


# ---------------------------------------------------------------------------
# 3. EvidenceSpan
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class EvidenceSpan:
    span_id: str
    participant_id: str
    question_id: str
    detected_language: Literal["fr", "de", "en"]
    raw_response_sha256: str
    char_start: int
    char_end: int
    verbatim_quote: str
    missingness_state: MissingnessState
    language_detection_confidence: float
    span_boundary_confidence: float
    provenance: ProvenanceMeta
    # Optional fields
    english_working_gloss: str | None = None
    sentence_index: int | None = None
    schema_version: str = SCHEMA_VERSION


# ---------------------------------------------------------------------------
# 4. SubtopicCandidate
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SubtopicCandidate:
    candidate_id: str
    question_id: str
    participant_id: str
    coder_id: Literal["coder_a", "coder_b"]
    evidence_span_ids: list[str]
    proposed_label_en: str
    proposed_description: str
    candidate_alternative_distribution: dict[str, float]
    semantic_importance: float
    coder_confidence: float
    missingness_state: MissingnessState
    provenance: ProvenanceMeta
    # Optional fields
    proposed_economic_good_class: EconomicGoodClass | None = None
    proposed_alternative_frame_label: str | None = None
    native_language_keywords: list[str] = field(default_factory=list)
    derived_scalar_stance: float | None = None
    schema_version: str = SCHEMA_VERSION


# ---------------------------------------------------------------------------
# 5. CanonicalSubtopic
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CanonicalSubtopic:
    subtopic_id: str
    question_id: str
    canonical_label_en: str
    canonical_description: str
    source_candidate_ids: list[str]
    supporting_span_ids: list[str]
    mention_participant_count: int
    unmentioned_participant_count: int
    missing_question_participant_count: int
    economic_good_applicability: Literal["APPLIED", "NOT_APPLICABLE_FRAME", "MIXED_CONTESTED"]
    coder_agreement: float
    mean_coder_confidence: float
    provenance: ProvenanceMeta
    # Optional fields
    labels_by_lang: dict[str, str] = field(default_factory=dict)
    dominant_economic_good_class: EconomicGoodClass | None = None
    economic_good_distribution: dict[str, float] | None = None
    question_specific_category: str | None = None
    linked_value_ids: list[str] = field(default_factory=list)
    feasible_alternatives: list[str] = field(default_factory=list)
    has_defensible_ordering: bool = False
    schema_version: str = SCHEMA_VERSION


# ---------------------------------------------------------------------------
# 6. ValueAssignment
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ValueAssignment:
    value_assignment_id: str
    value_id: str
    value_label_en: str
    value_definition: str
    participant_id: str
    question_id: str
    subtopic_id: str
    evidence_span_ids: list[str]
    missingness_state: MissingnessState
    polarity: float
    semantic_importance: float
    coder_confidence: float
    coder_agreement: float
    polarity_uncertainty_interval: tuple[float, float]
    provenance: ProvenanceMeta
    # Optional fields
    coder_a_raw_label: str | None = None
    coder_b_raw_label: str | None = None
    cross_question_bridge_ids: list[str] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION


# ---------------------------------------------------------------------------
# 7. CodingResult
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CodingResult:
    coding_id: str
    participant_id: str
    question_id: str
    subtopic_id: str
    coder_source: Literal["coder_a", "coder_b", "reconciled"]
    missingness_state: MissingnessState
    alternative_probabilities: dict[str, float]
    semantic_importance: float | None
    coder_confidence: float | None
    coder_agreement: float | None
    evidence_span_ids: list[str]
    provenance: ProvenanceMeta
    # Uncertainty bounds over alternative probabilities
    probability_ci_lower: dict[str, float] | None = None
    probability_ci_upper: dict[str, float] | None = None
    # Optional derived scalar ONLY when alternatives have an analytically defensible ordering
    derived_scalar_score: float | None = None
    # Optional fields
    economic_good_class: EconomicGoodClass | None = None
    perception_category: str | None = None
    value_assignment_ids: list[str] = field(default_factory=list)
    reconciliation_method: Literal[
        "EXACT_MATCH",
        "CONFIDENCE_WEIGHTED_DISTRIBUTION",
        "ARBITRATED_SPAN_CHECK",
        "HIGH_UNCERTAINTY_FLAGGED",
    ] | None = None
    rationale_summary: str | None = None
    schema_version: str = SCHEMA_VERSION

    def validate_invariants(self, tolerance: float = 1e-4) -> None:
        if not self.missingness_state.is_usable():
            if self.alternative_probabilities:
                raise ValueError(
                    f"CodingResult {self.coding_id}: non-usable state {self.missingness_state} "
                    "must have empty alternative_probabilities."
                )
            if self.derived_scalar_score is not None or self.semantic_importance is not None:
                raise ValueError(
                    f"CodingResult {self.coding_id}: non-usable state {self.missingness_state} "
                    "must not impute scalar preference or semantic_importance."
                )
        else:
            if not self.evidence_span_ids:
                raise ValueError(
                    f"CodingResult {self.coding_id}: OBSERVED_USABLE coding must cite >= 1 EvidenceSpan."
                )
            total = sum(self.alternative_probabilities.values())
            if abs(total - 1.0) > tolerance:
                raise ValueError(
                    f"CodingResult {self.coding_id}: alternative_probabilities must sum to 1.0 "
                    f"within {tolerance}, got {total:.6f}."
                )


# ---------------------------------------------------------------------------
# 8. PreferenceCell (Aligned with ADR-0005 Distributional Contract)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PreferenceCell:
    cell_id: str
    participant_id: str
    question_id: str
    subtopic_id: str
    missingness_state: MissingnessState
    alternative_probabilities: dict[str, float]
    semantic_importance: float | None
    coder_confidence: float | None
    coder_agreement: float | None
    source_coding_id: str
    evidence_span_ids: list[str]
    provenance: ProvenanceMeta
    # Uncertainty over probability simplex
    probability_lower_bounds: dict[str, float] | None = None
    probability_upper_bounds: dict[str, float] | None = None
    probability_std_errors: dict[str, float] | None = None
    # Optional derived scalar ONLY when alternatives have an analytically defensible ordering
    derived_scalar_score: float | None = None
    # Optional coder diagnostics
    coder_a_probabilities: dict[str, float] | None = None
    coder_b_probabilities: dict[str, float] | None = None
    coder_a_importance: float | None = None
    coder_b_importance: float | None = None
    economic_good_class: str | None = None
    schema_version: str = SCHEMA_VERSION

    def validate_simplex(self, tolerance: float = 1e-4) -> bool:
        """Verify that alternative_probabilities sum to 1.0 within tolerance for usable cells."""
        if self.missingness_state.is_usable():
            total = sum(self.alternative_probabilities.values())
            if abs(total - 1.0) > tolerance:
                raise ValueError(
                    f"PreferenceCell {self.cell_id}: alternative_probabilities must sum to 1.0 "
                    f"within {tolerance}, got {total:.6f}"
                )
        return True


# ---------------------------------------------------------------------------
# 9. PreferenceMatrix
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PreferenceMatrix:
    matrix_id: str
    participant_ids: list[str]
    question_ids: list[str]
    subtopic_ids: list[str]
    subtopic_to_question: dict[str, str]
    cells: list[PreferenceCell]
    observed_usable_cell_count: int
    unobserved_missing_cell_count: int
    infeasible_choice_cell_count: int
    ambiguous_cell_count: int
    overall_coder_agreement_mean: float
    overall_coder_confidence_mean: float
    validation_passed: bool
    provenance: ProvenanceMeta
    # Optional fields
    question_coverage_rates: dict[str, float] = field(default_factory=dict)
    participant_response_rates: dict[str, float] = field(default_factory=dict)
    flagged_low_agreement_cell_ids: list[str] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION


# ---------------------------------------------------------------------------
# 10. FeasibleAlternative
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class FeasibleAlternative:
    alternative_id: str
    question_id: str
    label_en: str
    description_en: str
    subtopic_alternative_allocations: dict[str, dict[str, float]]
    active_subtopic_mask: dict[str, bool]
    supporting_participant_count: int
    missing_participant_count: int
    feasibility_status: Literal["FEASIBLE", "PRUNED_INCOMPATIBLE", "PRUNED_DEPENDENCY_MISSING"]
    empirical_support_uncertainty: UncertaintyEnvelope
    provenance: ProvenanceMeta
    # Optional fields
    economic_good_profile: dict[str, str] | None = None
    explanatory_value_ids: list[str] = field(default_factory=list)
    constraint_checks_passed: list[str] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION


# ---------------------------------------------------------------------------
# 11. GovernanceSolution
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class GovernanceSolution:
    solution_id: str
    label_en: str
    question_alternatives: dict[str, str]
    global_alternative_profile: dict[str, dict[str, float]]
    included_question_ids: list[str]
    diagnostic_context_question_ids: list[str]
    logical_constraints_satisfied: list[str]
    institutional_constraints_satisfied: list[str]
    dependencies_satisfied: list[str]
    feasibility_evaluation_status: Literal[
        "STRICTLY_FEASIBLE", "INCOMPLETE_DEPENDENCY", "LOGICAL_CONFLICT"
    ]
    generation_method: Literal[
        "COMBINATORIAL_CONSTRAINT_SATISFACTION",
        "DISCRETE_POLICY_GRID",
        "STRUCTURAL_DIRECTED_SEARCH",
    ]
    provenance: ProvenanceMeta
    # Explanatory characterization fields (strictly non-filtering; never used to prune the Pareto choice set)
    explanatory_organisational_values: list[str] = field(default_factory=list)
    # Optional fields
    summary_by_lang: dict[str, str] = field(default_factory=dict)
    economic_good_summary: dict[str, str] | None = None
    schema_version: str = SCHEMA_VERSION


# ---------------------------------------------------------------------------
# 12. ParticipantUtility
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ParticipantUtility:
    utility_id: str
    participant_id: str
    solution_id: str
    preference_matrix_id: str
    missingness_state: MissingnessState
    observed_subtopic_count: int
    total_subtopic_count: int
    point_utility: float | None
    utility_ci_lower_95: float | None
    utility_ci_upper_95: float | None
    utility_std_error: float | None
    mean_coder_confidence: float | None
    mean_coder_agreement: float | None
    provenance: ProvenanceMeta
    # Optional fields
    per_question_utilities: dict[str, float | None] = field(default_factory=dict)
    individual_regret: float | None = None
    is_below_veto_threshold: bool | None = None
    schema_version: str = SCHEMA_VERSION


# ---------------------------------------------------------------------------
# 13. ParetoResult
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ParetoResult:
    pareto_result_id: str
    preference_matrix_id: str
    evaluated_solution_ids: list[str]
    valid_participant_ids: list[str]
    excluded_all_missing_participant_ids: list[str]
    nondominated_solution_ids: list[str]
    dominated_solution_map: dict[str, list[str]]
    rawls_maximin_scores: dict[str, float]
    utilitarian_scores: dict[str, float]
    nash_welfare_scores: dict[str, float]
    gini_inequality_scores: dict[str, float]
    atkinson_inequality_scores: dict[str, float]
    opposition_counts: dict[str, int]
    opposition_shares: dict[str, float]
    max_regret_scores: dict[str, float]
    rankings_by_criterion: dict[str, list[str]]
    provenance: ProvenanceMeta
    # Optional fields
    pairwise_dominance_margins: dict[str, float] = field(default_factory=dict)
    profile_mean_utilities: dict[str, dict[str, float]] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION


# ---------------------------------------------------------------------------
# 14. RobustParetoResult
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class RobustParetoResult:
    robust_pareto_id: str
    base_pareto_result_id: str
    monte_carlo_draws: int
    random_seed: int
    pareto_mc_config_path: str | None
    frontier_inclusion_probabilities: dict[str, float]
    robust_frontier_solution_ids: list[str]
    criterion_top1_probabilities: dict[str, dict[str, float]]
    utility_metric_intervals: dict[str, dict[str, UncertaintyEnvelope]]
    missing_participant_ids_preserved: list[str]
    provenance: ProvenanceMeta
    # Optional fields
    veto_threshold_sensitivity: dict[str, dict[str, float]] = field(default_factory=dict)
    subtopic_weight_perturbation_sensitivity: dict[str, float] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION


# ---------------------------------------------------------------------------
# 15. ClusterResult (Interpretive Preference Profiles Only — Non-Pruning)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ClusterResult:
    cluster_result_id: str
    preference_matrix_id: str
    distance_metric: Literal["MASKED_JENSEN_SHANNON", "MASKED_COSINE", "MASKED_WEIGHTED_L1"]
    min_shared_subtopics_for_pair: int
    candidate_k_evaluated: list[int]
    silhouette_scores_by_k: dict[int, float]
    stability_scores_by_k: dict[int, float]
    selected_k: int
    profile_assignments: dict[str, str]
    unassigned_missing_participant_ids: list[str]
    profile_sizes: dict[str, int]
    profile_distinguishing_subtopics: dict[str, list[str]]
    profile_distinguishing_values: dict[str, list[str]]
    participant_assignment_confidence: dict[str, float]
    provenance: ProvenanceMeta
    # Optional fields
    descriptive_labels_en: dict[str, str] = field(default_factory=dict)
    pairwise_distance_matrix_hash: str | None = None
    schema_version: str = SCHEMA_VERSION


# ---------------------------------------------------------------------------
# 16. BaldwinResult
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class BaldwinResult:
    baldwin_result_id: str
    execution_status: Literal["EXECUTED", "SKIPPED_NO_VALID_INPUT", "FAILED_VALIDATION"]
    missingness_state: MissingnessState
    input_file_path: str | None
    input_file_sha256: str | None
    candidate_ids: list[str]
    valid_ballot_count: int
    missing_or_spoiled_ballot_count: int
    elimination_rounds: list[dict[str, Any]]
    winner_candidate_ids: list[str]
    provenance: ProvenanceMeta
    # Uncertainty fields
    tie_margin_min: float | None = None
    bootstrap_winner_stability: dict[str, float] | None = None
    # Optional fields
    tie_breaking_rule_used: str | None = None
    borda_initial_ranking: list[str] | None = None
    schema_version: str = SCHEMA_VERSION


# ---------------------------------------------------------------------------
# 17. RRVResult
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class RRVResult:
    rrv_result_id: str
    execution_status: Literal["EXECUTED", "SKIPPED_NO_VALID_INPUT", "FAILED_VALIDATION"]
    missingness_state: MissingnessState
    input_file_path: str | None
    input_file_sha256: str | None
    score_scale_min: float | None
    score_scale_max: float | None
    reweighting_constant_k: float | None
    seats_to_fill: int
    valid_ballot_count: int
    missing_ballot_count: int
    selection_rounds: list[dict[str, Any]]
    selected_committee_ids: list[str]
    provenance: ProvenanceMeta
    # Uncertainty fields
    round_margin_min: float | None = None
    bootstrap_committee_inclusion_freq: dict[str, float] | None = None
    # Optional fields
    proportionality_satisfaction_metrics: dict[str, float] | None = None
    schema_version: str = SCHEMA_VERSION


# ---------------------------------------------------------------------------
# 18. ReportClaim
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ReportClaim:
    claim_id: str
    section_id: str
    question_ids: list[str]
    claim_type: Literal[
        "QUALITATIVE_SUBTOPIC_FINDING",
        "CROSS_QUESTION_VALUE_LINK",
        "ECONOMIC_GOOD_CLASSIFICATION",
        "PERCEPTION_FINDING",
        "PROFILE_CHARACTERIZATION",
        "PARETO_RANKING_STATEMENT",
        "VOTING_OUTCOME_STATEMENT",
        "MISSINGNESS_DISCLOSURE",
    ]
    statement_text_en: str
    evidence_span_ids: list[str]
    canonical_subtopic_ids: list[str]
    artifact_references: list[str]
    numerical_values_cited: dict[str, float | int]
    observed_count_disclosed: int
    missing_count_disclosed: int
    uncertainty_summary: UncertaintyEnvelope
    verification_passed: bool
    provenance: ProvenanceMeta
    # Optional fields
    statement_translations: dict[str, str] = field(default_factory=dict)
    caveats_and_assumptions: list[str] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION


# ---------------------------------------------------------------------------
# 19. ArtifactRecord
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ArtifactRecord:
    artifact_id: str
    artifact_type: str
    stage_id: str
    file_path: str
    content_sha256: str
    byte_size: int
    record_count: int
    null_record_count: int
    is_cacheable: bool
    invalidation_keys: dict[str, str]
    validation_status: Literal["VERIFIED", "STALE_NEEDS_REGEN", "CORRUPTED"]
    authority_level: str
    provenance: ProvenanceMeta
    # Optional fields
    compression: Literal["none", "gzip", "zstd", "parquet_snappy"] | None = None
    execution_duration_seconds: float | None = None
    schema_version: str = SCHEMA_VERSION


# ---------------------------------------------------------------------------
# 20. AgentHandoff
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class AgentHandoff:
    handoff_id: str
    from_agent: str
    to_agents: list[str]
    completed_stage_ids: list[str]
    modified_files: list[str]
    produced_artifact_ids: list[str]
    architectural_decisions: list[str]
    identified_risks: list[dict[str, str]]
    downstream_tasks: dict[str, list[str]]
    blocking_issues: list[str]
    open_verification_checks: list[str]
    ready_for_next_stage: bool
    provenance: ProvenanceMeta
    # Optional fields
    skipped_optional_modules: list[str] = field(default_factory=list)
    performance_metrics_sec: dict[str, float] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


ALL_CONTRACT_TYPES: dict[str, type] = {
    "RunManifest": RunManifest,
    "QuestionSpec": QuestionSpec,
    "EvidenceSpan": EvidenceSpan,
    "SubtopicCandidate": SubtopicCandidate,
    "CanonicalSubtopic": CanonicalSubtopic,
    "ValueAssignment": ValueAssignment,
    "CodingResult": CodingResult,
    "PreferenceCell": PreferenceCell,
    "PreferenceMatrix": PreferenceMatrix,
    "FeasibleAlternative": FeasibleAlternative,
    "GovernanceSolution": GovernanceSolution,
    "ParticipantUtility": ParticipantUtility,
    "ParetoResult": ParetoResult,
    "RobustParetoResult": RobustParetoResult,
    "ClusterResult": ClusterResult,
    "BaldwinResult": BaldwinResult,
    "RRVResult": RRVResult,
    "ReportClaim": ReportClaim,
    "ArtifactRecord": ArtifactRecord,
    "AgentHandoff": AgentHandoff,
}
