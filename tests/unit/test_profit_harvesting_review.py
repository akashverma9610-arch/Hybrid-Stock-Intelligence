from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
import pytest
from app.crisis.models import UpsideExcessState
from app.intelligence.market_extremes_assurance_projection import MarketExtremesAssuranceState
from app.intelligence.profit_harvesting_review import *
from tests.unit.test_market_extremes_assurance_projection import _assessment, _candidate, _context
from app.intelligence.market_extremes_assurance_projection import project_market_extremes_assurance

T=datetime(2026,9,3,10,tzinfo=UTC)
def assurance(state=UpsideExcessState.EUPHORIA): return project_market_extremes_assurance(_context(),(_candidate(assessment=_assessment(state=state)),))
def test_euphoria_maps_to_monitor_only():
 v=evaluate_profit_harvesting_review(assurance=assurance())
 assert v.status is ProfitHarvestingReviewStatus.MONITOR_PROFIT and v.selected_regime is UpsideExcessState.EUPHORIA
 assert v.actionability is ProfitHarvestingActionability.WATCH_ONLY and v.execution_status is ProfitHarvestingExecutionStatus.NON_EXECUTABLE
def test_all_other_ready_regimes_map_to_no_evidence():
 for state in (UpsideExcessState.NORMAL,UpsideExcessState.OPTIMISM,UpsideExcessState.CROWDING,UpsideExcessState.SPECULATION,UpsideExcessState.DISTRIBUTION,UpsideExcessState.BREAKDOWN):
  assert evaluate_profit_harvesting_review(assurance=assurance(state)).status is ProfitHarvestingReviewStatus.NO_PROFIT_REVIEW_EVIDENCE
def test_nonready_mapping_and_lineage():
 unavailable=project_market_extremes_assurance(_context(),())
 future=project_market_extremes_assurance(_context(),(_candidate(assessment=_assessment(data_as_of=T+timedelta(1),assessed_at=T+timedelta(2))),))
 stale=project_market_extremes_assurance(_context(),(_candidate(assessment=_assessment(data_as_of=T-timedelta(days=2),assessed_at=T-timedelta(days=2)+timedelta(minutes=1))),))
 left=_candidate(snapshot_id='left');right=_candidate(snapshot_id='right',assessment=_assessment(assessment_id='right',warning='OTHER'))
 conflicted=project_market_extremes_assurance(_context(),(left,right))
 for value in (unavailable,future,stale): assert evaluate_profit_harvesting_review(assurance=value).status is ProfitHarvestingReviewStatus.PROFIT_REVIEW_UNAVAILABLE
 review=evaluate_profit_harvesting_review(assurance=conflicted)
 assert review.status is ProfitHarvestingReviewStatus.CONFLICTED_PROFIT_REVIEW and review.assurance_reason_codes==conflicted.reason_codes
def test_deterministic_immutable_and_tamper_detecting():
 one=evaluate_profit_harvesting_review(assurance=assurance(),canonical_instrument_id='NSE:INE000A01001');two=evaluate_profit_harvesting_review(assurance=assurance(),canonical_instrument_id='NSE:INE000A01001')
 assert one.review_id==two.review_id and serialize_profit_harvesting_review(one)==serialize_profit_harvesting_review(two)
 with pytest.raises(FrozenInstanceError): one.status=ProfitHarvestingReviewStatus.NO_PROFIT_REVIEW_EVIDENCE
 object.__setattr__(one,'fingerprint','sha256:'+'0'*64)
 with pytest.raises(ProfitHarvestingReviewError): one.verify()
def test_domains_stay_unavailable_and_no_priority_or_execution_fields():
 value=evaluate_profit_harvesting_review(assurance=assurance())
 assert ProfitHarvestingUnavailableDomain.VALUATION_EXTENSION in value.unavailable_domains
 assert 'PRIORITY_PROFIT_REVIEW' not in {x.value for x in ProfitHarvestingReviewStatus}
 assert not ({'price','target','quantity','portfolio','order'} & set(value.__dataclass_fields__))
