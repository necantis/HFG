"""Conditional Baldwin Sequential Borda Elimination Module (Agent 06).

Owned by: Agent 06 — Voting & Social Choice
Schema Version: 1.0.0 (Aligned with ADR-0005, ADR-0007, and ADR-0008)

Executes Baldwin sequential Borda elimination IF AND ONLY IF a validated
active-group ranked ballot file exists and passes schema, dataset-fingerprint,
anti-cluster-weighting, and non-fabrication checks. Otherwise returns a
contract-compliant BaldwinResult with execution_status="SKIPPED_NO_VALID_INPUT"
and marks the method NOT_APPLICABLE without fabricating complete rankings across
missing preference cells, partial identification, or coding gaps.
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
    BaldwinResult,
    MissingnessState,
    ProvenanceMeta,
    SCHEMA_VERSION,
)
from src.voting.validation import compute_sha256


def _load_ballot_payload(ballot_path: Path) -> dict[str, Any]:
    if ballot_path.suffix.lower() == ".json":
        data = json.loads(ballot_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Baldwin JSON ballot file must be a JSON object.")
        return data
    if ballot_path.suffix.lower() == ".csv":
        ballots: list[dict[str, Any]] = []
        with open(ballot_path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for idx, row in enumerate(reader):
                ranking_raw = str(row.get("ranking") or "").strip()
                ranking = [x.strip() for x in ranking_raw.split(">") if x.strip()] if ranking_raw else []
                ballots.append({
                    "ballot_id": row.get("ballot_id") or f"BAL_{idx + 1:03d}",
                    "ranking": ranking,
                    "is_missing_or_spoiled": str(row.get("is_missing_or_spoiled", "")).lower() in ("true", "1", "yes"),
                    "cluster_weight": row.get("cluster_weight"),
                })
        return {"ballots": ballots}
    raise ValueError(f"Unsupported Baldwin ballot file format: {ballot_path.suffix}")


def validate_baldwin_ballot_file(
    ballot_path: Path | str,
    *,
    run_id: str,
    expected_dataset_fingerprint: str,
    authorized_candidate_ids: set[str] | list[str],
) -> tuple[bool, list[str], dict[str, Any]]:
    """Validate an active-group ranked ballot file before executing Baldwin voting."""
    p = Path(ballot_path)
    errors: list[str] = []
    if not p.is_file():
        return False, [f"Baldwin ballot file not found: {p}"], {}

    try:
        payload = _load_ballot_payload(p)
    except Exception as exc:
        return False, [f"Failed parsing Baldwin ballot file {p}: {exc}"], {}

    file_run_id = payload.get("run_id")
    if file_run_id is not None and str(file_run_id) != run_id:
        errors.append(f"run_id mismatch: ballot file has {file_run_id!r}, expected {run_id!r}.")

    file_fp = payload.get("dataset_fingerprint")
    if file_fp is not None and expected_dataset_fingerprint and str(file_fp) != expected_dataset_fingerprint:
        errors.append(
            f"dataset_fingerprint mismatch: ballot file has {file_fp!r}, expected {expected_dataset_fingerprint!r}."
        )

    if payload.get("synthetic_complete_ballots") or payload.get("imputed_from_coding_gaps"):
        errors.append("Forbidden flag: ballot file marks rankings as synthetically completed or imputed.")
    if payload.get("cluster_weighted_ballots"):
        errors.append("Forbidden flag: cluster_weighted_ballots=True violates equal ballot weight invariant.")

    auth_set = {str(c) for c in authorized_candidate_ids}
    ballots = payload.get("ballots")
    if not isinstance(ballots, list) or not ballots:
        errors.append("Ballot file contains no 'ballots' records.")
        return False, errors, payload

    valid_ballots: list[dict[str, Any]] = []
    spoiled_count = 0
    for idx, b in enumerate(ballots):
        if not isinstance(b, dict):
            errors.append(f"Ballot entry {idx} is not a dict.")
            continue
        if b.get("cluster_weight") not in (None, "", 1, 1.0, "1", "1.0"):
            errors.append(f"Ballot {idx} specifies non-unit cluster_weight={b.get('cluster_weight')!r}.")
        if b.get("weight") not in (None, 1, 1.0):
            errors.append(f"Ballot {idx} specifies non-unit weight={b.get('weight')!r}.")
        if b.get("is_missing_or_spoiled"):
            spoiled_count += 1
            continue
        ranking = b.get("ranking")
        if not isinstance(ranking, list) or not ranking:
            spoiled_count += 1
            continue
        seen: set[str] = set()
        bad_cand = False
        for c in ranking:
            cs = str(c)
            if auth_set and cs not in auth_set:
                errors.append(f"Ballot {idx} contains unauthorized candidate ID {cs!r}.")
                bad_cand = True
                break
            if cs in seen:
                errors.append(f"Ballot {idx} contains duplicate candidate ID {cs!r}.")
                bad_cand = True
                break
            seen.add(cs)
        if not bad_cand:
            valid_ballots.append({
                "ballot_id": str(b.get("ballot_id") or f"B_{idx + 1:03d}"),
                "ranking": [str(c) for c in ranking],
            })

    if not valid_ballots:
        errors.append("Zero valid non-spoiled ballots found in ballot file.")

    # Candidate universe check
    declared_cands = payload.get("candidate_ids")
    if declared_cands is not None:
        bad_decl = [str(c) for c in declared_cands if auth_set and str(c) not in auth_set]
        if bad_decl:
            errors.append(f"Ballot file declares unauthorized candidate_ids: {bad_decl[:5]}")

    parsed_info = {
        "payload": payload,
        "valid_ballots": valid_ballots,
        "missing_or_spoiled_ballot_count": spoiled_count,
        "candidate_ids": [str(c) for c in (declared_cands or sorted({c for b in valid_ballots for c in b["ranking"]}))],
    }
    return len(errors) == 0, errors, parsed_info


def _round_borda_scores(
    active: list[str],
    valid_ballots: list[list[str]],
) -> tuple[dict[str, float], dict[str, int]]:
    """Compute Borda scores over currently active candidates without fabricating unranked comparisons.

    Under standard Borda for partial rankings, a voter ranking k active candidates
    awards (m - 1), (m - 2), ..., (m - k) points to ranked choices in order and
    distributes the remaining tied bottom positions' mean points equally among
    unranked active candidates (so each ballot preserves constant total sum
    m*(m-1)/2 regardless of ballot length, zero synthetic ordering between unranked items).
    """
    m = len(active)
    active_set = set(active)
    scores: dict[str, float] = {c: 0.0 for c in active}
    first_place: dict[str, int] = {c: 0 for c in active}
    if m <= 1:
        for c in active:
            first_place[c] = len(valid_ballots)
        return scores, first_place

    for ballot in valid_ballots:
        filtered = [c for c in ballot if c in active_set]
        for rank_idx, cand in enumerate(filtered):
            scores[cand] += float(m - 1 - rank_idx)
        if filtered:
            first_place[filtered[0]] += 1
        unranked = [c for c in active if c not in filtered]
        if unranked:
            rem_positions = m - len(filtered)
            avg_bottom = 0.5 * (rem_positions - 1)
            for cand in unranked:
                scores[cand] += avg_bottom

    return scores, first_place


def execute_baldwin_from_ballots(
    candidate_ids: list[str],
    valid_ballots: list[list[str]],
    *,
    run_id: str,
    dataset_fingerprint: str,
    input_file_path: str | None,
    input_file_sha256: str | None,
    missing_or_spoiled_ballot_count: int = 0,
    bootstrap_draws: int = 200,
    random_seed: int = 42,
) -> BaldwinResult:
    """Execute Baldwin sequential Borda elimination cleanly on validated ballots."""
    if not candidate_ids or not valid_ballots:
        raise ValueError("execute_baldwin_from_ballots requires non-empty candidate_ids and valid_ballots.")

    def _run_once(ballot_lists: list[list[str]]) -> tuple[list[str], list[dict[str, Any]], float, list[str]]:
        active = list(candidate_ids)
        rounds: list[dict[str, Any]] = []
        min_margin = float("inf")
        initial_ranking: list[str] = []

        r_idx = 0
        while len(active) > 1:
            r_idx += 1
            b_scores, first_counts = _round_borda_scores(active, ballot_lists)
            ordered_desc = sorted(
                active,
                key=lambda c: (-b_scores[c], -first_counts[c], c),
            )
            if r_idx == 1:
                initial_ranking = list(ordered_desc)

            sorted_vals = sorted(b_scores.values())
            min_score = sorted_vals[0]
            if len(sorted_vals) > 1:
                margin = float(sorted_vals[1] - sorted_vals[0])
                min_margin = min(min_margin, margin)

            # Check exact total tie among all remaining candidates
            if abs(max(b_scores.values()) - min_score) <= 1e-9:
                rounds.append({
                    "round": r_idx,
                    "active_candidates": list(active),
                    "borda_scores": {k: round(v, 6) for k, v in b_scores.items()},
                    "eliminated_candidate": None,
                    "tie_detected": True,
                    "note": "All remaining active candidates tied on round Borda scores.",
                })
                break

            lowest_cands = [c for c in active if abs(b_scores[c] - min_score) <= 1e-9]
            # Tie-break: fewest first-place votes, then reverse sorted ID
            eliminated = sorted(lowest_cands, key=lambda c: (first_counts[c], -1, c), reverse=False)[0]
            rounds.append({
                "round": r_idx,
                "active_candidates": list(active),
                "borda_scores": {k: round(v, 6) for k, v in b_scores.items()},
                "eliminated_candidate": eliminated,
                "tie_detected": len(lowest_cands) > 1,
            })
            active = [c for c in active if c != eliminated]

        winners = list(active)
        if min_margin == float("inf"):
            min_margin = 0.0
        return winners, rounds, min_margin, initial_ranking

    winners, rounds, min_margin, initial_ranking = _run_once(valid_ballots)

    # Bootstrap stability across valid ballots
    rng = np.random.default_rng(random_seed)
    n_b = len(valid_ballots)
    boot_counts: dict[str, int] = {c: 0 for c in candidate_ids}
    if bootstrap_draws > 0 and n_b > 1:
        for _ in range(bootstrap_draws):
            idxs = rng.integers(0, n_b, size=n_b)
            sample = [valid_ballots[int(i)] for i in idxs]
            b_win, _, _, _ = _run_once(sample)
            for w in b_win:
                boot_counts[w] = boot_counts.get(w, 0) + 1
        boot_stab = {
            c: round(cnt / bootstrap_draws, 6)
            for c, cnt in boot_counts.items()
            if cnt > 0
        }
    else:
        boot_stab = {w: 1.0 for w in winners}

    return BaldwinResult(
        baldwin_result_id=f"BALDWIN_{run_id}",
        execution_status="EXECUTED",
        missingness_state=(
            MissingnessState.OBSERVED_USABLE
            if missing_or_spoiled_ballot_count == 0
            else MissingnessState.AMBIGUOUS
        ),
        input_file_path=input_file_path,
        input_file_sha256=input_file_sha256,
        candidate_ids=list(candidate_ids),
        valid_ballot_count=len(valid_ballots),
        missing_or_spoiled_ballot_count=missing_or_spoiled_ballot_count,
        elimination_rounds=rounds,
        winner_candidate_ids=winners,
        provenance=ProvenanceMeta(
            record_id=f"BALDWIN_{run_id}",
            run_id=run_id,
            dataset_fingerprint=dataset_fingerprint,
            created_at_utc=datetime.now(timezone.utc).isoformat(),
            producer_module="src/voting/voting_baldwin.py",
            producer_agent="agent_06",
            upstream_artifact_ids=["feasible_alternatives_v1"],
            config_hash="",
            schema_version=SCHEMA_VERSION,
        ),
        tie_margin_min=round(float(min_margin), 6),
        bootstrap_winner_stability=boot_stab,
        tie_breaking_rule_used="MIN_BORDA_THEN_FEWEST_FIRST_PLACE_THEN_LEXICOGRAPHIC",
        borda_initial_ranking=initial_ranking,
        schema_version=SCHEMA_VERSION,
    )


def evaluate_baldwin_voting(
    *,
    run_id: str,
    dataset_fingerprint: str,
    candidate_ids: list[str],
    ballot_file_path: Path | str | None,
    ballot_derivation_audit: dict[str, Any],
    random_seed: int = 42,
) -> tuple[BaldwinResult, dict[str, Any]]:
    """Run conditional Baldwin gate: execute ONLY if validated ballots exist, else NOT_APPLICABLE."""
    now_utc = datetime.now(timezone.utc).isoformat()
    if ballot_file_path is None or not Path(ballot_file_path).is_file():
        res = BaldwinResult(
            baldwin_result_id=f"BALDWIN_{run_id}",
            execution_status="SKIPPED_NO_VALID_INPUT",
            missingness_state=MissingnessState.MISSING_RAW_BLANK,
            input_file_path=None,
            input_file_sha256=None,
            candidate_ids=list(candidate_ids),
            valid_ballot_count=0,
            missing_or_spoiled_ballot_count=0,
            elimination_rounds=[],
            winner_candidate_ids=[],
            provenance=ProvenanceMeta(
                record_id=f"BALDWIN_{run_id}",
                run_id=run_id,
                dataset_fingerprint=dataset_fingerprint,
                created_at_utc=now_utc,
                producer_module="src/voting/voting_baldwin.py",
                producer_agent="agent_06",
                upstream_artifact_ids=["participant_utility_v1", "feasible_alternatives_v1"],
                config_hash="",
                schema_version=SCHEMA_VERSION,
            ),
            tie_margin_min=None,
            bootstrap_winner_stability=None,
            tie_breaking_rule_used=None,
            borda_initial_ranking=None,
            schema_version=SCHEMA_VERSION,
        )
        envelope = {
            "schema_version": SCHEMA_VERSION,
            "contract_id": "baldwin_results_v1",
            "run_id": run_id,
            "generated_at_utc": now_utc,
            "method_name": "Baldwin Sequential Borda Elimination",
            "applicability_status": "NOT_APPLICABLE",
            "execution_status": res.execution_status,
            "not_applicable_reasons": [
                "No external active-group ranked ballot file (baldwin_input_path) exists for this run.",
                *ballot_derivation_audit.get("blocking_reasons", []),
            ],
            "synthetic_ballots_fabricated": False,
            "baldwin_result": asdict(res),
        }
        return res, envelope

    bp = Path(ballot_file_path)
    bp_sha = compute_sha256(bp)
    ok, errors, parsed = validate_baldwin_ballot_file(
        bp,
        run_id=run_id,
        expected_dataset_fingerprint=dataset_fingerprint,
        authorized_candidate_ids=candidate_ids,
    )
    if not ok:
        res = BaldwinResult(
            baldwin_result_id=f"BALDWIN_{run_id}",
            execution_status="FAILED_VALIDATION",
            missingness_state=MissingnessState.AMBIGUOUS,
            input_file_path=str(bp),
            input_file_sha256=bp_sha,
            candidate_ids=list(candidate_ids),
            valid_ballot_count=0,
            missing_or_spoiled_ballot_count=int(parsed.get("missing_or_spoiled_ballot_count", 0)),
            elimination_rounds=[],
            winner_candidate_ids=[],
            provenance=ProvenanceMeta(
                record_id=f"BALDWIN_{run_id}",
                run_id=run_id,
                dataset_fingerprint=dataset_fingerprint,
                created_at_utc=now_utc,
                producer_module="src/voting/voting_baldwin.py",
                producer_agent="agent_06",
                upstream_artifact_ids=["feasible_alternatives_v1"],
                config_hash="",
                schema_version=SCHEMA_VERSION,
            ),
            schema_version=SCHEMA_VERSION,
        )
        envelope = {
            "schema_version": SCHEMA_VERSION,
            "contract_id": "baldwin_results_v1",
            "run_id": run_id,
            "generated_at_utc": now_utc,
            "method_name": "Baldwin Sequential Borda Elimination",
            "applicability_status": "NOT_APPLICABLE",
            "execution_status": res.execution_status,
            "validation_errors": errors,
            "synthetic_ballots_fabricated": False,
            "baldwin_result": asdict(res),
        }
        return res, envelope

    valid_lists = [b["ranking"] for b in parsed["valid_ballots"]]
    res = execute_baldwin_from_ballots(
        candidate_ids=parsed["candidate_ids"],
        valid_ballots=valid_lists,
        run_id=run_id,
        dataset_fingerprint=dataset_fingerprint,
        input_file_path=str(bp),
        input_file_sha256=bp_sha,
        missing_or_spoiled_ballot_count=int(parsed["missing_or_spoiled_ballot_count"]),
        random_seed=random_seed,
    )
    envelope = {
        "schema_version": SCHEMA_VERSION,
        "contract_id": "baldwin_results_v1",
        "run_id": run_id,
        "generated_at_utc": now_utc,
        "method_name": "Baldwin Sequential Borda Elimination",
        "applicability_status": "APPLICABLE",
        "execution_status": res.execution_status,
        "synthetic_ballots_fabricated": False,
        "baldwin_result": asdict(res),
    }
    return res, envelope
