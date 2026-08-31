from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.main import create_app
from app.portfolio.models import CashPosition, HoldingAnalytics, PortfolioDataStatus, PortfolioExposureSummary, PortfolioHolding, PortfolioRiskSummary, PortfolioSnapshot, PortfolioState
from app.portfolio.sell_side_policy import CURRENT_FROZEN_PORTFOLIO_SELL_SIDE_DECISION_POLICY as POLICY
from app.portfolio.sell_side_runtime import (
    CapitalEfficiencyState, EvidenceFreshness, PortfolioSellSideDecisionAuditService,
    PortfolioSellSideInput, evaluate_portfolio_sell_side_action,
)
from app.rotation.models import RotationDecisionState, RotationExecutionEligibility
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository
from app.storage.core_api_snapshot_repository import CoreApiSnapshotFamily


T = datetime(2026, 8, 30, tzinfo=UTC)


def _input(*, trading="VALID", invalidation="INTACT", rotation=RotationDecisionState.NO_ACTION,
           rotation_present=True, conflicted=False, comparable=True, stale=False, future=False, adjustment=Decimal("0")):
    analytics = HoldingAnalytics("ABC", T if not stale else datetime(2026, 8, 29, tzinfo=UTC), datetime(2026, 8, 31, tzinfo=UTC) if future else T, trading_thesis=trading, invalidation_status=invalidation)
    holding = PortfolioHolding("holding-ABC", "ABC", Decimal("10"), Decimal("100"), Decimal("1000"), T, Decimal("0"), "TECH", None, None, True, Decimal("110"), "price", Decimal("1100"), Decimal("100"), Decimal(".1"), analytics, 1, 1, Decimal("10"))
    snapshot = PortfolioSnapshot("portfolio-T", "portfolio", T, T, (holding,), CashPosition(Decimal("0"), "INR", Decimal("0"), T), (), Decimal("1100"), Decimal("0"), Decimal("100"), Decimal("0"), PortfolioExposureSummary({}, Decimal("0"), {}, 1, Decimal("1")), PortfolioRiskSummary(Decimal(".1"), Decimal("1"), PortfolioDataStatus.COMPLETE, {}), PortfolioState.FULLY_INVESTED, PortfolioDataStatus.COMPLETE, "v1", None)
    evaluation = None
    if rotation_present:
        comparison = SimpleNamespace(holding_instrument_id="ABC", result=rotation)
        context = SimpleNamespace(as_of_timestamp=T, holdings=(SimpleNamespace(instrument_id="ABC", capital_velocity_adjustment=adjustment),))
        evaluation = SimpleNamespace(decision=rotation, comparisons=(comparison,), context=context, evaluation_id="rotation-T")
    return PortfolioSellSideInput(snapshot, holding, evaluation, "shared-brain-T", conflicted, comparable)


def test_hold_for_intact_profitable_or_losing_holding_without_rotation() -> None:
    assert evaluate_portfolio_sell_side_action(_input()).action.value == "HOLD"
    value = _input()
    losing = value.holding.__class__(**{field: getattr(value.holding, field) for field in value.holding.__dataclass_fields__} | {"unrealized_pnl": Decimal("-100"), "unrealized_pnl_percent": Decimal("-.1")})
    assert evaluate_portfolio_sell_side_action(PortfolioSellSideInput(value.portfolio_snapshot, losing, value.rotation_evaluation, "shared-brain-T")).action.value == "HOLD"


def test_invalidated_rotation_and_cash_priority() -> None:
    assert evaluate_portfolio_sell_side_action(_input(trading="INVALIDATED", invalidation="TRIGGERED", rotation=RotationDecisionState.ROTATE_CANDIDATE_PREFERRED)).action.value == "ROTATE"
    assert evaluate_portfolio_sell_side_action(_input(trading="INVALIDATED", invalidation="TRIGGERED")).action.value == "EXIT_TO_CASH"


def test_cash_unknown_comparison_never_authorizes_rotate_and_does_not_block_exit_to_cash() -> None:
    value = _input(trading="INVALIDATED", invalidation="TRIGGERED", rotation=RotationDecisionState.COMPARISON_AVAILABLE_EXECUTION_BLOCKED)
    value.rotation_evaluation.execution_eligibility = RotationExecutionEligibility.EXECUTION_BLOCKED_CASH_UNKNOWN
    decision = evaluate_portfolio_sell_side_action(value)
    assert decision.action.value == "REVIEW_REQUIRED" and "CASH_UNKNOWN_EXECUTION_BLOCKED" in decision.blockers
    exit_value = _input(trading="INVALIDATED", invalidation="TRIGGERED", rotation=RotationDecisionState.CASH_PREFERRED)
    exit_value.rotation_evaluation.execution_eligibility = RotationExecutionEligibility.EXECUTION_BLOCKED_CASH_UNKNOWN
    assert evaluate_portfolio_sell_side_action(exit_value).action.value == "EXIT_TO_CASH"


def test_fail_closed_stale_conflicted_missing_or_unresolved_replacement() -> None:
    assert evaluate_portfolio_sell_side_action(_input(stale=True)).action.value == "REVIEW_REQUIRED"
    assert evaluate_portfolio_sell_side_action(_input(future=True)).action.value == "REVIEW_REQUIRED"
    assert evaluate_portfolio_sell_side_action(_input(conflicted=True)).action.value == "REVIEW_REQUIRED"
    assert evaluate_portfolio_sell_side_action(_input(rotation_present=False)).action.value == "REVIEW_REQUIRED"


def test_trim_firewall_and_capital_efficiency_are_non_authorizing() -> None:
    value = evaluate_portfolio_sell_side_action(_input(adjustment=Decimal("-.2")))
    assert value.action.value == "HOLD" and value.capital_efficiency_state is CapitalEfficiencyState.CAPITAL_INEFFICIENT
    for condition in ("profit", "target", "valuation", "concentration", "extension"):
        assert "TRIM" not in value.action.value, condition


def test_policy_mismatch_fails_closed_and_fingerprint_is_deterministic() -> None:
    mismatch = SimpleNamespace(policy_id=POLICY.policy_id, version=POLICY.version, fingerprint="wrong")
    first = evaluate_portfolio_sell_side_action(_input(), policy=mismatch)
    second = evaluate_portfolio_sell_side_action(_input())
    assert first.action.value == "REVIEW_REQUIRED" and "POLICY_FINGERPRINT_MISMATCH" in first.blockers
    assert second.fingerprint == evaluate_portfolio_sell_side_action(_input()).fingerprint


def test_append_only_audit_is_idempotent_and_emits_factual_event(tmp_path: Path) -> None:
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "sell-side.db")
    decision = evaluate_portfolio_sell_side_action(_input())
    service = PortfolioSellSideDecisionAuditService(repository)
    assert service.persist(decision) == decision
    assert service.persist(decision) == decision
    stored = repository.get_snapshot("sell-side-decision:" + decision.decision_id)
    assert stored is not None and stored.payload == decision
    events = repository.list_snapshots(CoreApiSnapshotFamily.DECISION_OUTCOME_LINK)
    assert len(events) == 1 and events[0].payload.outcome_type == "SELL_SIDE_DECISION_EVENT"


def test_no_current_canonical_portfolio_is_a_safe_read_only_api_state() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/portfolio/sell-side")
    assert response.status_code == 200
    assert response.json()["status"] == "NO_CURRENT_CANONICAL_PORTFOLIO"
