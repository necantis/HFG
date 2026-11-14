# Data Contracts & Interface Specifications — HFG

> **Status**: Approved (`v1.1.0` — 12-Agent Architecture, aligned with `ADR-0005`, `ADR-0006`, `ADR-0008`, and `ADR-0009`)  
> **Schema Version (`SCHEMA_VERSION`)**: `"1.0.0"` / `"v1.1.0"`  
> **Enforced by**: `src/artifact_registry.py`, `src/contracts.py`, `src/review/`, `src/pipeline/`  
> **Canonical Python Implementation**: [`src/contracts.py`](../src/contracts.py)  
> **Canonical JSON Schema Catalog**: [`schemas/interfaces.json`](../schemas/interfaces.json)

---

## 1. Cross-Contract Conventions

### 1.1. Schema Versioning
Every serialized record includes `schema_version` (`"1.0.0"` for typed Python interface records in `src/contracts.py`; `"v1.1.0"` / `"v1.0.0"` for registered canonical artifacts in `src/artifact_registry.py`). Deserializers reject mismatched major versions and trigger upstream regeneration when contracts evolve.

### 1.2. Provenance Block (`ProvenanceMeta`)
Every record interface embeds standardized provenance fields:
- `record_id: str` — Deterministic UUIDv5 or SHA-256 prefix derived from primary key fields.
- `run_id: str` — Identifier of the active run (`run_20261111_002`).
- `dataset_fingerprint: str` — SHA-256 digest of the immutable raw input survey file (`data/raw/survey_raw.csv`).
- `created_at_utc: str` — ISO-8601 UTC timestamp.
- `producer_module: str` — Canonical module path.
- `producer_agent: str` — Responsible agent identifier (`agent_00`–`agent_11`).
- `upstream_artifact_ids: list[str]` — Content-addressed IDs of all parent artifacts/records.
- `config_hash: str` — SHA-256 digest of the active stage configuration and prompt templates.

### 1.3. Missingness Representation (`MissingnessState`)
Missing survey responses and unexpressed stances are **never** represented by `0.0` or empty imputed scores. Canonical `PreferenceCell` missingness (`ADR-0005`) and fine-grained ingestion/coding diagnostics map via `MissingnessState`:
- `observed_usable` (`OBSERVED_USABLE`): Participant provided a substantive response; `alternative_probabilities` sums to $1.0 \pm 10^{-4}$.
- `unobserved_missing` (`UNOBSERVED_MISSING`): General unobserved / missing entry.
- `infeasible_choice` (`INFEASIBLE_CHOICE`): Choice outside the feasible alternative set.
- `ambiguous` (`AMBIGUOUS`): Insufficient clarity to assign a reliable probability distribution.
- Fine-grained sub-states (mapping canonically to `unobserved_missing` in downstream utility matrices):
  - `missing_raw_blank` (`MISSING_RAW_BLANK`): Cell is empty/`NaN` in `data/raw/survey_raw.csv`.
  - `missing_non_substantive` (`MISSING_NON_SUBSTANTIVE`): Participant wrote `"N/A"`, `"none"`, `"?"`, `"je ne sais pas"`, `"keine Angabe"`, etc.
  - `not_mentioned_in_response` (`NOT_MENTIONED_IN_RESPONSE`): Participant answered the question (`observed_usable` at question level) but did not address this dynamically extracted subtopic (`alternative_probabilities = {}`).
  - `not_applicable_frame` (`NOT_APPLICABLE_FRAME`): Classification (such as economic good type) is disabled for this question's `AnalyticalFrameType`.
  - `skipped_missing_input_file` (`SKIPPED_MISSING_INPUT_FILE`): Optional voting module (Baldwin/RRV) skipped because no validated active ballot file exists.

### 1.3.1. Canonical Epistemic Status Taxonomy (`ResponseEpistemicStatus`)
Reconciled across Agent 01 (`src/ingest/`) and Agent 02 (`src/nlp/`) via `src.contracts.ResponseEpistemicStatus`:
- **Usable Institutional Preferences (`has_usable_preference = True`, `missingness_state = "observed_usable"`)**:
  - `substantive`: Participant supplied actionable stance/position (`"Oui"`, `"Non"`, `"Idem"`, or rich prose).
  - `mixed_uncertainty_and_preference`: Response mixes explicit epistemic uncertainty with an actionable preference or critique; preference subtopics and uncertainty spans are both preserved.
- **Reportable Observed Statements Without Preference (`text_supplied = True`, `has_usable_preference = False`, `missingness_state = "missing_non_substantive"` or `"ambiguous"`)**:
  - `explicit_no_opinion`: Reportable observed statement (`EvidenceSpan` retained, zero fabricated preference).
  - `explicit_insufficient_experience`: Reportable observed statement (`EvidenceSpan` retained, zero fabricated preference).
  - `explicit_insufficient_information`: Reportable observed statement (`EvidenceSpan` retained, zero fabricated preference).
  - `ambiguous`: Unclear short statement or context-sensitive `"RAS"` in `Q01`–`Q13`; passed to Agent 02 qualitative coders for semantic interpretation while defaulting to zero preference if unresolved.
- **Blank / Non-Reportable Missingness (`has_usable_preference = False`, zero `EvidenceSpan` records)**:
  - `raw_blank`: Empty / whitespace-only cell (`text_supplied = False`, `missingness_state = "missing_raw_blank"`).
  - `punctuation_uninterpretable`: Punctuation-only marker (e.g., `"?"`, `"-"`; `missingness_state = "missing_non_substantive"`).
  - `no_additional_remarks`: Context-sensitive `"RAS"` or placeholder in optional `Q14` (`missingness_state = "missing_non_substantive"`).

### 1.4. Uncertainty Representation (`UncertaintyEnvelope`)
Empirical, coded, and aggregated quantities explicitly carry `UncertaintyEnvelope`:
- `point_estimate: float | None`
- `ci_lower_95: float | None` — 2.5th percentile bound.
- `ci_upper_95: float | None` — 97.5th percentile bound.
- `std_error: float | None` — Standard deviation across coders or bootstrap/Monte Carlo draws.
- `coder_confidence: float | None` $\in [0.0, 1.0]$ — Epistemic certainty of the LLM coder(s).
- `coder_agreement: float | None` $\in [0.0, 1.0]$ — Inter-coder concordance between `coder_a` and `coder_b`.
- `distribution_type: Literal["DETERMINISTIC", "DUAL_CODER_INTERVAL", "MONTE_CARLO_EMPIRICAL", "BOOTSTRAP"]`

---

## 2. Canonical Artifact Contracts Overview

| Contract ID | Canonical File Path | Format | Producing Agent | Consumer Agents | Authority Level |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `survey_raw_v1` | `data/raw/survey_raw.csv` | CSV | External Source | Agent 01 | **Immutable External Source** |
| `answers_normalized_v1` | `data/normalized/answers_normalized.parquet` | Parquet / JSON | Agent 01 | Agent 02, Agent 04 | **Canonical Ingestion** |
| `themes_codebook_v1` | `data/processed/themes_codebook.json` | JSON | Agent 02 | Agent 03, Agent 08 | **Canonical Qualitative** |
| `candidate_options_v1` | `data/processed/candidate_options.json` | JSON | Agent 03 | Agent 04, Agent 05, Agent 06 | **Canonical Option Set** |
| `preference_matrix_v1` | `data/processed/preference_matrix.parquet` | Parquet / JSON | Agent 04 | Agent 05, Agent 06 | **Canonical Utility Input** |
| `preference_profiles_v1` | `data/processed/preference_profiles.json` | JSON | Agent 05 | Agent 08, Agent 09 | **Interpretive Artifact (Non-Pruning)** |
| `voting_results_v1` | `data/processed/voting_results.json` | JSON | Agent 06 | Agent 08, Agent 09 | **Canonical Decision** |
| `gpu_runtime_config_v1` | `runs/<run_id>/gpu_runtime_config.json` | JSON | Agent 07 | Agent 02, Agent 03, Agent 04, Agent 05, Agent 11 | **Configurable Runtime Config** |
| `pareto_mc_config_v1` | `runs/<run_id>/pareto_mc_config.json` | JSON | Agent 04 | Agent 04, Agent 09 | **Configurable Runtime Config** |
| `counterfactual_regime_config_v1` | `runs/<run_id>/counterfactual_regime_config.json` | JSON | Agent 11 | Agent 04, Agent 08, Agent 09 | **Configurable Regime Sensitivity Config (`ADR-0009`)** |
| `policy_brief_v1` | `runs/<run_id>/reports/policy_brief.md` | Markdown | Agent 08 | Stakeholders | **Presentation Only (Sink)** |
| `integration_review_v1` | `runs/<run_id>/integration_review_report.json` | JSON | Agent 09 | Agent 10, Agent 11 | **Authoritative Audit Artifact** |
| `artifact_manifest_v1` | `runs/<run_id>/manifest.json` | JSON | Agent 10 | All Agents | **Authoritative Manifest** |
| `run_card_v1` | `runs/<run_id>/RUN_CARD.md` | Markdown | Agent 10 | All Agents | **Authoritative Run Provenance** |
| `pipeline_qa_log_v1` | `runs/<run_id>/pipeline_execution.log` | Log / JSON | Agent 11 | Agent 09, Agent 10 | **Execution Trace & QA** |

---

## 3. Canonical File-Level Artifact Schemas

### 3.1. `survey_raw_v1` (Immutable External Source)
- **Path**: `data/raw/survey_raw.csv` (external source: `Anonymized_survey_data_2026.csv`)
- **Authority**: `immutable_source`
- **Cryptographic Hash (SHA-256)**: `56acded3e02be49be27d6b288fa2c43fcce68df24525113eba1b1161eec52a95`
- **Dimensions**: 11 data rows, 27 columns (total 12 lines including header).
- **Primary Fields**:
  - `Obs_No`: Observation / participant index.
  - Substantive Questions (`Q01`–`Q13`) + Open Remarks (`Q14`):
    - `1. Pertinence_de_ces_poles`
    - `2. Pertinence_des_personnes_identifiees`
    - `3. Denomination_de_ces_poles`
    - `4. Faut-il_un_fonctionnement_unifie_entre_l`
    - `5. Quelle_coordination_de_pole_choisir_Scen`
    - `6. Tres_concretement_avez-vous_des_inputs_c`
    - `7. Les_engagements_doivent-ils_etre_faits_e`
    - `8. A_quel_niveau_la_gestion_RH_notamment_le`
    - `9. Le_pole_dans_son_ensemble_est_responsabl`
    - `10. Comment_le_socle_doit-il_etre_gere_Scena`
    - `11. Comment_les_overheads_doivent-ils_etre_g`
    - `12. Comment_les_primes_de_depot_doivent_etre`
    - `13. Comment_gerer_les_evaluations_individuel`
    - `14. Avez-vous_des_remarques__suggestions`
  - Metadata Columns (15–25, 38): Timestamps, completion progression, submission origin, `LANG_SAISIE`, device, and identifier hashes.
- **Invariants**: Write-once external input; locked via SHA-256 digest in `runs/run_20261111_002/manifest.json`.

### 3.2. `answers_normalized_v1` (Canonical Ingestion Artifact)
- **Path**: `data/normalized/answers_normalized.parquet` (or `.json`; gitignored sensitive normalized respondent text)
- **Fields**: `response_id`, `participant_id`, `question_id`, `is_primary_question`, `question_scope`, `response_type` (`categorical | numeric | open_text | ranking`), `detected_language` (`fr | de | en`), `raw_value`, `source_text`, `normalized_value`, `normalized_text`, `offset_reference_text` (`"source_text"`), `text_supplied`, `response_presence` (`blank | provided`), `epistemic_status` (`ResponseEpistemicStatus`), `has_usable_preference`, `missingness_state` (`MissingnessState`), `is_valid`, `validation_flags`, `raw_response_sha256`, `char_length`.
- **Invariants**: All records map to an immutable source `participant_id`; `char_start`/`char_end` offsets always reference `source_text`; observed statements without actionable preference (`explicit_no_opinion`, `explicit_insufficient_experience`, `ambiguous`) preserve `text_supplied: true` and `has_usable_preference: false` without imputation.

### 3.3. `themes_codebook_v1` (Canonical Qualitative Themes)
- **Path**: `data/processed/themes_codebook.json`
- **Fields**: `schema_version`, `run_id`, `themes[]` (`theme_id`, `question_id`, `name`, `description`, `keywords`, `evidence_response_ids`, `support_count`), plus `canonical_subtopics[]` (`CanonicalSubtopic`) and `value_assignments[]` (`ValueAssignment`).
- **Invariants**: Every `evidence_response_ids` / `supporting_span_ids` item MUST resolve to a valid `response_id` in `answers_normalized_v1`.

### 3.4. `candidate_options_v1` (Canonical Option Set)
- **Path**: `data/processed/candidate_options.json`
- **Fields**: `schema_version`, `candidates[]` (`candidate_id`, `question_id`, `title`, `description`, `grounding_theme_ids`, `feasibility_constraints`), aligned with `FeasibleAlternative` and `GovernanceSolution`.
- **Invariants**:
  - Feasible-option pruning depends **only** on explicit logical, institutional, or dependency constraints.
  - Clusters, centroids, and empirical preference profiles must **NOT** be used to prune feasible candidates before Pareto analysis.

### 3.5. `preference_matrix_v1` & `PreferenceCell` (Canonical Utility Input, `ADR-0005` & `ADR-0008`)
- **Path**: `data/processed/preference_matrix.parquet` (or `.json`)
- **Primary Representation (`ADR-0005` + `ADR-0008`)**: Participant preference is represented **primarily** as a probability distribution (for exact consensus) OR an explicit formal **`PreferenceUncertaintySet`** over feasible institutional alternatives when coders diverge, vocabularies are unaligned/partial, `probability_interpretation` differs, or only a single coder observed the facet. Uncalibrated scalar representations (`participant_preference ∈ [-1, +1]`), `"CONFIDENCE_WEIGHTED_DISTRIBUTION"` averaging, unweighted default midpoint collapse, majority voting, highest-confidence-wins, and Coder-A/Coder-B precedence are **strictly forbidden**.
- **Seven-Level Reconciliation & `ISSUE-005` Resolution (`ADR-0008`)**:
  - `ProbabilityInterpretation` distinguishes `epistemic_uncertainty_over_preference`, `explicit_mixed_preference`, and `conditional_or_context_dependent`.
  - Numerically equal distributions (`TVD <= 1e-4`) with differing `probability_interpretation` MUST remain `AGREEMENT_DISTRIBUTION_ONLY_INTERPRETATION_FLAGGED` (never promoted to `AGREEMENT_EXACT`), retain `resolved_point_distribution = None`, and preserve both variants in `preference_uncertainty_set.interpretation_variants`.
  - Agent 04 evaluates interpretation-aware utility operators (`Categorical` realized draws vs. linear portfolio alignment vs. regime-contingent worst/best-case brackets) rather than collapsing interpretations into homogeneous cardinal utilities.
- **Illustrative Schema Example**:
  ```json
  {
    "participant_id": "PARTICIPANT_001",
    "cell_id": "CELL_001",
    "question_or_dimension_id": "Q08_ST01",
    "alternative_probabilities": {
      "professor": 0.10,
      "laboratory": 0.65,
      "pole": 0.20,
      "institute": 0.05
    },
    "resolved_point_distribution": {
      "professor": 0.10,
      "laboratory": 0.65,
      "pole": 0.20,
      "institute": 0.05
    },
    "uncertainty_class": "NONE_CONSENSUS",
    "reconciliation_status": "AGREEMENT_EXACT",
    "probability_interpretation": "epistemic_uncertainty_over_preference",
    "semantic_importance": 0.85,
    "coder_confidence": 0.95,
    "coder_agreement": 0.90,
    "missingness_state": "observed_usable",
    "evidence_ids": ["RESP_001", "RESP_004"],
    "derived_scalar_score": null
  }
  ```
- **Invariants**:
  1. **Probability Simplex Normalization**: Every observed distribution (`coder_a_distribution`, `coder_b_distribution`, every entry in `preference_uncertainty_set.discrete_scenarios`, every entry in `disjoint_coder_hypotheses`, and any non-`None` `resolved_point_distribution`) MUST sum to $1.0 \pm 10^{-4}$.
  2. **No Point Collapse When Unresolved**: `resolved_point_distribution` MUST be `None` (and `alternative_probabilities == {}`) whenever `uncertainty_class != "NONE_CONSENSUS"`, `PARTIAL_CROSSWALK` / `NO_VALID_CROSSWALK`, `INTERPRETATION_DIVERGENCE`, or single-coder partial identification applies.
  3. **Separately Kept Metadata**: `semantic_importance`, `coder_confidence`, `coder_agreement`, `missingness_state`, `probability_interpretation`, and `evidence_ids`/`evidence_span_ids` remain strictly distinct; `coder_confidence` is **never** used as an aggregation or utility weight.
  4. **Single-Coder Non-Zero-Fill**: For `SINGLE_CODER_PARTICIPANT_OMISSION` and `SINGLE_CODER_SUBTOPIC_GRANULARITY`, the silent coder MUST stay `None` (`EPISTEMICALLY_UNOBSERVED`), never `{k: 0.0}`.
  5. **Scalar Restriction**: `derived_scalar_score` may exist **only** as an optional derived representation when alternatives have an analytically defensible ordering.

### 3.6. `preference_profiles_v1` (Interpretive Empirical Profiles)
- **Path**: `data/processed/preference_profiles.json`
- **Fields**: `schema_version`, `run_id`, `profiles[]` (`profile_id`, `name`, `centroid_distribution`, `value_coherence_score`, `member_participant_ids`), corresponding to `ClusterResult`.
- **Invariants**: Empirical patterns only (never normative institutional archetypes); strictly prohibited from excluding feasible solutions prior to Pareto analysis.

### 3.7. `voting_results_v1` (Canonical Decision Artifact)
- **Path**: `data/processed/voting_results.json`
- **Fields**: `schema_version`, `run_id`, `social_choice_rules` (`borda_count`, `condorcet`, `minimax`), `baldwin_result` (`BaldwinResult`), `rrv_result` (`RRVResult`), `consensus_winner`, `is_unanimous`.

### 3.8. Configurable Runtime & Sink Contracts
- **`gpu_runtime_config_v1`** (`runs/<run_id>/gpu_runtime_config.json`, owned by **Agent 07**): `gpu_memory_fraction` (e.g., `0.85` total or `0.44` per concurrent coder server), `allow_growth`, `device_ids`, `coder_a_port`, `coder_b_port`.
- **`pareto_mc_config_v1`** (`runs/<run_id>/pareto_mc_config.json`, owned by **Agent 04**): `robust_pareto_mc_samples` (default `1000`–`2000`, dynamically tuned), `bootstrap_seed` (`42`), `confidence_interval` (`0.95`).
- **`policy_brief_v1`** (`runs/<run_id>/reports/policy_brief.md`, owned by **Agent 08**): Presentation-only sink; strictly forbidden as an upstream input.
- **`integration_review_v1`** (`runs/<run_id>/integration_review_report.json`, owned by **Agent 09**): `audit_timestamp`, `overall_status` (`PASS | FAIL | ADVISORY`), `invariant_verifications`, `red_team_findings`.
- **`artifact_manifest_v1` & `run_card_v1`** (`runs/<run_id>/manifest.json`, `runs/<run_id>/RUN_CARD.md`, owned by **Agent 10**).

---

## 4. Detailed Python Interface Specifications (20 Core Contracts + `ADR-0008` Sub-Contracts)

All 20 core contracts plus supporting `ADR-0008` sub-contracts (`CanonicalAlternativeCrosswalk`, `PreferenceUncertaintySet`) are implemented in [`src/contracts.py`](../src/contracts.py) and exported in [`schemas/interfaces.json`](../schemas/interfaces.json). Every top-level contract includes `schema_version: str = "1.0.0"` and `provenance: ProvenanceMeta`.

### 4.1. `RunManifest`
- **Required Fields:** `run_id`, `survey_group_id`, `dataset_path`, `dataset_fingerprint`, `expected_question_count` (`13`), `detected_participant_count`, `supported_languages`, `gpu_device_name`, `coder_a_model_spec`, `coder_b_model_spec`, `hardcoding_scan_passed`, `provenance`.
- **Optional / Runtime Fields:** `gpu_runtime_config_path`, `pareto_mc_config_path`, `monte_carlo_draws`, `random_seed`, `confidence_level`, `baldwin_input_state`, `rrv_input_state`, `baldwin_input_path`, `baldwin_input_fingerprint`, `rrv_input_path`, `rrv_input_fingerprint`, `git_commit_sha`, `notes`.
- **Missingness & Uncertainty:** `baldwin_input_state` / `rrv_input_state` default to `SKIPPED_MISSING_INPUT_FILE` when absent; global `random_seed` and `confidence_level` track stochastic reproducibility.

### 4.2. `QuestionSpec`
- **Required Fields:** `question_id` (`Q01`–`Q13`, optional `Q14`), `question_index`, `column_headers_by_lang`, `canonical_prompt_en`, `analytical_frame` (`AnalyticalFrameType`), `economic_good_classification_policy` (`ENABLED | CONDITIONAL | DISABLED`), `alternative_classification_scheme`, `observed_response_count`, `missing_response_count`, `missing_participant_ids`, `provenance`.
- **Optional Fields:** `frame_assignment_source`, `prompt_fr`, `prompt_de`, `domain_tags`, `compatibility_rule_id`, `is_primary_question`, `question_scope` (`primary | optional_contextual_remarks`).
- **Missingness & Uncertainty:** Explicitly partitions observed vs. `missing_participant_ids`; `frame_assignment_source` marks deterministic config vs. header validation.

### 4.3. `EvidenceSpan`
- **Required Fields:** `span_id`, `participant_id`, `question_id`, `detected_language` (`fr | de | en`), `raw_response_sha256`, `char_start`, `char_end`, `verbatim_quote`, `missingness_state`, `language_detection_confidence`, `span_boundary_confidence`, `provenance`.
- **Optional Fields:** `english_working_gloss`, `sentence_index`, `offset_reference_text` (`"source_text"`), `span_role` (`substantive_evidence | explicit_uncertainty_or_no_opinion | value_evidence`).
- **Missingness & Uncertainty:** Blank/non-reportable missing cells emit zero `EvidenceSpan` objects; reportable non-preference (`explicit_no_opinion`, `explicit_insufficient_experience`, `explicit_insufficient_information`) and `ambiguous` statements preserve verbatim `EvidenceSpan` records with `span_role = "explicit_uncertainty_or_no_opinion"`; `language_detection_confidence` and `span_boundary_confidence` quantify extraction reliability.

### 4.4. `SubtopicCandidate`
- **Required Fields:** `candidate_id`, `question_id`, `participant_id`, `coder_id` (`coder_a | coder_b`), `evidence_span_ids`, `proposed_label_en`, `proposed_description`, `candidate_alternative_distribution`, `semantic_importance`, `coder_confidence`, `missingness_state`, `provenance`.
- **Optional Fields:** `proposed_economic_good_class`, `proposed_alternative_frame_label`, `native_language_keywords`, `derived_scalar_stance`.
- **Missingness & Uncertainty:** Economic good class is `None` (`NOT_APPLICABLE_FRAME`) when question policy is `DISABLED`; `coder_confidence` $\in [0, 1]$.

### 4.5. `CanonicalSubtopic`
- **Required Fields:** `subtopic_id`, `question_id`, `canonical_label_en`, `canonical_description`, `source_candidate_ids`, `supporting_span_ids`, `mention_participant_count`, `unmentioned_participant_count`, `missing_question_participant_count`, `economic_good_applicability`, `coder_agreement`, `mean_coder_confidence`, `provenance`.
- **Optional Fields:** `labels_by_lang`, `dominant_economic_good_class`, `economic_good_distribution`, `question_specific_category`, `linked_value_ids`, `feasible_alternatives`, `has_defensible_ordering`.
- **Missingness & Uncertainty:** Partitions $N = \text{mention} + \text{unmentioned} + \text{missing\_question}$; carries `coder_agreement` and `mean_coder_confidence`.

### 4.6. `ValueAssignment`
- **Required Fields:** `value_assignment_id`, `value_id`, `value_label_en`, `value_definition`, `participant_id`, `question_id`, `subtopic_id`, `evidence_span_ids`, `missingness_state`, `polarity` (`float | None`), `semantic_importance`, `coder_confidence`, `coder_agreement`, `polarity_uncertainty_interval` (`tuple[float, float] | None`), `provenance`.
- **Optional Fields:** `coder_a_raw_label`, `coder_b_raw_label`, `cross_question_bridge_ids`.
- **Polarity Invariant:** Values that express ethical/organisational priorities without an inherent bipolar pro/con direction MUST retain `polarity = None` and `polarity_uncertainty_interval = None` rather than inventing `0.0`.

### 4.7. `CodingResult`
- **Required Fields:** `coding_id`, `participant_id`, `question_id`, `subtopic_id`, `coder_source` (`coder_a | coder_b | reconciled`), `missingness_state`, `alternative_probabilities`, `semantic_importance`, `coder_confidence`, `coder_agreement`, `evidence_span_ids`, `provenance`.
- **Optional Fields:** `probability_ci_lower`, `probability_ci_upper`, `probability_interpretation`, `derived_scalar_score` (ordered dimensions only), `economic_good_class`, `perception_category`, `value_assignment_ids`, `reconciliation_method` (`EXACT_MATCH | ARBITRATED_SPAN_CHECK | HIGH_UNCERTAINTY_FLAGGED | UNCERTAINTY_SET_PRESERVED | NO_VALID_CROSSWALK_UNMERGED | SINGLE_CODER_PARTIAL_ID` — legacy `"CONFIDENCE_WEIGHTED_DISTRIBUTION"` removed and forbidden by `ADR-0008`), `rationale_summary`.
- **Invariants (`validate_invariants()`):** Non-usable states require empty `alternative_probabilities = {}` and `derived_scalar_score = None`; usable states require $\ge 1$ `EvidenceSpan` and $\sum_k p_k = 1.0 \pm 10^{-4}$; forbidden averaging tokens raise `ValueError`.

### 4.8. `PreferenceCell`, `CanonicalAlternativeCrosswalk`, & `PreferenceUncertaintySet` (`ADR-0008`)
- **Required Identity & Raw Coder Fields:** `cell_id`, `participant_id`, `question_id` (`question_or_dimension_id`), `subtopic_id` (`canonical_subtopic_id`), `missingness_state`, `coder_a_distribution` (`coder_a_probabilities`), `coder_b_distribution` (`coder_b_probabilities`), `canonical_alternative_crosswalk` (`CanonicalAlternativeCrosswalk`), `coder_a_probability_interpretation`, `coder_b_probability_interpretation`, `semantic_importance_a` (`coder_a_importance`), `semantic_importance_b` (`coder_b_importance`), `coder_confidence_a`, `coder_confidence_b`, `agreement_status` (`AgreementStatus`), `uncertainty_class` (`UncertaintyClass`), `preference_uncertainty_set` (`PreferenceUncertaintySet`), `source_evidence_ids` (`evidence_span_ids` / `evidence_ids`), `reconciliation_status` (`ReconciliationStatus`), `provenance`.
- **Optional Point Consensus & Aliases:** `resolved_point_distribution` (`dict[str, float] | None`, non-`None` **only** when `uncertainty_class == NONE_CONSENSUS` / `reconciliation_status == AGREEMENT_EXACT`), `alternative_probabilities` (empty `{}` when unresolved; mirrors `resolved_point_distribution` for consensus or legacy fixtures), `semantic_importance`, `coder_confidence`, `coder_agreement`, `source_coding_id`, `probability_lower_bounds`, `probability_upper_bounds`, `probability_std_errors`, `probability_interpretation`, `derived_scalar_score`, `economic_good_class`.
- **`CanonicalAlternativeCrosswalk` (Level 2):** Scoped strictly to `(question_id, canonical_subtopic_id)` with `crosswalk_status` (`EXACT_KEY_MATCH | SEMANTIC_KEY_MATCH | SCENARIO_PREFIX_MATCH | PARTIAL_CROSSWALK | NO_VALID_CROSSWALK | SINGLE_CODER_ONLY`), `comparable`, `coder_a_to_canonical`, `coder_b_to_canonical`, `canonical_keys`, `unmapped_keys_a`, `unmapped_keys_b`, `unmapped_mass_a`, `unmapped_mass_b`, `crosswalk_rule_id`, `provenance_rationale`, `lossless_deterministic_aggregation`.
- **`PreferenceUncertaintySet` (Levels 5–6):** `representation_type` (`EMPTY_MISSING | SINGLETON | DISCRETE_CODER_SET | PARTIAL_CROSSWALK_SET | DISJOINT_CODER_HYPOTHESES | SINGLE_CODER_PARTIAL_ID`), `discrete_scenarios`, `disjoint_coder_hypotheses`, `lower_bounds`, `upper_bounds`, `interpretation_variants`, `single_coder_active_side`, `single_coder_uncertainty_type` (`SINGLE_CODER_PARTICIPANT_OMISSION | SINGLE_CODER_SUBTOPIC_GRANULARITY`), `non_coding_coder_state` (`"EPISTEMICALLY_UNOBSERVED"`), `allows_derived_convex_hull`, `derived_scenarios` (every item tagged `DERIVED_ROBUSTNESS_SCENARIO | DERIVED_ROBUSTNESS_CONVEX_BARYCENTER | DERIVED_BOUNDS_SAMPLE`), `scenario_origin`, `double_count_guard_applied`.
- **Invariants (`validate_simplex()`):** Enforces non-usable emptiness, `NO_VALID_CROSSWALK` non-merge (`DISJOINT_CODER_HYPOTHESES`), simplex sums on all coder distributions / scenarios / non-null point vectors, single-coder `None` silent coder enforcement, `ISSUE-005` dual-interpretation retention, and strict `resolved_point_distribution = None` whenever unresolved. Single canonical implementation shared across `src/contracts.py` and `src/artifact_registry.py`.

### 4.9. `PreferenceMatrix`
- **Required Fields:** `matrix_id`, `participant_ids`, `question_ids`, `subtopic_ids`, `subtopic_to_question`, `cells`, `observed_usable_cell_count`, `unobserved_missing_cell_count`, `infeasible_choice_cell_count`, `ambiguous_cell_count`, `overall_coder_agreement_mean`, `overall_coder_confidence_mean`, `validation_passed`, `provenance`.
- **Optional Fields:** `question_coverage_rates`, `participant_response_rates`, `flagged_low_agreement_cell_ids`, `uncertainty_class_counts`.

### 4.10. `FeasibleAlternative`
- **Required Fields:** `alternative_id`, `question_id`, `label_en`, `description_en`, `subtopic_alternative_allocations`, `active_subtopic_mask`, `supporting_participant_count`, `missing_participant_count`, `feasibility_status` (`FEASIBLE | PRUNED_INCOMPATIBLE | PRUNED_DEPENDENCY_MISSING`), `empirical_support_uncertainty`, `provenance`.
- **Optional & Invariant Fields:** `economic_good_profile`, `explanatory_value_ids`, `constraint_checks_passed`, `is_minority_position`, `pruned_by_clusters_or_values` (`False`), `pruning_sources_applied` (rejects `PROHIBITED_PRUNING_SOURCES`).

### 4.11. `GovernanceSolution`
- **Required Fields:** `solution_id`, `label_en`, `question_alternatives`, `global_alternative_profile`, `included_question_ids`, `diagnostic_context_question_ids`, `logical_constraints_satisfied`, `institutional_constraints_satisfied`, `dependencies_satisfied`, `feasibility_evaluation_status`, `generation_method` (`COMBINATORIAL_CONSTRAINT_SATISFACTION | DISCRETE_POLICY_GRID | STRUCTURAL_DIRECTED_SEARCH`), `provenance`.
- **Optional / Explanatory & Non-Pruning Fields:** `explanatory_organisational_values` (strictly non-filtering), `summary_by_lang`, `economic_good_summary`, `pruned_by_clusters_or_values` (`False`), `pruned_by_coder_disagreement` (`False`), `pruned_by_coder_confidence` (`False`), `pruning_sources_applied`.
- **Constraint-Only Pruning Rule:** Solutions are pruned **strictly and exclusively** by logical constraints, institutional constraints, and structural dependencies—never by clusters, value coherence, coder disagreement, or confidence.

### 4.12. `ParticipantUtility`
Derived **exclusively** from the validated `PreferenceMatrix` uncertainty sets (`PreferenceUncertaintySet` scenarios / interpretations and `semantic_importance` $w_{i,m}$) over observed usable cells $\mathcal{M}_i^{\text{usable}}$:

$$U_i(s \mid \omega) = \frac{\sum_{m \in \mathcal{M}_i^{\text{usable}}} \tilde{w}_{i,m}^{(\omega)} \cdot \phi_{\text{interp}}\!\left(p_{i,m}^{(\omega)}, \alpha_m(s)\right)}{\sum_{m \in \mathcal{M}_i^{\text{usable}}} \tilde{w}_{i,m}^{(\omega)}}$$

- **Required Fields:** `utility_id`, `participant_id`, `solution_id`, `preference_matrix_id`, `missingness_state`, `observed_subtopic_count`, `total_subtopic_count`, `point_utility`, `utility_ci_lower_95`, `utility_ci_upper_95`, `utility_std_error`, `mean_coder_confidence`, `mean_coder_agreement`, `provenance`.
- **Optional & ADR-0008 Fields:** `per_question_utilities`, `individual_regret`, `is_below_veto_threshold`, `interpretation_modes_evaluated`, `derived_scenario_origins`, `min_scenario_utility`, `max_scenario_utility`, `single_coder_uncertainty_bounded`, `uses_coder_confidence_as_weight` (must remain `False`), `double_count_guard_evaluated`.

### 4.13. `ParetoResult`
- **Required Fields:** `pareto_result_id`, `preference_matrix_id`, `evaluated_solution_ids`, `valid_participant_ids`, `excluded_all_missing_participant_ids`, `nondominated_solution_ids`, `dominated_solution_map`, `rawls_maximin_scores`, `utilitarian_scores`, `nash_welfare_scores`, `gini_inequality_scores`, `atkinson_inequality_scores`, `opposition_counts`, `opposition_shares`, `max_regret_scores`, `rankings_by_criterion`, `provenance`.
- **Optional Fields:** `pairwise_dominance_margins`, `profile_mean_utilities`.

### 4.14. `RobustParetoResult`
- **Required Fields:** `robust_pareto_id`, `base_pareto_result_id`, `monte_carlo_draws`, `random_seed`, `pareto_mc_config_path`, `frontier_inclusion_probabilities`, `robust_frontier_solution_ids`, `criterion_top1_probabilities`, `utility_metric_intervals`, `missing_participant_ids_preserved`, `provenance`.
- **Optional & ADR-0008 4-State Robustness Fields:** `veto_threshold_sensitivity`, `subtopic_weight_perturbation_sensitivity`, `solution_robustness_statuses` (`dict[str, RobustParetoStatus]`), `robustly_dominated_solution_ids`, `robustly_nondominated_solution_ids`, `conditionally_nondominated_solution_ids`, `unresolved_due_to_coding_uncertainty_ids`, `conditional_nondominated_regimes`, `derived_scenario_origins_used`, `robust_core_inclusion_threshold`, `pruned_by_clusters_values_or_disagreement` (`False`).
- **4-State Invariant (`validate_invariants()`):** Classifies evaluated feasible solutions into mutually exclusive buckets (`ROBUSTLY_DOMINATED`, `ROBUSTLY_NONDOMINATED`, `CONDITIONALLY_NONDOMINATED`, `UNRESOLVED_DUE_TO_CODING_UNCERTAINTY`) and rejects cluster/value/disagreement pruning.

### 4.15. `ClusterResult` (Interpretive Preference Profiles Only)
- **Required Fields:** `cluster_result_id`, `preference_matrix_id`, `distance_metric` (`MASKED_JENSEN_SHANNON | MASKED_COSINE | MASKED_WEIGHTED_L1`), `min_shared_subtopics_for_pair`, `candidate_k_evaluated`, `silhouette_scores_by_k`, `stability_scores_by_k`, `selected_k`, `profile_assignments`, `unassigned_missing_participant_ids`, `profile_sizes`, `profile_distinguishing_subtopics`, `profile_distinguishing_values`, `participant_assignment_confidence`, `provenance`.
- **Optional Fields:** `descriptive_labels_en`, `pairwise_distance_matrix_hash`.

### 4.16. `BaldwinResult`
- **Required Fields:** `baldwin_result_id`, `execution_status` (`EXECUTED | SKIPPED_NO_VALID_INPUT | FAILED_VALIDATION`), `missingness_state`, `input_file_path`, `input_file_sha256`, `candidate_ids`, `valid_ballot_count`, `missing_or_spoiled_ballot_count`, `elimination_rounds`, `winner_candidate_ids`, `provenance`.
- **Optional / Uncertainty Fields:** `tie_margin_min`, `bootstrap_winner_stability`, `tie_breaking_rule_used`, `borda_initial_ranking`.

### 4.17. `RRVResult`
- **Required Fields:** `rrv_result_id`, `execution_status` (`EXECUTED | SKIPPED_NO_VALID_INPUT | FAILED_VALIDATION`), `missingness_state`, `input_file_path`, `input_file_sha256`, `score_scale_min`, `score_scale_max`, `reweighting_constant_k`, `seats_to_fill`, `valid_ballot_count`, `missing_ballot_count`, `selection_rounds`, `selected_committee_ids`, `provenance`.
- **Optional / Uncertainty Fields:** `round_margin_min`, `bootstrap_committee_inclusion_freq`, `proportionality_satisfaction_metrics`.

### 4.18. `ReportClaim`
- **Required Fields:** `claim_id`, `section_id`, `question_ids`, `claim_type`, `statement_text_en`, `evidence_span_ids`, `canonical_subtopic_ids`, `artifact_references`, `numerical_values_cited`, `observed_count_disclosed`, `missing_count_disclosed`, `uncertainty_summary`, `verification_passed`, `provenance`.
- **Optional Fields:** `statement_translations`, `caveats_and_assumptions`.

### 4.19. `ArtifactRecord`
- **Required Fields:** `artifact_id`, `artifact_type`, `stage_id`, `file_path`, `content_sha256`, `byte_size`, `record_count`, `null_record_count`, `is_cacheable`, `invalidation_keys`, `validation_status`, `authority_level`, `provenance`.
- **Optional Fields:** `compression`, `execution_duration_seconds`.
*(Aligned with [`src/artifact_registry.py`](../src/artifact_registry.py) manifest entries via `artifact_id`, `run_id`, `path`, `producing_module`, `producing_agent`, `code_commit`, `source_hashes`, `prompt_hash`, `model_revision`, `stale_state`, and `authority_level`.)*

### 4.20. `AgentHandoff`
- **Required Fields:** `handoff_id`, `from_agent`, `to_agents`, `completed_stage_ids`, `modified_files`, `produced_artifact_ids`, `architectural_decisions`, `identified_risks`, `downstream_tasks`, `blocking_issues`, `open_verification_checks`, `ready_for_next_stage`, `provenance`.
- **Optional Fields:** `skipped_optional_modules`, `performance_metrics_sec`.
*(Serialized to markdown handoffs under `docs/AGENT_HANDOFFS/agent_XX_handoff.md` per [`docs/AGENT_HANDOFFS/template_handoff.md`](AGENT_HANDOFFS/template_handoff.md).)*

### 4.21. `ADR-0009` Resource-Good Regimes, Voluntary Club Provision & Counterfactual Sensitivity Contracts (`ADR0009_SUPPORTING_CONTRACT_TYPES`)
All seven `ADR-0009` sub-contracts live in [`src/contracts.py`](../src/contracts.py) and [`schemas/interfaces.json`](../schemas/interfaces.json) (`ADR0009_SUPPORTING_CONTRACT_TYPES`), governed by strict `FRONTIER_A` (`OBSERVED_DESIGN_FRONTIER`) vs `FRONTIER_B` (`RESOURCE_REGIME_EXPANDED_FRONTIER`) separation:

- **`ResourceEligibilityAssessment`**: Subtopic-level gate (`ResourceEligibilityStatus`: `ELIGIBLE | CONDITIONAL_RESOURCE_ONLY | INELIGIBLE | UNKNOWN`). Requires non-empty `resource_evidence_basis` for `ELIGIBLE` / `CONDITIONAL_RESOURCE_ONLY`; rejects `is_pure_opinion_or_perception = True` unless `INELIGIBLE`; forbids attaching `GoodRegimeType` when `INELIGIBLE` or `UNKNOWN`; requires `requires_segregated_sensitivity_tier = True` and `segregated_tier_id` (e.g. `Q-G`) for `CONDITIONAL_RESOURCE_ONLY`.
- **`ClubGoodMechanism`** *(alias `ClubGoodContract`)*: Enforces the 10-field operational contract for `CLUB_GOOD`: `voluntary_membership == True` (`membership_mode == "VOLUNTARY"`), exact `non_member_compulsory_contribution == 0.0`, strictly higher `member_access` than `non_member_access` (`NONE | RESIDUAL_CAPACITY | PAY_PER_USE | ALLOCATED_QUOTA | OTHER_EXPLICIT`), non-empty `member_contribution_rule`, `member_priority`, `capacity_or_congestion_rule`, `governance_rule`, `pricing_or_contribution_rule`, and explicit `exit_rule in {ALLOWED, CONSTRAINED}` (with `governing_constraint_id` if `CONSTRAINED`). Bare `"CLUB_GOOD"` labels fail validation.
- **`ResourceRegimeSpec`**: Parameterizes multiple institutional regimes (`PRIVATE_GOOD | CLUB_GOOD | COMMON_POOL_RESOURCE | PUBLIC_GOOD | HYBRID`) over five orthogonal dimensions (`RivalryLevel`, `ExcludabilityLevel`, `FinancingRuleType`, `AccessRuleType`, `ExitPolicyType`), preserving `UNKNOWN` without silent inference, rejecting `is_intrinsic_ontological_label = True`, and requiring a validated `ClubGoodMechanism` whenever `regime_type == CLUB_GOOD`.
- **`CounterfactualPreferenceMapping` & `PreferenceCell.provenance_category`**: Segregates `OBSERVED_RESPONDENT_PREFERENCE`, `INSTITUTIONALLY_DERIVED_MECHANISM`, and `COUNTERFACTUAL_PREFERENCE_ASSUMPTION`. `PreferenceCell` rejects any provenance other than `OBSERVED_RESPONDENT_PREFERENCE`, and `validate_provenance_boundary()` rejects rewriting refusal-to-pay (`is_refusal_to_pay_origin = True`) into an observed preference for `CLUB_GOOD`.
- **`CounterfactualUtilityBound`**: Supports `CounterfactualUtilityIdentification` (`point_identified | partially_identified | scenario_identified | unresolved_counterfactual`), rejecting non-null `point_utility` unless `POINT_IDENTIFIED` with `OBSERVED_RESPONDENT_PREFERENCE` and direct `observed_direct_evidence_span_ids`.
- **`CounterfactualSolutionMetadata`**: Requires `frontier_namespace == RESOURCE_REGIME_EXPANDED_FRONTIER`, `solution_origin == "COUNTERFACTUAL_INSTITUTIONAL_DESIGN"`, `design_expansion_type == "RESOURCE_REGIME_EXPANSION"`, valid `ResourceRegimeSpec` objects per eligible/conditional subtopic, and rejects `COUNTERFACTUAL_PROHIBITED_PRUNING_SOURCES` (clusters, values, goods taxonomy, resource eligibility, disagreement, or confidence).
- **`FrontierComparisonResult`**: Uses `CounterfactualParetoStatus` (adding `UNRESOLVED_DUE_TO_COUNTERFACTUAL_UTILITY` as a fifth state distinct from `UNRESOLVED_DUE_TO_CODING_UNCERTAINTY`), verifies zero removal (`frontier_a_feasible_ids` is a subset of `frontier_b_feasible_ids`), preserves frozen `FRONTIER_A` snapshot hashes, and tracks the configurable regime config `runs/<run_id>/counterfactual_regime_config.json`.

