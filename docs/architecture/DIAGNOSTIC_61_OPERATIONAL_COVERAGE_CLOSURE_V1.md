# Canonical 61 Diagnostic Operational Coverage Closure V1

Status: `AUDIT_CLOSED / OPERATIONAL_COVERAGE_PARTIAL / NO_ACTIVATION`.

Baseline: `c7a888e79afe2ad73cabd05c56ad37216200dec2`. Authoritative repository:
`D:\nse-stock-manager`. Explicit audit visibility cutoff: `2026-09-10T00:00:00+00:00`.
This is not a September 10 live-market or freshness claim.

## Authority and interpretation

The sole Rule authority is [the canonical registry](../../app/registry/canonical.py).
The [machine artifact](DIAGNOSTIC_61_OPERATIONAL_COVERAGE_V1.json) projects its
IDs, names, purposes, categories and missing-data behavior. It is not a second
registry, configuration input, evaluator, weighted readiness score or Brain.
[The read-only generator](../../scripts/audit_diagnostic_61_operational_coverage.py)
binds canonical metadata to measured source coverage and a supplied cutoff.
Its fingerprint is SHA-256 over sorted, compact, ASCII JSON excluding only the
top-level fingerprint field. Every fingerprint input is serialized.
Final artifact fingerprint:
`sha256:586123ce4e59f57dd27f4cde7754115af2f452f01325b828d2a789ef542bf5ff`.

Definitions of reported states:

- `OPERATIONAL_CURRENT_DESCRIPTIVE`: existing evaluator and canonical input
  path can evaluate an eligible stored snapshot in the stated security subset.
  It does **not** mean every security produces an eligible result, that an entry
  geometry exists, that every horizon is active, or that evidence is fresh now.
- `PARTIAL`: some required components exist but full canonical coverage is
  not certified. `NOT_READY`: the necessary named input/join is unavailable.
- Input coverage is a prerequisite count, not a count of successful full
  diagnostic runs. No whole-universe 61-rule materialization was performed.
- `null` means unmeasured/unproven; `0` means measured absence. Missing data is
  never reclassified as `NOT_APPLICABLE`. No fake percentage is assigned.

## Frozen horizon policy correction

The human-accepted [183-row horizon definition](RULE_HORIZON_TIMEFRAME_APPLICABILITY_POLICY_V1_CANDIDATE.json)
is `READY / FROZEN`. Its unchanged content fingerprint is
`sha256:bc1f7548b372738d69b72c2e54afdc34c9f10929aee9a10d834ce99cb8d43d8a`.
The stored legacy `CANDIDATE_NOT_ACTIVE` label is retained, not taken as a
revocation of the accepted definition. Runtime consumption remains `PARTIAL`.
Existing explicit per-cell `POLICY_UNSET`/`DATA_NOT_READY` values are preserved;
they do not mean the whole policy definition is missing. No durations, roles,
weights, indicators or timeframes were added.

The three horizons remain `SHORT_TERM / POSITIONAL / LONG_TERM`; `MID_TERM`
is display wording. Setup type is not horizon. Fundamental/governance red-flag
checks remain relevant to short-term setups, deeper company evidence to
positional interpretation, and quality/governance/valuation to long-term
interpretation. This audit activates no setup, trade or horizon consumer.

## Measured security and technical coverage

The universe snapshot contains 2,553 securities. Certified daily/weekly input
scope is 2,538. The single daily/weekly audit selects each instrument's latest
contiguous six-week suffix; 598 suffixes have fewer than six weeks. The latest
persisted weekly end is August 30, 2026, not a live session.

| Input | Ready securities / 2,538 | Meaning |
| --- | ---: | --- |
| Rule 4 daily + weekly trend | 1,940 | 6 genuine daily and 6 weekly observations; 499 partial, 99 not ready |
| Rule 5 weekly stage | 2,007 | 5 weekly observations; 531 not ready |
| Rule 10 daily structure | 2,439 | 6 daily observations; 99 not ready |
| Rule 14 daily + weekly subset | 2,007 | 531 partial; full intraday/MTF coverage remains partial |
| Other listed price/volume prerequisites | 2,538 | Exact per-rule lookbacks and blockers are in the machine artifact |
| Exact governed sector mapping | 601 | Mapping alone is not OHLC input readiness |
| Mapped sector OHLC history | 354 | 247 other mapped securities still lack the full OHLC contract |
| Aligned Rule 2/3 inputs after repair | 354 | Before repair: 207; +147 from existing local history only |
| Rule 6 authoritative peer cohorts | 0 | Stock/benchmark classification exists; no invented peer ranking |
| Canonical prospective 15m production bars | 0 | Implementation/reader exists, live data proof does not |

Rule 1 uses canonical `NIFTY_50` PRI OHLC: 247 sessions through
`2026-09-04T10:00:00+00:00`; latest retrieval known-at
`2026-09-06T17:15:31.353328+00:00`. Its existing evaluator uses return, trend
and ATR; it does not consume a new breadth/flow requirement. Sector endpoints
can extend through September 8; comparative inputs are selected through the
benchmark's exact September 4 endpoint. No claim of September 8 benchmark
coverage is made. All index IDs, counts, endpoints and retrieval times are
retained in the machine artifact.

Unmapped technical scope is separately classified: 1,827 taxonomy-missing,
84 without an exact official index, 26 mapping-policy unresolved. The 247
mapped-but-OHLC-blocked securities are not hidden in these categories.

Rule 6 keeps the existing three-session stock-versus-benchmark classification;
sector and peer outputs are descriptive, not newly mandatory score gates.
Basic Industry remains a future authoritative peer candidate, not a cohort.
Rule 35 remains `NAMED_VWAP_SEMANTICS_UNAVAILABLE`; the generic legacy fallback
is not a certified named VWAP/value-area stream. Rule 57 remains
`EVENT_EVIDENCE_NOT_READY`: News storage alone does not provide its canonical
materiality, known-at and completed-session relation.

## Financial, ownership, research and temporal coverage

Actual canonical production state is **4,067 FinancialFacts / 362 corporate
filings / 31 companies**, not the old five-holding count. All 31 select
consolidated scope through the current adapter. Standalone facts are retained
as separate source facts, not mixed into consolidated metrics.

| Stream | Rows / coverage | Exact limitation |
| --- | --- | --- |
| Annual / full-year / units | 787; periods 2022–2026 | At most five annual dates; no six-point five-year CAGR series |
| Point-in-time balance fields | 480, basis `UNKNOWN` | Legacy annual/quarter adapter does not join these balance observations |
| Quarter-only | 2,214 | 2,193 units; 7 each crores/lakhs/millions; no silent unit conversion |
| Quarterly tagged year-to-date | 586 | Must not be interpreted as quarter-only or interpolated |
| Frozen factual vintage selector | 3,730 selected groups; 120 conflicted groups | 3,850 semantic groups, not 4,067 independent periods; conflicts are not overwritten |
| Direct EBITDA, EBIT, CAPEX, total debt, shares outstanding | 0 each | Components/PBT/other income do not authorize synthetic reconstruction |
| Annual CFO/PPE purchases/intangible purchases | 17 consolidated + 19 standalone each; 4 companies each scope | Purchases are not automatically a governed CAPEX total |
| Ownership normalized observations | 30; five companies | One period per company/category, not a comparable two-period shift |
| External events / News evidence | 15 / 28 | Operational infrastructure exists; not equivalent to typed Rule 15/23/28/30/57 inputs |
| Generic MarketObservation store | 0 | Generic research/crowd/order-book stream not populated |

Revenue/PAT/EPS and certain other annual metrics cover 25 consolidated and 24
standalone companies; quarterly revenue/PAT/EPS cover 29 consolidated and 26
standalone companies. Per-metric scope/basis/scale and period endpoints, all
31 per-company period sets, selector fingerprints and current adapter warnings
are retained in the machine artifact. Different denominators are intentional.

A read-only probe of the existing financial wrappers (Rules
16/17/18/19/20/21/22/24/25/26/27 only) finds Rules 24 and 25 eligible for CRISIL,
GLAND, DEEPINDS, APARINDS and GENUSPOWER. This is **5/31 source companies**, not
a new fundamental-completeness certificate. Other probed rules remain
insufficient. No results were persisted or scores/gates invoked.

Important contract gaps remain: the legacy adapter groups by period type/end
and loses basis/scale/period-start comparability; quarter-only and YTD facts
can create false conflicts. It does not use the separately governed full
vintage-selection contract. Five calendar dates do not meet Rule 16's six-point
requirement. Point-in-time balance joins, industrial-versus-financial-company
applicability, forward-EPS/growth/shares and ratio denominators need explicit
compatible contracts. Existing EV computation also has legacy missing
debt/cash defaults; no production EV readiness is claimed. These are recorded
for the single next bounded financial contract slice, not silently repaired
with new financial semantics here. The frozen selector's non-active future
consumer status is not changed by this read-only diagnostic audit.

Ownership retains category relationships: DII/MF are not added blindly, FII
is absent from the current normalized category contract, promoter percentages
exist for four companies, pledge percentage for one. Category dates across
different companies (June 30 / August 13 local) are not two comparable periods
for one company. Quarterly holdings, daily aggregate institutional flows and
stock-specific block/bulk transactions remain distinct. No canonical rule
requires a new daily aggregate-flow stream: `NOT_APPLICABLE` for that proposed
dependency, not for missing ownership inputs.

Order book/inflow and comparable guidance have no populated canonical
diagnostic stream. Source, instrument, reporting period, units, received-at,
revision/cancellation and exact amendment identity must precede any business
interpretation. Financial totals or stale announcements cannot stand in.

Governance uses the existing primary-source adverse-claim logic; disclosures,
five reliability/integrity artifacts and external evidence are reusable but
not a complete typed Rule 23 claim join. Missing claims are not clearance.
Growth/technical evidence cannot override a verified legal/governance blocker.
No new legal, promoter, dilution or audit scoring rule was introduced.

Every source has its own temporal axis. Financial/ownership publication and
receipt evidence support selection only at/after `max(published_at,received_at)`;
2022 financial periods received in 2026 do not prove availability in 2022.
Market source historical publication/adjustment integrity and historical
taxonomy are not certified by a modern download timestamp. Prospective 15m
contracts are implemented but empty. No arbitrary freshness-day cutoff or
expiry was invented. The adapter's `FRESH` label merely tests visibility, not
an approved maximum age. Financial freshness remains `FRESHNESS_POLICY_UNSET`.

## Internal repairs and regression evidence

1. Rule 59 now requires all four upstream diagnostics (47/12/13/14) to be
   eligible. Missing/invalid MTF or crowd evidence previously became a valid
   `CONFLICTING` result because a missing-result object was truthy. It now
   remains `INSUFFICIENT_DATA` through 59 → 60 → 61. Genuine disagreement with
   all eligible inputs is unchanged.
2. The benchmark/sector adapter validates every supplied observation first,
   then selects the existing sector prefix through the benchmark endpoint.
   It never backfills, moves the benchmark backwards, ignores invalid future
   lineage or overwrites source history. This closes the 147-security alignment
   gap. A missing session still fails closed; duplicate/future lineage is still
   rejected. No new return or sector policy was added.

Daily/weekly ordering was inspected and is already correct; no Rule 4/14
timeframe rewrite was made. Only the two bounded runtime files above change.

## Radar, Decision Score and Six Gates

The deterministic fixture in
[coverage tests](../../tests/unit/test_diagnostic_61_operational_coverage.py)
uses the accepted canonical Discovery Lead and existing Radar bridge: exactly
61 IDs, 25 `EVALUATED`, 32 `INSUFFICIENT_DATA`, two `PARTIAL`, two
`SOURCE_NOT_READY`. Its receipt fingerprint is
`599ef138b1cd87c01650b583ba18d1fa02cccc17d789a2bb1dc2d607c1200b4d`.
This is an isolated proof, not production diagnostic materialization.

Decision Score and Six Gates are `DOWNSTREAM_EXISTING_AUTHORITY /
NOT_INVOKED_IN_THIS_SLICE`, not globally `NOT_APPLICABLE`. Three stored canonical
scorecards have `COMPLETE` status at their historical as-of; no current score
is recomputed. The existing mandatory score inputs are Rules
24/1/2/7/6/10/11/12/29/45, with exact component mapping in each coverage row.
Missing required inputs prevent a complete score; weights are unchanged and
not renormalized. Rule 31 is an existing ordinal synthesis, not a new
calibrated probability; its existing execution order precedes Rule 46, so the
coverage artifact does not claim the latter's risk contribution is consumed.

One Six Gates production policy approval exists, but zero canonical gate
evaluation/decision rows exist. Existing gate input requirements are:

| Gate | Existing required evidence | Current audit boundary/blocker |
| --- | --- | --- |
| 1 rotation comparison | comparable scores, friction/advantage and economic inputs where governed | Not invoked; no new comparison or assumed return |
| 2 velocity | holding entry date, session calendar, ATR expansion | Not invoked; current compatible holding context not proven |
| 3 surveillance | fresh authoritative ASM/GSM/circuit fields | No new clearance; generic observation store empty |
| 4 plan | approved entry/stop/T1/tranche context | Zero trade plans; diagnostic geometry is not a plan |
| 5 heat | portfolio equity, existing/candidate risk and allocations | Cash UNKNOWN; no inferred capital/allocations |
| 6 earnings blackout | verified schedule and exchange-session calendar | Current schedule not proven; prior results are not a future schedule |

None has a new live PASS claim. Existing contextual exemptions remain governed
inside the gate engine and are not applied by this audit. No broker, order,
portfolio, allocation, automatic action, provider, persistence, API/UI or
runtime activation was added. Generic rule names/legacy verdict vocabulary
remain descriptive; the audit and Radar boundary remain non-executable.

## Final readiness matrix

| Item | State | Evidence / remaining limitation |
| --- | --- | --- |
| A canonical registry | READY | 61 exact IDs, no 62, one registry |
| B evaluator coverage | READY | 61 wrappers |
| C input contracts | PARTIAL | 46 ready; 15 partial |
| D source authority | PARTIAL | 31 ready; 30 partial |
| E identity | PARTIAL | 38 ready; 23 partial at diagnostic-join boundary |
| F applicability | PARTIAL | 51 ready; 10 partial; no missing-as-inapplicable |
| G horizon definition | READY | frozen 183 cells; runtime partial |
| H timeframe definition | READY | unchanged profiles; absent runtime frames explicit |
| I current descriptive | PARTIAL | 29 operational in stated subsets; 18 partial; 14 not ready |
| J prospective PIT | NOT_READY | zero fully operational rules; 21 partially supported, 40 not ready |
| K strict historical PIT | NOT_READY | zero fully operational rules; 11 partially supported, 50 not ready |
| L technical | PARTIAL | certified 1D/1W scope 2,538, rule-dependent depth; no live claim |
| M fundamental | PARTIAL | 4,067 facts / 31 companies; comparability and missing metrics |
| N sector | PARTIAL | 354 aligned contexts / 2,538 |
| O ownership | NOT_READY | 30 observations / five companies; missing comparative join/history |
| P governance | NOT_READY | evidence exists; canonical research-claim completeness not proven |
| Q valuation | PARTIAL | partial EPS/price; denominator/basis/forward inputs missing |
| R event/catalyst | NOT_READY | existing external infrastructure != canonical event/session join |
| S Rule 1 | READY | stored benchmark snapshot only, through September 4 |
| T Rule 2 | PARTIAL | 354 subset operational; other securities blocked |
| U Rule 3 | PARTIAL | same exact context denominator |
| V Rule 6 | PARTIAL | stock/benchmark works; sector partial; peers zero |
| W Rule 14 | PARTIAL | 2,007 daily/weekly inputs; no invented intraday frames |
| X Rule 35 | NOT_READY | named VWAP contract absent |
| Y Rule 57 | NOT_READY | canonical event/session semantics absent |
| Z annual facts | PARTIAL | 787 annual facts; maximum five calendar dates |
| AA quarterly facts | PARTIAL | quarter-only/YTD and unit comparability gaps |
| AB ownership streams | READY | holdings/flows/transactions distinguished |
| AC sector coverage | PARTIAL | 601 mapped; 354 history-ready; 247 OHLC-blocked |
| AD peers | NOT_READY | zero authoritative cohorts; no proxies |
| AE live 15m | NOT_READY | implemented contracts; zero production bars |
| AF MTF orchestration | NOT_READY | NOT_ACTIVE; no 30m/1H/4H construction |
| AG Radar proof | READY | all 61 states and explicit blockers |
| AH Decision Score | PARTIAL | existing downstream authority, not invoked |
| AI Six Gates | PARTIAL | existing approved policy; no invocation/authorization |
| AJ machine artifact | READY | deterministic 61 records, 16 independent reported axes |
| AK bounded repairs | READY | upstream eligibility propagation; exact sector endpoint selection |
| AL external blockers | PARTIAL | insufficient history/metrics, taxonomy/peers, events, live/PIT source proof |
| AM full 61 production readiness | PARTIAL | coverage audit complete; not all 61 production operational |
| AN next bounded slice | PARTIAL | canonical financial diagnostic comparability contract |

The machine artifact's 61-rule blocker counts are non-exclusive: one rule may
have multiple blockers. Current-descriptive operation can coexist with
historical-PIT and horizon-runtime blockers. Policy definition and consumer
activation are not collapsed into the same axis.

## Validation and immutable production boundary

- Final focused coverage/changed-input/universe regression tests: 33 passed.
- Final affected Brain/fundamental/technical/PIT/horizon regression: 136 passed,
  0 failed, 2 dependency deprecation warnings.
- SQLite `quick_check=ok`, `integrity_check=ok`, FK violations = 0; protected
  table counts/content and snapshot-family counts remained unchanged.
- Final complete backend suite: **3,276 passed / 0 failed / 6 skipped /
  2 warnings**, 313.88 seconds. Warnings are the installed Starlette/httpx and
  AnyIO alias deprecations, not runtime test failures.
- Markdown validation: 239 local links passed; all 61 canonical names and all
  15 table columns verified; whitespace and `git diff --check` passed. Changed
  files passed the bounded secret/private-key/credential-URL pattern scan.
- The first complete regression exposed the old rich-fixture count assertion
  (59 versus correctly propagated 56; missing IDs 4/14/59/60/61). Its exact
  missing-ID/result assertions were strengthened; runtime semantics were not
  weakened. The subsequent run passed 3,275 tests. Final review then added one
  regression preventing price-only counts from being reported as full valuation
  coverage; the final complete suite includes that additional test.
- The authoritative final audit reused one captured daily/weekly security
  audit; the earlier discovery pass exposed the sector alignment defect.
  Final sector/financial remeasurement was read-only, with no weekly re-scan.
- Counts/fingerprints protect FinancialFacts, canonical strategy definition,
  portfolio snapshot, all snapshot families, paper trades and trade plans.
  Portfolio snapshots = 1; cash = UNKNOWN; generic strategy/results = 0;
  canonical results = 2,074; paper trades/trade plans = 0.
- No source acquisition, raw provider download, credential inspection, Dhan
  canary, per-tick capture or database write occurred. No secrets are part of
  the report. Runtime source changes do not alter investment thresholds.

## Exactly one next continuation

`CANONICAL_FINANCIAL_DIAGNOSTIC_INPUT_COMPARABILITY_CLOSURE_V1`

Specify and connect the existing factual vintage/period/scope/unit contracts
to the legacy financial diagnostic-input boundary, keeping explicit conflicts
and unavailable metrics, with no new financial ratios, valuation model,
provider acquisition or invented EBITDA/EBIT/CAPEX/debt. This is the dominant
internally addressable contract gap in the measured 4,067 local facts.
It is **not started** here. Signals, portfolio and UI remain out of scope.

## Complete canonical rule table

The table below is generated from the same artifact. `R/P/N` mean
READY/PARTIAL/NOT_READY; `F` means frozen horizon/timeframe definition with
partial runtime consumption. `CD` is current-descriptive at the stored input
endpoint, not fresh-live coverage. Evaluators are methods of
`app.diagnostics.evaluators.DeterministicDiagnosticEvaluators`. Coverage counts
are input prerequisites; `unproven` is deliberately not zero. Full source
fields, exact blockers and canonical horizon cells remain in the JSON.

| ID | Canonical rule name | Category | Evaluator | Canonical input | Source | Coverage | CD | Prospective PIT | Historical PIT | Horizon | Timeframe | Operational state | Exact blockers | Next requirement |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Market Regime Classification | market | market_regime | NIFTY_50 daily OHLC; 4+ aligned observations; breadth optional | CANONICAL_INDEX_OHLC_OBSERVATION | 1/1 | R | N | N | F | F: BENCHMARK_SECTOR_DAILY | OPERATIONAL_CURRENT_DESCRIPTIVE | HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN | Benchmark retrieval known-at; breadth missing remains a limitation |
| 2 | Sector Index Health & Trend | sector | sector_health | Exact sector index + NIFTY_50; 4 aligned daily sessions | NSE_SECTOR_INDEX_MAPPING + CANONICAL_INDEX_OHLC_OBSERVATION | 354/2538 | R | N | N | F | F: BENCHMARK_SECTOR_DAILY | OPERATIONAL_CURRENT_DESCRIPTIVE | HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN, SECTOR_CONTEXT_PARTIAL | No close-only/ETF/TRI or broad-sector proxy |
| 3 | Sector Rotation Phase | sector | sector_rotation | Exact sector index + NIFTY_50; 3-session relative return | NSE_SECTOR_INDEX_MAPPING + CANONICAL_INDEX_OHLC_OBSERVATION | 354/2538 | R | N | N | F | F: BENCHMARK_SECTOR_DAILY | OPERATIONAL_CURRENT_DESCRIPTIVE | HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN, SECTOR_CONTEXT_PARTIAL | Mapping is not OHLC readiness |
| 4 | Primary Trend Direction — Weekly & Daily | technical | primary_trend | Distinct certified daily/weekly snapshots | NSE_UDIFF_DAILY/WEEKLY | 1940/2538 | R | N | N | F | F: TREND_DAILY_WEEKLY | OPERATIONAL_CURRENT_DESCRIPTIVE | HISTORICAL_DEPTH_INSUFFICIENT, HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN | 6 daily and 6 genuine weekly observations |
| 5 | Weinstein Market Stage | technical | weinstein | Genuine weekly structure | NSE_UDIFF_WEEKLY | 2007/2538 | R | N | N | F | F: WEEKLY_STRUCTURE | OPERATIONAL_CURRENT_DESCRIPTIVE | HISTORICAL_DEPTH_INSUFFICIENT, HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN | 5 weekly observations; no daily relabel |
| 6 | Relative Strength Rank vs Nifty 50, Sector Index & Peers | relative | relative_strength | Stock/benchmark aligned sessions; sector/peers descriptive | NSE_UDIFF + canonical PRI index OHLC | unproven | P | N | N | F | F: RELATIVE_STRENGTH_DAILY | PARTIAL | HORIZON_RUNTIME_NOT_ACTIVE, PEER_COHORT_NOT_READY, PIT_NOT_PROVEN, SECTOR_CONTEXT_PARTIAL | Classification uses stock/benchmark; peers absent, not synthetic |
| 7 | Institutional / Smart Money Observable Proxies | technical | smart_money_proxies | OHLCV location and volume | NSE_UDIFF_DAILY | 2538/2538 | R | N | N | F | F: DAILY_PRICE_VOLUME | OPERATIONAL_CURRENT_DESCRIPTIVE | HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN | Observable proxy; not actual institutional transactions |
| 8 | Liquidity Pool Mapping — Buy-side & Sell-side | technical | liquidity_pools | Price/volume clusters | NSE_UDIFF_DAILY | 2538/2538 | R | N | N | F | F: DAILY_PRICE_VOLUME | OPERATIONAL_CURRENT_DESCRIPTIVE | HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN | Technical evidence only |
| 9 | Wyckoff Phase Classification | technical | wyckoff_phase | Price/volume phase proxies | NSE_UDIFF_DAILY | 2538/2538 | R | N | N | F | F: DAILY_PRICE_VOLUME | OPERATIONAL_CURRENT_DESCRIPTIVE | HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN | Existing heuristic unchanged |
| 10 | Classical Market Structure — Dow HH/HL vs LH/LL | technical | market_structure | Daily pivot structure | NSE_UDIFF_DAILY | 2439/2538 | R | N | N | F | F: DAILY_PRICE | OPERATIONAL_CURRENT_DESCRIPTIVE | HISTORICAL_DEPTH_INSUFFICIENT, HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN | 6 daily observations |
| 11 | Volume Behavior & Relative Volume (RVOL) | technical | volume | RVOL and volume continuity | NSE_UDIFF_DAILY | 2538/2538 | R | N | N | F | F: DAILY_PRICE_VOLUME | OPERATIONAL_CURRENT_DESCRIPTIVE | HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN | 4 daily observations |
| 12 | Ichimoku Cloud Structure | technical | ichimoku | Daily OHLC; existing 2/3/4/1 parameters | NSE_UDIFF_DAILY | 2538/2538 | R | N | N | F | F: DAILY_PRICE | OPERATIONAL_CURRENT_DESCRIPTIVE | HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN | 5 daily observations |
| 13 | Chikou Span Confirmation | technical | chikou | Daily OHLC; existing displacement | NSE_UDIFF_DAILY | 2538/2538 | R | N | N | F | F: DAILY_PRICE | OPERATIONAL_CURRENT_DESCRIPTIVE | HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN | 5 daily observations |
| 14 | Multi-Timeframe Alignment — Weekly, Daily, 4H/1H, 15M where data permits | technical | mtf | Distinct 1D/1W snapshots; other frames only if real | NSE_UDIFF_DAILY/WEEKLY | 2007/2538 | P | N | N | F | F: MTF_ROLES_UNSET | PARTIAL | HISTORICAL_DEPTH_INSUFFICIENT, HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN, TIMEFRAME_DATA_NOT_READY | Partial timeframe coverage; no 4H/1H/15m substitution |
| 15 | Business Model & Moat Sustainability | research | business_model_moat | Business/moat predicate ResearchClaims | ResearchSnapshot primary/secondary documents | unproven | N | P | N | F | F: filing/evidence period | NOT_READY | DATA_UNAVAILABLE, HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN | No claim synthesis from financial totals or headlines |
| 16 | Five-Year Financial Trend — Revenue, EBITDA, PAT, EPS CAGR | annual | financial_trend | 6 annual revenue/EBITDA/PAT/EPS points for 5-year CAGR | FinancialFact -> FundamentalsEngineAdapter | unproven | P | P | P | F | F: filing/evidence period | PARTIAL | DATA_UNAVAILABLE, EVIDENCE_CONFLICTED, FRESHNESS_POLICY_UNSET, HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN, SOURCE_CONTRACT_INCOMPLETE | Calendar continuity, basis and units must be comparable |
| 17 | Return Ratios — ROCE and ROE | annual | return_ratios | PAT/EBIT; equity/capital denominator; balance-sheet dates | FinancialFact -> FundamentalsEngineAdapter | unproven | P | P | P | F | F: filing/evidence period | PARTIAL | DATA_UNAVAILABLE, EVIDENCE_CONFLICTED, FRESHNESS_POLICY_UNSET, HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN, SOURCE_CONTRACT_INCOMPLETE | Average equity preferred; documented ending fallback; industrial applicability not inferred for banks |
| 18 | Operating Cash Flow & Free Cash Flow Health | annual | cash_flow | Annual CFO, CAPEX, PAT | FinancialFact -> FundamentalsEngineAdapter | unproven | P | P | P | F | F: filing/evidence period | PARTIAL | DATA_UNAVAILABLE, EVIDENCE_CONFLICTED, FRESHNESS_POLICY_UNSET, HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN, SOURCE_CONTRACT_INCOMPLETE | CFO minus CAPEX; missing CAPEX is not zero |
| 19 | Balance Sheet Leverage — Debt/Equity, Net Debt, Interest Coverage | annual | leverage | Debt/equity/cash/EBIT/interest expense | FinancialFact -> FundamentalsEngineAdapter | unproven | P | P | P | F | F: filing/evidence period | PARTIAL | DATA_UNAVAILABLE, EVIDENCE_CONFLICTED, FRESHNESS_POLICY_UNSET, HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN, SOURCE_CONTRACT_INCOMPLETE | No synthesis from borrowings without governed total-debt bridge |
| 20 | Working Capital & Cash Conversion Cycle | annual | working_capital | Receivables/revenue; inventory/payables/COGS for CCC | FinancialFact -> FundamentalsEngineAdapter | unproven | P | P | P | F | F: filing/evidence period | PARTIAL | DATA_UNAVAILABLE, EVIDENCE_CONFLICTED, FRESHNESS_POLICY_UNSET, HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN, SOURCE_CONTRACT_INCOMPLETE | Explicit applicability flag only; missing is not not-applicable |
| 21 | Ownership Structure — Promoter Holding & Pledge | ownership | ownership | 2 comparable promoter holding/pledge periods | NSE Reg31 OwnershipObservation -> legacy filing fields (not connected) | unproven | N | P | P | F | F: filing/evidence period | NOT_READY | HISTORICAL_DEPTH_INSUFFICIENT, HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN, SOURCE_CONTRACT_INCOMPLETE | One reporting period is not a holding shift |
| 22 | Institutional Holding Shifts — DII/MF/FII | ownership | institutional_holdings | 2 comparable FII/DII/MF holding periods | NSE Reg31 OwnershipObservation -> legacy filing fields (not connected) | unproven | N | P | P | F | F: filing/evidence period | NOT_READY | HISTORICAL_DEPTH_INSUFFICIENT, HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN, SOURCE_CONTRACT_INCOMPLETE | Quarterly holdings != daily flows != block/bulk transactions |
| 23 | Corporate Governance & Auditor Cleanliness | governance | corporate_governance | Auditor/regulatory/restatement/related-party/pledge claims | ResearchSnapshot; canonical disclosures/reliability are separate evidence | unproven | N | P | N | F | F: filing/evidence period | NOT_READY | DATA_UNAVAILABLE, HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN | No claims must not mean CLEAN; adverse block not overridden by growth |
| 24 | Earnings Acceleration Status — Organic vs One-Off | quarterly | earnings_acceleration | 5 quarterly revenue observations | FinancialFact -> FundamentalsEngineAdapter | unproven | P | P | P | F | F: filing/evidence period | PARTIAL | DATA_UNAVAILABLE, EVIDENCE_CONFLICTED, FRESHNESS_POLICY_UNSET, HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN, SOURCE_CONTRACT_INCOMPLETE | Latest versus year-ago; organic/one-off classification not provided |
| 25 | Latest Quarterly Results — YoY & QoQ | quarterly | latest_quarter | 5 quarter-only revenue/EBITDA/PAT/EPS observations | FinancialFact -> FundamentalsEngineAdapter | unproven | P | P | P | F | F: filing/evidence period | PARTIAL | DATA_UNAVAILABLE, EVIDENCE_CONFLICTED, FRESHNESS_POLICY_UNSET, HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN, SOURCE_CONTRACT_INCOMPLETE | Available metrics only; no quarterly interpolation |
| 26 | Operating Margin & Gross Margin Trajectory | quarterly | margin_trajectory | 5 quarter-only EBITDA/revenue observations | FinancialFact -> FundamentalsEngineAdapter | unproven | P | P | P | F | F: filing/evidence period | PARTIAL | DATA_UNAVAILABLE, EVIDENCE_CONFLICTED, FRESHNESS_POLICY_UNSET, HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN, SOURCE_CONTRACT_INCOMPLETE | Operating margin only; gross-margin input unavailable |
| 27 | Order Book & Book-to-Bill Ratio | business | order_book | Latest order book/order inflow/revenue and prior disclosure | Typed FinancialObservation business fields | unproven | N | N | N | F | F: filing/evidence period | NOT_READY | DATA_UNAVAILABLE, HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN | Exact identity, unit, period, known-at and amendments; no stream present |
| 28 | Management Execution Track Record — Guidance vs Delivery | research | management_guidance | Dated GuidanceItem expected versus actual | ResearchSnapshot guidance/documents | unproven | N | P | N | F | F: filing/evidence period | NOT_READY | DATA_UNAVAILABLE, HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN | At least one comparable item; repeated misses use existing rule |
| 29 | Valuation Multiples — P/E, Forward P/E, PEG, EV/EBITDA, P/B | valuation | valuation_multiples | Price date; annual EPS; forward EPS/growth; shares/debt/cash/EBITDA/book | Certified daily price + canonical FinancialFact | unproven | P | P | P | F | F: VALUATION_PRICE_CONTEXT | PARTIAL | DATA_UNAVAILABLE, EVIDENCE_CONFLICTED, FRESHNESS_POLICY_UNSET, HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN, SOURCE_CONTRACT_INCOMPLETE | Partial P/E is not full valuation; missing denominators not zero |
| 30 | Fundamental Catalysts — High/Medium/Low Impact | event | fundamental_catalysts | Non-cancelled typed Catalyst and canonical document | ResearchSnapshot catalysts | unproven | N | P | N | F | F: filing/evidence period | NOT_READY | EVENT_EVIDENCE_NOT_READY, HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN | News-store existence does not establish Catalyst semantics |
| 31 | Comprehensive Risk Engine — Probability × Impact | synthesis | comprehensive_risk | Eligible 1/2/19/23/29/46/55/30; ordinal probability-impact | Existing EvaluatedDiagnostic lineage | unproven | P | N | N | F | F: UPSTREAM_SYNTHESIS | PARTIAL | DATA_UNAVAILABLE, HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN, SOURCE_CONTRACT_INCOMPLETE | Existing runner order does not yet include Rule46 when Rule31 executes |
| 32 | Trading Thesis | synthesis | trading_thesis | Eligible 43/45/46 and risk context | Existing EvaluatedDiagnostic lineage | unproven | P | N | N | F | F: UPSTREAM_SYNTHESIS | PARTIAL | DATA_UNAVAILABLE, HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN | No downstream execution; geometry can still be insufficient |
| 33 | Investment Thesis | synthesis | investment_thesis | Eligible 16/17/18/19/23 | Existing EvaluatedDiagnostic lineage | unproven | P | N | N | F | F: filing/evidence period | PARTIAL | DATA_UNAVAILABLE, HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN | All required fundamental/governance results needed |
| 34 | Bull / Base / Bear Probability Scenarios | synthesis | scenarios | Eligible 31/32/33 | Existing EvaluatedDiagnostic lineage | unproven | P | N | N | F | F: UPSTREAM_SYNTHESIS | PARTIAL | DATA_UNAVAILABLE, HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN | No newly calibrated probabilities |
| 35 | VWAP & Value Area Acceptance | named_vwap | vwap | Named canonical VWAP/value-area semantics | No certified named source | unproven | N | N | N | F | F: NAMED_VWAP_UNAVAILABLE | NOT_READY | HORIZON_RUNTIME_NOT_ACTIVE, NAMED_VWAP_SEMANTICS_UNAVAILABLE, PIT_NOT_PROVEN | Legacy generic VWAP fallback is not canonical source readiness |
| 36 | OBV Trend & Divergence | technical | obv | Daily close/volume | NSE_UDIFF_DAILY | 2538/2538 | R | N | N | F | F: DAILY_PRICE_VOLUME | OPERATIONAL_CURRENT_DESCRIPTIVE | HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN | 4 daily observations |
| 37 | Base Pattern Quality — VCP, Cup & Handle, Flat Base, Ascending Base | technical | base_pattern | Daily OHLCV structural window | NSE_UDIFF_DAILY | 2538/2538 | R | N | N | F | F: DAILY_EXECUTION_CONTEXT | OPERATIONAL_CURRENT_DESCRIPTIVE | HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN | 5 daily observations; governed heuristic unchanged |
| 38 | Pullback Quality & Support Confluence | technical | pullback_quality | Daily support/volume | NSE_UDIFF_DAILY | 2538/2538 | R | N | N | F | F: DAILY_EXECUTION_CONTEXT | OPERATIONAL_CURRENT_DESCRIPTIVE | HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN | 5 daily observations |
| 39 | Technical Indicator Layer — RSI, ADX, ATR | technical | indicator_layer | Existing RSI/ADX/ATR inputs | NSE_UDIFF_DAILY | 2538/2538 | R | N | N | F | F: DAILY_PRICE | OPERATIONAL_CURRENT_DESCRIPTIVE | HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN | 5 daily observations; no added indicators |
| 40 | Aggressive Entry Level | technical | aggressive_entry | Existing daily structure | NSE_UDIFF_DAILY | 2538/2538 | R | N | N | F | F: DAILY_EXECUTION_CONTEXT | OPERATIONAL_CURRENT_DESCRIPTIVE | HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN | Diagnostic geometry; no order authority |
| 41 | Confirmation Entry Level | technical | confirmation_entry | Existing daily structure | NSE_UDIFF_DAILY | 2538/2538 | R | N | N | F | F: DAILY_EXECUTION_CONTEXT | OPERATIONAL_CURRENT_DESCRIPTIVE | HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN | Diagnostic geometry; no order authority |
| 42 | Pullback / Retest Entry Level | technical | retest_entry | Existing daily retest structure | NSE_UDIFF_DAILY | 2538/2538 | R | N | N | F | F: DAILY_EXECUTION_CONTEXT | OPERATIONAL_CURRENT_DESCRIPTIVE | HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN | Diagnostic geometry; no order authority |
| 43 | Structural Stop-Loss | technical | structural_stop | Existing daily structural low | NSE_UDIFF_DAILY | 2538/2538 | R | N | N | F | F: DAILY_EXECUTION_CONTEXT | OPERATIONAL_CURRENT_DESCRIPTIVE | HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN | Diagnostic geometry; no stop order |
| 44 | Target Hierarchy — T1, T2, Extended Target | technical | target_hierarchy | Existing daily resistance/structure | NSE_UDIFF_DAILY | 2538/2538 | R | N | N | F | F: DAILY_EXECUTION_CONTEXT | OPERATIONAL_CURRENT_DESCRIPTIVE | HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN | Diagnostic geometry; no forecast authority |
| 45 | Risk/Reward Calculation — minimum structural R:R normally 1:2 | technical | risk_reward | Existing Rule40/43/44 geometry | Existing diagnostics + certified daily input | 2538/2538 | R | N | N | F | F: UPSTREAM_SYNTHESIS | OPERATIONAL_CURRENT_DESCRIPTIVE | HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN | Input readiness does not guarantee valid reward/risk geometry |
| 46 | Exact Thesis Invalidation Conditions | technical | thesis_invalidation | Existing structural/volume invalidation | NSE_UDIFF_DAILY | 2538/2538 | R | N | N | F | F: DAILY_EXECUTION_CONTEXT | OPERATIONAL_CURRENT_DESCRIPTIVE | HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN | Descriptive invalidation; no automatic sale |
| 47 | Retail / Public Sentiment Score — 0 to 100 | crowd | crowd_sentiment | Typed crowd observations with source/reliability/known-at/dedup | CrowdSnapshot | unproven | N | P | N | F | F: filing/evidence period | NOT_READY | DATA_UNAVAILABLE, HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN | No measured production crowd observations |
| 48 | Crowd Positioning Tier | crowd | crowd_positioning | Typed positioning observations | CrowdSnapshot | unproven | N | P | N | F | F: filing/evidence period | NOT_READY | DATA_UNAVAILABLE, HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN | Not inferred from daily aggregate institutional flows |
| 49 | Crowd Data Confidence | crowd | crowd_data_confidence | Sample, source reliability and independent dedup groups | CrowdSnapshot | unproven | N | P | N | F | F: filing/evidence period | NOT_READY | DATA_UNAVAILABLE, HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN | Not financial-data confidence |
| 50 | Institutional Accumulation vs Distribution Proxy | technical | accumulation_distribution_proxy | OHLCV location/participation | NSE_UDIFF_DAILY | 2538/2538 | R | N | N | F | F: DAILY_PRICE_VOLUME | OPERATIONAL_CURRENT_DESCRIPTIVE | HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN | Not observed institutional ownership |
| 51 | Major Stop-Loss Cluster Mapping | technical | stop_clusters | OHLCV structural clusters | NSE_UDIFF_DAILY | 2538/2538 | R | N | N | F | F: DAILY_PRICE_VOLUME | OPERATIONAL_CURRENT_DESCRIPTIVE | HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN | Technical evidence, not actual stop orders |
| 52 | Liquidity Event Detection — Sweep, Absorption, Breakout Acceptance | technical | liquidity_events | Sweep/absorption/acceptance price-volume | NSE_UDIFF_DAILY | 2538/2538 | R | N | N | F | F: DAILY_PRICE_VOLUME | OPERATIONAL_CURRENT_DESCRIPTIVE | HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN | No execution |
| 53 | Bull Trap Identification | technical | bull_trap | Daily price-volume trap context | NSE_UDIFF_DAILY | 2538/2538 | R | N | N | F | F: DAILY_PRICE_VOLUME | OPERATIONAL_CURRENT_DESCRIPTIVE | HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN | 3 daily observations |
| 54 | Bear Trap Identification | technical | bear_trap | Daily price-volume trap context | NSE_UDIFF_DAILY | 2538/2538 | R | N | N | F | F: DAILY_PRICE_VOLUME | OPERATIONAL_CURRENT_DESCRIPTIVE | HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN | 3 daily observations |
| 55 | Crowd Trap Probability | crowd | crowd_trap_probability | Crowd plus price; certified hybrid input required | CrowdSnapshot + technical input | unproven | N | P | N | F | F: CROWD_PRICE_CONTEXT | NOT_READY | DATA_UNAVAILABLE, HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN | Canonical path fails closed; no hybrid adapter |
| 56 | Price vs Crowd Sentiment Divergence | crowd | crowd_divergence | Crowd plus aligned price | CrowdSnapshot + technical input | unproven | N | P | N | F | F: CROWD_PRICE_CONTEXT | NOT_READY | DATA_UNAVAILABLE, HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN | Canonical path fails closed; no hybrid adapter |
| 57 | Post-News Price Reaction — Absorption vs Sell-the-News | event | post_news_reaction | Canonical event materiality/known-at/completed-session relation | NewsEvent + technical input (canonical join absent) | unproven | N | P | N | F | F: EVENT_REACTION_UNAVAILABLE | NOT_READY | EVENT_EVIDENCE_NOT_READY, HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN | No same-date/post-news-price inference |
| 58 | Volume Climax & Distribution Signs | technical | volume_climax | Daily price and volume | NSE_UDIFF_DAILY | 2538/2538 | R | N | N | F | F: DAILY_PRICE_VOLUME | OPERATIONAL_CURRENT_DESCRIPTIVE | HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN | 3 daily observations |
| 59 | Contrarian Ichimoku Confluence | synthesis | contrarian_ichimoku | Eligible 47/12/13/14 | Existing EvaluatedDiagnostic lineage | unproven | P | N | N | F | F: CONTRARIAN_MTF_UNAVAILABLE | PARTIAL | DATA_UNAVAILABLE, HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN | Missing upstream is INSUFFICIENT_DATA, not CONFLICTING |
| 60 | Contrarian Signal Quality — Strong / Moderate / Weak | synthesis | contrarian_quality | Eligible 55/56/59/49 | Existing EvaluatedDiagnostic lineage | unproven | P | N | N | F | F: CONTRARIAN_MTF_UNAVAILABLE | PARTIAL | DATA_UNAVAILABLE, HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN | No missing-to-weak conversion |
| 61 | Contrarian Action Verdict — Buy / Sell / Hold / Avoid / Wait | synthesis | contrarian_verdict | Eligible 60/49 | Existing EvaluatedDiagnostic lineage | unproven | P | N | N | F | F: CONTRARIAN_MTF_UNAVAILABLE | PARTIAL | DATA_UNAVAILABLE, HORIZON_RUNTIME_NOT_ACTIVE, PIT_NOT_PROVEN | Legacy diagnostic label is not product/trade authorization |
