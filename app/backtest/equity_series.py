from __future__ import annotations

from decimal import Decimal

from app.historical.guard import manifest_fingerprint
from app.backtest.engine import ReplayClock
from app.backtest.portfolio import BacktestPortfolioReplayEngine

from .models import HistoricalEquityPoint, HistoricalEquitySeries


class HistoricalEquitySeriesService:
    """Samples the persisted session-end backtest portfolio state, never prices."""

    methodology_version = "historical-session-end-equity-v1"

    def __init__(self, repository) -> None: self.repository=repository

    def build(self, *, run, states, generated_at) -> tuple[HistoricalEquitySeries, tuple[HistoricalEquityPoint, ...]]:
        ordered=tuple(sorted((state for state in states if state.backtest_run_id==run.backtest_run_id and run.evaluation_start<=state.evaluation_timestamp<=run.evaluation_end),key=lambda state:(state.evaluation_timestamp,state.replay_step_number,state.backtest_portfolio_state_id)))
        if not ordered: raise ValueError("Historical equity series requires frozen portfolio states in the evaluation window.")
        ledger=self.repository.list_backtest_portfolio_ledger_events(run.backtest_run_id)
        points=[]
        for state in ordered:
            snapshot=state.snapshot
            holding_value=sum((holding.market_value or Decimal("0") for holding in snapshot.holdings),Decimal("0"))
            costs=sum((event.fees+event.taxes for event in ledger if event.effective_at<=state.evaluation_timestamp and event.known_at<=state.evaluation_timestamp),Decimal("0"))
            marks=tuple(sorted(set(state.price_reference_ids)))
            point=HistoricalEquityPoint("historical-equity-point-"+manifest_fingerprint(run=run.backtest_run_id,state=state.backtest_portfolio_state_id)[:24],run.backtest_run_id,state.evaluation_timestamp,snapshot.cash.amount,holding_value,snapshot.portfolio_equity if snapshot.portfolio_equity is not None else snapshot.cash.amount+holding_value,holding_value,holding_value,snapshot.realized_pnl,snapshot.unrealized_pnl,costs,len(snapshot.holdings),state.backtest_portfolio_state_id,marks,state.warnings,manifest_fingerprint(run=run.fingerprint,state=state.fingerprint,cash=snapshot.cash.amount,marks=marks,equity=snapshot.portfolio_equity))
            points.append(point)
        series=HistoricalEquitySeries("historical-equity-series-"+manifest_fingerprint(run=run.backtest_run_id,points=[point.fingerprint for point in points],version=self.methodology_version)[:24],run.backtest_run_id,tuple(point.point_id for point in points),run.initial_paper_capital,points[0].evaluation_timestamp,points[-1].evaluation_timestamp,generated_at,self.methodology_version,tuple(sorted({warning for point in points for warning in point.warnings})),manifest_fingerprint(run=run.fingerprint,points=[point.fingerprint for point in points],starting=run.initial_paper_capital,version=self.methodology_version))
        for point in points:self.repository.save_historical_equity_point(point)
        self.repository.save_historical_equity_series(series)
        return series,tuple(points)

    def build_session_complete(self, *, run, calendar, marks_by_session, generated_at):
        """Persist a valuation-only state for every frozen DAILY_CLOSE session.

        The ledger is read unchanged on every session; only historically
        eligible marks vary. This deliberately creates no synthetic cash or
        transaction event.
        """
        schedule=self.repository.get_replay_schedule(run.replay_schedule_id)
        if schedule is None or schedule.version != run.replay_schedule_version: raise ValueError("Session-complete equity requires the frozen replay schedule.")
        sessions=ReplayClock(schedule,calendar).timestamps(start=run.evaluation_start,end=run.evaluation_end)
        ledger=self.repository.list_backtest_portfolio_ledger_events(run.backtest_run_id)
        engine=BacktestPortfolioReplayEngine(calendar); states=[]
        for step,session in enumerate(sessions,1):
            marks=tuple(marks_by_session.get(session,()))
            state=engine.reconstruct(run_id=run.backtest_run_id,step_number=step,at=session,starting_capital=run.initial_paper_capital,events=ledger,prices=marks)
            self.repository.save_backtest_portfolio_state(state); states.append(state)
        series,points=self.build(run=run,states=tuple(states),generated_at=generated_at)
        if tuple(point.evaluation_timestamp for point in points)!=sessions: raise ValueError("Historical equity series has an unexplained session gap.")
        return series,points
