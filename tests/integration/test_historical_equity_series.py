from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

import pytest

from app.backtest.equity_series import HistoricalEquitySeriesService
from app.backtest.performance import HistoricalPerformanceIntegrationService
from app.backtest.models import BacktestRunStatus
from app.backtest.portfolio import BacktestPortfolioLedgerEvent, BacktestPortfolioLedgerType, BacktestPortfolioReplayEngine
from app.performance.models import PerformanceConfig
from app.portfolio.models import PriceReference
from app.services.audit_reconstruction_service import AuditReconstructionError, AuditReconstructionService
from tests.unit.test_backtest_portfolio_replay import CALENDAR, T, setup_repo


def event(identifier, run_id, kind, at, *, instrument=None, quantity=None, price=None, cash=Decimal("0")):
    gross=(quantity or Decimal("0"))*(price or Decimal("0"))
    return BacktestPortfolioLedgerEvent(identifier,run_id,kind,at,at,"fixture",identifier,instrument,quantity,price,gross,Decimal("0"),Decimal("0"),cash)


def test_session_equity_series_uses_cash_plus_open_marked_holdings_and_is_auditable(tmp_path):
    repo, original=setup_repo(tmp_path)
    run=replace(original,backtest_run_id="equity-run",evaluation_end=T+timedelta(days=4),status=BacktestRunStatus.COMPLETED,fingerprint="equity-run-fingerprint")
    repo.save_backtest_run(run)
    ledger=(event("initial",run.backtest_run_id,BacktestPortfolioLedgerType.INITIAL_CAPITAL,T,cash=Decimal("100")),event("buy",run.backtest_run_id,BacktestPortfolioLedgerType.HYPOTHETICAL_BUY,T,instrument="A",quantity=Decimal("4"),price=Decimal("10"),cash=Decimal("-40")))
    for item in ledger: repo.append_backtest_portfolio_ledger_event(item)
    engine=BacktestPortfolioReplayEngine(CALENDAR); states=[]
    for step, (at, price) in enumerate(((T,Decimal("10")),(T+timedelta(days=3),Decimal("5")),(T+timedelta(days=4),Decimal("10"))),1):
        state=engine.reconstruct(run_id=run.backtest_run_id,step_number=step,at=at,starting_capital=Decimal("100"),events=ledger,prices=(PriceReference(f"mark-{step}","A",price,at,at),))
        repo.save_backtest_portfolio_state(state); states.append(state)
    series,points=HistoricalEquitySeriesService(repo).build(run=run,states=tuple(states),generated_at=states[-1].evaluation_timestamp)
    assert [point.equity for point in points]==[Decimal("100"),Decimal("80"),Decimal("100")]
    assert points[1].gross_exposure==Decimal("20") and points[-1].frozen_mark_ids==("mark-3",)
    assert repo.get_historical_equity_series(series.series_id)==series and AuditReconstructionService(repo).reconstruct_historical_equity_series(series.series_id)[0]==series
    report=HistoricalPerformanceIntegrationService(repo,CALENDAR,PerformanceConfig("equity-performance-v1",Decimal("100"),252,Decimal("0"),2,3,4,())).generate(run=run,paper_trade_ids=(),generated_at=states[-1].evaluation_timestamp,equity_series=series).report
    assert report.metrics["portfolio_return"]==Decimal("0") and report.metrics["max_drawdown"]==Decimal("-.2")
    with pytest.raises(ValueError,match="immutable"): repo.save_historical_equity_series(series)
    future=PriceReference("future","A",Decimal("999"),T+timedelta(days=5),T+timedelta(days=5))
    assert future.observation_id not in str(repo.get_historical_equity_series(series.series_id))


def test_session_complete_builder_creates_no_trade_day_valuations_without_synthetic_ledger_events(tmp_path):
    repo, original=setup_repo(tmp_path)
    schedule=repo.get_replay_schedule(original.replay_schedule_id)
    schedule=replace(schedule,schedule_id="complete-schedule",start=T.replace(hour=0,minute=0),end=T+timedelta(days=4))
    # Tuesday's close is inside the window; weekend sessions are excluded.
    schedule=replace(schedule,end=(T+timedelta(days=4)).replace(hour=15,minute=30))
    repo.save_replay_schedule(schedule)
    run=replace(original,backtest_run_id="complete-equity-run",replay_schedule_id=schedule.schedule_id,evaluation_start=schedule.start,evaluation_end=schedule.end,fingerprint="complete-equity-run-fingerprint")
    repo.save_backtest_run(run)
    ledger=(event("complete-initial",run.backtest_run_id,BacktestPortfolioLedgerType.INITIAL_CAPITAL,T,cash=Decimal("100")),event("complete-buy",run.backtest_run_id,BacktestPortfolioLedgerType.HYPOTHETICAL_BUY,T,instrument="A",quantity=Decimal("4"),price=Decimal("10"),cash=Decimal("-40")))
    for item in ledger: repo.append_backtest_portfolio_ledger_event(item)
    sessions=(T,T+timedelta(days=3),T+timedelta(days=4))
    marks={session:(PriceReference(f"complete-mark-{index}","A",price,session,session),) for index,(session,price) in enumerate(zip(sessions,(Decimal("10"),Decimal("8"),Decimal("11"))),1)}
    series,points=HistoricalEquitySeriesService(repo).build_session_complete(run=run,calendar=CALENDAR,marks_by_session=marks,generated_at=sessions[-1])
    assert [point.evaluation_timestamp for point in points]==list(sessions)
    assert [point.equity for point in points]==[Decimal("100"),Decimal("92"),Decimal("104")]
    assert len(repo.list_backtest_portfolio_ledger_events(run.backtest_run_id))==2
    assert AuditReconstructionService(repo).reconstruct_historical_equity_series(series.series_id)[0]==series
