# Earnings Blackout Prospective Receipt Collector V1

**Status:** `V1_ACTIVE / PROSPECTIVE_EVIDENCE_ONLY / GATE_POLICY_V2_INACTIVE / NON_TRADING`.

This document closes the bounded implementation gap identified by the
[prospective schedule receipt readiness audit](EARNINGS_BLACKOUT_PROSPECTIVE_SCHEDULE_RECEIPT_READINESS_V1.md).
It describes only prospective official-source observation. It neither changes
the frozen six-gate V1 policy nor activates Gate 6 V2, selects an earnings-risk
horizon, creates calendar clearance, or evaluates an investment action.

## Purpose and hard boundary

`ProspectiveEarningsScheduleReceiptCollector` performs one bounded official
NSE/BSE pass for an exact caller-supplied current instrument cohort. It retains
immutable source evidence in the existing `CoreApiSnapshotRepository` family
`EARNINGS_SCHEDULE_PROSPECTIVE_RECEIPT`; this is a typed use of the existing
snapshot table, not a new calendar database, migration, event warehouse, API,
or runtime scheduler.

Every output is `WATCH_ONLY / NON_EXECUTABLE`; every coverage receipt carries
`SOURCE_SCOPE_UNPROVEN` and `gate6_clearance=false`. The collector has no
dependency on signals, portfolios, orders, brokers, Decision Score, or Gate 6
execution. It is a one-shot library boundary, not a daemon and not an automatic
runtime job.

## Immutable prospective chain

```text
bounded official GET
  -> raw response bytes + SHA-256 artifact
  -> automatic aware-UTC first observation
  -> parsed source-row observation
  -> exact canonical identity and purpose assessment
  -> immutable qualifying receipt or explicit unavailable assessment
  -> partial/failed coverage receipt
```

The collector captures `RAW_ARTIFACT_FIRST_OBSERVED_AT` automatically through
an injectable UTC clock at the observation boundary. Production uses only
`SystemUtcClock`; `collect_once` accepts no caller-supplied historical
first-observed override. Tests may inject a deterministic clock. An unchanged
artifact or row returns its stored original observation on restart; a later
parser/processing step cannot move it forward.

The following fields remain distinct:

| Field | Treatment |
| --- | --- |
| Source public / received time | Raw source strings only; semantic authority is `UNPROVEN` unless separately governed. |
| Raw artifact first observed | Automatic HSI aware-UTC observation bound to exact raw bytes. |
| HSI available / qualifying time | Detail-row first observation, only after HSI actually acquired qualifying evidence. |
| Event date | Parsed `DATE_ONLY` meeting date; never a publication or known-at timestamp. |
| Processed time | Separate aware-UTC persistence/assessment time. |

## Discovery and qualification

NSE rolling RSS and BSE recent-corporates list records are discovery evidence
only. The collector retains their bytes and observations first. It then uses
only the existing exact linked NSE Prior Intimation document or BSE mobile
detail document for financial-results-purpose classification. List/RSS
observation time never backdates the qualifying receipt's HSI first-observed
time.

Identity uses the existing `EarningsScheduleCanonicalIdentityBridge` only:
NSE requires exact structured symbol/ISIN and BSE requires exact code/ISIN
mapping at the prospective observation time. There is no company-name fallback.
Unresolved identity, ambiguous/non-qualifying purpose, unavailable date, source
conflict, and unsupported revision lineage are persisted as typed assessments,
not silent drops or positive events.

NSE and BSE remain independent provenance. One valid exchange detail creates a
positive official observation; neither exchange proves the other absent.

## Raw retention, replay, revisions, and failures

Raw response bytes are base64-retained with a SHA-256 content fingerprint,
public endpoint identity, response status, adapter version, parser-bound row
lineage, and receipt fingerprint. No credentials, request headers, cookies, or
secrets are retained.

| Observed condition | Immutable outcome | Prohibited interpretation |
| --- | --- | --- |
| Identical source record and bytes after restart | Existing artifact, observation, and qualifying receipt reused with original first observation | New logical first-observed time |
| Same source record, changed bytes | New immutable observation and a `REVISED` receipt only when deterministic lineage exists | Overwrite of prior evidence |
| Exact source-declared reschedule/cancellation with stored exact parent | New immutable `RESCHEDULED`/`CANCELLED` receipt linked to parent | Rewrite of parent history |
| Source-declared lifecycle with no exact parent or unsupported lifecycle label | Raw evidence plus `REVISION_LINEAGE_UNRESOLVED` assessment | Guessed parent or lifecycle |
| HTTP/transport/parser/detail failure or empty partial result | Source-poll plus partial/failed coverage receipt | No-event, safe, clear, or Gate-6 permission |
| Disappearance from a later partial feed | No new lifecycle conclusion | Cancellation inference |

Every root and detail poll retains a `ProspectiveSourcePollReceipt`, including
zero rows and failures. Per-target existing `EarningsScheduleCoverageReceipt`
records partial/failed source coverage. Its absence states remain evidence-only;
zero rows never mean `NO_EVENT_EXISTS`, `CLEAR`, `SAFE`, or `PASS`.

## Calibration readiness

The receipt includes exact source observation, canonical identity, qualifying
purpose, date precision, raw source timestamp strings, automatic first-observed
receipt, lifecycle/revision parent, identity fingerprint, policy version, and
tamper-evident fingerprint. This is enough lineage for a future
`PROSPECTIVE_SHADOW_CALIBRATION` event under the accepted
[horizon calibration contract](EARNINGS_BLACKOUT_HORIZON_CALIBRATION_CONTRACT_V1.md).

It does not create actual-result reconciliation, a reaction session, price
outcomes, MFE/MAE, a risk horizon, or any action-impact result.

| Capability | State |
| --- | --- |
| Prospective positive official receipt collection | `READY` after a successful bounded official canary; otherwise runtime-blocked only at the source boundary. |
| Automatic first observed and raw evidence | `READY`. |
| Replay/restart idempotency and revision evidence | `READY` for exact source lineage. |
| Negative absence / calendar clearance | `NOT_READY` by design. |
| Actual-result and price-outcome linkage | `PARTIAL`; separately governed future work. |
| Layer 1 market-event prospective shadow input | `READY` once live source receipt collection runs. |
| Layer 2 action-impact calibration | `PARTIAL`; needs a genuine prospective setup/signal/gate/paper-outcome chain. |

## Preserved governance

`V1_ACTIVE=TRUE`; `GATE_POLICY_V2_ACTIVE=FALSE`;
`SIX_GATES_EXACTLY_SIX=TRUE`; `NO_UNVERIFIED_CALENDAR_CLEARANCE=TRUE`;
`NO_RETROACTIVE_BLACKOUT=TRUE`; `NO_FUTURE_LEAKAGE=TRUE`;
`NO_HORIZON_GUESS=TRUE`; `PROSPECTIVE_FIRST_OBSERVED_ONLY=TRUE`;
`PILOT_SIMPLICITY_RULE=ACTIVE`; and `AI_DECISION_AUTHORITY=FALSE`.

The next permitted continuation, after a successful bounded canary, is
`EARNINGS_BLACKOUT_HORIZON_PROSPECTIVE_SHADOW_V1`; it must not activate Gate 6
V2 or manufacture retrospective receipts.
