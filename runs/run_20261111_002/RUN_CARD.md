# Run Card: `run_20261111_002`

- **Run ID**: `run_20261111_002`
- **Updated At**: `2026-11-14T13:15:00+00:00` (Initial raw lock: `2026-11-12T05:33:44.383744+00:00`)
- **Initial Raw Lock Commit**: `414aee57d1aa854ac8922956564049b228ecdcc6`
- **Main Integrated Baseline Commit Evaluated**: `baef68b4f3efa04d3e442591a747ad2d8fd26fd2` (PR `#1`–PR `#15`)
- **Live Colab GPU Preflight Hardware**: `NVIDIA RTX PRO 6000 Blackwell Server Edition` (`1` GPU, `97887 MB` total VRAM, `97251 MB` free at preflight, CUDA `13.0`, Driver `580.82.07`, Compute Capability `12.0`, CPU `AMD EPYC 9B45`, System RAM `181130 MB`)
- **Live GPU Hardware Preflight Status**: `PASS` (`execution_mode = CONCURRENT_DUAL_SERVER`, `combined_required_mb = 49384`)
- **Local Clean-Checkout Runtime / Benchmark Status**: `NOT_STAGED` (`runs/run_20261111_002/gpu_runtime_benchmark.json`, `data/processed/coder_a_outputs.json`, and `data/processed/coder_b_outputs.json` are gitignored runtime artifacts not present in clean Git checkouts; prior release-bundle production dual coding verified in PR `#11` and documented in `docs/PROJECT_STATE.md`)
- **Pinned Production Coder Models (`src/runtime/model_runtime.py`)**: `Coder A: Valdemardi/DeepSeek-R1-Distill-Qwen-32B-AWQ @ 1de6a3f7b151f6ea0f6d42acb3566e094eb8a264` | `Coder B: RedHatAI/Mistral-Small-3.1-24B-Instruct-2503-quantized.w4a16 @ dc0a9d9df93998ec3163cabca261715c0bbee4f6`

---

## 1. Input Files & Tracked Config Hashes (SHA-256)
| File Path | Digest / Notes |
| :--- | :--- |
| `data/raw/survey_raw.csv` | SHA-256: `56acded3e02be49be27d6b288fa2c43fcce68df24525113eba1b1161eec52a95` \| Git blob SHA-1: `eb526813aadcfab2b4b157e7b6513de50e6b3178` |
| `runs/run_20261111_002/alternative_crosswalk.json` | SHA-256: `8fa47137fe3d73efea4835fedc90f21c40920a510d03b9e67844b961bf6dc600` (`17` scoped rules, PR `#15`) |

---

## 2. LLM Models, Prompt Versions & Wave-3B Reconciliation Provenance
- **Release-Bundle Production Dual Coding (PR `#11` Historical Record)**: `Coder A` (`8939adc884672a1cdf883e496f476a872248d90d4f8da8f3549d29e24b20dadf`) and `Coder B` (`129c7257c1c4fdf9f3b88067b96180cf68ebd3056f41e0880fd5831d48ffcd49`) completed `136/136/0` usable responses + `18` non-preference cells preserved; `source_evidence_hash = 0b814c3b6f6a88ec8e5d895a025cb146ed2e73e08f814ace145c0237c17c9753`.
- **Clean-Checkout Staging Status (Wave 3B Gate)**: `IMMUTABLE_CODER_INPUTS = FAIL` — the verified production `data/processed/coder_a_outputs.json`, `data/processed/coder_b_outputs.json`, and `runs/run_20261111_002/gpu_runtime_benchmark.json` files are absent from this isolated Git workspace, halting Agent 03 output regeneration and canonical `manifest.json` registration without substituting fixtures.
- **Configured Coder Architecture**: Dual independent vLLM OpenAI-compatible servers (`temperature = 0.0`, `seed = 42`, `SEQUENTIAL_FALLBACK` default unless matching live benchmark passes concurrent mode).

---

## 3. Pipeline Execution Stages & Release Gate Status
- **Completed / Verified Stages in Git (`baef68b`)**:
  - `Stage 00`: Architecture Invariants, 20 Contracts & `ADR-0008` (`PR #12`, `PR #13`; `PROHIBITED_PRUNING_SOURCES` & 4-state `RobustParetoResult` enforced)
  - `Stage 01`: Data & Question Registry Ingestion (`src/ingest/ingestion.py`, `src/registry/question_registry.py`, Gate 1 `PASS`: `154` normalized rows across `11` participants: `136` `observed_usable`, `10` `missing_raw_blank`, `6` `missing_non_substantive`, `2` `ambiguous`; `13` primary `QuestionSpec` + optional `Q14`)
  - `Stage 02 (Contracts & Entrance Gate)`: Qualitative Coding Schemas & Engine (`src/nlp/`, Gate 2 `PASS`)
  - `Stage 03 (Code & Crosswalk Spec Merged)`: Initial Agent 03 engine (`PR #11`) adapted to `ADR-0008` (`PR #15`, `src/evidence/reconciliation.py`, `runs/run_20261111_002/alternative_crosswalk.json`, `17` `(question_id, canonical_subtopic_id)` rules verified)
  - `Stage 07`: GPU Runtime persisted & hardened (`PR #4`, `PR #6`–`#9`, live Blackwell hardware preflight `PASS`)
  - `Stage 10`: `ISSUE-005` synced `RESOLVED` in `docs/OPEN_ISSUES.md`, `docs/PROJECT_STATE.md` updated, and all 12 context packs regenerated (`PR #14`)
  - `Stage 11`: Orchestration, Hardcoding Scanner, Freshness Checker, and 9-Condition `Agent04ReleaseDecision` gate (`src/pipeline/orchestrator.py`)
- **Hard Release Gate Decisions (`python -m src.pipeline.orchestrator`)**:
  - **`AGENT_03_RELEASE`**: `BLOCKED` (clean Git checkout lacks `runs/run_20261111_002/gpu_runtime_benchmark.json`, `data/processed/coder_a_outputs.json`, and `data/processed/coder_b_outputs.json`)
  - **`AGENT_04_RELEASE`**: `BLOCKED` (`5/9` conditions pass: `#2`, `#3`, `#4`, `#5`, `#9`; `4/9` fail: `1_agent_03_release_ready`, `6_agent_03_outputs_exist`, `7_agent_03_crosswalk_and_uncertainty_sets_valid`, `8_agent_03_artifacts_registered_in_manifest`)
- **Remaining Wave-3B Blockers (`ISSUE-007`)**:
  - Stage verified production `data/processed/coder_a_outputs.json` (`8939adc...`), `data/processed/coder_b_outputs.json` (`129c725...`), and `runs/run_20261111_002/gpu_runtime_benchmark.json` into the integration workspace.
  - Regenerate Agent 03 ADR-0008 reconciliation outputs on CPU (`python -m src.evidence.reconciliation`), verify SHA-256 digests and `PreferenceUncertaintySet` invariants, canonically register them in `runs/run_20261111_002/manifest.json`, and re-evaluate `AGENT_04_RELEASE`.

---

## 4. Registered Artifacts (`runs/run_20261111_002/manifest.json`)
*(Canonical manifest untouched during Wave-3B clean-checkout evaluation; Agent 03 artifacts remain unregistered until immutable production coder outputs are staged and verified.)*

| Artifact ID | Authority Level | Format | Producing Agent | Commit SHA | Status | Freshness | Path |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `raw_survey_v1` | `immutable_source` | `csv` | `external_stakeholder_survey` | `414aee57d1aa854ac8922956564049b228ecdcc6` | `valid` | `fresh` | `data/raw/survey_raw.csv` |
| `norm_answers_v1` | `canonical_ingestion` | `parquet` | `agent_01` | `f83c32952c568dafa415463eb73ca1911b175377` | `valid` | `fresh` | `data/normalized/answers_normalized.parquet` |
| `question_registry_v1` | `canonical_intermediate` | `json` | `agent_01` | `f83c32952c568dafa415463eb73ca1911b175377` | `valid` | `fresh` | `data/normalized/question_registry.json` |
| `gpu_runtime_config_v1` | `canonical_intermediate` | `json` | `agent_07` | `61417ebcad6f1de1232c596604cd791ab8d784a3` | `valid` | `fresh` | `runs/run_20261111_002/gpu_runtime_config.json` |

---
> **Analytical Certification**: This run card certifies immutable raw provenance (`56acded...`), Gate 1 (`PASS`), Gate 2 (`PASS`), `ADR-0008` contract + crosswalk code integration (`baef68b`), `ISSUE-005` sync, and truthful enforcement of `AGENT_04_RELEASE = BLOCKED` while immutable production Coder A/B and benchmark artifacts remain unstaged for canonical Wave-3B registration.
