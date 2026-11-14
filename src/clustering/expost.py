"""Ex-Post Cluster Interpretation, Organisational Values & Pareto Relationship Analysis.

Owned by: Agent 05 — Clustering & Preference Heterogeneity
Schema Version: 1.0.0 (Aligned with ADR-0005 and ADR-0008)

Strictly DESCRIPTIVE and EX-POST:
- Describes preference patterns solely from observed Q01-Q13 coded evidence
  (no psychological, personality, attitude, competence, or political inference;
  no ranking or evaluation of participants).
- Compares organisational values (reconciled_values_v1) purely ex post.
- Evaluates alignment with the 10 ROBUSTLY_NONDOMINATED core solutions and the
  broader 102 high-confidence Pareto frontier (p >= 0.95) strictly as explanatory
  analysis without altering feasible alternatives, Pareto sets, or voting weights.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

import numpy as np
from scipy.stats import spearmanr

from src.clustering.features import (
    PRIMARY_QUESTION_IDS,
    RepresentationBundle,
    VerifiedCanonicalInputs,
)

CORE_CLEAVAGE_SUBTOPICS: tuple[str, ...] = (
    "Q01_pole_relevance",
    "Q03_terminology_clarity",
    "Q04_ad_hoc_operation",
    "Q05_coordination_mechanism",
    "Q06_collaboration_framework",
    "Q06_coordination_mechanisms",
    "Q07_engagement_level",
    "Q08_hr_management_level",
    "Q09_financial_responsibility_regime",
    "Q10_allocation_mechanism_core_funding",
    "Q11_overhead_allocation_mechanism",
    "Q12_allocation_primes_depot",
    "Q13_evaluation_incentives",
)


def _summarize_group_subtopics(
    participant_ids: list[str],
    inputs: VerifiedCanonicalInputs,
) -> dict[str, Any]:
    """Summarize observed Q01-Q13 preference distributions for a set of participants."""
    member_set = set(participant_ids)
    sub_obs: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for c in inputs.primary_usable_cells:
        if c["participant_id"] in member_set:
            sub_obs[c["canonical_subtopic_id"]].append(c)

    subtopic_summaries: dict[str, Any] = {}
    for sid in sorted(sub_obs):
        cs = sub_obs[sid]
        alt_mass: Counter[str] = Counter()
        n_scen_cells = 0
        disjoint_cnt = 0
        for c in cs:
            pus = c.get("preference_uncertainty_set") or {}
            scens = pus.get("discrete_scenarios") or []
            if scens:
                n_scen_cells += 1
                w = 1.0 / len(scens)
                for sc in scens:
                    for k, v in sc.items():
                        alt_mass[str(k)] += w * float(v)
            else:
                disjoint_cnt += 1
        mean_dist = (
            {k: round(float(v / n_scen_cells), 4) for k, v in sorted(alt_mass.items(), key=lambda x: -x[1])}
            if n_scen_cells > 0
            else {}
        )
        subtopic_summaries[sid] = {
            "observed_participants": sorted({c["participant_id"] for c in cs}),
            "observed_count": len(cs),
            "comparable_cell_count": n_scen_cells,
            "disjoint_crosswalk_cell_count": disjoint_cnt,
            "scenario_averaged_distribution": mean_dist,
            "modal_alternative": max(mean_dist, key=lambda k: mean_dist[k]) if mean_dist else None,
        }

    # Missing primary cells audit
    missing_primary = [
        f"{c['participant_id']}:{c['question_id']}"
        for c in inputs.missing_cells
        if c["participant_id"] in member_set and c["question_id"] in PRIMARY_QUESTION_IDS
    ]

    return {
        "member_participant_ids": sorted(participant_ids),
        "member_count": len(participant_ids),
        "missing_primary_cell_count": len(missing_primary),
        "subtopic_profiles": subtopic_summaries,
    }


def _find_distinguishing_subtopics(
    group_assignments: dict[str, list[str]],
    inputs: VerifiedCanonicalInputs,
    top_n: int = 5,
) -> dict[str, list[str]]:
    """Identify core subtopics with highest modal prevalence or inter-group JSD divergence."""
    groups = sorted(group_assignments.keys())
    if len(groups) <= 1:
        # For single cohort (K=1), return highest-coverage primary core subtopics sorted by coverage
        cov: list[tuple[int, str]] = []
        for sid in CORE_CLEAVAGE_SUBTOPICS:
            cnt = sum(
                1
                for c in inputs.primary_usable_cells
                if c["canonical_subtopic_id"] == sid
            )
            cov.append((cnt, sid))
        cov.sort(key=lambda x: (-x[0], x[1]))
        sole = groups[0] if groups else "PROFILE_01"
        return {sole: [sid for _, sid in cov[:top_n]]}

    # Inter-group JSD contrast per subtopic
    sub_divs: dict[str, list[tuple[float, str, str]]] = defaultdict(list)
    summaries = {g: _summarize_group_subtopics(pids, inputs)["subtopic_profiles"] for g, pids in group_assignments.items()}

    for sid in CORE_CLEAVAGE_SUBTOPICS:
        for g in groups:
            d_g = (summaries[g].get(sid) or {}).get("scenario_averaged_distribution") or {}
            if not d_g:
                continue
            other_dists = [
                (summaries[og].get(sid) or {}).get("scenario_averaged_distribution") or {}
                for og in groups
                if og != g
            ]
            other_dists = [od for od in other_dists if od]
            if not other_dists:
                continue
            # L1 distance from other groups' centroid
            l1_vals = []
            for od in other_dists:
                keys = set(d_g) | set(od)
                l1_vals.append(0.5 * sum(abs(d_g.get(k, 0.0) - od.get(k, 0.0)) for k in keys))
            modal_alt = (summaries[g].get(sid) or {}).get("modal_alternative") or ""
            sub_divs[g].append((float(np.mean(l1_vals)), sid, modal_alt))

    out: dict[str, list[str]] = {}
    for g in groups:
        ranked = sorted(sub_divs[g], key=lambda x: (-x[0], x[1]))
        out[g] = [sid for _, sid, _ in ranked[:top_n]]
    return out


def compare_clusters_with_values_expost(
    group_assignments: dict[str, list[str]],
    inputs: VerifiedCanonicalInputs,
    top_n: int = 6,
) -> dict[str, Any]:
    """Ex-post descriptive association between participant groups and reconciled organisational values."""
    rvs = inputs.reconciled_values_payload.get("reconciled_values") or []
    dual_values = [v for v in rvs if v.get("dual_coder_confirmed")]
    n_total = len(inputs.participant_ids)

    value_rows: list[dict[str, Any]] = []
    group_value_lift: dict[str, list[tuple[float, str, str]]] = defaultdict(list)

    for v in rvs:
        vid = str(v["reconciled_value_id"])
        label = str(v["canonical_value_label"])
        sup_set = set(v.get("supporting_participant_ids") or [])
        overall_rate = len(sup_set) / n_total if n_total > 0 else 0.0
        group_rates: dict[str, dict[str, Any]] = {}
        for g, gpids in sorted(group_assignments.items()):
            in_g = len(sup_set & set(gpids))
            rate = in_g / len(gpids) if gpids else 0.0
            group_rates[g] = {"count": in_g, "group_size": len(gpids), "proportion": round(rate, 4)}
            lift = rate - overall_rate
            group_value_lift[g].append((lift, vid, label))
        value_rows.append(
            {
                "reconciled_value_id": vid,
                "canonical_value_label": label,
                "dual_coder_confirmed": bool(v.get("dual_coder_confirmed")),
                "overall_participant_count": len(sup_set),
                "overall_proportion": round(overall_rate, 4),
                "supporting_question_ids": list(v.get("supporting_question_ids") or []),
                "by_group": group_rates,
            }
        )

    value_rows.sort(key=lambda r: (-int(r["dual_coder_confirmed"]), -r["overall_participant_count"], r["reconciled_value_id"]))
    distinguishing_values: dict[str, list[str]] = {}
    for g in sorted(group_assignments):
        if len(group_assignments) <= 1:
            distinguishing_values[g] = [
                f"{v['reconciled_value_id']} ({v['canonical_value_label']})"
                for v in sorted(dual_values, key=lambda x: (-len(x.get("supporting_participant_ids") or []), x["reconciled_value_id"]))[:top_n]
            ]
        else:
            ranked = sorted(group_value_lift[g], key=lambda x: (-x[0], x[1]))
            distinguishing_values[g] = [
                f"{vid} ({lbl}, diff={lift:+.2f})" for lift, vid, lbl in ranked[:top_n] if lift > 0.0
            ]

    return {
        "analysis_role": "EX_POST_DESCRIPTIVE_ONLY",
        "values_influenced_clustering_or_feasible_set": False,
        "total_reconciled_values": len(rvs),
        "dual_coder_confirmed_values_count": len(dual_values),
        "distinguishing_values_by_group": distinguishing_values,
        "top_values_cross_tabulation": value_rows[:25],
    }


def build_cluster_profiles(
    inputs: VerifiedCanonicalInputs,
    canonical_assignments: dict[str, str],
    selected_k_status: str,
    exploratory_partitions: dict[str, dict[str, list[str]]],
) -> dict[str, Any]:
    """Build descriptive cluster profiles strictly from observed Q01-Q13 coded evidence."""
    canon_groups: dict[str, list[str]] = defaultdict(list)
    for pid, label in sorted(canonical_assignments.items()):
        canon_groups[label].append(pid)

    canon_profiles = {
        gid: _summarize_group_subtopics(gpids, inputs)
        for gid, gpids in sorted(canon_groups.items())
    }
    canon_dist_subs = _find_distinguishing_subtopics(dict(canon_groups), inputs, top_n=6)
    canon_values = compare_clusters_with_values_expost(dict(canon_groups), inputs, top_n=6)

    exploratory_summaries: dict[str, Any] = {}
    for exp_name, exp_groups in exploratory_partitions.items():
        exp_profiles = {
            gid: _summarize_group_subtopics(gpids, inputs)
            for gid, gpids in sorted(exp_groups.items())
        }
        exp_dist_subs = _find_distinguishing_subtopics(exp_groups, inputs, top_n=6)
        exp_vals = compare_clusters_with_values_expost(exp_groups, inputs, top_n=5)
        exploratory_summaries[exp_name] = {
            "status": "EXPLORATORY_SENSITIVITY_ONLY_NON_CANONICAL",
            "group_sizes": {g: len(ps) for g, ps in sorted(exp_groups.items())},
            "distinguishing_subtopics": exp_dist_subs,
            "ex_post_values_comparison": exp_vals,
            "group_profiles": exp_profiles,
        }

    # Summarize cross-cutting core preference patterns observed across the cohort
    core_distribution_overview: dict[str, Any] = {}
    cohort_all = canon_profiles[next(iter(canon_profiles))]
    for sid in CORE_CLEAVAGE_SUBTOPICS:
        if sid in cohort_all["subtopic_profiles"]:
            core_distribution_overview[sid] = cohort_all["subtopic_profiles"][sid]

    return {
        "schema_version": "1.0.0",
        "run_id": inputs.run_id,
        "interpretation_policy": (
            "Descriptive observed Q01-Q13 preference patterns only. No psychological, personality, "
            "attitude, competence, or political traits inferred. No participant ranking."
        ),
        "selected_k_status": selected_k_status,
        "canonical_distinguishing_subtopics": canon_dist_subs,
        "canonical_ex_post_values": canon_values,
        "canonical_profiles": canon_profiles,
        "cohort_core_preference_overview": core_distribution_overview,
        "exploratory_partition_interpretations": exploratory_summaries,
        "q14_contextual_note": {
            "q14_excluded_from_clustering": True,
            "q14_cell_count": len(inputs.contextual_q14_cells),
            "q14_usable_count": sum(1 for c in inputs.contextual_q14_cells if c["missingness_state"] == "observed_usable"),
        },
    }


def analyze_cluster_pareto_associations(
    inputs: VerifiedCanonicalInputs,
    reps: RepresentationBundle,
    canonical_assignments: dict[str, str],
    exploratory_partitions: dict[str, dict[str, list[str]]],
    high_conf_threshold: float = 0.95,
) -> dict[str, Any]:
    """Ex-post descriptive analysis of cluster/participant preferences on the robust core & frontier."""
    pids = inputs.participant_ids
    p_idx = {p: i for i, p in enumerate(pids)}
    sol_ids = reps.rep_c_solution_ids
    s_idx = {s: k for k, s in enumerate(sol_ids)}

    rpr = inputs.robust_pareto_payload.get("robust_pareto_result") or {}
    pr = inputs.pareto_results_payload.get("pareto_result") or {}
    sols_by_id = {s["solution_id"]: s for s in (inputs.feasible_alternatives_payload.get("governance_solutions") or [])}

    robust_core_10 = list(rpr.get("robustly_nondominated_solution_ids") or [])
    fip_map = dict(rpr.get("frontier_inclusion_probabilities") or {})
    high_conf_ids = sorted([sid for sid, p in fip_map.items() if float(p) >= high_conf_threshold])
    base_nondom_ids = list(pr.get("nondominated_solution_ids") or [])

    U_mid = reps.rep_c_utility_mid
    U_lo = reps.rep_c_utility_lo
    U_hi = reps.rep_c_utility_hi

    def _summarize_solution_set(target_sids: list[str], groups: dict[str, list[str]]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for sid in target_sids:
            k = s_idx[sid]
            sol_obj = sols_by_id.get(sid, {})
            qa = sol_obj.get("question_alternatives") or {}
            per_p = {
                pids[i]: {
                    "ci_mid": round(float(U_mid[i, k]), 6),
                    "ci_lower_95": round(float(U_lo[i, k]), 6),
                    "ci_upper_95": round(float(U_hi[i, k]), 6),
                }
                for i in range(len(pids))
            }
            by_g: dict[str, Any] = {}
            for g, gpids in sorted(groups.items()):
                idxs = [p_idx[p] for p in gpids]
                vals_mid = [float(U_mid[i, k]) for i in idxs]
                vals_lo = [float(U_lo[i, k]) for i in idxs]
                vals_hi = [float(U_hi[i, k]) for i in idxs]
                by_g[g] = {
                    "group_size": len(idxs),
                    "mean_ci_mid": round(float(np.mean(vals_mid)), 6),
                    "min_ci_mid": round(float(np.min(vals_mid)), 6),
                    "max_ci_mid": round(float(np.max(vals_mid)), 6),
                    "mean_ci_lower_95": round(float(np.mean(vals_lo)), 6),
                    "mean_ci_upper_95": round(float(np.mean(vals_hi)), 6),
                }
            rows.append(
                {
                    "solution_id": sid,
                    "robustness_status": (rpr.get("solution_robustness_statuses") or {}).get(sid),
                    "frontier_inclusion_probability": round(float(fip_map.get(sid, 0.0)), 6),
                    "utilitarian_score": round(float((pr.get("utilitarian_scores") or {}).get(sid, 0.0)), 6),
                    "rawls_maximin_score": round(float((pr.get("rawls_maximin_scores") or {}).get(sid, 0.0)), 6),
                    "core_institutional_posture": {
                        q: qa.get(q)
                        for q in ("Q01", "Q04", "Q05", "Q07", "Q08", "Q09", "Q10", "Q11", "Q12", "Q13")
                    },
                    "by_group": by_g,
                    "by_participant": per_p,
                }
            )
        return rows

    canon_groups: dict[str, list[str]] = defaultdict(list)
    for pid, lbl in sorted(canonical_assignments.items()):
        canon_groups[lbl].append(pid)

    core_10_cohort = _summarize_solution_set(robust_core_10, dict(canon_groups))

    # Exploratory group comparisons on Robust Core 10 & High-Confidence 102 Frontier
    exploratory_pareto: dict[str, Any] = {}
    hc_indices = [s_idx[sid] for sid in high_conf_ids]
    core_indices = [s_idx[sid] for sid in robust_core_10]

    for exp_name, exp_groups in exploratory_partitions.items():
        core_rows = _summarize_solution_set(robust_core_10, exp_groups)
        group_means_hc: dict[str, np.ndarray] = {}
        top_hc_by_group: dict[str, list[dict[str, Any]]] = {}
        top_core_by_group: dict[str, list[dict[str, Any]]] = {}

        for g, gpids in sorted(exp_groups.items()):
            idxs = [p_idx[p] for p in gpids]
            mean_vec_hc = U_mid[np.ix_(idxs, hc_indices)].mean(axis=0)
            group_means_hc[g] = mean_vec_hc
            ranked_hc = sorted(
                [(float(mean_vec_hc[pos]), high_conf_ids[pos]) for pos in range(len(high_conf_ids))],
                key=lambda x: (-x[0], x[1]),
            )
            top_hc_by_group[g] = [
                {
                    "solution_id": sid,
                    "group_mean_ci_mid": round(val, 6),
                    "in_robust_core_10": sid in set(robust_core_10),
                    "frontier_inclusion_probability": round(float(fip_map.get(sid, 0.0)), 6),
                    "key_postures": {
                        q: (sols_by_id[sid].get("question_alternatives") or {}).get(q)
                        for q in ("Q04", "Q05", "Q08", "Q09", "Q10", "Q11", "Q12")
                    },
                }
                for val, sid in ranked_hc[:10]
            ]

            mean_vec_core = U_mid[np.ix_(idxs, core_indices)].mean(axis=0)
            ranked_core = sorted(
                [(float(mean_vec_core[pos]), robust_core_10[pos]) for pos in range(len(robust_core_10))],
                key=lambda x: (-x[0], x[1]),
            )
            top_core_by_group[g] = [
                {"solution_id": sid, "group_mean_ci_mid": round(val, 6)} for val, sid in ranked_core
            ]

        # Inter-group rank correlation over high-confidence 102 frontier and robust core 10
        g_names = sorted(group_means_hc.keys())
        inter_group_hc_spearman: dict[str, dict[str, float]] = {}
        for g1 in g_names:
            inter_group_hc_spearman[g1] = {}
            for g2 in g_names:
                rho_raw = float(spearmanr(group_means_hc[g1], group_means_hc[g2]).statistic)
                rho = 0.0 if np.isnan(rho_raw) else rho_raw
                inter_group_hc_spearman[g1][g2] = round(rho, 6)

        # Spread across groups on Robust Core 10
        max_divergence_core = []
        for row in core_rows:
            gvals = [row["by_group"][g]["mean_ci_mid"] for g in g_names]
            spread = max(gvals) - min(gvals) if gvals else 0.0
            max_divergence_core.append(
                {
                    "solution_id": row["solution_id"],
                    "between_group_ci_mid_spread": round(spread, 6),
                    "group_means": {g: row["by_group"][g]["mean_ci_mid"] for g in g_names},
                }
            )
        max_divergence_core.sort(key=lambda x: (-x["between_group_ci_mid_spread"], x["solution_id"]))

        exploratory_pareto[exp_name] = {
            "status": "EXPLORATORY_EX_POST_DESCRIPTIVE_ONLY",
            "group_sizes": {g: len(ps) for g, ps in sorted(exp_groups.items())},
            "top_robust_core_10_by_group": top_core_by_group,
            "robust_core_10_between_group_spread": max_divergence_core,
            "top_10_of_high_confidence_frontier_by_group": top_hc_by_group,
            "inter_group_spearman_on_high_confidence_102": inter_group_hc_spearman,
        }

    # Participant-level top-3 among Robust Core 10
    participant_top_core = {}
    for p in pids:
        i = p_idx[p]
        ranked_p = sorted(
            [(float(U_mid[i, s_idx[sid]]), sid) for sid in robust_core_10],
            key=lambda x: (-x[0], x[1]),
        )
        participant_top_core[p] = [
            {"solution_id": sid, "ci_mid": round(val, 6)} for val, sid in ranked_p[:3]
        ]

    return {
        "schema_version": "1.0.0",
        "run_id": inputs.run_id,
        "analysis_role": "EX_POST_DESCRIPTIVE_ONLY",
        "non_interference_verified": {
            "feasible_solutions_count": len(sol_ids),
            "baseline_nondominated_count": len(base_nondom_ids),
            "robust_core_count": len(robust_core_10),
            "high_confidence_frontier_count": len(high_conf_ids),
            "clusters_modified_feasible_set": False,
            "clusters_modified_pareto_membership": False,
            "clusters_modified_voting_weights_or_rights": False,
        },
        "robust_core_10_ids": robust_core_10,
        "high_confidence_frontier_102_count": len(high_conf_ids),
        "high_confidence_frontier_threshold": high_conf_threshold,
        "robust_core_10_cohort_summary": core_10_cohort,
        "participant_top3_within_robust_core_10": participant_top_core,
        "exploratory_group_pareto_associations": exploratory_pareto,
    }
