# Prospective Dhan Live-Bar Foundation V1

**Status: `PROSPECTIVE_DHAN_LIVE_BAR_FOUNDATION_V1 = ACTIVE / PROSPECTIVE_CAPTURE_FOUNDATION / WATCH_ONLY / NON_EXECUTABLE / HIGHER_INTRADAY_TECHNICAL_INPUTS = NOT_ACTIVE / RAW_TICK_RETENTION_POLICY = UNSET`.**

## Purpose and non-goals

This is the smallest provider-composed foundation for retaining a **genuinely
completed, prospectively observed** Dhan Quote-mode one-minute receipt.  It is
not a technical evaluator, an HSI horizon, a technical-reader activation, a
bar resampler, an Internal Radar input, a setup, a signal, a Six-Gates
authorization, or an order/broker/portfolio surface.

The foundation is deliberately separate from the provider-versioned historical
OHLCV store.  It does not alter canonical Daily or Weekly evidence, any of the
61 diagnostic rules, price-adjustment policy, or historical-PIT status.

```text
exact canonical identity + exact Dhan identity
  -> bounded Quote observation
  -> event_time + received_at
  -> canonical NSE ordinary-session binding
  -> completed prospective 1-minute receipt
  -> immutable local snapshot / conflict receipt

not -> 15m / 30m / 1H / 4H bar
not -> technical diagnostic input
not -> setup, gate, signal, trade, or order
```

## Fresh Dhan V2 provider-contract receipt

The contract was rechecked against Dhan's official [Live Market Feed V2
documentation](https://dhanhq.co/docs/v2/live-market-feed/), [Annexure](https://dhanhq.co/docs/v2/annexure/), and [Instrument List](https://dhanhq.co/docs/v2/instruments/).
The contract is represented by the immutable
`DhanV2LiveProviderContract` in `app.market_data.dhan_live_bar`.

| Contract fact | Verified value | Foundation consequence |
| --- | --- | --- |
| WebSocket version | `v2` | Reuses the existing authenticated V2 WebSocket URL construction without exposing its query values. |
| Connections per user | `5` maximum | Capacity is shared HSI infrastructure, never one feed per SenseEdge user. |
| Instruments per connection | `5,000` maximum | The current exact mapped population fits mathematically in one connection. This is not authorization to start it. |
| Instruments per subscription message | `100` maximum | The deterministic planner rejects an oversized request and batches exact identities only. |
| Request / response encoding | JSON / binary | The adapter emits Quote subscription JSON and parses only documented binary Quote packets. |
| Endianness | little-endian | The parser uses the official little-endian layout. |
| Provider feed modes | Ticker, Quote, Full | This foundation uses **Quote only**. Ticker lacks the required volume evidence; Full market depth is outside scope. |
| Quote subscription / response code | `17` / `4` | Exact Dhan V2 Annexure values. |
| Quote packet fields used | LTP, LTQ, LTT, ATP, cumulative volume, day OHLC | Only LTP, LTQ, LTT, and cumulative volume can contribute to a prospective minute. Day OHLC is never used to manufacture minute OHLC. |
| Quote wire layout | `50` bytes | Dhan documents an 8-byte header plus fields totalling 42 bytes; the current official Python client uses `<BHBIfHIfIIIffff`, also 50 bytes. The parser follows field sizes rather than ambiguous inclusive byte labels. |
| Ping / close | server ping every 10 seconds; close after more than 40 seconds without client pong | The underlying WebSocket library retains its normal pong handling. The bounded adapter does not run a background reconnect loop. |
| Provider disconnect | response code `50`, then a disconnect reason; `805` is documented connection-limit evidence | The existing sanitized disconnect parser is reused. No packet bytes, credentials, headers, or authenticated URL are retained. |

Previous-close, OI, and market-status packets that may accompany a Quote
subscription are explicitly ignored by the Quote-event adapter.  They are not
promoted to prospective price/volume observations.

## Detailed-master and exact identity audit

The public detailed-master source is the documented
`https://images.dhan.co/api-data/api-scrip-master-detailed.csv` URL.  A
controlled read-only audit retrieved a 34,136,030-byte CSV at
`2026-09-08T18:25:53+00:00` with:

```text
SHA256 = 7086c528b7dc65388542357c87ddcd1ad4a54033a36d7b99a5246e64082639e6
records parsed = 201,075
```

Observed columns include `EXCH_ID`, `SEGMENT`, `SECURITY_ID`, `ISIN`,
`INSTRUMENT`, `SYMBOL_NAME`, `DISPLAY_NAME`, `INSTRUMENT_TYPE`, `SERIES`, and
the documented instrument-detail fields.  The raw CSV was a temporary
read-only audit artifact; it is **not** a retained production artifact or a
new source-of-truth snapshot.  A governed source-artifact policy is required
before long-term master retention.

The selected exact-ISIN ordinary-NSE-equity denominator is 2,553, distinct
from the broader 5,106 canonical NSE-equity records and from any certified
Daily technical universe.  Matching required exact ISIN plus the ordinary
NSE-equity constraints (`EXCH_ID = NSE`, `SEGMENT = E`, `INSTRUMENT = EQUITY`,
and `SERIES = EQ`); a symbol was supporting evidence only.

| Exact audit result | Count |
| --- | ---: |
| Selected exact-ISIN denominator | 2,553 |
| `MAPPED_EXACT` | 2,287 |
| `PROVIDER_IDENTITY_NOT_FOUND` | 5 |
| `AMBIGUOUS_PROVIDER_IDENTITY` | 0 |
| `SYMBOL_CONFLICT` | 0 |
| `SECURITY_CLASS_MISMATCH` | 261 |

No fuzzy symbol/name matching, nearest-name selection, LLM identity
resolution, ETF/index substitution, or Dhan sector/industry taxonomy is
allowed.  An attempted identity must include canonical security ID, uppercase
12-character ISIN, Dhan security ID, `NSE_EQ`, `EQ`, detailed-master
fingerprint, and master-version identifier.  Empty, duplicate, noncanonical,
or ambiguous identity sets fail closed.

## Subscription capacity, not streaming authorization

At 2,287 exact mapped identities, Quote subscriptions need
`ceil(2,287 / 100) = 23` JSON messages and fit one 5,000-instrument provider
connection.  This establishes only mathematical provider capacity:

```text
ONE SHARED HSI MARKET FEED
  -> ONE SHARED CANONICAL MARKET STATE
  -> MANY USERS
```

It does not authorize whole-universe production streaming, separate feeds per
user, a long-running process, or a market-data retention commitment.

## Normalized prospective event and PIT lineage

`DhanProspectiveMarketEvent` is immutable and contains:

| Field group | Contract |
| --- | --- |
| Exact identity | canonical security ID, ISIN, provider security ID, `NSE_EQ`, `EQ`, detailed-master fingerprint, provider version |
| Quote fact | `packet_type = QUOTE`, LTP, optional LTQ, provider LTT, optional cumulative session volume |
| Observation lineage | `event_time`, `received_at`, connection ID, provider version, event identity, content fingerprint |
| Quality | only an accepted, exact-mapped Quote observation can be constructed |

`event_time` is the provider LTT, while `received_at` is when HSI observed the
packet.  They are distinct, timezone-aware, normalized to UTC, immutable, and
included in the appropriate lineage: the event identity excludes receipt and
connection noise, while the immutable event fingerprint includes both.  A
future-dated event (`event_time > received_at`), a naive timestamp, malformed
lineage, or tampered fingerprint is rejected.

This foundation can provide **prospective PIT** only: a receipt is not known
until after interval completion and after HSI actually received its supporting
events.  It does not upgrade any existing historical source to strict
historical PIT.

```text
PROSPECTIVE_PIT = PARTIAL / foundation implemented; live-session evidence pending
HISTORICAL_BACKFILL_PIT = NOT_READY / unchanged
```

## Canonical NSE session binding

`bind_dhan_event_to_regular_minute` consumes the existing canonical NSE
market-session calendar with `received_at` as the calendar as-of boundary.  It
uses Asia/Kolkata only for exchange-local session/minute boundaries and stores
interval timestamps in UTC.

Only a source-backed `REGULAR_CONTINUOUS` phase on a canonical regular trading
day may bind.  Pre-open, block-deal, post-close/closing, special, holiday, and
unknown/conflicted-session observations are excluded or marked session
unavailable.  Dhan market-status packets are not exchange-session authority.

The binding retains its exact `TechnicalTradingPeriod`, session identifier,
calendar identifier/fingerprint, and canonical trading-day source lineage.
It creates neither a 15m/30m/1H/4H period nor a technical reader input.

## Completed prospective one-minute evidence

The `ProspectiveDhanOneMinuteBarBuilder` creates a bar only for a fully
observed regular one-minute interval:

| Element | Deterministic rule |
| --- | --- |
| Open / high / low / close | First / maximum / minimum / last accepted LTP ordered by provider event time. Day OHLC values are never substituted. |
| Volume | Last cumulative session volume minus the last exact prior observation before the interval. A missing baseline, regression, or non-positive delta cannot become a complete volume bar. |
| Event ordering | Event time, cumulative volume, price, and deterministic event identity. Same-time/same-cumulative-volume conflicting prices are `EVIDENCE_CONFLICTED`, never arbitrarily ordered. |
| Completion | `known_at >= interval_end` and `known_at >= last_received_at`; finalized evidence cannot be rewritten. |
| Startup | A feed beginning after the current interval start produces `MID_INTERVAL_START / INCOMPLETE`; it must wait for a fully observed minute. |
| Gap | A disconnect/reconnect overlap on the same connection produces `PROVIDER_GAP / INCOMPLETE`. No interpolation, carry-forward, or synthetic repair occurs. |
| Duplicate / replay | Same semantic event is idempotent. A replay after finalization is retained as `LATE_EVENT_AFTER_FINALIZATION`, not a rewrite. |
| No trade | No observation is not a zero-price bar and not itself a provider outage. `NO_TRADE_OBSERVED` is possible only when separately proven, contains no bar, and is not persisted by this foundation. |
| Basis | `RAW_AS_TRADED` and `AdjustmentStatus.RAW` describe the observed packet; no corporate-action adjustment is performed. The separate source-basis decision remains authoritative. |

The builder holds only bounded in-process observation state for the caller's
capture window.  It has no background-feed lifecycle and no raw-tick archive.

## Immutable receipt persistence and conflicts

The existing generic immutable Core API snapshot repository safely represents
this additive evidence without a new SQLite schema or a change to historical
OHLCV storage:

| Snapshot family | Payload |
| --- | --- |
| `PROSPECTIVE_DHAN_ONE_MINUTE_BAR` | closed, incomplete, or conflicted one-minute receipt with identity, session, receipt state, known-at, and full fingerprinted provenance |
| `PROSPECTIVE_DHAN_ONE_MINUTE_CONFLICT` | immutable stored-versus-incoming fingerprint receipt and detected-at provenance |

Saving identical evidence is idempotent.  A different payload for the same
minute identity preserves the original and emits a separate immutable conflict
receipt; it never silently overwrites the first receipt.  The storage adapter
is not wired to any runtime, API, dashboard, technical reader, or production
capture job in this slice.

## Raw retention and capacity ceiling

```text
RAW_TICK_RETENTION_POLICY = UNSET
WHOLE_UNIVERSE_LONG_RETENTION_1M = NOT_APPROVED
```

Only receipt-level evidence and conflict lineage are defined.  There is no
indefinite raw-packet capture, and therefore a future raw-event replay policy
still needs independent approval.

The normal NSE session has approximately 375 one-minute intervals.  The
2,287 exact mapped identities therefore define a ceiling—not a prediction of
trading activity—of 857,625 completed receipt rows per day.  A representative
closed receipt serialized through the existing immutable snapshot format was
5,446 UTF-8 bytes.  This is a payload-only measurement, not a SQLite
file-size promise; indexes, pages, WAL, conflicts, and retention overhead are
additional.

| Ceiling | Rows | Serialized payload lower-bound |
| --- | ---: | ---: |
| One trading day | 857,625 | 4,670,625,750 bytes / 4.350 GiB |
| 20 trading days | 17,152,500 | 93,412,515,000 bytes / 86.997 GiB |
| 250 trading days | 214,406,250 | 1,167,656,437,500 bytes / 1,087.465 GiB |

This scale evidence is why a capture/retention rollout remains blocked on a
separate storage-retention decision.  It must not be used to fabricate actual
market activity or to start broad ingestion.

## Bounded proof and unchanged readiness

The deterministic integration proof uses synthetic test-only Quote packets,
the existing canonical 2022–2026 NSE calendar, a temporary SQLite snapshot
repository, and injected clocks.  It verifies packet parsing, identity
constraints, batching, regular-session binding, minute OHLC/volume,
mid-interval/gap behavior, reconnect isolation, duplicate/replay behavior,
finalization, immutable persistence/conflicts, and secret-free bounded
transport diagnostics.  Test observations never enter production storage.

No credential or market-session success is fabricated.  A bounded live Quote
subscription proof is separately attempted only when the existing secure Dhan
credentials are valid; a closed market with no Quote event remains an external
proof limitation, not an architectural success claim.

| Readiness cell | State | Exact reason |
| --- | --- | --- |
| Dhan V2 provider contract | `READY` | Official V2 limits, modes, Quote fields, parser layout, and disconnect semantics are versioned and tested. |
| Dhan detailed master | `PARTIAL` | Read-only public audit is fingerprinted; no governed long-term raw-master retention is approved. |
| Canonical-to-Dhan identity | `PARTIAL` | 2,287 exact mappings; 266 selected identities remain blocked rather than guessed. |
| Whole-universe subscription capacity | `READY` | 23 messages; one connection is mathematically sufficient. Streaming is not authorized. |
| Live WebSocket adapter | `PARTIAL` | Bounded Quote adapter is tested and reuses secure transport; it is not a background/reconnect runtime. |
| Normalized prospective event / event-time lineage | `READY` | Immutable exact identity, UTC event and receipt times, deterministic identities/fingerprints. |
| NSE session binding | `READY` | Existing canonical calendar excludes non-regular phases by default. |
| Prospective 1m base-bar / volume semantics | `READY` | Completed receipt, cumulative-volume delta, incompleteness, and conflict rules are deterministic. |
| Startup, gap, duplicate, out-of-order handling | `READY` | Each rejects fake completeness or immutable rewrites. |
| Immutable finalization | `READY` | Append-only Core snapshot persistence, reopen idempotency, and conflict receipts are tested. |
| Prospective PIT | `PARTIAL` | Contract is sound; actual live captured-session evidence is not claimed here. |
| Historical backfill PIT | `NOT_READY` | Unchanged; no historical availability proof was added. |
| Storage scale readiness | `PARTIAL` | Ceiling is quantified; whole-universe long retention remains unapproved. |
| Raw tick retention | `NOT_READY` | `RAW_TICK_RETENTION_POLICY = UNSET`. |
| 15m / 30m / 1H / 4H production readiness | `NOT_READY` | No approved session anchoring, gap aggregation, partial-interval, 4H, or retention derivation policy. |
| Daily / Weekly regression | `READY` | The foundation is isolated and does not read or write their existing evidence tables. |

## Next internally solvable continuation

`CANONICAL_INTRADAY_TIMEFRAME_DERIVATION_POLICY_V1`

That future bounded policy must define session anchors, completed-child rules,
gap propagation, partial final intervals, benchmark parity, 4H semantics, and
retention constraints before any 15m/30m/1H/4H reader can be activated.  It
must not assume that one-minute receipt availability automatically authorizes
resampling or technical diagnostics.
