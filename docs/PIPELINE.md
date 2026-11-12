# Analytical Pipeline & Stage DAG — HFG

> **Status**: Approved (`v1.1.0` — 12-Agent Architecture)
> **Pipeline Orchestrator & QA**: Agent 11 (`src/pipeline/`)
> **Final Integration Reviewer**: Agent 09 (`src/review/`)
> **Registry & Provenance**: Agent 10 (`src/artifact_registry.py`)

---

## 1. Directed Acyclic Graph (DAG)

```mermaid
flowchart TD
    S0["Immutable External Source: data/raw/survey_raw.csv"] --> S1["Stage 01: Data & Question Registry (Agent 01)"]
    S1 -->|"data/normalized/answers_normalized.parquet"| S2["Stage 02: Qualitative Coding (Agent 02)"]
    S1 -->|"data/normalized/answers_normalized.parquet"| S4["Stage 04: Preference, Utility & Pareto (Agent 04)"]
    S2 -->|"data/processed/themes_codebook.json"| S3["Stage 03: Evidence & Reconciliation (Agent 03)"]
    S3 -->|"data/processed/candidate_options.json"| S4
    S3 -->|"data/processed/candidate_options.json"| S6["Stage 06: Voting (Agent 06)"]
    S4 -->|"data/processed/preference_matrix.parquet"| S5["Stage 05: Preference Profiles / Clustering (Agent 05)"]
    S4 -->|"data/processed/preference_matrix.parquet"| S6
    S2 -->|"data/processed/themes_codebook.json"| S8["Stage 08: Report (Agent 08)"]
    S5 -->|"data/processed/preference_profiles.json (Interpretive Only)"| S8
    S6 -->|"data/processed/voting_results.json"| S8
    S8 -->|"runs/<run_id>/reports/policy_brief.md"| S9["Stage 09: Final Integration Review (Agent 09)"]
    S5 --> S9
    S6 --> S9
    S9 -->|"runs/<run_id>/integration_review_report.json"| S10["Stage 10: Memory & Artifact Registry Freeze (Agent 10)"]
    S10 -->|"runs/<run_id>/RUN_CARD.md + manifest.json"| FIN["Frozen Certified Run Baseline"]

    GPU["Stage 07: GPU Runtime (Agent 07)"] -.-> S4
    GPU -.-> S5
    QA["Stage 11: Orchestration & QA (Agent 11)"] ==> S1
    QA ==> S2
    QA ==> S3
    QA ==> S4
    QA ==> S5
    QA ==> S6
    QA ==> S8
    QA ==> S9

    classDef immutable fill:#ffebee,stroke:#c62828,stroke-width:2px;
    classDef canonical fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px;
    classDef sink fill:#fff3e0,stroke:#ef6c00,stroke-width:2px;
    class S0 immutable;
    class S1,S2,S3,S4,S5,S6 canonical;
    class S8 sink;
```

---

## 2. Stage Breakdown & Execution Matrix

| Stage | Name | Owner | Canonical Input | Canonical Output | Validation Invariant |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **00** | System Architecture | Agent 00 | Project Charter | Architecture Specs | Invariant and boundary coherence |
| **01** | Data & Question Registry | Agent 01 | `data/raw/survey_raw.csv` | `data/normalized/answers_normalized.parquet` | Schema validation `answers_normalized_v1` |
| **02** | Qualitative Coding | Agent 02 | `answers_normalized.parquet` | `data/processed/themes_codebook.json` | Every evidence ID resolves to normalized answer |
| **03** | Evidence & Reconciliation | Agent 03 | `themes_codebook.json` | `data/processed/candidate_options.json` | Feasible-option pruning relies only on explicit constraints |
| **04** | Preference, Utility & Pareto | Agent 04 | `answers_normalized.parquet`, `candidate_options.json` | `data/processed/preference_matrix.parquet` | `PreferenceCell` alternative probabilities sum to 1.0 $\pm 10^{-4}$ |
| **05** | Preference Profiles / Clustering | Agent 05 | `preference_matrix.parquet` | `data/processed/preference_profiles.json` | Non-pruning rule: profiles used for empirical interpretation only |
| **06** | Voting | Agent 06 | `preference_matrix.parquet`, `candidate_options.json` | `data/processed/voting_results.json` | Multi-rule consistency (Borda, Condorcet, Minimax) |
| **07** | GPU Runtime | Agent 07 | Hardware / CUDA | `runs/<run_id>/gpu_runtime_config.json` | GPU memory fraction is configurable runtime parameter |
| **08** | Report | Agent 08 | `voting_results.json`, `themes_codebook.json`, `preference_profiles.json` | `runs/<run_id>/reports/policy_brief.md` | Markdown valid, **strictly sink-only (never analytical input)** |
| **09** | Final Integration Review | Agent 09 | All stage outputs | `runs/<run_id>/integration_review_report.json` | Independent audit, zero cross-contamination, invariant checks pass |
| **10** | Manifest & Run Card Freeze | Agent 10 | `manifest.json`, stage logs | `runs/<run_id>/RUN_CARD.md` | Full provenance & hash lock verification |
| **11** | Orchestration & QA Automation | Agent 11 | DAG definitions | `runs/<run_id>/pipeline_execution.log` | End-to-end execution, dependency order, test assertions |

---

## 3. Disambiguation: Orchestration vs. Review
- **Agent 11 (Orchestration & QA)**: Owns running the pipeline, dispatching stages, enforcing caching, and collecting QA test results.
- **Agent 09 (Final Integration Reviewer)**: Has zero operational orchestration responsibility. It acts as an independent adversarial reviewer and red team auditor validating that all pipeline invariants hold prior to final sign-off.

---

## 4. Analytical Invariants Enforced in Pipeline
1. **Pareto Non-Exclusion Invariant**: Stage 05 (Clustering) outputs must never be used by Stage 04 or Stage 06 to prune candidate solutions prior to Pareto frontier computation. Pruning is restricted exclusively to explicit constraints established in Stage 03.
2. **Distributional Preference Representation**: Stage 04 must verify that observed usable PreferenceCells have `alternative_probabilities` that sum to 1 within numerical tolerance.
