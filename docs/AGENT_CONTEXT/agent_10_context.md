# Context Pack: Agent 10 — Documentation, Memory & Artifact Engineer

> **Target Agent**: `agent_10`
> **Architecture Version**: `v1.0.0`
> **Active Run ID**: `run_20261111_001`
> **Generated Context**: Scoped specifically to your mission and boundaries. Do not request full project history.

---

## 1. Mission
Create and maintain persistent shared memory, artifact provenance, context packs, freshness checks, and Architecture Decision Records to enable seamless collaboration between independent Antigravity agents without reliance on chat history.

---

## 2. File Ownership Boundaries

### Files You Own (Authorized to Create & Modify)
- `src/artifact_registry.py`
- `src/context_pack.py`
- `src/freshness_checker.py`
- `AGENTS.md`
- `docs/`
- `runs/<run_id>/manifest.json`
- `runs/<run_id>/RUN_CARD.md`
- `notebooks/10_memory_and_registry.ipynb`

### Files You Must NOT Edit (Ownership Violations)
- ❌ `data/raw/* (immutable)`
- ❌ `src/ingest/`
- ❌ `src/nlp/`
- ❌ `src/candidates/`
- ❌ `src/preference/`
- ❌ `src/social_choice/`
- ❌ `src/robustness/`
- ❌ `src/reporting/`
- ❌ `src/validation/`
- ❌ `src/pipeline/`
- ❌ Any other files outside your assigned ownership scope without an approved ADR.

---

## 3. Required Interfaces

### Input Interfaces (Upstream Contracts)
- `All registered artifact records and documentation`

### Output Interfaces (Deliverables)
- `artifact_manifest_v1 (runs/<run_id>/manifest.json)`
- `run_card_v1 (runs/<run_id>/RUN_CARD.md)`
- `agent_context_packs (docs/AGENT_CONTEXT/agent_XX_context.md)`

---

## 4. Dependencies & Canonical Artifacts

### Upstream Dependencies
- `runs/<run_id>/manifest.json`

### Downstream Consumers
- `All Agents (Provides Context Packs & Registry Manifest)`

### Authoritative Canonical Artifacts
- `AGENTS.md` (Authoritative Agent Protocol)
- `docs/PROJECT_STATE.md` (Authoritative System State)
- `docs/DATA_CONTRACTS.md` (Authoritative Schemas)
- `runs/<run_id>/manifest.json` (Authoritative Manifest)
- `runs/<run_id>/RUN_CARD.md` (Authoritative Run Provenance)

---

## 5. Applicable Architecture Decision Records (ADRs)
- [`ADR-0001`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0001*.md)
- [`ADR-0002`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0002*.md)
- [`ADR-0003`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0003*.md)
- [`ADR-0004`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0004*.md)

---

## 6. Active Open Issues
*No open issues currently logged for this agent module.*

---

## 7. Acceptance Criteria & Test Execution
Before declaring your turn complete, you must satisfy:
- [ ] Context pack generation produces complete, accurate, scoped documentation for every agent.
- [ ] Artifact registry enforces canonical authority rules and immutability.
- [ ] Freshness checker identifies stale documentation, schema drifts, and ungrounded artifacts.
- [ ] Acceptance test verifies an agent with zero chat history can bootstrap completely from AGENTS.md and context pack.

### Test Commands to Run
```bash
source .venv/bin/activate
pytest tests/test_artifact_registry.py -v
pytest tests/test_context_pack.py -v
pytest tests/test_freshness_checker.py -v
pytest tests/test_acceptance.py -v
```

---

## 8. Mandatory Agent Handoff
Before finishing, write your formal handoff to:
`docs/AGENT_HANDOFFS/agent_10_handoff.md`
following the template in [`docs/AGENT_HANDOFFS/template_handoff.md`](file:///home/antigravity/necantis/HFG/docs/AGENT_HANDOFFS/template_handoff.md).
