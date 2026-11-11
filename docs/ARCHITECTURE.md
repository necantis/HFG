# System Architecture — HFG (Hybrid Feedback Governance)

> **Core Axiom**: Chat history is not project memory. Git, manifests, Architecture Decision Records (ADRs), schemas, context packs, and registered artifacts are project memory.
> **Architecture Version**: `v1.1.0` (12-Agent Architecture)

---

## 1. Overview and Design Philosophy

HFG is structured as a decentralized, 12-agent analytical system designed for collaborative execution without relying on shared conversational history.

Traditional LLM agent workflows degrade rapidly when conversation contexts grow long, context windows truncate, or distinct agent sessions lose synchronization. HFG resolves this failure mode by establishing **externalized, machine-readable, and version-controlled project memory**:

```mermaid
flowchart TD
    subgraph PersistentMemory["Externalized Project Memory (Authoritative)"]
        GIT["Git Tree & Commits"]
        ADR["Architecture Decision Records (docs/DECISIONS/)"]
        CONTRACTS["Data Contracts & Schemas (docs/DATA_CONTRACTS.md)"]
        REGISTRY["Artifact Registry Manifest (runs/<run_id>/manifest.json)"]
        HANDOFFS["Agent Handoffs (docs/AGENT_HANDOFFS/)"]
    end

    subgraph AgentRuntime["Stateless Agent Execution Loop"]
        CPACK["Context Pack Generator (src/context_pack.py)"]
        AGENT["Specialist Agent (Agent 00..11)"]
        EXEC["Task Execution & Pytest Validation"]
        HANDOFF_OUT["Agent Handoff Emission"]
    end

    GIT --> CPACK
    CONTRACTS --> CPACK
    REGISTRY --> CPACK
    CPACK --> AGENT
    AGENT --> EXEC
    EXEC --> REGISTRY
    EXEC --> HANDOFF_OUT
    HANDOFF_OUT --> HANDOFFS
```

---

## 2. 12-Agent Specialization & Responsibilities

The system divides analytical and governance responsibilities among 12 specialized agents:

1. **Agent 00 — System Architect**: Owns holistic architecture specifications, invariant definitions, and cross-cutting design integrity (`src/architecture/`, `notebooks/00_architecture_exploration.ipynb`).
2. **Agent 01 — Data & Question Registry**: Ingests raw survey data, registers question metadata, and produces canonical normalized answers (`src/ingest/`, `src/registry/`, `notebooks/01_ingest_exploration.ipynb`).
3. **Agent 02 — Qualitative Coding**: Extracts grounded themes and qualitative codebooks from open-ended feedback (`src/nlp/`, `notebooks/02_qualitative_coding.ipynb`).
4. **Agent 03 — Evidence & Reconciliation**: Reconciles qualitative evidence, synthesizes discrete candidate options, and resolves semantic ambiguities (`src/evidence/`, `notebooks/03_evidence_reconciliation.ipynb`).
5. **Agent 04 — Preference, Utility & Pareto**: Constructs distributional PreferenceCells, models utility, computes Pareto frontiers, and tunes robust-Pareto Monte Carlo sample counts (`src/preference/`, `notebooks/04_preference_utility_pareto.ipynb`).
6. **Agent 05 — Preference Profiles / Clustering**: Derives empirical archetypes, clusters, and value coherence for institutional interpretation (`src/clustering/`, `notebooks/05_preference_profiles_clustering.ipynb`).
7. **Agent 06 — Voting**: Executes social choice mechanisms (Borda, Condorcet, Minimax) and determines consensus winners (`src/voting/`, `notebooks/06_voting_social_choice.ipynb`).
8. **Agent 07 — GPU Runtime**: Manages acceleration hardware, execution kernels, and tunes GPU memory allocation fractions (`src/runtime/`, `notebooks/07_gpu_runtime.ipynb`).
9. **Agent 08 — Report**: Generates stakeholder presentation artifacts and policy briefs as sink-only deliverables (`src/reporting/`, `notebooks/08_reporting.ipynb`).
10. **Agent 09 — Final Integration Reviewer**: Independent auditor performing holistic cross-stage verification, invariant auditing, and red-teaming. **Does NOT orchestrate pipelines** (`src/review/`, `notebooks/09_integration_review.ipynb`).
11. **Agent 10 — Documentation, Memory & Artifacts**: Implements persistent memory, context packs, artifact registry, and freshness tooling (`src/artifact_registry.py`, `src/context_pack.py`, `src/freshness_checker.py`, `notebooks/10_memory_and_registry.ipynb`).
12. **Agent 11 — Orchestration & QA**: Sole owner of end-to-end pipeline execution, DAG runner, stage caching, and automated QA suites (`src/pipeline/`, `notebooks/11_orchestration_qa.ipynb`).

---

## 3. Core Analytical Invariants & Mathematical Principles

### 3.1. Distributional Preference Representation (`PreferenceCell`)
- Preferences are modeled primarily as a probability distribution over actual feasible alternatives: `alternative_probabilities: dict[str, float]`.
- For observed usable cells, probabilities must satisfy $\sum p_i = 1 \pm 10^{-4}$.
- Uncertainty and contextual metrics (`semantic_importance`, `coder_confidence`, `coder_agreement`, `missingness_state`, and `evidence_ids`) are stored in distinct fields.
- Scalar preferences exist only as optional derived representations when alternatives possess an analytically defensible ordering.

### 3.2. Pareto Non-Exclusion Invariant
- Clusters, centroids, empirical archetypes, and value coherence may be used to interpret and contextualize institutional solutions.
- **They must NOT be used to prune or exclude otherwise feasible candidate solutions prior to Pareto analysis.**
- Feasible-option pruning may depend **only** on explicit logical, institutional, or dependency constraints.

### 3.3. Configurable Runtime Parameters
- **GPU Memory Fractions**: Owned and dynamically configured by Agent 07 (`gpu_runtime_config_v1`).
- **Robust-Pareto Monte Carlo Sample Counts**: Owned and dynamically configured by Agent 04 (`pareto_mc_config_v1`).
- These are runtime execution parameters, not immutable architectural constants.

### 3.4. Canonical-Source Rules & Sink-Only Reports
- `data/raw/survey_raw.csv` is an immutable external source (write-once, read-only).
- Presentation reports (`runs/<run_id>/reports/*.md`) are sink-only presentation deliverables and are strictly forbidden from becoming analytical inputs to any pipeline run.

---

## 4. Multi-Agent Lifecycle & Handoff Protocol

Each agent executes within a three-phase lifecycle:
1. **Bootstrap Phase**: Reads `AGENTS.md` and its scoped context pack (`docs/AGENT_CONTEXT/agent_XX_context.md`).
2. **Execution Phase**: Operates strictly within owned files, executes tests via `pytest`, and registers outputs with `src/artifact_registry.py`.
3. **Handoff Phase**: Writes standardized handoff to `docs/AGENT_HANDOFFS/agent_XX_handoff.md`, updates `docs/PROJECT_STATE.md`, and verifies zero drift via `src/freshness_checker.py`.
