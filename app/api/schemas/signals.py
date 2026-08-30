"""Read-only signal and simulated paper-trade response models."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class SignalGateResponse(BaseModel):
    status: str | None
    eligibility: str | None
    warnings: tuple[str, ...]


class SignalTradeStructureResponse(BaseModel):
    plan_id: str | None
    entry_type: str | None
    planned_entry: Decimal | None
    entry_zone_low: Decimal | None
    entry_zone_high: Decimal | None
    structural_stop: Decimal | None
    target_1: Decimal | None
    target_2: Decimal | None
    extended_target: Decimal | None
    risk_reward_t1: Decimal | None
    risk_reward_t2: Decimal | None
    thesis_reference: str | None
    invalidation: str | None
    catalyst: str | None
    catalyst_clock: str | None
    warnings: tuple[str, ...]


class SignalResponse(BaseModel):
    signal_id: str
    symbol: str | None
    exchange: str | None
    lifecycle_status: str
    signal_type: str
    generated_at: datetime
    data_as_of: datetime
    strategy_version: str
    decision_score: Decimal | None
    confidence: float | None
    gate: SignalGateResponse
    trade_structure: SignalTradeStructureResponse
    warnings: tuple[str, ...]


class SignalListResponse(BaseModel):
    items: tuple[SignalResponse, ...]
    total: int
    limit: int
    offset: int


class PaperTradeResponse(BaseModel):
    paper_trade_id: str
    symbol: str
    exchange: str | None
    strategy_version: str
    lifecycle_status: str
    created_at: datetime
    data_as_of: datetime
    trigger_timestamp: datetime | None
    fill_timestamp: datetime | None
    entry_price: Decimal | None
    quantity: Decimal | None
    planned_entry: Decimal | None
    structural_stop: Decimal | None
    target_1: Decimal | None
    target_2: Decimal | None
    extended_target: Decimal | None
    planned_r_multiple: Decimal | None
    exit_timestamp: datetime | None
    exit_price: Decimal | None
    gross_pnl: Decimal | None
    costs: Decimal | None
    net_pnl: Decimal | None
    realized_r: Decimal | None
    mfe: Decimal | None
    mae: Decimal | None
    mfe_r: Decimal | None
    mae_r: Decimal | None
    outcome_flags: tuple[str, ...]
    exit_reason: str | None
    warnings: tuple[str, ...]


class PaperTradeListResponse(BaseModel):
    items: tuple[PaperTradeResponse, ...]
    total: int
    limit: int
    offset: int


class PaperTradePerformanceResponse(BaseModel):
    report_id: str
    strategy_version: str
    start: datetime
    end: datetime
    sample_status: str | None
    total_trades: int | None
    closed_trades: int | None
    open_trades: int | None
    wins: int | None
    losses: int | None
    win_rate: Decimal | None
    expectancy: Decimal | None
    average_r: Decimal | None
    profit_factor: Decimal | None
    max_drawdown: Decimal | None
    sharpe: Decimal | None
    sortino: Decimal | None
    volatility: Decimal | None
    costs: Decimal | None
    capital_efficiency: Decimal | None
    warnings: tuple[str, ...]
