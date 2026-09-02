"""Least-privilege bearer authentication for future external-intelligence intake."""
from __future__ import annotations

import hmac
import os
from dataclasses import dataclass
from enum import StrEnum
from fastapi import Header

from app.api.errors import APIRequestError


class IntelligenceScope(StrEnum):
    INGEST = "intelligence:ingest"
    READ = "intelligence:read"


@dataclass(frozen=True, slots=True)
class AuthenticatedIntelligenceProducer:
    producer_id: str
    credential_id: str
    scopes: frozenset[IntelligenceScope]


def require_intelligence_scope(scope: IntelligenceScope):
    def dependency(authorization: str | None = Header(default=None)) -> AuthenticatedIntelligenceProducer:
        token = _bearer(authorization)
        configured = os.getenv("HSI_EXTERNAL_INTELLIGENCE_INGEST_TOKEN")
        if not configured:
            raise APIRequestError(status_code=503, code="INTELLIGENCE_AUTH_UNAVAILABLE", message="Intelligence intake authentication is not configured.")
        if token is None or not hmac.compare_digest(token, configured):
            raise APIRequestError(status_code=401, code="INTELLIGENCE_AUTH_FAILED", message="Intelligence authentication failed.")
        context = AuthenticatedIntelligenceProducer("HSI_EXTERNAL_INTELLIGENCE_DESK", "external-intelligence-ingest-v1", frozenset({IntelligenceScope.INGEST}))
        if scope not in context.scopes:
            raise APIRequestError(status_code=403, code="INTELLIGENCE_SCOPE_DENIED", message="Intelligence credential lacks the required scope.")
        return context
    return dependency


def _bearer(value: str | None) -> str | None:
    if not value or not value.startswith("Bearer "):
        return None
    token = value[7:]
    return token if token and " " not in token else None
