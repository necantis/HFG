"""Survey Ingestion module entrypoint.

Owned by: Agent 01 — Data & Question Registry
Re-exports from src.ingest.ingestion for module compatibility.
"""

from src.ingest.ingestion import (
    SurveyIngester,
    ingest_survey,
    detect_language,
    classify_missingness,
    compute_sha256,
    EXPECTED_RAW_SHA256,
    EXPECTED_RESPONDENT_COUNT,
    EXPECTED_COLUMN_COUNT,
    QUESTION_MAP,
)

__all__ = [
    "SurveyIngester",
    "ingest_survey",
    "detect_language",
    "classify_missingness",
    "compute_sha256",
    "EXPECTED_RAW_SHA256",
    "EXPECTED_RESPONDENT_COUNT",
    "EXPECTED_COLUMN_COUNT",
    "QUESTION_MAP",
]

if __name__ == "__main__":
    import argparse
    from src.ingest.ingestion import ACTIVE_RUN_ID

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
    print(f"Observed usable: {(df_out['missingness_state'] == 'observed_usable').sum()} cells.")
    print(f"Missing blank: {(df_out['missingness_state'] == 'missing_raw_blank').sum()} cells.")
    print(f"Missing non-substantive: {(df_out['missingness_state'] == 'missing_non_substantive').sum()} cells.")
