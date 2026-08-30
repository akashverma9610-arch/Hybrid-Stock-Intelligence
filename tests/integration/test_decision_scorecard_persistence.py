from dataclasses import replace
import pytest

from app.services.audit_reconstruction_service import AuditReconstructionService
from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository
from app.scoring.engine import build_scorecard
from tests.fixtures.analytical_observations import ANALYSIS_TIME
from tests.fixtures.governance_records import strategy_definition
from tests.unit.test_decision_score import complete

def persisted(tmp_path, version="0.1"):
    repo=SQLiteStrategyGovernanceRepository(tmp_path/f"score-{version}.db"); definition=strategy_definition(version); repo.save_strategy_definition(definition)
    items=tuple(replace(x,record=replace(x.record,strategy_version=definition.reference)) for x in complete())
    for item in items: repo.save_diagnostic_result(item.record)
    card=build_scorecard(instrument_id="stock",strategy_version=definition.reference,registry_version="diagnostic-registry-v1",as_of_timestamp=ANALYSIS_TIME,evaluated_at=ANALYSIS_TIME,diagnostics=items)
    return repo,card

def test_complete_and_incomplete_scorecards_persist_immutably_with_components(tmp_path):
    repo,card=persisted(tmp_path); repo.save_decision_scorecard(card)
    assert repo.get_decision_scorecard(card.id)==card and len(card.components)==10
    with pytest.raises(ValueError): repo.save_decision_scorecard(card)
    incomplete=replace(card,id="incomplete",final_score=None,score_status="SCORE_INCOMPLETE")
    repo.save_decision_scorecard(incomplete); assert repo.get_decision_scorecard("incomplete").score_status=="SCORE_INCOMPLETE"; repo.close()

def test_referential_and_asof_integrity_and_reconstruction(tmp_path):
    repo,card=persisted(tmp_path); repo.save_decision_scorecard(card)
    assert AuditReconstructionService(repo).reconstruct_decision_scorecard(card.id)==card
    future=replace(card,id="future",components=tuple(replace(x,diagnostic_ids=("missing",)) for x in card.components))
    with pytest.raises(ValueError): repo.save_decision_scorecard(future)
    repo.close()

def test_scoring_configuration_versions_are_append_only(tmp_path):
    repo,card=persisted(tmp_path); repo.save_decision_scorecard(card); v2=replace(card,id="v2",configuration_version="decision-score-v2")
    repo.save_decision_scorecard(v2)
    assert repo.get_decision_scorecard(card.id).configuration_version=="decision-score-v1" and repo.get_decision_scorecard("v2").configuration_version=="decision-score-v2"; repo.close()
