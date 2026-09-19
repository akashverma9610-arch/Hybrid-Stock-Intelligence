"""Isolated SQLite and HTTP proof; never production providers or credentials."""
import ast
from datetime import timedelta, timezone
from hashlib import sha256
from pathlib import Path
import sqlite3
import json

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
import pytest

from app.api.errors import APIRequestError, api_request_error_handler, request_validation_error_handler
from app.api.p1_signal_lifecycle_query import P1SignalLifecycleQueryService
from app.api.routes.p1_signal_lifecycle import router
from app.api.schemas.p1_signal_lifecycle import P1LifecycleQuery, P1LifecycleResponse
from app.intelligence.p1_signal_lifecycle import Outcome, Reason
from app.storage.database import DatabaseSettings
from app.storage.readonly_p1_signal_lifecycle import P1ReadUnavailable, ReadOnlyP1SignalLifecycleReader
from app.storage.sqlite_p1_signal_lifecycle import SQLiteP1SignalLifecycleRepository
from tests.unit.test_p1_signal_lifecycle_runtime import I, T, Ledger, fixture, governance


@pytest.fixture
def journal(tmp_path, governance):
    path = tmp_path / "p1.sqlite"
    repo = SQLiteP1SignalLifecycleRepository(path)
    first = fixture(governance)
    assert repo.submit(first, Ledger(first)).outcome is Outcome.ACCEPTED
    later = fixture(governance, T + timedelta(days=1), negative="BBW_NOT_COMPRESSED")
    assert repo.submit(later, Ledger(later)).outcome is Outcome.ACCEPTED
    repo.close()
    return path


def client_for(path):
    app = FastAPI()
    app.state.database_settings = DatabaseSettings(url=f"sqlite:///{path}")
    app.add_exception_handler(APIRequestError, api_request_error_handler)
    app.add_exception_handler(RequestValidationError, request_validation_error_handler)
    app.include_router(router, prefix="/api/v1")
    return TestClient(app)


def read(client, at=T, **extras):
    return client.get("/api/v1/p1-signals/lifecycle", params={
        "canonical_instrument_id": I, "as_of": at.isoformat(), **extras,
    })


def test_real_reader_route_and_stable_serialization_without_writes(journal):
    before = sha256(journal.read_bytes()).hexdigest()
    client = client_for(journal)
    first, second = read(client), read(client)
    assert first.status_code == 200
    assert first.json() == second.json()
    body = first.json()
    assert body["availability"] == "VERIFIED_HISTORY"
    assert body["outcome"] == "ACCEPTED"
    assert body["last_transition"]["next_state"] == "CURRENT"
    assert body["last_transition"]["known_at"] <= body["as_of"]
    assert len(body["transition_ids"]) == 1
    assert len(body["observation_references"]) == 1
    assert P1LifecycleResponse.model_validate_json(first.text).model_dump(mode="json") == body
    assert body["actionability"] == "WATCH_ONLY"
    assert body["execution_status"] == "NON_EXECUTABLE"
    assert body["expiry"] == "EXPIRY_NOT_GOVERNED_FOR_THIS_PATH"
    assert sha256(journal.read_bytes()).hexdigest() == before


def test_staleness_and_terminal_state_reuse_existing_replay(journal):
    client = client_for(journal)
    stale = read(client, T + timedelta(seconds=1)).json()
    assert stale["last_transition"]["next_state"] == "CURRENT"
    assert stale["outcome"] == "SOURCE_BLOCKED"
    assert stale["reason"] == "REEVALUATION_REQUIRED"
    terminal = read(client, T + timedelta(days=5)).json()
    assert terminal["outcome"] == "ACCEPTED"
    assert terminal["last_transition"]["next_state"] == "INVALIDATED"
    assert len(terminal["transition_ids"]) == 2


def test_timezone_equivalence_and_future_history_excluded(journal):
    client = client_for(journal)
    assert read(client, T.astimezone(timezone(timedelta(hours=5, minutes=30)))).json() == read(client).json()
    missing = read(client, T - timedelta(seconds=1)).json()
    assert missing["availability"] == "NO_HISTORY"
    assert missing["last_transition"] is None
    assert missing["outcome"] == "SOURCE_BLOCKED"
    with sqlite3.connect(journal) as db:
        db.execute("UPDATE core_api_snapshots SET payload_json='{}' WHERE created_at>?", (T.isoformat(),))
    assert read(client).json()["outcome"] == "ACCEPTED"
    corrupt = read(client, T + timedelta(days=1)).json()
    assert corrupt["availability"] == "CONFLICTED"
    assert corrupt["last_transition"] is None


def test_tampered_index_is_not_rebuilt_by_get(journal):
    with sqlite3.connect(journal) as db:
        db.execute("UPDATE p1_signal_lifecycle_heads SET fingerprint='tampered'")
    before = sha256(journal.read_bytes()).hexdigest()
    body = read(client_for(journal), T + timedelta(days=1)).json()
    assert body["availability"] == "CONFLICTED"
    assert body["reason"] == "CHAIN_CONFLICT"
    assert sha256(journal.read_bytes()).hexdigest() == before


def test_tampered_type_is_rejected_before_dynamic_import(journal, monkeypatch):
    with sqlite3.connect(journal) as db:
        row = db.execute("SELECT snapshot_id,payload_json FROM core_api_snapshots WHERE created_at=?", (T.isoformat(),)).fetchone()
        payload = json.loads(row[1])
        payload["payload"]["class"] = "app.storage.sqlite_p1_signal_lifecycle:SQLiteP1SignalLifecycleRepository"
        db.execute("UPDATE core_api_snapshots SET payload_json=? WHERE snapshot_id=?", (json.dumps(payload), row[0]))
    def forbidden(*args, **kwargs):
        pytest.fail("Must reject unexpected type before decoder")
    monkeypatch.setattr("app.storage.sqlite_p1_signal_lifecycle.snapshot_json_from", forbidden)
    body = read(client_for(journal)).json()
    assert body["availability"] == "CONFLICTED"
    assert body["last_transition"] is None


def test_empty_store_distinct_from_missing_schema(tmp_path):
    path = tmp_path / "empty.sqlite"
    with sqlite3.connect(path):
        pass
    before = sha256(path.read_bytes()).hexdigest()
    response = read(client_for(path))
    assert response.status_code == 503
    assert "P1_LIFECYCLE_SCHEMA_UNAVAILABLE" in response.text
    assert sha256(path.read_bytes()).hexdigest() == before
    repo = SQLiteP1SignalLifecycleRepository(path)
    repo.close()
    response = read(client_for(path))
    assert response.status_code == 200
    assert response.json()["availability"] == "NO_HISTORY"


@pytest.mark.parametrize("name", ("missing.sqlite", "secret-api-token-do-not-print.sqlite"))
def test_missing_file_never_created_or_path_leaked(tmp_path, name):
    path = tmp_path / "absent-parent" / name
    response = read(client_for(path))
    assert response.status_code == 503
    assert name not in response.text
    assert str(tmp_path) not in response.text
    assert not path.parent.exists()


def test_nonpersistent_configuration_fails_without_fallback():
    with pytest.raises(APIRequestError) as raised:
        P1SignalLifecycleQueryService(DatabaseSettings()).read(P1LifecycleQuery(canonical_instrument_id=I, as_of=T))
    assert raised.value.status_code == 503


def test_registered_core_route_and_safe_request_error(journal):
    from app.api.main import create_app
    from app.api.settings import APISettings
    # No lifespan/background startup needed: this service owns only an ro read.
    app = create_app(api_settings=APISettings(database=DatabaseSettings(url=f"sqlite:///{journal}")))
    client = TestClient(app)
    assert read(client).status_code == 200
    response = read(client, token="synthetic-secret-do-not-echo")
    assert response.status_code == 422
    assert "synthetic-secret" not in response.text
    assert response.headers["x-request-id"] == response.json()["error"]["request_id"]
    assert set(app.openapi()["paths"]["/api/v1/p1-signals/lifecycle"]) == {"get"}


@pytest.mark.parametrize("params", (
    {}, {"canonical_instrument_id": I}, {"as_of": T.isoformat()},
    {"canonical_instrument_id": "ALPHA", "as_of": T.isoformat()},
    {"canonical_instrument_id": I, "as_of": "2026-09-02T10:30:00"},
    {"canonical_instrument_id": I, "as_of": "now"},
    {"canonical_instrument_id": I, "as_of": T.isoformat(), "action": "BUY"},
))
def test_invalid_input_rejected_before_database_access(tmp_path, params):
    response = client_for(tmp_path / "absent").get("/api/v1/p1-signals/lifecycle", params=params)
    assert response.status_code == 422


@pytest.mark.parametrize("method", ("post", "put", "patch", "delete"))
def test_no_write_route(tmp_path, method):
    assert getattr(client_for(tmp_path / "absent"), method)("/api/v1/p1-signals/lifecycle").status_code == 405


@pytest.mark.parametrize("statement", (
    "CREATE TABLE forbidden (id)", "DELETE FROM core_api_snapshots", "PRAGMA query_only=OFF",
    "ATTACH DATABASE ':memory:' AS other", "DROP TABLE p1_signal_lifecycle_heads",
))
def test_read_connection_cannot_mutate_even_if_misused(journal, statement):
    reader = ReadOnlyP1SignalLifecycleReader(journal)
    try:
        with pytest.raises(sqlite3.DatabaseError):
            reader._connection.execute(statement)
        assert not hasattr(reader, "submit")
        assert not hasattr(reader, "save_snapshot")
        assert not hasattr(reader, "rebuild_indexes")
    finally:
        reader.close()


@pytest.mark.parametrize("limit", ("MAX_BATCHES", "MAX_PAYLOAD_BYTES", "MAX_SQL_STEPS"))
def test_bounded_read_fails_instead_of_partial_history(journal, monkeypatch, limit):
    monkeypatch.setattr(ReadOnlyP1SignalLifecycleReader, limit, 0)
    response = read(client_for(journal), T + timedelta(days=1))
    # Force enough SQL work to hit the VM interrupt when testing its step budget.
    if limit == "MAX_SQL_STEPS" and response.status_code == 200:
        reader = ReadOnlyP1SignalLifecycleReader(journal)
        try:
            with pytest.raises(sqlite3.OperationalError):
                reader._connection.execute("SELECT count(*) FROM sqlite_master a, sqlite_master b, sqlite_master c, sqlite_master d").fetchone()
        finally:
            reader.close()
    else:
        assert response.status_code == 503
        assert "P1_LIFECYCLE_READ_LIMIT_EXCEEDED" in response.text


def test_reader_closed_on_failure_and_success(journal, monkeypatch):
    closed = []
    original = ReadOnlyP1SignalLifecycleReader.close
    def record(self):
        closed.append(True)
        original(self)
    monkeypatch.setattr(ReadOnlyP1SignalLifecycleReader, "close", record)
    assert read(client_for(journal)).status_code == 200
    monkeypatch.setattr(ReadOnlyP1SignalLifecycleReader, "MAX_BATCHES", 0)
    assert read(client_for(journal)).status_code == 503
    assert len(closed) == 2


def test_response_whitelist_and_static_boundary(journal):
    body = read(client_for(journal)).json()
    forbidden = {"entry", "stop", "target", "price", "quantity", "allocation", "setup_key", "p1_json",
                 "references", "approvals", "selections", "credentials", "access_token"}
    def check(value):
        if isinstance(value, dict):
            assert not forbidden.intersection(value)
            for child in value.values():
                check(child)
        elif isinstance(value, list):
            for child in value:
                check(child)
    check(body)
    root = Path(__file__).resolve().parents[2]
    for name in ("app/api/p1_signal_lifecycle_query.py", "app/api/routes/p1_signal_lifecycle.py",
                 "app/storage/readonly_p1_signal_lifecycle.py"):
        tree = ast.parse((root / name).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not any((node.module or "").startswith(prefix) for prefix in
                               ("app.signals", "app.portfolio", "app.broker", "app.orders", "app.gates", "app.connections"))
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in {"now", "utcnow", "submit", "save_snapshot", "rebuild_indexes"}
