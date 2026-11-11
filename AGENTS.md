# AGENTS.md — Multi-Agent Collaboration Protocol

> **Core Principle**: Chat history is not project memory. Git commits, manifests, Architecture Decision Records (ADRs), schemas, context packs, and registered artifacts constitute project memory.

---

## 1. Project Purpose
**HFG (Hybrid Feedback Governance)** is a reproducible multi-agent analytical system for ingesting raw stakeholder survey data, extracting qualitative themes, modeling participant utility and pairwise preferences, executing social choice voting rules, and publishing policy briefs with provable analytical invariants.

---

## 2. Current Status & Active Coordinates
- **Architecture Version**: `v1.1.0` (12-Agent Architecture)
- **Active Run**: `run_20261111_001`
- **Global Project State**: [`docs/PROJECT_STATE.md`](file:///home/antigravity/necantis/HFG/docs/PROJECT_STATE.md)
- **Active Architecture**: [`docs/ARCHITECTURE.md`](file:///home/antigravity/necantis/HFG/docs/ARCHITECTURE.md)
- **Data Contracts**: [`docs/DATA_CONTRACTS.md`](file:///home/antigravity/necantis/HFG/docs/DATA_CONTRACTS.md)
- **Execution Pipeline**: [`docs/PIPELINE.md`](file:///home/antigravity/necantis/HFG/docs/PIPELINE.md)
- **Model Strategy**: [`docs/MODEL_STRATEGY.md`](file:///home/antigravity/necantis/HFG/docs/MODEL_STRATEGY.md)
- **Open Issues**: [`docs/OPEN_ISSUES.md`](file:///home/antigravity/necantis/HFG/docs/OPEN_ISSUES.md)

---

## 3. Analytical Invariants (Strict & Enforced)
1. **Survey Isolation & No Cross-Contamination**: Never reuse entities, packages, cluster names, candidate names, voting results, participant counts, numerical results, or recommendations from another survey group.
2. **Immutable Raw Data**: Raw input files in `data/raw/` are external, write-once immutable sources. No agent or script may modify or overwrite them.
3. **No Presentation Feedback Loop**: Final reports and presentation artifacts (`runs/<run_id>/reports/`) are sink-only presentation deliverables. They are strictly forbidden from becoming analytical inputs to any new pipeline run.
4. **Distributional Preference Representation (PreferenceCell)**:
   - Participant preference must be represented primarily as a probability distribution over the actual feasible alternatives: `alternative_probabilities: dict[str, float]`.
   - For observed usable preference cells, probabilities must sum to 1 within numerical tolerance ($\sum p_i = 1 \pm 10^{-4}$).
   - The following metadata MUST be kept separately and never conflated with choice probabilities:
     - `semantic_importance`
     - `coder_confidence`
     - `coder_agreement`
     - `missingness_state`
     - `evidence_ids`
   - A scalar preference score may exist **only** as an optional derived representation when the alternatives have an analytically defensible ordering.
5. **Cluster Non-Exclusion Invariant (Pareto Integrity)**:
   - Clusters, cluster centroids, empirical archetypes, and value coherence may be used to interpret institutional solutions, but must **NOT** be used to exclude otherwise feasible solutions before Pareto analysis.
   - Feasible-option pruning may depend **only** on explicit logical, institutional, or dependency constraints.
6. **Configurable Runtime Parameters**:
   - GPU memory fractions (owned by Agent 07) and robust-Pareto Monte Carlo sample counts (owned by Agent 04) are configurable runtime execution parameters, not immutable architectural constants.
7. **Deterministic Reproducibility**: All modeling, clustering, and sampling must use explicit seeds tracked in `runs/<run_id>/RUN_CARD.md`.
8. **Contract Conformance**: All stage outputs must validate against canonical schemas defined in [`docs/DATA_CONTRACTS.md`](file:///home/antigravity/necantis/HFG/docs/DATA_CONTRACTS.md).

---

## 4. 12-Agent Map & Notebook Ownership

| Agent ID | Role / Specialization | Module Ownership | Notebook Ownership | Primary Output |
| :--- | :--- | :--- | :--- | :--- |
| **Agent 00** | System Architect | `src/architecture/`, `docs/ARCHITECTURE.md` | `notebooks/00_architecture_exploration.ipynb` | Systemic Invariants & Architecture Specs |
| **Agent 01** | Data & Question Registry | `src/ingest/`, `src/registry/` | `notebooks/01_ingest_exploration.ipynb` | `data/normalized/answers_normalized.parquet` & Question Registry |
| **Agent 02** | Qualitative Coding | `src/nlp/` | `notebooks/02_qualitative_coding.ipynb` | `data/processed/themes_codebook.json` |
| **Agent 03** | Evidence & Reconciliation | `src/evidence/` | `notebooks/03_evidence_reconciliation.ipynb` | `data/processed/candidate_options.json` |
| **Agent 04** | Preference, Utility & Pareto | `src/preference/` | `notebooks/04_preference_utility_pareto.ipynb` | `data/processed/preference_matrix.parquet` & Pareto Frontiers |
| **Agent 05** | Preference Profiles / Clustering | `src/clustering/` | `notebooks/05_preference_profiles_clustering.ipynb` | `data/processed/preference_profiles.json` (Archetypes) |
| **Agent 06** | Voting | `src/voting/` | `notebooks/06_voting_social_choice.ipynb` | `data/processed/voting_results.json` |
| **Agent 07** | GPU Runtime | `src/runtime/` | `notebooks/07_gpu_runtime.ipynb` | GPU Resource & Execution Allocation Config |
| **Agent 08** | Report | `src/reporting/` | `notebooks/08_reporting.ipynb` | `runs/<run_id>/reports/policy_brief.md` (Sink Only) |
| **Agent 09** | Final Integration Reviewer | `src/review/` | `notebooks/09_integration_review.ipynb` | `runs/<run_id>/integration_review_report.json` |
| **Agent 10** | Documentation, Memory & Artifacts | `src/artifact_registry.py`, `src/context_pack.py`, `src/freshness_checker.py`, `docs/`, `AGENTS.md` | `notebooks/10_memory_and_registry.ipynb` | Artifact Manifests & Run Cards |
| **Agent 11** | Orchestration & QA | `src/pipeline/` | `notebooks/11_orchestration_qa.ipynb` | `runs/<run_id>/pipeline_execution.log` & QA Test Reports |

> **Crucial Role Disambiguation**:
> - **Agent 09** is the independent **Final Integration Reviewer** responsible for end-to-end holistic auditing and invariant compliance. It does NOT orchestrate pipelines.
> - **Agent 11** is the sole owner of **Pipeline Orchestration & QA Automation**.

---

## 5. Canonical Artifacts Hierarchy

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

## 6. How to Find Your Context Pack
Every agent must start by reading its assigned context pack:
- File path: `docs/AGENT_CONTEXT/agent_XX_context.md` (e.g. [`docs/AGENT_CONTEXT/agent_00_context.md`](file:///home/antigravity/necantis/HFG/docs/AGENT_CONTEXT/agent_00_context.md) through [`docs/AGENT_CONTEXT/agent_11_context.md`](file:///home/antigravity/necantis/HFG/docs/AGENT_CONTEXT/agent_11_context.md))
- Regenerate anytime using:
  ```bash
  python3 -m src.context_pack --agent XX
  ```
  *(Or generate all context packs with `python3 -m src.context_pack --all`)*.

---

## 7. Files You Must NOT Edit (Boundary Rules)
- **Do not edit files owned by other agents** unless you have logged an Architecture Decision Record (ADR) and updated the relevant data contract in [`docs/DATA_CONTRACTS.md`](file:///home/antigravity/necantis/HFG/docs/DATA_CONTRACTS.md).
- **Do not edit raw data**: Never modify `data/raw/survey_raw.csv`.
- **Do not edit superseded ADRs**: Historical ADRs are immutable; mark them superseded with a new ADR.
- **Do not edit registered run manifests directly**: Use [`src/artifact_registry.py`](file:///home/antigravity/necantis/HFG/src/artifact_registry.py).

---

## 8. How to Create an Agent Handoff
Before finishing any turn or session, every agent must write a formal handoff file:
- File path: `docs/AGENT_HANDOFFS/agent_XX_handoff.md`
- Template: [`docs/AGENT_HANDOFFS/template_handoff.md`](file:///home/antigravity/necantis/HFG/docs/AGENT_HANDOFFS/template_handoff.md)
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

## 9. How to Run Relevant Tests
All testing is managed via `pytest`. Use the project virtual environment:
```bash
source .venv/bin/activate
pytest tests/ -v
```
To run artifact registry and memory verification specifically:
```bash
pytest tests/test_artifact_registry.py tests/test_context_pack.py tests/test_freshness_checker.py tests/test_acceptance.py -v
```
To run automated freshness and provenance checks:
```bash
python3 -m src.freshness_checker --check-all
```
