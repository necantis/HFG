"""Bottom-up question-corpus subtopic discovery, participant coding, and synthesis.

Owned by: Agent 02 — Qualitative Coding
Schema Version: 1.0.0 / v1.1.0
Active Run: run_20261111_002

Core Classes & Entry Point:
- EvidenceSpanExtractor: offset-verified verbatim EvidenceSpan extraction with unambiguous
  disambiguation for repeated identical quotations.
- QuestionCorpusDiscoveryEngine: Phase 1 complete question-corpus discovery with documented
  chunk-and-consolidate (never silently truncating, preserving minority positions).
- SubtopicExtractor: Phase 2 participant-level assignment preserving response status,
  strict probability repair safety, and metadata orthogonality.
- CanonicalSubtopicSynthesizer: structured semantic matching (topic vs. position separation)
  and exact participant partitioning (mention + unmentioned + missing == N).
- DualCoderRunner / QuestionCorpusCoder: canonical coding entry point enforcing two-coder
  independence, separate evidence vs. prompt hashes, and full-corpus discovery -> assignment.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Optional, Set, Tuple

from src.contracts import (
    AnalyticalFrameType,
    CanonicalSubtopic,
    EconomicGoodClass,
    EvidenceSpan,
    MissingnessState,
    ProvenanceMeta,
    ResponseEpistemicStatus,
    SCHEMA_VERSION,
    SubtopicCandidate,
)
from src.nlp.matching import SubtopicDescriptor, SubtopicMatcher
from src.nlp.prompts import (
    PromptBuilder,
    assert_coder_input_isolation,
    compute_prompt_hash,
    compute_source_evidence_hash,
)
from src.nlp.repair import (
    AmbiguousQuoteOffsetError,
    classify_response_status,
    enforce_economic_goods_policy,
    find_exact_char_offsets,
    is_non_substantive_response,
    repair_json_string_with_audit,
    validate_and_repair_probabilities,
)
from src.nlp.schemas import (
    BLANK_OR_NON_REPORTABLE_STATUSES,
    CorpusChunkMetadata,
    DiscoveredQuestionTaxonomy,
    LLMCorpusDiscoveryResponse,
    LLMDiscoveredSubtopic,
    LLMEvidenceSpan,
    LLMQuestionCodingResponse,
    LLMSubtopicCandidate,
    LLMValueExtraction,
    NormalizedResponseInput,
    ProbabilityRepairRecord,
    QuestionCorpusInput,
    REPORTABLE_NO_PREFERENCE_STATUSES,
    ResponseStatusLabel,
    SubtopicGoodsAssessment,
    SubtopicMatchProposal,
    ThemeRecord,
    ThemesCodebook,
    USABLE_PREFERENCE_STATUSES,
    ValueConsolidationProposal,
)
from src.nlp.value_extraction import ValueExtractor


class EvidenceSpanExtractor:
    """Extracts and verifies exact character-offset EvidenceSpan records from response text."""

    def __init__(
        self,
        run_id: str = "run_20261111_002",
        dataset_fingerprint: str = "56acded3e02be49be27d6b288fa2c43fcce68df24525113eba1b1161eec52a95",
    ):
        self.run_id = run_id
        self.dataset_fingerprint = dataset_fingerprint

    def extract_spans(
        self,
        participant_id: str,
        question_id: str,
        raw_text: str,
        detected_language: Literal["fr", "de", "en"],
        quotes_or_spans: List[str | LLMEvidenceSpan],
        config_hash: str = "",
        missingness_state: MissingnessState = MissingnessState.OBSERVED_USABLE,
        allow_ambiguous: bool = False,
        allow_non_preference_spans: bool = False,
        default_span_role: Literal[
            "substantive_evidence",
            "explicit_uncertainty_or_no_opinion",
            "value_evidence",
        ] = "substantive_evidence",
    ) -> List[EvidenceSpan]:
        """Extract verified EvidenceSpan objects.

        Enforces:
        - Exact character offset verification: raw_text[char_start:char_end] == verbatim_quote
        - Unambiguous resolution when identical quotes repeat (raises AmbiguousQuoteOffsetError
          unless expected char_start or sentence_index disambiguates, or allow_ambiguous=True).
        - Non-usable missingness states emit empty list unless `allow_non_preference_spans=True`
          for reportable explicit no-opinion, insufficient-experience, or ambiguous statements.
        """
        if not missingness_state.is_usable() and not allow_non_preference_spans:
            return []

        if not raw_text or not quotes_or_spans:
            return []

        raw_sha256 = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
        spans: List[EvidenceSpan] = []

        for idx, item in enumerate(quotes_or_spans):
            if isinstance(item, LLMEvidenceSpan):
                quote = item.verbatim_quote
                gloss = item.english_working_gloss
                lang = item.detected_language or detected_language
                lang_conf = item.language_confidence
                sent_idx = item.sentence_index
                expected_start = item.char_start
                span_role = item.span_role
            else:
                quote = str(item)
                gloss = None
                lang = detected_language
                lang_conf = 1.0
                sent_idx = None
                expected_start = None
                span_role = default_span_role

            if not quote or not quote.strip():
                continue

            try:
                char_start, char_end, matched_str = find_exact_char_offsets(
                    raw_text,
                    quote,
                    expected_char_start=expected_start,
                    sentence_index=sent_idx,
                    allow_ambiguous=allow_ambiguous,
                )
            except AmbiguousQuoteOffsetError:
                raise
            except ValueError:
                # Never invent or paraphrase missing quotes
                continue

            span_hash = hashlib.sha256(
                f"{self.run_id}_{question_id}_{participant_id}_{char_start}_{char_end}".encode("utf-8")
            ).hexdigest()[:12]
            span_id = f"SPAN_{question_id}_{participant_id}_{span_hash}"

            provenance = ProvenanceMeta(
                record_id=span_hash,
                run_id=self.run_id,
                dataset_fingerprint=self.dataset_fingerprint,
                created_at_utc=datetime.now(timezone.utc).isoformat(),
                producer_module="src/nlp/subtopic_extraction.py",
                producer_agent="agent_02",
                upstream_artifact_ids=[],
                config_hash=config_hash,
                schema_version=SCHEMA_VERSION,
            )

            span = EvidenceSpan(
                span_id=span_id,
                participant_id=participant_id,
                question_id=question_id,
                detected_language=lang,
                raw_response_sha256=raw_sha256,
                char_start=char_start,
                char_end=char_end,
                verbatim_quote=matched_str,
                missingness_state=missingness_state,
                language_detection_confidence=lang_conf,
                span_boundary_confidence=1.0,
                provenance=provenance,
                english_working_gloss=gloss,
                sentence_index=sent_idx if sent_idx is not None else idx,
                offset_reference_text="source_text",
                span_role=span_role,
                schema_version=SCHEMA_VERSION,
            )
            spans.append(span)

        return spans


class QuestionCorpusDiscoveryEngine:
    """Phase 1 complete question-corpus subtopic discovery with chunk-and-consolidate support."""

    def __init__(
        self,
        coder_id: Literal["coder_a", "coder_b"] = "coder_a",
        model_adapter_tag: str = "default",
        max_corpus_chars: int = 24000,
        max_responses_per_chunk: int = 40,
    ):
        self.coder_id = coder_id
        self.prompt_builder = PromptBuilder(coder_id=coder_id, model_adapter_tag=model_adapter_tag)
        self.max_corpus_chars = max_corpus_chars
        self.max_responses_per_chunk = max_responses_per_chunk

    def build_chunks(
        self,
        responses: List[NormalizedResponseInput],
    ) -> List[Tuple[List[NormalizedResponseInput], CorpusChunkMetadata]]:
        """Partition responses deterministically into chunks without dropping or truncating any item."""
        if not responses:
            return []

        raw_chunks: List[Tuple[int, int, List[NormalizedResponseInput], int]] = []
        current: List[NormalizedResponseInput] = []
        current_chars = 0
        start_idx = 0

        for idx, resp in enumerate(responses):
            text_len = len(resp.raw_value or "") + 160
            # Note: even a single large response is never truncated; it gets its own chunk
            if current and (
                current_chars + text_len > self.max_corpus_chars
                or len(current) >= self.max_responses_per_chunk
            ):
                raw_chunks.append((start_idx, idx - 1, current, current_chars))
                current = [resp]
                current_chars = text_len
                start_idx = idx
            else:
                current.append(resp)
                current_chars += text_len

        if current:
            raw_chunks.append((start_idx, len(responses) - 1, current, current_chars))

        total_chunks = len(raw_chunks)
        result: List[Tuple[List[NormalizedResponseInput], CorpusChunkMetadata]] = []
        for c_idx, (s_i, e_i, chunk_items, ch_len) in enumerate(raw_chunks):
            meta = CorpusChunkMetadata(
                chunk_index=c_idx,
                total_chunks=total_chunks,
                start_item_index=s_i,
                end_item_index=e_i,
                participant_ids=[r.participant_id for r in chunk_items],
                response_ids=[r.response_id for r in chunk_items],
                char_count=ch_len,
            )
            result.append((chunk_items, meta))
        return result

    @staticmethod
    def _ensure_minority_preservation(
        chunk_subtopics: List[LLMDiscoveredSubtopic],
        consolidated: List[LLMDiscoveredSubtopic],
    ) -> List[LLMDiscoveredSubtopic]:
        """Guarantee no minority position discovered in any chunk is dropped during consolidation."""
        consolidated_rids: Set[str] = set()
        consolidated_keys: Set[str] = set()
        for st in consolidated:
            consolidated_keys.add(st.subtopic_key)
            consolidated_rids.update(st.supporting_response_ids)

        preserved = list(consolidated)
        for st in chunk_subtopics:
            if st.is_minority_position:
                st_rids = set(st.supporting_response_ids)
                # Keep if neither its key nor any of its supporting response IDs were absorbed
                if st.subtopic_key not in consolidated_keys and (
                    not st_rids or not (st_rids & consolidated_rids)
                ):
                    preserved.append(st)
                    consolidated_keys.add(st.subtopic_key)
                    consolidated_rids.update(st_rids)
        return preserved

    def discover_question_taxonomy(
        self,
        corpus: QuestionCorpusInput,
        discovery_callable: Callable[[str, str], str | Dict[str, Any] | LLMCorpusDiscoveryResponse],
        consolidation_callable: Optional[
            Callable[[str, str], str | Dict[str, Any] | LLMCorpusDiscoveryResponse]
        ] = None,
    ) -> DiscoveredQuestionTaxonomy:
        """Discover multiple subtopics across the complete question corpus.

        - Passes exact question wording + all participant responses + stable IDs + response status.
        - If corpus fits within max_corpus_chars & max_responses_per_chunk, executes a single complete call.
        - If corpus exceeds limits, executes documented chunk-and-consolidate (as many LLM calls
          as completeness requires), recording chunk boundaries and preserving minority positions.
        """
        source_hash = corpus.source_evidence_hash or compute_source_evidence_hash(corpus)

        # Estimate full corpus size
        total_chars = sum(len(r.raw_value or "") + 160 for r in corpus.responses)
        needs_chunking = (
            total_chars > self.max_corpus_chars
            or len(corpus.responses) > self.max_responses_per_chunk
        )

        def _invoke_discovery(sys_p: str, usr_p: str) -> LLMCorpusDiscoveryResponse:
            raw_out = discovery_callable(sys_p, usr_p)
            if isinstance(raw_out, LLMCorpusDiscoveryResponse):
                return raw_out
            if isinstance(raw_out, dict):
                return LLMCorpusDiscoveryResponse.model_validate(raw_out)
            parsed_dict, _ = repair_json_string_with_audit(str(raw_out))
            return LLMCorpusDiscoveryResponse.model_validate(parsed_dict)

        if not needs_chunking:
            user_prompt, prompt_hash, _ = self.prompt_builder.build_corpus_discovery_prompt(corpus)
            parsed = _invoke_discovery(self.prompt_builder.system_prompt, user_prompt)
            minority_keys = [st.subtopic_key for st in parsed.discovered_subtopics if st.is_minority_position]
            return DiscoveredQuestionTaxonomy(
                question_id=corpus.question_id,
                coder_id=self.coder_id,
                source_evidence_hash=source_hash,
                prompt_hash=prompt_hash,
                discovered_subtopics=parsed.discovered_subtopics,
                chunked=False,
                chunk_boundaries=[],
                total_llm_calls=1,
                minority_positions_preserved=minority_keys,
            )

        # Chunk-and-Consolidate (never silently truncating, no fixed call limit)
        chunks = self.build_chunks(corpus.responses)
        chunk_boundaries: List[CorpusChunkMetadata] = []
        all_chunk_subtopics: List[LLMDiscoveredSubtopic] = []
        prompt_hashes: List[str] = []
        llm_calls = 0

        for chunk_items, chunk_meta in chunks:
            user_prompt, p_hash, _ = self.prompt_builder.build_corpus_discovery_prompt(
                corpus,
                chunk_responses=chunk_items,
                chunk_meta=chunk_meta,
            )
            prompt_hashes.append(p_hash)
            chunk_resp = _invoke_discovery(self.prompt_builder.system_prompt, user_prompt)
            llm_calls += 1
            chunk_boundaries.append(chunk_meta)
            all_chunk_subtopics.extend(chunk_resp.discovered_subtopics)

        # Consolidate across chunks
        cons_prompt, cons_hash = self.prompt_builder.build_chunk_consolidation_prompt(
            corpus,
            chunk_boundaries=chunk_boundaries,
            chunk_subtopics=all_chunk_subtopics,
        )
        prompt_hashes.append(cons_hash)

        if consolidation_callable is not None:
            raw_cons = consolidation_callable(self.prompt_builder.system_prompt, cons_prompt)
            llm_calls += 1
            if isinstance(raw_cons, LLMCorpusDiscoveryResponse):
                cons_resp = raw_cons
            elif isinstance(raw_cons, dict):
                cons_resp = LLMCorpusDiscoveryResponse.model_validate(raw_cons)
            else:
                parsed_dict, _ = repair_json_string_with_audit(str(raw_cons))
                cons_resp = LLMCorpusDiscoveryResponse.model_validate(parsed_dict)
            consolidated_subtopics = self._ensure_minority_preservation(
                all_chunk_subtopics,
                cons_resp.discovered_subtopics,
            )
        else:
            # Deterministic union preserving all unique subtopics and minority positions
            by_key: Dict[str, LLMDiscoveredSubtopic] = {}
            for st in all_chunk_subtopics:
                if st.subtopic_key not in by_key:
                    by_key[st.subtopic_key] = st
                else:
                    existing = by_key[st.subtopic_key]
                    merged_rids = sorted(set(existing.supporting_response_ids) | set(st.supporting_response_ids))
                    merged_pids = sorted(set(existing.supporting_participant_ids) | set(st.supporting_participant_ids))
                    merged_alts = list(existing.discovered_alternatives)
                    seen_alt_ids = {a.alternative_id for a in merged_alts}
                    for a in st.discovered_alternatives:
                        if a.alternative_id not in seen_alt_ids:
                            merged_alts.append(a)
                            seen_alt_ids.add(a.alternative_id)
                    by_key[st.subtopic_key] = existing.model_copy(
                        update={
                            "supporting_response_ids": merged_rids,
                            "supporting_participant_ids": merged_pids,
                            "discovered_alternatives": merged_alts,
                            "is_minority_position": existing.is_minority_position or st.is_minority_position,
                        }
                    )
            consolidated_subtopics = list(by_key.values())

        combined_prompt_hash = compute_prompt_hash("|".join(prompt_hashes))
        minority_keys = [st.subtopic_key for st in consolidated_subtopics if st.is_minority_position]

        return DiscoveredQuestionTaxonomy(
            question_id=corpus.question_id,
            coder_id=self.coder_id,
            source_evidence_hash=source_hash,
            prompt_hash=combined_prompt_hash,
            discovered_subtopics=consolidated_subtopics,
            chunked=True,
            chunk_boundaries=chunk_boundaries,
            total_llm_calls=llm_calls,
            minority_positions_preserved=minority_keys,
        )


class SubtopicExtractor:
    """Phase 2 participant-level extractor preserving missingness, response status, and repair audit."""

    def __init__(
        self,
        coder_id: Literal["coder_a", "coder_b"] = "coder_a",
        run_id: str = "run_20261111_002",
        dataset_fingerprint: str = "56acded3e02be49be27d6b288fa2c43fcce68df24525113eba1b1161eec52a95",
        wal_path: Optional[Path] = None,
        model_adapter_tag: str = "default",
    ):
        self.coder_id = coder_id
        self.run_id = run_id
        self.dataset_fingerprint = dataset_fingerprint
        self.prompt_builder = PromptBuilder(coder_id=coder_id, model_adapter_tag=model_adapter_tag)
        self.span_extractor = EvidenceSpanExtractor(run_id=run_id, dataset_fingerprint=dataset_fingerprint)
        self.value_extractor = ValueExtractor(run_id=run_id, dataset_fingerprint=dataset_fingerprint)
        self.wal_path = wal_path

    def _append_wal(self, record: Dict[str, Any]) -> None:
        """Append-only write-ahead log for incremental checkpointing."""
        if self.wal_path:
            self.wal_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.wal_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def process_response_detailed(
        self,
        participant_id: str,
        question_id: str,
        question_index: int,
        canonical_prompt_en: str,
        raw_response: Optional[str],
        detected_language: Literal["fr", "de", "en"] = "fr",
        analytical_frame: str | AnalyticalFrameType = AnalyticalFrameType.GOVERNANCE_GOODS_ALLOCATION,
        economic_good_policy: Literal["ENABLED", "CONDITIONAL", "DISABLED"] = "ENABLED",
        llm_callable: Optional[Callable[[str, str], str]] = None,
        preparsed_output: Optional[LLMQuestionCodingResponse | Dict[str, Any]] = None,
        response_id: str = "",
        agent01_missingness: Optional[MissingnessState | str] = None,
        agent01_response_status: Optional[ResponseStatusLabel | str] = None,
        discovered_subtopics: Optional[List[LLMDiscoveredSubtopic]] = None,
        allow_ambiguous_quotes: bool = False,
        agent01_text_supplied: Optional[bool] = None,
        agent01_has_usable_preference: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Process one participant response with full epistemic-status, repair, and value support."""
        m_state, resp_status = classify_response_status(
            raw_response,
            agent01_missingness=agent01_missingness,
            agent01_response_status=agent01_response_status,
            question_id=question_id,
            text_supplied=agent01_text_supplied,
            has_usable_preference=agent01_has_usable_preference,
        )

        # Truly blank, punctuation-only, or Q14 no-additional-remarks placeholder receives ZERO coding
        if resp_status in BLANK_OR_NON_REPORTABLE_STATUSES or not raw_response or not raw_response.strip():
            return {
                "evidence_spans": [],
                "uncertainty_spans": [],
                "candidates": [],
                "values": [],
                "missingness_state": m_state,
                "response_status": resp_status,
                "has_observed_statement": False,
                "has_usable_preference": False,
                "probability_repairs": [],
                "unmentioned_subtopic_keys": [],
                "prompt_hash": "",
            }

        user_prompt, prompt_hash = self.prompt_builder.build_user_prompt(
            participant_id=participant_id,
            question_id=question_id,
            question_index=question_index,
            canonical_prompt_en=canonical_prompt_en,
            raw_response=raw_response,
            analytical_frame=analytical_frame,
            economic_good_policy=economic_good_policy,
            response_id=response_id,
            missingness_state=m_state.value,
            response_status=resp_status.value,
            discovered_subtopics=discovered_subtopics,
        )

        json_repairs: List[str] = []
        if preparsed_output is not None:
            if isinstance(preparsed_output, LLMQuestionCodingResponse):
                parsed = preparsed_output
            else:
                parsed = LLMQuestionCodingResponse.model_validate(preparsed_output)
        elif llm_callable is not None:
            raw_llm_text = llm_callable(self.prompt_builder.system_prompt, user_prompt)
            data_dict, json_repairs = repair_json_string_with_audit(raw_llm_text)
            parsed = LLMQuestionCodingResponse.model_validate(data_dict)
        elif resp_status in REPORTABLE_NO_PREFERENCE_STATUSES or resp_status == ResponseEpistemicStatus.AMBIGUOUS:
            # Deterministic reportable preservation without requiring an LLM call
            reportable_spans = self.span_extractor.extract_spans(
                participant_id=participant_id,
                question_id=question_id,
                raw_text=raw_response,
                detected_language=detected_language,
                quotes_or_spans=[
                    LLMEvidenceSpan(
                        verbatim_quote=raw_response.strip(),
                        detected_language=detected_language,
                        span_role="explicit_uncertainty_or_no_opinion",
                    )
                ],
                config_hash=prompt_hash,
                missingness_state=m_state,
                allow_ambiguous=True,
                allow_non_preference_spans=True,
            )
            return {
                "evidence_spans": reportable_spans,
                "uncertainty_spans": reportable_spans,
                "candidates": [],
                "values": [],
                "missingness_state": m_state,
                "response_status": resp_status,
                "has_observed_statement": bool(reportable_spans),
                "has_usable_preference": False,
                "probability_repairs": [],
                "unmentioned_subtopic_keys": [st.subtopic_key for st in (discovered_subtopics or [])],
                "prompt_hash": prompt_hash,
            }
        else:
            raise ValueError("Either preparsed_output or llm_callable must be provided for substantive responses.")

        final_status: ResponseEpistemicStatus = parsed.response_status or resp_status

        # Check if coder determined blank/placeholder non-reportable missingness
        if final_status in BLANK_OR_NON_REPORTABLE_STATUSES or (
            not parsed.is_substantive
            and final_status not in REPORTABLE_NO_PREFERENCE_STATUSES
            and final_status != ResponseEpistemicStatus.AMBIGUOUS
        ):
            out_m = (
                MissingnessState(parsed.missingness_state)
                if parsed.missingness_state in {e.value for e in MissingnessState}
                else MissingnessState.MISSING_NON_SUBSTANTIVE
            )
            return {
                "evidence_spans": [],
                "uncertainty_spans": [],
                "candidates": [],
                "values": [],
                "missingness_state": out_m,
                "response_status": final_status,
                "has_observed_statement": False,
                "has_usable_preference": False,
                "probability_repairs": [],
                "unmentioned_subtopic_keys": [],
                "prompt_hash": prompt_hash,
            }

        is_reportable_non_pref = (
            final_status in REPORTABLE_NO_PREFERENCE_STATUSES
            or final_status == ResponseEpistemicStatus.AMBIGUOUS
        )
        span_m_state = (
            (
                MissingnessState.AMBIGUOUS
                if final_status == ResponseEpistemicStatus.AMBIGUOUS
                else (m_state if not m_state.is_usable() else MissingnessState.MISSING_NON_SUBSTANTIVE)
            )
            if is_reportable_non_pref
            else MissingnessState.OBSERVED_USABLE
        )

        # Extract verified EvidenceSpans (allowing non-preference spans for reportable statuses)
        evidence_spans = self.span_extractor.extract_spans(
            participant_id=participant_id,
            question_id=question_id,
            raw_text=raw_response,
            detected_language=parsed.detected_language or detected_language,
            quotes_or_spans=parsed.evidence_spans,
            config_hash=prompt_hash,
            missingness_state=span_m_state,
            allow_ambiguous=allow_ambiguous_quotes,
            allow_non_preference_spans=is_reportable_non_pref,
            default_span_role=(
                "explicit_uncertainty_or_no_opinion" if is_reportable_non_pref else "substantive_evidence"
            ),
        )
        uncertainty_spans = self.span_extractor.extract_spans(
            participant_id=participant_id,
            question_id=question_id,
            raw_text=raw_response,
            detected_language=parsed.detected_language or detected_language,
            quotes_or_spans=parsed.uncertainty_statements,
            config_hash=prompt_hash,
            missingness_state=span_m_state,
            allow_ambiguous=allow_ambiguous_quotes,
            allow_non_preference_spans=True,
            default_span_role="explicit_uncertainty_or_no_opinion",
        )

        # Reportable non-preference statuses and unresolved ambiguous answers emit NO fabricated preferences!
        if is_reportable_non_pref:
            if not evidence_spans and not uncertainty_spans:
                uncertainty_spans = self.span_extractor.extract_spans(
                    participant_id=participant_id,
                    question_id=question_id,
                    raw_text=raw_response,
                    detected_language=parsed.detected_language or detected_language,
                    quotes_or_spans=[
                        LLMEvidenceSpan(
                            verbatim_quote=raw_response.strip(),
                            detected_language=parsed.detected_language or detected_language,
                            span_role="explicit_uncertainty_or_no_opinion",
                        )
                    ],
                    config_hash=prompt_hash,
                    missingness_state=span_m_state,
                    allow_ambiguous=True,
                    allow_non_preference_spans=True,
                )
            all_reportable_spans = evidence_spans + [
                u for u in uncertainty_spans if u.span_id not in {e.span_id for e in evidence_spans}
            ]
            return {
                "evidence_spans": all_reportable_spans,
                "uncertainty_spans": uncertainty_spans,
                "candidates": [],
                "values": [],
                "missingness_state": span_m_state,
                "response_status": final_status,
                "has_observed_statement": bool(all_reportable_spans),
                "has_usable_preference": False,
                "probability_repairs": [],
                "unmentioned_subtopic_keys": [st.subtopic_key for st in (discovered_subtopics or [])],
                "prompt_hash": prompt_hash,
            }

        all_spans_by_quote = {s.verbatim_quote: s.span_id for s in evidence_spans}
        span_ids = [s.span_id for s in evidence_spans]
        all_repairs: List[ProbabilityRepairRecord] = []
        candidates: List[SubtopicCandidate] = []

        for s_idx, st in enumerate(parsed.subtopics):
            label = st.proposed_label_en.strip() or f"Subtopic_{question_id}_{s_idx + 1}"

            # Repair-safe probability simplex validation with audit logging
            repaired_dist, repair_rec = validate_and_repair_probabilities(
                st.candidate_alternative_distribution,
                tolerance=1e-4,
            )
            if repair_rec is not None:
                all_repairs.append(repair_rec)

            # Subtopic-level selective goods assessment (evidence overrides question prior)
            enforced_list = enforce_economic_goods_policy(
                [st.model_dump()],
                policy=economic_good_policy,
            )
            enforced_st = enforced_list[0]
            good_class_str = enforced_st.get("proposed_economic_good_class")
            good_class: Optional[EconomicGoodClass] = None
            if good_class_str and good_class_str != "NOT_APPLICABLE":
                try:
                    good_class = EconomicGoodClass(good_class_str.lower())
                except ValueError:
                    good_class = None

            # Never impose 1D scalar ordering across the 4 economic goods categories
            scalar_stance = st.derived_scalar_stance
            if good_class is not None and len(repaired_dist) > 1 and scalar_stance is not None:
                # Clear invalid scalar collapse over non-ordered economic goods unless explicitly non-goods ordered
                if st.goods_assessment and len(st.goods_assessment.alternative_good_classes) > 1:
                    scalar_stance = None

            # Match specific evidence spans for this candidate if evidence_quotes given
            cand_span_ids: List[str] = []
            for q in st.evidence_quotes:
                if q in all_spans_by_quote:
                    cand_span_ids.append(all_spans_by_quote[q])
                else:
                    # Extract verified span for candidate quote if not already in top-level evidence_spans
                    new_sp = self.span_extractor.extract_spans(
                        participant_id=participant_id,
                        question_id=question_id,
                        raw_text=raw_response,
                        detected_language=parsed.detected_language or detected_language,
                        quotes_or_spans=[q],
                        config_hash=prompt_hash,
                        missingness_state=MissingnessState.OBSERVED_USABLE,
                        allow_ambiguous=allow_ambiguous_quotes,
                    )
                    for sp in new_sp:
                        if sp.span_id not in span_ids:
                            evidence_spans.append(sp)
                            span_ids.append(sp.span_id)
                        all_spans_by_quote[sp.verbatim_quote] = sp.span_id
                        cand_span_ids.append(sp.span_id)
            if not cand_span_ids:
                cand_span_ids = list(span_ids)

            cand_key = f"{self.run_id}_{question_id}_{participant_id}_{self.coder_id}_{s_idx}_{label}"
            cand_hash = hashlib.sha256(cand_key.encode("utf-8")).hexdigest()[:12]
            candidate_id = f"CAND_{question_id}_{cand_hash}"

            provenance = ProvenanceMeta(
                record_id=cand_hash,
                run_id=self.run_id,
                dataset_fingerprint=self.dataset_fingerprint,
                created_at_utc=datetime.now(timezone.utc).isoformat(),
                producer_module="src/nlp/subtopic_extraction.py",
                producer_agent="agent_02",
                upstream_artifact_ids=cand_span_ids,
                config_hash=prompt_hash,
                schema_version=SCHEMA_VERSION,
            )

            cand = SubtopicCandidate(
                candidate_id=candidate_id,
                question_id=question_id,
                participant_id=participant_id,
                coder_id=self.coder_id,
                evidence_span_ids=cand_span_ids,
                proposed_label_en=label,
                proposed_description=st.proposed_description,
                candidate_alternative_distribution=repaired_dist,
                semantic_importance=st.semantic_importance,
                coder_confidence=st.coder_confidence,
                missingness_state=MissingnessState.OBSERVED_USABLE,
                provenance=provenance,
                proposed_economic_good_class=good_class,
                proposed_alternative_frame_label=st.proposed_alternative_frame_label,
                native_language_keywords=st.native_language_keywords,
                derived_scalar_stance=scalar_stance,
                schema_version=SCHEMA_VERSION,
            )
            candidates.append(cand)

        # Stage A open value extraction
        stage_a_values: List[LLMValueExtraction] = []
        for val_raw in parsed.values:
            val_span_ids = []
            for q in val_raw.evidence_quotes:
                if q in all_spans_by_quote:
                    val_span_ids.append(all_spans_by_quote[q])
            if not val_span_ids:
                val_span_ids = list(span_ids)
            extracted_val = self.value_extractor.extract_stage_a_value(
                participant_id=participant_id,
                question_id=question_id,
                raw_value=val_raw,
                supporting_span_ids=val_span_ids,
                coder_id=self.coder_id,
                response_id=response_id or parsed.response_id,
            )
            stage_a_values.append(extracted_val)

        self._append_wal({
            "participant_id": participant_id,
            "question_id": question_id,
            "response_id": response_id or parsed.response_id,
            "coder_id": self.coder_id,
            "response_status": final_status.value,
            "span_count": len(evidence_spans),
            "uncertainty_span_count": len(uncertainty_spans),
            "candidate_count": len(candidates),
            "value_count": len(stage_a_values),
            "json_repairs": json_repairs,
            "prompt_hash": prompt_hash,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        return {
            "evidence_spans": evidence_spans,
            "uncertainty_spans": uncertainty_spans,
            "candidates": candidates,
            "values": stage_a_values,
            "missingness_state": MissingnessState.OBSERVED_USABLE,
            "response_status": final_status,
            "has_observed_statement": True,
            "has_usable_preference": True,
            "probability_repairs": all_repairs,
            "unmentioned_subtopic_keys": list(parsed.unmentioned_subtopic_keys),
            "prompt_hash": prompt_hash,
            "parsed_subtopics": parsed.subtopics,
        }

    def process_response(
        self,
        participant_id: str,
        question_id: str,
        question_index: int,
        canonical_prompt_en: str,
        raw_response: Optional[str],
        detected_language: Literal["fr", "de", "en"] = "fr",
        analytical_frame: str | AnalyticalFrameType = AnalyticalFrameType.GOVERNANCE_GOODS_ALLOCATION,
        economic_good_policy: Literal["ENABLED", "CONDITIONAL", "DISABLED"] = "ENABLED",
        llm_callable: Optional[Callable[[str, str], str]] = None,
        preparsed_output: Optional[LLMQuestionCodingResponse | Dict[str, Any]] = None,
    ) -> Tuple[List[EvidenceSpan], List[SubtopicCandidate], MissingnessState]:
        """Backward-compatible single-response entry point returning (spans, candidates, missingness)."""
        res = self.process_response_detailed(
            participant_id=participant_id,
            question_id=question_id,
            question_index=question_index,
            canonical_prompt_en=canonical_prompt_en,
            raw_response=raw_response,
            detected_language=detected_language,
            analytical_frame=analytical_frame,
            economic_good_policy=economic_good_policy,
            llm_callable=llm_callable,
            preparsed_output=preparsed_output,
        )
        return res["evidence_spans"], res["candidates"], res["missingness_state"]


class CanonicalSubtopicSynthesizer:
    """Synthesizes CanonicalSubtopic records using structured semantic matching (not Jaccard alone)."""

    def __init__(
        self,
        run_id: str = "run_20261111_002",
        dataset_fingerprint: str = "56acded3e02be49be27d6b288fa2c43fcce68df24525113eba1b1161eec52a95",
        matcher: Optional[SubtopicMatcher] = None,
    ):
        self.run_id = run_id
        self.dataset_fingerprint = dataset_fingerprint
        self.matcher = matcher or SubtopicMatcher()

    def synthesize_with_matching_audit(
        self,
        question_id: str,
        candidates: List[SubtopicCandidate],
        all_participant_ids: List[str],
        observed_participant_ids: Set[str],
        economic_good_policy: Literal["ENABLED", "CONDITIONAL", "DISABLED"] = "ENABLED",
        candidate_metadata: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Tuple[List[CanonicalSubtopic], List[SubtopicMatchProposal]]:
        """Synthesize CanonicalSubtopic records via structured matching and preserve uncertain matches.

        Enforces:
        - Structured matching over definition, evidence, decision_object, mechanism, and scope.
        - Opposing positions on the SAME topic merge into one CanonicalSubtopic containing all
          competing alternatives rather than splitting or overwriting.
        - Uncertain matches are preserved in SubtopicMatchProposal records for Agent 03.
        - Exact partitioning: total_participants = mention + unmentioned + missing_question.
        """
        all_participants_set = set(all_participant_ids)
        missing_question_ids = all_participants_set - observed_participant_ids
        missing_count = len(missing_question_ids)

        if not candidates:
            return [], []

        meta_map = candidate_metadata or {}
        descriptors: List[SubtopicDescriptor] = []
        cand_by_id: Dict[str, SubtopicCandidate] = {}
        for c in candidates:
            cand_by_id[c.candidate_id] = c
            extra = meta_map.get(c.candidate_id, {})
            descriptors.append(
                SubtopicDescriptor(
                    item_id=c.candidate_id,
                    question_id=c.question_id,
                    label=c.proposed_label_en,
                    definition=c.proposed_description,
                    decision_object=extra.get("decision_object", c.proposed_label_en),
                    mechanism=extra.get("mechanism", ""),
                    scope=extra.get("scope", ""),
                    alternatives=list(c.candidate_alternative_distribution.keys()),
                    evidence_ids=c.evidence_span_ids,
                    response_ids=extra.get("response_ids", []),
                    coder_id=c.coder_id,
                )
            )

        merged_groups, match_proposals = self.matcher.cluster_subtopics(descriptors)
        canonical_list: List[CanonicalSubtopic] = []

        for idx, grp_descs in enumerate(merged_groups):
            group_cands = [cand_by_id[d.item_id] for d in grp_descs]
            subtopic_id = f"SUB_{question_id}_{idx + 1:02d}"

            group_cands_sorted = sorted(group_cands, key=lambda c: len(c.proposed_description), reverse=True)
            rep_label = group_cands_sorted[0].proposed_label_en
            rep_desc = group_cands_sorted[0].proposed_description

            source_cand_ids = [c.candidate_id for c in group_cands]
            supporting_spans = sorted({s for c in group_cands for s in c.evidence_span_ids})

            mention_participants = {c.participant_id for c in group_cands}
            mention_count = len(mention_participants)
            unmentioned_participants = observed_participant_ids - mention_participants
            unmentioned_count = len(unmentioned_participants)

            assert mention_count + unmentioned_count + missing_count == len(all_participants_set), (
                f"Partition invariant failed: {mention_count} + {unmentioned_count} + {missing_count} != {len(all_participants_set)}"
            )

            coder_a_cands = [c for c in group_cands if c.coder_id == "coder_a"]
            coder_b_cands = [c for c in group_cands if c.coder_id == "coder_b"]
            if coder_a_cands and coder_b_cands:
                coder_agreement = 1.0
            elif coder_a_cands or coder_b_cands:
                coder_agreement = 0.5
            else:
                coder_agreement = 0.0

            mean_conf = sum(c.coder_confidence for c in group_cands) / len(group_cands)

            # Subtopic-level economic good classification: evidence overrides question-level guidance
            goods = [
                c.proposed_economic_good_class
                for c in group_cands
                if c.proposed_economic_good_class is not None
                and c.proposed_economic_good_class != EconomicGoodClass.NOT_APPLICABLE
            ]
            if goods:
                applicability: Literal["APPLIED", "NOT_APPLICABLE_FRAME", "MIXED_CONTESTED"] = (
                    "APPLIED" if len(set(goods)) == 1 else "MIXED_CONTESTED"
                )
                dominant_good = max(set(goods), key=goods.count)
            else:
                applicability = "NOT_APPLICABLE_FRAME"
                dominant_good = None

            feas_alts: Set[str] = set()
            for c in group_cands:
                feas_alts.update(c.candidate_alternative_distribution.keys())

            prov_hash = hashlib.sha256(f"{self.run_id}_{subtopic_id}_{idx}".encode("utf-8")).hexdigest()[:12]
            provenance = ProvenanceMeta(
                record_id=prov_hash,
                run_id=self.run_id,
                dataset_fingerprint=self.dataset_fingerprint,
                created_at_utc=datetime.now(timezone.utc).isoformat(),
                producer_module="src/nlp/subtopic_extraction.py",
                producer_agent="agent_02",
                upstream_artifact_ids=source_cand_ids,
                schema_version=SCHEMA_VERSION,
            )

            canonical = CanonicalSubtopic(
                subtopic_id=subtopic_id,
                question_id=question_id,
                canonical_label_en=rep_label,
                canonical_description=rep_desc,
                source_candidate_ids=source_cand_ids,
                supporting_span_ids=supporting_spans,
                mention_participant_count=mention_count,
                unmentioned_participant_count=unmentioned_count,
                missing_question_participant_count=missing_count,
                economic_good_applicability=applicability,
                coder_agreement=coder_agreement,
                mean_coder_confidence=round(mean_conf, 3),
                provenance=provenance,
                dominant_economic_good_class=dominant_good,
                feasible_alternatives=sorted(feas_alts),
                has_defensible_ordering=False,  # Never impose 1D ordering on goods categories
                schema_version=SCHEMA_VERSION,
            )
            canonical_list.append(canonical)

        return canonical_list, match_proposals

    def synthesize_canonical_subtopics(
        self,
        question_id: str,
        candidates: List[SubtopicCandidate],
        all_participant_ids: List[str],
        observed_participant_ids: Set[str],
        economic_good_policy: Literal["ENABLED", "CONDITIONAL", "DISABLED"] = "ENABLED",
    ) -> List[CanonicalSubtopic]:
        """Backward-compatible wrapper returning synthesized CanonicalSubtopics."""
        canonical_list, _ = self.synthesize_with_matching_audit(
            question_id=question_id,
            candidates=candidates,
            all_participant_ids=all_participant_ids,
            observed_participant_ids=observed_participant_ids,
            economic_good_policy=economic_good_policy,
        )
        return canonical_list


class QuestionCorpusCoder:
    """Canonical Agent 02 qualitative coding entry point.

    Executes:
    1. Equivalent source evidence hashing (shared by Coder A and Coder B) vs. separate prompt hashes.
    2. Phase 1 complete question-corpus discovery (with chunk-and-consolidate when needed).
    3. Phase 2 participant-level coding, exact span extraction, response-status preservation,
       and Stage A free-form value extraction.
    4. Stage B cross-question value consolidation proposals (reconciliation deferred to Agent 03).
    5. Structured subtopic matching & CanonicalSubtopic synthesis (uncertain matches deferred to Agent 03).
    """

    def __init__(
        self,
        run_id: str = "run_20261111_002",
        dataset_fingerprint: str = "56acded3e02be49be27d6b288fa2c43fcce68df24525113eba1b1161eec52a95",
        max_corpus_chars: int = 24000,
        max_responses_per_chunk: int = 40,
        matcher: Optional[SubtopicMatcher] = None,
    ):
        self.run_id = run_id
        self.dataset_fingerprint = dataset_fingerprint
        self.discovery_a = QuestionCorpusDiscoveryEngine(
            coder_id="coder_a",
            model_adapter_tag="coder_a_model",
            max_corpus_chars=max_corpus_chars,
            max_responses_per_chunk=max_responses_per_chunk,
        )
        self.discovery_b = QuestionCorpusDiscoveryEngine(
            coder_id="coder_b",
            model_adapter_tag="coder_b_model",
            max_corpus_chars=max_corpus_chars,
            max_responses_per_chunk=max_responses_per_chunk,
        )
        self.coder_a = SubtopicExtractor(
            coder_id="coder_a",
            run_id=run_id,
            dataset_fingerprint=dataset_fingerprint,
            model_adapter_tag="coder_a_model",
        )
        self.coder_b = SubtopicExtractor(
            coder_id="coder_b",
            run_id=run_id,
            dataset_fingerprint=dataset_fingerprint,
            model_adapter_tag="coder_b_model",
        )
        self.value_extractor = ValueExtractor(run_id=run_id, dataset_fingerprint=dataset_fingerprint)
        self.synthesizer = CanonicalSubtopicSynthesizer(
            run_id=run_id,
            dataset_fingerprint=dataset_fingerprint,
            matcher=matcher,
        )

    def code_question_corpus(
        self,
        corpus: QuestionCorpusInput,
        coder_a_discovery_fn: Callable[[str, str], Any],
        coder_b_discovery_fn: Callable[[str, str], Any],
        coder_a_assign_fn: Callable[[NormalizedResponseInput, DiscoveredQuestionTaxonomy, str, str], Any],
        coder_b_assign_fn: Callable[[NormalizedResponseInput, DiscoveredQuestionTaxonomy, str, str], Any],
        coder_a_consolidation_fn: Optional[Callable[[str, str], Any]] = None,
        coder_b_consolidation_fn: Optional[Callable[[str, str], Any]] = None,
    ) -> Dict[str, Any]:
        """Execute full two-phase independent dual-LLM qualitative coding for a complete question corpus."""
        # 1. Verify equivalent source evidence for Coder A and Coder B (separate from model prompt hashes)
        source_hash = compute_source_evidence_hash(corpus)
        corpus_a = corpus.model_copy(update={"source_evidence_hash": source_hash})
        corpus_b = corpus.model_copy(update={"source_evidence_hash": source_hash})

        # 2. Phase 1 Independent Question-Corpus Discovery
        tax_a = self.discovery_a.discover_question_taxonomy(
            corpus_a,
            discovery_callable=coder_a_discovery_fn,
            consolidation_callable=coder_a_consolidation_fn,
        )
        tax_b = self.discovery_b.discover_question_taxonomy(
            corpus_b,
            discovery_callable=coder_b_discovery_fn,
            consolidation_callable=coder_b_consolidation_fn,
        )
        assert tax_a.source_evidence_hash == tax_b.source_evidence_hash == source_hash

        # 3. Phase 2 Independent Participant-Level Assignment & Stage A Value Extraction
        all_participants = [r.participant_id for r in corpus.responses]
        observed_participants: Set[str] = set()
        observed_statement_participants: Set[str] = set()
        all_spans: List[EvidenceSpan] = []
        all_uncertainty_spans: List[EvidenceSpan] = []
        all_candidates: List[SubtopicCandidate] = []
        candidate_metadata: Dict[str, Dict[str, Any]] = {}
        stage_a_values: List[LLMValueExtraction] = []
        all_repairs: List[ProbabilityRepairRecord] = []
        response_status_counts: Dict[str, int] = {}
        coder_a_prompt_hashes: List[str] = [tax_a.prompt_hash]
        coder_b_prompt_hashes: List[str] = [tax_b.prompt_hash]

        for resp in corpus.responses:
            m_state, status_label = classify_response_status(
                resp.raw_value,
                agent01_missingness=resp.missingness_state,
                agent01_response_status=resp.epistemic_status or resp.response_status,
                question_id=corpus.question_id,
                text_supplied=resp.text_supplied,
                has_usable_preference=resp.has_usable_preference,
            )
            response_status_counts[status_label.value] = (
                response_status_counts.get(status_label.value, 0) + 1
            )

            if (
                status_label in BLANK_OR_NON_REPORTABLE_STATUSES
                or not resp.raw_value
                or not resp.raw_value.strip()
            ):
                continue

            observed_statement_participants.add(resp.participant_id)

            # Build isolated prompt per coder using ONLY that coder's Phase 1 taxonomy
            for coder_tag, extractor, tax, assign_fn, prompt_hash_list in [
                ("coder_a", self.coder_a, tax_a, coder_a_assign_fn, coder_a_prompt_hashes),
                ("coder_b", self.coder_b, tax_b, coder_b_assign_fn, coder_b_prompt_hashes),
            ]:
                u_prompt, p_hash = extractor.prompt_builder.build_user_prompt(
                    participant_id=resp.participant_id,
                    question_id=corpus.question_id,
                    question_index=corpus.question_index,
                    canonical_prompt_en=corpus.canonical_prompt_en,
                    raw_response=resp.raw_value,
                    analytical_frame=corpus.analytical_frame,
                    economic_good_policy=corpus.economic_good_classification_policy,
                    prompt_fr=corpus.exact_question_wording.get("fr"),
                    prompt_de=corpus.exact_question_wording.get("de"),
                    response_id=resp.response_id,
                    missingness_state=m_state.value,
                    response_status=status_label.value,
                    discovered_subtopics=tax.discovered_subtopics,
                )
                assert_coder_input_isolation(u_prompt, coder_tag)
                prompt_hash_list.append(p_hash)

                raw_assign = assign_fn(resp, tax, extractor.prompt_builder.system_prompt, u_prompt)
                if isinstance(raw_assign, str):
                    parsed_dict, _ = repair_json_string_with_audit(raw_assign)
                    preparsed = parsed_dict
                else:
                    preparsed = raw_assign

                res = extractor.process_response_detailed(
                    participant_id=resp.participant_id,
                    question_id=corpus.question_id,
                    question_index=corpus.question_index,
                    canonical_prompt_en=corpus.canonical_prompt_en,
                    raw_response=resp.raw_value,
                    detected_language=resp.detected_language,
                    analytical_frame=corpus.analytical_frame,
                    economic_good_policy=corpus.economic_good_classification_policy,
                    preparsed_output=preparsed,
                    response_id=resp.response_id,
                    agent01_missingness=m_state,
                    agent01_response_status=status_label,
                    discovered_subtopics=tax.discovered_subtopics,
                    agent01_text_supplied=resp.text_supplied,
                    agent01_has_usable_preference=resp.has_usable_preference,
                )

                if res["missingness_state"].is_usable() or res["candidates"]:
                    observed_participants.add(resp.participant_id)

                all_spans.extend(res["evidence_spans"])
                all_uncertainty_spans.extend(res["uncertainty_spans"])
                all_candidates.extend(res["candidates"])
                stage_a_values.extend(res["values"])
                all_repairs.extend(res["probability_repairs"])

                parsed_sts = res.get("parsed_subtopics", [])
                for cand, pst in zip(res["candidates"], parsed_sts):
                    candidate_metadata[cand.candidate_id] = {
                        "decision_object": pst.decision_object or cand.proposed_label_en,
                        "mechanism": pst.mechanism,
                        "scope": pst.scope,
                        "response_ids": [resp.response_id],
                    }

        # 4. Structured Subtopic Matching & Synthesis (preserving uncertain matches for Agent 03)
        canonical_subtopics, match_proposals = self.synthesizer.synthesize_with_matching_audit(
            question_id=corpus.question_id,
            candidates=all_candidates,
            all_participant_ids=all_participants,
            observed_participant_ids=observed_participants,
            economic_good_policy=corpus.economic_good_classification_policy,
            candidate_metadata=candidate_metadata,
        )

        # 5. Stage B Cross-Question Consolidation Proposals (for Agent 03 reconciliation)
        value_proposals = self.value_extractor.propose_cross_question_consolidation(stage_a_values)

        return {
            "question_id": corpus.question_id,
            "source_evidence_hash": source_hash,
            "coder_a_prompt_hash": compute_prompt_hash("|".join(coder_a_prompt_hashes)),
            "coder_b_prompt_hash": compute_prompt_hash("|".join(coder_b_prompt_hashes)),
            "taxonomy_coder_a": tax_a,
            "taxonomy_coder_b": tax_b,
            "evidence_spans": all_spans,
            "uncertainty_spans": all_uncertainty_spans,
            "subtopic_candidates": all_candidates,
            "canonical_subtopics": canonical_subtopics,
            "subtopic_match_proposals": match_proposals,
            "value_stage_a_extractions": stage_a_values,
            "value_stage_b_proposals": value_proposals,
            "probability_repairs": all_repairs,
            "response_status_counts": response_status_counts,
            "observed_preference_participants": sorted(observed_participants),
            "observed_statement_participants": sorted(observed_statement_participants),
        }


class DualCoderRunner:
    """Backward-compatible dual-coder orchestrator (delegates to QuestionCorpusCoder for full corpus runs)."""

    def __init__(
        self,
        run_id: str = "run_20261111_002",
        dataset_fingerprint: str = "56acded3e02be49be27d6b288fa2c43fcce68df24525113eba1b1161eec52a95",
    ):
        self.run_id = run_id
        self.dataset_fingerprint = dataset_fingerprint
        self.coder_a = SubtopicExtractor(coder_id="coder_a", run_id=run_id, dataset_fingerprint=dataset_fingerprint)
        self.coder_b = SubtopicExtractor(coder_id="coder_b", run_id=run_id, dataset_fingerprint=dataset_fingerprint)
        self.synthesizer = CanonicalSubtopicSynthesizer(run_id=run_id, dataset_fingerprint=dataset_fingerprint)

    def run_dual_coding_for_question(
        self,
        question_id: str,
        question_index: int,
        canonical_prompt_en: str,
        responses_by_participant: Dict[str, Optional[str]],
        languages_by_participant: Dict[str, Literal["fr", "de", "en"]],
        coder_a_mock: Callable[[str, str], Dict[str, Any]],
        coder_b_mock: Callable[[str, str], Dict[str, Any]],
        analytical_frame: str | AnalyticalFrameType = AnalyticalFrameType.GOVERNANCE_GOODS_ALLOCATION,
        economic_good_policy: Literal["ENABLED", "CONDITIONAL", "DISABLED"] = "ENABLED",
    ) -> Tuple[List[EvidenceSpan], List[SubtopicCandidate], List[CanonicalSubtopic]]:
        """Execute concurrent coding for both coders and synthesize canonical subtopics."""
        all_participants = list(responses_by_participant.keys())
        observed_participants: Set[str] = set()

        all_spans: List[EvidenceSpan] = []
        all_candidates: List[SubtopicCandidate] = []

        for p_id in all_participants:
            raw_text = responses_by_participant.get(p_id)
            lang = languages_by_participant.get(p_id, "fr")

            is_missing, _ = is_non_substantive_response(raw_text)
            if not is_missing and raw_text:
                observed_participants.add(p_id)

                out_a = coder_a_mock(p_id, raw_text)
                spans_a, cands_a, _ = self.coder_a.process_response(
                    participant_id=p_id,
                    question_id=question_id,
                    question_index=question_index,
                    canonical_prompt_en=canonical_prompt_en,
                    raw_response=raw_text,
                    detected_language=lang,
                    analytical_frame=analytical_frame,
                    economic_good_policy=economic_good_policy,
                    preparsed_output=out_a,
                )
                all_spans.extend(spans_a)
                all_candidates.extend(cands_a)

                out_b = coder_b_mock(p_id, raw_text)
                spans_b, cands_b, _ = self.coder_b.process_response(
                    participant_id=p_id,
                    question_id=question_id,
                    question_index=question_index,
                    canonical_prompt_en=canonical_prompt_en,
                    raw_response=raw_text,
                    detected_language=lang,
                    analytical_frame=analytical_frame,
                    economic_good_policy=economic_good_policy,
                    preparsed_output=out_b,
                )
                all_spans.extend(spans_b)
                all_candidates.extend(cands_b)

        canonical_subtopics = self.synthesizer.synthesize_canonical_subtopics(
            question_id=question_id,
            candidates=all_candidates,
            all_participant_ids=all_participants,
            observed_participant_ids=observed_participants,
            economic_good_policy=economic_good_policy,
        )

        return all_spans, all_candidates, canonical_subtopics
