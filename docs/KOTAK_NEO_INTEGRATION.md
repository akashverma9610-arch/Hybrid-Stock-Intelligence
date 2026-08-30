# Kotak Neo V1 market-data adapter

Kotak Neo is the first configured real-provider adapter, implemented only as
`KotakNeoMarketDataProvider` behind the provider-neutral #027A contract. The
adapter provides explicitly loaded instrument-master resolution and current
single/batch quote retrieval for mapped NSE/BSE equities and index/VIX records.
It can preserve LTP, previous close, OHLC, volume, change, depth top of book,
provider/exchange timestamps, receipt time, `Decimal` values, freshness, and
safe provenance. Provider tokens stay in `ProviderInstrumentMapping` and are
never canonical internal IDs.

## Current Neo contract

Kotak’s current Trade API documentation calls the Neo App-issued authorization credential a **TradeAPI Access Token** (the SDK parameter is named `consumer_key`). Quote and scrip-master/search reads are a **quote-only** path: they require that token but no completed 2FA session. The optional authenticated-session diagnostic follows the documented sequence: `POST /login/1.0/tradeApiLogin` with `Authorization: <TradeAPI Access Token>`, `neo-fin-key: neotradeapi`, mobile number, UCC, and the **current six-digit authenticator TOTP**; then `POST /login/1.0/tradeApiValidate` with that same access token plus `neo-fin-key`, the returned `sid`, the returned view token in `Auth`, and MPIN. MPIN validation returns a
dynamic `baseUrl`, which is retained only in `KotakNeoSession` and used for
authenticated follow-up operations such as the scrip-master path discovery.
The adapter uses the current fixed `mis.kotaksecurities.com` login endpoints
and deliberately excludes deprecated `/oauth2/token` and legacy-host flows.

Current official quote documentation states that quote retrieval supports one
or multiple `{exchange_segment, instrument_token}` values and requires the
TradeAPI Access Token without a completed 2FA session. The adapter therefore uses the
documented batch quote route directly; it does not fabricate a batch limit or
retry policy. Request failures remain per-instrument in a batch result.

Normal local setup uses the OS-backed connection profile described in
[Connection management](CONNECTION_MANAGEMENT.md), so PowerShell environment
variables are no longer required for ordinary app use. The developer-fallback
environment variable names are `KOTAK_NEO_TRADEAPI_ACCESS_TOKEN`,
`KOTAK_NEO_MOBILE_NUMBER`, `KOTAK_NEO_UCC`, and `KOTAK_NEO_MPIN`. They are
placeholders in `.env.example`. There is deliberately no normal TOTP-seed
environment setting: the current code is entered transiently for an optional
session diagnostic and is never persisted. Credentials, codes, session
IDs/tokens, and authorization headers are redacted from representations,
errors, provenance, API responses, tests, and documentation.

## Explicitly unsupported/deferred

The current official material reviewed for this task does not provide a stable
current historical/intraday candle contract suitable for this adapter, so
historical and intraday bars fail closed as unsupported. Direct breadth and
market-session endpoints are likewise unsupported here; future breadth must be
derived separately from a frozen universe and canonical stored facts. WebSocket
streaming exists in the current Neo SDK but is not initialized, imported, or
connected by this phase. There is no scheduler, polling loop, auto-ingestion,
FastAPI call path, order, portfolio, demat, funds, or account operation.

An optional read-only integration test is skipped unless isolated
`KOTAK_NEO_TEST_*` settings explicitly enable it. It makes one quote request
only; default tests never use normal credentials or the network.

## Explicit local smoke validation

Run the smoke test only in a local shell with `KOTAK_NEO_TEST_ENABLED=true` and
the existing credential variables named above, plus
`KOTAK_NEO_TEST_EXCHANGE_SEGMENT`, `KOTAK_NEO_TEST_INSTRUMENT_TOKEN`, and
`KOTAK_NEO_TEST_SYMBOL`. The flag is mandatory: the test does not consume any
credentials merely because they happen to be present in the environment.

Run `pytest tests/integration/test_kotak_neo_live.py -q`. It resolves the one
explicitly configured mapping and fetches one quote; it never uses an order,
portfolio, holdings, positions, funds, demat, WebSocket, or historical-candle
endpoint. Market-closed responses remain valid when canonical session-aware
freshness labels them appropriately.

Failures are reported without credentials and may identify the safe failing
authentication stage as `ACCESS_TOKEN_REJECTED`, `TOTP_LOGIN_FAILED`,
`MPIN_VALIDATION_FAILED`, `SESSION_BASE_URL_MISSING`, or
`PROVIDER_UNAVAILABLE`; they otherwise remain classified as configuration,
instrument-resolution, quote API, rate-limit,
provider-unavailable, malformed response, canonical-normalization, quality, or
optional index/VIX availability issues. A default skip means the explicit local
smoke environment was not enabled; it is not evidence of a provider failure.

## Local Settings connection validation

For normal local setup, use Settings → Connections → Kotak Neo or
`/setup/kotak-neo` as described in
[Connection management](CONNECTION_MANAGEMENT.md#connect-kotak-neo-without-powershell).
The quote-only test reads the token from the secure credential store, discovers
the documented token-only scrip master, deterministically intersects the NSE
cash master with the stored NSE universe, and makes exactly one quote request.
The optional session test separately accepts a current six-digit TOTP and tests
TOTP/MPIN/dynamic-base-URL creation; it never stores that code. Neither test
requires developer test environment variables. They report only sanitized provider/mode/status,
canonical symbol, normalization, freshness, timestamp, and safe error code. It
does not make account, holdings, funds, positions, orders, trades, margin,
WebSocket, or market-scan calls.

## Sources reviewed

- [Kotak migration guidance](https://www.kotakneo.com/support/what-are-the-changes-in-the-new-apis-is-there-a-migration-guide/)
- [Current official quote documentation](https://github.com/Kotak-Neo/kotak-neo-python/blob/main/docs/functions/market_data/quotes.md)
- [Current official scrip-master documentation](https://github.com/Kotak-Neo/kotak-neo-python/blob/main/docs/functions/market_data/scrip_master.md)
- [Current official SDK authentication sequence](https://github.com/Kotak-Neo/Kotak-Neo/blob/main/docs/authentication.md)
- [Current official SDK overview](https://github.com/Kotak-Neo/kotak-neo-python)
