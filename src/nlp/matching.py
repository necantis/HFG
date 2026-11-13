"""Structured semantic subtopic matching and topic-vs-position separation.

Owned by: Agent 02 — Qualitative Coding
Schema Version: 1.0.0 / v1.1.0
Active Run: run_20261111_002

Implements Section 6 (Subtopic Matching):
- Lexical Jaccard / embedding similarity is used ONLY for candidate retrieval,
  NEVER for final semantic merge decisions alone.
- Explicitly separates the TOPIC (decision_object, mechanism, scope, definition, evidence)
  from the PARTICIPANT POSITION / ALTERNATIVES on that topic.
  For example, individual vs. collective financial responsibility are opposing alternatives
  within ONE subtopic, rather than automatic duplicates or automatically separate topics.
- Recognizes low-lexical-overlap semantic equivalence when structured dimensions align.
- Preserves uncertain matches as SubtopicMatchProposal records for Agent 03 adjudication.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from src.nlp.schemas import SubtopicMatchProposal


STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "into",
    "that",
    "this",
    "about",
    "over",
    "under",
    "between",
    "within",
    "regarding",
    "subtopic",
    "question",
    "level",
    "mode",
    "system",
}

# Domain-neutral structural concept groups (for multilingual/synonym equivalence across FR/DE/EN)
SEMANTIC_SYNONYM_GROUPS: List[Set[str]] = [
    {"hr", "hiring", "recruitment", "recrutement", "recrutements", "staffing", "personal", "personalentscheidungen", "stellenbesetzungen"},
    {"lab", "laboratory", "laboratoire", "laboratoires", "group", "forschungsgruppen", "team", "unit"},
    {"pole", "poles", "pôle", "pôles", "center", "centers", "zentren", "cluster"},
    {"finance", "financial", "financier", "financing", "budget", "funding", "deficit", "deficits", "cost", "costs", "liability", "responsibility", "responsabilité"},
    {"overhead", "overheads", "indirect", "frais", "pool", "socle"},
    {"autonomy", "autonomie", "autonom", "decentralized", "decentral", "dezentral", "independent", "discretion"},
    {"central", "centralized", "centralisé", "zentrale", "centralisation", "institute", "university"},
    {"collective", "collectif", "collective", "solidarity", "solidarité", "mutualized", "mutualisé", "shared", "common"},
    {"individual", "individuel", "individuelle", "private", "solitary", "single"},
    {"evaluation", "evaluations", "évaluation", "évaluations", "assessment", "review", "appraisal"},
    {"decision", "decisions", "décision", "authority", "mandate", "governance", "steering", "steuerung", "right", "rights"},
    {"transparency", "transparence", "transparent", "clarity", "klarheit", "criteria", "critères"},
]


def _tokenize(text: str) -> Set[str]:
    clean = re.sub(r"[^\w\s]", " ", (text or "").lower())
    return {t for t in clean.split() if len(t) > 1 and t not in STOPWORDS}


def _canonicalize_tokens(tokens: Set[str]) -> Set[str]:
    """Map surface tokens to concept tokens when comparing definitions/decision objects."""
    mapped: Set[str] = set()
    for t in tokens:
        matched_group = None
        for idx, grp in enumerate(SEMANTIC_SYNONYM_GROUPS):
            if t in grp:
                matched_group = f"CONCEPT_{idx}"
                break
        mapped.add(matched_group or t)
    return mapped


def _jaccard(a: Set[str], b: Set[str]) -> float:
    if not a and not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


class SubtopicDescriptor:
    """Normalized structural view of a SubtopicCandidate or LLMDiscoveredSubtopic for matching."""

    def __init__(
        self,
        item_id: str,
        question_id: str,
        label: str,
        definition: str = "",
        decision_object: str = "",
        mechanism: str = "",
        scope: str = "",
        alternatives: Optional[List[str]] = None,
        evidence_ids: Optional[List[str]] = None,
        response_ids: Optional[List[str]] = None,
        coder_id: str = "coder_a",
    ):
        self.item_id = item_id
        self.question_id = question_id
        self.label = label
        self.definition = definition
        self.decision_object = decision_object
        self.mechanism = mechanism
        self.scope = scope
        self.alternatives = alternatives or []
        self.evidence_ids = set(evidence_ids or [])
        self.response_ids = set(response_ids or [])
        self.coder_id = coder_id


class SubtopicMatcher:
    """Evaluates semantic equivalence between subtopics using structured criteria.

    Jaccard/lexical overlap is strictly restricted to candidate retrieval; final match
    classification requires evaluating definition, evidence, decision_object, mechanism,
    and scope—explicitly preserving opposing alternatives within the same topic and
    forwarding uncertain matches to Agent 03.
    """

    def __init__(
        self,
        semantic_judge_callable: Optional[
            Callable[[SubtopicDescriptor, SubtopicDescriptor], Dict[str, Any]]
        ] = None,
    ):
        self.semantic_judge_callable = semantic_judge_callable

    def compute_lexical_retrieval_score(
        self,
        a: SubtopicDescriptor,
        b: SubtopicDescriptor,
    ) -> float:
        """Purely lexical Jaccard score for candidate retrieval ONLY (never final merge)."""
        tok_a = _tokenize(a.label) | _tokenize(a.definition)
        tok_b = _tokenize(b.label) | _tokenize(b.definition)
        return round(_jaccard(tok_a, tok_b), 4)

    def retrieve_candidate_pairs(
        self,
        descriptors: List[SubtopicDescriptor],
        min_retrieval_threshold: float = 0.0,
    ) -> List[Tuple[SubtopicDescriptor, SubtopicDescriptor, float]]:
        """Retrieve candidate subtopic pairs for structured semantic evaluation.

        Note: Within a single question, pairs can share low lexical overlap yet have
        high structural equivalence (e.g. multilingual synonyms), so by default all
        within-question pairs (or pairs exceeding threshold / sharing evidence / sharing
        structural tokens) are retrieved for structured evaluation.
        """
        pairs: List[Tuple[SubtopicDescriptor, SubtopicDescriptor, float]] = []
        for i in range(len(descriptors)):
            for j in range(i + 1, len(descriptors)):
                da = descriptors[i]
                db = descriptors[j]
                if da.question_id != db.question_id:
                    continue
                lex_score = self.compute_lexical_retrieval_score(da, db)
                shared_evidence = bool(
                    (da.evidence_ids & db.evidence_ids) or (da.response_ids & db.response_ids)
                )
                # Broad recall retrieval: lexical overlap, shared evidence, or structural concept overlap
                struct_a = _canonicalize_tokens(
                    _tokenize(f"{da.label} {da.definition} {da.decision_object} {da.mechanism} {da.scope}")
                )
                struct_b = _canonicalize_tokens(
                    _tokenize(f"{db.label} {db.definition} {db.decision_object} {db.mechanism} {db.scope}")
                )
                struct_overlap = _jaccard(struct_a, struct_b)

                if (
                    lex_score >= min_retrieval_threshold
                    or shared_evidence
                    or struct_overlap >= 0.15
                ):
                    pairs.append((da, db, lex_score))
        return pairs

    @staticmethod
    def _field_match(val_a: str, val_b: str) -> Tuple[bool, float]:
        """Compare a structured topic field (decision_object, mechanism, or scope)."""
        ta = _canonicalize_tokens(_tokenize(val_a))
        tb = _canonicalize_tokens(_tokenize(val_b))
        if not ta or not tb:
            return False, 0.0
        sim = _jaccard(ta, tb)
        return sim >= 0.45, sim

    def evaluate_pair(
        self,
        a: SubtopicDescriptor,
        b: SubtopicDescriptor,
        lexical_retrieval_score: Optional[float] = None,
    ) -> SubtopicMatchProposal:
        """Evaluate whether two subtopics represent the same topic (possibly with opposing positions)."""
        if lexical_retrieval_score is None:
            lexical_retrieval_score = self.compute_lexical_retrieval_score(a, b)

        # If an external LLM semantic judge is supplied, allow it to supply structured judgements
        if self.semantic_judge_callable is not None:
            judgement = self.semantic_judge_callable(a, b)
            def_sim = float(judgement.get("definition_similarity", 0.0))
            ev_overlap = float(judgement.get("evidence_overlap", 0.0))
            obj_match = bool(judgement.get("decision_object_match", False))
            mech_match = bool(judgement.get("mechanism_match", False))
            scope_match = bool(judgement.get("scope_match", False))
            opposing = bool(judgement.get("opposing_alternatives", False))
            rationale = str(judgement.get("rationale", "Semantic judge evaluation."))
            explicit_decision = judgement.get("match_decision")
        else:
            # Deterministic structured matching over definitions, evidence, decision_object, mechanism, scope
            def_a = _canonicalize_tokens(_tokenize(f"{a.label} {a.definition}"))
            def_b = _canonicalize_tokens(_tokenize(f"{b.label} {b.definition}"))
            def_sim = round(_jaccard(def_a, def_b), 4)

            ev_union = (a.evidence_ids | a.response_ids) | (b.evidence_ids | b.response_ids)
            ev_inter = (a.evidence_ids & b.evidence_ids) | (a.response_ids & b.response_ids)
            ev_overlap = round(len(ev_inter) / len(ev_union), 4) if ev_union else 0.0

            obj_match, obj_sim = self._field_match(a.decision_object, b.decision_object)
            mech_match, mech_sim = self._field_match(a.mechanism, b.mechanism)
            scope_match, scope_sim = self._field_match(a.scope, b.scope)

            # Check whether alternatives are opposing or distinct positions on the same topic
            alt_set_a = {alt.lower().strip() for alt in a.alternatives if alt}
            alt_set_b = {alt.lower().strip() for alt in b.alternatives if alt}
            opposing = bool(alt_set_a and alt_set_b and alt_set_a != alt_set_b and not (alt_set_a & alt_set_b))
            explicit_decision = None
            rationale = (
                f"Structured comparison: def_sim={def_sim:.2f}, evidence_overlap={ev_overlap:.2f}, "
                f"decision_object_match={obj_match} ({obj_sim:.2f}), "
                f"mechanism_match={mech_match} ({mech_sim:.2f}), scope_match={scope_match} ({scope_sim:.2f})."
            )

        if explicit_decision in {
            "MATCH_SAME_TOPIC_SAME_POSITION",
            "MATCH_SAME_TOPIC_OPPOSING_ALTERNATIVES",
            "UNCERTAIN_FOR_AGENT_03",
            "NO_MATCH",
        }:
            decision = explicit_decision
        else:
            # Rule: NEVER merge on lexical overlap alone!
            # Require structured alignment across decision_object / mechanism / scope / definition / evidence.
            struct_matches = int(obj_match) + int(mech_match) + int(scope_match)
            if obj_match and (mech_match or scope_match or def_sim >= 0.45):
                if opposing:
                    decision = "MATCH_SAME_TOPIC_OPPOSING_ALTERNATIVES"
                else:
                    decision = "MATCH_SAME_TOPIC_SAME_POSITION"
            elif struct_matches >= 1 or def_sim >= 0.35 or ev_overlap >= 0.30:
                # Uncertain match: partial structural/definition/evidence overlap -> preserve for Agent 03
                decision = "UNCERTAIN_FOR_AGENT_03"
            else:
                decision = "NO_MATCH"

        requires_agent_03 = decision in {
            "UNCERTAIN_FOR_AGENT_03",
            "MATCH_SAME_TOPIC_OPPOSING_ALTERNATIVES",
        }
        match_hash = hashlib.sha256(
            f"{a.question_id}_{a.item_id}_{b.item_id}".encode("utf-8")
        ).hexdigest()[:12]

        return SubtopicMatchProposal(
            match_id=f"MATCH_{a.question_id}_{match_hash}",
            question_id=a.question_id,
            candidate_a_id=a.item_id,
            candidate_b_id=b.item_id,
            label_a=a.label,
            label_b=b.label,
            lexical_retrieval_score=round(lexical_retrieval_score, 4),
            definition_similarity=round(def_sim, 4),
            evidence_overlap=round(ev_overlap, 4),
            decision_object_match=obj_match,
            mechanism_match=mech_match,
            scope_match=scope_match,
            match_decision=decision,  # type: ignore[arg-type]
            rationale=rationale,
            requires_agent_03_adjudication=requires_agent_03,
        )

    def cluster_subtopics(
        self,
        descriptors: List[SubtopicDescriptor],
    ) -> Tuple[List[List[SubtopicDescriptor]], List[SubtopicMatchProposal]]:
        """Group strictly matched subtopics (including opposing-alternative same-topic matches)
        while preserving uncertain matches separately for Agent 03.

        Returns:
            (merged_groups, all_match_proposals)
        """
        if not descriptors:
            return [], []

        pairs = self.retrieve_candidate_pairs(descriptors, min_retrieval_threshold=0.0)
        proposals: List[SubtopicMatchProposal] = []

        # Disjoint-set union ONLY for clear MATCH_SAME_TOPIC_* decisions (never UNCERTAIN)
        parent = {i: i for i in range(len(descriptors))}
        id_to_idx = {d.item_id: i for i, d in enumerate(descriptors)}

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(x: int, y: int) -> None:
            rx, ry = find(x), find(y)
            if rx != ry:
                parent[ry] = rx

        for da, db, lex_score in pairs:
            prop = self.evaluate_pair(da, db, lexical_retrieval_score=lex_score)
            proposals.append(prop)
            if prop.match_decision in {
                "MATCH_SAME_TOPIC_SAME_POSITION",
                "MATCH_SAME_TOPIC_OPPOSING_ALTERNATIVES",
            }:
                union(id_to_idx[da.item_id], id_to_idx[db.item_id])

        groups_map: Dict[int, List[SubtopicDescriptor]] = {}
        for idx, d in enumerate(descriptors):
            root = find(idx)
            groups_map.setdefault(root, []).append(d)

        return list(groups_map.values()), proposals
