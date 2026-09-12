# Earnings Blackout Policy V2 Proposal

Status: `PROPOSED / NOT_ACTIVE / DOCUMENTATION_ONLY`.

Candidate: `execution-gate-policy-v2-proposed / v2-proposal.1`.
Parent authority: `six-gates-production-v1 / v1`.
Audited baseline: `faa4394b3f4b77a538133a5de4f75f7d135d9e1e`.

This is the successor **proposal**, not approval, a registered policy, a shadow
runtime, or an active evaluator. It records the accepted
`VERIFIED_HARD_BLOCK_PLUS_SOFT_RISK_CONTEXT_RECOMMENDED` finding in the
[horizon research](EARNINGS_BLACKOUT_HORIZON_POLICY_RESEARCH_V1.md). That research
traces five sessions to a strategy assumption, not a calibrated optimum or a
regulatory guarantee. Its effective-dated regulatory/source findings remain the
authority for this proposal; a current notice requirement is not historical
knowledge and does not establish an earlier earnings date.

The [machine-readable proposal](EARNINGS_BLACKOUT_POLICY_V2_PROPOSAL.json) is
normative together with this document. Neither overrides active V1. Any conflict
between them blocks approval; neither is permission to implement around the other.

## Frozen state and versioning

| Boundary | State retained |
| --- | --- |
| Core/execution V1 | `V1_ACTIVE = TRUE` |
| Proposed execution policy | `GATE_POLICY_V2_ACTIVE = FALSE` |
| Fundamental diagnostic V2 | `V2_DIAGNOSTIC_ACTIVE = FALSE`; `V2_SHADOW_ONLY = TRUE` |
| B08 | `CLOSED_FOR_ACTIVATION_COMPATIBILITY`; not reopened |
| Exact identity / prospective first-observed PIT contracts | `READY`; contract readiness is not active source admission |
| Six Gates | Exactly six; no Gate 7 or parallel engine |
| Negative clearance / predicted dates / AI authority | No unverified clearance, no AI-predicted date, no AI decision authority |
| Pilot | `PILOT_SIMPLICITY_RULE = ACTIVE`; uncertainty cannot be hidden for usability |

Policy lifecycle vocabulary is `PROPOSED`, `GOVERNANCE_APPROVED`, `SHADOW`,
`ACTIVE`, `RETIRED`. Only `PROPOSED` is created here. Each later transition
requires its own governance evidence; approval of this proposal does not activate
the horizon, source, adapter, or soft context. Execution-policy version is separate
from diagnostic-registry version; a proposed Gate-policy V2 cannot authorize
fundamental diagnostic V2. Existing version-rejection guards remain intact.

The exact runtime IDs, in existing order, are:

1. `GATE_1_ROTATION`
2. `GATE_2_VELOCITY`
3. `GATE_3_SURVEILLANCE`
4. `GATE_4_TRADE_PLAN`
5. `GATE_5_HEAT`
6. `GATE_6_EARNINGS`

These map one-to-one to numeric registry IDs 1–6. The artifact pins each Gate 1–5
definition and implementation fingerprint, plus complete V1 registry, engine,
production-policy, source-authority, and version-compatibility files. Gate 1–5
thresholds, order, arithmetic, authority, and outcomes are unchanged. V1 Gate 6
and its five-session configuration are also pinned, not patched.

## Exact V1 → proposed V2 difference

| Aspect | Existing V1 (retained) | Proposed V2 only |
| --- | --- | --- |
| Name | Five-Trading-Day Pre-Earnings Blackout | Verified Earnings Event Risk Window |
| Purpose | Prevent fresh entries immediately before scheduled earnings. | Prevent fresh-entry authorization when verified, PIT-valid imminent scheduled results carry binary gap/repricing risk inside an approved execution-risk window. |
| Positive block | After authority admission, `_blackout` fails when scheduled time is at/after as-of and existing calendar distance is at most configured five sessions. | `BLOCKED` only when all verified-event predicates below and approved window membership hold. Never inherit five. |
| Schedule inputs | `earnings_scheduled_at` and `earnings_schedule_verified_at` scalar datetimes; separate source-authority boundary. | Exact identity, qualifying official purpose, versioned event/payload lineage, HSI-local first observation, effective lifecycle, and governed relevant coverage/freshness. |
| PIT | Missing/future verification is insufficient; upstream authority/lineage checks also apply. | Each positive fact and lifecycle revision is visible only at its own verified HSI-local known-at; source-public time retained separately. |
| Absence | Missing scalar schedule/verification is `INSUFFICIENT_DATA`; official source contract has `absence_is_pass=False`. | `UNKNOWN`; never infer `CLEAR` from no row. |
| Outside window / passed date | Admitted scalar path returns `PASS` outside configured blackout, including a past scheduled time. This is not a claim that current source admission is ready. | Removing a particular positive block does not prove no other event. Without separately approved negative clearance, fresh-entry result is `UNKNOWN / CLEAR_UNSUPPORTED`. |
| Horizon | Human-approved `blackout_sessions=5`; historical V1 unchanged. | `EVENT_RISK_HORIZON=POLICY_UNSET`; value/unit/boundary interpretation absent; calibration and approval required. |
| Revision/cancellation | `_blackout` has no lifecycle field; repository schedule selection handles lineage separately. | Future adapter composes known-at and lifecycle before evaluation; revision/cancellation affects only its own visible linked event from its own known-at. |
| Existing holdings | Four management action contexts are exempt from this gate. | Same scope exemption; no liquidation rule, no market-wide `CLEAR`, no all-gates pass. |

## Candidate hard-block contract

This is a declarative policy, not an implemented decision function. In an approved
future version, **all** the following must hold for a scoped entry to be `BLOCKED`:

- Exact canonical instrument match through the existing identity bridge; no
  symbol-only, fuzzy, proxy, or predicted mapping.
- Qualifying financial-results schedule under approved official-source purpose
  semantics; generic board meetings and ambiguous agendas do not qualify.
- Trusted exchange-distributed official filing lineage, payload identity and
  version, with all existing integrity/authority verification retained. Current
  `UNVERIFIED_SOURCE_AUTHORITY` candidates are not automatically promoted.
- `HSI_LOCAL` prospective known-at verified by the existing automatic
  first-observed receipt and bound to this exact instrument/filing/payload.
  Every admitted dependency must satisfy `known_at <= evaluation_as_of`.
- Effective, conflict-free schedule/revision lineage at that local cutoff. No
  cancelled, superseded, unresolved, or completed event may provide this positive
  future-event block. Current/source-public state cannot replace historical state.
- Relevant source coverage and revision freshness meet an approved, effective
  contract. Partial, stale, failed, conflicting, or unproven coverage stays unknown.
  A complete historical archive for every company is not required to admit a
  particular adequately covered positive event.
- Exact horizon policy identity/version/fingerprint, approved and effective at
  the evaluation as-of, proves membership of the event in that risk window.
  Missing/ambiguous policy or unsupported timestamp precision is not membership.

Let `K` be the verified HSI-local known-at, `T` the decision as-of, and
`W(T,event,policy)` membership under a **future approved** risk-window policy.
The causal condition is `K <= T AND W(T,event,policy)`, in addition to every
admission predicate above. This introduces no duration, unit, opening/closing
boundary, event-completion delay, or calendar formula. `W` cannot currently be
computed: its policy is unset. No present V2 hard block is operational.

`APPROVED_VALUE`, `POLICY_UNSET`, and `CALIBRATION_REQUIRED` are horizon-state
vocabulary. Actual state is `POLICY_UNSET`, value `null`, calibration required.
Even a historically approved V1 five-session value is not a V2 approved value.
There is no separate bank/industrial horizon without evidence and approval.

### PIT composition and precision gap

Reuse [known-at semantics](EARNINGS_CALENDAR_KNOWN_AT_SEMANTICS_V1.md), not a second
clock. A candidate's current `known_at` is source-public dissemination, while
`HSI_LOCAL` uses a separately verified `SystemFirstObservedReceipt`. Do not mutate
the source-public timestamp, use caller-supplied retrieval time as observation,
or silently choose `max(source_time, local_time)` as a new temporal policy.

The future adapter must resolve the chosen perspective for each event/revision
**before** composing the lifecycle view. Calling a source-public `effective_schedule_as_of`
and then filtering only the surviving parent could hide an earlier event because
of a revision not yet seen by HSI. Preserve the older visible state until the
revision's own HSI-local known-at. Future evidence is excluded, not backfilled.

Candidates support `DATE_ONLY` and `DATE_TIME`; the current GateInput scalar
datetime does not express both. Do not convert a date-only board meeting to
midnight, exchange open, or presumed results release time. Horizon governance
must explicitly define accepted precision, session inclusion/exclusion and event
end semantics using the existing exchange calendar. Until then, unsupported
precision is `UNKNOWN`, not fabricated membership or clearance. A board-meeting
date is not automatically an actual earnings-publication timestamp.

## Output, scope, and causal truth table

Proposed presentation vocabulary is `BLOCKED / UNKNOWN / CLEAR`. Only the first
two are conditionally supportable; `clear_support_state=CLEAR_UNSUPPORTED`.
Reuse existing `GateOutcome`: `BLOCKED → FAIL`, `UNKNOWN → INSUFFICIENT_DATA`.
`FAIL` means a verified **entry-risk restriction**, not a bad stock. `UNKNOWN`
means unresolved evidence/policy; it is neither `PASS` nor `FAIL`. No new enum,
gate, or engine is implemented. Overall execution still composes all six gates.
Gate results remain eligibility **evidence**, not broker/order authority. This
proposal authorizes no automatic trade, portfolio mutation, or capital deployment.

| Condition for an entry-scoped evaluation | Proposed state | Existing GateOutcome mapping / explanation |
| --- | --- | --- |
| All evidence admitted, approved horizon and membership proven | `BLOCKED` | `FAIL`; no order/action generated |
| Event-risk horizon unset or approval unverifiable | `UNKNOWN` | `INSUFFICIENT_DATA`; applies to current candidate |
| Evidence not yet known at evaluation time | `UNKNOWN` | Future evidence excluded, not a retroactive block |
| No verified schedule, unknown known-at or ambiguous event purpose | `UNKNOWN` | No inferred earnings date |
| Incomplete/unproven coverage, stale coverage or source failure | `UNKNOWN` | No source absence clearance |
| Conflicting schedules, integrity failure or unresolved revision | `UNKNOWN` | Preserve evidence conflict and reason |
| Event outside approved window or already completed/past | `UNKNOWN` | Particular block absent; general clearance unsupported |
| Visible cancellation/supersession removes last positive event | `UNKNOWN` | Linked block removed; not global `CLEAR` |
| Management-scope exemption | Not a clearance determination | Existing `PASS` exemption only; other gates/policies still apply |

Entry scope retains exact existing `FRESH_ENTRY`, `ADD_TO_POSITION`, `ROTATE_IN`.
Management exemptions retain `HOLD_EXISTING`, `REDUCE_EXISTING`, `EXIT_EXISTING`,
`RISK_MANAGEMENT`. These are existing **input context identifiers**, not actions
issued by this proposal. A later tranche follows its existing action
classification; it is not automatically exempt just because a holding exists.

If a schedule is first observed at T−2, block only from that known-at (inclusive),
and only if the future approved window applies. A decision at T−5 through T−3
cannot be rewritten. A legitimate earlier entry remains historically legitimate.
Existing-position review/revalidation can occur only through already governed
policies; this proposal creates no sell, exit, sizing, or portfolio mutation.

A reschedule changes the positive event's membership only after its own known-at.
A cancellation removes only its linked block from its own known-at. Another
independently valid positive event may still block. Identical retained documents
reuse canonical identity; no second event/alert from repeated headlines.
Conflicting child revisions remain unknown, not last-input-wins. Append-only
lineage is preserved; no deletion, overwrite, or backward correction of decisions.

## Separate reporting-season context

`RESULTS_SEASON_RISK_CONTEXT` is a proposed, optional **non-gate** description of
broad effective-dated reporting windows, not a specific company's schedule.
Reuse existing research evidence and Shared Brain research/explanation channels;
there is no new diagnostic or Earnings Risk Brain. A display adapter and its
source interpretation still require separate approval; nothing is activated here.

Allowed purpose: research/UI explanation and qualitative confidence **context**.
Not allowed: gate pass/fail, score points, numerical confidence penalty, sizing,
target/stop, predicted date, entry/exit, BUY/SELL/HOLD, or trade authorization.
No runtime season inference, calendar query, calculation or UI is added.

## Research, pilot and historical replay

Market, technical, fundamental, sector, valuation and portfolio research continue
under their own evidence rules when Gate 6 is unknown. Research completion is
not `ENTRY_READY`. In a future 25–30-user research pilot: admitted positive event
plus approved effective window blocks a scoped entry; uncertainty withholds
entry readiness; neither creates a trade. With horizon unset, even otherwise
verified evidence cannot make this candidate operational. Do not bypass Gate 6
or reinterpret unknown as pass to make the pilot usable. The resulting
entry-readiness limitation is an explicit governance/usability decision.

Perfect historical schedule reconstruction is not a prerequisite for a
prospective research pilot. Trusted prospective collection, policy/source
admission, version rejection and prospective audit evidence are prerequisites
for any later Gate-policy activation. B14 remains open; no horizon optimization
or shadow collection is started here. B09 Rule × Horizon and investment horizons
(short-term/positional/long-term) are distinct from Gate-6 event-risk timing.

V1 evaluations, signals, paper and outcome records retain original V1 lineage.
Future V2 research replay must explicitly bind policy ID/version/fingerprint,
effective approval/source/regulatory version, as-of, temporal perspective,
first-observed and payload/revision lineage, horizon/calendar versions and action
scope. Missing or mismatched provenance rejects replay; never default to latest
policy or current calendar rows. No rewriting of V1 records. Complete historical
V2 outcome analysis can be deferred, but version isolation cannot.

## Calibration requirements, not new formulas

Each future record must bind canonical instrument/event/revision identity,
source-public time and HSI-local known-at separately, schedule precision,
actual event timing where verified, observation cutoff, policy/horizon/calendar,
and immutable market-evidence lineage. Predefine cohorts (including new listings,
irregular reporters and instrument types) and forward/out-of-sample splits.
Missing observations must remain missing, not zero or synthetic trades.

| Required observation | Required future definition/data; unresolved choice |
| --- | --- |
| Known-at → event distance | Verified observation and event times, precision and session calendar; approved distance units/boundaries |
| Overnight/open gap; absolute gap | Comparable prior close and next executable/open observation, corporate-action basis; no assumed execution |
| ATR-normalized gap | Same gap plus PIT ATR; approve lookback, adjustment and zero-denominator treatment |
| MFE/MAE around event; drawdown | Timestamped comparable series and predeclared windows/reference prices, no future data at decision time |
| Slippage | Actual shadow observation methodology and realistic liquidity; never treat a hypothetical fill as executed |
| Post-event volatility | Approved sampling/window/return and adjustment convention; no metric chosen here |
| Missed opportunity; false-block rate | Predeclared counterfactual eligibility, denominator and outcome windows; separate unknown deferrals from verified blocks |
| Schedule revision rate; known-late rate | All immutable revisions/cancellations, inclusion denominator and approved horizon for lateness; don't label T−2 inherently late under an unset V2 window |

No formulas/thresholds for these calibration metrics are approved here. Their
definition, data and collection plan precede optimization. No prospective or
historical performance claim is made. Sample sufficiency, event-end timing,
false-block acceptance and a numerical horizon need later human policy approval.

## Scoped dependency-impact audit

Classification is the **future integration change**, not permission to change
these files. Existing implementations are not being marked unavailable.

| Consumer | Classification | Existing owner/reference and precise impact |
| --- | --- | --- |
| Decision Score | `NO_CHANGE` | [score evidence](../../app/intelligence/decision_score_evidence.py): no score weights/points or uncertainty penalty |
| Brain | `ADAPTER_UPDATE_REQUIRED` | [output evaluation context](../../app/intelligence/output_evaluation_context.py), [research/application](../../app/intelligence/shared_brain_application.py): preserve gate-policy/as-of provenance and distinguish unknown; research remains independent |
| Portfolio | `POLICY_REVIEW_REQUIRED` | [canonical gates activation](../../app/portfolio/canonical_six_gates_activation.py): preserve entry/add versus management action classification; no holdings/cash writes or new exit rule |
| Signals | `ADAPTER_UPDATE_REQUIRED` | [signal models](../../app/signals/models.py), [orchestrator](../../app/signals/engine.py): current gate-status/blackout bool cannot by itself explain V2 unknown versus verified block; preserve non-executable analytical boundary |
| TradePlan | `NO_CHANGE` | Existing `TradePlan` in [signal models](../../app/signals/models.py) and `TradeManagementPlan` in [gates](../../app/gates/engine.py): entry/stop/targets/tranche policy and Gate 4 remain unchanged; eligibility consumes versioned gates outside price-plan construction |
| Entry-ready lifecycle | `POLICY_REVIEW_REQUIRED` | [output requirement policy](../../app/brain_output_requirement_policy.py) and signal revalidation: unknown cannot become required gate status/trigger eligibility; management exemption is not clearance |
| Alerts | `POLICY_REVIEW_REQUIRED` | Existing signal lifecycle events are the reuse point, not a dedicated earnings-alert authority. No such delivery adapter found in scoped audit; approve wording/dedup/routing before notifications, otherwise keep disabled |
| Outcome ledger | `CALIBRATION_REQUIRED` | [paper models](../../app/paper/models.py), [forward paper](../../app/forward_paper/models.py): retain V1 configuration IDs; prove V2 evidence/horizon linkage and predeclare calibration/counterfactual observations; no new ledger or fills |
| Backtest | `ADAPTER_UPDATE_REQUIRED` | [analytical replay](../../app/backtest/analytical.py): scalar schedule selection needs explicit version/perspective binding and historical source semantics; fail closed if missing |
| Six-Gates orchestration | `ADAPTER_UPDATE_REQUIRED` | [engine](../../app/gates/engine.py), [source authority](../../app/gates/source_authority.py), [version checks](../../app/gates/version_compatibility.py): one existing engine, approved future version selection and schedule admission, no V2 artifact loaded now |

## Activation blockers

`BLOCKING` prevents Gate-policy V2 activation. `NON_BLOCKING` is safe only with
the optional feature disabled. `DEFERRED_FOR_SHADOW` does not authorize that
feature or relax rejection. All blockers below remain unresolved as applicable.

| ID | Area | Class | Closure required |
| --- | --- | --- | --- |
| A1 | Event-risk horizon/policy/calibration | `BLOCKING` | B14 research/shadow evidence, exact timing/precision/window parameters and human approval; no inherited five |
| A2 | Schedule ingestion producer | `BLOCKING` | Trusted automatic first-observed receipts and admitted official qualifying schedules; pure source candidates alone insufficient |
| A3 | Source coverage/freshness | `BLOCKING` | Approved relevant source/window completeness and revision/freshness contract; today's coverage vocabulary alone is not proof |
| A4 | Gate-6 runtime adapter | `BLOCKING` | Compose exact identity, local known-at and lifecycle in correct order; approved source and horizon; reject tampering/ambiguous precision |
| A5 | Execution-state mapping | `BLOCKING` | Review unknown versus blocked, required gate status/entry-readiness and management exemption; no bypass |
| A6 | Alert behavior | `NON_BLOCKING` | Optional alerts remain disabled; any later activation requires wording, dedup, late-event and revision review |
| A7 | Outcome/calibration compatibility | `BLOCKING` | Bind policy/evidence/as-of and distinguish missed opportunities/unknowns; predeclare metrics before V2 shadow outcome claims |
| A8 | Historical replay version isolation | `BLOCKING` | Preserve V1 records; explicit V2 provenance and effective source/regulatory semantics, fail closed on missing history |
| A9 | Complete historical event archive/outcomes | `DEFERRED_FOR_SHADOW` | Not needed for prospective research pilot; no incomplete historical performance claim |
| A10 | Authoritative negative clearance | `DEFERRED_FOR_SHADOW` | `CLEAR_UNSUPPORTED` retained; later clearance needs distinct approved negative-evidence policy, never an absence shortcut |
| A11 | Optional results-season context | `NON_BLOCKING` | Remains disabled until evidence/presentation contract approved; never a gate or score |

The next approval may accept this **proposal and blockers**, not approve an
unset duration or runtime activation. Pilot research usefulness and absent fresh
entry clearance must both be stated truthfully.

## Deduplication and immutable artifact conventions

| Concern | Reuse, not a second source of truth |
| --- | --- |
| Schedule/event identity | [official candidate](../../app/gates/official_earnings_schedule_candidate.py), [canonical identity bridge](../../app/filings/earnings_schedule_identity.py), [schedule store lineage](../../app/filings/earnings_schedule_store.py) |
| Known-at | [existing resolution and first-observed receipt](../../app/filings/earnings_schedule_known_at.py); no new clock or backdating |
| Coverage/freshness | [coverage contract](../../app/filings/earnings_schedule_coverage.py), [governance](EARNINGS_CALENDAR_COVERAGE_WINDOW_POLICY_V1.md); do not fabricate COMPLETE/FRESH |
| Calendar | Existing `ExchangeCalendar` in [engine](../../app/gates/engine.py); no new calendar or changed trading-session arithmetic |
| Gate result / authority | Existing `GateOutcome`, decision/evaluation records, source authority and approved [production policy](../../app/gates/production_policy.py); candidate presentation mapping only |
| Evidence / soft explanation | Same canonical filing/payload and Shared Brain research evidence; no new event store, Earnings Risk Brain, diagnostic or AI authority |

This is a scoped reuse check, not a repository-wide dedup audit. No acquisition,
commercial calendar/TrueData evaluation or `DATA_BUILD_VS_BUY_AUDIT_V1` occurs.
No production DB inspection/mutation, source changes, provider calls, API/UI or
runtime wiring is needed for this proposal.

The JSON uses repository `canonical_json` / `content_fingerprint` conventions:
sorted object keys, explicit ordered arrays, UTF-8 canonical JSON, SHA-256 over
all fields **except** `proposal_fingerprint`. No generation time or environment
participates. Source file fingerprints normalize CRLF to LF for cross-platform
verification; definition fingerprints use canonical immutable dataclasses, method
fingerprints use exact LF-normalized AST source segments. This proves retained
definition/implementation text, not a newly synthesized production approval ID.

Test-only schema/semantic checks reject malformed structure and altered safety
values, verify reference hashes and deterministic round-trip, and check the
declarative scenario table. They **do not execute an unimplemented V2 gate**.
Existing V1 gate tests validate actual runtime behavior. No full backend suite
is required for this documentation/artifact/test-only change.

Exact next continuation, not started:
`EARNINGS_BLACKOUT_POLICY_V2_GOVERNANCE_APPROVAL`.
