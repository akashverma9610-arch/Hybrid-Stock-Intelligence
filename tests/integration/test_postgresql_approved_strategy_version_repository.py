"""Opt-in PostgreSQL contract test; requires a disposable dedicated test DB."""

import os

import pytest


POSTGRES_URL = os.environ.get("POSTGRES_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not POSTGRES_URL, reason="POSTGRES_TEST_DATABASE_URL is not configured")


def test_postgresql_approved_strategy_version_round_trip_duplicate_and_rollback():
    pytest.importorskip("psycopg")
    pytest.importorskip("alembic")
    from alembic import command
    from alembic.config import Config

    from app.backtest.promotion import ApprovedStrategyVersion
    from app.storage.database import DatabaseBackend, DatabaseConnectionFactory, DatabaseSettings
    from app.storage.postgresql_approved_strategy_version_repository import PostgreSQLApprovedStrategyVersionRepository
    from tests.unit.test_strategy_promotion_persistence import records

    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", POSTGRES_URL)
    command.upgrade(config, "head")
    repository = PostgreSQLApprovedStrategyVersionRepository(
        DatabaseConnectionFactory(DatabaseSettings(DatabaseBackend.POSTGRESQL, POSTGRES_URL))
    )
    _policy, _proposal, _eligibility, _review, version, _activation = records()
    value = ApprovedStrategyVersion(
        approved_id=f"{version.approved_id}-postgres",
        strategy_id=version.strategy_id,
        version="postgres-contract-v1",
        parent_approved_id=None,
        proposal_id=version.proposal_id,
        review_id=version.review_id,
        candidate_id=version.candidate_id,
        config_fingerprints=version.config_fingerprints,
        approved_at=version.approved_at,
        effective_from=version.effective_from,
        status=version.status,
        methodology_notes=version.methodology_notes,
        fingerprint=f"{version.fingerprint}-postgres",
    )
    repository.save_approved_strategy_version(value)
    assert repository.get_approved_strategy_version(value.approved_id) == value
    assert value in repository.list_approved_strategy_versions()
    with pytest.raises(ValueError, match="immutable"):
        repository.save_approved_strategy_version(value)


def test_postgresql_core_api_snapshots_round_trip_and_duplicate_rejection():
    pytest.importorskip("psycopg")
    pytest.importorskip("alembic")
    from alembic import command
    from alembic.config import Config
    from datetime import UTC, datetime
    from decimal import Decimal
    from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily
    from app.storage.database import DatabaseBackend, DatabaseConnectionFactory, DatabaseSettings
    from app.storage.postgresql_core_api_snapshot_repository import PostgreSQLCoreApiSnapshotRepository
    config=Config("alembic.ini"); config.set_main_option("sqlalchemy.url",POSTGRES_URL); command.upgrade(config,"head")
    repository=PostgreSQLCoreApiSnapshotRepository(DatabaseConnectionFactory(DatabaseSettings(DatabaseBackend.POSTGRESQL,POSTGRES_URL)))
    value=CoreApiSnapshot("postgres-core-snapshot",CoreApiSnapshotFamily.PERFORMANCE_REPORT,"v1","api-read-model-v1","postgres-core-fingerprint",datetime(2026,8,22,10,tzinfo=UTC),{"decimal":Decimal("1.25")})
    repository.save_snapshot(value)
    assert repository.get_snapshot(value.snapshot_id)==value
    with pytest.raises(ValueError,match="immutable"): repository.save_snapshot(value)
