"""Authorized Social-Choice Aggregation & ADR-0008 Uncertainty Engine (Agent 06).

Owned by: Agent 06 — Voting & Social Choice
Schema Version: 1.0.0 (Aligned with ADR-0005, ADR-0007, and ADR-0008)

Evaluates repository-authorized social-choice rules (Borda count, Condorcet
pairwise analysis, and Simpson-Kramer Minimax) over ParticipantUtility scenario
ensembles without ranking participants, without cluster-based vote weighting,
and without fabricating complete point orders across ADR-0008 coding gaps.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

import numpy as np

from src.contracts import SCHEMA_VERSION
from src.preference.utilities import UtilityEnsembleSummary
from src.voting.voting_rrv import small_n_quota_diagnostics


def _tie_safe_borda_ranks(vals: np.ndarray, tol: float = 1e-12) -> np.ndarray:
    """Return Borda points in [0, S-1] per candidate for one voter using average mid-rank on ties."""
    S = vals.shape[0]
    order = np.argsort(vals, kind="mergesort")
    sv = vals[order]
    ranks = np.empty(S, dtype=np.float64)
    i = 0
    while i < S:
        j = i
        while j + 1 < S and abs(float(sv[j + 1]) - float(sv[i])) <= tol:
            j += 1
        ranks[order[i : j + 1]] = 0.5 * (i + j)
        i = j + 1
    return ranks


def compute_borda_scores(
    utility_matrix: np.ndarray,
    solution_ids: list[str],
    *,
    tol: float = 1e-12,
) -> dict[str, Any]:
    """Compute equal-weight Borda count scores over (S, P) utility matrix."""
    S, P = utility_matrix.shape
    if S == 0 or P == 0:
        raise ValueError("Empty utility matrix passed to compute_borda_scores.")

    total_scores = np.zeros(S, dtype=np.float64)
    for p_i in range(P):
        total_scores += _tie_safe_borda_ranks(utility_matrix[:, p_i], tol=tol)

    max_score = float(total_scores.max())
    winners = [solution_ids[i] for i in range(S) if abs(float(total_scores[i]) - max_score) <= 1e-9]
    ordered_idx = sorted(range(S), key=lambda i: (-float(total_scores[i]), solution_ids[i]))
    ranking = [solution_ids[i] for i in ordered_idx]
    top2_margin = (
        float(total_scores[ordered_idx[0]] - total_scores[ordered_idx[1]])
        if S >= 2
        else 0.0
    )

    return {
        "rule": "borda_count",
        "voter_count": P,
        "candidate_count": S,
        "equal_voter_weight": round(1.0 / P, 6),
        "max_score": round(max_score, 6),
        "top2_margin": round(top2_margin, 6),
        "winner_ids": winners,
        "ranking": ranking,
        "scores": {solution_ids[i]: round(float(total_scores[i]), 6) for i in ordered_idx},
    }


def _compute_smith_set(margins: np.ndarray, solution_ids: list[str]) -> list[str]:
    """Compute exact Smith set (smallest non-empty set beating/tying all outsiders) via Tarjan SCC."""
    S = margins.shape[0]
    if S == 0:
        return []
    # Build weak dominance graph: edge a -> b if margins[a, b] >= 0 (a beats or ties b)
    # Using Tarjan's SCC in O(S^2) on numpy adjacency rows
    index_counter = 0
    indices = [-1] * S
    lowlink = [0] * S
    on_stack = [False] * S
    stack: list[int] = []
    sccs: list[list[int]] = []

    adj = margins >= 0
    np.fill_diagonal(adj, False)
    neighbors = [np.flatnonzero(adj[i]).tolist() for i in range(S)]

    # Iterative Tarjan to avoid recursion-limit risk at S=543
    for root in range(S):
        if indices[root] != -1:
            continue
        call_stack: list[tuple[int, int]] = [(root, 0)]
        indices[root] = lowlink[root] = index_counter
        index_counter += 1
        stack.append(root)
        on_stack[root] = True

        while call_stack:
            v, ni = call_stack[-1]
            nbrs = neighbors[v]
            if ni < len(nbrs):
                w = nbrs[ni]
                call_stack[-1] = (v, ni + 1)
                if indices[w] == -1:
                    indices[w] = lowlink[w] = index_counter
                    index_counter += 1
                    stack.append(w)
                    on_stack[w] = True
                    call_stack.append((w, 0))
                elif on_stack[w]:
                    if indices[w] < lowlink[v]:
                        lowlink[v] = indices[w]
            else:
                call_stack.pop()
                if call_stack:
                    parent = call_stack[-1][0]
                    if lowlink[v] < lowlink[parent]:
                        lowlink[parent] = lowlink[v]
                if lowlink[v] == indices[v]:
                    comp: list[int] = []
                    while True:
                        w = stack.pop()
                        on_stack[w] = False
                        comp.append(w)
                        if w == v:
                            break
                    sccs.append(comp)

    # Select source SCC(s) with no strict incoming defeat from any node outside the SCC
    top_nodes: list[int] = []
    for comp in sccs:
        comp_set = set(comp)
        outside = [u for u in range(S) if u not in comp_set]
        if not outside or not bool((margins[np.ix_(outside, comp)] > 0).any()):
            top_nodes = comp
            break
    if not top_nodes:
        top_nodes = sccs[-1]
    return sorted(solution_ids[i] for i in top_nodes)


def compute_condorcet_minimax_metrics(
    utility_matrix: np.ndarray,
    solution_ids: list[str],
    *,
    tol: float = 1e-12,
    compute_smith: bool = True,
) -> dict[str, Any]:
    """Compute pairwise Condorcet, cycle diagnostics, Copeland diagnostic, and Simpson-Kramer Minimax."""
    S, P = utility_matrix.shape
    if S == 0 or P == 0:
        raise ValueError("Empty utility matrix passed to compute_condorcet_minimax_metrics.")

    # Pairwise strict preference counts across voters
    gt_counts = (utility_matrix[:, None, :] > utility_matrix[None, :, :] + tol).sum(axis=2)
    lt_counts = gt_counts.T
    margins = (gt_counts - lt_counts).astype(np.int64)
    np.fill_diagonal(margins, 0)

    wins = (margins > 0).sum(axis=1)
    losses = (margins < 0).sum(axis=1)
    ties = (margins == 0).sum(axis=1) - 1

    strict_condorcet = [
        solution_ids[i] for i in range(S) if losses[i] == 0 and wins[i] == S - 1
    ]
    weak_condorcet = [solution_ids[i] for i in range(S) if losses[i] == 0]
    has_cycle = len(weak_condorcet) == 0

    copeland = wins - losses
    max_copeland = int(copeland.max())
    copeland_top = [solution_ids[i] for i in range(S) if int(copeland[i]) == max_copeland]
    ordered_copeland = sorted(
        range(S), key=lambda i: (-int(copeland[i]), int(losses[i]), solution_ids[i])
    )

    worst_defeat = np.where(margins < 0, -margins, 0).max(axis=1)
    min_wd = int(worst_defeat.min())
    minimax_winners = [solution_ids[i] for i in range(S) if int(worst_defeat[i]) == min_wd]
    ordered_minimax = sorted(
        range(S), key=lambda i: (int(worst_defeat[i]), -int(copeland[i]), solution_ids[i])
    )

    smith_set = _compute_smith_set(margins, solution_ids) if compute_smith else []

    return {
        "voter_count": P,
        "candidate_count": S,
        "condorcet": {
            "strict_condorcet_winners": strict_condorcet,
            "weak_condorcet_winners": weak_condorcet,
            "has_condorcet_winner": len(strict_condorcet) > 0,
            "has_weak_condorcet_winner": len(weak_condorcet) > 0,
            "has_condorcet_cycle": has_cycle,
            "smith_set_ids": smith_set,
            "smith_set_size": len(smith_set),
            "copeland_diagnostic_top_ids": copeland_top,
            "copeland_max_score": max_copeland,
            "copeland_top20_ranking": [solution_ids[i] for i in ordered_copeland[:20]],
        },
        "minimax": {
            "rule": "minimax_simpson_kramer_margin",
            "min_worst_pairwise_defeat": min_wd,
            "winner_ids": minimax_winners,
            "ranking": [solution_ids[i] for i in ordered_minimax],
            "worst_pairwise_defeats": {
                solution_ids[i]: int(worst_defeat[i]) for i in ordered_minimax
            },
        },
    }


def compute_interval_partial_order_stats(
    min_scenario_matrix: np.ndarray,
    max_scenario_matrix: np.ndarray,
) -> dict[str, Any]:
    """Quantify strict interval-order comparability without fabricating orders or ranking participants."""
    S, P = min_scenario_matrix.shape
    total_pairs = S * (S - 1) // 2
    comp_fractions: list[float] = []
    for p_i in range(P):
        lo = min_scenario_matrix[:, p_i]
        hi = max_scenario_matrix[:, p_i]
        strict_comp = int((lo[:, None] > hi[None, :] + 1e-12).sum())
        comp_fractions.append(strict_comp / total_pairs if total_pairs > 0 else 0.0)

    # Interval-certain pairwise majority across voters: a strictly beats b for voter p iff lo[a,p] > hi[b,p]
    certain_gt = (min_scenario_matrix[:, None, :] > max_scenario_matrix[None, :, :] + 1e-12).sum(axis=2)
    certain_majority_wins = int((certain_gt > (P / 2.0)).sum())

    return {
        "participant_count": P,
        "candidate_count": S,
        "total_unordered_candidate_pairs": total_pairs,
        "aggregate_strict_interval_comparability": {
            "min_fraction": round(min(comp_fractions) if comp_fractions else 0.0, 6),
            "median_fraction": round(float(np.median(comp_fractions)) if comp_fractions else 0.0, 6),
            "mean_fraction": round(float(np.mean(comp_fractions)) if comp_fractions else 0.0, 6),
            "max_fraction": round(max(comp_fractions) if comp_fractions else 0.0, 6),
        },
        "interval_certain_strict_majority_pairs": certain_majority_wins,
        "interval_certain_strict_majority_share": round(
            certain_majority_wins / max(1, S * (S - 1)), 6
        ),
        "ranked_as_participant": False,
    }


def propagate_social_choice_uncertainty(
    ensemble: UtilityEnsembleSummary,
    *,
    tol: float = 1e-12,
) -> dict[str, Any]:
    """Propagate ADR-0008 uncertainty ensembles across Borda, Condorcet, and Minimax."""
    sol_ids = list(ensemble.solution_ids)
    S, P = ensemble.expected_utility_matrix.shape
    mc_utils = ensemble.mc_draws_utilities
    D = mc_utils.shape[0]
    regimes = ensemble.mc_draw_regimes

    # 1. Expected-reference baseline
    exp_borda = compute_borda_scores(ensemble.expected_utility_matrix, sol_ids, tol=tol)
    exp_cm = compute_condorcet_minimax_metrics(ensemble.expected_utility_matrix, sol_ids, tol=tol, compute_smith=True)

    # 2. Full Monte Carlo pass (D draws)
    borda_win_mass: dict[str, float] = defaultdict(float)
    borda_top5_mass: dict[str, float] = defaultdict(float)
    borda_ranks_accum = np.zeros((D, S), dtype=np.float64)

    minimax_win_mass: dict[str, float] = defaultdict(float)
    minimax_top5_mass: dict[str, float] = defaultdict(float)
    minimax_defeats_accum = np.zeros((D, S), dtype=np.float64)

    condorcet_strict_mass: dict[str, float] = defaultdict(float)
    condorcet_weak_mass: dict[str, float] = defaultdict(float)
    strict_condorcet_exists_flags = np.zeros(D, dtype=bool)
    weak_condorcet_exists_flags = np.zeros(D, dtype=bool)

    draw_borda_winners: list[list[str]] = []
    draw_minimax_winners: list[list[str]] = []
    draw_weak_condorcet: list[list[str]] = []

    for d in range(D):
        U_d = mc_utils[d]
        # Borda vectorized per draw
        b_scores = np.zeros(S, dtype=np.float64)
        for p_i in range(P):
            b_scores += _tie_safe_borda_ranks(U_d[:, p_i], tol=tol)
        max_b = float(b_scores.max())
        b_win_idx = [i for i in range(S) if abs(float(b_scores[i]) - max_b) <= 1e-9]
        b_wins = [sol_ids[i] for i in b_win_idx]
        draw_borda_winners.append(b_wins)
        for sid in b_wins:
            borda_win_mass[sid] += 1.0 / len(b_wins)

        b_order = np.argsort(-b_scores, kind="mergesort")
        # Ordinal ranks 1..S (average on exact score ties or fast ordinal rank)
        rank_positions = np.empty(S, dtype=np.float64)
        rank_positions[b_order] = np.arange(1, S + 1, dtype=np.float64)
        borda_ranks_accum[d] = rank_positions
        for idx in b_order[:5]:
            borda_top5_mass[sol_ids[int(idx)]] += 1.0

        # Pairwise Condorcet & Minimax per draw
        gt = (U_d[:, None, :] > U_d[None, :, :] + tol).sum(axis=2)
        margins = (gt - gt.T).astype(np.int64)
        np.fill_diagonal(margins, 0)
        losses = (margins < 0).sum(axis=1)
        wins = (margins > 0).sum(axis=1)

        sc_idx = [i for i in range(S) if losses[i] == 0 and wins[i] == S - 1]
        wc_idx = [i for i in range(S) if losses[i] == 0]
        if sc_idx:
            strict_condorcet_exists_flags[d] = True
            for i in sc_idx:
                condorcet_strict_mass[sol_ids[i]] += 1.0 / len(sc_idx)
        if wc_idx:
            weak_condorcet_exists_flags[d] = True
            for i in wc_idx:
                condorcet_weak_mass[sol_ids[i]] += 1.0 / len(wc_idx)
        draw_weak_condorcet.append([sol_ids[i] for i in wc_idx])

        wd = np.where(margins < 0, -margins, 0).max(axis=1)
        minimax_defeats_accum[d] = wd
        min_wd = int(wd.min())
        mw_idx = [i for i in range(S) if int(wd[i]) == min_wd]
        mw_sids = [sol_ids[i] for i in mw_idx]
        draw_minimax_winners.append(mw_sids)
        for sid in mw_sids:
            minimax_win_mass[sid] += 1.0 / len(mw_sids)

        m_order = np.argsort(wd, kind="mergesort")
        for idx in m_order[:5]:
            minimax_top5_mass[sol_ids[int(idx)]] += 1.0

    def _sorted_probs(mass_dict: dict[str, float], denom: int) -> dict[str, float]:
        if denom <= 0:
            return {}
        return {
            sid: round(val / denom, 6)
            for sid, val in sorted(mass_dict.items(), key=lambda kv: (-kv[1], kv[0]))
        }

    borda_probs = _sorted_probs(borda_win_mass, D)
    borda_top5_probs = _sorted_probs(borda_top5_mass, D)
    minimax_probs = _sorted_probs(minimax_win_mass, D)
    minimax_top5_probs = _sorted_probs(minimax_top5_mass, D)
    cond_strict_probs = _sorted_probs(condorcet_strict_mass, D)
    cond_weak_probs = _sorted_probs(condorcet_weak_mass, D)

    # Rank stability summary for key candidates (expected top-10 union + MC top winners)
    mean_borda_ranks = borda_ranks_accum.mean(axis=0)
    std_borda_ranks = borda_ranks_accum.std(axis=0)
    q05_borda_ranks = np.quantile(borda_ranks_accum, 0.05, axis=0)
    q95_borda_ranks = np.quantile(borda_ranks_accum, 0.95, axis=0)
    mean_minimax_wd = minimax_defeats_accum.mean(axis=0)
    max_minimax_wd = minimax_defeats_accum.max(axis=0)

    key_sids = sorted(
        set(exp_borda["ranking"][:10])
        | set(list(borda_probs.keys())[:10])
        | set(exp_cm["minimax"]["ranking"][:10])
        | set(list(minimax_probs.keys())[:10])
    )
    sid_to_idx = {sid: idx for idx, sid in enumerate(sol_ids)}
    rank_stability_summary = {
        sid: {
            "borda_mean_rank": round(float(mean_borda_ranks[sid_to_idx[sid]]), 3),
            "borda_rank_std": round(float(std_borda_ranks[sid_to_idx[sid]]), 3),
            "borda_rank_90pct_interval": [
                round(float(q05_borda_ranks[sid_to_idx[sid]]), 1),
                round(float(q95_borda_ranks[sid_to_idx[sid]]), 1),
            ],
            "borda_winner_inclusion_prob": borda_probs.get(sid, 0.0),
            "borda_top5_inclusion_prob": borda_top5_probs.get(sid, 0.0),
            "minimax_winner_inclusion_prob": minimax_probs.get(sid, 0.0),
            "minimax_mean_worst_defeat": round(float(mean_minimax_wd[sid_to_idx[sid]]), 3),
            "minimax_max_worst_defeat": int(max_minimax_wd[sid_to_idx[sid]]),
            "weak_condorcet_inclusion_prob": cond_weak_probs.get(sid, 0.0),
        }
        for sid in key_sids
    }

    # 3. Deterministic sensitivity scenarios (weighting, coding-gap corners, derived barycenters)
    def _summarize_matrix(label: str, mat: np.ndarray, *, origin: str) -> dict[str, Any]:
        b = compute_borda_scores(mat, sol_ids, tol=tol)
        cm = compute_condorcet_minimax_metrics(mat, sol_ids, tol=tol, compute_smith=True)
        return {
            "scenario_label": label,
            "scenario_origin": origin,
            "borda_winners": b["winner_ids"],
            "borda_top5": b["ranking"][:5],
            "borda_max_score": b["max_score"],
            "strict_condorcet_winners": cm["condorcet"]["strict_condorcet_winners"],
            "weak_condorcet_winners": cm["condorcet"]["weak_condorcet_winners"],
            "has_condorcet_cycle": cm["condorcet"]["has_condorcet_cycle"],
            "smith_set_size": cm["condorcet"]["smith_set_size"],
            "smith_set_ids": cm["condorcet"]["smith_set_ids"][:20],
            "copeland_top_ids": cm["condorcet"]["copeland_diagnostic_top_ids"],
            "minimax_winners": cm["minimax"]["winner_ids"],
            "minimax_min_worst_defeat": cm["minimax"]["min_worst_pairwise_defeat"],
            "minimax_top5": cm["minimax"]["ranking"][:5],
        }

    weighting_scenarios = {
        "coder_semantic_importance": _summarize_matrix(
            "coder_semantic_importance", ensemble.expected_utility_matrix, origin="OBSERVED_CODER_EVIDENCE"
        ),
        "uniform_subtopic_weight": _summarize_matrix(
            "uniform_subtopic_weight", ensemble.uniform_subtopic_utility_matrix, origin="OBSERVED_CODER_EVIDENCE"
        ),
        "uniform_question_weight": _summarize_matrix(
            "uniform_question_weight", ensemble.uniform_question_utility_matrix, origin="OBSERVED_CODER_EVIDENCE"
        ),
    }

    corner_scenarios = {
        k: _summarize_matrix(k, mat, origin="OBSERVED_CODER_EVIDENCE_CORNER")
        for k, mat in sorted(ensemble.coupled_gap_corner_matrices.items())
    }

    barycenter_scenarios = {
        k: _summarize_matrix(k, mat, origin="DERIVED_ROBUSTNESS_CONVEX_BARYCENTER")
        for k, mat in sorted(ensemble.derived_barycenter_matrices.items())
    }

    # 4. Regime-stratified MC slices (interpretation, conditional operator, single-coder partial ID)
    def _mc_slice_summary(indices: list[int]) -> dict[str, Any]:
        if not indices:
            return {"n_draws": 0, "borda_top_winners": {}, "minimax_top_winners": {}, "weak_condorcet_rate": 0.0}
        b_cnt: dict[str, float] = defaultdict(float)
        m_cnt: dict[str, float] = defaultdict(float)
        wc_cnt = 0
        for idx in indices:
            bw = draw_borda_winners[idx]
            for s in bw:
                b_cnt[s] += 1.0 / len(bw)
            mw = draw_minimax_winners[idx]
            for s in mw:
                m_cnt[s] += 1.0 / len(mw)
            if draw_weak_condorcet[idx]:
                wc_cnt += 1
        n = len(indices)
        return {
            "n_draws": n,
            "borda_top_winners": {
                k: round(v / n, 4) for k, v in sorted(b_cnt.items(), key=lambda kv: -kv[1])[:5]
            },
            "minimax_top_winners": {
                k: round(v / n, 4) for k, v in sorted(m_cnt.items(), key=lambda kv: -kv[1])[:5]
            },
            "weak_condorcet_rate": round(wc_cnt / n, 4),
        }

    interpretation_sensitivity = {
        "mc_EPISTEMIC_CATEGORICAL_ALL_FLAGGED": _mc_slice_summary(
            [r["draw_index"] for r in regimes if r.get("interpretation_mode") == "EPISTEMIC_CATEGORICAL_ALL_FLAGGED"]
        ),
        "mc_EXPLICIT_MIXED_ALL_FLAGGED": _mc_slice_summary(
            [r["draw_index"] for r in regimes if r.get("interpretation_mode") == "EXPLICIT_MIXED_ALL_FLAGGED"]
        ),
        "mc_SAMPLED_INTERPRETATION_VARIANT": _mc_slice_summary(
            [r["draw_index"] for r in regimes if r.get("interpretation_mode") == "SAMPLED_INTERPRETATION_VARIANT"]
        ),
        "mc_COND_ADVERSARIAL_LOW": _mc_slice_summary(
            [r["draw_index"] for r in regimes if r.get("conditional_mode") == "ADVERSARIAL_LOW"]
        ),
        "mc_COND_CHARITABLE_HIGH": _mc_slice_summary(
            [r["draw_index"] for r in regimes if r.get("conditional_mode") == "CHARITABLE_HIGH"]
        ),
    }

    partial_id_sensitivity = {
        "mc_CODER_A_REGIME": _mc_slice_summary(
            [r["draw_index"] for r in regimes if r.get("coder_regime") == "CODER_A_REGIME"]
        ),
        "mc_CODER_B_REGIME": _mc_slice_summary(
            [r["draw_index"] for r in regimes if r.get("coder_regime") == "CODER_B_REGIME"]
        ),
        "mc_MIXED_CODER_SAMPLING": _mc_slice_summary(
            [r["draw_index"] for r in regimes if r.get("coder_regime") == "MIXED_INDEPENDENT_CODER_SAMPLING"]
        ),
        "mc_OMISSION_EXCLUDE_ALL_0": _mc_slice_summary(
            [r["draw_index"] for r in regimes if r.get("omission_include_prob") == 0.0]
        ),
        "mc_OMISSION_INCLUDE_ALL_1": _mc_slice_summary(
            [r["draw_index"] for r in regimes if r.get("omission_include_prob") == 1.0]
        ),
        "mc_OVERLAP_MULT_0.5": _mc_slice_summary(
            [r["draw_index"] for r in regimes if r.get("overlap_multiplier") == 0.5]
        ),
        "mc_OVERLAP_MULT_1.0": _mc_slice_summary(
            [r["draw_index"] for r in regimes if r.get("overlap_multiplier") == 1.0]
        ),
    }

    # Check survival thresholds (whether any candidate survives as winner across all admissible scenarios)
    all_borda_corner_winners = [tuple(sorted(v["borda_winners"])) for v in corner_scenarios.values()]
    all_minimax_corner_winners = [set(v["minimax_winners"]) for v in corner_scenarios.values()]
    minimax_corner_intersection = (
        sorted(set.intersection(*all_minimax_corner_winners)) if all_minimax_corner_winners else []
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "contract_id": "voting_uncertainty_v1",
        "run_id": ensemble.run_id,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "monte_carlo_draws": D,
        "valid_participant_count": P,
        "candidate_count": S,
        "equal_ballot_weighting_enforced": True,
        "cluster_weights_applied": False,
        "participants_ranked": False,
        "expected_reference": {
            "note": "Expected-value reference only (NOT collapsed point truth under ADR-0008).",
            "borda_count": exp_borda,
            "condorcet": exp_cm["condorcet"],
            "minimax": exp_cm["minimax"],
        },
        "monte_carlo_results": {
            "borda_winner_inclusion_probabilities": borda_probs,
            "borda_unique_winners_observed": len(borda_probs),
            "borda_top5_inclusion_probabilities": dict(list(borda_top5_probs.items())[:20]),
            "condorcet_strict_exists_rate": round(float(strict_condorcet_exists_flags.mean()), 6),
            "condorcet_weak_exists_rate": round(float(weak_condorcet_exists_flags.mean()), 6),
            "condorcet_cycle_rate": round(float(1.0 - weak_condorcet_exists_flags.mean()), 6),
            "condorcet_strict_winner_inclusion_probabilities": cond_strict_probs,
            "condorcet_weak_winner_inclusion_probabilities": cond_weak_probs,
            "minimax_winner_inclusion_probabilities": minimax_probs,
            "minimax_unique_winners_observed": len(minimax_probs),
            "minimax_top5_inclusion_probabilities": dict(list(minimax_top5_probs.items())[:20]),
        },
        "rank_stability_summary": rank_stability_summary,
        "weighting_sensitivity": weighting_scenarios,
        "coupled_coding_gap_corners": corner_scenarios,
        "probability_interpretation_sensitivity": interpretation_sensitivity,
        "partial_identification_sensitivity": partial_id_sensitivity,
        "derived_barycenter_scenarios": barycenter_scenarios,
        "robustness_verdicts": {
            "borda_has_unique_invariant_winner": len(set(all_borda_corner_winners)) == 1 and len(borda_probs) == 1,
            "borda_max_mc_inclusion_prob": max(borda_probs.values()) if borda_probs else 0.0,
            "condorcet_winner_exists_on_expected_reference": exp_cm["condorcet"]["has_weak_condorcet_winner"],
            "condorcet_cycle_rate_mc": round(float(1.0 - weak_condorcet_exists_flags.mean()), 6),
            "minimax_has_invariant_corner_winner": len(minimax_corner_intersection) > 0,
            "minimax_corner_intersection_ids": minimax_corner_intersection,
            "minimax_max_mc_inclusion_prob": max(minimax_probs.values()) if minimax_probs else 0.0,
            "conclusion_survives_all_admissible_scenarios": False,
        },
    }


def compute_small_n_sensitivity(
    ensemble: UtilityEnsembleSummary,
    unc_report: dict[str, Any],
    *,
    committee_size_reference: int = 3,
    tol: float = 1e-12,
) -> dict[str, Any]:
    """Evaluate small-N discreteness and aggregate single-ballot / missing-cell sensitivity.

    Strictly avoids ranking or scoring individual participants: only aggregate
    collective-choice stability counts/rates across the N leave-one-out subsamples
    are computed and reported.
    """
    exp_U = ensemble.expected_utility_matrix
    sol_ids = list(ensemble.solution_ids)
    S, P = exp_U.shape
    base_borda_w = set(unc_report["expected_reference"]["borda_count"]["winner_ids"])
    base_minimax_w = set(unc_report["expected_reference"]["minimax"]["winner_ids"])
    base_weak_cond = set(unc_report["expected_reference"]["condorcet"]["weak_condorcet_winners"])

    borda_changed = 0
    minimax_changed = 0
    condorcet_emerged = 0
    loo_borda_winner_freq: Counter[str] = Counter()
    loo_minimax_winner_freq: Counter[str] = Counter()
    loo_weak_cond_freq: Counter[str] = Counter()

    if P > 1:
        for drop_col in range(P):
            keep_cols = [j for j in range(P) if j != drop_col]
            sub_U = exp_U[:, keep_cols]
            b_res = compute_borda_scores(sub_U, sol_ids, tol=tol)
            cm_res = compute_condorcet_minimax_metrics(sub_U, sol_ids, tol=tol, compute_smith=False)

            bw = set(b_res["winner_ids"])
            mw = set(cm_res["minimax"]["winner_ids"])
            wc = set(cm_res["condorcet"]["weak_condorcet_winners"])
            if bw != base_borda_w:
                borda_changed += 1
            if mw != base_minimax_w:
                minimax_changed += 1
            if wc and not base_weak_cond:
                condorcet_emerged += 1

            for sid in bw:
                loo_borda_winner_freq[sid] += 1
            for sid in mw:
                loo_minimax_winner_freq[sid] += 1
            for sid in wc:
                loo_weak_cond_freq[sid] += 1

    quota_ctx = small_n_quota_diagnostics(P, committee_size_reference)
    interval_stats = compute_interval_partial_order_stats(
        ensemble.min_scenario_matrix,
        ensemble.max_scenario_matrix,
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "contract_id": "voting_sensitivity_v1",
        "run_id": ensemble.run_id,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "ranked_as_participant": False,
        "cluster_weights_applied": False,
        "small_n_discreteness": quota_ctx,
        "single_ballot_leave_one_out_sensitivity": {
            "total_ballots_n": P,
            "single_ballot_weight_fraction": round(1.0 / max(1, P), 6),
            "borda_winner_set_changed_count": borda_changed,
            "borda_winner_set_preservation_rate": round((P - borda_changed) / max(1, P), 6),
            "borda_loo_winner_counts": dict(sorted(loo_borda_winner_freq.items(), key=lambda kv: (-kv[1], kv[0]))),
            "minimax_winner_set_changed_count": minimax_changed,
            "minimax_winner_set_preservation_rate": round((P - minimax_changed) / max(1, P), 6),
            "minimax_loo_winner_counts": dict(sorted(loo_minimax_winner_freq.items(), key=lambda kv: (-kv[1], kv[0]))),
            "condorcet_weak_winner_emerged_count": condorcet_emerged,
            "condorcet_loo_weak_winner_counts": dict(sorted(loo_weak_cond_freq.items(), key=lambda kv: (-kv[1], kv[0]))),
        },
        "partial_identification_interval_comparability": interval_stats,
        "weighting_sensitivity_winners": {
            k: {
                "borda_winners": v["borda_winners"],
                "minimax_winners": v["minimax_winners"],
                "weak_condorcet_winners": v["weak_condorcet_winners"],
            }
            for k, v in unc_report["weighting_sensitivity"].items()
        },
        "interpretation_sensitivity_summary": unc_report["probability_interpretation_sensitivity"],
        "partial_identification_sensitivity_summary": unc_report["partial_identification_sensitivity"],
        "derived_barycenter_sensitivity_summary": {
            k: {
                "scenario_origin": v["scenario_origin"],
                "borda_winners": v["borda_winners"],
                "minimax_winners": v["minimax_winners"],
                "strict_condorcet_winners": v["strict_condorcet_winners"],
                "has_condorcet_cycle": v["has_condorcet_cycle"],
            }
            for k, v in unc_report["derived_barycenter_scenarios"].items()
        },
    }
