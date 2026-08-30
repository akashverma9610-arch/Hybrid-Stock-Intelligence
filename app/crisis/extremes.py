"""Provider-neutral upside excess/euphoria and two-tail market-extremes layer."""
from __future__ import annotations

from decimal import Decimal

from app.crisis.models import (
    CashRecommendationState,
    ChaseRestriction,
    CrisisAssessment,
    CrisisExecutionOverride,
    DistributionRisk,
    EffectiveMarketExtremesPolicy,
    ExistingWinnerPosture,
    LeadershipQuality,
    MarketCycleStage,
    MarketExtremesAssessment,
    PriceEarningsDivergence,
    ProfitProtectionMode,
    UpsideExcessAssessment,
    UpsideExcessAssessmentInput,
    UpsideExcessExecutionPolicy,
    UpsideExcessFactor,
    UpsideExcessPolicySettings,
    UpsideExcessState,
    UpsideTransitionContext,
)


_HEALTHY_FACTORS = {
    UpsideExcessFactor.HIGH_QUALITY_LEADER_OUTPERFORMANCE,
    UpsideExcessFactor.EARNINGS_ACCELERATION,
}
_DISTRIBUTION_FACTORS = {
    UpsideExcessFactor.BREADTH_DIVERGENCE,
    UpsideExcessFactor.LEADER_RS_DETERIORATION,
    UpsideExcessFactor.INSTITUTIONAL_DISTRIBUTION_PROXY,
    UpsideExcessFactor.PROMOTER_OFS_ACTIVITY,
    UpsideExcessFactor.EARNINGS_DETERIORATION,
    UpsideExcessFactor.FAILED_BREAKOUTS,
    UpsideExcessFactor.WEAK_HIGH_VOLUME_CLOSES,
    UpsideExcessFactor.SECTOR_RS_ROLLOVER,
}


class MarketExtremesEngine:
    """Composes independent downside and upside dimensions without trading."""

    def __init__(self, upside_policy: UpsideExcessPolicySettings) -> None:
        self.upside_policy = upside_policy

    def assess_upside(
        self,
        value: UpsideExcessAssessmentInput,
        context: UpsideTransitionContext = UpsideTransitionContext(),
    ) -> UpsideExcessAssessment:
        if value.data_as_of > value.assessed_at:
            raise ValueError("Upside assessment data_as_of cannot be after assessed_at.")
        signals = tuple(value.signals)
        unavailable = tuple(item for item in signals if not item.available)
        triggered = tuple(item for item in signals if item.available and item.triggered)
        contradicting = tuple(item for item in triggered if item.factor in _HEALTHY_FACTORS)
        supporting = tuple(item for item in triggered if item.factor not in _HEALTHY_FACTORS)
        scores = tuple(item.normalized_score for item in supporting if item.normalized_score is not None)
        score = sum(scores, Decimal("0")) / Decimal(len(scores)) if scores else None
        distribution = tuple(item for item in supporting if item.factor in _DISTRIBUTION_FACTORS)
        structural_breakdown = any(item.factor is UpsideExcessFactor.STRUCTURAL_BREAKDOWN for item in supporting)
        raw_state = self._raw_state(len(supporting), score, len(distribution), structural_breakdown)
        state, transition_reason, transition_warning = self._transition(raw_state, structural_breakdown, context)
        confidence, confidence_warnings = self._confidence(value, signals, unavailable)
        distribution_risk = self._distribution_risk(len(distribution), structural_breakdown)
        leadership = self._leadership_quality(triggered)
        divergence = self._price_earnings_divergence(triggered)
        top_confirmed = structural_breakdown and len(distribution) >= self.upside_policy.minimum_top_confirmation_factors
        warnings = (*confidence_warnings, *((transition_warning,) if transition_warning else ()))
        if state is UpsideExcessState.EUPHORIA and not top_confirmed:
            warnings = (*warnings, "EUPHORIA_IS_NOT_TOP_CONFIRMATION")
        evidence_ids = tuple(entry for item in signals for entry in item.evidence_ids)
        provenance_ids = (*value.source_snapshot_ids, *(entry for item in signals for entry in item.provenance_ids))
        return UpsideExcessAssessment(
            value.assessment_id, self.upside_policy.version, value.level, value.entity_id, state,
            self._cycle_stage(state, leadership), score, confidence, top_confirmed, distribution_risk,
            leadership, divergence, value.assessed_at, value.data_as_of, context.previous_state,
            transition_reason, tuple(item.factor for item in supporting), tuple(item.factor for item in contradicting),
            tuple(item.factor for item in unavailable), warnings, evidence_ids, provenance_ids,
        )

    def compose(
        self,
        *,
        assessment_id: str,
        normal_market_regime_id: str | None,
        downside: CrisisAssessment | None,
        upside: UpsideExcessAssessment | None,
    ) -> MarketExtremesAssessment:
        assessments = tuple(item for item in (downside, upside) if item is not None)
        if not assessments:
            raise ValueError("Market extremes composition needs at least one assessment.")
        assessed_at = max(item.assessed_at for item in assessments)
        data_as_of = min(item.data_as_of for item in assessments)
        warnings = tuple(entry for item in assessments for entry in item.warnings)
        provenance = tuple(entry for item in assessments for entry in item.provenance_ids)
        return MarketExtremesAssessment(
            assessment_id, normal_market_regime_id,
            downside.assessment_id if downside else None, upside.assessment_id if upside else None,
            assessed_at, data_as_of, warnings, provenance,
        )

    def effective_policy(
        self,
        composed: MarketExtremesAssessment,
        downside: CrisisExecutionOverride | None,
        upside: UpsideExcessExecutionPolicy | None,
    ) -> EffectiveMarketExtremesPolicy:
        if downside is None and upside is None:
            raise ValueError("Market extremes policy needs a downside or upside overlay.")
        allow_entries = (downside.allow_new_entries if downside else True) and (upside.allow_new_entries if upside else True)
        size = min(
            downside.maximum_position_size_multiplier if downside else Decimal("1"),
            upside.position_size_multiplier if upside else Decimal("1"),
        )
        risk = downside.risk_budget_multiplier if downside else Decimal("1")
        chase = upside.chase_restriction if upside else ChaseRestriction.NONE
        cash = downside.cash_preference if downside else CashRecommendationState.NORMAL_ALLOCATION
        reasons = tuple(entry for item in (downside, upside) if item is not None for entry in item.reasons)
        warnings = tuple(entry for item in (downside, upside) if item is not None for entry in item.warnings)
        return EffectiveMarketExtremesPolicy(
            composed.assessment_id, composed.downside_assessment_id, composed.upside_assessment_id,
            allow_entries, size, risk, chase, cash, upside.rotation_readiness if upside else False, reasons, warnings,
        )

    def _raw_state(self, count: int, score: Decimal | None, distribution_count: int, structural_breakdown: bool) -> UpsideExcessState:
        if structural_breakdown:
            return UpsideExcessState.BREAKDOWN
        if distribution_count >= self.upside_policy.minimum_distribution_factors:
            return UpsideExcessState.DISTRIBUTION
        if count < self.upside_policy.minimum_multifactor_triggers or score is None:
            return UpsideExcessState.NORMAL if count == 0 else UpsideExcessState.OPTIMISM
        if score >= self.upside_policy.euphoria_score:
            return UpsideExcessState.EUPHORIA
        if score >= self.upside_policy.speculation_score:
            return UpsideExcessState.SPECULATION
        if score >= self.upside_policy.crowding_score:
            return UpsideExcessState.CROWDING
        if score >= self.upside_policy.optimism_score:
            return UpsideExcessState.OPTIMISM
        return UpsideExcessState.NORMAL

    def _transition(self, raw: UpsideExcessState, structural_breakdown: bool, context: UpsideTransitionContext):
        if context.previous_state is None:
            return raw, "INITIAL_EVIDENCE_ASSESSMENT", None
        if raw is UpsideExcessState.BREAKDOWN and structural_breakdown:
            return raw, "STRUCTURAL_BREAKDOWN_EVIDENCE", None
        if raw in {UpsideExcessState.DISTRIBUTION, UpsideExcessState.BREAKDOWN} and context.previous_state is UpsideExcessState.EUPHORIA:
            if context.consecutive_transition_observations < self.upside_policy.minimum_transition_confirmations:
                return context.previous_state, "TRANSITION_CONFIRMATION_PENDING", "HYSTERESIS_CONFIRMATION_PENDING"
            return raw, "DISTRIBUTION_TRANSITION_CONFIRMED", None
        return raw, "MULTI_FACTOR_EXCESS_STATE", None

    def _confidence(self, value, signals, unavailable):
        available = tuple(item for item in signals if item.available)
        factor_confidence = tuple(item.confidence for item in available if item.confidence is not None)
        coverage = len(available) / len(signals) if signals else 0.0
        confidence = (sum(factor_confidence) / len(factor_confidence) if factor_confidence else coverage) * coverage
        warnings: tuple[str, ...] = ()
        unavailable_factors = {item.factor for item in unavailable}
        if any(item in unavailable_factors for item in value.critical_factors):
            confidence = min(confidence, self.upside_policy.critical_data_high_confidence_floor)
            warnings = ("CRITICAL_UPSIDE_INPUT_UNAVAILABLE",)
        narrative = value.narrative_observation
        if narrative and (narrative.source_quality.value in {"LOW", "UNKNOWN"} or (narrative.coverage is not None and narrative.coverage < 0.5)):
            confidence = min(confidence, self.upside_policy.critical_data_high_confidence_floor)
            warnings = (*warnings, "NARRATIVE_SOURCE_LOW_QUALITY_OR_COVERAGE")
        return confidence, warnings

    def _distribution_risk(self, count: int, structural: bool) -> DistributionRisk:
        if structural:
            return DistributionRisk.CONFIRMED
        if count >= self.upside_policy.minimum_distribution_factors:
            return DistributionRisk.ELEVATED
        if count:
            return DistributionRisk.EMERGING
        return DistributionRisk.NONE

    @staticmethod
    def _leadership_quality(triggered) -> LeadershipQuality:
        factors = {item.factor for item in triggered}
        if UpsideExcessFactor.LEADER_RS_DETERIORATION in factors:
            return LeadershipQuality.DETERIORATING
        if UpsideExcessFactor.LOW_QUALITY_PARTICIPATION in factors:
            return LeadershipQuality.LOW_QUALITY_LEADERSHIP
        if UpsideExcessFactor.HIGH_QUALITY_LEADER_OUTPERFORMANCE in factors:
            return LeadershipQuality.HEALTHY
        if UpsideExcessFactor.MARKET_BREADTH_EXTREME in factors:
            return LeadershipQuality.BROADENING
        return LeadershipQuality.UNKNOWN

    @staticmethod
    def _price_earnings_divergence(triggered) -> PriceEarningsDivergence:
        factors = {item.factor for item in triggered}
        if UpsideExcessFactor.EARNINGS_DETERIORATION in factors:
            return PriceEarningsDivergence.DETERIORATING
        if UpsideExcessFactor.PRICE_ACCELERATION in factors and UpsideExcessFactor.EARNINGS_ACCELERATION in factors:
            return PriceEarningsDivergence.SUPPORTED_ACCELERATION
        if UpsideExcessFactor.PRICE_ACCELERATION in factors and (
            UpsideExcessFactor.EARNINGS_PRICE_DIVERGENCE in factors or UpsideExcessFactor.VALUATION_EXPANSION in factors
        ):
            return PriceEarningsDivergence.PRICE_OUTPACING_EARNINGS
        return PriceEarningsDivergence.INSUFFICIENT_DATA

    @staticmethod
    def _cycle_stage(state: UpsideExcessState, leadership: LeadershipQuality) -> MarketCycleStage:
        if state is UpsideExcessState.BREAKDOWN:
            return MarketCycleStage.BREAKDOWN
        if state is UpsideExcessState.DISTRIBUTION:
            return MarketCycleStage.DISTRIBUTION
        if state is UpsideExcessState.EUPHORIA:
            return MarketCycleStage.EUPHORIA
        if leadership in {LeadershipQuality.HEALTHY, LeadershipQuality.BROADENING}:
            return MarketCycleStage.ACCELERATING if state is not UpsideExcessState.NORMAL else MarketCycleStage.HEALTHY_LEADERSHIP
        return MarketCycleStage.LEADERSHIP_RESET if leadership is LeadershipQuality.DETERIORATING else MarketCycleStage.ACCELERATING


class UpsideExcessExecutionPolicyService:
    """Entry and profit-protection posture only; euphoria never emits SELL."""

    def resolve(self, assessment: UpsideExcessAssessment, *, policy_version: str) -> UpsideExcessExecutionPolicy:
        state = assessment.excess_state
        if state in {UpsideExcessState.NORMAL, UpsideExcessState.OPTIMISM}:
            values = (True, ChaseRestriction.NONE, "1", "1", False, ProfitProtectionMode.NORMAL, False, False, False, ExistingWinnerPosture.HOLD)
        elif state in {UpsideExcessState.CROWDING, UpsideExcessState.SPECULATION}:
            values = (True, ChaseRestriction.CAUTION, "1.25", "0.75", True, ProfitProtectionMode.HEIGHTENED_REVIEW, True, True, True, ExistingWinnerPosture.HOLD_AND_TRAIL)
        elif state is UpsideExcessState.EUPHORIA:
            values = (True, ChaseRestriction.DO_NOT_CHASE, "1.50", "0.50", True, ProfitProtectionMode.PROTECT_PROFITS, True, True, True, ExistingWinnerPosture.PROTECT_PROFIT)
        elif state is UpsideExcessState.DISTRIBUTION:
            values = (False, ChaseRestriction.DO_NOT_CHASE, "1.75", "0.35", True, ProfitProtectionMode.PROTECT_PROFITS, True, True, True, ExistingWinnerPosture.ROTATION_WATCH)
        else:
            values = (False, ChaseRestriction.DO_NOT_CHASE, "2.00", "0.25", True, ProfitProtectionMode.PROTECT_PROFITS, True, True, True, ExistingWinnerPosture.REVIEW)
        allow, chase, rr, size, addon, protection, trailing, structure, rotation, posture = values
        return UpsideExcessExecutionPolicy(
            policy_version, assessment.assessment_id, assessment.level, assessment.entity_id, state, allow, chase,
            Decimal(rr), Decimal(size), addon, protection, trailing, structure, rotation,
            assessment.distribution_risk is not DistributionRisk.NONE,
            assessment.leadership_quality in {LeadershipQuality.DETERIORATING, LeadershipQuality.LOW_QUALITY_LEADERSHIP},
            posture, (f"UPSIDE_EXCESS_STATE:{state.value}", "EUPHORIA_IS_NOT_SELL"),
            ("NO_AUTOMATIC_EXIT_OR_ROTATION",),
        )
