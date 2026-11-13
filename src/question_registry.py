"""Question Registry module entrypoint.

Owned by: Agent 01 — Data & Question Registry
Re-exports from src.registry.question_registry for module compatibility.
"""

from src.registry.question_registry import (
    QuestionRegistry,
    build_question_registry,
    QUESTION_METADATA,
)

__all__ = [
    "QuestionRegistry",
    "build_question_registry",
    "QUESTION_METADATA",
]

if __name__ == "__main__":
    import argparse
    from src.ingest.ingestion import ACTIVE_RUN_ID

    parser = argparse.ArgumentParser(description="Build and serialize question registry.")
    parser.add_argument("--answers", default="data/normalized/answers_normalized.parquet", help="Path to normalized answers.")
    parser.add_argument("--raw-csv", default="data/raw/survey_raw.csv", help="Path to raw CSV.")
    parser.add_argument("--out-json", default="data/normalized/question_registry.json", help="Output JSON path.")
    parser.add_argument("--run-id", default=ACTIVE_RUN_ID, help="Active run ID.")
    args = parser.parse_args()

    reg = build_question_registry(
        answers_df_or_path=args.answers,
        raw_csv_path=args.raw_csv,
        output_json=args.out_json,
        run_id=args.run_id,
    )
    print(f"Successfully registered {len(reg.specs)} questions ({len(reg.get_substantive_questions())} substantive).")
    for q in reg.list_questions():
        print(f"  {q.question_id} (Q{q.question_index:02d}): observed={q.observed_response_count}, missing={q.missing_response_count}, frame={q.analytical_frame.value}, economic_good_policy={q.economic_good_classification_policy}")
