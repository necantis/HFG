# HFG — Hybrid Feedback Governance

**HFG** is a reproducible, multi-agent analytical governance system for ingesting multilingual stakeholder survey responses (`fr`, `de`, `en`), discovering evidence-grounded subtopics and organisational values bottom-up via independent dual-LLM qualitative coding, constructing distributional preference representations and constraint-only governance solutions, running exact and Monte Carlo participant-level Pareto analysis alongside social choice voting rules, and publishing traceable policy briefs under strict, machine-verified release gates.

- **Repository**: <https://github.com/necantis/HFG>
- **Architecture Version**: `v1.1.0` (12-Agent Architecture + 5-Stage Google Colab Topology)
- **Contract Schema Version**: `1.0.0` / `v1.1.0`
- **Active Analytical Run**: `run_20261111_002`
- **Current Authoritative Pipeline Gates**: **`AGENT_04_RELEASE = BLOCKED`** *(pending Wave 3B CPU `ADR-0008` schema adaptation & canonical manifest registration)* · **Clean-Checkout `AGENT_03_RELEASE = BLOCKED`** *(live Blackwell production dual coding `136/136/0` & initial Agent 03 reconciliation completed in release-bundle run `PR #11`; sensitive coder outputs & runtime benchmark remain gitignored outside Git)*

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

| Agent | Role | Module Ownership | Tracked Notebooks | Output Authority |
| :--- | :--- | :--- | :--- | :--- |
| **Agent 00** | System Architect | [`src/contracts.py`](src/contracts.py), [`schemas/interfaces.json`](schemas/interfaces.json), [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | *(planned `00_architecture_exploration.ipynb`)* | Systemic invariants, 20 contracts & `ADR-0008` policy |
| **Agent 01** | Data & Question Registry | [`src/ingest/`](src/ingest/ingestion.py), [`src/registry/`](src/registry/question_registry.py) | [`notebooks/00_control_plane.ipynb`](notebooks/00_control_plane.ipynb), [`notebooks/01_ingest_exploration.ipynb`](notebooks/01_ingest_exploration.ipynb) | `answers_normalized.parquet` (gitignored) & [`data/normalized/question_registry.json`](data/normalized/question_registry.json) |
| **Agent 02** | Qualitative Coding | [`src/nlp/`](src/nlp/) | [`notebooks/01_gpu_coders.ipynb`](notebooks/01_gpu_coders.ipynb), [`notebooks/02_qualitative_coding.ipynb`](notebooks/02_qualitative_coding.ipynb) | Production dual coding executed on Blackwell (`136/136/0`, outputs gitignored) |
| **Agent 03** | Evidence & Reconciliation | [`src/evidence/`](src/evidence/reconciliation.py) | *(planned `03_evidence_reconciliation.ipynb`)* | Initial production reconciliation completed (`PR #11`); **Wave-3B CPU `ADR-0008` crosswalk/uncertainty-set adaptation pending** |
| **Agent 04** | Preference, Utility & Pareto | `src/preference/` *(pending; `ISSUE-005` resolved by `ADR-0008`)* | *(planned `02_math_analysis.ipynb`, `04_preference_utility_pareto.ipynb`)* | `preference_matrix.parquet`, `GovernanceSolution`, 4-state `RobustParetoResult` (**`AGENT_04_RELEASE = BLOCKED` pending Wave 3B**) |
| **Agent 05** | Preference Profiles / Clustering | `src/clustering/` *(pending)* | *(planned `05_preference_profiles_clustering.ipynb`)* | `preference_profiles.json` (interpretive only, non-pruning) |
| **Agent 06** | Voting & Social Choice | `src/voting/` *(pending)* | *(planned `06_voting_social_choice.ipynb`)* | `voting_results.json` (Borda/Condorcet/Minimax + conditional Baldwin/RRV) |
| **Agent 07** | GPU Runtime | [`src/runtime/`](src/runtime/model_runtime.py) | [`notebooks/07_gpu_runtime.ipynb`](notebooks/07_gpu_runtime.ipynb), [`notebooks/01_gpu_coders.ipynb`](notebooks/01_gpu_coders.ipynb), [`notebooks/HFG_live_execution.ipynb`](notebooks/HFG_live_execution.ipynb) | [`runs/run_20261111_002/gpu_runtime_config.json`](runs/run_20261111_002/gpu_runtime_config.json), dual vLLM execution & WAL checkpoints |
| **Agent 08** | Policy Report | `src/reporting/` *(pending)* | *(planned `03_report.ipynb`, `08_reporting.ipynb`)* | `runs/<run_id>/reports/policy_brief.md` (sink-only deliverable) |
| **Agent 09** | Final Integration Reviewer | `src/review/` *(pending)* | *(planned `09_integration_review.ipynb`)* | Independent end-to-end invariant audit (never orchestrates) |
| **Agent 10** | Documentation, Memory & Artifacts | [`src/artifact_registry.py`](src/artifact_registry.py), [`src/context_pack.py`](src/context_pack.py), [`src/freshness_checker.py`](src/freshness_checker.py), [`docs/`](docs/), [`AGENTS.md`](AGENTS.md) | *(planned `10_memory_and_registry.ipynb`)* | Governance ADRs, audit docs, context packs, manifests & run cards |
| **Agent 11** | Orchestration & QA | [`src/pipeline/orchestrator.py`](src/pipeline/orchestrator.py), [`src/hardcoding_scanner.py`](src/hardcoding_scanner.py) | [`notebooks/00_control_plane.ipynb`](notebooks/00_control_plane.ipynb), [`notebooks/04_validation.ipynb`](notebooks/04_validation.ipynb) | Gate 1 verification, A–H validation, Agent 03 + 9-condition Agent 04 release gates & release QA |

Under [`ADR-0007`](docs/DECISIONS/ADR-0007-git-collaboration-shared-file-ownership-and-artifact-handoff.md), implementation agents develop exclusively on dedicated task branches (`agent/*`) in isolated worktrees/clones and submit formal handoffs ([`docs/AGENT_HANDOFFS/`](docs/AGENT_HANDOFFS/)), while **Agent 11** owns cross-branch integration, combined QA, and release-gate enforcement before merges to `main`.

---

## Pipeline

### Analytical Dependency Order

Every analytical run progresses strictly along this evidence-derived DAG:

```text
data/raw/survey_raw.csv (immutable external CSV, SHA-256 verified)
  -> Agent 01: Deterministic Normalization & Question Registry (Gate 1)
  -> Agent 02: Dual-Pass Qualitative Coding Contracts & Prompt Builders (Gate 2)
  -> Agent 07: Hardware Preflight, 5-Stage GPU Benchmark & vLLM Server Runtime
  -> Independent Qualitative Execution [PRODUCTION CODING COMPLETED ON BLACKWELL; GITIGNORED]:
       Coder A (DeepSeek reasoning family)  +  Coder B (independent Mistral family)
  -> Agent 11 Validation Gate (Checks A-H + 13-condition AGENT_03_RELEASE gate)
  -> Agent 03: Evidence Span Ledger & Initial Reconciliation [COMPLETED IN PR #11; WAVE-3B ADR-0008 SCHEMA ADAPTATION PENDING]
  -> Agent 11 Agent 04 Gate (9-condition AGENT_04_RELEASE gate) [CURRENTLY BLOCKED]
  -> Agent 04: Uncertainty-Set PreferenceMatrix -> Interpretation-Aware ParticipantUtility -> Constraint-Only Solutions -> Exact & 4-State Robust Pareto
  -> Agent 05 (Missingness-Masked Preference Profiles) + Agent 06 (Social Choice & Conditional Baldwin/RRV)
  -> Agent 08 (Evidence-Bound Sink Policy Brief) + Agent 09 (Independent Final Integration Review)
```

### Implementation Order vs. Analytical Dependency Order

Auditors must distinguish **development/integration chronology** from **analytical runtime execution order**:

1. **Implementation & Hardening Order (Completed on `main` through PR `#13`)**: Persistent memory (`ADR-0001`–`0004`) → 20 data contracts (`ADR-0005`, `ADR-0006`) → raw survey lock (`run_20261111_002`) → Git collaboration policy (`ADR-0007`, PR `#1`) → Agent 01 & Agent 02 refinements (Wave 2A, PR `#2`) → Agent 07 runtime persistence & Colab preflight (PR `#4`) → Agent 11 orchestration & hard release gate (PR `#5`) → live vLLM launcher, 5-stage benchmark, dual-coder runner, JSON recovery ladder, execution profiles, external checkpoints, and `smoke_tiny` scoping fixes (PRs `#6`–`#9`) → audit documentation & live runner tracking (PR `#10`, `ef716ac`) → Agent 03 `src/evidence/` ledger & initial reconciliation against live Blackwell production coding (PR `#11`) → [`ADR-0008`](docs/DECISIONS/ADR-0008-dual-coder-preference-reconciliation-and-uncertainty.md) methodological policy (PR `#12`) → shared contract updates & 9-condition `Agent04ReleaseDecision` gate (PR `#13`).
2. **Analytical Dependency Order (Runtime State Today)**: Live Blackwell `production` dual coding (`136/136/0`) and initial Agent 03 reconciliation (`284` cells, `84` subtopics, `219` options, `107` values, `0` silent averages) **completed** in the release-bundle workflow (`PR #11`), while gitignored runtime coder/benchmark JSONs remain outside Git. **Wave 3B** (Agent 03 CPU `ADR-0008` crosswalk & uncertainty-set emission + canonical manifest registration + benchmark sync) is required before `AGENT_04_RELEASE` transitions from **`BLOCKED`** to `READY`; Agents 04–09 remain unexecuted.

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

### Readiness Classification (`origin/main` = `92386cd` / PR `#13` + `PR #11` Runtime Evidence)

| Coder / Profile | Configured Model Repo & Revision | Stage Status |
| :--- | :--- | :--- |
| **Production Coder A** *(PR #8 `src/runtime/model_runtime.py`)* | `Valdemardi/DeepSeek-R1-Distill-Qwen-32B-AWQ` (`AWQ-INT4`, `rev: 1de6a3f7b151f6ea0f6d42acb3566e094eb8a264`) | **Production-Completed** on live Colab Blackwell (`136/136/0`, `18` non-preference cells preserved, `0` span errors per [`docs/AGENT_HANDOFFS/agent_03_handoff.md`](docs/AGENT_HANDOFFS/agent_03_handoff.md)); gitignored JSON excluded from Git |
| **Production Coder B** *(PR #8 `src/runtime/model_runtime.py`)* | `RedHatAI/Mistral-Small-3.1-24B-Instruct-2503-quantized.w4a16` (`W4A16-INT4`, `rev: dc0a9d9df93998ec3163cabca261715c0bbee4f6`) *(Alt: `pytorch/gemma-3-27b-it-AWQ-INT4`)* | **Production-Completed** on live Colab Blackwell (`136/136/0`, `18` non-preference cells preserved, `0` span errors per [`docs/AGENT_HANDOFFS/agent_03_handoff.md`](docs/AGENT_HANDOFFS/agent_03_handoff.md)); gitignored JSON excluded from Git |
| **Smoke Coder A** *(PR #9 `smoke_tiny`)* | `deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B` (`BF16`, `max_model_len=4096`, `max_output_tokens=2048`) | **Configured** *(Unit-tested with mock server)* |
| **Smoke Coder B** *(PR #9 `smoke_tiny`)* | `HuggingFaceTB/SmolLM2-1.7B-Instruct` (`BF16`, `max_model_len=4096`, `max_output_tokens=2048`) | **Configured** *(Unit-tested with mock server)* |

**Explicit Readiness Accounting**:
- **Configured**: Yes (pinned 40-char HF revisions in [`src/runtime/model_runtime.py`](src/runtime/model_runtime.py); legacy PR `#5` preflight snapshot in [`runs/run_20261111_002/gpu_runtime_config.json`](runs/run_20261111_002/gpu_runtime_config.json)).
- **Resolved** (live Hugging Face Hub metadata verification + remote commit resolution): Verified during live Blackwell production coding (`resolve_dual_coder_specs`); tracked PR `#5` config still lists pre-pinning `remote_repo_validated = false`.
- **Benchmarked** (5-stage live GPU benchmark `runs/<run_id>/gpu_runtime_benchmark.json`): Not yet synced into tracked Git canonical state (`ISSUE-007` remains `OPEN`).
- **Pilot-Validated** (`pilot_subset` live GPU run): Not separately archived in canonical Git state.
- **Production-Completed** (`production` dual-coder outputs passing checks A–H): **`True` on release bundle** (`136/136/0`, `common source_evidence_hash` verified and consumed by Agent 03 in PR `#11`); gitignored JSONs remain outside Git, so clean Git checkouts show `AGENT_03_RELEASE = BLOCKED` locally unless staged.

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

Full step-by-step instructions across CPU validation, `smoke_tiny`, `pilot_subset`, `production`, and final validation are documented in **[`docs/REPRODUCIBILITY.md`](docs/REPRODUCIBILITY.md)**. High-level canonical sequence:

1. **Clone & Install Dependencies**:
   ```bash
   git clone https://github.com/necantis/HFG.git && cd HFG
   python3 -m venv .venv && .venv/bin/pip install -e .
   ```
2. **Deterministic Ingestion & Gate 1 (CPU)**:
   ```bash
   .venv/bin/python -m src.ingest.ingestion
   .venv/bin/python -m src.hardcoding_scanner --check-gate-1
   ```
   *(Or run [`notebooks/00_control_plane.ipynb`](notebooks/00_control_plane.ipynb) on Colab, which automatically regenerates gitignored normalized files from `data/raw/survey_raw.csv`.)*
3. **5-Stage Live GPU Benchmark (GPU Host / Colab)**:
   Run [`notebooks/07_gpu_runtime.ipynb`](notebooks/07_gpu_runtime.ipynb) (or `.venv/bin/python -m src.runtime.model_runtime`) on a CUDA GPU runtime to resolve Hugging Face repos and produce `runs/<run_id>/gpu_runtime_benchmark.json`.
4. **Dual-Coder Qualitative Execution (GPU Host / Colab)**:
   Execute [`notebooks/01_gpu_coders.ipynb`](notebooks/01_gpu_coders.ipynb) (or `.venv/bin/python -m src.runtime.dual_coder_runner`) with `HFG_EXECUTION_PROFILE` set explicitly to `smoke_tiny`, `pilot_subset`, or `production`, and optional durable `HFG_CHECKPOINT_ROOT`.
5. **Release Gate & QA Validation (CPU)**:
   Run `.venv/bin/pytest tests/ -v`, `.venv/bin/python -m src.freshness_checker --check-all`, `.venv/bin/python -m src.hardcoding_scanner --scan`, and `.venv/bin/python -m src.pipeline.orchestrator` (or [`notebooks/04_validation.ipynb`](notebooks/04_validation.ipynb)).

---

## Evidence Provenance

HFG requires an unbroken cryptographic and structural chain from raw survey text to analytical claims (full inventory in **[`docs/ARTIFACT_PROVENANCE.md`](docs/ARTIFACT_PROVENANCE.md)**):

```text
raw source (data/raw/survey_raw.csv, SHA-256)
  -> normalized response (data/normalized/answers_normalized.parquet, source_hash)
  -> participant_id / question_id / response_id coordinates
  -> source / EvidenceSpan (exact_quote, start_char, end_char, offset_reference_text)
  -> independent coder output (coder_a_outputs.json & coder_b_outputs.json, prompt_hash + model_revision)
  -> dual-coder reconciliation (candidate_options.json, themes_codebook.json, Level 2 CanonicalAlternativeCrosswalk & PreferenceUncertaintySet; zero silent averaging)
  -> PreferenceMatrix (PreferenceUncertaintySet + alternative_probabilities summing to 1.0 +/- 1e-4 when consensus/resolved, missingness_state separate)
  -> ParticipantUtility (interpretation-aware operators derived strictly from PreferenceMatrix; zero coder_confidence weighting)
  -> Pareto & 4-State Robust Pareto Analysis (constraint-pruned GovernanceSolution only)
```

---

## Validation and QA

Four automated quality gates govern repository integrity and release readiness:

1. **`pytest` Suite ([`tests/`](tests/))**: Verifies schemas, memory registry, context packs, freshness checks, collaboration policy, ingestion invariants, NLP coding/repair logic, Agent 03 evidence ledger & reconciliation, `ADR-0008` uncertainty/crosswalk contracts (`tests/test_contracts_adr0008.py`), GPU runtime & JSON recovery ladder, and orchestration gates (`118` passed on clean CPU checkout, `1` integration test skipped locally when gitignored runtime outputs are absent).
2. **`FreshnessChecker` ([`src/freshness_checker.py`](src/freshness_checker.py))**: 9-category audit checking stale documentation, schema versions, obsolete filenames, deprecated model names, notebook ownership, superseded ADRs, manifest provenance, unresolved evidence IDs, and stale upstream chains.
3. **`HardcodingScanner` ([`src/hardcoding_scanner.py`](src/hardcoding_scanner.py))**: Static AST/regex scan across `src/` and `notebooks/` blocking foreign survey entities, hardcoded packages, deprecated models, or fixed hardware assumptions, plus `verify_gate_1`.
4. **`PipelineOrchestrator` & Dual Release Gates ([`src/pipeline/orchestrator.py`](src/pipeline/orchestrator.py))**: Evaluates progression across `AGENT_03_RELEASE` (13 conditions + checks A–H) and **`AGENT_04_RELEASE`** (9 mandatory `ADR-0008` conditions in [`Agent04ReleaseDecision`](src/pipeline/orchestrator.py), keeping Agent 04 **`BLOCKED`** pending Wave 3B completion).

---

## Repository Map

- **Governance & Agent Rules**: [`AGENTS.md`](AGENTS.md)
- **System Architecture**: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- **20+ Data Contracts & Schemas (`ADR-0008`-Aligned)**: [`docs/DATA_CONTRACTS.md`](docs/DATA_CONTRACTS.md) · [`src/contracts.py`](src/contracts.py) · [`schemas/interfaces.json`](schemas/interfaces.json)
- **Authoritative Project State Snapshot**: [`docs/PROJECT_STATE.md`](docs/PROJECT_STATE.md) *(synchronized through PR `#13` & `ADR-0008`; see [`docs/AUDIT_TRAIL.md`](docs/AUDIT_TRAIL.md) for historical PR ledger)*
- **Chronological Audit Trail**: [`docs/AUDIT_TRAIL.md`](docs/AUDIT_TRAIL.md)
- **Reproducibility Guide**: [`docs/REPRODUCIBILITY.md`](docs/REPRODUCIBILITY.md)
- **Artifact Provenance Ledger**: [`docs/ARTIFACT_PROVENANCE.md`](docs/ARTIFACT_PROVENANCE.md)
- **Open Issues & Technical Debt**: [`docs/OPEN_ISSUES.md`](docs/OPEN_ISSUES.md)
- **Notebook Inventory**: [`docs/NOTEBOOK_INDEX.md`](docs/NOTEBOOK_INDEX.md)
- **Architecture Decision Records (`ADR-0001`–`0008`)**: [`docs/DECISIONS/`](docs/DECISIONS/)
- **Agent Handoffs**: [`docs/AGENT_HANDOFFS/`](docs/AGENT_HANDOFFS/)
- **Model Strategy**: [`docs/MODEL_STRATEGY.md`](docs/MODEL_STRATEGY.md)
- **Active Run Card & Manifest**: [`runs/run_20261111_002/RUN_CARD.md`](runs/run_20261111_002/RUN_CARD.md) · [`runs/run_20261111_002/manifest.json`](runs/run_20261111_002/manifest.json)