"""Missingness-Masked Distance Metrics for Preference Heterogeneity Analysis.

Owned by: Agent 05 — Clustering & Preference Heterogeneity
Schema Version: 1.0.0 (Aligned with ADR-0005 and ADR-0008)

All distance functions operate strictly on mutually observed subtopics/questions
without imputing missing participant preferences. Multi-scenario uncertainty
sets are evaluated via exact pairwise set expectation rather than collapsing to
arbitrary point averages.
"""

from __future__ import annotations

import hashlib
import math
from typing import Callable, Literal, Sequence

import numpy as np
from scipy.stats import spearmanr

DistanceMetricName = Literal[
    "MASKED_JENSEN_SHANNON",
    "MASKED_COSINE",
    "MASKED_WEIGHTED_L1",
]


def jensen_shannon_distance(p: dict[str, float], q: dict[str, float]) -> float:
    """Metric square-root Jensen-Shannon distance in base-2 bits, bounded in [0, 1]."""
    keys = sorted(set(p) | set(q))
    if not keys:
        return 0.0
    pv = np.array([max(0.0, float(p.get(k, 0.0))) for k in keys], dtype=np.float64)
    qv = np.array([max(0.0, float(q.get(k, 0.0))) for k in keys], dtype=np.float64)
    sp = float(pv.sum())
    sq = float(qv.sum())
    if sp <= 0.0 or sq <= 0.0:
        return 0.0
    pv /= sp
    qv /= sq
    m = 0.5 * (pv + qv)
    jsd = 0.0
    for a, mid in zip(pv, m):
        if a > 0.0 and mid > 0.0:
            jsd += 0.5 * float(a) * math.log2(float(a) / float(mid))
    for b, mid in zip(qv, m):
        if b > 0.0 and mid > 0.0:
            jsd += 0.5 * float(b) * math.log2(float(b) / float(mid))
    return float(math.sqrt(max(0.0, min(1.0, jsd))))


def cosine_distance(p: dict[str, float], q: dict[str, float]) -> float:
    """Cosine dissimilarity (1 - cos(p, q)) in [0, 1] over aligned simplex keys."""
    keys = sorted(set(p) | set(q))
    if not keys:
        return 0.0
    pv = np.array([max(0.0, float(p.get(k, 0.0))) for k in keys], dtype=np.float64)
    qv = np.array([max(0.0, float(q.get(k, 0.0))) for k in keys], dtype=np.float64)
    npv = float(np.linalg.norm(pv))
    nqv = float(np.linalg.norm(qv))
    if npv <= 0.0 or nqv <= 0.0:
        return 0.0
    cos_sim = float(np.dot(pv, qv) / (npv * nqv))
    return float(max(0.0, min(1.0, 1.0 - cos_sim)))


def weighted_l1_distance(p: dict[str, float], q: dict[str, float]) -> float:
    """Total variation / half-L1 simplex distance in [0, 1]."""
    keys = sorted(set(p) | set(q))
    if not keys:
        return 0.0
    l1 = sum(abs(max(0.0, float(p.get(k, 0.0))) - max(0.0, float(q.get(k, 0.0)))) for k in keys)
    return float(max(0.0, min(1.0, 0.5 * l1)))


def get_distribution_distance_fn(
    metric: DistanceMetricName,
) -> Callable[[dict[str, float], dict[str, float]], float]:
    """Return the distribution-level distance callable for a canonical metric identifier."""
    mapping: dict[str, Callable[[dict[str, float], dict[str, float]], float]] = {
        "MASKED_JENSEN_SHANNON": jensen_shannon_distance,
        "MASKED_COSINE": cosine_distance,
        "MASKED_WEIGHTED_L1": weighted_l1_distance,
    }
    if metric not in mapping:
        raise ValueError(f"Unsupported distance metric '{metric}'. Expected one of {sorted(mapping)}.")
    return mapping[metric]


def set_to_set_expected_distance(
    scenarios_i: Sequence[dict[str, float]],
    scenarios_j: Sequence[dict[str, float]],
    dist_fn: Callable[[dict[str, float], dict[str, float]], float],
) -> float:
    """Exact expected pairwise distance over discrete scenario sets S_i x S_j."""
    if not scenarios_i or not scenarios_j:
        return 1.0
    total = 0.0
    for si in scenarios_i:
        for sj in scenarios_j:
            total += dist_fn(si, sj)
    return float(total / (len(scenarios_i) * len(scenarios_j)))


def hash_distance_matrix(D: np.ndarray, participant_ids: Sequence[str]) -> str:
    """Deterministic SHA-256 digest of a pairwise distance matrix and participant order."""
    payload = {
        "participant_ids": list(participant_ids),
        "matrix": [[round(float(x), 8) for x in row] for row in D.tolist()],
    }
    encoded = str(payload).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def compute_masked_subtopic_distance_matrix(
    participant_ids: Sequence[str],
    subtopic_scenarios: dict[str, dict[str, list[dict[str, float]]]],
    metric: DistanceMetricName = "MASKED_JENSEN_SHANNON",
    min_shared_subtopics: int = 3,
    subtopic_weights: dict[str, dict[str, float]] | None = None,
) -> dict[str, object]:
    """Compute missingness-masked pairwise distance matrix across participants.

    Only subtopics observed and comparable for BOTH participants in a pair (i, j)
    contribute to d(i, j). Zero missingness imputation is ever performed.
    """
    n = len(participant_ids)
    dist_fn = get_distribution_distance_fn(metric)
    D = np.zeros((n, n), dtype=np.float64)
    shared_counts = np.zeros((n, n), dtype=np.int64)
    below_min_pairs: list[tuple[str, str, int]] = []

    for i in range(n):
        pi = participant_ids[i]
        subs_i = subtopic_scenarios.get(pi, {})
        for j in range(i + 1, n):
            pj = participant_ids[j]
            subs_j = subtopic_scenarios.get(pj, {})
            shared = sorted(set(subs_i) & set(subs_j))
            cnt = len(shared)
            shared_counts[i, j] = cnt
            shared_counts[j, i] = cnt
            if cnt < min_shared_subtopics:
                below_min_pairs.append((pi, pj, cnt))
            if cnt == 0:
                val = 1.0
            else:
                num = 0.0
                den = 0.0
                for sid in shared:
                    w = 1.0
                    if subtopic_weights is not None:
                        wi = float(subtopic_weights.get(pi, {}).get(sid, 1.0))
                        wj = float(subtopic_weights.get(pj, {}).get(sid, 1.0))
                        w = math.sqrt(max(0.0, wi) * max(0.0, wj))
                    if w <= 0.0:
                        continue
                    d_cell = set_to_set_expected_distance(subs_i[sid], subs_j[sid], dist_fn)
                    num += w * d_cell
                    den += w
                val = num / den if den > 0.0 else 1.0
            D[i, j] = val
            D[j, i] = val

    np.fill_diagonal(D, 0.0)
    upper = shared_counts[np.triu_indices(n, 1)]
    min_shared_obs = int(upper.min()) if len(upper) > 0 else 0
    med_shared_obs = int(np.median(upper)) if len(upper) > 0 else 0
    max_shared_obs = int(upper.max()) if len(upper) > 0 else 0

    return {
        "distance_matrix": D,
        "shared_counts": shared_counts,
        "min_shared_observed": min_shared_obs,
        "median_shared_observed": med_shared_obs,
        "max_shared_observed": max_shared_obs,
        "below_min_shared_pairs": below_min_pairs,
        "matrix_hash": hash_distance_matrix(D, participant_ids),
    }


def compute_question_aggregated_distance_matrix(
    participant_ids: Sequence[str],
    question_subtopic_scenarios: dict[str, dict[str, dict[str, list[dict[str, float]]]]],
    metric: DistanceMetricName = "MASKED_JENSEN_SHANNON",
) -> dict[str, object]:
    """Compute question-level aggregated distance matrix (equal weight per observed Q01-Q13 question).

    For each pair (i, j) and each mutually observed question q where they share at least
    one comparable subtopic, averages subtopic distances within q and then averages across
    those mutually observed questions. Unobserved (participant, question) pairs are masked out.
    """
    n = len(participant_ids)
    dist_fn = get_distribution_distance_fn(metric)
    D = np.zeros((n, n), dtype=np.float64)
    shared_q_counts = np.zeros((n, n), dtype=np.int64)

    for i in range(n):
        pi = participant_ids[i]
        qs_i = question_subtopic_scenarios.get(pi, {})
        for j in range(i + 1, n):
            pj = participant_ids[j]
            qs_j = question_subtopic_scenarios.get(pj, {})
            q_dists: list[float] = []
            for qid in sorted(set(qs_i) & set(qs_j)):
                shared_subs = sorted(set(qs_i[qid]) & set(qs_j[qid]))
                if shared_subs:
                    mean_q = float(
                        np.mean([set_to_set_expected_distance(qs_i[qid][s], qs_j[qid][s], dist_fn) for s in shared_subs])
                    )
                    q_dists.append(mean_q)
            shared_q_counts[i, j] = len(q_dists)
            shared_q_counts[j, i] = len(q_dists)
            val = float(np.mean(q_dists)) if q_dists else 1.0
            D[i, j] = val
            D[j, i] = val

    np.fill_diagonal(D, 0.0)
    upper = shared_q_counts[np.triu_indices(n, 1)]
    return {
        "distance_matrix": D,
        "shared_question_counts": shared_q_counts,
        "min_shared_questions": int(upper.min()) if len(upper) > 0 else 0,
        "median_shared_questions": int(np.median(upper)) if len(upper) > 0 else 0,
        "max_shared_questions": int(upper.max()) if len(upper) > 0 else 0,
        "matrix_hash": hash_distance_matrix(D, participant_ids),
    }


def compute_utility_distance_matrices(utility_matrix: np.ndarray) -> dict[str, np.ndarray]:
    """Compute pairwise distance matrices over participant utility profiles (N x S).

    Returns centered-cosine (Pearson correlation), Spearman rank-correlation, and RMS L2 matrices.
    """
    n = utility_matrix.shape[0]
    # 1. Centered cosine / Pearson correlation distance: 0.5 * (1 - r)
    centered = utility_matrix - utility_matrix.mean(axis=1, keepdims=True)
    norms = np.linalg.norm(centered, axis=1, keepdims=True)
    normed = np.divide(centered, np.where(norms > 1e-12, norms, 1.0))
    corr = np.clip(normed @ normed.T, -1.0, 1.0)
    d_corr = np.clip(0.5 * (1.0 - corr), 0.0, 1.0)
    d_corr = 0.5 * (d_corr + d_corr.T)
    np.fill_diagonal(d_corr, 0.0)

    # 2. Spearman rank-correlation distance: 0.5 * (1 - rho)
    if n >= 2:
        rho = spearmanr(utility_matrix, axis=1).statistic
        if np.ndim(rho) == 0:
            rho_mat = np.array([[1.0, float(rho)], [float(rho), 1.0]], dtype=np.float64)
        else:
            rho_mat = np.asarray(rho, dtype=np.float64)
        d_spearman = np.clip(0.5 * (1.0 - rho_mat), 0.0, 1.0)
        d_spearman = 0.5 * (d_spearman + d_spearman.T)
        np.fill_diagonal(d_spearman, 0.0)
    else:
        d_spearman = np.zeros((n, n), dtype=np.float64)

    # 3. RMS L2 utility distance
    diffs = utility_matrix[:, None, :] - utility_matrix[None, :, :]
    d_l2 = np.sqrt(np.mean(diffs ** 2, axis=2))
    d_l2 = 0.5 * (d_l2 + d_l2.T)
    np.fill_diagonal(d_l2, 0.0)

    return {
        "utility_centered_cosine": d_corr,
        "utility_spearman": d_spearman,
        "utility_rms_l2": d_l2,
    }
