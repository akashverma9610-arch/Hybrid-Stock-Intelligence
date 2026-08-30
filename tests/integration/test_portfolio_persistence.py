import pytest

from app.services.audit_reconstruction_service import AuditReconstructionService
from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository
from tests.unit.test_portfolio_engine import PORTFOLIO, T0, build, buy100, tx
from app.portfolio.models import TransactionType


def test_portfolio_ledger_actions_and_snapshot_are_immutable_and_reconstructable(tmp_path):
    repo = SQLiteStrategyGovernanceRepository(tmp_path / "portfolio.db")
    repo.save_portfolio(PORTFOLIO)
    transaction = buy100(); repo.append_portfolio_transaction(transaction)
    snapshot = build((transaction,)); repo.save_portfolio_snapshot(snapshot)
    assert repo.get_portfolio(PORTFOLIO.portfolio_id) == PORTFOLIO
    assert repo.list_portfolio_transactions_as_of(PORTFOLIO.portfolio_id, snapshot.as_of_timestamp) == (transaction,)
    assert repo.get_portfolio_snapshot(snapshot.snapshot_id) == snapshot
    assert AuditReconstructionService(repo).reconstruct_portfolio_snapshot(snapshot.snapshot_id) == snapshot
    with pytest.raises(ValueError): repo.append_portfolio_transaction(transaction)
    with pytest.raises(ValueError): repo.save_portfolio_snapshot(snapshot)
    repo.close()
