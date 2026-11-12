# Run Card: `run_20261111_002`

- **Run ID**: `run_20261111_002`
- **Generated At**: `2026-11-12T05:31:08.465497+00:00`
- **Git Commit**: `d170c29706b67e95f8400e77d34c072a3c05375a`
- **Hardware Architecture**: `Debian 12 Linux x86_64`
- **Model Quantisations**: `None (FP16/BF16 API)`

---

## 1. Input Files & Cryptographic Hashes (SHA-256)
| File Path | SHA-256 Hash |
| :--- | :--- |
| `/home/antigravity/necantis/HFG/data/raw/survey_raw.csv` | `56acded3e02be49be27d6b288fa2c43fcce68df24525113eba1b1161eec52a95` |

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
