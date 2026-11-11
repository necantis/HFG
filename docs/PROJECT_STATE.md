# Project State — HFG (Hybrid Feedback Governance)

> **Last Updated**: 2026-11-11
> **Maintained By**: Agent 10 (Documentation, Memory & Artifacts)
> **Active Architecture Version**: `v1.1.0` (12-Agent Architecture)
> **Active Run ID**: `run_20261111_001`
> **Readiness Status**: `WAVE_2_READY`

---

## 1. Global System Status (12-Agent Roster)

| Agent ID | Role / Specialization | Module Scope | Status | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Agent 00** | System Architect | `src/architecture/` | `READY` | Invariants and 12-agent systemic specs locked. |
| **Agent 01** | Data & Question Registry | `src/ingest/`, `src/registry/` | `READY` | External raw survey verified & locked; ready for ingestion. |
| **Agent 02** | Qualitative Coding | `src/nlp/` | `STANDBY` | Qualitative coding prompts and codebook contracts defined. |
| **Agent 03** | Evidence & Reconciliation | `src/evidence/` | `STANDBY` | Candidate schema and constraint-only pruning rules locked. |
| **Agent 04** | Preference, Utility & Pareto | `src/preference/` | `STANDBY` | `PreferenceCell` probability distribution contract & MC tuning ready. |
| **Agent 05** | Preference Profiles / Clustering | `src/clustering/` | `STANDBY` | Non-pruning interpretive archetype contract defined. |
| **Agent 06** | Voting | `src/voting/` | `STANDBY` | Multi-rule social choice contracts locked. |
| **Agent 07** | GPU Runtime | `src/runtime/` | `READY` | Runtime memory fraction parameters configured. |
| **Agent 08** | Report | `src/reporting/` | `STANDBY` | Sink-only presentation report templates configured. |
| **Agent 09** | Final Integration Reviewer | `src/review/` | `READY` | Independent audit and red team protocols active (NOT orchestration). |
| **Agent 10** | Documentation, Memory & Artifacts | `src/artifact_registry.py`, `src/context_pack.py` | `ACTIVE / GREEN` | Context packs 00–11 generated, registry and freshness checks green. |
| **Agent 11** | Orchestration & QA | `src/pipeline/` | `READY` | DAG runner and QA harness established. |

---

## 2. External Immutable Raw Source Verification
- **Path**: [`data/raw/survey_raw.csv`](file:///home/antigravity/necantis/HFG/data/raw/survey_raw.csv)
- **Authority**: `immutable_source` (external write-once source, NOT an analytically generated artifact)
- **Content Modification**: STRICTLY ZERO MODIFICATION.
- **SHA-256 Digest**: `d5da57a02403cfbe3e267b48590ae75dce923bc47da3a0037da0d42fab88b963`
- **Dimensions**:
  - Data Rows: `10`
  - Total Lines (with header): `11`
  - Columns: `5` (`participant_id`, `submission_time`, `q1_open_feedback`, `q2_ranking_choices`, `group_cohort`)

---

## 3. Registered Artifacts Summary

| Artifact ID | Canonical Path | Producing Agent | Status | Freshness | Authority Level |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `raw_survey_v1` | `data/raw/survey_raw.csv` | External Input | Registered | Fresh | `immutable_source` |
| `norm_answers_v1` | `data/normalized/answers_normalized.parquet` | Agent 01 | Contract Ready | Pending Run | `canonical_ingestion` |
| `themes_codebook_v1` | `data/processed/themes_codebook.json` | Agent 02 | Contract Ready | Pending Run | `canonical_intermediate` |
| `candidate_options_v1` | `data/processed/candidate_options.json` | Agent 03 | Contract Ready | Pending Run | `canonical_intermediate` |
| `pref_matrix_v1` | `data/processed/preference_matrix.parquet` | Agent 04 | Contract Ready | Pending Run | `canonical_utility_input` |
| `pref_profiles_v1` | `data/processed/preference_profiles.json` | Agent 05 | Contract Ready | Pending Run | `canonical_intermediate` (Interpretive) |
| `voting_results_v1` | `data/processed/voting_results.json` | Agent 06 | Contract Ready | Pending Run | `canonical_decision` |
| `gpu_config_v1` | `runs/run_20261111_001/gpu_runtime_config.json` | Agent 07 | Config Ready | Fresh | `canonical_intermediate` |
| `report_brief_v1` | `runs/run_20261111_001/reports/policy_brief.md` | Agent 08 | Presentation Only | Pending Run | `presentation_only` (Sink) |
| `review_report_v1`| `runs/run_20261111_001/integration_review_report.json` | Agent 09 | Contract Ready | Pending Run | `canonical_decision` |
| `manifest_v1` | `runs/run_20261111_001/manifest.json` | Agent 10 | Active | Fresh | Authoritative Manifest |
| `run_card_v1` | `runs/run_20261111_001/RUN_CARD.md` | Agent 10 | Active | Fresh | Authoritative Run Provenance |
| `pipeline_qa_v1` | `runs/run_20261111_001/pipeline_execution.log` | Agent 11 | Contract Ready | Pending Run | `canonical_intermediate` |

---

## 4. Architecture Decisions & Records (ADR Summary)
- [`ADR-0001`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0001-persistent-project-memory-architecture.md): Persistent Project Memory Architecture.
- [`ADR-0002`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0002-canonical-artifact-hierarchy-and-immutability.md): Canonical Artifact Hierarchy and Immutability.
- [`ADR-0003`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0003-context-pack-generation-strategy.md): Context Pack Generation and Scope Isolation.
- [`ADR-0004`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0004-artifact-registry-and-provenance-manifest.md): Artifact Registry, Provenance Hashes, and Stale State Propagation.
- [`ADR-0005`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0005-twelve-agent-architecture-preference-cell-and-pareto-invariants.md): 12-Agent Architecture, Distributional PreferenceCell, and Pareto Invariants.

---

## 5. Wave 2 Readiness Status
**`WAVE_2_READY`**: The persistent project-memory layer, 12-agent context packs, canonical contracts, and analytical invariants are fully synchronized and validated. Agent 01 is cleared to begin execution.
