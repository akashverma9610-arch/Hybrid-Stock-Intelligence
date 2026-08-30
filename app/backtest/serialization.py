from __future__ import annotations

from dataclasses import fields, is_dataclass
from datetime import datetime, time
from decimal import Decimal
from enum import Enum
from typing import Any, Mapping

from .models import (
    BacktestDataGapBehavior, BacktestDataGapPolicy, BacktestEvent,
    BacktestEventType, BacktestReplayStep, BacktestRun, BacktestRunStatus,
    EvaluationLabel, ExecutionTimingPolicy, HistoricalAnalyticalEvaluation,
    HistoricalAnalyticalSnapshot, HistoricalAnalyticalStatus, ReplayFrequency, ReplaySchedule,
    HistoricalHoldingGateContext, HistoricalPortfolioGateEvaluation,
    HistoricalRotationCandidateContext, HistoricalRotationHistory, HistoricalRotationEvaluation,
    HistoricalSignalReplayReference, HistoricalPaperReplayReference, HistoricalTriggerTimingContext,
    HistoricalExecutionTimingContext, ExecutionTimingStatus,
    SignalConfigSnapshot, PaperTradingConfigSnapshot,
    HistoricalCapitalAllocation, HistoricalPaperLedgerLink, FrozenSizingSpecification, HistoricalEquityPoint, HistoricalEquitySeries,
    ReplayStepStatus,
)
from app.historical.models import DatasetQuality


def dump(value: object) -> dict[str, Any]:
    return _plain(value)


def _plain(value: object) -> Any:
    if isinstance(value, (datetime, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {item.name: _plain(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def schedule_from(value: dict[str, Any]) -> ReplaySchedule:
    return ReplaySchedule(
        value["schedule_id"], value["version"], ReplayFrequency(value["frequency"]), value["timezone"],
        value["exchange_calendar_reference"], value["evaluation_cutoff_semantics"],
        ExecutionTimingPolicy(value["execution_timing_policy"]), datetime.fromisoformat(value["start"]),
        datetime.fromisoformat(value["end"]), tuple(value["warnings"]), time.fromisoformat(value["daily_close_time"]),
    )


def gap_policy_from(value: dict[str, Any]) -> BacktestDataGapPolicy:
    return BacktestDataGapPolicy(value["policy_id"], value["version"], BacktestDataGapBehavior(value["behavior"]), tuple(value["warnings"]))


def run_from(value: dict[str, Any]) -> BacktestRun:
    value = dict(value)
    for key in ("evaluation_start", "evaluation_end", "created_at", "completed_at"):
        if value[key] is not None:
            value[key] = datetime.fromisoformat(value[key])
    value["initial_paper_capital"] = Decimal(value["initial_paper_capital"])
    value["random_seeds"] = tuple(value["random_seeds"])
    value["status"] = BacktestRunStatus(value["status"])
    value["quality"] = DatasetQuality(value["quality"])
    value["evaluation_label"] = EvaluationLabel(value["evaluation_label"])
    value["warnings"] = tuple(value["warnings"])
    value["methodology_notes"] = tuple(value["methodology_notes"])
    return BacktestRun(**value)


def step_from(value: dict[str, Any]) -> BacktestReplayStep:
    value = dict(value)
    value["evaluation_timestamp"] = datetime.fromisoformat(value["evaluation_timestamp"])
    value["status"] = ReplayStepStatus(value["status"])
    value["snapshot_references"] = tuple(value["snapshot_references"])
    value["warnings"] = tuple(value["warnings"])
    return BacktestReplayStep(**value)


def event_from(value: dict[str, Any]) -> BacktestEvent:
    value = dict(value)
    for key in ("event_timestamp", "evaluation_timestamp", "created_at"):
        value[key] = datetime.fromisoformat(value[key])
    value["event_type"] = BacktestEventType(value["event_type"])
    value["referenced_artifact_ids"] = tuple(value["referenced_artifact_ids"])
    return BacktestEvent(**value)


def historical_snapshot_from(value: dict[str, Any]) -> HistoricalAnalyticalSnapshot:
    value = dict(value); value["evaluation_timestamp"] = datetime.fromisoformat(value["evaluation_timestamp"])
    for key in ("selected_input_ids", "latest_eligible_input_ids", "provenance_references", "missing_data_fields", "warnings"):
        value[key] = tuple(value[key])
    return HistoricalAnalyticalSnapshot(**value)


def historical_evaluation_from(value: dict[str, Any]) -> HistoricalAnalyticalEvaluation:
    value = dict(value); value["evaluation_timestamp"] = datetime.fromisoformat(value["evaluation_timestamp"])
    for key in ("diagnostic_result_ids", "warnings", "insufficient_reasons"):
        value[key] = tuple(value[key])
    value["status"] = HistoricalAnalyticalStatus(value["status"])
    return HistoricalAnalyticalEvaluation(**value)


def holding_gate_context_from(value: dict[str, Any]) -> HistoricalHoldingGateContext:
    value=dict(value); value["warnings"]=tuple(value["warnings"]); return HistoricalHoldingGateContext(**value)


def portfolio_gate_evaluation_from(value: dict[str, Any]) -> HistoricalPortfolioGateEvaluation:
    value=dict(value); value["evaluation_timestamp"]=datetime.fromisoformat(value["evaluation_timestamp"]); value["holding_context_ids"]=tuple(value["holding_context_ids"]); value["warnings"]=tuple(value["warnings"])
    for key in ("candidate_risk_amount", "candidate_allocation", "expected_incremental_return", "modeled_switching_friction"):
        if value.get(key) is not None: value[key]=str(value[key])
    return HistoricalPortfolioGateEvaluation(**value)


def rotation_candidate_context_from(value: dict[str, Any]) -> HistoricalRotationCandidateContext:
    value=dict(value); value["known_at"]=datetime.fromisoformat(value["known_at"]); value["warnings"]=tuple(value["warnings"]); return HistoricalRotationCandidateContext(**value)


def rotation_history_from(value: dict[str, Any]) -> HistoricalRotationHistory:
    value=dict(value); value["occurred_at"]=datetime.fromisoformat(value["occurred_at"]); value["cooldown_anchor"]=datetime.fromisoformat(value["cooldown_anchor"]) if value["cooldown_anchor"] else None; value["source_rotation_evaluation_ids"]=tuple(value["source_rotation_evaluation_ids"]); return HistoricalRotationHistory(**value)


def rotation_evaluation_from(value: dict[str, Any]) -> HistoricalRotationEvaluation:
    value=dict(value); value["evaluation_timestamp"]=datetime.fromisoformat(value["evaluation_timestamp"])
    for key in ("candidate_context_ids","holding_context_ids","rotation_history_ids","ranked_candidate_ids","warnings"): value[key]=tuple(value[key])
    return HistoricalRotationEvaluation(**value)

def signal_replay_reference_from(value: dict[str, Any]) -> HistoricalSignalReplayReference:
    value=dict(value); value["generation_timestamp"]=datetime.fromisoformat(value["generation_timestamp"]); value["trigger_timestamp"]=datetime.fromisoformat(value["trigger_timestamp"]) if value["trigger_timestamp"] else None; value["warnings"]=tuple(value["warnings"]); return HistoricalSignalReplayReference(**value)

def paper_replay_reference_from(value: dict[str, Any]) -> HistoricalPaperReplayReference:
    value=dict(value); value["replay_step_numbers"]=tuple(value["replay_step_numbers"]); value["frozen_bar_ids"]=tuple(value["frozen_bar_ids"]); value["warnings"]=tuple(value["warnings"]); return HistoricalPaperReplayReference(**value)

def trigger_timing_context_from(value: dict[str, Any]) -> HistoricalTriggerTimingContext:
    value=dict(value); value["trigger_timestamp"]=datetime.fromisoformat(value["trigger_timestamp"]); value["trigger_known_at"]=datetime.fromisoformat(value["trigger_known_at"]); value["execution_timing_policy"]=ExecutionTimingPolicy(value["execution_timing_policy"]); value["warnings"]=tuple(value["warnings"]); return HistoricalTriggerTimingContext(**value)

def execution_timing_context_from(value: dict[str, Any]) -> HistoricalExecutionTimingContext:
    value=dict(value); value["execution_timing_policy"]=ExecutionTimingPolicy(value["execution_timing_policy"]); value["status"]=ExecutionTimingStatus(value["status"]); value["replay_timestamp"]=datetime.fromisoformat(value["replay_timestamp"]); value["skipped_bar_ids"]=tuple(value["skipped_bar_ids"]); value["skipped_session_dates"]=tuple(value["skipped_session_dates"]); value["warnings"]=tuple(value["warnings"]); return HistoricalExecutionTimingContext(**value)

def signal_config_snapshot_from(value: dict[str, Any]) -> SignalConfigSnapshot:
    from app.signals.models import EntryType, SignalConfig
    value=dict(value); config=dict(value["config"]); config["minimum_score"]=Decimal(config["minimum_score"]) if config["minimum_score"] is not None else None; config["minimum_risk_reward"]=Decimal(config["minimum_risk_reward"]) if config["minimum_risk_reward"] is not None else None; config["allowed_entry_types"]=tuple(EntryType(x) for x in config["allowed_entry_types"]) if config["allowed_entry_types"] is not None else None; value["config"]=SignalConfig(**config); value["created_at"]=datetime.fromisoformat(value["created_at"]); value["methodology_notes"]=tuple(value["methodology_notes"]); return SignalConfigSnapshot(**value)

def paper_config_snapshot_from(value: dict[str, Any]) -> PaperTradingConfigSnapshot:
    from app.paper.models import PaperTradingConfig, CreationPolicy, FillMethod, SameBarPolicy, GapPolicy, SizingBasis, InvalidationPolicy
    value=dict(value); config=dict(value["config"])
    for key in ("entry_slippage","exit_slippage","fees_per_unit","initial_tranche","t1_reduction"): config[key]=Decimal(config[key]) if config[key] is not None else None
    for key, enum in (("creation_policy",CreationPolicy),("fill_method",FillMethod),("same_bar_policy",SameBarPolicy),("gap_policy",GapPolicy),("sizing_basis",SizingBasis),("invalidation_policy",InvalidationPolicy)): config[key]=enum(config[key])
    value["config"]=PaperTradingConfig(**config); value["created_at"]=datetime.fromisoformat(value["created_at"]); value["methodology_notes"]=tuple(value["methodology_notes"])
    if value.get("sizing_specification") is not None:
        sizing=dict(value["sizing_specification"])
        for key in ("fixed_notional_amount","fixed_risk_capital_amount","minimum_quantity"): sizing[key]=Decimal(sizing[key]) if sizing[key] is not None else None
        value["sizing_specification"]=FrozenSizingSpecification(**sizing)
    return PaperTradingConfigSnapshot(**value)

def capital_allocation_from(value: dict[str, Any]) -> HistoricalCapitalAllocation:
    value=dict(value); value["evaluation_timestamp"]=datetime.fromisoformat(value["evaluation_timestamp"]); value["candidate_signal_ids"]=tuple(value["candidate_signal_ids"]); value["ranking_inputs"]={key:tuple(item) for key,item in value["ranking_inputs"].items()}; value["available_cash_before"]=Decimal(value["available_cash_before"]); value["reserved_capital"]=Decimal(value["reserved_capital"]); value["selected_signal_ids"]=tuple(value["selected_signal_ids"]); value["rejected_signal_ids"]=tuple(value["rejected_signal_ids"]); value["paper_ledger_link_ids"]=tuple(value["paper_ledger_link_ids"]); value["warnings"]=tuple(value["warnings"]); return HistoricalCapitalAllocation(**value)

def paper_ledger_link_from(value: dict[str, Any]) -> HistoricalPaperLedgerLink:
    value=dict(value)
    for key in ("quantity","entry_value","exit_proceeds","realized_pnl","costs","net_pnl","raw_quantity","required_cash"):
        value[key]=Decimal(value[key]) if value[key] is not None else None
    for key in ("partial_exit_ledger_event_ids","source_bar_ids","warnings"): value[key]=tuple(value[key])
    return HistoricalPaperLedgerLink(**value)

def historical_equity_point_from(value: dict[str, Any]) -> HistoricalEquityPoint:
    value=dict(value); value["evaluation_timestamp"]=datetime.fromisoformat(value["evaluation_timestamp"])
    for key in ("cash","holdings_market_value","equity","invested_capital","gross_exposure","realized_pnl","unrealized_pnl","cumulative_costs"):
        value[key]=Decimal(value[key]) if value[key] is not None else None
    value["frozen_mark_ids"]=tuple(value["frozen_mark_ids"]); value["warnings"]=tuple(value["warnings"]); return HistoricalEquityPoint(**value)

def historical_equity_series_from(value: dict[str, Any]) -> HistoricalEquitySeries:
    value=dict(value); value["start"]=datetime.fromisoformat(value["start"]); value["end"]=datetime.fromisoformat(value["end"]); value["generated_at"]=datetime.fromisoformat(value["generated_at"]); value["starting_capital"]=Decimal(value["starting_capital"]); value["point_ids"]=tuple(value["point_ids"]); value["warnings"]=tuple(value["warnings"]); return HistoricalEquitySeries(**value)
