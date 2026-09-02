# Post-V1 Strategy and Signal-Window Catalogue

**Status: `APPROVED_AS_PRODUCT_SCOPE / DOCUMENTATION_ONLY / STRATEGY_POLICIES_NOT_APPROVED / NOT_ACTIVE`.**

## Authority and status language

This is the canonical Post-V1 product catalogue for strategy and signal-window scope. It complements the [Post-V1 Product Architecture](POST_V1_PRODUCT_ARCHITECTURE.md) and the approved P1 `HSISignal` foundation proposal. It creates no strategy, registry, projection, persistence record, API, UI, provider, runtime job, score, setup, gate decision, or trade. HSI Core V1 remains the frozen implementation baseline.

`IMPLEMENTED` means only that a named Core V1 evidence, diagnostic, read model, or analytical component exists. It never means the product strategy is implemented. `POLICY_AVAILABLE` means only that the existing governed Pre-Breakout policy can be referenced through its canonical governance path; it does not make a product signal executable. `STRATEGY_UNAVAILABLE` means no approved product strategy contract resolves for that entry. `NOT_ACTIVE` means it cannot be activated by this document, an archetype, a Watch, a setup, a Decision Score, or Six Gates.

Detection, classification, actionability, setup sufficiency, Six-Gates evaluation, capital authorization, and any separately approved paper-trading evaluation are separate stages. No catalogue entry is a BUY, SELL, or ROTATE instruction. Six Gates remain evidence-only and cannot call a broker or place an order.

## One Brain and signal-window boundary

All windows consume the same canonical Brain: market data, evidence, news, macro, sector, governance, and, only where a separately approved read model permits it, portfolio state. They must not create another Brain, duplicate provider truth, or turn a product view into a source of truth.

| Window | Product question | Required boundary |
| --- | --- | --- |
| Event / catalyst | What new verified event may matter, and through what evidence chain? | Source reliability, PIT time, and explicit transmission policy. |
| Tactical | Is there a short-to-medium horizon research pattern worth watching? | Approved structure, freshness, session, liquidity, and setup policy. |
| Positional | Is there a multi-session opportunity context? | An archetype is not an entry, gate result, or capital authorization. |
| Investment | Is there a longer-horizon evidence-backed thesis context? | Product-specific financial/research sufficiency. |
| Sell / risk / profit | What invalidation, risk, or profit-protection evidence is present? | Governed analysis only; never an order instruction. |
| Rotation | Does a governed candidate compare with a comparable holding? | Consumes governed outputs; it is not another discovery Brain. |

Equity, IPO, and Mutual Fund intelligence may share canonical identity, PIT, lineage, and governance discipline. They require separate data contracts, quality rules, horizons, calculations, and sufficiency policies. A single equity score must never be reused blindly for IPO or Mutual Fund intelligence.

## External-Intelligence-First, Evidence-Gated

Financial news, business developments, exchange disclosures, government policy
and regulation, and geopolitical developments are HSI's primary continuous
change-detection layer. They are never its sole trade-authorisation layer.
External intelligence detects novel, potentially material change; canonical
market, financial, technical, reliability, governance, setup, Six-Gates, and
portfolio-comparison evidence retain their separately governed roles.

The source hierarchy follows the existing [Source Reliability]
(../SOURCE_RELIABILITY.md) and [Claim Model](../CLAIM_MODEL.md) boundaries:

1. exchange, regulator, government, and company primary sources come first;
2. reliable business and financial media is secondary research;
3. social sentiment, rumours, and GMP are low-reliability evidence. They may
   describe sentiment but cannot establish business truth, an official fact, or
   an action.

An eventual intake must be novelty/change-first: it detects a new, superseding,
contradictory, or materially changed eligible artifact rather than repeatedly
promoting unchanged coverage. It deduplicates exact and semantically equivalent
source events while retaining source provenance and contradiction/supersession
links. It must assess materiality, map exact company and sector exposure, and
retain macro/policy transmission rather than claiming a beneficiary from a
theme alone.

Where a strategy discusses market implications, it separately needs
priced-in/price-reaction evidence and an approved interpretation policy. An
event is not automatically unpriced, confirmed, or actionable because it is
recent. Freshness and staleness remain source- and strategy-specific;
future-dated, stale, conflicting, unidentified, or insufficient evidence fails
closed. Governance, legal, fraud, sanction, disclosure, and other negative-risk
evidence may veto or cap a future product classification under a separately
approved policy. Such a veto is evidence-gated and fail-closed; it is not an
automatic SELL, broker call, or portfolio mutation.

The existing evidence hierarchy remains strict:

`FACT → DATA → INTERPRETATION → INFERENCE`.

A lower layer cannot be silently promoted to a higher layer. Source event,
deduplication, exposure, materiality, price reaction, and veto lineage must be
available for inspection. No fixed numerical news weights are introduced here.
Strategy-specific weights require separately approved research and shadow
evidence.

### External-intelligence strategy-dependency matrix

The matrix defines evidence roles for future product strategies, not current
execution behavior. `Required` means the future strategy's contract must
specify it; `Eligible` means it can be used only under that future approved
contract; `—` means it is not a required role. A legal/governance veto always
requires exact, PIT-valid evidence and a separately approved policy.

| Strategy / window | Primary trigger | Thesis origin | Confirmation | Context | Continuous risk monitor | Veto / override evidence |
| --- | --- | --- | --- | --- | --- | --- |
| Event/Catalyst Intelligence | Required | Required | Required | Required | Required | Eligible |
| Pre-Breakout Compression | — | — | Eligible | Eligible | Eligible | Eligible |
| Breakout Retest/Supply Exhaustion | — | — | Eligible | Eligible | Eligible | Eligible |
| Capitulation Reversal | — | — | Eligible | Required | Eligible | Eligible |
| Tactical Breakout/Pullback | — | — | Eligible | Required | Eligible | Eligible |
| Positional Setups | — | Eligible | Eligible | Required | Eligible | Eligible |
| Market-Red Relative Resilience | — | — | Eligible | Required | Eligible | Eligible |
| Post-Listing Expectation Dislocation | Required | Required | Required | Required | Required | Eligible |
| Long-Term Quality at Fair Value | Eligible | Required | Required | Required | Required | Eligible |
| Long-Term Fundamental Compounder | Eligible | Required | Required | Required | Required | Eligible |
| Long-Term Fundamental Inflection | Eligible | Required | Required | Required | Required | Eligible |
| Long-Term Policy Transmission | Required | Required | Required | Required | Required | Eligible |
| Long-Term Asymmetric Emerging Compounder | Eligible | Required | Required | Required | Required | Eligible |
| Sell/Risk Alerts | Eligible | — | Required | Required | Required | Required |
| Profit Harvesting | — | — | Eligible | Required | Required | Eligible |
| Fast Portfolio Rotation | — | — | Eligible | Required | Required | Eligible |

## Common contract and fail-closed rule

Every future strategy must retain exact canonical identity, source Watch/archetype and as-of lineage, policy/version references, evidence availability, freshness, and blockers. It fails closed when inputs are absent, stale, ambiguous, not PIT-valid, not approved, or not reproducible.

A future product output is descriptive and versioned. Until a separately approved policy and implementation exist, strategy resolution is `STRATEGY_UNAVAILABLE` and activation is `NOT_ACTIVE`. Within P1, any output is unconditionally `WATCH_ONLY / NON_EXECUTABLE`; it has no entry, stop, target, quantity, sizing, allocation, or trade instruction. The existing canonical signal lifecycle is a Core V1 analytical record and must not be silently reclassified as this future consumer catalogue.

## Catalogue

Each entry defines its identifier, objective/horizon, required evidence, prohibited inference, future signal output and setup/Six-Gates dependency, bucket/relevance, lifecycle/fail-closed conditions, and current state.

### `EVENT_CATALYST_INTELLIGENCE`

- **Objective / horizon:** expose company announcements, earnings, policy, regulation, geopolitical developments, and macro transmission as time-bounded research context; horizon is unavailable unless an approved event policy supplies it.
- **Required evidence:** attributable timestamped primary or assessed-source evidence, exact company/sector/economy identity, PIT-valid lineage, source reliability, and an explicit transmission chain where impact is discussed.
- **Prohibited inference:** a headline, policy announcement, or narrative does not prove company revenue, earnings, price direction, or investability.
- **Output / dependency:** future descriptive event/catalyst Watch; it has no setup or Six-Gates result without a separate approved strategy.
- **Bucket / lifecycle / fail-closed:** no portfolio relevance is inferred; source freshness controls lifecycle. Unidentified, unverified, future-dated, stale, or untraceable evidence fails closed.
- **Status:** catalyst and external-intelligence evidence are `IMPLEMENTED`; product strategy is `STRATEGY_UNAVAILABLE / NOT_ACTIVE`.

Policy transmission must retain this chain:

`announcement → legal/funding implementation → tender/orders → company eligibility/capacity → execution → revenue → cash flow`.

Each beneficiary claim is `DIRECT`, `SUPPLIER_ENABLER`, `INDIRECT`, or `NARRATIVE_ONLY`. A later stage cannot be inferred from an earlier one; `NARRATIVE_ONLY` is not an eligibility finding.

### `PRE_BREAKOUT_COMPRESSION`

- **Objective / horizon:** identify positional compression/base context before a confirmed breakout.
- **Required evidence:** governed Pre-Breakout structural assessment, canonical OHLCV/delivery lineage, approved policy reference, PIT-valid as-of time, and explicit missing-data/invalidation conditions.
- **Prohibited inference:** compression is not a breakout, entry, target, expected return, or institutional-demand fact.
- **Output / dependency:** future Watch-only Pre-Breakout projection may reference the existing approved policy; setup and Six Gates remain separately governed.
- **Bucket / lifecycle / fail-closed:** positional bucket only when separately governed; source lifecycle controls freshness. Unavailable setup, policy mismatch, stale data, or incomplete structure fails closed.
- **Status:** governed Pre-Breakout evidence/setup is `IMPLEMENTED`; policy is `POLICY_AVAILABLE`; catalogue activation is `NOT_ACTIVE`.

Pre-breakout volume contraction is distinct from both a post-breakout low-volume retest and high-volume capitulation. These terms are never interchangeable.

### `BREAKOUT_RETEST_SUPPLY_EXHAUSTION`

- **Objective / horizon:** research a post-breakout retest whose structure and volume may be consistent with supply exhaustion.
- **Required evidence:** approved prior-breakout, retest, low-volume, liquidity, and PIT-valid price/volume definitions.
- **Prohibited inference:** low volume alone does not prove supply exhaustion, support, renewed demand, or a valid entry.
- **Output / dependency:** future tactical/positional Watch; a separate setup policy is required before any setup or Six-Gates dependency.
- **Bucket / lifecycle / fail-closed:** tactical or positional only under its policy; ambiguous breakout/retest identity or stale sessions fail closed.
- **Status:** supporting technical evidence is partial; `STRATEGY_UNAVAILABLE / NOT_ACTIVE`.

### `CAPITULATION_REVERSAL`

- **Objective / horizon:** research a potential downside-dislocation reversal after a defined high-volume capitulation event.
- **Required evidence:** approved capitulation/response policy, high-volume price-event facts, liquidity, market/sector context, and PIT lineage.
- **Prohibited inference:** high volume, a sharp decline, or one rebound does not prove a durable bottom or reversal.
- **Output / dependency:** future Watch-only tactical/reversal classification; setup and Six Gates require independent policies.
- **Bucket / lifecycle / fail-closed:** tactical or satellite only when separately governed; missing confirmation, quality, or event identity fails closed.
- **Status:** market-dislocation/extremes evidence is `IMPLEMENTED`; `STRATEGY_UNAVAILABLE / NOT_ACTIVE`.

### `TACTICAL_BREAKOUT_PULLBACK`

- **Objective / horizon:** research short-to-medium horizon breakout or pullback contexts with approved structure and risk semantics.
- **Required evidence:** approved tactical pattern, session/freshness, liquidity, canonical price/volume, market/sector context, and explicit invalidation semantics.
- **Prohibited inference:** momentum, relative strength, or a Watch does not establish an executable tactical trade.
- **Output / dependency:** future tactical Watch; separately approved setup then independent Six-Gates evaluation are required.
- **Bucket / lifecycle / fail-closed:** tactical bucket only unless a higher cross-bucket policy permits comparison; absent structure or stale sessions fail closed.
- **Status:** technical/relative-strength components are `IMPLEMENTED`; `STRATEGY_UNAVAILABLE / NOT_ACTIVE`.

### `POSITIONAL_SETUP`

- **Objective / horizon:** organize multi-session structural opportunity contexts without treating an archetype as a trade.
- **Required evidence:** approved positional definition, canonical technical/market/sector facts, PIT lineage, and explicit setup sufficiency.
- **Prohibited inference:** a candidate setup, score, or archetype is not capital authorization.
- **Output / dependency:** future positional Watch; a complete governed setup and independent Six Gates are required before later analytical eligibility.
- **Bucket / lifecycle / fail-closed:** positional only; incomplete, stale, or policy-unapproved structure fails closed.
- **Status:** the Pre-Breakout setup path is an implemented instance; all other positional strategies are `STRATEGY_UNAVAILABLE / NOT_ACTIVE`.

### `MARKET_RED_RELATIVE_RESILIENCE`

- **Objective / horizon:** identify research candidates retaining relative resilience during a defined adverse market context.
- **Required evidence:** approved market-red definition, synchronized stock/benchmark sessions, relative-strength lineage, liquidity, and PIT controls.
- **Prohibited inference:** historical relative performance does not prove institutional sponsorship, future outperformance, or downside protection.
- **Output / dependency:** future Watch-only resilience classification; no setup or Six-Gates result is implied.
- **Bucket / lifecycle / fail-closed:** may inform any separately approved window; missing benchmark or market-context evidence fails closed.
- **Status:** relative-strength calculation is `IMPLEMENTED`; `STRATEGY_UNAVAILABLE / NOT_ACTIVE`.

### `POST_LISTING_EXPECTATION_DISLOCATION`

- **Objective / horizon:** research a post-listing divergence between verifiable official listing/fundamental evidence and prior expectation context.
- **Required evidence:** official issuer/exchange listing facts, exact security identity, approved IPO/listing contract, PIT-valid financial/market evidence, and reliability-scored secondary sentiment if used.
- **Prohibited inference:** GMP is unofficial, low-reliability secondary sentiment evidence only. It is not an official price, valuation, demand, allocation, or performance fact and cannot establish dislocation alone.
- **Output / dependency:** future Watch-only IPO/product research context; no equity setup or Six-Gates dependency is inherited.
- **Bucket / lifecycle / fail-closed:** distinct IPO product/bucket policy required; unverified GMP, missing official source, or mixed identity fails closed.
- **Status:** primary-market inputs are future-feed boundaries; `STRATEGY_UNAVAILABLE / NOT_ACTIVE`.

### `LONG_TERM_QUALITY_AT_FAIR_VALUE`

- **Objective / horizon:** research durable quality and valuation context at a separately approved fair-value horizon.
- **Required evidence:** authoritative financial facts, scope/period comparability, quality criteria, approved valuation method and inputs, and PIT/revision lineage.
- **Prohibited inference:** a quality label or valuation multiple does not prove fair value, margin of safety, or a purchase decision.
- **Output / dependency:** future investment Watch; no tactical setup or Six-Gates shortcut.
- **Bucket / lifecycle / fail-closed:** Core or Emerging investment research only under approved bucket definitions; missing method, comparability, or fact sufficiency fails closed.
- **Status:** financial evidence is `IMPLEMENTED`; `STRATEGY_UNAVAILABLE / NOT_ACTIVE`.

### `LONG_TERM_FUNDAMENTAL_COMPOUNDER`

- **Objective / horizon:** research repeatable, evidence-backed long-horizon compounding characteristics.
- **Required evidence:** multi-period financial facts, earnings/cash-flow quality, governance/reliability context, and approved growth/quality policy.
- **Prohibited inference:** historical growth does not guarantee compounding, valuation suitability, or future returns.
- **Output / dependency:** future investment Watch; no executable setup or gate authorization by itself.
- **Bucket / lifecycle / fail-closed:** Core or Emerging research only under a portfolio policy; insufficient history, unstable facts, or unavailable policy fails closed.
- **Status:** financial/reliability evidence is `IMPLEMENTED`; `STRATEGY_UNAVAILABLE / NOT_ACTIVE`.

### `LONG_TERM_FUNDAMENTAL_INFLECTION`

- **Objective / horizon:** research a material financial trajectory change without equating it to an established compounder.
- **Required evidence:** PIT-valid multi-period facts, approved trajectory/materiality policies, earnings comparability, and explicit prior baseline.
- **Prohibited inference:** one improved result, margin change, or order does not prove sustained inflection or investability.
- **Output / dependency:** future investment Watch; no setup, Six-Gates result, or capital authorization.
- **Bucket / lifecycle / fail-closed:** Emerging/Satellite research only until separately governed otherwise; missing comparable periods or materiality policy fails closed.
- **Status:** inflection evidence/setup components are partial; `STRATEGY_UNAVAILABLE / NOT_ACTIVE`.

### `LONG_TERM_POLICY_TRANSMISSION`

- **Objective / horizon:** research long-horizon company implications after an evidence-backed policy transmission chain.
- **Required evidence:** complete staged policy chain, beneficiary typing, company eligibility/capacity evidence, financial linkage where claimed, and PIT-valid official/reliable sources.
- **Prohibited inference:** policy intent, theme, or narrative exposure cannot be promoted to revenue/cash-flow impact without later-stage evidence.
- **Output / dependency:** future investment Watch; it does not inherit setup or Six-Gates authorization.
- **Bucket / lifecycle / fail-closed:** Thematic/Emerging research only under approved policy; missing legal/funding, company linkage, or cash evidence fails closed for that claim.
- **Status:** policy/catalyst evidence is `IMPLEMENTED`; `STRATEGY_UNAVAILABLE / NOT_ACTIVE`.

### `LONG_TERM_ASYMMETRIC_EMERGING_COMPOUNDER`

- **Objective / horizon:** research a possible asymmetric Emerging/Satellite outcome under an explicit future policy.
- **Required evidence:** governed financial trajectory, quality, risk, valuation, liquidity, governance, and thesis-invalidation evidence.
- **Prohibited inference:** “multibagger” is only a possible asymmetric outcome, never a forecast, guarantee, or label that bypasses risk.
- **Output / dependency:** future Watch-only investment research; no sizing, allocation, setup, gate, or rotation instruction follows.
- **Bucket / lifecycle / fail-closed:** Emerging/Satellite only; insufficient evidence, liquidity/risk uncertainty, or absent asymmetry policy fails closed.
- **Status:** supporting evidence is partial; `STRATEGY_UNAVAILABLE / NOT_ACTIVE`.

### `SELL_RISK_ALERT`

- **Objective / horizon:** surface risk, invalidation, distribution, deterioration, or reliability context for review.
- **Required evidence:** approved risk/invalidation policy, canonical evidence, PIT lifecycle, and explicit fact/data/interpretation/inference separation.
- **Prohibited inference:** a drawdown, euphoria, risk Watch, or weak signal does not establish SELL, EXIT, or ROTATE.
- **Output / dependency:** future descriptive risk alert; existing sell-side runtime remains independently governed.
- **Bucket / lifecycle / fail-closed:** may read portfolio only through a separately approved boundary; stale or unsupported risk evidence fails closed to review/unavailable.
- **Status:** risk, thesis, and extremes evidence is `IMPLEMENTED`; `STRATEGY_UNAVAILABLE / NOT_ACTIVE`.

### `PROFIT_HARVESTING`

- **Objective / horizon:** research profit-protection or harvesting context separately from risk invalidation.
- **Required evidence:** approved profit policy, current forward risk/reward, structure, extremes context, and PIT-valid portfolio/evidence read model where authorized.
- **Prohibited inference:** gains, euphoria, or a target-looking price does not mandate a sale, trim, or rotation.
- **Output / dependency:** future descriptive profit context; no sell instruction, quantity, trade plan, or Six-Gates override.
- **Bucket / lifecycle / fail-closed:** only a future holding-management policy may establish relevance; incomplete forward economics or absent policy fails closed.
- **Status:** supporting analytical evidence is partial; `STRATEGY_UNAVAILABLE / NOT_ACTIVE`.

### `FAST_PORTFOLIO_ROTATION`

- **Objective / horizon:** research a time-sensitive opportunity-cost comparison between a governed candidate and a comparable existing holding.
- **Required evidence:** versioned rotation comparison, eligible candidate/holding evidence, exact hurdle, anti-churn/friction checks, current forward risk/reward, comparable bucket identity, and PIT lineage.
- **Prohibited inference:** a higher score, Watch, or archetype does not prove a rotation, sale, replacement, or deployment decision.
- **Output / dependency:** future descriptive rotation challenger consuming governed outputs; it is not another discovery Brain and cannot bypass setup, Six Gates, or rotation controls.
- **Bucket / lifecycle / fail-closed:** Core, Emerging/Satellite, Thematic, and Tactical buckets may not be compared interchangeably without a higher separately approved cross-bucket hurdle. Missing comparability, gate, friction, or bucket policy fails closed.
- **Status:** capital-rotation comparison is `IMPLEMENTED` analysis; product strategy is `STRATEGY_UNAVAILABLE / NOT_ACTIVE`.

## Capability-status matrix

Reusable Core V1 foundations remain implemented even when a consumer product
strategy is unavailable. In particular, operational external-evidence
infrastructure, Watch/archetype routing, relative-strength inputs, Market
Extremes evidence, and the portfolio rotation challenger/comparison framework
are not made unavailable by this product catalogue.

| Strategy / window | Reusable Core V1 capability / input | Underlying policy status | Post-V1 product-strategy status | Activation status |
| --- | --- | --- | --- | --- |
| `EVENT_CATALYST_INTELLIGENCE` | Operational external-evidence infrastructure; Watch/archetype routing; catalyst evidence | Core evidence governance implemented; no product strategy policy | `STRATEGY_UNAVAILABLE` | `NOT_ACTIVE` |
| `PRE_BREAKOUT_COMPRESSION` | Governed Pre-Breakout setup, Watch/archetype routing, OHLCV/delivery lineage | Existing governed Pre-Breakout policy `POLICY_AVAILABLE` | Internal P1 registry/projection implemented only as `WATCH_ONLY / NON_EXECUTABLE`; no consumer strategy | `NOT_CONSUMER_ACTIVE` |
| `BREAKOUT_RETEST_SUPPLY_EXHAUSTION` | Technical/volume inputs and Watch routing, partial | No approved strategy policy | `STRATEGY_UNAVAILABLE` | `NOT_ACTIVE` |
| `CAPITULATION_REVERSAL` | Market Extremes evidence, dislocation evidence, and Watch routing | No approved strategy policy | `STRATEGY_UNAVAILABLE` | `NOT_ACTIVE` |
| `TACTICAL_BREAKOUT_PULLBACK` | Technical and relative-strength inputs; Watch routing | No approved strategy policy | `STRATEGY_UNAVAILABLE` | `NOT_ACTIVE` |
| `POSITIONAL_SETUP` | Pre-Breakout setup instance; other components partial | Only existing Pre-Breakout policy available | Other product strategies `STRATEGY_UNAVAILABLE` | `NOT_ACTIVE` |
| `MARKET_RED_RELATIVE_RESILIENCE` | Relative-strength calculation and Watch routing | No approved strategy policy | `STRATEGY_UNAVAILABLE` | `NOT_ACTIVE` |
| `POST_LISTING_EXPECTATION_DISLOCATION` | Primary-market evidence boundary; canonical identity | No approved strategy policy | `STRATEGY_UNAVAILABLE` | `NOT_ACTIVE` |
| `LONG_TERM_QUALITY_AT_FAIR_VALUE` | Financial evidence and reliability inputs | No approved product strategy policy | `STRATEGY_UNAVAILABLE` | `NOT_ACTIVE` |
| `LONG_TERM_FUNDAMENTAL_COMPOUNDER` | Financial, earnings, and reliability inputs | No approved strategy policy | `STRATEGY_UNAVAILABLE` | `NOT_ACTIVE` |
| `LONG_TERM_FUNDAMENTAL_INFLECTION` | Fundamental-inflection inputs and Watch routing, partial | No approved strategy policy | `STRATEGY_UNAVAILABLE` | `NOT_ACTIVE` |
| `LONG_TERM_POLICY_TRANSMISSION` | Operational external intelligence; policy/catalyst evidence and Watch routing | No approved strategy policy | `STRATEGY_UNAVAILABLE` | `NOT_ACTIVE` |
| `LONG_TERM_ASYMMETRIC_EMERGING_COMPOUNDER` | Financial, risk, governance, and thesis inputs, partial | No approved strategy policy | `STRATEGY_UNAVAILABLE` | `NOT_ACTIVE` |
| `SELL_RISK_ALERT` | Risk, thesis invalidation, Market Extremes, and Watch routing | Existing risk evidence governance; no product strategy policy | `STRATEGY_UNAVAILABLE` | `NOT_ACTIVE` |
| `PROFIT_HARVESTING` | Forward risk/reward and Market Extremes inputs, partial | No approved strategy policy | `STRATEGY_UNAVAILABLE` | `NOT_ACTIVE` |
| `FAST_PORTFOLIO_ROTATION` | Portfolio rotation challenger/comparison framework, gates, friction and anti-churn lineage | Existing comparison governance; no product strategy policy | `STRATEGY_UNAVAILABLE` | `NOT_ACTIVE` |

## Methodological lineage

> Methodological lineage explains conceptual origin; it does not constitute empirical validation, endorsement, performance evidence or strategy activation.

| Catalogue concept | Conceptual consistency / methodological lineage | Boundary |
| --- | --- | --- |
| Quality at fair value and compounder research | Buffett/Munger, Fisher, and quality/fair-value investing | Not a copied method, formula, or endorsement. |
| Fundamental growth and inflection | Lynch-style growth; Driehaus-style earnings acceleration with price confirmation | Needs separate approved growth, valuation, and confirmation policies. |
| Pre-breakout, tactical breakout, resilience | O'Neil/Darvas breakout and institutional-demand principles; Livermore/Weinstein relative-strength and leadership principles | Relative strength is historical performance, not sponsorship or return proof. |
| Compression and retest structure | Minervini-style volatility contraction; Wyckoff price-volume/supply-demand principles | Existing Wyckoff work is a transparent approximation, not discretionary interpretation. |
| Capitulation, extremes, risk | Wyckoff price-volume concepts and Howard Marks-style cycle/risk thinking | Risk context is not automatic timing or a sell signal. |
| Policy transmission | Professional macro-to-sector-to-company transmission analysis | Claims must traverse the stated implementation/economics chain. |
| Thesis invalidation, rotation, and profit/risk review | HSI's evidence-supported thesis invalidation; portfolio opportunity-cost and risk-management principles | Existing rotation is analytical, versioned, comparable, and non-executable. |

These labels identify conceptual consistency where supportable by HSI documentation. They do not claim quotations, direct derivation, endorsement, empirical proof, or transferability of historical performance.

## Unresolved taxonomy and approval decisions

The following are future approval decisions, not gaps this document fills:

- typed product horizon/direction vocabulary for every window;
- strategy-specific data contracts, freshness/staleness rules, and lifecycle semantics;
- standalone policy IDs, versions, thresholds, validation, and shadow evidence for every unavailable strategy;
- a formal bucket taxonomy and exact higher cross-bucket rotation hurdle;
- IPO official-source coverage and permitted reliability-scored treatment of secondary sentiment;
- product-specific valuation, compounder, inflection, policy-transmission, profit-harvesting, and risk calculation contracts;
- consumer-facing Strategy Registry and product API/UI decisions.

Until those approvals and independently tested implementations exist, new strategies resolve fail-closed to `STRATEGY_UNAVAILABLE / NOT_ACTIVE`.

## Non-goals

This catalogue does not authorize automatic BUY, SELL, ROTATE, trim, broker authority, order placement, capital allocation, paper-trade creation, holdings or cash mutation, portfolio mutation, policy activation, or any change to frozen Core V1.
