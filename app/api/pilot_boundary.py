"""Deny-by-default pilot facade over existing HSI query contracts.

Local single-user Core V1 stays intact. Pilot/staging/production installs this
boundary unconditionally; missing identity config never enables legacy access.
"""
from __future__ import annotations

import os
import re
import logging
from time import perf_counter
from uuid import uuid4
from dataclasses import dataclass
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware

from app.api import dependencies as deps
from app.api.errors import APIRequestError
from app.api.pilot_identity import ManagedTokenVerifier, PilotIdentitySettings, PilotRole, denied
from app.api.repository_query_services import (
    RepositoryBenchmarkQueryService, RepositoryCapitalRotationQueryService,
    RepositoryPaperTradeQueryService, RepositoryPerformanceQueryService,
    RepositoryPortfolioQueryService, RepositorySignalQueryService,
)
from app.storage.core_api_snapshot_repository import CoreApiSnapshotFamily
from app.storage.pilot_identity_store import PilotIdentityStore, PrivateResourceKind


@dataclass(frozen=True)
class PilotSecurity:
    settings: PilotIdentitySettings
    store: PilotIdentityStore
    verifier: ManagedTokenVerifier

    @classmethod
    def from_environment(cls):
        settings = PilotIdentitySettings(
            issuer=os.environ.get("HSI_IDENTITY_ISSUER", ""),
            audience=os.environ.get("HSI_IDENTITY_AUDIENCE", ""),
            client_ids=tuple(x.strip() for x in os.environ.get("HSI_IDENTITY_CLIENT_IDS", "").split(",") if x.strip()),
            store_path=os.environ.get("HSI_IDENTITY_STORE", ""),
        )
        return cls(settings, PilotIdentityStore(settings.store_path), ManagedTokenVerifier(settings))


class PilotRequestContextMiddleware(BaseHTTPMiddleware):
    """Log server IDs and route templates, never caller-controlled paths/IDs."""

    async def dispatch(self, request: Request, call_next):
        request_id = uuid4().hex
        request.state.request_id = request_id
        started = perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        route = getattr(request.scope.get("route"), "path", "PILOT_REJECTED_ROUTE")
        method = request.method if request.method in {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"} else "OTHER"
        logging.getLogger(__name__).info(
            "pilot_request_completed request_id=%s method=%s route=%s status=%s duration_ms=%.3f",
            request_id, method, route, response.status_code, (perf_counter() - started) * 1000,
        )
        return response


class OwnedSnapshotReader:
    """Only exact, explicitly bound snapshots, never global latest fallback.

    Unknown families are private by default. The only shared family needed by
    these private query adapters is the common market regime. This object has
    no write method and never changes canonical payloads or PIT cutoffs.
    """

    def __init__(self, repository, security: PilotSecurity, principal):
        self._source, self._security, self._principal = repository, security, principal

    def list_snapshots(self, family, *, limit=100, offset=0):
        if self._source is None:
            raise denied("PILOT_CANONICAL_STORAGE_UNAVAILABLE", 503)
        if family is CoreApiSnapshotFamily.MARKET_REGIME:
            return self._source.list_snapshots(family, limit=limit, offset=offset)
        records = []
        for record_id, fingerprint in self._security.store.owned(self._principal, PrivateResourceKind.CORE_SNAPSHOT):
            item = self._source.get_snapshot(record_id)
            if item is None or item.family != family:
                continue
            if item.fingerprint != fingerprint:
                raise denied("PILOT_OWNERSHIP_PROVENANCE_MISMATCH", 503)
            records.append(item)
        records.sort(key=lambda x: (x.created_at, x.snapshot_id))
        return tuple(records[offset:offset + limit])


# Exact GET surfaces audited as shared data: no portfolio/holding context.
# Do NOT allow a whole prefix: future routes must be explicitly reviewed.
_SHARED = tuple(re.compile(x) for x in (
    r"/api/v1/news(?:/[^/]+)?", r"/api/v1/filings(?:/[^/]+)?",
    r"/api/v1/fundamentals/[^/]+(?:/series)?",
    r"/api/v1/market/(?:regime|breadth|extremes|crisis)", r"/api/v1/sectors(?:/[^/]+)?",
))
_PRIVATE = tuple(re.compile(x) for x in (
    r"/api/v1/portfolio(?:/holdings|/summary|/sell-side)?",
    r"/api/v1/paper-trades(?:/[^/]+)?", r"/api/v1/performance(?:/[^/]+)?",
    r"/api/v1/benchmarks(?:/[^/]+)?", r"/api/v1/signals(?:/[^/]+)?",
    r"/api/v1/capital-rotation",
))
_ADMIN_READ = frozenset({"/api/v1/governance/strategy-versions", "/api/v1/governance/active-strategy"})
_CANCEL = re.compile(r"/api/v1/portfolio/import/([^/]+)/cancel")


def _error(error: APIRequestError):
    headers = {"Cache-Control": "no-store"}
    if error.status_code == 401:
        headers["WWW-Authenticate"] = "Bearer"
    return JSONResponse(status_code=error.status_code,
                        content={"error": {"code": error.code, "message": error.message}}, headers=headers)


def install_pilot_boundary(application, security: PilotSecurity | None = None):
    environment = application.state.api_settings.environment.lower()
    enabled = environment not in {"development", "local", "test"} or os.environ.get("HSI_PILOT_AUTH_ENABLED") == "1"
    if security is None and not enabled:
        return
    if security is None:
        try:
            security = PilotSecurity.from_environment()
        except Exception:
            security = None  # All non-health requests fail 503, not legacy fallback.
    if security is not None:
        canonical = application.state.database_settings.url
        if canonical.startswith("sqlite:///") and Path(canonical.removeprefix("sqlite:///")).resolve() == security.store.path:
            raise ValueError("PILOT_IDENTITY_STORE_MUST_BE_SEPARATE")
    application.state.pilot_security = security

    def owned(factory):
        def dependency(request: Request):
            reader = OwnedSnapshotReader(request.app.state.core_api_snapshot_repository,
                                         security, request.state.pilot_principal)
            return factory(reader)
        return dependency

    for dependency, factory in (
        (deps.get_portfolio_query_service, RepositoryPortfolioQueryService),
        (deps.get_paper_trade_query_service, RepositoryPaperTradeQueryService),
        (deps.get_performance_query_service, RepositoryPerformanceQueryService),
        (deps.get_benchmark_query_service, RepositoryBenchmarkQueryService),
        (deps.get_capital_rotation_query_service, RepositoryCapitalRotationQueryService),
        (deps.get_signal_query_service, RepositorySignalQueryService),
    ):
        application.dependency_overrides[dependency] = owned(factory)

    @application.middleware("http")
    async def pilot_access(request: Request, call_next):
        path, method = request.url.path, request.method
        if method == "GET" and path == "/health":
            return JSONResponse({"status": "ok", "pilot_identity": "CONFIGURED" if security else "UNAVAILABLE"},
                                headers={"Cache-Control": "no-store"})
        try:
            if security is None:
                raise denied("PILOT_IDENTITY_UNAVAILABLE", 503)
            values = request.headers.getlist("authorization")
            if len(values) != 1 or not values[0].startswith("Bearer ") or " " in values[0][7:]:
                raise denied("PILOT_AUTHENTICATION_REQUIRED", 401)
            issuer, subject = await run_in_threadpool(security.verifier.verify, values[0][7:])
            principal = await run_in_threadpool(security.store.principal, issuer, subject)
            request.state.pilot_principal = principal
            is_admin = principal.role in (PilotRole.OWNER, PilotRole.ADMIN)
            allowed = method == "GET" and (
                path == "/api/v1/pilot/me"
                or any(p.fullmatch(path) for p in _SHARED + _PRIVATE)
                or is_admin and path in _ADMIN_READ
            )
            if path in {"/api/v1/pilot/admin/users", "/api/v1/pilot/admin/audit", "/api/v1/pilot/admin/status"}:
                allowed = is_admin and ((method == "POST" and path.endswith("/users"))
                                        or method == "GET" and not path.endswith("/users"))
            if re.fullmatch(r"/api/v1/pilot/admin/users/[^/]+", path):
                allowed = is_admin and method == "PATCH"
            match = _CANCEL.fullmatch(path)
            if method == "POST" and match:
                await run_in_threadpool(security.store.require_owner, principal, PrivateResourceKind.IMPORT_DRAFT, match[1])
                allowed = True
            if not allowed:
                raise denied("PILOT_ROUTE_NOT_AUTHORIZED")
            response = await call_next(request)
            response.headers["Cache-Control"] = "no-store"
            response.headers["Vary"] = "Authorization, Origin"
            return response
        except APIRequestError as error:
            return _error(error)
        except Exception:
            # Do not serialize exception args, claims, auth headers or private payloads.
            return _error(denied("PILOT_REQUEST_UNAVAILABLE", 503))

    router = APIRouter(prefix="/api/v1/pilot", tags=["pilot-identity"])

    @router.get("/me")
    def me(request: Request):
        principal = request.state.pilot_principal
        return {"user_id": principal.user_id, "role": principal.role.value}

    @router.post("/admin/users", status_code=201)
    def invite(request: Request, payload: TesterInvitation):
        # The ADMIN supplies a provider subject to authorize, not the caller's
        # identity or role. Issuer and TESTER role are fixed by server config.
        principal = security.store.invite_tester(request.state.pilot_principal, security.settings.issuer,
                                                 payload.subject, reason=payload.reason)
        return {"user_id": principal.user_id, "role": principal.role.value}

    @router.patch("/admin/users/{user_id}")
    def revoke(request: Request, user_id: str, payload: TesterAccess):
        security.store.set_tester_enabled(request.state.pilot_principal, user_id,
                                         enabled=payload.enabled, reason=payload.reason)
        return {"user_id": user_id, "enabled": payload.enabled}

    @router.get("/admin/audit")
    def audit(request: Request):
        return {"events": security.store.audit(request.state.pilot_principal)}

    @router.get("/admin/status")
    def status():
        return {"identity_provider": "AUTH0", "identity_mode": "INVITE_ONLY",
                "private_access": "EXPLICIT_OWNERSHIP_ONLY", "broker_order_authority": False,
                "public_deployment_verified": False}

    application.include_router(router)


class TesterInvitation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject: str = Field(min_length=1, max_length=255)
    reason: str = Field(min_length=1, max_length=200)


class TesterAccess(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: StrictBool
    reason: str = Field(min_length=1, max_length=200)
