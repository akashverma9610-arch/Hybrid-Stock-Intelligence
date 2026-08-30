from datetime import UTC, datetime, timedelta
from decimal import Decimal

import inspect
import pytest

from app.analysis.models import MarketRegime
from app.crisis.engine import (
    CrisisExecutionPolicyService,
    CrisisMarketDislocationEngine,
    CrisisOpportunityScanner,
    CrisisSlippageAssumptionService,
    PortfolioCrisisAssessmentService,
    crisis_dashboard_read_model,
)
from app.crisis.models import (
    CashRecommendationState,
    CrisisAssessmentInput,
    CrisisEvent,
    CrisisFactor,
    CrisisFactorSignal,
    CrisisOpportunityCategory,
    CrisisOpportunityInput,
    CrisisOpportunityPolicy,
    CrisisPolicySettings,
    CrisisSignalDisposition,
    CrisisSlippagePolicy,
    CrisisState,
    CrisisTransitionContext,
    MarketStatus,
    PaperTradeCrisisContext,
    PortfolioCrisisInput,
    PortfolioHoldingAction,
    SlippageModelMode,
)
from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily
from app.storage.database import DatabaseBackend, DatabaseSettings
from app.storage.repository_factory import create_core_api_snapshot_repository


T = datetime(2026, 8, 23, 10, tzinfo=UTC)
POLICY = CrisisPolicySettings(
    "crisis-policy-v1", 2, Decimal("0.25"), Decimal("0.50"), Decimal("0.80"), Decimal("0.95"), 2, 2, 0.49
)


def factor(
    item: CrisisFactor,
    *,
    triggered: bool = False,
    severity: str | None = None,
    available: bool = True,
    confidence: float | None = 0.9,
):
    return CrisisFactorSignal(
        item, available, triggered, Decimal(severity) if severity is not None else None,
        confidence, T, T, (f"evidence-{item.value}",), (f"source-{item.value}",), None,
    )


def assessment_input(*signals, assessment_id="assessment", critical=(CrisisFactor.MARKET_BREADTH,)):
    return CrisisAssessmentInput(
        assessment_id, "NIFTY50", "regime-1", T, T, MarketStatus.TRADING_NORMAL,
        tuple(signals), critical, ("market-snapshot-1",),
    )


def test_crisis_states_multifactor_severe_override_and_hysteresis_are_deterministic():
    engine = CrisisMarketDislocationEngine(POLICY)
    normal = engine.assess(assessment_input(factor(CrisisFactor.MARKET_BREADTH), factor(CrisisFactor.INDEX_PRICE_VELOCITY)))
    elevated = engine.assess(assessment_input(factor(CrisisFactor.MARKET_BREADTH, triggered=True, severity="0.40")))
    stress = engine.assess(assessment_input(factor(CrisisFactor.MARKET_BREADTH, triggered=True, severity="0.60"), factor(CrisisFactor.ATR_EXPANSION, triggered=True, severity="0.60")))
    crisis = engine.assess(assessment_input(factor(CrisisFactor.MARKET_BREADTH, triggered=True, severity="0.90"), factor(CrisisFactor.ATR_EXPANSION, triggered=True, severity="0.90")))
    direct = engine.assess(
        assessment_input(factor(CrisisFactor.GAP_MAGNITUDE, triggered=True, severity="0.99")),
        CrisisTransitionContext(CrisisState.NORMAL, T - timedelta(days=1), 0),
    )
    sticky = engine.assess(
        assessment_input(factor(CrisisFactor.MARKET_BREADTH), factor(CrisisFactor.ATR_EXPANSION)),
        CrisisTransitionContext(CrisisState.STRESS, T - timedelta(days=1), 0),
    )
    assert (normal.crisis_state, elevated.crisis_state, stress.crisis_state, crisis.crisis_state, direct.crisis_state) == (
        CrisisState.NORMAL, CrisisState.ELEVATED_RISK, CrisisState.STRESS, CrisisState.CRISIS, CrisisState.CRISIS,
    )
    assert direct.transition_reason == "SEVERE_ESCALATION_OVERRIDE"
    assert sticky.crisis_state is CrisisState.STRESS
    assert "HYSTERESIS_CONFIRMATION_PENDING" in sticky.warnings


def test_stabilization_recovery_and_stale_critical_data_are_explicit():
    engine = CrisisMarketDislocationEngine(POLICY)
    stabilization = engine.assess(
        assessment_input(
            factor(CrisisFactor.SELLING_VELOCITY_SLOWING, triggered=True, severity="0.10"),
            factor(CrisisFactor.BREADTH_IMPROVING, triggered=True, severity="0.10"),
        ),
        CrisisTransitionContext(CrisisState.CRISIS, T - timedelta(days=3), 2),
    )
    recovery = engine.assess(
        assessment_input(factor(CrisisFactor.SELLING_VELOCITY_SLOWING, triggered=True, severity="0.10")),
        CrisisTransitionContext(CrisisState.STABILIZING, T - timedelta(days=1), 2),
    )
    stale = engine.assess(
        assessment_input(
            factor(CrisisFactor.MARKET_BREADTH, available=False, confidence=None),
            factor(CrisisFactor.INDEX_PRICE_VELOCITY, triggered=True, severity="0.70"),
        )
    )
    assert stabilization.crisis_state is CrisisState.STABILIZING
    assert recovery.crisis_state is CrisisState.RECOVERY
    assert stale.confidence is not None and stale.confidence <= POLICY.critical_data_high_confidence_floor
    assert "CRITICAL_MARKET_DATA_UNAVAILABLE" in stale.warnings
    assert CrisisFactor.MARKET_BREADTH in stale.unavailable_factors


def test_execution_policy_keeps_scores_confidence_and_six_gates_separate_and_cash_valid():
    assessment = CrisisMarketDislocationEngine(POLICY).assess(
        assessment_input(factor(CrisisFactor.MARKET_BREADTH, triggered=True, severity="0.90"), factor(CrisisFactor.ATR_EXPANSION, triggered=True, severity="0.90"))
    )
    service = CrisisExecutionPolicyService()
    crisis = service.resolve(assessment, policy_version="execution-overlay-v1")
    signal = service.apply_to_signal(crisis, decision_score=Decimal("8.7"), confidence=0.96, six_gate_eligibility="EXECUTABLE")
    recovery_assessment = CrisisMarketDislocationEngine(POLICY).assess(
        assessment_input(factor(CrisisFactor.SELLING_VELOCITY_SLOWING, triggered=True, severity="0.1")),
        CrisisTransitionContext(CrisisState.STABILIZING, T - timedelta(days=1), 2),
    )
    recovery = service.resolve(recovery_assessment, policy_version="execution-overlay-v1")
    assert crisis.allow_new_entries is False
    assert crisis.cash_preference is CashRecommendationState.PRESERVED_OPTIONALITY
    assert signal.disposition is CrisisSignalDisposition.DEFERRED
    assert signal.decision_score == Decimal("8.7") and signal.confidence == 0.96
    assert signal.six_gate_eligibility == "EXECUTABLE"
    assert recovery.maximum_position_size_multiplier > crisis.maximum_position_size_multiplier
    assert recovery.maximum_position_size_multiplier < Decimal("1")
    assert "NO_BLANKET_LIQUIDATION" in crisis.warnings and "NO_AUTOMATIC_DIP_BUYING" in crisis.warnings


def test_opportunity_portfolio_and_gap_aware_slippage_are_read_only_contracts():
    assessment = CrisisMarketDislocationEngine(POLICY).assess(
        assessment_input(factor(CrisisFactor.MARKET_BREADTH, triggered=True, severity="0.90"), factor(CrisisFactor.ATR_EXPANSION, triggered=True, severity="0.90"))
    )
    override = CrisisExecutionPolicyService().resolve(assessment, policy_version="execution-overlay-v1")
    opportunity = CrisisOpportunityScanner(CrisisOpportunityPolicy("opportunity-v1", Decimal("-0.12"), Decimal("0.15"), Decimal("-0.05"))).assess(
        CrisisOpportunityInput("candidate-1", "RS-SURVIVOR", assessment.assessment_id, Decimal("-0.18"), Decimal("0.20"), True, Decimal("-0.03"), False, False, False, ("rs-evidence",), ("stock-analysis-1",))
    )
    portfolio_input = PortfolioCrisisInput(
        "portfolio-1", assessment.assessment_id, Decimal("-0.15"), Decimal("0.45"), Decimal("0.55"), True,
        False, Decimal("100"), {"holding-1": PortfolioHoldingAction.REVIEW, "holding-2": PortfolioHoldingAction.HOLD}, ("portfolio-evidence",),
    )
    portfolio = PortfolioCrisisAssessmentService().assess(portfolio_input, override)
    fill = CrisisSlippageAssumptionService(CrisisSlippagePolicy("slippage-v1", Decimal("0"), Decimal("2"), Decimal("5"))).stop_fill(
        assumption_id="gap-stop-1", mode=SlippageModelMode.CRISIS, planned_stop=Decimal("950"), market_open=Decimal("925"), source_bar_ids=("gap-bar",),
    )
    assert CrisisOpportunityCategory.EXCEPTIONAL_RELATIVE_STRENGTH in opportunity.categories
    assert opportunity.disposition.value == "PRIORITY_RESEARCH"
    assert "holding-1" in portfolio.urgent_review_holding_ids
    assert "holding-2" not in portfolio.urgent_review_holding_ids
    assert portfolio_input.holding_actions["holding-2"] is PortfolioHoldingAction.HOLD
    assert fill.gap_through_stop and fill.expected_fill == Decimal("950") and fill.simulated_fill == Decimal("920")
    assert "GAP_THROUGH_STOP_NO_PLANNED_STOP_FILL_ASSUMPTION" in fill.warnings


def test_crisis_context_event_snapshot_round_trip_and_dashboard_are_versioned(tmp_path):
    assessment = CrisisMarketDislocationEngine(POLICY).assess(
        assessment_input(factor(CrisisFactor.MARKET_BREADTH, triggered=True, severity="0.90"), factor(CrisisFactor.ATR_EXPANSION, triggered=True, severity="0.90"))
    )
    override = CrisisExecutionPolicyService().resolve(assessment, policy_version="execution-overlay-v1")
    context = PaperTradeCrisisContext(
        "paper-crisis-1", "v1", "paper-1", assessment.assessment_id, None, None, assessment.crisis_state, None, None,
        SlippageModelMode.CRISIS, Decimal("950"), Decimal("920"), False,
        (CrisisOpportunityCategory.EXCEPTIONAL_RELATIVE_STRENGTH,), override.entry_restriction_level, ("paper-1",), "context-fingerprint",
    )
    event = CrisisEvent(
        "event-1", "v1", "NIFTY50", T, None, assessment.crisis_state, assessment.severity_score,
        (assessment.assessment_id,), assessment.triggered_factors, Decimal("-0.18"), "expanded", "collapsed", ("TECH",), None,
        ("market-snapshot-1",), "event-fingerprint",
    )
    repository = create_core_api_snapshot_repository(DatabaseSettings(DatabaseBackend.SQLITE, f"sqlite:///{tmp_path / 'crisis.db'}"))
    context_snapshot = CoreApiSnapshot("snapshot-context", CoreApiSnapshotFamily.PAPER_TRADE_CRISIS_CONTEXT, "v1", "paper-crisis-context-v1", "snapshot-context-fingerprint", T, context)
    event_snapshot = CoreApiSnapshot("snapshot-event", CoreApiSnapshotFamily.CRISIS_EVENT, "v1", "crisis-event-v1", "snapshot-event-fingerprint", T, event)
    repository.save_snapshot(context_snapshot)
    repository.save_snapshot(event_snapshot)
    dashboard = crisis_dashboard_read_model(assessment, override)
    assert repository.get_snapshot(context_snapshot.snapshot_id) == context_snapshot
    assert repository.get_snapshot(event_snapshot.snapshot_id) == event_snapshot
    with pytest.raises(ValueError, match="immutable"):
        repository.save_snapshot(event_snapshot)
    assert dashboard.state is CrisisState.CRISIS and dashboard.label.value == "CRISIS"
    assert not hasattr(dashboard, "severity_score")
    assert MarketRegime.PANIC.value == "panic"  # Normal market-regime contract remains distinct/unchanged.


def test_crisis_package_has_no_provider_broker_or_strategy_mutation_path():
    import app.crisis.engine as crisis_engine

    source = inspect.getsource(crisis_engine)
    forbidden = ("requests.", "httpx.", "urllib", "broker", "demat", "place_order", "activate_strategy", "approve_strategy")
    assert not any(item in source.lower() for item in forbidden)
