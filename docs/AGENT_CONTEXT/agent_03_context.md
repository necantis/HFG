# Context Pack: Agent 03 — Evidence & Reconciliation

> **Target Agent**: `agent_03`
> **Architecture Version**: `v1.1.0`
> **Active Run ID**: `run_20261111_001`
> **Generated Context**: Scoped specifically to your mission and boundaries. Do not request full project history.

---

## 1. Mission
Reconcile qualitative evidence and participant proposals into discrete candidate options. Ensure feasible-option pruning depends strictly on explicit logical, institutional, or dependency constraints, never on empirical clustering.

---

## 2. File Ownership Boundaries

### Files You Own (Authorized to Create & Modify)
- `src/evidence/`
- `notebooks/03_evidence_reconciliation.ipynb`

### Files You Must NOT Edit (Ownership Violations)
- ❌ `data/raw/*`
- ❌ `src/ingest/`
- ❌ `src/voting/`
- ❌ `src/clustering/`
- ❌ Any other files outside your assigned ownership scope without an approved ADR.

---

## 3. Required Interfaces

### Input Interfaces (Upstream Contracts)
- `themes_codebook_v1 (data/processed/themes_codebook.json)`

### Output Interfaces (Deliverables)
- `candidate_options_v1 (data/processed/candidate_options.json)`

---

## 4. Dependencies & Canonical Artifacts

### Upstream Dependencies
- `data/processed/themes_codebook.json`

### Downstream Consumers
- `agent_04 (Preference, Utility & Pareto)`
- `agent_06 (Voting)`

### Authoritative Canonical Artifacts
- `data/processed/themes_codebook.json` (Canonical Qualitative Artifact)
- `data/processed/candidate_options.json` (Canonical Option Set)

---

## 5. Applicable Architecture Decision Records (ADRs)
- [`ADR-0001`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0001*.md)
- [`ADR-0002`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0002*.md)
- [`ADR-0005`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0005*.md)

---

## 6. Active Open Issues
*No open issues currently logged for this agent module.*

---

## 7. Acceptance Criteria & Test Execution
Before declaring your turn complete, you must satisfy:
- [ ] Synthesized candidates reference valid theme_ids in grounding_theme_ids.
- [ ] Pruning of candidate options relies ONLY on explicit logical, institutional, or dependency constraints.
- [ ] candidate_options.json conforms to candidate_options_v1 schema.

### Test Commands to Run
```bash
source .venv/bin/activate
pytest tests/test_evidence.py -v
```

---

## 8. Mandatory Agent Handoff
Before finishing, write your formal handoff to:
`docs/AGENT_HANDOFFS/agent_03_handoff.md`
following the template in [`docs/AGENT_HANDOFFS/template_handoff.md`](file:///home/antigravity/necantis/HFG/docs/AGENT_HANDOFFS/template_handoff.md).
