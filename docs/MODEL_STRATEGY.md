# Model Strategy & Inference Governance — HFG

> **Status**: Approved (`v1.1.0` — 12-Agent Architecture)
> **Enforced by**: `src/artifact_registry.py`, `src/review/`, `src/pipeline/`

---

## 1. Model Tier Selection Matrix

To balance computational latency, token economics, and analytical depth, models are assigned strictly by task complexity across the 12 agents:

| Tier | Model Designation | Recommended Agents / Roles | Characteristics & Usage |
| :--- | :--- | :--- | :--- |
| `flash_lite` | Lightweight fast model | Agent 01 (Registry checks), Agent 11 (Pipeline status logging) | Ultra-fast token throughput, minimal latency, low reasoning overhead. |
| `flash` | Fast balanced model | Agent 02 (Theme tagging), Agent 04 (Preference calculation), Agent 06 (Voting aggregations) | High throughput, reliable structured output extraction. |
| `pro` | Advanced reasoning model | Agent 00 (Architecture), Agent 02 (Deep thematic synthesis), Agent 03 (Option synthesis & reconciliation), Agent 08 (Policy brief synthesis), Agent 09 (Independent Integration Review & Red Team) | Deep contextual reasoning, zero-shot nuance, rigorous invariant enforcement. |
| `inherit` | Calling agent model | Default for subagent invocations | Inherits parent session configuration unless overridden by explicit need. |

---

## 2. Configurable Runtime Parameters

1. **GPU Runtime & Memory Allocation (Agent 07)**:
   - GPU memory fractions, device selections, and execution concurrency are **configurable runtime parameters** owned by Agent 07 (`runs/<run_id>/gpu_runtime_config.json`).
   - They are NOT immutable architectural constants.
2. **Robust-Pareto Monte Carlo Sample Counts (Agent 04)**:
   - The number of Monte Carlo iterations for robust-Pareto frontiers is a **configurable runtime parameter** owned by Agent 04 (`runs/<run_id>/pareto_mc_config.json`).
   - It is dynamically calibrated based on respondent sample size and variance.

---

## 3. Determinism & Analytical Reproducibility Controls

1. **Zero Temperature Invariant**: For all analytical extractions, preference reconciliations, and candidate generation, inference requests MUST specify `temperature = 0.0` (or `seed = 42`).
2. **Prompt Versioning & Hashing**:
   - Every system and user prompt template used in production code must be versioned and stored under `prompts/` or embedded in module constants.
   - The Artifact Registry requires recording the SHA-256 hash of the prompt template (`prompt_hash`) whenever an LLM produces or annotates an artifact.
3. **Quantisation Tracking**:
   - The Run Card records whether models were executed via full precision FP16/BF16 or quantised (e.g., INT8/INT4/AWQ).

---

## 4. Strict Prompt Isolation (Anti-Contamination)

- **Prohibition of Multi-Turn Cross-Talk**: Agents must never pass raw conversational transcripts or unparsed reasoning chains from prior turns into LLM inference prompts.
- **Context Injection Boundary**: Prompts may only consume strictly validated, registered canonical artifacts (e.g. `data/normalized/answers_normalized.parquet` or `data/processed/candidate_options.json`).
- **Prompt Hash Verification**: If a prompt template changes, `src/freshness_checker.py` flags registered downstream artifacts as stale until regenerated.
