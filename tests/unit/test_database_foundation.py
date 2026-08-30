import pytest

from app.api.main import create_app
from app.api.settings import APISettings
from app.backtest.promotion import ApprovedStrategyStatus
from app.storage.database import DatabaseBackend, DatabaseConnectionFactory, DatabaseReadinessProbe, DatabaseSettings
from app.storage.postgresql_approved_strategy_version_repository import PostgreSQLApprovedStrategyVersionRepository
from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository
from tests.unit.test_strategy_promotion_persistence import records


def test_database_settings_default_to_lazy_sqlite_and_parse_postgresql_without_connecting():
    local = DatabaseSettings.from_environment({})
    production = DatabaseSettings.from_environment({"DATABASE_BACKEND": "postgresql", "DATABASE_URL": "postgresql://user:secret@db.example/nse"})
    assert (local.backend, local.url) == (DatabaseBackend.SQLITE, "sqlite:///:memory:")
    assert production.backend is DatabaseBackend.POSTGRESQL
    assert "secret" in production.url
    assert APISettings.from_environment({}).database == local
    with pytest.raises(ValueError, match="required"):
        DatabaseSettings.from_environment({"DATABASE_BACKEND": "postgresql"})
    with pytest.raises(ValueError, match="wildcard"):
        APISettings.from_environment({"CORS_ORIGINS": "*"})


def test_sqlite_connection_factory_transactions_readiness_and_import_are_side_effect_free(tmp_path):
    database = DatabaseSettings(DatabaseBackend.SQLITE, f"sqlite:///{tmp_path / 'factory.db'}")
    factory = DatabaseConnectionFactory(database)
    assert create_app(api_settings=APISettings(database=database)).state.database_settings == database
    with factory.transaction() as connection:
        connection.execute("CREATE TABLE transactions (id TEXT PRIMARY KEY)")
        connection.execute("INSERT INTO transactions (id) VALUES (?)", ("committed",))
    with pytest.raises(RuntimeError):
        with factory.transaction() as connection:
            connection.execute("INSERT INTO transactions (id) VALUES (?)", ("rolled-back",))
            raise RuntimeError("force rollback")
    with factory.transaction() as connection:
        ids = tuple(row[0] for row in connection.execute("SELECT id FROM transactions ORDER BY id"))
    assert ids == ("committed",)
    assert DatabaseReadinessProbe(factory).check().ready is True


def test_postgresql_factory_and_repository_are_lazy_and_readiness_fails_safely_without_connection(monkeypatch):
    settings = DatabaseSettings(DatabaseBackend.POSTGRESQL, "postgresql://not-a-real-host/nse")
    factory = DatabaseConnectionFactory(settings)
    repository = PostgreSQLApprovedStrategyVersionRepository(factory)
    monkeypatch.setattr(factory, "connect", lambda: (_ for _ in ()).throw(RuntimeError("unavailable")))
    assert repository is not None and DatabaseReadinessProbe(factory).check().ready is False


def test_representative_sqlite_approved_version_contract_remains_immutable_and_typed(tmp_path):
    repository = SQLiteStrategyGovernanceRepository(tmp_path / "governance.db")
    policy, proposal, eligibility, review, version, _activation = records()
    repository.save_strategy_promotion_policy(policy)
    repository.save_strategy_promotion_proposal(proposal)
    repository.save_promotion_eligibility_result(eligibility)
    repository.save_strategy_promotion_review(review)
    repository.save_approved_strategy_version(version)
    assert repository.get_approved_strategy_version(version.approved_id) == version
    assert repository.list_approved_strategy_versions() == (version,)
    assert version.status is ApprovedStrategyStatus.APPROVED and version.approved_at.tzinfo is not None
    with pytest.raises(ValueError, match="immutable"):
        repository.save_approved_strategy_version(version)
