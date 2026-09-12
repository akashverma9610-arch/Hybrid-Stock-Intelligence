from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from tests.fixtures.gate_provenance import synthetic_evaluate

from app.gates.engine import (
    ActionContext, ExchangeCalendar, ExecutionGateEngine, GateInput, GateOutcome, PortfolioExposure,
    SurveillanceObservation, TradeManagementPlan,
)
from app.gates.production_policy import (
    approved_six_gates_production_policy, policy_from_dict, policy_to_dict,
    selected_production_gate_engine,
)
from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository


T = datetime(2026, 9, 1, 10, tzinfo=UTC)
CALENDAR = ExchangeCalendar("nse-v1", frozenset({date(2026, 8, 31)}))


def _policy():
    return approved_six_gates_production_policy(approved_at=T, effective_at=T)


def _input(**changes):
    base = GateInput(
        "canonical-score", Decimal("8"), "pit-snapshot", T, Decimal("6"), Decimal("5"), Decimal("1"),
        holding_entry_date=date(2026, 8, 10), atr_expansion=Decimal("1.1"),
        surveillance=SurveillanceObservation("nse-surveillance", T - timedelta(days=4), "NSE", True, 0, 0, Decimal("0.10"), ("nse:surveillance",)),
        trade_plan=TradeManagementPlan("setup", Decimal("0.50"), Decimal("0.50"), True, True, "T1 de-risk", "structural", "v1", "six-gates-production-v1"),
        exposure=PortfolioExposure(Decimal("100"), Decimal("1"), Decimal("1"), Decimal("0.20"), Decimal("0.30"), ("portfolio",)),
        earnings_scheduled_at=T + timedelta(days=10), earnings_schedule_verified_at=T,
        evidence_ids=("evidence",), diagnostic_ids=("diagnostic",),
    )
    return replace(base, **changes)


def _decision(value, gate_id):
    return next(item for item in value.decisions if item.gate_id == gate_id)


def test_human_approval_is_deterministic_immutable_and_reopens(tmp_path) -> None:
    policy = _policy()
    assert policy.reviewer_authority == "HUMAN_APPROVED"
    assert policy.gate_config.unresolved() == ()
    assert policy_from_dict(policy_to_dict(policy)) == policy
    repo = SQLiteStrategyGovernanceRepository(tmp_path / "policy.db")
    assert repo.save_six_gates_production_policy(policy) == policy
    assert repo.save_six_gates_production_policy(policy) == policy
    assert repo.selected_six_gates_production_policy(as_of=T) == policy
    repo.close()
    reopened = SQLiteStrategyGovernanceRepository(tmp_path / "policy.db")
    assert reopened.get_six_gates_production_policy(policy.approval_id) == policy
    assert selected_production_gate_engine(repository=reopened, calendar=CALENDAR, as_of=T).config == policy.gate_config
    assert reopened._connection.execute("SELECT COUNT(*) FROM execution_gate_evaluations").fetchone()[0] == 0
    assert reopened._connection.execute("SELECT COUNT(*) FROM canonical_execution_gate_evaluations").fetchone()[0] == 0
    reopened.close()


def test_exact_approved_values_and_friction_require_explicit_user_costs() -> None:
    policy = _policy()
    config = policy.gate_config
    assert (config.min_score_advantage, config.net_economic_hurdle, config.require_economic_hurdle) == (Decimal("1.00"), Decimal("0.00"), True)
    assert (config.inactivity_sessions, config.atr_expansion_threshold, config.velocity_penalty) == (12, Decimal("1.0"), Decimal("-0.50"))
    assert (config.disallowed_asm_stage, config.disallow_gsm, config.circuit_limit_threshold, config.surveillance_max_age_days) == (2, True, Decimal("0.05"), 4)
    assert (config.initial_tranche, config.t1_reduction, config.require_breakeven_plan) == (Decimal("0.50"), Decimal("0.50"), True)
    assert (config.max_total_heat, config.max_stock_allocation, config.max_sector_allocation, config.heat_methodology_version) == (Decimal("0.06"), Decimal("0.25"), Decimal("0.35"), "portfolio-structural-risk-heat-v1")
    assert config.blackout_sessions == 5
    assert policy.friction_model.modeled_switching_friction(
        purchase_turnover=Decimal("100000"), sale_turnover=Decimal("100000"), brokerage=None,
        slippage=Decimal("1"), capital_gains_tax=Decimal("1"), gst_taxable_services=Decimal("1"),
    ) is None
    assert policy.friction_model.modeled_switching_friction(
        purchase_turnover=Decimal("100000"), sale_turnover=Decimal("100000"), brokerage=Decimal("10"),
        slippage=Decimal("10"), capital_gains_tax=Decimal("10"), gst_taxable_services=Decimal("10"),
    ) > 0


def test_gate_one_is_strictly_positive_and_gate_three_uses_eligible_sessions() -> None:
    policy = _policy()
    engine = ExecutionGateEngine(policy.gate_config, CALENDAR)
    zero = synthetic_evaluate(engine, instrument_id="NSE:TEST", strategy_version="v1", registry_version="v1", scoring_configuration_version="v1", action_context=ActionContext.ROTATE_IN, as_of_timestamp=T, evaluated_at=T, inputs=_input(expected_incremental_return=Decimal("1"), modeled_switching_friction=Decimal("1")))
    assert _decision(zero, "GATE_1_ROTATION").outcome is GateOutcome.FAIL
    weekend = synthetic_evaluate(engine, instrument_id="NSE:TEST", strategy_version="v1", registry_version="v1", scoring_configuration_version="v1", action_context=ActionContext.FRESH_ENTRY, as_of_timestamp=T, evaluated_at=T, inputs=_input())
    assert _decision(weekend, "GATE_3_SURVEILLANCE").outcome is GateOutcome.PASS
    for observation in (
        replace(_input().surveillance, asm_stage=2), replace(_input().surveillance, gsm_stage=1), replace(_input().surveillance, circuit_limit=Decimal("0.05")),
    ):
        result = synthetic_evaluate(engine, instrument_id="NSE:TEST", strategy_version="v1", registry_version="v1", scoring_configuration_version="v1", action_context=ActionContext.FRESH_ENTRY, as_of_timestamp=T, evaluated_at=T, inputs=_input(surveillance=observation))
        assert _decision(result, "GATE_3_SURVEILLANCE").outcome is GateOutcome.FAIL


def test_tranche_heat_earnings_and_pit_contract_fail_closed() -> None:
    policy = _policy()
    engine = ExecutionGateEngine(policy.gate_config, CALENDAR)
    invalid = synthetic_evaluate(engine, instrument_id="NSE:TEST", strategy_version="v1", registry_version="v1", scoring_configuration_version="v1", action_context=ActionContext.FRESH_ENTRY, as_of_timestamp=T, evaluated_at=T, inputs=_input(trade_plan=replace(_input().trade_plan, t1_reduction=Decimal("0.40")), exposure=None))
    assert _decision(invalid, "GATE_4_TRADE_PLAN").outcome is GateOutcome.FAIL
    assert _decision(invalid, "GATE_5_HEAT").outcome is GateOutcome.INSUFFICIENT_DATA
    near = synthetic_evaluate(engine, instrument_id="NSE:TEST", strategy_version="v1", registry_version="v1", scoring_configuration_version="v1", action_context=ActionContext.FRESH_ENTRY, as_of_timestamp=T, evaluated_at=T, inputs=_input(earnings_scheduled_at=T + timedelta(days=4)))
    managed = synthetic_evaluate(engine, instrument_id="NSE:TEST", strategy_version="v1", registry_version="v1", scoring_configuration_version="v1", action_context=ActionContext.HOLD_EXISTING, as_of_timestamp=T, evaluated_at=T, inputs=_input(earnings_scheduled_at=T + timedelta(days=4)))
    assert _decision(near, "GATE_6_EARNINGS").outcome is GateOutcome.FAIL
    assert _decision(managed, "GATE_6_EARNINGS").outcome is GateOutcome.PASS
    with pytest.raises(ValueError, match="LOOKAHEAD"):
        policy.pit_contract.validate(decision_score_as_of=T, portfolio_snapshot_as_of=T + timedelta(seconds=1), setup_as_of=None, surveillance_as_of=T, earnings_verified_as_of=T, friction_policy_effective_at=policy.friction_model.effective_at, execution_gate_as_of=T)
