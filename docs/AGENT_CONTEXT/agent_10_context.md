# Context Pack: Agent 10 — Documentation, Memory & Artifacts

> **Target Agent**: `agent_10`
> **Architecture Version**: `v1.1.0`
> **Active Run ID**: `run_20261111_002`
> **Generated Context**: Scoped specifically to your mission and boundaries. Do not request full project history.

---

## 1. Mission
Create and maintain persistent shared memory, artifact provenance, context packs, freshness checks, governance documentation, notebook inventory, and Architecture Decision Records to enable seamless collaboration between independent Antigravity agents without reliance on chat history.

---

## 2. File Ownership Boundaries

### Files You Own (Authorized to Create & Modify)
- `src/artifact_registry.py`
- `src/context_pack.py`
- `src/freshness_checker.py`
- `AGENTS.md`
- `docs/`
- `runs/<run_id>/manifest.json`
- `runs/<run_id>/RUN_CARD.md`
- `notebooks/10_memory_and_registry.ipynb`

### Files You Must NOT Edit (Ownership Violations)
- ❌ `data/raw/* (immutable)`
- ❌ `src/architecture/`
- ❌ `src/contracts.py`
- ❌ `schemas/interfaces.json`
- ❌ `pyproject.toml`
- ❌ `src/ingest/`
- ❌ `src/nlp/`
- ❌ `src/evidence/`
- ❌ `src/preference/`
- ❌ `src/clustering/`
- ❌ `src/voting/`
- ❌ `src/runtime/`
- ❌ `src/reporting/`
- ❌ `src/review/`
- ❌ `src/pipeline/`
- ❌ Any other files outside your assigned ownership scope without an approved ADR.

---

## 3. Required Interfaces

### Input Interfaces (Upstream Contracts)
- `All registered artifact records and documentation`

### Output Interfaces (Deliverables)
- `artifact_manifest_v1 (runs/<run_id>/manifest.json)`
- `run_card_v1 (runs/<run_id>/RUN_CARD.md)`
- `agent_context_packs (docs/AGENT_CONTEXT/agent_XX_context.md)`
- `notebook_index (docs/NOTEBOOK_INDEX.md)`

---

## 4. Dependencies & Canonical Artifacts

### Upstream Dependencies
- `runs/<run_id>/manifest.json`

### Downstream Consumers
- `All Agents (Provides Context Packs, Governance Policy & Registry Manifest)`

### Authoritative Canonical Artifacts
- `AGENTS.md` (Authoritative Agent Protocol)
- `docs/PROJECT_STATE.md` (Authoritative System State)
- `docs/DATA_CONTRACTS.md` (Authoritative Schemas)
- `docs/NOTEBOOK_INDEX.md` (Authoritative Notebook Inventory)
- `runs/<run_id>/manifest.json` (Authoritative Manifest)
- `runs/<run_id>/RUN_CARD.md` (Authoritative Run Provenance)

---

## 5. Applicable Architecture Decision Records (ADRs)
- [`ADR-0001`](file:///home/antigravity/necantis/HFG-wave-2a/docs/DECISIONS/ADR-0001*.md)
- [`ADR-0002`](file:///home/antigravity/necantis/HFG-wave-2a/docs/DECISIONS/ADR-0002*.md)
- [`ADR-0003`](file:///home/antigravity/necantis/HFG-wave-2a/docs/DECISIONS/ADR-0003*.md)
- [`ADR-0004`](file:///home/antigravity/necantis/HFG-wave-2a/docs/DECISIONS/ADR-0004*.md)
- [`ADR-0005`](file:///home/antigravity/necantis/HFG-wave-2a/docs/DECISIONS/ADR-0005*.md)
- [`ADR-0006`](file:///home/antigravity/necantis/HFG-wave-2a/docs/DECISIONS/ADR-0006*.md)
- [`ADR-0007`](file:///home/antigravity/necantis/HFG-wave-2a/docs/DECISIONS/ADR-0007*.md)

---

## 6. Active Open Issues
*No open issues currently logged for this agent module.*

---

## 7. Acceptance Criteria & Test Execution
Before declaring your turn complete, you must satisfy:
- [ ] Context pack generation produces complete, accurate, scoped documentation for all 12 agents.
- [ ] Artifact registry enforces canonical authority rules, immutability, and PreferenceCell contracts.
- [ ] Freshness checker identifies stale documentation, schema drifts, and ungrounded artifacts.
- [ ] Notebook inventory in docs/NOTEBOOK_INDEX.md tracks actual .ipynb files without inventing missing ones.
- [ ] Acceptance test verifies an agent with zero chat history can bootstrap completely from AGENTS.md and context pack.

### Test Commands to Run
```bash
source .venv/bin/activate
pytest tests/test_artifact_registry.py -v
pytest tests/test_context_pack.py -v
pytest tests/test_freshness_checker.py -v
pytest tests/test_acceptance.py -v
```

---

## 8. Mandatory Agent Handoff
Before finishing, write your formal handoff to:
`docs/AGENT_HANDOFFS/agent_10_handoff.md`
following the template in [`docs/AGENT_HANDOFFS/template_handoff.md`](file:///home/antigravity/necantis/HFG-wave-2a/docs/AGENT_HANDOFFS/template_handoff.md).

---

## 9. Git Collaboration, Shared-File Ownership & Artifact Handoff (`ADR-0007`)
- **Suggested Task Branch**: `agent/10-collaboration-policy` (if it already exists, inspect it and safely resume or create a uniquely suffixed branch; never overwrite it).
- **Isolation & Git Rules**: Work in an isolated Git worktree, clone, or remote workspace; never switch branches in a shared filesystem; never push directly to `main`; never force-push; never bypass branch protection; never commit credentials, identity mappings, raw participant data, model weights, caches, or large runtime artifacts. Commit only task-related changes, push your task branch, and record the base commit and exact pushed commit SHA in your handoff.
- **Shared-File Non-Concurrency**: Do not concurrently edit `runs/<run_id>/manifest.json`, `runs/<run_id>/RUN_CARD.md`, `AGENTS.md`, `docs/PROJECT_STATE.md`, `src/context_pack.py`, `docs/AGENT_CONTEXT/agent_XX_context.md`, `src/contracts.py`, `schemas/interfaces.json`, `docs/DATA_CONTRACTS.md`, `pyproject.toml`, or another agent's handoff (`docs/AGENT_HANDOFFS/agent_XX_handoff.md`). To request a shared-file change, include a precise change request (affected interface, proposed fields/dependency, reason, compatibility impact, required tests) in your handoff; never create a second incompatible contract.
- **Artifact & Evidence Discipline**: Produce only task-local artifact descriptors and test outputs; only the integration process (Agent 11) publishes canonical production artifact registrations after validating merged code and source hashes. A planned artifact is not a completed artifact; a CPU-only runtime test is not a validated GPU benchmark; a passing fixture test is not a completed survey analysis.
- **Notebook Inventory**: Tracked vs. planned notebooks are indexed in `docs/NOTEBOOK_INDEX.md` (do not invent missing notebooks or create duplicate production entry points).
