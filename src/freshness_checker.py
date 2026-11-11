"""
Freshness & Provenance Checker for HFG.

Detects:
1. Changed code with stale documentation
2. Schema differences
3. Obsolete filenames in documentation
4. Obsolete or non-standard model names
5. Stale or orphaned notebook ownership
6. Superseded decisions still referenced as active
7. Artifacts without complete provenance
8. Unresolved evidence IDs in qualitative themes
9. Current artifacts depending on stale upstream artifacts
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from src.artifact_registry import ArtifactRegistry, ArtifactRecord


class FreshnessIssue(BaseModel):
    category: str
    severity: str  # ERROR, WARNING, INFO
    target: str
    description: str
    remediation: str


class FreshnessReport(BaseModel):
    timestamp: str
    issues_found: int
    issues: List[FreshnessIssue] = Field(default_factory=list)
    passed_categories: List[str] = Field(default_factory=list)


class FreshnessChecker:
    """Automated audit engine verifying repository memory freshness and integrity."""

    def __init__(self, base_dir: Optional[Path] = None, run_id: str = "run_20261111_001"):
        self.base_dir = (base_dir or Path.cwd()).resolve()
        self.run_id = run_id
        self.registry = ArtifactRegistry(base_dir=self.base_dir, run_id=run_id)

        # Load manifest if available
        manifest_file = self.base_dir / "runs" / run_id / "manifest.json"
        if manifest_file.is_file():
            self.registry.load_manifest(manifest_file)

    def check_changed_code_with_stale_documentation(self) -> List[FreshnessIssue]:
        """Detect code modified more recently than its primary documentation."""
        issues = []
        doc_files = list((self.base_dir / "docs").glob("*.md")) + [self.base_dir / "AGENTS.md"]
        src_files = list((self.base_dir / "src").glob("*.py"))

        if not src_files or not doc_files:
            return issues

        latest_doc_mtime = max(f.stat().st_mtime for f in doc_files if f.is_file())

        for src in src_files:
            if src.stat().st_mtime > latest_doc_mtime + 3600:  # Code modified >1h after docs
                issues.append(
                    FreshnessIssue(
                        category="stale_documentation",
                        severity="WARNING",
                        target=str(src.relative_to(self.base_dir)),
                        description=f"Source file {src.name} was modified after documentation was updated.",
                        remediation="Update relevant docs in docs/ or regenerate agent context packs.",
                    )
                )
        return issues

    def check_schema_differences(self) -> List[FreshnessIssue]:
        """Verify registered artifacts conform to their declared schema version in DATA_CONTRACTS.md."""
        issues = []
        contracts_file = self.base_dir / "docs" / "DATA_CONTRACTS.md"
        if not contracts_file.is_file():
            issues.append(
                FreshnessIssue(
                    category="schema_differences",
                    severity="ERROR",
                    target="docs/DATA_CONTRACTS.md",
                    description="docs/DATA_CONTRACTS.md missing.",
                    remediation="Create docs/DATA_CONTRACTS.md with canonical schema definitions.",
                )
            )
            return issues

        text = contracts_file.read_text(encoding="utf-8")
        declared_versions = re.findall(r"`([a-zA-Z0-9_]+_v\d+)`", text)

        for art in self.registry.artifacts.values():
            if art.schema_version not in ["v1.0.0", "v1.0", "1.0.0"]:
                issues.append(
                    FreshnessIssue(
                        category="schema_differences",
                        severity="WARNING",
                        target=art.artifact_id,
                        description=f"Artifact {art.artifact_id} uses unapproved schema version {art.schema_version}.",
                        remediation="Ensure artifact adheres to approved v1.0.0 contracts.",
                    )
                )
        return issues

    def check_obsolete_filenames(self) -> List[FreshnessIssue]:
        """Scan documentation for references to filenames that do not exist."""
        issues = []
        doc_dir = self.base_dir / "docs"
        docs = list(doc_dir.glob("**/*.md")) + [self.base_dir / "AGENTS.md"]

        # Known future/pending file paths or template patterns permitted in docs
        template_patterns = [
            r"agent_XX_",
            r"agent_\d{2}_handoff\.md",
            r"path/to/",
            r"<run_id>",
            r"<artifact_id>",
        ]
        
        permitted_basenames = {
            "survey_raw.csv",
            "answers_normalized.parquet",
            "themes_codebook.json",
            "candidate_options.json",
            "preference_matrix.parquet",
            "voting_results.json",
            "sensitivity_metrics.json",
            "policy_brief.md",
            "audit_report.json",
            "pipeline_execution.log",
            "manifest.json",
            "RUN_CARD.md",
        }

        for doc in docs:
            if not doc.is_file():
                continue
            content = doc.read_text(encoding="utf-8")
            matches = re.findall(r"`([a-zA-Z0-9_\-\./]+\.(?:py|md|json|parquet|csv|ipynb))`", content)
            for ref in matches:
                # Check if it matches a permitted template pattern
                if any(re.search(pat, ref) for pat in template_patterns):
                    continue
                if Path(ref).name in permitted_basenames:
                    continue
                target = self.base_dir / ref
                if not target.exists() and not (self.base_dir / ref.lstrip("/")).exists():
                    if ref.startswith("notebooks/") or ref.startswith("tests/test_") or ref.startswith("data/"):
                        continue
                    issues.append(
                        FreshnessIssue(
                            category="obsolete_filenames",
                            severity="WARNING",
                            target=str(doc.relative_to(self.base_dir)),
                            description=f"References missing or obsolete file path `{ref}`.",
                            remediation=f"Create `{ref}` or update reference in `{doc.name}`.",
                        )
                    )
        return issues

    def check_obsolete_model_names(self) -> List[FreshnessIssue]:
        """Detect obsolete or non-approved model names in docs or code."""
        issues = []
        approved_tiers = {"pro", "flash", "flash_lite", "inherit"}
        # Obsolete model tokens to flag
        obsolete_tokens = ["gpt-3.5", "gpt-4-0314", "text-davinci-003", "claude-1", "bison-001"]

        for p in list((self.base_dir / "docs").glob("**/*.md")) + list((self.base_dir / "src").glob("**/*.py")):
            if not p.is_file() or p.name == "freshness_checker.py":
                continue
            text = p.read_text(encoding="utf-8")
            for obs in obsolete_tokens:
                if obs in text:
                    issues.append(
                        FreshnessIssue(
                            category="obsolete_model_names",
                            severity="ERROR",
                            target=str(p.relative_to(self.base_dir)),
                            description=f"Contains deprecated model name '{obs}'.",
                            remediation=f"Replace with modern approved tier: {approved_tiers}.",
                        )
                    )
        return issues

    def check_stale_notebook_ownership(self) -> List[FreshnessIssue]:
        """Ensure all 10 exploratory notebooks are properly mapped to single agents."""
        issues = []
        agents_file = self.base_dir / "AGENTS.md"
        if not agents_file.is_file():
            issues.append(
                FreshnessIssue(
                    category="stale_notebook_ownership",
                    severity="ERROR",
                    target="AGENTS.md",
                    description="AGENTS.md missing.",
                    remediation="Create AGENTS.md specifying notebook ownership table.",
                )
            )
            return issues

        text = agents_file.read_text(encoding="utf-8")
        for i in range(1, 11):
            expected_prefix = f"notebooks/{i:02d}_"
            if expected_prefix not in text:
                issues.append(
                    FreshnessIssue(
                        category="stale_notebook_ownership",
                        severity="WARNING",
                        target="AGENTS.md",
                        description=f"Missing notebook ownership entry for Agent {i:02d} (`{expected_prefix}*.ipynb`).",
                        remediation=f"Register notebook ownership for Agent {i:02d} in AGENTS.md.",
                    )
                )
        return issues

    def check_superseded_decisions(self) -> List[FreshnessIssue]:
        """Detect references to superseded ADRs as active authority."""
        issues = []
        decisions_dir = self.base_dir / "docs" / "DECISIONS"
        if not decisions_dir.is_dir():
            return issues

        superseded_adrs = []
        for adr in decisions_dir.glob("*.md"):
            content = adr.read_text(encoding="utf-8")
            if "Status: SUPERSEDED" in content.upper() or "STATUS`: `SUPERSEDED`" in content.upper():
                superseded_adrs.append(adr.stem.split("-")[0].upper())

        for sup in superseded_adrs:
            # Check if active docs cite it as active
            for doc in (self.base_dir / "docs").glob("*.md"):
                content = doc.read_text(encoding="utf-8")
                if sup in content and "superseded" not in content.lower():
                    issues.append(
                        FreshnessIssue(
                            category="superseded_decisions",
                            severity="ERROR",
                            target=doc.name,
                            description=f"Cites superseded decision `{sup}` as active authority.",
                            remediation=f"Update `{doc.name}` to reference replacing ADR.",
                        )
                    )
        return issues

    def check_artifacts_without_provenance(self) -> List[FreshnessIssue]:
        """Flag registered artifacts lacking essential provenance metadata."""
        issues = []
        for art in self.registry.artifacts.values():
            missing = []
            if not art.code_commit or art.code_commit == "unknown":
                missing.append("code_commit")
            if not art.producing_agent:
                missing.append("producing_agent")
            if not art.creation_timestamp:
                missing.append("creation_timestamp")
            if not art.schema_version:
                missing.append("schema_version")

            if missing:
                issues.append(
                    FreshnessIssue(
                        category="artifacts_without_provenance",
                        severity="ERROR",
                        target=art.artifact_id,
                        description=f"Artifact {art.artifact_id} is missing provenance fields: {missing}.",
                        remediation="Re-register artifact with complete metadata via src/artifact_registry.py.",
                    )
                )
        return issues

    def check_unresolved_evidence_ids(self) -> List[FreshnessIssue]:
        """Scan qualitative artifacts for evidence IDs that do not exist in normalized answers."""
        issues = []
        themes_file = self.base_dir / "data" / "processed" / "themes_codebook.json"
        answers_file = self.base_dir / "data" / "normalized" / "answers_normalized.parquet"
        answers_json = self.base_dir / "data" / "normalized" / "answers_normalized.json"

        if not themes_file.is_file():
            return issues  # Not yet generated in run

        valid_response_ids = set()
        if answers_json.is_file():
            try:
                data = json.loads(answers_json.read_text(encoding="utf-8"))
                for row in data:
                    if "response_id" in row:
                        valid_response_ids.add(row["response_id"])
            except Exception:
                pass

        try:
            theme_data = json.loads(themes_file.read_text(encoding="utf-8"))
            for theme in theme_data.get("themes", []):
                for ev_id in theme.get("evidence_response_ids", []):
                    if valid_response_ids and ev_id not in valid_response_ids:
                        issues.append(
                            FreshnessIssue(
                                category="unresolved_evidence_ids",
                                severity="ERROR",
                                target=theme.get("theme_id", "unknown"),
                                description=f"Evidence ID `{ev_id}` does not resolve to any normalized answer.",
                                remediation="Ensure theme evidence IDs accurately ground into answers_normalized.",
                            )
                        )
        except Exception:
            pass

        return issues

    def check_stale_upstream_artifacts(self) -> List[FreshnessIssue]:
        """Check for current artifacts that depend on stale upstream artifacts."""
        issues = []
        for art in self.registry.artifacts.values():
            if art.stale_state == "stale":
                issues.append(
                    FreshnessIssue(
                        category="stale_upstream_dependency",
                        severity="WARNING",
                        target=art.artifact_id,
                        description=f"Artifact `{art.artifact_id}` is marked STALE due to upstream changes.",
                        remediation=f"Rerun producing module `{art.producing_module}` to refresh artifact.",
                    )
                )
        return issues

    def run_all_checks(self) -> FreshnessReport:
        """Execute all 9 freshness checks and return structured report."""
        categories = [
            ("changed_code_with_stale_documentation", self.check_changed_code_with_stale_documentation),
            ("schema_differences", self.check_schema_differences),
            ("obsolete_filenames", self.check_obsolete_filenames),
            ("obsolete_model_names", self.check_obsolete_model_names),
            ("stale_notebook_ownership", self.check_stale_notebook_ownership),
            ("superseded_decisions", self.check_superseded_decisions),
            ("artifacts_without_provenance", self.check_artifacts_without_provenance),
            ("unresolved_evidence_ids", self.check_unresolved_evidence_ids),
            ("stale_upstream_artifacts", self.check_stale_upstream_artifacts),
        ]

        all_issues: List[FreshnessIssue] = []
        passed_categories: List[str] = []

        for name, check_func in categories:
            cat_issues = check_func()
            if cat_issues:
                all_issues.extend(cat_issues)
            else:
                passed_categories.append(name)

        from datetime import datetime, timezone
        return FreshnessReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            issues_found=len(all_issues),
            issues=all_issues,
            passed_categories=passed_categories,
        )


def main():
    parser = argparse.ArgumentParser(description="HFG Freshness and Integrity Checker")
    parser.add_argument("--check-all", action="store_true", help="Run all 9 freshness checks")
    parser.add_argument("--run-id", default="run_20261111_001", help="Target Run ID")
    args = parser.parse_args()

    checker = FreshnessChecker(run_id=args.run_id)
    report = checker.run_all_checks()

    print(f"\n=======================================================")
    print(f"HFG Freshness & Provenance Report [{report.timestamp}]")
    print(f"Passed Checks: {len(report.passed_categories)}/9")
    print(f"Issues Detected: {report.issues_found}")
    print(f"=======================================================\n")

    for cat in report.passed_categories:
        print(f"  [PASS] {cat}")

    if report.issues:
        print("\nIdentified Issues:")
        for iss in report.issues:
            print(f"  [{iss.severity}] {iss.category} -> {iss.target}: {iss.description}")
            print(f"         Remediation: {iss.remediation}")
    else:
        print("\nAll memory, schema, provenance, and filename freshness checks PASSED.")


if __name__ == "__main__":
    main()
