"""Comprehensive test suite for NLP and Qualitative Coding package (Agent 02).

Owned by: Agent 02 — Qualitative Coding
Schema Version: 1.0.0 / v1.1.0
Active Run: run_20261111_002

Covers all methodological requirements:
1. Unseen free-form values accepted (not restricted to fixed 7 categories)
2. Original value labels preserved
3. Stage B semantic consolidation with uncertainty & unresolved alternatives for Agent 03
4. Value polarity separate from semantic importance (and never using text length as importance)
5. Full-question corpus discovery (exact wording, all responses, stable IDs, response status)
6. Multiple evidence-grounded subtopics per question
7. Minority positions preserved (including across chunked discovery)
8. Same topic with opposing alternatives separated cleanly from duplicates/splits
9. Low lexical overlap with semantic equivalence (never Jaccard alone)
10. Subtopic-level goods applicability (perception->allocation & allocation->perception overrides, no 1D order)
11. Explicit no opinion / insufficient experience / insufficient info without fabricated preference
12. Mixed uncertainty and substantive preference
13. Missing answers without coding
14. No silent truncation (documented chunk-and-consolidate)
15. Invalid probability repair rejected; valid repairs audited; repeated quotes require disambiguation
16. Independent coder inputs (separate source_evidence_hash vs. prompt hashes, isolation checks)
"""

import json
import math
import pytest

from src.contracts import (
    AnalyticalFrameType,
    EconomicGoodClass,
    MissingnessState,
    ProvenanceMeta,
    SubtopicCandidate,
)
from src.nlp.fixtures import (
    get_multilingual_test_fixtures,
    get_sample_question_specs,
)
from src.nlp.matching import SubtopicDescriptor, SubtopicMatcher
from src.nlp.prompts import (
    PromptBuilder,
    SYSTEM_PROMPT_QUALITATIVE_CODER,
    assert_coder_input_isolation,
    compute_prompt_hash,
    compute_source_evidence_hash,
)
from src.nlp.repair import (
    AmbiguousQuoteOffsetError,
    classify_response_status,
    enforce_economic_goods_policy,
    find_exact_char_offsets,
    is_non_substantive_response,
    repair_json_string,
    repair_json_string_with_audit,
    validate_and_repair_probabilities,
    validate_and_repair_simplex,
)
from src.nlp.schemas import (
    LLMCorpusDiscoveryResponse,
    LLMDiscoveredAlternative,
    LLMDiscoveredSubtopic,
    LLMEvidenceSpan,
    LLMQuestionCodingResponse,
    LLMSubtopicCandidate,
    LLMValueExtraction,
    NormalizedResponseInput,
    QuestionCorpusInput,
    ResponseStatusLabel,
    SubtopicGoodsAssessment,
    ThemeRecord,
    ThemesCodebook,
)
from src.nlp.subtopic_extraction import (
    CanonicalSubtopicSynthesizer,
    DualCoderRunner,
    EvidenceSpanExtractor,
    QuestionCorpusCoder,
    QuestionCorpusDiscoveryEngine,
    SubtopicExtractor,
)
from src.nlp.value_extraction import (
    CANONICAL_ORGANISATIONAL_VALUES,
    EXAMPLE_ORGANISATIONAL_VALUE_ALIASES,
    ValueExtractor,
)


# ---------------------------------------------------------------------------
# 1-4. Open Value Discovery, Original Labels, Consolidation & Distinct Quantities
# ---------------------------------------------------------------------------
def test_unseen_values_accepted_and_original_labels_preserved():
    extractor = ValueExtractor(run_id="run_20261111_002")

    # Unseen values NOT in EXAMPLE_ORGANISATIONAL_VALUE_ALIASES must be accepted without coercion
    unseen_a = extractor.extract_stage_a_value(
        participant_id="P01",
        question_id="Q08",
        raw_value={
            "original_label": "Intergenerational Mentoring Continuity",
            "value_definition": "Protecting long-term knowledge transfer from senior PIs to postdocs.",
            "polarity": 0.9,
            "semantic_importance": 0.85,
            "coder_confidence": 0.92,
            "evidence_quotes": ["protect mentoring continuity"],
        },
        supporting_span_ids=["SPAN_01"],
        coder_id="coder_a",
    )
    assert unseen_a.original_label == "Intergenerational Mentoring Continuity"
    assert unseen_a.value_label_en == "Intergenerational Mentoring Continuity"
    assert unseen_a.matched_example_alias is None
    assert unseen_a.value_id not in EXAMPLE_ORGANISATIONAL_VALUE_ALIASES

    # ValueAssignment also preserves the original label without forcing into 7 categories
    va = extractor.create_value_assignment(
        participant_id="P01",
        question_id="Q08",
        subtopic_id="SUB_Q08_01",
        raw_value=unseen_a,
        supporting_span_ids=["SPAN_01"],
        coder_id="coder_a",
    )
    assert va.value_label_en == "Intergenerational Mentoring Continuity"
    assert va.coder_a_raw_label == "Intergenerational Mentoring Continuity"
    assert va.value_id not in EXAMPLE_ORGANISATIONAL_VALUE_ALIASES


def test_stage_b_value_semantic_consolidation_preserves_originals_and_uncertainty():
    extractor = ValueExtractor(run_id="run_20261111_002")

    v1 = extractor.extract_stage_a_value(
        participant_id="P01",
        question_id="Q04",
        raw_value={
            "original_label": "Mentoring Continuity",
            "value_definition": "Maintaining senior-junior research mentoring continuity across labs.",
            "polarity": 1.0,
            "semantic_importance": 0.9,
            "coder_confidence": 0.88,
        },
        supporting_span_ids=["SPAN_Q04_01"],
    )
    v2 = extractor.extract_stage_a_value(
        participant_id="P02",
        question_id="Q14",
        raw_value={
            "original_label": "Research Mentoring Continuity",
            "value_definition": "Sustaining senior-junior research mentoring continuity across poles.",
            "polarity": None,  # Non-polar descriptive value
            "semantic_importance": 0.7,
            "coder_confidence": 0.80,
        },
        supporting_span_ids=["SPAN_Q14_02"],
    )
    v3 = extractor.extract_stage_a_value(
        participant_id="P03",
        question_id="Q11",
        raw_value={
            "original_label": "Disciplinary Epistemic Pluralism",
            "value_definition": "Avoiding single-metric bias across humanities and engineering.",
            "polarity": 0.95,
            "semantic_importance": 0.95,
            "coder_confidence": 0.91,
        },
        supporting_span_ids=["SPAN_Q11_03"],
    )

    proposals = extractor.propose_cross_question_consolidation([v1, v2, v3])
    assert len(proposals) == 2

    mentoring_prop = next(p for p in proposals if "Mentoring" in p.proposed_canonical_label)
    assert set(mentoring_prop.supporting_question_ids) == {"Q04", "Q14"}
    assert set(mentoring_prop.supporting_evidence_ids) == {"SPAN_Q04_01", "SPAN_Q14_02"}
    orig_lbls = {entry["original_label"] for entry in mentoring_prop.original_labels}
    assert orig_lbls == {"Mentoring Continuity", "Research Mentoring Continuity"}
    assert mentoring_prop.requires_agent_03_reconciliation is True
    assert "min_coder_confidence" in mentoring_prop.uncertainty
    assert len(mentoring_prop.unresolved_alternatives) == 1


def test_polarity_separate_from_importance_and_not_derived_from_length():
    extractor = ValueExtractor(run_id="run_20261111_002")

    # Negative polarity (-0.9: strongly opposing centralization) can still have HIGH semantic importance (0.95)!
    val = extractor.extract_stage_a_value(
        participant_id="P01",
        question_id="Q08",
        raw_value={
            "original_label": "Top-Down Bureaucratic Control",
            "value_definition": "Centralized administrative control over hiring.",
            "polarity": -0.9,
            "semantic_importance": 0.95,
            "coder_confidence": 0.92,
        },
        supporting_span_ids=["SPAN_01"],
    )
    assert val.polarity == pytest.approx(-0.9)
    assert val.semantic_importance == pytest.approx(0.95)
    assert val.polarity != val.semantic_importance

    # Non-polar value allows polarity=None
    non_polar = extractor.extract_stage_a_value(
        participant_id="P02",
        question_id="Q01",
        raw_value={
            "original_label": "Institutional Clarity",
            "value_definition": "Descriptive reference to clear structural definitions.",
            "polarity": None,
            "semantic_importance": 0.65,
            "coder_confidence": 0.85,
        },
        supporting_span_ids=["SPAN_02"],
    )
    assert non_polar.polarity is None

    # Semantic importance is NOT derived from response length: short sharp text can have 0.95 importance
    sub_ext = SubtopicExtractor(coder_id="coder_a")
    short_sharp_text = "Non, gardez les RH au labo!"
    long_rambling_text = (
        "Eh bien, je travaille ici depuis quelque temps et j'ai vu plusieurs réunions passées, "
        "mais en fait sur ce point précis je dirais simplement qu'une petite coordination peut être utile."
    )
    _, cands_short, _ = sub_ext.process_response(
        participant_id="P_SHORT",
        question_id="Q08",
        question_index=8,
        canonical_prompt_en="HR level",
        raw_response=short_sharp_text,
        preparsed_output={
            "participant_id": "P_SHORT",
            "question_id": "Q08",
            "is_substantive": True,
            "evidence_spans": [{"verbatim_quote": "gardez les RH au labo!"}],
            "subtopics": [
                {
                    "proposed_label_en": "Lab Hiring Control",
                    "proposed_description": "Hiring remains at lab.",
                    "candidate_alternative_distribution": {"laboratory": 1.0},
                    "semantic_importance": 0.95,
                    "coder_confidence": 0.90,
                    "probability_interpretation": "epistemic_uncertainty_over_preference",
                }
            ],
        },
    )
    _, cands_long, _ = sub_ext.process_response(
        participant_id="P_LONG",
        question_id="Q08",
        question_index=8,
        canonical_prompt_en="HR level",
        raw_response=long_rambling_text,
        preparsed_output={
            "participant_id": "P_LONG",
            "question_id": "Q08",
            "is_substantive": True,
            "evidence_spans": [{"verbatim_quote": "une petite coordination peut être utile"}],
            "subtopics": [
                {
                    "proposed_label_en": "Light Coordination",
                    "proposed_description": "Mild coordination.",
                    "candidate_alternative_distribution": {"light_coord": 1.0},
                    "semantic_importance": 0.30,
                    "coder_confidence": 0.85,
                }
            ],
        },
    )
    assert cands_short[0].semantic_importance > cands_long[0].semantic_importance


# ---------------------------------------------------------------------------
# 5-7 & 14 & 16. Full-Question Corpus Discovery, Minority Positions, No Silent Truncation, Two-Coder Independence
# ---------------------------------------------------------------------------
def _build_sample_corpus() -> QuestionCorpusInput:
    return QuestionCorpusInput(
        question_id="Q11",
        question_index=11,
        canonical_prompt_en="How should grant overheads and indirect costs be managed and distributed?",
        exact_question_wording={
            "fr": "11. Comment les overheads doivent-ils être gérés ?",
            "de": "11. Wie sollen Overheads verwaltet werden?",
        },
        analytical_frame=AnalyticalFrameType.GOVERNANCE_GOODS_ALLOCATION,
        economic_good_classification_policy="ENABLED",
        responses=[
            NormalizedResponseInput(
                response_id="R_01",
                participant_id="P_01",
                question_id="Q11",
                raw_value="Les overheads doivent revenir au laboratoire porteur à 60% et au pôle à 40%.",
                detected_language="fr",
                missingness_state=MissingnessState.OBSERVED_USABLE,
                response_status="observed_substantive",
            ),
            NormalizedResponseInput(
                response_id="R_02",
                participant_id="P_02",
                question_id="Q11",
                raw_value="Overheads should fund shared technical staff across the pole, not individual labs.",
                detected_language="en",
                missingness_state=MissingnessState.OBSERVED_USABLE,
                response_status="observed_substantive",
            ),
            NormalizedResponseInput(
                response_id="R_03",
                participant_id="P_03",
                question_id="Q11",
                raw_value="Unique minority concern: create an emergency equipment repair reserve from 5% of overheads.",
                detected_language="en",
                missingness_state=MissingnessState.OBSERVED_USABLE,
                response_status="observed_substantive",
            ),
            NormalizedResponseInput(
                response_id="R_04",
                participant_id="P_04",
                question_id="Q11",
                raw_value="Pas d'avis sur ce point.",
                detected_language="fr",
                missingness_state=MissingnessState.OBSERVED_USABLE,
                response_status="explicit_no_opinion",
            ),
            NormalizedResponseInput(
                response_id="R_05",
                participant_id="P_05",
                question_id="Q11",
                raw_value="   ",
                detected_language="fr",
                missingness_state=MissingnessState.MISSING_RAW_BLANK,
                response_status="missing_raw_blank",
            ),
        ],
    )


def test_full_question_corpus_discovery_multiple_subtopics_and_minority_preserved():
    corpus = _build_sample_corpus()
    engine = QuestionCorpusDiscoveryEngine(coder_id="coder_a")

    captured_prompts = []

    def mock_discovery(sys_p: str, usr_p: str) -> dict:
        captured_prompts.append(usr_p)
        # Verify complete corpus wording, all IDs, and response statuses were included
        assert "11. Comment les overheads doivent-ils être gérés ?" in usr_p
        assert "R_01" in usr_p and "P_01" in usr_p
        assert "R_02" in usr_p and "P_02" in usr_p
        assert "R_03" in usr_p and "P_03" in usr_p
        assert "explicit_no_opinion" in usr_p
        assert "missing_raw_blank" in usr_p

        return {
            "question_id": "Q11",
            "discovered_subtopics": [
                {
                    "subtopic_key": "overhead_sharing_split",
                    "proposed_label_en": "Overhead Revenue Split Between Labs and Pole",
                    "definition": "Allocation ratio between grant-winning laboratories and collective pole pools.",
                    "decision_object": "overhead_revenue_split",
                    "mechanism": "percentage_formula",
                    "scope": "lab_vs_pole",
                    "discovered_alternatives": [
                        {"alternative_id": "lab_majority_60_40", "label_en": "60% Lab / 40% Pole"},
                        {"alternative_id": "collective_pole_pool", "label_en": "Collective Pole Technical Pool"},
                    ],
                    "goods_assessment": {
                        "goods_applicability": "APPLICABLE",
                        "applicability_domain": "financing",
                        "applicability_rationale": "Direct distribution of grant overhead financing.",
                        "alternative_good_classes": {
                            "lab_majority_60_40": "private_good",
                            "collective_pole_pool": "club_good",
                        },
                    },
                    "is_minority_position": False,
                    "supporting_response_ids": ["R_01", "R_02"],
                    "supporting_participant_ids": ["P_01", "P_02"],
                },
                {
                    "subtopic_key": "emergency_repair_reserve",
                    "proposed_label_en": "Emergency Equipment Repair Reserve",
                    "definition": "Dedicated 5% overhead carve-out for urgent shared equipment repairs.",
                    "decision_object": "equipment_repair_contingency",
                    "mechanism": "reserve_carveout",
                    "scope": "pole_equipment",
                    "discovered_alternatives": [
                        {"alternative_id": "five_percent_reserve", "label_en": "5% Emergency Repair Reserve"},
                    ],
                    "goods_assessment": {
                        "goods_applicability": "APPLICABLE",
                        "applicability_domain": "risk",
                        "applicability_rationale": "Risk pooling for unexpected instrument breakdown.",
                    },
                    "is_minority_position": True,
                    "supporting_response_ids": ["R_03"],
                    "supporting_participant_ids": ["P_03"],
                },
            ],
            "minority_positions_noted": ["Emergency Equipment Repair Reserve (P_03)"],
        }

    taxonomy = engine.discover_question_taxonomy(corpus, discovery_callable=mock_discovery)
    assert len(captured_prompts) == 1
    assert taxonomy.chunked is False
    assert len(taxonomy.discovered_subtopics) == 2
    assert "emergency_repair_reserve" in taxonomy.minority_positions_preserved


def test_chunk_and_consolidate_no_silent_truncation_and_minority_preserved():
    # Build 6 responses and force chunking with max_responses_per_chunk=2
    responses = [
        NormalizedResponseInput(
            response_id=f"R_{i:02d}",
            participant_id=f"P_{i:02d}",
            question_id="Q11",
            raw_value=f"Participant {i} substantive view on overhead distribution option {i}.",
            detected_language="en",
            missingness_state=MissingnessState.OBSERVED_USABLE,
            response_status="observed_substantive",
        )
        for i in range(1, 7)
    ]
    corpus = QuestionCorpusInput(
        question_id="Q11",
        question_index=11,
        canonical_prompt_en="Overhead allocation",
        exact_question_wording={"en": "How should overheads be distributed?"},
        responses=responses,
    )

    engine = QuestionCorpusDiscoveryEngine(
        coder_id="coder_a",
        max_corpus_chars=50000,
        max_responses_per_chunk=2,  # forces 3 chunks + 1 consolidation = 4 calls (not capped at 1)
    )

    seen_response_ids = []

    def chunk_discovery_fn(sys_p: str, usr_p: str) -> dict:
        for i in range(1, 7):
            rid = f"R_{i:02d}"
            if rid in usr_p:
                seen_response_ids.append(rid)

        if "R_05" in usr_p:
            # Chunk 3 contains minority position R_06
            return {
                "question_id": "Q11",
                "discovered_subtopics": [
                    {
                        "subtopic_key": "minority_reserve_r06",
                        "proposed_label_en": "Minority Reserve Fund",
                        "definition": "Single-respondent proposal for strategic reserve.",
                        "decision_object": "strategic_reserve",
                        "mechanism": "earmark",
                        "scope": "institute",
                        "discovered_alternatives": [{"alternative_id": "reserve", "label_en": "Reserve"}],
                        "is_minority_position": True,
                        "supporting_response_ids": ["R_06"],
                        "supporting_participant_ids": ["P_06"],
                    }
                ],
            }
        return {
            "question_id": "Q11",
            "discovered_subtopics": [
                {
                    "subtopic_key": "overhead_split",
                    "proposed_label_en": "Overhead Allocation Split",
                    "definition": "Split between labs and center.",
                    "decision_object": "overhead_split",
                    "mechanism": "formula",
                    "scope": "lab_pole",
                    "discovered_alternatives": [{"alternative_id": "lab_share", "label_en": "Lab Share"}],
                    "is_minority_position": False,
                    "supporting_response_ids": ["R_01"],
                    "supporting_participant_ids": ["P_01"],
                }
            ],
        }

    # Even if consolidation mock accidentally omits the minority position, engine guarantees preservation!
    def buggy_consolidation_fn(sys_p: str, usr_p: str) -> dict:
        return {
            "question_id": "Q11",
            "discovered_subtopics": [
                {
                    "subtopic_key": "overhead_split",
                    "proposed_label_en": "Overhead Allocation Split",
                    "definition": "Split between labs and center.",
                    "decision_object": "overhead_split",
                    "mechanism": "formula",
                    "scope": "lab_pole",
                    "discovered_alternatives": [{"alternative_id": "lab_share", "label_en": "Lab Share"}],
                    "is_minority_position": False,
                    "supporting_response_ids": ["R_01"],
                    "supporting_participant_ids": ["P_01"],
                }
            ],
        }

    taxonomy = engine.discover_question_taxonomy(
        corpus,
        discovery_callable=chunk_discovery_fn,
        consolidation_callable=buggy_consolidation_fn,
    )

    assert taxonomy.chunked is True
    assert len(taxonomy.chunk_boundaries) == 3
    assert taxonomy.total_llm_calls == 4  # 3 chunks + 1 consolidation (no fixed cap)
    # Zero silent truncation: every single response R_01..R_06 was passed in full
    assert sorted(seen_response_ids) == ["R_01", "R_02", "R_03", "R_04", "R_05", "R_06"]
    # Minority position preserved
    keys = {st.subtopic_key for st in taxonomy.discovered_subtopics}
    assert "minority_reserve_r06" in keys
    assert "minority_reserve_r06" in taxonomy.minority_positions_preserved


def test_independent_coder_inputs_and_hash_separation():
    corpus = _build_sample_corpus()
    source_hash = compute_source_evidence_hash(corpus)

    pb_a = PromptBuilder(coder_id="coder_a", model_adapter_tag="model_family_alpha")
    pb_b = PromptBuilder(coder_id="coder_b", model_adapter_tag="model_family_beta")

    prompt_a, p_hash_a, src_hash_a = pb_a.build_corpus_discovery_prompt(corpus)
    prompt_b, p_hash_b, src_hash_b = pb_b.build_corpus_discovery_prompt(corpus)

    # Coder A and Coder B receive identical source evidence
    assert src_hash_a == src_hash_b == source_hash
    # Model-specific prompt hashes are stored separately from source_evidence_hash
    assert p_hash_a != source_hash
    assert p_hash_b != source_hash
    assert p_hash_a != p_hash_b

    # Isolation checks forbid peer coder references or downstream leakage
    with pytest.raises(ValueError, match="Isolation Violation"):
        assert_coder_input_isolation('Here is what "coder_b" concluded earlier.', "coder_a")

    with pytest.raises(ValueError, match="Isolation Violation"):
        assert_coder_input_isolation("The Pareto frontier favored Package A.", "coder_a")


# ---------------------------------------------------------------------------
# 8 & 9. Subtopic Matching: Topic vs Opposing Alternatives & Low Lexical Overlap
# ---------------------------------------------------------------------------
def test_same_topic_with_opposing_alternatives():
    matcher = SubtopicMatcher()

    d1 = SubtopicDescriptor(
        item_id="C1",
        question_id="Q09",
        label="Individual Laboratory Deficit Responsibility",
        definition="Financial liability for laboratory budget deficits assigned individually to the lab.",
        decision_object="deficit financial responsibility",
        mechanism="cost liability rule",
        scope="laboratory vs pole",
        alternatives=["individual_lab_liability"],
        evidence_ids=["SPAN_1"],
    )
    d2 = SubtopicDescriptor(
        item_id="C2",
        question_id="Q09",
        label="Collective Pole Solidarity for Deficits",
        definition="Financial liability for laboratory budget deficits mutualized collectively across the pole.",
        decision_object="deficit financial responsibility",
        mechanism="cost liability rule",
        scope="laboratory vs pole",
        alternatives=["collective_pole_solidarity"],
        evidence_ids=["SPAN_2"],
    )

    prop = matcher.evaluate_pair(d1, d2)
    assert prop.decision_object_match is True
    assert prop.mechanism_match is True
    assert prop.scope_match is True
    assert prop.match_decision == "MATCH_SAME_TOPIC_OPPOSING_ALTERNATIVES"

    # When clustered, they form ONE topic containing BOTH opposing alternatives!
    groups, _ = matcher.cluster_subtopics([d1, d2])
    assert len(groups) == 1
    combined_alts = {alt for d in groups[0] for alt in d.alternatives}
    assert combined_alts == {"individual_lab_liability", "collective_pole_solidarity"}


def test_low_lexical_overlap_with_semantic_equivalence_and_uncertain_match_preserved():
    matcher = SubtopicMatcher()

    # Low surface word overlap in labels ("HR Hiring Rights" vs "Dezentrale Personalhoheit")
    # yet aligned decision_object, mechanism, and scope via multilingual semantic concepts
    d_en = SubtopicDescriptor(
        item_id="C_EN",
        question_id="Q08",
        label="Lab Staffing Mandate",
        definition="Authority over hiring decisions rests with research units.",
        decision_object="hr recruitment decision rights",
        mechanism="decentralized hiring governance",
        scope="laboratory level",
        alternatives=["laboratory_level"],
    )
    d_de = SubtopicDescriptor(
        item_id="C_DE",
        question_id="Q08",
        label="Dezentrale Personalhoheit der Gruppen",
        definition="Personalentscheidungen und Stellenbesetzungen bei Forschungsgruppen.",
        decision_object="personal stellenbesetzungen decision authority",
        mechanism="dezentral personal governance",
        scope="forschungsgruppen level",
        alternatives=["laboratory_level"],
    )

    lex_score = matcher.compute_lexical_retrieval_score(d_en, d_de)
    assert lex_score < 0.25  # Low surface lexical overlap

    prop = matcher.evaluate_pair(d_en, d_de, lexical_retrieval_score=lex_score)
    assert prop.decision_object_match is True
    assert prop.mechanism_match is True
    assert prop.scope_match is True
    assert prop.match_decision == "MATCH_SAME_TOPIC_SAME_POSITION"

    # Borderline / partial alignment -> preserved as UNCERTAIN_FOR_AGENT_03 (never auto-merged)
    d_ambig_a = SubtopicDescriptor(
        item_id="C_AMB_A",
        question_id="Q08",
        label="Pole HR Coordination",
        definition="Administrative support for hiring workflows.",
        decision_object="hr workflow support",
        mechanism="administrative support",
        scope="pole",
        alternatives=["pole_support"],
    )
    d_ambig_b = SubtopicDescriptor(
        item_id="C_AMB_B",
        question_id="Q08",
        label="Pole Strategic Steering",
        definition="Strategic direction of scientific hiring priorities.",
        decision_object="scientific hiring priorities",
        mechanism="strategic prioritization",
        scope="pole",
        alternatives=["pole_strategy"],
    )
    prop_unc = matcher.evaluate_pair(d_ambig_a, d_ambig_b)
    assert prop_unc.match_decision == "UNCERTAIN_FOR_AGENT_03"
    assert prop_unc.requires_agent_03_adjudication is True
    groups, _ = matcher.cluster_subtopics([d_ambig_a, d_ambig_b])
    assert len(groups) == 2  # Not auto-merged!


# ---------------------------------------------------------------------------
# 10. Subtopic-Level Selective Goods Applicability & No 1D Ordering
# ---------------------------------------------------------------------------
def test_subtopic_level_goods_applicability_overrides_question_prior_and_no_1d_order():
    # Case A: Perception question (policy=DISABLED) containing an allocation-related answer
    perception_with_alloc = [
        {
            "proposed_label_en": "Shared Core Equipment Access Rules",
            "proposed_description": "Participant answers Q01 by specifying club-good access rules for shared pole instruments.",
            "proposed_economic_good_class": "club_good",
            "goods_assessment": {
                "goods_applicability": "APPLICABLE",
                "applicability_domain": "access",
                "applicability_rationale": "Participant explicitly raised excludable shared platform access.",
                "alternative_good_classes": {"member_only_access": "club_good", "open_access": "public_good"},
            },
        }
    ]
    res_a = enforce_economic_goods_policy(perception_with_alloc, policy="DISABLED")
    assert res_a[0]["proposed_economic_good_class"] == "club_good"
    assert res_a[0]["goods_assessment"]["question_frame_override_applied"] is True

    # Case B: Allocation question (policy=ENABLED) containing a perception-only subtopic
    alloc_with_perception = [
        {
            "proposed_label_en": "Perceived Lack of Trust in Leadership",
            "proposed_description": "Diagnostic expression of low trust without any resource/access proposal.",
            "proposed_economic_good_class": "public_good",
            "goods_assessment": {
                "goods_applicability": "NOT_APPLICABLE",
                "applicability_domain": None,
                "applicability_rationale": "Purely diagnostic perception of organizational trust.",
            },
        }
    ]
    res_b = enforce_economic_goods_policy(alloc_with_perception, policy="ENABLED")
    assert res_b[0]["proposed_economic_good_class"] == "NOT_APPLICABLE"
    assert res_b[0]["goods_assessment"]["question_frame_override_applied"] is True

    # Case C: Reject imposing 1D linear ordering across economic goods categories
    with pytest.raises(ValueError, match="must not impose a 1D ordering"):
        SubtopicGoodsAssessment(
            goods_applicability="APPLICABLE",
            applicability_domain="allocation",
            applicability_rationale="Testing ordering ban",
            imposes_linear_ordering=True,
        )


# ---------------------------------------------------------------------------
# 11-13. Response Status: Explicit No Opinion, Mixed Uncertainty, Missing Answers
# ---------------------------------------------------------------------------
def test_explicit_no_opinion_insufficient_info_without_fabricated_preference():
    extractor = SubtopicExtractor(coder_id="coder_a")

    # 1. Explicit no opinion -> reportable observed statement, NO fabricated preference, preserves missing_non_substantive
    raw_no_op = "Je n'ai pas d'avis sur cette question."
    res_no_op = extractor.process_response_detailed(
        participant_id="P_NOOP",
        question_id="Q08",
        question_index=8,
        canonical_prompt_en="HR management",
        raw_response=raw_no_op,
        preparsed_output={
            "participant_id": "P_NOOP",
            "question_id": "Q08",
            "is_substantive": False,
            "missingness_state": "missing_non_substantive",
            "response_status": "explicit_no_opinion",
            "detected_language": "fr",
            "evidence_spans": [{"verbatim_quote": raw_no_op, "span_role": "explicit_uncertainty_or_no_opinion"}],
            "subtopics": [],
        },
    )
    assert res_no_op["missingness_state"] == MissingnessState.MISSING_NON_SUBSTANTIVE
    assert res_no_op["response_status"] == ResponseStatusLabel.EXPLICIT_NO_OPINION
    assert res_no_op["has_observed_statement"] is True
    assert res_no_op["has_usable_preference"] is False
    assert len(res_no_op["evidence_spans"]) == 1
    assert res_no_op["evidence_spans"][0].verbatim_quote == raw_no_op
    assert len(res_no_op["candidates"]) == 0  # Zero fabricated preferences!

    # Attempting to fabricate preferences on explicit_no_opinion MUST fail schema validation
    with pytest.raises(ValueError, match="must not fabricate alternative preference probabilities"):
        LLMQuestionCodingResponse(
            participant_id="P_NOOP",
            question_id="Q08",
            is_substantive=False,
            missingness_state="missing_non_substantive",
            response_status="explicit_no_opinion",
            subtopics=[
                LLMSubtopicCandidate(
                    proposed_label_en="Fake Preference",
                    proposed_description="Should fail",
                    candidate_alternative_distribution={"lab": 0.5, "pole": 0.5},
                )
            ],
        )

    # 2. Insufficient experience / insufficient information detected automatically
    m_exp, st_exp = classify_response_status("Ich habe zu wenig Erfahrung mit dem System.")
    assert m_exp == MissingnessState.MISSING_NON_SUBSTANTIVE
    assert st_exp == ResponseStatusLabel.EXPLICIT_INSUFFICIENT_EXPERIENCE

    m_inf, st_inf = classify_response_status("Insufficient information about overhead numbers.")
    assert m_inf == MissingnessState.MISSING_NON_SUBSTANTIVE
    assert st_inf == ResponseStatusLabel.EXPLICIT_INSUFFICIENT_INFORMATION


def test_mixed_uncertainty_and_substantive_preference():
    extractor = SubtopicExtractor(coder_id="coder_a")
    raw_mixed = (
        "Je ne connais pas assez la répartition budgétaire actuelle, "
        "mais pour les recrutements doctoraux la décision doit rester au laboratoire."
    )

    res = extractor.process_response_detailed(
        participant_id="P_MIX",
        question_id="Q08",
        question_index=8,
        canonical_prompt_en="HR recruitment",
        raw_response=raw_mixed,
        preparsed_output={
            "participant_id": "P_MIX",
            "question_id": "Q08",
            "is_substantive": True,
            "missingness_state": "observed_usable",
            "response_status": "mixed_uncertainty_and_preference",
            "detected_language": "fr",
            "evidence_spans": [
                {"verbatim_quote": "pour les recrutements doctoraux la décision doit rester au laboratoire"}
            ],
            "uncertainty_statements": [
                {
                    "verbatim_quote": "Je ne connais pas assez la répartition budgétaire actuelle",
                    "span_role": "explicit_uncertainty_or_no_opinion",
                }
            ],
            "subtopics": [
                {
                    "proposed_label_en": "Doctoral Recruitment Authority",
                    "proposed_description": "Doctoral hiring decision stays at lab.",
                    "candidate_alternative_distribution": {"laboratory_level": 0.95, "pole_level": 0.05},
                    "semantic_importance": 0.85,
                    "coder_confidence": 0.90,
                    "probability_interpretation": "epistemic_uncertainty_over_preference",
                }
            ],
            "unmentioned_subtopic_keys": ["administrative_staff_hiring"],
        },
    )

    assert res["response_status"] == ResponseStatusLabel.MIXED_UNCERTAINTY_AND_PREFERENCE
    assert res["has_usable_preference"] is True
    assert len(res["evidence_spans"]) == 1
    assert len(res["uncertainty_spans"]) == 1
    assert "répartition budgétaire" in res["uncertainty_spans"][0].verbatim_quote
    assert len(res["candidates"]) == 1
    assert res["candidates"][0].candidate_alternative_distribution["laboratory_level"] == pytest.approx(0.95)
    assert res["unmentioned_subtopic_keys"] == ["administrative_staff_hiring"]


def test_missing_answers_without_coding():
    extractor = SubtopicExtractor(coder_id="coder_a")
    for blank_val in [None, "", "   ", "N/A", "keine Angabe", "Pas de remarque.", "-"]:
        res = extractor.process_response_detailed(
            participant_id="P_MISS",
            question_id="Q08",
            question_index=8,
            canonical_prompt_en="HR recruitment",
            raw_response=blank_val,
        )
        assert not res["missingness_state"].is_usable()
        assert res["evidence_spans"] == []
        assert res["uncertainty_spans"] == []
        assert res["candidates"] == []
        assert res["values"] == []


# ---------------------------------------------------------------------------
# 15. Repair Safety: Invalid Probabilities Rejected, Valid Repairs Logged, Offset Safety
# ---------------------------------------------------------------------------
def test_probability_repair_safety_and_audit():
    # 1. Reject negative, NaN, Inf, boolean
    with pytest.raises(ValueError, match="negative"):
        validate_and_repair_probabilities({"a": -0.1, "b": 1.1})
    with pytest.raises(ValueError, match="non-finite"):
        validate_and_repair_probabilities({"a": math.nan, "b": 1.0})
    with pytest.raises(ValueError, match="non-finite"):
        validate_and_repair_probabilities({"a": math.inf, "b": 0.0})
    with pytest.raises(ValueError, match="must be numeric"):
        validate_and_repair_probabilities({"a": True, "b": 0.0})  # type: ignore[dict-item]

    # 2. Reject arbitrary unnormalized scores (DO NOT silently normalize!)
    with pytest.raises(ValueError, match="materially invalid"):
        validate_and_repair_probabilities({"a": 0.4, "b": 0.2})  # sum = 0.6
    with pytest.raises(ValueError, match="materially invalid"):
        validate_and_repair_probabilities({"a": 4.0, "b": 2.0})  # Likert-like scores sum = 6
    with pytest.raises(ValueError, match="materially invalid"):
        validate_and_repair_probabilities({"a": 50.0, "b": 20.0})  # sum = 70 (ambiguous)

    # 3. Unambiguous percentage (sum ~ 100) scales and records raw values
    scaled, rec_pct = validate_and_repair_probabilities({"lab": 70.0, "pole": 30.0})
    assert scaled["lab"] == pytest.approx(0.70)
    assert scaled["pole"] == pytest.approx(0.30)
    assert rec_pct is not None
    assert rec_pct.repair_action == "unambiguous_percentage_scaling"
    assert rec_pct.raw_values == {"lab": 70.0, "pole": 30.0}

    # 4. Micro rounding drift within +-0.01 renormalizes and logs repair
    repaired, rec_drift = validate_and_repair_probabilities({"a": 0.333, "b": 0.333, "c": 0.333})
    assert sum(repaired.values()) == pytest.approx(1.0, abs=1e-4)
    assert rec_drift is not None
    assert rec_drift.repair_action == "micro_drift_renormalization"
    assert rec_drift.raw_values == {"a": 0.333, "b": 0.333, "c": 0.333}


def test_quotation_repair_safety_and_repeated_quote_disambiguation():
    # Never invent or paraphrase missing quote
    with pytest.raises(ValueError, match="paraphrasing/invention forbidden"):
        find_exact_char_offsets("Le laboratoire décide.", "Le labo prend la décision.")

    # Repeated identical quotation requires unambiguous char_start or sentence_index
    repeated_text = "Autonomie requise. Le pôle coordonne. Autonomie requise."
    with pytest.raises(AmbiguousQuoteOffsetError, match="Ambiguous repeated quotation"):
        find_exact_char_offsets(repeated_text, "Autonomie requise.")

    # Disambiguating via sentence_index=2 resolves to second occurrence cleanly
    s, e, matched = find_exact_char_offsets(repeated_text, "Autonomie requise.", sentence_index=2)
    assert s > 20
    assert repeated_text[s:e] == "Autonomie requise."

    # Disambiguating via expected_char_start=0 resolves to first occurrence
    s0, e0, _ = find_exact_char_offsets(repeated_text, "Autonomie requise.", expected_char_start=0)
    assert s0 == 0


def test_mechanical_json_repair_audit():
    raw = """Here is JSON:
    ```json
    {
      "participant_id": "P1",
      "question_id": "Q08",
      "subtopics": [],
    }
    ```"""
    parsed, repairs = repair_json_string_with_audit(raw)
    assert parsed["participant_id"] == "P1"
    assert "stripped_markdown_code_fence" in repairs
    assert "removed_trailing_commas" in repairs


# ---------------------------------------------------------------------------
# End-to-End QuestionCorpusCoder & Multilingual Fixtures Verification
# ---------------------------------------------------------------------------
def test_question_corpus_coder_end_to_end():
    corpus = _build_sample_corpus()
    coder = QuestionCorpusCoder(run_id="run_20261111_002")

    def disc_a(sys_p, usr_p):
        return {
            "question_id": "Q11",
            "discovered_subtopics": [
                {
                    "subtopic_key": "overhead_split",
                    "proposed_label_en": "Overhead Allocation Formula",
                    "definition": "Sharing grant overheads between labs and pole.",
                    "decision_object": "overhead_allocation",
                    "mechanism": "percentage_split",
                    "scope": "lab_vs_pole",
                    "discovered_alternatives": [
                        {"alternative_id": "lab_60_pole_40", "label_en": "60% Lab / 40% Pole"},
                        {"alternative_id": "pole_shared_staff", "label_en": "Pole Shared Staff"},
                    ],
                    "goods_assessment": {
                        "goods_applicability": "APPLICABLE",
                        "applicability_domain": "financing",
                        "applicability_rationale": "Financial distribution of overhead funds.",
                    },
                    "supporting_response_ids": ["R_01", "R_02"],
                    "supporting_participant_ids": ["P_01", "P_02"],
                },
                {
                    "subtopic_key": "repair_reserve",
                    "proposed_label_en": "Equipment Repair Contingency",
                    "definition": "Emergency 5% reserve for equipment repair.",
                    "decision_object": "equipment_repair_reserve",
                    "mechanism": "reserve_fund",
                    "scope": "pole_equipment",
                    "discovered_alternatives": [{"alternative_id": "five_pct_reserve", "label_en": "5% Reserve"}],
                    "is_minority_position": True,
                    "supporting_response_ids": ["R_03"],
                    "supporting_participant_ids": ["P_03"],
                },
            ],
        }

    def disc_b(sys_p, usr_p):
        return disc_a(sys_p, usr_p)

    def assign_common(resp: NormalizedResponseInput, tax, sys_p: str, usr_p: str) -> dict:
        if resp.response_id == "R_04":
            return {
                "participant_id": resp.participant_id,
                "question_id": "Q11",
                "response_id": resp.response_id,
                "is_substantive": True,
                "missingness_state": "observed_usable",
                "response_status": "explicit_no_opinion",
                "detected_language": resp.detected_language,
                "evidence_spans": [{"verbatim_quote": resp.raw_value}],
                "subtopics": [],
            }
        if resp.response_id == "R_01":
            return {
                "participant_id": resp.participant_id,
                "question_id": "Q11",
                "response_id": resp.response_id,
                "is_substantive": True,
                "response_status": "observed_substantive",
                "detected_language": "fr",
                "evidence_spans": [{"verbatim_quote": "laboratoire porteur à 60% et au pôle à 40%"}],
                "subtopics": [
                    {
                        "subtopic_key": "overhead_split",
                        "proposed_label_en": "Overhead Allocation Formula",
                        "proposed_description": "Sharing grant overheads between labs and pole.",
                        "decision_object": "overhead_allocation",
                        "mechanism": "percentage_split",
                        "scope": "lab_vs_pole",
                        "candidate_alternative_distribution": {"lab_60_pole_40": 0.9, "pole_shared_staff": 0.1},
                        "probability_interpretation": "epistemic_uncertainty_over_preference",
                        "semantic_importance": 0.9,
                        "coder_confidence": 0.92,
                        "proposed_economic_good_class": "common_good",
                    }
                ],
                "values": [
                    {
                        "original_label": "Proportional Fair Return",
                        "value_definition": "Returning majority of indirect costs to the earning lab.",
                        "polarity": 1.0,
                        "semantic_importance": 0.85,
                        "coder_confidence": 0.90,
                        "evidence_quotes": ["laboratoire porteur à 60% et au pôle à 40%"],
                    }
                ],
                "unmentioned_subtopic_keys": ["repair_reserve"],
            }
        if resp.response_id == "R_02":
            return {
                "participant_id": resp.participant_id,
                "question_id": "Q11",
                "response_id": resp.response_id,
                "is_substantive": True,
                "response_status": "observed_substantive",
                "detected_language": "en",
                "evidence_spans": [{"verbatim_quote": "fund shared technical staff across the pole"}],
                "subtopics": [
                    {
                        "subtopic_key": "overhead_split",
                        "proposed_label_en": "Overhead Allocation Formula",
                        "proposed_description": "Sharing grant overheads between labs and pole.",
                        "decision_object": "overhead_allocation",
                        "mechanism": "percentage_split",
                        "scope": "lab_vs_pole",
                        "candidate_alternative_distribution": {"lab_60_pole_40": 0.05, "pole_shared_staff": 0.95},
                        "probability_interpretation": "epistemic_uncertainty_over_preference",
                        "semantic_importance": 0.88,
                        "coder_confidence": 0.90,
                        "proposed_economic_good_class": "club_good",
                    }
                ],
                "unmentioned_subtopic_keys": ["repair_reserve"],
            }
        # R_03 minority position
        return {
            "participant_id": resp.participant_id,
            "question_id": "Q11",
            "response_id": resp.response_id,
            "is_substantive": True,
            "response_status": "observed_substantive",
            "detected_language": "en",
            "evidence_spans": [{"verbatim_quote": "emergency equipment repair reserve from 5% of overheads"}],
            "subtopics": [
                {
                    "subtopic_key": "repair_reserve",
                    "proposed_label_en": "Equipment Repair Contingency",
                    "proposed_description": "Emergency 5% reserve for equipment repair.",
                    "decision_object": "equipment_repair_reserve",
                    "mechanism": "reserve_fund",
                    "scope": "pole_equipment",
                    "candidate_alternative_distribution": {"five_pct_reserve": 1.0},
                    "semantic_importance": 0.80,
                    "coder_confidence": 0.95,
                    "proposed_economic_good_class": "club_good",
                }
            ],
            "unmentioned_subtopic_keys": ["overhead_split"],
        }

    out = coder.code_question_corpus(
        corpus=corpus,
        coder_a_discovery_fn=disc_a,
        coder_b_discovery_fn=disc_b,
        coder_a_assign_fn=assign_common,
        coder_b_assign_fn=assign_common,
    )

    assert out["source_evidence_hash"] == compute_source_evidence_hash(corpus)
    assert out["coder_a_prompt_hash"] != out["coder_b_prompt_hash"]
    assert len(out["canonical_subtopics"]) == 2
    assert len(out["value_stage_a_extractions"]) == 2  # P_01 coded by A and B
    assert out["value_stage_a_extractions"][0].original_label == "Proportional Fair Return"
    assert len(out["value_stage_b_proposals"]) == 1
    assert out["response_status_counts"]["explicit_no_opinion"] == 1
    assert out["response_status_counts"]["raw_blank"] == 1
    assert "P_04" not in out["observed_preference_participants"]
    assert "P_04" in out["observed_statement_participants"]

    # Verify methodological flag is present on ThemesCodebook
    cb = ThemesCodebook(run_id="run_20261111_002")
    assert "NOT measured cardinal utility" in cb.methodological_flags["alternative_probabilities_meaning"]


def test_multilingual_fixtures_processing():
    fixtures = get_multilingual_test_fixtures()
    extractor = SubtopicExtractor(coder_id="coder_a")

    for f_id, data in fixtures.items():
        text = data.get("text")
        lang = data.get("language", "fr")
        q_id = data.get("question_id", "Q08")
        is_sub = data.get("is_substantive", True)
        status = data.get("response_status", "observed_substantive")

        if not is_sub:
            res = extractor.process_response_detailed(
                participant_id=data["participant_id"],
                question_id=q_id,
                question_index=int(q_id[1:]),
                canonical_prompt_en="Prompt",
                raw_response=text,
            )
            assert res["evidence_spans"] == []
            assert res["candidates"] == []
            assert not res["missingness_state"].is_usable()
        elif status in {"explicit_no_opinion", "insufficient_experience", "insufficient_information"}:
            res = extractor.process_response_detailed(
                participant_id=data["participant_id"],
                question_id=q_id,
                question_index=int(q_id[1:]),
                canonical_prompt_en="Prompt",
                raw_response=text,
                detected_language=lang,
                preparsed_output={
                    "participant_id": data["participant_id"],
                    "question_id": q_id,
                    "is_substantive": False,
                    "missingness_state": "missing_non_substantive",
                    "response_status": status,
                    "detected_language": lang,
                    "evidence_spans": [{"verbatim_quote": text.strip()}],
                    "subtopics": [],
                },
            )
            assert res["missingness_state"] == MissingnessState.MISSING_NON_SUBSTANTIVE
            assert res["has_observed_statement"] is True
            assert res["has_usable_preference"] is False
            assert len(res["evidence_spans"]) == 1
            assert res["candidates"] == []
        else:
            mock_subtopics = [
                LLMSubtopicCandidate(
                    proposed_label_en=st["label"],
                    proposed_description=st["description"],
                    candidate_alternative_distribution=st["alternatives"],
                    semantic_importance=st["importance"],
                    coder_confidence=st["confidence"],
                    proposed_economic_good_class=st.get("good_class"),
                )
                for st in data["expected_subtopics"]
            ]
            mock_spans = [
                LLMEvidenceSpan(
                    verbatim_quote=q,
                    detected_language=lang,
                    english_working_gloss=f"Gloss in {lang}",
                )
                for q in data["expected_quotes"]
            ]
            unc_spans = [
                LLMEvidenceSpan(
                    verbatim_quote=uq,
                    detected_language=lang,
                    span_role="explicit_uncertainty_or_no_opinion",
                )
                for uq in data.get("uncertainty_quotes", [])
            ]
            preparsed = LLMQuestionCodingResponse(
                participant_id=data["participant_id"],
                question_id=q_id,
                is_substantive=True,
                missingness_state=MissingnessState.OBSERVED_USABLE.value,
                response_status=status,
                detected_language=lang,
                evidence_spans=mock_spans,
                uncertainty_statements=unc_spans,
                subtopics=mock_subtopics,
            )
            res = extractor.process_response_detailed(
                participant_id=data["participant_id"],
                question_id=q_id,
                question_index=int(q_id[1:]),
                canonical_prompt_en="Prompt",
                raw_response=text,
                detected_language=lang,
                preparsed_output=preparsed,
            )
            assert res["missingness_state"] == MissingnessState.OBSERVED_USABLE
            assert len(res["evidence_spans"]) >= 1
            for sp in res["evidence_spans"]:
                assert text[sp.char_start : sp.char_end] == sp.verbatim_quote
            for cd in res["candidates"]:
                assert abs(sum(cd.candidate_alternative_distribution.values()) - 1.0) < 1e-4


def test_zero_foreign_entity_leakage():
    forbidden_terms = [
        "Package A",
        "Package B",
        "Option 1: Centralized",
        "LegacySurvey2022",
        "SurveyCohortAlpha",
    ]
    for term in forbidden_terms:
        assert term not in SYSTEM_PROMPT_QUALITATIVE_CODER
        assert term not in json.dumps(list(CANONICAL_ORGANISATIONAL_VALUES.keys()))
