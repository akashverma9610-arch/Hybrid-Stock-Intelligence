# Gate 1 Rotation Policy V2 Proposal

Status: **`PROPOSED / NOT_ACTIVE`**. No implementation or activation approval.
Baseline: `33f32f5821943406f2c8d7988811d01da1e6ab74`, clean `main`.

Policy recommendation: **`DETERMINISTIC_INR_ROTATION_ADVANTAGE_RECOMMENDED`**.
Result: **`GATE1_V2_PROPOSAL_COHERENT_COMPOSITE_V2_4_REQUIRED`**.

The [machine-readable proposal](GATE1_ROTATION_POLICY_V2_PROPOSAL.json) defines
`execution-gate-policy-v2-proposed / v2-proposal.4`, parent
`six-gates-production-v1 / v1`. It is a proposed revision of the **same single
successor line**, not a competing Gate 1 policy authority. The
[accepted repair](GATE1_ROTATION_POLICY_DEFINITION_REPAIR_V1.md) established why
new economic meaning cannot silently enter V1.

The [.3 proposal](GATE3_SURVEILLANCE_POLICY_V2_PROPOSAL.json) and its
[conditional composite approval](EXECUTION_GATE_POLICY_V2_COMPOSITE_GOVERNANCE_APPROVAL.json)
remain immutable. Their approval does **not** approve .4. This document neither
revokes .3's historical approval nor activates either candidate. New composite
governance must review the complete .4 fingerprint before implementation/activation
steps are separately authorized.

## 1. Exact V1 to proposed V2 delta

| Dimension | Accepted V1 | Proposed .4 Gate 1 |
| --- | --- | --- |
| Action | `ROTATE_IN` only | Unchanged; replacement of an exact incumbent parcel |
| Score | Candidate raw score minus incumbent comparison score `>= 1.00` points | Identical independent hurdle and canonical score provenance |
| Benefit | `expected_incremental_return`, undefined unit/comparator/horizon | `gross_rotation_scenario_advantage_inr`: candidate modeled terminal value minus incumbent continuation modeled terminal value |
| Comparator | Economic counterfactual ungoverned | Exact incumbent **no-rotation continuation**, same capital and common horizon |
| Unit | Return unspecified; cost helper INR | Both operands nominal, undiscounted INR; not percent/bps/R units |
| Cost | `modeled_switching_friction`, partial approved helper | `modeled_switching_friction_inr`, complete disjoint execution-cost plus mandatory tax-realization manifest |
| Economic hurdle | Return minus cost strictly `> 0.00` | Scenario advantage minus governed cost strictly `> 0.00` INR |
| Authority | Caller economic values currently rejected | Proposed independently verified `DETERMINISTIC_HSI_DERIVED_SCENARIO`; not registered |
| History | Existing records and engine | Never alias/relabel V1 fields, fingerprints or prior outcomes as .4 |

All six IDs remain exactly `GATE_1_ROTATION`, `GATE_2_VELOCITY`,
`GATE_3_SURVEILLANCE`, `GATE_4_TRADE_PLAN`, `GATE_5_HEAT`, `GATE_6_EARNINGS`.
Gates 2/4/5 definitions and methods remain pinned unchanged. Production V1's
entire Gate 1 method/configuration, including strict-zero precedence, is untouched.

## 2. Comparator, capital, scope and horizon

`C = switched_capital_inr` is the **positive gross decision-reference value of
the actual incumbent parcel selected for reallocation, before switching costs**:

```text
C = selected_incumbent_quantity * incumbent_reference_price_inr
candidate_purchase_turnover_inr + candidate_residual_capital_inr = C
```

The first identity binds the sale leg's reference turnover to `C`; it is not an
actual fill claim. The second reconciles the candidate deployment to the **same
C**, including any uninvested residual. It is not a position-sizing algorithm.
The future contract must verify canonical holding quantity, selected lots,
`0 < selected_quantity <= held_quantity`, positive finite prices and nonnegative
deployment/residual. The exact candidate and incumbent identities must differ
and match the score/portfolio provenance. No fuzzy/provider-token substitute.

The no-rotation scenario retains that exact parcel, not the whole portfolio and
not a zero-return placeholder. Untouched incumbent quantity is excluded from
both compared legs and must not produce spurious advantage. A full switch uses
the whole selected holding only when explicitly evidenced; a partial switch
uses its actual smaller parcel. Costs/tax lots cannot be scaled from a full
holding by an assumed proportional rate. NAV is never a denominator.

**Funding and cost reconciliation are required, not assumed.** Gross scenario
values exclude every cost subsequently subtracted. If costs instead reduce
candidate deployment, subtracting the same costs again is invalid. A separately
governed funding/residual convention must explain any fee reserve, cash residual,
whole-unit constraint and its treatment in both terminal values. Unknown cash
does not become available funding; residual yield is not defaulted to zero.
`funding_and_residual_policy = POLICY_UNSET` blocks admission until that convention
is approved and evidenced. This prevents the common-capital definition from
silently assuming free financing or fractional executions.

| Context | Gate 1 treatment |
| --- | --- |
| New-position replacement / holding-to-holding `ROTATE_IN` | Economic comparison required |
| Partial/full replacement | Only exact evidenced switched parcel; no full-position default |
| Cash-funded `FRESH_ENTRY` | Existing not-applicable PASS; no cash comparator |
| `ADD_TO_POSITION` | Existing not-applicable PASS; no tranche expansion |
| Other existing non-rotation contexts | Existing exemptions retained; not a whole Six-Gates clearance |

`rotation_evaluation_horizon` is a required governed reference: identity,
version/fingerprint, start at `decision_as_of`, explicit terminal endpoint,
precision/calendar and endpoint convention. Candidate and incumbent must bind
the **same reference and endpoint**. Terminal endpoint is after the decision;
it is a modeled future point, not observed future evidence. No numeric duration
is selected. Short/positional/long labels or `TradePlan.time_horizon` cannot
substitute for the reference. Missing binding yields `INSUFFICIENT_DATA`.

[Fundamental V2 B09](FUNDAMENTAL_DIAGNOSTIC_REGISTRY_V2_GOVERNANCE_APPROVAL.json)
requires a V2-compatible horizon/applicability contract when that registry is
used. It supplies no numeric rotation horizon. This remains a conditional B09
compatibility dependency plus an unconditional Gate 1 common-horizon requirement.
Gate 6's earnings-risk window, including its independently unset calibration,
is a different concept; similarly numbered blocker namespaces are not aliases.

## 3. Deterministic quantity, endpoints and limits

```text
gross_rotation_scenario_advantage_inr
  = candidate_scenario_terminal_value_inr
  - incumbent_continuation_terminal_value_inr

net_rotation_scenario_advantage_inr
  = gross_rotation_scenario_advantage_inr
  - modeled_switching_friction_inr

economic hurdle: net_rotation_scenario_advantage_inr > 0.00
```

Both terminal values are cost-exclusive, modeled marked wealth for the same
capital/cutoff/horizon and compatible scenario assumptions. They are **not** a
promise, expected value, realized return or probability. There is no assumed
sale at the terminal endpoint. All operands use the same nominal INR valuation
basis; no discounting, compounding of fees or opportunity-cost penalty is added.
This is a conditional scenario metric, not a complete after-tax investment NPV.
Amounts must be finite, exact decimal values with explicit units, not silently
coerced floats. Terminal wealth/costs are nonnegative; gross advantage may be
negative. Rounding rules remain a model-policy dependency, never an implicit
round-up that changes strict-zero equality into a PASS.

`ROTATION_SCENARIO_MODEL = POLICY_UNSET`. Its future methodology must govern
terminal marks, distributions/dividends/corporate-action bases, funding, residuals,
applicability/invalidation, precision and rounding. Candidate/incumbent producer
versions must be jointly compatible and economically symmetric where appropriate;
any justified asymmetry must be explicit. Both modeled values must be generated
from evidence already known by the decision cutoff. The future terminal date
does not permit using a price actually observed after that cutoff.

Price structure, valuation, thesis evidence and TradePlan are possible upstream
facts **only after separate producer governance**. A target endpoint does not
become an expectation or admitted terminal value by subtraction or relabelling.
Decision Score is neither probability nor money. No probability/win-rate input
is required for this deterministic contract. No endpoint or model is implemented.

## 4. Friction, tax and slippage decisions

The proposed breakdown is explicit, with every amount INR and counted once:

```text
execution_switching_cost_inr
  = purchase_statutory_costs_inr + sale_statutory_costs_inr
  + nse_member_transaction_charge_inr + brokerage_inr + slippage_inr + gst_inr

modeled_switching_friction_inr
  = execution_switching_cost_inr + tax_realization_impact_inr
```

These costs arise from switching now, not assumed liquidation of both positions
at the horizon. Gross endpoints must exclude the same included costs; no second
tax/fee deduction. Retention of a component is a **proposal**, not proof its
current rate/base or producer is available.

| Component | Decision | Future authority, base and boundary |
| --- | --- | --- |
| Purchase STT/SEBI/stamp | `RETAIN` | Official effective/local-known rate version on exact purchase-side turnover; scope/rounding verified |
| Sale STT/SEBI | `RETAIN` | Same requirements on exact selected incumbent sale-side turnover |
| NSE member transaction charge | `RETAIN` | Verify actual official charge scope, turnover sides and GST overlap; no duplicate exchange-charge line |
| Brokerage | `RETAIN` | Independently governed broker/account schedule and both-leg calculation; not caller-entered rupees |
| GST | `RETAIN` | Explicit governed taxable-service base times official versioned rate; the base is not another charge |
| Slippage | `SEPARATE_POLICY_REQUIRED`, **mandatory** | Side/reference-price methodology and independently admitted evidence; current producer `NOT_READY` |
| Capital-gains tax | `SEPARATE_POLICY_REQUIRED`, **mandatory** | Selected-lot tax-realization policy, canonical cost basis/acquisition history and relevant verified user/rule circumstances |
| Separate spread/impact/liquidity penalty | No new term | Absorption within slippage requires later governance; no assumed zero or double counting |

No new current rates are hard-coded and no external rate validity is claimed.
The [V1 helper](../../app/gates/production_policy.py) is reusable arithmetic only
after its scope/rates/base interpretation are confirmed compatible. Every
retained statutory input needs rate/source identity, source fingerprint,
effective applicability, HSI known-at, side, base and rounding provenance.
No automatic inheritance of stale statutory constants.

**Tax choice T1:** retain mandatory, nonnegative tax impact attributable to the
selected incumbent disposal. Separate it visibly from execution costs, but
Gate 1 consumes their **sum**. This does not create a universal personal-tax
calculator. Tax policy remains unset; missing tax blocks the economic branch.
Loss credits, netting and future tax benefits are not invented or admitted.
T2 (exclude tax from the universal hurdle and delegate elsewhere) is not selected:
without a separate mandatory boundary it would change V1's net-cost protection.
T3 has no better supported model here. Tax presentation separation is not removal.

Slippage remains mandatory; no OHLC proxy, broker-fill assumption or default
zero is introduced. Every included cost is nonnegative; even a claimed zero
requires independently admitted evidence under policy. A missing component,
unresolved taxable base or ambiguous cost overlap yields insufficiency.

## 5. Authority, PIT and result contract

The proposed authority class is `DETERMINISTIC_HSI_DERIVED_SCENARIO`, composed
from canonical facts and approved model parameters. No enum/producer is registered.
An independently configured verifier must reproduce the scenario, confirm both
operands and bind the economic pair/capital/horizon to the score comparison.
Arbitrary user context, self-hashes and approved-policy labels cannot do this.
Users may supply legitimate facts/preferences through governed intake, but may
not type a return or friction amount to satisfy the gate. AI may later explain
admitted results, never populate economics, tax, slippage, probability or gate state.

Required immutable lineage includes decision-as-of, exact candidate/incumbent,
portfolio snapshot ID/fingerprint, selected quantity/lots, capital, both reference
prices/bases, common horizon/version/endpoint, paired model versions, cost/rate/
tax/slippage policies, funding/residual conventions, source IDs/fingerprints and
scenario fingerprint. A modeled price remains a reference, not an actual fill.

Known-at and observation-as-of boundaries are inclusive `<= decision_as_of`,
UTC-normalized; policy approval/effectiveness must also be valid by that cutoff.
Common market-state cutoff and approved freshness/application rules are required;
no invented age limit or infinite validity. Filter future inputs before resolving
conflicts or revisions; never use later portfolio state or outcome data. Distinct
applicable conflicting receipts yield insufficiency; identical receipt/content
is idempotent, with lineage retained. Supersession needs an explicit visible relation.

Scenario identity binds the versioned canonical input manifest and composite
fingerprint; its content fingerprint binds the complete body excluding only its
derived identity/self-fingerprint. Required inputs are never omitted from the
fingerprint. Canonical ordering follows duplicate/conflict validation; no runtime
clock, locale, unordered iteration or historical backdating affects identity.
These are future contract requirements, not a new persistence design.

| Order | Proposed result |
| --- | --- |
| Unapproved/incompatible composite/configuration or unverified supplied source | Admission rejection or `INSUFFICIENT_DATA`, never clearance |
| Admitted non-rotation context | Existing not-applicable `PASS` |
| Required score missing | `INSUFFICIENT_DATA` |
| Valid score advantage below `1.00` | `FAIL`, even if economics are missing |
| Required scenario missing/unset/stale/conflicted/future-only/incompatible | `INSUFFICIENT_DATA` |
| Complete valid scenario net `<= 0.00` | `FAIL` |
| Complete valid scenario net `> 0.00`, score hurdle met | `PASS` |

This preserves score-failure precedence, strict economic equality failure and
source rejection before arithmetic. PASS annotation `1.0` retains V1 semantics,
not prediction confidence. No seventh gate or new reducer state is proposed.
The existing six-result reducer and all independent prerequisites remain intact;
`EXECUTABLE` remains an evidence classification, never broker/capital authority.

## 6. Composite carry-forward and downstream review

The JSON pins .3 proposal fingerprint
`sha256:57bbd7af01fe14fa95ae419187302d5dcc353e3cbd98181e43b5f691cb97ab3d`
and approval fingerprint
`sha256:caad6fb766fbcf93ea4859a94454c78d57ba59551274601eba9741486ae7d30e`.
It additionally fingerprints component bundles and source files. Pinned references
are incorporated by content, not a mutable latest-policy lookup:

- Gate 3: current-effective NSE selection, source identity/known-at/completeness,
  four-session freshness, unchanged thresholds, completeness-before-failure,
  no independent-veto shortcut and descriptive security status all retained.
- Gate 6: verified-event-veto mode, `.2` component/approval chain, no-veto PASS
  with null confidence and `EARNINGS_CLEARANCE_UNVERIFIED`, residual-source-risk
  acceptance, no retroactive blackout and unset calibrated horizon all retained.
- All .3 component activation constraints, reducer and historical isolation
  requirements are incorporated. Historical blocker receipts are not rewritten
  or presented as freshly measured state. Later closure evidence must be explicitly
  reconciled at new composite approval; this slice certifies no operational closure.

| Consumer | Classification | Exact review boundary |
| --- | --- | --- |
| [Six-Gates orchestration](../../app/gates/source_authority.py) | `ADAPTER_UPDATE_REQUIRED` | One engine; .4 selection and shared scenario verifier; no old-field alias |
| [Rotation Challenger](../../app/rotation/engine.py) | `ADAPTER_UPDATE_REQUIRED / POLICY_REVIEW_REQUIRED` | Reuse identities/context; candidate-global caller economics and inclusive friction checks are not pair-bound .4 proof |
| [Brain](../../app/intelligence/six_gates_evidence.py) | `ADAPTER_UPDATE_REQUIRED` | Preserve scenario/policy/as-of/limitations and inherited Gate 6 metadata; no second Brain |
| [Signals](../../app/signals/engine.py) | `ADAPTER_UPDATE_REQUIRED / POLICY_REVIEW_REQUIRED` | Versioned descriptive semantics, no implied trade action |
| [Portfolio](../../app/portfolio/canonical_six_gates_activation.py) | `ADAPTER_UPDATE_REQUIRED / POLICY_REVIEW_REQUIRED` | Existing call supplies candidate score, not an incumbent argument; future paired adapter required, no position mutation |
| [Entry-ready lifecycle](../../app/brain_output_requirement_policy.py) | `POLICY_REVIEW_REQUIRED` | All score/setup/gate prerequisites retained; single Gate 1 PASS is not readiness |
| [Backtest/replay](../../app/backtest/analytical.py) | `REPLAY_UPDATE_REQUIRED` | Exact version and decision-time inputs; no V1 relabelling or outcomes as forecasts |
| [Outcome ledger](../../app/paper/models.py) | `ADAPTER_UPDATE_REQUIRED / CALIBRATION_REQUIRED` | Separate modeled scenario from observed outcomes/cohorts; no fabricated trade rows |
| [TradePlan](../../app/signals/models.py) | `NO_CHANGE` | Keep Gate 4 ownership; shared upstream facts require producer approval, never Gate 4 PASS as input |
| [Decision Score](../../app/scoring/engine.py) | `NO_CHANGE` | Existing score weights, units and provenance unchanged |
| Alerts | `POLICY_REVIEW_REQUIRED` | Disabled pending truthful wording/dedup; no automatic action |

The [rotation contracts](../../app/rotation/models.py) already retain exact pair
identities, snapshot reference and PIT comparison context. They do not contain
a governed capital/endpoint producer. Challenger output consumes gate results;
feeding its final clearance back into Gate 1 would be circular. No second engine,
portfolio model, TradePlan implementation or source of truth is proposed.

## 7. Activation blockers, calibration and alternatives

All new `G1B01`–`G1B15` entries in the machine proposal are **BLOCKING**:
comparator contract; horizon/B09 compatibility; switched capital/funding;
candidate producer; incumbent producer; friction manifest; statutory rate
versioning; tax policy; slippage producer; independent authority; one Gate 1
adapter; challenger/consumer compatibility; replay isolation; new composite
approval/selection; scenario shadow/calibration compatibility.

`G1B16` complete historical archives is `DEFERRED_FOR_REPLAY`;
`G1B17` extended prospective outcome accumulation is `DEFERRED_FOR_SHADOW`;
`G1B18` optional disabled alerts is `NON_BLOCKING`. These deferrals do not waive
pre-activation tests, source proof or limitations review. Existing Gate 3/Gate 6
blockers and accepted risk constraints remain independently applicable.

Calibration decision: **`BEFORE_ACTIVATION`** for the scenario's governed
validation/limitations and outcome-compatible shadow methodology. A semantic
contract can later be implemented without fitting a probability model. If the
selected endpoint/slippage method uses outcome statistics, its calibration must
precede activation. Fundamental B14 compatibility is conditional on using those
economic-classification capabilities; it is not a probability source. No B14
work begins. Deterministic arithmetic is not empirical validation. A perfect
historical archive is not an automatic prerequisite for a prospective pilot.

| Option | Semantics / units | Capital and partial behavior | Tax/slippage; horizon/PIT | Calibration / pilot complexity |
| --- | --- | --- | --- | --- |
| A: deterministic INR | Honest conditional gross-minus-cost amount | Exact parcel cash-flow audit; costs can be nonlinear; no denominator choice | All same-scenario INR; actual lots/legs; common horizon and frozen inputs required | Recommended; simplest auditable conservation/accounting representation, no probability claim; real model still blocked |
| B: deterministic rate/bps | Coherent on one positive common capital with explicit scale | Same economic size/lot issues remain; extra normalization and rounding | Must normalize every cost on identical base; same horizon/PIT | No added evidence; more unit/rounding surface. Not selected |
| C: probability-weighted expected value | Requires approved outcomes/distribution/dependence | Same actual-capital and tax/lot constraints | Common horizon plus training cutoff; no score-as-probability | Highest calibration/data burden, not required by original holding-comparison intent. Not selected |
| D: indefinitely blocked | Honest about missing evidence, no defined future comparison | No usable contract | Current fail-closed behavior retained | Necessary current state, not preferred indefinite architecture decision |

INR is selected not merely because V1 costs use it: it directly reconciles the
actual parcel and both cost legs, preserves size/nonlinear-tax visibility, supports
partial-rotation audits and avoids a second denominator/scale/rounding convention.
Normalized values add no evidence or protection to the unchanged strict-zero
test. INR alone still confers no truth on endpoints or fee assumptions.

## 8. Validation and stop boundary

[Proposal tests](../../tests/unit/test_gate1_rotation_policy_v2_proposal.py) check
the exact six gates, source/history pins, Gate 2/4/5 unchanged definitions/methods,
Gate 3/Gate 6 carry-forward bundles, no approval transfer, independent score and
strict-zero algebra, same-capital/horizon witnesses, funding/tax/slippage and
PIT boundaries, user/AI rejection, and deterministic complete fingerprints.
Synthetic terminal values are test witnesses, not models or readiness evidence.
Markdown links and staged whitespace are checked. No full backend suite is
needed or run because no runtime code changes.

Final validation: **80 focused passed / 0 failed / 0 skipped / 0 warnings**;
**370 relevant passed / 0 failed / 0 skipped / 2 warnings** (existing
Starlette/httpx and AnyIO deprecations). Twenty-two baseline file fingerprints
and the inherited component/approval bundles remain unchanged. Markdown checks
cover 293 local links in this document and README, table columns and whitespace.
No production DB read/write, provider call, runtime job or order operation was
performed. This proof closes the proposal slice, not source readiness or activation.

```text
V1_ACTIVE = TRUE
GATE_POLICY_V2_ACTIVE = FALSE
SIX_GATES_EXACTLY_SIX = TRUE
NO_FABRICATED_ECONOMIC_RETURN = TRUE
NO_FABRICATED_SWITCHING_FRICTION = TRUE
NO_FUTURE_LEAKAGE = TRUE
NO_USER_ENTERED_GATE1_EXPECTED_RETURN_AUTHORITY = TRUE
NO_AI_ECONOMIC_AUTHORITY = TRUE
PILOT_SIMPLICITY_RULE = ACTIVE
AI_DECISION_AUTHORITY = FALSE
```

Exactly one next continuation:
**`EXECUTION_GATE_POLICY_V2_COMPOSITE_GOVERNANCE_APPROVAL_2`**.
It is not started here. Local proposal commit only; no push.
