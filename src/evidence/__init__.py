"""Agent 03 — Evidence & Reconciliation Package.

Owned by: Agent 03 — Evidence & Reconciliation
Architecture Version: v1.1.0
"""

from src.evidence.evidence_ledger import (
    CoderInputProvenance,
    EvidenceIntegrityError,
    EvidenceLedger,
    MissingnessLedgerEntry,
    ProvenanceLock,
    ProvenanceVerificationError,
    SpanValidationReport,
    VerifiedSpanRecord,
    compute_char_overlap_metrics,
)
from src.evidence.reconciliation import (
    AlternativeAlignmentInfo,
    EvidenceReconciler,
    PairwiseSubtopicAlignment,
    PreferenceReconciliationRecord,
    ProposedSubtopicRecord,
    ReconciledOrganisationalValue,
    UncertaintyMetadata,
    UnresolvedCaseRecord,
    align_alternative_vocabularies,
)

__all__ = [
    "AlternativeAlignmentInfo",
    "CoderInputProvenance",
    "EvidenceIntegrityError",
    "EvidenceLedger",
    "EvidenceReconciler",
    "MissingnessLedgerEntry",
    "PairwiseSubtopicAlignment",
    "PreferenceReconciliationRecord",
    "ProposedSubtopicRecord",
    "ProvenanceLock",
    "ProvenanceVerificationError",
    "ReconciledOrganisationalValue",
    "SpanValidationReport",
    "UncertaintyMetadata",
    "UnresolvedCaseRecord",
    "VerifiedSpanRecord",
    "align_alternative_vocabularies",
    "compute_char_overlap_metrics",
]
