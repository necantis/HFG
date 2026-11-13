"""Robust parsing, validation, and repair routines for LLM structured outputs.

Owned by: Agent 02 — Qualitative Coding
Schema Version: 1.0.0 / v1.1.0
Active Run: run_20261111_002

Implements strict Repair Safety (Section 9) & Response Status Preservation (Section 8):
- Mechanical JSON repairs ONLY when semantic meaning is unchanged (audit-logged).
- Probability validation preserving raw values, recording every repair, rejecting
  negative, non-finite, or materially invalid distributions, never silently normalizing
  arbitrary scores, and scaling percentages only when the 0-100 scale is unambiguous.
- Exact verbatim evidence span offset resolution without ever inventing or paraphrasing
  quotations; repeated identical quotations require unambiguous offset/sentence resolution.
- Consumes Agent 01's missingness_state and response-status metadata while preserving
  explicit no-opinion, insufficient-experience, and insufficient-information statements.
- Subtopic-level selective economic goods assessment (question frame guides, never overrides evidence).
"""

from __future__ import annotations

import json
import math
import re
from typing import Any, Dict, List, Optional, Tuple

from src.contracts import EconomicGoodClass, MissingnessState, ResponseEpistemicStatus
from src.nlp.schemas import (
    BLANK_OR_NON_REPORTABLE_STATUSES,
    ProbabilityRepairRecord,
    REPORTABLE_NO_PREFERENCE_STATUSES,
    ResponseStatusLabel,
    SubtopicGoodsAssessment,
    USABLE_PREFERENCE_STATUSES,
    normalize_epistemic_status,
)


class AmbiguousQuoteOffsetError(ValueError):
    """Raised when an identical quotation appears multiple times without disambiguating context."""


# Truly blank / placeholder non-substantive patterns (receive ZERO coding).
# Concise substantive answers ('Oui', 'Non', 'Idem', 'Aucun') are NEVER treated as missingness placeholders.
NON_SUBSTANTIVE_PATTERNS = [
    r"^\s*$",
    r"^\s*n/?a\s*$",
    r"^\s*na\s*$",
    r"^\s*none\s*$",
    r"^\s*nil\s*$",
    r"^\s*[\?\.\-\/\!\:\;\,]+\s*$",
    # French placeholders
    r"^\s*rien\s*$",
    r"^\s*rien\s+de\s+particulier.*$",
    r"^\s*pas\s+de\s+remarque[s]?\.?\s*$",
    # German placeholders
    r"^\s*keine\s+angabe[n]?\.?\s*$",
    r"^\s*nichts\s*$",
    r"^\s*kein\s+kommentar\.?\s*$",
    r"^\s*k\.?a\.?\s*$",
    # English placeholders
    r"^\s*no\s+comment[s]?\.?\s*$",
    r"^\s*not\s+applicable\.?\s*$",
    r"^\s*nothing\s*$",
    r"^\s*none\s+at\s+this\s+time\.?\s*$",
]

NON_SUBSTANTIVE_REGEX = re.compile("|".join(NON_SUBSTANTIVE_PATTERNS), re.IGNORECASE)
PUNCTUATION_ONLY_REGEX = re.compile(r"^\s*[\?\.\-\/\!\:\;\,]+\s*$")
RAS_REGEX = re.compile(r"^\s*(?:r\.?a\.?s\.?|rien\s+[àa]\s+signaler)\s*$", re.IGNORECASE)
AMBIGUOUS_RESERVATION_REGEX = re.compile(r"^\s*[àa]\s+r[ée]fl[ée]chir(?:\s+encore\s+un\s+peu)?\.?\s*$", re.IGNORECASE)

# Reportable explicit epistemic / non-preference statements (preserved as observed statements, NO fabricated preference)
EXPLICIT_NO_OPINION_PATTERNS = [
    r"^\s*(?:aucun\s+avis|pas\s+d['’]avis|sans\s+avis|je\s+n['’]ai\s+(?:pas|aucun)\s+d['’]?avis).*$",
    r"^\s*no\s+opinion.*$",
    r"^\s*keine\s+meinung.*$",
    r"^\s*neutral\s+/\s+no\s+opinion.*$",
]
INSUFFICIENT_EXPERIENCE_PATTERNS = [
    r".*\bpas\s+(?:assez\s+)?d['’]exp[eé]rience\b.*",
    r".*\bmanque\s+d['’]exp[eé]rience\b.*",
    r".*\binsufficient\s+experience\b.*",
    r".*\bnot\s+enough\s+experience\b.*",
    r".*\bzu\s+wenig\s+erfahrung\b.*",
    r".*\bkeine\s+ausreichende\s+erfahrung\b.*",
]
INSUFFICIENT_INFO_PATTERNS = [
    r"^\s*(?:je\s+)?ne\s+sais\s+pas\.?\s*$",
    r".*\bpas\s+assez\s+d['’]informations?\b.*",
    r".*\bmanque\s+d['’]informations?\b.*",
    r".*\binsufficient\s+information\b.*",
    r".*\bnot\s+enough\s+information\b.*",
    r"^\s*weiß\s+nicht\.?\s*$",
    r"^\s*weiss\s+nicht\.?\s*$",
    r".*\bnicht\s+genügend\s+informationen\b.*",
    r".*\bmangels\s+informationen\b.*",
]

NO_OPINION_REGEX = re.compile("|".join(EXPLICIT_NO_OPINION_PATTERNS), re.IGNORECASE)
INSUFFICIENT_EXP_REGEX = re.compile("|".join(INSUFFICIENT_EXPERIENCE_PATTERNS), re.IGNORECASE)
INSUFFICIENT_INFO_REGEX = re.compile("|".join(INSUFFICIENT_INFO_PATTERNS), re.IGNORECASE)


def classify_response_status(
    text: Optional[str],
    agent01_missingness: Optional[MissingnessState | str] = None,
    agent01_response_status: Optional[ResponseStatusLabel | str] = None,
    *,
    question_id: str = "",
    text_supplied: Optional[bool] = None,
    has_usable_preference: Optional[bool] = None,
) -> Tuple[MissingnessState, ResponseEpistemicStatus]:
    """Consume Agent 01's missingness and epistemic-status fields without overwriting them.

    Reconciled contract:
    - Observed statements (`explicit_no_opinion`, `explicit_insufficient_experience`,
      `explicit_insufficient_information`, `ambiguous`) are kept strictly distinct from usable
      institutional preference (`has_usable_preference` / `OBSERVED_USABLE`).
    - Explicit no-opinion and insufficient-experience/information retain reportable status and
      preserve `MISSING_NON_SUBSTANTIVE` (no fabricated institutional preference).
    - Ambiguous responses retain `AMBIGUOUS` status for downstream qualitative interpretation.
    - Context-sensitive `"RAS"` is non-substantive (`no_additional_remarks`) in `Q14` and
      `ambiguous` in substantive primary questions (`Q01`-`Q13`).
    """
    m_state: Optional[MissingnessState]
    if agent01_missingness is not None:
        m_state = (
            agent01_missingness
            if isinstance(agent01_missingness, MissingnessState)
            else MissingnessState(str(agent01_missingness))
        )
    else:
        m_state = None

    a1_status = normalize_epistemic_status(agent01_response_status)

    # 1. If Agent 01 (or caller) explicitly declared canonical epistemic status, honor it first
    if a1_status is not None:
        if a1_status in BLANK_OR_NON_REPORTABLE_STATUSES:
            resolved_m = m_state or (
                MissingnessState.MISSING_RAW_BLANK
                if a1_status == ResponseEpistemicStatus.RAW_BLANK
                else MissingnessState.MISSING_NON_SUBSTANTIVE
            )
            return resolved_m, a1_status
        if a1_status in REPORTABLE_NO_PREFERENCE_STATUSES:
            resolved_m = m_state or MissingnessState.MISSING_NON_SUBSTANTIVE
            return resolved_m, a1_status
        if a1_status == ResponseEpistemicStatus.AMBIGUOUS:
            resolved_m = m_state or MissingnessState.AMBIGUOUS
            return resolved_m, ResponseEpistemicStatus.AMBIGUOUS
        if a1_status in USABLE_PREFERENCE_STATUSES:
            if text is None or not text.strip() or text_supplied is False:
                return MissingnessState.MISSING_RAW_BLANK, ResponseEpistemicStatus.RAW_BLANK
            resolved_m = m_state or MissingnessState.OBSERVED_USABLE
            return resolved_m, a1_status

    # 2. Check raw blank text
    if m_state == MissingnessState.MISSING_RAW_BLANK or text is None or text_supplied is False:
        return MissingnessState.MISSING_RAW_BLANK, ResponseEpistemicStatus.RAW_BLANK

    stripped = text.strip()
    if not stripped or stripped.lower() in {"nan", "null"}:
        return MissingnessState.MISSING_RAW_BLANK, ResponseEpistemicStatus.RAW_BLANK

    if PUNCTUATION_ONLY_REGEX.match(stripped):
        return (
            m_state or MissingnessState.MISSING_NON_SUBSTANTIVE,
            ResponseEpistemicStatus.PUNCTUATION_UNINTERPRETABLE,
        )

    # 3. Context-sensitive "RAS"
    if RAS_REGEX.match(stripped):
        if question_id == "Q14" or not question_id:
            return (
                m_state or MissingnessState.MISSING_NON_SUBSTANTIVE,
                ResponseEpistemicStatus.NO_ADDITIONAL_REMARKS,
            )
        return MissingnessState.AMBIGUOUS, ResponseEpistemicStatus.AMBIGUOUS

    # 4. Reportable explicit epistemic non-preference statements (checked even if m_state == MISSING_NON_SUBSTANTIVE)
    if NO_OPINION_REGEX.match(stripped):
        return (
            m_state or MissingnessState.MISSING_NON_SUBSTANTIVE,
            ResponseEpistemicStatus.EXPLICIT_NO_OPINION,
        )
    if INSUFFICIENT_EXP_REGEX.match(stripped) and len(stripped.split()) <= 18:
        return (
            m_state or MissingnessState.MISSING_NON_SUBSTANTIVE,
            ResponseEpistemicStatus.EXPLICIT_INSUFFICIENT_EXPERIENCE,
        )
    if INSUFFICIENT_INFO_REGEX.match(stripped) and len(stripped.split()) <= 18:
        return (
            m_state or MissingnessState.MISSING_NON_SUBSTANTIVE,
            ResponseEpistemicStatus.EXPLICIT_INSUFFICIENT_INFORMATION,
        )

    # 5. Respect upstream AMBIGUOUS or placeholder MISSING_NON_SUBSTANTIVE
    if m_state == MissingnessState.AMBIGUOUS or AMBIGUOUS_RESERVATION_REGEX.match(stripped):
        return MissingnessState.AMBIGUOUS, ResponseEpistemicStatus.AMBIGUOUS

    if m_state in {MissingnessState.MISSING_NON_SUBSTANTIVE, MissingnessState.UNOBSERVED_MISSING}:
        return m_state, ResponseEpistemicStatus.NO_ADDITIONAL_REMARKS

    if NON_SUBSTANTIVE_REGEX.match(stripped):
        return MissingnessState.MISSING_NON_SUBSTANTIVE, ResponseEpistemicStatus.NO_ADDITIONAL_REMARKS

    if has_usable_preference is False:
        return m_state or MissingnessState.AMBIGUOUS, ResponseEpistemicStatus.AMBIGUOUS

    return m_state or MissingnessState.OBSERVED_USABLE, ResponseEpistemicStatus.SUBSTANTIVE


def is_non_substantive_response(text: Optional[str]) -> Tuple[bool, MissingnessState]:
    """Detect whether a response lacks usable institutional preference."""
    m_state, _ = classify_response_status(text)
    is_missing = not m_state.is_usable()
    return is_missing, m_state


def repair_json_string_with_audit(raw_text: str) -> Tuple[Dict[str, Any], List[str]]:
    """Extract and mechanically repair JSON from raw LLM text ONLY when meaning is unchanged.

    Returns:
        (parsed_dict, list_of_repairs_applied)
    """
    repairs: List[str] = []
    cleaned = raw_text.strip()

    # Extract JSON inside code fences if present
    code_block_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
    if code_block_match:
        cleaned = code_block_match.group(1).strip()
        repairs.append("stripped_markdown_code_fence")
    else:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            if start > 0 or end < len(cleaned) - 1:
                repairs.append("stripped_non_json_prose_wrapper")
            cleaned = cleaned[start : end + 1]

    # Attempt direct parse first
    try:
        return json.loads(cleaned), repairs
    except json.JSONDecodeError:
        pass

    # Mechanical syntax repair 1: trailing commas before } or ]
    repaired = re.sub(r",\s*([\]\}])", r"\1", cleaned)
    if repaired != cleaned:
        repairs.append("removed_trailing_commas")

    try:
        return json.loads(repaired), repairs
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Failed to parse or mechanically repair JSON from LLM response without altering meaning: {e}\n"
            f"Raw content snippet: {cleaned[:300]}"
        ) from e


def repair_json_string(raw_text: str) -> Dict[str, Any]:
    """Extract and mechanically repair a JSON object from raw LLM output text."""
    parsed, _ = repair_json_string_with_audit(raw_text)
    return parsed


def validate_and_repair_probabilities(
    dist: Dict[str, float],
    tolerance: float = 1e-4,
    is_percentage: Optional[bool] = None,
) -> Tuple[Dict[str, float], Optional[ProbabilityRepairRecord]]:
    """Strictly validate alternative probability distributions and record any mechanical repair.

    Enforces Repair Safety (Section 9):
    - Preserves raw values in ProbabilityRepairRecord.
    - Rejects negative, NaN, infinite, boolean, or non-numeric values.
    - Rejects arbitrary unnormalized scores (e.g., sum=0.3, sum=0.6, Likert scores like 4+2=6).
    - Converts percentages ONLY when the 0-100 scale is unambiguous (sum within [99.5, 100.5]
      and max(v) > 1.0, or is_percentage=True with sum near 100).
    - Allows micro floating-point rounding drift ONLY within [0.99, 1.01] and records the repair.
    """
    if not dist:
        return {}, None

    raw_snapshot: Dict[str, float] = {}
    for k, v in dist.items():
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise ValueError(f"Probability for alternative '{k}' must be numeric, got {type(v).__name__}: {v!r}")
        fv = float(v)
        if not math.isfinite(fv):
            raise ValueError(f"Probability for alternative '{k}' is non-finite: {v!r}")
        if fv < 0.0:
            raise ValueError(f"Probability for alternative '{k}' is negative: {fv}")
        raw_snapshot[k] = fv

    raw_sum = sum(raw_snapshot.values())

    # Check unambiguous percentage scale (e.g., {a: 70, b: 30}, sum ~ 100)
    max_val = max(raw_snapshot.values())
    unambiguous_pct = (
        (is_percentage is True and 99.5 <= raw_sum <= 100.5)
        or (is_percentage is None and 99.5 <= raw_sum <= 100.5 and max_val > 1.0)
    )
    if unambiguous_pct:
        scaled = {k: round(v / raw_sum, 6) for k, v in raw_snapshot.items()}
        record = ProbabilityRepairRecord(
            raw_values=raw_snapshot,
            repaired_values=scaled,
            repair_action="unambiguous_percentage_scaling",
            scale_detected="0_to_100_percentage",
            reason=f"Scaled unambiguous percentage distribution (raw sum={raw_sum:.4f}) to probability simplex.",
        )
        return scaled, record

    # Exact or within strict tolerance (1e-4)
    if abs(raw_sum - 1.0) <= tolerance:
        normalized = {k: round(v / raw_sum, 6) for k, v in raw_snapshot.items()} if raw_sum != 1.0 else dict(raw_snapshot)
        # Recompute exact sum check
        record = ProbabilityRepairRecord(
            raw_values=raw_snapshot,
            repaired_values=normalized,
            repair_action="none",
            scale_detected="0_to_1_probability_simplex",
            reason="Valid probability simplex within tolerance.",
        )
        return normalized, record

    # Micro floating-point rounding drift only (e.g., 0.333 + 0.333 + 0.333 = 0.999)
    if abs(raw_sum - 1.0) <= 0.01:
        normalized = {k: round(v / raw_sum, 6) for k, v in raw_snapshot.items()}
        record = ProbabilityRepairRecord(
            raw_values=raw_snapshot,
            repaired_values=normalized,
            repair_action="micro_drift_renormalization",
            scale_detected="0_to_1_probability_simplex_with_rounding_drift",
            reason=f"Renormalized minor rounding drift (raw sum={raw_sum:.6f}) to 1.0.",
        )
        return normalized, record

    # Reject materially invalid distributions or arbitrary scores (never silently normalize!)
    raise ValueError(
        f"Probability distribution rejected: sum={raw_sum:.6f} is materially invalid "
        f"(neither simplex 1.0 +- 0.01 nor unambiguous 0-100 percentage). Raw distribution: {raw_snapshot}"
    )


def validate_and_repair_simplex(
    dist: Dict[str, float],
    tolerance: float = 1e-4,
    auto_normalize: bool = True,
    is_percentage: Optional[bool] = None,
) -> Dict[str, float]:
    """Validate alternative probability simplex; rejects arbitrary unnormalized scores.

    Note: `auto_normalize` is retained only for signature compatibility; arbitrary sums
    outside micro-drift (+-0.01) or unambiguous 100% scale are always rejected.
    """
    repaired, _ = validate_and_repair_probabilities(
        dist=dist,
        tolerance=tolerance,
        is_percentage=is_percentage,
    )
    return repaired


def find_exact_char_offsets(
    raw_text: str,
    quote: str,
    expected_char_start: Optional[int] = None,
    sentence_index: Optional[int] = None,
    allow_ambiguous: bool = False,
) -> Tuple[int, int, str]:
    """Find exact 0-indexed character offsets (char_start, char_end) for a verbatim quote.

    Enforces Repair Safety:
    - NEVER repairs a quotation by inventing or paraphrasing source evidence.
    - Verifies: raw_text[char_start:char_end] == matched_substring.
    - Repeated identical quotations require unambiguous offset or sentence_index resolution
      unless `allow_ambiguous=True`.
    """
    if not quote or not quote.strip():
        raise ValueError("Cannot search for empty quote.")

    # Search exact substring matches first (verbatim without alteration)
    matches: List[Tuple[int, int]] = []
    search_quote = quote
    start_pos = 0
    while True:
        idx = raw_text.find(search_quote, start_pos)
        if idx == -1:
            break
        matches.append((idx, idx + len(search_quote)))
        start_pos = idx + 1

    # Fallback: stripped leading/trailing whitespace around the exact substring
    if not matches:
        stripped = quote.strip()
        if stripped:
            start_pos = 0
            while True:
                idx = raw_text.find(stripped, start_pos)
                if idx == -1:
                    break
                matches.append((idx, idx + len(stripped)))
                start_pos = idx + 1

    # Fallback: flexible internal whitespace regex (matching exact characters in raw_text)
    if not matches:
        normalized_quote = " ".join(quote.strip().split())
        pattern_escaped = re.escape(normalized_quote).replace(r"\ ", r"\s+")
        for m in re.finditer(pattern_escaped, raw_text):
            matches.append((m.start(), m.end()))

    if not matches:
        raise ValueError(
            f"Verbatim quote '{quote[:80]}...' not found in raw response (paraphrasing/invention forbidden)."
        )

    if len(matches) == 1:
        s, e = matches[0]
        return s, e, raw_text[s:e]

    # Multiple identical occurrences found: require unambiguous resolution
    if expected_char_start is not None:
        for s, e in matches:
            if s == expected_char_start:
                return s, e, raw_text[s:e]
        raise AmbiguousQuoteOffsetError(
            f"Repeated quote '{quote[:50]}' has {len(matches)} occurrences and none start at expected_char_start={expected_char_start}."
        )

    if sentence_index is not None:
        # Compute sentence spans and find unique occurrence inside that sentence
        sent_matches: List[Tuple[int, int]] = []
        sent_spans = [(m.start(), m.end()) for m in re.finditer(r"[^.!?\n]+[.!?\n]*", raw_text)]
        if 0 <= sentence_index < len(sent_spans):
            s_lo, s_hi = sent_spans[sentence_index]
            sent_matches = [(s, e) for (s, e) in matches if s >= s_lo and e <= s_hi]
        if len(sent_matches) == 1:
            s, e = sent_matches[0]
            return s, e, raw_text[s:e]

    if allow_ambiguous:
        s, e = matches[0]
        return s, e, raw_text[s:e]

    raise AmbiguousQuoteOffsetError(
        f"Ambiguous repeated quotation: '{quote[:60]}' occurs {len(matches)} times at offsets {matches}. "
        "Provide expected_char_start or sentence_index for unambiguous offset resolution."
    )


def enforce_economic_goods_policy(
    subtopics: List[Dict[str, Any]],
    policy: str,
) -> List[Dict[str, Any]]:
    """Evaluate subtopic-level economic goods applicability.

    Section 7 Rule:
    - Question-level policy guides coding as a prior, NEVER overriding concrete subtopic evidence.
    - If a subtopic explicitly declares `goods_assessment` with `goods_applicability='APPLICABLE'`
      and a valid `applicability_domain` (`allocation`, `access`, `ownership`, `financing`,
      `risk`, `decision_rights`), preserve that evidence-driven classification even on a
      perception-framed question (marking `question_frame_override_applied=True`).
    - Conversely, if `goods_applicability='NOT_APPLICABLE'` (e.g. perception-only subtopic in
      an allocation question), enforce `proposed_economic_good_class='NOT_APPLICABLE'`.
    - When no explicit subtopic `goods_assessment` is provided, fall back to question-level `policy`.
    """
    allowed = {e.value for e in EconomicGoodClass if e != EconomicGoodClass.NOT_APPLICABLE}
    valid_domains = {"allocation", "access", "ownership", "financing", "risk", "decision_rights"}
    enforced: List[Dict[str, Any]] = []

    for st in subtopics:
        item = dict(st)
        ga = item.get("goods_assessment")
        cls_val = item.get("proposed_economic_good_class")

        if isinstance(ga, SubtopicGoodsAssessment):
            ga_dict = ga.model_dump()
        elif isinstance(ga, dict):
            ga_dict = dict(ga)
        else:
            ga_dict = None

        if ga_dict is not None:
            app = ga_dict.get("goods_applicability", "NOT_APPLICABLE")
            domain = ga_dict.get("applicability_domain")
            if app == "APPLICABLE" and domain in valid_domains:
                if policy == "DISABLED":
                    ga_dict["question_frame_override_applied"] = True
                if cls_val is not None and str(cls_val).lower() in allowed:
                    item["proposed_economic_good_class"] = str(cls_val).lower()
                else:
                    # Check alternative_good_classes
                    alt_classes = ga_dict.get("alternative_good_classes") or {}
                    valid_alts = [v.lower() for v in alt_classes.values() if str(v).lower() in allowed]
                    item["proposed_economic_good_class"] = valid_alts[0] if valid_alts else "NOT_APPLICABLE"
                item["goods_assessment"] = ga_dict
            else:
                if policy == "ENABLED":
                    ga_dict["question_frame_override_applied"] = True
                ga_dict["goods_applicability"] = "NOT_APPLICABLE"
                item["proposed_economic_good_class"] = "NOT_APPLICABLE"
                item["goods_assessment"] = ga_dict
        else:
            # No explicit subtopic-level assessment provided: follow question-level prior
            if policy == "DISABLED":
                item["proposed_economic_good_class"] = "NOT_APPLICABLE"
            elif policy in {"ENABLED", "CONDITIONAL"}:
                if cls_val is not None and str(cls_val).lower() in allowed:
                    item["proposed_economic_good_class"] = str(cls_val).lower()
                else:
                    item["proposed_economic_good_class"] = "NOT_APPLICABLE"

        enforced.append(item)

    return enforced
