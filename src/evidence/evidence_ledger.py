"""Agent 03 Evidence Ledger & Provenance Lock for Multilingual Qualitative Reconciliation.

Owned by: Agent 03 — Evidence & Reconciliation
Architecture Version: v1.1.0
Schema Version: 1.0.0 / v1.1.0

Responsibilities:
1. Verify release prerequisites and cryptographic provenance lock before any reconciliation:
   - Reject smoke_tiny, pilot_subset, synthetic, mock, or CPU-fallback outputs.
   - Compute and record Git SHA, raw CSV SHA-256, normalized input SHA-256, Coder A/B SHA-256,
     source_evidence_hash, model repos/revisions, prompt hashes, response counts, and non-preference preservation.
2. Treat Coder A and Coder B outputs as strictly immutable inputs.
3. Validate every EvidenceSpan against answers_normalized.parquet / source_text:
   - Verify participant_id, question_id, response_id, raw_response_sha256.
   - Verify exact character offsets (0 <= char_start < char_end <= len(source_text)) and verbatim equality.
   - Reject orphan span IDs across discovered_subtopics, coding_results, and value_assignments.
4. Preserve missingness and non-preference cells without generating synthetic preferences:
   - Verify empty alternative_probabilities, null semantic_importance, null derived_scalar_score
     for raw_blank, explicit_no_opinion, explicit_insufficient_experience,
     explicit_insufficient_information, punctuation_uninterpretable, no_additional_remarks, and ambiguous.
   - Expose character-index sets per span / subtopic for evidence-grounded alignment.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Set, Tuple

import pandas as pd
from pydantic import BaseModel, Field

from src.contracts import (
    AnalyticalFrameType,
    MissingnessState,
    ResponseEpistemicStatus,
    SCHEMA_VERSION,
)
from src.ingest.ingestion import ACTIVE_RUN_ID, EXPECTED_RAW_SHA256, compute_sha256
from src.nlp.prompts import compute_source_evidence_hash
from src.nlp.schemas import NormalizedResponseInput, QuestionCorpusInput
from src.runtime.model_runtime import (
    CoderModelSpec,
    ExecutionMode,
    ExecutionProfile,
    validate_model_family_diversity,
)


NON_PREFERENCE_MISSINGNESS_STATES = {
    MissingnessState.MISSING_RAW_BLANK.value,
    MissingnessState.MISSING_NON_SUBSTANTIVE.value,
    MissingnessState.AMBIGUOUS.value,
    MissingnessState.UNOBSERVED_MISSING.value,
}

NON_PREFERENCE_EPISTEMIC_STATUSES = {
    ResponseEpistemicStatus.RAW_BLANK.value,
    ResponseEpistemicStatus.EXPLICIT_NO_OPINION.value,
    ResponseEpistemicStatus.EXPLICIT_INSUFFICIENT_EXPERIENCE.value,
    ResponseEpistemicStatus.EXPLICIT_INSUFFICIENT_INFORMATION.value,
    ResponseEpistemicStatus.PUNCTUATION_UNINTERPRETABLE.value,
    ResponseEpistemicStatus.NO_ADDITIONAL_REMARKS.value,
}


class ProvenanceVerificationError(ValueError):
    """Raised when production provenance, model independence, or input eligibility fails."""


class EvidenceIntegrityError(ValueError):
    """Raised when an EvidenceSpan fails offset/SHA/orphan resolution or missingness invariants."""


class CoderInputProvenance(BaseModel):
    """Locked cryptographic and execution provenance for one independent LLM coder."""

    coder_id: Literal["coder_a", "coder_b"]
    artifact_path: str
    artifact_sha256: str
    execution_profile: str
    production_eligible: bool
    synthetic_or_test_execution: bool
    execution_mode: str
    model_family: str
    base_model: str = ""
    model_repo: str
    model_revision: str
    quantization: str = ""
    prompt_hash: str
    source_evidence_hash: str
    model_load_succeeded: bool
    gpu_resident: bool
    inference_occurred: bool
    responses_attempted: int
    responses_completed: int
    responses_failed: int
    non_preference_cells_preserved: int
    reconciled_by_agent_03: bool
    discovered_subtopics_count: int
    evidence_spans_count: int
    coding_results_count: int
    value_assignments_count: int


class ProvenanceLock(BaseModel):
    """Immutable provenance lock captured prior to any Agent 03 reconciliation."""

    lock_id: str
    run_id: str
    locked_at_utc: str
    git_commit_sha: str
    git_branch: str
    raw_survey_path: str
    raw_survey_sha256: str
    raw_survey_matches_baseline: bool
    answers_normalized_parquet_path: str
    answers_normalized_parquet_sha256: str
    answers_normalized_json_path: Optional[str] = None
    answers_normalized_json_sha256: Optional[str] = None
    question_registry_path: str
    question_registry_sha256: str
    recomputed_source_evidence_hash: str
    common_source_evidence_hash: str
    production_release_manifest_path: Optional[str] = None
    production_release_manifest_sha256: Optional[str] = None
    production_release_git_sha: Optional[str] = None
    gpu_benchmark_path: Optional[str] = None
    gpu_benchmark_sha256: Optional[str] = None
    participant_count: int
    question_count: int
    primary_question_count: int
    total_response_cells: int
    observed_usable_response_cells: int
    non_preference_response_cells: int
    coder_a: CoderInputProvenance
    coder_b: CoderInputProvenance
    validation_status: Literal["LOCKED_VERIFIED", "FAILED"]
    verification_checks: Dict[str, bool] = Field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION


class VerifiedSpanRecord(BaseModel):
    """Validated evidence span reference (free of verbatim quote storage when sanitized)."""

    span_id: str
    coder_id: Literal["coder_a", "coder_b"]
    participant_id: str
    question_id: str
    response_id: str
    detected_language: str
    raw_response_sha256: str
    char_start: int
    char_end: int
    missingness_state: str
    span_role: str
    offset_reference_text: str = "source_text"
    offset_verified: bool = True
    hash_verified: bool = True


class MissingnessLedgerEntry(BaseModel):
    """Explicit non-preference / missingness preservation audit record per cell."""

    participant_id: str
    question_id: str
    response_id: str
    text_supplied: bool
    normalized_missingness_state: str
    epistemic_status: str
    non_preference_category: Literal[
        "absence_of_input_raw_blank",
        "evidence_of_absence_explicit_no_opinion",
        "evidence_of_absence_insufficient_experience_or_info",
        "uninterpretable_punctuation",
        "ambiguous_unresolved",
        "no_additional_remarks",
    ]
    coder_a_missingness_state: Optional[str] = None
    coder_b_missingness_state: Optional[str] = None
    coder_a_span_ids: List[str] = Field(default_factory=list)
    coder_b_span_ids: List[str] = Field(default_factory=list)
    coder_a_probabilities_empty: bool = True
    coder_b_probabilities_empty: bool = True
    synthetic_preference_detected: bool = False


class SpanValidationReport(BaseModel):
    """Aggregate report covering span verification, orphan checks, and missingness integrity."""

    coder_a_spans_total: int
    coder_b_spans_total: int
    coder_a_spans_verified: int
    coder_b_spans_verified: int
    orphan_span_references: List[str] = Field(default_factory=list)
    offset_mismatches: List[str] = Field(default_factory=list)
    response_sha_mismatches: List[str] = Field(default_factory=list)
    missing_coordinate_errors: List[str] = Field(default_factory=list)
    non_preference_cells_total: int
    non_preference_cells_preserved: int
    non_preference_violations: List[str] = Field(default_factory=list)
    all_checks_passed: bool


def _git_output(base_dir: Path, args: List[str]) -> str:
    try:
        res = subprocess.run(
            ["git", *args],
            cwd=str(base_dir),
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip()
    except Exception:
        return "unavailable"


def _classify_non_preference_category(
    epistemic_status: str,
) -> Literal[
    "absence_of_input_raw_blank",
    "evidence_of_absence_explicit_no_opinion",
    "evidence_of_absence_insufficient_experience_or_info",
    "uninterpretable_punctuation",
    "ambiguous_unresolved",
    "no_additional_remarks",
]:
    if epistemic_status == ResponseEpistemicStatus.RAW_BLANK.value:
        return "absence_of_input_raw_blank"
    if epistemic_status == ResponseEpistemicStatus.EXPLICIT_NO_OPINION.value:
        return "evidence_of_absence_explicit_no_opinion"
    if epistemic_status in {
        ResponseEpistemicStatus.EXPLICIT_INSUFFICIENT_EXPERIENCE.value,
        ResponseEpistemicStatus.EXPLICIT_INSUFFICIENT_INFORMATION.value,
    }:
        return "evidence_of_absence_insufficient_experience_or_info"
    if epistemic_status == ResponseEpistemicStatus.PUNCTUATION_UNINTERPRETABLE.value:
        return "uninterpretable_punctuation"
    if epistemic_status == ResponseEpistemicStatus.NO_ADDITIONAL_REMARKS.value:
        return "no_additional_remarks"
    return "ambiguous_unresolved"


class EvidenceLedger:
    """Loads, locks, and verifies immutable production inputs for Agent 03 reconciliation."""

    def __init__(
        self,
        base_dir: Optional[Path | str] = None,
        run_id: str = ACTIVE_RUN_ID,
        coder_a_path: Optional[Path | str] = None,
        coder_b_path: Optional[Path | str] = None,
        answers_parquet_path: Optional[Path | str] = None,
        answers_json_path: Optional[Path | str] = None,
        question_registry_path: Optional[Path | str] = None,
        require_baseline_raw_sha: bool = True,
    ):
        self.base_dir = (Path(base_dir) if base_dir else Path.cwd()).resolve()
        self.run_id = run_id
        self.require_baseline_raw_sha = require_baseline_raw_sha

        self.raw_survey_path = self.base_dir / "data" / "raw" / "survey_raw.csv"
        self.coder_a_path = (
            Path(coder_a_path)
            if coder_a_path
            else self.base_dir / "data" / "processed" / "coder_a_outputs.json"
        )
        self.coder_b_path = (
            Path(coder_b_path)
            if coder_b_path
            else self.base_dir / "data" / "processed" / "coder_b_outputs.json"
        )
        self.answers_parquet_path = (
            Path(answers_parquet_path)
            if answers_parquet_path
            else self.base_dir / "data" / "normalized" / "answers_normalized.parquet"
        )
        self.answers_json_path = (
            Path(answers_json_path)
            if answers_json_path
            else self.base_dir / "data" / "normalized" / "answers_normalized.json"
        )
        self.question_registry_path = (
            Path(question_registry_path)
            if question_registry_path
            else self.base_dir / "data" / "normalized" / "question_registry.json"
        )

        self.norm_df: pd.DataFrame = pd.DataFrame()
        self.question_registry: Dict[str, Any] = {}
        self.coder_a_payload: Dict[str, Any] = {}
        self.coder_b_payload: Dict[str, Any] = {}

        self.rows_by_pair: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self.rows_by_response_id: Dict[str, Dict[str, Any]] = {}

        self.spans_by_coder_and_id: Dict[str, Dict[str, Dict[str, Any]]] = {
            "coder_a": {},
            "coder_b": {},
        }
        self.verified_spans: Dict[str, Dict[str, VerifiedSpanRecord]] = {
            "coder_a": {},
            "coder_b": {},
        }
        self.provenance_lock: Optional[ProvenanceLock] = None
        self.span_report: Optional[SpanValidationReport] = None
        self.missingness_ledger: List[MissingnessLedgerEntry] = []

    def _compute_recomputed_source_evidence_hash(self) -> str:
        """Deterministically recompute global source_evidence_hash across all questions."""
        if self.norm_df.empty:
            return ""
        questions = self.question_registry.get("questions", {})
        if not questions:
            return ""
        per_q_hashes: List[str] = []
        for qid in sorted(questions):
            qmeta = questions[qid]
            rows = self.norm_df[self.norm_df["question_id"] == qid].sort_values("participant_id")
            resps = [
                NormalizedResponseInput.from_normalized_row(row.to_dict())
                for _, row in rows.iterrows()
            ]
            corpus = QuestionCorpusInput(
                question_id=qid,
                question_index=int(qmeta.get("question_index", 0)),
                canonical_prompt_en=str(qmeta.get("canonical_prompt_en", "")),
                exact_question_wording=dict(qmeta.get("column_headers_by_lang") or {}),
                analytical_frame=AnalyticalFrameType(qmeta["analytical_frame"]),
                economic_good_classification_policy=qmeta["economic_good_classification_policy"],
                responses=resps,
            )
            per_q_hashes.append(compute_source_evidence_hash(corpus))
        return hashlib.sha256("|".join(per_q_hashes).encode("utf-8")).hexdigest()

    def _extract_coder_provenance(
        self,
        coder_id: Literal["coder_a", "coder_b"],
        path: Path,
        payload: Dict[str, Any],
    ) -> CoderInputProvenance:
        if not path.is_file():
            raise ProvenanceVerificationError(f"Missing required {coder_id} output file: {path}")

        meta = payload.get("execution_metadata") or {}
        top_profile = payload.get("execution_profile")
        meta_profile = meta.get("execution_profile")
        if top_profile is not None and meta_profile is not None and top_profile != meta_profile:
            raise ProvenanceVerificationError(
                f"{coder_id}: conflicting execution_profile top={top_profile!r} vs meta={meta_profile!r}"
            )
        execution_profile = str(meta_profile if meta_profile is not None else (top_profile or ""))
        if execution_profile != ExecutionProfile.PRODUCTION.value:
            raise ProvenanceVerificationError(
                f"{coder_id}: rejected non-production execution_profile={execution_profile!r}; "
                "only 'production' coder outputs may be reconciled."
            )

        top_elig = payload.get("production_eligible") if "production_eligible" in payload else None
        meta_elig = meta.get("production_eligible") if "production_eligible" in meta else None
        if top_elig is not None and meta_elig is not None and bool(top_elig) != bool(meta_elig):
            raise ProvenanceVerificationError(f"{coder_id}: inconsistent production_eligible flags.")
        prod_elig = bool(meta_elig if meta_elig is not None else (top_elig is True))
        if not prod_elig:
            raise ProvenanceVerificationError(f"{coder_id}: production_eligible must be True.")

        top_synth = payload.get("synthetic_or_test_execution") if "synthetic_or_test_execution" in payload else None
        meta_synth = meta.get("synthetic_or_test_execution") if "synthetic_or_test_execution" in meta else None
        if top_synth is not None and meta_synth is not None and bool(top_synth) != bool(meta_synth):
            raise ProvenanceVerificationError(f"{coder_id}: inconsistent synthetic_or_test_execution flags.")
        synth_flag = True if (meta_synth is None and top_synth is None) else bool(
            meta_synth if meta_synth is not None else top_synth
        )
        if synth_flag:
            raise ProvenanceVerificationError(
                f"{coder_id}: rejected synthetic/mock/test execution output (synthetic_or_test_execution=True)."
            )

        if payload.get("run_id") != self.run_id:
            raise ProvenanceVerificationError(
                f"{coder_id}: run_id mismatch: expected {self.run_id!r}, got {payload.get('run_id')!r}."
            )
        if payload.get("coder_id") != coder_id:
            raise ProvenanceVerificationError(
                f"{coder_id}: coder_id mismatch: expected {coder_id!r}, got {payload.get('coder_id')!r}."
            )

        exec_mode = str(meta.get("execution_mode", ""))
        if exec_mode == ExecutionMode.CPU_FALLBACK.value:
            raise ProvenanceVerificationError(f"{coder_id}: CPU_FALLBACK outputs cannot be reconciled.")

        if not (
            bool(meta.get("model_load_succeeded"))
            and bool(meta.get("gpu_resident"))
            and bool(meta.get("inference_occurred"))
        ):
            raise ProvenanceVerificationError(
                f"{coder_id}: execution_metadata must prove model_load_succeeded, gpu_resident, and inference_occurred."
            )

        model_repo = str(meta.get("model_repo", "")).strip()
        model_rev = str(meta.get("model_revision", "")).strip()
        prompt_hash = str(meta.get("prompt_hash", "")).strip()
        source_ev_hash = str(meta.get("source_evidence_hash", "")).strip()
        if not model_repo or not model_rev or not prompt_hash or not source_ev_hash:
            raise ProvenanceVerificationError(
                f"{coder_id}: missing immutable provenance fields (model_repo/model_revision/prompt_hash/source_evidence_hash)."
            )

        attempted = int(meta.get("responses_attempted", 0))
        completed = int(meta.get("responses_completed", 0))
        failed = int(meta.get("responses_failed", -1))
        if failed != 0 or completed <= 0 or completed != attempted:
            raise ProvenanceVerificationError(
                f"{coder_id}: incomplete response execution: attempted={attempted}, completed={completed}, failed={failed}."
            )

        coding_results = payload.get("coding_results") or []
        non_pref_preserved = int(
            meta.get(
                "non_preference_cells_preserved",
                sum(1 for c in coding_results if c.get("missingness_state") != MissingnessState.OBSERVED_USABLE.value),
            )
        )

        try:
            rel_path = str(path.resolve().relative_to(self.base_dir))
        except ValueError:
            rel_path = str(path)

        return CoderInputProvenance(
            coder_id=coder_id,
            artifact_path=rel_path,
            artifact_sha256=compute_sha256(path),
            execution_profile=execution_profile,
            production_eligible=prod_elig,
            synthetic_or_test_execution=synth_flag,
            execution_mode=exec_mode,
            model_family=str(meta.get("model_family", "")),
            base_model=str(meta.get("base_model", "")),
            model_repo=model_repo,
            model_revision=model_rev,
            quantization=str(meta.get("quantization", "")),
            prompt_hash=prompt_hash,
            source_evidence_hash=source_ev_hash,
            model_load_succeeded=bool(meta.get("model_load_succeeded")),
            gpu_resident=bool(meta.get("gpu_resident")),
            inference_occurred=bool(meta.get("inference_occurred")),
            responses_attempted=attempted,
            responses_completed=completed,
            responses_failed=failed,
            non_preference_cells_preserved=non_pref_preserved,
            reconciled_by_agent_03=bool(meta.get("reconciled_by_agent_03", False)),
            discovered_subtopics_count=len(payload.get("discovered_subtopics") or []),
            evidence_spans_count=len(payload.get("evidence_spans") or []),
            coding_results_count=len(coding_results),
            value_assignments_count=len(payload.get("value_assignments") or []),
        )

    def load_and_lock_provenance(self) -> ProvenanceLock:
        """Load all immutable inputs, verify hashes and independence, and lock provenance."""
        if not self.answers_parquet_path.is_file():
            raise ProvenanceVerificationError(f"Missing answers_normalized.parquet: {self.answers_parquet_path}")
        if not self.question_registry_path.is_file():
            raise ProvenanceVerificationError(f"Missing question_registry.json: {self.question_registry_path}")

        self.norm_df = pd.read_parquet(self.answers_parquet_path)
        self.question_registry = json.loads(self.question_registry_path.read_text(encoding="utf-8"))
        self.coder_a_payload = json.loads(self.coder_a_path.read_text(encoding="utf-8"))
        self.coder_b_payload = json.loads(self.coder_b_path.read_text(encoding="utf-8"))

        for _, row in self.norm_df.iterrows():
            rdict = row.to_dict()
            pair = (str(rdict["participant_id"]), str(rdict["question_id"]))
            self.rows_by_pair[pair] = rdict
            self.rows_by_response_id[str(rdict["response_id"])] = rdict

        raw_sha = compute_sha256(self.raw_survey_path) if self.raw_survey_path.is_file() else "missing"
        raw_matches = raw_sha == EXPECTED_RAW_SHA256
        if self.require_baseline_raw_sha and not raw_matches:
            raise ProvenanceVerificationError(
                f"Raw survey SHA-256 mismatch: expected {EXPECTED_RAW_SHA256}, got {raw_sha}"
            )

        prov_a = self._extract_coder_provenance("coder_a", self.coder_a_path, self.coder_a_payload)
        prov_b = self._extract_coder_provenance("coder_b", self.coder_b_path, self.coder_b_payload)

        if prov_a.source_evidence_hash != prov_b.source_evidence_hash:
            raise ProvenanceVerificationError(
                f"Common source_evidence_hash mismatch: Coder A={prov_a.source_evidence_hash} != Coder B={prov_b.source_evidence_hash}"
            )
        if prov_a.prompt_hash == prov_b.prompt_hash:
            raise ProvenanceVerificationError(
                "Coder A and Coder B prompt_hash values must be independent."
            )

        # Verify model family diversity (rejects same family or Qwen substitution)
        spec_a = CoderModelSpec(
            coder_id="coder_a",
            model_family=prov_a.model_family,
            model_repo=prov_a.model_repo,
            model_revision=prov_a.model_revision,
            quantization=prov_a.quantization or "AWQ-INT4",
            port=8001,
        )
        spec_b = CoderModelSpec(
            coder_id="coder_b",
            model_family=prov_b.model_family,
            model_repo=prov_b.model_repo,
            model_revision=prov_b.model_revision,
            quantization=prov_b.quantization or "W4A16-INT4",
            port=8002,
        )
        validate_model_family_diversity(spec_a, spec_b, execution_profile=ExecutionProfile.PRODUCTION.value)

        # Verify primary usable count matches completion count
        usable_df = self.norm_df[self.norm_df["missingness_state"] == MissingnessState.OBSERVED_USABLE.value]
        total_usable = len(usable_df)
        if prov_a.responses_completed != total_usable or prov_b.responses_completed != total_usable:
            raise ProvenanceVerificationError(
                f"Coder completion count mismatch against usable normalized answers ({total_usable}): "
                f"A={prov_a.responses_completed}, B={prov_b.responses_completed}"
            )

        non_pref_df = self.norm_df[self.norm_df["missingness_state"] != MissingnessState.OBSERVED_USABLE.value]
        non_pref_total = len(non_pref_df)
        if (
            prov_a.non_preference_cells_preserved != non_pref_total
            or prov_b.non_preference_cells_preserved != non_pref_total
        ):
            raise ProvenanceVerificationError(
                f"Non-preference cells preserved mismatch against normalized data ({non_pref_total}): "
                f"A={prov_a.non_preference_cells_preserved}, B={prov_b.non_preference_cells_preserved}"
            )

        recomputed_source_hash = self._compute_recomputed_source_evidence_hash()
        recomputed_matches = (not recomputed_source_hash) or (recomputed_source_hash == prov_a.source_evidence_hash)
        if self.require_baseline_raw_sha and not recomputed_matches:
            raise ProvenanceVerificationError(
                f"Recomputed source_evidence_hash mismatch: recomputed={recomputed_source_hash} != coder={prov_a.source_evidence_hash}"
            )

        bench_path = self.base_dir / "runs" / self.run_id / "gpu_runtime_benchmark.json"
        rel_bench: Optional[str] = None
        bench_sha: Optional[str] = None
        if bench_path.is_file():
            rel_bench = str(bench_path.relative_to(self.base_dir))
            bench_sha = compute_sha256(bench_path)

        rel_release: Optional[str] = None
        release_sha: Optional[str] = None
        release_git_sha: Optional[str] = None
        release_candidate = self.base_dir / "runs" / self.run_id / "production_release.json"
        if release_candidate.is_file():
            rel_release = str(release_candidate.relative_to(self.base_dir))
            release_sha = compute_sha256(release_candidate)
            release_git_sha = json.loads(release_candidate.read_text(encoding="utf-8")).get("git_sha")

        questions = self.question_registry.get("questions", {})
        primary_q_count = sum(1 for q in questions.values() if q.get("is_primary_question", True))

        checks = {
            "raw_survey_sha256_verified": raw_matches or (not self.require_baseline_raw_sha),
            "coder_a_production_eligible": True,
            "coder_b_production_eligible": True,
            "model_family_diversity_verified": True,
            "independent_prompt_hashes_verified": prov_a.prompt_hash != prov_b.prompt_hash,
            "common_source_evidence_hash_verified": prov_a.source_evidence_hash == prov_b.source_evidence_hash,
            "recomputed_source_evidence_hash_verified": recomputed_matches or (not self.require_baseline_raw_sha),
            "usable_completion_counts_match": True,
            "non_preference_count_matches": True,
        }

        lock_seed = f"{self.run_id}|{prov_a.artifact_sha256}|{prov_b.artifact_sha256}|{prov_a.source_evidence_hash}"
        lock_id = f"LOCK_{hashlib.sha256(lock_seed.encode('utf-8')).hexdigest()[:12]}"

        def _rel(p: Path) -> str:
            try:
                return str(p.resolve().relative_to(self.base_dir))
            except ValueError:
                return str(p)

        self.provenance_lock = ProvenanceLock(
            lock_id=lock_id,
            run_id=self.run_id,
            locked_at_utc=datetime.now(timezone.utc).isoformat(),
            git_commit_sha=_git_output(self.base_dir, ["rev-parse", "HEAD"]),
            git_branch=_git_output(self.base_dir, ["branch", "--show-current"]),
            raw_survey_path=_rel(self.raw_survey_path),
            raw_survey_sha256=raw_sha,
            raw_survey_matches_baseline=raw_matches,
            answers_normalized_parquet_path=_rel(self.answers_parquet_path),
            answers_normalized_parquet_sha256=compute_sha256(self.answers_parquet_path),
            answers_normalized_json_path=_rel(self.answers_json_path) if self.answers_json_path.is_file() else None,
            answers_normalized_json_sha256=(
                compute_sha256(self.answers_json_path) if self.answers_json_path.is_file() else None
            ),
            question_registry_path=_rel(self.question_registry_path),
            question_registry_sha256=compute_sha256(self.question_registry_path),
            recomputed_source_evidence_hash=recomputed_source_hash,
            common_source_evidence_hash=prov_a.source_evidence_hash,
            production_release_manifest_path=rel_release,
            production_release_manifest_sha256=release_sha,
            production_release_git_sha=release_git_sha,
            gpu_benchmark_path=rel_bench,
            gpu_benchmark_sha256=bench_sha,
            participant_count=int(self.norm_df["participant_id"].nunique()),
            question_count=len(questions),
            primary_question_count=primary_q_count,
            total_response_cells=len(self.norm_df),
            observed_usable_response_cells=total_usable,
            non_preference_response_cells=non_pref_total,
            coder_a=prov_a,
            coder_b=prov_b,
            validation_status="LOCKED_VERIFIED" if all(checks.values()) else "FAILED",
            verification_checks=checks,
        )
        return self.provenance_lock

    def verify_spans_and_missingness(self) -> SpanValidationReport:
        """Verify all EvidenceSpan coordinates, exact offsets, zero orphan IDs, and missingness preservation."""
        if self.provenance_lock is None:
            self.load_and_lock_provenance()

        orphan_refs: List[str] = []
        offset_mismatches: List[str] = []
        sha_mismatches: List[str] = []
        missing_coord_errors: List[str] = []
        non_pref_violations: List[str] = []

        for coder_id, payload in [("coder_a", self.coder_a_payload), ("coder_b", self.coder_b_payload)]:
            spans = payload.get("evidence_spans") or []
            span_map: Dict[str, Dict[str, Any]] = {}
            verified_map: Dict[str, VerifiedSpanRecord] = {}

            for sp in spans:
                sp_id = str(sp.get("span_id", ""))
                pid = str(sp.get("participant_id", ""))
                qid = str(sp.get("question_id", ""))
                pair = (pid, qid)
                if not sp_id or sp_id in span_map:
                    missing_coord_errors.append(f"{coder_id}: invalid or duplicate span_id={sp_id!r}")
                    continue
                row = self.rows_by_pair.get(pair)
                if row is None:
                    missing_coord_errors.append(f"{coder_id}: span {sp_id} references unknown coordinate {pair}")
                    continue

                span_map[sp_id] = sp
                src_text = str(row.get("source_text") if row.get("source_text") is not None else row.get("raw_value") or "")
                expected_sha = str(row.get("raw_response_sha256", ""))
                span_sha = str(sp.get("raw_response_sha256", ""))
                hash_ok = bool(expected_sha) and (span_sha == expected_sha)
                if not hash_ok:
                    sha_mismatches.append(f"{coder_id}: span {sp_id} raw_response_sha256 mismatch")

                c_start = int(sp.get("char_start", -1))
                c_end = int(sp.get("char_end", -1))
                quote = str(sp.get("verbatim_quote", ""))
                offset_ok = (
                    0 <= c_start < c_end <= len(src_text)
                    and src_text[c_start:c_end] == quote
                )
                if not offset_ok:
                    offset_mismatches.append(
                        f"{coder_id}: span {sp_id} offset [{c_start}:{c_end}] fails verbatim match on {pair}"
                    )

                verified_map[sp_id] = VerifiedSpanRecord(
                    span_id=sp_id,
                    coder_id=coder_id,  # type: ignore[arg-type]
                    participant_id=pid,
                    question_id=qid,
                    response_id=str(row["response_id"]),
                    detected_language=str(sp.get("detected_language", row.get("detected_language", "fr"))),
                    raw_response_sha256=span_sha,
                    char_start=c_start,
                    char_end=c_end,
                    missingness_state=str(sp.get("missingness_state", row["missingness_state"])),
                    span_role=str(sp.get("span_role", "substantive_evidence")),
                    offset_verified=offset_ok,
                    hash_verified=hash_ok,
                )

            self.spans_by_coder_and_id[coder_id] = span_map
            self.verified_spans[coder_id] = verified_map

            # Verify zero orphan span references across subtopics, coding_results, and value_assignments
            for st in payload.get("discovered_subtopics") or []:
                st_id = str(st.get("subtopic_id", ""))
                for sp_id in st.get("supporting_span_ids") or []:
                    if sp_id not in span_map:
                        orphan_refs.append(f"{coder_id}:subtopic:{st_id}:{sp_id}")
                    elif (
                        span_map[sp_id].get("participant_id") not in set(st.get("supporting_participant_ids") or [])
                    ):
                        # Only sanity-check when supporting_participant_ids is populated
                        pass

            for cr in payload.get("coding_results") or []:
                cid = str(cr.get("coding_id", ""))
                pid = str(cr.get("participant_id", ""))
                qid = str(cr.get("question_id", ""))
                miss = str(cr.get("missingness_state", ""))
                sp_ids = cr.get("evidence_span_ids") or []
                if miss == MissingnessState.OBSERVED_USABLE.value and not sp_ids:
                    orphan_refs.append(f"{coder_id}:coding:{cid}:missing_required_spans")
                for sp_id in sp_ids:
                    sp = span_map.get(sp_id)
                    if sp is None:
                        orphan_refs.append(f"{coder_id}:coding:{cid}:{sp_id}")
                    elif (str(sp.get("participant_id")), str(sp.get("question_id"))) != (pid, qid):
                        missing_coord_errors.append(
                            f"{coder_id}: coding {cid} ({pid},{qid}) links span {sp_id} from ({sp.get('participant_id')},{sp.get('question_id')})"
                        )

            for va in payload.get("value_assignments") or []:
                vid = str(va.get("value_assignment_id", va.get("value_id", "")))
                pid = str(va.get("participant_id", ""))
                qid = str(va.get("question_id", ""))
                sp_ids = va.get("evidence_span_ids") or []
                if not sp_ids:
                    orphan_refs.append(f"{coder_id}:value:{vid}:empty_spans")
                for sp_id in sp_ids:
                    sp = span_map.get(sp_id)
                    if sp is None:
                        orphan_refs.append(f"{coder_id}:value:{vid}:{sp_id}")
                    elif (str(sp.get("participant_id")), str(sp.get("question_id"))) != (pid, qid):
                        missing_coord_errors.append(
                            f"{coder_id}: value {vid} ({pid},{qid}) links span {sp_id} from ({sp.get('participant_id')},{sp.get('question_id')})"
                        )

        # Missingness & non-preference preservation verification
        cr_a_by_pair: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
        cr_b_by_pair: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
        for cr in self.coder_a_payload.get("coding_results") or []:
            cr_a_by_pair[(str(cr["participant_id"]), str(cr["question_id"]))].append(cr)
        for cr in self.coder_b_payload.get("coding_results") or []:
            cr_b_by_pair[(str(cr["participant_id"]), str(cr["question_id"]))].append(cr)

        non_pref_ledger: List[MissingnessLedgerEntry] = []
        for pair, row in sorted(self.rows_by_pair.items()):
            norm_miss = str(row["missingness_state"])
            ep_status = str(row.get("epistemic_status", ""))
            if norm_miss == MissingnessState.OBSERVED_USABLE.value:
                continue

            pid, qid = pair
            ca_recs = cr_a_by_pair.get(pair, [])
            cb_recs = cr_b_by_pair.get(pair, [])
            ca_probs_empty = all(not (r.get("alternative_probabilities") or {}) for r in ca_recs) and len(ca_recs) > 0
            cb_probs_empty = all(not (r.get("alternative_probabilities") or {}) for r in cb_recs) and len(cb_recs) > 0

            synth_violation = False
            if not ca_recs or not cb_recs or not ca_probs_empty or not cb_probs_empty:
                synth_violation = True
                non_pref_violations.append(f"Non-preference cell {pair} altered or synthesized preference.")

            for label, recs in [("coder_a", ca_recs), ("coder_b", cb_recs)]:
                for r in recs:
                    if r.get("missingness_state") == MissingnessState.OBSERVED_USABLE.value:
                        synth_violation = True
                        non_pref_violations.append(f"{label}: {pair} became observed_usable.")
                    if r.get("semantic_importance") is not None or r.get("derived_scalar_score") is not None:
                        synth_violation = True
                        non_pref_violations.append(
                            f"{label}: {pair} imputed semantic_importance or derived_scalar_score."
                        )

            sp_a_ids = sorted(
                sp_id
                for sp_id, sp in self.spans_by_coder_and_id["coder_a"].items()
                if (str(sp["participant_id"]), str(sp["question_id"])) == pair
            )
            sp_b_ids = sorted(
                sp_id
                for sp_id, sp in self.spans_by_coder_and_id["coder_b"].items()
                if (str(sp["participant_id"]), str(sp["question_id"])) == pair
            )

            non_pref_ledger.append(
                MissingnessLedgerEntry(
                    participant_id=pid,
                    question_id=qid,
                    response_id=str(row["response_id"]),
                    text_supplied=bool(row.get("text_supplied", False)),
                    normalized_missingness_state=norm_miss,
                    epistemic_status=ep_status,
                    non_preference_category=_classify_non_preference_category(ep_status),
                    coder_a_missingness_state=ca_recs[0]["missingness_state"] if ca_recs else None,
                    coder_b_missingness_state=cb_recs[0]["missingness_state"] if cb_recs else None,
                    coder_a_span_ids=sp_a_ids,
                    coder_b_span_ids=sp_b_ids,
                    coder_a_probabilities_empty=ca_probs_empty,
                    coder_b_probabilities_empty=cb_probs_empty,
                    synthetic_preference_detected=synth_violation,
                )
            )

        self.missingness_ledger = non_pref_ledger
        preserved_count = sum(1 for e in non_pref_ledger if not e.synthetic_preference_detected)

        all_passed = (
            not orphan_refs
            and not offset_mismatches
            and not sha_mismatches
            and not missing_coord_errors
            and not non_pref_violations
            and len(non_pref_ledger) == preserved_count
        )

        self.span_report = SpanValidationReport(
            coder_a_spans_total=len(self.spans_by_coder_and_id["coder_a"]),
            coder_b_spans_total=len(self.spans_by_coder_and_id["coder_b"]),
            coder_a_spans_verified=sum(
                1 for r in self.verified_spans["coder_a"].values() if r.offset_verified and r.hash_verified
            ),
            coder_b_spans_verified=sum(
                1 for r in self.verified_spans["coder_b"].values() if r.offset_verified and r.hash_verified
            ),
            orphan_span_references=orphan_refs,
            offset_mismatches=offset_mismatches,
            response_sha_mismatches=sha_mismatches,
            missing_coordinate_errors=missing_coord_errors,
            non_preference_cells_total=len(non_pref_ledger),
            non_preference_cells_preserved=preserved_count,
            non_preference_violations=non_pref_violations,
            all_checks_passed=all_passed,
        )

        if not all_passed:
            raise EvidenceIntegrityError(
                f"Evidence span or missingness verification failed: orphans={len(orphan_refs)}, "
                f"offsets={len(offset_mismatches)}, sha={len(sha_mismatches)}, "
                f"coords={len(missing_coord_errors)}, non_pref={len(non_pref_violations)}"
            )
        return self.span_report

    def get_subtopic_char_ranges(
        self,
        coder_id: Literal["coder_a", "coder_b"],
        subtopic: Dict[str, Any],
        coding_results_for_subtopic: List[Dict[str, Any]],
    ) -> Dict[Tuple[str, str], Set[int]]:
        """Collect exact character index sets across verified spans for evidence-overlap alignment."""
        span_ids: Set[str] = set(subtopic.get("supporting_span_ids") or [])
        for cr in coding_results_for_subtopic:
            span_ids.update(cr.get("evidence_span_ids") or [])
        spans = self.spans_by_coder_and_id[coder_id]
        char_map: Dict[Tuple[str, str], Set[int]] = defaultdict(set)
        for sp_id in span_ids:
            sp = spans.get(sp_id)
            if sp is not None:
                c_start = int(sp["char_start"])
                c_end = int(sp["char_end"])
                char_map[(str(sp["participant_id"]), str(sp["question_id"]))].update(range(c_start, c_end))
        return char_map

    def get_span_char_ranges(
        self,
        coder_id: Literal["coder_a", "coder_b"],
        span_ids: List[str],
    ) -> Dict[Tuple[str, str], Set[int]]:
        """Collect exact character index sets for an arbitrary list of verified EvidenceSpan IDs."""
        spans = self.spans_by_coder_and_id[coder_id]
        char_map: Dict[Tuple[str, str], Set[int]] = defaultdict(set)
        for sp_id in span_ids:
            sp = spans.get(sp_id)
            if sp is not None:
                char_map[(str(sp["participant_id"]), str(sp["question_id"]))].update(
                    range(int(sp["char_start"]), int(sp["char_end"]))
                )
        return char_map


def compute_char_overlap_metrics(
    ranges_a: Dict[Tuple[str, str], Set[int]],
    ranges_b: Dict[Tuple[str, str], Set[int]],
) -> Tuple[float, float, float]:
    """Compute (span_char_iou, containment_a_in_b, containment_b_in_a) from exact character offsets."""
    total_a = sum(len(v) for v in ranges_a.values())
    total_b = sum(len(v) for v in ranges_b.values())
    if total_a == 0 or total_b == 0:
        return 0.0, 0.0, 0.0
    inter = 0
    for key in set(ranges_a) & set(ranges_b):
        inter += len(ranges_a[key] & ranges_b[key])
    union = total_a + total_b - inter
    iou = inter / union if union > 0 else 0.0
    cont_a = inter / total_a if total_a > 0 else 0.0
    cont_b = inter / total_b if total_b > 0 else 0.0
    return iou, cont_a, cont_b
