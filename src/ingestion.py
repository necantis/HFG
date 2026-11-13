"""Survey Ingestion module entrypoint.

Owned by: Agent 01 — Data & Question Registry
Re-exports from src.ingest.ingestion for module compatibility.
"""

from src.ingest.ingestion import (
    SurveyIngester,
    ingest_survey,
    detect_language,
    classify_missingness,
    classify_response_semantics,
    compute_sha256,
    EXPECTED_RAW_SHA256,
    EXPECTED_RESPONDENT_COUNT,
    EXPECTED_COLUMN_COUNT,
    QUESTION_MAP,
    PRIMARY_QUESTIONS,
    OPTIONAL_REMARKS_QUESTIONS,
    ACTIVE_RUN_ID,
)

__all__ = [
    "SurveyIngester",
    "ingest_survey",
    "detect_language",
    "classify_missingness",
    "classify_response_semantics",
    "compute_sha256",
    "EXPECTED_RAW_SHA256",
    "EXPECTED_RESPONDENT_COUNT",
    "EXPECTED_COLUMN_COUNT",
    "QUESTION_MAP",
    "PRIMARY_QUESTIONS",
    "OPTIONAL_REMARKS_QUESTIONS",
    "ACTIVE_RUN_ID",
]

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Ingest raw survey CSV into normalized long-format answers.")
    parser.add_argument("--raw-csv", default="data/raw/survey_raw.csv", help="Path to raw CSV file.")
    parser.add_argument("--out-parquet", default="data/normalized/answers_normalized.parquet", help="Output parquet path.")
    parser.add_argument("--out-json", default="data/normalized/answers_normalized.json", help="Output json path.")
    parser.add_argument("--run-id", default=ACTIVE_RUN_ID, help="Active run ID.")
    args = parser.parse_args()

    print(f"Ingesting raw survey from {args.raw_csv}...")
    df_out = ingest_survey(
        raw_csv_path=args.raw_csv,
        output_parquet=args.out_parquet,
        output_json=args.out_json,
        run_id=args.run_id,
    )
    print(f"Successfully normalized {len(df_out)} answer records across {df_out['participant_id'].nunique()} participants.")
    print("Epistemic Status Breakdown:")
    for status, count in df_out["epistemic_status"].value_counts().items():
        print(f"  {status}: {count}")
    print("Missingness State Breakdown:")
    for state, count in df_out["missingness_state"].value_counts().items():
        print(f"  {state}: {count}")
    print(f"Text supplied: {df_out['text_supplied'].sum()} / {len(df_out)}")
    print(f"Has usable preference: {df_out['has_usable_preference'].sum()} / {len(df_out)}")
