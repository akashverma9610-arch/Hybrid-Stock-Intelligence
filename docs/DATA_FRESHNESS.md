# Market-data quality, freshness, and provenance

Canonical records retain provider, provider instrument reference, exchange and
provider timestamps when supplied, receipt timestamp, normalization/schema
version, and safe request/source references. All material timestamps are
timezone-aware. Missing optional fields remain unavailable with warnings rather
than fabricated values.

`MarketDataQualityValidator` fails closed for material corruption: non-positive
prices, negative volume/trade count, inconsistent OHLC ranges, timestamp
inversion, duplicate bars, and out-of-order bar collections. It does not repair
or reorder a corrupted provider response.

`SessionAwareFreshnessEvaluator` produces `FRESH`, `STALE`, `VERY_STALE`, or
`UNKNOWN` independently for quotes, intraday bars, daily bars, indices, and
breadth. Thresholds are configured per family. During PRE_OPEN, POST_CLOSE, or
CLOSED states the configured threshold is expanded instead of treating an
unchanged closed-session price as equivalent to an open-session feed outage.
The implementation deliberately does not claim to be an exchange calendar.
`DEGRADED` is preserved as a warning.

Downstream Crisis and Market Extremes engines receive only their own immutable
factor inputs. This foundation carries the price, volatility, breadth, sector,
liquidity, session, quality, and provenance facts needed for later input
assembly, so downstream confidence can be reduced for stale, partial, degraded,
or low-coverage data without calculating that confidence here.

Kotak quote timestamps are parsed only when explicitly supplied by the current
payload (epoch or timezone-aware ISO form); receipt time is separately recorded.
The adapter never substitutes local time for a provider/exchange timestamp and
uses the canonical evaluator for fresh/stale/very-stale/unknown status.
