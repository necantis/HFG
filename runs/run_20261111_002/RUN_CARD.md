# Run Card: `run_20261111_002`

- **Run ID**: `run_20261111_002`
- **Updated At**: `2026-11-14T13:58:00+00:00` (Initial raw lock: `2026-11-12T05:33:44.383744+00:00`)
- **Initial Raw Lock Commit**: `414aee57d1aa854ac8922956564049b228ecdcc6`
- **Main Integrated Baseline Commit**: `d322b1872b8ea79d1fa5e9e763ef08392bf158f9` (PR `#1`–PR `#16`)
- **Live Colab GPU Preflight Hardware**: `NVIDIA RTX PRO 6000 Blackwell Server Edition` (`1` GPU, `97887 MB` total VRAM, `97251 MB` free at preflight, CUDA `13.0`, Driver `580.82.07`, Compute Capability `12.0`, CPU `AMD EPYC 9B45`, System RAM `181130 MB`)
- **Live GPU Hardware Preflight & 5-Stage Benchmark Status**: `PASS` (`EXECUTED_LIVE_GPU`, `gpu_runtime_benchmark.json` SHA-256 `bc8e6d228ec471225377c77d1ee4fecb518b678ee425069199eb1ccb95e23ba4`, `production_release.json` SHA-256 `c4cda5c49cb5cd78a49b51423c530b5723e1c60f2de52afbfb20a9420c0716c0`)
- **Pinned Production Coder Models (`src/runtime/model_runtime.py`)**: `Coder A: Valdemardi/DeepSeek-R1-Distill-Qwen-32B-AWQ @ 1de6a3f7b151f6ea0f6d42acb3566e094eb8a264` | `Coder B: RedHatAI/Mistral-Small-3.1-24B-Instruct-2503-quantized.w4a16 @ dc0a9d9df93998ec3163cabca261715c0bbee4f6`

---

## 1. Input Files & Verified Bundle Provenance (SHA-256)
| File Path | Digest / Notes |
| :--- | :--- |
| `data/raw/survey_raw.csv` | SHA-256: `56acded3e02be49be27d6b288fa2c43fcce68df24525113eba1b1161eec52a95` \| Git blob SHA-1: `eb526813aadcfab2b4b157e7b6513de50e6b3178` |
| `runs/run_20261111_002/alternative_crosswalk.json` | SHA-256: `8fa47137fe3d73efea4835fedc90f21c40920a510d03b9e67844b961bf6dc600` (`17` scoped rules, PR `#15`) |
| `data/processed/coder_a_outputs.json` *(transient/gitignored)* | SHA-256: `8939adc884672a1cdf883e496f476a872248d90d4f8da8f3549d29e24b20dadf` (`136/136/0`, prompt hash `4d1279f046aa4460707cb81b4e291cce30179cc060659fcdb4f796e224864377`) |
| `data/processed/coder_b_outputs.json` *(transient/gitignored)* | SHA-256: `129c7257c1c4fdf9f3b88067b96180cf68ebd3056f41e0880fd5831d48ffcd49` (`136/136/0`, prompt hash `d880fc917663268813188f833ad0bd7b0a2a3fa26a3096df5e36959965e3083b`) |
| `runs/run_20261111_002/gpu_runtime_benchmark.json` *(transient)* | SHA-256: `bc8e6d228ec471225377c77d1ee4fecb518b678ee425069199eb1ccb95e23ba4` (`EXECUTED_LIVE_GPU`) |

---

## 2. LLM Models, Prompt Versions & Wave-3B ADR-0008 Reconciliation Provenance
- **Common `source_evidence_hash`**: `0b814c3b6f6a88ec8e5d895a025cb146ed2e73e08f814ace145c0237c17c9753`
- **Dual-Coder Validation (Checks A–H)**: `8/8 PASS` (`0` violations; `136/136/0` usable responses + `18` non-preference cells preserved)
- **ADR-0008 CPU Reconciliation (`python -m src.evidence.reconciliation`)**: `284` preference records; `NONE_CONSENSUS = 12`, `INTERPRETATION_DIVERGENCE = 30`, `DUAL_CODER_DISTRIBUTION_SET = 36`, `CROSSWALK_PARTIAL_OR_UNALIGNED = 30`, `SINGLE_CODER_PARTIAL_ID_GRANULARITY = 130`, `SINGLE_CODER_PARTIAL_ID_OMISSION = 28` (`158` single-coder total), `PRESERVED_MISSINGNESS = 18`; `DATA_CONTRACT_VIOLATION = 0`; `16/16` QA checks `PASS`; `0` forbidden methods or silent averages.
- **Deterministic Hash Note**: `data/processed/reconciliation/coder_agreement_stats.json` matches Agent 03 bit-for-bit (`26419a3348a7f7d51f72a04ff5d174157aac4495de2b45bbb9806cf6cfca6e11`); the remaining 8 regenerated JSONs differ only in embedded runtime UTC timestamps (`generated_at_utc` / `evaluated_at_utc`) and `git_commit_sha` (`d322b187...` vs pre-merge Agent 03 commit), with 100% identical analytical counts and payloads.

---

## 3. Pipeline Execution Stages & Release Gate Status
- **Completed / Verified Stages**:
  - `Stage 00`: Architecture Invariants, 20 Contracts & `ADR-0008` (`PR #12`, `PR #13`; `PROHIBITED_PRUNING_SOURCES` & 4-state `RobustParetoResult` enforced)
  - `Stage 01`: Data & Question Registry Ingestion (`src/ingest/ingestion.py`, `src/registry/question_registry.py`, Gate 1 `PASS`: `154` rows / `11` participants: `136` `observed_usable`, `10` `missing_raw_blank`, `6` `missing_non_substantive`, `2` `ambiguous`; `13` primary `QuestionSpec` + `Q14`)
  - `Stage 02`: Qualitative Dual Coding (`136/136/0` per coder on RTX PRO 6000 Blackwell; Checks A–H `PASS`)
  - `Stage 03`: CPU-Only `ADR-0008` Evidence Reconciliation (`src/evidence/reconciliation.py`, `16/16` QA `PASS`, `284` records, `185` options, `107` values, `84` canonical subtopics, `262` unresolved diagnostics)
  - `Stage 07`: GPU Runtime & 5-Stage Live Benchmark verified (`EXECUTED_LIVE_GPU`)
  - `Stage 10`: `ISSUE-005` synced `RESOLVED`, context packs `00`–`11` updated (`PR #14`)
  - `Stage 11`: Orchestration, Hardcoding Scanner (`0` hits), Freshness Checker (`9/9` PASS), Canonical Manifest Registration (`runs/run_20261111_002/manifest.json`)
- **Hard Release Gate Decisions (`python -m src.pipeline.orchestrator`)**:
  - **`AGENT_03_RELEASE`**: `READY` (`13/13` conditions pass)
  - **`AGENT_04_RELEASE`**: `READY` (`9/9` conditions pass; `highest_verified_state = AGENT_04_RELEASE_READY`)

---

## 4. Registered Artifacts (`runs/run_20261111_002/manifest.json`)
| Artifact ID | Authority Level | Format | Producing Agent | Validation | Freshness | Path |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `raw_survey_v1` | `immutable_source` | `csv` | `external_stakeholder_survey` | `valid` | `fresh` | `data/raw/survey_raw.csv` |
| `norm_answers_v1` | `canonical_ingestion` | `parquet` | `agent_01` | `valid` | `fresh` | `data/normalized/answers_normalized.parquet` |
| `question_registry_v1` | `canonical_intermediate` | `json` | `agent_01` | `valid` | `fresh` | `data/normalized/question_registry.json` |
| `gpu_runtime_config_v1` | `canonical_intermediate` | `json` | `agent_07` | `valid` | `fresh` | `runs/run_20261111_002/gpu_runtime_config.json` |
| `themes_codebook_v1` | `canonical_intermediate` | `json` | `agent_03` | `valid` | `fresh` | `data/processed/themes_codebook.json` |
| `candidate_options_v1` | `canonical_intermediate` | `json` | `agent_03` | `valid` | `fresh` | `data/processed/candidate_options.json` |
| `reconciled_evidence_v1` | `canonical_intermediate` | `json` | `agent_03` | `valid` | `fresh` | `data/processed/reconciliation/reconciled_evidence.json` |
| `subtopic_alignment_v1` | `canonical_intermediate` | `json` | `agent_03` | `valid` | `fresh` | `data/processed/reconciliation/subtopic_alignment.json` |
| `reconciled_values_v1` | `canonical_intermediate` | `json` | `agent_03` | `valid` | `fresh` | `data/processed/reconciliation/reconciled_values.json` |
| `coder_agreement_stats_v1` | `canonical_intermediate` | `json` | `agent_03` | `valid` | `fresh` | `data/processed/reconciliation/coder_agreement_stats.json` |
| `unresolved_cases_registry_v1` | `canonical_intermediate` | `json` | `agent_03` | `valid` | `fresh` | `data/processed/reconciliation/unresolved_cases_registry.json` |
| `alternative_crosswalk_summary_v1` | `canonical_intermediate` | `json` | `agent_03` | `valid` | `fresh` | `data/processed/reconciliation/alternative_crosswalk_summary.json` |
| `reconciliation_qa_report_v1` | `canonical_intermediate` | `json` | `agent_03` | `valid` | `fresh` | `data/processed/reconciliation/reconciliation_qa_report.json` |

---
> **Analytical Certification**: This run card certifies frozen Blackwell dual-coder provenance, `AGENT_03_RELEASE = READY` (`13/13`), `ADR-0008` CPU reconciliation (`16/16` QA checks, `DATA_CONTRACT_VIOLATION = 0`), canonical metadata registration in `runs/run_20261111_002/manifest.json` without committing sensitive runtime payloads, and `AGENT_04_RELEASE = READY` (`9/9`).
