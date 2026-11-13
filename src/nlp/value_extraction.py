"""Open two-stage organisational value discovery and cross-question consolidation proposals.

Owned by: Agent 02 — Qualitative Coding
Schema Version: 1.0.0 / v1.1.0
Active Run: run_20261111_002

Implements Section 2 (Open Value Discovery):
- EXAMPLE_ORGANISATIONAL_VALUE_ALIASES (aliased as CANONICAL_ORGANISATIONAL_VALUES for
  backward compatibility) is strictly an illustrative, non-exhaustive set of examples/aliases.
  It MUST NOT restrict model output or force unfamiliar values into 7 fixed categories.
- Stage A: Independent free-form value extraction grounded in exact evidence spans, storing
  original label, definition, evidence IDs, participant/question refs, polarity (where
  meaningful), semantic importance, and coder confidence.
- Stage B: Cross-question consolidation proposals preserving original labels, proposed
  canonical label, supporting evidence, merge rationale, uncertainty, and unresolved
  alternatives. Final cross-coder reconciliation belongs to Agent 03.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from src.contracts import MissingnessState, ProvenanceMeta, SCHEMA_VERSION, ValueAssignment
from src.nlp.schemas import LLMValueExtraction, ValueConsolidationProposal


# Non-exhaustive illustrative examples / optional aliases ONLY (never a closed taxonomy)
EXAMPLE_ORGANISATIONAL_VALUE_ALIASES: Dict[str, Dict[str, Any]] = {
    "VAL_ACADEMIC_AUTONOMY": {
        "label": "Academic Autonomy",
        "definition": "Discretionary decision-making and scientific freedom of laboratories, professors, and research units.",
        "aliases": ["autonomy", "autonomie", "academic freedom", "freiheit", "self-governance", "indépendance"],
    },
    "VAL_SOLIDARITY_EQUITY": {
        "label": "Solidarity & Inter-Team Equity",
        "definition": "Mutualization of financial and infrastructural resources to protect emerging or vulnerable teams.",
        "aliases": ["solidarity", "solidarité", "equity", "équité", "gerechtigkeit", "mutualization", "redistribution"],
    },
    "VAL_TRANSPARENCY": {
        "label": "Procedural Transparency",
        "definition": "Clear, predictable, and publicly disclosed criteria for resource allocation, overheads, and evaluation.",
        "aliases": ["transparency", "transparence", "clarity", "klarheit", "predictability", "transparenz"],
    },
    "VAL_SUBSIDIARITY": {
        "label": "Operational Subsidiarity",
        "definition": "Assigning decision rights and administrative tasks to the lowest competent operational level.",
        "aliases": ["subsidiarity", "subsidiarité", "subsidiarität", "decentralization", "dezentral", "proximity"],
    },
    "VAL_SCIENTIFIC_EXCELLENCE": {
        "label": "Scientific Excellence & Merit",
        "definition": "Incentivizing high-impact research, competitive grant success, and quality-driven recognition.",
        "aliases": ["excellence", "merit", "mérite", "leistung", "scientific quality", "competitiveness"],
    },
    "VAL_COLLEGIAL_GOVERNANCE": {
        "label": "Collegial & Participatory Governance",
        "definition": "Shared deliberation, democratic representation across academic ranks, and consensus-oriented coordination.",
        "aliases": ["collegial", "collegiality", "collégialité", "participatory", "mitbestimmung", "democratic"],
    },
    "VAL_OPERATIONAL_EFFICIENCY": {
        "label": "Operational Efficiency & Overhead Containment",
        "definition": "Minimizing bureaucratic friction, avoiding structural duplication, and optimizing shared services.",
        "aliases": ["efficiency", "efficacité", "effizienz", "streamlining", "anti-bureaucracy", "simplification"],
    },
}

# Retained alias for backwards compatibility; strictly non-exhaustive examples, NOT a closed enum.
CANONICAL_ORGANISATIONAL_VALUES = EXAMPLE_ORGANISATIONAL_VALUE_ALIASES


def _slugify_value_id(label: str) -> str:
    clean = re.sub(r"[^\w]+", "_", label.upper()).strip("_")
    return f"VAL_{clean[:48]}" if not clean.startswith("VAL_") else clean[:52]


def _tokenize_value(text: str) -> set[str]:
    clean = re.sub(r"[^\w\s]", " ", (text or "").lower())
    stops = {"and", "the", "for", "with", "of", "in", "to", "value", "institutional", "val"}
    return {t for t in clean.split() if len(t) > 2 and t not in stops}


class ValueExtractor:
    """Two-stage open organisational value discovery (Stage A extraction, Stage B consolidation proposal)."""

    def __init__(
        self,
        run_id: str = "run_20261111_002",
        dataset_fingerprint: str = "56acded3e02be49be27d6b288fa2c43fcce68df24525113eba1b1161eec52a95",
    ):
        self.run_id = run_id
        self.dataset_fingerprint = dataset_fingerprint

    def find_optional_example_alias(self, label_or_id: str) -> Optional[str]:
        """Non-binding lookup returning an illustrative alias ID ONLY on strong match, else None.

        Never overwrites or restricts unseen free-form labels.
        """
        upper_id = label_or_id.upper().strip()
        if upper_id in EXAMPLE_ORGANISATIONAL_VALUE_ALIASES:
            return upper_id
        if f"VAL_{upper_id}" in EXAMPLE_ORGANISATIONAL_VALUE_ALIASES:
            return f"VAL_{upper_id}"

        lower_raw = label_or_id.lower().strip()
        for alias_id, meta in EXAMPLE_ORGANISATIONAL_VALUE_ALIASES.items():
            if meta["label"].lower() == lower_raw:
                return alias_id
            for kw in meta.get("aliases", []):
                if kw in lower_raw:
                    return alias_id
        return None

    def normalize_value_id(self, raw_id: str) -> Tuple[str, str, str]:
        """Backward-compatible helper preserving unseen values without forcing into the 7 examples."""
        upper_clean = raw_id.strip()
        if upper_clean.upper() in EXAMPLE_ORGANISATIONAL_VALUE_ALIASES:
            meta = EXAMPLE_ORGANISATIONAL_VALUE_ALIASES[upper_clean.upper()]
            return upper_clean.upper(), meta["label"], meta["definition"]

        alias_hit = self.find_optional_example_alias(raw_id)
        if alias_hit is not None and (
            raw_id.upper().startswith("VAL_") or raw_id.lower().strip() in {
                EXAMPLE_ORGANISATIONAL_VALUE_ALIASES[alias_hit]["label"].lower(),
                *EXAMPLE_ORGANISATIONAL_VALUE_ALIASES[alias_hit].get("aliases", []),
            }
        ):
            meta = EXAMPLE_ORGANISATIONAL_VALUE_ALIASES[alias_hit]
            return alias_hit, meta["label"], meta["definition"]

        # Preserve unseen value cleanly without coercion
        slug_id = _slugify_value_id(raw_id)
        clean_label = raw_id.replace("VAL_", "").replace("_", " ").strip()
        if clean_label.isupper() or "_" in raw_id:
            clean_label = clean_label.title()
        return slug_id, clean_label, f"Participant-grounded organisational value: {clean_label}."

    def extract_stage_a_value(
        self,
        participant_id: str,
        question_id: str,
        raw_value: LLMValueExtraction | Dict[str, Any],
        supporting_span_ids: List[str],
        coder_id: str = "coder_a",
        response_id: str = "",
    ) -> LLMValueExtraction:
        """Stage A: Independently extract a free-form organisational value preserving original label & metadata.

        Unseen values are accepted directly without forcing into fixed categories.
        Polarity is stored only where meaningful (None permitted).
        """
        if isinstance(raw_value, LLMValueExtraction):
            val_dict = raw_value.model_dump()
        else:
            val_dict = dict(raw_value)

        orig_label = (
            val_dict.get("original_label")
            or val_dict.get("value_label_en")
            or str(val_dict.get("value_id", "")).replace("VAL_", "").replace("_", " ").title()
        ).strip()
        if not orig_label:
            raise ValueError("Stage A value extraction requires an original_label.")

        raw_id = (val_dict.get("value_id") or "").strip()
        val_id = _slugify_value_id(raw_id if raw_id else orig_label)
        definition = (val_dict.get("value_definition") or "").strip() or (
            f"Participant-expressed value concerning {orig_label}."
        )
        matched_alias = self.find_optional_example_alias(orig_label) or (
            self.find_optional_example_alias(raw_id) if raw_id else None
        )

        # Polarity ONLY where meaningful (None allowed)
        raw_pol = val_dict.get("polarity")
        polarity: Optional[float] = None
        if raw_pol is not None:
            polarity = max(-1.0, min(1.0, float(raw_pol)))

        sem_imp = max(0.0, min(1.0, float(val_dict.get("semantic_importance", 0.8))))
        conf = max(0.0, min(1.0, float(val_dict.get("coder_confidence", 0.9))))

        pol_interval = val_dict.get("polarity_uncertainty_interval")
        if polarity is not None and isinstance(pol_interval, (list, tuple)) and len(pol_interval) == 2:
            interval_tuple: Optional[Tuple[float, float]] = (float(pol_interval[0]), float(pol_interval[1]))
        elif polarity is not None:
            interval_tuple = (round(max(-1.0, polarity - 0.1), 3), round(min(1.0, polarity + 0.1), 3))
        else:
            interval_tuple = None

        return LLMValueExtraction(
            original_label=orig_label,
            value_id=val_id,
            value_label_en=orig_label,
            value_definition=definition,
            participant_id=participant_id,
            question_id=question_id,
            response_id=response_id or f"RESP_{participant_id}_{question_id}",
            polarity=polarity,
            semantic_importance=sem_imp,
            coder_confidence=conf,
            polarity_uncertainty_interval=interval_tuple,
            evidence_quotes=list(val_dict.get("evidence_quotes") or []),
            evidence_span_ids=list(supporting_span_ids),
            matched_example_alias=matched_alias,
        )

    def create_value_assignment(
        self,
        participant_id: str,
        question_id: str,
        subtopic_id: str,
        raw_value: LLMValueExtraction | Dict[str, Any],
        supporting_span_ids: List[str],
        missingness_state: MissingnessState = MissingnessState.OBSERVED_USABLE,
        coder_id: str = "coder_a",
        config_hash: str = "",
        coder_agreement: float = 1.0,
        response_id: str = "",
    ) -> ValueAssignment:
        """Construct a ValueAssignment contract record preserving Stage A open discovery labels."""
        if not missingness_state.is_usable():
            raise ValueError(
                f"Cannot create ValueAssignment for non-usable missingness_state={missingness_state}."
            )
        if not supporting_span_ids:
            raise ValueError("ValueAssignment must cite >= 1 supporting EvidenceSpan.")

        stage_a = self.extract_stage_a_value(
            participant_id=participant_id,
            question_id=question_id,
            raw_value=raw_value,
            supporting_span_ids=supporting_span_ids,
            coder_id=coder_id,
            response_id=response_id,
        )

        # Contract ValueAssignment currently declares polarity: float; encode non-polar explicitly in definition note
        # while requesting ValueAssignment.polarity: Optional[float] in shared-file change request.
        contract_polarity = stage_a.polarity if stage_a.polarity is not None else 0.0
        contract_interval = stage_a.polarity_uncertainty_interval or (0.0, 0.0)
        definition_text = stage_a.value_definition
        if stage_a.polarity is None and "[polarity_not_applicable]" not in definition_text:
            definition_text = f"{definition_text} [polarity_not_applicable]"

        key_str = f"{self.run_id}_{question_id}_{subtopic_id}_{participant_id}_{stage_a.value_id}_{coder_id}"
        record_id = hashlib.sha256(key_str.encode("utf-8")).hexdigest()[:16]
        assignment_id = f"VA_{question_id}_{subtopic_id}_{record_id[:8]}"

        provenance = ProvenanceMeta(
            record_id=record_id,
            run_id=self.run_id,
            dataset_fingerprint=self.dataset_fingerprint,
            created_at_utc=datetime.now(timezone.utc).isoformat(),
            producer_module="src/nlp/value_extraction.py",
            producer_agent="agent_02",
            upstream_artifact_ids=supporting_span_ids,
            config_hash=config_hash,
            schema_version=SCHEMA_VERSION,
        )

        return ValueAssignment(
            value_assignment_id=assignment_id,
            value_id=stage_a.value_id,
            value_label_en=stage_a.original_label,
            value_definition=definition_text,
            participant_id=participant_id,
            question_id=question_id,
            subtopic_id=subtopic_id,
            evidence_span_ids=supporting_span_ids,
            missingness_state=missingness_state,
            polarity=contract_polarity,
            semantic_importance=stage_a.semantic_importance,
            coder_confidence=stage_a.coder_confidence,
            coder_agreement=coder_agreement,
            polarity_uncertainty_interval=contract_interval,
            provenance=provenance,
            coder_a_raw_label=stage_a.original_label if coder_id == "coder_a" else None,
            coder_b_raw_label=stage_a.original_label if coder_id == "coder_b" else None,
            cross_question_bridge_ids=[],
            schema_version=SCHEMA_VERSION,
        )

    def propose_cross_question_consolidation(
        self,
        stage_a_extractions: List[LLMValueExtraction],
        consolidation_callable: Optional[Any] = None,
    ) -> List[ValueConsolidationProposal]:
        """Stage B: Propose cross-question value consolidations while preserving originals and uncertainty.

        Final cross-coder reconciliation belongs to Agent 03.
        """
        if not stage_a_extractions:
            return []

        if consolidation_callable is not None:
            raw_proposals = consolidation_callable(stage_a_extractions)
            return [
                p if isinstance(p, ValueConsolidationProposal) else ValueConsolidationProposal.model_validate(p)
                for p in raw_proposals
            ]

        # Deterministic semantic grouping by normalized alias or token overlap on label + definition
        groups: List[Dict[str, Any]] = []
        for item in stage_a_extractions:
            tokens = _tokenize_value(f"{item.original_label} {item.value_definition}")
            alias = item.matched_example_alias

            best_group = None
            best_score = 0.0
            for grp in groups:
                if alias and grp["alias"] and alias == grp["alias"]:
                    best_group = grp
                    best_score = 1.0
                    break
                inter = len(tokens & grp["tokens"])
                union = len(tokens | grp["tokens"])
                sim = inter / union if union > 0 else 0.0
                if sim > best_score and sim >= 0.35:
                    best_score = sim
                    best_group = grp

            if best_group is not None:
                best_group["items"].append(item)
                best_group["tokens"].update(tokens)
                best_group["scores"].append(best_score)
            else:
                groups.append({
                    "alias": alias,
                    "tokens": set(tokens),
                    "items": [item],
                    "scores": [1.0],
                })

        proposals: List[ValueConsolidationProposal] = []
        for idx, grp in enumerate(groups):
            items: List[LLMValueExtraction] = grp["items"]
            distinct_labels = sorted({it.original_label for it in items})
            # Representative proposed canonical label (most frequent original label, or longest)
            counts = {lbl: sum(1 for it in items if it.original_label == lbl) for lbl in distinct_labels}
            proposed_label = max(distinct_labels, key=lambda l: (counts[l], len(l)))
            proposed_def = max((it.value_definition for it in items), key=len)

            evidence_ids = sorted({eid for it in items for eid in it.evidence_span_ids})
            question_ids = sorted({it.question_id for it in items if it.question_id})
            participant_ids = sorted({it.participant_id for it in items if it.participant_id})
            confs = [it.coder_confidence for it in items]

            original_records = [
                {
                    "original_label": it.original_label,
                    "value_id": it.value_id,
                    "participant_id": it.participant_id,
                    "question_id": it.question_id,
                    "response_id": it.response_id,
                    "polarity": it.polarity,
                    "semantic_importance": it.semantic_importance,
                    "coder_confidence": it.coder_confidence,
                    "evidence_span_ids": it.evidence_span_ids,
                }
                for it in items
            ]

            unresolved_alts: List[str] = []
            if len(distinct_labels) > 1:
                unresolved_alts = [lbl for lbl in distinct_labels if lbl != proposed_label]

            min_sim = min(grp["scores"]) if grp["scores"] else 1.0
            rationale = (
                f"Consolidated {len(items)} Stage A extractions across questions {question_ids} "
                f"from original labels {distinct_labels} (min_cluster_similarity={min_sim:.2f})."
            )
            prop_hash = hashlib.sha256(f"{self.run_id}_{idx}_{proposed_label}".encode("utf-8")).hexdigest()[:10]
            proposals.append(
                ValueConsolidationProposal(
                    proposal_id=f"VALPROP_{prop_hash}",
                    proposed_canonical_label=proposed_label,
                    proposed_definition=proposed_def,
                    original_labels=original_records,
                    supporting_evidence_ids=evidence_ids,
                    supporting_question_ids=question_ids,
                    supporting_participant_ids=participant_ids,
                    merge_rationale=rationale,
                    uncertainty={
                        "min_coder_confidence": round(min(confs), 3),
                        "max_coder_confidence": round(max(confs), 3),
                        "label_variance_count": len(distinct_labels),
                        "cluster_similarity_min": round(min_sim, 3),
                    },
                    unresolved_alternatives=unresolved_alts,
                    requires_agent_03_reconciliation=True,
                )
            )

        return proposals

    def populate_cross_question_bridges(
        self,
        assignments: List[ValueAssignment],
    ) -> List[ValueAssignment]:
        """Compute cross-question links for each value and populate cross_question_bridge_ids."""
        value_to_questions: Dict[str, set[str]] = {}
        for va in assignments:
            if va.missingness_state.is_usable():
                value_to_questions.setdefault(va.value_id, set()).add(va.question_id)

        bridged: List[ValueAssignment] = []
        for va in assignments:
            other_questions = sorted(list(value_to_questions.get(va.value_id, set()) - {va.question_id}))
            updated = ValueAssignment(
                value_assignment_id=va.value_assignment_id,
                value_id=va.value_id,
                value_label_en=va.value_label_en,
                value_definition=va.value_definition,
                participant_id=va.participant_id,
                question_id=va.question_id,
                subtopic_id=va.subtopic_id,
                evidence_span_ids=va.evidence_span_ids,
                missingness_state=va.missingness_state,
                polarity=va.polarity,
                semantic_importance=va.semantic_importance,
                coder_confidence=va.coder_confidence,
                coder_agreement=va.coder_agreement,
                polarity_uncertainty_interval=va.polarity_uncertainty_interval,
                provenance=va.provenance,
                coder_a_raw_label=va.coder_a_raw_label,
                coder_b_raw_label=va.coder_b_raw_label,
                cross_question_bridge_ids=other_questions,
                schema_version=va.schema_version,
            )
            bridged.append(updated)

        return bridged
