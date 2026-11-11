# AGENTS.md — Multi-Agent Collaboration Protocol

> **Core Principle**: Chat history is not project memory. Git commits, manifests, Architecture Decision Records (ADRs), schemas, context packs, and registered artifacts constitute project memory.

---

## 1. Project Purpose
**HFG (Hybrid Feedback Governance)** is a reproducible multi-agent analytical system for ingesting raw stakeholder survey data, extracting qualitative themes, modeling participant utility and pairwise preferences, executing social choice voting rules, and publishing policy briefs with provable analytical invariants.

---

## 2. Current Status & Active Coordinates
- **Architecture Version**: `v1.0.0`
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
2. **Immutable Raw Data**: Raw input files in `data/raw/` are write-once, immutable sources. No agent or script may modify or overwrite them.
3. **No Presentation Feedback Loop**: Final reports and presentation artifacts (`runs/<run_id>/reports/`) are sink-only presentation artifacts. They are strictly forbidden from becoming analytical inputs to any new pipeline run.
4. **Deterministic Reproducibility**: All modeling, clustering, and sampling must use explicit seeds tracked in `runs/<run_id>/RUN_CARD.md`.
5. **Contract Conformance**: All stage outputs must validate against canonical schemas defined in [`docs/DATA_CONTRACTS.md`](file:///home/antigravity/necantis/HFG/docs/DATA_CONTRACTS.md).

---

## 4. Agent Map & Notebook Ownership

| Agent ID | Role / Specialization | Module Ownership | Notebook Ownership | Primary Output |
| :--- | :--- | :--- | :--- | :--- |
| **Agent 01** | Ingestion & Normalization Engineer | `src/ingest/` | `notebooks/01_ingest_exploration.ipynb` | `data/normalized/answers_normalized.parquet` |
| **Agent 02** | Qualitative Coding & Entity Specialist | `src/nlp/` | `notebooks/02_qualitative_coding.ipynb` | `data/processed/themes_codebook.json` |
| **Agent 03** | Candidate & Option Synthesizer | `src/candidates/` | `notebooks/03_candidate_generation.ipynb` | `data/processed/candidate_options.json` |
| **Agent 04** | Preference Learning & Reconciler | `src/preference/` | `notebooks/04_preference_learning.ipynb` | `data/processed/preference_matrix.parquet` |
| **Agent 05** | Utility Modeling & Social Choice Engineer | `src/social_choice/` | `notebooks/05_social_choice_voting.ipynb` | `data/processed/voting_results.json` |
| **Agent 06** | Robustness & Sensitivity Analyst | `src/robustness/` | `notebooks/06_sensitivity_analysis.ipynb` | `data/processed/sensitivity_metrics.json` |
| **Agent 07** | Report & Presentation Generator | `src/reporting/` | `notebooks/07_reporting_presentation.ipynb` | `runs/<run_id>/reports/policy_brief.md` |
| **Agent 08** | Red Team & Invariant Auditor | `src/validation/` | `notebooks/08_verification_redteam.ipynb` | `runs/<run_id>/audit_report.json` |
| **Agent 09** | Orchestration & Execution Engineer | `src/pipeline/` | `notebooks/09_orchestration_monitoring.ipynb` | `runs/<run_id>/pipeline_execution.log` |
| **Agent 10** | Documentation, Memory & Artifact Engineer | `src/artifact_registry.py`, `src/context_pack.py`, `src/freshness_checker.py`, `docs/`, `AGENTS.md` | `notebooks/10_memory_and_registry.ipynb` | Artifact Manifests & Run Cards |

---

## 5. Canonical Artifacts Hierarchy

| Layer | Canonical Artifact | Authority Level | Downstream Consumers |
| :--- | :--- | :--- | :--- |
| **Source** | `data/raw/survey_raw.csv` | Immutable Source | Agent 01 (`src/ingest/`) |
| **Ingestion** | `data/normalized/answers_normalized.parquet` | Canonical Ingestion Artifact | Agent 02, Agent 04 |
| **NLP / Themes** | `data/processed/themes_codebook.json` | Canonical Qualitative Artifact | Agent 03, Agent 07 |
| **Options** | `data/processed/candidate_options.json` | Canonical Option Set | Agent 04, Agent 05 |
| **Preference** | `data/processed/preference_matrix.parquet` | Canonical Utility Input | Agent 05, Agent 06 |
| **Social Choice** | `data/processed/voting_results.json` | Canonical Decision Artifact | Agent 06, Agent 07, Agent 08 |
| **Sensitivity** | `data/processed/sensitivity_metrics.json` | Canonical Robustness Artifact | Agent 07, Agent 08 |
| **Presentation** | `runs/<run_id>/reports/*.md` | Presentation Only (**Never Analytical Input**) | End Users / Stakeholders |
| **Provenance** | `runs/<run_id>/manifest.json` | Authoritative Manifest | Agent 10, All Agents |

---

## 6. How to Find Your Context Pack
Every agent must start by reading its assigned context pack:
- File path: `docs/AGENT_CONTEXT/agent_XX_context.md` (e.g. [`docs/AGENT_CONTEXT/agent_10_context.md`](file:///home/antigravity/necantis/HFG/docs/AGENT_CONTEXT/agent_10_context.md))
- Regenerate anytime using:
  ```bash
  python3 -m src.context_pack --agent XX
  ```
  *(Or generate all context packs with `python3 -m src.context_pack --all`)*.

---

## 7. Files You Must NOT Edit (Boundary Rules)
- **Do not edit files owned by other agents** unless you have logged an Architecture Decision Record (ADR) and updated the relevant data contract in [`docs/DATA_CONTRACTS.md`](file:///home/antigravity/necantis/HFG/docs/DATA_CONTRACTS.md).
- **Do not edit raw data**: Never modify `data/raw/`.
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
