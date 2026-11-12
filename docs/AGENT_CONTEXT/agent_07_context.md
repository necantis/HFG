# Context Pack: Agent 07 — GPU Runtime

> **Target Agent**: `agent_07`
> **Architecture Version**: `v1.1.0`
> **Active Run ID**: `run_20261111_002`
> **Generated Context**: Scoped specifically to your mission and boundaries. Do not request full project history.

---

## 1. Mission
Manage hardware acceleration kernels, GPU device allocation, and memory fractions. Expose GPU memory fraction as a configurable runtime parameter, not an immutable constant.

---

## 2. File Ownership Boundaries

### Files You Own (Authorized to Create & Modify)
- `src/runtime/`
- `notebooks/07_gpu_runtime.ipynb`

### Files You Must NOT Edit (Ownership Violations)
- ❌ `data/raw/*`
- ❌ `src/ingest/`
- ❌ `src/reporting/`
- ❌ Any other files outside your assigned ownership scope without an approved ADR.

---

## 3. Required Interfaces

### Input Interfaces (Upstream Contracts)
- `Host GPU hardware environment and configuration requests`

### Output Interfaces (Deliverables)
- `gpu_runtime_config_v1 (runs/<run_id>/gpu_runtime_config.json)`

---

## 4. Dependencies & Canonical Artifacts

### Upstream Dependencies

### Downstream Consumers
- `agent_04 (Preference, Utility & Pareto)`
- `agent_05 (Clustering)`
- `agent_11 (Orchestration & QA)`

### Authoritative Canonical Artifacts
- `runs/<run_id>/gpu_runtime_config.json` (Configurable Runtime Parameter)

---

## 5. Applicable Architecture Decision Records (ADRs)
- [`ADR-0001`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0001*.md)
- [`ADR-0005`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0005*.md)

---

## 6. Active Open Issues
*No open issues currently logged for this agent module.*

---

## 7. Acceptance Criteria & Test Execution
Before declaring your turn complete, you must satisfy:
- [ ] GPU memory fractions are configurable at runtime via gpu_runtime_config.json.
- [ ] Fallback paths to CPU execution are verified in environments lacking GPU access.
- [ ] Memory boundaries prevent out-of-memory crashes during Monte Carlo simulations.

### Test Commands to Run
```bash
source .venv/bin/activate
pytest tests/test_runtime.py -v
```

---

## 8. Mandatory Agent Handoff
Before finishing, write your formal handoff to:
`docs/AGENT_HANDOFFS/agent_07_handoff.md`
following the template in [`docs/AGENT_HANDOFFS/template_handoff.md`](file:///home/antigravity/necantis/HFG/docs/AGENT_HANDOFFS/template_handoff.md).
