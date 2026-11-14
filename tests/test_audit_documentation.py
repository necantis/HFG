"""Auditability & Consistency Tests for Agent 10 Documentation Deliverables."""

from __future__ import annotations

import csv
import re
from pathlib import Path

from src.freshness_checker import FreshnessChecker


REPO_ROOT = Path(__file__).resolve().parents[1]


def _extract_markdown_links(markdown_text: str) -> list[str]:
    return re.findall(r"\[[^\]]+\]\(([^)#]+)(?:#[^)]*)?\)", markdown_text)


def test_audit_documentation_files_exist_and_cover_required_sections() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    audit_trail = (REPO_ROOT / "docs" / "AUDIT_TRAIL.md").read_text(encoding="utf-8")
    repro = (REPO_ROOT / "docs" / "REPRODUCIBILITY.md").read_text(encoding="utf-8")
    provenance = (REPO_ROOT / "docs" / "ARTIFACT_PROVENANCE.md").read_text(encoding="utf-8")

    for section in [
        "# HFG",
        "## Purpose",
        "## Analytical Principles",
        "## Dataset and Current Run (`run_20261111_002`)",
        "## 12-Agent Architecture",
        "## Pipeline",
        "## Execution Profiles",
        "## Models",
        "## GPU Execution",
        "## Checkpointing",
        "## Reproducibility",
        "## Evidence Provenance",
        "## Validation and QA",
        "## Repository Map",
    ]:
        assert section in readme, f"Missing section in README.md: {section}"

    # Verify dataset invariants & truthful readiness reporting
    assert "run_20261111_002" in readme
    assert "11" in readme and "154" in readme and "136" in readme
    assert "BLOCKED" in readme
    assert "smoke_tiny" in readme and "pilot_subset" in readme and "production" in readme

    # Chronological PR #1-#9 milestones & honest unexecuted state in AUDIT_TRAIL.md
    for token in ["run_20261111_002", "PR #1", "PR #2", "PR #4", "PR #5", "PR #6", "PR #7", "PR #8", "PR #9", "NOT_EXECUTED", "BLOCKED"]:
        assert token in audit_trail, f"Missing milestone/status in AUDIT_TRAIL.md: {token}"

    # Practical reproducibility separation A-E
    for stage in ["Stage A", "Stage B", "Stage C", "Stage D", "Stage E", "smoke_tiny", "pilot_subset", "production"]:
        assert stage in repro, f"Missing reproducibility stage: {stage}"

    # Artifact provenance complete table columns
    for col in ["Artifact", "Producer", "Schema / Contract", "Authority Level", "Git Tracked?", "Downstream Consumers", "PLANNED / BLOCKED"]:
        assert col in provenance, f"Missing provenance metadata: {col}"


def test_audit_documentation_links_resolve() -> None:
    targets = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "docs" / "AUDIT_TRAIL.md",
        REPO_ROOT / "docs" / "REPRODUCIBILITY.md",
        REPO_ROOT / "docs" / "ARTIFACT_PROVENANCE.md",
    ]
    for doc_path in targets:
        text = doc_path.read_text(encoding="utf-8")
        for link in _extract_markdown_links(text):
            if link.startswith(("http://", "https://", "mailto:")):
                continue
            resolved = (doc_path.parent / link).resolve()
            assert resolved.exists(), f"{doc_path.relative_to(REPO_ROOT)} contains broken link: {link}"


def test_audit_documentation_contains_no_participant_answer_text() -> None:
    raw_csv = REPO_ROOT / "data" / "raw" / "survey_raw.csv"
    assert raw_csv.is_file()

    # Collect genuine long respondent strings (> 35 chars) from data rows (skipping header & IDs)
    respondent_snippets: list[str] = []
    with raw_csv.open("r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        next(reader)  # header
        for row in reader:
            for cell in row[1:]:
                val = cell.strip()
                if len(val) > 35:
                    respondent_snippets.append(val[:40])

    assert respondent_snippets, "Expected non-trivial survey cells in raw CSV baseline."

    docs_to_scan = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "docs" / "AUDIT_TRAIL.md",
        REPO_ROOT / "docs" / "REPRODUCIBILITY.md",
        REPO_ROOT / "docs" / "ARTIFACT_PROVENANCE.md",
    ]
    for doc_path in docs_to_scan:
        content = doc_path.read_text(encoding="utf-8")
        for snippet in respondent_snippets:
            assert snippet not in content, f"Participant answer leak detected in {doc_path.name}"


def test_freshness_checker_passes_with_audit_docs() -> None:
    report = FreshnessChecker(base_dir=REPO_ROOT, run_id="run_20261111_002").run_all_checks()
    assert report.issues_found == 0, f"Freshness issues: {[i.model_dump() for i in report.issues]}"
