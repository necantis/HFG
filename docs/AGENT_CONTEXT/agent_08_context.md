# Context Pack: Agent 08 — Report

> **Target Agent**: `agent_08`
> **Architecture Version**: `v1.1.0`
> **Active Run ID**: `run_20261111_001`
> **Generated Context**: Scoped specifically to your mission and boundaries. Do not request full project history.

---

## 1. Mission
Synthesize stakeholder policy briefs, visual summaries, and decision presentations. Enforce invariant: reports are strictly sink-only presentation artifacts and are never permitted to become analytical inputs to any pipeline run.

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
- `runs/<run_id>/reports/policy_brief.md` (Presentation Only Artifact — Sink)

---

## 5. Applicable Architecture Decision Records (ADRs)
- [`ADR-0001`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0001*.md)
- [`ADR-0002`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0002*.md)
- [`ADR-0005`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0005*.md)

---

## 6. Active Open Issues
| Issue ID | Severity | Component | Description | Status |
| :--- | :--- | :--- | :--- | :--- |
| `ISSUE-004` | `MEDIUM` | `src/validation/` | Implement automated red-team adversarial check for lexical leakage between distinct survey groups. | `OPEN` |

---

## 7. Acceptance Criteria & Test Execution
Before declaring your turn complete, you must satisfy:
- [ ] Policy brief accurately reflects voting results, themes, and empirical archetypes.
- [ ] Report artifact is registered with authority_level='presentation_only'.
- [ ] Report is never consumed as an analytical input by any upstream or peer module.

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
