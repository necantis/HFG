"""
Context Pack Generator for HFG Agents.

Compiles scoped, high-signal context packs for individual agents:
`docs/AGENT_CONTEXT/agent_XX_context.md`
containing only the mission, architecture, owned files, interfaces,
dependencies, canonical artifacts, open issues, ADRs, and acceptance criteria.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AgentSpec(BaseModel):
    agent_id: str
    numeric_id: str
    title: str
    mission: str
    owned_files: List[str]
    owned_notebook: str
    forbidden_files: List[str]
    input_interfaces: List[str]
    output_interfaces: List[str]
    upstream_artifacts: List[str]
    downstream_dependencies: List[str]
    canonical_artifacts: List[str]
    relevant_adrs: List[str]
    relevant_issue_ids: List[str]
    acceptance_criteria: List[str]
    test_commands: List[str]


# Authoritative Agent Specification Catalog
AGENT_SPECS: Dict[str, AgentSpec] = {
    "agent_01": AgentSpec(
        agent_id="agent_01",
        numeric_id="01",
        title="Ingestion & Normalization Engineer",
        mission=(
            "Ingest raw survey CSV/Excel inputs, enforce survey isolation invariants, "
            "validate data against survey_raw_v1, and transform responses into the canonical "
            "normalized long-format answers artifact (answers_normalized_v1)."
        ),
        owned_files=["src/ingest/"],
        owned_notebook="notebooks/01_ingest_exploration.ipynb",
        forbidden_files=["data/raw/* (write-protected)", "src/nlp/", "src/preference/", "docs/DECISIONS/"],
        input_interfaces=["survey_raw_v1 (data/raw/survey_raw.csv)"],
        output_interfaces=["answers_normalized_v1 (data/normalized/answers_normalized.parquet)"],
        upstream_artifacts=["data/raw/survey_raw.csv"],
        downstream_dependencies=["agent_02 (Qualitative Coding)", "agent_04 (Preference Learning)"],
        canonical_artifacts=[
            "`data/raw/survey_raw.csv` (Immutable Source)",
            "`data/normalized/answers_normalized.parquet` (Canonical Ingestion Artifact)",
        ],
        relevant_adrs=["ADR-0001", "ADR-0002", "ADR-0004"],
        relevant_issue_ids=["ISSUE-001"],
        acceptance_criteria=[
            "Raw survey data is ingested without modifying or overwriting data/raw/survey_raw.csv.",
            "Normalized answers validate against answers_normalized_v1 schema.",
            "All participant IDs are preserved without data loss.",
            "Output artifact is registered with artifact_registry.py.",
        ],
        test_commands=["pytest tests/test_ingest.py -v"],
    ),
    "agent_02": AgentSpec(
        agent_id="agent_02",
        numeric_id="02",
        title="Qualitative Coding & Entity Specialist",
        mission=(
            "Perform rigorous qualitative coding on open-ended survey responses, "
            "synthesize thematic codebooks, and extract participant themes without lexical "
            "or entity leakage from other survey populations."
        ),
        owned_files=["src/nlp/"],
        owned_notebook="notebooks/02_qualitative_coding.ipynb",
        forbidden_files=["data/raw/*", "src/ingest/", "src/candidates/", "src/preference/"],
        input_interfaces=["answers_normalized_v1 (data/normalized/answers_normalized.parquet)"],
        output_interfaces=["themes_codebook_v1 (data/processed/themes_codebook.json)"],
        upstream_artifacts=["data/normalized/answers_normalized.parquet"],
        downstream_dependencies=["agent_03 (Candidate Synthesis)", "agent_07 (Presentation Reporting)"],
        canonical_artifacts=[
            "`data/normalized/answers_normalized.parquet` (Canonical Ingestion Artifact)",
            "`data/processed/themes_codebook.json` (Canonical Qualitative Artifact)",
        ],
        relevant_adrs=["ADR-0001", "ADR-0002", "ADR-0004"],
        relevant_issue_ids=["ISSUE-004"],
        acceptance_criteria=[
            "Every extracted theme includes explicit evidence_response_ids grounded in answers_normalized.parquet.",
            "Themes pass cross-contamination check: zero entities or candidates from foreign survey groups.",
            "themes_codebook.json validates against themes_codebook_v1 contract.",
        ],
        test_commands=["pytest tests/test_nlp.py -v"],
    ),
    "agent_03": AgentSpec(
        agent_id="agent_03",
        numeric_id="03",
        title="Candidate & Option Synthesizer",
        mission=(
            "Synthesize discrete candidate options and policy proposals from grounded qualitative "
            "themes. Ensure all candidates are grounded in participant evidence."
        ),
        owned_files=["src/candidates/"],
        owned_notebook="notebooks/03_candidate_generation.ipynb",
        forbidden_files=["data/raw/*", "src/ingest/", "src/social_choice/"],
        input_interfaces=["themes_codebook_v1 (data/processed/themes_codebook.json)"],
        output_interfaces=["candidate_options_v1 (data/processed/candidate_options.json)"],
        upstream_artifacts=["data/processed/themes_codebook.json"],
        downstream_dependencies=["agent_04 (Preference Learning)", "agent_05 (Social Choice)"],
        canonical_artifacts=[
            "`data/processed/themes_codebook.json` (Canonical Qualitative Artifact)",
            "`data/processed/candidate_options.json` (Canonical Option Set)",
        ],
        relevant_adrs=["ADR-0001", "ADR-0002"],
        relevant_issue_ids=[],
        acceptance_criteria=[
            "Synthesized candidates reference valid theme_ids in grounding_theme_ids.",
            "Candidate titles and descriptions are distinct, balanced, and evidence-grounded.",
            "candidate_options.json conforms to candidate_options_v1 schema.",
        ],
        test_commands=["pytest tests/test_candidates.py -v"],
    ),
    "agent_04": AgentSpec(
        agent_id="agent_04",
        numeric_id="04",
        title="Preference Learning & Reconciler",
        mission=(
            "Construct reconciled pairwise preference matrices across all respondent pairs and candidates. "
            "Enforce mathematical anti-symmetry and self-comparison invariants."
        ),
        owned_files=["src/preference/"],
        owned_notebook="notebooks/04_preference_learning.ipynb",
        forbidden_files=["data/raw/*", "src/social_choice/", "src/reporting/"],
        input_interfaces=[
            "answers_normalized_v1 (data/normalized/answers_normalized.parquet)",
            "candidate_options_v1 (data/processed/candidate_options.json)",
        ],
        output_interfaces=["preference_matrix_v1 (data/processed/preference_matrix.parquet)"],
        upstream_artifacts=[
            "data/normalized/answers_normalized.parquet",
            "data/processed/candidate_options.json",
        ],
        downstream_dependencies=["agent_05 (Social Choice Voting)", "agent_06 (Sensitivity Analyst)"],
        canonical_artifacts=[
            "`data/processed/candidate_options.json` (Canonical Option Set)",
            "`data/processed/preference_matrix.parquet` (Canonical Utility Input)",
        ],
        relevant_adrs=["ADR-0001", "ADR-0002", "ADR-0004"],
        relevant_issue_ids=["ISSUE-002"],
        acceptance_criteria=[
            "Pairwise preference matrix satisfies anti-symmetry: pref(A, B) == -pref(B, A).",
            "Diagonal elements equal zero: pref(A, A) == 0.0.",
            "Outputs validate against preference_matrix_v1 contract.",
        ],
        test_commands=["pytest tests/test_preference.py -v"],
    ),
    "agent_05": AgentSpec(
        agent_id="agent_05",
        numeric_id="05",
        title="Utility Modeling & Social Choice Engineer",
        mission=(
            "Execute social choice aggregation rules (Borda, Condorcet, Minimax) over the reconciled "
            "preference matrix to determine consensus winners and complete collective rankings."
        ),
        owned_files=["src/social_choice/"],
        owned_notebook="notebooks/05_social_choice_voting.ipynb",
        forbidden_files=["data/raw/*", "src/preference/", "src/robustness/"],
        input_interfaces=[
            "preference_matrix_v1 (data/processed/preference_matrix.parquet)",
            "candidate_options_v1 (data/processed/candidate_options.json)",
        ],
        output_interfaces=["voting_results_v1 (data/processed/voting_results.json)"],
        upstream_artifacts=[
            "data/processed/preference_matrix.parquet",
            "data/processed/candidate_options.json",
        ],
        downstream_dependencies=["agent_06 (Sensitivity Analyst)", "agent_07 (Reporting)", "agent_08 (Audit)"],
        canonical_artifacts=[
            "`data/processed/preference_matrix.parquet` (Canonical Utility Input)",
            "`data/processed/voting_results.json` (Canonical Decision Artifact)",
        ],
        relevant_adrs=["ADR-0001", "ADR-0002", "ADR-0004"],
        relevant_issue_ids=[],
        acceptance_criteria=[
            "Borda count, Condorcet pairwise winner, and Minimax scores are computed correctly.",
            "Consensus winner is determined and unanimity status verified.",
            "Output JSON conforms to voting_results_v1 contract.",
        ],
        test_commands=["pytest tests/test_social_choice.py -v"],
    ),
    "agent_06": AgentSpec(
        agent_id="agent_06",
        numeric_id="06",
        title="Robustness & Sensitivity Analyst",
        mission=(
            "Perform bootstrap re-sampling, margin-of-victory calculations, and perturbation sensitivity "
            "to assess the stability and robustness of social choice voting results."
        ),
        owned_files=["src/robustness/"],
        owned_notebook="notebooks/06_sensitivity_analysis.ipynb",
        forbidden_files=["data/raw/*", "src/social_choice/", "src/reporting/"],
        input_interfaces=[
            "voting_results_v1 (data/processed/voting_results.json)",
            "preference_matrix_v1 (data/processed/preference_matrix.parquet)",
        ],
        output_interfaces=["sensitivity_metrics_v1 (data/processed/sensitivity_metrics.json)"],
        upstream_artifacts=[
            "data/processed/voting_results.json",
            "data/processed/preference_matrix.parquet",
        ],
        downstream_dependencies=["agent_07 (Reporting)", "agent_08 (Audit)"],
        canonical_artifacts=[
            "`data/processed/voting_results.json` (Canonical Decision Artifact)",
            "`data/processed/sensitivity_metrics.json` (Canonical Robustness Artifact)",
        ],
        relevant_adrs=["ADR-0001", "ADR-0002", "ADR-0004"],
        relevant_issue_ids=["ISSUE-003"],
        acceptance_criteria=[
            "Bootstrap confidence intervals and winner stability percentages are quantified.",
            "Perturbation tolerance margin is determined.",
            "sensitivity_metrics.json conforms to sensitivity_metrics_v1.",
        ],
        test_commands=["pytest tests/test_robustness.py -v"],
    ),
    "agent_07": AgentSpec(
        agent_id="agent_07",
        numeric_id="07",
        title="Report & Presentation Generator",
        mission=(
            "Synthesize final stakeholder policy briefs and visual decision summaries. "
            "Maintain strict presentation-only status: report is sink-only and never analytical input."
        ),
        owned_files=["src/reporting/"],
        owned_notebook="notebooks/07_reporting_presentation.ipynb",
        forbidden_files=["data/raw/*", "src/ingest/", "src/preference/", "src/social_choice/"],
        input_interfaces=[
            "voting_results_v1 (data/processed/voting_results.json)",
            "sensitivity_metrics_v1 (data/processed/sensitivity_metrics.json)",
            "themes_codebook_v1 (data/processed/themes_codebook.json)",
        ],
        output_interfaces=["policy_brief_v1 (runs/<run_id>/reports/policy_brief.md)"],
        upstream_artifacts=[
            "data/processed/voting_results.json",
            "data/processed/sensitivity_metrics.json",
            "data/processed/themes_codebook.json",
        ],
        downstream_dependencies=["Human Stakeholders / End Users"],
        canonical_artifacts=[
            "`runs/<run_id>/reports/policy_brief.md` (Presentation Only Artifact — Sink)",
        ],
        relevant_adrs=["ADR-0001", "ADR-0002"],
        relevant_issue_ids=[],
        acceptance_criteria=[
            "Policy brief accurately reflects voting results, themes, and sensitivity bounds.",
            "Report artifact is registered with authority_level='presentation_only'.",
            "Report is never consumed by any upstream or peer analytical module.",
        ],
        test_commands=["pytest tests/test_reporting.py -v"],
    ),
    "agent_08": AgentSpec(
        agent_id="agent_08",
        numeric_id="08",
        title="Red Team & Invariant Auditor",
        mission=(
            "Audit analytical outputs for invariant compliance: survey isolation, zero entity leakage, "
            "schema conformance, mathematical anti-symmetry, and absence of report feedback loops."
        ),
        owned_files=["src/validation/"],
        owned_notebook="notebooks/08_verification_redteam.ipynb",
        forbidden_files=["data/raw/*", "src/ingest/", "src/reporting/"],
        input_interfaces=["All registered stage artifacts via manifest.json"],
        output_interfaces=["audit_report_v1 (runs/<run_id>/audit_report.json)"],
        upstream_artifacts=["runs/<run_id>/manifest.json"],
        downstream_dependencies=["agent_10 (Run Card Certification)"],
        canonical_artifacts=[
            "`runs/<run_id>/manifest.json` (Authoritative Manifest)",
            "`runs/<run_id>/audit_report.json` (Audit Verification)",
        ],
        relevant_adrs=["ADR-0001", "ADR-0002", "ADR-0004"],
        relevant_issue_ids=["ISSUE-004"],
        acceptance_criteria=[
            "Cross-contamination detection runs across all qualitative and candidate artifacts.",
            "Schema conformance verified across 100% of registered outputs.",
            "Mathematical invariants (anti-symmetry, self-comparison) independently checked.",
        ],
        test_commands=["pytest tests/test_validation.py -v"],
    ),
    "agent_09": AgentSpec(
        agent_id="agent_09",
        numeric_id="09",
        title="Orchestration & Execution Engineer",
        mission=(
            "Coordinate automated DAG stage execution, manage checkpointing, and monitor "
            "pipeline run health and runtime performance."
        ),
        owned_files=["src/pipeline/"],
        owned_notebook="notebooks/09_orchestration_monitoring.ipynb",
        forbidden_files=["data/raw/*", "src/artifact_registry.py"],
        input_interfaces=["Pipeline stage definitions in docs/PIPELINE.md"],
        output_interfaces=["pipeline_execution_log (runs/<run_id>/pipeline_execution.log)"],
        upstream_artifacts=["data/raw/survey_raw.csv"],
        downstream_dependencies=["All Analytical Agents (01-08)"],
        canonical_artifacts=[
            "`docs/PIPELINE.md` (Authoritative DAG Definition)",
            "`runs/<run_id>/pipeline_execution.log` (Execution Trace)",
        ],
        relevant_adrs=["ADR-0001", "ADR-0004"],
        relevant_issue_ids=[],
        acceptance_criteria=[
            "DAG runner executes stages in strict dependency order.",
            "Automatic halting and error isolation on stage validation failure.",
            "Pipeline logs are persisted to runs/<run_id>/.",
        ],
        test_commands=["pytest tests/test_pipeline.py -v"],
    ),
    "agent_10": AgentSpec(
        agent_id="agent_10",
        numeric_id="10",
        title="Documentation, Memory & Artifact Engineer",
        mission=(
            "Create and maintain persistent shared memory, artifact provenance, context packs, "
            "freshness checks, and Architecture Decision Records to enable seamless collaboration "
            "between independent Antigravity agents without reliance on chat history."
        ),
        owned_files=[
            "src/artifact_registry.py",
            "src/context_pack.py",
            "src/freshness_checker.py",
            "AGENTS.md",
            "docs/",
            "runs/<run_id>/manifest.json",
            "runs/<run_id>/RUN_CARD.md",
        ],
        owned_notebook="notebooks/10_memory_and_registry.ipynb",
        forbidden_files=[
            "data/raw/* (immutable)",
            "src/ingest/",
            "src/nlp/",
            "src/candidates/",
            "src/preference/",
            "src/social_choice/",
            "src/robustness/",
            "src/reporting/",
            "src/validation/",
            "src/pipeline/",
        ],
        input_interfaces=["All registered artifact records and documentation"],
        output_interfaces=[
            "artifact_manifest_v1 (runs/<run_id>/manifest.json)",
            "run_card_v1 (runs/<run_id>/RUN_CARD.md)",
            "agent_context_packs (docs/AGENT_CONTEXT/agent_XX_context.md)",
        ],
        upstream_artifacts=["runs/<run_id>/manifest.json"],
        downstream_dependencies=["All Agents (Provides Context Packs & Registry Manifest)"],
        canonical_artifacts=[
            "`AGENTS.md` (Authoritative Agent Protocol)",
            "`docs/PROJECT_STATE.md` (Authoritative System State)",
            "`docs/DATA_CONTRACTS.md` (Authoritative Schemas)",
            "`runs/<run_id>/manifest.json` (Authoritative Manifest)",
            "`runs/<run_id>/RUN_CARD.md` (Authoritative Run Provenance)",
        ],
        relevant_adrs=["ADR-0001", "ADR-0002", "ADR-0003", "ADR-0004"],
        relevant_issue_ids=[],
        acceptance_criteria=[
            "Context pack generation produces complete, accurate, scoped documentation for every agent.",
            "Artifact registry enforces canonical authority rules and immutability.",
            "Freshness checker identifies stale documentation, schema drifts, and ungrounded artifacts.",
            "Acceptance test verifies an agent with zero chat history can bootstrap completely from AGENTS.md and context pack.",
        ],
        test_commands=[
            "pytest tests/test_artifact_registry.py -v",
            "pytest tests/test_context_pack.py -v",
            "pytest tests/test_freshness_checker.py -v",
            "pytest tests/test_acceptance.py -v",
        ],
    ),
}


class ContextPackGenerator:
    """Compiles scoped agent context packs from project state, ADRs, open issues, and contracts."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = (base_dir or Path.cwd()).resolve()

    def get_project_state(self) -> Dict[str, str]:
        """Extract active architecture version and run ID from docs/PROJECT_STATE.md."""
        state_file = self.base_dir / "docs" / "PROJECT_STATE.md"
        arch_version = "v1.0.0"
        active_run = "run_20261111_001"

        if state_file.is_file():
            text = state_file.read_text(encoding="utf-8")
            arch_match = re.search(r"Active Architecture Version`?:\s*`?([v\d\.]+)", text)
            if arch_match:
                arch_version = arch_match.group(1).strip()
            run_match = re.search(r"Active Run ID`?:\s*`?([a-zA-Z\d_]+)", text)
            if run_match:
                active_run = run_match.group(1).strip()

        return {"architecture_version": arch_version, "active_run": active_run}

    def get_open_issues_for_agent(self, agent_id: str) -> List[Dict[str, str]]:
        """Parse open issues affecting this agent from docs/OPEN_ISSUES.md."""
        issues_file = self.base_dir / "docs" / "OPEN_ISSUES.md"
        agent_num = agent_id.replace("agent_", "").lstrip("0")
        results = []

        if issues_file.is_file():
            text = issues_file.read_text(encoding="utf-8")
            for line in text.splitlines():
                if f"Agent {agent_num}" in line or f"agent_{agent_num}" in line or agent_id in line:
                    parts = [p.strip() for p in line.split("|") if p.strip()]
                    if len(parts) >= 6:
                        results.append({
                            "issue_id": parts[0].strip("`"),
                            "severity": parts[1].strip("`"),
                            "component": parts[3].strip("`"),
                            "description": parts[4].strip("`"),
                            "status": parts[5].strip("`"),
                        })
        return results

    def generate_markdown(self, agent_id: str) -> str:
        """Render specialized markdown for the agent's context pack."""
        # Normalize agent_id
        if agent_id.isdigit():
            agent_id = f"agent_{int(agent_id):02d}"
        agent_id = agent_id.lower()

        spec = AGENT_SPECS.get(agent_id)
        if not spec:
            raise KeyError(f"Unknown agent ID '{agent_id}'. Must be one of {list(AGENT_SPECS.keys())}")

        state = self.get_project_state()
        issues = self.get_open_issues_for_agent(agent_id)

        md = f"""# Context Pack: Agent {spec.numeric_id} — {spec.title}

> **Target Agent**: `{spec.agent_id}`
> **Architecture Version**: `{state['architecture_version']}`
> **Active Run ID**: `{state['active_run']}`
> **Generated Context**: Scoped specifically to your mission and boundaries. Do not request full project history.

---

## 1. Mission
{spec.mission}

---

## 2. File Ownership Boundaries

### Files You Own (Authorized to Create & Modify)
"""
        for f in spec.owned_files:
            md += f"- `{f}`\n"
        md += f"- `{spec.owned_notebook}`\n"

        md += "\n### Files You Must NOT Edit (Ownership Violations)\n"
        for f in spec.forbidden_files:
            md += f"- ❌ `{f}`\n"
        md += "- ❌ Any other files outside your assigned ownership scope without an approved ADR.\n"

        md += f"""
---

## 3. Required Interfaces

### Input Interfaces (Upstream Contracts)
"""
        for i in spec.input_interfaces:
            md += f"- `{i}`\n"

        md += "\n### Output Interfaces (Deliverables)\n"
        for o in spec.output_interfaces:
            md += f"- `{o}`\n"

        md += f"""
---

## 4. Dependencies & Canonical Artifacts

### Upstream Dependencies
"""
        for u in spec.upstream_artifacts:
            md += f"- `{u}`\n"

        md += "\n### Downstream Consumers\n"
        for d in spec.downstream_dependencies:
            md += f"- `{d}`\n"

        md += "\n### Authoritative Canonical Artifacts\n"
        for c in spec.canonical_artifacts:
            md += f"- {c}\n"

        md += f"""
---

## 5. Applicable Architecture Decision Records (ADRs)
"""
        for a in spec.relevant_adrs:
            md += f"- [`{a}`](file://{self.base_dir}/docs/DECISIONS/{a}*.md)\n"

        md += "\n---\n\n## 6. Active Open Issues\n"
        if issues:
            md += "| Issue ID | Severity | Component | Description | Status |\n| :--- | :--- | :--- | :--- | :--- |\n"
            for iss in issues:
                md += f"| `{iss['issue_id']}` | `{iss['severity']}` | `{iss['component']}` | {iss['description']} | `{iss['status']}` |\n"
        else:
            md += "*No open issues currently logged for this agent module.*\n"

        md += f"""
---

## 7. Acceptance Criteria & Test Execution
Before declaring your turn complete, you must satisfy:
"""
        for ac in spec.acceptance_criteria:
            md += f"- [ ] {ac}\n"

        md += "\n### Test Commands to Run\n```bash\nsource .venv/bin/activate\n"
        for tc in spec.test_commands:
            md += f"{tc}\n"
        md += "```\n"

        md += f"""
---

## 8. Mandatory Agent Handoff
Before finishing, write your formal handoff to:
`docs/AGENT_HANDOFFS/{spec.agent_id}_handoff.md`
following the template in [`docs/AGENT_HANDOFFS/template_handoff.md`](file://{self.base_dir}/docs/AGENT_HANDOFFS/template_handoff.md).
"""
        return md

    def write_context_pack(self, agent_id: str) -> Path:
        """Write context pack to docs/AGENT_CONTEXT/agent_XX_context.md."""
        if agent_id.isdigit():
            agent_id = f"agent_{int(agent_id):02d}"
        agent_id = agent_id.lower()

        out_dir = self.base_dir / "docs" / "AGENT_CONTEXT"
        out_dir.mkdir(parents=True, exist_ok=True)
        target = out_dir / f"{agent_id}_context.md"

        content = self.generate_markdown(agent_id)
        target.write_text(content, encoding="utf-8")
        return target

    def write_all_context_packs(self) -> List[Path]:
        """Generate context packs for all known agents (01 through 10)."""
        paths = []
        for aid in sorted(AGENT_SPECS.keys()):
            paths.append(self.write_context_pack(aid))
        return paths


def main():
    parser = argparse.ArgumentParser(description="HFG Scoped Context Pack Generator")
    parser.add_argument("--agent", help="Agent identifier (e.g. 10 or agent_10)")
    parser.add_argument("--all", action="store_true", help="Generate context packs for all 10 agents")
    args = parser.parse_args()

    generator = ContextPackGenerator()

    if args.all:
        paths = generator.write_all_context_packs()
        print(f"Generated {len(paths)} context packs in docs/AGENT_CONTEXT/")
    elif args.agent:
        path = generator.write_context_pack(args.agent)
        print(f"Generated context pack: {path}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
