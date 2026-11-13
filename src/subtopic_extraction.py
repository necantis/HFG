"""Top-level re-export for subtopic_extraction module.

Points to src.nlp.subtopic_extraction.
Owned by: Agent 02 — Qualitative Coding
"""

from src.nlp.subtopic_extraction import (
    EvidenceSpanExtractor,
    QuestionCorpusDiscoveryEngine,
    QuestionCorpusCoder,
    SubtopicExtractor,
    CanonicalSubtopicSynthesizer,
    DualCoderRunner,
)

__all__ = [
    "EvidenceSpanExtractor",
    "QuestionCorpusDiscoveryEngine",
    "QuestionCorpusCoder",
    "SubtopicExtractor",
    "CanonicalSubtopicSynthesizer",
    "DualCoderRunner",
]
