"""Exact Participant-Level Pareto Frontier & Multi-Criteria Welfare Analyzer.

Owned by: Agent 04 — Preference, Utility & Pareto
Schema Version: 1.0.0 (Aligned with ADR-0005 and ADR-0008)

Evaluates strict Pareto dominance strictly across valid (non-all-missing)
participants on Q01-Q13 without pruning by clusters, organisational values,
or coding disagreement.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from src.contracts import (
    ParetoResult,
    ProvenanceMeta,
    SCHEMA_VERSION,
)
from src.preference.preference_matrix import compute_sha256


def nondominated_mask_exact(U: np.ndarray, tol: float = 1e-9) -> np.ndarray:
    """Exact pairwise O(S^2 * P) strict Pareto nondominated boolean mask of shape (S,).

    Solution j strictly Pareto-dominates solution i iff:
      forall p: U[j, p] >= U[i, p] - tol  AND  exists p: U[j, p] > U[i, p] + tol
    """
    S = U.shape[0]
    if S == 0:
        return np.zeros(0, dtype=bool)
    is_dom = np.zeros(S, dtype=bool)
    chunk = 256
    for start in range(0, S, chunk):
        end = min(S, start + chunk)
        Uc = U[start:end]  # (C, P)
        ge = (U[None, :, :] >= Uc[:, None, :] - tol).all(axis=2)
        gt = (U[None, :, :] > Uc[:, None, :] + tol).any(axis=2)
        is_dom[start:end] = (ge & gt).any(axis=1)
    return ~is_dom


def nondominated_mask_skyline(U: np.ndarray, tol: float = 1e-9) -> np.ndarray:
    """Fast skyline filter exact for strict dominance up to pairwise survival refinement."""
    S = U.shape[0]
    if S <= 256:
        return nondominated_mask_exact(U, tol=tol)
    order = np.argsort(-U.sum(axis=1))
    survivors: list[int] = []
    # Incremental pruning against current frontier (exact up to P*tol sum bound)
    sum_u = U.sum(axis=1)
    p_margin = U.shape[1] * tol
    front_arr = np.empty((0, U.shape[1]), dtype=np.float64)
    for idx in order:
        row = U[idx]
        if front_arr.shape[0] > 0:
            # A point j in front_arr with sum_u[j] >= sum_u[idx] can dominate row:
            ge = (front_arr >= row[None, :] - tol).all(axis=1)
            gt = (front_arr > row[None, :] + tol).any(axis=1)
            if (ge & gt).any():
                continue
        survivors.append(int(idx))
        front_arr = U[survivors]
    # Exact pairwise check over surviving candidates plus check against potential near-sum peers
    surv_idx = np.asarray(survivors, dtype=np.int64)
    surv_mask = nondominated_mask_exact(U[surv_idx], tol=tol)
    out = np.zeros(S, dtype=bool)
    out[surv_idx[surv_mask]] = True
    # Safety check if any near-sum dominator exists within P * tol
    if p_margin > 0.0:
        cand_idx = np.where(out)[0]
        if cand_idx.size > 0:
            # Verify no earlier-discarded point dominates cand_idx due to tol
            ge_all = (U[None, :, :] >= U[cand_idx][:, None, :] - tol).all(axis=2)
            gt_all = (U[None, :, :] > U[cand_idx][:, None, :] + tol).any(axis=2)
            bad = (ge_all & gt_all).any(axis=1)
            out[cand_idx[bad]] = False
    return out


def compute_welfare_metrics(
    U: np.ndarray,  # shape (S, P_valid)
    *,
    nash_epsilon: float = 1e-6,
    atkinson_aversion: float = 0.5,
    veto_threshold: float = 0.35,
) -> dict[str, np.ndarray]:
    """Compute multi-criteria welfare metrics vectorised across S feasible solutions."""
    S, P = U.shape
    if S == 0 or P == 0:
        raise ValueError("Utility matrix must be non-empty on both solution and participant axes.")

    U_clipped = np.clip(U, 0.0, 1.0)
    rawls = U_clipped.min(axis=1)
    utilitarian = U_clipped.mean(axis=1)
    nash = np.exp(np.log(np.maximum(nash_epsilon, U_clipped)).mean(axis=1))

    # Gini inequality: sum_{a,b} |u_a - u_b| / (2 * P^2 * mean(u))
    diffs = np.abs(U_clipped[:, :, None] - U_clipped[:, None, :]).sum(axis=(1, 2))
    denom = 2.0 * (P ** 2) * np.maximum(nash_epsilon, utilitarian)
    gini = np.clip(diffs / denom, 0.0, 1.0)

    # Atkinson inequality index
    if abs(atkinson_aversion - 1.0) < 1e-9:
        ede = nash
    else:
        power = 1.0 - atkinson_aversion
        ede = (np.maximum(nash_epsilon, U_clipped) ** power).mean(axis=1) ** (1.0 / power)
    atkinson = np.clip(1.0 - (ede / np.maximum(nash_epsilon, utilitarian)), 0.0, 1.0)

    opp_counts = (U_clipped < veto_threshold).sum(axis=1).astype(np.int64)
    opp_shares = opp_counts / float(P)

    best_per_p = U_clipped.max(axis=0, keepdims=True)
    max_regret = np.maximum(0.0, best_per_p - U_clipped).max(axis=1)

    return {
        "rawls_maximin": rawls,
        "utilitarian": utilitarian,
        "nash_welfare": nash,
        "gini_inequality": gini,
        "atkinson_inequality": atkinson,
        "opposition_counts": opp_counts,
        "opposition_shares": opp_shares,
        "max_regret": max_regret,
    }


class ParetoAnalyzer:
    """Compute exact ParetoResult with full dominator map and multi-criteria rankings."""

    def __init__(self, base_dir: Path | str, run_id: str = "run_20261111_002") -> None:
        self.base_dir = Path(base_dir).resolve()
        self.run_id = run_id

    def evaluate(
        self,
        *,
        matrix_id: str,
        solution_ids: list[str],
        valid_participant_ids: list[str],
        excluded_all_missing_participant_ids: list[str],
        utility_matrix: np.ndarray,  # shape (S, P_valid)
        mc_config: dict[str, Any],
        config_hash: str = "",
        profile_assignments: dict[str, str] | None = None,
    ) -> ParetoResult:
        S, P = utility_matrix.shape
        if S != len(solution_ids) or P != len(valid_participant_ids):
            raise ValueError("Utility matrix shape does not match solution_ids / valid_participant_ids.")

        tol = float(mc_config.get("dominance_tolerance", 1e-9))
        nash_eps = float(mc_config.get("nash_epsilon", 1e-6))
        atk_eps = float(mc_config.get("atkinson_inequality_aversion", 0.5))
        veto_thr = float(mc_config.get("veto_threshold", 0.35))

        # Exact pairwise dominance matrix: dom_mat[i, j] True iff j strictly dominates i
        ge = (utility_matrix[None, :, :] >= utility_matrix[:, None, :] - tol).all(axis=2)
        gt = (utility_matrix[None, :, :] > utility_matrix[:, None, :] + tol).any(axis=2)
        dom_mat = ge & gt  # shape (S, S)

        nondom_ids: list[str] = []
        dominated_map: dict[str, list[str]] = {}
        pairwise_margins: dict[str, float] = {}

        for i, sid in enumerate(solution_ids):
            dominators = [solution_ids[j] for j in range(S) if j != i and dom_mat[i, j]]
            if not dominators:
                nondom_ids.append(sid)
            else:
                dominated_map[sid] = dominators

            # Dominance margin: min over challengers j!=i of max_p (U[i,p] - U[j,p])
            # Positive <=> nondominated by margin m; Negative <=> strictly dominated with deficit -m
            other_idx = [j for j in range(S) if j != i]
            if other_idx:
                diff_vs_others = utility_matrix[i][None, :] - utility_matrix[other_idx]  # (S-1, P)
                best_escape_per_j = diff_vs_others.max(axis=1)  # (S-1,)
                margin = float(best_escape_per_j.min())
            else:
                margin = 1.0
            pairwise_margins[sid] = round(margin, 6)

        metrics = compute_welfare_metrics(
            utility_matrix,
            nash_epsilon=nash_eps,
            atkinson_aversion=atk_eps,
            veto_threshold=veto_thr,
        )

        def _score_dict(arr: np.ndarray, is_int: bool = False) -> dict[str, Any]:
            return {
                sid: (int(arr[i]) if is_int else round(float(arr[i]), 6))
                for i, sid in enumerate(solution_ids)
            }

        rawls_d = _score_dict(metrics["rawls_maximin"])
        util_d = _score_dict(metrics["utilitarian"])
        nash_d = _score_dict(metrics["nash_welfare"])
        gini_d = _score_dict(metrics["gini_inequality"])
        atk_d = _score_dict(metrics["atkinson_inequality"])
        opp_c_d = _score_dict(metrics["opposition_counts"], is_int=True)
        opp_s_d = _score_dict(metrics["opposition_shares"])
        regret_d = _score_dict(metrics["max_regret"])

        rankings = {
            "rawls_maximin": sorted(solution_ids, key=lambda s: (-rawls_d[s], -util_d[s], s)),
            "utilitarian": sorted(solution_ids, key=lambda s: (-util_d[s], -rawls_d[s], s)),
            "nash_welfare": sorted(solution_ids, key=lambda s: (-nash_d[s], -util_d[s], s)),
            "min_gini_inequality": sorted(solution_ids, key=lambda s: (gini_d[s], -util_d[s], s)),
            "min_atkinson_inequality": sorted(solution_ids, key=lambda s: (atk_d[s], -util_d[s], s)),
            "min_opposition": sorted(solution_ids, key=lambda s: (opp_c_d[s], regret_d[s], -util_d[s], s)),
            "minimax_regret": sorted(solution_ids, key=lambda s: (regret_d[s], -rawls_d[s], s)),
        }

        profile_means: dict[str, dict[str, float]] = {}
        if profile_assignments:
            p_to_idx = {pid: k for k, pid in enumerate(valid_participant_ids)}
            clusters: dict[str, list[int]] = {}
            for pid, cname in profile_assignments.items():
                if pid in p_to_idx:
                    clusters.setdefault(cname, []).append(p_to_idx[pid])
            for cname, idxs in sorted(clusters.items()):
                profile_means[cname] = {
                    sid: round(float(utility_matrix[i, idxs].mean()), 6)
                    for i, sid in enumerate(solution_ids)
                }

        dataset_fp = compute_sha256(self.base_dir / "data" / "raw" / "survey_raw.csv")
        created_utc = datetime.now(timezone.utc).isoformat()
        pid_str = f"PARETO_{self.run_id}_expected_ref"

        return ParetoResult(
            pareto_result_id=pid_str,
            preference_matrix_id=matrix_id,
            evaluated_solution_ids=list(solution_ids),
            valid_participant_ids=list(valid_participant_ids),
            excluded_all_missing_participant_ids=list(excluded_all_missing_participant_ids),
            nondominated_solution_ids=nondom_ids,
            dominated_solution_map=dominated_map,
            rawls_maximin_scores=rawls_d,
            utilitarian_scores=util_d,
            nash_welfare_scores=nash_d,
            gini_inequality_scores=gini_d,
            atkinson_inequality_scores=atk_d,
            opposition_counts=opp_c_d,
            opposition_shares=opp_s_d,
            max_regret_scores=regret_d,
            rankings_by_criterion=rankings,
            provenance=ProvenanceMeta(
                record_id=pid_str,
                run_id=self.run_id,
                dataset_fingerprint=dataset_fp,
                created_at_utc=created_utc,
                producer_module="src/preference/pareto.py",
                producer_agent="agent_04",
                upstream_artifact_ids=[matrix_id],
                config_hash=config_hash,
                schema_version=SCHEMA_VERSION,
            ),
            pairwise_dominance_margins=pairwise_margins,
            profile_mean_utilities=profile_means,
            schema_version=SCHEMA_VERSION,
        )

    def save(
        self,
        result: ParetoResult,
        *,
        extra_metadata: dict[str, Any] | None = None,
    ) -> Path:
        out_dir = self.base_dir / "data" / "processed" / "preference"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "pareto_results.json"

        payload: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "run_id": self.run_id,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "adr_reference": "ADR-0008",
            "evaluation_note": (
                "Reference deterministic expected-scenario ParetoResult across Q01-Q13 valid participants. "
                "Full set-valued, coding-gap, and Monte Carlo robustness classification appears in robust_pareto_results.json."
            ),
            "pareto_result": asdict(result),
        }
        if extra_metadata:
            payload["sensitivity_comparison"] = extra_metadata
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return out_path
