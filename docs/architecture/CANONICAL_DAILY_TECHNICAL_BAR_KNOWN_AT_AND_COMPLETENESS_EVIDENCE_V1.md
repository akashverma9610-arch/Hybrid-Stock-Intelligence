# Canonical Daily Technical Bar Known-at and Completeness Evidence V1

**Status: `CANONICAL_DAILY_TECHNICAL_TEMPORAL_EVIDENCE = ACTIVE / PURE_READ_ONLY_RESOLVER / NO_STORAGE_MIGRATION / STRICT_PRODUCTION_PIT_BINDING = NOT_ACTIVE`.**

## Scope and boundary

This slice adds a pure, source-injected temporal receipt for an existing daily
`CanonicalOHLCVBar`.  It reuses the canonical technical-bar contract and the
first-party NSE session calendar; it creates no alternate OHLCV store, provider
call, cache, migration, API/UI, score, horizon policy, portfolio mutation,
broker/order capability, or execution authority.

`stored daily bar != strict PIT-ready daily bar`.

The resolver accepts explicit source session-date and source-availability
evidence. It retains `received_at` separately and never interprets it as market
known-at. It preserves `FACT -> DATA -> INTERPRETATION -> INFERENCE`: this is
temporal data validation only, not a technical interpretation.

## Daily temporal receipt

`DailyTechnicalBarTemporalReceipt` carries canonical bar/instrument and source
identity; explicit session date and calendar result; regular-session close;
session and source-timing evidence identifiers/fingerprints; completeness and
known-at states; strict PIT usability; source exchange/provider/received
timestamps; adjustment state; volume readiness; reasons; and a deterministic
fingerprint.

| Area | Rule |
| --- | --- |
| Session identity | Source must state the exact exchange session date; a stored timestamp/date is not silently converted into one. The calendar verifies regular, special and Muhurat sessions. |
| Completion | `CLOSED` requires an existing canonical session, an exact regular-session close, a source rule proving availability after that close (or explicit publication time), and no conflicting evidence. |
| Known-at | Explicit publication time must be no earlier than session close. A source contract may derive it exactly at session close only when that contract is itself identified and fingerprinted. Otherwise it is `SOURCE_TIMING_UNRESOLVED`. |
| Current session | Before known session close it is `IN_PROGRESS`, even if an OHLC row exists. |
| Historical bars | Age never supplies a timestamp. No midnight/23:59:59 backfill exists. |
| PIT | Strict use requires `CLOSED`, resolved known-at, and `known_at <= evaluation_as_of`. |
| Volume / adjustment | Volume readiness and adjustment status remain independent of temporal readiness. A price bar can be temporally usable with `VOLUME_NOT_READY` or `UNKNOWN` adjustment. |

Holiday/weekend bars are `EVIDENCE_CONFLICTED` unless calendar evidence says a
special/Muhurat session. Special weekend sessions are valid only through their
exact source-backed calendar override. Missing calendar data, source session
date, timing semantics, or phase close remains fail-closed.

## Retained-source audit

Read-only audit of `historical_bars` found 1,545,139 `1D` rows across 2,561
instruments (2023–2026):

| Source family | Rows | Stored temporal fields | Strict-PIT conclusion |
| --- | ---: | --- | --- |
| Upstox `upstox-history-v3` | 1,518,604 | Exchange/provider timestamp and `received_at` on every row | `BLOCKED`: Upstox V3 documents candle timestamp as the **start** of its timeframe, while the current adapter uses it as `end_time`; stored rows have no governed source-session anchor or publication/availability receipt. |
| yfinance `yfinance-history-v1` | 26,487 | Provider date/timestamp and `received_at` | `BLOCKED`: secondary-research source; no approved session/publication timing contract. |
| NSE official full bhavcopy | 48 | Exchange timestamp and retrieval time | `BLOCKED`: the retained row has no immutable official publication timestamp/session receipt. NSE confirms EOD bhavcopy is generated after the trading day, but a generic retrieval timestamp is not historical market-known time. |

All retained daily rows therefore remain `STRICT_PIT_USABILITY = BLOCKED` in
this V1 audit: **0 / 1,545,139** can be newly certified under strict temporal
PIT without supplying source timing/session evidence. This is not a claim that
the historical prices are false; it is a refusal to retrospectively invent
when they became usable.

The bounded 2022–2026 first-party calendar intentionally has incomplete
ordinary-weekday evidence. It can validate its explicit special/Muhurat
sessions, but cannot establish universal historical regular-session identity
or close timing for this data population.

References: [Upstox Historical Candle Data V3](https://upstox.com/developer/api-documentation/v3/get-historical-candle-data/)
defines candle timestamp as the start of its timeframe; [NSE EOD data](https://www.nseindia.com/static/market-data/eod-historical-data-subscription)
describes EOD files as generated at the end of each trading day; the NSE CM
snapshot specification records bhavcopy generation around 17:00 on trading
days. These sources do not authorise converting an HSI fetch/receive timestamp
into a historical market-known timestamp.

## Parity and derivation gates

NIFTY 50 and NIFTY 500 have retained daily bars (746 and 1,673 respectively)
but share the same missing source timing/session evidence; broad benchmark
parity is `NOT_READY`. Sector indices are likewise daily-only and have no
temporal shortcut. Relative strength must not compare a future-certified stock
bar with a temporally unresolved benchmark/sector bar.

Weekly and monthly derivation remain `NOT_READY`: required constituent session
identity, closed status, known-at, exact period coverage, and compatible
adjustment lineage are not available for the retained daily population. Rules
4 and 14 remain `INSUFFICIENT_DATA`; daily data is never relabelled as weekly.

## Final classification

| Classification | State | Reason |
| --- | --- | --- |
| Daily session identity | `NOT_READY` | retained source session-date receipt absent; ordinary calendar evidence incomplete |
| Daily completeness | `NOT_READY` | exact session close and source availability proof absent |
| Daily known-at | `NOT_READY` | fetch/ingest time is not market known-at |
| Daily strict PIT usability | `NOT_READY` | 0 retained rows certified by this contract |
| Daily volume readiness | `PARTIAL` | 11,279 null/zero-volume rows; price validity is separate |
| Daily adjustment readiness | `PARTIAL` | 1,518,652 `UNKNOWN`, 26,487 `RAW` |
| Benchmark / sector temporal parity | `NOT_READY` | same source/session/timing gaps |
| Weekly / monthly derivation gates | `NOT_READY` | daily temporal and adjustment prerequisites incomplete |

## Follow-on source semantics

[Canonical Daily Source Session and Publication Semantics V1](CANONICAL_DAILY_SOURCE_SESSION_AND_PUBLICATION_SEMANTICS_V1.md)
is now active as a source-facts and forward-adapter boundary. It preserves raw
Upstox V3 interval-start evidence while isolating its legacy mislabelled
`end_time`, repairs future adapter capture without fabricating a daily end, and
permits only a forward HSI-observed known-at receipt. It does not rewrite
retained rows or certify historical publication time.

The remaining dominant repair is
`CANONICAL_NSE_ORDINARY_SESSION_IDENTITY_AND_CLOSE_EVIDENCE_V1`: effective-dated
first-party ordinary-session identity and close evidence only. Adjustment
repair, weekly/monthly derivation, and horizon policy remain out of scope.

`4H_SEMANTICS = UNRESOLVED`
`HORIZON_SPECIFIC_TECHNICAL_POLICY = NOT_ACTIVE`
`MULTI_TIMEFRAME_TECHNICAL_ORCHESTRATOR = NOT_ACTIVE`
