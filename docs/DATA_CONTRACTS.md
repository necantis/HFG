# Data Contracts & Schemas — HFG

> **Status**: Approved (`v1.0.0`)
> **Enforced by**: `src/artifact_registry.py`, `src/validation/`
> **Rule**: Every artifact registered in the system MUST conform to its contract version.

---

## 1. Canonical Artifact Contracts Overview

| Contract ID | Canonical File Path | Format | Producing Agent | Consumer Agents | Authority Level |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `survey_raw_v1` | `data/raw/survey_raw.csv` | CSV | Human / External | Agent 01 | **Immutable Source** |
| `answers_normalized_v1` | `data/normalized/answers_normalized.parquet` | Parquet / JSON | Agent 01 | Agent 02, Agent 04 | **Canonical Ingestion** |
| `themes_codebook_v1` | `data/processed/themes_codebook.json` | JSON | Agent 02 | Agent 03, Agent 07 | **Canonical Qualitative** |
| `candidate_options_v1` | `data/processed/candidate_options.json` | JSON | Agent 03 | Agent 04, Agent 05 | **Canonical Option Set** |
| `preference_matrix_v1` | `data/processed/preference_matrix.parquet` | Parquet / JSON | Agent 04 | Agent 05, Agent 06 | **Canonical Utility Input** |
| `voting_results_v1` | `data/processed/voting_results.json` | JSON | Agent 05 | Agent 06, Agent 07, Agent 08 | **Canonical Decision** |
| `sensitivity_metrics_v1`| `data/processed/sensitivity_metrics.json` | JSON | Agent 06 | Agent 07, Agent 08 | **Canonical Robustness** |
| `policy_brief_v1` | `runs/<run_id>/reports/policy_brief.md` | Markdown | Agent 07 | Human Stakeholders | **Presentation Only (Sink)** |
| `artifact_manifest_v1` | `runs/<run_id>/manifest.json` | JSON | Agent 10 | All Agents | **Authoritative Manifest** |
| `run_card_v1` | `runs/<run_id>/RUN_CARD.md` | Markdown | Agent 10 | All Agents | **Authoritative Run Provenance** |

---

## 2. Detailed Contract Definitions

### 2.1. `survey_raw_v1` (Immutable Source)
- **Path**: `data/raw/survey_raw.csv`
- **Fields**:
  - `participant_id` (string, required, unique): Pseudonymous participant identifier.
  - `submission_time` (string, ISO 8601): Submission timestamp.
  - `q1_open_feedback` (string, optional): Qualitative response regarding system preferences.
  - `q2_ranking_choices` (string, optional): Delimited ranking string or score.
  - `group_cohort` (string, required): Cohort identifier.
- **Invariants**:
  - Write-once. Overwriting an existing raw survey file is strictly prohibited.

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
    "schema_version": "v1.0.0",
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
    "schema_version": "v1.0.0",
    "candidates": [
      {
        "candidate_id": "string (CAND-01)",
        "title": "string",
        "description": "string",
        "grounding_theme_ids": ["string (references themes_codebook_v1.theme_id)"]
      }
    ]
  }
  ```

---

### 2.5. `preference_matrix_v1` (Canonical Utility Input)
- **Path**: `data/processed/preference_matrix.parquet` (or `.json`)
- **Schema**:
  ```json
  {
    "participant_id": "string",
    "candidate_a": "string",
    "candidate_b": "string",
    "preference_score": "float (-1.0 to 1.0, where >0 favors A, <0 favors B)",
    "confidence": "float (0.0 to 1.0)",
    "derivation_method": "string (direct_ranking | pairwise_prompt | imputed)"
  }
  ```
- **Invariants**:
  - Anti-symmetry: `preference_score(A, B) == -preference_score(B, A)`.
  - Self-comparison: `preference_score(A, A) == 0.0`.

---

### 2.6. `voting_results_v1` (Canonical Decision Artifact)
- **Path**: `data/processed/voting_results.json`
- **Schema**:
  ```json
  {
    "schema_version": "v1.0.0",
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

### 2.7. `sensitivity_metrics_v1` (Canonical Robustness Artifact)
- **Path**: `data/processed/sensitivity_metrics.json`
- **Schema**:
  ```json
  {
    "schema_version": "v1.0.0",
    "bootstrap_iterations": "integer",
    "margin_of_victory": "float",
    "winner_stability_percentage": "float",
    "perturbation_tolerance": "float",
    "is_robust": "boolean"
  }
  ```

---

### 2.8. `policy_brief_v1` (Presentation Only Artifact)
- **Path**: `runs/<run_id>/reports/policy_brief.md`
- **Authority**: Presentation only.
- **Rule**: Strictly forbidden from being listed as an `upstream_artifacts` dependency by any analytical module.

---

### 2.9. `artifact_manifest_v1` (Authoritative Registry Manifest)
- **Path**: `runs/<run_id>/manifest.json`
- **Schema**:
  ```json
  {
    "manifest_version": "v1.0.0",
    "run_id": "string",
    "generated_at": "string (ISO 8601)",
    "artifacts": {
      "<artifact_id>": {
        "artifact_id": "string",
        "run_id": "string",
        "path": "string",
        "format": "string",
        "producing_module": "string",
        "producing_agent": "string",
        "creation_timestamp": "string",
        "code_commit": "string",
        "source_hashes": {"<filepath>": "<sha256>"},
        "prompt_hash": "string | null",
        "model_revision": "string | null",
        "schema_version": "string",
        "validation_status": "valid | invalid | pending",
        "upstream_artifacts": ["string"],
        "downstream_consumers": ["string"],
        "stale_state": "fresh | stale | unverified"
      }
    }
  }
  ```

---

### 2.10. `run_card_v1` (Authoritative Run Card)
- **Path**: `runs/<run_id>/RUN_CARD.md`
- **Specification**: Contains Run ID, input files and SHA-256 hashes, Git commit, prompt versions, LLM models and revisions, quantisations, hardware, completed stages, retries, failures, skipped modules, runtimes, and registered artifact list.
