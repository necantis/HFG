"""Orchestration & QA Gate Layer for HFG (Agent 11).

Owned by: Agent 11 — Orchestration & QA (`src/pipeline/`, `src/orchestrator.py`)
Architecture Version: v1.1.0
Active Run ID: run_20261111_002
"""

from src.pipeline.orchestrator import (
    Agent03ReleaseDecision,
    CoderExecutionSummary,
    DualCoderValidationReport,
    PipelineEvaluationReport,
    PipelineState,
    PipelineOrchestrator,
    evaluate_pipeline_state,
    validate_dual_coder_outputs,
)

__all__ = [
    "Agent03ReleaseDecision",
    "CoderExecutionSummary",
    "DualCoderValidationReport",
    "PipelineEvaluationReport",
    "PipelineState",
    "PipelineOrchestrator",
    "evaluate_pipeline_state",
    "validate_dual_coder_outputs",
]
