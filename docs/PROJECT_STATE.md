# Project State — HFG (Hybrid Feedback Governance)

> **Last Updated**: 2026-11-14
> **Maintained By**: Agent 10 (Memory & Artifacts) & Agent 00 (System Architect) | **Reconciled By**: Agent 11 (Orchestration & QA)
> **Active Architecture Version**: `v1.1.0` (12-Agent Architecture + 5-Stage Colab Topology)
> **Active Run ID**: `run_20261111_002`
> **Contract Schema Version**: `1.0.0` / `v1.1.0`
> **Readiness Status**: `FRONTIER_A_FROZEN_ADR_0009_SENSITIVITY_PENDING` (`AGENT_03_RELEASE = READY`, `AGENT_04_RELEASE = READY`, `AGENT_05_RELEASE = READY`, `AGENT_06_RELEASE = READY` for `FRONTIER_A`; **`AGENT_08_TECHNICAL_RELEASE = READY`** · **`AGENT_08_REPORTING_STATUS = HELD_FOR_RESOURCE_REGIME_SENSITIVITY`**; `NEW_LLM_CODING_REQUIRED = NO`; clean Git checkouts without staged gitignored runtime payloads evaluate local gates `BLOCKED`)

---

## 1. Global System Status (12-Agent Roster)

| Agent ID | Role / Specialization | Module Scope | Status | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Agent 00** | System Architect | `src/architecture/`, `src/contracts.py`, `schemas/interfaces.json` | `COMPLETE / ADR-0008 & ADR-0009 APPROVED` | Authored `ADR-0008` (`PR #12`) and [`ADR-0009`](DECISIONS/ADR-0009-resource-good-regimes-and-counterfactual-institutional-design.md) (`PR #23`, `6508ded`), freezing `FRONTIER_A = OBSERVED_DESIGN_FRONTIER`, defining `FRONTIER_B = RESOURCE_REGIME_EXPANDED_FRONTIER`, subtopic-level `RESOURCE_ELIGIBILITY`, 10-field `CLUB_GOOD` contract, 3-way provenance boundary, and `AGENT_08_REPORTING_STATUS = HELD_FOR_RESOURCE_REGIME_SENSITIVITY`. |
| **Agent 01** | Data & Question Registry | `src/ingest/`, `src/registry/` | `COMPLETE / INTEGRATED` | Integrated on `main` (`PR #2`): `154` normalized rows (`11` participants), `136` `observed_usable`, `10` `missing_raw_blank`, `6` `missing_non_substantive`, `2` `ambiguous`, `0` imputed, `13` primary `QuestionSpec` (`Q01`–`Q13`) + contextual `Q14`, Gate 1 `PASS`. |
| **Agent 02** | Qualitative Coding | `src/nlp/` | `COMPLETE / PRODUCTION CODING COMPLETED (NEW_LLM_CODING_REQUIRED = NO)` | Integrated (`PR #2`); live `production` Blackwell dual coding verified (`136/136/0`, `18` non-preference cells preserved, `0` span errors, Checks A–H `8/8 PASS`). Under `ADR-0009`, **`NEW_LLM_CODING_REQUIRED = NO`**: no additional LLM coding run is permitted or required. |
| **Agent 03** | Evidence & Reconciliation | `src/evidence/` | `COMPLETE / PRODUCTION RECONCILIATION COMPLETED & ADR-0008 INTEGRATED` | Initial reconciliation (`PR #11`) + CPU-only `ADR-0008` crosswalk/uncertainty adaptation (`PR #15`, `baef68b`) integrated (`PR #17`): `101 -> 84` subtopics, `284` aligned records, `185` options, `107` values, `17` crosswalk rules, `16/16` QA checks `PASS`, `0` silent averages. Under `ADR-0009`, only optional deterministic CPU `RESOURCE_ELIGIBILITY` subtopic tagging applies if requested by Agent 04 (`NEW_LLM_CODING_REQUIRED = NO`). |
| **Agent 04** | Preference, Utility & Pareto | `src/preference/` | `FRONTIER_A COMPLETE (FROZEN); FRONTIER_B COUNTERFACTUAL FOLLOW-UP PENDING` | Implemented in `PR #18` (`155f843`) and canonically registered in `PR #19` (`0f03f33`): `FRONTIER_A = OBSERVED_DESIGN_FRONTIER` produced **`543`** feasible `Q01`–`Q13` packages, **`326`** expected-reference nondominated, and 4-state `RobustParetoResult` (**`10`** `ROBUSTLY_NONDOMINATED`, **`248`** `CONDITIONALLY_NONDOMINATED` with **`102`** at `p_nd >= 0.95`, **`285`** `UNRESOLVED_DUE_TO_CODING_UNCERTAINTY`, **`0`** `ROBUSTLY_DOMINATED`; `11/11` QA checks). **`FRONTIER_A` is strictly immutable**; additive `FRONTIER_B` counterfactual sensitivity (`src.preference.resource_regimes`) awaits Agent 11 contract integration (`ISSUE-008`). |
| **Agent 05** | Preference Profiles / Clustering | `src/clustering/` | `COMPLETE / INTEGRATED (UNCHANGED UNDER ADR-0009)` | Implemented in `PR #21` (`79c0349`) and integrated in `PR #22` (`ceb3004`): **`NO_STABLE_CLUSTER_STRUCTURE`** (`selected_k = 1`, `PROFILE_01`; exploratory `Rep C` `8` vs `3` non-canonical only; `11/11` QA checks `PASS`, `0` Pareto/voting interference). No changes required under `ADR-0009`. Note: `pyproject.toml` omits `numpy`/`scipy`/`scikit-learn` (`ISSUE-009`). |
| **Agent 06** | Voting | `src/voting/` | `COMPLETE / INTEGRATED (UNCHANGED UNDER ADR-0009)` | Implemented in `PR #20` (`3119baf`) and integrated in `PR #22` (`ceb3004`): **`NO_ROBUST_SINGLE_WINNER`**, **`BALDWIN = NOT_APPLICABLE`** (`SKIPPED_NO_VALID_INPUT`), **`RRV = NOT_APPLICABLE`** (`SKIPPED_NO_VALID_INPUT`), `77.8%` MC Condorcet cycles, `N = 11` LOO flips (`6/11` Borda, `9/11` Minimax), `12/12` QA checks `PASS`. No changes required under `ADR-0009`. |
| **Agent 07** | GPU Runtime | `src/runtime/`, `src/model_runtime.py` | `COMPLETE / INTEGRATED (NEW_LLM_CODING_REQUIRED = NO)` | Live vLLM serving, JSON recovery ladder, isolated `smoke_tiny`/`pilot_subset`/`production` profiles (`PR #4`–`#9`), live Blackwell benchmark (`gpu_runtime_benchmark.json` SHA-256 `bc8e6d22...`, `EXECUTED_LIVE_GPU`), and `136/136/0` production coding completed (`PR #17`). No further GPU coding required (`NEW_LLM_CODING_REQUIRED = NO`). |
| **Agent 08** | Report | `src/reporting/` | **`AGENT_08_TECHNICAL_RELEASE = READY` / `AGENT_08_REPORTING_STATUS = HELD_FOR_RESOURCE_REGIME_SENSITIVITY`** | Agents 03–06 outputs verified and frozen into private Agent 08 bundle (`a84df6ff...`, `PR #22`, `40/40` packaged). Reporting is **deliberately held** (not a pipeline failure) under `ADR-0009` (`ISSUE-008`) to evaluate counterfactual resource-regime sensitivity (`FRONTIER_B`) and enforce dual-frontier reporting separation. |
| **Agent 09** | Final Integration Reviewer | `src/review/` | `READY` | Independent audit scope expanded with `ADR-0009` verification gates `VG-01`–`VG-09` alongside `ADR-0008` V1–V8 and Pareto non-exclusion invariants (NOT orchestration). |
| **Agent 10** | Documentation, Memory & Artifacts | `src/artifact_registry.py`, `src/context_pack.py`, `src/freshness_checker.py` | `ACTIVE / GREEN` | Synchronized `docs/PROJECT_STATE.md`, `docs/OPEN_ISSUES.md`, `README.md`, `docs/AUDIT_TRAIL.md`, `docs/ARTIFACT_PROVENANCE.md`, `docs/REPRODUCIBILITY.md`, and all 12 context packs (`agent_00`–`agent_11`) to `PR #23` / `ADR-0009` (`9/9` freshness PASS). |
| **Agent 11** | Orchestration & QA | `src/pipeline/`, `src/hardcoding_scanner.py` | `FRONTIER_A INTEGRATED (39 MANIFEST ARTIFACTS); ADR-0009 & DEPENDENCY INTEGRATION PENDING` | Integrated Wave 3B, Agent 04, and Agents 05+06 across `PR #16`, `#17`, `#19`, and `#22` (`39` registered entries in `runs/run_20261111_002/manifest.json` + `RUN_CARD.md`). Next owns `ADR-0009` contract integration (`src/contracts.py`, `schemas/interfaces.json`, `docs/DATA_CONTRACTS.md`), orchestrator `AGENT_08_TECHNICAL_RELEASE` vs `AGENT_08_REPORTING_STATUS` split (`ISSUE-008`), and `pyproject.toml` dependency sync for `numpy`/`scipy`/`scikit-learn` (`ISSUE-009`). |

---

## 2. Frozen `FRONTIER_A` Baseline & `ADR-0009` `FRONTIER_B` Sensitivity Layer

### 2.1. Frozen Evidence-Grounded Baseline (`FRONTIER_A = OBSERVED_DESIGN_FRONTIER`)
`FRONTIER_A` (`OBSERVED_DESIGN_FRONTIER`) is **complete, canonically registered (`39` artifacts in `runs/run_20261111_002/manifest.json`), and strictly immutable**. Downstream `ADR-0009` sensitivity analysis MUST NOT alter or overwrite any `FRONTIER_A` output:

- **Feasible Solution Space**: **`543`** strictly constraint-feasible `Q01`–`Q13` governance packages (`161` `FeasibleAlternative`, `112` constraint-pruned packages / `113` constraint exclusions, `0` prohibited cluster/value/disagreement prunings, `0` `Q14` inclusions).
- **Exact Baseline Pareto**: **`326`** expected-reference nondominated solutions (`5,973` `ParticipantUtility` records across `11` participants, `0` non-null `point_utility`).
- **4-State `RobustParetoResult`** (`1,000` Monte Carlo draws, `random_seed = 42`, `veto_threshold = 0.35`):
  - **`10`** `ROBUSTLY_NONDOMINATED` (`SOL_0003`, `SOL_0009`, `SOL_0212`, `SOL_0416`, `SOL_0419`, `SOL_0422`, `SOL_0423`, `SOL_0424`, `SOL_0440`, `SOL_0522`)
  - **`248`** `CONDITIONALLY_NONDOMINATED`
  - **`285`** `UNRESOLVED_DUE_TO_CODING_UNCERTAINTY`
  - **`0`** `ROBUSTLY_DOMINATED`
  - **`102`** solutions with nondominated inclusion probability `p_nd >= 0.95`
- **Clustering & Social Choice Conclusions**:
  - **`NO_STABLE_CLUSTER_STRUCTURE`** (`selected_k = 1`, `PROFILE_01`; exploratory `Rep C` `8` vs `3` non-canonical only)
  - **`NO_ROBUST_SINGLE_WINNER`** (`77.8%` MC Condorcet cycle rate; `N = 11` LOO sensitivity flips `6/11` Borda and `9/11` Minimax)
  - **`BALDWIN = NOT_APPLICABLE`** (`SKIPPED_NO_VALID_INPUT`)
  - **`RRV = NOT_APPLICABLE`** (`SKIPPED_NO_VALID_INPUT`)
- **Authoritative Scientific Interpretation**: *"A robust Pareto core exists, but no single collective-choice winner is stable across the admissible uncertainty scenarios."* Never report that "no solution was found."

### 2.2. Counterfactual Institutional-Design Layer (`FRONTIER_B = RESOURCE_REGIME_EXPANDED_FRONTIER`)
Approved in [`ADR-0009`](DECISIONS/ADR-0009-resource-good-regimes-and-counterfactual-institutional-design.md) (`PR #23`, `6508ded`):

- **Separate Counterfactual Layer**: `FRONTIER_B` (`RESOURCE_REGIME_EXPANDED_FRONTIER`) is a **separate counterfactual institutional-design sensitivity analysis**, NOT a replacement for `FRONTIER_A`. It tests institutionally coherent regimes—`PRIVATE_GOOD`, `CLUB_GOOD`, `COMMON_POOL_RESOURCE`, `PUBLIC_GOOD`, and `HYBRID`—strictly for `ADR-0009`-eligible resource subtopics (`VG-01`–`VG-09`, questions `Q-A`–`Q-H`), introducing the fifth robustness state `UNRESOLVED_DUE_TO_COUNTERFACTUAL_UTILITY` distinct from `UNRESOLVED_DUE_TO_CODING_UNCERTAINTY`.
- **Subtopic-Level `RESOURCE_ELIGIBILITY`** (never whole-question automatic goods; perception/opinion/process/authority topics are `INELIGIBLE`):
  - **`Q10`**: funding/allocation resources (`Q10_allocation_mechanism_core_funding` — `ELIGIBLE`)
  - **`Q11`**: overhead/resource-pooling mechanisms (`Q11_overhead_allocation_mechanism*` / reversal — `ELIGIBLE`; negotiation/transparency process facets — `INELIGIBLE`)
  - **`Q12`**: bonus/investment pools (`Q12_allocation_primes_depot`, bonus allocation/purpose — `ELIGIBLE`; `Q12_socle_adequacy_B_ONLY` adequacy perception — `INELIGIBLE`)
  - **`Q09`**: risk/resource-pooling facets (`Q09_financial_responsibility_regime` — `ELIGIBLE` with statutory solvency/risk-pooling caveat; diagnostic/burnout facets — `INELIGIBLE`)
  - **`Q06`**: selected financial facets only (`Q06_financial_responsibility_B_ONLY`, `Q06_financial_responsibility_regime_A_ONLY` under double-count guard; scenario evaluation/communication/autonomy facets — `INELIGIBLE`)
  - **`Q08`**: **`CONDITIONAL_RESOURCE_ONLY`** (`Q08_hr_management_level` only where evidence concerns allocable HR/administrative support capacity in segregated Tier `Q-G`, not general HR hiring authority; delegation/clarity diagnostic facets — `INELIGIBLE`)
  - **`Q01`–`Q05`**, **`Q07`** *(all facets—governance signing/recruitment authority, despite `ENABLED` in `question_registry.json`)*, **`Q13`**, **`Q14`**: **`INELIGIBLE`**
- **Operational `CLUB_GOOD` Contract** (bare `"club"` / `"voluntary_pooling"` labels rejected): Requires `membership_mode = VOLUNTARY`, explicit `member_contribution_rule`, exact `non_member_compulsory_contribution = 0.0`, explicit `member_priority` (`member_access >= non_member_access`), explicit `non_member_access` in `{NONE, RESIDUAL_CAPACITY, PAY_PER_USE, OTHER_EXPLICIT}`, `exit_policy` (`ALLOWED | CONSTRAINED`), `capacity_congestion_rule` (mandatory when `RIVAL` or `CONGESTIBLE`), `governance_rule`, and `pricing_contribution_rule`.
- **Three-Way Evidence Provenance Boundary**: Strictly separates `OBSERVED_RESPONDENT_PREFERENCE`, `INSTITUTIONALLY_DERIVED_MECHANISM`, and `COUNTERFACTUAL_PREFERENCE_ASSUMPTION`. Refusal to pay (*"I do not want compulsory payment"*) **never** implies *"I prefer club provision"* without direct `EvidenceSpan` support: `non_member_compulsory_contribution = 0.0` is an `INSTITUTIONALLY_DERIVED_MECHANISM`, whereas club preference remains counterfactual unless evidenced (`UNRESOLVED_DUE_TO_COUNTERFACTUAL_UTILITY`, zero arbitrary point utility).
- **Zero Re-Coding & Agent 08 Hold**: **`NEW_LLM_CODING_REQUIRED = NO`**. Agent 08 status is explicitly split into **`AGENT_08_TECHNICAL_RELEASE = READY`** and **`AGENT_08_REPORTING_STATUS = HELD_FOR_RESOURCE_REGIME_SENSITIVITY`** (deliberately paused, not failed).

---

## 3. Completed Architectural & Analytical Milestones

- [x] **Persistent Multi-Agent Memory Layer (`ADR-0001`–`ADR-0004`):** Established `src/artifact_registry.py`, `src/context_pack.py`, `src/freshness_checker.py`, context packs `agent_00`–`agent_11`, and passing verification tests.
- [x] **12-Agent Architecture, Contracts & Git Collaboration (`ADR-0005`–`ADR-0007`, PR `#1`):** Unified domain contracts across 12 agents and enforced isolated task-branch collaboration.
- [x] **Wave 2A, GPU Runtime Hardening & Orchestration Recovery (PRs `#2`, `#4`–`#10`):** Integrated Agent 01/02 refinements, live vLLM runtime, JSON recovery ladder, isolated execution profiles (`smoke_tiny`, `pilot_subset`, `production`), durable WAL checkpoints, and initial audit documentation.
- [x] **Production Dual Coding, `ADR-0008` Reconciliation & Wave-3B Release (PRs `#11`–`#17`):** Verified Blackwell `production` dual coding (`136/136/0`), live benchmark (`bc8e6d22...`, `EXECUTED_LIVE_GPU`), [`ADR-0008`](DECISIONS/ADR-0008-dual-coder-preference-reconciliation-and-uncertainty.md) (`ISSUE-005` `RESOLVED`), CPU uncertainty-set reconciliation (`284` records, `17` crosswalk rules), and `AGENT_04_RELEASE = READY`.
- [x] **`FRONTIER_A` Completion & Integration (Agents 04, 05, 06 & 11 — PRs `#18`–`#22`):** Completed and integrated `PreferenceMatrix`, `543`-package `SolutionSpace`, `326`-nondominated exact Pareto, `10/248/285/0` 4-state `RobustParetoResult`, `NO_STABLE_CLUSTER_STRUCTURE` ex-post clustering, `NO_ROBUST_SINGLE_WINNER` / `BALDWIN = NOT_APPLICABLE` / `RRV = NOT_APPLICABLE` voting, `39` canonical `manifest.json` registrations, `RUN_CARD.md`, and Agent 08 technical release (`a84df6ff...`).
- [x] **`ADR-0009` Architectural Approval (Agent 00 — PR `#23`, `6508ded`):** Froze `FRONTIER_A` (`OBSERVED_DESIGN_FRONTIER`), defined `FRONTIER_B` counterfactual resource-regime sensitivity, subtopic `RESOURCE_ELIGIBILITY`, 10-field `CLUB_GOOD` contract, 3-way provenance separation, `NEW_LLM_CODING_REQUIRED = NO`, and Agent 08 reporting hold (`HELD_FOR_RESOURCE_REGIME_SENSITIVITY`).

---

## 4. External Immutable Raw Source Verification

- **Canonical Path**: [`data/raw/survey_raw.csv`](data/raw/survey_raw.csv)
- **External Source**: `Anonymized_survey_data_2026.csv` (`immutable_source`, write-locked; `11` data rows, `12` lines, `27` cols)
- **Authoritative Cryptographic Hash (SHA-256)**: `56acded3e02be49be27d6b288fa2c43fcce68df24525113eba1b1161eec52a95`
- **Git Blob Object Hash (SHA-1, `git hash-object`)**: `eb526813aadcfab2b4b157e7b6513de50e6b3178`
- **Raw-SHA Discrepancy Resolution**: `docs/AGENT_HANDOFFS/agent_03_handoff.md` (`ff1a704`, line 120) contains an isolated transcription typo (`56acded3e8fe510085d38126fc93fc29a8f104e2396cf201be50016b1fc287da`). Direct inspection confirms `56acded3e02be49be27d6b288fa2c43fcce68df24525113eba1b1161eec52a95` as the sole canonical SHA-256 digest (immutable historical handoff untouched).
- **Ingestion Breakdown**: `154` normalized cells (`136` `observed_usable`, `10` `missing_raw_blank`, `6` `missing_non_substantive`, `2` `ambiguous`, `0` imputed; `Q01`–`Q13` primary + optional `Q14`).

---

## 5. Registered Artifacts Summary (`run_20261111_002` — `39` Canonical Manifest Entries)

| Layer / Scope | Registered Artifact IDs (`runs/run_20261111_002/manifest.json`) | Producing Agent | Status & Privacy Boundary | Authority Level |
| :--- | :--- | :--- | :--- | :--- |
| **Raw Source** | `raw_survey_v1` (`data/raw/survey_raw.csv`) | External | Tracked & Frozen (`SHA-256: 56acded3...`) | `immutable_source` |
| **Ingestion & Registry** | `norm_answers_v1`, `question_registry_v1` | Agent 01 | Registered; `answers_normalized.*` gitignored & deterministically regenerable | `canonical_ingestion` / `canonical_intermediate` |
| **GPU Runtime & Production Coding** | `gpu_runtime_config_v1` *(benchmark `bc8e6d22...` & coder outputs verified in `RUN_CARD.md`)* | Agent 07 / 02 | Completed (`136/136/0`, `NEW_LLM_CODING_REQUIRED = NO`); sensitive coder payloads gitignored | `canonical_intermediate` |
| **Evidence & Reconciliation** | `themes_codebook_v1`, `candidate_options_v1`, `reconciled_evidence_v1`, `subtopic_alignment_v1`, `reconciled_values_v1`, `coder_agreement_stats_v1`, `unresolved_cases_registry_v1`, `alternative_crosswalk_summary_v1`, `reconciliation_qa_report_v1` | Agent 03 | Registered (`9` entries, `PR #17`); payloads in bundle/local storage (gitignored) | `canonical_intermediate` |
| **`FRONTIER_A` Preference & Pareto** | `pareto_mc_config_v1`, `preference_matrix_v1`, `preference_matrix_json_v1`, `feasible_alternatives_v1`, `participant_utility_v1`, `pareto_results_v1`, `robust_pareto_results_v1`, `pareto_sensitivity_v1`, `preference_uncertainty_summary_v1`, `agent_04_qa_report_v1` | Agent 04 | Registered (`10` entries, `PR #19`); **`FRONTIER_A` FROZEN** (`543 / 326 / 10-248-285-0 / 102`) | `canonical_utility_input` / `canonical_decision` |
| **`FRONTIER_A` Clustering** | `clustering_config_v1`, `preference_profiles_v1`, `participant_cluster_assignments_v1`, `cluster_profiles_v1`, `cluster_stability_v1`, `cluster_sensitivity_v1`, `cluster_pareto_associations_v1`, `agent_05_qa_report_v1` | Agent 05 | Registered (`8` entries, `PR #22`); `NO_STABLE_CLUSTER_STRUCTURE` (interpretive only) | `canonical_intermediate` |
| **`FRONTIER_A` Voting** | `voting_input_validation_v1`, `voting_results_v1`, `voting_uncertainty_v1`, `baldwin_results_v1`, `rrv_results_v1`, `pareto_voting_comparison_v1`, `voting_sensitivity_v1`, `agent_06_qa_report_v1` | Agent 06 | Registered (`8` entries, `PR #22`); `NO_ROBUST_SINGLE_WINNER`, `BALDWIN`/`RRV = NOT_APPLICABLE` | `canonical_decision` / `canonical_intermediate` |
| **`FRONTIER_B` Counterfactual** | Isolated namespace under `data/processed/preference/counterfactual/` *(planned)* | Agent 04 (`ADR-0009`) | **`PLANNED / PENDING`** (`ISSUE-008`; additive only, zero mutation to `39` `FRONTIER_A` entries) | `counterfactual_sensitivity` |
| **Presentation & Review** | `policy_brief_v1` (`runs/<run_id>/reports/policy_brief.md`), `review_report_v1` (`runs/<run_id>/integration_review_report.json`) | Agents 08, 09 | **`AGENT_08_TECHNICAL_RELEASE = READY`** · **`AGENT_08_REPORTING_STATUS = HELD_FOR_RESOURCE_REGIME_SENSITIVITY`** | `presentation_only` (Sink) / `canonical_decision` |

---

## 6. Pending Milestones & Next Sequence (`ADR-0009` + Packaging Hygiene)

- [x] **Stages 00–07 & `FRONTIER_A` Integration (`run_20261111_002`)**: Complete, verified (`39` registered artifacts in `manifest.json`), and frozen as `OBSERVED_DESIGN_FRONTIER`.
- [x] **`ADR-0009` Architectural Approval (`PR #23`, `6508ded`)**: Dual-frontier separation, `RESOURCE_ELIGIBILITY`, 10-field `CLUB_GOOD`, provenance separation, `NEW_LLM_CODING_REQUIRED = NO`, and Agent 08 reporting hold codified.
- [x] **Agent 10 `ADR-0009` Governance & Context-Pack Sync**: `docs/PROJECT_STATE.md`, `docs/OPEN_ISSUES.md`, audit docs, and all 12 context packs (`agent_00`–`agent_11`) synchronized.
- [ ] **Shared Dependency Sync (`ISSUE-009` — Agent 11)**: Add `numpy`, `scipy`, and `scikit-learn` to `pyproject.toml` so `tests/test_clustering.py` and full `pytest tests/ -v` collect and run cleanly in a fresh `.venv`.
- [ ] **`ADR-0009` Contract Integration & Orchestrator Hold Split (`ISSUE-008` — Agent 11)**: Integrate `ADR-0009` schemas into `src/contracts.py`, `schemas/interfaces.json`, `docs/DATA_CONTRACTS.md`, update `src/pipeline/orchestrator.py` to separate `AGENT_08_TECHNICAL_RELEASE = READY` from `AGENT_08_REPORTING_STATUS = HELD_FOR_RESOURCE_REGIME_SENSITIVITY`, and reserve the isolated `FRONTIER_B` manifest namespace.
- [ ] **Optional Deterministic Eligibility Tagging (Agent 03, Zero GPU) & `FRONTIER_B` Execution (Agent 04)**: Evaluate counterfactual `RESOURCE_REGIME_EXPANDED_FRONTIER` (`Q-A`–`Q-H`, `VG-01`–`VG-09`) into `data/processed/preference/counterfactual/` while preserving frozen `FRONTIER_A` bit-for-bit.
- [ ] **Agent 08 Dual-Frontier Reporting & Agent 09 Final Review**: Lift `AGENT_08_REPORTING_STATUS` after `FRONTIER_B` integration (or explicit governance override), generate sink-only dual-frontier briefs, and pass Agent 09 audit (`ADR-0008` V1–V8 + `ADR-0009` `VG-01`–`VG-09`).

