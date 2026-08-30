from datetime import UTC,datetime,timedelta
from app.historical.guard import BacktestLookaheadGuard,manifest_fingerprint,validate_partitions
from app.historical.models import *
T=datetime(2026,7,15,tzinfo=UTC)
def test_point_in_time_guard_fails_closed_for_all_historical_fact_classes():
 g=BacktestLookaheadGuard();kinds=('stock','nifty','sector','financial','restatement','news','crowd','surveillance','earnings_reschedule','corporate_action')
 for k in kinds:assert g.evaluate(HistoricalFact(k,k,T+timedelta(days=1),T+timedelta(days=1),T+timedelta(days=1)),T) is Eligibility.INELIGIBLE_FUTURE_EVENT
 assert g.evaluate(HistoricalFact('published','financial',T,T+timedelta(days=1),T),T) is Eligibility.INELIGIBLE_FUTURE_PUBLICATION
def test_universe_fingerprint_and_partitions():
 g=BacktestLookaheadGuard();m=UniverseMembership('m','A','u',T,T+timedelta(days=1),T,'x','p',InstrumentLifecycle.ACTIVE);assert g.membership(m,T) is Eligibility.ELIGIBLE and g.membership(m,T-timedelta(days=1)) is Eligibility.INELIGIBLE_NOT_EFFECTIVE
 assert manifest_fingerprint(a=1)==manifest_fingerprint(a=1) and manifest_fingerprint(a=1)!=manifest_fingerprint(a=2)
 a=HistoricalPartition('a','d',PartitionType.TRAIN,T,T,0,0,'',T);b=HistoricalPartition('b','d',PartitionType.TEST,T,T,0,0,'',T)
 try:validate_partitions((a,b))
 except ValueError:pass
 else:raise AssertionError('overlap accepted')
