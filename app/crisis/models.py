"""Immutable crisis/dislocation contracts; they never place or alter trades."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping


class CrisisState(StrEnum):
    NORMAL = "NORMAL"
    ELEVATED_RISK = "ELEVATED_RISK"
    STRESS = "STRESS"
    CRISIS = "CRISIS"
    STABILIZING = "STABILIZING"
    RECOVERY = "RECOVERY"


class CrisisFactor(StrEnum):
    INDEX_PRICE_VELOCITY = "INDEX_PRICE_VELOCITY"
    INTRADAY_DRAWDOWN = "INTRADAY_DRAWDOWN"
    GAP_MAGNITUDE = "GAP_MAGNITUDE"
    ATR_EXPANSION = "ATR_EXPANSION"
    REALIZED_VOLATILITY = "REALIZED_VOLATILITY"
    INDIA_VIX = "INDIA_VIX"
    MARKET_BREADTH = "MARKET_BREADTH"
    SECTOR_BREADTH = "SECTOR_BREADTH"
    CROSS_SECTOR_CORRELATION = "CROSS_SECTOR_CORRELATION"
    ABNORMAL_VOLUME = "ABNORMAL_VOLUME"
    LIQUIDITY_DETERIORATION = "LIQUIDITY_DETERIORATION"
    CIRCUIT_OR_MARKET_STATUS = "CIRCUIT_OR_MARKET_STATUS"
    PORTFOLIO_DRAWDOWN = "PORTFOLIO_DRAWDOWN"
    PORTFOLIO_CONCENTRATION = "PORTFOLIO_CONCENTRATION"
    DATA_FRESHNESS = "DATA_FRESHNESS"
    EXCHANGE_STATUS = "EXCHANGE_STATUS"
    SELLING_VELOCITY_SLOWING = "SELLING_VELOCITY_SLOWING"
    BREADTH_IMPROVING = "BREADTH_IMPROVING"
    VOLATILITY_NORMALIZING = "VOLATILITY_NORMALIZING"
    FEWER_NEW_LOWS = "FEWER_NEW_LOWS"
    INDEX_RECLAIM = "INDEX_RECLAIM"
    LIQUIDITY_NORMALIZING = "LIQUIDITY_NORMALIZING"
    RECOVERY_LEADERSHIP = "RECOVERY_LEADERSHIP"


class MarketStatus(StrEnum):
    TRADING_NORMAL = "TRADING_NORMAL"
    HALTED = "HALTED"
    CIRCUIT_RESTRICTED = "CIRCUIT_RESTRICTED"
    FEED_DEGRADED = "FEED_DEGRADED"
    UNKNOWN = "UNKNOWN"


class EntryRestrictionLevel(StrEnum):
    NONE = "NONE"
    HIGHER_QUALITY = "HIGHER_QUALITY"
    RESTRICTED = "RESTRICTED"
    DISABLED = "DISABLED"


class StopHandlingMode(StrEnum):
    NORMAL = "NORMAL"
    GAP_AWARE_REVIEW = "GAP_AWARE_REVIEW"
    EXECUTION_UNCERTAIN = "EXECUTION_UNCERTAIN"


class SlippageModelMode(StrEnum):
    NORMAL = "NORMAL"
    ELEVATED = "ELEVATED"
    CRISIS = "CRISIS"


class CrisisOpportunityCategory(StrEnum):
    EXCEPTIONAL_RELATIVE_STRENGTH = "EXCEPTIONAL_RELATIVE_STRENGTH"
    MAJOR_STRUCTURE_SURVIVOR = "MAJOR_STRUCTURE_SURVIVOR"
    LOW_DRAWDOWN_LEADER = "LOW_DRAWDOWN_LEADER"
    FORCED_SELLING_CANDIDATE = "FORCED_SELLING_CANDIDATE"
    CAPITULATION_CANDIDATE = "CAPITULATION_CANDIDATE"
    ABNORMAL_VOLUME_REVERSAL = "ABNORMAL_VOLUME_REVERSAL"
    EMERGING_SECTOR_LEADER = "EMERGING_SECTOR_LEADER"
    RECOVERY_LEADER = "RECOVERY_LEADER"
    POST_CRASH_BASE_RECLAIM = "POST_CRASH_BASE_RECLAIM"


class OpportunityDisposition(StrEnum):
    WATCH = "WATCH"
    PRIORITY_RESEARCH = "PRIORITY_RESEARCH"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"


class PortfolioHoldingAction(StrEnum):
    HOLD = "HOLD"
    REDUCE = "REDUCE"
    EXIT = "EXIT"
    TRAIL = "TRAIL"
    REVIEW = "REVIEW"
    ROTATE = "ROTATE"
    UNABLE_TO_EXECUTE_CLEANLY = "UNABLE_TO_EXECUTE_CLEANLY"


class CashRecommendationState(StrEnum):
    NORMAL_ALLOCATION = "NORMAL_ALLOCATION"
    DEFENSIVE_ALLOCATION = "DEFENSIVE_ALLOCATION"
    PRESERVED_OPTIONALITY = "PRESERVED_OPTIONALITY"
    DELIBERATE_NO_TRADE = "DELIBERATE_NO_TRADE"


class CrisisDashboardLabel(StrEnum):
    NORMAL = "NORMAL"
    CAUTION = "CAUTION"
    DEFENSIVE = "DEFENSIVE"
    CRISIS = "CRISIS"
    WAIT_FOR_STABILIZATION = "WAIT_FOR_STABILIZATION"
    RECOVERY_WATCH = "RECOVERY_WATCH"
    ROTATION_WINDOW = "ROTATION_WINDOW"


class CrisisSignalDisposition(StrEnum):
    POLICY_ALLOWED = "POLICY_ALLOWED"
    WATCH = "WATCH"
    DEFERRED = "DEFERRED"


@dataclass(frozen=True, slots=True)
class CrisisFactorSignal:
    factor: CrisisFactor
    available: bool
    triggered: bool
    normalized_severity: Decimal | None
    confidence: float | None
    observed_at: datetime | None
    known_at: datetime | None
    evidence_ids: tuple[str, ...] = ()
    provenance_ids: tuple[str, ...] = ()
    warning: str | None = None


@dataclass(frozen=True, slots=True)
class CrisisAssessmentInput:
    assessment_id: str
    benchmark_instrument_id: str
    normal_market_regime_id: str | None
    assessed_at: datetime
    data_as_of: datetime
    market_status: MarketStatus
    signals: tuple[CrisisFactorSignal, ...]
    critical_factors: tuple[CrisisFactor, ...]
    source_snapshot_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CrisisTransitionContext:
    previous_state: CrisisState | None = None
    previous_state_since: datetime | None = None
    consecutive_deescalation_observations: int = 0


@dataclass(frozen=True, slots=True)
class CrisisPolicySettings:
    version: str
    minimum_multifactor_triggers: int
    elevated_risk_severity: Decimal
    stress_severity: Decimal
    crisis_severity: Decimal
    severe_single_factor_override: Decimal
    minimum_deescalation_confirmations: int
    minimum_stabilization_signals: int
    critical_data_high_confidence_floor: float


@dataclass(frozen=True, slots=True)
class CrisisAssessment:
    assessment_id: str
    policy_version: str
    crisis_state: CrisisState
    severity_score: Decimal | None
    confidence: float | None
    assessed_at: datetime
    data_as_of: datetime
    previous_state: CrisisState | None
    state_duration: timedelta | None
    transition_reason: str
    triggered_factors: tuple[CrisisFactor, ...]
    non_triggered_factors: tuple[CrisisFactor, ...]
    unavailable_factors: tuple[CrisisFactor, ...]
    warnings: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    provenance_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CrisisExecutionOverride:
    policy_version: str
    assessment_id: str
    crisis_state: CrisisState
    allow_new_entries: bool
    entry_restriction_level: EntryRestrictionLevel
    maximum_position_size_multiplier: Decimal
    risk_budget_multiplier: Decimal
    require_stabilization_confirmation: bool
    require_higher_score_threshold: bool
    require_higher_confidence: bool
    restrict_breakout_entries: bool
    allow_relative_strength_watch: bool
    allow_capitulation_watch: bool
    allow_reversal_watch: bool
    stop_handling_mode: StopHandlingMode
    slippage_model_mode: SlippageModelMode
    portfolio_review_required: bool
    cash_preference: CashRecommendationState
    reasons: tuple[str, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CrisisOpportunityPolicy:
    version: str
    exceptional_market_drawdown: Decimal
    exceptional_relative_strength: Decimal
    low_drawdown_limit: Decimal


@dataclass(frozen=True, slots=True)
class CrisisOpportunityInput:
    candidate_id: str
    instrument_id: str
    assessment_id: str
    market_drawdown: Decimal | None
    relative_strength_excess: Decimal | None
    structure_intact: bool | None
    instrument_drawdown: Decimal | None
    abnormal_volume_reversal: bool | None
    emerging_sector_leader: bool | None
    recovery_reclaim: bool | None
    evidence_ids: tuple[str, ...] = ()
    provenance_ids: tuple[str, ...] = ()
    forced_selling: bool | None = None
    capitulation: bool | None = None


@dataclass(frozen=True, slots=True)
class CrisisOpportunityAssessment:
    candidate_id: str
    instrument_id: str
    assessment_id: str
    policy_version: str
    categories: tuple[CrisisOpportunityCategory, ...]
    disposition: OpportunityDisposition
    reasons: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    provenance_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PortfolioCrisisInput:
    portfolio_snapshot_id: str
    assessment_id: str
    portfolio_drawdown: Decimal | None
    concentration: Decimal | None
    sector_concentration: Decimal | None
    correlation_spike: bool | None
    liquidity_adequate: bool | None
    cash_available: Decimal | None
    holding_actions: Mapping[str, PortfolioHoldingAction]
    evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "holding_actions", MappingProxyType(dict(self.holding_actions)))


@dataclass(frozen=True, slots=True)
class PortfolioCrisisAssessment:
    portfolio_snapshot_id: str
    assessment_id: str
    crisis_state: CrisisState
    portfolio_risk_level: EntryRestrictionLevel
    urgent_review_holding_ids: tuple[str, ...]
    concentration_warnings: tuple[str, ...]
    cash_recommendation: CashRecommendationState
    risk_budget_multiplier: Decimal
    warnings: tuple[str, ...]
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CrisisSlippagePolicy:
    version: str
    normal_slippage: Decimal
    elevated_slippage: Decimal
    crisis_slippage: Decimal


@dataclass(frozen=True, slots=True)
class CrisisFillAssumption:
    assumption_id: str
    policy_version: str
    mode: SlippageModelMode
    planned_stop: Decimal | None
    market_open: Decimal | None
    expected_fill: Decimal | None
    simulated_fill: Decimal | None
    slippage: Decimal | None
    gap_through_stop: bool
    source_bar_ids: tuple[str, ...]
    provenance_ids: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PaperTradeCrisisContext:
    context_id: str
    schema_version: str
    paper_trade_id: str
    assessment_at_signal_id: str | None
    assessment_at_entry_id: str | None
    assessment_at_exit_id: str | None
    crisis_state_at_signal: CrisisState | None
    crisis_state_at_entry: CrisisState | None
    crisis_state_at_exit: CrisisState | None
    slippage_mode: SlippageModelMode | None
    expected_fill: Decimal | None
    simulated_fill: Decimal | None
    stabilization_confirmed: bool | None
    opportunity_categories: tuple[CrisisOpportunityCategory, ...]
    policy_restriction: EntryRestrictionLevel | None
    provenance_ids: tuple[str, ...]
    fingerprint: str


@dataclass(frozen=True, slots=True)
class CrisisEvent:
    event_id: str
    schema_version: str
    benchmark_instrument_id: str
    started_at: datetime
    ended_at: datetime | None
    peak_state: CrisisState
    peak_severity: Decimal | None
    transition_assessment_ids: tuple[str, ...]
    primary_triggers: tuple[CrisisFactor, ...]
    index_move: Decimal | None
    volatility_context: str | None
    breadth_context: str | None
    affected_sector_ids: tuple[str, ...]
    recovery_at: datetime | None
    provenance_ids: tuple[str, ...]
    fingerprint: str


@dataclass(frozen=True, slots=True)
class CrisisSignalEligibility:
    assessment_id: str
    decision_score: Decimal | None
    confidence: float | None
    six_gate_eligibility: str | None
    disposition: CrisisSignalDisposition
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CrisisDashboardReadModel:
    state: CrisisState
    label: CrisisDashboardLabel
    confidence: float | None
    primary_drivers: tuple[str, ...]
    new_entry_policy: EntryRestrictionLevel
    position_sizing_multiplier: Decimal
    opportunity_categories: tuple[CrisisOpportunityCategory, ...]
    warnings: tuple[str, ...]


class MarketExtremeLevel(StrEnum):
    MARKET = "MARKET"
    SECTOR = "SECTOR"
    STOCK = "STOCK"


class UpsideExcessState(StrEnum):
    NORMAL = "NORMAL"
    OPTIMISM = "OPTIMISM"
    CROWDING = "CROWDING"
    SPECULATION = "SPECULATION"
    EUPHORIA = "EUPHORIA"
    DISTRIBUTION = "DISTRIBUTION"
    BREAKDOWN = "BREAKDOWN"


class MarketCycleStage(StrEnum):
    HEALTHY_LEADERSHIP = "HEALTHY_LEADERSHIP"
    ACCELERATING = "ACCELERATING"
    EUPHORIA = "EUPHORIA"
    DISTRIBUTION = "DISTRIBUTION"
    BREAKDOWN = "BREAKDOWN"
    LEADERSHIP_RESET = "LEADERSHIP_RESET"


class UpsideExcessFactor(StrEnum):
    PRICE_ACCELERATION = "PRICE_ACCELERATION"
    PARABOLIC_EXTENSION = "PARABOLIC_EXTENSION"
    LONG_TERM_MA_EXTENSION = "LONG_TERM_MA_EXTENSION"
    ATR_EXTENSION = "ATR_EXTENSION"
    REPEATED_GAP_UPS = "REPEATED_GAP_UPS"
    PULLBACK_DISAPPEARANCE = "PULLBACK_DISAPPEARANCE"
    BREAKOUT_FREQUENCY = "BREAKOUT_FREQUENCY"
    MARKET_BREADTH_EXTREME = "MARKET_BREADTH_EXTREME"
    BREADTH_DIVERGENCE = "BREADTH_DIVERGENCE"
    LEADERSHIP_CONCENTRATION = "LEADERSHIP_CONCENTRATION"
    LOW_QUALITY_PARTICIPATION = "LOW_QUALITY_PARTICIPATION"
    LEADER_RS_DETERIORATION = "LEADER_RS_DETERIORATION"
    VALUATION_EXPANSION = "VALUATION_EXPANSION"
    EARNINGS_PRICE_DIVERGENCE = "EARNINGS_PRICE_DIVERGENCE"
    TURNOVER_ACCELERATION = "TURNOVER_ACCELERATION"
    RETAIL_PARTICIPATION_PROXY = "RETAIL_PARTICIPATION_PROXY"
    IPO_INTENSITY = "IPO_INTENSITY"
    NARRATIVE_INTENSITY = "NARRATIVE_INTENSITY"
    INSTITUTIONAL_DISTRIBUTION_PROXY = "INSTITUTIONAL_DISTRIBUTION_PROXY"
    PROMOTER_OFS_ACTIVITY = "PROMOTER_OFS_ACTIVITY"
    EARNINGS_DETERIORATION = "EARNINGS_DETERIORATION"
    FAILED_BREAKOUTS = "FAILED_BREAKOUTS"
    WEAK_HIGH_VOLUME_CLOSES = "WEAK_HIGH_VOLUME_CLOSES"
    STRUCTURAL_BREAKDOWN = "STRUCTURAL_BREAKDOWN"
    SECTOR_RS_ROLLOVER = "SECTOR_RS_ROLLOVER"
    HIGH_QUALITY_LEADER_OUTPERFORMANCE = "HIGH_QUALITY_LEADER_OUTPERFORMANCE"
    EARNINGS_ACCELERATION = "EARNINGS_ACCELERATION"


class LeadershipQuality(StrEnum):
    HEALTHY = "HEALTHY"
    BROADENING = "BROADENING"
    SPECULATIVE_BROADENING = "SPECULATIVE_BROADENING"
    LOW_QUALITY_LEADERSHIP = "LOW_QUALITY_LEADERSHIP"
    DETERIORATING = "DETERIORATING"
    UNKNOWN = "UNKNOWN"


class DistributionRisk(StrEnum):
    NONE = "NONE"
    EMERGING = "EMERGING"
    ELEVATED = "ELEVATED"
    CONFIRMED = "CONFIRMED"
    UNKNOWN = "UNKNOWN"


class PriceEarningsDivergence(StrEnum):
    SUPPORTED_ACCELERATION = "SUPPORTED_ACCELERATION"
    PRICE_OUTPACING_EARNINGS = "PRICE_OUTPACING_EARNINGS"
    DETERIORATING = "DETERIORATING"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class NarrativeSourceQuality(StrEnum):
    HIGH = "HIGH"
    MODERATE = "MODERATE"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class ChaseRestriction(StrEnum):
    NONE = "NONE"
    CAUTION = "CAUTION"
    DO_NOT_CHASE = "DO_NOT_CHASE"


class ProfitProtectionMode(StrEnum):
    NORMAL = "NORMAL"
    HEIGHTENED_REVIEW = "HEIGHTENED_REVIEW"
    PROTECT_PROFITS = "PROTECT_PROFITS"


class ExistingWinnerPosture(StrEnum):
    HOLD = "HOLD"
    HOLD_AND_TRAIL = "HOLD_AND_TRAIL"
    PROTECT_PROFIT = "PROTECT_PROFIT"
    REVIEW = "REVIEW"
    ROTATION_WATCH = "ROTATION_WATCH"


@dataclass(frozen=True, slots=True)
class UpsideExcessFactorSignal:
    factor: UpsideExcessFactor
    available: bool
    triggered: bool
    normalized_score: Decimal | None
    confidence: float | None
    observed_at: datetime | None
    known_at: datetime | None
    evidence_ids: tuple[str, ...] = ()
    provenance_ids: tuple[str, ...] = ()
    warning: str | None = None


@dataclass(frozen=True, slots=True)
class IPOIntensityObservation:
    observation_id: str
    level: MarketExtremeLevel
    entity_id: str
    as_of_timestamp: datetime
    known_at: datetime
    rolling_ipo_count: int | None
    ipo_count_acceleration: Decimal | None
    aggregate_issue_size: Decimal | None
    fresh_issue_ratio: Decimal | None
    ofs_ratio: Decimal | None
    retail_subscription: Decimal | None
    hni_subscription: Decimal | None
    institutional_subscription: Decimal | None
    listing_premium: Decimal | None
    post_listing_return: Decimal | None
    coverage: float | None
    provenance_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class NarrativeIntensityObservation:
    observation_id: str
    level: MarketExtremeLevel
    entity_id: str
    as_of_timestamp: datetime
    known_at: datetime
    mention_count: int | None
    mention_acceleration: Decimal | None
    sentiment_distribution: Mapping[str, Decimal]
    speculative_language_intensity: Decimal | None
    search_interest_proxy: Decimal | None
    social_interest_proxy: Decimal | None
    source_quality: NarrativeSourceQuality
    coverage: float | None
    provenance_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "sentiment_distribution", MappingProxyType(dict(self.sentiment_distribution)))


@dataclass(frozen=True, slots=True)
class UpsideExcessAssessmentInput:
    assessment_id: str
    level: MarketExtremeLevel
    entity_id: str
    normal_market_regime_id: str | None
    assessed_at: datetime
    data_as_of: datetime
    signals: tuple[UpsideExcessFactorSignal, ...]
    critical_factors: tuple[UpsideExcessFactor, ...]
    ipo_observation: IPOIntensityObservation | None = None
    narrative_observation: NarrativeIntensityObservation | None = None
    source_snapshot_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class UpsideTransitionContext:
    previous_state: UpsideExcessState | None = None
    consecutive_transition_observations: int = 0


@dataclass(frozen=True, slots=True)
class UpsideExcessPolicySettings:
    version: str
    minimum_multifactor_triggers: int
    optimism_score: Decimal
    crowding_score: Decimal
    speculation_score: Decimal
    euphoria_score: Decimal
    minimum_distribution_factors: int
    minimum_top_confirmation_factors: int
    minimum_transition_confirmations: int
    critical_data_high_confidence_floor: float


@dataclass(frozen=True, slots=True)
class UpsideExcessAssessment:
    assessment_id: str
    policy_version: str
    level: MarketExtremeLevel
    entity_id: str
    excess_state: UpsideExcessState
    cycle_stage: MarketCycleStage
    excess_score: Decimal | None
    confidence: float | None
    top_confirmed: bool
    distribution_risk: DistributionRisk
    leadership_quality: LeadershipQuality
    price_earnings_divergence: PriceEarningsDivergence
    assessed_at: datetime
    data_as_of: datetime
    previous_state: UpsideExcessState | None
    transition_reason: str
    supporting_factors: tuple[UpsideExcessFactor, ...]
    contradicting_factors: tuple[UpsideExcessFactor, ...]
    unavailable_factors: tuple[UpsideExcessFactor, ...]
    warnings: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    provenance_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class UpsideExcessExecutionPolicy:
    policy_version: str
    assessment_id: str
    level: MarketExtremeLevel
    entity_id: str
    excess_state: UpsideExcessState
    allow_new_entries: bool
    chase_restriction: ChaseRestriction
    required_rr_multiplier: Decimal
    position_size_multiplier: Decimal
    add_on_restriction: bool
    profit_protection_mode: ProfitProtectionMode
    trailing_vigilance: bool
    require_structure_confirmation: bool
    rotation_readiness: bool
    watch_breadth_divergence: bool
    watch_leadership_deterioration: bool
    existing_winner_posture: ExistingWinnerPosture
    reasons: tuple[str, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MarketExtremesAssessment:
    assessment_id: str
    normal_market_regime_id: str | None
    downside_assessment_id: str | None
    upside_assessment_id: str | None
    assessed_at: datetime
    data_as_of: datetime
    warnings: tuple[str, ...]
    provenance_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EffectiveMarketExtremesPolicy:
    assessment_id: str
    downside_assessment_id: str | None
    upside_assessment_id: str | None
    allow_new_entries: bool
    position_size_multiplier: Decimal
    risk_budget_multiplier: Decimal
    chase_restriction: ChaseRestriction
    cash_preference: CashRecommendationState
    rotation_readiness: bool
    reasons: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PaperTradeUpsideExtremeContext:
    context_id: str
    schema_version: str
    paper_trade_id: str
    market_assessment_id: str | None
    sector_assessment_id: str | None
    stock_assessment_id: str | None
    market_state: UpsideExcessState | None
    sector_state: UpsideExcessState | None
    stock_state: UpsideExcessState | None
    excess_score: Decimal | None
    confidence: float | None
    distribution_risk: DistributionRisk | None
    chase_restriction: ChaseRestriction | None
    leadership_quality: LeadershipQuality | None
    ipo_context_id: str | None
    narrative_context_id: str | None
    provenance_ids: tuple[str, ...]
    fingerprint: str


@dataclass(frozen=True, slots=True)
class ForwardOutcomeReference:
    horizon_sessions: int
    outcome_reference_id: str
    methodology_version: str


@dataclass(frozen=True, slots=True)
class MarketExtremeEvent:
    event_id: str
    schema_version: str
    level: MarketExtremeLevel
    entity_id: str
    started_at: datetime
    ended_at: datetime | None
    peak_state: UpsideExcessState
    peak_excess_score: Decimal | None
    transition_assessment_ids: tuple[str, ...]
    key_drivers: tuple[UpsideExcessFactor, ...]
    distribution_transition_at: datetime | None
    breakdown_transition_at: datetime | None
    forward_outcome_references: tuple[ForwardOutcomeReference, ...]
    provenance_ids: tuple[str, ...]
    fingerprint: str
