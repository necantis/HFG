# Context Pack: Agent 11 — Orchestration & QA

> **Target Agent**: `agent_11`
> **Architecture Version**: `v1.1.0`
> **Active Run ID**: `run_20261111_002`
> **Generated Context**: Scoped specifically to your mission and boundaries. Do not request full project history.

---

## 1. Mission
Sole owner of end-to-end pipeline execution, DAG scheduling, stage caching, runtime failure recovery, and automated QA regression test suites. Coordinates execution across Stages 00 through 10.

---

## 2. File Ownership Boundaries

### Files You Own (Authorized to Create & Modify)
- `src/pipeline/`
- `notebooks/11_orchestration_qa.ipynb`

### Files You Must NOT Edit (Ownership Violations)
- ❌ `data/raw/*`
- ❌ `src/artifact_registry.py`
- ❌ `src/review/`
- ❌ Any other files outside your assigned ownership scope without an approved ADR.

---

## 3. Required Interfaces

### Input Interfaces (Upstream Contracts)
- `Pipeline stage definitions in docs/PIPELINE.md`

### Output Interfaces (Deliverables)
- `pipeline_qa_log_v1 (runs/<run_id>/pipeline_execution.log)`

---

## 4. Dependencies & Canonical Artifacts

### Upstream Dependencies
- `data/raw/survey_raw.csv`

### Downstream Consumers
- `All Analytical Agents (00 through 10)`

### Authoritative Canonical Artifacts
- `docs/PIPELINE.md` (Authoritative DAG Definition)
- `runs/<run_id>/pipeline_execution.log` (Execution Trace & QA Log)

---

## 5. Applicable Architecture Decision Records (ADRs)
- [`ADR-0001`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0001*.md)
- [`ADR-0004`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0004*.md)
- [`ADR-0005`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0005*.md)

---

## 6. Active Open Issues
*No open issues currently logged for this agent module.*

---

## 7. Acceptance Criteria & Test Execution
Before declaring your turn complete, you must satisfy:
- [ ] DAG runner executes stages in strict dependency order.
- [ ] Automatic halting and error isolation on stage validation failure.
- [ ] Automated QA test suite exercises acceptance criteria across all stages.
- [ ] Pipeline logs are persisted to runs/<run_id>/pipeline_execution.log.

### Test Commands to Run
```bash
source .venv/bin/activate
pytest tests/test_pipeline.py -v
```

---

## 8. Mandatory Agent Handoff
Before finishing, write your formal handoff to:
`docs/AGENT_HANDOFFS/agent_11_handoff.md`
following the template in [`docs/AGENT_HANDOFFS/template_handoff.md`](file:///home/antigravity/necantis/HFG/docs/AGENT_HANDOFFS/template_handoff.md).
