# Official NSE/BSE Earnings Calendar Discovery Repair

Status: `IMPLEMENTED_BOUNDED_SOURCE_JOIN_REPAIR / LIVE_COVERAGE_NOT_READY / CANDIDATES_NON_ACTIVE / GATE6_NOT_READY`.

This is a source-discovery/join extension of the [V1 adapters](OFFICIAL_NSE_BSE_EARNINGS_CALENDAR_ADAPTER_V1.md), under [source governance](EARNINGS_CALENDAR_SOURCE_GOVERNANCE_V1.md). The previous receipt remains historical and immutable; this [repair receipt](OFFICIAL_NSE_BSE_EARNINGS_CALENDAR_ADAPTER_REPAIR_RECEIPT.json) records the new inspection. Baseline: `018d28e0a8a3666093c070d40f08a0b16e67fea5`, main, clean.

Frozen: `V1_ACTIVE=TRUE / V2_ACTIVE=FALSE / V2_SHADOW_ONLY=TRUE / B08=CLOSED_FOR_ACTIVATION_COMPATIBILITY`. No authority registry, five-session blackout, Gate 6 integration, freshness/absence policy, runtime, credentials, schema, financial ingestion or portfolio change is made.

## Exact public source findings

| Surface | Measured evidence | Admission / remaining boundary |
| --- | --- | --- |
| [NSE Board Meetings](https://www.nseindia.com/companies-listing/corporate-filings-board-meetings) | HTTP 200; Company/Meeting controls and Equity/SME Download links. Both download controls have `href="#"` and empty `data-url`. Only the RSS is a directly exposed data link in the retrieved representation. | CSV **not admitted**: no actual public download URL or usable company/window submission protocol was established. No hidden/client API was reverse-engineered. This is a measured retrieval limitation, not a claim that NSE never offers CSV. |
| [Published NSE RSS](https://nsearchives.nseindia.com//content/RSS/Board_Meetings.xml) | 12 rolling rows; six exact Prior Intimation XML links. Each of those six documents was fetched once in the final canary. | Bounded discovery assistance. PDF links are retained but not fetched/interpreted. No complete pagination, source-applied date window or individual-company query protocol. |
| Exact RSS-linked Reg29 XBRL | Six successful parses, five distinct symbol/ISIN pairs. Explicit fields include symbol, ISIN, meeting/intimation type, proposed date, multiple numbered agendas, report date; the results example additionally supplies audit basis, scope and reporting-period type/month/year. | Source-side identity is now measurable; it is not automatically canonical identity. All six linked documents concern companies outside the requested 31. |
| [NSE public iXBRL WEB representation](https://nsearchives.nseindia.com/corporate/ixbrl/PRIOR_INTIMATION_75266_12012026173231_iXBRL_WEB.html) | Historical **markup-only** sample: public HTML table, not inline-XBRL fact tags. Exact labels expose reschedule type/reason, original/proposed dates, report date, financial-results agenda, audit basis, scope and period. | Exact observed table parser, not generic HTML inference. This sample is **not** a current canary event or ingested schedule. Original date/reason prove intent, not an exact parent-filing identity. |
| [BSE public recent corporate list](https://m.bseindia.com/corporates.aspx) | HTTP 200, ten exact mobile announcement links using published `newsid/flag/type/scrip_CD` query keys. Current list has zero Board Meeting Intimation headlines. | Admitted **partial recent discovery**, not complete board-meeting coverage. Existing exact mobile detail parser supports this observed query variant and the legacy `Form/newsid/scrpcd` variant. No unrelated announcement details were fetched. |
| BSE desktop shell | Prior measurement retained; not queried again. | No repair loop around the shell. Empty/shell mobile discovery returns `SOURCE_DISCOVERY_NOT_READY`, never no-event success. |

The website's market-snapshot “IST” clock does not define Board Meetings publication fields. Neither the RSS item timestamp nor the observed BSE dissemination label proves a timezone. No timezone rule was created. The iXBRL Date of Report remains a report date, never public `known_at`.

Requests remain HTTPS-only with verified certificates; fixed public route allowlist; 2 MiB response bound; ten-second socket/read deadline checks; no cookies, credentials or retries. The final canary used eight sequential requests, one-second spacing between document requests, a maximum of eight linked documents, and no historical crawl. Earlier bounded archaeology is separately identified in the receipt, not counted as current acquisition.

## Bounded repair and exact joining

[Source/parser changes](../../app/filings/earnings_schedule_source.py) retain the existing classifier unchanged. The measured multiple-agenda rejection is repaired: contiguous Agenda1…AgendaN (maximum 16) are all retained. Duplicate, gapped, unsupported or conflicting structured fields fail closed. An exact explicit Financial results agenda supplies that existing classifier label; unrelated agendas and remarks cannot invent it. Unrecognized non-results combinations remain ambiguous rather than being promoted. The prior source field values and full document-byte checksum remain auditable.

Supported XML optional fields are the **observed** `DateOfReport`, `WhetherResultsAreAuditedOrUnaudited`, `NatureOfReportStandaloneConsolidated`, `ReportingPeriodType`, `MonthOfPeriodEnded`, `YearOfPeriodEnded`, `RemarksWebsiteDissemination`. The rendered table additionally supports exact `Original Meeting Date` and `Reason for Re-schedule (postpone or prepone) / Cancellation` labels. Unobserved XML QName variants for those two fields are not guessed. Scope/period remain raw source metadata; this repair does not infer a single canonical scope from “Standalone And Consolidated.”

The acquisition boundary binds actual response URL **equal to** the inventory's published link. The parsed source retains inventory reference/fingerprint, original inventory purpose/prose, raw dissemination value, each structured agenda, and document checksum. Joined source fingerprint covers both representations. Different published URLs remain different lineage even when document bytes are identical (observed GFSTEELS pair); there is no same-company/date deduplication. Symbol/date/title matching cannot create a source join. Integrated Financials paths are outside the admitted prior-intimation allowlist and cannot supply an earlier inventory's public visibility.

The [discovery inspection](../../app/filings/earnings_schedule_discovery.py) consumes exact joined bytes and the existing immutable identity reader, with a supplied aware observation time. Exact symbol and ISIN must agree with the same canonical identity; disagreement is `IDENTITY_CONFLICTED`. Names are not used. Missing or temporally ineligible identities remain unresolved. No current master is converted into invented historical identity evidence.

### Descriptive versus strict PIT

A `CURRENT_DESCRIPTIVE_READY` inspection requires exact identity, qualifying structured results purpose, a valid proposed date and an original/new notice. A reschedule/cancellation without an exact parent link is not an active schedule. Current identity is checked at the supplied observation time; existing normalization independently checks historical identity at publication time. The observation timestamp is retained as observation only, not substituted for public `known_at`.

Naive/missing dissemination remains `KNOWN_AT_NOT_STRICT_PIT`. Even an explicitly offset-resolved timestamp is reported as `TIMEZONE_RESOLVED_AUTHORITY_UNVERIFIED`: timezone arithmetic is **not** approval of public-time semantics. Existing candidates remain `UNVERIFIED_SOURCE_AUTHORITY`; this repair's strict-PIT flag is unconditionally false until separate authority admission. No new semantics/authority switch is exposed to callers. Fixture success proves the structural distinction, not live strict-PIT readiness.

The existing classifier, schedule normalization, immutable SQLite store, reconciliation and historical selector implementations are otherwise unchanged. No BSE lookup is required for an independently valid NSE inspection. Source count and coverage are separate from identity/event qualification.

### Company and window receipts

Every target receives a deterministic receipt binding exchange/source URL, requested start/end dates, retrieval timestamp, source and batch fingerprints, query state and joined inspection fingerprints. Publication evidence is not retrieved from system time. Output distinguishes local exact-identity match attempts from individual source HTTP queries.

Current admitted transports support only `WINDOW_COVERAGE_UNPROVEN`, `SOURCE_PARTIAL`, `IDENTITY_UNRESOLVED` and `SOURCE_FAILED` outcomes. `QUERY_SUCCEEDED_MATCHED`, `QUERY_SUCCEEDED_NO_QUALIFYING_EVENT` and `QUERY_SUCCEEDED_NON_RESULTS_ONLY` are **not emitted** without a proven source query protocol. There is no caller-supplied completeness Boolean: window-applied, pagination-complete, response-complete and complete-success are false for both observed inventories. Descriptive counts are locally limited to the requested window, without claiming the source applied it. Duplicate/mismatched inspection lineage is rejected. Freshness remains POLICY_BLOCKED and Gate 6 clearance false.

## Completed 31-company canary

Requested inspection window: **2026-08-29 to 2026-10-27**, an acquisition control, not a freshness/investment threshold. NSE retrieval: **2026-09-12T16:45:50.472094+00:00**; BSE: **2026-09-12T16:45:59.458377+00:00**.

| Measure | NSE | BSE |
| --- | ---: | ---: |
| Requested population | 31 | 31 |
| Individual source queries / complete windows | 0 / 0 | 0 / 0 |
| Local target-receipt construction | 31 | 31 |
| Local exact joined-source matching attempts | 31 | 0 (no board-intimation links) |
| Inventory rows | 12 | 10 |
| Linked prior-intimation document requests / parses | 6 / 6 | 0 / 0 |
| Source-side symbol+ISIN rows / distinct pairs | 6 / 5 | 0 / 0 |
| Structured results / non-qualifying / ambiguous linked documents | 1 / 3 / 2 | 0 / 0 / 0 |
| Canonical target identity matches | 0 | 0 |
| Target results / non-results / ambiguous matching schedules | 0 / 0 / 0 | 0 / 0 / 0 |
| Target current-descriptive / strict-PIT candidates | 0 / 0 | 0 / 0 |
| Timezone / public-time authority proofs | 0 / 0 | 0 / 0 |
| Current reschedules / cancellations / admitted parent links | 0 / 0 / 0 | 0 / 0 / 0 |
| Canonical conflicts | 0 | 0 |

HTEL's financial-results notice is outside the population; it is not attributed to one of the 31. GFSTEELS has two distinct source links with identical bytes, retained separately. The one historical NITINFIRE reschedule sample is archaeology only, excluded from canary counts.

The 201 stored historical security identities are NSE_CM_UDIFF_FINAL_BHAVCOPY observations; none resolves currently for these 31: 30 DATA_UNAVAILABLE, one NOT_EFFECTIVE (`NSE:INE00FF01025`). The legacy instruments table is empty. These facts do not mean the companies do not exist or that other Core inventories are unavailable; they mean the **existing effective-identity reader used by this adapter** cannot currently supply their required provenance. No identity import/fallback was invented. FinancialFact instrument IDs define the requested population, not a schedule identity receipt.

In this matrix “UNPROVEN” means `WINDOW_COVERAGE_UNPROVEN` for both exchange queries. Every row has `identity_query_state=IDENTITY_UNRESOLVED`, future schedule `UNPROVEN_NOT_ABSENT`, coverage false and known-at unavailable. Names below are the user-supplied target labels, **not** successful source-identity joins.

| Canonical target | User target label | Effective identity reader | NSE / BSE query coverage | Descriptive / strict PIT |
| --- | --- | --- | --- | ---: |
| NSE:INE002A01018 | — | DATA_UNAVAILABLE | UNPROVEN / UNPROVEN | 0 / 0 |
| NSE:INE002L01015 | — | DATA_UNAVAILABLE | UNPROVEN / UNPROVEN | 0 / 0 |
| NSE:INE002S01010 | — | DATA_UNAVAILABLE | UNPROVEN / UNPROVEN | 0 / 0 |
| NSE:INE003A01024 | — | DATA_UNAVAILABLE | UNPROVEN / UNPROVEN | 0 / 0 |
| NSE:INE006I01046 | — | DATA_UNAVAILABLE | UNPROVEN / UNPROVEN | 0 / 0 |
| NSE:INE007A01025 | — | DATA_UNAVAILABLE | UNPROVEN / UNPROVEN | 0 / 0 |
| NSE:INE008A01015 | — | DATA_UNAVAILABLE | UNPROVEN / UNPROVEN | 0 / 0 |
| NSE:INE009A01021 | — | DATA_UNAVAILABLE | UNPROVEN / UNPROVEN | 0 / 0 |
| NSE:INE00E101023 | — | DATA_UNAVAILABLE | UNPROVEN / UNPROVEN | 0 / 0 |
| NSE:INE00FF01025 | — | NOT_EFFECTIVE | UNPROVEN / UNPROVEN | 0 / 0 |
| NSE:INE00H001014 | — | DATA_UNAVAILABLE | UNPROVEN / UNPROVEN | 0 / 0 |
| NSE:INE00LO01017 | — | DATA_UNAVAILABLE | UNPROVEN / UNPROVEN | 0 / 0 |
| NSE:INE00R701025 | — | DATA_UNAVAILABLE | UNPROVEN / UNPROVEN | 0 / 0 |
| NSE:INE00WC01027 | — | DATA_UNAVAILABLE | UNPROVEN / UNPROVEN | 0 / 0 |
| NSE:INE010B01027 | — | DATA_UNAVAILABLE | UNPROVEN / UNPROVEN | 0 / 0 |
| NSE:INE010J01012 | — | DATA_UNAVAILABLE | UNPROVEN / UNPROVEN | 0 / 0 |
| NSE:INE010V01017 | — | DATA_UNAVAILABLE | UNPROVEN / UNPROVEN | 0 / 0 |
| NSE:INE011K01018 | — | DATA_UNAVAILABLE | UNPROVEN / UNPROVEN | 0 / 0 |
| NSE:INE012A01025 | — | DATA_UNAVAILABLE | UNPROVEN / UNPROVEN | 0 / 0 |
| NSE:INE013P01021 | — | DATA_UNAVAILABLE | UNPROVEN / UNPROVEN | 0 / 0 |
| NSE:INE016A01026 | — | DATA_UNAVAILABLE | UNPROVEN / UNPROVEN | 0 / 0 |
| NSE:INE017A01032 | — | DATA_UNAVAILABLE | UNPROVEN / UNPROVEN | 0 / 0 |
| NSE:INE018A01030 | — | DATA_UNAVAILABLE | UNPROVEN / UNPROVEN | 0 / 0 |
| NSE:INE068V01023 | GLAND | DATA_UNAVAILABLE | UNPROVEN / UNPROVEN | 0 / 0 |
| NSE:INE090A01021 | ICICIBANK | DATA_UNAVAILABLE | UNPROVEN / UNPROVEN | 0 / 0 |
| NSE:INE0FHS01024 | DEEPINDS | DATA_UNAVAILABLE | UNPROVEN / UNPROVEN | 0 / 0 |
| NSE:INE0PPK01015 | — | DATA_UNAVAILABLE | UNPROVEN / UNPROVEN | 0 / 0 |
| NSE:INE372A01015 | APARINDS | DATA_UNAVAILABLE | UNPROVEN / UNPROVEN | 0 / 0 |
| NSE:INE429E01023 | — | DATA_UNAVAILABLE | UNPROVEN / UNPROVEN | 0 / 0 |
| NSE:INE437A01024 | — | DATA_UNAVAILABLE | UNPROVEN / UNPROVEN | 0 / 0 |
| NSE:INE955D01029 | GENUSPOWER | DATA_UNAVAILABLE | UNPROVEN / UNPROVEN | 0 / 0 |

Thus APARINDS, DEEPINDS, GENUSPOWER and GLAND all explicitly remain identity-unresolved / future-schedule-unproven / coverage-unproven / known-at-unavailable. “No qualifying event” is not asserted.

## Readiness after repair

| Domain | State | Boundary |
| --- | --- | --- |
| NSE discovery / CSV | PARTIAL / NOT_ADMITTED | RSS exact links usable; no exposed CSV or complete company/window protocol. |
| BSE discovery / detail | PARTIAL | Public recent list and exact detail paths; no complete company/window protocol. |
| NSE structured parser / exact source join | READY_FOR_OBSERVED_VARIANTS | Six real linked XML parses, exact rendered-table fields in fixtures; unknown variants fail closed. |
| Source-side identity | READY_FOR_OBSERVED_VARIANTS | Symbol and ISIN retained together; canonical admission remains separate. |
| Canonical security identity / 31-company coverage | PARTIAL / NOT_READY | Zero current canonical schedule joins; effective identity and discovery coverage gaps. |
| Financial-results classification / date precision | READY / READY | Existing classifier unchanged; explicit structured evidence only; DATE_ONLY retained. |
| Known-at / timezone | PARTIAL / UNPROVEN | Zero live authority/timezone proofs; no assumed IST. |
| Revision/cancellation lineage | PARTIAL | Intent parsed; exact parent linkage unproven. |
| Reconciliation | PARTIAL | Existing isolated mechanics retained; no live dual-source pair. |
| Immutable storage / PIT selector / coverage receipt | READY / READY / READY_PARTIAL_RECEIPTS | Existing mechanics unchanged; truthful incomplete receipts, no production schedule writes. |
| Freshness / Gate 6 integration | POLICY_BLOCKED / NOT_READY | Neither activated nor wired. |

## Validation and defensive audit

Focused source/inspection/candidate tests: **124 passed**. Affected schedule-store, source-authority, timestamp and identity tests: **200 passed / 2 warnings**. Deterministic canary reparse and per-company receipt replay: **equal**, with no repeated network requests or production writes. Isolated existing tests prove reopen, no duplicate candidate creation, immutable conflicts, single-source validity, and future revision exclusion.

Exactly one full backend run completed: **4,324 passed / 0 failed / 6 skipped / 2 warnings**, exit 0, **359.47 seconds**. The warnings are the existing Starlette/httpx and AnyIO deprecations. No rerun or application/test edits followed. All four application/test SHA-256 hashes matched the pre-run hashes. Markdown local-target validation checked **256 links**, with zero errors; seven-file whitespace and `git diff --check` passed.

The post-full-suite read-only protected row hashes and schema fingerprint are unchanged. FinancialFacts **6,118**; CorporateFilings **455**; portfolio snapshots **1**, cash **UNKNOWN**; canonical strategy definitions **1** and results **2,074**; generic strategy/results **0/0**; paper trades/trade plans **0/0**; generic/canonical gate evaluations **0/0**; portfolio transactions **5**, portfolios **1**. No production schedule tables exist. Final full SQLite integrity: **ok** (539.0 seconds); FK violations: **0**. The integrity process independently reconfirmed protected hashes and schema unchanged.

Defensive review: only the two filing-source/discovery modules and their focused tests change application behavior. No classifier function, normalized-candidate authority, existing store, PIT selector, reconciliation, GateInput/engine, schema, API/UI, provider credentials, runtime wiring or investment thresholds change. Source URL restrictions prevent later Integrated Financials backdating and arbitrary endpoint use. Neither source incompleteness nor an HTTP 200/zero-row response can manufacture absence or clearance.

## Exact next continuation — not started

`EARNINGS_CALENDAR_ALTERNATIVE_OFFICIAL_SOURCE_RESEARCH_V1`

The dominant blocker is a publicly retrievable, source-complete scoped inventory with exact filing linkage, plus appropriate canonical identity provenance. Current RSS/BSE recent links are useful but insufficient for 31-company completeness; fixing timezone alone would still yield no scoped coverage. Research an alternative official/public source protocol, not another generic shell/parser repair loop. Known-at semantics, freshness and Gate 6 authority stay separately blocked.
