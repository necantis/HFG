# Context Pack: Agent 09 — Final Integration Reviewer

> **Target Agent**: `agent_09`
> **Architecture Version**: `v1.1.0`
> **Active Run ID**: `run_20261111_002`
> **Generated Context**: Scoped specifically to your mission and boundaries. Do not request full project history.

---

## 1. Mission
Serve as the independent final integration reviewer and red team auditor. Conduct holistic invariant audits: survey isolation, probability simplex compliance, Pareto non-exclusion verification, and absence of report feedback loops. DOES NOT orchestrate pipelines.

---

## 2. File Ownership Boundaries

### Files You Own (Authorized to Create & Modify)
- `src/review/`
- `notebooks/09_integration_review.ipynb`

### Files You Must NOT Edit (Ownership Violations)
- ❌ `data/raw/*`
- ❌ `src/ingest/`
- ❌ `src/pipeline/`
- ❌ `src/artifact_registry.py`
- ❌ Any other files outside your assigned ownership scope without an approved ADR.

---

## 3. Required Interfaces

### Input Interfaces (Upstream Contracts)
- `All registered stage artifacts via manifest.json`

### Output Interfaces (Deliverables)
- `integration_review_v1 (runs/<run_id>/integration_review_report.json)`

---

## 4. Dependencies & Canonical Artifacts

### Upstream Dependencies
- `runs/<run_id>/manifest.json`

### Downstream Consumers
- `agent_10 (Run Card Certification)`
- `agent_11 (Orchestration & QA)`

### Authoritative Canonical Artifacts
- `runs/<run_id>/manifest.json` (Authoritative Manifest)
- `runs/<run_id>/integration_review_report.json` (Independent Audit Report)

---

## 5. Applicable Architecture Decision Records (ADRs)
- [`ADR-0001`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0001*.md)
- [`ADR-0002`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0002*.md)
- [`ADR-0004`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0004*.md)
- [`ADR-0005`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0005*.md)

---

## 6. Active Open Issues
*No open issues currently logged for this agent module.*

---

## 7. Acceptance Criteria & Test Execution
Before declaring your turn complete, you must satisfy:
- [ ] Independent audit confirms zero survey cross-contamination across all artifacts.
- [ ] PreferenceCell probability distributions verified to sum to 1.0 within tolerance.
- [ ] Pareto non-exclusion invariant confirmed: no candidate pruned by clustering.
- [ ] Report sink-only invariant confirmed: reports never consumed analytically.

### Test Commands to Run
```bash
source .venv/bin/activate
pytest tests/test_review.py -v
```

---

## 8. Mandatory Agent Handoff
Before finishing, write your formal handoff to:
`docs/AGENT_HANDOFFS/agent_09_handoff.md`
following the template in [`docs/AGENT_HANDOFFS/template_handoff.md`](file:///home/antigravity/necantis/HFG/docs/AGENT_HANDOFFS/template_handoff.md).
