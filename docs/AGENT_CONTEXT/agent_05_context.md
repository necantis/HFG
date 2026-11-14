# Context Pack: Agent 05 — Preference Profiles / Clustering

> **Target Agent**: `agent_05`
> **Architecture Version**: `v1.1.0`
> **Active Run ID**: `run_20261111_002`
> **Generated Context**: Scoped specifically to your mission and boundaries. Do not request full project history.

---

## 1. Mission
Discover empirical preference profiles, respondent clusters, and value coherence metrics to interpret institutional solutions. FRONTIER_A clustering is complete and frozen (NO_STABLE_CLUSTER_STRUCTURE, selected_k = 1, PROFILE_01) with zero changes required under ADR-0009. Enforce invariant: clusters/profiles must NOT be used to prune or exclude feasible solutions prior to Pareto analysis.

---

## 2. File Ownership Boundaries

### Files You Own (Authorized to Create & Modify)
- `src/clustering/`
- `notebooks/05_preference_profiles_clustering.ipynb`

### Files You Must NOT Edit (Ownership Violations)
- ❌ `data/raw/*`
- ❌ `src/preference/`
- ❌ `src/voting/`
- ❌ Any other files outside your assigned ownership scope without an approved ADR.

---

## 3. Required Interfaces

### Input Interfaces (Upstream Contracts)
- `preference_matrix_v1 (data/processed/preference_matrix.parquet)`

### Output Interfaces (Deliverables)
- `preference_profiles_v1 (data/processed/preference_profiles.json)`

---

## 4. Dependencies & Canonical Artifacts

### Upstream Dependencies
- `data/processed/preference_matrix.parquet`

### Downstream Consumers
- `agent_08 (Report)`
- `agent_09 (Final Integration Reviewer)`

### Authoritative Canonical Artifacts
- `data/processed/preference_matrix.parquet` (Canonical Utility Input)
- `data/processed/preference_profiles.json` (Interpretive Artifact — Non-Pruning)

---

## 5. Applicable Architecture Decision Records (ADRs)
- [`ADR-0001`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0001*.md)
- [`ADR-0002`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0002*.md)
- [`ADR-0004`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0004*.md)
- [`ADR-0005`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0005*.md)
- [`ADR-0006`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0006*.md)
- [`ADR-0007`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0007*.md)
- [`ADR-0009`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0009*.md)

---

## 6. Active Open Issues
*No open issues currently logged for this agent module.*

---

## 7. Acceptance Criteria & Test Execution
Before declaring your turn complete, you must satisfy:
- [ ] Preserve frozen FRONTIER_A clustering result (NO_STABLE_CLUSTER_STRUCTURE, selected_k = 1); zero code changes required under ADR-0009.
- [ ] Zero feasible candidate options are excluded based on cluster membership prior to Pareto analysis.
- [ ] preference_profiles.json conforms to preference_profiles_v1 schema.
- [ ] NOTE (ISSUE-009): tests/test_clustering.py requires numpy, scipy, and scikit-learn in pyproject.toml (owned by Agent 11).

### Test Commands to Run
```bash
source .venv/bin/activate
pytest tests/test_clustering.py -v
```

---

## 8. Mandatory Agent Handoff
Before finishing, write your formal handoff to:
`docs/AGENT_HANDOFFS/agent_05_handoff.md`
following the template in [`docs/AGENT_HANDOFFS/template_handoff.md`](file:///home/antigravity/necantis/HFG/docs/AGENT_HANDOFFS/template_handoff.md).

---

## 9. Git Collaboration, Shared-File Ownership & Artifact Handoff (`ADR-0007`)
- **Suggested Task Branch**: `agent/05-clustering-profiles` (if it already exists, inspect it and safely resume or create a uniquely suffixed branch; never overwrite it).
- **Isolation & Git Rules**: Work in an isolated Git worktree, clone, or remote workspace; never switch branches in a shared filesystem; never push directly to `main`; never force-push; never bypass branch protection; never commit credentials, identity mappings, raw participant data, model weights, caches, or large runtime artifacts. Commit only task-related changes, push your task branch, and record the base commit and exact pushed commit SHA in your handoff.
- **Shared-File Non-Concurrency**: Do not concurrently edit `runs/<run_id>/manifest.json`, `runs/<run_id>/RUN_CARD.md`, `AGENTS.md`, `docs/PROJECT_STATE.md`, `src/context_pack.py`, `docs/AGENT_CONTEXT/agent_XX_context.md`, `src/contracts.py`, `schemas/interfaces.json`, `docs/DATA_CONTRACTS.md`, `pyproject.toml`, or another agent's handoff (`docs/AGENT_HANDOFFS/agent_XX_handoff.md`). To request a shared-file change, include a precise change request (affected interface, proposed fields/dependency, reason, compatibility impact, required tests) in your handoff; never create a second incompatible contract.
- **Artifact & Evidence Discipline**: Produce only task-local artifact descriptors and test outputs; only the integration process (Agent 11) publishes canonical production artifact registrations after validating merged code and source hashes. A planned artifact is not a completed artifact; a CPU-only runtime test is not a validated GPU benchmark; a passing fixture test is not a completed survey analysis.
- **Notebook Inventory**: Tracked vs. planned notebooks are indexed in `docs/NOTEBOOK_INDEX.md` (do not invent missing notebooks or create duplicate production entry points).
