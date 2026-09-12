# Official NSE/BSE Earnings Calendar Adapter V1

Status: `IMPLEMENTED_BOUNDED_ADAPTERS / LIVE_COVERAGE_PARTIAL / CANDIDATES_NON_ACTIVE / GATE6_NOT_READY`.

This slice implements the [approved source governance](EARNINGS_CALENDAR_SOURCE_GOVERNANCE_V1.md), not calendar clearance. The [machine-readable acquisition receipt](OFFICIAL_NSE_BSE_EARNINGS_CALENDAR_ADAPTER_V1_RECEIPT.json) records the 2026-09-12 observations and the protected production baseline. Frozen state remains `V1_ACTIVE=TRUE / V2_ACTIVE=FALSE / V2_SHADOW_ONLY=TRUE / B08=CLOSED_FOR_ACTIVATION_COMPATIBILITY`. No Gate 6 producer is registered and no five-trading-session arithmetic changes.

## Public transport archaeology

| Surface | Actual host observation | Admission and limit |
| --- | --- | --- |
| [NSE Board Meetings](https://www.nseindia.com/companies-listing/corporate-filings-board-meetings) | HTTP 200 HTML, publicly links the Board Meetings RSS. | Public page only; no private JSON API inspected or used. |
| [NSE RSS documentation](https://www.nseindia.com/static/rss-feed) and [published RSS](https://nsearchives.nseindia.com//content/RSS/Board_Meetings.xml) | HTTP 200 XML; rolling inventory of 12 items during the canary. Item fields are title, link, description and pubDate. | Public downloadable RSS, no credentials/cookies used. No documented date filter, pagination completion or revision coverage established. Always `SOURCE_PARTIAL`. Feed TTL is not adopted as HSI freshness policy. |
| Direct prior-intimation XML linked by RSS | One bounded archaeology sample returned an XBRL instance with NSESymbol, ISIN, company, meeting type, intimation type, proposed date and Agenda1, using the observed 2023-05-31 namespace. | Explicitly selected linked XML only, no automatic attachment crawl. Sample was Amalgamation, not a results schedule. No broadcast timestamp in the XML. |
| [BSE Board Meetings](https://www.bseindia.com/corporates/board_meeting.aspx) | HTTP 200 after same-host redirect to `/corporates/board_meeting`, 14,287-byte application shell. Announcements page returned the same checksum. | HTTP success is not query success. `SOURCE_TRANSPORT_NOT_READY`. No undocumented backend endpoint was reverse-engineered. |
| [BSE public detail already cited in governance](https://m.bseindia.com/MAnnDet.aspx?Form=STR&newsid=15bec8ef-4d88-44f6-bccc-4b0d111db3b3&scrpcd=544176) | HTTP 200 HTML with security code, company, exchange receipt/dissemination, subject and exact meeting-date phrase. | A public detail parser is implemented. This historical reference establishes markup only, not current 31-company coverage. No current bounded discovery list of detail identities was obtained. |

Transport uses exact observed HTTPS paths and exact host checks, verified TLS, ten-second socket/read deadline checks, at most two redirects, a 2 MiB decoded-input bound, at most 128 RSS items, no cookies, credentials or automatic retries. Compression other than identity is refused. Redirects are revalidated. Transport operational timing is separate from canonical timestamps. No rate-limit response was observed in these sequential low-volume probes; this is not proof of a published rate entitlement. No broad crawl, source-IP bypass, browser automation, commercial feed or AI is used.

## Implementation and reproducibility

- [Source adapters and parsers](../../app/filings/earnings_schedule_source.py): injected transport, immutable raw relevant fields, per-artifact checksum, source status, parser versions and `official-results-purpose/v1` receipt. RSS items are not mapped by company title. PDF links are retained descriptively, not fetched or interpreted. The BSE parser consumes observed `resultgreyhead/resultleft`, `ann01/ann02` cells and exact `is scheduled on DD/MM/YYYY` wording; missing/duplicate/changed layouts fail closed. Unknown XBRL agendas/duplicate fields fail closed, rather than dropping potentially relevant data.
- [Normalization](../../app/filings/earnings_schedule_ingestion.py): reuses `resolve_historical_security_identity` and `resolve_filing_timestamp`. Supplied immutable historical identities must match exact source symbol/security code, canonical ISIN, source provenance and effective time at public `known_at`. No current-symbol fallback or name matching. No timezone rules are introduced by this slice.
- [Dedicated immutable store](../../app/filings/earnings_schedule_store.py): explicitly constructed versioned `earnings_schedule_candidates_v1`, `earnings_schedule_conflicts_v1`, and `earnings_schedule_coverage_v1` tables. Construction is not wired into the production runtime. Isolated SQLite tests only; no production migration or schedule writes occurred.
- [Candidate contract](../../app/gates/official_earnings_schedule_candidate.py): reused with narrow validation/reconciliation repairs. ID ordering is now canonical independent of exchange ordering; source exchanges are unique. Qualified purpose, not raw textual wording, is compared. Distinct same-source filing identities retain independent lineage even when they agree. Source enums and visible candidates are revalidated. Cancellation cannot corroborate an active notice. Identity/fingerprint formulas and admission state are unchanged.

Generic `BoardMeetingMetadata` stores a datetime rather than lossless date-only/public-time/revision semantics; the current generic snapshot-family enum has no exact schedule family. Forcing either representation would lose semantics or expand unrelated runtime contracts. The dedicated store therefore creates only its own bounded versioned schema when explicitly instantiated; no broad migration is needed or performed.

### Purpose, timestamps and precision

The versioned classifier accepts exact results labels, including hyphen-normalized half-yearly labels and `Financial Results / Dividend`. Generic purpose plus one explicit affirmative bounded consider/approve/take-on-record financial-results clause can qualify. Non-results labels, conditional/negative language, unrelated historical results and ambiguous text cannot be completed by inference. It retains raw purpose/details, matched rule, version and source fingerprint. It does not change the older standalone classifier; acquisition uses this independently versioned stricter classifier.

`known_at` must resolve from the raw exchange dissemination/broadcast field. Current NSE `pubDate` and BSE detail-field values lack explicit timezone evidence. The RSS channel offset or BSE footer `(IST)` does **not** define the item/filing field timezone. Existing governed field-specific timezone rules may be injected when separately evidenced; none was created here. Missing/unresolved publication time yields `TIMESTAMP_UNAVAILABLE`. Receipt time, meeting date, financial period, HTTP date and HSI observation time cannot substitute. Exchange receipt is retained separately. DATE_ONLY always has `scheduled_time=None`; no scope, reporting period or meeting clock is invented.

### Revisions, conflict and replay

Observed parser formats do not establish an exact original-filing link for every amendment. Revision/reschedule/cancellation wording therefore yields `REVISION_LINEAGE_UNRESOLVED` rather than inferred linkage. The store supports explicit linked candidate mechanics: same instrument/exchange, strictly later public time, existing parent, no mutation of original; independent revisions of one parent conflict. Fixture-only linked lifecycle tests are not live lifecycle-source proof.

Exact source-filing replay is `IDENTICAL`: a changed HSI retrieval timestamp alone does not duplicate canonical evidence. Changed immutable filing content is preserved in the conflict table with incoming payload/raw lineage and never overwrites the old candidate. The conflict becomes visible at its HSI observation time, not at a potentially backdated changed claim. Both variants remain auditable. Coverage replay is also idempotent.

`effective_schedule_as_of(instrument, as_of)` reads only public candidates with `known_at <= as_of`. A later linked revision/cancellation cannot affect the earlier view. Agreement retains every independent source receipt. Date/purpose/scope/precision disagreement fails closed, with no earliest/latest/NSE/BSE preference. A cancelled candidate is descriptive, never absence clearance. No date-passed completion rule exists. All candidates remain `UNVERIFIED_SOURCE_AUTHORITY`; all query views have `gate_eligible=False`.

## Current 31-company canary

The requested bounded inspection window was 2026-08-29 through 2026-10-27 (inspection control, **not** an expiry/freshness/investment policy). Neither source applied that window. One NSE rolling-feed request and one BSE discovery-page request were performed after focused fixture validation. No per-company endpoint or attachment fan-out was used.

| Measure | NSE | BSE |
| --- | ---: | ---: |
| Canonical population requested | 31 | 31 |
| Source-level HTTP requests / HTTP successes | 1 / 1 | 1 / 1 |
| Complete window-query successes | 0 | 0 |
| Individually queried/resolved identities | 0 / 0 | 0 / 0 |
| Source inventory rows | 12 | 0 |
| Explicit results-purpose / non-results / ambiguous inventory rows | 1 / 3 / 8 | 0 / 0 / 0 |
| Exact identifier fields in inventory rows | 0 | 0 |
| Date-only / raw public-time values | 12 / 12 | 0 / 0 |
| Exact timezone-proven public timestamps | 0 | 0 |
| Materialized canonical schedule candidates | 0 | 0 |
| Completed canonical evidence coverage | 0 / 31 | 0 / 31 |

The single explicit results-purpose RSS row is an **unmapped inventory row**, not evidence for any of the 31 companies. All 31 remain coverage-unproven. APARINDS, DEEPINDS, GENUSPOWER and GLAND have the same exact blocker: no exact current source identity/dissemination-bound schedule was acquired; absence is not asserted. The database contains 201 historical identity snapshots in total, but their existence is not a substitute for the source identifiers missing from the RSS.

Live dual-exchange matches, canonical conflicts, admitted revisions/reschedules/cancellations and materialized records are all zero because no canonical candidates passed admission preconditions. Their absence is not evidence that the market has none. A real non-results example is the RSS `Fund Raising` label. A real multiple-purpose row is `Fund Raising/Other business matters`, conservatively ambiguous in v1. No results/dividend, dual-exchange or successful source-no-record example was manufactured. BSE's shell is the observed discovery-unavailable case, not `SUCCESS_NO_QUALIFYING_ROWS`.

Coverage receipts distinguish requested population, individually queried identities, HTTP versus complete-query success, unapplied window, inventory counts, source errors/checksums, retrieval time, and missing last complete query. They always retain `freshness=POLICY_BLOCKED` and `gate6_clearance=false`.

## Readiness matrix

| ID | Domain | State | Exact boundary |
| --- | --- | --- | --- |
| A | NSE_SOURCE_TRANSPORT | PARTIAL | Published RSS and linked XML fetched; rolling inventory is not complete company/window coverage. |
| B | BSE_SOURCE_TRANSPORT | PARTIAL | Public detail works; board discovery returns shell, no approved current detail inventory. |
| C | NSE_PARSER | PARTIAL | Observed RSS/Reg29 XML supported; missing feed identifiers/timezone and unsupported extra agendas remain closed. |
| D | BSE_PARSER | PARTIAL | Observed mobile detail supported; no stable admitted current discovery parser or complete revision feed. |
| E | FINANCIAL_RESULTS_CLASSIFICATION | READY | Exact/bounded versioned rules tested; all ambiguity retained. |
| F | SECURITY_IDENTITY | PARTIAL | Existing effective identity resolver reused/tested; 0 live schedule identities resolved. |
| G | SOURCE_KNOWN_AT | PARTIAL | Raw values retained; 0 current source item timestamps timezone-proven. |
| H | DATE_PRECISION | READY | 12 observed date-only entries; no fabricated time. |
| I | REVISION_LINEAGE | PARTIAL | Explicit append-only store mechanics tested; live parent linkage unproven. |
| J | CANCELLATION_RESCHEDULE | PARTIAL | Prospective linked mechanics tested; no admitted live transition. |
| K | DUAL_EXCHANGE_RECONCILIATION | PARTIAL | Deterministic agreeing/conflicting fixtures pass; 0 live corroborations. |
| L | IMMUTABLE_STORAGE | READY | Dedicated versioned store, isolated reopen/replay/conflict tests; production untouched. |
| M | PIT_SELECTION | READY | Source-time filtering and future-revision exclusion in isolated tests. |
| N | COVERAGE_RECEIPT | READY | Deterministic truthful partial/error/HTTP/query distinctions; no absence certificate. |
| O | SOURCE_FRESHNESS | POLICY_BLOCKED | No complete feed or approved freshness policy. |
| P | CURRENT_31_COMPANY_COVERAGE | NOT_READY | 0/31 canonical schedules, all coverage-unproven. |
| Q | GATE6_INTEGRATION | NOT_READY | Deliberately unwired; no calendar clearance or policy change. |

## Validation and protected state

Final focused validation: **90 passed**. Affected Gate/filing/timestamp/historical-identity bundle: **211 passed / 2 warnings**; the subsequent final date-only publication guard is covered by the focused and full runs. Exactly one complete backend run: **4,290 passed / 0 failed / 6 skipped / 2 warnings**, exit 0, 331.56 seconds. The two warnings concern existing Starlette/httpx and AnyIO deprecations. Tests cover transport and URL bounds, source failures, malformed XML/DTD rejection, observed parsers, purpose/version, exact effective identities, unresolved timestamps, date precision, PIT, revisions/cancellations, conflicting forks, dual-source reconciliation, replay, immutable-source conflicts, reopen and static safety. Production SQL is read-only; only isolated test stores create schedule tables.

Protected before/after counts and deterministic row fingerprints are recorded in the machine receipt. Required unchanged baseline: FinancialFacts 6,118; CorporateFilings 455; portfolio snapshots 1; canonical definitions 1/results 2,074; generic strategy/results 0; paper trades/trade plans 0; generic/canonical gate evaluations 0. No broker/order operations, acquisition resume, fundamental ingestion or portfolio mutation is performed.

Final read-only SQLite integrity: **ok**; FK violations: **0**. Every protected count and row fingerprint matched again after the complete suite. Cash remains `UNKNOWN`; production schedule tables remain absent. Markdown validation checked **256 local links**, with no broken targets; edited-document/source whitespace and `git diff --check` passed. The five application/test file hashes were unchanged across the full run. No full-suite rerun was needed.

## Exact next continuation

`OFFICIAL_NSE_BSE_EARNINGS_CALENDAR_ADAPTER_REPAIR`

Obtain a publicly documented stable BSE current discovery route, prove exact NSE/BSE source-identity/timezone semantics and explicitly linked revision fields, then repeat bounded coverage validation. Do not guess private routes or create a timezone/freshness assumption. This next task is **not started**. Freshness policy and Gate 6 admission cannot be claimed merely because bounded parsers/stores pass fixtures.
