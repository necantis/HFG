# Project State — HFG (Hybrid Feedback Governance)

> **Last Updated**: 2026-11-11
> **Maintained By**: Agent 10 (Documentation, Memory & Artifact Engineer)
> **Active Architecture Version**: `v1.0.0`
> **Active Run ID**: `run_20261111_001`

---

## 1. Global System Status

| Component | Status | Owner | Health Notes |
| :--- | :--- | :--- | :--- |
| **Documentation & Memory System** | `GREEN / ACTIVE` | Agent 10 | Core docs, ADRs, context packs, artifact registry, and freshness tooling online. |
| **Stage 1: Ingestion & Normalization** | `PENDING` | Agent 01 | Raw survey schemas finalized; awaits sample ingestion execution. |
| **Stage 2: Qualitative NLP Coding** | `PENDING` | Agent 02 | Extraction prompts and codebook data contract ready. |
| **Stage 3: Candidate Option Synthesis** | `PENDING` | Agent 03 | Candidate schema defined; awaits NLP themes. |
| **Stage 4: Preference Learning** | `PENDING` | Agent 04 | Pairwise matrix contract locked. |
| **Stage 5: Social Choice Voting** | `PENDING` | Agent 05 | Borda, Condorcet, Minimax rules specified. |
| **Stage 6: Robustness & Sensitivity** | `PENDING` | Agent 06 | Perturbation & bootstrap schema locked. |
| **Stage 7: Presentation Reporting** | `PENDING` | Agent 07 | Policy brief markdown template established (sink-only). |
| **Stage 8: Red-Team & Audit** | `PENDING` | Agent 08 | Cross-contamination invariant verifiers specified. |
| **Stage 9: Pipeline Orchestration** | `PENDING` | Agent 09 | DAG runner hooks configured. |

---

## 2. Active Run Coordinates: `run_20261111_001`
- **Run Directory**: [`runs/run_20261111_001/`](file:///home/antigravity/necantis/HFG/runs/run_20261111_001/)
- **Run Card**: [`runs/run_20261111_001/RUN_CARD.md`](file:///home/antigravity/necantis/HFG/runs/run_20261111_001/RUN_CARD.md)
- **Manifest**: [`runs/run_20261111_001/manifest.json`](file:///home/antigravity/necantis/HFG/runs/run_20261111_001/manifest.json)
- **Execution Mode**: Baseline validation and registry bootstrap run.

---

## 3. Registered Artifacts Summary

| Artifact ID | Canonical Path | Producing Agent | Status | Freshness |
| :--- | :--- | :--- | :--- | :--- |
| `raw_survey_v1` | `data/raw/survey_raw.csv` | Immutable Input | Registered | Fresh |
| `norm_answers_v1` | `data/normalized/answers_normalized.parquet` | Agent 01 | Contract Ready | Pending Run |
| `themes_codebook_v1` | `data/processed/themes_codebook.json` | Agent 02 | Contract Ready | Pending Run |
| `candidate_options_v1` | `data/processed/candidate_options.json` | Agent 03 | Contract Ready | Pending Run |
| `pref_matrix_v1` | `data/processed/preference_matrix.parquet` | Agent 04 | Contract Ready | Pending Run |
| `voting_results_v1` | `data/processed/voting_results.json` | Agent 05 | Contract Ready | Pending Run |
| `sensitivity_v1` | `data/processed/sensitivity_metrics.json` | Agent 06 | Contract Ready | Pending Run |
| `report_brief_v1` | `runs/run_20261111_001/reports/policy_brief.md` | Agent 07 | Presentation Only | Pending Run |

---

## 4. Architecture Decisions & Records (ADR Summary)
- [`ADR-0001`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0001-persistent-project-memory-architecture.md): Persistent Project Memory Architecture (Git, manifests, ADRs, context packs instead of chat history).
- [`ADR-0002`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0002-canonical-artifact-hierarchy-and-immutability.md): Canonical Artifact Hierarchy, Immutability of Raw Data, and Prohibition of Report Feedback.
- [`ADR-0003`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0003-context-pack-generation-strategy.md): Context Pack Generation and Scope Isolation.
- [`ADR-0004`](file:///home/antigravity/necantis/HFG/docs/DECISIONS/ADR-0004-artifact-registry-and-provenance-manifest.md): Artifact Registry, Provenance Hashes, and Stale State Propagation.

---

## 5. Recent Agent Handoffs
- [`docs/AGENT_HANDOFFS/agent_10_handoff.md`](file:///home/antigravity/necantis/HFG/docs/AGENT_HANDOFFS/agent_10_handoff.md) — Documentation, Memory & Artifact Engine established.

---

## 6. Immediate Next Milestones
1. Complete validation test suite for Artifact Registry and Context Pack generation.
2. Initialize sample raw survey data matching `survey_raw_v1` contract in `data/raw/survey_raw.csv`.
3. Agent 01 takes handoff to implement `src/ingest/` normalization pipeline.
