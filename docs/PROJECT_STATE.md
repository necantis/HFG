# Project State — HFG (Hybrid Feedback Governance)

> **Last Updated**: 2026-11-12
> **Maintained By**: Agent 10 (Memory & Artifacts) & Agent 00 (System Architect)
> **Active Architecture Version**: `v1.1.0` (12-Agent Architecture + 5-Stage Colab Topology)
> **Active Run ID**: `run_20261111_002`
> **Contract Schema Version**: `1.0.0` / `v1.1.0`
> **Readiness Status**: `WAVE_2_READY`

---

## 1. Global System Status (12-Agent Roster)

| Agent ID | Role / Specialization | Module Scope | Status | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Agent 00** | System Architect | `src/architecture/`, `src/contracts.py`, `schemas/interfaces.json` | `COMPLETE / READY` | Reconciled 12-agent persistent memory with 5-notebook Colab architecture, 20 interface contracts, `ADR-0005` distributional `PreferenceCell`, and `ADR-0006`. |
| **Agent 01** | Data & Question Registry | `src/ingest/`, `src/registry/` | `READY` | Authentic survey `Anonymized_survey_data_2026.csv` write-locked & verified; ready for ingestion (`Q01`–`Q13` + `Q14` remarks). |
| **Agent 02** | Qualitative Coding | `src/nlp/` | `STANDBY` | Bottom-up subtopic extraction, value assignment, and dual-LLM coding contracts defined. |
| **Agent 03** | Evidence & Reconciliation | `src/evidence/` | `STANDBY` | Offset-verified `EvidenceSpan` ledger, dual-coder reconciliation, and constraint-only pruning rules locked. |
| **Agent 04** | Preference, Utility & Pareto | `src/preference/` | `STANDBY` | Distributional `PreferenceCell` ($\sum p_k = 1 \pm 10^{-4}$), constraint-only `GovernanceSolution`, `ParetoResult`, and configurable MC `RobustParetoResult` ready. |
| **Agent 05** | Preference Profiles / Clustering | `src/clustering/` | `STANDBY` | Non-pruning missingness-masked clustering (`preference_profiles.json` / `ClusterResult`) contract defined. |
| **Agent 06** | Voting | `src/voting/` | `STANDBY` | Multi-rule social choice & conditional Baldwin/RRV contracts locked. |
| **Agent 07** | GPU Runtime | `src/runtime/` | `READY` | Dual concurrent LLM hosting & configurable GPU memory fractions (`NVIDIA RTX PRO 6000 Blackwell Server Edition`) specified. |
| **Agent 08** | Report | `src/reporting/` | `STANDBY` | Sink-only presentation report & evidence-bound `ReportClaim` templates configured. |
| **Agent 09** | Final Integration Reviewer | `src/review/` | `READY` | Independent audit, zero-hardcoding gate, and Pareto non-exclusion protocols active (NOT orchestration). |
| **Agent 10** | Documentation, Memory & Artifacts | `src/artifact_registry.py`, `src/context_pack.py`, `src/freshness_checker.py` | `ACTIVE / GREEN` | Context packs `00`–`11`, registry, and freshness checks green. |
| **Agent 11** | Orchestration & QA | `src/pipeline/` | `READY` | DAG runner, Merkle checkpointing, hardcoding scanner, and QA harness established. |

---

## 2. Completed Architectural & Memory Milestones

- [x] **Persistent Multi-Agent Memory Layer (`ADR-0001`–`ADR-0004`):** Established `src/artifact_registry.py`, `src/context_pack.py`, `src/freshness_checker.py`, context packs `agent_00`–`agent_11`, and passing pytest verification suite.
- [x] **12-Agent Reconciliation, Distributional `PreferenceCell` & Pareto Non-Exclusion (`ADR-0005` & `ADR-0006`):** Unified the 12-agent persistent memory architecture with the 5-notebook Google Colab execution pipeline (`00_control_plane.ipynb` through `04_validation.ipynb`) and NVIDIA RTX PRO 6000 Blackwell Server Edition dual-LLM runtime.
- [x] **20 Interface Data Contracts (`docs/DATA_CONTRACTS.md`, `src/contracts.py`, `schemas/interfaces.json`):** Baselined all 20 contracts (`RunManifest` through `AgentHandoff`) with explicit `MissingnessState`, `UncertaintyEnvelope`, `ProvenanceMeta`, and simplex-validated distributional `PreferenceCell`.
- [x] **Pipeline, Checkpointing & Implementation Plan (`docs/PIPELINE.md`, `docs/IMPLEMENTATION_PLAN.md`):** Separated GPU vs. CPU operations, specified WAL resumption and Merkle invalidation targeting $\le 10$ min warm-cache execution, and defined verification gates.

---

## 3. External Immutable Raw Source Verification

- **Canonical Path**: [`data/raw/survey_raw.csv`](data/raw/survey_raw.csv)
- **External Source**: `Anonymized_survey_data_2026.csv`
- **Authority**: `immutable_source` (external write-once source, NOT an analytically generated artifact)
- **Content Status**: Authentic stakeholder dataset, strictly write-locked.
- **Cryptographic Hash (SHA-256)**:
  `56acded3e02be49be27d6b288fa2c43fcce68df24525113eba1b1161eec52a95`
- **Dataset Dimensions**:
  - **Data Rows**: `11`
  - **Total Lines** (with header): `12`
  - **Columns**: `27`
  - **Substantive Questions (1–13) + Remarks (14)**: Pôles relevance, governance coordination scenarios, unified operations, HR, overheads, individual evaluations, and open remarks.
  - **Metadata Columns (15–25, 38)**: Submission timestamps, language (`LANG_SAISIE`), device type, completion progression, and identifier hashes.

---

## 4. Registered Artifacts Summary (`run_20261111_002`)

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
| `review_report_v1` | `runs/run_20261111_002/integration_review_report.json` | Agent 09 | Contract Ready | Pending Run | `canonical_decision` |
| `manifest_v1` | `runs/run_20261111_002/manifest.json` | Agent 10 | Active | Fresh | Authoritative Manifest |
| `run_card_v1` | `runs/run_20261111_002/RUN_CARD.md` | Agent 10 | Active | Fresh | Authoritative Run Provenance |
| `pipeline_qa_v1` | `runs/run_20261111_002/pipeline_execution.log` | Agent 11 | Contract Ready | Pending Run | `canonical_intermediate` |

---

## 5. Run Lifecycle & Historical Invalidation

- **`run_20261111_001`**: `INVALIDATED (Superseded)`. Used temporary scaffolding placeholder data during initial framework setup. Formally invalidated to preserve rigorous cryptographic provenance.
- **`run_20261111_002`**: `ACTIVE / CERTIFIED`. Established with authentic `Anonymized_survey_data_2026.csv` dataset.

---

## 6. Wave 2 Pending Milestones & Readiness Status

- [ ] **Control Plane & Ingestion (Agents 01, 11):** Implement `src/hardcoding_scanner.py`, `src/ingestion.py`, `src/question_registry.py`, `src/provenance.py`, `src/checkpointing.py`, `src/orchestrator.py`, and `00_control_plane.ipynb`.
- [ ] **GPU Qualitative Coding & Reconciliation (Agents 02, 03, 07):** Implement `src/model_runtime.py`, `src/subtopic_extraction.py`, `src/value_extraction.py`, `src/evidence_ledger.py`, `src/reconciliation.py`, and `01_gpu_coders.ipynb`.
- [ ] **Math, Social Choice & Voting (Agents 04, 05, 06):** Implement `src/preference_matrix.py`, `src/clustering.py`, `src/solution_space.py`, `src/utilities.py`, `src/pareto.py`, `src/robust_pareto.py`, `src/voting_baldwin.py`, `src/voting_rrv.py`, and `02_math_analysis.ipynb`.
- [ ] **Reporting & Independent Validation (Agents 08, 09, 11):** Implement `src/report_generator.py`, `03_report.ipynb`, and `04_validation.ipynb`.

**`WAVE_2_READY`**: The persistent project-memory layer, 12-agent context packs, reconciled architecture & 20 interface contracts, authentic raw survey dataset, and analytical invariants are synchronized and validated. Agent 01 is cleared to begin execution.
