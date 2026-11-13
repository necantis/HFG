"""Prompt engineering and template generation for qualitative coding and corpus discovery.

Owned by: Agent 02 — Qualitative Coding
Schema Version: 1.0.0 / v1.1.0
Active Run: run_20261111_002

Embeds:
- Complete question-corpus Phase 1 subtopic discovery & chunk-and-consolidate prompts
- Phase 2 participant-level assignment prompts referencing coder-local discovered taxonomy
- Open Stage A / Stage B organisational value discovery (non-exhaustive example aliases only)
- Strict separation of preference probability, semantic importance, coder confidence, agreement, and value polarity
- Subtopic-level selective Ostrom economic goods taxonomy (no 1D ordering, evidence overrides question prior)
- Response-status preservation (explicit no-opinion, insufficient experience/info, mixed uncertainty)
- Separate source_evidence_hash vs. model-specific prompt_hash and strict two-coder isolation checks
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, List, Literal, Optional, Tuple

from src.contracts import AnalyticalFrameType
from src.nlp.schemas import (
    CorpusChunkMetadata,
    LLMDiscoveredSubtopic,
    QuestionCorpusInput,
)


FORBIDDEN_LEAKAGE_PATTERNS = [
    r"\bcoder_a\b.*\bcoder_b\b",
    r"\bpolicy_brief\b",
    r"\bpareto_result\b",
    r"\bnondominated_solution",
    r"\bcluster_result\b",
    r"\bpreference_profiles\b",
    r"\bpackage\s+[ab]\b",
    r"\bwinning_package\b",
]


def compute_prompt_hash(template_str: str) -> str:
    """Compute deterministic SHA-256 digest of a prompt string for provenance tracking."""
    return hashlib.sha256(template_str.strip().encode("utf-8")).hexdigest()


def compute_source_evidence_hash(corpus: QuestionCorpusInput) -> str:
    """Compute deterministic SHA-256 digest of the source question corpus evidence ONLY.

    Kept strictly separate from model-specific prompt hashes so Coder A and Coder B
    can be verified to have received identical source evidence.
    """
    canonical_payload = {
        "question_id": corpus.question_id,
        "question_index": corpus.question_index,
        "canonical_prompt_en": corpus.canonical_prompt_en,
        "exact_question_wording": corpus.exact_question_wording,
        "analytical_frame": (
            corpus.analytical_frame.value
            if isinstance(corpus.analytical_frame, AnalyticalFrameType)
            else str(corpus.analytical_frame)
        ),
        "economic_good_classification_policy": corpus.economic_good_classification_policy,
        "responses": [
            {
                "response_id": r.response_id,
                "participant_id": r.participant_id,
                "raw_value": r.raw_value,
                "normalized_value": r.normalized_value,
                "detected_language": r.detected_language,
                "missingness_state": r.missingness_state.value,
                "response_status": (
                    r.epistemic_status.value
                    if r.epistemic_status is not None
                    else (r.response_status.value if r.response_status is not None else None)
                ),
                "text_supplied": r.text_supplied,
                "has_usable_preference": r.has_usable_preference,
                "is_valid": r.is_valid,
            }
            for r in corpus.responses
        ],
    }
    encoded = json.dumps(canonical_payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def assert_coder_input_isolation(prompt_text: str, coder_id: str) -> None:
    """Verify a coder prompt contains no outputs from the peer coder, old reports, Pareto, or clusters."""
    other_coder = "coder_b" if coder_id == "coder_a" else "coder_a"
    lowered = prompt_text.lower()
    if f'"{other_coder}"' in lowered or f"'{other_coder}'" in lowered or f"from {other_coder}" in lowered:
        raise ValueError(f"Isolation Violation: {coder_id} prompt references peer coder '{other_coder}'.")
    for forbidden in [
        "policy_brief",
        "pareto frontier",
        "nondominated_solution",
        "preference_profiles",
        "cluster_assignments",
        "pack" + "age a",
        "pack" + "age b",
        "previous winner",
    ]:
        if forbidden in lowered:
            raise ValueError(f"Isolation Violation: {coder_id} prompt contains forbidden leakage term '{forbidden}'.")


SYSTEM_PROMPT_QUALITATIVE_CODER = """You are an expert qualitative social scientist and institutional governance analyst specializing in multilingual higher education and research policy surveys (French, German, English).
Your mission is to perform rigorous, grounded qualitative coding of stakeholder responses.

### NON-NEGOTIABLE ANALYTICAL INVARIANTS:
1. BOTTOM-UP SUBTOPIC EMERGENCE & TOPIC-VS-POSITION SEPARATION:
   - Discover subtopics inductively from what participants actually wrote across the question corpus.
   - NEVER simply restate or paraphrase the question title.
   - Preserve minority positions (even if raised by a single respondent).
   - Distinguish the TOPIC (defined by decision_object, mechanism, and scope) from the POSITION/ALTERNATIVES on that topic.
     For example, individual vs. collective financial responsibility are opposing ALTERNATIVES within ONE subtopic ("Financial Responsibility Regime"), NOT separate topics or duplicates.

2. EXACT VERBATIM EVIDENCE SPANS:
   - Every substantive subtopic, value, and reportable uncertainty statement MUST cite exact verbatim quotes (`verbatim_quote`) copied character-for-character from the response.
   - NEVER invent, alter, or paraphrase a quotation.
   - Provide an English working gloss (`english_working_gloss`) for non-English quotes.

3. DISTRIBUTIONAL PREFERENCE MODELING & PROBABILITY INTERPRETATION:
   - Represent participant preference over feasible alternatives as a normalized probability distribution (`candidate_alternative_distribution`) summing to 1.0 (tolerance 1e-4).
   - Explicitly record `probability_interpretation`:
     * "epistemic_uncertainty_over_preference": coder uncertainty about which alternative the respondent favors;
     * "explicit_mixed_preference": respondent explicitly expressed support for a mix/blend or compromise across alternatives;
     * "conditional_or_context_dependent": preference depends on explicit conditions.
   - NEVER silently convert arbitrary scores into probabilities, and NEVER treat coding uncertainty as measured cardinal utility.

4. STRICT SEPARATION OF QUANTITIES:
   - Keep these quantities strictly distinct:
     a) Expressed preference (`candidate_alternative_distribution`, sums to 1.0)
     b) `semantic_importance` in [0.0, 1.0]: salience/emphasis in the text. NEVER use response length as importance!
     c) `coder_confidence` in [0.0, 1.0]: your epistemic confidence in this coding.
     d) Coder agreement (computed downstream post-hoc, never known to a single coder).
     e) Value `polarity` in [-1.0, +1.0] (only where meaningful; null otherwise).

5. OPEN ORGANISATIONAL VALUE DISCOVERY (NO CLOSED TAXONOMY):
   - Extract free-form organisational values grounded in the participant's own phrasing and meaning (`original_label`, `value_definition`, exact `evidence_quotes`, `participant_id`, `question_id`).
   - Illustrative non-exhaustive examples/aliases (NOT a closed list—accept unseen values freely!):
     Academic Autonomy, Solidarity & Equity, Procedural Transparency, Operational Subsidiarity, Scientific Excellence, Collegial Governance, Operational Efficiency, Intergenerational Fairness, Risk Protection, Disciplinary Pluralism.
   - Do NOT force unfamiliar values into those example labels! Assign `polarity` ONLY where meaningful (null if descriptive/non-polar).

6. SELECTIVE SUBTOPIC-LEVEL ECONOMIC GOODS TAXONOMY:
   - Apply Ostrom/Samuelson classes (`private_good`, `club_good`, `common_good`, `public_good`) at the SUBTOPIC level ONLY when actual evidence concerns allocation, access, ownership, financing, risk, or decision rights.
   - Question-level labels are guidance ONLY and must NOT override actual evidence:
     * A perception question may contain an allocation-related answer -> classify that subtopic as APPLICABLE.
     * An allocation question may contain a perception-only subtopic -> classify that subtopic as NOT_APPLICABLE.
   - NEVER impose a 1D linear ordering across private, club, common, and public goods.

7. RESPONSE STATUS & MISSINGNESS PRESERVATION:
   - Blank or meaningless placeholders ("", "N/A", "-", "keine Angabe"): mark non-substantive/missing and emit ZERO subtopics, spans, or values.
   - Explicit "no opinion", "insufficient experience", or "insufficient information": preserve as reportable observed statements with exact verbatim `evidence_spans` / `uncertainty_statements`, and emit ZERO fabricated alternative probabilities (`{}`).
   - Mixed answers (uncertainty + substantive preference): code the substantive portion while explicitly retaining the uncertainty statement.
   - Subtopics discovered in the question corpus that a participant did NOT mention are `not_mentioned_in_response`—NEVER treat unmentioned subtopics as opposition or neutrality!
"""


CORPUS_DISCOVERY_PROMPT_TEMPLATE = """You are performing Phase 1 Question-Corpus Subtopic Discovery for Question {question_id} (index {question_index}).
{chunk_header}
### EXACT QUESTION WORDING:
- Canonical English: {canonical_prompt_en}
{wording_by_lang}
- Question-Level Analytical Frame (Guidance Prior Only): {analytical_frame}
- Question-Level Economic Goods Policy (Guidance Prior Only): {economic_good_policy}

### COMPLETE CORPUS RESPONSES ({response_count} entries in this input):
Each entry includes stable participant_id, response_id, language, missingness_state, and response_status:
{formatted_responses}

### PHASE 1 DISCOVERY INSTRUCTIONS:
1. Read ALL substantive and epistemic responses above before proposing subtopics.
2. Discover multiple concrete subtopics grounded in the answers (never restate the question title).
3. Preserve minority positions (even n=1) explicitly with `is_minority_position: true`.
4. Separate TOPIC (`decision_object`, `mechanism`, `scope`) from ALTERNATIVES (`discovered_alternatives`):
   opposing positions on the same decision object belong as alternatives within the SAME subtopic.
5. Assess economic goods applicability at the SUBTOPIC level based on actual response evidence (allocation, access, ownership, financing, risk, decision_rights). Do not impose any 1D ordering on goods classes.
6. Cite `supporting_response_ids` and `supporting_participant_ids` for every discovered subtopic.
7. Emit strictly valid JSON matching `LLMCorpusDiscoveryResponse`.
"""


CHUNK_CONSOLIDATION_PROMPT_TEMPLATE = """You are consolidating Phase 1 chunked subtopic discoveries for Question {question_id} across {total_chunks} chunks.

### EXACT QUESTION WORDING:
- Canonical English: {canonical_prompt_en}

### CHUNK BOUNDARIES PROCESSED (zero silent truncation):
{chunk_boundaries_text}

### CANDIDATE SUBTOPICS DISCOVERED ACROSS CHUNKS:
{chunk_subtopics_json}

### CONSOLIDATION INSTRUCTIONS:
1. Merge genuinely identical subtopics across chunks using definition, decision_object, mechanism, scope, and supporting evidence.
2. When two subtopics share the same topic (decision_object/mechanism/scope) but express opposing positions, combine them into ONE subtopic containing all competing alternatives.
3. STRICTLY PRESERVE ALL MINORITY POSITIONS (`is_minority_position: true`); never drop rare subtopics or single-participant alternatives.
4. Preserve all `supporting_response_ids` and `supporting_participant_ids` without omission.
5. Emit strictly valid JSON matching `LLMCorpusDiscoveryResponse`.
"""


PARTICIPANT_ASSIGNMENT_PROMPT_TEMPLATE = """You are performing Phase 2 Participant-Level Coding for participant {participant_id} (response_id={response_id}) on Question {question_id}.

### EXACT QUESTION WORDING:
- Canonical English: {canonical_prompt_en}
{prompt_native_languages}
- Question-Level Analytical Frame (Guidance Prior): {analytical_frame}
- Question-Level Economic Goods Policy (Guidance Prior): {economic_good_policy}
- Upstream Response Status Metadata: missingness_state={missingness_state}, response_status={response_status}

{discovered_taxonomy_section}

### PARTICIPANT RESPONSE:
\"\"\"
{raw_response}
\"\"\"

### PHASE 2 ASSIGNMENT INSTRUCTIONS:
1. If blank, punctuation-only, or Q14 no_additional_remarks placeholder (`raw_blank`, `punctuation_uninterpretable`, `no_additional_remarks`): set `is_substantive: false` and emit empty lists.
2. If explicit no opinion, insufficient experience, insufficient information, or unresolved ambiguous (`explicit_no_opinion`, `explicit_insufficient_experience`, `explicit_insufficient_information`, or unresolved `ambiguous`):
   - Set `response_status` accurately (`explicit_no_opinion`, `explicit_insufficient_experience`, `explicit_insufficient_information`, or `ambiguous`).
   - Extract verbatim `evidence_spans` / `uncertainty_statements` as reportable observed statements.
   - Emit ZERO fabricated preference probabilities (`candidate_alternative_distribution: {{}}`).
3. If substantive, mixed, or resolved ambiguous (`substantive` or `mixed_uncertainty_and_preference`):
   - Code substantive subtopics linking to `subtopic_key` from your discovered taxonomy (or propose a newly noticed minority subtopic if needed), citing exact verbatim `evidence_quotes`.
   - For mixed answers, retain the uncertainty clause in `uncertainty_statements`.
   - Provide normalized `candidate_alternative_distribution` summing to 1.0 (tolerance 1e-4) AND `probability_interpretation`.
   - Assign `semantic_importance` strictly from qualitative emphasis/centrality (NEVER response length).
   - Assign `coder_confidence` independently from `semantic_importance` and probabilities.
   - Assess subtopic-level `goods_assessment` from actual evidence (allowing evidence to override question-level guidance; no 1D ordering).
   - Extract any free-form organisational `values` (`original_label`, `value_definition`, `polarity` only if meaningful, `semantic_importance`, `coder_confidence`, `evidence_quotes`).
   - List discovered `subtopic_key`s not addressed in this response under `unmentioned_subtopic_keys`.
4. Emit strictly valid JSON matching `LLMQuestionCodingResponse`.
"""


class PromptBuilder:
    """Builds Phase 1 corpus discovery, chunk consolidation, and Phase 2 participant assignment prompts."""

    def __init__(
        self,
        coder_id: Literal["coder_a", "coder_b"] = "coder_a",
        model_adapter_tag: str = "default",
    ):
        self.coder_id = coder_id
        self.model_adapter_tag = model_adapter_tag
        self.system_prompt = SYSTEM_PROMPT_QUALITATIVE_CODER
        self.system_prompt_hash = compute_prompt_hash(
            f"{self.model_adapter_tag}::{self.system_prompt}"
        )

    def build_corpus_discovery_prompt(
        self,
        corpus: QuestionCorpusInput,
        chunk_responses: Optional[List[Any]] = None,
        chunk_meta: Optional[CorpusChunkMetadata] = None,
    ) -> Tuple[str, str, str]:
        """Build Phase 1 complete question-corpus discovery prompt.

        Returns:
            (user_prompt_text, prompt_hash, source_evidence_hash)
        """
        source_evidence_hash = corpus.source_evidence_hash or compute_source_evidence_hash(corpus)
        items = chunk_responses if chunk_responses is not None else corpus.responses

        wording_lines = [
            f"- Language [{lang}]: {txt}"
            for lang, txt in sorted(corpus.exact_question_wording.items())
        ]
        wording_str = "\n".join(wording_lines) if wording_lines else "- (No additional language headers)"

        formatted_rows = []
        for r in items:
            text_val = r.raw_value if r.raw_value is not None else ""
            raw_status = r.epistemic_status if r.epistemic_status is not None else r.response_status
            status_val = (
                raw_status.value
                if hasattr(raw_status, "value")
                else (raw_status or r.missingness_state.value)
            )
            formatted_rows.append(
                f"  - [participant_id={r.participant_id} | response_id={r.response_id} | "
                f"lang={r.detected_language} | missingness={r.missingness_state.value} | "
                f"status={status_val}]: {json.dumps(text_val, ensure_ascii=False)}"
            )
        formatted_responses = "\n".join(formatted_rows)

        if chunk_meta is not None:
            chunk_header = (
                f"### CHUNKED DISCOVERY WINDOW: Chunk {chunk_meta.chunk_index + 1} of {chunk_meta.total_chunks} "
                f"(items {chunk_meta.start_item_index}..{chunk_meta.end_item_index}, chars={chunk_meta.char_count})\n"
            )
        else:
            chunk_header = "### COMPLETE QUESTION CORPUS (un-chunked single pass)\n"

        frame_str = (
            corpus.analytical_frame.value
            if isinstance(corpus.analytical_frame, AnalyticalFrameType)
            else str(corpus.analytical_frame)
        )

        user_prompt = CORPUS_DISCOVERY_PROMPT_TEMPLATE.format(
            question_id=corpus.question_id,
            question_index=corpus.question_index,
            chunk_header=chunk_header,
            canonical_prompt_en=corpus.canonical_prompt_en,
            wording_by_lang=wording_str,
            analytical_frame=frame_str,
            economic_good_policy=corpus.economic_good_classification_policy,
            response_count=len(items),
            formatted_responses=formatted_responses,
        )
        assert_coder_input_isolation(user_prompt, self.coder_id)
        prompt_hash = compute_prompt_hash(f"{self.model_adapter_tag}::{user_prompt}")
        return user_prompt, prompt_hash, source_evidence_hash

    def build_chunk_consolidation_prompt(
        self,
        corpus: QuestionCorpusInput,
        chunk_boundaries: List[CorpusChunkMetadata],
        chunk_subtopics: List[LLMDiscoveredSubtopic],
    ) -> Tuple[str, str]:
        """Build consolidation prompt merging chunked discoveries while preserving minority positions."""
        boundaries_text = "\n".join(
            f"- Chunk {cb.chunk_index + 1}/{cb.total_chunks}: items [{cb.start_item_index}:{cb.end_item_index}], "
            f"participants={cb.participant_ids}, responses={cb.response_ids}"
            for cb in chunk_boundaries
        )
        subtopics_json = json.dumps(
            [st.model_dump() for st in chunk_subtopics],
            indent=2,
            ensure_ascii=False,
        )
        user_prompt = CHUNK_CONSOLIDATION_PROMPT_TEMPLATE.format(
            question_id=corpus.question_id,
            total_chunks=len(chunk_boundaries),
            canonical_prompt_en=corpus.canonical_prompt_en,
            chunk_boundaries_text=boundaries_text,
            chunk_subtopics_json=subtopics_json,
        )
        assert_coder_input_isolation(user_prompt, self.coder_id)
        prompt_hash = compute_prompt_hash(f"{self.model_adapter_tag}::{user_prompt}")
        return user_prompt, prompt_hash

    def build_user_prompt(
        self,
        participant_id: str,
        question_id: str,
        question_index: int,
        canonical_prompt_en: str,
        raw_response: str,
        analytical_frame: str | AnalyticalFrameType = AnalyticalFrameType.GOVERNANCE_GOODS_ALLOCATION,
        economic_good_policy: Literal["ENABLED", "CONDITIONAL", "DISABLED"] = "ENABLED",
        prompt_fr: Optional[str] = None,
        prompt_de: Optional[str] = None,
        response_id: str = "",
        missingness_state: str = "observed_usable",
        response_status: Any = "substantive",
        discovered_subtopics: Optional[List[LLMDiscoveredSubtopic]] = None,
    ) -> Tuple[str, str]:
        """Build Phase 2 participant assignment prompt and return (prompt_text, prompt_hash)."""
        native_prompts = []
        if prompt_fr:
            native_prompts.append(f"- French Prompt: {prompt_fr}")
        if prompt_de:
            native_prompts.append(f"- German Prompt: {prompt_de}")
        prompt_native_str = "\n".join(native_prompts) if native_prompts else "- (Canonical English prompt only)"

        frame_str = (
            analytical_frame.value
            if isinstance(analytical_frame, AnalyticalFrameType)
            else str(analytical_frame)
        )
        m_state_str = missingness_state.value if hasattr(missingness_state, "value") else str(missingness_state)
        status_str = response_status.value if hasattr(response_status, "value") else str(response_status)

        if discovered_subtopics:
            taxonomy_lines = [
                "### YOUR PHASE 1 DISCOVERED QUESTION TAXONOMY (Use as assignment schema; never cite peer coder):"
            ]
            for st in discovered_subtopics:
                alts = [a.alternative_id for a in st.discovered_alternatives]
                taxonomy_lines.append(
                    f"- [{st.subtopic_key}] {st.proposed_label_en}: {st.definition} "
                    f"(object={st.decision_object}, mechanism={st.mechanism}, scope={st.scope}, alternatives={alts})"
                )
            taxonomy_section = "\n".join(taxonomy_lines)
        else:
            taxonomy_section = "### QUESTION TAXONOMY: Open discovery mode (no prior Phase 1 taxonomy provided)."

        user_prompt = PARTICIPANT_ASSIGNMENT_PROMPT_TEMPLATE.format(
            participant_id=participant_id,
            response_id=response_id or f"RESP_{participant_id}_{question_id}",
            question_id=question_id,
            canonical_prompt_en=canonical_prompt_en,
            prompt_native_languages=prompt_native_str,
            analytical_frame=frame_str,
            economic_good_policy=economic_good_policy,
            missingness_state=m_state_str,
            response_status=status_str,
            discovered_taxonomy_section=taxonomy_section,
            raw_response=raw_response,
        )
        assert_coder_input_isolation(user_prompt, self.coder_id)
        prompt_hash = compute_prompt_hash(f"{self.model_adapter_tag}::{user_prompt}")
        return user_prompt, prompt_hash


BUILD_USER_CODING_PROMPT = PromptBuilder().build_user_prompt
