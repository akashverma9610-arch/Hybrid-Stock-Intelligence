"""Explicit loopback-only Auth0 canary using the unchanged HSI API boundary.

Only synthetic empty portfolios and authorization metadata are created in a
fresh .tmp directory. No production database is opened. Human credentials and
tokens are never CLI arguments, files, logs, or canary responses.
"""
from __future__ import annotations

import argparse
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import json
import logging
import os
from pathlib import Path
import re
import sys
import tempfile
from threading import Timer
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
ASSETS = Path(__file__).with_suffix("")
ORIGIN = "http://127.0.0.1:8766"
sys.path.insert(0, str(ROOT))


def safe_failure_classification(error: Exception) -> str:
    """Only fixed labels; never serialize an exception, token or claim value.

    The verifier intentionally hides its original exception from HTTP clients.
    Its exception context is useful to the private operator without weakening
    validation or repeating provider requests. Unknown cases stay unknown.
    """
    import jwt
    cause = error.__context__
    for error_type, label in (
        (jwt.ExpiredSignatureError, "TOKEN_EXPIRED"),
        (jwt.ImmatureSignatureError, "TOKEN_NOT_YET_VALID"),
        (jwt.InvalidAudienceError, "AUDIENCE_MISMATCH"),
        (jwt.InvalidIssuerError, "ISSUER_MISMATCH"),
        (jwt.InvalidSignatureError, "SIGNATURE_INVALID"),
        (jwt.MissingRequiredClaimError, "REQUIRED_CLAIM_MISSING"),
        (jwt.PyJWKClientConnectionError, "JWKS_PROVIDER_UNAVAILABLE"),
        (jwt.InvalidTokenError, "TOKEN_FORMAT_OR_CLAIMS_INVALID"),
        (ValueError, "CLAIM_POLICY_REJECTED"),
    ):
        if isinstance(cause, error_type):
            return label
    return "UNCLASSIFIED_VERIFICATION_FAILURE"


def isolated_environment():
    """Process-local controls only; never edit user/machine configuration."""
    os.environ.update(DATABASE_BACKEND="sqlite", DATABASE_URL="sqlite:///:memory:",
                      APP_ENV="pilot", HSI_LOCAL_OPERATOR_RUNTIME="false",
                      DHAN_LIVE_MARKET_ENABLED="false",
                      ENABLE_AUTOMATED_SELF_IMPROVEMENT_RESEARCH="false")


def create_canary(*, directory: Path, issuer: str, audience: str, client_id: str,
                  owner_subject: str, tester_a_subject: str, tester_b_subject: str):
    # Fail before importing the application's module-level factory if an
    # operator tries to reuse a production/local runtime environment.
    if (os.environ.get("DATABASE_URL") != "sqlite:///:memory:"
            or os.environ.get("APP_ENV") != "pilot"
            or os.environ.get("HSI_LOCAL_OPERATOR_RUNTIME") != "false"
            or os.environ.get("DHAN_LIVE_MARKET_ENABLED") != "false"):
        raise ValueError("CANARY_ISOLATED_ENVIRONMENT_REQUIRED")
    from fastapi import FastAPI, Request
    from fastapi.responses import FileResponse, JSONResponse
    from app.api.main import create_app
    from app.api.errors import APIRequestError
    from app.api.pilot_boundary import PilotSecurity
    from app.api.pilot_identity import ManagedTokenVerifier, PilotIdentitySettings
    from app.api.settings import APISettings
    from app.feature_settings import FeatureSettings
    from app.portfolio.models import (
        CashPosition, CashState, PortfolioDataStatus, PortfolioExposureSummary,
        PortfolioRiskSummary, PortfolioSnapshot, PortfolioState,
    )
    from app.portfolio_import.models import ImportStatus, PortfolioImportDraft
    from app.portfolio_import.service import PortfolioImportService
    from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily
    from app.storage.database import DatabaseSettings
    from app.storage.pilot_identity_store import PilotIdentityStore, PrivateResourceKind
    from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository

    subjects = (owner_subject, tester_a_subject, tester_b_subject)
    if len(set(subjects)) != 3 or any(not re.fullmatch(r"auth0\|[A-Za-z0-9_-]{1,200}", s) for s in subjects):
        raise ValueError("CANARY_THREE_DISTINCT_DATABASE_SUBJECTS_REQUIRED")
    # New empty directory required; no accepted database path or migration flag.
    directory = directory.resolve()
    if not directory.is_dir() or any(directory.iterdir()):
        raise ValueError("CANARY_FRESH_EMPTY_DIRECTORY_REQUIRED")
    settings = PilotIdentitySettings(issuer, audience, (client_id,), str(directory / "authorization.sqlite"))
    sdk_root = ASSETS / "node_modules/@auth0/auth0-spa-js"
    if json.loads((sdk_root / "package.json").read_text())["version"] != "2.27.0":
        raise ValueError("CANARY_SDK_VERSION_MISMATCH")
    sdk = sdk_root / "dist/auth0-spa-js.production.js"
    if not sdk.is_file():
        raise ValueError("CANARY_SDK_REQUIRED")
    store = PilotIdentityStore.initialize(settings.store_path)
    owner = store.bootstrap_owner(issuer, owner_subject, reason="EXPLICIT_PRIVATE_CANARY_OWNER")
    users = {"OWNER": owner}
    for label, subject in (("A", tester_a_subject), ("B", tester_b_subject)):
        users[label] = store.invite_tester(owner, issuer, subject, reason="EXPLICIT_PRIVATE_CANARY_TESTER")
    repository = SQLiteCoreApiSnapshotRepository(directory / "synthetic.sqlite")
    imports = PortfolioImportService()
    as_of = datetime(2026, 1, 1, tzinfo=UTC)  # Clearly synthetic, not backfilled market evidence.
    for label in ("A", "B"):
        payload = PortfolioSnapshot(
            f"SYNTHETIC-SNAPSHOT-{label}", f"SYNTHETIC-{label}", as_of, as_of, (),
            CashPosition(None, "INR", Decimal(0), as_of, CashState.UNKNOWN), (), None,
            Decimal(0), None, Decimal(0), PortfolioExposureSummary({}, None, {}, 0, None),
            PortfolioRiskSummary(None, Decimal(0), PortfolioDataStatus.INSUFFICIENT_DATA, {}),
            PortfolioState.ALL_CASH, PortfolioDataStatus.INSUFFICIENT_DATA, "SYNTHETIC-CANARY", None,
        )
        record = CoreApiSnapshot(f"SYNTHETIC-RECORD-{label}", CoreApiSnapshotFamily.PORTFOLIO,
                                 "v1", "SYNTHETIC_CANARY", f"synthetic-canary-{label}", as_of, payload)
        repository.save_snapshot(record)
        store.bind(owner, PrivateResourceKind.CORE_SNAPSHOT, record.snapshot_id, record.fingerprint,
                   users[label].user_id, reason="SYNTHETIC_EMPTY_PORTFOLIO_ONLY")
        draft_id = f"SYNTHETIC-DRAFT-{label}"
        now = datetime.now(UTC)
        imports._drafts[draft_id] = PortfolioImportDraft(
            draft_id, ImportStatus.DRAFT, now, now + timedelta(hours=2), 0, (), ())
        store.bind(owner, PrivateResourceKind.IMPORT_DRAFT, draft_id, f"synthetic-draft-{label}",
                   users[label].user_id, reason="SYNTHETIC_DRAFT_IDOR_ONLY")
    class CanaryVerifier(ManagedTokenVerifier):
        def verify(self, token):
            try:
                return super().verify(token)
            except APIRequestError as error:
                print("CANARY_AUTH_REJECTED classification=" + safe_failure_classification(error), flush=True)
                raise

    security = PilotSecurity(settings, store, CanaryVerifier(settings))
    backend = create_app(
        api_settings=APISettings(environment="pilot", database=DatabaseSettings(), cors_origins=(ORIGIN,)),
        feature_settings=FeatureSettings(), pilot_security=security,
        core_api_snapshot_repository=repository, portfolio_import_service=imports,
    )

    @asynccontextmanager
    async def lifespan(application):
        try:
            async with backend.router.lifespan_context(backend):
                yield
        finally:
            repository.close()

    shell = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    shell.state.backend = backend
    shell.state.users = users
    shell.state.security = security
    shell.state.repository = repository

    @shell.middleware("http")
    async def local_boundary(request: Request, call_next):
        # Do not trust forwarded headers. Host validation prevents DNS rebinding;
        # Origin validation protects the unauthenticated canary shell itself.
        if (request.headers.get("host") != "127.0.0.1:8766"
                or request.headers.get("origin") not in (None, ORIGIN)
                or request.headers.get("sec-fetch-site") == "cross-site" and request.method != "GET"):
            return JSONResponse({"error": "CANARY_LOCAL_ORIGIN_REQUIRED"}, status_code=403)
        try:
            response = await call_next(request)
        except Exception:
            response = JSONResponse({"error": "CANARY_REQUEST_FAILED"}, status_code=500)
        response.headers.update({
            "Cache-Control": "no-store", "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY",
            "Content-Security-Policy": "default-src 'none'; script-src 'self'; connect-src 'self' "
                + issuer.rstrip("/") + "; frame-src " + issuer.rstrip("/")
                + "; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
        })
        return response

    @shell.get("/")
    @shell.get("/callback")
    def page():
        return FileResponse(ASSETS / "index.html", media_type="text/html")

    @shell.get("/auth0-sdk.js")
    def sdk_file():
        return FileResponse(sdk, media_type="application/javascript")

    @shell.get("/canary.js")
    def script():
        return FileResponse(ASSETS / "canary.js", media_type="application/javascript")

    @shell.get("/canary-config")
    def config():
        return {"origin": ORIGIN, "domain": urlsplit(issuer).hostname, "audience": audience,
                "client_id": client_id, "users": {label: p.user_id for label, p in users.items()},
                "labels": {p.user_id: label for label, p in users.items()}}

    shell.mount("/", backend)
    return shell


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("issuer", "audience", "client-id", "owner-subject", "tester-a-subject", "tester-b-subject"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    isolated_environment()
    # No request/access/error logs: OAuth callback query strings may contain codes.
    logging.disable(logging.CRITICAL)
    temporary_root = ROOT / ".tmp"
    temporary_root.mkdir(exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="pilot-identity-canary-", dir=temporary_root))
    application = create_canary(directory=directory, **vars(args))
    import uvicorn
    print("PILOT_IDENTITY_CANARY_READY " + ORIGIN, flush=True)
    print("REAL_AUTH0_IDENTITIES_SYNTHETIC_DATA_ONLY; NO_PRODUCTION_DB; DHAN_DISABLED", flush=True)
    server = uvicorn.Server(uvicorn.Config(application, host="127.0.0.1", port=8766, access_log=False,
                                          log_config=None, proxy_headers=False, server_header=False))
    timer = Timer(7200, lambda: setattr(server, "should_exit", True))
    timer.daemon = True
    timer.start()
    try:
        server.run()
    finally:
        timer.cancel()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("PILOT_IDENTITY_CANARY_START_FAILED", file=sys.stderr)
        raise SystemExit(1) from None
