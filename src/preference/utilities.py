"""Interpretation-Aware, Uncertainty-Propagating Participant Utility Engine (ADR-0008).

Owned by: Agent 04 — Preference, Utility & Pareto
Schema Version: 1.0.0 (Aligned with ADR-0005, ADR-0008, and ISSUE-005)

Derives ParticipantUtility strictly from PreferenceMatrix (Q01-Q13 primary cells;
Q14 strictly isolated). Never uses coder_confidence as a preference or utility
weight. Preserves all 7 UncertaintyClass types, discrete coder scenarios P_i={p_A,p_B},
ISSUE-005 probability interpretations, single-coder partial ID without 0.0-fill,
double-count guards, NO_VALID_CROSSWALK disjoint hypotheses, and PARTIAL_CROSSWALK
residual mass bounds.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from src.contracts import (
    CrosswalkStatus,
    DerivedScenarioOrigin,
    GovernanceSolution,
    MissingnessState,
    ParticipantUtility,
    PreferenceCell,
    PreferenceMatrix,
    ProbabilityInterpretation,
    ProvenanceMeta,
    SCHEMA_VERSION,
    UncertaintyClass,
)
from src.preference.preference_matrix import PRIMARY_QUESTION_IDS, compute_sha256


@dataclass
class CellSolutionBounds:
    """Deterministic and stochastic alignment components for one usable cell across solutions."""

    cell: PreferenceCell
    double_count_guard: bool
    is_omission_partial_id: bool
    is_granularity_partial_id: bool
    is_no_valid_crosswalk: bool
    is_partial_crosswalk: bool
    has_conditional_operator: bool
    has_unresolved_operator_flag: bool
    #Coder-A & Coder-B aligned option spaces & discrete/mixed values over solutions (shape (S,))
    coder_a_expected: np.ndarray | None
    coder_a_mixed: np.ndarray | None
    coder_a_min: np.ndarray | None
    coder_a_max: np.ndarray | None
    coder_a_keys: list[str]
    coder_a_probs: np.ndarray | None
    coder_a_sol_vecs: np.ndarray | None  # shape (K_a, S)
    coder_b_expected: np.ndarray | None
    coder_b_mixed: np.ndarray | None
    coder_b_min: np.ndarray | None
    coder_b_max: np.ndarray | None
    coder_b_keys: list[str]
    coder_b_probs: np.ndarray | None
    coder_b_sol_vecs: np.ndarray | None  # shape (K_b, S)
    # Crosswalk canonical / partial residual bounds over solutions
    unmapped_residual_a: float
    unmapped_residual_b: float
    min_align: np.ndarray  # deterministic lower alignment across all admissible coding resolutions (S,)
    max_align: np.ndarray  # deterministic upper alignment across all admissible coding resolutions (S,)
    hinges_on_coding_gap: bool  # True if dominance uncertainty originates from NO_VALID_CROSSWALK / SINGLE_CODER / CONDITIONAL / PARTIAL_CROSSWALK


@dataclass
class UtilityEnsembleSummary:
    """Complete ParticipantUtility output plus precomputed scenario tensors for RobustParetoEngine."""

    run_id: str
    matrix_id: str
    participant_ids: list[str]
    valid_participant_ids: list[str]
    excluded_all_missing_participant_ids: list[str]
    solution_ids: list[str]
    question_ids_evaluated: list[str]
    participant_utilities: list[ParticipantUtility]
    # Arrays shaped (S, P_valid)
    expected_utility_matrix: np.ndarray
    uniform_subtopic_utility_matrix: np.ndarray
    uniform_question_utility_matrix: np.ndarray
    ci_lower_matrix: np.ndarray
    ci_upper_matrix: np.ndarray
    min_scenario_matrix: np.ndarray
    max_scenario_matrix: np.ndarray
    # Arrays for exact dominance sign & coding-gap decomposition (S, P_valid)
    min_coding_gap_matrix: np.ndarray
    max_coding_gap_matrix: np.ndarray
    coupled_gap_corner_matrices: dict[str, np.ndarray]
    # Monte Carlo draws tensor (D, S, P_valid) and metadata
    mc_draws_utilities: np.ndarray
    mc_draw_regimes: list[dict[str, Any]]
    # Derived sensitivity utility matrices (strictly labeled DERIVED_ROBUSTNESS_*)
    derived_barycenter_matrices: dict[str, np.ndarray]
    # Operator diagnostics
    interpretation_operator_audit: dict[str, Any]
    participant_diagnostics: dict[str, dict[str, Any]]
    question_diagnostics: dict[str, dict[str, Any]]


def _extract_solution_subtopic_alignment(
    sol: GovernanceSolution,
    subtopic_id: str,
    dist: dict[str, float],
    crosswalk_map: dict[str, str] | None,
    coder_side: str,
    crosswalk_status: CrosswalkStatus | None,
) -> tuple[list[str], np.ndarray, np.ndarray, float, bool]:
    """Map a coder distribution onto a GovernanceSolution's posture vector cleanly.

    Returns:
      keys_ordered: aligned/raw option keys
      p_vec: probability vector over keys_ordered summing to 1.0
      sol_align_per_key: solution's posture weight in [0, 1] for each key
      unmapped_residual_mass: probability mass without a mapped solution axis
      unmapped_crosswalk_flag: True if solution lacks posture on a NO_VALID_CROSSWALK coder axis
    """
    sol_prof = sol.global_alternative_profile.get(subtopic_id) or {}
    # Check whether crosswalk maps raw keys -> canonical keys
    mapped_probs: dict[str, float] = defaultdict(float)
    unmapped_keys: dict[str, float] = {}

    if crosswalk_map and crosswalk_status != CrosswalkStatus.NO_VALID_CROSSWALK:
        for raw_k, prob in dist.items():
            if raw_k in crosswalk_map:
                mapped_probs[crosswalk_map[raw_k]] += float(prob)
            else:
                unmapped_keys[raw_k] = float(prob)
    else:
        for raw_k, prob in dist.items():
            if crosswalk_status == CrosswalkStatus.NO_VALID_CROSSWALK:
                unmapped_keys[raw_k] = float(prob)
            else:
                mapped_probs[raw_k] += float(prob)

    # Evaluate solution's posture on canonical + coder-qualified keys
    keys_ordered: list[str] = []
    p_vals: list[float] = []
    sol_vals: list[float] = []
    unmapped_mass = 0.0
    unmapped_cw_flag = False

    # 1. Mapped / comparable keys
    for k, prob in sorted(mapped_probs.items()):
        keys_ordered.append(k)
        p_vals.append(prob)
        if k in sol_prof:
            sol_vals.append(float(sol_prof[k]))
        elif f"{coder_side}:{k}" in sol_prof:
            sol_vals.append(float(sol_prof[f"{coder_side}:{k}"]))
        elif sol_prof:
            # Solution explicitly chose an alternative within this subtopic other than k -> 0.0 match
            sol_vals.append(0.0)
        else:
            sol_vals.append(0.0)
            unmapped_mass += prob

    # 2. Unmapped residual / disjoint keys (PARTIAL_CROSSWALK or NO_VALID_CROSSWALK or SINGLE_CODER)
    has_side_posture = any(k.startswith(f"{coder_side}:") for k in sol_prof)
    for raw_k, prob in sorted(unmapped_keys.items()):
        qual_k = f"{coder_side}:{raw_k}"
        keys_ordered.append(qual_k)
        p_vals.append(prob)
        if qual_k in sol_prof:
            sol_vals.append(float(sol_prof[qual_k]))
        elif raw_k in sol_prof:
            sol_vals.append(float(sol_prof[raw_k]))
        elif crosswalk_status == CrosswalkStatus.NO_VALID_CROSSWALK:
            if has_side_posture:
                # Solution commits to the opposite option on this coder's disjoint axis
                sol_vals.append(0.0)
            else:
                # Solution is uncommitted on this unaligned coder axis -> partial identification gap
                sol_vals.append(np.nan)
                unmapped_mass += prob
                unmapped_cw_flag = True
        elif crosswalk_status == CrosswalkStatus.PARTIAL_CROSSWALK:
            # Unmapped residual under PARTIAL_CROSSWALK
            if has_side_posture or any(not kk.startswith("coder_") for kk in sol_prof):
                # Residual key not resolved onto coarse/canonical key
                sol_vals.append(np.nan)
                unmapped_mass += prob
            else:
                sol_vals.append(0.0)
                unmapped_mass += prob
        else:
            sol_vals.append(0.0)

    return (
        keys_ordered,
        np.asarray(p_vals, dtype=np.float64),
        np.asarray(sol_vals, dtype=np.float64),
        float(unmapped_mass),
        unmapped_cw_flag,
    )


def _compute_alignment_metrics(
    p_vec: np.ndarray,
    sol_mat: np.ndarray,  # shape (K, S), may contain NaN for unmapped residual keys
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Compute (expected_align, mixed_overlap_align, min_align, max_align) of shape (S,)."""
    nan_mask = np.isnan(sol_mat)
    # Conservative imputation ONLY for bounded min/max envelope tracking
    sol_lo = np.where(nan_mask, 0.0, np.clip(sol_mat, 0.0, 1.0))
    sol_hi = np.where(nan_mask, 1.0, np.clip(sol_mat, 0.0, 1.0))

    # Expected alignment: sum_k p_k * alpha_k(s)
    exp_mid = (p_vec[:, None] * (0.5 * (sol_lo + sol_hi))).sum(axis=0)
    # Mixed portfolio overlap (1 - TVD = sum_k min(p_k, alpha_k(s))) on normalized posture when finite
    # Notice: when a subtopic posture sums <= 1.0 across mapped keys, min(p_k, alpha_k) measures exact portfolio overlap
    sol_mid = 0.5 * (sol_lo + sol_hi)
    # Normalize sol_mid only when positive and > 1.0 to keep valid probability comparison
    col_sums = np.maximum(1.0, sol_mid.sum(axis=0, keepdims=True))
    sol_mid_norm = sol_mid / col_sums
    mixed_align = np.minimum(p_vec[:, None], sol_mid_norm).sum(axis=0)

    # Min/Max across support realizations and unmapped residual ambiguity:
    # Under discrete epistemic choice over support of p_vec (p_k > 1e-6), nature could pick argmin/argmax k
    active_k = p_vec > 1e-6
    if active_k.any():
        lo_support = sol_lo[active_k].min(axis=0)
        hi_support = sol_hi[active_k].max(axis=0)
    else:
        lo_support = np.zeros(sol_mat.shape[1], dtype=np.float64)
        hi_support = np.ones(sol_mat.shape[1], dtype=np.float64)
    return exp_mid, mixed_align, lo_support, hi_support


class ParticipantUtilityEngine:
    """Compute interpretation-aware, uncertainty-propagated utilities from PreferenceMatrix."""

    def __init__(self, base_dir: Path | str, run_id: str = "run_20261111_002") -> None:
        self.base_dir = Path(base_dir).resolve()
        self.run_id = run_id

    def _build_cell_solution_bounds(
        self,
        cell: PreferenceCell,
        solutions: list[GovernanceSolution],
    ) -> CellSolutionBounds:
        sid = cell.canonical_subtopic_id or cell.subtopic_id
        pus = cell.preference_uncertainty_set
        cw = cell.canonical_alternative_crosswalk
        cw_status = cw.crosswalk_status if cw else None
        uc = cell.uncertainty_class

        is_omission = uc == UncertaintyClass.SINGLE_CODER_PARTIAL_ID_OMISSION
        is_granularity = uc == UncertaintyClass.SINGLE_CODER_PARTIAL_ID_GRANULARITY
        is_no_cw = cw_status == CrosswalkStatus.NO_VALID_CROSSWALK
        is_partial_cw = cw_status == CrosswalkStatus.PARTIAL_CROSSWALK
        double_guard = bool(pus.double_count_guard_applied) if pus else False

        interps = set(pus.interpretation_variants if pus else [])
        if cell.coder_a_probability_interpretation:
            interps.add(cell.coder_a_probability_interpretation)
        if cell.coder_b_probability_interpretation:
            interps.add(cell.coder_b_probability_interpretation)
        has_cond = "conditional_or_context_dependent" in interps
        # Conditional operator lacks a formal machine-evaluated AST predicate in upstream coder output
        has_unresolved_op = has_cond

        S = len(solutions)

        def _side_arrays(side: str, dist: dict[str, float] | None, cw_map: dict[str, str] | None):
            if dist is None:
                return None, None, None, None, [], None, None, 0.0, False
            keys_ref: list[str] = []
            p_ref: np.ndarray | None = None
            sol_cols: list[np.ndarray] = []
            res_max = 0.0
            unmapped_any = False

            # Collect union of keys across solutions cleanly
            first_keys, p0, _, _, _ = _extract_solution_subtopic_alignment(
                solutions[0], sid, dist, cw_map, side, cw_status
            )
            keys_ref = first_keys
            p_ref = p0
            sol_mat = np.zeros((len(keys_ref), S), dtype=np.float64)
            for s_idx, sol in enumerate(solutions):
                ks, _, sv, r_mass, u_flag = _extract_solution_subtopic_alignment(
                    sol, sid, dist, cw_map, side, cw_status
                )
                if ks != keys_ref:
                    raise RuntimeError(f"Key ordering mismatch across solutions for {cell.cell_id}: {ks} vs {keys_ref}")
                sol_mat[:, s_idx] = sv
                res_max = max(res_max, r_mass)
                unmapped_any = unmapped_any or u_flag
            exp_m, mix_m, lo_m, hi_m = _compute_alignment_metrics(p_ref, sol_mat)
            return exp_m, mix_m, lo_m, hi_m, keys_ref, p_ref, sol_mat, res_max, unmapped_any

        cw_a = cw.coder_a_to_canonical if cw else None
        cw_b = cw.coder_b_to_canonical if cw else None

        (
            a_exp, a_mix, a_lo, a_hi, a_keys, a_p, a_mat, res_a, u_a
        ) = _side_arrays("coder_a", cell.coder_a_distribution, cw_a)
        (
            b_exp, b_mix, b_lo, b_hi, b_keys, b_p, b_mat, res_b, u_b
        ) = _side_arrays("coder_b", cell.coder_b_distribution, cw_b)

        # Deterministic lower & upper alignment over all admissible realizations for this cell
        candidates_lo: list[np.ndarray] = []
        candidates_hi: list[np.ndarray] = []
        if a_exp is not None and a_mix is not None and a_lo is not None and a_hi is not None:
            if (
                cell.coder_a_probability_interpretation == "explicit_mixed_preference"
                and uc == UncertaintyClass.NONE_CONSENSUS
            ):
                candidates_lo.append(a_mix)
                candidates_hi.append(a_mix)
            elif uc in (UncertaintyClass.NONE_CONSENSUS, UncertaintyClass.INTERPRETATION_DIVERGENCE):
                # Under NONE_CONSENSUS with epistemic uncertainty (p_max < 1), realized choice vs expected?
                # Note: For deterministic scenario bounds, if p is deterministic (p_max >= 0.999) both equal exp=mix;
                # if interior epistemic uncertainty exists, discrete support bounds span [a_lo, a_hi].
                if a_p is not None and float(a_p.max()) >= 1.0 - 1e-4:
                    candidates_lo.append(a_exp)
                    candidates_hi.append(a_exp)
                else:
                    candidates_lo.append(np.minimum(a_lo, a_mix))
                    candidates_hi.append(np.maximum(a_hi, a_mix))
            else:
                candidates_lo.append(np.minimum(a_lo, a_mix))
                candidates_hi.append(np.maximum(a_hi, a_mix))

        if b_exp is not None and b_mix is not None and b_lo is not None and b_hi is not None:
            if (
                cell.coder_b_probability_interpretation == "explicit_mixed_preference"
                and uc == UncertaintyClass.NONE_CONSENSUS
            ):
                candidates_lo.append(b_mix)
                candidates_hi.append(b_mix)
            elif b_p is not None and float(b_p.max()) >= 1.0 - 1e-4 and uc in (
                UncertaintyClass.NONE_CONSENSUS, UncertaintyClass.INTERPRETATION_DIVERGENCE
            ):
                candidates_lo.append(b_exp)
                candidates_hi.append(b_exp)
            else:
                candidates_lo.append(np.minimum(b_lo, b_mix))
                candidates_hi.append(np.maximum(b_hi, b_mix))

        if not candidates_lo:
            raise ValueError(f"Usable cell {cell.cell_id} produced no active coder alignment arrays.")

        min_align = np.min(np.vstack(candidates_lo), axis=0)
        max_align = np.max(np.vstack(candidates_hi), axis=0)

        # Conditional cells bracket over full conditional regime unless deterministic singleton
        if has_cond:
            min_align = np.minimum(min_align, np.min(np.vstack(candidates_lo), axis=0))
            max_align = np.maximum(max_align, np.max(np.vstack(candidates_hi), axis=0))

        hinges_on_gap = bool(
            is_no_cw
            or is_partial_cw
            or is_omission
            or has_cond
            or u_a
            or u_b
            or res_a > 1e-6
            or res_b > 1e-6
        )

        return CellSolutionBounds(
            cell=cell,
            double_count_guard=double_guard,
            is_omission_partial_id=is_omission,
            is_granularity_partial_id=is_granularity,
            is_no_valid_crosswalk=is_no_cw,
            is_partial_crosswalk=is_partial_cw,
            has_conditional_operator=has_cond,
            has_unresolved_operator_flag=has_unresolved_op,
            coder_a_expected=a_exp,
            coder_a_mixed=a_mix,
            coder_a_min=a_lo,
            coder_a_max=a_hi,
            coder_a_keys=a_keys,
            coder_a_probs=a_p,
            coder_a_sol_vecs=a_mat,
            coder_b_expected=b_exp,
            coder_b_mixed=b_mix,
            coder_b_min=b_lo,
            coder_b_max=b_hi,
            coder_b_keys=b_keys,
            coder_b_probs=b_p,
            coder_b_sol_vecs=b_mat,
            unmapped_residual_a=res_a,
            unmapped_residual_b=res_b,
            min_align=min_align,
            max_align=max_align,
            hinges_on_coding_gap=hinges_on_gap,
        )

    def evaluate(
        self,
        matrix: PreferenceMatrix,
        solutions: list[GovernanceSolution],
        mc_config: dict[str, Any],
        *,
        config_hash: str = "",
    ) -> UtilityEnsembleSummary:
        """Compute exact scenario-set and Monte Carlo ParticipantUtility ensemble."""
        rng = np.random.default_rng(int(mc_config.get("random_seed", 42)))
        n_draws = int(mc_config.get("monte_carlo_draws", 1000))
        veto_threshold = float(mc_config.get("veto_threshold", 0.35))
        weight_sigma = float(mc_config.get("weight_perturbation_sigma", 0.15))
        partial_overlap_modes = [float(x) for x in mc_config.get("partial_overlap_weight_modes", [0.5, 1.0])]
        bary_lambdas = [float(x) for x in mc_config.get("derived_barycenter_lambdas", [0.25, 0.5, 0.75])]
        bary_enabled = bool(mc_config.get("derived_convex_hull_sweep_enabled", True))

        # Strictly isolate Q01-Q13 primary cells from Q14 contextual remarks
        primary_cells = [c for c in matrix.cells if c.question_id in PRIMARY_QUESTION_IDS]
        usable_primary = [c for c in primary_cells if c.missingness_state.is_usable()]

        all_pids = list(matrix.participant_ids)
        usable_by_pid: dict[str, list[PreferenceCell]] = defaultdict(list)
        all_primary_by_pid: dict[str, list[PreferenceCell]] = defaultdict(list)
        for c in primary_cells:
            all_primary_by_pid[c.participant_id].append(c)
            if c.missingness_state.is_usable():
                usable_by_pid[c.participant_id].append(c)

        valid_pids = [p for p in all_pids if len(usable_by_pid[p]) > 0]
        excluded_pids = [p for p in all_pids if len(usable_by_pid[p]) == 0]

        S = len(solutions)
        P_valid = len(valid_pids)
        sol_ids = [s.solution_id for s in solutions]
        pid_to_idx = {p: idx for idx, p in enumerate(valid_pids)}

        # Precompute cell-level solution bounds once (C_usable, S)
        cell_bounds: list[CellSolutionBounds] = [
            self._build_cell_solution_bounds(c, solutions) for c in usable_primary
        ]
        C = len(cell_bounds)

        # Indices of usable cells grouped by participant
        pid_cell_indices: dict[str, list[int]] = defaultdict(list)
        for idx, cb in enumerate(cell_bounds):
            pid_cell_indices[cb.cell.participant_id].append(idx)

        # Build baseline expected alignment & importance matrices (no coder_confidence EVER!)
        # For each cell c: nominal coder weights w_a, w_b from semantic_importance ONLY
        base_exp_align = np.zeros((C, S), dtype=np.float64)
        base_w_sem = np.zeros(C, dtype=np.float64)
        base_w_unif_sub = np.ones(C, dtype=np.float64)
        base_w_unif_q = np.zeros(C, dtype=np.float64)
        min_align_mat = np.zeros((C, S), dtype=np.float64)
        max_align_mat = np.zeros((C, S), dtype=np.float64)

        # Count usable subtopics per (pid, qid) for uniform-question weighting sensitivity
        usable_per_pq: dict[tuple[str, str], int] = defaultdict(int)
        for cb in cell_bounds:
            usable_per_pq[(cb.cell.participant_id, cb.cell.question_id)] += 1

        for idx, cb in enumerate(cell_bounds):
            c = cb.cell
            min_align_mat[idx] = cb.min_align
            max_align_mat[idx] = cb.max_align

            # Reference alignment (neutral unweighted mean across observed scenarios ONLY for baseline summary;
            # never stored back onto PreferenceCell.resolved_point_distribution and never using coder_confidence!)
            a_ref = (
                cb.coder_a_mixed
                if (cb.coder_a_mixed is not None and c.coder_a_probability_interpretation == "explicit_mixed_preference")
                else cb.coder_a_expected
            )
            b_ref = (
                cb.coder_b_mixed
                if (cb.coder_b_mixed is not None and c.coder_b_probability_interpretation == "explicit_mixed_preference")
                else cb.coder_b_expected
            )
            if a_ref is not None and b_ref is not None:
                base_exp_align[idx] = 0.5 * (a_ref + b_ref)
            elif a_ref is not None:
                base_exp_align[idx] = a_ref
            elif b_ref is not None:
                base_exp_align[idx] = b_ref

            # Normalized semantic importance (from semantic_importance_a/b, zero coder_confidence!)
            imp_vals = [v for v in (c.semantic_importance_a, c.semantic_importance_b) if v is not None]
            imp = (sum(imp_vals) / len(imp_vals)) if imp_vals else 0.5
            guard_mult = 0.5 if cb.double_count_guard else 1.0
            base_w_sem[idx] = max(0.05, imp) * guard_mult
            base_w_unif_sub[idx] = 1.0 * guard_mult
            n_pq = max(1, usable_per_pq[(c.participant_id, c.question_id)])
            base_w_unif_q[idx] = (1.0 / n_pq)

        def _aggregate_by_participant(align_mat: np.ndarray, weights_vec: np.ndarray) -> np.ndarray:
            """Return (S, P_valid) matrix."""
            out = np.zeros((S, P_valid), dtype=np.float64)
            for p_idx, pid in enumerate(valid_pids):
                c_idxs = pid_cell_indices[pid]
                w = weights_vec[c_idxs]
                w_sum = float(w.sum())
                if w_sum <= 1e-12:
                    out[:, p_idx] = align_mat[c_idxs].mean(axis=0)
                else:
                    out[:, p_idx] = (w[:, None] * align_mat[c_idxs]).sum(axis=0) / w_sum
            return out

        exp_u_mat = _aggregate_by_participant(base_exp_align, base_w_sem)
        unif_sub_u_mat = _aggregate_by_participant(base_exp_align, base_w_unif_sub)
        unif_q_u_mat = _aggregate_by_participant(base_exp_align, base_w_unif_q)

        # Deterministic min/max scenario utilities (AND separate min/max on non-gap vs coding-gap bounds)
        # Note: For SINGLE_CODER_PARTIAL_ID_OMISSION, lower/upper structural weight in [0, 1] shifts participant mean
        # smoothly between leaving the cell omitted (w=0) vs included at semantic importance w>0.
        # Compute exact min/max over omission inclusion {0, 1} and partial-overlap guard {0.5, 1.0} per participant!
        min_scen_mat = np.zeros((S, P_valid), dtype=np.float64)
        max_scen_mat = np.zeros((S, P_valid), dtype=np.float64)
        min_gap_mat = np.zeros((S, P_valid), dtype=np.float64)
        max_gap_mat = np.zeros((S, P_valid), dtype=np.float64)

        for p_idx, pid in enumerate(valid_pids):
            c_idxs = pid_cell_indices[pid]
            c_list = [cell_bounds[i] for i in c_idxs]
            # Base weights under guard modes 0.5 vs 1.0 for partial-overlap, and 0/1 for omission
            w_base = np.array(
                [max(0.05, cb.cell.semantic_importance or 0.5) for cb in c_list],
                dtype=np.float64,
            )
            is_omit = np.array([cb.is_omission_partial_id for cb in c_list], dtype=bool)
            is_guard = np.array([cb.double_count_guard for cb in c_list], dtype=bool)
            is_gap = np.array([cb.hinges_on_coding_gap for cb in c_list], dtype=bool)

            lo_c = np.vstack([cb.min_align for cb in c_list])  # (Cp, S)
            hi_c = np.vstack([cb.max_align for cb in c_list])  # (Cp, S)

            # Exact minimum weighted average with box weights w_i in [w_lo_i, w_hi_i]
            # (solved via greedy ranking per solution column in O(Cp log Cp), zero heuristics!):
            w_lo = np.where(is_omit, 0.0, np.where(is_guard, 0.5 * w_base, w_base))
            w_hi = w_base.copy()
            # Keep non-omission at least positive so denominator > 0
            for s_idx in range(S):
                # Minimize sum(w_i * lo_i) / sum(w_i): sort ascending by lo_i, assign w_hi to smallest below threshold
                order_min = np.argsort(lo_c[:, s_idx])
                w_cur = w_lo.copy()
                if w_cur.sum() <= 1e-12:
                    w_cur = w_hi.copy()
                cur_val = float((w_cur * lo_c[:, s_idx]).sum() / w_cur.sum())
                for k_i in order_min:
                    if lo_c[k_i, s_idx] < cur_val and w_hi[k_i] > w_cur[k_i]:
                        w_cur[k_i] = w_hi[k_i]
                        cur_val = float((w_cur * lo_c[:, s_idx]).sum() / w_cur.sum())
                min_scen_mat[s_idx, p_idx] = cur_val

                # Maximize sum(w_i * hi_i) / sum(w_i): sort descending by hi_i
                order_max = np.argsort(-hi_c[:, s_idx])
                w_cur_max = w_lo.copy()
                if w_cur_max.sum() <= 1e-12:
                    w_cur_max = w_hi.copy()
                cur_max = float((w_cur_max * hi_c[:, s_idx]).sum() / w_cur_max.sum())
                for k_i in order_max:
                    if hi_c[k_i, s_idx] > cur_max and w_hi[k_i] > w_cur_max[k_i]:
                        w_cur_max[k_i] = w_hi[k_i]
                        cur_max = float((w_cur_max * hi_c[:, s_idx]).sum() / w_cur_max.sum())
                max_scen_mat[s_idx, p_idx] = cur_max

            # Also track pure coding-gap interval isolating ONLY cells with hinges_on_coding_gap=False fixed at exp
            # vs coding-gap cells allowed to span [lo_c, hi_c] and omission weights in [0, w_base]
            fixed_mid = np.vstack([base_exp_align[i] for i in c_idxs])
            lo_gap_only = np.where(is_gap[:, None], lo_c, fixed_mid)
            hi_gap_only = np.where(is_gap[:, None], hi_c, fixed_mid)
            w_no_omit = np.where(is_guard, 0.5 * w_base, w_base)
            w_g_lo = np.where(is_omit, 0.0, w_no_omit)
            for s_idx in range(S):
                # Gap min
                w_cur = w_g_lo.copy()
                cur_val = float((w_cur * lo_gap_only[:, s_idx]).sum() / max(1e-12, w_cur.sum()))
                for k_i in np.argsort(lo_gap_only[:, s_idx]):
                    if lo_gap_only[k_i, s_idx] < cur_val and w_no_omit[k_i] > w_cur[k_i]:
                        w_cur[k_i] = w_no_omit[k_i]
                        cur_val = float((w_cur * lo_gap_only[:, s_idx]).sum() / w_cur.sum())
                min_gap_mat[s_idx, p_idx] = cur_val
                # Gap max
                w_cur_m = w_g_lo.copy()
                cur_m = float((w_cur_m * hi_gap_only[:, s_idx]).sum() / max(1e-12, w_cur_m.sum()))
                for k_i in np.argsort(-hi_gap_only[:, s_idx]):
                    if hi_gap_only[k_i, s_idx] > cur_m and w_no_omit[k_i] > w_cur_m[k_i]:
                        w_cur_m[k_i] = w_no_omit[k_i]
                        cur_m = float((w_cur_m * hi_gap_only[:, s_idx]).sum() / w_cur_m.sum())
                max_gap_mat[s_idx, p_idx] = cur_m

        # ------------------------------------------------------------------
        # Monte Carlo ADR-0008 Propagation (D draws from pareto_mc_config.json)
        # ------------------------------------------------------------------
        mc_utils = np.zeros((n_draws, S, P_valid), dtype=np.float64)
        mc_regimes: list[dict[str, Any]] = []

        # Precompute mapping indices for fast vectorized draw sampling
        p_idx_groups = [np.array(pid_cell_indices[pid], dtype=np.int64) for pid in valid_pids]

        for d in range(n_draws):
            # Regime switches recorded explicitly per draw for CONDITIONALLY_NONDOMINATED provenance
            coder_regime = "MIXED_INDEPENDENT_CODER_SAMPLING"
            if d % 10 == 0:
                coder_regime = "CODER_A_REGIME"
            elif d % 10 == 1:
                coder_regime = "CODER_B_REGIME"

            overlap_mult = partial_overlap_modes[d % len(partial_overlap_modes)]
            interp_mode = "SAMPLED_INTERPRETATION_VARIANT"
            if d % 12 == 2:
                interp_mode = "EPISTEMIC_CATEGORICAL_ALL_FLAGGED"
            elif d % 12 == 3:
                interp_mode = "EXPLICIT_MIXED_ALL_FLAGGED"

            omission_include_prob = 0.0 if (d % 15 == 4) else (1.0 if (d % 15 == 5) else float(rng.uniform(0.25, 1.0)))
            cond_mode = "ADVERSARIAL_LOW" if (d % 8 == 6) else ("CHARITABLE_HIGH" if (d % 8 == 7) else "UNIFORM_BRACKET")

            align_d = np.zeros((C, S), dtype=np.float64)
            weights_d = np.zeros(C, dtype=np.float64)

            # Vectorized weight noise
            noise_vec = np.exp(rng.normal(0.0, weight_sigma, size=C)) if weight_sigma > 0.0 else np.ones(C)

            for idx, cb in enumerate(cell_bounds):
                c = cb.cell
                # 1. Pick active coder side
                if cb.coder_a_probs is not None and cb.coder_b_probs is not None:
                    if coder_regime == "CODER_A_REGIME":
                        side = "coder_a"
                    elif coder_regime == "CODER_B_REGIME":
                        side = "coder_b"
                    else:
                        side = "coder_a" if rng.random() < 0.5 else "coder_b"
                elif cb.coder_a_probs is not None:
                    side = "coder_a"
                else:
                    side = "coder_b"

                if side == "coder_a":
                    probs = cb.coder_a_probs
                    sol_mat = cb.coder_a_sol_vecs
                    mixed_vec = cb.coder_a_mixed
                    lo_vec = cb.coder_a_min
                    hi_vec = cb.coder_a_max
                    raw_interp = c.coder_a_probability_interpretation
                    raw_imp = c.semantic_importance_a if c.semantic_importance_a is not None else 0.5
                else:
                    probs = cb.coder_b_probs
                    sol_mat = cb.coder_b_sol_vecs
                    mixed_vec = cb.coder_b_mixed
                    lo_vec = cb.coder_b_min
                    hi_vec = cb.coder_b_max
                    raw_interp = c.coder_b_probability_interpretation
                    raw_imp = c.semantic_importance_b if c.semantic_importance_b is not None else 0.5

                assert probs is not None and sol_mat is not None and mixed_vec is not None
                assert lo_vec is not None and hi_vec is not None

                # For INTERPRETATION_DIVERGENCE, allow sampling across both variants
                if c.uncertainty_class == UncertaintyClass.INTERPRETATION_DIVERGENCE and c.preference_uncertainty_set:
                    variants = c.preference_uncertainty_set.interpretation_variants or [raw_interp]
                    if interp_mode == "EPISTEMIC_CATEGORICAL_ALL_FLAGGED" and "epistemic_uncertainty_over_preference" in variants:
                        active_interp = "epistemic_uncertainty_over_preference"
                    elif interp_mode == "EXPLICIT_MIXED_ALL_FLAGGED" and "explicit_mixed_preference" in variants:
                        active_interp = "explicit_mixed_preference"
                    else:
                        active_interp = variants[int(rng.integers(0, len(variants)))]
                else:
                    active_interp = raw_interp or "epistemic_uncertainty_over_preference"

                # 2. Apply ISSUE-005 interpretation operator
                if active_interp == "conditional_or_context_dependent":
                    if cond_mode == "ADVERSARIAL_LOW":
                        cell_align = lo_vec
                    elif cond_mode == "CHARITABLE_HIGH":
                        cell_align = hi_vec
                    else:
                        alpha_u = float(rng.random())
                        cell_align = (1.0 - alpha_u) * lo_vec + alpha_u * hi_vec
                elif active_interp == "explicit_mixed_preference":
                    # Fixed blend alignment; if PARTIAL/NO_VALID_CROSSWALK NaN exists, sample unmapped bracket
                    nan_rows = np.isnan(sol_mat)
                    if nan_rows.any():
                        sol_s = np.where(nan_rows, rng.random(), sol_mat)
                        sol_s_norm = sol_s / np.maximum(1.0, sol_s.sum(axis=0, keepdims=True))
                        cell_align = np.minimum(probs[:, None], sol_s_norm).sum(axis=0)
                    else:
                        cell_align = mixed_vec
                else:
                    # epistemic_uncertainty_over_preference -> Categorical latent draw
                    k_draw = int(rng.choice(len(probs), p=probs / probs.sum()))
                    row_vals = sol_mat[k_draw]
                    if np.isnan(row_vals).any():
                        fill = float(rng.random())
                        cell_align = np.where(np.isnan(row_vals), fill, row_vals)
                    else:
                        cell_align = row_vals

                align_d[idx] = cell_align

                # 3. Sample structural weights (NEVER coder_confidence)
                w_val = max(0.05, float(raw_imp)) * float(noise_vec[idx])
                if cb.double_count_guard:
                    w_val *= overlap_mult
                if cb.is_omission_partial_id:
                    if omission_include_prob == 0.0:
                        w_val = 0.0
                    elif omission_include_prob < 1.0 and rng.random() > omission_include_prob:
                        w_val = 0.0
                weights_d[idx] = w_val

            for p_idx, grp in enumerate(p_idx_groups):
                w = weights_d[grp]
                w_sum = float(w.sum())
                if w_sum <= 1e-12:
                    # Fallback if all cells happened to be omitted in an extreme draw
                    mc_utils[d, :, p_idx] = align_d[grp].mean(axis=0)
                else:
                    mc_utils[d, :, p_idx] = (w[:, None] * align_d[grp]).sum(axis=0) / w_sum

            mc_regimes.append({
                "draw_index": d,
                "coder_regime": coder_regime,
                "overlap_multiplier": overlap_mult,
                "interpretation_mode": interp_mode,
                "omission_include_prob": round(omission_include_prob, 4),
                "conditional_mode": cond_mode,
            })

        # Derived Convex-Hull Barycenter sensitivity sweeps (STRICTLY DERIVED_ROBUSTNESS_CONVEX_BARYCENTER!)
        derived_bary: dict[str, np.ndarray] = {}
        if bary_enabled:
            for lam in bary_lambdas:
                bary_align = np.zeros((C, S), dtype=np.float64)
                for idx, cb in enumerate(cell_bounds):
                    c = cb.cell
                    a_ref = cb.coder_a_mixed if (cb.coder_a_mixed is not None and c.coder_a_probability_interpretation == "explicit_mixed_preference") else cb.coder_a_expected
                    b_ref = cb.coder_b_mixed if (cb.coder_b_mixed is not None and c.coder_b_probability_interpretation == "explicit_mixed_preference") else cb.coder_b_expected
                    if a_ref is not None and b_ref is not None and c.canonical_alternative_crosswalk and c.canonical_alternative_crosswalk.comparable:
                        bary_align[idx] = lam * a_ref + (1.0 - lam) * b_ref
                    else:
                        bary_align[idx] = base_exp_align[idx]
                derived_bary[f"barycenter_lambda_{lam:.2f}"] = _aggregate_by_participant(bary_align, base_w_sem)

        # Quantiles (95% CI) and std errors across D draws
        ci_lower_mat = np.quantile(mc_utils, 0.025, axis=0)
        ci_upper_mat = np.quantile(mc_utils, 0.975, axis=0)
        std_mat = np.std(mc_utils, axis=0)
        mc_mean_mat = np.mean(mc_utils, axis=0)

        # Build ParticipantUtility contract objects
        dataset_fp = compute_sha256(self.base_dir / "data" / "raw" / "survey_raw.csv")
        created_utc = datetime.now(timezone.utc).isoformat()
        participant_utilities: list[ParticipantUtility] = []

        # Track solution regret denominator (best achievable utility per participant across feasible S)
        p_best_expected = exp_u_mat.max(axis=0)  # (P_valid,)

        # Precompute per-question baseline utility cleanly per (pid, qid) -> vector (S,)
        per_pq_align: dict[tuple[str, str], np.ndarray] = {}
        for p_idx, pid in enumerate(valid_pids):
            by_q: dict[str, list[int]] = defaultdict(list)
            for idx in pid_cell_indices[pid]:
                by_q[cell_bounds[idx].cell.question_id].append(idx)
            for qid in PRIMARY_QUESTION_IDS:
                q_idxs = by_q.get(qid)
                if not q_idxs:
                    continue
                wq = base_w_sem[q_idxs]
                wqs = float(wq.sum())
                if wqs <= 1e-12:
                    per_pq_align[(pid, qid)] = base_exp_align[q_idxs].mean(axis=0)
                else:
                    per_pq_align[(pid, qid)] = (wq[:, None] * base_exp_align[q_idxs]).sum(axis=0) / wqs

        # Total primary subtopic count (excluding Q14)
        total_primary_subtopics = len({c.canonical_subtopic_id or c.subtopic_id for c in primary_cells})

        for p_idx, pid in enumerate(valid_pids):
            c_idxs = pid_cell_indices[pid]
            p_cells = [cell_bounds[i].cell for i in c_idxs]
            confs = [c.coder_confidence for c in p_cells if c.coder_confidence is not None]
            agrees = [c.coder_agreement for c in p_cells if c.coder_agreement is not None]
            mean_conf = round(sum(confs) / len(confs), 6) if confs else None
            mean_agree = round(sum(agrees) / len(agrees), 6) if agrees else None

            interps_p = sorted(
                {
                    interp
                    for c in p_cells
                    for interp in (
                        [c.coder_a_probability_interpretation, c.coder_b_probability_interpretation]
                        + (c.preference_uncertainty_set.interpretation_variants if c.preference_uncertainty_set else [])
                    )
                    if interp is not None
                }
            )
            has_single = any(
                cell_bounds[i].is_omission_partial_id or cell_bounds[i].is_granularity_partial_id
                for i in c_idxs
            )
            has_guard = any(cell_bounds[i].double_count_guard for i in c_idxs)
            has_unres_op = any(cell_bounds[i].has_unresolved_operator_flag for i in c_idxs)

            for s_idx, sol in enumerate(solutions):
                min_u = float(min_scen_mat[s_idx, p_idx])
                max_u = float(max_scen_mat[s_idx, p_idx])
                ci_lo = float(ci_lower_mat[s_idx, p_idx])
                ci_hi = float(ci_upper_mat[s_idx, p_idx])
                std_e = float(std_mat[s_idx, p_idx])
                exp_u = float(exp_u_mat[s_idx, p_idx])

                # Enforce ADR-0008 non-fabrication of point_utility when uncertainty sets are genuinely non-collapsed
                pt_u: float | None = round(exp_u, 6) if (abs(max_u - min_u) <= 1e-6 and not has_unres_op) else None
                per_q_dict = {
                    qid: (round(float(per_pq_align[(pid, qid)][s_idx]), 6) if (pid, qid) in per_pq_align else None)
                    for qid in PRIMARY_QUESTION_IDS
                }
                regret_val = float(max(0.0, p_best_expected[p_idx] - exp_u))

                pu = ParticipantUtility(
                    utility_id=f"PU_{pid}_{sol.solution_id}",
                    participant_id=pid,
                    solution_id=sol.solution_id,
                    preference_matrix_id=matrix.matrix_id,
                    missingness_state=MissingnessState.OBSERVED_USABLE,
                    observed_subtopic_count=len(c_idxs),
                    total_subtopic_count=total_primary_subtopics,
                    point_utility=pt_u,
                    utility_ci_lower_95=round(ci_lo, 6),
                    utility_ci_upper_95=round(ci_hi, 6),
                    utility_std_error=round(std_e, 6),
                    mean_coder_confidence=mean_conf,
                    mean_coder_agreement=mean_agree,
                    provenance=ProvenanceMeta(
                        record_id=f"PU_{pid}_{sol.solution_id}",
                        run_id=self.run_id,
                        dataset_fingerprint=dataset_fp,
                        created_at_utc=created_utc,
                        producer_module="src/preference/utilities.py",
                        producer_agent="agent_04",
                        upstream_artifact_ids=[matrix.matrix_id, sol.solution_id],
                        config_hash=config_hash,
                        schema_version=SCHEMA_VERSION,
                    ),
                    per_question_utilities=per_q_dict,
                    individual_regret=round(regret_val, 6),
                    is_below_veto_threshold=bool(exp_u < veto_threshold),
                    interpretation_modes_evaluated=interps_p,  # type: ignore[arg-type]
                    derived_scenario_origins=[DerivedScenarioOrigin.OBSERVED_CODER_EVIDENCE],
                    min_scenario_utility=round(min_u, 6),
                    max_scenario_utility=round(max_u, 6),
                    single_coder_uncertainty_bounded=has_single,
                    uses_coder_confidence_as_weight=False,
                    double_count_guard_evaluated=has_guard,
                )
                participant_utilities.append(pu)

        # Operator Audit & Participant / Question Diagnostics (strictly NO participant ranking!)
        interp_audit = {
            "issue_005_operators": {
                "epistemic_uncertainty_over_preference": "MACHINE_AUTHORIZED_CATEGORICAL_LATENT_DRAW_WITH_EXPECTED_SENSITIVITY",
                "explicit_mixed_preference": "MACHINE_AUTHORIZED_FRACTIONAL_OVERLAP_1_MINUS_TVD",
                "conditional_or_context_dependent": "UNRESOLVED_NO_FORMAL_PREREQUISITE_AST_BRACKETED_MIN_MAX_REGIME",
            },
            "conditional_primary_cell_ids": [
                cb.cell.cell_id for cb in cell_bounds if cb.has_conditional_operator
            ],
            "interpretation_divergence_primary_cell_count": sum(
                1 for cb in cell_bounds if cb.cell.uncertainty_class == UncertaintyClass.INTERPRETATION_DIVERGENCE
            ),
            "uses_coder_confidence_as_weight": False,
            "semantic_importance_role": "authorized_subtopic_salience_weight_with_uniform_sensitivity",
            "q14_excluded_from_utility": True,
        }

        part_diags: dict[str, dict[str, Any]] = {}
        for pid in all_pids:
            p_all = all_primary_by_pid[pid]
            p_use = usable_by_pid[pid]
            if pid in pid_to_idx:
                p_i = pid_to_idx[pid]
                mean_width = float((max_scen_mat[:, p_i] - min_scen_mat[:, p_i]).mean())
                max_u_best = float(exp_u_mat[:, p_i].max())
                min_u_worst = float(exp_u_mat[:, p_i].min())
            else:
                mean_width = 0.0
                max_u_best = 0.0
                min_u_worst = 0.0
            part_diags[pid] = {
                "primary_record_count": len(p_all),
                "usable_primary_record_count": len(p_use),
                "preserved_missing_primary_count": len(p_all) - len(p_use),
                "single_coder_primary_count": sum(
                    1
                    for c in p_use
                    if c.uncertainty_class
                    in (
                        UncertaintyClass.SINGLE_CODER_PARTIAL_ID_OMISSION,
                        UncertaintyClass.SINGLE_CODER_PARTIAL_ID_GRANULARITY,
                    )
                ),
                "crosswalk_unresolved_primary_count": sum(
                    1 for c in p_use if c.uncertainty_class == UncertaintyClass.CROSSWALK_PARTIAL_OR_UNALIGNED
                ),
                "conditional_primary_count": sum(
                    1
                    for c in p_use
                    if c.coder_a_probability_interpretation == "conditional_or_context_dependent"
                    or c.coder_b_probability_interpretation == "conditional_or_context_dependent"
                ),
                "mean_scenario_utility_width": round(mean_width, 6),
                "achievable_expected_utility_range": [round(min_u_worst, 6), round(max_u_best, 6)],
                "ranked_as_participant": False,
            }

        q_diags: dict[str, dict[str, Any]] = {}
        for qid in PRIMARY_QUESTION_IDS:
            q_cells = [cb.cell for cb in cell_bounds if cb.cell.question_id == qid]
            q_all = [c for c in primary_cells if c.question_id == qid]
            q_diags[qid] = {
                "total_primary_cells": len(q_all),
                "usable_primary_cells": len(q_cells),
                "preserved_missing_cells": len(q_all) - len(q_cells),
                "distinct_subtopics_observed": len({c.canonical_subtopic_id or c.subtopic_id for c in q_all}),
                "minority_subtopic_cells": sum(
                    1 for cb in cell_bounds if cb.cell.question_id == qid and cb.is_granularity_partial_id
                ),
                "uncertainty_class_breakdown": {
                    uc_val: sum(1 for c in q_all if c.uncertainty_class and c.uncertainty_class.value == uc_val)
                    for uc_val in sorted({c.uncertainty_class.value for c in q_all if c.uncertainty_class})
                },
            }

        # Deterministic coupled coding-gap corners (common world applied to ALL solutions jointly!)
        # Varies ONLY unmapped NO_VALID_CROSSWALK / PARTIAL_CROSSWALK / CONDITIONAL / SINGLE_CODER_OMISSION
        coupled_gap_corners: dict[str, np.ndarray] = {}
        gap_corner_specs = [
            ("gap_unmapped0_omit0_condLo", "a_or_b_unmapped_0", 0.0, "cond_lo"),
            ("gap_unmapped1_omit1_condHi", "a_or_b_unmapped_1", 1.0, "cond_hi"),
            ("gap_coderA_only_unmapped0", "coder_a_pref", 1.0, "cond_lo"),
            ("gap_coderB_only_unmapped1", "coder_b_pref", 1.0, "cond_hi"),
            ("gap_coderA_omit0", "coder_a_pref", 0.0, "cond_hi"),
            ("gap_coderB_omit0", "coder_b_pref", 0.0, "cond_lo"),
        ]
        for corner_name, side_mode, omit_w, cond_mode_c in gap_corner_specs:
            c_align = base_exp_align.copy()
            c_weights = base_w_sem.copy()
            for idx, cb in enumerate(cell_bounds):
                if cb.is_omission_partial_id:
                    c_weights[idx] *= omit_w
                if cb.hinges_on_coding_gap:
                    if side_mode == "a_or_b_unmapped_0" or cond_mode_c == "cond_lo":
                        if cb.has_conditional_operator or cb.is_no_valid_crosswalk or cb.is_partial_crosswalk:
                            c_align[idx] = cb.min_align if cond_mode_c == "cond_lo" else cb.max_align
                    if side_mode == "coder_a_pref" and cb.coder_a_expected is not None:
                        c_align[idx] = cb.coder_a_min if cond_mode_c == "cond_lo" else cb.coder_a_max
                    elif side_mode == "coder_b_pref" and cb.coder_b_expected is not None:
                        c_align[idx] = cb.coder_b_min if cond_mode_c == "cond_lo" else cb.coder_b_max
                    elif side_mode == "a_or_b_unmapped_0":
                        c_align[idx] = cb.min_align
                    elif side_mode == "a_or_b_unmapped_1":
                        c_align[idx] = cb.max_align
            coupled_gap_corners[corner_name] = _aggregate_by_participant(c_align, c_weights)

        return UtilityEnsembleSummary(
            run_id=self.run_id,
            matrix_id=matrix.matrix_id,
            participant_ids=all_pids,
            valid_participant_ids=valid_pids,
            excluded_all_missing_participant_ids=excluded_pids,
            solution_ids=sol_ids,
            question_ids_evaluated=list(PRIMARY_QUESTION_IDS),
            participant_utilities=participant_utilities,
            expected_utility_matrix=exp_u_mat,
            uniform_subtopic_utility_matrix=unif_sub_u_mat,
            uniform_question_utility_matrix=unif_q_u_mat,
            ci_lower_matrix=ci_lower_mat,
            ci_upper_matrix=ci_upper_mat,
            min_scenario_matrix=min_scen_mat,
            max_scenario_matrix=max_scen_mat,
            min_coding_gap_matrix=min_gap_mat,
            max_coding_gap_matrix=max_gap_mat,
            coupled_gap_corner_matrices=coupled_gap_corners,
            mc_draws_utilities=mc_utils,
            mc_draw_regimes=mc_regimes,
            derived_barycenter_matrices=derived_bary,
            interpretation_operator_audit=interp_audit,
            participant_diagnostics=part_diags,
            question_diagnostics=q_diags,
        )

    def save(self, summary: UtilityEnsembleSummary) -> Path:
        out_dir = self.base_dir / "data" / "processed" / "preference"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "participant_utility.json"

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
            "matrix_id": summary.matrix_id,
            "valid_participant_ids": summary.valid_participant_ids,
            "excluded_all_missing_participant_ids": summary.excluded_all_missing_participant_ids,
            "question_ids_evaluated": summary.question_ids_evaluated,
            "solution_count": len(summary.solution_ids),
            "utility_record_count": len(summary.participant_utilities),
            "interpretation_operator_audit": summary.interpretation_operator_audit,
            "participant_diagnostics": summary.participant_diagnostics,
            "question_diagnostics": summary.question_diagnostics,
            "participant_utilities": [_enum_clean(asdict(u)) for u in summary.participant_utilities],
        }
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return out_path
