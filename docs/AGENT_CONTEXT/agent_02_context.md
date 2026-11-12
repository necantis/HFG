# Context Pack: Agent 02 — Qualitative Coding

> **Target Agent**: `agent_02`
> **Architecture Version**: `v1.1.0`
> **Active Run ID**: `run_20261111_002`
> **Generated Context**: Scoped specifically to your mission and boundaries. Do not request full project history.

---

## 1. Mission
Perform rigorous qualitative coding on open-ended survey responses, synthesize thematic codebooks, and extract participant themes without lexical or entity leakage from other survey populations.

---

## 2. File Ownership Boundaries

### Files You Own (Authorized to Create & Modify)
- `src/nlp/`
- `notebooks/02_qualitative_coding.ipynb`

### Files You Must NOT Edit (Ownership Violations)
- ❌ `data/raw/*`
- ❌ `src/ingest/`
- ❌ `src/evidence/`
- ❌ `src/preference/`
- ❌ Any other files outside your assigned ownership scope without an approved ADR.

---

## 3. Required Interfaces

### Input Interfaces (Upstream Contracts)
- `answers_normalized_v1 (data/normalized/answers_normalized.parquet)`

### Output Interfaces (Deliverables)
- `themes_codebook_v1 (data/processed/themes_codebook.json)`

---

## 4. Dependencies & Canonical Artifacts

### Upstream Dependencies
- `data/normalized/answers_normalized.parquet`

### Downstream Consumers
- `agent_03 (Evidence & Reconciliation)`
- `agent_08 (Report)`

### Authoritative Canonical Artifacts
- `data/normalized/answers_normalized.parquet` (Canonical Ingestion Artifact)
- `data/processed/themes_codebook.json` (Canonical Qualitative Artifact)

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
- [ ] Every extracted theme includes explicit evidence_response_ids grounded in answers_normalized.parquet.
- [ ] Themes pass cross-contamination check: zero entities or candidates from foreign survey groups.
- [ ] themes_codebook.json validates against themes_codebook_v1 contract.

### Test Commands to Run
```bash
source .venv/bin/activate
pytest tests/test_nlp.py -v
```

---

## 8. Mandatory Agent Handoff
Before finishing, write your formal handoff to:
`docs/AGENT_HANDOFFS/agent_02_handoff.md`
following the template in [`docs/AGENT_HANDOFFS/template_handoff.md`](file:///home/antigravity/necantis/HFG/docs/AGENT_HANDOFFS/template_handoff.md).
