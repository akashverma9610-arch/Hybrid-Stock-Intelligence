# Canonical Technical Price Adjustment and Corporate-Action Integrity V1

**Status: `CANONICAL_TECHNICAL_PRICE_ADJUSTMENT_INTEGRITY = ACTIVE / DERIVED_SPLIT_BONUS_ONLY / NO_PERSISTENCE / NO_LEGACY_REWRITE`.**

## Scope and fixed boundaries

This contract supplies a pure, deterministic integrity assessment and, only
where the existing official action receipt proves its semantics, an in-memory
split/bonus-adjusted derivative. It is data integrity, not a horizon policy,
technical strategy, indicator expansion, signal, score, portfolio operation,
or execution surface.

- `raw source data != adjusted data`
- `adjustment != mutation`
- `today's back-adjusted series != historical PIT truth`
- `announcement != ex/effective date`
- `price adjustment != total-return adjustment`
- `split != rights issue`
`equity adjustment != index adjustment`

The implementation is
`app/market_data/technical_price_adjustment_integrity.py`. It has no store,
repository, provider request, clock, API, UI, broker, order, portfolio, or
diagnostic dependency. Existing `HistoricalCorporateAction`,
`HistoricalSecurityMasterStore`, `CanonicalOHLCVBar`, and
`HistoricalPriceIntegrityService` remain the only corporate-action/raw-bar
storage and existing consumption paths.

Raw provider OHLCV remains immutable. A `DerivedTechnicalOHLCVBar` exists only
in the caller's returned `TechnicalPriceAdjustmentResult`; it retains raw-bar
fingerprint, price/volume factor, action IDs, requested `as_of`, adjustment
policy/version, and deterministic fingerprint. It cannot overwrite
`historical_bars`. A correction is represented by a new immutable action ID or
revision and a new derived result; an older result is never repaired.

## Existing action source and security boundary

`HistoricalCorporateAction` already retains one exact canonical security ID,
kind, announcement date, record date, ex-date, effective date, imported/source
known time (`as_of`), source, revision, source reference, original purpose,
and optional ratio. Its source boundary uses the official NSE corporate-action
CSV and maps only `EQ` rows through an exact symbol and, when necessary, one
unique canonical-ISIN identity. It has no fuzzy company-name mapping.

NSE's corporate-actions page exposes issuer action purpose plus announcement
and record dates, while the current corporate-filings action export includes
the ex-date and record date fields used by the importer. [NSE corporate-actions
page](https://www.nseindia.com/static/investor-relations/corporate-actions) and
[NSE corporate-filings actions](https://www.nseindia.com/companies-listing/corporate-filings-actions)
therefore support retaining these dates separately; they do not make them
interchangeable. The adjustment boundary for this contract is the receipt's
explicit `effective_date` (NSE importer currently sets it from official
`EX-DATE`), never the announcement or record date.

An action is eligible only when both:

```text
source_known_at <= requested_as_of
effective_at    <= requested_as_of
```

An announced but future-effective action is excluded. A past-effective action
learned after the requested `as_of` is also excluded. Thus a 2027 split cannot
alter evidence available in 2026. The source-known field is an immutable HSI
source/import receipt, not an invented market-publication timestamp; this does
not remove the separate historical source-timing limitation.

## Technical action taxonomy and V1 treatment

| Technical class | Existing source representation | Price continuity / share count / volume | V1 deterministic treatment | Required exact evidence | Fail-closed result |
| --- | --- | --- | --- | --- | --- |
| `STOCK_SPLIT` | `SPLIT` | Price/share count change; volume comparability can change | Only official NSE V1 receipt with exact `From Rs old ... To Rs new` source text whose parsed ratio agrees | exact canonical security, source/revision, source-known, ex/effective date, old/new face values | `SPLIT_RATIO_SEMANTICS_UNVERIFIED` |
| `BONUS` | `BONUS` | Price/share count change; volume comparability can change | Only official NSE V1 `Bonus additional:existing` ratio | exact security, source/revision, source-known, ex/effective date, positive ratio | `BONUS_RATIO_SEMANTICS_UNVERIFIED` |
| `RIGHTS` | `RIGHTS` | Potential price/share-count change | No TERP or subscription-price calculation | exact issue terms, subscription/premium and an approved rights method are absent | `RIGHTS_ADJUSTMENT_NOT_READY` |
| `CASH_DIVIDEND` / special dividend | model supports `DIVIDEND`; current NSE importer does not yet ingest it | Price gap is distinct from return reinvestment | Neither price nor total-return adjustment is approved here | separately governed price and total-return policies | `DIVIDEND_PRICE_POLICY_NOT_APPROVED` |
| merger, demerger, spin-off, hive-off | `MERGER`, `DEMERGER`; spin-off/hive-off not separately coded | Often changes security/issuer economics and comparability | Never reduce to a multiplier | exact successor/security and value-allocation policy | `COMPLEX_ACTION_NON_COMPARABLE` |
| symbol/security continuity | `SYMBOL_CHANGE`, lifecycle evidence | Identity continuity can be material | Do not bridge price automatically | exact successor/predecessor evidence and approved continuity method | `SECURITY_CONTINUITY_NON_COMPARABLE` |
| capital reduction / standalone face-value change / other | no separate current model code; a face-value subdivision may be represented as `SPLIT` source text | Unknown without terms | No generic inference | explicit action taxonomy and governed method | `OTHER_ACTION_NON_COMPARABLE` |

NSE's derivative corporate-action adjustment guidance lists bonus, rights,
merger/demerger, splits and cash benefits as different action families, and
places its derivative adjustment after the last cum-basis trading day. That is
useful primary-source confirmation that these effects are not a universal
multiplier; it is not imported as an equity OHLC adjustment formula.
[NSE corporate-action adjustment guidance](https://www.nseindia.com/products-services/equity-derivatives-corporate-actions-adjustments?f=YMME).

For an approved V1 split, old/new face values give:

```text
price_factor  = new_face_value / old_face_value
volume_factor = old_face_value / new_face_value
```

For a V1 bonus `additional:existing`:

```text
price_factor  = existing / (existing + additional)
volume_factor = (existing + additional) / existing
```

Factors apply only to raw bars strictly before that action's effective
boundary. Multiple distinct split/bonus actions multiply deterministically.
Duplicate action IDs and multiple same-kind records at one effective boundary
are ambiguous and block the result. Split plus bonus on the same boundary can
remain independently lineaged and multiply; no action is deduplicated by a
price pattern. Derived volume is a Decimal because a source volume multiplied
by a valid share-count factor need not be integral. Missing raw volume blocks
volume readiness while leaving a valid price derivation distinct.

## Basis vocabulary and source-basis audit

`PriceAdjustmentBasis` retains existing legacy names and now additionally
defines `SPLIT_BONUS_ADJUSTED`, `PRICE_ADJUSTED`, and
`PROVIDER_ADJUSTED_UNKNOWN_METHOD`. The V1 derivation can produce only
`SPLIT_BONUS_ADJUSTED`. `PRICE_ADJUSTED`, `TOTAL_RETURN_ADJUSTED`, and
provider-adjusted unknown method remain policy unavailable; they never inherit
the label from a smooth chart.

| Source family | Current retained HSI basis | Source method proven for this contract | Raw values recoverable | Canonical technical authority | V1 result |
| --- | --- | --- | --- | --- | --- |
| Upstox V3/V4 daily equity/index | `UNKNOWN` | Historical-candle documentation supplies OHLCV fields but no retained corporate-action adjustment method | Yes, immutable provider rows | No price-continuity approval | `UNKNOWN` / blocked |
| NSE full bhavcopy | `UNKNOWN` | Retained importer has no approved adjustment-basis source fact | Yes | No price-continuity approval | `UNKNOWN` / blocked |
| yfinance `yfinance-history-v1` | `RAW` from explicit `auto_adjust=False`, `back_adjust=False`, `actions=False` adapter configuration | Raw adapter output only | Yes | Secondary research only; cannot override canonical evidence | `RAW`, non-authoritative |
| broad benchmarks | provider/source specific | Index methodology may handle constituent actions; equity rules do not apply | Yes where stored | No V1 equity adjustment application | `INDEX_SOURCE_SPECIFIC` |
| sector indices | provider/source specific | Same constraint as broad benchmarks | Yes where stored | No V1 equity adjustment application | `INDEX_SOURCE_SPECIFIC` |

Upstox's [Historical Candle V3 documentation](https://upstox.com/developer/api-documentation/v3/get-historical-candle-data/)
specifies returned timestamp/OHLCV fields and retrieval ranges, but does not
state a corporate-action adjustment method. Its separately documented
[Corporate Actions API](https://upstox.com/developer/api-documentation/get-corporate-actions/)
does not change the basis of already retained V3/V4 candles. HSI therefore
keeps existing Upstox bars `UNKNOWN`. yfinance remains secondary exactly as
documented in [YFINANCE.md](../YFINANCE.md); it cannot become canonical because
its raw values are convenient.

For indices, NSE methodology itself describes action-specific index treatment
(for example, bonus or rights changes can alter shares, price or divisor).
[NIFTY index methodology example](https://archives.nseindia.com/content/indices/Method_Nifty100_Equal_Weight.pdf)
confirms the need for a source-specific index basis. No stock split policy is
applied to NIFTY 50, NIFTY 500, or sector-index bars.

## Adjustment result and continuity gate

The minimal pure input is:

```text
canonical security + requested as_of + raw source-bar window
+ immutable action receipts + target basis + policy/version
```

The output contains raw-bar IDs/fingerprints, eligible action receipts/source
fingerprints, factors, derived bars where allowed, readiness, price continuity,
volume readiness, explicit reasons, policy/version, assessment identity and a
canonical SHA-256 fingerprint. Serialization uses sorted identities, UTC
timestamps, Decimal strings and JSON sorted keys. It has no runtime clock,
locale, unordered collection, or current/latest lookup.

`RAW` can be continuous only when no known price-transforming action crosses
the requested bar window. A raw window crossing a known action is retained but
`PARTIAL / NON_COMPARABLE`; a technical consumer must not smooth an indicator
through it. A derived split/bonus window is `READY / CONTINUOUS` only if every
crossing action has a proven V1 factor. Rights, dividends, complex actions,
ambiguous receipts, mixed/unknown source bases and security discontinuities
remain `NOT_READY` or `NON_COMPARABLE`.

This is a gating fact for existing continuity-sensitive families—moving
averages, ATR, RSI, ADX, Ichimoku/Chikou, OBV, price structure, pivots,
patterns and relative strength. It does not activate any family. Current
session VWAP may be less exposed over a non-crossing session, but this contract
does not grant intraday readiness.

## Direct production audit at 2026-09-05

Read-only SQLite audit of `data/nse_stock_manager.db` found:

| Item | Count / state |
| --- | --- |
| retained daily bars | 1,545,139 |
| Upstox provenance / `UNKNOWN` | 1,518,604 |
| NSE official provenance / `UNKNOWN` | 48 |
| yfinance provenance / `RAW` | 26,487 |
| immutable official NSE corporate-action receipts | 501 |
| exact action securities | 410 |
| action-security IDs with retained bars | 408 |
| bars on those action-security IDs | 290,340 |
| action taxonomy | 166 split; 162 bonus; 138 rights; 35 demerger |
| action receipts with both parsed ratio values | 386 |
| historical strict source-known-at certification | 0 retained rows / `NOT_READY` |

These counts prove stored coverage, not that each action can be applied to a
specific historical bar window. The present source action import time is a PIT
receipt, but historical daily source publication timing remains unresolved.
No price-match inference was used to classify the 1,518,652 `UNKNOWN` bars.

## Readiness matrix

| Area | State | Exact reason |
| --- | --- | --- |
| A. corporate-action source coverage | `PARTIAL` | 501 exact NSE receipts; no broad all-action taxonomy or BSE/Upstox ingestion path |
| B. split adjustment | `PARTIAL` | Pure V1 factor is ready only for explicit old/new face-value NSE source text; generic split notation remains blocked |
| C. bonus adjustment | `PARTIAL` | Pure V1 factor is ready only for exact official additional:existing ratio |
| D. rights adjustment | `NOT_READY` | no approved TERP/terms policy |
| E. dividend price policy | `NOT_READY` | price and total-return policies deliberately separate |
| F. complex reorganisation continuity | `NOT_READY` | merger/demerger/spin-off/security allocation not a multiplier |
| G. price-adjustment basis | `PARTIAL` | vocabulary and pure derivative exist; most stored bars remain unknown |
| H. volume adjustment | `PARTIAL` | explicit split/bonus factor exists, but volume is independently missing for some rows and non-split actions remain blocked |
| I. Upstox current basis | `NOT_READY` | provider adjustment method undocumented for retained V3/V4 contract |
| J. NSE bhavcopy basis | `NOT_READY` | no approved source-basis proof retained |
| K. yfinance authority | `NOT_APPLICABLE` | raw secondary/research evidence only |
| L. benchmark basis | `NOT_READY` | index-specific methodology and stored source semantics unresolved |
| M. sector basis | `NOT_READY` | index-specific methodology and stored source semantics unresolved |
| N. daily forward price continuity | `PARTIAL` | forward session/close path exists, but an explicit source basis and eligible-action window are still required per bar |
| O. daily historical price continuity | `PARTIAL` | action factor gate exists, but strict historical temporal eligibility remains separate and blocked |
| P. weekly derivation gate | `NOT_READY` | daily temporal usability, period completeness, compatible basis and continuity are not broadly present |
| Q. monthly derivation gate | `NOT_READY` | same missing prerequisites as weekly |

`PRICE_TEMPORAL_READY`, `PRICE_CONTINUITY_READY`, and `VOLUME_READY` remain
separate. Forward session/close evidence alone does not provide source basis or
action continuity. Solving a price factor does not retrospectively establish
historical source availability.

## Explicit exclusions and next continuation

No intraday 15m/30m/1H/4H storage or fetch, weekly/monthly materialization,
horizon applicability, MACD/Stochastic/CCI/Williams %R or other indicator,
technical score/voting, alternate Brain, signal, portfolio mutation, broker,
order or execution capability is added.

The immediate next bounded repair is one authoritative source-basis/action
coverage decision—not broad historical archaeology.
`CANONICAL_WEEKLY_MONTHLY_TECHNICAL_BAR_DERIVATION_V1` remains premature until
daily source timing, adjustment continuity and volume prerequisites are
materially available.

- `ONE_CANONICAL_61_DIAGNOSTIC_REGISTRY = TRUE`
- `SEPARATE_TECHNICAL_BRAIN = FALSE`
- `HYBRID_TECHNICAL_ARCHITECTURE = FROZEN`
- `EXTERNAL_SCREENER_AUTHORITY = DISCOVERY_ONLY`
- `NO_INDICATOR_EXPANSION = TRUE`
- `HORIZON_SPECIFIC_TECHNICAL_POLICY = NOT_ACTIVE`
`MULTI_TIMEFRAME_TECHNICAL_ORCHESTRATOR = NOT_ACTIVE`
