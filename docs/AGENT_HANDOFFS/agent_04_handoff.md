# Agent Handoff: Agent 04 — Preference Matrix, Utility Model & Robust Pareto Analysis (ADR-0008)

> **Mission**: First authorized production execution of Agent 04 for `run_20261111_002` under `ADR-0005`, `ADR-0007`, `ADR-0008`, and `ISSUE-005` following Wave-3B release (`AGENT_04_RELEASE = READY`, PR `#17`).

---

## Agent Handoff Information

- **Agent ID**: `agent_04`
- **Model Used**: `inherit`
- **Branch / Worktree**: `agent/04-preference-utility-pareto` (`/home/antigravity/necantis/HFG`)
- **Base Commit**: `c991d95f1ba937fbd4dfc11fb313be8cbf5fbf66` (`origin/main`, PR `#17` merge)
- **Pushed Commit SHA**: Recorded in branch push / PR summary on `agent/04-preference-utility-pareto` (never pushed directly to `main`)
- **Timestamp (UTC)**: `2026-11-14T14:46:00Z`
- **Active Run ID**: `run_20261111_002`

---

## 1. Files Changed

- `runs/run_20261111_002/pareto_mc_config.json` (Created — versioned runtime configuration for Monte Carlo draws (`1000`), seed (`42`), 95% confidence level, `veto_threshold` (`0.35`) & grid (`[0.25, 0.35, 0.45, 0.55]`), `robust_core_inclusion_threshold` (`1.0`), `high_confidence_inclusion_threshold` (`0.95`), `partial_overlap_weight_modes` (`[0.5, 1.0]`), `derived_convex_hull_sweep_enabled` (`true`), `derived_barycenter_lambdas` (`[0.25, 0.5, 0.75]`), `weight_perturbation_sigma` (`0.15`), `nash_epsilon` (`1e-6`), `atkinson_inequality_aversion` (`0.5`), `dominance_tolerance` (`1e-9`), and `simplex_tolerance` (`1e-4`))
- `src/preference/__init__.py` (Created — public Agent 04 package exports)
- `src/preference/preference_matrix.py` (Created — `PreferenceMatrixBuilder` with manifest SHA-256 verification against `runs/run_20261111_002/manifest.json`, Parquet/JSON round-trip serialization, inline `PreferenceCell.validate_simplex()`, strict non-collapse of non-consensus uncertainty sets, and explicit missingness preservation)
- `src/preference/solution_space.py` (Created — dynamic constraint-only `SolutionSpaceBuilder` generating `161` `FeasibleAlternative` records and `543` strictly feasible `GovernanceSolution` packages on the `Q01`–`Q13` primary spine while isolating `Q14` as contextual-only, logging `112` constraint-pruned packages / `113` explicit constraint exclusions, and prohibiting cluster/value/disagreement/confidence/minority pruning)
- `src/preference/utilities.py` (Created — `ParticipantUtilityEngine` propagating `ADR-0008` uncertainty sets and `ISSUE-005` interpretation operators, enforcing `uses_coder_confidence_as_weight = False`, preserving `SINGLE_CODER_PARTIAL_ID` without `0.0`-fill, applying double-count guards, propagating `NO_VALID_CROSSWALK`/`PARTIAL_CROSSWALK` bounds, computing deterministic coupled coding-gap corners, and computing Monte Carlo + derived barycenter robustness sweeps)
- `src/preference/pareto.py` (Created — exact pairwise + skyline-verified participant-level Pareto dominance analyzer and 7 multi-criteria welfare metrics: Rawls maximin, utilitarian, Nash social welfare, Gini inequality, Atkinson inequality, veto opposition counts/shares, and minimax regret)
- `src/preference/robust_pareto.py` (Created — 4-state mutually exclusive & exhaustive `RobustParetoEngine` classifying every feasible `GovernanceSolution` into `ROBUSTLY_NONDOMINATED`, `CONDITIONALLY_NONDOMINATED`, `UNRESOLVED_DUE_TO_CODING_UNCERTAINTY`, or `ROBUSTLY_DOMINATED` across Monte Carlo ensembles and coupled common-world coding-gap corners)
- `src/preference/pipeline.py` (Created — orchestrator-gated end-to-end runner, machine-checkable `11`-point QA auditor, uncertainty summary emitter, and task-local artifact descriptor builder)
- `tests/test_preference.py` (Created — `8` comprehensive unit + production invariant tests covering `pareto_mc_config_v1`, exact skyline dominance parity, prohibited pruning rejection, zero `coder_confidence` weight dependence, `ISSUE-005` operator separation, single-coder non-zero-fill + `Q14` isolation, 4-state `RobustParetoResult` mutual exclusivity, and staged `run_20261111_002` output audit)
- `docs/AGENT_HANDOFFS/agent_04_handoff.md` (Created — this handoff)

*Strict Boundary Compliance (`ADR-0007` §§9–11)*: Neither LLM coder (`coder_a`, `coder_b`) nor Agent 03 reconciliation was rerun. Shared governance/contract files (`src/contracts.py`, `schemas/interfaces.json`, `docs/DATA_CONTRACTS.md`, `docs/OPEN_ISSUES.md`, `docs/PROJECT_STATE.md`, `AGENTS.md`, `pyproject.toml`, `runs/run_20261111_002/manifest.json`, `runs/run_20261111_002/RUN_CARD.md`, top-level `src/*.py`, and peer handoffs) and immutable `data/raw/survey_raw.csv` were NOT modified. Private runtime data under `data/normalized/answers_normalized.*`, `data/processed/**`, and `runs/run_20261111_002/gpu_runtime_benchmark.json` were NOT staged or committed to Git.

---

## 2. Interfaces Changed

- **Canonical Contracts Modified**: None (`src/contracts.py` and `schemas/interfaces.json` unchanged).
- **New Implementation Package (`src/preference/`)**:
  - `PreferenceMatrixBuilder`, `load_preference_matrix`, `load_pareto_mc_config`, `PRIMARY_QUESTION_IDS` (`Q01`–`Q13`).
  - `SolutionSpaceBuilder`, `SolutionSpaceSummary`.
  - `ParticipantUtilityEngine`, `UtilityEnsembleSummary`.
  - `ParetoAnalyzer`, `nondominated_mask_exact`, `nondominated_mask_skyline`, `compute_welfare_metrics`.
  - `RobustParetoEngine`.
  - `run_agent_04_pipeline`.

---

## 3. Shared-File Change Requests (If Any)

1. **Request `agent11_integration_agent04_manifest_registration`**:
   - **Affected interface**: `runs/run_20261111_002/manifest.json`, `runs/run_20261111_002/RUN_CARD.md`
   - **Proposed fields or dependency**: Register the `pareto_mc_config_v1` Git-versioned config and the 9 task-local Agent 04 runtime outputs (`preference_matrix_v1`, `preference_matrix_json_v1`, `feasible_alternatives_v1`, `participant_utility_v1`, `pareto_results_v1`, `robust_pareto_results_v1`, `pareto_sensitivity_v1`, `preference_uncertainty_summary_v1`, `agent_04_qa_report_v1`) from `data/processed/preference/task_local_artifact_descriptors.json` into `runs/run_20261111_002/manifest.json` upon review and merge of branch `agent/04-preference-utility-pareto`.
   - **Reason**: Per `ADR-0007` §§10–11, canonical `manifest.json` publication belongs exclusively to Agent 11 during integration.
   - **Compatibility impact**: Additive manifest registration unblocking downstream production runs for Agents `05`, `06`, `08`, and `09`.
   - **Required tests**: `pytest tests/test_preference.py tests/test_artifact_registry.py tests/test_freshness_checker.py tests/test_acceptance.py -v` and `python -m src.pipeline.orchestrator`.

2. **Request `agent10_project_state_context_sync` (Post-Merge)**:
   - **Affected interface**: `docs/PROJECT_STATE.md`, `docs/AGENT_CONTEXT/agent_XX_context.md`
   - **Proposed fields or dependency**: Refresh active wave status once PR on `agent/04-preference-utility-pareto` is merged and Agent 11 publishes canonical Agent 04 registrations, then run `python -m src.context_pack --all`.
   - **Reason**: Keep project memory synchronized for Agents `05` and `06`.
   - **Compatibility impact**: Governance documentation sync only.
   - **Required tests**: `python -m src.freshness_checker --check-all`.

---

## 4. Tests & Pipeline Verification Executed

*(All analytical computations executed against verified canonical `run_20261111_002` artifacts from the attached Agent 11 bundle after SHA-256 verification.)*

```bash
/tmp/hfg_venv/bin/python -m src.pipeline.orchestrator
# AGENT_03_RELEASE = READY (13/13) | AGENT_04_RELEASE = READY (9/9)

/tmp/hfg_venv/bin/python -m src.preference.pipeline
# Executed in 35.643s | 284 PreferenceCells (264 primary Q01-Q13, 20 contextual Q14)
# 161 FeasibleAlternatives | 543 Feasible GovernanceSolutions | 112 constraint-pruned (0 prohibited)
# 5,973 ParticipantUtility records across 11 valid participants
# 326 baseline nondominated solutions | 4-state RobustPareto: 10 / 248 / 285 / 0
# QA: 11/11 checks passed (all_qa_checks_passed = True)

/tmp/hfg_venv/bin/pytest tests/test_preference.py -v
# 8 passed in 0.53s

/tmp/hfg_venv/bin/pytest tests/ -v
# Full repository suite: all tests passed (re-run verified after final test_preference.py edit)

/tmp/hfg_venv/bin/python -m src.freshness_checker --check-all
# Passed Checks: 9/9 | Issues Detected: 0

/tmp/hfg_venv/bin/python -m src.hardcoding_scanner --scan
# Violations found: 0 | verify_gate_1(): PASS

# Privacy verbatim respondent quote scan across src/preference/, pareto_mc_config.json,
# tests/test_preference.py, handoff, and all generated data/processed/preference/*.json outputs:
# 0 verbatim respondent text leaks detected.
```

---

## 5. Artifacts Created (Task-Local Pending Agent 11 Canonical Registration)

*(Runtime outputs under `data/processed/**` are uncommitted per `ADR-0007`. Descriptor index: `data/processed/preference/task_local_artifact_descriptors.json`.)*

| Artifact ID | Scope | Path | Records | Bytes | SHA-256 |
| :--- | :--- | :--- | ---: | ---: | :--- |
| `pareto_mc_config_v1` | `git_versioned_config` | `runs/run_20261111_002/pareto_mc_config.json` | 1 | 913 | `704f40afbfa30e580729d70de21c514c2ee5cc5716041b9a8aeaa0a8033a2b55` |
| `preference_matrix_v1` | `task_local_pending_integration_registration` | `data/processed/preference_matrix.parquet` | 284 | 116,810 | `330789c4b015e6262a8a73e1e98fdeb02e694641236c85fdf04852fe29524ae4` |
| `preference_matrix_json_v1` | `task_local_pending_integration_registration` | `data/processed/preference/preference_matrix.json` | 284 | 1,536,733 | `17e96eb7d0e70a4f5018da7e38a060cbee86548d8ef7c1413a9950c1d91de562` |
| `feasible_alternatives_v1` | `task_local_pending_integration_registration` | `data/processed/preference/feasible_alternatives.json` | 543 | 6,794,132 | `a325b4c8f2bb98f4a74d1a27fd708fa1f2dc169a3fa85e2fd3d275759e55c0db` |
| `participant_utility_v1` | `task_local_pending_integration_registration` | `data/processed/preference/participant_utility.json` | 5,973 | 12,143,715 | `7ed56be14484939e97128c0e3f434554c3915d83d37d786ce3b662e6e1304209` |
| `pareto_results_v1` | `task_local_pending_integration_registration` | `data/processed/preference/pareto_results.json` | 543 | 279,966 | `6365bc9aa1961e1560b3c471bbfae7067354b08eabf5b1b6379c81b9bcf2e8aa` |
| `robust_pareto_results_v1` | `task_local_pending_integration_registration` | `data/processed/preference/robust_pareto_results.json` | 543 | 1,396,633 | `9da907c3289127e7ab3b1ac24e392365cdf6b8d949e248d27cc09dd45b02c236` |
| `pareto_sensitivity_v1` | `task_local_pending_integration_registration` | `data/processed/preference/pareto_sensitivity.json` | 126 | 292,646 | `6eb6013a0ef913b583cc2b1dfa02078bd75e8e5ee36757901545f91b8e7d4920` |
| `preference_uncertainty_summary_v1` | `task_local_pending_integration_registration` | `data/processed/preference/preference_uncertainty_summary.json` | 284 | 2,137 | `588863a2eb88c9312b5861d6016595b5b63c0f5870580a9616ea8f3150a4d0c6` |
| `agent_04_qa_report_v1` | `task_local_pending_integration_registration` | `data/processed/preference/agent_04_qa_report.json` | 11 | 1,182 | `d7259785434ebc80b138373d8da9404103d8a62dec6bd7801fc15c2abcf1b7c5` |

### Verified Upstream Provenance Lock (`run_20261111_002`)

- **Raw Survey (`data/raw/survey_raw.csv`)**: `56acded3e02be49be27d6b288fa2c43fcce68df24525113eba1b1161eec52a95`
- **Coder A (`data/processed/coder_a_outputs.json`)**: `8939adc884672a1cdf883e496f476a872248d90d4f8da8f3549d29e24b20dadf`
- **Coder B (`data/processed/coder_b_outputs.json`)**: `129c7257c1c4fdf9f3b88067b96180cf68ebd3056f41e0880fd5831d48ffcd49`
- **GPU Benchmark (`runs/run_20261111_002/gpu_runtime_benchmark.json`)**: `bc8e6d228ec471225377c77d1ee4fecb518b678ee25069199eb1ccb95e23ba4`

---

## 6. Assumptions

- `semantic_importance` (`semantic_importance_a`/`b`) is authorized strictly as a subtopic salience coefficient with parallel uniform-subtopic (`282` nondominated) and uniform-question (`314` nondominated) sensitivity comparisons and never alters choice probabilities inside cells.
- For `ISSUE-005`, `epistemic_uncertainty_over_preference` is evaluated via discrete categorical latent draws over support alternatives (`with expected baseline reference`), `explicit_mixed_preference` uses fractional portfolio overlap (`1 - TVD`), and `conditional_or_context_dependent` cells remain without a machine-authorized prerequisite AST and are bounded across adversarial-low / charitable-high / uniform brackets (`point_utility = None` whenever active).
- Derived convex-hull barycenters ($\lambda \in \{0.25, 0.50, 0.75\}$) are labeled exclusively `DERIVED_ROBUSTNESS_CONVEX_BARYCENTER` for sensitivity auditing (`305`, `326`, `344` nondominated) and never overwrite raw coder distributions.
- `RobustParetoEngine` evaluates deterministic coupled common-world coding-gap corner matrices across all feasible solutions simultaneously to separate stochastic MC sensitivity (`CONDITIONALLY_NONDOMINATED`: `248`) from unresolved coding/crosswalk ambiguity (`UNRESOLVED_DUE_TO_CODING_UNCERTAINTY`: `285`).

---

## 7. Unresolved Issues & Blockers

- **No Agent 04 blockers**: All 11 machine-checkable QA invariants pass on `run_20261111_002`.
- **Methodological Uncertainty Preserved**: `285` of `543` feasible governance packages remain `UNRESOLVED_DUE_TO_CODING_UNCERTAINTY` due to genuine Level 2 crosswalk gaps (`30` cells), single-coder participant omission (`28` cells), and unparameterized conditional prerequisites (`7` primary cells); `10` packages remain `ROBUSTLY_NONDOMINATED` across all `1,000` Monte Carlo draws and all coupled coding-gap corners (`102` qualify under `p >= 0.95`).

---

## 8. Downstream Dependencies

- **Unblocked Once Integrated**:
  - **Agent 05 (`src/clustering/`)**: May consume `preference_matrix_v1` (`data/processed/preference_matrix.parquet`) using missingness-masked distances (`Q01`–`Q13`) strictly for ex-post preference profile discovery.
  - **Agent 06 (`src/voting/`)**: May consume `feasible_alternatives_v1`, `participant_utility_v1`, and `pareto_results_v1` (`Q01`–`Q13`, conditional Baldwin/RRV rules only if valid ballots exist).
- **Requires Agent 05 + 06**: **Agent 08 (`src/reporting/`)** remains gated on completion of both Agent 05 and Agent 06 before generating stakeholder policy briefs.

---

## 9. Exact Recommended Next Action

1. **Agent 11**: Review and merge the PR on `agent/04-preference-utility-pareto`, register Agent 04 artifacts from `data/processed/preference/task_local_artifact_descriptors.json` into `runs/run_20261111_002/manifest.json`, and run `python -m src.pipeline.orchestrator`.
2. **Agent 05 & Agent 06**: Execute missingness-masked preference-profile clustering (`src/clustering/`) and social-choice voting analysis (`src/voting/`) from `preference_matrix_v1` and `feasible_alternatives_v1`.
