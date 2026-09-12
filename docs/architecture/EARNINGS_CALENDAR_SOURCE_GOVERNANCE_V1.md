# Earnings Calendar Source Governance V1

**Status:** `SOURCE_GOVERNANCE_READY / CANDIDATE_CONTRACT_NON_ACTIVE / SOURCE_ADAPTER_NOT_IMPLEMENTED / GATE6_NOT_READY`.

**Research date:** 2026-09-12. This is an official future financial-results board-meeting notice governance slice only. It does not introduce calendar acquisition, persistence, a Gate 6 producer, a blackout-policy change, a provider credential, API/UI, portfolio operation, or order capability.

`V1_ACTIVE=TRUE / V2_ACTIVE=FALSE / V2_SHADOW_ONLY=TRUE` remains unchanged. `NO_UNVERIFIED_CALENDAR_CLEARANCE=TRUE`, `NO_HISTORICAL_RESULT_DATE_AS_FUTURE_SCHEDULE=TRUE`, and `NO_AI_PREDICTED_EARNINGS_DATE=TRUE` remain binding.

## Governing decision

An exchange-distributed issuer filing is eligible only as a **candidate** source under this exact semantic class:

`PRIMARY_EXCHANGE_DISTRIBUTED_COMPANY_FILING`

It proves that the named exchange distributed a filing attributed to the listed company, with retained exchange receipt/dissemination evidence and a declared meeting purpose. It does **not** independently establish the truth of eventual results, their timing, their materiality, or future notice coverage.

```text
official NSE/BSE filing receipt
  -> non-active schedule candidate
  -> future admitted verified-calendar producer
  -> existing Gate 6 input admission
  -> unchanged five-session blackout calculation
```

A candidate is never the future producer. No schedule evidence is not a safe schedule state; it means only that HSI has no admitted schedule evidence. An absence clearance would require a separately approved complete coverage, refresh, revision-feed, identity, non-partial-response, and known-at policy. No arbitrary freshness interval is defined here.

## Pinned primary sources and bounded findings

| Source | Official surface and bounded finding | Candidate use | Not established here |
| --- | --- | --- | --- |
| NSE Board Meetings | [NSE Board Meetings](https://www.nseindia.com/companies-listing/corporate-filings-board-meetings) exposes company/symbol/time-period filters, CSV download, and Board Meeting Details. The [NSE issuer board-meeting surface](https://www.nseindia.com/static/investor-relations/board-meetings) visibly separates subject, announcement date, meeting date and attachment. | A results-purpose notice can identify a future meeting date. | A page row is not a complete all-company or revision feed. |
| NSE Announcements | [NSE Corporate Filings Announcements](https://www.nseindia.com/companies-listing/corporate-filings-announcements) exposes company/subject/time filters and CSV download. | Source/attachment identity and declared purpose may be retained. | The dynamic public page alone is not an approved ingestion protocol. |
| NSE XBRL | [NSE XBRL filing information](https://www.nseindia.com/static/companies-listing/xbrl-information) states that compliance filings are separately submitted to exchanges, and describes NEAPS/XBRL data-entry or file-upload paths. | Structured purpose/reference is preferred when the exact filing supplies it. | XBRL availability does not turn an unverified record into a Gate 6 source. |
| NSE LODR calendar | [NSE Compliance Calendar](https://www.nseindia.com/static/companies-listing/compliance-information-compliance-calendar-main-board) lists Regulation 29 prior-intimation timing and Regulation 33 financial-result timelines, while warning that the calendar is indicative. | Regulatory context only. | It is not a schedule feed or an absence certificate. |
| BSE Board Meetings | [BSE Board Meetings](https://www.bseindia.com/corporates/board_meeting.aspx/board_meeting.aspx) exposes security code/name, purpose and meeting date; its purpose filter distinguishes results from unrelated matters. | A BSE results-purpose row may form a separately retained receipt. | It does not establish NSE/BSE equivalence or a preference between them. |
| BSE Corporate Announcements | BSE official corporate-announcement records retain an exchange received and disseminated time when exposed, as shown by the [BSE corporate-announcement surface](https://m.bseindia.com/MAnnDet.aspx?Form=STR&newsid=15bec8ef-4d88-44f6-bccc-4b0d111db3b3&scrpcd=544176). | Disseminated time is the preferred `known_at`; received time is retained separately. | A browser fetch failure or partial response is not `NO_QUALIFYING_EVENT_FOUND`. |
| BSE structured filing guidance | BSE’s official [XBRL FAQ/notice](https://www.bseindia.com/markets/MarketInfo/DownloadAttach.aspx?attachedId=6b163bb8-fbe3-4e14-be9a-47b99f2cfaaf&id=20250523-40) distinguishes `Original` and `Revision` for XBRL announcements and lists Regulation 29 Prior Intimation for Board Meeting. | Explicit original/revision links may be retained. | Same company/date is never an inferred amendment link. |
| SEBI LODR | [SEBI LODR Regulations, 2015](https://www.sebi.gov.in/legal/regulations/aug-2023/securities-and-exchange-board-of-india-listing-obligations-and-disclosure-requirements-regulations-2015-last-amended-on-august-18-2023-_76364.html) remains the legal source; the NSE calendar says its summary is indicative and directs issuers to the latest regulation. | Regulatory authority for Regulation 29 classification. | This research does not freeze a stale legal text; an activating adapter must re-check the current consolidated regulation. |

The source hierarchy is: exact exchange-distributed company filing with retained first-party reference/identity; structured exchange/XBRL fields where present; attachment text only through bounded deterministic parsing when needed. No commercial calendar, broker feed, finance portal, search snippet, social item, or AI-predicted date participates. Text/attachment AI is only a future escalation aid and can never create canonical schedule authority.

## Qualification, identity and public time

Only a Regulation 29 prior-intimation that explicitly says the board will consider, approve, or take on record quarterly, half-yearly, annual, audited, or unaudited financial results is qualifying. Structured exchange/XBRL purpose values are preferred. The bounded parser accepts only an exact structured results label, or the explicit action plus `financial result(s)` wording. It does not perform semantic completion.

The following do **not** qualify without that explicit results purpose: generic board meetings; fund raise; bonus; dividend; split; rights; buyback; capital action; a historical financial-results filing; a period end; an earnings-call item; or a company calendar assertion.

The adapter must resolve the source security using an exact NSE symbol, BSE security code, ISIN, or already governed effective-dated provider mapping. Names alone are never sufficient. A historical/successor symbol requires effective-date evidence; no fuzzy identity is permitted.

`known_at` is **only** the public exchange dissemination/broadcast timestamp. The exchange-received timestamp is retained separately, but is not substituted for `known_at`. Financial period end, attachment signing date, company internal date, meeting date, HSI receipt time, and a later revision cannot backdate public knowledge. If the source gives only a date, the field is `DATE_ONLY`; no midnight, market-open, close, or timezone is invented. PIT selection is exactly `known_at <= as_of`.

## Non-active immutable candidate contract

`app/gates/official_earnings_schedule_candidate.py` defines the pure immutable `OfficialEarningsScheduleCandidate` contract. It is not registered with a repository, adapter, authority, engine, API, UI, or `GateInput`.

| Contract field group | Exact rule |
| --- | --- |
| Deterministic receipt identity | `schedule_id` is derived from contract version, canonical instrument, event/purpose/date/time/precision, scope/period reference, exchange filing identity, lifecycle/revision link, and source fingerprint. It distinguishes a duplicate receipt, revision, and a second meeting with a different purpose. |
| Canonical/source identity | Canonical instrument plus source identifier kind/value (`NSE_SYMBOL`, `BSE_SECURITY_CODE`, or `ISIN`) are mandatory. `EXACT_CANONICAL_IDENTITY` is the sole candidate state. |
| Event/purpose | Event type is only `FINANCIAL_RESULTS_BOARD_MEETING`; a qualifying purpose classification and verbatim declared purpose are mandatory. |
| Schedule time | A `date` is mandatory. `DATE_ONLY` requires no time. `DATE_TIME` requires an explicit source clock string and remains descriptive; it is not converted into an invented UTC instant. |
| First-party source lineage | Exchange, authority class, Regulation 29 announcement type, source reference, filing identity, optional attachment/XBRL references, source fingerprint, policy id/version, and content fingerprint are retained. |
| Public-time lineage | Optional exchange receipt, mandatory exchange dissemination, `known_at == dissemination`, and HSI receipt are separate. HSI receipt cannot precede public dissemination. |
| Lifecycle | `ANNOUNCED`, `REVISED`, `RESCHEDULED`, `CANCELLED`, `SUPERSEDED`, and `COMPLETED` are descriptive only. Revised/rescheduled/cancelled/superseded records require explicit `revision_of_schedule_id`; same company/date matching is forbidden. |
| Admission state | Fixed to `UNVERIFIED_SOURCE_AUTHORITY`; no constructor field can promote it. |

The companion reconciliation view considers only receipts public at its `as_of`. It retains both NSE and BSE receipts and returns a one-exchange candidate, dual-exchange agreement, `EVIDENCE_CONFLICTED`, or `PIT_NOT_VISIBLE`. It never chooses NSE over BSE, silently deduplicates an identical receipt, or discovers a revision by similarity. All source rows must be append-only in a future adapter; this contract has no persistence.

### Failure vocabulary for the future adapter

The eventual adapter must preserve, rather than collapse to “no earnings”, the following source outcomes: `NO_QUALIFYING_EVENT_FOUND`, `SOURCE_QUERY_FAILED`, `SOURCE_PARTIAL`, `IDENTITY_UNRESOLVED`, `EVENT_PURPOSE_AMBIGUOUS`, `EVIDENCE_CONFLICTED`, `REVISION_LINEAGE_UNRESOLVED`, and `FRESHNESS_UNPROVEN`.

`NO_QUALIFYING_EVENT_FOUND` is permitted only after a separately approved complete source query. A failure, partial response, missing identity, or unproven freshness remains distinct and fail closed.

## Revision, dual-exchange and coverage policy

An official original/revision marker is retained verbatim in lifecycle. Where a later official update lacks structured original/revision linkage, the future adapter must require an explicit source amendment reference to a prior filing identity. It cannot infer a link from same company, same date, or similar wording. Missing or competing links are `REVISION_LINEAGE_UNRESOLVED` or `EVIDENCE_CONFLICTED`.

NSE and BSE receipts stay independent. A reconciled view is possible only if canonical identity, qualified purpose, scheduled date/time precision, scope, and financial-period reference agree. Conflicting dates or purposes without explicit lineage are conflicted. One exact exchange receipt can remain descriptive only if the future coverage policy permits; no undocumented source preference is created.

No expiry/staleness duration is introduced. Freshness is blocked until the adapter proves successful bounded query completion, identity coverage, revision-aware search window, `known_at`/receipt retention, and non-partial response. No schedule evidence therefore cannot clear Gate 6.

## Bounded read-only feasibility probe

This audit performed no source query, ingestion, attachment fetch, historical crawl, database write, or runtime activation. Production SQLite was opened read-only with `query_only=ON`.

| Probe | Result |
| --- | --- |
| Current canonical financial population | 31 instruments, 6,118 `financial_facts`; the same 31 instruments have corporate filings. |
| Existing filing inventory | 455 records: 425 BSE `FINANCIAL_RESULTS`, 30 NSE `SHAREHOLDING_PATTERN`. |
| Existing schedule metadata | 0 `board_meeting_date`, 0 `board_meeting` payloads, 0 retained timestamp-evidence payloads. |
| Existing revision evidence | 11 existing filing revision links, but none is a results-schedule lifecycle feed. |
| Exact source-identity/board/purpose/revision coverage | `NOT_QUERIED`: no approved NSE/BSE schedule adapter exists, so a 31-company external probe would not be a governed query. |
| Official surface semantics | NSE/BSE pages demonstrate future board-meeting dates and explicit results purposes; BSE announcement records demonstrate received/disseminated time exposure. |

The stored financial-result corpus cannot be reinterpreted as future schedules. It lacks board-purpose metadata and public-time semantics.

## Readiness and next boundary

| Domain | State | Reason |
| --- | --- | --- |
| Source governance | `READY` | Exact source class, purpose, identity, PIT, date precision, revision, dual-exchange, and failure semantics are specified. |
| Candidate contract | `READY_NON_ACTIVE` | Immutable deterministic fixture-only contract; no persistence or authority admission. |
| Source adapter | `NOT_READY` | No official NSE/BSE acquisition/query implementation exists. |
| Current data coverage | `NOT_READY` | The current corpus has no schedule metadata or verified future notices. |
| Freshness coverage | `POLICY_BLOCKED` | No complete response/revision/coverage policy or successful feed exists. |
| Revision handling | `PARTIAL` | Candidate linkage is specified; no source adapter preserves live original/revision feeds. |
| Gate 6 integration | `NOT_READY` | Existing policy and five-session arithmetic remain frozen; no candidate is admitted. |

Final feasibility: **`OFFICIAL_SOURCE_FEASIBLE_WITH_POLICY_GAPS`**.

The exact one next task is `OFFICIAL_NSE_BSE_EARNINGS_CALENDAR_ADAPTER_V1`. It must implement only a bounded official-source adapter and coverage receipt against this contract, then prove revision/cancellation, PIT, source-failure, and identity behavior before any separate Gate 6 admission decision. It may not activate the existing blackout policy merely by creating candidate rows.

## Validation and safety

`tests/unit/test_official_earnings_schedule_candidate.py` covers explicit results qualification; secondary-source rejection; exact identity; date-only precision; dissemination-based `known_at`; PIT exclusion; UTC-normalized serialization; revision/cancellation links; dual-exchange agreement/conflict; duplicate receipt rejection; tamper detection; and static no-storage/network/clock/execution boundaries. Existing filing, timestamp-provenance, and Gate-source-authority tests retain pre-existing non-admission behaviour.

No source adapter, database schema/migration, stored schedule event, Gate 6 logic/policy, source-readiness descriptor, provider integration, trade plan, portfolio operation, broker/order call, or credentials were changed.
