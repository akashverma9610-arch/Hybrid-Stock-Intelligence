# Inflection Event-Session and Market-Reaction Policy Proposal V1

**Status: `PROPOSED / NOT_APPROVED / NOT_ACTIVE / RESEARCH_ONLY / NON_EXECUTABLE`.**

## Purpose and non-negotiable separation

`INFLECTION_EVENT_SESSION_AND_MARKET_REACTION_POLICY_PROPOSAL_V1` defines
only the future deterministic evidence contract needed to relate a verified
financial-result filing to market data. It does not implement a reaction
calculator, choose a window, assign a threshold, or qualify an Inflection.

```text
official filing timestamp
  != canonical exchange session
  != clean reaction window
  != price or volume confirmation
  != surprise
  != Inflection qualification
```

This proposal consumes the factual
[Inflection Testable Derived Metrics and Event Alignment V1](INFLECTION_TESTABLE_DERIVED_METRICS_AND_EVENT_ALIGNMENT_V1.md)
receipt when, and only when, a later approved contract supplies the additional
session and price-integrity evidence. It preserves `FACT -> DATA ->
INTERPRETATION -> INFERENCE`: a return or a volume ratio would remain data,
not an interpretation or an action.

No `INFLECTION_CANDIDATE`, `INFLECTION_CONFIRMED`, `STRONG_INFLECTION`, score,
rank, BUY/SELL/HOLD/ADD/TRIM/EXIT/ROTATE instruction, target, stop, portfolio
mutation, broker/order capability, API, UI, persistence, or signal lifecycle
work is authorised here.

## Current repository evidence and readiness audit

The audit below is read-only and records what the repository actually has; it
does not promote a partial input into an event-reaction contract.

| Domain | Existing canonical input | Audit finding | Policy consequence |
| --- | --- | --- | --- |
| Date-only session guard | `NseTradingSessionCalendar` protocol; `ExchangeCalendar` | Both accept a caller-supplied day decision. `ExchangeCalendar` is weekday plus explicitly supplied holidays; [Exchange Calendar](../EXCHANGE_CALENDAR.md) explicitly has no live holiday source. | Not a historical exchange-session schedule. |
| Historical session identity | Dated NSE MII session-point receipts | Exact source-labelled dates can be retained, but [BRSR Issuer Anchor Session-Master Backfill V1](BRSR_ISSUER_ANCHOR_SESSION_MASTER_BACKFILL_V1.md) confirms no durable NSE holiday dataset or intraday boundary. | Cannot classify a filing time as before/during/after regular trading. |
| Live market state | `MarketSessionState` | `PRE_OPEN`, `OPEN`, and `POST_CLOSE` describe runtime feed state, not historical exchange schedules or filing-event evidence. | Must not be backfilled into history. |
| Official session source | NSE market-timing/holiday pages and exchange circulars | Official sources publish holiday and timing information, including separately notified Muhurat sessions; they are not retained as versioned historical session records. | Acquisition and immutable primary-source retention are required before use. |
| Financial-result filings | 332 BSE `FINANCIAL_RESULTS` filings; 9 current exact Inflection links per metric | The five target filing payloads retain `TIMESTAMP_EXCHANGE_LOCAL_ASSUMPTION`; no target timestamp is an approved session classification. | A timestamp alone cannot choose a reaction session. |
| Daily OHLCV | 1,545,139 daily bars: 2 broad indexes, 2,551 equities, 8 sector indexes | 1,518,652 bars are `UNKNOWN` adjustment status; 26,487 are `RAW`. | Daily reaction data is unavailable until a declared compatible price basis is approved. |
| Broad benchmarks | NIFTY 50 and NIFTY 500 daily bars | NIFTY 50 is `UNKNOWN`; NIFTY 500 contains both `RAW` and `UNKNOWN` bars. No event-reaction benchmark selector exists. | No benchmark-relative return. |
| Sector inputs | PIT taxonomy, official sector-index registry/mappings, 8 daily sector-index series | The repository has useful components but no approved PIT event-date stock-to-sector-index selector. | No sector-relative return or current-sector backfill. |
| Delivery | Official NSE delivery artifacts/observations | 4 delivery observations exist for each named target, far short of a candidate 20/60-session baseline. | Optional future context only; not an Inflection V1 prerequisite. |

The official NSE [Market Timings & Holidays](https://www.nseindia.com/resources/exchange-communication-holidays)
page is a primary source for future acquired records. It explicitly distinguishes
holiday notices from separately notified Muhurat timings. The official NSE
[All Reports](https://www.nseindia.com/all-reports) page lists delivery and
bhavcopy reports. These source pages are references for future acquisition,
not a substitute for retained, versioned historical evidence.

## Proposed canonical exchange-session contract

The next implementation may create a single immutable, primary-source-backed
`CanonicalExchangeSession` contract. This proposal does not create it.

| Candidate field | Required future rule |
| --- | --- |
| `exchange`, `session_date`, `calendar_version` | Exact exchange and local calendar date; no generic NSE/BSE substitution. |
| `timezone_id` | IANA timezone from retained source/governed contract, not a runtime locale. |
| `session_type` | One of `REGULAR`, `HOLIDAY`, `SPECIAL`, `MUHURAT`, `SHORTENED`, or `UNKNOWN`. `UNKNOWN` is not regular. |
| `trading_state` | Explicit trading/non-trading state derived from the retained exchange record. |
| `regular_session_open`, `regular_session_close` | Timezone-aware timestamps only when the exact session record supports them; absent for holiday/unknown and never copied from a normal day. |
| `session_phases` | Canonically ordered, source-backed phase identities and bounds (for example pre-open, continuous, or a separately declared closing auction). A missing phase schedule is not reconstructed from a default session. |
| `special_session_state` | Exact special/Muhurat/shortened-session evidence and its declared boundary, otherwise `UNKNOWN`. |
| `source`, `source_reference`, `source_document_fingerprint` | Official exchange circular/page/document identity and content fingerprint. |
| `published_at` and `known_at` | Retain both only where source evidence provides them; `known_at` cannot precede source publication/observation. |
| `session_id`, `fingerprint` | Deterministic identity over the above factual fields; acquisition/runtime time excluded. |

Missing, duplicated/conflicting, non-official, timezone-naive, or
historically unavailable session evidence must produce `SESSION_UNKNOWN`, not
a regular-hours default. A special session is never treated as regular merely
because a daily bar exists.

This phase-level requirement is deliberate. The official
[SEBI closing-auction circular](https://www.sebi.gov.in/legal/circulars/jan-2026/introduction-of-closing-auction-session-cas-in-the-equity-cash-segment-and-certain-modifications-in-the-pre-open-auction-session_99122.html)
illustrates why a static normal-day open/close assumption cannot describe every
historical price-formation session. The circular is source context only; no
phase timing from it is retroactively inserted into HSI.

## Proposed event-time and first-clean-session semantics

These are research candidates, not approved reaction rules. They may be
assigned only after exact filing timestamp, exchange identity, and a
PIT-visible `CanonicalExchangeSession` all validate.

| Candidate event-time state | Preconditions | Candidate first clean daily session | Daily-bar treatment |
| --- | --- | --- | --- |
| `BEFORE_REGULAR_SESSION` | Filing timestamp is before a retained regular open on a `REGULAR` session. | Same session, subject to price-integrity checks. | Candidate clean. |
| `DURING_REGULAR_SESSION` | Timestamp is within retained regular boundaries. | Next regular session. | Filing-day daily bar is `DAILY_BAR_EVENT_CONTAMINATED`; it contains pre- and post-information trading. |
| `AFTER_REGULAR_SESSION` | Timestamp is after a retained regular close. | Next regular session. | Filing-day close is not a post-information daily reaction. |
| `NON_TRADING_DAY` | Retained session says non-trading. | Next regular session. | No filing-day trading reaction. |
| `SPECIAL_SESSION` | Exact session is special, Muhurat, or shortened. | Unavailable unless a later approved special-session rule exists. | Fail closed. |
| `SESSION_UNKNOWN` | Calendar/session record missing, conflicted, or non-comparable. | Unavailable. | Fail closed. |
| `TIMESTAMP_UNAVAILABLE` | Official filing timing is absent or not source-verifiable. | Unavailable. | Fail closed. |

The `DURING_REGULAR_SESSION` rule exists because a daily OHLCV bar cannot
separate prices formed before a filing from those formed after it. It does not
assert that the next session measures a pure causal effect; it only avoids
fabricating intraday precision from daily data.

## Proposed price, gap, benchmark, sector, and volume dimensions

All dimensions remain separate factual candidates. None is a signal direction,
confirmation, surprise proxy, or qualification.

### Price integrity prerequisite

A future reaction record requires one `HistoricalPriceIntegrity` assessment
per involved instrument and a declared `PriceAdjustmentBasis`. It must reject:

- `UNKNOWN` or mixed `AdjustmentStatus` values;
- `PriceAdjustmentBasis.UNKNOWN`;
- security/ISIN continuity mismatch at the evaluated session;
- missing, stale, invalid, suspended, or zero/invalid-volume bars as relevant
  to the dimension;
- a corporate action whose effective date contaminates the reference or end
  session; and
- stock, benchmark, or sector series with different or unverified bases.

The existing historical-integrity service already fails closed on adjustment
mismatch; this proposal does not redefine it. Raw and adjusted series must
never be silently mixed.

### Candidate window vocabulary

Let `S0` be the candidate first clean regular session and `S-1` its immediately
preceding canonical regular session. The following definitions are candidates
for empirical review only:

| Dimension | Candidate factual formula | Required future evidence |
| --- | --- | --- |
| `GAP_RETURN` | `open(S0) / close(S-1) - 1` | Valid same-basis stock bars for `S-1` and `S0`; no corporate-action contamination. |
| `SESSION_RETURN` | `close(S0) / open(S0) - 1` | Valid `S0` open and close. |
| `MULTI_SESSION_RETURN_1D` | `close(S0) / close(S-1) - 1` | Same as gap/session input, with explicit close convention. |
| `MULTI_SESSION_RETURN_3D` | `close(S2) / close(S-1) - 1` | `S0`, `S1`, `S2` complete and valid. |
| `MULTI_SESSION_RETURN_5D` | `close(S4) / close(S-1) - 1` | `S0` through `S4` complete and valid. |
| `MULTI_SESSION_RETURN_20D` | `close(S19) / close(S-1) - 1` | `S0` through `S19` complete and valid. |
| `VOLUME_RATIO_20_MEAN` | `volume(S0) / mean(volume(S-20..S-1))` | 20 valid, comparable prior-session volumes. |
| `VOLUME_RATIO_20_MEDIAN` | `volume(S0) / median(volume(S-20..S-1))` | Same 20-session evidence. |
| `VOLUME_RATIO_60_MEDIAN` | `volume(S0) / median(volume(S-60..S-1))` | 60 valid, comparable prior-session volumes. |

The formulae define a candidate measurement convention, not a selected window
or threshold. No baseline choice, positive/negative cutoff, return ranking, or
Cartesian optimisation is authorised. `GAP_RETURN`, `SESSION_RETURN`, and
multi-session drift are deliberately separate so a later
`OPENING_GAP_AND_OVERNIGHT_INTELLIGENCE` capability can reuse the same session
and price-reference primitives without duplicating them.

### Relative dimensions

`BENCHMARK_RELATIVE_RETURN = StockReturn - BenchmarkReturn` and
`SECTOR_RELATIVE_RETURN = StockReturn - SectorIndexReturn` are future factual
definitions only. Each requires the same declared window convention, exact
aligned session identities, compatible price integrity/basis, and immutable
lineage for all bars.

Broad benchmark selection is unavailable until a separately approved,
versioned event-reaction selector supplies one canonical identity at the
event's as-of. Sector-relative measurement additionally requires a PIT-valid
stock-to-sector-index mapping at the event date. Current rankings, current
taxonomy, an index that merely looks related, or an index ETF cannot be
substituted backward.

## Maturity, insufficiency, and future receipt

A future window must distinguish `NOT_STARTED`, `PARTIALLY_MATURE`, `MATURE`,
`DATA_MISSING`, and `NON_COMPARABLE`. A 5D window with only two completed
sessions is `PARTIALLY_MATURE`, not a negative reaction or a failed strategy.

The smallest future immutable `InflectionMarketReactionReceipt` would retain:

- acceleration receipt identity/fingerprint and exact official filing lineage;
- filing timestamp and canonical session identity/fingerprint;
- event-time state, first-clean-session identity, and contamination state;
- reference and end bar identities/fingerprints, window definition/version,
  stock measurement, and maturity state;
- optional benchmark/sector identities, measurements, and only their exact
  PIT mappings when independently available;
- optional volume baseline bar identities, baseline definition, and ratio;
- declared price-integrity assessments and corporate-action lineage;
- policy ID/version/fingerprint, source provenance, deterministic identity,
  and content fingerprint.

It would contain no score, threshold result, action, expectation/surprise,
guidance, recommendation, or execution field. Persistence is not authorised
by this proposal.

## Five-target factual readiness

| Target | Filing timestamp retained | Session classification | Stock bars | Benchmark / sector / volume | Exact blocker |
| --- | --- | --- | --- | --- | --- |
| APARINDS | Yes; BSE local-time assumption lineage | Unavailable | 748 daily bars, `UNKNOWN` basis, no zero volume | Broad/sector relative unavailable; 4 delivery observations | Canonical session and compatible price basis absent. |
| DEEPINDS | Yes; BSE local-time assumption lineage | Unavailable | 748 daily bars, `UNKNOWN` basis, no zero volume | Same; 4 delivery observations | Same; no reaction inference despite factual filing data. |
| GENUSPOWER | Yes; BSE local-time assumption lineage | Unavailable | 748 daily bars, `UNKNOWN` basis, no zero volume | Same; 4 delivery observations | Same. |
| GLAND | Yes; BSE local-time assumption lineage | Unavailable | 748 daily bars, `UNKNOWN` basis, no zero volume | Same; 4 delivery observations | Same. |
| ICICIBANK | Yes; BSE local-time assumption lineage | Unavailable | 748 daily bars, `UNKNOWN` basis, no zero volume | Same; 4 delivery observations | Same reaction blocker; non-financial Inflection accounting remains separately `NOT_APPLICABLE`. |

## Explicitly blocked domains and future validation

`CANONICAL_CONSENSUS_DATA_MISSING`, `REVISION_DATA_MISSING`, and
`CANONICAL_GUIDANCE_DATA_MISSING` remain blocked. Price or volume cannot stand
in for any of them.

Future empirical research must ask whether a declared reaction measurement
adds incremental information about accounting-acceleration persistence or
quality beyond the accounting receipt. It must not tune reaction thresholds for
historical return. Any study needs PIT-complete session, adjustment,
benchmark, sector, corporate-action, and outcome lineage first.

## Exact next bounded continuation

The dominant missing dependency is an immutable primary-source session record.
The exact next bounded continuation is:

`CANONICAL_MARKET_SESSION_CALENDAR_AND_EVENT_TIME_V1`

It must acquire and validate exchange-specific historical session records,
including holiday, special/Muhurat, and shortened-session evidence where
available, before an event-time classifier or market-reaction research shadow
is proposed. It must not activate Inflection qualification.
