from __future__ import annotations

from decimal import Decimal

from app.domain.models import EvidenceType
from app.registry.models import (
    BenchmarkDefinition, CatalystTiming, DataConfidencePolicy, DecisionScoreComponentDefinition,
    DiagnosticRuleDefinition, DiagnosticState, EvaluationMode, ExecutionGateDefinition,
    MissingDataPolicy, MissingDataTreatment, ResearchSourceTier, ScoringPolicy,
    SelfImprovementLifecycleDefinition,
)


DIAGNOSTIC_REGISTRY_VERSION = "diagnostic-registry-v1"
SCORING_POLICY_VERSION = "decision-score-policy-v1"
EXECUTION_GATE_REGISTRY_VERSION = "execution-gate-registry-v1"
RESEARCH_POLICY_VERSION = "research-policy-v1"
BENCHMARK_REGISTRY_VERSION = "benchmark-registry-v1"
SELF_IMPROVEMENT_GOVERNANCE_VERSION = "self-improvement-governance-v1"

_NAMES = (
    "Market Regime Classification", "Sector Index Health & Trend", "Sector Rotation Phase",
    "Primary Trend Direction — Weekly & Daily", "Weinstein Market Stage",
    "Relative Strength Rank vs Nifty 50, Sector Index & Peers", "Institutional / Smart Money Observable Proxies",
    "Liquidity Pool Mapping — Buy-side & Sell-side", "Wyckoff Phase Classification",
    "Classical Market Structure — Dow HH/HL vs LH/LL", "Volume Behavior & Relative Volume (RVOL)",
    "Ichimoku Cloud Structure", "Chikou Span Confirmation",
    "Multi-Timeframe Alignment — Weekly, Daily, 4H/1H, 15M where data permits",
    "Business Model & Moat Sustainability", "Five-Year Financial Trend — Revenue, EBITDA, PAT, EPS CAGR",
    "Return Ratios — ROCE and ROE", "Operating Cash Flow & Free Cash Flow Health",
    "Balance Sheet Leverage — Debt/Equity, Net Debt, Interest Coverage",
    "Working Capital & Cash Conversion Cycle", "Ownership Structure — Promoter Holding & Pledge",
    "Institutional Holding Shifts — DII/MF/FII", "Corporate Governance & Auditor Cleanliness",
    "Earnings Acceleration Status — Organic vs One-Off", "Latest Quarterly Results — YoY & QoQ",
    "Operating Margin & Gross Margin Trajectory", "Order Book & Book-to-Bill Ratio",
    "Management Execution Track Record — Guidance vs Delivery",
    "Valuation Multiples — P/E, Forward P/E, PEG, EV/EBITDA, P/B", "Fundamental Catalysts — High/Medium/Low Impact",
    "Comprehensive Risk Engine — Probability × Impact", "Trading Thesis", "Investment Thesis",
    "Bull / Base / Bear Probability Scenarios", "VWAP & Value Area Acceptance", "OBV Trend & Divergence",
    "Base Pattern Quality — VCP, Cup & Handle, Flat Base, Ascending Base", "Pullback Quality & Support Confluence",
    "Technical Indicator Layer — RSI, ADX, ATR", "Aggressive Entry Level", "Confirmation Entry Level",
    "Pullback / Retest Entry Level", "Structural Stop-Loss", "Target Hierarchy — T1, T2, Extended Target",
    "Risk/Reward Calculation — minimum structural R:R normally 1:2", "Exact Thesis Invalidation Conditions",
    "Retail / Public Sentiment Score — 0 to 100", "Crowd Positioning Tier", "Crowd Data Confidence",
    "Institutional Accumulation vs Distribution Proxy", "Major Stop-Loss Cluster Mapping",
    "Liquidity Event Detection — Sweep, Absorption, Breakout Acceptance", "Bull Trap Identification",
    "Bear Trap Identification", "Crowd Trap Probability", "Price vs Crowd Sentiment Divergence",
    "Post-News Price Reaction — Absorption vs Sell-the-News", "Volume Climax & Distribution Signs",
    "Contrarian Ichimoku Confluence", "Contrarian Signal Quality — Strong / Moderate / Weak",
    "Contrarian Action Verdict — Buy / Sell / Hold / Avoid / Wait",
)

_DETERMINISTIC = frozenset({1, 2, 4, 6, 10, 11, 12, 13, 14, 16, 17, 18, 19, 20, 25, 26, 29, 35, 36, 39, 43, 44, 45})
_INTERPRETIVE = frozenset({15, 23, 28, 30, 32, 33, 34, 46, 48, 55, 60, 61})


def _category(rule_id: int) -> str:
    if rule_id <= 14:
        return "market_and_technical"
    if rule_id <= 34:
        return "fundamental_and_thesis"
    if rule_id <= 46:
        return "technical_execution_and_risk"
    return "crowd_vs_smart_money_contrarian"


def _mode(rule_id: int) -> EvaluationMode:
    if rule_id in _DETERMINISTIC:
        return EvaluationMode.DETERMINISTIC
    if rule_id in _INTERPRETIVE:
        return EvaluationMode.INTERPRETIVE
    return EvaluationMode.HYBRID


def _allowed_evidence(mode: EvaluationMode) -> tuple[EvidenceType, ...]:
    if mode is EvaluationMode.DETERMINISTIC:
        return (EvidenceType.FACT, EvidenceType.DATA, EvidenceType.INTERPRETATION)
    if mode is EvaluationMode.INTERPRETIVE:
        return (EvidenceType.FACT, EvidenceType.DATA, EvidenceType.INTERPRETATION, EvidenceType.INFERENCE)
    return (EvidenceType.DATA, EvidenceType.INTERPRETATION, EvidenceType.INFERENCE)


def _required_inputs(rule_id: int) -> tuple[str, ...]:
    base = ("strategy version", "validated as-of snapshot")
    if rule_id <= 14 or rule_id >= 35:
        return base + ("validated market observations",)
    return base + ("validated source filings or disclosures",)


DIAGNOSTIC_RULES = tuple(
    DiagnosticRuleDefinition(
        rule_id=rule_id,
        canonical_name=name,
        category=_category(rule_id),
        purpose=f"Canonical diagnostic checkpoint for {name}.",
        required_inputs=_required_inputs(rule_id),
        optional_inputs=("corroborating evidence", "approved provider-specific metadata"),
        output_type="auditable diagnostic result",
        possible_statuses=(DiagnosticState.PASS, DiagnosticState.FAIL, DiagnosticState.NEUTRAL,
                           DiagnosticState.INSUFFICIENT_DATA, DiagnosticState.NOT_APPLICABLE,
                           DiagnosticState.UNVERIFIED),
        dependencies=(() if rule_id in {1, 15, 47} else (1,)),
        minimum_data_requirements="Rule-specific requirements must be met without fabricating or filling inputs.",
        missing_data_behavior="Return INSUFFICIENT_DATA or UNVERIFIED; never convert missing evidence to NEUTRAL, PASS, or a positive score.",
        confidence_policy="Retain source reliability, freshness, completeness, validation, corroboration, and input coverage separately from the Decision Score.",
        evaluation_mode=_mode(rule_id),
        allowed_evidence_types=_allowed_evidence(_mode(rule_id)),
        calculation_version=DIAGNOSTIC_REGISTRY_VERSION,
        notes_limitations="Definition only in Phase 4A; no evaluator or production formula is implemented.",
    )
    for rule_id, name in enumerate(_NAMES, start=1)
)


DECISION_SCORE_COMPONENTS = (
    DecisionScoreComponentDefinition("earnings_acceleration", "Earnings Acceleration", Decimal("15")),
    DecisionScoreComponentDefinition("market_regime", "Market Regime", Decimal("10")),
    DecisionScoreComponentDefinition("sector_rotation", "Sector Rotation", Decimal("10")),
    DecisionScoreComponentDefinition("smart_money_evidence", "Smart Money Evidence", Decimal("10")),
    DecisionScoreComponentDefinition("relative_strength", "Relative Strength", Decimal("10")),
    DecisionScoreComponentDefinition("price_structure", "Price Structure", Decimal("10")),
    DecisionScoreComponentDefinition("volume_obv_vwap", "Volume / OBV / VWAP", Decimal("10")),
    DecisionScoreComponentDefinition("ichimoku_mtf", "Ichimoku & MTF", Decimal("10")),
    DecisionScoreComponentDefinition("valuation_risk_reward", "Valuation & Risk/Reward", Decimal("10")),
    DecisionScoreComponentDefinition("liquidity_smc_traps", "Liquidity & SMC Traps", Decimal("5")),
)

DATA_CONFIDENCE_POLICY = DataConfidencePolicy(
    version="data-confidence-policy-v1",
    factors=("source reliability", "freshness", "completeness", "validation status", "corroboration", "input coverage"),
)
MISSING_DATA_POLICY = MissingDataPolicy(
    version="missing-data-policy-v1",
    treatments=(MissingDataTreatment.NO_SILENT_WEIGHT_RENORMALIZATION,
                MissingDataTreatment.SURFACE_MISSING_COMPONENT,
                MissingDataTreatment.REDUCE_ELIGIBILITY_AND_CONFIDENCE),
)
SCORING_POLICY = ScoringPolicy(SCORING_POLICY_VERSION, DECISION_SCORE_COMPONENTS, DATA_CONFIDENCE_POLICY, MISSING_DATA_POLICY)


EXECUTION_GATES = (
    ExecutionGateDefinition(1, "Net Friction & Tax Hurdle", "Require a justified incremental opportunity after applicable costs and friction.",
                            ("candidate score", "weakest holding score", "current friction/tax assumptions"),
                            "Candidate normally exceeds weakest holding by +0.70 to +1.00 Decision Score points and justifies applicable costs, slippage, taxes, and friction.",
                            "REQUIRES_STRATEGY_VERSIONED_EXACT_VALUES", "INSUFFICIENT_DATA blocks eligibility.", EXECUTION_GATE_REGISTRY_VERSION),
    ExecutionGateDefinition(2, "Capital Velocity / Time Stop", "Review capital tied in non-expanding consolidations.",
                            ("holding duration", "ATR expansion", "Decision Score"),
                            "Approximately 10–15 trading sessions without meaningful >1 ATR expansion may receive a -0.5 Decision Score penalty and rotation-priority review.",
                            "REQUIRES_STRATEGY_VERSIONED_EXACT_VALUES", "INSUFFICIENT_DATA blocks eligibility.", EXECUTION_GATE_REGISTRY_VERSION),
    ExecutionGateDefinition(3, "Surveillance & Circuit Filter", "Block candidates with current material surveillance/circuit restrictions.",
                            ("fresh authoritative ASM/GSM/surveillance data", "current circuit restrictions"),
                            "Intended disqualification includes ASM Stage 2+ / GSM and restrictive 5% circuits, subject only to an approved verified exception policy.",
                            "REQUIRES_FRESH_AUTHORITATIVE_DATA", "INSUFFICIENT_DATA blocks eligibility.", EXECUTION_GATE_REGISTRY_VERSION),
    ExecutionGateDefinition(4, "Tranche Scaling & De-Risking", "Version position staging and profit-protection intent.",
                            ("entry plan", "target hierarchy", "liquidity/structure conditions"),
                            "Intended policy: 50% initial tranche; 33–50% partial profit around T1; remaining stop may move to breakeven subject to structure/liquidity.",
                            "REQUIRES_STRATEGY_VERSIONED_EXACT_VALUES", "INSUFFICIENT_DATA blocks eligibility.", EXECUTION_GATE_REGISTRY_VERSION),
    ExecutionGateDefinition(5, "Portfolio Heat & Factor Cap", "Constrain aggregate, position, and sector risk.",
                            ("portfolio heat", "single-stock allocation", "sector exposure"),
                            "Intended limits: heat <=6%, single-stock <=25–30%, sector <=35%; ranges require resolution before production eligibility.",
                            "REQUIRES_STRATEGY_VERSIONED_EXACT_VALUES", "INSUFFICIENT_DATA blocks eligibility.", EXECUTION_GATE_REGISTRY_VERSION),
    ExecutionGateDefinition(6, "Five-Trading-Day Pre-Earnings Blackout", "Prevent fresh entries immediately before scheduled earnings.",
                            ("verified scheduled earnings date", "trading calendar", "entry state"),
                            "No fresh entries within five trading sessions before scheduled earnings; existing positions may still be risk-managed.",
                            "REQUIRES_FRESH_EARNINGS_CALENDAR", "INSUFFICIENT_DATA blocks eligibility.", EXECUTION_GATE_REGISTRY_VERSION),
)


CATALYST_TIMING_CATEGORIES = (CatalystTiming.IMMEDIATE, CatalystTiming.NEAR_TERM, CatalystTiming.MEDIUM_TERM)
RESEARCH_SOURCE_HIERARCHY = (
    ResearchSourceTier(1, "primary_and_regulatory", ("NSE/BSE/regulatory filings", "company results/disclosures", "investor presentations", "earnings-call material"), "May support FACT when directly attributable."),
    ResearchSourceTier(2, "high_quality_financial_news", ("high-quality financial/news sources",), "May support DATA or corroborated INTERPRETATION."),
    ResearchSourceTier(3, "social_and_community", ("social/community data",), "Sentiment evidence only; cannot override verified primary filings."),
)
RESEARCH_ANALYSIS_FIELDS = ("FACT", "MATERIALITY", "DURATION", "EARNINGS_IMPACT", "CATALYST_TIMING", "EXPECTATION_VS_REALITY", "POST_NEWS_PRICE_REACTION")

BENCHMARKS = (
    BenchmarkDefinition(1, "Nifty 50 buy-and-hold", "Broad-market buy-and-hold baseline"),
    BenchmarkDefinition(2, "Nifty 500", "Broad-market universe benchmark"),
    BenchmarkDefinition(3, "Relevant sector indices", "Sector-relative comparison"),
    BenchmarkDefinition(4, "Simple momentum strategy", "Simple systematic baseline"),
    BenchmarkDefinition(5, "Simple moving-average strategy", "Simple technical baseline"),
    BenchmarkDefinition(6, "Randomized stock selection", "Chance-selection control"),
    BenchmarkDefinition(7, "Previous NSE Stock Manager strategy version", "Version-over-version comparison"),
    BenchmarkDefinition(8, "Trader-like baseline", "Human-style baseline requiring explicit future definition"),
)
BENCHMARK_METRICS = ("total return", "CAGR", "max drawdown", "volatility", "Sharpe", "Sortino", "expectancy", "profit factor", "win rate", "average R multiple", "turnover", "transaction/friction costs", "capital efficiency", "rotation efficiency", "market-regime performance", "sector performance", "out-of-sample performance")

SELF_IMPROVEMENT_LIFECYCLE = SelfImprovementLifecycleDefinition(
    stages=("Observation", "hypothesis", "experiment", "historical backtest", "walk-forward validation", "out-of-sample validation", "forward/paper validation", "review", "strategy promotion or rejection"),
    required_experiment_fields=("experiment ID", "parent strategy", "hypothesis", "proposed change", "reason", "affected diagnostics/weights/gates", "training sample", "validation sample", "sample size", "results", "comparison vs baseline", "approval/rejection", "new strategy version if promoted"),
    active_rule_change_policy="The Self-Improvement Engine must never silently change ACTIVE rules.",
)


def get_diagnostic_rule(rule_id: int) -> DiagnosticRuleDefinition:
    return DIAGNOSTIC_RULES[rule_id - 1]
