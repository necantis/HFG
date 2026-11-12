# Data Contracts & Interface Specifications

**Document Version:** `1.0.0`  
**Schema Version (`SCHEMA_VERSION`):** `"1.0.0"`  
**Owner:** Agent 00 — System Architect  
**Canonical Python Implementation:** `src/contracts.py`  
**Canonical JSON Schema:** `schemas/interfaces.json`

---

## 1. Cross-Contract Conventions

Every interface in the system adheres to four foundational conventions:

### 1.1 Schema Versioning
Every serialized record includes `schema_version: str = "1.0.0"`. Deserializers in `src/checkpointing.py` and `src/artifact_registry.py` reject records with mismatched major versions and trigger upstream regeneration when minor/patch contracts evolve.

### 1.2 Provenance Block (`ProvenanceMeta`)
Every interface embeds or inherits standardized provenance fields:
- `record_id: str` — Deterministic UUIDv5 or SHA-256 prefix derived from primary key fields.
- `run_id: str` — Identifier of the active `RunManifest`.
- `dataset_fingerprint: str` — SHA-256 digest of the raw input survey file.
- `created_at_utc: str` — ISO-8601 UTC timestamp.
- `producer_module: str` — Canonical module path (e.g., `"src/subtopic_extraction.py"`).
- `producer_agent: str` — Responsible agent identifier (e.g., `"agent_02"`).
- `upstream_artifact_ids: list[str]` — Content-addressed IDs of all parent records/artifacts.
- `config_hash: str` — SHA-256 digest of the active stage configuration and prompt templates.

### 1.3 Missingness Representation (`MissingnessState`)
Missing survey responses and unexpressed subtopic stances are **never** represented by `0.0` or empty strings. All interfaces use the explicit enumeration `MissingnessState`:
- `OBSERVED`: Participant provided a substantive response addressing the question/subtopic.
- `MISSING_RAW_BLANK`: Cell is empty/`NaN` in the raw survey file.
- `MISSING_NON_SUBSTANTIVE`: Participant wrote `"N/A"`, `"none"`, `"?"`, `"je ne sais pas"`, `"keine Angabe"`, etc.
- `NOT_MENTIONED_IN_RESPONSE`: Participant answered the question (`OBSERVED` at question level) but did not mention or imply a stance on this specific dynamically extracted subtopic (`preference_value = None`).
- `NOT_APPLICABLE_FRAME`: Classification (such as economic good type) is disabled for this question's `AnalyticalFrameType`.
- `SKIPPED_MISSING_INPUT_FILE`: Optional module (Baldwin/RRV) skipped because no validated active input file exists.

### 1.4 Uncertainty Representation (`UncertaintyEnvelope`)
Whenever an interface captures an empirical, coded, or aggregated quantity, uncertainty is represented explicitly via `UncertaintyEnvelope`:
- `point_estimate: float | None`
- `ci_lower_95: float | None` — 2.5th percentile bound.
- `ci_upper_95: float | None` — 97.5th percentile bound.
- `std_error: float | None` — Standard deviation across coders or bootstrap/Monte Carlo draws.
- `coder_confidence: float | None` $\in [0.0, 1.0]$ — Epistemic certainty of the LLM coder(s).
- `coder_agreement: float | None` $\in [0.0, 1.0]$ — Concordance between `coder_a` and `coder_b`.
- `distribution_type: Literal["DETERMINISTIC", "DUAL_CODER_INTERVAL", "MONTE_CARLO_EMPIRICAL", "BOOTSTRAP"]`

---

## 2. Interface Specifications (20 Required Contracts)

---

### 2.1 `RunManifest`
Captures the immutable execution context, hardware topology, model hashes, and input dataset digests for an entire pipeline run.

- **Required Fields:**
  - `run_id: str`
  - `survey_group_id: str` (derived from input metadata/filename, never hardcoded)
  - `dataset_path: str`
  - `dataset_fingerprint: str` (SHA-256)
  - `expected_question_count: int` (`13`)
  - `detected_participant_count: int` ($N$, dynamically populated at ingestion)
  - `supported_languages: list[Literal["fr", "de", "en"]]`
  - `gpu_device_name: str` (e.g., `"NVIDIA RTX PRO 6000 Blackwell Server Edition"`)
  - `coder_a_model_spec: dict[str, Any]` (`model_id`, `weights_hash`, `port`, `temperature`, `seed`)
  - `coder_b_model_spec: dict[str, Any]` (`model_id`, `weights_hash`, `port`, `temperature`, `seed`)
  - `hardcoding_scan_passed: bool`
- **Optional Fields:**
  - `baldwin_input_path: str | None`
  - `baldwin_input_fingerprint: str | None`
  - `rrv_input_path: str | None`
  - `rrv_input_fingerprint: str | None`
  - `git_commit_sha: str | None`
  - `notes: str | None`
- **Missingness Representation:** Optional voting files use `baldwin_input_path = None` and `baldwin_input_fingerprint = None` when absent.
- **Uncertainty Representation:** Records global `monte_carlo_draws: int` (default `2000`), `random_seed: int`, and `confidence_level: float` (`0.95`).
- **Schema Version:** `schema_version: str = "1.0.0"`
- **Provenance Fields:** `record_id`, `run_id`, `dataset_fingerprint`, `created_at_utc`, `producer_module="src/orchestrator.py"`, `producer_agent="agent_01"`, `upstream_artifact_ids=[]`, `config_hash`.

---

### 2.2 `QuestionSpec`
Defines one of the 13 substantive survey questions, its multilingual prompt text, and its analytical frame rules.

- **Required Fields:**
  - `question_id: str` (`"Q01"` through `"Q13"`)
  - `question_index: int` (`1` through `13`)
  - `column_headers_by_lang: dict[str, str]` (raw column headers found in dataset for `fr`, `de`, `en`)
  - `canonical_prompt_en: str`
  - `analytical_frame: Literal["GOVERNANCE_GOODS_ALLOCATION", "INSTITUTIONAL_DESIGN_DECISION", "PERCEPTION_AND_DIAGNOSTIC", "OPEN_STRATEGIC_PRIORITY"]`
  - `economic_good_classification_policy: Literal["ENABLED", "CONDITIONAL", "DISABLED"]`
  - `alternative_classification_scheme: str` (e.g., `"DIAGNOSTIC_VALENCE_AND_ROOT_CAUSE"` when economic good classification is `DISABLED`)
  - `observed_response_count: int`
  - `missing_response_count: int`
- **Optional Fields:**
  - `prompt_fr: str | None`
  - `prompt_de: str | None`
  - `domain_tags: list[str]`
  - `compatibility_rule_id: str | None`
- **Missingness Representation:** Explicitly tracks `observed_response_count` vs. `missing_response_count` and `missing_participant_ids: list[str]`.
- **Uncertainty Representation:** `frame_assignment_source: Literal["DECLARED_CONFIG", "VALIDATED_HEADER"]` (deterministic `0.0` variance).
- **Schema Version:** `schema_version: str = "1.0.0"`
- **Provenance Fields:** Standard `ProvenanceMeta` (`producer_module="src/question_registry.py"`).

---

### 2.3 `EvidenceSpan`
An immutable, character-offset-verified substring from a single participant's response to a single question.

- **Required Fields:**
  - `span_id: str`
  - `participant_id: str`
  - `question_id: str` (`"Q01"`–`"Q13"`)
  - `detected_language: Literal["fr", "de", "en"]`
  - `raw_response_sha256: str`
  - `char_start: int` (0-based inclusive index into raw cell string)
  - `char_end: int` (0-based exclusive index into raw cell string)
  - `verbatim_quote: str` (must equal `raw_text[char_start:char_end]`)
  - `missingness_state: MissingnessState` (`OBSERVED` for valid spans; if a cell is missing, no `EvidenceSpan` is fabricated)
- **Optional Fields:**
  - `english_working_gloss: str | None` (clearly marked as translation gloss, never replacing `verbatim_quote`)
  - `sentence_index: int | None`
- **Missingness Representation:** Missing participant cells have zero `EvidenceSpan` entries and are recorded in the raw ledger with `MissingnessState.MISSING_RAW_BLANK` or `MISSING_NON_SUBSTANTIVE`.
- **Uncertainty Representation:** `language_detection_confidence: float` $\in [0.0, 1.0]$; `span_boundary_confidence: float` $\in [0.0, 1.0]$.
- **Schema Version:** `schema_version: str = "1.0.0"`
- **Provenance Fields:** Standard `ProvenanceMeta` (`producer_module="src/evidence_ledger.py"`).

---

### 2.4 `SubtopicCandidate`
A coder-extracted candidate subtopic proposed from a specific participant's `EvidenceSpan` before cross-participant canonicalization.

- **Required Fields:**
  - `candidate_id: str`
  - `question_id: str`
  - `participant_id: str`
  - `coder_id: Literal["coder_a", "coder_b"]`
  - `evidence_span_ids: list[str]` (non-empty list of valid `EvidenceSpan.span_id`)
  - `proposed_label_en: str`
  - `proposed_description: str`
  - `stance_direction: float` $\in [-1.0, +1.0]$
  - `semantic_importance: float` $\in [0.0, 1.0]$
  - `coder_confidence: float` $\in [0.0, 1.0]$
- **Optional Fields:**
  - `proposed_economic_good_class: Literal["private_good", "club_good", "common_good", "public_good", "NOT_APPLICABLE"] | None`
  - `proposed_alternative_frame_label: str | None` (used for perception/diagnostic questions)
  - `native_language_keywords: list[str]`
- **Missingness Representation:** If economic good classification is disabled for `question_id`, `proposed_economic_good_class` is `None` with `MissingnessState.NOT_APPLICABLE_FRAME`.
- **Uncertainty Representation:** `coder_confidence: float` $\in [0.0, 1.0]$ derived from model structured evaluation and token log-probabilities.
- **Schema Version:** `schema_version: str = "1.0.0"`
- **Provenance Fields:** Standard `ProvenanceMeta` (`producer_module="src/subtopic_extraction.py"`).

---

### 2.5 `CanonicalSubtopic`
A deduplicated, reconciled subtopic within one of the 13 questions, synthesized strictly from `SubtopicCandidate` clusters produced by `coder_a` and `coder_b`.

- **Required Fields:**
  - `subtopic_id: str` (e.g., `"Q01_ST01"`)
  - `question_id: str`
  - `canonical_label_en: str`
  - `canonical_description: str`
  - `source_candidate_ids: list[str]` (must reference $\ge 1$ `SubtopicCandidate`)
  - `supporting_span_ids: list[str]` (all `EvidenceSpan` IDs grounding this subtopic)
  - `mention_participant_count: int` (number of distinct participants addressing this subtopic)
  - `unmentioned_participant_count: int` (number of respondents to `question_id` who did not mention this subtopic)
  - `missing_question_participant_count: int` (number of participants who left `question_id` blank)
  - `economic_good_applicability: Literal["APPLIED", "NOT_APPLICABLE_FRAME", "MIXED_CONTESTED"]`
  - `coder_agreement: float` $\in [0.0, 1.0]$ (Jaccard/bipartite matching score between `coder_a` and `coder_b` subtopic induction)
- **Optional Fields:**
  - `labels_by_lang: dict[Literal["fr", "de", "en"], str]`
  - `dominant_economic_good_class: Literal["private_good", "club_good", "common_good", "public_good"] | None`
  - `economic_good_distribution: dict[str, float] | None` (empirical distribution across participants when contested)
  - `question_specific_category: str | None` (for perception/diagnostic questions)
  - `linked_value_ids: list[str]`
  - `allowed_postures: list[str]` (e.g., `["OPPOSE", "NEUTRAL_CONDITIONAL", "SUPPORT"]`)
- **Missingness Representation:** Explicitly partitions $N = \text{mention\_participant\_count} + \text{unmentioned\_participant\_count} + \text{missing\_question\_participant\_count}$.
- **Uncertainty Representation:** `coder_agreement: float` $\in [0.0, 1.0]$ and `mean_coder_confidence: float` $\in [0.0, 1.0]$.
- **Schema Version:** `schema_version: str = "1.0.0"`
- **Provenance Fields:** Standard `ProvenanceMeta` (`producer_module="src/subtopic_extraction.py"`).

---

### 2.6 `ValueAssignment`
Represents an evidence-supported organisational value that connects responses and `CanonicalSubtopic` nodes across the 13 questions.

- **Required Fields:**
  - `value_assignment_id: str`
  - `value_id: str` (canonical slug derived from data, e.g., `"VAL_TRANSPARENCY"`, never imported from external survey groups)
  - `value_label_en: str`
  - `value_definition: str`
  - `participant_id: str`
  - `question_id: str`
  - `subtopic_id: str`
  - `evidence_span_ids: list[str]` (mandatory verbatim span support)
  - `polarity: float` $\in [-1.0, +1.0]$ (whether the value is invoked positively as a goal or negatively as a deficit)
  - `semantic_importance: float` $\in [0.0, 1.0]$
  - `coder_confidence: float` $\in [0.0, 1.0]$
  - `coder_agreement: float` $\in [0.0, 1.0]$
- **Optional Fields:**
  - `coder_a_raw_label: str | None`
  - `coder_b_raw_label: str | None`
  - `cross_question_bridge_ids: list[str]` (other `subtopic_id`s across `Q01`–`Q13` sharing this `value_id`)
- **Missingness Representation:** If a response invokes no identifiable organisational value, no `ValueAssignment` is emitted (`MissingnessState.NOT_MENTIONED_IN_RESPONSE`).
- **Uncertainty Representation:** `coder_confidence`, `coder_agreement`, and `polarity_uncertainty_interval: tuple[float, float]`.
- **Schema Version:** `schema_version: str = "1.0.0"`
- **Provenance Fields:** Standard `ProvenanceMeta` (`producer_module="src/value_extraction.py"`).

---

### 2.7 `CodingResult`
Records the structured coding output (either per-coder or reconciled) for a `(participant_id, question_id, subtopic_id)` tuple.

- **Required Fields:**
  - `coding_id: str`
  - `participant_id: str`
  - `question_id: str`
  - `subtopic_id: str`
  - `coder_source: Literal["coder_a", "coder_b", "reconciled"]`
  - `missingness_state: MissingnessState`
  - `participant_preference: float | None` $\in [-1.0, +1.0]$ (`None` iff `missingness_state != OBSERVED`)
  - `semantic_importance: float | None` $\in [0.0, 1.0]$ (`None` iff `missingness_state != OBSERVED`)
  - `coder_confidence: float | None` $\in [0.0, 1.0]$ (`None` iff `missingness_state != OBSERVED`)
  - `coder_agreement: float | None` $\in [0.0, 1.0]$ (populated on `"reconciled"` records; `None` on single-coder pre-reconciliation records)
  - `evidence_span_ids: list[str]` (must be non-empty whenever `missingness_state == OBSERVED`)
- **Optional Fields:**
  - `economic_good_class: Literal["private_good", "club_good", "common_good", "public_good", "NOT_APPLICABLE"] | None`
  - `perception_category: str | None`
  - `value_assignment_ids: list[str]`
  - `reconciliation_method: Literal["EXACT_MATCH", "CONFIDENCE_WEIGHTED_MEAN", "ARBITRATED_SPAN_CHECK", "HIGH_UNCERTAINTY_FLAGGED"] | None`
  - `rationale_summary: str | None`
- **Missingness Representation:** Enforces invariant: `if missingness_state != OBSERVED: assert participant_preference is None and semantic_importance is None`.
- **Uncertainty Representation:** `preference_ci_lower: float | None`, `preference_ci_upper: float | None`, `coder_confidence`, and `coder_agreement` remain four distinct, non-conflated fields.
- **Schema Version:** `schema_version: str = "1.0.0"`
- **Provenance Fields:** Standard `ProvenanceMeta` (`producer_module="src/reconciliation.py"`).

---

### 2.8 `PreferenceCell`
A single validated cell $(i, m)$ in the participant-by-subtopic `PreferenceMatrix` for participant $i$ and canonical subtopic $m$.

- **Required Fields:**
  - `cell_id: str` (`f"{participant_id}__{subtopic_id}"`)
  - `participant_id: str`
  - `question_id: str`
  - `subtopic_id: str`
  - `missingness_state: MissingnessState`
  - `participant_preference: float | None` $\in [-1.0, +1.0]$
  - `semantic_importance: float | None` $\in [0.0, 1.0]$
  - `coder_confidence: float | None` $\in [0.0, 1.0]$
  - `coder_agreement: float | None` $\in [0.0, 1.0]$
  - `preference_lower_bound: float | None` $\in [-1.0, +1.0]$
  - `preference_upper_bound: float | None` $\in [-1.0, +1.0]$
  - `preference_std_error: float | None` $\ge 0.0$
  - `source_coding_id: str`
  - `evidence_span_ids: list[str]`
- **Optional Fields:**
  - `coder_a_preference: float | None`
  - `coder_b_preference: float | None`
  - `coder_a_importance: float | None`
  - `coder_b_importance: float | None`
  - `economic_good_class: str | None`
- **Missingness Representation:** `missingness_state` distinguishes `MISSING_RAW_BLANK` (participant skipped the question) from `NOT_MENTIONED_IN_RESPONSE` (participant answered the question but did not address this subtopic). In both cases, `participant_preference is None`.
- **Uncertainty Representation:** Stores `[preference_lower_bound, preference_upper_bound]`, `preference_std_error`, `coder_confidence`, and `coder_agreement`.
- **Schema Version:** `schema_version: str = "1.0.0"`
- **Provenance Fields:** Standard `ProvenanceMeta` (`producer_module="src/preference_matrix.py"`).

---

### 2.9 `PreferenceMatrix`
The complete, validated $N \times M$ preference structure over all $N$ active participants and all $M$ dynamically extracted `CanonicalSubtopic` columns across the 13 questions.

- **Required Fields:**
  - `matrix_id: str`
  - `participant_ids: list[str]` (length $N$)
  - `question_ids: list[str]` (the 13 questions `Q01`–`Q13`)
  - `subtopic_ids: list[str]` (length $M$, ordered by `question_id`)
  - `subtopic_to_question: dict[str, str]`
  - `cells: list[PreferenceCell]` (length $N \times M$)
  - `observed_cell_count: int`
  - `missing_blank_cell_count: int`
  - `unmentioned_cell_count: int`
  - `overall_coder_agreement_mean: float`
  - `overall_coder_confidence_mean: float`
  - `validation_passed: bool`
- **Optional Fields:**
  - `question_coverage_rates: dict[str, float]`
  - `participant_response_rates: dict[str, float]`
  - `flagged_low_agreement_cell_ids: list[str]`
- **Missingness Representation:** Preserves the exact 2D mask of `MissingnessState` for every $(i, m)$ entry; zero imputation is strictly forbidden.
- **Uncertainty Representation:** Aggregates matrix-wide `overall_coder_agreement_mean`, `overall_coder_confidence_mean`, and retains per-cell `UncertaintyEnvelope` parameters for downstream Monte Carlo sampling.
- **Schema Version:** `schema_version: str = "1.0.0"`
- **Provenance Fields:** Standard `ProvenanceMeta` (`producer_module="src/preference_matrix.py"`).

---

### 2.10 `FeasibleAlternative`
A question-level institutional or policy configuration for a single question $q \in \{\text{Q01} \dots \text{Q13}\}$, defined as a coherent vector of stances across the canonical subtopics of $q$.

- **Required Fields:**
  - `alternative_id: str` (e.g., `"Q01_ALT_01"`)
  - `question_id: str`
  - `label_en: str` (dynamically generated from constituent subtopic postures)
  - `description_en: str`
  - `subtopic_postures: dict[str, float]` (maps each `subtopic_id` of `question_id` to target posture $a_m \in [-1.0, +1.0]$)
  - `supporting_participant_count: int` (empirical count of participants aligned with this posture combination)
  - `feasibility_status: Literal["FEASIBLE", "PRUNED_INCOMPATIBLE", "PRUNED_ZERO_SUPPORT"]`
- **Optional Fields:**
  - `economic_good_profile: dict[str, str] | None` (only if applicable to `question_id`)
  - `aligned_value_ids: list[str]`
  - `constraint_checks_passed: list[str]`
- **Missingness Representation:** If a subtopic is orthogonal to a specific question-level alternative, its posture weight is `0.0` (explicitly marked in `active_subtopic_mask: dict[str, bool]`), whereas participant missingness remains in `PreferenceMatrix`.
- **Uncertainty Representation:** `empirical_support_uncertainty: UncertaintyEnvelope` (confidence interval on the share of participants supporting this question-level alternative).
- **Schema Version:** `schema_version: str = "1.0.0"`
- **Provenance Fields:** Standard `ProvenanceMeta` (`producer_module="src/solution_space.py"`).

---

### 2.11 `GovernanceSolution`
A complete cross-question institutional solution combining compatible `FeasibleAlternative` selections across the substantive governance questions.

- **Required Fields:**
  - `solution_id: str` (e.g., `"SOL_001"`)
  - `label_en: str` (dynamically synthesized from constituent question-level alternatives and institutional characteristics)
  - `question_alternatives: dict[str, str]` (maps `question_id` $\to$ `alternative_id`)
  - `global_subtopic_vector: dict[str, float]` (maps `subtopic_id` $\to$ $a_m \in [-1.0, +1.0]$ across all active subtopics)
  - `included_question_ids: list[str]`
  - `diagnostic_context_question_ids: list[str]`
  - `explanatory_organisational_values: list[str]` (`value_id`s used ex-post to explain or characterize the solution; strictly non-filtering)
  - `logical_constraints_satisfied: list[str]` (e.g., `"allocation_shares_sum_to_100pct"`)
  - `institutional_constraints_satisfied: list[str]` (e.g., `"evaluation_entity_possesses_decision_right"`)
  - `dependencies_satisfied: list[str]` (e.g., `"club_fund_membership_rules_present"`)
  - `generation_method: Literal["COMBINATORIAL_CONSTRAINT_SATISFACTION", "DISCRETE_POLICY_GRID", "STRUCTURAL_DIRECTED_SEARCH"]`
- **Optional Fields:**
  - `summary_by_lang: dict[Literal["fr", "de", "en"], str]`
  - `economic_good_summary: dict[str, str] | None` (for allocation/access questions only)
- **Missingness Representation:** Questions that are purely diagnostic (`PERCEPTION_AND_DIAGNOSTIC`) inform diagnostic context rather than prescriptive allocation postures when appropriate, tracked via `included_question_ids: list[str]` and `diagnostic_context_question_ids: list[str]`.
- **Constraint-Based Pruning vs. Characterization Rule:** Solutions are pruned **strictly and exclusively** by logical constraints, institutional constraints, and structural dependencies. Cluster assignments and organisational values may be annotated ex-post in `explanatory_organisational_values` or report summaries to characterize solutions, but are strictly prohibited from acting as inclusion or pruning gates.
- **Uncertainty Representation:** `feasibility_evaluation_status: Literal["STRICTLY_FEASIBLE", "INCOMPLETE_DEPENDENCY", "LOGICAL_CONFLICT"]`.
- **Schema Version:** `schema_version: str = "1.0.0"`
- **Provenance Fields:** Standard `ProvenanceMeta` (`producer_module="src/solution_space.py"`).

---

### 2.12 `ParticipantUtility`
The utility evaluation of a single participant $i$ for a single `GovernanceSolution` $s$, computed **exclusively** from the validated `PreferenceMatrix`.

#### Mathematical Formulation
For participant $i$ and governance solution $s$ with subtopic vector $a_m(s) \in [-1, +1]$, let $\mathcal{M}_i^{\text{obs}} = \{m : \text{state}(i, m) = \text{OBSERVED}\}$ be the set of subtopics on which participant $i$ expressed an empirical preference $p_{i,m} \in [-1, +1]$ with semantic importance $w_{i,m} \in [0, 1]$:

$$U_i(s) = \frac{\sum_{m \in \mathcal{M}_i^{\text{obs}}} \tilde{w}_{i,m} \cdot p_{i,m} \cdot a_m(s)}{\sum_{m \in \mathcal{M}_i^{\text{obs}}} \tilde{w}_{i,m}}, \quad \text{where } \tilde{w}_{i,m} = \max(\epsilon_w, w_{i,m})$$

Notice that:
- `coder_confidence` and `coder_agreement` do **not** distort the point estimate $U_i(s)$; instead, they parameterize the uncertainty distribution $U_i^{(k)}(s)$ around $U_i(s)$.
- If $\mathcal{M}_i^{\text{obs}} = \emptyset$ (participant had no observed preferences on any active subtopic of $s$), $U_i(s)$ is `None` (`MissingnessState.MISSING_RAW_BLANK`).

- **Required Fields:**
  - `utility_id: str` (`f"{participant_id}__{solution_id}"`)
  - `participant_id: str`
  - `solution_id: str`
  - `preference_matrix_id: str` (proving exclusive derivation from validated `PreferenceMatrix`)
  - `missingness_state: MissingnessState`
  - `observed_subtopic_count: int` ($|\mathcal{M}_i^{\text{obs}}|$)
  - `total_subtopic_count: int` ($M$)
  - `point_utility: float | None` $\in [-1.0, +1.0]$
  - `utility_ci_lower_95: float | None` $\in [-1.0, +1.0]$
  - `utility_ci_upper_95: float | None` $\in [-1.0, +1.0]$
  - `utility_std_error: float | None` $\ge 0.0$
  - `mean_coder_confidence: float | None` $\in [0.0, 1.0]$
  - `mean_coder_agreement: float | None` $\in [0.0, 1.0]$
- **Optional Fields:**
  - `per_question_utilities: dict[str, float | None]` (breakdown across `Q01`–`Q13`)
  - `individual_regret: float | None` ($\max_{s'} U_i(s') - U_i(s)$)
  - `is_below_veto_threshold: bool | None`
- **Missingness Representation:** If `observed_subtopic_count == 0`, `missingness_state = MISSING_RAW_BLANK` and `point_utility = None`. Per-question utilities for unanswered questions are `None`.
- **Uncertainty Representation:** `utility_ci_lower_95`, `utility_ci_upper_95`, `utility_std_error`, `mean_coder_confidence`, and `mean_coder_agreement`.
- **Schema Version:** `schema_version: str = "1.0.0"`
- **Provenance Fields:** Standard `ProvenanceMeta` (`producer_module="src/utilities.py"`).

---

### 2.13 `ParetoResult`
Deterministic participant-level Pareto dominance analysis and multi-criteria social choice rankings across all evaluated `GovernanceSolution` candidates.

- **Required Fields:**
  - `pareto_result_id: str`
  - `preference_matrix_id: str`
  - `evaluated_solution_ids: list[str]`
  - `valid_participant_ids: list[str]` (participants with $\ge 1$ observed utility)
  - `excluded_all_missing_participant_ids: list[str]`
  - `nondominated_solution_ids: list[str]` (the exact Pareto frontier $\mathcal{F}$)
  - `dominated_solution_map: dict[str, list[str]]` (maps each dominated `solution_id` to the list of solutions that strictly Pareto-dominate it)
  - `rawls_maximin_scores: dict[str, float]` ($\min_i U_i(s)$)
  - `utilitarian_scores: dict[str, float]` ($\text{mean}_i U_i(s)$)
  - `nash_welfare_scores: dict[str, float]` (geometric mean of shifted utilities $U_i(s) - U_{\min} + \epsilon$)
  - `gini_inequality_scores: dict[str, float]` $\in [0.0, 1.0]$ (lower is more equal)
  - `atkinson_inequality_scores: dict[str, float]` $\in [0.0, 1.0]$
  - `opposition_counts: dict[str, int]` (number of participants with $U_i(s) < \tau_{\text{veto}}$)
  - `opposition_shares: dict[str, float]` $\in [0.0, 1.0]$
  - `max_regret_scores: dict[str, float]` ($\max_i (\max_{s'} U_i(s') - U_i(s))$)
  - `rankings_by_criterion: dict[str, list[str]]` (ordered lists of `nondominated_solution_ids` for `"rawls"`, `"utilitarian"`, `"nash"`, `"lowest_gini"`, `"lowest_opposition"`, `"minimax_regret"`)
- **Optional Fields:**
  - `pairwise_dominance_margins: dict[str, float]`
  - `cluster_mean_utilities: dict[str, dict[str, float]]`
- **Missingness Representation:** Explicitly lists `valid_participant_ids` vs. `excluded_all_missing_participant_ids`. Pareto dominance is evaluated over `valid_participant_ids` without imputing missing participants.
- **Uncertainty Representation:** Point-estimate deterministic frontier; links directly to `RobustParetoResult` for uncertainty-propagated metrics.
- **Schema Version:** `schema_version: str = "1.0.0"`
- **Provenance Fields:** Standard `ProvenanceMeta` (`producer_module="src/pareto.py"`).

---

### 2.14 `RobustParetoResult`
Propagates dual-coder disagreement and confidence uncertainty from `PreferenceMatrix` through `ParticipantUtility` into the Pareto frontier via $K$ Monte Carlo perturbation realizations.

- **Required Fields:**
  - `robust_pareto_id: str`
  - `base_pareto_result_id: str`
  - `monte_carlo_draws: int` ($K$, default `2000`)
  - `random_seed: int`
  - `frontier_inclusion_probabilities: dict[str, float]` $\in [0.0, 1.0]$ (fraction of $K$ draws in which `solution_id` is Pareto-nondominated)
  - `robust_frontier_solution_ids: list[str]` (solutions with inclusion probability $\ge \alpha_{\text{robust}}$, default `0.50`, plus sensitivity tiers at `0.80` and `0.95`)
  - `criterion_top1_probabilities: dict[str, dict[str, float]]` (for each criterion—Rawls, Utilitarian, Nash, Min-Opposition—the probability each solution ranks #1 across the $K$ draws)
  - `utility_metric_intervals: dict[str, dict[str, UncertaintyEnvelope]]` (95% CIs for Rawls, Utilitarian, Nash, Gini, and Opposition share per solution)
- **Optional Fields:**
  - `veto_threshold_sensitivity: dict[str, dict[str, float]]` (opposition share across $\tau_{\text{veto}} \in \{-0.7, -0.5, -0.3\}$)
  - `subtopic_weight_ perturbation_sensitivity: dict[str, float]`
- **Missingness Representation:** Missing cells in `PreferenceMatrix` remain missing across all $K$ Monte Carlo draws (missingness is never perturbed into synthetic observations).
- **Uncertainty Representation:** Full empirical distribution over $K$ realizations (`frontier_inclusion_probabilities`, `criterion_top1_probabilities`, and `UncertaintyEnvelope` per welfare criterion).
- **Schema Version:** `schema_version: str = "1.0.0"`
- **Provenance Fields:** Standard `ProvenanceMeta` (`producer_module="src/robust_pareto.py"`).

---

### 2.15 `ClusterResult`
Data-driven participant clustering derived strictly from the active `PreferenceMatrix` using missingness-aware pairwise distances.

- **Required Fields:**
  - `cluster_result_id: str`
  - `preference_matrix_id: str`
  - `distance_metric: Literal["MASKED_COSINE", "MASKED_WEIGHTED_L1", "MASKED_EUCLIDEAN"]`
  - `min_shared_subtopics_for_pair: int`
  - `candidate_k_evaluated: list[int]` (e.g., `[2, 3, 4, 5, 6]`)
  - `silhouette_scores_by_k: dict[int, float]`
  - `stability_scores_by_k: dict[int, float]` (bootstrap Jaccard / ARI stability per $k$)
  - `selected_k: int` ($k^*$ chosen automatically by maximizing composite silhouette + stability criterion)
  - `cluster_assignments: dict[str, str]` (maps `participant_id` $\to$ `cluster_id` like `"CLUSTER_01"`, or `"UNASSIGNED_INSUFFICIENT_DATA"`)
  - `cluster_sizes: dict[str, int]`
  - `cluster_ distinguishing_subtopics: dict[str, list[str]]` (top `subtopic_id`s characterizing each cluster based on empirical effect size)
  - `cluster_distinguishing_values: dict[str, list[str]]` (`value_id`s characterizing each cluster)
- **Optional Fields:**
  - `descriptive_labels_en: dict[str, str]` (generated strictly from `cluster_distinguishing_subtopics`, labeled as empirical summaries)
  - `pairwise_distance_matrix_hash: str | None`
- **Missingness Representation:** Participants with fewer observed subtopics than `min_shared_subtopics_for_pair` are assigned `"UNASSIGNED_INSUFFICIENT_DATA"` (`MissingnessState.MISSING_RAW_BLANK`) rather than forced into a cluster via zero-imputation.
- **Uncertainty Representation:** `participant_assignment_confidence: dict[str, float]` (bootstrap co-clustering probability for each participant) and `stability_scores_by_k`.
- **Schema Version:** `schema_version: str = "1.0.0"`
- **Provenance Fields:** Standard `ProvenanceMeta` (`producer_module="src/clustering.py"`).

---

### 2.16 `BaldwinResult`
Result of the conditional Baldwin sequential Borda elimination voting procedure. Executes **only if** an active-group rank/score ballot file exists and passes validation.

- **Required Fields:**
  - `baldwin_result_id: str`
  - `execution_status: Literal["EXECUTED", "SKIPPED_NO_VALID_INPUT", "FAILED_VALIDATION"]`
  - `input_file_path: str | None`
  - `input_file_sha256: str | None`
  - `candidate_ids: list[str]` (empty if skipped)
  - `valid_ballot_count: int` (`0` if skipped)
  - `missing_or_spoiled_ballot_count: int` (`0` if skipped)
  - `elimination_rounds: list[dict[str, Any]]` (each round records active candidates, Borda scores, lowest candidate(s) eliminated, and tie-breaking status)
  - `winner_candidate_ids: list[str]` (supports ties; empty if skipped)
- **Optional Fields:**
  - `tie_breaking_rule_used: str | None`
  - `borda_initial_ranking: list[str] | None`
- **Missingness Representation:** When no active Baldwin input file is present, `execution_status = "SKIPPED_NO_VALID_INPUT"`, `input_file_path = None`, and no historical ballots are loaded. Partial ballots with missing ranks use standard modified Borda weighting without fabricating preferences.
- **Uncertainty Representation:** `tie_margin_min: float | None` and `bootstrap_winner_stability: dict[str, float] | None` (fraction of ballot-resample bootstrap runs won by each candidate).
- **Schema Version:** `schema_version: str = "1.0.0"`
- **Provenance Fields:** Standard `ProvenanceMeta` (`producer_module="src/voting_baldwin.py"`).

---

### 2.17 `RRVResult`
Result of the conditional Reweighted Range Voting (proportional multi-winner score voting) module. Executes **only if** an active-group RRV score file exists and passes validation.

- **Required Fields:**
  - `rrv_result_id: str`
  - `execution_status: Literal["EXECUTED", "SKIPPED_NO_VALID_INPUT", "FAILED_VALIDATION"]`
  - `input_file_path: str | None`
  - `input_file_sha256: str | None`
  - `score_scale_min: float | None`
  - `score_scale_max: float | None`
  - `reweighting_constant_k: float | None` (e.g., $k = 1.0$ for Jefferson/D'Hondt or $k = 0.5$ for Sainte-Laguë proportional reweighting $w_i = \frac{k}{k + \sum_{c \in W} s_{i,c}/S_{\max}}$)
  - `seats_to_fill: int` (`0` if skipped)
  - `valid_ballot_count: int` (`0` if skipped)
  - `missing_ballot_count: int` (`0` if skipped)
  - `selection_rounds: list[dict[str, Any]]` (round-by-round weighted score totals, selected winner, and updated voter weights)
  - `selected_committee_ids: list[str]` (ordered list of winners; empty if skipped)
- **Optional Fields:**
  - `proportionality_satisfaction_metrics: dict[str, float] | None`
- **Missingness Representation:** When no active RRV file exists, `execution_status = "SKIPPED_NO_VALID_INPUT"`. Unscored cells within a valid ballot are tracked via `missing_cell_policy: Literal["EXPLICIT_NA_EXCLUDED_FROM_DENOMINATOR"]`.
- **Uncertainty Representation:** `round_margin_min: float | None` and `bootstrap_committee_inclusion_freq: dict[str, float] | None`.
- **Schema Version:** `schema_version: str = "1.0.0"`
- **Provenance Fields:** Standard `ProvenanceMeta` (`producer_module="src/voting_rrv.py"`).

---

### 2.18 `ReportClaim`
An atomic, audit-verified analytical statement included in the final report, bound to explicit empirical evidence or mathematical artifacts.

- **Required Fields:**
  - `claim_id: str`
  - `section_id: str` (e.g., `"SEC_Q01"`, `"SEC_VALUES"`, `"SEC_PARETO"`, `"SEC_VOTING"`)
  - `question_ids: list[str]`
  - `claim_type: Literal["QUALITATIVE_SUBTOPIC_FINDING", "CROSS_QUESTION_VALUE_LINK", "ECONOMIC_GOOD_CLASSIFICATION", "PERCEPTION_FINDING", "CLUSTER_CHARACTERIZATION", "PARETO_RANKING_STATEMENT", "VOTING_OUTCOME_STATEMENT", "MISSINGNESS_DISCLOSURE"]`
  - `statement_text_en: str`
  - `evidence_span_ids: list[str]` (required for qualitative/subtopic/value claims)
  - `canonical_subtopic_ids: list[str]`
  - `artifact_references: list[str]` (IDs of `PreferenceMatrix`, `ParetoResult`, `RobustParetoResult`, `ClusterResult`, etc.)
  - `numerical_values_cited: dict[str, float | int]` (every number in `statement_text_en` must match the referenced artifact exactly)
  - `verification_passed: bool`
- **Optional Fields:**
  - `statement_translations: dict[Literal["fr", "de"], str]`
  - `caveats_and_assumptions: list[str]`
- **Missingness Representation:** Every question section must include at least one `MISSINGNESS_DISCLOSURE` claim stating exact observed $N_q$ vs. missing $N - N_q$ counts.
- **Uncertainty Representation:** `uncertainty_summary: UncertaintyEnvelope` (e.g., coder agreement rate, confidence interval, or robust Pareto inclusion probability accompanying the claim).
- **Schema Version:** `schema_version: str = "1.0.0"`
- **Provenance Fields:** Standard `ProvenanceMeta` (`producer_module="src/report_generator.py"`).

---

### 2.19 `ArtifactRecord`
Registry entry for any persisted dataset, checkpoint, matrix, or report generated during the pipeline run.

- **Required Fields:**
  - `artifact_id: str`
  - `artifact_type: str` (name of the contract interface, e.g., `"PreferenceMatrix"`)
  - `stage_id: str`
  - `file_path: str`
  - `content_sha256: str`
  - `byte_size: int`
  - `record_count: int`
  - `is_cacheable: bool`
  - `invalidation_keys: dict[str, str]` (`dataset_fingerprint`, `config_hash`, `upstream_merkle_root`, `schema_version`)
- **Optional Fields:**
  - `compression: Literal["none", "gzip", "zstd", "parquet_snappy"] | None`
  - `execution_duration_seconds: float | None`
- **Missingness Representation:** Tracks `null_record_count: int` inside the serialized payload summary.
- **Uncertainty Representation:** `validation_status: Literal["VERIFIED", "STALE_NEEDS_REGEN", "CORRUPTED"]`.
- **Schema Version:** `schema_version: str = "1.0.0"`
- **Provenance Fields:** Standard `ProvenanceMeta` (`producer_module="src/artifact_registry.py"`).

---

### 2.20 `AgentHandoff`
Structured handoff record emitted when an agent or notebook stage completes its work package and transfers control to downstream agents.

- **Required Fields:**
  - `handoff_id: str`
  - `from_agent: str` (e.g., `"agent_00"`)
  - `to_agents: list[str]` (e.g., `["agent_01", "agent_02", "agent_03", "agent_04"]`)
  - `completed_stage_ids: list[str]`
  - `modified_files: list[str]`
  - `produced_artifact_ids: list[str]`
  - `architectural_decisions: list[str]`
  - `identified_risks: list[dict[str, str]]` (`risk`, `severity`, `mitigation`)
  - `downstream_tasks: dict[str, list[str]]` (maps each target agent to mandatory actionable tasks)
  - `blocking_issues: list[str]`
  - `ready_for_next_stage: bool`
- **Optional Fields:**
  - `skipped_optional_modules: list[str]`
  - `performance_metrics_sec: dict[str, float]`
- **Missingness Representation:** Any unexecuted optional stage is listed in `skipped_optional_modules` with explicit reason codes.
- **Uncertainty Representation:** `open_verification_checks: list[str]` enumerating any invariants pending downstream validation in `04_validation.ipynb`.
- **Schema Version:** `schema_version: str = "1.0.0"`
- **Provenance Fields:** Standard `ProvenanceMeta` (`producer_module="src/orchestrator.py"`).

