# Fundamental Inflection Policy Research Proposal V1

**Status: `PROPOSED / NOT_APPROVED / NOT_ACTIVE / RESEARCH_ONLY / NON_EXECUTABLE`.**

## 1. Purpose and boundary

`FUNDAMENTAL_INFLECTION_POLICY_RESEARCH_PROPOSAL_V1` turns the explicit
definition gaps reported by the existing Fundamental Inflection Research Shadow
into a governed research map. It does not evaluate an issuer, create a
candidate, select a threshold, calculate a score, rank securities, create a
setup, or alter a portfolio.

The required conceptual chain remains deliberately separated:

```text
ACCOUNTING CHANGE -> EXPECTATION SURPRISE -> CONFIRMATION -> MARKET REACTION
```

Each arrow requires separate evidence and separately approved semantics. An
accounting change is neither an analyst surprise nor proof of confirmation; a
market reaction is neither proof of fundamental truth nor an investment
instruction.

Every future result must preserve the existing `WATCH_ONLY / NON_EXECUTABLE /
RESEARCH_ONLY` boundary. This proposal grants no policy, product strategy,
broker, order, portfolio, discovery, Decision Score, Six Gates, API, UI, or
runtime authority.

## 2. Existing contracts reused, without rebuilding them

The following are current factual infrastructure, not an approved Inflection
qualification policy:

| Existing contract | Reusable factual role | Inflection implication |
| --- | --- | --- |
| Canonical instrument, NSE session, ISIN/CIN continuity, and PIT company-type receipts | Exact issuer/security/basis lineage | Required for every eventual input join. |
| `FinancialFact`, vintage selection, financial observation bundle, and `financial-metric-trajectory-policy / v1-approved` | Exact scope, period, representation, revision, PIT and period-pair checks | Can construct an eligible factual YoY quarterly trajectory only through an explicit pair request. |
| Metric directionality and semantic-materiality policies | Metric-local factual orientation; materiality remains calibration-gated | Neither is an Inflection confirmation, acceleration, score, or qualification. |
| `CorporateFiling` and financial-result metadata | Primary-exchange filing identity, `announced_at`, `received_at`, period, scope, and revision links | A filing timestamp is available for many BSE financial-result records, but no event-session/reaction contract exists. |
| Historical daily OHLCV, `NIFTY_500`, and sector-index series | Raw bars, volume, provider lineage and adjustment status | Candidate reaction inputs only; no approved event join, benchmark-selection, or price-integrity policy for Inflection. |
| External Intelligence, News Evidence, Research Snapshot | Contextual primary/secondary evidence with source and PIT fields | Not a consensus, estimate-history, structured guidance, or analyst-revision source. |
| Fundamental Inflection Research Shadow V1 | Fail-closed long-term readiness projection | Remains unchanged; its `POLICY_DEFINITION_MISSING` output is the starting boundary for this proposal. |

The legacy `app.strategies.inflection` candidate engine is not this policy and
does not establish a Post-V1 Fundamental Inflection strategy approval. Its
legacy candidate-generation configuration, thresholds, and output vocabulary
are neither reused nor activated here.

## 3. Candidate accounting definitions — research only

### 3.1 Required factual precursor

For a metric `m` at reporting quarter `t`, the factual input must be an
`AVAILABLE` `FinancialMetricTrajectory` with:

- `basis = YEAR_OVER_YEAR_QUARTER`;
- one exact instrument, statement scope, currency, unit, scale, value basis,
  normalization and complete-period identity;
- selected-vintage and source-fact lineage visible at the same explicit
  `as_of`;
- no unresolved conflict, ambiguous pair, same-accounting-period revision,
  partial period, or later-known fact; and
- a positive prior base, because only then does the existing trajectory
  contract expose a relative delta.

This is a factual comparison prerequisite. It has no favorable/unfavorable,
material, persistent, or action meaning.

### 3.2 PAT acceleration candidate

For research notation only, let `g_PAT(t)` be the relative delta of the exact
YoY quarterly PAT trajectory at `t`. The candidate accounting acceleration is:

```text
PAT_ACCELERATION(t) = g_PAT(t) - g_PAT(t-1)
```

This is a proposed factual derived measure, not an approved formula, filter,
or result. It requires two separately valid YoY PAT trajectories: `t` versus
the matching quarter in the preceding fiscal year, and `t-1` versus its own
matching prior-year quarter. It must never pair source records by arrival order
or use a same-period revision as business growth.

| Numeric/lineage condition | Proposed disposition |
| --- | --- |
| Positive prior PAT in both YoY trajectories; exact parity; both trajectories factual and PIT-valid | `READY_FOR_DEFINITION_TESTING`; raw candidate value may be computed only in a future factual contract. |
| Loss to profit, profit to loss, loss to loss, or zero prior PAT | `NON_COMPARABLE`; no percentage growth or acceleration is fabricated. |
| Near-zero but non-zero prior PAT | `DEFINITION_MISSING`; no epsilon or denominator rule is approved. |
| Restated same accounting period, unresolved revision lineage, exceptional item, acquisition/disposal attribution absent, or basis/scope mismatch | `NON_COMPARABLE` or `DEFINITION_MISSING`; no hidden normalized earnings adjustment. |
| Missing comparable quarter, incomplete period identity, later-known input, or ambiguous selection | `PARTIALLY_READY` input only; no acceleration value. |

`EXCEPTIONAL_ITEM_PRESENT`, `ACQUISITION_DISTORTION`, and
`DISPOSAL_DISTORTION` are required future explicit states when primary filing
evidence can establish them. The complete proposed fail-closed base-effect and
one-off register is `LOSS_TO_PROFIT`, `PROFIT_TO_LOSS`, `NEAR_ZERO_BASE`,
`EXCEPTIONAL_ITEM_PRESENT`, `RESTATEMENT`, `ACQUISITION_DISTORTION`,
`DISPOSAL_DISTORTION`, `BASIS_CHANGED`, and `NON_COMPARABLE`. These states are
not inferred from an unusual number, and none authorize an adjustment to the
reported facts.

### 3.3 Revenue acceleration candidate

For research notation only, let `g_REVENUE(t)` be the relative delta of the
exact YoY quarterly revenue trajectory at `t`:

```text
REVENUE_ACCELERATION(t) = g_REVENUE(t) - g_REVENUE(t-1)
```

It uses the same exact lineage and numeric-domain requirements as PAT but is a
separate measure. Revenue acceleration neither repairs a PAT base effect nor
substitutes for PAT acceleration. Revenue-specific acquisition, demerger,
currency, reporting-perimeter and accounting-basis evidence requires a future
attribution policy; absent that, the result is `DEFINITION_MISSING` or
`NON_COMPARABLE` as applicable.

### 3.4 Research combinations, not scoring

The following are mutually inspectable future research combinations only:

| Candidate combination | Proposed evidence requirement | Current policy state |
| --- | --- | --- |
| A. PAT acceleration | One valid PAT acceleration observation | `PROPOSED`; no qualification meaning. |
| B. Revenue acceleration | One valid revenue acceleration observation | `PROPOSED`; no qualification meaning. |
| C. Revenue and PAT same-direction acceleration | Both factual measures with explicit sign/domain treatment | `PROPOSED`; no weight, score, or winner. |
| D. Revenue + PAT + operating/margin corroboration | A separately approved operating/margin contract | `CANONICAL_DATA_MISSING` for the required Inflection interpretation. |
| E. Revenue + PAT + cash-quality corroboration | A separately approved cash-quality contract | `CANONICAL_DATA_MISSING` for the required Inflection interpretation. |

Candidate confirmation windows `{1Q, 2Q, 3Q}` are frozen research alternatives
only. In particular, `2Q` is not a confirmed state, and no persistence window
is selected.

## 4. Expectations, revisions, and guidance remain distinct

| Dimension | Exact required canonical input | Current finding | Proposed fail-closed state |
| --- | --- | --- | --- |
| `CONSENSUS_SURPRISE` | Actual reported metric; consensus immediately before the announcement; estimate timestamp; forecast horizon; analyst count and dispersion where available | No PIT-safe consensus snapshot or estimate-history contract/store exists | `CANONICAL_CONSENSUS_DATA_MISSING` |
| `TIME_SERIES_UNEXPECTED_EARNINGS` | Separately governed accounting-series forecast/model, training scope, revision treatment, and PIT outcome design | No forecasting contract is approved | `DEFINITION_MISSING` |
| Analyst revision | PIT consensus immediately before/after result; exact horizon, analyst count, dispersion, direction, magnitude, and deterministic `+2/+5/+10` trading-session windows | No PIT estimate revision-history contract exists | `REVISION_DATA_MISSING` |
| Management guidance | Exact primary filing/event identity, metric, horizon, value/range, previous guidance, announcement time, provenance and a controlled state transition | Generic `ResearchSnapshot.GuidanceItem` exists, but no canonical primary-source, immutable guidance observation/selection contract exists | `CANONICAL_DATA_MISSING` |

Time-series accounting change must never be labelled analyst surprise. Generic
text sentiment or management language must never be converted to `RAISED`
guidance. A future guidance contract may use only the states
`NEW_GUIDANCE`, `RAISED`, `MAINTAINED`, `LOWERED`, `WITHDRAWN`, and
`NOT_PROVIDED` when its exact sourced comparison is available.

## 5. Event, price, and volume research boundaries

`CorporateFiling.announced_at` and `received_at` are timezone-aware, and the
current production database contains primary BSE financial-result filings.
That alone does not establish whether an event was before market, intraday,
after close, or on a non-trading day. A future reaction contract must require:

1. the exact financial-result filing and selected-fact lineage;
2. an exact publication/announcement timestamp, never an invented time;
3. the applicable exchange calendar and a verified event-session / next
   tradable-session classification;
4. raw-bar provider, adjustment-basis, quality, and bar-knownness lineage;
5. a separately selected broad-market and, where used, sector benchmark; and
6. a rule that excludes later restatements, after-event estimates, and future
   sector/index data from the event-as-of view.

| Candidate dimension | Candidate research families | Current feasibility | Reason it is not an active calculation |
| --- | --- | --- | --- |
| Event alignment | before market / during market / after close / non-trading day; event session and next tradable session | `EVENT_TIME_MISSING` | No canonical event-session classifier or result-to-bar alignment contract. |
| Price reaction | raw return; stock minus broad benchmark; stock minus sector benchmark at event session, `0->1D`, `0->3D`, `0->5D` | `PARTIALLY_READY` inputs | Daily stock, NIFTY 500, and sector-index bars exist, but event alignment, benchmark selection, adjustment treatment and reaction semantics are unapproved. |
| Post-announcement drift | Follow-on `1D/3D/5D` and later persistence | `DEFINITION_MISSING` | It must not be conflated with the event reaction. |
| Volume reaction | event volume / prior `20D mean`, `20D median`, or `60D median` | `PARTIALLY_READY` inputs | Daily volume exists, but no event alignment, valid-session baseline, or volume-ratio policy is approved. |

No return threshold, volume threshold, benchmark, sector fallback, or reaction
sign is selected. `AdjustmentStatus.UNKNOWN` bars cannot silently become
adjusted or total-return evidence.

## 6. Financial-sector and structural branches

Industrial revenue/PAT acceleration is not a universal formula.

| Branch | Required future inputs | V1 disposition |
| --- | --- | --- |
| Non-financial corporate | Exact revenue/PAT quarterly trajectories and the safety conditions in section 3 | `READY_FOR_DEFINITION_TESTING` only; not a qualification result. |
| Bank | NII, operating profit, PAT, loan/deposit growth, asset-quality trajectory, credit costs, exact regulatory/reporting basis | `NOT_APPLICABLE` until a separately governed bank contract exists. |
| NBFC | AUM, NII, PAT, credit costs, asset quality, exact reporting basis | `NOT_APPLICABLE` until a separately governed NBFC contract exists. |
| Insurer | Product-specific life/general/health operating metrics, reserve/solvency and reporting basis | `NOT_APPLICABLE` until a separately governed insurer contract exists. |
| Unknown or structurally non-comparable issuer | Exact company-type and comparability evidence | `NOT_APPLICABLE`. |

## 7. Read-only checkpoint data feasibility

The following is a read-only repository/SQLite audit at this proposal
checkpoint; counts describe available evidence, not coverage adequacy or
Inflection validity.

| Concept | Current canonical evidence | PIT/time status | Calculation status | Missing contract/data | Status |
| --- | --- | --- | --- | --- | --- |
| Quarterly revenue/PAT source facts | 2,800 quarterly facts (1,457 consolidated, 1,343 standalone); 393 quarterly revenue and 393 PAT facts | `published_at`, `received_at`, scope and fact-vintage selection retained | Factual YoY pair can be built only from an explicit valid bundle/pair | Cross-trajectory acceleration artifact and edge-case/attribution policy | `READY_FOR_DEFINITION_TESTING` |
| PAT/revenue acceleration | Existing trajectory policy supports exact `YEAR_OVER_YEAR_QUARTER` factual relative delta only with positive prior base | PIT-safe if both trajectories share explicit cutoff | No current acceleration object/evaluator | Acceleration semantic, near-zero, restatement/one-off and attribution definition | `DEFINITION_MISSING` |
| Consensus surprise/revisions | No canonical consensus or estimate-history table/contract | Not available | No | Estimate snapshots, timestamps, horizon, analyst count/dispersion | `CONSENSUS_DATA_MISSING` / `REVISION_DATA_MISSING` |
| Guidance | Generic research-model type only | No canonical selected primary guidance observation | No | Primary-source extraction, range/previous-value semantics, immutable selection/versioning | `CANONICAL_DATA_MISSING` |
| Result event timestamp | 332 `FINANCIAL_RESULTS` filings, all currently BSE-official, with timezone-aware filing timestamps | Timestamp field exists | No event-session classification | Exchange-session timing and exact result-to-fact contract | `EVENT_TIME_MISSING` |
| Price/benchmark reaction | 1,545,139 daily bars, including NIFTY 500 and sector-index series | Bar provenance/quality/adjustment retained | No event-safe reaction calculation | Event join, benchmark selection, adjustment and reaction policy | `PARTIALLY_READY` |
| Volume reaction | All stored daily bars have volume | Bar series exists | No event-safe baseline calculation | Event join, valid-session baseline and ratio interpretation policy | `PARTIALLY_READY` |
| Operating/margin/cash confirmation | Raw financial metric vocabulary has partial ingredients | Exact interpretation not materialized for Inflection | No | Metric/materiality, definition, sector and calibration policy | `CANONICAL_DATA_MISSING` |
| Bank/NBFC/insurer inflection | PIT company-type branches exist | Company class retained | No | Sector-specific financial/operating metric contracts | `NOT_APPLICABLE` |

The smallest useful current subset is therefore **factual non-financial
quarterly revenue/PAT acceleration inputs only**, after an explicit
cross-trajectory, edge-case and event-alignment contract is added. It is not a
positive Inflection Watch and must not be represented as one.

## 8. Future candidate grid and validation protocol

No Cartesian search or winner selection is authorized. A future empirical plan
may record, separately and immutably:

- acceleration representation: positive raw acceleration, cross-sectional
  percentile only after an exact PIT universe/membership contract, or
  predeclared magnitude bands only after human approval;
- confirmation alternatives: `1Q`, `2Q`, `3Q`;
- reaction windows: event session, `0->1D`, `0->3D`, `0->5D`; and
- volume baselines: prior `20D mean`, `20D median`, `60D median`.

Future primary outcomes must retain next-quarter growth persistence, future
revenue/PAT trajectory, and—only where future contracts exist—operating/margin
continuation, revision persistence, and guidance follow-through. Secondary
market telemetry may retain `1D/5D/20D` raw, benchmark-relative and
sector-relative return, MFE, MAE, drawdown and trend persistence. None may be
optimized solely for return, and no immature outcome is a failed outcome.

Required anti-look-ahead safeguards are: selected-vintage facts at the event
as-of; no current restatement substituted into an old observation; no
post-event estimate in a pre-event consensus snapshot; exact after-hours and
non-trading-day handling; point-in-time benchmark/sector membership; and
immutable source/evidence fingerprints.

## 9. Intended governance lifecycle and next bounded continuation

```text
RESEARCH_PROPOSAL -> DATA_READY -> CANDIDATE_GRID -> PROSPECTIVE_SHADOW
    -> EMPIRICALLY_REVIEWED -> HUMAN_APPROVED -> ACTIVE
```

This proposal remains at the first state. The next bounded continuation is:

`INFLECTION_TESTABLE_DERIVED_METRICS_AND_EVENT_ALIGNMENT_V1`

It may define and test a pure factual, non-financial acceleration observation
over two exact YoY trajectories and specify the immutable financial-result to
event-session lineage. It must not compute a candidate, choose a grid value,
interpret materiality, calculate a price/volume reaction, or modify the
existing Inflection Research Shadow.

Consensus, revision, guidance, financial-sector, price-reaction and
volume-reaction work remain separate missing-contract slices. Compounder
historical reconstruction, qualification, candidate grid, and prospective
ledger are explicitly out of scope.

## 10. Explicit non-goals

No active Inflection qualification, `SHADOW_CANDIDATE`, score, ranking,
recommendation, entry/exit/target/stop, allocation, portfolio access, paper
trade, broker/order access, API/UI, persistence, scheduler, provider request,
or automatic action is created by this proposal.

`FACT -> DATA -> INTERPRETATION -> INFERENCE` remains mandatory. Primary
sources remain first; all unavailable or non-comparable evidence fails closed.
