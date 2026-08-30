from __future__ import annotations
from dataclasses import FrozenInstanceError
import pytest
from app.intelligence.intelligence_delta import compare_intelligence_states, IntelligenceDeltaStatus
from app.intelligence.intelligence_delta_projection import project_intelligence_delta
from app.intelligence.unified_state import IntelligenceEvidenceDomain
from tests.unit.test_intelligence_delta import _pair, _reference

def test_projection_is_deterministic_immutable_and_action_free():
    p,c=_pair((),(_reference(IntelligenceEvidenceDomain.NEWS_CATALYSTS),)); d=compare_intelligence_states(p,c); a=project_intelligence_delta(d)
    assert a==project_intelligence_delta(d) and a.changed_domain_count==1
    assert not any(hasattr(a,x) for x in ('action','recommendation','alert','buy','sell','hold'))
    with pytest.raises(FrozenInstanceError): a.changed_domain_count=0

def test_no_change_is_clean():
    r=_reference(IntelligenceEvidenceDomain.MARKET_DATA); p,c=_pair((r,),(r,)); a=project_intelligence_delta(compare_intelligence_states(p,c))
    assert a.overall_change_status is IntelligenceDeltaStatus.NO_SEMANTIC_CHANGE and a.changed_domains==() and a.affected_output_contexts==()
