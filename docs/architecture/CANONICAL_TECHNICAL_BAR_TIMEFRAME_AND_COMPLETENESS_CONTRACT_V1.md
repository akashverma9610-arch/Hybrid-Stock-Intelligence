# Canonical Technical Bar Timeframe and Completeness Contract V1

**Status: `CANONICAL_TECHNICAL_BAR_CONTRACT = ACTIVE / READ_ONLY_DOMAIN_CONTRACT / NO_STORAGE_MIGRATION / HORIZON_SPECIFIC_TECHNICAL_POLICY = NOT_ACTIVE / MULTI_TIMEFRAME_TECHNICAL_ORCHESTRATOR = NOT_ACTIVE`.**

## Purpose and hard boundaries

This contract establishes temporal truth for canonical technical bars before a
horizon policy, multi-timeframe evaluator, provider integration, external
screener, technical score, cache, or execution path may be activated.  It
extends the meaning of an existing provider-neutral
`CanonicalOHLCVBar`; it does not replace the OHLCV store, mutate retained raw
history, fetch data, write SQLite, create an API/UI surface, or change a
portfolio, broker, order or Six-Gates boundary.

`ONE_CANONICAL_61_DIAGNOSTIC_REGISTRY = TRUE` and
`SEPARATE_TECHNICAL_BRAIN = FALSE` remain unchanged.  The contract is factual:
it preserves `FACT → DATA → INTERPRETATION → INFERENCE` and does not decide a
rule's horizon applicability or produce an action.

## Existing primitives reused

- `app.market_data.models.CanonicalOHLCVBar` remains the market-value carrier.
- `Timeframe` remains the current stored-bar enum; its existing values cover
  1m, 5m, 15m, 30m, 1H, 1D and 1W only.
- `AdjustmentStatus`, `InstrumentIdentity`, exchange/provenance and the
  provider-versioned historical conflict artifacts remain the raw-data source
  truth.
- `CanonicalMarketSessionCalendar`, `CanonicalTradingDay`, and
  `CanonicalSessionPhase` remain the source-injected session/evidence layer.
- Existing snapshot PIT guards remain required for evaluator input.

The new pure module,
`app.market_data.technical_bar_contract`, adds no competing data store.  A
`CanonicalTechnicalBar` is an immutable temporal overlay around one existing
`CanonicalOHLCVBar`; a `TechnicalBarCompletenessReceipt` can also describe an
unavailable future interval without inventing a market bar.

## Canonical interval identity

`CanonicalTechnicalInterval` is a typed `(unit, multiplier, semantics)`
identity, not arbitrary label text.  Its canonical IDs are `15m`, `30m`, `1H`,
`4H`, `1D`, `1W` and `1M`; it can represent other positive multiples without a
model redesign.  A `ProviderIntervalRepresentation` retains the provider's
own interval code separately from canonical identity.

| Interval | Contract state | Current stored/provider state |
| --- | --- | --- |
| 15m / 30m / 1H | Typed future-compatible interval | No stored canonical bars or production on-demand binding. |
| 4H | `FOUR_HOUR_SEMANTICS_UNRESOLVED` only | No native mapping, session composition or resampler.  It cannot become `CLOSED` under V1. |
| 1D | Typed stored-compatible interval | 1,545,139 retained daily bars, but temporal readiness remains partial. |
| 1W | Typed stored-compatible interval | Certified UDiFF Daily-derived artifacts are retained from 2024-07-08 onward; current-descriptive only, with strict historical PIT unavailable. |
| 1M | Typed future-compatible interval | No `Timeframe` storage value or retained monthly bar. |

The 4H identity exists so future evidence can be reported safely; it is not an
approval of generic crypto/FX-style four-hour boundaries.  A later contract may
approve a provider-native convention, an exchange-session segmentation, another
interval, or continued non-support.  V1 selects none of them.

## Session anchoring and canonical identity

Every eligible bar must carry a `TechnicalTradingPeriod`, supplied from
existing calendar/phase evidence.  It retains:

- trading venue and segment;
- exact included trading-session dates;
- timezone-aware period start/end;
- session-calendar identity and fingerprint; and
- exact source identities/fingerprints for its session evidence.

The deterministic `canonical_bar_id` hashes canonical instrument ID, exchange,
segment, interval identity, period identity/fingerprint, and start/end.  It
intentionally excludes provider identity, so observations from two providers
for the same market interval remain reconcilable rather than being silently
treated as unrelated.  Provider provenance remains inside the wrapped source
bar and the complete content fingerprint.  A conflict is therefore evidence,
not a provider-precedence choice.

## Native versus derived lineage

`TechnicalBarOrigin` is exactly one of:

- `NATIVE_SOURCE_BAR` — a provider-originating existing canonical OHLCV bar;
  it must retain a provider interval representation and has no parent lineage.
- `DERIVED_RESAMPLED_BAR` — a prospective derived artifact; it must retain
  sorted source-bar IDs/fingerprints, source intervals/known-at values, and an
  aggregation-policy identity/version.  It cannot carry a provider-native
  interval representation.

Duplicate source IDs, missing source fingerprint, missing aggregate policy,
and a derived `known_at` before any parent `known_at` fail construction.  This
is pure in-memory lineage; derived bars are not persisted by this slice.

Corporate-action IDs are retained as optional immutable lineage references.
They do not repair continuity, change `RAW`/`UNKNOWN`, or mutate retained raw
evidence.  A future adjusted series must be a new versioned artifact with its
raw parents, not a rewrite.

## Completeness and known-at

`TechnicalBarCompletenessReceipt` carries the bar/interval identity, period,
expected and observed source lineage, missing count, adjustment status, volume
readiness, explicit reason codes, `known_at`, state, readiness and a
deterministic fingerprint.

| State | Meaning and eligibility |
| --- | --- |
| `CLOSED` | Requires a period, zero missing sources and `known_at >= period.ends_at`.  It is the only state that can be `READY`. |
| `IN_PROGRESS` | Current period is not complete; historical diagnostics must not consume it. |
| `INCOMPLETE` / `DATA_MISSING` | Required source/session evidence is absent; no interpolation or forward fill. |
| `EVIDENCE_CONFLICTED` | Competing provider/source evidence remains visible and fail-closed. |

For a derived bar, `derived_known_at >= max(source_bar_known_at)` is enforced.
For a native closed bar, `bar_known_at >= bar/period completion` is enforced.
Freshness is deliberately separate: a closed bar can be stale, and a current
quote cannot make an in-progress bar closed.

## Deterministic resampling contract

`derive_closed_bar` is a pure prospective aggregation function.  It requires
an explicit caller-supplied, calendar-certified exact source set; it does not
invent a Friday, session, weekday, or parent-bar list.  It rejects missing or
duplicate coverage, non-closed source bars, absent source known-at, instrument,
calendar/venue/segment mismatch, out-of-period source bars, unresolved 4H,
and incompatible adjustment basis.

Only after those checks may it calculate:

```text
open   = first valid source open
high   = maximum valid source high
low    = minimum valid source low
close  = last valid source close
volume = sum compatible positive source volumes
```

Missing/zero/incompatible source volume yields `VOLUME_NOT_READY` and a null
aggregate volume; it does not fabricate a price failure.  The contract has no
volume-at-price calculation, so VWAP is not Value Area and Value Area remains
unavailable.

## Daily, weekly and monthly meaning

- **1D:** one canonical exchange trading-session bar, not a calendar-day
  assumption.  Existing retained daily bars lack universal session/known-at
  evidence and therefore remain `PARTIAL`, not retrospectively closed by this
  contract.
- **1W:** `CANONICAL_WEEKLY_TECHNICAL_BAR_DERIVATION_V1` now aggregates only
  exact included certified UDiFF Daily sessions.  A holiday-shortened week
  ends at its actual final trading session; a Friday holiday never creates a
  synthetic Friday bar or future leakage.  It is current-descriptive only and
  does not activate diagnostics or multi-timeframe assembly.
- **1M:** follows the same exact included-session rule through its final
  trading session.  It cannot expose month-end information mid-month.  Current
  storage has no monthly timeframe, so V1 defines semantics only.

For intraday 15m/30m/1H, the same period contract requires explicit start/end,
session anchor, no cross-session/overnight contamination, known-at after
completion, and a native-source representation or a separately approved
resampling policy.  It does not assume that a provider's label already has
those properties.

## Benchmark, sector and external-discovery parity

NIFTY 50, NIFTY 500, and all sector-index bars must pass the same interval,
period, closed-bar, known-at, adjustment and conflict semantics as a stock bar.
Relative Strength may later compare only comparable canonical intervals.

An external provider may later emit a `TECHNICAL_DISCOVERY_EVENT`, but a source
interval, RSI/EMA/ADX/VWAP value, or non-alert is never a canonical bar or
diagnostic result.  It cannot bypass this contract.  An alert remains positive
discovery evidence only; a non-alert remains
`PER_SECURITY_NEGATIVE_EVALUATION_UNKNOWN` unless independent evidence proves
otherwise.

## Rule 4 and Rule 14 safety correction

The all-61 runner previously supplied its one snapshot twice as `daily` and
`weekly`.  That is not multi-timeframe evidence.  The runner now supplies no
weekly snapshot and only one daily snapshot, so Rule 4 and Rule 14 fail closed
with their existing `INSUFFICIENT_DATA` result until distinct canonical
timeframe snapshots are supplied.  The evaluator also rejects equal snapshot
IDs or overlapping observation IDs for direct callers.  No rule ID, score,
provider, persistence, horizon mapping, or orchestration behaviour was added.

## Current readiness matrix

| Timeframe | Interval identity | Session/completeness/known-at | Native/derived status | Adjustment / benchmark / sector parity | Operational readiness |
| --- | --- | --- | --- | --- | --- |
| 15m | Defined | Contract-defined; no source evidence | Future native/on-demand only | No retained parity | `NOT_READY` |
| 30m | Defined | Contract-defined; no source evidence | Future native/on-demand only | No retained parity | `NOT_READY` |
| 1H | Defined | Contract-defined; no source evidence | Future native/on-demand only | No retained parity | `NOT_READY` |
| 4H | Unresolved | Cannot be closed or derived in V1 | None | None | `SEMANTICS_UNRESOLVED` |
| 1D | Defined | Existing rows have start/end but not a universal completed-session/known-at proof | Native retained | Mostly `UNKNOWN` adjustment; daily benchmark/sector partial | `PARTIAL` |
| 1W | Defined | Certified UDiFF session/receipt proof for eligible source-era weeks | Derived from certified Daily only | UDiFF-only current-descriptive subsets | `READY` for bar derivation; diagnostics remain `NOT_ACTIVE` |
| 1M | Defined | Exact source-session rule defined; no retained monthly bars | Future derived only | Requires daily parity first | `NOT_READY` |

## Daily audit and derivation feasibility

The previous read-only audit remains authoritative: 1,545,139 daily OHLCV
bars cover 2,561 instruments; 1,518,652 are `UNKNOWN` adjustment and 26,487
are `RAW`; 11,279 have zero/null volume.  Nominal eligible-equity daily ID
coverage was 2,551/2,553, not a PIT-complete claim.  NIFTY 50, NIFTY 500 and
eight sector indices are daily-only.

Weekly aggregation is now canonical only for certified UDiFF Daily subsets
with exact coverage, identity and action lineage; it remains **not strict
historical-PIT-ready** because original source availability is unavailable.
Monthly aggregation remains unimplemented.  The contract makes each missing
fact explicit rather than treating arithmetic possibility as eligibility.

## Non-goals and next decision

This slice does not activate horizon-specific mappings, timeframe voting,
technical consensus, a technical score, cache/storage, any provider or screener
integration, corporate-action repair, portfolio work, orders, brokers or
execution.  It does not state that a Rule is suitable for an interval.

`HORIZON_SPECIFIC_TECHNICAL_POLICY_V1` remains unsafe until actual bar inputs
can instantiate the distinct closed canonical intervals it would reference.
The single next bounded repair is:

`CANONICAL_DAILY_TECHNICAL_BAR_KNOWN_AT_AND_COMPLETENESS_EVIDENCE_V1`

It should map retained daily provider/source receipts to exact session-period
and known-at evidence without rewriting bars, selecting a freshness threshold,
or activating weekly/monthly derivation.  It is a focused evidence/adapter
decision, not broad data engineering.

`4H_SEMANTICS = UNRESOLVED`

`HORIZON_SPECIFIC_TECHNICAL_POLICY = NOT_ACTIVE`

`MULTI_TIMEFRAME_TECHNICAL_ORCHESTRATOR = NOT_ACTIVE`
