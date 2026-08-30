from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.backtest.promotion import ApprovedStrategyStatus
from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily, snapshot_from
from app.storage.database import DatabaseBackend, DatabaseSettings
from app.storage.repository_factory import create_core_api_snapshot_repository
from app.storage.postgresql_core_api_snapshot_repository import PostgreSQLCoreApiSnapshotRepository


T = datetime(2026, 8, 22, 10, tzinfo=UTC)


def snapshot(identifier: str, family: CoreApiSnapshotFamily, *, created_at=T):
    return CoreApiSnapshot(identifier, family, "v1", "api-read-model-v1", f"fingerprint-{identifier}", created_at, {
        "amount": Decimal("123.4500"), "timestamp": created_at,
        "status": ApprovedStrategyStatus.APPROVED, "provenance": ("evidence-1",),
    })


def test_sqlite_core_api_snapshot_families_round_trip_losslessly_and_deterministically(tmp_path):
    repository = create_core_api_snapshot_repository(DatabaseSettings(DatabaseBackend.SQLITE, f"sqlite:///{tmp_path / 'core.db'}"))
    families = tuple(CoreApiSnapshotFamily)
    values = tuple(snapshot(f"snapshot-{index}", family, created_at=T + timedelta(seconds=index)) for index, family in enumerate(families))
    for value in values:
        repository.save_snapshot(value)
        assert repository.get_snapshot(value.snapshot_id) == value
    assert repository.list_snapshots(CoreApiSnapshotFamily.SIGNAL) == (values[1],)
    assert repository.list_snapshots(CoreApiSnapshotFamily.SIGNAL, limit=1, offset=1) == ()
    assert values[0].payload["amount"] == Decimal("123.4500")
    assert values[0].payload["timestamp"].tzinfo is not None
    assert values[0].payload["status"] is ApprovedStrategyStatus.APPROVED


def test_core_snapshots_reject_duplicate_or_schema_incompatible_history(tmp_path):
    repository = create_core_api_snapshot_repository(DatabaseSettings(DatabaseBackend.SQLITE, f"sqlite:///{tmp_path / 'core.db'}"))
    value = snapshot("immutable", CoreApiSnapshotFamily.STOCK_ANALYSIS)
    repository.save_snapshot(value)
    with pytest.raises(ValueError, match="immutable"):
        repository.save_snapshot(value)
    with pytest.raises(ValueError, match="Unsupported"):
        snapshot_from({"snapshot_id": "bad", "family": "STOCK_ANALYSIS", "schema_version": "v2", "record_type": "x", "fingerprint": "x", "created_at": {"$type": "datetime", "value": T.isoformat()}, "payload": {}})
    with pytest.raises(ValueError, match="pagination"):
        repository.list_snapshots(CoreApiSnapshotFamily.STOCK_ANALYSIS, limit=101)


def test_backend_factory_selects_sqlite_without_import_time_connection(tmp_path):
    settings = DatabaseSettings(DatabaseBackend.SQLITE, f"sqlite:///{tmp_path / 'factory.db'}")
    repository = create_core_api_snapshot_repository(settings)
    assert repository.__class__.__name__ == "SQLiteCoreApiSnapshotRepository"


def test_backend_factory_selects_postgresql_adapter_without_connecting():
    repository = create_core_api_snapshot_repository(
        DatabaseSettings(DatabaseBackend.POSTGRESQL, "postgresql://user:secret@db.example/nse")
    )
    assert isinstance(repository, PostgreSQLCoreApiSnapshotRepository)
