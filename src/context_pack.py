"""
Context Pack Generator for HFG Agents (12-Agent Architecture).

Compiles scoped, high-signal context packs for individual agents:
`docs/AGENT_CONTEXT/agent_XX_context.md` (Agents 00 through 11)
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
    suggested_branch: str = ""
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


# Authoritative 12-Agent Specification Catalog
AGENT_SPECS: Dict[str, AgentSpec] = {
    "agent_00": AgentSpec(
        agent_id="agent_00",
        numeric_id="00",
        title="System Architect",
        mission=(
            "Define and maintain holistic system architecture, formal analytical invariants, "
            "and cross-cutting design contracts. Ensure all 12 agents operate within verified "
            "mathematical, governance, and architectural boundaries."
        ),
        suggested_branch="agent/00-architecture",
        owned_files=["src/architecture/", "docs/ARCHITECTURE.md"],
        owned_notebook="notebooks/00_architecture_exploration.ipynb",
        forbidden_files=["data/raw/*", "src/ingest/", "src/preference/", "src/pipeline/"],
        input_interfaces=["System requirements and analytical specifications"],
        output_interfaces=["Systemic invariant specifications in docs/ARCHITECTURE.md"],
        upstream_artifacts=[],
        downstream_dependencies=["All Agents (01 through 11)"],
        canonical_artifacts=[
            "`docs/ARCHITECTURE.md` (Authoritative Architecture Specification)",
            "`docs/DATA_CONTRACTS.md` (Canonical Schemas)",
        ],
        relevant_adrs=["ADR-0001", "ADR-0002", "ADR-0003", "ADR-0004", "ADR-0005", "ADR-0006", "ADR-0007", "ADR-0008"],
        relevant_issue_ids=[],
        acceptance_criteria=[
            "All 12 agents have unambiguous, mutually exclusive module ownership.",
            "Distributional preference and Pareto non-exclusion invariants are strictly codified.",
            "Boundary enforcement rules are verified.",
        ],
        test_commands=["pytest tests/test_acceptance.py -v"],
    ),
    "agent_01": AgentSpec(
        agent_id="agent_01",
        numeric_id="01",
        title="Data & Question Registry",
        mission=(
            "Ingest external raw survey CSV inputs, enforce raw survey immutability, "
            "maintain the question registry, and normalize responses into the canonical "
            "long-format answers artifact (answers_normalized_v1)."
        ),
        suggested_branch="agent/01-ingestion-refinement",
        owned_files=["src/ingest/", "src/registry/"],
        owned_notebook="notebooks/01_ingest_exploration.ipynb",
        forbidden_files=["data/raw/* (external immutable source)", "src/nlp/", "src/preference/", "docs/DECISIONS/"],
        input_interfaces=["survey_raw_v1 (data/raw/survey_raw.csv)"],
        output_interfaces=["answers_normalized_v1 (data/normalized/answers_normalized.parquet)"],
        upstream_artifacts=["data/raw/survey_raw.csv"],
        downstream_dependencies=["agent_02 (Qualitative Coding)", "agent_04 (Preference, Utility & Pareto)"],
        canonical_artifacts=[
            "`data/raw/survey_raw.csv` (Immutable External Source)",
            "`data/normalized/answers_normalized.parquet` (Canonical Ingestion Artifact)",
        ],
        relevant_adrs=["ADR-0001", "ADR-0002", "ADR-0004", "ADR-0005", "ADR-0006", "ADR-0007"],
        relevant_issue_ids=["ISSUE-001"],
        acceptance_criteria=[
            "External raw survey data is ingested without modifying or overwriting data/raw/survey_raw.csv.",
            "Normalized answers validate against answers_normalized_v1 schema.",
            "All participant IDs and question dimensions are preserved without data loss.",
            "Task-local artifact descriptors validate schema compliance without publishing canonical production manifest entries prior to integration.",
        ],
        test_commands=["pytest tests/test_ingest.py -v"],
    ),
    "agent_02": AgentSpec(
        agent_id="agent_02",
        numeric_id="02",
        title="Qualitative Coding",
        mission=(
            "Perform rigorous qualitative coding on open-ended survey responses, "
            "synthesize thematic codebooks, and extract participant themes without lexical "
            "or entity leakage from other survey populations."
        ),
        suggested_branch="agent/02-qualitative-refinement",
        owned_files=["src/nlp/"],
        owned_notebook="notebooks/02_qualitative_coding.ipynb",
        forbidden_files=["data/raw/*", "src/ingest/", "src/evidence/", "src/preference/"],
        input_interfaces=["answers_normalized_v1 (data/normalized/answers_normalized.parquet)"],
        output_interfaces=["themes_codebook_v1 (data/processed/themes_codebook.json)"],
        upstream_artifacts=["data/normalized/answers_normalized.parquet"],
        downstream_dependencies=["agent_03 (Evidence & Reconciliation)", "agent_08 (Report)"],
        canonical_artifacts=[
            "`data/normalized/answers_normalized.parquet` (Canonical Ingestion Artifact)",
            "`data/processed/themes_codebook.json` (Canonical Qualitative Artifact)",
        ],
        relevant_adrs=["ADR-0001", "ADR-0002", "ADR-0004", "ADR-0005", "ADR-0006", "ADR-0007"],
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
        title="Evidence & Reconciliation",
        mission=(
            "Reconcile qualitative evidence and participant proposals into discrete candidate "
            "options. Ensure feasible-option pruning depends strictly on explicit logical, "
            "institutional, or dependency constraints, never on empirical clustering."
        ),
        suggested_branch="agent/03-evidence-reconciliation",
        owned_files=["src/evidence/"],
        owned_notebook="notebooks/03_evidence_reconciliation.ipynb",
        forbidden_files=["data/raw/*", "src/ingest/", "src/voting/", "src/clustering/"],
        input_interfaces=[
            "themes_codebook_v1 (data/processed/themes_codebook.json)",
            "coder_a_outputs & coder_b_outputs (data/processed/coder_a_outputs.json, data/processed/coder_b_outputs.json)",
        ],
        output_interfaces=[
            "candidate_options_v1 (data/processed/candidate_options.json)",
            "reconciled_evidence_v1 (data/processed/reconciliation/reconciled_evidence.json)",
        ],
        upstream_artifacts=["data/processed/themes_codebook.json"],
        downstream_dependencies=["agent_04 (Preference, Utility & Pareto)", "agent_06 (Voting)"],
        canonical_artifacts=[
            "`data/processed/themes_codebook.json` (Canonical Qualitative Artifact)",
            "`data/processed/candidate_options.json` (Canonical Option Set)",
            "`data/processed/reconciliation/reconciled_evidence.json` (ADR-0008 Crosswalk & Uncertainty-Set Record)",
        ],
        relevant_adrs=["ADR-0001", "ADR-0002", "ADR-0005", "ADR-0006", "ADR-0007", "ADR-0008"],
        relevant_issue_ids=[],
        acceptance_criteria=[
            "Synthesized candidates reference valid theme_ids in grounding_theme_ids.",
            "Pruning of candidate options relies ONLY on explicit logical, institutional, or dependency constraints.",
            "candidate_options.json conforms to candidate_options_v1 schema.",
            "Wave 3B CPU adaptation: emit ADR-0008 Level 2 CrosswalkStatus, deterministic per-question CanonicalAlternativeCrosswalk, and PreferenceUncertaintySet on data/processed/reconciliation/reconciled_evidence.json without silent averaging.",
        ],
        test_commands=["pytest tests/test_evidence.py -v"],
    ),
    "agent_04": AgentSpec(
        agent_id="agent_04",
        numeric_id="04",
        title="Preference, Utility & Pareto",
        mission=(
            "Construct reconciled PreferenceCell matrices representing participant preferences "
            "primarily as uncertainty sets / probability distributions over feasible alternatives (summing to 1 within "
            "numerical tolerance), following ADR-0008 and strict AGENT_04_RELEASE gate enforcement. Compute Pareto frontiers. "
            "Dynamically tune robust-Pareto Monte Carlo sample counts as a configurable runtime parameter."
        ),
        suggested_branch="agent/04-preference-pareto",
        owned_files=["src/preference/"],
        owned_notebook="notebooks/04_preference_utility_pareto.ipynb",
        forbidden_files=["data/raw/*", "src/voting/", "src/reporting/"],
        input_interfaces=[
            "answers_normalized_v1 (data/normalized/answers_normalized.parquet)",
            "candidate_options_v1 (data/processed/candidate_options.json)",
            "reconciled_evidence_v1 (data/processed/reconciliation/reconciled_evidence.json)",
            "gpu_runtime_config_v1 (runs/<run_id>/gpu_runtime_config.json)",
        ],
        output_interfaces=[
            "preference_matrix_v1 (data/processed/preference_matrix.parquet)",
            "pareto_mc_config_v1 (runs/<run_id>/pareto_mc_config.json)",
        ],
        upstream_artifacts=[
            "data/normalized/answers_normalized.parquet",
            "data/processed/candidate_options.json",
            "data/processed/reconciliation/reconciled_evidence.json",
        ],
        downstream_dependencies=["agent_05 (Preference Profiles / Clustering)", "agent_06 (Voting)"],
        canonical_artifacts=[
            "`data/processed/candidate_options.json` (Canonical Option Set)",
            "`data/processed/reconciliation/reconciled_evidence.json` (ADR-0008 Crosswalk & Uncertainty Input)",
            "`data/processed/preference_matrix.parquet` (Canonical Utility Input)",
        ],
        relevant_adrs=["ADR-0001", "ADR-0002", "ADR-0004", "ADR-0005", "ADR-0006", "ADR-0007", "ADR-0008"],
        relevant_issue_ids=["ISSUE-002", "ISSUE-005"],
        acceptance_criteria=[
            "Verify AGENT_04_RELEASE = READY (all 9 conditions in PipelineOrchestrator._evaluate_agent_04_gate pass after Wave 3B completion) before executing Agent 04 modeling.",
            "PreferenceCell alternative_probabilities and PreferenceUncertaintySet scenarios sum to 1.0 within numerical tolerance (1e-4) for usable cells; forbid CONFIDENCE_WEIGHTED_DISTRIBUTION and uses_coder_confidence_as_weight.",
            "semantic_importance, coder_confidence, coder_agreement, missingness_state, and evidence_ids are preserved separately.",
            "Evaluate ISSUE-005 interpretation-aware ParticipantUtility operators and emit 4-state RobustParetoResult without cluster/value/disagreement pruning.",
            "Robust-Pareto Monte Carlo sample counts are exposed as a configurable runtime parameter.",
            "Outputs validate against preference_matrix_v1 contract.",
        ],
        test_commands=["pytest tests/test_preference.py -v"],
    ),
    "agent_05": AgentSpec(
        agent_id="agent_05",
        numeric_id="05",
        title="Preference Profiles / Clustering",
        mission=(
            "Discover empirical preference profiles, respondent clusters, and value coherence "
            "metrics to interpret institutional solutions. Enforce invariant: clusters/profiles "
            "must NOT be used to prune or exclude feasible solutions prior to Pareto analysis."
        ),
        suggested_branch="agent/05-clustering-profiles",
        owned_files=["src/clustering/"],
        owned_notebook="notebooks/05_preference_profiles_clustering.ipynb",
        forbidden_files=["data/raw/*", "src/preference/", "src/voting/"],
        input_interfaces=["preference_matrix_v1 (data/processed/preference_matrix.parquet)"],
        output_interfaces=["preference_profiles_v1 (data/processed/preference_profiles.json)"],
        upstream_artifacts=["data/processed/preference_matrix.parquet"],
        downstream_dependencies=["agent_08 (Report)", "agent_09 (Final Integration Reviewer)"],
        canonical_artifacts=[
            "`data/processed/preference_matrix.parquet` (Canonical Utility Input)",
            "`data/processed/preference_profiles.json` (Interpretive Artifact — Non-Pruning)",
        ],
        relevant_adrs=["ADR-0001", "ADR-0002", "ADR-0004", "ADR-0005", "ADR-0006", "ADR-0007"],
        relevant_issue_ids=["ISSUE-003"],
        acceptance_criteria=[
            "Empirical preference profiles and cluster centroids are derived for interpretive purposes.",
            "Zero feasible candidate options are excluded based on cluster membership prior to Pareto analysis.",
            "preference_profiles.json conforms to preference_profiles_v1 schema.",
        ],
        test_commands=["pytest tests/test_clustering.py -v"],
    ),
    "agent_06": AgentSpec(
        agent_id="agent_06",
        numeric_id="06",
        title="Voting",
        mission=(
            "Execute social choice aggregation rules (Borda count, Condorcet pairwise winner, Minimax) "
            "over the reconciled preference matrix to determine consensus winners and collective rankings."
        ),
        suggested_branch="agent/06-voting-social-choice",
        owned_files=["src/voting/"],
        owned_notebook="notebooks/06_voting_social_choice.ipynb",
        forbidden_files=["data/raw/*", "src/preference/", "src/reporting/"],
        input_interfaces=[
            "preference_matrix_v1 (data/processed/preference_matrix.parquet)",
            "candidate_options_v1 (data/processed/candidate_options.json)",
        ],
        output_interfaces=["voting_results_v1 (data/processed/voting_results.json)"],
        upstream_artifacts=[
            "data/processed/preference_matrix.parquet",
            "data/processed/candidate_options.json",
        ],
        downstream_dependencies=["agent_08 (Report)", "agent_09 (Final Integration Reviewer)"],
        canonical_artifacts=[
            "`data/processed/preference_matrix.parquet` (Canonical Utility Input)",
            "`data/processed/voting_results.json` (Canonical Decision Artifact)",
        ],
        relevant_adrs=["ADR-0001", "ADR-0002", "ADR-0004", "ADR-0005", "ADR-0006", "ADR-0007"],
        relevant_issue_ids=[],
        acceptance_criteria=[
            "Borda count, Condorcet pairwise winner, and Minimax scores are computed correctly.",
            "Consensus winner is determined and unanimity status verified.",
            "Output JSON conforms to voting_results_v1 contract.",
        ],
        test_commands=["pytest tests/test_voting.py -v"],
    ),
    "agent_07": AgentSpec(
        agent_id="agent_07",
        numeric_id="07",
        title="GPU Runtime",
        mission=(
            "Manage hardware acceleration kernels, GPU device allocation, and memory fractions. "
            "Expose GPU memory fraction as a configurable runtime parameter, not an immutable constant."
        ),
        suggested_branch="agent/07-runtime",
        owned_files=["src/runtime/"],
        owned_notebook="notebooks/07_gpu_runtime.ipynb",
        forbidden_files=["data/raw/*", "src/ingest/", "src/reporting/"],
        input_interfaces=["Host GPU hardware environment and configuration requests"],
        output_interfaces=["gpu_runtime_config_v1 (runs/<run_id>/gpu_runtime_config.json)"],
        upstream_artifacts=[],
        downstream_dependencies=["agent_04 (Preference, Utility & Pareto)", "agent_05 (Clustering)", "agent_11 (Orchestration & QA)"],
        canonical_artifacts=[
            "`runs/<run_id>/gpu_runtime_config.json` (Configurable Runtime Parameter)",
        ],
        relevant_adrs=["ADR-0001", "ADR-0005", "ADR-0006", "ADR-0007"],
        relevant_issue_ids=[],
        acceptance_criteria=[
            "GPU memory fractions are configurable at runtime via gpu_runtime_config.json.",
            "Fallback paths to CPU execution are verified in environments lacking GPU access (CPU-only test is not reported as a validated GPU benchmark).",
            "Memory boundaries prevent out-of-memory crashes during Monte Carlo simulations.",
        ],
        test_commands=["pytest tests/test_runtime.py -v"],
    ),
    "agent_08": AgentSpec(
        agent_id="agent_08",
        numeric_id="08",
        title="Report",
        mission=(
            "Synthesize stakeholder policy briefs, visual summaries, and decision presentations. "
            "Enforce invariant: reports are strictly sink-only presentation artifacts and are never "
            "permitted to become analytical inputs to any pipeline run."
        ),
        suggested_branch="agent/08-reporting",
        owned_files=["src/reporting/"],
        owned_notebook="notebooks/08_reporting.ipynb",
        forbidden_files=["data/raw/*", "src/ingest/", "src/preference/", "src/voting/"],
        input_interfaces=[
            "voting_results_v1 (data/processed/voting_results.json)",
            "themes_codebook_v1 (data/processed/themes_codebook.json)",
            "preference_profiles_v1 (data/processed/preference_profiles.json)",
        ],
        output_interfaces=["policy_brief_v1 (runs/<run_id>/reports/policy_brief.md)"],
        upstream_artifacts=[
            "data/processed/voting_results.json",
            "data/processed/themes_codebook.json",
            "data/processed/preference_profiles.json",
        ],
        downstream_dependencies=["Human Stakeholders / End Users", "agent_09 (Final Integration Reviewer)"],
        canonical_artifacts=[
            "`runs/<run_id>/reports/policy_brief.md` (Presentation Only Artifact — Sink)",
        ],
        relevant_adrs=["ADR-0001", "ADR-0002", "ADR-0005", "ADR-0006", "ADR-0007"],
        relevant_issue_ids=[],
        acceptance_criteria=[
            "Policy brief accurately reflects voting results, themes, and preference profiles.",
            "Report artifact is registered with authority_level='presentation_only'.",
            "Report is never consumed as an analytical input by any upstream or peer module.",
        ],
        test_commands=["pytest tests/test_reporting.py -v"],
    ),
    "agent_09": AgentSpec(
        agent_id="agent_09",
        numeric_id="09",
        title="Final Integration Reviewer",
        mission=(
            "Serve as the independent final integration reviewer and red team auditor. "
            "Conduct holistic invariant audits: survey isolation, probability simplex compliance, "
            "Pareto non-exclusion verification, and absence of report feedback loops. "
            "DOES NOT orchestrate pipelines."
        ),
        suggested_branch="agent/09-integration-review",
        owned_files=["src/review/"],
        owned_notebook="notebooks/09_integration_review.ipynb",
        forbidden_files=["data/raw/*", "src/ingest/", "src/pipeline/", "src/artifact_registry.py"],
        input_interfaces=["All registered stage artifacts via manifest.json"],
        output_interfaces=["integration_review_v1 (runs/<run_id>/integration_review_report.json)"],
        upstream_artifacts=["runs/<run_id>/manifest.json"],
        downstream_dependencies=["agent_10 (Run Card Certification)", "agent_11 (Orchestration & QA)"],
        canonical_artifacts=[
            "`runs/<run_id>/manifest.json` (Authoritative Manifest)",
            "`runs/<run_id>/integration_review_report.json` (Independent Audit Report)",
        ],
        relevant_adrs=["ADR-0001", "ADR-0002", "ADR-0004", "ADR-0005", "ADR-0006", "ADR-0007", "ADR-0008"],
        relevant_issue_ids=["ISSUE-004"],
        acceptance_criteria=[
            "Independent audit confirms zero survey cross-contamination across all artifacts.",
            "PreferenceCell probability distributions and PreferenceUncertaintySet scenarios verified to sum to 1.0 within tolerance.",
            "ADR-0008 rules V1-V8 verified: zero unauthorized confidence weighting, valid crosswalks, and 4-state RobustParetoResult integrity.",
            "Pareto non-exclusion invariant confirmed: no candidate pruned by clustering, values, or coder disagreement.",
            "Report sink-only invariant confirmed: reports never consumed analytically.",
        ],
        test_commands=["pytest tests/test_review.py -v"],
    ),
    "agent_10": AgentSpec(
        agent_id="agent_10",
        numeric_id="10",
        title="Documentation, Memory & Artifacts",
        mission=(
            "Create and maintain persistent shared memory, artifact provenance, context packs, "
            "freshness checks, governance documentation, notebook inventory, and Architecture Decision Records "
            "to enable seamless collaboration between independent Antigravity agents without reliance on chat history."
        ),
        suggested_branch="agent/10-collaboration-policy",
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
            "src/architecture/",
            "src/contracts.py",
            "schemas/interfaces.json",
            "pyproject.toml",
            "src/ingest/",
            "src/nlp/",
            "src/evidence/",
            "src/preference/",
            "src/clustering/",
            "src/voting/",
            "src/runtime/",
            "src/reporting/",
            "src/review/",
            "src/pipeline/",
        ],
        input_interfaces=["All registered artifact records and documentation"],
        output_interfaces=[
            "artifact_manifest_v1 (runs/<run_id>/manifest.json)",
            "run_card_v1 (runs/<run_id>/RUN_CARD.md)",
            "agent_context_packs (docs/AGENT_CONTEXT/agent_XX_context.md)",
            "notebook_index (docs/NOTEBOOK_INDEX.md)",
        ],
        upstream_artifacts=["runs/<run_id>/manifest.json"],
        downstream_dependencies=["All Agents (Provides Context Packs, Governance Policy & Registry Manifest)"],
        canonical_artifacts=[
            "`AGENTS.md` (Authoritative Agent Protocol)",
            "`docs/PROJECT_STATE.md` (Authoritative System State)",
            "`docs/DATA_CONTRACTS.md` (Authoritative Schemas)",
            "`docs/NOTEBOOK_INDEX.md` (Authoritative Notebook Inventory)",
            "`runs/<run_id>/manifest.json` (Authoritative Manifest)",
            "`runs/<run_id>/RUN_CARD.md` (Authoritative Run Provenance)",
        ],
        relevant_adrs=["ADR-0001", "ADR-0002", "ADR-0003", "ADR-0004", "ADR-0005", "ADR-0006", "ADR-0007", "ADR-0008"],
        relevant_issue_ids=[],
        acceptance_criteria=[
            "Context pack generation produces complete, accurate, scoped documentation for all 12 agents.",
            "Artifact registry enforces canonical authority rules, immutability, and PreferenceCell contracts.",
            "Freshness checker identifies stale documentation, schema drifts, and ungrounded artifacts.",
            "Notebook inventory in docs/NOTEBOOK_INDEX.md tracks actual .ipynb files without inventing missing ones.",
            "Acceptance test verifies an agent with zero chat history can bootstrap completely from AGENTS.md and context pack.",
        ],
        test_commands=[
            "pytest tests/test_artifact_registry.py -v",
            "pytest tests/test_context_pack.py -v",
            "pytest tests/test_freshness_checker.py -v",
            "pytest tests/test_acceptance.py -v",
        ],
    ),
    "agent_11": AgentSpec(
        agent_id="agent_11",
        numeric_id="11",
        title="Orchestration & QA",
        mission=(
            "Sole owner of end-to-end pipeline execution, DAG scheduling, stage caching, "
            "runtime failure recovery, and automated QA regression test suites. "
            "Coordinates execution across Stages 00 through 10 and owns branch integration "
            "(inspecting task-branch diffs, resolving interface conflicts, running combined tests, "
            "refreshing canonical manifests and context packs, and preparing the integrated branch for main)."
        ),
        suggested_branch="integration/wave-2a",
        owned_files=["src/pipeline/"],
        owned_notebook="notebooks/11_orchestration_qa.ipynb",
        forbidden_files=["data/raw/*", "src/artifact_registry.py", "src/review/"],
        input_interfaces=["Pipeline stage definitions in docs/PIPELINE.md"],
        output_interfaces=["pipeline_qa_log_v1 (runs/<run_id>/pipeline_execution.log)"],
        upstream_artifacts=["data/raw/survey_raw.csv"],
        downstream_dependencies=["All Analytical Agents (00 through 10)"],
        canonical_artifacts=[
            "`docs/PIPELINE.md` (Authoritative DAG Definition)",
            "`docs/NOTEBOOK_INDEX.md` (Notebook Entry-Point Resolution)",
            "`runs/<run_id>/pipeline_execution.log` (Execution Trace & QA Log)",
        ],
        relevant_adrs=["ADR-0001", "ADR-0004", "ADR-0005", "ADR-0006", "ADR-0007", "ADR-0008"],
        relevant_issue_ids=[],
        acceptance_criteria=[
            "DAG runner executes stages in strict dependency order.",
            "Automatic halting and error isolation on stage validation failure (including AGENT_03_RELEASE and 9-condition AGENT_04_RELEASE gates).",
            "Automated QA test suite exercises acceptance criteria across all stages.",
            "Task-branch diffs inspected, shared-file change requests integrated, combined tests passed, and canonical manifests refreshed.",
            "Duplicate notebook production entry points flagged in docs/NOTEBOOK_INDEX.md resolved prior to Wave-2 notebook creation.",
            "Pipeline logs are persisted to runs/<run_id>/pipeline_execution.log.",
        ],
        test_commands=["pytest tests/test_pipeline.py -v"],
    ),
}


class ContextPackGenerator:
    """Compiles scoped agent context packs from project state, ADRs, open issues, and contracts."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = (base_dir or Path.cwd()).resolve()

    def get_project_state(self) -> Dict[str, str]:
        """Extract active architecture version and run ID from docs/PROJECT_STATE.md."""
        state_file = self.base_dir / "docs" / "PROJECT_STATE.md"
        arch_version = "v1.1.0"
        active_run = "run_20261111_002"

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
        agent_num = agent_id.replace("agent_", "")
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

---

## 9. Git Collaboration, Shared-File Ownership & Artifact Handoff (`ADR-0007`)
- **Suggested Task Branch**: `{spec.suggested_branch or f"agent/{spec.numeric_id}-task"}` (if it already exists, inspect it and safely resume or create a uniquely suffixed branch; never overwrite it).
- **Isolation & Git Rules**: Work in an isolated Git worktree, clone, or remote workspace; never switch branches in a shared filesystem; never push directly to `main`; never force-push; never bypass branch protection; never commit credentials, identity mappings, raw participant data, model weights, caches, or large runtime artifacts. Commit only task-related changes, push your task branch, and record the base commit and exact pushed commit SHA in your handoff.
- **Shared-File Non-Concurrency**: Do not concurrently edit `runs/<run_id>/manifest.json`, `runs/<run_id>/RUN_CARD.md`, `AGENTS.md`, `docs/PROJECT_STATE.md`, `src/context_pack.py`, `docs/AGENT_CONTEXT/agent_XX_context.md`, `src/contracts.py`, `schemas/interfaces.json`, `docs/DATA_CONTRACTS.md`, `pyproject.toml`, or another agent's handoff (`docs/AGENT_HANDOFFS/agent_XX_handoff.md`). To request a shared-file change, include a precise change request (affected interface, proposed fields/dependency, reason, compatibility impact, required tests) in your handoff; never create a second incompatible contract.
- **Artifact & Evidence Discipline**: Produce only task-local artifact descriptors and test outputs; only the integration process (Agent 11) publishes canonical production artifact registrations after validating merged code and source hashes. A planned artifact is not a completed artifact; a CPU-only runtime test is not a validated GPU benchmark; a passing fixture test is not a completed survey analysis.
- **Notebook Inventory**: Tracked vs. planned notebooks are indexed in `docs/NOTEBOOK_INDEX.md` (do not invent missing notebooks or create duplicate production entry points).
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
        """Generate context packs for all 12 agents (00 through 11)."""
        paths = []
        for aid in sorted(AGENT_SPECS.keys()):
            paths.append(self.write_context_pack(aid))
        return paths


def main():
    parser = argparse.ArgumentParser(description="HFG Scoped Context Pack Generator (12 Agents)")
    parser.add_argument("--agent", help="Agent identifier (e.g. 00 or agent_00)")
    parser.add_argument("--all", action="store_true", help="Generate context packs for all 12 agents")
    args = parser.parse_args()

    generator = ContextPackGenerator()

    if args.all:
        paths = generator.write_all_context_packs()
        print(f"Generated {len(paths)} context packs in docs/AGENT_CONTEXT/ (agent_00 through agent_11)")
    elif args.agent:
        path = generator.write_context_pack(args.agent)
        print(f"Generated context pack: {path}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
