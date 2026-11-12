# Project State — HFG (Hybrid Feedback Governance)

> **Last Updated**: 2026-11-11
> **Maintained By**: Agent 10 (Documentation, Memory & Artifacts)
> **Active Architecture Version**: `v1.1.0` (12-Agent Architecture)
> **Active Run ID**: `run_20261111_002`
> **Readiness Status**: `WAVE_2_READY`

---

## 1. Global System Status (12-Agent Roster)

| Agent ID | Role / Specialization | Module Scope | Status | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Agent 00** | System Architect | `src/architecture/` | `READY` | Invariants and 12-agent systemic specs locked. |
| **Agent 01** | Data & Question Registry | `src/ingest/`, `src/registry/` | `READY` | Authentic survey `Anonymized_survey_data_2026.csv` write-locked & verified; ready for ingestion. |
| **Agent 02** | Qualitative Coding | `src/nlp/` | `STANDBY` | Qualitative coding prompts and codebook contracts defined. |
| **Agent 03** | Evidence & Reconciliation | `src/evidence/` | `STANDBY` | Candidate schema and constraint-only pruning rules locked. |
| **Agent 04** | Preference, Utility & Pareto | `src/preference/` | `STANDBY` | `PreferenceCell` probability distribution contract & MC tuning ready. |
| **Agent 05** | Preference Profiles / Clustering | `src/clustering/` | `STANDBY` | Non-pruning empirical preference profiles contract defined. |
| **Agent 06** | Voting | `src/voting/` | `STANDBY` | Multi-rule social choice contracts locked. |
| **Agent 07** | GPU Runtime | `src/runtime/` | `READY` | Runtime memory fraction parameters configured. |
| **Agent 08** | Report | `src/reporting/` | `STANDBY` | Sink-only presentation report templates configured. |
| **Agent 09** | Final Integration Reviewer | `src/review/` | `READY` | Independent audit and red team protocols active (NOT orchestration). |
| **Agent 10** | Documentation, Memory & Artifacts | `src/artifact_registry.py`, `src/context_pack.py` | `ACTIVE / GREEN` | Context packs 00–11 generated, registry and freshness checks green. |
| **Agent 11** | Orchestration & QA | `src/pipeline/` | `READY` | DAG runner and QA harness established. |

---

## 2. External Immutable Raw Source Verification
- **Canonical Path**: [`data/raw/survey_raw.csv`](file:///home/antigravity/necantis/HFG/data/raw/survey_raw.csv)
- **External Source**: [`Anonymized_survey_data_2026.csv`](file:///home/antigravity/Anonymized_survey_data_2026.csv)
- **Authority**: `immutable_source` (external write-once source, NOT an analytically generated artifact)
- **Content Status**: Authentic stakeholder dataset, strictly write-locked.
- **Cryptographic Hash (SHA-256)**:
  `56acded3e02be49be27d6b288fa2c43fcce68df24525113eba1b1161eec52a95`
- **Dataset Dimensions**:
  - **Data Rows**: `11`
  - **Total Lines** (with header): `12`
  - **Columns**: `27`
  - **Key Questions (1–14)**: Pôles relevance, governance coordination scenarios, unified operations, HR, overheads, individual evaluations.
  - **Metadata Columns (15–25, 38)**: Submission timestamps, device type, completion progression, and cryptographic identifier hashes.

---

## 3. Registered Artifacts Summary (`run_20261111_002`)

| Artifact ID | Canonical Path | Producing Agent | Status | Freshness | Authority Level |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `raw_survey_v1` | `data/raw/survey_raw.csv` | External Input | Registered | Fresh | `immutable_source` |
| `norm_answers_v1` | `data/normalized/answers_normalized.parquet` | Agent 01 | Contract Ready | Pending Run | `canonical_ingestion` |
| `themes_codebook_v1` | `data/processed/themes_codebook.json` | Agent 02 | Contract Ready | Pending Run | `canonical_intermediate` |
| `candidate_options_v1` | `data/processed/candidate_options.json` | Agent 03 | Contract Ready | Pending Run | `canonical_intermediate` |
| `pref_matrix_v1` | `data/processed/preference_matrix.parquet` | Agent 04 | Contract Ready | Pending Run | `canonical_utility_input` |
| `pref_profiles_v1` | `data/processed/preference_profiles.json` | Agent 05 | Contract Ready | Pending Run | `canonical_intermediate` (Interpretive) |
| `voting_results_v1` | `data/processed/voting_results.json` | Agent 06 | Contract Ready | Pending Run | `canonical_decision` |
| `gpu_config_v1` | `runs/run_20261111_002/gpu_runtime_config.json` | Agent 07 | Config Ready | Fresh | `canonical_intermediate` |
| `report_brief_v1` | `runs/run_20261111_002/reports/policy_brief.md` | Agent 08 | Presentation Only | Pending Run | `presentation_only` (Sink) |
| `review_report_v1`| `runs/run_20261111_002/integration_review_report.json` | Agent 09 | Contract Ready | Pending Run | `canonical_decision` |
| `manifest_v1` | `runs/run_20261111_002/manifest.json` | Agent 10 | Active | Fresh | Authoritative Manifest |
| `run_card_v1` | `runs/run_20261111_002/RUN_CARD.md` | Agent 10 | Active | Fresh | Authoritative Run Provenance |
| `pipeline_qa_v1` | `runs/run_20261111_002/pipeline_execution.log` | Agent 11 | Contract Ready | Pending Run | `canonical_intermediate` |

---

## 4. Run Lifecycle & Historical Invalidation
- **`run_20261111_001`**: `INVALIDATED (Superseded)`. Used temporary scaffolding placeholder data during initial framework setup. Formally invalidated to preserve rigorous cryptographic provenance.
- **`run_20261111_002`**: `ACTIVE / CERTIFIED`. Established with authentic `Anonymized_survey_data_2026.csv` dataset.

---

## 5. Wave 2 Readiness Status
**`WAVE_2_READY`**: The persistent project-memory layer, 12-agent context packs, canonical contracts, authentic raw survey dataset, and analytical invariants are fully synchronized and validated. Agent 01 is cleared to begin execution.
