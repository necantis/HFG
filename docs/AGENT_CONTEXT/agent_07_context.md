# Context Pack: Agent 07 — Report & Presentation Generator

> **Target Agent**: `agent_07`
> **Architecture Version**: `v1.0.0`
> **Active Run ID**: `run_20261111_001`
> **Generated Context**: Scoped specifically to your mission and boundaries. Do not request full project history.

---

## 1. Mission
Synthesize final stakeholder policy briefs and visual decision summaries. Maintain strict presentation-only status: report is sink-only and never analytical input.

---

## 2. File Ownership Boundaries

### Files You Own (Authorized to Create & Modify)
- `src/reporting/`
- `notebooks/07_reporting_presentation.ipynb`

### Files You Must NOT Edit (Ownership Violations)
- ❌ `data/raw/*`
- ❌ `src/ingest/`
- ❌ `src/preference/`
- ❌ `src/social_choice/`
- ❌ Any other files outside your assigned ownership scope without an approved ADR.

---

## 3. Required Interfaces

### Input Interfaces (Upstream Contracts)
- `voting_results_v1 (data/processed/voting_results.json)`
- `sensitivity_metrics_v1 (data/processed/sensitivity_metrics.json)`
- `themes_codebook_v1 (data/processed/themes_codebook.json)`

### Output Interfaces (Deliverables)
- `policy_brief_v1 (runs/<run_id>/reports/policy_brief.md)`

---

## 4. Dependencies & Canonical Artifacts

### Upstream Dependencies
- `data/processed/voting_results.json`
- `data/processed/sensitivity_metrics.json`
- `data/processed/themes_codebook.json`

### Downstream Consumers
- `Human Stakeholders / End Users`

### Authoritative Canonical Artifacts
- `runs/<run_id>/reports/policy_brief.md` (Presentation Only Artifact — Sink)

---

## 5. Applicable Architecture Decision Records (ADRs)
- [`ADR-0001`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0001*.md)
- [`ADR-0002`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0002*.md)

---

## 6. Active Open Issues
*No open issues currently logged for this agent module.*

---

## 7. Acceptance Criteria & Test Execution
Before declaring your turn complete, you must satisfy:
- [ ] Policy brief accurately reflects voting results, themes, and sensitivity bounds.
- [ ] Report artifact is registered with authority_level='presentation_only'.
- [ ] Report is never consumed by any upstream or peer analytical module.

### Test Commands to Run
```bash
source .venv/bin/activate
pytest tests/test_reporting.py -v
```

---

## 8. Mandatory Agent Handoff
Before finishing, write your formal handoff to:
`docs/AGENT_HANDOFFS/agent_07_handoff.md`
following the template in [`docs/AGENT_HANDOFFS/template_handoff.md`](file:///home/antigravity/necantis/HFG/docs/AGENT_HANDOFFS/template_handoff.md).
