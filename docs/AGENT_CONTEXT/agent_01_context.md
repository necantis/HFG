# Context Pack: Agent 01 — Data & Question Registry

> **Target Agent**: `agent_01`
> **Architecture Version**: `v1.1.0`
> **Active Run ID**: `run_20261111_002`
> **Generated Context**: Scoped specifically to your mission and boundaries. Do not request full project history.

---

## 1. Mission
Ingest external raw survey CSV inputs, enforce raw survey immutability, maintain the question registry, and normalize responses into the canonical long-format answers artifact (answers_normalized_v1).

---

## 2. File Ownership Boundaries

### Files You Own (Authorized to Create & Modify)
- `src/ingest/`
- `src/registry/`
- `notebooks/01_ingest_exploration.ipynb`

### Files You Must NOT Edit (Ownership Violations)
- ❌ `data/raw/* (external immutable source)`
- ❌ `src/nlp/`
- ❌ `src/preference/`
- ❌ `docs/DECISIONS/`
- ❌ Any other files outside your assigned ownership scope without an approved ADR.

---

## 3. Required Interfaces

### Input Interfaces (Upstream Contracts)
- `survey_raw_v1 (data/raw/survey_raw.csv)`

### Output Interfaces (Deliverables)
- `answers_normalized_v1 (data/normalized/answers_normalized.parquet)`

---

## 4. Dependencies & Canonical Artifacts

### Upstream Dependencies
- `data/raw/survey_raw.csv`

### Downstream Consumers
- `agent_02 (Qualitative Coding)`
- `agent_04 (Preference, Utility & Pareto)`

### Authoritative Canonical Artifacts
- `data/raw/survey_raw.csv` (Immutable External Source)
- `data/normalized/answers_normalized.parquet` (Canonical Ingestion Artifact)

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
| `ISSUE-001` | `MEDIUM` | `src/ingest/` | Baseline raw survey data sample needs generation in `data/raw/survey_raw.csv` conforming to `survey_raw_v1`. | `RESOLVED` |

---

## 7. Acceptance Criteria & Test Execution
Before declaring your turn complete, you must satisfy:
- [ ] External raw survey data is ingested without modifying or overwriting data/raw/survey_raw.csv.
- [ ] Normalized answers validate against answers_normalized_v1 schema.
- [ ] All participant IDs and question dimensions are preserved without data loss.
- [ ] Output artifact is registered with src/artifact_registry.py.

### Test Commands to Run
```bash
source .venv/bin/activate
pytest tests/test_ingest.py -v
```

---

## 8. Mandatory Agent Handoff
Before finishing, write your formal handoff to:
`docs/AGENT_HANDOFFS/agent_01_handoff.md`
following the template in [`docs/AGENT_HANDOFFS/template_handoff.md`](file:///home/antigravity/necantis/HFG/docs/AGENT_HANDOFFS/template_handoff.md).
