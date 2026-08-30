from datetime import UTC,datetime
from decimal import Decimal
from app.performance.engine import PerformanceEngine
from app.performance.models import PerformanceConfig,PerformanceEvaluationDataset,TradePerformanceRecord
from app.performance.benchmarks import buy_hold
from app.performance.reporting import compare
from app.services.audit_reconstruction_service import AuditReconstructionService
from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository
JUNE=datetime(2026,6,30,tzinfo=UTC);JULY=datetime(2026,7,31,tzinfo=UTC);C=PerformanceConfig('v',Decimal('1000'),252,Decimal('0'),2,3,4,())
def record(i,t,pnl):return TradePerformanceRecord(i,'CLOSED_TARGET',t,t,Decimal(pnl),Decimal(pnl),Decimal(pnl)/100,None,.9,'BULL','TECH','CONF',Decimal('0'),Decimal('2'),Decimal('-1'))
def dataset(i,end,trade_ids,inputs):return PerformanceEvaluationDataset(i,'s','registry','score','gate',None,'signal','paper','eval',JUNE,end,trade_ids,('sig',),inputs,('nifty-v1','momentum-v1'),'cost','nse','event_and_retrieval_at_or_before_cutoff')
def save(repo,ds,report,run,comparison):repo.save_performance_dataset(ds);repo.save_performance_report(report,ds.dataset_id);repo.save_benchmark_run('run-'+ds.dataset_id,report.report_id,run,ds.benchmark_input_ids,'v1',ds.end);repo.save_benchmark_comparison('cmp-'+ds.dataset_id,report.report_id,comparison)
def test_june_report_is_frozen_against_all_eight_future_input_classes(tmp_path):
 repo=SQLiteStrategyGovernanceRepository(tmp_path/'frozen.db'); june=record('june-trade',JUNE,'100');a=PerformanceEngine(C).report(strategy_version='s',start=JUNE,end=JUNE,trades=(june,),generated_at=JUNE);a=a.__class__(*a.__dict__.values()) if False else a
 ds=dataset('june-dataset',JUNE,('june-trade',),('june-nifty50','june-nifty500','june-sector','june-momentum','june-ma','june-universe','june-prior'));run=buy_hold('nifty50_buy_hold',(Decimal('100'),Decimal('110')));save(repo,ds,a,run,compare('nifty50','v1',a.metrics,run.net_return)); frozen=(repo.get_performance_report(a.report_id),repo.get_performance_dataset(ds.dataset_id),repo.list_benchmark_runs(a.report_id),repo.list_benchmark_comparisons(a.report_id),AuditReconstructionService(repo).reconstruct_performance_report(a.report_id))
 future=record('july-paper-outcome',JULY,'-500');b=PerformanceEngine(C).report(strategy_version='s',start=JUNE,end=JULY,trades=(june,future),generated_at=JULY);dsb=dataset('july-dataset',JULY,('june-trade','july-paper-outcome'),('july-nifty50','july-nifty500','july-sector','july-momentum','july-ma','july-universe','july-prior'));runb=buy_hold('nifty50_buy_hold',(Decimal('100'),Decimal('50')));save(repo,dsb,b,runb,compare('nifty50','v1',b.metrics,runb.net_return))
 after=(repo.get_performance_report(a.report_id),repo.get_performance_dataset(ds.dataset_id),repo.list_benchmark_runs(a.report_id),repo.list_benchmark_comparisons(a.report_id),AuditReconstructionService(repo).reconstruct_performance_report(a.report_id));assert frozen==after and a!=b and 'july' not in str(after)
