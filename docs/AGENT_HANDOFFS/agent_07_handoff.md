# Agent Handoff: Agent 07 — `smoke_tiny` Scope, Compact Bounds, Metadata Injection & Checkpoint Invalidation

> **Instructions**: Every agent must copy and complete this document before terminating its turn or session. Save as `docs/AGENT_HANDOFFS/agent_07_handoff.md`.

---

## Agent Handoff Information

- **Agent ID**: `agent_07`
- **Model Used**: `Claude Opus 4.6 / GPT-5`
- **Branch / Worktree**: `agent/07-smoke-profile-fix` (branched from `origin/main` at `c96b70de72d0b1b0fe612b0d461ce5a23b46b09d`)
- **Base Commit**: `c96b70de72d0b1b0fe612b0d461ce5a23b46b09d` (`origin/main`)
- **Pushed Commit SHA**: `origin/agent/07-smoke-profile-fix` (verified upon push; reported in PR & final summary)
- **Timestamp (UTC)**: `2026-11-14T08:25:00Z`

---

## 1. Files Changed
- `src/runtime/model_runtime.py` (Modified: set `DEFAULT_SMOKE_CODER_A_SPEC.max_output_tokens = 2048` and `DEFAULT_SMOKE_CODER_B_SPEC.max_output_tokens = 2048` inside `max_model_len = 4096`; updated `build_profile_runtime_config` `SMOKE_TINY` max generation cap up to `2048`; added `profile_config_hash` to `QuestionCheckpointRecord`, `AtomicQuestionCheckpointStore`, `_assert_spec_compatible`, `verify_or_bind_coder_spec`, `put`, and `get`; added `AtomicQuestionCheckpointStore.has_incompatible_profile_state` and `AtomicQuestionCheckpointStore.archive_incompatible_smoke_namespace`; added `response_schema` / `response_schema_name` with `json_schema -> json_object -> plain` HTTP 400/422 fallback, retry `safe_cap` handling, and escalated `repair_payload["max_tokens"]` within available context)
- `src/runtime/dual_coder_runner.py` (Modified: added `SMOKE_BOUNDED_LIMITS` and `compute_profile_config_hash`; updated `select_profile_dataframe` so `smoke_tiny` excludes `PARTICIPANT_002 / Q06` and longest corpus responses while picking 1 short substantive response `<= 300` chars plus 1 non-substantive response with real provenance, preserving `pilot_subset` and complete `production`; added compact `smoke_tiny` system/user prompts and JSON schema appendices for Phase 1 & Phase 2 with distinct coder prompt hashes and bounded `1280 -> 2048` token budgets; enforced canonical enum prompt guidance and deterministic immutable source metadata injection for `participant_id`, `question_id`, `response_id`, `detected_language`, `is_substantive`, `missingness_state`, and `response_status`; added `validate_smoke_compact_bounds`, compact-bound normalizers keeping `pilot_subset`/`production` capacity intact, automatic archival of incompatible `smoke_tiny` checkpoint namespaces in `run_dual_coder_production` without disturbing `pilot_subset` or `production`, and updated `_run_smoke_tiny_diagnostics`)
- `src/runtime/__init__.py` (Modified: exported `SMOKE_BOUNDED_LIMITS`, `compute_profile_config_hash`, and `validate_smoke_compact_bounds`)
- `tests/test_runtime.py` & `tests/test_pipeline.py` (Modified: added 10 mandatory tests covering `smoke_tiny` exclusion of `PARTICIPANT_002 / Q06`, short substantive `<= 300` char + non-substantive selection, `pilot_subset` inclusion of `PARTICIPANT_002 / Q06` + edge cases, `production` 154/136 completeness, deterministic immutable metadata injection, compact `smoke_tiny` schema/bounds/provenance/simplex validity, bounded repair escalation & `response_format` fallback, `profile_config_hash` checkpoint invalidation/archival preserving `pilot_subset`/`production`, and `smoke_tiny` Agent 03 release blocking)
- `docs/AGENT_HANDOFFS/agent_07_handoff.md` (Updated)

---

## 2. Interfaces Changed
- Backwards-compatible extensions in `src/runtime/model_runtime.py` and `src/runtime/dual_coder_runner.py`:
  - `SMOKE_BOUNDED_LIMITS`
  - `compute_profile_config_hash(execution_profile, selected_df, coder_a_spec, coder_b_spec)`
  - `validate_smoke_compact_bounds(payload)`
  - `QuestionCheckpointRecord.profile_config_hash: str = ""`
  - `AtomicQuestionCheckpointStore(..., profile_config_hash: str = "")`
  - `AtomicQuestionCheckpointStore.has_incompatible_profile_state(expected_profile_config_hash)`
  - `AtomicQuestionCheckpointStore.archive_incompatible_smoke_namespace(checkpoint_dir, run_id, expected_profile_config_hash)`
  - `run_dual_coder_production(..., archive_incompatible_smoke: bool = True)`
  - `DualCoderRuntimeManager.execute_json_chat_completion(..., response_schema=None, response_schema_name="hfg_structured_output")`
- All existing contracts (`src/contracts.py`, `schemas/interfaces.json`, `docs/DATA_CONTRACTS.md`) remain intact and unmodified.

---

## 3. Shared-File Change Requests (If Any)
- None. `runs/run_20261111_002/gpu_runtime_config.json`, `runs/run_20261111_002/manifest.json`, `AGENTS.md`, `docs/PROJECT_STATE.md`, `src/contracts.py`, and `schemas/interfaces.json` are preserved untouched (`git diff -- runs/run_20261111_002/gpu_runtime_config.json` is empty).

---

## 4. Tests Executed
- Verification commands run on CPU-only Antigravity VM (`0` physical GPUs attached):
  ```bash
  .venv/bin/pytest tests/test_runtime.py -v
  .venv/bin/pytest tests/test_pipeline.py -v
  .venv/bin/pytest -v
  .venv/bin/python -m src.freshness_checker --check-all
  .venv/bin/python -m src.hardcoding_scanner --scan
  ```
- **Results**:
  - `tests/test_runtime.py`: **28/28 passed**
  - `tests/test_pipeline.py`: **8/8 passed**
  - Full repository suite (`pytest -v`): **97/97 passed**
  - `python -m src.freshness_checker --check-all`: **9/9 passed, 0 issues**
  - `python -m src.hardcoding_scanner --scan`: **0 violations**

---

## 5. Artifacts Created & Registered
*(No fake GPU benchmark or dual-coder inference artifacts created on this CPU-only host.)*
- **Verified Preexisting Artifact Preserved Untouched**:
  - `runs/run_20261111_002/gpu_runtime_config.json` (preserved untouched)
- **Canonical Tracked Notebooks Preserved**:
  - `notebooks/07_gpu_runtime.ipynb`
  - `notebooks/01_gpu_coders.ipynb` (zero root `.ipynb` duplicates)

---

## 6. Assumptions & Runtime Truthfulness
- Current VM has `0` physical GPUs (`gpu_available = false`). Per `AGENTS.md` Section 11, CPU-only mock tests are strictly separated from live GPU execution (`live_gpu_benchmark_status = NOT_EXECUTED_NO_GPU`, `AGENT_03_RELEASE = BLOCKED`).
- `smoke_tiny` now runs exclusively on short representative rows (e.g. `PARTICIPANT_006 / Q13` + `PARTICIPANT_011 / Q13`), leaving stress-testing of `PARTICIPANT_002 / Q06` to `pilot_subset` and full `production`.
- Existing Google Drive `pilot_subset` and `production` checkpoint namespaces are never modified or cleared when `smoke_tiny` archives an incompatible `smoke_tiny` namespace.

---

## 7. Unresolved Issues & Blockers
- Live Colab `smoke_tiny` re-validation (`notebooks/01_gpu_coders.ipynb` with `HFG_EXECUTION_PROFILE=smoke_tiny`), followed by `pilot_subset`, 5-stage live GPU benchmark (`notebooks/07_gpu_runtime.ipynb`), and `production` must execute on Google Colab with an attached NVIDIA GPU (`ISSUE-007`).

---

## 8. Downstream Dependencies
- Unblocks clean `smoke_tiny` live GPU rerun on Google Colab without disturbing existing Google Drive `pilot_subset` or `production` checkpoints.

---

## 9. Exact Recommended Next Action
1. Review and merge the PR from `agent/07-smoke-profile-fix` into `main`.
2. On Google Colab (attached GPU + Google Drive mounted), pull the fix and run `HFG_EXECUTION_PROFILE=smoke_tiny` ONLY first (preserving existing `pilot_subset` and `production` checkpoint directories).
3. Only after live `smoke_tiny` passes on GPU, proceed to `pilot_subset` and then `production`. Do not start Agent 03 until `PipelineOrchestrator` reports `AGENT_03_RELEASE = READY`.
