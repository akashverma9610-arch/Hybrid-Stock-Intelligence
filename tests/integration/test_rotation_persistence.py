from dataclasses import replace

import pytest

from app.services.audit_reconstruction_service import AuditReconstructionService
from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository
from tests.unit.test_capital_rotation import evaluate, context
from tests.unit.test_portfolio_engine import PORTFOLIO, build, buy100


def test_rotation_evaluation_and_matrix_are_immutable_and_audit_reconstructable(tmp_path):
    repo = SQLiteStrategyGovernanceRepository(tmp_path / "rotation.db")
    repo.save_portfolio(PORTFOLIO)
    transaction = buy100(); repo.append_portfolio_transaction(transaction)
    snapshot = build((transaction,)); repo.save_portfolio_snapshot(snapshot)
    evaluation = evaluate(replace(context(), portfolio_snapshot_id=snapshot.snapshot_id))
    repo.save_portfolio_rotation_evaluation(evaluation)
    assert repo.get_portfolio_rotation_evaluation(evaluation.evaluation_id) == evaluation
    assert repo._connection.execute("SELECT COUNT(*) FROM rotation_comparisons WHERE evaluation_id = ?", (evaluation.evaluation_id,)).fetchone()[0] == 1
    assert AuditReconstructionService(repo).reconstruct_portfolio_rotation_evaluation(evaluation.evaluation_id) == evaluation
    with pytest.raises(ValueError): repo.save_portfolio_rotation_evaluation(evaluation)
    repo.close()
