from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from app.backtest.serialization import dump
from app.historical.models import HistoricalPartition, PartitionType
from .walk_forward import (
    OOSStartingCapitalMethodology, StrategyCandidate, WalkForwardMode, WalkForwardPlan,
    WalkForwardRun, WalkForwardRunStatus, WalkForwardStatus, WalkForwardWindow,
    WalkForwardWindowResult, WalkForwardWindowResultStatus,
)


def plan_from(value: dict[str, Any]) -> WalkForwardPlan:
    value = dict(value); value["mode"] = WalkForwardMode(value["mode"]); value["generated_at"] = datetime.fromisoformat(value["generated_at"]); value["warnings"] = tuple(value["warnings"])
    return WalkForwardPlan(**value)


def candidate_from(value: dict[str, Any]) -> StrategyCandidate:
    return StrategyCandidate(**dict(value))


def _partition(value: dict[str, Any]) -> HistoricalPartition:
    value = dict(value); value["partition_type"] = PartitionType(value["partition_type"]); value["start"] = datetime.fromisoformat(value["start"]); value["end"] = datetime.fromisoformat(value["end"]); value["created_at"] = datetime.fromisoformat(value["created_at"])
    return HistoricalPartition(**value)


def window_from(value: dict[str, Any]) -> WalkForwardWindow:
    value = dict(value); value["train"] = _partition(value["train"]); value["validation"] = _partition(value["validation"]) if value["validation"] is not None else None; value["test"] = _partition(value["test"]); value["selection_timestamp"] = datetime.fromisoformat(value["selection_timestamp"]) if value.get("selection_timestamp") else None; value["status"] = WalkForwardStatus(value["status"]); value["warnings"] = tuple(value["warnings"])
    return WalkForwardWindow(**value)


def run_from(value: dict[str, Any]) -> WalkForwardRun:
    value = dict(value); value["ordered_window_ids"] = tuple(value["ordered_window_ids"]); value["candidate_ids"] = tuple(value["candidate_ids"]); value["status"] = WalkForwardRunStatus(value["status"]); value["started_at"] = datetime.fromisoformat(value["started_at"]); value["completed_at"] = datetime.fromisoformat(value["completed_at"]) if value["completed_at"] else None; value["warnings"] = tuple(value["warnings"])
    return WalkForwardRun(**value)


def result_from(value: dict[str, Any]) -> WalkForwardWindowResult:
    value = dict(value)
    for key in ("selection_timestamp", "test_start", "test_end"):
        value[key] = datetime.fromisoformat(value[key])
    for key in ("starting_equity", "ending_equity", "absolute_return", "max_drawdown", "sharpe", "sortino", "expectancy", "profit_factor", "win_rate", "total_costs"):
        if value[key] is not None:
            value[key] = Decimal(value[key])
    value["selection_evidence_ids"] = tuple(value["selection_evidence_ids"]); value["oos_starting_capital_methodology"] = OOSStartingCapitalMethodology(value["oos_starting_capital_methodology"]); value["status"] = WalkForwardWindowResultStatus(value["status"]); value["warnings"] = tuple(value["warnings"])
    return WalkForwardWindowResult(**value)


__all__ = ["dump", "plan_from", "candidate_from", "window_from", "run_from", "result_from"]
