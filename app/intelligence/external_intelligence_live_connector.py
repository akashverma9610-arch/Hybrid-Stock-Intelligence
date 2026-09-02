"""Narrow live-delivery bridge for the External Intelligence Desk.

The connector has one capability: submit a V1C event to HSI's fixed intake
endpoint.  It has no read, storage, portfolio, execution, or general HTTP
surface.  The Desk retains events that cannot be truthfully delivered.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from pydantic import ValidationError

from app.api.schemas.intelligence import (
    ExternalIntelligenceEventRequest,
    ExternalIntelligenceReceiptResponse,
)


INGEST_TOKEN_ENVIRONMENT_KEY = "HSI_EXTERNAL_INTELLIGENCE_INGEST_TOKEN"
HSI_ORIGIN_ENVIRONMENT_KEY = "HSI_EXTERNAL_INTELLIGENCE_HSI_ORIGIN"
INTELLIGENCE_EVENT_PATH = "/api/v1/intelligence/events"
_ACCEPTED_DISPOSITIONS = frozenset({"ACCEPTED_NEW", "ACCEPTED_EXISTING", "ACCEPTED_NEW_EVIDENCE"})


class DeliveryStatus(StrEnum):
    DELIVERED = "DELIVERED"
    PENDING_DELIVERY = "PENDING_DELIVERY"


class LiveConnectorConfigurationError(ValueError):
    """Safe configuration error; it never contains secret material."""


@dataclass(frozen=True, slots=True)
class IntelligenceIngestHttpResponse:
    status_code: int
    body: Mapping[str, object]


class IntelligenceEventTransport(Protocol):
    """A deliberately single-purpose transport, not a general client."""

    def post_intelligence_event(
        self, *, endpoint: str, authorization: str, payload: bytes,
    ) -> IntelligenceIngestHttpResponse: ...


@dataclass(frozen=True, slots=True)
class DeskDeliveryReceipt:
    delivery_status: DeliveryStatus
    producer_event_id: str
    hsi_disposition: str | None
    canonical_event_id: str | None
    evidence_version_id: str | None
    reevaluation_request_id: str | None
    received_at: str | None
    failure_code: str | None


class UrllibIntelligenceEventTransport:
    """Bounded POST implementation for the one validated intake endpoint."""

    def __init__(self, *, timeout_seconds: float = 15.0) -> None:
        if not 0 < timeout_seconds <= 30:
            raise LiveConnectorConfigurationError("Live intelligence delivery timeout must be between 0 and 30 seconds.")
        self._timeout_seconds = timeout_seconds

    def post_intelligence_event(
        self, *, endpoint: str, authorization: str, payload: bytes,
    ) -> IntelligenceIngestHttpResponse:
        request = Request(endpoint, data=payload, method="POST", headers={
            "Authorization": authorization,
            "Content-Type": "application/json",
            "Accept": "application/json",
        })
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:  # nosec B310: endpoint is constructor-validated
                return IntelligenceIngestHttpResponse(int(response.status), _json_object(response.read()))
        except HTTPError as error:
            return IntelligenceIngestHttpResponse(int(error.code), _json_object(error.read()))
        except (OSError, URLError) as error:
            raise ConnectionError("HSI intelligence intake is unavailable.") from error


class ExternalIntelligenceLiveConnector:
    """One-action Desk capability: ``ingest_intelligence_event(event)``."""

    def __init__(
        self, *, backend_url: str, ingest_token: str,
        transport: IntelligenceEventTransport | None = None,
    ) -> None:
        self._endpoint = _intelligence_event_endpoint(backend_url)
        if not ingest_token or not ingest_token.strip():
            raise LiveConnectorConfigurationError("External-intelligence intake credential is not configured.")
        self._authorization = "Bearer " + ingest_token
        self._transport = transport or UrllibIntelligenceEventTransport()

    @classmethod
    def from_environment(
        cls, *, backend_url: str | None = None, transport: IntelligenceEventTransport | None = None,
    ) -> "ExternalIntelligenceLiveConnector":
        token = os.getenv(INGEST_TOKEN_ENVIRONMENT_KEY)
        if not token:
            raise LiveConnectorConfigurationError("External-intelligence intake credential is not configured.")
        origin = backend_url or os.getenv(HSI_ORIGIN_ENVIRONMENT_KEY)
        if not origin:
            raise LiveConnectorConfigurationError("External-intelligence HTTPS origin is not configured.")
        endpoint = _intelligence_event_endpoint(origin, require_public_https=True)
        return cls(backend_url=endpoint.removesuffix(INTELLIGENCE_EVENT_PATH), ingest_token=token, transport=transport)

    def ingest_intelligence_event(self, event: Mapping[str, object]) -> DeskDeliveryReceipt:
        """Validate and deliver only an approved V1C payload; retain failures pending."""
        producer_event_id = _producer_event_id(event)
        try:
            validated = ExternalIntelligenceEventRequest.model_validate(event)
        except ValidationError:
            return _pending(producer_event_id, "HSI_SCHEMA_REJECTED")
        payload = json.dumps(validated.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode("utf-8")
        if len(payload) > 256 * 1024:
            return _pending(validated.producer_event_id, "HSI_PAYLOAD_TOO_LARGE")
        try:
            response = self._transport.post_intelligence_event(
                endpoint=self._endpoint, authorization=self._authorization, payload=payload,
            )
        except (ConnectionError, OSError):
            return _pending(validated.producer_event_id, "HSI_NETWORK_UNAVAILABLE")
        return _map_response(validated.producer_event_id, response)


def _intelligence_event_endpoint(backend_url: str, *, require_public_https: bool = False) -> str:
    value = backend_url.rstrip("/")
    parsed = urlsplit(value)
    if parsed.scheme not in {"https", "http"} or not parsed.netloc:
        raise LiveConnectorConfigurationError("HSI backend URL must be an absolute HTTP(S) origin.")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise LiveConnectorConfigurationError("HSI backend URL must be an origin, not an arbitrary route.")
    if require_public_https and parsed.scheme != "https":
        raise LiveConnectorConfigurationError("External Desk delivery requires a public HTTPS origin.")
    if parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise LiveConnectorConfigurationError("Live HSI intelligence delivery requires HTTPS outside loopback.")
    return value + INTELLIGENCE_EVENT_PATH


def _map_response(producer_event_id: str, response: IntelligenceIngestHttpResponse) -> DeskDeliveryReceipt:
    try:
        receipt = ExternalIntelligenceReceiptResponse.model_validate(response.body)
    except ValidationError:
        return _pending(producer_event_id, _failure_code(response.status_code, response.body))
    if not 200 <= response.status_code < 300 or receipt.disposition not in _ACCEPTED_DISPOSITIONS:
        return _pending(producer_event_id, _failure_code(response.status_code, response.body))
    return DeskDeliveryReceipt(
        DeliveryStatus.DELIVERED, producer_event_id, receipt.disposition,
        receipt.canonical_event_id, receipt.evidence_version_id,
        receipt.reevaluation_request_id, receipt.received_at.isoformat(), None,
    )


def _failure_code(status_code: int, body: Mapping[str, object]) -> str:
    error = body.get("error")
    if isinstance(error, Mapping) and isinstance(error.get("code"), str):
        return error["code"]
    return f"HSI_HTTP_{status_code}"


def _pending(producer_event_id: str, failure_code: str) -> DeskDeliveryReceipt:
    return DeskDeliveryReceipt(
        DeliveryStatus.PENDING_DELIVERY, producer_event_id,
        None, None, None, None, None, failure_code,
    )


def _producer_event_id(event: Mapping[str, object]) -> str:
    value = event.get("producer_event_id")
    return value if isinstance(value, str) else ""


def _json_object(value: bytes) -> Mapping[str, object]:
    try:
        decoded = json.loads(value.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return decoded if isinstance(decoded, dict) else {}


__all__ = (
    "DeliveryStatus", "DeskDeliveryReceipt", "ExternalIntelligenceLiveConnector",
    "HSI_ORIGIN_ENVIRONMENT_KEY", "INGEST_TOKEN_ENVIRONMENT_KEY", "INTELLIGENCE_EVENT_PATH", "IntelligenceEventTransport",
    "IntelligenceIngestHttpResponse", "LiveConnectorConfigurationError",
    "UrllibIntelligenceEventTransport",
)
