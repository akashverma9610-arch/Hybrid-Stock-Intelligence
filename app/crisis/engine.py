"""Pure crisis/dislocation assessors and policy adapters.

These services consume already-created observations.  They neither access a
provider nor mutate scores, gates, portfolios, paper trades, or strategy state.
"""
from __future__ import annotations

from decimal import Decimal

from app.crisis.models import (
    CashRecommendationState,
    CrisisAssessment,
    CrisisAssessmentInput,
    CrisisDashboardLabel,
    CrisisDashboardReadModel,
    CrisisExecutionOverride,
    CrisisFactor,
    CrisisFillAssumption,
    CrisisOpportunityAssessment,
    CrisisOpportunityCategory,
    CrisisOpportunityInput,
    CrisisOpportunityPolicy,
    CrisisPolicySettings,
    CrisisSignalDisposition,
    CrisisSignalEligibility,
    CrisisSlippagePolicy,
    CrisisState,
    CrisisTransitionContext,
    EntryRestrictionLevel,
    OpportunityDisposition,
    PortfolioCrisisAssessment,
    PortfolioCrisisInput,
    PortfolioHoldingAction,
    SlippageModelMode,
    StopHandlingMode,
)


_RISK_RANK = {
    CrisisState.NORMAL: 0,
    CrisisState.RECOVERY: 1,
    CrisisState.STABILIZING: 2,
    CrisisState.ELEVATED_RISK: 3,
    CrisisState.STRESS: 4,
    CrisisState.CRISIS: 5,
}
_STABILIZATION_FACTORS = {
    CrisisFactor.SELLING_VELOCITY_SLOWING,
    CrisisFactor.BREADTH_IMPROVING,
    CrisisFactor.VOLATILITY_NORMALIZING,
    CrisisFactor.FEWER_NEW_LOWS,
    CrisisFactor.INDEX_RECLAIM,
    CrisisFactor.LIQUIDITY_NORMALIZING,
    CrisisFactor.RECOVERY_LEADERSHIP,
}


class CrisisMarketDislocationEngine:
    """Multi-factor emergency overlay; normal market regime remains separate."""

    def __init__(self, policy: CrisisPolicySettings) -> None:
        self.policy = policy

    def assess(
        self,
        value: CrisisAssessmentInput,
        context: CrisisTransitionContext = CrisisTransitionContext(),
    ) -> CrisisAssessment:
        if value.data_as_of > value.assessed_at:
            raise ValueError("Crisis assessment data_as_of cannot be after assessed_at.")
        if self.policy.minimum_multifactor_triggers < 1:
            raise ValueError("Crisis policy requires at least one multi-factor trigger.")

        signals = tuple(value.signals)
        triggered = tuple(signal for signal in signals if signal.available and signal.triggered)
        unavailable = tuple(signal for signal in signals if not signal.available)
        non_triggered = tuple(signal for signal in signals if signal.available and not signal.triggered)
        severity_values = tuple(signal.normalized_severity for signal in triggered if signal.normalized_severity is not None)
        severity = (
            sum(severity_values, Decimal("0")) / Decimal(len(severity_values))
            if severity_values
            else None
        )
        severe_override = any(
            signal.normalized_severity is not None
            and signal.normalized_severity >= self.policy.severe_single_factor_override
            for signal in triggered
        )
        raw_state = self._raw_state(len(triggered), severity, severe_override)
        stabilization_count = sum(
            signal.triggered and signal.available and signal.factor in _STABILIZATION_FACTORS
            for signal in signals
        )
        state, transition_reason, transition_warning = self._transition(
            raw_state, stabilization_count, value.assessed_at, context
        )
        confidence, confidence_warnings = self._confidence(value, signals, unavailable)
        warnings = (*confidence_warnings, *((transition_warning,) if transition_warning else ()))
        evidence_ids = tuple(item for signal in signals for item in signal.evidence_ids)
        provenance_ids = (*value.source_snapshot_ids, *(item for signal in signals for item in signal.provenance_ids))
        duration = (
            value.assessed_at - context.previous_state_since
            if state is context.previous_state and context.previous_state_since is not None
            else None
        )
        return CrisisAssessment(
            assessment_id=value.assessment_id,
            policy_version=self.policy.version,
            crisis_state=state,
            severity_score=severity,
            confidence=confidence,
            assessed_at=value.assessed_at,
            data_as_of=value.data_as_of,
            previous_state=context.previous_state,
            state_duration=duration,
            transition_reason=transition_reason,
            triggered_factors=tuple(signal.factor for signal in triggered),
            non_triggered_factors=tuple(signal.factor for signal in non_triggered),
            unavailable_factors=tuple(signal.factor for signal in unavailable),
            warnings=warnings,
            evidence_ids=evidence_ids,
            provenance_ids=provenance_ids,
        )

    def _raw_state(self, trigger_count: int, severity: Decimal | None, severe_override: bool) -> CrisisState:
        if severe_override:
            return CrisisState.CRISIS
        if trigger_count == 0:
            return CrisisState.NORMAL
        if trigger_count < self.policy.minimum_multifactor_triggers:
            return CrisisState.ELEVATED_RISK
        if severity is None:
            return CrisisState.ELEVATED_RISK
        if severity >= self.policy.crisis_severity:
            return CrisisState.CRISIS
        if severity >= self.policy.stress_severity:
            return CrisisState.STRESS
        if severity >= self.policy.elevated_risk_severity:
            return CrisisState.ELEVATED_RISK
        return CrisisState.NORMAL

    def _transition(
        self,
        raw_state: CrisisState,
        stabilization_count: int,
        assessed_at,
        context: CrisisTransitionContext,
    ) -> tuple[CrisisState, str, str | None]:
        prior = context.previous_state
        if prior is None:
            return raw_state, "INITIAL_MULTI_FACTOR_ASSESSMENT", None
        if raw_state is CrisisState.CRISIS and prior is not CrisisState.CRISIS:
            return CrisisState.CRISIS, "SEVERE_ESCALATION_OVERRIDE", None
        if prior in {CrisisState.CRISIS, CrisisState.STRESS} and stabilization_count >= self.policy.minimum_stabilization_signals:
            if context.consecutive_deescalation_observations < self.policy.minimum_deescalation_confirmations:
                return prior, "DE_ESCALATION_CONFIRMATION_PENDING", "HYSTERESIS_CONFIRMATION_PENDING"
            return CrisisState.STABILIZING, "STABILIZATION_EVIDENCE_CONFIRMED", None
        if prior is CrisisState.STABILIZING and raw_state in {CrisisState.NORMAL, CrisisState.ELEVATED_RISK}:
            if context.consecutive_deescalation_observations < self.policy.minimum_deescalation_confirmations:
                return prior, "RECOVERY_CONFIRMATION_PENDING", "HYSTERESIS_CONFIRMATION_PENDING"
            return CrisisState.RECOVERY, "RECOVERY_EVIDENCE_CONFIRMED", None
        if prior is CrisisState.RECOVERY and raw_state is CrisisState.NORMAL:
            if context.consecutive_deescalation_observations < self.policy.minimum_deescalation_confirmations:
                return prior, "NORMALIZATION_CONFIRMATION_PENDING", "HYSTERESIS_CONFIRMATION_PENDING"
            return CrisisState.NORMAL, "NORMALIZATION_CONFIRMED", None
        if _RISK_RANK[raw_state] < _RISK_RANK[prior]:
            if context.consecutive_deescalation_observations < self.policy.minimum_deescalation_confirmations:
                return prior, "DE_ESCALATION_CONFIRMATION_PENDING", "HYSTERESIS_CONFIRMATION_PENDING"
            return raw_state, "DE_ESCALATION_CONFIRMED", None
        return raw_state, "MULTI_FACTOR_POLICY_STATE", None

    def _confidence(self, value, signals, unavailable):
        relevant = tuple(signal for signal in signals if signal.factor not in _STABILIZATION_FACTORS)
        available = tuple(signal for signal in relevant if signal.available)
        factor_confidence = tuple(signal.confidence for signal in available if signal.confidence is not None)
        coverage = len(available) / len(relevant) if relevant else 0.0
        confidence = (sum(factor_confidence) / len(factor_confidence) if factor_confidence else coverage) * coverage
        missing_critical = tuple(factor for factor in value.critical_factors if factor in {item.factor for item in unavailable})
        warnings: tuple[str, ...] = ()
        if missing_critical:
            confidence = min(confidence, self.policy.critical_data_high_confidence_floor)
            warnings = ("CRITICAL_MARKET_DATA_UNAVAILABLE",)
        if not available:
            warnings = (*warnings, "INSUFFICIENT_MARKET_DISLOCATION_INPUTS")
        return confidence, warnings


class CrisisExecutionPolicyService:
    """Converts a state into analytical execution constraints, never an order."""

    def resolve(self, assessment: CrisisAssessment, *, policy_version: str) -> CrisisExecutionOverride:
        state = assessment.crisis_state
        profiles = {
            CrisisState.NORMAL: (True, EntryRestrictionLevel.NONE, "1", "1", False, False, False, False, StopHandlingMode.NORMAL, SlippageModelMode.NORMAL, False, CashRecommendationState.NORMAL_ALLOCATION),
            CrisisState.ELEVATED_RISK: (True, EntryRestrictionLevel.HIGHER_QUALITY, "0.75", "0.75", False, True, True, True, StopHandlingMode.GAP_AWARE_REVIEW, SlippageModelMode.ELEVATED, True, CashRecommendationState.DEFENSIVE_ALLOCATION),
            CrisisState.STRESS: (False, EntryRestrictionLevel.RESTRICTED, "0.50", "0.50", True, True, True, True, StopHandlingMode.GAP_AWARE_REVIEW, SlippageModelMode.ELEVATED, True, CashRecommendationState.PRESERVED_OPTIONALITY),
            CrisisState.CRISIS: (False, EntryRestrictionLevel.DISABLED, "0.25", "0.25", True, True, True, True, StopHandlingMode.EXECUTION_UNCERTAIN, SlippageModelMode.CRISIS, True, CashRecommendationState.PRESERVED_OPTIONALITY),
            CrisisState.STABILIZING: (False, EntryRestrictionLevel.RESTRICTED, "0.35", "0.35", True, True, True, True, StopHandlingMode.GAP_AWARE_REVIEW, SlippageModelMode.ELEVATED, True, CashRecommendationState.DELIBERATE_NO_TRADE),
            CrisisState.RECOVERY: (True, EntryRestrictionLevel.HIGHER_QUALITY, "0.50", "0.50", True, True, True, True, StopHandlingMode.GAP_AWARE_REVIEW, SlippageModelMode.ELEVATED, True, CashRecommendationState.DEFENSIVE_ALLOCATION),
        }
        allow, level, size, risk, stabilize, score, confidence, breakout, stop, slippage, review, cash = profiles[state]
        return CrisisExecutionOverride(
            policy_version, assessment.assessment_id, state, allow, level, Decimal(size), Decimal(risk), stabilize,
            score, confidence, breakout, True, True, True, stop, slippage, review, cash,
            (f"CRISIS_STATE:{state.value}", "CRISIS_IS_NOT_A_TRADE_ORDER"),
            ("NO_BLANKET_LIQUIDATION", "NO_AUTOMATIC_DIP_BUYING"),
        )

    def apply_to_signal(
        self,
        override: CrisisExecutionOverride,
        *,
        decision_score: Decimal | None,
        confidence: float | None,
        six_gate_eligibility: str | None,
    ) -> CrisisSignalEligibility:
        if not override.allow_new_entries:
            disposition = CrisisSignalDisposition.DEFERRED
            reason = "CRISIS_POLICY_RESTRICTS_NEW_ENTRIES"
        elif override.require_higher_confidence and confidence is None:
            disposition = CrisisSignalDisposition.WATCH
            reason = "CRISIS_POLICY_REQUIRES_CONFIDENCE"
        else:
            disposition = CrisisSignalDisposition.POLICY_ALLOWED
            reason = "CRISIS_POLICY_ALLOWS_ANALYTICAL_REVIEW"
        return CrisisSignalEligibility(
            override.assessment_id, decision_score, confidence, six_gate_eligibility, disposition, (reason,)
        )


class CrisisOpportunityScanner:
    """Classifies research/watch candidates only; it never emits BUY."""

    def __init__(self, policy: CrisisOpportunityPolicy) -> None:
        self.policy = policy

    def assess(self, value: CrisisOpportunityInput) -> CrisisOpportunityAssessment:
        categories: list[CrisisOpportunityCategory] = []
        reasons: list[str] = []
        if (
            value.market_drawdown is not None
            and value.relative_strength_excess is not None
            and value.structure_intact is True
            and value.market_drawdown <= self.policy.exceptional_market_drawdown
            and value.relative_strength_excess >= self.policy.exceptional_relative_strength
        ):
            categories.append(CrisisOpportunityCategory.EXCEPTIONAL_RELATIVE_STRENGTH)
            reasons.append("SEVERE_MARKET_DRAWDOWN_WITH_INTACT_RELATIVE_STRENGTH")
        if value.structure_intact is True:
            categories.append(CrisisOpportunityCategory.MAJOR_STRUCTURE_SURVIVOR)
        if value.instrument_drawdown is not None and value.instrument_drawdown >= self.policy.low_drawdown_limit:
            categories.append(CrisisOpportunityCategory.LOW_DRAWDOWN_LEADER)
        if value.abnormal_volume_reversal:
            categories.append(CrisisOpportunityCategory.ABNORMAL_VOLUME_REVERSAL)
        if value.forced_selling:
            categories.append(CrisisOpportunityCategory.FORCED_SELLING_CANDIDATE)
        if value.capitulation:
            categories.append(CrisisOpportunityCategory.CAPITULATION_CANDIDATE)
        if value.emerging_sector_leader:
            categories.append(CrisisOpportunityCategory.EMERGING_SECTOR_LEADER)
        if value.recovery_reclaim:
            categories.extend((CrisisOpportunityCategory.RECOVERY_LEADER, CrisisOpportunityCategory.POST_CRASH_BASE_RECLAIM))
        if CrisisOpportunityCategory.EXCEPTIONAL_RELATIVE_STRENGTH in categories:
            disposition = OpportunityDisposition.PRIORITY_RESEARCH
        elif categories:
            disposition = OpportunityDisposition.WATCH
        else:
            disposition = OpportunityDisposition.NOT_ELIGIBLE
        return CrisisOpportunityAssessment(
            value.candidate_id, value.instrument_id, value.assessment_id, self.policy.version,
            tuple(dict.fromkeys(categories)), disposition,
            tuple(reasons) or ("NO_CRISIS_OPPORTUNITY_CLASSIFICATION",), value.evidence_ids, value.provenance_ids,
        )


class PortfolioCrisisAssessmentService:
    """Read-only portfolio review context; holding actions are supplied, not executed."""

    def assess(self, value: PortfolioCrisisInput, override: CrisisExecutionOverride) -> PortfolioCrisisAssessment:
        urgent = tuple(
            holding_id for holding_id, action in value.holding_actions.items()
            if action in {PortfolioHoldingAction.REDUCE, PortfolioHoldingAction.EXIT, PortfolioHoldingAction.REVIEW, PortfolioHoldingAction.UNABLE_TO_EXECUTE_CLEANLY}
        )
        warnings: list[str] = []
        if value.concentration is not None and value.concentration >= Decimal("0.40"):
            warnings.append("PORTFOLIO_CONCENTRATION_STRESS")
        if value.sector_concentration is not None and value.sector_concentration >= Decimal("0.50"):
            warnings.append("SECTOR_CONCENTRATION_STRESS")
        if value.liquidity_adequate is False:
            warnings.append("LIQUIDITY_REVIEW_REQUIRED")
        return PortfolioCrisisAssessment(
            value.portfolio_snapshot_id, value.assessment_id, override.crisis_state,
            override.entry_restriction_level, urgent, tuple(warnings), override.cash_preference,
            override.risk_budget_multiplier, tuple(warnings), value.evidence_ids,
        )


class CrisisSlippageAssumptionService:
    """A transparent future paper/backtest fill assumption, not an execution router."""

    def __init__(self, policy: CrisisSlippagePolicy) -> None:
        self.policy = policy

    def stop_fill(
        self,
        *,
        assumption_id: str,
        mode: SlippageModelMode,
        planned_stop: Decimal | None,
        market_open: Decimal | None,
        source_bar_ids: tuple[str, ...] = (),
        provenance_ids: tuple[str, ...] = (),
    ) -> CrisisFillAssumption:
        slippage = {
            SlippageModelMode.NORMAL: self.policy.normal_slippage,
            SlippageModelMode.ELEVATED: self.policy.elevated_slippage,
            SlippageModelMode.CRISIS: self.policy.crisis_slippage,
        }[mode]
        gap = planned_stop is not None and market_open is not None and market_open < planned_stop
        expected = planned_stop
        base = market_open if gap else planned_stop
        simulated = base - slippage if base is not None else None
        warnings = ("GAP_THROUGH_STOP_NO_PLANNED_STOP_FILL_ASSUMPTION",) if gap else ()
        return CrisisFillAssumption(
            assumption_id, self.policy.version, mode, planned_stop, market_open, expected, simulated,
            slippage if simulated is not None else None, gap, source_bar_ids, provenance_ids, warnings,
        )


def crisis_dashboard_read_model(
    assessment: CrisisAssessment,
    override: CrisisExecutionOverride,
    opportunities: tuple[CrisisOpportunityAssessment, ...] = (),
) -> CrisisDashboardReadModel:
    labels = {
        CrisisState.NORMAL: CrisisDashboardLabel.NORMAL,
        CrisisState.ELEVATED_RISK: CrisisDashboardLabel.CAUTION,
        CrisisState.STRESS: CrisisDashboardLabel.DEFENSIVE,
        CrisisState.CRISIS: CrisisDashboardLabel.CRISIS,
        CrisisState.STABILIZING: CrisisDashboardLabel.WAIT_FOR_STABILIZATION,
        CrisisState.RECOVERY: CrisisDashboardLabel.RECOVERY_WATCH,
    }
    categories = tuple(
        dict.fromkeys(category for item in opportunities for category in item.categories)
    )
    if CrisisOpportunityCategory.EMERGING_SECTOR_LEADER in categories:
        label = CrisisDashboardLabel.ROTATION_WINDOW if assessment.crisis_state is CrisisState.RECOVERY else labels[assessment.crisis_state]
    else:
        label = labels[assessment.crisis_state]
    return CrisisDashboardReadModel(
        assessment.crisis_state, label, assessment.confidence,
        tuple(item.value.replace("_", " ").lower() for item in assessment.triggered_factors[:3]),
        override.entry_restriction_level, override.maximum_position_size_multiplier,
        categories, assessment.warnings,
    )
