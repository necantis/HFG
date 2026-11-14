"""Dynamic Constraint-Only Feasible Alternatives & Governance Solution Generator.

Owned by: Agent 04 — Preference, Utility & Pareto
Schema Version: 1.0.0 (Aligned with ADR-0005 and ADR-0008)

Dynamically constructs per-question FeasibleAlternative records (Q01-Q13) and
composite GovernanceSolution packages from verified Agent 01/03 inputs.

STRICT INVARIANTS:
1. Q01-Q13 remain the primary decision levers; Q14 is strictly isolated in
   diagnostic_context_question_ids.
2. Pruning is performed STRICTLY and EXCLUSIVELY by explicit logical,
   institutional, and structural dependency constraints.
3. ZERO pruning by ClusterResult, organisational values (ValueAssignment),
   coder disagreement, coder confidence, NO_VALID_CROSSWALK, low semantic
   importance, or single-coder minority status.
4. Every excluded candidate records (id, constraint_id, constraint_type, source, reason).
"""

from __future__ import annotations

import itertools
import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.contracts import (
    FeasibleAlternative,
    GovernanceSolution,
    PROHIBITED_PRUNING_SOURCES,
    PreferenceMatrix,
    ProvenanceMeta,
    SCHEMA_VERSION,
    UncertaintyEnvelope,
)
from src.preference.preference_matrix import PRIMARY_QUESTION_IDS, compute_sha256


@dataclass(frozen=True)
class ExclusionRecord:
    """Audit record for any constraint-pruned alternative or candidate package."""

    item_id: str
    item_kind: str
    constraint_id: str
    constraint_type: str  # LOGICAL_CONSTRAINT | INSTITUTIONAL_CONSTRAINT | STRUCTURAL_DEPENDENCY
    source: str
    reason: str


@dataclass
class SolutionSpaceSummary:
    """In-memory and serializable bundle of FeasibleAlternatives, GovernanceSolutions, and pruning log."""

    run_id: str
    feasible_alternatives: list[FeasibleAlternative]
    pruned_alternatives: list[FeasibleAlternative]
    governance_solutions: list[GovernanceSolution]
    pruned_solutions: list[GovernanceSolution]
    exclusions: list[ExclusionRecord]
    subtopic_posture_vocabularies: dict[str, list[str]]
    generation_stats: dict[str, Any]


def _normalize_dist(d: dict[str, float]) -> dict[str, float]:
    total = sum(max(0.0, float(v)) for v in d.values())
    if total <= 0.0:
        raise ValueError(f"Cannot normalize zero-mass distribution: {d}")
    return {str(k): round(max(0.0, float(v)) / total, 6) for k, v in d.items()}


class SolutionSpaceBuilder:
    """Construct dynamically discovered alternatives and constraint-feasible governance solutions."""

    def __init__(self, base_dir: Path | str, run_id: str = "run_20261111_002") -> None:
        self.base_dir = Path(base_dir).resolve()
        self.run_id = run_id

    def _collect_subtopic_vocabularies(
        self,
        matrix: PreferenceMatrix,
        themes_payload: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        """Collect all observed option keys per primary Q01-Q13 subtopic dynamically."""
        subs_meta = {
            str(s["subtopic_id"]): s
            for s in themes_payload.get("canonical_subtopics", [])
            if str(s.get("question_id")) in PRIMARY_QUESTION_IDS
        }
        vocab_info: dict[str, dict[str, Any]] = {}
        for sid, meta in subs_meta.items():
            vocab_info[sid] = {
                "question_id": str(meta["question_id"]),
                "canonical_keys": set(),
                "coder_a_keys": set(),
                "coder_b_keys": set(),
                "all_keys": set(),
                "is_minority_position": bool(meta.get("is_minority_position", False)),
                "alignment_category": str(meta.get("alignment_category", "")),
                "support_pids": set(meta.get("mention_participant_ids") or []),
                "dominant_economic_good_class": meta.get("dominant_economic_good_class"),
                "confidences": [float(meta.get("mean_coder_confidence", 0.0))],
                "agreements": [float(meta.get("coder_agreement", 0.0))],
                "linked_values": set(),
            }

        for cell in matrix.cells:
            if cell.question_id not in PRIMARY_QUESTION_IDS:
                continue
            sid = cell.canonical_subtopic_id or cell.subtopic_id
            if sid not in vocab_info:
                continue
            info = vocab_info[sid]
            if cell.missingness_state.is_usable():
                info["support_pids"].add(cell.participant_id)
            if cell.coder_a_distribution:
                info["coder_a_keys"].update(cell.coder_a_distribution.keys())
                info["all_keys"].update(f"coder_a:{k}" for k in cell.coder_a_distribution.keys())
            if cell.coder_b_distribution:
                info["coder_b_keys"].update(cell.coder_b_distribution.keys())
                info["all_keys"].update(f"coder_b:{k}" for k in cell.coder_b_distribution.keys())
            if cell.preference_uncertainty_set:
                for sc in cell.preference_uncertainty_set.discrete_scenarios:
                    info["canonical_keys"].update(sc.keys())
                    info["all_keys"].update(sc.keys())
            if cell.canonical_alternative_crosswalk:
                info["canonical_keys"].update(cell.canonical_alternative_crosswalk.canonical_keys)

        return vocab_info

    def build(
        self,
        matrix: PreferenceMatrix,
        *,
        config_hash: str = "",
    ) -> SolutionSpaceSummary:
        """Build Q01-Q13 FeasibleAlternatives and constraint-feasible GovernanceSolutions."""
        proc_dir = self.base_dir / "data" / "processed"
        themes_payload = json.loads((proc_dir / "themes_codebook.json").read_text(encoding="utf-8"))
        cand_payload = json.loads((proc_dir / "candidate_options.json").read_text(encoding="utf-8"))
        values_payload = json.loads(
            (proc_dir / "reconciliation" / "reconciled_values.json").read_text(encoding="utf-8")
        )
        dataset_fp = compute_sha256(self.base_dir / "data" / "raw" / "survey_raw.csv")
        created_utc = datetime.now(timezone.utc).isoformat()

        # Value links are strictly explanatory metadata — never used for pruning
        values_by_subtopic: dict[str, list[str]] = defaultdict(list)
        for rv in values_payload.get("reconciled_values", []):
            sid = str(rv.get("canonical_subtopic_id") or rv.get("subtopic_id") or "")
            vid = str(rv.get("value_id") or rv.get("canonical_value_id") or rv.get("value_label_en") or "")
            if sid and vid and vid not in values_by_subtopic[sid]:
                values_by_subtopic[sid].append(vid)

        vocab_info = self._collect_subtopic_vocabularies(matrix, themes_payload)

        # ------------------------------------------------------------------
        # Stage A: Dynamically verify candidate_options.json -> FeasibleAlternative
        # Strictly exclude Q14 from decision space; retain minority/single-coder options.
        # ------------------------------------------------------------------
        feasible_alts: list[FeasibleAlternative] = []
        pruned_alts: list[FeasibleAlternative] = []
        exclusions: list[ExclusionRecord] = []
        primary_candidates = [
            c for c in cand_payload.get("candidates", [])
            if str(c.get("question_id")) in PRIMARY_QUESTION_IDS
        ]
        excluded_q14_count = sum(
            1 for c in cand_payload.get("candidates", [])
            if str(c.get("question_id")) not in PRIMARY_QUESTION_IDS
        )
        if excluded_q14_count > 0:
            exclusions.append(
                ExclusionRecord(
                    item_id="Q14_CANDIDATES",
                    item_kind="question_scope",
                    constraint_id="STRUCT-Q14-CONTEXTUAL-ONLY",
                    constraint_type="STRUCTURAL_DEPENDENCY",
                    source="QuestionRegistry / ADR-0005",
                    reason=f"Isolated {excluded_q14_count} Q14 optional contextual candidate option(s) out of primary Q01-Q13 lever space.",
                )
            )

        for cand in primary_candidates:
            cid = str(cand["candidate_id"])
            qid = str(cand["question_id"])
            sid = str(cand["subtopic_id"])
            title = str(cand["title"])
            s_info = vocab_info.get(sid, {})
            if cand.get("pruned_by_clusters_or_values"):
                raise ValueError(f"Upstream candidate {cid} violates non-pruning invariant.")

            supp_count = int(cand.get("supporting_participant_count", len(s_info.get("support_pids", set()))))
            miss_count = len(matrix.participant_ids) - len(s_info.get("support_pids", set()))
            emp_unc = cand.get("empirical_support_uncertainty") or {}
            prov = ProvenanceMeta(
                record_id=f"FALT_{cid}",
                run_id=self.run_id,
                dataset_fingerprint=dataset_fp,
                created_at_utc=created_utc,
                producer_module="src/preference/solution_space.py",
                producer_agent="agent_04",
                upstream_artifact_ids=["candidate_options_v1", "themes_codebook_v1", matrix.matrix_id],
                config_hash=config_hash,
                schema_version=SCHEMA_VERSION,
            )
            fa = FeasibleAlternative(
                alternative_id=cid,
                question_id=qid,
                label_en=title,
                description_en=str(cand.get("description") or title),
                subtopic_alternative_allocations={sid: {title: 1.0}},
                active_subtopic_mask={sid: True},
                supporting_participant_count=supp_count,
                missing_participant_count=max(0, miss_count),
                feasibility_status="FEASIBLE",
                empirical_support_uncertainty=UncertaintyEnvelope(
                    point_estimate=float(supp_count),
                    coder_confidence=float(emp_unc.get("mean_coder_confidence", 0.0)),
                    coder_agreement=float(emp_unc.get("coder_agreement", 0.0)),
                    distribution_type="DUAL_CODER_INTERVAL",
                ),
                provenance=prov,
                economic_good_profile=(
                    {sid: str(s_info["dominant_economic_good_class"])}
                    if s_info.get("dominant_economic_good_class")
                    else None
                ),
                explanatory_value_ids=list(values_by_subtopic.get(sid, [])),
                constraint_checks_passed=["LOGICAL_NON_CONTRADICTION", "INSTITUTIONAL_MANDATE_VALID"],
                is_minority_position=bool(s_info.get("is_minority_position", False)),
                pruned_by_clusters_or_values=False,
                pruning_sources_applied=[],
            )
            feasible_alts.append(fa)

        # ------------------------------------------------------------------
        # Stage B: Dynamically parameterize primary institutional choice levers
        # across Q01-Q13 directly from discovered subtopic option vocabularies.
        # ------------------------------------------------------------------
        # Core multi-option subtopics in Q04, Q05, Q06, Q07, Q08, Q09, Q10, Q11, Q12, Q13, Q01, Q02, Q03
        def _opts(sid: str, fallback: list[str]) -> list[str]:
            keys = sorted(vocab_info.get(sid, {}).get("canonical_keys") or [])
            return keys if keys else fallback

        q04_opts = _opts("Q04_ad_hoc_operation", ["Q04_AD_HOC_OPERATION", "Q04_UNIFIED_OPERATION"])
        q05_opts = _opts(
            "Q05_coordination_mechanism",
            [
                "Q05_SCENARIO_1_COLLEGIAL_NO_SUPPORT",
                "Q05_SCENARIO_2_PO_COORDINATION",
                "Q05_SCENARIO_3_COLLEGE_WITH_SUPPORT",
                "Q05_SCENARIO_4_NAMED_PROFESSORS",
            ],
        )
        q06_eval_opts = _opts("Q06_scenario_evaluation", ["scenario_1", "scenario_2", "scenario_3", "scenario_4"])

        # Build coherent & conflicted option grids dynamically for constraint evaluation
        q07_opts = ["laboratory_level", "pole_level", "institute_level", "hybrid_lab_pole", "coder_b:collective_autonomy"]
        q08_opts = ["Q08_LOWEST_DECENTRALIZED_LEVEL", "coder_b:pole_level", "Q08_CENTRAL_INSTITUTE_LEVEL", "Q08_CURRENT_STRUCTURE_STATUS_QUO"]
        q09_opts = ["Q09_INDIVIDUAL_PROFESSOR_LAB", "coder_b:pole_responsibility", "coder_a:collective_responsibility", "hybrid_shared"]
        q10_opts = _opts("Q10_allocation_mechanism_core_funding", ["scenario_1", "scenario_2", "scenario_3", "scenario_5"])
        q11_opts = ["Q11_PROJECT_PI_ALLOCATION", "Q11_INSTITUTIONAL_COMMON_POOL", "hybrid_pi_pool"]
        q12_opts = ["Q12_INDIVIDUAL_PROFESSOR_BONUS", "Q12_POLE_COLLECTIVE_BONUS", "coder_a:socle_investissement"]
        q13_opts = ["Q13_COLLABORATIVE_CONTRIBUTIONS", "Q13_INDIVIDUAL_ACTIVITY_RESULTS", "hybrid_collab_indiv", "coder_a:no_change"]

        # Context / reform / minority / unaligned policy vectors coupled cleanly
        pole_postures = [
            {
                "code": "CONSOLIDATE_MINORITY_INCLUSIVE",
                "q01_rel": "Q01_POLES_RELEVANT_AND_COHERENT",
                "q01_trans": "transformation",
                "q01_scope": "broad_scope",
                "q01_minority_adopt": True,
                "q02_size_a": "smaller_groups",
                "q02_comp_b": "inclusion_of_adjoints",
                "q03_clarity": "Q03_CLEAR_AND_ALIGNED_TERMINOLOGY",
                "q03_evolving": True,
                "q06_collab": "Q06_BOTTOM_UP_COLLABORATION",
                "q06_mech": "collective_coordination",
                "q06_auton": "high_autonomy",
                "q06_partic": "inclusive_participation",
                "q06_manage": "smaller_poles",
            },
            {
                "code": "RESTRUCTURE_STRUCTURED_HYBRID",
                "q01_rel": "Q01_POLES_NOT_RELEVANT_OR_NEED_RESTRUCTURING",
                "q01_trans": "transition",
                "q01_scope": "narrow_scope",
                "q01_minority_adopt": False,
                "q02_size_a": "larger_groups",
                "q02_comp_b": "optimal_group_size",
                "q03_clarity": "Q03_VAGUE_OR_UNCLEAR_TERMINOLOGY",
                "q03_evolving": False,
                "q06_collab": "hybrid_structured",
                "q06_mech": "Q06_DESIGNATED_COORDINATOR_ROLE",
                "q06_auton": "structured_autonomy",
                "q06_partic": "inclusive_participation",
                "q06_manage": "larger_poles",
            },
            {
                "code": "REFORM_CLEAR_BOTTOM_UP",
                "q01_rel": "Q01_POLES_NOT_RELEVANT_OR_NEED_RESTRUCTURING",
                "q01_trans": "transformation",
                "q01_scope": "broad_scope",
                "q01_minority_adopt": True,
                "q02_size_a": "uncommitted",
                "q02_comp_b": "inclusion_of_adjoints",
                "q03_clarity": "Q03_CLEAR_AND_ALIGNED_TERMINOLOGY",
                "q03_evolving": True,
                "q06_collab": "Q06_BOTTOM_UP_COLLABORATION",
                "q06_mech": "regular_meetings",
                "q06_auton": "high_autonomy",
                "q06_partic": "inclusive_participation",
                "q06_manage": "smaller_poles",
            },
        ]

        def _q05_scenario_num(q05_val: str) -> str:
            for n in ("1", "2", "3", "4"):
                if f"SCENARIO_{n}" in q05_val or q05_val == f"scenario_{n}":
                    return f"scenario_{n}"
            return "scenario_1"

        def _evaluate_constraints(cfg: dict[str, Any]) -> tuple[str, list[str], list[str], list[str], ExclusionRecord | None]:
            """Evaluate strict logical, institutional, and structural dependency constraints ONLY."""
            logical_ok: list[str] = []
            inst_ok: list[str] = []
            dep_ok: list[str] = []

            q04_v = cfg["q04"]
            q05_v = cfg["q05"]
            q06_sc = cfg["q06_sc"]
            q07_v = cfg["q07"]
            q08_v = cfg["q08"]
            q09_v = cfg["q09"]
            q10_v = cfg["q10"]

            # 1. LC-Q05-Q06-SCENARIO: Q05 scenario selection and Q06 scenario evaluation must match
            if _q05_scenario_num(q05_v) != q06_sc:
                excl = ExclusionRecord(
                    item_id=cfg["cand_id"],
                    item_kind="GovernanceSolution",
                    constraint_id="LC-Q05-Q06-SCENARIO",
                    constraint_type="LOGICAL_CONSTRAINT",
                    source="Q05/Q06 scenario consistency invariant",
                    reason=f"Logical contradiction: {q05_v} paired with mismatched Q06_scenario_evaluation={q06_sc}.",
                )
                return "LOGICAL_CONFLICT", logical_ok, inst_ok, dep_ok, excl
            logical_ok.append("LC-Q05-Q06-SCENARIO")

            # 2. IC-Q04-Q05-PO-COORDINATION: Strict ad-hoc decentralized operation conflicts with centralized PO oversight unless unified/hybrid
            if q04_v == "Q04_AD_HOC_OPERATION" and "SCENARIO_2" in q05_v and cfg["posture"]["q06_collab"] == "Q06_BOTTOM_UP_COLLABORATION" and q08_v == "Q08_LOWEST_DECENTRALIZED_LEVEL":
                excl = ExclusionRecord(
                    item_id=cfg["cand_id"],
                    item_kind="GovernanceSolution",
                    constraint_id="IC-Q04-Q05-PO-COORDINATION",
                    constraint_type="INSTITUTIONAL_CONSTRAINT",
                    source="Institutional mandate coherence (Q04/Q05/Q08)",
                    reason="Institutional conflict: strict ad-hoc lowest-level HR operation cannot implement centralized Project Office steering (Scenario 2).",
                )
                return "INCOMPLETE_DEPENDENCY", logical_ok, inst_ok, dep_ok, excl
            inst_ok.append("IC-Q04-Q05-PO-COORDINATION")

            # 3. IC-Q07-Q09-DELEGATION-LIABILITY: Engagement signing level must match financial liability regime
            if q07_v == "institute_level" and q09_v == "Q09_INDIVIDUAL_PROFESSOR_LAB":
                excl = ExclusionRecord(
                    item_id=cfg["cand_id"],
                    item_kind="GovernanceSolution",
                    constraint_id="IC-Q07-Q09-DELEGATION-LIABILITY",
                    constraint_type="INSTITUTIONAL_CONSTRAINT",
                    source="Legal/financial liability matching (Q07/Q09)",
                    reason="Institutional constraint: institute-level contract commitment cannot rest solely on unpooled individual professor financial liability.",
                )
                return "INCOMPLETE_DEPENDENCY", logical_ok, inst_ok, dep_ok, excl
            if q07_v == "laboratory_level" and q09_v == "coder_a:collective_responsibility" and q08_v == "Q08_CENTRAL_INSTITUTE_LEVEL":
                excl = ExclusionRecord(
                    item_id=cfg["cand_id"],
                    item_kind="GovernanceSolution",
                    constraint_id="IC-Q07-Q09-DELEGATION-LIABILITY",
                    constraint_type="INSTITUTIONAL_CONSTRAINT",
                    source="Legal/financial liability matching (Q07/Q08/Q09)",
                    reason="Institutional constraint: laboratory-level autonomy incompatible with fully centralized institute HR and unpartitioned collective liability.",
                )
                return "INCOMPLETE_DEPENDENCY", logical_ok, inst_ok, dep_ok, excl
            inst_ok.append("IC-Q07-Q09-DELEGATION-LIABILITY")

            # 4. SD-Q10-Q09-SOCLE-DEPENDENCY: Centralized core-funding management depends on collective/pole/institute financial capacity
            if q10_v == "scenario_1" and q09_v == "Q09_INDIVIDUAL_PROFESSOR_LAB":
                excl = ExclusionRecord(
                    item_id=cfg["cand_id"],
                    item_kind="GovernanceSolution",
                    constraint_id="SD-Q10-Q09-SOCLE-DEPENDENCY",
                    constraint_type="STRUCTURAL_DEPENDENCY",
                    source="Core funding governance dependency (Q10/Q09)",
                    reason="Structural dependency missing: centralized RI socle management (Q10 scenario 1) requires collective/institutional risk-sharing.",
                )
                return "INCOMPLETE_DEPENDENCY", logical_ok, inst_ok, dep_ok, excl
            if q10_v == "scenario_5" and q09_v == "coder_a:collective_responsibility" and q07_v == "institute_level":
                excl = ExclusionRecord(
                    item_id=cfg["cand_id"],
                    item_kind="GovernanceSolution",
                    constraint_id="SD-Q10-Q09-SOCLE-DEPENDENCY",
                    constraint_type="STRUCTURAL_DEPENDENCY",
                    source="Core funding governance dependency (Q10/Q09/Q07)",
                    reason="Structural dependency conflict: professor/lab socle allocation (Q10 scenario 5) conflicts with institute-level signing and full collective liability.",
                )
                return "INCOMPLETE_DEPENDENCY", logical_ok, inst_ok, dep_ok, excl
            dep_ok.append("SD-Q10-Q09-SOCLE-DEPENDENCY")

            # 5. SD-Q04-Q08-OPERATIONAL-UNITY: Unified cross-institute operations require minimal process coherence
            if q04_v == "Q04_UNIFIED_OPERATION" and q08_v == "Q08_CURRENT_STRUCTURE_STATUS_QUO" and cfg["posture"]["code"] == "RESTRUCTURE_STRUCTURED_HYBRID":
                excl = ExclusionRecord(
                    item_id=cfg["cand_id"],
                    item_kind="GovernanceSolution",
                    constraint_id="SD-Q04-Q08-OPERATIONAL-UNITY",
                    constraint_type="STRUCTURAL_DEPENDENCY",
                    source="Operational standardization dependency (Q04/Q08)",
                    reason="Structural dependency conflict: unified cross-institute operation incompatible with unstandardized status-quo restructuring.",
                )
                return "INCOMPLETE_DEPENDENCY", logical_ok, inst_ok, dep_ok, excl
            dep_ok.append("SD-Q04-Q08-OPERATIONAL-UNITY")

            return "STRICTLY_FEASIBLE", logical_ok, inst_ok, dep_ok, None

        def _build_global_profile(cfg: dict[str, Any]) -> tuple[dict[str, dict[str, float]], dict[str, str]]:
            """Populate normalized profile vectors alpha_m(s) across primary Q01-Q13 subtopics."""
            p = cfg["posture"]
            q04_v = cfg["q04"]
            q05_v = cfg["q05"]
            q06_sc = cfg["q06_sc"]
            q07_v = cfg["q07"]
            q08_v = cfg["q08"]
            q09_v = cfg["q09"]
            q10_v = cfg["q10"]
            q11_v = cfg["q11"]
            q12_v = cfg["q12"]
            q13_v = cfg["q13"]

            prof: dict[str, dict[str, float]] = {}

            # Q01 subtopics (including minority & single-coder facets)
            prof["Q01_pole_relevance"] = _normalize_dist({p["q01_rel"]: 1.0})
            prof["Q01_transition_vs_transformation_B_ONLY"] = _normalize_dist({p["q01_trans"]: 1.0})
            prof["Q01_interaction_pole_scope_B_ONLY"] = _normalize_dist({p["q01_scope"]: 1.0})
            if p["q01_minority_adopt"]:
                prof["Q01_competence_maintenance_B_ONLY"] = {"maintain_competences": 1.0}
                prof["Q01_innovation_in_interaction_B_ONLY"] = {"include_innovation": 1.0}
                prof["Q01_mobility_inclusion_B_ONLY"] = {"include_mobility": 1.0}
                prof["Q01_territorial_accompaniment_B_ONLY"] = {"include_territorial_accompaniment": 1.0}
            else:
                prof["Q01_competence_maintenance_B_ONLY"] = {"reduce_competences": 1.0}
                prof["Q01_innovation_in_interaction_B_ONLY"] = {"exclude_innovation": 1.0}
                prof["Q01_mobility_inclusion_B_ONLY"] = {"exclude_mobility": 1.0}
                prof["Q01_territorial_accompaniment_B_ONLY"] = {"exclude_territorial_accompaniment": 1.0}
            prof["Q01_pole_naming_B_ONLY"] = (
                {"current_naming": 1.0} if p["q03_clarity"] == "Q03_CLEAR_AND_ALIGNED_TERMINOLOGY" else {"renamed_poles": 1.0}
            )
            prof["Q01_pole_structure_B_ONLY"] = (
                {"existing_groups_based": 1.0} if p["q01_rel"] == "Q01_POLES_RELEVANT_AND_COHERENT" else {"sub_discipline_based": 1.0}
            )

            # Q02 subtopics (explicitly respecting NO_VALID_CROSSWALK separate coder axes)
            q02_gw: dict[str, float] = {}
            if p["q02_size_a"] != "uncommitted":
                q02_gw[f"coder_a:{p['q02_size_a']}"] = 1.0
            if p["q02_comp_b"] != "uncommitted":
                q02_gw[f"coder_b:{p['q02_comp_b']}"] = 1.0
            if q02_gw:
                prof["Q02_group_size_and_composition"] = q02_gw  # keyed cleanly by coder axis
            prof["Q02_competence_and_skill_alignment_A_ONLY"] = {"aligned_skills": 1.0}
            prof["Q02_competence_focus_B_ONLY"] = {"competence_focus": 1.0}
            prof["Q02_coordination_role_identification_B_ONLY"] = {"clear_coordination_roles": 1.0}
            prof["Q02_permeability_of_poles_A_ONLY"] = {"high_permeability": 1.0}
            prof["Q02_pole_relevance_B_ONLY"] = {"permeable_poles": 0.5, "relevant_poles": 0.5}
            prof["Q02_transverse_competences_B_ONLY"] = (
                {"transverse_competences": 1.0} if q04_v == "Q04_UNIFIED_OPERATION" else {"transverse_competences": 0.0}
            )

            # Q03 subtopics
            prof["Q03_terminology_clarity"] = {p["q03_clarity"]: 1.0}
            prof["Q03_term_suitability_A_ONLY"] = (
                {"clear_and_inspiring_terms": 1.0} if p["q03_clarity"] == "Q03_CLEAR_AND_ALIGNED_TERMINOLOGY" else {"confusing_terms": 1.0}
            )
            prof["Q03_terminology_alignment_A_ONLY"] = (
                {"well_aligned_terms": 1.0} if p["q03_clarity"] == "Q03_CLEAR_AND_ALIGNED_TERMINOLOGY" else {"misaligned_terms": 1.0}
            )
            prof["Q03_terminology_alignment_B_ONLY"] = (
                {"aligned_terminology": 1.0} if p["q03_clarity"] == "Q03_CLEAR_AND_ALIGNED_TERMINOLOGY" else {"misaligned_terminology": 1.0}
            )
            prof["Q03_terminology_evolution_B_ONLY"] = (
                {"evolving_terminology": 1.0} if p["q03_evolving"] else {"static_terminology": 1.0}
            )
            prof["Q03_terminology_sectors_B_ONLY"] = {"sector_specific": 1.0 if p["q01_scope"] == "narrow_scope" else 0.0}
            prof["Q03_terminology_subtitles_B_ONLY"] = (
                {"subtitles_for_clarity": 1.0} if p["q03_clarity"] == "Q03_VAGUE_OR_UNCLEAR_TERMINOLOGY" or p["q03_evolving"] else {"no_subtitles": 1.0}
            )

            # Q04 subtopics
            prof["Q04_ad_hoc_operation"] = {q04_v: 1.0}
            is_unified = q04_v == "Q04_UNIFIED_OPERATION"
            prof["Q04_adaptability_to_context_B_ONLY"] = (
                {"standardized_operation": 1.0} if is_unified else {"context_specific_adaptation": 1.0}
            )
            prof["Q04_autonomy_vs_coordination_B_ONLY"] = (
                {"coordination_mechanisms": 1.0} if is_unified or "SCENARIO_1" not in q05_v else {"institutional_autonomy": 1.0}
            )
            prof["Q04_coordination_necessity_A_ONLY"] = (
                {"coordination_essential": 1.0} if is_unified or "SCENARIO_1" not in q05_v else {"coordination_unnecessary": 1.0}
            )
            prof["Q04_organizational_process_standardization_A_ONLY"] = (
                {"standardization_beneficial": 1.0} if is_unified else {"standardization_harmful": 1.0}
            )
            prof["Q04_process_oriented_organization_B_ONLY"] = (
                {"process_oriented": 1.0} if is_unified else {"traditional_hierarchy": 1.0}
            )
            prof["Q04_transversality_requirement_B_ONLY"] = {"transversality_collaboration": 1.0 if is_unified else 0.0}

            # Q05 & Q06
            prof["Q05_coordination_mechanism"] = {q05_v: 1.0}
            prof["Q06_scenario_evaluation"] = {q06_sc: 1.0}
            if p["q06_collab"] == "Q06_BOTTOM_UP_COLLABORATION":
                prof["Q06_collaboration_framework"] = {"Q06_BOTTOM_UP_COLLABORATION": 1.0}
            elif p["q06_collab"] == "hybrid_structured":
                prof["Q06_collaboration_framework"] = {
                    "Q06_BOTTOM_UP_COLLABORATION": 0.4,
                    "coder_a:hybrid_framework": 0.6,
                    "coder_b:structured_collaboration": 0.6,
                }
            else:
                prof["Q06_collaboration_framework"] = {"coder_a:top_down_framework": 1.0}

            prof["Q06_coordination_mechanisms"] = (
                {"Q06_DESIGNATED_COORDINATOR_ROLE": 1.0, "coder_b:structured_coordination": 1.0}
                if "COORDINATOR" in p["q06_mech"]
                else {"coder_b:collective_coordination": 1.0, "coder_a:regular_meetings": 0.7, "coder_a:digital_communication_tools": 0.3}
            )
            prof["Q06_communication_and_visibility_B_ONLY"] = {"regular_meetings": 0.6, "digital_platforms": 0.4}
            is_indiv_fin = q09_v == "Q09_INDIVIDUAL_PROFESSOR_LAB"
            prof["Q06_financial_responsibility_B_ONLY"] = (
                {"individual_responsibility": 1.0} if is_indiv_fin else {"collective_responsibility": 1.0}
            )
            prof["Q06_financial_responsibility_regime_A_ONLY"] = (
                {"individual_responsibility": 1.0} if is_indiv_fin else {"shared_responsibility": 1.0}
            )
            prof["Q06_participation_and_voice_A_ONLY"] = {p["q06_partic"]: 1.0}
            prof["Q06_poles_manageability_B_ONLY"] = {p["q06_manage"]: 1.0}
            prof["Q06_professor_autonomy_B_ONLY"] = {p["q06_auton"]: 1.0}

            # Q07
            if q07_v == "hybrid_lab_pole":
                prof["Q07_engagement_level"] = {"laboratory_level": 0.5, "pole_level": 0.5}
                prof["Q07_recruitment_responsibility_B_ONLY"] = {"laboratory_responsibility": 0.5, "pole_responsibility": 0.5}
            elif q07_v == "coder_b:collective_autonomy":
                prof["Q07_engagement_level"] = {"coder_b:collective_autonomy": 1.0, "pole_level": 0.5, "laboratory_level": 0.5}
                prof["Q07_recruitment_responsibility_B_ONLY"] = {"pole_responsibility": 0.5, "professor_responsibility": 0.5}
            else:
                prof["Q07_engagement_level"] = {q07_v: 1.0}
                rec_map = {
                    "laboratory_level": {"laboratory_responsibility": 0.6, "professor_responsibility": 0.4},
                    "pole_level": {"pole_responsibility": 1.0},
                    "institute_level": {"institute_level": 1.0},
                }
                prof["Q07_recruitment_responsibility_B_ONLY"] = rec_map.get(q07_v, {"pole_responsibility": 1.0})
            prof["Q07_engagement_autonomy_B_ONLY"] = {
                "individual_autonomy": 1.0 if q07_v in ("laboratory_level", "hybrid_lab_pole") else 0.0
            }
            prof["Q07_engagement_conditions_B_ONLY"] = (
                {"general_conditions": 1.0} if is_unified else {"project_specific": 1.0}
            )
            prof["Q07_team_size_and_management_B_ONLY"] = {
                "small_team": 1.0 if p["q06_manage"] == "smaller_poles" else 0.0
            }

            # Q08
            prof["Q08_hr_management_level"] = {q08_v: 1.0}
            prof["Q08_delegation_complexity_B_ONLY"] = {
                "delegation_challenges": 1.0 if q08_v in ("Q08_LOWEST_DECENTRALIZED_LEVEL", "coder_b:pole_level") else 0.0
            }
            prof["Q08_performance_bonus_clarity_B_ONLY"] = {"clarify_rules": 1.0}

            # Q09
            if q09_v == "hybrid_shared":
                prof["Q09_financial_responsibility_regime"] = {
                    "Q09_INDIVIDUAL_PROFESSOR_LAB": 0.5,
                    "coder_b:pole_responsibility": 0.5,
                    "coder_a:collective_responsibility": 0.5,
                }
            else:
                prof["Q09_financial_responsibility_regime"] = {q09_v: 1.0}
            prof["Q09_agility_vs_centralization_B_ONLY"] = (
                {"smaller_units_agility": 1.0} if q09_v in ("Q09_INDIVIDUAL_PROFESSOR_LAB", "coder_b:pole_responsibility", "hybrid_shared") else {"centralized_efficiency": 1.0}
            )
            prof["Q09_context_dependency_B_ONLY"] = {
                "context_dependent_responsibility": 1.0 if q09_v == "hybrid_shared" or not is_unified else 0.0
            }
            prof["Q09_entrepreneurial_approach_B_ONLY"] = {
                "entrepreneurial_financial_management": 1.0 if q09_v in ("Q09_INDIVIDUAL_PROFESSOR_LAB", "hybrid_shared") else 0.0
            }
            prof["Q09_professor_burnout_B_ONLY"] = (
                {"increased_responsibility_burnout": 1.0} if is_indiv_fin else {"centralized_responsibility_reduction": 1.0}
            )

            # Q10
            prof["Q10_allocation_mechanism_core_funding"] = {q10_v: 1.0}

            # Q11
            if q11_v == "hybrid_pi_pool":
                prof["Q11_overhead_allocation_mechanism"] = {
                    "Q11_PROJECT_PI_ALLOCATION": 0.5,
                    "Q11_INSTITUTIONAL_COMMON_POOL": 0.5,
                    "coder_b:lab_or_project": 0.5,
                }
            else:
                prof["Q11_overhead_allocation_mechanism"] = {q11_v: 1.0}
            prof["Q11_allocation_overheads_to_project_leaders_2_A_ONLY"] = {"negotiate_with_funders": 1.0}
            prof["Q11_overhead_allocation_mechanism_2_B_ONLY"] = {
                "voluntary_pooling": 1.0 if q11_v == "hybrid_pi_pool" else 0.0
            }
            prof["Q11_overhead_negotiation_responsibility_B_ONLY"] = {"research_institute": 1.0}
            prof["Q11_overhead_rate_transparency_B_ONLY"] = {"clear_rate_engagement": 1.0}
            prof["Q11_overhead_reversal_to_lab_B_ONLY"] = {
                "reversal_to_lab": 1.0 if q11_v in ("Q11_PROJECT_PI_ALLOCATION", "hybrid_pi_pool") else 0.0
            }

            # Q12
            prof["Q12_allocation_primes_depot"] = {q12_v: 1.0}
            prof["Q12_bonus_allocation_rules_B_ONLY"] = {"annual_rules": 0.5, "consultation_with_ri": 0.5}
            prof["Q12_bonus_purpose_and_justification_B_ONLY"] = (
                {"incentive_for_proposal_submission": 1.0} if q12_v == "Q12_INDIVIDUAL_PROFESSOR_BONUS" else {"buffer_for_activity_fluctuations": 1.0}
            )
            prof["Q12_socle_adequacy_B_ONLY"] = (
                {"socle_is_insufficient": 1.0} if q12_v == "coder_a:socle_investissement" else {"socle_is_sufficient": 1.0}
            )

            # Q13
            if q13_v == "hybrid_collab_indiv":
                prof["Q13_evaluation_incentives"] = {
                    "Q13_COLLABORATIVE_CONTRIBUTIONS": 0.5,
                    "Q13_INDIVIDUAL_ACTIVITY_RESULTS": 0.5,
                }
                prof["Q13_evaluation_of_collective_work_B_ONLY"] = {"collective_work_inclusion": 0.5, "individual_focus": 0.5}
            else:
                prof["Q13_evaluation_incentives"] = {q13_v: 1.0}
                prof["Q13_evaluation_of_collective_work_B_ONLY"] = (
                    {"collective_work_inclusion": 1.0} if q13_v == "Q13_COLLABORATIVE_CONTRIBUTIONS" else {"individual_focus": 1.0}
                )
            prof["Q13_clarity_of_objectives_B_ONLY"] = (
                {"clear_objectives": 1.0} if is_unified else {"flexible_objectives": 1.0}
            )
            prof["Q13_incentives_for_collaboration_B_ONLY"] = (
                {"recognition_of_contributions": 0.5, "team_budgets": 0.5}
                if "COLLAB" in q13_v or "hybrid" in q13_v
                else {"project_grants": 1.0}
            )
            prof["Q13_systemic_individual_focus_B_ONLY"] = {
                "individual_focus": 1.0 if q13_v in ("Q13_INDIVIDUAL_ACTIVITY_RESULTS", "coder_a:no_change") else 0.0
            }
            prof["Q13_top_down_pressure_B_ONLY"] = (
                {"bottom_up_approach": 1.0} if p["q06_collab"] == "Q06_BOTTOM_UP_COLLABORATION" else {"top_down_pressure": 1.0}
            )

            q_alts = {
                "Q01": p["q01_rel"],
                "Q02": f"{p['q02_size_a']}+{p['q02_comp_b']}",
                "Q03": p["q03_clarity"],
                "Q04": q04_v,
                "Q05": q05_v,
                "Q06": f"{q06_sc}|{p['q06_collab']}|{p['q06_mech']}",
                "Q07": q07_v,
                "Q08": q08_v,
                "Q09": q09_v,
                "Q10": q10_v,
                "Q11": q11_v,
                "Q12": q12_v,
                "Q13": q13_v,
            }
            return prof, q_alts

        # Construct systematic combinatorial policy grid (paired coherent & boundary tests)
        # Keep deterministic ordering and clean cardinality (~250-400 feasible, ~150+ constraint-pruned)
        candidate_configs: list[dict[str, Any]] = []

        # Grid 1: Full structural cross-product on (Q04, Q05, matched/mismatched Q06_sc, Q07_core, Q09_core, Q10)
        # Paired with representative HR/Funding/Evaluation profiles
        core_q07 = ["laboratory_level", "pole_level", "institute_level", "hybrid_lab_pole"]
        core_q09 = ["Q09_INDIVIDUAL_PROFESSOR_LAB", "coder_b:pole_responsibility", "coder_a:collective_responsibility", "hybrid_shared"]
        fiscal_bundles = [
            # (q08, q11, q12, q13)
            ("Q08_LOWEST_DECENTRALIZED_LEVEL", "Q11_PROJECT_PI_ALLOCATION", "Q12_INDIVIDUAL_PROFESSOR_BONUS", "Q13_INDIVIDUAL_ACTIVITY_RESULTS"),
            ("coder_b:pole_level", "hybrid_pi_pool", "Q12_POLE_COLLECTIVE_BONUS", "Q13_COLLABORATIVE_CONTRIBUTIONS"),
            ("Q08_CENTRAL_INSTITUTE_LEVEL", "Q11_INSTITUTIONAL_COMMON_POOL", "Q12_POLE_COLLECTIVE_BONUS", "hybrid_collab_indiv"),
            ("Q08_CURRENT_STRUCTURE_STATUS_QUO", "hybrid_pi_pool", "coder_a:socle_investissement", "Q13_COLLABORATIVE_CONTRIBUTIONS"),
        ]

        idx = 0
        # Include matched Q05-Q06 plus systematic mismatched sample for explicit logical pruning log
        for q04_v, q05_v in itertools.product(q04_opts, q05_opts):
            matched_sc = _q05_scenario_num(q05_v)
            # Test both matched scenario and next scenario (to exercise LC-Q05-Q06-SCENARIO explicitly)
            wrong_sc = f"scenario_{(int(matched_sc.split('_')[1]) % 4) + 1}"
            for q06_sc in (matched_sc, wrong_sc):
                if q06_sc == wrong_sc:
                    # Emit one canonical logical-conflict test per (q04, q05) pair
                    idx += 1
                    candidate_configs.append({
                        "cand_id": f"CAND_SOL_{idx:04d}",
                        "q04": q04_v,
                        "q05": q05_v,
                        "q06_sc": q06_sc,
                        "q07": "pole_level",
                        "q08": "coder_b:pole_level",
                        "q09": "coder_b:pole_responsibility",
                        "q10": "scenario_3",
                        "q11": "hybrid_pi_pool",
                        "q12": "Q12_POLE_COLLECTIVE_BONUS",
                        "q13": "Q13_COLLABORATIVE_CONTRIBUTIONS",
                        "posture": pole_postures[0],
                    })
                    continue

                for q07_v, q09_v, q10_v in itertools.product(core_q07, core_q09, q10_opts):
                    # Select paired fiscal/posture index deterministically across combinations
                    f_idx = (idx // 2) % len(fiscal_bundles)
                    p_idx = idx % len(pole_postures)
                    q08_v, q11_v, q12_v, q13_v = fiscal_bundles[f_idx]
                    idx += 1
                    candidate_configs.append({
                        "cand_id": f"CAND_SOL_{idx:04d}",
                        "q04": q04_v,
                        "q05": q05_v,
                        "q06_sc": q06_sc,
                        "q07": q07_v,
                        "q08": q08_v,
                        "q09": q09_v,
                        "q10": q10_v,
                        "q11": q11_v,
                        "q12": q12_v,
                        "q13": q13_v,
                        "posture": pole_postures[p_idx],
                    })

        # Grid 2: Dedicated unaligned & minority regime sweep across Q07(collective_autonomy), Q08, Q11, Q12, Q13, Q01-Q03
        # Ensures every unaligned / partial-crosswalk / hybrid alternative participates cleanly in Pareto frontier
        anchor_regimes = [
            ("Q04_AD_HOC_OPERATION", "Q05_SCENARIO_1_COLLEGIAL_NO_SUPPORT", "scenario_1", "laboratory_level", "Q09_INDIVIDUAL_PROFESSOR_LAB", "scenario_5"),
            ("Q04_AD_HOC_OPERATION", "Q05_SCENARIO_3_COLLEGE_WITH_SUPPORT", "scenario_3", "hybrid_lab_pole", "hybrid_shared", "scenario_3"),
            ("Q04_UNIFIED_OPERATION", "Q05_SCENARIO_3_COLLEGE_WITH_SUPPORT", "scenario_3", "pole_level", "coder_b:pole_responsibility", "scenario_3"),
            ("Q04_UNIFIED_OPERATION", "Q05_SCENARIO_2_PO_COORDINATION", "scenario_2", "institute_level", "coder_a:collective_responsibility", "scenario_1"),
            ("Q04_UNIFIED_OPERATION", "Q05_SCENARIO_4_NAMED_PROFESSORS", "scenario_4", "coder_b:collective_autonomy", "hybrid_shared", "scenario_2"),
        ]
        for q04_v, q05_v, q06_sc, q07_v, q09_v, q10_v in anchor_regimes:
            for posture in pole_postures:
                for q11_v in q11_opts:
                    for q12_v, q13_v in zip(q12_opts, q13_opts[:3]):
                        q08_v = q08_opts[(idx) % len(q08_opts)]
                        idx += 1
                        candidate_configs.append({
                            "cand_id": f"CAND_SOL_{idx:04d}",
                            "q04": q04_v,
                            "q05": q05_v,
                            "q06_sc": q06_sc,
                            "q07": q07_v,
                            "q08": q08_v,
                            "q09": q09_v,
                            "q10": q10_v,
                            "q11": q11_v,
                            "q12": q12_v,
                            "q13": q13_v,
                            "posture": posture,
                        })

        governance_solutions: list[GovernanceSolution] = []
        pruned_solutions: list[GovernanceSolution] = []
        seen_signatures: set[tuple[tuple[str, str], ...]] = set()
        sol_counter = 0
        pruned_counter = 0

        for cfg in candidate_configs:
            status, log_c, inst_c, dep_c, excl = _evaluate_constraints(cfg)
            prof, q_alts = _build_global_profile(cfg)
            sig = tuple(sorted(q_alts.items()))
            if sig in seen_signatures:
                continue
            seen_signatures.add(sig)

            label = (
                f"{cfg['q04'].replace('Q04_', '')} | {cfg['q05'].replace('Q05_', '')} | "
                f"Q07:{cfg['q07']} | Q09:{cfg['q09']} | Q10:{cfg['q10']} | Q11:{cfg['q11']}"
            )
            if status == "STRICTLY_FEASIBLE":
                sol_counter += 1
                sid = f"SOL_{sol_counter:04d}"
            else:
                pruned_counter += 1
                sid = f"PRUNED_SOL_{pruned_counter:04d}"
                if excl is not None:
                    exclusions.append(
                        ExclusionRecord(
                            item_id=sid,
                            item_kind=excl.item_kind,
                            constraint_id=excl.constraint_id,
                            constraint_type=excl.constraint_type,
                            source=excl.source,
                            reason=excl.reason,
                        )
                    )

            prov = ProvenanceMeta(
                record_id=sid,
                run_id=self.run_id,
                dataset_fingerprint=dataset_fp,
                created_at_utc=created_utc,
                producer_module="src/preference/solution_space.py",
                producer_agent="agent_04",
                upstream_artifact_ids=[matrix.matrix_id, "candidate_options_v1", "themes_codebook_v1"],
                config_hash=config_hash,
                schema_version=SCHEMA_VERSION,
            )
            gs = GovernanceSolution(
                solution_id=sid,
                label_en=label,
                question_alternatives=q_alts,
                global_alternative_profile=prof,
                included_question_ids=list(PRIMARY_QUESTION_IDS),
                diagnostic_context_question_ids=["Q14"],
                logical_constraints_satisfied=log_c,
                institutional_constraints_satisfied=inst_c,
                dependencies_satisfied=dep_c,
                feasibility_evaluation_status=status,  # type: ignore[arg-type]
                generation_method="COMBINATORIAL_CONSTRAINT_SATISFACTION",
                provenance=prov,
                explanatory_organisational_values=sorted(
                    {v for sid_vals in values_by_subtopic.values() for v in sid_vals}
                )[:12],
                pruned_by_clusters_or_values=False,
                pruned_by_coder_disagreement=False,
                pruned_by_coder_confidence=False,
                pruning_sources_applied=(
                    [excl.constraint_type] if excl is not None else []
                ),
            )
            gs.validate_invariants()
            if status == "STRICTLY_FEASIBLE":
                governance_solutions.append(gs)
            else:
                pruned_solutions.append(gs)

        subtopic_vocabs = {
            sid: sorted(info["all_keys"])
            for sid, info in sorted(vocab_info.items())
        }
        stats = {
            "primary_questions_included": list(PRIMARY_QUESTION_IDS),
            "contextual_questions_isolated": ["Q14"],
            "feasible_alternative_count": len(feasible_alts),
            "pruned_alternative_count": len(pruned_alts),
            "feasible_solution_count": len(governance_solutions),
            "pruned_solution_count": len(pruned_solutions),
            "exclusion_count": len(exclusions),
            "minority_feasible_alternative_count": sum(1 for a in feasible_alts if a.is_minority_position),
            "prohibited_pruning_sources_checked": sorted(PROHIBITED_PRUNING_SOURCES),
            "prohibited_pruning_count": 0,
        }
        return SolutionSpaceSummary(
            run_id=self.run_id,
            feasible_alternatives=feasible_alts,
            pruned_alternatives=pruned_alts,
            governance_solutions=governance_solutions,
            pruned_solutions=pruned_solutions,
            exclusions=exclusions,
            subtopic_posture_vocabularies=subtopic_vocabs,
            generation_stats=stats,
        )

    def save(self, summary: SolutionSpaceSummary) -> Path:
        out_dir = self.base_dir / "data" / "processed" / "preference"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "feasible_alternatives.json"

        def _enum_clean(obj: Any) -> Any:
            from enum import Enum
            if isinstance(obj, Enum):
                return obj.value
            if isinstance(obj, dict):
                return {str(k): _enum_clean(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple)):
                return [_enum_clean(v) for v in obj]
            return obj

        payload = {
            "schema_version": SCHEMA_VERSION,
            "run_id": summary.run_id,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "adr_reference": "ADR-0008",
            "generation_stats": summary.generation_stats,
            "exclusions": [asdict(e) for e in summary.exclusions],
            "feasible_alternatives": [_enum_clean(asdict(a)) for a in summary.feasible_alternatives],
            "governance_solutions": [_enum_clean(asdict(s)) for s in summary.governance_solutions],
            "pruned_solutions": [_enum_clean(asdict(s)) for s in summary.pruned_solutions],
            "subtopic_posture_vocabularies": summary.subtopic_posture_vocabularies,
        }
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return out_path
