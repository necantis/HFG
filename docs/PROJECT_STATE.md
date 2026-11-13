# Project State — HFG (Hybrid Feedback Governance)

> **Last Updated**: 2026-11-12
> **Maintained By**: Agent 10 (Memory & Artifacts) & Agent 00 (System Architect)
> **Active Architecture Version**: `v1.1.0` (12-Agent Architecture + 5-Stage Colab Topology)
> **Active Run ID**: `run_20261111_002`
> **Contract Schema Version**: `1.0.0` / `v1.1.0`
> **Readiness Status**: `WAVE_2A_INTEGRATED_RECOVERY_REQUIRED`

---

## 1. Global System Status (12-Agent Roster)

| Agent ID | Role / Specialization | Module Scope | Status | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Agent 00** | System Architect | `src/architecture/`, `src/contracts.py`, `schemas/interfaces.json` | `COMPLETE / READY` | Reconciled 20 interface contracts, `ResponseEpistemicStatus`, nullable `ValueAssignment.polarity`, and unified `PreferenceCell` (`ADR-0005`, `ADR-0006`, `ADR-0007`). |
| **Agent 01** | Data & Question Registry | `src/ingest/`, `src/registry/` | `COMPLETE / INTEGRATED` | Wave 2A ingestion refinement integrated (`b9dacd5`): 154 normalized rows, orthogonal epistemic status vs usable preference, 13 primary `QuestionSpec` + optional Q14, Gate 1 PASS. |
| **Agent 02** | Qualitative Coding | `src/nlp/` | `INTEGRATED (CPU-TESTED)` | Wave 2A qualitative refinement integrated (`5160140`): consumes canonical `ResponseEpistemicStatus`, preserves reportable non-preference/ambiguous spans, native `polarity=None`, 18/18 unit tests PASS; live GPU coding `NOT_EXECUTED`. |
| **Agent 03** | Evidence & Reconciliation | `src/evidence/` | `STANDBY` | Offset-verified `EvidenceSpan` ledger, dual-coder reconciliation, and constraint-only pruning rules locked (Wave 2B — not yet integrated). |
| **Agent 04** | Preference, Utility & Pareto | `src/preference/` | `STANDBY (OPEN CONTRACT)` | Distributional `PreferenceCell` ($\sum p_k = 1 \pm 10^{-4}$) & `ISSUE-005` open methodological contract (`alternative_probabilities` vs cardinal utility) awaiting resolution prior to utility calculations. |
| **Agent 05** | Preference Profiles / Clustering | `src/clustering/` | `STANDBY` | Non-pruning missingness-masked clustering (`preference_profiles.json` / `ClusterResult`) contract defined. |
| **Agent 06** | Voting | `src/voting/` | `STANDBY` | Multi-rule social choice & conditional Baldwin/RRV contracts locked. |
| **Agent 07** | GPU Runtime | `src/runtime/` | `RECOVERY_REQUIRED` | Prior unpushed implementation (`src/runtime/`, `notebooks/01_gpu_coders.ipynb`, `notebooks/07_gpu_runtime.ipynb`) not recoverable from Git/worktrees; `live_gpu_benchmark: NOT_EXECUTED`. |
| **Agent 08** | Report | `src/reporting/` | `STANDBY` | Sink-only presentation report & evidence-bound `ReportClaim` templates configured. |
| **Agent 09** | Final Integration Reviewer | `src/review/` | `READY` | Independent audit, zero-hardcoding gate, and Pareto non-exclusion protocols active (NOT orchestration). |
| **Agent 10** | Documentation, Memory & Artifacts | `src/artifact_registry.py`, `src/context_pack.py`, `src/freshness_checker.py` | `ACTIVE / GREEN` | Collaboration policy (`ADR-0007`), `docs/NOTEBOOK_INDEX.md`, context packs `00`–`11`, and freshness checks green. |
| **Agent 11** | Orchestration & QA | `src/pipeline/`, `src/hardcoding_scanner.py` | `INTEGRATION_COMPLETE / RECOVERY_REQUIRED` | Wave 2A integrated on `integration/wave-2a` with unified contracts & Gate 1 PASS; prior unpushed `src/orchestration/`, `src/qa/`, `notebooks/00_control_plane.ipynb`, `notebooks/04_validation.ipynb` remain unrecoverable (`ISSUE-006`). |

---

## 2. Completed Architectural & Memory Milestones

- [x] **Persistent Multi-Agent Memory Layer (`ADR-0001`–`ADR-0004`):** Established `src/artifact_registry.py`, `src/context_pack.py`, `src/freshness_checker.py`, context packs `agent_00`–`agent_11`, and passing pytest verification suite.
- [x] **12-Agent Reconciliation, Distributional `PreferenceCell` & Pareto Non-Exclusion (`ADR-0005` & `ADR-0006`):** Unified the 12-agent persistent memory architecture with the 5-notebook Google Colab execution pipeline (`notebooks/00_control_plane.ipynb` through `notebooks/04_validation.ipynb`) and NVIDIA RTX PRO 6000 Blackwell Server Edition dual-LLM runtime.
- [x] **Git Collaboration & Shared-File Protocol (`ADR-0007`):** Enforced branch isolation, handoff synchronization, and canonical vs task-local artifact discipline.
- [x] **20 Interface Data Contracts (`docs/DATA_CONTRACTS.md`, `src/contracts.py`, `schemas/interfaces.json`):** Updated with `ResponseEpistemicStatus`, `ProbabilityInterpretation`, `QuestionSpec.is_primary_question`, `EvidenceSpan.offset_reference_text`, nullable `ValueAssignment.polarity`, and unified `PreferenceCell`.

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
| `raw_survey_v1` | `data/raw/survey_raw.csv` | External Input | Registered | Fresh (Immutable) | `immutable_source` |
| `norm_answers_v1` | `data/normalized/answers_normalized.parquet` | Agent 01 | Registered (Wave 2A Refreshed) | Fresh | `canonical_ingestion` |
| `question_registry_v1` | `data/normalized/question_registry.json` | Agent 01 | Registered (Wave 2A Refreshed) | Fresh | `canonical_intermediate` |
| `themes_codebook_v1` | `data/processed/themes_codebook.json` | Agent 02 | Pending Run (Invalidated / Upstream Updated) | Pending Colab GPU | `canonical_intermediate` |
| `candidate_options_v1` | `data/processed/candidate_options.json` | Agent 03 | Contract Ready | Pending Run | `canonical_intermediate` |
| `pref_matrix_v1` | `data/processed/preference_matrix.parquet` | Agent 04 | Contract Ready | Pending Run | `canonical_utility_input` |
| `pref_profiles_v1` | `data/processed/preference_profiles.json` | Agent 05 | Contract Ready | Pending Run | `canonical_intermediate` (Interpretive) |
| `voting_results_v1` | `data/processed/voting_results.json` | Agent 06 | Contract Ready | Pending Run | `canonical_decision` |
| `gpu_config_v1` | `runs/run_20261111_002/gpu_runtime_config.json` | Agent 07 | Recovery Required (`NOT_EXECUTED`) | Pending Runtime | `canonical_intermediate` |
| `report_brief_v1` | `runs/run_20261111_002/reports/policy_brief.md` | Agent 08 | Presentation Only | Pending Run | `presentation_only` (Sink) |
| `review_report_v1` | `runs/run_20261111_002/integration_review_report.json` | Agent 09 | Contract Ready | Pending Run | `canonical_decision` |
| `manifest_v1` | `runs/run_20261111_002/manifest.json` | Agent 10 / Integration | Active | Fresh | Authoritative Manifest |
| `run_card_v1` | `runs/run_20261111_002/RUN_CARD.md` | Agent 10 / Integration | Active | Fresh | Authoritative Run Provenance |
| `pipeline_qa_v1` | `runs/run_20261111_002/pipeline_execution.log` | Agent 11 | Recovery Required | Pending Run | `canonical_intermediate` |

---

## 5. Run Lifecycle & Historical Invalidation

- **`run_20261111_001`**: `INVALIDATED (Superseded)`. Used temporary scaffolding placeholder data during initial framework setup. Formally invalidated to preserve rigorous cryptographic provenance.
- **`run_20261111_002`**: `ACTIVE / WAVE_2A_INTEGRATED`. Established with authentic `Anonymized_survey_data_2026.csv` dataset; normalized/registry outputs refreshed post-Wave 2A merge; live GPU coding `NOT_EXECUTED`.

---

## 6. Wave 2 Pending Milestones & Readiness Status

- [x] **Data & Question Registry Ingestion (Agent 01):** Integrated `b9dacd5` into `integration/wave-2a`, normalized 154 answers with orthogonal `epistemic_status` vs `has_usable_preference`, registered 13 primary `QuestionSpec`s + optional Q14, and verified Gate 1 PASS.
- [x] **Qualitative Coding Engine & Schema Alignment (Agent 02):** Integrated `5160140` (`e9d3c96`) into `integration/wave-2a` and reconciled `ResponseEpistemicStatus`, `ValueAssignment.polarity: float | None`, and `CodingResult` / `PreferenceCell` contracts.
- [ ] **Control Plane & QA Infrastructure Recovery (Agent 11):** Recover or rebuild `src/orchestration/`, `src/qa/`, `notebooks/00_control_plane.ipynb`, and `notebooks/04_validation.ipynb` (`ISSUE-006`).
- [ ] **GPU Runtime Recovery & Colab Validation (Agent 07):** Recover or rebuild `src/runtime/`, `notebooks/01_gpu_coders.ipynb`, and `notebooks/07_gpu_runtime.ipynb`, then execute dual-LLM coding on Colab GPU hardware.
- [ ] **Evidence Reconciliation, Math, Voting & Reporting (Agents 03–06, 08, 09):** Integrate Agent 03 and resolve `ISSUE-005` (`alternative_probabilities` interpretation for Agent 04) prior to utility calculations.

**`WAVE_2A_INTEGRATED_RECOVERY_REQUIRED`**: Wave 2A code, contracts, ingestion, and qualitative coding engine are integrated and verified on CPU (`integration/wave-2a`), while unpushed Agent 07 GPU runtime and Agent 11 orchestration/QA modules remain unrecoverable and must be restored before Colab GPU validation.
