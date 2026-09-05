# Canonical Daily Source Session and Publication Semantics V1

**Status: `CANONICAL_DAILY_SOURCE_TEMPORAL_SEMANTICS = ACTIVE / SOURCE_FACTS_AND_FORWARD_ADAPTER = ACTIVE / NO_LEGACY_REWRITE / STRICT_PRODUCTION_PIT_BINDING = NOT_ACTIVE`.**

## Scope

This slice adds immutable, versioned source-time interpretation only. It changes no stored rows, migrations, adjustment basis, weekly/monthly derivation, intraday ingestion, indicator, horizon policy, score, portfolio, broker/order, or execution behavior. `FACT -> DATA -> INTERPRETATION -> INFERENCE` remains fixed.

`market period != source availability != HSI observation`
`interval start != interval end`
`interval end != source publication`
`source publication != HSI observation`

`app/market_data/daily_source_temporal_semantics.py` defines fingerprinted `DailySourceTemporalSemantics` and `DailySourceTemporalFacts`. Its role vocabulary is `INTERVAL_START`, `INTERVAL_END`, `TRADING_DATE`, `SOURCE_PUBLICATION_TIME`, `SOURCE_DISSEMINATION_TIME`, `PROVIDER_OBSERVED_TIME`, `HSI_INGESTED_TIME`, and `UNKNOWN`. It separately records source/version, timezone, session-date rule, source availability, HSI-observation permission, historical/forward applicability, policy/version, evidence ID/reference and fingerprints. The reference fingerprint hashes the retained evidence-ID/reference tuple; it is not an invented hash of an unretained remote document.

| Concept | Factual field | Rule |
| --- | --- | --- |
| Market period | `raw_timestamp`, role, `session_date` | A source interval-start or trading-date fact, never a derived session end. |
| Source availability | `source_available_at` | Present only for an exact authoritative finished-bar publication/dissemination instant. |
| HSI observation | `hsi_observed_at` | Immutable provenance `received_at`; conservative and forward-safe only. |

The existing daily temporal resolver accepts the new `HSI_OBSERVED_AT_FORWARD_ONLY` input and returns `KNOWN_AT_FROM_HSI_OBSERVATION` only when the calendar proves the session/close and HSI received the record no earlier than that close. It means only that HSI could use the record then; it does not claim source publication or backdate a replay.

## Source family audit

Read-only audit of `data/nse_stock_manager.db` found 1,545,139 retained daily rows across 2,561 instruments. Every listed row retains immutable provenance `received_at`; no row retains an exact authoritative historical publication timestamp.

| Source / normalization | Rows | Raw source and stored lineage | Role | Timezone fact | Source availability | HSI fallback | Adjustment |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| Upstox / `upstox-history-v3` | 1,518,604 | Candle element `0` remains unchanged in exchange/provider provenance and legacy `end_time` | `INTERVAL_START` | Provider payload offset; V3 examples use `+05:30` | Unproven | Every row | `UNKNOWN` |
| NSE official / `nse-full-bhavcopy-v1` | 48 | CSV `DATE1`, checked against file date; local trade-date marker with artifact hash/retrieval receipt | `TRADING_DATE` | Importer explicitly uses `Asia/Kolkata` | Unproven | Every row | `UNKNOWN` |
| yfinance / `yfinance-history-v1` | 26,487 | yfinance `Date` and received receipt | `UNKNOWN` for canonical authority | No approved source-time contract | Unproven | Not canonical | `RAW` |

The [Upstox Historical Candle Data V3 documentation](https://upstox.com/developer/api-documentation/v3/get-historical-candle-data/) states that its candle timestamp indicates the **start time of candle's timeframe**. It does not supply a retained finished-candle publication instant. The [NSE EOD historical data page](https://www.nseindia.com/static/market-data/eod-historical-data-subscription) says EOD files are generated at the end of the trading day; it does not provide an exact immutable publication instant for each retained bhavcopy row.

## Upstox legacy isolation and future repair

All retained Upstox V3 raw starts are recoverable. The old adapter also copied that raw **start** to `end_time` and fabricated `start_time = end_time - 24h`. Retained rows are therefore `LEGACY_SEMANTICS_AMBIGUOUS`: no direct update or silent reinterpretation is allowed, and legacy `end_time` is not a trusted daily session end.

Future Upstox ingestion uses `upstox-history-v4-interval-start`. It preserves the raw provider start as `start_time` and provenance, keeps `end_time == start_time` as an explicitly unbound marker, and emits `UPSTOX_DAILY_TIMESTAMP_INTERVAL_START` plus `UPSTOX_DAILY_SESSION_END_UNBOUND`. This does not claim a zero-duration market period; it refuses to fabricate `start + 24h`. Only a governed session contract may derive daily interval end. The strict-consumer guard is false for retained V3 and V4 unbound ends.

Bhavcopy `DATE1` is a source-specific session label, not a publication time. yfinance remains secondary enrichment/research and cannot fill a primary canonical timing or strict-PIT gap.

## Benchmark, sector, and reinterpretation receipt

NIFTY 50 has 746 daily Upstox V3 rows. NIFTY 500 has 938 Upstox V3 rows and 735 yfinance rows. Sector indices have 8,612 daily Upstox V3 rows. No index or sector shortcut exists.

| Source | Rows | Raw recoverable | Role resolved | Session date derivable | Source availability | HSI observation | Historical strict PIT | Forward source facts | Legacy ambiguous/conflicted |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Upstox V3 | 1,518,604 | 1,518,604 | 1,518,604 | 1,518,604 | 0 | 1,518,604 | 0 | 0 (legacy) | 1,518,604 / 0 |
| NSE bhavcopy | 48 | 48 trade-date markers | 48 | 48 | 0 | 48 | 0 | 48 source-facts only | 0 / 0 |
| yfinance | 26,487 | 26,487 | 0 | 0 | 0 | 0 canonical | 0 | 0 | 26,487 / 0 |

“Forward source facts” means only eligibility to enter the calendar/known-at resolver, not technical readiness. No retained V4 rows exist.

## Readiness

| Gate | State | Reason |
| --- | --- | --- |
| `UPSTOX_HISTORICAL_TEMPORAL_READINESS` | `NOT_READY` | Recoverable raw start, mislabelled legacy end, no historical source availability. |
| `UPSTOX_FORWARD_TEMPORAL_READINESS` | `PARTIAL` | V4 captures raw start and HSI observation; ordinary NSE session/close proof is absent. |
| `NSE_BHAVCOPY_HISTORICAL_TEMPORAL_READINESS` | `NOT_READY` | Trade-date exists; historical publication and ordinary session/close proof do not. |
| `NSE_BHAVCOPY_FORWARD_TEMPORAL_READINESS` | `PARTIAL` | Trade-date and HSI receipt can feed the resolver, subject to calendar proof. |
| `YFINANCE_CANONICAL_AUTHORITY` | `NOT_READY` | Secondary research source with no approved canonical timing contract. |
| `BENCHMARK_FORWARD_TEMPORAL_READINESS` | `NOT_READY` | Retained benchmark rows are V3/yfinance only. |
| `SECTOR_FORWARD_TEMPORAL_READINESS` | `NOT_READY` | Retained sector rows are V3 only. |
| `DAILY_SESSION_IDENTITY` / `DAILY_COMPLETENESS` | `NOT_READY` | First-party calendar lacks ordinary-weekday identity/regular-close coverage. |
| `DAILY_KNOWN_AT` / `DAILY_FORWARD_PIT` | `PARTIAL` | HSI-observation boundary exists, subject to session proof; source publication remains unavailable. |
| `DAILY_HISTORICAL_STRICT_PIT` | `NOT_READY` | Zero retained rows receive a historical source-availability certificate. |
| `WEEKLY_DERIVATION_GATE` / `MONTHLY_DERIVATION_GATE` | `NOT_READY` | Daily end/session/known-at and adjustment parity are not certified. |

HSI cannot yet claim trustworthy current/forward daily technical evaluation for the general eligible NSE universe, discovered candidates, holdings, or watchlists. A prospective corrected-source path exists but is not broadly operational or a historical-backtest substitute.

## Next repair and preserved boundaries

`UNKNOWN` adjustment remains `UNKNOWN`. Rules 4 and 14 remain `INSUFFICIENT_DATA`; no daily row is relabelled weekly/monthly, no fake MTF or horizon policy is added, and no multi-timeframe orchestrator is active. The next exact continuation is `CANONICAL_NSE_ORDINARY_SESSION_IDENTITY_AND_CLOSE_EVIDENCE_V1`: effective-dated first-party ordinary-session identity/close evidence only, with no fabricated publication times, adjustment repair, indicators, portfolio, or execution authority.

`ONE_CANONICAL_61_DIAGNOSTIC_REGISTRY = TRUE`
`SEPARATE_TECHNICAL_BRAIN = FALSE`
`HYBRID_TECHNICAL_ARCHITECTURE = FROZEN`
`EXTERNAL_SCREENER_AUTHORITY = DISCOVERY_ONLY`
`NO_INDICATOR_EXPANSION = TRUE`
`HORIZON_SPECIFIC_TECHNICAL_POLICY = NOT_ACTIVE`
`MULTI_TIMEFRAME_TECHNICAL_ORCHESTRATOR = NOT_ACTIVE`
