# Earnings Blackout Policy V2 — Governance Approval Receipt

Decision **A: `GOVERNANCE_APPROVED_WITH_ACTIVATION_BLOCKERS`**.
Scope: semantic governance only; **V1 active, V2 not active**.

This separate receipt governs the repaired
[proposal .2](EARNINGS_BLACKOUT_POLICY_V2_PROPOSAL.md) and its
[machine definition](EARNINGS_BLACKOUT_POLICY_V2_PROPOSAL.json).
The [approval artifact](EARNINGS_BLACKOUT_POLICY_V2_GOVERNANCE_APPROVAL.json)
records the exact decision, residual risk and blocker register. The proposal's
original `PROPOSED / NOT_ACTIVE` bytes and fingerprint are preserved as the
reviewed input; its historical next-step label is not a second current decision.

## Authority, identity and scope

| Field | Value |
| --- | --- |
| Reviewed baseline | `3b6194cadf9ff1e300f7272b8991d7b4e1525d78` |
| Candidate | `execution-gate-policy-v2-proposed / v2-proposal.2` |
| Proposal fingerprint | `sha256:36c80f2ea561a4411b252e6b4749f9c73275d6e434b257e89bdeb24d83de0e21` |
| Parent | `six-gates-production-v1 / v1` |
| Receipt identity | `earnings-blackout-policy-v2-governance-approval/v1` |
| Authority | User-delegated bounded governance review; directive `f0107207-5d2f-4a01-8dd8-d82dbf07f4d9` |
| Reviewer | Codex governance reviewer; no human signature or named-person attestation claimed |
| Approval | Repaired veto semantics and explicit residual-risk acceptance, subject to activation blockers |
| Runtime effective time, registration, implementation | None; no runtime authority created |

This is not a production approval/selection repository write, an approved numeric
horizon, a shadow evaluator or permission to implement in this slice. The
fingerprint is reproducible content identity, not a signature. No runtime/current
timestamp is invented. A later effective policy needs its own governed identity,
provenance, tests and activation decision. Diagnostic V2, B08 and other policy
approvals are neither reopened nor promoted by this execution-policy receipt.

## A–T governance determinations

| Review | Decision and binding interpretation |
| --- | --- |
| A, N — liveness | Approved/effective future mode and horizon, valid request and producer observation, no independent veto or retained unresolved event, and Gates 1–5 `PASS` permit `NO_VETO_ESTABLISHED → PASS → EXECUTABLE` in the existing reducer. This is a logical composition witness, not a present V2 result, source success-rate estimate or complete entry-ready proof. |
| B, F, O — no false clearance | `NO_VETO_ESTABLISHED` is not `CLEAR`, `SAFE`, `NO_EARNINGS_SOON` or authoritative negative evidence. Coverage gaps remain visible; source uncertainty is not low quality, bearishness or a score penalty. Conditional semantic risk acceptance is named and versioned below. |
| C — PASS hazard | Existing `_decision` gives `PASS` confidence `1.0`. It is unchanged and is not safe for future no-veto interpretation. B05 must prove `confidence=None`; B06 must preserve metadata end-to-end. Until closure V2 stays inactive. |
| D — positive veto | Every exact identity, purpose, official lineage, automatic local observation, effective/conflict-free lifecycle, freshness, approved horizon and producer/admission predicate is conjunctive. A policy record or an event date alone is insufficient. |
| E — undetermined | Missing receipt, invalid provenance, unresolved retained event, source-state conflict, malformed evidence or version mismatch cannot become no veto. Global admission rejection precedes composition; represent `UNDETERMINED` only where a structured result can safely be produced. |
| G — horizon | `POLICY_UNSET / CALIBRATION_REQUIRED`; value, unit, precision and boundaries remain absent. Neither V1 five sessions nor a regulatory two-working-day notice period is a V2 risk-window default. B14 open; B09 Rule × Horizon remains separate. |
| H — soft context | `RESULTS_SEASON_RISK_CONTEXT` stays `NOT_ACTIVE / NON_GATE / NON_SCORING / NON_EXECUTABLE / NON_SIZING / NON_ACTIONABLE`. Future research/UI/qualitative confidence discussion only; no numeric penalty or second Earnings Brain. |
| I — holdings | A newly observed event does not make an earlier entry a retroactive violation. No automatic sell or forced exit. Existing input scopes/exemptions remain distinct; future adds/tranches require their own approved entry policy and are not automatically exempt. |
| J — revisions | Resolve each revision's HSI-local visibility before lifecycle selection. Revisions, reschedules and cancellations affect only their own known-at onward. Cancellation removes only its linked veto, not other risks or global clearance. |
| K — immutability | Pinned Gate 1–5 definitions/methods, V1 Gate 6 five-session rule, production-policy, registry, source authority and version guards remain exact. Historical V1 decisions/replay stay V1; no implicit latest-version upgrade. |
| L — engine | Exactly six existing gates and one reducer. `VETO → FAIL`, `NO_VETO_ESTABLISHED → PASS`, `UNDETERMINED → INSUFFICIENT_DATA`; no abstention, Gate 7 or generic insufficient-data bypass. |
| M — presentation | Future Event `VERIFIED / NOT VERIFIED`; Clearance `UNVERIFIED`; Veto `ACTIVE / NO VERIFIED VETO / UNDETERMINED`. An outside-window verified event remains verified. No “Earnings Safe”, “No Earnings Soon”, “Calendar Clear” or suppressed warnings. No UI changes. |
| P — calibration | Retain all proposal measurement requirements, explicitly include reschedules and measurable unobserved-event misses. No metric formula, threshold, horizon or performance conclusion is approved here. |
| Q — pilot | A future 25–30-user pilot may use these semantics only after the governed runtime/horizon and all applicable blockers close. Research remains available independently. No current pilot activation or commercial-readiness claim. |
| R, S — dependencies | Separate blocking confidence guard, metadata propagation and signal/entry-ready review. Preserve prior downstream classifications; optional notifications remain disabled pending review. See registers below. |
| T — reuse | Existing schedule evidence, identity bridge, known-at receipts, coverage, lifecycle, calendar, reducer and provenance authority remain owners. No parallel calendar, event store, identity system, risk engine or Brain. |

## Admissibility, source gaps and no-veto metadata

Apply the proposal's existing precedence without introducing an alternate gate:

1. Global request/policy/producer/integrity failure rejects evaluation or safely
   returns `UNDETERMINED`; it never produces eligibility. Missing/mismatched
   policy versions, malformed evidence and untrustworthy source-state receipts
   fall here, not into the failed-query exception.
2. Exclude future evidence using verified HSI-local `known_at <= evaluation_as_of`.
   Do not expose future event IDs even in historical warnings. Source-public time
   stays separate; caller retrieval time is not a trusted first observation.
3. With global admission valid, an independent fully verified in-window event
   establishes `VETO`, even if an unrelated query fails or another local event
   is unresolved. A conflict in the veto event's own lineage disqualifies that
   positive proof. Global invalidity cannot be bypassed by another event.
4. Without an independent valid veto, retained possibly qualifying unresolved or
   stale events, or conflicting source-state evidence, remain `UNDETERMINED`.
   Source-state conflict is not ordinary partial/failed coverage. No input-order
   conflict resolution or deletion of old evidence is authorized.
5. Only after those exclusions may a trusted producer's actual observation of
   partial/unproven/stale coverage or a failed query support no veto when no
   retained unresolved event remains. A missing receipt, disabled producer,
   swallowed exception or fabricated empty list is not such an observation.

These are approval constraints on the existing global-admission/retained-event
rules, not new runtime reason codes or an implemented evaluator. B03/B04 require
explicit tested mappings. The existing proposal admission reasons remain intact.
Passed dates, completed labels and date-only events cannot invent a window end;
approved precision/window semantics are still required. No midnight/open-time
substitution, backdating, retrospective calendar repair or current-time lookup.

The future no-veto record must preserve `evaluation_mode=VERIFIED_EVENT_VETO`,
`earnings_clearance=UNVERIFIED`, `confidence=None`, actual source warnings and
coverage limitations, policy ID/version/fingerprint, source receipt lineage and
evaluation as-of. Names here follow the proposal's conceptual parameters, not a
new API schema. Required warning: `EARNINGS_CLEARANCE_UNVERIFIED`.
Metadata must participate in immutable lineage and survive downstream projection;
missing metadata rejects compatibility. A bare `PASS` cannot prove source
completeness or calendar confidence. The current Brain projection's loss of some
per-decision parameters is not repaired here. No global PASS/confidence change.

### Explicit residual risk

`VERIFIED_EVENT_VETO_RESIDUAL_SOURCE_RISK / v1` is accepted **for these conditional
semantics, not current runtime activation**: an official event may exist but be
unobserved/unverified until later. The eventual pilot must expose this risk and
measure no-veto/source-gap outcomes, not merely false blocks. It cannot be hidden
under confidence `1.0`, a green safety claim or fabricated negative evidence.

## Activation blocker register

All entries remain open. `BLOCKING` prevents V2 activation. `NON_BLOCKING` is
conditional on the optional feature remaining disabled; enabling it requires its
review to close. `DEFERRED_FOR_SHADOW` grants no authority to make unsupported
historical/clearance claims. B05–B07 split proposal A5 into independently provable
requirements; semantic approval does not close its implementation work.

These B01–B13 identifiers are local to this receipt's `approval_id`, not the
project-wide blocker register. In particular, local B08/B09 do not rename or
reopen the existing project B08 compatibility or B09 Rule × Horizon controls;
project B14 calibration remains open independently.

| ID (proposal origin) | Area | Classification | Required closure |
| --- | --- | --- | --- |
| B01 (A1) | Event-risk horizon/calibration | `BLOCKING` | Versioned calibrated window, calendar/precision/end boundaries and human approval; no five/two-day default |
| B02 (A2) | Trusted schedule producer | `BLOCKING` | Admitted official producer, exact payload identity and automatic first-observed receipts |
| B03 (A3) | Source-state interpretation | `BLOCKING` | Tested observed-gap versus missing-receipt/conflict/retained-event and positive-freshness semantics |
| B04 (A4) | Runtime V2 Gate-6 adapter | `BLOCKING` | One engine; exact identity, local PIT before lifecycle, approved provenance/horizon and malformed/version rejection |
| B05 (A5) | PASS/confidence semantic guard | `BLOCKING` | No-veto confidence null and mode/clearance retained; no completeness inference; V1 and Gates 1–5 unchanged |
| B06 (A5) | Execution-state metadata propagation | `BLOCKING` | Lossless fingerprint-bound mode, clearance, confidence, source limitations/warnings, policy/as-of and lineage through records/Brain |
| B07 (A5; downstream review) | Signal/entry-ready compatibility | `BLOCKING` | Explicit downstream no-veto risk interpretation; other gates/setup still required; no management-to-entry authority shortcut |
| B08 (A6) | Optional alert compatibility | `NON_BLOCKING` | Stay disabled until truthful wording, metadata, dedup and revision handling approved |
| B09 (A7) | Outcome/calibration compatibility | `BLOCKING` | Versioned observation/counterfactual contracts; no fabricated fills, denominators or missing-event measurements |
| B10 (A8) | Historical policy-version isolation | `BLOCKING` | Exact policy/source/regulatory/horizon/calendar and local observation replay; no V1 rewrite or latest fallback |
| B11 (A9) | Complete historical archive/outcomes | `DEFERRED_FOR_SHADOW` | Not a prospective research prerequisite; incomplete data cannot support complete-history performance claims |
| B12 (A10) | Authoritative negative clearance | `DEFERRED_FOR_SHADOW` | `CLEAR_UNSUPPORTED` until separate negative-evidence governance; never inferred from absence |
| B13 (A11) | Optional results-season context | `NON_BLOCKING` | Disabled pending source/presentation approval; never gate, score, sizing or action |

## Downstream impact and canonical reuse

| Classification | Consumers | Governance consequence |
| --- | --- | --- |
| `NO_CHANGE` | Decision Score; TradePlan | No weights, points, uncertainty penalty, entry/stop/target or Gate-4 policy changes |
| `ADAPTER_UPDATE_REQUIRED` | Brain; Signals; Backtest; Six-Gates orchestration | Preserve mode/clearance/warnings and exact effective policy/source/as-of lineage; reject loss or mismatch |
| `POLICY_REVIEW_REQUIRED` | Portfolio; Entry-ready lifecycle; Alerts | Approve interpretation, not actions; separate holding scope, complete entry requirements and disabled optional notification paths |
| `CALIBRATION_REQUIRED` | Outcome ledger | Predeclared versioned observations/counterfactuals; no synthetic executions or performance claim |

The scoped reuse paths are the existing [official schedule evidence](../../app/gates/official_earnings_schedule_candidate.py),
[identity bridge](../../app/filings/earnings_schedule_identity.py),
[local observation/known-at](../../app/filings/earnings_schedule_known_at.py),
[coverage](../../app/filings/earnings_schedule_coverage.py),
[schedule lifecycle](../../app/filings/earnings_schedule_store.py),
[exchange calendar and canonical reducer](../../app/gates/engine.py),
[source authority](../../app/gates/source_authority.py) and
[production policy](../../app/gates/production_policy.py).
The proposal's downstream audit remains the detailed file map. No source is
importing the new artifact; no new producer, store, calendar or engine is created.

## Calibration and pilot limits

Retain known-at → event distance; overnight/open gap; absolute and ATR-normalized
gap; MFE/MAE; drawdown; slippage; post-event volatility; missed opportunities;
false-block rate; known-late rate; revision and reschedule frequency; and
**unobserved-event miss rate where measurable**. The latter needs independently
verified eventual event ascertainment and a declared denominator; an absent
observation cannot be counted as zero misses. These are measurement requirements,
not newly approved formulas, thresholds, sample sizes or risk windows.

All measurements need canonical PIT/event/revision/market lineage, price
comparability, missing-data rules, cohort definitions and forward/out-of-sample
protocols as in the proposal. ATR lookback, reference prices, windows, hypothetical
fill methodology and event-end precision remain unresolved; no number is selected.
B14 remains open. Full historical coverage is not a prerequisite for prospective
research, but it cannot be replaced by a performance claim from incomplete data.

The future 25–30-user pilot can continue composition after admitted no veto and
block fresh entry after verified veto, while showing `UNVERIFIED` clearance.
This is conditional on the governed horizon/runtime and all applicable blockers,
not just installing an adapter. Research stays independent of entry eligibility.
No pilot, outcome collection, notification or commercial activation starts here.

## Validation, replay and frozen boundaries

The static [approval tests](../../tests/unit/test_earnings_blackout_policy_v2_governance_approval.py)
bind this receipt to the proposal's fingerprint and unchanged source artifacts,
verify risk/blocker completeness, reject contradictory rehashed approval fields,
and replay all approval fields through deterministic serialization. Existing
[proposal proofs](../../tests/unit/test_earnings_blackout_policy_v2_proposal.py)
independently pin every gate definition/method and active authority source.
Test-only synthetic outcomes enter the actual reducer to prove liveness and
failure precedence, not to implement or validate a V2 schedule evaluator.

Approval hashing uses existing `canonical_json` / `content_fingerprint`: UTF-8,
sorted keys, ordered arrays, compact separators, ASCII escaping, no non-finite
numbers, excluding only `approval_fingerprint`. LF-normalized file pins preserve
cross-platform comparisons; every semantic field participates. Rehashing altered
safety values does not satisfy test-only semantic validation. No secret, database
write, runtime registration or execution authority is present in this artifact.

Retained: `V1_ACTIVE=TRUE`, `GATE_POLICY_V2_ACTIVE=FALSE`,
`SIX_GATES_EXACTLY_SIX=TRUE`, `NO_UNVERIFIED_CALENDAR_CLEARANCE=TRUE`,
`NO_RETROACTIVE_BLACKOUT=TRUE`, `NO_AI_PREDICTED_EARNINGS_DATE=TRUE`,
`PILOT_SIMPLICITY_RULE=ACTIVE`, `AI_DECISION_AUTHORITY=FALSE`.
No runtime changes means no full backend suite is required for this slice.

Exact next continuation, **not started**:
`EARNINGS_BLACKOUT_HORIZON_CALIBRATION_CONTRACT_V1`.
Define the measurement/precision/data contract before proposing a numeric horizon;
do not implement a runtime adapter around the unset parameter.
