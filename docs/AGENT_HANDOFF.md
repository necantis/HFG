# Standard Agent Handoff — Agent 00 to Downstream Agents (`01`–`04`)

**Handoff ID:** `HANDOFF_AGENT_00_BASELINE_V1`  
**From Agent:** `agent_00` (System Architect)  
**To Agents:** `["agent_01", "agent_02", "agent_03", "agent_04"]`  
**Schema Version:** `1.0.0`  
**Ready for Next Stage:** `true`

---

## 1. Architectural Decisions

1. **Question-Centric Spine with Frame-Gated Taxonomies:**
   - The 13 substantive questions (`Q01`–`Q13`) are modeled via `QuestionSpec` with explicit `AnalyticalFrameType` (`GOVERNANCE_GOODS_ALLOCATION`, `INSTITUTIONAL_DESIGN_DECISION`, `PERCEPTION_AND_DIAGNOSTIC`, `OPEN_STRATEGIC_PRIORITY`).
   - Economic-good classifications (`private_good`, `club_good`, `common_good`, `public_good`) are strictly gated by `economic_good_classification_policy` (`ENABLED` / `CONDITIONAL` / `DISABLED`) and prohibited on perception/diagnostic questions.
2. **Orthogonal Four-Quantity Coding Contract:**
   - `CodingResult` and `PreferenceCell` separate `participant_preference` ($\in [-1, +1]$), `semantic_importance` ($\in [0, 1]$), `coder_confidence` ($\in [0, 1]$), and `coder_agreement` ($\in [0, 1]$).
   - Point utilities $U_i(s)$ use only `participant_preference` weighted by `semantic_importance` over observed subtopics, while `coder_confidence` and `coder_agreement` parameterize the cell's uncertainty interval for `RobustParetoResult`.
3. **Strict Non-Imputation of Missingness:**
   - `MissingnessState` distinguishes `OBSERVED`, `MISSING_RAW_BLANK`, `MISSING_NON_SUBSTANTIVE`, `NOT_MENTIONED_IN_RESPONSE`, `NOT_APPLICABLE_FRAME`, and `SKIPPED_MISSING_INPUT_FILE`.
   - Any non-observed cell enforces `participant_preference = None` and `semantic_importance = None`.
4. **Strict Constraint-Based Solution Pruning & Unbiased Pareto Choice Set:**
   - Solutions in `src/solution_space.py` are pruned **strictly and exclusively** by objective feasibility rules:
     * *Logical constraints* (e.g. allocation shares sum to 100%, mutually exclusive postures not co-selected).
     * *Institutional constraints* (e.g. entity formally responsible for an evaluation must possess the required decision right).
     * *Structural dependencies* (e.g. if a club fund is selected, membership and contribution rules must exist).
   - **Crucial Rule for Agent 03 & Agent 04:** Clustering and values may explain or characterize solutions ex-post; they may **never** determine or filter whether an otherwise feasible solution is included in the Pareto choice set. Pre-filtering solutions (e.g. "nobody in Cluster 2 prefers this -> eliminate solution") is strictly prohibited as it would systematically bias the Pareto frontier. Agent 04 must validate in `04_validation.ipynb` that no candidate solution was pruned due to cluster preference or value tagging.
5. **Concurrent Dual-LLM Runtime on NVIDIA RTX PRO 6000 Blackwell Server Edition:**
   - Two architecturally distinct models (`coder_a` on `:8001`, `coder_b` on `:8002`) run concurrently with 44% VRAM allocation each (~42.2 GB per server on the 96 GB Blackwell GPU) and guided JSON Schema decoding.
6. **Warm-Cache $\le 10$ Minute Execution via Merkle Checkpointing:**
   - Append-only JSONL WAL per `(question_id, participant_id, coder_id)` for GPU coding and vectorized CPU NumPy broadcasting for $K=2000$ Monte Carlo draws in `src/robust_pareto.py`.
7. **Conditional Execution of Baldwin & RRV Voting:**
   - `src/voting_baldwin.py` and `src/voting_rrv.py` execute if and only if active-group ballot files are present and pass SHA-256 and schema validation; otherwise they return `SKIPPED_NO_VALID_INPUT`.

---

## 2. Created / Modified Files

- [AGENTS.md](../AGENTS.md)
- [docs/PROJECT_STATE.md](PROJECT_STATE.md)
- [docs/AGENT_CONTEXT/agent_00_context.md](AGENT_CONTEXT/agent_00_context.md)
- [docs/ARCHITECTURE.md](ARCHITECTURE.md)
- [docs/DATA_CONTRACTS.md](DATA_CONTRACTS.md)
- [docs/PIPELINE.md](PIPELINE.md)
- [docs/IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)
- [docs/AGENT_HANDOFF.md](AGENT_HANDOFF.md)
- [src/contracts.py](../src/contracts.py)
- [schemas/interfaces.json](../schemas/interfaces.json)

---

## 3. Architectural Risks & Mitigations

| Risk ID | Severity | Description | Mitigation |
| :--- | :--- | :--- | :--- |
| `RISK-01` | **HIGH** | Legacy notebooks or scripts from a prior survey group may be copied into the repo containing hardcoded group names, package labels, participant counts, or winners. | `src/hardcoding_scanner.py` must run as Step 1 of `00_control_plane.ipynb` and Gate 4 of `04_validation.ipynb`, blocking execution on any Category 4 match. |
| `RISK-02` | **HIGH** | Sparse subtopic matrices (when many participants only mention a subset of subtopics in open-ended text) can distort Euclidean distances or utilities if `NOT_MENTIONED_IN_RESPONSE` is treated as `0.0`. | `PreferenceCell` keeps `participant_preference = None` for `NOT_MENTIONED_IN_RESPONSE`; `src/utilities.py` normalizes strictly over $\mathcal{M}_i^{\text{obs}}$, and `src/clustering.py` uses pairwise masked distances over shared observed subtopics. |
| `RISK-03` | **MEDIUM** | Concurrent local LLM servers on a single GPU can contend for VRAM or KV-cache if context lengths are unbounded. | Cap `gpu_memory_utilization = 0.44` per server (~84.5 GB total out of 96 GB on RTX PRO 6000 Blackwell) and bound `max_model_len = 16384`. |
| `RISK-04` | **HIGH** | Candidate solutions could be pre-filtered based on social group preferences (e.g. cluster popularity or value alignment), severely biasing the Pareto frontier. | `src/solution_space.py` prunes candidates **strictly and exclusively** on logical constraints, institutional constraints, and structural dependencies. Agent 04's validation notebook (`04_validation.ipynb`) must explicitly test and enforce that no solution was pruned due to cluster preference or value alignment. |

---

## 4. Mandatory Tasks for Downstream Agents

### Tasks for Agent 01 (Control Plane & Ingestion)
1. Implement `src/provenance.py`, `src/artifact_registry.py`, and `src/checkpointing.py` adhering to `ArtifactRecord` and `ProvenanceMeta` in `src/contracts.py`.
2. Implement `src/hardcoding_scanner.py` to scan both `.py` ASTs and `.ipynb` code/markdown cells for Category 4 forbidden patterns. If legacy `.ipynb` files are dropped into the workspace, run the scanner and report all violations before executing any pipeline stage.
3. Implement `src/ingestion.py` and `src/question_registry.py` for the 13 multilingual (`fr`/`de`/`en`) questions, preserving `MissingnessState`.
4. Implement `src/orchestrator.py` and `00_control_plane.ipynb`.

### Tasks for Agent 02 (GPU Qualitative Coding & Reconciliation)
1. Implement `src/model_runtime.py` targeting dual concurrent servers on NVIDIA RTX PRO 6000 Blackwell Server Edition (`localhost:8001` and `localhost:8002`).
2. Implement `src/subtopic_extraction.py` and `src/value_extraction.py` with character-offset-verified `EvidenceSpan` extraction and frame-gated economic-good classification.
3. Implement `src/evidence_ledger.py` and `src/reconciliation.py`, ensuring `participant_preference`, `semantic_importance`, `coder_confidence`, and `coder_agreement` remain distinct.
4. Implement `01_gpu_coders.ipynb`.

### Tasks for Agent 03 (Mathematical Analysis, Social Choice & Voting)
1. Implement `src/preference_matrix.py` and validate zero-imputation invariants.
2. Implement `src/clustering.py` with missingness-masked distances and automated $k^*$ selection.
3. Implement `src/solution_space.py`, `src/utilities.py`, `src/pareto.py`, and vectorized `src/robust_pareto.py` (Rawls, Utilitarian, Nash, Gini/Atkinson, Opposition, Minimax Regret).
4. Implement conditional `src/voting_baldwin.py` and `src/voting_rrv.py`.
5. Implement `02_math_analysis.ipynb`.

### Tasks for Agent 04 (Traceable Reporting & Validation)
1. Implement `src/report_generator.py` and `03_report.ipynb` ensuring every statement is backed by a verified `ReportClaim`. Use clustering and values exclusively to explain or characterize solutions ex-post.
2. Implement `04_validation.ipynb` to audit all 20 data contracts, provenance hashes, missingness invariants, warm-cache execution timing, and **explicitly verify that no candidate solution was pruned or excluded from the Pareto choice set based on cluster preferences or value alignment**.

