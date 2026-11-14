# Open Issues & Technical Debt Tracker — HFG

> **Status**: Active (`v1.1.0`)
> **Curated by**: Agent 10 (Documentation, Memory & Artifact Engineer)
> **Rule**: Every unresolved issue affecting any agent's scope must be logged here and exposed in the agent's context pack.

---

## 1. Active Issues Table

| Issue ID | Severity | Owner | Component | Description | Status | Target |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `ISSUE-001` | `MEDIUM` | Agent 01 | `src/ingest/` | Baseline raw survey data sample needs generation in `data/raw/survey_raw.csv` conforming to `survey_raw_v1`. | `RESOLVED` | `run_20261111_002` |
| `ISSUE-002` | `LOW` | Agent 04 | `src/preference/` | Handling missing pairwise comparisons in sparse respondent graphs during matrix reconciliation. | `OPEN` | `run_20261111_002` |
| `ISSUE-003` | `LOW` | Agent 06 | `src/robustness/` | Vectorized bootstrap iteration performance optimization for large respondent pools ($N > 10,000$). | `OPEN` | `run_20261111_002` |
| `ISSUE-004` | `MEDIUM` | Agent 08 | `src/validation/` | Implement automated red-team adversarial check for lexical leakage between distinct survey groups. | `OPEN` | `run_20261111_001` |
| `ISSUE-005` | `HIGH` | Agent 04 | `src/preference/` | **Resolved by [`ADR-0008`](DECISIONS/ADR-0008-dual-coder-preference-reconciliation-and-uncertainty.md) (PRs `#12`, `#13`) and Executed in `FRONTIER_A` (`PR #18`)**: Replaces implicit cardinal-utility conflation with mandatory interpretation-aware operators (`epistemic_uncertainty_over_preference`, `explicit_mixed_preference`, `conditional_or_context_dependent`), uncertainty-set `PreferenceCell` contracts, and 4-state `RobustParetoResult` (`543` feasible packages, `326` expected-reference nondominated, `10 / 248 / 285 / 0`). `FRONTIER_A` (`OBSERVED_DESIGN_FRONTIER`) is now frozen under [`ADR-0009`](DECISIONS/ADR-0009-resource-good-regimes-and-counterfactual-institutional-design.md). | `RESOLVED` | `run_20261111_002` |
| `ISSUE-006` | `HIGH` | Agent 07, Agent 11 | `src/runtime/`, `src/pipeline/` | **Resolved Infrastructure Recovery**: Agent 07 GPU runtime (`src/runtime/`, `notebooks/01_gpu_coders.ipynb`, `notebooks/07_gpu_runtime.ipynb`) merged via PR #4 (`5f8c305`); Agent 11 minimal evidence-derived orchestration & validation (`src/pipeline/orchestrator.py`, `notebooks/00_control_plane.ipynb`, `notebooks/04_validation.ipynb`, `tests/test_pipeline.py`) recovered on `agent/11-orchestration-recovery`. | `RESOLVED` | `run_20261111_002` |
| `ISSUE-007` | `HIGH` | Agent 02, Agent 07, Agent 11 | `src/runtime/`, `src/nlp/`, `notebooks/01_gpu_coders.ipynb` | **Resolved in PRs `#15`, `#17`, `#19`, `#22`**: Live Blackwell `production` dual coding (`136/136/0`), 5-stage benchmark (`runs/run_20261111_002/gpu_runtime_benchmark.json` SHA-256 `bc8e6d22...`, `EXECUTED_LIVE_GPU`), Wave-3B CPU `ADR-0008` Agent 03 reconciliation (`16/16` QA), and canonical registration of all `39` `FRONTIER_A` artifacts in `runs/run_20261111_002/manifest.json` + `RUN_CARD.md` completed. Sensitive runtime outputs remain gitignored outside Git on clean checkouts; under `ADR-0009`, `NEW_LLM_CODING_REQUIRED = NO`. | `RESOLVED` | `run_20261111_002` |
| `ISSUE-008` | `HIGH` | Agent 04, Agent 08, Agent 11 | `src/contracts.py`, `src/preference/`, `src/pipeline/`, `src/reporting/` | **`ADR-0009` Counterfactual Resource-Regime Sensitivity (`FRONTIER_B`) & Agent 08 Reporting Hold**: Track (1) Agent 11 `ADR-0009` contract integration (`ResourceEligibilityStatus`, `GoodRegimeType`, 10-field `ClubGoodContract`, `ProvenanceCategory`, `UNRESOLVED_DUE_TO_COUNTERFACTUAL_UTILITY`, and orchestrator split `AGENT_08_TECHNICAL_RELEASE = READY` vs `AGENT_08_REPORTING_STATUS = HELD_FOR_RESOURCE_REGIME_SENSITIVITY`), (2) optional deterministic CPU `RESOURCE_ELIGIBILITY` tagging if needed (`NEW_LLM_CODING_REQUIRED = NO`), (3) isolated `FRONTIER_B` (`RESOURCE_REGIME_EXPANDED_FRONTIER`) sensitivity execution (`Q-A`–`Q-H`, `VG-01`–`VG-09`) preserving frozen `FRONTIER_A` (`543 / 326 / 10-248-285-0`) bit-for-bit, (4) isolated counterfactual manifest namespace registration, and (5) lifting `AGENT_08_REPORTING_STATUS` with mandatory dual-frontier separation (`ADR-0009` §10). Links `UNRES_GOODS_ENABLED_Q07_Q12_UNPOPULATED`. | `OPEN` | `run_20261111_002` |
| `ISSUE-009` | `MEDIUM` | Agent 11 | `pyproject.toml`, `src/clustering/` | **Packaging Dependency Sync Gap (`numpy`, `scipy`, `scikit-learn`)**: `src/clustering/distances.py` (`scipy.stats.spearmanr`) and `tests/test_clustering.py` require `numpy`, `scipy`, and `scikit-learn`, which are currently omitted from `[project].dependencies` in `pyproject.toml`. In a clean `.venv` created via `pip install -e .`, `pytest tests/ -v` fails collection on `tests/test_clustering.py` (`ModuleNotFoundError: No module named 'scipy'`) until Agent 11 updates `pyproject.toml` per Agent 10's `ADR-0007` Shared-File Change Request. | `OPEN` | `run_20261111_002` |

---

## 2. Issue Lifecycle Protocol
1. **Creation**: Any agent discovering a defect, missing dependency, or boundary ambiguity logs an issue here before handoff.
2. **Context Pack Ingestion**: `src/context_pack.py` automatically injects active open issues matching the target agent's ownership into `docs/AGENT_CONTEXT/agent_XX_context.md`.
3. **Resolution**: An agent resolving an issue updates the status to `RESOLVED`, references the git commit / PR, and records it in its handoff.
