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

| Repository-Relative Path | Owner | Purpose | Production / Exploration Status | GPU Required | Prerequisites |
| :--- | :--- | :--- | :--- | :--- | :--- |
| *(None — `0` tracked `.ipynb` files currently exist in Git)* | — | — | — | — | — |

> **Factual Status**: As of base commit `af595e2`, **zero** `.ipynb` files are committed or tracked in the repository. All notebook execution paths remain **planned** until implemented, tested, and integrated onto `main` via Agent 11.

---

## 2. Planned Notebooks Referenced in Architecture Specs (Not Yet Created)

The architectural specifications ([`AGENTS.md`](../AGENTS.md), [`docs/ARCHITECTURE.md`](ARCHITECTURE.md), [`docs/PIPELINE.md`](PIPELINE.md), [`docs/IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md), and [`src/context_pack.py`](../src/context_pack.py)) reference two distinct sets of planned notebooks. Neither set exists on disk yet.

### 2A. Planned Colab Production Stage Entry Points (5-Stage Pipeline)

| Referenced Path (Unresolved Prefix — See Section 3) | Owner | Purpose | Status | GPU Required | Prerequisites |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `00_control_plane.ipynb` | Agents 01, 10, 11 (Orchestration: Agent 11) | Control plane: hardcoding scan, raw survey ingestion, `QuestionSpec` registry, `RunManifest` initialization | **Production Entry Point (PLANNED — Not Created)** | No (CPU deterministic) | `src/hardcoding_scanner.py`, `src/ingestion.py`, `src/question_registry.py`, `src/orchestrator.py`, `src/artifact_registry.py`, `data/raw/survey_raw.csv` |
| `01_gpu_coders.ipynb` | Agents 02, 03, 07 (Runtime: Agent 07) | Launch concurrent `coder_a` / `coder_b` LLM servers, extract `EvidenceSpan`, `CanonicalSubtopic`, `ValueAssignment`, reconcile `CodingResult` | **Production Entry Point (PLANNED — Not Created)** | **Yes** — Dual concurrent LLMs on NVIDIA RTX PRO 6000 Blackwell (CPU fallback config in Agent 07) | `00_control_plane.ipynb` outputs (`answers_normalized_v1`, `QuestionSpec`), `src/model_runtime.py`, `src/subtopic_extraction.py`, `src/value_extraction.py`, `src/evidence_ledger.py`, `src/reconciliation.py`, `runs/<run_id>/gpu_runtime_config.json` |
| `02_math_analysis.ipynb` | Agents 04, 05, 06 | Build distributional `PreferenceMatrix`, clustering (`preference_profiles.json`), constraint-only `GovernanceSolution`, `ParticipantUtility`, `ParetoResult`, `RobustParetoResult`, social choice & conditional Baldwin/RRV | **Production Entry Point (PLANNED — Not Created)** | No (CPU vectorized; optional acceleration only if configured) | `01_gpu_coders.ipynb` outputs (`candidate_options_v1`, `CodingResult`), `src/preference_matrix.py`, `src/clustering.py`, `src/solution_space.py`, `src/utilities.py`, `src/pareto.py`, `src/robust_pareto.py`, `src/voting_baldwin.py`, `src/voting_rrv.py`, `runs/<run_id>/pareto_mc_config.json` |
| `03_report.ipynb` | Agent 08 | Assemble evidence-bound, sink-only policy brief (`ReportClaim`, `policy_brief.md`) | **Production Entry Point (PLANNED — Not Created)** | No (CPU deterministic) | `02_math_analysis.ipynb` outputs (`PreferenceMatrix`, `preference_profiles.json`, `voting_results.json`, `ParetoResult`, `RobustParetoResult`), `themes_codebook.json`, `src/report_generator.py` |
| `04_validation.ipynb` | Agents 09, 11 (Audit: Agent 09; Orchestration: Agent 11) | Independent integration audit, contract validation, zero-hardcoding gate, Pareto non-exclusion verification, freshness checks, `RUN_CARD.md` freeze trigger | **Production Entry Point (PLANNED — Not Created)** | No (CPU deterministic) | Outputs of `00`–`03`, `src/review/`, `src/freshness_checker.py`, `src/hardcoding_scanner.py` |

### 2B. Planned Per-Agent Exploratory Notebooks (12-Agent Scopes)

| Planned Repository-Relative Path | Owner | Purpose | Status | GPU Required | Prerequisites |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `notebooks/00_architecture_exploration.ipynb` | Agent 00 | Architecture invariants & 20-contract exploration | **Exploration (PLANNED — Not Created)** | No | `src/contracts.py`, `schemas/interfaces.json` |
| `notebooks/01_ingest_exploration.ipynb` | Agent 01 | Multilingual (`fr`/`de`/`en`) CSV ingestion & missingness exploration | **Exploration (PLANNED — Not Created)** | No | `data/raw/survey_raw.csv`, `src/ingestion.py`, `src/question_registry.py` |
| `notebooks/02_qualitative_coding.ipynb` | Agent 02 | Subtopic discovery & cross-question value extraction prototyping | **Exploration (PLANNED — Not Created)** | Yes (Optional / Dev LLM endpoint) | `answers_normalized_v1`, `src/subtopic_extraction.py`, `src/value_extraction.py` |
| `notebooks/03_evidence_reconciliation.ipynb` | Agent 03 | Offset-verified evidence ledger & dual-coder reconciliation checks | **Exploration (PLANNED — Not Created)** | Optional (CPU reconciliation; GPU if re-querying coders) | `themes_codebook_v1`, `src/evidence_ledger.py`, `src/reconciliation.py` |
| `notebooks/04_preference_utility_pareto.ipynb` | Agent 04 | `PreferenceMatrix` simplex checks, constraint-only solutions, Pareto & MC exploration | **Exploration (PLANNED — Not Created)** | No | `candidate_options_v1`, `src/preference_matrix.py`, `src/solution_space.py`, `src/utilities.py`, `src/pareto.py`, `src/robust_pareto.py` |
| `notebooks/05_preference_profiles_clustering.ipynb` | Agent 05 | Missingness-masked distance & $k^*$ silhouette/stability exploration | **Exploration (PLANNED — Not Created)** | No | `preference_matrix_v1`, `src/clustering.py` |
| `notebooks/06_voting_social_choice.ipynb` | Agent 06 | Social choice rules (Borda/Condorcet/Minimax) & conditional Baldwin/RRV testing | **Exploration (PLANNED — Not Created)** | No | `preference_matrix_v1`, `candidate_options_v1`, `src/voting_baldwin.py`, `src/voting_rrv.py` |
| `notebooks/07_gpu_runtime.ipynb` | Agent 07 | Dual-LLM server launch, VRAM fraction tuning, & CPU fallback verification | **Exploration (PLANNED — Not Created)** | **Yes** (GPU target; CPU fallback test mode) | `src/model_runtime.py`, `runs/<run_id>/gpu_runtime_config.json` |
| `notebooks/08_reporting.ipynb` | Agent 08 | Evidence-bound `ReportClaim` & sink-only policy brief prototyping | **Exploration (PLANNED — Not Created)** | No | Upstream math & coding outputs, `src/report_generator.py` |
| `notebooks/09_integration_review.ipynb` | Agent 09 | Red-team audit, zero-hardcoding & Pareto non-exclusion inspection | **Exploration (PLANNED — Not Created)** | No | `runs/<run_id>/manifest.json`, `src/review/` |
| `notebooks/10_memory_and_registry.ipynb` | Agent 10 | Artifact registry, context packs, and freshness verification | **Exploration (PLANNED — Not Created)** | No | `src/artifact_registry.py`, `src/context_pack.py`, `src/freshness_checker.py` |
| `notebooks/11_orchestration_qa.ipynb` | Agent 11 | DAG execution, checkpointing, and QA harness prototyping | **Exploration (PLANNED — Not Created)** | No | `src/orchestrator.py`, `src/checkpointing.py`, `src/hardcoding_scanner.py` |

---

## 3. Flagged Duplicate / Ambiguous Production Entry Points for Agent 11 to Resolve

Before any Wave-2 `.ipynb` files are merged to `main`, **Agent 11** must resolve the following structural ambiguities to prevent duplicate production entry points:

1. **Unresolved Directory Path for Colab Stage Notebooks (`00_control_plane.ipynb`–`04_validation.ipynb`)**:
   - Existing architecture documents reference `00_control_plane.ipynb` through `04_validation.ipynb` without a directory prefix (implying repository root or an unspecified `colab/` / `notebooks/` directory), while per-agent notebooks use `notebooks/XX_*.ipynb`.
   - **Action for Agent 11**: Designate one canonical repository-relative path convention (e.g., repo root or `notebooks/colab/0X_*.ipynb`) before creating them so duplicate copies do not appear in multiple directories.
2. **Orchestration Entry-Point Overlap (`src/orchestrator.py` vs. `00_control_plane.ipynb` / `04_validation.ipynb` vs. `notebooks/11_orchestration_qa.ipynb`)**:
   - Control plane (`00_control_plane.ipynb`) and validation (`04_validation.ipynb`) list Agent 11 alongside Agents 01/10 and Agent 09, respectively, while `notebooks/11_orchestration_qa.ipynb` also covers orchestration/QA.
   - **Action for Agent 11**: Enforce that `notebooks/00_`–`11_` are strictly **exploration/diagnostic only** and never act as production pipeline entry points; all production execution must live in `src/` modules invoked by the canonical 5 Colab stage notebooks (or `src/orchestrator.py` CLI).
3. **GPU Coder Entry-Point Overlap (`01_gpu_coders.ipynb` vs. `notebooks/02_qualitative_coding.ipynb`, `notebooks/03_evidence_reconciliation.ipynb`, `notebooks/07_gpu_runtime.ipynb`)**:
   - **Action for Agent 11**: Ensure production LLM inference and reconciliation execute solely through `01_gpu_coders.ipynb` calling `src/model_runtime.py`, `src/subtopic_extraction.py`, `src/value_extraction.py`, `src/evidence_ledger.py`, and `src/reconciliation.py`, with no divergent production code duplicated inside exploratory notebooks.
4. **Handoff & Index Update Rule**:
   - Any agent introducing an actual `.ipynb` file on a task branch must declare its exact repository-relative path, status (`production` vs. `exploration`), GPU requirement, and prerequisites in its handoff so Agent 11 / Agent 10 can update this index during integration.
