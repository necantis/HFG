# Notebook Index — HFG

> **Owner**: Agent 10 (Governance & Inventory) | **Integration Resolution**: Agent 11 (Orchestration & QA)  
> **Active Run Discovery**: Read from [`docs/PROJECT_STATE.md`](PROJECT_STATE.md)  
> **Rule**: Do not invent missing notebooks or rename existing notebooks merely to match an earlier plan. Planned notebooks are **not** completed artifacts (`ADR-0007`).

---

## 1. Actual Tracked `.ipynb` Files (Git Inventory)

Inspection command executed against repository root:

```bash
git ls-files '*.ipynb'
```

| Repository-Relative Path | Owner | Purpose | Status | GPU Required | Prerequisites |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `notebooks/00_control_plane.ipynb` | Agents 01, 10, 11 (Orchestration: Agent 11) | Control plane: hardcoding scan, raw survey SHA-256 verification, deterministic ingestion / Gate 1 check, manifest inspection, and Agent 11 state-machine evaluation | **Production Entry Point (Tracked — Verified Runnable)** | No (CPU deterministic) | `data/raw/survey_raw.csv`, `src/ingest/ingestion.py`, `src/registry/question_registry.py`, `src/hardcoding_scanner.py`, `src/pipeline/orchestrator.py`, `src/artifact_registry.py` |
| `notebooks/01_gpu_coders.ipynb` | Agents 02, 03, 07 (Runtime: Agent 07) | **Canonical GPU Coding Entry Point**: currently executes runtime hardware preflight (`detect_hardware_profile`) and Gate 1 + Gate 2 authorization (`verify_full_survey_coding_gates`); live `coder_a` / `coder_b` corpus inference invocation pending | **Production Entry Point (Tracked — Preflight & Gate 2 Only; Full Coding Pending)** | **Yes** — Dual concurrent LLMs on NVIDIA RTX PRO 6000 Blackwell (CPU fallback config in Agent 07) | `data/normalized/answers_normalized.parquet`, `src/registry/question_registry.py`, `src/runtime/model_runtime.py`, `src/nlp/subtopic_extraction.py`, `runs/<run_id>/gpu_runtime_config.json` |
| `notebooks/01_ingest_exploration.ipynb` | Agent 01 | Exploratory CSV ingestion, epistemic-status checks, `QuestionSpec` registry & Gate 1 run | **Exploration (Tracked — Not Production Entry Point)** | No (CPU deterministic) | `data/raw/survey_raw.csv`, `src/ingest/ingestion.py`, `src/registry/question_registry.py`, `src/hardcoding_scanner.py` |
| `notebooks/02_qualitative_coding.ipynb` | Agent 02 | Exploratory qualitative subtopic discovery, free-form Stage A/B value extraction & probability repair demo | **Exploration (Tracked — Not Production Entry Point)** | Optional (CPU fixture checks verified; GPU needed for live corpus coding) | `src/contracts.py`, `src/nlp/` |
| `notebooks/04_validation.ipynb` | Agents 09, 11 (Audit: Agent 09; Orchestration: Agent 11) | End-to-end QA, Gate 1 + hardcoding checks, 9-category `FreshnessChecker`, and 13-condition Agent 03 Hard Release Gate evaluation (`READY` / `BLOCKED`) | **Production Entry Point (Tracked — Verified Runnable)** | No (CPU deterministic) | `src/hardcoding_scanner.py`, `src/freshness_checker.py`, `src/pipeline/orchestrator.py`, `runs/<run_id>/manifest.json` |
| `notebooks/07_gpu_runtime.ipynb` | Agent 07 | Dual-LLM server launch, model-family diversity validation, and 5-stage runtime benchmark (`build_and_save_runtime_config`) | **Exploration / Runtime Diagnostics (Tracked — Persisted via PR #4; Live 5-Stage Benchmark Pending Execution)** | **Yes** (GPU target; CPU fallback test mode) | `src/runtime/model_runtime.py`, `runs/<run_id>/gpu_runtime_config.json` |

> **Factual Status (Post-Agent-07 & Agent 11 Reconciliation)**: `6` `.ipynb` files are tracked under `notebooks/`: `notebooks/00_control_plane.ipynb`, `notebooks/01_gpu_coders.ipynb`, `notebooks/01_ingest_exploration.ipynb`, `notebooks/02_qualitative_coding.ipynb`, `notebooks/04_validation.ipynb`, and `notebooks/07_gpu_runtime.ipynb`. On live Google Colab (`NVIDIA RTX PRO 6000 Blackwell Server Edition`), hardware preflight, Gate 1 (`PASS`), and Gate 2 authorization (`AUTHORIZED`) succeeded; however, the 5-stage live GPU benchmark (`notebooks/07_gpu_runtime.ipynb`) and actual dual-LLM corpus inference (`coder_a` / `coder_b` via `notebooks/01_gpu_coders.ipynb`) have **not yet been executed**.

---

## 2. Planned Notebooks Referenced in Architecture Specs (Canonical Paths Under `notebooks/`)

### 2A. Canonical Colab Production Stage Entry Points (5-Stage Pipeline)

Per Agent 11 normalization, all production stage entry points are standardized exclusively under `notebooks/` with zero root-directory duplicates:

| Canonical Repository-Relative Path | Owner | Purpose | Status | GPU Required | Prerequisites |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `notebooks/00_control_plane.ipynb` | Agents 01, 10, 11 (Orchestration: Agent 11) | Control plane: hardcoding scan, raw survey SHA-256 & ingestion, `QuestionSpec` registry, `ArtifactRegistry` manifest inspection, state evaluation | **Production Entry Point (Tracked — Verified Runnable)** | No (CPU deterministic) | `src/ingest/ingestion.py`, `src/registry/question_registry.py`, `src/pipeline/orchestrator.py`, `src/artifact_registry.py`, `data/raw/survey_raw.csv` |
| `notebooks/01_gpu_coders.ipynb` | Agents 02, 03, 07 (Runtime: Agent 07) | **Canonical GPU Coding Entry Point**: hardware preflight & Gate 2 verification persisted via PR #4; full `QuestionCorpusCoder.code_question_corpus` dual-server execution cells still pending wiring and live GPU run | **Production Entry Point (Tracked — Preflight/Gates Only; Live Coding Pending)** | **Yes** — Dual concurrent LLMs on NVIDIA RTX PRO 6000 Blackwell | `data/normalized/answers_normalized.parquet`, `src/registry/question_registry.py`, `src/runtime/model_runtime.py`, `src/nlp/subtopic_extraction.py`, `runs/<run_id>/gpu_runtime_config.json` |
| `notebooks/02_math_analysis.ipynb` | Agents 04, 05, 06 | Build distributional `PreferenceMatrix`, clustering (`preference_profiles.json`), constraint-only `GovernanceSolution`, `ParticipantUtility`, `ParetoResult`, `RobustParetoResult`, social choice & conditional Baldwin/RRV | **Production Entry Point (PLANNED — Not Created)** | No (CPU vectorized; optional acceleration only if configured) | `notebooks/01_gpu_coders.ipynb` outputs (`candidate_options.json`, `CodingResult`), `src/preference/`, `src/clustering/`, `src/voting/`, `runs/<run_id>/pareto_mc_config.json` |
| `notebooks/03_report.ipynb` | Agent 08 | Assemble evidence-bound, sink-only policy brief (`ReportClaim`, `policy_brief.md`) | **Production Entry Point (PLANNED — Not Created)** | No (CPU deterministic) | `notebooks/02_math_analysis.ipynb` outputs (`PreferenceMatrix`, `preference_profiles.json`, `voting_results.json`, `ParetoResult`, `RobustParetoResult`), `themes_codebook.json`, `src/reporting/` |
| `notebooks/04_validation.ipynb` | Agents 09, 11 (Audit: Agent 09; Orchestration: Agent 11) | Gate 1 + zero-hardcoding check, 9-category `FreshnessChecker`, and 13-condition Agent 03 Hard Release Gate (`PipelineOrchestrator`) | **Production Entry Point (Tracked — Verified Runnable)** | No (CPU deterministic) | `src/freshness_checker.py`, `src/hardcoding_scanner.py`, `src/pipeline/orchestrator.py`, `runs/<run_id>/manifest.json` |

### 2B. Per-Agent Exploratory & Diagnostic Notebooks (12-Agent Scopes)

| Canonical Repository-Relative Path | Owner | Purpose | Status | GPU Required | Prerequisites |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `notebooks/00_architecture_exploration.ipynb` | Agent 00 | Architecture invariants & 20-contract exploration | **Exploration (PLANNED — Not Created)** | No | `src/contracts.py`, `schemas/interfaces.json` |
| `notebooks/01_ingest_exploration.ipynb` | Agent 01 | Multilingual (`fr`/`de`/`en`) CSV ingestion & missingness exploration | **Exploration (Tracked — Verified Runnable)** | No | `data/raw/survey_raw.csv`, `src/ingest/ingestion.py`, `src/registry/question_registry.py` |
| `notebooks/02_qualitative_coding.ipynb` | Agent 02 | Subtopic discovery & cross-question value extraction prototyping | **Exploration (Tracked — Verified Runnable)** | Optional (CPU fixture checks; Dev GPU optional) | `src/contracts.py`, `src/nlp/` |
| `notebooks/03_evidence_reconciliation.ipynb` | Agent 03 | Offset-verified evidence ledger & dual-coder reconciliation checks | **Exploration (PLANNED — Not Created)** | Optional (CPU reconciliation; GPU if re-querying coders) | `themes_codebook.json`, `src/evidence/` |
| `notebooks/04_preference_utility_pareto.ipynb` | Agent 04 | `PreferenceMatrix` simplex checks, constraint-only solutions, Pareto & MC exploration | **Exploration (PLANNED — Not Created)** | No | `candidate_options.json`, `src/preference/` |
| `notebooks/05_preference_profiles_clustering.ipynb` | Agent 05 | Missingness-masked distance & $k^*$ silhouette/stability exploration | **Exploration (PLANNED — Not Created)** | No | `preference_matrix.parquet`, `src/clustering/` |
| `notebooks/06_voting_social_choice.ipynb` | Agent 06 | Social choice rules (Borda/Condorcet/Minimax) & conditional Baldwin/RRV testing | **Exploration (PLANNED — Not Created)** | No | `preference_matrix.parquet`, `candidate_options.json`, `src/voting/` |
| `notebooks/07_gpu_runtime.ipynb` | Agent 07 | Dual-LLM server launch, VRAM fraction tuning, & 5-stage runtime benchmark | **Exploration / Diagnostics (Tracked — Persisted via PR #4)** | **Yes** (GPU target; CPU fallback test mode) | `src/runtime/model_runtime.py`, `runs/<run_id>/gpu_runtime_config.json` |
| `notebooks/08_reporting.ipynb` | Agent 08 | Evidence-bound `ReportClaim` & sink-only policy brief prototyping | **Exploration (PLANNED — Not Created)** | No | Upstream math & coding outputs, `src/reporting/` |
| `notebooks/09_integration_review.ipynb` | Agent 09 | Red-team audit, zero-hardcoding & Pareto non-exclusion inspection | **Exploration (PLANNED — Not Created)** | No | `runs/<run_id>/manifest.json`, `src/review/` |
| `notebooks/10_memory_and_registry.ipynb` | Agent 10 | Artifact registry, context packs, and freshness verification | **Exploration (PLANNED — Not Created)** | No | `src/artifact_registry.py`, `src/context_pack.py`, `src/freshness_checker.py` |
| `notebooks/11_orchestration_qa.ipynb` | Agent 11 | Exploratory DAG & QA prototyping (production gate logic lives in `src/pipeline/orchestrator.py`) | **Exploration (PLANNED — Not Created)** | No | `src/pipeline/orchestrator.py`, `src/hardcoding_scanner.py` |

---

## 3. Flagged Duplicate / Ambiguous Production Entry Points for Agent 11 to Resolve

Resolution status on `main` / `agent/11-orchestration-recovery`:

1. **Standardized Directory Path for Colab Stage Notebooks (RESOLVED by Agent 11)**:
   - All Colab production stage notebooks and diagnostics are standardized strictly under `notebooks/`:
     - `notebooks/00_control_plane.ipynb` (**Created & Verified Runnable**)
     - `notebooks/01_gpu_coders.ipynb` (**Canonical GPU Coding Entry Point — Persisted via PR #4; Live Inference Execution Pending**)
     - `notebooks/02_math_analysis.ipynb` (**Planned**)
     - `notebooks/03_report.ipynb` (**Planned**)
     - `notebooks/04_validation.ipynb` (**Created & Verified Runnable**)
     - `notebooks/07_gpu_runtime.ipynb` (**Canonical Runtime Diagnostics — Persisted via PR #4**)
   - **Invariant**: Duplicate root-level (`./01_gpu_coders.ipynb`, `./00_control_plane.ipynb`, etc.) and nested (`notebooks/colab/...`) copies are strictly prohibited.
2. **Orchestration Entry-Point Overlap (`src/orchestrator.py` vs. `notebooks/00_control_plane.ipynb` / `notebooks/04_validation.ipynb` vs. `notebooks/11_orchestration_qa.ipynb`)**:
   - **Rule Enforced**: `notebooks/01_ingest_exploration.ipynb`, `notebooks/02_qualitative_coding.ipynb`, and sibling exploratory notebooks remain strictly **exploration/diagnostic only**; production orchestration & release-gate logic resides in `src/pipeline/orchestrator.py` (with `src/orchestrator.py` compatibility shim) invoked by `notebooks/00_control_plane.ipynb` and `notebooks/04_validation.ipynb`.
3. **GPU Coder Entry-Point Overlap (`notebooks/01_gpu_coders.ipynb` vs. `notebooks/02_qualitative_coding.ipynb`, `notebooks/07_gpu_runtime.ipynb`)**:
   - **Rule Enforced**: Production dual-LLM inference executes solely through `notebooks/01_gpu_coders.ipynb` invoking `src/runtime/model_runtime.py` and `src/nlp/`. Currently `notebooks/01_gpu_coders.ipynb` executes only preflight + Gate 1/2 checks; live Coder A / Coder B GPU execution remains pending (`ISSUE-007`).
4. **Handoff & Index Update Rule**:
   - Any agent introducing an actual `.ipynb` file on a task branch must declare its exact repository-relative path under `notebooks/`, status (`production` vs. `exploration`), GPU requirement, and prerequisites in its handoff so Agent 11 / Agent 10 can verify zero duplicates during integration.
