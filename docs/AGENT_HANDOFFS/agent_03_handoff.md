# Agent Handoff: Agent 03 — Evidence & Reconciliation (ADR-0008 Adaptation)

> **Mission**: CPU-Only ADR-0008 Dual-Coder Reconciliation Schema Adaptation for `run_20261111_002`

---

## Agent Handoff Information

- **Agent ID**: `agent_03`
- **Model Used**: `inherit`
- **Branch / Worktree**: `agent/03-adr0008-adaptation` (`/home/antigravity/necantis/HFG`)
- **Base Commit**: `92386cdc4689f094f5881d6c91f88e323c614441` (`origin/main`, PR #13 ADR-0008 shared contracts merged)
- **Pushed Commit SHA**: Recorded in branch push / PR summary on `agent/03-adr0008-adaptation` (never pushed directly to `main`)
- **Timestamp (UTC)**: `2026-11-14T13:00:00Z`
- **Active Run ID**: `run_20261111_002`

---

## 1. Files Changed

- `runs/run_20261111_002/alternative_crosswalk.json` (Created — versioned Level 2 per-`(question_id, canonical_subtopic_id)` alternative-vocabulary crosswalk specification covering all 17 paired canonical subtopics under `Q01`–`Q14` with SHA-256 `8fa47137fe3d73efea4835fedc90f21c40920a510d03b9e67844b961bf6dc600`)
- `src/evidence/reconciliation.py` (Modified — adapted `EvidenceReconciler` to emit full `ADR-0008` schemas: scoped `CanonicalAlternativeCrosswalk`, formal `PreferenceUncertaintySet` per cell, `uncertainty_class`, `agreement_status`, `crosswalk_status`, `source_evidence_ids`, strict `resolved_point_distribution = None` whenever `uncertainty_class != "NONE_CONSENSUS"`, 5-class unresolved case taxonomy, `data/processed/reconciliation/alternative_crosswalk_summary.json` emission, inline `PreferenceCell.validate_simplex()` enforcement across 100% of records, and strict rejection of `FORBIDDEN_RECONCILIATION_METHODS`)
- `tests/test_evidence.py` (Modified — updated assertions to ADR-0008 semantics and added unit + live production integration tests verifying Condition 6, Condition 7, `ISSUE-005` `interpretation_variants`, `PARTIAL_CROSSWALK`, `NO_VALID_CROSSWALK`, scoped crosswalk misuse rejection, and `SINGLE_CODER_PARTIAL_ID` without 0.0-fill)
- `docs/AGENT_HANDOFFS/agent_03_handoff.md` (Updated — this handoff)

*Strict boundary compliance (`ADR-0007`)*: `data/raw/survey_raw.csv`, `data/processed/coder_a_outputs.json`, `data/processed/coder_b_outputs.json`, `src/contracts.py`, `schemas/interfaces.json`, `docs/DATA_CONTRACTS.md`, `docs/OPEN_ISSUES.md`, `docs/PROJECT_STATE.md`, `AGENTS.md`, `pyproject.toml`, `runs/run_20261111_002/manifest.json`, `runs/run_20261111_002/RUN_CARD.md`, `tests/test_contracts_adr0008.py`, and peer handoffs were NOT modified or committed. Neither production LLM coder was rerun.

---

## 2. Interfaces Changed

- **Canonical Contracts Modified**: None (`src/contracts.py` and `schemas/interfaces.json` unchanged).
- **Agent 03 Reconciliation Output Schema (`src/evidence/reconciliation.py`)**:
  - Added versioned scoped crosswalk loader (`EvidenceReconciler._load_crosswalk_table()`) consuming `runs/<run_id>/alternative_crosswalk.json` (`(question_id, canonical_subtopic_id)` scope).
  - Updated `align_alternative_vocabularies(..., question_id=..., canonical_subtopic_id=..., crosswalk_rule=...)` to classify `EXACT_KEY_MATCH`, `SEMANTIC_KEY_MATCH`, `SCENARIO_PREFIX_MATCH`, `PARTIAL_CROSSWALK`, `NO_VALID_CROSSWALK`, and `SINGLE_CODER_ONLY` without global lexical substitution.
  - Emits full ADR-0008 fields on every `PreferenceReconciliationRecord` (`coder_a_distribution`, `coder_b_distribution`, `coder_a_probability_interpretation`, `coder_b_probability_interpretation`, `canonical_alternative_crosswalk`, `crosswalk_status`, `agreement_status`, `uncertainty_class`, `preference_uncertainty_set`, `resolved_point_distribution`, `source_evidence_ids`, `reconciliation_status`, `reconciliation_method`), validated directly against `PreferenceCell.validate_simplex()`.
  - Replaces legacy pre-ADR policy stop status with `ADR-0008` uncertainty sets (`RESOLVED_WITH_UNCERTAINTY_SET`, `AGREEMENT_DISTRIBUTION_ONLY_INTERPRETATION_FLAGGED`, `UNRESOLVED_CROSSWALK`) and zero `FORBIDDEN_RECONCILIATION_METHODS`.
  - Adds companion Level 2 crosswalk summary artifact `data/processed/reconciliation/alternative_crosswalk_summary.json` and populates all 5 `ADR-0008` resolution classes (`RESOLVED_AS_UNCERTAINTY`, `PARTIALLY_IDENTIFIED`, `CROSSWALK_UNRESOLVED`, `SEMANTICALLY_UNRESOLVED`, `DATA_CONTRACT_VIOLATION`) in `data/processed/reconciliation/unresolved_cases_registry.json`.

---

## 3. Shared-File Change Requests (If Any)

1. **Request `agent10_governance_issue005_and_state_sync`**:
   - **Affected interface**: `docs/OPEN_ISSUES.md` (`ISSUE-005`), `docs/PROJECT_STATE.md`, `docs/AGENT_CONTEXT/agent_XX_context.md`
   - **Proposed fields or dependency**:
     - Update `ISSUE-005` status from `OPEN` to closed/resolved by `ADR-0008` (`Condition 5` of `Agent04ReleaseGate`), noting `PROBABILITY_INTERPRETATION_DISAGREEMENT` (30 interpretation-divergent cells in `run_20261111_002`) is preserved via `INTERPRETATION_DIVERGENCE` and `interpretation_variants`.
     - Refresh `docs/PROJECT_STATE.md` and regenerate agent context packs (`python -m src.context_pack --all`).
   - **Reason**: Orchestrator `5_open_issues_issue_005_synced` checks `docs/OPEN_ISSUES.md` governance synchronization.
   - **Compatibility impact**: Governance documentation sync only (backwards-compatible).
   - **Required tests**: `pytest tests/test_contracts_adr0008.py tests/test_freshness_checker.py -v` and `python -m src.freshness_checker --check-all`.

2. **Request `agent11_integration_manifest_registration_and_gate`**:
   - **Affected interface**: `runs/run_20261111_002/manifest.json`, `runs/run_20261111_002/RUN_CARD.md`
   - **Proposed fields or dependency**:
     - Register the regenerated ADR-0008 Agent 03 canonical artifacts (`themes_codebook_v1`, `candidate_options_v1`, `reconciled_evidence_v1`, and companion reconciliation artifacts listed in Section 5) in `runs/run_20261111_002/manifest.json` with verified SHA-256 checksums and `validation_status = "valid"` after merging the Agent 03 ADR-0008 adaptation PR (`agent/03-adr0008-adaptation`).
     - Re-run `python -m src.pipeline.orchestrator` to verify Conditions 1–9 of `agent_04_release_checklist` after merge + Agent 10 sync.
   - **Reason**: Per `ADR-0007` Section 10/11, canonical `manifest.json` publication belongs exclusively to Agent 11 integration (`Condition 8`).
   - **Compatibility impact**: Canonical manifest publication releasing Agent 04 downstream.
   - **Required tests**: `pytest tests/test_evidence.py tests/test_artifact_registry.py tests/test_freshness_checker.py tests/test_acceptance.py -v` and `python -m src.pipeline.orchestrator`.

---

## 4. Tests Executed

*(CPU-only adaptation tests executed against immutable GPU production artifacts for `run_20261111_002`.)*

```bash
/tmp/hfg_venv/bin/python -m src.evidence.reconciliation
# Regenerated all 10 task-local reconciliation JSON outputs on run_20261111_002;
# 16/16 qa_checks passed (all_reconciliation_invariants_passed = True),
# adr0008_preference_cells_validated = True across 284/284 records, DATA_CONTRACT_VIOLATION = 0

/tmp/hfg_venv/bin/python -m src.pipeline.orchestrator
# Verified states: AGENT_03_RELEASE = READY
# Condition 6 (6_agent_03_outputs_exist) = True
# Condition 7 (7_agent_03_crosswalk_and_uncertainty_sets_valid) = True
# Condition 9 (9_freshness_and_hardcoding_pass) = True
# Condition 5 (Agent 10) & Condition 8 (Agent 11) remain False -> AGENT_04_RELEASE = BLOCKED

/tmp/hfg_venv/bin/pytest tests/test_evidence.py tests/test_contracts_adr0008.py tests/test_freshness_checker.py tests/test_acceptance.py tests/test_artifact_registry.py tests/test_context_pack.py -v
# 38 passed, 1 workspace-state expected failure:
# - tests/test_evidence.py: 8/8 PASSED
# - tests/test_freshness_checker.py: 4/4 PASSED
# - tests/test_acceptance.py: 6/6 PASSED
# - tests/test_artifact_registry.py: 6/6 PASSED
# - tests/test_context_pack.py: 4/4 PASSED
# - tests/test_contracts_adr0008.py: 10/11 PASSED (1 expected CI-clean failure `test_agent_04_release_gate_blocked_on_current_repo` because staged runtime coder outputs make `1_agent_03_release_ready = True` locally)

/tmp/hfg_venv/bin/python -m src.hardcoding_scanner --scan
# Hardcoding scan completed. Violations found: 0

/tmp/hfg_venv/bin/python -m src.freshness_checker --check-all
# Passed Checks: 9/9 | Issues Detected: 0

# Privacy & forbidden-method scan across all 10 generated reconciliation JSONs vs 130 respondent texts:
# 0 verbatim respondent quote leaks detected; 0 FORBIDDEN_RECONCILIATION_METHODS occurrences.
```

---

## 5. Artifacts Created & Registered (Task-Local Pending Agent 11 Integration)

*(Runtime outputs under `data/processed/**` are untracked in Git per `ADR-0007` and documented below with SHA-256 checksums for Agent 11 canonical registration in `runs/run_20261111_002/manifest.json`. Config `runs/run_20261111_002/alternative_crosswalk.json` IS versioned in Git with SHA-256 `8fa47137fe3d73efea4835fedc90f21c40920a510d03b9e67844b961bf6dc600`.)*

| Artifact ID | Scope | Local Path | Records | Validation | SHA-256 |
| :--- | :--- | :--- | ---: | :--- | :--- |
| `themes_codebook_v1` | `task_local_pending_integration_registration` | `data/processed/themes_codebook.json` | 84 | `valid` | `3c7f177655ccf01de69402184f1ff2a97c20670c5f785b74a32f6108c1db3132` |
| `candidate_options_v1` | `task_local_pending_integration_registration` | `data/processed/candidate_options.json` | 185 | `valid` | `a816a96d46ea0a34252bc8e0b43256da904a1d90ae599e1d57ff68106cb02583` |
| `reconciled_evidence_v1` | `task_local_pending_integration_registration` | `data/processed/reconciliation/reconciled_evidence.json` | 284 | `valid` | `156aec2b620a45353fcc8727eab874ab8e249b91e1f9d1f8aa210818bd1d9d37` |
| `subtopic_alignment_v1` | `task_local_pending_integration_registration` | `data/processed/reconciliation/subtopic_alignment.json` | 84 | `valid` | `fdc58bf5d0b7e848370e3a2540ba9d5858eb0f84836de8bfc4b8c0bb7c66ffc3` |
| `reconciled_values_v1` | `task_local_pending_integration_registration` | `data/processed/reconciliation/reconciled_values.json` | 107 | `valid` | `ef041299d0597d3e9cdbcf22fcc4b1bd8450b562e48dc2f29f0f1e7e595e9b70` |
| `coder_agreement_stats_v1` | `task_local_pending_integration_registration` | `data/processed/reconciliation/coder_agreement_stats.json` | 4 | `valid` | `26419a3348a7f7d51f72a04ff5d174157aac4495de2b45bbb9806cf6cfca6e11` |
| `unresolved_cases_registry_v1` | `task_local_pending_integration_registration` | `data/processed/reconciliation/unresolved_cases_registry.json` | 262 | `valid` | `72ef1bc7d32c5930c0b5d1c07cbd6d1c431732a38511e6ca49b174b17f5ee346` |
| `alternative_crosswalk_summary_v1` | `task_local_pending_integration_registration` | `data/processed/reconciliation/alternative_crosswalk_summary.json` | 17 | `valid` | `f500a577f6fd7fb2ae63affd05a780ac5d4878d9b1f0b7c26c60f4622c22f870` |
| `reconciliation_qa_report_v1` | `task_local_pending_integration_registration` | `data/processed/reconciliation/reconciliation_qa_report.json` | 16 | `valid` | `0d9f97ad43b97ca429fc946f98646614a94147ffc216cf4c0b3f3218290f1e55` |

*Descriptor index*: `data/processed/reconciliation/task_local_artifact_descriptors.json`

### Verified Production Provenance Lock (`run_20261111_002`)
- **Canonical Raw Survey SHA-256**: `56acded3e02be49be27d6b288fa2c43fcce68df24525113eba1b1161eec52a95`
- **Common `source_evidence_hash` (verified identical)**: `0b814c3b6f6a88ec8e5d895a025cb146ed2e73e08f814ace145c0237c17c9753`
- **Coder A (`data/processed/coder_a_outputs.json`, `Valdemardi/DeepSeek-R1-Distill-Qwen-32B-AWQ` @ `1de6a3f7b151f6ea0f6d42acb3566e094eb8a264`)**: SHA-256 `8939adc884672a1cdf883e496f476a872248d90d4f8da8f3549d29e24b20dadf` (`136/136/0`, prompt hash `4d1279f046aa4460707cb81b4e291cce30179cc060659fcdb4f796e224864377`)
- **Coder B (`data/processed/coder_b_outputs.json`, `RedHatAI/Mistral-Small-3.1-24B-Instruct-2503-quantized.w4a16` @ `dc0a9d9df93998ec3163cabca261715c0bbee4f6`)**: SHA-256 `129c7257c1c4fdf9f3b88067b96180cf68ebd3056f41e0880fd5831d48ffcd49` (`136/136/0`, prompt hash `d880fc917663268813188f833ad0bd7b0a2a3fa26a3096df5e36959965e3083b`)

---

## 6. Assumptions

- Every Level 2 alternative mapping in `runs/run_20261111_002/alternative_crosswalk.json` is strictly scoped to a single `(question_id, canonical_subtopic_id)` pair; unaligned or structurally distinct residual alternatives remain `PARTIAL_CROSSWALK` (`18` cells) or `NO_VALID_CROSSWALK` (`12` cells) without fabricated equivalence.
- Per `ADR-0008` and `ISSUE-005` Rule 4A/4C, matching distributions with differing `probability_interpretation` (`30` cells) retain `resolved_point_distribution = None` and propagate `INTERPRETATION_DIVERGENCE` with all `interpretation_variants`.
- Per `ADR-0008`, single-coder cells (`158` cells) retain `non_coding_coder_state = "EPISTEMICALLY_UNOBSERVED"` without 0.0-filling or silent exclusion.

---

## 7. Unresolved Issues & Blockers

- **Remaining Agent 04 Release Gate Conditions (Outside Agent 03 Ownership)**:
  - **Condition 5 (`5_open_issues_issue_005_synced`)**: Owned by Agent 10 (`docs/OPEN_ISSUES.md` sync).
  - **Condition 8 (`8_agent_03_artifacts_registered_in_manifest`)**: Owned by Agent 11 (`runs/run_20261111_002/manifest.json` canonical registration post-merge).
- **Methodological Diagnostics Retained Under ADR-0008**:
  - `66` `RESOLVED_AS_UNCERTAINTY` (`36` `PREFERENCE_DISTRIBUTION_DISAGREEMENT`, `30` `PROBABILITY_INTERPRETATION_DISAGREEMENT`), `158` `PARTIALLY_IDENTIFIED` (`130` `SINGLE_CODER_SUBTOPIC_GRANULARITY`, `28` `SINGLE_CODER_PARTICIPANT_OMISSION`), `30` `CROSSWALK_UNRESOLVED` (`18` `PARTIAL_CROSSWALK_RESIDUAL`, `12` `ALTERNATIVE_VOCABULARY_MISMATCH`), `8` `SEMANTICALLY_UNRESOLVED` (`1` `GOODS_ASSESSMENT_UNPOPULATED_ON_ENABLED_QUESTION`, `3` `PHASE1_SUBTOPIC_ZERO_PHASE2_CODINGS`, `2` `PHASE2_DEDUP_SPLIT_UNDECLARED_IN_PHASE1`, `2` `AMBIGUOUS_EPISTEMIC_RESPONSE`), `0` `DATA_CONTRACT_VIOLATION`.

---

## 8. Downstream Dependencies

- **Ready for Review / Governance / Integration**: Agent 10 (`docs/OPEN_ISSUES.md` + `docs/PROJECT_STATE.md` + context packs) and Agent 11 (PR review, canonical `manifest.json` registration, orchestrator gate verification).
- **Agent 04**: Must remain unstarted until Agent 10 and Agent 11 complete Conditions 5 & 8 and formally release Agent 04 (`AGENT_04_RELEASE = READY`).

---

## 9. Exact Recommended Next Action

1. **Agent 11**: Review and merge branch `agent/03-adr0008-adaptation`, verify `6_agent_03_outputs_exist = True` and `7_agent_03_crosswalk_and_uncertainty_sets_valid = True`, and register the canonical Agent 03 ADR-0008 artifacts into `runs/run_20261111_002/manifest.json` (Condition 8).
2. **Agent 10**: Sync `ISSUE-005` in `docs/OPEN_ISSUES.md` to `CLOSED_BY_ADR_0008` (Condition 5), update `docs/PROJECT_STATE.md`, and run `python -m src.context_pack --all`.
