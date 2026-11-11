# Context Pack: Agent 04 — Preference Learning & Reconciler

> **Target Agent**: `agent_04`
> **Architecture Version**: `v1.0.0`
> **Active Run ID**: `run_20261111_001`
> **Generated Context**: Scoped specifically to your mission and boundaries. Do not request full project history.

---

## 1. Mission
Construct reconciled pairwise preference matrices across all respondent pairs and candidates. Enforce mathematical anti-symmetry and self-comparison invariants.

---

## 2. File Ownership Boundaries

### Files You Own (Authorized to Create & Modify)
- `src/preference/`
- `notebooks/04_preference_learning.ipynb`

### Files You Must NOT Edit (Ownership Violations)
- ❌ `data/raw/*`
- ❌ `src/social_choice/`
- ❌ `src/reporting/`
- ❌ Any other files outside your assigned ownership scope without an approved ADR.

---

## 3. Required Interfaces

### Input Interfaces (Upstream Contracts)
- `answers_normalized_v1 (data/normalized/answers_normalized.parquet)`
- `candidate_options_v1 (data/processed/candidate_options.json)`

### Output Interfaces (Deliverables)
- `preference_matrix_v1 (data/processed/preference_matrix.parquet)`

---

## 4. Dependencies & Canonical Artifacts

### Upstream Dependencies
- `data/normalized/answers_normalized.parquet`
- `data/processed/candidate_options.json`

### Downstream Consumers
- `agent_05 (Social Choice Voting)`
- `agent_06 (Sensitivity Analyst)`

### Authoritative Canonical Artifacts
- `data/processed/candidate_options.json` (Canonical Option Set)
- `data/processed/preference_matrix.parquet` (Canonical Utility Input)

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
- [ ] Pairwise preference matrix satisfies anti-symmetry: pref(A, B) == -pref(B, A).
- [ ] Diagonal elements equal zero: pref(A, A) == 0.0.
- [ ] Outputs validate against preference_matrix_v1 contract.

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
