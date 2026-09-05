# Canonical Market Session and Event Time V1

**Status: `IMPLEMENTED_CONTRACT / PARTIAL_FIRST_PARTY_COVERAGE / RESEARCH_ONLY / NON_EXECUTABLE`.**

This bounded foundation provides immutable, effective-dated, source-injected
facts about NSE Capital Market calendar days, exact special-session phases, and
an event's relationship to the **regular continuous** session. It does not
calculate a return, gap, volume reaction, benchmark-relative measurement,
sector-relative measurement, Inflection qualification, score, rank, signal, or
portfolio/execution action.

```text
filing source exchange != reaction trading venue
trading day != session-phase timing
regular continuous close != all exchange activity ended
event session != market reaction
```

All output objects are factual and fixed to `WATCH_ONLY / NON_EXECUTABLE`.
There is no storage, API, UI, provider, runtime-clock, portfolio, broker,
order, price, return, or volume dependency. This in-memory primitive creates
zero database records and a replay with equal evidence yields equal identities.

## Scope and source rule

The implementation is:

- `app/historical/canonical_market_session_event_time.py` — immutable
  contracts, deterministic construction, PIT visibility, calendar/phase
  resolution, adjacent-session lookup, and factual event alignment.
- `app/historical/nse_capital_market_session_evidence_2022_2026.py` — bounded
  first-party evidence catalogue with no network retrieval.

The required result-filing interval is **2022-05-13 through 2026-08-25**:
332 canonical `FINANCIAL_RESULTS` filings. The evidence catalogue covers whole
years **2022-01-01 through 2026-12-31**, avoiding an open-ended archive hunt.

Only first-party NSE Capital Market sources are catalogued. Annual holiday
circulars supply declared holidays; special-session circulars supply only the
exact special date and phases they state. The current NSE
[Market Timings](https://www.nseindia.com/static/market-data/market-timings)
page states normal-market 09:15–15:30 and separate post-close activity, but is
not backfilled into historical years.

| First-party family | Recovered evidence | V1 use |
| --- | --- | --- |
| NSE CM annual holiday circulars | [CMTR50560](https://archives.nseindia.com/content/circulars/CMTR50560.pdf) (2022), [CMTR54757](https://archives.nseindia.com/content/circulars/CMTR54757.pdf) (2023), [CMTR59722](https://archives.nseindia.com/content/circulars/CMTR59722.pdf) (2024), [CMTR65587](https://nsearchives.nseindia.com/content/circulars/CMTR65587.pdf) (2025), [CMTR71775](https://nsearchives.nseindia.com/content/circulars/CMTR71775.pdf) (2026) | Declared `HOLIDAY` dates only. |
| NSE Muhurat circulars | [CMTR54023](https://archives.nseindia.com/content/circulars/CMTR54023.pdf) (2022-10-24), [CMTR59124](https://nsearchives.nseindia.com/content/circulars/CMTR59124.pdf) (2023-11-12), [CMTR64628](https://nsearchives.nseindia.com/content/circulars/CMTR64628.pdf) (2024-11-01), [CMTR70319](https://nsearchives.nseindia.com/content/circulars/CMTR70319.pdf) (2025-10-21) | Exact `MUHURAT_TRADING` day and phases. |
| NSE Budget live-session circulars | [CMTR65729](https://nsearchives.nseindia.com/content/circulars/CMTR65729.pdf) (2025-02-01), [CMTR72349](https://nsearchives.nseindia.com/content/circulars/CMTR72349.pdf) (2026-02-01) | Exact `SPECIAL_TRADING_DAY` and regular-continuous phase. |
| Current NSE timing page | Current semantics | Never a historical phase rule. |

Each catalogued evidence record has deterministic identity, HTTPS primary-source
reference, publication-date provenance, and fingerprint. A source without an
exact publication time becomes PIT-visible only after its local publication
date; it is never presumed known earlier on that same date.

The June 2023 holiday amendment is retained separately: first-party
[CMPT57296](https://nsearchives.nseindia.com/content/circulars/CMPT57296.pdf)
quotes CMTR57285 and the June 28 to June 29 change. Its explicitly linked
replacement schedule becomes visible after June 27; historical queries before
that cutoff retain the original announcement. The fingerprints protect the
catalogued record content; they are not hashes of downloaded PDF bytes.

## Canonical calendar and phase contracts

`CanonicalMarketSessionCalendar` separately retains:

1. `AnnualTradingHolidaySchedule` — year, source, declared holidays;
2. `WeekdayTradingConvention` — source-backed effective range and explicit
   weekday set; and
3. `SpecialTradingDay` — exact `SPECIAL_TRADING_DAY` or `MUHURAT_TRADING`
   override, including an exceptional weekend.

`CanonicalTradingDay` has only these factual states:
`REGULAR_TRADING_DAY`, `HOLIDAY`, `WEEKEND_NON_TRADING`,
`SPECIAL_TRADING_DAY`, `MUHURAT_TRADING`, and `UNKNOWN`.

An annual holiday schedule alone does not prove an ordinary historical weekday
was a trading day. Weekday derivation requires a separately retained,
first-party, effective-dated weekday convention. A special circular overrides
a weekday or holiday only for its exact date. Missing, future, outside-coverage,
or conflicting evidence stays unavailable; conflicting source order never
selects a winner.

`EffectiveSessionPhaseTiming` is independent of the day calendar. It contains
effective dates, eligible day state, phase type, local start/end,
`Asia/Kolkata`, source identity/fingerprint, and a deterministic fingerprint.
The limited factual vocabulary is `PRE_OPEN`, `SPECIAL_PRE_OPEN`,
`REGULAR_CONTINUOUS`, `CLOSING_SESSION`, `CLOSING_AUCTION`, `BLOCK_DEAL`,
`AUCTION`, and `SPECIAL_SESSION`.

For Inflection alignment the critical boundary is `REGULAR_CONTINUOUS`:

```text
event < regular continuous open       -> BEFORE_REGULAR_SESSION
open <= event < regular close         -> DURING_REGULAR_SESSION
event >= regular continuous close      -> AFTER_REGULAR_SESSION
```

The close is exclusive. A later closing/post-close phase cannot turn an
after-regular event into a during-regular event. Conflicting effective phase
records return `EVIDENCE_CONFLICTED` and retain the conflicting source IDs.

## Event timestamp and alignment facts

`CanonicalEventTimestamp` preserves original timestamp text and timezone
provenance, a separately validated aware timestamp and IANA timezone when
available, source identity/fingerprint, and one factual state:
`EXACT_TIMEZONE_AWARE`, `EVENT_TIMESTAMP_UNAVAILABLE`, or
`TIMEZONE_UNRESOLVED`. An offset-bearing value with an unknown or mismatched
timezone identifier is rejected; it is not silently labelled IST.
Ambiguous raw timestamps remain in provenance while the normalized timestamp
remains unavailable. Known special dates retain `SPECIAL_SESSION` with an
explicit `SESSION_PHASE_TIMING_UNAVAILABLE` reason when no exact phase is
available; exact special phase boundaries remain descriptive.

`EventSessionAlignment` takes the canonical instrument and an explicit **NSE
Capital Market** venue. It does not take a filing exchange as a selector: a BSE
filing cannot make BSE the reaction venue for an NSE security. The result is
one of `BEFORE_REGULAR_SESSION`, `DURING_REGULAR_SESSION`,
`AFTER_REGULAR_SESSION`, `NON_TRADING_DAY`, `SPECIAL_SESSION`,
`SESSION_TIMING_UNAVAILABLE`, `EVENT_TIMESTAMP_UNAVAILABLE`,
`TIMEZONE_UNRESOLVED`, or `EVIDENCE_CONFLICTED`.

Previous/next sessions are emitted only if every intervening date resolves; no
calendar-day substitute is used. `DURING_REGULAR_SESSION` exposes the factual
`DAILY_BAR_EVENT_CONTAMINATED` readiness state and still does not calculate a
return.

## Initial coverage audit

At explicit `as_of=2026-09-05T00:00:00Z`, the bounded catalogue produces:

| Measure | Count / state |
| --- | ---: |
| Calendar days in range | 1,826 |
| `HOLIDAY` | 68 |
| `MUHURAT_TRADING` | 4 |
| `SPECIAL_TRADING_DAY` | 2 |
| `UNKNOWN` ordinary/weekend dates | 1,752 |
| Special dates with exact phase timing | 6 |
| Exact phase records | 14 |
| Known special dates with timing unavailable | 0 |
| Historical normal-weekday regular timing | 0 retained rules |
| Timing-rule groups | 6 exact special-session groups |

Exact timing covers 2022-10-24, 2023-11-12, 2024-11-01, and 2025-10-21 (three
phases each), plus 2025-02-01 and 2026-02-01 (one regular-continuous phase
each). Ordinary historical weekdays still never receive invented hours.

`HISTORICAL_SESSION_TIMING_COVERAGE = PARTIAL`

## Current Inflection re-audit

The production audit is read-only. All 332 in-scope financial-result filings
are BSE sourced. 329 retain `TIMESTAMP_EXCHANGE_LOCAL_ASSUMPTION`; 3 retain
`SOURCE_PUBLICATION_TIMESTAMP_UNKNOWN` and only a system-first-observed time.
None can construct an `EXACT_TIMEZONE_AWARE` event timestamp today.

| Event-session result | Count |
| --- | ---: |
| `BEFORE_REGULAR_SESSION` / `DURING_REGULAR_SESSION` / `AFTER_REGULAR_SESSION` | 0 / 0 / 0 |
| `NON_TRADING_DAY` / `SPECIAL_SESSION` / `SESSION_TIMING_UNAVAILABLE` | 0 / 0 / 0 |
| `TIMEZONE_UNRESOLVED` | 329 |
| `EVENT_TIMESTAMP_UNAVAILABLE` | 3 |
| `EVIDENCE_CONFLICTED` / `DAILY_BAR_EVENT_CONTAMINATED` / next-session resolved | 0 / 0 / 0 |

| Instrument | Result filings | Timestamp status | Trading venue | Event class | Previous / next | Daily-bar state |
| --- | ---: | --- | --- | --- | --- | --- |
| APARINDS / `NSE:INE372A01015` | 19 | Local-time assumption | NSE CM | `TIMEZONE_UNRESOLVED` | Unavailable | `NOT_EVALUABLE` |
| DEEPINDS / `NSE:INE0FHS01024` | 14 | Local-time assumption | NSE CM | `TIMEZONE_UNRESOLVED` | Unavailable | `NOT_EVALUABLE` |
| GENUSPOWER / `NSE:INE955D01029` | 18 | Local-time assumption | NSE CM | `TIMEZONE_UNRESOLVED` | Unavailable | `NOT_EVALUABLE` |
| GLAND / `NSE:INE068V01023` | 18 | Local-time assumption | NSE CM | `TIMEZONE_UNRESOLVED` | Unavailable | `NOT_EVALUABLE` |
| ICICIBANK / `NSE:INE090A01021` | 12 | Local-time assumption | NSE CM | `TIMEZONE_UNRESOLVED` | Unavailable | `NOT_EVALUABLE` |

## Boundaries and next decision

This slice does not repair `UNKNOWN` price adjustment basis, select a benchmark
or sector index, derive a market reaction, or activate Inflection. It retains
`FACT -> DATA -> INTERPRETATION -> INFERENCE` and stops at event-time facts.

`CANONICAL_MARKET_SESSION_CALENDAR = IMPLEMENTED_PARTIAL / NOT_ACTIVE_FOR_GENERAL_HISTORICAL_COVERAGE`

`INFLECTION_MARKET_REACTION = NOT_ACTIVE`

`INFLECTION_QUALIFICATION = NOT_ACTIVE`

The single dominant next bounded continuation is:

`CANONICAL_FILING_TIMESTAMP_TIMEZONE_PROVENANCE_V1`

It must recover or validate source timestamp timezone semantics for canonical
filing lineage. It must not substitute observation time, assume IST, calculate
a market reaction, or repair price-adjustment integrity.
