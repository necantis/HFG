# Agent Handoff: Agent 03 — Evidence & Reconciliation

> **Mission**: First Authorized Production Evidence Reconciliation for `run_20261111_002`

---

## Agent Handoff Information

- **Agent ID**: `agent_03`
- **Model Used**: `inherit`
- **Branch / Worktree**: `agent/03-reconciliation` (`/home/antigravity/necantis/HFG`)
- **Base Commit**: `ef716ac2386b8fcdd9b6d87bfb988158faee17a5` (`origin/main`)
- **Implementation Commit SHA**: `96c32951996c96773c1ad820e41aa32c0a3ea944`
- **Pushed Commit SHA**: Handoff commit stacked directly on `96c32951996c96773c1ad820e41aa32c0a3ea944` on `agent/03-reconciliation` (exact final pushed SHA reported in session completion summary; never pushed to `main`)
- **Timestamp (UTC)**: `2026-11-14T11:46:00Z`
- **Active Run ID**: `run_20261111_002`

---

## 1. Files Changed

- `src/evidence/__init__.py` (Created — public exports for Agent 03 provenance lock, evidence ledger, and reconciliation engine)
- `src/evidence/evidence_ledger.py` (Created — `ProvenanceLock`, `CoderInputProvenance`, `VerifiedSpanRecord`, `MissingnessLedgerEntry`, `SpanValidationReport`, `EvidenceLedger`, `compute_char_overlap_metrics`)
- `src/evidence/reconciliation.py` (Created — `EvidenceReconciler`, `ProposedSubtopicRecord`, `PairwiseSubtopicAlignment`, `AlternativeAlignmentInfo`, `UncertaintyMetadata`, `PreferenceReconciliationRecord`, `ReconciledOrganisationalValue`, `UnresolvedCaseRecord`, `align_alternative_vocabularies`, CLI entry point `python -m src.evidence.reconciliation`)
- `tests/test_evidence.py` (Created — 7 unit and live-production integration tests covering provenance lock rejection gates, exact span offset & zero-orphan checks, missingness preservation, no-silent-averaging stop rule, antonym guard, 4-part separated agreement metrics, open bottom-up values with Pareto non-pruning, non-forced goods audit, constraint-only `candidate_options`, and end-to-end verification of `run_20261111_002`)
- `docs/AGENT_HANDOFFS/agent_03_handoff.md` (Created — this handoff)

*Strict boundary compliance (`ADR-0007`)*: `data/raw/survey_raw.csv`, `AGENTS.md`, `src/contracts.py`, `schemas/interfaces.json`, `docs/DATA_CONTRACTS.md`, `docs/PROJECT_STATE.md`, `docs/NOTEBOOK_INDEX.md`, `pyproject.toml`, `runs/run_20261111_002/manifest.json`, `runs/run_20261111_002/RUN_CARD.md`, `runs/run_20261111_002/gpu_runtime_config.json`, `runs/run_20261111_002/gpu_runtime_benchmark.json`, `data/processed/coder_a_outputs.json`, `data/processed/coder_b_outputs.json`, and all peer handoffs were NOT modified or committed.

---

## 2. Interfaces Changed

- **Canonical Data Contracts**: None modified (conforms cleanly to `src/contracts.py`, `schemas/interfaces.json`, and `src/nlp/schemas.py` `ThemesCodebook`).
- **New Agent 03 Module API (`src/evidence/`)**:
  - `EvidenceLedger`: verifies `production`-only dual-coder inputs (`production_eligible=True`, `synthetic_or_test_execution=False`, `execution_mode != CPU_FALLBACK`, model family diversity, independent prompt hashes, matching `source_evidence_hash` recomputed identically across all 14 question corpora, 136/136/0 completions, 18 non-preference cells preserved), validates 100% of `EvidenceSpan` coordinates/offsets/`raw_response_sha256` against `data/normalized/answers_normalized.parquet`, enforces zero orphan span IDs across `discovered_subtopics`, `coding_results`, and `value_assignments`, and audits explicit missingness preservation.
  - `EvidenceReconciler`: executes evidence-grounded subtopic alignment within `Q01`–`Q13` (+ optional `Q14`), preference comparison without silent averaging (stopping at documented disagreement with `reconciled_alternative_probabilities = None` and flagging missing authorization policy), separate 4-module coder agreement metrics (no omnibus score, pre-reconciliation `0.0` placeholders excluded), open bottom-up organisational value consolidation (`pareto_pruning_prohibited=True`), non-forced goods classification audit, 4-part uncertainty propagation metadata for Agent 04, and privacy-safe `ThemesCodebook` + `candidate_options_v1`.

---

## 3. Shared-File Change Requests (If Any)

1. **Request `agent00_agent04_section8_reconciliation_policy_adr`**:
   - **Affected interface**: `docs/DECISIONS/` (new ADR), `docs/OPEN_ISSUES.md` (`ISSUE-005`), `src/contracts.py` (`PreferenceCell` reconciliation rule metadata), `schemas/interfaces.json`
   - **Proposed fields or dependency**:
     1. Authorized mathematical reconciliation rule for `alternative_probabilities` when Coder A and Coder B distributions differ (exact disagreement cells in `Q06` plus single-coder omission/granularity rules);
     2. Authorized per-question canonical alternative crosswalk mapping (`ALTERNATIVE_VOCABULARY_MISMATCH`: 83 cells in `Q01`–`Q05`, `Q08`–`Q14`; `ALTERNATIVE_KEY_CROSSWALK_PENDING`: 5 cells);
     3. Formal resolution of `ISSUE-005` unifying `probability_interpretation` semantics (`epistemic_uncertainty_over_preference`, `explicit_mixed_preference`, `conditional_or_context_dependent`: 17 interpretation-flagged cells) prior to utility derivation in Agent 04.
   - **Reason**: Per Section 8, Agent 03 stopped at the documented disagreement representation without silent averaging because no authorized combination rule or canonical alternative crosswalk exists in current contracts.
   - **Compatibility impact**: Blocking prerequisite (`AGENT_04_RELEASE = BLOCKED`) before Agent 04 may generate a consolidated `PreferenceMatrix` or run Pareto optimization.
   - **Required tests**: Assert `PreferenceMatrix` cells pass all distribution sum, non-preference empty preservation, and documented crosswalk checks in Agent 04 tests.

2. **Request `agent11_integration_canonical_registration_and_benchmark_sync`**:
   - **Affected interface**: `runs/run_20261111_002/manifest.json`, `runs/run_20261111_002/RUN_CARD.md`, `runs/run_20261111_002/gpu_runtime_config.json`, `docs/NOTEBOOK_INDEX.md`, `docs/PROJECT_STATE.md`, `docs/OPEN_ISSUES.md` (`ISSUE-007`)
   - **Proposed fields or dependency**:
     - Register validated production artifacts upon integration (`themes_codebook_v1`, `candidate_options_v1`, and Agent 03 reconciliation outputs listed in Section 5 below) after verifying merged code & source hashes;
     - Reconcile tracked runtime config/benchmark/release artifacts (`runs/run_20261111_002/gpu_runtime_benchmark.json` and the release-bundle production release manifest) and close `ISSUE-007`;
     - Sync `docs/NOTEBOOK_INDEX.md` to include `notebooks/HFG_live_execution.ipynb` added in `ef716ac` (which caused pre-existing baseline failure `test_notebook_index_matches_tracked_ipynb_files`).
   - **Reason**: Per `ADR-0007` Section 10/11, Agent 03 produces task-local artifact descriptors only and does not concurrently modify `runs/run_20261111_002/manifest.json`, `runs/run_20261111_002/RUN_CARD.md`, `docs/NOTEBOOK_INDEX.md`, or `docs/PROJECT_STATE.md`.
   - **Compatibility impact**: Backwards-compatible canonical integration registration.
   - **Required tests**: `pytest tests/test_artifact_registry.py tests/test_context_pack.py tests/test_freshness_checker.py -v` and `python -m src.freshness_checker --check-all`.

3. **Request `agent02_agent11_goods_and_phase2_split_annotations`**:
   - **Affected interface**: `src/nlp/subtopic_extraction.py` / qualitative post-coding QA (`ISSUE-005` / future coder runs)
   - **Proposed fields or dependency**:
     - Ensure Phase-2 deduplication splits (e.g., `Q11_allocation_overheads_to_project_leaders_2`, `Q11_overhead_allocation_mechanism_2`) emit explicit Phase-1 facet descriptors when split in Phase 2;
     - Review why both production coders emitted `goods_applicability="NOT_APPLICABLE"` / `economic_good_class=None` across all 6 `ENABLED` allocation questions (`Q07`–`Q12`) before deciding whether targeted economic-good annotation is needed downstream.
   - **Reason**: Agent 03 preserved both Phase-2 splits unmerged (`PHASE2_DEDUP_SPLIT_UNDECLARED_IN_PHASE1`) and preserved `NOT_APPLICABLE`/`None` on `Q07`–`Q12` (`GOODS_ASSESSMENT_UNPOPULATED_ON_ENABLED_QUESTION`) without fabricating classes.
   - **Compatibility impact**: Additive future-run prompt/schema hygiene; current reconciliation preserves all records losslessly.
   - **Required tests**: `pytest tests/test_nlp.py tests/test_evidence.py -v`.

---

## 4. Tests Executed

```bash
/tmp/hfg_venv/bin/python -m src.pipeline.orchestrator
# Verified baseline: AGENT_03_RELEASE = READY (7 states true, 13 checklist items true, A-H true, 0 violations)

/tmp/hfg_venv/bin/python -m src.evidence.reconciliation
# Executed live production reconciliation on run_20261111_002: all 13 qa_checks = True

/tmp/hfg_venv/bin/pytest tests/test_evidence.py tests/test_nlp.py tests/test_artifact_registry.py tests/test_freshness_checker.py tests/test_acceptance.py -v
# 41 passed in 0.96s (7/7 in test_evidence.py including live run_20261111_002 integration check)

/tmp/hfg_venv/bin/python -m src.hardcoding_scanner --scan
# Hardcoding scan completed. Violations found: 0

/tmp/hfg_venv/bin/python -m src.freshness_checker --check-all
# Passed Checks: 9/9 | Issues Detected: 0

# Privacy scan across all 9 generated JSON files vs 130 respondent texts:
# 0 verbatim respondent quote leaks detected.
```

- *Full repository test run note (`pytest tests/ -q`)*: Zero regressions from Agent 03. Pre-existing / staged-workspace failures outside Agent 03 scope were observed and verified: (1) `tests/test_collaboration_policy.py::test_notebook_index_matches_tracked_ipynb_files` (pre-existing on `origin/main` `ef716ac` where `notebooks/HFG_live_execution.ipynb` was committed without updating `docs/NOTEBOOK_INDEX.md`), (2) 4 tests in `tests/test_pipeline.py` that assert `AGENT_03_RELEASE = BLOCKED` on an unstaged repo (now returning `READY` locally because production bundle outputs are staged), and (3) `tests/test_runtime.py::test_smoke_checkpoint_namespace_invalidation_preserves_pilot_and_production` hitting an ephemeral port bind race (`Errno 98`) during multi-server mock execution.
- *Evidentiary note*: Reconciliation ran in CPU Python against the verified RTX PRO 6000 Blackwell production Coder A and Coder B JSON outputs staged from the supplied release zip archive.

---

## 5. Artifacts Created & Registered (Task-Local Pending Integration)

*(Per `ADR-0007` Section 11, generated task-local artifacts under processed data are untracked in Git and recorded below with SHA-256 checksums for Agent 11 canonical registration in `runs/run_20261111_002/manifest.json`.)*

| Artifact ID | Scope | Local Path | Schema Version | Records | Validation | SHA-256 |
| :--- | :--- | :--- | :--- | ---: | :--- | :--- |
| `themes_codebook_v1` | `task_local_pending_integration_registration` | `data/processed/themes_codebook.json` | `1.0.0` / `v1.1.0` | 84 | `valid` | `78f9de9342182bb01fdcb41b78ad299d7175aaef671908849ac67b0372a7ee40` |
| `candidate_options_v1` | `task_local_pending_integration_registration` | `data/processed/candidate_options.json` | `1.0.0` / `v1.1.0` | 219 | `valid` | `dfb32d0d44cc16d75e20c2f2887db4b06ecbc453738f26a5bb0162d20a2e1051` |
| `reconciled_evidence_v1` | `task_local_pending_integration_registration` | `data/processed/reconciliation/reconciled_evidence.json` | `1.0.0` | 284 | `valid` | `2a8cd06948c0bf91de6d756e85b421c77d6646b8ca81ff5949f8f17efbab8fbf` |
| `subtopic_alignment_v1` | `task_local_pending_integration_registration` | `data/processed/reconciliation/subtopic_alignment.json` | `1.0.0` | 84 | `valid` | `2639cedf54f93eda42ec521c8c1e79159ecd9014f11a99c26a528337adb4ecf0` |
| `reconciled_values_v1` | `task_local_pending_integration_registration` | `data/processed/reconciliation/reconciled_values.json` | `1.0.0` | 107 | `valid` | `b8ada24ae040efdd939ce70dfeb15873441c32ab84cfc209c47fa3025f2eb20c` |
| `coder_agreement_stats_v1` | `task_local_pending_integration_registration` | `data/processed/reconciliation/coder_agreement_stats.json` | `1.0.0` | 4 | `valid` | `ec3fb14d9ecb211c0bbbb62132dbb207a0ec0e6c0e2991092581444c13d3449a` |
| `unresolved_cases_registry_v1` | `task_local_pending_integration_registration` | `data/processed/reconciliation/unresolved_cases_registry.json` | `1.0.0` | 274 | `valid` | `2c309d684dbcf0763413e7dcd81eef534591aa71d47dd6c93648322e47123af0` |
| `reconciliation_qa_report_v1` | `task_local_pending_integration_registration` | `data/processed/reconciliation/reconciliation_qa_report.json` | `1.0.0` | 13 | `valid` | `8ec3c8e26950a91f9bc82521859d5480253e760bf73675a61c622a3fbac946b3` |

*Descriptor index*: `data/processed/reconciliation/task_local_artifact_descriptors.json` (dynamically refreshed per run).

### Locked Provenance Coordinates (`LOCK_9dc304b23bf2`)
- **Base Git SHA**: `ef716ac2386b8fcdd9b6d87bfb988158faee17a5` (Release bundle production release metadata recorded `85ff51cffae1276d52feeab7fe1f716543de72b8`)
- **Immutable Raw Survey SHA-256**: `56acded3e8fe510085d38126fc93fc29a8f104e2396cf201be50016b1fc287da`
- **Common `source_evidence_hash` (verified by full recomputation)**: `0b814c3b6f6a88ec8e5d895a025cb146ed2e73e08f814ace145c0237c17c9753`
- **Coder A (`data/processed/coder_a_outputs.json`, `Valdemardi/DeepSeek-R1-Distill-Qwen-32B-AWQ` @ `1de6a3f7b151f6ea0f6d42acb3566e094eb8a264`)**:
  - Artifact SHA-256: `8939adc884672a1cdf883e496f476a872248d90d4f8da8f3549d29e24b20dadf`
  - Prompt Hash: `4d1279f046aa4460707cb81b4e291cce30179cc060659fcdb4f796e224864377` *(exact 64-hex SHA-256 verified from runtime & release bundle; note prompt body omitted char index 21 `'8'`)*
  - Counts: `136` attempted / `136` completed / `0` failed / `18` non-preference cells preserved
- **Coder B (`data/processed/coder_b_outputs.json`, `RedHatAI/Mistral-Small-3.1-24B-Instruct-2503-quantized.w4a16` @ `dc0a9d9df93998ec3163cabca261715c0bbee4f6`)**:
  - Artifact SHA-256: `129c7257c1c4fdf9f3b88067b96180cf68ebd3056f41e0880fd5831d48ffcd49`
  - Prompt Hash: `d880fc917663268813188f833ad0bd7b0a2a3fa26a3096df5e36959965e3083b` *(exact 64-hex SHA-256 verified from runtime & release bundle; note prompt body omitted trailing `'b'`)*
  - Counts: `136` attempted / `136` completed / `0` failed / `18` non-preference cells preserved

---

## 6. Assumptions

- `EvidenceSpan` character offsets in both coders were validated strictly against `source_text` (fallback `raw_value`) in `data/normalized/answers_normalized.parquet`, yielding `100%` exact verbatim match with `0` offset errors, `0` SHA mismatches, and `0` orphan references.
- Synthesizing unmerged `ProposedSubtopicRecord` facets for the 2 Phase-2 `_2` split IDs (`Q11_allocation_overheads_to_project_leaders_2`, `Q11_overhead_allocation_mechanism_2`) preserves participant preference observations without collapsing multiple within-participant codings onto parent subtopics.
- Antonym guarding in `_canonicalize_tokens` (`vague`/`confusing`/`unclear`/`ambiguous` separated from `clear`/`clarity`/`transparent`) prevents false key equivalence between opposing qualitative assessments (e.g., `Q03` `vague_denominations` vs `clear_terminology`).

---

## 7. Unresolved Issues & Blockers (`AGENT_04_RELEASE = BLOCKED`)

1. **`UNRESOLVED_PREFERENCE_RECONCILIATION_POLICY` (`HIGH_BLOCKING_POLICY`)**: Repository contracts define no authorized rule to combine differing probability distributions (`Q06` TVD=0.15 and 0.45), align incompatible alternative vocabularies (`83` cells across both-coded subtopics, plus `5` semantically aligned pairs needing formal crosswalk confirmation), or resolve `130` single-coder subtopic cells and `28` single-coder participant omissions.
2. **`ISSUE-005` (`HIGH_BLOCKING_POLICY`)**: Heterogeneous `probability_interpretation` tags across coders (`17` distribution-equal cells differ solely in `epistemic_uncertainty_over_preference` vs `explicit_mixed_preference`; overall pairwise `probability_interpretation` agreement = `49.07%` across `108` paired cells) must be harmonized by ADR before cardinal utility construction in Agent 04.
3. **`GOODS_ASSESSMENT_UNPOPULATED_ON_ENABLED_QUESTION` (`MEDIUM`)**: Both coders emitted `NOT_APPLICABLE` / `None` across `Q07`–`Q12`; preserved untouched without forcing classes.
4. **`PHASE1_SUBTOPIC_ZERO_PHASE2_CODINGS` (`LOW`, 3 cases)** & **`PHASE2_DEDUP_SPLIT_UNDECLARED_IN_PHASE1` (`LOW`, 2 cases)**: Documented cleanly in `data/processed/reconciliation/unresolved_cases_registry.json`.

---

## 8. Downstream Dependencies

- **Unblocked (Inspection / ADR Review / Integration)**: Agent 00 (System Architect), Agent 10 (Governance / ADR Drafting), Agent 11 (Integration & Canonical Manifest Registration).
- **Blocked Pending ADR**: **Agent 04 (`AGENT_04_RELEASE = BLOCKED`)** must NOT construct a collapsed point-estimate `PreferenceMatrix` or execute Pareto frontier synthesis until the Section 8 reconciliation rule, canonical alternative crosswalks, and `ISSUE-005` are authorized by ADR.

---

## 9. Exact Recommended Next Action

1. Issue an Architecture Decision Record (`ADR-0008`+) via Agent 00 / Agent 10 authorizing:
   - cross-coder probability combination & uncertainty representation for Agent 04 (`reconciled_evidence_v1`),
   - per-question canonical alternative crosswalk tables resolving `ALTERNATIVE_VOCABULARY_MISMATCH` (`83` cells) and confirming `ALTERNATIVE_KEY_CROSSWALK_PENDING` (`5` cells),
   - single-coder omission/subtopic policy (`158` cells), and `ISSUE-005` `probability_interpretation` utility semantics.
2. Have Agent 11 review branch `agent/03-reconciliation`, run integration validation, update `docs/NOTEBOOK_INDEX.md` (`notebooks/HFG_live_execution.ipynb`), register canonical Agent 03 artifacts into `runs/run_20261111_002/manifest.json`, and regenerate context packs (`python -m src.context_pack --all`).
