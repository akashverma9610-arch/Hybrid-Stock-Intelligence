# Composite Execution Gate Policy V2.4 Governance Approval

Decision **A: `COMPOSITE_V2_4_GOVERNANCE_APPROVED_WITH_ACTIVATION_BLOCKERS`**.
Scope: **`SEMANTIC_GOVERNANCE_ONLY / NOT_ACTIVE`**.
Reviewed baseline: `c3eb2caa15b7d3e2aecf74c41f8706e9d6c3a479`, clean `main`.

This is a bounded user-delegated governance review, not a claimed human digital
signature, model certification, production observation or activation instruction.
The [machine approval receipt](EXECUTION_GATE_POLICY_V2_COMPOSITE_GOVERNANCE_APPROVAL_2.json)
binds the complete [immutable .4 proposal](GATE1_ROTATION_POLICY_V2_PROPOSAL.json)
and its [explanation](GATE1_ROTATION_POLICY_V2_PROPOSAL.md). No earlier artifact is
overwritten. The proposal still records its original `PROPOSED` status; this
separate approval supplies the semantic decision, not a runtime effective date.

## 1. Single successor and verified content lineage

The one future whole-policy candidate is
`execution-gate-policy-v2-proposed / v2-proposal.4`, parent
`six-gates-production-v1 / v1`. The .2 and .3 revisions and individual Gate 1/3/6
artifacts remain historical/component-governance evidence, not competing current
whole-policy authorities. The [.3 approval](EXECUTION_GATE_POLICY_V2_COMPOSITE_GOVERNANCE_APPROVAL.json)
does not transfer automatically; this receipt independently approves .4's exact
content. No second reducer, production selection or policy registration exists.

| Artifact | Verified canonical fingerprint |
| --- | --- |
| .4 whole proposal | `sha256:0be5819937f85910700b672c7238d6cc01efa4777d8dac3518606837e2454769` |
| .3 whole proposal | `sha256:57bbd7af01fe14fa95ae419187302d5dcc353e3cbd98181e43b5f691cb97ab3d` |
| .3 composite approval | `sha256:caad6fb766fbcf93ea4859a94454c78d57ba59551274601eba9741486ae7d30e` |
| .2 Gate-6 proposal | `sha256:36c80f2ea561a4411b252e6b4749f9c73275d6e434b257e89bdeb24d83de0e21` |
| .2 Gate-6 approval | `sha256:0d2bd690a9b5cec347437163cbc7ad88cadec940b0546549ce40361b833414d0` |
| This .4 approval | `sha256:4e93795ab75b9eac7dc05aca853e63008252765ca21a5d30b5dc160c54334c9e` |

Repository canonical JSON/SHA-256 excludes only the artifact's self-fingerprint.
Full-content identities, separate component-bundle fingerprints and LF-normalized
file pins are independently recomputed from the repository, not trusted because
these values are printed. The approval pins 28 existing source/governance files;
it is tamper-evident content identity, not source authenticity or a signature.

Exact ordered gates, no duplicates, omissions or Gate 7:

```text
GATE_1_ROTATION
GATE_2_VELOCITY
GATE_3_SURVEILLANCE
GATE_4_TRADE_PLAN
GATE_5_HEAT
GATE_6_EARNINGS
```

Gate 2/4/5 canonical definitions and individual method fingerprints match V1.
The complete production configuration, evidence-authority and version-compatibility
files also match the accepted source pins. Gate 1 V1 remains `ROTATE_IN` only,
with `raw_decision_score - comparison_score >= 1.00` and legacy
`expected_incremental_return - modeled_switching_friction > 0.00`. Its fields
are not renamed, retyped or reinterpreted as .4 scenarios. No migration by meaning.

## 2. Gate-1 semantic approval and explicit non-approvals

All `/gate1_proposed` requirements are incorporated without overrides. The
following decisions explain the approval; they do not implement an evaluator.

| Dimension | Approved semantic boundary | Unapproved / fail-closed boundary |
| --- | --- | --- |
| Scope | Exact incumbent replacement, `ROTATE_IN` only | Cash-funded `FRESH_ENTRY`, `ADD_TO_POSITION` and existing non-rotation contexts retain Gate-1 not-applicable behavior, not whole-policy clearance |
| Quality hurdle | Candidate raw score minus exact incumbent comparison score `>= 1.00` score points, independent canonical score provenance | No score-to-INR/probability conversion; economics cannot change Decision Score |
| Comparator | Candidate rotation versus exact incumbent no-rotation continuation, same parcel/capital/cutoff/horizon | No candidate-versus-cash, benchmark, zero-incumbent or entire-portfolio substitute |
| Quantity | Candidate terminal scenario INR minus incumbent continuation terminal scenario INR; nominal undiscounted conditional marked wealth | Not expected value, realized return, probability, promise, target, forecast or full after-tax NPV; no assumed terminal sale |
| Capital | Positive `C = selected_incumbent_quantity * incumbent_reference_price_inr`; candidate purchase turnover plus residual equals the same C | NAV is not a denominator; reference turnover is not an actual fill; no quantity/sizing chosen by Gate 1 |
| Partial replacement | Both scenarios, friction, statutory costs, slippage and selected tax lots apply to the actual selected parcel | No full-position default or proportional cost/tax shortcut; selected quantity must not exceed canonical holding |
| Cost exclusion | Both endpoints exclude every cost subsequently included in friction; disjoint cost manifest deducts each once | Costs reducing candidate deployment cannot be subtracted again; no assumed free financing, fractional execution or available cash |
| Funding / residual | Candidate deployment + residual = C must reconcile under a separately governed cost-exclusive convention | `POLICY_UNSET`: fee reserve, whole-unit and residual treatment/yield not invented; missing reconciliation is insufficient |
| Horizon | Same governed reference, version/fingerprint and endpoint, starting at decision-as-of | No numeric horizon; TradePlan label is not binding; applicable fundamental B09 is compatibility, not a number or Gate-6 risk window |
| Scenario model | Paired, independently reproduced, PIT-safe candidate/incumbent methodology is required | `ROTATION_SCENARIO_MODEL = POLICY_UNSET`; no approved terminal pricing, dividends/adjustment, funding, rounding or statistical methodology |
| Economic hurdle | Gross scenario advantage minus complete switching friction strictly `> 0.00 INR` | Equality fails; no `>= 0`, extra margin or rounding-created positive result |
| Probability | Not required for these deterministic semantics | No score, AI confidence, historical win rate or target-hit assumption becomes probability; statistical models need separate governance/calibration |

The capital identities are coherent conditional accounting constraints, **not an
operational funding solution**. Their unresolved funding/model contract is a
mandatory blocker, not permission to assume free fee financing or double-count
costs. Gross advantage may be negative; terminal values and costs must be finite
nonnegative exact decimals with explicit INR units. Float coercion or mixed
percentage/INR arithmetic cannot satisfy the future contract.

```text
gross_rotation_scenario_advantage_inr
  = candidate_scenario_terminal_value_inr
  - incumbent_continuation_terminal_value_inr

execution_switching_cost_inr
  = purchase_statutory_costs_inr + sale_statutory_costs_inr
  + nse_member_transaction_charge_inr + brokerage_inr + slippage_inr + gst_inr

modeled_switching_friction_inr
  = execution_switching_cost_inr + tax_realization_impact_inr

economic hurdle:
gross_rotation_scenario_advantage_inr - modeled_switching_friction_inr > 0.00
```

Retain purchase STT/SEBI/stamp, sale STT/SEBI, member/exchange-charge scope,
brokerage and GST on governed taxable services. Every rate needs official/source
identity, version/fingerprint, effective applicability, HSI known-at, side, base,
GST-overlap and rounding proof. No current rate, tax law interpretation or stale
V1 constant is approved by this receipt.

**Tax T1 remains mandatory:** a nonnegative selected-disposal tax-realization
component, separated in presentation but included in total friction once.
Canonical selected lots, cost basis/acquisition history and applicable verified
user/rule context are required. Tax policy/producer remains `POLICY_UNSET`;
there is no invented rate, credit/netting benefit or user-typed hard-gate amount.

**Slippage remains mandatory and its producer `NOT_READY`.** No zero default,
OHLC proxy, AI estimate or manual value qualifies. No independent spread,
market-impact or liquidity penalty is added. Later incorporation of those
effects requires separately governed slippage decomposition, not double counting.

## 3. Authority, PIT, dependencies and historical isolation

`DETERMINISTIC_HSI_DERIVED_SCENARIO` is approved **as a conceptual authority role
only**. It is not registered or admitted by the running system. A separately
approved producer and independent verifier must reproduce both scenario operands,
capital, pair, horizon, cost manifest and compatible policy versions. A policy
fingerprint, self-hash or caller-selected class label cannot establish authority.
User return/friction/tax/slippage numbers and AI economics remain rejected. AI
may explain admitted evidence later, not create it or grant clearance.

The required binding is the proposal's complete `/gate1_proposed/pit` manifest:
decision-as-of; exact candidate/incumbent; portfolio snapshot identity/fingerprint;
selected parcel and tax lots; capital; both reference prices/bases/cutoffs; common
horizon/version/endpoint; paired model versions; friction/rates; tax and slippage
policy/evidence; all upstream IDs/fingerprints; score/incumbent provenance;
funding/residual/rounding conventions; and scenario fingerprint. Canonical
ordering follows duplicate/conflict checks; identity and complete-body fingerprint
are separate, non-circular, runtime-clock-independent concepts.

Known-at and observation-as-of must each be `<= decision_as_of`, inclusive and
UTC normalized, with valid approved/effective policies and a common market cutoff.
Filter future evidence before revisions/conflicts. Modeled future endpoints are
allowed; future observed prices, realized outcomes and later portfolio facts are
not. Identical receipt/content is idempotent with lineage retained; conflicting
content or applicable candidates remain insufficient. Only an explicit PIT-visible
supersession relation resolves revisions. No invented freshness duration or
publication-date backdating.

Reuse existing portfolio snapshots, canonical market facts, upstream Rotation
Challenger pair/context, policy/versioning, gate evidence envelope and outcome
infrastructure. Challenger final clearance cannot feed back into the evidence
that obtains that same clearance. Its candidate-global caller economics and
legacy inclusive friction check are not .4 proof. TradePlan remains Gate-4
authority; neither Gate-4 PASS nor a target price becomes a scenario prerequisite
or economic value automatically. No parallel Rotation Engine, Portfolio model,
Brain, AI economic engine or reducer is approved.

V1 historical decisions remain V1; .3 remains historical governance lineage.
.4 applies only after future explicit activation. Replay requires an explicit
V2 mode and exact versioned PIT inputs, not relabelling or recomputing old records
with later information. Replay isolation is mandatory before activation; perfect
historical archives are not a prerequisite for a bounded prospective pilot.

## 4. Gate-3 / Gate-6 carry-forward and six-gate liveness

The .4 machine proposal pins the complete .3 Gate-3 definition bundle and approval
bundle, and the Gate-6 .3 carry-forward objects through the original .2 proposal
and approval. This receipt recomputes those chains and permits no semantic override.

| Gate / composition | Preserved meaning |
| --- | --- |
| Gate 3 | Current-effective PIT-visible official ASM/GSM/PRICE_BAND, complete vector required; ASM >=2, GSM >0, static band <=5%; inclusive four-trading-session freshness plus independent current applicability |
| Missing Gate-3 input plus blocking input | `INSUFFICIENT_DATA`, not independent positive-only veto; SECURITY_STATUS remains descriptive only |
| Gate 6 | `VERIFIED_EVENT_VETO`: VETO -> FAIL; NO_VETO_ESTABLISHED -> composition-only PASS; UNDETERMINED -> INSUFFICIENT_DATA |
| Gate-6 no-veto metadata | Confidence null, clearance `UNVERIFIED`, warning `EARNINGS_CLEARANCE_UNVERIFIED`, source limits/PIT/policy lineage retained; missing metadata rejects compatibility |
| Gate-6 horizon | `POLICY_UNSET / CALIBRATION_REQUIRED`; no inherited five-session default, no absence clearance, retroactive blackout or forced position action |
| Existing reducer | Any FAIL -> BLOCKED; else any INSUFFICIENT_DATA -> INSUFFICIENT_DATA; else six PASS -> EXECUTABLE |

Synthetic witnesses only: score advantage exactly 1; cost-exclusive terminal
values 1091 and 1080 INR; execution cost 8 including slippage; tax 2; net 1 INR.
With the other five composition results PASS, the **existing** reducer returns
EXECUTABLE. Terminal 1090 gives zero net, hence Gate-1 FAIL / BLOCKED; 1089 is
also FAIL. Missing required scenario/friction with adequate score is insufficient
unless another gate fails. Score below 1 remains its independent FAIL even when
economics are absent. All 27 Gate-1/Gate-3/Gate-6 outcome combinations preserve
the reducer's precedence and individual metadata.

These are explicitly invented test numbers and declared governed-fixture
assumptions, not model parameters, producer proof, live source admission, complete
entry-readiness, performance evidence or capital authority. No test fixes a
production horizon. `EXECUTABLE` remains an evidence classification; no orders.

## 5. Reconciled activation register and accepted source subproofs

The machine register maps **all 20 .3 entries and all 18 Gate-1 entries exactly
once into 29 entries**. Shared infrastructure is merged, but all origin closure
requirements remain mandatory conjunctively. Origin IDs are namespaced; the old
registers are immutable. Earlier closure text is a historical requirement, not
a fresh measurement or claim that this review closed/reopened its subcomponents.

| New IDs | Area and disposition |
| --- | --- |
| CV24B01-02 | ASM/GSM complete capture: BLOCKING, `BLOCKED_PARKED` |
| CV24B03 | Exact price-band target admission: BLOCKING OPEN, accepted direct CSV/master capture subproofs retained |
| CV24B04-08 | Trusted receipts/independent scenario authority; surveillance effective selection; conflict/lifecycle; one engine with component-specific adapters; surveillance canary: BLOCKING OPEN |
| CV24B09-10 | Earnings horizon/calibration and no-veto confidence/metadata guard: BLOCKING OPEN |
| CV24B11 | Lossless metadata plus Challenger/Signals/Portfolio/entry-ready review: BLOCKING OPEN; all consumer proofs required |
| CV24B12 | Outcome/scenario shadow/calibration compatibility: BLOCKING OPEN, statistics-dependent model calibration required before activation |
| CV24B13 | .4 registration/effectiveness/selection/compatibility: BLOCKING OPEN; only new semantic approval is satisfied here |
| CV24B14 | Historical policy-version isolation: BLOCKING OPEN |
| CV24B15-17 | Complete surveillance history: DEFERRED_FOR_REPLAY; extended earnings/scenario history/outcomes and negative-calendar clearance: DEFERRED_FOR_SHADOW |
| CV24B18-19 | Optional alerts/results-season context: NON_BLOCKING, disabled |
| CV24B20-24 | Paired comparator contract; common horizon/applicable B09; capital/funding/residual; candidate producer; incumbent continuation producer: BLOCKING OPEN |
| CV24B25-28 | Friction component policy; effective statutory rates; tax policy/producer; slippage producer: BLOCKING OPEN |
| CV24B29 | Complete historical scenario archives: DEFERRED_FOR_REPLAY |

The [ASM/GSM fallback](GATE3_ASM_GSM_COMPLETENESS_GOVERNANCE_FALLBACK_V1.md)
remains blocked/parked; no API absence-to-clearance exception. The later
[execution-master repair](NSE_EXECUTION_MASTER_CURRENT_CAPTURE_CONTINUITY_REPAIR_V1.md)
already closed current-capture continuity as source evidence. That closure and
its exact receipt fingerprint are retained, not reopened because an older .3
requirement mentioned it. Existing per-row identity conflicts and decision-specific
freshness remain separate; historical capture success is not perpetual currency.
[Direct price-band CSV capture](GATE3_SURVEILLANCE_SOURCE_CAPTURE_COMPLETENESS_REPAIR_V1.md)
also remains ready as a subproof, not complete target Gate admission.

The [earnings prospective shadow structure](EARNINGS_BLACKOUT_HORIZON_PROSPECTIVE_SHADOW_V1.md)
and collector structure remain ready; their accepted live event/outcome proof is
`PENDING_EVENT`. Event-risk horizon remains unset independently. No source is
refetched, runtime invoked or production DB measured in this governance review.

Semantic approval can precede model calibration; scenario validation/limitations
and shadow/outcome compatibility cannot be waived. Statistical or outcome-derived
parameters require defensible prior calibration. Applicable fundamental B14
compatibility remains separate; B14 work is not started. No rates, scenario
producer, tax calculator, slippage model or numeric horizon is approved here.

## 6. Downstream compatibility and pilot boundary

| Consumer | Classification | Obligation |
| --- | --- | --- |
| Six-Gates orchestration | ADAPTER_UPDATE_REQUIRED | One engine, explicit .4 selection and source admission |
| Brain | ADAPTER_UPDATE_REQUIRED | Lossless scenario/policy/PIT and inherited no-veto metadata |
| Portfolio Rotation Challenger | ADAPTER_UPDATE_REQUIRED / POLICY_REVIEW_REQUIRED | Exact paired economics; strict comparison compatibility; no circular clearance |
| Signals / Portfolio | ADAPTER_UPDATE_REQUIRED / POLICY_REVIEW_REQUIRED | Version-aware descriptive results, no action authority or portfolio mutation |
| Entry-ready lifecycle | POLICY_REVIEW_REQUIRED | Preserve all score/setup/gate and uncertainty prerequisites |
| Backtest/replay | ADAPTER_UPDATE_REQUIRED / REPLAY_UPDATE_REQUIRED | All inherited lineage plus separate .4 scenario meaning |
| Outcome ledger | ADAPTER_UPDATE_REQUIRED / CALIBRATION_REQUIRED | Modeled versus observed outcomes, compatible cohorts and missingness |
| TradePlan / Decision Score | NO_CHANGE | Gate-4 ownership and score units/weights unchanged |
| Alerts | POLICY_REVIEW_REQUIRED | Disabled, future truthful wording/metadata/dedup review |
| Gate-3 numeric thresholds | CALIBRATION_NOT_REQUIRED | No numeric-policy change |
| Gate-6 event-risk horizon | CALIBRATION_REQUIRED | Not the Gate-1 comparison horizon |

Research and portfolio comparison may continue independently. Gate-1 execution
economics remains fail-closed until all required scenario, horizon, funding,
friction, tax, slippage and adapter proofs close. Uncertainty is not low quality,
a bearish opinion or a new Decision Score penalty. Cash-funded fresh entry and
ADD remain outside this economic branch. No automatic job or trading action is
authorized by this receipt; the pilot simplicity rule remains active.

## 7. Validation and stop boundary

[Focused governance tests](../../tests/unit/test_execution_gate_policy_v2_composite_governance_approval_2.py)
verify exact proposal/approval chains, frozen methods/configuration/authority,
INR/capital/horizon/cost/PIT invariants, user/AI rejection, complete blocker-origin
coverage, retained source subproofs, immutable historical behavior, rehashed
unsafe-artifact rejection and deterministic full-content fingerprint replay.
Synthetic composition uses the existing reducer only. Existing proposal,
governance, source-authority, rotation and surveillance/source-capture regression
tests also passed: **147 focused / 0 failed / 0 skipped / 0 warnings**, and
**524 relevant / 0 failed / 0 skipped / 2 existing deprecation warnings**
(Starlette/httpx and AnyIO). The two runs total 671 passing tests. Final local
Markdown validation covers 285 links and five tables across this document and
README, including table separators, columns, whitespace and code-fence balance.

Markdown local links/table structure, whitespace and `git diff --check` must
pass. No application/runtime changes are permitted and no full backend suite is
required or run for this documentation/governance slice. Source hash tests prove
the baseline files remain unchanged; they do not audit a running installation.

```text
V1_ACTIVE = TRUE
GATE_POLICY_V2_ACTIVE = FALSE
SIX_GATES_EXACTLY_SIX = TRUE
NO_FABRICATED_ECONOMIC_RETURN = TRUE
NO_FABRICATED_SWITCHING_FRICTION = TRUE
NO_FUTURE_LEAKAGE = TRUE
NO_USER_ENTERED_GATE1_EXPECTED_RETURN_AUTHORITY = TRUE
NO_AI_ECONOMIC_AUTHORITY = TRUE
NO_RETROACTIVE_SURVEILLANCE_STATE = TRUE
NO_RETROACTIVE_BLACKOUT = TRUE
NO_HORIZON_GUESS = TRUE
PILOT_SIMPLICITY_RULE = ACTIVE
AI_DECISION_AUTHORITY = FALSE
```

Exactly one next continuation: **`GATE1_ROTATION_ECONOMIC_SCENARIO_CONTRACT_V1`**.
It is **not started**. This local governance commit is not pushed.
