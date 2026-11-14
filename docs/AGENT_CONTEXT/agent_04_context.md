# Context Pack: Agent 04 — Preference, Utility & Pareto

> **Target Agent**: `agent_04`
> **Architecture Version**: `v1.1.0`
> **Active Run ID**: `run_20261111_002`
> **Generated Context**: Scoped specifically to your mission and boundaries. Do not request full project history.

---

## 1. Mission
Preserve the completed, canonically registered FRONTIER_A (OBSERVED_DESIGN_FRONTIER: 543 feasible packages, 326 expected-reference nondominated, 10/248/285/0 4-state RobustParetoResult, 102 with p_nd >= 0.95) strictly immutable. Implement ADR-0009 FRONTIER_B (RESOURCE_REGIME_EXPANDED_FRONTIER) strictly as a separate counterfactual institutional-design sensitivity layer in data/processed/preference/counterfactual/ testing coherent regimes solely on eligible resource subtopics, with zero LLM re-coding (NEW_LLM_CODING_REQUIRED = NO), zero refusal-to-pay conversion into club preference, and zero arbitrary point utility.

---

## 2. File Ownership Boundaries

### Files You Own (Authorized to Create & Modify)
- `src/preference/`
- `notebooks/04_preference_utility_pareto.ipynb`

### Files You Must NOT Edit (Ownership Violations)
- ❌ `data/raw/*`
- ❌ `src/voting/`
- ❌ `src/reporting/`
- ❌ Any other files outside your assigned ownership scope without an approved ADR.

---

## 3. Required Interfaces

### Input Interfaces (Upstream Contracts)
- `answers_normalized_v1 (data/normalized/answers_normalized.parquet)`
- `candidate_options_v1 (data/processed/candidate_options.json)`
- `reconciled_evidence_v1 (data/processed/reconciliation/reconciled_evidence.json)`
- `gpu_runtime_config_v1 (runs/<run_id>/gpu_runtime_config.json)`

### Output Interfaces (Deliverables)
- `preference_matrix_v1 (data/processed/preference_matrix.parquet — FRONTIER_A FROZEN)`
- `pareto_mc_config_v1 (runs/<run_id>/pareto_mc_config.json)`
- `frontier_b_counterfactual_v1 (data/processed/preference/counterfactual/ — isolated ADR-0009 sensitivity namespace)`

---

## 4. Dependencies & Canonical Artifacts

### Upstream Dependencies
- `data/normalized/answers_normalized.parquet`
- `data/processed/candidate_options.json`
- `data/processed/reconciliation/reconciled_evidence.json`

### Downstream Consumers
- `agent_05 (Preference Profiles / Clustering)`
- `agent_06 (Voting)`
- `agent_08 (Report — Dual-Frontier Presentation)`

### Authoritative Canonical Artifacts
- `data/processed/candidate_options.json` (Canonical Option Set)
- `data/processed/reconciliation/reconciled_evidence.json` (ADR-0008 Crosswalk & Uncertainty Input)
- `data/processed/preference_matrix.parquet` (Canonical Utility Input — FRONTIER_A FROZEN)

---

## 5. Applicable Architecture Decision Records (ADRs)
- [`ADR-0001`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0001*.md)
- [`ADR-0002`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0002*.md)
- [`ADR-0004`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0004*.md)
- [`ADR-0005`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0005*.md)
- [`ADR-0006`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0006*.md)
- [`ADR-0007`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0007*.md)
- [`ADR-0008`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0008*.md)
- [`ADR-0009`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0009*.md)

---

## 6. Active Open Issues
| Issue ID | Severity | Component | Description | Status |
| :--- | :--- | :--- | :--- | :--- |
| `ISSUE-002` | `LOW` | `src/preference/` | Handling missing pairwise comparisons in sparse respondent graphs during matrix reconciliation. | `OPEN` |
| `ISSUE-005` | `HIGH` | `src/preference/` | **Resolved by [`ADR-0008`](DECISIONS/ADR-0008-dual-coder-preference-reconciliation-and-uncertainty.md) (PRs `#12`, `#13`) and Executed in `FRONTIER_A` (`PR #18`)**: Replaces implicit cardinal-utility conflation with mandatory interpretation-aware operators (`epistemic_uncertainty_over_preference`, `explicit_mixed_preference`, `conditional_or_context_dependent`), uncertainty-set `PreferenceCell` contracts, and 4-state `RobustParetoResult` (`543` feasible packages, `326` expected-reference nondominated, `10 / 248 / 285 / 0`). `FRONTIER_A` (`OBSERVED_DESIGN_FRONTIER`) is now frozen under [`ADR-0009`](DECISIONS/ADR-0009-resource-good-regimes-and-counterfactual-institutional-design.md). | `RESOLVED` |
| `ISSUE-008` | `HIGH` | `src/contracts.py`, `src/preference/`, `src/pipeline/`, `src/reporting/` | **`ADR-0009` Counterfactual Resource-Regime Sensitivity (`FRONTIER_B`) & Agent 08 Reporting Hold**: Track (1) Agent 11 `ADR-0009` contract integration (`ResourceEligibilityStatus`, `GoodRegimeType`, 10-field `ClubGoodContract`, `ProvenanceCategory`, `UNRESOLVED_DUE_TO_COUNTERFACTUAL_UTILITY`, and orchestrator split `AGENT_08_TECHNICAL_RELEASE = READY` vs `AGENT_08_REPORTING_STATUS = HELD_FOR_RESOURCE_REGIME_SENSITIVITY`), (2) optional deterministic CPU `RESOURCE_ELIGIBILITY` tagging if needed (`NEW_LLM_CODING_REQUIRED = NO`), (3) isolated `FRONTIER_B` (`RESOURCE_REGIME_EXPANDED_FRONTIER`) sensitivity execution (`Q-A`–`Q-H`, `VG-01`–`VG-09`) preserving frozen `FRONTIER_A` (`543 / 326 / 10-248-285-0`) bit-for-bit, (4) isolated counterfactual manifest namespace registration, and (5) lifting `AGENT_08_REPORTING_STATUS` with mandatory dual-frontier separation (`ADR-0009` §10). Links `UNRES_GOODS_ENABLED_Q07_Q12_UNPOPULATED`. | `OPEN` |

---

## 7. Acceptance Criteria & Test Execution
Before declaring your turn complete, you must satisfy:
- [ ] FROZEN BASELINE INVARIANT: Never modify or overwrite FRONTIER_A = OBSERVED_DESIGN_FRONTIER (543 feasible packages, 326 expected-reference nondominated, 10 ROBUSTLY_NONDOMINATED, 248 CONDITIONALLY_NONDOMINATED, 285 UNRESOLVED_DUE_TO_CODING_UNCERTAINTY, 0 ROBUSTLY_DOMINATED, 102 p_nd >= 0.95).
- [ ] Do not start FRONTIER_B implementation until Agent 11 integrates ADR-0009 schemas into src/contracts.py and schemas/interfaces.json (ISSUE-008); run in isolated data/processed/preference/counterfactual/ via src.preference.resource_regimes (NEW_LLM_CODING_REQUIRED = NO).
- [ ] Enforce subtopic-level RESOURCE_ELIGIBILITY: apply regimes (PRIVATE_GOOD, CLUB_GOOD, COMMON_POOL_RESOURCE, PUBLIC_GOOD, HYBRID) ONLY to eligible subtopics (Q10, Q11 pools, Q12 pools, risk-caveated Q09, Q06 financial facets under double-count guard, Q08 CONDITIONAL_RESOURCE_ONLY in Tier Q-G); strictly exclude Q01-Q05, Q07, Q13, Q14 and all INELIGIBLE perception/process/authority facets.
- [ ] CLUB_GOOD operational mechanism completeness: reject bare 'club' labels; populate membership_mode=VOLUNTARY, member_contribution_rule, non_member_compulsory_contribution=0.0, member_priority, non_member_access, exit_policy, capacity_congestion_rule, governance_rule, and pricing_contribution_rule.
- [ ] 3-Way Provenance & Refusal-to-Pay Guard: strictly separate OBSERVED_RESPONDENT_PREFERENCE, INSTITUTIONALLY_DERIVED_MECHANISM, and COUNTERFACTUAL_PREFERENCE_ASSUMPTION; NEVER infer preference for club provision from refusal to pay without direct EvidenceSpan support; mark ungrounded counterfactual comparisons UNRESOLVED_DUE_TO_COUNTERFACTUAL_UTILITY with zero arbitrary point utility.
- [ ] PreferenceCell alternative_probabilities and PreferenceUncertaintySet scenarios sum to 1.0 within numerical tolerance (1e-4) for usable cells; semantic_importance, coder_confidence, coder_agreement, missingness_state, and evidence_ids remain separate.

### Test Commands to Run
```bash
source .venv/bin/activate
pytest tests/test_preference.py -v
```

---

## 8. Mandatory Agent Handoff
Before finishing, write your formal handoff to:
`docs/AGENT_HANDOFFS/agent_04_handoff.md`
following the template in [`docs/AGENT_HANDOFFS/template_handoff.md`](file:///home/antigravity/necantis/HFG/docs/AGENT_HANDOFFS/template_handoff.md).

---

## 9. Git Collaboration, Shared-File Ownership & Artifact Handoff (`ADR-0007`)
- **Suggested Task Branch**: `agent/04-preference-pareto` (if it already exists, inspect it and safely resume or create a uniquely suffixed branch; never overwrite it).
- **Isolation & Git Rules**: Work in an isolated Git worktree, clone, or remote workspace; never switch branches in a shared filesystem; never push directly to `main`; never force-push; never bypass branch protection; never commit credentials, identity mappings, raw participant data, model weights, caches, or large runtime artifacts. Commit only task-related changes, push your task branch, and record the base commit and exact pushed commit SHA in your handoff.
- **Shared-File Non-Concurrency**: Do not concurrently edit `runs/<run_id>/manifest.json`, `runs/<run_id>/RUN_CARD.md`, `AGENTS.md`, `docs/PROJECT_STATE.md`, `src/context_pack.py`, `docs/AGENT_CONTEXT/agent_XX_context.md`, `src/contracts.py`, `schemas/interfaces.json`, `docs/DATA_CONTRACTS.md`, `pyproject.toml`, or another agent's handoff (`docs/AGENT_HANDOFFS/agent_XX_handoff.md`). To request a shared-file change, include a precise change request (affected interface, proposed fields/dependency, reason, compatibility impact, required tests) in your handoff; never create a second incompatible contract.
- **Artifact & Evidence Discipline**: Produce only task-local artifact descriptors and test outputs; only the integration process (Agent 11) publishes canonical production artifact registrations after validating merged code and source hashes. A planned artifact is not a completed artifact; a CPU-only runtime test is not a validated GPU benchmark; a passing fixture test is not a completed survey analysis.
- **Notebook Inventory**: Tracked vs. planned notebooks are indexed in `docs/NOTEBOOK_INDEX.md` (do not invent missing notebooks or create duplicate production entry points).
