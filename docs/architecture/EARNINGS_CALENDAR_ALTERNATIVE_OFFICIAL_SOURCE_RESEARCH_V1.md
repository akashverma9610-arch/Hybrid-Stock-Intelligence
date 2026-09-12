# Earnings Calendar Alternative Official Source Research V1

Status: `RESEARCH_COMPLETE / SOURCE_AVAILABLE / INTERNAL_IDENTITY_BRIDGE_BLOCKED / CANDIDATES_NON_ACTIVE / GATE6_NOT_READY`.

This bounded research and cross-store audit follows the [Official NSE/BSE Earnings Calendar Discovery Repair](OFFICIAL_NSE_BSE_EARNINGS_CALENDAR_ADAPTER_REPAIR.md). The companion [deterministic receipt](EARNINGS_CALENDAR_ALTERNATIVE_OFFICIAL_SOURCE_RESEARCH_V1_RECEIPT.json) is the machine-readable audit artifact. This slice creates no source data, schedule candidate, production record, schema, runtime, provider or Gate 6 change.

Frozen controls remain exactly:

`V1_ACTIVE=TRUE / V2_ACTIVE=FALSE / V2_SHADOW_ONLY=TRUE / B08=CLOSED_FOR_ACTIVATION_COMPATIBILITY / NO_UNVERIFIED_CALENDAR_CLEARANCE=TRUE / NO_HISTORICAL_RESULT_DATE_AS_FUTURE_SCHEDULE=TRUE / NO_NAME_BASED_IDENTITY=TRUE / NO_UNDOCUMENTED_PRIVATE_SOURCE=TRUE / NO_AI_PREDICTED_EARNINGS_DATE=TRUE / AI_DECISION_AUTHORITY=FALSE`.

## Scope and method

The audit reads the existing production database in SQLite read-only mode and uses direct public HTTPS page probes plus public official documents indexed by the exchanges. It did not automate a browser, reverse engineer a client API, guess archive paths or document identifiers, crawl an archive, download a production filing, use a commercial source, or use an AI-predicted date.

The canonical population is the 31 distinct `financial_facts.instrument_id` values. The comparison covers the schedule adapter's effective `HistoricalSecurityIdentity` reader, current NSE universe, dated NSE MII/session observations, NSE UDIFF intervals, provider mappings, BSE official filings/facts, and existing historical intervals.

## Cross-store identity diagnosis

All 31 targets have an exact canonical `NSE:<ISIN>` identity in the current NSE universe at `2026-08-24T20:38:50.218348+00:00`, active BSE official and Upstox mappings, BSE official filing/fact evidence, and dated NSE MII/session/UDIFF evidence through `2026-08-31`. Seven also have an active Dhan mapping. The current schedule adapter selects only effective `HistoricalSecurityIdentity` records at source `known_at`.

Thirty targets have no record in that reader. `NSE:INE00FF01025` has two `AMIORG` records, but both end in 2025 and are ineffective for current source time. This is not a missing-company conclusion: exact identity evidence exists in owned stores but is not bridged into the reader's strict effective-identity representation. It is an `INTERNAL_IDENTITY_BRIDGE` blocker, not authorization for a current-master fallback.

All table rows have: current NSE universe evidence at 2026-08-24; BSE official financial filing/fact lineage; an active Upstox mapping; dated MII/session evidence (latest 2026-08-31); and at least one UDIFF effective-identity interval. `Dhan` appears only where an active mapping exists. The historical reader column is the adapter's actual input, not a statement about any other canonical store.

| Canonical ID / ISIN | NSE symbol | BSE code | UDIFF intervals | Historical reader records | Active providers | Classification |
| --- | --- | ---: | ---: | ---: | --- | --- |
| NSE:INE002A01018 | RELIANCE | 500325 | 12 | 0 | BSE, Upstox | `CANONICAL_IDENTITY_EXISTS_ADAPTER_READER_MISALIGNED` |
| NSE:INE002L01015 | SJVN | 533206 | 2 | 0 | BSE, Upstox | `CANONICAL_IDENTITY_EXISTS_ADAPTER_READER_MISALIGNED` |
| NSE:INE002S01010 | MGL | 539957 | 1 | 0 | BSE, Upstox | `CANONICAL_IDENTITY_EXISTS_ADAPTER_READER_MISALIGNED` |
| NSE:INE003A01024 | SIEMENS | 500550 | 1 | 0 | BSE, Upstox | `CANONICAL_IDENTITY_EXISTS_ADAPTER_READER_MISALIGNED` |
| NSE:INE006I01046 | ASTRAL | 532830 | 1 | 0 | BSE, Upstox | `CANONICAL_IDENTITY_EXISTS_ADAPTER_READER_MISALIGNED` |
| NSE:INE007A01025 | CRISIL | 500092 | 1 | 0 | BSE, Upstox | `CANONICAL_IDENTITY_EXISTS_ADAPTER_READER_MISALIGNED` |
| NSE:INE008A01015 | IDBI | 500116 | 3 | 0 | BSE, Upstox | `CANONICAL_IDENTITY_EXISTS_ADAPTER_READER_MISALIGNED` |
| NSE:INE009A01021 | INFY | 500209 | 9 | 0 | BSE, Upstox | `CANONICAL_IDENTITY_EXISTS_ADAPTER_READER_MISALIGNED` |
| NSE:INE00E101023 | BIKAJI | 543653 | 1 | 0 | BSE, Upstox | `CANONICAL_IDENTITY_EXISTS_ADAPTER_READER_MISALIGNED` |
| NSE:INE00FF01025 | ACUTAAS | 543349 | 1 | 2 (ended 2025) | BSE, Upstox | `IDENTITY_EXISTS_BUT_NOT_EFFECTIVE_FOR_DATE` |
| NSE:INE00H001014 | SWIGGY | 544285 | 4 | 0 | BSE, Upstox | `CANONICAL_IDENTITY_EXISTS_ADAPTER_READER_MISALIGNED` |
| NSE:INE00LO01017 | CRAFTSMAN | 543276 | 5 | 0 | BSE, Upstox | `CANONICAL_IDENTITY_EXISTS_ADAPTER_READER_MISALIGNED` |
| NSE:INE00R701025 | DALBHARAT | 542216 | 1 | 0 | BSE, Upstox | `CANONICAL_IDENTITY_EXISTS_ADAPTER_READER_MISALIGNED` |
| NSE:INE00WC01027 | AFFLE | 542752 | 1 | 0 | BSE, Upstox | `CANONICAL_IDENTITY_EXISTS_ADAPTER_READER_MISALIGNED` |
| NSE:INE010B01027 | ZYDUSLIFE | 532321 | 1 | 0 | BSE, Dhan, Upstox | `CANONICAL_IDENTITY_EXISTS_ADAPTER_READER_MISALIGNED` |
| NSE:INE010J01012 | TEJASNET | 540595 | 1 | 0 | BSE, Upstox | `CANONICAL_IDENTITY_EXISTS_ADAPTER_READER_MISALIGNED` |
| NSE:INE010V01017 | LTTS | 540115 | 1 | 0 | BSE, Upstox | `CANONICAL_IDENTITY_EXISTS_ADAPTER_READER_MISALIGNED` |
| NSE:INE011K01018 | TEGA | 543413 | 1 | 0 | BSE, Upstox | `CANONICAL_IDENTITY_EXISTS_ADAPTER_READER_MISALIGNED` |
| NSE:INE012A01025 | ACC | 500410 | 1 | 0 | BSE, Upstox | `CANONICAL_IDENTITY_EXISTS_ADAPTER_READER_MISALIGNED` |
| NSE:INE013P01021 | ONESOURCE | 544292 | 3 | 0 | BSE, Upstox | `CANONICAL_IDENTITY_EXISTS_ADAPTER_READER_MISALIGNED` |
| NSE:INE016A01026 | DABUR | 500096 | 2 | 0 | BSE, Upstox | `CANONICAL_IDENTITY_EXISTS_ADAPTER_READER_MISALIGNED` |
| NSE:INE017A01032 | GESHIP | 500620 | 1 | 0 | BSE, Upstox | `CANONICAL_IDENTITY_EXISTS_ADAPTER_READER_MISALIGNED` |
| NSE:INE018A01030 | LT | 500510 | 6 | 0 | BSE, Upstox | `CANONICAL_IDENTITY_EXISTS_ADAPTER_READER_MISALIGNED` |
| NSE:INE068V01023 | GLAND | 543245 | 1 | 0 | BSE, Dhan, Upstox | `CANONICAL_IDENTITY_EXISTS_ADAPTER_READER_MISALIGNED` |
| NSE:INE090A01021 | ICICIBANK | 532174 | 9 | 0 | BSE, Dhan, Upstox | `CANONICAL_IDENTITY_EXISTS_ADAPTER_READER_MISALIGNED` |
| NSE:INE0FHS01024 | DEEPINDS | 543288 | 1 | 0 | BSE, Dhan, Upstox | `CANONICAL_IDENTITY_EXISTS_ADAPTER_READER_MISALIGNED` |
| NSE:INE0PPK01015 | ORIENTTECH | 544235 | 2 | 0 | BSE, Upstox, YFinance | `CANONICAL_IDENTITY_EXISTS_ADAPTER_READER_MISALIGNED` |
| NSE:INE372A01015 | APARINDS | 532259 | 1 | 0 | BSE, Dhan, Upstox | `CANONICAL_IDENTITY_EXISTS_ADAPTER_READER_MISALIGNED` |
| NSE:INE429E01023 | SAFARI | 523025 | 4 | 0 | BSE, Upstox, YFinance | `CANONICAL_IDENTITY_EXISTS_ADAPTER_READER_MISALIGNED` |
| NSE:INE437A01024 | APOLLOHOSP | 508869 | 7 | 0 | BSE, Dhan, Upstox, YFinance | `CANONICAL_IDENTITY_EXISTS_ADAPTER_READER_MISALIGNED` |
| NSE:INE955D01029 | GENUSPOWER | 530343 | 5 | 0 | BSE, Dhan, Upstox | `CANONICAL_IDENTITY_EXISTS_ADAPTER_READER_MISALIGNED` |

`YFinance` is reported only because it is a pre-existing mapping record; it is not a calendar source and was not used.

## Official-source routing research

| Official source family | Public evidence and bounded probe | Supports | Remains unproven / forbidden |
| --- | --- | --- | --- |
| [NSE Event Calendar](https://www.nseindia.com/companies-listing/corporate-filings-event-calendar) | Company/symbol, purpose, date-window and CSV controls are public. Each of the five direct public symbol pages returned HTTP 200 within 2 MiB. | Exchange-owned discovery surface; public indexed historical rows show symbol, purpose, details and date. | Static responses did not render a target row. No source-applied window, pagination/completeness, CSV URL or filing identity was established. HTTP 200 is not `no event`. |
| [NSE Board Meetings](https://www.nseindia.com/companies-listing/corporate-filings-board-meetings) | The shell exposes Meeting controls, Board Meeting Details, XBRL and Download CSV. Five symbol pages were HTTP 200. | Exchange-owned board-meeting discovery family. | No target row, exact filing identifier, received/disseminated time or complete company/window protocol was proven. No client API was inspected. |
| [NSE Announcements](https://www.nseindia.com/companies-listing/corporate-filings-announcements) | Symbol, subject, date-window, CSV and XBRL are public. Rendered official records separately label Exchange Received and Dissemination Times. | Exchange-owned announcements discovery and the only researched family visibly distinguishing receipt from dissemination. | Five static symbol pages supplied no target row. Timezone and publication-time authority remain unproven. |
| [NSE archive/iXBRL](https://nsearchives.nseindia.com/) | Official public examples expose exact symbol, ISIN, financial-results agenda and dates for APARINDS, DEEPINDS and ICICIBANK; GENUSPOWER has exact archive evidence. | Exact corroboration only after an inventory item links to the document. | Search is not a production protocol. A later result cannot backdate a prior notice; an unlinked archive path is never guessed. GLAND was not individually linked in this bounded probe. |
| [BSE Board Meetings](https://www.bseindia.com/corporates/board_meeting.aspx) and [BSE results](https://www.bseindia.com/corporates/Comp_Results.aspx?Code=532259) | Official indexed Board Meetings rows show Security Code, Security Name, purpose and Meeting Date. One exact BSE code exists per target. | Exchange-owned alternative once an inventory-to-detail identity/timestamp link is documented. | Current static desktop responses did not prove a target-scoped complete window, immutable record identifier, exact document link or public known-at. No detail ID was guessed. |
| Issuer investor-relations site | Not invoked because exchange families are reachable. | Separately governed fallback only if exchange discovery is genuinely unusable and exact identity/time semantics are proven. | No issuer fallback is admitted here. |

The [NSE Event Calendar](https://www.nseindia.com/companies-listing/corporate-filings-event-calendar) has a public symbol-query shape and historical rows. The public [NSE Announcements](https://www.nseindia.com/companies-listing/corporate-filings-announcements) presentation distinguishes receipt from dissemination, but proves neither a timezone nor `known_at` authority. The official [NSE corporate route inventory](https://archives.nseindia.com/content/circulars/WEB45032.pdf) identifies Board Meetings and Announcements as corporate disclosure surfaces.

## Exact joins, PIT and coverage

An admissible future join is only:

`exchange inventory record/immutable identifier → its published exact XBRL or attachment URL → exact NSE symbol and ISIN, agenda and meeting date → effective canonical identity at exchange dissemination/known-at`.

Company name plus date, symbol plus date, a guessed archive URL, and a result filing backdated to a prior notice are rejected. `exchange_received_at`, `exchange_disseminated_at`, and HSI retrieval are distinct fields; no timezone is assumed to be IST. A report date alone cannot create strict `known_at`.

Each of APARINDS, DEEPINDS, GENUSPOWER, GLAND and ICICIBANK is `SOURCE_FAMILY_PROVEN / CURRENT_WINDOW_QUERYABLE / CURRENT_EVENT_UNKNOWN_BECAUSE_WINDOW_INCOMPLETE`. This is deliberately not an absence statement.

## Five-target historical evidence probe

The following is source-feasibility research, not a schedule import. A public archive record located by search is not an admitted production inventory link; it cannot establish a historical `known_at` or be used to backdate a schedule.

| Target | Bounded official historical evidence | Exact fields observed | Admission and current-window state |
| --- | --- | --- | --- |
| APARINDS | [Public NSE Prior Intimation iXBRL](https://nsearchives.nseindia.com/corporate/ixbrl/PRIOR_INTIMATION_59958_16072025195757_iXBRL_WEB.html) and a later [Integrated Filing](https://nsearchives.nseindia.com/corporate/ixbrl/INTEGRATED_FILING_INDAS_163124_28052026205114_iXBRL_WEB.html). | Prior-intimation search representation: symbol and financial-results agenda. Later filing: `APARINDS`, `INE372A01015`, results-approved date and prior-intimation date. | Archive family proven; neither search discovery nor later filing is an exact current inventory link. Current event is unknown because window completeness is unproven. |
| DEEPINDS | [Integrated Filing](https://nsearchives.nseindia.com/corporate/ixbrl/INTEGRATED_FILING_INDAS_179353_28072026181006_iXBRL_WEB.html) and official [board-outcome archive record](https://nsearchives.nseindia.com/corporate/DEEPINDS_05082024152043_Outcome.pdf). | `DEEPINDS`, `INE0FHS01024`, results approval date and a prior-intimation date appear in the later filing; outcome confirms results. | Later corroboration only; no original prior-intimation inventory link or public known-at is admitted. Current event unknown because window completeness is unproven. |
| GENUSPOWER | Official [NSE archive results communication](https://nsearchives.nseindia.com/corporate/GENUSPOWER_10112023134630_STX_signed.pdf). | Exact `GENUSPOWER` results communication. | Confirms archive family existence, but this bounded probe did not obtain an exact ISIN-bearing prior-intimation link. Current event unknown because window completeness is unproven. |
| GLAND | No target-specific prior-intimation or board record was linked in the bounded public probe. | Current canonical identity and BSE code are exact internally; no public schedule record was admitted. | `SOURCE_FAMILY_PROVEN`, not target-event absence. Current event unknown because window completeness is unproven. |
| ICICIBANK | [Public NSE Prior Intimation iXBRL](https://nsearchives.nseindia.com/corporate/ixbrl/PRIOR_INTIMATION_58420_25062025185335_iXBRL_WEB.html). | `ICICIBANK`, `INE090A01021`, financial-results agenda, proposed meeting date and report date. | Strong identity/agenda/date corroboration, but public dissemination timestamp/timezone and exact inventory lineage remain unproven. Current event unknown because window completeness is unproven. |

## Source-option matrix

`YES_IF_LINKED` means an exact official inventory-to-document lineage is still mandatory. `NOT_ADMITTED` means this research does not approve the source for a future candidate or absence decision.

| Source | Identity | Event date | Public known-at | Revision | Complete window | Machine access | Authority | Overall feasibility |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| NSE Event Calendar | UNPROVEN | Visible schema | UNPROVEN | UNPROVEN | UNPROVEN | Public static shell; documented symbol surface | PRIMARY_EXCHANGE | PARTIAL / NOT_ADMITTED |
| NSE Board Meetings | UNPROVEN | Visible schema | UNPROVEN | UNPROVEN | UNPROVEN | Public static shell | PRIMARY_EXCHANGE | PARTIAL / NOT_ADMITTED |
| NSE Announcements | YES_IF_LINKED | YES_IF_LINKED | Value visible in public records; timezone authority unproven | UNPROVEN | UNPROVEN | Public static shell | PRIMARY_EXCHANGE | PARTIAL / NOT_ADMITTED |
| NSE Prior Intimation XBRL/iXBRL | YES_IF_LINKED | YES_IF_LINKED | Not independently established | Intent only; parent linkage unproven | No inventory | Structured exact document when linked | PRIMARY_EXCHANGE_DISTRIBUTED_COMPANY_FILING | CORROBORATION_ONLY |
| BSE Board Meetings | BSE code available internally; source join unproven | Visible indexed schema | UNPROVEN | UNPROVEN | UNPROVEN | Desktop/static surface reached | PRIMARY_EXCHANGE | PARTIAL / NOT_ADMITTED |
| BSE Announcements | BSE code available internally; detail identity unproven in this probe | Depends on exact record | UNPROVEN | UNPROVEN | UNPROVEN | Public mobile/static family | PRIMARY_EXCHANGE | PARTIAL / NOT_ADMITTED |
| BSE Prior Intimation structured | UNPROVEN | UNPROVEN | UNPROVEN | UNPROVEN | UNPROVEN | No documented scoped route established | PRIMARY_EXCHANGE | UNAVAILABLE_FOR_THIS_SLICE |
| Primary issuer website fallback | Exact issuer ownership can be separate evidence | Potentially | Typically weak unless independently proven | Potentially | UNPROVEN | Site-specific | PRIMARY_ISSUER | DEFERRED / NOT_ADMITTED |

## Required outcome and next slice

**Outcome: B — source available, identity bridge blocked.** The dominant blocker is the adapter's inability to read exact existing canonical identity evidence via its effective `HistoricalSecurityIdentity` contract. Coverage and known-at remain independently blocked, but resolving either cannot make a candidate while strict identity fails first.

The one authorized next slice is:

`EARNINGS_CALENDAR_CANONICAL_IDENTITY_BRIDGE_V1`

It must be a strict, PIT-effective projection from existing owned identity evidence into the reader's required provenance form. It may not use a current-master fallback, name matching, inferred listing ranges, schedule persistence, Gate 6, automatic clearance, or source-data acquisition. `EARNINGS_CALENDAR_KNOWN_AT_SEMANTICS_V1` and `EARNINGS_CALENDAR_COVERAGE_WINDOW_POLICY_V1` remain deferred.

## Validation and non-effects

The deterministic receipt test validates the complete 31-row population, classification distribution (30 reader misalignments; one ineffective interval), exact target mappings, no-name-identity control, source availability state and receipt fingerprint replay. Markdown links and whitespace are checked separately. No runtime code, source fixture acquisition, schedule candidate, database record, portfolio mutation, broker/order operation, provider call or trading action is introduced.
