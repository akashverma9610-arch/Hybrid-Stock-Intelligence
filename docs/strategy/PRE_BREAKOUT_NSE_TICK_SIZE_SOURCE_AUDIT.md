# Pre-Breakout NSE Tick-Size Source Audit and Proposal

**Status: PROPOSED — NOT APPROVED — NOT SELECTED — NOT ACTIVE.**

This is a governance audit only. It does not alter selected `pre-breakout-policy-v1` / `v1.1-draft`, create a successor, write reference data, materialize a tick or stop, or create candidates, signals, orders, or activation.

## Sources inspected

| Source/path | Classification | Identity / tick finding | PIT and storage finding |
| --- | --- | --- | --- |
| Official NSE local universe importer | Official exchange identity evidence | Stores canonical instrument, symbol, ISIN, exchange, series, and source-as-of. It has no tick-size field. | Snapshot/instrument `data_as_of` is retained, but no tick fact is represented. |
| Historical security master | Official/reference identity-capable architecture | Represents canonical identity, ISIN, symbol effective intervals, listing/tradability, revision/source, and as-of. It has no tick-size record. | PIT identity is supported; tick effective periods are not. |
| Kotak Neo NSE cash master | Licensed/provider reference-data candidate | Live-shaped fixture contains `dTickSize`; `KotakNeoInstrumentRecord`, identity conversion, and durable mapping retain token/symbol/ISIN/series but discard tick size. | Master is loaded for bounded mapping; no tick observation, observed timestamp, effective period, or durable tick record is retained. |
| Upstox BOD instrument master | Licensed/provider reference-data candidate | `UpstoxInstrumentRecord` retains instrument key, segment, exchange, ISIN, symbol, and type; no tick field is modeled. | Mapping checksum/effective mapping time may be stored, but no tick evidence exists. |
| Provider instrument mappings | Existing implementation only | Durable mappings bind canonical identity to provider token/key, not price increments. | `effective_as_of` applies to routing mapping, not a tick value/effective period. |
| OHLCV, quotes, decimals, lot size, circuit limits | Derived/generic/unrelated | Prices/precision, observed differences, lot size, and limits are not authoritative tick metadata. | Must never infer tick size. |
| Generic trade/execution/friction helpers | Generic/unrelated | No price-grid or NSE tick source exists. | No stop/tick semantics are defined. |

## Audit conclusion

No current canonical tick-size data model, reference-data repository, resolver, or PIT-effective tick record exists. The repository can bind a tick record to canonical instrument identity in a future bounded reference-data layer, but it cannot materialize a governed one-tick stop today.

**Current repository readiness: NOT_READY.** This is a data/representation limitation, not a reason to weaken the desired policy.

## Recommended `NSE_TICK_SIZE_SOURCE` rule

**AUTHORITATIVE_REFERENCE_DATA_WITH_PIT_PRECEDENCE**

For canonical NSE equity identity `I` at evaluation `as_of = T`, use only an immutable tick reference record with exact instrument binding, `Decimal` tick value, source/provenance fingerprint, source identity, and availability/effective timestamps that make it eligible at `T`.

Proposed precedence:

1. Official NSE reference/security-master evidence that explicitly states tick size, maps exactly to `I`, and is eligible at `T`.
2. Otherwise, approved licensed reference-data evidence that explicitly states tick size, maps exactly to `I` by ISIN plus NSE cash identity, and is eligible at `T`.
3. Otherwise return `TICK_SIZE_UNAVAILABLE_FOR_AS_OF` and fail closed.

If eligible official and licensed evidence conflict, return `REFERENCE_DATA_CONFLICT` and fail closed unless a future canonical resolver has separately governed a safe conflict policy. Do not silently privilege whatever provider is currently configured.

Neither Yahoo nor current/derived OHLCV may supply a fallback.

## PIT requirement

Historical evaluation requires evidence observable/effective by `T`. A current-only provider master may be used only for a contemporaneous/current evaluation after it is captured with valid observation provenance. It cannot backdate today's tick size to prior evaluations.

If a future source has only first-observed metadata rather than documented effective periods, any period before first observation remains `TICK_SIZE_UNAVAILABLE_FOR_AS_OF` unless separately governed exchange evidence proves invariance for the exact instrument. Invariance must never be assumed from a ticker, price range, or generic NSE convention.

Symbol changes, ISIN changes, instrument replacement, delisting/relisting, corporate actions, and master revisions reinforce that lookup must bind to canonical instrument identity/effective identity interval, not ticker text alone.

## Exact numerical and grid policy

Represent `tick_size`, `structural_invalidation_price`, and future derived values with `Decimal`, never binary float. A future stop materializer must fail closed when tick is missing/conflicting, support is malformed, or one-tick subtraction does not yield a valid price-grid result. It must not silently round support or choose a rounding mode.

The exact future grid test requires a separate governed `TICK_GRID_ALIGNMENT_RULE`: it should specify the exchange-consistent `Decimal` divisibility/quantization convention for `support_price` relative to `tick_size`. No such rule exists now, so this proposal does not claim that simple decimal-place formatting or price/tick division is already authoritative.

## Explicitly prohibited inference

Never derive tick size from decimal places, recent price differences, minimum candle movement, order-book spacing, price band, price level, a generic INR 0.05 assumption, lot size, circuit limits, or any OHLCV field. Observed prices are not security-master metadata.

## Stop boundary

The future high-level relation remains conceptual only:

```text
final_stop = structural_invalidation_price - one governed valid tick
```

This audit does not compute it. Missing tick, conflicting tick, historical tick unavailability, misaligned support, or malformed reference metadata must fail closed; no automatic rounding is permitted.

## Newly named ambiguities

- `HISTORICAL_TICK_EFFECTIVE_PERIOD`
- `REFERENCE_DATA_PRECEDENCE_CONFLICT`
- `TICK_GRID_ALIGNMENT_RULE`
- `TICK_REFERENCE_DATA_RECORD_SCHEMA`

## Required human decision

Before a successor policy resolves `NSE_TICK_SIZE_SOURCE`, a human must approve, reject, or modify `AUTHORITATIVE_REFERENCE_DATA_WITH_PIT_PRECEDENCE`, including its official-first/approved-licensed fallback, conflict fail-closed behavior, and current not-ready state. A later bounded reference-data implementation must separately define the tick record schema and grid validation before it can materialize a final stop.
