from datetime import UTC,datetime,timedelta
from app.historical.guard import BacktestLookaheadGuard,validate_partitions
from app.historical.models import *
T=datetime(2026,7,10,tzinfo=UTC);G=BacktestLookaheadGuard()
def fact(i,kind,event,pub,effective=None):return HistoricalFact(i,kind,event,pub,pub,effective)
def test_reschedule_restatement_surveillance_and_actions_respect_knowledge_time():
 original=fact('earnings-aug10','earnings_schedule',datetime(2026,7,1,tzinfo=UTC),datetime(2026,7,1,tzinfo=UTC));rescheduled=fact('earnings-aug5','earnings_schedule',datetime(2026,7,20,tzinfo=UTC),datetime(2026,7,20,tzinfo=UTC));assert G.evaluate(original,T) is Eligibility.ELIGIBLE and G.evaluate(rescheduled,T) is Eligibility.INELIGIBLE_FUTURE_EVENT
 base=fact('financial-original','financial',datetime(2026,8,10,tzinfo=UTC),datetime(2026,8,10,tzinfo=UTC));restated=fact('financial-restatement','financial',datetime(2026,11,5,tzinfo=UTC),datetime(2026,11,5,tzinfo=UTC));oct=datetime(2026,10,1,tzinfo=UTC);assert G.evaluate(base,oct) is Eligibility.ELIGIBLE and G.evaluate(restated,oct) is Eligibility.INELIGIBLE_FUTURE_EVENT
 for k in ('surveillance','split','bonus','dividend'):assert G.evaluate(fact('future-'+k,k,T+timedelta(days=1),T+timedelta(days=1),T+timedelta(days=1)),T) is Eligibility.INELIGIBLE_FUTURE_EVENT
def test_universe_lifecycle_static_gaps_and_partition_edges():
 a=UniverseMembership('a','A','u',datetime(2026,1,10,tzinfo=UTC),None,datetime(2026,1,10,tzinfo=UTC),'x','p',InstrumentLifecycle.ACTIVE);b=UniverseMembership('b','B','u',datetime(2026,1,1,tzinfo=UTC),datetime(2026,3,1,tzinfo=UTC),datetime(2026,1,1,tzinfo=UTC),'x','p',InstrumentLifecycle.DELISTED);assert G.membership(a,datetime(2026,1,9,tzinfo=UTC)) is Eligibility.INELIGIBLE_NOT_EFFECTIVE and G.membership(a,datetime(2026,1,11,tzinfo=UTC)) is Eligibility.ELIGIBLE and G.membership(b,datetime(2026,2,1,tzinfo=UTC)) is Eligibility.ELIGIBLE
 p1=HistoricalPartition('train','d',PartitionType.TRAIN,datetime(2026,1,1,tzinfo=UTC),datetime(2026,1,2,tzinfo=UTC),2,1,'',T);p2=HistoricalPartition('test','d',PartitionType.TEST,datetime(2026,1,3,tzinfo=UTC),datetime(2026,1,4,tzinfo=UTC),0,0,'',T);validate_partitions((p1,p2))
