# Context Pack: Agent 08 — Report

> **Target Agent**: `agent_08`
> **Architecture Version**: `v1.1.0`
> **Active Run ID**: `run_20261111_002`
> **Generated Context**: Scoped specifically to your mission and boundaries. Do not request full project history.

---

## 1. Mission
Synthesize stakeholder policy briefs, visual summaries, and decision presentations as strictly sink-only deliverables. CURRENT ADR-0009 GOVERNANCE STATE: AGENT_08_TECHNICAL_RELEASE = READY, AGENT_08_REPORTING_STATUS = HELD_FOR_RESOURCE_REGIME_SENSITIVITY. Do NOT start reporting execution until FRONTIER_B counterfactual sensitivity is completed and the governance hold is lifted (ISSUE-008).

---

## 2. File Ownership Boundaries

### Files You Own (Authorized to Create & Modify)
- `src/reporting/`
- `notebooks/08_reporting.ipynb`

### Files You Must NOT Edit (Ownership Violations)
- ❌ `data/raw/*`
- ❌ `src/ingest/`
- ❌ `src/preference/`
- ❌ `src/voting/`
- ❌ Any other files outside your assigned ownership scope without an approved ADR.

---

## 3. Required Interfaces

### Input Interfaces (Upstream Contracts)
- `voting_results_v1 (data/processed/voting_results.json)`
- `themes_codebook_v1 (data/processed/themes_codebook.json)`
- `preference_profiles_v1 (data/processed/preference_profiles.json)`
- `frontier_b_counterfactual_v1 (data/processed/preference/counterfactual/ — pending ISSUE-008)`

### Output Interfaces (Deliverables)
- `policy_brief_v1 (runs/<run_id>/reports/policy_brief.md)`

---

## 4. Dependencies & Canonical Artifacts

### Upstream Dependencies
- `data/processed/voting_results.json`
- `data/processed/themes_codebook.json`
- `data/processed/preference_profiles.json`

### Downstream Consumers
- `Human Stakeholders / End Users`
- `agent_09 (Final Integration Reviewer)`

### Authoritative Canonical Artifacts
- `runs/<run_id>/reports/policy_brief.md` (Presentation Only Artifact — Sink; HELD_FOR_RESOURCE_REGIME_SENSITIVITY)

---

## 5. Applicable Architecture Decision Records (ADRs)
- [`ADR-0001`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0001*.md)
- [`ADR-0002`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0002*.md)
- [`ADR-0005`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0005*.md)
- [`ADR-0006`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0006*.md)
- [`ADR-0007`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0007*.md)
- [`ADR-0008`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0008*.md)
- [`ADR-0009`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0009*.md)

---

## 6. Active Open Issues
| Issue ID | Severity | Component | Description | Status |
| :--- | :--- | :--- | :--- | :--- |
| `ISSUE-004` | `MEDIUM` | `src/validation/` | Implement automated red-team adversarial check for lexical leakage between distinct survey groups. | `OPEN` |
| `ISSUE-008` | `HIGH` | `src/contracts.py`, `src/preference/`, `src/pipeline/`, `src/reporting/` | **`ADR-0009` Counterfactual Resource-Regime Sensitivity (`FRONTIER_B`) & Agent 08 Reporting Hold**: Track (1) Agent 11 `ADR-0009` contract integration (`ResourceEligibilityStatus`, `GoodRegimeType`, 10-field `ClubGoodContract`, `ProvenanceCategory`, `UNRESOLVED_DUE_TO_COUNTERFACTUAL_UTILITY`, and orchestrator split `AGENT_08_TECHNICAL_RELEASE = READY` vs `AGENT_08_REPORTING_STATUS = HELD_FOR_RESOURCE_REGIME_SENSITIVITY`), (2) optional deterministic CPU `RESOURCE_ELIGIBILITY` tagging if needed (`NEW_LLM_CODING_REQUIRED = NO`), (3) isolated `FRONTIER_B` (`RESOURCE_REGIME_EXPANDED_FRONTIER`) sensitivity execution (`Q-A`–`Q-H`, `VG-01`–`VG-09`) preserving frozen `FRONTIER_A` (`543 / 326 / 10-248-285-0`) bit-for-bit, (4) isolated counterfactual manifest namespace registration, and (5) lifting `AGENT_08_REPORTING_STATUS` with mandatory dual-frontier separation (`ADR-0009` §10). Links `UNRES_GOODS_ENABLED_Q07_Q12_UNPOPULATED`. | `OPEN` |

---

## 7. Acceptance Criteria & Test Execution
Before declaring your turn complete, you must satisfy:
- [ ] WAIT FOR HOLD LIFT: Verify AGENT_08_REPORTING_STATUS transitions from HELD_FOR_RESOURCE_REGIME_SENSITIVITY to READY (AGENT_08_TECHNICAL_RELEASE = READY is already satisfied).
- [ ] Report FRONTIER_A (OBSERVED_DESIGN_FRONTIER) and FRONTIER_B (RESOURCE_REGIME_EXPANDED_FRONTIER) in strictly separate sections; never collapse counterfactual regimes into observed consensus.
- [ ] Preserve accurate FRONTIER_A scientific framing: 'A robust Pareto core exists, but no single collective-choice winner is stable across the admissible uncertainty scenarios' (never report 'no solution was found').
- [ ] State all 10 operational CLUB_GOOD fields (including non_member_compulsory_contribution = 0.0) and explicit 3-way provenance attribution (OBSERVED_RESPONDENT_PREFERENCE vs INSTITUTIONALLY_DERIVED_MECHANISM vs COUNTERFACTUAL_PREFERENCE_ASSUMPTION), never implying club preference from refusal to pay.
- [ ] Report artifact is registered with authority_level='presentation_only' and never consumed analytically.

### Test Commands to Run
```bash
source .venv/bin/activate
pytest tests/test_reporting.py -v
```

---

## 8. Mandatory Agent Handoff
Before finishing, write your formal handoff to:
`docs/AGENT_HANDOFFS/agent_08_handoff.md`
following the template in [`docs/AGENT_HANDOFFS/template_handoff.md`](file:///home/antigravity/necantis/HFG/docs/AGENT_HANDOFFS/template_handoff.md).

---

## 9. Git Collaboration, Shared-File Ownership & Artifact Handoff (`ADR-0007`)
- **Suggested Task Branch**: `agent/08-reporting` (if it already exists, inspect it and safely resume or create a uniquely suffixed branch; never overwrite it).
- **Isolation & Git Rules**: Work in an isolated Git worktree, clone, or remote workspace; never switch branches in a shared filesystem; never push directly to `main`; never force-push; never bypass branch protection; never commit credentials, identity mappings, raw participant data, model weights, caches, or large runtime artifacts. Commit only task-related changes, push your task branch, and record the base commit and exact pushed commit SHA in your handoff.
- **Shared-File Non-Concurrency**: Do not concurrently edit `runs/<run_id>/manifest.json`, `runs/<run_id>/RUN_CARD.md`, `AGENTS.md`, `docs/PROJECT_STATE.md`, `src/context_pack.py`, `docs/AGENT_CONTEXT/agent_XX_context.md`, `src/contracts.py`, `schemas/interfaces.json`, `docs/DATA_CONTRACTS.md`, `pyproject.toml`, or another agent's handoff (`docs/AGENT_HANDOFFS/agent_XX_handoff.md`). To request a shared-file change, include a precise change request (affected interface, proposed fields/dependency, reason, compatibility impact, required tests) in your handoff; never create a second incompatible contract.
- **Artifact & Evidence Discipline**: Produce only task-local artifact descriptors and test outputs; only the integration process (Agent 11) publishes canonical production artifact registrations after validating merged code and source hashes. A planned artifact is not a completed artifact; a CPU-only runtime test is not a validated GPU benchmark; a passing fixture test is not a completed survey analysis.
- **Notebook Inventory**: Tracked vs. planned notebooks are indexed in `docs/NOTEBOOK_INDEX.md` (do not invent missing notebooks or create duplicate production entry points).
