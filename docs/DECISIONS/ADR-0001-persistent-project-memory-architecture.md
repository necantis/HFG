# ADR-0001: Persistent Project Memory Architecture

- **Decision ID**: `ADR-0001`
- **Date**: 2026-11-11
- **Status**: `APPROVED`
- **Superseded By**: None
- **Affected Modules**: All (`AGENTS.md`, `docs/*`, `src/*`, `runs/*`)
- **Dependencies**: Git, Filesystem, `src/artifact_registry.py`

---

## 1. Problem Statement
In multi-agent collaborative engineering, agents frequently execute in stateless, isolated, or time-bounded sessions. Relying on conversational chat history across distinct agent turns introduces compounding context degradation, hallucinated state transitions, token explosion, and loss of synchronization across specialized roles.

## 2. Alternatives Considered
1. **Shared Continuous Chat History**: Passing the concatenated transcript of all previous agents to each new agent session.
   - *Drawbacks*: Severe context limit exhaustion, token cost explosion, high noise-to-signal ratio, rapid hallucination accumulation.
2. **Centralized External Vector DB / Blackboard Service**: Running an external daemon vector store for agent communication.
   - *Drawbacks*: Added runtime infrastructure dependency, non-deterministic retrieval, lack of atomic git versioning, hidden state outside the repository.
3. **Externalized Git & Manifest-Backed Persistent Memory (Selected)**: Treat git commits, structured manifests, Architecture Decision Records (ADRs), schemas, context packs, and registered artifacts as the single source of truth.

## 3. Selected Option & Rationale
We adopt **Option 3**: Chat history is explicitly declared ephemeral and non-authoritative. The repository's git tree, versioned documentation, cryptographic manifests (`runs/<run_id>/manifest.json`), ADRs, and scoped context packs constitute the persistent project memory.

## 4. Consequences
- **Positive**:
  - Independent agents can spin up with zero prior chat context and achieve full situational awareness within seconds.
  - Complete analytical auditability and reproducibility.
  - Zero cross-session conversational drift.
- **Negative / Trade-offs**:
  - Agents must strictly adhere to the handoff protocol before concluding sessions.
  - Artifacts must be formally registered and hashed.
