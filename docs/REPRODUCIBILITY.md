# Reproducibility Guide — HFG (`run_20261111_002`)

> **Owner**: Agent 10 — Documentation, Memory & Artifacts  
> **Applies To**: Active analytical run `run_20261111_002` (`origin/main` baseline `6508ded` / `PR #23`, `ADR-0008` & [`ADR-0009`](DECISIONS/ADR-0009-resource-good-regimes-and-counterfactual-institutional-design.md)-aligned)  
> **Privacy & Boundary Rule**: Raw data (`data/raw/survey_raw.csv`) is immutable and never modified. Normalized participant text (`data/normalized/answers_normalized.parquet`), unreconciled participant coder outputs (`data/processed/coder_a_outputs.json`, `data/processed/coder_b_outputs.json`), downstream `FRONTIER_A` payloads (`data/processed/**`), and runtime WAL checkpoints are **intentionally excluded from Git** (`.gitignore`) and reproduced deterministically from staged bundles or local pipelines without ever committing participant payloads.

---

## Tracked vs. Regenerated / External Files

| Category | Paths | In Git? | Origin / Lifecycle |
| :--- | :--- | :--- | :--- |
| **Immutable Raw Input** | `data/raw/survey_raw.csv` | Yes | External anonymized source (`SHA-256: 56acded3e02be49be27d6b288fa2c43fcce68df24525113eba1b1161eec52a95`) |
| **Question Registry & Stage Configs** | `data/normalized/question_registry.json`, `runs/<run_id>/alternative_crosswalk.json`, `runs/<run_id>/pareto_mc_config.json`, `runs/<run_id>/clustering_config.json` | Yes | Tracked analytical configuration specs (no participant text) |
| **Runtime Config & Governance** | `runs/<run_id>/gpu_runtime_config.json`, `runs/<run_id>/manifest.json` (`39` entries), `runs/<run_id>/RUN_CARD.md`, `runs/<run_id>/pipeline_execution.log` | Yes | Tracked provenance, preflight measurements, and QA trace |
| **Normalized Survey Cells** | `data/normalized/answers_normalized.parquet`, `data/normalized/answers_normalized.json` | **No (`.gitignore`)** | Deterministically regenerated on every clean checkout via `src.ingest.ingestion` |
| **Live GPU Benchmark** | `runs/<run_id>/gpu_runtime_benchmark.json` | **No (bundle-certified)** | `EXECUTED_LIVE_GPU` on Blackwell (`SHA-256: bc8e6d22...`, certified in `RUN_CARD.md`) |
| **Profile & Production Coder Outputs** | `data/processed/profiles/smoke_tiny/...`, `data/processed/profiles/pilot_subset/...`, `data/processed/coder_a_outputs.json`, `data/processed/coder_b_outputs.json` | **No (`.gitignore`)** | Generated during Blackwell GPU inference (`136/136/0`; **`NEW_LLM_CODING_REQUIRED = NO`**) |
| **Stage 03–06 `FRONTIER_A` Outputs** | `data/processed/themes_codebook.json`, `data/processed/candidate_options.json`, `data/processed/preference_matrix.parquet`, `data/processed/preference_profiles.json`, `data/processed/voting_results.json`, etc. | **No (`.gitignore`)** | Produced across PRs `#15`–`#22`, `39` entries registered in `manifest.json` & frozen under `ADR-0009` |
| **WAL Checkpoints & Logs** | `.checkpoints/gpu_coder_wal/<run_id>/<profile>/` or `$HFG_CHECKPOINT_ROOT/<run_id>/<profile>/` | **No (`.gitignore`)** | Crash-safe atomic checkpoints |

---

## Environment Setup & Packaging Dependency Disclosure (`ISSUE-009`)

```bash
git clone https://github.com/necantis/HFG.git
cd HFG
python3 -m venv .venv
.venv/bin/pip install -e .
```

> **Truthful Dependency Blocker (`ISSUE-009`)**: As of `6508ded` (`PR #23`), [`pyproject.toml`](../pyproject.toml) declares only `pydantic`, `pyyaml`, `pandas`, `pyarrow`, and `pytest`, and **omits `numpy`, `scipy`, and `scikit-learn`** imported by `src.clustering.distances` (`scipy.stats.spearmanr`) and `src.clustering`. Consequently, after `.venv/bin/pip install -e .` alone:
> - **Targeted CPU suites pass cleanly** (e.g., `tests/test_context_pack.py`, `tests/test_audit_documentation.py`, `tests/test_acceptance.py`, `tests/test_freshness_checker.py`, `tests/test_contracts_adr0008.py`, `tests/test_pipeline.py`).
> - **Full `.venv/bin/pytest tests/ -v` fails during test collection** at `tests/test_clustering.py` with `ModuleNotFoundError: No module named 'scipy'`.
> - A Shared-File Change Request has been filed with **Agent 11** (owner of `pyproject.toml`, [`AGENTS.md`](../AGENTS.md) §10.2) under `ISSUE-009` to declare `numpy`, `scipy`, and `scikit-learn`.

Key environment variables recognized by Colab notebooks ([`src/runtime/notebook_builder.py`](../src/runtime/notebook_builder.py), [`notebooks/00_control_plane.ipynb`](../notebooks/00_control_plane.ipynb), [`notebooks/04_validation.ipynb`](../notebooks/04_validation.ipynb)):

- `HFG_BRANCH` / `HFG_COMMIT`: Optional branch/SHA pin when bootstrapping inside Google Colab.
- `HFG_EXECUTION_PROFILE`: Explicit profile selector (`smoke_tiny`, `pilot_subset`, or `production`).
- `HFG_CHECKPOINT_ROOT`: Optional durable external checkpoint directory.
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

3. **Run repository freshness & unit/integration tests**:
   ```bash
   .venv/bin/python -m src.freshness_checker --check-all
   .venv/bin/pytest tests/test_context_pack.py tests/test_audit_documentation.py tests/test_acceptance.py tests/test_freshness_checker.py tests/test_contracts_adr0008.py tests/test_pipeline.py -v
   ```
   Expected: Freshness `9/9` categories passed (`0` issues) and targeted CPU tests pass cleanly. Running unfiltered `.venv/bin/pytest tests/ -v` currently errors at collection on `tests/test_clustering.py` (`ModuleNotFoundError: No module named 'scipy'`) until Agent 11 resolves `ISSUE-009` in `pyproject.toml`.

4. **Evaluate Agent 11 Pipeline Orchestrator**:
   ```bash
   .venv/bin/python -m src.pipeline.orchestrator
   ```
   On a clean Git checkout **without** staged gitignored production/benchmark/reconciliation payloads on disk, `PipelineOrchestrator` reports local gates as `BLOCKED` (expected truthfulness guard because sensitive runtime payloads are kept out of Git). When verified `run_20261111_002` runtime payloads are staged locally, all `FRONTIER_A` upstream gates certify `READY` (`AGENT_03_RELEASE = READY`, `AGENT_04_RELEASE = READY`), as recorded in [`runs/run_20261111_002/RUN_CARD.md`](../runs/run_20261111_002/RUN_CARD.md).

*(Notebook equivalent: [`notebooks/00_control_plane.ipynb`](../notebooks/00_control_plane.ipynb).)*

---

## Stage B — GPU Smoke Test (`smoke_tiny`)

Validates live CUDA + vLLM OpenAI-compatible serving, structured JSON output recovery, bounded schema limits (`SMOKE_BOUNDED_LIMITS`), and atomic WAL checkpointing on compact inputs (`2` rows: `1` short substantive reply `<= 300` chars excluding `PARTICIPANT_002/Q06` + `1` non-substantive reply).

```bash
export HFG_EXECUTION_PROFILE="smoke_tiny"
export HFG_CHECKPOINT_ROOT="/content/drive/MyDrive/HFG_checkpoints"  # optional on Colab

.venv/bin/python -m src.runtime.dual_coder_runner \
  --execution-profile smoke_tiny \
  --checkpoint-root "$HFG_CHECKPOINT_ROOT"
```

Passing `smoke_tiny` validates live vLLM plumbing only (`production_eligible = False`).

---

## Stage C — Real-Model Pilot (`pilot_subset`)

Validates the full **pinned production models** (`Valdemardi/DeepSeek-R1-Distill-Qwen-32B-AWQ` + `RedHatAI/Mistral-Small-3.1-24B-Instruct-2503-quantized.w4a16`) on mandatory hard edge cases before committing to a full production sweep.

```bash
.venv/bin/python -m src.runtime.model_runtime --verify-tokenizer
export HFG_EXECUTION_PROFILE="pilot_subset"
.venv/bin/python -m src.runtime.dual_coder_runner --execution-profile pilot_subset
```

*(Note: `select_safe_execution_mode` defaults to `SEQUENTIAL_FALLBACK` unless a matching `gpu_runtime_benchmark.json` proves `CONCURRENT_DUAL_SERVER` safe.)*

---

## Stage D — Full Production Execution (`production`) *(Already Completed for `run_20261111_002`; `NEW_LLM_CODING_REQUIRED = NO`)*

Full `154`-cell dual-coding inference (`136/136/0`, `temperature = 0.0`, `seed = 42`, Blackwell runtime) is **already completed and verified** (`RUN_CARD.md`, common `source_evidence_hash` `0b814c3b...`). Under [`ADR-0009`](DECISIONS/ADR-0009-resource-good-regimes-and-counterfactual-institutional-design.md), **`NEW_LLM_CODING_REQUIRED = NO`**:

- **Do NOT re-run dual-LLM GPU coding** for `FRONTIER_B` counterfactual resource-regime sensitivity.
- Downstream `FRONTIER_B` work reuses existing `EvidenceSpan`s, Agent 03 `reconciled_evidence_v1`, `candidate_options_v1`, `data/normalized/question_registry.json`, and frozen `FRONTIER_A` outputs read-only.

---

## Stage E — `FRONTIER_A` Mathematical Stages (Agents 03–06 — Frozen)

All CPU `FRONTIER_A` (`OBSERVED_DESIGN_FRONTIER`) stages completed across PRs `#15`–`#22` and are canonically certified in [`runs/run_20261111_002/manifest.json`](../runs/run_20261111_002/manifest.json) (`39` entries) and [`runs/run_20261111_002/RUN_CARD.md`](../runs/run_20261111_002/RUN_CARD.md):

1. Agent 03 (`src.evidence.reconciliation`): `284` records, `185` options, `107` values, `84` canonical subtopics, `16/16` QA `PASS`.
2. Agent 04 (`src.preference.pipeline`): `543` feasible `Q01`–`Q13` packages, `326` expected-reference nondominated, `10` `ROBUSTLY_NONDOMINATED`, `248` `CONDITIONALLY_NONDOMINATED` (`102` `p_nd >= 0.95`), `285` `UNRESOLVED_DUE_TO_CODING_UNCERTAINTY`, `0` `ROBUSTLY_DOMINATED` (`11/11` QA `PASS`).
3. Agent 05 (`src.clustering.pipeline`): `NO_STABLE_CLUSTER_STRUCTURE` (`selected_k = 1`, `PROFILE_01`; `11/11` QA `PASS`, requires `numpy`/`scipy`/`scikit-learn` per `ISSUE-009`).
4. Agent 06 (`src.voting.pipeline`): `NO_ROBUST_SINGLE_WINNER`, `BALDWIN = NOT_APPLICABLE`, `RRV = NOT_APPLICABLE` (`SKIPPED_NO_VALID_INPUT`, `12/12` QA `PASS`).

---

## Stage F — `ADR-0009` Counterfactual Sensitivity (`FRONTIER_B`) & Agent 08 Reporting Hold

1. **Immutability Guard**: `FRONTIER_A` (`OBSERVED_DESIGN_FRONTIER`) metrics and the `39` manifest entries in `runs/run_20261111_002/manifest.json` MUST remain bit-for-bit unchanged.
2. **Contract & Hold Integration (`ISSUE-008`)**: Agent 11 integrates `ADR-0009` schema contracts (`ResourceEligibilityStatus`, `GoodRegimeType`, 10-field `ClubGoodContract`, `ProvenanceCategory`, `UNRESOLVED_DUE_TO_COUNTERFACTUAL_UTILITY`) and splits `src/pipeline/orchestrator.py` into `AGENT_08_TECHNICAL_RELEASE = READY` and `AGENT_08_REPORTING_STATUS = HELD_FOR_RESOURCE_REGIME_SENSITIVITY`.
3. **Counterfactual Sensitivity & Audit (`VG-01`–`VG-09`)**: Agent 04 executes `FRONTIER_B` (`RESOURCE_REGIME_EXPANDED_FRONTIER`) strictly inside `data/processed/preference/counterfactual/` for eligible resource subtopics only (`NEW_LLM_CODING_REQUIRED = NO`), before Agent 08 reporting hold is lifted for dual-frontier publication (`ADR-0009` §10) and Agent 09 performs independent review.
