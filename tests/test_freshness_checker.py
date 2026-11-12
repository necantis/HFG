"""
Tests for HFG Freshness Checker.
"""

from pathlib import Path
import pytest
from src.freshness_checker import FreshnessChecker


def test_freshness_checker_active_repo():
    checker = FreshnessChecker()
    report = checker.run_all_checks()

    # In our properly maintained repository, all 9 checks must pass!
    assert len(report.passed_categories) == 9
    assert report.issues_found == 0


def test_detects_obsolete_model_name(tmp_path):
    # Set up mock repo with an obsolete model name
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    bad_doc = docs_dir / "bad_model.md"
    bad_doc.write_text("We use model gpt-3.5 for this task.", encoding="utf-8")

    checker = FreshnessChecker(base_dir=tmp_path)
    issues = checker.check_obsolete_model_names()

    assert len(issues) == 1
    assert issues[0].category == "obsolete_model_names"
    assert "gpt-3.5" in issues[0].description


def test_detects_unowned_or_missing_notebooks(tmp_path):
    agents_file = tmp_path / "AGENTS.md"
    agents_file.write_text("# AGENTS\nNo notebooks here.", encoding="utf-8")

    checker = FreshnessChecker(base_dir=tmp_path)
    issues = checker.check_stale_notebook_ownership()

    assert len(issues) > 0
    assert any("notebooks/01_" in iss.description for iss in issues)


def test_detects_unresolved_evidence_ids(tmp_path):
    proc_dir = tmp_path / "data" / "processed"
    norm_dir = tmp_path / "data" / "normalized"
    proc_dir.mkdir(parents=True, exist_ok=True)
    norm_dir.mkdir(parents=True, exist_ok=True)

    # Valid response id: RESP_100
    norm_file = norm_dir / "answers_normalized.json"
    norm_file.write_text('[{"response_id": "RESP_100"}]', encoding="utf-8")

    # Theme references non-existent evidence ID: RESP_999
    theme_file = proc_dir / "themes_codebook.json"
    theme_file.write_text(
        '{"themes": [{"theme_id": "TH-1", "evidence_response_ids": ["RESP_999"]}]}',
        encoding="utf-8",
    )

    checker = FreshnessChecker(base_dir=tmp_path)
    issues = checker.check_unresolved_evidence_ids()

    assert len(issues) == 1
    assert issues[0].category == "unresolved_evidence_ids"
    assert "RESP_999" in issues[0].description
