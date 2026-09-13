# Gate 3 Surveillance V2 — Single Composite Successor Proposal

Status: **`PROPOSED / NOT_ACTIVE / DOCUMENTATION_ONLY`**.
Baseline: `62a78a00314403e1d051056d04dc5326da877f7a`, `main`.

Decision **A: `GATE3_V2_PROPOSAL_COHERENT_COMPOSITE_V2_REQUIRED`**.
This is the bounded successor to [Repair 2](GATE3_SURVEILLANCE_POLICY_SOURCE_REPAIR_2.md).
The [machine proposal](GATE3_SURVEILLANCE_POLICY_V2_PROPOSAL.json) is the exact
versioned definition; the [tests](../../tests/unit/test_gate3_surveillance_policy_v2_proposal.py)
check its source pins, temporal examples and unchanged reducer composition.
No collector, runtime model, registration, database write or activation occurs.

## 1. One future policy, not competing V2s

| Identity / authority | Definition |
| --- | --- |
| Composite candidate | `execution-gate-policy-v2-proposed / v2-proposal.3` |
| Parent production policy | `six-gates-production-v1 / v1` |
| Prior whole-policy candidate | `execution-gate-policy-v2-proposed / v2-proposal.2` |
| Prior proposal fingerprint | `sha256:36c80f2ea561a4411b252e6b4749f9c73275d6e434b257e89bdeb24d83de0e21` |
| Prior Gate-6 approval fingerprint | `sha256:0d2bd690a9b5cec347437163cbc7ad88cadec940b0546549ce40361b833414d0` |
| New composite approval / effective time | **Absent; new governance approval required** |
| Production selection | V1 only; no implicit latest-candidate lookup |

The repository's [production policy](../../app/gates/production_policy.py) is a
whole-six-gate immutable policy, not a registry of independently activatable gate
components. Existing future proposals are documentation JSON, not runtime policy
instances. Accordingly this is one composite revision in the existing candidate
line, with exact by-reference incorporation rather than a second whole-policy ID.
No additional independently selectable `execution-gate-policy-v2` is created.

The complete [Gate-6 proposal .2](EARNINGS_BLACKOUT_POLICY_V2_PROPOSAL.json) and
[approval](EARNINGS_BLACKOUT_POLICY_V2_GOVERNANCE_APPROVAL.json) remain byte-for-byte
unchanged. All their Gate-6 normative semantics, positive-event prerequisites,
local known-at/revision rules, source-gap distinctions, residual risk, horizon
requirements, confidence/warnings, action scopes, and activation constraints are
incorporated by their exact hashes. There are no local Gate-6 overrides. In
particular:

- `VERIFIED_EVENT_VETO`: `VETO -> FAIL`, `NO_VETO_ESTABLISHED -> PASS`,
  `UNDETERMINED -> INSUFFICIENT_DATA`, subject to the existing admission order.
- No veto is **not calendar clearance**. Retain `UNVERIFIED`, confidence `null`,
  `EARNINGS_CLEARANCE_UNVERIFIED`, and the approved visible residual risk.
- The event horizon is still `POLICY_UNSET`; no inherited five-session default.
  The [prospective shadow](EARNINGS_BLACKOUT_HORIZON_PROSPECTIVE_SHADOW_V1.md)
  adds measurement support, not a selected horizon or Gate-6 activation.

The prior approval's Gate-1-through-5 immutability statement describes the .2
reviewed baseline. It is not silently extended to approve a changed Gate 3.
This proposal explicitly adds that change, pins Gates 1/2/4/5, and requires a new
composite approval. The prior approval remains valid evidence of the Gate-6
component decision; it is not an approval signature for the new fingerprint.
Earlier next-step labels and statuses remain historical, not competing authority.

## 2. Exact V1 to proposed composite diff

| Aspect | Active V1 | Composite .3 proposal |
| --- | --- | --- |
| Policy | `six-gates-production-v1 / v1` | Existing future ID, `v2-proposal.3`; not approved/active |
| Gate count | Six | Same six IDs, same order, no abstain/Gate 7 |
| Gates 1/2/4/5 | Existing definitions/configuration/methods | Exact definition/method fingerprints carried forward |
| Gate-3 numeric thresholds | ASM >=2; GSM >0; static circuit <=0.05 | Identical; no exceptions or new thresholds |
| Gate-3 substantive inputs | ASM, GSM, PRICE_BAND | Identical three fields |
| SECURITY_STATUS | Descriptive source family, no formula/guard | Same; no mandatory PASS value or predicate |
| Authority | NSE execution venue; BSE corroboration only | Same |
| State selection | Approved state for relevant completed session | Latest PIT-visible, admitted, source-proven state effective for the target execution context |
| Identity | Exact canonical security; source-specific execution grain | ASM/GSM security membership; price band exact target symbol+series; resolved V1 scope retained |
| Effective precision | Single datetime carrier; source selector not implemented | Preserve source date/session or instant precision; do not invent a datetime to fit V1 carrier |
| First observation | PIT provenance required; no surveillance producer admitted | Verified automatic payload-available receipt <= as-of, separately from publication/effectiveness |
| Freshness | Maximum four trading sessions, inclusive | Same cap, plus truthful current applicability; fetching again cannot renew effective age |
| Missing/source failure | INSUFFICIENT_DATA before threshold comparison | Same; no old non-blocking fallback when required current state is unresolved |
| Conflict | No truthful admitted clearance | Unresolved authoritative disagreement -> INSUFFICIENT_DATA; no timestamp voting |
| Gate-3 PASS annotation | Constant 1.0 | Same annotation, not empirical reliability |
| Gate 6 | Existing five-session V1 rule | Exact approved .2 verified-event-veto semantics carried forward, still inactive |
| Historical records | V1 policy/source lineage | V1 remains V1; V2 replay needs its own exact policy and PIT lineage |

Exact IDs: `GATE_1_ROTATION`, `GATE_2_VELOCITY`, `GATE_3_SURVEILLANCE`,
`GATE_4_TRADE_PLAN`, `GATE_5_HEAT`, `GATE_6_EARNINGS`.
The sole **new** semantic change relative to .2 is Gate-3 source-state selection.
No numerical calibration project follows from that change. Gate-6's existing
calibration requirement is separate and is neither removed nor declared complete.

## 3. Normative temporal selector

Name: **`LATEST_PIT_VISIBLE_EFFECTIVE_SURVEILLANCE_STATE`**.
"Latest" means the unique applicable terminal state under verified official
replacement/revision relations, **not** maximum fetch/publication timestamp.

| Term | Exact proposed meaning |
| --- | --- |
| `EVALUATION_AS_OF` | Explicit timezone-aware decision cutoff, normalized UTC; no runtime clock |
| `EXECUTION_SESSION` | Explicit target NSE trading-session identity bound to that cutoff by existing PIT-visible canonical calendar evidence; not guessed from UTC date or last completed bar |
| `KNOWN` | Verified automatic HSI receipt proves the payload was available by as-of; inclusive `known_at <= as_of` |
| `SOURCE_PUBLICATION` | Separate official publication evidence at its genuine precision; never substituted for HSI observation |
| `EFFECTIVE_FROM/TO` | Official applicability bounds and precision; not observation or download times |
| `EFFECTIVE` | The exact target session/as-of belongs to the source-proven applicability, with boundary semantics supported by the source |

Use the existing [canonical session resolver](../../app/historical/canonical_market_session_event_time.py).
If the request's session is missing, ambiguous, unsupported, or cannot be bound
to as-of, return insufficient. A closed-market cutoff does not silently select
tomorrow's session; any distinct future-session evaluation scope needs its own
approved context. This does not add an independent market-hours gate or change
existing action scopes/exemptions.

For an exact instant interval, use `from <= as_of < to` **only if official
semantics establish those boundaries**. A differently stated endpoint must be
resolved from source evidence, not coerced to this form. For a date-only source,
use the proved session date/set or source-defined session range and its stated
endpoint inclusivity. No midnight, market-open or end-of-day datetime is invented.
Unknown end date is not proof of indefinite validity. Explicit "until further
notice" scope still needs current admitted evidence and unchanged freshness cap.

Future adapter/selector obligations, in order:

1. Verify request, canonical execution context, effective approved composite and
   source versions. This document itself is not an admitted policy.
2. Apply HSI-local known-at filtering **before** selecting revisions or conflicts.
   Future receipts cannot enter selected lineage, warnings or historical output.
3. Verify NSE authority, exact family scope/identity, immutable raw/receipt hashes
   and source contract. Malformed or unverified required evidence is insufficient.
4. Establish genuine applicability for the target session/as-of. An old snapshot
   covering only the prior date cannot govern today just because its age is <=4.
5. Resolve only same-component/same-scope official supersession or a verified
   complete-replacement product relation. The relationship's own evidence must
   also be PIT-visible and effective; cancellation/removal cannot be backdated.
6. Require one non-conflicted current state per component. Identical receipt ID
   and fingerprint is an idempotent input; same ID/different content is conflicted.
   Independent unresolved states do not gain precedence from input order, a
   larger timestamp or a favourable value. No voting or averaging.
7. Require a fresh admitted complete three-component vector, then apply the
   unchanged formula and existing six-gate reducer.

Partial/failed/stale current capture or an unresolved current notice does not
authorize falling back to an old non-blocking record. A source-supported older
record can be used only when it genuinely remains current/applicable and all
capture, conflict and freshness proofs still hold. There is no new polling rate,
TTL, observation-renewal rule, inferred absence or price-derived band.

### Causality and transitions

Prospective `HSI_FIRST_OBSERVED_AT <= EVALUATION_AS_OF` is inclusive. The receipt
must attest completed payload availability, not request start or a caller-entered
retrieval time. Reuse [first-observed](../../app/filings/earnings_schedule_known_at.py)
and [coverage](../../app/filings/earnings_schedule_coverage.py) patterns, not an
unexamined timestamp from another collector. The earnings shadow explicitly
uses a later completed-observation bound where its collector stamped request
start; this proposal does not alter that collector or backdate surveillance.

| Situation | Required interpretation |
| --- | --- |
| Prior session non-blocking; today's restriction effective and known | Today's admitted restriction governs; prior-session PASS no longer supplies current proof |
| Restriction already effective but first seen after decision T | Replay at T excludes it; original decision unchanged, whether originally PASS or insufficient |
| Same restriction at/after its truthful observation | It may govern only if current applicability and all admission requirements hold |
| Notice known now, effective in a future session | Do not apply its restriction early; retain genuinely valid present state or insufficient |
| Removal first seen late | No retroactive clearance; reassess only its linked effective state from its own known-at onward |
| Historical T had no admissible current proof | It remains insufficient; no retrospective fabrication of PASS or FAIL |

All are synthetic semantic test cases, not a live NSE transition or a canary.
Replay identity includes the explicit policy ID/version/fingerprint and selected
source/session/known-at lineage. Loading later data cannot alter a frozen decision.

## 4. Source-specific admission and formula contracts

| Component | Exact identity and non-blocking proof | Blocking / unknown |
| --- | --- | --- |
| ASM | Classified NSE security/ISIN + validated symbol + framework applicability to actual target; complete admitted applicable current snapshot proving stage below 2 or defensible absence of a blocking stage | Stage >=2 blocks after common admission; incomplete scope/export, ambiguous stage or conflict is unknown |
| GSM | Same security-level proof; complete admitted stage-wise current state proving no stage >0 | Stage >0 blocks; stage-0 shortlisting remains distinct from absence; composite indicator is not a stage number |
| PRICE_BAND | Actual execution symbol+series, exact security and official master/token join where needed; explicit static numeric band >5% | <=5% blocks; absent/blank/dynamic/unsupported/mismatched/ambiguous is unknown |
| SECURITY_STATUS | Descriptive source family retained only | No blocking/non-blocking value or required PASS field; future use requires separate explicit governance |

ASM/GSM do not require a fabricated list-row series, and cannot fan out by issuer
name. Reuse [InstrumentIdentity](../../app/market_data/models.py) and existing
[NSE identity evidence](../../app/historical/nse_session_identity.py). Price band
must use the actual target's verified series, never default EQ; a provider token
is not automatically an NSE master token. The earlier 0/314 list-series result
is not a gate-wide identity blocker or a measurement of target price joins.

Accepted ASM/GSM official products are complete; actual future adapter/export
completeness remains **UNPROVEN**. Documentation is not collector proof. Every
required applicable capture must be admitted as complete; HTTP success is not
that proof. Bare absence never supplies zero. Once an admitted complete product
and source semantics establish non-blocking state, its proof is component-level,
not global Gate clearance. Percent-to-fraction conversion is exact Decimal `/100`.

### Outcome precedence — unchanged Gate 3, not a new veto model

Common admission requires effective approved policy/source versions, exact
context, NSE authority, payload-bound first observation, supported current
applicability, non-conflicted lineage and a fresh complete three-component vector.

| Condition | Gate-3 result |
| --- | --- |
| Required source/identity/known-at/effectiveness/freshness/conflict proof missing or invalid | `INSUFFICIENT_DATA`, or existing pre-formula admission rejection; never eligibility |
| Any substantive field missing | `INSUFFICIENT_DATA` |
| Common admission and any ASM >=2, GSM >0, static band <=5% | `FAIL` |
| Common admission and all three non-blocking | `PASS` |
| ASM blocking but GSM missing, or any analogous mixed vector | `INSUFFICIENT_DATA`, preserving V1 completeness-first behavior |

The request's "any admitted blocking component" is thus evaluated after common
Gate-3 admission, as in the frozen engine. It is not permission to override
missing other required inputs with an independent-component veto. That would be
an additional, unauthorized semantic change. Gate-6 retains its separately
approved independent-event-veto order; that order is **not imported into Gate 3**.
An unresolved current source can neither create PASS nor fabricate a risk FAIL.

The reducer remains `any FAIL -> BLOCKED; else any INSUFFICIENT_DATA ->
INSUFFICIENT_DATA; else all six PASS -> EXECUTABLE`. No broker/order authority
follows. `GATE_RESULT_CONFIDENCE_ANNOTATION != SOURCE_COMPLETENESS_PROBABILITY`:
Gate-3's constant 1.0 annotation is retained, while the incorporated Gate-6
no-veto result still requires null confidence. No global confidence change.

## 5. Downstream audit, reuse and activation blockers

| Consumer | Gate-3 addition classification | Required future compatibility (no changes here) |
| --- | --- | --- |
| Six-Gates orchestration | `ADAPTER_UPDATE_REQUIRED` | Existing source authority/envelope and engine; explicit composite selection, session and component lineage |
| Brain | `ADAPTER_UPDATE_REQUIRED` | Stored-only gate context; preserve source/version/selection rather than turning unknown into low quality |
| Signals | `ADAPTER_UPDATE_REQUIRED` | Exact gate context/version; later reevaluation does not rewrite an earlier signal |
| Portfolio | `POLICY_REVIEW_REQUIRED` | Context compatibility only; no position action, new management exemption or authority |
| Entry-ready lifecycle | `POLICY_REVIEW_REQUIRED` | All existing setup/score/gate requirements plus Gate-6 non-clearance metadata |
| Backtest/replay | `REPLAY_UPDATE_REQUIRED` | No market-timestamp-max selection masquerading as local PIT; exact historical version |
| Outcome ledger | `ADAPTER_UPDATE_REQUIRED` | Preserve source/session/policy decision lineage, not simulated transactions |
| Alerts | `POLICY_REVIEW_REQUIRED` | Disabled pending truthful wording, dedup and prospective-only revision interpretation |
| Decision Score / trade-plan calculation | `NO_CHANGE` | No score weights, thresholds, prices or sizing changes |
| Gate-3 numeric calibration | `CALIBRATION_NOT_REQUIRED` | Same thresholds; temporal/admission tests required, not a new calibration project |

This is the **incremental Gate-3** impact. Incorporated Gate-6 outcome/calibration
and downstream blockers still apply separately. Existing [Brain gate adapter](../../app/intelligence/six_gates_evidence.py)
and [output context](../../app/intelligence/output_evaluation_context.py) retain
stored references, but do not prove full future selector metadata propagation.
The [signal engine](../../app/signals/engine.py) uses gate status/configuration;
the [portfolio activator](../../app/portfolio/canonical_six_gates_activation.py)
persists existing evaluations. [Backtest](../../app/backtest/analytical.py) has
market-timestamp selection, not this new current-effective selector. The
[paper ledger](../../app/paper/models.py) records gate-configuration versions, not
proof of surveillance completeness. These are reuse points, not readiness claims.

The existing gate ID format and in-memory evidence context cannot be assumed to
provide collision-free, lossless cross-policy persistence automatically. Future
compatibility must verify policy-version-scoped identities and full source/session
lineage. Do not register .3 into the V1-only verifier or overwrite V1 records.

| ID | Activation requirement | Classification |
| --- | --- | --- |
| G3A01 | Actual complete prospective ASM export | `BLOCKING` |
| G3A02 | Actual complete prospective GSM export | `BLOCKING` |
| G3A03 | Exact target symbol+series static price-band producer | `BLOCKING` |
| G3A04 | Automatic payload-bound immutable first-observed receipts | `BLOCKING` |
| G3A05 | Effective-state selector, session precision and unchanged four-session cap | `BLOCKING` |
| G3A06 | Conflicts and explicit PIT-visible supersession | `BLOCKING` |
| G3A07 | Existing Gate-3 evidence adapter and source admission | `BLOCKING` |
| G3A08 | New composite approval, policy selection and downstream version compatibility | `BLOCKING` |
| G3A09 | Bounded prospective canary, including transition/no-false-pass proof | `BLOCKING` |
| G3A10 | Historical V1/V2 version isolation and no retroactive mutation | `BLOCKING` |
| G3A11 | Complete historical surveillance archive | `DEFERRED_FOR_REPLAY` |
| G3A12 | Optional alerts remain disabled | `NON_BLOCKING` while disabled |

These IDs are scoped to this proposal. They do not close or rename the Gate-6
approval's blockers. Existing earnings collector/shadow progress is retained;
this audit neither reopens it nor treats it as approved horizon/runtime evidence.

Use the existing [snapshot repository](../../app/storage/core_api_snapshot_repository.py),
canonical identity, known-at/coverage patterns, calendar, [gate envelope](../../app/gates/version_compatibility.py),
[source authority](../../app/gates/source_authority.py) and [reducer](../../app/gates/engine.py).
Existing earnings-specific receipts are a pattern, not an admitted surveillance
receipt type; do not falsely label surveillance as earnings. No second store,
symbol master, calendar, surveillance Brain/score, engine or policy authority.

Prospective pilot operation needs current complete admitted evidence and all
applicable composite/Gate-3/Gate-6 blockers closed, not perfect historical
surveillance archives. V1 history remains immutable; later V2 replay requires
strict local-PIT, effective-state and exact policy/source/calendar lineage. A
missing archive prevents that replay, not independent research. No commercial
readiness, live capture, canary, portfolio mutation or order claim is made here.

## 6. Validation and continuation

Use existing canonical JSON/fingerprint helpers: sorted object keys, ordered
arrays, UTF-8, deterministic Decimal conventions, no nonfinite values. The
proposal hash excludes only `proposal_fingerprint`; referenced normative artifacts
are verified against pinned full hashes before composition. No runtime timestamp
or production approval hash is fabricated. File pins are explicitly LF-normalized;
definition and method pins follow the existing Gate-6 proposal tests.

Tests cover exact six gates and source pins; Gate-6 carry-forward and absence of
transferred approval; current-session transitions; inclusive local known-at;
future/late/revision exclusion; date precision; identity; complete product versus
capture; mixed incomplete vectors; deterministic artifact replay/tamper rejection;
and synthetic composition through the **existing** reducer. Test-only temporal
examples are not a production selector or evidence of a live collector.
No full backend run is required because runtime files remain unchanged.

```text
V1_ACTIVE = TRUE
GATE_POLICY_V2_ACTIVE = FALSE
SIX_GATES_EXACTLY_SIX = TRUE
NO_FABRICATED_SURVEILLANCE_CLEARANCE = TRUE
NO_UNVERIFIED_CALENDAR_CLEARANCE = TRUE
NO_FUTURE_LEAKAGE = TRUE
NO_RETROACTIVE_SURVEILLANCE_STATE = TRUE
PILOT_SIMPLICITY_RULE = ACTIVE
AI_DECISION_AUTHORITY = FALSE
```

Exact one next continuation: **`EXECUTION_GATE_POLICY_V2_COMPOSITE_GOVERNANCE_APPROVAL`**.
It is **not started**. This proposal does not supply that approval or activate V2.
