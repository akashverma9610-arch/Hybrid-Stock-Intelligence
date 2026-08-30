from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from app.gates.engine import ExchangeCalendar
from app.historical.guard import manifest_fingerprint
from .models import BacktestEvent, BacktestEventType
from app.portfolio.engine import PortfolioEngine
from app.portfolio.models import (
    CashPosition, CorporateAction, CorporateActionType, HoldingAnalytics, Portfolio,
    PortfolioSnapshot, PortfolioStatus, PortfolioTransaction, PriceReference, TransactionType,
)
from app.portfolio.serialization import dumps as portfolio_dumps, snapshot_from


class BacktestPortfolioInitialization(str, Enum):
    CASH_ONLY_START = "CASH_ONLY_START"
    SUPPLIED_HISTORICAL_PORTFOLIO = "SUPPLIED_HISTORICAL_PORTFOLIO"


class BacktestPortfolioLedgerType(str, Enum):
    INITIAL_CAPITAL = "INITIAL_CAPITAL"; HYPOTHETICAL_BUY = "HYPOTHETICAL_BUY"; HYPOTHETICAL_SELL = "HYPOTHETICAL_SELL"
    DIVIDEND = "DIVIDEND"; SPLIT = "SPLIT"; BONUS = "BONUS"; CASH_ADJUSTMENT = "CASH_ADJUSTMENT"; POSITION_CLOSED = "POSITION_CLOSED"


@dataclass(frozen=True, slots=True)
class BacktestPortfolioLedgerEvent:
    ledger_event_id: str; backtest_run_id: str; event_type: BacktestPortfolioLedgerType
    effective_at: datetime; known_at: datetime; source: str; provenance_reference: str
    instrument_id: str | None = None; quantity: Decimal | None = None; price: Decimal | None = None
    gross_amount: Decimal = Decimal("0"); fees: Decimal = Decimal("0"); taxes: Decimal = Decimal("0")
    net_cash_impact: Decimal = Decimal("0"); ratio: Decimal | None = None; sector: str | None = None
    structural_stop: Decimal | None = None


@dataclass(frozen=True, slots=True)
class BacktestPortfolioState:
    backtest_portfolio_state_id: str; backtest_run_id: str; replay_step_number: int; evaluation_timestamp: datetime
    initialization_policy: BacktestPortfolioInitialization; starting_capital: Decimal; snapshot: PortfolioSnapshot
    source_ledger_ids: tuple[str, ...]; price_reference_ids: tuple[str, ...]; warnings: tuple[str, ...]; fingerprint: str
    frozen_price_marks: tuple["BacktestFrozenPriceMark", ...] = (); corporate_action_ledger_ids: tuple[str, ...] = (); risk_reference_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class BacktestFrozenPriceMark:
    observation_id: str; instrument_id: str; price: Decimal; observed_at: datetime; known_at: datetime


class BacktestPortfolioReplayEngine:
    """Separate backtest ledger adapter; it never reads or mutates a real Portfolio."""
    def __init__(self, calendar: ExchangeCalendar): self._engine = PortfolioEngine(calendar)

    def reconstruct(self, *, run_id: str, step_number: int, at: datetime, starting_capital: Decimal,
                    events: tuple[BacktestPortfolioLedgerEvent, ...], prices: tuple[PriceReference, ...],
                    initialization_policy: BacktestPortfolioInitialization = BacktestPortfolioInitialization.CASH_ONLY_START) -> BacktestPortfolioState:
        if initialization_policy is not BacktestPortfolioInitialization.CASH_ONLY_START:
            raise ValueError("Supplied historical portfolios are not implemented by this V1 backtest adapter.")
        eligible = tuple(sorted((x for x in events if x.backtest_run_id == run_id and x.effective_at <= at and x.known_at <= at), key=lambda x:(x.effective_at,x.ledger_event_id)))
        initial = [x for x in eligible if x.event_type is BacktestPortfolioLedgerType.INITIAL_CAPITAL]
        if initial and initial[0].net_cash_impact != starting_capital: raise ValueError("Initial-capital event must match the frozen backtest starting capital.")
        transactions, actions = [], []
        for event in eligible:
            if event.event_type is BacktestPortfolioLedgerType.INITIAL_CAPITAL: continue
            if event.event_type in {BacktestPortfolioLedgerType.SPLIT, BacktestPortfolioLedgerType.BONUS}:
                actions.append(CorporateAction(event.ledger_event_id, f"backtest:{run_id}", event.instrument_id or "", CorporateActionType.SPLIT if event.event_type is BacktestPortfolioLedgerType.SPLIT else CorporateActionType.BONUS, event.ratio or Decimal("0"), event.effective_at,event.known_at,event.source,event.provenance_reference)); continue
            mapping={BacktestPortfolioLedgerType.HYPOTHETICAL_BUY:TransactionType.BUY,BacktestPortfolioLedgerType.HYPOTHETICAL_SELL:TransactionType.SELL,BacktestPortfolioLedgerType.DIVIDEND:TransactionType.DIVIDEND,BacktestPortfolioLedgerType.CASH_ADJUSTMENT:TransactionType.CASH_DEPOSIT,BacktestPortfolioLedgerType.POSITION_CLOSED:TransactionType.SELL}
            transactions.append(PortfolioTransaction(event.ledger_event_id,f"backtest:{run_id}",mapping[event.event_type],event.effective_at,event.known_at,event.source,event.provenance_reference,event.instrument_id,event.quantity,event.price,event.gross_amount,event.fees,event.taxes,event.net_cash_impact))
        # Reject unaffordable buys before delegating the canonical accounting method.
        cash=starting_capital
        for tx in transactions:
            if tx.transaction_type is TransactionType.BUY and tx.net_cash_impact + cash < 0: raise ValueError("Backtest portfolio cannot deploy more cash than available.")
            cash += tx.net_cash_impact
        portfolio=Portfolio(f"backtest:{run_id}","Backtest-only portfolio","INR",at,None,None,PortfolioStatus.ACTIVE,{"backtest_run_id":run_id})
        stop_events={x.instrument_id:x for x in eligible if x.instrument_id and x.structural_stop is not None}
        analytics=tuple(HoldingAnalytics(instrument_id=instrument,as_of_timestamp=at,known_at=event.known_at,structural_stop=event.structural_stop) for instrument,event in stop_events.items())
        snapshot=self._engine.reconstruct(portfolio=portfolio,as_of_timestamp=at,initial_cash=CashPosition(starting_capital,"INR",Decimal("0"),at),transactions=tuple(transactions),actions=tuple(actions),prices=prices,analytics=analytics)
        stale_instruments={x.instrument_id for x in prices if x.instrument_id in {h.instrument_id for h in snapshot.holdings} and x.stale}
        warnings=tuple(sorted({("STALE_MARK" if x.instrument_id in stale_instruments else "MISSING_MARK") for x in snapshot.holdings if x.current_price is None}))
        fingerprint=manifest_fingerprint(run=run_id,step=step_number,at=at,ledger=tuple(x.ledger_event_id for x in eligible),prices=snapshot.market_price_ids)
        marks=tuple(BacktestFrozenPriceMark(x.observation_id,x.instrument_id,x.price,x.observed_at,x.known_at) for x in prices if x.observation_id in snapshot.market_price_ids)
        actions=tuple(x.ledger_event_id for x in eligible if x.event_type in {BacktestPortfolioLedgerType.SPLIT,BacktestPortfolioLedgerType.BONUS})
        return BacktestPortfolioState(f"backtest-state-{fingerprint[:24]}",run_id,step_number,at,initialization_policy,starting_capital,snapshot,tuple(x.ledger_event_id for x in eligible),snapshot.market_price_ids,warnings,fingerprint,marks,actions,tuple(x.ledger_event_id for x in stop_events.values()))


class BacktestPortfolioReplayService:
    """Persistence/event wrapper around the pure backtest-only accounting adapter."""
    def __init__(self, repository, calendar: ExchangeCalendar): self.repository,self.engine=repository,BacktestPortfolioReplayEngine(calendar)
    def reconstruct_and_persist(self, **kwargs):
        state=self.engine.reconstruct(**kwargs); self.repository.save_backtest_portfolio_state(state)
        event_type=BacktestEventType.PORTFOLIO_INSUFFICIENT if state.warnings else BacktestEventType.PORTFOLIO_VALUED
        for kind,message in ((BacktestEventType.PORTFOLIO_RECONSTRUCTED,"Backtest portfolio reconstructed"),(event_type,"Backtest portfolio valuation complete" if not state.warnings else "; ".join(state.warnings))):
            sequence=len(self.repository.list_backtest_events(state.backtest_run_id))+1
            self.repository.append_backtest_event(BacktestEvent(f"{state.backtest_run_id}:event:{sequence:06d}",state.backtest_run_id,kind,state.evaluation_timestamp,state.replay_step_number,state.evaluation_timestamp,(state.backtest_portfolio_state_id,),message,{"warnings":state.warnings},state.evaluation_timestamp))
        return state


def ledger_from(value):
    value=dict(value)
    for key in ("effective_at","known_at"): value[key]=datetime.fromisoformat(value[key])
    for key in ("quantity","price","gross_amount","fees","taxes","net_cash_impact","ratio","structural_stop"):
        value[key]=Decimal(value[key]) if value[key] is not None else None
    value["event_type"]=BacktestPortfolioLedgerType(value["event_type"])
    return BacktestPortfolioLedgerEvent(**value)


def state_dump(state):
    return {"backtest_portfolio_state_id":state.backtest_portfolio_state_id,"backtest_run_id":state.backtest_run_id,"replay_step_number":state.replay_step_number,"evaluation_timestamp":state.evaluation_timestamp.isoformat(),"initialization_policy":state.initialization_policy.value,"starting_capital":str(state.starting_capital),"snapshot":portfolio_dumps(state.snapshot),"source_ledger_ids":list(state.source_ledger_ids),"price_reference_ids":list(state.price_reference_ids),"warnings":list(state.warnings),"fingerprint":state.fingerprint,"frozen_price_marks":[{"observation_id":x.observation_id,"instrument_id":x.instrument_id,"price":str(x.price),"observed_at":x.observed_at.isoformat(),"known_at":x.known_at.isoformat()} for x in state.frozen_price_marks],"corporate_action_ledger_ids":list(state.corporate_action_ledger_ids),"risk_reference_ids":list(state.risk_reference_ids)}


def state_from(value):
    marks=tuple(BacktestFrozenPriceMark(x["observation_id"],x["instrument_id"],Decimal(x["price"]),datetime.fromisoformat(x["observed_at"]),datetime.fromisoformat(x["known_at"])) for x in value.get("frozen_price_marks",()))
    return BacktestPortfolioState(value["backtest_portfolio_state_id"],value["backtest_run_id"],value["replay_step_number"],datetime.fromisoformat(value["evaluation_timestamp"]),BacktestPortfolioInitialization(value["initialization_policy"]),Decimal(value["starting_capital"]),snapshot_from(value["snapshot"]),tuple(value["source_ledger_ids"]),tuple(value["price_reference_ids"]),tuple(value["warnings"]),value["fingerprint"],marks,tuple(value.get("corporate_action_ledger_ids",())),tuple(value.get("risk_reference_ids",())))
