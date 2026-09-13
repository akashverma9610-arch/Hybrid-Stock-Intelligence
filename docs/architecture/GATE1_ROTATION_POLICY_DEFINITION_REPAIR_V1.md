# Gate 1 Rotation Economic Policy Definition Repair V1

Decision **B — `GATE1_VERSIONED_ECONOMIC_POLICY_CHANGE_REQUIRED`**.
Status: **`GOVERNANCE_REPAIR_COMPLETE / DOCUMENTATION_ONLY / NOT_ACTIVE`**.
Baseline: `c8842a9fcd61588c377d9d455c582a282c01cf30`, clean `main`.

This bounded review establishes the versioning consequence of the accepted
[source-readiness audit](GATE1_ROTATION_SOURCE_READINESS_V1.md). It does not
approve a return model, comparator formula, horizon, capital base, tax model,
slippage assumption or runtime producer. Those values remain explicitly unset.
The [policy-repair receipt](GATE1_ROTATION_POLICY_DEFINITION_REPAIR_V1.json)
records the evidence, unresolved decisions and preserved source fingerprints.
Its fingerprint is content identity, not a signature or runtime approval.

Internal conclusion:
`V1_FORMULA_REQUIRES_VERSIONED_ECONOMIC_POLICY_CHANGE`.
The scalar subtraction can be retained, but introducing economic meaning changes
the policy's admitted inputs. No historical evidence proves that an INR, rate,
probability or deterministic-scenario interpretation is the original approved
meaning. Completing that definition cannot silently authorize new inputs under
V1. This is enough to proceed to a versioned proposal; a producer or another
search for missing market data would be premature.

## 1. Original authority and its limits

The earliest reachable repository baseline is
`d64bb988ad253d04f970e7cea96f775e2e9dcbf6`. Searches used Git history inside the
authoritative D: repository, including `git log -S`, original file contents,
current documentation, tests and schema/selection code. No old OneDrive checkout
was accessed. No external tax/rate guidance was selected or updated in this audit.

| Source / historical evidence | What it establishes | What it does not establish |
| --- | --- | --- |
| [Original Gate definitions](../EXECUTION_GATES.md) and [canonical registry](../../app/registry/canonical.py), present at `d64bb98` | Net Friction & Tax Hurdle; candidate versus weakest holding score; applicable costs, slippage and taxes; strategy-versioned exact values | Quantitative economic comparator, payoff, probabilities, units or horizon |
| [Friction Model](../FRICTION_MODEL.md), unchanged since `d64bb98` | `ROTATE_IN` only; cash-funded fresh-entry exemption; missing required economics never default to zero | Meaning of incremental expected return; original optional inputs are not optional under a selected policy requiring the check |
| [Production policy](../../app/gates/production_policy.py), introduced in `9c9af08dd7fbd8f868e87131908f8d847bcd269e` and unchanged | Approved fixed `1.00` score hurdle; strict net `> 0.00`; required economics; explicit nonnegative cost-input formula | Approved source/calculation for user-specific costs or expected return |
| [Approval persistence and selection](../../app/storage/sqlite_governance_repository.py) | Integrity-checked immutable payload, policy/version/effective-time uniqueness, selection at `effective_at <= as_of` | No schema column or migration supplies a comparator, horizon, capital denominator, probability or economic-scenario approval |
| [Synthetic production tests](../../tests/unit/test_six_gates_production_policy.py) and [isolated canary](../../tests/unit/test_six_gates_e2e_isolated_canary.py) | Missing-cost rejection and strict zero-hurdle liveness; hypothetical positive scalar examples | Fixture return `500` or any other number is not a policy definition or real forecast |
| [Rotation efficiency](../ROTATION_EFFICIENCY.md) and [outcome calculation](../../app/performance/efficiency.py) | Retrospective candidate-minus-retained-holding outcomes when comparable paths exist | No decision-time expectation, probability, capital-base governance or Gate 1 source authority |
| [Prior authority closure](FUNDAMENTAL_V2_SIX_GATES_VERSION_COMPATIBILITY_REPAIR_3.md) | Both economic inputs remain rejected without an independently admitted producer | A policy hash or a caller label is not scenario approval |

| Semantic dimension | Original authority classification | Decision |
| --- | --- | --- |
| Rotation-only action scope and independent score comparison | `EXPLICITLY_APPROVED` | Preserve existing branch and `1.00` score points |
| Economic comparison of replacing versus retaining a holding | `IMPLIED_BUT_INCOMPLETE` | Broad opportunity-cost intent exists; exact comparator is `COMPARATOR_POLICY_MISSING` |
| Return quantity, currency/rate/R units, capital base and horizon | `UNKNOWN` | `RETURN_QUANTITY_POLICY_MISSING`, `RETURN_UNIT_POLICY_MISSING`, `CAPITAL_BASE_POLICY_MISSING`, `HORIZON_POLICY_MISSING` |
| Statistical expectation versus deterministic scenario | `UNKNOWN` | `EXPECTED_VALUE_MODEL_POLICY_MISSING`; neither method selected |
| Friction helper's absolute monetary arithmetic and listed components | `EXPLICITLY_APPROVED` within the accepted production policy | Preserve the helper and its required-cost behavior |
| Broker fee amount, personal tax computation, slippage measurement/decomposition | `UNKNOWN` | No admitted producer or user-account calculation policy |
| Treating arbitrary fixture scalars as economic evidence | `LEGACY_ASSUMPTION` if inferred from tests | Explicitly rejected; fixtures establish arithmetic only |

One refinement to the prior audit: `GateInput` itself has no incumbent identity,
but [GateScoreEvidence](../../app/gates/score_provenance.py) **does** retain the
incumbent instrument through its scorecard and prior gate comparison. This is
reusable identity/provenance. It does not bind either economic scalar to that
incumbent, the switched amount or the scenario horizon. There is no need to
rebuild incumbent identity or a second portfolio model.

## 2. Frozen formula, applicability and precedence

For valid admitted inputs in `ROTATE_IN`:

```text
score_advantage = raw_decision_score - comparison_score
score branch meets hurdle when score_advantage >= 1.00
economic branch meets hurdle when expected_incremental_return - modeled_switching_friction > 0.00
```

Actual order in [the evaluator](../../app/gates/engine.py): unresolved score/friction
configuration -> `INSUFFICIENT_DATA`; non-rotation -> not-applicable `PASS`;
missing score -> `INSUFFICIENT_DATA`; low score advantage -> `FAIL`; required
economic value/hurdle absent -> `INSUFFICIENT_DATA`; net value `<= 0` -> `FAIL`;
otherwise `PASS`. Thus a known score failure can precede missing economics.
An unverified populated value is rejected before this formula by the existing
authority firewall. Neither exception is a license to fabricate a zero value.
Constant PASS confidence `1.0` is not an economic probability.

Historical boundary proof: `d64bb98` rejected net values only when `< hurdle`
(equality could pass). The accepted production-policy commit `9c9af08` changed
that predicate to `<= hurdle`, establishing the current strict `> 0.00` rule.
The entire current `_rotation` method matches that accepted commit, not the
earliest baseline. This repair preserves the accepted strict rule; the older
inclusive rule is not authority to relax it.

| Scenario | Scope | Exact boundary |
| --- | --- | --- |
| New candidate replacing an incumbent, explicitly `ROTATE_IN` | `IN_SCOPE` | Only the caller's existing rotation action classification reaches the economic branch |
| Holding-to-holding switch, explicitly `ROTATE_IN` | `IN_SCOPE` | Score provenance may identify both instruments; no economic pair/size binding yet |
| Partial rotation | `UNDEFINED` | No partial/full marker or capital-switch contract; do not assume full-position or proportional costs |
| Full rotation | `UNDEFINED` | The qualitative switch is in scope, but full-position capital treatment is not governed |
| Cash-funded purchase classified `FRESH_ENTRY` | `OUT_OF_SCOPE` | Original friction documentation expressly exempts this case; no expected return versus cash |
| Add/tranche classified `ADD_TO_POSITION` | `OUT_OF_SCOPE` | Existing not-applicable Gate 1 branch; no expansion of action scope |

Other non-rotation contexts keep their existing exemptions. Non-applicability is
not a full Six-Gates pass: the other gates and pre-formula admission still apply.

## 3. Quantity, comparator, horizon and unit decision

Neither candidate-minus-incumbent expected P&L, cash-relative return nor
benchmark-relative return is selected here. Candidate versus incumbent is the
best-supported **proposal direction**, from the original holding-comparison
intent, but the counterfactual continuation, cost treatment and measurement
horizon are still undefined. A weakest score is not a quantified counterfactual.

| Quantity | Current unit | Governed intended unit | Capital base | Horizon | Compatibility |
| --- | --- | --- | --- | --- | --- |
| `raw_decision_score - comparison_score` | Score points | Score points | Not monetary | Original score provenance/as-of | Independent `>= 1.00`; never a return or probability |
| `expected_incremental_return` | Bare `Decimal`, unit unspecified | `UNRESOLVED`; no P&L, percent, bps or R-multiple selected | `CAPITAL_BASE_POLICY_MISSING` | `HORIZON_POLICY_MISSING` | Cannot certify comparison with INR friction |
| `modeled_switching_friction` from existing helper | Absolute INR cost when monetary inputs are INR | Same INR amount within helper | Explicit purchase/sale turnovers, which need not be equal; no normalization denominator | Switch-cost scenario timing undefined; fixed rate has effective time | Compatible only with a quantity in the same currency, scale and scenario |
| `net_economic_hurdle` | Scalar `0.00` | Zero in the eventual common dimension | None specified | Same future scenario | Zero does not repair incompatible operands |

`INR - percentage` is forbidden by this governance boundary. The bare V1 types
do not detect such a mismatch; source rejection currently prevents admission.
The earlier audit's dimensional incompatibility remains unresolved, rather than
being repaired by labelling any existing number INR.

No Short-Term, Positional, Long-Term, planned holding period, TradePlan horizon
or rotation horizon is already bound. `TradePlan.time_horizon` is descriptive
and is not a Gate 1 horizon authority. B09 in the fundamental V2 approval governs
that registry's applicability; it is not automatically a Gate 1 holding period.
If a later proposal consumes that registry/horizon, explicit compatibility is
required; it supplies no missing value by itself.

## 4. Dimensional repair and policy options

The following are alternatives for future governance, not approved methods.
`E` means an as-yet-governed gross incremental benefit; `F` means costs counted
exactly once; `C` means an as-yet-governed positive common capital denominator.

| Option / model | Semantics and dimensional correctness | Size / partial rotation | PIT and replay | Horizon / calibration | Pilot / complexity | V1 compatibility |
| --- | --- | --- | --- | --- | --- | --- |
| A / model 1: absolute expected incremental P&L INR minus INR friction | Dimensionally correct only after comparator, gross/net and expectation are defined | Amount-specific; bind actual switched capital and both legs; no automatic full-position scaling | Freeze inputs, models and local known-at; replayable once approved | Common horizon missing; statistical expectation would need an approved/calibrated model | Moderate-to-high; INR arithmetic is simple but producing an expectation is not | Scalar subtraction reusable; semantic admission needs versioning |
| B / model 2: common-base return rate or bps | `(E/C) - (F/C)`; fractions, percent-points and bps must have explicit scale | Numerator still depends on size/costs; sale proceeds, purchase capital and NAV are not interchangeable | Freeze the same positive denominator and both source legs; reject zero/unknown/mixed bases | Same horizon and expectation gaps as A; normalization does not remove calibration needs | Additional denominator/precision rules; no data simplification | Same sign at exact zero only before rounding on one positive base; new normalization is a policy change |
| C: separately named deterministic scenario advantage, in a versioned successor | Honest conditional comparison without calling a target payoff an expectation; provisional INR direction can reuse cost arithmetic | Must define actual switched amount, unchanged residual holding, funding/cash residual and both scenario legs; all deferred | Reuse canonical evidence and explicit assumptions; hindsight-free conditional replay possible | Scenario endpoint/horizon/invalidation must be governed; return calibration requirement still unresolved | Preferred proposal direction for a bounded pilot; fewer unsupported statistical assumptions, but no scenario yet exists | Material meaning/name change; requires the single existing future whole-policy successor |
| D: keep economics blocked pending probabilistic expected-value policy | Expected value would require defined outcomes, probabilities, dependence and comparator; no probabilities exist | Same capital/partial/tax questions remain | PIT cohorts, model training cutoff and OOS/replay evidence required | Calibration required for an eventual statistical model; no model selected now | Highest burden; original policy does not mandate this choice | New model/admission semantics need versioning; V1 stays blocked |
| E / model 3: R-multiple or another representation | No repository authority chooses a common risk denominator or another economic unit | Candidate and incumbent risk bases can differ; cannot subtract INR costs directly | No approved contract to replay | Unresolved | Not justified for this pilot | Not selected |

Recommendation: develop **option C for review**, provisionally considering an
absolute-INR representation because the accepted cost helper already uses it.
This is not approval of a scenario formula or a renamed V1 field. The next
proposal must select the comparator, endpoints, horizon, capital, gross/net
treatment and restrictions explicitly. If defensible scenario evidence cannot
support them, the economic path must stay unavailable.

Algebraically, with one positive `C` and no rounding,
`E - F > 0` iff `E/C - F/C > 0`. This proves scalar sign preservation only.
It proves neither the economics of `E`, a denominator, stochastic expectation,
matching cash flows nor full behavioral compatibility. Rounding, unequal bases,
negative/zero bases and nonlinear actual costs defeat a casual conversion.

## 5. Exact accepted friction formula and component authority

Let `P` be purchase turnover and `S` sale turnover, both INR; `B`, `L`, `T` and
`G` are respectively brokerage, slippage, capital-gains tax and GST-taxable
services base, all explicit nonnegative INR amounts. The existing helper is:

```text
F_INR = P * (0.001 + 0.000001 + 0.00015)
      + S * (0.001 + 0.000001)
      + (P + S) * 307 / 10000000
      + B + L + T + G * 0.18
```

These are the stored `nse-cash-delivery-friction-v1 / v1` values effective
`2026-03-01T00:00:00+00:00`; this audit is not a current statutory-rate check.
The policy retains four official-source reference descriptions, not fetched
current fee schedules or a source-publication/known-at receipt.

| Component | Unit / formula | Current authority and required input | PIT and governance boundary |
| --- | --- | --- | --- |
| Purchase/sale turnover | `P`, `S`: INR | Explicit scenario amounts; no selected capital-base rule | Scenario sizes/prices/source times not governed; not the whole portfolio by default |
| STT | INR: `P*0.001 + S*0.001` | Fixed approved statutory parameter plus both turnovers | Effective-dated policy; not user-specific capital-gains tax |
| SEBI turnover charges | INR: `(P+S)*0.000001` | Fixed approved parameter plus both turnovers | Same policy/time requirements |
| Stamp duty | INR: `P*0.00015` | Purchase-side only in this helper | No extra sale-side charge added |
| NSE exchange/member outflow | INR: `(P+S)*307/10000000` | Existing approved member-outflow term | No extra exchange-charge line or assumed GST split added |
| Brokerage | INR: `B` | Explicit required amount; no broker/account schedule selected | `NOT_READY` source and fee semantics; market-data providers confer no cost authority |
| GST | INR: `G*0.18` | Approved rate; separately supplied taxable-service base `G` | `G` is a base, not another charge; which services enter it/double-counting prevention need governance |
| Slippage | INR: `L` | Required explicit amount under accepted helper | Producer `NOT_READY`, methodology undefined; no measured/proxy/OHLC substitution approved |
| Capital-gains tax | INR: `T` | **`EXPLICIT_CURRENT_POLICY` for inclusion as a required additive term** | Tax calculation `UNKNOWN`: no cost-basis/holding-duration/rule-version/jurisdiction/user-tax policy approved |
| Spread, impact, liquidity penalty, opportunity delay | No separate component | Not separately represented or approved | Their inclusion inside `L` is ambiguous; do not silently add, double count or claim measured zero |

`None` in any of `B/L/T/G` makes the helper return `None`; negative supplied
amounts are rejected. An explicitly supplied zero is numerically accepted by
the helper but is never evidence of no cost and gains no source authority.
Removing tax or slippage, treating them as optional, or manufacturing zero would
weaken the accepted required-cost contract. Any later exclusion or changed
tax/slippage meaning needs explicit successor governance.

Trade transaction charges and personal capital-gains taxation remain separate.
The latter can depend on cost basis, holding duration, gain/loss and applicable
tax circumstances; none is computed here. The helper is not a tax calculator,
and its nonnegative additive input must not be interpreted as a tax-saving or
tax-credit model. Gross versus net return and immediate versus future disposal
costs must be settled before subtracting friction to avoid double counting.

## 6. Future scenario admission requirements, not an implemented contract

The repair records the following requirements for the **future proposal**.
No dataclass, repository, API or scenario instance is created. Conditional fields
must only become required where the chosen economic model actually uses them.

| Required binding | Future decision-time rule |
| --- | --- |
| Scenario identity, version, fingerprint; decision as-of | Deterministic canonical serialization; same admitted inputs/version give same identity; UTC-aware cutoff; runtime processing time cannot supply historical knowledge |
| Candidate and exact comparator; score references | Reuse canonical instrument identities and incumbent score/gate provenance; selected economic comparator must explicitly match them |
| Portfolio snapshot and switched capital | Read-only exact snapshot/version/source cutoff when used; amount and currency bound to the actual switch, both legs and remaining position; no portfolio mutation and no portfolio access in this repair |
| Prices, setup assumptions and scenario endpoints | Bind only model-required canonical observations and price/adjustment bases, known by cutoff; a target endpoint never becomes expectation by relabelling |
| Return-model and horizon versions | Explicit approved semantics; source/model approval, training evidence if any, and input known-at no later than cutoff; no B09 default |
| Friction model/rate versions and cost components | Reuse existing helper where approved; rate effectiveness and local availability verified; explicit component bases/side coverage; no invented missing costs |
| Tax/slippage evidence and versions when retained | Independently verified modeled inputs under separately defined policy; no arbitrary user amount or later fill used retrospectively |
| Dependency fingerprints and conflict state | Bind all required inputs, units, policy/approval references, comparability and limitations; reject duplicate/conflicting or tampered dependencies; exclude future evidence before selection |

Source classification for a future accepted producer should be conceptually
`DETERMINISTIC_HSI_DERIVED_SCENARIO`, composed from canonical facts, approved
policy parameters and allowed preferences. This is a proposed authority role,
not a new enum or an admitted source. Current `USER_APPROVED_CONTEXT` and
[source-authority rejection](../../app/gates/source_authority.py) stay unchanged.
The independently configured verifier must reproduce the scenario and bind both
economic operands to it; two individually plausible numbers are insufficient.

`USER_PREFERENCE` may choose a policy-allowed horizon or preference only after
the policy permits it. It is not `HARD_GATE_ECONOMIC_FACT`. User-entered return,
tax/slippage assertions, Gemini/LLM forecasts, source-name claims, policy hashes,
scores, diagnostic counts and target-price arithmetic cannot satisfy Gate 1.

## 7. Reuse, calibration and one future policy authority

Reuse [RotationEvaluationContext / candidate / holding / comparison](../../app/rotation/models.py)
for their existing exact identities, portfolio snapshot reference, as-of/known-at,
comparison score and descriptive source context. They contain no complete
capital-switch or return distribution. The [rotation engine](../../app/rotation/engine.py)
compares caller-supplied benefits and friction; its `>=` comparison is not Gate 1's
strict `>` economic boundary. It also consumes gate results: using its final
positive output to satisfy the same gate would create a cycle. Share validated
upstream facts, not another engine or circular clearance.

[TradePlan](../../app/signals/models.py) owns planned entry/zone, stop, targets
and descriptive `time_horizon`. Gate 4 uses its distinct management-plan carrier
and its own still-required admission. No current contract authorizes Gate 1 to
extract expected return from either. A later explicitly governed shared upstream
scenario could reuse a valid entry assumption without depending on a Gate 4 PASS;
such integration is deferred. Neither plan nor portfolio is changed here.

Calibration classification remains **`UNRESOLVED`** because the economic method
is unselected. Fixed rate arithmetic does not require empirical calibration;
expectation/probability, slippage proxies and economic decision performance may.
For option D an eventual probability-based policy requires calibration before
activation. Even option C requires an approved shadow-evaluation/limitations plan
before activation; deterministic arithmetic alone is not economic validation.
Fundamental V2 B14 is a versioned outcome-compatibility prerequisite if those
capabilities are used, not an automatic Gate 1 forecast authority. No B14 work runs.

For the bounded pilot, the minimum useful next deliverable is a complete, honest
conditional-scenario policy definition using existing evidence and cost utilities.
Unavailable required endpoints, taxes, slippage or comparability keep rotation
economics unavailable. User count grants no exception. Research comparisons
continue under their own current boundaries.

The existing sole future whole-policy candidate is
`execution-gate-policy-v2-proposed / v2-proposal.3`, with
[conditional composite approval](EXECUTION_GATE_POLICY_V2_COMPOSITE_GOVERNANCE_APPROVAL.md).
It pins Gate 1 unchanged. A later material Gate 1 proposal must amend that same
successor line through a new composite fingerprint and governance decision.
The .3 proposal/approval and Gate 3/Gate 6 work remain immutable and inactive.
This repair creates no competing V2, selects no successor version and transfers
no prior approval automatically.

## 8. Validation and protected state

The [repair proofs](../../tests/unit/test_gate1_rotation_policy_definition_repair.py)
exercise frozen formula boundaries/precedence, conditional same-base dimensional
algebra, original-history pins, missing comparator/horizon claims, explicit
friction/tax terms, real rejection of AI/user values, PIT and tamper rejection,
and unchanged composite policy fingerprints. Synthetic values prove arithmetic
only; no economic producer, tax/slippage estimator or unit adapter is implemented.
Existing Gate, policy, provenance, challenger and composite tests are rerun.
Final results: **57 focused passed / 0 failed / 0 skipped / 2 warnings** and
**215 relevant passed / 0 failed / 0 skipped / 2 warnings**. Warnings are the
existing Starlette/httpx and AnyIO deprecations. The first focused run caught an
incorrect audit-test assumption about the earliest inclusive hurdle; the test
and historical account now pin the accepted strict production-policy commit.
No application defect or runtime change was involved. Local Markdown validation
checked 294 links across this document and README, plus table column structure.
No full backend suite, external acquisition, production database operation or
runtime job is required or performed. Markdown links and diff whitespace are
checked before the local commit. No push.

```text
V1_ACTIVE = TRUE
GATE_POLICY_V2_ACTIVE = FALSE
SIX_GATES_EXACTLY_SIX = TRUE
NO_FABRICATED_ECONOMIC_RETURN = TRUE
NO_FABRICATED_SWITCHING_FRICTION = TRUE
NO_FUTURE_LEAKAGE = TRUE
NO_USER_ENTERED_GATE1_EXPECTED_RETURN_AUTHORITY = TRUE
PILOT_SIMPLICITY_RULE = ACTIVE
AI_DECISION_AUTHORITY = FALSE
```

Exactly one next continuation: **`GATE1_ROTATION_POLICY_V2_PROPOSAL`**.
It is not started by this slice.
