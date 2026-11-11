# Data Contracts & Schemas — HFG

> **Status**: Approved (`v1.1.0` — 12-Agent Architecture)
> **Enforced by**: `src/artifact_registry.py`, `src/review/`, `src/pipeline/`
> **Rule**: Every artifact registered in the system MUST conform to its contract version.

---

## 1. Canonical Artifact Contracts Overview

| Contract ID | Canonical File Path | Format | Producing Agent | Consumer Agents | Authority Level |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `survey_raw_v1` | `data/raw/survey_raw.csv` | CSV | External Source | Agent 01 | **Immutable External Source** |
| `answers_normalized_v1` | `data/normalized/answers_normalized.parquet` | Parquet / JSON | Agent 01 | Agent 02, Agent 04 | **Canonical Ingestion** |
| `themes_codebook_v1` | `data/processed/themes_codebook.json` | JSON | Agent 02 | Agent 03, Agent 08 | **Canonical Qualitative** |
| `candidate_options_v1` | `data/processed/candidate_options.json` | JSON | Agent 03 | Agent 04, Agent 05, Agent 06 | **Canonical Option Set** |
| `preference_matrix_v1` | `data/processed/preference_matrix.parquet` | Parquet / JSON | Agent 04 | Agent 05, Agent 06 | **Canonical Utility Input** |
| `preference_profiles_v1` | `data/processed/preference_profiles.json` | JSON | Agent 05 | Agent 08, Agent 09 | **Interpretive Artifact (Non-Pruning)** |
| `voting_results_v1` | `data/processed/voting_results.json` | JSON | Agent 06 | Agent 08, Agent 09 | **Canonical Decision** |
| `gpu_runtime_config_v1`| `runs/<run_id>/gpu_runtime_config.json` | JSON | Agent 07 | Agent 04, Agent 05, Agent 11 | **Configurable Runtime Config** |
| `policy_brief_v1` | `runs/<run_id>/reports/policy_brief.md` | Markdown | Agent 08 | Stakeholders | **Presentation Only (Sink)** |
| `integration_review_v1`| `runs/<run_id>/integration_review_report.json` | JSON | Agent 09 | Agent 10, Agent 11 | **Authoritative Audit Artifact** |
| `artifact_manifest_v1` | `runs/<run_id>/manifest.json` | JSON | Agent 10 | All Agents | **Authoritative Manifest** |
| `run_card_v1` | `runs/<run_id>/RUN_CARD.md` | Markdown | Agent 10 | All Agents | **Authoritative Run Provenance** |
| `pipeline_qa_log_v1` | `runs/<run_id>/pipeline_execution.log` | Log / JSON | Agent 11 | Agent 09, Agent 10 | **Execution Trace & QA** |

---

## 2. Detailed Contract Definitions

### 2.1. `survey_raw_v1` (Immutable External Source)
- **Path**: `data/raw/survey_raw.csv`
- **Fields**:
  - `participant_id` (string, required, unique): Pseudonymous participant identifier.
  - `submission_time` (string, ISO 8601): Submission timestamp.
  - `q1_open_feedback` (string, optional): Qualitative response regarding system preferences.
  - `q2_ranking_choices` (string, optional): Delimited ranking string or score.
  - `group_cohort` (string, required): Cohort identifier.
- **Invariants**:
  - Write-once external input. Overwriting an existing raw survey file is strictly prohibited.
  - Registered as `immutable_source` with SHA-256 and dimensions verified in the run manifest.

---

### 2.2. `answers_normalized_v1` (Canonical Ingestion Artifact)
- **Path**: `data/normalized/answers_normalized.parquet` (or `.json`)
- **Schema**:
  ```json
  {
    "response_id": "string (UUID or deterministic hash)",
    "participant_id": "string",
    "question_id": "string",
    "response_type": "string (categorical | numeric | open_text | ranking)",
    "raw_value": "string",
    "normalized_value": "string | number | list",
    "is_valid": "boolean",
    "validation_flags": ["list of strings"]
  }
  ```
- **Invariants**:
  - All records must map to an immutable source `participant_id`.
  - Missing or malformed records must be explicitly flagged with `is_valid: false`.

---

### 2.3. `themes_codebook_v1` (Canonical Qualitative Themes)
- **Path**: `data/processed/themes_codebook.json`
- **Schema**:
  ```json
  {
    "schema_version": "v1.1.0",
    "run_id": "string",
    "themes": [
      {
        "theme_id": "string (TH-001)",
        "name": "string",
        "description": "string",
        "keywords": ["string"],
        "evidence_response_ids": ["string (references answers_normalized_v1.response_id)"],
        "support_count": "integer"
      }
    ]
  }
  ```
- **Invariants**:
  - Every `evidence_response_ids` item MUST resolve to a valid `response_id` in `answers_normalized_v1`.

---

### 2.4. `candidate_options_v1` (Canonical Option Set)
- **Path**: `data/processed/candidate_options.json`
- **Schema**:
  ```json
  {
    "schema_version": "v1.1.0",
    "candidates": [
      {
        "candidate_id": "string (CAND-01)",
        "title": "string",
        "description": "string",
        "grounding_theme_ids": ["string (references themes_codebook_v1.theme_id)"],
        "feasibility_constraints": ["string (logical, institutional, or dependency constraints)"]
      }
    ]
  }
  ```
- **Invariants**:
  - Feasible-option pruning may depend **only** on explicit logical, institutional, or dependency constraints.
  - Clusters, centroids, and empirical archetypes must NOT be used to prune feasible candidates before Pareto analysis.

---

### 2.5. `preference_matrix_v1` & `PreferenceCell` (Canonical Utility Input)
- **Path**: `data/processed/preference_matrix.parquet` (or `.json`)
- **Schema (`PreferenceCell`)**:
  ```json
  {
    "participant_id": "string",
    "cell_id": "string",
    "question_or_dimension_id": "string",
    "alternative_probabilities": {
      "<alternative_id>": "float (probability >= 0.0)"
    },
    "semantic_importance": "float (relative importance weight)",
    "coder_confidence": "float (0.0 to 1.0)",
    "coder_agreement": "float (inter-coder reliability metric)",
    "missingness_state": "string (observed_usable | unobserved_missing | infeasible_choice | ambiguous)",
    "evidence_ids": ["string (references answers_normalized_v1.response_id)"],
    "derived_scalar_score": "float | null (optional derived representation only when alternatives have a defensible ordering)"
  }
  ```
- **Invariants**:
  - **Probability Simplex Normalization**: For observed usable preference cells (`missingness_state == "observed_usable"`), the alternative probabilities must sum to 1 within numerical tolerance:
    $$\sum_{k} \text{alternative\_probabilities}[k] = 1.0 \pm 10^{-4}$$
  - **Separate Preserved Fields**: `semantic_importance`, `coder_confidence`, `coder_agreement`, `missingness_state`, and `evidence_ids` must be kept strictly separate from `alternative_probabilities`.
  - **Scalar Score Restriction**: `derived_scalar_score` may exist only as an optional derived representation when the alternatives possess an analytically defensible ordering.

---

### 2.6. `preference_profiles_v1` (Empirical Archetypes & Clustering)
- **Path**: `data/processed/preference_profiles.json`
- **Schema**:
  ```json
  {
    "schema_version": "v1.1.0",
    "run_id": "string",
    "archetypes": [
      {
        "profile_id": "string (PROF-01)",
        "name": "string",
        "centroid_distribution": {"<alternative_id>": "float"},
        "value_coherence_score": "float",
        "member_participant_ids": ["string"]
      }
    ]
  }
  ```
- **Invariants**:
  - **Non-Pruning Invariant**: May be used to interpret and contextualize institutional solutions, but must **NOT** be used to exclude otherwise feasible solutions before Pareto analysis.

---

### 2.7. `voting_results_v1` (Canonical Decision Artifact)
- **Path**: `data/processed/voting_results.json`
- **Schema**:
  ```json
  {
    "schema_version": "v1.1.0",
    "run_id": "string",
    "social_choice_rules": {
      "borda_count": {
        "rankings": [{"candidate_id": "string", "score": "float", "rank": "integer"}],
        "winner": "string"
      },
      "condorcet": {
        "has_condorcet_winner": "boolean",
        "winner": "string | null",
        "copeland_scores": {"<candidate_id>": "integer"}
      },
      "minimax": {
        "rankings": [{"candidate_id": "string", "worst_loss": "float", "rank": "integer"}],
        "winner": "string"
      }
    },
    "consensus_winner": "string",
    "is_unanimous": "boolean"
  }
  ```

---

### 2.8. Configurable Runtime Contracts

#### `gpu_runtime_config_v1` (Agent 07)
- **Path**: `runs/<run_id>/gpu_runtime_config.json`
- **Fields**:
  - `gpu_memory_fraction`: `float` (default: 0.85, configurable runtime parameter)
  - `allow_growth`: `boolean` (default: true)
  - `device_ids`: `list[int]`

#### `pareto_mc_config_v1` (Agent 04)
- **Path**: `runs/<run_id>/pareto_mc_config.json`
- **Fields**:
  - `robust_pareto_mc_samples`: `integer` (default: 1000, configurable runtime parameter)
  - `bootstrap_seed`: `integer` (default: 42)
  - `confidence_interval`: `float` (default: 0.95)

---

### 2.9. `policy_brief_v1` (Presentation Only Artifact)
- **Path**: `runs/<run_id>/reports/policy_brief.md`
- **Authority**: Presentation only.
- **Rule**: Strictly forbidden from being listed as an `upstream_artifacts` dependency by any analytical module.

---

### 2.10. `integration_review_v1` (Independent Final Review)
- **Path**: `runs/<run_id>/integration_review_report.json`
- **Producing Agent**: Agent 09 (Final Integration Reviewer)
- **Fields**:
  - `audit_timestamp`: `string (ISO 8601)`
  - `overall_status`: `PASS | FAIL | ADVISORY`
  - `invariant_verifications`: `dict[str, boolean]` (survey_isolation, probability_simplex, pareto_non_exclusion, etc.)
  - `red_team_findings`: `list[dict]`

---

### 2.11. `artifact_manifest_v1` & `run_card_v1` (Provenance)
- **Manifest Path**: `runs/<run_id>/manifest.json`
- **Run Card Path**: `runs/<run_id>/RUN_CARD.md`
- Persists cryptographic provenance, input hashes, Git commit, prompt hashes, and artifact freshness state.
