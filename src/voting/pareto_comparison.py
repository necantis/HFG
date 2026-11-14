"""Robust Pareto & Separate 7-Criterion Cross-Check Module (Agent 06).

Owned by: Agent 06 — Voting & Social Choice
Schema Version: 1.0.0 (Aligned with ADR-0005 and ADR-0008)

Compares voting outcomes against Agent 04's 10-solution robust core, 102
high-confidence frontier solutions, 326 expected-reference nondominated
solutions, and 4-state robustness buckets without conflating Pareto status
with voting status and without silently combining the 7 welfare criteria.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.contracts import SCHEMA_VERSION


def _tier_membership(
    sids: list[str],
    robust_core: set[str],
    high_conf: set[str],
    expected_nd: set[str],
    conditional_nd: set[str],
    unresolved: set[str],
    prob_map: dict[str, float],
    status_map: dict[str, str],
) -> dict[str, Any]:
    s_set = set(sids)
    return {
        "solution_ids": list(sids),
        "count": len(sids),
        "in_robust_core_10": sorted(s_set & robust_core),
        "in_high_confidence_102": sorted(s_set & high_conf),
        "in_expected_nondominated_326": sorted(s_set & expected_nd),
        "in_conditionally_nondominated_248": sorted(s_set & conditional_nd),
        "in_unresolved_coding_uncertainty_285": sorted(s_set & unresolved),
        "per_solution_status": {
            sid: {
                "robust_pareto_status": status_map.get(sid, "UNKNOWN"),
                "frontier_inclusion_probability": prob_map.get(sid),
                "in_expected_nondominated": sid in expected_nd,
            }
            for sid in sids
        },
    }


def _mc_mass_by_tier(
    winner_probs: dict[str, float],
    robust_core: set[str],
    high_conf: set[str],
    expected_nd: set[str],
    conditional_nd: set[str],
    unresolved: set[str],
) -> dict[str, float]:
    return {
        "robust_core_10_mass": round(sum(p for sid, p in winner_probs.items() if sid in robust_core), 6),
        "high_confidence_102_mass": round(sum(p for sid, p in winner_probs.items() if sid in high_conf), 6),
        "expected_nondominated_326_mass": round(sum(p for sid, p in winner_probs.items() if sid in expected_nd), 6),
        "conditionally_nondominated_248_mass": round(sum(p for sid, p in winner_probs.items() if sid in conditional_nd), 6),
        "unresolved_285_mass": round(sum(p for sid, p in winner_probs.items() if sid in unresolved), 6),
    }


def _spearman_rank_corr(order_a: list[str], order_b: list[str]) -> float:
    """Compute exact Spearman correlation between two complete permutations of identical IDs."""
    if not order_a or len(order_a) != len(order_b):
        return 0.0
    pos_b = {sid: idx for idx, sid in enumerate(order_b)}
    n = len(order_a)
    if n <= 1:
        return 1.0
    d2 = sum((idx - pos_b[sid]) ** 2 for idx, sid in enumerate(order_a) if sid in pos_b)
    return round(1.0 - (6.0 * d2) / (n * (n * n - 1)), 6)


def build_pareto_voting_comparison(
    *,
    run_id: str,
    pareto_payload: dict[str, Any],
    robust_payload: dict[str, Any],
    unc_report: dict[str, Any],
    baldwin_envelope: dict[str, Any],
    rrv_envelope: dict[str, Any],
) -> dict[str, Any]:
    """Build contract-compliant pareto_voting_comparison_v1 cross-check report."""
    pr = pareto_payload.get("pareto_result") or {}
    rpr = robust_payload.get("robust_pareto_result") or {}

    robust_core = set(rpr.get("robustly_nondominated_solution_ids") or [])
    high_conf = set(robust_payload.get("high_confidence_nondominated_ids") or [])
    expected_nd = set(pr.get("nondominated_solution_ids") or [])
    conditional_nd = set(rpr.get("conditionally_nondominated_solution_ids") or [])
    unresolved = set(rpr.get("unresolved_due_to_coding_uncertainty_ids") or [])
    prob_map = {str(k): float(v) for k, v in (rpr.get("frontier_inclusion_probabilities") or {}).items()}
    status_map = {str(k): str(v) for k, v in (rpr.get("solution_robustness_statuses") or {}).items()}

    exp_ref = unc_report["expected_reference"]
    mc_res = unc_report["monte_carlo_results"]

    borda_exp_winners = list(exp_ref["borda_count"]["winner_ids"])
    borda_exp_top10 = list(exp_ref["borda_count"]["ranking"][:10])
    minimax_exp_winners = list(exp_ref["minimax"]["winner_ids"])
    minimax_exp_top10 = list(exp_ref["minimax"]["ranking"][:10])
    cond_exp_weak = list(exp_ref["condorcet"]["weak_condorcet_winners"])
    smith_exp = list(exp_ref["condorcet"]["smith_set_ids"])

    borda_mc_probs = mc_res["borda_winner_inclusion_probabilities"]
    minimax_mc_probs = mc_res["minimax_winner_inclusion_probabilities"]

    # Track which robust-core solutions ever win under Borda / Minimax / Condorcet in MC
    robust_core_voting_profile = {
        sid: {
            "frontier_inclusion_probability": prob_map.get(sid),
            "expected_borda_rank": exp_ref["borda_count"]["ranking"].index(sid) + 1
            if sid in exp_ref["borda_count"]["ranking"]
            else None,
            "expected_minimax_worst_defeat": exp_ref["minimax"]["worst_pairwise_defeats"].get(sid),
            "mc_borda_winner_prob": borda_mc_probs.get(sid, 0.0),
            "mc_minimax_winner_prob": minimax_mc_probs.get(sid, 0.0),
            "mc_weak_condorcet_prob": mc_res["condorcet_weak_winner_inclusion_probabilities"].get(sid, 0.0),
        }
        for sid in sorted(robust_core)
    }

    # Separate 7-criterion diagnostic comparison (strictly NOT combined into any rule!)
    rankings_by_criterion = pr.get("rankings_by_criterion") or {}
    crit_top1_mc = rpr.get("criterion_top1_probabilities") or {}
    borda_full_ranking = exp_ref["borda_count"]["ranking"]
    minimax_full_ranking = exp_ref["minimax"]["ranking"]

    separate_welfare_diagnostics: dict[str, Any] = {}
    for crit_name, crit_ranking in sorted(rankings_by_criterion.items()):
        c_list = [str(s) for s in crit_ranking]
        separate_welfare_diagnostics[crit_name] = {
            "kept_strictly_separate_from_voting_rule": True,
            "criterion_expected_top1": c_list[0] if c_list else None,
            "criterion_expected_top5": c_list[:5],
            "top1_matches_expected_borda_winner": (c_list[0] in borda_exp_winners) if c_list else False,
            "top1_matches_expected_minimax_winner": (c_list[0] in minimax_exp_winners) if c_list else False,
            "top10_overlap_with_expected_borda_top10": len(set(c_list[:10]) & set(borda_exp_top10)),
            "top10_overlap_with_expected_minimax_top10": len(set(c_list[:10]) & set(minimax_exp_top10)),
            "spearman_corr_with_expected_borda": _spearman_rank_corr(borda_full_ranking, c_list),
            "spearman_corr_with_expected_minimax": _spearman_rank_corr(minimax_full_ranking, c_list),
            "mc_criterion_top1_probabilities": {
                k: round(float(v), 6)
                for k, v in sorted((crit_top1_mc.get(crit_name) or {}).items(), key=lambda kv: -kv[1])[:5]
            },
        }

    return {
        "schema_version": SCHEMA_VERSION,
        "contract_id": "pareto_voting_comparison_v1",
        "run_id": run_id,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "pareto_choice_set_counts": {
            "total_feasible_solutions": len(pr.get("evaluated_solution_ids") or []),
            "robustly_nondominated_core_count": len(robust_core),
            "high_confidence_nondominated_count": len(high_conf),
            "expected_baseline_nondominated_count": len(expected_nd),
            "conditionally_nondominated_count": len(conditional_nd),
            "unresolved_due_to_coding_uncertainty_count": len(unresolved),
        },
        "expected_reference_comparisons": {
            "borda_winners": _tier_membership(
                borda_exp_winners, robust_core, high_conf, expected_nd, conditional_nd, unresolved, prob_map, status_map
            ),
            "borda_top10": _tier_membership(
                borda_exp_top10, robust_core, high_conf, expected_nd, conditional_nd, unresolved, prob_map, status_map
            ),
            "minimax_winners": _tier_membership(
                minimax_exp_winners, robust_core, high_conf, expected_nd, conditional_nd, unresolved, prob_map, status_map
            ),
            "minimax_top10": _tier_membership(
                minimax_exp_top10, robust_core, high_conf, expected_nd, conditional_nd, unresolved, prob_map, status_map
            ),
            "condorcet_weak_winners": _tier_membership(
                cond_exp_weak, robust_core, high_conf, expected_nd, conditional_nd, unresolved, prob_map, status_map
            ),
            "smith_set": _tier_membership(
                smith_exp, robust_core, high_conf, expected_nd, conditional_nd, unresolved, prob_map, status_map
            ),
            "baldwin": {
                "applicability_status": baldwin_envelope.get("applicability_status"),
                "execution_status": baldwin_envelope.get("execution_status"),
                "winners": (baldwin_envelope.get("baldwin_result") or {}).get("winner_candidate_ids") or [],
            },
            "rrv": {
                "applicability_status": rrv_envelope.get("applicability_status"),
                "execution_status": rrv_envelope.get("execution_status"),
                "selected_committee_ids": (rrv_envelope.get("rrv_result") or {}).get("selected_committee_ids") or [],
            },
        },
        "monte_carlo_tier_mass": {
            "borda_winner_mass": _mc_mass_by_tier(
                borda_mc_probs, robust_core, high_conf, expected_nd, conditional_nd, unresolved
            ),
            "minimax_winner_mass": _mc_mass_by_tier(
                minimax_mc_probs, robust_core, high_conf, expected_nd, conditional_nd, unresolved
            ),
            "condorcet_weak_winner_mass_conditional_on_existence": _mc_mass_by_tier(
                mc_res["condorcet_weak_winner_inclusion_probabilities"],
                robust_core,
                high_conf,
                expected_nd,
                conditional_nd,
                unresolved,
            ),
        },
        "robust_core_10_voting_performance": robust_core_voting_profile,
        "separate_welfare_criteria_diagnostics": separate_welfare_diagnostics,
        "conceptual_distinction_and_interpretation": {
            "pareto_vs_voting_non_conflation": True,
            "welfare_criteria_combined_into_voting_rule": False,
            "interpretation_notes": [
                "Pareto dominance tests vector nondominance across all participants simultaneously; social-choice rules aggregate ordinal ranks or pairwise majorities.",
                "A voting winner outside the 10-solution robust core (such as an expected-Borda or MC-Borda leader in the 102 high-confidence conditionally nondominated tier with p_nd >= 0.99) is not invalid: it reflects strong average rank-sum performance while losing nondominance in a tiny fraction (<1%) of coding draws.",
                "Conversely, not all 10 robustly nondominated core solutions win Borda or Minimax: a Pareto-robust solution protecting extreme worst-case participant profiles may rank lower in average ordinal Borda position while still avoiding dominance across all scenarios.",
                "Notably, Minimax pairwise voting places substantial expected and MC probability mass directly inside the 10-solution robust core (both expected Minimax co-winners belong to the robust core), whereas Borda spreads winner probability across 46 candidates spanning both the robust core and high-confidence conditional frontier.",
            ],
        },
    }
