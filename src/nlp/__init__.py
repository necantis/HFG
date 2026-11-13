"""NLP and Qualitative Coding Package for HFG.

Owned by: Agent 02 — Qualitative Coding
Schema Version: 1.0.0 / v1.1.0
Active Run: run_20261111_002
"""

from src.nlp.schemas import (
    CorpusChunkMetadata,
    DiscoveredQuestionTaxonomy,
    LLMCorpusDiscoveryResponse,
    LLMDiscoveredAlternative,
    LLMDiscoveredSubtopic,
    LLMEvidenceSpan,
    LLMQuestionCodingResponse,
    LLMSubtopicCandidate,
    LLMValueExtraction,
    NormalizedResponseInput,
    ProbabilityInterpretation,
    ProbabilityRepairRecord,
    QuestionCorpusInput,
    ResponseStatusLabel,
    SubtopicGoodsAssessment,
    SubtopicMatchProposal,
    ThemeRecord,
    ThemesCodebook,
    ValueConsolidationProposal,
)
from src.nlp.prompts import (
    PromptBuilder,
    assert_coder_input_isolation,
    compute_prompt_hash,
    compute_source_evidence_hash,
    SYSTEM_PROMPT_QUALITATIVE_CODER,
    BUILD_USER_CODING_PROMPT,
)
from src.nlp.repair import (
    AmbiguousQuoteOffsetError,
    classify_response_status,
    repair_json_string,
    repair_json_string_with_audit,
    validate_and_repair_probabilities,
    validate_and_repair_simplex,
    is_non_substantive_response,
    find_exact_char_offsets,
    enforce_economic_goods_policy,
)
from src.nlp.matching import (
    SubtopicDescriptor,
    SubtopicMatcher,
)
from src.nlp.subtopic_extraction import (
    EvidenceSpanExtractor,
    QuestionCorpusDiscoveryEngine,
    QuestionCorpusCoder,
    SubtopicExtractor,
    CanonicalSubtopicSynthesizer,
    DualCoderRunner,
)
from src.nlp.value_extraction import (
    ValueExtractor,
    EXAMPLE_ORGANISATIONAL_VALUE_ALIASES,
    CANONICAL_ORGANISATIONAL_VALUES,
)
from src.nlp.fixtures import (
    get_multilingual_test_fixtures,
    get_sample_question_specs,
)

__all__ = [
    "CorpusChunkMetadata",
    "DiscoveredQuestionTaxonomy",
    "LLMCorpusDiscoveryResponse",
    "LLMDiscoveredAlternative",
    "LLMDiscoveredSubtopic",
    "LLMEvidenceSpan",
    "LLMQuestionCodingResponse",
    "LLMSubtopicCandidate",
    "LLMValueExtraction",
    "NormalizedResponseInput",
    "ProbabilityInterpretation",
    "ProbabilityRepairRecord",
    "QuestionCorpusInput",
    "ResponseStatusLabel",
    "SubtopicGoodsAssessment",
    "SubtopicMatchProposal",
    "ThemeRecord",
    "ThemesCodebook",
    "ValueConsolidationProposal",
    "PromptBuilder",
    "assert_coder_input_isolation",
    "compute_prompt_hash",
    "compute_source_evidence_hash",
    "SYSTEM_PROMPT_QUALITATIVE_CODER",
    "BUILD_USER_CODING_PROMPT",
    "AmbiguousQuoteOffsetError",
    "classify_response_status",
    "repair_json_string",
    "repair_json_string_with_audit",
    "validate_and_repair_probabilities",
    "validate_and_repair_simplex",
    "is_non_substantive_response",
    "find_exact_char_offsets",
    "enforce_economic_goods_policy",
    "SubtopicDescriptor",
    "SubtopicMatcher",
    "EvidenceSpanExtractor",
    "QuestionCorpusDiscoveryEngine",
    "QuestionCorpusCoder",
    "SubtopicExtractor",
    "CanonicalSubtopicSynthesizer",
    "DualCoderRunner",
    "ValueExtractor",
    "EXAMPLE_ORGANISATIONAL_VALUE_ALIASES",
    "CANONICAL_ORGANISATIONAL_VALUES",
    "get_multilingual_test_fixtures",
    "get_sample_question_specs",
]
