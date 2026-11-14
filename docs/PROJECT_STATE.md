# Project State — HFG (Hybrid Feedback Governance)

> **Last Updated**: 2026-11-14
> **Maintained By**: Agent 10 (Memory & Artifacts) & Agent 00 (System Architect) | **Reconciled By**: Agent 11 (Orchestration & QA)
> **Active Architecture Version**: `v1.1.0` (12-Agent Architecture + 5-Stage Colab Topology)
> **Active Run ID**: `run_20261111_002`
> **Contract Schema Version**: `1.0.0` / `v1.1.0`
> **Readiness Status**: `PRODUCTION_DUAL_CODING_AND_INITIAL_RECONCILIATION_COMPLETE_ADR_0008_INTEGRATED` (`AGENT_04_RELEASE = BLOCKED` pending Wave 3B completion; clean Git checkouts report `AGENT_03_RELEASE = BLOCKED` when gitignored runtime outputs are not staged)

---

## 1. Global System Status (12-Agent Roster)

| Agent ID | Role / Specialization | Module Scope | Status | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Agent 00** | System Architect | `src/architecture/`, `src/contracts.py`, `schemas/interfaces.json` | `COMPLETE / ADR-0008 APPROVED` | Reconciled 20 interface contracts (`ADR-0005`–`ADR-0007`) and authored `ADR-0008` (PR `#12`, `cfe7c6f`), resolving `ISSUE-005` methodologically, defining the 7-level reconciliation hierarchy, Level 2 crosswalk taxonomy, `PreferenceUncertaintySet`, and 4-state `RobustParetoResult`. |
| **Agent 01** | Data & Question Registry | `src/ingest/`, `src/registry/` | `COMPLETE / INTEGRATED` | Integrated on `main` (PR `#2`): `154` normalized rows (`11` participants), orthogonal epistemic status vs usable preference (`136` usable, `10` blank, `6` non-substantive, `2` ambiguous, `0` imputed), `13` primary `QuestionSpec` + optional `Q14`, Gate 1 `PASS`. |
| **Agent 02** | Qualitative Coding | `src/nlp/` | `INTEGRATED / PRODUCTION CODING COMPLETED` | Integrated on `main` (PR `#2`); live `production` dual coding on `NVIDIA RTX PRO 6000 Blackwell` completed `136/136/0` usable responses + `18` non-preference cells preserved (`0` span offset/hash errors) across pinned `DeepSeek-R1-Distill-Qwen-32B-AWQ` + `Mistral-Small-3.1-24B-Instruct-2503-quantized.w4a16` (`PR #11`). Sensitive coder JSONs remain gitignored outside Git (`ISSUE-007` canonical sync open). |
| **Agent 03** | Evidence & Reconciliation | `src/evidence/` | `PRODUCTION RECONCILIATION COMPLETED; WAVE-3B SCHEMA ADAPTATION PENDING` | Merged `src/evidence/` (`PR #11`, `dbec14c`) and completed initial production reconciliation on staged Blackwell coder outputs (`101 -> 84` subtopics, `284` aligned preference cells, `219` options, `107` values, `13/13` QA checks `True`, `0` silent averages). **Wave 3B CPU-only `ADR-0008` schema adaptation** (`CrosswalkStatus`, `PreferenceUncertaintySet` in `src/evidence/reconciliation.py`) and canonical manifest registration remain pending before unlocking Agent 04. |
| **Agent 04** | Preference, Utility & Pareto | `src/preference/` | **`BLOCKED` (`AGENT_04_RELEASE = BLOCKED` PENDING WAVE 3B)** | `ISSUE-005` is methodologically **`RESOLVED`** by `ADR-0008` (`PR #12`) and enforced in shared contracts (`PR #13`), but `src/preference/` **must not start** until all 9 conditions of `_evaluate_agent_04_gate()` pass (Wave 3B Agent 03 CPU `ADR-0008` crosswalk/uncertainty-set emission + canonical manifest registration + staged verified production/benchmark artifacts). |
| **Agent 05** | Preference Profiles / Clustering | `src/clustering/` | `BLOCKED (UPSTREAM AGENT 04)` | Non-pruning missingness-masked clustering (`preference_profiles.json` / `ClusterResult`) contract locked; waiting on Agent 04 `PreferenceMatrix`. |
| **Agent 06** | Voting | `src/voting/` | `BLOCKED (UPSTREAM AGENT 04)` | Multi-rule social choice & conditional Baldwin/RRV contracts locked; waiting on Agent 04. |
| **Agent 07** | GPU Runtime | `src/runtime/`, `src/model_runtime.py` | `INTEGRATED / PRODUCTION INFERENCE EXECUTED; BENCHMARK SYNC PENDING` | Persisted via PR `#4` (`5f8c305`) and hardened across PRs `#6`–`#9` (live vLLM serving, JSON recovery ladder, immutable 40-char HF SHAs, `SEQUENTIAL_FALLBACK` default, `smoke_tiny`/`pilot_subset`/`production` isolation, durable WAL checkpoints); production coding verified in release bundle (`PR #11`), while `runs/run_20261111_002/gpu_runtime_benchmark.json` canonical sync remains open (`ISSUE-007`). |
| **Agent 08** | Report | `src/reporting/` | `STANDBY (UPSTREAM BLOCKED)` | Sink-only presentation report & evidence-bound `ReportClaim` templates configured; downstream of Agents 03–06. |
| **Agent 09** | Final Integration Reviewer | `src/review/` | `READY` | Independent audit, zero-hardcoding gate, `ADR-0008` V1–V8 rules, and Pareto non-exclusion protocols active (NOT orchestration). |
| **Agent 10** | Documentation, Memory & Artifacts | `src/artifact_registry.py`, `src/context_pack.py`, `src/freshness_checker.py` | `ACTIVE / GREEN` | Governance (`ADR-0007`), `README.md`, `docs/AUDIT_TRAIL.md`, `docs/REPRODUCIBILITY.md`, `docs/ARTIFACT_PROVENANCE.md` (`PR #10`), `ISSUE-005` + `docs/PROJECT_STATE.md` ADR-0008 sync, regenerated context packs `00`–`11`, and 9/9 freshness checks green. |
| **Agent 11** | Orchestration & QA | `src/pipeline/`, `src/hardcoding_scanner.py` | `INTEGRATED / ENFORCING AGENT 03 & AGENT 04 GATES` | Integrated `ADR-0008` into `src/contracts.py`, `schemas/interfaces.json`, `docs/DATA_CONTRACTS.md` and added 9-condition `Agent04ReleaseDecision` gate in `src/pipeline/orchestrator.py` (`PR #13`, `92386cd`); refreshed `docs/NOTEBOOK_INDEX.md` (`notebooks/HFG_live_execution.ipynb`) and verified `118/118` CPU tests (`1` local runtime skip). |

---

## 2. Completed Architectural & Memory Milestones

- [x] **Persistent Multi-Agent Memory Layer (`ADR-0001`–`ADR-0004`):** Established `src/artifact_registry.py`, `src/context_pack.py`, `src/freshness_checker.py`, context packs `agent_00`–`agent_11`, and passing pytest verification suite.
- [x] **12-Agent Reconciliation, Distributional `PreferenceCell` & Pareto Non-Exclusion (`ADR-0005` & `ADR-0006`):** Unified the 12-agent persistent memory architecture with the 5-notebook Google Colab execution pipeline (`notebooks/00_control_plane.ipynb` through `notebooks/04_validation.ipynb`).
- [x] **Git Collaboration & Shared-File Protocol (`ADR-0007`, PR `#1`):** Enforced branch isolation, handoff synchronization, and canonical vs task-local artifact discipline.
- [x] **Wave 2A, Agent 07 GPU Runtime Hardening & Orchestration Recovery (PRs `#2`, `#4`–`#9`):** Integrated Agent 01/02 refinements, live vLLM dual-coder runtime, 5-stage benchmark harness, JSON recovery ladder, isolated `smoke_tiny`/`pilot_subset`/`production` profiles, and Agent 11 `PipelineOrchestrator`.
- [x] **Audit Documentation & Live Colab Runner Tracking (PR `#10`, `ef716ac`):** Published `README.md`, `docs/AUDIT_TRAIL.md`, `docs/REPRODUCIBILITY.md`, `docs/ARTIFACT_PROVENANCE.md`, and tracked `notebooks/HFG_live_execution.ipynb`.
- [x] **Production Dual Coding & Initial Agent 03 Evidence Reconciliation (PR `#11`, `dbec14c`):** Verified live Blackwell `production` Coder A (`136/136/0`) and independent Coder B (`136/136/0`) outputs (`0` span errors) and implemented `src/evidence/` (`101 -> 84` canonical subtopics, `284` aligned preference cells, `219` options, `107` values, `0` silent averages), halting cleanly before Agent 04 due to missing disagreement/crosswalk policy.
- [x] **ADR-0008 Methodological Policy & Shared Contract Integration (PR `#12`, `cfe7c6f`; PR `#13`, `92386cd`):** Approved [`ADR-0008`](DECISIONS/ADR-0008-dual-coder-preference-reconciliation-and-uncertainty.md) resolving `ISSUE-005`, forbade `"CONFIDENCE_WEIGHTED_DISTRIBUTION"` and default point averaging, integrated uncertainty-set `PreferenceCell` / `CanonicalAlternativeCrosswalk` / 4-state `RobustParetoResult` into `src/contracts.py`, `schemas/interfaces.json`, and `docs/DATA_CONTRACTS.md`, and deployed the 9-condition `AGENT_04_RELEASE` gate in `src/pipeline/orchestrator.py`.

---

## 3. External Immutable Raw Source Verification

- **Canonical Path**: [`data/raw/survey_raw.csv`](data/raw/survey_raw.csv)
- **External Source**: `Anonymized_survey_data_2026.csv`
- **Authority**: `immutable_source` (external write-once source, NOT an analytically generated artifact)
- **Content Status**: Authentic stakeholder dataset, strictly write-locked.
- **Authoritative Cryptographic Hash (SHA-256)**:
  `56acded3e02be49be27d6b288fa2c43fcce68df24525113eba1b1161eec52a95`
- **Git Blob Object Hash (SHA-1, `git hash-object`)**:
  `eb526813aadcfab2b4b157e7b6513de50e6b3178`
- **Raw-SHA Discrepancy Resolution**:
  `docs/AGENT_HANDOFFS/agent_03_handoff.md` (`ff1a704`, line 120) contains an isolated transcription typo (`56acded3e8fe510085d38126fc93fc29a8f104e2396cf201be50016b1fc287da`). Direct inspection across Git history (`414aee5`..`HEAD`), `sha256sum data/raw/survey_raw.csv`, `runs/run_20261111_002/manifest.json`, and `src/ingest/ingestion.py` confirms `56acded3e02be49be27d6b288fa2c43fcce68df24525113eba1b1161eec52a95` as the sole canonical SHA-256 digest (see [`docs/AUDIT_TRAIL.md`](AUDIT_TRAIL.md)). Agent 03's historical handoff remains unmodified per immutable handoff rules.
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
| `question_registry_v1` | `data/normalized/question_registry.json` | Agent 01 | Registered (13 Primary + Q14) | Fresh | `canonical_intermediate` |
| `gpu_runtime_config_v1` | `runs/run_20261111_002/gpu_runtime_config.json` | Agent 07 | Registered (PR `#5` Blackwell preflight baseline; model pinning updated in PR `#8` `src/runtime/model_runtime.py`) | Integration Refresh Queued | `canonical_intermediate` |
| `coder_a_outputs` / `coder_b_outputs` | `data/processed/coder_a_outputs.json`, `data/processed/coder_b_outputs.json` | Agent 07 + Agent 02 | **Production Coding Completed** on Blackwell release bundle (`136/136/0`, `18` non-pref preserved); Gitignored / Untracked in Git | Untracked Local / Bundle | `canonical_intermediate` (Unreconciled) |
| `themes_codebook_v1` | `data/processed/themes_codebook.json` | Agent 02 / Agent 03 | Initial Task-Local Output Produced (`PR #11`, `84` subtopics); Wave-3B Sync & Manifest Registration Pending | Pending Integration | `canonical_intermediate` |
| `candidate_options_v1` | `data/processed/candidate_options.json` | Agent 03 | Initial Task-Local Output Produced (`PR #11`, `219` options); Wave-3B Sync & Manifest Registration Pending | Pending Integration | `canonical_intermediate` |
| `reconciled_evidence_v1` | `data/processed/reconciliation/reconciled_evidence.json` | Agent 03 | Initial Output Produced (`PR #11`, `284` cells); **Requires Wave-3B CPU `ADR-0008` Crosswalk & Uncertainty-Set Adaptation** | Adaptation Required | `canonical_intermediate` |
| `pref_matrix_v1` | `data/processed/preference_matrix.parquet` | Agent 04 | **`BLOCKED`** (`AGENT_04_RELEASE = BLOCKED`, ADR-0008 contract ready) | Pending Wave 3B | `canonical_utility_input` |
| `pref_profiles_v1` | `data/processed/preference_profiles.json` | Agent 05 | **`BLOCKED`** (Contract Ready) | Pending Run | `canonical_intermediate` (Interpretive) |
| `voting_results_v1` | `data/processed/voting_results.json` | Agent 06 | **`BLOCKED`** (Contract Ready) | Pending Run | `canonical_decision` |
| `report_brief_v1` | `runs/run_20261111_002/reports/policy_brief.md` | Agent 08 | Presentation Only (`BLOCKED`) | Pending Run | `presentation_only` (Sink) |
| `review_report_v1` | `runs/run_20261111_002/integration_review_report.json` | Agent 09 | Contract Ready (`BLOCKED`) | Pending Run | `canonical_decision` |
| `manifest_v1` | `runs/run_20261111_002/manifest.json` | Agent 10 / Integration | Active (`4` canonical PR `#5` entries; Wave-3B Agent 03 registration queued) | Fresh | Authoritative Manifest |
| `run_card_v1` | `runs/run_20261111_002/RUN_CARD.md` | Agent 10 / Integration | Active (PR `#5` snapshot; integration refresh queued post-Wave 3B) | Integration Refresh Queued | Authoritative Run Provenance |
| `pipeline_qa_v1` | `runs/run_20261111_002/pipeline_execution.log` | Agent 11 | Active Evaluator (`src/pipeline/orchestrator.py` — enforces Agent 03 + Agent 04 gates) | Evaluates on Demand | `canonical_intermediate` |

---

## 5. Run Lifecycle & Historical Invalidation

- **`run_20261111_001`**: `INVALIDATED (Superseded)`. Used temporary scaffolding placeholder data during initial framework setup.
- **`run_20261111_002`**: `ACTIVE / PRODUCTION_DUAL_CODING_AND_INITIAL_RECONCILIATION_COMPLETE_ADR_0008_INTEGRATED`. Authentic `Anonymized_survey_data_2026.csv` ingested; live Blackwell `production` dual coding (`136/136/0`) and initial Agent 03 evidence reconciliation (`PR #11`) completed on staged release-bundle outputs; [`ADR-0008`](DECISIONS/ADR-0008-dual-coder-preference-reconciliation-and-uncertainty.md) approved (`PR #12`) and enforced in shared contracts + 9-condition `Agent04ReleaseDecision` gate (`PR #13`); **`AGENT_04_RELEASE = BLOCKED`** pending Wave 3B completion (Agent 03 CPU-only ADR-0008 schema adaptation, runtime/benchmark sync, and canonical manifest registration).

---

## 6. Pending Milestones & Hard Release Gate Status

- [x] **Data & Question Registry Ingestion (Agent 01):** Gate 1 `PASS` (`154` normalized rows / `11` participants).
- [x] **Qualitative Coding Engine & Entrance Contracts (Agent 02):** `src/nlp/` merged on `main`, CPU tests `PASS`, Gate 2 `PASS`.
- [x] **Agent 07 GPU Runtime Hardening & Live Production Dual Coding (Agents 02, 07):** Merged via PRs `#4`, `#6`–`#9`; live Blackwell `production` Coder A + Coder B (`136/136/0`, `0` span errors) verified in Agent 03 release-bundle run (`PR #11`).
- [x] **Initial Agent 03 Evidence Ledger & Reconciliation Engine (Agent 03, PR `#11`):** Lossless span ledger and no-silent-averaging reconciliation engine implemented and executed on production outputs (`101 -> 84` subtopics, `284` cells, `219` options, `107` values).
- [x] **`ADR-0008` Methodological Approval & Shared-Contract Integration (Agents 00, 10, 11 — PRs `#12`, `#13`):** Methodologically resolved `ISSUE-005`, banned `"CONFIDENCE_WEIGHTED_DISTRIBUTION"`, updated `src/contracts.py` / `schemas/interfaces.json` / `docs/DATA_CONTRACTS.md`, added 9-condition `AGENT_04_RELEASE` gate, and synchronized `docs/OPEN_ISSUES.md` + `docs/PROJECT_STATE.md` + all 12 context packs.
- [ ] **Wave 3B — Agent 03 CPU `ADR-0008` Schema Adaptation (Agent 03 — Zero GPU Re-Coding):** Update `src/evidence/reconciliation.py` to emit Level 2 `CrosswalkStatus`, deterministic per-question `CanonicalAlternativeCrosswalk`, and `PreferenceUncertaintySet` on `data/processed/reconciliation/reconciled_evidence.json` (plus `tests/test_evidence.py`).
- [ ] **Wave 3B — Canonical Integration Registration & Benchmark Sync (Agent 11 — `ISSUE-007`):** Stage verified production & benchmark artifacts (`runs/run_20261111_002/gpu_runtime_benchmark.json`), validate merged hashes, refresh `runs/run_20261111_002/manifest.json` + `runs/run_20261111_002/RUN_CARD.md`, and unlock `AGENT_04_RELEASE = READY`.
- [ ] **Agent 04 Preference, Utility & Robust Pareto Execution and Downstream Stages (Agents 04–06, 08, 09):** Strictly **`BLOCKED`** until `_evaluate_agent_04_gate()` passes all 9 conditions (`AGENT_04_RELEASE = READY`).

**`AGENT_04_RELEASE = BLOCKED` Pending Wave 3B Completion**: Although production dual coding and initial Agent 03 reconciliation have completed (`PR #11`) and `ISSUE-005` is methodologically resolved by [`ADR-0008`](DECISIONS/ADR-0008-dual-coder-preference-reconciliation-and-uncertainty.md) (`PR #12`–`#13`), Agent 04 remains strictly gated until Wave 3B finishes Agent 03's CPU-only `ADR-0008` crosswalk/uncertainty-set emission, canonical manifest registration, and clean release-gate verification.
