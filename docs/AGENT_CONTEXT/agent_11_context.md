# Context Pack: Agent 11 — Orchestration & QA

> **Target Agent**: `agent_11`
> **Architecture Version**: `v1.1.0`
> **Active Run ID**: `run_20261111_002`
> **Generated Context**: Scoped specifically to your mission and boundaries. Do not request full project history.

---

## 1. Mission
Sole owner of end-to-end pipeline execution, DAG scheduling, stage caching, runtime failure recovery, and automated QA regression test suites. Coordinates execution across Stages 00 through 10 and owns branch integration (inspecting task-branch diffs, resolving interface conflicts, running combined tests, refreshing canonical manifests and context packs, and preparing the integrated branch for main).

---

## 2. File Ownership Boundaries

### Files You Own (Authorized to Create & Modify)
- `src/pipeline/`
- `notebooks/11_orchestration_qa.ipynb`

### Files You Must NOT Edit (Ownership Violations)
- ❌ `data/raw/*`
- ❌ `src/artifact_registry.py`
- ❌ `src/review/`
- ❌ Any other files outside your assigned ownership scope without an approved ADR.

---

## 3. Required Interfaces

### Input Interfaces (Upstream Contracts)
- `Pipeline stage definitions in docs/PIPELINE.md`

### Output Interfaces (Deliverables)
- `pipeline_qa_log_v1 (runs/<run_id>/pipeline_execution.log)`

---

## 4. Dependencies & Canonical Artifacts

### Upstream Dependencies
- `data/raw/survey_raw.csv`

### Downstream Consumers
- `All Analytical Agents (00 through 10)`

### Authoritative Canonical Artifacts
- `docs/PIPELINE.md` (Authoritative DAG Definition)
- `docs/NOTEBOOK_INDEX.md` (Notebook Entry-Point Resolution)
- `runs/<run_id>/pipeline_execution.log` (Execution Trace & QA Log)

---

## 5. Applicable Architecture Decision Records (ADRs)
- [`ADR-0001`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0001*.md)
- [`ADR-0004`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0004*.md)
- [`ADR-0005`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0005*.md)
- [`ADR-0006`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0006*.md)
- [`ADR-0007`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0007*.md)
- [`ADR-0008`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0008*.md)

---

## 6. Active Open Issues
| Issue ID | Severity | Component | Description | Status |
| :--- | :--- | :--- | :--- | :--- |
| `ISSUE-006` | `HIGH` | `src/runtime/`, `src/pipeline/` | **Resolved Infrastructure Recovery**: Agent 07 GPU runtime (`src/runtime/`, `notebooks/01_gpu_coders.ipynb`, `notebooks/07_gpu_runtime.ipynb`) merged via PR #4 (`5f8c305`); Agent 11 minimal evidence-derived orchestration & validation (`src/pipeline/orchestrator.py`, `notebooks/00_control_plane.ipynb`, `notebooks/04_validation.ipynb`, `tests/test_pipeline.py`) recovered on `agent/11-orchestration-recovery`. | `RESOLVED` |
| `ISSUE-007` | `HIGH` | `src/runtime/`, `src/nlp/`, `notebooks/01_gpu_coders.ipynb` | **Production Dual Coding Executed on Blackwell Runtime; Canonical Benchmark Sync & Wave-3B Manifest Registration Pending**: Live `production` Coder A (`Valdemardi/DeepSeek-R1-Distill-Qwen-32B-AWQ`) + independent Coder B (`RedHatAI/Mistral-Small-3.1-24B-Instruct-2503-quantized.w4a16`) inference (`136/136/0`, `18` non-preference cells preserved) and initial Agent 03 reconciliation (`PR #11`) completed against staged release-bundle outputs, while `runs/run_20261111_002/gpu_runtime_benchmark.json` sync, Agent 03 Wave-3B CPU `ADR-0008` schema adaptation, and canonical `manifest.json` registration remain pending (`AGENT_04_RELEASE = BLOCKED`; clean Git checkouts lack gitignored runtime coder artifacts). | `OPEN` |

---

## 7. Acceptance Criteria & Test Execution
Before declaring your turn complete, you must satisfy:
- [ ] DAG runner executes stages in strict dependency order.
- [ ] Automatic halting and error isolation on stage validation failure (including AGENT_03_RELEASE and 9-condition AGENT_04_RELEASE gates).
- [ ] Automated QA test suite exercises acceptance criteria across all stages.
- [ ] Task-branch diffs inspected, shared-file change requests integrated, combined tests passed, and canonical manifests refreshed.
- [ ] Duplicate notebook production entry points flagged in docs/NOTEBOOK_INDEX.md resolved prior to Wave-2 notebook creation.
- [ ] Pipeline logs are persisted to runs/<run_id>/pipeline_execution.log.

### Test Commands to Run
```bash
source .venv/bin/activate
pytest tests/test_pipeline.py -v
```

---

## 8. Mandatory Agent Handoff
Before finishing, write your formal handoff to:
`docs/AGENT_HANDOFFS/agent_11_handoff.md`
following the template in [`docs/AGENT_HANDOFFS/template_handoff.md`](file:///home/antigravity/necantis/HFG/docs/AGENT_HANDOFFS/template_handoff.md).

---

## 9. Git Collaboration, Shared-File Ownership & Artifact Handoff (`ADR-0007`)
- **Suggested Task Branch**: `integration/wave-2a` (if it already exists, inspect it and safely resume or create a uniquely suffixed branch; never overwrite it).
- **Isolation & Git Rules**: Work in an isolated Git worktree, clone, or remote workspace; never switch branches in a shared filesystem; never push directly to `main`; never force-push; never bypass branch protection; never commit credentials, identity mappings, raw participant data, model weights, caches, or large runtime artifacts. Commit only task-related changes, push your task branch, and record the base commit and exact pushed commit SHA in your handoff.
- **Shared-File Non-Concurrency**: Do not concurrently edit `runs/<run_id>/manifest.json`, `runs/<run_id>/RUN_CARD.md`, `AGENTS.md`, `docs/PROJECT_STATE.md`, `src/context_pack.py`, `docs/AGENT_CONTEXT/agent_XX_context.md`, `src/contracts.py`, `schemas/interfaces.json`, `docs/DATA_CONTRACTS.md`, `pyproject.toml`, or another agent's handoff (`docs/AGENT_HANDOFFS/agent_XX_handoff.md`). To request a shared-file change, include a precise change request (affected interface, proposed fields/dependency, reason, compatibility impact, required tests) in your handoff; never create a second incompatible contract.
- **Artifact & Evidence Discipline**: Produce only task-local artifact descriptors and test outputs; only the integration process (Agent 11) publishes canonical production artifact registrations after validating merged code and source hashes. A planned artifact is not a completed artifact; a CPU-only runtime test is not a validated GPU benchmark; a passing fixture test is not a completed survey analysis.
- **Notebook Inventory**: Tracked vs. planned notebooks are indexed in `docs/NOTEBOOK_INDEX.md` (do not invent missing notebooks or create duplicate production entry points).
