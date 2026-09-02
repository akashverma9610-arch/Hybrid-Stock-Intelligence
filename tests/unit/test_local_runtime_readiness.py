from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.api.local_runtime_readiness import LocalRuntimeReadinessService
from app.api.main import create_app
from app.api.settings import APISettings
from app.runtime.local_runtime import LOCAL_DATABASE_URL, validate_local_operator_runtime
from app.storage.database import DatabaseBackend, DatabaseSettings


def _persistent_database(tmp_path):
    path = tmp_path / "runtime.db"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE financial_facts (id TEXT)")
        connection.execute("CREATE TABLE corporate_filings (id TEXT)")
        connection.execute("CREATE TABLE portfolio_snapshots (id TEXT)")
        connection.execute("CREATE TABLE bse_financial_acquisition_receipts (id TEXT)")
        connection.execute("INSERT INTO financial_facts VALUES ('f1')")
        connection.execute("INSERT INTO corporate_filings VALUES ('c1')")
    return DatabaseSettings(DatabaseBackend.SQLITE, f"sqlite:///{path.as_posix()}")


def test_local_runtime_rejects_memory_when_explicit_operator_mode_is_enabled(tmp_path) -> None:
    with pytest.raises(ValueError, match="HSI_LOCAL_RUNTIME_REQUIRES_PERSISTENT_DATABASE"):
        validate_local_operator_runtime(
            DatabaseSettings(),
            environ={"HSI_LOCAL_OPERATOR_RUNTIME": "true"},
            repository_root=tmp_path,
        )


def test_app_factory_applies_the_operator_guard_without_changing_default_tests(monkeypatch) -> None:
    monkeypatch.setenv("HSI_LOCAL_OPERATOR_RUNTIME", "true")
    with pytest.raises(ValueError, match="HSI_LOCAL_RUNTIME_REQUIRES_PERSISTENT_DATABASE"):
        create_app(api_settings=APISettings())


def test_local_runtime_accepts_only_the_fixed_persistent_project_database(tmp_path) -> None:
    database = tmp_path / "data" / "nse_stock_manager.db"
    database.parent.mkdir()
    database.touch()
    accepted = validate_local_operator_runtime(
        DatabaseSettings(DatabaseBackend.SQLITE, LOCAL_DATABASE_URL),
        environ={"HSI_LOCAL_OPERATOR_RUNTIME": "true"},
        repository_root=tmp_path,
    )
    assert accepted == database


def test_readiness_uses_short_lived_read_only_summary_and_no_work_execution(tmp_path) -> None:
    class Watch:
        def latest(self):
            return object()

    value = LocalRuntimeReadinessService(_persistent_database(tmp_path), market_wide_watch_service=Watch()).status()
    assert value.sqlite_integrity == "ok"
    assert value.foreign_key_violations == 0
    assert (value.financial_facts, value.corporate_filings, value.portfolio_snapshots, value.bse_receipts) == (1, 1, 0, None)
    assert value.bse_status == "NOT_CONFIGURED"
    assert value.market_wide_watch_status == "AVAILABLE"


def test_readiness_api_is_read_only_and_serializes_persistent_status(tmp_path) -> None:
    path = tmp_path / "runtime-api.db"
    sqlite3.connect(path).close()
    settings = APISettings(database=DatabaseSettings(DatabaseBackend.SQLITE, f"sqlite:///{path.as_posix()}"))
    with TestClient(create_app(api_settings=settings)) as client:
        response = client.get("/api/v1/runtime/local-readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["storage_mode"] == "PERSISTENT_SQLITE"
    assert body["sqlite_integrity"] == "ok"
    assert body["financial_facts"] == 0
