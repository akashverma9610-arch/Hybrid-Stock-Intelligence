from datetime import UTC,datetime,timedelta
from decimal import Decimal
from app.performance.engine import PerformanceEngine
from app.performance.models import PerformanceConfig,TradePerformanceRecord
T=datetime(2026,1,1,tzinfo=UTC); C=PerformanceConfig("perf-v1",Decimal("10000"),252,Decimal("0"),5,20,50,(Decimal("8"),Decimal("9")))
def trade(i,pnl,r):return TradePerformanceRecord(i,"CLOSED_TARGET" if Decimal(pnl)>0 else "CLOSED_STOP",T,T+timedelta(days=i),Decimal(pnl),Decimal(pnl),Decimal(r),Decimal("9"),.9,"BULL","TECH","CONFIRMATION",Decimal("10"),Decimal("20"),Decimal("-5"))
def test_metrics_groups_drawdown_and_frozen_asof():
 report=PerformanceEngine(C).report(strategy_version="v1",start=T,end=T+timedelta(days=3),trades=(trade(1,"100",1),trade(2,"-50","-.5"),trade(3,"200",2)),generated_at=T)
 assert report.metrics["win_rate"]==Decimal(2)/3 and report.metrics["profit_factor"]==Decimal("6") and report.metrics["max_drawdown"]<0 and report.groups["sector"]["TECH"]["count"]==3
 assert PerformanceEngine(C).benchmark_return((Decimal("100"),Decimal("110")))==Decimal(".1")
