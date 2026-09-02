"""Bounded Supabase inbox transport to the existing loopback HSI V1C intake.

This is a transport adapter, not an intelligence store or a generic Supabase
client. Its only remote resources are the approved inbox table and its atomic
claim RPC; its only HSI destination is the existing authenticated intake path.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from threading import Event
from time import sleep
from typing import Callable, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
from uuid import UUID

from pydantic import ValidationError

from app.api.schemas.intelligence import ExternalIntelligenceEventRequest
from app.intelligence.external_intelligence_live_connector import (
    DeliveryStatus,
    DeskDeliveryReceipt,
    ExternalIntelligenceLiveConnector,
    INGEST_TOKEN_ENVIRONMENT_KEY,
)


SUPABASE_URL_ENVIRONMENT_KEY = "HSI_EXTERNAL_INTELLIGENCE_SUPABASE_URL"
SUPABASE_SECRET_KEY_ENVIRONMENT_KEY = "HSI_EXTERNAL_INTELLIGENCE_SUPABASE_SECRET_KEY"
BRIDGE_ENABLED_ENVIRONMENT_KEY = "HSI_EXTERNAL_INTELLIGENCE_SUPABASE_BRIDGE_ENABLED"
APPROVED_SUPABASE_ORIGIN = "https://mfvxjkgdmrprfzylnhbe.supabase.co"
LOCAL_HSI_ORIGIN = "http://127.0.0.1:8000"
INBOX_TABLE = "external_intelligence_inbox"
CLAIM_RPC = "claim_external_intelligence_inbox"
DEFAULT_BATCH_SIZE = 10
MAX_BATCH_SIZE = 10
DEFAULT_CLAIM_TTL_SECONDS = 10 * 60
DEFAULT_POLL_INTERVAL_SECONDS = 60
DEFAULT_MAX_ATTEMPTS = 10


class SupabaseBridgeConfigurationError(ValueError):
    """Safe configuration failure with no credential material."""


class SupabaseBridgeNetworkError(RuntimeError):
    """Safe transport failure; no raw payload or secret is included."""


class InboxDeliveryState(StrEnum):
    PENDING = "PENDING"
    CLAIMED = "CLAIMED"
    DELIVERED = "DELIVERED"
    RETRY = "RETRY"
    DEAD_LETTER = "DEAD_LETTER"


@dataclass(frozen=True, slots=True)
class SupabaseBridgeSettings:
    enabled: bool = False
    batch_size: int = DEFAULT_BATCH_SIZE
    claim_ttl_seconds: int = DEFAULT_CLAIM_TTL_SECONDS
    poll_interval_seconds: int = DEFAULT_POLL_INTERVAL_SECONDS
    max_attempts: int = DEFAULT_MAX_ATTEMPTS

    def __post_init__(self) -> None:
        if not 1 <= self.batch_size <= MAX_BATCH_SIZE:
            raise SupabaseBridgeConfigurationError("Supabase inbox batch size must be between 1 and 10.")
        if self.claim_ttl_seconds < 60:
            raise SupabaseBridgeConfigurationError("Supabase claim TTL must be at least 60 seconds.")
        if self.poll_interval_seconds < 30:
            raise SupabaseBridgeConfigurationError("Supabase bridge poll interval must be at least 30 seconds.")
        if not 1 <= self.max_attempts <= DEFAULT_MAX_ATTEMPTS:
            raise SupabaseBridgeConfigurationError("Supabase bridge max attempts must be between 1 and 10.")

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> "SupabaseBridgeSettings":
        source = os.environ if environ is None else environ
        return cls(
            enabled=_environment_bool(source.get(BRIDGE_ENABLED_ENVIRONMENT_KEY, "false")),
            batch_size=_environment_int(source, "HSI_EXTERNAL_INTELLIGENCE_SUPABASE_BRIDGE_BATCH_SIZE", DEFAULT_BATCH_SIZE),
            claim_ttl_seconds=_environment_int(source, "HSI_EXTERNAL_INTELLIGENCE_SUPABASE_BRIDGE_CLAIM_TTL_SECONDS", DEFAULT_CLAIM_TTL_SECONDS),
            poll_interval_seconds=_environment_int(source, "HSI_EXTERNAL_INTELLIGENCE_SUPABASE_BRIDGE_POLL_INTERVAL_SECONDS", DEFAULT_POLL_INTERVAL_SECONDS),
            max_attempts=_environment_int(source, "HSI_EXTERNAL_INTELLIGENCE_SUPABASE_BRIDGE_MAX_ATTEMPTS", DEFAULT_MAX_ATTEMPTS),
        )


@dataclass(frozen=True, slots=True)
class InboxRow:
    id: str
    producer_event_id: str
    payload_fingerprint: str
    raw_payload: Mapping[str, object]
    delivery_status: InboxDeliveryState
    attempt_count: int


@dataclass(frozen=True, slots=True)
class BridgeCycleReceipt:
    claimed: int = 0
    delivered: int = 0
    accepted_new: int = 0
    accepted_existing: int = 0
    accepted_new_evidence: int = 0
    retry: int = 0
    dead_letter: int = 0
    malformed: int = 0
    hsi_unavailable: int = 0
    supabase_failure: int = 0


class SupabaseInboxGateway(Protocol):
    def claim_due(self, *, limit: int, claim_ttl_seconds: int) -> tuple[InboxRow, ...]: ...
    def update_row(self, row_id: str, values: Mapping[str, object]) -> None: ...


class HsiIntelligenceConnector(Protocol):
    def ingest_intelligence_event(self, event: Mapping[str, object]) -> DeskDeliveryReceipt: ...


class SupabaseInboxRestGateway:
    """Fixed REST/RPC implementation using one server-side key only in apikey."""

    def __init__(self, *, origin: str, secret_key: str, timeout_seconds: float = 15.0) -> None:
        _validate_approved_supabase_origin(origin)
        if not secret_key.strip():
            raise SupabaseBridgeConfigurationError("Supabase server secret is not configured.")
        if not 0 < timeout_seconds <= 30:
            raise SupabaseBridgeConfigurationError("Supabase bridge timeout must be between 0 and 30 seconds.")
        self._origin = origin.rstrip("/")
        self._secret_key = secret_key
        self._timeout_seconds = timeout_seconds

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> "SupabaseInboxRestGateway":
        source = os.environ if environ is None else environ
        origin = source.get(SUPABASE_URL_ENVIRONMENT_KEY)
        secret = source.get(SUPABASE_SECRET_KEY_ENVIRONMENT_KEY)
        if not origin:
            raise SupabaseBridgeConfigurationError("Supabase inbox URL is not configured.")
        if not secret:
            raise SupabaseBridgeConfigurationError("Supabase server secret is not configured.")
        return cls(origin=origin, secret_key=secret)

    def claim_due(self, *, limit: int, claim_ttl_seconds: int) -> tuple[InboxRow, ...]:
        if not 1 <= limit <= MAX_BATCH_SIZE:
            raise SupabaseBridgeConfigurationError("Supabase inbox claim limit must be between 1 and 10.")
        result = self._request_json(
            method="POST", path=f"/rest/v1/rpc/{CLAIM_RPC}",
            body={"p_limit": limit, "p_claim_ttl": f"{claim_ttl_seconds} seconds"},
        )
        if not isinstance(result, list):
            raise SupabaseBridgeNetworkError("Supabase claim RPC returned an invalid response.")
        try:
            return tuple(_inbox_row(value) for value in result)
        except (TypeError, ValueError) as error:
            raise SupabaseBridgeNetworkError("Supabase claim RPC returned an invalid inbox row.") from error

    def update_row(self, row_id: str, values: Mapping[str, object]) -> None:
        _validate_row_id(row_id)
        unsafe = set(values).difference(_UPDATABLE_INBOX_FIELDS)
        if unsafe:
            raise SupabaseBridgeConfigurationError("Supabase inbox update attempted a protected field.")
        self._request_json(
            method="PATCH", path="/rest/v1/" + INBOX_TABLE + "?" + urlencode({"id": f"eq.{row_id}"}), body=dict(values),
        )

    def _request_json(self, *, method: str, path: str, body: Mapping[str, object]) -> object:
        request = Request(self._origin + path, data=json.dumps(body, separators=(",", ":")).encode("utf-8"), method=method, headers={
            "apikey": self._secret_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Prefer": "return=representation",
        })
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:  # nosec B310: origin/path are constructor constants
                raw = response.read()
        except HTTPError as error:
            raise SupabaseBridgeNetworkError(f"Supabase inbox request failed with HTTP {error.code}.") from error
        except (OSError, URLError) as error:
            raise SupabaseBridgeNetworkError("Supabase inbox service is unavailable.") from error
        if not raw:
            return []
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise SupabaseBridgeNetworkError("Supabase inbox response was not valid JSON.") from error


class SupabaseExternalIntelligenceBridge:
    """One bounded claim-and-deliver cycle; it never projects News or reads Brain."""

    def __init__(self, *, inbox: SupabaseInboxGateway, connector: HsiIntelligenceConnector, settings: SupabaseBridgeSettings | None = None, clock: Callable[[], datetime] | None = None) -> None:
        self._inbox = inbox
        self._connector = connector
        self._settings = settings or SupabaseBridgeSettings()
        self._clock = clock or (lambda: datetime.now(UTC))

    def run_once(self) -> BridgeCycleReceipt:
        try:
            rows = self._inbox.claim_due(limit=self._settings.batch_size, claim_ttl_seconds=self._settings.claim_ttl_seconds)
        except SupabaseBridgeNetworkError:
            return BridgeCycleReceipt(supabase_failure=1)
        receipt = BridgeCycleReceipt(claimed=len(rows))
        for row in rows:
            receipt = _add(receipt, self._process_row(row))
        return receipt

    def run_forever(self, *, stop_event: Event | None = None, max_cycles: int | None = None, wait: Callable[[float], None] = sleep) -> int:
        if not self._settings.enabled:
            return 0
        stopper = stop_event or Event()
        cycles = 0
        while not stopper.is_set() and (max_cycles is None or cycles < max_cycles):
            self.run_once()
            cycles += 1
            if max_cycles is None or cycles < max_cycles:
                wait(self._settings.poll_interval_seconds)
        return cycles

    def _process_row(self, row: InboxRow) -> BridgeCycleReceipt:
        try:
            payload = ExternalIntelligenceEventRequest.model_validate(row.raw_payload).model_dump(mode="json")
        except ValidationError:
            return self._dead_letter(row, "HSI_SCHEMA_REJECTED", malformed=True)
        if payload["producer_event_id"] != row.producer_event_id:
            return self._dead_letter(row, "PRODUCER_EVENT_ID_MISMATCH", malformed=True)
        try:
            hsi = self._connector.ingest_intelligence_event(payload)
        except (ConnectionError, OSError):
            return self._retry(row, "HSI_NETWORK_UNAVAILABLE", unavailable=True)
        if hsi.delivery_status is DeliveryStatus.DELIVERED:
            return self._delivered(row, hsi)
        failure = hsi.failure_code or "HSI_DELIVERY_FAILED"
        if _is_permanent_hsi_failure(failure):
            return self._dead_letter(row, failure)
        return self._retry(row, failure, unavailable=failure in {"HSI_NETWORK_UNAVAILABLE", "HSI_HTTP_500", "HSI_HTTP_502", "HSI_HTTP_503", "HSI_HTTP_504"})

    def _delivered(self, row: InboxRow, hsi: DeskDeliveryReceipt) -> BridgeCycleReceipt:
        disposition = hsi.hsi_disposition
        try:
            self._inbox.update_row(row.id, {
                "delivery_status": InboxDeliveryState.DELIVERED.value,
                "delivered_at": _timestamp(self._clock()), "next_attempt_at": None,
                "hsi_disposition": disposition, "hsi_canonical_event_id": hsi.canonical_event_id,
                "hsi_evidence_version_id": hsi.evidence_version_id, "hsi_reevaluation_request_id": hsi.reevaluation_request_id,
                "hsi_received_at": hsi.received_at, "last_error": None,
            })
        except SupabaseBridgeNetworkError:
            # Keep CLAIMED unchanged: the RPC's stale-claim recovery will safely resend the exact payload.
            return BridgeCycleReceipt(supabase_failure=1)
        return BridgeCycleReceipt(
            delivered=1,
            accepted_new=int(disposition == "ACCEPTED_NEW"),
            accepted_existing=int(disposition == "ACCEPTED_EXISTING"),
            accepted_new_evidence=int(disposition == "ACCEPTED_NEW_EVIDENCE"),
        )

    def _retry(self, row: InboxRow, error_code: str, *, unavailable: bool = False) -> BridgeCycleReceipt:
        if row.attempt_count >= self._settings.max_attempts:
            return self._dead_letter(row, "MAX_ATTEMPTS_EXCEEDED")
        next_attempt = _aware_utc(self._clock()) + retry_delay(row.attempt_count)
        try:
            self._inbox.update_row(row.id, {
                "delivery_status": InboxDeliveryState.RETRY.value,
                "next_attempt_at": next_attempt.isoformat(), "last_error": error_code,
            })
        except SupabaseBridgeNetworkError:
            return BridgeCycleReceipt(supabase_failure=1)
        return BridgeCycleReceipt(retry=1, hsi_unavailable=int(unavailable))

    def _dead_letter(self, row: InboxRow, error_code: str, *, malformed: bool = False) -> BridgeCycleReceipt:
        try:
            self._inbox.update_row(row.id, {
                "delivery_status": InboxDeliveryState.DEAD_LETTER.value,
                "next_attempt_at": None, "last_error": error_code,
            })
        except SupabaseBridgeNetworkError:
            return BridgeCycleReceipt(supabase_failure=1)
        return BridgeCycleReceipt(dead_letter=1, malformed=int(malformed))


def build_supabase_external_intelligence_bridge(*, environ: Mapping[str, str] | None = None) -> SupabaseExternalIntelligenceBridge:
    source = os.environ if environ is None else environ
    token = source.get(INGEST_TOKEN_ENVIRONMENT_KEY)
    if not token:
        raise SupabaseBridgeConfigurationError("External-intelligence intake credential is not configured.")
    return SupabaseExternalIntelligenceBridge(
        inbox=SupabaseInboxRestGateway.from_environment(source),
        connector=ExternalIntelligenceLiveConnector(backend_url=LOCAL_HSI_ORIGIN, ingest_token=token),
        settings=SupabaseBridgeSettings.from_environment(source),
    )


_UPDATABLE_INBOX_FIELDS = frozenset({
    "delivery_status", "delivered_at", "next_attempt_at", "hsi_disposition", "hsi_canonical_event_id",
    "hsi_evidence_version_id", "hsi_reevaluation_request_id", "hsi_received_at", "last_error",
})


def retry_delay(attempt_count: int) -> timedelta:
    # attempt_count is incremented atomically by the claim RPC before this calculation.
    minutes = (1, 2, 4, 8, 15, 30, 60)[min(max(attempt_count - 1, 0), 6)]
    return timedelta(minutes=minutes)


def _is_permanent_hsi_failure(code: str) -> bool:
    return code == "HSI_SCHEMA_REJECTED" or code == "HSI_PAYLOAD_TOO_LARGE" or code in {
        "HSI_HTTP_400", "HSI_HTTP_401", "HSI_HTTP_403", "HSI_HTTP_404", "HSI_HTTP_409", "HSI_HTTP_411", "HSI_HTTP_413", "HSI_HTTP_422",
    }


def _add(left: BridgeCycleReceipt, right: BridgeCycleReceipt) -> BridgeCycleReceipt:
    return BridgeCycleReceipt(*(getattr(left, field) + getattr(right, field) for field in left.__dataclass_fields__))


def _inbox_row(value: object) -> InboxRow:
    if not isinstance(value, Mapping):
        raise ValueError("inbox row must be an object")
    row_id = value.get("id")
    producer_event_id = value.get("producer_event_id")
    payload_fingerprint = value.get("payload_fingerprint")
    payload = value.get("raw_payload")
    status = value.get("delivery_status")
    attempts = value.get("attempt_count")
    if not all(isinstance(item, str) for item in (row_id, producer_event_id, payload_fingerprint, status)) or not isinstance(payload, Mapping) or not isinstance(attempts, int):
        raise ValueError("inbox row fields are invalid")
    _validate_row_id(row_id)
    return InboxRow(row_id, producer_event_id, payload_fingerprint, dict(payload), InboxDeliveryState(status), attempts)


def _validate_approved_supabase_origin(origin: str) -> None:
    parsed = urlsplit(origin.rstrip("/"))
    if origin.rstrip("/") != APPROVED_SUPABASE_ORIGIN or parsed.scheme != "https" or parsed.path or parsed.query or parsed.fragment:
        raise SupabaseBridgeConfigurationError("Supabase inbox URL must be the approved HTTPS project origin.")


def _validate_row_id(value: str) -> None:
    try:
        UUID(value)
    except (ValueError, AttributeError) as error:
        raise SupabaseBridgeConfigurationError("Supabase inbox row ID must be a UUID.") from error


def _environment_bool(value: str) -> bool:
    if value.strip().lower() in {"1", "true", "yes", "on"}:
        return True
    if value.strip().lower() in {"0", "false", "no", "off", ""}:
        return False
    raise SupabaseBridgeConfigurationError("Supabase bridge enabled flag must be a boolean.")


def _environment_int(source: Mapping[str, str], name: str, default: int) -> int:
    try:
        return int(source.get(name, str(default)))
    except ValueError as error:
        raise SupabaseBridgeConfigurationError(f"{name} must be an integer.") from error


def _timestamp(value: datetime) -> str:
    return _aware_utc(value).isoformat()


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Supabase bridge clock must be timezone-aware.")
    return value.astimezone(UTC)


__all__ = (
    "APPROVED_SUPABASE_ORIGIN", "BRIDGE_ENABLED_ENVIRONMENT_KEY", "BridgeCycleReceipt", "CLAIM_RPC",
    "DEFAULT_BATCH_SIZE", "DEFAULT_CLAIM_TTL_SECONDS", "DEFAULT_MAX_ATTEMPTS", "DEFAULT_POLL_INTERVAL_SECONDS",
    "INBOX_TABLE", "InboxDeliveryState", "InboxRow", "LOCAL_HSI_ORIGIN", "MAX_BATCH_SIZE",
    "SUPABASE_SECRET_KEY_ENVIRONMENT_KEY", "SUPABASE_URL_ENVIRONMENT_KEY", "SupabaseBridgeConfigurationError",
    "SupabaseBridgeNetworkError", "SupabaseBridgeSettings", "SupabaseExternalIntelligenceBridge", "SupabaseInboxRestGateway",
    "build_supabase_external_intelligence_bridge", "retry_delay",
)
