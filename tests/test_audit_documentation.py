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

    # Verify dataset invariants, raw-SHA verification, frozen FRONTIER_A, FRONTIER_B & Agent 08 hold
    for token in [
        "run_20261111_002",
        "11",
        "154",
        "136",
        "ADR-0008",
        "ADR-0009",
        "56acded3e02be49be27d6b288fa2c43fcce68df24525113eba1b1161eec52a95",
        "FRONTIER_A",
        "OBSERVED_DESIGN_FRONTIER",
        "543",
        "326",
        "ROBUSTLY_NONDOMINATED",
        "CONDITIONALLY_NONDOMINATED",
        "UNRESOLVED_DUE_TO_CODING_UNCERTAINTY",
        "ROBUSTLY_DOMINATED",
        "248",
        "285",
        "102",
        "NO_STABLE_CLUSTER_STRUCTURE",
        "NO_ROBUST_SINGLE_WINNER",
        "BALDWIN = NOT_APPLICABLE",
        "RRV = NOT_APPLICABLE",
        "A robust Pareto core exists, but no single collective-choice winner is stable across the admissible uncertainty scenarios.",
        "FRONTIER_B",
        "RESOURCE_REGIME_EXPANDED_FRONTIER",
        "CLUB_GOOD",
        "non_member_compulsory_contribution = 0.0",
        "CONDITIONAL_RESOURCE_ONLY",
        "OBSERVED_RESPONDENT_PREFERENCE",
        "INSTITUTIONALLY_DERIVED_MECHANISM",
        "COUNTERFACTUAL_PREFERENCE_ASSUMPTION",
        "UNRESOLVED_DUE_TO_COUNTERFACTUAL_UTILITY",
        "NEW_LLM_CODING_REQUIRED = NO",
        "AGENT_08_TECHNICAL_RELEASE = READY",
        "AGENT_08_REPORTING_STATUS = HELD_FOR_RESOURCE_REGIME_SENSITIVITY",
        "smoke_tiny",
        "pilot_subset",
        "production",
        "ISSUE-009",
    ]:
        assert token in readme, f"Missing required ADR-0009 / audit token in README.md: {token}"

    # Chronological PR #1-#23 milestones, raw-SHA audit, & ADR-0009 state in AUDIT_TRAIL.md
    for token in [
        "run_20261111_002",
        *[f"PR #{i}" for i in (1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23)],
        "ADR-0008",
        "ADR-0009",
        "6508ded",
        "56acded3e02be49be27d6b288fa2c43fcce68df24525113eba1b1161eec52a95",
        "eb526813aadcfab2b4b157e7b6513de50e6b3178",
        "FRONTIER_A",
        "OBSERVED_DESIGN_FRONTIER",
        "FRONTIER_B",
        "RESOURCE_REGIME_EXPANDED_FRONTIER",
        "NEW_LLM_CODING_REQUIRED = NO",
        "AGENT_08_TECHNICAL_RELEASE = READY",
        "AGENT_08_REPORTING_STATUS = HELD_FOR_RESOURCE_REGIME_SENSITIVITY",
        "ISSUE-009",
    ]:
        assert token in audit_trail, f"Missing milestone/status in AUDIT_TRAIL.md: {token}"

    # Practical reproducibility separation A-F + truthful dependency disclosure
    for token in [
        "Stage A",
        "Stage B",
        "Stage C",
        "Stage D",
        "Stage E",
        "Stage F",
        "smoke_tiny",
        "pilot_subset",
        "production",
        "ADR-0009",
        "NEW_LLM_CODING_REQUIRED = NO",
        "FRONTIER_A",
        "FRONTIER_B",
        "ISSUE-009",
        "tests/test_clustering.py",
        "pyproject.toml",
        "scipy",
    ]:
        assert token in repro, f"Missing reproducibility stage or disclosure: {token}"

    # Artifact provenance complete table columns & 3-way counterfactual provenance rule
    for col in [
        "Artifact",
        "Producer",
        "Schema / Contract",
        "Authority Level",
        "Git Tracked?",
        "Downstream Consumers",
        "PLANNED / BLOCKED",
        "FRONTIER_A",
        "FRONTIER_B",
        "OBSERVED_RESPONDENT_PREFERENCE",
        "INSTITUTIONALLY_DERIVED_MECHANISM",
        "COUNTERFACTUAL_PREFERENCE_ASSUMPTION",
        "AGENT_08_REPORTING_STATUS = HELD_FOR_RESOURCE_REGIME_SENSITIVITY",
    ]:
        assert col in provenance, f"Missing provenance metadata: {col}"

    # Governance state sync: ISSUE-005 & ISSUE-007 resolved, ISSUE-008 & ISSUE-009 open
    open_issues = (REPO_ROOT / "docs" / "OPEN_ISSUES.md").read_text(encoding="utf-8")
    assert re.search(r"\|\s*`ISSUE-005`\s*\|[^\n]*\|\s*`RESOLVED`\s*\|", open_issues), "ISSUE-005 must be RESOLVED"
    assert re.search(r"\|\s*`ISSUE-007`\s*\|[^\n]*\|\s*`RESOLVED`\s*\|", open_issues), "ISSUE-007 must be RESOLVED"
    assert re.search(r"\|\s*`ISSUE-008`\s*\|[^\n]*\|\s*`OPEN`\s*\|", open_issues), "ISSUE-008 must be OPEN"
    assert re.search(r"\|\s*`ISSUE-009`\s*\|[^\n]*\|\s*`OPEN`\s*\|", open_issues), "ISSUE-009 must be OPEN"

    project_state = (REPO_ROOT / "docs" / "PROJECT_STATE.md").read_text(encoding="utf-8")
    for token in [
        "56acded3e02be49be27d6b288fa2c43fcce68df24525113eba1b1161eec52a95",
        "FRONTIER_A = OBSERVED_DESIGN_FRONTIER",
        "543",
        "326",
        "ROBUSTLY_NONDOMINATED",
        "CONDITIONALLY_NONDOMINATED",
        "UNRESOLVED_DUE_TO_CODING_UNCERTAINTY",
        "ROBUSTLY_DOMINATED",
        "248",
        "285",
        "102",
        "NO_STABLE_CLUSTER_STRUCTURE",
        "NO_ROBUST_SINGLE_WINNER",
        "BALDWIN = NOT_APPLICABLE",
        "RRV = NOT_APPLICABLE",
        "A robust Pareto core exists, but no single collective-choice winner is stable across the admissible uncertainty scenarios.",
        "FRONTIER_B = RESOURCE_REGIME_EXPANDED_FRONTIER",
        "CONDITIONAL_RESOURCE_ONLY",
        "non_member_compulsory_contribution = 0.0",
        "OBSERVED_RESPONDENT_PREFERENCE",
        "INSTITUTIONALLY_DERIVED_MECHANISM",
        "COUNTERFACTUAL_PREFERENCE_ASSUMPTION",
        "UNRESOLVED_DUE_TO_COUNTERFACTUAL_UTILITY",
        "NEW_LLM_CODING_REQUIRED = NO",
        "AGENT_08_TECHNICAL_RELEASE = READY",
        "AGENT_08_REPORTING_STATUS = HELD_FOR_RESOURCE_REGIME_SENSITIVITY",
    ]:
        assert token in project_state, f"Missing token in PROJECT_STATE.md: {token}"

    for aid in ("00", "03", "04", "05", "06", "08", "09", "10", "11"):
        ctx = (REPO_ROOT / "docs" / "AGENT_CONTEXT" / f"agent_{aid}_context.md").read_text(encoding="utf-8")
        assert "ADR-0009" in ctx, f"agent_{aid}_context.md missing ADR-0009"

    ctx_04 = (REPO_ROOT / "docs" / "AGENT_CONTEXT" / "agent_04_context.md").read_text(encoding="utf-8")
    for token in [
        "FRONTIER_B",
        "OBSERVED_DESIGN_FRONTIER",
        "non_member_compulsory_contribution",
        "UNRESOLVED_DUE_TO_COUNTERFACTUAL_UTILITY",
        "NEW_LLM_CODING_REQUIRED = NO",
        "arbitrary point utility",
        "refusal to pay",
    ]:
        assert token in ctx_04, f"agent_04_context.md missing ADR-0009 guard: {token}"

    ctx_08 = (REPO_ROOT / "docs" / "AGENT_CONTEXT" / "agent_08_context.md").read_text(encoding="utf-8")
    assert "AGENT_08_TECHNICAL_RELEASE = READY" in ctx_08
    assert "AGENT_08_REPORTING_STATUS = HELD_FOR_RESOURCE_REGIME_SENSITIVITY" in ctx_08

    ctx_11 = (REPO_ROOT / "docs" / "AGENT_CONTEXT" / "agent_11_context.md").read_text(encoding="utf-8")
    assert "ISSUE-008" in ctx_11 and "ISSUE-009" in ctx_11
    assert "pyproject.toml" in ctx_11
    assert "AGENT_08_REPORTING_STATUS = HELD_FOR_RESOURCE_REGIME_SENSITIVITY" in ctx_11


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
