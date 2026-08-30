from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

import pytest

from app.backtest.models import BacktestRunStatus
from app.backtest.performance import HistoricalPerformanceIntegrationService
from app.performance.models import PerformanceConfig
from app.services.audit_reconstruction_service import AuditReconstructionService
from tests.integration.test_historical_analytical_replay import CALENDAR, setup
from tests.integration.test_historical_signal_paper_chronology_matrix import T, bar, through_timing


def completed(run):
    return replace(run, status=BacktestRunStatus.COMPLETED, evaluation_start=T, evaluation_end=T + timedelta(days=5), created_at=T)


def test_completed_historical_run_normalizes_frozen_paper_outcomes_into_existing_performance_and_benchmarks(tmp_path):
    repo, _manifest, schedule, _gap, raw_run, _config=setup(tmp_path); run=completed(raw_run); repo.save_replay_schedule(schedule); repo.save_backtest_run(run)
    entry=bar("performance-entry",T+timedelta(days=1),"106","108","105","106")
    target=bar("performance-target",T+timedelta(days=4),"106","140","105","135")
    signal, _timing, trade, _events, fills, outcome=through_timing(bars=(bar("performance-trigger",T,"100","106","99","106"),entry,target),replay_at=target.timestamp)
    repo.save_signal(signal); repo.save_paper_trade(trade); repo.save_paper_outcome(outcome)
    cfg=PerformanceConfig("historical-performance-v1",Decimal("1000"),252,Decimal("0"),2,3,4,(Decimal("8"),))
    result=HistoricalPerformanceIntegrationService(repo,CALENDAR,cfg).generate(run=run,paper_trade_ids=(trade.paper_trade_id,),generated_at=target.timestamp,benchmark_series={"nifty50_buy_hold":(Decimal("100"),Decimal("110")),"nifty500_buy_hold":()})
    assert result.dataset.paper_trade_ids==(trade.paper_trade_id,) and result.report.metrics["closed_trades"]==1
    assert result.normalized_trades[0].net_pnl==outcome.net_pnl and result.normalized_trades[0].holding_sessions==1
    assert len(repo.list_benchmark_runs(result.report.report_id))==2 and "BENCHMARK_UNAVAILABLE:nifty500_buy_hold" in result.warnings
    assert AuditReconstructionService(repo).reconstruct_performance_report(result.report.report_id)[0]==result.report
    frozen=repo.get_performance_report(result.report.report_id)
    later=bar("future",T+timedelta(days=10),"135","300","130","290")
    assert repo.get_performance_report(result.report.report_id)==frozen and later.bar_id not in str(frozen)


def test_incomplete_run_is_not_eligible_for_historical_performance(tmp_path):
    repo, _manifest, schedule, _gap, run, _config=setup(tmp_path); repo.save_replay_schedule(schedule); repo.save_backtest_run(run)
    cfg=PerformanceConfig("historical-performance-v1",Decimal("1000"),252,Decimal("0"),2,3,4,())
    with pytest.raises(ValueError,match="completed"):
        HistoricalPerformanceIntegrationService(repo,CALENDAR,cfg).generate(run=run,paper_trade_ids=(),generated_at=T)
