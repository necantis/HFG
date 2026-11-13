# Run Card: `run_20261111_002`

- **Run ID**: `run_20261111_002`
- **Generated At**: `2026-11-13T07:46:22+00:00` (Initial raw lock: `2026-11-12T05:33:44.383744+00:00`)
- **Initial Raw Lock Commit**: `414aee57d1aa854ac8922956564049b228ecdcc6`
- **Wave 2A Integration Code Commit**: `f83c32952c568dafa415463eb73ca1911b175377`
- **Hardware Architecture**: `Debian 12 Linux x86_64 (CPU Integration / QA Verification Only)`
- **GPU Hardware Benchmark Status**: `NOT_EXECUTED` (Colab NVIDIA RTX PRO 6000 Blackwell execution pending recovery of `src/runtime/` & `notebooks/01_gpu_coders.ipynb`)
- **Model Quantisations**: `N/A (No live LLM execution performed on this branch)`

---

## 1. Input Files & Cryptographic Hashes (SHA-256)
| File Path | SHA-256 Hash |
| :--- | :--- |
| `data/raw/survey_raw.csv` | `56acded3e02be49be27d6b288fa2c43fcce68df24525113eba1b1161eec52a95` |

---

## 2. LLM Models, Prompt Versions & Execution Details
- **Live Dual-LLM Coding Execution**: `NOT_EXECUTED` (CPU fixture & unit contract verification only)
- **Planned Coder Architecture**: Dual concurrent independent coders (`coder_a`, `coder_b`, `temperature = 0.0`) on Colab GPU via `notebooks/01_gpu_coders.ipynb`
- **Prompt Provenance Status**: Prompt builders & `source_evidence_hash` verified on CPU fixtures; runtime model revisions will be recorded upon Colab GPU execution.

---

## 3. Pipeline Execution Stages & Reliability
- **Completed Stages**:
  - `Stage 00`: Architecture Invariants & Reconciled 20 Contracts (`src/contracts.py`, `schemas/interfaces.json`)
  - `Stage 01`: Data & Question Registry Ingestion (`src/ingest/ingestion.py`, `src/registry/question_registry.py`, 154 normalized rows, 13 primary QuestionSpecs + optional Q14)
  - `Stage 02 (CPU Engine Integrated)`: Qualitative Coding Schemas & Engine (`src/nlp/` — unit & integration corpus checks passing)
  - `Stage 10`: Canonical Manifest & Context Pack Refresh (`runs/run_20261111_002/manifest.json`, `docs/AGENT_CONTEXT/`)
- **Gate 1 Status**: `PASS` (Hardcoding scanner: 0 violations; raw SHA-256 verified; 13 primary QuestionSpecs; missingness preserved with 0 imputed cells)
- **Retries**: `0`
- **Failures**: `0`
- **Pending / Blocked Stages**:
  - `Agent 07 GPU Runtime` & `Agent 11 Orchestration/QA`: Prior unpushed modules unrecoverable (`RECOVERY_REQUIRED` — `ISSUE-006`)
  - `Colab GPU Dual-LLM Coding`: `NOT_EXECUTED`
  - `Stage 03–09 (Evidence Reconciliation, PreferenceMatrix/Pareto, Clustering, Voting, Reporting, Review)`: Pending Wave 2B integration & `ISSUE-005` methodological resolution for Agent 04

---

## 4. Final Registered Artifacts
| Artifact ID | Authority Level | Format | Producing Agent | Commit SHA | Status | Freshness | Path |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `raw_survey_v1` | `immutable_source` | `csv` | `external_stakeholder_survey` | `414aee57d1aa854ac8922956564049b228ecdcc6` | `valid` | `fresh` | `data/raw/survey_raw.csv` |
| `norm_answers_v1` | `canonical_ingestion` | `parquet` | `agent_01` | `f83c32952c568dafa415463eb73ca1911b175377` | `valid` | `fresh` | `data/normalized/answers_normalized.parquet` |
| `question_registry_v1` | `canonical_intermediate` | `json` | `agent_01` | `f83c32952c568dafa415463eb73ca1911b175377` | `valid` | `fresh` | `data/normalized/question_registry.json` |

---
> **Analytical Certification**: This run card certifies immutable inputs, deterministic ingestion & contract reconciliation on `integration/wave-2a`, and truthful reporting that Colab GPU execution remains `NOT_EXECUTED` until missing runtime/control-plane modules are recovered.
