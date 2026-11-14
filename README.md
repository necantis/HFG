# HFG — Hybrid Feedback Governance

**HFG** is a reproducible, multi-agent analytical governance system for ingesting multilingual stakeholder survey responses (`fr`, `de`, `en`), discovering evidence-grounded subtopics and organisational values bottom-up via independent dual-LLM qualitative coding, constructing distributional preference representations and constraint-only governance solutions, running exact and Monte Carlo participant-level Pareto analysis alongside social choice voting rules, and publishing traceable policy briefs under strict, machine-verified release gates.

- **Repository**: <https://github.com/necantis/HFG>
- **Architecture Version**: `v1.1.0` (12-Agent Architecture + 5-Stage Google Colab Topology)
- **Contract Schema Version**: `1.0.0` / `v1.1.0`
- **Active Analytical Run**: `run_20261111_002`
- **Current Frontier & Release Status (`origin/main` = `6508ded` / PR `#23`, [`ADR-0009`](docs/DECISIONS/ADR-0009-resource-good-regimes-and-counterfactual-institutional-design.md))**:
  - **`FRONTIER_A = OBSERVED_DESIGN_FRONTIER` (Completed & Frozen)**: `543` feasible `Q01`–`Q13` packages · `326` expected-reference nondominated · `10` `ROBUSTLY_NONDOMINATED` · `248` `CONDITIONALLY_NONDOMINATED` (`102` at `p_nd >= 0.95`) · `285` `UNRESOLVED_DUE_TO_CODING_UNCERTAINTY` · `0` `ROBUSTLY_DOMINATED` · `NO_STABLE_CLUSTER_STRUCTURE` · `NO_ROBUST_SINGLE_WINNER` · `BALDWIN = NOT_APPLICABLE` · `RRV = NOT_APPLICABLE` (`39` registered artifacts in [`runs/run_20261111_002/manifest.json`](runs/run_20261111_002/manifest.json)).
  - **`FRONTIER_B = RESOURCE_REGIME_EXPANDED_FRONTIER` (Pending Counterfactual Sensitivity)**: Separate counterfactual institutional-design sensitivity layer (`ISSUE-008`); **`NEW_LLM_CODING_REQUIRED = NO`**.
  - **Release Gates**: `AGENT_03_RELEASE = READY`, `AGENT_04_RELEASE = READY` *(for frozen `FRONTIER_A`; clean checkouts without staged gitignored runtime payloads evaluate local gates `BLOCKED`)*, **`AGENT_08_TECHNICAL_RELEASE = READY`**, **`AGENT_08_REPORTING_STATUS = HELD_FOR_RESOURCE_REGIME_SENSITIVITY`**.

---

## Purpose

HFG analyzes authentic institutional stakeholder survey data to inform multi-party governance design decisions without imposing pre-existing institutional packages, predetermined theme taxonomies, or synthetic preference scores.

The system is designed so that an external reviewer can trace every downstream analytical structure—discovered subtopics, value assignments, candidate governance alternatives, distributional preference cells, Pareto-nondominated solutions, and policy claims—back through cryptographic hashes and verbatim character-offset spans to immutable raw participant cells, while enforcing explicit failure gates whenever upstream requirements are unverified or incomplete.

---

## Analytical Principles

All analytical stages in HFG are governed by strict methodological invariants ([`AGENTS.md`](AGENTS.md), [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), [`docs/DECISIONS/ADR-0005-twelve-agent-architecture-preference-cell-and-pareto-invariants.md`](docs/DECISIONS/ADR-0005-twelve-agent-architecture-preference-cell-and-pareto-invariants.md)):

- **`Q01`–`Q13` remain the primary survey questions**: All substantive qualitative discovery, candidate option synthesis, preference modeling, utility derivation, and Pareto evaluation operate over the 13 primary analytical questions.
- **`Q14` is optional contextual material where applicable**: Question 14 (open general remarks) is preserved for contextual interpretation and reportable remarks without distorting primary-question preference coverage metrics.
- **Subtopics are discovered bottom-up from participant evidence**: Multiple [`CanonicalSubtopic`](src/contracts.py) themes per question are discovered dynamically by analyzing question-scoped participant [`EvidenceSpan`](src/contracts.py) records.
- **Subtopics are not simply derived from question wording**: Automated coders are explicitly barred from splitting or inventing subtopics merely by paraphrasing the survey prompt text.
- **Organisational values are openly discovered from evidence**: Cross-question values ([`ValueAssignment`](src/contracts.py)) emerge openly from participant evidence with optional polarity (`None` when unstated rather than fabricated).
- **Goods classification applies only to relevant allocation/access/ownership/financing/risk/decision-right questions**: Economic good labels (`private_good`, `club_good`, `common_good`, `public_good`) are restricted to questions where allocation, access, ownership, financing, risk, or decision rights are conceptually applicable (`Q07`–`Q12` enabled; institutional design questions conditional).
- **Perception questions are not automatically goods-classified**: Diagnostic and perception items (`Q01`, `Q02`, `Q03`, `Q06`) use question-specific analytical frames rather than forced economic-good categorization (`disabled` unless conditional evidence triggers an allocation framing).
- **Missing answers never become preferences**: Blank cells (`missing_raw_blank`) are explicitly tracked and excluded from preference simplexes (`0.0` imputation is forbidden).
- **Explicit no-opinion and insufficient-experience remain evidence but do not create synthetic preferences**: Non-preference epistemic statuses (`explicit_no_opinion`, `explicit_insufficient_experience`, `explicit_insufficient_information`, `punctuation_uninterpretable`, `no_additional_remarks`) are preserved as reportable epistemic observations while enforcing empty alternative probability distributions (`is_valid = False`, `has_usable_preference = False`).
- **Semantic importance, preference, confidence, and agreement remain separate**: In [`PreferenceCell`](src/contracts.py), choice probability distributions (`alternative_probabilities`, summing to $1.0 \pm 10^{-4}$ for `observed_usable` cells) are kept strictly orthogonal from `semantic_importance`, `coder_confidence`, `coder_agreement`, `missingness_state`, and `evidence_span_ids`.
- **Exact evidence provenance is required**: Every [`EvidenceSpan`](src/contracts.py) must carry a verbatim `exact_quote` whose character offsets `[start_char, end_char]` match `offset_reference_text` and whose SHA-256 links back to the normalized cell and raw CSV baseline.
- **Clusters and values never pre-filter Pareto-feasible solutions**: Candidate solutions are generated and pruned solely by logical, institutional, and structural feasibility constraints. Cluster profiles (`preference_profiles.json`) and organisational values explain solutions ex-post and may never exclude feasible alternatives from Pareto frontiers.

### Dual-Frontier Baseline Freeze & `ADR-0009` Resource-Regime Sensitivity

[`ADR-0009`](docs/DECISIONS/ADR-0009-resource-good-regimes-and-counterfactual-institutional-design.md) (`PR #23`, `6508ded`) freezes the completed empirical baseline and establishes a strictly isolated counterfactual sensitivity layer:

- **Frozen Empirical Baseline (`FRONTIER_A = OBSERVED_DESIGN_FRONTIER`, Immutable)**:
  - **`543`** strictly constraint-feasible `Q01`–`Q13` governance packages (`161` `FeasibleAlternative`, `0` prohibited prunings)
  - **`326`** expected-reference nondominated solutions (`5,973` `ParticipantUtility` records, `0` non-null `point_utility`)
  - 4-state `RobustParetoResult`: **`10`** `ROBUSTLY_NONDOMINATED`, **`248`** `CONDITIONALLY_NONDOMINATED` (**`102`** with `p_nd >= 0.95`), **`285`** `UNRESOLVED_DUE_TO_CODING_UNCERTAINTY`, **`0`** `ROBUSTLY_DOMINATED`
  - **`NO_STABLE_CLUSTER_STRUCTURE`** (`selected_k = 1`, `PROFILE_01`; exploratory `Rep C` `8` vs `3` non-canonical only)
  - **`NO_ROBUST_SINGLE_WINNER`**, **`BALDWIN = NOT_APPLICABLE`**, **`RRV = NOT_APPLICABLE`** (`77.8%` MC Condorcet cycles; `N = 11` LOO flips `6/11` Borda / `9/11` Minimax)
  - **Authoritative Interpretation**: *"A robust Pareto core exists, but no single collective-choice winner is stable across the admissible uncertainty scenarios."* Never report that "no solution was found."
- **Counterfactual Institutional-Design Sensitivity (`FRONTIER_B = RESOURCE_REGIME_EXPANDED_FRONTIER`)**: A separate counterfactual sensitivity analysis—NOT a replacement for `FRONTIER_A`—testing `PRIVATE_GOOD`, `CLUB_GOOD`, `COMMON_POOL_RESOURCE`, `PUBLIC_GOOD`, and `HYBRID` regimes solely on `ADR-0009`-eligible resource subtopics (`UNRESOLVED_DUE_TO_COUNTERFACTUAL_UTILITY`, questions `Q-A`–`Q-H`, verification gates `VG-01`–`VG-09`).
- **Subtopic-Level `RESOURCE_ELIGIBILITY`**: Eligibility is decided at the subtopic level rather than blanket whole-question goods assignment (`Q10` funding/allocation resources = `ELIGIBLE`; `Q11` overhead/resource-pooling mechanisms = `ELIGIBLE` while negotiation/transparency process facets = `INELIGIBLE`; `Q12` bonus/investment pools = `ELIGIBLE` while `Q12_socle_adequacy_B_ONLY` perception = `INELIGIBLE`; `Q09` risk/resource-pooling facets = `ELIGIBLE` with statutory solvency/risk-pooling caveat while diagnostic facets = `INELIGIBLE`; `Q06` selected financial facets = `ELIGIBLE` under double-count guard while evaluation/autonomy/communication facets = `INELIGIBLE`; `Q08_hr_management_level` = `CONDITIONAL_RESOURCE_ONLY` strictly where evidence concerns allocable HR/admin support capacity rather than general HR authority/perception; `Q01`–`Q05`, `Q07` governance/signing authority despite `ENABLED` in registry, `Q13`, and `Q14` = `INELIGIBLE`).
- **Operational `CLUB_GOOD` Mechanism (Not a Bare Label)**: Any candidate labeled `CLUB_GOOD` is rejected unless all 10 explicit operational parameters are populated: `membership_mode = VOLUNTARY`, explicit `member_contribution_rule`, exact `non_member_compulsory_contribution = 0.0`, explicit `member_priority` (`member_access >= non_member_access`), explicit `non_member_access` (`NONE | RESIDUAL_CAPACITY | PAY_PER_USE | OTHER_EXPLICIT`), `exit_policy` (`ALLOWED | CONSTRAINED`), `capacity_congestion_rule` (mandatory when `RIVAL` or `CONGESTIBLE`), `governance_rule`, and `pricing_contribution_rule`.
- **Three-Way Evidence Provenance Boundary**: Strictly isolates `OBSERVED_RESPONDENT_PREFERENCE`, `INSTITUTIONALLY_DERIVED_MECHANISM`, and `COUNTERFACTUAL_PREFERENCE_ASSUMPTION`. *"I do not want compulsory payment"* does **not** imply *"I prefer club provision"* without direct `EvidenceSpan` support; zero compulsory non-member payment (`0.0`) is mechanically entailed, whereas club preference remains counterfactual unless evidenced (`UNRESOLVED_DUE_TO_COUNTERFACTUAL_UTILITY`, no arbitrary point utility).
- **Zero LLM Re-Coding & Agent 08 Hold Split**: **`NEW_LLM_CODING_REQUIRED = NO`**. Agent 08 status is split into **`AGENT_08_TECHNICAL_RELEASE = READY`** *(bundle `a84df6ff...` verified)* and **`AGENT_08_REPORTING_STATUS = HELD_FOR_RESOURCE_REGIME_SENSITIVITY`** *(deliberately paused pending `FRONTIER_B`, not a pipeline failure)*.

---

## Dataset and Current Run (`run_20261111_002`)

The repository initially scaffolded under `run_20261111_001` (placeholder testing data, later marked `INVALIDATED`). On 2026-11-12, authentic anonymized stakeholder survey data (`Anonymized_survey_data_2026.csv`) replaced scaffolding under active run **`run_20261111_002`**.

### Current Ingestion Invariants (`data/raw/survey_raw.csv`)

- **Source File**: [`data/raw/survey_raw.csv`](data/raw/survey_raw.csv) (`immutable_source`, external write-once CSV: `11` data rows, `12` lines including header, `27` columns)
- **Authoritative SHA-256**: `56acded3e02be49be27d6b288fa2c43fcce68df24525113eba1b1161eec52a95` *(Git SHA-1 blob `git hash-object`: `eb526813aadcfab2b4b157e7b6513de50e6b3178`; see [`docs/AUDIT_TRAIL.md`](docs/AUDIT_TRAIL.md) resolving the isolated transcription typo on line 120 of `docs/AGENT_HANDOFFS/agent_03_handoff.md`)*
- **Participants**: **`11`** anonymized stakeholder rows (`PARTICIPANT_001`–`PARTICIPANT_011`)
- **Normalized Cells**: **`154`** total participant/question cells (`11` participants × `14` questions)
- **Question Coverage**:
  - **`Q01`–`Q13`**: `13` primary substantive questions (`143` cells total)
  - **`Q14`**: `1` optional contextual remarks column (`11` cells total)
- **Observed Missingness & Preference-Capable Breakdown** (verified by [`src/ingest/ingestion.py`](src/ingest/ingestion.py) and Gate 1):
  - **`136`** `observed_usable` / preference-capable cells (`131` `substantive` + `5` `mixed` epistemic statuses, `has_usable_preference = True`)
  - **`10`** `missing_raw_blank` cells
  - **`6`** `missing_non_substantive` cells (`2` `explicit_no_opinion`, `2` `explicit_insufficient_experience`, `2` `punctuation_uninterpretable`)
  - **`2`** `ambiguous` cells (text supplied and reportable, `has_usable_preference = False`)
  - **`0`** imputed preference cells

### Respondent Privacy & Deterministic Regeneration

Normalized respondent files (`data/normalized/answers_normalized.parquet` and `data/normalized/answers_normalized.json`) as well as unreconciled participant-level coder outputs (`data/processed/coder_a_outputs.json`, `data/processed/coder_b_outputs.json`, `data/processed/profiles/`, and `.checkpoints/`) are **intentionally excluded from Git** via [`.gitignore`](.gitignore). Any authorised user with repository access deterministically regenerates identical normalized cells locally from `data/raw/survey_raw.csv` via [`src/ingest/ingestion.py`](src/ingest/ingestion.py). No participant answer text is included in GitHub documentation or audit logs.

---

## 12-Agent Architecture

HFG divides analytical, runtime, governance, and quality-assurance responsibilities across 12 specialized agents ([`AGENTS.md`](AGENTS.md)):

| Agent | Role | Module Ownership | Tracked Notebooks | Output Authority (`PR #23` / `ADR-0009`) |
| :--- | :--- | :--- | :--- | :--- |
| **Agent 00** | System Architect | [`src/contracts.py`](src/contracts.py), [`schemas/interfaces.json`](schemas/interfaces.json), [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | *(planned `00_architecture_exploration.ipynb`)* | Systemic invariants, 20+ contracts, `ADR-0008`, and `ADR-0009` |
| **Agent 01** | Data & Question Registry | [`src/ingest/`](src/ingest/ingestion.py), [`src/registry/`](src/registry/question_registry.py) | [`notebooks/00_control_plane.ipynb`](notebooks/00_control_plane.ipynb), [`notebooks/01_ingest_exploration.ipynb`](notebooks/01_ingest_exploration.ipynb) | `answers_normalized.parquet` (gitignored) & [`data/normalized/question_registry.json`](data/normalized/question_registry.json) |
| **Agent 02** | Qualitative Coding | [`src/nlp/`](src/nlp/) | [`notebooks/01_gpu_coders.ipynb`](notebooks/01_gpu_coders.ipynb), [`notebooks/02_qualitative_coding.ipynb`](notebooks/02_qualitative_coding.ipynb) | Production dual coding completed on Blackwell (`136/136/0`; **`NEW_LLM_CODING_REQUIRED = NO`**) |
| **Agent 03** | Evidence & Reconciliation | [`src/evidence/`](src/evidence/reconciliation.py) | *(planned `03_evidence_reconciliation.ipynb`)* | `ADR-0008` CPU reconciliation integrated (`PR #15`, `PR #17`; `16/16` QA `PASS`, `17` crosswalk rules); optional deterministic `RESOURCE_ELIGIBILITY` tagging only if needed |
| **Agent 04** | Preference, Utility & Pareto | [`src/preference/`](src/preference/pipeline.py) | *(planned `02_math_analysis.ipynb`, `04_preference_utility_pareto.ipynb`)* | **`FRONTIER_A` COMPLETE & FROZEN** (`PR #18`, `PR #19`: `543` / `326` / `10-248-285-0`); **`FRONTIER_B`** counterfactual follow-up pending (`ISSUE-008`) |
| **Agent 05** | Preference Profiles / Clustering | [`src/clustering/`](src/clustering/pipeline.py) | *(planned `05_preference_profiles_clustering.ipynb`)* | Completed & integrated (`PR #21`, `PR #22`: `NO_STABLE_CLUSTER_STRUCTURE`; unchanged under `ADR-0009`; `ISSUE-009` `pyproject.toml` dependency sync open) |
| **Agent 06** | Voting & Social Choice | [`src/voting/`](src/voting/pipeline.py) | *(planned `06_voting_social_choice.ipynb`)* | Completed & integrated (`PR #20`, `PR #22`: `NO_ROBUST_SINGLE_WINNER`, `BALDWIN`/`RRV = NOT_APPLICABLE`; unchanged under `ADR-0009`) |
| **Agent 07** | GPU Runtime | [`src/runtime/`](src/runtime/model_runtime.py) | [`notebooks/07_gpu_runtime.ipynb`](notebooks/07_gpu_runtime.ipynb), [`notebooks/01_gpu_coders.ipynb`](notebooks/01_gpu_coders.ipynb), [`notebooks/HFG_live_execution.ipynb`](notebooks/HFG_live_execution.ipynb) | [`runs/run_20261111_002/gpu_runtime_config.json`](runs/run_20261111_002/gpu_runtime_config.json), verified Blackwell benchmark (`bc8e6d22...`, `EXECUTED_LIVE_GPU`); **`NEW_LLM_CODING_REQUIRED = NO`** |
| **Agent 08** | Policy Report | `src/reporting/` *(held)* | *(planned `03_report.ipynb`, `08_reporting.ipynb`)* | **`AGENT_08_TECHNICAL_RELEASE = READY`** · **`AGENT_08_REPORTING_STATUS = HELD_FOR_RESOURCE_REGIME_SENSITIVITY`** (sink-only deliverable) |
| **Agent 09** | Final Integration Reviewer | `src/review/` *(pending)* | *(planned `09_integration_review.ipynb`)* | Independent end-to-end invariant audit (`ADR-0008` V1–V8 + `ADR-0009` `VG-01`–`VG-09`; never orchestrates) |
| **Agent 10** | Documentation, Memory & Artifacts | [`src/artifact_registry.py`](src/artifact_registry.py), [`src/context_pack.py`](src/context_pack.py), [`src/freshness_checker.py`](src/freshness_checker.py), [`docs/`](docs/), [`AGENTS.md`](AGENTS.md) | *(planned `10_memory_and_registry.ipynb`)* | Governance ADRs, audit docs, context packs, manifests & run cards |
| **Agent 11** | Orchestration & QA | [`src/pipeline/orchestrator.py`](src/pipeline/orchestrator.py), [`src/hardcoding_scanner.py`](src/hardcoding_scanner.py) | [`notebooks/00_control_plane.ipynb`](notebooks/00_control_plane.ipynb), [`notebooks/04_validation.ipynb`](notebooks/04_validation.ipynb) | Integrated `FRONTIER_A` (`39` manifest entries); next owns `ADR-0009` contract/hold integration (`ISSUE-008`) & `pyproject.toml` dependency sync (`ISSUE-009`) |

Under [`ADR-0007`](docs/DECISIONS/ADR-0007-git-collaboration-shared-file-ownership-and-artifact-handoff.md), implementation agents develop exclusively on dedicated task branches (`agent/*`) in isolated worktrees/clones and submit formal handoffs ([`docs/AGENT_HANDOFFS/`](docs/AGENT_HANDOFFS/)), while **Agent 11** owns cross-branch integration, combined QA, and release-gate enforcement before merges to `main`.

---

## Pipeline

### Analytical Dependency Order

Every analytical run progresses strictly along this evidence-derived DAG:

```text
data/raw/survey_raw.csv (immutable external CSV, SHA-256 verified)
  -> Agent 01: Deterministic Normalization & Question Registry (Gate 1 PASS)
  -> Agent 02: Dual-Pass Qualitative Coding Contracts & Prompt Builders (Gate 2 PASS)
  -> Agent 07: Hardware Preflight, 5-Stage GPU Benchmark [EXECUTED_LIVE_GPU] & vLLM Server Runtime
  -> Independent Qualitative Execution [COMPLETED ON BLACKWELL: 136/136/0; NEW_LLM_CODING_REQUIRED = NO]:
       Coder A (DeepSeek reasoning family)  +  Coder B (independent Mistral family)
  -> Agent 11 Validation Gate (Checks A-H + 13-condition AGENT_03_RELEASE = READY)
  -> Agent 03: Evidence Span Ledger & ADR-0008 CPU Reconciliation [COMPLETED IN PR #15 / #17; 16/16 QA PASS]
  -> Agent 11 Agent 04 Gate (9-condition AGENT_04_RELEASE = READY for FRONTIER_A)
  -> Agent 04 [FRONTIER_A FROZEN]: 543 Feasible Packages -> 326 Nondominated -> 10/248/285/0 Robust Pareto [PR #18 / #19]
  -> Agent 05 [FROZEN]: NO_STABLE_CLUSTER_STRUCTURE [PR #21 / #22]
  -> Agent 06 [FROZEN]: NO_ROBUST_SINGLE_WINNER, BALDWIN/RRV = NOT_APPLICABLE [PR #20 / #22]
  -> [ADR-0009 COUNTERFACTUAL BRANCH — ISSUE-008]:
       Agent 11 Contract & Hold Split -> Agent 04 FRONTIER_B (RESOURCE_REGIME_EXPANDED_FRONTIER, VG-01..VG-09)
  -> Agent 08 (AGENT_08_TECHNICAL_RELEASE = READY; AGENT_08_REPORTING_STATUS = HELD_FOR_RESOURCE_REGIME_SENSITIVITY)
  -> Agent 09 (Independent Final Integration Review: V1-V8 & VG-01-VG-09)
```

### Implementation Order vs. Analytical Dependency Order

Auditors must distinguish **development/integration chronology** from **analytical runtime execution order**:

1. **Implementation & Integration Chronology (`PR #1`–`PR #23`)**: Persistent memory (`ADR-0001`–`0004`) → 20 data contracts (`ADR-0005`, `ADR-0006`) → raw survey lock (`run_20261111_002`) → Git collaboration policy (`PR #1`, `ADR-0007`) → Agent 01/02 refinements (`PR #2`) → Agent 07 GPU runtime, live vLLM, JSON recovery, execution profiles & `smoke_tiny` scoping (`PRs #4`–`#9`) → audit documentation & notebook tracking (`PR #10`) → initial Agent 03 reconciliation on live Blackwell coding (`PR #11`) → `ADR-0008` policy, contract integration & `ISSUE-005` governance sync (`PRs #12`–`#14`) → Agent 03 CPU `ADR-0008` adaptation & Wave-3B registration (`PRs #15`–`#17`) → Agent 04 `FRONTIER_A` execution & registration (`PRs #18`–`#19`) → Agent 06 voting & Agent 05 clustering + `39`-artifact manifest convergence (`PRs #20`–`#22`) → [`ADR-0009`](docs/DECISIONS/ADR-0009-resource-good-regimes-and-counterfactual-institutional-design.md) dual-frontier contract (`PR #23`, `6508ded`).
2. **Analytical Dependency Order (Runtime State Today)**: The complete `FRONTIER_A` (`OBSERVED_DESIGN_FRONTIER`) analytical chain through Agents 01–07 (`39` registered artifacts in [`runs/run_20261111_002/manifest.json`](runs/run_20261111_002/manifest.json) and [`runs/run_20261111_002/RUN_CARD.md`](runs/run_20261111_002/RUN_CARD.md)) is verified and frozen. Agent 08 is technically `READY` (`a84df6ff...`), while execution is deliberately held (`AGENT_08_REPORTING_STATUS = HELD_FOR_RESOURCE_REGIME_SENSITIVITY`) pending `ADR-0009` contract integration and Agent 04's isolated `FRONTIER_B` counterfactual evaluation (`NEW_LLM_CODING_REQUIRED = NO`). On clean Git checkouts lacking gitignored runtime payloads, `PipelineOrchestrator` truthfully evaluates local gates as `BLOCKED` until payloads are staged.

---

## Execution Profiles

PR #8 ([`c96b70d`](docs/AUDIT_TRAIL.md)) and PR #9 ([`08d0096`](docs/AUDIT_TRAIL.md)) partition [`src/runtime/dual_coder_runner.py`](src/runtime/dual_coder_runner.py) and [`AtomicQuestionCheckpointStore`](src/runtime/model_runtime.py) into three strictly isolated execution profiles (`ExecutionProfile`):

| Profile | Purpose | Selected Corpus Scope | Output Location (Gitignored) | Agent 03 Gate Eligibility |
| :--- | :--- | :--- | :--- | :--- |
| **`smoke_tiny`** | Fast sanity check of live vLLM structured JSON generation, schema bounds & WAL checkpointing | 2 rows (`1` short substantive `<= 300` chars excluding `PARTICIPANT_002/Q06` & longest texts + `1` non-substantive row) with `SMOKE_BOUNDED_LIMITS` | `data/processed/profiles/smoke_tiny/` | **`production_eligible = False`** (`synthetic_or_test_execution = True`; **never** unlocks Agent 03) |
| **`pilot_subset`** | Real pinned-model trial covering hard edge cases before full run | Mandatory coverage set (including `PARTICIPANT_002/Q06`, ordinary substantive, long reply, `raw_blank`, `explicit_no_opinion`, `explicit_insufficient_experience`, `ambiguous`, plus per-question anchors) | `data/processed/profiles/pilot_subset/` | **`production_eligible = False`** (`synthetic_or_test_execution = False`; **never** unlocks Agent 03) |
| **`production`** | Full analytical dual-coding corpus inference for `run_20261111_002` | All `154` cells (`136` usable primary/Q14 + explicit non-preference preservation) | `data/processed/coder_a_outputs.json` & `data/processed/coder_b_outputs.json` | **`production_eligible = True`** (only profile accepted by [`PipelineOrchestrator`](src/pipeline/orchestrator.py)) |

> **Hard Invariant**: Agent 11's orchestrator inspects explicit `execution_profile`, `production_eligible`, and `synthetic_or_test_execution` flags in outputs and WAL checkpoints, rejecting any `smoke_tiny` or `pilot_subset` artifacts from satisfying the `AGENT_03_RELEASE` gate.

---

## Models

HFG enforces strict **architectural family diversity**: Coder A uses a DeepSeek reasoning-distilled model, while Coder B must belong to an independent non-Qwen/non-DeepSeek family (`mistral` primary, `gemma`/`gemma3` alternative; smoke tests additionally allow `smollm2` or `llama`). Substituting another Qwen-derived model for Coder B is programmatically blocked by [`validate_model_family_diversity`](src/runtime/model_runtime.py).

Production configuration follows an **immutable-revision philosophy**: `build_profile_runtime_config()` pins production weights to verified 40-character Hugging Face commit SHAs so model updates upstream cannot silently alter reproducibility.

### Readiness Classification (`origin/main` = `6508ded` / PR `#23` + `RUN_CARD.md` Canonical Runtime Evidence)

| Coder / Profile | Configured Model Repo & Revision | Stage Status |
| :--- | :--- | :--- |
| **Production Coder A** *(PR #8 `src/runtime/model_runtime.py`)* | `Valdemardi/DeepSeek-R1-Distill-Qwen-32B-AWQ` (`AWQ-INT4`, `rev: 1de6a3f7b151f6ea0f6d42acb3566e094eb8a264`) | **Production-Completed** (`136/136/0`, `18` non-preference cells preserved, `0` span errors, Checks A–H `8/8 PASS`); **`NEW_LLM_CODING_REQUIRED = NO`** |
| **Production Coder B** *(PR #8 `src/runtime/model_runtime.py`)* | `RedHatAI/Mistral-Small-3.1-24B-Instruct-2503-quantized.w4a16` (`W4A16-INT4`, `rev: dc0a9d9df93998ec3163cabca261715c0bbee4f6`) *(Alt: `pytorch/gemma-3-27b-it-AWQ-INT4`)* | **Production-Completed** (`136/136/0`, `18` non-preference cells preserved, `0` span errors, Checks A–H `8/8 PASS`); **`NEW_LLM_CODING_REQUIRED = NO`** |
| **Smoke Coder A** *(PR #9 `smoke_tiny`)* | `deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B` (`BF16`, `max_model_len=4096`, `max_output_tokens=2048`) | **Configured** *(Unit-tested with mock server)* |
| **Smoke Coder B** *(PR #9 `smoke_tiny`)* | `HuggingFaceTB/SmolLM2-1.7B-Instruct` (`BF16`, `max_model_len=4096`, `max_output_tokens=2048`) | **Configured** *(Unit-tested with mock server)* |

**Explicit Readiness Accounting**:
- **Configured & Resolved**: Yes (pinned 40-char HF revisions in [`src/runtime/model_runtime.py`](src/runtime/model_runtime.py); `common source_evidence_hash` `0b814c3b...` verified).
- **Benchmarked**: Yes — 5-stage live Blackwell benchmark `runs/run_20261111_002/gpu_runtime_benchmark.json` verified `EXECUTED_LIVE_GPU` (`SHA-256: bc8e6d22...`, certified in [`runs/run_20261111_002/RUN_CARD.md`](runs/run_20261111_002/RUN_CARD.md); payload gitignored outside Git).
- **Production-Completed**: Yes (`136/136/0`, `AGENT_03_RELEASE = READY`, `AGENT_04_RELEASE = READY` for frozen `FRONTIER_A`, `39` registered manifest entries). Sensitive coder JSONs remain outside Git, so clean Git checkouts show upstream runtime gates `BLOCKED` locally unless payloads are staged. Under [`ADR-0009`](docs/DECISIONS/ADR-0009-resource-good-regimes-and-counterfactual-institutional-design.md), **`NEW_LLM_CODING_REQUIRED = NO`**.

---

## GPU Execution

- **Target Environment**: Google Colab GPU runtime running vLLM OpenAI-compatible HTTP servers (`localhost:8001` for Coder A, `localhost:8002` for Coder B, `temperature = 0.0`, `seed = 42`).
- **Recorded Hardware Preflight (`runs/run_20261111_002/gpu_runtime_config.json`)**: An initial Colab preflight (`2026-11-13T17:40:00Z`) measured `1 × NVIDIA RTX PRO 6000 Blackwell Server Edition` (`97887 MB` total VRAM, `97251 MB` free VRAM, CUDA `13.0`, Driver `580.82.07`, Compute Capability `12.0`, CPU `AMD EPYC 9B45`, `181130 MB` system RAM) and passed Gate 1 and Gate 2.
- **`SEQUENTIAL_FALLBACK` vs. `CONCURRENT_DUAL_SERVER`**: As of PR #8 ([`select_safe_execution_mode`](src/runtime/model_runtime.py)), both **`pilot_subset`** and **`production`** default conservatively to **`SEQUENTIAL_FALLBACK`** (booting Coder A to completion, stopping it, then booting Coder B) unless a matching live 5-stage benchmark report (`runs/<run_id>/gpu_runtime_benchmark.json`) empirically proves `CONCURRENT_DUAL_SERVER` is safe for the active pinned models.
- **Concurrent Residency vs. Safe Production Concurrency**: Fits-in-VRAM preflight math (`combined_required_mb = 49384 MB` vs `97887 MB` total VRAM) demonstrates **potential concurrent residency**, NOT **safe production concurrency**. Live dual-server stability requires passing all 5 stages of `run_runtime_benchmark_suite` (`1_coder_a_alone`, `2_coder_b_alone`, `3_both_servers_resident`, `4_simultaneous_structured_request`, `5_bounded_concurrent_requests`, including `schema_valid_output_rate == 1.0`, recovery after failure, and failure isolation).

---

## Checkpointing

To survive Google Colab session preemption, disconnections, or GPU out-of-memory interrupts without re-running completed questions:

- **Crash-Safe Atomic WAL**: [`AtomicQuestionCheckpointStore`](src/runtime/model_runtime.py) writes per-question JSON records atomically and appends to profile-scoped write-ahead logs (`runs/<run_id>/<execution_profile>` directories under `.checkpoints/gpu_coder_wal` or `HFG_CHECKPOINT_ROOT`).
- **Configurable Persistent Root (`HFG_CHECKPOINT_ROOT`)**: Colab notebooks honor `HFG_CHECKPOINT_ROOT` (for example, a mounted Google Drive folder) via [`resolve_checkpoint_dir`](src/runtime/dual_coder_runner.py) so checkpoints persist across fresh clones and runtime restarts.
- **Google Drive Is Not Canonical Project Memory**: Google Drive provides durable **runtime persistence** for in-flight checkpoints and failure diagnostics only. GitHub (`AGENTS.md`, `docs/`, `src/`, `schemas/`, `runs/<run_id>/manifest.json`, and `RUN_CARD.md`) remains the sole authoritative project memory.
- **Strict Profile & Model Namespace Isolation**: `smoke_tiny != pilot_subset != production`. Checkpoints enforce exact verification of `execution_profile`, `model_repo`, `model_revision`, `quantization`, `prompt_hash`, `source_hash`, and (for `smoke_tiny`) `profile_config_hash`. Any model/config mismatch raises `CheckpointMismatchError` (or cleanly archives stale `smoke_tiny` namespaces via `archive_incompatible_smoke_namespace` without touching `pilot_subset` or `production`).

---

## Reproducibility

Full step-by-step instructions across CPU validation, `smoke_tiny`, `pilot_subset`, `production`, and post-`ADR-0009` counterfactual sensitivity discipline are documented in **[`docs/REPRODUCIBILITY.md`](docs/REPRODUCIBILITY.md)**. High-level canonical sequence:

1. **Clone & Install Dependencies**:
   ```bash
   git clone https://github.com/necantis/HFG.git && cd HFG
   python3 -m venv .venv && .venv/bin/pip install -e .
   ```
   > **Current Packaging Notice (`ISSUE-009`)**: [`pyproject.toml`](pyproject.toml) currently omits `numpy`, `scipy`, and `scikit-learn` imported by [`src/clustering/`](src/clustering/distances.py). Until Agent 11 updates `pyproject.toml`, running `.venv/bin/pytest tests/ -v` in a fresh `.venv` fails collection on [`tests/test_clustering.py`](tests/test_clustering.py) (`ModuleNotFoundError: No module named 'scipy'`). Targeted CPU verification suites (`test_context_pack.py`, `test_audit_documentation.py`, `test_acceptance.py`, `test_freshness_checker.py`, `test_contracts_adr0008.py`, `test_pipeline.py`) pass cleanly.
2. **Deterministic Ingestion & Gate 1 (CPU)**:
   ```bash
   .venv/bin/python -m src.ingest.ingestion
   .venv/bin/python -m src.hardcoding_scanner --check-gate-1
   ```
   *(Or run [`notebooks/00_control_plane.ipynb`](notebooks/00_control_plane.ipynb) on Colab, which automatically regenerates gitignored normalized files from `data/raw/survey_raw.csv`.)*
3. **5-Stage Live GPU Benchmark & Dual Coding (Already Completed for `run_20261111_002`; `NEW_LLM_CODING_REQUIRED = NO`)**:
   Live Blackwell `production` dual coding (`136/136/0`) and benchmark (`bc8e6d22...`) are verified in [`runs/run_20261111_002/RUN_CARD.md`](runs/run_20261111_002/RUN_CARD.md). Do **not** re-run LLM coding for `ADR-0009`.
4. **Release Gate & QA Validation (CPU)**:
   Run `.venv/bin/python -m src.freshness_checker --check-all`, `.venv/bin/python -m src.hardcoding_scanner --scan`, targeted CPU tests or `.venv/bin/pytest tests/ -v` (once `ISSUE-009` dependencies are installed), and `.venv/bin/python -m src.pipeline.orchestrator`.

---

## Evidence Provenance

HFG requires an unbroken cryptographic and structural chain from raw survey text to analytical claims (full inventory in **[`docs/ARTIFACT_PROVENANCE.md`](docs/ARTIFACT_PROVENANCE.md)**):

```text
raw source (data/raw/survey_raw.csv, SHA-256 56acded3...)
  -> normalized response (data/normalized/answers_normalized.parquet, source_hash)
  -> participant_id / question_id / response_id coordinates
  -> source / EvidenceSpan (exact_quote, start_char, end_char, offset_reference_text)
  -> independent coder output (coder_a_outputs.json & coder_b_outputs.json, prompt_hash + model_revision) [NEW_LLM_CODING_REQUIRED = NO]
  -> dual-coder reconciliation (candidate_options.json, themes_codebook.json, Level 2 CanonicalAlternativeCrosswalk & PreferenceUncertaintySet; zero silent averaging)
  -> PreferenceMatrix (OBSERVED_RESPONDENT_PREFERENCE only; alternative_probabilities summing to 1.0 +/- 1e-4, missingness_state separate)
  -> FRONTIER_A (FROZEN): ParticipantUtility -> 543 Feasible Packages -> 326 Nondominated -> 10/248/285/0 Robust Pareto + NO_STABLE_CLUSTER_STRUCTURE + NO_ROBUST_SINGLE_WINNER
  -> FRONTIER_B (COUNTERFACTUAL LAYER, ADR-0009): Separate sensitivity over eligible resource subtopics preserving OBSERVED_RESPONDENT_PREFERENCE vs INSTITUTIONALLY_DERIVED_MECHANISM vs COUNTERFACTUAL_PREFERENCE_ASSUMPTION
```

---

## Validation and QA

Four automated quality gates govern repository integrity and release readiness:

1. **`pytest` Suite ([`tests/`](tests/))**: Verifies schemas, memory registry, context packs, freshness checks, collaboration policy, ingestion invariants, NLP coding/repair logic, Agent 03 reconciliation, `ADR-0008` contracts (`tests/test_contracts_adr0008.py`), Agent 04 preference/Pareto invariants (`tests/test_preference.py`), Agent 05 clustering (`tests/test_clustering.py`, currently blocked on collection in clean `.venv` by `ISSUE-009`), Agent 06 voting (`tests/test_voting.py`), GPU runtime & JSON recovery ladder, and orchestration gates.
2. **`FreshnessChecker` ([`src/freshness_checker.py`](src/freshness_checker.py))**: 9-category audit checking stale documentation, schema versions, obsolete filenames, deprecated model names, notebook ownership, superseded ADRs, manifest provenance (`39` entries), unresolved evidence IDs, and stale upstream chains.
3. **`HardcodingScanner` ([`src/hardcoding_scanner.py`](src/hardcoding_scanner.py))**: Static AST/regex scan across `src/` and `notebooks/` blocking foreign survey entities, hardcoded packages, deprecated models, or fixed hardware assumptions, plus `verify_gate_1`.
4. **`PipelineOrchestrator` & Dual Release Gates ([`src/pipeline/orchestrator.py`](src/pipeline/orchestrator.py))**: Evaluates `AGENT_03_RELEASE` and 9-condition `AGENT_04_RELEASE` (`READY` on verified production bundle; locally `BLOCKED` on clean Git checkouts lacking gitignored payloads). Under [`ADR-0009`](docs/DECISIONS/ADR-0009-resource-good-regimes-and-counterfactual-institutional-design.md), Agent 08 reporting tracking distinguishes `AGENT_08_TECHNICAL_RELEASE = READY` from `AGENT_08_REPORTING_STATUS = HELD_FOR_RESOURCE_REGIME_SENSITIVITY`.

---

## Repository Map

- **Governance & Agent Rules**: [`AGENTS.md`](AGENTS.md)
- **System Architecture**: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- **20+ Data Contracts & Schemas (`ADR-0008`-Aligned; `ADR-0009` Integration Queued)**: [`docs/DATA_CONTRACTS.md`](docs/DATA_CONTRACTS.md) · [`src/contracts.py`](src/contracts.py) · [`schemas/interfaces.json`](schemas/interfaces.json)
- **Authoritative Project State Snapshot**: [`docs/PROJECT_STATE.md`](docs/PROJECT_STATE.md) *(synchronized through PR `#23` & `ADR-0009`; see [`docs/AUDIT_TRAIL.md`](docs/AUDIT_TRAIL.md) for historical PR ledger)*
- **Chronological Audit Trail**: [`docs/AUDIT_TRAIL.md`](docs/AUDIT_TRAIL.md)
- **Reproducibility Guide**: [`docs/REPRODUCIBILITY.md`](docs/REPRODUCIBILITY.md)
- **Artifact Provenance Ledger**: [`docs/ARTIFACT_PROVENANCE.md`](docs/ARTIFACT_PROVENANCE.md)
- **Open Issues & Technical Debt**: [`docs/OPEN_ISSUES.md`](docs/OPEN_ISSUES.md)
- **Notebook Inventory**: [`docs/NOTEBOOK_INDEX.md`](docs/NOTEBOOK_INDEX.md)
- **Architecture Decision Records (`ADR-0001`–`0009`)**: [`docs/DECISIONS/`](docs/DECISIONS/)
- **Agent Handoffs**: [`docs/AGENT_HANDOFFS/`](docs/AGENT_HANDOFFS/)
- **Model Strategy**: [`docs/MODEL_STRATEGY.md`](docs/MODEL_STRATEGY.md)
- **Active Run Card & Manifest**: [`runs/run_20261111_002/RUN_CARD.md`](runs/run_20261111_002/RUN_CARD.md) · [`runs/run_20261111_002/manifest.json`](runs/run_20261111_002/manifest.json)