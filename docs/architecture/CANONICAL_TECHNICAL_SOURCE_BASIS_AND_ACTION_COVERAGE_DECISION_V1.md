# Canonical Technical Source-Basis and Action-Coverage Decision V1

**Status: CANONICAL_TECHNICAL_SOURCE_BASIS_AND_ACTION_COVERAGE_DECISION = ACTIVE / READ_ONLY_DECISION / NO_WEEKLY_MONTHLY_DERIVATION / NO_TECHNICAL_ACTIVATION.**

## Decision and hard boundary

This bounded evidence decision records what HSI can establish about a source price basis and whether official corporate-action coverage can certify absence of a discontinuity inside one exact instrument/window. It does not fetch, persist, modify, aggregate, resample, score, or activate market data.

- Provider basis is not HSI transformation state.
- HSI_DID_NOT_ADJUST is not PROVIDER_SUPPLIED_RAW.
- No action receipt is not proof that no action occurred.
- An action-free window requires coverage proof.
- Weekly aggregation is not canonical weekly evidence.

The pure decision contract is app.market_data.technical_source_basis_action_coverage. It reuses ProviderPriceBasisState, HistoricalCorporateAction, canonical identity, Timeframe, and the price-adjustment contract. It has no repository, SQLite, provider request, clock, API, UI, diagnostic, portfolio, broker, order, screener, indicator, or bar-builder dependency.

## Authoritative source-basis research

### Upstox historical candles

The official [Upstox Historical Candle V3 documentation](https://upstox.com/developer/api-documentation/v3/get-historical-candle-data/) specifies available units/intervals, depth, request identity and OHLC response structure. Its V3 announcement likewise describes interval and historical-depth expansion. Neither source uses adjusted, unadjusted, raw, split-adjusted, bonus-adjusted, total-return, back-adjusted, or equivalent price-basis terminology for returned candle values. The separate official [Corporate Actions API](https://upstox.com/developer/api-documentation/get-corporate-actions/) supplies event data; it does not define a transformation of V3 candle values.

Therefore:

    UPSTOX_HISTORICAL_PRICE_BASIS = UNKNOWN
    UPSTOX_HISTORICAL_TECHNICAL_CONTINUITY = NOT_READY

Provider agreement is only a diagnostic observation and cannot alter that conclusion. Retained Upstox V3 rows remain immutable and UNKNOWN; a future provider restatement is new external evidence and cannot rewrite HSI's stored observation.

### Dhan history and live observations

Dhan's official support documentation says its **Daily Historical Data** is adjusted for bonuses and splits. [Dhan daily historical adjustment FAQ](https://dhan.co/support/platforms/dhanhq-api/is-the-historical-data-from-dhan-s-data-api-adjusted-for-corporate-actions-like-bonuses-and-splits/) This establishes a provider-adjusted split/bonus fact, not a full canonical method, raw series, factor, revision rule, total-return series, or PIT proof.

    DHAN_DAILY_HISTORICAL_BASIS = PROVIDER_ADJUSTED_UNKNOWN_METHOD
    DHAN_DAILY_HISTORICAL_TECHNICAL_CONTINUITY = PARTIAL / NOT_CANONICALLY_READY

Dhan documents its live market feed as real-time WebSocket data and its data API as including live feeds and historical OHLCV. [Dhan live-feed support](https://dhan.co/support/platforms/dhanhq-api/how-can-i-access-live-market-data-through-dhan/) The current HSI DhanLiveFeedService is a bounded in-memory latest-LTP state; it does not retain session-complete immutable OHLCV bars. A future exact provider/session-aware capture can preserve observed values and HSI observed_at prospectively, but it must retain SOURCE_BASIS_UNKNOWN unless Dhan supplies an authoritative live-basis statement. It is a feasible future path, not an implemented bar-builder.

    DHAN_FORWARD_BASIS_READINESS = PARTIAL
    PROSPECTIVE_IMMUTABLE_SESSION_BAR_CAPTURE = NOT_IMPLEMENTED

### NSE bhavcopy and indices

The retained full-bhavcopy adapter has a source trade-date/session fact but no approved price-basis source fact. Thus it remains UNKNOWN; being first-party does not itself prove raw/unadjusted history. Broad and sector indices remain source/methodology-specific. NSE methodology recognises action-specific index treatment, so an equity split/bonus multiplier must never be applied directly to an index series. [NSE index methodology example](https://archives.nseindia.com/content/indices/Method_Nifty100_Equal_Weight.pdf)

## Versioned source-basis contract

TechnicalSourceBasisDecision carries:

| Field | Meaning and invariant |
| --- | --- |
| source family/version/timeframe | Exact provider-normalization path, never a chart label. |
| provider_basis | RAW, UNKNOWN, PROVIDER_ADJUSTED_UNKNOWN_METHOD, or INDEX_SOURCE_SPECIFIC; a raw claim requires authoritative supporting evidence. |
| hsi_transformation | Separate from provider basis. Current factory decisions use HSI_DID_NOT_ADJUST; it cannot imply RAW. |
| supporting evidence ID/fingerprint | Sorted, non-empty immutable local reference to the exact authoritative semantic statement. It is not a false hash of a remote page. |
| historical / forward readiness | Typed READY, PARTIAL, NOT_READY, or NOT_APPLICABLE, with stable reasons. |
| identity / fingerprint | SHA-256 canonical JSON with normalized ordering. No runtime clock, locale, environment or provider call participates. |

The TechnicalWindowSourceIntegrity combiner allows a technical window only when both source decision is historically READY and its action window is certified. A quiet window therefore cannot upgrade unknown, retrospectively adjusted, or otherwise undocumented provider basis.

## Corporate-action coverage and action-free windows

CorporateActionCoverageAssertion is an explicit, security/window-specific coverage claim. READY requires first-party coverage for every current continuity family:

    SPLIT, BONUS, RIGHTS, DIVIDEND, MERGER, DEMERGER, SYMBOL_CHANGE,
    DELISTING, SUSPENSION, RELISTING

It also requires an authoritative source-evidence reference, the sole
OFFICIAL_SOURCE_WINDOW_COMPLETE reason, exact canonical security, coverage
start/end, source-known time, source evidence ID/fingerprint, and deterministic
content fingerprint. No constructor can promote missing action families,
partial-source reasons, or non-authoritative provenance into READY.

assess_action_free_window uses an assertion and immutable action receipts. It uses only records known by requested as_of and whose effective date is at or before it. Future-effective and source-known-later actions are excluded from historical interpretation.

| State | Meaning |
| --- | --- |
| NO_KNOWN_PRICE_DISCONTINUITY_WITHIN_WINDOW | Only complete, PIT-visible coverage plus no exact in-window action. It is not a provider-basis certificate. |
| KNOWN_SPLIT_BONUS_REQUIRES_DERIVATION_GATE | Exact known split/bonus is visible; the separate V1 split/bonus factor contract remains mandatory. |
| NON_COMPARABLE_ACROSS_WINDOW | Rights, merger/demerger, symbol continuity, delisting/suspension/relisting, or known cash distribution crosses the window. |
| NOT_CERTIFIED | Coverage partial/not-ready/known too late, duplicate action identity, or another absence-of-proof condition. |

Cash dividends do not create a total-return adjustment in this contract. With no approved ordinary-versus-special distribution policy, a known dividend in a continuity-sensitive price lookback prevents action-free certification. This is a comparability gate, not a claim to adjust price or calculate total return. Split/bonus volume factors remain separate from price factors; volume-sensitive diagnostics need both action continuity and valid source volume.

## Direct production receipt audit at 2026-09-05

The read-only audit used frozen eligible universe snapshot nse-universe:fundamental-probe:2d5692582f3f43fda4eb73aa3caf2d34 at 2026-08-25T15:00:38.602331+00:00 and immutable HISTORICAL_CORPORATE_ACTION snapshots. It does not infer unobserved exchange events.

| Audit fact | Current value |
| --- | ---: |
| retained daily OHLCV bars | 1,545,139 |
| canonical-authoritative known-basis bars | 0 |
| Upstox V3 / UNKNOWN | 1,518,604 |
| NSE bhavcopy / UNKNOWN | 48 |
| yfinance / RAW secondary evidence | 26,487 |
| immutable official NSE action receipts | 501 |
| exact action security IDs | 410 |
| action IDs with retained bars | 408 |
| bars on action-security IDs | 290,340 |
| frozen eligible NSE securities | 2,553 |
| eligible securities with accepted receipt | 410 |
| eligible securities without accepted receipt | 2,143 |
| eligible securities with split/bonus receipt(s) | 284 |
| eligible securities with rights/complex receipt(s) | 150 |

| Receipt field / taxonomy | Current value |
| --- | --- |
| source/revision | 501 NSE_OFFICIAL_CORPORATE_ACTION_EXPORT / nse-corporate-action-v1 |
| retained source file | one manually staged CF-CA-equities-25-08-2023-to-25-08-2026.csv |
| effective/ex-date range | 2023-09-01 through 2026-08-25; ex-date 501/501 |
| record-date coverage | 501/501; 2023-09-02 through 2026-08-26 |
| HSI first-observed (as_of) range | 2026-08-24 through 2026-08-30 |
| split / bonus / rights / demerger | 166 / 162 / 138 / 35 |
| dividend / merger / symbol-change retained | 0 / 0 / 0 |
| both parsed ratio fields present and positive | 386/501 |
| accepted receipt purpose missing | 0 |
| accepted identity mapping | 492 exact symbol + canonical ISIN; 9 exact symbol EQ |

The importer deliberately stores only supported, exactly mapped EQ rows. It has no retained exchange-wide accounting of source rows excluded for unsupported purpose, ambiguous symbol, or no canonical identity. The zero unresolved-purpose and identity-blocked values apply only to accepted receipts, not the underlying NSE surface.

The retained source is a manually staged bounded date export. NseCorporateActionsRefreshJob reads local approved CSVs only; it neither downloads nor proves full exchange/history coverage. NSE's official actions surface supports symbol/purpose/period filters and CSV download, and exposes symbol, company name, series, purpose, face value, ex-date, record date and book-closure fields. [NSE corporate-filings actions](https://www.nseindia.com/companies-listing/corporate-filings-actions) That is enough for a future bounded first-party acquisition design, not evidence that retained data is exchange-wide, historically complete, or current after 2026-08-25.

    CORPORATE_ACTION_COVERAGE_COMPLETENESS = PARTIAL
    NO_CORPORATE_ACTION_RECEIPT = NO_PROOF_OF_NO_ACTION

## Continuity matrix for existing technical intelligence

This is research/decision support, not indicator or horizon activation. Potential scale invariance means only under hypothetical uniform positive scaling of every observation in a complete window. It does not cure unknown provider semantics, retrospective revisions, action coverage, PIT, volume, benchmark compatibility, or rule policy.

| Family | Uniform-scale mathematical property | Price/action sensitivity | Volume/action sensitivity | Action-free alone sufficient? | UNKNOWN usable now? | Prospective frozen path | Historical strict PIT now |
| --- | --- | --- | --- | --- | --- | --- | --- |
| RSI | potentially scale-invariant | discontinuity-sensitive | no direct volume | no | no | possible after capture/policy | no |
| ADX / directional movement | potentially scale-invariant; ATR value is not | gap/discontinuity-sensitive | no direct volume | no | no | possible after capture/policy | no |
| ATR | absolute-price-level sensitive | high | no direct volume | no | no | possible after capture/policy | no |
| Ichimoku / Chikou relations | relation only potentially scale-invariant | high; lead/lag continuity required | no direct volume | no | no | possible after capture/policy | no |
| OBV | close-direction relation may be scale-invariant | high | high; split/bonus volume factor required | no | no | possible after capture/policy | no |
| session VWAP | same-session scale relation only | session/source sensitive | high; source volume required | no | no | possible after capture/policy | no |
| Relative Strength | ratio/change relation needs compatible stock/benchmark semantics | high | indirect | no | no | possible after both captures/policy | no |
| Dow / price structure | no approved invariance | high | contextual | no | no | possible after capture/policy | no |
| pivots / support / resistance | absolute-price-level sensitive | high | contextual | no | no | possible after capture/policy | no |
| base patterns | shape may be scale-invariant; policy still needs continuity | high | often high | no | no | possible after capture/policy | no |
| RVOL / volume climax / liquidity-trap proxy | not price-basis substitute | high | high | no | no | possible after capture/policy | no |
| entry / SL / target / R:R | absolute-price-level sensitive | high | contextual | no | no | not authorized by this slice | no |

## Benchmark, sector, historical, and prospective decision

NIFTY 50, NIFTY 500 and sector indices have provider/source-specific action semantics. Relative Strength needs compatible semantics, not an equity split/bonus transformation of index bars. Existing retained benchmark/sector Upstox rows remain UNKNOWN; yfinance is secondary only.

A prospective split is architecturally sound but not operative:

    live provider observation
      -> exact instrument/session-aware HSI bar capture
      -> immutable HSI observed_at and source payload lineage
      -> future first-party action receipt and versioned adjustment derivative

It would never backdate historical truth. A later provider revision would be a distinct observation/conflict rather than mutate the first HSI receipt. Present DhanLiveFeedService has only in-memory latest-price state, so this is PARTIAL feasibility, not active technical radar or stored bars.

## Final readiness decision

| Decision | State | Exact reason |
| --- | --- | --- |
| A. UPSTOX_SOURCE_BASIS | NOT_READY | Official historical-candle documentation does not define adjustment basis. |
| B. DHAN_FORWARD_BASIS_READINESS | PARTIAL | Real-time observation exists; immutable session-bar capture and explicit live basis proof do not. |
| C. NSE_BHAVCOPY_BASIS | NOT_READY | First-party trade-date is not a documented adjustment-basis fact. |
| D. CORPORATE_ACTION_COVERAGE_COMPLETENESS | PARTIAL | One manually staged three-year export; no broad completeness proof. |
| E. SPLIT_BONUS_ACTION_COVERAGE | PARTIAL | Exact retained evidence exists only for sampled source window/cohort. |
| F. RIGHTS_COMPLEX_ACTION_COVERAGE | PARTIAL | Retained rights/demerger evidence exists; complete source and policy coverage do not. |
| G. ACTION_FREE_WINDOW_CERTIFICATION | NOT_READY | Contract exists, but no current security/window has a READY coverage assertion. |
| H. UNKNOWN_BASIS_TECHNICAL_USABILITY | NOT_READY | Quiet action window cannot establish provider candle semantics. |
| I. VOLUME_CONTINUITY | NOT_READY | Split/bonus action and source-volume comparability need exact complete window. |
| J. BENCHMARK_BASIS | NOT_READY | Retained index basis is source-specific/unknown. |
| K. SECTOR_BASIS | NOT_READY | Same index-specific/unknown limitation. |
| L. HISTORICAL_TECHNICAL_CONTINUITY | NOT_READY | Source basis, timing and action completeness are not jointly certified. |
| M. PROSPECTIVE_TECHNICAL_CONTINUITY | PARTIAL | Sound future architecture; no immutable session-bar implementation yet. |
| N. WEEKLY_DERIVATION_GATE | NOT_READY | Daily source basis, timing, action continuity and volume parity are not ready. |
| O. MONTHLY_DERIVATION_GATE | NOT_READY | Same missing daily prerequisites as weekly. |

The truthful current choice is **B**: historical technical continuity remains limited, while a prospective canonical accumulation path can begin only after its capture and action-coverage prerequisites. This does not permit fabrication or block unrelated HSI Core V1 evidence.

## Next exact continuation

NSE_CANONICAL_CORPORATE_ACTION_COVERAGE_BACKFILL_V1

This should be a bounded first-party NSE acquisition/coverage receipt for explicit date range and frozen eligible universe. It must retain raw CSV provenance, source-known time, exact identity outcomes, full accepted/rejected row accounting, and coverage completeness per security/window. It must not call a missing receipt action-free, rewrite bars, promote Upstox basis, derive 1W/1M bars, add indicators/horizon policy, or create technical score, portfolio action, broker access, or execution authority.

ONE_CANONICAL_61_DIAGNOSTIC_REGISTRY = TRUE
SEPARATE_TECHNICAL_BRAIN = FALSE
PRIMARY_TECHNICAL_DISCOVERY = HSI_INTERNAL_RADAR
EXTERNAL_SCREENER_AUTHORITY = OPTIONAL_DISCOVERY_ONLY
NO_INDICATOR_EXPANSION = TRUE
HORIZON_SPECIFIC_TECHNICAL_POLICY = NOT_ACTIVE
MULTI_TIMEFRAME_TECHNICAL_ORCHESTRATOR = NOT_ACTIVE
