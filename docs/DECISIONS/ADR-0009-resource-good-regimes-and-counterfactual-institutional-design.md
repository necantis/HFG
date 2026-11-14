# ADR-0009: Resource-Good Regimes, Voluntary Club Provision, and Counterfactual Institutional-Design Sensitivity

- **Decision ID**: `ADR-0009`
- **Date**: `2026-11-14`
- **Status**: `APPROVED`
- **Superseded By**: `None`
- **Active Run Reference**: `run_20261111_002`
- **Affected Modules**: `docs/ARCHITECTURE.md`, `docs/DATA_CONTRACTS.md`, `docs/PROJECT_STATE.md`, `docs/OPEN_ISSUES.md`, `src/contracts.py`, `schemas/interfaces.json`, `src/evidence/`, `src/preference/`, `src/reporting/`, `src/pipeline/orchestrator.py`
- **Dependencies**: `ADR-0001`, `ADR-0002`, `ADR-0005`, `ADR-0006`, `ADR-0007`, `ADR-0008`

---

## 1. Context

### 1.1. Frozen Original Evidence-Grounded Baseline (`OBSERVED_DESIGN_FRONTIER`)

On `run_20261111_002`, Agents 01–07 and Agent 11 integration (`runs/<run_id>/manifest.json` with `39` registered artifacts, `runs/<run_id>/RUN_CARD.md`) completed the first end-to-end production analytical pass under `ADR-0005` and `ADR-0008`:

- **Ingestion & Dual-LLM Coding (Agents 01, 02, 07)**: `154` raw records across `N = 11` participants (`Q01`–`Q13` primary plus optional `Q14`; `136` `observed_usable`, `10` `missing_raw_blank`, `6` `missing_non_substantive`, `2` `ambiguous`), coded independently by `coder_a` (`Valdemardi/DeepSeek-R1-Distill-Qwen-32B-AWQ`) and `coder_b` (`RedHatAI/Mistral-Small-3.1-24B-Instruct-2503-quantized.w4a16`) on NVIDIA RTX PRO 6000 Blackwell (`136/136/0`, Checks A–H `8/8 PASS`).
- **Evidence Reconciliation (Agent 03, `src/evidence/reconciliation.py`)**: `101` coder subtopic proposals consolidated into `84` canonical subtopics (`9` `EXACT_MATCH`, `8` `SEMANTIC_MATCH`, `43` `PARTIAL_OVERLAP`, `7` `CODER_A_ONLY`, `17` `CODER_B_ONLY`); `284` preference reconciliation records (`16/16` QA checks, `0` forbidden methods, `0` unauthorized point collapses, `18` preserved missingness/non-preference cells).
- **Preference Matrix, Constraint-Only Solution Space & Robust Pareto (Agent 04, `src/preference/`)**:
  - `PreferenceMatrix`: `284` cells (`264` primary `Q01`–`Q13`, `20` contextual `Q14`, `18` missingness preserved, `0` `coder_confidence` weightings, `0` single-coder `0.0`-fills).
  - `SolutionSpace`: `161` `FeasibleAlternative` records (`32` minority-preserved) and **`543` strictly constraint-feasible `GovernanceSolution` packages** (`13` primary questions each, `0` `Q14` inclusions; `112` constraint-pruned packages / `113` explicit constraint exclusions; `0` prohibited cluster/value/disagreement prunings).
  - `ParticipantUtility`: `5,973` records across `11` valid participants (`0` non-null `point_utility`).
  - Exact `ParetoResult`: **`326` expected-reference nondominated solutions**.
  - 4-State `RobustParetoResult` (`1,000` Monte Carlo draws, `random_seed = 42`, `veto_threshold = 0.35`, coupled common-world coding-gap corners):
    - **`10` `ROBUSTLY_NONDOMINATED`** (`SOL_0003`, `SOL_0009`, `SOL_0212`, `SOL_0416`, `SOL_0419`, `SOL_0422`, `SOL_0423`, `SOL_0424`, `SOL_0440`, `SOL_0522`)
    - **`248` `CONDITIONALLY_NONDOMINATED`** (`102` with inclusion probability $\ge 0.95$)
    - **`285` `UNRESOLVED_DUE_TO_CODING_UNCERTAINTY`**
    - **`0` `ROBUSTLY_DOMINATED`**
    - Four distinct welfare criteria yield distinct top-1 solutions (`SOL_0160`, `SOL_0364`, `SOL_0371`, `SOL_0416`); zero composite winner collapsed.
- **Ex-Post Clustering & Social Choice (Agents 05 & 06)**:
  - Agent 05 (`src/clustering/clustering.py`): **`NO_STABLE_CLUSTER_STRUCTURE`** (`selected_k = 1`, `PROFILE_01`; `K = 2` fails empirical stability gates; exploratory `Rep C` non-canonical only; zero pruning/weighting influence).
  - Agent 06 (`src/voting/`): **`NO_ROBUST_SINGLE_WINNER`**, **`BALDWIN = NOT_APPLICABLE`** (`SKIPPED_NO_VALID_INPUT`), **`RRV = NOT_APPLICABLE`** (`SKIPPED_NO_VALID_INPUT`), `77.8%` MC Condorcet cycle rate (`46` unique MC Borda winners, `81` unique MC Minimax winners), and `N = 11` LOO instability (`6/11` Borda flips, `9/11` Minimax flips).

**Baseline Freeze Mandate**: All `543` feasible packages, `326` baseline nondominated solutions, the `10 / 248 / 285 / 0` 4-state `RobustParetoResult`, and Agents 05–06 conclusions constitute the immutable, reproducible baseline hereby formally labeled **`OBSERVED_DESIGN_FRONTIER`** (**`FRONTIER_A`**). Agent 08 (`src/reporting/report_generator.py`) is technically released (`AGENT_08_TECHNICAL_RELEASE = READY`), but its execution is **temporarily held** (`AGENT_08_REPORTING_STATUS = HELD_FOR_RESOURCE_REGIME_SENSITIVITY`) strictly to address whether alternative institutional resource regimes—especially voluntary **club-good** provision—were omitted from the original solution space.

### 1.2. Empirical Audit of Goods-Classification History in Repository Artifacts

A direct audit of repository schemas, runtime configurations, prompts, reconciliation logic, and solution-space generation establishes exactly how economic-good classification behaved across `run_20261111_002`:

| System Layer | Source File | Verified Behavior on `run_20261111_002` |
| :--- | :--- | :--- |
| **Question Registry (Agent 01)** | `data/normalized/question_registry.json`, `docs/ARCHITECTURE.md` (§3) | `economic_good_classification_policy` is **`ENABLED`** (`GOVERNANCE_GOODS_ALLOCATION`) on six questions: `Q07`, `Q08`, `Q09`, `Q10`, `Q11`, `Q12`. It is **`CONDITIONAL`** on `Q01`, `Q02`, `Q03`, `Q06` (`PERCEPTION_AND_DIAGNOSTIC`), `Q04`, `Q05`, `Q13` (`INSTITUTIONAL_DESIGN_DECISION`), and `Q14` (`OPEN_STRATEGIC_PRIORITY`), with `0` `DISABLED` flags in the JSON registry (though `docs/ARCHITECTURE.md` §3 explicitly specifies `DISABLED` for `PERCEPTION_AND_DIAGNOSTIC`). |
| **Agent 02 Schemas & Prompts** | `src/nlp/schemas.py`, `src/nlp/prompts.py` | Defined `SubtopicGoodsAssessment` and `CodingResult.economic_good_class`, instructing dual LLMs to label `private_good`, `club_good`, `common_good`, or `public_good` **only** when response evidence supports allocation, access, ownership, financing, risk, or decision-rights semantics, explicitly permitting `NOT_APPLICABLE`. |
| **Dual-LLM Coding (RTX PRO 6000 Blackwell)** | `src/evidence/reconciliation.py` (`_audit_goods_classification`, L2360–2438) | **Both** `coder_a` and `coder_b` emitted `goods_applicability = "NOT_APPLICABLE"` across `0` populated subtopics (`coder_a_applicable_subtopics = 0`, `coder_b_applicable_subtopics = 0`) and `0` non-null `economic_good_class` entries in `coding_results` across all `6` `ENABLED` questions (`Q07`–`Q12`). |
| **Agent 03 Reconciliation** | `src/evidence/reconciliation.py` (L1178–1306, L2397–2438), `docs/AGENT_HANDOFFS/agent_03_handoff.md` | Agent 03 **deliberately refused to force** classifications (`forced_classifications_count = 0`), recorded `economic_good_applicability = "NOT_APPLICABLE_FRAME"` and `dominant_economic_good_class = None` on all `84` canonical subtopics, and logged `UNRES_GOODS_ENABLED_Q07_Q12_UNPOPULATED` (`GOODS_ASSESSMENT_UNPOPULATED_ON_ENABLED_QUESTION`, severity `MEDIUM`, `SEMANTICALLY_UNRESOLVED`), deferring targeted goods-semantics evaluation. |
| **Data Contracts & ADRs** | `docs/DATA_CONTRACTS.md`, `src/contracts.py`, `ADR-0005`, `ADR-0008` | `ADR-0005` established the domain-appropriateness invariant (`private_good`, `club_good`, `common_good`, `public_good`); `ADR-0008` intentionally scoped reconciliation to distribution uncertainty sets and Level 2 crosswalks (`runs/<run_id>/alternative_crosswalk.json`), leaving multi-dimensional institutional-design regime parameters out of scope. |
| **Agent 04 Solution Space** | `src/preference/solution_space.py` (L227–231, L261–269, L607–638) | Because upstream `dominant_economic_good_class` was `None`, every `FeasibleAlternative` carried `economic_good_profile = None`. Stage B of `SolutionSpaceBuilder` spanned only raw coder stance vocabularies (`Q09`: individual/pole/collective/hybrid; `Q10`: `scenario_1`..`scenario_5`; `Q11`: PI/common pool/hybrid; `Q12`: individual/pole/`socle_investissement`). Even where raw coder key `"voluntary_pooling"` appeared in `Q11_overhead_allocation_mechanism_2_B_ONLY`, `SolutionSpaceBuilder` lacked systematic parameterization of voluntary membership, zero non-member compulsory contribution, member priority, exit rules, or congestion/capacity management. |

---

## 2. Problem

The original `543`-package `OBSERVED_DESIGN_FRONTIER` accurately reflects the institutional postures surfaced verbatim by participants and coded by `coder_a`/`coder_b`. However, institutional governance regimes are design mechanisms—not merely descriptive labels—and when a survey poses dichotomous or scenario-based trade-offs (e.g., individual PI allocation vs compulsory institutional common pool, or individual liability vs collective pooling), a voluntary **club-good** institutional arrangement (or a structured hybrid with exit rights and residual non-member access) may resolve conflicts over non-consenting financial burden without appearing verbatim in the original coder alternative keys.

This creates a strict architectural tension:

1. **Completeness of Design Sensitivity**: If feasible resource-allocating subtopics admit voluntary club-good, private, common-pool, public, or hybrid regimes that were never parameterized in `SolutionSpaceBuilder`, omitting them from sensitivity review could mask institutionally viable Pareto options.
2. **Epistemic Integrity**: Survey participants were not presented with explicit counterfactual club-good contracts (membership rules, exit conditions, non-member zero-contribution guarantees, congestion rules). Fabricating point utilities for unobserved options, reinterpreting *"I refuse to pay"* as *"I prefer a voluntary club"*, forcing economic-good labels onto perceptions/decision-rights questions (`Q01`–`Q07`, `Q13`, `Q14`), or altering the frozen `543`-package frontier would corrupt `ADR-0005` and `ADR-0008` provenance.

HFG therefore requires a formal architectural contract separating **observed empirical governance analysis** from **counterfactual institutional-design sensitivity analysis**.

---

## 3. Economic-Good Regime Model

### 3.1. Foundational Principle: Institutional Regimes, Not Ontological Essence

Economic goods classifications in HFG describe **institutional-design regimes** parameterized by explicit property, access, financing, and governance rules—**never** immutable ontological labels affixed permanently to a resource. A single allocable resource (for instance, an overhead revenue pool or a research support fund) can legitimately be organized under multiple alternative regimes (`PRIVATE_GOOD`, `CLUB_GOOD`, `COMMON_POOL_RESOURCE`, `PUBLIC_GOOD`, or `HYBRID`), subject to technical feasibility (rivalry/congestion) and institutional constraints.

### 3.2. Orthogonal Economic & Institutional Dimensions

Every candidate resource regime specification MUST be represented explicitly across five orthogonal dimensions. Unknown attributes MUST remain `UNKNOWN` unless supported by span evidence or explicitly declared as counterfactual parameters—**never** inferred silently:

| Dimension | Required Enum Values | Normative Rule |
| :--- | :--- | :--- |
| **`RIVALRY`** | `RIVAL \| CONGESTIBLE \| NON_RIVAL \| UNKNOWN` | Captures whether one unit's consumption subtracts from another's (`RIVAL`: rivalrous budget euros), degrades quality above capacity (`CONGESTIBLE`: shared HR/admin support bandwidth), or is non-depleting (`NON_RIVAL`: non-rival shared digital standards), or remains unstated (`UNKNOWN`). |
| **`EXCLUDABILITY`** | `EXCLUDABLE \| PARTIALLY_EXCLUDABLE \| NON_EXCLUDABLE \| UNKNOWN` | Captures institutional and technical ability to restrict access to contributing members (`EXCLUDABLE`), enforce priority/tiered rationing (`PARTIALLY_EXCLUDABLE`), or allow universal access (`NON_EXCLUDABLE`). |
| **`FINANCING`** | `INDIVIDUAL \| VOLUNTARY_MEMBER \| USAGE_BASED \| COLLECTIVE \| INSTITUTIONAL \| MIXED` | Identifies who pays and whether contributions are voluntary (`VOLUNTARY_MEMBER`, `USAGE_BASED`), self-funded (`INDIVIDUAL`), or compulsory/pooled (`COLLECTIVE`, `INSTITUTIONAL`, `MIXED`). |
| **`ACCESS`** | `OWNER_ONLY \| MEMBER_PRIORITY \| PAY_PER_USE \| RESIDUAL_CAPACITY \| OPEN_ACCESS \| ALLOCATED_QUOTA \| OTHER_EXPLICIT` | Defines access entitlements for owners, members, and non-members. `OTHER_EXPLICIT` requires a non-empty `access_rule_description`. |
| **`EXIT`** | `ALLOWED \| CONSTRAINED \| NOT_APPLICABLE` | Defines whether a member/unit may withdraw from voluntary pooling (`ALLOWED`), faces notice/vested-commitment lock-in (`CONSTRAINED`), or cannot exit compulsory/non-pooled regimes (`NOT_APPLICABLE`). |

### 3.3. Supported Good Regimes

| Regime (`GoodRegimeType`) | Structural Profile |
| :--- | :--- |
| **`PRIVATE_GOOD`** | `RIVAL` (or excludable budget slice), `EXCLUDABLE`, `FINANCING in {INDIVIDUAL, USAGE_BASED}`, `ACCESS = OWNER_ONLY`, `EXIT = NOT_APPLICABLE`. |
| **`CLUB_GOOD`** | `CONGESTIBLE \| NON_RIVAL \| RIVAL` (when budget pool is excludable to club members via contribution-gated quota/services), `EXCLUDABLE \| PARTIALLY_EXCLUDABLE`, `FINANCING = VOLUNTARY_MEMBER` (with optional `USAGE_BASED` surcharge), `non_member_compulsory_contribution = 0.0`, `ACCESS` governed by §5, `EXIT = ALLOWED` unless explicit constraint sets `CONSTRAINED`. |
| **`COMMON_POOL_RESOURCE`** | `RIVAL \| CONGESTIBLE`, `NON_EXCLUDABLE \| PARTIALLY_EXCLUDABLE`, `FINANCING in {COLLECTIVE, INSTITUTIONAL, MIXED}`, `ACCESS in {OPEN_ACCESS, ALLOCATED_QUOTA}`, governed by quota/extraction rules to prevent depletion/congestion. |
| **`PUBLIC_GOOD`** | `NON_RIVAL` (or non-excludable institutional infrastructure), `NON_EXCLUDABLE`, `FINANCING in {COLLECTIVE, INSTITUTIONAL}`, `ACCESS = OPEN_ACCESS`, `EXIT = NOT_APPLICABLE` (mandatory shared funding). |
| **`HYBRID`** | Explicit multi-tier combination (e.g., mandatory baseline institutional tier + voluntary club surcharge tier, or PI-private tranche + residual pooled reserve) with disjoint rule accounting for each tranche so financing and access remain conflict-free. |

---

## 4. Resource Eligibility (`RESOURCE_ELIGIBILITY` Contract)

### 4.1. Formal `RESOURCE_ELIGIBILITY` Criteria

A canonical subtopic $m$ may enter counterfactual resource-regime expansion **if and only if** its empirical evidence (`EvidenceSpan`s and `CanonicalSubtopic` definitions) concerns an **economically meaningful allocable resource, budget pool, financial risk-sharing pool, shared capacity, or excludable service**. Mere presence inside `Q07`–`Q12` does **not** grant resource eligibility (`Agent 01` `"ENABLED"` policy permits but never mandates resource status).

Three mutually exclusive eligibility statuses are defined:

1. **`ELIGIBLE`**: Subtopic evidence directly addresses allocation, sharing, pooling, access, ownership, financing, or financial risk-sharing of an allocable budget, revenue stream, bonus/investment pool, or shared financial reserve.
2. **`CONDITIONAL_RESOURCE_ONLY`**: Subtopic primarily concerns institutional decision/management levels (`INELIGIBLE` as pure authority), **but** contains an evidenced service-capacity component (e.g., pooled administrative/HR support staff) that can be parameterized as a congestible shared service *only* in a clearly segregated sensitivity tier and with explicit counterfactual framing disclosure.
3. **`INELIGIBLE`**: Subtopic concerns respondent perceptions, competence/team-size evaluations, terminology clarity, collaboration attitudes, psychological/burnout diagnostics, process transparency, legal signing authority/mandates, evaluation criteria, or open strategic remarks. **Must never receive economic-good regime assignment or counterfactual club expansion.**

### 4.2. Subtopic Eligibility Audit for `run_20261111_002` (`Q01`–`Q14`)

*(Derived strictly from `data/normalized/question_registry.json`, `runs/<run_id>/alternative_crosswalk.json`, and `src/preference/solution_space.py` without modifying any data or fabricating subtopics.)*

| Question(s) | Subtopic Scope in `run_20261111_002` | `RESOURCE_ELIGIBILITY` | Analytical Rationale & Structural Boundaries |
| :--- | :--- | :--- | :--- |
| **`Q01`–`Q03`** | Pole relevance, transformation/scope, competence/group size (`Q02_group_size_and_composition`), terminology clarity/alignment/subtitles (`Q03_terminology_clarity`, etc.) | **`INELIGIBLE`** | `PERCEPTION_AND_DIAGNOSTIC` frame: assessments of organizational relevance, skills, team size, and naming—zero allocable economic goods. |
| **`Q04`–`Q05`** | Ad-hoc vs unified operational organization (`Q04_ad_hoc_operation`, process standardization, transversality) & coordination scenarios (`Q05_coordination_mechanism`) | **`INELIGIBLE`** | `INSTITUTIONAL_DESIGN_DECISION` frame: workflow and steering structures, not rivalrous/excludable resource pools. |
| **`Q06`** *(excl. financial facets)* | `Q06_scenario_evaluation`, `Q06_collaboration_framework`, `Q06_coordination_mechanisms`, `Q06_communication_and_visibility_B_ONLY`, `Q06_participation_and_voice_A_ONLY`, `Q06_poles_manageability_B_ONLY`, `Q06_professor_autonomy_B_ONLY` | **`INELIGIBLE`** | Diagnostic ratings, collaboration culture, autonomy perceptions, and communication practices. |
| **`Q06`** *(financial facets)* & **`Q09`** *(core regime)* | `Q09_financial_responsibility_regime` (+ linked `Q06_financial_responsibility_B_ONLY`, `Q06_financial_responsibility_regime_A_ONLY` subject to double-count guard) | **`ELIGIBLE` *(Risk-Pooling Caveat)*** | Concerns allocation of financial responsibility, surplus/deficit buffers, and reserve mutualization across individual, pole, solidarity/club mutual, or collective institute tiers. **Caveat**: Risk-pooling/liability regimes are structurally distinct from service clubs because institutional solvency/deficit backstops (`IC-Q07-Q09-DELEGATION-LIABILITY`, `SD-Q10-Q09-SOCLE-DEPENDENCY`) constrain unilateral exit from statutory liabilities. |
| **`Q09`** *(diagnostic facets)* | `Q09_agility_vs_centralization_B_ONLY`, `Q09_context_dependency_B_ONLY`, `Q09_entrepreneurial_approach_B_ONLY`, `Q09_professor_burnout_B_ONLY` | **`INELIGIBLE`** | Attitudes, contextual observations, and workload/burnout perceptions—not allocable resources. |
| **`Q07`** *(all facets)* | `Q07_engagement_level`, `Q07_recruitment_responsibility_B_ONLY`, `Q07_engagement_autonomy_B_ONLY`, `Q07_engagement_conditions_B_ONLY`, `Q07_team_size_and_management_B_ONLY` | **`INELIGIBLE`** | Despite `Q07` having `ENABLED` in `question_registry.json`, actual evidence concerns **contractual commitment / signing authority, recruitment level, and risk-mandate governance rules**, not an allocable economic good. Couples into resource regimes strictly via `IC-Q07-Q09-DELEGATION-LIABILITY`. |
| **`Q08`** *(core HR level)* | `Q08_hr_management_level` | **`CONDITIONAL_RESOURCE_ONLY`** | Primarily concerns *where HR hiring/management decisions sit* (authority rule = `INELIGIBLE`). Admits counterfactual club/shared-service analysis **only** if operationalized as *pooled HR/administrative support staff capacity* (`CONGESTIBLE`, `PARTIALLY_EXCLUDABLE` shared support pool), segregated in Sensitivity Tier Q-G so baseline `Q10`–`Q12`/`Q09` conclusions never rely silently on `Q08`. |
| **`Q08`** *(diagnostic facets)* | `Q08_delegation_complexity_B_ONLY`, `Q08_performance_bonus_clarity_B_ONLY` | **`INELIGIBLE`** | Perceptions of delegation friction and rule clarity—not allocable resources. |
| **`Q10`** | `Q10_allocation_mechanism_core_funding` | **`ELIGIBLE`** | Allocable core funding (`socle`) institutional budget pool spanning centralized RI management, flat-rate allocation, pole management, and professor/lab management (`scenario_1`/`2`/`3`/`5`), directly admitting institutional vs pooled-club co-investment / hybrid tranches. |
| **`Q11`** *(pool mechanisms)* | `Q11_overhead_allocation_mechanism`, `Q11_overhead_allocation_mechanism_2_B_ONLY` *(already surfaces `"voluntary_pooling"`)*, `Q11_allocation_overheads_to_project_leaders_2_A_ONLY`, `Q11_overhead_reversal_to_lab_B_ONLY` | **`ELIGIBLE`** | Canonical allocable research overhead revenue pool (`Q11` project PI vs common institutional pool vs lab reversal vs explicit **voluntary club pooling**). Primary candidate for voluntary `CLUB_GOOD` parameterization. |
| **`Q11`** *(process facets)* | `Q11_overhead_negotiation_responsibility_B_ONLY`, `Q11_overhead_rate_transparency_B_ONLY` | **`INELIGIBLE`** | Institutional negotiation mandate and rate transparency rules—governance process norms, not allocable goods. |
| **`Q12`** *(bonus pool)* | `Q12_allocation_primes_depot`, `Q12_bonus_allocation_rules_B_ONLY`, `Q12_bonus_purpose_and_justification_B_ONLY` | **`ELIGIBLE`** | Allocable proposal-submission bonus / shared investment fund (`Q12_INDIVIDUAL_PROFESSOR_BONUS`, `Q12_POLE_COLLECTIVE_BONUS`, `coder_a:socle_investissement`), directly admitting private individual retention, voluntary shared investment club, or mandatory collective pool regimes. |
| **`Q12`** *(adequacy perception)* | `Q12_socle_adequacy_B_ONLY` | **`INELIGIBLE`** | Diagnostic adequacy judgment (`socle_is_insufficient` vs `socle_is_sufficient`)—perception, not a resource pool. |
| **`Q13`** | `Q13_evaluation_incentives` and `Q13_*_B_ONLY` | **`INELIGIBLE`** | `INSTITUTIONAL_DESIGN_DECISION`: performance evaluation metrics and recognition norms, not economic goods. |
| **`Q14`** | `Q14_collaboration_encouragement`, `Q14_organizational_learning`, open remarks | **`INELIGIBLE`** | `OPEN_STRATEGIC_PRIORITY` optional contextual remarks (`Q14` isolated from `Q01`–`Q13` primary decision lever space per `ADR-0005`/`ADR-0008`). |

**Double-Count Guard Invariant**: When evaluating `Q06_financial_responsibility_*` alongside `Q09_financial_responsibility_regime`, or when evaluating `Q11_overhead_allocation_mechanism_2_B_ONLY` alongside `Q11_overhead_allocation_mechanism`, counterfactual regime generators MUST preserve the Agent 04 double-count guard (`src/preference/utilities.py`) so multiple subtopic facets of the same underlying resource are parameterized consistently as one coherent regime without inflating utility weight.

---

## 5. Club-Good Operational Contract

A candidate solution or subtopic option labeled **`CLUB_GOOD`** is **invalid and MUST be rejected by structural constraint checks** unless every mandatory operational parameter below is explicitly populated:

| Contract Field | Type / Valid Values | Mandatory Operational Invariant |
| :--- | :--- | :--- |
| `regime` | `"CLUB_GOOD"` | Must be paired with an `ELIGIBLE` or explicitly flagged `CONDITIONAL_RESOURCE_ONLY` subtopic. |
| `membership_mode` | `"VOLUNTARY"` | Membership cannot be compulsory. Any compulsory membership fee converts the mechanism into `COLLECTIVE` / `PUBLIC_GOOD` or `HYBRID` (`non_club`). |
| `member_contribution_rule` | Non-empty explicit rule schema | Must define exact contribution basis (e.g., flat fee per participating lab/PI, proportional share of overhead/bonus receipts, or FTE capacity buy-in). |
| `non_member_compulsory_contribution` | `float == 0.0` (exact) | Non-members incur **strictly zero compulsory contribution** toward club provision. |
| `member_priority` | Non-empty explicit priority rule | Members must enjoy strictly prioritized entitlement (`member_access >= non_member_access`) over any club asset, reserve, or support capacity. |
| `non_member_access` | `NONE \| RESIDUAL_CAPACITY \| PAY_PER_USE \| OTHER_EXPLICIT` | Defines exact non-member status: excluded (`NONE`), residual surplus only after member demand is served (`RESIDUAL_CAPACITY`), market/surcharge fee (`PAY_PER_USE`), or documented exception (`OTHER_EXPLICIT`). |
| `exit_policy` | `ALLOWED \| CONSTRAINED` | Default **`ALLOWED`**. `CONSTRAINED` is permitted *only* when an explicit, documented institutional dependency requires notice period or settled liability (e.g., multi-year HR contract or open deficit in `Q09`) and MUST name the governing constraint ID. |
| `capacity_congestion_rule` | Explicit rule (mandatory when `RIVAL` or `CONGESTIBLE`) | Specifies how finite shared capacity (e.g., administrative FTE hours, finite mutual fund balance) is rationed or queue-managed when demand approaches capacity. |
| `governance_rule` | Explicit decision/oversight body & accounting rule | Defines club admission, rule-modification voting/quorum, budget ring-fencing, and surplus/deficit accounting separate from general institutional accounts. |
| `pricing_contribution_rule` | Explicit fee / cost-recovery / pay-per-use schedule | Must match `FINANCING` (`VOLUNTARY_MEMBER` or `VOLUNTARY_MEMBER + USAGE_BASED`) with zero hidden cross-subsidies from non-members. |

**Bare-Label Rejection Rule**: A label `"club"` or `"voluntary_pooling"` alone without all 10 populated structural fields fails `STRUCTURAL_DEPENDENCY` validation and MUST NOT enter `FRONTIER_B`.

---

## 6. Observed vs. Derived vs. Counterfactual Distinction

### 6.1. Three Strictly Segregated Provenance Categories

Every preference, structural consequence, or assumption entering counterfactual sensitivity analysis MUST carry one and only one of three mutually exclusive provenance tags:

| Provenance Tag | Exact Definition | Permitted Scope | Prohibited Conflation |
| :--- | :--- | :--- | :--- |
| **`OBSERVED_RESPONDENT_PREFERENCE`** | Empirical distributions `P_i = {p_A, p_B}` and missingness states derived directly from validated `EvidenceSpan`s via Agent 03/04 `PreferenceMatrix`. | Primary input for `FRONTIER_A` (`OBSERVED_DESIGN_FRONTIER`) and invariant anchor dimensions in `FRONTIER_B`. | **MUST NEVER** be modified, re-weighted, imputed, or overwritten by counterfactual models. |
| **`INSTITUTIONALLY_DERIVED_MECHANISM`** | Deterministic logical, accounting, or structural consequences entailed by a regime definition under existing institutional rules (e.g., setting `non_member_compulsory_contribution = 0.0` removes compulsory cross-subsidy burden from non-members; `non_member_access = NONE` denies non-member club-service usage). | Defines constraint satisfaction (`STRICTLY_FEASIBLE` vs pruned) and deterministic mechanical boundary relations inside `FRONTIER_B` utility intervals. | **MUST NEVER** fabricate positive preference for joining or endorsing the club mechanism itself. |
| **`COUNTERFACTUAL_PREFERENCE_ASSUMPTION`** | Explicit, named behavioral or utility sensitivity assumption over regime attributes never directly asked in the survey (e.g., how a PI opposing compulsory pooling values optional club membership vs retaining pure individual autonomy). | Authorized **solely** inside labeled `FRONTIER_B` sensitivity sweeps (`DERIVED_COUNTERFACTUAL_SCENARIO`). | **MUST NEVER** be presented as empirical respondent testimony, merged into `PreferenceMatrix`, or reported without assumption attribution. |

### 6.2. Critical Epistemic Boundary on Refusal to Pay

> **Strict Rule**: Never convert *"I do not want to pay / pool compulsorily"* (`Q11_PROJECT_PI_ALLOCATION`, `Q12_INDIVIDUAL_PROFESSOR_BONUS`, `Q09_INDIVIDUAL_PROFESSOR_LAB`) into *"I prefer voluntary club-good provision"* without direct `EvidenceSpan` support.

Specifically:
- Under `CLUB_GOOD`, `INSTITUTIONALLY_DERIVED_MECHANISM` establishes that a non-member pays **`0.0` compulsory contribution**, removing the forced-payment disutility present in a compulsory `PUBLIC_GOOD` or mandatory `COLLECTIVE` pool.
- However, the respondent's **non-member vs member vs private-retention utility differential**—including transaction/governance costs of club administration, potential exclusion from positive externalities (`NON_RIVAL`/`RESIDUAL_CAPACITY` spillovers), strategic holdout aversion, or preference for zero club existence altogether—remains **counterfactually unobserved** unless directly evidenced (such as explicit spans backing `voluntary_pooling`).

### 6.3. Counterfactual Solution Status Contract

Every counterfactual candidate solution generated for `FRONTIER_B` MUST carry:
- `solution_origin = "COUNTERFACTUAL_INSTITUTIONAL_DESIGN"`
- `design_expansion_type = "RESOURCE_REGIME_EXPANSION"`
- `parent_baseline_solution_id: str | None` (links to exact `FRONTIER_A` baseline package when derived by varying resource subtopics, preserving audit diff)
- `counterfactual_regime_specs: dict[str, ResourceRegimeSpec]` (keyed by `canonical_subtopic_id` of `ELIGIBLE` or explicitly opted-in `CONDITIONAL_RESOURCE_ONLY` subtopics)
- `utility_provenance_breakdown`: explicit separation of `OBSERVED_RESPONDENT_PREFERENCE` cells vs `INSTITUTIONALLY_DERIVED_MECHANISM` relations vs `COUNTERFACTUAL_PREFERENCE_ASSUMPTION` sweeps.

---

## 7. Partial Utility Identification & `UNRESOLVED_DUE_TO_COUNTERFACTUAL_UTILITY`

When a candidate solution $s \in \mathcal{S}_{\text{B}}$ contains `COUNTERFACTUAL_INSTITUTIONAL_DESIGN` parameters on subtopic $m$ that were not directly posed as alternatives in the survey:

1. **Non-Fabrication Rule**: Agent 04 MUST NOT assign arbitrary point alignment $\alpha_{m}(s) \in [0, 1]$ pretending respondent $i$ evaluated the counterfactual contract.
2. **Admissible Interval / Scenario Bounds**: For each scenario realization $\omega \in \Omega$ (inheriting `ADR-0008` coding-uncertainty draws), counterfactual utility for respondent $i$ on counterfactual dimension $m$ is partially identified as a bounded interval $[U_{i,m}^{\min}(s \mid \omega), U_{i,m}^{\max}(s \mid \omega)] \subseteq [0, 1]$ disciplined strictly by:
   - **Observed Baseline Alignment**: Empirical distribution `P_{i,m}` over the survey's private/individual vs pole vs institutional-pool poles (`OBSERVED_RESPONDENT_PREFERENCE`);
   - **Revealed Logical Dominance / Structural Relations (`INSTITUTIONALLY_DERIVED_MECHANISM`)**:
     - If $s_{\text{club}}$ matches $s_{\text{private}}$ on a respondent's own non-member cashflow (`non_member_compulsory_contribution = 0.0`) while differing only in allowing *voluntary* opt-in by other units, then under zero unmodeled externality a respondent preferring `INDIVIDUAL`/`PI_ALLOCATION` cannot incur direct compulsory-tax loss, though external spillover effects leave upper/lower utility open over `[align_baseline_conflict, align_no_compulsory_tax]`;
     - Conversely, a respondent demanding universal mandatory redistribution (`INSTITUTIONAL_COMMON_POOL` / `COLLECTIVE`) faces structural risk of under-provision/opt-out under voluntary exit (`EXIT = ALLOWED`), bounding their lower alignment strictly below guaranteed collective pooling unless explicit cross-subsidy constraints hold.
   - **Explicit Counterfactual Sensitivity Families (`COUNTERFACTUAL_PREFERENCE_ASSUMPTION`)**: Evaluate structured scenario corners (e.g., *Non-Member Indifferent / Burden-Relieved*, *Club-Transaction-Cost Averse*, *Pro-Voluntary-Cooperation*) strictly outside partial-ID bounds to characterize *what assumption would be required* for dominance.
3. **Fifth Robustness Classification State (`UNRESOLVED_DUE_TO_COUNTERFACTUAL_UTILITY`)**:
   - In `FRONTIER_B` (`RobustParetoResult`), dominance relations MUST explicitly recognize **`UNRESOLVED_DUE_TO_COUNTERFACTUAL_UTILITY`** alongside the four `ADR-0008` states (`ROBUSTLY_NONDOMINATED`, `CONDITIONALLY_NONDOMINATED`, `UNRESOLVED_DUE_TO_CODING_UNCERTAINTY`, `ROBUSTLY_DOMINATED`):
     - Under **Partial-ID Only (no counterfactual preference assumption)**, a counterfactual package $s$ whose interval utility overlaps competitors on counterfactual resource dimensions cannot be falsely declared `ROBUSTLY_DOMINATED` or `ROBUSTLY_NONDOMINATED`—its dominance ambiguity caused specifically by unobserved counterfactual preferences MUST be classified as **`UNRESOLVED_DUE_TO_COUNTERFACTUAL_UTILITY`** (distinguished cleanly from `UNRESOLVED_DUE_TO_CODING_UNCERTAINTY`).

---

## 8. Strict Dual-Frontier Separation (`FRONTIER_A` vs. `FRONTIER_B`)

| Property | `FRONTIER_A` (`OBSERVED_DESIGN_FRONTIER`) | `FRONTIER_B` (`RESOURCE_REGIME_EXPANDED_FRONTIER`) |
| :--- | :--- | :--- |
| **Epistemic Status** | **Frozen Empirical Baseline** (`run_20261111_002`) | **Counterfactual Institutional-Design Sensitivity Space** |
| **Candidate Solutions** | Exact **`543`** strictly feasible `GovernanceSolution` packages | Union of frozen `543` packages (`OBSERVED_DESIGN_FRONTIER`) **plus** constraint-feasible `COUNTERFACTUAL_INSTITUTIONAL_DESIGN` / `RESOURCE_REGIME_EXPANSION` packages |
| **Modification Policy** | **READ-ONLY / IMMUTABLE** — existing `326` nondominated and `10 / 248 / 285 / 0` `RobustParetoResult` MUST remain bit-for-bit reproducible | Generated into isolated namespace (`data/processed/preference/counterfactual/`), never overwriting canonical Agent 04 outputs |
| **Utility Provenance** | `100%` `OBSERVED_RESPONDENT_PREFERENCE` (`PreferenceMatrix`) | Observed dimensions + `INSTITUTIONALLY_DERIVED_MECHANISM` bounds + explicitly parameterized `COUNTERFACTUAL_PREFERENCE_ASSUMPTION` sweeps |
| **Role in Policy Brief** | **Primary Empirical Findings** | **Methodological Sensitivity & Institutional Design Exploration** |

---

## 9. Pareto Sensitivity Rules & Testable Questions (`Q-A`–`Q-H`)

### 9.1. Core Sensitivity Rules

1. **Club-Good Viability Is Strictly a Testable Hypothesis**: Whether voluntary `CLUB_GOOD` (or `HYBRID`) regimes enter, expand, or outperform existing options on the Pareto frontier is a **research question to test empirically and structurally—NOT an analytical premise or pre-ordained recommendation**.
2. **Strict Non-Filtering Invariant (`ADR-0005` & `ADR-0008` Extension)**: Economic-good classifications, `RESOURCE_ELIGIBILITY` tags, `ClusterResult` (`preference_profiles.json`), `ValueAssignment` linkages, and coder disagreements may **never** prune or filter alternatives out of `FRONTIER_A`, nor exclude constraint-feasible solutions from `FRONTIER_B`. Only objective `LOGICAL_CONSTRAINT`, `INSTITUTIONAL_CONSTRAINT`, and `STRUCTURAL_DEPENDENCY` rules (such as rejecting an unparameterized `"club"` label missing §5 fields, or `IC-Q07-Q09-DELEGATION-LIABILITY` legal-liability mismatches) may prune candidates, with full `ExclusionRecord` audit logging.

### 9.2. Required Pareto Sensitivity Questions (`Q-A` through `Q-H`)

Any downstream `FRONTIER_B` sensitivity execution MUST answer all eight standardized diagnostic questions:

- **Q-A (Feasible Expansion Audit)**: How many resource-regime variants across `Q10`, `Q11`, `Q12`, `Q09` (and Tier-2 `Q08`) satisfy §5 operational completeness and `SolutionSpaceBuilder` institutional constraints without violating `IC-Q07-Q09-DELEGATION-LIABILITY` or `SD-Q10-Q09-SOCLE-DEPENDENCY`?
- **Q-B (Club-Good Viability Under Partial Identification)**: Under pure `OBSERVED_RESPONDENT_PREFERENCE` + `INSTITUTIONALLY_DERIVED_MECHANISM` partial identification (zero ungrounded club preference assumptions), do any `CLUB_GOOD` or `HYBRID` packages achieve `ROBUSTLY_NONDOMINATED`, `CONDITIONALLY_NONDOMINATED`, or remain `UNRESOLVED_DUE_TO_COUNTERFACTUAL_UTILITY`?
- **Q-C (Non-Member Burden Relief & Spillover Trade-Off)**: Which participants experience guaranteed lower-bound utility improvement strictly from `non_member_compulsory_contribution = 0.0` relative to compulsory-pooling baseline packages, and which participants face risk of reduced pooled/public provision or congestion?
- **Q-D (Multi-Criteria Welfare & Veto Sensitivity)**: How do Rawls/maximin, utilitarian, Nash social welfare, Gini/Atkinson inequality, veto opposition shares ($\tau_{\text{veto}} = 0.35$), and minimax regret shift between `FRONTIER_A` and `FRONTIER_B` across assumption corners?
- **Q-E (Displacement of `OBSERVED_DESIGN_FRONTIER`)**: Does any counterfactual `CLUB_GOOD` / `HYBRID` package strictly Pareto-dominate any of the `326` baseline nondominated solutions or any of the `10` `ROBUSTLY_NONDOMINATED` core packages, and under exactly which provenance tier (`INSTITUTIONALLY_DERIVED_MECHANISM` vs specific `COUNTERFACTUAL_PREFERENCE_ASSUMPTION`)?
- **Q-F (Uncertainty Decomposition)**: Across `FRONTIER_B`, what fraction of non-resolution is attributable to `ADR-0008` `UNRESOLVED_DUE_TO_CODING_UNCERTAINTY` versus counterfactual `UNRESOLVED_DUE_TO_COUNTERFACTUAL_UTILITY`?
- **Q-G (Resource Scope Sensitivity — Conservative vs. `Q08` Conditional)**: How do `FRONTIER_B` findings differ between Tier-1 (`Q10`/`Q11`/`Q12` + risk-caveated `Q09`) and Tier-2 (additionally operationalizing `Q08_hr_management_level` as congestible pooled HR support capacity)?
- **Q-H (Minimal Assumption Threshold)**: If a `CLUB_GOOD` regime requires behavioral preference assumptions to dominate or enter the robust core, what is the *minimal assumption strength* (e.g., threshold acceptance rate among private-preferring respondents or minimum transaction-cost ceiling) required to switch dominance status?

---

## 10. Reporting Requirements (Agent 08 Sink Constraints)

When `AGENT_08_REPORTING_STATUS` is eventually lifted after `FRONTIER_B` integration (or explicit governance override), Agent 08 (`src/reporting/report_generator.py`) MUST obey five mandatory reporting constraints:

1. **Primary vs. Sensitivity Separation**: Present `FRONTIER_A` (`OBSERVED_DESIGN_FRONTIER`, `543` packages, `10 / 248 / 285 / 0`) first and unambiguously as the sole **empirically observed** baseline. Present `FRONTIER_B` (`RESOURCE_REGIME_EXPANDED_FRONTIER`) strictly in a dedicated *Counterfactual Institutional-Design Sensitivity* section.
2. **Zero Survey Attribution of Counterfactuals**: Never assert or imply that survey respondents rated, endorsed, or rejected `FRONTIER_B` club contracts. Every `ReportClaim` referencing `FRONTIER_B` MUST explicitly cite its provenance mix (`OBSERVED_RESPONDENT_PREFERENCE` vs `INSTITUTIONALLY_DERIVED_MECHANISM` vs `COUNTERFACTUAL_PREFERENCE_ASSUMPTION`).
3. **Transparent Unresolved-Utility Reporting**: Report `UNRESOLVED_DUE_TO_COUNTERFACTUAL_UTILITY` counts and mechanisms explicitly alongside `UNRESOLVED_DUE_TO_CODING_UNCERTAINTY` rather than collapsing counterfactual intervals into point averages.
4. **Operational Detail Fidelity**: Whenever describing a `CLUB_GOOD` package, disclose its full §5 parameters (`FINANCING`, `ACCESS`, `non_member_access`, `EXIT`, `capacity_congestion_rule`, `governance_rule`, `pricing_contribution_rule`) rather than a bare `"club"` label.
5. **Retain Conclusions A–F (`RUN_CARD.md`)**: Maintain all `N = 11` small-sample LOO warnings, `NO_STABLE_CLUSTER_STRUCTURE`, `BALDWIN = NOT_APPLICABLE`, `RRV = NOT_APPLICABLE`, and `NO_ROBUST_SINGLE_WINNER` disclosures unmodified.

---

## 11. Rejected Shortcuts

The following shortcuts are explicitly **REJECTED**:

1. **Forcing Economic Goods Onto Non-Resources**: Applying `PRIVATE/CLUB/COMMON/PUBLIC` labels to `Q01`–`Q07`, `Q13`, or `Q14` merely to achieve `100%` coverage across `ENABLED` questions (`Q07` is governance signing authority, not an economic good).
2. **Inferring Club Preference from Non-Payment**: Treating *"I do not want to pay into a common pool"* as equivalent to *"I prefer a voluntary club"* without `EvidenceSpan` backing.
3. **Mutating `OBSERVED_DESIGN_FRONTIER`**: Modifying `src/preference/solution_space.py`'s frozen `543`-package grid or overwriting canonical `data/processed/preference/*.json` / `data/processed/preference/pareto_results.json` / `data/processed/preference/robust_pareto_results.json`.
4. **Re-Running LLMs to Hallucinate Counterfactual Utilities**: Asking `coder_a` or `coder_b` to speculate how respondents *would have* answered unasked club-good contract questions.
5. **Goods-Based or Cluster-Based Filtering**: Using economic-good classifications, `ValueAssignment`, or `ClusterResult` to prune candidate packages from either `FRONTIER_A` or `FRONTIER_B`.
6. **Bare-Label `"Club"` Options**: Inserting `"club_good"` keys into `GovernanceSolution` without operational membership, exit, non-member access, capacity, governance, and contribution rules.
7. **Pre-Judging Club-Good Superiority**: Treating voluntary club provision as an assumed policy winner prior to evaluating `Q-A`–`Q-H` under partial utility identification.

---

## 12. Validation Requirements (Machine-Checkable Invariants)

Downstream unit tests and Agent 09 audit gates MUST enforce:

- **`VG-01` (Baseline Frontier Immutability)**: SHA-256 checksums and exact metrics of `FRONTIER_A` (`543` feasible packages, `326` baseline nondominated, `10 / 248 / 285 / 0` `RobustParetoResult`, `5,973` `ParticipantUtility` records) remain bit-for-bit identical before and after any `FRONTIER_B` sensitivity execution.
- **`VG-02` (Resource Eligibility Gate)**: Zero `INELIGIBLE` subtopics (`Q01`–`Q07`, `Q13`, `Q14`, and diagnostic/process facets of `Q08`/`Q09`/`Q11`/`Q12`) appear in `counterfactual_regime_specs`; Tier-2 `Q08_hr_management_level` enters only when explicitly flagged `CONDITIONAL_RESOURCE_ONLY` and segregated in `Q-G`.
- **`VG-03` (No Ungrounded Unknown Inference)**: Any dimension (`RIVALRY`, `EXCLUDABILITY`, etc.) lacking direct span support or explicit counterfactual declaration remains `UNKNOWN`.
- **`VG-04` (Club-Good 10-Field Structural Completeness)**: Every `CLUB_GOOD` spec passes deterministic validation of `membership_mode == "VOLUNTARY"`, `non_member_compulsory_contribution == 0.0`, `member_access >= non_member_access`, explicit `member_priority`, `non_member_access`, `exit_policy`, `capacity_congestion_rule` (when `RIVAL`/`CONGESTIBLE`), `governance_rule`, and `pricing_contribution_rule`.
- **`VG-05` (Provenance Boundary Enforcement)**: Zero `COUNTERFACTUAL_PREFERENCE_ASSUMPTION` or `INSTITUTIONALLY_DERIVED_MECHANISM` values appear inside `PreferenceMatrix` (`OBSERVED_RESPONDENT_PREFERENCE` only), and zero refusal-to-pay spans are auto-rewritten as club preferences.
- **`VG-06` (`UNRESOLVED_DUE_TO_COUNTERFACTUAL_UTILITY` Retention)**: Partial-ID intervals without counterfactual preference assumptions never emit fabricated scalar `point_utility`; overlapping intervals preserve `UNRESOLVED_DUE_TO_COUNTERFACTUAL_UTILITY` distinct from `UNRESOLVED_DUE_TO_CODING_UNCERTAINTY`.
- **`VG-07` (Pareto Non-Filtering Invariant)**: Zero solutions in `FRONTIER_A` or `FRONTIER_B` are pruned by goods taxonomy, `ClusterResult`, `ValueAssignment`, or coding disagreement (`PROHIBITED_PRUNING_SOURCES` respected).
- **`VG-08` (Double-Count Prevention)**: Counterfactual regime expansions covering `Q09` + `Q06_financial_responsibility_*` or `Q11` facets enforce unified regime parameterization with zero duplicate utility weighting.
- **`VG-09` (Agent 08 Reporting Hold Integrity)**: Pipeline orchestrator and release metadata distinguish `AGENT_08_TECHNICAL_RELEASE = READY` from `AGENT_08_REPORTING_STATUS = HELD_FOR_RESOURCE_REGIME_SENSITIVITY` until dual-frontier sensitivity artifacts or an explicit governance override are registered.

---

## 13. Agent Ownership, Re-Coding Determination & Minimal Downstream Design

### 13.1. Re-Coding Determination: `NEW_LLM_CODING_REQUIRED = NO`

**`NEW_LLM_CODING_REQUIRED = NO`.**

**Architectural Justification**:
1. Both `coder_a` and `coder_b` already executed full `136/136/0` verified Blackwell GPU extraction; existing `themes_codebook_v1`, `reconciled_evidence_v1`, `runs/<run_id>/alternative_crosswalk.json`, and `PreferenceMatrix` contain 100% of observable participant stances on `Q07`–`Q12` (including raw signals such as `"voluntary_pooling"` on `Q11_overhead_allocation_mechanism_2_B_ONLY`).
2. Because the underlying questionnaire did not present participants with explicit counterfactual club contracts (membership fees, exit lock-in periods, residual non-member access schedules, congestion tiers), re-running LLM inference over the same raw text **cannot empirically observe unasked counterfactual preferences** and would risk ungrounded LLM extrapolation.
3. Assigning `RESOURCE_ELIGIBILITY` and constructing structured `CLUB_GOOD` / `PRIVATE_GOOD` / `COMMON_POOL_RESOURCE` / `PUBLIC_GOOD` / `HYBRID` institutional parameterizations over `Q10`, `Q11`, `Q12`, `Q09` (and Tier-2 `Q08`) is a **deterministic structural and decision-theoretic modeling task**, not a natural-language coding task.

### 13.2. Minimal Downstream Scope by Agent

| Agent | Required Scope Under `ADR-0009` | Modules / Interfaces Impacted | Unchanged / Out of Scope |
| :--- | :--- | :--- | :--- |
| **Agent 00** *(This ADR)* | Define `ADR-0009` contracts, freeze `OBSERVED_DESIGN_FRONTIER`, update `docs/ARCHITECTURE.md`, issue `ADR-0007` shared-file change requests. | `docs/DECISIONS/`, `docs/ARCHITECTURE.md`, `docs/AGENT_HANDOFFS/agent_00_handoff.md` | Zero edits to `src/preference/`, `src/contracts.py`, or raw/runtime data. |
| **Agent 03** *(Optional Lightweight Tagging)* | **Only if needed by Agent 04**: Add deterministic CPU-only `resource_eligibility` metadata (`ELIGIBLE \| CONDITIONAL_RESOURCE_ONLY \| INELIGIBLE`) to subtopic metadata—zero LLM calls, zero distribution edits. *(Wait for Agent 11 contract integration or read directly from versioned config.)* | `src/evidence/` (optional deterministic metadata only) | Zero GPU re-coding; zero changes to `reconciled_evidence_v1` distributions or `runs/<run_id>/alternative_crosswalk.json`. |
| **Agent 04** *(Counterfactual Expansion & `FRONTIER_B`)* | Implement isolated counterfactual expansion package (e.g., `src.preference.resource_regimes`) that reads frozen `FRONTIER_A` read-only, builds §5-compliant `RESOURCE_REGIME_EXPANSION` variants, computes §7 partial-ID utility bounds + `FRONTIER_B` Pareto sensitivity (`Q-A`–`Q-H`), and writes exclusively to `data/processed/preference/counterfactual/`. | New additive module under `src/preference/` + `tests/test_preference.py` additions | **MUST NOT** modify `solution_space.py` (`543` packages), `pareto.py` (`326`), or `robust_pareto.py` (`10/248/285/0`) baseline outputs. |
| **Agents 05 & 06** | **No changes required.** Clustering and social-choice voting remain frozen on `OBSERVED_DESIGN_FRONTIER` unless a separate future ADR explicitly authorizes `FRONTIER_B` voting sensitivity. | None | `src/clustering/`, `src/voting/` untouched. |
| **Agent 08** *(Reporting — Held)* | Technical release remains `READY` (`AGENT_08_TECHNICAL_RELEASE = READY`), while reporting execution stays **HELD** (`AGENT_08_REPORTING_STATUS = HELD_FOR_RESOURCE_REGIME_SENSITIVITY`) until `FRONTIER_B` sensitivity outputs are produced and integrated with §10 dual-frontier disclosures. | `src/reporting/` (future dual-frontier template extension) | Do NOT start Agent 08 until hold is lifted. |
| **Agent 09** *(Audit Gate)* | Add `VG-01`–`VG-09` checks during post-`FRONTIER_B` validation (verifying `FRONTIER_A` invariance, provenance separation, Club-Good §5 completeness, and non-filtering). | `src/review/` | No pipeline orchestration role. |
| **Agent 10** *(Memory & Docs)* | Update `docs/PROJECT_STATE.md`, `docs/OPEN_ISSUES.md` (track `ADR-0009` resource-regime sensitivity & reporting hold), and regenerate `docs/AGENT_CONTEXT/` (`python -m src.context_pack --all`) after integration. | `docs/PROJECT_STATE.md`, `docs/OPEN_ISSUES.md`, `docs/AGENT_CONTEXT/` | Per `ADR-0007` change request. |
| **Agent 11** *(Contracts & Orchestration)* | Integrate `ADR-0009` contract models (`ResourceEligibilityStatus`, `GoodRegimeType`, `ResourceRegimeSpec`, `ClubGoodContract`, `ProvenanceCategory`, `CounterfactualParetoStatus`, `FrontierComparisonResult`) into `src/contracts.py`, `schemas/interfaces.json`, and `docs/DATA_CONTRACTS.md`; add versioned counterfactual config & manifest namespace; split orchestrator reporting gate into `AGENT_08_TECHNICAL_RELEASE = READY` and `AGENT_08_REPORTING_STATUS = HELD_FOR_RESOURCE_REGIME_SENSITIVITY`. | `src/contracts.py`, `schemas/interfaces.json`, `docs/DATA_CONTRACTS.md`, `src/pipeline/orchestrator.py`, `runs/<run_id>/manifest.json` | Never mutate existing `39` `FRONTIER_A` manifest entries. |
