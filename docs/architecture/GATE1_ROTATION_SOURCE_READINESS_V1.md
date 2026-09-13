# Gate 1 Rotation Source Readiness V1

**Status:** `GATE1_ROTATION_POLICY_DEFINITION_REPAIR_REQUIRED / DOCUMENTATION_ONLY / V1_ACTIVE / GATE_POLICY_V2_INACTIVE / NOT_ACTIVE`.

**Decision:** **C — `GATE1_ROTATION_POLICY_DEFINITION_REPAIR_REQUIRED`.** Gate 1 has a live, deterministic arithmetic branch and an approved fixed cash-delivery friction parameter set. It does **not** have a governed definition, unit, horizon, scenario contract, or admitted deterministic producer for `expected_incremental_return`; nor does it have an admitted scenario producer for `modeled_switching_friction`. Therefore the dominant next work is a policy-definition repair, not market-data acquisition, a broker integration, a calibration run, or a second rotation engine.

This is a read-only source-readiness assessment of the frozen V1 gate contract. It changes no Gate 1 formula, threshold, policy selection, Gate 2–6 behavior, portfolio model, Decision Score, provider, database, API, UI, runtime, order, broker, or execution authority. The machine-readable assessment is [the immutable receipt](GATE1_ROTATION_SOURCE_READINESS_V1.json).

## 1. Exact frozen V1 runtime contract

`ExecutionGateEngine` remains a read-only eligibility evaluator. It emits the existing `NO_ACTION_OR_ORDER_CREATED` warning and cannot place an order or mutate a portfolio.

| Contract element | Exact current behavior | Consequence |
| --- | --- | --- |
| Gate | `GATE_1_ROTATION`, exactly one of six gates | This assessment does not add a seventh gate or activate Composite V2. |
| Economic action scope | Only `ROTATE_IN` reaches the score and economic checks | `FRESH_ENTRY`, `ADD_TO_POSITION`, `HOLD_EXISTING`, `REDUCE_EXISTING`, `EXIT_EXISTING`, and `RISK_MANAGEMENT` return `PASS` with `not applicable: no holding is being replaced`. This is an existing context exemption, not evidence clearance. |
| Score inputs | `raw_decision_score: Decimal | None`, `comparison_score: Decimal | None` | Both are required only for `ROTATE_IN`. Their difference is in Decision Score points, not monetary return. |
| Score rule | `raw_decision_score - comparison_score < min_score_advantage` → `FAIL` | The active fixed hurdle is `1.00` score points; equality meets this score branch. Missing either score gives `INSUFFICIENT_DATA`. |
| Economic inputs | `expected_incremental_return: Decimal | None`, `modeled_switching_friction: Decimal | None` | Both are required when `require_economic_hurdle=True`; their bare `Decimal` types carry no unit, horizon, comparator, or calculation contract. |
| Economic rule | `expected_incremental_return - modeled_switching_friction <= net_economic_hurdle` → `FAIL` | The active fixed hurdle is `0.00`; the net benefit must be **strictly greater** than zero. Missing either input gives `INSUFFICIENT_DATA`. |
| Unresolved configuration | Missing `min_score_advantage` or `friction_model_version` → `INSUFFICIENT_DATA` | The active selected production policy supplies both; this does not admit a caller scenario. |
| Confidence | `PASS` carries the existing constant annotation `1.0`; `FAIL` and `INSUFFICIENT_DATA` carry `None` | It is not a measured probability, return confidence, or source-confidence formula. |
| Evaluation admission | Gate input snapshot as-of must exactly equal evaluation as-of; every populated domain input requires versioned lineage and independently configured authority | Caller-provided values, hashes, or source labels cannot confer authority. Current authority rejects both economic inputs before arithmetic. |

The exact active configuration is `six-gates-production-v1 / v1`, with `min_score_advantage=1.00`, `friction_model_version=nse-cash-delivery-friction-v1`, `net_economic_hurdle=0.00`, and `require_economic_hurdle=True`. These values are recorded, not recalibrated, by this audit.

## 2. Substantive Gate 1 inputs and readiness

The two known open inputs remain the only substantive economic inputs in the current `GateInput` contract. `raw_decision_score` and `comparison_score` are independently governed score inputs, not economic-return inputs.

| Input | Current semantic definition | Unit | Authority type | Existing deterministic producer | PIT / horizon | Current readiness | Pilot readiness |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `expected_incremental_return` | **`POLICY_DEFINITION_MISSING`**. No repository authority says whether this is candidate-minus-incumbent return, candidate-above-cash return, a rotation-specific benefit, or another measure. | `UNSPECIFIED`; dimensional compatibility with friction is unproved. | Intended `DERIVED_SCENARIO`, not an exchange fact. | None. Rotation/backtest callers can carry hypothetical benefit values, but neither produces an admitted Gate 1 value. Decision Score, targets, valuation, thesis, and paper outcomes are not converted. | The input must be known at the decision as-of, but no holding horizon, return definition, or probability method is bound. | `POLICY_BLOCKED` | Not ready until a policy defines the scenario and its evidence. |
| `modeled_switching_friction` | A partial formula exists: effective-dated statutory rates plus explicit scenario costs for an NSE cash-delivery switch. | Formula result is an absolute INR amount; turnover inputs are monetary amounts. | `DERIVED_SCENARIO_PLUS_POLICY_PARAMETERS`. | `NseCashDeliveryFrictionModel` can calculate only when every required scenario cost is present. No authority admits its output as Gate 1 evidence. | Fixed policy is effective-dated; required scenario inputs have no approved source, `known_at`, or scenario receipt. Cost formula has no return horizon by itself. | `PARTIAL` policy formula, `NOT_READY` producer/authority | Not ready until scenario semantics and source binding are approved. |

`DOMAIN_FIELDS` currently labels both fields `USER_APPROVED_CONTEXT`. That is a nominal domain family for provenance admission, not an approved user assertion, scenario definition, or source authority. The readiness classification above identifies what a valid future authority would need to verify.

`expected_incremental_return` is a name only, not an approved forecast model. The existing runtime does not state that it is probability-weighted, nor define a payoff or probability. Accordingly no probability is currently required by arithmetic, and no probability may be invented. Whether a future definition needs probability, deterministic structural payoff, calibrated outcome statistics, or another governed method is a required policy decision.

## 3. Friction policy: exact existing meaning and gaps

The approved `nse-cash-delivery-friction-v1` model is explicitly documented as “effective-dated official charges plus explicit user-specific inputs.” Its result is:

```text
purchase_turnover × (STT_purchase + SEBI_each_side + stamp_duty_purchase)
+ sale_turnover × (STT_sale + SEBI_each_side)
+ (purchase_turnover + sale_turnover) × NSE_member_outflow_per_crore_each_side / 10,000,000
+ brokerage + slippage + capital_gains_tax
+ GST_taxable_services × GST_rate
```

The fixed policy parameters are statutory/exchange rates and the NSE member outflow. They are integrity-bound and effective-dated. The function returns `None` unless every scenario input below is supplied:

| Component | Current state | Audit boundary |
| --- | --- | --- |
| `purchase_turnover`, `sale_turnover` | `NOT_READY` scenario inputs | No Gate 1 scenario says which candidate/incumbent amount, scale, or portfolio binding is authoritative. |
| Brokerage | `NOT_READY` | The model accepts an explicit amount; there is no broker or account fee policy, and Dhan/Upstox presence does not define one. |
| Slippage | `NOT_READY` | It is required for a non-null formula output. No measured source or approved proxy exists. OHLC, spread, or a guessed percentage cannot populate it. |
| Capital-gains tax | `NOT_READY` scenario input | Tax is not excluded: it is explicitly accepted by the formula. No user-specific tax classification, amount, or treatment is governed here. |
| GST-taxable services | `NOT_READY` scenario input | The policy fixes the GST rate but not the taxable-service amount. |
| Statutory/exchange parameters | `READY` fixed policy inputs | They do not determine a complete switching-cost amount without the scenario inputs. |

Thus the friction formula is broker-neutral only for its fixed statutory/exchange component. It is neither an actual-broker/account cost model nor a complete broker-neutral scenario. It cannot be treated as a percentage return, basis-point value, R-multiple, or portfolio percentage. Since the return field has no stated unit, the live subtraction is dimensionally ungoverned. This alone prohibits producer activation.

## 4. Comparator, cash, add, portfolio, and TradePlan boundaries

| Area | Actual current contract | Prohibited inference |
| --- | --- | --- |
| Incumbent comparison | Gate 1 accepts only a numeric `comparison_score`; `GateInput` has no incumbent instrument identity or economic-comparator field. | The score comparison cannot identify the incumbent, position amount, cost basis, exit price, or return. |
| Cash | There is no cash-specific Gate 1 branch, cash comparator, or cash-friction exemption. A non-`ROTATE_IN` context is merely the existing not-applicable path. | Do not call `ROTATE_IN` a cash case or derive a candidate-above-cash return. |
| Add / tranche | `ADD_TO_POSITION` is not a Gate 1 economic branch. | Do not reuse rotation economics for an add. |
| Portfolio | There is one persisted portfolio snapshot, but it is partial and its cash state is `UNKNOWN`; no Gate 1 economic-scenario receipt or production rotation evaluation exists. | The current personal portfolio is not a producer requirement and is not used by this audit. |
| Rotation Challenger | It accepts `expected_incremental_benefit` and `modeled_switching_friction` as caller-supplied candidate fields and can compare them. | It has no Gate 1 source authority, unit/horizon contract, or scenario calculation; it cannot be relabelled a producer. |
| TradePlan | Generic `TradePlan` has structural stop/target references, but lacks the Gate 4 management fields and an instrument/as-of Gate 1 economic contract. | A target, stop, or reward structure is not an expected return, and Gate 1 may not secretly depend on Gate 4. |
| Backtest / outcome data | Existing replay accepts caller-provided economics. | Replay values are not a live decision-time producer, calibration proof, or forecast. |

This preserves one rotation model and one portfolio model. Any future economic scenario must reuse their valid canonical identities and evidence envelopes rather than create parallel models.

## 5. PIT, provenance, and fail-closed behavior

For every populated economic input, V1 already requires a `GateEvidenceLineage` binding with an input field, source identity/version/policy, fingerprints, `as_of`, `known_at`, and execution-eligibility flags. `GateEvidenceContext` rejects a dependency whose `as_of` or `known_at` is later than evaluation as-of, and gate input snapshot as-of must equal the evaluation as-of.

Those mechanics are necessary but not sufficient: there is no accepted authority that independently reconstructs either economic value. `UnavailableGateAuthority` and `RepositoryGateAuthority` both identify the two source gaps as `SOURCE_GOVERNANCE_REQUIRED / GATE1_FRICTION_POLICY_AUTHORITY_NOT_READY`, then reject before any Gate 1 formula. Binding a value to the selected policy fingerprint still fails; a policy hash is not scenario authority.

Missing economic values at the direct frozen formula boundary return `INSUFFICIENT_DATA`, never zero, `PASS`, or a fabricated `FAIL`. A self-attested populated value is rejected before formula evaluation rather than granted a synthetic pass. Future realized returns, later liquidity, later portfolio state, AI/LLM output, Decision Score points, or wall-clock interpretation cannot construct decision-time evidence.

## 6. Synthetic liveness and bounded current-readiness observation

Synthetic fixture evidence proves only code liveness:

| Path | Result under synthetic valid inputs | Production-evidence meaning |
| --- | --- | --- |
| Score advantage below `1.00` | `FAIL` | Formula behavior only. |
| Score advantage sufficient, missing economic input | `INSUFFICIENT_DATA` | No default economic value is applied. |
| Score advantage sufficient, net economic value exactly `0.00` | `FAIL` | The economic comparator is strictly greater than the fixed hurdle. |
| Score advantage sufficient, net economic value greater than `0.00` | `PASS` | Synthetic arithmetic only; it does not bypass source authority or establish production readiness. |

The bounded read-only SQLite audit records: one selected production policy, three canonical Decision Scorecards, one partial portfolio snapshot, and zero canonical Gate evaluations, rotation evaluations, rotation comparisons, TradePlans, or Gate 1 economic scenario receipts. No database row was written and no whole-market scan ran. The scorecards may support score provenance in their own contract; they do not supply the missing economic scenario.

## 7. Dominant blocker and smallest truthful next slice

The blocker classification is deliberately split:

| Need | Correct blocker classification | Why it is not merely data missing |
| --- | --- | --- |
| Return comparator / meaning | `POLICY_DEFINITION_MISSING` | Neither cash versus incumbent nor rotation-specific benefit is defined. |
| Return unit and horizon | `HORIZON_BINDING_MISSING` and dimensional policy missing | A bare `Decimal` cannot be safely subtracted from an INR cost without a definition. |
| Return calculation / probability | `POLICY_DEFINITION_MISSING`; calibration need `UNRESOLVED` | No payoff, probability, forecast, structural-return, or outcome-statistics method is approved. |
| Friction scenario | `PRODUCER_NOT_IMPLEMENTED` after policy definition | The formula exists, but scenario source inputs, tax/broker/slippage treatment, known-at, and authority are absent. |
| Fixed statutory rates | `READY` | They are insufficient to produce total switching friction. |

The exact one next continuation is **`GATE1_ROTATION_POLICY_DEFINITION_REPAIR_V1`**. It must decide, without altering the current active Gate 1 runtime:

1. the comparator and allowed action scope;
2. the exact return meaning, compatible unit, and holding horizon;
3. whether probability is required and, if so, its approved deterministic source;
4. immutable candidate/incumbent-or-cash scenario identity, as-of, known-at, fingerprints, and conflict handling;
5. which turnover, brokerage, slippage, tax, and GST inputs are allowed, required, or excluded;
6. whether calibration is mandatory before a future producer and what a bounded 25–30 user-controlled pilot may claim.

It must not choose those answers implicitly, alter `1.00` or `0.00`, turn a score into a forecast, add broker-specific costs, construct an AI predictor, duplicate the rotation engine, activate V2, or create orders.

## 8. Preserved invariants

```text
V1_ACTIVE = TRUE
GATE_POLICY_V2_ACTIVE = FALSE
SIX_GATES_EXACTLY_SIX = TRUE
NO_FABRICATED_ECONOMIC_RETURN = TRUE
NO_FABRICATED_SWITCHING_FRICTION = TRUE
NO_FUTURE_LEAKAGE = TRUE
PILOT_SIMPLICITY_RULE = ACTIVE
AI_DECISION_AUTHORITY = FALSE
```
