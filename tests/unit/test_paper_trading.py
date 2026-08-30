from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from app.gates.engine import ExchangeCalendar
from app.paper.engine import PaperTradingEngine
from app.paper.models import *
from tests.unit.test_signal_lifecycle import create, plan

T=datetime(2026,8,20,10,tzinfo=UTC)
CFG=PaperTradingConfig("paper-v1",CreationPolicy.GENERATED,FillMethod.MARKETABLE_TRIGGER_FILL,SameBarPolicy.CONSERVATIVE_STOP_FIRST,GapPolicy.MARKET_OPEN,SizingBasis.UNIT_BASIS,Decimal("0"),Decimal("0"),"cost-v1",Decimal("0"),Decimal(".5"),Decimal(".5"),True,InvalidationPolicy.EXIT_ON_INVALIDATION,3,5,"daily")
E=PaperTradingEngine(CFG,ExchangeCalendar("nse",frozenset()))
def trade():
 s,_=create();return E.create(s,plan(),instrument_id="stock",generated_at=T)
def bar(i,o,h,l,c,days=0,valid=True):return PaperBar(f"bar-{i}",T+timedelta(days=days),T+timedelta(days=days),Decimal(o),Decimal(h),Decimal(l),Decimal(c),"daily",valid)
def test_unfilled_trigger_target_stop_and_same_bar_policy():
 events,fills,out=E.simulate(trade(),(bar("wait",100,104,99,104),bar("expiry",100,104,99,103,days=6)),T+timedelta(days=6));assert out.state is PaperTradeState.UNFILLED and not fills
 events,fills,out=E.simulate(trade(),(bar("entry",100,107,100,106),bar("t1",106,126,105,125,days=1),bar("t2",125,136,120,135,days=2)),T+timedelta(days=2));assert out.t1_reached and out.t2_reached and out.state is PaperTradeState.CLOSED_TARGET
 events,fills,out=E.simulate(trade(),(bar("entry",100,107,100,106),bar("both",106,126,94,110,days=1)),T+timedelta(days=1));assert out.state is PaperTradeState.CLOSED_STOP
def test_gap_invalid_future_and_bad_bars_fail_closed_without_real_mutation():
 events,fills,out=E.simulate(trade(),(bar("entry",100,107,100,106),bar("gap",90,96,89,92,days=1)),T+timedelta(days=1));assert out.final_exit_price==Decimal("90") and out.stop_hit
 events,fills,prior=E.simulate(trade(),(bar("entry",100,107,100,106),bar("future",106,140,105,139,days=2)),T-timedelta(seconds=1));assert not prior.filled
 events,fills,bad=E.simulate(trade(),(bar("bad",100,107,99,106,valid=False),),T);assert bad.state is PaperTradeState.INSUFFICIENT_DATA
def test_original_signal_is_untouched_and_no_broker_order_exists():
 s,_=create();before=s; E.simulate(E.create(s,plan(),instrument_id="stock",generated_at=T),(bar("entry",100,107,100,106),),T);assert s==before and not hasattr(s,"broker_order")
