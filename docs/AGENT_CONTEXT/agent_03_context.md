# Context Pack: Agent 03 — Candidate & Option Synthesizer

> **Target Agent**: `agent_03`
> **Architecture Version**: `v1.0.0`
> **Active Run ID**: `run_20261111_001`
> **Generated Context**: Scoped specifically to your mission and boundaries. Do not request full project history.

---

## 1. Mission
Synthesize discrete candidate options and policy proposals from grounded qualitative themes. Ensure all candidates are grounded in participant evidence.

---

## 2. File Ownership Boundaries

### Files You Own (Authorized to Create & Modify)
- `src/candidates/`
- `notebooks/03_candidate_generation.ipynb`

### Files You Must NOT Edit (Ownership Violations)
- ❌ `data/raw/*`
- ❌ `src/ingest/`
- ❌ `src/social_choice/`
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
- `agent_04 (Preference Learning)`
- `agent_05 (Social Choice)`

### Authoritative Canonical Artifacts
- `data/processed/themes_codebook.json` (Canonical Qualitative Artifact)
- `data/processed/candidate_options.json` (Canonical Option Set)

---

## 5. Applicable Architecture Decision Records (ADRs)
- [`ADR-0001`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0001*.md)
- [`ADR-0002`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0002*.md)

---

## 6. Active Open Issues
*No open issues currently logged for this agent module.*

---

## 7. Acceptance Criteria & Test Execution
Before declaring your turn complete, you must satisfy:
- [ ] Synthesized candidates reference valid theme_ids in grounding_theme_ids.
- [ ] Candidate titles and descriptions are distinct, balanced, and evidence-grounded.
- [ ] candidate_options.json conforms to candidate_options_v1 schema.

### Test Commands to Run
```bash
source .venv/bin/activate
pytest tests/test_candidates.py -v
```

---

## 8. Mandatory Agent Handoff
Before finishing, write your formal handoff to:
`docs/AGENT_HANDOFFS/agent_03_handoff.md`
following the template in [`docs/AGENT_HANDOFFS/template_handoff.md`](file:///home/antigravity/necantis/HFG/docs/AGENT_HANDOFFS/template_handoff.md).
