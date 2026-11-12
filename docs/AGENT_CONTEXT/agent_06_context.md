# Context Pack: Agent 06 — Voting

> **Target Agent**: `agent_06`
> **Architecture Version**: `v1.1.0`
> **Active Run ID**: `run_20261111_002`
> **Generated Context**: Scoped specifically to your mission and boundaries. Do not request full project history.

---

## 1. Mission
Execute social choice aggregation rules (Borda count, Condorcet pairwise winner, Minimax) over the reconciled preference matrix to determine consensus winners and collective rankings.

---

## 2. File Ownership Boundaries

### Files You Own (Authorized to Create & Modify)
- `src/voting/`
- `notebooks/06_voting_social_choice.ipynb`

### Files You Must NOT Edit (Ownership Violations)
- ❌ `data/raw/*`
- ❌ `src/preference/`
- ❌ `src/reporting/`
- ❌ Any other files outside your assigned ownership scope without an approved ADR.

---

## 3. Required Interfaces

### Input Interfaces (Upstream Contracts)
- `preference_matrix_v1 (data/processed/preference_matrix.parquet)`
- `candidate_options_v1 (data/processed/candidate_options.json)`

### Output Interfaces (Deliverables)
- `voting_results_v1 (data/processed/voting_results.json)`

---

## 4. Dependencies & Canonical Artifacts

### Upstream Dependencies
- `data/processed/preference_matrix.parquet`
- `data/processed/candidate_options.json`

### Downstream Consumers
- `agent_08 (Report)`
- `agent_09 (Final Integration Reviewer)`

### Authoritative Canonical Artifacts
- `data/processed/preference_matrix.parquet` (Canonical Utility Input)
- `data/processed/voting_results.json` (Canonical Decision Artifact)

---

## 5. Applicable Architecture Decision Records (ADRs)
- [`ADR-0001`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0001*.md)
- [`ADR-0002`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0002*.md)
- [`ADR-0004`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0004*.md)
- [`ADR-0005`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0005*.md)

---

## 6. Active Open Issues
| Issue ID | Severity | Component | Description | Status |
| :--- | :--- | :--- | :--- | :--- |
| `ISSUE-003` | `LOW` | `src/robustness/` | Vectorized bootstrap iteration performance optimization for large respondent pools ($N > 10,000$). | `OPEN` |

---

## 7. Acceptance Criteria & Test Execution
Before declaring your turn complete, you must satisfy:
- [ ] Borda count, Condorcet pairwise winner, and Minimax scores are computed correctly.
- [ ] Consensus winner is determined and unanimity status verified.
- [ ] Output JSON conforms to voting_results_v1 contract.

### Test Commands to Run
```bash
source .venv/bin/activate
pytest tests/test_voting.py -v
```

---

## 8. Mandatory Agent Handoff
Before finishing, write your formal handoff to:
`docs/AGENT_HANDOFFS/agent_06_handoff.md`
following the template in [`docs/AGENT_HANDOFFS/template_handoff.md`](file:///home/antigravity/necantis/HFG/docs/AGENT_HANDOFFS/template_handoff.md).
