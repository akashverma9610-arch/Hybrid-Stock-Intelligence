# Earnings Blackout Policy V2 Proposal

Status: `PROPOSED / NOT_ACTIVE / DOCUMENTATION_ONLY`.

Candidate: `execution-gate-policy-v2-proposed / v2-proposal.2`.
Parent authority: `six-gates-production-v1 / v1`.
Repair baseline: `3543c32cd0257dfacecc2498e904b7bc40d6b1d0`.
Supersedes proposal `.1` at that commit; its historical content remains in Git.
The unchanged V1 source pins originate at
`faa4394b3f4b77a538133a5de4f75f7d135d9e1e` and still match the repair baseline.

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

Final decision: **`B. VERIFIED_EVENT_VETO_GATE_RECOMMENDED`**.

This is a material, explicit proposed risk-acceptance change: lack of a verified
veto may cease to prohibit fresh-entry eligibility **without becoming clearance**.
It is not a silent bypass of V1 or proposal `.1`. Human approval, a calibrated
horizon and the activation prerequisites below are still required. No source
research is repeated and no gate runtime is changed in this repair.

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

## Actual runtime aggregation and the liveness defect

The audit reads [ExecutionGateEngine.evaluate](../../app/gates/engine.py), the
[production activator](../../app/portfolio/canonical_six_gates_activation.py),
[canonical record](../../app/portfolio/canonical_six_gates.py),
[universe consumer](../../app/universe_analysis/service.py), and
[signal lifecycle](../../app/signals/engine.py), not just policy documents.

| Runtime question | Actual current behavior |
| --- | --- |
| All gates must pass? | The engine emits exactly six decisions. Any `FAIL` yields `BLOCKED`; otherwise any `INSUFFICIENT_DATA` yields `INSUFFICIENT_DATA`; only six `PASS` results yield `EXECUTABLE`. |
| Does insufficient data inhibit entry eligibility? | Yes. It is not an abstention. A simultaneous `FAIL` takes precedence in aggregate status; both failed/insufficient ID lists remain recorded. |
| Can a gate abstain/not-veto? | There is no such `GateOutcome`. The enum is exactly `PASS`, `FAIL`, `INSUFFICIENT_DATA`. |
| `NOT_APPLICABLE`? | No separate gate outcome. Gate 1 non-rotation, Gate 2 no holding-management context, and Gate 6 existing-management exemptions express non-applicability as `PASS` with explanatory detail, after admission. |
| Is a veto-only mode implemented? | No. The existing reducer could compose its explicit versioned mapping into the same three outcomes, but a Gate-6-specific approved mode and evidence adapter do not yet exist. |
| Does a source failure automatically yield a gate result? | Not necessarily: source/version/score/domain admission precedes all formulas and can reject evaluation. Existing unavailable calendar authority must not be caught and converted to `PASS`. |
| Is `ENTRY_READY` the engine's return enum? | No: it returns analytical `ExecutionEligibility`. Universe opportunities require `EXECUTABLE`; signals require their configured gate status plus other conditions. `STRUCTURAL_ENTRY_READY` is a separate Pre-Breakout structural state, not six-gate authorization. Brain context matching proves lineage, not eligibility. |

The prior proposal maps `BLOCKED → FAIL`, `UNKNOWN → INSUFFICIENT_DATA` and has
no supported `CLEAR`. Hence the set of possible fresh-entry Gate-6 outcomes
contains no `PASS`. Even with Gates 1–5 all passing, **100% of fresh-entry
evaluations would be ineligible under that proposed state space**. This is a
logical deadlock, not an empirical estimate of source coverage or market entries.
It persists even after approving a horizon unless the model is repaired. Existing
management exemptions do not solve fresh-entry liveness.

## Clearance versus veto: policy choice

Clearance is positive proof that no blocking event exists in the governed scope.
A veto is positive proof of a qualifying blocking event. `NO_VETO_ESTABLISHED`
is only a statement about admitted evidence at the cutoff; neither a successful
query nor a failed/partial one establishes absence of real earnings risk.

| Model | Safety / residual risk | Source feasibility | Entries inhibited / usability / liveness |
| --- | --- | --- | --- |
| A — mandatory clearance | Avoids entry while earnings absence is unproven, but over-blocking/missed opportunities remain. | No approved complete negative-calendar proof exists in the accepted record. | All fresh entries structurally inhibited while `CLEAR` is unsupported; no live pilot entry path. No empirical percentage is claimed. |
| B — verified-event veto | Blocks proven event risk; explicitly accepts unobserved-event and source-gap exposure on a no-veto path. Not equally protective as Model A and never called safe. | Can use existing positive-event/coverage/known-at contracts once their producer and mode are admitted; does not require negative completeness. | At least one future path exists. Actual veto, unknown-admission and missed-event rates require shadow data; no forecast percentage. |

Recommend **B**, with source uncertainty separated from policy/admission failure.
It preserves a usable prospective research pilot without claiming complete
calendar certainty. Integrity conflicts and an unevaluable retained event still
fail closed; they are not converted into no veto. This is one veto-style Gate 6,
not a hybrid requiring negative clearance on another path or a seventh gate.

## Exact V1 → proposed V2 difference

| Aspect | Existing V1 (retained) | Proposed V2 only |
| --- | --- | --- |
| Name | Five-Trading-Day Pre-Earnings Blackout | Verified Earnings Event Veto |
| Purpose | Prevent fresh entries immediately before scheduled earnings. | Prevent fresh-entry authorization when verified, PIT-valid imminent scheduled results carry binary gap/repricing risk inside an approved execution-risk window. |
| Positive block | After authority admission, `_blackout` fails when scheduled time is at/after as-of and existing calendar distance is at most configured five sessions. | `VETO → FAIL` only when all verified-event predicates below and approved window membership hold. Never inherit five. |
| Schedule inputs | `earnings_scheduled_at` and `earnings_schedule_verified_at` scalar datetimes; separate source-authority boundary. | Exact identity, qualifying official purpose, versioned event/payload lineage, HSI-local first observation, effective lifecycle, and governed relevant coverage/freshness. |
| PIT | Missing/future verification is insufficient; upstream authority/lineage checks also apply. | Each positive fact and lifecycle revision is visible only at its own verified HSI-local known-at; source-public time retained separately. |
| Absence | Missing scalar schedule/verification is `INSUFFICIENT_DATA`; official source contract has `absence_is_pass=False`. | After approved mode/producer admission, `NO_VETO_ESTABLISHED → PASS` for composition, with `EARNINGS_CLEARANCE=UNVERIFIED` and source warnings. Absence is not clearance. This mapping is a new V2 policy, not V1 behavior. |
| Outside window / passed date | Admitted scalar path returns `PASS` outside configured blackout, including a past scheduled time. This is not a claim that current source admission is ready. | A deterministically non-blocking event may yield no veto if no other retained unresolved/proven blocking event exists; clearance remains unverified. |
| Horizon | Human-approved `blackout_sessions=5`; historical V1 unchanged. | `EVENT_RISK_HORIZON=POLICY_UNSET`; value/unit/boundary interpretation absent; calibration and approval required. |
| Revision/cancellation | `_blackout` has no lifecycle field; repository schedule selection handles lineage separately. | Future adapter composes known-at and lifecycle before evaluation; revision/cancellation affects only its own visible linked event from its own known-at. |
| Existing holdings | Four management action contexts are exempt from this gate. | Same scope exemption; no liquidation rule, no market-wide `CLEAR`, no all-gates pass. |

## Candidate hard-block contract

This is a declarative policy, not an implemented decision function. In an approved
future version, **all** the following must hold for a scoped entry to be `VETO`:

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
- The positive event's relevant lineage and revision freshness meet an approved,
  effective contract. Broad coverage may be partial without invalidating an
  independently admitted positive event. A subsequent query failure cannot erase
  a still-valid veto. If a retained event becomes stale/unevaluable, the result is
  `UNDETERMINED`, not no veto. Complete negative coverage is not required.
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
precision is `UNDETERMINED`, not fabricated membership or clearance. A board-meeting
date is not automatically an actual earnings-publication timestamp.

## Minimal separate source-state / gate-action contract

Do not replace the canonical source states with a parallel calendar enum. Retain
existing `CoverageState` (`COMPLETE / PARTIAL / FAILED / UNPROVEN / CONFLICTED`),
`EarningsScheduleFreshnessState` (`FRESH / STALE / UNPROVEN / SOURCE_FAILED`),
`EarningsScheduleAbsenceState`, event lifecycle and immutable evidence references.
These remain descriptions of available evidence, not execution conclusions.
Existing candidate/store `gate_eligible=False` and coverage
`gate6_clearance=False` guards remain unchanged. A future approved gate mode must
interpret admitted evidence; it cannot flip those guards into clearance proof.

The only new proposed interpretation is `gate6_evaluation_mode=VERIFIED_EVENT_VETO`
and the following mode-bound gate-action vocabulary. `execution_veto` is a
derived display value, not a second independently settable authority field.

| Proposed gate action | Derived execution veto | Existing GateOutcome | Earnings clearance |
| --- | --- | --- | --- |
| `VETO` | `TRUE` | `FAIL` | `UNVERIFIED` (positive risk proof is not negative clearance) |
| `NO_VETO_ESTABLISHED` | `FALSE` (no established veto only) | `PASS` for composition only | `UNVERIFIED` |
| `UNDETERMINED` | `UNDETERMINED` | `INSUFFICIENT_DATA` | `UNVERIFIED` |

The mode must be explicitly approved, effective at as-of and carried with policy
ID/version/fingerprint. A missing mode/horizon/adapter/trusted source-state
receipt is **not** the no-veto case. Current `.2` is still non-active with an
unset horizon: it cannot produce a live `PASS` or veto.

After those prerequisites, use the following ordered requirements:

1. Reject invalid request identity, policy/evidence integrity, source admission
   or temporal perspective. These produce no eligible evaluation; where a
   structured result can be represented safely, map to `UNDETERMINED`.
2. Compose only PIT-visible evidence. Exclude future events/revisions without
   exposing their future identities in historical warnings. A visible candidate
   with unverifiable known-at is an unresolved admission, not proof of no event.
3. An independent fully admitted in-window event establishes `VETO`. A source
   gap cannot clear it. Conflict in that event's own lineage disqualifies its
   positive proof; retain `UNDETERMINED` unless another independent event proves
   a veto. Never choose a conflicting revision by input order.
4. Without a proven veto, any retained possibly qualifying event with unresolved
   identity/purpose/known-at/lifecycle/precision/freshness remains `UNDETERMINED`.
5. Otherwise `NO_VETO_ESTABLISHED` is allowed, including an admitted observation
   of no event, partial/unproven coverage, stale coverage, or failed source query.
   This explicitly accepts source-gap risk; **it is not clearance**. A trusted
   configured producer must attest the actual query/coverage state. A disabled
   producer, missing receipt, swallowed exception or forged empty list cannot
   masquerade as an observed source failure or produce this path.

| Entry-scoped condition | Gate action / outcome | Required context |
| --- | --- | --- |
| Fully admitted event within approved window, including with unrelated coverage gaps | `VETO / FAIL` | Verified event lineage, window, scope and as-of |
| Global mode/horizon/producer receipt unavailable | `UNDETERMINED / INSUFFICIENT_DATA` | Policy/admission blocker; no current activation |
| Observed no verified event, no retained unresolved event | `NO_VETO_ESTABLISHED / PASS` | `EARNINGS_SCHEDULE_UNVERIFIED`, `EARNINGS_CLEARANCE_UNVERIFIED` |
| Observed partial/unproven/stale/failed coverage, no retained unresolved event | `NO_VETO_ESTABLISHED / PASS` | Same warnings plus exact source-state warning; accepted residual risk |
| Visible event has conflict, unknown known-at, ambiguous purpose, unsupported precision or stale lineage | `UNDETERMINED / INSUFFICIENT_DATA` | Preserve exact unresolved reason |
| Valid revision proves event non-blocking under the approved window, or cancelled; no other veto/unresolved event | `NO_VETO_ESTABLISHED / PASS` | Known-at revision lineage; clearance still unverified |
| Management-scope exemption | Existing `PASS` exemption | Scope exemption, not a market clearance or all-gates pass |

`UNKNOWN` remains an epistemic description of source/clearance, not the universal
Gate-6 action used in `.1`. It never becomes clear. `UNDETERMINED` admission still
blocks eligibility. Neither source gaps nor a verified veto make a stock bearish,
weak, low-score or bad-thesis. No numeric confidence penalty is introduced.

### Same engine, explicit mapping and truthful presentation

Keep the current aggregation rule and all six IDs: a future approved Gate-6 mode
may emit the table's three existing outcomes, while Gates 1–5 remain unchanged.
No generic rule to ignore `INSUFFICIENT_DATA`, no missing gate, and no second
engine is proposed. This mode is not present in current `ExecutionGateConfig`.

Reuse `GateDecisionRecord.parameters`, detail and evidence IDs for mode, veto
state, clearance and source receipt references; preserve these in the versioned
evaluation and its immutable fingerprint. Propagate source/clearance warnings
into evaluation warnings and downstream research/explanation views. Do not rely
on a consumer reading a bare `PASS`: the existing Brain projection drops some
per-decision parameters, so lossless interpretation needs an explicit adapter
review. Missing mode/clearance metadata must fail downstream compatibility checks.

The current `_decision` helper assigns confidence `1.0` to `PASS`. A future
no-veto adapter must **not** inherit that as earnings-certainty evidence: retain
`confidence=None` for this new no-veto result and distinguish mode in all consumers.
This helper and all V1 behavior remain unchanged now. No global PASS semantics
or Gate 1–5 confidence is being weakened.

Truthful no-event UX is: `Earnings Event: NOT VERIFIED`;
`Earnings Clearance: UNVERIFIED`; `Execution Veto: NO VERIFIED VETO`;
plus actual coverage/freshness warnings. For a verified but outside-window event,
show the actual verified event, not “not verified,” while retaining unverified
clearance. Prohibit `CLEAR`, `SAFE`, `NO EARNINGS SOON`, green safety assurances,
or suppression of source warnings. No UI is implemented.

A passed date or completed-status label alone cannot define an unapproved window
end. Non-blocking membership must be established under the future approved
horizon and timestamp-precision rules; otherwise retain `UNDETERMINED`. No
synthetic post-event expiry or calendar-passage shortcut is introduced.

**Future liveness witness:** approved/effective V2 mode and horizon, valid request
and trusted producer observation, no proven veto or retained unresolved event,
Gates 1–5 `PASS` → Gate 6 `NO_VETO_ESTABLISHED / PASS` → six-gate `EXECUTABLE`,
with `EARNINGS_CLEARANCE=UNVERIFIED` and warnings retained. All other setup/signal
requirements still apply. This proves a logically possible path, not a current
production path, positive calendar certainty or broker/order authority.

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
Conflicting child revisions remain `UNDETERMINED`, not last-input-wins. Append-only
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
under their own evidence rules regardless of earnings source uncertainty.
Research completion is not `ENTRY_READY`. In a future 25–30-user pilot, an
approved veto-style mode may allow entry eligibility without verified clearance
when its explicit no-veto conditions hold. This accepts unobserved-event risk,
which must remain visible, not treated as bearishness or numerical score damage.
Policy/admission failure and retained unresolved events still inhibit eligibility.
With horizon unset, no live V2 path is enabled. Approval of this material
source-risk acceptance is required; it is not an implicit bypass of a failed gate.

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
| Missed opportunity; false-block rate | Predeclared counterfactual eligibility, denominator and outcome windows; separate admission deferrals, verified vetoes, and no-veto entries with source warnings |
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
| Signals | `ADAPTER_UPDATE_REQUIRED` | [signal models](../../app/signals/models.py), [orchestrator](../../app/signals/engine.py): distinguish mode-bound no-veto pass from clearance and admission failure, retain source warnings; preserve non-executable analytical boundary |
| TradePlan | `NO_CHANGE` | Existing `TradePlan` in [signal models](../../app/signals/models.py) and `TradeManagementPlan` in [gates](../../app/gates/engine.py): entry/stop/targets/tranche policy and Gate 4 remain unchanged; eligibility consumes versioned gates outside price-plan construction |
| Entry-ready lifecycle | `POLICY_REVIEW_REQUIRED` | [output requirement policy](../../app/brain_output_requirement_policy.py) and signal revalidation: explicitly approve eligibility with unverified clearance only for mode-bound no-veto; admission failure still blocks; management exemption is not clearance |
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
| A3 | Source coverage/freshness interpretation | `BLOCKING` | Approve trusted observation of partial/failed/unknown coverage versus missing producer, positive-event freshness and retained-event handling; negative completeness is not a prerequisite |
| A4 | Gate-6 runtime adapter | `BLOCKING` | Compose exact identity, local known-at and lifecycle in correct order; approved source and horizon; reject tampering/ambiguous precision |
| A5 | Execution-state mapping | `BLOCKING` | Human approval of veto-style mode and source-gap risk acceptance; lossless no-veto versus clearance metadata, confidence and warning handling; no generic insufficient-data bypass |
| A6 | Alert behavior | `NON_BLOCKING` | Optional alerts remain disabled; any later activation requires wording, dedup, late-event and revision review |
| A7 | Outcome/calibration compatibility | `BLOCKING` | Bind policy/evidence/as-of and distinguish missed opportunities/unknowns; predeclare metrics before V2 shadow outcome claims |
| A8 | Historical replay version isolation | `BLOCKING` | Preserve V1 records; explicit V2 provenance and effective source/regulatory semantics, fail closed on missing history |
| A9 | Complete historical event archive/outcomes | `DEFERRED_FOR_SHADOW` | Not needed for prospective research pilot; no incomplete historical performance claim |
| A10 | Authoritative negative clearance | `DEFERRED_FOR_SHADOW` | `CLEAR_UNSUPPORTED` retained; later clearance needs distinct approved negative-evidence policy, never an absence shortcut |
| A11 | Optional results-season context | `NON_BLOCKING` | Remains disabled until evidence/presentation contract approved; never a gate or score |

The next approval may accept this **proposal, risk acceptance and blockers**, not
approve an unset duration or runtime activation. Future no-veto entry eligibility
and absent earnings clearance must both be stated truthfully. Shadow work must
measure event exposure after no-veto/source-gap decisions, not just false blocks.

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
declarative scenario table. Test-only injection of declared gate outcomes into
the real V1 reducer proves old deadlock and proposed composition liveness;
this **does not implement or execute a V2 schedule evaluator**. Existing V1 gate
tests validate actual runtime behavior. No full backend suite
is required for this documentation/artifact/test-only change.

Exact next continuation, not started:
`EARNINGS_BLACKOUT_POLICY_V2_GOVERNANCE_APPROVAL`.
