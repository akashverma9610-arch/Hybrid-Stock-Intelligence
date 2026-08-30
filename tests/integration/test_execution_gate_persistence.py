from dataclasses import replace
from datetime import timedelta

import pytest

from app.gates.engine import ActionContext, ExecutionGateEngine
from app.services.audit_reconstruction_service import AuditReconstructionService
from tests.integration.test_decision_scorecard_persistence import persisted
from tests.unit.test_execution_gates import ASOF, CALENDAR, CONFIG, inputs


def gate_evaluation(card):
    asof = card.as_of_timestamp
    base = inputs()
    data = replace(base, scorecard_id=card.id, snapshot_as_of_timestamp=asof,
        surveillance=replace(base.surveillance, effective_at=asof),
        earnings_scheduled_at=asof + timedelta(days=13), earnings_schedule_verified_at=asof)
    return ExecutionGateEngine(CONFIG, CALENDAR).evaluate(
        instrument_id=card.instrument_id, strategy_version=card.strategy_version, registry_version=card.registry_version,
        scoring_configuration_version=card.configuration_version, action_context=ActionContext.FRESH_ENTRY,
        as_of_timestamp=asof, evaluated_at=asof, inputs=data,
    )


def test_execution_gate_evaluation_is_immutable_persisted_and_audit_reconstructable(tmp_path):
    repo, card = persisted(tmp_path); repo.save_decision_scorecard(card)
    evaluation = gate_evaluation(card)
    repo.save_execution_gate_evaluation(evaluation)
    assert repo.get_execution_gate_evaluation(evaluation.id) == evaluation
    assert repo._connection.execute("SELECT COUNT(*) FROM execution_gate_decisions WHERE evaluation_id = ?", (evaluation.id,)).fetchone()[0] == 6
    assert AuditReconstructionService(repo).reconstruct_execution_gate_evaluation(evaluation.id) == evaluation
    with pytest.raises(ValueError):
        repo.save_execution_gate_evaluation(evaluation)
    repo.close()
