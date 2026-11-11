# Context Pack: Agent 04 — Preference, Utility & Pareto

> **Target Agent**: `agent_04`
> **Architecture Version**: `v1.1.0`
> **Active Run ID**: `run_20261111_001`
> **Generated Context**: Scoped specifically to your mission and boundaries. Do not request full project history.

---

## 1. Mission
Construct reconciled PreferenceCell matrices representing participant preferences primarily as probability distributions over feasible alternatives (summing to 1 within numerical tolerance). Compute Pareto frontiers. Dynamically tune robust-Pareto Monte Carlo sample counts as a configurable runtime parameter.

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
- `gpu_runtime_config_v1 (runs/<run_id>/gpu_runtime_config.json)`

### Output Interfaces (Deliverables)
- `preference_matrix_v1 (data/processed/preference_matrix.parquet)`
- `pareto_mc_config_v1 (runs/<run_id>/pareto_mc_config.json)`

---

## 4. Dependencies & Canonical Artifacts

### Upstream Dependencies
- `data/normalized/answers_normalized.parquet`
- `data/processed/candidate_options.json`

### Downstream Consumers
- `agent_05 (Preference Profiles / Clustering)`
- `agent_06 (Voting)`

### Authoritative Canonical Artifacts
- `data/processed/candidate_options.json` (Canonical Option Set)
- `data/processed/preference_matrix.parquet` (Canonical Utility Input)

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
| `ISSUE-002` | `LOW` | `src/preference/` | Handling missing pairwise comparisons in sparse respondent graphs during matrix reconciliation. | `OPEN` |

---

## 7. Acceptance Criteria & Test Execution
Before declaring your turn complete, you must satisfy:
- [ ] PreferenceCell alternative_probabilities sum to 1.0 within numerical tolerance (1e-4) for usable cells.
- [ ] semantic_importance, coder_confidence, coder_agreement, missingness_state, and evidence_ids are preserved separately.
- [ ] Robust-Pareto Monte Carlo sample counts are exposed as a configurable runtime parameter.
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
