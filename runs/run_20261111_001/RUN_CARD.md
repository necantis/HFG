# Run Card: `run_20261111_001`

- **Run ID**: `run_20261111_001`
- **Generated At**: `2026-11-11T15:29:04.534110+00:00`
- **Git Commit**: `7f1ebe6ff71977b40da9f9b980c5887114568ef1`
- **Hardware Architecture**: `Debian 12 Linux x86_64`
- **Model Quantisations**: `None (FP16/BF16 API)`

---

## 1. Input Files & Cryptographic Hashes (SHA-256)
| File Path | SHA-256 Hash |
| :--- | :--- |
| `/home/antigravity/necantis/HFG/data/raw/survey_raw.csv` | `d5da57a02403cfbe3e267b48590ae75dce923bc47da3a0037da0d42fab88b963` |

---

## 2. LLM Models, Prompt Versions & Execution Details
- **LLM Models & Revisions**:
  - **qualitative_coding**: `pro`
  - **social_choice**: `flash`
- **Prompt Versions & Hashes**:
  - **system_v1**: `sha256:baseline_system_prompt`
  - **coding_v1**: `sha256:baseline_coding_prompt`

---

## 3. Pipeline Execution Stages & Reliability
- **Completed Stages**: `Stage 0 (Source Ingestion & Registry Lock)`, `Stage 9 (Run Card Freeze)`
- **Retries**: `0`
- **Failures**: `0`
- **Skipped Modules**: {'Stage 1-8': 'Awaiting downstream agent executions'}

### Stage Runtimes (seconds)
| Stage | Runtime (s) |
| :--- | :--- |
| `stage_0_ingest_lock` | 0.05s |
| `stage_9_freeze` | 0.08s |

---

## 4. Final Registered Artifacts
| Artifact ID | Authority Level | Format | Producing Agent | Status | Freshness | Path |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `raw_survey_v1` | `immutable_source` | `csv` | `external_stakeholder_survey` | `valid` | `fresh` | `data/raw/survey_raw.csv` |

---
> **Analytical Certification**: This run card certifies immutable inputs, deterministic reproducibility, and strict compliance with HFG analytical invariants.
