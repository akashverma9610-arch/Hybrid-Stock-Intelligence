# NSE Security Master Session-Knownness Policy Proposal V1

**Status: `PROPOSED / NOT_APPROVED / NOT_ACTIVE / RESEARCH_ONLY / NON_EXECUTABLE`.**

## Purpose and scope

This proposal defines the smallest conservative semantic that may later be
approved for a validated official NSE CM-MII dated security-master file:

> For trading session `D`, an exact row in the official
> `NSE_CM_security_DDMMYYYY.csv.gz` file dated `D` may establish that the
> exact NSE security identity was present in the exchange master for session
> `D`.

It defines **`SESSION_IDENTITY_EVIDENCE`**, not `LISTING_INTERVAL_EVIDENCE`.
It answers neither original listing date nor continuous trading/listing status.
It does not classify a company, qualify a universe, evaluate a Compounder,
alter a portfolio, or authorize an action.

## Proposed policy object

`app.historical.nse_mii_session_knownness.NseMiiSessionKnownnessPolicy` is an
immutable research object. Its identity is
`nse-security-master-session-knownness-policy / v1-proposed`; its deterministic
fingerprint covers the source contract, allowed semantics, prohibited
semantics, and the fixed states below.

| Field | Fixed value |
| --- | --- |
| policy state | `PROPOSED` |
| approval state | `NOT_APPROVED` |
| activation state | `NOT_ACTIVE` |
| source contract | `nse-historical-mii-security-master-snapshot-acquisition / v1` |
| evidence scope | exact NSE symbol, ISIN, series, security code, and raw status/type fields for the same session only |
| timestamp semantics | no exact `historical_known_at`; it remains `null` |

The object has no selection record and cannot activate itself. Its evaluator is
a deterministic test adapter only; its `SESSION_IDENTITY_PRESENT` result is a
proposed descriptive semantic, never an authoritative
`HistoricalSecurityIdentity` receipt.

## Strict evidence and session rule

The same-session result is possible only when all conditions hold:

1. the source is the exact official HTTPS NSE archive path
   `https://nsearchives.nseindia.com/content/cm/NSE_CM_security_DDMMYYYY.csv.gz`;
2. the filename, requested report date, and immutable snapshot report date all
   agree;
3. the pre-existing acquisition validation accepted gzip/CSV integrity,
   required columns, stable source/schema fingerprints, and structurally valid
   identity fields;
4. the exact row is bound to that snapshot and is unambiguous within the
   validated supplied snapshot rows; and
5. `D` is an actual canonical trading session through an existing
   `is_trading_day(date)` calendar contract.

The evaluator is compatible with the existing calendar abstraction; it does
not create a new exchange calendar or add holiday data. Weekends/holidays are
`NOT_APPLICABLE`, not session-known. Invalid source/date or row binding is
`INVALID_SOURCE_DATE`; an absent file/row is `SNAPSHOT_UNAVAILABLE`.

No fetch/observation timestamp is used as historical knowledge time. The
official daily MII file is documented for pre-trading use on its labelled
session, but the public artifact does not provide a verifiable HH:MM:SS.

## PIT and lifecycle boundaries

| Evaluation versus report date | Required proposed result | Prohibited interpretation |
| --- | --- | --- |
| `evaluation_session = D` | `SESSION_IDENTITY_PRESENT` for one exact valid row | listing start, full listed interval, investment eligibility |
| `evaluation_session < D` | `FUTURE_SNAPSHOT` | backward substitution to any earlier session |
| `evaluation_session > D` | `WRONG_SESSION` | forward substitution or assumed continuing presence |
| non-trading date | `NOT_APPLICABLE` | session identity from a weekend/holiday label |

First observed snapshot does not establish a listing start. Last observed
snapshot does not establish a listing end. A later missing row is descriptive
absence only and is not delisting. The policy cannot create
`listed_since`, `delisted`, a historical interval, a company type, or a
Compounder/backtest output.

Same exact ISIN with different symbols on dated files is retained as distinct
descriptive observations. It creates no rename effective date or
predecessor/successor relationship. Changed ISINs are never stitched from
symbol/name/date similarity. An exact BSE lifecycle ISIN cross-reference is a
separate evidence lineage: BSE delisting dates and compiled-document
observation times cannot supply NSE listing/delisting or NSE known time.

## Deterministic evaluator vocabulary

`evaluate_nse_mii_session_knownness` accepts a proposed policy, one validated
snapshot, one exact row, supplied rows from that same artifact for conflict
checking, a session date, and an existing calendar. It performs no I/O,
persistence, identity lookup, current-master lookup, or runtime-clock call.

| Status | Stable reason / meaning |
| --- | --- |
| `SESSION_IDENTITY_PRESENT` | exact row observed for the same trading session; result retains exact symbol/ISIN/series/security-code/status/type fields and source row/snapshot fingerprints |
| `SNAPSHOT_UNAVAILABLE` | `SNAPSHOT_REQUIRED` or `EXACT_ROW_REQUIRED` |
| `FUTURE_SNAPSHOT` | `FUTURE_SNAPSHOT_EXCLUDED` |
| `WRONG_SESSION` | `LATER_SESSION_REQUIRES_OWN_SNAPSHOT` |
| `INVALID_SOURCE_DATE` | source, row-to-snapshot, or supplied-row validation failed |
| `AMBIGUOUS_CONFLICTED_ROW` | more than one supplied exact security identity row exists |
| `NOT_APPLICABLE` | `EVALUATION_SESSION_NOT_TRADING_DAY` |

Every unavailable/conflicted result has no identity or source-row fields. The
result’s stable serialization includes `historical_known_at: null`; its
fingerprint covers every serialized semantic field. It never includes a
publication timestamp, listing state, eligible/investable field, canonical
instrument ID, portfolio state, company type, or action.

## Existing evidence and descriptive readiness

The official archive path has proven valid samples for `2024-02-05`,
`2025-09-01`, `2025-12-29`, `2026-08-20`, and `2026-08-31`. The known official
failure is `2023-07-03` (404). This proves only sampled availability; archive
status remains `PARTIAL`, and no archive-start date is inferred or crawled.

| Anchor | Valid rows / would-be exact same-session observations | Distinct ISINs | Distinct symbols | Invalid identity rows |
| --- | ---: | ---: | ---: | ---: |
| `2024-02-05` | 24,693 | 11,295 | 10,252 | 58 |
| `2026-08-31` | 37,155 | 16,520 | 16,019 | 60 |

The committed acquisition facts across both anchors are 61,848 immutable row
receipts, 16,154 distinct symbols, 16,662 distinct ISINs, 729 same-ISIN
changed-symbol observations, 11,153 exact ISINs shared by both anchors, 142
earlier-anchor-only ISINs, 5,367 later-anchor-only ISINs, and 52 exact BSE
compulsory-delisted ISIN overlaps. No missing row is a lifecycle conclusion.

## Explicit prohibitions and approval boundary

The proposed policy forbids backward/forward substitution, listing-start/end
or delisting inference, any inferred continuity from changed ISIN/symbol,
publication-time fabrication, company-type classification, and Compounder or
investment eligibility. It does not import `HistoricalSecurityIdentity`, run a
backtest, access a portfolio, create an order, invoke a broker, or change
Holding/Sell/Harvest/Rotation behavior.

`HUMAN_APPROVAL_REQUIRED`: no later work may promote a session observation into
authoritative PIT identity, use it to construct a Compounder backtest universe,
or begin company-type classification until this proposed policy is explicitly
approved and activated through existing governance.

## Residual blocker

`SURVIVORSHIP_RECONSTRUCTION = NOT_READY`. Same-session observations alone do
not create security listing intervals, prove continuity, or establish a
historical universe. The next possible approved work is
`NSE_SESSION_KNOWN_SECURITY_IDENTITY_ACTIVATION_V1`, followed separately by
`PIT_COMPANY_TYPE_CLASSIFICATION_RESEARCH_AND_CONTRACT_V1`.
