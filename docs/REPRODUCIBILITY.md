# Reproducibility Guide — HFG (`run_20261111_002`)

> **Owner**: Agent 10 — Documentation, Memory & Artifacts  
> **Applies To**: Active analytical run `run_20261111_002` (`origin/main` baseline `08d0096`)  
> **Privacy & Boundary Rule**: Raw data (`data/raw/survey_raw.csv`) is immutable and never modified. Normalized participant text (`data/normalized/answers_normalized.parquet`), unreconciled participant coder outputs (`data/processed/coder_a_outputs.json`, `data/processed/coder_b_outputs.json`), and runtime WAL checkpoints are **intentionally excluded from Git** (`.gitignore`) and deterministically regenerated or stored externally (`HFG_CHECKPOINT_ROOT`).

---

## Tracked vs. Regenerated / External Files

| Category | Paths | In Git? | Origin / Lifecycle |
| :--- | :--- | :--- | :--- |
| **Immutable Raw Input** | `data/raw/survey_raw.csv` | Yes | External anonymized source (`SHA-256: 56acded3e02be49be27d6b288fa2c43fcce68df24525113eba1b1161eec52a95`) |
| **Question Registry** | `data/normalized/question_registry.json` | Yes | Canonical `Q01`–`Q14` structural specs (no participant answer text) |
| **Runtime Config & Governance** | `runs/<run_id>/gpu_runtime_config.json`, `runs/<run_id>/manifest.json`, `runs/<run_id>/RUN_CARD.md`, `runs/<run_id>/pipeline_execution.log` | Yes | Tracked provenance, preflight measurements, and QA trace |
| **Normalized Survey Cells** | `data/normalized/answers_normalized.parquet`, `data/normalized/answers_normalized.json` | **No (`.gitignore`)** | Deterministically regenerated on every clean checkout via `src.ingest.ingestion` |
| **Live GPU Benchmark** | `runs/<run_id>/gpu_runtime_benchmark.json` | Not yet created | Generated at Colab/GPU runtime by `notebooks/07_gpu_runtime.ipynb` / `src.runtime.model_runtime` |
| **Profile & Production Coder Outputs** | `data/processed/profiles/smoke_tiny/...`, `data/processed/profiles/pilot_subset/...`, `data/processed/coder_a_outputs.json`, `data/processed/coder_b_outputs.json` | **No (`.gitignore`)** | Generated during GPU inference (`smoke_tiny`, `pilot_subset`, or `production`) |
| **WAL Checkpoints & Logs** | `.checkpoints/gpu_coder_wal/<run_id>/<profile>/` or `$HFG_CHECKPOINT_ROOT/<run_id>/<profile>/` | **No (`.gitignore`)** | Crash-safe atomic checkpoints (stored on Drive during Colab runs if configured) |

---

## Environment Setup

```bash
git clone https://github.com/necantis/HFG.git
cd HFG
python3 -m venv .venv
.venv/bin/pip install -e .
```

Key environment variables recognized by Colab notebooks ([`src/runtime/notebook_builder.py`](../src/runtime/notebook_builder.py), [`notebooks/00_control_plane.ipynb`](../notebooks/00_control_plane.ipynb), [`notebooks/04_validation.ipynb`](../notebooks/04_validation.ipynb)):

- `HFG_BRANCH` / `HFG_COMMIT`: Optional branch/SHA pin when bootstrapping inside Google Colab.
- `HFG_EXECUTION_PROFILE`: Explicit profile selector (`smoke_tiny`, `pilot_subset`, or `production`).
- `HFG_CHECKPOINT_ROOT`: Optional durable external checkpoint directory (e.g., `/content/drive/MyDrive/HFG_checkpoints`).
- `HFG_WRITE_EXECUTION_LOG`: Set to `'1'` only when intentionally refreshing `runs/<run_id>/pipeline_execution.log`.

---

## Stage A — CPU-Only Repository Validation (No GPU Required)

Use this procedure to verify code contracts, regenerate normalized cells locally, verify Gate 1, and inspect pipeline readiness on any standard CPU workstation.

1. **Regenerate normalized cells deterministically from `data/raw/survey_raw.csv`**:
   ```bash
   .venv/bin/python -m src.ingest.ingestion
   ```
   Verify output counts: `154` normalized rows (`11` participants × `14` questions), `136` `observed_usable`, `10` `missing_raw_blank`, `6` `missing_non_substantive`, `2` `ambiguous`, `0` imputed.

2. **Verify Gate 1 and static hardcoding audit**:
   ```bash
   .venv/bin/python -m src.hardcoding_scanner --scan
   .venv/bin/python -m src.hardcoding_scanner --check-gate-1
   ```
   Expected: `0` hardcoding violations and `overall_passed = True`.

3. **Run repository freshness & unit/integration test suite**:
   ```bash
   .venv/bin/python -m src.freshness_checker --check-all
   .venv/bin/pytest tests/ -v
   ```
   Expected: Freshness `9/9` categories passed (`0` issues) and full `pytest` pass (`97` tests baseline; CPU mock runtime tests only—does **not** validate live GPU execution).

4. **Evaluate Agent 11 Pipeline Orchestrator**:
   ```bash
   .venv/bin/python -m src.pipeline.orchestrator
   ```
   Expected on a clean repository without persisted production GPU outputs: `highest_verified_state = GPU_PREFLIGHT_READY`, `agent_01_gate_1 = PASS`, `agent_02_entrance_gate = PASS`, and **`AGENT_03_RELEASE = BLOCKED`**.

*(Notebook equivalent: [`notebooks/00_control_plane.ipynb`](../notebooks/00_control_plane.ipynb).)*

---

## Stage B — GPU Smoke Test (`smoke_tiny`)

Validates live CUDA + vLLM OpenAI-compatible serving, structured JSON output recovery, bounded schema limits (`SMOKE_BOUNDED_LIMITS`), and atomic WAL checkpointing on compact inputs (`2` rows: `1` short substantive reply `<= 300` chars excluding `PARTICIPANT_002/Q06` + `1` non-substantive reply).

**Preconditions**: NVIDIA GPU runtime with vLLM + Hugging Face access; Stage A Gate 1 completed.

```bash
export HFG_EXECUTION_PROFILE="smoke_tiny"
export HFG_CHECKPOINT_ROOT="/content/drive/MyDrive/HFG_checkpoints"  # optional on Colab

.venv/bin/python -m src.runtime.dual_coder_runner \
  --execution-profile smoke_tiny \
  --checkpoint-root "$HFG_CHECKPOINT_ROOT"
```

**Verification & Invariants**:
- Outputs write strictly to isolated `data/processed/profiles/smoke_tiny/` (`production_eligible = False`, `synthetic_or_test_execution = True`).
- WAL checkpoints write to `<checkpoint_root>/<run_id>/smoke_tiny/` with `profile_config_hash` guarding incompatible re-runs.
- Passing `smoke_tiny` validates live vLLM plumbing only; it **never** unlocks Agent 03 or proves 32B/24B production capacity.

---

## Stage C — Real-Model Pilot (`pilot_subset`)

Validates the full **pinned production models** (`Valdemardi/DeepSeek-R1-Distill-Qwen-32B-AWQ` + `RedHatAI/Mistral-Small-3.1-24B-Instruct-2503-quantized.w4a16`) on mandatory hard edge cases—including `PARTICIPANT_002/Q06`, ordinary substantive, long reply, `raw_blank`, `explicit_no_opinion`, `explicit_insufficient_experience`, `ambiguous`, and per-question anchors—before committing to a full production sweep.

**Preconditions**: High-VRAM GPU (target: `NVIDIA RTX PRO 6000 Blackwell Server Edition`, `97887 MB` VRAM); Stage A Gate 1 completed.

1. **Run 5-Stage Live GPU Benchmark (recommended before concurrent mode)**:
   Run [`notebooks/07_gpu_runtime.ipynb`](../notebooks/07_gpu_runtime.ipynb) or:
   ```bash
   .venv/bin/python -m src.runtime.model_runtime --verify-tokenizer
   ```
   This verifies Hugging Face remote repo metadata/revisions and produces `runs/<run_id>/gpu_runtime_benchmark.json`.

2. **Execute `pilot_subset` Dual Coding**:
   ```bash
   export HFG_EXECUTION_PROFILE="pilot_subset"
   export HFG_CHECKPOINT_ROOT="/content/drive/MyDrive/HFG_checkpoints"

   .venv/bin/python -m src.runtime.dual_coder_runner \
     --execution-profile pilot_subset \
     --checkpoint-root "$HFG_CHECKPOINT_ROOT"
   ```
   Note: By default (`select_safe_execution_mode`), `pilot_subset` runs in `SEQUENTIAL_FALLBACK` unless a matching `runs/<run_id>/gpu_runtime_benchmark.json` proves `CONCURRENT_DUAL_SERVER` safe for both pinned repos. Outputs write strictly to `data/processed/profiles/pilot_subset/` (`production_eligible = False`).

---

## Stage D — Full Production Execution (`production`)

Executes complete independent Phase 1 discovery and Phase 2 participant qualitative coding over all `154` cells (`136` usable primary/Q14 + non-preference preservation) using pinned immutable Hugging Face model revisions (`temperature = 0.0`, `seed = 42`).

**Preconditions**:
- Stage A (`verify_gate_1`) = `PASS`
- Gate 2 (`verify_full_survey_coding_gates`) = `AUTHORIZED`
- Stage C 5-stage live GPU benchmark executed (`runs/<run_id>/gpu_runtime_benchmark.json` present and `EXECUTED_LIVE_GPU`)

**Execution** (via [`notebooks/01_gpu_coders.ipynb`](../notebooks/01_gpu_coders.ipynb) with `HFG_EXECUTION_PROFILE="production"` or CLI):
```bash
export HFG_EXECUTION_PROFILE="production"
export HFG_CHECKPOINT_ROOT="/content/drive/MyDrive/HFG_checkpoints"

.venv/bin/python -m src.runtime.dual_coder_runner \
  --execution-profile production \
  --checkpoint-root "$HFG_CHECKPOINT_ROOT"
```

**Expected Production Outputs (Local / External Protected Storage, Gitignored)**:
- `data/processed/coder_a_outputs.json` (`execution_profile = "production"`, `production_eligible = True`, `synthetic_or_test_execution = False`)
- `data/processed/coder_b_outputs.json` (`execution_profile = "production"`, `production_eligible = True`, `synthetic_or_test_execution = False`)
- `<checkpoint_root>/<run_id>/production/` WAL checkpoints
- Privacy-redacted failure logs (if any retries/errors occurred) without raw survey quotes

---

## Stage E — Agent 11 Release Validation & Hard Gate Check

After production dual coding finishes, execute validation either in [`notebooks/04_validation.ipynb`](../notebooks/04_validation.ipynb) or via CLI:

```bash
.venv/bin/python -m src.hardcoding_scanner --scan
.venv/bin/python -m src.hardcoding_scanner --check-gate-1
.venv/bin/python -m src.freshness_checker --check-all
.venv/bin/pytest tests/ -v
.venv/bin/python -m src.pipeline.orchestrator --write-log
```

**Acceptance Criteria for `AGENT_03_RELEASE = READY`**:
All **13 checklist conditions** and **checks A–H** (`validate_dual_coder_outputs`) must pass simultaneously:
1. Agent 01 real ingestion Gate 1 `PASS`
2. Agent 02 entrance contracts `PASS`
3. Agent 07 persisted in Git
4. Live 5-stage GPU benchmark `EXECUTED_LIVE_GPU` and all stages `PASS`
5. Real `production` Coder A executed (`inference_occurred = True`, `model_load_succeeded = True`)
6. Real `production` independent Coder B executed (distinct non-Qwen/non-DeepSeek model family, distinct `prompt_hash`)
7. Persisted `data/processed/coder_a_outputs.json` valid & `production_eligible = True`
8. Persisted `data/processed/coder_b_outputs.json` valid & `production_eligible = True`
9. Structural integrity (`A_structural_integrity`) & orthogonal quantity separation (`G_quantity_separation`) `PASS`
10. Verbatim character-offset provenance (`B_evidence_provenance`) `PASS`
11. Missingness non-preference integrity (`C_missingness_integrity`, zero synthetic probabilities on blank/no-opinion/ambiguous cells) `PASS`
12. Agent 11 orchestration, notebooks & 9-category freshness `PASS`
13. Zero Category-4 hardcoding violations `PASS`

Until every check passes with real production artifacts on disk, `PipelineOrchestrator` enforces **`AGENT_03_RELEASE = BLOCKED`**.
