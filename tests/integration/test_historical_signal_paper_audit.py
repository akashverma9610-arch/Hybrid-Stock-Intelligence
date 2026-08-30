from dataclasses import replace
from decimal import Decimal
import json

import pytest

from app.backtest.models import HistoricalSignalReplayReference, HistoricalPaperReplayReference, SignalConfigSnapshot, PaperTradingConfigSnapshot
from app.historical.guard import manifest_fingerprint
from app.paper.engine import PaperTradingEngine
from app.services.audit_reconstruction_service import AuditReconstructionError, AuditReconstructionService
from app.backtest.serialization import dump as backtest_dump
from tests.integration.test_historical_rotation_replay import persisted_rotation
from tests.unit.test_signal_lifecycle import create, CONFIG as BASE_SIGNAL_CONFIG
from tests.unit.test_paper_trading import CFG, E, plan


def audited_chain(tmp_path):
    repo, run, candidate, _scorecard, state, gate, _holding, _context, _history, rotation, _result = persisted_rotation(tmp_path)
    at=candidate.evaluation_timestamp
    signal_config=replace(BASE_SIGNAL_CONFIG, version=run.signal_config_version)
    paper_config=replace(CFG, version=run.paper_config_version)
    signal_snapshot=SignalConfigSnapshot("audit-signal-config",signal_config,at,(),manifest_fingerprint(config=signal_config))
    paper_snapshot=PaperTradingConfigSnapshot("audit-paper-config",paper_config,at,(),manifest_fingerprint(config=paper_config))
    repo.save_signal_config_snapshot(signal_snapshot); repo.save_paper_config_snapshot(paper_snapshot)
    signal,event=create(); signal=replace(signal,as_of_timestamp=at,generated_at=at,registry_version=run.registry_version,scoring_configuration_version=run.scoring_config_version,gate_configuration_version=run.gate_config_version,rotation_configuration_version=run.rotation_config_version,portfolio_snapshot_id=state.snapshot.snapshot_id,decision_scorecard_id=candidate.decision_scorecard_id,execution_gate_evaluation_id=gate.resulting_execution_gate_evaluation_id,portfolio_rotation_evaluation_id=rotation.rotation_evaluation_id)
    event=replace(event,signal_id=signal.signal_id,event_timestamp=at,as_of_timestamp=at,scorecard_id=signal.decision_scorecard_id,gate_evaluation_id=signal.execution_gate_evaluation_id,rotation_evaluation_id=rotation.rotation_evaluation_id)
    repo.save_trade_plan(plan()); repo.save_signal(signal); repo.append_signal_event(event)
    signal_ref=HistoricalSignalReplayReference("audit-signal-ref",run.backtest_run_id,1,at,candidate.evaluation_id,gate.portfolio_gate_evaluation_id,rotation.rotation_evaluation_id,state.backtest_portfolio_state_id,signal.signal_id,signal_config.version,plan().plan_id,"v1",signal.status.value,None,(),"signal-ref-fp",signal_snapshot.snapshot_id,signal_snapshot.fingerprint)
    repo.save_historical_signal_replay_reference(signal_ref)
    trade=PaperTradingEngine(paper_config,E.calendar).create(signal,plan(),instrument_id=signal.instrument_id,generated_at=at); repo.save_paper_trade(trade)
    events,fills,outcome=PaperTradingEngine(paper_config,E.calendar).simulate(trade,(),at)
    for event_item in events: repo.append_paper_lifecycle_event(event_item)
    repo.save_paper_outcome(outcome)
    paper_ref=HistoricalPaperReplayReference("audit-paper-ref",run.backtest_run_id,signal.signal_id,trade.paper_trade_id,outcome.paper_trade_id,(1,),outcome.price_bar_ids,paper_config.version,paper_config.cost_model_version,paper_config.fill_method.value,paper_config.same_bar_policy.value,paper_config.gap_policy.value,outcome.state.value,(),"paper-ref-fp",paper_snapshot.snapshot_id,paper_snapshot.fingerprint)
    repo.save_historical_paper_replay_reference(paper_ref)
    return repo, signal_ref, paper_ref


def test_historical_signal_and_paper_audits_and_config_tampers_fail_closed(tmp_path):
    repo, signal_ref, paper_ref=audited_chain(tmp_path)
    assert AuditReconstructionService(repo).reconstruct_historical_signal_replay_reference(signal_ref.reference_id)[0] == signal_ref
    assert AuditReconstructionService(repo).reconstruct_historical_paper_replay_reference(paper_ref.reference_id)[0] == paper_ref
    for table, identifier, tampered in (("historical_signal_replay_references",signal_ref.reference_id,replace(signal_ref,signal_config_snapshot_id="missing")),("historical_paper_replay_references",paper_ref.reference_id,replace(paper_ref,paper_config_snapshot_id="missing"))):
        repo._connection.execute(f"UPDATE {table} SET payload_json=? WHERE id=?",(json.dumps(backtest_dump(tampered),sort_keys=True),identifier)); repo._connection.commit()
        with pytest.raises(AuditReconstructionError):
            (AuditReconstructionService(repo).reconstruct_historical_signal_replay_reference(identifier) if table.startswith("historical_signal") else AuditReconstructionService(repo).reconstruct_historical_paper_replay_reference(identifier))


@pytest.mark.parametrize("field,value", [("signal_id","missing-signal"),("historical_analytical_evaluation_id","missing-analysis"),("historical_portfolio_gate_evaluation_id","missing-gate"),("historical_rotation_evaluation_id","missing-rotation"),("backtest_portfolio_state_id","missing-state"),("trade_plan_id","missing-plan"),("signal_config_snapshot_id","missing-config"),("signal_config_fingerprint","bad-fingerprint"),("signal_config_version","signal-v2")])
def test_signal_audit_dependency_tampers_fail_closed(tmp_path,field,value):
    repo, signal_ref, _paper_ref=audited_chain(tmp_path)
    tampered=replace(signal_ref,**{field:value})
    repo._connection.execute("UPDATE historical_signal_replay_references SET payload_json=? WHERE id=?",(json.dumps(backtest_dump(tampered),sort_keys=True),signal_ref.reference_id)); repo._connection.commit()
    with pytest.raises(AuditReconstructionError): AuditReconstructionService(repo).reconstruct_historical_signal_replay_reference(signal_ref.reference_id)


@pytest.mark.parametrize("field,value", [("paper_trade_id","missing-trade"),("paper_outcome_id","missing-outcome"),("paper_config_snapshot_id","missing-config"),("paper_config_fingerprint","bad-fingerprint"),("paper_config_version","paper-v2"),("fill_policy","LIMIT_ZONE_FILL"),("same_bar_policy","UNRESOLVED"),("gap_policy","LEVEL"),("cost_model_version","cost-v2"),("frozen_bar_ids",("future-bar",))])
def test_paper_audit_dependency_and_policy_tampers_fail_closed(tmp_path,field,value):
    repo, _signal_ref, paper_ref=audited_chain(tmp_path)
    tampered=replace(paper_ref,**{field:value})
    repo._connection.execute("UPDATE historical_paper_replay_references SET payload_json=? WHERE id=?",(json.dumps(backtest_dump(tampered),sort_keys=True),paper_ref.reference_id)); repo._connection.commit()
    with pytest.raises(AuditReconstructionError): AuditReconstructionService(repo).reconstruct_historical_paper_replay_reference(paper_ref.reference_id)
