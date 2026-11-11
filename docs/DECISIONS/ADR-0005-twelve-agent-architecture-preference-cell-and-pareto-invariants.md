# ADR-0005: 12-Agent Architecture, Distributional PreferenceCell, and Pareto Invariants

- **Decision ID**: `ADR-0005`
- **Date**: 2026-11-11
- **Status**: `APPROVED`
- **Superseded By**: None
- **Affected Modules**: All (`AGENTS.md`, `src/*`, `docs/*`, `runs/*`)
- **Dependencies**: `ADR-0001`, `ADR-0002`, `ADR-0003`, `ADR-0004`

---

## 1. Problem Statement
Before Wave 2 execution begins, four critical architectural alignments were required:
1. **12-Agent Specialization**: Expand from initial scaffolding to the complete 12-agent system (Agents 00 through 11).
2. **Disambiguation of Integration Review and Orchestration**: Agent 09 must be an independent Final Integration Reviewer, while Agent 11 owns pipeline orchestration and QA.
3. **Preference Representation Rigor**: Preference modeling must avoid premature scalar collapse and faithfully represent participant choice as probability distributions over actual feasible alternatives.
4. **Pareto Integrity & Cluster Non-Exclusion**: Clustering, empirical archetypes, and value coherence must not be used to prematurely prune feasible options before Pareto analysis.
5. **Runtime Configurability**: GPU memory allocation and Monte Carlo sample counts must be dynamic runtime parameters rather than rigid architectural constants.

## 2. Alternatives Considered
1. **Retain 10-Agent Mapping with Hybrid Roles**:
   - *Drawback*: Conflates orchestration with independent review; lacks dedicated GPU runtime and architectural governance agents.
2. **Scalar-Only Preference Cells**:
   - *Drawback*: Discards distributional uncertainty, multimodality, and coder disagreement.
3. **Cluster-Based Candidate Pruning**:
   - *Drawback*: Excludes non-archetypal but Pareto-optimal compromise solutions, violating social choice fairness.
4. **12-Agent Architecture with Distributional PreferenceCells and Pareto Invariants (Selected)**.

## 3. Selected Option & Rationale

### 3.1. 12-Agent Division of Labor
- **Agent 00**: System Architect (`src/architecture/`)
- **Agent 01**: Data & Question Registry (`src/ingest/`, `src/registry/`)
- **Agent 02**: Qualitative Coding (`src/nlp/`)
- **Agent 03**: Evidence & Reconciliation (`src/evidence/`)
- **Agent 04**: Preference, Utility & Pareto (`src/preference/`)
- **Agent 05**: Preference Profiles / Clustering (`src/clustering/`)
- **Agent 06**: Voting (`src/voting/`)
- **Agent 07**: GPU Runtime (`src/runtime/`)
- **Agent 08**: Report (`src/reporting/`)
- **Agent 09**: Final Integration Reviewer (`src/review/`) — Independent review and audit; NOT orchestration.
- **Agent 10**: Documentation, Memory & Artifacts (`src/artifact_registry.py`, `src/context_pack.py`, `src/freshness_checker.py`, `docs/`)
- **Agent 11**: Orchestration & QA (`src/pipeline/`) — Sole owner of execution DAG and automated testing.

### 3.2. Canonical PreferenceCell Contract
Participant preference is modeled primarily as a probability distribution over the actual feasible alternatives:
- `alternative_probabilities: dict[str, float]` (must sum to $1.0 \pm 10^{-4}$ for observed usable cells).
- Separately preserved fields:
  - `semantic_importance: float`
  - `coder_confidence: float` (0.0 to 1.0)
  - `coder_agreement: float`
  - `missingness_state: str` (`observed_usable`, `unobserved_missing`, `infeasible_choice`, `ambiguous`)
  - `evidence_ids: list[str]`
- Scalar preference scores exist **only** as optional derived representations when alternatives possess an analytically defensible ordering.

### 3.3. Pareto Non-Exclusion Invariant
- Clusters, centroids, empirical archetypes, and value coherence may be used to interpret and characterize institutional solutions.
- They must **NOT** be used to exclude otherwise feasible solutions prior to Pareto analysis.
- Feasible-option pruning may depend **only** on explicit logical, institutional, or dependency constraints.

### 3.4. Configurable Runtime Parameters
- **GPU Memory Fractions**: Configurable runtime parameter owned and tuned by Agent 07 (`gpu_runtime_config_v1`).
- **Robust-Pareto Monte Carlo Sample Counts**: Configurable runtime parameter owned and tuned by Agent 04 (`pareto_mc_config_v1`).
- Neither parameter is hard-coded as an immutable architectural constant.

## 4. Consequences
- Independent auditability is guaranteed by decoupling Agent 09 (Reviewer) from Agent 11 (Orchestrator).
- Mathematical integrity is preserved by enforcing probability simplex normalization and banning premature cluster pruning.
- Full compatibility with existing cryptographic artifact registry and freshness checks.
