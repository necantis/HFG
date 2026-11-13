# Agent Handoff Template

> **Instructions**: Every agent must copy and complete this document before terminating its turn or session. Save as `docs/AGENT_HANDOFFS/agent_XX_handoff.md`.

---

## Agent Handoff Information

- **Agent ID**: `agent_XX`
- **Model Used**: `pro | flash | flash_lite | inherit` (specify exact model name/revision if known)
- **Branch / Worktree**: `agent/XX-task-slug` (isolated worktree/clone/workspace; never push directly to `main`)
- **Base Commit**: `<base_commit_sha>`
- **Pushed Commit SHA**: `<pushed_commit_sha>`
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

## 3. Shared-File Change Requests (If Any)
*Implementation agents must NOT concurrently edit shared governance files, `src/contracts.py`, `schemas/interfaces.json`, `pyproject.toml`, `runs/<run_id>/manifest.json`, or peer handoffs. If a shared-file change is needed, specify each request below (otherwise state "None"):*
- **Affected interface**: `<file or contract name>`
- **Proposed fields or dependency**: `<exact fields/types or package version>`
- **Reason**: `<why required>`
- **Compatibility impact**: `<backwards-compatible | breaking | migration notes>`
- **Required tests**: `<pytest commands / assertions>`

---

## 4. Tests Executed
- List pytest commands run and test results:
  ```bash
  pytest tests/test_module.py -v
  ```
- *Pass / Fail counts and coverage summary (note explicitly if CPU-only or fixture-based; a CPU-only runtime test is not a validated GPU benchmark, and a passing fixture test is not a completed survey analysis).*

---

## 5. Artifacts Created & Registered
*(Distinguish task-local descriptors/test outputs from integration-published canonical production artifacts. A planned artifact is not a completed artifact.)*
- **Artifact ID**: `artifact_id_v1`
  - **Scope**: `task_local_test | integration_canonical`
  - **Path**: `data/...` or `runs/...`
  - **Schema Version**: `v1.0.0`
  - **Validation Status**: `valid`
  - **Provenance Hash**: `<sha256>`

---

## 6. Assumptions
- *State any domain, analytical, or implementation assumptions made during this session.*

---

## 7. Unresolved Issues & Blockers
- *Reference issue IDs from `docs/OPEN_ISSUES.md` or list any newly discovered blockers.*

---

## 8. Downstream Dependencies
- *List which agents/modules are directly unblocked or affected by this work.*

---

## 9. Exact Recommended Next Action
- *Provide the single, unambiguous command or step the succeeding agent must take.*

