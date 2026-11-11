# ADR-0002: Canonical Artifact Hierarchy and Immutability

- **Decision ID**: `ADR-0002`
- **Date**: 2026-11-11
- **Status**: `APPROVED`
- **Superseded By**: None
- **Affected Modules**: `src/artifact_registry.py`, `src/ingest/`, `src/reporting/`, `data/*`, `runs/*`
- **Dependencies**: `docs/DATA_CONTRACTS.md`, `ADR-0001`

---

## 1. Problem Statement
Analytical corruption in survey processing commonly originates from two failure modes:
1. In-place modification or corruption of raw survey responses.
2. Circular feedback loops where generated presentation reports or summaries are inadvertently fed back into subsequent analytical stages as ground-truth evidence.

## 2. Alternatives Considered
1. **Permissive Data Flow**: Allow modules to read any file in `runs/` or `data/` dynamically without provenance constraints.
   - *Drawbacks*: Severe risk of circular reasoning, data leakage, and undetectable contamination.
2. **Strict Layered Artifact Hierarchy with Immutability and Sink-Only Reports (Selected)**.

## 3. Selected Option & Rationale
We enforce an explicit hierarchy of authority:
- **Raw Survey Data (`data/raw/`)**: Immutable source. Write-once, read-only.
- **Normalized Ingestion (`data/normalized/`)**: Canonical ingested artifact for downstream modeling.
- **Intermediate Derived Artifacts (`data/processed/`)**: Reconciled preference matrices, candidate options, and social choice metrics.
- **Final Presentation Reports (`runs/<run_id>/reports/`)**: Strictly sink-only deliverables. They are programmatically blocked by `src/artifact_registry.py` from ever becoming upstream inputs to any analytical stage.

## 4. Consequences
- **Positive**:
  - Eliminates data leakage and circular justification.
  - Raw evidence is preserved intact for independent audit and verification.
- **Negative / Trade-offs**:
  - Any transformation of presentation material must be re-derived directly from canonical data artifacts.
