# Run Card: `run_20261111_002`

- **Run ID**: `run_20261111_002`
- **Updated At**: `2026-11-14T17:15:00+00:00` (Initial raw lock: `2026-11-12T05:33:44.383744+00:00`)
- **Initial Raw Lock Commit**: `414aee57d1aa854ac8922956564049b228ecdcc6`
- **Main Integrated Baseline Commit**: `79c0349af36464a9e898f1e35cc8bfd764f621a6` (PR `#1`–PR `#21`)
- **Live Colab GPU Preflight Hardware**: `NVIDIA RTX PRO 6000 Blackwell Server Edition` (`1` GPU, `97887 MB` total VRAM, `97251 MB` free at preflight, CUDA `13.0`, Driver `580.82.07`, Compute Capability `12.0`, CPU `AMD EPYC 9B45`, System RAM `181130 MB`)
- **Live GPU Hardware Preflight & 5-Stage Benchmark Status**: `PASS` (`EXECUTED_LIVE_GPU`, `gpu_runtime_benchmark.json` SHA-256 `bc8e6d228ec471225377c77d1ee4fecb518b678ee425069199eb1ccb95e23ba4`, `production_release.json` SHA-256 `c4cda5c49cb5cd78a49b51423c530b5723e1c60f2de52afbfb20a9420c0716c0`)
- **Pinned Production Coder Models (`src/runtime/model_runtime.py`)**: `Coder A: Valdemardi/DeepSeek-R1-Distill-Qwen-32B-AWQ @ 1de6a3f7b151f6ea0f6d42acb3566e094eb8a264` | `Coder B: RedHatAI/Mistral-Small-3.1-24B-Instruct-2503-quantized.w4a16 @ dc0a9d9df93998ec3163cabca261715c0bbee4f6`

---

## 1. Input Files & Verified Bundle Provenance (SHA-256)
| File Path | Digest / Notes |
| :--- | :--- |
| `data/raw/survey_raw.csv` | SHA-256: `56acded3e02be49be27d6b288fa2c43fcce68df24525113eba1b1161eec52a95` \| Git blob SHA-1: `eb526813aadcfab2b4b157e7b6513de50e6b3178` |
| `runs/run_20261111_002/alternative_crosswalk.json` | SHA-256: `8fa47137fe3d73efea4835fedc90f21c40920a510d03b9e67844b961bf6dc600` (`17` scoped rules, PR `#15`) |
| `runs/run_20261111_002/pareto_mc_config.json` | SHA-256: `704f40afbfa30e580729d70de21c514c2ee5cc5716041b9a8aeaa0a8033a2b55` (`monte_carlo_draws=1000`, `random_seed=42`, `veto_threshold=0.35`, PR `#18`) |
| `runs/run_20261111_002/clustering_config.json` | SHA-256: `25b3ba371ef0ccfb5f39d95018c5a95c21c0a30763666dbd75cad51342ec02bc` (`candidate_k=[1..5]`, `MASKED_JENSEN_SHANNON`, `scenario_draws=200`, `bootstrap_draws=200`, PR `#21`) |
| `runs/run_20261111_002/counterfactual_regime_config.json` | SHA-256: `88707dd13c054a2e0672aa8d5a24b0abb7a46fbc854388ee6c0b26b2e3adf2e9` (`ADR-0009` `84`-subtopic `RESOURCE_ELIGIBILITY` registry: `11` `ELIGIBLE`, `1` `CONDITIONAL_RESOURCE_ONLY`, `72` `INELIGIBLE`, `0` `UNKNOWN`; `DCG_*` double-count guards; `FRONTIER_A` freeze bounds) |
| `data/processed/coder_a_outputs.json` *(transient/gitignored)* | SHA-256: `8939adc884672a1cdf883e496f476a872248d90d4f8da8f3549d29e24b20dadf` (`136/136/0`, prompt hash `4d1279f046aa4460707cb81b4e291cce30179cc060659fcdb4f796e224864377`) |
| `data/processed/coder_b_outputs.json` *(transient/gitignored)* | SHA-256: `129c7257c1c4fdf9f3b88067b96180cf68ebd3056f41e0880fd5831d48ffcd49` (`136/136/0`, prompt hash `d880fc917663268813188f833ad0bd7b0a2a3fa26a3096df5e36959965e3083b`) |
| `runs/run_20261111_002/gpu_runtime_benchmark.json` *(transient)* | SHA-256: `bc8e6d228ec471225377c77d1ee4fecb518b678ee425069199eb1ccb95e23ba4` (`EXECUTED_LIVE_GPU`) |

---

## 2. LLM Models, Prompt Versions & Wave-3B / Stage-04–06 Analytical Provenance
- **Common `source_evidence_hash`**: `0b814c3b6f6a88ec8e5d895a025cb146ed2e73e08f814ace145c0237c17c9753`
- **Dual-Coder Validation (Checks A–H)**: `8/8 PASS` (`0` violations; `136/136/0` usable responses + `18` non-preference cells preserved)
- **ADR-0008 CPU Reconciliation (`python -m src.evidence.reconciliation`)**: `284` preference records; `NONE_CONSENSUS = 12`, `INTERPRETATION_DIVERGENCE = 30`, `DUAL_CODER_DISTRIBUTION_SET = 36`, `CROSSWALK_PARTIAL_OR_UNALIGNED = 30`, `SINGLE_CODER_PARTIAL_ID_GRANULARITY = 130`, `SINGLE_CODER_PARTIAL_ID_OMISSION = 28` (`158` single-coder total), `PRESERVED_MISSINGNESS = 18`; `DATA_CONTRACT_VIOLATION = 0`; `16/16` QA checks `PASS`; `0` forbidden methods or silent averages.
- **ADR-0008 Agent 04 Preference, Utility & Robust Pareto (`python -m src.preference.pipeline`)**:
  - `PreferenceMatrix`: `284` cells (`264` `Q01`–`Q13` primary, `20` `Q14` contextual-only, `18` preserved missingness, `0` synthetic preferences, `0` unauthorized point collapses, `0` `coder_confidence` weightings, `0` single-coder `0.0`-fills)
  - `SolutionSpace` (`FEASIBLE_SET_AUDIT = PASS`): `161` `FeasibleAlternative` (`32` minority-preserved), `543` strictly feasible `GovernanceSolution` packages (`13` primary questions each, `0` `Q14` inclusions), `112` constraint-pruned packages / `113` exclusion events (`54` `STRUCTURAL_DEPENDENCY`, `51` `INSTITUTIONAL_CONSTRAINT`, `8` `LOGICAL_CONSTRAINT`), `0` prohibited prunings
  - `ParticipantUtility`: `5,973` records across `11` valid participants (`0` non-null `point_utility`); `ISSUE-005` interpretation operators separated; double-count guards preserved
  - Exact `ParetoResult` & 4-State `RobustParetoResult` (`1,000` MC draws, `random_seed = 42`, `veto_threshold = 0.35`, coupled coding-gap corners): `326` baseline nondominated; `ROBUSTLY_NONDOMINATED = 10` (`SOL_0003`, `SOL_0009`, `SOL_0212`, `SOL_0416`, `SOL_0419`, `SOL_0422`, `SOL_0423`, `SOL_0424`, `SOL_0440`, `SOL_0522`), `CONDITIONALLY_NONDOMINATED = 248`, `UNRESOLVED_DUE_TO_CODING_UNCERTAINTY = 285`, `ROBUSTLY_DOMINATED = 0`; `>= 0.95` high-confidence nondominated = `102`; 7 welfare criteria retained separately without composite winner (`4` distinct criterion top-1 solutions: `SOL_0160`, `SOL_0364`, `SOL_0371`, `SOL_0416`); `11/11` Agent 04 QA checks `PASS`.
- **ADR-0008 Agent 05 Ex-Post Clustering (`python -m src.clustering.pipeline`, PR `#21`)**:
  - `SELECTED_K = NO_STABLE_CLUSTER_STRUCTURE` (`selected_k = 1`, `PROFILE_01`) across `11` participants (`Q01`–`Q13` primary, `Q14` isolated contextual-only, `18` missingness cells preserved unimputed, `0` coder-confidence weightings, `0` participant rankings, `0` psychological attribution tokens).
  - Primary `Rep A` (`MASKED_JENSEN_SHANNON`) `K = 2` PAM fails empirical stability gates (`silhouette = 0.1433`, `scenario_ari_mean = 0.3022`, `bootstrap_ari_mean = 0.3823`, `permutation_p_value = 0.3134`); `K in {3, 4, 5}` collapses into singletons (`min_cluster_size = 1`).
  - Exploratory `Rep C` (`ParticipantUtility` centered-cosine `8` vs `3`: `{P04, P06, P07}` vs remaining `8`) is explicitly recorded as **non-canonical / exploratory only**; `clusters_modified_feasible_set = False`, `clusters_modified_pareto_membership = False`, `clusters_modified_voting_weights_or_rights = False`; `11/11` Agent 05 QA checks `PASS`.
- **ADR-0008 Agent 06 Social Choice & Voting (`python -m src.voting.pipeline`, PR `#20`)**:
  - `BALDWIN = NOT_APPLICABLE` (`SKIPPED_NO_VALID_INPUT`) and `RRV = NOT_APPLICABLE` (`SKIPPED_NO_VALID_INPUT`): zero external ballot files supplied and `0 / 5,973` `ParticipantUtility` records have non-null `point_utility` (zero fabricated complete ballots).
  - `ROBUST_VOTING_CONCLUSION = NO_ROBUST_SINGLE_WINNER` (`consensus_winner = null`, `is_unanimous = false`, `conclusion_survives_all_admissible_scenarios = false`).
  - Expected-reference diagnostics: `Borda = SOL_0160` (`4817.5`), `Condorcet = CYCLE` (`Smith set = 543`), `Minimax = ['SOL_0416', 'SOL_0422']` (worst defeat `1`). Across `1,000` ADR-0008 MC draws: `77.8%` Condorcet cycle rate, `46` unique MC Borda winners, `81` unique MC Minimax winners.
  - Small-N (`N = 11`, discrete ballot share `1/11 = 9.0909%`, 3-seat Hare `3.6667`, Droop `3`): single-ballot leave-one-out flips Borda winner set in `6/11` (`54.5%`) and Minimax in `9/11` (`81.8%`) drops; equal `1/11` weighting enforced, zero participant ranking, 7 welfare criteria kept separate; `12/12` Agent 06 QA checks `PASS`.
- **ADR-0009 Shared Contract & Dual-Frontier Separation (`PR #23`, `agent/11-adr0009-contract-integration`)**:
  - `ORIGINAL_FRONTIER_STATUS = PRESERVED_UNMODIFIED` (`OBSERVED_DESIGN_FRONTIER` / `FRONTIER_A`: `161` `FeasibleAlternative`, `543` feasible `GovernanceSolution`, `326` baseline Pareto, `10/248/285/0` `RobustParetoResult`, `5,973` `ParticipantUtility` records, all `39` prior manifest hashes unchanged).
  - `NEW_LLM_CODING_REQUIRED = NO` (`Q-A`–`Q-H` sensitivity operates deterministically on frozen baseline evidence + versioned `counterfactual_regime_config.json`).
  - `RESOURCE_ELIGIBILITY` registry (`84` canonical subtopics): `ELIGIBLE = 11`, `CONDITIONAL_RESOURCE_ONLY = 1` (`Q08_hr_management_level`, tier `Q-G`), `INELIGIBLE = 72`, `UNKNOWN = 0`.
  - Isolated `FRONTIER_B` (`RESOURCE_REGIME_EXPANDED_FRONTIER`, output namespace `data/processed/preference/counterfactual`) enforces 10-field `ClubGoodMechanism`, `PreferenceCell` provenance boundary (`OBSERVED_RESPONDENT_PREFERENCE` only), partial utility intervals (`UNRESOLVED_DUE_TO_COUNTERFACTUAL_UTILITY`), and double-count guard groups (`DCG_FINANCIAL_RESPONSIBILITY`, `DCG_OVERHEAD_POOL`, `DCG_BONUS_POOL`).
- **Integrated Scientific Conclusions (A–F) for Agent 08**:
  - **A (Pareto Frontier)**: `543` strictly constraint-feasible packages (`Q01`–`Q13`); `326` baseline expected-utility nondominated; `10` `ROBUSTLY_NONDOMINATED` core packages, `248` `CONDITIONALLY_NONDOMINATED` (`102` at `p_nd >= 0.95`), `285` `UNRESOLVED_DUE_TO_CODING_UNCERTAINTY`, `0` `ROBUSTLY_DOMINATED`.
  - **B (Participant Heterogeneity)**: `NO_STABLE_CLUSTER_STRUCTURE` (`selected_k = 1`, `PROFILE_01`); `Rep C` (`8` vs `3`) exploratory directional utility divergence only; zero cluster interference.
  - **C (Collective Choice)**: `BALDWIN = NOT_APPLICABLE`, `RRV = NOT_APPLICABLE`, `NO_ROBUST_SINGLE_WINNER` (`77.8%` MC Condorcet cycles, `46` MC Borda / `81` MC Minimax unique winners); expected-reference winners reported strictly as non-invariant diagnostics.
  - **D (Small-N Discreteness)**: Explicit `N = 11` (`9.0909%` per ballot) LOO sensitivity (`6/11` Borda, `9/11` Minimax flips) qualification required in all public reporting.
  - **E (Construct & Non-Interference Separation)**: Pareto dominance, `7` welfare criteria, clustering, and equal-weight voting remain strictly unconflated with zero participant ranking.
  - **F (Reporting Sink Boundary)**: `runs/run_20261111_002/reports/` is presentation sink-only; every `ReportClaim` must cite verified `EvidenceSpan` / `evidence_ids` and registered `ArtifactRecord` IDs without fabricating consensus or certainty.

---

## 3. Pipeline Execution Stages & Release Gate Status
- **Completed / Verified Stages**:
  - `Stage 00`: Architecture Invariants, 20 Contracts, `ADR-0008` (`PR #12`, `PR #13`; `PROHIBITED_PRUNING_SOURCES` & 4-state `RobustParetoResult`), and `ADR-0009` (`PR #23` + shared contracts / `schemas/interfaces.json` / `counterfactual_regime_config_v1` integration)
  - `Stage 01`: Data & Question Registry Ingestion (`src/ingest/ingestion.py`, `src/registry/question_registry.py`, Gate 1 `PASS`: `154` rows / `11` participants: `136` `observed_usable`, `10` `missing_raw_blank`, `6` `missing_non_substantive`, `2` `ambiguous`; `13` primary `QuestionSpec` + `Q14`)
  - `Stage 02`: Qualitative Dual Coding (`136/136/0` per coder on RTX PRO 6000 Blackwell; Checks A–H `PASS`)
  - `Stage 03`: CPU-Only `ADR-0008` Evidence Reconciliation (`src/evidence/reconciliation.py`, `16/16` QA `PASS`, `284` records, `185` options, `107` values, `84` canonical subtopics, `262` unresolved diagnostics)
  - `Stage 04`: Preference Matrix, Dynamic Constraint-Only Solution Space, Utility & 4-State Robust Pareto (`src/preference/pipeline.py`, PR `#18`, `11/11` QA `PASS`, `FEASIBLE_SET_AUDIT = PASS`, `ROBUSTLY_NONDOMINATED = 10`)
  - `Stage 05`: Ex-Post Missingness-Masked Clustering & Preference Profiles (`src/clustering/pipeline.py`, PR `#21`, `11/11` QA `PASS`, `SELECTED_K = NO_STABLE_CLUSTER_STRUCTURE`)
  - `Stage 06`: Social Choice, Conditional Ballot Gating & Uncertainty Propagation (`src/voting/pipeline.py`, PR `#20`, `12/12` QA `PASS`, `BALDWIN = NOT_APPLICABLE`, `RRV = NOT_APPLICABLE`, `NO_ROBUST_SINGLE_WINNER`)
  - `Stage 07`: GPU Runtime & 5-Stage Live Benchmark verified (`EXECUTED_LIVE_GPU`)
  - `Stage 10`: `ISSUE-005` synced `RESOLVED`, context packs `00`–`11` updated (`PR #14`)
  - `Stage 11`: Orchestration, Hardcoding Scanner (`0` hits), Freshness Checker (`9/9` PASS), Canonical Manifest Registration (`runs/run_20261111_002/manifest.json` — `40` artifacts)
- **Hard Release Gate Decisions**:
  - **`AGENT_03_RELEASE`**: `READY` (`13/13` conditions pass when production bundle staged)
  - **`AGENT_04_RELEASE`**: `READY` (`9/9` conditions pass; executed & audited on `run_20261111_002`)
  - **`AGENT_05_RELEASE`**: `READY` (executed & audited on `run_20261111_002`)
  - **`AGENT_06_RELEASE`**: `READY` (executed & audited on `run_20261111_002`)
  - **`ORIGINAL_FRONTIER_STATUS`**: `PRESERVED_UNMODIFIED` (`OBSERVED_DESIGN_FRONTIER` / `FRONTIER_A`)
  - **`RESOURCE_REGIME_EXPANSION_RELEASE`**: `READY` (`9/9` ADR-0009 Frontier-B gate conditions pass against verified `FRONTIER_A` bundle; `BLOCKED` on clean Git checkout without staged private payloads)
  - **`AGENT_08_TECHNICAL_RELEASE`**: `READY` (Agents 03, 04, 05, 06, and `counterfactual_regime_config_v1` integrated and registered)
  - **`AGENT_08_REPORTING_STATUS`**: `HELD_FOR_RESOURCE_REGIME_SENSITIVITY` (execution held pending `FRONTIER_B` resource-regime sensitivity execution or explicit governance override)

---

## 4. Registered Artifacts (`runs/run_20261111_002/manifest.json` — `40` Total)
| Artifact ID | Authority Level | Format | Producing Agent | Validation | Freshness | Path |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `raw_survey_v1` | `immutable_source` | `csv` | `external_stakeholder_survey` | `valid` | `fresh` | `data/raw/survey_raw.csv` |
| `norm_answers_v1` | `canonical_ingestion` | `parquet` | `agent_01` | `valid` | `fresh` | `data/normalized/answers_normalized.parquet` |
| `question_registry_v1` | `canonical_intermediate` | `json` | `agent_01` | `valid` | `fresh` | `data/normalized/question_registry.json` |
| `gpu_runtime_config_v1` | `canonical_intermediate` | `json` | `agent_07` | `valid` | `fresh` | `runs/run_20261111_002/gpu_runtime_config.json` |
| `themes_codebook_v1` | `canonical_intermediate` | `json` | `agent_03` | `valid` | `fresh` | `data/processed/themes_codebook.json` |
| `candidate_options_v1` | `canonical_intermediate` | `json` | `agent_03` | `valid` | `fresh` | `data/processed/candidate_options.json` |
| `reconciled_evidence_v1` | `canonical_intermediate` | `json` | `agent_03` | `valid` | `fresh` | `data/processed/reconciliation/reconciled_evidence.json` |
| `subtopic_alignment_v1` | `canonical_intermediate` | `json` | `agent_03` | `valid` | `fresh` | `data/processed/reconciliation/subtopic_alignment.json` |
| `reconciled_values_v1` | `canonical_intermediate` | `json` | `agent_03` | `valid` | `fresh` | `data/processed/reconciliation/reconciled_values.json` |
| `coder_agreement_stats_v1` | `canonical_intermediate` | `json` | `agent_03` | `valid` | `fresh` | `data/processed/reconciliation/coder_agreement_stats.json` |
| `unresolved_cases_registry_v1` | `canonical_intermediate` | `json` | `agent_03` | `valid` | `fresh` | `data/processed/reconciliation/unresolved_cases_registry.json` |
| `alternative_crosswalk_summary_v1` | `canonical_intermediate` | `json` | `agent_03` | `valid` | `fresh` | `data/processed/reconciliation/alternative_crosswalk_summary.json` |
| `reconciliation_qa_report_v1` | `canonical_intermediate` | `json` | `agent_03` | `valid` | `fresh` | `data/processed/reconciliation/reconciliation_qa_report.json` |
| `pareto_mc_config_v1` | `canonical_intermediate` | `json` | `agent_04` | `valid` | `fresh` | `runs/run_20261111_002/pareto_mc_config.json` |
| `preference_matrix_v1` | `canonical_utility_input` | `parquet` | `agent_04` | `valid` | `fresh` | `data/processed/preference_matrix.parquet` |
| `preference_matrix_json_v1` | `canonical_utility_input` | `json` | `agent_04` | `valid` | `fresh` | `data/processed/preference/preference_matrix.json` |
| `feasible_alternatives_v1` | `canonical_intermediate` | `json` | `agent_04` | `valid` | `fresh` | `data/processed/preference/feasible_alternatives.json` |
| `participant_utility_v1` | `canonical_utility_input` | `json` | `agent_04` | `valid` | `fresh` | `data/processed/preference/participant_utility.json` |
| `pareto_results_v1` | `canonical_decision` | `json` | `agent_04` | `valid` | `fresh` | `data/processed/preference/pareto_results.json` |
| `robust_pareto_results_v1` | `canonical_decision` | `json` | `agent_04` | `valid` | `fresh` | `data/processed/preference/robust_pareto_results.json` |
| `pareto_sensitivity_v1` | `canonical_intermediate` | `json` | `agent_04` | `valid` | `fresh` | `data/processed/preference/pareto_sensitivity.json` |
| `preference_uncertainty_summary_v1` | `canonical_intermediate` | `json` | `agent_04` | `valid` | `fresh` | `data/processed/preference/preference_uncertainty_summary.json` |
| `agent_04_qa_report_v1` | `canonical_intermediate` | `json` | `agent_04` | `valid` | `fresh` | `data/processed/preference/agent_04_qa_report.json` |
| `clustering_config_v1` | `canonical_intermediate` | `json` | `agent_05` | `valid` | `fresh` | `runs/run_20261111_002/clustering_config.json` |
| `preference_profiles_v1` | `canonical_intermediate` | `json` | `agent_05` | `valid` | `fresh` | `data/processed/preference_profiles.json` |
| `participant_cluster_assignments_v1` | `canonical_intermediate` | `json` | `agent_05` | `valid` | `fresh` | `data/processed/clustering/participant_cluster_assignments.json` |
| `cluster_profiles_v1` | `canonical_intermediate` | `json` | `agent_05` | `valid` | `fresh` | `data/processed/clustering/cluster_profiles.json` |
| `cluster_stability_v1` | `canonical_intermediate` | `json` | `agent_05` | `valid` | `fresh` | `data/processed/clustering/cluster_stability.json` |
| `cluster_sensitivity_v1` | `canonical_intermediate` | `json` | `agent_05` | `valid` | `fresh` | `data/processed/clustering/cluster_sensitivity.json` |
| `cluster_pareto_associations_v1` | `canonical_intermediate` | `json` | `agent_05` | `valid` | `fresh` | `data/processed/clustering/cluster_pareto_associations.json` |
| `agent_05_qa_report_v1` | `canonical_intermediate` | `json` | `agent_05` | `valid` | `fresh` | `data/processed/clustering/agent_05_qa_report.json` |
| `voting_input_validation_v1` | `canonical_intermediate` | `json` | `agent_06` | `valid` | `fresh` | `data/processed/voting/voting_input_validation.json` |
| `voting_results_v1` | `canonical_decision` | `json` | `agent_06` | `valid` | `fresh` | `data/processed/voting_results.json` |
| `voting_uncertainty_v1` | `canonical_intermediate` | `json` | `agent_06` | `valid` | `fresh` | `data/processed/voting/voting_uncertainty.json` |
| `baldwin_results_v1` | `canonical_intermediate` | `json` | `agent_06` | `valid` | `fresh` | `data/processed/voting/baldwin_results.json` |
| `rrv_results_v1` | `canonical_intermediate` | `json` | `agent_06` | `valid` | `fresh` | `data/processed/voting/rrv_results.json` |
| `pareto_voting_comparison_v1` | `canonical_intermediate` | `json` | `agent_06` | `valid` | `fresh` | `data/processed/voting/pareto_voting_comparison.json` |
| `voting_sensitivity_v1` | `canonical_intermediate` | `json` | `agent_06` | `valid` | `fresh` | `data/processed/voting/voting_sensitivity.json` |
| `agent_06_qa_report_v1` | `canonical_intermediate` | `json` | `agent_06` | `valid` | `fresh` | `data/processed/voting/agent_06_qa_report.json` |
| `counterfactual_regime_config_v1` | `canonical_intermediate` | `json` | `agent_11` | `valid` | `fresh` | `runs/run_20261111_002/counterfactual_regime_config.json` |

---
> **Analytical Certification**: This run card certifies frozen Blackwell dual-coder provenance, `AGENT_03_RELEASE = READY` (`13/13`), `ADR-0008` CPU reconciliation (`16/16` QA checks, `DATA_CONTRACT_VIOLATION = 0`), Agent 04 preference/utility/4-state robust Pareto (`11/11` QA checks, `FEASIBLE_SET_AUDIT = PASS`, `0` prohibited prunings, `ROBUSTLY_NONDOMINATED = 10`, `0` composite winner collapse), Agent 05 ex-post clustering (`11/11` QA checks, `SELECTED_K = NO_STABLE_CLUSTER_STRUCTURE`, `Rep C` exploratory only), Agent 06 social-choice voting (`12/12` QA checks, `BALDWIN = NOT_APPLICABLE`, `RRV = NOT_APPLICABLE`, `NO_ROBUST_SINGLE_WINNER`, `N = 11` LOO sensitivity), `ADR-0009` shared contract integration (`ORIGINAL_FRONTIER_STATUS = PRESERVED_UNMODIFIED`, `NEW_LLM_CODING_REQUIRED = NO`, `RESOURCE_REGIME_EXPANSION_RELEASE = READY`), canonical metadata registration in `runs/run_20261111_002/manifest.json` (`40` artifacts) without committing sensitive runtime payloads, and `AGENT_08_TECHNICAL_RELEASE = READY` / `AGENT_08_REPORTING_STATUS = HELD_FOR_RESOURCE_REGIME_SENSITIVITY`.
