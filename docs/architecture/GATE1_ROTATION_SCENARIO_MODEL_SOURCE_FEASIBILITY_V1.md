# Gate-1 Rotation Scenario Model Source Feasibility V1

Status: `FEASIBILITY_AUDITED / GOVERNANCE_AND_TESTS_ONLY / NOT_ACTIVE`

Decision **C — `SCENARIO_MODEL_NOT_YET_FEASIBLE`**.

Baseline: `979543d1627c1b4ce09bd3dcec82824487b6dc48` on `main`.
This is one bounded feasibility slice; it neither implements a model nor starts
the recommended continuation. Its [machine-readable readiness matrix](GATE1_ROTATION_SCENARIO_MODEL_SOURCE_FEASIBILITY_V1.json)
and [governance tests](../../tests/unit/test_gate1_rotation_scenario_model_source_feasibility.py)
are audit artifacts, not runtime authority.

Machine artifact fingerprint:
`sha256:ae287baed26f5d57248284c044d959ad37b505402261b45394a9a4a1f25c95e3`.

The accepted [scenario contract](GATE1_ROTATION_ECONOMIC_SCENARIO_CONTRACT_V1.md)
is unchanged: `gate1-rotation-economic-scenario / v1`,
`sha256:b4f5c83f33c44c889218823041800d80507733b1932b89529c5aed26ea8c6e14`.
Its parent [V2.4 approval](EXECUTION_GATE_POLICY_V2_COMPOSITE_GOVERNANCE_APPROVAL_2.md)
also remains immutable. `six-gates-production-v1 / v1` remains active; proposed
V2 remains **NOT_ACTIVE**. No source producer is registered.

## 1. Decision and implementability

HSI has reusable canonical data, deterministic descriptors, immutable storage,
PIT guards and an independent gate-authority boundary. It does **not** currently
have an approved, calibrated paired-outcome method that establishes either
`incumbent_economic_result_inr` or `challenger_economic_result_inr` at a chosen
decision cutoff. Both remain unavailable, not zero.

Decision A is unsupported. Decision B would imply that responsible model
implementation is reachable merely by closing identified bounded inputs/policies.
The gaps here also include the methodological estimand, horizon, historical
knownness/comparability of calibration cohorts and empirical adequacy. These
are foundational research questions, not just a missing adapter. Therefore C
is the truthful current decision; it does not mean the architecture is unusable.

No model family, sample-size minimum, horizon, probability, expected return,
tax rate, slippage value or monetary rounding rule is selected in this study.
No direct model implementation is justified now.

## 2. Audit method and evidence limits

Repository inspection covers schemas, readers, source authorities, source
timing/adjustment contracts, portfolio reconstruction, Watch/router, targets/RR,
calibration, forward paper, backtests and governance. The machine artifact lists
inspected paths and LF-normalized file fingerprints. It inherits the frozen
predecessor pins and binds its own artifact and data-audit fingerprints.
The source search included expected/projected/probabilistic/scenario returns,
forecast/terminal/target prices, terminal values, reward-to-risk, target ladders,
expected R, MFE/MAE, expectancy, outcome distributions and forward studies.

Production metadata was read with SQLite URI `mode=ro`, `query_only=ON` and
a read transaction. The committed aggregate capture is dated
`2026-09-14T15:30:56.149868+00:00`; that is **audit observation time**, not an
economic decision cutoff or a backdated historical availability assertion.
There was no source acquisition, credential access, application repository
constructor/migration, database write or private full-payload export.

The database is approximately 18.53 GB. A provider/timeframe full aggregation was
interrupted by a four-second safety bound. This is a query limit, not proof of
database corruption or an absent source. No whole-database hash or exhaustive
integrity/data-coverage claim is made. Counts and samples below are explicitly
bounded audit evidence, not model-training certification.

| Stored evidence | Exact observed quantity / implication |
| --- | --- |
| Historical bars | 2,663,799; row count is not session count or unique comparable observations |
| Historical bar conflicts | 795 artifacts; affected windows require their existing conflict rules |
| New canonical historical membership | 762 CoreApiSnapshot records; legacy `historical_memberships` is empty |
| Historical security identities / lifecycle records | 201 / 1,340 |
| NSE master / session identity records | 120,821 / 61,850; observations, not guaranteed complete security-date coverage |
| Historical corporate actions / raw action observations | 3,886 / 7,263; one coverage assessment, not blanket clearance |
| Official index close / OHLC observations | 992 / 2,229 across indices; no universal index coverage claim |
| Delivery / current sector rankings | 9,122 / 5 |
| Watch run artifacts / market-technical artifacts | 12 / 5; not 12 individual signals or five complete training cohorts |
| Canonical scorecards / diagnostics / FinancialFacts | 3 / 2,074 / 6,118; exact cutoff completeness remains unverified |
| Portfolio | One snapshot, five holdings, five transactions, zero portfolio corporate-action rows; cash UNKNOWN |
| Rotation comparisons / replay evaluations | Zero / zero |
| Paper outcomes / performance reports / OOS window results | Zero / zero / zero |
| Forward paper | Three run receipts, zero studies/events; sampled latest run admitted zero and processed zero sessions |
| Decision outcome links | 43; sampled outcome type is `SELL_SIDE_DECISION_EVENT`, not a realized return |
| Quote/depth | One stored quote; bid/ask absent, bid/ask quantities zero, August 2026 receipt; no spread-history proof |
| Prospective 15m/live-bar families | No matching populated Core snapshot families found; reader/runtime code existence is not data |
| Generic strategies/results / TradePlans | Zero / zero / zero; one existing V1 production-policy approval |

The first 2,000 historical rows in instrument/timeframe/start/end index order
are a **non-representative sample**: 1,306 Upstox daily UNKNOWN-basis rows,
554 unknown-existing-source daily RAW rows and 140 unknown-existing-source
daily UNKNOWN rows. Their raw date range is August 2023 through August 2026;
receipt timestamps span August 24 through September 1, 2026. Raw stored dates
are not certified session-end semantics.

This does not make all old data unusable today: it prevents using later receipt
as if it proved earlier decision-time knowledge. Exact source publication/
canonical knownness proof must independently support any historical admission.
A sampled membership begins and is known in August 2026. A sampled 2017 delisting
has `historical_known_at=null` and a September 2026 document observation.
Neither sample licenses historical backdating. No selected pair, decision cutoff
or comparison horizon was supplied, so no pair-specific source certification was
performed.

## 3. Complete scenario input readiness matrix

The JSON matrix contains 43 explicit rows, all mandatory contract components,
canonical source/schema, timestamp and adjustment semantics, PIT safety,
historical replay, determinism, calibration, authority, readiness, blocker and
prerequisite. `READY` below applies only to the accepted structural contract,
not a producer. `DERIVABLE` means an existing input/transform can be reused
**if exact required evidence is admitted**; it never means a ready endpoint.

Method-dependent rows are audited candidates, not newly imposed universal Gate-1
requirements. For example, this study does not require a bid/ask model for every
possible future methodology, select an OHLCV lookback or authorize optional cash.
Any eventual method must specify its own input closure.

| Component | Requirement | Readiness | Canonical schema/source | Current blocker |
| --- | --- | --- | --- | --- |
| `CONTRACT` | Required | `READY` | [Scenario / Parcel / Endpoint / Assessment](../../docs/architecture/GATE1_ROTATION_ECONOMIC_SCENARIO_CONTRACT_V1.json) | NONE |
| `IDENTITY` | Required | `DERIVABLE` | [HistoricalSecurityIdentity / Instrument.id](../../app/historical/security_master.py) | Pair/date-specific identity admission not supplied |
| `OHLCV` | Method-dependent / optional | `HISTORICAL_COVERAGE_INSUFFICIENT` | [CanonicalOHLCVBar / historical_bars](../../app/market_data/historical.py) | Count is not conflict-free same-window historically-known coverage |
| `ADJUSTMENT` | Method-dependent / optional | `SOURCE_NOT_READY` | [ProviderPriceBasisAssessment / TechnicalActionReceipt](../../app/market_data/technical_price_adjustment_integrity.py) | No universal total-return or complex-action normalization; unknown bases rejected |
| `CORPORATE_ACTIONS` | Method-dependent / optional | `HISTORICAL_COVERAGE_INSUFFICIENT` | [NseCorporateActionCoverageAssessment / HistoricalCorporateAction](../../app/historical/nse_corporate_action_coverage.py) | Receipt existence not complete comparable action coverage for a chosen pair/window |
| `LIFECYCLE` | Method-dependent / optional | `HISTORICAL_COVERAGE_INSUFFICIENT` | [BsePrimaryLifecycleEvidence / BseCompulsoryDelistedPdfRow](../../app/historical/bse_lifecycle.py) | Observed archive metadata cannot fabricate availability at the 2017 event |
| `UNIVERSE` | Method-dependent / optional | `HISTORICAL_COVERAGE_INSUFFICIENT` | [UniverseMembership in CoreApiSnapshot](../../app/historical/security_master.py) | Sample membership begins/known in August 2026; not a historical NIFTY500 panel proof |
| `CALENDAR` | Required | `DERIVABLE` | [CanonicalMarketSessionCalendar](../../app/historical/canonical_market_session_event_time.py) | Source coverage/visibility must be certified for chosen research interval; weekday-only V1 cannot substitute |
| `BENCHMARK` | Method-dependent / optional | `HISTORICAL_COVERAGE_INSUFFICIENT` | [CanonicalOfficialIndexOhlcObservation](../../app/market_data/official_nse_index_ohlc.py) | Owner explicitly current-descriptive, no historical availability claim or traded index volume |
| `SECTOR_INDEX` | Method-dependent / optional | `HISTORICAL_COVERAGE_INSUFFICIENT` | [CanonicalIndexCloseObservation](../../app/market_data/index_close_series.py) | Close-only cannot become OHLC; latest sector membership cannot backfill earlier sector exposures |
| `VOLUME_ADV` | Method-dependent / optional | `DERIVABLE` | [PriceBarSeries / CanonicalOHLCVBar](../../app/analysis/series.py) | Require aligned complete comparable bars and approved lookback; not a fill or impact estimate |
| `VOLATILITY` | Method-dependent / optional | `DERIVABLE` | [IndicatorResult / technical-v1](../../app/analysis/technical.py) | Descriptive statistic not drift, terminal price or approved volatility projection |
| `INTRADAY` | Method-dependent / optional | `SOURCE_NOT_READY` | [CanonicalFifteenMinuteTechnicalRead](../../app/market_data/canonical_fifteen_minute_technical_reader.py) | Implemented bounded strict reader is not a populated history or tick archive |
| `INCUMBENT_STATE` | Required | `DERIVABLE` | [PortfolioSnapshot / PortfolioHolding / PortfolioTransaction](../../app/portfolio/engine.py) | Replay possible only with complete prior ledger and known-at evidence; one snapshot not broad history |
| `COST_BASIS` | Method-dependent / optional | `DERIVABLE` | [PortfolioHolding / weighted-average-cost-v1](../../app/portfolio/models.py) | Accounting acquisition/basis is not statutory lot selection or verified tax classification |
| `SELECTED_PARCEL` | Required | `POLICY_UNSET` | [RotationCandidate / RotationEvaluationContext and predecessor Parcel](../../app/rotation/models.py) | No currently admitted selection/funding proof; cannot default to whole holding |
| `CANDIDATE_ID` | Required | `DERIVABLE` | [MarketWideWatchRecord](../../app/intelligence/market_wide_watch.py) | Need exact selected candidate, pair and cutoff; Watch label is not economics |
| `SCORE` | Required | `DERIVABLE` | [ScoreEvidenceAttestation / canonical_decision_scorecards](../../app/gates/source_authority.py) | Availability of complete same-cutoff pair not established; score never converts to return |
| `DIAGNOSTICS` | Method-dependent / optional | `DERIVABLE` | [DiagnosticResult / canonical_diagnostic_results / FinancialFact](../../app/registry/canonical.py) | Counts not completeness/comparability at chosen date; version/PIT/conflict guards remain mandatory |
| `STRATEGY` | Method-dependent / optional | `DERIVABLE` | [RoutingResult / OpportunityArchetype](../../app/intelligence/opportunity_archetypes.py) | Archetype does not supply executable policy or homogeneous return cohort |
| `REGIME` | Method-dependent / optional | `DERIVABLE` | [MarketRegimeResult](../../app/analysis/market_regime.py) | No approved regime-conditioned forward economics or stationary-regime assumption |
| `CATALYST` | Method-dependent / optional | `DERIVABLE` | [MacroEarningsTransmission / EvidenceVersion](../../app/intelligence/company_sensitivity/service.py) | Directional context explicitly not EPS forecast; no monetary causal model |
| `RELATIVE_STRENGTH` | Method-dependent / optional | `DERIVABLE` | [RelativeStrengthResult](../../app/analysis/relative_strength.py) | Past excess is not future excess; exact date alignment required before any cohort use |
| `HORIZON` | Required | `POLICY_UNSET` | [Categorical candidate plus B09 applicability](../../docs/architecture/RULE_HORIZON_TIMEFRAME_APPLICABILITY_POLICY_V1_CANDIDATE.json) | No ROTATE_IN numeric horizon policy/calendar/endpoint selected at cutoff |
| `INCUMBENT_ENDPOINT` | Required | `AUTHORITY_NOT_REGISTERED` | [No authoritative paired Endpoint producer](../../app/rotation/models.py) | Must model keeping exact parcel with same family and horizon, not zero/flat/current-mark forecast |
| `CHALLENGER_ENDPOINT` | Required | `AUTHORITY_NOT_REGISTERED` | [Caller expected_incremental_benefit is not Endpoint](../../app/rotation/models.py) | Targets/score/user estimate cannot satisfy independently reproduced terminal value |
| `MODEL` | Required | `CALIBRATION_REQUIRED` | [OutcomeSample / CalibrationObservation (measurement only)](../../app/calibration/service.py) | No approved method, horizon, eligible cohort, sample rule or empirical adequacy proof |
| `SALE_FUNDING` | Required | `POLICY_UNSET` | [CashPosition plus predecessor Parcel](../../app/portfolio/models.py) | Reference C is not guaranteed sale proceeds; gross deployment cannot imply free fees |
| `SUPPLEMENTAL_CASH` | Method-dependent / optional | `BLOCKED` | [Parcel.cash_contribution_inr](../../docs/architecture/GATE1_ROTATION_ECONOMIC_SCENARIO_CONTRACT_V1.json) | No additional invested capital authorized; unknown cash cannot become zero |
| `QUANTITY` | Required | `POLICY_UNSET` | [Lifecycle/master lot fields and predecessor quantity policy](../../app/historical/bse_lifecycle.py) | Metadata not approved current paired allocation; no fractional-share/rounding policy inferred |
| `RESIDUAL` | Required | `POLICY_UNSET` | [Parcel conservation invariant](../../docs/architecture/GATE1_ROTATION_ECONOMIC_SCENARIO_CONTRACT_V1.json) | No assumption that residual earns benchmark return or finances costs without proof |
| `TRADEABILITY` | Required | `SOURCE_NOT_READY` | [TickSizeObservation / surveillance evidence](../../app/market_data/reference_data/nse_master.py) | Exact cutoff source completeness/price constraints still need applicable admission; not perfect fill |
| `COST_RATES` | Required | `SOURCE_NOT_READY` | [NseCashDeliveryFrictionModel / effective-dated V1](../../app/gates/production_policy.py) | Not verified complete historical tariff panel or current V2 rate authority; GST base caller-supplied |
| `BROKERAGE` | Required | `SOURCE_NOT_READY` | [modeled_switching_friction brokerage argument](../../app/gates/production_policy.py) | Account-specific canonical tariff/source not established |
| `TAX_LOTS` | Required | `SOURCE_NOT_READY` | [Transactions/accounting cost; no selected statutory-lot engine](../../app/portfolio/models.py) | Cannot infer jurisdiction, holding classification, statutory lots or loss offsets |
| `TAX_POLICY` | Required | `POLICY_UNSET` | [T1 mandatory, policy unset](../../docs/architecture/GATE1_ROTATION_ECONOMIC_SCENARIO_CONTRACT_V1.json) | No rates/FIFO/zero-tax rule or accounting-basis shortcut permitted |
| `BID_ASK` | Method-dependent / optional | `SOURCE_NOT_READY` | [CanonicalQuote](../../app/market_data/models.py) | No populated exact-depth/spread panel or fill/impact evidence |
| `SLIPPAGE` | Required | `AUTHORITY_NOT_REGISTERED` | [MicroAnalysis proxies; no Gate1 slippage producer](../../app/analysis/liquidity.py) | Volume/ATR alone not calibrated impact; mandatory legs/cost evidence absent |
| `FRICTION` | Required | `POLICY_UNSET` | [V1 friction arithmetic plus predecessor Cost](../../app/gates/production_policy.py) | Missing policy precision/funding/components cannot become neutral friction |
| `REPLAY` | Required | `DERIVABLE` | [HistoricalCapitalRotationReplayService](../../app/backtest/rotation.py) | Old caller economics or prior gate clearance cannot serve as independent scenario authority |
| `AUTHORITY` | Required | `AUTHORITY_NOT_REGISTERED` | [GateSourceAuthority.verify_domain](../../app/gates/source_authority.py) | Receipt/AI/user/analyst/self-hash never confers authority |
| `OUTCOMES` | Method-dependent / optional | `HISTORICAL_COVERAGE_INSUFFICIENT` | [ForwardPaperAggregate / paper outcomes / OOS windows](../../app/intelligence/forward_paper_intelligence.py) | 43 links exist; sampled link is a decision event, not proof of a matured paired-return cohort |
| `REFERENCE_PRICES` | Required | `SOURCE_NOT_READY` | [CanonicalQuote / CanonicalOHLCVBar via certified readers](../../app/market_data/models.py) | No decision pair/cutoff supplied or verified current same-cutoff price admission |

No unavailable monetary output is labelled READY. Horizon has the task-specific
classification **`POLICY_REQUIRED`**, corresponding to matrix `POLICY_UNSET`.

### Price, adjustment, identity and calendar conclusions

- [Provider-versioned bars](../../app/market_data/historical.py) preserve source
  versions and same-provider conflicts; as-of reads filter bar end and receipt.
  Consumers must explicitly request the cutoff. A no-as-of read is not replay proof.
- [Daily temporal semantics](../../app/market_data/daily_source_temporal_semantics.py)
  distinguish raw timestamp roles, source timing and observed-at fallback.
  Receipt time is not silently converted into historical publication/session close.
- [Adjustment integrity](../../app/market_data/technical_price_adjustment_integrity.py)
  supports exact verified split/bonus derivatives without changing raw inputs.
  Rights, cash-dividend/total-return policy, mergers and other complex actions
  are not thereby solved. Labels RAW/ADJUSTED/UNKNOWN do not establish a shared
  economic basis. Delisting exits/cash consideration cannot be imputed.
- [Historical security master](../../app/historical/security_master.py) uses the
  newer Core snapshot families. Empty legacy tables do not erase implemented
  membership/identity capability. Current members alone cannot form a
  survivor-neutral historical training denominator.
- [Canonical session calendar](../../app/historical/canonical_market_session_event_time.py)
  has effective holiday, special-day and phase sources with PIT visibility.
  The simpler V1 weekday-minus-holidays `ExchangeCalendar` is not equivalent
  proof of all historical/exceptional session timings. Neither defines the
  economic holding horizon.
- [Official index OHLC](../../app/market_data/official_nse_index_ohlc.py) is
  explicitly current-descriptive PRICE_RETURN_INDEX evidence, without a
  historical availability claim or traded volume. [Close-only history](../../app/market_data/index_close_series.py)
  cannot become OHLC, total return, delivery or liquidity.
- ATR/ranges/returns/ADV-like descriptive transforms are possible with admitted
  source windows; no drift, forward direction, gap-fill price, impact coefficient
  or square-root-time projection follows from their existence. Intraday gap
  ordering needs prospective closed-bar continuity, not daily OHLC path guesses.

## 4. Existing forward-looking structures: semantic rejection audit

| Candidate structure | What actually exists | Why it cannot supply Gate-1 endpoints |
| --- | --- | --- |
| [Measured-move targets and RR](../../app/analysis/valuation_trade.py) | Base-height target ladder and reward/risk geometry with configured input rules | Conditional instrument setup levels, not probability, date-pinned terminal wealth or calibrated expectation |
| [TradePlan](../../app/signals/models.py) and governed Pre-Breakout support | Entry/stop/target fields and target-support provenance | A valid plan does not prove a target will be reached; no mirrored incumbent continuation or common numeric horizon |
| [Rotation expected benefit](../../app/rotation/models.py) | Caller-supplied optional economic/friction scalars | Names are not independently reproduced methodology/provenance; no scalar alias into V2 |
| [CalibrationService](../../app/calibration/service.py) | Score buckets, observed win rate, mean/median R, regime/horizon filters | Measurement-only samples lack a complete canonical decision/outcome lineage contract; OBSERVED is not sample adequacy or calibrated prediction |
| [Performance reports](../../app/performance/engine.py) | Realized sample expectancy, PnL, average R, MFE/MAE and descriptive risk statistics | Post-outcome strategy statistics; absent current production report cohort; cannot use outcomes not matured before model fit/decision |
| [Forward-paper intelligence](../../app/intelligence/forward_paper_intelligence.py) | As-of projections of known studies/events with instrument/sector cohorts | Useful observational infrastructure, but zero stored studies/events; run receipts are not returns |
| [Walk-forward/OOS](../../app/backtest/oos_aggregation.py) | Frozen train/test structures and aggregated out-of-sample performance | Evaluation infrastructure, not an instrument-level forward model; stitched equity/R/costs are not cost-exclusive selected-parcel endpoints |
| [Batch-1 calibration readiness](../../app/intelligence/batch1_calibration_readiness.py) | Completed-session window observability checks | Prospective collection support, not estimated Gate-1 returns; its windows do not authorize a rotation horizon |
| [Long-Term research shadow](../../app/intelligence/long_term_thesis_research_shadow.py) and [Compounder observations](../../app/intelligence/compounder_prospective_shadow_validation.py) | Typed unavailable/readiness states and factual prospective accounting inputs | Not a fair value, EPS forecast, return model or universal financial-company methodology |
| [Macro-to-company transmission](../../app/intelligence/company_sensitivity/service.py) | Bounded directional sensitivity/context | Explicitly not an EPS forecast; no currency outcome or causal probability |
| [Relative strength](../../app/analysis/relative_strength.py) / [regime](../../app/analysis/market_regime.py) | Backward-looking price/excess-return classification | No approved persistence of past excess/drift or regime-conditioned future distribution |
| [Fast Rotation assurance](../../app/intelligence/fast_rotation_comparison_assurance.py) | PIT and evidence-quality assurance for an existing comparison | Does not calculate a scenario, supply missing economics or become a second discovery Brain |

For these structures, deterministic arithmetic is not economic authority.
They may have existed at a decision only if their exact versions and all inputs
were then available. Retrospective reports can be training measurements only
after their outcomes mature and the fitted-model version is frozen before the
decision being evaluated. No score-to-return multiplier, analyst target,
AI inference, uncalibrated probability or rebadged historical expectancy is
accepted.

## 5. Method-family feasibility

Each of the ten machine rows explicitly records required/available inputs,
PIT integrity, calibration, sample-size status, survivorship, corporate actions,
regime and strategy dependence, deterministic reproducibility, INR compatibility
and symmetric applicability. **None is selected or calibrated for Gate-1.**
Minimum sample sizes remain unset; no count threshold is invented.

| Model family | Existing support and gap | Calibration requirement | Symmetric incumbent/challenger issue |
| --- | --- | --- | --- |
| `EMPIRICAL_FORWARD_RETURNS` | Bars and guards exist; outcome panel, horizon and sampling rule absent | Pre-register window, estimator, tail/missing/delist handling, minimum sample and held-out adequacy | Could be symmetric only with matched known-at paired cohorts |
| `STRATEGY_CONDITIONED_OUTCOMES` | Pre-Breakout/setup and forward-paper schemas exist; zero studies/events/outcomes | Cohort selection, censoring, costs exclusion, model fitting and out-of-sample adequacy | Incumbent may not have a fresh setup; cannot compare historical entrant expectancy to flat incumbent |
| `REGIME_CONDITIONED_RETURNS` | Backward-looking regime engine exists, not regime-return calibration | Predefine regimes/changes and per-regime sample sufficiency without new gate thresholds | Must apply identical regime/fit vintage to both instruments |
| `BENCHMARK_RELATIVE` | Trailing relative strength and index records only | Govern future excess model and compatible index basis; trailing excess not drift | Symmetric formula possible in principle, presently no paired model |
| `TARGET_STOP_PATHWAYS` | Measured-move targets/TradePlan/RR exist, no probabilities or common endpoint timing | Target/stop/time censoring and path ambiguity, fills/gaps, outcome frequencies | Target for challenger alone is asymmetric; held incumbent needs same admissible setup methodology |
| `EXPECTED_R` | Expectancy and R reporting utilities; no production outcome cohort | Conditioned expectation, risk base, uncertainty and capital/INR conversion | R uses stop-defined risk, not same selected C or common horizon |
| `SCORE_TO_RETURN` | 3 scorecards; CalibrationService buckets are measurement only | Mapping, sample/cross-validation and all versions would require separate governance | Would not replace independent >=1 score hurdle; no arbitrary multiplier |
| `VOLATILITY_NORMALIZED` | ATR deterministic as descriptor; no drift or stochastic/path model | No square-root-time, distribution, drift, quantile or multiplier selected | Same dynamics required both legs; volatility is not expected direction |
| `COMPARABLE_SETUPS` | Diagnostics/router schemas exist; no approved distance/selection panel | Matching, leakage/purge, sample thresholds and reproducible selection policy | Must match both instruments comparably, not cherry-pick challenger winners |
| `SCENARIO_TREE` | Macro transmission is bounded direction, not earnings or return forecast | Govern transitions/weights/endpoints, method and calibration before monetary use | No probability-free authoritative choice among invented branches |

For every family, a defensible protocol must define the estimand, fit cutoff,
horizon, eligibility, rejected/missing cases, survivorship denominator,
corporate actions, outcome maturation, train/test separation and empirical
adequacy before claiming readiness. Purge/embargo choices, tail treatment,
estimator/probability, uncertainty and minimum samples are not chosen here.
A reproducible backtest with post-decision information is still invalid evidence
for an ex-ante Gate-1 result.

## 6. Paired continuation, challenger deployment and funding

**Incumbent:** use the selected existing quantity, not an empty baseline, cash,
index, zero return or its accounting profit. Current marked value and diagnostics
describe state; they do not establish the value of keeping that parcel through
an approved common horizon. Historical reconstruction can reuse known-at ledger
transactions/actions and immutable snapshots, but the one stored snapshot is not
a longitudinal complete ledger proof. No later holdings can substitute.

**Challenger:** requires an exact admissible price at the same cutoff, permitted
quantity/quanta, market/tradeability constraints, residual and friction financing.
Neither last traded price nor historical close guarantees investable quantity,
sale proceeds or perfect fills. Candidate and incumbent must use the same
methodology family, vintage, economic basis and horizon. Different factual
features are legitimate; a target-based challenger versus flat incumbent is not.

The predecessor's reference-capital and once-only-friction equations are retained:

```text
C = selected_incumbent_quantity * admitted_incumbent_reference_price
candidate_purchase_turnover + residual = C
G = candidate_terminal_gross_value_inr - incumbent_terminal_gross_value_inr
N = G - modeled_switching_friction_inr
score hurdle: raw_decision_score - comparison_score >= 1.00 points
economic hurdle: N > 0.00 INR
```

No formula in this report calculates live endpoints. Exclusive-sale financing,
integer allocation, per-instrument lot constraints and fee/residual rules remain
policy gaps. Decimal portfolio quantities support ledger arithmetic, not a
fractional-share authorization. Price tick rounding is not share-count rounding.
Historical master lot-size fields are source candidates, not current transaction
allocation authority. Positive supplemental cash remains unsupported by the
predecessor. Cash is UNKNOWN; it cannot become zero or available buying power.
No whole-position/NAV substitution or prorated cost shortcut is allowed.

## 7. Costs, tax and slippage

The [V1 friction model](../../app/gates/production_policy.py) has versioned,
effective-dated statutory/exchange/STT/stamp/GST rate fields and immutable
approval. This is an implemented capability, **not** a verified historical
tariff panel for arbitrary dates/accounts or all required V2 component values.
Brokerage, slippage, capital-gains tax and GST service base are explicit required
inputs; absence returns no modeled friction. The audit neither changes existing
rates nor publishes new current rates. Extra execution charges require approved
disjoint treatment, never an arbitrary extra penalty.

T1 is transaction-specific and mandatory. Five ledger transactions and
weighted-average accounting do not supply verified statutory acquisition-lot
selection, acquisition dates for each tax lot, entity/jurisdiction/classification
facts or historically pinned tax law. No FIFO, loss offset, tax exemption or
default rate is inferred; missing policy/input fails closed.

[CanonicalQuote](../../app/market_data/models.py) supports optional bid/ask and
quantities, but the stored sample is missing depth. Live LTP is not historical
spread/impact evidence. [Liquidity analysis](../../app/analysis/liquidity.py)
explicitly marks actual order-book quantity unobserved; stop clusters/absorption
are proxies. Volume/ADV and ATR may be future model inputs only after policy and
calibration. No current credible independently reproducible two-leg slippage
producer was found. Model choice must determine needed microstructure inputs;
this audit imposes no new universal quote requirement. Slippage remains
mandatory, NOT_READY, and never defaults to zero. Costs stay outside endpoints,
deducted once; neither friction nor the tax component is omitted to obtain a
positive comparison.

## 8. Ownership and exact prerequisites

Recommend the future **pure paired producer under existing `app/rotation`**.
It consumes canonical immutable evidence and a separately approved model,
emits the accepted structured scenario contract, and does not call gates,
brokers, repositories for writes or mutate portfolio state. This is a namespace
recommendation, not a new module in this slice.

Reuse `app/calibration` and `app/backtest` for measurement, frozen cohorts and
validation; do not promote their descriptive statistics directly into Gate-1.
The independently configured [GateSourceAuthority](../../app/gates/source_authority.py)
verifies/reproduces the future registered producer's exact evidence. The gate
retains adjudication, and all other gates remain independent. Final challenger
clearance cannot feed back as upstream scenario authority. No second Brain,
replacement score or AI decision authority is introduced.

| Prerequisite | Type | Exact required proof |
| --- | --- | --- |
| `P01` | `FOUNDATIONAL_POLICY_AND_METHODOLOGY` | Pre-register same-family paired-cohort research requirements, common horizon authority, estimand, eligibility, precision and method-comparison protocol; no model chosen by convenience. |
| `P02` | `FOUNDATIONAL_HISTORICAL_DATA` | Certify a finite PIT-known, survivor-aware, adjustment-comparable source/outcome cohort with publication/receipt lineage and held-out evaluation; no backdating receipts. |
| `P03` | `BOUNDED_FUNDING_POLICY` | Approve and source exact parcel selection, quantity quanta, sale/fee funding and residual conservation on both legs; keep cash UNKNOWN. |
| `P04` | `SOURCE_AND_CALIBRATION` | Establish point-in-time execution constraints and liquidity/spread/impact observations required by the separately approved slippage method, plus governed two-leg calibration. |
| `P05` | `POLICY_AND_SOURCE` | Verify versioned fee schedules, taxable bases, statutory lot selection and tax context; preserve mandatory components and once-only costs. |
| `P06` | `DOWNSTREAM_AUTHORITY` | Only after methodology and data validation, add a versioned pure producer under existing rotation and independently configured GateSourceAuthority; adapter/activation separate. |

These are dependencies, not six authorized follow-on tasks. P01/P02 are
foundational and may remain infeasible after research; no positive result or
closure schedule is promised. Bounded P03-P06 implementation would not repair
missing methodological evidence by itself.

## 9. Validation and closure boundary

Governance/conformance tests must verify the accepted predecessor, frozen file
pins, exact complete matrix/vocabularies, no false READY claims, no fake
economic authority/defaults, fixed PIT/parcel/horizon/method-family/INR semantics,
independent hurdles and exactly one continuation. They do not open production
SQLite, collect live data or implement a return model. The audit capture is
immutable evidence of this read-only inspection, not a fixture that asserts
the live database can never change.

Focused and relevant regression tests, local documentation-link/whitespace
checks and `git diff --check` are required before the local commit. No
application/shared behavior is changed, so a full backend suite is not required
under this slice's explicit rule. No production performance or authority claim
follows from green governance tests.

Completed validation:

- Focused conformance: **199 passed, 0 failed**, no skips or warnings.
- Relevant regression: **553 passed, 0 failed**, no skips, **2 existing
  dependency deprecation warnings** (Starlette/httpx and AnyIO BlockingPortal).
  This covers the predecessor contract, V2.4 governance, Gate-1 proposal/source
  readiness, gate authority/V1 behavior, historical bars/identity/adjustment,
  horizon governance, portfolio reconstruction/rotation and paper/calibration
  support. It is not a full-backend result.
- Documentation checks: **350 local links, 5 tables**, no broken targets,
  malformed columns, unclosed fences or trailing whitespace.
- Source preservation: **77 inspected file fingerprints** verified;
  predecessor contract and its frozen-file checks pass unchanged.
- `git diff --check`: passed. Only this report, its JSON artifact, its offline
  governance tests and the README architecture-index link are in scope.
- Full backend: **not run**, as explicitly permitted for this audit-only slice;
  no runtime/shared application behavior was changed.

Operational blockers closed: **zero**. Audit questions closed: canonical source
inventory, lack of an existing authoritative paired producer, horizon-policy
gap, and quantified stored-outcome/PIT limitations. All predecessor model,
funding, cost/tax/slippage, authority/adapter and V2 activation dependencies remain.

Slice closure means **the feasibility audit is ACCEPTED/CLOSED with decision C**,
not that Gate-1 scenarios are operational. V1 is active; V2 remains NOT_ACTIVE.
No push and no downstream slice are authorized by this checkpoint.

## 10. Exactly one next frozen continuation

**`GATE1_ROTATION_PAIRED_SCENARIO_RESEARCH_PROTOCOL_V1`**.

Specify a model-neutral, PIT-safe paired research-cohort and outcome-admission
protocol: horizon authority requirements, explicit source/corporate-action/
survivorship knownness, matching and outcome-maturation requirements, and
calibration adequacy questions. Do not invent a model, numeric horizon, sample
threshold or return merely to fill the protocol. This recommendation is frozen
as the sole continuation and **has not been started**.
