# Data-source architecture

`app.data_sources` is a provider-neutral readiness and composition layer. It
does not connect to, scrape, validate, or retrieve from any source. It records
which explicitly configured source is responsible for each data family and
whether that capability is safe to use.

## Families and priorities

The registry has independent slots for current/streaming quotes, historical
OHLCV, index data, VIX, universe membership, fundamentals, corporate filings
and actions, news/research, and IPO/primary-market data. One provider is never
assumed to supply every family. `DATA_SOURCE_<FAMILY>_PRIORITY` may declare an
ordered primary/verification source list; only listed sources are considered.
There is no automatic mock or latest-provider fallback.

Readiness is `READY`, `CONFIGURED_NOT_VALIDATED`, `MISSING_CONFIGURATION`,
`UNSUPPORTED`, `DEGRADED`, or `UNAVAILABLE`. Each immutable report retains
priority, requirement level, validation metadata, freshness policy, PIT and
adjustment capability, warnings, and non-secret provenance.

## Current source matrix

Kotak Neo has a current quote/index/VIX adapter boundary and connection
management. Its live quote and streaming validation remain pending external
validation. Kotak historical OHLCV is explicitly `UNSUPPORTED`: no stable,
documented endpoint is assumed or called.

`stored_data` is the source slot for already persisted canonical quotes, bars,
indices, VIX, and point-in-time universe membership. It is separate from a live
provider. `mock` is usable only when explicitly selected and is labelled as an
explicit mock source.

Future source slots are intentionally unconfigured for fundamentals, filings
and actions, news/research, and IPO data. Fundamentals distinguish `REPORTED`,
`GUIDANCE`, `CONSENSUS_ESTIMATE`, and `DERIVED`; estimates never become reported
facts. Future source records must retain source/reference, publication/observed/
received times, effective period, data family, and schema/normalization version.

The filings/action slots now include implemented NSE and BSE normalization and
storage boundaries. They remain configured-not-validated until a documented
external integration is separately verified; no NSE/BSE historical or filing API
contract is inferred. See [corporate filings](CORPORATE_FILINGS.md).

## Freshness and point in time

Freshness is family-specific: quotes use wall-clock policies, daily history uses
completed-session semantics, and filings/fundamentals/news use publication-time
semantics. PIT capability is reported explicitly and is required for reliable
replay/OOS usage. A missing or limited guarantee is visible, never inferred.

## Runtime and API

`DataSourceCompositionService.runtime_readiness()` reports whether a requested
runtime mode has its critical source families and which optional analysis
families will remain unavailable. It does not build a runtime coordinator or
invent a universe. `GET /api/v1/data-sources/status` is a sanitized read-only
view for a future Settings/Data Sources UI. It contains no credentials and no
control action.
## Stored financial facts

The `stored_data` source declares point-in-time `FUNDAMENTALS` capability for locally persisted canonical facts only. It does not validate or imply an external live fundamentals provider. `future_fundamentals` remains unconfigured until an approved provider/parser phase.

Global Datafeeds is an optional historical-only source. Its readiness stays configured-not-validated until an explicit validation succeeds; it is independent from Kotak current quotes.

`yfinance` may additionally provide bounded secondary-research enrichment
snapshots for an already frozen cohort. This is not a `FUNDAMENTALS`,
`FILINGS`, `CORPORATE_ACTIONS`, or taxonomy readiness source: its observations
are explicitly non-canonical and observed-at-fetch-only, so they do not change
canonical coverage or stored-data Brain eligibility.

Upstox Historical Candle V3 is a second optional historical-only source. Its
priority is selected explicitly with `HISTORICAL_DATA_PROVIDER=upstox`; it does
not replace Kotak current quotes or Global Datafeeds. `upstox` is only `READY`
after a secure access token and a bounded successful validation. No provider
family silently falls back to another provider.
## Optional GNews research evidence

`NEWS_RESEARCH` may be configured independently as `gnews`.  Its `api_key` is held only by the existing secure credential store and is never serialized, returned by connection APIs, logged, or added to provenance.  Readiness progresses from `MISSING_CONFIGURATION` to `CONFIGURED_NOT_VALIDATED` and only then to `READY` after validation.  GNews is secondary and optional; stored primary filings retain precedence and no provider silently substitutes for it.
## Primary-market source

`IPO_PRIMARY_MARKET` is an official-export/store capability.  It is available only after a local official NSE export has been imported; no live automatic provider is declared ready and there is no silent fallback.
