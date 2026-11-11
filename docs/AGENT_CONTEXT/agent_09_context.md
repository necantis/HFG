# Context Pack: Agent 09 — Orchestration & Execution Engineer

> **Target Agent**: `agent_09`
> **Architecture Version**: `v1.0.0`
> **Active Run ID**: `run_20261111_001`
> **Generated Context**: Scoped specifically to your mission and boundaries. Do not request full project history.

---

## 1. Mission
Coordinate automated DAG stage execution, manage checkpointing, and monitor pipeline run health and runtime performance.

---

## 2. File Ownership Boundaries

### Files You Own (Authorized to Create & Modify)
- `src/pipeline/`
- `notebooks/09_orchestration_monitoring.ipynb`

### Files You Must NOT Edit (Ownership Violations)
- ❌ `data/raw/*`
- ❌ `src/artifact_registry.py`
- ❌ Any other files outside your assigned ownership scope without an approved ADR.

---

## 3. Required Interfaces

### Input Interfaces (Upstream Contracts)
- `Pipeline stage definitions in docs/PIPELINE.md`

### Output Interfaces (Deliverables)
- `pipeline_execution_log (runs/<run_id>/pipeline_execution.log)`

---

## 4. Dependencies & Canonical Artifacts

### Upstream Dependencies
- `data/raw/survey_raw.csv`

### Downstream Consumers
- `All Analytical Agents (01-08)`

### Authoritative Canonical Artifacts
- `docs/PIPELINE.md` (Authoritative DAG Definition)
- `runs/<run_id>/pipeline_execution.log` (Execution Trace)

---

## 5. Applicable Architecture Decision Records (ADRs)
- [`ADR-0001`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0001*.md)
- [`ADR-0004`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0004*.md)

---

## 6. Active Open Issues
*No open issues currently logged for this agent module.*

---

## 7. Acceptance Criteria & Test Execution
Before declaring your turn complete, you must satisfy:
- [ ] DAG runner executes stages in strict dependency order.
- [ ] Automatic halting and error isolation on stage validation failure.
- [ ] Pipeline logs are persisted to runs/<run_id>/.

### Test Commands to Run
```bash
source .venv/bin/activate
pytest tests/test_pipeline.py -v
```

---

## 8. Mandatory Agent Handoff
Before finishing, write your formal handoff to:
`docs/AGENT_HANDOFFS/agent_09_handoff.md`
following the template in [`docs/AGENT_HANDOFFS/template_handoff.md`](file:///home/antigravity/necantis/HFG/docs/AGENT_HANDOFFS/template_handoff.md).
