# Context Pack: Agent 06 — Voting

> **Target Agent**: `agent_06`
> **Architecture Version**: `v1.1.0`
> **Active Run ID**: `run_20261111_002`
> **Generated Context**: Scoped specifically to your mission and boundaries. Do not request full project history.

---

## 1. Mission
Execute social choice aggregation rules (Borda count, Condorcet pairwise winner, Minimax) over the reconciled preference matrix to determine consensus winners and collective rankings.

---

## 2. File Ownership Boundaries

### Files You Own (Authorized to Create & Modify)
- `src/voting/`
- `notebooks/06_voting_social_choice.ipynb`

### Files You Must NOT Edit (Ownership Violations)
- ❌ `data/raw/*`
- ❌ `src/preference/`
- ❌ `src/reporting/`
- ❌ Any other files outside your assigned ownership scope without an approved ADR.

---

## 3. Required Interfaces

### Input Interfaces (Upstream Contracts)
- `preference_matrix_v1 (data/processed/preference_matrix.parquet)`
- `candidate_options_v1 (data/processed/candidate_options.json)`

### Output Interfaces (Deliverables)
- `voting_results_v1 (data/processed/voting_results.json)`

---

## 4. Dependencies & Canonical Artifacts

### Upstream Dependencies
- `data/processed/preference_matrix.parquet`
- `data/processed/candidate_options.json`

### Downstream Consumers
- `agent_08 (Report)`
- `agent_09 (Final Integration Reviewer)`

### Authoritative Canonical Artifacts
- `data/processed/preference_matrix.parquet` (Canonical Utility Input)
- `data/processed/voting_results.json` (Canonical Decision Artifact)

---

## 5. Applicable Architecture Decision Records (ADRs)
- [`ADR-0001`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0001*.md)
- [`ADR-0002`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0002*.md)
- [`ADR-0004`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0004*.md)
- [`ADR-0005`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0005*.md)
- [`ADR-0006`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0006*.md)
- [`ADR-0007`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0007*.md)

---

## 6. Active Open Issues
| Issue ID | Severity | Component | Description | Status |
| :--- | :--- | :--- | :--- | :--- |
| `ISSUE-003` | `LOW` | `src/robustness/` | Vectorized bootstrap iteration performance optimization for large respondent pools ($N > 10,000$). | `OPEN` |

---

## 7. Acceptance Criteria & Test Execution
Before declaring your turn complete, you must satisfy:
- [ ] Borda count, Condorcet pairwise winner, and Minimax scores are computed correctly.
- [ ] Consensus winner is determined and unanimity status verified.
- [ ] Output JSON conforms to voting_results_v1 contract.

### Test Commands to Run
```bash
source .venv/bin/activate
pytest tests/test_voting.py -v
```

---

## 8. Mandatory Agent Handoff
Before finishing, write your formal handoff to:
`docs/AGENT_HANDOFFS/agent_06_handoff.md`
following the template in [`docs/AGENT_HANDOFFS/template_handoff.md`](file:///home/antigravity/necantis/HFG/docs/AGENT_HANDOFFS/template_handoff.md).

---

## 9. Git Collaboration, Shared-File Ownership & Artifact Handoff (`ADR-0007`)
- **Suggested Task Branch**: `agent/06-voting-social-choice` (if it already exists, inspect it and safely resume or create a uniquely suffixed branch; never overwrite it).
- **Isolation & Git Rules**: Work in an isolated Git worktree, clone, or remote workspace; never switch branches in a shared filesystem; never push directly to `main`; never force-push; never bypass branch protection; never commit credentials, identity mappings, raw participant data, model weights, caches, or large runtime artifacts. Commit only task-related changes, push your task branch, and record the base commit and exact pushed commit SHA in your handoff.
- **Shared-File Non-Concurrency**: Do not concurrently edit `runs/<run_id>/manifest.json`, `runs/<run_id>/RUN_CARD.md`, `AGENTS.md`, `docs/PROJECT_STATE.md`, `src/context_pack.py`, `docs/AGENT_CONTEXT/agent_XX_context.md`, `src/contracts.py`, `schemas/interfaces.json`, `docs/DATA_CONTRACTS.md`, `pyproject.toml`, or another agent's handoff (`docs/AGENT_HANDOFFS/agent_XX_handoff.md`). To request a shared-file change, include a precise change request (affected interface, proposed fields/dependency, reason, compatibility impact, required tests) in your handoff; never create a second incompatible contract.
- **Artifact & Evidence Discipline**: Produce only task-local artifact descriptors and test outputs; only the integration process (Agent 11) publishes canonical production artifact registrations after validating merged code and source hashes. A planned artifact is not a completed artifact; a CPU-only runtime test is not a validated GPU benchmark; a passing fixture test is not a completed survey analysis.
- **Notebook Inventory**: Tracked vs. planned notebooks are indexed in `docs/NOTEBOOK_INDEX.md` (do not invent missing notebooks or create duplicate production entry points).
