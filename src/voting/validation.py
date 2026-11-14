"""Input Provenance & Active Ballot Validation Engine (Agent 06).

Owned by: Agent 06 — Voting & Social Choice
Schema Version: 1.0.0 (Aligned with ADR-0005 and ADR-0008)

Verifies upstream Agent 04 & manifest provenance hashes, enforces strict
Q01-Q13 primary spine / Q14 exclusion, checks prohibition against cluster or
coder-confidence weighting and participant ranking, and evaluates whether
active ballots/rankings for Baldwin and RRV exist or can legitimately be derived
without fabricating complete rankings across missing cells, partial
identification, unresolved crosswalks, or coding gaps.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.contracts import (
    GovernanceSolution,
    PreferenceMatrix,
    ProvenanceMeta,
    SCHEMA_VERSION,
)
from src.preference.preference_matrix import (
    PRIMARY_QUESTION_IDS,
    load_pareto_mc_config,
    load_preference_matrix,
)

PRIMARY_QUESTION_SET = frozenset(PRIMARY_QUESTION_IDS)


def compute_sha256(path: Path | str) -> str:
    """Compute hex SHA-256 of a file safely."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def get_git_commit_sha(base_dir: Path) -> str:
    """Return current HEAD commit SHA or 'unknown' cleanly."""
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=base_dir,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        return out or "unknown"
    except Exception:
        return "unknown"


def _match_manifest_sha(art_entry: dict[str, Any], rel_path: str) -> str | None:
    src_hashes = art_entry.get("source_hashes") or {}
    for k, v in src_hashes.items():
        if k == rel_path or k.endswith("/" + rel_path):
            return str(v)
    return None


def discover_external_ballot_paths(
    base_dir: Path,
    run_id: str,
    manifest_payload: dict[str, Any] | None = None,
) -> dict[str, Path | None]:
    """Check canonical run metadata and filesystem for active-group ballot files."""
    run_dir = base_dir / "runs" / run_id
    candidates_baldwin = [
        run_dir / "baldwin_ballots.json",
        run_dir / "baldwin_ballots.csv",
        base_dir / "data" / "raw" / "baldwin_ballots.json",
        base_dir / "data" / "raw" / "baldwin_ballots.csv",
    ]
    candidates_rrv = [
        run_dir / "rrv_ballots.json",
        run_dir / "rrv_ballots.csv",
        base_dir / "data" / "raw" / "rrv_ballots.json",
        base_dir / "data" / "raw" / "rrv_ballots.csv",
    ]

    if manifest_payload:
        run_meta = manifest_payload.get("run_metadata") or manifest_payload
        for key, bucket in (("baldwin_input_path", candidates_baldwin), ("rrv_input_path", candidates_rrv)):
            raw_p = run_meta.get(key)
            if raw_p:
                p = Path(str(raw_p))
                bucket.insert(0, p if p.is_absolute() else (base_dir / p))

    baldwin_path = next((p for p in candidates_baldwin if p.is_file()), None)
    rrv_path = next((p for p in candidates_rrv if p.is_file()), None)
    return {"baldwin": baldwin_path, "rrv": rrv_path}


def _load_solutions(fa_payload: dict[str, Any]) -> list[GovernanceSolution]:
    raw_sols = fa_payload.get("governance_solutions") or []
    solutions: list[GovernanceSolution] = []
    for raw in raw_sols:
        s_dict = dict(raw)
        prov = s_dict.get("provenance")
        if isinstance(prov, dict):
            s_dict["provenance"] = ProvenanceMeta(**prov)
        solutions.append(GovernanceSolution(**s_dict))
    return solutions


def evaluate_ballot_derivation_legitimacy(
    matrix: PreferenceMatrix,
    pu_payload: dict[str, Any],
    interval_strict_comparability_by_participant: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Assess whether complete ordinal/cardinal ballots can be derived from ADR-0008 contracts.

    Under ADR-0008, point_utility is None whenever scenario intervals do not
    collapse to a deterministic singleton or whenever unresolved conditional /
    partial-ID / crosswalk gaps remain. Fabricating complete rankings or exact
    cardinal ballot matrices across those gaps violates statistical honesty.
    """
    pu_records = pu_payload.get("participant_utilities") or []
    total_records = len(pu_records)
    non_null_point = sum(1 for r in pu_records if r.get("point_utility") is not None)
    null_point = total_records - non_null_point

    primary_cells = [c for c in matrix.cells if c.question_id in PRIMARY_QUESTION_SET]
    uc_counts: dict[str, int] = {}
    for c in primary_cells:
        key = c.uncertainty_class.value if c.uncertainty_class else str(c.missingness_state.value)
        uc_counts[key] = uc_counts.get(key, 0) + 1

    none_consensus = uc_counts.get("NONE_CONSENSUS", 0)
    preserved_missing = uc_counts.get("PRESERVED_MISSINGNESS", 0)
    single_coder_total = (
        uc_counts.get("SINGLE_CODER_PARTIAL_ID_OMISSION", 0)
        + uc_counts.get("SINGLE_CODER_PARTIAL_ID_GRANULARITY", 0)
    )
    crosswalk_unresolved = uc_counts.get("CROSSWALK_PARTIAL_OR_UNALIGNED", 0)
    interp_divergence = uc_counts.get("INTERPRETATION_DIVERGENCE", 0)
    dual_coder_set = uc_counts.get("DUAL_CODER_DISTRIBUTION_SET", 0)

    # Check mean interval width from participant_utility records
    widths = [
        float(r["max_scenario_utility"]) - float(r["min_scenario_utility"])
        for r in pu_records
        if r.get("min_scenario_utility") is not None and r.get("max_scenario_utility") is not None
    ]
    mean_width = (sum(widths) / len(widths)) if widths else 0.0
    max_width = max(widths) if widths else 0.0
    min_width = min(widths) if widths else 0.0

    # Derive strict complete ballots strictly prohibited when point_utility is missing
    # or substantive partial identification/coding uncertainty prevents total orderings
    all_participants_collapsed = total_records > 0 and non_null_point == total_records
    can_derive_complete_strict_rankings = bool(all_participants_collapsed)
    can_derive_point_cardinal_ballots = bool(all_participants_collapsed)

    blocking_reasons: list[str] = []
    if null_point > 0 or total_records == 0:
        blocking_reasons.append(
            f"point_utility is None for {null_point}/{total_records} (participant, solution) utility records under ADR-0008."
        )
    if preserved_missing > 0:
        blocking_reasons.append(
            f"{preserved_missing} primary Q01-Q13 cells have PRESERVED_MISSINGNESS (cannot be zero-imputed)."
        )
    if single_coder_total > 0:
        blocking_reasons.append(
            f"{single_coder_total} primary Q01-Q13 cells have SINGLE_CODER_PARTIAL_ID uncertainty (silent coder is EPISTEMICALLY_UNOBSERVED)."
        )
    if crosswalk_unresolved > 0:
        blocking_reasons.append(
            f"{crosswalk_unresolved} primary Q01-Q13 cells have CROSSWALK_PARTIAL_OR_UNALIGNED residual ambiguity."
        )
    if interp_divergence > 0 or dual_coder_set > 0:
        blocking_reasons.append(
            f"{interp_divergence} INTERPRETATION_DIVERGENCE and {dual_coder_set} DUAL_CODER_DISTRIBUTION_SET primary cells prevent point collapse."
        )
    if interval_strict_comparability_by_participant:
        max_comp = max(interval_strict_comparability_by_participant.values())
        if max_comp < 1.0:
            blocking_reasons.append(
                f"Interval dominance across [min_scenario_utility, max_scenario_utility] yields at most "
                f"{100.0 * max_comp:.2f}% strictly comparable pairs per participant (remaining >={100.0 * (1.0 - max_comp):.2f}% pairs overlap)."
            )

    return {
        "total_utility_records": total_records,
        "non_null_point_utility_count": non_null_point,
        "null_point_utility_count": null_point,
        "primary_cell_count": len(primary_cells),
        "primary_uncertainty_class_counts": dict(sorted(uc_counts.items())),
        "none_consensus_primary_count": none_consensus,
        "preserved_missing_primary_count": preserved_missing,
        "single_coder_partial_id_primary_count": single_coder_total,
        "crosswalk_partial_or_unaligned_primary_count": crosswalk_unresolved,
        "scenario_utility_interval_width_stats": {
            "min": round(min_width, 6),
            "mean": round(mean_width, 6),
            "max": round(max_width, 6),
        },
        "can_derive_complete_strict_rankings_without_fabrication": can_derive_complete_strict_rankings,
        "can_derive_point_cardinal_ballots_without_fabrication": can_derive_point_cardinal_ballots,
        "blocking_reasons": blocking_reasons,
    }


def validate_agent_06_inputs(
    base_dir: Path | str,
    run_id: str = "run_20261111_002",
    *,
    verify_manifest: bool = True,
) -> dict[str, Any]:
    """Load, verify provenance, enforce prohibitions, and run active ballot validation."""
    root = Path(base_dir).resolve()
    proc_dir = root / "data" / "processed"
    pref_dir = proc_dir / "preference"
    run_dir = root / "runs" / run_id

    required_paths = {
        "preference_matrix_v1": proc_dir / "preference_matrix.parquet",
        "feasible_alternatives_v1": pref_dir / "feasible_alternatives.json",
        "participant_utility_v1": pref_dir / "participant_utility.json",
        "pareto_results_v1": pref_dir / "pareto_results.json",
        "robust_pareto_results_v1": pref_dir / "robust_pareto_results.json",
        "pareto_sensitivity_v1": pref_dir / "pareto_sensitivity.json",
        "preference_uncertainty_summary_v1": pref_dir / "preference_uncertainty_summary.json",
        "agent_04_qa_report_v1": pref_dir / "agent_04_qa_report.json",
        "pareto_mc_config_v1": run_dir / "pareto_mc_config.json",
    }

    missing_files = [aid for aid, p in required_paths.items() if not p.is_file()]
    if missing_files:
        raise FileNotFoundError(
            f"Agent 06 required upstream artifact(s) missing for {run_id}: {missing_files}"
        )

    manifest_path = run_dir / "manifest.json"
    manifest_payload: dict[str, Any] | None = None
    verified_inputs: dict[str, dict[str, Any]] = {}
    manifest_mismatches: list[str] = []

    if manifest_path.is_file():
        manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        m_arts = manifest_payload.get("artifacts") or {}
        for aid, fpath in required_paths.items():
            actual_sha = compute_sha256(fpath)
            rel_path = str(fpath.relative_to(root))
            entry: dict[str, Any] = {
                "path": rel_path,
                "sha256": actual_sha,
                "bytes": fpath.stat().st_size,
                "manifest_verified": False,
            }
            if verify_manifest and aid in m_arts:
                exp_sha = _match_manifest_sha(m_arts[aid], rel_path)
                if exp_sha is not None and exp_sha != actual_sha:
                    manifest_mismatches.append(
                        f"{aid} ({rel_path}): expected {exp_sha}, got {actual_sha}"
                    )
                elif exp_sha is not None:
                    entry["manifest_verified"] = True
            verified_inputs[aid] = entry
    else:
        for aid, fpath in required_paths.items():
            verified_inputs[aid] = {
                "path": str(fpath.relative_to(root)),
                "sha256": compute_sha256(fpath),
                "bytes": fpath.stat().st_size,
                "manifest_verified": False,
            }

    if manifest_mismatches:
        raise ValueError(
            f"Manifest SHA-256 verification failed for upstream Agent 04 inputs: {manifest_mismatches}"
        )

    # Load verified inputs
    matrix = load_preference_matrix(required_paths["preference_matrix_v1"])
    fa_payload = json.loads(required_paths["feasible_alternatives_v1"].read_text(encoding="utf-8"))
    pu_payload = json.loads(required_paths["participant_utility_v1"].read_text(encoding="utf-8"))
    pareto_payload = json.loads(required_paths["pareto_results_v1"].read_text(encoding="utf-8"))
    robust_payload = json.loads(required_paths["robust_pareto_results_v1"].read_text(encoding="utf-8"))
    sens_payload = json.loads(required_paths["pareto_sensitivity_v1"].read_text(encoding="utf-8"))
    unc_summary_payload = json.loads(
        required_paths["preference_uncertainty_summary_v1"].read_text(encoding="utf-8")
    )
    qa04_payload = json.loads(required_paths["agent_04_qa_report_v1"].read_text(encoding="utf-8"))
    mc_cfg, mc_path, mc_hash = load_pareto_mc_config(root, run_id)

    solutions = _load_solutions(fa_payload)

    # Structural & Invariant Audits on Loaded Inputs
    if not qa04_payload.get("all_qa_checks_passed"):
        raise ValueError("Agent 04 QA report indicates failed upstream checks.")

    # Check Q01-Q13 spine, Q14 exclusion, zero prohibited pruning
    q14_leaks = [
        s.solution_id for s in solutions if "Q14" in s.included_question_ids or "Q14" in s.question_alternatives
    ]
    prohibited_pruned = [
        s.solution_id
        for s in solutions
        if s.pruned_by_clusters_or_values or s.pruned_by_coder_disagreement or s.pruned_by_coder_confidence
    ]
    uses_conf_weights = [
        r.get("utility_id") for r in (pu_payload.get("participant_utilities") or []) if r.get("uses_coder_confidence_as_weight")
    ]
    ranked_parts = [
        pid
        for pid, diag in (pu_payload.get("participant_diagnostics") or {}).items()
        if diag.get("ranked_as_participant")
    ]

    if q14_leaks:
        raise ValueError(f"Q14 leaked into feasible solutions: {q14_leaks[:5]}")
    if prohibited_pruned:
        raise ValueError(f"Prohibited pruning detected on solutions: {prohibited_pruned[:5]}")
    if uses_conf_weights:
        raise ValueError(f"Prohibited coder_confidence weight detected: {uses_conf_weights[:5]}")
    if ranked_parts:
        raise ValueError(f"Prohibited participant ranking detected upstream: {ranked_parts}")

    # Cross-check canonical counts against Pareto results
    status_counts = robust_payload.get("status_counts") or {}
    baseline_nondom = (pareto_payload.get("pareto_result") or {}).get("nondominated_solution_ids") or []
    robust_core_ids = (robust_payload.get("robust_pareto_result") or {}).get("robustly_nondominated_solution_ids") or []
    high_conf_ids = robust_payload.get("high_confidence_nondominated_ids") or []

    external_ballots = discover_external_ballot_paths(root, run_id, manifest_payload)
    derivation_audit = evaluate_ballot_derivation_legitimacy(matrix, pu_payload)

    raw_csv_path = root / "data" / "raw" / "survey_raw.csv"
    dataset_fp = compute_sha256(raw_csv_path) if raw_csv_path.is_file() else matrix.provenance.dataset_fingerprint

    # Build active ballot validation verdicts
    baldwin_has_ext = external_ballots["baldwin"] is not None
    rrv_has_ext = external_ballots["rrv"] is not None

    method_applicability = {
        "borda_count": {
            "applicability": "APPLICABLE_WITH_ADR0008_SCENARIO_PROPAGATION",
            "reason": (
                "Authorized social-choice rule over PreferenceMatrix/ParticipantUtility scenarios; "
                "must propagate ADR-0008 uncertainty ensembles rather than relying on a single collapsed ranking."
            ),
            "requires_external_ballot_file": False,
        },
        "condorcet_and_minimax": {
            "applicability": "APPLICABLE_WITH_ADR0008_SCENARIO_PROPAGATION",
            "reason": (
                "Authorized pairwise social-choice and minimax worst-defeat rules over admissible ADR-0008 scenarios; "
                "must explicitly report Condorcet cycles and pairwise indeterminacy."
            ),
            "requires_external_ballot_file": False,
        },
        "baldwin": {
            "applicability": (
                "PENDING_EXTERNAL_FILE_VALIDATION"
                if baldwin_has_ext
                else "NOT_APPLICABLE"
            ),
            "execution_status": "PENDING" if baldwin_has_ext else "SKIPPED_NO_VALID_INPUT",
            "external_ballot_file_present": baldwin_has_ext,
            "external_ballot_file_path": str(external_ballots["baldwin"]) if external_ballots["baldwin"] else None,
            "can_legitimately_derive_from_utilities": derivation_audit["can_derive_complete_strict_rankings_without_fabrication"],
            "reason": (
                "Validated active-group ranked ballot file located; subject to ballot schema & fingerprint check."
                if baldwin_has_ext
                else "No active-group ranked ballot file exists for Baldwin elimination, and complete strict ordinal ballots "
                     "cannot be legitimately derived from ParticipantUtility without fabricating over ADR-0008 coding gaps, "
                     "single-coder partial identification, unresolved crosswalks, and null point_utility records."
            ),
        },
        "rrv": {
            "applicability": (
                "PENDING_EXTERNAL_FILE_VALIDATION"
                if rrv_has_ext
                else "NOT_APPLICABLE"
            ),
            "execution_status": "PENDING" if rrv_has_ext else "SKIPPED_NO_VALID_INPUT",
            "external_ballot_file_present": rrv_has_ext,
            "external_ballot_file_path": str(external_ballots["rrv"]) if external_ballots["rrv"] else None,
            "can_legitimately_derive_from_utilities": derivation_audit["can_derive_point_cardinal_ballots_without_fabrication"],
            "reason": (
                "Validated active-group score ballot file located; subject to ballot schema & fingerprint check."
                if rrv_has_ext
                else "No active-group score ballot file exists for RRV committee selection, and exact cardinal ballots "
                     "cannot be legitimately derived from ParticipantUtility without fabricating over null point_utility records, "
                     "missing preference cells, partial identification, and unresolved crosswalk gaps."
            ),
        },
    }

    validation_report = {
        "schema_version": SCHEMA_VERSION,
        "contract_id": "voting_input_validation_v1",
        "run_id": run_id,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "adr_references": ["ADR-0005", "ADR-0007", "ADR-0008"],
        "dataset_fingerprint": dataset_fp,
        "preference_matrix_id": matrix.matrix_id,
        "choice_set_summary": {
            "feasible_solution_count": len(solutions),
            "robustly_nondominated_count": len(robust_core_ids),
            "high_confidence_nondominated_count": len(high_conf_ids),
            "baseline_expected_nondominated_count": len(baseline_nondom),
            "robust_pareto_status_counts": status_counts,
            "participant_count": len(pu_payload.get("valid_participant_ids") or []),
            "excluded_all_missing_participant_ids": pu_payload.get("excluded_all_missing_participant_ids") or [],
            "q14_leaks": len(q14_leaks),
            "prohibited_prunings": len(prohibited_pruned),
            "coder_confidence_weighting_used": False,
            "participants_ranked": False,
        },
        "verified_upstream_inputs": verified_inputs,
        "external_ballots_discovered": {
            "baldwin_input_path": str(external_ballots["baldwin"]) if external_ballots["baldwin"] else None,
            "rrv_input_path": str(external_ballots["rrv"]) if external_ballots["rrv"] else None,
        },
        "ballot_derivation_legitimacy": derivation_audit,
        "method_applicability": method_applicability,
        "validation_passed": True,
    }

    return {
        "validation_report": validation_report,
        "matrix": matrix,
        "solutions": solutions,
        "mc_config": mc_cfg,
        "mc_config_path": mc_path,
        "mc_config_hash": mc_hash,
        "pu_payload": pu_payload,
        "pareto_payload": pareto_payload,
        "robust_payload": robust_payload,
        "sens_payload": sens_payload,
        "unc_summary_payload": unc_summary_payload,
        "external_ballots": external_ballots,
        "dataset_fingerprint": dataset_fp,
    }
