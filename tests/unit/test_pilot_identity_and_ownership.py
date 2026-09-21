"""Real RSA-signed token verification and two-user API/storage isolation.

Only JWKS transport is replaced by a fixture; authentication is never mocked.
No provider, production DB, broker, portfolio writer or runtime is contacted.
"""
from dataclasses import replace
from datetime import UTC, datetime, timedelta
import json
import sqlite3
import time
import runpy
from pathlib import Path

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.api.pilot_boundary import OwnedSnapshotReader, PilotSecurity
from app.api.pilot_identity import ManagedTokenVerifier, PilotIdentitySettings, PilotPrincipal, PilotRole
from app.api.errors import APIRequestError
from app.api.settings import APISettings
from app.api.dependencies import get_news_query_service
from app.portfolio_import.models import PortfolioImportDraft, ImportStatus
from app.portfolio_import.service import PortfolioImportService
from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily as F
from app.storage.database import DatabaseBackend, DatabaseSettings
from app.storage.repository_factory import create_core_api_snapshot_repository
from app.storage.pilot_identity_store import PilotIdentityStore, PrivateResourceKind as K
from tests.unit.test_portfolio_api import snapshot
from tests.unit.test_signal_paper_api import _records


ISSUER = "https://pilot-test.auth0.com/"
AUDIENCE = "https://hsi.example/api"
CLIENT = "synthetic-spa-client"


def expected_pilot_boundary_source(accepted: bytes) -> bytes:
    """Exact authorized additions, not a new hash replacing frozen history."""
    for before, after in (
        ("    core_api_snapshot_repository=None,\n", "    core_api_snapshot_repository=None,\n    pilot_security=None,\n"),
        ("    application.add_middleware(\n",
         "    from app.api.pilot_boundary import PilotRequestContextMiddleware, install_pilot_boundary\n"
         "    install_pilot_boundary(application, pilot_security)\n    application.add_middleware(\n"),
        ('        allow_methods=["GET", "PUT", "POST", "DELETE"],\n',
         '        allow_methods=["GET", "PUT", "POST", "DELETE", "PATCH"],\n'),
        ('        allow_headers=["X-Request-ID", "Content-Type"],\n',
         '        allow_headers=["X-Request-ID", "Content-Type", "Authorization"],\n'),
        ('    application.add_middleware(RequestContextMiddleware)\n',
         '    application.add_middleware(PilotRequestContextMiddleware if hasattr(application.state, "pilot_security") else RequestContextMiddleware)\n'),
    ):
        assert accepted.count(before.encode()) == 1
        accepted = accepted.replace(before.encode(), after.encode(), 1)
    return accepted


@pytest.fixture
def setup(tmp_path):
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private.public_key()))
    public.update(kid="fixture-key", alg="RS256", use="sig")
    path = tmp_path / "identity.db"
    store = PilotIdentityStore.initialize(str(path))
    owner = store.bootstrap_owner(ISSUER, "auth0|owner", reason="explicit fixture bootstrap")
    a = store.invite_tester(owner, ISSUER, "auth0|a", reason="invited A")
    b = store.invite_tester(owner, ISSUER, "auth0|b", reason="invited B")
    settings = PilotIdentitySettings(ISSUER, AUDIENCE, (CLIENT,), str(path))
    verifier = ManagedTokenVerifier(settings)
    verifier._keys.jwk_set_cache.put({"keys": [public]})
    def no_network(*args, **kwargs):
        raise AssertionError("NETWORK_FORBIDDEN")
    verifier._keys.fetch_data = no_network
    security = PilotSecurity(settings, store, verifier)
    repository = create_core_api_snapshot_repository(DatabaseSettings(DatabaseBackend.SQLITE, f"sqlite:///{tmp_path / 'canonical.db'}"))
    base = snapshot()
    records = []
    for user, label in ((a, "A"), (b, "B")):
        payload = replace(base, portfolio_id=f"portfolio-{label}", snapshot_id=f"portfolio-snapshot-{label}")
        record = CoreApiSnapshot(f"record-{label}", F.PORTFOLIO, "v1", "fixture", f"fingerprint-{label}", base.as_of_timestamp, payload)
        repository.save_snapshot(record)
        store.bind(owner, K.CORE_SNAPSHOT, record.snapshot_id, record.fingerprint, user.user_id, reason="explicit fixture ownership")
        records.append(record)
    unbound = replace(records[0], snapshot_id="unbound-newest", fingerprint="unbound-fingerprint", created_at=base.as_of_timestamp + timedelta(days=1),
                      payload=replace(base, portfolio_id="PRIVATE_LEGACY"))
    repository.save_snapshot(unbound)
    imports = PortfolioImportService()
    now = datetime.now(UTC)
    imports._drafts["draft-B"] = PortfolioImportDraft("draft-B", ImportStatus.DRAFT, now, now + timedelta(minutes=5), 1, (), ())
    store.bind(owner, K.IMPORT_DRAFT, "draft-B", "fixture-draft", b.user_id, reason="explicit draft fixture")
    app = create_app(api_settings=APISettings(environment="test"), pilot_security=security,
                     core_api_snapshot_repository=repository, portfolio_import_service=imports)
    class SharedNews:
        def list_news(self, **kwargs):
            return ()
    app.dependency_overrides[get_news_query_service] = lambda: SharedNews()
    client = TestClient(app, raise_server_exceptions=False)
    def token(subject="auth0|a", **changes):
        now = int(time.time())
        claims = {"iss": ISSUER, "aud": AUDIENCE, "sub": subject, "azp": CLIENT,
                  "scope": "hsi:access", "iat": now, "exp": now + 300}
        claims.update(changes)
        return jwt.encode(claims, private, algorithm="RS256", headers={"kid": "fixture-key"})
    yield client, security, owner, a, b, token, repository, records, imports
    client.close()
    repository.close()


def headers(token):
    return {"Authorization": "Bearer " + token}


@pytest.mark.parametrize("path", ["/api/v1/portfolio", "/api/v1/paper-trades", "/api/v1/pilot/me", "/api/v1/news", "/api/v1/pilot/admin/audit"])
def test_anonymous_rejected(setup, path):
    client, *_ = setup
    response = client.get(path)
    assert response.status_code == 401
    assert response.headers["cache-control"] == "no-store"


def test_actual_portfolio_routes_are_owner_scoped_not_global_latest(setup):
    client, security, owner, a, b, token, repository, records, _ = setup
    before = repository.list_snapshots(F.PORTFOLIO)
    for subject, expected in (("auth0|a", "portfolio-A"), ("auth0|b", "portfolio-B")):
        for suffix in ("", "/summary"):
            response = client.get("/api/v1/portfolio" + suffix, headers=headers(token(subject)))
            assert response.status_code == 200, response.text
            assert response.json()["portfolio_id"] == expected
            assert "PRIVATE_LEGACY" not in response.text
        assert client.get("/api/v1/portfolio/holdings", headers=headers(token(subject))).status_code == 200
    # Admin is NOT an implicit owner of either tester's financial state.
    assert client.get("/api/v1/portfolio", headers=headers(token("auth0|owner"))).status_code == 503
    assert repository.list_snapshots(F.PORTFOLIO) == before


def test_client_ids_roles_and_owner_flags_never_change_context(setup):
    client, _, _, a, b, token, *_ = setup
    response = client.get("/api/v1/portfolio", params={"user_id": b.user_id, "owner_id": b.user_id, "role": "OWNER"},
                          headers={**headers(token(role="OWNER", user_id=b.user_id, admin=True)), "X-User-Id": b.user_id})
    assert response.status_code == 200
    assert response.json()["portfolio_id"] == "portfolio-A"
    me = client.get("/api/v1/pilot/me", headers=headers(token(role="OWNER"))).json()
    assert me == {"user_id": a.user_id, "role": "TESTER"}


def test_cross_user_mutation_denied_before_draft_service_and_own_cancel_works(setup):
    client, _, _, _, _, token, _, _, imports = setup
    response = client.post("/api/v1/portfolio/import/draft-B/cancel", headers=headers(token()), json={"owner_id": "B"})
    assert response.status_code == 404
    assert imports._drafts["draft-B"].status is ImportStatus.DRAFT
    response = client.post("/api/v1/portfolio/import/draft-B/cancel", headers=headers(token("auth0|b")))
    assert response.status_code == 200
    assert imports._drafts["draft-B"].status is ImportStatus.CANCELLED


@pytest.mark.parametrize("path,method", [
    ("/api/v1/connections/upstox", "PUT"), ("/api/v1/connections/upstox/test", "POST"),
    ("/api/v1/portfolio/import/draft-B/confirm", "POST"),
    ("/api/v1/portfolio/import/screenshots", "POST"), ("/api/v1/portfolio/analysis-jobs", "POST"),
    ("/api/v1/portfolio/live-valuation", "GET"), ("/api/v1/market-wide-watch", "GET"),
    ("/api/v1/stocks/NSE:EXAMPLE/decision-trust-envelope", "GET"),
    ("/api/v1/stocks/NSE:EXAMPLE/shared-brain", "GET"), ("/api/v1/p1-signals/lifecycle", "GET"),
    ("/api/v1/intelligence/events", "POST"), ("/docs", "GET"), ("/openapi.json", "GET"),
    ("/api/v1/unknown-future-route", "GET"),
])
def test_unscoped_or_unreviewed_surface_fails_closed_for_all_roles(setup, path, method):
    client, _, _, _, _, token, *_ = setup
    for subject in ("auth0|a", "auth0|owner"):
        assert client.request(method, path, headers=headers(token(subject))).status_code == 403


def test_admin_allowlist_invite_revoke_no_tester_escalation(setup):
    client, security, _, a, b, token, *_ = setup
    payload = {"subject": "auth0|new", "reason": "explicit invitation"}
    assert client.post("/api/v1/pilot/admin/users", headers=headers(token()), json=payload).status_code == 403
    assert client.get("/api/v1/pilot/admin/audit", headers=headers(token())).status_code == 403
    elevated = client.post("/api/v1/pilot/admin/users", headers=headers(token("auth0|owner")), json={**payload, "role": "OWNER"})
    assert elevated.status_code == 422
    assert client.post("/api/v1/pilot/admin/users", headers=headers(token("auth0|owner")), json=payload).status_code == 201
    assert security.store.principal(ISSUER, "auth0|new").role is PilotRole.TESTER
    assert client.patch(f"/api/v1/pilot/admin/users/{b.user_id}", headers=headers(token()), json={"enabled": False, "reason": "attack"}).status_code == 403
    assert client.patch(f"/api/v1/pilot/admin/users/{b.user_id}", headers=headers(token("auth0|owner")), json={"enabled": False, "reason": "revoke invitation"}).status_code == 200
    assert client.get("/api/v1/portfolio", headers=headers(token("auth0|b"))).status_code == 403
    assert client.get("/api/v1/pilot/admin/audit", headers=headers(token("auth0|owner"))).status_code == 200
    assert client.get("/api/v1/pilot/admin/status", headers=headers(token("auth0|owner"))).status_code == 200


def test_shared_research_access_does_not_duplicate_canonical_data(setup):
    client, _, _, _, _, token, repository, *_ = setup
    before = repository.list_snapshots(F.PORTFOLIO)
    a = client.get("/api/v1/news", headers=headers(token()))
    b = client.get("/api/v1/news", headers=headers(token("auth0|b")))
    assert a.status_code == b.status_code == 200
    assert a.json() == b.json() == {"items": []}
    assert repository.list_snapshots(F.PORTFOLIO) == before


@pytest.mark.parametrize("changes", [
    {"iss": "https://attacker.example/"}, {"aud": CLIENT}, {"azp": "other-client"},
    {"exp": 1}, {"iat": 9999999999}, {"nbf": 9999999999}, {"sub": "svc@clients"},
    {"gty": "client-credentials"}, {"scope": "other:scope"}, {"sub": ""},
    {"exp": 9999999999}, {"iat": "1"},
])
def test_signed_invalid_claims_rejected(setup, changes):
    client, _, _, _, _, token, *_ = setup
    assert client.get("/api/v1/pilot/me", headers=headers(token(**changes))).status_code == 401


def test_uninvited_subject_and_bad_signature_never_gain_access(setup):
    client, _, _, _, _, token, *_ = setup
    assert client.get("/api/v1/pilot/me", headers=headers(token("auth0|not-invited"))).status_code == 403
    parts = token().split(".")
    parts[1] = jwt.utils.base64url_encode(json.dumps({"sub": "auth0|owner"}).encode()).decode()
    assert client.get("/api/v1/pilot/me", headers=headers(".".join(parts))).status_code == 401
    forged = jwt.encode({"sub": "auth0|owner"}, "not-a-real-secret-just-fixture-value", algorithm="HS256")
    assert client.get("/api/v1/pilot/me", headers=headers(forged)).status_code == 401


def test_duplicate_headers_and_secret_redaction(setup, caplog):
    client, _, _, _, _, token, *_ = setup
    value = token()
    response = client.get("/api/v1/pilot/me", headers=[("Authorization", "Bearer " + value), ("Authorization", "Bearer " + value)])
    assert response.status_code == 401
    assert value not in response.text + caplog.text
    response = client.get("/api/v1/pilot/me", headers=headers(value))
    assert value not in response.text + caplog.text
    assert "auth0|" not in response.text


def test_fingerprint_mismatch_and_duplicate_reassignment_fail_closed(setup):
    _, security, owner, a, b, _, repository, records, _ = setup
    with pytest.raises(APIRequestError, match="not authorized"):
        security.store.bind(owner, K.CORE_SNAPSHOT, records[0].snapshot_id, records[0].fingerprint, b.user_id, reason="wrong owner")
    reader = OwnedSnapshotReader(repository, security, a)
    original = repository.get_snapshot
    repository.get_snapshot = lambda record_id: replace(original(record_id), fingerprint="tampered")
    with pytest.raises(APIRequestError) as error:
        reader.list_snapshots(F.PORTFOLIO)
    assert error.value.code == "PILOT_OWNERSHIP_PROVENANCE_MISMATCH"


def test_every_resource_kind_is_owner_bound_without_admin_bypass(setup):
    _, security, owner, a, b, *_ = setup
    for kind in K:
        security.store.bind(owner, kind, f"{kind}-A", "immutable-reference", a.user_id, reason="explicit test")
        security.store.require_owner(a, kind, f"{kind}-A")
        for other in (b, owner):
            with pytest.raises(APIRequestError):
                security.store.require_owner(other, kind, f"{kind}-A")
        with pytest.raises(APIRequestError):
            security.store.bind(a, kind, "spoofed", "fingerprint", b.user_id, reason="attack")


def test_sqlite_integrity_foreign_keys_reopen_and_immutable_audit(setup):
    _, security, owner, a, b, *_ = setup
    reopened = PilotIdentityStore(str(security.store.path))
    assert reopened.principal(ISSUER, "auth0|a") == a
    with sqlite3.connect(security.store.path) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("DELETE FROM pilot_auth_audit")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("UPDATE pilot_ownership SET owner_user_id=?", (b.user_id,))
    with pytest.raises(ValueError):
        reopened.bootstrap_owner(ISSUER, "second", reason="not allowed")
    with pytest.raises(FileExistsError):
        PilotIdentityStore.initialize(str(security.store.path))


def test_unconfigured_production_cannot_fall_back_to_global_portfolio(monkeypatch):
    monkeypatch.delenv("HSI_IDENTITY_ISSUER", raising=False)
    client = TestClient(create_app(api_settings=APISettings(environment="production")))
    assert client.get("/health").status_code == 200
    assert client.get("/api/v1/portfolio").status_code == 503
    assert client.get("/api/v1/portfolio").json()["error"]["code"] == "PILOT_IDENTITY_UNAVAILABLE"


def test_cors_allows_auth_header_but_not_unapproved_origin(setup):
    client, *_ = setup
    response = client.options("/api/v1/pilot/me", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "authorization"})
    assert response.status_code == 200
    denied_response = client.get("/api/v1/portfolio", headers={"Origin": "http://localhost:3000"})
    assert denied_response.headers["access-control-allow-origin"] == "http://localhost:3000"
    response = client.options("/api/v1/pilot/me", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
    assert response.status_code == 400


def test_paper_trade_detail_list_and_performance_are_isolated(setup):
    client, security, owner, a, b, token, repository, _, _ = setup
    _, completed, active, report = _records()
    for record_id, payload, family, user in (
        ("paper-A", completed, F.PAPER_TRADE, a),
        ("paper-B", active, F.PAPER_TRADE, b),
        ("performance-A", report, F.PERFORMANCE_REPORT, a),
    ):
        record = CoreApiSnapshot(record_id, family, "v1", "fixture", record_id, datetime.now(UTC), payload)
        repository.save_snapshot(record)
        security.store.bind(owner, K.CORE_SNAPSHOT, record_id, record_id, user.user_id, reason="explicit paper fixture")
    own = client.get("/api/v1/paper-trades", headers=headers(token()))
    assert own.status_code == 200 and own.json()["total"] == 1
    own_id = completed.trade.paper_trade_id
    other_id = active.trade.paper_trade_id
    assert client.get(f"/api/v1/paper-trades/{own_id}", headers=headers(token())).status_code == 200
    assert client.get(f"/api/v1/paper-trades/{other_id}", headers=headers(token())).status_code == 404
    assert client.get(f"/api/v1/paper-trades/{own_id}", headers=headers(token("auth0|b"))).status_code == 404
    assert client.get("/api/v1/paper-trades/performance", headers=headers(token())).status_code == 200
    assert client.get("/api/v1/paper-trades/performance", headers=headers(token("auth0|b"))).status_code == 503


def test_private_reader_paginates_after_isolation_and_has_no_write_method(setup):
    _, security, _, a, _, _, repository, records, _ = setup
    reader = OwnedSnapshotReader(repository, security, a)
    assert reader.list_snapshots(F.PORTFOLIO, limit=1) == (records[0],)
    assert reader.list_snapshots(F.PORTFOLIO, offset=1) == ()
    assert not hasattr(reader, "save_snapshot")
    assert reader.list_snapshots(F.PERFORMANCE_REPORT) == ()


def test_forged_principal_cannot_promote_or_bind(setup):
    _, security, _, a, b, *_ = setup
    forged = PilotPrincipal(a.user_id, PilotRole.OWNER)
    with pytest.raises(APIRequestError):
        security.store.invite_tester(forged, ISSUER, "auth0|evil", reason="attack")
    with pytest.raises(APIRequestError):
        security.store.bind(forged, K.PORTFOLIO, "stolen", "fp", b.user_id, reason="attack")


def test_jwks_failure_is_safe_and_refresh_is_bounded(setup):
    _, security, _, _, _, token, *_ = setup
    verifier = ManagedTokenVerifier(security.settings)
    calls = []
    def unavailable():
        calls.append(1)
        raise jwt.PyJWKClientConnectionError("sensitive-provider-details")
    verifier._keys.fetch_data = unavailable
    with pytest.raises(APIRequestError) as first:
        verifier.verify(token())
    assert first.value.status_code == 503
    with pytest.raises(APIRequestError) as second:
        verifier.verify(token())
    assert "sensitive-provider-details" not in str(first.value) + str(second.value)
    assert len(calls) == 1


def test_agent_mount_cannot_bypass_pilot_boundary(setup):
    from app.api.agent_tools import create_tool_app
    client, _, _, _, _, token, *_ = setup
    client.app.mount("/hsi/v1", create_tool_app(lambda: client.app.state))
    assert client.get("/hsi/v1/portfolio", headers=headers(token("auth0|owner"))).status_code == 403


@pytest.mark.parametrize("environment", ["pilot", "staging", "production", "unexpected-environment"])
def test_non_local_environments_fail_closed_even_if_disabled_flag_set(monkeypatch, environment):
    monkeypatch.setenv("HSI_PILOT_AUTH_ENABLED", "0")
    monkeypatch.delenv("HSI_IDENTITY_ISSUER", raising=False)
    client = TestClient(create_app(api_settings=APISettings(environment=environment)))
    assert client.get("/api/v1/portfolio").status_code == 503


@pytest.mark.parametrize("issuer", ["http://unsafe.example/", "https://user:secret@example.com/", "https://example.com/?x=1", "https://example.com/path/"])
def test_issuer_is_pinned_https_origin_only(issuer, tmp_path):
    with pytest.raises(ValueError):
        PilotIdentitySettings(issuer, AUDIENCE, (CLIENT,), str(tmp_path / "identity.db"))


def test_no_token_persisted_and_canonical_db_unchanged_by_authenticated_reads(setup):
    client, security, _, _, _, token, repository, records, _ = setup
    value = token()
    before = repository.list_snapshots(F.PORTFOLIO)
    for path in ("/api/v1/pilot/me", "/api/v1/portfolio", "/api/v1/news"):
        assert client.get(path, headers=headers(value)).status_code == 200
    assert value.encode() not in security.store.path.read_bytes()
    assert repository.list_snapshots(F.PORTFOLIO) == before


def test_offline_migration_is_explicit_idempotent_and_never_changes_canonical_db(setup):
    _, security, _, a, _, _, repository, records, _ = setup
    main = runpy.run_path(str(Path("scripts/dev/pilot-identity-admin.py")))["main"]
    canonical = security.store.path.parent / "canonical.db"
    before = canonical.read_bytes()
    args = ["--store", str(security.store.path), "--issuer", ISSUER, "--owner-subject", "auth0|owner",
            "bind-snapshot", "--canonical-db", str(canonical), "--snapshot-id", records[0].snapshot_id,
            "--expected-fingerprint", records[0].fingerprint, "--target-subject", "auth0|a", "--confirm-reviewed-ownership"]
    main(args)
    main(args)
    assert canonical.read_bytes() == before
    with pytest.raises(ValueError, match="REFERENCE_MISMATCH"):
        main(["incorrect-fingerprint" if x == records[0].fingerprint else x for x in args])
    assert canonical.read_bytes() == before


def test_bootstrap_refuses_existing_canonical_file(tmp_path):
    main = runpy.run_path(str(Path("scripts/dev/pilot-identity-admin.py")))["main"]
    path = tmp_path / "existing.db"
    path.write_bytes(b"must-not-overwrite")
    with pytest.raises(FileExistsError):
        main(["--store", str(path), "--issuer", ISSUER, "--owner-subject", "auth0|owner", "bootstrap-owner"])
    assert path.read_bytes() == b"must-not-overwrite"


def test_non_preflight_options_cannot_bypass_authorization(setup):
    client, *_ = setup
    assert client.options("/api/v1/portfolio").status_code == 401


def test_pilot_logs_do_not_echo_caller_paths_or_request_ids(setup, caplog):
    client, _, _, _, _, token, *_ = setup
    caplog.set_level("INFO", logger="app.api.pilot_boundary")
    marker = "sensitive-user-supplied-value"
    response = client.get("/" + marker, headers={**headers(token()), "X-Request-ID": marker})
    assert response.status_code == 403
    assert marker not in caplog.text
    assert response.headers["X-Request-ID"] != marker
    assert "PILOT_REJECTED_ROUTE" in caplog.text


def test_exact_source_successor_preserves_every_other_baseline_byte():
    import subprocess
    original = subprocess.check_output(["git", "show", "cc639c2d700b1f18eb0873c118d9b042c7d32d2b:app/api/main.py"]).replace(b"\r\n", b"\n")
    assert Path("app/api/main.py").read_bytes().replace(b"\r\n", b"\n") == expected_pilot_boundary_source(original)
