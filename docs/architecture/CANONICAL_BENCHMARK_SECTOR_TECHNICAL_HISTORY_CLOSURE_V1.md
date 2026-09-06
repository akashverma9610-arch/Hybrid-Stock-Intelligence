# Canonical Benchmark / Sector Technical History Closure V1

Status: `CURRENT_DESCRIPTIVE_TECHNICAL / PARTIAL / STRICT_HISTORICAL_PIT_NOT_READY`

## Scope

This closure supplies first-party calculated-index Daily OHLC evidence to the
existing canonical 61-diagnostic evaluator only for Rule 1 (Market Regime),
Rule 2 (Sector Health), Rule 3 (Sector Rotation), and Rule 6 (Relative
Strength). It changes neither diagnostic definitions nor thresholds,
indicators, policy horizons, scoring, Six Gates, portfolio state, orders, or
broker authority.

`NIFTY_50` is the already configured `Canonical61DiagnosticRunner` benchmark.
No `NIFTY_500` history is added to this path merely for catalogue completeness.

## First-party index contract

The official NSE Indices Historical Data report and its first-party historical
data response are used only under the bounded `NseIndicesOfficialOhlcClient`.
For an exact official index name, the parser accepts a date only when the
response supplies valid daily `OPEN`, `HIGH`, `LOW`, and `CLOSE` fields. It
records:

- `provider = NSE_INDICES_OFFICIAL`;
- `index_level_basis = OFFICIAL_INDEX_LEVEL_OHLC`;
- `index_return_family = PRICE_RETURN_INDEX`; and
- hash-addressed raw response artifact plus immutable observation lineage.

This is an index-level price-return series. It is not an equity security bar,
does not receive equity split/bonus adjustment, and never obtains invented
volume, delivery, traded quantity, or VWAP. Price-return and total-return
indices are never mixed: the technical trend and relative-strength path uses
only the exact price-return index requested by the existing evaluator.

Each response is exact-name checked. An empty, close-only, malformed,
conflicting, or identity-mismatched response yields its specific unavailable
state; it cannot be repaired with Upstox, Yahoo, an ETF, an index proxy, or a
synthetic OHLC bar.

Compact immutable Core snapshots are used instead of equity historical-bar
storage:

- `OFFICIAL_INDEX_OHLC_ARTIFACT`
- `CANONICAL_INDEX_OHLC_OBSERVATION`

Replaying the same economic index/session OHLC leaves canonical observations
unchanged. A changed value for the same index/session is a closed conflict;
an additional source artifact with the same exact values is retained without
duplicating the canonical observation.

## Mapping and current availability

The official sector-index registry remains the sole mapping authority.
`EXACT_OFFICIAL` mappings are converted deterministically to
`NSE_SECTOR_INDEX:<CANONICAL_SECTOR>`. No industry-to-sector or broad
macro-sector relation is inferred. The consumer is intentionally partial:
an unmapped or OHLC-unavailable sector remains blocked.

The stored current mapping inventory contains 19 represented taxonomy sectors,
of which 12 have an exact official sector-index mapping. The first operational
retrieval showed that first-party field availability is per-index: some exact
official series publish full OHLC while other exact mappings presently expose
only close data or no rows. Such mappings do not become technical OHLC inputs.

The separate current-sector ranking service and its close-only evidence remain
unchanged. They are not repurposed as Rule 1--3/6 price-bar evidence.

## Rule assembly and session rules

`CanonicalBenchmarkSectorTechnicalInput` is a deterministic adapter around
the existing certified Daily equity input plus official index observations:

| Rule | Required canonical input | Fail-closed condition |
| --- | --- | --- |
| 1 | `NIFTY_50` Daily price-return OHLC | `BENCHMARK_HISTORY_NOT_READY` |
| 2 | exact sector-index and `NIFTY_50` Daily OHLC | `SECTOR_INDEX_NOT_MAPPED` or `SECTOR_HISTORY_NOT_READY` |
| 3 | exact sector-index and `NIFTY_50` Daily OHLC | `SECTOR_INDEX_NOT_MAPPED` or `SECTOR_HISTORY_NOT_READY` |
| 6 | certified equity Daily observations and aligned `NIFTY_50` OHLC; exact sector OHLC when available | `DAILY_*`, `BENCHMARK_HISTORY_NOT_READY`, or `SESSION_ALIGNMENT_FAILED` |

Rule 6's existing numerical calculation/classification uses stock-versus-
benchmark return. Its passed `sector` and `peers` values are currently
descriptive only; the evaluator neither calculates with peers nor changes its
classification from peer data. Therefore the accurate state is
`PEER_COHORT_NOT_APPLICABLE`, not a fabricated cohort or new minimum count.
Sector context is included only when exact and session-aligned.

For Rule 6 every stock session selected by the certified Daily read must have
the same-date benchmark session. The adapter selects that exact intersection;
it does not compare a stock's final session with a newer index close, forward
fill, or substitute the preceding index level. Rules 1--3 use their own exact
index windows. No Weekly index bars are created because active Rules 1--3/6
consume only Daily history.

## As-of boundary

This evidence is `CURRENT_DESCRIPTIVE_TECHNICAL` only. Index observations are
usable only at or after both their session close and their retrieval time.
Certified equity input may be rebuilt at that later current-descriptive cutoff
without claiming that the index source was historically known. Consequently:

`STRICT_HISTORICAL_PIT = NOT_READY`

No historical backtest or frozen historical Brain trial receives this data
until independent historical source-availability evidence exists.

## Permanently preserved boundaries

- `CANONICAL_DAILY_TECHNICAL_INPUT = READY`
- `CANONICAL_WEEKLY_TECHNICAL_INPUT = READY`
- `ONE_CANONICAL_61_DIAGNOSTIC_REGISTRY = TRUE`
- `SEPARATE_TECHNICAL_BRAIN = FALSE`
- `NO_INDICATOR_EXPANSION = TRUE`
- Rule 35 remains `NAMED_VWAP_SEMANTICS_UNAVAILABLE`.
- Rule 57 remains event-evidence dependent.
- No horizon-specific policy or multi-timeframe technical orchestrator is
  activated.

## Next decision

After the measured current-universe audit, the next slice is selected from the
dominant remaining blocker only: horizon/timeframe applicability if daily and
weekly diagnostics are broadly ready; prospective capture if source freshness
is dominant; or a narrow peer-cohort policy only if a future Rule 6 evaluator
actually adopts peers as a numerical/classification input.
