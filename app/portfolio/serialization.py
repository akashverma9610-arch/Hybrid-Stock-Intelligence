from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from app.domain.models import StrategyVersionReference
from .models import *


def dumps(value: Any) -> dict[str, Any]:
    return _plain(value)


def portfolio_from(value: dict[str, Any]) -> Portfolio:
    return Portfolio(value["portfolio_id"], value["name"], value["base_currency"], _time(value["created_at"]), _strategy_from(value["strategy_version"]), value["account_reference"], PortfolioStatus(value["status"]), value["metadata"])


def transaction_from(value: dict[str, Any]) -> PortfolioTransaction:
    return PortfolioTransaction(value["transaction_id"], value["portfolio_id"], TransactionType(value["transaction_type"]), _time(value["effective_at"]), _time(value["known_at"]), value["source"], value["provenance_reference"], value["instrument_id"], _decimal(value["quantity"]), _decimal(value["price"]), _decimal(value["gross_amount"]) or Decimal("0"), _decimal(value["fees"]) or Decimal("0"), _decimal(value["taxes"]) or Decimal("0"), _decimal(value["net_cash_impact"]) or Decimal("0"), _optional_time(value["settlement_at"]), value["strategy_reference"], value["signal_reference"])


def corporate_action_from(value: dict[str, Any]) -> CorporateAction:
    return CorporateAction(value["action_id"], value["portfolio_id"], value["instrument_id"], CorporateActionType(value["action_type"]), Decimal(value["ratio"]), _time(value["effective_at"]), _time(value["known_at"]), value["source"], value["provenance_reference"])


def snapshot_from(value: dict[str, Any]) -> PortfolioSnapshot:
    holdings = tuple(_holding_from(x) for x in value["holdings"])
    exposure = PortfolioExposureSummary({k: _decimal(v) for k, v in value["exposure"]["position_allocations"].items()}, _decimal(value["exposure"]["cash_allocation"]), {k: _decimal(v) for k, v in value["exposure"]["sector_exposure"].items()}, value["exposure"]["active_holding_count"], _decimal(value["exposure"]["concentration"]))
    risk = PortfolioRiskSummary(_decimal(value["risk"]["total_heat"]), Decimal(value["risk"]["heat_coverage"]), PortfolioDataStatus(value["risk"]["status"]), {k: _decimal(v) for k, v in value["risk"]["risk_amounts"].items()})
    cash = value["cash"]
    return PortfolioSnapshot(value["snapshot_id"], value["portfolio_id"], _time(value["as_of_timestamp"]), _time(value["source_transaction_cutoff"]), holdings,
        CashPosition(_decimal(cash["amount"]), cash["currency"], Decimal(cash["reserved_amount"]), _time(cash["as_of_timestamp"]), CashState(cash.get("cash_state", "KNOWN"))), tuple(value["market_price_ids"]), _decimal(value["portfolio_equity"]), Decimal(value["realized_pnl"]), _decimal(value["unrealized_pnl"]), Decimal(value["dividends"]), exposure, risk, PortfolioState(value["portfolio_state"]), PortfolioDataStatus(value["data_status"]), value["cost_basis_methodology_version"], _strategy_from(value["strategy_version"]))


def _holding_from(value: dict[str, Any]) -> PortfolioHolding:
    return PortfolioHolding(value["holding_id"], value["instrument_id"], Decimal(value["quantity"]), Decimal(value["average_cost"]), Decimal(value["cost_basis"]), _time(value["acquisition_at"]), Decimal(value["realized_pnl"]), value["sector"], value["strategy_reference"], value["signal_reference"], value["active"], _decimal(value["current_price"]), value["price_observation_id"], _decimal(value["market_value"]), _decimal(value["unrealized_pnl"]), _decimal(value["unrealized_pnl_percent"]), _analytics_from(value["analytics"]) if value["analytics"] else None, value["calendar_holding_days"], value["trading_sessions_held"], _decimal(value["risk_amount"]))


def _analytics_from(value: dict[str, Any]) -> HoldingAnalytics:
    value = dict(value); value["as_of_timestamp"] = _time(value["as_of_timestamp"]); value["known_at"] = _time(value["known_at"]); value["raw_decision_score"] = _decimal(value["raw_decision_score"]); value["diagnostic_ids"] = tuple(value["diagnostic_ids"]); value["structural_stop"] = _decimal(value["structural_stop"]); value["target_1"] = _decimal(value["target_1"]); value["target_2"] = _decimal(value["target_2"]); value["extended_target"] = _decimal(value["extended_target"])
    return HoldingAnalytics(**value)


def _plain(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)): return value
    if isinstance(value, Decimal): return str(value)
    if isinstance(value, datetime): return value.isoformat()
    if isinstance(value, Enum): return value.value
    if isinstance(value, StrategyVersionReference): return {"strategy_id": value.strategy_id, "version": value.version}
    if hasattr(value, "__dataclass_fields__"): return {key: _plain(getattr(value, key)) for key in value.__dataclass_fields__}
    if isinstance(value, dict): return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)): return [_plain(item) for item in value]
    return str(value)


def _decimal(value): return Decimal(value) if value is not None else None
def _time(value): return datetime.fromisoformat(value)
def _optional_time(value): return _time(value) if value else None
def _strategy_from(value): return StrategyVersionReference(value["strategy_id"], value["version"]) if isinstance(value, dict) else value
