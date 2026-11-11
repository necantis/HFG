# Context Pack: Agent 06 — Robustness & Sensitivity Analyst

> **Target Agent**: `agent_06`
> **Architecture Version**: `v1.0.0`
> **Active Run ID**: `run_20261111_001`
> **Generated Context**: Scoped specifically to your mission and boundaries. Do not request full project history.

---

## 1. Mission
Perform bootstrap re-sampling, margin-of-victory calculations, and perturbation sensitivity to assess the stability and robustness of social choice voting results.

---

## 2. File Ownership Boundaries

### Files You Own (Authorized to Create & Modify)
- `src/robustness/`
- `notebooks/06_sensitivity_analysis.ipynb`

### Files You Must NOT Edit (Ownership Violations)
- ❌ `data/raw/*`
- ❌ `src/social_choice/`
- ❌ `src/reporting/`
- ❌ Any other files outside your assigned ownership scope without an approved ADR.

---

## 3. Required Interfaces

### Input Interfaces (Upstream Contracts)
- `voting_results_v1 (data/processed/voting_results.json)`
- `preference_matrix_v1 (data/processed/preference_matrix.parquet)`

### Output Interfaces (Deliverables)
- `sensitivity_metrics_v1 (data/processed/sensitivity_metrics.json)`

---

## 4. Dependencies & Canonical Artifacts

### Upstream Dependencies
- `data/processed/voting_results.json`
- `data/processed/preference_matrix.parquet`

### Downstream Consumers
- `agent_07 (Reporting)`
- `agent_08 (Audit)`

### Authoritative Canonical Artifacts
- `data/processed/voting_results.json` (Canonical Decision Artifact)
- `data/processed/sensitivity_metrics.json` (Canonical Robustness Artifact)

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
- [ ] Bootstrap confidence intervals and winner stability percentages are quantified.
- [ ] Perturbation tolerance margin is determined.
- [ ] sensitivity_metrics.json conforms to sensitivity_metrics_v1.

### Test Commands to Run
```bash
source .venv/bin/activate
pytest tests/test_robustness.py -v
```

---

## 8. Mandatory Agent Handoff
Before finishing, write your formal handoff to:
`docs/AGENT_HANDOFFS/agent_06_handoff.md`
following the template in [`docs/AGENT_HANDOFFS/template_handoff.md`](file:///home/antigravity/necantis/HFG/docs/AGENT_HANDOFFS/template_handoff.md).
