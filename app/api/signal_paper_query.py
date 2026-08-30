"""Read-only facades for existing signal, paper-trade, and performance records.

This module only packages persisted/injected immutable values.  It contains no
signal evaluation, fill, outcome, R-multiple, or performance calculations.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from app.api.errors import APIRequestError
from app.api.schemas.signals import (
    PaperTradePerformanceResponse,
    PaperTradeResponse,
    SignalGateResponse,
    SignalResponse,
    SignalTradeStructureResponse,
)
from app.paper.models import PaperFill, PaperOutcome, PaperTrade, PaperTradeState
from app.performance.models import PerformanceReport
from app.signals.models import SignalRecord, TradePlan


def _strategy_version(value: object) -> str:
    strategy_id = getattr(value, "strategy_id", None)
    version = getattr(value, "version", None)
    return f"{strategy_id}/{version}" if strategy_id is not None and version is not None else str(value)


@dataclass(frozen=True, slots=True)
class SignalQueryRecord:
    signal: SignalRecord
    exchange: str | None = None
    trade_plan: TradePlan | None = None
    decision_score: Decimal | None = None
    gate_eligibility: str | None = None
    gate_warnings: tuple[str, ...] = ()
    gate_evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PaperTradeQueryRecord:
    trade: PaperTrade
    exchange: str | None = None
    outcome: PaperOutcome | None = None
    fills: tuple[PaperFill, ...] = ()
    provenance_ids: tuple[str, ...] = ()


class SignalQueryService(Protocol):
    def list_signals(self, *, symbol: str | None, status: str | None, strategy_version: str | None) -> tuple[SignalQueryRecord, ...]: ...
    def get_signal(self, signal_id: str) -> SignalQueryRecord: ...


class PaperTradeQueryService(Protocol):
    def list_paper_trades(self, *, symbol: str | None, status: str | None, strategy_version: str | None) -> tuple[PaperTradeQueryRecord, ...]: ...
    def get_paper_trade(self, trade_id: str) -> PaperTradeQueryRecord: ...
    def get_performance(self, *, strategy_version: str | None) -> PerformanceReport: ...


class UnavailableSignalQueryService:
    def list_signals(self, **_: object) -> tuple[SignalQueryRecord, ...]:
        raise _unavailable("SIGNALS_UNAVAILABLE", "Signals are not available.")

    def get_signal(self, signal_id: str) -> SignalQueryRecord:
        raise _unavailable("SIGNALS_UNAVAILABLE", "Signals are not available.")


class UnavailablePaperTradeQueryService:
    def list_paper_trades(self, **_: object) -> tuple[PaperTradeQueryRecord, ...]:
        raise _unavailable("PAPER_TRADES_UNAVAILABLE", "Paper trades are not available.")

    def get_paper_trade(self, trade_id: str) -> PaperTradeQueryRecord:
        raise _unavailable("PAPER_TRADES_UNAVAILABLE", "Paper trades are not available.")

    def get_performance(self, **_: object) -> PerformanceReport:
        raise _unavailable("PERFORMANCE_UNAVAILABLE", "Paper-trade performance is not available.")


class SnapshotSignalQueryService:
    """Deterministic test/local read adapter for already-created signal records."""

    def __init__(self, records: tuple[SignalQueryRecord, ...]) -> None:
        self._records = records

    def list_signals(self, *, symbol: str | None, status: str | None, strategy_version: str | None) -> tuple[SignalQueryRecord, ...]:
        return tuple(record for record in self._records if _signal_matches(record, symbol, status, strategy_version))

    def get_signal(self, signal_id: str) -> SignalQueryRecord:
        for record in self._records:
            if record.signal.signal_id == signal_id:
                return record
        raise APIRequestError(status_code=404, code="SIGNAL_NOT_FOUND", message="Signal was not found.")


class SnapshotPaperTradeQueryService:
    """Deterministic test/local read adapter; it never simulates or changes trades."""

    def __init__(self, records: tuple[PaperTradeQueryRecord, ...], reports: tuple[PerformanceReport, ...] = ()) -> None:
        self._records = records
        self._reports = reports

    def list_paper_trades(self, *, symbol: str | None, status: str | None, strategy_version: str | None) -> tuple[PaperTradeQueryRecord, ...]:
        return tuple(record for record in self._records if _trade_matches(record, symbol, status, strategy_version))

    def get_paper_trade(self, trade_id: str) -> PaperTradeQueryRecord:
        for record in self._records:
            if record.trade.paper_trade_id == trade_id:
                return record
        raise APIRequestError(status_code=404, code="PAPER_TRADE_NOT_FOUND", message="Paper trade was not found.")

    def get_performance(self, *, strategy_version: str | None) -> PerformanceReport:
        candidates = tuple(report for report in self._reports if strategy_version is None or _strategy_version(report.strategy_version) == strategy_version)
        if not candidates:
            raise _unavailable("PERFORMANCE_UNAVAILABLE", "Paper-trade performance is not available.")
        return candidates[-1]


def _unavailable(code: str, message: str) -> APIRequestError:
    return APIRequestError(status_code=503, code=code, message=message)


def _signal_matches(record: SignalQueryRecord, symbol: str | None, status: str | None, strategy_version: str | None) -> bool:
    value = record.signal
    return ((symbol is None or value.instrument_id == symbol) and (status is None or value.status.value == status) and (strategy_version is None or _strategy_version(value.strategy_version) == strategy_version))


def _trade_matches(record: PaperTradeQueryRecord, symbol: str | None, status: str | None, strategy_version: str | None) -> bool:
    value = record.trade
    state = record.outcome.state.value if record.outcome is not None else PaperTradeState.CREATED.value
    return ((symbol is None or value.instrument_id == symbol) and (status is None or state == status) and (strategy_version is None or _strategy_version(value.strategy_version) == strategy_version))


def signal_response(record: SignalQueryRecord) -> SignalResponse:
    signal, plan = record.signal, record.trade_plan
    return SignalResponse(
        signal_id=signal.signal_id, symbol=signal.instrument_id, exchange=record.exchange,
        lifecycle_status=signal.status.value, signal_type=signal.signal_type.value,
        generated_at=signal.generated_at, data_as_of=signal.as_of_timestamp,
        strategy_version=_strategy_version(signal.strategy_version),
        decision_score=record.decision_score, confidence=signal.signal_confidence,
        gate=SignalGateResponse(status=None, eligibility=record.gate_eligibility, warnings=record.gate_warnings),
        trade_structure=SignalTradeStructureResponse(
            plan_id=signal.trade_plan_id, entry_type=plan.entry_type.value if plan and plan.entry_type else None,
            planned_entry=plan.entry_price if plan else None, entry_zone_low=plan.entry_zone_low if plan else None,
            entry_zone_high=plan.entry_zone_high if plan else None, structural_stop=plan.structural_stop if plan else None,
            target_1=plan.target_1 if plan else None, target_2=plan.target_2 if plan else None,
            extended_target=plan.extended_target if plan else None, risk_reward_t1=plan.risk_reward_t1 if plan else None,
            risk_reward_t2=plan.risk_reward_t2 if plan else None, thesis_reference=plan.thesis_reference if plan else None,
            invalidation=plan.exact_invalidation if plan else None, catalyst=plan.catalyst if plan else None,
            catalyst_clock=plan.catalyst_clock if plan else None, warnings=plan.key_risks if plan else (),
        ),
        warnings=signal.warnings,
    )


def paper_trade_response(record: PaperTradeQueryRecord) -> PaperTradeResponse:
    trade, outcome = record.trade, record.outcome
    first_fill = record.fills[0] if record.fills else None
    flags = _outcome_flags(outcome)
    return PaperTradeResponse(
        paper_trade_id=trade.paper_trade_id, symbol=trade.instrument_id, exchange=record.exchange,
        strategy_version=_strategy_version(trade.strategy_version), lifecycle_status=outcome.state.value if outcome else PaperTradeState.CREATED.value,
        created_at=trade.created_at, data_as_of=trade.as_of_timestamp,
        trigger_timestamp=outcome.entry_timestamp if outcome and outcome.triggered else None,
        fill_timestamp=first_fill.timestamp if first_fill else (outcome.entry_timestamp if outcome and outcome.filled else None),
        entry_price=outcome.entry_price if outcome else None, quantity=first_fill.quantity if first_fill else None,
        planned_entry=trade.planned_entry, structural_stop=trade.structural_stop, target_1=trade.target_1, target_2=trade.target_2,
        extended_target=trade.extended_target, planned_r_multiple=trade.initial_risk_reward,
        exit_timestamp=outcome.final_exit_timestamp if outcome else None, exit_price=outcome.final_exit_price if outcome else None,
        gross_pnl=outcome.gross_pnl if outcome else None, costs=outcome.costs if outcome else None,
        net_pnl=outcome.net_pnl if outcome else None, realized_r=outcome.r_multiple if outcome else None,
        mfe=outcome.mfe if outcome else None, mae=outcome.mae if outcome else None,
        mfe_r=outcome.mfe_r if outcome else None, mae_r=outcome.mae_r if outcome else None,
        outcome_flags=flags, exit_reason=_exit_reason(outcome), warnings=trade.warnings,
    )


def _outcome_flags(outcome: PaperOutcome | None) -> tuple[str, ...]:
    if outcome is None:
        return ()
    return tuple(name for name, enabled in (("TRIGGERED", outcome.triggered), ("FILLED", outcome.filled), ("T1_REACHED", outcome.t1_reached), ("T2_REACHED", outcome.t2_reached), ("STOP_HIT", outcome.stop_hit), ("INVALIDATED", outcome.invalidated), ("EXPIRED", outcome.expiry)) if enabled)


def _exit_reason(outcome: PaperOutcome | None) -> str | None:
    if outcome is None or outcome.final_exit_timestamp is None:
        return None
    return outcome.state.value


def paper_performance_response(report: PerformanceReport) -> PaperTradePerformanceResponse:
    metrics = report.metrics
    closed = metrics.get("closed_trades")
    win_rate = metrics.get("win_rate")
    wins = int(win_rate * closed) if isinstance(win_rate, Decimal) and isinstance(closed, int) else None
    losses = int((metrics.get("loss_rate") or Decimal("0")) * closed) if isinstance(closed, int) and isinstance(metrics.get("loss_rate"), Decimal) else None
    return PaperTradePerformanceResponse(
        report_id=report.report_id, strategy_version=_strategy_version(report.strategy_version), start=report.start, end=report.end,
        sample_status=metrics.get("sample_status"), total_trades=metrics.get("total_trades"), closed_trades=closed,
        open_trades=metrics.get("open_trades"), wins=wins, losses=losses, win_rate=win_rate,
        expectancy=metrics.get("expectancy"), average_r=metrics.get("average_r"), profit_factor=metrics.get("profit_factor"),
        max_drawdown=metrics.get("max_drawdown"), sharpe=metrics.get("sharpe"), sortino=metrics.get("sortino"),
        volatility=metrics.get("volatility"), costs=metrics.get("costs"), capital_efficiency=metrics.get("capital_efficiency"),
        warnings=report.warnings,
    )
