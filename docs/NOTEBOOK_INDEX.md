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
| `notebooks/01_ingest_exploration.ipynb` | Agent 01 | Exploratory CSV ingestion, epistemic-status checks, `QuestionSpec` registry & Gate 1 run | **Exploration (Tracked — Not Production Entry Point)** | No (CPU deterministic) | `data/raw/survey_raw.csv`, `src/ingest/ingestion.py`, `src/registry/question_registry.py`, `src/hardcoding_scanner.py` |
| `notebooks/02_qualitative_coding.ipynb` | Agent 02 | Exploratory qualitative subtopic discovery, free-form Stage A/B value extraction & probability repair demo | **Exploration (Tracked — Not Production Entry Point)** | Optional (CPU fixture checks verified; GPU needed for live corpus coding) | `src/contracts.py`, `src/nlp/` |

> **Factual Status (Wave 2A Integration)**: `2` exploratory `.ipynb` files are tracked in Git under `notebooks/`. **Zero** production Colab stage notebooks (`notebooks/00_control_plane.ipynb`–`notebooks/04_validation.ipynb`) or runtime diagnostics (`notebooks/07_gpu_runtime.ipynb`) exist on disk or in Git history yet because prior unpushed Agent 07 and Agent 11 implementations were not recoverable (`RECOVERY_REQUIRED`).

---

## 2. Planned Notebooks Referenced in Architecture Specs (Canonical Paths Under `notebooks/`)

### 2A. Canonical Colab Production Stage Entry Points (5-Stage Pipeline)

Per Agent 11 Wave 2A normalization (`PART 7`), all production stage entry points are standardized exclusively under `notebooks/` with zero root-directory duplicates:

| Canonical Repository-Relative Path | Owner | Purpose | Status | GPU Required | Prerequisites |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `notebooks/00_control_plane.ipynb` | Agents 01, 10, 11 (Orchestration: Agent 11) | Control plane: hardcoding scan, raw survey ingestion, `QuestionSpec` registry, `RunManifest` initialization | **Production Entry Point (PLANNED — Prior Impl Not Recoverable)** | No (CPU deterministic) | `src/ingest/ingestion.py`, `src/registry/question_registry.py`, `src/orchestration/`, `src/artifact_registry.py`, `data/raw/survey_raw.csv` |
| `notebooks/01_gpu_coders.ipynb` | Agents 02, 03, 07 (Runtime: Agent 07) | **Canonical GPU Coding Entry Point**: launch concurrent `coder_a` / `coder_b` LLM servers, run `QuestionCorpusCoder.code_question_corpus`, extract `EvidenceSpan`, `CanonicalSubtopic`, `ValueAssignment`, reconcile `CodingResult` | **Production Entry Point (PLANNED — Prior Agent 07 Impl Not Recoverable)** | **Yes** — Dual concurrent LLMs on NVIDIA RTX PRO 6000 Blackwell (CPU fallback config in Agent 07) | `answers_normalized_v1`, `QuestionRegistry`, `src/runtime/model_runtime.py` (to recover/rebuild), `src/nlp/`, `src/evidence/`, `runs/<run_id>/gpu_runtime_config.json` |
| `notebooks/02_math_analysis.ipynb` | Agents 04, 05, 06 | Build distributional `PreferenceMatrix`, clustering (`preference_profiles.json`), constraint-only `GovernanceSolution`, `ParticipantUtility`, `ParetoResult`, `RobustParetoResult`, social choice & conditional Baldwin/RRV | **Production Entry Point (PLANNED — Not Created)** | No (CPU vectorized; optional acceleration only if configured) | `notebooks/01_gpu_coders.ipynb` outputs (`candidate_options_v1`, `CodingResult`), `src/preference/`, `src/clustering/`, `src/voting/`, `runs/<run_id>/pareto_mc_config.json` |
| `notebooks/03_report.ipynb` | Agent 08 | Assemble evidence-bound, sink-only policy brief (`ReportClaim`, `policy_brief.md`) | **Production Entry Point (PLANNED — Not Created)** | No (CPU deterministic) | `notebooks/02_math_analysis.ipynb` outputs (`PreferenceMatrix`, `preference_profiles.json`, `voting_results.json`, `ParetoResult`, `RobustParetoResult`), `themes_codebook.json`, `src/reporting/` |
| `notebooks/04_validation.ipynb` | Agents 09, 11 (Audit: Agent 09; Orchestration: Agent 11) | Independent integration audit, contract validation, zero-hardcoding gate, Pareto non-exclusion verification, freshness checks, `RUN_CARD.md` freeze trigger | **Production Entry Point (PLANNED — Prior Impl Not Recoverable)** | No (CPU deterministic) | Outputs of `00`–`03`, `src/review/`, `src/freshness_checker.py`, `src/hardcoding_scanner.py`, `src/qa/` |

### 2B. Per-Agent Exploratory & Diagnostic Notebooks (12-Agent Scopes)

| Canonical Repository-Relative Path | Owner | Purpose | Status | GPU Required | Prerequisites |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `notebooks/00_architecture_exploration.ipynb` | Agent 00 | Architecture invariants & 20-contract exploration | **Exploration (PLANNED — Not Created)** | No | `src/contracts.py`, `schemas/interfaces.json` |
| `notebooks/01_ingest_exploration.ipynb` | Agent 01 | Multilingual (`fr`/`de`/`en`) CSV ingestion & missingness exploration | **Exploration (Tracked — Verified Runnable)** | No | `data/raw/survey_raw.csv`, `src/ingest/ingestion.py`, `src/registry/question_registry.py` |
| `notebooks/02_qualitative_coding.ipynb` | Agent 02 | Subtopic discovery & cross-question value extraction prototyping | **Exploration (Tracked — Verified Runnable)** | Optional (CPU fixture checks; Dev GPU optional) | `src/contracts.py`, `src/nlp/` |
| `notebooks/03_evidence_reconciliation.ipynb` | Agent 03 | Offset-verified evidence ledger & dual-coder reconciliation checks | **Exploration (PLANNED — Not Created)** | Optional (CPU reconciliation; GPU if re-querying coders) | `themes_codebook_v1`, `src/evidence/` |
| `notebooks/04_preference_utility_pareto.ipynb` | Agent 04 | `PreferenceMatrix` simplex checks, constraint-only solutions, Pareto & MC exploration | **Exploration (PLANNED — Not Created)** | No | `candidate_options_v1`, `src/preference/` |
| `notebooks/05_preference_profiles_clustering.ipynb` | Agent 05 | Missingness-masked distance & $k^*$ silhouette/stability exploration | **Exploration (PLANNED — Not Created)** | No | `preference_matrix_v1`, `src/clustering/` |
| `notebooks/06_voting_social_choice.ipynb` | Agent 06 | Social choice rules (Borda/Condorcet/Minimax) & conditional Baldwin/RRV testing | **Exploration (PLANNED — Not Created)** | No | `preference_matrix_v1`, `candidate_options_v1`, `src/voting/` |
| `notebooks/07_gpu_runtime.ipynb` | Agent 07 | Dual-LLM server launch, VRAM fraction tuning, & CPU fallback diagnostics | **Exploration / Diagnostics (PLANNED — Prior Agent 07 Impl Not Recoverable)** | **Yes** (GPU target; CPU fallback test mode) | `src/runtime/model_runtime.py`, `runs/<run_id>/gpu_runtime_config.json` |
| `notebooks/08_reporting.ipynb` | Agent 08 | Evidence-bound `ReportClaim` & sink-only policy brief prototyping | **Exploration (PLANNED — Not Created)** | No | Upstream math & coding outputs, `src/reporting/` |
| `notebooks/09_integration_review.ipynb` | Agent 09 | Red-team audit, zero-hardcoding & Pareto non-exclusion inspection | **Exploration (PLANNED — Not Created)** | No | `runs/<run_id>/manifest.json`, `src/review/` |
| `notebooks/10_memory_and_registry.ipynb` | Agent 10 | Artifact registry, context packs, and freshness verification | **Exploration (PLANNED — Not Created)** | No | `src/artifact_registry.py`, `src/context_pack.py`, `src/freshness_checker.py` |
| `notebooks/11_orchestration_qa.ipynb` | Agent 11 | DAG execution, checkpointing, and QA harness prototyping | **Exploration (PLANNED — Not Created)** | No | `src/orchestration/`, `src/qa/`, `src/hardcoding_scanner.py` |

---

## 3. Flagged Duplicate / Ambiguous Production Entry Points for Agent 11 to Resolve

Resolution status for Wave 2A (`integration/wave-2a`):

1. **Standardized Directory Path for Colab Stage Notebooks (RESOLVED by Agent 11)**:
   - All Colab production stage notebooks and diagnostics are standardized strictly under `notebooks/`:
     - `notebooks/00_control_plane.ipynb`
     - `notebooks/01_gpu_coders.ipynb` (**Canonical GPU Coding Entry Point**)
     - `notebooks/02_math_analysis.ipynb`
     - `notebooks/03_report.ipynb`
     - `notebooks/04_validation.ipynb`
     - `notebooks/07_gpu_runtime.ipynb` (**Canonical Runtime Diagnostics**)
   - **Invariant**: Duplicate root-level (`./01_gpu_coders.ipynb`, `./00_control_plane.ipynb`, etc.) and nested (`notebooks/colab/...`) copies are strictly prohibited.
2. **Orchestration Entry-Point Overlap (`src/orchestrator.py` vs. `notebooks/00_control_plane.ipynb` / `notebooks/04_validation.ipynb` vs. `notebooks/11_orchestration_qa.ipynb`)**:
   - **Rule Enforced**: `notebooks/01_ingest_exploration.ipynb`, `notebooks/02_qualitative_coding.ipynb`, and sibling `notebooks/XX_*.ipynb` files remain strictly **exploration/diagnostic only**; production pipeline logic must reside in `src/` modules invoked by the canonical 5 stage notebooks under `notebooks/00_`–`04_`.
3. **GPU Coder Entry-Point Overlap (`notebooks/01_gpu_coders.ipynb` vs. `notebooks/02_qualitative_coding.ipynb`, `notebooks/07_gpu_runtime.ipynb`)**:
   - **Rule Enforced**: Production dual-LLM inference executes solely through `notebooks/01_gpu_coders.ipynb` invoking `src/runtime/` and `src/nlp/` (`QuestionCorpusCoder.code_question_corpus`). `notebooks/01_gpu_coders.ipynb` and `notebooks/07_gpu_runtime.ipynb` remain `NOT_RECOVERED` pending Agent 07 / Agent 11 recovery.
4. **Handoff & Index Update Rule**:
   - Any agent introducing an actual `.ipynb` file on a task branch must declare its exact repository-relative path under `notebooks/`, status (`production` vs. `exploration`), GPU requirement, and prerequisites in its handoff so Agent 11 / Agent 10 can verify zero duplicates during integration.
