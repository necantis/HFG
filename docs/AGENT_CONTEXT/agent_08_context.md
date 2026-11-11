# Context Pack: Agent 08 — Red Team & Invariant Auditor

> **Target Agent**: `agent_08`
> **Architecture Version**: `v1.0.0`
> **Active Run ID**: `run_20261111_001`
> **Generated Context**: Scoped specifically to your mission and boundaries. Do not request full project history.

---

## 1. Mission
Audit analytical outputs for invariant compliance: survey isolation, zero entity leakage, schema conformance, mathematical anti-symmetry, and absence of report feedback loops.

---

## 2. File Ownership Boundaries

### Files You Own (Authorized to Create & Modify)
- `src/validation/`
- `notebooks/08_verification_redteam.ipynb`

### Files You Must NOT Edit (Ownership Violations)
- ❌ `data/raw/*`
- ❌ `src/ingest/`
- ❌ `src/reporting/`
- ❌ Any other files outside your assigned ownership scope without an approved ADR.

---

## 3. Required Interfaces

### Input Interfaces (Upstream Contracts)
- `All registered stage artifacts via manifest.json`

### Output Interfaces (Deliverables)
- `audit_report_v1 (runs/<run_id>/audit_report.json)`

---

## 4. Dependencies & Canonical Artifacts

### Upstream Dependencies
- `runs/<run_id>/manifest.json`

### Downstream Consumers
- `agent_10 (Run Card Certification)`

### Authoritative Canonical Artifacts
- `runs/<run_id>/manifest.json` (Authoritative Manifest)
- `runs/<run_id>/audit_report.json` (Audit Verification)

---

## 5. Applicable Architecture Decision Records (ADRs)
- [`ADR-0001`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0001*.md)
- [`ADR-0002`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0002*.md)
- [`ADR-0004`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0004*.md)

---

## 6. Active Open Issues
*No open issues currently logged for this agent module.*

---

## 7. Acceptance Criteria & Test Execution
Before declaring your turn complete, you must satisfy:
- [ ] Cross-contamination detection runs across all qualitative and candidate artifacts.
- [ ] Schema conformance verified across 100% of registered outputs.
- [ ] Mathematical invariants (anti-symmetry, self-comparison) independently checked.

### Test Commands to Run
```bash
source .venv/bin/activate
pytest tests/test_validation.py -v
```

---

## 8. Mandatory Agent Handoff
Before finishing, write your formal handoff to:
`docs/AGENT_HANDOFFS/agent_08_handoff.md`
following the template in [`docs/AGENT_HANDOFFS/template_handoff.md`](file:///home/antigravity/necantis/HFG/docs/AGENT_HANDOFFS/template_handoff.md).
