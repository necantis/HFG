# AGENTS.md — Multi-Agent Collaboration & Governance Protocol

> **Core Principle**: Chat history is not project memory. Git commits, manifests, Architecture Decision Records (ADRs), schemas, context packs, and registered artifacts constitute project memory.

**System:** Multilingual Institutional Survey Analysis System (HFG — Hybrid Feedback Governance)  
**Architecture Version:** `v1.1.0` (12-Agent Architecture + 5-Stage Colab Execution Topology)  
**Contract Schema Version:** `1.0.0` / `v1.1.0`

---

## 1. Project Purpose & Active Coordinates

**HFG (Hybrid Feedback Governance)** is a reproducible multi-agent analytical system for ingesting raw multilingual (`fr`, `de`, `en`) stakeholder survey data, extracting evidence-grounded subtopics and qualitative themes, modeling participant preferences and utilities, executing social choice voting rules and participant-level Pareto analysis, and publishing traceable policy briefs with provable analytical invariants.

- **Active Run**: `run_20261111_002`
- **Global Project State**: [`docs/PROJECT_STATE.md`](docs/PROJECT_STATE.md)
- **Active Architecture**: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- **Data Contracts**: [`docs/DATA_CONTRACTS.md`](docs/DATA_CONTRACTS.md) (`src/contracts.py`, `schemas/interfaces.json`)
- **Execution Pipeline**: [`docs/PIPELINE.md`](docs/PIPELINE.md)
- **Implementation Plan**: [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md)
- **Model Strategy**: [`docs/MODEL_STRATEGY.md`](docs/MODEL_STRATEGY.md)
- **Open Issues**: [`docs/OPEN_ISSUES.md`](docs/OPEN_ISSUES.md)

---

## 2. Analytical Invariants (Strict & Enforced)

1. **Authoritative Sources Only:** Treat repository documentation (`docs/`), ADRs (`docs/DECISIONS/`), active source files (`src/`), and registered artifacts (`runs/<run_id>/manifest.json` / `ArtifactRecord`) as authoritative. Never rely on prior chat history.
2. **Survey Isolation & Zero Cross-Survey Reuse:** Never reuse entities, institutional packages, cluster names, candidate names, voting results, participant counts, numerical results, or recommendations from another survey group. Blocked statically and at runtime by `src/hardcoding_scanner.py` and audited by Agent 09.
3. **Immutable Raw Data:** Raw input files in `data/raw/` (`data/raw/survey_raw.csv`) are external, write-once immutable sources. No agent or script may modify or overwrite them.
4. **No Presentation Feedback Loop:** Final reports and presentation artifacts (`runs/<run_id>/reports/`) are sink-only presentation deliverables. They are strictly forbidden from becoming analytical inputs to any pipeline run.
5. **13-Question Primary Analytical Spine:** The 13 substantive questions (`Q01`–`Q13`, plus optional general remarks `Q14`) in French (`fr`), German (`de`), or English (`en`) remain the primary analytical structure across ingestion, subtopic discovery, preference modeling, solution synthesis, and reporting.
6. **Bottom-Up Subtopic Discovery & Cross-Question Values:** Multiple subtopics per question (`CanonicalSubtopic`) must be extracted dynamically from participant `EvidenceSpan` records—never inferred merely from question wording. Subtopics across questions are connected via evidence-supported organisational values (`ValueAssignment`).
7. **Domain-Appropriate Economic Good Classification:** Apply `private_good`, `club_good`, `common_good`, and `public_good` classifications **only** when conceptually appropriate to allocation, access, ownership, financial responsibility, or decision rights (`QuestionSpec.economic_good_classification_policy != "DISABLED"`). Use question-specific analytical frames for perception and diagnostic questions.
8. **Dual Independent LLM Coding:** Two architecturally distinct LLMs (`coder_a` and `coder_b`) code qualitative evidence concurrently on the target GPU runtime (e.g., NVIDIA RTX PRO 6000 Blackwell Server Edition) with `temperature = 0.0` and prompt hash provenance.
9. **Strict Missingness Preservation:** Missing answers always remain explicitly missing (`MissingnessState != observed_usable`, no imputation of `0.0` for missing or unmentioned cells).
10. **Distributional Preference Representation (`PreferenceCell`) & Orthogonal Quantities (`ADR-0005`):**
    - Participant preference must be represented primarily as a probability distribution over the actual feasible alternatives: `alternative_probabilities: dict[str, float]`.
    - For observed usable preference cells (`observed_usable`), probabilities must sum to 1 within numerical tolerance ($\sum p_k = 1.0 \pm 10^{-4}$).
    - The following metadata MUST be kept strictly separate and never conflated with choice probabilities:
      - `semantic_importance`
      - `coder_confidence`
      - `coder_agreement`
      - `missingness_state`
      - `evidence_ids` / `evidence_span_ids`
    - A scalar preference score (`derived_scalar_score`) may exist **only** as an optional derived representation when the alternatives have an analytically defensible ordering.
11. **Exclusive Utility Provenance:** Derive `ParticipantUtility` exclusively from the validated `PreferenceMatrix`.
12. **Dynamic Solutions, Constraint-Only Pruning & Pareto Non-Exclusion Invariant:**
    - Generate `FeasibleAlternative` and `GovernanceSolution` dynamically; prune candidate solutions **strictly and exclusively** by logical constraints, institutional constraints, and explicit structural dependencies.
    - **Strict Invariant:** Clustering assignments, cluster centroids, empirical preference profiles, and value linkages may explain, interpret, or characterize solutions ex-post—they may **never** determine or filter whether an otherwise feasible solution is included in the Pareto choice set.
    - Evaluate exact participant-level `ParetoResult` and Monte Carlo `RobustParetoResult`; rank nondominated solutions transparently using Rawls/maximin, utilitarian, Nash social welfare, inequality (Gini/Atkinson), opposition/veto, and minimax regret.
13. **Data-Driven Clustering (`Preference Profiles`):** Select cluster count $k^*$ and assignments (`ClusterResult` / `preference_profiles.json`) strictly from missingness-masked distances on `PreferenceMatrix`.
14. **Conditional Voting Modules & Social Choice:** Execute `src/voting_baldwin.py` and `src/voting_rrv.py` **only if** active-group ballot files exist and pass validation (`execution_status = "SKIPPED_NO_VALID_INPUT"` otherwise), alongside Borda/Condorcet/Minimax social choice rules (`voting_results.json`).
15. **Configurable Runtime Parameters:** GPU memory fractions (owned by Agent 07) and robust-Pareto Monte Carlo sample counts (owned by Agent 04) are configurable runtime execution parameters, not immutable architectural constants.
16. **Traceable Claims, Deterministic Reproducibility & Checkpoints:** Every `ReportClaim` must link to verified `EvidenceSpan` / `evidence_ids` and mathematical `ArtifactRecord` IDs; explicit seeds are tracked in `runs/<run_id>/RUN_CARD.md`; all expensive stages use content-addressed checkpoints targeting $\le 10$ minutes warm-cache execution.
17. **Contract Conformance:** All stage outputs must validate against canonical schemas defined in [`docs/DATA_CONTRACTS.md`](docs/DATA_CONTRACTS.md) and [`src/contracts.py`](src/contracts.py).

---

## 3. 12-Agent Map, Notebook Ownership & Colab Execution Mapping

| Agent ID | Role / Specialization | Module Ownership | Exploratory Notebook | Colab Stage Notebook | Primary Output |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Agent 00** | System Architect | `src/architecture/`, `src/contracts.py`, `schemas/interfaces.json`, `docs/ARCHITECTURE.md` | `notebooks/00_architecture_exploration.ipynb` | Architecture Specs | Systemic Invariants, 20 Data Contracts & Architecture Specs |
| **Agent 01** | Data & Question Registry | `src/ingest/`, `src/registry/` (`src/ingestion.py`, `src/question_registry.py`) | `notebooks/01_ingest_exploration.ipynb` | `00_control_plane.ipynb` | `data/normalized/answers_normalized.parquet` & 13 `QuestionSpec` |
| **Agent 02** | Qualitative Coding | `src/nlp/` (`src/subtopic_extraction.py`, `src/value_extraction.py`) | `notebooks/02_qualitative_coding.ipynb` | `01_gpu_coders.ipynb` | `data/processed/themes_codebook.json`, `CanonicalSubtopic`, `ValueAssignment` |
| **Agent 03** | Evidence & Reconciliation | `src/evidence/` (`src/evidence_ledger.py`, `src/reconciliation.py`) | `notebooks/03_evidence_reconciliation.ipynb` | `01_gpu_coders.ipynb` | `data/processed/candidate_options.json`, `EvidenceSpan`, `CodingResult` |
| **Agent 04** | Preference, Utility & Pareto | `src/preference/` (`src/preference_matrix.py`, `src/solution_space.py`, `src/utilities.py`, `src/pareto.py`, `src/robust_pareto.py`) | `notebooks/04_preference_utility_pareto.ipynb` | `02_math_analysis.ipynb` | `data/processed/preference_matrix.parquet`, `GovernanceSolution`, Pareto Frontiers |
| **Agent 05** | Preference Profiles / Clustering | `src/clustering/` (`src/clustering.py`) | `notebooks/05_preference_profiles_clustering.ipynb` | `02_math_analysis.ipynb` | `data/processed/preference_profiles.json` (`ClusterResult`) |
| **Agent 06** | Voting | `src/voting/` (`src/voting_baldwin.py`, `src/voting_rrv.py`) | `notebooks/06_voting_social_choice.ipynb` | `02_math_analysis.ipynb` | `data/processed/voting_results.json` (`BaldwinResult`, `RRVResult`) |
| **Agent 07** | GPU Runtime | `src/runtime/` (`src/model_runtime.py`) | `notebooks/07_gpu_runtime.ipynb` | `01_gpu_coders.ipynb` | GPU Resource & Dual-LLM Server Allocation Config (`gpu_runtime_config.json`) |
| **Agent 08** | Report | `src/reporting/` (`src/report_generator.py`) | `notebooks/08_reporting.ipynb` | `03_report.ipynb` | `runs/<run_id>/reports/policy_brief.md` (`ReportClaim`, Sink Only) |
| **Agent 09** | Final Integration Reviewer | `src/review/` | `notebooks/09_integration_review.ipynb` | `04_validation.ipynb` | `runs/<run_id>/integration_review_report.json` |
| **Agent 10** | Documentation, Memory & Artifacts | `src/artifact_registry.py`, `src/context_pack.py`, `src/freshness_checker.py`, `docs/`, `AGENTS.md` | `notebooks/10_memory_and_registry.ipynb` | `00_control_plane.ipynb` | Artifact Manifests (`manifest.json`) & Run Cards (`RUN_CARD.md`) |
| **Agent 11** | Orchestration & QA | `src/pipeline/` (`src/provenance.py`, `src/checkpointing.py`, `src/hardcoding_scanner.py`, `src/orchestrator.py`) | `notebooks/11_orchestration_qa.ipynb` | `00_control_plane.ipynb` / `04_validation.ipynb` | `runs/<run_id>/pipeline_execution.log` & QA Test Reports |

> **Crucial Role Disambiguation**:
> - **Agent 09** is the independent **Final Integration Reviewer** responsible for end-to-end holistic auditing and invariant compliance. It does NOT orchestrate pipelines.
> - **Agent 11** is the sole owner of **Pipeline Orchestration & QA Automation**.

---

## 4. Canonical Artifacts Hierarchy

| Layer | Canonical Artifact | Authority Level | Producing Agent | Downstream Consumers |
| :--- | :--- | :--- | :--- | :--- |
| **Source** | `data/raw/survey_raw.csv` | Immutable External Source | External | Agent 01 (`src/ingest/`) |
| **Ingestion** | `data/normalized/answers_normalized.parquet` | Canonical Ingestion Artifact | Agent 01 | Agent 02, Agent 04 |
| **Qualitative** | `data/processed/themes_codebook.json` | Canonical Qualitative Artifact | Agent 02 | Agent 03, Agent 08 |
| **Evidence/Options** | `data/processed/candidate_options.json` | Canonical Option Set | Agent 03 | Agent 04, Agent 05, Agent 06 |
| **Preference/Pareto** | `data/processed/preference_matrix.parquet` | Canonical Utility Input | Agent 04 | Agent 05, Agent 06 |
| **Profiles/Clusters** | `data/processed/preference_profiles.json` | Interpretive Artifact (Non-Pruning) | Agent 05 | Agent 08, Agent 09 |
| **Voting/Decision** | `data/processed/voting_results.json` | Canonical Decision Artifact | Agent 06 | Agent 08, Agent 09 |
| **Presentation** | `runs/<run_id>/reports/*.md` | Presentation Only (**Never Analytical Input**) | Agent 08 | Stakeholders |
| **Integration Review** | `runs/<run_id>/integration_review_report.json` | Authoritative Audit Artifact | Agent 09 | Agent 10, Agent 11 |
| **Provenance** | `runs/<run_id>/manifest.json` | Authoritative Manifest | Agent 10 | All Agents |
| **Pipeline Trace** | `runs/<run_id>/pipeline_execution.log` | Execution Trace Artifact | Agent 11 | Agent 09, Agent 10 |

---

## 5. How to Find Your Context Pack

Every agent must start by reading its assigned context pack:
- File path: `docs/AGENT_CONTEXT/agent_XX_context.md` (e.g. [`docs/AGENT_CONTEXT/agent_00_context.md`](docs/AGENT_CONTEXT/agent_00_context.md) through [`docs/AGENT_CONTEXT/agent_11_context.md`](docs/AGENT_CONTEXT/agent_11_context.md))
- Regenerate anytime using:
  ```bash
  python -m src.context_pack --agent XX
  ```
  *(Or generate all context packs with `python -m src.context_pack --all`)*.

---

## 6. Files You Must NOT Edit (Boundary Rules)

- **Do not edit files owned by other agents** unless you have logged an Architecture Decision Record (ADR) and updated the relevant data contract in [`docs/DATA_CONTRACTS.md`](docs/DATA_CONTRACTS.md).
- **Do not edit raw data**: Never modify `data/raw/survey_raw.csv`.
- **Do not edit superseded ADRs**: Historical ADRs are immutable; mark them superseded with a new ADR.
- **Do not edit registered run manifests directly**: Use [`src/artifact_registry.py`](src/artifact_registry.py).

---

## 7. How to Create an Agent Handoff

Before finishing any turn or session, every agent must write a formal handoff file:
- File path: `docs/AGENT_HANDOFFS/agent_XX_handoff.md`
- Template: [`docs/AGENT_HANDOFFS/template_handoff.md`](docs/AGENT_HANDOFFS/template_handoff.md)
- Required fields:
  1. Agent ID
  2. Model used
  3. Branch / worktree
  4. Files changed
  5. Interfaces changed
  6. Tests executed
  7. Artifacts created
  8. Assumptions
  9. Unresolved issues
  10. Downstream dependencies
  11. Exact recommended next action

---

## 8. How to Run Relevant Tests

All testing is managed via `pytest`:
```bash
pytest tests/ -v
```
To run artifact registry and memory verification specifically:
```bash
pytest tests/test_artifact_registry.py tests/test_context_pack.py tests/test_freshness_checker.py tests/test_acceptance.py -v
```
To run automated freshness and provenance checks:
```bash
python -m src.freshness_checker --check-all
```

## 9. Git synchronization

An agent task is not considered handed off until:

1. tests pass;
2. freshness checks pass;
3. artifacts are registered;
4. handoff is written;
5. changes are committed;
6. remote branch is pushed successfully;
7. the handoff records the resulting Git commit SHA.