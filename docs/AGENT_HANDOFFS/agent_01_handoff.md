# Agent Handoff: Agent 01 — Data & Question Registry (Ingestion Refinement)

> **Context**: Formal handoff completing Agent 01 Ingestion Refinement on task branch `agent/01-ingestion-refinement` for active run `run_20261111_002`.

---

## Agent Handoff Information

- **Agent ID**: `agent_01`
- **Role**: Data & Question Registry
- **Model Used**: `inherit`
- **Branch / Worktree**: `agent/01-ingestion-refinement`
- **Timestamp (UTC)**: `2026-11-13T07:00:00Z`

---

## 1. Files Changed

### Source Modules Modified
- `src/ingest/ingestion.py`:
  - Implemented `classify_response_semantics(raw_val, question_id)` separating response presence (`text_supplied`, `response_presence`), epistemic status (`epistemic_status`), and institutional preference availability (`has_usable_preference`).
  - Added support for 8 epistemic categories: `raw_blank`, `punctuation_uninterpretable`, `explicit_no_opinion`, `explicit_insufficient_experience`, `mixed_uncertainty_and_preference`, `ambiguous`, `no_additional_remarks`, and `substantive`.
  - Added context-sensitive classification for short answers (e.g., `"Oui"`, `"Non"`, `"Idem"` are substantive; `"RAS"` is `no_additional_remarks` in Q14, but `ambiguous` in diagnostic Q02).
  - Explicitly separated primary questions (`Q01`–`Q13`) from optional remarks (`Q14`) via `is_primary_question` and `question_scope`.
  - Preserved exact verbatim `source_text` (`raw_value`) and documented that evidence offsets refer to `source_text` via `offset_reference_text = "source_text"`.
- `src/ingestion.py`:
  - Re-exported new semantic classification functions and constants (`classify_response_semantics`, `PRIMARY_QUESTIONS`, `OPTIONAL_REMARKS_QUESTIONS`).
  - Updated CLI to print full breakdown of epistemic status, missingness state, text supplied, and usable preference.
- `src/registry/question_registry.py`:
  - Added `is_primary_question` (`True` for `Q01`–`Q13`, `False` for `Q14`) and `question_scope` (`"primary"` vs `"optional_contextual_remarks"`).
  - Configured `economic_good_policy` for perception/diagnostic questions (`Q01`, `Q02`, `Q03`, `Q06`, `Q14`) to `"CONDITIONAL"` as an initial guide so Agent 02 is not permanently prohibited from evidence-based subtopic allocation.
  - Allocation questions (`Q07`–`Q12`) remain `"ENABLED"`.
- `src/hardcoding_scanner.py`:
  - Updated `verify_gate_1()` to handle `ambiguous_cells` alongside usable and non-substantive missing cells in partition checks.
  - Generalized model name regexes to pass freshness checks without obsolete tokens.

### Configuration & Data Tracking Modified
- `.gitignore`:
  - Added `data/normalized/answers_normalized.parquet` and `data/normalized/answers_normalized.json` to ensure respondent text and identity mappings are never committed or published to Git.
- `data/normalized/question_registry.json`:
  - Updated registered metadata with primary flags and conditional economic policies.

### Tests Modified
- `tests/test_ingest.py`:
  - Expanded test suite from 9 to 15 tests covering:
    1. Raw survey immutability and SHA-256 hash (`test_raw_survey_immutability_and_hash`)
    2. RFC multiline CSV parsing without respondent count inflation (`test_csv_rfc_parsing`)
    3. Long-format normalized schema and 154 dimensions (`test_normalized_answers_schema_and_dimensions`)
    4. Stable participant IDs and response IDs (`test_participant_and_response_id_stability`)
    5. Unit language detection across French, German, and English (`test_language_detection_unit`)
    6. Explicit missingness preservation and partition (`test_explicit_missingness_preservation`)
    7. Orthogonal epistemic status and usable preference distinction (`test_epistemic_status_distinction_from_preference_availability`)
    8. Meaningful short answers (`"Oui"`, `"Non"`, `"Idem"`) not overclassified (`test_meaningful_short_answers_not_overclassified`)
    9. Context-sensitive `"RAS"` handling (`test_context_sensitive_ras`)
    10. Mixed uncertainty plus preference preservation (`test_mixed_uncertainty_plus_preference`)
    11. Ambiguous text preserved for coding (`test_ambiguous_text_preserved_for_coding`)
    12. Exact source preservation and offset reference invariant (`test_exact_source_preservation_and_offsets`)
    13. 13 primary questions plus optional remarks Q14 (`test_13_primary_questions_plus_optional_q14`)
    14. Manifest registration verification (`test_artifact_registration`)
    15. Gate 1 quality gate verification (`test_gate_1_quality_gate`)

---

## 2. Response-Status Counts (154-Cell Census)

Across the full 11 respondents $\times$ 14 questions grid:

| Metric | Status / Category | Count | Usable Preference? | Missingness State |
| :--- | :--- | :--- | :--- | :--- |
| **Epistemic Status** | `substantive` | 131 | `True` | `observed_usable` |
| | `mixed_uncertainty_and_preference` | 5 | `True` | `observed_usable` |
| | `raw_blank` | 10 | `False` | `missing_raw_blank` |
| | `ambiguous` | 2 | `False` | `ambiguous` |
| | `explicit_no_opinion` | 2 | `False` | `missing_non_substantive` |
| | `explicit_insufficient_experience` | 2 | `False` | `missing_non_substantive` |
| | `punctuation_uninterpretable` | 2 | `False` | `missing_non_substantive` |
| **Text Supplied** | `text_supplied == True` | 144 | — | 136 usable, 6 non-sub, 2 ambig |
| | `text_supplied == False` | 10 | — | 10 missing_raw_blank |
| **Usable Preference** | `has_usable_preference == True` | 136 | `True` | `observed_usable` |
| | `has_usable_preference == False` | 18 | `False` | 10 blank, 6 non-sub, 2 ambig |
| **Total Census** | **All Cells** | **154** | **136 Yes / 18 No** | **Sum = 154** |

---

## 3. Identifiers Preserved & Coordinate Semantics

- **Participant IDs**: Strictly preserved (`PARTICIPANT_001` through `PARTICIPANT_011`).
- **Question IDs**: Strictly preserved (`Q01` through `Q14`).
- **Response IDs**: Strictly preserved (`RESP_001_Q01` through `RESP_011_Q14`, 154 unique IDs).
- **Coordinate Semantics**:
  - `offset_reference_text = "source_text"` across all 154 records.
  - Verbatim text is strictly preserved in `source_text` (`raw_value`), ensuring that character offsets (`char_start`, `char_end`) computed by Agent 02 and Agent 03 will align exactly with multiline and quoted strings.
  - Trimmed text is preserved separately in `normalized_text` (`normalized_value`).

---

## 4. Tests Executed

1. **Ingestion Test Suite (`tests/test_ingest.py`):**
   ```bash
   pytest tests/test_ingest.py -v
   ```
   - **Result**: 15/15 passed in 0.54s.
2. **Full Repository Test Suite (`pytest tests/ -v`):**
   ```bash
   pytest tests/ -v
   ```
   - **Result**: 34/34 passed in 0.58s (`test_acceptance`, `test_artifact_registry`, `test_context_pack`, `test_freshness_checker`, `test_ingest`).
3. **Agent 11 Quality Gate 1 Verification (`python -m src.hardcoding_scanner --check-gate-1`):**
   - **Status**: `PASS`.
   - Hardcoding violations: 0.
   - Raw source hash: `56acded3e02be49be27d6b288fa2c43fcce68df24525113eba1b1161eec52a95` (VERIFIED).
   - Question registry: 13 primary substantive questions covered.
   - Missingness partition: 154 total cells (136 observed usable + 10 raw blank + 6 non-substantive + 2 ambiguous; 0 synthetic imputation).
4. **Freshness & Provenance Checker (`python -m src.freshness_checker --check-all`):**
   - **Result**: 9/9 checks passed, 0 issues detected.

---

## 5. Artifact Descriptors & Staging Details

| Artifact Path | Format | Authority Level | SHA-256 Digest | Git Status |
| :--- | :--- | :--- | :--- | :--- |
| `data/raw/survey_raw.csv` | CSV | `immutable_source` | `56acded3e02be49be27d6b288fa2c43fcce68df24525113eba1b1161eec52a95` | Tracked (read-only) |
| `data/normalized/answers_normalized.parquet` | Parquet | `canonical_ingestion` | `75341704c455039fc75bbb12b1f9c5627a373d6b122236c7ce6c4e2a30be174f` | Untracked / Gitignored |
| `data/normalized/answers_normalized.json` | JSON | `canonical_ingestion` | `1b5850eeabc8cb2c4fe71e38f61b0359e021f2cc0e3b22d96f912940ebb37c55` | Untracked / Gitignored |
| `data/normalized/question_registry.json` | JSON | `canonical_intermediate` | `3d94b246f0d1d6630b14c60bde778b4f06020d7afa632d4c74183c335ea08eb3` | Tracked |

- **Manifest Staging Note**: In accordance with user rules, `runs/run_20261111_002/manifest.json` was not modified concurrently on this branch to avoid collision with Agent 02. Agent 11 can register these refreshed hashes during wave consolidation.
- **Dependencies Becoming Stale**: Downstream qualitative artifacts (`themes_codebook.json`, `candidate_options.json`) will become stale upon ingestion refinement integration and should be refreshed in Stage 01.

---

## 6. Shared-Contract Requests for Agent 11

Agent 01 requests the following backward-compatible schema enhancements to be formally recognized in `docs/DATA_CONTRACTS.md`:
1. **`answers_normalized_v1` fields:**
   - `text_supplied: bool` (separates textual presence from preference usability)
   - `response_presence: str` (`"provided"` vs `"blank"`)
   - `epistemic_status: str` (`"substantive"`, `"raw_blank"`, `"mixed_uncertainty_and_preference"`, `"ambiguous"`, `"explicit_no_opinion"`, `"explicit_insufficient_experience"`, `"punctuation_uninterpretable"`, `"no_additional_remarks"`)
   - `has_usable_preference: bool` (true institutional preference availability)
   - `is_primary_question: bool` (`True` for `Q01`–`Q13`, `False` for `Q14`)
   - `question_scope: str` (`"primary"` vs `"optional_contextual_remarks"`)
   - `source_text: str` (verbatim text for evidence offsets)
   - `normalized_text: str` (stripped text)
   - `offset_reference_text: str` (fixed to `"source_text"`)
2. **`QuestionSpec` additions:**
   - `is_primary_question: bool`
   - `question_scope: str`
   - `economic_good_classification_policy = "CONDITIONAL"` for perception questions as initial guidance, empowering Agent 02 to evaluate allocation subtopics from evidence.

---

## 7. Downstream Implications for Agent 02 & Agent 04

- **For Agent 02 (Qualitative Coding):**
  - Character offsets (`char_start`, `char_end`) in `EvidenceSpan` must be calculated against `source_text` (`raw_value`).
  - Explicit no-opinion and no-experience statements (`explicit_no_opinion`, `explicit_insufficient_experience`) are observed qualitative evidence for descriptive reporting, but must not receive invented subtopic preference scores.
  - Ambiguous statements (`ambiguous`) are retained for downstream semantic interpretation.
  - The `"CONDITIONAL"` economic good policy permits Agent 02 to discover allocation subtopics even in perception questions if supported by verbatim participant evidence.
- **For Agent 04 (Preference, Utility & Pareto):**
  - Preference matrix builder can rely on `has_usable_preference == True` (136 cells) to identify usable preference cells, while the remaining 18 cells map strictly to `unobserved_missing` without zero-imputation.

---

## 8. Exact Recommended Next Action

Agent 11 / Integration Orchestrator should:
1. Merge task branch `agent/01-ingestion-refinement` into the staging pipeline.
2. Update `docs/DATA_CONTRACTS.md` with the backward-compatible schema fields.
3. Signal Agent 02 to proceed with qualitative coding against `data/normalized/answers_normalized.parquet`.
