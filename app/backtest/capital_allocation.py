from __future__ import annotations

"""Backtest-only bridge from immutable paper fills to the existing ledger."""

from dataclasses import dataclass
from decimal import Decimal, ROUND_FLOOR

from app.historical.guard import manifest_fingerprint
from app.paper.models import PaperFill, PaperOutcome, PaperTrade, SizingBasis

from .models import BacktestEvent, BacktestEventType, FrozenSizingSpecification, HistoricalCapitalAllocation, HistoricalPaperLedgerLink
from .portfolio import BacktestPortfolioLedgerEvent, BacktestPortfolioLedgerType


@dataclass(frozen=True, slots=True)
class AllocationPolicy:
    version: str
    ordering: str = "RANK_ORDER"
    management_before_entries: bool = True


@dataclass(frozen=True, slots=True)
class PaperFillCandidate:
    signal_id: str
    paper_trade: PaperTrade
    paper_outcome: PaperOutcome
    entry_fill: PaperFill | None
    score: Decimal | None
    confidence: float | None
    risk_reward: Decimal | None
    sector: str | None = None
    sizing_basis: str = "UNIT_BASIS"
    sizing_specification: FrozenSizingSpecification | None = None
    paper_config_snapshot_id: str | None = None


@dataclass(frozen=True, slots=True)
class AllocationApplication:
    allocation: HistoricalCapitalAllocation
    links: tuple[HistoricalPaperLedgerLink, ...]
    ledger_events: tuple[BacktestPortfolioLedgerEvent, ...]


class HistoricalPaperLedgerIntegrationService:
    """Applies hypothetical fills only; this class has no real-account dependency."""

    def __init__(self, repository, *, policy: AllocationPolicy) -> None:
        self.repository, self.policy = repository, policy

    def allocate_fills(self, *, run, replay_step_number: int, at, starting_capital: Decimal,
                       existing_ledger_events: tuple[BacktestPortfolioLedgerEvent, ...],
                       candidates: tuple[PaperFillCandidate, ...]) -> AllocationApplication:
        if self.policy.ordering != "RANK_ORDER":
            raise ValueError("Only frozen RANK_ORDER allocation is supported in V1.")
        available = starting_capital + sum((event.net_cash_impact for event in existing_ledger_events if event.event_type is not BacktestPortfolioLedgerType.INITIAL_CAPITAL and event.effective_at <= at and event.known_at <= at), Decimal("0"))
        ranked = tuple(sorted(candidates, key=self._rank))
        selected: list[str] = []; rejected: list[str] = []; links: list[HistoricalPaperLedgerLink] = []; created: list[BacktestPortfolioLedgerEvent] = []
        ranking = {candidate.signal_id: self._rank_input(candidate) for candidate in ranked}
        for candidate in ranked:
            fill = candidate.entry_fill
            raw_quantity, quantity, sizing_reason = self._quantity(candidate)
            if fill is None or not candidate.paper_outcome.filled or quantity is None:
                rejected.append(candidate.signal_id); continue
            gross = fill.price * quantity; fees = fill.fees * quantity
            needed = gross + fees
            if needed > available:
                rejected.append(candidate.signal_id); continue
            event_id = "paper-entry-" + manifest_fingerprint(run=run.backtest_run_id, signal=candidate.signal_id, fill=fill.fill_id)[:24]
            entry = BacktestPortfolioLedgerEvent(event_id, run.backtest_run_id, BacktestPortfolioLedgerType.HYPOTHETICAL_BUY,
                fill.timestamp, fill.timestamp, "historical-paper-fill", fill.fill_id, candidate.paper_trade.instrument_id,
                quantity, fill.price, gross, fees, Decimal("0"), -needed, None, candidate.sector, candidate.paper_trade.structural_stop)
            created.append(entry); available -= needed; selected.append(candidate.signal_id)
            link = self._link(run, candidate, quantity, entry, (), None, gross, Decimal("0"), fees, raw_quantity, needed, sizing_reason)
            links.append(link)
        allocation = HistoricalCapitalAllocation(
            "capital-allocation-" + manifest_fingerprint(run=run.backtest_run_id, at=at, candidates=[x.signal_id for x in ranked], selected=selected, policy=self.policy.version)[:24],
            run.backtest_run_id, replay_step_number, at, tuple(x.signal_id for x in ranked), ranking,
            starting_capital + sum((event.net_cash_impact for event in existing_ledger_events if event.event_type is not BacktestPortfolioLedgerType.INITIAL_CAPITAL and event.effective_at <= at and event.known_at <= at), Decimal("0")),
            sum((-event.net_cash_impact for event in created), Decimal("0")), tuple(selected), tuple(rejected),
            "RANK_ORDER_AVAILABLE_CASH", self.policy.version, "OPEN_MANAGEMENT_THEN_NEW_ENTRIES", tuple(link.link_id for link in links),
            tuple("INSUFFICIENT_CASH_OR_UNSUPPORTED_SIZING" for _ in rejected),
            manifest_fingerprint(run=run.fingerprint, policy=self.policy.version, candidates=ranking, selected=selected, rejected=rejected, cash=starting_capital),
        )
        for event in created: self.repository.append_backtest_portfolio_ledger_event(event)
        for link in links: self.repository.save_historical_paper_ledger_link(link)
        self.repository.save_historical_capital_allocation(allocation)
        self._events(run, replay_step_number, at, allocation, created)
        return AllocationApplication(allocation, tuple(links), tuple(created))

    def settle_outcome(self, *, run, replay_step_number: int, at, link: HistoricalPaperLedgerLink,
                       trade: PaperTrade, outcome: PaperOutcome, initial_fill: PaperFill, paper_events=(),
                       t1_reduction: Decimal = Decimal("0.5")) -> HistoricalPaperLedgerLink:
        """Emit ledger exits whose cash/cost total reconciles to the frozen outcome."""
        if not outcome.filled or outcome.final_exit_price is None or outcome.final_exit_timestamp is None:
            return link
        existing = self.repository.get_historical_paper_ledger_link(link.link_id)
        if existing is None or existing.entry_ledger_event_id != link.entry_ledger_event_id:
            raise ValueError("Paper outcome settlement requires the persisted immutable entry link.")
        partial_ids: list[str] = []; events: list[BacktestPortfolioLedgerEvent] = []; partial_quantity = Decimal("0"); proceeds = Decimal("0")
        if outcome.t1_reached and trade.target_1 is not None:
            partial_quantity = link.quantity * t1_reduction
            t1_event = next((event for event in paper_events if event.event_type.value == "T1"), None)
            t1_at = t1_event.timestamp if t1_event else outcome.final_exit_timestamp
            partial_id = "paper-t1-" + manifest_fingerprint(link=link.link_id, outcome=outcome.paper_trade_id)[:24]
            partial = BacktestPortfolioLedgerEvent(partial_id, run.backtest_run_id, BacktestPortfolioLedgerType.HYPOTHETICAL_SELL,
                t1_at, t1_at, "historical-paper-t1", t1_event.event_id if t1_event else link.link_id, trade.instrument_id,
                partial_quantity, trade.target_1, partial_quantity * trade.target_1, Decimal("0"), Decimal("0"), partial_quantity * trade.target_1, None, trade.sector)
            events.append(partial); partial_ids.append(partial_id); proceeds += partial.net_cash_impact
        residual = link.quantity - partial_quantity
        final_fees = max(Decimal("0"), outcome.costs - initial_fill.fees * link.quantity)
        final_id = "paper-exit-" + manifest_fingerprint(link=link.link_id, outcome=outcome.paper_trade_id, exit=outcome.final_exit_timestamp)[:24]
        final = BacktestPortfolioLedgerEvent(final_id, run.backtest_run_id, BacktestPortfolioLedgerType.HYPOTHETICAL_SELL,
            outcome.final_exit_timestamp, outcome.final_exit_timestamp, "historical-paper-exit", link.link_id, trade.instrument_id,
            residual, outcome.final_exit_price, residual * outcome.final_exit_price, final_fees, Decimal("0"), residual * outcome.final_exit_price - final_fees, None, trade.sector)
        events.append(final); proceeds += final.net_cash_impact
        # Links are immutable: settlement creates a distinct immutable linkage record.
        settled = __import__("dataclasses").replace(link, link_id=link.link_id + "-settled", paper_outcome_id=outcome.paper_trade_id,
            partial_exit_ledger_event_ids=tuple(partial_ids), final_exit_ledger_event_id=final_id, exit_proceeds=proceeds,
            realized_pnl=outcome.gross_pnl, costs=outcome.costs, net_pnl=outcome.net_pnl, source_bar_ids=outcome.price_bar_ids,
            fingerprint=manifest_fingerprint(parent=link.fingerprint, exits=[x.ledger_event_id for x in events], outcome=outcome.net_pnl))
        for event in events: self.repository.append_backtest_portfolio_ledger_event(event)
        self.repository.save_historical_paper_ledger_link(settled)
        for event in events: self._event(run, replay_step_number, at, BacktestEventType.BACKTEST_PARTIAL_EXIT_APPLIED if event.ledger_event_id in partial_ids else BacktestEventType.BACKTEST_EXIT_APPLIED, (settled.link_id,event.ledger_event_id), "PAPER_OUTCOME_SETTLED")
        return settled

    def _quantity(self, candidate: PaperFillCandidate) -> tuple[Decimal | None, Decimal | None, str]:
        fill, spec = candidate.entry_fill, candidate.sizing_specification
        if fill is None or fill.price <= 0: return None, None, "INVALID_ACTUAL_FILL_PRICE"
        if candidate.sizing_basis == "UNIT_BASIS": return Decimal("1"), Decimal("1"), "UNIT_BASIS"
        if spec is None or spec.sizing_basis != candidate.sizing_basis: return None, None, "MISSING_OR_MISMATCHED_FROZEN_SIZING_SPECIFICATION"
        if spec.minimum_quantity <= 0 or spec.quantity_rounding_policy != "FLOOR_INTEGER" or spec.fractional_shares_allowed:
            return None, None, "UNSUPPORTED_FROZEN_QUANTITY_POLICY"
        if candidate.sizing_basis == "FIXED_NOTIONAL":
            if spec.fixed_notional_amount is None or spec.fixed_notional_amount <= 0: return None, None, "MISSING_OR_INVALID_FIXED_NOTIONAL"
            raw = spec.fixed_notional_amount / fill.price
        elif candidate.sizing_basis in {"FIXED_R_R", "FIXED_RISK_R"}:
            if spec.fixed_risk_capital_amount is None or spec.fixed_risk_capital_amount <= 0: return None, None, "MISSING_OR_INVALID_FIXED_RISK_CAPITAL"
            if candidate.paper_trade.structural_stop is None: return None, None, "MISSING_STRUCTURAL_STOP"
            risk = abs(fill.price - candidate.paper_trade.structural_stop)
            if risk <= 0: return None, None, "INVALID_PER_UNIT_STRUCTURAL_RISK"
            raw = spec.fixed_risk_capital_amount / risk
        else: return None, None, "UNSUPPORTED_SIZING_BASIS"
        quantity = raw.to_integral_value(rounding=ROUND_FLOOR)
        if quantity < spec.minimum_quantity: return raw, None, "ROUNDED_QUANTITY_BELOW_MINIMUM"
        return raw, quantity, candidate.sizing_basis

    @staticmethod
    def _rank(candidate: PaperFillCandidate):
        return (-(candidate.score or Decimal("0")), -(Decimal(str(candidate.confidence)) if candidate.confidence is not None else Decimal("0")), -(candidate.risk_reward or Decimal("0")), candidate.signal_id)

    @staticmethod
    def _rank_input(candidate: PaperFillCandidate) -> tuple[str, str, str, str]:
        return (str(candidate.score or Decimal("0")), str(candidate.confidence if candidate.confidence is not None else 0), str(candidate.risk_reward or Decimal("0")), candidate.signal_id)

    @staticmethod
    def _link(run, candidate, quantity, entry, partials, final, entry_value, proceeds, costs, raw_quantity, required_cash, sizing_reason):
        spec=candidate.sizing_specification
        return HistoricalPaperLedgerLink("paper-ledger-link-" + manifest_fingerprint(run=run.backtest_run_id, signal=candidate.signal_id, trade=candidate.paper_trade.paper_trade_id)[:24], run.backtest_run_id, candidate.signal_id, candidate.paper_trade.paper_trade_id, None, candidate.entry_fill.fill_id, entry.ledger_event_id, partials, final, quantity, entry_value, proceeds, None, costs, None, candidate.sizing_basis, candidate.paper_trade.paper_configuration_version, candidate.entry_fill.source_bar_ids, (), manifest_fingerprint(run=run.fingerprint, trade=candidate.paper_trade.paper_trade_id, fill=candidate.entry_fill.fill_id, entry=entry.ledger_event_id, sizing=spec.fingerprint if spec else None), candidate.paper_config_snapshot_id, spec.fingerprint if spec else None, raw_quantity, required_cash, sizing_reason)

    def _events(self, run, step, at, allocation, events):
        for event in events: self._event(run, step, at, BacktestEventType.BACKTEST_FILL_APPLIED, (allocation.allocation_id,event.ledger_event_id), "HYPOTHETICAL_FILL_FUNDED")
        for signal_id in allocation.rejected_signal_ids: self._event(run, step, at, BacktestEventType.BACKTEST_ALLOCATION_REJECTED, (allocation.allocation_id,signal_id), "INSUFFICIENT_CASH_OR_UNSUPPORTED_SIZING")

    def _event(self, run, step, at, kind, refs, reason):
        sequence=len(self.repository.list_backtest_events(run.backtest_run_id))+1
        self.repository.append_backtest_event(BacktestEvent(f"{run.backtest_run_id}:event:{sequence:06d}",run.backtest_run_id,kind,at,step,at,tuple(refs),reason,{"reason":reason},at))
