# Run Card: `run_20261111_002`

- **Run ID**: `run_20261111_002`
- **Updated At**: `2026-11-13T18:02:00+00:00` (Initial raw lock: `2026-11-12T05:33:44.383744+00:00`)
- **Initial Raw Lock Commit**: `414aee57d1aa854ac8922956564049b228ecdcc6`
- **Main Integrated Baseline Commit**: `61417ebcad6f1de1232c596604cd791ab8d784a3` (PR #1 + PR #2 + PR #4)
- **Live Colab GPU Preflight Hardware**: `NVIDIA RTX PRO 6000 Blackwell Server Edition` (`1` GPU, `97887 MB` total VRAM, `97251 MB` free at preflight, CUDA `13.0`, Driver `580.82.07`, Compute Capability `12.0`, CPU `AMD EPYC 9B45`, System RAM `181130 MB`)
- **Live GPU Hardware Preflight Status**: `PASS` (`execution_mode = CONCURRENT_DUAL_SERVER`, `combined_required_mb = 49384`)
- **5-Stage Live GPU Runtime Benchmark Status**: `NOT_EXECUTED` (`derived_from_benchmark = false`; `production_dual_model_validation = false`)
- **Model Quantisations Configured (Unexecuted)**: `Coder A: AWQ-INT4 (deepseek-ai/DeepSeek-R1-Distill-Qwen-32B-AWQ)` | `Coder B: INT4-AWQ (mistralai/Mistral-Small-3.1-24B-Instruct-2503-AWQ)` (`Gemma 3 27B QAT-INT4` alternative)

---

## 1. Input Files & Cryptographic Hashes (SHA-256)
| File Path | SHA-256 Hash |
| :--- | :--- |
| `data/raw/survey_raw.csv` | `56acded3e02be49be27d6b288fa2c43fcce68df24525113eba1b1161eec52a95` |

---

## 2. LLM Models, Prompt Versions & Execution Details
- **Live Dual-LLM Coding Execution**: `NOT_EXECUTED` (`Coder A: NOT_EXECUTED`, `Coder B: NOT_EXECUTED`)
- **Authorization Gate (`verify_full_survey_coding_gates`)**: `AUTHORIZED` (Gate 1 `PASS` + Gate 2 `PASS`; authorizes running dual coding only, does NOT prove dual coding executed)
- **Configured Coder Architecture**: Dual concurrent independent servers (`coder_a` on `localhost:8001`, `coder_b` on `localhost:8002`, `temperature = 0.0`, `seed = 42`) via `notebooks/01_gpu_coders.ipynb`
- **Prompt Provenance Status**: Prompt builders & `source_evidence_hash` verified on CPU unit tests; live runtime model revisions & prompt hashes will be recorded upon Colab execution.

---

## 3. Pipeline Execution Stages & Release Gate Status
- **Completed / Verified Stages**:
  - `Stage 00`: Architecture Invariants & Reconciled 20 Contracts (`src/contracts.py`, `schemas/interfaces.json`)
  - `Stage 01`: Data & Question Registry Ingestion (`src/ingest/ingestion.py`, `src/registry/question_registry.py`, `154` normalized rows across `11` participants: `136` `observed_usable`, `10` `missing_raw_blank`, `6` `missing_non_substantive`, `2` `ambiguous`; `13` primary `QuestionSpec` + optional `Q14`)
  - `Stage 02 (Contracts & Entrance Gate)`: Qualitative Coding Schemas & Engine (`src/nlp/`, CPU unit tests passing, Gate 2 `PASS`)
  - `Stage 07 (Persisted & Preflight PASS)`: GPU Runtime persisted via PR #4 (`src/runtime/model_runtime.py`); live Colab Blackwell hardware preflight `PASS`
  - `Stage 10`: Canonical Manifest & Context Pack Governance (`runs/run_20261111_002/manifest.json` updated with `gpu_runtime_config_v1`)
  - `Stage 11`: Minimal Evidence-Derived Orchestration & Hard Release Gate (`src/pipeline/orchestrator.py`, `notebooks/00_control_plane.ipynb`, `notebooks/04_validation.ipynb`, `tests/test_pipeline.py`)
- **Gate 1 Status**: `PASS` (`0` hardcoding violations; raw SHA-256 verified; `13` primary `QuestionSpec`; `0` imputed cells)
- **Agent 03 Hard Release Gate (`AGENT_03_RELEASE`)**: `BLOCKED`
- **Pending / Blocking Stages (`ISSUE-007`)**:
  - `5-Stage Live GPU Runtime Benchmark`: `NOT_EXECUTED` (no `runs/run_20261111_002/gpu_runtime_benchmark.json`)
  - `Live Coder A & Independent Coder B Inference`: `NOT_EXECUTED` (no persisted dual-coder qualitative outputs under `data/processed/` or `.checkpoints/gpu_coder_wal/`)
  - `Stage 03–09 (Evidence Reconciliation, PreferenceMatrix/Pareto, Clustering, Voting, Reporting, Review)`: Strictly blocked pending live dual-coder outputs, A–H validation, and `ISSUE-005` resolution for Agent 04.

---

## 4. Registered Artifacts (`runs/run_20261111_002/manifest.json`)
| Artifact ID | Authority Level | Format | Producing Agent | Commit SHA | Status | Freshness | Path |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `raw_survey_v1` | `immutable_source` | `csv` | `external_stakeholder_survey` | `414aee57d1aa854ac8922956564049b228ecdcc6` | `valid` | `fresh` | `data/raw/survey_raw.csv` |
| `norm_answers_v1` | `canonical_ingestion` | `parquet` | `agent_01` | `f83c32952c568dafa415463eb73ca1911b175377` | `valid` | `fresh` | `data/normalized/answers_normalized.parquet` |
| `question_registry_v1` | `canonical_intermediate` | `json` | `agent_01` | `f83c32952c568dafa415463eb73ca1911b175377` | `valid` | `fresh` | `data/normalized/question_registry.json` |
| `gpu_runtime_config_v1` | `canonical_intermediate` | `json` | `agent_07` | `61417ebcad6f1de1232c596604cd791ab8d784a3` | `valid` | `fresh` | `runs/run_20261111_002/gpu_runtime_config.json` |

---
> **Analytical Certification**: This run card certifies immutable inputs, Gate 1 (`PASS`), live Colab Blackwell hardware preflight (`PASS`), Gate 2 authorization (`AUTHORIZED`), and truthful enforcement of `AGENT_03_RELEASE = BLOCKED` while the 5-stage live GPU benchmark and real dual-LLM coding remain `NOT_EXECUTED`.
