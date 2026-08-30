from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Mapping


class PortfolioStatus(str, Enum):
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


class PortfolioState(str, Enum):
    ALL_CASH = "ALL_CASH"
    PARTIALLY_INVESTED = "PARTIALLY_INVESTED"
    FULLY_INVESTED = "FULLY_INVESTED"


class PortfolioDataStatus(str, Enum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class TransactionType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    ADD = "ADD"
    REDUCE = "REDUCE"
    DIVIDEND = "DIVIDEND"
    SPLIT = "SPLIT"
    BONUS = "BONUS"
    TRANSFER_IN = "TRANSFER_IN"
    TRANSFER_OUT = "TRANSFER_OUT"
    CASH_DEPOSIT = "CASH_DEPOSIT"
    CASH_WITHDRAWAL = "CASH_WITHDRAWAL"
    FEE = "FEE"
    TAX = "TAX"


class CorporateActionType(str, Enum):
    SPLIT = "SPLIT"
    BONUS = "BONUS"


@dataclass(frozen=True, slots=True)
class Portfolio:
    portfolio_id: str
    name: str
    base_currency: str
    created_at: datetime
    strategy_version: object | None
    account_reference: str | None
    status: PortfolioStatus
    metadata: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class CashPosition:
    amount: Decimal
    currency: str
    reserved_amount: Decimal
    as_of_timestamp: datetime

    @property
    def available_amount(self) -> Decimal:
        return self.amount - self.reserved_amount


@dataclass(frozen=True, slots=True)
class PortfolioTransaction:
    transaction_id: str
    portfolio_id: str
    transaction_type: TransactionType
    effective_at: datetime
    known_at: datetime
    source: str
    provenance_reference: str
    instrument_id: str | None = None
    quantity: Decimal | None = None
    price: Decimal | None = None
    gross_amount: Decimal = Decimal("0")
    fees: Decimal = Decimal("0")
    taxes: Decimal = Decimal("0")
    net_cash_impact: Decimal = Decimal("0")
    settlement_at: datetime | None = None
    strategy_reference: str | None = None
    signal_reference: str | None = None


@dataclass(frozen=True, slots=True)
class CorporateAction:
    action_id: str
    portfolio_id: str
    instrument_id: str
    action_type: CorporateActionType
    ratio: Decimal
    effective_at: datetime
    known_at: datetime
    source: str
    provenance_reference: str


@dataclass(frozen=True, slots=True)
class PriceReference:
    observation_id: str
    instrument_id: str
    price: Decimal
    observed_at: datetime
    known_at: datetime
    valid: bool = True
    stale: bool = False


@dataclass(frozen=True, slots=True)
class HoldingAnalytics:
    instrument_id: str
    as_of_timestamp: datetime
    known_at: datetime
    decision_scorecard_id: str | None = None
    raw_decision_score: Decimal | None = None
    score_status: str | None = None
    data_confidence: float | None = None
    execution_gate_evaluation_id: str | None = None
    gate_status: str | None = None
    diagnostic_ids: tuple[str, ...] = ()
    risk_state: str | None = None
    trading_thesis: str | None = None
    investment_thesis: str | None = None
    scenarios: str | None = None
    invalidation_status: str | None = None
    structural_stop: Decimal | None = None
    target_1: Decimal | None = None
    target_2: Decimal | None = None
    extended_target: Decimal | None = None
    sector: str | None = None
    market_regime_reference: str | None = None


@dataclass(frozen=True, slots=True)
class PortfolioHolding:
    holding_id: str
    instrument_id: str
    quantity: Decimal
    average_cost: Decimal
    cost_basis: Decimal
    acquisition_at: datetime
    realized_pnl: Decimal
    sector: str
    strategy_reference: str | None
    signal_reference: str | None
    active: bool
    current_price: Decimal | None
    price_observation_id: str | None
    market_value: Decimal | None
    unrealized_pnl: Decimal | None
    unrealized_pnl_percent: Decimal | None
    analytics: HoldingAnalytics | None
    calendar_holding_days: int
    trading_sessions_held: int
    risk_amount: Decimal | None


@dataclass(frozen=True, slots=True)
class PortfolioExposureSummary:
    position_allocations: Mapping[str, Decimal | None]
    cash_allocation: Decimal | None
    sector_exposure: Mapping[str, Decimal | None]
    active_holding_count: int
    concentration: Decimal | None


@dataclass(frozen=True, slots=True)
class PortfolioRiskSummary:
    total_heat: Decimal | None
    heat_coverage: Decimal
    status: PortfolioDataStatus
    risk_amounts: Mapping[str, Decimal | None]


@dataclass(frozen=True, slots=True)
class PortfolioSnapshot:
    snapshot_id: str
    portfolio_id: str
    as_of_timestamp: datetime
    source_transaction_cutoff: datetime
    holdings: tuple[PortfolioHolding, ...]
    cash: CashPosition
    market_price_ids: tuple[str, ...]
    portfolio_equity: Decimal | None
    realized_pnl: Decimal
    unrealized_pnl: Decimal | None
    dividends: Decimal
    exposure: PortfolioExposureSummary
    risk: PortfolioRiskSummary
    portfolio_state: PortfolioState
    data_status: PortfolioDataStatus
    cost_basis_methodology_version: str
    strategy_version: object | None
