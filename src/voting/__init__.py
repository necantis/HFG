"""Agent 06 — Social Choice, Voting & Collective-Choice Robustness Package.

Owned by: Agent 06 — Voting & Social Choice
Schema Version: 1.0.0 (Aligned with ADR-0005, ADR-0007, and ADR-0008)

Evaluates collective choice over Agent 04's validated feasible governance
solutions using repository-authorized social-choice rules (Borda count,
Condorcet / Minimax, plus conditional Baldwin and RRV gated on strict active
ballot validation), full ADR-0008 uncertainty propagation, Robust Pareto
cross-checks, and explicit small-N (N=11) discreteness diagnostics.
"""

from src.voting.pareto_comparison import build_pareto_voting_comparison
from src.voting.pipeline import run_agent_06_pipeline
from src.voting.social_choice import (
    compute_borda_scores,
    compute_condorcet_minimax_metrics,
    compute_interval_partial_order_stats,
    compute_small_n_sensitivity,
    propagate_social_choice_uncertainty,
)
from src.voting.validation import validate_agent_06_inputs
from src.voting.voting_baldwin import evaluate_baldwin_voting, validate_baldwin_ballot_file
from src.voting.voting_rrv import evaluate_rrv_voting, validate_rrv_ballot_file

__all__ = [
    "build_pareto_voting_comparison",
    "compute_borda_scores",
    "compute_condorcet_minimax_metrics",
    "compute_interval_partial_order_stats",
    "compute_small_n_sensitivity",
    "evaluate_baldwin_voting",
    "evaluate_rrv_voting",
    "propagate_social_choice_uncertainty",
    "run_agent_06_pipeline",
    "validate_agent_06_inputs",
    "validate_baldwin_ballot_file",
    "validate_rrv_ballot_file",
]
