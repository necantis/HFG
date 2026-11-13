"""Ingestion module for HFG survey data.

Owned by: Agent 01 — Data & Question Registry
"""

from src.ingest.ingestion import SurveyIngester, ingest_survey, detect_language, classify_missingness

__all__ = [
    "SurveyIngester",
    "ingest_survey",
    "detect_language",
    "classify_missingness",
]
