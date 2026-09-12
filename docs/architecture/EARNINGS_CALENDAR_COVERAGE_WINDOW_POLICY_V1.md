# Earnings Calendar Coverage / Window Policy V1

**Status:** `CURRENT_5_SESSION_BLACKOUT_INCOMPATIBLE_WITH_AUTHORITATIVE_NOTICE_LEAD_TIME / COVERAGE_AND_FRESHNESS_NOT_ACTIVE / GATE6_NOT_READY / NON_EXECUTABLE`.

This bounded policy slice follows [known-at semantics](EARNINGS_CALENDAR_KNOWN_AT_SEMANTICS_V1.md), [canonical identity](EARNINGS_CALENDAR_CANONICAL_IDENTITY_BRIDGE_V1.md), and the bounded [official NSE/BSE adapters](OFFICIAL_NSE_BSE_EARNINGS_CALENDAR_ADAPTER_V1.md). It adds a pure receipt contract in [earnings_schedule_coverage.py](../../app/filings/earnings_schedule_coverage.py), with no collector, persistence, adapter query, Gate 6 wiring, blackout change, API/UI, portfolio, broker, order, or AI activity.

Frozen controls remain: `V1_ACTIVE=TRUE`, `V2_ACTIVE=FALSE`, `V2_SHADOW_ONLY=TRUE`, `B08=CLOSED_FOR_ACTIVATION_COMPATIBILITY`, `CURRENT_EARNINGS_IDENTITY=READY`, `NO_TIMEZONE_GUESS=TRUE`, `NO_UNVERIFIED_CALENDAR_CLEARANCE=TRUE`, and `NO_AI_PREDICTED_EARNINGS_DATE=TRUE`.

## Primary-source regulatory finding

The current NSE Main Board compliance calendar (updated 2025-10-24) describes Regulation 29 prior intimation of a board meeting as **at least two working days in advance**, excluding both the intimation date and meeting date. Its table expressly directs issuers to the current consolidated LODR regulations because the calendar is indicative. [NSE Compliance Calendar](https://www.nseindia.com/static/companies-listing/compliance-information-compliance-calendar-main-board)

This is a working-day rule, not a five-trading-session rule. It does not promise that a results-meeting notice exists at `T-5` sessions. Therefore a Regulation 29 notice alone cannot guarantee the existing five-session Gate 6 horizon. The current Gate 6 policy remains unchanged and unwired.

Regulation 33's 45-day quarterly / 60-day final-quarter result-filing deadlines are a broad reporting-season context only; they do not prove a board-meeting date, public knowledge of one, or an earnings schedule. [NSE Compliance Calendar](https://www.nseindia.com/static/companies-listing/compliance-information-compliance-calendar-main-board)

### Historical replay guard

Historical timing must use the version effective at the historical point, never the current rule by default. SEBI's 2020 COVID circular records the then-existing Regulation 29(2) split: five days for results meetings and two working days in other cases, with a temporary reduction to two days for covered meetings through 2020-07-31. [SEBI circular dated 2020-04-17](https://www.sebi.gov.in/sebi_data/attachdocs/apr-2020/1587109438485.pdf)

This slice does not derive a full effective-date table or replay engine. In particular, an activating historical policy must retain a regulation/version/effective-date lineage for every claimed notice horizon; no current two-working-day rule may be applied retroactively, and no old five-day rule may be assumed current.

## Official-source window matrix

`CAN_QUERY` describes the currently bounded, documented implementation/evidence surface. It is not a claim that a public page's HTTP success proves a complete query.

| Source family | Can query by exact instrument? | Can query by date window? | Pagination provable? | Window completeness provable? | Positive event discovery | Negative absence proof |
| --- | --- | --- | --- | --- | --- | --- |
| `NSE_EVENT_CALENDAR` | `UNPROVEN` | `UNPROVEN` | `UNPROVEN` | `NO` | `PARTIAL` only when an exact official row is retained | `NO` |
| `NSE_BOARD_MEETINGS` | `PARTIAL`; current RSS has no exact retained identifier in the canary | `NO`; rolling RSS only | `NO` | `NO` | `YES`, subject to exact identity/purpose/PIT admission | `NO` |
| `NSE_ANNOUNCEMENTS` | public filter surface observed; governed complete query protocol not proved | public time filter surface observed; scope/pagination not proved | `UNPROVEN` | `NO` | `PARTIAL`, subject to exact filing admission | `NO` |
| `NSE_PRIOR_INTIMATION_XBRL` | direct linked document only | `NO` broad inventory | `NO` | `NO` | `YES` for one exact linked, qualifying document | `NO` |
| `BSE_BOARD_MEETINGS` | `UNPROVEN`; observed page is an application shell | `UNPROVEN` | `UNPROVEN` | `NO` | `NOT_PROVED` as a current discovery feed | `NO` |
| `BSE_ANNOUNCEMENTS` | direct mobile detail can be parsed only after a known link | `NO` governed current discovery feed | `NO` | `NO` | `YES` for a retained exact qualifying detail | `NO` |

The prior bounded adapter canary found a 12-item rolling NSE RSS inventory and no BSE discovery inventory; it did not apply its requested window and resolved no individual source identity. Those observations remain useful positive-discovery archaeology, not coverage evidence. See [adapter record](OFFICIAL_NSE_BSE_EARNINGS_CALENDAR_ADAPTER_V1.md).

## Coverage receipt contract — non-active

`EarningsScheduleCoverageReceipt` is immutable and deterministically identifies one source-window query through contract/version, canonical instrument, source family, window, query filter semantics, UTC query completion instant, and ordered response fingerprints. Its content fingerprint covers every serialised field. Empty, duplicate, cross-category, unordered, or malformed lineage is rejected.

| Bound field / state | V1 rule |
| --- | --- |
| Source scope | One of `NSE_EVENT_CALENDAR`, `NSE_BOARD_MEETINGS`, `NSE_ANNOUNCEMENTS`, `NSE_PRIOR_INTIMATION_XBRL`, `BSE_BOARD_MEETINGS`, `BSE_ANNOUNCEMENTS`. |
| Exact identity/window | Canonical instrument plus inclusive `window_start`/`window_end`; no name matching. |
| Filter semantics | `EXACT_INSTRUMENT_AND_DATE_WINDOW` or `SOURCE_SCOPE_UNPROVEN`; only the former can participate in `COMPLETE`. |
| Query lineage | UTC `query_completed_at`, ordered response fingerprints, qualifying/non-qualifying/ambiguous row references, query status, and an error code only for `FAILED`. |
| Completeness checks | `pagination_complete`, `identity_scope_complete`, and `revision_scope_complete` are all mandatory for `COMPLETE`; any unproved item prevents it. |
| Coverage state | `COMPLETE`, `PARTIAL`, `FAILED`, `UNPROVEN`, or `CONFLICTED`. An ambiguous row makes the result `CONFLICTED`. |
| Absence state | `QUALIFYING_EVENT_FOUND`, `NO_QUALIFYING_EVENT_FOUND_COMPLETE_WINDOW`, `NO_QUALIFYING_EVENT_FOUND_INCOMPLETE_WINDOW`, `SOURCE_QUERY_FAILED`, `IDENTITY_UNRESOLVED`, `WINDOW_UNPROVEN`, or `EVIDENCE_CONFLICTED`. |
| Authority | Always `WATCH_ONLY / NON_EXECUTABLE`; `gate6_clearance` is hard-coded `false`. |

`COMPLETE` means all of the following, for one source family: exact canonical identity; source evidence that the exact date window and filter were applied; successful query; pagination completion; complete identity scope; revision/cancellation scope; retained response fingerprints; no conflicting/ambiguous result; and no source failure. It does **not** mean that another exchange has been queried, that a legal notice must have existed by any earlier horizon, or that a trade can clear Gate 6.

## Positive and negative evidence

An official, exact-identity, results-purpose schedule whose prospective `known_at` is valid can eventually support a **blocking** input. The current receipt does not promote one; it only preserves row lineage.

`NO_QUALIFYING_EVENT_FOUND_COMPLETE_WINDOW` is merely a candidate negative-evidence fact. It never clears Gate 6. Any incomplete, failed, unproven, identity-unresolved, stale, or conflicted query is distinct from absence and stays fail closed. A cancelled notice is not absence proof.

The sources inspected do not prove that a single exchange gives universal absence coverage for a dual-listed issuer. Regulation/disclosure obligations may be exchange-specific, and a delayed or incomplete surface cannot be assumed equivalent. Dual-exchange corroboration can improve evidence, but a two-exchange requirement is not adopted here without separate legal/source proof.

## Freshness and prospective collection

The separate vocabulary is `FRESH`, `STALE`, `UNPROVEN`, and `SOURCE_FAILED`. V1 permits only `UNPROVEN` for a nonfailed receipt and `SOURCE_FAILED` for a failed receipt. It deliberately does not construct `FRESH` or `STALE`: no documented exchange update cadence, complete query interval, liveness bound, or revision-feed behaviour justifies an arbitrary duration.

A future collector may create a `SystemCoverageFirstObservedReceipt` only at an automatic ingestion boundary. It binds the exact query identity, response fingerprints, UTC first observation instant, ingestion run identity, and monotonic run sequence. It is not a claim of the public-market first-known instant. A future activation must make collector liveness/failure observable; a dead collector cannot yield a negative clearance. This contract selects no poll frequency.

## Gate 6 research decision

| Proposed behaviour (not activated) | Coverage/policy result |
| --- | --- |
| Verified positive schedule + inside existing blackout | Future `BLACKOUT / WAIT` candidate only after a separately admitted producer. |
| Verified positive schedule + outside blackout | Descriptive schedule only; no clearance or entry authority. |
| No schedule + complete fresh coverage | Candidate negative evidence only; no Gate 6 clearance policy exists. |
| No schedule + incomplete/unproven coverage | `UNKNOWN / UNVERIFIED`, never `ENTRY_READY`. |
| Source failure or stale coverage | `SOURCE_QUERY_FAILED` / future `STALE`; fail closed. |
| Conflicting schedule or unknown known-at | `EVIDENCE_CONFLICTED` / `PIT_UNPROVEN`; fail closed. |

The three policy families remain mutually distinct:

| Model | Finding |
| --- | --- |
| A — retain five sessions and require an earlier authoritative source | Not demonstrated by this source audit. |
| B — retain five sessions and fail closed until a notice exists | May be conservative, but needs a separate practicality/usability and entry-policy decision. |
| C — version the blackout horizon to a source-realistic notice window | Material policy, calibration, and strategy-versioning change; not implemented here. |

The dominant result is **C**: current authoritative Regulation 29 notice timing is not sufficient to guarantee a notice at five sessions. This says nothing about whether an issuer sometimes announces earlier; that is not a universal official coverage guarantee.

## Read-only 31-company feasibility audit

The audit opened `data/nse_stock_manager.db` read-only. Current stored facts cover 31 instruments (6,118 `financial_facts`) and 455 corporate filings. There are no production `earnings_schedule_*` tables, zero non-null board-meeting/schedule metadata in the filing payloads, and no admitted current schedule evidence. The prior identity receipt establishes 31/31 current NSE and BSE identities, but identity alone does not make a source-window query complete.

| Measure | Result |
| --- | ---: |
| Identities eligible for a future exact query | 31 / 31 NSE; 31 / 31 BSE |
| Current admitted positive schedule records | 0 |
| Current persisted complete-window receipts | 0 |
| Current persisted partial-window receipts | 0 |
| Current audit query failures | 0; no live source query was run |
| Known-at-ready positive evidence | 0 |
| Negative-absence proof capability | 0 |

## Validation and exact continuation

Focused tests cover source-family enumeration, complete/partial/failed/unproven/conflicted windows, positive versus absence states, automatic prospective observation, UTC replay, lineage tampering, forbidden freshness fabrication, deterministic serialisation, and static no-Gate/no-network/no-database/no-execution boundaries. The [machine receipt](EARNINGS_CALENDAR_COVERAGE_WINDOW_POLICY_V1_RECEIPT.json) records the immutable audit result and policy outcome.

`EARNINGS_CALENDAR_COVERAGE_WINDOW_POLICY_V1` result:

`CURRENT_5_SESSION_BLACKOUT_INCOMPATIBLE_WITH_AUTHORITATIVE_NOTICE_LEAD_TIME`

Exact next continuation, not started: `EARNINGS_BLACKOUT_HORIZON_POLICY_RESEARCH_V1`.
