# Context Pack: Agent 09 — Final Integration Reviewer

> **Target Agent**: `agent_09`
> **Architecture Version**: `v1.1.0`
> **Active Run ID**: `run_20261111_002`
> **Generated Context**: Scoped specifically to your mission and boundaries. Do not request full project history.

---

## 1. Mission
Serve as the independent final integration reviewer and red team auditor. Conduct holistic invariant audits: survey isolation, probability simplex compliance, Pareto non-exclusion verification, and absence of report feedback loops. DOES NOT orchestrate pipelines.

---

## 2. File Ownership Boundaries

### Files You Own (Authorized to Create & Modify)
- `src/review/`
- `notebooks/09_integration_review.ipynb`

### Files You Must NOT Edit (Ownership Violations)
- ❌ `data/raw/*`
- ❌ `src/ingest/`
- ❌ `src/pipeline/`
- ❌ `src/artifact_registry.py`
- ❌ Any other files outside your assigned ownership scope without an approved ADR.

---

## 3. Required Interfaces

### Input Interfaces (Upstream Contracts)
- `All registered stage artifacts via manifest.json`

### Output Interfaces (Deliverables)
- `integration_review_v1 (runs/<run_id>/integration_review_report.json)`

---

## 4. Dependencies & Canonical Artifacts

### Upstream Dependencies
- `runs/<run_id>/manifest.json`

### Downstream Consumers
- `agent_10 (Run Card Certification)`
- `agent_11 (Orchestration & QA)`

### Authoritative Canonical Artifacts
- `runs/<run_id>/manifest.json` (Authoritative Manifest)
- `runs/<run_id>/integration_review_report.json` (Independent Audit Report)

---

## 5. Applicable Architecture Decision Records (ADRs)
- [`ADR-0001`](file:///home/antigravity/necantis/HFG-agent11/docs/DECISIONS/ADR-0001*.md)
- [`ADR-0002`](file:///home/antigravity/necantis/HFG-agent11/docs/DECISIONS/ADR-0002*.md)
- [`ADR-0004`](file:///home/antigravity/necantis/HFG-agent11/docs/DECISIONS/ADR-0004*.md)
- [`ADR-0005`](file:///home/antigravity/necantis/HFG-agent11/docs/DECISIONS/ADR-0005*.md)
- [`ADR-0006`](file:///home/antigravity/necantis/HFG-agent11/docs/DECISIONS/ADR-0006*.md)
- [`ADR-0007`](file:///home/antigravity/necantis/HFG-agent11/docs/DECISIONS/ADR-0007*.md)

---

## 6. Active Open Issues
*No open issues currently logged for this agent module.*

---

## 7. Acceptance Criteria & Test Execution
Before declaring your turn complete, you must satisfy:
- [ ] Independent audit confirms zero survey cross-contamination across all artifacts.
- [ ] PreferenceCell probability distributions verified to sum to 1.0 within tolerance.
- [ ] Pareto non-exclusion invariant confirmed: no candidate pruned by clustering.
- [ ] Report sink-only invariant confirmed: reports never consumed analytically.

### Test Commands to Run
```bash
source .venv/bin/activate
pytest tests/test_review.py -v
```

---

## 8. Mandatory Agent Handoff
Before finishing, write your formal handoff to:
`docs/AGENT_HANDOFFS/agent_09_handoff.md`
following the template in [`docs/AGENT_HANDOFFS/template_handoff.md`](file:///home/antigravity/necantis/HFG-agent11/docs/AGENT_HANDOFFS/template_handoff.md).

---

## 9. Git Collaboration, Shared-File Ownership & Artifact Handoff (`ADR-0007`)
- **Suggested Task Branch**: `agent/09-integration-review` (if it already exists, inspect it and safely resume or create a uniquely suffixed branch; never overwrite it).
- **Isolation & Git Rules**: Work in an isolated Git worktree, clone, or remote workspace; never switch branches in a shared filesystem; never push directly to `main`; never force-push; never bypass branch protection; never commit credentials, identity mappings, raw participant data, model weights, caches, or large runtime artifacts. Commit only task-related changes, push your task branch, and record the base commit and exact pushed commit SHA in your handoff.
- **Shared-File Non-Concurrency**: Do not concurrently edit `runs/<run_id>/manifest.json`, `runs/<run_id>/RUN_CARD.md`, `AGENTS.md`, `docs/PROJECT_STATE.md`, `src/context_pack.py`, `docs/AGENT_CONTEXT/agent_XX_context.md`, `src/contracts.py`, `schemas/interfaces.json`, `docs/DATA_CONTRACTS.md`, `pyproject.toml`, or another agent's handoff (`docs/AGENT_HANDOFFS/agent_XX_handoff.md`). To request a shared-file change, include a precise change request (affected interface, proposed fields/dependency, reason, compatibility impact, required tests) in your handoff; never create a second incompatible contract.
- **Artifact & Evidence Discipline**: Produce only task-local artifact descriptors and test outputs; only the integration process (Agent 11) publishes canonical production artifact registrations after validating merged code and source hashes. A planned artifact is not a completed artifact; a CPU-only runtime test is not a validated GPU benchmark; a passing fixture test is not a completed survey analysis.
- **Notebook Inventory**: Tracked vs. planned notebooks are indexed in `docs/NOTEBOOK_INDEX.md` (do not invent missing notebooks or create duplicate production entry points).
