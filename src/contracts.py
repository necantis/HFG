"""Canonical data contracts and interface schemas for the HFG multilingual survey analysis system.

Owned by: Agent 00 — System Architect (Shared contract integration: Agent 11)
Schema Version: 1.0.0 (Aligned with Architecture v1.1.0, ADR-0005, ADR-0006, and ADR-0008)

Defines all required system interfaces with explicit required fields, optional fields,
missingness representations, ADR-0008 uncertainty-set and Level 2 crosswalk representations,
schema version, and provenance metadata.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Literal

SCHEMA_VERSION: str = "1.0.0"

FORBIDDEN_RECONCILIATION_METHODS: frozenset[str] = frozenset(
    {
        "CONFIDENCE_WEIGHTED_DISTRIBUTION",
        "UNWEIGHTED_DEFAULT_AVERAGE",
        "MAJORITY_VOTE",
        "HIGHEST_CONFIDENCE_WINS",
        "CODER_A_PRECEDENCE",
        "CODER_B_PRECEDENCE",
    }
)

PROHIBITED_PRUNING_SOURCES: frozenset[str] = frozenset(
    {
        "CLUSTER_ASSIGNMENT",
        "CLUSTER_CENTROID",
        "VALUE_ASSIGNMENT",
        "CODER_DISAGREEMENT",
        "NO_VALID_CROSSWALK",
        "SINGLE_CODER_MINORITY_SUBTOPIC",
        "CODER_CONFIDENCE",
    }
)


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


class ResponseEpistemicStatus(str, Enum):
    """Canonical response epistemic status produced by Agent 01 and consumed by Agent 02+.

    Separates whether response text was supplied and what epistemic content is present from
    whether an actionable institutional preference can be extracted.
    """

    SUBSTANTIVE = "substantive"
    MIXED_UNCERTAINTY_AND_PREFERENCE = "mixed_uncertainty_and_preference"
    RAW_BLANK = "raw_blank"
    AMBIGUOUS = "ambiguous"
    EXPLICIT_NO_OPINION = "explicit_no_opinion"
    EXPLICIT_INSUFFICIENT_EXPERIENCE = "explicit_insufficient_experience"
    EXPLICIT_INSUFFICIENT_INFORMATION = "explicit_insufficient_information"
    PUNCTUATION_UNINTERPRETABLE = "punctuation_uninterpretable"
    NO_ADDITIONAL_REMARKS = "no_additional_remarks"


class CrosswalkStatus(str, Enum):
    """ADR-0008 Level 2 per-question/subtopic alternative-vocabulary crosswalk status."""

    EXACT_KEY_MATCH = "EXACT_KEY_MATCH"
    SEMANTIC_KEY_MATCH = "SEMANTIC_KEY_MATCH"
    SCENARIO_PREFIX_MATCH = "SCENARIO_PREFIX_MATCH"
    PARTIAL_CROSSWALK = "PARTIAL_CROSSWALK"
    NO_VALID_CROSSWALK = "NO_VALID_CROSSWALK"
    SINGLE_CODER_ONLY = "SINGLE_CODER_ONLY"


class AgreementStatus(str, Enum):
    """ADR-0008 multi-axis agreement state separating numeric match from interpretation & crosswalk."""

    EXACT_AGREEMENT = "EXACT_AGREEMENT"
    DISTRIBUTION_AGREEMENT_INTERP_FLAGGED = "DISTRIBUTION_AGREEMENT_INTERP_FLAGGED"
    DISTRIBUTION_AGREEMENT_CROSSWALK_PENDING = "DISTRIBUTION_AGREEMENT_CROSSWALK_PENDING"
    DISTRIBUTION_DISAGREEMENT = "DISTRIBUTION_DISAGREEMENT"
    VOCABULARY_MISMATCH = "VOCABULARY_MISMATCH"
    SINGLE_CODER_ONLY = "SINGLE_CODER_ONLY"
    NON_PREFERENCE_AGREEMENT = "NON_PREFERENCE_AGREEMENT"


class UncertaintyClass(str, Enum):
    """ADR-0008 canonical epistemic uncertainty classification for PreferenceCell."""

    NONE_CONSENSUS = "NONE_CONSENSUS"
    PRESERVED_MISSINGNESS = "PRESERVED_MISSINGNESS"
    INTERPRETATION_DIVERGENCE = "INTERPRETATION_DIVERGENCE"
    DUAL_CODER_DISTRIBUTION_SET = "DUAL_CODER_DISTRIBUTION_SET"
    CROSSWALK_PARTIAL_OR_UNALIGNED = "CROSSWALK_PARTIAL_OR_UNALIGNED"
    SINGLE_CODER_PARTIAL_ID_OMISSION = "SINGLE_CODER_PARTIAL_ID_OMISSION"
    SINGLE_CODER_PARTIAL_ID_GRANULARITY = "SINGLE_CODER_PARTIAL_ID_GRANULARITY"


class SingleCoderUncertaintyType(str, Enum):
    """ADR-0008 single-coder epistemic uncertainty subtypes (non-coding side stays unobserved)."""

    SINGLE_CODER_PARTICIPANT_OMISSION = "SINGLE_CODER_PARTICIPANT_OMISSION"
    SINGLE_CODER_SUBTOPIC_GRANULARITY = "SINGLE_CODER_SUBTOPIC_GRANULARITY"


class ReconciliationStatus(str, Enum):
    """ADR-0008 downstream reconciliation status for PreferenceCell."""

    AGREEMENT_EXACT = "AGREEMENT_EXACT"
    AGREEMENT_DISTRIBUTION_ONLY_INTERPRETATION_FLAGGED = "AGREEMENT_DISTRIBUTION_ONLY_INTERPRETATION_FLAGGED"
    RESOLVED_WITH_UNCERTAINTY_SET = "RESOLVED_WITH_UNCERTAINTY_SET"
    UNRESOLVED_CROSSWALK = "UNRESOLVED_CROSSWALK"
    PRESERVED_MISSING_OR_NON_PREFERENCE = "PRESERVED_MISSING_OR_NON_PREFERENCE"
    NOT_MENTIONED_ABSENCE = "NOT_MENTIONED_ABSENCE"


class DerivedScenarioOrigin(str, Enum):
    """ADR-0008 provenance tag distinguishing observed coder distributions from derived sensitivity draws."""

    OBSERVED_CODER_EVIDENCE = "OBSERVED_CODER_EVIDENCE"
    DERIVED_ROBUSTNESS_SCENARIO = "DERIVED_ROBUSTNESS_SCENARIO"
    DERIVED_ROBUSTNESS_CONVEX_BARYCENTER = "DERIVED_ROBUSTNESS_CONVEX_BARYCENTER"
    DERIVED_BOUNDS_SAMPLE = "DERIVED_BOUNDS_SAMPLE"


class UncertaintyRepresentationType(str, Enum):
    """ADR-0008 formal uncertainty-set structural mode."""

    EMPTY_MISSING = "EMPTY_MISSING"
    SINGLETON = "SINGLETON"
    DISCRETE_CODER_SET = "DISCRETE_CODER_SET"
    PARTIAL_CROSSWALK_SET = "PARTIAL_CROSSWALK_SET"
    DISJOINT_CODER_HYPOTHESES = "DISJOINT_CODER_HYPOTHESES"
    SINGLE_CODER_PARTIAL_ID = "SINGLE_CODER_PARTIAL_ID"


class RobustParetoStatus(str, Enum):
    """ADR-0008 4-state mutually exclusive solution robustness classification."""

    ROBUSTLY_DOMINATED = "ROBUSTLY_DOMINATED"
    ROBUSTLY_NONDOMINATED = "ROBUSTLY_NONDOMINATED"
    CONDITIONALLY_NONDOMINATED = "CONDITIONALLY_NONDOMINATED"
    UNRESOLVED_DUE_TO_CODING_UNCERTAINTY = "UNRESOLVED_DUE_TO_CODING_UNCERTAINTY"


# ---------------------------------------------------------------------------
# ADR-0009 Resource-Good Regimes & Counterfactual Sensitivity Enums / Constants
# ---------------------------------------------------------------------------
FRONTIER_A_NAMESPACE: str = "OBSERVED_DESIGN_FRONTIER"
FRONTIER_B_NAMESPACE: str = "RESOURCE_REGIME_EXPANDED_FRONTIER"
FRONTIER_NAMESPACES: tuple[str, str] = (FRONTIER_A_NAMESPACE, FRONTIER_B_NAMESPACE)

RESOURCE_ELIGIBLE_EVIDENCE_CATEGORIES: frozenset[str] = frozenset(
    {
        "ALLOCABLE_BUDGET_POOL",
        "REVENUE_OVERHEAD_POOL",
        "BONUS_INVESTMENT_POOL",
        "FINANCIAL_RISK_POOL",
        "SHARED_SERVICE_CAPACITY",
        "ACCESS_OR_USAGE_RIGHT",
    }
)

COUNTERFACTUAL_PROHIBITED_PRUNING_SOURCES: frozenset[str] = PROHIBITED_PRUNING_SOURCES | frozenset(
    {
        "GOODS_TAXONOMY",
        "RESOURCE_ELIGIBILITY",
    }
)


class ResourceEligibilityStatus(str, Enum):
    """ADR-0009 subtopic eligibility status for counterfactual resource-regime expansion."""

    ELIGIBLE = "ELIGIBLE"
    CONDITIONAL_RESOURCE_ONLY = "CONDITIONAL_RESOURCE_ONLY"
    INELIGIBLE = "INELIGIBLE"
    UNKNOWN = "UNKNOWN"


class RivalryLevel(str, Enum):
    """ADR-0009 orthogonal economic dimension: consumption rivalry."""

    RIVAL = "RIVAL"
    CONGESTIBLE = "CONGESTIBLE"
    NON_RIVAL = "NON_RIVAL"
    UNKNOWN = "UNKNOWN"


class ExcludabilityLevel(str, Enum):
    """ADR-0009 orthogonal economic dimension: access excludability."""

    EXCLUDABLE = "EXCLUDABLE"
    PARTIALLY_EXCLUDABLE = "PARTIALLY_EXCLUDABLE"
    NON_EXCLUDABLE = "NON_EXCLUDABLE"
    UNKNOWN = "UNKNOWN"


class FinancingRuleType(str, Enum):
    """ADR-0009 orthogonal institutional dimension: financing & contribution rule."""

    INDIVIDUAL = "INDIVIDUAL"
    VOLUNTARY_MEMBER = "VOLUNTARY_MEMBER"
    USAGE_BASED = "USAGE_BASED"
    COLLECTIVE = "COLLECTIVE"
    INSTITUTIONAL = "INSTITUTIONAL"
    MIXED = "MIXED"
    UNKNOWN = "UNKNOWN"


class AccessRuleType(str, Enum):
    """ADR-0009 orthogonal institutional dimension: member and non-member access entitlement."""

    OWNER_ONLY = "OWNER_ONLY"
    MEMBER_PRIORITY = "MEMBER_PRIORITY"
    PAY_PER_USE = "PAY_PER_USE"
    RESIDUAL_CAPACITY = "RESIDUAL_CAPACITY"
    OPEN_ACCESS = "OPEN_ACCESS"
    ALLOCATED_QUOTA = "ALLOCATED_QUOTA"
    OTHER_EXPLICIT = "OTHER_EXPLICIT"
    UNKNOWN = "UNKNOWN"


class ExitPolicyType(str, Enum):
    """ADR-0009 orthogonal institutional dimension: member withdrawal / exit policy."""

    ALLOWED = "ALLOWED"
    CONSTRAINED = "CONSTRAINED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNKNOWN = "UNKNOWN"


class GoodRegimeType(str, Enum):
    """ADR-0009 institutional resource-good regime classification (never ontological essence)."""

    PRIVATE_GOOD = "PRIVATE_GOOD"
    CLUB_GOOD = "CLUB_GOOD"
    COMMON_POOL_RESOURCE = "COMMON_POOL_RESOURCE"
    PUBLIC_GOOD = "PUBLIC_GOOD"
    HYBRID = "HYBRID"


class ProvenanceCategory(str, Enum):
    """ADR-0009 strictly segregated provenance tier for empirical vs counterfactual claims."""

    OBSERVED_RESPONDENT_PREFERENCE = "OBSERVED_RESPONDENT_PREFERENCE"
    INSTITUTIONALLY_DERIVED_MECHANISM = "INSTITUTIONALLY_DERIVED_MECHANISM"
    COUNTERFACTUAL_PREFERENCE_ASSUMPTION = "COUNTERFACTUAL_PREFERENCE_ASSUMPTION"


class FrontierNamespace(str, Enum):
    """ADR-0009 dual-frontier separation: frozen empirical baseline vs counterfactual expansion."""

    FRONTIER_A = "OBSERVED_DESIGN_FRONTIER"
    FRONTIER_B = "RESOURCE_REGIME_EXPANDED_FRONTIER"


class CounterfactualUtilityIdentification(str, Enum):
    """ADR-0009 identification status for counterfactual utility intervals."""

    POINT_IDENTIFIED = "point_identified"
    PARTIALLY_IDENTIFIED = "partially_identified"
    SCENARIO_IDENTIFIED = "scenario_identified"
    UNRESOLVED_COUNTERFACTUAL = "unresolved_counterfactual"


class CounterfactualParetoStatus(str, Enum):
    """ADR-0009 5-state mutually exclusive robustness classification for FRONTIER_B."""

    ROBUSTLY_DOMINATED = "ROBUSTLY_DOMINATED"
    ROBUSTLY_NONDOMINATED = "ROBUSTLY_NONDOMINATED"
    CONDITIONALLY_NONDOMINATED = "CONDITIONALLY_NONDOMINATED"
    UNRESOLVED_DUE_TO_CODING_UNCERTAINTY = "UNRESOLVED_DUE_TO_CODING_UNCERTAINTY"
    UNRESOLVED_DUE_TO_COUNTERFACTUAL_UTILITY = "UNRESOLVED_DUE_TO_COUNTERFACTUAL_UTILITY"


ProbabilityInterpretation = Literal[
    "epistemic_uncertainty_over_preference",
    "explicit_mixed_preference",
    "conditional_or_context_dependent",
]


def _validate_simplex_dict(
    dist: dict[str, float],
    context: str,
    tolerance: float = 1e-4,
) -> None:
    """Validate that a probability dictionary is non-empty, in [0, 1], and sums to 1.0 ± tolerance."""
    if not dist:
        raise ValueError(f"{context}: probability distribution must not be empty.")
    for key, val in dist.items():
        if val < -tolerance or val > 1.0 + tolerance:
            raise ValueError(
                f"{context}: probability for '{key}' must lie in [0.0, 1.0], got {val:.6f}."
            )
    total = sum(dist.values())
    if abs(total - 1.0) > tolerance:
        raise ValueError(
            f"{context}: probability distribution must sum to 1.0 within {tolerance}, got {total:.6f}."
        )


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


@dataclass(frozen=True)
class CanonicalAlternativeCrosswalk:
    """ADR-0008 Level 2 alternative-vocabulary crosswalk scoped strictly to (question_id, canonical_subtopic_id)."""

    question_id: str
    canonical_subtopic_id: str
    crosswalk_status: CrosswalkStatus
    comparable: bool
    coder_a_to_canonical: dict[str, str] = field(default_factory=dict)
    coder_b_to_canonical: dict[str, str] = field(default_factory=dict)
    canonical_keys: list[str] = field(default_factory=list)
    unmapped_keys_a: list[str] = field(default_factory=list)
    unmapped_keys_b: list[str] = field(default_factory=list)
    unmapped_mass_a: float = 0.0
    unmapped_mass_b: float = 0.0
    crosswalk_rule_id: str | None = None
    provenance_rationale: str | None = None
    lossless_deterministic_aggregation: bool = False
    scope_pair: tuple[str, str] | None = None
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if isinstance(self.crosswalk_status, str) and not isinstance(self.crosswalk_status, CrosswalkStatus):
            object.__setattr__(self, "crosswalk_status", CrosswalkStatus(self.crosswalk_status))
        if self.scope_pair is None:
            object.__setattr__(self, "scope_pair", (self.question_id, self.canonical_subtopic_id))
        self.validate()

    def validate(self) -> bool:
        if not self.question_id or not self.canonical_subtopic_id:
            raise ValueError("CanonicalAlternativeCrosswalk requires non-empty question_id and canonical_subtopic_id.")
        if self.scope_pair != (self.question_id, self.canonical_subtopic_id):
            raise ValueError(
                "CanonicalAlternativeCrosswalk scope_pair must match (question_id, canonical_subtopic_id)."
            )
        if self.unmapped_mass_a < 0.0 or self.unmapped_mass_b < 0.0:
            raise ValueError("CanonicalAlternativeCrosswalk unmapped residual mass cannot be negative.")
        if self.crosswalk_status == CrosswalkStatus.NO_VALID_CROSSWALK:
            if self.comparable:
                raise ValueError("NO_VALID_CROSSWALK must have comparable=False.")
            if self.canonical_keys or self.coder_a_to_canonical or self.coder_b_to_canonical:
                raise ValueError(
                    "NO_VALID_CROSSWALK must not emit merged canonical_keys or cross-coder key maps."
                )
        elif self.crosswalk_status in {
            CrosswalkStatus.EXACT_KEY_MATCH,
            CrosswalkStatus.SEMANTIC_KEY_MATCH,
            CrosswalkStatus.SCENARIO_PREFIX_MATCH,
        }:
            if not self.comparable:
                raise ValueError(f"{self.crosswalk_status.value} must have comparable=True.")
        elif self.crosswalk_status == CrosswalkStatus.PARTIAL_CROSSWALK:
            if not (self.unmapped_keys_a or self.unmapped_keys_b or self.unmapped_mass_a > 0.0 or self.unmapped_mass_b > 0.0):
                raise ValueError(
                    "PARTIAL_CROSSWALK must record explicit unmapped_keys_* or positive unmapped_mass_*."
                )
        elif self.crosswalk_status == CrosswalkStatus.SINGLE_CODER_ONLY:
            if self.comparable:
                raise ValueError("SINGLE_CODER_ONLY crosswalk must have comparable=False.")
        return True


@dataclass(frozen=True)
class PreferenceUncertaintySet:
    """ADR-0008 formal uncertainty-set representation preserving discrete coder scenarios,
    disjoint unaligned hypotheses, marginal bounds, single-coder partial ID, and ISSUE-005 variants.
    """

    representation_type: UncertaintyRepresentationType
    discrete_scenarios: list[dict[str, float]] = field(default_factory=list)
    disjoint_coder_hypotheses: dict[str, dict[str, float]] = field(default_factory=dict)
    lower_bounds: dict[str, float] | None = None
    upper_bounds: dict[str, float] | None = None
    interpretation_variants: list[ProbabilityInterpretation] = field(default_factory=list)
    single_coder_active_side: Literal["coder_a", "coder_b"] | None = None
    single_coder_uncertainty_type: SingleCoderUncertaintyType | None = None
    non_coding_coder_state: Literal["EPISTEMICALLY_UNOBSERVED"] | None = None
    allows_derived_convex_hull: bool = False
    derived_scenarios: list[dict[str, Any]] = field(default_factory=list)
    scenario_origin: DerivedScenarioOrigin = DerivedScenarioOrigin.OBSERVED_CODER_EVIDENCE
    double_count_guard_applied: bool = False
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if isinstance(self.representation_type, str) and not isinstance(
            self.representation_type, UncertaintyRepresentationType
        ):
            object.__setattr__(
                self, "representation_type", UncertaintyRepresentationType(self.representation_type)
            )
        if isinstance(self.single_coder_uncertainty_type, str) and not isinstance(
            self.single_coder_uncertainty_type, SingleCoderUncertaintyType
        ):
            object.__setattr__(
                self,
                "single_coder_uncertainty_type",
                SingleCoderUncertaintyType(self.single_coder_uncertainty_type),
            )
        if isinstance(self.scenario_origin, str) and not isinstance(self.scenario_origin, DerivedScenarioOrigin):
            object.__setattr__(self, "scenario_origin", DerivedScenarioOrigin(self.scenario_origin))
        self.validate()

    def validate(self, tolerance: float = 1e-4) -> bool:
        if self.representation_type == UncertaintyRepresentationType.EMPTY_MISSING:
            if self.discrete_scenarios or self.disjoint_coder_hypotheses:
                raise ValueError("EMPTY_MISSING uncertainty set must have empty scenarios and hypotheses.")
        elif self.representation_type == UncertaintyRepresentationType.DISJOINT_CODER_HYPOTHESES:
            if self.discrete_scenarios:
                raise ValueError(
                    "DISJOINT_CODER_HYPOTHESES (NO_VALID_CROSSWALK) must keep discrete_scenarios empty/unmerged."
                )
            if not self.disjoint_coder_hypotheses:
                raise ValueError("DISJOINT_CODER_HYPOTHESES requires raw coder_a / coder_b distributions.")
            for side, dist in self.disjoint_coder_hypotheses.items():
                _validate_simplex_dict(dist, f"PreferenceUncertaintySet.disjoint_coder_hypotheses[{side}]", tolerance)
        else:
            if not self.discrete_scenarios:
                raise ValueError(
                    f"PreferenceUncertaintySet ({self.representation_type.value}) requires >= 1 discrete scenario."
                )
            for idx, sc in enumerate(self.discrete_scenarios):
                _validate_simplex_dict(sc, f"PreferenceUncertaintySet.discrete_scenarios[{idx}]", tolerance)
            if self.representation_type == UncertaintyRepresentationType.SINGLE_CODER_PARTIAL_ID:
                if self.single_coder_active_side not in ("coder_a", "coder_b"):
                    raise ValueError("SINGLE_CODER_PARTIAL_ID requires single_coder_active_side in {'coder_a', 'coder_b'}.")
                if self.non_coding_coder_state != "EPISTEMICALLY_UNOBSERVED":
                    raise ValueError(
                        "SINGLE_CODER_PARTIAL_ID requires non_coding_coder_state == 'EPISTEMICALLY_UNOBSERVED'."
                    )
                silent_side = "coder_b" if self.single_coder_active_side == "coder_a" else "coder_a"
                if silent_side in self.disjoint_coder_hypotheses and self.disjoint_coder_hypotheses[silent_side] is not None:
                    raise ValueError(
                        f"SINGLE_CODER_PARTIAL_ID forbids populating silent coder '{silent_side}' distribution."
                    )

        if self.lower_bounds is not None and self.upper_bounds is not None:
            for k, lo in self.lower_bounds.items():
                hi = self.upper_bounds.get(k)
                if hi is not None and lo > hi + tolerance:
                    raise ValueError(f"PreferenceUncertaintySet bounds inverted for '{k}': {lo} > {hi}.")
                if lo < -tolerance or lo > 1.0 + tolerance:
                    raise ValueError(f"PreferenceUncertaintySet lower bound out of [0, 1] for '{k}': {lo}.")
            for k, hi in self.upper_bounds.items():
                if hi < -tolerance or hi > 1.0 + tolerance:
                    raise ValueError(f"PreferenceUncertaintySet upper bound out of [0, 1] for '{k}': {hi}.")

        derived_allowed = {
            DerivedScenarioOrigin.DERIVED_ROBUSTNESS_SCENARIO.value,
            DerivedScenarioOrigin.DERIVED_ROBUSTNESS_CONVEX_BARYCENTER.value,
            DerivedScenarioOrigin.DERIVED_BOUNDS_SAMPLE.value,
        }
        for idx, derived in enumerate(self.derived_scenarios):
            origin = derived.get("scenario_origin")
            origin_val = origin.value if isinstance(origin, Enum) else origin
            if origin_val not in derived_allowed:
                raise ValueError(
                    f"PreferenceUncertaintySet.derived_scenarios[{idx}] must carry derived scenario_origin in {sorted(derived_allowed)}, got {origin_val!r}."
                )
            if "probabilities" in derived and derived["probabilities"] is not None:
                _validate_simplex_dict(
                    derived["probabilities"],
                    f"PreferenceUncertaintySet.derived_scenarios[{idx}].probabilities",
                    tolerance,
                )
        return True



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
    is_primary_question: bool = True
    question_scope: Literal["primary", "optional_contextual_remarks"] = "primary"
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
    offset_reference_text: str = "source_text"
    span_role: Literal[
        "substantive_evidence",
        "explicit_uncertainty_or_no_opinion",
        "value_evidence",
    ] = "substantive_evidence"
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
    polarity: float | None
    semantic_importance: float
    coder_confidence: float
    coder_agreement: float
    polarity_uncertainty_interval: tuple[float, float] | None
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
    probability_interpretation: ProbabilityInterpretation | None = None
    # Optional derived scalar ONLY when alternatives have an analytically defensible ordering
    derived_scalar_score: float | None = None
    # Optional fields
    economic_good_class: EconomicGoodClass | None = None
    perception_category: str | None = None
    value_assignment_ids: list[str] = field(default_factory=list)
    reconciliation_method: Literal[
        "EXACT_MATCH",
        "ARBITRATED_SPAN_CHECK",
        "HIGH_UNCERTAINTY_FLAGGED",
        "UNCERTAINTY_SET_PRESERVED",
        "NO_VALID_CROSSWALK_UNMERGED",
        "SINGLE_CODER_PARTIAL_ID",
    ] | None = None
    rationale_summary: str | None = None
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.reconciliation_method in FORBIDDEN_RECONCILIATION_METHODS:
            raise ValueError(
                f"CodingResult {self.coding_id}: reconciliation_method '{self.reconciliation_method}' "
                "is strictly forbidden by ADR-0008 (uncalibrated / unauthorized averaging)."
            )

    def validate_invariants(self, tolerance: float = 1e-4) -> None:
        if self.reconciliation_method in FORBIDDEN_RECONCILIATION_METHODS:
            raise ValueError(
                f"CodingResult {self.coding_id}: reconciliation_method '{self.reconciliation_method}' "
                "is strictly forbidden by ADR-0008."
            )
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
# 8. PreferenceCell (Aligned with ADR-0005 & ADR-0008 Distributional Contract)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PreferenceCell:
    cell_id: str
    participant_id: str
    question_id: str = ""
    subtopic_id: str = ""
    missingness_state: MissingnessState = MissingnessState.OBSERVED_USABLE
    alternative_probabilities: dict[str, float] = field(default_factory=dict)
    semantic_importance: float | None = None
    coder_confidence: float | None = None
    coder_agreement: float | None = None
    source_coding_id: str = ""
    evidence_span_ids: list[str] = field(default_factory=list)
    provenance: ProvenanceMeta | None = None
    # Uncertainty over probability simplex & open methodological interpretation tag
    probability_lower_bounds: dict[str, float] | None = None
    probability_upper_bounds: dict[str, float] | None = None
    probability_std_errors: dict[str, float] | None = None
    probability_interpretation: ProbabilityInterpretation | None = None
    # Optional derived scalar ONLY when alternatives have an analytically defensible ordering
    derived_scalar_score: float | None = None
    # Optional coder diagnostics
    coder_a_probabilities: dict[str, float] | None = None
    coder_b_probabilities: dict[str, float] | None = None
    coder_a_importance: float | None = None
    coder_b_importance: float | None = None
    economic_good_class: str | None = None
    # Convenience aliases for registry/matrix serialization without duplicating PreferenceCell
    question_or_dimension_id: str | None = None
    evidence_ids: list[str] = field(default_factory=list)
    # ADR-0008 Dual-Coder Uncertainty Set & Level 2 Crosswalk Contract
    canonical_subtopic_id: str | None = None
    coder_a_distribution: dict[str, float] | None = None
    coder_b_distribution: dict[str, float] | None = None
    canonical_alternative_crosswalk: CanonicalAlternativeCrosswalk | None = None
    coder_a_probability_interpretation: ProbabilityInterpretation | None = None
    coder_b_probability_interpretation: ProbabilityInterpretation | None = None
    semantic_importance_a: float | None = None
    semantic_importance_b: float | None = None
    coder_confidence_a: float | None = None
    coder_confidence_b: float | None = None
    agreement_status: AgreementStatus | None = None
    uncertainty_class: UncertaintyClass | None = None
    preference_uncertainty_set: PreferenceUncertaintySet | None = None
    source_evidence_ids: list[str] = field(default_factory=list)
    reconciliation_status: ReconciliationStatus | None = None
    resolved_point_distribution: dict[str, float] | None = None
    provenance_category: ProvenanceCategory = ProvenanceCategory.OBSERVED_RESPONDENT_PREFERENCE
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if isinstance(self.missingness_state, str) and not isinstance(self.missingness_state, MissingnessState):
            object.__setattr__(self, "missingness_state", MissingnessState(self.missingness_state))
        if isinstance(self.agreement_status, str) and not isinstance(self.agreement_status, AgreementStatus):
            object.__setattr__(self, "agreement_status", AgreementStatus(self.agreement_status))
        if isinstance(self.uncertainty_class, str) and not isinstance(self.uncertainty_class, UncertaintyClass):
            object.__setattr__(self, "uncertainty_class", UncertaintyClass(self.uncertainty_class))
        if isinstance(self.reconciliation_status, str) and not isinstance(
            self.reconciliation_status, ReconciliationStatus
        ):
            object.__setattr__(self, "reconciliation_status", ReconciliationStatus(self.reconciliation_status))
        if isinstance(self.provenance_category, str) and not isinstance(
            self.provenance_category, ProvenanceCategory
        ):
            object.__setattr__(self, "provenance_category", ProvenanceCategory(self.provenance_category))
        if self.provenance_category != ProvenanceCategory.OBSERVED_RESPONDENT_PREFERENCE:
            raise ValueError(
                f"PreferenceCell {self.cell_id}: PreferenceMatrix cells must carry "
                "OBSERVED_RESPONDENT_PREFERENCE provenance only (ADR-0009 VG-05)."
            )

        if not self.question_id and self.question_or_dimension_id:
            object.__setattr__(self, "question_id", self.question_or_dimension_id)
        elif self.question_id and not self.question_or_dimension_id:
            object.__setattr__(self, "question_or_dimension_id", self.question_id)

        if not self.subtopic_id and self.canonical_subtopic_id:
            object.__setattr__(self, "subtopic_id", self.canonical_subtopic_id)
        elif self.subtopic_id and not self.canonical_subtopic_id:
            object.__setattr__(self, "canonical_subtopic_id", self.subtopic_id)

        merged_evidence = (
            list(self.evidence_span_ids)
            or list(self.evidence_ids)
            or list(self.source_evidence_ids)
        )
        if merged_evidence:
            if not self.evidence_span_ids:
                object.__setattr__(self, "evidence_span_ids", list(merged_evidence))
            if not self.evidence_ids:
                object.__setattr__(self, "evidence_ids", list(merged_evidence))
            if not self.source_evidence_ids:
                object.__setattr__(self, "source_evidence_ids", list(merged_evidence))

        if self.coder_a_distribution is None and self.coder_a_probabilities is not None:
            object.__setattr__(self, "coder_a_distribution", dict(self.coder_a_probabilities))
        elif self.coder_a_distribution is not None and self.coder_a_probabilities is None:
            object.__setattr__(self, "coder_a_probabilities", dict(self.coder_a_distribution))

        if self.coder_b_distribution is None and self.coder_b_probabilities is not None:
            object.__setattr__(self, "coder_b_distribution", dict(self.coder_b_probabilities))
        elif self.coder_b_distribution is not None and self.coder_b_probabilities is None:
            object.__setattr__(self, "coder_b_probabilities", dict(self.coder_b_distribution))

        if self.semantic_importance_a is None and self.coder_a_importance is not None:
            object.__setattr__(self, "semantic_importance_a", self.coder_a_importance)
        elif self.semantic_importance_a is not None and self.coder_a_importance is None:
            object.__setattr__(self, "coder_a_importance", self.semantic_importance_a)

        if self.semantic_importance_b is None and self.coder_b_importance is not None:
            object.__setattr__(self, "semantic_importance_b", self.coder_b_importance)
        elif self.semantic_importance_b is not None and self.coder_b_importance is None:
            object.__setattr__(self, "coder_b_importance", self.semantic_importance_b)

        if self.uncertainty_class == UncertaintyClass.NONE_CONSENSUS:
            if self.resolved_point_distribution is None and self.alternative_probabilities:
                object.__setattr__(self, "resolved_point_distribution", dict(self.alternative_probabilities))
            elif self.resolved_point_distribution is not None and not self.alternative_probabilities:
                object.__setattr__(self, "alternative_probabilities", dict(self.resolved_point_distribution))
        elif self.uncertainty_class is None and self.resolved_point_distribution is not None and not self.alternative_probabilities:
            object.__setattr__(self, "alternative_probabilities", dict(self.resolved_point_distribution))

        for fname, fval in (
            ("coder_confidence", self.coder_confidence),
            ("coder_confidence_a", self.coder_confidence_a),
            ("coder_confidence_b", self.coder_confidence_b),
            ("semantic_importance", self.semantic_importance),
            ("semantic_importance_a", self.semantic_importance_a),
            ("semantic_importance_b", self.semantic_importance_b),
        ):
            if fval is not None and not (0.0 <= fval <= 1.0):
                raise ValueError(f"PreferenceCell {self.cell_id}: {fname} must be in [0.0, 1.0].")

    def validate_simplex(self, tolerance: float = 1e-4) -> bool:
        """Verify ADR-0005, ADR-0008, & ADR-0009 simplex, crosswalk, missingness, provenance, and uncertainty-set invariants."""
        if self.provenance_category != ProvenanceCategory.OBSERVED_RESPONDENT_PREFERENCE:
            raise ValueError(
                f"PreferenceCell {self.cell_id}: PreferenceMatrix cells must carry "
                "OBSERVED_RESPONDENT_PREFERENCE provenance only (ADR-0009 VG-05)."
            )
        if not self.missingness_state.is_usable():
            if self.resolved_point_distribution is not None:
                raise ValueError(
                    f"PreferenceCell {self.cell_id}: non-usable state {self.missingness_state.value} "
                    "must keep resolved_point_distribution=None."
                )
            if self.alternative_probabilities:
                raise ValueError(
                    f"PreferenceCell {self.cell_id}: non-usable state {self.missingness_state.value} "
                    "must have empty alternative_probabilities."
                )
            if self.preference_uncertainty_set is not None:
                if (
                    self.preference_uncertainty_set.discrete_scenarios
                    or self.preference_uncertainty_set.disjoint_coder_hypotheses
                ):
                    raise ValueError(
                        f"PreferenceCell {self.cell_id}: non-usable state {self.missingness_state.value} "
                        "must have empty uncertainty scenarios and hypotheses."
                    )
            return True

        # Observed usable cell validation
        if self.coder_a_distribution is not None:
            _validate_simplex_dict(
                self.coder_a_distribution,
                f"PreferenceCell {self.cell_id}.coder_a_distribution",
                tolerance,
            )
        if self.coder_b_distribution is not None:
            _validate_simplex_dict(
                self.coder_b_distribution,
                f"PreferenceCell {self.cell_id}.coder_b_distribution",
                tolerance,
            )

        if self.canonical_alternative_crosswalk is not None:
            self.canonical_alternative_crosswalk.validate()
            if self.question_id and self.canonical_alternative_crosswalk.question_id != self.question_id:
                raise ValueError(
                    f"PreferenceCell {self.cell_id}: crosswalk question_id mismatch "
                    f"({self.canonical_alternative_crosswalk.question_id} != {self.question_id})."
                )
            if (
                self.canonical_subtopic_id
                and self.canonical_alternative_crosswalk.canonical_subtopic_id != self.canonical_subtopic_id
            ):
                raise ValueError(
                    f"PreferenceCell {self.cell_id}: crosswalk canonical_subtopic_id mismatch."
                )
            if self.canonical_alternative_crosswalk.crosswalk_status == CrosswalkStatus.NO_VALID_CROSSWALK:
                if self.resolved_point_distribution is not None:
                    raise ValueError(
                        f"PreferenceCell {self.cell_id}: NO_VALID_CROSSWALK forbids resolved_point_distribution."
                    )
                if self.reconciliation_status == ReconciliationStatus.AGREEMENT_EXACT:
                    raise ValueError(
                        f"PreferenceCell {self.cell_id}: NO_VALID_CROSSWALK cannot be AGREEMENT_EXACT."
                    )
                if (
                    self.preference_uncertainty_set is not None
                    and self.preference_uncertainty_set.representation_type
                    != UncertaintyRepresentationType.DISJOINT_CODER_HYPOTHESES
                ):
                    raise ValueError(
                        f"PreferenceCell {self.cell_id}: NO_VALID_CROSSWALK requires "
                        "DISJOINT_CODER_HYPOTHESES uncertainty set."
                    )

        # ISSUE-005: differing probability interpretations prevent exact consensus & retain variants
        if (
            self.coder_a_probability_interpretation is not None
            and self.coder_b_probability_interpretation is not None
            and self.coder_a_probability_interpretation != self.coder_b_probability_interpretation
        ):
            if self.agreement_status == AgreementStatus.EXACT_AGREEMENT:
                raise ValueError(
                    f"PreferenceCell {self.cell_id}: differing probability_interpretation "
                    "cannot produce EXACT_AGREEMENT (ISSUE-005 Rule 4A)."
                )
            if self.reconciliation_status == ReconciliationStatus.AGREEMENT_EXACT:
                raise ValueError(
                    f"PreferenceCell {self.cell_id}: differing probability_interpretation "
                    "cannot produce AGREEMENT_EXACT (ISSUE-005 Rule 4A)."
                )
            if self.resolved_point_distribution is not None:
                raise ValueError(
                    f"PreferenceCell {self.cell_id}: differing probability_interpretation "
                    "requires resolved_point_distribution=None."
                )
            if self.preference_uncertainty_set is not None:
                expected_interps = {
                    self.coder_a_probability_interpretation,
                    self.coder_b_probability_interpretation,
                }
                if not expected_interps.issubset(set(self.preference_uncertainty_set.interpretation_variants)):
                    raise ValueError(
                        f"PreferenceCell {self.cell_id}: differing probability_interpretation "
                        "must retain both variants in preference_uncertainty_set.interpretation_variants."
                    )

        if self.uncertainty_class in {
            UncertaintyClass.SINGLE_CODER_PARTIAL_ID_OMISSION,
            UncertaintyClass.SINGLE_CODER_PARTIAL_ID_GRANULARITY,
        }:
            has_a = self.coder_a_distribution is not None
            has_b = self.coder_b_distribution is not None
            if has_a == has_b:
                raise ValueError(
                    f"PreferenceCell {self.cell_id}: {self.uncertainty_class.value} requires exactly one "
                    "active coder distribution and the silent coder kept as None (never 0.0-filled)."
                )
            if self.resolved_point_distribution is not None:
                raise ValueError(
                    f"PreferenceCell {self.cell_id}: single-coder partial identification requires "
                    "resolved_point_distribution=None."
                )

        if self.preference_uncertainty_set is not None:
            self.preference_uncertainty_set.validate(tolerance)

        if self.uncertainty_class is not None or self.preference_uncertainty_set is not None:
            if self.uncertainty_class == UncertaintyClass.NONE_CONSENSUS:
                target = (
                    self.resolved_point_distribution
                    if self.resolved_point_distribution is not None
                    else self.alternative_probabilities
                )
                total = sum(target.values()) if target else 0.0
                if not target or abs(total - 1.0) > tolerance:
                    raise ValueError(
                        f"PreferenceCell {self.cell_id}: alternative_probabilities must sum to 1.0 "
                        f"within {tolerance}, got {total:.6f}"
                    )
            else:
                if self.resolved_point_distribution is not None:
                    raise ValueError(
                        f"PreferenceCell {self.cell_id}: resolved_point_distribution must be None when "
                        f"uncertainty_class={self.uncertainty_class.value if self.uncertainty_class else None}."
                    )
                if self.alternative_probabilities:
                    raise ValueError(
                        f"PreferenceCell {self.cell_id}: alternative_probabilities must remain empty when "
                        "unresolved or set-valued (unauthorized point collapsing forbidden by ADR-0008)."
                    )
                if self.preference_uncertainty_set is None:
                    raise ValueError(
                        f"PreferenceCell {self.cell_id}: preference_uncertainty_set is required when "
                        f"uncertainty_class={self.uncertainty_class.value if self.uncertainty_class else None}."
                    )
        else:
            if self.resolved_point_distribution is not None:
                _validate_simplex_dict(
                    self.resolved_point_distribution,
                    f"PreferenceCell {self.cell_id}.resolved_point_distribution",
                    tolerance,
                )
            total = sum(self.alternative_probabilities.values())
            if not self.alternative_probabilities or abs(total - 1.0) > tolerance:
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
    uncertainty_class_counts: dict[str, int] = field(default_factory=dict)
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
    is_minority_position: bool = False
    pruned_by_clusters_or_values: bool = False
    pruning_sources_applied: list[str] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        self.validate_invariants()

    def validate_invariants(self) -> bool:
        if self.pruned_by_clusters_or_values:
            raise ValueError(
                f"FeasibleAlternative {self.alternative_id}: pruning by clusters or values is forbidden (ADR-0008)."
            )
        prohibited = set(self.pruning_sources_applied) & PROHIBITED_PRUNING_SOURCES
        if prohibited:
            raise ValueError(
                f"FeasibleAlternative {self.alternative_id}: prohibited pruning source(s) {sorted(prohibited)}."
            )
        return True


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
    pruned_by_clusters_or_values: bool = False
    pruned_by_coder_disagreement: bool = False
    pruned_by_coder_confidence: bool = False
    pruning_sources_applied: list[str] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        self.validate_invariants()

    def validate_invariants(self) -> bool:
        if self.pruned_by_clusters_or_values or self.pruned_by_coder_disagreement or self.pruned_by_coder_confidence:
            raise ValueError(
                f"GovernanceSolution {self.solution_id}: solutions may only be pruned by explicit logical, "
                "institutional, or dependency constraints — never clusters, values, coder disagreement, or confidence."
            )
        prohibited = set(self.pruning_sources_applied) & PROHIBITED_PRUNING_SOURCES
        if prohibited:
            raise ValueError(
                f"GovernanceSolution {self.solution_id}: prohibited pruning source(s) {sorted(prohibited)}."
            )
        return True


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
    # ADR-0008 scenario & interpretation provenance
    interpretation_modes_evaluated: list[ProbabilityInterpretation] = field(default_factory=list)
    derived_scenario_origins: list[DerivedScenarioOrigin] = field(default_factory=list)
    min_scenario_utility: float | None = None
    max_scenario_utility: float | None = None
    single_coder_uncertainty_bounded: bool = False
    uses_coder_confidence_as_weight: bool = False
    double_count_guard_evaluated: bool = False
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        coerced_origins = [
            DerivedScenarioOrigin(o) if isinstance(o, str) and not isinstance(o, DerivedScenarioOrigin) else o
            for o in self.derived_scenario_origins
        ]
        object.__setattr__(self, "derived_scenario_origins", coerced_origins)
        self.validate_invariants()

    def validate_invariants(self) -> bool:
        if self.uses_coder_confidence_as_weight:
            raise ValueError(
                f"ParticipantUtility {self.utility_id}: coder_confidence must NEVER be used as a "
                "utility or aggregation weight multiplier (ADR-0005 / ADR-0008)."
            )
        if (
            self.min_scenario_utility is not None
            and self.max_scenario_utility is not None
            and self.min_scenario_utility > self.max_scenario_utility + 1e-9
        ):
            raise ValueError(
                f"ParticipantUtility {self.utility_id}: min_scenario_utility ({self.min_scenario_utility}) "
                f"exceeds max_scenario_utility ({self.max_scenario_utility})."
            )
        return True


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
    # ADR-0008 4-state mutually exclusive robustness classification
    solution_robustness_statuses: dict[str, RobustParetoStatus] = field(default_factory=dict)
    robustly_dominated_solution_ids: list[str] = field(default_factory=list)
    robustly_nondominated_solution_ids: list[str] = field(default_factory=list)
    conditionally_nondominated_solution_ids: list[str] = field(default_factory=list)
    unresolved_due_to_coding_uncertainty_ids: list[str] = field(default_factory=list)
    conditional_nondominated_regimes: dict[str, list[str]] = field(default_factory=dict)
    derived_scenario_origins_used: list[DerivedScenarioOrigin] = field(default_factory=list)
    robust_core_inclusion_threshold: float = 1.0
    pruned_by_clusters_values_or_disagreement: bool = False
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        coerced_statuses = {
            sid: (RobustParetoStatus(st) if isinstance(st, str) and not isinstance(st, RobustParetoStatus) else st)
            for sid, st in self.solution_robustness_statuses.items()
        }
        object.__setattr__(self, "solution_robustness_statuses", coerced_statuses)
        coerced_origins = [
            DerivedScenarioOrigin(o) if isinstance(o, str) and not isinstance(o, DerivedScenarioOrigin) else o
            for o in self.derived_scenario_origins_used
        ]
        object.__setattr__(self, "derived_scenario_origins_used", coerced_origins)
        self.validate_invariants()

    def validate_invariants(self) -> bool:
        if self.pruned_by_clusters_values_or_disagreement:
            raise ValueError(
                f"RobustParetoResult {self.robust_pareto_id}: solutions must NEVER be pruned by clusters, "
                "organisational values, or unresolved coder disagreement (ADR-0008)."
            )
        buckets = [
            ("ROBUSTLY_DOMINATED", set(self.robustly_dominated_solution_ids)),
            ("ROBUSTLY_NONDOMINATED", set(self.robustly_nondominated_solution_ids)),
            ("CONDITIONALLY_NONDOMINATED", set(self.conditionally_nondominated_solution_ids)),
            ("UNRESOLVED_DUE_TO_CODING_UNCERTAINTY", set(self.unresolved_due_to_coding_uncertainty_ids)),
        ]
        seen: dict[str, str] = {}
        for label, sids in buckets:
            for sid in sids:
                if sid in seen:
                    raise ValueError(
                        f"RobustParetoResult {self.robust_pareto_id}: solution '{sid}' cannot belong to both "
                        f"{seen[sid]} and {label} (statuses must be mutually exclusive)."
                    )
                seen[sid] = label
        if self.solution_robustness_statuses and seen:
            for sid, status in self.solution_robustness_statuses.items():
                if sid in seen and seen[sid] != status.value:
                    raise ValueError(
                        f"RobustParetoResult {self.robust_pareto_id}: solution '{sid}' status map {status.value} "
                        f"conflicts with bucket {seen[sid]}."
                    )
        return True



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

ADR0008_SUPPORTING_CONTRACT_TYPES: dict[str, type] = {
    "CanonicalAlternativeCrosswalk": CanonicalAlternativeCrosswalk,
    "PreferenceUncertaintySet": PreferenceUncertaintySet,
}


# ---------------------------------------------------------------------------
# ADR-0009 Resource-Good Regimes & Counterfactual Sensitivity Contracts
# ---------------------------------------------------------------------------
_ACCESS_RANK: dict[str, int] = {
    "NONE": 0,
    AccessRuleType.RESIDUAL_CAPACITY.value: 1,
    AccessRuleType.PAY_PER_USE.value: 2,
    AccessRuleType.OTHER_EXPLICIT.value: 2,
    AccessRuleType.ALLOCATED_QUOTA.value: 3,
    AccessRuleType.MEMBER_PRIORITY.value: 4,
    AccessRuleType.OWNER_ONLY.value: 5,
}


def _coerce_enum(value: Any, enum_cls: type[Enum]) -> Any:
    if isinstance(value, str) and not isinstance(value, enum_cls):
        return enum_cls(value)
    return value


@dataclass(frozen=True)
class ResourceEligibilityAssessment:
    """ADR-0009 subtopic-level RESOURCE_ELIGIBILITY contract preventing forced labeling."""

    subtopic_id: str
    question_id: str
    eligibility_status: ResourceEligibilityStatus
    analytical_rationale: str
    resource_evidence_basis: str | None = None
    evidence_span_ids: list[str] = field(default_factory=list)
    is_pure_opinion_or_perception: bool = False
    requires_segregated_sensitivity_tier: bool = False
    segregated_tier_id: str | None = None
    risk_pooling_caveat: str | None = None
    double_count_guard_group_id: str | None = None
    assigned_regime_types: list[GoodRegimeType] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "eligibility_status", _coerce_enum(self.eligibility_status, ResourceEligibilityStatus))
        coerced_regimes = [_coerce_enum(r, GoodRegimeType) for r in self.assigned_regime_types]
        object.__setattr__(self, "assigned_regime_types", coerced_regimes)
        self.validate()

    def validate(self) -> bool:
        if not self.subtopic_id or not self.subtopic_id.strip():
            raise ValueError("ResourceEligibilityAssessment requires non-empty subtopic_id.")
        if not self.question_id or not self.question_id.strip():
            raise ValueError("ResourceEligibilityAssessment requires non-empty question_id.")
        if not self.analytical_rationale or not self.analytical_rationale.strip():
            raise ValueError("ResourceEligibilityAssessment requires non-empty analytical_rationale.")
        if self.is_pure_opinion_or_perception and self.eligibility_status != ResourceEligibilityStatus.INELIGIBLE:
            raise ValueError(
                f"Subtopic {self.subtopic_id}: pure opinion, perception, or diagnostic subtopics "
                "must remain INELIGIBLE (ADR-0009 VG-02)."
            )
        if self.eligibility_status in {
            ResourceEligibilityStatus.ELIGIBLE,
            ResourceEligibilityStatus.CONDITIONAL_RESOURCE_ONLY,
        }:
            if not self.resource_evidence_basis or not self.resource_evidence_basis.strip():
                raise ValueError(
                    f"Subtopic {self.subtopic_id}: {self.eligibility_status.value} requires explicit "
                    "resource_evidence_basis referencing an allocable resource, pool, or service capacity."
                )
        if self.eligibility_status == ResourceEligibilityStatus.CONDITIONAL_RESOURCE_ONLY:
            if not self.requires_segregated_sensitivity_tier or not (self.segregated_tier_id or "").strip():
                raise ValueError(
                    f"Subtopic {self.subtopic_id}: CONDITIONAL_RESOURCE_ONLY requires "
                    "requires_segregated_sensitivity_tier=True and a non-empty segregated_tier_id."
                )
        if self.eligibility_status in {ResourceEligibilityStatus.INELIGIBLE, ResourceEligibilityStatus.UNKNOWN}:
            if self.assigned_regime_types:
                raise ValueError(
                    f"Subtopic {self.subtopic_id}: {self.eligibility_status.value} subtopics "
                    "cannot receive GoodRegimeType assignments."
                )
        return True


@dataclass(frozen=True)
class ClubGoodMechanism:
    """ADR-0009 Section 5 10-field operational CLUB_GOOD mechanism contract (rejects bare labels)."""

    member_contribution_rule: str
    non_member_compulsory_contribution: float
    member_access: AccessRuleType
    non_member_access: AccessRuleType | Literal["NONE"]
    member_priority: str
    exit_rule: ExitPolicyType
    capacity_or_congestion_rule: str
    governance_rule: str
    pricing_or_contribution_rule: str
    voluntary_membership: bool = True
    membership_mode: Literal["VOLUNTARY"] = "VOLUNTARY"
    regime: Literal["CLUB_GOOD"] = "CLUB_GOOD"
    governing_constraint_id: str | None = None
    non_member_access_description: str | None = None
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "member_access", _coerce_enum(self.member_access, AccessRuleType))
        if self.non_member_access != "NONE":
            object.__setattr__(self, "non_member_access", _coerce_enum(self.non_member_access, AccessRuleType))
        object.__setattr__(self, "exit_rule", _coerce_enum(self.exit_rule, ExitPolicyType))
        self.validate()

    def validate(self) -> bool:
        if self.regime != "CLUB_GOOD":
            raise ValueError(f"ClubGoodMechanism regime must be 'CLUB_GOOD', got {self.regime!r}.")
        if self.voluntary_membership is not True or self.membership_mode != "VOLUNTARY":
            raise ValueError(
                "ClubGoodMechanism requires voluntary_membership=True and membership_mode='VOLUNTARY' (ADR-0009 §5)."
            )
        if isinstance(self.non_member_compulsory_contribution, bool) or abs(
            float(self.non_member_compulsory_contribution)
        ) > 1e-12:
            raise ValueError(
                "ClubGoodMechanism requires non_member_compulsory_contribution == 0.0 exact (ADR-0009 VG-04)."
            )
        for field_name in (
            "member_contribution_rule",
            "member_priority",
            "capacity_or_congestion_rule",
            "governance_rule",
            "pricing_or_contribution_rule",
        ):
            val = getattr(self, field_name)
            if not isinstance(val, str) or not val.strip():
                raise ValueError(f"ClubGoodMechanism requires non-empty operational field '{field_name}'.")
        if self.member_access in {AccessRuleType.UNKNOWN, AccessRuleType.OPEN_ACCESS}:
            raise ValueError(
                f"ClubGoodMechanism member_access cannot be {self.member_access.value}; members must have excludable priority."
            )
        non_member_val = self.non_member_access if self.non_member_access == "NONE" else self.non_member_access.value
        if non_member_val in {
            AccessRuleType.UNKNOWN.value,
            AccessRuleType.OPEN_ACCESS.value,
            AccessRuleType.OWNER_ONLY.value,
        }:
            raise ValueError(
                f"ClubGoodMechanism non_member_access={non_member_val!r} is incompatible with excludable club provision."
            )
        if self.non_member_access == AccessRuleType.OTHER_EXPLICIT and not (self.non_member_access_description or "").strip():
            raise ValueError("ClubGoodMechanism non_member_access=OTHER_EXPLICIT requires non_member_access_description.")
        m_rank = _ACCESS_RANK.get(self.member_access.value, -1)
        nm_rank = _ACCESS_RANK.get(non_member_val, 99)
        if m_rank <= nm_rank:
            raise ValueError(
                f"ClubGoodMechanism requires strictly higher member entitlement than non-member access "
                f"(member_access={self.member_access.value}, non_member_access={non_member_val})."
            )
        if self.exit_rule in {ExitPolicyType.NOT_APPLICABLE, ExitPolicyType.UNKNOWN}:
            raise ValueError(
                f"ClubGoodMechanism requires explicit exit_rule ALLOWED or CONSTRAINED, got {self.exit_rule.value}."
            )
        if self.exit_rule == ExitPolicyType.CONSTRAINED and not (self.governing_constraint_id or "").strip():
            raise ValueError(
                "ClubGoodMechanism with exit_rule=CONSTRAINED requires explicit governing_constraint_id."
            )
        return True


ClubGoodContract = ClubGoodMechanism


@dataclass(frozen=True)
class ResourceRegimeSpec:
    """ADR-0009 5-dimension institutional regime specification (multiple regimes allowed; never ontological)."""

    regime_id: str
    subtopic_id: str
    question_id: str
    regime_type: GoodRegimeType
    rivalry: RivalryLevel
    excludability: ExcludabilityLevel
    financing: FinancingRuleType
    access: AccessRuleType
    exit_policy: ExitPolicyType
    eligibility_status: ResourceEligibilityStatus = ResourceEligibilityStatus.ELIGIBLE
    provenance_category: ProvenanceCategory = ProvenanceCategory.INSTITUTIONALLY_DERIVED_MECHANISM
    club_good_mechanism: ClubGoodMechanism | None = None
    access_rule_description: str | None = None
    evidence_span_ids: list[str] = field(default_factory=list)
    allows_multiple_regimes: bool = True
    is_intrinsic_ontological_label: bool = False
    capacity_congestion_rule: str | None = None
    double_count_guard_group_id: str | None = None
    segregated_sensitivity_tier: str | None = None
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "regime_type", _coerce_enum(self.regime_type, GoodRegimeType))
        object.__setattr__(self, "rivalry", _coerce_enum(self.rivalry, RivalryLevel))
        object.__setattr__(self, "excludability", _coerce_enum(self.excludability, ExcludabilityLevel))
        object.__setattr__(self, "financing", _coerce_enum(self.financing, FinancingRuleType))
        object.__setattr__(self, "access", _coerce_enum(self.access, AccessRuleType))
        object.__setattr__(self, "exit_policy", _coerce_enum(self.exit_policy, ExitPolicyType))
        object.__setattr__(self, "eligibility_status", _coerce_enum(self.eligibility_status, ResourceEligibilityStatus))
        object.__setattr__(self, "provenance_category", _coerce_enum(self.provenance_category, ProvenanceCategory))
        self.validate()

    def validate(self) -> bool:
        if not self.regime_id or not self.regime_id.strip():
            raise ValueError("ResourceRegimeSpec requires non-empty regime_id.")
        if not self.subtopic_id or not self.subtopic_id.strip():
            raise ValueError("ResourceRegimeSpec requires non-empty subtopic_id.")
        if not self.question_id or not self.question_id.strip():
            raise ValueError("ResourceRegimeSpec requires non-empty question_id.")
        if self.eligibility_status in {ResourceEligibilityStatus.INELIGIBLE, ResourceEligibilityStatus.UNKNOWN}:
            raise ValueError(
                f"ResourceRegimeSpec {self.regime_id}: subtopic {self.subtopic_id} has "
                f"eligibility_status={self.eligibility_status.value} and cannot enter resource regime expansion."
            )
        if self.eligibility_status == ResourceEligibilityStatus.CONDITIONAL_RESOURCE_ONLY:
            if not (self.segregated_sensitivity_tier or "").strip():
                raise ValueError(
                    f"ResourceRegimeSpec {self.regime_id}: CONDITIONAL_RESOURCE_ONLY requires segregated_sensitivity_tier."
                )
        if self.is_intrinsic_ontological_label:
            raise ValueError(
                f"ResourceRegimeSpec {self.regime_id}: immutable intrinsic ontological good labeling is forbidden (ADR-0009 §3.1)."
            )
        if self.access == AccessRuleType.OTHER_EXPLICIT and not (self.access_rule_description or "").strip():
            raise ValueError(
                f"ResourceRegimeSpec {self.regime_id}: access=OTHER_EXPLICIT requires non-empty access_rule_description."
            )
        if self.regime_type == GoodRegimeType.CLUB_GOOD:
            if self.club_good_mechanism is None:
                raise ValueError(
                    f"ResourceRegimeSpec {self.regime_id}: CLUB_GOOD cannot be used as a bare label; "
                    "complete ClubGoodMechanism is mandatory (ADR-0009 §5 / VG-04)."
                )
            self.club_good_mechanism.validate()
            if self.excludability not in {ExcludabilityLevel.EXCLUDABLE, ExcludabilityLevel.PARTIALLY_EXCLUDABLE}:
                raise ValueError(
                    f"ResourceRegimeSpec {self.regime_id}: CLUB_GOOD requires EXCLUDABLE or PARTIALLY_EXCLUDABLE, "
                    f"got {self.excludability.value}."
                )
            if self.financing not in {FinancingRuleType.VOLUNTARY_MEMBER, FinancingRuleType.USAGE_BASED}:
                raise ValueError(
                    f"ResourceRegimeSpec {self.regime_id}: CLUB_GOOD requires VOLUNTARY_MEMBER or USAGE_BASED financing, "
                    f"got {self.financing.value}."
                )
            if self.exit_policy != self.club_good_mechanism.exit_rule:
                raise ValueError(
                    f"ResourceRegimeSpec {self.regime_id}: exit_policy ({self.exit_policy.value}) must match "
                    f"club_good_mechanism.exit_rule ({self.club_good_mechanism.exit_rule.value})."
                )
        elif self.regime_type == GoodRegimeType.PUBLIC_GOOD:
            if self.rivalry == RivalryLevel.RIVAL or self.excludability == ExcludabilityLevel.EXCLUDABLE:
                raise ValueError(
                    f"ResourceRegimeSpec {self.regime_id}: PUBLIC_GOOD cannot declare RIVAL or EXCLUDABLE."
                )
        elif self.regime_type == GoodRegimeType.PRIVATE_GOOD:
            if self.financing in {FinancingRuleType.COLLECTIVE, FinancingRuleType.INSTITUTIONAL}:
                raise ValueError(
                    f"ResourceRegimeSpec {self.regime_id}: PRIVATE_GOOD cannot declare compulsory {self.financing.value} financing."
                )
            if self.excludability == ExcludabilityLevel.NON_EXCLUDABLE:
                raise ValueError(
                    f"ResourceRegimeSpec {self.regime_id}: PRIVATE_GOOD cannot declare NON_EXCLUDABLE."
                )
        return True


def validate_provenance_boundary(
    *,
    provenance_category: ProvenanceCategory | str,
    target_regime_type: GoodRegimeType | str,
    is_refusal_to_pay_origin: bool = False,
    evidence_span_ids: list[str] | None = None,
    mechanism_rule_id: str | None = None,
    assumption_id: str | None = None,
) -> bool:
    """Enforce ADR-0009 §6.2: never convert refusal-to-pay into observed CLUB_GOOD preference."""
    prov_cat = _coerce_enum(provenance_category, ProvenanceCategory)
    regime = _coerce_enum(target_regime_type, GoodRegimeType)
    spans = list(evidence_span_ids or [])

    if prov_cat == ProvenanceCategory.OBSERVED_RESPONDENT_PREFERENCE:
        if is_refusal_to_pay_origin and regime == GoodRegimeType.CLUB_GOOD:
            raise ValueError(
                "Cannot reclassify opposition to compulsory payment / refusal-to-pay as "
                "OBSERVED_RESPONDENT_PREFERENCE for CLUB_GOOD without direct EvidenceSpan support (ADR-0009 §6.2)."
            )
        if not spans:
            raise ValueError(
                "OBSERVED_RESPONDENT_PREFERENCE requires explicit supporting evidence_span_ids."
            )
    elif prov_cat == ProvenanceCategory.INSTITUTIONALLY_DERIVED_MECHANISM:
        if not (mechanism_rule_id or "").strip():
            raise ValueError("INSTITUTIONALLY_DERIVED_MECHANISM requires explicit mechanism_rule_id.")
    elif prov_cat == ProvenanceCategory.COUNTERFACTUAL_PREFERENCE_ASSUMPTION:
        if not (assumption_id or "").strip():
            raise ValueError("COUNTERFACTUAL_PREFERENCE_ASSUMPTION requires explicit assumption_id.")
    return True


@dataclass(frozen=True)
class CounterfactualPreferenceMapping:
    """Typed record enforcing ADR-0009 §6 provenance segregation for preference vs assumption claims."""

    mapping_id: str
    participant_id: str
    question_id: str
    subtopic_id: str
    source_preference_key: str
    target_regime_type: GoodRegimeType
    provenance_category: ProvenanceCategory
    evidence_span_ids: list[str] = field(default_factory=list)
    mechanism_rule_id: str | None = None
    assumption_id: str | None = None
    is_refusal_to_pay_origin: bool = False
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "target_regime_type", _coerce_enum(self.target_regime_type, GoodRegimeType))
        object.__setattr__(self, "provenance_category", _coerce_enum(self.provenance_category, ProvenanceCategory))
        self.validate()

    def validate(self) -> bool:
        if not self.mapping_id or not self.participant_id or not self.question_id or not self.subtopic_id:
            raise ValueError("CounterfactualPreferenceMapping requires non-empty identity coordinates.")
        return validate_provenance_boundary(
            provenance_category=self.provenance_category,
            target_regime_type=self.target_regime_type,
            is_refusal_to_pay_origin=self.is_refusal_to_pay_origin,
            evidence_span_ids=self.evidence_span_ids,
            mechanism_rule_id=self.mechanism_rule_id,
            assumption_id=self.assumption_id,
        )


@dataclass(frozen=True)
class CounterfactualUtilityBound:
    """ADR-0009 §7 partially identified utility interval preventing ungrounded counterfactual point utilities."""

    bound_id: str
    participant_id: str
    solution_id: str
    subtopic_id: str
    identification_status: CounterfactualUtilityIdentification
    provenance_category: ProvenanceCategory
    utility_lower_bound: float | None
    utility_upper_bound: float | None
    point_utility: float | None = None
    scenario_utility_set: list[float] = field(default_factory=list)
    assumption_id: str | None = None
    mechanism_rule_id: str | None = None
    burden_removal_implication: str | None = None
    dominance_relation_note: str | None = None
    observed_direct_evidence_span_ids: list[str] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "identification_status",
            _coerce_enum(self.identification_status, CounterfactualUtilityIdentification),
        )
        object.__setattr__(
            self,
            "provenance_category",
            _coerce_enum(self.provenance_category, ProvenanceCategory),
        )
        self.validate()

    def validate(self) -> bool:
        if not self.bound_id or not self.participant_id or not self.solution_id or not self.subtopic_id:
            raise ValueError("CounterfactualUtilityBound requires non-empty identity fields.")
        if self.utility_lower_bound is not None and not (-1e-9 <= self.utility_lower_bound <= 1.0 + 1e-9):
            raise ValueError(f"CounterfactualUtilityBound {self.bound_id}: utility_lower_bound out of [0, 1].")
        if self.utility_upper_bound is not None and not (-1e-9 <= self.utility_upper_bound <= 1.0 + 1e-9):
            raise ValueError(f"CounterfactualUtilityBound {self.bound_id}: utility_upper_bound out of [0, 1].")
        if (
            self.utility_lower_bound is not None
            and self.utility_upper_bound is not None
            and self.utility_lower_bound > self.utility_upper_bound + 1e-9
        ):
            raise ValueError(
                f"CounterfactualUtilityBound {self.bound_id}: inverted interval "
                f"[{self.utility_lower_bound}, {self.utility_upper_bound}]."
            )
        if self.point_utility is not None:
            if self.identification_status != CounterfactualUtilityIdentification.POINT_IDENTIFIED:
                raise ValueError(
                    f"CounterfactualUtilityBound {self.bound_id}: cannot assign non-null point_utility when "
                    f"identification_status={self.identification_status.value} (ADR-0009 VG-06)."
                )
            if (
                self.provenance_category != ProvenanceCategory.OBSERVED_RESPONDENT_PREFERENCE
                or not self.observed_direct_evidence_span_ids
            ):
                raise ValueError(
                    f"CounterfactualUtilityBound {self.bound_id}: point_utility requires "
                    "OBSERVED_RESPONDENT_PREFERENCE and non-empty observed_direct_evidence_span_ids."
                )
        if self.identification_status == CounterfactualUtilityIdentification.POINT_IDENTIFIED and self.point_utility is None:
            raise ValueError(
                f"CounterfactualUtilityBound {self.bound_id}: POINT_IDENTIFIED requires point_utility."
            )
        if self.identification_status == CounterfactualUtilityIdentification.SCENARIO_IDENTIFIED:
            if (
                self.provenance_category != ProvenanceCategory.COUNTERFACTUAL_PREFERENCE_ASSUMPTION
                or not (self.assumption_id or "").strip()
                or not self.scenario_utility_set
            ):
                raise ValueError(
                    f"CounterfactualUtilityBound {self.bound_id}: SCENARIO_IDENTIFIED requires "
                    "COUNTERFACTUAL_PREFERENCE_ASSUMPTION, assumption_id, and scenario_utility_set."
                )
        if self.provenance_category == ProvenanceCategory.INSTITUTIONALLY_DERIVED_MECHANISM and not (
            self.mechanism_rule_id or ""
        ).strip():
            raise ValueError(
                f"CounterfactualUtilityBound {self.bound_id}: INSTITUTIONALLY_DERIVED_MECHANISM requires mechanism_rule_id."
            )
        return True


@dataclass(frozen=True)
class CounterfactualSolutionMetadata:
    """ADR-0009 §6.3 metadata required on every FRONTIER_B counterfactual GovernanceSolution."""

    solution_id: str
    frontier_namespace: FrontierNamespace = FrontierNamespace.FRONTIER_B
    solution_origin: Literal["COUNTERFACTUAL_INSTITUTIONAL_DESIGN"] = "COUNTERFACTUAL_INSTITUTIONAL_DESIGN"
    design_expansion_type: Literal["RESOURCE_REGIME_EXPANSION"] = "RESOURCE_REGIME_EXPANSION"
    parent_baseline_solution_id: str | None = None
    counterfactual_regime_specs: dict[str, ResourceRegimeSpec] = field(default_factory=dict)
    utility_provenance_breakdown: dict[str, list[str]] = field(default_factory=dict)
    segregated_sensitivity_tier: str | None = None
    double_count_guards_applied: list[str] = field(default_factory=list)
    pruning_sources_applied: list[str] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "frontier_namespace", _coerce_enum(self.frontier_namespace, FrontierNamespace))
        self.validate()

    def validate(self) -> bool:
        if not self.solution_id or not self.solution_id.strip():
            raise ValueError("CounterfactualSolutionMetadata requires non-empty solution_id.")
        if self.frontier_namespace != FrontierNamespace.FRONTIER_B:
            raise ValueError(
                f"CounterfactualSolutionMetadata {self.solution_id}: counterfactual solutions cannot enter "
                f"{FrontierNamespace.FRONTIER_A.value}; must target {FrontierNamespace.FRONTIER_B.value}."
            )
        if self.solution_origin != "COUNTERFACTUAL_INSTITUTIONAL_DESIGN":
            raise ValueError(
                f"CounterfactualSolutionMetadata {self.solution_id}: invalid solution_origin {self.solution_origin!r}."
            )
        if self.design_expansion_type != "RESOURCE_REGIME_EXPANSION":
            raise ValueError(
                f"CounterfactualSolutionMetadata {self.solution_id}: invalid design_expansion_type "
                f"{self.design_expansion_type!r}."
            )
        if not self.counterfactual_regime_specs:
            raise ValueError(
                f"CounterfactualSolutionMetadata {self.solution_id}: requires at least one ResourceRegimeSpec."
            )
        for subtopic_key, spec in self.counterfactual_regime_specs.items():
            if not isinstance(spec, ResourceRegimeSpec):
                raise ValueError(
                    f"CounterfactualSolutionMetadata {self.solution_id}: spec for '{subtopic_key}' must be ResourceRegimeSpec."
                )
            if spec.subtopic_id != subtopic_key:
                raise ValueError(
                    f"CounterfactualSolutionMetadata {self.solution_id}: key '{subtopic_key}' != spec.subtopic_id '{spec.subtopic_id}'."
                )
            spec.validate()
        prohibited = set(self.pruning_sources_applied) & COUNTERFACTUAL_PROHIBITED_PRUNING_SOURCES
        if prohibited:
            raise ValueError(
                f"CounterfactualSolutionMetadata {self.solution_id}: prohibited pruning source(s) {sorted(prohibited)} (ADR-0009 VG-07)."
            )
        return True


@dataclass(frozen=True)
class FrontierComparisonResult:
    """ADR-0009 §8–§9 dual-frontier comparison keeping OBSERVED_DESIGN_FRONTIER unmodified."""

    comparison_id: str
    run_id: str
    frontier_a_feasible_ids: list[str]
    frontier_b_feasible_ids: list[str]
    frontier_a_pareto_nondominated_ids: list[str]
    frontier_a_robust_status_counts: dict[str, int]
    frontier_b_robust_statuses: dict[str, CounterfactualParetoStatus]
    frontier_a_snapshot_hashes: dict[str, str]
    frontier_a_namespace: FrontierNamespace = FrontierNamespace.FRONTIER_A
    frontier_b_namespace: FrontierNamespace = FrontierNamespace.FRONTIER_B
    added_counterfactual_solution_ids: list[str] = field(default_factory=list)
    uncertainty_decomposition: dict[str, int | float] = field(default_factory=dict)
    answered_sensitivity_questions: list[str] = field(default_factory=list)
    pruned_by_prohibited_sources: bool = False
    provenance: ProvenanceMeta | None = None
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "frontier_a_namespace", _coerce_enum(self.frontier_a_namespace, FrontierNamespace))
        object.__setattr__(self, "frontier_b_namespace", _coerce_enum(self.frontier_b_namespace, FrontierNamespace))
        coerced_statuses = {
            sid: _coerce_enum(st, CounterfactualParetoStatus)
            for sid, st in self.frontier_b_robust_statuses.items()
        }
        object.__setattr__(self, "frontier_b_robust_statuses", coerced_statuses)
        self.validate()

    def validate(self) -> bool:
        if self.frontier_a_namespace != FrontierNamespace.FRONTIER_A:
            raise ValueError("FrontierComparisonResult frontier_a_namespace must remain OBSERVED_DESIGN_FRONTIER.")
        if self.frontier_b_namespace != FrontierNamespace.FRONTIER_B:
            raise ValueError("FrontierComparisonResult frontier_b_namespace must be RESOURCE_REGIME_EXPANDED_FRONTIER.")
        if self.pruned_by_prohibited_sources:
            raise ValueError("FrontierComparisonResult rejects cluster/value/goods/disagreement pruning (VG-07).")
        removed = sorted(set(self.frontier_a_feasible_ids) - set(self.frontier_b_feasible_ids))
        if removed:
            raise ValueError(
                f"FrontierComparisonResult {self.comparison_id}: FRONTIER_B removed existing FRONTIER_A solution(s): {removed[:5]}"
            )
        return True


ADR0009_SUPPORTING_CONTRACT_TYPES: dict[str, type] = {
    "ResourceEligibilityAssessment": ResourceEligibilityAssessment,
    "ClubGoodMechanism": ClubGoodMechanism,
    "ResourceRegimeSpec": ResourceRegimeSpec,
    "CounterfactualPreferenceMapping": CounterfactualPreferenceMapping,
    "CounterfactualUtilityBound": CounterfactualUtilityBound,
    "CounterfactualSolutionMetadata": CounterfactualSolutionMetadata,
    "FrontierComparisonResult": FrontierComparisonResult,
}


