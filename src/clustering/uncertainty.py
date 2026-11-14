"""ADR-0008 Uncertainty Propagation & Sensitivity Analysis for Clustering.

Owned by: Agent 05 — Clustering & Preference Heterogeneity
Schema Version: 1.0.0 (Aligned with ADR-0005 and ADR-0008)

Propagates all four ADR-0008 epistemic uncertainty classes (dual-coder distribution
sets, interpretation divergence, crosswalk partial/unaligned disjoint spaces,
and single-coder partial identification) into pairwise distances, cluster
stability diagnostics, and consensus co-association probabilities without
collapsing uncertainty sets or weighting by coder_confidence.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

import numpy as np
from sklearn.metrics import adjusted_rand_score

from src.clustering.distances import (
    DistanceMetricName,
    compute_masked_subtopic_distance_matrix,
    compute_question_aggregated_distance_matrix,
    compute_utility_distance_matrices,
    get_distribution_distance_fn,
    hash_distance_matrix,
)
from src.clustering.features import RepresentationBundle, VerifiedCanonicalInputs
from src.clustering.methods import (
    compute_leave_one_out_stability,
    compute_partition_geometry,
    compute_permutation_null_silhouette,
    consensus_clustering_from_coassociation,
    hierarchical_clustering,
    pam_clustering,
)


def _sample_cell_distribution(
    cell: dict[str, Any],
    cw_axis_choice: str,
    rng: np.random.Generator,
    omission_inclusion_prob: float,
    double_count_downweight: float,
) -> tuple[dict[str, float] | None, float]:
    """Sample one ADR-0008 scenario realization (dist, weight) for a primary usable cell."""
    uc = cell["uncertainty_class"]
    pus = cell.get("preference_uncertainty_set") or {}
    cw = cell.get("canonical_alternative_crosswalk") or {}
    cw_status = cw.get("crosswalk_status")
    interps = list(pus.get("interpretation_variants") or [])

    if uc == "SINGLE_CODER_PARTIAL_ID_OMISSION" and rng.random() > omission_inclusion_prob:
        return None, 0.0

    w = 1.0
    if uc == "SINGLE_CODER_PARTIAL_ID_GRANULARITY" and pus.get("double_count_guard_applied", False):
        w = double_count_downweight if rng.random() < 0.7 else 1.0

    if cw_status == "NO_VALID_CROSSWALK":
        disjoint = pus.get("disjoint_coder_hypotheses") or {}
        d_side = disjoint.get(cw_axis_choice)
        if not d_side:
            return None, 0.0
        dist = {f"{cw_axis_choice}:{k}": float(v) for k, v in d_side.items()}
    else:
        scens = pus.get("discrete_scenarios") or []
        if not scens:
            return None, 0.0
        chosen_scen = scens[int(rng.integers(0, len(scens)))]
        dist = {str(k): float(v) for k, v in chosen_scen.items()}

    if interps:
        chosen_interp = interps[int(rng.integers(0, len(interps)))]
        if chosen_interp == "epistemic_uncertainty_over_preference" and len(dist) > 1:
            keys = sorted(dist.keys())
            probs = np.array([max(0.0, dist[k]) for k in keys], dtype=np.float64)
            s = float(probs.sum())
            if s > 0.0:
                probs /= s
                picked = keys[int(rng.choice(len(keys), p=probs))]
                dist = {picked: 1.0}

    return dist, w


def generate_adr0008_distance_ensemble(
    inputs: VerifiedCanonicalInputs,
    metric: DistanceMetricName = "MASKED_JENSEN_SHANNON",
    n_draws: int = 200,
    seed: int = 42,
    omission_inclusion_prob: float = 0.7,
    double_count_downweight: float = 0.5,
) -> dict[str, Any]:
    """Generate B ADR-0008 uncertainty-propagated distance matrices (Representation B)."""
    rng = np.random.default_rng(seed)
    pids = inputs.participant_ids
    n = len(pids)
    dist_fn = get_distribution_distance_fn(metric)

    by_p_sub: dict[str, dict[str, dict[str, Any]]] = {p: {} for p in pids}
    for c in inputs.primary_usable_cells:
        by_p_sub[c["participant_id"]][c["canonical_subtopic_id"]] = c

    D_draws: list[np.ndarray] = []
    shared_min_across_draws: list[int] = []

    for _ in range(n_draws):
        cw_axis_choice = "coder_a" if rng.random() < 0.5 else "coder_b"
        sampled: dict[str, dict[str, tuple[dict[str, float], float]]] = {p: {} for p in pids}
        for p in pids:
            for sid, c in by_p_sub[p].items():
                dist, w = _sample_cell_distribution(
                    c, cw_axis_choice, rng, omission_inclusion_prob, double_count_downweight
                )
                if dist is not None and w > 0.0:
                    sampled[p][sid] = (dist, w)

        D_b = np.zeros((n, n), dtype=np.float64)
        min_sh = 999
        for i in range(n):
            pi = pids[i]
            for j in range(i + 1, n):
                pj = pids[j]
                shared = sorted(set(sampled[pi]) & set(sampled[pj]))
                min_sh = min(min_sh, len(shared))
                if not shared:
                    val = 1.0
                else:
                    num = 0.0
                    den = 0.0
                    for sid in shared:
                        d1, w1 = sampled[pi][sid]
                        d2, w2 = sampled[pj][sid]
                        wij = math.sqrt(w1 * w2)
                        num += wij * dist_fn(d1, d2)
                        den += wij
                    val = num / den if den > 0.0 else 1.0
                D_b[i, j] = val
                D_b[j, i] = val
        np.fill_diagonal(D_b, 0.0)
        D_draws.append(D_b)
        shared_min_across_draws.append(0 if min_sh == 999 else min_sh)

    stack = np.stack(D_draws, axis=0)
    D_mean = np.mean(stack, axis=0)
    D_mean = 0.5 * (D_mean + D_mean.T)
    np.fill_diagonal(D_mean, 0.0)
    D_std = np.std(stack, axis=0)
    upper_std = D_std[np.triu_indices(n, 1)]
    upper_mean = D_mean[np.triu_indices(n, 1)]

    return {
        "distance_draws": D_draws,
        "mean_distance_matrix": D_mean,
        "std_distance_matrix": D_std,
        "mean_pairwise_distance": round(float(upper_mean.mean()), 6),
        "median_pairwise_distance": round(float(np.median(upper_mean)), 6),
        "mean_pair_uncertainty_std": round(float(upper_std.mean()), 6),
        "max_pair_uncertainty_std": round(float(upper_std.max()), 6),
        "min_shared_observed_in_draws": int(min(shared_min_across_draws)),
        "matrix_hash": hash_distance_matrix(D_mean, pids),
    }


def evaluate_k_grid_with_stability(
    participant_ids: list[str],
    D_primary: np.ndarray,
    D_scenario_draws: list[np.ndarray],
    subtopic_scenarios: dict[str, dict[str, list[dict[str, float]]]],
    candidate_k_values: list[int],
    metric: DistanceMetricName = "MASKED_JENSEN_SHANNON",
    bootstrap_draws: int = 200,
    permutation_draws: int = 200,
    seed: int = 42,
) -> dict[str, Any]:
    """Evaluate PAM, Hierarchical (avg/complete), and Consensus across candidate K values."""
    rng = np.random.default_rng(seed)
    n = len(participant_ids)
    all_subs = sorted({sid for m in subtopic_scenarios.values() for sid in m})
    dist_fn = get_distribution_distance_fn(metric)

    # Pre-sample subtopic bootstrap distance matrices so all K share the exact same bootstrap ensemble
    D_boot_draws: list[np.ndarray] = []
    for _ in range(bootstrap_draws):
        boot_subs = rng.choice(all_subs, size=len(all_subs), replace=True).tolist()
        D_b = np.zeros((n, n), dtype=np.float64)
        for i in range(n):
            pi = participant_ids[i]
            mi = subtopic_scenarios.get(pi, {})
            for j in range(i + 1, n):
                pj = participant_ids[j]
                mj = subtopic_scenarios.get(pj, {})
                vals: list[float] = []
                for sid in boot_subs:
                    si = mi.get(sid)
                    sj = mj.get(sid)
                    if si and sj:
                        tot = sum(dist_fn(a, b) for a in si for b in sj) / (len(si) * len(sj))
                        vals.append(tot)
                val = float(np.mean(vals)) if vals else 1.0
                D_b[i, j] = val
                D_b[j, i] = val
        np.fill_diagonal(D_b, 0.0)
        D_boot_draws.append(D_b)

    pam_fit = lambda D, k: pam_clustering(D, k)[0]
    havg_fit = lambda D, k: hierarchical_clustering(D, k, "average")
    hcomp_fit = lambda D, k: hierarchical_clustering(D, k, "complete")

    by_k_pam: dict[int, dict[str, Any]] = {}
    by_k_havg: dict[int, dict[str, Any]] = {}
    by_k_hcomp: dict[int, dict[str, Any]] = {}
    by_k_consensus: dict[int, dict[str, Any]] = {}
    coassoc_by_k: dict[int, np.ndarray] = {}

    for k in candidate_k_values:
        if k < 1 or k >= n:
            continue

        if k == 1:
            zeros = np.zeros(n, dtype=np.int64)
            geom = compute_partition_geometry(D_primary, zeros)
            base_entry = {
                **geom,
                "scenario_ari_mean": 1.0,
                "scenario_ari_std": 0.0,
                "bootstrap_ari_mean": 1.0,
                "bootstrap_ari_std": 0.0,
                "loo_ari_mean": 1.0,
                "loo_ari_min": 1.0,
                "permutation_p_value": 1.0,
                "null_silhouette_mean": 0.0,
                "assignments": {p: 0 for p in participant_ids},
                "member_stability_confidence": {p: 1.0 for p in participant_ids},
            }
            by_k_pam[k] = dict(base_entry)
            by_k_havg[k] = dict(base_entry)
            by_k_hcomp[k] = dict(base_entry)
            by_k_consensus[k] = dict(base_entry)
            coassoc_by_k[k] = np.ones((n, n), dtype=np.float64)
            continue

        # 1. Fit each method on D_primary
        lbl_pam, medoids_pam, pam_cost = pam_clustering(D_primary, k)
        lbl_havg = havg_fit(D_primary, k)
        lbl_hcomp = hcomp_fit(D_primary, k)

        # 2. Propagate across ADR-0008 scenario draws + compute co-association
        coassoc_pam = np.zeros((n, n), dtype=np.float64)
        aris_scen_pam: list[float] = []
        aris_scen_havg: list[float] = []
        aris_scen_hcomp: list[float] = []

        for D_sc in D_scenario_draws:
            lp = pam_fit(D_sc, k)
            lh = havg_fit(D_sc, k)
            lc = hcomp_fit(D_sc, k)
            aris_scen_pam.append(float(adjusted_rand_score(lbl_pam, lp)))
            aris_scen_havg.append(float(adjusted_rand_score(lbl_havg, lh)))
            aris_scen_hcomp.append(float(adjusted_rand_score(lbl_hcomp, lc)))
            coassoc_pam += (lp[:, None] == lp[None, :]).astype(np.float64) / len(D_scenario_draws)

        coassoc_by_k[k] = coassoc_pam
        lbl_cons, _ = consensus_clustering_from_coassociation(coassoc_pam, k, method="average")

        # 3. Bootstrap stability across subtopic resamples
        aris_boot_pam: list[float] = []
        aris_boot_havg: list[float] = []
        aris_boot_hcomp: list[float] = []
        for D_bt in D_boot_draws:
            aris_boot_pam.append(float(adjusted_rand_score(lbl_pam, pam_fit(D_bt, k))))
            aris_boot_havg.append(float(adjusted_rand_score(lbl_havg, havg_fit(D_bt, k))))
            aris_boot_hcomp.append(float(adjusted_rand_score(lbl_hcomp, hcomp_fit(D_bt, k))))

        # 4. Member stability confidence from co-association matrix within assigned cluster
        def _member_conf(labels: np.ndarray) -> dict[str, float]:
            confs: dict[str, float] = {}
            for idx, p in enumerate(participant_ids):
                peers = [j for j in range(n) if labels[j] == labels[idx] and j != idx]
                confs[p] = round(float(np.mean([coassoc_pam[idx, j] for j in peers])) if peers else 1.0, 6)
            return confs

        # 5. Assemble method diagnostics
        for target_dict, lbl, fit_fn, scen_aris, boot_aris, extra in [
            (
                by_k_pam,
                lbl_pam,
                pam_fit,
                aris_scen_pam,
                aris_boot_pam,
                {"medoids": [participant_ids[m] for m in medoids_pam], "pam_medoid_cost": round(pam_cost, 6)},
            ),
            (by_k_havg, lbl_havg, havg_fit, aris_scen_havg, aris_boot_havg, {}),
            (by_k_hcomp, lbl_hcomp, hcomp_fit, aris_scen_hcomp, aris_boot_hcomp, {}),
        ]:
            geom = compute_partition_geometry(D_primary, lbl)
            loo = compute_leave_one_out_stability(D_primary, k, fit_fn)
            perm = compute_permutation_null_silhouette(D_primary, k, fit_fn, n_perm=permutation_draws, seed=seed + k)
            target_dict[k] = {
                **geom,
                **loo,
                **perm,
                **extra,
                "scenario_ari_mean": round(float(np.mean(scen_aris)), 6),
                "scenario_ari_std": round(float(np.std(scen_aris)), 6),
                "bootstrap_ari_mean": round(float(np.mean(boot_aris)), 6),
                "bootstrap_ari_std": round(float(np.std(boot_aris)), 6),
                "assignments": {participant_ids[i]: int(lbl[i]) for i in range(n)},
                "member_stability_confidence": _member_conf(lbl),
            }

        # Consensus diagnostics evaluated against D_primary
        geom_c = compute_partition_geometry(D_primary, lbl_cons)
        aris_scen_cons = [float(adjusted_rand_score(lbl_cons, pam_fit(D_sc, k))) for D_sc in D_scenario_draws]
        aris_boot_cons = [float(adjusted_rand_score(lbl_cons, pam_fit(D_bt, k))) for D_bt in D_boot_draws]
        by_k_consensus[k] = {
            **geom_c,
            "scenario_ari_mean": round(float(np.mean(aris_scen_cons)), 6),
            "scenario_ari_std": round(float(np.std(aris_scen_cons)), 6),
            "bootstrap_ari_mean": round(float(np.mean(aris_boot_cons)), 6),
            "bootstrap_ari_std": round(float(np.std(aris_boot_cons)), 6),
            "loo_ari_mean": by_k_havg[k]["loo_ari_mean"],
            "permutation_p_value": by_k_havg[k]["permutation_p_value"],
            "assignments": {participant_ids[i]: int(lbl_cons[i]) for i in range(n)},
            "member_stability_confidence": _member_conf(lbl_cons),
        }

    return {
        "pam": by_k_pam,
        "hierarchical_average": by_k_havg,
        "hierarchical_complete": by_k_hcomp,
        "uncertainty_consensus": by_k_consensus,
        "coassociation_matrices": {
            str(k): [[round(float(x), 4) for x in row] for row in mat.tolist()]
            for k, mat in coassoc_by_k.items()
        },
    }


def run_multi_representation_sensitivity(
    inputs: VerifiedCanonicalInputs,
    reps: RepresentationBundle,
    candidate_k_values: list[int],
    min_shared_subtopics: int = 3,
    n_draws: int = 200,
    seed: int = 42,
) -> dict[str, Any]:
    """Compare all 4 representations (A, B, C, D), 3 masked metrics, and partial-ID regimes."""
    pids = inputs.participant_ids
    n = len(pids)
    rng = np.random.default_rng(seed)

    # 1. Rep A across all 3 canonical metrics
    rep_a_metrics: dict[str, Any] = {}
    for metric_name in ("MASKED_JENSEN_SHANNON", "MASKED_COSINE", "MASKED_WEIGHTED_L1"):
        res_a = compute_masked_subtopic_distance_matrix(
            pids, reps.rep_a_subtopic_scenarios, metric=metric_name, min_shared_subtopics=min_shared_subtopics
        )
        D_a = res_a["distance_matrix"]
        k_table = {}
        for k in candidate_k_values:
            if k <= 1 or k >= n:
                continue
            lp, _, _ = pam_clustering(D_a, k)
            lh = hierarchical_clustering(D_a, k, "average")
            lc = hierarchical_clustering(D_a, k, "complete")
            k_table[str(k)] = {
                "pam": compute_partition_geometry(D_a, lp),
                "hierarchical_average": compute_partition_geometry(D_a, lh),
                "hierarchical_complete": compute_partition_geometry(D_a, lc),
                "pam_assignments": {pids[i]: int(lp[i]) for i in range(n)},
                "hierarchical_average_assignments": {pids[i]: int(lh[i]) for i in range(n)},
            }
        rep_a_metrics[metric_name] = {
            "matrix_hash": res_a["matrix_hash"],
            "min_shared_observed": res_a["min_shared_observed"],
            "median_shared_observed": res_a["median_shared_observed"],
            "max_shared_observed": res_a["max_shared_observed"],
            "by_k": k_table,
        }

    # 2. Rep D Question-level aggregated profiles
    rep_d_res = compute_question_aggregated_distance_matrix(
        pids, reps.rep_d_question_scenarios, metric="MASKED_JENSEN_SHANNON"
    )
    D_d = rep_d_res["distance_matrix"]
    rep_d_by_k = {}
    for k in candidate_k_values:
        if k <= 1 or k >= n:
            continue
        lp, _, _ = pam_clustering(D_d, k)
        lh = hierarchical_clustering(D_d, k, "average")
        rep_d_by_k[str(k)] = {
            "pam": compute_partition_geometry(D_d, lp),
            "hierarchical_average": compute_partition_geometry(D_d, lh),
            "pam_assignments": {pids[i]: int(lp[i]) for i in range(n)},
        }

    # 3. Rep C Utility profiles (centered cosine, Spearman, RMS-L2) + CI-interval scenario draws
    util_mats = compute_utility_distance_matrices(reps.rep_c_utility_mid)
    D_c_corr = util_mats["utility_centered_cosine"]
    D_c_draws: list[np.ndarray] = []
    for _ in range(n_draws):
        alphas = rng.uniform(0.0, 1.0, size=(n, 1))
        noise = rng.normal(0.0, 1.0, size=reps.rep_c_utility_mid.shape) * reps.rep_c_utility_se * 0.25
        u_b = np.clip(
            reps.rep_c_utility_lo + alphas * (reps.rep_c_utility_hi - reps.rep_c_utility_lo) + noise,
            reps.rep_c_utility_lo,
            reps.rep_c_utility_hi,
        )
        D_c_draws.append(compute_utility_distance_matrices(u_b)["utility_centered_cosine"])

    rep_c_summary: dict[str, Any] = {}
    for dname, D_mat in util_mats.items():
        by_k_u = {}
        for k in candidate_k_values:
            if k <= 1 or k >= n:
                continue
            lp, _, _ = pam_clustering(D_mat, k)
            lh = hierarchical_clustering(D_mat, k, "average")
            geom_p = compute_partition_geometry(D_mat, lp)
            geom_h = compute_partition_geometry(D_mat, lh)
            entry = {
                "pam": geom_p,
                "hierarchical_average": geom_h,
                "pam_assignments": {pids[i]: int(lp[i]) for i in range(n)},
                "hierarchical_average_assignments": {pids[i]: int(lh[i]) for i in range(n)},
            }
            if dname == "utility_centered_cosine":
                scen_aris_p = [float(adjusted_rand_score(lp, pam_clustering(d, k)[0])) for d in D_c_draws]
                loo_p = compute_leave_one_out_stability(D_mat, k, lambda dm, kk: pam_clustering(dm, kk)[0])
                perm_p = compute_permutation_null_silhouette(
                    D_mat, k, lambda dm, kk: pam_clustering(dm, kk)[0], n_perm=n_draws, seed=seed + k
                )
                entry["pam_ci_scenario_ari_mean"] = round(float(np.mean(scen_aris_p)), 6)
                entry["pam_loo_ari_mean"] = loo_p["loo_ari_mean"]
                entry["pam_permutation_p_value"] = perm_p["empirical_p_value"]
            by_k_u[str(k)] = entry
        rep_c_summary[dname] = {
            "matrix_hash": hash_distance_matrix(D_mat, pids),
            "by_k": by_k_u,
        }

    # 4. Single-coder & crosswalk subset regimes (checking ADR-0008 assumptions)
    def _build_regime_matrix(mode: str) -> tuple[np.ndarray, int, int]:
        sub_map: dict[str, dict[str, list[dict[str, float]]]] = {p: {} for p in pids}
        weights: dict[str, dict[str, float]] | None = {p: {} for p in pids} if mode == "double_count_guard_0_5" else None
        cells_kept = 0
        for c in inputs.primary_usable_cells:
            uc = c["uncertainty_class"]
            pus = c.get("preference_uncertainty_set") or {}
            cw = c.get("canonical_alternative_crosswalk") or {}
            cw_status = cw.get("crosswalk_status")
            p = c["participant_id"]
            sid = c["canonical_subtopic_id"]

            if mode == "exclude_single_coder_omission" and uc == "SINGLE_CODER_PARTIAL_ID_OMISSION":
                continue
            if mode == "exclude_single_coder_granularity" and uc == "SINGLE_CODER_PARTIAL_ID_GRANULARITY":
                continue
            if mode in ("coder_a_regime_incl_disjoint", "coder_b_regime_incl_disjoint"):
                side = "coder_a" if mode.startswith("coder_a") else "coder_b"
                if cw_status == "NO_VALID_CROSSWALK":
                    d_side = (pus.get("disjoint_coder_hypotheses") or {}).get(side)
                    if not d_side:
                        continue
                    sub_map[p][sid] = [{f"{side}:{kk}": float(vv) for kk, vv in d_side.items()}]
                    cells_kept += 1
                else:
                    sc = pus.get("discrete_scenarios") or []
                    if not sc:
                        continue
                    idx_side = 0 if (side == "coder_a" or len(sc) == 1) else 1
                    sub_map[p][sid] = [{str(kk): float(vv) for kk, vv in sc[idx_side].items()}]
                    cells_kept += 1
            else:
                sc = pus.get("discrete_scenarios") or []
                if not sc:
                    continue
                sub_map[p][sid] = [{str(kk): float(vv) for kk, vv in s.items()} for s in sc]
                cells_kept += 1
                if weights is not None:
                    w = 0.5 if (uc == "SINGLE_CODER_PARTIAL_ID_GRANULARITY" and pus.get("double_count_guard_applied")) else 1.0
                    weights[p][sid] = w

        res_m = compute_masked_subtopic_distance_matrix(
            pids, sub_map, metric="MASKED_JENSEN_SHANNON", min_shared_subtopics=min_shared_subtopics, subtopic_weights=weights
        )
        return res_m["distance_matrix"], cells_kept, int(res_m["min_shared_observed"])

    regime_names = [
        "baseline_comparable_238",
        "exclude_single_coder_omission",
        "exclude_single_coder_granularity",
        "double_count_guard_0_5",
        "coder_a_regime_incl_disjoint",
        "coder_b_regime_incl_disjoint",
    ]
    regime_results: dict[str, Any] = {}
    regime_pam_k2: dict[str, np.ndarray] = {}
    for rname in regime_names:
        D_r, cnt_r, min_sh_r = _build_regime_matrix(rname)
        by_kr = {}
        for k in candidate_k_values:
            if k <= 1 or k >= n:
                continue
            lp, _, _ = pam_clustering(D_r, k)
            lh = hierarchical_clustering(D_r, k, "average")
            if k == 2:
                regime_pam_k2[rname] = lp
            by_kr[str(k)] = {
                "pam": compute_partition_geometry(D_r, lp),
                "hierarchical_average": compute_partition_geometry(D_r, lh),
                "pam_assignments": {pids[i]: int(lp[i]) for i in range(n)},
            }
        regime_results[rname] = {
            "cells_used": cnt_r,
            "min_shared_subtopics_observed": min_sh_r,
            "by_k": by_kr,
        }

    # Cross-regime ARI table at K=2
    cross_regime_ari_k2: dict[str, dict[str, float]] = {}
    for r1, l1 in regime_pam_k2.items():
        cross_regime_ari_k2[r1] = {
            r2: round(float(adjusted_rand_score(l1, l2)), 6) for r2, l2 in regime_pam_k2.items()
        }

    return {
        "representation_a_metrics": rep_a_metrics,
        "representation_d_question_aggregated": {
            "matrix_hash": rep_d_res["matrix_hash"],
            "min_shared_questions": rep_d_res["min_shared_questions"],
            "median_shared_questions": rep_d_res["median_shared_questions"],
            "max_shared_questions": rep_d_res["max_shared_questions"],
            "by_k": rep_d_by_k,
        },
        "representation_c_utility_profiles": rep_c_summary,
        "partial_id_and_coder_regimes": regime_results,
        "cross_regime_pam_k2_ari": cross_regime_ari_k2,
    }
