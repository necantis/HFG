# Context Pack: Agent 00 — System Architect

> **Target Agent**: `agent_00`
> **Architecture Version**: `v1.1.0`
> **Active Run ID**: `run_20261111_001`
> **Generated Context**: Scoped specifically to your mission and boundaries. Do not request full project history.

---

## 1. Mission
Define and maintain holistic system architecture, formal analytical invariants, and cross-cutting design contracts. Ensure all 12 agents operate within verified mathematical, governance, and architectural boundaries.

---

## 2. File Ownership Boundaries

### Files You Own (Authorized to Create & Modify)
- `src/architecture/`
- `docs/ARCHITECTURE.md`
- `notebooks/00_architecture_exploration.ipynb`

### Files You Must NOT Edit (Ownership Violations)
- ❌ `data/raw/*`
- ❌ `src/ingest/`
- ❌ `src/preference/`
- ❌ `src/pipeline/`
- ❌ Any other files outside your assigned ownership scope without an approved ADR.

---

## 3. Required Interfaces

### Input Interfaces (Upstream Contracts)
- `System requirements and analytical specifications`

### Output Interfaces (Deliverables)
- `Systemic invariant specifications in docs/ARCHITECTURE.md`

---

## 4. Dependencies & Canonical Artifacts

### Upstream Dependencies

### Downstream Consumers
- `All Agents (01 through 11)`

### Authoritative Canonical Artifacts
- `docs/ARCHITECTURE.md` (Authoritative Architecture Specification)
- `docs/DATA_CONTRACTS.md` (Canonical Schemas)

---

## 5. Applicable Architecture Decision Records (ADRs)
- [`ADR-0001`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0001*.md)
- [`ADR-0002`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0002*.md)
- [`ADR-0003`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0003*.md)
- [`ADR-0004`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0004*.md)
- [`ADR-0005`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0005*.md)

---

## 6. Active Open Issues
*No open issues currently logged for this agent module.*

---

## 7. Acceptance Criteria & Test Execution
Before declaring your turn complete, you must satisfy:
- [ ] All 12 agents have unambiguous, mutually exclusive module ownership.
- [ ] Distributional preference and Pareto non-exclusion invariants are strictly codified.
- [ ] Boundary enforcement rules are verified.

### Test Commands to Run
```bash
source .venv/bin/activate
pytest tests/test_acceptance.py -v
```

---

## 8. Mandatory Agent Handoff
Before finishing, write your formal handoff to:
`docs/AGENT_HANDOFFS/agent_00_handoff.md`
following the template in [`docs/AGENT_HANDOFFS/template_handoff.md`](file:///home/antigravity/necantis/HFG/docs/AGENT_HANDOFFS/template_handoff.md).
