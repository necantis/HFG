# Agent Handoff: Agent 02 — Qualitative Coding

- **Agent ID**: `agent_02`
- **Model Used**: `inherit`
- **Branch / Worktree**: `agent/02-qualitative-refinement` (`/home/antigravity/necantis/HFG`)
- **Base Commit**: `25bc988c3070989a2da53c94329b3ab1db9c9061` (`origin/main`)
- **Implementation Commit SHA**: `e9d3c96520229198a1a29ae265cdf1025b5f12f4` (handoff recorded in subsequent commit on `agent/02-qualitative-refinement`)
- **Pushed Commit SHA**: See subsequent handoff commit on `agent/02-qualitative-refinement` (reported in agent final message)
- **Timestamp (UTC)**: `2026-11-13T06:59:32Z`
- **Active Run ID**: `run_20261111_002`

---

## 1. Files Changed

- `src/nlp/__init__.py` (Created: package exports for schemas, prompts, repair safety, structured matching, open value extraction, corpus discovery, and canonical entry point `QuestionCorpusCoder`)
- `src/nlp/schemas.py` (Created: Pydantic v2 structured input/output contracts including `NormalizedResponseInput`, `CorpusChunkMetadata`, `QuestionCorpusInput`, `SubtopicGoodsAssessment`, `LLMDiscoveredAlternative`, `LLMDiscoveredSubtopic`, `LLMCorpusDiscoveryResponse`, `DiscoveredQuestionTaxonomy`, `ProbabilityRepairRecord`, `LLMSubtopicCandidate`, `LLMValueExtraction`, `ValueConsolidationProposal`, `SubtopicMatchProposal`, `LLMQuestionCodingResponse`, `ThemeRecord`, `ThemesCodebook`)
- `src/nlp/prompts.py` (Created: `SYSTEM_PROMPT_QUALITATIVE_CODER`, `compute_source_evidence_hash`, `compute_prompt_hash`, `assert_coder_input_isolation`, and `PromptBuilder` supporting Phase 1 corpus discovery, documented chunk consolidation, and Phase 2 participant assignment)
- `src/nlp/repair.py` (Created: `AmbiguousQuoteOffsetError`, `classify_response_status`, `repair_json_string_with_audit`, `validate_and_repair_probabilities`, exact offset resolution `find_exact_char_offsets` without paraphrasing, and subtopic-level `enforce_economic_goods_policy`)
- `src/nlp/matching.py` (Created: `SubtopicDescriptor` and `SubtopicMatcher` enforcing retrieval-only lexical Jaccard, topic-vs-position separation, structured matching over `definition`/`evidence`/`decision_object`/`mechanism`/`scope`, and `UNCERTAIN_FOR_AGENT_03` preservation)
- `src/nlp/value_extraction.py` (Created: two-stage open organisational value discovery with non-exhaustive `EXAMPLE_ORGANISATIONAL_VALUE_ALIASES` / `CANONICAL_ORGANISATIONAL_VALUES`, `ValueExtractor.extract_stage_a_value`, `ValueExtractor.propose_cross_question_consolidation`, `ValueExtractor.create_value_assignment`)
- `src/nlp/subtopic_extraction.py` (Created: `EvidenceSpanExtractor`, `QuestionCorpusDiscoveryEngine`, `SubtopicExtractor`, `CanonicalSubtopicSynthesizer`, canonical entry point `QuestionCorpusCoder.code_question_corpus`, and `DualCoderRunner`)
- `src/nlp/fixtures.py` (Created: multilingual `fr`/`de`/`en` fixtures covering substantive responses, mixed uncertainty + substantive preference, explicit no-opinion, insufficient experience/information, unseen values, and blank/placeholder missingness)
- `src/subtopic_extraction.py` (Created: backward-compatible root module re-export)
- `src/value_extraction.py` (Created: backward-compatible root module re-export)
- `tests/test_nlp.py` (Created: 18 unit and integration tests covering all methodological invariants and edge cases)
- `notebooks/02_qualitative_coding.ipynb` (Created: exploratory validation notebook — **Notebook Inventory Declaration per `docs/NOTEBOOK_INDEX.md`**:
  - **Repository-Relative Path**: `notebooks/02_qualitative_coding.ipynb`
  - **Status**: `exploration` (non-production exploratory prototype; never a pipeline production entry point)
  - **GPU Required**: `Yes (Optional / Dev LLM endpoint)` for live LLM testing; CPU smoke-verified on deterministic fixtures
  - **Prerequisites**: `answers_normalized_v1`, `src/subtopic_extraction.py`, `src/value_extraction.py`, `src/nlp/`)
- `docs/AGENT_HANDOFFS/agent_02_handoff.md` (Updated)

---

## 2. Interfaces Changed, Coding Entry Point & Schemas

### Exact Canonical Coding Entry Point
- `src.nlp.subtopic_extraction.QuestionCorpusCoder.code_question_corpus(...)` (re-exported at `src.subtopic_extraction.QuestionCorpusCoder` and `src.nlp.QuestionCorpusCoder`)
  - Executes:
    1. Equivalent source evidence hashing (`compute_source_evidence_hash`) shared across `coder_a` and `coder_b`, kept strictly separate from model-specific prompt hashes (`coder_a_prompt_hash`, `coder_b_prompt_hash`).
    2. Anti-leakage input assertions (`assert_coder_input_isolation`).
    3. Phase 1 full-question corpus discovery (`QuestionCorpusDiscoveryEngine.discover_question_taxonomy`) with documented chunk-and-consolidate (`CorpusChunkMetadata`) preserving minority positions and never silently truncating.
    4. Phase 2 participant-level assignment (`SubtopicExtractor.process_response_detailed`) preserving explicit `response_status`, separating `semantic_importance`, `coder_confidence`, `alternative_probabilities`, and `probability_interpretation`, and extracting exact character-offset `EvidenceSpan`s.
    5. Stage A free-form value extraction (`ValueExtractor.extract_stage_a_value`) without enum restriction and Stage B cross-question consolidation proposals (`ValueExtractor.propose_cross_question_consolidation`).
    6. Structured subtopic matching & canonical synthesis (`CanonicalSubtopicSynthesizer.synthesize_with_matching_audit`) returning `CanonicalSubtopic`s and `SubtopicMatchProposal`s for Agent 03 adjudication.

### Input / Output Schemas (`src/nlp/schemas.py`)
- **Input Schemas**:
  - `NormalizedResponseInput`: Consumes Agent 01 `answers_normalized_v1` fields (`response_id`, `participant_id`, `question_id`, `raw_value`, `normalized_value`, `response_type`, `detected_language`, `missingness_state: src.contracts.MissingnessState`, `is_valid`, `validation_flags`) plus optional `response_status: Optional[ResponseStatusLabel]` (`observed_substantive`, `explicit_no_opinion`, `insufficient_experience`, `insufficient_information`, `mixed_substantive_and_uncertainty`, `missing_raw_blank`, `missing_non_substantive`).
  - `QuestionCorpusInput`: Exact wording by language (`fr`/`de`/`en`), `canonical_prompt_en`, `QuestionSpec` analytical frame & goods policy, ordered list of `NormalizedResponseInput`, and optional `source_evidence_hash`.
- **Intermediate & Output Schemas**:
  - `DiscoveredQuestionTaxonomy` / `LLMCorpusDiscoveryResponse` (with `LLMDiscoveredSubtopic`, `LLMDiscoveredAlternative`, `CorpusChunkMetadata`, `SubtopicGoodsAssessment`)
  - `LLMQuestionCodingResponse` (with `LLMEvidenceSpan`, `uncertainty_statements`, `LLMSubtopicCandidate`, `LLMValueExtraction`, `unmentioned_subtopic_keys`)
  - `ProbabilityRepairRecord` (captures `raw_values`, `repaired_values`, `repair_action`, `scale_detected`, `reason`)
  - `SubtopicMatchProposal` (`MATCH_SAME_TOPIC_SAME_POSITION`, `MATCH_SAME_TOPIC_OPPOSING_ALTERNATIVES`, `UNCERTAIN_FOR_AGENT_03`, `NO_MATCH`)
  - `ValueConsolidationProposal` (Stage B cross-question consolidation proposals preserving original labels, uncertainty, and unresolved alternatives for Agent 03)
  - `ThemesCodebook` (planned `themes_codebook_v1` container with `methodological_flags`)

---

## 3. Shared-File Change Requests (If Any)

No shared governance, contract, manifest, dependency, or peer handoff files were modified on `agent/02-qualitative-refinement`. Agent 00 / Agent 01 integration requests:

1. **Request `contracts_value_polarity_optional`**:
   - **Affected interface**: `src/contracts.py` (`ValueAssignment.polarity` and `ValueAssignment.polarity_uncertainty_interval`) and `schemas/interfaces.json`
   - **Proposed fields or dependency**: `polarity: Optional[float] = None`, `polarity_uncertainty_interval: Optional[Tuple[float, float]] = None`
   - **Reason**: Open value discovery extracts values where directional polarity is sometimes not meaningful (e.g., non-polar institutional commitments). Currently `ValueExtractor.create_value_assignment` bridges this by emitting `0.0` alongside a `[polarity_not_applicable]` marker in `value_definition` until the shared contract allows `None`.
   - **Compatibility impact**: Backwards-compatible extension once downstream consumers handle `polarity is None`.
   - **Required tests**: Assert `ValueAssignment(..., polarity=None)` validates cleanly against `src.contracts` and `schemas/interfaces.json`.

2. **Request `agent01_response_status_alignment`**:
   - **Affected interface**: `src/contracts.py` (`NormalizedResponse` / `answers_normalized_v1`) and Agent 01 ingestion output
   - **Proposed fields or dependency**: Optional `response_status: Optional[Literal["observed_substantive", "explicit_no_opinion", "insufficient_experience", "insufficient_information", "mixed_substantive_and_uncertainty", "missing_raw_blank", "missing_non_substantive"]] = None` (or equivalent documented metadata flag on `NormalizedResponse`)
   - **Reason**: Enables seamless zero-reclassification pass-through of Agent 01's explicit epistemic non-preference and mixed-uncertainty classifications alongside canonical `MissingnessState`. Currently `NormalizedResponseInput` accepts optional `response_status` and falls back to `classify_response_status` when absent, without inventing a competing missingness taxonomy.
   - **Compatibility impact**: Additive, backwards-compatible optional field.
   - **Required tests**: Integration test confirming Agent 01 `answers_normalized.parquet` rows round-trip directly into `NormalizedResponseInput` / `QuestionCorpusInput`.

---

## 4. Tests Executed

```bash
.venv/bin/pytest tests/test_nlp.py -v
.venv/bin/pytest tests/ -v
.venv/bin/python3 -m src.freshness_checker --check-all
```
- **`tests/test_nlp.py`**: `18 passed in 0.23s`
  - Covers: unseen free-form values accepted without coercion into the 7 example categories; original labels preserved; Stage B cross-question consolidation proposals preserving uncertainty and unresolved alternatives; polarity separated from `semantic_importance` and optional (`None`); full-question corpus discovery (never single-participant concatenation or title restatement); multiple evidence-grounded subtopics; chunk-and-consolidate preserving minority positions without silent truncation; same topic with opposing alternatives grouped under one subtopic; low lexical overlap with semantic equivalence; lexical overlap alone never merging distinct mechanisms; subtopic-level selective goods applicability overriding question-level default without imposing 1D ordering; explicit `no_opinion` / `insufficient_experience` / `insufficient_information` preserved as reportable statements with zero fabricated preference; mixed uncertainty + substantive coding; blank/placeholder missing answers receiving zero coding; probability repair audit (micro-drift & unambiguous percentage only; negative, NaN, arbitrary score normalization, and materially invalid totals rejected); exact quote offset disambiguation for repeated quotes (never paraphrasing/inventing); independent Coder A / Coder B input equivalence + anti-leakage checks + separate evidence vs. prompt hashes; end-to-end `QuestionCorpusCoder.code_question_corpus` & `DualCoderRunner` & multilingual `fr`/`de`/`en` fixtures.
- **Full Repository Suite (`tests/`)**: `42 passed` (`tests/test_acceptance.py`: 6, `tests/test_artifact_registry.py`: 6, `tests/test_collaboration_policy.py`: 4, `tests/test_context_pack.py`: 4, `tests/test_freshness_checker.py`: 4, `tests/test_nlp.py`: 18; re-verified `42 passed` with `notebooks/02_qualitative_coding.ipynb` tracked in git).
- **Notebook Smoke Validation**: Executed all Python cells of `notebooks/02_qualitative_coding.ipynb` via `.venv/bin/python3` (`NOTEBOOK_SMOKE_OK`).
- **Freshness Checker**: `9/9` checks passed, `0` issues detected.
- **Evidentiary Clarification**: All executed tests are deterministic CPU unit/fixture tests. They do **not** constitute a validated GPU benchmark or a completed full-survey analytical coding run.

---

## 5. Artifacts Created & Registered

- `runs/run_20261111_002/manifest.json` was **NOT modified**. Zero unexecuted analytical outputs were registered as completed production evidence.
- **Planned / Unexecuted Analytical Artifacts** (awaiting Agent 01 Gate 1 & Agent 07 GPU runtime):
  - **Artifact ID**: `themes_codebook_v1`
    - **Status**: `PLANNED — NOT EXECUTED` (blocked on Agent 01 Gate 1 & Agent 07 GPU validation)
    - **Scope**: `integration_canonical` (future production output of `01_gpu_coders.ipynb` / `QuestionCorpusCoder`)
    - **Planned Path**: `data/processed/themes_codebook.json`
    - **Schema Version**: `v1.1.0`
    - **Validation Status**: `pending_upstream_and_runtime`
  - **Planned Intermediate Outputs per Question Corpus**: `DiscoveredQuestionTaxonomy` (Coder A & B), participant `EvidenceSpan`s & `uncertainty_spans`, `SubtopicCandidate`s, `CanonicalSubtopic`s, `SubtopicMatchProposal`s, Stage A `LLMValueExtraction`s, Stage B `ValueConsolidationProposal`s, and `ProbabilityRepairRecord`s.

---

## 6. Assumptions

- `NormalizedResponseInput` treats `src.contracts.MissingnessState` as the sole canonical missingness enum while supporting additive `response_status` metadata from Agent 01.
- Stage B (`propose_cross_question_consolidation`) and `SubtopicMatcher` produce auditable proposals (`ValueConsolidationProposal`, `SubtopicMatchProposal`) rather than silently resolving ambiguous merges; final cross-coder adjudication remains with Agent 03.
- Dual-LLM execution callables (`coder_a_*_fn`, `coder_b_*_fn`) will be bound by Agent 07's validated GPU runtime (`src/model_runtime.py`) inside `01_gpu_coders.ipynb` with `temperature = 0.0` and distinct model weights/endpoints.

---

## 7. Unresolved Issues, Runtime Prerequisites & Unresolved Methodological Decisions

1. **Runtime Prerequisites Blocking Authoritative Full-Survey Coding Run**:
   - **Agent 01 Gate 1**: Verified normalized dataset (`data/normalized/answers_normalized.parquet`, `answers_normalized_v1`) and 13+ `QuestionSpec` records matching `data/raw/survey_raw.csv` (`ISSUE-001` in `docs/OPEN_ISSUES.md`).
   - **Agent 07 GPU Runtime**: Dual concurrent open-weight LLM server endpoints (`coder_a`, `coder_b`) validated on the target GPU hardware (`runs/<run_id>/gpu_runtime_config.json`).
2. **Unresolved Methodological Decisions Requiring Downstream Alignment**:
   - **Flag for Agent 04 & Agent 00 (Architecture Reviewer) — Probability Interpretation vs. Cardinal Utility**: `alternative_probabilities` in Agent 02 explicitly denote either `epistemic_uncertainty_over_preference`, `explicit_mixed_preference`, or `conditional_or_context_dependent` stance as inferred from text. Coding probability must **never** be silently treated by Agent 04 as measured von Neumann–Morgenstern cardinal utility intensities without an explicit methodological decision / ADR.
   - **Flag for Agent 03 (Evidence & Reconciliation)**: Cross-coder adjudication is required for Stage B `ValueConsolidationProposal`s (including `unresolved_alternatives`) and `SubtopicMatchProposal`s tagged `UNCERTAIN_FOR_AGENT_03`, as well as promotion of `[polarity_not_applicable]` non-polar value commitments.

---

## 8. Downstream Dependencies

- **Agent 01**: Confirm `NormalizedResponseInput` / `QuestionCorpusInput` ingestion adapter compatibility upon Gate 1 completion.
- **Agent 03**: Consumes `QuestionCorpusCoder.code_question_corpus(...)` outputs (`evidence_spans`, `uncertainty_spans`, `subtopic_candidates`, `canonical_subtopics`, `subtopic_match_proposals`, `value_stage_a_extractions`, `value_stage_b_proposals`, `probability_repairs`).
- **Agent 04 & Agent 00**: Review `probability_interpretation` flag (coding uncertainty is not cardinal utility) and shared-file change request for `ValueAssignment.polarity: Optional[float]`.
- **Agent 07**: Bind `coder_a` / `coder_b` GPU inference callables into `QuestionCorpusCoder.code_question_corpus`.
- **Agent 11 / Agent 10**: Review and integrate `agent/02-qualitative-refinement` (`notebooks/02_qualitative_coding.ipynb` index update + shared-file requests).

---

## 9. Exact Recommended Next Action

1. Review and integrate branch `agent/02-qualitative-refinement` via Agent 11 / authorized PR alongside Agent 01 (`agent/01-ingestion-refinement`) and Agent 07 (`agent/07-runtime`), resolving the two Shared-File Change Requests in Section 3 and updating `docs/NOTEBOOK_INDEX.md` for `notebooks/02_qualitative_coding.ipynb`.
2. Execute the authoritative qualitative coding run (`QuestionCorpusCoder.code_question_corpus`) **only after** both Agent 01 Gate 1 and Agent 07 GPU runtime validation pass.
