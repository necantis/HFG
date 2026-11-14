# ADR-0008: Dual-Coder Preference Reconciliation, Crosswalk, and Uncertainty Contract

- **Decision ID**: `ADR-0008`
- **Date**: 2026-11-14
- **Status**: `APPROVED`
- **Superseded By**: None
- **Affected Modules**: `docs/ARCHITECTURE.md`, `docs/DATA_CONTRACTS.md`, `docs/OPEN_ISSUES.md`, `src/contracts.py`, `schemas/interfaces.json`, `src/evidence/reconciliation.py`, `src/preference/`, `src/review/`
- **Dependencies**: `ADR-0001`, `ADR-0002`, `ADR-0005`, `ADR-0006`, `ADR-0007`

---

## 1. Context

Following completion of the first verified production dual-LLM qualitative coding (`coder_a` and `coder_b`) and Agent 03 evidence reconciliation for active run `run_20261111_002` (branch `agent/03-reconciliation`, merged via PR `#11`), the repository holds empirical reconciliation evidence produced by `src/evidence/reconciliation.py` and documented in `docs/AGENT_HANDOFFS/agent_03_handoff.md`:

- **Subtopic Alignment (`101` proposals $\to$ `84` canonical subtopics)**:
  - `99` Phase-1 discovered subtopics plus `2` Phase-2 `_2` split facets (`101` total coder proposals) consolidated losslessly into `84` canonical subtopics within `Q01`–`Q13` (plus optional `Q14`):
    - `9` `EXACT_MATCH`
    - `8` `SEMANTIC_MATCH`
    - `43` `PARTIAL_OVERLAP` (retained as distinct facets with overlap annotations rather than silently merged)
    - `7` `CODER_A_ONLY`
    - `17` `CODER_B_ONLY`
    - `0` silent `CONFLICT` merges
- **Preference Reconciliation (`284` aligned records)**:
  - `18` `PRESERVED_MISSING_OR_NON_PREFERENCE` (explicit missing/non-substantive/no-opinion/ambiguous cells preserved with zero synthetic preference)
  - `1` `AGREEMENT_EXACT`
  - `22` `AGREEMENT_DISTRIBUTION_ONLY_INTERPRETATION_FLAGGED`:
    - `17` `PROBABILITY_INTERPRETATION_DISAGREEMENT` (identical distributions and keys, differing `probability_interpretation`)
    - `5` `ALTERNATIVE_KEY_CROSSWALK_PENDING` (identical distributions and interpretations, aligned only via lexical/scenario heuristics pending formal crosswalk approval)
  - `243` `UNRESOLVED_RECONCILIATION_POLICY`:
    - `2` `PREFERENCE_DISTRIBUTION_DISAGREEMENT` (in `Q06`, with total variation distance $\text{TVD} = 0.15$ and $\text{TVD} = 0.45$)
    - `83` `ALTERNATIVE_VOCABULARY_MISMATCH` (across `Q01`–`Q05`, `Q08`–`Q14`)
    - `28` `SINGLE_CODER_PARTICIPANT_OMISSION` (subtopic aligned across both coders, participant coded by only one coder)
    - `130` `SINGLE_CODER_SUBTOPIC_GRANULARITY` (subtopic exists in one coder's facet taxonomy only)
- **Comparable Dual-Observed Cells (`108` paired cells)**:
  - Exact distribution agreement = `0.92`
  - Modal agreement = `0.96`
  - Mean $1 - \text{TVD} = 0.976$
  - Pairwise `probability_interpretation` agreement = `0.4907` (`49.07%`)

Agent 03 strictly honored `ADR-0005` and `docs/DATA_CONTRACTS.md` by refusing to fabricate consensus through undocumented averaging (`reconciled_alternative_probabilities = None` for all `265` flagged/unresolved preference records) and correctly flagged `AGENT_04_RELEASE = BLOCKED`.

---

## 2. Problem

Agent 04 (`src/preference/`) cannot construct `PreferenceMatrix`, `ParticipantUtility`, `FeasibleAlternative`, `ParetoResult`, or `RobustParetoResult` until five methodological gaps in the existing contracts are formally resolved:

1. **No Authorized Disagreement Combination Policy**: Existing contracts define no valid rule when `coder_a` and `coder_b` distributions disagree (`TVD > 1e-4`), and `CodingResult.reconciliation_method` in `src/contracts.py` still contains an uncalibrated legacy literal `"CONFIDENCE_WEIGHTED_DISTRIBUTION"`.
2. **Unresolved Alternative-Vocabulary Crosswalk Policy**: `83` `ALTERNATIVE_VOCABULARY_MISMATCH` and `5` `ALTERNATIVE_KEY_CROSSWALK_PENDING` records lack an explicit Level 2 crosswalk contract distinguishing valid canonical mappings from structurally incompatible alternative spaces.
3. **Undefined Treatment of Single-Coder Facets**: `158` single-coder records (`28` participant omissions, `130` subtopic granularity facets) lack an explicit uncertainty representation, risking silent zero-imputation or deletion of minority positions.
4. **Open Methodological Contract (`ISSUE-005`)**: With `probability_interpretation` agreeing on only `49.07%` of paired cells, numerically identical probability distributions carry incompatible epistemic meanings (`epistemic_uncertainty_over_preference`, `explicit_mixed_preference`, `conditional_or_context_dependent`), which cannot be collapsed silently into uniform cardinal utilities.
5. **Point-Estimate Simplex Constraint Mismatch in `PreferenceCell`**: `PreferenceCell` in `src/contracts.py` currently requires a single `alternative_probabilities` dictionary summing to $1.0 \pm 10^{-4}$ for every `observed_usable` cell, leaving no schema-valid way to pass an epistemic uncertainty set directly to Agent 04 when a single point vector is unwarranted by evidence.

---

## 3. Decision

HFG adopts an **Uncertainty-Preserving, Crosswalk-Gated Reconciliation Contract** for Agent 03 $\to$ Agent 04 handoff. Numerical point-collapsing of unresolved coder disagreement is **prohibited** as a canonical representation; coding uncertainty, crosswalk granularity, single-coder partial identification, and interpretation heterogeneity MUST propagate explicitly into Agent 04's `ParticipantUtility` and `RobustParetoResult`.

### 3.1. Default Averaging & Aggregation Rules (Explicit Authorizations and Prohibitions)

1. **Confidence-Weighted Averaging (`p_reconciled = (c_A p_A + c_B p_B) / (c_A + c_B)`): `FORBIDDEN`**
   - **Conditional Exception Threshold**: Confidence-weighted averaging is **strictly forbidden** unless the repository contains an empirically validated, out-of-sample calibration study against blind human gold adjudication demonstrating that both LLM families' self-reported `coder_confidence` values are statistically calibrated probability aggregation weights. **No such calibration evidence exists in the repository.**
   - **Architectural Rationale**:
     - *Uncalibrated cross-family scale mismatch*: `coder_a` and `coder_b` belong to distinct model families (`DeepSeek-R1-Distill` vs `Mistral-Small`); self-reported confidence scores are uncalibrated and systematically non-comparable across architectures.
     - *Orthogonality invariant (`ADR-0005`)*: `coder_confidence` measures an LLM's self-assessed extraction certainty, not a preference intensity or Bayesian likelihood weight over another coder's hypothesis.
     - *Fabrication of unsupported distributions*: When `p_A` and `p_B` represent distinct substantive stances or mutually incompatible interpretations (e.g., `Q06` with $\text{TVD} = 0.45$), a confidence-weighted convex blend fabricates an intermediate distribution asserted by neither coder and masks bimodality behind false point precision.
   - **Contract Action**: The legacy enum value `"CONFIDENCE_WEIGHTED_DISTRIBUTION"` in `CodingResult.reconciliation_method` (`src/contracts.py` and `schemas/interfaces.json`) MUST be removed and replaced with uncertainty-preserving reconciliation statuses.

2. **Unweighted Arithmetic Averaging (`0.5 * p_A + 0.5 * p_B`): `REJECTED` as default canonical representation (`CONDITIONAL` solely as labeled derived sensitivity scenario)**
   - **Why rejected as default**: An unweighted mean still manufactures a synthetic midpoint vector not supported by either coder whenever $\text{TVD}(p_A, p_B) > 10^{-4}$ or interpretations diverge, falsely shrinking variance to zero in downstream point utilities.
   - **Narrow robustness exception**: Agent 04 MAY evaluate `0.5 * p_A + 0.5 * p_B` inside Monte Carlo or convex-hull sensitivity sweeps **only** when explicitly tagged `scenario_origin = "DERIVED_ROBUSTNESS_CONVEX_BARYCENTER"`, and MUST NEVER store it as `resolved_point_distribution` or canonical evidence.

3. **Majority Selection: `REJECTED`**
   - Undefined for $K = 2$ independent coders; breaking ties via a heuristic reintroduces arbitrary bias, and adding an ungrounded third coder breaks the dual-LLM architecture.

4. **Highest-Confidence Coder Wins ($\arg\max_{j \in \{A, B\}} c_j$): `REJECTED`**
   - Systematically rewards whichever LLM family exhibits higher overconfidence, discards valid minority interpretations from the other family, and collapses genuine disagreement into an artificial zero-uncertainty point estimate.

5. **Coder-A Precedence & Coder-B Precedence: `REJECTED`**
   - Violates coder symmetry and undermines the core dual-LLM independence invariant by converting dual coding into single-coder bias whenever coders disagree or omit a cell.

---

### 3.2. Seven-Level Reconciliation Hierarchy (Strict Evaluation Order)

Reconciliation and downstream matrix construction MUST proceed strictly in Levels 0 through 6. No higher-numbered numeric operation may execute unless lower-numbered comparability gates pass.

| Level | Gate / Operation | Normative Rule | Valid Output / Status |
| :--- | :--- | :--- | :--- |
| **Level 0** | **Preserve Missing & Non-Preference Evidence** | Preserve `missing_raw_blank`, `missing_non_substantive`, `explicit_no_opinion`, `explicit_insufficient_experience`, `explicit_insufficient_information`, `ambiguous`, `not_mentioned_in_response`, and `not_applicable_frame` verbatim. Zero synthetic preferences or `0.0` imputation. | `PRESERVED_MISSING_OR_NON_PREFERENCE`, `NOT_MENTIONED_ABSENCE` |
| **Level 1** | **Canonical Subtopic Correspondence** | Align coder subtopic proposals strictly within `Q01`–`Q13` (and optional `Q14` separately). Never force label-only merges across distinct concepts or across questions; retain minority positions and Phase-2 split facets. | `EXACT_MATCH`, `SEMANTIC_MATCH`, `PARTIAL_OVERLAP`, `CODER_A_ONLY`, `CODER_B_ONLY`, `CONFLICT` |
| **Level 2** | **Alternative-Vocabulary Crosswalk** | Establish explicit per-question/subtopic key equivalence between `coder_a` and `coder_b` alternative keys **before** any probability comparison. | `EXACT_KEY_MATCH`, `SEMANTIC_KEY_MATCH`, `SCENARIO_PREFIX_MATCH`, `PARTIAL_CROSSWALK`, `NO_VALID_CROSSWALK` *(or `SINGLE_CODER_ONLY`)* |
| **Level 3** | **Preference Distribution Comparison** | Compute `TVD`, $L_1$, `JSD`, modal comparison, and bounds **only** when Level 1 establishes subtopic correspondence and Level 2 yields a valid comparable crosswalk (`EXACT_KEY_MATCH`, `SEMANTIC_KEY_MATCH`, `SCENARIO_PREFIX_MATCH`, or comparable subspace under `PARTIAL_CROSSWALK`). Never compare unaligned distributions under `NO_VALID_CROSSWALK`. | `DIST_EXACT_MATCH` ($\text{TVD} \le 10^{-4}$), `DIST_DISAGREEMENT` ($\text{TVD} > 10^{-4}$), `NOT_COMPARABLE_CROSSWALK` |
| **Level 4** | **`probability_interpretation` Compatibility** | Evaluate `(interp_a, interp_b)` explicitly per Section 3.5. Numerically identical vectors with differing interpretations MUST NOT be promoted to full consensus (`AGREEMENT_EXACT`). | `INTERP_EXACT_MATCH`, `INTERP_FLAGGED_COMPATIBLE`, `INTERP_DIVERGENCE` |
| **Level 5** | **True Disagreement as Uncertainty Set** | Preserve genuine distribution divergence ($\text{TVD} > 10^{-4}$), `PARTIAL_CROSSWALK` residual divergence, and `NO_VALID_CROSSWALK` dual spaces as explicit uncertainty sets $P_i$ with `resolved_point_distribution = None`. | `UNCERTAINTY_SET_DUAL_CODER`, `UNCERTAINTY_SET_CROSSWALK_PARTIAL`, `UNCERTAINTY_SET_UNALIGNED` |
| **Level 6** | **Single-Coder Epistemic Uncertainty** | Treat `SINGLE_CODER_PARTICIPANT_OMISSION` (`28` cells) and `SINGLE_CODER_SUBTOPIC_GRANULARITY` (`130` cells) as one-sided epistemic uncertainty / partial identification—**never** assign `0.0` to the non-coding coder or erase minority positions. | `SINGLE_CODER_OMISSION_UNCERTAINTY`, `SINGLE_CODER_GRANULARITY_UNCERTAINTY` |

#### Level 2 Crosswalk Status Definitions
- **`EXACT_KEY_MATCH`**: `sorted(keys_a) == sorted(keys_b)` with identical canonical alternative meanings.
- **`SEMANTIC_KEY_MATCH`**: Deterministic 1-to-1 bijection between `keys_a` and `keys_b` grounded in an authorized per-question/domain-neutral glossary or verified bilingual equivalence.
- **`SCENARIO_PREFIX_MATCH`**: Deterministic 1-to-1 alignment via shared explicit `scenario_N` identifiers (`scenario_1`, `scenario_2`, ...) after verifying prefix identity maps to the same institutional option.
- **`PARTIAL_CROSSWALK`**: Only a strict subset of alternatives aligns 1-to-1 or many-to-1 onto canonical options (e.g., one coder splits an option into finer sub-variants while the other keeps a coarse option, or shares core alternatives plus an unmapped extra alternative). Comparable **only** after recording explicit residual unmapped probability mass $m_{\text{unmapped}}$; MUST retain `resolved_point_distribution = None` unless a lossless deterministic aggregation map over equivalent sub-alternatives is explicitly justified in the crosswalk spec.
- **`NO_VALID_CROSSWALK`**: Coder alternative keys represent incompatible decision axes, mismatched supports with zero verified mapping, or conflicting framing. Distribution comparison is forbidden; `TVD`/`JSD` remain `None`; both raw distributions are preserved separately under `coder_a_distribution` and `coder_b_distribution`.

---

### 3.3. Formal Uncertainty Set Contract

Let $\Delta(\mathcal{A}_m)$ denote the probability simplex over canonical alternatives $\mathcal{A}_m$ for subtopic $m$ (after a valid Level 2 crosswalk). For any dual-observed participant $\times$ subtopic cell $i = (p, q, m)$ with genuine coder disagreement or partial comparability:

1. **Primary Canonical Uncertainty Set (Discrete Coder Scenario Set)**:
   $$P_i = \{p_i^A, p_i^B\} \subset \Delta(\mathcal{A}_m)$$
   Every element in $P_i$ is an empirical distribution directly produced and span-grounded by an independent coder (`coder_a` or `coder_b`). When $p_i^A = p_i^B$ within $10^{-4}$ and interpretations match (`AGREEMENT_EXACT`), $P_i$ collapses to the singleton $\{p_i^*\}$.

2. **Authorized Derived Robustness Representations (For Agent 04 Sensitivity Analysis Only)**:
   Agent 04 MAY derive and evaluate all three of the following representations downstream from $P_i$:
   - **Discrete scenario set ($P_i = \{p_i^A, p_i^B\}$)**: **Mandatory primary ensemble** — preserves exact coder-supported multimodal hypotheses without introducing unsupported mixtures.
   - **Convex hull / credal set ($\mathcal{C}_i = \text{conv}(\{p_i^A, p_i^B\}) = \{ \lambda p_i^A + (1-\lambda) p_i^B : \lambda \in [0, 1] \}$)**: **Authorized derived robustness family** — captures continuous interpolation sensitivity when coders represent endpoints of an interval of plausibility.
   - **Marginal lower/upper probability bounds ($[l_{i,k}, u_{i,k}]$)**:
     $$l_{i,k} = \min(p_{i,k}^A, p_{i,k}^B), \qquad u_{i,k} = \max(p_{i,k}^A, p_{i,k}^B), \qquad \forall k \in \mathcal{A}_m$$
     **Authorized derived box/outer envelope** — useful for analytical upper/lower utility bracketing ($\sum_k l_{i,k} \le 1 \le \sum_k u_{i,k}$). Any simplex draw sampled inside $[l_{i,k}, u_{i,k}]$ when $|\mathcal{A}_m| \ge 3$ is strictly an outer-envelope robustness test.

3. **Explicit Provenance & Non-Fabrication Assumption**:
   - No intermediate vector ($\lambda \in (0, 1)$ in $\mathcal{C}_i$ or arbitrary point inside $[l_i, u_i]$) may be introduced without explicitly labeling its evaluation trace as `DERIVED_ROBUSTNESS_SCENARIO` (never `OBSERVED_CODER_EVIDENCE`).
   - Whenever $|\,P_i\,| > 1$, `resolved_point_distribution` MUST remain `None` in the canonical cell contract; Agent 04 computes set-valued / scenario-indexed utilities directly over $P_i$ (and optional derived bounds).

4. **Unaligned Crosswalk Uncertainty (`NO_VALID_CROSSWALK`)**:
   - When Level 2 returns `NO_VALID_CROSSWALK`, $p_i^A \in \Delta(\mathcal{A}_{m,A})$ and $p_i^B \in \Delta(\mathcal{A}_{m,B})$ live on distinct key spaces and cannot be averaged or interval-min/maxed key-wise.
   - `preference_uncertainty_set` stores `representation_type = "DISJOINT_CODER_HYPOTHESES"` containing both raw distributions `{"coder_a": p_i^A, "coder_b": p_i^B}` keyed by coder-qualified namespaces until mapped onto `GovernanceSolution` postures via explicit solution-alignment rules (or marked `UNRESOLVED_DUE_TO_CODING_UNCERTAINTY` if a solution's posture on $m$ cannot be mapped cleanly to one or both coder vocabularies).

---

### 3.4. Single-Coder Facets Contract (`SINGLE_CODER_PARTICIPANT_OMISSION` & `SINGLE_CODER_SUBTOPIC_GRANULARITY`)

Both single-coder patterns observed in `run_20261111_002` represent **epistemic uncertainty due to asymmetric coder detection/granularity**, NOT evidence of zero preference by the participant or non-coding coder:

| Single-Coder Class | Count in `run_20261111_002` | Epistemic Meaning | Mandatory Rule for Non-Coding Coder | Downstream Partial-Identification Treatment |
| :--- | :---: | :--- | :--- | :--- |
| **`SINGLE_CODER_PARTICIPANT_OMISSION`** | `28` | Canonical subtopic $m$ was discovered by **both** coders (`EXACT_MATCH` / `SEMANTIC_MATCH`), yet only one coder extracted a usable `CodingResult` for participant $i$. | Non-coding coder MUST remain `None` / `EPISTEMICALLY_UNOBSERVED`. **Strictly forbidden** to impute `0.0` probabilities or `0.0` preference. | **Partial Identification (One-Sided Evidenced vs Unobserved Bound)**: Primary evidenced scenario uses the active coder's span-verified distribution $p_i^{\text{active}}$ with `single_coder_uncertainty_flag = True`; robustness bounds test sensitivity between (a) active coder distribution (span exists!) and (b) non-informative / structural abstention sensitivity (`w_{i,m} \in [0, w_{i,m}^{\text{active}}]`), tracking whether dominance flips. |
| **`SINGLE_CODER_SUBTOPIC_GRANULARITY`** | `130` | Subtopic $m$ exists in only one coder's facet taxonomy (`CODER_A_ONLY`, `CODER_B_ONLY`, `PARTIAL_OVERLAP`, or Phase-2 `_2` split). Often reflects finer decomposition of spans already coded under a broader parent subtopic by the other coder. | Non-coding coder MUST remain `None` / `EPISTEMICALLY_UNOBSERVED`. **Strictly forbidden** to assign `0.0` preference or discard as noise. | **One-Sided Structural Uncertainty with Double-Count Guard**: Retain minority and split facets in `CanonicalSubtopic` and `FeasibleAlternative`. When computing `ParticipantUtility`, evaluate: (i) **full-granularity scenario** (including single-coder facets at normalized question weight to avoid erasing minority positions) and (ii) **parent-deduplicated / overlapping-facet sensitivity scenario** (preventing double-weighting of a participant's overlapping `PARTIAL_OVERLAP` text spans across parent + child facets). |

**Minority Position Invariant**: Any single-coder subtopic flagged `is_minority_position = True` or originating from a single participant span MUST remain eligible for `FeasibleAlternative` and `GovernanceSolution` evaluation and visible in `RobustParetoResult`.

---

### 3.5. Probability Interpretation Policy & Resolution of `ISSUE-005`

`ProbabilityInterpretation` distinguishes three fundamentally different epistemic meanings attached to `alternative_probabilities`:

1. **`epistemic_uncertainty_over_preference`**:
   - *Meaning*: The participant favors a single institutional option $a^* \in \mathcal{A}_m$, and $p_{i,m}(k)$ expresses the coder's posterior plausibility that $a^* = k$ given ambiguous or brief text.
   - *Utility Semantics*: Under realized-choice Monte Carlo draws, the participant's latent stance is a discrete draw $a_\omega \sim \text{Categorical}(p_{i,m})$ (inducing full $0/1$ match utility variance across draws), **not** an interior compromise. Only under explicit expected-utility evaluation does $\sum_k p_{i,m}(k) \alpha_{m,k}(s)$ act as expected alignment.

2. **`explicit_mixed_preference`**:
   - *Meaning*: The participant explicitly endorses a hybrid, compromise, or multi-level allocation (e.g., splitting authority or funding across multiple levels).
   - *Utility Semantics*: $p_{i,m}$ represents **direct fractional/portfolio alignment** with institutional composition $\alpha_{m}(s)$: $u_{i,m}(s) = \sum_{k \in \mathcal{A}_m} p_{i,m}(k) \alpha_{m,k}(s)$ (or negative divergence from the target blend) **without** collapsing to a single vertex draw.

3. **`conditional_or_context_dependent`**:
   - *Meaning*: The participant states an "if condition $C$, then option $A$; otherwise option $B$" posture (conditional on implementation prerequisites, voluntariness, lab capacity, or structural rules).
   - *Utility Semantics*: Cannot be evaluated purely as unconditional random noise; represents **regime-contingent choice** whose alignment depends on whether `GovernanceSolution` $s$ satisfies the conditioning institutional context (tracked via structural sensitivity and worst-case / minimax-regret bounds across regimes).

#### Compatibility Rules When Numerically Equal (`TVD <= 1e-4`) With Differing Interpretations (`17` cells in `run_20261111_002`)
- **Rule 4A — Prohibition on Silent Equivalence**: If $p_i^A \approx p_i^B$ ($\text{TVD} \le 10^{-4}$) on an aligned crosswalk (`EXACT_KEY_MATCH` / `SEMANTIC_KEY_MATCH` / `SCENARIO_PREFIX_MATCH`) **but** `interp_a != interp_b`, the cell MUST remain `AGREEMENT_DISTRIBUTION_ONLY_INTERPRETATION_FLAGGED` (NEVER `AGREEMENT_EXACT`).
- **Rule 4B — When Preference-Compatible (Distributional Level Only)**: Two differing interpretations are **distributionally preference-compatible** when:
  1. Level 2 crosswalk is valid and aligned ($\text{TVD} \le 10^{-4}$),
  2. Either both assign $\ge 0.99$ mass to a single deterministic modal option (`p_max >= 0.99` -> zero variance under categorical vs mixed draw), **or** they agree on modal ordering and support under linear expected alignment.
  Even when distributionally compatible for expected-value diagnostics, the cell **remains flagged** (`uncertainty_class = "INTERPRETATION_DIVERGENCE"`).
- **Rule 4C — Mandatory Retention in Robustness Analysis**: Whenever `interp_a != interp_b` (and $\max_k p_k < 0.99$ or conditional framing is present), Agent 04 **MUST retain both interpretations** in `preference_uncertainty_set.interpretation_variants = [interp_a, interp_b]` and evaluate both utility operators across Monte Carlo robustness sweeps (categorical choice draw for `epistemic_uncertainty_over_preference`, fixed fractional blend for `explicit_mixed_preference`, and regime-contingent worst/best-case bracket for `conditional_or_context_dependent`).

**Resolution of `ISSUE-005`**: `ISSUE-005` is hereby resolved at the architectural and methodological contract level by replacing implicit point-utility assumptions with explicit `interpretation_variants` propagation in `PreferenceCell`, `ParticipantUtility`, and `RobustParetoResult`.

---

## 4. Rejected Alternatives

| Alternative Considered | Why Rejected |
| :--- | :--- |
| **Confidence-weighted averaging** $\frac{c_A p_A + c_B p_B}{c_A + c_B}$ | Self-reported LLM confidences are uncalibrated and non-comparable across architectures; violates `ADR-0005` orthogonality (`coder_confidence != preference`); fabricates synthetic interior mixtures. |
| **Unweighted arithmetic mean** $\frac{1}{2}(p_A + p_B)$ as canonical cell | Destroys bimodal disagreement signal ($\text{TVD} = 0.45$) and manufactures unsupported point estimates. Allowed only as an explicitly labeled derived scenario inside sensitivity analysis. |
| **Majority vote / 3rd tie-breaker LLM** | Undefined for 2 coders; adding an unbudgeted adjudicator LLM for canonical averaging breaks the validated dual-LLM symmetry without calibration guarantees. |
| **Highest-confidence / Coder-A / Coder-B precedence** | Introduces systematic model-family bias and discards span-verified evidence from the other independent coder. |
| **Assign `0.0` to silent coder on single-coder facets** | Conflates absence of coder extraction with evidence of zero preference; distorts question weights and erases minority subtopics. |
| **Collapse `probability_interpretation` differences when `p_A == p_B`** | Silently treats epistemic ambiguity, fractional mixing, and conditional rules as interchangeable cardinal utilities (`ISSUE-005`). |

---

## 5. Downstream Contract Specification (Agent 03 $\to$ Agent 04)

Every reconciled preference cell delivered to Agent 04 MUST conform to the following contract structure (implemented via schema update in `src/contracts.py` / `schemas/interfaces.json` and adapter/emitter alignment in `src/evidence/reconciliation.py`):

| Field | Type | Required | Normative Semantics |
| :--- | :--- | :---: | :--- |
| `participant_id` | `str` | Yes | Immutable participant identifier from `answers_normalized_v1`. |
| `question_id` | `str` | Yes | `Q01`–`Q13` primary spine (or `Q14` optional contextual remarks). |
| `canonical_subtopic_id` | `str` | Yes | Canonical subtopic identifier from Level 1 alignment. |
| `coder_a_distribution` | `dict[str, float] \| None` | Yes | Raw simplex distribution emitted by `coder_a` (or `None` if absent/non-preference). |
| `coder_b_distribution` | `dict[str, float] \| None` | Yes | Raw simplex distribution emitted by `coder_b` (or `None` if absent/non-preference). |
| `canonical_alternative_crosswalk` | `CanonicalAlternativeCrosswalk` | Yes | Level 2 crosswalk object: `crosswalk_status` (`EXACT_KEY_MATCH \| SEMANTIC_KEY_MATCH \| SCENARIO_PREFIX_MATCH \| PARTIAL_CROSSWALK \| NO_VALID_CROSSWALK \| SINGLE_CODER_ONLY`), `comparable: bool`, `coder_a_to_canonical: dict[str, str]`, `coder_b_to_canonical: dict[str, str]`, `canonical_keys: list[str]`, `unmapped_keys_a: list[str]`, `unmapped_keys_b: list[str]`, `crosswalk_rule_id: str \| None`. |
| `coder_a_probability_interpretation` | `ProbabilityInterpretation \| None` | Yes | Interpretation emitted by `coder_a`. |
| `coder_b_probability_interpretation` | `ProbabilityInterpretation \| None` | Yes | Interpretation emitted by `coder_b`. |
| `semantic_importance_a` | `float \| None` | Yes | Subtopic salience from `coder_a` $\in [0, 1]$ (strictly separate from preference). |
| `semantic_importance_b` | `float \| None` | Yes | Subtopic salience from `coder_b` $\in [0, 1]$ (strictly separate from preference). |
| `coder_confidence_a` | `float \| None` | Yes | Extraction confidence from `coder_a` $\in [0, 1]$ (never an aggregation weight). |
| `coder_confidence_b` | `float \| None` | Yes | Extraction confidence from `coder_b` $\in [0, 1]$ (never an aggregation weight). |
| `agreement_status` | `AgreementStatus` | Yes | Explicit multi-axis agreement state: `EXACT_AGREEMENT \| DISTRIBUTION_AGREEMENT_INTERP_FLAGGED \| DISTRIBUTION_AGREEMENT_CROSSWALK_PENDING \| DISTRIBUTION_DISAGREEMENT \| VOCABULARY_MISMATCH \| SINGLE_CODER_ONLY \| NON_PREFERENCE_AGREEMENT`. |
| `uncertainty_class` | `UncertaintyClass` | Yes | Explicit epistemic uncertainty class: `NONE_CONSENSUS \| PRESERVED_MISSINGNESS \| INTERPRETATION_DIVERGENCE \| DUAL_CODER_DISTRIBUTION_SET \| CROSSWALK_PARTIAL_OR_UNALIGNED \| SINGLE_CODER_PARTIAL_ID_OMISSION \| SINGLE_CODER_PARTIAL_ID_GRANULARITY`. |
| `preference_uncertainty_set` | `PreferenceUncertaintySet` | Yes | Structured formal set: `representation_type` (`"EMPTY_MISSING" \| "SINGLETON" \| "DISCRETE_CODER_SET" \| "PARTIAL_CROSSWALK_SET" \| "DISJOINT_CODER_HYPOTHESES" \| "SINGLE_CODER_PARTIAL_ID"`), `discrete_scenarios: list[dict[str, float]]` (on canonical keys when comparable), `lower_bounds: dict[str, float] \| None`, `upper_bounds: dict[str, float] \| None`, `interpretation_variants: list[ProbabilityInterpretation]`, `single_coder_active_side: Literal["coder_a", "coder_b"] \| None`, `non_coding_coder_state: Literal["EPISTEMICALLY_UNOBSERVED"] \| None`, `allows_derived_convex_hull: bool`. |
| `source_evidence_ids` | `list[str]` | Yes | All offset-verified `EvidenceSpan` IDs (`coder_a` + `coder_b`) and `response_id` links. |
| `reconciliation_status` | `ReconciliationStatus` | Yes | `AGREEMENT_EXACT \| AGREEMENT_DISTRIBUTION_ONLY_INTERPRETATION_FLAGGED \| RESOLVED_WITH_UNCERTAINTY_SET \| UNRESOLVED_CROSSWALK \| PRESERVED_MISSING_OR_NON_PREFERENCE \| NOT_MENTIONED_ABSENCE`. |
| `resolved_point_distribution` | `dict[str, float] \| None` | **Optional** | Present **only** when `reconciliation_status == "AGREEMENT_EXACT"` (or deterministic post-crosswalk singleton consensus with identical interpretation). **MUST be `None`** whenever evidence supports only an uncertainty set, `PARTIAL_CROSSWALK`, `NO_VALID_CROSSWALK`, `INTERPRETATION_DIVERGENCE`, or single-coder partial identification. |

### Simplex & Non-Missingness Validator Semantics
- `PreferenceCell.validate_simplex(tolerance=1e-4)` MUST enforce:
  1. When `missingness_state` is non-usable: `resolved_point_distribution is None`, `alternative_probabilities == {}`, and `preference_uncertainty_set.discrete_scenarios == []`.
  2. When `missingness_state == observed_usable`:
     - Every raw non-`None` distribution (`coder_a_distribution`, `coder_b_distribution`) and every scenario in `preference_uncertainty_set.discrete_scenarios` MUST sum to $1.0 \pm 10^{-4}$.
     - If `resolved_point_distribution` is not `None`, it MUST sum to $1.0 \pm 10^{-4}$ AND `uncertainty_class` MUST be `NONE_CONSENSUS` (or explicitly documented singleton agreement).
     - `resolved_point_distribution is None` is **valid and required** whenever `uncertainty_class != "NONE_CONSENSUS"`.

---

## 6. Agent 04 Robustness & Pareto Propagation Contract

Agent 04 (`src/preference/`) MUST propagate `preference_uncertainty_set` end-to-end across all four modules:

1. **`PreferenceMatrix` (`src/preference/preference_matrix.py`)**:
   - Retains strict separation between `Q01`–`Q13` primary analytical matrix and optional `Q14` contextual annotations.
   - Preserves `missingness_state != observed_usable` cells strictly un-imputed (`{}`), never converting `SINGLE_CODER_*` silence into `0.0`.
   - Exposes both canonical uncertainty-set cells and summary diagnostic counts by `uncertainty_class`.

2. **`ParticipantUtility` (`src/preference/utilities.py`)**:
   - Computes scenario-indexed utility $U_i(s \mid \omega)$ for each participant $i$, constraint-feasible solution $s$, and Monte Carlo / credal corner draw $\omega \in \Omega$:
     - **Dual-coder distribution draws**: Sample $p_{i,m}^{(\omega)}$ from discrete set $P_i = \{p_i^A, p_i^B\}$ (primary ensemble), plus explicitly labeled sensitivity sweeps over $\text{conv}(P_i)$ / marginal bounds $[l_i, u_i]$ (`scenario_origin = "DERIVED_ROBUSTNESS_SCENARIO"`).
     - **Interpretation-aware operator (`ISSUE-005`)**:
       - `epistemic_uncertainty_over_preference`: draw latent discrete option $a_\omega \sim \text{Categorical}(p_{i,m}^{(\omega)})$ (or report both realized-draw distribution and expected-alignment sensitivity);
       - `explicit_mixed_preference`: evaluate linear fractional alignment $\sum_k p_{i,m}^{(\omega)}(k) \alpha_{m,k}(s)$;
       - `conditional_or_context_dependent`: evaluate regime-contingent alignment conditioned on solution constraints, bracketing satisfied vs unsatisfied prerequisite bounds.
     - **Single-coder facets**: Evaluate primary evidenced scenario alongside structural partial-identification bounds (including `PARTIAL_OVERLAP` deduplication guard for `SINGLE_CODER_SUBTOPIC_GRANULARITY`).
     - **Semantic importance weights**: Sample $\tilde{w}_{i,m}^{(\omega)} \in \{w_{i,m}^A, w_{i,m}^B\}$ (or single-coder weight where applicable); never use `coder_confidence` as a utility or weight multiplier.
   - Emits `utility_ci_lower_95`, `utility_ci_upper_95`, `utility_std_error`, and deterministic min/max scenario utility bounds; `point_utility` may be `None` or an explicitly labeled ensemble mean/median summary when uncertainty sets are active.

3. **`FeasibleAlternative` & `GovernanceSolution` (`src/preference/solution_space.py`)**:
   - **Constraint-Only Pruning Invariant (Strict)**: Alternatives and composite solutions MAY be pruned **exclusively** by explicit logical constraints, institutional mandate constraints, and structural dependencies.
   - **Absolute Non-Pruning Prohibitions**: No alternative or solution may EVER be removed, down-weighted, or filtered out because of:
     - participant clusters / `ClusterResult` (`preference_profiles.json`),
     - organisational values / `ValueAssignment` linkages,
     - unresolved coder disagreement, `NO_VALID_CROSSWALK`, or single-coder minority subtopics.

4. **`ParetoResult` & `RobustParetoResult` (`src/preference/pareto.py`, `src/preference/robust_pareto.py`)**:
   - Compute participant-level Pareto dominance over valid (non-all-missing) participants for every realization $\omega \in \Omega$, tracking dominance stability and multi-criteria rankings (Rawls/maximin, utilitarian, Nash social welfare, Gini/Atkinson inequality, opposition/veto share, minimax regret).
   - `RobustParetoResult` MUST classify every constraint-feasible solution $s \in \mathcal{S}_{\text{feasible}}$ into at least the following four mutually exclusive robustness statuses:
     1. **`ROBUSTLY_DOMINATED`**: Strictly Pareto-dominated by at least one feasible $s'$ across **all** admissible uncertainty realizations $\omega \in \Omega$ (frontier inclusion probability $= 0.0$ even under worst-case coding/interpretation/partial-ID realizations).
     2. **`ROBUSTLY_NONDOMINATED`**: Nondominated across all admissible uncertainty realizations $\omega \in \Omega$ (strict robust Pareto core: inclusion probability $= 1.0$, or reported jointly with configurable $\tau_{\text{robust}}$ inclusion threshold in `pareto_mc_config_v1` while retaining exact $1.0$ core identification).
     3. **`CONDITIONALLY_NONDOMINATED`**: Nondominated under a strict nonempty subset of admissible uncertainty realizations $\omega \in \Omega$ ($0 < P(\text{nondominated}) < 1$), accompanied by the exact coder, crosswalk, single-coder, or `probability_interpretation` regime under which it holds nondominated status.
     4. **`UNRESOLVED_DUE_TO_CODING_UNCERTAINTY`**: Dominance comparisons against at least one frontier candidate cannot be signed deterministically because the comparison hinges on cells with `NO_VALID_CROSSWALK` or structurally unidentifiable single-coder bounds; MUST remain explicitly surfaced in `RobustParetoResult` and stakeholder reporting rather than silently dropped as dominated.

---

## 7. Agent Responsibilities

| Agent | Responsibilities Under `ADR-0008` |
| :--- | :--- |
| **Agent 00** (System Architect) | Maintains `ADR-0008` and updates `docs/ARCHITECTURE.md` invariants; reviews contract alignment and defines release gates (`AGENT_04_RELEASE`). |
| **Agent 03** (Evidence & Reconciliation) | Preserves all raw coder distributions, confidences, importances, span IDs, and interpretations losslessly; implements Level 2 crosswalk table alignment (`PARTIAL_CROSSWALK`, `NO_VALID_CROSSWALK`, etc.) and populates ADR-0008 `uncertainty_class` and `preference_uncertainty_set` descriptors without forcing point estimates. |
| **Agent 04** (Preference, Utility & Pareto) | Consumes uncertainty-set cells via updated `PreferenceCell` / `PreferenceMatrix`; implements interpretation-aware `ParticipantUtility` operators (`ISSUE-005`), constraint-only `GovernanceSolution` pruning, and 4-tier `RobustParetoResult` classification. |
| **Agent 09** (Final Integration Reviewer) | Independently audits zero silent averaging, absence of confidence-weighted point collapse, Level 2 crosswalk provenance, non-imputation of single-coder zeros, `ISSUE-005` dual-interpretation retention, and strict non-pruning by clusters/values/disagreement. |
| **Agent 10** (Documentation & Memory) | Updates `docs/OPEN_ISSUES.md` (`ISSUE-005` $\to$ `RESOLVED` by `ADR-0008`, with downstream implementation tracked in Agent 04/11), updates `docs/PROJECT_STATE.md`, and regenerates `docs/AGENT_CONTEXT/` packs after integration. |
| **Agent 11** (Orchestration & QA) | Integrates shared contract updates into `src/contracts.py`, `schemas/interfaces.json`, and `docs/DATA_CONTRACTS.md` per `ADR-0007`, enforces static/runtime removal of `"CONFIDENCE_WEIGHTED_DISTRIBUTION"`, wires QA release checks, and publishes canonical `runs/<run_id>/manifest.json` registrations upon merge. |

---

## 8. Validation Rules (Machine-Checkable Invariants)

Downstream unit tests (`tests/test_evidence.py`, `tests/test_preference.py`, Agent 09 audit checks) MUST enforce:

- **V1 (Zero Unauthorized Averaging)**: `reconciliation_method != "CONFIDENCE_WEIGHTED_DISTRIBUTION"` across all records; no cell with `uncertainty_class != "NONE_CONSENSUS"` may emit a synthetic point estimate in `resolved_point_distribution`.
- **V2 (Derived Scenario Labeling)**: Any interior convex-hull or interval-sampled vector generated by Agent 04 MUST carry `scenario_origin in {"DERIVED_ROBUSTNESS_CONVEX_BARYCENTER", "DERIVED_ROBUSTNESS_SCENARIO", "DERIVED_BOUNDS_SAMPLE"}` and MUST NOT mutate `PreferenceMatrix` observed evidence.
- **V3 (Crosswalk Gating)**: Whenever `crosswalk_status == "NO_VALID_CROSSWALK"`, `TVD`, `JSD`, `resolved_point_distribution`, and aligned `discrete_scenarios` MUST be `None`/unmerged, and both raw coder distributions MUST remain intact.
- **V4 (Simplex Integrity)**: Every observed distribution (`coder_a_distribution`, `coder_b_distribution`, each entry in `discrete_scenarios`, and non-`None` `resolved_point_distribution`) sums to $1.0 \pm 10^{-4}$; all missing/non-preference cells remain empty (`{}`).
- **V5 (Single-Coder Non-Zero-Fill)**: For `SINGLE_CODER_PARTICIPANT_OMISSION` and `SINGLE_CODER_SUBTOPIC_GRANULARITY`, the silent coder field MUST remain `None` (`non_coding_coder_state == "EPISTEMICALLY_UNOBSERVED"`), never `{k: 0.0}`.
- **V6 (`ISSUE-005` Interpretation Preservation)**: Equal distributions with differing `probability_interpretation` MUST NOT be tagged `AGREEMENT_EXACT`; both `coder_a_probability_interpretation` and `coder_b_probability_interpretation` MUST appear in `preference_uncertainty_set.interpretation_variants`.
- **V7 (Constraint-Only Pruning)**: Zero feasible solutions may be pruned by `ClusterResult`, `ValueAssignment`, or unresolved coder disagreement (`RobustParetoResult` audit verifies `UNRESOLVED_DUE_TO_CODING_UNCERTAINTY` retention).
- **V8 (Primary Spine Preservation)**: `Q01`–`Q13` remain primary; `Q14` stays isolated as optional contextual material.

---

## 9. Review of Agent 03 Output Schema Compatibility & Agent 04 Release Status

1. **Lossless Raw Coder Preservation (`PASS`)**: Inspection of `src/evidence/reconciliation.py` (`PreferenceReconciliationRecord`, `AlternativeAlignmentInfo`, `UncertaintyMetadata`) confirms that Agent 03 **already preserves 100% of raw coder information losslessly** (`coder_a_probabilities`, `coder_b_probabilities`, `probability_interpretation_a/b`, `semantic_importance_a/b`, `coder_confidence_a/b`, `coder_a/b_span_ids`, `reconciled_alternative_probabilities = None` for all `265` unresolved/flagged records). **No GPU re-coding of `coder_a` or `coder_b` is required.**
2. **Schema Alignment Requirements (`AGENT_03_SCHEMA_COMPATIBILITY = REQUIRES_CHANGE`)**: While raw data is lossless, minor deterministic CPU schema/crosswalk additions are required to conform strictly to `ADR-0008`:
   - `AlternativeAlignmentInfo.mapping_type` in `src/evidence/reconciliation.py` currently uses `EXACT_KEYS` / `ALTERNATIVE_VOCABULARY_MISMATCH` and lacks `PARTIAL_CROSSWALK` and Level 2 `EXACT_KEY_MATCH` / `NO_VALID_CROSSWALK` alignment;
   - `align_alternative_vocabularies()` currently applies lexical/prefix 1-to-1 heuristics only and needs an authorized deterministic per-question canonical crosswalk lookup (addressing the `83` `ALTERNATIVE_VOCABULARY_MISMATCH` and `5` `ALTERNATIVE_KEY_CROSSWALK_PENDING` records where valid mappings exist, while tagging irreducible splits as `PARTIAL_CROSSWALK` or `NO_VALID_CROSSWALK`);
   - Downstream export/adapter (or `PreferenceReconciliationRecord` / `PreferenceCell`) needs explicit `uncertainty_class`, `preference_uncertainty_set`, `agreement_status`, and optional `resolved_point_distribution` fields synchronized with `src/contracts.py`.
3. **Agent 04 Release Gate (`AGENT_04_RELEASE = BLOCKED` until contract integration)**:
   Although `ADR-0008` resolves the methodological policy and `ISSUE-005` on this branch, Agent 04 execution remains **gated (`BLOCKED`)** until:
   - `agent/00-adr-0008` is merged into `main`;
   - Agent 11 updates shared contracts (`src/contracts.py`, `schemas/interfaces.json`, `docs/DATA_CONTRACTS.md`)—specifically removing `"CONFIDENCE_WEIGHTED_DISTRIBUTION"` and adding `preference_uncertainty_set` / optional `resolved_point_distribution` to `PreferenceCell` so `validate_simplex()` accepts set-valued cells—and Agent 10 updates `docs/OPEN_ISSUES.md`;
   - Agent 03 / integration emits ADR-0008 Level 2 crosswalk mappings (`EXACT_KEY_MATCH`, ..., `PARTIAL_CROSSWALK`, `NO_VALID_CROSSWALK`) and `preference_uncertainty_set` fields on `reconciled_evidence_v1` and canonically registers Agent 03 artifacts in `runs/<run_id>/manifest.json`.

---

## 10. Consequences & Open Questions

### Consequences
- **Positive**:
  - Eliminates hidden averaging, uncalibrated confidence weighting, zero-imputation on single-coder facets, and silent interpretation collapse (`ISSUE-005`).
  - Allows Agent 04 to launch on a deterministic, mathematically auditable uncertainty-set contract without re-running expensive dual-GPU inference.
  - Protects minority subtopics and structurally unresolvable divergences via explicit `CONDITIONALLY_NONDOMINATED` and `UNRESOLVED_DUE_TO_CODING_UNCERTAINTY` Pareto reporting.
- **Trade-offs**:
  - Increases analytical complexity in Agent 04 (`src/preference/`) due to set-valued / scenario-indexed `ParticipantUtility` and 4-state `RobustParetoResult`.
  - Requires coordinated shared-contract integration by Agent 11 and Agent 10 per `ADR-0007`.

### Open Questions
1. **Per-Question Canonical Alternative Crosswalk Authoring**: For the `83` `ALTERNATIVE_VOCABULARY_MISMATCH` cells in `run_20261111_002`, which subset has an unambiguous deterministic key crosswalk (`SEMANTIC_KEY_MATCH` / `PARTIAL_CROSSWALK`) versus genuine irreducible framing divergence (`NO_VALID_CROSSWALK`)? To be cataloged transparently in a versioned, hashed crosswalk configuration table during Agent 03/11 alignment without inventing synthetic preferences.
2. **Robust Core Threshold Parameterization**: Should `RobustParetoResult.robust_frontier_solution_ids` report solely the strict $100\%$ nondominated core alongside a configurable high-confidence tier (e.g., inclusion probability $\ge 0.95$ configured in `pareto_mc_config_v1`), ensuring both strict core and threshold-based sets appear transparently?
3. **Single-Coder Weight Bounding Calibration**: In `SINGLE_CODER_SUBTOPIC_GRANULARITY` sensitivity sweeps, should overlapping `PARTIAL_OVERLAP` parent/child facet pairs default to half-split weight (`0.5 * w`) versus $[0, w]$ full bracketing in `pareto_mc_config_v1`?
