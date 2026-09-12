from __future__ import annotations

import hashlib
from datetime import datetime
from decimal import Decimal
from app.diagnostics.brain_lineage import require_production_evidence

from app.gates.engine import ExchangeCalendar
from .models import (
    CashPosition, CorporateAction, CorporateActionType, HoldingAnalytics, Portfolio,
    PortfolioDataStatus, PortfolioExposureSummary, PortfolioHolding, PortfolioRiskSummary,
    PortfolioSnapshot, PortfolioState, PortfolioTransaction, PriceReference, TransactionType,
)


COST_BASIS_VERSION = "weighted-average-cost-v1"
UNKNOWN_SECTOR = "UNKNOWN"


class PortfolioEngine:
    """Pure, deterministic ledger reconstruction; it never recommends or executes a trade."""
    def __init__(self, calendar: ExchangeCalendar):
        self.calendar = calendar

    def reconstruct(self, *, portfolio: Portfolio, as_of_timestamp: datetime, initial_cash: CashPosition,
                    transactions: tuple[PortfolioTransaction, ...], actions: tuple[CorporateAction, ...],
                    prices: tuple[PriceReference, ...], analytics: tuple[HoldingAnalytics, ...]) -> PortfolioSnapshot:
        for item in analytics:
            require_production_evidence(item)
        if initial_cash.as_of_timestamp > as_of_timestamp:
            raise ValueError("Initial cash cannot be known after the requested portfolio snapshot.")
        ledger = tuple(sorted((x for x in transactions if x.portfolio_id == portfolio.portfolio_id and x.effective_at <= as_of_timestamp and x.known_at <= as_of_timestamp), key=lambda x: (x.effective_at, x.transaction_id)))
        events = [(x.effective_at, x.action_id, "action", x) for x in actions if x.portfolio_id == portfolio.portfolio_id and x.effective_at <= as_of_timestamp and x.known_at <= as_of_timestamp]
        events += [(x.effective_at, x.transaction_id, "transaction", x) for x in ledger]
        state: dict[str, dict] = {}; cash = initial_cash.amount; dividends = Decimal("0")
        for _, _, kind, event in sorted(events):
            if kind == "action": self._apply_action(state, event)
            else:
                if cash is not None:
                    cash += event.net_cash_impact
                if event.transaction_type in {TransactionType.BUY, TransactionType.ADD}: self._buy(state, event)
                elif event.transaction_type in {TransactionType.SELL, TransactionType.REDUCE}: self._sell(state, event)
                elif event.transaction_type is TransactionType.DIVIDEND: dividends += event.net_cash_impact
        holdings = tuple(self._holding(instrument, item, as_of_timestamp, prices, analytics) for instrument, item in sorted(state.items()) if item["quantity"] > 0)
        known_values = [x.market_value for x in holdings if x.market_value is not None]
        equity = cash + sum(known_values, Decimal("0")) if cash is not None and len(known_values) == len(holdings) else None
        realized = sum((item["realized"] for item in state.values()), Decimal("0"))
        unrealized = sum((x.unrealized_pnl for x in holdings if x.unrealized_pnl is not None), Decimal("0")) if len(known_values) == len(holdings) else None
        exposure = self._exposure(holdings, cash, equity)
        risk = self._risk(holdings, equity)
        status = PortfolioDataStatus.COMPLETE if equity is not None and risk.status is PortfolioDataStatus.COMPLETE else (PortfolioDataStatus.INSUFFICIENT_DATA if not holdings and initial_cash.amount is None else PortfolioDataStatus.PARTIAL)
        pstate = PortfolioState.ALL_CASH if not holdings and cash is not None else (PortfolioState.FULLY_INVESTED if holdings and cash == 0 else PortfolioState.PARTIALLY_INVESTED)
        marker = "|".join([portfolio.portfolio_id, as_of_timestamp.isoformat(), *(x.transaction_id for x in ledger), *(x.action_id for x in actions if x.effective_at <= as_of_timestamp and x.known_at <= as_of_timestamp)])
        return PortfolioSnapshot("portfolio-" + hashlib.sha256(marker.encode()).hexdigest()[:20], portfolio.portfolio_id, as_of_timestamp, as_of_timestamp,
            holdings, CashPosition(cash, initial_cash.currency, initial_cash.reserved_amount, as_of_timestamp, initial_cash.cash_state),
            tuple(x.price_observation_id for x in holdings if x.price_observation_id), equity, realized, unrealized, dividends,
            exposure, risk, pstate, status, COST_BASIS_VERSION, portfolio.strategy_version)

    def _buy(self, state, tx):
        self._require_trade(tx); item = state.setdefault(tx.instrument_id, {"quantity": Decimal("0"), "cost": Decimal("0"), "realized": Decimal("0"), "acquisition": tx.effective_at, "strategy": tx.strategy_reference, "signal": tx.signal_reference})
        item["cost"] += tx.gross_amount + tx.fees + tx.taxes; item["quantity"] += tx.quantity

    def _sell(self, state, tx):
        self._require_trade(tx); item = state.get(tx.instrument_id)
        if item is None or tx.quantity > item["quantity"]: raise ValueError("A reduction cannot exceed the reconstructed holding quantity.")
        average = item["cost"] / item["quantity"]; sold_cost = average * tx.quantity; proceeds = tx.gross_amount - tx.fees - tx.taxes
        item["realized"] += proceeds - sold_cost; item["cost"] -= sold_cost; item["quantity"] -= tx.quantity

    def _apply_action(self, state, action):
        if action.ratio <= 0: raise ValueError("Corporate-action ratio must be positive.")
        item = state.get(action.instrument_id)
        if item is None or item["quantity"] == 0: return
        if action.action_type is CorporateActionType.SPLIT: item["quantity"] *= action.ratio
        elif action.action_type is CorporateActionType.BONUS: item["quantity"] *= Decimal("1") + action.ratio

    @staticmethod
    def _require_trade(tx):
        if tx.instrument_id is None or tx.quantity is None or tx.quantity <= 0 or tx.price is None:
            raise ValueError("BUY/SELL/ADD/REDUCE ledger events require instrument, positive quantity, and price.")

    def _holding(self, instrument, item, asof, prices, analytics):
        eligible = [x for x in prices if x.instrument_id == instrument and x.valid and not x.stale and x.observed_at <= asof and x.known_at <= asof]
        price = max(eligible, key=lambda x: (x.observed_at, x.known_at, x.observation_id)) if eligible else None
        relevant = [x for x in analytics if x.instrument_id == instrument and x.as_of_timestamp <= asof and x.known_at <= asof]
        analysis = max(relevant, key=lambda x: (x.as_of_timestamp, x.known_at)) if relevant else None
        quantity, cost = item["quantity"], item["cost"]; average = cost / quantity
        value = quantity * price.price if price else None; pnl = value - cost if value is not None else None
        sessions = self.calendar.sessions_between(item["acquisition"].date(), asof.date())
        reference = price.price if price else average
        risk = quantity * abs(reference - analysis.structural_stop) if analysis and analysis.structural_stop is not None else None
        return PortfolioHolding(f"holding-{instrument}", instrument, quantity, average, cost, item["acquisition"], item["realized"], analysis.sector if analysis and analysis.sector else UNKNOWN_SECTOR,
            item["strategy"], item["signal"], True, price.price if price else None, price.observation_id if price else None, value, pnl, pnl / cost if pnl is not None and cost else None,
            analysis, (asof.date() - item["acquisition"].date()).days, sessions, risk)

    @staticmethod
    def _exposure(holdings, cash, equity):
        allocations = {x.instrument_id: (x.market_value / equity if equity and x.market_value is not None else None) for x in holdings}
        sectors = {}; 
        for x in holdings: sectors[x.sector] = (sectors.get(x.sector, Decimal("0")) + x.market_value / equity) if equity and x.market_value is not None else None
        known = [x.market_value for x in holdings if x.market_value is not None]
        return PortfolioExposureSummary(allocations, cash / equity if equity else None, sectors, len(holdings), max(allocations.values()) if allocations and all(x is not None for x in allocations.values()) else None)

    @staticmethod
    def _risk(holdings, equity):
        amounts = {x.instrument_id: x.risk_amount for x in holdings}; known = [x for x in amounts.values() if x is not None]
        status = PortfolioDataStatus.COMPLETE if len(known) == len(holdings) else PortfolioDataStatus.PARTIAL
        return PortfolioRiskSummary(sum(known, Decimal("0")) / equity if equity and len(known) == len(holdings) else None, Decimal(len(known)) / Decimal(len(holdings)) if holdings else Decimal("1"), status, amounts)
