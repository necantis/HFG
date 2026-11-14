"""Conditional Reweighted Range Voting (RRV) Module (Agent 06).

Owned by: Agent 06 — Voting & Social Choice
Schema Version: 1.0.0 (Aligned with ADR-0005, ADR-0007, and ADR-0008)

Executes Reweighted Range Voting (RRV) IF AND ONLY IF a validated active-group
cardinal score ballot file exists and passes schema, dataset-fingerprint,
anti-cluster-weighting, and non-fabrication checks. Explicitly accounts for
small-N (N=11) quota discreteness, committee size sensitivity, leave-one-out
single-ballot sensitivity, and missing/partial ballot sensitivity.
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from src.contracts import (
    MissingnessState,
    ProvenanceMeta,
    RRVResult,
    SCHEMA_VERSION,
)
from src.voting.validation import compute_sha256


def small_n_quota_diagnostics(n_voters: int, seats_to_fill: int) -> dict[str, Any]:
    """Compute exact small-N discreteness and effective quota diagnostics."""
    n = max(0, int(n_voters))
    k_seats = max(1, int(seats_to_fill))
    hare_share = 1.0 / k_seats
    droop_share = 1.0 / (k_seats + 1)
    single_ballot_share = (1.0 / n) if n > 0 else 0.0
    hare_votes_exact = n / k_seats if n > 0 else 0.0
    droop_votes_integer = (n // (k_seats + 1)) + 1 if n > 0 else 0
    return {
        "valid_ballot_count": n,
        "committee_size": k_seats,
        "single_ballot_vote_share": round(single_ballot_share, 6),
        "hare_quota_fraction": round(hare_share, 6),
        "hare_quota_ballots_exact": round(hare_votes_exact, 4),
        "droop_quota_fraction": round(droop_share, 6),
        "droop_quota_ballots_floor_plus_1": droop_votes_integer,
        "achieved_share_resolution_step": round(single_ballot_share, 6),
        "discreteness_note": (
            f"With N={n} voters and committee size {k_seats}, each individual ballot represents "
            f"{100.0 * single_ballot_share:.2f}% of electorate weight; Hare quota is {hare_votes_exact:.2f} ballots "
            f"({100.0 * hare_share:.2f}%) and Droop quota is {droop_votes_integer} ballots ({100.0 * droop_votes_integer / max(1, n):.2f}% effective), "
            "so fractional proportionality claims cannot be resolved finer than 1/N quanta."
        ),
    }


def _load_rrv_ballot_payload(ballot_path: Path) -> dict[str, Any]:
    if ballot_path.suffix.lower() == ".json":
        data = json.loads(ballot_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("RRV JSON ballot file must be a JSON object.")
        return data
    if ballot_path.suffix.lower() == ".csv":
        ballots: list[dict[str, Any]] = []
        with open(ballot_path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            fields = list(reader.fieldnames or [])
            ignore = {"ballot_id", "is_missing_or_spoiled", "cluster_weight", "weight"}
            cands = [c for c in fields if c not in ignore]
            for idx, row in enumerate(reader):
                is_miss = str(row.get("is_missing_or_spoiled", "")).lower() in ("true", "1", "yes")
                scores: dict[str, float] = {}
                for c in cands:
                    raw_v = str(row.get(c, "")).strip()
                    if raw_v != "":
                        scores[c] = float(raw_v)
                ballots.append({
                    "ballot_id": row.get("ballot_id") or f"RRV_{idx + 1:03d}",
                    "scores": scores,
                    "is_missing_or_spoiled": is_miss,
                    "cluster_weight": row.get("cluster_weight"),
                })
        return {"candidate_ids": cands, "ballots": ballots}
    raise ValueError(f"Unsupported RRV ballot file format: {ballot_path.suffix}")


def validate_rrv_ballot_file(
    ballot_path: Path | str,
    *,
    run_id: str,
    expected_dataset_fingerprint: str,
    authorized_candidate_ids: set[str] | list[str],
) -> tuple[bool, list[str], dict[str, Any]]:
    """Validate an active-group cardinal score ballot file prior to RRV execution."""
    p = Path(ballot_path)
    errors: list[str] = []
    if not p.is_file():
        return False, [f"RRV ballot file not found: {p}"], {}

    try:
        payload = _load_rrv_ballot_payload(p)
    except Exception as exc:
        return False, [f"Failed parsing RRV ballot file {p}: {exc}"], {}

    file_run_id = payload.get("run_id")
    if file_run_id is not None and str(file_run_id) != run_id:
        errors.append(f"run_id mismatch: ballot file has {file_run_id!r}, expected {run_id!r}.")

    file_fp = payload.get("dataset_fingerprint")
    if file_fp is not None and expected_dataset_fingerprint and str(file_fp) != expected_dataset_fingerprint:
        errors.append(
            f"dataset_fingerprint mismatch: ballot file has {file_fp!r}, expected {expected_dataset_fingerprint!r}."
        )

    if payload.get("synthetic_complete_ballots") or payload.get("imputed_from_coding_gaps"):
        errors.append("Forbidden flag: ballot file marks cardinal scores as synthetically completed or imputed.")
    if payload.get("cluster_weighted_ballots"):
        errors.append("Forbidden flag: cluster_weighted_ballots=True violates equal ballot weight invariant.")

    s_min = float(payload.get("score_scale_min", 0.0))
    s_max = float(payload.get("score_scale_max", 1.0))
    if s_max <= s_min:
        errors.append(f"Invalid score scale: [{s_min}, {s_max}].")

    k_const = float(payload.get("reweighting_constant_k", 1.0))
    if k_const <= 0.0:
        errors.append(f"Invalid RRV reweighting constant k={k_const} (must be > 0).")

    seats = int(payload.get("seats_to_fill", 3))
    if seats < 1:
        errors.append(f"Invalid seats_to_fill={seats}.")

    auth_set = {str(c) for c in authorized_candidate_ids}
    ballots = payload.get("ballots")
    if not isinstance(ballots, list) or not ballots:
        errors.append("RRV ballot file contains no 'ballots' records.")
        return False, errors, payload

    valid_ballots: list[dict[str, Any]] = []
    missing_count = 0
    partial_count = 0
    cand_universe: set[str] = set()

    for idx, b in enumerate(ballots):
        if not isinstance(b, dict):
            errors.append(f"Ballot entry {idx} is not a dict.")
            continue
        if b.get("cluster_weight") not in (None, "", 1, 1.0, "1", "1.0"):
            errors.append(f"Ballot {idx} specifies non-unit cluster_weight={b.get('cluster_weight')!r}.")
        if b.get("weight") not in (None, 1, 1.0):
            errors.append(f"Ballot {idx} specifies non-unit weight={b.get('weight')!r}.")
        if b.get("is_missing_or_spoiled"):
            missing_count += 1
            continue
        scores = b.get("scores")
        if not isinstance(scores, dict) or not scores:
            missing_count += 1
            continue
        clean_scores: dict[str, float] = {}
        bad_entry = False
        for cid, val in scores.items():
            cs = str(cid)
            if auth_set and cs not in auth_set:
                errors.append(f"Ballot {idx} scores unauthorized candidate ID {cs!r}.")
                bad_entry = True
                break
            fv = float(val)
            if fv < s_min - 1e-9 or fv > s_max + 1e-9:
                errors.append(f"Ballot {idx} score {fv} for {cs} outside [{s_min}, {s_max}].")
                bad_entry = True
                break
            clean_scores[cs] = fv
            cand_universe.add(cs)
        if not bad_entry and clean_scores:
            valid_ballots.append({
                "ballot_id": str(b.get("ballot_id") or f"R_{idx + 1:03d}"),
                "scores": clean_scores,
            })

    declared_cands = [str(c) for c in (payload.get("candidate_ids") or sorted(cand_universe))]
    for b in valid_ballots:
        if len(b["scores"]) < len(declared_cands):
            partial_count += 1

    if not valid_ballots:
        errors.append("Zero valid non-missing score ballots found in RRV ballot file.")
    if seats > len(declared_cands):
        errors.append(f"seats_to_fill ({seats}) exceeds declared candidate count ({len(declared_cands)}).")

    parsed = {
        "payload": payload,
        "valid_ballots": valid_ballots,
        "missing_ballot_count": missing_count,
        "partial_ballot_count": partial_count,
        "candidate_ids": declared_cands,
        "score_scale_min": s_min,
        "score_scale_max": s_max,
        "reweighting_constant_k": k_const,
        "seats_to_fill": seats,
    }
    return len(errors) == 0, errors, parsed


def _run_rrv_core(
    candidate_ids: list[str],
    ballot_scores: list[dict[str, float]],
    *,
    score_scale_min: float,
    score_scale_max: float,
    reweighting_constant_k: float,
    seats_to_fill: int,
) -> tuple[list[str], list[dict[str, Any]], float, dict[str, float]]:
    """Run Warren/Smith RRV selection on normalized cardinal scores."""
    span = score_scale_max - score_scale_min
    n_voters = len(ballot_scores)
    n_cands = len(candidate_ids)
    # Build (n_voters, n_cands) normalized matrix without zero-imputing missing meanings across coding gaps
    # (unscored candidates within an explicit valid ballot contribute 0 score to that candidate's round tally)
    norm_mat = np.zeros((n_voters, n_cands), dtype=np.float64)
    for v_i, sc in enumerate(ballot_scores):
        for c_j, cid in enumerate(candidate_ids):
            if cid in sc:
                norm_mat[v_i, c_j] = np.clip((float(sc[cid]) - score_scale_min) / span, 0.0, 1.0)

    voter_weights = np.ones(n_voters, dtype=np.float64)
    chosen_indices: list[int] = []
    chosen_set: set[int] = set()
    rounds: list[dict[str, Any]] = []
    min_round_margin = float("inf")

    for seat_idx in range(min(seats_to_fill, n_cands)):
        weighted_totals = voter_weights @ norm_mat
        remaining = [j for j in range(n_cands) if j not in chosen_set]
        ordered = sorted(remaining, key=lambda j: (-float(weighted_totals[j]), candidate_ids[j]))
        best_j = ordered[0]
        if len(ordered) > 1:
            margin = float(weighted_totals[ordered[0]] - weighted_totals[ordered[1]])
            min_round_margin = min(min_round_margin, margin)
        chosen_indices.append(best_j)
        chosen_set.add(best_j)

        round_scores = {candidate_ids[j]: round(float(weighted_totals[j]), 6) for j in remaining}
        rounds.append({
            "round": seat_idx + 1,
            "selected_candidate": candidate_ids[best_j],
            "winning_weighted_score": round(float(weighted_totals[best_j]), 6),
            "remaining_candidate_weighted_scores": round_scores,
            "mean_voter_weight_before_update": round(float(voter_weights.mean()), 6),
        })

        # Update voter weights via RRV formula: k / (k + sum_{c in chosen} r_{v,c})
        cum_satisfaction = norm_mat[:, chosen_indices].sum(axis=1)
        voter_weights = reweighting_constant_k / (reweighting_constant_k + cum_satisfaction)

    committee = [candidate_ids[j] for j in chosen_indices]
    if min_round_margin == float("inf"):
        min_round_margin = 0.0

    # Satisfaction & proportionality metrics
    sat_per_voter = norm_mat[:, chosen_indices].sum(axis=1) if chosen_indices else np.zeros(n_voters)
    represented_fraction = float(np.mean(sat_per_voter > 0.0)) if n_voters > 0 else 0.0
    mean_sat = float(np.mean(sat_per_voter)) if n_voters > 0 else 0.0
    min_sat = float(np.min(sat_per_voter)) if n_voters > 0 else 0.0
    prop_metrics = {
        "mean_voter_committee_satisfaction": round(mean_sat, 6),
        "min_voter_committee_satisfaction": round(min_sat, 6),
        "positive_representation_voter_share": round(represented_fraction, 6),
        "effective_hare_quota": round(1.0 / max(1, len(committee)), 6),
        "effective_droop_quota": round(1.0 / (len(committee) + 1), 6),
    }
    return committee, rounds, min_round_margin, prop_metrics


def execute_rrv_from_ballots(
    candidate_ids: list[str],
    valid_ballots: list[dict[str, float]],
    *,
    run_id: str,
    dataset_fingerprint: str,
    input_file_path: str | None,
    input_file_sha256: str | None,
    score_scale_min: float = 0.0,
    score_scale_max: float = 1.0,
    reweighting_constant_k: float = 1.0,
    seats_to_fill: int = 3,
    missing_ballot_count: int = 0,
    bootstrap_draws: int = 200,
    random_seed: int = 42,
) -> tuple[RRVResult, dict[str, Any]]:
    """Execute RRV and compute small-N quota + single-ballot/missing-ballot sensitivity."""
    committee, rounds, min_margin, prop_metrics = _run_rrv_core(
        candidate_ids=candidate_ids,
        ballot_scores=valid_ballots,
        score_scale_min=score_scale_min,
        score_scale_max=score_scale_max,
        reweighting_constant_k=reweighting_constant_k,
        seats_to_fill=seats_to_fill,
    )

    n_b = len(valid_ballots)
    rng = np.random.default_rng(random_seed)
    inc_counts: dict[str, int] = {c: 0 for c in candidate_ids}
    if bootstrap_draws > 0 and n_b > 1:
        for _ in range(bootstrap_draws):
            idxs = rng.integers(0, n_b, size=n_b)
            sample = [valid_ballots[int(i)] for i in idxs]
            b_comm, _, _, _ = _run_rrv_core(
                candidate_ids=candidate_ids,
                ballot_scores=sample,
                score_scale_min=score_scale_min,
                score_scale_max=score_scale_max,
                reweighting_constant_k=reweighting_constant_k,
                seats_to_fill=seats_to_fill,
            )
            for c in b_comm:
                inc_counts[c] = inc_counts.get(c, 0) + 1
        boot_freq = {c: round(cnt / bootstrap_draws, 6) for c, cnt in inc_counts.items() if cnt > 0}
    else:
        boot_freq = {c: 1.0 for c in committee}

    # Aggregate leave-one-out single-ballot sensitivity (NO participant ranking/scoring)
    loo_exact_match_count = 0
    loo_unique_committees: set[tuple[str, ...]] = set()
    if n_b > 1:
        for drop_idx in range(n_b):
            sub_b = [b for i, b in enumerate(valid_ballots) if i != drop_idx]
            l_comm, _, _, _ = _run_rrv_core(
                candidate_ids=candidate_ids,
                ballot_scores=sub_b,
                score_scale_min=score_scale_min,
                score_scale_max=score_scale_max,
                reweighting_constant_k=reweighting_constant_k,
                seats_to_fill=seats_to_fill,
            )
            if set(l_comm) == set(committee):
                loo_exact_match_count += 1
            loo_unique_committees.add(tuple(sorted(l_comm)))

    small_n_diag = small_n_quota_diagnostics(n_b, seats_to_fill)
    small_n_diag["leave_one_ballot_out_exact_committee_preservation_rate"] = (
        round(loo_exact_match_count / n_b, 6) if n_b > 1 else 1.0
    )
    small_n_diag["leave_one_ballot_out_distinct_committee_count"] = len(loo_unique_committees)
    small_n_diag["missing_ballot_count"] = missing_ballot_count

    res = RRVResult(
        rrv_result_id=f"RRV_{run_id}",
        execution_status="EXECUTED",
        missingness_state=(
            MissingnessState.OBSERVED_USABLE
            if missing_ballot_count == 0
            else MissingnessState.AMBIGUOUS
        ),
        input_file_path=input_file_path,
        input_file_sha256=input_file_sha256,
        score_scale_min=score_scale_min,
        score_scale_max=score_scale_max,
        reweighting_constant_k=reweighting_constant_k,
        seats_to_fill=seats_to_fill,
        valid_ballot_count=n_b,
        missing_ballot_count=missing_ballot_count,
        selection_rounds=rounds,
        selected_committee_ids=committee,
        provenance=ProvenanceMeta(
            record_id=f"RRV_{run_id}",
            run_id=run_id,
            dataset_fingerprint=dataset_fingerprint,
            created_at_utc=datetime.now(timezone.utc).isoformat(),
            producer_module="src/voting/voting_rrv.py",
            producer_agent="agent_06",
            upstream_artifact_ids=["feasible_alternatives_v1"],
            config_hash="",
            schema_version=SCHEMA_VERSION,
        ),
        round_margin_min=round(float(min_margin), 6),
        bootstrap_committee_inclusion_freq=boot_freq,
        proportionality_satisfaction_metrics=prop_metrics,
        schema_version=SCHEMA_VERSION,
    )
    return res, small_n_diag


def evaluate_rrv_voting(
    *,
    run_id: str,
    dataset_fingerprint: str,
    candidate_ids: list[str],
    ballot_file_path: Path | str | None,
    ballot_derivation_audit: dict[str, Any],
    participant_count: int = 11,
    default_committee_size: int = 3,
    random_seed: int = 42,
) -> tuple[RRVResult, dict[str, Any]]:
    """Run conditional RRV gate: execute ONLY if validated score ballots exist, else NOT_APPLICABLE."""
    now_utc = datetime.now(timezone.utc).isoformat()
    quota_ref = small_n_quota_diagnostics(participant_count, default_committee_size)

    if ballot_file_path is None or not Path(ballot_file_path).is_file():
        res = RRVResult(
            rrv_result_id=f"RRV_{run_id}",
            execution_status="SKIPPED_NO_VALID_INPUT",
            missingness_state=MissingnessState.MISSING_RAW_BLANK,
            input_file_path=None,
            input_file_sha256=None,
            score_scale_min=None,
            score_scale_max=None,
            reweighting_constant_k=None,
            seats_to_fill=default_committee_size,
            valid_ballot_count=0,
            missing_ballot_count=participant_count,
            selection_rounds=[],
            selected_committee_ids=[],
            provenance=ProvenanceMeta(
                record_id=f"RRV_{run_id}",
                run_id=run_id,
                dataset_fingerprint=dataset_fingerprint,
                created_at_utc=now_utc,
                producer_module="src/voting/voting_rrv.py",
                producer_agent="agent_06",
                upstream_artifact_ids=["participant_utility_v1", "feasible_alternatives_v1"],
                config_hash="",
                schema_version=SCHEMA_VERSION,
            ),
            round_margin_min=None,
            bootstrap_committee_inclusion_freq=None,
            proportionality_satisfaction_metrics=None,
            schema_version=SCHEMA_VERSION,
        )
        envelope = {
            "schema_version": SCHEMA_VERSION,
            "contract_id": "rrv_results_v1",
            "run_id": run_id,
            "generated_at_utc": now_utc,
            "method_name": "Reweighted Range Voting (RRV)",
            "applicability_status": "NOT_APPLICABLE",
            "execution_status": res.execution_status,
            "not_applicable_reasons": [
                "No external active-group score ballot file (rrv_input_path) exists for this run.",
                *ballot_derivation_audit.get("blocking_reasons", []),
            ],
            "synthetic_ballots_fabricated": False,
            "small_n_quota_context": quota_ref,
            "rrv_result": asdict(res),
        }
        return res, envelope

    bp = Path(ballot_file_path)
    bp_sha = compute_sha256(bp)
    ok, errors, parsed = validate_rrv_ballot_file(
        bp,
        run_id=run_id,
        expected_dataset_fingerprint=dataset_fingerprint,
        authorized_candidate_ids=candidate_ids,
    )
    if not ok:
        res = RRVResult(
            rrv_result_id=f"RRV_{run_id}",
            execution_status="FAILED_VALIDATION",
            missingness_state=MissingnessState.AMBIGUOUS,
            input_file_path=str(bp),
            input_file_sha256=bp_sha,
            score_scale_min=parsed.get("score_scale_min"),
            score_scale_max=parsed.get("score_scale_max"),
            reweighting_constant_k=parsed.get("reweighting_constant_k"),
            seats_to_fill=int(parsed.get("seats_to_fill", default_committee_size)),
            valid_ballot_count=0,
            missing_ballot_count=int(parsed.get("missing_ballot_count", participant_count)),
            selection_rounds=[],
            selected_committee_ids=[],
            provenance=ProvenanceMeta(
                record_id=f"RRV_{run_id}",
                run_id=run_id,
                dataset_fingerprint=dataset_fingerprint,
                created_at_utc=now_utc,
                producer_module="src/voting/voting_rrv.py",
                producer_agent="agent_06",
                upstream_artifact_ids=["feasible_alternatives_v1"],
                config_hash="",
                schema_version=SCHEMA_VERSION,
            ),
            schema_version=SCHEMA_VERSION,
        )
        envelope = {
            "schema_version": SCHEMA_VERSION,
            "contract_id": "rrv_results_v1",
            "run_id": run_id,
            "generated_at_utc": now_utc,
            "method_name": "Reweighted Range Voting (RRV)",
            "applicability_status": "NOT_APPLICABLE",
            "execution_status": res.execution_status,
            "validation_errors": errors,
            "synthetic_ballots_fabricated": False,
            "small_n_quota_context": quota_ref,
            "rrv_result": asdict(res),
        }
        return res, envelope

    valid_scores = [b["scores"] for b in parsed["valid_ballots"]]
    res, small_n_diag = execute_rrv_from_ballots(
        candidate_ids=parsed["candidate_ids"],
        valid_ballots=valid_scores,
        run_id=run_id,
        dataset_fingerprint=dataset_fingerprint,
        input_file_path=str(bp),
        input_file_sha256=bp_sha,
        score_scale_min=float(parsed["score_scale_min"]),
        score_scale_max=float(parsed["score_scale_max"]),
        reweighting_constant_k=float(parsed["reweighting_constant_k"]),
        seats_to_fill=int(parsed["seats_to_fill"]),
        missing_ballot_count=int(parsed["missing_ballot_count"]),
        random_seed=random_seed,
    )
    small_n_diag["partial_ballot_count"] = int(parsed.get("partial_ballot_count", 0))
    envelope = {
        "schema_version": SCHEMA_VERSION,
        "contract_id": "rrv_results_v1",
        "run_id": run_id,
        "generated_at_utc": now_utc,
        "method_name": "Reweighted Range Voting (RRV)",
        "applicability_status": "APPLICABLE",
        "execution_status": res.execution_status,
        "synthetic_ballots_fabricated": False,
        "small_n_proportionality_diagnostics": small_n_diag,
        "rrv_result": asdict(res),
    }
    return res, envelope
