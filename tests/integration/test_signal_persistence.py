import pytest

from app.services.audit_reconstruction_service import AuditReconstructionService
from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository
from tests.unit.test_signal_lifecycle import ORCHESTRATOR, create, plan, request


def test_signal_plan_trigger_and_events_are_immutable_and_audit_reconstructable(tmp_path):
    repo = SQLiteStrategyGovernanceRepository(tmp_path / "signals.db")
    signal, created = create(); trade_plan = plan()
    repo.save_trade_plan(trade_plan); repo.save_signal(signal); repo.append_signal_event(created)
    assert repo.get_signal(signal.signal_id) == signal and repo.get_trade_plan(trade_plan.plan_id) == trade_plan
    assert repo.list_signal_events(signal.signal_id) == (created,)
    assert AuditReconstructionService(repo).reconstruct_signal(signal.signal_id) == (signal, trade_plan, (created,))
    with pytest.raises(ValueError): repo.save_signal(signal)
    with pytest.raises(ValueError): repo.save_trade_plan(trade_plan)
    repo.close()
