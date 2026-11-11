# Context Pack: Agent 05 — Preference Profiles / Clustering

> **Target Agent**: `agent_05`
> **Architecture Version**: `v1.1.0`
> **Active Run ID**: `run_20261111_001`
> **Generated Context**: Scoped specifically to your mission and boundaries. Do not request full project history.

---

## 1. Mission
Discover empirical preference archetypes, respondent clusters, and value coherence metrics to interpret institutional solutions. Enforce invariant: clusters/archetypes must NOT be used to prune or exclude feasible solutions prior to Pareto analysis.

---

## 2. File Ownership Boundaries

### Files You Own (Authorized to Create & Modify)
- `src/clustering/`
- `notebooks/05_preference_profiles_clustering.ipynb`

### Files You Must NOT Edit (Ownership Violations)
- ❌ `data/raw/*`
- ❌ `src/preference/`
- ❌ `src/voting/`
- ❌ Any other files outside your assigned ownership scope without an approved ADR.

---

## 3. Required Interfaces

### Input Interfaces (Upstream Contracts)
- `preference_matrix_v1 (data/processed/preference_matrix.parquet)`

### Output Interfaces (Deliverables)
- `preference_profiles_v1 (data/processed/preference_profiles.json)`

---

## 4. Dependencies & Canonical Artifacts

### Upstream Dependencies
- `data/processed/preference_matrix.parquet`

### Downstream Consumers
- `agent_08 (Report)`
- `agent_09 (Final Integration Reviewer)`

### Authoritative Canonical Artifacts
- `data/processed/preference_matrix.parquet` (Canonical Utility Input)
- `data/processed/preference_profiles.json` (Interpretive Artifact — Non-Pruning)

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
- [ ] Empirical archetypes and cluster centroids are derived for interpretive purposes.
- [ ] Zero feasible candidate options are excluded based on cluster membership prior to Pareto analysis.
- [ ] preference_profiles.json conforms to preference_profiles_v1 schema.

### Test Commands to Run
```bash
source .venv/bin/activate
pytest tests/test_clustering.py -v
```

---

## 8. Mandatory Agent Handoff
Before finishing, write your formal handoff to:
`docs/AGENT_HANDOFFS/agent_05_handoff.md`
following the template in [`docs/AGENT_HANDOFFS/template_handoff.md`](file:///home/antigravity/necantis/HFG/docs/AGENT_HANDOFFS/template_handoff.md).
