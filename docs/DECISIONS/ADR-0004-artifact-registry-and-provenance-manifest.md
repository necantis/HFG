# ADR-0004: Artifact Registry and Provenance Manifest

- **Decision ID**: `ADR-0004`
- **Date**: 2026-11-11
- **Status**: `APPROVED`
- **Superseded By**: None
- **Affected Modules**: `src/artifact_registry.py`, `src/freshness_checker.py`, `runs/*`
- **Dependencies**: `docs/DATA_CONTRACTS.md`, `ADR-0001`, `ADR-0002`

---

## 1. Problem Statement
In multi-stage multi-agent data pipelines, determining whether an analytical artifact is fresh, stale, corrupted, or produced by obsolete code/prompts requires rigorous metadata tracking. Without machine-readable provenance, downstream consumers cannot ascertain data validity.

## 2. Alternatives Considered
1. **Implicit File Timestamps**: Relying on OS filesystem `mtime`.
   - *Drawbacks*: Fragile across git clones, CI runners, and branch switches.
2. **Cryptographic Manifest Registry with DAG Dependency Tracking (Selected)**: Persisting JSON manifests (`runs/<run_id>/manifest.json`) capturing Git commits, SHA-256 hashes of inputs and code, prompt hashes, model revisions, schema versions, validation statuses, and upstream/downstream DAG links.

## 3. Selected Option & Rationale
We implement `src/artifact_registry.py`. Every artifact produced by any agent must be registered with complete provenance attributes. When an upstream artifact or source code file changes, downstream artifacts are automatically flagged as `stale`.

## 4. Consequences
- **Positive**:
  - Full cryptographic audit trail for every number and policy recommendation.
  - Automatic detection of stale dependencies and schema mismatches.
- **Negative / Trade-offs**:
  - Slight overhead during pipeline registration to compute SHA-256 digests.
