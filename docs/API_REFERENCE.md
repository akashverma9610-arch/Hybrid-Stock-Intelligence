# API reference

All analytical routes are read only and live under `/api/v1` unless noted
otherwise. The API has no authentication or user tenancy yet, so
the portfolio boundary represents one injected local portfolio context.

## Local/private connection settings

`GET /api/v1/connections` and `GET /api/v1/connections/kotak-neo` return
secret-free profiles and safe field metadata. The isolated local-only writes
are `PUT /api/v1/connections/kotak-neo`, `POST
/api/v1/connections/kotak-neo/test`, and `DELETE
/api/v1/connections/kotak-neo/credentials`. Save returns configured flags only;
partial updates preserve omitted secrets. Test performs only the smallest
supported market-data read and cannot promote/activate strategy, trade, or
access an account. These unauthenticated routes are not public-ready.
The connection test response retains `mode`, safe test symbol,
`canonical_normalization`, and freshness. A quote-only success means one
canonical Kotak quote was resolved, normalized, quality-checked, and accepted;
it does not imply account/session/trading access.

For a non-Swagger local setup surface, `GET /setup/kotak-neo` renders a small
password-input page. Its buttons call only the same isolated save/test/clear
connection routes; the page does not receive or display saved credential values.

## `GET /health`

Returns a lightweight liveness response:

```json
{"status":"ok"}
```

## `GET /api/v1/portfolio`

Returns the current immutable portfolio snapshot supplied by the application
query service. Synthetic response example:

```json
{
  "portfolio_id": "example-local-portfolio",
  "as_of": "2026-08-20T10:00:00Z",
  "invested_value": "10000",
  "marked_value": "12000",
  "cash": "10000",
  "unrealized_pnl": "2000",
  "realized_pnl": "0",
  "total_equity": "22000",
  "portfolio_heat": "0.13636",
  "holding_count": 1,
  "data_status": "COMPLETE",
  "warnings": []
}
```

All money, price, quantity, allocation, and heat values preserve `Decimal`
semantics and are serialized as JSON strings. If marks are unavailable, marked
values and total equity are `null` with explicit warnings; no substitute price
is fabricated.

## `GET /api/v1/portfolio/holdings`

Returns a list of existing snapshot holdings. `symbol` and `exchange` are
`null` until an instrument-display mapping is introduced; `instrument_id` is
always retained. Each item retains the snapshot `data_as_of` timestamp.

## `GET /api/v1/portfolio/summary`

Returns the same canonical snapshot totals with the largest existing position
and sector allocation where their precomputed exposure data is available.

## `GET /api/v1/market/regime`

Returns an existing injected `MarketRegimeResult`; the route does not classify
markets. Synthetic response example:

```json
{
  "result_id": "example-market-regime",
  "benchmark_instrument_id": "NIFTY50",
  "regime": "bull",
  "calculated_at": "2026-09-01T15:30:00Z",
  "data_as_of": "2026-09-01T15:15:00Z",
  "confidence": 0.87,
  "status": "valid",
  "conditions": ["benchmark_return=0.040000", "trend=uptrend"],
  "evidence_ids": [],
  "input_observation_ids": ["nifty-bar-1"],
  "warnings": []
}
```

The `regime` value is the existing `MarketRegime` enum value. Confidence is
separate from any future score. Stored timestamps and provenance IDs are
returned unchanged. Until a current analysis source is injected, the route
returns `503 MARKET_REGIME_UNAVAILABLE`.

## `GET /api/v1/sectors` and `GET /api/v1/sectors/{sector_id}`

Return existing injected sector rotation diagnostics in their source order; the
API does not rerank sectors or calculate sector phases. A synthetic item is:

```json
{
  "sector_id": "energy",
  "sector_name": "Energy",
  "phase": "ROTATING_IN",
  "rank": 2,
  "relative_strength": "0.125",
  "score": null,
  "confidence": 0.82,
  "calculated_at": "2026-09-01T15:30:00Z",
  "data_as_of": "2026-09-01T15:15:00Z",
  "status": "eligible",
  "evidence_ids": ["example-sector-evidence"],
  "input_observation_ids": ["example-sector-bar"],
  "warnings": ["PROXY_INFERENCE_ONLY"]
}
```

Relative strength retains `Decimal` JSON-string encoding. Phase values are the
existing deterministic sector-rotation result, based on price/RS proxies and
not factual fund-flow claims. An unknown injected sector returns `404
SECTOR_NOT_FOUND`; an unavailable source returns `503
SECTOR_ANALYSIS_UNAVAILABLE`.

## `GET /api/v1/stocks/{symbol}/analysis`

Returns an existing injected analytical aggregate for one stock. It is a compact
read-only presentation of existing diagnostics, Decision Scorecard, canonical
gate evaluation, and available analytical sections. Synthetic response excerpt:

```json
{
  "identity": {"symbol": "COFORGE", "exchange": "NSE", "name": "Coforge Limited", "sector": "TECHNOLOGY", "industry": "IT Services"},
  "data": {"analysis_timestamp": "2026-10-01T15:30:00Z", "data_as_of": "2026-10-01T15:15:00Z", "status": "PARTIAL", "warnings": ["STALE_PRICE_DATA"], "provenance_ids": ["snapshot-1"]},
  "market_context": {"market_regime": "selective_bull", "sector_phase": "ROTATING_IN", "sector_rank": 3},
  "diagnostics": {"total_count": 61, "pass_count": 45, "fail_count": 4, "neutral_count": 8, "unknown_count": 4, "items": []},
  "decision": {"final_score": "8.20", "score_status": "COMPLETE", "confidence": 0.74, "components": [], "warnings": []},
  "execution_gates": null
}
```

Score and confidence are separate values. Gate outcomes are returned unchanged,
including blocked or insufficient states. Technical, fundamentals, research,
valuation, trade-structure, and liquidity sections contain only available
existing diagnostics. The API does not calculate indicators, scorecards, gates,
patterns, R:R, or fundamentals.

The route uses local case/whitespace normalization only (`coforge` resolves to
`COFORGE`). There is no current NSE/BSE/Yahoo exchange-suffix mapping, so
`COFORGE.NS` is rejected as `422 INVALID_SYMBOL`. An unknown canonical local
symbol returns `404 STOCK_NOT_FOUND`; an unavailable analysis source returns
`503 STOCK_ANALYSIS_UNAVAILABLE`.

## Signals and simulated paper trades

`GET /api/v1/signals` returns injected, stored signal-lifecycle records. It
supports deterministic `symbol`, `status`, `strategy_version`, `limit`, and
`offset` filtering; an empty query is a normal `200` response. `GET
/api/v1/signals/{signal_id}` returns its frozen score, confidence, gate
reference, trade structure, warnings, and provenance where those records are
available. For example, `planned_entry`, `structural_stop`, targets, and R:R
are stored plan values, not HTTP calculations.

`GET /api/v1/paper-trades` and `GET /api/v1/paper-trades/{trade_id}` return
stored simulated paper-trade records. Open or waiting trades legitimately have
`null` exit, P&L, and realized-R fields. Completed outcomes retain their exact
state, MFE/MAE, R multiple, timestamps, and frozen bar/provenance IDs.

`GET /api/v1/paper-trades/performance` exposes an existing stored canonical
paper-trade `PerformanceReport` only. A synthetic excerpt is:

```json
{"report_id":"example-performance","strategy_version":"example/1","total_trades":12,"win_rate":"0.58","average_r":"0.72","max_drawdown":"-0.08","warnings":["SMALL_SAMPLE"]}
```

All price, quantity, P&L, R, and metric `Decimal` values are JSON strings.
Signals/paper sources which are not configured return safe `503`
`SIGNALS_UNAVAILABLE`, `PAPER_TRADES_UNAVAILABLE`, or
`PERFORMANCE_UNAVAILABLE` envelopes; missing IDs return `404`. These routes
never generate a signal, trigger/fill/exit a trade, contact a broker, or modify
a portfolio or strategy.

## Errors

Unavailable local portfolio data returns a safe `503 PORTFOLIO_UNAVAILABLE`
envelope. A future context-specific missing portfolio may return safe `404
PORTFOLIO_NOT_FOUND`. Error responses include `X-Request-ID` and never expose
stack traces.

## Not exposed yet

There are no domain-mutation, buy, sell, rebalance, rotation-execution,
broker-sync, or live-market routes. The isolated local/private connection
configuration writes above do not alter domain state. `GET /api/v1/portfolio/rotation` is intentionally
deferred: the existing rotation evaluation is immutable and ID-addressable, but
the repository has no coherent current-local-portfolio rotation-query contract.

There is no live NSE/BSE or news provider. Market/sector timestamps and
provenance represent only stored or injected analytical data.

## Performance, benchmarks, and governance

`GET /api/v1/performance` and `GET /api/v1/performance/{report_id}` project
stored canonical reports with bounded pagination and optional strategy/run/mode
filters. Zero-trade or insufficient records remain visible unchanged.

`GET /api/v1/benchmarks` and `GET /api/v1/benchmarks/{comparison_id}` return
stored comparison records only. Unavailable or partial benchmark alignment is
retained, never replaced by a current calculation. TRAIN, VALIDATION, TEST/OOS,
and aggregate OOS modes remain distinct.

`GET /api/v1/governance/strategy-versions`, `/governance/active-strategy`,
`/governance/promotions`, and `/governance/promotions/{proposal_id}` expose
immutable governance lineage. `approved != active`: a neutral active response
is returned if no activation exists, with no latest-version fallback. These
GET-only endpoints cannot promote, approve, activate, roll back, benchmark, or
run a backtest.

## Persisted snapshot source

By default, these GET APIs read immutable V1 `CoreApiSnapshotRepository`
payloads created by a separate writer/runtime. SQLite is the safe local default;
PostgreSQL is used only when explicitly configured. Existing injected query
services still override this default for tests or local composition.

Single current views select the latest compatible snapshot using deterministic
stored `(created_at, snapshot_id)` order. Stock analysis is additionally scoped
to its exact normalized symbol. List views retain the deterministic stored order
and then apply their existing bounded filters/pagination. Empty stores return
their established `503`/`404`/empty-list semantics. Unsupported stored snapshot
schemas return `503 SNAPSHOT_SCHEMA_UNSUPPORTED`; no alternate/latest record is
substituted.

## Security and Phase 10 freeze

This unauthenticated backend is for local/private development and must not be
publicly exposed. Authentication/user tenancy, PostgreSQL, live/current data
providers, mutations, broker integration, OpenAI runtime, and Phase 9B runtime
are deferred. **PHASE 10 / #026A — PRODUCTION API FOUNDATION: COMPLETE.** This
means the HTTP architecture and read-only safety boundaries are stable, not
that the full application is production deployable.
