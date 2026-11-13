# ADR-0007: Git Collaboration, Shared-File Ownership, and Artifact Handoff Policy

- **Decision ID**: `ADR-0007`
- **Date**: 2026-11-13
- **Status**: `APPROVED`
- **Superseded By**: None
- **Affected Modules**: `AGENTS.md`, `src/context_pack.py`, `docs/AGENT_CONTEXT/agent_XX_context.md`, `docs/NOTEBOOK_INDEX.md`, `docs/AGENT_HANDOFFS/template_handoff.md`, `pyproject.toml`, `src/contracts.py`, `schemas/interfaces.json`, `runs/<run_id>/manifest.json`
- **Dependencies**: `ADR-0001`, `ADR-0002`, `ADR-0003`, `ADR-0004`, `ADR-0005`, `ADR-0006`

---

## 1. Problem Statement

With Wave-2 implementation beginning across parallel specialist agents (such as Agent 01, Agent 02, Agent 07, and Agent 11), concurrent edits on `main` or concurrent modifications to shared governance, contract, manifest, and dependency files create severe risks:
1. Branch collisions, accidental overwrites, or shared-filesystem branch switching between concurrent agents.
2. Merge conflicts and silent drift across shared files (`AGENTS.md`, `docs/PROJECT_STATE.md`, `src/context_pack.py`, generated context packs, `src/contracts.py`, `schemas/interfaces.json`, `pyproject.toml`, `runs/<run_id>/manifest.json`, and peer handoffs).
3. Premature publication of canonical production artifact registrations before merged code and source hashes have been validated, or conflating planned/CPU-only/fixture test outputs with completed GPU benchmarks or full survey analyses.
4. Accidental commits of credentials, identity mappings, raw participant data, model weights, caches, or large runtime artifacts to Git.
5. Ambiguity between planned Colab production notebooks and per-agent exploratory notebooks where no `.ipynb` files are currently tracked.

---

## 2. Alternatives Considered

1. **Direct Commits to `main` with Ad-Hoc File Locking**:
   - *Drawbacks*: High risk of concurrent merge conflicts, dirty working trees blocking parallel agents, and unreviewed changes to shared contracts or canonical manifests.
2. **Parallel Feature Branches Allowing Direct Shared-File Edits**:
   - *Drawbacks*: Agents independently modifying `src/contracts.py`, `pyproject.toml`, `AGENTS.md`, or `runs/<run_id>/manifest.json` produce incompatible contract variants and manifest hash mismatches.
3. **Isolated Task Branches + Strict Shared-File Ownership + Integration-Gated Canonical Artifact Publication (Selected)**:
   - *Strengths*: Clean task isolation, deterministic handoff-based change requests for shared files, single integration authority (Agent 11), governance authority (Agent 10), and clear separation between task-local test outputs and canonical production manifests.

---

## 3. Selected Resolution & Rationale

### 3.1. Isolated Workspaces & Dedicated Task Branches
Parallel implementation agents must:
- work in isolated Git worktrees, clones, or remote workspaces;
- use a dedicated task branch (suggested names: `agent/01-ingestion-refinement`, `agent/02-qualitative-refinement`, `agent/07-runtime`, `agent/10-collaboration-policy`, `integration/wave-2a`);
- inspect any existing suggested branch first and either resume it safely or create a uniquely suffixed branch (**never overwrite**);
- never switch branches in a filesystem shared with another active agent;
- never push directly to `main` and never force-push;
- never commit credentials, identity mappings, raw participant data, model weights, caches, or large runtime artifacts;
- run relevant tests, write their handoff, commit only task-related changes, push their task branch, and report the exact pushed commit SHA;
- follow existing repository protection and approval requirements without bypassing branch protection.

### 3.2. Integration Ownership (Agent 11)
**Agent 11** owns integration:
- inspect task-branch diffs;
- resolve interface conflicts;
- run combined tests;
- refresh canonical manifests (`runs/<run_id>/manifest.json`) and context packs (`docs/AGENT_CONTEXT/agent_XX_context.md`, coordinating with Agent 10 governance rules);
- prepare the integrated branch for `main`.

### 3.3. Shared-File Ownership & Change Request Protocol
Implementation agents must **not** concurrently edit:
- the canonical run manifest (`runs/<run_id>/manifest.json`, `runs/<run_id>/RUN_CARD.md`);
- `AGENTS.md`;
- `docs/PROJECT_STATE.md`;
- the context-pack generator (`src/context_pack.py`);
- generated context packs (`docs/AGENT_CONTEXT/agent_XX_context.md`);
- shared contracts (`src/contracts.py`, `schemas/interfaces.json`, `docs/DATA_CONTRACTS.md`);
- the common dependency file (`pyproject.toml`);
- another agent's handoff (`docs/AGENT_HANDOFFS/agent_XX_handoff.md`).

Ownership and coordination split:
- **Agent 10** owns governance documentation and context-pack generation.
- **Agent 11** coordinates integration of shared executable contracts, dependencies, and canonical manifests.

When an implementation agent requires a shared-file change, it must record a precise change request in its own handoff (`docs/AGENT_HANDOFFS/agent_XX_handoff.md`) specifying:
1. affected interface;
2. proposed fields or dependency;
3. reason;
4. compatibility impact;
5. required tests.

Agents must **not** create a second incompatible contract to avoid coordination.

### 3.4. Artifact Handoff & Storage Policy
- Agents may produce task-local artifact descriptors and test outputs.
- **Only the integration process publishes canonical production artifact registrations** after validating the merged code and source hashes.
- Evidentiary distinctions enforced in all handoffs, manifests, and reviews:
  - A planned artifact is not a completed artifact.
  - A CPU-only runtime test is not a validated GPU benchmark.
  - A passing fixture test is not a completed survey analysis.
- Store sensitive or large runtime artifacts in approved persistent storage. Git should contain code, schemas, sanitized documentation, small safe metadata, and artifact references.

### 3.5. Authoritative Notebook Inventory (`docs/NOTEBOOK_INDEX.md`)
- `docs/NOTEBOOK_INDEX.md` tracks the exact set of tracked `.ipynb` files in Git (currently `0` tracked `.ipynb` files) separately from planned notebooks referenced in architectural documents.
- Agents must not invent missing notebooks or rename existing notebooks merely to match an earlier plan.
- Ambiguous paths and potential duplicate production entry points are flagged in `docs/NOTEBOOK_INDEX.md` for **Agent 11** to resolve prior to Wave-2 notebook creation.

---

## 4. Consequences
- **Positive**:
  - Zero concurrent-edit collisions on governance docs, shared contracts, dependencies, and canonical manifests.
  - Clear audit trail linking every task branch, exact pushed commit SHA, change request, and integration-validated artifact registration.
  - Explicit protection against overclaiming readiness from fixture or CPU-only tests.
- **Trade-offs**:
  - Shared contract or dependency additions require a structured handoff change request and Agent 11 integration step before appearing on `main`.
