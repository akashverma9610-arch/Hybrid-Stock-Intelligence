"""Offline harness tests; real Auth0 login remains a separate human canary."""
from pathlib import Path
import json
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from scripts.dev import pilot_identity_canary as canary


@pytest.fixture
def harness(tmp_path, monkeypatch):
    for key in ("DATABASE_BACKEND", "DATABASE_URL", "APP_ENV", "HSI_LOCAL_OPERATOR_RUNTIME",
                "DHAN_LIVE_MARKET_ENABLED", "ENABLE_AUTOMATED_SELF_IMPROVEMENT_RESEARCH"):
        monkeypatch.setenv(key, "")
    canary.isolated_environment()
    assets = tmp_path / "assets"
    sdk = assets / "node_modules/@auth0/auth0-spa-js"
    (sdk / "dist").mkdir(parents=True)
    (sdk / "package.json").write_text('{"version":"2.27.0"}')
    (sdk / "dist/auth0-spa-js.production.js").write_text("/* offline fixture */")
    for name in ("index.html", "canary.js"):
        (assets / name).write_bytes((canary.ASSETS / name).read_bytes())
    monkeypatch.setattr(canary, "ASSETS", assets)
    directory = tmp_path / "isolated"
    directory.mkdir()
    arguments = dict(directory=directory, issuer="https://canary-test.auth0.com/",
                     audience="urn:hsi:test", client_id="test-spa", owner_subject="auth0|owner",
                     tester_a_subject="auth0|a", tester_b_subject="auth0|b")
    app = canary.create_canary(**arguments)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    jwk.update(kid="test-key", alg="RS256", use="sig")
    verifier = app.state.security.verifier
    verifier._keys.jwk_set_cache.put({"keys": [jwk]})
    def forbidden_network(*args, **kwargs):
        raise AssertionError("NO_NETWORK_IN_OFFLINE_TEST")
    verifier._keys.fetch_data = forbidden_network
    def headers(subject="a", **changes):
        now = int(time.time())
        claims = dict(iss=arguments["issuer"], aud=arguments["audience"], azp="test-spa",
                      sub="auth0|" + subject, scope="hsi:access", iat=now, exp=now + 300)
        claims.update(changes)
        return {"Authorization": "Bearer " + jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test-key"})}
    with TestClient(app, base_url=canary.ORIGIN) as client:
        yield client, app, headers, arguments


def test_canary_uses_real_unchanged_backend_boundary(harness):
    client, app, headers, _ = harness
    assert client.get("/health").json()["pilot_identity"] == "CONFIGURED"
    assert not app.state.backend.state.dhan_live_market_runtime._enabled
    assert client.get("/api/v1/pilot/me").status_code == 401
    for label in ("a", "b"):
        result = client.get("/api/v1/portfolio", headers=headers(label))
        assert result.status_code == 200
        assert result.json()["portfolio_id"] == "SYNTHETIC-" + label.upper()
        assert result.json()["cash_status"] == "UNKNOWN"
        other = "B" if label == "a" else "A"
        assert client.post(f"/api/v1/portfolio/import/SYNTHETIC-DRAFT-{other}/cancel",
                           headers=headers(label), json={}).status_code == 404
        assert client.get("/api/v1/pilot/admin/status", headers=headers(label)).status_code == 403
    assert client.get("/api/v1/pilot/admin/status", headers=headers("owner")).status_code == 200
    assert client.get("/api/v1/portfolio", headers=headers("owner")).status_code == 503


def test_canary_revocation_and_no_client_authority(harness):
    client, app, headers, _ = harness
    b = app.state.users["B"].user_id
    path = "/api/v1/pilot/admin/users/" + b
    body = {"enabled": False, "reason": "explicit test revocation"}
    existing_token = headers("b")
    assert client.get("/api/v1/pilot/me", headers=existing_token).status_code == 200
    assert client.patch(path, headers=headers("a"), json=body).status_code == 403
    assert client.patch(path, headers=headers("owner"), json=body).status_code == 200
    denied = client.get("/api/v1/pilot/me", headers=existing_token)
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "PILOT_INVITATION_REQUIRED"
    assert client.patch(path, headers=headers("owner"),
                        json={"enabled": True, "reason": "explicit test restoration"}).status_code == 200
    assert client.get("/api/v1/pilot/me", headers=existing_token).status_code == 200
    assert client.get("/api/v1/pilot/me", headers=headers("uninvited")).status_code == 403
    result = client.get("/api/v1/portfolio?owner_id=" + b + "&role=OWNER", headers=headers("a"))
    assert result.json()["portfolio_id"] == "SYNTHETIC-A"


@pytest.mark.parametrize("changes", [{"aud": "wrong"}, {"azp": "wrong"}, {"exp": 1}, {"exp": 9999999999}])
def test_canary_rejects_invalid_claims(harness, changes):
    client, _, headers, _ = harness
    assert client.get("/api/v1/pilot/me", headers=headers(**changes)).status_code == 401


def test_shell_does_not_expose_files_or_secrets_and_blocks_rebinding(harness):
    client, _, _, _ = harness
    config = client.get("/canary-config").json()
    assert set(config) == {"origin", "domain", "audience", "client_id", "users", "labels"}
    page = client.get("/callback?code=never-echo-this&state=never-echo-this")
    assert "never-echo-this" not in page.text
    assert page.headers["cache-control"] == "no-store"
    assert page.headers["referrer-policy"] == "no-referrer"
    assert "'unsafe-inline'" not in page.headers["content-security-policy"]
    assert client.get("/canary-config", headers={"Host": "attacker.example"}).status_code == 403
    assert client.get("/canary-config", headers={"Origin": "https://attacker.example"}).status_code == 403
    assert client.get("/authorization.sqlite").status_code == 401
    assert client.get("/openapi.json").status_code == 401


def test_canary_refuses_existing_data_or_duplicate_subject(harness):
    _, _, _, arguments = harness
    with pytest.raises(ValueError, match="FRESH_EMPTY"):
        canary.create_canary(**arguments)
    with pytest.raises(ValueError, match="THREE_DISTINCT"):
        canary.create_canary(**{**arguments, "tester_b_subject": "auth0|a"})


def test_static_token_and_runtime_boundaries():
    script = (canary.ASSETS / "canary.js").read_text()
    assert 'cacheLocation: "memory"' in script
    assert 'useRefreshTokens: false' in script
    assert 'cacheMode: "cache-only"' in script
    assert "handleRedirectCallback" in script
    assert "history.replaceState" in script
    assert 'document.getElementById("recheck").onclick' in script
    assert 'document.getElementById("recheck").disabled = false' in script
    assert "setTimeout" not in script  # No silent/blind retry loop.
    for forbidden in ("console.", "localStorage", "sessionStorage", "innerHTML", "__raw", "clientSecret"):
        assert forbidden not in script
    source = Path(canary.__file__).read_text()
    assert 'host="127.0.0.1"' in source
    assert "access_log=False" in source
    assert "proxy_headers=False" in source
    assert "nse_stock_manager.db" not in source
    assert "CREATE TABLE" not in source
    assert 'shell.mount("/", backend)' in source


@pytest.mark.parametrize("cause,expected", [
    (jwt.ExpiredSignatureError("secret-must-not-appear"), "TOKEN_EXPIRED"),
    (jwt.ImmatureSignatureError("secret-must-not-appear"), "TOKEN_NOT_YET_VALID"),
    (jwt.InvalidAudienceError("secret-must-not-appear"), "AUDIENCE_MISMATCH"),
    (ValueError("secret-must-not-appear"), "CLAIM_POLICY_REJECTED"),
    (RuntimeError("secret-must-not-appear"), "UNCLASSIFIED_VERIFICATION_FAILURE"),
])
def test_diagnostic_reports_only_fixed_labels(cause, expected):
    error = RuntimeError("never-display-wrapper")
    error.__context__ = cause
    assert canary.safe_failure_classification(error) == expected


def test_diagnostic_keeps_verifier_rejection_and_redacts(harness, capsys):
    client, _, headers, _ = harness
    credential = headers(exp=1)
    response = client.get("/api/v1/pilot/me", headers=credential)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "PILOT_TOKEN_INVALID"
    output = capsys.readouterr().out
    assert "classification=TOKEN_EXPIRED" in output
    assert credential["Authorization"][7:] not in output
