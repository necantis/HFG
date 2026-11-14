# Agent Handoff: Agent 07 — GPU Runtime, Execution Profiles & Durable Checkpoints

> **Instructions**: Every agent must copy and complete this document before terminating its turn or session. Save as `docs/AGENT_HANDOFFS/agent_07_handoff.md`.

---

## Agent Handoff Information

- **Agent ID**: `agent_07`
- **Model Used**: `Gemini 4 Hydrogen (Medium)`
- **Branch / Worktree**: `agent/07-execution-profiles` (branched from `origin/main` at `76024d8b9163fe6b899fe62980e7dfec5d323654`, post-PR #7, with corrective commit `15586839f0722be19a9626f9386cdb6d0ce40c78` verified ancestor)
- **Base Commit**: `76024d8b9163fe6b899fe62980e7dfec5d323654` (`origin/main`)
- **Pushed Commit SHA**: `Pending push to origin/agent/07-execution-profiles`
- **Timestamp (UTC)**: `2026-11-14T07:29:00Z`

---

## 1. Files Changed
- `src/runtime/model_runtime.py` (Modified: added `ExecutionProfile` enum (`smoke_tiny`, `pilot_subset`, `production`), `CheckpointMismatchError`, `ALLOWED_SMOKE_CODER_B_FAMILIES`, pinned production repo/revision constants `PINNED_PRODUCTION_CODER_A_REPO`/`PINNED_PRODUCTION_CODER_A_REVISION` & `PINNED_PRODUCTION_CODER_B_REPO`/`PINNED_PRODUCTION_CODER_B_REVISION`, `DEFAULT_SMOKE_CODER_A_SPEC` & `DEFAULT_SMOKE_CODER_B_SPEC`, `GPURuntimeConfig.checkpoint_root` & `execution_profile`, `benchmark_supports_concurrent_mode`, `select_safe_execution_mode`, `build_profile_runtime_config`, profile-scoped & coder-bound `AtomicQuestionCheckpointStore` namespaces with strict mismatch rejection across `model_repo`, `model_revision`, `quantization`, and `execution_profile`, and Pydantic `input_value=[REDACTED]` sanitization in failure diagnostics)
- `src/runtime/dual_coder_runner.py` (Modified: added `execution_profile` and `checkpoint_root` CLI/API options defaulting to `production`, `get_profile_flags`, `resolve_checkpoint_dir`, `select_profile_dataframe`, `_run_smoke_tiny_diagnostics`, profile isolation under `data/processed/profiles/<profile>/` for non-production runs, and strict `production_eligible` / `synthetic_or_test_execution` stamping)
- `src/runtime/__init__.py` & `src/model_runtime.py` (Modified: exported new execution-profile and checkpoint-mismatch APIs)
- `src/pipeline/orchestrator.py` (Modified: hardened Agent 11 `PipelineOrchestrator` & `CoderExecutionSummary` so `AGENT_03_RELEASE = BLOCKED` whenever artifacts come from `smoke_tiny` or `pilot_subset`, have `production_eligible != True` or `synthetic_or_test_execution != False`, or miss primary usable coordinates; filtered WAL discovery to `production` records only)
- `src/runtime/notebook_builder.py`, `notebooks/01_gpu_coders.ipynb`, `notebooks/07_gpu_runtime.ipynb` (Modified/Regenerated: exposed `HFG_EXECUTION_PROFILE` defaulting to `production` and `HFG_CHECKPOINT_ROOT` for durable external WAL checkpoints in Colab)
- `.gitignore` (Modified: ignored non-production profile outputs under `data/processed/profiles/`)
- `docs/MODEL_STRATEGY.md` (Modified: documented `smoke_tiny`, `pilot_subset`, `production` execution profiles and external `checkpoint_root` behavior in Section 2)
- `tests/test_runtime.py` & `tests/test_pipeline.py` (Modified: added tests for `smoke_tiny`, `pilot_subset`, `production` default & safe sequential mode selection, checkpoint namespace isolation & mismatch rejection, privacy-safe diagnostics, fresh-clone resume via external `checkpoint_root`, and negative Agent 03 release-gate enforcement)
- `docs/AGENT_HANDOFFS/agent_07_handoff.md` (Updated)

---

## 2. Interfaces Changed
- Backwards-compatible extensions in `src/runtime/model_runtime.py` and `src/runtime/dual_coder_runner.py`:
  - `ExecutionProfile` (`"smoke_tiny"`, `"pilot_subset"`, `"production"`)
  - `CheckpointMismatchError`
  - `run_dual_coder_production(..., execution_profile="production", checkpoint_root=None)`
  - `GPURuntimeConfig.checkpoint_root: Optional[str]`, `execution_profile: str`
  - `CoderExecutionSummary` (`execution_profile`, `production_eligible`, `synthetic_or_test_execution`)
- All existing contracts (`src/contracts.py`, `schemas/interfaces.json`, `docs/DATA_CONTRACTS.md`) remain intact and unmodified.

---

## 3. Shared-File Change Requests (If Any)
- Preexisting PR #5 `runs/run_20261111_002/gpu_runtime_config.json`, `runs/run_20261111_002/manifest.json`, `AGENTS.md`, `docs/PROJECT_STATE.md`, `src/contracts.py`, and `schemas/interfaces.json` are preserved untouched (`git diff -- runs/run_20261111_002/gpu_runtime_config.json` is empty).
- Note for Agent 11 review: `src/pipeline/orchestrator.py` was updated on this task branch per requirement to enforce profile/eligibility-aware Agent 03 release gating.
- After live Google Colab execution completes on `production`, Agent 10/11 may register verified benchmark and dual-coder outputs in `runs/run_20261111_002/manifest.json` and `docs/PROJECT_STATE.md`.

---

## 4. Tests Executed
- Executed targeted runtime & pipeline tests, full repository test suite, freshness audit, static hardcoding scanner, and orchestrator state verification:
  ```bash
  .venv/bin/pytest tests/test_runtime.py tests/test_pipeline.py -v
  .venv/bin/pytest -v
  .venv/bin/python -m src.freshness_checker --check-all
  .venv/bin/python -m src.hardcoding_scanner --scan
  .venv/bin/python -m src.pipeline.orchestrator
  ```
- **Results** (CPU-only Antigravity VM; `0` physical GPUs attached):
  - `tests/test_runtime.py` + `tests/test_pipeline.py`: **30/30 passed** (`tests/test_runtime.py`: 23/23 passed; `tests/test_pipeline.py`: 7/7 passed).
  - Full repository suite (`pytest -v`): **91/91 passed**.
  - `python -m src.freshness_checker --check-all`: **9/9 passed, 0 issues**.
  - `python -m src.hardcoding_scanner --scan`: **0 violations**.
  - `python -m src.pipeline.orchestrator`: truthfully reports `live_gpu_hardware_preflight = "PASS"`, `live_gpu_runtime_benchmark = "NOT_EXECUTED"`, and `AGENT_03_RELEASE = BLOCKED` on CPU VM.

---

## 5. Artifacts Created & Registered
*(No fake GPU benchmark or dual-coder inference artifacts created on this CPU-only host.)*
- **Verified Preexisting Artifact Preserved Untouched**:
  - `runs/run_20261111_002/gpu_runtime_config.json` (PR #5 Blackwell hardware preflight intact; `git diff` is empty)
- **Canonical Tracked Notebooks Regenerated**:
  - `notebooks/07_gpu_runtime.ipynb`
  - `notebooks/01_gpu_coders.ipynb` (zero root `.ipynb` duplicates)

---

## 6. Assumptions & Runtime Truthfulness
- Current VM has `0` physical GPUs (`gpu_available = false`). Per `AGENTS.md` Section 11, CPU-only mock tests are strictly separated from live GPU execution (`runtime_implementation_status = VALID`, `live_gpu_benchmark_status = NOT_EXECUTED_NO_GPU`, `production_dual_model_validation = FALSE`, `AGENT_03_RELEASE = BLOCKED`).
- Pinned production models (`Valdemardi/DeepSeek-R1-Distill-Qwen-32B-AWQ` @ `1de6a3f7b151f6ea0f6d42acb3566e094eb8a264` and `RedHatAI/Mistral-Small-3.1-24B-Instruct-2503-quantized.w4a16` @ `dc0a9d9df93998ec3163cabca261715c0bbee4f6`) default to `ExecutionMode.SEQUENTIAL_FALLBACK` unless a verified concurrent `runs/<run_id>/gpu_runtime_benchmark.json` proves dual residency is safe.

---

## 7. Unresolved Issues & Blockers
- Live 5-stage GPU benchmark (`notebooks/07_gpu_runtime.ipynb`) and live `smoke_tiny` -> `pilot_subset` -> `production` Colab validation (`notebooks/01_gpu_coders.ipynb`) must run on Google Colab with an attached NVIDIA GPU (`ISSUE-007`).

---

## 8. Downstream Dependencies
- **Unblocks Live Colab Execution & Durable Resumption**: Operators can pull this branch / merged `main` on Colab, set `HFG_CHECKPOINT_ROOT=/content/drive/MyDrive/HFG_checkpoints`, and validate `smoke_tiny` -> `pilot_subset` -> `production` sequentially with zero lost progress across disconnects, followed by `notebooks/04_validation.ipynb`.

---

## 9. Exact Recommended Next Action
1. Review and merge the PR from `agent/07-execution-profiles` into `main`.
2. On Google Colab (RTX PRO 6000 Blackwell runtime), mount Google Drive and export `HFG_CHECKPOINT_ROOT=/content/drive/MyDrive/HFG_checkpoints`.
3. Optionally validate server lifecycle & recovery end-to-end with `HFG_EXECUTION_PROFILE=smoke_tiny`, then edge-case parity with `HFG_EXECUTION_PROFILE=pilot_subset`.
4. Run `notebooks/07_gpu_runtime.ipynb` (or sequential-verified `notebooks/01_gpu_coders.ipynb` with default `HFG_EXECUTION_PROFILE=production`), then run `notebooks/04_validation.ipynb` (`python -m src.pipeline.orchestrator --write-log`) to verify `AGENT_03_RELEASE = READY`. Do not run Agent 03 prematurely.
