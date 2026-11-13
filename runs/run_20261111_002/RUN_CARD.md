# Run Card: `run_20261111_002`

- **Run ID**: `run_20261111_002`
- **Generated At**: `2026-11-12T05:33:44.383744+00:00`
- **Git Commit**: `414aee57d1aa854ac8922956564049b228ecdcc6`
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
- **Completed Stages**: `Stage 00 (Architecture Invariants)`, `Stage 01 (Data & Question Registry)`, `Stage 10 (Registry & Context Freeze)`
- **Gate 1 Status**: `PASSED` (Hardcoding scanner: 0 violations; 13 substantive QuestionSpecs; missingness explicitly preserved)
- **Retries**: `0`
- **Failures**: `0`
- **Skipped Modules**: {'Stage 02-09, 11': 'Awaiting downstream agent executions'}

### Stage Runtimes (seconds)
| Stage | Runtime (s) |
| :--- | :--- |
| `stage_00_spec` | 0.05s |
| `stage_01_ingest` | 0.42s |
| `stage_10_freeze` | 0.08s |

---

## 4. Final Registered Artifacts
| Artifact ID | Authority Level | Format | Producing Agent | Status | Freshness | Path |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `raw_survey_v1` | `immutable_source` | `csv` | `external_stakeholder_survey` | `valid` | `fresh` | `data/raw/survey_raw.csv` |
| `norm_answers_v1` | `canonical_ingestion` | `parquet` | `agent_01` | `valid` | `fresh` | `data/normalized/answers_normalized.parquet` |
| `question_registry_v1` | `canonical_intermediate` | `json` | `agent_01` | `valid` | `fresh` | `data/normalized/question_registry.json` |

---
> **Analytical Certification**: This run card certifies immutable inputs, deterministic reproducibility, and strict compliance with HFG analytical invariants.
