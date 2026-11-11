# Run Card: `run_20261111_001`

- **Run ID**: `run_20261111_001`
- **Generated At**: `2026-11-11T16:48:51.775763+00:00`
- **Git Commit**: `e15369ac9db3cbd9d4773f7a20f3ee2841c2fd9d`
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
- **Completed Stages**: `Stage 00 (Architecture Invariants)`, `Stage 10 (Registry & Context Freeze)`
- **Retries**: `0`
- **Failures**: `0`
- **Skipped Modules**: {'Stage 01-09, 11': 'Awaiting downstream agent executions'}

### Stage Runtimes (seconds)
| Stage | Runtime (s) |
| :--- | :--- |
| `stage_00_spec` | 0.05s |
| `stage_10_freeze` | 0.08s |

---

## 4. Final Registered Artifacts
| Artifact ID | Authority Level | Format | Producing Agent | Status | Freshness | Path |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `raw_survey_v1` | `immutable_source` | `csv` | `external_stakeholder_survey` | `valid` | `fresh` | `data/raw/survey_raw.csv` |

---
> **Analytical Certification**: This run card certifies immutable inputs, deterministic reproducibility, and strict compliance with HFG analytical invariants.
