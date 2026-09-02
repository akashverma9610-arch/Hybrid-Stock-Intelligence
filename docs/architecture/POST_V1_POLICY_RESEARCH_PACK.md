# Post-V1 Policy Research Pack — Research-Shadow Parameters

**Status: `RESEARCHED_POLICY_PROPOSAL / DOCUMENTATION_ONLY / IMPLEMENTATION_NOT_AUTHORIZED / NOT_ACTIVE`.**

This pack is a primary-source and repository-feasibility record for the
remaining Post-V1 strategy families. It creates no evaluator, registry
activation, persistence, API/UI, portfolio access, broker/order access, or
trade authority. Every proposed output remains research-only,
`WATCH_ONLY / NON_EXECUTABLE`.

## 1. Research dossier and source hierarchy

Access date for every source below: **2026-09-03**. Regulatory requirements
are disclosure, prudential, or accounting boundaries—not investment SELL/EXIT
rules.

| ID | Source / authority / date | Claim used | Jurisdiction, limitation, classification |
| --- | --- | --- | --- |
| R1 | [SEBI LODR Regulations, last amended 28 March 2025](https://www.sebi.gov.in/legal/regulations/mar-2025/securities-and-exchange-board-of-india-listing-obligations-and-disclosure-requirements-regulations-2015-last-amended-on-march-28-2025-_93409.html) | Material-event disclosure is an authoritative event boundary. | India listed entities; disclosure is not economic direction. `REGULATORY_BOUNDARY` |
| R2 | [SEBI Regulation 30 industry standards, 25 February 2025](https://www.sebi.gov.in/sebi_data/attachdocs/feb-2025/1740483434491.pdf) | Listed entities must follow standards for material-event disclosure. | India; disclosed materiality is not HSI materiality or a trade conclusion. `REGULATORY_BOUNDARY` |
| R3 | [SEBI statutory-auditor resignation circular, 18 October 2019](https://www.sebi.gov.in/legal/circulars/oct-2019/resignation-of-statutory-auditors-from-listed-entities-and-their-material-subsidiaries_44703.html) | Auditor resignation is an official disclosure event requiring retained factual context. | India; no presumption of misconduct. `REGULATORY_BOUNDARY` |
| R4 | [SEBI CRA Regulations, last amended 23 April 2025](https://www.sebi.gov.in/legal/regulations/apr-2025/securities-and-exchange-board-of-india-credit-rating-agencies-regulations-1999-last-amended-on-april-23-2025-_93688.html) | CRA ratings are monitored/reviewed and rating definitions/rationale are disclosed; they are not buy/hold/sell recommendations. | India debt issuers; issuer and instrument scope must match. `REGULATORY_BOUNDARY` |
| R5 | [MCA Ind AS 1](https://www.mca.gov.in/Ministry/pdf/INDAS1.pdf) and [Ind AS 7](https://www.mca.gov.in/Ministry/pdf/Ind_AS7.pdf) | Financial-statement presentation and cash-flow classification are source/period boundaries. | India Ind-AS reporters; not a comparability or quality threshold. `ACCOUNTING_DEFINITION` |
| R6 | [ICAI audit standards index](https://www.icai.org/category/accounting-standards) (Revised SA 705/706 listed) | Modified-opinion and emphasis/other-matter labels must retain exact audit taxonomy. | India audit standards; an audit label is not a fraud finding. `ACCOUNTING_DEFINITION` |
| R7 | [RBI NBFC Scale Based Regulation Directions, 2023, updated 10 October 2024](https://systemhealth.rbi.org.in/Scripts/BS_ViewMasDirections.aspx_id%3D12550%281%29.html) | NBFC prudential capital/liquidity/asset-quality measures are sector-specific. | India NBFCs; never apply non-financial debt/EBITDA rules. `REGULATORY_BOUNDARY` |
| R8 | [IRDAI Corporate Governance for Insurers Regulations, 2024](https://irdai.gov.in/web/guest/consolidated-gazette-notified-regulations?filterDepartment=FNA&filtersApplied=true) and [Insurance Act solvency provisions](https://noc.irdai.gov.in/Content/docs/Insurance%20Act%2C1938%20-%20incorporating%20all%20amendments%20till%2020212021-08-12.pdf) | Insurer solvency/governance is insurer-specific. | India insurers; not debt/EBITDA or CFO/PAT. `REGULATORY_BOUNDARY` |
| R9 | [Nifty 500 methodology, October 2025](https://www.niftyindices.com/docs/default-source/indices/nifty-500/nifty-500-whitepaper_2025.pdf?sfvrsn=7b2c6635_4) | Nifty 500 has defined investability, trading-frequency and impact-cost methodology. | India equity benchmark; index eligibility is not a trade-liquidity approval. `REGULATORY_BOUNDARY` |
| R10 | [Jegadeesh & Titman (1993), *Journal of Finance*, DOI](https://doi.org/10.1111/j.1540-6261.1993.tb04702.x) | Intermediate-horizon relative-return persistence motivates a testable resilience/rotation hypothesis. | US 1965–89 sample; not an Indian threshold or performance promise. `EMPIRICAL_LINEAGE` |

Primary-source order for any future event: exact exchange/issuer filing;
regulator/government notification; registered CRA release; official audited
statement; then reliable media as contextual only. Social, rumour, GMP, or
unverified narrative cannot satisfy eligibility. `FACT → DATA →
INTERPRETATION → INFERENCE` remains mandatory.

## 2. Repository evidence-feasibility matrix

| Proposed input | Core source/module | PIT/depth and limitation | Outcome |
| --- | --- | --- | --- |
| Exact instrument / filing / fact | `FinancialFact`, vintage selector, BSE collector | PIT publication/receipt and revision lineage; coverage remains uneven. | `REUSABLE_UNCHANGED` |
| External event/source/exposure/materiality | `ExternalEvent`, `EvidenceVersion`, `OpportunityArchetypeRouter` | Immutable identity and timestamps; no approved adverse-polarity or legal-family classifier. | `DERIVED_READ_ONLY_METRIC_REQUIRED` |
| Reliability/freshness/conflict | `IntelligenceEvidenceAvailability`, `ReliabilityIntegrityObservation` | PIT state exists; source-specific freshness policy varies. | `REUSABLE_UNCHANGED` |
| Rule 46 | canonical diagnostic / `THESIS_INVALIDATION.md` | Exact price-structure context only. | `REUSABLE_UNCHANGED` |
| Revenue, margin, cash, balance sheet | financial facts, financial research wrappers | Quarterly/annual scope and restatement lineage; sector and coverage gaps. | `MORE_PIT_HISTORY_REQUIRED` |
| Bank/NBFC asset quality/capital/liquidity | no canonical prudential extractor | RBI disclosures are issuer/sector-specific. | `NEW_APPROVED_DATA_SOURCE_REQUIRED` |
| Insurer solvency/combined ratio/embedded value | no canonical insurer extractor | IRDAI/issuer reporting required. | `NEW_APPROVED_DATA_SOURCE_REQUIRED` |
| Price, return, sector, benchmark | canonical OHLCV, index stores, sector ranking | PIT history exists; breadth/delivery parity is incomplete. | `DERIVED_READ_ONLY_METRIC_REQUIRED` |
| Delivery, impact cost, slippage, tax | NSE data / no canonical tax-cost contract | No replay-complete cost/tax model. | `NEW_APPROVED_DATA_SOURCE_REQUIRED` |
| Portfolio concentration / incumbent facts | portfolio snapshot and rotation engine | Access is prohibited for this product-policy phase. | `UNAVAILABLE` |
| Market extremes | `MarketExtremesAssessment` | Context only; not a resilience threshold. | `REUSABLE_UNCHANGED` |

## 3. Sell/Risk completeness matrix

`SELL_RISK_REVIEW_POLICY / v1-research-shadow` is implemented only for
already-classified, exact primary adverse evidence and Rule 46 context. It is
not the broad family below.

| Category | Branch / exact candidate or explicit unavailable rule | Parameter status | Core feasibility / status |
| --- | --- | --- | --- |
| Rule 46 price structure | Reuse verbatim; output only `TECHNICAL_STRUCTURE_REVIEW`. | `IMPLEMENTED_EXACTLY` | `REUSABLE_UNCHANGED` |
| Official HIGH/CRITICAL adverse event | Existing upstream adverse class + exact verified mapping + fresh primary source + `received_at` and `available_at <= as_of`; conflict wins. | `IMPLEMENTED_EXACTLY` | Existing adverse classifier absent in live upstream; otherwise reusable. |
| Revenue / earnings | Non-financial: annual/TTM revenue and PAT change vs same basis; candidate deterioration grid `{<0%, <=-5%, <=-10%}` over `{1,2}` comparable periods. Zero/negative bases → unavailable. | `RESEARCH_SHADOW_V1_CANDIDATE` | `MORE_PIT_HISTORY_REQUIRED` |
| EBITDA / operating margin | Non-financial only: `(operating_profit / revenue)` current minus prior comparable margin; grid `{<-100,-250,-500}` bps, with both numerator/denominator same scope. | `RESEARCH_SHADOW_V1_CANDIDATE` | `DERIVED_READ_ONLY_METRIC_REQUIRED` |
| CFO/PAT and FCF | Non-financial only: `CFO / PAT`; FCF requires approved capex definition. Negative/zero PAT or missing cash-flow → unavailable, never ratio sign inference. | `PARAMETER_RESEARCH_REQUIRED` | `MORE_PIT_HISTORY_REQUIRED` |
| Leverage / interest cover | Non-financial only: net debt/EBITDA and EBIT/finance cost; candidate grids `{2,3,4}` and `{3,2,1}` respectively; zero/negative EBITDA/EBIT → unavailable. | `RESEARCH_SHADOW_V1_CANDIDATE` | `DERIVED_READ_ONLY_METRIC_REQUIRED` |
| Refinancing / liquidity | Require dated debt maturity, committed facilities and cash; no proxy from total debt. | `PARAMETER_RESEARCH_REQUIRED` | `NEW_APPROVED_DATA_SOURCE_REQUIRED` |
| Rating/default | Exact CRA release, issuer/instrument match, rating symbol/outlook and previous release retained; no cross-issuer aggregation. | `REGULATORY_BOUNDARY` | `REGULATORY_EVENT_ONLY` |
| Dilution | Exact filing with shares before/after, instrument, record/ex date and proceeds; candidate ratio `(post-pre)/pre` grid `{5%,10%,20%}`. | `RESEARCH_SHADOW_V1_CANDIDATE` | `NEW_APPROVED_DATA_SOURCE_REQUIRED` |
| Order book/execution | Require order-book opening, additions, revenue conversion and cancellation, all same currency/scope; no announcement-only conclusion. | `PARAMETER_RESEARCH_REQUIRED` | `NEW_APPROVED_DATA_SOURCE_REQUIRED` |
| Pledge / promoter sale | Exact exchange shareholding/encumbrance disclosure, holder identity, before/after quantities and dates; no motive inference. | `REGULATORY_BOUNDARY` | `NEW_APPROVED_DATA_SOURCE_REQUIRED` |
| Auditor resignation / opinion | Retain exact R3/SA 705/706 category, filing, date and stated reason. `QUALIFIED`, `ADVERSE`, `DISCLAIMER`, `RESIGNATION` are review facts, not fraud labels. | `REGULATORY_BOUNDARY` | `REGULATORY_EVENT_ONLY` |
| Fraud / investigation / litigation | Require exact official category (`allegation`, `notice`, `investigation`, `charge`, `order`, `final adjudication`) and primary source. No promotion between categories. | `REGULATORY_BOUNDARY` | `DERIVED_READ_ONLY_METRIC_REQUIRED` |
| Policy transmission / external deterioration | Exact source plus verified exposure and lifecycle; the transmission chain remains unscored until revenue/cash evidence exists. | `PARAMETER_RESEARCH_REQUIRED` | `DERIVED_READ_ONLY_METRIC_REQUIRED` |
| Evidence degradation | Missing/stale/conflicted/non-comparable/unverified → unavailable/blocker, never negative thesis. | `IMPLEMENTED_PARTIALLY` | `REUSABLE_UNCHANGED` |
| Banks | Use capital, GNPA/NNPA, provision coverage, liquidity and RBI action only after dedicated extractor; debt/EBITDA, EBITDA margin, CFO/PAT are `NOT_APPLICABLE`. | `PARAMETER_RESEARCH_REQUIRED` | `NEW_APPROVED_DATA_SOURCE_REQUIRED` |
| NBFCs | Use R7 scale/layer, capital, asset quality, liquidity and funding-mix fields only after extractor; non-financial ratios are `NOT_APPLICABLE`. | `REGULATORY_BOUNDARY` | `NEW_APPROVED_DATA_SOURCE_REQUIRED` |
| Insurers | Use R8 solvency, claims/combined-ratio and product-specific measures only after extractor; debt/EBITDA, EBITDA margin, CFO/PAT are `NOT_APPLICABLE`. | `REGULATORY_BOUNDARY` | `NEW_APPROVED_DATA_SOURCE_REQUIRED` |

All non-implemented categories require exact primary/source lineage, `as_of`,
freshness, conflict state, supersession link, and `EVIDENCE_UNAVAILABLE` when
any required field is absent. Recurrence is keyed by canonical event identity;
the same identity never increases review state.

## 4. Profit-Harvesting review proposal

**Implementability correction:**
[`POST_V1_PROFIT_HARVESTING_IMPLEMENTABILITY_CORRECTION.md`](POST_V1_PROFIT_HARVESTING_IMPLEMENTABILITY_CORRECTION.md)
records why this research-shadow candidate table is not by itself an
implementation authorization. In particular, its total-return and PIT-peer
contracts, grid-to-status mapping, confirmation, persistence, and freshness
semantics require an explicit selected policy path.

Allowed future statuses only: `PROFIT_REVIEW_UNAVAILABLE`,
`NO_PROFIT_REVIEW_EVIDENCE`, `MONITOR_PROFIT`, `PRIORITY_PROFIT_REVIEW`,
`THESIS_REALIZATION_REVIEW`, and `CONFLICTED_PROFIT_REVIEW`. They never mean
SELL, TRIM, EXIT, a target, quantity, or order.

| Rule / exact input | Candidate measurable definition and failure state | Parameter status / feasibility |
| --- | --- | --- |
| Valuation extension | Require one approved sector-specific valuation method, price timestamp, denominator, peer/historical universe and scope. Without all → `PROFIT_REVIEW_UNAVAILABLE`. | `PARAMETER_RESEARCH_REQUIRED`; `MORE_PIT_HISTORY_REQUIRED` |
| Price extension / euphoria | Candidate read-only excess return: `stock total-return - NIFTY500 total-return` over `{20,60,120}` completed sessions; candidate percentile grid `{80,90,95}` within PIT peer universe. | `RESEARCH_SHADOW_V1_CANDIDATE`; `DERIVED_READ_ONLY_METRIC_REQUIRED` |
| Concentration | Requires approved read-only portfolio snapshot, valuation basis and concentration denominator; no access in P1. | `PARAMETER_RESEARCH_REQUIRED`; `UNAVAILABLE` |
| Milestone/catalyst realization | Exact approved family milestone plus verified primary completion/correction lifecycle. Missing milestone contract → unavailable. | `PARAMETER_RESEARCH_REQUIRED`; `DERIVED_READ_ONLY_METRIC_REQUIRED` |
| Forward reward/risk | Requires approved valuation/upside and structural-risk methods; Rule 46 is context only. | `PARAMETER_RESEARCH_REQUIRED`; `UNAVAILABLE` |
| Partial vs complete realization | Requires approved thesis target/milestone and portfolio authority; neither exists. | `PARAMETER_RESEARCH_REQUIRED`; `UNAVAILABLE` |
| Liquidity/slippage/tax | Require executable cost/tax schedule, order-size and PIT liquidity data; candidate grid must be calibrated by bucket. | `PARAMETER_RESEARCH_REQUIRED`; `NEW_APPROVED_DATA_SOURCE_REQUIRED` |
| Freshness/conflict/persistence | All inputs must align at `as_of`; conflict → `CONFLICTED_PROFIT_REVIEW`; no universal duration or persistence count is selected. | `PARAMETER_RESEARCH_REQUIRED`; `REUSABLE_UNCHANGED` |

## 5. Fast-Rotation comparison proposal

This is `ROTATION_COMPARISON`, never `ROTATION_AUTHORIZATION`. Cash may be a
comparison state, but no cash deployment or holding mutation is permitted.

| Rule / exact input | Candidate measurable definition and failure state | Parameter status / feasibility |
| --- | --- | --- |
| Bucket taxonomy | `CORE_COMPOUNDER`, `EMERGING_SATELLITE`, `THEMATIC`, `TACTICAL`; require an approved immutable assignment source. Missing → comparison unavailable. | `PARAMETER_RESEARCH_REQUIRED`; `UNAVAILABLE` |
| Same/cross-bucket | Same bucket only initially; cross-bucket requires separately approved hurdle, never implicit substitution. | `PARAMETER_RESEARCH_REQUIRED`; `UNAVAILABLE` |
| Improvement | Existing concept becomes candidate normalized delta grid `{0.70,0.85,1.00}` only after common score scale/version/evidence parity is verified. | `RESEARCH_SHADOW_V1_CANDIDATE`; `DERIVED_READ_ONLY_METRIC_REQUIRED` |
| Risk/reward | Require identical horizon, valuation/risk method and non-zero comparable denominators; otherwise unavailable. | `PARAMETER_RESEARCH_REQUIRED`; `UNAVAILABLE` |
| Costs/liquidity/tradability | Require R9-style trading evidence plus actual PIT impact-cost/slippage and tax model; index eligibility is insufficient. | `PARAMETER_RESEARCH_REQUIRED`; `NEW_APPROVED_DATA_SOURCE_REQUIRED` |
| Correlation/concentration | Require approved return frequency/window and read-only portfolio exposure; candidate windows `{60,120,252}` sessions. | `RESEARCH_SHADOW_V1_CANDIDATE`; `UNAVAILABLE` |
| Freshness/persistence/churn | Candidate alignment: all evidence `available_at <= as_of`, same completed session; test persistence grid `{1,3,5}` sessions and cooldown `{5,10,20}` sessions. | `RESEARCH_SHADOW_V1_CANDIDATE`; `MORE_PIT_HISTORY_REQUIRED` |
| Conflict/invalidation | Any unaligned/stale/conflicted/non-comparable input → comparison unavailable; Rule 46 can be context, never authorization. | `IMPLEMENTED_PARTIALLY`; `REUSABLE_UNCHANGED` |

## 6. Long-Term family parameter proposal

All families require consolidated facts where available; standalone only when
consolidated is unavailable and the output says so. Annual/TTM and quarterly
facts cannot be mixed without an approved normalization rule. Restated,
negative-base, missing, stale, or non-comparable facts are unavailable.

| Family | Eligibility / candidate grids | Sector boundary and shadow method | Status |
| --- | --- | --- | --- |
| `LONG_TERM_QUALITY_FAIR_VALUE` | Candidate: `{3,5}` annual comparable periods; quality metrics ROCE/ROE and CFO/PAT only for non-financials; valuation requires separately chosen method. | Banks/NBFCs/insurers use dedicated prudential metrics; replay compares evidence availability and milestone completion, not return promises. | `RESEARCH_SHADOW_V1_CANDIDATE`; valuation `PARAMETER_RESEARCH_REQUIRED` |
| `LONG_TERM_FUNDAMENTAL_COMPOUNDER` | Candidate growth consistency: positive revenue/PAT observations in `{3/3,4/5,5/5}` annual periods, with same scope/currency and zero-base unavailable. | Non-financial only until bank/NBFC/insurer metric contracts exist; shadow tracks revisions and future filing milestones. | `RESEARCH_SHADOW_V1_CANDIDATE` |
| `LONG_TERM_FUNDAMENTAL_INFLECTION` | Candidate comparison: current TTM/annual metric versus `{1,2}` prior comparable periods plus `{1,2}` confirmations; no one-period claim. | Requires restatement and exceptional-item taxonomy; shadow evaluates persistence of later reported facts. | `RESEARCH_SHADOW_V1_CANDIDATE`; `MORE_PIT_HISTORY_REQUIRED` |
| `LONG_TERM_POLICY_TRANSMISSION` | Exact stage chain: announcement → legal/rule → funding → tender/order → verified capacity → execution → revenue → cash; no stage skipping. | Direct/supplier/indirect/narrative exposure retained exactly; shadow measures stage completion, not price. | `PARAMETER_RESEARCH_REQUIRED`; `DERIVED_READ_ONLY_METRIC_REQUIRED` |
| `LONG_TERM_ASYMMETRIC_EMERGING_COMPOUNDER` | Candidate only after approved growth, dilution, liquidity, governance and valuation-availability contracts. “Asymmetric” is uncertainty disclosure, not forecast. | Requires emerging-company survivorship controls and prospective holdout; no universal score. | `PARAMETER_RESEARCH_REQUIRED`; `MORE_PIT_HISTORY_REQUIRED` |

For every family: horizon, review cadence, milestone, deterioration,
invalidation, conflict, and stale state remain unavailable until the selected
grid passes PIT calibration. Rule 46 remains price context only.

## 7. Event/Catalyst and Market-Red parameter proposal

| Family / field | Exact candidate definition | Status / evidence gate |
| --- | --- | --- |
| Event taxonomy/source | Exact `EventType`, primary source type in `{OFFICIAL, OFFICIAL_PRIMARY, GOVERNMENT, REGULATOR, EXCHANGE}`, verified exact exposure, and typed adverse/positive polarity from upstream. | `PARAMETER_RESEARCH_REQUIRED`: upstream polarity/family classifier absent. |
| Novelty/dedup/correction | Key `(canonical_event_id,evidence_version_id,evidence_fingerprint)`; correction/supersession requires explicit lineage link; input order irrelevant. | `IMPLEMENTED_PARTIALLY`; immutable event data reusable. |
| Event materiality/confirmation | Candidate only `HIGH/CRITICAL`; one verified primary source; secondary contextual only; conflict wins. | `RESEARCH_SHADOW_V1_CANDIDATE`; 13 retained critical/high observations are insufficient for promotion. |
| Event freshness/reaction | `received_at` and `available_at <= as_of`; no duration; price reaction/priced-in remains unavailable until a versioned event window and benchmark method are calibrated. | `PARAMETER_RESEARCH_REQUIRED` |
| Legal-risk veto | Exact primary category retained; only review/block output; never legal conclusion or SELL. | `REGULATORY_BOUNDARY` |
| Market benchmark | Explicit Nifty 50 and Nifty 500 completed-session returns; sector benchmark must be exact mapped index. | `RESEARCH_SHADOW_V1_CANDIDATE`; `REUSABLE_UNCHANGED` data |
| Weak market | Candidate grid: both benchmarks return below `{0%,-1%,-2%,-3%}` over `{1,5,20}` sessions plus breadth candidate `{<50%,<40%,<30%}`. | `RESEARCH_SHADOW_V1_CANDIDATE`; breadth parity missing. |
| Resilience | `stock_return(window) - benchmark_return(window)`; candidate percentile `{70,80,90}` within eligible PIT peer universe. | `RESEARCH_SHADOW_V1_CANDIDATE`; Indian calibration required. |
| Sector/liquidity/delivery | Candidate sector excess return non-negative; liquidity grids use `{20,60}`-session ADT and official delivery only when unit/coverage parity exists. | `PARAMETER_RESEARCH_REQUIRED`; delivery parity incomplete. |
| Beta/gap/false resilience | Beta uses OLS stock/benchmark returns over `{60,120,252}` completed sessions; gap/news days excluded until linked-event policy exists. | `RESEARCH_SHADOW_V1_CANDIDATE`; no activation. |
| Persistence/expiry/invalidation | Candidate persistence `{1,3,5}` weak sessions; no expiry duration; invalidate when benchmark condition ends, data becomes unavailable/conflicted, or relative metric fails selected grid. | `RESEARCH_SHADOW_V1_CANDIDATE`; PIT replay required. |

## 8. Parameter register and calibration plan

Every number above is either `REGULATORY_BOUNDARY`,
`RESEARCH_SHADOW_V1_CANDIDATE`, or `PARAMETER_RESEARCH_REQUIRED`; none is an
active investment threshold. Each candidate must record policy version,
canonical source IDs/fingerprints, scope, units, as-of, lookback, negative/
zero-base disposition, conflict state, and unavailable reason.

Calibration protocol: freeze a chronological Indian-equity sample; split
research/validation/holdout without overlap; replay only information available
at each `as_of`; test every grid point by sector and market regime; retain
coverage, unavailable rate, revision sensitivity, event duplication, and
false-resilience diagnostics; then prospectively shadow the frozen candidate.
Do not select a grid by maximum historical return. Promotion requires adequate
PIT coverage, stable sensitivity across holdout/regime/sector, documented
false-positive and false-negative review, and explicit human approval.

## 9. Remaining approval decisions

1. Select or reject the proposed candidate grids after Indian PIT calibration.
2. Approve upstream adverse-polarity/legal-family and financial-sector data
   contracts before broad Sell/Risk or Event/Catalyst implementation.
3. Approve valuation, portfolio bucket, cost/tax/slippage, and concentration
   contracts before Profit-Harvesting or Rotation comparison implementation.
4. Approve sector-specific bank/NBFC/insurer metrics before Long-Term family
   eligibility.
5. Approve a durable breadth/delivery and event-reaction history before
   Market-Red or Event/Catalyst positive eligibility.

## Approval/resume statement

> Approve, reject, or amend the explicitly versioned research-shadow candidate
> grids and data contracts in `POST_V1_POLICY_RESEARCH_PACK.md` for the named
> policy family. Authorize only the selected isolated, deterministic,
> PIT-safe, Watch-only/non-executable evaluator after its required canonical
> data contract and calibration evidence are accepted. No persistence, API/UI,
> portfolio access or mutation, broker/order authority, BUY/SELL/ADD/TRIM/EXIT/
> ROTATE output, capital authorization, or performance claim is approved.
