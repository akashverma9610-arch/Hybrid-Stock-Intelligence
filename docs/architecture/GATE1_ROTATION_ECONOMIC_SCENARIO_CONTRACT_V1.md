# Gate-1 Rotation Economic Scenario Contract V1

Status: `CONTRACT_SPECIFIED / GOVERNANCE_AND_TESTS_ONLY / NOT_ACTIVE`

Decision **A** means **contract defined and validated with activation blockers**,
not an operational economic model, approved return forecast or Gate-1 clearance.
Baseline: `main` at `53cf15e1e299aa8ba89ca8380acf042dad71f79b`.
Contract: `gate1-rotation-economic-scenario / v1`.
Authority: the bounded user directive `GATE1_ROTATION_ECONOMIC_SCENARIO_CONTRACT_V1`;
no human signature or production registration is manufactured.

The [machine contract](GATE1_ROTATION_ECONOMIC_SCENARIO_CONTRACT_V1.json) is a
closed, versioned **record-shape and invariant specification**, not JSON Schema
and not a runtime loader. The [conformance witnesses](../../tests/unit/test_gate1_rotation_economic_scenario_contract.py)
use synthetic, independently supplied test authority only. They are not a
production validator, producer, source registry or authorization path.

## 1. Authority and unchanged boundaries

This document refines the [immutable V2.4 proposal](GATE1_ROTATION_POLICY_V2_PROPOSAL.md)
under its [separate conditional composite approval](EXECUTION_GATE_POLICY_V2_COMPOSITE_GOVERNANCE_APPROVAL_2.md).
Neither historical artifact is edited or re-fingerprinted.

| Binding | Exact value |
| --- | --- |
| Active policy | `six-gates-production-v1 / v1` |
| Proposed single successor | `execution-gate-policy-v2-proposed / v2-proposal.4`, `NOT_ACTIVE` |
| Proposal fingerprint | `sha256:0be5819937f85910700b672c7238d6cc01efa4777d8dac3518606837e2454769` |
| Approval fingerprint | `sha256:4e93795ab75b9eac7dc05aca853e63008252765ca21a5d30b5dc160c54334c9e` |
| This contract fingerprint | `sha256:b4f5c83f33c44c889218823041800d80507733b1932b89529c5aed26ea8c6e14` |
| Operational blockers closed | **Zero**; contract-definition subproofs only |
| Registered scenario/slippage/tax producers | None added; required economic producers remain `NOT_READY` |

Gate-1 concerns `ROTATE_IN` only. It compares the exact selected incumbent
continuation with the candidate rotation, on the same capital, cutoff, horizon
and INR basis. The following hurdles remain independent:

- `raw_decision_score - comparison_score >= 1.00` score points, using the existing
  canonical candidate/incumbent comparison binding; no new score calculation.
- `incremental_net_advantage_inr > 0.00`; equality is not sufficient.

This contract grants no trade authority. It changes no Gate-1 V1 behavior,
Gate 2/3/4/5/6, Decision Score, TradePlan, registration, selection or source
adapter. No portfolio access, SQL, persistence, live provider call, order or
broker action occurs in this slice. Existing Six Gates remain evidence-only.

## 2. Repository reconciliation and conflicts

| Existing canonical component | Reuse and explicit limitation |
| --- | --- |
| [Instrument](../../app/domain/models.py) | Resolve the existing exact `Instrument.id`; an ISIN-looking string or symbol is not authority. No fuzzy mapping or second instrument registry. |
| [Portfolio models](../../app/portfolio/models.py) | Bind snapshot, portfolio, holding and selected quantity to existing immutable evidence. This is not a new portfolio object or current-position lookup. |
| [Portfolio ledger engine](../../app/portfolio/engine.py) | Existing effective/known-at transaction cutoff and corporate-action evidence are reusable. `weighted-average-cost-v1` is accounting, **not statutory tax-lot selection**. An average-cost price fallback is not an eligible market reference price for this contract. |
| [Rotation pair/context](../../app/rotation/models.py) | Existing pair and snapshot references are reusable. Caller-supplied `expected_incremental_benefit` and friction scalars are not V2 economic authority. No NAV or full-position substitution. |
| [Rotation comparison engine](../../app/rotation/engine.py) | Final challenger comparison consumes gate context. Its eventual clearance cannot feed back into upstream scenario authority. |
| [V1 production friction policy](../../app/gates/production_policy.py) | Preserve existing effective-dated rates and arithmetic. Their existence does not certify fresh, applicable account/tax/slippage inputs for V2. No rates are copied into this contract as current verified rates. |
| [Gate source authority](../../app/gates/source_authority.py) | Reuse the independently configured verification boundary in a later adapter. Present neutral economic sources remain unready. A role string or self-hash is not authority. |
| [Gate version/PIT envelope](../../app/gates/version_compatibility.py) | Reuse UTC, exact content binding and pre-formula rejection patterns. Its current closed GateInput envelope is **not** extended; new records cannot be smuggled through old scalar aliases. |
| [Governance repository](../../app/storage/sqlite_governance_repository.py) | Reuse immutable exact reads conceptually. The existing V1 effective-time/approval-ID selection tie-break is not proof that a new model's conflicting approvals are unambiguous. No persistence extension here. |
| [Fundamental V2 B09](FUNDAMENTAL_DIAGNOSTIC_REGISTRY_V2_GOVERNANCE_APPROVAL.json) | Conditional fundamental horizon/applicability dependency, not a numeric rotation horizon. |
| [Horizon/timeframe candidate](RULE_HORIZON_TIMEFRAME_APPLICABILITY_POLICY_V1_CANDIDATE.json) | Candidate intent labels are not an active duration policy. Duration remains unset. No TradePlan or Gate-6 time window fallback. |
| [Dhan live state](../../app/market_data/dhan_live.py) | LTP and trade/receipt timestamps are observations, not guaranteed sale proceeds, order-book depth, fills or slippage. No live acquisition. |
| [Liquidity analysis](../../app/analysis/liquidity.py) | Its OHLC proxies are not observed order-book quantity and cannot silently become a hard-gate slippage model. |
| [Historical rotation adapter](../../app/backtest/rotation.py) | Reuse frozen source/version binding conventions, not caller economic assumptions or prior gate clearance as a scenario producer. No replay writes. |
| [Canonical serialization](../../app/fundamentals/diagnostic_comparability.py) | Reuse `canonical_json` and `content_fingerprint` after this contract's explicit normalization; no Core serializer change. |

No equivalent authoritative paired-outcome/selected-parcel contract was found.
These are reuse boundaries, not a claim that the missing model or adapter exists.
The machine artifact pins 38 existing source/governance files, including the
parent approval, to their LF-normalized baseline content.

## 3. Closed record and provenance contract

Every key in `wire_contract.shapes` is required. A `?` permits explicit JSON
`null`, meaning unavailable, **not** an omitted key or default. Arrays are JSON
arrays with immutable canonical interpretation. Unknown fields, floats, NaN,
infinities, naive datetimes, malformed fingerprints and blank IDs are rejected.
IDs use nonempty ASCII `[A-Za-z0-9._:/-]+`; syntax never substitutes for exact
canonical resolution. Decimal amounts/quantities are exact finite decimal
strings; no scientific notation or float coercion. Other scalar words in the
machine shapes are exact literals. Assessment vocabulary is additionally closed
by `failure_contract`, not free text.

| Record | Required content and unavailable treatment |
| --- | --- |
| `Scenario` | Identity/content fingerprint; contract version/fingerprint; exact composite proposal/approval fingerprints; `ROTATE_IN`; `decision_as_of`; `INR`; canonical candidate/incumbent/portfolio IDs; parcel; nullable horizon; policy references; nullable paired endpoints; friction, tax lots, tax-context and slippage manifests; nullable producer reference; score binding; complete evidence manifest. |
| `EvidenceRef` | `id`, `version`, `fingerprint`, `as_of`, `known_at`, `role`. Resolve full payload independently; role is not authorization. All reference edges must resolve to the exact required input closure, with no unrelated evidence added to identity. |
| `Parcel` | Snapshot/holding IDs; selected and held quantities; both reference prices; nullable candidate quantity, purchase turnover and residual; switched capital; nullable cash contribution; price evidence IDs; `actual_realized_proceeds_inr` fixed `null`. |
| `Horizon` | Policy reference, start, endpoint, calendar reference and precision reference. A missing/unapproved duration produces no invented endpoint. |
| `Endpoint` | Exact leg instrument, common parcel/horizon fingerprints, paired-model reference, nonnegative terminal gross INR value, upstream input-manifest evidence ID and `COST_EXCLUSIVE`. |
| `Policies` | Nullable references for composite, paired model, funding, cost, tax, slippage, quantity, precision and freshness. Every required policy must be available before a conformant result. |
| `ScoreBinding` | Exact candidate score and incumbent comparison evidence IDs. No score-to-INR conversion; no score value is created here. |
| `Cost` | Exact component, nullable nonnegative INR amount, source evidence IDs, policy reference. Zero requires verified evidence; missing is not zero. |
| `TaxLot` | Canonical acquisition and cost-basis evidence IDs, exact positive selected quantity; the lot manifest must sum to the selected parcel. |
| `SlippageLeg` | Exact instrument, side, quantity, reference price, nullable INR amount, output/input evidence references, market-state IDs, policy and producer references; confidence fixed `null / UNAVAILABLE`. |
| `Assessment` | State, stable reason codes, nullable derived gross/net INR values, economic predicate, `execution_authority=false`. Never an order, portfolio instruction or gate-clearance token. |

IDs in policy/producer/reference fields bind the corresponding `EvidenceRef`
version and fingerprint. The independent canonical payload must prove approval,
selection, applicability, effective interval, source role and producer version.
Visible approval and effective start must be `<= decision_as_of`; any expiry,
revocation or conflicting effective selection must also be respected. Unknown
validity is not infinite validity. No implicit latest-now or arbitrary ID
tie-break is permitted. Identical selected records are idempotent; conflicting
selected provenance fails closed.

## 4. Deterministic identity, immutability and replay

Normalize aware timestamps to UTC instants. Normalize decimal **lexemes** by
removing insignificant fractional zeros and representing negative zero as `0`;
this does not round amounts or approve a monetary precision policy. Verify
duplicates/conflicts before sorting evidence by `(role, id, version)`, costs by
component, lots by acquisition ID, slippage by `(side, instrument_id)` and
set-valued reference lists lexically. Identical evidence receipts may collapse
idempotently; duplicate cost/lot/leg keys or conflicting evidence must not vanish.

Let `B` be all normalized Scenario fields except `scenario_id` and
`content_fingerprint`. Let `I` be `B` without `candidate_endpoint` and
`incumbent_endpoint`.

```text
scenario_id = "gate1-rotation-scenario:" + SHA256(canonical_json({
    "version": "rotation-scenario-identity/v1", "inputs": I
}))
content_fingerprint = "sha256:" + SHA256(canonical_json(B))
```

SHA256 denotes lowercase hex of UTF-8 bytes. Endpoint `evidence_id` points to
an `ENDPOINT_INPUT` manifest: canonical model/source **inputs**, not the endpoint
output or the scenario's own ID/fingerprint. Its evidence ID/version/fingerprint
remains in `I`. This breaks circularity: paired output values are covered by
content integrity but do not redefine the same logical input identity. All
endpoint fields remain covered by `B`. A different endpoint with identical
inputs is conflicting output, not a replacement. Rehashing cannot repair it:
independent authority must reproduce the original model output. No hash alone
confers authority.

The artifact's own fingerprint uses repository canonical JSON over every field
except `contract_fingerprint`. Stable serialization contains all replay inputs;
there are no current-time, environment or locale-dependent inputs.

Every source payload must have `as_of <= decision_as_of` and
`known_at <= decision_as_of`. Exact requested versions are pinned before
comparison, with future pool records filtered before conflict assessment.
Different versions are not an automatic conflict or a license to substitute the
newest version. Different visible payloads for the same pinned ID/version are a
conflict. A required future reference is insufficient; an unused future pool
record is excluded without changing a historical result. The future *modeled*
endpoint date is allowed, but observed prices/releases from that future date are
not. Later financial releases, holdings, cost/tax policies or scenario revisions
cannot replace earlier evidence. Replay requires original immutable payloads,
not hashes without recoverable evidence. No storage implementation is added.

## 5. Selected capital, funding and horizon

Let `q` be selected incumbent quantity and `p` its admitted reference price:

```text
0 < q <= held_quantity
C = q * p > 0 INR
candidate_purchase_turnover = candidate_quantity * candidate_reference_price
candidate_purchase_turnover + residual_capital = C
```

Both endpoints bind the same normalized parcel and horizon fingerprints. A
partial selection is explicit; selecting the full holding is valid only when
explicitly requested. `C` is **reference gross proceeds before friction**, not
actual or guaranteed realizable proceeds. Actual proceeds remain unavailable;
no fill, settlement or future sale is invented. Acquisition accounting cost is
not substituted for a missing current reference price.

This same-`C` contract authorizes no additional invested cash. A positive cash
contribution is unsupported; explicit zero means no invested top-up, not that
fees are funded. Unknown cash contribution remains unavailable. No unrelated
cash balance, portfolio NAV or full-position fallback is allowed.

Funding, residual treatment and quantity/rounding policies remain `POLICY_UNSET`.
A later independently approved funding proof must show how friction is financed
without free capital or counting a reduced deployment and the same cost twice.
Both instruments require their exact governed quantity quanta; no fractional
share invention, universal lot-size assumption or automatic rounding. Residual
is nonnegative and conserved but earns no invented return. Nonzero residual
requires the same still-unset governed treatment. Missing proof blocks admission,
even when the arithmetic balances. Partial costs/taxes are recomputed for exact
legs/lots, not prorated from a full-position cost estimate.

No active numeric comparison horizon was found. The contract references a
future explicitly registered **comparison-horizon policy**, with exact ID,
version, fingerprint, calendar, start at the decision cutoff, later endpoint,
endpoint convention, precision and applicability to both legs. B09 additionally
constrains fundamental V2 horizon compatibility when such evidence is consumed;
it supplies no numeric holding period. The existing horizon candidate cannot
silently be activated. Horizon is frozen at the cutoff, cannot be relabelled
later, and remains `POLICY_UNSET` until authorized.

## 6. Common INR endpoint and independent comparator

Let `Vc` and `Vi` be deterministic, cost-exclusive, same-horizon gross marked
values of candidate deployment plus governed residual, and exact incumbent
continuation, respectively. Both start from `C`:

```text
candidate modeled marked capital change = Vc - C
incumbent modeled marked capital change = Vi - C
G = (Vc - C) - (Vi - C) = Vc - Vi
F = execution_switching_cost_inr + tax_realization_impact_inr
N = G - F
economic predicate satisfied iff N > 0 INR
```

The two capital-change expressions explain dimensional equivalence; they are
not duplicate caller-authoritative input fields, realized profits or tax P&L.
This is nominal undiscounted common-horizon marked wealth, not terminal
liquidation, a percentage spread, a probability-weighted expected return, a
target price or a performance claim. No terminal sale/cost or second opportunity
penalty is assumed. Scenario methodology, treatment of intervening cash flows,
corporate actions and comparable endpoint normalization must be approved in the
paired model; none is guessed here. If not reproducible, the endpoint is absent.
No model or currency-rounding convention is selected by this contract.

## 7. Independent model authority

A later adapter must extend the **existing independently configured
GateSourceAuthority boundary**, not establish a parallel authority via JSON.
It must verify exact producer/model registration and historical applicability,
resolve canonical full source payloads, reproduce both endpoints, and bind the
score pair, parcel, horizon, prices, component bases/rates, funding, tax and
slippage. Required source roles and closure must match, not just IDs/hashes.
The producer cannot use final challenger clearance, Gate-4 PASS, TradePlan or
another downstream gate as its own source proof.

`DETERMINISTIC_HSI_DERIVED_SCENARIO` is a conceptual producer class, not a
registered instance. An AI, analyst or user cannot establish authority by
submitting that string, a terminal value or a self-generated hash. AI may provide
upstream evidence subject to existing governance, not the authoritative result.
No producer is registered and no silent fallback exists. Actual model authority
therefore remains `NOT_READY` even for structurally valid records.

## 8. Friction, tax and slippage

The exact disjoint top-level component set is inherited from the approved path:
`purchase_statutory_costs`, `sale_statutory_costs`,
`nse_member_transaction_charge`, `brokerage`, `gst`, `slippage`,
`capital_gains_tax`. All are mandatory nonnegative INR amounts; verified
not-applicable/zero treatment requires evidence, never a missing-to-zero default.

The first six form execution switching cost; `capital_gains_tax` is the separate
T1 tax-realization impact. Every component must carry applicable historically
known rate/schedule/policy versions, exact side/quantity/turnover, source payloads,
taxable base, GST inclusion/exclusion and rounding proof. Constituent statutory
charges must be disjoint from explicit exchange/GST components. No extra spread,
impact penalty, terminal liquidation cost or ungoverned cost key is accepted.
Each component is deducted **once**; endpoints must exclude these costs. No
current rates, brokerage tariff, default zero or tax percentage is defined here.

**Tax:** T1 remains mandatory and `POLICY_UNSET`. It is transaction-specific to
the selected incumbent disposal, not the whole holding, accounting P&L or all
portfolio gains. Required proof includes canonical acquisition transactions and
corporate actions, exact selected tax-lot quantities summing to `q`, acquisition
dates, cost basis, jurisdiction/entity/account and verified relevant tax facts,
plus a historically effective and known tax calculation/lot-selection policy.
No weighted-average-to-tax shortcut, assumed FIFO, rate, loss-credit/netting or
zero-tax classification is approved. Missing classification/policy/input blocks
the calculation. Existing completed transactions are not evidence that this
prospective disposal has occurred. No taxpayer details are collected here.

**Slippage:** two exact legs, `INCUMBENT_DISPOSAL` and
`CANDIDATE_ACQUISITION`, each bind instrument, quantity, reference price/value,
common cutoff, producer/policy ID/version/fingerprint and model-declared canonical
PIT liquidity/market-state inputs. Their nonnegative INR adverse-cost amounts
must sum to the **one** `slippage` component. They are modeled costs, not fills.
Confidence stays `null / UNAVAILABLE`; no probability threshold is invented or
borrowed from Gate 6. Missing policy/producer/input/amount blocks. LTP or an OHLC
proxy does not prove execution impact; no zero default or duplicate spread cost.

## 9. Failure and result contract

| Code | Required fail-closed meaning |
| --- | --- |
| `HORIZON_UNAVAILABLE` | Missing, ambiguous, incompatible or unapproved common horizon; no numeric fallback. |
| `SCENARIO_AUTHORITY_UNAVAILABLE` | Missing/unregistered/unverifiable independent producer; self-assertion cannot authorize. |
| `CANDIDATE_SCENARIO_UNAVAILABLE` | Candidate endpoint cannot be admitted/reproduced. |
| `INCUMBENT_SCENARIO_UNAVAILABLE` | Exact incumbent continuation cannot be admitted/reproduced. |
| `TAX_POLICY_UNAVAILABLE` | Missing approved tax calculation/selection policy. |
| `TAX_INPUT_UNAVAILABLE` | Missing/non-comparable lot, classification, tax context or amount. |
| `SLIPPAGE_UNAVAILABLE` | Missing model, either leg, required input or amount. |
| `COST_EVIDENCE_UNAVAILABLE` | Missing component, applicable rate/base/rounding or amount proof. |
| `FUNDING_POLICY_UNSET` | Missing governed funding, quantity allocation/residual proof or known contribution. |
| `POLICY_UNAVAILABLE` | Missing/inactive/expired/unapproved/unknown-applicability required policy. |
| `STALE_EVIDENCE` | Fails its approved freshness rule; no new maximum age is invented. |
| `EVIDENCE_CONFLICTED` | Conflicting selected provenance or duplicate/conflicting leg, lot or cost keys. |
| `INVALID_UNIT` | Non-INR/percentage mixing; no implicit conversion. |
| `INVALID_PARCEL` | Invalid quantity/capital/price, conservation or exact pair/parcel binding. |
| `FUTURE_EVIDENCE` | Required source/approval/effectiveness is after cutoff. |
| `UNSUPPORTED_STATE` | Unsupported instrument/context/funding state or unresolvable identity. |
| `LINEAGE_UNVERIFIED` | Full canonical payload, exact role/reference or independently reproduced result cannot be verified. |
| `FINGERPRINT_MISMATCH` | Tampering; reject without repair. |
| `COST_DOUBLE_COUNT` | Component/leg aggregate mismatch or reused deduction; no recalculation into guessed validity. |
| `POLICY_VERSION_MISMATCH` | Incorrect contract/composite/model policy pin. |
| `INVALID_WIRE_SHAPE` | Closed shape/type/literal/format violation; reject. |

Assessment states are `CONTRACT_CONFORMANT`, `INSUFFICIENT_DATA`, `REJECTED`.
Predicates are `NOT_EVALUATED`, `POSITIVE`, `NON_POSITIVE`. A conformant
synthetic witness has derived gross/net values, no reason codes and one evaluated
predicate. Unavailable/rejected evidence has null derived values,
`NOT_EVALUATED`, and stable reason codes; never neutral friction or guessed return.
Shape/tamper violations are rejected. Other invalid/missing sources are
insufficient or subject to the existing pre-formula rejection boundary, never
PASS. The reference witnesses report the first failed validation stage, not an
exhaustive explanation of every simultaneous defect; reported codes are unique
and deterministic. No malformed economic evidence implies that the company failed
an investment rule.

Parent gate precedence is unchanged: verify effective composite/score policy;
reject populated unverified source before formula; non-ROTATE_IN is not
applicable; missing score is insufficient; score advantage below one fails;
missing/invalid required economic scenario is insufficient; admitted `N <= 0`
fails; otherwise the economic hurdle can pass. `CONTRACT_CONFORMANT` or
`POSITIVE` is **not** Six-Gates clearance. All six gates and downstream governed
boundaries remain independent. Every assessment has `execution_authority=false`.

## 10. Validation and activation ledger

Synthetic witnesses use `C=1000`, selected quantity `10` of held `20`, reference
price `100`, candidate deployment `1000`, residual `0`, incumbent endpoint `1080`,
candidate endpoints `1091/1090/1089`, and total friction `10` INR. Therefore net
advantage is `1/0/-1` respectively. These are arithmetic test values, **not**
market assumptions, rates, estimates or an approved numeric horizon. Test-only
policies and authority are passed independently; the normal absent-authority
case always remains insufficient. Existing six-gate reducer witnesses test
strict-zero and independent score hurdles, not live execution authority.

Tests cover shape/type closure, partial/full-explicit selection, capital/unit
conservation, separate instrument quanta, missing horizon/model/funding/tax/cost/
slippage, no zero default, once-only deduction, future exclusion, exact-version
replay, visible conflicts, duplicate policy/evidence receipts, full lineage,
rehash attacks, identity/content separation, UTC/decimal/order normalization,
frozen governance fingerprints and unchanged V1/all-gates behavior. Relevant
existing authority, governance, rotation, portfolio and horizon tests are run.
No shared/runtime behavior changes, so no full backend run is required by this
slice. Local link/table/whitespace checks and `git diff --check` are also required.

Completed validation: **102 focused tests passed**; **582 relevant tests passed,
2 existing dependency deprecation warnings**. No failures or skipped tests in
these runs. Edited Markdown validation checked 296 local links and five tables.
This is not a claim that a new full-backend run or production canary occurred.

| Parent blocker | This slice specifies | Still required before operational closure |
| --- | --- | --- |
| `CV24B20` | Paired scenario identity, units, endpoints and fail-closed contract | Model methodology, exact reproducible producers and independent source authority |
| `CV24B21` | Same-cutoff/same-horizon interface and B09 reconciliation | Approved numeric horizon/calendar/applicability and any applicable B09 closure |
| `CV24B22` | Selected parcel, partial selection, reference capital and conservation | Quantity, funding, fee financing and residual policy/proof |
| `CV24B23/24` | Required candidate/incumbent producer interface | Both real governed producers remain unready |
| `CV24B25/26/27/28` | Disjoint cost, T1 tax, both slippage legs and PIT lineage | Verified schedules/rates/bases/rounding, tax-lot selection/calculation, slippage model and producers |
| Other inherited blockers | Unchanged | Adapters/downstream compatibility, required shadow evidence, registration/selection and explicit activation; unrelated surveillance/calendar blockers also unchanged |

No parent blocker is silently marked closed, and no historic approval is changed.
Schema syntax and test authority do not supply missing economics. V1 remains
active; V2 remains `NOT_ACTIVE`.

## 11. Exactly one recommended continuation

**`GATE1_ROTATION_SCENARIO_MODEL_SOURCE_FEASIBILITY_V1`**: determine which
reproducible paired endpoint methodology and canonical source evidence can
satisfy this contract, explicitly retaining unready horizon, funding, cost, tax
and slippage dependencies. No return model, numeric horizon or rate is preselected
by this recommendation. This continuation is **not started** here.
