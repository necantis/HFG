"""Interpretable Small-N Clustering Methods & Empirical K Diagnostics.

Owned by: Agent 05 — Clustering & Preference Heterogeneity
Schema Version: 1.0.0 (Aligned with ADR-0005 and ADR-0008)

Implements interpretable clustering methods suited to small-sample (n=11)
precomputed distance matrices:
1. K-Medoids / PAM (Partitioning Around Medoids: deterministic BUILD + SWAP);
2. Hierarchical Agglomerative Clustering (average & complete linkage);
3. Uncertainty-Aware Consensus Clustering over scenario co-association matrices.

Provides empirical K-selection diagnostics (silhouette, intra-cluster dispersion,
average inter-cluster separation, leave-one-out stability, bootstrap/scenario
ARI, and random-graph null silhouette) without assuming a fixed cluster count.
"""

from __future__ import annotations

from typing import Any, Callable, Sequence

import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform
from sklearn.metrics import adjusted_rand_score, silhouette_samples, silhouette_score


def canonicalize_labels(labels: np.ndarray) -> np.ndarray:
    """Relabel cluster IDs deterministically 0..K-1 in order of first appearance."""
    mapping: dict[int, int] = {}
    out = np.empty_like(labels, dtype=np.int64)
    for idx, val in enumerate(labels.tolist()):
        ival = int(val)
        if ival not in mapping:
            mapping[ival] = len(mapping)
        out[idx] = mapping[ival]
    return out


def pam_clustering(D: np.ndarray, k: int) -> tuple[np.ndarray, list[int], float]:
    """Deterministic PAM (Kaufman & Rousseeuw BUILD + SWAP) on precomputed distance matrix D."""
    n = D.shape[0]
    if k <= 1 or n <= 1:
        med = int(np.argmin(D.sum(axis=1))) if n > 0 else 0
        total_cost = float(D[:, med].sum()) if n > 0 else 0.0
        return np.zeros(n, dtype=np.int64), [med], total_cost
    k_eff = min(int(k), n)

    # BUILD phase
    medoids: list[int] = [int(np.argmin(D.sum(axis=1)))]
    while len(medoids) < k_eff:
        cur_min = D[:, medoids].min(axis=1)
        best_c: int | None = None
        best_gain = -1.0
        for c in range(n):
            if c in medoids:
                continue
            gain = float(np.maximum(0.0, cur_min - D[:, c]).sum())
            if gain > best_gain + 1e-12:
                best_gain = gain
                best_c = c
        if best_c is None:
            best_c = next(c for c in range(n) if c not in medoids)
        medoids.append(best_c)

    medoids = sorted(medoids)

    def _cost(meds: list[int]) -> float:
        return float(D[:, meds].min(axis=1).sum())

    best_cost = _cost(medoids)
    improved = True
    while improved:
        improved = False
        best_swap: tuple[list[int], float] | None = None
        for m_pos in range(k_eff):
            for c in range(n):
                if c in medoids:
                    continue
                cand = sorted(medoids[:m_pos] + [c] + medoids[m_pos + 1 :])
                cand_cost = _cost(cand)
                if cand_cost < best_cost - 1e-12:
                    if best_swap is None or cand_cost < best_swap[1] - 1e-12:
                        best_swap = (cand, cand_cost)
        if best_swap is not None:
            medoids, best_cost = best_swap
            improved = True

    raw_labels = np.argmin(D[:, medoids], axis=1)
    labels = canonicalize_labels(raw_labels)
    return labels, medoids, best_cost


def hierarchical_clustering(
    D: np.ndarray,
    k: int,
    linkage_method: str = "average",
) -> np.ndarray:
    """Agglomerative hierarchical clustering on condensed precomputed distance matrix."""
    n = D.shape[0]
    if k <= 1 or n <= 1:
        return np.zeros(n, dtype=np.int64)
    k_eff = min(int(k), n)
    sym = 0.5 * (D + D.T)
    np.fill_diagonal(sym, 0.0)
    condensed = squareform(sym, checks=False)
    Z = linkage(condensed, method=linkage_method)
    raw = fcluster(Z, t=k_eff, criterion="maxclust")
    return canonicalize_labels(raw)


def consensus_clustering_from_coassociation(
    coassoc_matrix: np.ndarray,
    k: int,
    method: str = "average",
) -> tuple[np.ndarray, np.ndarray]:
    """Derive consensus partition from scenario co-association matrix C in [0, 1]."""
    D_cons = np.clip(1.0 - coassoc_matrix, 0.0, 1.0)
    D_cons = 0.5 * (D_cons + D_cons.T)
    np.fill_diagonal(D_cons, 0.0)
    if method == "pam":
        labels, _, _ = pam_clustering(D_cons, k)
    else:
        labels = hierarchical_clustering(D_cons, k, linkage_method=method)
    return labels, D_cons


def compute_partition_geometry(
    D: np.ndarray,
    labels: np.ndarray,
) -> dict[str, Any]:
    """Compute silhouette, within-cluster dispersion, and inter-cluster separation metrics."""
    n = D.shape[0]
    unique = sorted(set(labels.tolist()))
    k_actual = len(unique)
    sizes = sorted([int((labels == c).sum()) for c in unique], reverse=True)

    # K=1 baseline dispersion
    upper_all = D[np.triu_indices(n, 1)]
    baseline_mean_pairwise = float(upper_all.mean()) if len(upper_all) > 0 else 0.0

    # Within-cluster pairwise distances
    intra_dists: list[float] = []
    inter_dists: list[float] = []
    cluster_pair_means: list[float] = []

    for c in unique:
        idx_c = np.where(labels == c)[0]
        if len(idx_c) >= 2:
            sub = D[np.ix_(idx_c, idx_c)]
            vals = sub[np.triu_indices(len(idx_c), 1)]
            intra_dists.extend(vals.tolist())

    for a_pos in range(len(unique)):
        for b_pos in range(a_pos + 1, len(unique)):
            idx_a = np.where(labels == unique[a_pos])[0]
            idx_b = np.where(labels == unique[b_pos])[0]
            block = D[np.ix_(idx_a, idx_b)]
            inter_dists.extend(block.ravel().tolist())
            cluster_pair_means.append(float(block.mean()))

    within_disp = float(np.mean(intra_dists)) if intra_dists else 0.0
    avg_sep = float(np.mean(inter_dists)) if inter_dists else 0.0
    min_cluster_pair_sep = float(min(cluster_pair_means)) if cluster_pair_means else 0.0

    if 2 <= k_actual <= n - 1:
        sil_mean = float(silhouette_score(D, labels, metric="precomputed"))
        sil_samples = [float(x) for x in silhouette_samples(D, labels, metric="precomputed")]
    else:
        sil_mean = 0.0
        sil_samples = [0.0] * n

    return {
        "k_actual": k_actual,
        "cluster_sizes": sizes,
        "min_cluster_size": min(sizes) if sizes else 0,
        "singleton_count": sum(1 for s in sizes if s == 1),
        "silhouette": round(sil_mean, 6),
        "silhouette_per_participant": [round(x, 6) for x in sil_samples],
        "within_cluster_mean_distance": round(within_disp, 6),
        "baseline_k1_mean_distance": round(baseline_mean_pairwise, 6),
        "dispersion_reduction_vs_k1": round(
            (baseline_mean_pairwise - within_disp) / baseline_mean_pairwise
            if baseline_mean_pairwise > 1e-12
            else 0.0,
            6,
        ),
        "average_pairwise_separation": round(avg_sep, 6),
        "min_intercluster_separation": round(min_cluster_pair_sep, 6),
    }


def compute_leave_one_out_stability(
    D: np.ndarray,
    k: int,
    fit_fn: Callable[[np.ndarray, int], np.ndarray],
) -> dict[str, float]:
    """Leave-one-out stability (mean and min ARI over N LOO subsets)."""
    n = D.shape[0]
    if k <= 1 or n <= 3:
        return {"loo_ari_mean": 1.0, "loo_ari_min": 1.0}
    ref_labels = fit_fn(D, k)
    aris: list[float] = []
    for leave in range(n):
        keep = [idx for idx in range(n) if idx != leave]
        D_sub = D[np.ix_(keep, keep)]
        sub_labels = fit_fn(D_sub, min(k, len(keep) - 1))
        aris.append(float(adjusted_rand_score(ref_labels[keep], sub_labels)))
    return {
        "loo_ari_mean": round(float(np.mean(aris)), 6),
        "loo_ari_min": round(float(np.min(aris)), 6),
    }


def compute_permutation_null_silhouette(
    D: np.ndarray,
    k: int,
    fit_fn: Callable[[np.ndarray, int], np.ndarray],
    n_perm: int = 200,
    seed: int = 42,
) -> dict[str, float]:
    """Null silhouette distribution by permuting upper-triangle distances symmetrically."""
    n = D.shape[0]
    if k <= 1 or n <= 2 or k >= n:
        return {"null_silhouette_mean": 0.0, "null_silhouette_p95": 0.0, "empirical_p_value": 1.0, "permutation_p_value": 1.0}

    obs_labels = fit_fn(D, k)
    if len(set(obs_labels.tolist())) <= 1:
        return {"null_silhouette_mean": 0.0, "null_silhouette_p95": 0.0, "empirical_p_value": 1.0, "permutation_p_value": 1.0}
    obs_sil = float(silhouette_score(D, obs_labels, metric="precomputed"))

    rng = np.random.default_rng(seed)
    iu = np.triu_indices(n, 1)
    vals = D[iu].copy()
    null_sils: list[float] = []
    for _ in range(n_perm):
        perm = rng.permutation(vals)
        D_perm = np.zeros((n, n), dtype=np.float64)
        D_perm[iu] = perm
        D_perm[(iu[1], iu[0])] = perm
        lbl_p = fit_fn(D_perm, k)
        if 2 <= len(set(lbl_p.tolist())) <= n - 1:
            null_sils.append(float(silhouette_score(D_perm, lbl_p, metric="precomputed")))
        else:
            null_sils.append(0.0)

    arr = np.asarray(null_sils, dtype=np.float64)
    p_val = float((1 + np.sum(arr >= obs_sil)) / (len(arr) + 1))
    return {
        "observed_silhouette": round(obs_sil, 6),
        "null_silhouette_mean": round(float(arr.mean()), 6),
        "null_silhouette_p95": round(float(np.percentile(arr, 95)), 6),
        "empirical_p_value": round(p_val, 6),
        "permutation_p_value": round(p_val, 6),
    }


def select_k_empirically(
    diagnostics_by_k: dict[int, dict[str, Any]],
    thresholds: dict[str, Any],
) -> dict[str, Any]:
    """Empirically evaluate whether any K >= 2 achieves structural separation and stability.

    Returns a transparent decision dict with selected_k (int, 1 if no stable structure),
    selected_k_status ('SELECTED_K_<k>' or 'NO_STABLE_CLUSTER_STRUCTURE'), and gate audits.
    """
    min_sil = float(thresholds.get("min_silhouette", 0.25))
    min_scen_ari = float(thresholds.get("min_scenario_ari", 0.65))
    min_boot_ari = float(thresholds.get("min_bootstrap_ari", 0.65))
    min_loo_ari = float(thresholds.get("min_loo_ari", 0.65))
    min_size = int(thresholds.get("min_cluster_size", 2))
    p_margin = float(thresholds.get("min_permutation_p_margin", 0.05))

    passing: list[tuple[int, float, dict[str, bool]]] = []
    gate_audits: dict[int, dict[str, Any]] = {}

    for k in sorted(diagnostics_by_k):
        if k <= 1:
            continue
        d = diagnostics_by_k[k]
        gates = {
            "silhouette_above_min": float(d.get("silhouette", 0.0)) >= min_sil,
            "scenario_ari_above_min": float(d.get("scenario_ari_mean", 0.0)) >= min_scen_ari,
            "bootstrap_ari_above_min": float(d.get("bootstrap_ari_mean", 0.0)) >= min_boot_ari,
            "loo_ari_above_min": float(d.get("loo_ari_mean", 0.0)) >= min_loo_ari,
            "no_singleton_outlier_only": int(d.get("min_cluster_size", 0)) >= min_size,
            "exceeds_permutation_null": float(d.get("permutation_p_value", 1.0)) <= p_margin,
        }
        gate_audits[k] = {
            "gates": gates,
            "all_gates_passed": all(gates.values()),
            "silhouette": d.get("silhouette"),
            "scenario_ari_mean": d.get("scenario_ari_mean"),
            "bootstrap_ari_mean": d.get("bootstrap_ari_mean"),
            "loo_ari_mean": d.get("loo_ari_mean"),
            "min_cluster_size": d.get("min_cluster_size"),
            "permutation_p_value": d.get("permutation_p_value"),
        }
        if all(gates.values()):
            score = (
                float(d.get("silhouette", 0.0))
                + 0.5 * float(d.get("scenario_ari_mean", 0.0))
                + 0.5 * float(d.get("bootstrap_ari_mean", 0.0))
            )
            passing.append((k, score, gates))

    if passing:
        best_k, best_score, _ = max(passing, key=lambda x: x[1])
        return {
            "selected_k": int(best_k),
            "selected_k_status": f"SELECTED_K_{best_k}",
            "is_stable_partition": True,
            "selection_score": round(best_score, 6),
            "gate_audits": gate_audits,
            "thresholds_applied": thresholds,
            "rationale": (
                f"K={best_k} satisfied all structural separation, ADR-0008 scenario stability, "
                "subtopic bootstrap stability, LOO stability, minimum cluster size, and permutation null gates."
            ),
        }

    return {
        "selected_k": 1,
        "selected_k_status": "NO_STABLE_CLUSTER_STRUCTURE",
        "is_stable_partition": False,
        "selection_score": 0.0,
        "gate_audits": gate_audits,
        "thresholds_applied": thresholds,
        "rationale": (
            "No K >= 2 in the primary PreferenceMatrix (Q01-Q13) satisfies minimum cluster separation "
            f"(silhouette >= {min_sil}), ADR-0008 uncertainty stability (scenario ARI >= {min_scen_ari}), "
            f"and subtopic resampling stability (bootstrap ARI >= {min_boot_ari}) without either collapsing "
            "into singleton outlier splits or exhibiting low scenario/bootstrap reproducibility at n=11. "
            "Retaining K=1 (single cohort) prevents overinterpreting small-sample noise."
        ),
    }
