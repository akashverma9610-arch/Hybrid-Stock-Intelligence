from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from app.portfolio.serialization import dumps
from .models import *


def loads(value: dict) -> PortfolioRotationEvaluation:
    context = _context(value["context"])
    holdings = tuple(_holding(x) for x in value["ranked_holdings"])
    ranks = tuple(RankedCandidate(_candidate(x["candidate"]), x["rank"], x["ranking_inputs"], x["tie_break_reason"]) for x in value["ranked_candidates"])
    comparisons = tuple(_comparison(x) for x in value["comparisons"])
    return PortfolioRotationEvaluation(value["evaluation_id"], context, value["rotation_configuration_version"], holdings, ranks,
        tuple(value["blocked_candidate_ids"]), value["weakest_holding_id"], value["strongest_holding_id"], comparisons,
        RotationStance(value["stance"]), value["preferred_candidate_id"], RotationDecisionState(value["decision"]), tuple(value["warnings"]),
        RotationComparisonStatus(value.get("comparison_status", "NO_ELIGIBLE_REPLACEMENT")),
        RotationExecutionEligibility(value.get("execution_eligibility", "EXECUTION_ELIGIBLE")))


def _context(value):
    return RotationEvaluationContext(value["portfolio_snapshot_id"], value["strategy_version"], value["registry_version"], value["scoring_configuration_version"], value["gate_configuration_version"], _time(value["as_of_timestamp"]), tuple(_holding(x) for x in value["holdings"]), _decimal(value["cash_amount"]), tuple(_candidate(x) for x in value["candidates"]), value["transaction_friction_model_version"], _time(value["last_rotation_at"]) if value["last_rotation_at"] else None, value.get("cash_state", "KNOWN"))


def _candidate(value):
    value = dict(value)
    for key in ("as_of_timestamp", "known_at"): value[key] = _time(value[key])
    for key in ("raw_decision_score", "structural_risk_reward", "modeled_switching_friction", "expected_incremental_benefit"): value[key] = _decimal(value[key])
    for key in ("warnings", "evidence_ids"): value[key] = tuple(value[key])
    return RotationCandidate(**value)


def _holding(value):
    value = dict(value)
    for key in ("as_of_timestamp", "known_at"): value[key] = _time(value[key])
    for key in ("raw_decision_score", "structural_risk_reward", "current_forward_risk_reward", "allocation", "heat", "capital_velocity_adjustment", "current_market_value", "unrealized_pnl", "structural_stop"): value[key] = _decimal(value[key])
    for key in ("warnings", "evidence_ids"): value[key] = tuple(value[key])
    return RotationHoldingState(**value)


def _comparison(value):
    value = dict(value)
    for key in ("holding_comparison_score", "candidate_score", "score_gap", "hurdle", "holding_forward_risk_reward", "candidate_risk_reward"): value[key] = _decimal(value[key])
    for key in ("reasons_for", "reasons_against", "warnings"): value[key] = tuple(value[key])
    value["result"] = RotationDecisionState(value["result"])
    return RotationComparison(**value)


def _decimal(value): return Decimal(value) if value is not None else None
def _time(value): return datetime.fromisoformat(value)
