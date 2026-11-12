# ADR-0006: Reconciliation of Colab Execution Architecture and 20-Contract Baseline with 12-Agent Persistent Memory

- **Decision ID**: `ADR-0006`
- **Date**: 2026-11-12
- **Status**: `APPROVED`
- **Superseded By**: None
- **Affected Modules**: `AGENTS.md`, `docs/*`, `src/contracts.py`, `schemas/interfaces.json`, `src/freshness_checker.py`
- **Dependencies**: `ADR-0001`, `ADR-0002`, `ADR-0003`, `ADR-0004`, `ADR-0005`

---

## 1. Problem Statement
During parallel initialization, two architectural branches diverged before merging onto `main`:
1. The **12-Agent Persistent Memory Branch (`origin/main`)** established `ADR-0001` through `ADR-0005`, the 12-agent roster (`Agent 00`–`Agent 11`), `src/artifact_registry.py`, `src/context_pack.py`, `src/freshness_checker.py`, the authentic raw survey dataset `data/raw/survey_raw.csv` (`run_20261111_002`), and the distributional `PreferenceCell` contract.
2. The **Agent 00 Architecture & Contracts Branch (`95f4e61`)** established the 13-question multilingual (`fr`/`de`/`en`) domain-scoped analytical design, 20 typed Python interfaces (`src/contracts.py`, `schemas/interfaces.json`), the 5-notebook Google Colab execution pipeline (`00_control_plane.ipynb` through `04_validation.ipynb`) targeting dual concurrent LLMs on the NVIDIA RTX PRO 6000 Blackwell Server Edition, the 4-tier hardcoding classification, and the ~10-minute warm-cache checkpoint architecture.

Merging these branches required resolving textual and structural conflicts while eliminating all semantic contradictions.

---

## 2. Selected Resolution & Rationale

1. **Unified 12-Agent Ownership + 5-Stage Colab Execution Mapping**:
   - Preserve the 12-agent specialization (`Agent 00`–`Agent 11`), `notebooks/00_`–`11_` exploratory notebook mapping, and strict disambiguation between **Agent 09** (independent Final Integration Reviewer) and **Agent 11** (Orchestration & QA).
   - Map the 12 agents and 21 planned analytical modules (`src/ingestion.py` through `src/orchestrator.py`) onto the 5 Colab stage notebooks (`00_control_plane.ipynb`–`04_validation.ipynb`).
2. **Distributional `PreferenceCell` Alignment in `src/contracts.py`**:
   - Update `PreferenceCell` and `CodingResult` in `src/contracts.py` and `schemas/interfaces.json` to conform strictly to `ADR-0005`: primary preference is represented as `alternative_probabilities: dict[str, float]` summing to $1.0 \pm 10^{-4}$ for `observed_usable` cells, with `derived_scalar_score` permitted only as an optional derived field on ordered dimensions.
   - Preserve `semantic_importance`, `coder_confidence`, `coder_agreement`, `missingness_state`, and `evidence_span_ids` as strictly separate fields.
3. **Configurable Runtime Parameters & Constraint-Only Pareto Integrity**:
   - Ensure `GovernanceSolution` and `FeasibleAlternative` enforce constraint-only pruning (logical, institutional, structural dependencies) and ban cluster/value pre-filtering before Pareto analysis.
   - Align `RunManifest` and `RobustParetoResult` to reference Agent 07's `gpu_runtime_config_v1` and Agent 04's `pareto_mc_config_v1` rather than rigid constants.
4. **Freshness Checker Reconciliation**:
   - Permit planned Wave-2 analytical module paths and Colab stage notebook filenames defined in `docs/ARCHITECTURE.md` and `docs/IMPLEMENTATION_PLAN.md` within `src/freshness_checker.py` (`permitted_basenames`), preventing false-positive obsolescence warnings prior to Wave-2 implementation.

---

## 3. Consequences
- All 19 existing persistent-memory, registry, context-pack, freshness, and stateless-bootstrap acceptance tests remain green.
- Downstream Wave-2 agents (`01`–`11`) inherit a single unified source of truth with zero contradictions across `AGENTS.md`, `docs/DATA_CONTRACTS.md`, `src/contracts.py`, and `src/artifact_registry.py`.

