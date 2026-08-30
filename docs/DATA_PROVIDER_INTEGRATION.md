# Data-provider integration boundary

Providers implement the `MarketDataProvider` protocol only for capabilities
they actually support: identity resolution, single/batch quotes, historical or
latest bars, index data, breadth, and market status. `ProviderCapabilities`
uses `SUPPORTED`, `UNSUPPORTED`, and `UNKNOWN`; it also exposes supported
timeframes and a metadata-only rate-limit boundary. No provider-specific limit
is guessed.

`MarketDataProviderRegistry` requires an explicit configured name. An unknown
or real-but-unregistered provider raises a sanitized configuration error; it
never falls back to the mock provider. Batch quotes retain successes and
per-instrument sanitized failures so one unavailable instrument does not erase
other facts.

`MarketDataNormalizer` performs field/token mapping, timezone and enum
conversion, and `Decimal` conversion. It never repairs missing values or
creates a decision, confidence, crisis/euphoria state, gate, rotation, or
trading recommendation. Malformed values produce safe taxonomy codes,
including unavailable, authentication/authorization, rate limit, instrument
not found, unsupported capability/timeframe, malformed response, freshness,
quality, and partial batch failure. Retryability is metadata for future adapters
only; this phase implements no retry loop.

`MARKET_DATA_PROVIDER=mock` selects the local deterministic adapter. Settings
can carry environment, timeout, freshness thresholds, and a credential variable
*name* for later adapters. They never read or log credential values. #027A
does not connect to Upstox, Zerodha, Angel, NSE, BSE, Yahoo, a broker, or a
WebSocket.

## Kotak Neo V1

`MARKET_DATA_PROVIDER=kotak_neo` selects the explicit read-only Kotak Neo
adapter; an unavailable/misconfigured Kotak provider never falls back to mock.
It uses the current consumer-key quote path and an isolated TOTP → MPIN session
client that retains the dynamic base URL returned after validation. Only
instrument master, current/batch quotes, quote depth, index, and VIX-compatible
records are advertised. Historical/intraday candles, direct breadth, exchange
status, WebSocket, retries, and rate-limit assumptions are deliberately not
invented. See [Kotak Neo integration](KOTAK_NEO_INTEGRATION.md).

## Historical OHLCV

Historical providers use the existing `get_historical_bars(HistoricalBarsRequest)`
contract and return canonical bars only. `HistoricalIngestionService` handles
deterministic chunks, validation, provider-order normalization, duplicate and
conflict reporting, coverage, and dedicated storage. Kotak historical support
remains deferred until a stable documented endpoint is separately validated.
Imported CSV/Parquet sources may implement the same contract; they require
canonical identity/timeframe, timezone-aware bar bounds, OHLCV, adjustment
state, and provenance. No new live provider, scheduler, or automatic refresh is
introduced.
