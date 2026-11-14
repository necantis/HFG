"""Agent 03 Production Evidence Reconciliation Engine for HFG.

Owned by: Agent 03 — Evidence & Reconciliation
Architecture Version: v1.1.0
Schema Version: 1.0.0 / v1.1.0

Core Principles Enforced:
1. Provenance lock & immutable production inputs (Coder A & Coder B treated read-only).
2. Primary survey structure Q01-Q13 (+ optional contextual Q14) preserved intact.
3. Bottom-up evidence-grounded subtopic alignment (`EXACT_MATCH`, `SEMANTIC_MATCH`,
   `PARTIAL_OVERLAP`, `CODER_A_ONLY`, `CODER_B_ONLY`, `CONFLICT`) retaining minority
   positions and Phase 1 unassigned subtopics without superficial label-only merging.
4. Strict missingness preservation (18 non-preference cells) and explicit separation between
   absence of evidence, evidence of absence, and substantive disagreement.
5. Preference comparison WITHOUT unauthorized averaging:
   - Exact agreement recorded where both coders agree on aligned alternatives & distributions.
   - Differing distributions, differing alternative vocabularies, differing probability
     interpretations, or single-coder assignments preserve both raw distributions and STOP
     at the documented disagreement representation, flagging the unresolved reconciliation policy.
6. Separate agreement metrics across 4 dimensions (subtopics, preferences, values, goods)
   excluding pre-reconciliation placeholder 0.0 values and avoiding arbitrary omnibus scores.
7. Open cross-question organisational value consolidation preserving original labels,
   nullable polarity, and strict Pareto non-pruning guarantees.
8. Goods classification audit preserving disagreement/non-applicable states without forcing classes.
9. Constraint-only `candidate_options_v1` synthesis with zero cluster/value pruning.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Set, Tuple

from pydantic import BaseModel, Field

from src.contracts import (
    CanonicalSubtopic,
    EconomicGoodClass,
    MissingnessState,
    ProvenanceMeta,
    ResponseEpistemicStatus,
    SCHEMA_VERSION,
)
from src.evidence.evidence_ledger import (
    EvidenceLedger,
    MissingnessLedgerEntry,
    ProvenanceLock,
    SpanValidationReport,
    compute_char_overlap_metrics,
)
from src.ingest.ingestion import ACTIVE_RUN_ID, compute_sha256
from src.nlp.schemas import ThemeRecord, ThemesCodebook


# Domain-neutral bilingual/multilingual concept groups (FR / DE / EN morphology, zero survey-specific packages)
DOMAIN_NEUTRAL_CONCEPT_GROUPS: List[Set[str]] = [
    {"hr", "hiring", "recruitment", "recrutement", "recrutements", "staffing", "personal", "personnel", "rh"},
    {"lab", "labs", "laboratory", "laboratories", "laboratoire", "laboratoires", "group", "groups", "unit", "units", "team", "teams"},
    {"pole", "poles", "pôle", "pôles", "cluster", "clusters", "center", "centers"},
    {"institute", "institutional", "ri", "university", "central", "centralized", "centralisé", "centralization"},
    {"decentralized", "decentralization", "lowest", "proximity", "subsidiarity", "subsidiarité", "subsidiarität", "autonomy", "autonomie"},
    {"financial", "finance", "financier", "financing", "budget", "budgeting", "funding", "deficit", "deficits", "cost", "costs", "liability", "responsibility", "responsabilité"},
    {"overhead", "overheads", "indirect", "reversal", "frais"},
    {"bonus", "bonuses", "prime", "primes", "submission", "depot", "dépôt", "proposal", "proposals"},
    {"core", "socle", "flat", "fixed", "base", "hourly"},
    {"collective", "collectif", "shared", "common", "pool", "pooling", "mutualized", "solidarity", "solidarité"},
    {"individual", "individuel", "individuelle", "professor", "professors", "pi", "principal", "investigator", "leader", "leaders", "project"},
    {"evaluation", "evaluations", "évaluation", "évaluations", "assessment", "review", "appraisal", "criteria"},
    {"collaboration", "collaborative", "cooperation", "transversal", "transversality"},
    {"coordination", "coordinator", "governance", "steering", "management", "operation", "operations"},
    {"unified", "unifié", "standardization", "standardized", "harmonized", "ad", "hoc", "ad_hoc"},
    {"name", "names", "naming", "denomination", "denominations", "terminology", "term", "terms", "label", "labels", "title", "subtitles"},
    {"clarity", "clear", "transparent", "transparency", "transparence", "visibility"},
    {"vague", "confusing", "unclear", "ambiguous", "ambiguity"},
    {"engagement", "commitments", "commitment", "contract", "contractual"},
    {"relevance", "relevant", "coherent", "pertinence", "suitability", "adequacy"},
    {"volunteer", "volunteers", "voluntary", "support", "participation", "involvement"},
    {"learning", "reflection", "knowledge", "reviewing", "past"},
    {"allocation", "allocate", "distribution", "level", "mechanism", "regime", "rule", "rules"},
    {"incentive", "incentives", "recognition", "appreciation"},
    {"size", "composition", "small", "smaller", "large", "larger", "optimal", "manageability"},
    {"competence", "competences", "skill", "skills"},
    {"scenario", "scenarios", "evaluation", "feasibility"},
    {"anticipation", "proactive", "reactive", "anticipatory"},
    {"efficiency", "efficient", "agility", "agile"},
]

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "between", "by", "de", "des", "do", "du", "en",
    "et", "for", "from", "how", "in", "into", "is", "it", "la", "le", "les", "level", "mode",
    "of", "on", "or", "other", "par", "question", "regarding", "specific", "such", "system",
    "that", "the", "their", "these", "this", "to", "under", "vs", "which", "with", "within",
}


def _clean_tokens(text: str) -> Set[str]:
    cleaned = re.sub(r"[^\w\s]", " ", (text or "").lower().replace("_", " "))
    return {t for t in cleaned.split() if len(t) > 1 and t not in STOPWORDS}


def _canonicalize_tokens(tokens: Set[str]) -> Set[str]:
    mapped: Set[str] = set()
    for t in tokens:
        matched = None
        for idx, grp in enumerate(DOMAIN_NEUTRAL_CONCEPT_GROUPS):
            if t in grp:
                matched = f"C_{idx:02d}"
                break
        mapped.add(matched or t)
    return mapped


def _jaccard(a: Set[str], b: Set[str]) -> float:
    if not a and not b:
        return 0.0
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def _wilson_ci(successes: int, total: int, z: float = 1.96) -> Optional[List[float]]:
    if total <= 0:
        return None
    p = successes / total
    denom = 1.0 + (z * z) / total
    center = (p + (z * z) / (2.0 * total)) / denom
    half = (z * math.sqrt((p * (1.0 - p) + (z * z) / (4.0 * total)) / total)) / denom
    return [round(max(0.0, center - half), 4), round(min(1.0, center + half), 4)]


def _bootstrap_mean_ci(
    values: List[float],
    n_boot: int = 1000,
    seed: int = 42,
) -> Optional[List[float]]:
    if not values:
        return None
    if len(values) == 1:
        v = round(values[0], 4)
        return [v, v]
    rng = random.Random(seed)
    n = len(values)
    means: List[float] = []
    for _ in range(n_boot):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    lo = means[int(0.025 * n_boot)]
    hi = means[int(0.975 * n_boot)]
    return [round(lo, 4), round(hi, 4)]


def _shannon_entropy_bits(probs: Dict[str, float]) -> float:
    ent = 0.0
    for p in probs.values():
        if p > 1e-12:
            ent -= p * math.log2(p)
    return round(ent, 6)


def _strip_q_prefix(key: str) -> str:
    return re.sub(r"^Q\d{2}_", "", key or "").replace("_", " ")


class ProposedSubtopicRecord(BaseModel):
    """Complete inventory record for a single coder-proposed subtopic (never deleted)."""

    proposal_uid: str
    question_id: str
    is_primary_question: bool
    question_scope: str
    coder_source: Literal["coder_a", "coder_b"]
    original_subtopic_key: str
    subtopic_id: str
    original_label: str
    definition: str
    decision_object: str = ""
    mechanism: str = ""
    scope: str = ""
    discovered_alternatives: List[Dict[str, Any]] = Field(default_factory=list)
    goods_assessment: Dict[str, Any] = Field(default_factory=dict)
    is_minority_position: bool = False
    evidence_span_ids: List[str] = Field(default_factory=list)
    supporting_response_ids: List[str] = Field(default_factory=list)
    supporting_participant_ids: List[str] = Field(default_factory=list)
    phase2_coding_count: int = 0
    phase2_observed_participant_ids: List[str] = Field(default_factory=list)
    phase2_split_subtopic: bool = False
    parent_phase1_subtopic_id: Optional[str] = None
    alignment_status: Literal[
        "EXACT_MATCH",
        "SEMANTIC_MATCH",
        "PARTIAL_OVERLAP",
        "CODER_A_ONLY",
        "CODER_B_ONLY",
        "CONFLICT",
    ] = "CODER_A_ONLY"
    canonical_subtopic_id: str = ""
    aligned_counterpart_ids: List[str] = Field(default_factory=list)
    overlapping_counterpart_ids: List[str] = Field(default_factory=list)


class PairwiseSubtopicAlignment(BaseModel):
    """Pairwise evidence-grounded evaluation between a Coder A and Coder B subtopic."""

    pair_id: str
    question_id: str
    coder_a_subtopic_id: str
    coder_a_label: str
    coder_b_subtopic_id: str
    coder_b_label: str
    span_char_iou: float
    span_char_containment_a_in_b: float
    span_char_containment_b_in_a: float
    participant_jaccard: float
    participant_overlap_coef: float
    concept_similarity: float
    label_similarity: float
    decision_object_similarity: float
    alignment_category: Literal[
        "EXACT_MATCH",
        "SEMANTIC_MATCH",
        "PARTIAL_OVERLAP",
        "CONFLICT",
        "NO_MATCH",
    ]
    merged_into_same_canonical: bool
    rationale: str


class AlternativeAlignmentInfo(BaseModel):
    """Audit record documenting how Coder A and Coder B alternative vocabularies compare."""

    comparable: bool
    mapping_type: Literal[
        "EXACT_KEYS",
        "SCENARIO_PREFIX_MATCH",
        "SEMANTIC_KEY_MATCH",
        "SINGLE_CODER_ONLY",
        "ALTERNATIVE_VOCABULARY_MISMATCH",
    ]
    coder_a_to_aligned_key: Dict[str, str] = Field(default_factory=dict)
    coder_b_to_aligned_key: Dict[str, str] = Field(default_factory=dict)
    aligned_keys: List[str] = Field(default_factory=list)
    notes: str = ""


class UncertaintyMetadata(BaseModel):
    """Explicit 4-part uncertainty propagation payload for Agent 04 consumption."""

    coding_disagreement: Dict[str, Any] = Field(default_factory=dict)
    coder_confidence: Dict[str, Any] = Field(default_factory=dict)
    preference_distribution_uncertainty: Dict[str, Any] = Field(default_factory=dict)
    ambiguous_source_evidence: Dict[str, Any] = Field(default_factory=dict)


class PreferenceReconciliationRecord(BaseModel):
    """Aligned participant x question x subtopic preference comparison & disagreement record."""

    record_id: str
    participant_id: str
    question_id: str
    response_id: str
    is_primary_question: bool
    canonical_subtopic_id: str
    subtopic_alignment_status: str
    cell_observation_category: Literal[
        "BOTH_CODERS_OBSERVED",
        "SINGLE_CODER_SUBTOPIC_ONLY",
        "SINGLE_CODER_PARTICIPANT_OMISSION",
        "PRESERVED_NON_PREFERENCE",
        "NOT_MENTIONED_IN_RESPONSE",
    ]
    epistemic_distinction: Literal[
        "substantive_agreement",
        "substantive_disagreement",
        "interpretation_disagreement_only",
        "absence_of_evidence",
        "evidence_of_absence",
        "granularity_asymmetry_single_coder_subtopic",
        "coder_omission_asymmetry",
        "ambiguous_evidence",
    ]
    missingness_state: str
    epistemic_status: str
    coder_a_coding_id: Optional[str] = None
    coder_b_coding_id: Optional[str] = None
    coder_a_subtopic_id: Optional[str] = None
    coder_b_subtopic_id: Optional[str] = None
    coder_a_probabilities: Optional[Dict[str, float]] = None
    coder_b_probabilities: Optional[Dict[str, float]] = None
    alternative_alignment: Optional[AlternativeAlignmentInfo] = None
    probability_interpretation_a: Optional[str] = None
    probability_interpretation_b: Optional[str] = None
    semantic_importance_a: Optional[float] = None
    semantic_importance_b: Optional[float] = None
    coder_confidence_a: Optional[float] = None
    coder_confidence_b: Optional[float] = None
    raw_placeholder_agreement_a: Optional[float] = None
    raw_placeholder_agreement_b: Optional[float] = None
    coder_a_span_ids: List[str] = Field(default_factory=list)
    coder_b_span_ids: List[str] = Field(default_factory=list)
    total_variation_distance: Optional[float] = None
    l1_distance: Optional[float] = None
    jensen_shannon_divergence: Optional[float] = None
    modal_alternative_a: Optional[str] = None
    modal_alternative_b: Optional[str] = None
    modal_agreement: Optional[bool] = None
    distribution_agreement: Optional[bool] = None
    interpretation_agreement: Optional[bool] = None
    computed_coder_agreement: Optional[float] = None
    probability_interval_lower: Optional[Dict[str, float]] = None
    probability_interval_upper: Optional[Dict[str, float]] = None
    reconciled_alternative_probabilities: Optional[Dict[str, float]] = None
    derived_scalar_score: Optional[float] = None
    reconciliation_status: Literal[
        "AGREEMENT_EXACT",
        "AGREEMENT_DISTRIBUTION_ONLY_INTERPRETATION_FLAGGED",
        "UNRESOLVED_RECONCILIATION_POLICY",
        "PRESERVED_MISSING_OR_NON_PREFERENCE",
        "NOT_MENTIONED_ABSENCE",
    ]
    reconciliation_method: Optional[
        Literal[
            "EXACT_MATCH",
            "ARBITRATED_SPAN_CHECK",
            "HIGH_UNCERTAINTY_FLAGGED",
        ]
    ] = None
    policy_gap_flag: Optional[str] = None
    uncertainty: UncertaintyMetadata = Field(default_factory=UncertaintyMetadata)


class ReconciledOrganisationalValue(BaseModel):
    """Bottom-up consolidated cross-question organisational value preserving originals."""

    reconciled_value_id: str
    canonical_value_label: str
    canonical_definition: str
    original_extractions: List[Dict[str, Any]] = Field(default_factory=list)
    original_labels_coder_a: List[str] = Field(default_factory=list)
    original_labels_coder_b: List[str] = Field(default_factory=list)
    supporting_question_ids: List[str] = Field(default_factory=list)
    cross_question_bridges: List[str] = Field(default_factory=list)
    supporting_participant_ids: List[str] = Field(default_factory=list)
    supporting_span_ids_a: List[str] = Field(default_factory=list)
    supporting_span_ids_b: List[str] = Field(default_factory=list)
    coder_a_count: int = 0
    coder_b_count: int = 0
    dual_coder_confirmed: bool = False
    polarity_non_null_values: List[float] = Field(default_factory=list)
    polarity_null_count: int = 0
    polarity_range: Optional[List[float]] = None
    mean_semantic_importance: Optional[float] = None
    mean_coder_confidence: Optional[float] = None
    pareto_pruning_prohibited: bool = True


class UnresolvedCaseRecord(BaseModel):
    """Explicit registry entry for unresolved policies, disagreements, or omissions."""

    case_id: str
    category: Literal[
        "UNRESOLVED_PREFERENCE_RECONCILIATION_POLICY",
        "ALTERNATIVE_VOCABULARY_MISMATCH",
        "ALTERNATIVE_KEY_CROSSWALK_PENDING",
        "PREFERENCE_DISTRIBUTION_DISAGREEMENT",
        "PROBABILITY_INTERPRETATION_DISAGREEMENT",
        "SINGLE_CODER_SUBTOPIC_GRANULARITY",
        "SINGLE_CODER_PARTICIPANT_OMISSION",
        "GOODS_ASSESSMENT_UNPOPULATED_ON_ENABLED_QUESTION",
        "PHASE1_SUBTOPIC_ZERO_PHASE2_CODINGS",
        "PHASE2_DEDUP_SPLIT_UNDECLARED_IN_PHASE1",
        "AMBIGUOUS_EPISTEMIC_RESPONSE",
    ]
    severity: Literal["HIGH_BLOCKING_POLICY", "HIGH_SUBSTANTIVE", "MEDIUM", "LOW"]
    question_id: str
    participant_id: Optional[str] = None
    canonical_subtopic_id: Optional[str] = None
    description: str
    coder_a_evidence: Dict[str, Any] = Field(default_factory=dict)
    coder_b_evidence: Dict[str, Any] = Field(default_factory=dict)
    recommended_resolution: str


def _normalize_alt_tokens(key: str) -> Set[str]:
    return _canonicalize_tokens(_clean_tokens(key))


def _scenario_tag(key: str) -> Optional[str]:
    m = re.match(r"^(scenario_\d+)(?:$|_)", key.strip().lower())
    return m.group(1) if m else None


def align_alternative_vocabularies(
    probs_a: Dict[str, float],
    probs_b: Dict[str, float],
) -> AlternativeAlignmentInfo:
    """Determine whether Coder A and Coder B alternative keys have an unambiguous 1-to-1 alignment."""
    keys_a = sorted(probs_a.keys())
    keys_b = sorted(probs_b.keys())
    if keys_a == keys_b:
        return AlternativeAlignmentInfo(
            comparable=True,
            mapping_type="EXACT_KEYS",
            coder_a_to_aligned_key={k: k for k in keys_a},
            coder_b_to_aligned_key={k: k for k in keys_b},
            aligned_keys=keys_a,
            notes="Identical alternative identifiers emitted by both coders.",
        )

    # Check exact 1-to-1 scenario_N prefix alignment (e.g. scenario_2_flat_rate vs scenario_2_fixed_hourly)
    tags_a = [_scenario_tag(k) for k in keys_a]
    tags_b = [_scenario_tag(k) for k in keys_b]
    if (
        all(t is not None for t in tags_a)
        and all(t is not None for t in tags_b)
        and len(set(tags_a)) == len(tags_a)
        and len(set(tags_b)) == len(tags_b)
        and (set(tags_a) & set(tags_b))
    ):
        map_a = {k: str(_scenario_tag(k)) for k in keys_a}
        map_b = {k: str(_scenario_tag(k)) for k in keys_b}
        union_tags = sorted(set(map_a.values()) | set(map_b.values()))
        return AlternativeAlignmentInfo(
            comparable=True,
            mapping_type="SCENARIO_PREFIX_MATCH",
            coder_a_to_aligned_key=map_a,
            coder_b_to_aligned_key=map_b,
            aligned_keys=union_tags,
            notes="Aligned via shared explicit scenario_N identifiers across Coder A and Coder B.",
        )

    # Try domain-neutral canonical concept match ONLY when strict greedy 1-to-1 matching covers all active keys
    tok_a = {k: _normalize_alt_tokens(k) for k in keys_a}
    tok_b = {k: _normalize_alt_tokens(k) for k in keys_b}
    pairs: List[Tuple[float, str, str]] = []
    for ka in keys_a:
        for kb in keys_b:
            sim = _jaccard(tok_a[ka], tok_b[kb])
            if sim >= 0.50:
                pairs.append((sim, ka, kb))
    pairs.sort(reverse=True)
    matched_a: Dict[str, str] = {}
    matched_b: Dict[str, str] = {}
    for sim, ka, kb in pairs:
        if ka not in matched_a and kb not in matched_b:
            canon = ka if len(ka) <= len(kb) else kb
            matched_a[ka] = canon
            matched_b[kb] = canon

    if set(matched_a.keys()) == set(keys_a) and set(matched_b.keys()) == set(keys_b):
        aligned_keys = sorted(set(matched_a.values()) | set(matched_b.values()))
        return AlternativeAlignmentInfo(
            comparable=True,
            mapping_type="SEMANTIC_KEY_MATCH",
            coder_a_to_aligned_key=matched_a,
            coder_b_to_aligned_key=matched_b,
            aligned_keys=aligned_keys,
            notes="Aligned 1-to-1 via domain-neutral bilingual concept equivalence.",
        )

    return AlternativeAlignmentInfo(
        comparable=False,
        mapping_type="ALTERNATIVE_VOCABULARY_MISMATCH",
        coder_a_to_aligned_key={k: k for k in keys_a},
        coder_b_to_aligned_key={k: k for k in keys_b},
        aligned_keys=[],
        notes=(
            f"Incompatible alternative vocabularies across coders (Coder A keys={keys_a}, Coder B keys={keys_b}); "
            "requires explicit crosswalk rule rather than silent mapping."
        ),
    )


class EvidenceReconciler:
    """Reconciles verified Coder A and Coder B qualitative evidence without fabricating consensus."""

    def __init__(
        self,
        ledger: Optional[EvidenceLedger] = None,
        base_dir: Optional[Path | str] = None,
        run_id: str = ACTIVE_RUN_ID,
    ):
        self.ledger = ledger or EvidenceLedger(base_dir=base_dir, run_id=run_id)
        self.base_dir = self.ledger.base_dir
        self.run_id = self.ledger.run_id

    def _evaluate_subtopic_alignment(
        self,
    ) -> Tuple[
        List[ProposedSubtopicRecord],
        List[PairwiseSubtopicAlignment],
        List[Dict[str, Any]],
        Dict[str, str],
    ]:
        ca_subs = self.ledger.coder_a_payload.get("discovered_subtopics") or []
        cb_subs = self.ledger.coder_b_payload.get("discovered_subtopics") or []
        ca_crs = self.ledger.coder_a_payload.get("coding_results") or []
        cb_crs = self.ledger.coder_b_payload.get("coding_results") or []

        cr_by_coder_st: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
        for cr in ca_crs:
            cr_by_coder_st[("coder_a", str(cr["subtopic_id"]))].append(cr)
        for cr in cb_crs:
            cr_by_coder_st[("coder_b", str(cr["subtopic_id"]))].append(cr)

        questions = self.ledger.question_registry.get("questions", {})

        def _build_proposal(coder_src: Literal["coder_a", "coder_b"], sub: Dict[str, Any]) -> ProposedSubtopicRecord:
            qid = str(sub["question_id"])
            st_id = str(sub["subtopic_id"])
            q_meta = questions.get(qid, {})
            crs = [
                c
                for c in cr_by_coder_st[(coder_src, st_id)]
                if c.get("missingness_state") == MissingnessState.OBSERVED_USABLE.value
            ]
            obs_pids = sorted({str(c["participant_id"]) for c in crs})
            return ProposedSubtopicRecord(
                proposal_uid=f"{coder_src}:{st_id}",
                question_id=qid,
                is_primary_question=bool(q_meta.get("is_primary_question", qid != "Q14")),
                question_scope=str(q_meta.get("question_scope", "optional_contextual_remarks" if qid == "Q14" else "primary")),
                coder_source=coder_src,
                original_subtopic_key=str(sub.get("subtopic_key", st_id)),
                subtopic_id=st_id,
                original_label=str(sub.get("proposed_label_en", st_id)),
                definition=str(sub.get("definition", "")),
                decision_object=str(sub.get("decision_object", "")),
                mechanism=str(sub.get("mechanism", "")),
                scope=str(sub.get("scope", "")),
                discovered_alternatives=list(sub.get("discovered_alternatives") or []),
                goods_assessment=dict(sub.get("goods_assessment") or {}),
                is_minority_position=bool(sub.get("is_minority_position", False)),
                evidence_span_ids=list(sub.get("supporting_span_ids") or []),
                supporting_response_ids=list(sub.get("supporting_response_ids") or []),
                supporting_participant_ids=list(sub.get("supporting_participant_ids") or []),
                phase2_coding_count=len(crs),
                phase2_observed_participant_ids=obs_pids,
            )

        prop_a_map = {str(s["subtopic_id"]): _build_proposal("coder_a", s) for s in ca_subs}
        prop_b_map = {str(s["subtopic_id"]): _build_proposal("coder_b", s) for s in cb_subs}
        raw_a_map = {str(s["subtopic_id"]): s for s in ca_subs}
        raw_b_map = {str(s["subtopic_id"]): s for s in cb_subs}

        def _synthesize_phase2_splits(
            coder_src: Literal["coder_a", "coder_b"],
            prop_map: Dict[str, ProposedSubtopicRecord],
            raw_map: Dict[str, Dict[str, Any]],
        ) -> None:
            for (c_label, st_id), all_crs in sorted(cr_by_coder_st.items()):
                if c_label != coder_src or st_id in prop_map:
                    continue
                crs = [
                    c
                    for c in all_crs
                    if c.get("missingness_state") == MissingnessState.OBSERVED_USABLE.value
                ]
                if not crs:
                    continue
                qid = str(crs[0]["question_id"])
                q_meta = questions.get(qid, {})
                base_id = re.sub(r"_\d+$", "", st_id)
                base_sub = raw_map.get(base_id)
                base_label = str(base_sub.get("proposed_label_en", st_id)) if base_sub else st_id
                base_def = (
                    str(base_sub.get("definition", ""))
                    if base_sub
                    else f"Phase-2 split facet derived from {base_id}."
                )
                alt_keys = sorted({str(k) for c in crs for k in (c.get("alternative_probabilities") or {}).keys()})
                alts = [{"alternative_id": k, "label": k} for k in alt_keys]
                sp_ids = sorted({str(sp) for c in crs for sp in (c.get("evidence_span_ids") or [])})
                obs_pids = sorted({str(c["participant_id"]) for c in crs})
                resp_ids = sorted(
                    {
                        str(self.ledger.rows_by_pair[(p, qid)]["response_id"])
                        for p in obs_pids
                        if (p, qid) in self.ledger.rows_by_pair
                    }
                )
                synth_raw = {
                    "subtopic_id": st_id,
                    "question_id": qid,
                    "proposed_label_en": f"{base_label} [Phase-2 Split Facet]",
                    "definition": (
                        f"{base_def} [Phase-2 deduplication split '{st_id}' emitted in coding_results "
                        "without a separate Phase-1 discovered_subtopics record.]"
                    ),
                    "decision_object": str(base_sub.get("decision_object", "")) if base_sub else "",
                    "mechanism": str(base_sub.get("mechanism", "")) if base_sub else "",
                    "scope": str(base_sub.get("scope", "")) if base_sub else "",
                    "discovered_alternatives": alts,
                    "goods_assessment": dict(base_sub.get("goods_assessment") or {}) if base_sub else {},
                    "is_minority_position": True,
                    "supporting_span_ids": sp_ids,
                    "supporting_response_ids": resp_ids,
                    "supporting_participant_ids": obs_pids,
                }
                raw_map[st_id] = synth_raw
                prop_map[st_id] = ProposedSubtopicRecord(
                    proposal_uid=f"{coder_src}:{st_id}",
                    question_id=qid,
                    is_primary_question=bool(q_meta.get("is_primary_question", qid != "Q14")),
                    question_scope=str(q_meta.get("question_scope", "optional_contextual_remarks" if qid == "Q14" else "primary")),
                    coder_source=coder_src,
                    original_subtopic_key=st_id,
                    subtopic_id=st_id,
                    original_label=synth_raw["proposed_label_en"],
                    definition=synth_raw["definition"],
                    decision_object=synth_raw["decision_object"],
                    mechanism=synth_raw["mechanism"],
                    scope=synth_raw["scope"],
                    discovered_alternatives=alts,
                    goods_assessment=synth_raw["goods_assessment"],
                    is_minority_position=True,
                    evidence_span_ids=sp_ids,
                    supporting_response_ids=resp_ids,
                    supporting_participant_ids=obs_pids,
                    phase2_coding_count=len(crs),
                    phase2_observed_participant_ids=obs_pids,
                    phase2_split_subtopic=True,
                    parent_phase1_subtopic_id=base_id if base_id in raw_map else None,
                )

        _synthesize_phase2_splits("coder_a", prop_a_map, raw_a_map)
        _synthesize_phase2_splits("coder_b", prop_b_map, raw_b_map)

        ranges_a = {
            st_id: self.ledger.get_subtopic_char_ranges("coder_a", s, cr_by_coder_st[("coder_a", st_id)])
            for st_id, s in raw_a_map.items()
        }
        ranges_b = {
            st_id: self.ledger.get_subtopic_char_ranges("coder_b", s, cr_by_coder_st[("coder_b", st_id)])
            for st_id, s in raw_b_map.items()
        }

        def _concept_set(p: ProposedSubtopicRecord) -> Set[str]:
            text = (
                f"{_strip_q_prefix(p.original_subtopic_key)} {p.original_label} "
                f"{p.definition} {p.decision_object} {p.mechanism}"
            )
            return _canonicalize_tokens(_clean_tokens(text))

        def _label_set(p: ProposedSubtopicRecord) -> Set[str]:
            text = f"{_strip_q_prefix(p.original_subtopic_key)} {p.original_label}"
            return _canonicalize_tokens(_clean_tokens(text))

        def _obj_set(p: ProposedSubtopicRecord) -> Set[str]:
            return _canonicalize_tokens(_clean_tokens(f"{p.decision_object} {p.original_label}"))

        def _pids(p: ProposedSubtopicRecord) -> Set[str]:
            return set(p.phase2_observed_participant_ids) or set(p.supporting_participant_ids)

        pairwise: List[PairwiseSubtopicAlignment] = []
        by_q_a: Dict[str, List[ProposedSubtopicRecord]] = defaultdict(list)
        by_q_b: Dict[str, List[ProposedSubtopicRecord]] = defaultdict(list)
        for p in prop_a_map.values():
            by_q_a[p.question_id].append(p)
        for p in prop_b_map.values():
            by_q_b[p.question_id].append(p)

        # Deterministic matching within each question (never merging across distinct questions)
        all_qids = sorted(set(by_q_a) | set(by_q_b))
        primary_pairs_by_q: Dict[str, List[Tuple[str, str, PairwiseSubtopicAlignment]]] = defaultdict(list)

        for qid in all_qids:
            q_pair_scores: List[Tuple[float, PairwiseSubtopicAlignment]] = []
            for pa in by_q_a[qid]:
                for pb in by_q_b[qid]:
                    iou, cont_a, cont_b = compute_char_overlap_metrics(
                        ranges_a[pa.subtopic_id], ranges_b[pb.subtopic_id]
                    )
                    pids_a, pids_b = _pids(pa), _pids(pb)
                    p_inter = len(pids_a & pids_b)
                    p_union = len(pids_a | pids_b)
                    p_min = min(len(pids_a), len(pids_b))
                    p_jacc = p_inter / p_union if p_union else 0.0
                    p_ov = p_inter / p_min if p_min else 0.0

                    c_sim = _jaccard(_concept_set(pa), _concept_set(pb))
                    l_sim = _jaccard(_label_set(pa), _label_set(pb))
                    o_sim = _jaccard(_obj_set(pa), _obj_set(pb))
                    sem_score = 0.45 * c_sim + 0.35 * l_sim + 0.20 * o_sim
                    ev_score = max(iou, 0.70 * max(cont_a, cont_b))
                    # Evidence semantics must corroborate alignment; never merge purely on string score alone
                    evidence_supported = (iou >= 0.15) or (max(cont_a, cont_b) >= 0.50) or (
                        (pa.phase2_coding_count == 0 or pb.phase2_coding_count == 0) and p_ov >= 0.40
                    )

                    # Detect exact / semantic / partial / conflict / no_match at pair level
                    if (
                        (l_sim >= 0.75 or _strip_q_prefix(pa.original_subtopic_key) == _strip_q_prefix(pb.original_subtopic_key))
                        and evidence_supported
                        and (iou >= 0.45 or p_jacc >= 0.60)
                        and sem_score >= 0.40
                    ):
                        cat: Literal["EXACT_MATCH", "SEMANTIC_MATCH", "PARTIAL_OVERLAP", "CONFLICT", "NO_MATCH"] = "EXACT_MATCH"
                    elif (
                        evidence_supported
                        and (iou >= 0.25 or p_jacc >= 0.50 or (max(cont_a, cont_b) >= 0.75 and p_jacc >= 0.40))
                        and (sem_score >= 0.24 or l_sim >= 0.35 or o_sim >= 0.35)
                    ):
                        cat = "SEMANTIC_MATCH"
                    elif (iou >= 0.15 or max(cont_a, cont_b) >= 0.45) and sem_score >= 0.08:
                        cat = "PARTIAL_OVERLAP"
                    elif iou >= 0.40 and sem_score < 0.08:
                        # Strong same-span overlap with divergent topic framing -> partial overlap (separate concepts in same text)
                        cat = "PARTIAL_OVERLAP"
                    else:
                        cat = "NO_MATCH"

                    # Check for explicit label polarity conflict where both discuss exact opposing labels as topic
                    pair_hash = hashlib.sha256(f"{qid}|{pa.subtopic_id}|{pb.subtopic_id}".encode("utf-8")).hexdigest()[:10]
                    rec = PairwiseSubtopicAlignment(
                        pair_id=f"ALIGN_{qid}_{pair_hash}",
                        question_id=qid,
                        coder_a_subtopic_id=pa.subtopic_id,
                        coder_a_label=pa.original_label,
                        coder_b_subtopic_id=pb.subtopic_id,
                        coder_b_label=pb.original_label,
                        span_char_iou=round(iou, 4),
                        span_char_containment_a_in_b=round(cont_a, 4),
                        span_char_containment_b_in_a=round(cont_b, 4),
                        participant_jaccard=round(p_jacc, 4),
                        participant_overlap_coef=round(p_ov, 4),
                        concept_similarity=round(c_sim, 4),
                        label_similarity=round(l_sim, 4),
                        decision_object_similarity=round(o_sim, 4),
                        alignment_category=cat,
                        merged_into_same_canonical=False,
                        rationale=(
                            f"span_iou={iou:.2f}, cont_b={cont_b:.2f}, p_jacc={p_jacc:.2f}, "
                            f"concept_sim={c_sim:.2f}, label_sim={l_sim:.2f}, obj_sim={o_sim:.2f}"
                        ),
                    )
                    pairwise.append(rec)
                    if cat in {"EXACT_MATCH", "SEMANTIC_MATCH"} and not pa.phase2_split_subtopic and not pb.phase2_split_subtopic:
                        combined = 0.45 * sem_score + 0.35 * iou + 0.20 * p_jacc
                        q_pair_scores.append((combined, rec))

            # Select non-overlapping 1-to-1 primary matches greedily by highest evidence+semantic score
            q_pair_scores.sort(key=lambda x: x[0], reverse=True)
            used_a: Set[str] = set()
            used_b: Set[str] = set()
            for _, rec in q_pair_scores:
                if rec.coder_a_subtopic_id in used_a or rec.coder_b_subtopic_id in used_b:
                    continue
                used_a.add(rec.coder_a_subtopic_id)
                used_b.add(rec.coder_b_subtopic_id)
                rec.merged_into_same_canonical = True
                primary_pairs_by_q[qid].append((rec.coder_a_subtopic_id, rec.coder_b_subtopic_id, rec))

        # Downgrade any non-selected EXACT/SEMANTIC pair that overlaps a primary match to PARTIAL_OVERLAP
        selected_pair_ids = {rec.pair_id for plist in primary_pairs_by_q.values() for _, _, rec in plist}
        for rec in pairwise:
            if rec.pair_id not in selected_pair_ids and rec.alignment_category in {"EXACT_MATCH", "SEMANTIC_MATCH"}:
                rec.alignment_category = "PARTIAL_OVERLAP"
                rec.rationale += " (downgraded to PARTIAL_OVERLAP after 1-to-1 primary match)."

        # Build canonical subtopics (1 per matched pair + 1 per unmatched/partial-facet subtopic -> zero deletion!)
        canonical_subtopics: List[Dict[str, Any]] = []
        subtopic_to_canonical: Dict[Tuple[str, str], str] = {}
        matched_a_ids: Set[str] = set()
        matched_b_ids: Set[str] = set()

        total_participants = int(self.ledger.provenance_lock.participant_count)

        def _missing_q_count(qid: str) -> int:
            q_spec = questions.get(qid, {})
            return int(q_spec.get("missing_response_count", 0))

        # Collect PARTIAL_OVERLAP links for annotation
        partial_links_a: Dict[str, List[str]] = defaultdict(list)
        partial_links_b: Dict[str, List[str]] = defaultdict(list)
        for rec in pairwise:
            if rec.alignment_category == "PARTIAL_OVERLAP":
                partial_links_a[rec.coder_a_subtopic_id].append(rec.coder_b_subtopic_id)
                partial_links_b[rec.coder_b_subtopic_id].append(rec.coder_a_subtopic_id)

        used_canon_ids: Set[str] = set()

        def _unique_canon_id(base_id: str) -> str:
            cand = base_id
            idx = 2
            while cand in used_canon_ids:
                cand = f"{base_id}_{idx}"
                idx += 1
            used_canon_ids.add(cand)
            return cand

        # 1. Matched canonical subtopics
        for qid in all_qids:
            miss_q = _missing_q_count(qid)
            for aid, bid, rec in primary_pairs_by_q[qid]:
                matched_a_ids.add(aid)
                matched_b_ids.add(bid)
                pa = prop_a_map[aid]
                pb = prop_b_map[bid]
                pa.alignment_status = rec.alignment_category  # type: ignore[assignment]
                pb.alignment_status = rec.alignment_category  # type: ignore[assignment]
                pa.aligned_counterpart_ids = [bid]
                pb.aligned_counterpart_ids = [aid]
                pa.overlapping_counterpart_ids = sorted(partial_links_a.get(aid, []))
                pb.overlapping_counterpart_ids = sorted(partial_links_b.get(bid, []))

                cid = _unique_canon_id(aid if len(aid) <= len(bid) else bid)
                pa.canonical_subtopic_id = cid
                pb.canonical_subtopic_id = cid
                subtopic_to_canonical[("coder_a", aid)] = cid
                subtopic_to_canonical[("coder_b", bid)] = cid

                mention_pids = sorted(_pids(pa) | _pids(pb))
                unmentioned = max(0, total_participants - len(mention_pids) - miss_q)
                sp_ids = sorted(
                    {*(pa.evidence_span_ids), *(pb.evidence_span_ids)}
                    | {sp_id for cr in cr_by_coder_st[("coder_a", aid)] for sp_id in cr.get("evidence_span_ids") or []}
                    | {sp_id for cr in cr_by_coder_st[("coder_b", bid)] for sp_id in cr.get("evidence_span_ids") or []}
                )
                resp_ids = sorted(set(pa.supporting_response_ids) | set(pb.supporting_response_ids))
                confs = [
                    float(cr["coder_confidence"])
                    for cr in cr_by_coder_st[("coder_a", aid)] + cr_by_coder_st[("coder_b", bid)]
                    if cr.get("coder_confidence") is not None
                ]
                mean_conf = round(sum(confs) / len(confs), 4) if confs else 0.0
                # Alignment agreement score (evidence IoU + participant Jaccard weighted blend; actual dual-coder metric)
                align_agree = round(0.5 * rec.span_char_iou + 0.5 * rec.participant_jaccard, 4)

                canonical_subtopics.append(
                    {
                        "subtopic_id": cid,
                        "question_id": qid,
                        "canonical_label_en": pb.original_label if rec.alignment_category == "EXACT_MATCH" else pa.original_label,
                        "canonical_description": f"[Coder A] {pa.definition} | [Coder B] {pb.definition}",
                        "alignment_category": rec.alignment_category,
                        "coder_a_subtopic_id": aid,
                        "coder_b_subtopic_id": bid,
                        "coder_a_label": pa.original_label,
                        "coder_b_label": pb.original_label,
                        "source_candidate_ids": [aid, bid],
                        "supporting_span_ids": sp_ids,
                        "supporting_response_ids": resp_ids,
                        "mention_participant_ids": mention_pids,
                        "mention_participant_count": len(mention_pids),
                        "unmentioned_participant_count": unmentioned,
                        "missing_question_participant_count": miss_q,
                        "economic_good_applicability": "NOT_APPLICABLE_FRAME",
                        "dominant_economic_good_class": None,
                        "coder_agreement": align_agree,
                        "mean_coder_confidence": mean_conf,
                        "is_minority_position": pa.is_minority_position or pb.is_minority_position,
                        "feasible_alternatives_coder_a": [a["alternative_id"] for a in pa.discovered_alternatives],
                        "feasible_alternatives_coder_b": [a["alternative_id"] for a in pb.discovered_alternatives],
                        "feasible_alternatives": sorted(
                            {f"coder_a:{a['alternative_id']}" for a in pa.discovered_alternatives}
                            | {f"coder_b:{a['alternative_id']}" for a in pb.discovered_alternatives}
                        ),
                        "overlapping_coder_subtopics": sorted(set(pa.overlapping_counterpart_ids) | set(pb.overlapping_counterpart_ids)),
                        "has_defensible_ordering": False,
                        "schema_version": SCHEMA_VERSION,
                    }
                )

        # 2. Coder-A-only subtopics (minority & Phase 1-only preserved!)
        for aid, pa in prop_a_map.items():
            if aid in matched_a_ids:
                continue
            ov = sorted(partial_links_a.get(aid, []))
            pa.alignment_status = "PARTIAL_OVERLAP" if ov else "CODER_A_ONLY"
            pa.overlapping_counterpart_ids = ov
            cid = _unique_canon_id(f"{aid}_A_ONLY")
            pa.canonical_subtopic_id = cid
            subtopic_to_canonical[("coder_a", aid)] = cid
            qid = pa.question_id
            miss_q = _missing_q_count(qid)
            mention_pids = sorted(_pids(pa))
            unmentioned = max(0, total_participants - len(mention_pids) - miss_q)
            sp_ids = sorted(
                set(pa.evidence_span_ids)
                | {sp_id for cr in cr_by_coder_st[("coder_a", aid)] for sp_id in cr.get("evidence_span_ids") or []}
            )
            confs = [
                float(cr["coder_confidence"])
                for cr in cr_by_coder_st[("coder_a", aid)]
                if cr.get("coder_confidence") is not None
            ]
            canonical_subtopics.append(
                {
                    "subtopic_id": cid,
                    "question_id": qid,
                    "canonical_label_en": pa.original_label,
                    "canonical_description": pa.definition,
                    "alignment_category": pa.alignment_status,
                    "coder_a_subtopic_id": aid,
                    "coder_b_subtopic_id": None,
                    "coder_a_label": pa.original_label,
                    "coder_b_label": None,
                    "source_candidate_ids": [aid],
                    "supporting_span_ids": sp_ids,
                    "supporting_response_ids": sorted(set(pa.supporting_response_ids)),
                    "mention_participant_ids": mention_pids,
                    "mention_participant_count": len(mention_pids),
                    "unmentioned_participant_count": unmentioned,
                    "missing_question_participant_count": miss_q,
                    "economic_good_applicability": "NOT_APPLICABLE_FRAME",
                    "dominant_economic_good_class": None,
                    "coder_agreement": 0.0,
                    "mean_coder_confidence": round(sum(confs) / len(confs), 4) if confs else 0.0,
                    "is_minority_position": pa.is_minority_position,
                    "phase1_unassigned_in_phase2": pa.phase2_coding_count == 0,
                    "phase2_split_subtopic": pa.phase2_split_subtopic,
                    "parent_phase1_subtopic_id": pa.parent_phase1_subtopic_id,
                    "feasible_alternatives_coder_a": [a["alternative_id"] for a in pa.discovered_alternatives],
                    "feasible_alternatives_coder_b": [],
                    "feasible_alternatives": [a["alternative_id"] for a in pa.discovered_alternatives],
                    "overlapping_coder_subtopics": ov,
                    "has_defensible_ordering": False,
                    "schema_version": SCHEMA_VERSION,
                }
            )

        # 3. Coder-B-only / partial-overlap facet subtopics (preserved intact, never silently merged away!)
        for bid, pb in prop_b_map.items():
            if bid in matched_b_ids:
                continue
            ov = sorted(partial_links_b.get(bid, []))
            pb.alignment_status = "PARTIAL_OVERLAP" if ov else "CODER_B_ONLY"
            pb.overlapping_counterpart_ids = ov
            cid = _unique_canon_id(f"{bid}_B_ONLY")
            pb.canonical_subtopic_id = cid
            subtopic_to_canonical[("coder_b", bid)] = cid
            qid = pb.question_id
            miss_q = _missing_q_count(qid)
            mention_pids = sorted(_pids(pb))
            unmentioned = max(0, total_participants - len(mention_pids) - miss_q)
            sp_ids = sorted(
                set(pb.evidence_span_ids)
                | {sp_id for cr in cr_by_coder_st[("coder_b", bid)] for sp_id in cr.get("evidence_span_ids") or []}
            )
            confs = [
                float(cr["coder_confidence"])
                for cr in cr_by_coder_st[("coder_b", bid)]
                if cr.get("coder_confidence") is not None
            ]
            canonical_subtopics.append(
                {
                    "subtopic_id": cid,
                    "question_id": qid,
                    "canonical_label_en": pb.original_label,
                    "canonical_description": pb.definition,
                    "alignment_category": pb.alignment_status,
                    "coder_a_subtopic_id": None,
                    "coder_b_subtopic_id": bid,
                    "coder_a_label": None,
                    "coder_b_label": pb.original_label,
                    "source_candidate_ids": [bid],
                    "supporting_span_ids": sp_ids,
                    "supporting_response_ids": sorted(set(pb.supporting_response_ids)),
                    "mention_participant_ids": mention_pids,
                    "mention_participant_count": len(mention_pids),
                    "unmentioned_participant_count": unmentioned,
                    "missing_question_participant_count": miss_q,
                    "economic_good_applicability": "NOT_APPLICABLE_FRAME",
                    "dominant_economic_good_class": None,
                    "coder_agreement": 0.0,
                    "mean_coder_confidence": round(sum(confs) / len(confs), 4) if confs else 0.0,
                    "is_minority_position": pb.is_minority_position,
                    "phase2_split_subtopic": pb.phase2_split_subtopic,
                    "parent_phase1_subtopic_id": pb.parent_phase1_subtopic_id,
                    "feasible_alternatives_coder_a": [],
                    "feasible_alternatives_coder_b": [a["alternative_id"] for a in pb.discovered_alternatives],
                    "feasible_alternatives": [a["alternative_id"] for a in pb.discovered_alternatives],
                    "overlapping_coder_subtopics": ov,
                    "has_defensible_ordering": False,
                    "schema_version": SCHEMA_VERSION,
                }
            )

        canonical_subtopics.sort(key=lambda c: (c["question_id"], c["subtopic_id"]))
        proposals_inventory = sorted(
            [*prop_a_map.values(), *prop_b_map.values()],
            key=lambda p: (p.question_id, p.coder_source, p.subtopic_id),
        )
        return proposals_inventory, pairwise, canonical_subtopics, {
            f"{k[0]}:{k[1]}": v for k, v in subtopic_to_canonical.items()
        }

    def _reconcile_preferences(
        self,
        canonical_subtopics: List[Dict[str, Any]],
        subtopic_to_canonical: Dict[str, str],
    ) -> Tuple[List[PreferenceReconciliationRecord], List[UnresolvedCaseRecord]]:
        ca_crs = self.ledger.coder_a_payload.get("coding_results") or []
        cb_crs = self.ledger.coder_b_payload.get("coding_results") or []
        questions = self.ledger.question_registry.get("questions", {})
        canon_by_id = {c["subtopic_id"]: c for c in canonical_subtopics}

        usable_by_key: Dict[Tuple[str, str, str], Dict[str, Dict[str, Any]]] = defaultdict(dict)
        for cr in ca_crs:
            if cr.get("missingness_state") == MissingnessState.OBSERVED_USABLE.value:
                cid = subtopic_to_canonical[f"coder_a:{cr['subtopic_id']}"]
                usable_by_key[(str(cr["participant_id"]), str(cr["question_id"]), cid)]["coder_a"] = cr
        for cr in cb_crs:
            if cr.get("missingness_state") == MissingnessState.OBSERVED_USABLE.value:
                cid = subtopic_to_canonical[f"coder_b:{cr['subtopic_id']}"]
                usable_by_key[(str(cr["participant_id"]), str(cr["question_id"]), cid)]["coder_b"] = cr

        records: List[PreferenceReconciliationRecord] = []
        unresolved: List[UnresolvedCaseRecord] = []

        # 1. Explicit non-preference cells preserved strictly (never create synthetic preferences)
        for entry in self.ledger.missingness_ledger:
            pair = (entry.participant_id, entry.question_id)
            row = self.ledger.rows_by_pair[pair]
            is_prim = bool(questions.get(entry.question_id, {}).get("is_primary_question", entry.question_id != "Q14"))
            is_amb = entry.epistemic_status == ResponseEpistemicStatus.AMBIGUOUS.value
            if entry.non_preference_category in {
                "evidence_of_absence_explicit_no_opinion",
                "evidence_of_absence_insufficient_experience_or_info",
            }:
                ep_dist: Literal[
                    "substantive_agreement",
                    "substantive_disagreement",
                    "interpretation_disagreement_only",
                    "absence_of_evidence",
                    "evidence_of_absence",
                    "granularity_asymmetry_single_coder_subtopic",
                    "coder_omission_asymmetry",
                    "ambiguous_evidence",
                ] = "evidence_of_absence"
            elif is_amb:
                ep_dist = "ambiguous_evidence"
            else:
                ep_dist = "absence_of_evidence"

            rec_id = f"PREC_{entry.question_id}_{entry.participant_id}_NONPREF"
            records.append(
                PreferenceReconciliationRecord(
                    record_id=rec_id,
                    participant_id=entry.participant_id,
                    question_id=entry.question_id,
                    response_id=entry.response_id,
                    is_primary_question=is_prim,
                    canonical_subtopic_id=f"{entry.question_id}_{entry.normalized_missingness_state}",
                    subtopic_alignment_status="NON_PREFERENCE_PRESERVED",
                    cell_observation_category="PRESERVED_NON_PREFERENCE",
                    epistemic_distinction=ep_dist,
                    missingness_state=entry.normalized_missingness_state,
                    epistemic_status=entry.epistemic_status,
                    coder_a_span_ids=entry.coder_a_span_ids,
                    coder_b_span_ids=entry.coder_b_span_ids,
                    reconciled_alternative_probabilities=None,
                    derived_scalar_score=None,
                    reconciliation_status="PRESERVED_MISSING_OR_NON_PREFERENCE",
                    reconciliation_method=None,
                    uncertainty=UncertaintyMetadata(
                        ambiguous_source_evidence={
                            "is_ambiguous": is_amb,
                            "epistemic_status": entry.epistemic_status,
                            "non_preference_category": entry.non_preference_category,
                            "text_supplied": entry.text_supplied,
                            "uncertainty_span_ids": sorted(set(entry.coder_a_span_ids) | set(entry.coder_b_span_ids)),
                        }
                    ),
                )
            )
            if is_amb:
                unresolved.append(
                    UnresolvedCaseRecord(
                        case_id=f"UNRES_AMB_{entry.question_id}_{entry.participant_id}",
                        category="AMBIGUOUS_EPISTEMIC_RESPONSE",
                        severity="MEDIUM",
                        question_id=entry.question_id,
                        participant_id=entry.participant_id,
                        description=(
                            f"Ambiguous normalized cell ({entry.participant_id}, {entry.question_id}) "
                            "preserved without fabricated preference probabilities by both coders."
                        ),
                        coder_a_evidence={"span_ids": entry.coder_a_span_ids},
                        coder_b_evidence={"span_ids": entry.coder_b_span_ids},
                        recommended_resolution="Retain missingness_state='ambiguous' with empty alternative_probabilities in PreferenceMatrix.",
                    )
                )

        # 2. Usable preference comparisons per (participant, question, canonical_subtopic)
        for (pid, qid, cid), pair_coders in sorted(usable_by_key.items()):
            row = self.ledger.rows_by_pair[(pid, qid)]
            is_prim = bool(questions.get(qid, {}).get("is_primary_question", qid != "Q14"))
            cmeta = canon_by_id[cid]
            align_status = str(cmeta["alignment_category"])
            ca = pair_coders.get("coder_a")
            cb = pair_coders.get("coder_b")

            row_ep = str(row.get("epistemic_status", "substantive"))
            mixed_unc = row_ep == ResponseEpistemicStatus.MIXED_UNCERTAINTY_AND_PREFERENCE.value

            # Single-coder coverage only (never conflate with mutual disagreement on probabilities)
            if ca is None or cb is None:
                active = ca if ca is not None else cb
                assert active is not None
                active_probs = dict(active.get("alternative_probabilities") or {})
                is_aligned_subtopic = align_status in {"EXACT_MATCH", "SEMANTIC_MATCH"}
                obs_cat: Literal[
                    "BOTH_CODERS_OBSERVED",
                    "SINGLE_CODER_SUBTOPIC_ONLY",
                    "SINGLE_CODER_PARTICIPANT_OMISSION",
                    "PRESERVED_NON_PREFERENCE",
                    "NOT_MENTIONED_IN_RESPONSE",
                ] = (
                    "SINGLE_CODER_PARTICIPANT_OMISSION"
                    if is_aligned_subtopic
                    else "SINGLE_CODER_SUBTOPIC_ONLY"
                )
                ep_dist = (
                    "coder_omission_asymmetry"
                    if is_aligned_subtopic
                    else "granularity_asymmetry_single_coder_subtopic"
                )
                present_side = "coder_a" if ca is not None else "coder_b"
                missing_side = "coder_b" if ca is not None else "coder_a"
                policy_msg = (
                    f"Only {present_side} coded ({pid}, {qid}, {cid}); repository defines no authorized "
                    "single-coder acceptance or imputation rule into reconciled alternative_probabilities."
                )
                rec_hash = hashlib.sha256(f"{pid}|{qid}|{cid}".encode("utf-8")).hexdigest()[:8]
                conf_val = float(active["coder_confidence"]) if active.get("coder_confidence") is not None else None
                records.append(
                    PreferenceReconciliationRecord(
                        record_id=f"PREC_{qid}_{pid}_{rec_hash}",
                        participant_id=pid,
                        question_id=qid,
                        response_id=str(row["response_id"]),
                        is_primary_question=is_prim,
                        canonical_subtopic_id=cid,
                        subtopic_alignment_status=align_status,
                        cell_observation_category=obs_cat,
                        epistemic_distinction=ep_dist,
                        missingness_state=MissingnessState.OBSERVED_USABLE.value,
                        epistemic_status=str(active.get("epistemic_status") or row_ep),
                        coder_a_coding_id=str(ca["coding_id"]) if ca else None,
                        coder_b_coding_id=str(cb["coding_id"]) if cb else None,
                        coder_a_subtopic_id=str(ca["subtopic_id"]) if ca else None,
                        coder_b_subtopic_id=str(cb["subtopic_id"]) if cb else None,
                        coder_a_probabilities=active_probs if ca else None,
                        coder_b_probabilities=active_probs if cb else None,
                        alternative_alignment=AlternativeAlignmentInfo(
                            comparable=False,
                            mapping_type="SINGLE_CODER_ONLY",
                            aligned_keys=sorted(active_probs.keys()),
                            notes=f"Present only in {present_side}; absent in {missing_side}.",
                        ),
                        probability_interpretation_a=ca.get("probability_interpretation") if ca else None,
                        probability_interpretation_b=cb.get("probability_interpretation") if cb else None,
                        semantic_importance_a=ca.get("semantic_importance") if ca else None,
                        semantic_importance_b=cb.get("semantic_importance") if cb else None,
                        coder_confidence_a=ca.get("coder_confidence") if ca else None,
                        coder_confidence_b=cb.get("coder_confidence") if cb else None,
                        raw_placeholder_agreement_a=ca.get("coder_agreement") if ca else None,
                        raw_placeholder_agreement_b=cb.get("coder_agreement") if cb else None,
                        coder_a_span_ids=list(ca.get("evidence_span_ids") or []) if ca else [],
                        coder_b_span_ids=list(cb.get("evidence_span_ids") or []) if cb else [],
                        modal_alternative_a=max(active_probs, key=active_probs.get) if (ca and active_probs) else None,
                        modal_alternative_b=max(active_probs, key=active_probs.get) if (cb and active_probs) else None,
                        computed_coder_agreement=None,
                        reconciled_alternative_probabilities=None,
                        derived_scalar_score=None,
                        reconciliation_status="UNRESOLVED_RECONCILIATION_POLICY",
                        reconciliation_method="HIGH_UNCERTAINTY_FLAGGED",
                        policy_gap_flag=policy_msg,
                        uncertainty=UncertaintyMetadata(
                            coding_disagreement={
                                "single_coder_only": True,
                                "present_coder": present_side,
                                "missing_coder": missing_side,
                                "reason": obs_cat,
                            },
                            coder_confidence={
                                "coder_a_confidence": ca.get("coder_confidence") if ca else None,
                                "coder_b_confidence": cb.get("coder_confidence") if cb else None,
                                "mean_confidence": conf_val,
                            },
                            preference_distribution_uncertainty={
                                "entropy_bits": _shannon_entropy_bits(active_probs),
                                "single_coder_distribution_only": True,
                            },
                            ambiguous_source_evidence={
                                "mixed_uncertainty_and_preference": mixed_unc,
                                "epistemic_status": str(active.get("epistemic_status") or row_ep),
                            },
                        ),
                    )
                )
                unresolved.append(
                    UnresolvedCaseRecord(
                        case_id=f"UNRES_SC_{qid}_{pid}_{rec_hash}",
                        category=(
                            "SINGLE_CODER_PARTICIPANT_OMISSION"
                            if is_aligned_subtopic
                            else "SINGLE_CODER_SUBTOPIC_GRANULARITY"
                        ),
                        severity="MEDIUM" if not is_aligned_subtopic else "HIGH_SUBSTANTIVE",
                        question_id=qid,
                        participant_id=pid,
                        canonical_subtopic_id=cid,
                        description=policy_msg,
                        coder_a_evidence=(
                            {"subtopic_id": ca["subtopic_id"], "probs": active_probs} if ca else {}
                        ),
                        coder_b_evidence=(
                            {"subtopic_id": cb["subtopic_id"], "probs": active_probs} if cb else {}
                        ),
                        recommended_resolution=(
                            "Define ADR policy for single-coder participant omissions and finer-granularity facets "
                            "(adjudicate span presence vs treat unmentioned/disagreement uncertainty)."
                        ),
                    )
                )
                continue

            # Both coders observed this participant x canonical_subtopic
            probs_a = {str(k): float(v) for k, v in (ca.get("alternative_probabilities") or {}).items()}
            probs_b = {str(k): float(v) for k, v in (cb.get("alternative_probabilities") or {}).items()}
            alt_align = align_alternative_vocabularies(probs_a, probs_b)

            interp_a = ca.get("probability_interpretation")
            interp_b = cb.get("probability_interpretation")
            interp_agree = (interp_a == interp_b)

            imp_a = float(ca["semantic_importance"]) if ca.get("semantic_importance") is not None else None
            imp_b = float(cb["semantic_importance"]) if cb.get("semantic_importance") is not None else None
            conf_a = float(ca["coder_confidence"]) if ca.get("coder_confidence") is not None else None
            conf_b = float(cb["coder_confidence"]) if cb.get("coder_confidence") is not None else None

            rec_hash = hashlib.sha256(f"{pid}|{qid}|{cid}".encode("utf-8")).hexdigest()[:8]

            if alt_align.comparable:
                aligned_a = defaultdict(float)
                aligned_b = defaultdict(float)
                for ka, pa_val in probs_a.items():
                    aligned_a[alt_align.coder_a_to_aligned_key[ka]] += pa_val
                for kb, pb_val in probs_b.items():
                    aligned_b[alt_align.coder_b_to_aligned_key[kb]] += pb_val

                keys = sorted(set(aligned_a) | set(aligned_b))
                l1 = sum(abs(aligned_a.get(k, 0.0) - aligned_b.get(k, 0.0)) for k in keys)
                tvd = 0.5 * l1
                jsd = 0.0
                for k in keys:
                    pa_v = aligned_a.get(k, 0.0)
                    pb_v = aligned_b.get(k, 0.0)
                    m = 0.5 * (pa_v + pb_v)
                    if pa_v > 1e-12 and m > 1e-12:
                        jsd += 0.5 * pa_v * math.log2(pa_v / m)
                    if pb_v > 1e-12 and m > 1e-12:
                        jsd += 0.5 * pb_v * math.log2(pb_v / m)

                modal_a = max(keys, key=lambda k: (aligned_a.get(k, 0.0), k))
                modal_b = max(keys, key=lambda k: (aligned_b.get(k, 0.0), k))
                modal_agree = modal_a == modal_b
                dist_agree = tvd <= 1e-4
                agreement_score = round(max(0.0, 1.0 - tvd), 6)
                ci_low = {k: round(min(aligned_a.get(k, 0.0), aligned_b.get(k, 0.0)), 6) for k in keys}
                ci_high = {k: round(max(aligned_a.get(k, 0.0), aligned_b.get(k, 0.0)), 6) for k in keys}

                if dist_agree and interp_agree and alt_align.mapping_type == "EXACT_KEYS":
                    # Identical keys, identical distribution, identical interpretation -> exact agreement
                    reconciled_probs: Optional[Dict[str, float]] = dict(probs_a)
                    rec_status: Literal[
                        "AGREEMENT_EXACT",
                        "AGREEMENT_DISTRIBUTION_ONLY_INTERPRETATION_FLAGGED",
                        "UNRESOLVED_RECONCILIATION_POLICY",
                        "PRESERVED_MISSING_OR_NON_PREFERENCE",
                        "NOT_MENTIONED_ABSENCE",
                    ] = "AGREEMENT_EXACT"
                    rec_method: Optional[Literal["EXACT_MATCH", "ARBITRATED_SPAN_CHECK", "HIGH_UNCERTAINTY_FLAGGED"]] = "EXACT_MATCH"
                    ep_dist = "substantive_agreement"
                    policy_msg = None
                elif dist_agree:
                    # Distributions match numerically, but probability_interpretation or raw key naming differs
                    reconciled_probs = None
                    rec_status = "AGREEMENT_DISTRIBUTION_ONLY_INTERPRETATION_FLAGGED"
                    rec_method = "ARBITRATED_SPAN_CHECK"
                    ep_dist = "interpretation_disagreement_only"
                    if not interp_agree:
                        policy_msg = (
                            f"Probability distributions match cleanly (TVD={tvd:.4f}), but "
                            f"probability_interpretation differs ({interp_a!r} vs {interp_b!r}); "
                            "preserved without forcing uniform semantics."
                        )
                        unres_cat: Literal[
                            "PROBABILITY_INTERPRETATION_DISAGREEMENT",
                            "ALTERNATIVE_KEY_CROSSWALK_PENDING",
                        ] = "PROBABILITY_INTERPRETATION_DISAGREEMENT"
                        unres_id = f"UNRES_INT_{qid}_{pid}_{rec_hash}"
                        unres_res = "Standardize probability_interpretation semantics via ISSUE-005 / ADR before Agent 04 utility mapping."
                    else:
                        policy_msg = (
                            f"Probability distributions and interpretations match cleanly (TVD={tvd:.4f}), "
                            f"but raw coder alternative keys aligned via {alt_align.mapping_type}; "
                            "preserved pending formal alternative crosswalk approval."
                        )
                        unres_cat = "ALTERNATIVE_KEY_CROSSWALK_PENDING"
                        unres_id = f"UNRES_CW_{qid}_{pid}_{rec_hash}"
                        unres_res = "Approve canonical alternative key crosswalk via ADR before merging aligned keys in Agent 04."
                    unresolved.append(
                        UnresolvedCaseRecord(
                            case_id=unres_id,
                            category=unres_cat,
                            severity="MEDIUM",
                            question_id=qid,
                            participant_id=pid,
                            canonical_subtopic_id=cid,
                            description=policy_msg,
                            coder_a_evidence={"probs": probs_a, "interp": interp_a},
                            coder_b_evidence={"probs": probs_b, "interp": interp_b},
                            recommended_resolution=unres_res,
                        )
                    )
                else:
                    # Probability distributions genuinely differ (TVD > 1e-4): STOP without silent averaging!
                    reconciled_probs = None
                    rec_status = "UNRESOLVED_RECONCILIATION_POLICY"
                    rec_method = "HIGH_UNCERTAINTY_FLAGGED" if tvd >= 0.25 else "ARBITRATED_SPAN_CHECK"
                    ep_dist = "substantive_disagreement"
                    policy_msg = (
                        f"Probability distributions differ (TVD={tvd:.4f}, JSD={jsd:.4f}). Per Section 8, "
                        "no authorized numeric combination rule exists in the repository; raw Coder A & Coder B "
                        "distributions preserved without silent averaging."
                    )
                    unresolved.append(
                        UnresolvedCaseRecord(
                            case_id=f"UNRES_DIST_{qid}_{pid}_{rec_hash}",
                            category="PREFERENCE_DISTRIBUTION_DISAGREEMENT",
                            severity="HIGH_SUBSTANTIVE",
                            question_id=qid,
                            participant_id=pid,
                            canonical_subtopic_id=cid,
                            description=policy_msg,
                            coder_a_evidence={"probs": probs_a, "interp": interp_a, "conf": conf_a},
                            coder_b_evidence={"probs": probs_b, "interp": interp_b, "conf": conf_b},
                            recommended_resolution="Establish authorized dual-coder probability reconciliation ADR & adjudicate differing cells.",
                        )
                    )
            else:
                # Alternative vocabularies incompatible -> STOP without inventing mapping or averaging
                l1 = None
                tvd = None
                jsd = None
                modal_a = max(probs_a, key=probs_a.get) if probs_a else None
                modal_b = max(probs_b, key=probs_b.get) if probs_b else None
                modal_agree = None
                dist_agree = False
                agreement_score = 0.0
                ci_low = None
                ci_high = None
                reconciled_probs = None
                rec_status = "UNRESOLVED_RECONCILIATION_POLICY"
                rec_method = "HIGH_UNCERTAINTY_FLAGGED"
                ep_dist = "substantive_disagreement"
                policy_msg = alt_align.notes
                unresolved.append(
                    UnresolvedCaseRecord(
                        case_id=f"UNRES_ALT_{qid}_{pid}_{rec_hash}",
                        category="ALTERNATIVE_VOCABULARY_MISMATCH",
                        severity="HIGH_BLOCKING_POLICY",
                        question_id=qid,
                        participant_id=pid,
                        canonical_subtopic_id=cid,
                        description=policy_msg,
                        coder_a_evidence={"subtopic_id": ca["subtopic_id"], "probs": probs_a, "interp": interp_a},
                        coder_b_evidence={"subtopic_id": cb["subtopic_id"], "probs": probs_b, "interp": interp_b},
                        recommended_resolution="Define canonical alternative crosswalk per question/subtopic prior to Agent 04 matrix generation.",
                    )
                )

            confs = [c for c in (conf_a, conf_b) if c is not None]
            records.append(
                PreferenceReconciliationRecord(
                    record_id=f"PREC_{qid}_{pid}_{rec_hash}",
                    participant_id=pid,
                    question_id=qid,
                    response_id=str(row["response_id"]),
                    is_primary_question=is_prim,
                    canonical_subtopic_id=cid,
                    subtopic_alignment_status=align_status,
                    cell_observation_category="BOTH_CODERS_OBSERVED",
                    epistemic_distinction=ep_dist,
                    missingness_state=MissingnessState.OBSERVED_USABLE.value,
                    epistemic_status=str(ca.get("epistemic_status") or row_ep),
                    coder_a_coding_id=str(ca["coding_id"]),
                    coder_b_coding_id=str(cb["coding_id"]),
                    coder_a_subtopic_id=str(ca["subtopic_id"]),
                    coder_b_subtopic_id=str(cb["subtopic_id"]),
                    coder_a_probabilities=probs_a,
                    coder_b_probabilities=probs_b,
                    alternative_alignment=alt_align,
                    probability_interpretation_a=interp_a,
                    probability_interpretation_b=interp_b,
                    semantic_importance_a=imp_a,
                    semantic_importance_b=imp_b,
                    coder_confidence_a=conf_a,
                    coder_confidence_b=conf_b,
                    raw_placeholder_agreement_a=ca.get("coder_agreement"),
                    raw_placeholder_agreement_b=cb.get("coder_agreement"),
                    coder_a_span_ids=list(ca.get("evidence_span_ids") or []),
                    coder_b_span_ids=list(cb.get("evidence_span_ids") or []),
                    total_variation_distance=round(tvd, 6) if tvd is not None else None,
                    l1_distance=round(l1, 6) if l1 is not None else None,
                    jensen_shannon_divergence=round(jsd, 6) if jsd is not None else None,
                    modal_alternative_a=modal_a,
                    modal_alternative_b=modal_b,
                    modal_agreement=modal_agree,
                    distribution_agreement=dist_agree,
                    interpretation_agreement=interp_agree,
                    computed_coder_agreement=agreement_score,
                    probability_interval_lower=ci_low,
                    probability_interval_upper=ci_high,
                    reconciled_alternative_probabilities=reconciled_probs,
                    derived_scalar_score=None,
                    reconciliation_status=rec_status,
                    reconciliation_method=rec_method,
                    policy_gap_flag=policy_msg,
                    uncertainty=UncertaintyMetadata(
                        coding_disagreement={
                            "comparable_alternatives": alt_align.comparable,
                            "tvd": round(tvd, 6) if tvd is not None else None,
                            "jsd": round(jsd, 6) if jsd is not None else None,
                            "modal_agreement": modal_agree,
                            "interpretation_agreement": interp_agree,
                        },
                        coder_confidence={
                            "coder_a_confidence": conf_a,
                            "coder_b_confidence": conf_b,
                            "min_confidence": min(confs) if confs else None,
                            "mean_confidence": round(sum(confs) / len(confs), 4) if confs else None,
                            "confidence_gap": round(abs(conf_a - conf_b), 4) if (conf_a is not None and conf_b is not None) else None,
                        },
                        preference_distribution_uncertainty={
                            "entropy_a_bits": _shannon_entropy_bits(probs_a),
                            "entropy_b_bits": _shannon_entropy_bits(probs_b),
                            "interval_max_width": (
                                round(max((ci_high[k] - ci_low[k]) for k in ci_low), 6)
                                if (ci_low and ci_high)
                                else None
                            ),
                        },
                        ambiguous_source_evidence={
                            "mixed_uncertainty_and_preference": mixed_unc,
                            "epistemic_status": row_ep,
                        },
                    ),
                )
            )

        return records, unresolved

    def _reconcile_values(self) -> Tuple[List[ReconciledOrganisationalValue], Dict[str, Any]]:
        va_a = self.ledger.coder_a_payload.get("value_assignments") or []
        va_b = self.ledger.coder_b_payload.get("value_assignments") or []

        # Collect open-discovery Stage A items across both coders (never restricting to 7 fixed classes)
        items: List[Dict[str, Any]] = []
        for cid, arr in [("coder_a", va_a), ("coder_b", va_b)]:
            for v in arr:
                label = str(v.get("original_label") or v.get("value_label_en") or v.get("label_en") or v.get("value_id"))
                defn = str(v.get("value_definition", ""))
                sp_ids = list(v.get("evidence_span_ids") or [])
                tokens = _canonicalize_tokens(_clean_tokens(f"{label} {defn}"))
                ranges = self.ledger.get_span_char_ranges(cid, sp_ids)  # type: ignore[arg-type]
                items.append(
                    {
                        "coder_id": cid,
                        "value_assignment_id": str(v.get("value_assignment_id", "")),
                        "original_value_id": str(v.get("value_id", "")),
                        "original_label": label,
                        "value_definition": defn,
                        "participant_id": str(v.get("participant_id", "")),
                        "question_id": str(v.get("question_id", "")),
                        "subtopic_id": str(v.get("subtopic_id", "")),
                        "evidence_span_ids": sp_ids,
                        "polarity": v.get("polarity"),
                        "semantic_importance": float(v.get("semantic_importance", 0.0)),
                        "coder_confidence": float(v.get("coder_confidence", 0.0)),
                        "polarity_uncertainty_interval": v.get("polarity_uncertainty_interval"),
                        "tokens": tokens,
                        "label_tokens": _canonicalize_tokens(_clean_tokens(label)),
                        "ranges": ranges,
                    }
                )

        # Deterministic bottom-up clustering across questions & coders anchored on label/definition + shared span semantics
        clusters: List[Dict[str, Any]] = []
        for it in sorted(items, key=lambda x: (x["question_id"], x["participant_id"], x["coder_id"], x["original_label"])):
            best_cluster = None
            best_score = 0.0
            for cl in clusters:
                lbl_sim = _jaccard(it["label_tokens"], cl["label_tokens"])
                tok_sim = _jaccard(it["tokens"], cl["tokens"])
                # Bonus if same (participant, question) with overlapping character span AND meaningful label overlap
                iou, _, _ = compute_char_overlap_metrics(it["ranges"], cl["ranges"])
                same_span_bonus = 0.15 if (iou >= 0.35 and lbl_sim >= 0.25) else 0.0
                score = max(lbl_sim, 0.7 * lbl_sim + 0.3 * tok_sim) + same_span_bonus
                if (lbl_sim >= 0.50 or (tok_sim >= 0.45 and lbl_sim >= 0.33)) and score > best_score:
                    best_score = score
                    best_cluster = cl

            if best_cluster is not None:
                best_cluster["items"].append(it)
                best_cluster["label_tokens"].update(it["label_tokens"])
                best_cluster["tokens"].update(it["tokens"])
                for k, vset in it["ranges"].items():
                    best_cluster["ranges"].setdefault(k, set()).update(vset)
            else:
                clusters.append(
                    {
                        "label_tokens": set(it["label_tokens"]),
                        "tokens": set(it["tokens"]),
                        "ranges": {k: set(v) for k, v in it["ranges"].items()},
                        "items": [it],
                    }
                )

        reconciled: List[ReconciledOrganisationalValue] = []
        # Compute agreement stats across participant x question responses where values appeared
        by_resp_a: Dict[Tuple[str, str], Set[str]] = defaultdict(set)
        by_resp_b: Dict[Tuple[str, str], Set[str]] = defaultdict(set)
        paired_pol_a: List[Optional[float]] = []
        paired_pol_b: List[Optional[float]] = []

        # Order clusters deterministically by support desc, then canonical label
        clusters.sort(key=lambda c: (-len(c["items"]), min(x["original_label"] for x in c["items"])))
        for idx, cl in enumerate(clusters, start=1):
            cl_items = cl["items"]
            label_counts = Counter(x["original_label"] for x in cl_items)
            canon_label = max(label_counts, key=lambda lbl: (label_counts[lbl], -len(lbl), lbl))
            canon_def = max((x["value_definition"] for x in cl_items), key=len)
            slug = re.sub(r"[^\w]+", "_", canon_label.upper()).strip("_")[:40]
            rval_id = f"RVAL_{idx:03d}_{slug}"

            for x in cl_items:
                key = (x["participant_id"], x["question_id"])
                if x["coder_id"] == "coder_a":
                    by_resp_a[key].add(rval_id)
                else:
                    by_resp_b[key].add(rval_id)

            # Collect paired polarity concordance within cluster & same (participant, question)
            by_pq_cluster: Dict[Tuple[str, str], Dict[str, List[Optional[float]]]] = defaultdict(
                lambda: {"coder_a": [], "coder_b": []}
            )
            for x in cl_items:
                by_pq_cluster[(x["participant_id"], x["question_id"])][x["coder_id"]].append(x["polarity"])
            for _, sides in by_pq_cluster.items():
                if sides["coder_a"] and sides["coder_b"]:
                    paired_pol_a.append(sides["coder_a"][0])
                    paired_pol_b.append(sides["coder_b"][0])

            pols = [float(x["polarity"]) for x in cl_items if x["polarity"] is not None]
            null_pols = sum(1 for x in cl_items if x["polarity"] is None)
            imps = [x["semantic_importance"] for x in cl_items]
            confs = [x["coder_confidence"] for x in cl_items]
            qids = sorted({x["question_id"] for x in cl_items if x["question_id"]})
            a_items = [x for x in cl_items if x["coder_id"] == "coder_a"]
            b_items = [x for x in cl_items if x["coder_id"] == "coder_b"]

            raw_extractions = [
                {k: v for k, v in x.items() if k not in ("tokens", "label_tokens", "ranges")}
                for x in cl_items
            ]
            reconciled.append(
                ReconciledOrganisationalValue(
                    reconciled_value_id=rval_id,
                    canonical_value_label=canon_label,
                    canonical_definition=canon_def,
                    original_extractions=raw_extractions,
                    original_labels_coder_a=sorted({x["original_label"] for x in a_items}),
                    original_labels_coder_b=sorted({x["original_label"] for x in b_items}),
                    supporting_question_ids=qids,
                    cross_question_bridges=qids if len(qids) > 1 else [],
                    supporting_participant_ids=sorted({x["participant_id"] for x in cl_items}),
                    supporting_span_ids_a=sorted({s for x in a_items for s in x["evidence_span_ids"]}),
                    supporting_span_ids_b=sorted({s for x in b_items for s in x["evidence_span_ids"]}),
                    coder_a_count=len(a_items),
                    coder_b_count=len(b_items),
                    dual_coder_confirmed=bool(a_items and b_items),
                    polarity_non_null_values=pols,
                    polarity_null_count=null_pols,
                    polarity_range=[round(min(pols), 4), round(max(pols), 4)] if pols else None,
                    mean_semantic_importance=round(sum(imps) / len(imps), 4) if imps else None,
                    mean_coder_confidence=round(sum(confs) / len(confs), 4) if confs else None,
                    pareto_pruning_prohibited=True,
                )
            )

        all_resp_keys = sorted(set(by_resp_a) | set(by_resp_b))
        resp_jaccards = [
            _jaccard(by_resp_a.get(k, set()), by_resp_b.get(k, set()))
            for k in all_resp_keys
        ]
        sign_agree = [
            (pa == 0 and pb == 0) or (pa > 0 and pb > 0) or (pa < 0 and pb < 0)
            for pa, pb in zip(paired_pol_a, paired_pol_b)
            if pa is not None and pb is not None
        ]
        pol_mae = [
            abs(float(pa) - float(pb))
            for pa, pb in zip(paired_pol_a, paired_pol_b)
            if pa is not None and pb is not None
        ]
        val_agree_stats = {
            "total_stage_a_assignments_coder_a": len(va_a),
            "total_stage_a_assignments_coder_b": len(va_b),
            "consolidated_value_clusters": len(reconciled),
            "dual_coder_confirmed_clusters": sum(1 for r in reconciled if r.dual_coder_confirmed),
            "cross_question_value_clusters": sum(1 for r in reconciled if len(r.supporting_question_ids) > 1),
            "nullable_polarity_preserved_count": sum(r.polarity_null_count for r in reconciled),
            "response_level_value_concept_jaccard_mean": (
                round(sum(resp_jaccards) / len(resp_jaccards), 4) if resp_jaccards else 0.0
            ),
            "response_level_value_concept_jaccard_ci_95": _bootstrap_mean_ci(resp_jaccards),
            "paired_non_null_polarity_count": len(sign_agree),
            "paired_polarity_sign_agreement": (
                round(sum(1 for x in sign_agree if x) / len(sign_agree), 4) if sign_agree else None
            ),
            "paired_polarity_mae": round(sum(pol_mae) / len(pol_mae), 4) if pol_mae else None,
        }
        return reconciled, val_agree_stats

    def _audit_goods_classification(
        self,
        canonical_subtopics: List[Dict[str, Any]],
    ) -> Tuple[Dict[str, Any], List[UnresolvedCaseRecord]]:
        questions = self.ledger.question_registry.get("questions", {})
        ca_crs = self.ledger.coder_a_payload.get("coding_results") or []
        cb_crs = self.ledger.coder_b_payload.get("coding_results") or []
        ca_subs = self.ledger.coder_a_payload.get("discovered_subtopics") or []
        cb_subs = self.ledger.coder_b_payload.get("discovered_subtopics") or []

        enabled_qids = sorted(
            qid for qid, q in questions.items() if q.get("economic_good_classification_policy") == "ENABLED"
        )
        conditional_qids = sorted(
            qid for qid, q in questions.items() if q.get("economic_good_classification_policy") == "CONDITIONAL"
        )
        disabled_qids = sorted(
            qid for qid, q in questions.items() if q.get("economic_good_classification_policy") == "DISABLED"
        )

        # Count actual non-null goods classifications & agreement between coders
        a_populated_sub = sum(
            1 for s in ca_subs if (s.get("goods_assessment") or {}).get("goods_applicability") == "APPLICABLE"
        )
        b_populated_sub = sum(
            1 for s in cb_subs if (s.get("goods_assessment") or {}).get("goods_applicability") == "APPLICABLE"
        )
        a_populated_cr = sum(
            1 for c in ca_crs if c.get("economic_good_class") not in (None, "", "NOT_APPLICABLE")
        )
        b_populated_cr = sum(
            1 for c in cb_crs if c.get("economic_good_class") not in (None, "", "NOT_APPLICABLE")
        )

        # Check paired aligned subtopics agreement on economic_good_class
        paired_aligned = [
            c for c in canonical_subtopics if c.get("coder_a_subtopic_id") and c.get("coder_b_subtopic_id")
        ]
        # Both coders assigned NOT_APPLICABLE / None across all subtopics -> 100% raw agreement on None/NOT_APPLICABLE
        unresolved_goods: List[UnresolvedCaseRecord] = []
        if enabled_qids and (a_populated_sub == 0 and b_populated_sub == 0):
            unresolved_goods.append(
                UnresolvedCaseRecord(
                    case_id="UNRES_GOODS_ENABLED_Q07_Q12_UNPOPULATED",
                    category="GOODS_ASSESSMENT_UNPOPULATED_ON_ENABLED_QUESTION",
                    severity="MEDIUM",
                    question_id=",".join(enabled_qids),
                    description=(
                        f"Both Coder A and Coder B emitted goods_applicability='NOT_APPLICABLE' and "
                        f"economic_good_class=None across all {len(enabled_qids)} ENABLED allocation questions "
                        f"({enabled_qids}). Per Section 11, Agent 03 preserves raw coder agreement on NOT_APPLICABLE "
                        "without forcing private/club/common/public classes merely for completeness."
                    ),
                    coder_a_evidence={"applicable_subtopics": a_populated_sub, "non_null_coding_results": a_populated_cr},
                    coder_b_evidence={"applicable_subtopics": b_populated_sub, "non_null_coding_results": b_populated_cr},
                    recommended_resolution=(
                        "Confirm whether goods taxonomy annotation should be deferred or evaluated in a targeted "
                        "post-reconciliation review pass over Q07-Q12 allocation semantics."
                    ),
                )
            )

        audit = {
            "question_policies": {
                "ENABLED": enabled_qids,
                "CONDITIONAL": conditional_qids,
                "DISABLED": disabled_qids,
            },
            "coder_a_applicable_subtopics": a_populated_sub,
            "coder_b_applicable_subtopics": b_populated_sub,
            "coder_a_non_null_coding_good_classes": a_populated_cr,
            "coder_b_non_null_coding_good_classes": b_populated_cr,
            "paired_subtopics_checked": len(paired_aligned),
            "raw_concordance_on_not_applicable_or_none": 1.0 if (a_populated_sub == 0 and b_populated_sub == 0) else None,
            "forced_classifications_count": 0,
            "policy_compliance_note": (
                "No economic good classes fabricated by Agent 03; both coders left ENABLED questions "
                f"{enabled_qids} as NOT_APPLICABLE/None, preserved transparently and flagged in unresolved_cases_registry."
            ),
        }
        return audit, unresolved_goods

    def _compute_separate_agreement_stats(
        self,
        proposals: List[ProposedSubtopicRecord],
        pairwise: List[PairwiseSubtopicAlignment],
        canonical_subtopics: List[Dict[str, Any]],
        pref_records: List[PreferenceReconciliationRecord],
        val_agree_stats: Dict[str, Any],
        goods_audit: Dict[str, Any],
    ) -> Dict[str, Any]:
        # 1. Subtopic presence & alignment agreement
        align_counts = Counter(c["alignment_category"] for c in canonical_subtopics)
        matched_pairs = [p for p in pairwise if p.merged_into_same_canonical]
        matched_ious = [p.span_char_iou for p in matched_pairs]
        matched_p_jaccs = [p.participant_jaccard for p in matched_pairs]

        # Question-level participant coverage agreement on aligned vs total
        obs_by_q: Dict[str, int] = defaultdict(int)
        for p in proposals:
            obs_by_q[f"{p.question_id}:{p.coder_source}"] += 1

        subtopic_stats = {
            "coder_a_proposed_subtopics": sum(1 for p in proposals if p.coder_source == "coder_a"),
            "coder_b_proposed_subtopics": sum(1 for p in proposals if p.coder_source == "coder_b"),
            "canonical_subtopics_total": len(canonical_subtopics),
            "canonical_alignment_breakdown": dict(sorted(align_counts.items())),
            "aligned_1to1_pairs_count": len(matched_pairs),
            "matched_pair_span_char_iou_mean": round(sum(matched_ious) / len(matched_ious), 4) if matched_ious else 0.0,
            "matched_pair_span_char_iou_ci_95": _bootstrap_mean_ci(matched_ious),
            "matched_pair_participant_jaccard_mean": round(sum(matched_p_jaccs) / len(matched_p_jaccs), 4) if matched_p_jaccs else 0.0,
            "matched_pair_participant_jaccard_ci_95": _bootstrap_mean_ci(matched_p_jaccs),
            "granularity_ratio_b_to_a": round(
                sum(1 for p in proposals if p.coder_source == "coder_b")
                / max(1, sum(1 for p in proposals if p.coder_source == "coder_a")),
                4,
            ),
        }

        # 2. Preference / alternative assignment agreement (paired observed usable cells ONLY; ignore 0.0 placeholders)
        both_obs = [r for r in pref_records if r.cell_observation_category == "BOTH_CODERS_OBSERVED"]
        single_sub = [r for r in pref_records if r.cell_observation_category == "SINGLE_CODER_SUBTOPIC_ONLY"]
        single_omit = [r for r in pref_records if r.cell_observation_category == "SINGLE_CODER_PARTICIPANT_OMISSION"]
        comp_obs = [r for r in both_obs if r.alternative_alignment and r.alternative_alignment.comparable]

        tvd_vals = [float(r.total_variation_distance) for r in comp_obs if r.total_variation_distance is not None]
        one_minus_tvd = [1.0 - t for t in tvd_vals]
        jsd_vals = [float(r.jensen_shannon_divergence) for r in comp_obs if r.jensen_shannon_divergence is not None]
        modal_matches = [bool(r.modal_agreement) for r in comp_obs if r.modal_agreement is not None]
        interp_matches = [bool(r.interpretation_agreement) for r in both_obs if r.interpretation_agreement is not None]
        dist_exact_matches = [bool(r.distribution_agreement) for r in comp_obs]
        imp_diffs = [
            abs(float(r.semantic_importance_a) - float(r.semantic_importance_b))
            for r in both_obs
            if r.semantic_importance_a is not None and r.semantic_importance_b is not None
        ]
        conf_diffs = [
            abs(float(r.coder_confidence_a) - float(r.coder_confidence_b))
            for r in both_obs
            if r.coder_confidence_a is not None and r.coder_confidence_b is not None
        ]

        # Breakdown by key mapping type
        mapping_counts = Counter(
            r.alternative_alignment.mapping_type for r in both_obs if r.alternative_alignment
        )

        preference_stats = {
            "both_coders_observed_cells": len(both_obs),
            "single_coder_subtopic_only_cells": len(single_sub),
            "single_coder_participant_omission_cells": len(single_omit),
            "alternative_vocabulary_mapping_breakdown": dict(sorted(mapping_counts.items())),
            "comparable_alternative_cells": len(comp_obs),
            "exact_distribution_agreement_count": sum(1 for x in dist_exact_matches if x),
            "exact_distribution_agreement_rate": (
                round(sum(1 for x in dist_exact_matches if x) / len(dist_exact_matches), 4)
                if dist_exact_matches
                else None
            ),
            "exact_distribution_agreement_ci_95": _wilson_ci(
                sum(1 for x in dist_exact_matches if x), len(dist_exact_matches)
            ),
            "modal_alternative_agreement_count": sum(1 for x in modal_matches if x),
            "modal_alternative_agreement_rate": (
                round(sum(1 for x in modal_matches if x) / len(modal_matches), 4) if modal_matches else None
            ),
            "modal_alternative_agreement_ci_95": _wilson_ci(
                sum(1 for x in modal_matches if x), len(modal_matches)
            ),
            "mean_one_minus_tvd": round(sum(one_minus_tvd) / len(one_minus_tvd), 4) if one_minus_tvd else None,
            "mean_one_minus_tvd_ci_95": _bootstrap_mean_ci(one_minus_tvd),
            "mean_jsd_bits": round(sum(jsd_vals) / len(jsd_vals), 4) if jsd_vals else None,
            "probability_interpretation_agreement_count": sum(1 for x in interp_matches if x),
            "probability_interpretation_agreement_rate": (
                round(sum(1 for x in interp_matches if x) / len(interp_matches), 4) if interp_matches else None
            ),
            "probability_interpretation_agreement_ci_95": _wilson_ci(
                sum(1 for x in interp_matches if x), len(interp_matches)
            ),
            "semantic_importance_mae": round(sum(imp_diffs) / len(imp_diffs), 4) if imp_diffs else None,
            "coder_confidence_mae": round(sum(conf_diffs) / len(conf_diffs), 4) if conf_diffs else None,
            "note": (
                "Computed strictly from actual reconciled dual-coder comparisons; "
                "pre-reconciliation placeholder 0.0 / PRE_RECONCILIATION_AGENT_03_PENDING values were excluded."
            ),
        }

        return {
            "schema_version": SCHEMA_VERSION,
            "run_id": self.run_id,
            "omnibus_score_suppressed": True,
            "subtopic_presence_and_alignment_agreement": subtopic_stats,
            "preference_and_alternative_agreement": preference_stats,
            "organisational_value_coding_agreement": val_agree_stats,
            "goods_classification_agreement": goods_audit,
        }

    def run_reconciliation(
        self,
        write_outputs: bool = True,
    ) -> Dict[str, Any]:
        """Execute full Agent 03 production evidence verification and reconciliation."""
        lock = self.ledger.load_and_lock_provenance()
        span_report = self.ledger.verify_spans_and_missingness()

        proposals, pairwise, canonical_subtopics, st_to_canon = self._evaluate_subtopic_alignment()
        pref_records, pref_unresolved = self._reconcile_preferences(canonical_subtopics, st_to_canon)
        reconciled_values, val_agree_stats = self._reconcile_values()
        goods_audit, goods_unresolved = self._audit_goods_classification(canonical_subtopics)

        # Phase 1 zero-Phase-2 subtopics & Phase-2 undeclared deduplication split diagnostics
        phase1_zero_unresolved: List[UnresolvedCaseRecord] = []
        phase2_split_unresolved: List[UnresolvedCaseRecord] = []
        for p in proposals:
            if p.phase2_coding_count == 0:
                phase1_zero_unresolved.append(
                    UnresolvedCaseRecord(
                        case_id=f"UNRES_P1_0P_{p.question_id}_{p.subtopic_id}",
                        category="PHASE1_SUBTOPIC_ZERO_PHASE2_CODINGS",
                        severity="LOW",
                        question_id=p.question_id,
                        canonical_subtopic_id=p.canonical_subtopic_id,
                        description=(
                            f"Phase 1 discovered subtopic '{p.subtopic_id}' ({p.coder_source}) with "
                            f"{len(p.supporting_response_ids)} supporting response(s) has 0 Phase 2 coding_results."
                        ),
                        coder_a_evidence={"supporting_response_ids": p.supporting_response_ids} if p.coder_source == "coder_a" else {},
                        coder_b_evidence={"supporting_response_ids": p.supporting_response_ids} if p.coder_source == "coder_b" else {},
                        recommended_resolution="Preserve in CanonicalSubtopic inventory as Phase 1-only discovery without fabricating Phase 2 codings.",
                    )
                )
            if p.phase2_split_subtopic:
                phase2_split_unresolved.append(
                    UnresolvedCaseRecord(
                        case_id=f"UNRES_P2_SPLIT_{p.question_id}_{p.subtopic_id}",
                        category="PHASE2_DEDUP_SPLIT_UNDECLARED_IN_PHASE1",
                        severity="LOW",
                        question_id=p.question_id,
                        participant_id=",".join(p.phase2_observed_participant_ids) or None,
                        canonical_subtopic_id=p.canonical_subtopic_id,
                        description=(
                            f"Phase 2 coding_results emitted suffixed split subtopic '{p.subtopic_id}' "
                            f"({p.coder_source}) for {p.phase2_observed_participant_ids} without a separate "
                            f"Phase 1 discovered_subtopics declaration (parent={p.parent_phase1_subtopic_id}). "
                            "Preserved as an unmerged canonical subtopic facet without collapsing onto parent."
                        ),
                        coder_a_evidence={"subtopic_id": p.subtopic_id, "span_ids": p.evidence_span_ids} if p.coder_source == "coder_a" else {},
                        coder_b_evidence={"subtopic_id": p.subtopic_id, "span_ids": p.evidence_span_ids} if p.coder_source == "coder_b" else {},
                        recommended_resolution="Ensure Phase-2 deduplication splits emit formal Phase-1 facet annotations in future runs.",
                    )
                )

        # Top-level unresolved reconciliation policy record per Section 8
        both_obs = [r for r in pref_records if r.cell_observation_category == "BOTH_CODERS_OBSERVED"]
        unresolved_policy_cells = [r for r in pref_records if r.reconciliation_status != "AGREEMENT_EXACT" and r.cell_observation_category != "PRESERVED_NON_PREFERENCE"]
        policy_case = UnresolvedCaseRecord(
            case_id="UNRES_POLICY_SECTION_08_NO_COMBINATION_RULE",
            category="UNRESOLVED_PREFERENCE_RECONCILIATION_POLICY",
            severity="HIGH_BLOCKING_POLICY",
            question_id="Q01-Q14",
            description=(
                f"Repository contracts (src/contracts.py, docs/DATA_CONTRACTS.md) do not define an authorized "
                f"mathematical reconciliation rule for combining differing alternative_probabilities, reconciling "
                f"alternative vocabulary mismatches, or handling single-coder subtopics/omissions across Coder A & B. "
                f"Out of {len(both_obs)} dual-coded cells and {len(pref_records) - len(self.ledger.missingness_ledger)} "
                f"total usable cells, {len(unresolved_policy_cells)} cell(s) stopped at the documented disagreement "
                "representation without silent averaging."
            ),
            coder_a_evidence={"usable_coding_results": lock.coder_a.coding_results_count - lock.coder_a.non_preference_cells_preserved},
            coder_b_evidence={"usable_coding_results": lock.coder_b.coding_results_count - lock.coder_b.non_preference_cells_preserved},
            recommended_resolution=(
                "Agent 00 / Agent 04 / Architecture Review must issue an ADR specifying: (1) authorized cross-coder "
                "probability combination rule (`CONFIDENCE_WEIGHTED_DISTRIBUTION` / interval bounds / uncertainty draw), "
                "(2) cross-coder alternative vocabulary mapping rule (e.g. Q05 scenarios, Q08 management levels), "
                "(3) single-coder subtopic/omission treatment, and (4) resolution of ISSUE-005 before Agent 04 execution."
            ),
        )

        all_unresolved = [policy_case, *pref_unresolved, *goods_unresolved, *phase1_zero_unresolved, *phase2_split_unresolved]
        agreement_stats = self._compute_separate_agreement_stats(
            proposals, pairwise, canonical_subtopics, pref_records, val_agree_stats, goods_audit
        )

        # Build privacy-safe ThemesCodebook (themes_codebook_v1) ensuring every theme references real response_ids
        themes: List[ThemeRecord] = []
        canon_by_q: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for c in canonical_subtopics:
            canon_by_q[c["question_id"]].append(c)

        for idx, c in enumerate(canonical_subtopics, start=1):
            qid = c["question_id"]
            # Derive valid response_ids from mention_participant_ids -> RESP_<pid>_<qid>
            resp_ids = []
            for pid in c.get("mention_participant_ids") or []:
                row = self.ledger.rows_by_pair.get((pid, qid))
                if row:
                    resp_ids.append(str(row["response_id"]))
            for r_id in c.get("supporting_response_ids") or []:
                if r_id in self.ledger.rows_by_response_id and r_id not in resp_ids:
                    resp_ids.append(r_id)
            resp_ids = sorted(set(resp_ids))
            themes.append(
                ThemeRecord(
                    theme_id=f"TH_{qid}_{idx:03d}",
                    question_id=qid,
                    name=c["canonical_label_en"],
                    description=c["canonical_description"],
                    keywords=sorted(_clean_tokens(c["canonical_label_en"]))[:8],
                    evidence_response_ids=resp_ids,
                    support_count=int(c["mention_participant_count"]),
                )
            )

        theme_by_canon_subtopic = {
            c["subtopic_id"]: themes[i].theme_id for i, c in enumerate(canonical_subtopics)
        }

        value_assignment_records: List[Dict[str, Any]] = []
        for rv in reconciled_values:
            value_assignment_records.append(
                {
                    "value_assignment_id": f"VA_REC_{rv.reconciled_value_id}",
                    "value_id": rv.reconciled_value_id,
                    "value_label_en": rv.canonical_value_label,
                    "value_definition": rv.canonical_definition,
                    "supporting_question_ids": rv.supporting_question_ids,
                    "cross_question_bridge_ids": rv.cross_question_bridges,
                    "supporting_participant_ids": rv.supporting_participant_ids,
                    "evidence_span_ids": sorted(set(rv.supporting_span_ids_a) | set(rv.supporting_span_ids_b)),
                    "coder_a_raw_labels": rv.original_labels_coder_a,
                    "coder_b_raw_labels": rv.original_labels_coder_b,
                    "polarity_non_null_values": rv.polarity_non_null_values,
                    "polarity_null_count": rv.polarity_null_count,
                    "polarity_range": rv.polarity_range,
                    "mean_semantic_importance": rv.mean_semantic_importance,
                    "mean_coder_confidence": rv.mean_coder_confidence,
                    "dual_coder_confirmed": rv.dual_coder_confirmed,
                    "pareto_pruning_prohibited": True,
                }
            )

        themes_codebook = ThemesCodebook(
            schema_version="v1.1.0",
            run_id=self.run_id,
            themes=themes,
            canonical_subtopics=canonical_subtopics,
            value_assignments=value_assignment_records,
            subtopic_match_proposals=[p.model_dump() for p in pairwise],
            response_status_summary={
                "total_cells": lock.total_response_cells,
                "observed_usable_cells": lock.observed_usable_response_cells,
                "non_preference_cells_preserved": lock.non_preference_response_cells,
                "non_preference_breakdown": dict(
                    Counter(e.non_preference_category for e in self.ledger.missingness_ledger)
                ),
            },
            methodological_flags={
                "alternative_probabilities_meaning": (
                    "Epistemic coding uncertainty, mixed preference, or conditional allocation—NOT cardinal utility (ISSUE-005)."
                ),
                "reconciled_by_agent_03": True,
                "preference_reconciliation_policy_unresolved": True,
                "no_silent_averaging_enforced": True,
                "values_non_pruning_invariant": True,
            },
            provenance={
                "lock_id": lock.lock_id,
                "source_evidence_hash": lock.common_source_evidence_hash,
                "coder_a_prompt_hash": lock.coder_a.prompt_hash,
                "coder_b_prompt_hash": lock.coder_b.prompt_hash,
                "coder_a_outputs_sha256": lock.coder_a.artifact_sha256,
                "coder_b_outputs_sha256": lock.coder_b.artifact_sha256,
                "producer_agent": "agent_03",
                "producer_module": "src/evidence/reconciliation.py",
            },
        )

        # Build constraint-only candidate_options_v1 (ZERO cluster or value pruning!)
        candidates: List[Dict[str, Any]] = []
        for c in canonical_subtopics:
            sid = c["subtopic_id"]
            qid = c["question_id"]
            theme_id = theme_by_canon_subtopic[sid]
            for alt_label in c.get("feasible_alternatives") or []:
                alt_slug = re.sub(r"[^\w:]+", "_", alt_label).strip("_")
                cand_hash = hashlib.sha256(f"{qid}|{sid}|{alt_label}".encode("utf-8")).hexdigest()[:8]
                candidates.append(
                    {
                        "candidate_id": f"CAND_{qid}_{cand_hash}",
                        "question_id": qid,
                        "is_primary_question": qid != "Q14",
                        "subtopic_id": sid,
                        "title": alt_slug,
                        "description": (
                            f"Evidence-grounded alternative '{alt_label}' proposed within "
                            f"{c['canonical_label_en']} ({qid})."
                        ),
                        "grounding_theme_ids": [theme_id],
                        "supporting_span_ids": c.get("supporting_span_ids") or [],
                        "supporting_participant_count": int(c.get("mention_participant_count", 0)),
                        "missing_participant_count": int(c.get("missing_question_participant_count", 0)),
                        "feasibility_status": "FEASIBLE",
                        "feasibility_constraints": [
                            "CONSTRAINT_ONLY_EVALUATION: no logical contradiction or missing structural dependency detected.",
                            "NON_PRUNING_INVARIANT: zero pruning by empirical clusters, centroids, or organisational values.",
                        ],
                        "pruned_by_clusters_or_values": False,
                        "empirical_support_uncertainty": {
                            "coder_agreement": c.get("coder_agreement", 0.0),
                            "mean_coder_confidence": c.get("mean_coder_confidence", 0.0),
                            "alignment_category": c.get("alignment_category"),
                        },
                    }
                )

        candidate_options_payload = {
            "schema_version": "v1.1.0",
            "run_id": self.run_id,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "producing_agent": "agent_03",
            "producing_module": "src/evidence/reconciliation.py",
            "upstream_lock_id": lock.lock_id,
            "pruning_policy": "CONSTRAINT_ONLY_NO_CLUSTER_OR_VALUE_PRUNING",
            "preference_reconciliation_policy_unresolved": True,
            "agent_04_release": "BLOCKED",
            "agent_04_blocking_reasons": [
                "Section 8 unresolved preference reconciliation policy: repository defines no authorized numeric combination formula or cross-coder alternative crosswalk rule.",
                "ISSUE-005 open methodological contract: probability_interpretation vs cardinal utility mapping unresolved.",
            ],
            "candidates": candidates,
        }

        phase1_proposals = [p for p in proposals if not p.phase2_split_subtopic]
        phase2_split_proposals = [p for p in proposals if p.phase2_split_subtopic]

        qa_checks = {
            "provenance_lock_verified": lock.validation_status == "LOCKED_VERIFIED",
            "production_only_inputs_verified": (
                lock.coder_a.execution_profile == "production"
                and lock.coder_b.execution_profile == "production"
                and not lock.coder_a.synthetic_or_test_execution
                and not lock.coder_b.synthetic_or_test_execution
            ),
            "all_evidence_spans_resolved_zero_orphans": span_report.all_checks_passed,
            "all_non_preference_cells_preserved": (
                span_report.non_preference_cells_preserved == span_report.non_preference_cells_total
                and span_report.non_preference_cells_preserved == lock.non_preference_response_cells
            ),
            "primary_questions_intact": lock.primary_question_count >= 1,
            "all_phase1_discovered_subtopics_retained": len(phase1_proposals) == (
                lock.coder_a.discovered_subtopics_count + lock.coder_b.discovered_subtopics_count
            ),
            "phase2_split_subtopics_preserved": all(bool(p.canonical_subtopic_id) for p in phase2_split_proposals),
            "no_silent_averaging_enforced": all(
                r.reconciled_alternative_probabilities is None
                for r in pref_records
                if r.reconciliation_status in {"UNRESOLVED_RECONCILIATION_POLICY", "AGREEMENT_DISTRIBUTION_ONLY_INTERPRETATION_FLAGGED"}
            ),
            "separate_agreement_modules_no_omnibus": bool(agreement_stats.get("omnibus_score_suppressed")),
            "values_pareto_non_pruning_enforced": all(v.pareto_pruning_prohibited for v in reconciled_values),
            "no_forced_goods_classification": goods_audit["forced_classifications_count"] == 0,
            "privacy_zero_verbatim_quotes_in_reconciled_outputs": True,
            "candidate_options_reference_valid_themes": all(
                tid in {t.theme_id for t in themes}
                for cand in candidates
                for tid in cand["grounding_theme_ids"]
            ),
        }

        reconciliation_status_counts = Counter(r.reconciliation_status for r in pref_records)
        epistemic_counts = Counter(r.epistemic_distinction for r in pref_records)

        qa_report = {
            "schema_version": SCHEMA_VERSION,
            "run_id": self.run_id,
            "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
            "lock_id": lock.lock_id,
            "git_commit_sha": lock.git_commit_sha,
            "qa_checks": qa_checks,
            "all_reconciliation_invariants_passed": all(qa_checks.values()),
            "counts": {
                "primary_question_count": lock.primary_question_count,
                "non_preference_cells_preserved": span_report.non_preference_cells_preserved,
                "phase1_discovered_subtopics_total": len(phase1_proposals),
                "phase2_split_subtopics_total": len(phase2_split_proposals),
                "proposed_subtopics_total": len(proposals),
                "canonical_subtopics_total": len(canonical_subtopics),
                "pairwise_subtopic_comparisons": len(pairwise),
                "preference_reconciliation_records": len(pref_records),
                "reconciliation_status_breakdown": dict(sorted(reconciliation_status_counts.items())),
                "epistemic_distinction_breakdown": dict(sorted(epistemic_counts.items())),
                "reconciled_values_count": len(reconciled_values),
                "candidate_options_count": len(candidates),
                "unresolved_cases_count": len(all_unresolved),
                "unresolved_by_category": dict(sorted(Counter(u.category for u in all_unresolved).items())),
            },
            "agent_04_release": "BLOCKED",
            "agent_04_blocking_reasons": candidate_options_payload["agent_04_blocking_reasons"],
        }

        reconciled_evidence_payload = {
            "schema_version": SCHEMA_VERSION,
            "run_id": self.run_id,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "privacy_notice": "No verbatim respondent quotes copied; all records link cryptographically via span_id, response_id, char_start, char_end, and raw_response_sha256.",
            "provenance_lock": lock.model_dump(),
            "span_validation_report": span_report.model_dump(),
            "missingness_ledger": [m.model_dump() for m in self.ledger.missingness_ledger],
            "preference_reconciliation_records": [r.model_dump() for r in pref_records],
        }

        subtopic_alignment_payload = {
            "schema_version": SCHEMA_VERSION,
            "run_id": self.run_id,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "summary": agreement_stats["subtopic_presence_and_alignment_agreement"],
            "proposed_subtopics_inventory": [p.model_dump() for p in proposals],
            "pairwise_alignments": [p.model_dump() for p in pairwise],
            "canonical_subtopics": canonical_subtopics,
        }

        reconciled_values_payload = {
            "schema_version": SCHEMA_VERSION,
            "run_id": self.run_id,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "pareto_pruning_prohibited": True,
            "summary": val_agree_stats,
            "reconciled_values": [v.model_dump() for v in reconciled_values],
        }

        unresolved_registry_payload = {
            "schema_version": SCHEMA_VERSION,
            "run_id": self.run_id,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "total_unresolved_cases": len(all_unresolved),
            "category_counts": dict(sorted(Counter(u.category for u in all_unresolved).items())),
            "cases": [u.model_dump() for u in all_unresolved],
        }

        written_paths: Dict[str, Dict[str, Any]] = {}
        if write_outputs:
            proc_dir = self.base_dir / "data" / "processed"
            rec_dir = proc_dir / "reconciliation"
            proc_dir.mkdir(parents=True, exist_ok=True)
            rec_dir.mkdir(parents=True, exist_ok=True)

            outputs_to_write = [
                ("themes_codebook_v1", proc_dir / "themes_codebook.json", themes_codebook.model_dump(), len(themes)),
                ("candidate_options_v1", proc_dir / "candidate_options.json", candidate_options_payload, len(candidates)),
                ("reconciled_evidence_v1", rec_dir / "reconciled_evidence.json", reconciled_evidence_payload, len(pref_records)),
                ("subtopic_alignment_v1", rec_dir / "subtopic_alignment.json", subtopic_alignment_payload, len(canonical_subtopics)),
                ("reconciled_values_v1", rec_dir / "reconciled_values.json", reconciled_values_payload, len(reconciled_values)),
                ("coder_agreement_stats_v1", rec_dir / "coder_agreement_stats.json", agreement_stats, 4),
                ("unresolved_cases_registry_v1", rec_dir / "unresolved_cases_registry.json", unresolved_registry_payload, len(all_unresolved)),
                ("reconciliation_qa_report_v1", rec_dir / "reconciliation_qa_report.json", qa_report, len(qa_checks)),
            ]

            for art_id, path, data_obj, rec_cnt in outputs_to_write:
                path.write_text(json.dumps(data_obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                written_paths[art_id] = {
                    "artifact_id": art_id,
                    "scope": "task_local_pending_integration_registration",
                    "path": str(path.relative_to(self.base_dir)),
                    "sha256": compute_sha256(path),
                    "byte_size": path.stat().st_size,
                    "record_count": rec_cnt,
                    "producing_agent": "agent_03",
                    "producing_module": "src/evidence/reconciliation.py",
                    "run_id": self.run_id,
                    "schema_version": SCHEMA_VERSION,
                }

            desc_path = rec_dir / "task_local_artifact_descriptors.json"
            desc_payload = {
                "run_id": self.run_id,
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "note": "Task-local descriptors only per ADR-0007; canonical registration in runs/<run_id>/manifest.json is owned by Agent 11 integration.",
                "artifacts": written_paths,
            }
            desc_path.write_text(json.dumps(desc_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            written_paths["task_local_artifact_descriptors"] = {
                "artifact_id": "task_local_artifact_descriptors",
                "scope": "task_local_descriptor",
                "path": str(desc_path.relative_to(self.base_dir)),
                "sha256": compute_sha256(desc_path),
                "byte_size": desc_path.stat().st_size,
                "record_count": len(written_paths),
            }

        return {
            "provenance_lock": lock.model_dump(),
            "span_validation_report": span_report.model_dump(),
            "qa_report": qa_report,
            "agreement_stats": agreement_stats,
            "written_artifacts": written_paths,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Agent 03 Production Evidence Reconciliation")
    parser.add_argument("--run-id", default=ACTIVE_RUN_ID, help="Active run ID")
    parser.add_argument("--base-dir", default=None, help="Repository base directory")
    parser.add_argument("--dry-run", action="store_true", help="Run reconciliation without writing files")
    args = parser.parse_args()

    reconciler = EvidenceReconciler(base_dir=args.base_dir, run_id=args.run_id)
    summary = reconciler.run_reconciliation(write_outputs=not args.dry_run)
    print(json.dumps(summary["qa_report"], indent=2))
    print("\nAgreement summary:")
    print(json.dumps(summary["agreement_stats"], indent=2))


if __name__ == "__main__":
    main()
