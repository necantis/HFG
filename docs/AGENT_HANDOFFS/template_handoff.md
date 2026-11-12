# Agent Handoff Template

> **Instructions**: Every agent must copy and complete this document before terminating its turn or session. Save as `docs/AGENT_HANDOFFS/agent_XX_handoff.md`.

---

## Agent Handoff Information

- **Agent ID**: `agent_XX`
- **Model Used**: `pro | flash | flash_lite | inherit` (specify exact model name/revision if known)
- **Branch / Worktree**: `main` (or feature branch)
- **Timestamp (UTC)**: `YYYY-MM-DDTHH:MM:SSZ`

---

## 1. Files Changed
- `path/to/file1.py` (Created / Modified)
- `docs/path/to/doc.md` (Updated)

---

## 2. Interfaces Changed
- *Detail any additions, deprecations, or modifications to data contracts or public module APIs.*
- *If none, explicitly state "None (Conforms to existing data contracts)".*

---

## 3. Tests Executed
- List pytest commands run and test results:
  ```bash
  pytest tests/test_module.py -v
  ```
- *Pass / Fail counts and coverage summary.*

---

## 4. Artifacts Created & Registered
- **Artifact ID**: `artifact_id_v1`
  - **Path**: `data/...` or `runs/...`
  - **Schema Version**: `v1.0.0`
  - **Validation Status**: `valid`
  - **Provenance Hash**: `<sha256>`

---

## 5. Assumptions
- *State any domain, analytical, or implementation assumptions made during this session.*

---

## 6. Unresolved Issues & Blockers
- *Reference issue IDs from `docs/OPEN_ISSUES.md` or list any newly discovered blockers.*

---

## 7. Downstream Dependencies
- *List which agents/modules are directly unblocked or affected by this work.*

---

## 8. Exact Recommended Next Action
- *Provide the single, unambiguous command or step the succeeding agent must take.*
