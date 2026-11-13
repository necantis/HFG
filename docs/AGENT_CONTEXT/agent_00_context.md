# Context Pack: Agent 00 — System Architect

> **Target Agent**: `agent_00`
> **Architecture Version**: `v1.1.0`
> **Active Run ID**: `run_20261111_002`
> **Generated Context**: Scoped specifically to your mission and boundaries. Do not request full project history.

---

## 1. Mission
Define and maintain holistic system architecture, formal analytical invariants, and cross-cutting design contracts. Ensure all 12 agents operate within verified mathematical, governance, and architectural boundaries.

---

## 2. File Ownership Boundaries

### Files You Own (Authorized to Create & Modify)
- `src/architecture/`
- `docs/ARCHITECTURE.md`
- `notebooks/00_architecture_exploration.ipynb`

### Files You Must NOT Edit (Ownership Violations)
- ❌ `data/raw/*`
- ❌ `src/ingest/`
- ❌ `src/preference/`
- ❌ `src/pipeline/`
- ❌ Any other files outside your assigned ownership scope without an approved ADR.

---

## 3. Required Interfaces

### Input Interfaces (Upstream Contracts)
- `System requirements and analytical specifications`

### Output Interfaces (Deliverables)
- `Systemic invariant specifications in docs/ARCHITECTURE.md`

---

## 4. Dependencies & Canonical Artifacts

### Upstream Dependencies

### Downstream Consumers
- `All Agents (01 through 11)`

### Authoritative Canonical Artifacts
- `docs/ARCHITECTURE.md` (Authoritative Architecture Specification)
- `docs/DATA_CONTRACTS.md` (Canonical Schemas)

---

## 5. Applicable Architecture Decision Records (ADRs)
- [`ADR-0001`](file:///home/antigravity/necantis/HFG-agent11/docs/DECISIONS/ADR-0001*.md)
- [`ADR-0002`](file:///home/antigravity/necantis/HFG-agent11/docs/DECISIONS/ADR-0002*.md)
- [`ADR-0003`](file:///home/antigravity/necantis/HFG-agent11/docs/DECISIONS/ADR-0003*.md)
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
- [ ] All 12 agents have unambiguous, mutually exclusive module ownership.
- [ ] Distributional preference and Pareto non-exclusion invariants are strictly codified.
- [ ] Boundary enforcement rules are verified.

### Test Commands to Run
```bash
source .venv/bin/activate
pytest tests/test_acceptance.py -v
```

---

## 8. Mandatory Agent Handoff
Before finishing, write your formal handoff to:
`docs/AGENT_HANDOFFS/agent_00_handoff.md`
following the template in [`docs/AGENT_HANDOFFS/template_handoff.md`](file:///home/antigravity/necantis/HFG-agent11/docs/AGENT_HANDOFFS/template_handoff.md).

---

## 9. Git Collaboration, Shared-File Ownership & Artifact Handoff (`ADR-0007`)
- **Suggested Task Branch**: `agent/00-architecture` (if it already exists, inspect it and safely resume or create a uniquely suffixed branch; never overwrite it).
- **Isolation & Git Rules**: Work in an isolated Git worktree, clone, or remote workspace; never switch branches in a shared filesystem; never push directly to `main`; never force-push; never bypass branch protection; never commit credentials, identity mappings, raw participant data, model weights, caches, or large runtime artifacts. Commit only task-related changes, push your task branch, and record the base commit and exact pushed commit SHA in your handoff.
- **Shared-File Non-Concurrency**: Do not concurrently edit `runs/<run_id>/manifest.json`, `runs/<run_id>/RUN_CARD.md`, `AGENTS.md`, `docs/PROJECT_STATE.md`, `src/context_pack.py`, `docs/AGENT_CONTEXT/agent_XX_context.md`, `src/contracts.py`, `schemas/interfaces.json`, `docs/DATA_CONTRACTS.md`, `pyproject.toml`, or another agent's handoff (`docs/AGENT_HANDOFFS/agent_XX_handoff.md`). To request a shared-file change, include a precise change request (affected interface, proposed fields/dependency, reason, compatibility impact, required tests) in your handoff; never create a second incompatible contract.
- **Artifact & Evidence Discipline**: Produce only task-local artifact descriptors and test outputs; only the integration process (Agent 11) publishes canonical production artifact registrations after validating merged code and source hashes. A planned artifact is not a completed artifact; a CPU-only runtime test is not a validated GPU benchmark; a passing fixture test is not a completed survey analysis.
- **Notebook Inventory**: Tracked vs. planned notebooks are indexed in `docs/NOTEBOOK_INDEX.md` (do not invent missing notebooks or create duplicate production entry points).
