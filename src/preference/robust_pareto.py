"""ADR-0008 4-State Robust Pareto Classification & Sensitivity Engine.

Owned by: Agent 04 — Preference, Utility & Pareto
Schema Version: 1.0.0 (Aligned with ADR-0005 and ADR-0008)

Evaluates participant-level Pareto nondominance across:
- Discrete dual-coder scenario ensembles and ISSUE-005 interpretation variants;
- Single-coder omission/granularity partial identification & double-count guard modes;
- Level 2 NO_VALID_CROSSWALK & PARTIAL_CROSSWALK interval bounds;
- Configurable Monte Carlo draws (pareto_mc_config_v1);
- Derived convex-hull barycenter sensitivity sweeps (explicitly labeled
  DERIVED_ROBUSTNESS_CONVEX_BARYCENTER, never promoted to canonical).

Classifies EVERY feasible GovernanceSolution into the 4 mutually exclusive
RobustParetoStatus categories:
  1. ROBUSTLY_DOMINATED
  2. ROBUSTLY_NONDOMINATED
  3. CONDITIONALLY_NONDOMINATED
  4. UNRESOLVED_DUE_TO_CODING_UNCERTAINTY
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from src.contracts import (
    DerivedScenarioOrigin,
    GovernanceSolution,
    ParetoResult,
    ProvenanceMeta,
    RobustParetoResult,
    RobustParetoStatus,
    SCHEMA_VERSION,
    UncertaintyEnvelope,
)
from src.preference.pareto import compute_welfare_metrics, nondominated_mask_skyline
from src.preference.preference_matrix import compute_sha256
from src.preference.utilities import UtilityEnsembleSummary


class RobustParetoEngine:
    """Propagate ADR-0008 uncertainty sets into 4-state RobustParetoResult."""

    def __init__(self, base_dir: Path | str, run_id: str = "run_20261111_002") -> None:
        self.base_dir = Path(base_dir).resolve()
        self.run_id = run_id

    def evaluate(
        self,
        *,
        base_pareto: ParetoResult,
        utility_summary: UtilityEnsembleSummary,
        solutions: list[GovernanceSolution],
        mc_config: dict[str, Any],
        pareto_mc_config_rel_path: str,
        config_hash: str = "",
    ) -> tuple[RobustParetoResult, dict[str, Any]]:
        mc_u = utility_summary.mc_draws_utilities  # shape (D, S, P_valid)
        D, S, P = mc_u.shape
        sol_ids = utility_summary.solution_ids
        regimes = utility_summary.mc_draw_regimes

        tol = float(mc_config.get("dominance_tolerance", 1e-9))
        nash_eps = float(mc_config.get("nash_epsilon", 1e-6))
        atk_eps = float(mc_config.get("atkinson_inequality_aversion", 0.5))
        veto_thr = float(mc_config.get("veto_threshold", 0.35))
        veto_grid = [float(v) for v in mc_config.get("veto_threshold_grid", [0.25, 0.35, 0.45, 0.55])]
        core_thr = float(mc_config.get("robust_core_inclusion_threshold", 1.0))
        hi_conf_thr = float(mc_config.get("high_confidence_inclusion_threshold", 0.95))

        nondom_draws = np.zeros((D, S), dtype=bool)
        metric_series: dict[str, np.ndarray] = {
            "rawls_maximin": np.zeros((D, S), dtype=np.float64),
            "utilitarian": np.zeros((D, S), dtype=np.float64),
            "nash_welfare": np.zeros((D, S), dtype=np.float64),
            "gini_inequality": np.zeros((D, S), dtype=np.float64),
            "atkinson_inequality": np.zeros((D, S), dtype=np.float64),
            "opposition_share": np.zeros((D, S), dtype=np.float64),
            "max_regret": np.zeros((D, S), dtype=np.float64),
        }
        top1_counts: dict[str, np.ndarray] = {
            "rawls_maximin": np.zeros(S, dtype=np.int64),
            "utilitarian": np.zeros(S, dtype=np.int64),
            "nash_welfare": np.zeros(S, dtype=np.int64),
            "min_gini_inequality": np.zeros(S, dtype=np.int64),
            "min_atkinson_inequality": np.zeros(S, dtype=np.int64),
            "min_opposition": np.zeros(S, dtype=np.int64),
            "minimax_regret": np.zeros(S, dtype=np.int64),
        }

        for d in range(D):
            U_d = mc_u[d]
            mask_d = nondominated_mask_skyline(U_d, tol=tol)
            nondom_draws[d] = mask_d

            m_d = compute_welfare_metrics(
                U_d,
                nash_epsilon=nash_eps,
                atkinson_aversion=atk_eps,
                veto_threshold=veto_thr,
            )
            metric_series["rawls_maximin"][d] = m_d["rawls_maximin"]
            metric_series["utilitarian"][d] = m_d["utilitarian"]
            metric_series["nash_welfare"][d] = m_d["nash_welfare"]
            metric_series["gini_inequality"][d] = m_d["gini_inequality"]
            metric_series["atkinson_inequality"][d] = m_d["atkinson_inequality"]
            metric_series["opposition_share"][d] = m_d["opposition_shares"]
            metric_series["max_regret"][d] = m_d["max_regret"]

            # Track Top-1 winners across draws
            top1_counts["rawls_maximin"][int(np.argmax(m_d["rawls_maximin"]))] += 1
            top1_counts["utilitarian"][int(np.argmax(m_d["utilitarian"]))] += 1
            top1_counts["nash_welfare"][int(np.argmax(m_d["nash_welfare"]))] += 1
            top1_counts["min_gini_inequality"][int(np.argmin(m_d["gini_inequality"]))] += 1
            top1_counts["min_atkinson_inequality"][int(np.argmin(m_d["atkinson_inequality"]))] += 1
            top1_counts["min_opposition"][int(np.argmin(m_d["opposition_shares"]))] += 1
            top1_counts["minimax_regret"][int(np.argmin(m_d["max_regret"]))] += 1

        incl_probs = nondom_draws.mean(axis=0)  # shape (S,)

        # Deterministic coupled coding-gap corner checks (common world applied to ALL solutions jointly)
        gap_corner_masks: dict[str, np.ndarray] = {}
        for cname, C_mat in utility_summary.coupled_gap_corner_matrices.items():
            gap_corner_masks[cname] = nondominated_mask_skyline(C_mat, tol=tol)
        base_mask_ref = nondominated_mask_skyline(utility_summary.expected_utility_matrix, tol=tol)

        if gap_corner_masks:
            stacked_corners = np.vstack([gap_corner_masks[k] for k in sorted(gap_corner_masks)])
            corner_any_nondom = stacked_corners.any(axis=0)
            corner_all_nondom = stacked_corners.all(axis=0)
            coding_gap_flips_dominance = (stacked_corners != base_mask_ref[None, :]).any(axis=0) | (
                corner_any_nondom & (~corner_all_nondom)
            )
        else:
            corner_any_nondom = base_mask_ref.copy()
            corner_all_nondom = base_mask_ref.copy()
            coding_gap_flips_dominance = np.zeros(S, dtype=bool)

        # Mutual-exclusive 4-state ADR-0008 classification:
        #   1. ROBUSTLY_NONDOMINATED: nondominated in all admissible MC draws (p >= core_thr) AND all coupled gap corners
        #   2. ROBUSTLY_DOMINATED: dominated in ALL admissible MC draws (p == 0.0) AND dominated across ALL coupled gap corners
        #   3. UNRESOLVED_DUE_TO_CODING_UNCERTAINTY: dominance sign flips specifically across coupled coding-gap corners
        #      (NO_VALID_CROSSWALK / PARTIAL_CROSSWALK / SINGLE_CODER_OMISSION / unparameterized conditional bounds)
        #   4. CONDITIONALLY_NONDOMINATED: nondominated on a strict subset of MC draws (0 < p < core_thr) driven by
        #      comparable dual-coder distributions, ISSUE-005 interpretations, partial-overlap guard, or salience weights
        statuses: dict[str, RobustParetoStatus] = {}
        robustly_dom: list[str] = []
        robustly_nondom: list[str] = []
        conditionally_nondom: list[str] = []
        unresolved_coding: list[str] = []
        cond_regimes_map: dict[str, list[str]] = {}
        high_confidence_nondom: list[str] = []

        for s_idx, sid in enumerate(sol_ids):
            p_incl = float(incl_probs[s_idx])
            if p_incl >= hi_conf_thr - 1e-9:
                high_confidence_nondom.append(sid)

            active_draw_idxs = np.where(nondom_draws[:, s_idx])[0]
            active_corners = [cname for cname in sorted(gap_corner_masks) if bool(gap_corner_masks[cname][s_idx])]

            if p_incl >= core_thr - 1e-9 and bool(corner_all_nondom[s_idx]):
                statuses[sid] = RobustParetoStatus.ROBUSTLY_NONDOMINATED
                robustly_nondom.append(sid)
            elif p_incl == 0.0 and not bool(corner_any_nondom[s_idx]):
                statuses[sid] = RobustParetoStatus.ROBUSTLY_DOMINATED
                robustly_dom.append(sid)
            elif bool(coding_gap_flips_dominance[s_idx]):
                statuses[sid] = RobustParetoStatus.UNRESOLVED_DUE_TO_CODING_UNCERTAINTY
                unresolved_coding.append(sid)
                tags = _summarize_active_regimes(active_draw_idxs, regimes, gap_flipped=True)
                for ac in active_corners[:4]:
                    tags.append(f"CORNER:{ac}")
                cond_regimes_map[sid] = sorted(set(tags))
            elif active_draw_idxs.size > 0:
                statuses[sid] = RobustParetoStatus.CONDITIONALLY_NONDOMINATED
                conditionally_nondom.append(sid)
                cond_regimes_map[sid] = _summarize_active_regimes(active_draw_idxs, regimes, gap_flipped=False)
            else:
                statuses[sid] = RobustParetoStatus.ROBUSTLY_DOMINATED
                robustly_dom.append(sid)

        incl_dict = {sid: round(float(incl_probs[i]), 6) for i, sid in enumerate(sol_ids)}
        # Strict robust frontier uses core_thr; high-confidence tier recorded explicitly in sensitivity report
        robust_frontier = list(robustly_nondom) if robustly_nondom else list(high_confidence_nondom)

        top1_dict: dict[str, dict[str, float]] = {}
        for crit, counts_arr in top1_counts.items():
            nonzero = {
                sol_ids[i]: round(float(counts_arr[i] / D), 6)
                for i in range(S)
                if counts_arr[i] > 0
            }
            top1_dict[crit] = dict(sorted(nonzero.items(), key=lambda kv: (-kv[1], kv[0])))

        # Summary UncertaintyEnvelopes per solution across key social welfare metrics
        metric_intervals: dict[str, dict[str, UncertaintyEnvelope]] = {}
        for s_idx, sid in enumerate(sol_ids):
            s_env: dict[str, UncertaintyEnvelope] = {}
            for m_name, arr in metric_series.items():
                vals = arr[:, s_idx]
                s_env[m_name] = UncertaintyEnvelope(
                    point_estimate=round(float(np.mean(vals)), 6),
                    ci_lower_95=round(float(np.quantile(vals, 0.025)), 6),
                    ci_upper_95=round(float(np.quantile(vals, 0.975)), 6),
                    std_error=round(float(np.std(vals)), 6),
                    coder_confidence=None,
                    coder_agreement=None,
                    distribution_type="MONTE_CARLO_EMPIRICAL",
                )
            metric_intervals[sid] = s_env

        # Veto threshold sensitivity across veto_grid
        veto_sens: dict[str, dict[str, float]] = {}
        for thr in veto_grid:
            key = f"veto_{thr:.2f}"
            opp_s_thr = (utility_summary.expected_utility_matrix < thr).mean(axis=1)
            veto_sens[key] = {
                sid: round(float(opp_s_thr[i]), 6)
                for i, sid in enumerate(sol_ids)
                if opp_s_thr[i] > 0.0 or statuses[sid] != RobustParetoStatus.ROBUSTLY_DOMINATED
            }

        # Weight sensitivity: shift in normalized utilitarian score between semantic_importance,
        # uniform_subtopic_weight, and uniform_question_weight + std across weight perturbations
        u_sem = utility_summary.expected_utility_matrix.mean(axis=1)
        u_sub = utility_summary.uniform_subtopic_utility_matrix.mean(axis=1)
        u_q = utility_summary.uniform_question_utility_matrix.mean(axis=1)
        weight_sens = {
            sid: round(float(max(abs(u_sem[i] - u_sub[i]), abs(u_sem[i] - u_q[i]))), 6)
            for i, sid in enumerate(sol_ids)
        }

        origins_used = [DerivedScenarioOrigin.OBSERVED_CODER_EVIDENCE]
        if utility_summary.derived_barycenter_matrices:
            origins_used.append(DerivedScenarioOrigin.DERIVED_ROBUSTNESS_CONVEX_BARYCENTER)
        if float(mc_config.get("weight_perturbation_sigma", 0.0)) > 0.0:
            origins_used.append(DerivedScenarioOrigin.DERIVED_ROBUSTNESS_SCENARIO)

        dataset_fp = compute_sha256(self.base_dir / "data" / "raw" / "survey_raw.csv")
        created_utc = datetime.now(timezone.utc).isoformat()
        rob_id = f"ROBUST_PARETO_{self.run_id}_mc{D}"

        robust_res = RobustParetoResult(
            robust_pareto_id=rob_id,
            base_pareto_result_id=base_pareto.pareto_result_id,
            monte_carlo_draws=D,
            random_seed=int(mc_config.get("random_seed", 42)),
            pareto_mc_config_path=pareto_mc_config_rel_path,
            frontier_inclusion_probabilities=incl_dict,
            robust_frontier_solution_ids=robust_frontier,
            criterion_top1_probabilities=top1_dict,
            utility_metric_intervals=metric_intervals,
            missing_participant_ids_preserved=list(utility_summary.excluded_all_missing_participant_ids),
            provenance=ProvenanceMeta(
                record_id=rob_id,
                run_id=self.run_id,
                dataset_fingerprint=dataset_fp,
                created_at_utc=created_utc,
                producer_module="src/preference/robust_pareto.py",
                producer_agent="agent_04",
                upstream_artifact_ids=[base_pareto.pareto_result_id, utility_summary.matrix_id],
                config_hash=config_hash,
                schema_version=SCHEMA_VERSION,
            ),
            veto_threshold_sensitivity=veto_sens,
            subtopic_weight_perturbation_sensitivity=weight_sens,
            solution_robustness_statuses=statuses,
            robustly_dominated_solution_ids=robustly_dom,
            robustly_nondominated_solution_ids=robustly_nondom,
            conditionally_nondominated_solution_ids=conditionally_nondom,
            unresolved_due_to_coding_uncertainty_ids=unresolved_coding,
            conditional_nondominated_regimes=cond_regimes_map,
            derived_scenario_origins_used=origins_used,
            robust_core_inclusion_threshold=core_thr,
            pruned_by_clusters_values_or_disagreement=False,
            schema_version=SCHEMA_VERSION,
        )

        # Rich derived-sensitivity + Pareto explanations bundle
        bary_frontiers: dict[str, Any] = {}
        for b_name, B_mat in utility_summary.derived_barycenter_matrices.items():
            b_mask = nondominated_mask_skyline(B_mat, tol=tol)
            bary_frontiers[b_name] = {
                "scenario_origin": DerivedScenarioOrigin.DERIVED_ROBUSTNESS_CONVEX_BARYCENTER.value,
                "nondominated_count": int(b_mask.sum()),
                "nondominated_solution_ids": [sol_ids[i] for i in range(S) if b_mask[i]],
            }

        unif_sub_mask = nondominated_mask_skyline(utility_summary.uniform_subtopic_utility_matrix, tol=tol)
        unif_q_mask = nondominated_mask_skyline(utility_summary.uniform_question_utility_matrix, tol=tol)

        # Pareto explanations per non-dominated solution (ex-post interpretation ONLY!)
        sol_by_id = {s.solution_id: s for s in solutions}
        frontier_focus_ids = sorted(
            set(robustly_nondom) | set(high_confidence_nondom) | set(unresolved_coding[:15]) | set(conditionally_nondom[:20]),
            key=lambda sid: -incl_dict[sid],
        )
        explanations: list[dict[str, Any]] = []
        for sid in frontier_focus_ids:
            sol = sol_by_id[sid]
            st_val = statuses[sid].value
            explanations.append({
                "solution_id": sid,
                "label_en": sol.label_en,
                "robust_pareto_status": st_val,
                "frontier_inclusion_probability": incl_dict[sid],
                "mean_utilitarian": metric_intervals[sid]["utilitarian"].point_estimate,
                "mean_rawls_maximin": metric_intervals[sid]["rawls_maximin"].point_estimate,
                "mean_nash_welfare": metric_intervals[sid]["nash_welfare"].point_estimate,
                "mean_max_regret": metric_intervals[sid]["max_regret"].point_estimate,
                "question_postures": sol.question_alternatives,
                "explanatory_organisational_values": sol.explanatory_organisational_values,
                "regimes_if_conditional_or_unresolved": cond_regimes_map.get(sid, []),
                "explanation_note": (
                    "Ex-post structural & value characterization ONLY; never used for solution filtering or Pareto pruning."
                ),
            })

        sensitivity_bundle = {
            "status_counts": {
                "ROBUSTLY_NONDOMINATED": len(robustly_nondom),
                "CONDITIONALLY_NONDOMINATED": len(conditionally_nondom),
                "UNRESOLVED_DUE_TO_CODING_UNCERTAINTY": len(unresolved_coding),
                "ROBUSTLY_DOMINATED": len(robustly_dom),
            },
            "high_confidence_nondominated_threshold": hi_conf_thr,
            "high_confidence_nondominated_count": len(high_confidence_nondom),
            "high_confidence_nondominated_ids": high_confidence_nondom,
            "derived_barycenter_sensitivity": bary_frontiers,
            "weight_mode_frontiers": {
                "uniform_subtopic_weight": {
                    "nondominated_count": int(unif_sub_mask.sum()),
                    "nondominated_solution_ids": [sol_ids[i] for i in range(S) if unif_sub_mask[i]],
                },
                "uniform_question_weight": {
                    "nondominated_count": int(unif_q_mask.sum()),
                    "nondominated_solution_ids": [sol_ids[i] for i in range(S) if unif_q_mask[i]],
                },
            },
            "pareto_explanations": explanations,
        }
        return robust_res, sensitivity_bundle

    def save(
        self,
        result: RobustParetoResult,
        sensitivity_bundle: dict[str, Any],
        utility_summary: UtilityEnsembleSummary,
    ) -> dict[str, Path]:
        out_dir = self.base_dir / "data" / "processed" / "preference"
        out_dir.mkdir(parents=True, exist_ok=True)

        def _enum_clean(obj: Any) -> Any:
            from enum import Enum
            if isinstance(obj, Enum):
                return obj.value
            if isinstance(obj, dict):
                return {str(k): _enum_clean(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple)):
                return [_enum_clean(v) for v in obj]
            return obj

        robust_path = out_dir / "robust_pareto_results.json"
        robust_payload = {
            "schema_version": SCHEMA_VERSION,
            "run_id": self.run_id,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "adr_reference": "ADR-0008",
            "status_counts": sensitivity_bundle["status_counts"],
            "high_confidence_nondominated_threshold": sensitivity_bundle["high_confidence_nondominated_threshold"],
            "high_confidence_nondominated_count": sensitivity_bundle["high_confidence_nondominated_count"],
            "high_confidence_nondominated_ids": sensitivity_bundle["high_confidence_nondominated_ids"],
            "robust_pareto_result": _enum_clean(asdict(result)),
        }
        robust_path.write_text(json.dumps(robust_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        sens_path = out_dir / "pareto_sensitivity.json"
        sens_payload = {
            "schema_version": SCHEMA_VERSION,
            "run_id": self.run_id,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "adr_reference": "ADR-0008",
            "derived_scenario_notice": (
                "Derived convex-hull barycenters (DERIVED_ROBUSTNESS_CONVEX_BARYCENTER) and alternative weight modes "
                "are strictly diagnostic sensitivity sweeps and never override canonical observed coder sets."
            ),
            "derived_barycenter_sensitivity": sensitivity_bundle["derived_barycenter_sensitivity"],
            "weight_mode_frontiers": sensitivity_bundle["weight_mode_frontiers"],
            "veto_threshold_sensitivity": result.veto_threshold_sensitivity,
            "subtopic_weight_perturbation_sensitivity": result.subtopic_weight_perturbation_sensitivity,
            "pareto_explanations": sensitivity_bundle["pareto_explanations"],
            "participant_diagnostics": utility_summary.participant_diagnostics,
            "question_diagnostics": utility_summary.question_diagnostics,
        }
        sens_path.write_text(json.dumps(sens_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return {"robust_pareto": robust_path, "pareto_sensitivity": sens_path}


def _summarize_active_regimes(
    draw_idxs: np.ndarray,
    regimes: list[dict[str, Any]],
    *,
    gap_flipped: bool,
) -> list[str]:
    tags: list[str] = []
    if gap_flipped:
        tags.append("CODING_GAP_INTERVAL_UNRESOLVED")
    if draw_idxs.size == 0:
        return tags or ["BOUNDARY_INTERVAL_ONLY"]
    c_reg = {regimes[int(d)]["coder_regime"] for d in draw_idxs}
    o_mult = {regimes[int(d)]["overlap_multiplier"] for d in draw_idxs}
    i_mode = {regimes[int(d)]["interpretation_mode"] for d in draw_idxs}
    cond_m = {regimes[int(d)]["conditional_mode"] for d in draw_idxs}
    if "CODER_A_REGIME" in c_reg and "CODER_B_REGIME" not in c_reg:
        tags.append("CODER_A_FAVORABLE")
    elif "CODER_B_REGIME" in c_reg and "CODER_A_REGIME" not in c_reg:
        tags.append("CODER_B_FAVORABLE")
    if len(o_mult) == 1:
        tags.append(f"PARTIAL_OVERLAP_WEIGHT_{next(iter(o_mult))}")
    if "EXPLICIT_MIXED_ALL_FLAGGED" in i_mode and "EPISTEMIC_CATEGORICAL_ALL_FLAGGED" not in i_mode:
        tags.append("EXPLICIT_MIXED_INTERP_FAVORABLE")
    elif "EPISTEMIC_CATEGORICAL_ALL_FLAGGED" in i_mode and "EXPLICIT_MIXED_ALL_FLAGGED" not in i_mode:
        tags.append("EPISTEMIC_CATEGORICAL_INTERP_FAVORABLE")
    if "CHARITABLE_HIGH" in cond_m and "ADVERSARIAL_LOW" not in cond_m:
        tags.append("CONDITIONAL_PREREQUISITE_CHARITABLE")
    if not tags:
        tags.append("MULTI_REGIME_STOCHASTIC_SUPPORT")
    return sorted(set(tags))
