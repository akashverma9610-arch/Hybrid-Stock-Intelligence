from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.errors import APIRequestError, api_request_error_handler
from app.api.routes.intelligence import router


def _client(monkeypatch, token: str | None = "test-secret"):
    if token is None: monkeypatch.delenv("HSI_EXTERNAL_INTELLIGENCE_INGEST_TOKEN", raising=False)
    else: monkeypatch.setenv("HSI_EXTERNAL_INTELLIGENCE_INGEST_TOKEN", token)
    app = FastAPI(); app.add_exception_handler(APIRequestError, api_request_error_handler); app.include_router(router, prefix="/api/v1")
    return TestClient(app)


def test_intelligence_ingest_bearer_is_scoped_and_secret_is_redacted(monkeypatch):
    client = _client(monkeypatch)
    valid = client.get("/api/v1/intelligence/auth-check", headers={"Authorization": "Bearer test-secret"})
    assert valid.status_code == 200 and valid.json()["scopes"] == ["intelligence:ingest"]
    assert "test-secret" not in valid.text
    assert client.get("/api/v1/intelligence/auth-check").status_code == 401
    assert client.get("/api/v1/intelligence/auth-check", headers={"Authorization": "Basic test-secret"}).status_code == 401
    assert client.get("/api/v1/intelligence/auth-check", headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_intelligence_auth_fails_closed_when_unconfigured(monkeypatch):
    assert _client(monkeypatch, None).get("/api/v1/intelligence/auth-check", headers={"Authorization": "Bearer anything"}).status_code == 503


def test_intelligence_token_rotation_and_scope_firewall(monkeypatch):
    client = _client(monkeypatch, "first")
    assert client.get("/api/v1/intelligence/auth-check", headers={"Authorization": "Bearer first"}).status_code == 200
    monkeypatch.setenv("HSI_EXTERNAL_INTELLIGENCE_INGEST_TOKEN", "rotated")
    assert client.get("/api/v1/intelligence/auth-check", headers={"Authorization": "Bearer first"}).status_code == 401
    result = client.get("/api/v1/intelligence/auth-check", headers={"Authorization": "Bearer rotated"}).json()
    assert result["scopes"] == ["intelligence:ingest"]
    assert not {"admin", "trade", "broker", "portfolio:write", "cash:write"} & set(result["scopes"])
