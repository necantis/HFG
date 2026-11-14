"""
Canonical top-level re-export of `src.runtime.model_runtime` for Agent 07 — GPU Runtime.

Supports both `import src.model_runtime` and `from src.runtime import model_runtime`.
"""

from src.runtime.model_runtime import (
    ALTERNATIVE_CODER_B_GEMMA_CANDIDATES,
    ALTERNATIVE_CODER_B_GEMMA_SPEC,
    ALLOWED_CODER_B_FAMILIES,
    ALLOWED_SMOKE_CODER_B_FAMILIES,
    AtomicQuestionCheckpointStore,
    CheckpointMismatchError,
    CodedSpanOutput,
    CoderModelSpec,
    DEFAULT_CODER_A_CANDIDATES,
    DEFAULT_CODER_A_SPEC,
    DEFAULT_CODER_B_MISTRAL_CANDIDATES,
    DEFAULT_CODER_B_MISTRAL_SPEC,
    DEFAULT_RUN_ID,
    DEFAULT_SMOKE_CODER_A_SPEC,
    DEFAULT_SMOKE_CODER_B_SPEC,
    DualCoderRuntimeManager,
    ExecutionMode,
    ExecutionProfile,
    FORBIDDEN_CODER_B_FAMILIES,
    GPURuntimeConfig,
    HardwareProfile,
    LocalCoderServerProcess,
    PINNED_PRODUCTION_CODER_A_REPO,
    PINNED_PRODUCTION_CODER_A_REVISION,
    PINNED_PRODUCTION_CODER_B_REPO,
    PINNED_PRODUCTION_CODER_B_REVISION,
    QuestionCheckpointRecord,
    SchemaStatus,
    StructuredCoderResponse,
    StructuredCodingOutput,
    benchmark_supports_concurrent_mode,
    build_and_save_runtime_config,
    build_profile_runtime_config,
    derive_memory_budget_from_measurements,
    detect_hardware_profile,
    resolve_and_verify_coder_spec,
    resolve_dual_coder_specs,
    run_runtime_benchmark_suite,
    select_safe_execution_mode,
    strip_reasoning_tokens,
    validate_model_family_diversity,
    validate_structured_coding_response,
)

if __name__ == "__main__":
    cfg_out, bench_out, cfg_file = build_and_save_runtime_config()
    print(f"Saved GPU runtime config to: {cfg_file}")
    print(f"Selected Execution Mode: {cfg_out.execution_mode.value}")
