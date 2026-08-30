from datetime import UTC,datetime
from decimal import Decimal
from app.performance.grouped import analyze
from app.performance.models import PerformanceConfig,TradePerformanceRecord
T=datetime(2026,1,1,tzinfo=UTC);C=PerformanceConfig('v',Decimal('1'),252,Decimal('0'),2,3,4,())
def test_grouped_confidence_catalyst_exit_funnel_and_excursions():
 a=TradePerformanceRecord('a','CLOSED_TARGET',T,T,Decimal('2'),Decimal('2'),Decimal('1'),None,.9,None,None,None,Decimal('0'),Decimal('3'),Decimal('-1'),catalyst_type='RESULTS',catalyst_clock='IMMEDIATE',holding_sessions=1,triggered=True,filled=True,t1_hit=True,t2_hit=True,mfe_r=Decimal('1.5'),mae_r=Decimal('-.5'))
 b=TradePerformanceRecord('b','UNFILLED',None,None,None,None,None,None,None,None,None,None,Decimal('0'),None,None)
 r=analyze((a,b),C);assert r['confidence']['HIGH']['setup_count']==1 and r['confidence']['UNAVAILABLE']['setup_count']==1 and r['exit_metrics']['t1_hit_rate']==Decimal('1') and r['funnel']['unfilled']==1 and r['excursion']['average_mfe']==Decimal('3')
