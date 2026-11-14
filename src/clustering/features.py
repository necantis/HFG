"""Canonical Input Verification & Multi-Representation Feature Builder for Agent 05.

Owned by: Agent 05 — Clustering & Preference Heterogeneity
Schema Version: 1.0.0 (Aligned with ADR-0005, ADR-0007, and ADR-0008)

Verifies canonical production artifacts against runs/<run_id>/manifest.json
(and optional verified Agent 11 bundle SHA256SUMS.json) without ever reading test
fixtures as analytical data, imputing missingness, using coder_confidence as a
weight, or mixing Q14 contextual remarks into the Q01-Q13 primary clustering spine.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

PRIMARY_QUESTION_IDS: tuple[str, ...] = tuple(f"Q{i:02d}" for i in range(1, 14))
CONTEXTUAL_QUESTION_IDS: tuple[str, ...] = ("Q14",)


def compute_sha256(path: Path) -> str:
    """Compute lowercase hexadecimal SHA-256 digest for a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_clustering_config(
    base_dir: Path | str,
    run_id: str = "run_20261111_002",
) -> tuple[dict[str, Any], str, str]:
    """Load non-sensitive clustering configuration and return (config, rel_path, sha256)."""
    root = Path(base_dir).resolve()
    cfg_path = root / "runs" / run_id / "clustering_config.json"
    if not cfg_path.is_file():
        raise FileNotFoundError(f"Missing clustering configuration file: {cfg_path}")
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    if cfg.get("run_id") != run_id:
        raise ValueError(f"clustering_config.json run_id mismatch: {cfg.get('run_id')} != {run_id}")
    if cfg.get("uses_coder_confidence_as_weight"):
        raise ValueError("clustering_config.json violates ADR-0005/0008: uses_coder_confidence_as_weight must be False.")
    if cfg.get("imputes_missing_preferences"):
        raise ValueError("clustering_config.json violates ADR-0005: imputes_missing_preferences must be False.")
    if cfg.get("modifies_feasible_set_or_pareto") or cfg.get("modifies_voting_weights_or_rights"):
        raise ValueError("clustering_config.json violates Ex-Post Non-Interference invariant.")
    return cfg, str(cfg_path.relative_to(root)), compute_sha256(cfg_path)


@dataclass
class VerifiedCanonicalInputs:
    """Container for provenance-verified Agent 03/04 inputs and invariants."""

    run_id: str
    matrix_id: str
    participant_ids: list[str]
    all_cells: list[dict[str, Any]]
    primary_cells: list[dict[str, Any]]
    primary_usable_cells: list[dict[str, Any]]
    contextual_q14_cells: list[dict[str, Any]]
    missing_cells: list[dict[str, Any]]
    participant_utility_payload: dict[str, Any]
    pareto_results_payload: dict[str, Any]
    robust_pareto_payload: dict[str, Any]
    feasible_alternatives_payload: dict[str, Any]
    reconciled_values_payload: dict[str, Any]
    themes_codebook_payload: dict[str, Any]
    uncertainty_summary_payload: dict[str, Any]
    verified_hashes: dict[str, dict[str, Any]]
    provenance_checks: dict[str, bool]


def _resolve_artifact_path(
    root: Path,
    manifest_rel_path: str,
    bundle_dir: Path | None,
    bundle_rel_path: str | None = None,
) -> Path:
    """Resolve an artifact either from a verified bundle directory or the repo workspace."""
    if bundle_dir is not None and bundle_rel_path is not None:
        candidate = bundle_dir / bundle_rel_path
        if candidate.is_file():
            return candidate
    repo_candidate = root / manifest_rel_path
    if repo_candidate.is_file():
        return repo_candidate
    raise FileNotFoundError(
        f"Canonical artifact missing at {repo_candidate}"
        + (f" and bundle path {bundle_dir / bundle_rel_path}" if bundle_dir and bundle_rel_path else "")
    )


def load_and_verify_canonical_inputs(
    base_dir: Path | str,
    run_id: str = "run_20261111_002",
    bundle_dir: Path | str | None = None,
) -> VerifiedCanonicalInputs:
    """Load canonical Agent 03/04 artifacts and verify every digest against manifest.json."""
    root = Path(base_dir).resolve()
    bdir = Path(bundle_dir).resolve() if bundle_dir is not None else None
    manifest_path = root / "runs" / run_id / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Canonical manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    m_arts = manifest.get("artifacts", {})

    # Optional bundle SHA256SUMS verification
    bundle_sums: dict[str, str] = {}
    if bdir is not None:
        sums_candidates = [
            bdir / "metadata" / "SHA256SUMS.json",
            bdir.parent / "metadata" / "SHA256SUMS.json",
        ]
        for sc in sums_candidates:
            if sc.is_file():
                raw_sums = json.loads(sc.read_text(encoding="utf-8"))
                for rel_k, meta in (raw_sums.get("files") or {}).items():
                    bundle_sums[Path(rel_k).name] = meta["sha256"]
                break

    required_specs = [
        ("preference_matrix_v1", "preference/preference_matrix.parquet"),
        ("preference_matrix_json_v1", "preference/preference_matrix.json"),
        ("participant_utility_v1", "preference/participant_utility.json"),
        ("preference_uncertainty_summary_v1", "preference/preference_uncertainty_summary.json"),
        ("pareto_results_v1", "preference/pareto_results.json"),
        ("robust_pareto_results_v1", "preference/robust_pareto_results.json"),
        ("feasible_alternatives_v1", "preference/feasible_alternatives.json"),
        ("reconciled_values_v1", "reconciliation/reconciled_values.json"),
        ("themes_codebook_v1", "reconciliation/themes_codebook.json"),
    ]

    verified_hashes: dict[str, dict[str, Any]] = {}
    resolved_paths: dict[str, Path] = {}
    all_manifest_matched = True
    all_bundle_matched = True

    for aid, b_rel in required_specs:
        if aid not in m_arts:
            raise KeyError(f"Required canonical artifact '{aid}' missing from {manifest_path}")
        rec = m_arts[aid]
        rel_path = rec["path"]
        sh_map = rec.get("source_hashes", {})
        expected_manifest_sha = None
        for sk, sv in sh_map.items():
            if sk == rel_path or Path(sk).name == Path(rel_path).name:
                expected_manifest_sha = sv
                break
        if expected_manifest_sha is None:
            raise ValueError(f"Manifest entry for '{aid}' lacks self SHA-256 in source_hashes.")

        actual_path = _resolve_artifact_path(root, rel_path, bdir, b_rel)
        actual_sha = compute_sha256(actual_path)
        manifest_match = actual_sha == expected_manifest_sha
        bundle_expected = bundle_sums.get(actual_path.name)
        bundle_match = True if bundle_expected is None else (actual_sha == bundle_expected)

        if not manifest_match:
            all_manifest_matched = False
            raise ValueError(
                f"SHA-256 mismatch for {aid} at {actual_path}: expected {expected_manifest_sha}, got {actual_sha}"
            )
        if not bundle_match:
            all_bundle_matched = False
            raise ValueError(
                f"Bundle SHA256SUMS mismatch for {aid} at {actual_path}: expected {bundle_expected}, got {actual_sha}"
            )

        resolved_paths[aid] = actual_path
        verified_hashes[aid] = {
            "path": str(actual_path),
            "canonical_repo_path": rel_path,
            "sha256": actual_sha,
            "manifest_sha256_match": manifest_match,
            "bundle_sha256_match": bundle_match,
            "bytes": actual_path.stat().st_size,
        }

    # Verify Parquet row-count parity with JSON PreferenceMatrix
    pm_df = pd.read_parquet(resolved_paths["preference_matrix_v1"])
    pm_json = json.loads(resolved_paths["preference_matrix_json_v1"].read_text(encoding="utf-8"))
    cells = list(pm_json.get("cells") or [])
    if len(pm_df) != len(cells):
        raise ValueError(
            f"Parquet ({len(pm_df)}) vs JSON ({len(cells)}) PreferenceMatrix cell count mismatch."
        )

    primary_cells = [c for c in cells if c["question_id"] in PRIMARY_QUESTION_IDS]
    q14_cells = [c for c in cells if c["question_id"] in CONTEXTUAL_QUESTION_IDS]
    missing_cells = [c for c in cells if c["missingness_state"] != "observed_usable"]
    primary_usable = [c for c in primary_cells if c["missingness_state"] == "observed_usable"]

    # Audit zero silent imputation in preserved missingness cells
    for mc in missing_cells:
        if mc.get("resolved_point_distribution") is not None or mc.get("alternative_probabilities"):
            raise ValueError(
                f"Missingness invariant violated on {mc.get('cell_id')}: non-empty probability values found."
            )

    participant_ids = sorted({c["participant_id"] for c in cells})
    pu_payload = json.loads(resolved_paths["participant_utility_v1"].read_text(encoding="utf-8"))
    pr_payload = json.loads(resolved_paths["pareto_results_v1"].read_text(encoding="utf-8"))
    rpr_payload = json.loads(resolved_paths["robust_pareto_results_v1"].read_text(encoding="utf-8"))
    fa_payload = json.loads(resolved_paths["feasible_alternatives_v1"].read_text(encoding="utf-8"))
    rv_payload = json.loads(resolved_paths["reconciled_values_v1"].read_text(encoding="utf-8"))
    tc_payload = json.loads(resolved_paths["themes_codebook_v1"].read_text(encoding="utf-8"))
    unc_payload = json.loads(resolved_paths["preference_uncertainty_summary_v1"].read_text(encoding="utf-8"))

    # Confirm Q14 never enters feasible solutions or utilities
    q14_in_solutions = any(
        "Q14" in (s.get("included_question_ids") or []) or "Q14" in (s.get("question_alternatives") or {})
        for s in (fa_payload.get("governance_solutions") or [])
    )
    if q14_in_solutions:
        raise ValueError("Invariant violation: Q14 found inside feasible GovernanceSolution spine.")

    provenance_checks = {
        "manifest_hashes_verified": all_manifest_matched,
        "bundle_sums_verified": all_bundle_matched,
        "parquet_json_parity": len(pm_df) == len(cells),
        "participant_count_11": len(participant_ids) == 11,
        "q14_isolated_from_primary": len(primary_cells) + len(q14_cells) == len(cells) and not q14_in_solutions,
        "missingness_18_unimputed": len(missing_cells) == 18,
    }

    return VerifiedCanonicalInputs(
        run_id=run_id,
        matrix_id=str(pm_json.get("matrix_id", f"PM_{run_id}")),
        participant_ids=participant_ids,
        all_cells=cells,
        primary_cells=primary_cells,
        primary_usable_cells=primary_usable,
        contextual_q14_cells=q14_cells,
        missing_cells=missing_cells,
        participant_utility_payload=pu_payload,
        pareto_results_payload=pr_payload,
        robust_pareto_payload=rpr_payload,
        feasible_alternatives_payload=fa_payload,
        reconciled_values_payload=rv_payload,
        themes_codebook_payload=tc_payload,
        uncertainty_summary_payload=unc_payload,
        verified_hashes=verified_hashes,
        provenance_checks=provenance_checks,
    )


@dataclass
class RepresentationBundle:
    """Explicit feature representations (A, B, C, D) with exact provenance disclosures."""

    rep_a_subtopic_scenarios: dict[str, dict[str, list[dict[str, float]]]]
    rep_a_metadata: dict[str, Any]
    rep_d_question_scenarios: dict[str, dict[str, dict[str, list[dict[str, float]]]]]
    rep_d_metadata: dict[str, Any]
    rep_c_solution_ids: list[str]
    rep_c_utility_mid: np.ndarray
    rep_c_utility_lo: np.ndarray
    rep_c_utility_hi: np.ndarray
    rep_c_utility_min_scen: np.ndarray
    rep_c_utility_max_scen: np.ndarray
    rep_c_utility_se: np.ndarray
    rep_c_metadata: dict[str, Any]
    rep_b_metadata: dict[str, Any]
    q14_contextual_summary: dict[str, Any] = field(default_factory=dict)


def build_representations(inputs: VerifiedCanonicalInputs) -> RepresentationBundle:
    """Construct Representation A, B, C, D feature inputs with full accounting of included information."""
    pids = inputs.participant_ids
    p_idx = {p: i for i, p in enumerate(pids)}

    # --- Rep A: Comparable subtopic distributions on Q01-Q13 (excluding NO_VALID_CROSSWALK disjoint cells) ---
    rep_a: dict[str, dict[str, list[dict[str, float]]]] = {p: {} for p in pids}
    rep_d: dict[str, dict[str, dict[str, list[dict[str, float]]]]] = {p: defaultdict(dict) for p in pids}
    rep_a_cells_used = 0
    excluded_no_crosswalk = 0
    rep_a_uc_counts: Counter[str] = Counter()

    for c in inputs.primary_usable_cells:
        pus = c.get("preference_uncertainty_set") or {}
        scens = pus.get("discrete_scenarios") or []
        if not scens:
            excluded_no_crosswalk += 1
            continue
        p = c["participant_id"]
        qid = c["question_id"]
        sid = c["canonical_subtopic_id"]
        norm_scens = [{str(k): float(v) for k, v in s.items()} for s in scens]
        rep_a[p][sid] = norm_scens
        rep_d[p][qid][sid] = norm_scens
        rep_a_cells_used += 1
        rep_a_uc_counts[c["uncertainty_class"]] += 1

    rep_a_subtopics = sorted({sid for m in rep_a.values() for sid in m})
    rep_a_metadata = {
        "representation_id": "A_preference_distribution",
        "description": (
            "Cell-level discrete canonical preference distributions on Q01-Q13 evaluated via exact pairwise "
            "set-to-set expectation over mutually observed comparable canonical subtopics (zero missingness imputation)."
        ),
        "questions_included": list(PRIMARY_QUESTION_IDS),
        "questions_excluded": list(CONTEXTUAL_QUESTION_IDS),
        "usable_primary_cells_used": rep_a_cells_used,
        "disjoint_no_valid_crosswalk_cells_excluded": excluded_no_crosswalk,
        "missing_primary_cells_preserved_unimputed": sum(
            1 for c in inputs.missing_cells if c["question_id"] in PRIMARY_QUESTION_IDS
        ),
        "unique_canonical_subtopics_covered": len(rep_a_subtopics),
        "uncertainty_classes_represented": dict(sorted(rep_a_uc_counts.items())),
        "uses_coder_confidence_weight": False,
        "imputes_missing_values": False,
    }

    # --- Rep D: Question-level aggregated profiles across Q01-Q13 ---
    rep_d_dict = {p: {q: dict(subs) for q, subs in rep_d[p].items()} for p in pids}
    q_coverage = {
        qid: sum(1 for p in pids if qid in rep_d_dict[p])
        for qid in PRIMARY_QUESTION_IDS
    }
    rep_d_metadata = {
        "representation_id": "D_question_level_aggregated",
        "description": (
            "Question-level aggregated subtopic distributions over Q01-Q13 giving equal weight to each "
            "mutually observed primary question rather than weighting by subtopic granularity multiplicity."
        ),
        "questions_included": list(PRIMARY_QUESTION_IDS),
        "questions_excluded": list(CONTEXTUAL_QUESTION_IDS),
        "question_participant_coverage": q_coverage,
        "usable_primary_cells_used": rep_a_cells_used,
        "missing_question_cells_preserved_unimputed": sum(
            1 for p in pids for qid in PRIMARY_QUESTION_IDS if qid not in rep_d_dict[p]
        ),
        "uses_coder_confidence_weight": False,
        "imputes_missing_values": False,
    }

    # --- Rep B metadata: Full ADR-0008 uncertainty propagation across ALL 249 primary usable cells ---
    rep_b_uc_counts = Counter(c["uncertainty_class"] for c in inputs.primary_usable_cells)
    rep_b_metadata = {
        "representation_id": "B_uncertainty_aware_preference",
        "description": (
            "Full ADR-0008 scenario-ensemble representation across ALL 249 Q01-Q13 usable cells: propagates "
            "DUAL_CODER_DISTRIBUTION_SET (discrete coder draws), INTERPRETATION_DIVERGENCE (epistemic categorical "
            "realization vs mixed fractional alignment), CROSSWALK_PARTIAL_OR_UNALIGNED (including coherent coder-side "
            "regime sampling over NO_VALID_CROSSWALK disjoint hypotheses), and SINGLE_CODER_PARTIAL_ID "
            "(omission inclusion/exclusion & double-count-guard weight regimes)."
        ),
        "questions_included": list(PRIMARY_QUESTION_IDS),
        "questions_excluded": list(CONTEXTUAL_QUESTION_IDS),
        "usable_primary_cells_used": len(inputs.primary_usable_cells),
        "unique_canonical_subtopics_covered": len({c["canonical_subtopic_id"] for c in inputs.primary_usable_cells}),
        "uncertainty_classes_represented": dict(sorted(rep_b_uc_counts.items())),
        "missing_primary_cells_preserved_unimputed": sum(
            1 for c in inputs.missing_cells if c["question_id"] in PRIMARY_QUESTION_IDS
        ),
        "uses_coder_confidence_weight": False,
        "imputes_missing_values": False,
    }

    # --- Rep C: Participant utility profiles across 543 feasible GovernanceSolutions ---
    recs = inputs.participant_utility_payload.get("participant_utilities") or []
    sol_ids = sorted({r["solution_id"] for r in recs})
    s_idx = {s: k for k, s in enumerate(sol_ids)}
    n_p = len(pids)
    n_s = len(sol_ids)
    u_lo = np.zeros((n_p, n_s), dtype=np.float64)
    u_hi = np.zeros((n_p, n_s), dtype=np.float64)
    u_mid = np.zeros((n_p, n_s), dtype=np.float64)
    u_min_s = np.zeros((n_p, n_s), dtype=np.float64)
    u_max_s = np.zeros((n_p, n_s), dtype=np.float64)
    u_se = np.zeros((n_p, n_s), dtype=np.float64)

    for r in recs:
        i = p_idx[r["participant_id"]]
        k = s_idx[r["solution_id"]]
        lo = float(r["utility_ci_lower_95"])
        hi = float(r["utility_ci_upper_95"])
        u_lo[i, k] = lo
        u_hi[i, k] = hi
        u_mid[i, k] = 0.5 * (lo + hi)
        u_min_s[i, k] = float(r.get("min_scenario_utility", lo))
        u_max_s[i, k] = float(r.get("max_scenario_utility", hi))
        u_se[i, k] = float(r.get("utility_std_error") or 0.0)

    rep_c_metadata = {
        "representation_id": "C_participant_utility_profiles",
        "description": (
            "Participant utility profiles from participant_utility_v1 over all 543 constraint-feasible "
            "GovernanceSolutions (Q01-Q13 spine). Preserves ADR-0008 interval uncertainty ([ci_lower_95, ci_upper_95] "
            "and [min_scenario_utility, max_scenario_utility]; point_utility=None respected) via centered-cosine "
            "(Pearson correlation), Spearman rank-correlation, and RMS L2 distances plus CI scenario propagation."
        ),
        "feasible_solutions_count": n_s,
        "participant_utility_records": len(recs),
        "point_utility_null_count": sum(1 for r in recs if r.get("point_utility") is None),
        "questions_included": list(inputs.participant_utility_payload.get("question_ids_evaluated") or PRIMARY_QUESTION_IDS),
        "questions_excluded": list(CONTEXTUAL_QUESTION_IDS),
        "uses_coder_confidence_weight": False,
        "imputes_missing_values": False,
    }

    # Contextual Q14 audit summary only (never enters clustering matrices)
    q14_summary = {
        "total_q14_cells": len(inputs.contextual_q14_cells),
        "usable_q14_cells": sum(1 for c in inputs.contextual_q14_cells if c["missingness_state"] == "observed_usable"),
        "missing_q14_cells": sum(1 for c in inputs.contextual_q14_cells if c["missingness_state"] != "observed_usable"),
        "unique_q14_subtopics": sorted({c["canonical_subtopic_id"] for c in inputs.contextual_q14_cells}),
        "excluded_from_clustering_features": True,
    }

    return RepresentationBundle(
        rep_a_subtopic_scenarios=rep_a,
        rep_a_metadata=rep_a_metadata,
        rep_d_question_scenarios=rep_d_dict,
        rep_d_metadata=rep_d_metadata,
        rep_c_solution_ids=sol_ids,
        rep_c_utility_mid=u_mid,
        rep_c_utility_lo=u_lo,
        rep_c_utility_hi=u_hi,
        rep_c_utility_min_scen=u_min_s,
        rep_c_utility_max_scen=u_max_s,
        rep_c_utility_se=u_se,
        rep_c_metadata=rep_c_metadata,
        rep_b_metadata=rep_b_metadata,
        q14_contextual_summary=q14_summary,
    )
