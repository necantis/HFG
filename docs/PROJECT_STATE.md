# Project State — HFG (Hybrid Feedback Governance)

> **Last Updated**: 2026-11-13
> **Maintained By**: Agent 10 (Memory & Artifacts) & Agent 00 (System Architect) | **Reconciled By**: Agent 11 (Orchestration & QA)
> **Active Architecture Version**: `v1.1.0` (12-Agent Architecture + 5-Stage Colab Topology)
> **Active Run ID**: `run_20261111_002`
> **Contract Schema Version**: `1.0.0` / `v1.1.0`
> **Readiness Status**: `GPU_PREFLIGHT_VERIFIED_AWAITING_DUAL_CODING` (`AGENT_03_RELEASE = BLOCKED`)

---

## 1. Global System Status (12-Agent Roster)

| Agent ID | Role / Specialization | Module Scope | Status | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Agent 00** | System Architect | `src/architecture/`, `src/contracts.py`, `schemas/interfaces.json` | `COMPLETE / READY` | Reconciled 20 interface contracts, `ResponseEpistemicStatus`, nullable `ValueAssignment.polarity`, and unified `PreferenceCell` (`ADR-0005`, `ADR-0006`, `ADR-0007`). |
| **Agent 01** | Data & Question Registry | `src/ingest/`, `src/registry/` | `COMPLETE / INTEGRATED` | Integrated on `main` (PR #2): 154 normalized rows (`11` participants), orthogonal epistemic status vs usable preference, 13 primary `QuestionSpec` + optional Q14, Gate 1 `PASS`. |
| **Agent 02** | Qualitative Coding | `src/nlp/` | `INTEGRATED (ENTRANCE GATES PASS; LIVE CODING PENDING)` | Integrated on `main` (PR #2): consumes `ResponseEpistemicStatus`, preserves reportable non-preference/ambiguous spans, native `polarity=None`; live GPU Coder A/B execution `NOT_EXECUTED`. |
| **Agent 03** | Evidence & Reconciliation | `src/evidence/` | `BLOCKED (RELEASE GATE)` | **HARD BLOCK (`AGENT_03_RELEASE = BLOCKED`)**: Waiting on live 5-stage GPU benchmark, real Coder A & Coder B outputs, and A–H dual-coder invariant validation (`ISSUE-007`). |
| **Agent 04** | Preference, Utility & Pareto | `src/preference/` | `STANDBY (OPEN CONTRACT)` | Distributional `PreferenceCell` ($\sum p_k = 1 \pm 10^{-4}$) & `ISSUE-005` open methodological contract (`alternative_probabilities` vs cardinal utility) awaiting resolution prior to utility calculations. |
| **Agent 05** | Preference Profiles / Clustering | `src/clustering/` | `STANDBY` | Non-pruning missingness-masked clustering (`preference_profiles.json` / `ClusterResult`) contract defined. |
| **Agent 06** | Voting | `src/voting/` | `STANDBY` | Multi-rule social choice & conditional Baldwin/RRV contracts locked. |
| **Agent 07** | GPU Runtime | `src/runtime/`, `src/model_runtime.py` | `INTEGRATED / PREFLIGHT PASS (BENCHMARK PENDING)` | Persisted and merged into `main` via PR #4 (`5f8c305`, bootstrap `61417eb`). Colab `NVIDIA RTX PRO 6000 Blackwell` hardware preflight (`97887 MB` VRAM) & Gate 2 authorization (`AUTHORIZED`) verified; 5-stage live GPU benchmark `NOT_EXECUTED` (`ISSUE-007`). |
| **Agent 08** | Report | `src/reporting/` | `STANDBY` | Sink-only presentation report & evidence-bound `ReportClaim` templates configured. |
| **Agent 09** | Final Integration Reviewer | `src/review/` | `READY` | Independent audit, zero-hardcoding gate, and Pareto non-exclusion protocols active (NOT orchestration). |
| **Agent 10** | Documentation, Memory & Artifacts | `src/artifact_registry.py`, `src/context_pack.py`, `src/freshness_checker.py` | `ACTIVE / GREEN` | Collaboration policy (`ADR-0007`), `docs/NOTEBOOK_INDEX.md`, `runs/run_20261111_002/manifest.json` (`gpu_runtime_config_v1` registered), context packs `00`–`11`, and 9/9 freshness checks green. |
| **Agent 11** | Orchestration & QA | `src/pipeline/`, `src/hardcoding_scanner.py` | `INTEGRATION_READY / ENFORCING RELEASE GATE` | Minimal evidence-derived `PipelineOrchestrator`, A–H dual-coder validator, `notebooks/00_control_plane.ipynb`, `notebooks/04_validation.ipynb`, and `tests/test_pipeline.py` implemented on `agent/11-orchestration-recovery`; enforces `AGENT_03_RELEASE = BLOCKED` (`ISSUE-006` resolved). |

---

## 2. Completed Architectural & Memory Milestones

- [x] **Persistent Multi-Agent Memory Layer (`ADR-0001`–`ADR-0004`):** Established `src/artifact_registry.py`, `src/context_pack.py`, `src/freshness_checker.py`, context packs `agent_00`–`agent_11`, and passing pytest verification suite.
- [x] **12-Agent Reconciliation, Distributional `PreferenceCell` & Pareto Non-Exclusion (`ADR-0005` & `ADR-0006`):** Unified the 12-agent persistent memory architecture with the 5-notebook Google Colab execution pipeline (`notebooks/00_control_plane.ipynb` through `notebooks/04_validation.ipynb`) and NVIDIA RTX PRO 6000 Blackwell Server Edition dual-LLM runtime.
- [x] **Git Collaboration & Shared-File Protocol (`ADR-0007`):** Enforced branch isolation, handoff synchronization, and canonical vs task-local artifact discipline.
- [x] **20 Interface Data Contracts (`docs/DATA_CONTRACTS.md`, `src/contracts.py`, `schemas/interfaces.json`):** Updated with `ResponseEpistemicStatus`, `ProbabilityInterpretation`, `QuestionSpec.is_primary_question`, `EvidenceSpan.offset_reference_text`, nullable `ValueAssignment.polarity`, and unified `PreferenceCell`.
- [x] **Wave 2A + Agent 07 GPU Runtime Merged on `main`:** PR #1 (`agent/10-collaboration-policy`), PR #2 (`integration/wave-2a`), and PR #4 (`agent/07-runtime`) merged into `main` (`61417eb`); stale PR #3 closed without duplicate merge.

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
  - **Substantive Questions (1–13) + Remarks (14)**: Pôles relevance, governance coordination scenarios, unified operations, HR, overheads, individual evaluations, and open remarks (`154` normalized rows: `136` `observed_usable`, `10` `missing_raw_blank`, `6` `missing_non_substantive`, `2` `ambiguous`).

---

## 4. Registered Artifacts Summary (`run_20261111_002`)

| Artifact ID | Canonical Path | Producing Agent | Status | Freshness | Authority Level |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `raw_survey_v1` | `data/raw/survey_raw.csv` | External Input | Registered | Fresh (Immutable) | `immutable_source` |
| `norm_answers_v1` | `data/normalized/answers_normalized.parquet` | Agent 01 | Registered (Gate 1 PASS; Gitignored Local File) | Fresh | `canonical_ingestion` |
| `question_registry_v1` | `data/normalized/question_registry.json` | Agent 01 | Registered (13 Primary + Q14; Gitignored Local File) | Fresh | `canonical_intermediate` |
| `gpu_runtime_config_v1` | `runs/run_20261111_002/gpu_runtime_config.json` | Agent 07 | Registered (Live Blackwell Preflight Recorded; `derived_from_benchmark=false`) | Fresh | `canonical_intermediate` |
| `themes_codebook_v1` | `data/processed/themes_codebook.json` | Agent 02 | Not Yet Executed (Awaiting Live GPU Dual Coding) | Pending Colab GPU | `canonical_intermediate` |
| `candidate_options_v1` | `data/processed/candidate_options.json` | Agent 03 | **BLOCKED** (`AGENT_03_RELEASE = BLOCKED`) | Pending Release Gate | `canonical_intermediate` |
| `pref_matrix_v1` | `data/processed/preference_matrix.parquet` | Agent 04 | Contract Ready | Pending Run | `canonical_utility_input` |
| `pref_profiles_v1` | `data/processed/preference_profiles.json` | Agent 05 | Contract Ready | Pending Run | `canonical_intermediate` (Interpretive) |
| `voting_results_v1` | `data/processed/voting_results.json` | Agent 06 | Contract Ready | Pending Run | `canonical_decision` |
| `report_brief_v1` | `runs/run_20261111_002/reports/policy_brief.md` | Agent 08 | Presentation Only | Pending Run | `presentation_only` (Sink) |
| `review_report_v1` | `runs/run_20261111_002/integration_review_report.json` | Agent 09 | Contract Ready | Pending Run | `canonical_decision` |
| `manifest_v1` | `runs/run_20261111_002/manifest.json` | Agent 10 / Integration | Active (`4` registered artifacts) | Fresh | Authoritative Manifest |
| `run_card_v1` | `runs/run_20261111_002/RUN_CARD.md` | Agent 10 / Integration | Active | Fresh | Authoritative Run Provenance |
| `pipeline_qa_v1` | `runs/run_20261111_002/pipeline_execution.log` | Agent 11 | Active Evaluator (`src/pipeline/orchestrator.py`) | Ready to Persist on Colab/CI | `canonical_intermediate` |

---

## 5. Run Lifecycle & Historical Invalidation

- **`run_20261111_001`**: `INVALIDATED (Superseded)`. Used temporary scaffolding placeholder data during initial framework setup.
- **`run_20261111_002`**: `ACTIVE / GPU_PREFLIGHT_VERIFIED_AWAITING_DUAL_CODING`. Authentic `Anonymized_survey_data_2026.csv` ingested; Wave 2A + Agent 07 merged on `main`; live Colab RTX PRO 6000 Blackwell hardware preflight (`PASS`) & Gate 1/2 (`AUTHORIZED`) recorded; 5-stage live GPU benchmark and Coder A / Coder B qualitative coding `NOT_EXECUTED`; `AGENT_03_RELEASE = BLOCKED`.

---

## 6. Pending Milestones & Hard Release Gate Status

- [x] **Data & Question Registry Ingestion (Agent 01):** Gate 1 `PASS` (`154` normalized rows / `11` participants).
- [x] **Qualitative Coding Engine & Entrance Contracts (Agent 02):** `src/nlp/` merged on `main`, CPU tests `PASS`, Gate 2 `PASS`.
- [x] **Agent 07 GPU Runtime Persistence & Colab Hardware Preflight:** Merged via PR #4; Colab Blackwell `97887 MB` VRAM preflight `PASS` (`CONCURRENT_DUAL_SERVER`, `combined_required_mb = 49384`).
- [x] **Agent 11 Orchestration, Notebooks & Hard Release Gate (`agent/11-orchestration-recovery`):** `src/pipeline/orchestrator.py`, `notebooks/00_control_plane.ipynb`, `notebooks/04_validation.ipynb`, `tests/test_pipeline.py` implemented (`ISSUE-006` resolved).
- [ ] **5-Stage Live GPU Benchmark & Concurrent Dual-LLM Corpus Coding (Agents 02, 07 — `ISSUE-007`):** Execute `notebooks/07_gpu_runtime.ipynb` 5-stage live benchmark (`runs/<run_id>/gpu_runtime_benchmark.json`) and wire/run real Coder A (`DeepSeek-R1-Distill-Qwen-32B-AWQ`) + independent Coder B (`Mistral-Small-3.1-24B-Instruct-2503-AWQ`) corpus coding in `notebooks/01_gpu_coders.ipynb`.
- [ ] **Agent 03 Release Gate & Downstream Math/Voting/Reporting (Agents 03–06, 08, 09):** Blocked until all 13 requirements pass in `src/pipeline/orchestrator.py` and `ISSUE-005` is resolved for Agent 04.

**`GPU_PREFLIGHT_VERIFIED_AWAITING_DUAL_CODING`**: Hardware preflight and gates are verified, and Agent 11's evidence-derived release gate enforces `AGENT_03_RELEASE = BLOCKED` until real live-GPU benchmark and dual-coder qualitative outputs exist and pass validation checks A–H.
