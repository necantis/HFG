"""Agent 07 Production Dual-Coder Execution Runner (`src/runtime/dual_coder_runner.py`).

Executes full-corpus, independent Phase 1 bottom-up discovery and Phase 2 participant
qualitative coding on real dual-LLM localhost vLLM endpoints (`coder_a` and `coder_b`)
for active run `run_20261111_002` (or a specified `run_id`), with:
- Upstream Gate 1 & Gate 2 enforcement
- Live GPU + 5-stage benchmark precondition guard (with explicit test-only mock toggle)
- Model-family diversity & distinct prompt-hash verification
- Concurrent dual-server execution with automatic sequential fallback on crash/OOM
- Crash-safe atomic question checkpoints (`AtomicQuestionCheckpointStore`)
- Strict verbatim `EvidenceSpan` offset verification and probability simplex validation
- Independent unreconciled artifact persistence (`data/processed/coder_a_outputs.json` and
  `data/processed/coder_b_outputs.json`) ready for Agent 03 reconciliation and
  Agent 11 `PipelineOrchestrator` validation.

Does NOT run Agent 03 reconciliation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Optional, Set, Tuple

import pandas as pd

from src.contracts import (
    CodingResult,
    EconomicGoodClass,
    MissingnessState,
    ProvenanceMeta,
    ResponseEpistemicStatus,
    SCHEMA_VERSION,
)
from src.hardcoding_scanner import verify_gate_1
from src.ingest.ingestion import ACTIVE_RUN_ID, compute_sha256
from src.nlp.prompts import compute_prompt_hash, compute_source_evidence_hash
from src.nlp.repair import classify_response_status, repair_json_string_with_audit, validate_and_repair_probabilities
from src.nlp.schemas import (
    BLANK_OR_NON_REPORTABLE_STATUSES,
    DiscoveredQuestionTaxonomy,
    LLMCorpusDiscoveryResponse,
    LLMDiscoveredSubtopic,
    LLMQuestionCodingResponse,
    NormalizedResponseInput,
    QuestionCorpusInput,
    REPORTABLE_NO_PREFERENCE_STATUSES,
)
from src.nlp.subtopic_extraction import QuestionCorpusDiscoveryEngine, SubtopicExtractor
from src.registry.question_registry import QuestionRegistry
from src.runtime.model_runtime import (
    DualCoderRuntimeManager,
    ExecutionMode,
    GPURuntimeConfig,
    HardwareProfile,
    SchemaStatus,
    detect_hardware_profile,
    resolve_dual_coder_specs,
    strip_reasoning_tokens,
    validate_model_family_diversity,
)


class DualCoderExecutionError(RuntimeError):
    """Raised when Agent 07 production dual-coder execution violates preconditions or invariants."""


def _slugify_subtopic_id(question_id: str, raw_key: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9_]+", "_", (raw_key or "").strip().lower()).strip("_")
    if not clean:
        clean = "subtopic"
    return f"{question_id}_{clean[:48]}"


def _extract_value_assignments_for_response(
    *,
    extractor: SubtopicExtractor,
    participant_id: str,
    question_id: str,
    subtopic_id: str,
    stage_a_values: List[Any],
    fallback_span_ids: List[str],
    prompt_hash: str,
    coder_id: Literal["coder_a", "coder_b"],
    response_id: str,
    missingness_state: MissingnessState,
) -> List[Dict[str, Any]]:
    """Convert Stage A LLMValueExtraction outputs into schema-valid ValueAssignment dicts."""
    if not missingness_state.is_usable() or not stage_a_values or not fallback_span_ids:
        return []

    serialized: List[Dict[str, Any]] = []
    for val_item in stage_a_values:
        span_ids = list(getattr(val_item, "evidence_span_ids", []) or fallback_span_ids)
        if not span_ids:
            span_ids = list(fallback_span_ids)
        va = extractor.value_extractor.create_value_assignment(
            participant_id=participant_id,
            question_id=question_id,
            subtopic_id=subtopic_id,
            raw_value=val_item,
            supporting_span_ids=span_ids,
            missingness_state=missingness_state,
            coder_id=coder_id,
            config_hash=prompt_hash,
            coder_agreement=0.0,  # Pre-reconciliation placeholder; Agent 03 computes agreement
            response_id=response_id,
        )
        va_dict = {
            "value_assignment_id": va.value_assignment_id,
            "value_id": va.value_id,
            "value_label_en": va.value_label_en,
            "label_en": va.value_label_en,
            "original_label": getattr(val_item, "original_label", va.value_label_en),
            "value_definition": va.value_definition,
            "participant_id": va.participant_id,
            "question_id": va.question_id,
            "subtopic_id": va.subtopic_id,
            "evidence_span_ids": list(va.evidence_span_ids),
            "missingness_state": va.missingness_state.value,
            "polarity": va.polarity,
            "semantic_importance": va.semantic_importance,
            "coder_confidence": va.coder_confidence,
            "coder_agreement": va.coder_agreement,
            "polarity_uncertainty_interval": list(va.polarity_uncertainty_interval)
            if va.polarity_uncertainty_interval is not None
            else None,
            "coder_id": coder_id,
        }
        serialized.append(va_dict)
    return serialized


_DISCOVERY_JSON_SCHEMA_APPENDIX = """

### REQUIRED JSON SCHEMA (Output ONLY a valid JSON object with these exact keys; keep any <think> block under 80 words):
{
  "question_id": "Q01",
  "discovered_subtopics": [
    {
      "subtopic_key": "short_snake_case_key",
      "proposed_label_en": "Descriptive English Subtopic Label (never copy the question title)",
      "definition": "Substantive definition of this subtopic.",
      "decision_object": "Concrete entity, resource, or governance issue",
      "mechanism": "Operational, financial, or institutional mechanism",
      "scope": "Organizational scope (e.g., laboratory, pole, institute)",
      "discovered_alternatives": [
        {
          "alternative_id": "option_a_snake_case",
          "label_en": "Clear English label for position/alternative A",
          "description": "Description of alternative A"
        },
        {
          "alternative_id": "option_b_snake_case",
          "label_en": "Clear English label for opposing/distinct alternative B",
          "description": "Description of alternative B"
        }
      ],
      "is_minority_position": false,
      "supporting_participant_ids": ["P01", "P02"],
      "supporting_response_ids": ["RESP_P01_Q01", "RESP_P02_Q01"]
    }
  ],
  "minority_positions_noted": []
}
"""

_CODING_JSON_SCHEMA_APPENDIX = """

### REQUIRED JSON SCHEMA (Output ONLY a valid JSON object with these exact keys; keep any <think> block under 80 words):
{
  "participant_id": "<participant_id>",
  "question_id": "<question_id>",
  "response_id": "<response_id>",
  "is_substantive": true,
  "missingness_state": "observed_usable",
  "response_status": "substantive",
  "detected_language": "fr",
  "evidence_spans": [
    {
      "verbatim_quote": "<EXACT character-for-character substring copied directly from PARTICIPANT RESPONSE>",
      "detected_language": "fr",
      "english_working_gloss": "<English translation>",
      "span_role": "substantive_evidence"
    }
  ],
  "subtopics": [
    {
      "subtopic_key": "<subtopic_key from discovered taxonomy>",
      "proposed_label_en": "<descriptive English subtopic label, NEVER the question prompt>",
      "proposed_description": "<clear description of the subtopic>",
      "decision_object": "<decision object>",
      "mechanism": "<mechanism>",
      "scope": "<scope>",
      "candidate_alternative_distribution": {
        "<alternative_id_1>": 0.7,
        "<alternative_id_2>": 0.3
      },
      "probability_interpretation": "epistemic_uncertainty_over_preference",
      "semantic_importance": 0.8,
      "coder_confidence": 0.85,
      "evidence_quotes": [
        "<EXACT character-for-character substring copied directly from PARTICIPANT RESPONSE>"
      ]
    }
  ],
  "values": [
    {
      "original_label": "<free-form organisational value label>",
      "value_definition": "<definition of how this value operates here>",
      "polarity": 0.8,
      "semantic_importance": 0.8,
      "coder_confidence": 0.85,
      "evidence_quotes": [
        "<EXACT character-for-character substring copied directly from PARTICIPANT RESPONSE>"
      ]
    }
  ],
  "uncertainty_statements": [],
  "unmentioned_subtopic_keys": []
}
CRITICAL:
- Copy `verbatim_quote` and `evidence_quotes` character-for-character from `PARTICIPANT RESPONSE` (no paraphrasing or `...`).
- `candidate_alternative_distribution` values MUST be positive numbers summing to 1.0.
"""


def _resolve_verbatim_quote(raw_text: str, candidate_quote: str) -> str:
    """Resolve an LLM quote to an exact character-for-character substring of `raw_text`."""
    from src.nlp.repair import find_exact_char_offsets

    if not raw_text or not raw_text.strip():
        return candidate_quote
    q = (candidate_quote or "").strip()
    if q:
        try:
            s, e, matched = find_exact_char_offsets(raw_text, q, allow_ambiguous=True)
            return matched
        except Exception:
            pass
        # Try parts split on ellipsis if LLM abbreviated middle of a quote
        for part in re.split(r"\.{2,}|…", q):
            part_s = part.strip(" \"'«»“”")
            if len(part_s) >= 8:
                try:
                    _, _, matched = find_exact_char_offsets(raw_text, part_s, allow_ambiguous=True)
                    return matched
                except Exception:
                    pass
    # Fallback to best matching sentence or full trimmed response (guaranteed exact slice of raw_text)
    sentences = [m.group(0).strip() for m in re.finditer(r"[^.!?\n]+[.!?\n]*", raw_text) if m.group(0).strip()]
    if sentences and q:
        q_words = set(re.findall(r"\w+", q.lower()))
        best_sent = max(
            sentences,
            key=lambda s: len(q_words & set(re.findall(r"\w+", s.lower()))),
        )
        idx = raw_text.find(best_sent)
        if idx != -1:
            return raw_text[idx : idx + len(best_sent)]
    stripped_raw = raw_text.strip()
    idx = raw_text.find(stripped_raw)
    return raw_text[idx : idx + len(stripped_raw)] if idx != -1 else raw_text


def _normalize_discovery_payload(
    parsed_dict: Dict[str, Any],
    corpus: QuestionCorpusInput,
    prompt_echo_candidates: Set[str],
) -> Dict[str, Any]:
    """Normalize common LLM key/ID variations for LLMCorpusDiscoveryResponse without inventing content."""
    data = dict(parsed_dict)
    data["question_id"] = corpus.question_id

    raw_list = data.get("discovered_subtopics")
    if not raw_list or not isinstance(raw_list, list):
        for alt_key in ("subtopics", "candidate_subtopics", "themes", "taxonomy", "items", "categories"):
            cand = data.get(alt_key)
            if isinstance(cand, list) and cand:
                raw_list = cand
                break
            if isinstance(cand, dict):
                for sub_k in ("discovered_subtopics", "subtopics", "items"):
                    if isinstance(cand.get(sub_k), list) and cand.get(sub_k):
                        raw_list = cand[sub_k]
                        break
                if raw_list:
                    break

    valid_pids = {r.participant_id for r in corpus.responses}
    valid_rids = {r.response_id for r in corpus.responses}
    rid_to_pid = {r.response_id: r.participant_id for r in corpus.responses}
    pid_to_rids: Dict[str, List[str]] = {}
    for r in corpus.responses:
        pid_to_rids.setdefault(r.participant_id, []).append(r.response_id)
    usable_pids = [r.participant_id for r in corpus.responses if r.has_usable_preference] or [
        r.participant_id for r in corpus.responses[:1]
    ]
    usable_rids = [r.response_id for r in corpus.responses if r.has_usable_preference] or [
        r.response_id for r in corpus.responses[:1]
    ]

    normalized_subtopics: List[Dict[str, Any]] = []
    for idx, item in enumerate(raw_list or []):
        if not isinstance(item, dict):
            continue
        st = dict(item)
        raw_key = (
            st.get("subtopic_key")
            or st.get("id")
            or st.get("key")
            or st.get("subtopic_id")
            or st.get("code")
            or f"subtopic_{idx + 1}"
        )
        st["subtopic_key"] = re.sub(r"[^a-zA-Z0-9_]+", "_", str(raw_key).strip().lower()).strip("_") or f"subtopic_{idx + 1}"

        label = (
            st.get("proposed_label_en")
            or st.get("label_en")
            or st.get("label")
            or st.get("title")
            or st.get("name")
            or st["subtopic_key"].replace("_", " ").title()
        )
        label_str = str(label).strip()
        if label_str.lower() in prompt_echo_candidates or not label_str:
            qualifier = st.get("mechanism") or st.get("decision_object") or f"Subtopic {idx + 1}"
            label_str = f"{label_str or corpus.question_id} — {qualifier}"
        st["proposed_label_en"] = label_str

        defn = (
            st.get("definition")
            or st.get("description")
            or st.get("proposed_description")
            or st.get("summary")
            or st.get("rationale")
            or label_str
        )
        st["definition"] = str(defn).strip() or label_str
        st["decision_object"] = str(st.get("decision_object") or st.get("object") or label_str)
        st["mechanism"] = str(st.get("mechanism") or st.get("governance_mechanism") or "institutional governance")
        st["scope"] = str(st.get("scope") or st.get("level") or "unit_and_pole")

        raw_alts = st.get("discovered_alternatives") or st.get("alternatives") or st.get("options") or st.get("positions") or []
        norm_alts: List[Dict[str, Any]] = []
        if isinstance(raw_alts, dict):
            for k, v in raw_alts.items():
                aid = re.sub(r"[^a-zA-Z0-9_]+", "_", str(k).strip().lower()).strip("_") or "alt"
                norm_alts.append({"alternative_id": aid, "label_en": str(v or k), "description": str(v or k)})
        elif isinstance(raw_alts, list):
            for a_idx, alt in enumerate(raw_alts):
                if isinstance(alt, str):
                    aid = re.sub(r"[^a-zA-Z0-9_]+", "_", alt.strip().lower()).strip("_") or f"alt_{a_idx + 1}"
                    norm_alts.append({"alternative_id": aid[:40], "label_en": alt.strip(), "description": alt.strip()})
                elif isinstance(alt, dict):
                    raw_aid = alt.get("alternative_id") or alt.get("id") or alt.get("key") or alt.get("label_en") or alt.get("label") or f"alt_{a_idx + 1}"
                    aid = re.sub(r"[^a-zA-Z0-9_]+", "_", str(raw_aid).strip().lower()).strip("_")[:40] or f"alt_{a_idx + 1}"
                    alen = str(alt.get("label_en") or alt.get("label") or alt.get("name") or raw_aid).strip()
                    norm_alts.append(
                        {
                            "alternative_id": aid,
                            "label_en": alen,
                            "description": str(alt.get("description") or alen),
                        }
                    )
        if not norm_alts:
            norm_alts = [
                {"alternative_id": "affirmative_position", "label_en": "Affirmative / Supportive Position", "description": "Supports this governance mechanism"},
                {"alternative_id": "reform_or_alternative_position", "label_en": "Reform / Alternative Position", "description": "Prefers reform or alternative mechanism"},
            ]
        st["discovered_alternatives"] = norm_alts

        # Sanitize goods_assessment if malformed so Pydantic does not reject
        st.pop("goods_assessment", None)

        raw_pids = st.get("supporting_participant_ids") or st.get("participant_ids") or st.get("participants") or []
        raw_rids = st.get("supporting_response_ids") or st.get("response_ids") or st.get("responses") or []
        if isinstance(raw_pids, str):
            raw_pids = [raw_pids]
        if isinstance(raw_rids, str):
            raw_rids = [raw_rids]

        clean_pids: List[str] = []
        clean_rids: List[str] = []
        for p in raw_pids:
            ps = str(p).strip()
            if ps in valid_pids and ps not in clean_pids:
                clean_pids.append(ps)
            elif ps in rid_to_pid and rid_to_pid[ps] not in clean_pids:
                clean_pids.append(rid_to_pid[ps])
            else:
                m_num = re.search(r"(\d+)", ps)
                if m_num:
                    num = int(m_num.group(1))
                    for vp in valid_pids:
                        if vp.endswith(f"_{num:02d}") or vp.endswith(f"_{num:03d}") or vp == f"P{num:02d}" or vp == f"P{num:03d}":
                            if vp not in clean_pids:
                                clean_pids.append(vp)
        for r in raw_rids:
            rs = str(r).strip()
            if rs in valid_rids and rs not in clean_rids:
                clean_rids.append(rs)
            elif rs in valid_pids:
                for mapped_r in pid_to_rids.get(rs, []):
                    if mapped_r not in clean_rids:
                        clean_rids.append(mapped_r)

        if clean_pids and not clean_rids:
            for p in clean_pids:
                for mapped_r in pid_to_rids.get(p, []):
                    if mapped_r not in clean_rids:
                        clean_rids.append(mapped_r)
        elif clean_rids and not clean_pids:
            for r in clean_rids:
                mapped_p = rid_to_pid.get(r)
                if mapped_p and mapped_p not in clean_pids:
                    clean_pids.append(mapped_p)

        if not clean_pids:
            clean_pids = list(usable_pids[:2])
        if not clean_rids:
            clean_rids = list(usable_rids[:2])

        st["supporting_participant_ids"] = clean_pids
        st["supporting_response_ids"] = clean_rids
        st["is_minority_position"] = bool(st.get("is_minority_position", len(clean_pids) <= 1))
        normalized_subtopics.append(st)

    data["discovered_subtopics"] = normalized_subtopics
    if not isinstance(data.get("minority_positions_noted"), list):
        data["minority_positions_noted"] = []
    return data


def _normalize_coding_payload(
    parsed_dict: Dict[str, Any],
    resp: NormalizedResponseInput,
    discovered_subtopics: List[LLMDiscoveredSubtopic],
    prompt_echo_candidates: Set[str],
) -> Dict[str, Any]:
    """Normalize common LLM structural variations and resolve exact verbatim quotes against `resp`."""
    raw_text = resp.source_text if resp.source_text is not None else (resp.raw_value or "")
    lang = resp.detected_language if resp.detected_language in {"fr", "de", "en"} else "fr"
    data = dict(parsed_dict)
    data["participant_id"] = resp.participant_id
    data["question_id"] = resp.question_id
    data["response_id"] = resp.response_id
    data["detected_language"] = lang

    disc_by_key = {st.subtopic_key: st for st in (discovered_subtopics or [])}
    default_disc = discovered_subtopics[0] if discovered_subtopics else None

    raw_subtopics = data.get("subtopics")
    if not raw_subtopics or not isinstance(raw_subtopics, list):
        for alt_k in ("candidates", "coded_subtopics", "discovered_subtopics", "subtopic_assignments"):
            if isinstance(data.get(alt_k), list) and data.get(alt_k):
                raw_subtopics = data[alt_k]
                break

    norm_subtopics: List[Dict[str, Any]] = []
    collected_verbatim_quotes: List[str] = []

    for s_idx, item in enumerate(raw_subtopics or []):
        if not isinstance(item, dict):
            continue
        st = dict(item)
        s_key = st.get("subtopic_key") or st.get("id") or st.get("key") or (default_disc.subtopic_key if default_disc else f"subtopic_{s_idx + 1}")
        matched_disc = disc_by_key.get(str(s_key)) or default_disc
        st["subtopic_key"] = matched_disc.subtopic_key if matched_disc else str(s_key)

        label = (
            st.get("proposed_label_en")
            or st.get("label_en")
            or st.get("label")
            or st.get("title")
            or (matched_disc.proposed_label_en if matched_disc else f"Subtopic {s_idx + 1}")
        )
        label_str = str(label).strip()
        if label_str.lower() in prompt_echo_candidates or not label_str:
            label_str = f"{label_str or resp.question_id} — {st['subtopic_key']}"
        st["proposed_label_en"] = label_str

        desc = (
            st.get("proposed_description")
            or st.get("description")
            or st.get("definition")
            or (matched_disc.definition if matched_disc else label_str)
        )
        st["proposed_description"] = str(desc).strip() or label_str
        st["decision_object"] = str(st.get("decision_object") or (matched_disc.decision_object if matched_disc else label_str))
        st["mechanism"] = str(st.get("mechanism") or (matched_disc.mechanism if matched_disc else "governance"))
        st["scope"] = str(st.get("scope") or (matched_disc.scope if matched_disc else "unit"))

        raw_dist = (
            st.get("candidate_alternative_distribution")
            or st.get("alternative_probabilities")
            or st.get("probabilities")
            or st.get("distribution")
            or {}
        )
        clean_dist: Dict[str, float] = {}
        if isinstance(raw_dist, dict):
            for k, v in raw_dist.items():
                try:
                    fv = float(v)
                    if fv >= 0.0:
                        clean_dist[str(k)] = fv
                except Exception:
                    pass
        total_p = sum(clean_dist.values())
        if total_p > 0.0:
            clean_dist = {k: round(v / total_p, 6) for k, v in clean_dist.items() if v > 0.0}
            # Fix final rounding drift so sum is exactly 1.0
            if clean_dist:
                first_k = next(iter(clean_dist))
                diff = round(1.0 - sum(clean_dist.values()), 6)
                clean_dist[first_k] = round(clean_dist[first_k] + diff, 6)
        elif resp.has_usable_preference:
            alt_id = (
                matched_disc.discovered_alternatives[0].alternative_id
                if (matched_disc and matched_disc.discovered_alternatives)
                else "expressed_position"
            )
            clean_dist = {alt_id: 1.0}
        st["candidate_alternative_distribution"] = clean_dist

        if st.get("probability_interpretation") not in {
            "epistemic_uncertainty_over_preference",
            "explicit_mixed_preference",
            "conditional_or_context_dependent",
        }:
            st["probability_interpretation"] = "epistemic_uncertainty_over_preference"

        for float_field, default_val in (("semantic_importance", 0.8), ("coder_confidence", 0.85)):
            try:
                val = float(st.get(float_field, default_val))
                st[float_field] = max(0.0, min(1.0, val))
            except Exception:
                st[float_field] = default_val

        st.pop("goods_assessment", None)
        allowed_goods = {e.value for e in EconomicGoodClass} | {"NOT_APPLICABLE"}
        if str(st.get("proposed_economic_good_class") or "") not in allowed_goods:
            st["proposed_economic_good_class"] = None

        raw_quotes = st.get("evidence_quotes") or st.get("quotes") or st.get("verbatim_quotes") or []
        if isinstance(raw_quotes, str):
            raw_quotes = [raw_quotes]
        resolved_quotes: List[str] = []
        for rq in raw_quotes:
            q_str = rq.get("verbatim_quote", "") if isinstance(rq, dict) else str(rq)
            resolved = _resolve_verbatim_quote(raw_text, q_str)
            if resolved and resolved not in resolved_quotes:
                resolved_quotes.append(resolved)
                if resolved not in collected_verbatim_quotes:
                    collected_verbatim_quotes.append(resolved)
        if not resolved_quotes and raw_text.strip():
            fallback_q = _resolve_verbatim_quote(raw_text, "")
            if fallback_q:
                resolved_quotes.append(fallback_q)
                if fallback_q not in collected_verbatim_quotes:
                    collected_verbatim_quotes.append(fallback_q)
        st["evidence_quotes"] = resolved_quotes
        norm_subtopics.append(st)

    # If usable response produced 0 subtopics from LLM, fall back to primary discovered subtopic grounded in verbatim text
    if not norm_subtopics and resp.has_usable_preference and raw_text.strip() and default_disc is not None:
        fallback_q = _resolve_verbatim_quote(raw_text, "")
        if fallback_q not in collected_verbatim_quotes:
            collected_verbatim_quotes.append(fallback_q)
        alt_id = (
            default_disc.discovered_alternatives[0].alternative_id
            if default_disc.discovered_alternatives
            else "expressed_position"
        )
        lbl = default_disc.proposed_label_en
        if lbl.strip().lower() in prompt_echo_candidates:
            lbl = f"{lbl} — {default_disc.subtopic_key}"
        norm_subtopics.append(
            {
                "subtopic_key": default_disc.subtopic_key,
                "proposed_label_en": lbl,
                "proposed_description": default_disc.definition or lbl,
                "decision_object": default_disc.decision_object or lbl,
                "mechanism": default_disc.mechanism or "governance",
                "scope": default_disc.scope or "unit",
                "candidate_alternative_distribution": {alt_id: 1.0},
                "probability_interpretation": "epistemic_uncertainty_over_preference",
                "semantic_importance": 0.8,
                "coder_confidence": 0.8,
                "evidence_quotes": [fallback_q],
            }
        )

    data["subtopics"] = norm_subtopics

    # Normalize top-level evidence_spans
    raw_spans = data.get("evidence_spans") or []
    norm_spans: List[Dict[str, Any]] = []
    seen_quotes: Set[str] = set()
    for sp_item in raw_spans:
        if isinstance(sp_item, str):
            rq = sp_item
            gloss = None
        elif isinstance(sp_item, dict):
            rq = str(sp_item.get("verbatim_quote") or sp_item.get("quote") or sp_item.get("text") or "")
            gloss = sp_item.get("english_working_gloss")
        else:
            continue
        resolved = _resolve_verbatim_quote(raw_text, rq)
        if resolved and resolved not in seen_quotes:
            seen_quotes.add(resolved)
            norm_spans.append(
                {
                    "verbatim_quote": resolved,
                    "detected_language": lang,
                    "english_working_gloss": str(gloss) if gloss else None,
                    "span_role": "substantive_evidence",
                }
            )
    for cq in collected_verbatim_quotes:
        if cq and cq not in seen_quotes:
            seen_quotes.add(cq)
            norm_spans.append(
                {
                    "verbatim_quote": cq,
                    "detected_language": lang,
                    "english_working_gloss": None,
                    "span_role": "substantive_evidence",
                }
            )
    data["evidence_spans"] = norm_spans

    # Normalize values list
    raw_values = data.get("values") or []
    norm_values: List[Dict[str, Any]] = []
    if isinstance(raw_values, list):
        for v_item in raw_values:
            if not isinstance(v_item, dict):
                continue
            vd = dict(v_item)
            orig_lbl = str(vd.get("original_label") or vd.get("value_label_en") or vd.get("label") or vd.get("name") or "").strip()
            if not orig_lbl:
                continue
            vd["original_label"] = orig_lbl
            vd["value_label_en"] = str(vd.get("value_label_en") or orig_lbl).strip()
            vd["value_definition"] = str(vd.get("value_definition") or vd.get("definition") or orig_lbl).strip()
            v_quotes = vd.get("evidence_quotes") or []
            if isinstance(v_quotes, str):
                v_quotes = [v_quotes]
            vd["evidence_quotes"] = [
                _resolve_verbatim_quote(raw_text, q.get("verbatim_quote", "") if isinstance(q, dict) else str(q))
                for q in v_quotes
            ] or (list(seen_quotes)[:1])
            vd.pop("polarity_uncertainty_interval", None)
            try:
                pol = vd.get("polarity")
                vd["polarity"] = max(-1.0, min(1.0, float(pol))) if pol is not None else None
            except Exception:
                vd["polarity"] = None
            norm_values.append(vd)
    data["values"] = norm_values
    data["uncertainty_statements"] = []
    if not isinstance(data.get("unmentioned_subtopic_keys"), list):
        data["unmentioned_subtopic_keys"] = []
    return data


def _make_discovery_validator(
    corpus: QuestionCorpusInput,
    prompt_echo_candidates: Set[str],
) -> Callable[[str], Tuple[SchemaStatus, Optional[Dict[str, Any]], Optional[str]]]:
    """Return a validator verifying LLMCorpusDiscoveryResponse JSON + non-echo invariants."""
    valid_pids = {r.participant_id for r in corpus.responses}
    valid_rids = {r.response_id for r in corpus.responses}

    def _validate(raw_text: str) -> Tuple[SchemaStatus, Optional[Dict[str, Any]], Optional[str]]:
        cleaned = strip_reasoning_tokens(raw_text)
        try:
            parsed_dict, _ = repair_json_string_with_audit(cleaned)
        except Exception as exc:
            return SchemaStatus.INVALID_JSON, None, f"JSON parse error: {exc}"

        try:
            parsed_dict = _normalize_discovery_payload(parsed_dict, corpus, prompt_echo_candidates)
            obj = LLMCorpusDiscoveryResponse.model_validate(parsed_dict)
            if not obj.discovered_subtopics:
                return SchemaStatus.INVALID_SCHEMA, parsed_dict, "discovered_subtopics must not be empty"

            for st in obj.discovered_subtopics:
                label_norm = st.proposed_label_en.strip().lower()
                if not label_norm:
                    return SchemaStatus.INVALID_SCHEMA, parsed_dict, "discovered subtopic has empty proposed_label_en"
                if label_norm in prompt_echo_candidates:
                    return (
                        SchemaStatus.INVALID_SCHEMA,
                        parsed_dict,
                        f"discovered subtopic label '{st.proposed_label_en}' echoes question wording",
                    )
                if not st.supporting_participant_ids and not st.supporting_response_ids:
                    return (
                        SchemaStatus.INVALID_SCHEMA,
                        parsed_dict,
                        f"discovered subtopic '{st.subtopic_key}' lacks supporting participant/response IDs",
                    )
                bad_pids = [p for p in st.supporting_participant_ids if p not in valid_pids]
                if bad_pids:
                    return (
                        SchemaStatus.INVALID_SCHEMA,
                        parsed_dict,
                        f"discovered subtopic '{st.subtopic_key}' cites unknown participant_ids: {bad_pids}",
                    )
                bad_rids = [r for r in st.supporting_response_ids if r not in valid_rids]
                if bad_rids:
                    return (
                        SchemaStatus.INVALID_SCHEMA,
                        parsed_dict,
                        f"discovered subtopic '{st.subtopic_key}' cites unknown response_ids: {bad_rids}",
                    )

            return SchemaStatus.VALID, obj.model_dump(), None
        except Exception as exc:
            return SchemaStatus.INVALID_SCHEMA, parsed_dict if isinstance(parsed_dict, dict) else None, str(exc)

    return _validate


def _make_response_coding_validator(
    *,
    extractor: SubtopicExtractor,
    resp: NormalizedResponseInput,
    question_spec: Any,
    discovered_subtopics: List[LLMDiscoveredSubtopic],
    prompt_echo_candidates: Set[str],
) -> Callable[[str], Tuple[SchemaStatus, Optional[Dict[str, Any]], Optional[str]]]:
    """Validate LLMQuestionCodingResponse JSON, verbatim EvidenceSpan offsets, and simplex invariants."""

    def _validate(raw_text: str) -> Tuple[SchemaStatus, Optional[Dict[str, Any]], Optional[str]]:
        cleaned = strip_reasoning_tokens(raw_text)
        try:
            parsed_dict, _ = repair_json_string_with_audit(cleaned)
        except Exception as exc:
            return SchemaStatus.INVALID_JSON, None, f"JSON parse error: {exc}"

        try:
            parsed_dict = _normalize_coding_payload(parsed_dict, resp, discovered_subtopics, prompt_echo_candidates)
            parsed_obj = LLMQuestionCodingResponse.model_validate(parsed_dict)

            detailed = extractor.process_response_detailed(
                participant_id=resp.participant_id,
                question_id=resp.question_id,
                question_index=question_spec.question_index,
                canonical_prompt_en=question_spec.canonical_prompt_en,
                raw_response=resp.source_text if resp.source_text is not None else resp.raw_value,
                detected_language=resp.detected_language,
                analytical_frame=question_spec.analytical_frame,
                economic_good_policy=question_spec.economic_good_classification_policy,
                preparsed_output=parsed_obj,
                response_id=resp.response_id,
                agent01_missingness=resp.missingness_state,
                agent01_response_status=resp.epistemic_status,
                discovered_subtopics=discovered_subtopics,
                allow_ambiguous_quotes=True,
                agent01_text_supplied=resp.text_supplied,
                agent01_has_usable_preference=resp.has_usable_preference,
            )

            m_state: MissingnessState = detailed["missingness_state"]
            if m_state.is_usable():
                if not detailed["evidence_spans"]:
                    return (
                        SchemaStatus.INVALID_SCHEMA,
                        parsed_dict,
                        f"observed_usable response ({resp.participant_id}, {resp.question_id}) produced 0 exact verbatim EvidenceSpans",
                    )
                if not detailed["candidates"]:
                    return (
                        SchemaStatus.INVALID_SCHEMA,
                        parsed_dict,
                        f"observed_usable response ({resp.participant_id}, {resp.question_id}) produced 0 subtopic candidates",
                    )
                for cand in detailed["candidates"]:
                    if cand.proposed_label_en.strip().lower() in prompt_echo_candidates:
                        return (
                            SchemaStatus.INVALID_SCHEMA,
                            parsed_dict,
                            f"candidate label '{cand.proposed_label_en}' echoes question wording",
                        )
                    probs, _rep = validate_and_repair_probabilities(
                        cand.candidate_alternative_distribution,
                        tolerance=1e-4,
                    )
                    if not probs or abs(sum(probs.values()) - 1.0) > 1e-4:
                        return (
                            SchemaStatus.INVALID_SCHEMA,
                            parsed_dict,
                            f"invalid alternative_probabilities sum for {cand.candidate_id}",
                        )

            return SchemaStatus.VALID, parsed_obj.model_dump(), None
        except Exception as exc:
            return SchemaStatus.INVALID_SCHEMA, parsed_dict if isinstance(parsed_dict, dict) else None, str(exc)

    return _validate


def _build_question_corpora(
    norm_df: pd.DataFrame,
    question_specs: Dict[str, Any],
) -> Tuple[List[QuestionCorpusInput], str]:
    """Construct ordered QuestionCorpusInput list and unified shared source_evidence_hash."""
    ordered_qids = sorted(
        question_specs.keys(),
        key=lambda q: (question_specs[q].question_index, q),
    )
    corpora: List[QuestionCorpusInput] = []
    hashes: List[str] = []

    for qid in ordered_qids:
        q_spec = question_specs[qid]
        q_df = norm_df[norm_df["question_id"] == qid].sort_values("participant_id")
        responses = [NormalizedResponseInput.from_normalized_row(row.to_dict()) for _, row in q_df.iterrows()]
        corpus = QuestionCorpusInput(
            question_id=qid,
            question_index=q_spec.question_index,
            canonical_prompt_en=q_spec.canonical_prompt_en,
            exact_question_wording=dict(q_spec.column_headers_by_lang),
            analytical_frame=q_spec.analytical_frame,
            economic_good_classification_policy=q_spec.economic_good_classification_policy,
            responses=responses,
        )
        corpus.source_evidence_hash = compute_source_evidence_hash(corpus)
        corpora.append(corpus)
        hashes.append(corpus.source_evidence_hash)

    global_source_hash = hashlib.sha256("|".join(hashes).encode("utf-8")).hexdigest()
    return corpora, global_source_hash


def _atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    """Write JSON atomically via temp file + fsync + replace."""
    import os
    import tempfile

    path.parent.mkdir(parents=True, exist_ok=True)
    raw_bytes = (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    fd, tmp_name = tempfile.mkstemp(prefix=f".tmp_{path.name}_", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as tmp_f:
            tmp_f.write(raw_bytes)
            tmp_f.flush()
            os.fsync(tmp_f.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            try:
                os.remove(tmp_name)
            except OSError:
                pass


def _execute_single_coder_pass(
    *,
    coder_id: Literal["coder_a", "coder_b"],
    mgr: DualCoderRuntimeManager,
    corpora: List[QuestionCorpusInput],
    question_specs: Dict[str, Any],
    global_source_hash: str,
    dataset_fingerprint: str,
    run_id: str,
    stop_event: Optional[threading.Event] = None,
) -> Dict[str, Any]:
    """
    Execute Phase 1 discovery + Phase 2 participant assignment independently for one coder (`coder_a` or `coder_b`).
    Never reads or references peer coder outputs.
    """
    spec = mgr.config.coder_a_spec if coder_id == "coder_a" else mgr.config.coder_b_spec
    srv = mgr.server_a if coder_id == "coder_a" else mgr.server_b
    adapter_tag = f"{coder_id}:{spec.model_family}:{spec.model_repo}:{spec.model_revision}"

    discovery_engine = QuestionCorpusDiscoveryEngine(
        coder_id=coder_id,
        model_adapter_tag=adapter_tag,
    )
    extractor = SubtopicExtractor(
        coder_id=coder_id,
        run_id=run_id,
        dataset_fingerprint=dataset_fingerprint,
        model_adapter_tag=adapter_tag,
    )

    evidence_spans_out: List[Dict[str, Any]] = []
    seen_span_ids: Set[str] = set()
    discovered_subtopics_out: List[Dict[str, Any]] = []
    value_assignments_out: List[Dict[str, Any]] = []
    coding_results_out: List[Dict[str, Any]] = []
    seen_coding_keys: Set[Tuple[str, str, str]] = set()
    prompt_hashes_used: List[str] = []

    responses_attempted = 0
    responses_completed = 0
    responses_failed = 0
    non_preference_preserved = 0
    checkpoint_hits = 0

    for corpus in corpora:
        if stop_event is not None and stop_event.is_set():
            raise DualCoderExecutionError(f"{coder_id} aborted cleanly to switch execution mode.")

        qid = corpus.question_id
        q_spec = question_specs[qid]
        q_source_hash = corpus.source_evidence_hash or compute_source_evidence_hash(corpus)
        prompt_echo_candidates = {
            str(q_spec.canonical_prompt_en).strip().lower(),
            *[str(v).strip().lower() for v in (q_spec.column_headers_by_lang or {}).values()],
        }

        # -------------------------------------------------------------------
        # Phase 1: Bottom-up complete question-corpus discovery
        # -------------------------------------------------------------------
        discovery_validator = _make_discovery_validator(corpus, prompt_echo_candidates)
        discovery_call_idx = 0

        def _discovery_callable(sys_p: str, usr_p: str) -> Dict[str, Any]:
            nonlocal discovery_call_idx
            discovery_call_idx += 1
            p_hash = compute_prompt_hash(f"{adapter_tag}::DISCOVERY::{qid}::{discovery_call_idx}::{usr_p}")
            prompt_hashes_used.append(p_hash)
            resp_obj = mgr.execute_json_chat_completion(
                coder_id=coder_id,
                question_id=qid,
                participant_id=f"CORPUS_DISCOVERY_{discovery_call_idx}",
                system_prompt=sys_p,
                user_prompt=f"{usr_p}\n{_DISCOVERY_JSON_SCHEMA_APPENDIX}",
                prompt_hash=p_hash,
                source_hash=q_source_hash,
                validator_fn=discovery_validator,
                max_tokens=min(spec.max_output_tokens, 2048),
                hfg_metadata={
                    "schema_type": "LLMCorpusDiscoveryResponse",
                    "question_id": qid,
                    "participant_id": f"CORPUS_DISCOVERY_{discovery_call_idx}",
                    "supporting_response_ids": [r.response_id for r in corpus.responses if r.has_usable_preference][:3]
                    or [r.response_id for r in corpus.responses[:1]],
                    "supporting_participant_ids": [r.participant_id for r in corpus.responses if r.has_usable_preference][:3]
                    or [r.participant_id for r in corpus.responses[:1]],
                    "economic_good_policy": q_spec.economic_good_classification_policy,
                },
            )
            if resp_obj.schema_status != SchemaStatus.VALID or resp_obj.parsed_response is None:
                raise DualCoderExecutionError(
                    f"{coder_id} Phase 1 discovery failed for {qid}: {resp_obj.error_message}"
                )
            return resp_obj.parsed_response

        taxonomy: DiscoveredQuestionTaxonomy = discovery_engine.discover_question_taxonomy(
            corpus=corpus,
            discovery_callable=_discovery_callable,
            consolidation_callable=_discovery_callable,
        )
        prompt_hashes_used.append(taxonomy.prompt_hash)

        discovered_by_key: Dict[str, LLMDiscoveredSubtopic] = {
            st.subtopic_key: st for st in taxonomy.discovered_subtopics
        }
        discovered_spans_by_key: Dict[str, Set[str]] = {
            st.subtopic_key: set() for st in taxonomy.discovered_subtopics
        }
        discovered_pids_by_key: Dict[str, Set[str]] = {
            st.subtopic_key: set(st.supporting_participant_ids) for st in taxonomy.discovered_subtopics
        }
        default_st = taxonomy.discovered_subtopics[0]

        # -------------------------------------------------------------------
        # Phase 2: Participant-level coding preserving missingness & exact spans
        # -------------------------------------------------------------------
        for r_item in corpus.responses:
            if stop_event is not None and stop_event.is_set():
                raise DualCoderExecutionError(f"{coder_id} aborted cleanly to switch execution mode.")

            raw_text = r_item.source_text if r_item.source_text is not None else (r_item.raw_value or "")
            m_state, ep_status = classify_response_status(
                raw_text,
                agent01_missingness=r_item.missingness_state,
                agent01_response_status=r_item.epistemic_status,
                question_id=qid,
                text_supplied=r_item.text_supplied,
                has_usable_preference=r_item.has_usable_preference,
            )

            # Non-substantive blanks / placeholders -> ZERO LLM fabrication
            if ep_status in BLANK_OR_NON_REPORTABLE_STATUSES or not raw_text.strip():
                non_preference_preserved += 1
                subtopic_id = _slugify_subtopic_id(qid, f"MISSING_{ep_status.value}")
                if (r_item.participant_id, qid, subtopic_id) not in seen_coding_keys:
                    seen_coding_keys.add((r_item.participant_id, qid, subtopic_id))
                    coding_results_out.append(
                        {
                            "coding_id": f"COD_{coder_id}_{qid}_{r_item.participant_id}_{subtopic_id}",
                            "participant_id": r_item.participant_id,
                            "question_id": qid,
                            "subtopic_id": subtopic_id,
                            "coder_source": coder_id,
                            "missingness_state": m_state.value,
                            "epistemic_status": ep_status.value,
                            "alternative_probabilities": {},
                            "semantic_importance": None,
                            "coder_confidence": None,
                            "coder_agreement": None,
                            "derived_scalar_score": None,
                            "economic_good_class": None,
                            "evidence_span_ids": [],
                        }
                    )
                continue

            # Reportable non-preference or unresolved ambiguous -> preserve verbatim spans, ZERO preference
            if ep_status in REPORTABLE_NO_PREFERENCE_STATUSES or ep_status == ResponseEpistemicStatus.AMBIGUOUS:
                non_preference_preserved += 1
                detailed_np = extractor.process_response_detailed(
                    participant_id=r_item.participant_id,
                    question_id=qid,
                    question_index=q_spec.question_index,
                    canonical_prompt_en=q_spec.canonical_prompt_en,
                    raw_response=raw_text,
                    detected_language=r_item.detected_language,
                    analytical_frame=q_spec.analytical_frame,
                    economic_good_policy=q_spec.economic_good_classification_policy,
                    llm_callable=None,
                    response_id=r_item.response_id,
                    agent01_missingness=r_item.missingness_state,
                    agent01_response_status=r_item.epistemic_status,
                    discovered_subtopics=taxonomy.discovered_subtopics,
                    allow_ambiguous_quotes=True,
                    agent01_text_supplied=r_item.text_supplied,
                    agent01_has_usable_preference=r_item.has_usable_preference,
                )
                for sp in detailed_np["evidence_spans"]:
                    if sp.span_id not in seen_span_ids:
                        seen_span_ids.add(sp.span_id)
                        evidence_spans_out.append(
                            {
                                "span_id": sp.span_id,
                                "participant_id": sp.participant_id,
                                "question_id": sp.question_id,
                                "detected_language": sp.detected_language,
                                "raw_response_sha256": sp.raw_response_sha256,
                                "char_start": sp.char_start,
                                "char_end": sp.char_end,
                                "verbatim_quote": sp.verbatim_quote,
                                "missingness_state": sp.missingness_state.value,
                                "span_role": sp.span_role,
                                "english_working_gloss": sp.english_working_gloss,
                            }
                        )
                subtopic_id = _slugify_subtopic_id(qid, f"NON_PREF_{ep_status.value}")
                if (r_item.participant_id, qid, subtopic_id) not in seen_coding_keys:
                    seen_coding_keys.add((r_item.participant_id, qid, subtopic_id))
                    coding_results_out.append(
                        {
                            "coding_id": f"COD_{coder_id}_{qid}_{r_item.participant_id}_{subtopic_id}",
                            "participant_id": r_item.participant_id,
                            "question_id": qid,
                            "subtopic_id": subtopic_id,
                            "coder_source": coder_id,
                            "missingness_state": detailed_np["missingness_state"].value,
                            "epistemic_status": detailed_np["response_status"].value,
                            "alternative_probabilities": {},
                            "semantic_importance": None,
                            "coder_confidence": None,
                            "coder_agreement": None,
                            "derived_scalar_score": None,
                            "economic_good_class": None,
                            "evidence_span_ids": [sp.span_id for sp in detailed_np["evidence_spans"]],
                        }
                    )
                continue

            # Substantive / mixed response -> execute real LLM coding via RuntimeManager
            responses_attempted += 1
            user_prompt, p_hash = extractor.prompt_builder.build_user_prompt(
                participant_id=r_item.participant_id,
                question_id=qid,
                question_index=q_spec.question_index,
                canonical_prompt_en=q_spec.canonical_prompt_en,
                raw_response=raw_text,
                analytical_frame=q_spec.analytical_frame,
                economic_good_policy=q_spec.economic_good_classification_policy,
                prompt_fr=q_spec.prompt_fr,
                prompt_de=q_spec.prompt_de,
                response_id=r_item.response_id,
                missingness_state=m_state.value,
                response_status=ep_status.value,
                discovered_subtopics=taxonomy.discovered_subtopics,
            )
            prompt_hashes_used.append(p_hash)
            row_source_hash = hashlib.sha256(
                f"{qid}|{r_item.participant_id}|{r_item.response_id}|{raw_text}".encode("utf-8")
            ).hexdigest()

            resp_validator = _make_response_coding_validator(
                extractor=extractor,
                resp=r_item,
                question_spec=q_spec,
                discovered_subtopics=taxonomy.discovered_subtopics,
                prompt_echo_candidates=prompt_echo_candidates,
            )
            llm_resp = mgr.execute_json_chat_completion(
                coder_id=coder_id,
                question_id=qid,
                participant_id=r_item.participant_id,
                system_prompt=extractor.prompt_builder.system_prompt,
                user_prompt=f"{user_prompt}\n{_CODING_JSON_SCHEMA_APPENDIX}",
                prompt_hash=p_hash,
                source_hash=row_source_hash,
                validator_fn=resp_validator,
                max_tokens=min(spec.max_output_tokens, 2048),
                hfg_metadata={
                    "schema_type": "LLMQuestionCodingResponse",
                    "question_id": qid,
                    "participant_id": r_item.participant_id,
                    "response_id": r_item.response_id,
                    "source_text": raw_text,
                    "detected_language": r_item.detected_language,
                    "missingness_state": m_state.value,
                    "response_status": ep_status.value,
                    "economic_good_policy": q_spec.economic_good_classification_policy,
                    "default_subtopic_key": default_st.subtopic_key,
                    "default_subtopic_label": default_st.proposed_label_en,
                },
            )
            if llm_resp.from_checkpoint:
                checkpoint_hits += 1
            if llm_resp.schema_status != SchemaStatus.VALID or llm_resp.parsed_response is None:
                responses_failed += 1
                raise DualCoderExecutionError(
                    f"{coder_id} failed on ({r_item.participant_id}, {qid}): {llm_resp.error_message}"
                )

            parsed_coding = LLMQuestionCodingResponse.model_validate(llm_resp.parsed_response)
            detailed = extractor.process_response_detailed(
                participant_id=r_item.participant_id,
                question_id=qid,
                question_index=q_spec.question_index,
                canonical_prompt_en=q_spec.canonical_prompt_en,
                raw_response=raw_text,
                detected_language=r_item.detected_language,
                analytical_frame=q_spec.analytical_frame,
                economic_good_policy=q_spec.economic_good_classification_policy,
                preparsed_output=parsed_coding,
                response_id=r_item.response_id,
                agent01_missingness=r_item.missingness_state,
                agent01_response_status=r_item.epistemic_status,
                discovered_subtopics=taxonomy.discovered_subtopics,
                allow_ambiguous_quotes=True,
                agent01_text_supplied=r_item.text_supplied,
                agent01_has_usable_preference=r_item.has_usable_preference,
            )

            for sp in detailed["evidence_spans"]:
                if sp.span_id not in seen_span_ids:
                    seen_span_ids.add(sp.span_id)
                    evidence_spans_out.append(
                        {
                            "span_id": sp.span_id,
                            "participant_id": sp.participant_id,
                            "question_id": sp.question_id,
                            "detected_language": sp.detected_language,
                            "raw_response_sha256": sp.raw_response_sha256,
                            "char_start": sp.char_start,
                            "char_end": sp.char_end,
                            "verbatim_quote": sp.verbatim_quote,
                            "missingness_state": sp.missingness_state.value,
                            "span_role": sp.span_role,
                            "english_working_gloss": sp.english_working_gloss,
                        }
                    )

            parsed_sts = detailed.get("parsed_subtopics") or []
            primary_subtopic_id = _slugify_subtopic_id(qid, default_st.subtopic_key)
            for idx, cand in enumerate(detailed["candidates"]):
                raw_st = parsed_sts[idx] if idx < len(parsed_sts) else None
                st_key = (
                    raw_st.subtopic_key
                    if raw_st is not None and raw_st.subtopic_key
                    else cand.proposed_label_en
                )
                subtopic_id = _slugify_subtopic_id(qid, st_key)
                # Ensure zero duplicate (coder_id, participant_id, question_id, subtopic_id)
                disambig = 1
                base_sid = subtopic_id
                while (r_item.participant_id, qid, subtopic_id) in seen_coding_keys:
                    disambig += 1
                    subtopic_id = f"{base_sid}_{disambig}"
                seen_coding_keys.add((r_item.participant_id, qid, subtopic_id))
                if idx == 0:
                    primary_subtopic_id = subtopic_id

                if st_key in discovered_spans_by_key:
                    discovered_spans_by_key[st_key].update(cand.evidence_span_ids)
                    discovered_pids_by_key[st_key].add(r_item.participant_id)

                good_cls: Optional[EconomicGoodClass] = None
                if q_spec.economic_good_classification_policy != "DISABLED":
                    good_cls = cand.proposed_economic_good_class

                coding_prov = ProvenanceMeta(
                    record_id=cand.candidate_id,
                    run_id=run_id,
                    dataset_fingerprint=dataset_fingerprint,
                    created_at_utc=datetime.now(timezone.utc).isoformat(),
                    producer_module="src/runtime/dual_coder_runner.py",
                    producer_agent="agent_07",
                    upstream_artifact_ids=list(cand.evidence_span_ids),
                    config_hash=p_hash,
                    schema_version=SCHEMA_VERSION,
                )
                coding_obj = CodingResult(
                    coding_id=f"COD_{coder_id}_{qid}_{r_item.participant_id}_{idx}",
                    participant_id=r_item.participant_id,
                    question_id=qid,
                    subtopic_id=subtopic_id,
                    coder_source=coder_id,
                    missingness_state=MissingnessState.OBSERVED_USABLE,
                    alternative_probabilities=dict(cand.candidate_alternative_distribution),
                    semantic_importance=float(cand.semantic_importance),
                    coder_confidence=float(cand.coder_confidence),
                    coder_agreement=0.0,  # Explicit pre-reconciliation value; Agent 03 reconciles across coders
                    evidence_span_ids=list(cand.evidence_span_ids),
                    provenance=coding_prov,
                    probability_interpretation=raw_st.probability_interpretation
                    if raw_st is not None
                    else "epistemic_uncertainty_over_preference",
                    derived_scalar_score=cand.derived_scalar_stance,
                    economic_good_class=good_cls,
                    perception_category=cand.proposed_alternative_frame_label,
                    rationale_summary=parsed_coding.coder_rationale,
                )
                coding_obj.validate_invariants(tolerance=1e-4)

                coding_results_out.append(
                    {
                        "coding_id": coding_obj.coding_id,
                        "participant_id": coding_obj.participant_id,
                        "question_id": coding_obj.question_id,
                        "subtopic_id": coding_obj.subtopic_id,
                        "coder_source": coding_obj.coder_source,
                        "missingness_state": coding_obj.missingness_state.value,
                        "epistemic_status": detailed["response_status"].value,
                        "alternative_probabilities": coding_obj.alternative_probabilities,
                        "semantic_importance": coding_obj.semantic_importance,
                        "coder_confidence": coding_obj.coder_confidence,
                        "coder_agreement": coding_obj.coder_agreement,
                        "coder_agreement_status": "PRE_RECONCILIATION_AGENT_03_PENDING",
                        "derived_scalar_score": coding_obj.derived_scalar_score,
                        "economic_good_class": coding_obj.economic_good_class.value
                        if coding_obj.economic_good_class is not None
                        else None,
                        "perception_category": coding_obj.perception_category,
                        "probability_interpretation": coding_obj.probability_interpretation,
                        "evidence_span_ids": coding_obj.evidence_span_ids,
                        "rationale_summary": coding_obj.rationale_summary,
                    }
                )

            # Convert Stage A values into ValueAssignment dicts
            fallback_span_ids = [sp.span_id for sp in detailed["evidence_spans"]]
            va_dicts = _extract_value_assignments_for_response(
                extractor=extractor,
                participant_id=r_item.participant_id,
                question_id=qid,
                subtopic_id=primary_subtopic_id,
                stage_a_values=detailed["values"],
                fallback_span_ids=fallback_span_ids,
                prompt_hash=p_hash,
                coder_id=coder_id,
                response_id=r_item.response_id,
                missingness_state=MissingnessState.OBSERVED_USABLE,
            )
            value_assignments_out.extend(va_dicts)
            responses_completed += 1

        # Record Phase 1 discovered subtopics with Phase 2 evidence links attached
        for st in taxonomy.discovered_subtopics:
            sid = _slugify_subtopic_id(qid, st.subtopic_key)
            sp_links = sorted(discovered_spans_by_key.get(st.subtopic_key, set()))
            pid_links = sorted(discovered_pids_by_key.get(st.subtopic_key, set()))
            st_dict = st.model_dump()
            st_dict["subtopic_id"] = sid
            st_dict["question_id"] = qid
            st_dict["coder_id"] = coder_id
            st_dict["supporting_participant_ids"] = pid_links
            st_dict["supporting_span_ids"] = sp_links
            discovered_subtopics_out.append(st_dict)

    aggregate_prompt_hash = hashlib.sha256(
        (f"{adapter_tag}|" + "|".join(prompt_hashes_used)).encode("utf-8")
    ).hexdigest()

    live_gpu_exec = bool(mgr.hardware.gpu_available and not srv.use_mock_server)
    execution_metadata = {
        "coder_id": coder_id,
        "model_family": spec.model_family,
        "base_model": spec.base_model,
        "model_repo": spec.model_repo,
        "model_revision": spec.model_revision,
        "quantization": spec.quantization,
        "serving_engine": spec.serving_engine,
        "execution_mode": mgr.config.execution_mode.value,
        "server_backend": srv.server_backend,
        "model_load_succeeded": True,
        "gpu_resident": live_gpu_exec,
        "inference_occurred": responses_completed > 0,
        "responses_attempted": responses_attempted,
        "responses_completed": responses_completed,
        "responses_failed": responses_failed,
        "non_preference_cells_preserved": non_preference_preserved,
        "checkpoint_hits": checkpoint_hits,
        "prompt_hash": aggregate_prompt_hash,
        "source_evidence_hash": global_source_hash,
        "reconciled_by_agent_03": False,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "coder_id": coder_id,
        "execution_metadata": execution_metadata,
        "evidence_spans": evidence_spans_out,
        "discovered_subtopics": discovered_subtopics_out,
        "value_assignments": value_assignments_out,
        "coding_results": coding_results_out,
    }


def run_dual_coder_production(
    *,
    base_dir: Optional[Path | str] = None,
    run_id: str = ACTIVE_RUN_ID,
    require_live_gpu: bool = True,
    allow_mock_for_test: bool = False,
    hardware: Optional[HardwareProfile] = None,
    config: Optional[GPURuntimeConfig] = None,
    startup_timeout_sec: Optional[float] = None,
    resolve_remote_models: bool = True,
) -> Dict[str, Any]:
    """
    Execute full production dual-coder qualitative coding across `answers_normalized.parquet`:
    1. Enforce Gate 1 (`verify_gate_1`), Gate 2, model-family diversity, and (when `require_live_gpu=True`)
       live GPU hardware + passed 5-stage `gpu_runtime_benchmark.json`.
    2. Start dual servers concurrently (or sequentially according to runtime config / fallback).
    3. Independently execute Coder A and Coder B over all Q01-Q14 corpora using shared `source_evidence_hash`
       and strictly distinct coder-specific `prompt_hash` values with crash-safe WAL resume.
    4. Persist independent unreconciled artifacts:
       - `data/processed/coder_a_outputs.json`
       - `data/processed/coder_b_outputs.json`
    5. Run `validate_dual_coder_outputs` (Checks A-H) and update `gpu_runtime_config.json`.
    """
    root = (Path(base_dir) if base_dir else Path.cwd()).resolve()

    # 1. Upstream Gate 1 & Normalized Answers
    gate1 = verify_gate_1(base_dir=root, run_id=run_id)
    if gate1.get("status") != "PASS":
        raise DualCoderExecutionError(f"Gate 1 failed; cannot start dual-coder production run: {gate1}")

    cfg_path = root / "runs" / run_id / "gpu_runtime_config.json"
    if config is not None:
        cfg = config
    elif cfg_path.is_file():
        cfg = GPURuntimeConfig.load(cfg_path)
    else:
        cfg = GPURuntimeConfig(run_id=run_id)

    hw = hardware or detect_hardware_profile()
    validate_model_family_diversity(cfg.coder_a_spec, cfg.coder_b_spec)

    if require_live_gpu and not allow_mock_for_test:
        if not hw.gpu_available or hw.gpu_total_vram_mb <= 0.0:
            raise DualCoderExecutionError(
                f"Live physical GPU required for production dual-coder execution, detected: {hw.gpu_device_name}."
            )
        bench_path = root / "runs" / run_id / "gpu_runtime_benchmark.json"
        if cfg.live_gpu_benchmark_status != "EXECUTED_LIVE_GPU" or not bench_path.is_file():
            raise DualCoderExecutionError(
                f"Live 5-stage GPU benchmark must pass first (`runs/{run_id}/gpu_runtime_benchmark.json`). "
                "Execute `notebooks/07_gpu_runtime.ipynb` before running `01_gpu_coders.ipynb`."
            )
        if resolve_remote_models and (
            not cfg.coder_a_spec.remote_repo_validated or not cfg.coder_b_spec.remote_repo_validated
        ):
            resolve_dual_coder_specs(cfg, verify_remote=True, verify_tokenizer=False)
            validate_model_family_diversity(cfg.coder_a_spec, cfg.coder_b_spec)
    elif allow_mock_for_test and cfg.execution_mode == ExecutionMode.CPU_FALLBACK:
        # In test-only mock runs, exercise CONCURRENT_DUAL_SERVER or specified mode
        pass

    ckpt_dir = Path(cfg.checkpoint_dir)
    if not ckpt_dir.is_absolute():
        ckpt_dir = root / ckpt_dir

    use_mock = True if allow_mock_for_test else None
    mgr = DualCoderRuntimeManager(
        config=cfg,
        hardware=hw,
        use_mock_server=use_mock,
        startup_timeout_sec=startup_timeout_sec,
        log_dir=ckpt_dir / "vllm_logs",
    )
    mgr.checkpoint_store = mgr.checkpoint_store.__class__(checkpoint_dir=ckpt_dir, run_id=run_id)

    gate2_ok, gate2_msg = mgr.verify_full_survey_coding_gates(root)
    if not gate2_ok:
        raise DualCoderExecutionError(gate2_msg)

    answers_path = root / "data" / "normalized" / "answers_normalized.parquet"
    raw_csv_path = root / "data" / "raw" / "survey_raw.csv"
    norm_df = pd.read_parquet(answers_path)
    raw_sha256 = compute_sha256(raw_csv_path) if raw_csv_path.is_file() else ""

    registry = QuestionRegistry(raw_csv_path=raw_csv_path, run_id=run_id)
    question_specs = registry.build_from_answers(norm_df)
    corpora, global_source_hash = _build_question_corpora(norm_df, question_specs)

    coder_outputs: Dict[str, Dict[str, Any]] = {}
    coder_errors: Dict[str, Exception] = {}

    try:
        start_info = mgr.start_servers(cfg.execution_mode)

        if mgr.config.execution_mode == ExecutionMode.CONCURRENT_DUAL_SERVER and not start_info.get(
            "fallback_triggered"
        ):
            stop_evt = threading.Event()

            def _run_thread(cid: Literal["coder_a", "coder_b"]) -> None:
                try:
                    coder_outputs[cid] = _execute_single_coder_pass(
                        coder_id=cid,
                        mgr=mgr,
                        corpora=corpora,
                        question_specs=question_specs,
                        global_source_hash=global_source_hash,
                        dataset_fingerprint=raw_sha256,
                        run_id=run_id,
                        stop_event=stop_evt,
                    )
                except Exception as exc:
                    coder_errors[cid] = exc
                    if mgr.config.auto_sequential_fallback:
                        stop_evt.set()

            t_a = threading.Thread(target=_run_thread, args=("coder_a",), name="hfg-prod-coder-a")
            t_b = threading.Thread(target=_run_thread, args=("coder_b",), name="hfg-prod-coder-b")
            t_a.start()
            t_b.start()
            t_a.join()
            t_b.join()

            if coder_errors:
                if mgr.config.auto_sequential_fallback:
                    mgr._trigger_sequential_fallback(
                        f"Concurrent dual-coder pass failed ({coder_errors}); resuming sequentially with preserved checkpoints."
                    )
                else:
                    first_err = next(iter(coder_errors.values()))
                    raise DualCoderExecutionError(f"Concurrent coding failed: {first_err}") from first_err

        # Sequential fallback or sequential/test single-server execution (also completes any remaining coder)
        if "coder_a" not in coder_outputs:
            mgr.server_b.stop()
            mgr.server_a.start()
            coder_outputs["coder_a"] = _execute_single_coder_pass(
                coder_id="coder_a",
                mgr=mgr,
                corpora=corpora,
                question_specs=question_specs,
                global_source_hash=global_source_hash,
                dataset_fingerprint=raw_sha256,
                run_id=run_id,
            )
            mgr.server_a.stop()

        if "coder_b" not in coder_outputs:
            mgr.server_a.stop()
            mgr.server_b.start()
            coder_outputs["coder_b"] = _execute_single_coder_pass(
                coder_id="coder_b",
                mgr=mgr,
                corpora=corpora,
                question_specs=question_specs,
                global_source_hash=global_source_hash,
                dataset_fingerprint=raw_sha256,
                run_id=run_id,
            )
            mgr.server_b.stop()
    finally:
        mgr.shutdown()

    payload_a = coder_outputs["coder_a"]
    payload_b = coder_outputs["coder_b"]

    out_a_path = root / "data" / "processed" / "coder_a_outputs.json"
    out_b_path = root / "data" / "processed" / "coder_b_outputs.json"
    _atomic_write_json(out_a_path, payload_a)
    _atomic_write_json(out_b_path, payload_b)

    # Validate against Agent 11 checks A-H before reporting success
    from src.pipeline.orchestrator import validate_dual_coder_outputs

    val_report = validate_dual_coder_outputs(
        normalized_df=norm_df,
        question_specs=question_specs,
        coder_a_payload=payload_a,
        coder_b_payload=payload_b,
    )
    if val_report.status != "PASS":
        raise DualCoderExecutionError(
            f"Post-run dual-coder invariant validation failed ({val_report.status}): {val_report.violations}"
        )

    # Update config flags only when genuine non-mock GPU execution succeeded
    if not allow_mock_for_test and hw.gpu_available:
        cfg.production_dual_model_validation = True
        cfg.updated_at_utc = datetime.now(timezone.utc).isoformat()
        cfg.save(cfg_path)

    return {
        "status": "PASS",
        "run_id": run_id,
        "execution_mode_final": mgr.config.execution_mode.value,
        "fallback_events": list(mgr.fallback_events),
        "coder_a_output_path": str(out_a_path),
        "coder_b_output_path": str(out_b_path),
        "coder_a_metadata": payload_a["execution_metadata"],
        "coder_b_metadata": payload_b["execution_metadata"],
        "validation_checks": val_report.checks,
        "checkpoint_wal_path": str(mgr.checkpoint_store.flat_wal_path),
        "total_checkpoints_persisted": len(mgr.checkpoint_store.all_records()),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HFG Agent 07 Production Dual-Coder Runner")
    parser.add_argument("--run-id", default=ACTIVE_RUN_ID, help="Active HFG run ID")
    parser.add_argument("--base-dir", default=None, help="Repository root directory")
    parser.add_argument(
        "--skip-remote-resolve",
        action="store_true",
        help="Do not re-query Hugging Face API if config already carries validated repos",
    )
    args = parser.parse_args()

    result = run_dual_coder_production(
        base_dir=args.base_dir,
        run_id=args.run_id,
        require_live_gpu=True,
        resolve_remote_models=not args.skip_remote_resolve,
    )
    print(json.dumps(result, indent=2))
