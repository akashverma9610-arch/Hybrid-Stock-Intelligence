# NSE UDiFF Daily History Integrity and Continuity Closure V1

**Status:** `IMPLEMENTED_SESSION_COVERAGE / FAIL_CLOSED_SELECTION_CONTRACT / CONTINUITY_ELIGIBILITY_NOT_READY / NO_TECHNICAL_ACTIVATION`.

This closure follows the additive [UDiFF Daily Price-History Backfill](NSE_UDIFF_CANONICAL_DAILY_PRICE_HISTORY_BACKFILL_V1.md). It records integrity facts and a pure, unintegrated selection contract. It does not rewrite bars, resolve a conflict by preference, derive an adjusted series, derive Weekly bars, calculate an indicator, change canonical historical reads, or affect a diagnostic, Brain, portfolio, broker, or order.

## Frozen authority and time boundary

For the source era beginning **2024-07-08**, the retained source is unchanged:

| Field | Frozen value |
| --- | --- |
| Source family/version | `NSE_CM_UDIFF_FINAL_BHAVCOPY` / `nse-udiff-final-bhavcopy-v1` |
| Authority | `PRIMARY_EXCHANGE` |
| Market-fact basis | `EXCHANGE_EOD_TRADE_PRICE` |
| Raw storage basis | `RAW` exchange observation, with immutable source lineage |
| Provider comparison | `UPSTOX_HISTORICAL_PRICE_BASIS = UNKNOWN` |

Primary exchange authority is not contingent on numerical agreement with another provider. A source trade/session fact is not an assertion that HSI knew that fact on the historical trade date: every archive retains HSI `observed_at`, while original NSE publication/dissemination time remains unavailable. Strict historical PIT therefore remains separately `NOT_READY`.

## Deterministic UDiFF-era session receipt

`app.market_data.nse_udiff_daily_integrity` adds the versioned immutable session-coverage receipt `NSE_UDIFF_DAILY_SESSION_COVERAGE_MANIFEST`. It covers every requested weekday and preserves:

- labelled NSE trade date and exact source session label(s), when a retained artifact contains them;
- artifact/receipt identity, immutable fingerprint, and source gap classification;
- first-party calendar source identifiers/fingerprints for a non-trading conclusion; and
- an explicit `as_of` supplied by the caller, never runtime wall-clock time.

For the audited interval, 532 dates are `ARTIFACT_VALID_SESSION`, all carrying source session `F1`; 29 dates are `CONFIRMED_NON_TRADING_DAY`; no date is `EXPECTED_SESSION_SOURCE_MISSING` or `HISTORICAL_SESSION_UNRESOLVED`. Thus the 561 requested weekdays divide into 532 observed source sessions and 29 first-party-supported no-session dates. A missing file alone remains neither evidence of a holiday nor permission to synthesize a session.

### Source-unavailable reconciliation

All 29 source-unavailable dates now resolve to `CONFIRMED_EXCHANGE_HOLIDAY` through the existing NSE capital-market calendar. The two previously uncovered election dates are grounded in NSE's date-specific circular amendments: [CMTR64960](https://nsearchives.nseindia.com/content/circulars/CMTR64960.pdf) for 2024-11-20 and [CMTR72260](https://nsearchives.nseindia.com/content/circulars/CMTR72260.pdf) for 2026-01-15. The other 27 were already covered by the retained first-party annual NSE holiday schedules.

| Classification | Dates | Count |
| --- | --- | ---: |
| `CONFIRMED_EXCHANGE_HOLIDAY` | 2024-07-17, 2024-08-15, 2024-10-02, 2024-11-15, 2024-11-20, 2024-12-25; 2025-02-26, 2025-03-14, 2025-03-31, 2025-04-10, 2025-04-14, 2025-04-18, 2025-05-01, 2025-08-15, 2025-08-27, 2025-10-02, 2025-10-22, 2025-11-05, 2025-12-25; 2026-01-15, 2026-01-26, 2026-03-03, 2026-03-26, 2026-03-31, 2026-04-03, 2026-04-14, 2026-05-01, 2026-05-28, 2026-06-26 | 29 |
| `EXPECTED_SESSION_SOURCE_MISSING` | none | 0 |
| `HISTORICAL_SESSION_UNRESOLVED` | none | 0 |

## Contained row and identity exceptions

The retained archive audit is deterministic and does not repair source values.

| Fact | Count | Classification and containment |
| --- | ---: | --- |
| Raw source rows | 1,659,029 | Immutable ZIP evidence; no source row is discarded. |
| Current-target rows with exact ISIN/current-symbol match before OHLC validation | 1,104,131 | Exact source-target match only; this is not historical lifecycle continuity. |
| Valid normalized exact-identity observations | 1,103,937 | Additive raw observations; 1,103,153 inserts plus immutable same-provider conflicts. |
| Invalid rows | 194 | Every retained raw-row revalidation failed only `NSE_UDIFF_OHLC_INVALID` (impossible OHLC ordering). No guessed repair enters a bar. |
| Identity discontinuities | 14,723 | `ISIN` matches a current target but source `TckrSymb` differs from the current symbol. The importer classifies all as `IDENTITY_DISCONTINUITY`; it never backward-maps a current symbol. |
| Eligible-universe exclusions | 540,175 | `OUT_OF_ELIGIBLE_UNIVERSE`; raw source evidence is retained. |

The 14,723 discontinuities occur in 63 exact current-symbol/source-symbol pairings. The dominant raw-source series is `EQ` (11,764 rows), with `BE` (2,944) and `BL` (15) also represented. This establishes current-universe backward mismatch as the importer classification, but does **not** prove a historical ISIN/symbol/lifecycle successor chain. Existing `HISTORICAL_NSE_SESSION_IDENTITY` observations are session points; there are currently **0** `HISTORICAL_SECURITY_IDENTITY` effective-dated receipts. Accordingly, exact effective historical continuity is certified for **0** UDIFF technical windows in this closure, not inferred from ISIN or symbol alone.

## Same-provider conflict integrity

All 784 existing immutable conflict artifacts were audited. Every one is `CONFLICT_UNRESOLVED / INGESTION_KEY_COLLISION`: the stored and incoming rows share the same official artifact URL but carry different UDIFF `FinInstrmId` provider references. No artifact supports `first row wins`, `latest row wins`, maximum-volume selection, or a source correction interpretation.

| Conflict fact | Result |
| --- | --- |
| UDIFF conflict artifacts | 784 across 354 canonical instruments |
| Same source identity | 784 |
| Different UDIFF provider instrument reference | 784 |
| Normalizer-version difference | 0 |
| Provider-version difference | 0 |
| Resulting technical eligibility | blocked per conflicting instrument/session |

The most common differing-field tuple is all OHLC, volume, turnover, and trade count (725 artifacts). All competing observations and original raw source evidence remain immutable. The new selection boundary records conflict fingerprint(s), returns `CONFLICT_UNRESOLVED`, and returns no selected provider.

## Cross-provider divergence: diagnostic only

The source is not re-ranked by this audit. The recorded aggregate overlap has 813,843 UDIFF/Upstox observations; only 514 are within one paisa on all OHLC values and only 15 also have exact volume. The deterministic diagnostic recognizes exact/near match, volume-only mismatch, constant OHLC ratio, one-session shift, field mapping, and irregular mismatch without transforming either provider.

Five portfolio holdings and two known-action samples were independently audited from provider-versioned raw bars:

| Instrument | UDIFF / Upstox rows | Overlap | Near OHLC | Exact volume | Classification |
| --- | ---: | ---: | ---: | ---: | --- |
| APARINDS | 532 / 537 | 401 | 0 | 0 | `IRREGULAR_UNEXPLAINED` |
| DEEPINDS | 532 / 537 | 401 | 0 | 0 | `IRREGULAR_UNEXPLAINED` |
| GENUSPOWER | 532 / 537 | 401 | 0 | 0 | `IRREGULAR_UNEXPLAINED` |
| GLAND | 532 / 537 | 401 | 0 | 0 | `IRREGULAR_UNEXPLAINED` |
| ICICIBANK | 532 / 537 | 401 | 0 | 0 | `IRREGULAR_UNEXPLAINED` |
| Known split sample `NSE:INE863B01029` | 532 / 8 | 7 | 0 | 0 | `IRREGULAR_UNEXPLAINED` |
| Known bonus sample `NSE:INE04AK01028` | 532 / 8 | 7 | 0 | 0 | `IRREGULAR_UNEXPLAINED` |

Three additional exact-identity samples produced the same result except `NSE:IN9623B01058`, which had 2 near-OHLC sessions out of 398 overlaps. No representative sample has a constant OHLC multiplicative ratio, a date-shift match, or a field-mapping match. This rules out those simple, source-wide storage hypotheses for the audited samples; it does not attribute the irregular relation to an unproven provider adjustment method, nor does it repair Upstox. `UPSTOX_HISTORICAL_PRICE_BASIS` remains `UNKNOWN`.

## Canonical daily selection boundary

`select_eligible_udiff_daily_bar` is a pure, unintegrated, era-scoped contract. Its only success output is `SELECTED_UDIFF`; it has no path that returns Upstox, yfinance, or a merged candle. It requires all of:

1. trade date in the UDIFF era, calculated from the logical Asia/Kolkata source-session boundary rather than UTC midnight;
2. Daily UDIFF raw bar contract and validated UDIFF session coverage entry;
3. no same-provider `CONFLICT_UNRESOLVED`; and
4. an exact `RESOLVED` effective-dated historical-security identity at that bar's PIT cutoff.

Failures are explicit: `OUT_OF_ERA`, `UDIFF_BAR_INVALID`, `SOURCE_COVERAGE_UNAVAILABLE`, `CONFLICT_UNRESOLVED`, or `HISTORICAL_IDENTITY_UNRESOLVED`. A caller must eventually add requested-window continuity checks before technical use; this closure neither wires the contract into generic reads nor overrides existing Core V1 source priority. With zero effective-dated historical identity receipts, it intentionally certifies no production technical daily window today.

## Corporate-action and continuity composition

Existing corporate-action and technical-price-adjustment contracts are reused unchanged. In the UDIFF era, 3,052 existing action receipts intersect: 119 splits, 114 bonuses, 105 rights, 2,686 dividends, and 28 demergers. Raw UDIFF price and volume never change.

| Holding | UDIFF rows | UDIFF conflicts | Action intersection | Price continuity / volume continuity / Daily eligibility |
| --- | ---: | ---: | --- | --- |
| APARINDS | 532 | 0 | 2 dividends | `NOT_CERTIFIED` / `NOT_CERTIFIED` / blocked on effective identity and action coverage |
| DEEPINDS | 532 | 0 | none | `NOT_CERTIFIED` / `NOT_CERTIFIED` / blocked on effective identity and action coverage |
| GENUSPOWER | 532 | 2 | 1 demerger | `NOT_CERTIFIED` / `NOT_CERTIFIED` / blocked on conflict, effective identity, complex action |
| GLAND | 532 | 0 | 3 dividends | `NOT_CERTIFIED` / `NOT_CERTIFIED` / blocked on effective identity and dividend price policy |
| ICICIBANK | 532 | 8 | none | `NOT_CERTIFIED` / `NOT_CERTIFIED` / blocked on conflict and effective identity |

An absence of a recorded action is not action-free certification. Existing NSE corporate-action coverage explicitly remains `LIFECYCLE_SOURCE_REQUIRED`; therefore action-free certificates are **0**. Future price-only and volume-sensitive windows must remain separate: a split/bonus may use the established derived-adjustment contract only after its own gate, while rights, demergers, and other complex actions fail closed. Dividends do not turn raw price into total return; volume continuity is independently unverified across share-count transformations.

## Whole-universe audit and readiness

| Measure | Result |
| --- | ---: |
| Current instruments with at least one UDIFF raw Daily observation | 2,553 |
| Instruments with all 532 observed UDIFF session bars | 1,707 |
| Instruments with partial retained UDIFF session history | 846 |
| Conflict-free UDIFF instruments | 2,199 |
| Instruments with effective-dated historical identity ready | 0 |
| Conflict-free, identity-ready technical windows | 0 |
| Certified price-continuity windows | 0 |
| Certified volume-continuity windows | 0 |
| Certified action-free windows | 0 |

| Gate | State | Exact reason |
| --- | --- | --- |
| A. `UDIFF_SESSION_COVERAGE` | `READY` | 561 requested weekdays have deterministic outcomes: 532 source sessions, 29 confirmed no-session dates. |
| B. `UDIFF_SOURCE_GAP_RECONCILIATION` | `READY` | All 29 formerly unavailable dates have first-party-supported holiday classifications. |
| C. `SAME_PROVIDER_CONFLICT_INTEGRITY` | `PARTIAL` | All 784 are classified and preserved, but remain unresolved and excluded. |
| D. `UDIFF_INVALID_ROW_CONTAINMENT` | `READY` | 194 impossible-OHLC source rows remain raw evidence and entered no bar. |
| E. `HISTORICAL_SECURITY_IDENTITY_CONTINUITY` | `NOT_READY` | No effective-dated historical identity receipts; current identity cannot be backward-projected. |
| F. `CROSS_PROVIDER_DIVERGENCE_CLASSIFICATION` | `PARTIAL` | Deterministic audit exists; material relationship is irregular/unexplained and no provider repair is authorized. |
| G. `CANONICAL_DAILY_SOURCE_SELECTION` | `PARTIAL` | Fail-closed UDIFF-only selection contract exists but no production window satisfies effective identity. |
| H. `RAW_EXCHANGE_DAILY_HISTORY` | `READY` | Exchange-authoritative raw UDIFF artifacts and 1,103,153 additive observations are retained. |
| I. `PRICE_CONTINUITY_ELIGIBILITY` | `NOT_READY` | Requires effective identity and window-specific action coverage/adjustment readiness. |
| J. `VOLUME_CONTINUITY_ELIGIBILITY` | `NOT_READY` | Requires the price gate plus independently verified share-count continuity. |
| K. `CORPORATE_ACTION_COMPOSITION` | `PARTIAL` | 3,886 immutable action receipts exist, but full lifecycle/window coverage is not certified. |
| L. `ACTION_FREE_WINDOW_CERTIFICATION` | `NOT_READY` | Existing coverage remains `LIFECYCLE_SOURCE_REQUIRED`; zero certificates. |
| M. `CURRENT_DESCRIPTIVE_DAILY_TECHNICAL_DATA` | `PARTIAL` | Raw authoritative facts/session coverage are ready; canonical continuity-eligible technical windows are not. |
| N. `STRICT_HISTORICAL_PIT_TECHNICAL_HISTORY` | `NOT_READY` | Original historical source publication/dissemination time is absent. |
| O. `DAILY_INDICATOR_ACTIVATION` | `NOT_ACTIVE` | Explicitly out of scope. |
| P. `WEEKLY_DERIVATION_GATE` | `NOT_READY` | No eligible continuity-certified daily source window; Weekly bars are not derived. |
| Q. `MONTHLY_LONG_HISTORY_READINESS` | `NOT_READY` | UDIFF era is roughly two years and no continuity certification exists. |

## Preserved boundaries and exact next continuation

```text
ONE_CANONICAL_61_DIAGNOSTIC_REGISTRY = TRUE
SEPARATE_TECHNICAL_BRAIN = FALSE
PRIMARY_TECHNICAL_DISCOVERY = HSI_INTERNAL_RADAR
EXTERNAL_SCREENER_AUTHORITY = OPTIONAL_DISCOVERY_ONLY
NO_INDICATOR_EXPANSION = TRUE
UPSTOX_HISTORICAL_PRICE_BASIS = UNKNOWN
```

`FACT → DATA → INTERPRETATION → INFERENCE` remains intact. This closure creates no technical voting, score, signal, portfolio mutation, execution authority, or live acquisition. The exact next safe continuation is:

`NSE_UDIFF_CONFLICT_SEMANTICS_AND_HISTORICAL_SECURITY_IDENTITY_CONTINUITY_V1`

It must establish first-party-effective historical identity/lifecycle chains and deterministic semantics for the 784 same-source key collisions before any current descriptive technical window or Weekly derivation can become `READY`.
