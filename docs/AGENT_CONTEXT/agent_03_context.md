# Context Pack: Agent 03 — Evidence & Reconciliation

> **Target Agent**: `agent_03`
> **Architecture Version**: `v1.1.0`
> **Active Run ID**: `run_20261111_002`
> **Generated Context**: Scoped specifically to your mission and boundaries. Do not request full project history.

---

## 1. Mission
Reconcile qualitative evidence and participant proposals into discrete candidate options. Ensure feasible-option pruning depends strictly on explicit logical, institutional, or dependency constraints, never on empirical clustering. Wave 3B ADR-0008 reconciliation is complete; under ADR-0009, NEW_LLM_CODING_REQUIRED = NO and only optional deterministic CPU subtopic RESOURCE_ELIGIBILITY tagging applies if needed by Agent 04.

---

## 2. File Ownership Boundaries

### Files You Own (Authorized to Create & Modify)
- `src/evidence/`
- `notebooks/03_evidence_reconciliation.ipynb`

### Files You Must NOT Edit (Ownership Violations)
- ❌ `data/raw/*`
- ❌ `src/ingest/`
- ❌ `src/voting/`
- ❌ `src/clustering/`
- ❌ Any other files outside your assigned ownership scope without an approved ADR.

---

## 3. Required Interfaces

### Input Interfaces (Upstream Contracts)
- `themes_codebook_v1 (data/processed/themes_codebook.json)`
- `coder_a_outputs & coder_b_outputs (data/processed/coder_a_outputs.json, data/processed/coder_b_outputs.json)`

### Output Interfaces (Deliverables)
- `candidate_options_v1 (data/processed/candidate_options.json)`
- `reconciled_evidence_v1 (data/processed/reconciliation/reconciled_evidence.json)`

---

## 4. Dependencies & Canonical Artifacts

### Upstream Dependencies
- `data/processed/themes_codebook.json`

### Downstream Consumers
- `agent_04 (Preference, Utility & Pareto)`
- `agent_06 (Voting)`

### Authoritative Canonical Artifacts
- `data/processed/themes_codebook.json` (Canonical Qualitative Artifact)
- `data/processed/candidate_options.json` (Canonical Option Set)
- `data/processed/reconciliation/reconciled_evidence.json` (ADR-0008 Crosswalk & Uncertainty-Set Record)

---

## 5. Applicable Architecture Decision Records (ADRs)
- [`ADR-0001`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0001*.md)
- [`ADR-0002`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0002*.md)
- [`ADR-0005`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0005*.md)
- [`ADR-0006`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0006*.md)
- [`ADR-0007`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0007*.md)
- [`ADR-0008`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0008*.md)
- [`ADR-0009`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0009*.md)

---

## 6. Active Open Issues
| Issue ID | Severity | Component | Description | Status |
| :--- | :--- | :--- | :--- | :--- |
| `ISSUE-007` | `HIGH` | `src/runtime/`, `src/nlp/`, `notebooks/01_gpu_coders.ipynb` | **Resolved in PRs `#15`, `#17`, `#19`, `#22`**: Live Blackwell `production` dual coding (`136/136/0`), 5-stage benchmark (`runs/run_20261111_002/gpu_runtime_benchmark.json` SHA-256 `bc8e6d22...`, `EXECUTED_LIVE_GPU`), Wave-3B CPU `ADR-0008` Agent 03 reconciliation (`16/16` QA), and canonical registration of all `39` `FRONTIER_A` artifacts in `runs/run_20261111_002/manifest.json` + `RUN_CARD.md` completed. Sensitive runtime outputs remain gitignored outside Git on clean checkouts; under `ADR-0009`, `NEW_LLM_CODING_REQUIRED = NO`. | `RESOLVED` |

---

## 7. Acceptance Criteria & Test Execution
Before declaring your turn complete, you must satisfy:
- [ ] Synthesized candidates reference valid theme_ids in grounding_theme_ids.
- [ ] Pruning of candidate options relies ONLY on explicit logical, institutional, or dependency constraints.
- [ ] candidate_options.json conforms to candidate_options_v1 schema.
- [ ] Wave 3B CPU adaptation: emit ADR-0008 Level 2 CrosswalkStatus, deterministic per-question CanonicalAlternativeCrosswalk, and PreferenceUncertaintySet on data/processed/reconciliation/reconciled_evidence.json without silent averaging.
- [ ] ADR-0009 constraint: NEW_LLM_CODING_REQUIRED = NO; any additive RESOURCE_ELIGIBILITY tagging (Q10, Q11 pools, Q12 pools, risk-caveated Q09, Q06 financial facets, Q08 CONDITIONAL_RESOURCE_ONLY; never Q07 or perception/authority facets) must be deterministic CPU-only and leave frozen FRONTIER_A artifacts immutable.

### Test Commands to Run
```bash
source .venv/bin/activate
pytest tests/test_evidence.py -v
```

---

## 8. Mandatory Agent Handoff
Before finishing, write your formal handoff to:
`docs/AGENT_HANDOFFS/agent_03_handoff.md`
following the template in [`docs/AGENT_HANDOFFS/template_handoff.md`](file:///home/antigravity/necantis/HFG/docs/AGENT_HANDOFFS/template_handoff.md).

---

## 9. Git Collaboration, Shared-File Ownership & Artifact Handoff (`ADR-0007`)
- **Suggested Task Branch**: `agent/03-evidence-reconciliation` (if it already exists, inspect it and safely resume or create a uniquely suffixed branch; never overwrite it).
- **Isolation & Git Rules**: Work in an isolated Git worktree, clone, or remote workspace; never switch branches in a shared filesystem; never push directly to `main`; never force-push; never bypass branch protection; never commit credentials, identity mappings, raw participant data, model weights, caches, or large runtime artifacts. Commit only task-related changes, push your task branch, and record the base commit and exact pushed commit SHA in your handoff.
- **Shared-File Non-Concurrency**: Do not concurrently edit `runs/<run_id>/manifest.json`, `runs/<run_id>/RUN_CARD.md`, `AGENTS.md`, `docs/PROJECT_STATE.md`, `src/context_pack.py`, `docs/AGENT_CONTEXT/agent_XX_context.md`, `src/contracts.py`, `schemas/interfaces.json`, `docs/DATA_CONTRACTS.md`, `pyproject.toml`, or another agent's handoff (`docs/AGENT_HANDOFFS/agent_XX_handoff.md`). To request a shared-file change, include a precise change request (affected interface, proposed fields/dependency, reason, compatibility impact, required tests) in your handoff; never create a second incompatible contract.
- **Artifact & Evidence Discipline**: Produce only task-local artifact descriptors and test outputs; only the integration process (Agent 11) publishes canonical production artifact registrations after validating merged code and source hashes. A planned artifact is not a completed artifact; a CPU-only runtime test is not a validated GPU benchmark; a passing fixture test is not a completed survey analysis.
- **Notebook Inventory**: Tracked vs. planned notebooks are indexed in `docs/NOTEBOOK_INDEX.md` (do not invent missing notebooks or create duplicate production entry points).
