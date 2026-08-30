# Production market-data contracts

Source responsibility and readiness are declared separately in
[data-source architecture](DATA_SOURCE_ARCHITECTURE.md). In particular, Kotak
Neo historical OHLCV remains unsupported until a stable documented contract is
approved; no endpoint is assumed by the runtime.

`app.market_data` is the provider-neutral ingestion boundary. Its flow is:

`raw provider response → adapter/normalizer → canonical fact → quality and freshness → store → existing analytical inputs`

The package has no provider SDK, HTTP/WebSocket client, broker, scheduler,
credentials, trading calculation, strategy decision, confidence calculation, or
API route. The only operational adapter in this phase is the deterministic
`StaticMarketDataProvider` for local tests.

## Canonical facts

`InstrumentIdentity` owns the stable internal ID, exchange, symbol/trading
symbol, ISIN, series, type, name, currency, and explicit provider mappings.
Provider tokens remain in `ProviderInstrumentMapping`; they are not canonical
IDs and do not enter strategy engines.

`CanonicalQuote`, `CanonicalOHLCVBar`, `IndexMarketObservation`,
`MarketBreadthObservation`, `ParticipationLiquidityObservation`, and
`MarketSessionObservation` retain timezone-aware timestamps, `Decimal` prices
and value fields, nullable unavailable fields, quality, warnings, and
`MarketDataProvenance`. Supported V1 timeframes are 1m, 5m, 15m, 30m, 60m, 1D,
and 1W; a provider advertises its actual subset.

Bars state `RAW`, `ADJUSTED`, or `UNKNOWN`. This phase does not adjust for
splits, bonuses, or dividends. Corporate-action providers remain a future
interface boundary.

## Store boundary

`MarketDataSnapshotWriter` accepts canonical normalized records only and writes
to a provider-neutral `MarketDataStore`. `InMemoryMarketDataStore` is a
deterministic append-only local/test implementation. It is intentionally not a
high-volume tick or bar database. A future production deployment may add a
dedicated time-series/bar store behind the same boundary rather than putting
every tick into the V1 core API snapshot table.

#027E derives low-volume breadth and participation facts from those canonical
quotes, explicit PIT universe memberships, and optional historical bars. It
does not infer membership from quote availability or create a market decision.
See [market breadth](MARKET_BREADTH.md).

#027D/U06 define `HistoricalBarStore` as the dedicated time-series boundary.
Its raw SQLite/PostgreSQL identity includes provider identity in addition to
instrument/timeframe/start/end, so immutable Yahoo and Upstox session evidence
can coexist. Downstream consumers continue to receive one provider-resolved
canonical bar per session through the store facade; no indicator or Brain code
implements source selection. See [historical market data](HISTORICAL_MARKET_DATA.md).

Existing analytical engines continue to consume validated domain observations
and immutable snapshots. Provider raw types and mappings do not cross into
market-regime, crisis, extremes, technical, fundamental, score, gates,
portfolio, rotation, or paper-trading code.

## Future data families

Price-side contracts can later supply OHLCV, VIX-compatible indices, breadth,
sector/index observations, participation, liquidity, and exchange status.
Separate future providers are needed for valuation/fundamentals, IPO activity,
promoter/OFS activity, ownership proxies, news/narrative, and retail/search/
social proxies. Those inputs remain facts or explicitly labelled proxies.

## Kotak Neo adapter

#027B adds the first real-provider adapter behind this contract. Its raw Kotak
payloads are normalized to canonical facts and validated before they can cross
into the existing domain boundary. Auth/session mechanics, including dynamic
base URL handling, remain inside the adapter. The provider can never calculate
market regime, Crisis/Euphoria, score, confidence, gate, rotation, or trade
action, and FastAPI never calls it directly.
## Independent provider families

`MARKET_DATA_PROVIDER=kotak_neo` and `HISTORICAL_DATA_PROVIDER=global_datafeeds` are independent settings. GDFL is historical-only and has no fundamentals integration in this phase.
# Secondary historical fallback

`yfinance` is an optional `HISTORICAL_OHLCV` source only. It is classified as
secondary, research, and non-authoritative. It does not replace Kotak current
quotes, Upstox/GDFL primary-provider slots, or official NSE/BSE evidence. Source
priority is explicit: approved primary history, approved secondary history,
yfinance research fallback, last-known-good canonical bars, then unavailable.
Provider conflicts remain reconciliation records; the system never averages
provider bars.
