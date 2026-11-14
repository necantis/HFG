# Context Pack: Agent 11 — Orchestration & QA

> **Target Agent**: `agent_11`
> **Architecture Version**: `v1.1.0`
> **Active Run ID**: `run_20261111_002`
> **Generated Context**: Scoped specifically to your mission and boundaries. Do not request full project history.

---

## 1. Mission
Sole owner of end-to-end pipeline execution, DAG scheduling, stage caching, runtime failure recovery, and automated QA regression test suites. Coordinates execution across Stages 00 through 10 and owns branch integration (inspecting task-branch diffs, resolving interface conflicts, integrating ADR-0009 shared contracts and pyproject.toml dependencies, refreshing canonical manifests and context packs, and preparing the integrated branch for main).

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
- [`ADR-0009`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0009*.md)

---

## 6. Active Open Issues
| Issue ID | Severity | Component | Description | Status |
| :--- | :--- | :--- | :--- | :--- |
| `ISSUE-006` | `HIGH` | `src/runtime/`, `src/pipeline/` | **Resolved Infrastructure Recovery**: Agent 07 GPU runtime (`src/runtime/`, `notebooks/01_gpu_coders.ipynb`, `notebooks/07_gpu_runtime.ipynb`) merged via PR #4 (`5f8c305`); Agent 11 minimal evidence-derived orchestration & validation (`src/pipeline/orchestrator.py`, `notebooks/00_control_plane.ipynb`, `notebooks/04_validation.ipynb`, `tests/test_pipeline.py`) recovered on `agent/11-orchestration-recovery`. | `RESOLVED` |
| `ISSUE-007` | `HIGH` | `src/runtime/`, `src/nlp/`, `notebooks/01_gpu_coders.ipynb` | **Resolved in PRs `#15`, `#17`, `#19`, `#22`**: Live Blackwell `production` dual coding (`136/136/0`), 5-stage benchmark (`runs/run_20261111_002/gpu_runtime_benchmark.json` SHA-256 `bc8e6d22...`, `EXECUTED_LIVE_GPU`), Wave-3B CPU `ADR-0008` Agent 03 reconciliation (`16/16` QA), and canonical registration of all `39` `FRONTIER_A` artifacts in `runs/run_20261111_002/manifest.json` + `RUN_CARD.md` completed. Sensitive runtime outputs remain gitignored outside Git on clean checkouts; under `ADR-0009`, `NEW_LLM_CODING_REQUIRED = NO`. | `RESOLVED` |
| `ISSUE-008` | `HIGH` | `src/contracts.py`, `src/preference/`, `src/pipeline/`, `src/reporting/` | **`ADR-0009` Counterfactual Resource-Regime Sensitivity (`FRONTIER_B`) & Agent 08 Reporting Hold**: Track (1) Agent 11 `ADR-0009` contract integration (`ResourceEligibilityStatus`, `GoodRegimeType`, 10-field `ClubGoodContract`, `ProvenanceCategory`, `UNRESOLVED_DUE_TO_COUNTERFACTUAL_UTILITY`, and orchestrator split `AGENT_08_TECHNICAL_RELEASE = READY` vs `AGENT_08_REPORTING_STATUS = HELD_FOR_RESOURCE_REGIME_SENSITIVITY`), (2) optional deterministic CPU `RESOURCE_ELIGIBILITY` tagging if needed (`NEW_LLM_CODING_REQUIRED = NO`), (3) isolated `FRONTIER_B` (`RESOURCE_REGIME_EXPANDED_FRONTIER`) sensitivity execution (`Q-A`–`Q-H`, `VG-01`–`VG-09`) preserving frozen `FRONTIER_A` (`543 / 326 / 10-248-285-0`) bit-for-bit, (4) isolated counterfactual manifest namespace registration, and (5) lifting `AGENT_08_REPORTING_STATUS` with mandatory dual-frontier separation (`ADR-0009` §10). Links `UNRES_GOODS_ENABLED_Q07_Q12_UNPOPULATED`. | `OPEN` |
| `ISSUE-009` | `MEDIUM` | `pyproject.toml`, `src/clustering/` | **Packaging Dependency Sync Gap (`numpy`, `scipy`, `scikit-learn`)**: `src/clustering/distances.py` (`scipy.stats.spearmanr`) and `tests/test_clustering.py` require `numpy`, `scipy`, and `scikit-learn`, which are currently omitted from `[project].dependencies` in `pyproject.toml`. In a clean `.venv` created via `pip install -e .`, `pytest tests/ -v` fails collection on `tests/test_clustering.py` (`ModuleNotFoundError: No module named 'scipy'`) until Agent 11 updates `pyproject.toml` per Agent 10's `ADR-0007` Shared-File Change Request. | `OPEN` |

---

## 7. Acceptance Criteria & Test Execution
Before declaring your turn complete, you must satisfy:
- [ ] DAG runner executes stages in strict dependency order.
- [ ] Automatic halting and error isolation on stage validation failure (including AGENT_03_RELEASE, 9-condition AGENT_04_RELEASE, and ADR-0009 AGENT_08_TECHNICAL_RELEASE vs AGENT_08_REPORTING_STATUS = HELD_FOR_RESOURCE_REGIME_SENSITIVITY split).
- [ ] Integrate ADR-0009 schemas (ResourceEligibilityStatus, GoodRegimeType, 10-field ClubGoodContract, ProvenanceCategory, UNRESOLVED_DUE_TO_COUNTERFACTUAL_UTILITY) into src/contracts.py, schemas/interfaces.json, and docs/DATA_CONTRACTS.md, reserving an isolated FRONTIER_B manifest namespace without mutating the 39 frozen FRONTIER_A registrations.
- [ ] Synchronize pyproject.toml dependencies (ISSUE-009: add numpy, scipy, scikit-learn) so pytest tests/test_clustering.py -v and pytest tests/ -v collect and pass in clean environments.
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
