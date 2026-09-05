# Canonical Filing Timestamp Timezone Provenance V1

**Status: `IMPLEMENTED_CONTRACT / SOURCE_EVIDENCE_COVERAGE_UNAVAILABLE / RESEARCH_ONLY / NON_EXECUTABLE`.**

This bounded contract records how an official filing timestamp may (or may not)
be interpreted. It does not change a FinancialFact, an existing filing
`announced_at`/`received_at`, calendar rules, price adjustment, event returns,
Inflection qualification, scores, rankings, setups, gates, portfolio state, or
execution. All receipts are immutable and fixed to `WATCH_ONLY / NON_EXECUTABLE`.

```text
raw timestamp text != parsed local clock value
exchange location != timezone evidence
date != exact timestamp
timestamp != public-known time unless source semantics prove it
resolved event time != market reaction
```

`app/historical/filing_timestamp_timezone_provenance.py` has no storage,
transport, network, runtime-clock, price, portfolio, broker, order, API, or UI
dependency. Equal retained source inputs plus equal explicit rules replay to an
equal deterministic receipt identity and fingerprint.

## Canonical preservation and resolution contract

The immutable contract contains:

- `FilingTimestampSourceEvidence`: verbatim source family, document/payload
  identity, raw field path, raw text, and timestamp role. It asserts no
  timezone semantics.
- `FilingTimestampInput`: source-injected parsed/date/missing evidence before
  timezone interpretation.
- `SourceTimezoneRule`: exact source-family/field rule, first-party evidence
  identity/fingerprint, evidence-known instant, effective scope, explicit
  historical-continuity declaration, IANA zone, and policy fingerprint.
- `FilingTimestampProvenanceReceipt`: filing/instrument/source identity, raw
  evidence, parsed local value, timezone/offset provenance, rule lineage,
  normalized UTC only when justified, resolution/reason state, event-known-time
  caveat, deterministic receipt identity, and fingerprint.
- deterministic audit buckets by source family, recorded coverage year, and
  canonical instrument.

For future BSE Results Page/Archive ingestion, `BseResultMetadata` now retains
the exact selected `filing_date_time` or `revised_date_time` text and a
source-specific field path. The optional evidence is serialized inside the
existing immutable corporate-filing payload and the BSE archive alias sidecar;
no database migration is introduced. This does not change the legacy BSE
normalizer or any current FinancialFact/filing.

Historical payloads without raw evidence receive
`NOT_RETAINED_IN_LEGACY_CANONICAL_RECORD`. Their normalized time is never
recycled as supposed raw source input.

| Timezone provenance | Exact meaning |
| --- | --- |
| `EXPLICIT_OFFSET` | Raw text carries `Z` or numeric offset. |
| `EXPLICIT_TIMEZONE_IDENTIFIER` | Raw source evidence carries an IANA timezone identifier. |
| `SOURCE_SCHEMA_DOCUMENTED` | Exact first-party schema defines this source/field. |
| `SOURCE_SYSTEM_DOCUMENTED` | Exact first-party system document defines this source/field. |
| `SOURCE_NATIVE_EPOCH` | Exact first-party schema defines epoch unit and UTC semantics. |
| `DERIVED_FROM_APPROVED_SOURCE_RULE` | Exact governed source/field rule applies. |
| `TIMEZONE_UNRESOLVED` | A timestamp survives but UTC conversion lacks proof. |
| `TIMEZONE_EVIDENCE_CONFLICTED` | Offset/identifier/rule evidence conflicts; no preference is selected. |

`EXACT_FILING_TIMESTAMP_KNOWN` alone carries normalized UTC. Date-only input
is `FILING_DATE_KNOWN` with no clock time; no 00:00, market-open, close, or
other intraday default is invented. Missing source publication time remains
`EVENT_TIMESTAMP_UNAVAILABLE`. `EventKnownTimeStatus` is separate: BSE result
fields remain `SOURCE_PUBLICATION_TIMESTAMP_UNVERIFIED`, while local-XBRL
observation is `SYSTEM_FIRST_OBSERVED_NOT_SOURCE_PUBLICATION`.

## Primary-source inventory and timezone research

The production-corpus inventory and primary-source research are specific to the
read-only audit at `2026-09-05T00:00:00Z`.

| Source family | Production results | Exact source surface / field | Raw format example | Offset / zone metadata | Existing canonical provenance | Outcome |
| --- | ---: | --- | --- | --- | --- | --- |
| BSE Results Page | Part of legacy BSE corpus; no retained sub-family split | [BSE `Comp_Results.aspx`](https://www.bseindia.com/corporates/Comp_Results.aspx?Code=532259), HTML `Filing Date Time`; revision uses `Revised Date Time` | `01-08-2026 10:00:00` | None retained; no authoritative BSE timezone statement recovered | `EXCHANGE_LOCAL_ASSUMPTION`; raw field/text absent from historic payload | `TIMEZONE_UNRESOLVED`; new source path is `BSE_RESULT_PAGE.HTML.filing_date_time` or `revised_date_time`. |
| BSE Results Archive | Part of legacy BSE corpus; no retained sub-family split | [BSE `Result_Arch_Download`](https://api.bseindia.com/BseIndiaAPI/api/Result_Arch_Download/w?scrip_cd=532259), CSV `Filing Date Time`; revision uses `Revised Date Time` | `5/28/2026 6:31:40 PM`; controlled 24-hour form `8/13/2026 17:20:23` | None retained; no authoritative BSE schema/timezone statement recovered | Archive alias keeps only legacy normalized `filing_at` and status | `TIMEZONE_UNRESOLVED`; new source path is `BSE_RESULT_ARCHIVE.CSV.filing_date_time` or `revised_date_time`. |
| BSE official local/staged XBRL | 3 | Official XBRL/local artifact contains reporting-period dates but no selected publication/dissemination clock | Date/reporting context only | No source publication timestamp | `SOURCE_PUBLICATION_TIMESTAMP_UNKNOWN`; system-first-observed is not BSE publication | `EVENT_TIMESTAMP_UNAVAILABLE`. |
| NSE official financial results | 0 | No source family currently produces a canonical production result filing | Not applicable | Not applicable | Not applicable | No NSE rule; BSE semantics cannot leak. |
| Other official result source | 0 | None in canonical storage | Not applicable | Not applicable | Not applicable | No rule. |

The two BSE first-party surfaces above were inspected directly. In the research
environment, the archive URL returned a BSE application HTML shell rather than
a documented CSV schema; neither surface supplied an explicit offset, IANA
timezone, epoch definition, or source-system statement for historical `Filing
Date Time`. Repository fixtures prove only field labels and accepted text
formats. Therefore no BSE rule is installed. No NSE result source exists in
the production corpus, so no NSE material is repurposed as BSE proof.

The former adapter's `Asia/Kolkata` conversion remains explicitly labelled
`EXCHANGE_LOCAL_ASSUMPTION`, not `SOURCE_SYSTEM_DOCUMENTED`. Lack of DST in
India does not prove this field's semantics. A future proven local-time rule
must use `Asia/Kolkata`, never hand-maintained `UTC+05:30` arithmetic, and must
be exact to one source family and field.

## PIT and conflict rules

A rule applies only when source family and raw field match exactly, its
first-party evidence is visible by explicit `as_of`, source date is inside the
effective interval (or the rule states historical continuity), and there is no
conflicting effective rule. A current rule cannot automatically backfill an
old archive. Later-discovered evidence can cover historical records only when
it explicitly establishes historical system continuity.

Raw explicit offset resolves only if any matching source rule agrees. Conflicts
preserve all source-rule IDs/fingerprints and return
`TIMEZONE_EVIDENCE_CONFLICTED`. Source-native epoch requires an exact
`UNIX_SECONDS` or `UNIX_MILLISECONDS` first-party rule; numeric magnitude is
never used to guess scale. BSE/NSE rules and fields remain isolated.

## Read-only production replay

The actual database replayed **332** `FINANCIAL_RESULTS` filings using no
source rule. Its deterministic audit fingerprint is:

`sha256:25323a6230dcafcde289ba541317642ae6771995709c72c0e0a70fa68fab5abe`

| Result | Count |
| --- | ---: |
| Exact timestamp / normalized UTC available | 0 / 0 |
| Explicit-offset / source-documentation / epoch resolved | 0 / 0 / 0 |
| `FILING_DATE_KNOWN` / date-only | 0 / 0 |
| `EVENT_TIMESTAMP_UNAVAILABLE` | 3 |
| `TIMEZONE_UNRESOLVED` | 329 |
| `TIMEZONE_EVIDENCE_CONFLICTED` | 0 |

All 332 legacy payloads are `NOT_RETAINED_IN_LEGACY_CANONICAL_RECORD`: 329
lost BSE source text after the old assumption and 3 never contained a BSE
publication timestamp. Existing source/document identity and warnings remain;
no raw timestamp is fabricated retroactively.

### Recorded-year and source coverage

Year is the existing legacy canonical-recorded year for coverage diagnostics,
not a claim about resolved event time.

| Recorded year | `TIMEZONE_UNRESOLVED` | `EVENT_TIMESTAMP_UNAVAILABLE` | Normalized UTC |
| --- | ---: | ---: | ---: |
| 2022 | 6 | 0 | 0 |
| 2023 | 8 | 0 | 0 |
| 2024 | 6 | 0 | 0 |
| 2025 | 130 | 0 | 0 |
| 2026 | 179 | 3 | 0 |

| Stored source family | Total | `TIMEZONE_UNRESOLVED` | `EVENT_TIMESTAMP_UNAVAILABLE` | UTC |
| --- | ---: | ---: | ---: | ---: |
| BSE official legacy canonical | 332 | 329 | 3 | 0 |
| NSE | 0 | 0 | 0 | 0 |
| Other official source | 0 | 0 | 0 | 0 |

### Five-target audit

| Instrument | Result filings | Raw evidence | Timezone / UTC | Session classification | Blocker |
| --- | ---: | --- | --- | --- | --- |
| APARINDS / `NSE:INE372A01015` | 19 | Not retained | `TIMEZONE_UNRESOLVED` / 0 | Unavailable | `RAW_TIMESTAMP_EVIDENCE_NOT_RETAINED`; no BSE rule. |
| DEEPINDS / `NSE:INE0FHS01024` | 14 | Not retained | `TIMEZONE_UNRESOLVED` / 0 | Unavailable | `RAW_TIMESTAMP_EVIDENCE_NOT_RETAINED`; no BSE rule. |
| GENUSPOWER / `NSE:INE955D01029` | 18 | Not retained | `TIMEZONE_UNRESOLVED` / 0 | Unavailable | `RAW_TIMESTAMP_EVIDENCE_NOT_RETAINED`; no BSE rule. |
| GLAND / `NSE:INE068V01023` | 18 | Not retained | `TIMEZONE_UNRESOLVED` / 0 | Unavailable | `RAW_TIMESTAMP_EVIDENCE_NOT_RETAINED`; no BSE rule. |
| ICICIBANK / `NSE:INE090A01021` | 12 | Not retained | `TIMEZONE_UNRESOLVED` / 0 | Unavailable | `RAW_TIMESTAMP_EVIDENCE_NOT_RETAINED`; no BSE rule. |

Only `EXACT_FILING_TIMESTAMP_KNOWN` receipts are sent to the already existing
canonical session evaluator. This replay had none; therefore
`BEFORE_REGULAR_SESSION`, `DURING_REGULAR_SESSION`,
`AFTER_REGULAR_SESSION`, `NON_TRADING_DAY`, `SPECIAL_SESSION`,
`SESSION_TIMING_UNAVAILABLE`, `DAILY_BAR_EVENT_CONTAMINATED`, and resolved
previous/next session counts are all **0**. Filing-level unavailable outcomes
remain 329 timezone-unresolved and 3 timestamp-unavailable.

## Boundaries and continuation

`CANONICAL_FILING_TIMESTAMP_TIMEZONE_PROVENANCE = ACTIVE`

`FILING_TIMESTAMP_TIMEZONE_COVERAGE = UNAVAILABLE`

`HISTORICAL_SESSION_TIMING_COVERAGE = PARTIAL`

`INFLECTION_MARKET_REACTION = NOT_ACTIVE`

`INFLECTION_QUALIFICATION = NOT_ACTIVE`

No guessed IST, synthetic time, price adjustment, market reaction, or
qualification is introduced. The exact next bounded continuation is:

`INFLECTION_ACCOUNTING_ONLY_PROSPECTIVE_SHADOW_V1`

It is selected because market-event reaction is structurally blocked by
timezone provenance and unknown price-adjustment integrity, while any later
accounting-only work can remain prospective and separate from reaction,
qualification, and execution authority.
