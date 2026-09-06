# Daily/Weekly Existing Technical Diagnostics Operationalization V1

**Status: `CURRENT_DESCRIPTIVE_TECHNICAL_INPUT = ACTIVE / ONE_CANONICAL_61_DIAGNOSTIC_REGISTRY = TRUE / SEPARATE_TECHNICAL_BRAIN = FALSE / NO_INDICATOR_EXPANSION = TRUE / STRICT_HISTORICAL_PIT = NOT_READY / HORIZON_SPECIFIC_TECHNICAL_POLICY = NOT_ACTIVE / MULTI_TIMEFRAME_TECHNICAL_ORCHESTRATOR = NOT_ACTIVE`.**

## Scope

This slice binds existing canonical diagnostic evaluators to certified
current-descriptive NSE UDiFF Daily reads and persisted, lineage-complete
derived Weekly bars. It adds no Rule ID, indicator, scoring path, technical
vote, horizon policy, signal lifecycle, product API/UI, persistence record,
portfolio access, broker/order call, or execution authority.

The source archive begins on 2024-07-08 and is current-descriptive only.
It cannot establish when a historical source file was available to HSI, so
every strict historical PIT result remains fail-closed as
`STRICT_HISTORICAL_PIT_SOURCE_AVAILABILITY_UNAVAILABLE`.

## Canonical input boundary

`app.universe_analysis.technical_diagnostic_input` is a pure adapter to the
existing `AsOfSnapshot` and `MarketObservation` shapes. It only accepts:

1. a `NseUdiffCertifiedDailyTechnicalRead` in
   `CURRENT_DESCRIPTIVE_TECHNICAL` mode with a ready eligibility certificate;
2. an `NseUdiffWeeklyTechnicalBar` that is ready, closed, derived from that
   certified Daily source, and known at or before the caller-supplied canonical
   as-of cutoff.

It preserves canonical bar ID, raw source observation identity, certified-read
fingerprint, weekly aggregation lineage/fingerprint, timeframe, continuity
state, and the immutable source policy/version. The adapter rejects duplicate
or conflicting Daily lineage, duplicate Weekly identities, future source
evidence, non-current-descriptive source reads, malformed timestamps, and any
overlap between the projected Daily and Weekly observation identities.

The output has two explicitly different snapshots:

| Snapshot | Evidence | Meaning |
| --- | --- | --- |
| `1D` | certified Daily bar observations | genuine Daily canonical technical input |
| `1W` | closed derived Weekly bar observations | genuine Weekly canonical technical input, including Daily-child lineage |

No Daily snapshot may be reused under a Weekly label. The adapter does not
derive Monthly, 4H, 1H, 30m, or 15m bars.

## Current evaluator requirement matrix

The table states live wrapper configuration, not an investment recommendation
or a future timeframe policy. `D` and `W` are minimum observation counts; an
actual price-structure evaluator can still return `INSUFFICIENT_DATA` when its
confirmed-pivot pattern is absent even where the input-count gate passes.

| Rule IDs | Existing family | Evidence class | D | W | Required canonical input / immutable blocker |
| ---: | --- | --- | ---: | ---: | --- |
| 1 | Market regime | `BENCHMARK_RELATIVE` | — | — | Exact certified benchmark history; unavailable in this slice. |
| 2–3 | Sector health / rotation | `SECTOR_RELATIVE` | — | — | Exact certified sector and benchmark history; unavailable. |
| 4 | Primary Trend | `PRICE_ONLY` | 6 | 6 | Price continuity plus genuine Daily **and** Weekly inputs. `TrendRules(3,5,pivot=1)` is unchanged. |
| 5 | Weinstein | `PRICE_ONLY` | — | 5 | Genuine Weekly close history; `WeinsteinRules(3,2)` is unchanged. |
| 6 | Relative strength | `BENCHMARK_RELATIVE` | 4 | — | Price continuity plus exact benchmark, sector and peer cohort. It remains partial/fail-closed without them. |
| 7 | Smart-money proxy | `PRICE_AND_VOLUME` | 3 | — | Daily price and volume continuity; result remains explicitly a proxy. |
| 8 | Liquidity pools | `PRICE_AND_VOLUME` | 2 | — | Daily price and volume continuity. |
| 9 | Wyckoff proxy | `PRICE_AND_VOLUME` | 3 | — | Daily price and volume continuity; no order-flow claim. |
| 10 | Market structure | `PRICE_ONLY` | 6 | — | Daily price continuity and confirmed pivots. |
| 11 | RVOL | `PRICE_AND_VOLUME` | 4 | — | Daily volume continuity; existing `3 / 1.5 / 0.5` settings unchanged. |
| 12–13 | Ichimoku / Chikou | `PRICE_ONLY` | 5 | — | Daily price continuity; existing `2 / 3 / 4 / 1` settings unchanged. |
| 14 | MTF alignment | `PRICE_ONLY` | 5 | 5 | Genuine distinct Daily and Weekly inputs only; no 4H/1H/15m claim. |
| 29 | Valuation multiples | hybrid price + financial | 1 | — | Daily current price plus the existing financial snapshot; financial semantics are unchanged. |
| 31–32, 34 | Risk/trading/scenario synthesis | `TECHNICAL_DEPENDENT` | — | — | Existing upstream canonical results; no new synthesis. |
| 35 | VWAP / value area | `PRICE_AND_VOLUME` | 1 | — | **Not ready:** named canonical session VWAP/value-area semantics are absent. Generic typical-price × volume is not silently promoted. |
| 36 | OBV | `PRICE_AND_VOLUME` | 4 | — | Daily close plus certified volume continuity. |
| 37–46 | Base, pullback, descriptive entry/risk | `EXECUTION_CONTEXT` | 5 | — | Daily price continuity and existing `TradeRules`; outputs remain descriptive evaluator facts, never orders or portfolio instructions. |
| 50–54 | Accumulation/distribution, stops, liquidity events, traps | `PRICE_AND_VOLUME` | 3 | — | Daily price and volume continuity; all retain `PROXY` semantics. |
| 55–56, 59–61 | Crowd/technical contrarian dependencies | `TECHNICAL_DEPENDENT` | — | — | Existing crowd and upstream-rule lineage; this adapter does not manufacture them. |
| 57 | Post-news reaction | `EVENT_DEPENDENT` | 1 | — | Exact event evidence and approved event-session context; Daily/Weekly bars alone are insufficient. |
| 58 | Volume climax proxy | `PRICE_AND_VOLUME` | 3 | — | Daily price and volume continuity; no institutional-flow inference. |

Rules 15–28, 30, 33, and 47–49 have no direct Daily/Weekly technical input
requirement under the existing registry and are intentionally outside this
technical input receipt.

## Runner binding

`Canonical61DiagnosticRunner` retains its canonical strategy reference and
all 61 rule IDs. When a `CanonicalTechnicalDiagnosticInput` is explicitly
supplied, it uses only a ready source timeframe for the technical rules above;
it never falls back to a generic snapshot if that certified timeframe is not
ready. Legacy callers that supply no canonical technical input keep their
previous generic test/evidence behaviour.

The two repaired bindings are exact:

- **Rule 4:** receives the adapter's separate `1W` and `1D` snapshots. Missing
  either one returns the canonical insufficient-data result.
- **Rule 14:** receives `{"daily": 1D, "weekly": 1W}` only where both are
  independently ready. The evaluator's existing duplicate-timeframe rejection
  remains in force.

Rule 35 deliberately returns insufficient data on this canonical path until a
separate named-VWAP semantics contract exists. Rule 6 remains honest about its
benchmark, sector, and peer requirements. Rule 57 remains blocked without
event evidence. The adapter never converts a missing field into neutral,
pass, a score, a setup, a gate, or a trading conclusion.

## Rule-level readiness receipt

`technical_diagnostic_readiness(input, rule_id)` is a non-scoring, immutable
receipt. For each direct or material technical rule it records evaluator
implementation, evidence class, Daily/Weekly/benchmark/sector/volume/event
readiness independently, current-descriptive state, strict-PIT state,
blockers, exact projected observation IDs, and the source policy fingerprint.

It has no global technical-ready boolean. For example, Rule 4 can have Daily
history ready and Weekly history insufficient; Rule 6 can have stock history
ready while benchmark/sector/peer inputs remain blocked.

## Explicit non-activation boundaries

- `STRICT_HISTORICAL_PIT = NOT_READY`.
- Monthly technical input is `NOT_READY`.
- 15m, 30m, 1H and 4H technical input is `NOT_READY`.
- `HORIZON_SPECIFIC_TECHNICAL_POLICY = NOT_ACTIVE`.
- `MULTI_TIMEFRAME_TECHNICAL_ORCHESTRATOR = NOT_ACTIVE`.
- No indicator expansion, technical score, voting mechanism, Technical Brain,
  BUY/SELL/ROTATE output, broker/order interface, or portfolio mutation is
  created.

Real Weekly evidence is not a fake Weekly label. Current-descriptive analysis
is not strict historical PIT. Proxy evidence is not institutional order-flow.
VWAP is not a generic average-price approximation.

## Read-only production audit

`scripts/audit_nse_udiff_current_descriptive_technical_diagnostics.py` reads
only the persisted Weekly artifact table and embedded certified Daily reads. It
does not reconstruct or write Weekly bars, fetch a provider, call an evaluator,
or write SQLite. It reports per-rule ready/partial/not-ready states and exact
blocker counts for every security with certified Daily/Weekly source input,
plus input-readiness-only detail for APARINDS, DEEPINDS, GENUSPOWER, GLAND and
ICICIBANK.

### Final retained current-descriptive audit receipt

The one retained read-only audit examined **224,572** persisted Weekly
artifacts and assembled bounded latest-contiguous inputs for **2,538**
instruments. **598** instruments have a latest Weekly suffix shorter than the
six-observation audit window; the audit never bridges such a gap with older
evidence. Source continuity therefore remains visible as a history
insufficiency rather than a fabricated Weekly series.

| Rule family | Current-descriptive readiness across 2,538 inputs |
| --- | --- |
| 4 Primary Trend | 1,940 ready; 499 partial (Weekly history); 99 not ready (Daily history). |
| 5 Weinstein | 2,007 ready; 531 not ready (Weekly history). |
| 7–9, 11–13, 29, 36–46, 50–54, 58 | 2,538 ready for their existing canonical-input gate. This is evidence readiness only, not a recommendation or setup. |
| 10 Market Structure | 2,439 ready; 99 not ready (Daily history). |
| 14 genuine MTF | 2,007 ready; 531 partial (Weekly history). |
| 1–3, 6 relative families | blocked by certified benchmark/sector history; Rule 6 is additionally blocked by an exact peer cohort. |
| 35 VWAP | 2,538 not ready: `NAMED_VWAP_SEMANTICS_UNAVAILABLE`. |
| 57 Post-news reaction | 2,538 partial: `EVENT_EVIDENCE_NOT_READY`. |
| 31–32, 34, 55–56, 59–61 | not ready: required upstream canonical technical/crowd lineage is not manufactured by this adapter. |

The five-holding input proof is likewise descriptive only: APARINDS,
DEEPINDS, GENUSPOWER and ICICIBANK each have 30 Daily / 6 Weekly observations
and input-ready Rules 4, 5 and 14; GLAND has 10 Daily / 2 Weekly observations,
so Rule 4 and Rule 14 remain partial and Rule 5 remains not ready. All five
retain the same benchmark/sector/peer, event and VWAP blockers above.

`DAILY_WEEKLY_EXISTING_TECHNICAL_DIAGNOSTICS_OPERATIONALIZATION_V1 = ACTIVE_FOR_CURRENT_DESCRIPTIVE_INPUTS`
