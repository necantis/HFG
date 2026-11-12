"""Tests for Agent 01 — Data & Question Registry.

Verifies:
1. Raw survey cryptographic immutability and SHA-256 fingerprint.
2. RFC-compliant multiline CSV parsing (11 respondents, 27 columns).
3. Long-format normalized answers schema, dimensions (154 rows), and ID stability.
4. Per-cell language detection across supported languages ('fr', 'de', 'en').
5. Explicit missingness preservation and zero missingness imputation.
6. 13-question registry completeness, analytical frames, and economic good policy gating.
7. Artifact registry provenance and manifest registration.
8. Agent 11 Quality Gate 1 passing verification.
"""

import json
from pathlib import Path
import pandas as pd
import pytest

from src.contracts import AnalyticalFrameType, MissingnessState, QuestionSpec
from src.ingest.ingestion import (
    EXPECTED_COLUMN_COUNT,
    EXPECTED_RAW_SHA256,
    EXPECTED_RESPONDENT_COUNT,
    QUESTION_MAP,
    SurveyIngester,
    classify_missingness,
    compute_sha256,
    detect_language,
    ingest_survey,
)
from src.registry.question_registry import QuestionRegistry, build_question_registry
from src.hardcoding_scanner import HardcodingScanner, verify_gate_1
from src.artifact_registry import ArtifactRegistry, AUTHORITY_CANONICAL_INGESTION


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def test_raw_survey_immutability_and_hash(repo_root):
    """Verify that data/raw/survey_raw.csv exists and matches expected cryptographic hash."""
    raw_path = repo_root / "data" / "raw" / "survey_raw.csv"
    assert raw_path.is_file(), f"Missing raw survey file: {raw_path}"
    sha256 = compute_sha256(raw_path)
    assert sha256 == EXPECTED_RAW_SHA256, f"Hash mismatch: got {sha256}, expected {EXPECTED_RAW_SHA256}"


def test_csv_rfc_parsing(repo_root):
    """Verify RFC-compliant parsing handles multiline quoted fields without respondent inflation."""
    raw_path = repo_root / "data" / "raw" / "survey_raw.csv"
    ingester = SurveyIngester(raw_csv_path=raw_path)
    header, rows = ingester.parse_raw_csv()

    assert len(rows) == EXPECTED_RESPONDENT_COUNT, f"Expected {EXPECTED_RESPONDENT_COUNT} rows, got {len(rows)}"
    assert len(header) == EXPECTED_COLUMN_COUNT, f"Expected {EXPECTED_COLUMN_COUNT} columns, got {len(header)}"
    assert "Obs_No" in header


def test_normalized_answers_schema_and_dimensions(repo_root):
    """Verify long-format answers DataFrame conforms to answers_normalized_v1 contract."""
    parquet_path = repo_root / "data" / "normalized" / "answers_normalized.parquet"
    json_path = repo_root / "data" / "normalized" / "answers_normalized.json"

    assert parquet_path.is_file(), "answers_normalized.parquet must exist"
    assert json_path.is_file(), "answers_normalized.json must exist"

    df = pd.read_parquet(parquet_path)
    expected_rows = EXPECTED_RESPONDENT_COUNT * len(QUESTION_MAP)  # 11 * 14 = 154
    assert len(df) == expected_rows, f"Expected {expected_rows} rows, got {len(df)}"

    required_columns = {
        "response_id",
        "participant_id",
        "question_id",
        "response_type",
        "detected_language",
        "raw_value",
        "normalized_value",
        "missingness_state",
        "is_valid",
        "validation_flags",
        "raw_response_sha256",
        "char_length",
        "run_id",
        "dataset_fingerprint",
        "producer_agent",
        "producer_module",
        "created_at_utc",
    }
    assert required_columns.issubset(set(df.columns)), f"Missing columns: {required_columns - set(df.columns)}"


def test_participant_and_response_id_stability(repo_root):
    """Verify stable anonymized participant IDs and unique response IDs."""
    parquet_path = repo_root / "data" / "normalized" / "answers_normalized.parquet"
    df = pd.read_parquet(parquet_path)

    expected_pids = [f"PARTICIPANT_{i:03d}" for i in range(1, 12)]
    actual_pids = sorted(df["participant_id"].unique().tolist())
    assert actual_pids == expected_pids, f"Participant IDs mismatch: {actual_pids}"

    # Response IDs must be unique
    assert df["response_id"].nunique() == len(df)
    # Check response ID format
    assert df["response_id"].str.match(r"^RESP_\d{3}_Q\d{2}$").all()


def test_language_detection_unit():
    """Verify language detection across 'fr', 'de', and 'en'."""
    assert detect_language("Dans l'ensemble, les quatre pôles proposés paraissent pertinents.", "fr") == "fr"
    assert detect_language("Das ist ein sehr wichtiger Vorschlag für die Koordination.", "de") == "de"
    assert detect_language("We should consider a unified approach for laboratory management.", "en") == "en"
    # Fallback check
    assert detect_language("", fallback_lang="fr") == "fr"
    assert detect_language("", fallback_lang="de") == "de"


def test_explicit_missingness_preservation(repo_root):
    """Verify that missing answers remain explicitly missing with zero synthetic imputation."""
    parquet_path = repo_root / "data" / "normalized" / "answers_normalized.parquet"
    df = pd.read_parquet(parquet_path)

    # 1. Blank cells
    blank_rows = df[df["missingness_state"] == MissingnessState.MISSING_RAW_BLANK.value]
    assert len(blank_rows) > 0, "Expected missing_raw_blank cells"
    assert blank_rows["is_valid"].eq(False).all()
    assert blank_rows["raw_value"].str.strip().eq("").all()

    # 2. Non-substantive refusal cells
    non_sub_rows = df[df["missingness_state"] == MissingnessState.MISSING_NON_SUBSTANTIVE.value]
    assert len(non_sub_rows) > 0, "Expected missing_non_substantive cells"
    assert non_sub_rows["is_valid"].eq(False).all()

    # Verify specific known refusal texts are caught
    known_refusals = ["RAS", "Je n'ai aucun avis là-dessus", "Pas d'expérience, pas d'avis."]
    for refusal in known_refusals:
        matches = df[df["raw_value"].str.contains(refusal, regex=False, na=False)]
        assert (matches["missingness_state"] == MissingnessState.MISSING_NON_SUBSTANTIVE.value).all(), (
            f"Expected '{refusal}' to be classified as missing_non_substantive"
        )
    # Standalone '?' cells
    q_mark_rows = df[df["raw_value"].str.strip() == "?"]
    assert len(q_mark_rows) > 0
    assert (q_mark_rows["missingness_state"] == MissingnessState.MISSING_NON_SUBSTANTIVE.value).all()

    # 3. Usable cells
    usable_rows = df[df["missingness_state"] == MissingnessState.OBSERVED_USABLE.value]
    assert len(usable_rows) > 0
    assert usable_rows["is_valid"].eq(True).all()
    assert usable_rows["raw_value"].str.strip().ne("").all()

    # 4. Total partition
    assert len(blank_rows) + len(non_sub_rows) + len(usable_rows) == len(df)


def test_13_question_registry_and_contracts(repo_root):
    """Verify question registry covers Q01-Q13 and enforces analytical frames and policies."""
    registry_path = repo_root / "data" / "normalized" / "question_registry.json"
    assert registry_path.is_file(), "question_registry.json must exist"

    with open(registry_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    questions = data["questions"]
    assert len(questions) == 14
    assert data["substantive_question_count"] == 13

    # Verify all substantive questions Q01-Q13 are present
    for i in range(1, 14):
        qid = f"Q{i:02d}"
        assert qid in questions, f"Substantive question {qid} missing from registry"
        q_meta = questions[qid]
        assert q_meta["question_index"] == i
        assert q_meta["observed_response_count"] + q_meta["missing_response_count"] == EXPECTED_RESPONDENT_COUNT
        assert len(q_meta["missing_participant_ids"]) == q_meta["missing_response_count"]

    # Verify economic good policy: perception questions must have policy == 'DISABLED'
    perception_qids = ["Q01", "Q02", "Q03", "Q06", "Q14"]
    for qid in perception_qids:
        assert questions[qid]["economic_good_classification_policy"] == "DISABLED", (
            f"Question {qid} must have economic_good_classification_policy == 'DISABLED'"
        )

    # Allocation questions must have policy == 'ENABLED'
    allocation_qids = ["Q07", "Q08", "Q09", "Q10", "Q11", "Q12"]
    for qid in allocation_qids:
        assert questions[qid]["economic_good_classification_policy"] == "ENABLED", (
            f"Question {qid} must have economic_good_classification_policy == 'ENABLED'"
        )


def test_artifact_registration(repo_root):
    """Verify that norm_answers_v1 and question_registry_v1 are registered in manifest."""
    manifest_path = repo_root / "runs" / "run_20261111_002" / "manifest.json"
    assert manifest_path.is_file(), "manifest.json must exist"

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    artifacts = manifest["artifacts"]
    assert "raw_survey_v1" in artifacts
    assert "norm_answers_v1" in artifacts
    assert "question_registry_v1" in artifacts

    norm_art = artifacts["norm_answers_v1"]
    assert norm_art["authority_level"] == AUTHORITY_CANONICAL_INGESTION
    assert norm_art["validation_status"] == "valid"
    assert norm_art["stale_state"] == "fresh"
    assert "raw_survey_v1" in norm_art["upstream_artifacts"]


def test_gate_1_quality_gate(repo_root):
    """Verify Agent 11 Gate 1 check passes with 0 violations."""
    gate_result = verify_gate_1(base_dir=repo_root)
    assert gate_result["status"] == "PASS", f"Gate 1 failed: {json.dumps(gate_result, indent=2)}"
    assert gate_result["checks"]["hardcoding_scan"]["status"] == "PASS"
    assert gate_result["checks"]["raw_source_integrity"]["status"] == "PASS"
    assert gate_result["checks"]["question_registry"]["status"] == "PASS"
    assert gate_result["checks"]["missingness_preservation"]["status"] == "PASS"
