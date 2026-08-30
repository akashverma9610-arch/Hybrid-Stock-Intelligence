from datetime import UTC, datetime
from decimal import Decimal
import inspect

import pytest

from app.crisis.engine import CrisisExecutionPolicyService, CrisisMarketDislocationEngine
from app.crisis.extremes import MarketExtremesEngine, UpsideExcessExecutionPolicyService
from app.crisis.models import (
    ChaseRestriction,
    CrisisAssessmentInput,
    CrisisFactor,
    CrisisFactorSignal,
    CrisisPolicySettings,
    CrisisState,
    DistributionRisk,
    ForwardOutcomeReference,
    IPOIntensityObservation,
    LeadershipQuality,
    MarketExtremeEvent,
    MarketExtremeLevel,
    MarketStatus,
    NarrativeIntensityObservation,
    NarrativeSourceQuality,
    PaperTradeUpsideExtremeContext,
    PriceEarningsDivergence,
    UpsideExcessAssessmentInput,
    UpsideExcessFactor,
    UpsideExcessFactorSignal,
    UpsideExcessPolicySettings,
    UpsideExcessState,
    UpsideTransitionContext,
)
from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily
from app.storage.database import DatabaseBackend, DatabaseSettings
from app.storage.repository_factory import create_core_api_snapshot_repository


T = datetime(2026, 8, 24, 10, tzinfo=UTC)
UP_POLICY = UpsideExcessPolicySettings("upside-v1", 2, Decimal("0.20"), Decimal("0.40"), Decimal("0.60"), Decimal("0.80"), 2, 3, 2, 0.49)
DOWN_POLICY = CrisisPolicySettings("down-v1", 2, Decimal("0.25"), Decimal("0.50"), Decimal("0.80"), Decimal("0.95"), 2, 2, 0.49)


def signal(factor, *, triggered=True, score="0.90", available=True, confidence=0.9):
    return UpsideExcessFactorSignal(factor, available, triggered, Decimal(score) if score is not None else None, confidence, T, T, (f"e-{factor.value}",), (f"p-{factor.value}",))


def value(*signals, level=MarketExtremeLevel.MARKET, entity="NIFTY", critical=(), ipo=None, narrative=None):
    return UpsideExcessAssessmentInput("upside-assessment", level, entity, "regime-1", T, T, tuple(signals), tuple(critical), ipo, narrative, ("market-snapshot",))


def downside():
    signals = (
        CrisisFactorSignal(CrisisFactor.MARKET_BREADTH, True, True, Decimal("0.90"), 0.9, T, T),
        CrisisFactorSignal(CrisisFactor.ATR_EXPANSION, True, True, Decimal("0.90"), 0.9, T, T),
    )
    return CrisisMarketDislocationEngine(DOWN_POLICY).assess(CrisisAssessmentInput("downside", "NIFTY", "regime-1", T, T, MarketStatus.TRADING_NORMAL, signals, ()))


def test_healthy_and_supported_acceleration_do_not_prove_euphoria_or_a_top():
    engine = MarketExtremesEngine(UP_POLICY)
    result = engine.assess_upside(value(
        signal(UpsideExcessFactor.PRICE_ACCELERATION, score="0.70"),
        signal(UpsideExcessFactor.EARNINGS_ACCELERATION, score="0.90"),
        signal(UpsideExcessFactor.HIGH_QUALITY_LEADER_OUTPERFORMANCE, score="0.90"),
    ))
    assert result.excess_state is not UpsideExcessState.EUPHORIA
    assert result.top_confirmed is False
    assert result.leadership_quality is LeadershipQuality.HEALTHY
    assert result.price_earnings_divergence is PriceEarningsDivergence.SUPPORTED_ACCELERATION


def test_market_sector_and_stock_excess_are_independent_and_narrative_is_not_evidence():
    engine = MarketExtremesEngine(UP_POLICY)
    market = engine.assess_upside(value(signal(UpsideExcessFactor.PRICE_ACCELERATION, score="0.90"), signal(UpsideExcessFactor.VALUATION_EXPANSION, score="0.90"), signal(UpsideExcessFactor.RETAIL_PARTICIPATION_PROXY, score="0.90")))
    sector = engine.assess_upside(value(signal(UpsideExcessFactor.PRICE_ACCELERATION, score="0.90"), signal(UpsideExcessFactor.VALUATION_EXPANSION, score="0.90"), level=MarketExtremeLevel.SECTOR, entity="ENGINEERING"))
    stock = engine.assess_upside(value(signal(UpsideExcessFactor.HIGH_QUALITY_LEADER_OUTPERFORMANCE, score="0.90"), level=MarketExtremeLevel.STOCK, entity="ENGINEERING-STOCK"))
    unsupported_narrative = engine.assess_upside(value(level=MarketExtremeLevel.SECTOR, entity="ENGINEERING"))
    assert market.excess_state is UpsideExcessState.EUPHORIA
    assert sector.excess_state is UpsideExcessState.EUPHORIA
    assert stock.excess_state is not UpsideExcessState.EUPHORIA
    assert unsupported_narrative.excess_state is UpsideExcessState.NORMAL
    assert unsupported_narrative.confidence == 0.0


def test_ipo_narrative_quality_and_missing_inputs_do_not_create_false_high_confidence():
    engine = MarketExtremesEngine(UP_POLICY)
    ipo = IPOIntensityObservation("ipo-1", MarketExtremeLevel.SECTOR, "TECH", T, T, 20, Decimal("0.5"), Decimal("100"), Decimal("0.4"), Decimal("0.6"), Decimal("10"), Decimal("20"), Decimal("30"), Decimal("0.5"), Decimal("-0.2"), 0.9, ("ipo-source",))
    narrative = NarrativeIntensityObservation("narrative-1", MarketExtremeLevel.SECTOR, "TECH", T, T, 100, Decimal("2"), {}, Decimal("0.9"), Decimal("0.9"), Decimal("0.9"), NarrativeSourceQuality.LOW, 0.2, ("narrative-source",))
    ipo_only = engine.assess_upside(value(signal(UpsideExcessFactor.IPO_INTENSITY), ipo=ipo))
    rich_but_stale = engine.assess_upside(value(
        signal(UpsideExcessFactor.IPO_INTENSITY), signal(UpsideExcessFactor.RETAIL_PARTICIPATION_PROXY), signal(UpsideExcessFactor.VALUATION_EXPANSION), signal(UpsideExcessFactor.PRICE_ACCELERATION),
        critical=(UpsideExcessFactor.IPO_INTENSITY,), ipo=ipo, narrative=narrative,
    ))
    missing = engine.assess_upside(value(signal(UpsideExcessFactor.IPO_INTENSITY, available=False, score=None), critical=(UpsideExcessFactor.IPO_INTENSITY,)))
    assert ipo_only.excess_state is not UpsideExcessState.EUPHORIA
    assert rich_but_stale.excess_state is UpsideExcessState.EUPHORIA
    assert rich_but_stale.confidence is not None and rich_but_stale.confidence <= UP_POLICY.critical_data_high_confidence_floor
    assert "NARRATIVE_SOURCE_LOW_QUALITY_OR_COVERAGE" in rich_but_stale.warnings
    assert missing.confidence is not None and missing.confidence <= UP_POLICY.critical_data_high_confidence_floor


def test_euphoria_distribution_breakdown_transition_requires_evidence_and_euphoria_is_not_sell():
    engine = MarketExtremesEngine(UP_POLICY)
    euphoria = engine.assess_upside(value(signal(UpsideExcessFactor.PRICE_ACCELERATION), signal(UpsideExcessFactor.VALUATION_EXPANSION), signal(UpsideExcessFactor.RETAIL_PARTICIPATION_PROXY)))
    pending = engine.assess_upside(value(signal(UpsideExcessFactor.BREADTH_DIVERGENCE), signal(UpsideExcessFactor.FAILED_BREAKOUTS)), UpsideTransitionContext(UpsideExcessState.EUPHORIA, 0))
    distribution = engine.assess_upside(value(signal(UpsideExcessFactor.BREADTH_DIVERGENCE), signal(UpsideExcessFactor.FAILED_BREAKOUTS), signal(UpsideExcessFactor.RETAIL_PARTICIPATION_PROXY), signal(UpsideExcessFactor.INSTITUTIONAL_DISTRIBUTION_PROXY)), UpsideTransitionContext(UpsideExcessState.EUPHORIA, 2))
    breakdown = engine.assess_upside(value(signal(UpsideExcessFactor.STRUCTURAL_BREAKDOWN), signal(UpsideExcessFactor.BREADTH_DIVERGENCE), signal(UpsideExcessFactor.FAILED_BREAKOUTS)), UpsideTransitionContext(UpsideExcessState.DISTRIBUTION, 2))
    overlay = UpsideExcessExecutionPolicyService().resolve(euphoria, policy_version="upside-overlay-v1")
    assert euphoria.top_confirmed is False
    assert pending.excess_state is UpsideExcessState.EUPHORIA and "HYSTERESIS_CONFIRMATION_PENDING" in pending.warnings
    assert distribution.excess_state is UpsideExcessState.DISTRIBUTION
    assert UpsideExcessFactor.INSTITUTIONAL_DISTRIBUTION_PROXY in distribution.supporting_factors
    assert breakdown.excess_state is UpsideExcessState.BREAKDOWN and breakdown.top_confirmed is False
    assert distribution.distribution_risk is DistributionRisk.ELEVATED
    assert overlay.chase_restriction is ChaseRestriction.DO_NOT_CHASE
    assert overlay.existing_winner_posture.value == "PROTECT_PROFIT"
    assert "EUPHORIA_IS_NOT_SELL" in overlay.reasons and "NO_AUTOMATIC_EXIT_OR_ROTATION" in overlay.warnings


def test_two_tail_composition_preserves_downside_and_requires_no_rotation_or_trade():
    downside_assessment = downside()
    downside_policy = CrisisExecutionPolicyService().resolve(downside_assessment, policy_version="down-overlay-v1")
    engine = MarketExtremesEngine(UP_POLICY)
    upside = engine.assess_upside(value(signal(UpsideExcessFactor.PRICE_ACCELERATION), signal(UpsideExcessFactor.VALUATION_EXPANSION), signal(UpsideExcessFactor.RETAIL_PARTICIPATION_PROXY)))
    upside_policy = UpsideExcessExecutionPolicyService().resolve(upside, policy_version="upside-overlay-v1")
    composed = engine.compose(assessment_id="combined", normal_market_regime_id="regime-1", downside=downside_assessment, upside=upside)
    effective = engine.effective_policy(composed, downside_policy, upside_policy)
    assert downside_assessment.crisis_state is CrisisState.CRISIS
    assert composed.downside_assessment_id == downside_assessment.assessment_id
    assert composed.upside_assessment_id == upside.assessment_id
    assert effective.allow_new_entries is False
    assert effective.position_size_multiplier == Decimal("0.25")
    assert effective.rotation_readiness is True


def test_upside_event_and_paper_context_round_trip_and_no_external_or_mutation_path(tmp_path):
    event = MarketExtremeEvent("event-1", "v1", MarketExtremeLevel.SECTOR, "TECH", T, None, UpsideExcessState.EUPHORIA, Decimal("0.9"), ("assessment-1",), (UpsideExcessFactor.IPO_INTENSITY,), None, None, (ForwardOutcomeReference(20, "outcome-20", "future-outcome-v1"),), ("source-1",), "event-fingerprint")
    context = PaperTradeUpsideExtremeContext("context-1", "v1", "paper-1", "market-1", "sector-1", "stock-1", UpsideExcessState.NORMAL, UpsideExcessState.EUPHORIA, UpsideExcessState.EUPHORIA, Decimal("0.9"), 0.8, DistributionRisk.EMERGING, ChaseRestriction.DO_NOT_CHASE, LeadershipQuality.HEALTHY, "ipo-1", "narrative-1", ("paper-1",), "context-fingerprint")
    repository = create_core_api_snapshot_repository(DatabaseSettings(DatabaseBackend.SQLITE, f"sqlite:///{tmp_path / 'extremes.db'}"))
    event_snapshot = CoreApiSnapshot("event-snapshot", CoreApiSnapshotFamily.MARKET_EXTREME_EVENT, "v1", "market-extreme-event-v1", "event-snapshot-fingerprint", T, event)
    context_snapshot = CoreApiSnapshot("context-snapshot", CoreApiSnapshotFamily.PAPER_TRADE_UPSIDE_EXTREME_CONTEXT, "v1", "paper-upside-context-v1", "context-snapshot-fingerprint", T, context)
    repository.save_snapshot(event_snapshot)
    repository.save_snapshot(context_snapshot)
    assert repository.get_snapshot(event_snapshot.snapshot_id) == event_snapshot
    assert repository.get_snapshot(context_snapshot.snapshot_id) == context_snapshot
    with pytest.raises(ValueError, match="immutable"):
        repository.save_snapshot(event_snapshot)
    import app.crisis.extremes as extremes
    source = inspect.getsource(extremes).lower()
    assert not any(item in source for item in ("requests.", "httpx.", "urllib", "broker", "demat", "place_order", "approve_strategy", "activate_strategy"))
