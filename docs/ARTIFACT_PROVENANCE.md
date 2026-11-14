# Artifact Provenance Ledger — HFG (`run_20261111_002`)

> **Owner**: Agent 10 — Documentation, Memory & Artifacts  
> **Schemas Authority**: [`docs/DATA_CONTRACTS.md`](DATA_CONTRACTS.md) · [`src/contracts.py`](../src/contracts.py) · [`schemas/interfaces.json`](../schemas/interfaces.json)  
> **Manifest Authority**: [`runs/run_20261111_002/manifest.json`](../runs/run_20261111_002/manifest.json) (`ADR-0002`, `ADR-0004`, `ADR-0007`)  
> **Truthfulness Standard**: Artifacts marked **`PLANNED / BLOCKED`** or **`RUNTIME_NOT_EXECUTED`** do **not** yet exist on `origin/main` (`08d0096`).

---

## 1. End-to-End Provenance Chain

```text
data/raw/survey_raw.csv [immutable_source, SHA-256]
  ├─> data/normalized/answers_normalized.parquet [canonical_ingestion, gitignored, deterministic]
  ├─> data/normalized/question_registry.json [canonical_intermediate, Git-tracked]
  └─> runs/<run_id>/gpu_runtime_config.json [canonical_intermediate, Git-tracked]
        └─> runs/<run_id>/gpu_runtime_benchmark.json [live 5-stage GPU benchmark, NOT_EXECUTED]
              ├─> data/processed/profiles/smoke_tiny/... [non-eligible test, gitignored]
              ├─> data/processed/profiles/pilot_subset/... [non-eligible pilot, gitignored]
              └─> data/processed/coder_a_outputs.json + coder_b_outputs.json [gitignored, NOT_EXECUTED]
                    └─> Agent 03 Release Gate (13 checks + A-H) [CURRENTLY BLOCKED]
                          ├─> data/processed/themes_codebook.json [PLANNED / BLOCKED]
                          ├─> data/processed/candidate_options.json [PLANNED / BLOCKED]
                          └─> data/processed/preference_matrix.parquet [PLANNED / BLOCKED]
                                ├─> Utility & Pareto / Robust Pareto outputs [PLANNED / BLOCKED]
                                ├─> data/processed/preference_profiles.json [PLANNED / BLOCKED, Non-Pruning]
                                └─> data/processed/voting_results.json [PLANNED / BLOCKED]
                                      └─> runs/<run_id>/reports/policy_brief.md [Sink-Only, PLANNED]
                                            └─> runs/<run_id>/integration_review_report.json [PLANNED]
```

---

## 2. Complete Lifecycle Artifact Inventory

| Artifact | Producer | Upstream Inputs | Schema / Contract | Authority Level | Persistence Location | Privacy Status | Git Tracked? | Validation | Downstream Consumers | Status as of `08d0096` |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`data/raw/survey_raw.csv`** | External Stakeholder Survey | None | Raw survey baseline (`11` rows, `27` cols) | `immutable_source` | `data/raw/` | Anonymized CSV (`PARTICIPANT_001`–`011`) | **Yes** | SHA-256 `56acded3...` via `verify_gate_1` | Agent 01 | **Exists (Valid, Immutable)** |
| **`data/normalized/question_registry.json`** | Agent 01 ([`src/registry/question_registry.py`](../src/registry/question_registry.py)) | `survey_raw.csv`, `answers_normalized.parquet` | `QuestionSpec` (`v1.1.0`) | `canonical_intermediate` | `data/normalized/` | Question metadata only (**no** participant text) | **Yes** | Gate 1 (`13` primary `Q01`–`Q13` + `Q14`) | Agents 02, 03, 04, 11 | **Exists (Registered)** |
| **`data/normalized/answers_normalized.parquet`** (+ `.json`) | Agent 01 ([`src/ingest/ingestion.py`](../src/ingest/ingestion.py)) | `survey_raw.csv` | Normalized response table (`ResponseEpistemicStatus`, `MissingnessState`) | `canonical_ingestion` | Local `data/normalized/` (regenerable) | **Sensitive normalized participant text** | **No** (`.gitignore`) | Gate 1: `154` cells, `136` usable, `0` imputed | Agents 02, 03, 04, 11 | **Regenerable Locally (Gate 1 PASS)** |
| **`runs/<run_id>/gpu_runtime_config.json`** | Agent 07 ([`src/runtime/model_runtime.py`](../src/runtime/model_runtime.py)) | Hardware preflight / runtime probe | `GPURuntimeConfig` (`v1.1.0`) | `canonical_intermediate` | `runs/<run_id>/` | Non-sensitive hardware & config metadata | **Yes** | Pydantic validation + family diversity check | Agents 02, 07, 11 | **Exists (PR #5 Blackwell preflight; `derived_from_benchmark=false`)** |
| **`runs/<run_id>/gpu_runtime_benchmark.json`** | Agent 07 (`run_runtime_benchmark_suite`) | `gpu_runtime_config.json`, live GPU + HF models | 5-stage benchmark report (`v1.1.0`) | `canonical_intermediate` | `runs/<run_id>/` (or runtime persistence) | Hardware/latency/rate telemetry only | Optional safe metadata | `benchmark_supports_concurrent_mode` + Orchestrator Gate #4 | Agent 07 (`select_safe_execution_mode`), Agent 11 | **`RUNTIME_NOT_EXECUTED`** |
| **WAL Checkpoints (`smoke_tiny` / `pilot_subset` / `production`)** | Agent 07 (`AtomicQuestionCheckpointStore`) | Prompt inputs, model outputs | `QuestionCheckpointRecord` | `runtime_checkpoint` (task/session durability) | `.checkpoints/gpu_coder_wal/<run_id>/<profile>/` or `$HFG_CHECKPOINT_ROOT` | May store response payloads / diagnostics | **No** (`.gitignore` / Drive) | Profile, model repo, SHA revision, prompt/source hash & `profile_config_hash` | Resume interrupted `dual_coder_runner` | **No live production checkpoints in Git** |
| **`smoke_tiny` Checkpoints & Outputs** | Agent 07 ([`src/runtime/dual_coder_runner.py`](../src/runtime/dual_coder_runner.py)) | Compact 2-row subset (`SMOKE_BOUNDED_LIMITS`) | Smoke-bounded coder JSON (`execution_profile=smoke_tiny`) | Non-production test output (`synthetic_or_test_execution=True`) | `data/processed/profiles/smoke_tiny/` + `$HFG_CHECKPOINT_ROOT/.../smoke_tiny/` | Contains coded spans for 2 subset rows | **No** (`.gitignore`) | `validate_smoke_compact_bounds` + A–H checks | Diagnostics only (**rejected by Agent 03 gate**) | **`RUNTIME_NOT_EXECUTED`** (unit-tested with mocks) |
| **`pilot_subset` Checkpoints & Outputs** | Agent 07 ([`src/runtime/dual_coder_runner.py`](../src/runtime/dual_coder_runner.py)) | Edge-case coverage subset + `PARTICIPANT_002/Q06` | `LLMQuestionCodingResponse` (`execution_profile=pilot_subset`) | Non-production pilot output (`production_eligible=False`) | `data/processed/profiles/pilot_subset/` + `$HFG_CHECKPOINT_ROOT/.../pilot_subset/` | Contains participant spans & metadata | **No** (`.gitignore`) | `validate_dual_coder_outputs` (A–H) | Diagnostics & prompt/timeout tuning (**rejected by Agent 03 gate**) | **`RUNTIME_NOT_EXECUTED`** |
| **`data/processed/coder_a_outputs.json` & `data/processed/coder_b_outputs.json`** | Agent 07 + Agent 02 (`dual_coder_runner`) | `answers_normalized.parquet`, `question_registry.json`, live vLLM servers | Unreconciled Phase 1/2 payloads (`execution_profile=production`, `production_eligible=True`) | `canonical_intermediate` (unreconciled) | Local/external `data/processed/` | **Sensitive participant span outputs** | **No** (`.gitignore`) | Orchestrator A–H + checklist #5–#11 | Agent 03 Reconciliation, Agent 11 | **`RUNTIME_NOT_EXECUTED` (`BLOCKED`)** |
| **`data/processed/themes_codebook.json`** | Agent 02 / Agent 03 | Independent `coder_a` & `coder_b` outputs | `CanonicalSubtopic`, `ValueAssignment` | `canonical_intermediate` | `data/processed/` | Sanitized codebook metadata (verify zero leaked PII) | Contract planned | Schema + `FreshnessChecker` evidence ID check | Agents 03, 08 | **`PLANNED / BLOCKED`** |
| **`data/processed/candidate_options.json`** | Agent 03 (`src/evidence/`) | Reconciled `CodingResult`, `EvidenceSpan`, `themes_codebook.json` | `FeasibleAlternative`, `EvidenceSpan`, `CodingResult` | `canonical_intermediate` | `data/processed/` | Span-referenced options | Contract planned | Schema + verbatim offset validation | Agents 04, 05, 06 | **`PLANNED / BLOCKED`** (`ISSUE-007`) |
| **`data/processed/preference_matrix.parquet`** | Agent 04 (`src/preference/`) | `answers_normalized.parquet`, `candidate_options.json` | `PreferenceCell` (`alternative_probabilities` + orthogonal metadata) | `canonical_utility_input` | `data/processed/` | Participant-level matrix | Planned (evaluate Git exclusion if participant text present) | $\sum p_k = 1.0 \pm 10^{-4}$; missingness non-imputation | Agents 04 (Utility/Pareto), 05, 06 | **`PLANNED / BLOCKED`** (`ISSUE-005`, `ISSUE-007`) |
| **Utility, Constraint-Only Solutions & Pareto Frontiers** | Agent 04 (`src/preference/`) | `preference_matrix.parquet` only (for utility); structural constraints only (for pruning) | `ParticipantUtility`, `GovernanceSolution`, `ParetoResult`, `RobustParetoResult` | `canonical_intermediate` / `canonical_decision` | `data/processed/` & `runs/<run_id>/sensitivity_metrics.json` | Aggregated solution evaluations | Planned | Exclusive utility provenance; **Pareto Non-Exclusion invariant** | Agents 08, 09 | **`PLANNED / BLOCKED`** |
| **`data/processed/preference_profiles.json`** | Agent 05 (`src/clustering/`) | `preference_matrix.parquet` | `ClusterResult` | `canonical_intermediate` (**Interpretive Only**) | `data/processed/` | Anonymized profile clusters | Planned | Missingness-masked clustering, data-driven $k^*$ | Agents 08, 09 (**never** Agent 04 pruning) | **`PLANNED / BLOCKED`** |
| **`data/processed/voting_results.json`** | Agent 06 (`src/voting/`) | `preference_matrix.parquet`, `candidate_options.json` (+ conditional ballots) | `BaldwinResult`, `RRVResult`, Borda/Condorcet/Minimax | `canonical_decision` | `data/processed/` | Aggregated voting tallies | Planned | Conditional Baldwin/RRV guard (`SKIPPED_NO_VALID_INPUT` if no ballots) | Agents 08, 09 | **`PLANNED / BLOCKED`** |
| **`runs/<run_id>/reports/policy_brief.md`** | Agent 08 (`src/reporting/`) | Reconciled evidence, Pareto, profiles, voting | `ReportClaim` | **`presentation_only` (Sink Only)** | `runs/<run_id>/reports/` | Public-safe sanitized policy summary | Planned deliverable | Zero-leakage check; every claim linked to `evidence_ids` + `ArtifactRecord` | Stakeholders, Agent 09 (**never** upstream pipeline) | **`PLANNED / BLOCKED`** |
| **`runs/<run_id>/integration_review_report.json`** | Agent 09 (`src/review/`) | All canonical artifacts & pipeline traces | `IntegrationReviewReport` | `canonical_decision` | `runs/<run_id>/` | Audit findings only | Planned | Independent end-to-end invariant check | Agents 10, 11 | **`PLANNED / BLOCKED`** |
| **`runs/<run_id>/manifest.json`** | Agent 10 / Agent 11 (Integration) | Verified `ArtifactRecord` hashes & commits | `ArtifactRegistry` manifest (`v1.0.0`) | **Authoritative Manifest** | `runs/<run_id>/` | Hashes & paths only | **Yes** | `FreshnessChecker` checks 7–9 | All agents | **Exists (`4` canonical entries from PR #5)** |
| **`runs/<run_id>/RUN_CARD.md`** | Agent 10 / Integration | Manifest + gate telemetry | Authoritative Run Provenance | **Authoritative Provenance** | `runs/<run_id>/` | Non-sensitive operational summary | **Yes** | Reviewed on integration | Researchers, auditors | **Exists (PR #5 snapshot; PRs #6–#9 delta noted in `docs/AUDIT_TRAIL.md`)** |
| **`runs/<run_id>/pipeline_execution.log`** | Agent 11 ([`src/pipeline/orchestrator.py`](../src/pipeline/orchestrator.py)) | Live filesystem, gates, scanner, freshness | `PipelineEvaluationReport` JSON | `canonical_intermediate` | `runs/<run_id>/` | Gate/check summaries only | **Yes** | Written via `--write-log` on demand | Agents 09, 10, auditors | **Exists (records `AGENT_03_RELEASE = BLOCKED`)** |

---

## 3. Provenance & Privacy Governance Rules

1. **Canonical vs. Task-Local Artifact Scope (`ADR-0007`)**: Implementation branches may produce local test outputs or profile diagnostics, but only the **integration process** publishes canonical production registrations in `runs/<run_id>/manifest.json` after verifying merged code commits and source SHA-256 hashes.
2. **Orthogonality in Preference Provenance (`ADR-0005`)**: No downstream artifact may collapse `semantic_importance`, `coder_confidence`, `coder_agreement`, or missingness flags into choice probabilities (`alternative_probabilities`).
3. **Zero PII & Zero Raw Quote Leakage in Tracked Logs**: Error diagnostics written during JSON recovery (`failure_diagnostics.jsonl` / `failed_items/`) explicitly strip `forbidden_raw_keys` and redact input response text (`input_value = [REDACTED]`).
4. **Sink-Only Reporting**: Presentation artifacts (`runs/<run_id>/reports/*.md`) cannot feed back into analytical computation or manifest hash inputs for upstream stages.
