# Open Issues & Technical Debt Tracker — HFG

> **Status**: Active (`v1.0.0`)
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
| `ISSUE-005` | `HIGH` | Agent 04 | `src/preference/` | **Open Methodological Contract**: Define and justify mapping from `CodingResult` / `PreferenceCell.alternative_probabilities` (tagged via `probability_interpretation` as epistemic coding uncertainty, mixed stance, or conditional allocation) to `ParticipantUtility` and Pareto rankings without silently treating coder uncertainty as measured cardinal utility. | `OPEN` | `run_20261111_002` |
| `ISSUE-006` | `HIGH` | Agent 07, Agent 11 | `src/runtime/`, `src/orchestration/`, `src/qa/` | **Recovery Required Prior to Colab GPU Validation**: Prior unpushed Agent 07 GPU runtime (`src/runtime/`, `notebooks/01_gpu_coders.ipynb`, `notebooks/07_gpu_runtime.ipynb`) and Agent 11 orchestration/QA (`src/orchestration/`, `src/qa/`, `notebooks/00_control_plane.ipynb`, `notebooks/04_validation.ipynb`) were unrecoverable in Git/worktrees; must be recovered or cleanly rebuilt before Colab GPU execution. | `OPEN` | `run_20261111_002` |

---

## 2. Issue Lifecycle Protocol
1. **Creation**: Any agent discovering a defect, missing dependency, or boundary ambiguity logs an issue here before handoff.
2. **Context Pack Ingestion**: `src/context_pack.py` automatically injects active open issues matching the target agent's ownership into `docs/AGENT_CONTEXT/agent_XX_context.md`.
3. **Resolution**: An agent resolving an issue updates the status to `RESOLVED`, references the git commit / PR, and records it in its handoff.
