# ADR-0003: Context Pack Generation Strategy

- **Decision ID**: `ADR-0003`
- **Date**: 2026-11-11
- **Status**: `APPROVED`
- **Superseded By**: None
- **Affected Modules**: `src/context_pack.py`, `docs/AGENT_CONTEXT/`
- **Dependencies**: `AGENTS.md`, `docs/DATA_CONTRACTS.md`, `ADR-0001`

---

## 1. Problem Statement
Providing the entirety of a project's documentation, code history, and irrelevant module contracts to an LLM agent consumes excessive context tokens, distracts the model from its core task, and increases the likelihood of boundary violations (e.g. editing files owned by other agents).

## 2. Alternatives Considered
1. **Monolithic Prompt Injection**: Every agent reads all markdown files in `docs/` upon starting.
   - *Drawbacks*: Token bloat, irrelevant distraction, potential confusion regarding role ownership.
2. **Dynamically Scoped Context Packs (Selected)**: Generate targeted context packs (`docs/AGENT_CONTEXT/agent_XX_context.md`) tailored specifically to each agent's mission, owned files, interfaces, upstream and downstream artifacts, open issues, and acceptance criteria.

## 3. Selected Option & Rationale
We implement `src/context_pack.py` to compile specialized context packs for each agent. Each context pack contains:
- Mission and role definition
- Current architecture version and active run ID
- Owned source files and notebooks
- Files the agent must NOT touch
- Formal input interfaces (upstream dependencies)
- Formal output interfaces (downstream deliverables)
- Canonical authoritative artifacts
- Active open issues matching the module scope
- Applicable ADRs
- Acceptance criteria and required tests

## 4. Consequences
- **Positive**:
  - Compact, high-signal prompt injection (< 2,000 tokens per agent).
  - Explicit boundary clarity prevents unauthorized file edits.
- **Negative / Trade-offs**:
  - Context packs must be kept refreshed or dynamically generated when project state updates.
