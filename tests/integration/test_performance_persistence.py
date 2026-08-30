from datetime import UTC,datetime
from decimal import Decimal
import pytest
from app.performance.engine import PerformanceEngine
from app.performance.models import PerformanceConfig,PerformanceEvaluationDataset,TradePerformanceRecord
from app.performance.benchmarks import buy_hold
from app.performance.reporting import compare
from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository
T=datetime(2026,6,30,tzinfo=UTC)
def test_performance_roundtrip_and_immutable_benchmarks(tmp_path):
 repo=SQLiteStrategyGovernanceRepository(tmp_path/'p.db');cfg=PerformanceConfig('v1',Decimal('1000'),252,Decimal('0'),2,3,4,(Decimal('8'),));trade=TradePerformanceRecord('pt','CLOSED_TARGET',T,T,Decimal('100'),Decimal('110'),Decimal('1'),Decimal('9'),.9,'BULL','TECH','CONF',Decimal('10'),Decimal('20'),Decimal('-5'));report=PerformanceEngine(cfg).report(strategy_version='s1',start=T,end=T,trades=(trade,),generated_at=T);data=PerformanceEvaluationDataset('dataset','s1','r','sc','g',None,'sig','paper','eval',T,T,('pt',),('sig',),('index-june',),('nifty-v1',),'cost','nse','frozen')
 repo.save_performance_dataset(data);repo.save_performance_report(report,'dataset');run=buy_hold('nifty50_buy_hold',(Decimal('100'),Decimal('110')));comparison=compare('nifty50','v1',report.metrics,run.net_return);repo.save_benchmark_run('run',report.report_id,run,('index-june',),'v1',T);repo.save_benchmark_comparison('comparison',report.report_id,comparison)
 assert repo.get_performance_dataset('dataset')==data and repo.get_performance_report(report.report_id)==report and repo.list_benchmark_runs(report.report_id)==(run,) and repo.list_benchmark_comparisons(report.report_id)==(comparison,)
 with pytest.raises(ValueError):repo.save_performance_report(report,'dataset')
 with pytest.raises(ValueError):repo.save_benchmark_run('run',report.report_id,run,(), 'v1',T)
 with pytest.raises(ValueError):repo.save_benchmark_comparison('comparison',report.report_id,comparison)
