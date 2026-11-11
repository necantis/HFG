# Model Strategy & Inference Governance — HFG

> **Status**: Approved (`v1.0.0`)
> **Enforced by**: `src/artifact_registry.py`, `src/validation/`

---

## 1. Model Tier Selection Matrix

To balance computational latency, token economics, and analytical depth, models are assigned strictly by task complexity:

| Tier | Model Designation | Recommended Stages / Roles | Characteristics & Usage |
| :--- | :--- | :--- | :--- |
| `flash_lite` | Lightweight fast model | Stage 1 (Schema validation formatting, syntax checks) | Ultra-fast token throughput, minimal latency, low reasoning overhead. |
| `flash` | Fast balanced model | Stage 2 (Initial theme tagging), Stage 4 (Pairwise comparison formatting) | High throughput, reliable structured output extraction. |
| `pro` | Advanced reasoning model | Stage 2 (Complex thematic synthesis), Stage 3 (Candidate option generation), Stage 7 (Policy brief synthesis), Stage 8 (Red-team invariant audit) | Deep contextual reasoning, zero-shot nuance, rigorous invariant enforcement. |
| `inherit` | Calling agent model | Default for subagent invocations | Inherits parent session configuration unless overridden by explicit need. |

---

## 2. Determinism & Analytical Reproducibility Controls

1. **Zero Temperature Invariant**: For all analytical extractions, preference reconciliations, and candidate generation, inference requests MUST specify `temperature = 0.0` (or `seed = 42`).
2. **Prompt Versioning & Hashing**:
   - Every system and user prompt template used in production code must be versioned and stored under `prompts/` or embedded in module constants.
   - The Artifact Registry requires recording the SHA-256 hash of the prompt template (`prompt_hash`) whenever an LLM produces or annotates an artifact.
3. **Quantisation Tracking**:
   - The Run Card records whether models were executed via full precision FP16/BF16 or quantised (e.g., INT8/INT4/AWQ).

---

## 3. Strict Prompt Isolation (Anti-Contamination)

- **Prohibition of Multi-Turn Cross-Talk**: Agents must never pass raw conversational transcripts or unparsed reasoning chains from prior turns into LLM inference prompts.
- **Context Injection Boundary**: Prompts may only consume strictly validated, registered canonical artifacts (e.g. `data/normalized/answers_normalized.parquet` or `data/processed/candidate_options.json`).
- **Prompt Hash Verification**: If a prompt template changes, `src/freshness_checker.py` flags registered downstream artifacts as stale until regenerated.
