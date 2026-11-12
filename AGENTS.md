# Multi-Agent Governance & Ownership Rules (`AGENTS.md`)

**System:** Multilingual Institutional Survey Analysis System (HFG)  
**Schema Version:** `1.0.0`

---

## 1. Global Non-Negotiable Rules for All Agents

1. **Authoritative Sources Only:** Treat repository documentation (`docs/`), active source files (`src/`), and registered artifacts (`ArtifactRecord`) as authoritative. Never rely on prior chat history or external survey runs.
2. **Zero Cross-Survey Reuse:** Never reuse entities, institutional packages, cluster names, candidate names, voting results, participant counts, numerical results, or recommendations from another survey group.
3. **13-Question Primary Spine:** The 13 substantive questions (`Q01`–`Q13`) in French (`fr`), German (`de`), or English (`en`) remain the primary analytical structure.
4. **Bottom-Up Subtopic Discovery:** Multiple subtopics per question must be extracted dynamically from participant `EvidenceSpan` records—never inferred merely from question wording.
5. **Cross-Question Values:** Subtopics across questions are connected via evidence-supported organisational values (`ValueAssignment`).
6. **Domain-Appropriate Classification:** Apply `private_good`, `club_good`, `common_good`, and `public_good` classifications **only** when conceptually appropriate to allocation, access, ownership, financial responsibility, or decision rights (`QuestionSpec.economic_good_classification_policy != "DISABLED"`). Use question-specific analytical frames for perception and diagnostic questions.
7. **Dual Independent LLM Coding:** Two architecturally distinct LLMs (`coder_a` and `coder_b`) code qualitative evidence concurrently on the NVIDIA RTX PRO 6000 Blackwell Server Edition.
8. **Strict Missingness Preservation:** Missing answers always remain missing (`MissingnessState != OBSERVED`, `participant_preference = None`). Never impute `0.0` for missing or unmentioned subtopics.
9. **Four Distinct Quantities:** Keep `participant_preference`, `semantic_importance`, `coder_confidence`, and `coder_agreement` strictly orthogonal.
10. **Exclusive Utility Provenance:** Derive `ParticipantUtility` exclusively from the validated `PreferenceMatrix`.
11. **Dynamic Solutions & Participant-Level Pareto:** Generate `FeasibleAlternative` and `GovernanceSolution` dynamically; prune candidate solutions **strictly and exclusively** by logical constraints, institutional constraints, and explicit structural dependencies. **Strict Invariant:** Clustering assignments, cluster preference patterns, and value linkages may explain, interpret, or characterize solutions ex-post—they may **never** determine or filter whether an otherwise feasible solution is included in the Pareto choice set. Evaluate exact participant-level `ParetoResult` and Monte Carlo `RobustParetoResult`; rank nondominated solutions transparently using Rawls/maximin, utilitarian, Nash social welfare, inequality (Gini/Atkinson), opposition/veto, and minimax regret.
12. **Data-Driven Clustering:** Select cluster count $k^*$ and assignments (`ClusterResult`) strictly from missingness-masked distances on `PreferenceMatrix`.
13. **Conditional Baldwin & RRV Voting:** Execute `src/voting_baldwin.py` and `src/voting_rrv.py` only if active-group ballot files exist and pass validation.
14. **Traceable Claims & Checkpoints:** Every `ReportClaim` must link to `EvidenceSpan` and mathematical `ArtifactRecord` IDs; all expensive stages use content-addressed checkpoints targeting $\le 10$ minutes warm-cache execution.

---

## 2. Agent Roster & Scope Boundaries

| Agent ID | Role | Owned Files |
| :--- | :--- | :--- |
| **Agent 00** | System Architect | `AGENTS.md`, `docs/ARCHITECTURE.md`, `docs/DATA_CONTRACTS.md`, `docs/PIPELINE.md`, `docs/IMPLEMENTATION_PLAN.md`, `docs/PROJECT_STATE.md`, `docs/AGENT_CONTEXT/*`, `src/contracts.py`, `schemas/interfaces.json` |
| **Agent 01** | Control Plane & Ingestion Engineer | `00_control_plane.ipynb`, `src/provenance.py`, `src/artifact_registry.py`, `src/checkpointing.py`, `src/hardcoding_scanner.py`, `src/ingestion.py`, `src/question_registry.py`, `src/orchestrator.py` |
| **Agent 02** | GPU Qualitative Coding & Reconciliation Engineer | `01_gpu_coders.ipynb`, `src/model_runtime.py`, `src/subtopic_extraction.py`, `src/value_extraction.py`, `src/evidence_ledger.py`, `src/reconciliation.py` |
| **Agent 03** | Mathematical Analysis & Social Choice Engineer | `02_math_analysis.ipynb`, `src/preference_matrix.py`, `src/clustering.py`, `src/solution_space.py`, `src/utilities.py`, `src/pareto.py`, `src/robust_pareto.py`, `src/voting_baldwin.py`, `src/voting_rrv.py` |
| **Agent 04** | Traceable Reporting & Validation Engineer | `03_report.ipynb`, `04_validation.ipynb`, `src/report_generator.py` |

