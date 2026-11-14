"""ADR-0008 Preference Matrix Builder & Provenance Verifier for Agent 04.

Owned by: Agent 04 — Preference, Utility & Pareto
Schema Version: 1.0.0 (Aligned with ADR-0005 and ADR-0008)

Constructs the canonical distributional and uncertainty-set PreferenceMatrix
exclusively from Agent 01/03 reconciled inputs without:
- rerunning LLM coders or Agent 03 reconciliation;
- imputing 0.0 into missingness or single-coder silent sides;
- collapsing unresolved disagreement, crosswalk gaps, or ISSUE-005
  probability_interpretation divergences into synthetic point distributions.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src.contracts import (
    AgreementStatus,
    CanonicalAlternativeCrosswalk,
    CrosswalkStatus,
    FORBIDDEN_RECONCILIATION_METHODS,
    MissingnessState,
    PreferenceCell,
    PreferenceMatrix,
    PreferenceUncertaintySet,
    ProvenanceMeta,
    ReconciliationStatus,
    SCHEMA_VERSION,
    UncertaintyClass,
)


PRIMARY_QUESTION_IDS: tuple[str, ...] = tuple(f"Q{i:02d}" for i in range(1, 14))
CONTEXTUAL_QUESTION_IDS: tuple[str, ...] = ("Q14",)


def compute_sha256(path: Path) -> str:
    """Return lowercase hex SHA-256 digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def get_git_commit_sha(base_dir: Path) -> str:
    """Resolve current HEAD commit SHA safely."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=base_dir,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if res.returncode == 0:
            return res.stdout.strip()
    except Exception:
        pass
    return "UNKNOWN"


def load_pareto_mc_config(
    base_dir: Path | str,
    run_id: str = "run_20261111_002",
) -> tuple[dict[str, Any], str, str]:
    """Load configurable Pareto Monte Carlo runtime config and return (config, rel_path, sha256)."""
    root = Path(base_dir).resolve()
    cfg_path = root / "runs" / run_id / "pareto_mc_config.json"
    if not cfg_path.is_file():
        raise FileNotFoundError(
            f"Required configurable Agent 04 runtime parameter file missing: {cfg_path}"
        )
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    if cfg.get("run_id") != run_id:
        raise ValueError(
            f"pareto_mc_config.json run_id mismatch: expected {run_id}, got {cfg.get('run_id')}"
        )
    rel_path = str(cfg_path.relative_to(root))
    return cfg, rel_path, compute_sha256(cfg_path)


def _normalize_enum_dict(obj: Any) -> Any:
    """Recursively convert dataclass/Enum structures to JSON-serializable primitives."""
    if hasattr(obj, "value") and isinstance(obj, object):
        try:
            from enum import Enum
            if isinstance(obj, Enum):
                return obj.value
        except Exception:
            pass
    if isinstance(obj, dict):
        return {str(k): _normalize_enum_dict(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_normalize_enum_dict(v) for v in obj]
    return obj


def _coerce_missingness(raw_state: Any) -> MissingnessState:
    if isinstance(raw_state, MissingnessState):
        return raw_state
    return MissingnessState(str(raw_state))


def _deserialize_crosswalk(raw_cw: dict[str, Any] | None) -> CanonicalAlternativeCrosswalk | None:
    if not raw_cw:
        return None
    sp = raw_cw.get("scope_pair")
    scope_pair = tuple(sp) if isinstance(sp, (list, tuple)) and len(sp) == 2 else None
    return CanonicalAlternativeCrosswalk(
        question_id=str(raw_cw["question_id"]),
        canonical_subtopic_id=str(raw_cw["canonical_subtopic_id"]),
        crosswalk_status=CrosswalkStatus(str(raw_cw["crosswalk_status"])),
        comparable=bool(raw_cw["comparable"]),
        coder_a_to_canonical={str(k): str(v) for k, v in (raw_cw.get("coder_a_to_canonical") or {}).items()},
        coder_b_to_canonical={str(k): str(v) for k, v in (raw_cw.get("coder_b_to_canonical") or {}).items()},
        canonical_keys=[str(k) for k in (raw_cw.get("canonical_keys") or [])],
        unmapped_keys_a=[str(k) for k in (raw_cw.get("unmapped_keys_a") or [])],
        unmapped_keys_b=[str(k) for k in (raw_cw.get("unmapped_keys_b") or [])],
        unmapped_mass_a=float(raw_cw.get("unmapped_mass_a", 0.0)),
        unmapped_mass_b=float(raw_cw.get("unmapped_mass_b", 0.0)),
        crosswalk_rule_id=raw_cw.get("crosswalk_rule_id"),
        provenance_rationale=raw_cw.get("provenance_rationale"),
        lossless_deterministic_aggregation=bool(raw_cw.get("lossless_deterministic_aggregation", False)),
        scope_pair=scope_pair,  # type: ignore[arg-type]
        schema_version=str(raw_cw.get("schema_version", SCHEMA_VERSION)),
    )


def _deserialize_uncertainty_set(raw_pus: dict[str, Any] | None) -> PreferenceUncertaintySet | None:
    if not raw_pus:
        return None
    return PreferenceUncertaintySet(
        representation_type=raw_pus["representation_type"],
        discrete_scenarios=[
            {str(k): float(v) for k, v in sc.items()}
            for sc in (raw_pus.get("discrete_scenarios") or [])
        ],
        disjoint_coder_hypotheses={
            str(side): {str(k): float(v) for k, v in dist.items()}
            for side, dist in (raw_pus.get("disjoint_coder_hypotheses") or {}).items()
            if dist is not None
        },
        lower_bounds=(
            {str(k): float(v) for k, v in raw_pus["lower_bounds"].items()}
            if raw_pus.get("lower_bounds") is not None
            else None
        ),
        upper_bounds=(
            {str(k): float(v) for k, v in raw_pus["upper_bounds"].items()}
            if raw_pus.get("upper_bounds") is not None
            else None
        ),
        interpretation_variants=list(raw_pus.get("interpretation_variants") or []),
        single_coder_active_side=raw_pus.get("single_coder_active_side"),
        single_coder_uncertainty_type=raw_pus.get("single_coder_uncertainty_type"),
        non_coding_coder_state=raw_pus.get("non_coding_coder_state"),
        allows_derived_convex_hull=bool(raw_pus.get("allows_derived_convex_hull", False)),
        derived_scenarios=list(raw_pus.get("derived_scenarios") or []),
        scenario_origin=raw_pus.get("scenario_origin", "OBSERVED_CODER_EVIDENCE"),
        double_count_guard_applied=bool(raw_pus.get("double_count_guard_applied", False)),
        schema_version=str(raw_pus.get("schema_version", SCHEMA_VERSION)),
    )


class PreferenceMatrixBuilder:
    """Build and persist the validated ADR-0008 PreferenceMatrix from reconciled Agent 03 outputs."""

    def __init__(
        self,
        base_dir: Path | str,
        run_id: str = "run_20261111_002",
    ) -> None:
        self.base_dir = Path(base_dir).resolve()
        self.run_id = run_id

    def verify_upstream_manifest(self) -> dict[str, Any]:
        """Verify canonical Agent 03 artifacts in runs/<run_id>/manifest.json match staged files."""
        manifest_path = self.base_dir / "runs" / self.run_id / "manifest.json"
        if not manifest_path.is_file():
            raise FileNotFoundError(f"Canonical manifest missing: {manifest_path}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        artifacts = manifest.get("artifacts") or {}

        required_artifact_ids = [
            "themes_codebook_v1",
            "candidate_options_v1",
            "reconciled_evidence_v1",
            "subtopic_alignment_v1",
            "reconciled_values_v1",
            "coder_agreement_stats_v1",
            "unresolved_cases_registry_v1",
            "alternative_crosswalk_summary_v1",
            "reconciliation_qa_report_v1",
        ]
        verified: dict[str, dict[str, Any]] = {}
        for aid in required_artifact_ids:
            entry = artifacts.get(aid)
            if not isinstance(entry, dict):
                raise ValueError(f"Required Agent 03 artifact '{aid}' missing in manifest.json")
            if entry.get("validation_status") != "valid":
                raise ValueError(
                    f"Required Agent 03 artifact '{aid}' has validation_status={entry.get('validation_status')!r}"
                )
            rel_path = entry.get("path")
            fpath = self.base_dir / str(rel_path)
            if not fpath.is_file():
                raise FileNotFoundError(
                    f"Registered canonical input '{aid}' missing at runtime path {fpath}"
                )
            actual_sha = compute_sha256(fpath)
            src_hashes = entry.get("source_hashes") or {}
            expected_sha = str(
                entry.get("sha256")
                or entry.get("content_sha256")
                or next((h for k, h in src_hashes.items() if str(k).endswith(str(rel_path))), "")
            )
            if not expected_sha or actual_sha != expected_sha:
                raise ValueError(
                    f"SHA-256 mismatch for canonical input '{aid}': expected {expected_sha!r}, got {actual_sha!r}"
                )
            verified[aid] = {
                "path": str(rel_path),
                "sha256": actual_sha,
                "schema_version": entry.get("schema_version"),
                "producing_agent": entry.get("producing_agent"),
                "authority_level": entry.get("authority_level"),
                "stale_state": entry.get("stale_state"),
                "validation_status": entry.get("validation_status"),
            }
        return {
            "manifest_path": str(manifest_path.relative_to(self.base_dir)),
            "manifest_sha256": compute_sha256(manifest_path),
            "verified_inputs": verified,
        }

    def build(
        self,
        *,
        simplex_tolerance: float = 1e-4,
        config_hash: str = "",
        verify_manifest: bool = True,
    ) -> tuple[PreferenceMatrix, dict[str, dict[str, Any]]]:
        """Construct PreferenceMatrix and per-cell companion diagnostics cleanly without imputation."""
        proc_dir = self.base_dir / "data" / "processed"
        rec_dir = proc_dir / "reconciliation"
        norm_dir = self.base_dir / "data" / "normalized"

        upstream_report = self.verify_upstream_manifest() if verify_manifest else {"verified_inputs": {}}

        reconciled_path = rec_dir / "reconciled_evidence.json"
        themes_path = proc_dir / "themes_codebook.json"
        answers_path = norm_dir / "answers_normalized.parquet"
        qa_path = rec_dir / "reconciliation_qa_report.json"

        reconciled_payload = json.loads(reconciled_path.read_text(encoding="utf-8"))
        themes_payload = json.loads(themes_path.read_text(encoding="utf-8"))
        qa_payload = json.loads(qa_path.read_text(encoding="utf-8"))
        answers_df = pd.read_parquet(answers_path)

        if not qa_payload.get("all_reconciliation_invariants_passed"):
            raise ValueError("Agent 03 reconciliation_qa_report.json reports failed invariants.")

        records = reconciled_payload.get("preference_reconciliation_records") or []
        if not records:
            raise ValueError("reconciled_evidence.json contains zero preference_reconciliation_records.")

        subtopics_by_id = {
            str(st["subtopic_id"]): st
            for st in themes_payload.get("canonical_subtopics", [])
        }
        dataset_fp = compute_sha256(self.base_dir / "data" / "raw" / "survey_raw.csv")
        created_utc = datetime.now(timezone.utc).isoformat()
        upstream_ids = sorted(upstream_report.get("verified_inputs", {}).keys()) or [
            "answers_normalized_v1",
            "themes_codebook_v1",
            "reconciled_evidence_v1",
        ]

        cells: list[PreferenceCell] = []
        cell_diagnostics: dict[str, dict[str, Any]] = {}

        participant_ids = sorted(answers_df["participant_id"].astype(str).unique().tolist())
        question_ids = sorted(
            {str(r["question_id"]) for r in records} | set(answers_df["question_id"].astype(str).unique().tolist())
        )
        # Ensure primary Q01-Q13 precede contextual Q14 cleanly
        primary_present = [q for q in PRIMARY_QUESTION_IDS if q in question_ids]
        contextual_present = [q for q in CONTEXTUAL_QUESTION_IDS if q in question_ids]
        other_qs = [q for q in question_ids if q not in primary_present and q not in contextual_present]
        ordered_question_ids = primary_present + other_qs + contextual_present

        subtopic_to_question: dict[str, str] = {}
        uc_counts: Counter[str] = Counter()
        flagged_low_agreement: list[str] = []

        usable_agreements: list[float] = []
        usable_confidences: list[float] = []
        observed_usable_count = 0
        unobserved_missing_count = 0
        infeasible_choice_count = 0
        ambiguous_count = 0

        q_usable: Counter[str] = Counter()
        q_total: Counter[str] = Counter()
        p_usable: Counter[str] = Counter()
        p_total: Counter[str] = Counter()

        for rec in records:
            method = rec.get("reconciliation_method")
            if method in FORBIDDEN_RECONCILIATION_METHODS:
                raise ValueError(
                    f"Forbidden reconciliation method {method!r} detected in {rec.get('record_id')}"
                )

            cell_id = str(rec["record_id"])
            pid = str(rec["participant_id"])
            qid = str(rec["question_id"])
            sub_id = str(rec["canonical_subtopic_id"])
            subtopic_to_question[sub_id] = qid

            miss_state = _coerce_missingness(rec["missingness_state"])
            u_class = UncertaintyClass(str(rec["uncertainty_class"]))
            uc_counts[u_class.value] += 1

            cw = _deserialize_crosswalk(rec.get("canonical_alternative_crosswalk"))
            pus = _deserialize_uncertainty_set(rec.get("preference_uncertainty_set"))
            if pus is None:
                raise ValueError(f"Record {cell_id} missing preference_uncertainty_set.")

            resolved_pt = rec.get("resolved_point_distribution")
            if u_class != UncertaintyClass.NONE_CONSENSUS and resolved_pt is not None:
                raise ValueError(
                    f"Record {cell_id}: non-consensus uncertainty_class={u_class.value} must have resolved_point_distribution=None."
                )

            alt_probs: dict[str, float] = {}
            if u_class == UncertaintyClass.NONE_CONSENSUS and miss_state.is_usable():
                if not resolved_pt:
                    raise ValueError(f"Record {cell_id}: NONE_CONSENSUS missing resolved_point_distribution.")
                alt_probs = {str(k): float(v) for k, v in resolved_pt.items()}

            imp_a = float(rec["semantic_importance_a"]) if rec.get("semantic_importance_a") is not None else None
            imp_b = float(rec["semantic_importance_b"]) if rec.get("semantic_importance_b") is not None else None
            conf_a = float(rec["coder_confidence_a"]) if rec.get("coder_confidence_a") is not None else None
            conf_b = float(rec["coder_confidence_b"]) if rec.get("coder_confidence_b") is not None else None

            imp_vals = [v for v in (imp_a, imp_b) if v is not None]
            conf_vals = [v for v in (conf_a, conf_b) if v is not None]
            sem_imp = (sum(imp_vals) / len(imp_vals)) if imp_vals else None
            coder_conf = (sum(conf_vals) / len(conf_vals)) if conf_vals else None

            dist_sim = rec.get("distribution_similarity_1_minus_tvd")
            if dist_sim is not None:
                coder_agree: float | None = float(dist_sim)
            elif u_class == UncertaintyClass.NONE_CONSENSUS or u_class == UncertaintyClass.INTERPRETATION_DIVERGENCE:
                coder_agree = 1.0
            else:
                coder_agree = None

            ev_ids = [str(e) for e in (rec.get("source_evidence_ids") or [])]

            a_interp = rec.get("coder_a_probability_interpretation")
            b_interp = rec.get("coder_b_probability_interpretation")
            cell_interp = None
            if a_interp is not None and a_interp == b_interp:
                cell_interp = a_interp
            elif len(pus.interpretation_variants) == 1:
                cell_interp = pus.interpretation_variants[0]

            raw_a = (
                {str(k): float(v) for k, v in rec["coder_a_distribution"].items()}
                if rec.get("coder_a_distribution") is not None
                else None
            )
            raw_b = (
                {str(k): float(v) for k, v in rec["coder_b_distribution"].items()}
                if rec.get("coder_b_distribution") is not None
                else None
            )

            # Safeguard single-coder invariants
            if u_class in {
                UncertaintyClass.SINGLE_CODER_PARTIAL_ID_OMISSION,
                UncertaintyClass.SINGLE_CODER_PARTIAL_ID_GRANULARITY,
            }:
                if (raw_a is not None) and (raw_b is not None):
                    raise ValueError(f"Record {cell_id}: single-coder class has both distributions populated.")
                if (raw_a is None) and (raw_b is None):
                    raise ValueError(f"Record {cell_id}: single-coder class lacks any distribution.")

            st_info = subtopics_by_id.get(sub_id, {})
            econ_good = st_info.get("dominant_economic_good_class")

            lower_b = dict(pus.lower_bounds) if pus.lower_bounds is not None else None
            upper_b = dict(pus.upper_bounds) if pus.upper_bounds is not None else None

            prov = ProvenanceMeta(
                record_id=f"PCELL_{cell_id}",
                run_id=self.run_id,
                dataset_fingerprint=dataset_fp,
                created_at_utc=created_utc,
                producer_module="src/preference/preference_matrix.py",
                producer_agent="agent_04",
                upstream_artifact_ids=upstream_ids,
                config_hash=config_hash,
                schema_version=SCHEMA_VERSION,
            )

            cell = PreferenceCell(
                cell_id=cell_id,
                participant_id=pid,
                question_id=qid,
                subtopic_id=sub_id,
                missingness_state=miss_state,
                alternative_probabilities=alt_probs,
                semantic_importance=sem_imp,
                coder_confidence=coder_conf,
                coder_agreement=coder_agree,
                source_coding_id=cell_id,
                evidence_span_ids=ev_ids,
                provenance=prov,
                probability_lower_bounds=lower_b,
                probability_upper_bounds=upper_b,
                probability_interpretation=cell_interp,  # type: ignore[arg-type]
                derived_scalar_score=None,
                coder_a_probabilities=raw_a,
                coder_b_probabilities=raw_b,
                coder_a_importance=imp_a,
                coder_b_importance=imp_b,
                economic_good_class=econ_good,
                question_or_dimension_id=qid,
                evidence_ids=ev_ids,
                canonical_subtopic_id=sub_id,
                coder_a_distribution=raw_a,
                coder_b_distribution=raw_b,
                canonical_alternative_crosswalk=cw,
                coder_a_probability_interpretation=a_interp,
                coder_b_probability_interpretation=b_interp,
                semantic_importance_a=imp_a,
                semantic_importance_b=imp_b,
                coder_confidence_a=conf_a,
                coder_confidence_b=conf_b,
                agreement_status=AgreementStatus(str(rec["agreement_status"])),
                uncertainty_class=u_class,
                preference_uncertainty_set=pus,
                source_evidence_ids=ev_ids,
                reconciliation_status=ReconciliationStatus(str(rec["reconciliation_status"])),
                resolved_point_distribution=resolved_pt if u_class == UncertaintyClass.NONE_CONSENSUS else None,
                schema_version=SCHEMA_VERSION,
            )
            cell.validate_simplex(tolerance=simplex_tolerance)
            cells.append(cell)

            q_total[qid] += 1
            p_total[pid] += 1
            if miss_state.is_usable():
                observed_usable_count += 1
                q_usable[qid] += 1
                p_usable[pid] += 1
                if coder_agree is not None:
                    usable_agreements.append(coder_agree)
                    if coder_agree < 0.7:
                        flagged_low_agreement.append(cell_id)
                elif cw is not None and cw.crosswalk_status == CrosswalkStatus.NO_VALID_CROSSWALK:
                    flagged_low_agreement.append(cell_id)
                if coder_conf is not None:
                    usable_confidences.append(coder_conf)
            else:
                canon_m = miss_state.to_canonical_cell_state()
                if canon_m == MissingnessState.INFEASIBLE_CHOICE.value:
                    infeasible_choice_count += 1
                elif canon_m == MissingnessState.AMBIGUOUS.value:
                    ambiguous_count += 1
                else:
                    unobserved_missing_count += 1

            cell_diagnostics[cell_id] = {
                "is_primary_question": qid in PRIMARY_QUESTION_IDS,
                "question_scope": "primary" if qid in PRIMARY_QUESTION_IDS else "optional_contextual_remarks",
                "alignment_category": st_info.get("alignment_category"),
                "is_minority_position": bool(st_info.get("is_minority_position", False)),
                "phase2_split_subtopic": bool(st_info.get("phase2_split_subtopic", False)),
                "double_count_guard_applied": bool(pus.double_count_guard_applied),
                "tvd": rec.get("total_variation_distance"),
                "crosswalk_status": cw.crosswalk_status.value if cw else None,
                "single_coder_uncertainty_type": (
                    pus.single_coder_uncertainty_type.value if pus.single_coder_uncertainty_type else None
                ),
            }

        subtopic_ids = sorted(subtopic_to_question.keys())
        q_cov = {q: (q_usable[q] / q_total[q] if q_total[q] > 0 else 0.0) for q in ordered_question_ids}
        p_cov = {p: (p_usable[p] / p_total[p] if p_total[p] > 0 else 0.0) for p in participant_ids}

        mean_agree = (sum(usable_agreements) / len(usable_agreements)) if usable_agreements else 0.0
        mean_conf = (sum(usable_confidences) / len(usable_confidences)) if usable_confidences else 0.0

        matrix = PreferenceMatrix(
            matrix_id=f"PM_{self.run_id}_adr0008",
            participant_ids=participant_ids,
            question_ids=ordered_question_ids,
            subtopic_ids=subtopic_ids,
            subtopic_to_question=subtopic_to_question,
            cells=cells,
            observed_usable_cell_count=observed_usable_count,
            unobserved_missing_cell_count=unobserved_missing_count,
            infeasible_choice_cell_count=infeasible_choice_count,
            ambiguous_cell_count=ambiguous_count,
            overall_coder_agreement_mean=round(mean_agree, 6),
            overall_coder_confidence_mean=round(mean_conf, 6),
            validation_passed=True,
            provenance=ProvenanceMeta(
                record_id=f"PM_{self.run_id}_adr0008",
                run_id=self.run_id,
                dataset_fingerprint=dataset_fp,
                created_at_utc=created_utc,
                producer_module="src/preference/preference_matrix.py",
                producer_agent="agent_04",
                upstream_artifact_ids=upstream_ids,
                config_hash=config_hash,
                schema_version=SCHEMA_VERSION,
            ),
            question_coverage_rates=q_cov,
            participant_response_rates=p_cov,
            flagged_low_agreement_cell_ids=sorted(set(flagged_low_agreement)),
            uncertainty_class_counts=dict(sorted(uc_counts.items())),
            schema_version=SCHEMA_VERSION,
        )
        return matrix, cell_diagnostics

    def save(
        self,
        matrix: PreferenceMatrix,
        cell_diagnostics: dict[str, dict[str, Any]],
    ) -> dict[str, Path]:
        """Persist canonical data/processed/preference_matrix.parquet and structured JSON."""
        proc_dir = self.base_dir / "data" / "processed"
        pref_dir = proc_dir / "preference"
        pref_dir.mkdir(parents=True, exist_ok=True)

        parquet_path = proc_dir / "preference_matrix.parquet"
        json_path = pref_dir / "preference_matrix.json"

        rows: list[dict[str, Any]] = []
        for c in matrix.cells:
            diag = cell_diagnostics.get(c.cell_id, {})
            rows.append(
                {
                    "matrix_id": matrix.matrix_id,
                    "cell_id": c.cell_id,
                    "participant_id": c.participant_id,
                    "question_id": c.question_id,
                    "canonical_subtopic_id": c.canonical_subtopic_id or c.subtopic_id,
                    "is_primary_question": bool(diag.get("is_primary_question", c.question_id != "Q14")),
                    "question_scope": diag.get(
                        "question_scope",
                        "primary" if c.question_id != "Q14" else "optional_contextual_remarks",
                    ),
                    "missingness_state": c.missingness_state.value,
                    "uncertainty_class": c.uncertainty_class.value if c.uncertainty_class else None,
                    "agreement_status": c.agreement_status.value if c.agreement_status else None,
                    "reconciliation_status": c.reconciliation_status.value if c.reconciliation_status else None,
                    "crosswalk_status": (
                        c.canonical_alternative_crosswalk.crosswalk_status.value
                        if c.canonical_alternative_crosswalk
                        else None
                    ),
                    "alternative_probabilities_json": json.dumps(c.alternative_probabilities, sort_keys=True),
                    "resolved_point_distribution_json": (
                        json.dumps(c.resolved_point_distribution, sort_keys=True)
                        if c.resolved_point_distribution is not None
                        else None
                    ),
                    "coder_a_distribution_json": (
                        json.dumps(c.coder_a_distribution, sort_keys=True)
                        if c.coder_a_distribution is not None
                        else None
                    ),
                    "coder_b_distribution_json": (
                        json.dumps(c.coder_b_distribution, sort_keys=True)
                        if c.coder_b_distribution is not None
                        else None
                    ),
                    "coder_a_probability_interpretation": c.coder_a_probability_interpretation,
                    "coder_b_probability_interpretation": c.coder_b_probability_interpretation,
                    "probability_interpretation": c.probability_interpretation,
                    "semantic_importance": c.semantic_importance,
                    "semantic_importance_a": c.semantic_importance_a,
                    "semantic_importance_b": c.semantic_importance_b,
                    "coder_confidence": c.coder_confidence,
                    "coder_confidence_a": c.coder_confidence_a,
                    "coder_confidence_b": c.coder_confidence_b,
                    "coder_agreement": c.coder_agreement,
                    "double_count_guard_applied": bool(diag.get("double_count_guard_applied", False)),
                    "is_minority_position": bool(diag.get("is_minority_position", False)),
                    "alignment_category": diag.get("alignment_category"),
                    "source_evidence_ids_json": json.dumps(c.source_evidence_ids),
                    "canonical_alternative_crosswalk_json": (
                        json.dumps(_normalize_enum_dict(asdict(c.canonical_alternative_crosswalk)), sort_keys=True)
                        if c.canonical_alternative_crosswalk is not None
                        else None
                    ),
                    "preference_uncertainty_set_json": (
                        json.dumps(_normalize_enum_dict(asdict(c.preference_uncertainty_set)), sort_keys=True)
                        if c.preference_uncertainty_set is not None
                        else None
                    ),
                    "provenance_json": json.dumps(_normalize_enum_dict(asdict(c.provenance)), sort_keys=True),
                }
            )
        df = pd.DataFrame(rows)
        df.to_parquet(parquet_path, index=False)

        payload = {
            "schema_version": SCHEMA_VERSION,
            "run_id": self.run_id,
            "matrix_id": matrix.matrix_id,
            "adr_reference": "ADR-0008",
            "primary_question_ids": list(PRIMARY_QUESTION_IDS),
            "contextual_question_ids": list(CONTEXTUAL_QUESTION_IDS),
            "participant_ids": matrix.participant_ids,
            "question_ids": matrix.question_ids,
            "subtopic_ids": matrix.subtopic_ids,
            "subtopic_to_question": matrix.subtopic_to_question,
            "summary": {
                "total_cells": len(matrix.cells),
                "primary_cells": sum(1 for c in matrix.cells if c.question_id in PRIMARY_QUESTION_IDS),
                "contextual_cells": sum(1 for c in matrix.cells if c.question_id in CONTEXTUAL_QUESTION_IDS),
                "observed_usable_cell_count": matrix.observed_usable_cell_count,
                "unobserved_missing_cell_count": matrix.unobserved_missing_cell_count,
                "infeasible_choice_cell_count": matrix.infeasible_choice_cell_count,
                "ambiguous_cell_count": matrix.ambiguous_cell_count,
                "uncertainty_class_counts": matrix.uncertainty_class_counts,
                "overall_coder_agreement_mean": matrix.overall_coder_agreement_mean,
                "overall_coder_confidence_mean": matrix.overall_coder_confidence_mean,
                "validation_passed": matrix.validation_passed,
            },
            "question_coverage_rates": matrix.question_coverage_rates,
            "participant_response_rates": matrix.participant_response_rates,
            "flagged_low_agreement_cell_ids": matrix.flagged_low_agreement_cell_ids,
            "provenance": _normalize_enum_dict(asdict(matrix.provenance)),
            "cells": [_normalize_enum_dict(asdict(c)) for c in matrix.cells],
            "cell_diagnostics": cell_diagnostics,
        }
        json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return {"parquet": parquet_path, "json": json_path}


def load_preference_matrix(parquet_path: Path | str) -> PreferenceMatrix:
    """Reconstruct and validate PreferenceMatrix directly from canonical preference_matrix.parquet."""
    df = pd.read_parquet(parquet_path)
    if df.empty:
        raise ValueError(f"Empty PreferenceMatrix parquet at {parquet_path}")

    cells: list[PreferenceCell] = []
    subtopic_to_question: dict[str, str] = {}
    uc_counts: Counter[str] = Counter()
    flagged: list[str] = []

    q_usable: Counter[str] = Counter()
    q_total: Counter[str] = Counter()
    p_usable: Counter[str] = Counter()
    p_total: Counter[str] = Counter()

    usable_agreements: list[float] = []
    usable_confidences: list[float] = []
    observed_usable_count = 0
    unobserved_missing_count = 0
    infeasible_choice_count = 0
    ambiguous_count = 0

    for _, row in df.iterrows():
        cw_raw = json.loads(row["canonical_alternative_crosswalk_json"]) if pd.notna(row["canonical_alternative_crosswalk_json"]) else None
        pus_raw = json.loads(row["preference_uncertainty_set_json"]) if pd.notna(row["preference_uncertainty_set_json"]) else None
        prov_raw = json.loads(row["provenance_json"])
        cw = _deserialize_crosswalk(cw_raw)
        pus = _deserialize_uncertainty_set(pus_raw)
        prov = ProvenanceMeta(**prov_raw)

        miss = MissingnessState(str(row["missingness_state"]))
        u_cls = UncertaintyClass(str(row["uncertainty_class"])) if pd.notna(row["uncertainty_class"]) else None
        if u_cls:
            uc_counts[u_cls.value] += 1

        alt_probs = json.loads(row["alternative_probabilities_json"]) if pd.notna(row["alternative_probabilities_json"]) else {}
        res_pt = json.loads(row["resolved_point_distribution_json"]) if pd.notna(row["resolved_point_distribution_json"]) else None
        dist_a = json.loads(row["coder_a_distribution_json"]) if pd.notna(row["coder_a_distribution_json"]) else None
        dist_b = json.loads(row["coder_b_distribution_json"]) if pd.notna(row["coder_b_distribution_json"]) else None
        ev_ids = json.loads(row["source_evidence_ids_json"]) if pd.notna(row["source_evidence_ids_json"]) else []

        qid = str(row["question_id"])
        pid = str(row["participant_id"])
        sid = str(row["canonical_subtopic_id"])
        subtopic_to_question[sid] = qid

        c_agree = float(row["coder_agreement"]) if pd.notna(row["coder_agreement"]) else None
        c_conf = float(row["coder_confidence"]) if pd.notna(row["coder_confidence"]) else None

        cell = PreferenceCell(
            cell_id=str(row["cell_id"]),
            participant_id=pid,
            question_id=qid,
            subtopic_id=sid,
            missingness_state=miss,
            alternative_probabilities={str(k): float(v) for k, v in alt_probs.items()},
            semantic_importance=float(row["semantic_importance"]) if pd.notna(row["semantic_importance"]) else None,
            coder_confidence=c_conf,
            coder_agreement=c_agree,
            source_coding_id=str(row["cell_id"]),
            evidence_span_ids=[str(e) for e in ev_ids],
            provenance=prov,
            probability_lower_bounds=dict(pus.lower_bounds) if pus and pus.lower_bounds else None,
            probability_upper_bounds=dict(pus.upper_bounds) if pus and pus.upper_bounds else None,
            probability_interpretation=(
                str(row["probability_interpretation"]) if pd.notna(row["probability_interpretation"]) else None
            ),  # type: ignore[arg-type]
            coder_a_distribution=dist_a,
            coder_b_distribution=dist_b,
            canonical_alternative_crosswalk=cw,
            coder_a_probability_interpretation=(
                str(row["coder_a_probability_interpretation"]) if pd.notna(row["coder_a_probability_interpretation"]) else None
            ),  # type: ignore[arg-type]
            coder_b_probability_interpretation=(
                str(row["coder_b_probability_interpretation"]) if pd.notna(row["coder_b_probability_interpretation"]) else None
            ),  # type: ignore[arg-type]
            semantic_importance_a=float(row["semantic_importance_a"]) if pd.notna(row["semantic_importance_a"]) else None,
            semantic_importance_b=float(row["semantic_importance_b"]) if pd.notna(row["semantic_importance_b"]) else None,
            coder_confidence_a=float(row["coder_confidence_a"]) if pd.notna(row["coder_confidence_a"]) else None,
            coder_confidence_b=float(row["coder_confidence_b"]) if pd.notna(row["coder_confidence_b"]) else None,
            agreement_status=AgreementStatus(str(row["agreement_status"])) if pd.notna(row["agreement_status"]) else None,
            uncertainty_class=u_cls,
            preference_uncertainty_set=pus,
            reconciliation_status=(
                ReconciliationStatus(str(row["reconciliation_status"])) if pd.notna(row["reconciliation_status"]) else None
            ),
            resolved_point_distribution=res_pt,
        )
        cell.validate_simplex()
        cells.append(cell)

        q_total[qid] += 1
        p_total[pid] += 1
        if miss.is_usable():
            observed_usable_count += 1
            q_usable[qid] += 1
            p_usable[pid] += 1
            if c_agree is not None:
                usable_agreements.append(c_agree)
                if c_agree < 0.7:
                    flagged.append(cell.cell_id)
            if c_conf is not None:
                usable_confidences.append(c_conf)
        else:
            canon_m = miss.to_canonical_cell_state()
            if canon_m == MissingnessState.INFEASIBLE_CHOICE.value:
                infeasible_choice_count += 1
            elif canon_m == MissingnessState.AMBIGUOUS.value:
                ambiguous_count += 1
            else:
                unobserved_missing_count += 1

    participants = sorted(df["participant_id"].astype(str).unique().tolist())
    questions = sorted(df["question_id"].astype(str).unique().tolist())
    subtopics = sorted(subtopic_to_question.keys())
    matrix_id = str(df["matrix_id"].iloc[0])
    first_prov = cells[0].provenance
    assert first_prov is not None

    return PreferenceMatrix(
        matrix_id=matrix_id,
        participant_ids=participants,
        question_ids=questions,
        subtopic_ids=subtopics,
        subtopic_to_question=subtopic_to_question,
        cells=cells,
        observed_usable_cell_count=observed_usable_count,
        unobserved_missing_cell_count=unobserved_missing_count,
        infeasible_choice_cell_count=infeasible_choice_count,
        ambiguous_cell_count=ambiguous_count,
        overall_coder_agreement_mean=round(sum(usable_agreements) / len(usable_agreements), 6) if usable_agreements else 0.0,
        overall_coder_confidence_mean=round(sum(usable_confidences) / len(usable_confidences), 6) if usable_confidences else 0.0,
        validation_passed=True,
        provenance=first_prov,
        question_coverage_rates={q: q_usable[q] / q_total[q] for q in questions},
        participant_response_rates={p: p_usable[p] / p_total[p] for p in participants},
        flagged_low_agreement_cell_ids=sorted(set(flagged)),
        uncertainty_class_counts=dict(sorted(uc_counts.items())),
    )
