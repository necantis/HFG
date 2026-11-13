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


@pytest.fixture(scope="module", autouse=True)
def ensure_normalized_data() -> None:
    """Ensure gitignored normalized artifacts exist when running on a fresh worktree or CI runner."""
    root = Path(__file__).resolve().parent.parent
    raw_csv = root / "data" / "raw" / "survey_raw.csv"
    norm_parquet = root / "data" / "normalized" / "answers_normalized.parquet"
    norm_json = root / "data" / "normalized" / "answers_normalized.json"
    reg_json = root / "data" / "normalized" / "question_registry.json"
    if not (norm_parquet.is_file() and norm_json.is_file()):
        ingest_survey(
            raw_csv_path=raw_csv,
            output_parquet=norm_parquet,
            output_json=norm_json,
        )
    if not reg_json.is_file():
        build_question_registry(
            answers_df_or_path=norm_parquet,
            raw_csv_path=raw_csv,
            output_json=reg_json,
        )


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
    assert len(blank_rows) == 10, f"Expected exactly 10 missing_raw_blank cells, got {len(blank_rows)}"
    assert blank_rows["is_valid"].eq(False).all()
    assert blank_rows["text_supplied"].eq(False).all()
    assert blank_rows["raw_value"].str.strip().eq("").all()

    # 2. Non-substantive refusal / punctuation cells
    non_sub_rows = df[df["missingness_state"] == MissingnessState.MISSING_NON_SUBSTANTIVE.value]
    assert len(non_sub_rows) == 6, f"Expected 6 missing_non_substantive cells, got {len(non_sub_rows)}"
    assert non_sub_rows["is_valid"].eq(False).all()
    assert non_sub_rows["has_usable_preference"].eq(False).all()

    # Standalone '?' cells
    q_mark_rows = df[df["raw_value"].str.strip() == "?"]
    assert len(q_mark_rows) == 2
    assert (q_mark_rows["missingness_state"] == MissingnessState.MISSING_NON_SUBSTANTIVE.value).all()
    assert (q_mark_rows["epistemic_status"] == "punctuation_uninterpretable").all()

    # 3. Ambiguous cells preserved for downstream coding
    ambiguous_rows = df[df["missingness_state"] == MissingnessState.AMBIGUOUS.value]
    assert len(ambiguous_rows) == 2, f"Expected 2 ambiguous cells, got {len(ambiguous_rows)}"
    assert ambiguous_rows["is_valid"].eq(False).all()
    assert ambiguous_rows["has_usable_preference"].eq(False).all()

    # 4. Usable cells
    usable_rows = df[df["missingness_state"] == MissingnessState.OBSERVED_USABLE.value]
    assert len(usable_rows) == 136, f"Expected 136 observed_usable cells, got {len(usable_rows)}"
    assert usable_rows["is_valid"].eq(True).all()
    assert usable_rows["has_usable_preference"].eq(True).all()
    assert usable_rows["raw_value"].str.strip().ne("").all()

    # 5. Total partition
    assert len(blank_rows) + len(non_sub_rows) + len(ambiguous_rows) + len(usable_rows) == len(df) == 154


def test_epistemic_status_distinction_from_preference_availability(repo_root):
    """Verify response presence, epistemic status, and usable preference are kept orthogonal."""
    parquet_path = repo_root / "data" / "normalized" / "answers_normalized.parquet"
    df = pd.read_parquet(parquet_path)

    # Text supplied must be exactly True when text is non-empty
    assert (df["raw_value"].str.strip() != "").equals(df["text_supplied"])
    assert df["text_supplied"].sum() == 144
    assert (~df["text_supplied"]).sum() == 10

    # Epistemic statuses breakdown
    status_counts = df["epistemic_status"].value_counts().to_dict()
    assert status_counts["substantive"] == 131
    assert status_counts["raw_blank"] == 10
    assert status_counts["mixed_uncertainty_and_preference"] == 5
    assert status_counts["ambiguous"] == 2
    assert status_counts["explicit_no_opinion"] == 2
    assert status_counts["explicit_insufficient_experience"] == 2
    assert status_counts["punctuation_uninterpretable"] == 2

    # Explicit no-opinion and no-experience statements must NOT receive usable preference
    no_pref_mask = df["epistemic_status"].isin([
        "raw_blank",
        "punctuation_uninterpretable",
        "explicit_no_opinion",
        "explicit_insufficient_experience",
        "ambiguous",
    ])
    assert (~df[no_pref_mask]["has_usable_preference"]).all()

    # Usable preference is available for substantive and mixed responses
    pref_mask = df["epistemic_status"].isin(["substantive", "mixed_uncertainty_and_preference"])
    assert df[pref_mask]["has_usable_preference"].all()
    assert df["has_usable_preference"].sum() == 136


def test_meaningful_short_answers_not_overclassified(repo_root):
    """Verify conservative ingestion does not discard concise substantive answers like 'Oui', 'Non', 'Idem'."""
    parquet_path = repo_root / "data" / "normalized" / "answers_normalized.parquet"
    df = pd.read_parquet(parquet_path)

    # Participant 009 Q02: "oui"
    p09_q02 = df[(df["participant_id"] == "PARTICIPANT_009") & (df["question_id"] == "Q02")].iloc[0]
    assert p09_q02["raw_value"].strip().lower() == "oui"
    assert p09_q02["epistemic_status"] == "substantive"
    assert p09_q02["has_usable_preference"] is True or p09_q02["has_usable_preference"] == 1
    assert p09_q02["missingness_state"] == MissingnessState.OBSERVED_USABLE.value

    # Participant 011 Q12: "idem"
    p11_q12 = df[(df["participant_id"] == "PARTICIPANT_011") & (df["question_id"] == "Q12")].iloc[0]
    assert p11_q12["raw_value"].strip().lower() == "idem"
    assert p11_q12["epistemic_status"] == "substantive"
    assert p11_q12["has_usable_preference"] is True or p11_q12["has_usable_preference"] == 1
    assert p11_q12["missingness_state"] == MissingnessState.OBSERVED_USABLE.value

    # Unit classification verification for "Non", "Oui", and "Aucun"
    from src.ingest.ingestion import classify_response_semantics
    for short_ans in ["Oui", "Non", "oui", "non", "Idem", "idem", "Aucun"]:
        sem = classify_response_semantics(short_ans, question_id="Q07")
        assert sem["epistemic_status"] == "substantive"
        assert sem["has_usable_preference"] is True
        assert sem["missingness_state"] == MissingnessState.OBSERVED_USABLE.value


def test_context_sensitive_ras(repo_root):
    """Verify 'RAS' is context-sensitive: no additional remarks in Q14, but ambiguous in Q02."""
    parquet_path = repo_root / "data" / "normalized" / "answers_normalized.parquet"
    df = pd.read_parquet(parquet_path)

    # Participant 005 Q02: "RAS" in diagnostic question Q02 -> ambiguous, preserved for downstream coding
    p05_q02 = df[(df["participant_id"] == "PARTICIPANT_005") & (df["question_id"] == "Q02")].iloc[0]
    assert p05_q02["raw_value"].strip() == "RAS"
    assert p05_q02["epistemic_status"] == "ambiguous"
    assert p05_q02["missingness_state"] == MissingnessState.AMBIGUOUS.value
    assert p05_q02["has_usable_preference"] is False or p05_q02["has_usable_preference"] == 0

    # In Q14 (open remarks), "RAS" is classified as no_additional_remarks / non-substantive
    from src.ingest.ingestion import classify_response_semantics
    sem_q14 = classify_response_semantics("RAS", question_id="Q14")
    assert sem_q14["epistemic_status"] == "no_additional_remarks"
    assert sem_q14["missingness_state"] == MissingnessState.MISSING_NON_SUBSTANTIVE.value


def test_mixed_uncertainty_plus_preference(repo_root):
    """Verify responses combining uncertainty with substantive positions are preserved as usable evidence."""
    parquet_path = repo_root / "data" / "normalized" / "answers_normalized.parquet"
    df = pd.read_parquet(parquet_path)

    mixed = df[df["epistemic_status"] == "mixed_uncertainty_and_preference"]
    assert len(mixed) == 5

    # Participant 007 Q12: "je ne peux pas encore répondre à cette question. Je n'ai pas assez d'expérience. \n(mais pourquoi y-a-t-il des bonus pour cela...?)"
    p07_q12 = df[(df["participant_id"] == "PARTICIPANT_007") & (df["question_id"] == "Q12")].iloc[0]
    assert "pas assez d'expérience" in p07_q12["raw_value"].lower()
    assert "pourquoi" in p07_q12["raw_value"].lower()
    assert p07_q12["has_usable_preference"] is True or p07_q12["has_usable_preference"] == 1
    assert p07_q12["missingness_state"] == MissingnessState.OBSERVED_USABLE.value
    assert "UNCERTAINTY_WITH_QUALITATIVE_CRITIQUE" in p07_q12["validation_flags"]


def test_ambiguous_text_preserved_for_coding(repo_root):
    """Verify ambiguous texts are not discarded and remain accessible for downstream Agent 02 coding."""
    parquet_path = repo_root / "data" / "normalized" / "answers_normalized.parquet"
    df = pd.read_parquet(parquet_path)

    # Participant 009 Q03: "à réfléchir encore un peu"
    p09_q03 = df[(df["participant_id"] == "PARTICIPANT_009") & (df["question_id"] == "Q03")].iloc[0]
    assert "réfléchir" in p09_q03["raw_value"]
    assert p09_q03["epistemic_status"] == "ambiguous"
    assert p09_q03["missingness_state"] == MissingnessState.AMBIGUOUS.value
    assert p09_q03["raw_value"] == p09_q03["source_text"]


def test_exact_source_preservation_and_offsets(repo_root):
    """Verify verbatim source text preservation and explicit offset reference invariant."""
    parquet_path = repo_root / "data" / "normalized" / "answers_normalized.parquet"
    df = pd.read_parquet(parquet_path)

    assert "source_text" in df.columns
    assert "normalized_text" in df.columns
    assert "offset_reference_text" in df.columns

    # Invariant: offset_reference_text must be 'source_text' across all rows
    assert (df["offset_reference_text"] == "source_text").all()

    # Exact equality between source_text and raw_value
    assert (df["source_text"] == df["raw_value"]).all()

    # Normalized text is stripped version of source text
    assert (df["normalized_text"] == df["source_text"].str.strip()).all()


def test_13_primary_questions_plus_optional_q14(repo_root):
    """Verify primary questions Q01-Q13 vs optional remarks Q14 and initial economic good policy."""
    registry_path = repo_root / "data" / "normalized" / "question_registry.json"
    assert registry_path.is_file(), "question_registry.json must exist"

    with open(registry_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    questions = data["questions"]
    assert len(questions) == 14
    assert data["substantive_question_count"] == 13
    assert data["primary_question_count"] == 13
    assert data["optional_remarks_question_count"] == 1

    # Verify primary questions Q01-Q13
    for i in range(1, 14):
        qid = f"Q{i:02d}"
        assert qid in questions, f"Primary question {qid} missing from registry"
        q_meta = questions[qid]
        assert q_meta["question_index"] == i
        assert q_meta["is_primary_question"] is True
        assert q_meta["question_scope"] == "primary"
        assert q_meta["observed_response_count"] + q_meta["missing_response_count"] == EXPECTED_RESPONDENT_COUNT
        assert len(q_meta["missing_participant_ids"]) == q_meta["missing_response_count"]

    # Verify optional contextual remarks Q14
    q14 = questions["Q14"]
    assert q14["is_primary_question"] is False
    assert q14["question_scope"] == "optional_contextual_remarks"

    # Initial economic good policy: perception questions are CONDITIONAL (initial guide, Agent 02 evaluates evidence)
    perception_qids = ["Q01", "Q02", "Q03", "Q06", "Q14"]
    for qid in perception_qids:
        assert questions[qid]["economic_good_classification_policy"] == "CONDITIONAL", (
            f"Question {qid} must have economic_good_classification_policy == 'CONDITIONAL'"
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

