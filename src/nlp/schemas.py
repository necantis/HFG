"""Structured output schemas for LLM qualitative coding and themes codebook.

Owned by: Agent 02 — Qualitative Coding
Schema Version: 1.0.0 / v1.1.0
Active Run: run_20261111_002

These Pydantic models define the structured JSON schemas used for:
1. Question-corpus open subtopic discovery (Phase 1) and chunk-and-consolidate metadata
2. Participant-level position/alternative assignment with strict metadata orthogonality (Phase 2)
3. Two-stage open organisational value discovery (Stage A free-form, Stage B consolidation proposal)
4. Selective subtopic-level economic goods assessment
5. Agent 01 normalized-response consumption with explicit response-status preservation
6. Probability repair audit records and SubtopicMatchProposal handoffs for Agent 03
7. Canonical Themes Codebook serialization (themes_codebook_v1)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Tuple
from pydantic import BaseModel, Field, field_validator, model_validator

from src.contracts import (
    AnalyticalFrameType,
    EconomicGoodClass,
    MissingnessState,
    SCHEMA_VERSION,
)


ResponseStatusLabel = Literal[
    "observed_substantive",
    "explicit_no_opinion",
    "insufficient_experience",
    "insufficient_information",
    "mixed_substantive_and_uncertainty",
    "missing_raw_blank",
    "missing_non_substantive",
]

ProbabilityInterpretation = Literal[
    "epistemic_uncertainty_over_preference",
    "explicit_mixed_preference",
    "conditional_or_context_dependent",
]


class NormalizedResponseInput(BaseModel):
    """Adapter consuming Agent 01's answers_normalized_v1 row and response-status fields.

    Uses canonical MissingnessState from src.contracts without inventing a competing enum.
    """

    response_id: str = Field(..., description="Stable normalized response ID from Agent 01.")
    participant_id: str = Field(..., description="Stable participant identifier.")
    question_id: str = Field(..., description="Survey question ID (Q01-Q14).")
    raw_value: Optional[str] = Field(default=None, description="Exact unmodified survey response text.")
    normalized_value: Optional[str] = Field(default=None, description="Normalized response text if provided.")
    response_type: Literal["categorical", "numeric", "open_text", "ranking"] = Field(default="open_text")
    detected_language: Literal["fr", "de", "en"] = Field(default="fr")
    missingness_state: MissingnessState = Field(default=MissingnessState.OBSERVED_USABLE)
    is_valid: bool = Field(default=True)
    validation_flags: List[str] = Field(default_factory=list)
    response_status: Optional[ResponseStatusLabel] = Field(
        default=None,
        description="Optional explicit epistemic/response-status label from Agent 01.",
    )


class CorpusChunkMetadata(BaseModel):
    """Explicit boundary record when a question corpus requires chunk-and-consolidate discovery."""

    chunk_index: int = Field(..., ge=0)
    total_chunks: int = Field(..., ge=1)
    start_item_index: int = Field(..., ge=0)
    end_item_index: int = Field(..., ge=0)
    participant_ids: List[str] = Field(default_factory=list)
    response_ids: List[str] = Field(default_factory=list)
    char_count: int = Field(default=0, ge=0)


class QuestionCorpusInput(BaseModel):
    """Complete question corpus passed identically to Coder A and Coder B for Phase 1 discovery."""

    question_id: str
    question_index: int
    canonical_prompt_en: str
    exact_question_wording: Dict[str, str] = Field(
        default_factory=dict,
        description="Exact question text keyed by language code (e.g. 'fr', 'de', 'en').",
    )
    analytical_frame: AnalyticalFrameType = Field(default=AnalyticalFrameType.GOVERNANCE_GOODS_ALLOCATION)
    economic_good_classification_policy: Literal["ENABLED", "CONDITIONAL", "DISABLED"] = Field(default="ENABLED")
    responses: List[NormalizedResponseInput] = Field(default_factory=list)
    source_evidence_hash: Optional[str] = Field(default=None)


class SubtopicGoodsAssessment(BaseModel):
    """Subtopic-level selective economic goods classification gated by actual evidence.

    Question-level analytical frames serve as guidance, never overriding concrete subtopic evidence.
    Imposes no 1D ordering across private_good, club_good, common_good, public_good.
    """

    goods_applicability: Literal["APPLICABLE", "NOT_APPLICABLE"] = Field(default="NOT_APPLICABLE")
    applicability_domain: Optional[
        Literal["allocation", "access", "ownership", "financing", "risk", "decision_rights"]
    ] = Field(
        default=None,
        description="Conceptual domain justifying economic goods classification when APPLICABLE.",
    )
    applicability_rationale: str = Field(
        default="",
        description="Evidence-based explanation for why goods taxonomy is or is not applicable to this subtopic.",
    )
    question_frame_override_applied: bool = Field(
        default=False,
        description="True when subtopic evidence overrides the default question-level goods policy.",
    )
    alternative_good_classes: Dict[str, str] = Field(
        default_factory=dict,
        description="Optional mapping from feasible alternative ID to EconomicGoodClass when APPLICABLE.",
    )
    imposes_linear_ordering: bool = Field(
        default=False,
        description="Must remain False: the 4 goods categories are not 1D ordered.",
    )

    @model_validator(mode="after")
    def validate_goods_invariants(self) -> SubtopicGoodsAssessment:
        if self.imposes_linear_ordering:
            raise ValueError("Economic goods taxonomy (private/club/common/public) must not impose a 1D ordering.")
        allowed = {e.value for e in EconomicGoodClass}
        cleaned: Dict[str, str] = {}
        for alt, cls_val in self.alternative_good_classes.items():
            if cls_val in allowed:
                cleaned[alt] = cls_val
            elif cls_val.lower() in allowed:
                cleaned[alt] = cls_val.lower()
            elif cls_val.upper() == "NOT_APPLICABLE":
                cleaned[alt] = "NOT_APPLICABLE"
            else:
                raise ValueError(f"Invalid economic good class '{cls_val}' for alternative '{alt}'.")
        self.alternative_good_classes = cleaned
        if self.goods_applicability == "APPLICABLE" and self.applicability_domain is None:
            raise ValueError(
                "SubtopicGoodsAssessment with goods_applicability='APPLICABLE' must specify an "
                "applicability_domain (allocation, access, ownership, financing, risk, or decision_rights)."
            )
        return self


class LLMDiscoveredAlternative(BaseModel):
    """A feasible institutional or analytical position/alternative discovered within a subtopic."""

    alternative_id: str = Field(..., description="Short snake_case identifier for this position/alternative.")
    label_en: str = Field(..., description="Clear English label for the alternative.")
    description: str = Field(default="", description="Specific description of this position.")
    economic_good_class: Optional[str] = Field(
        default=None,
        description="Optional Ostrom economic good class if this specific alternative concerns goods governance.",
    )


class LLMDiscoveredSubtopic(BaseModel):
    """A bottom-up subtopic discovered from the full question corpus (not just the question title)."""

    subtopic_key: str = Field(..., description="Coder-local unique snake_case identifier for this subtopic.")
    proposed_label_en: str = Field(..., description="Descriptive English label emerging from participant responses.")
    definition: str = Field(..., description="Substantive definition of the topic under discussion.")
    decision_object: str = Field(
        default="",
        description="The concrete entity, rule, resource, or governance issue being decided.",
    )
    mechanism: str = Field(
        default="",
        description="The operational, financial, or institutional mechanism discussed.",
    )
    scope: str = Field(
        default="",
        description="The organizational level or boundary scope (e.g., lab, pole, institute).",
    )
    discovered_alternatives: List[LLMDiscoveredAlternative] = Field(
        default_factory=list,
        description="Competing or distinct positions/alternatives expressed on this subtopic.",
    )
    goods_assessment: SubtopicGoodsAssessment = Field(default_factory=SubtopicGoodsAssessment)
    is_minority_position: bool = Field(
        default=False,
        description="True if raised by only one or a small minority of respondents; must still be preserved.",
    )
    supporting_response_ids: List[str] = Field(default_factory=list)
    supporting_participant_ids: List[str] = Field(default_factory=list)
    rationale: str = Field(default="")


class LLMCorpusDiscoveryResponse(BaseModel):
    """Structured output for Phase 1 full-question corpus subtopic discovery."""

    question_id: str
    discovered_subtopics: List[LLMDiscoveredSubtopic] = Field(default_factory=list)
    minority_positions_noted: List[str] = Field(default_factory=list)
    discovery_notes: Optional[str] = None


class DiscoveredQuestionTaxonomy(BaseModel):
    """Consolidated Phase 1 question taxonomy for one independent coder."""

    question_id: str
    coder_id: Literal["coder_a", "coder_b"]
    source_evidence_hash: str
    prompt_hash: str
    discovered_subtopics: List[LLMDiscoveredSubtopic] = Field(default_factory=list)
    chunked: bool = False
    chunk_boundaries: List[CorpusChunkMetadata] = Field(default_factory=list)
    total_llm_calls: int = Field(default=1, ge=1)
    minority_positions_preserved: List[str] = Field(default_factory=list)


class LLMEvidenceSpan(BaseModel):
    """A verbatim excerpt extracted from participant open-ended response text."""

    verbatim_quote: str = Field(
        ...,
        description="Exact verbatim excerpt from the participant response without modification.",
    )
    detected_language: Literal["fr", "de", "en"] = Field(
        default="fr",
        description="ISO 639-1 language code detected for this excerpt.",
    )
    language_confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence in language detection (0.0 to 1.0).",
    )
    char_start: Optional[int] = Field(
        default=None,
        description="0-indexed starting character offset in raw response string.",
    )
    char_end: Optional[int] = Field(
        default=None,
        description="0-indexed ending character offset in raw response string.",
    )
    sentence_index: Optional[int] = Field(
        default=None,
        description="0-indexed sentence index within the response.",
    )
    english_working_gloss: Optional[str] = Field(
        default=None,
        description="English translation or working gloss of non-English quotes.",
    )
    span_role: Literal[
        "substantive_evidence",
        "explicit_uncertainty_or_no_opinion",
        "value_evidence",
    ] = Field(
        default="substantive_evidence",
        description="Distinguishes substantive coding spans from explicit no-opinion/uncertainty spans.",
    )


class ProbabilityRepairRecord(BaseModel):
    """Audit record documenting any mechanical repair applied to an alternative probability distribution."""

    raw_values: Dict[str, float]
    repaired_values: Dict[str, float]
    repair_action: Literal[
        "none",
        "micro_drift_renormalization",
        "unambiguous_percentage_scaling",
    ]
    scale_detected: str
    reason: str


class LLMSubtopicCandidate(BaseModel):
    """A grounded subtopic candidate proposed by an LLM coder for a participant response."""

    subtopic_key: Optional[str] = Field(
        default=None,
        description="Key linking this participant assignment back to Phase 1 DiscoveredQuestionTaxonomy.",
    )
    proposed_label_en: str = Field(
        ...,
        description="Precise English label for the subtopic. Must emerge bottom-up from text; never simply restate question.",
    )
    proposed_description: str = Field(
        ...,
        description="Clear description of the subtopic and its specific institutional context.",
    )
    decision_object: str = Field(default="", description="Concrete decision object of this subtopic.")
    mechanism: str = Field(default="", description="Institutional/operational mechanism.")
    scope: str = Field(default="", description="Organizational scope.")
    native_language_keywords: List[str] = Field(
        default_factory=list,
        description="Key terms extracted from native language text supporting this subtopic.",
    )
    candidate_alternative_distribution: Dict[str, float] = Field(
        default_factory=dict,
        description="Probability distribution over feasible alternatives mentioned (must sum to 1.0 within 1e-4 for usable cells).",
    )
    raw_alternative_distribution: Optional[Dict[str, float]] = Field(
        default=None,
        description="Original un-repaired distribution emitted by the coder prior to validation.",
    )
    probability_repairs: List[ProbabilityRepairRecord] = Field(
        default_factory=list,
        description="Audit trail of any mechanical simplex repairs applied.",
    )
    probability_interpretation: ProbabilityInterpretation = Field(
        default="epistemic_uncertainty_over_preference",
        description=(
            "Explicit meaning of alternative_probabilities: epistemic uncertainty about respondent preference, "
            "explicitly expressed mixed preference, or conditional preference. NOT measured cardinal utility."
        ),
    )
    semantic_importance: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Orthogonal semantic importance/salience assigned by participant (0.0 to 1.0). Never derived from text length or conflated with probability.",
    )
    importance_rationale: Optional[str] = Field(
        default=None,
        description="Qualitative cue justifying semantic importance (never response length).",
    )
    coder_confidence: float = Field(
        default=0.9,
        ge=0.0,
        le=1.0,
        description="Epistemic confidence of the LLM coder in this extraction (0.0 to 1.0). Strictly distinct from coder_agreement.",
    )
    goods_assessment: Optional[SubtopicGoodsAssessment] = Field(
        default=None,
        description="Subtopic-level goods applicability assessment.",
    )
    proposed_economic_good_class: Optional[str] = Field(
        default=None,
        description="Economic good classification (private_good, club_good, common_good, public_good, NOT_APPLICABLE). Applied ONLY if conceptually justified at subtopic level.",
    )
    proposed_alternative_frame_label: Optional[str] = Field(
        default=None,
        description="Domain-appropriate diagnostic/perception category when economic goods classification is not applicable.",
    )
    derived_scalar_stance: Optional[float] = Field(
        default=None,
        ge=-1.0,
        le=1.0,
        description="Optional scalar stance only valid when alternatives have an analytically defensible ordering (never across the 4 goods types).",
    )
    evidence_quotes: List[str] = Field(
        default_factory=list,
        description="List of verbatim quotes supporting this subtopic.",
    )
    is_minority_position: bool = Field(default=False)

    @field_validator("proposed_economic_good_class")
    @classmethod
    def validate_good_class(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        allowed = {e.value for e in EconomicGoodClass}
        if v not in allowed:
            if v.lower() in allowed:
                return v.lower()
            if v.upper() == "NOT_APPLICABLE":
                return "NOT_APPLICABLE"
            raise ValueError(f"Invalid economic good class '{v}'. Allowed: {sorted(allowed)}")
        return v


class LLMValueExtraction(BaseModel):
    """Stage A free-form organisational value extracted independently by a coder from exact evidence.

    Open value discovery: NEVER restricted to a fixed enum of categories.
    """

    original_label: str = Field(
        default="",
        description="Free-form value label grounded in the respondent's wording/meaning (never forced into fixed categories).",
    )
    value_id: str = Field(
        default="",
        description="Slugified or example-linked value identifier (open-ended; unseen values permitted).",
    )
    value_label_en: str = Field(
        default="",
        description="Descriptive English name of the organisational value (defaults to original_label if omitted).",
    )
    value_definition: str = Field(
        default="",
        description="Definition of how this value operates in the respondent's institutional context.",
    )
    participant_id: str = Field(default="", description="Participant reference.")
    question_id: str = Field(default="", description="Question reference.")
    response_id: str = Field(default="", description="Normalized response ID reference.")
    polarity: Optional[float] = Field(
        default=None,
        ge=-1.0,
        le=1.0,
        description="Participant posture toward this value where meaningful in [-1.0, +1.0], or None if non-polar.",
    )
    semantic_importance: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Salience or emphasis of this value in the response (0.0 to 1.0). Distinct from polarity and probability.",
    )
    coder_confidence: float = Field(
        default=0.9,
        ge=0.0,
        le=1.0,
        description="Epistemic certainty of coder in this value assignment (0.0 to 1.0).",
    )
    polarity_uncertainty_interval: Optional[Tuple[float, float]] = Field(
        default=None,
        description="Optional 95% confidence bounds around the polarity estimate when polarity is meaningful.",
    )
    evidence_quotes: List[str] = Field(
        default_factory=list,
        description="Verbatim excerpts from the response evidencing this value commitment.",
    )
    evidence_span_ids: List[str] = Field(
        default_factory=list,
        description="Resolved EvidenceSpan IDs supporting this value.",
    )
    matched_example_alias: Optional[str] = Field(
        default=None,
        description="Optional non-binding alias if this free-form value resembles an illustrative example.",
    )

    @model_validator(mode="after")
    def sync_labels(self) -> LLMValueExtraction:
        if not self.original_label and self.value_label_en:
            self.original_label = self.value_label_en
        elif not self.value_label_en and self.original_label:
            self.value_label_en = self.original_label
        if not self.original_label and self.value_id:
            clean = self.value_id.replace("VAL_", "").replace("_", " ").title()
            self.original_label = clean
            self.value_label_en = clean
        if not self.original_label:
            raise ValueError("Free-form value extraction must supply original_label (or value_label_en / value_id).")
        if not self.value_id:
            slug = "".join(ch if ch.isalnum() else "_" for ch in self.original_label.upper()).strip("_")
            while "__" in slug:
                slug = slug.replace("__", "_")
            self.value_id = f"VAL_{slug[:48]}"
        return self


class ValueConsolidationProposal(BaseModel):
    """Stage B cross-question consolidation proposal preserving original labels and uncertainty.

    Final cross-coder reconciliation belongs to Agent 03.
    """

    proposal_id: str
    proposed_canonical_label: str
    proposed_definition: str
    original_labels: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Original Stage A labels with participant_id, question_id, coder_id, and value_assignment_id.",
    )
    supporting_evidence_ids: List[str] = Field(default_factory=list)
    supporting_question_ids: List[str] = Field(default_factory=list)
    supporting_participant_ids: List[str] = Field(default_factory=list)
    merge_rationale: str = Field(default="")
    uncertainty: Dict[str, Any] = Field(default_factory=dict)
    unresolved_alternatives: List[str] = Field(
        default_factory=list,
        description="Alternative groupings or borderline merges preserved open for Agent 03.",
    )
    requires_agent_03_reconciliation: bool = Field(default=True)


class SubtopicMatchProposal(BaseModel):
    """Structured semantic match evaluation between subtopics for Agent 03 adjudication."""

    match_id: str
    question_id: str
    candidate_a_id: str
    candidate_b_id: str
    label_a: str
    label_b: str
    lexical_retrieval_score: float = Field(ge=0.0, le=1.0)
    definition_similarity: float = Field(ge=0.0, le=1.0)
    evidence_overlap: float = Field(ge=0.0, le=1.0)
    decision_object_match: bool
    mechanism_match: bool
    scope_match: bool
    match_decision: Literal[
        "MATCH_SAME_TOPIC_SAME_POSITION",
        "MATCH_SAME_TOPIC_OPPOSING_ALTERNATIVES",
        "UNCERTAIN_FOR_AGENT_03",
        "NO_MATCH",
    ]
    rationale: str
    requires_agent_03_adjudication: bool = False


class LLMQuestionCodingResponse(BaseModel):
    """Complete structured response emitted by an LLM coder for a single participant answer to a question."""

    participant_id: str = Field(..., description="Unique participant identifier.")
    question_id: str = Field(..., description="Question identifier (Q01-Q14).")
    response_id: str = Field(default="", description="Stable normalized response ID.")
    is_substantive: bool = Field(
        default=True,
        description="True if response contains substantive or reportable epistemic content; False if blank or placeholder.",
    )
    missingness_state: str = Field(
        default=MissingnessState.OBSERVED_USABLE.value,
        description="Explicit missingness classification conforming to MissingnessState.",
    )
    response_status: ResponseStatusLabel = Field(
        default="observed_substantive",
        description="Explicit response-status preserving no-opinion, insufficient-experience/info, and mixed uncertainty.",
    )
    detected_language: Literal["fr", "de", "en"] = Field(
        default="fr",
        description="Overall detected language of the response.",
    )
    evidence_spans: List[LLMEvidenceSpan] = Field(
        default_factory=list,
        description="List of verbatim quotes extracted from the response.",
    )
    uncertainty_statements: List[LLMEvidenceSpan] = Field(
        default_factory=list,
        description="Verbatim epistemic uncertainty, no-opinion, or insufficient-information statements retained.",
    )
    subtopics: List[LLMSubtopicCandidate] = Field(
        default_factory=list,
        description="List of grounded subtopic candidates emerging from the response.",
    )
    values: List[LLMValueExtraction] = Field(
        default_factory=list,
        description="List of free-form organisational values expressed in the response.",
    )
    unmentioned_subtopic_keys: List[str] = Field(
        default_factory=list,
        description="Discovered question subtopics not mentioned by this respondent (not opposition or neutrality).",
    )
    coder_rationale: Optional[str] = Field(
        default=None,
        description="Brief reasoning chain explaining the coding decisions.",
    )

    @model_validator(mode="after")
    def validate_substantive_consistency(self) -> LLMQuestionCodingResponse:
        """Enforce response-status invariants:
        - Truly blank/placeholder missing responses receive zero coding.
        - Purely epistemic non-preference statuses (explicit_no_opinion, insufficient_experience,
          insufficient_information) retain verbatim evidence/uncertainty spans as reportable statements
          but MUST NOT emit fabricated preference distributions.
        """
        non_usable_states = {
            MissingnessState.MISSING_RAW_BLANK.value,
            MissingnessState.MISSING_NON_SUBSTANTIVE.value,
            MissingnessState.UNOBSERVED_MISSING.value,
        }
        if (
            not self.is_substantive
            or self.missingness_state in non_usable_states
            or self.response_status in {"missing_raw_blank", "missing_non_substantive"}
        ):
            self.evidence_spans = []
            self.uncertainty_statements = []
            self.subtopics = []
            self.values = []
            return self

        if self.response_status in {
            "explicit_no_opinion",
            "insufficient_experience",
            "insufficient_information",
        }:
            # Reportable observed statement: preserve spans/uncertainty, reject fabricated preferences
            for st in self.subtopics:
                if st.candidate_alternative_distribution:
                    raise ValueError(
                        f"Response status '{self.response_status}' for {self.participant_id}/{self.question_id} "
                        "must not fabricate alternative preference probabilities."
                    )
            return self

        return self


class ThemeRecord(BaseModel):
    """Canonical qualitative theme record in themes_codebook.json."""

    theme_id: str = Field(..., description="Unique theme identifier (e.g., TH_Q01_01).")
    question_id: str = Field(..., description="Survey question ID this theme belongs to.")
    name: str = Field(..., description="Informative title of the qualitative theme.")
    description: str = Field(..., description="Detailed description of the theme.")
    keywords: List[str] = Field(default_factory=list, description="Associated keywords in native languages.")
    evidence_response_ids: List[str] = Field(
        default_factory=list,
        description="List of normalized response IDs grounding this theme in answers_normalized.parquet.",
    )
    support_count: int = Field(default=0, ge=0, description="Number of participants supporting this theme.")


class ThemesCodebook(BaseModel):
    """Canonical qualitative themes codebook conforming to themes_codebook_v1 contract.

    Canonical location: data/processed/themes_codebook.json
    Authority: canonical_intermediate
    """

    schema_version: str = Field(default="v1.1.0", description="Contract schema version.")
    run_id: str = Field(default="run_20261111_002", description="Active run identifier.")
    generated_at_utc: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of creation.",
    )
    themes: List[ThemeRecord] = Field(
        default_factory=list,
        description="Synthesized qualitative themes across all survey questions.",
    )
    canonical_subtopics: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of CanonicalSubtopic records conforming to CanonicalSubtopic contract.",
    )
    value_assignments: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of ValueAssignment records conforming to ValueAssignment contract.",
    )
    discovered_taxonomies: Dict[str, Any] = Field(
        default_factory=dict,
        description="Per-question Phase 1 DiscoveredQuestionTaxonomy records by coder.",
    )
    value_stage_a_extractions: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Stage A free-form value extractions preserving original labels.",
    )
    value_stage_b_proposals: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Stage B cross-question value consolidation proposals for Agent 03.",
    )
    subtopic_match_proposals: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Structured subtopic match evaluations including uncertain matches for Agent 03.",
    )
    response_status_summary: Dict[str, Any] = Field(
        default_factory=dict,
        description="Counts of substantive, explicit no-opinion, insufficient experience/info, mixed, and missing answers.",
    )
    probability_repairs: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Audit log of every mechanical probability repair performed.",
    )
    methodological_flags: Dict[str, Any] = Field(
        default_factory=lambda: {
            "alternative_probabilities_meaning": (
                "Represents epistemic coding uncertainty over respondent preference, explicitly expressed mixed "
                "preference, or conditional preference—NOT measured cardinal utility. Flagged for Agent 04 and Architecture Reviewer."
            ),
            "value_reconciliation_pending_agent_03": True,
            "uncertain_subtopic_matches_pending_agent_03": True,
        },
        description="Methodological flags forwarded to Agent 03, Agent 04, and Agent 09.",
    )
    provenance: Dict[str, Any] = Field(
        default_factory=dict,
        description="Provenance metadata including separate source_evidence_hash and coder prompt hashes.",
    )
