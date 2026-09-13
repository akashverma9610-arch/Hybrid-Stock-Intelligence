"""Bounded official NSE source capture, isolated from execution and scheduling.

The existing immutable snapshot store and UTC collector clock own persistence
and time. This module adds only surveillance-specific records and fixed routes.
"""
from __future__ import annotations

from base64 import b64decode, b64encode
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from hashlib import sha256
from http.client import HTTPException
import socket
import ssl
import re
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from app.filings.earnings_schedule_prospective_receipt_collector import CollectorClock, SystemUtcClock
from app.filings.earnings_schedule_source import utc
from app.fundamentals.diagnostic_comparability import content_fingerprint
from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily, CoreApiSnapshotRepository


VERSION = "nse-surveillance-prospective/v1"
MAX_BYTES = 5 * 1024 * 1024
TIMEOUT_SECONDS = 15


class SurveillanceFamily(StrEnum):
    ASM = "ASM"
    GSM = "GSM"
    PRICE_BAND = "PRICE_BAND"


class CaptureState(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    UNPROVEN = "UNPROVEN"
    CONFLICTED = "CONFLICTED"


def source_url(family: SurveillanceFamily) -> str:
    if not isinstance(family, SurveillanceFamily):
        raise ValueError("SURVEILLANCE_FAMILY_INVALID")
    return {
        SurveillanceFamily.ASM: "https://www.nseindia.com/api/reportASM",
        SurveillanceFamily.GSM: "https://www.nseindia.com/api/reportGSM",
        SurveillanceFamily.PRICE_BAND: "https://nsearchives.nseindia.com/content/equities/sec_list.csv",
    }[family]


def _digest(raw: bytes) -> str:
    return "sha256:" + sha256(raw).hexdigest()


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@dataclass(frozen=True, slots=True)
class SurveillanceFetch:
    family: SurveillanceFamily
    status: int | None
    body: bytes
    declared_length: int | None
    transfer_complete: bool
    reason: str | None = None

    def __post_init__(self):
        source_url(self.family)
        if (type(self.body) is not bytes or len(self.body) > MAX_BYTES
                or type(self.transfer_complete) is not bool
                or (self.status is not None and (type(self.status) is not int or not 100 <= self.status <= 599))
                or (self.declared_length is not None and (type(self.declared_length) is not int or self.declared_length < 0))
                or self.reason not in {None, "HTTP_REJECTED", "TIMEOUT", "TLS_FAILED", "NETWORK_FAILED",
                    "SIZE_BOUND", "ENCODING_UNSUPPORTED", "LENGTH_MISMATCH", "CONTENT_TYPE_UNSUPPORTED", "SENSITIVE_PAYLOAD_REJECTED"}
                or (self.transfer_complete and (self.status != 200 or self.reason is not None))):
            raise ValueError("SURVEILLANCE_FETCH_INVALID")


class OfficialSurveillanceTransport:
    """One GET per fixed product, no redirects, cookies, auth or retries.

    Only status/length/transfer facts cross the transport boundary. No response
    headers, proxy addresses or exception arguments enter a receipt or log.
    Certificate verification remains urllib's default.
    """
    def get(self, family: SurveillanceFamily) -> SurveillanceFetch:
        url = source_url(family)
        body, length, status = b"", None, None
        started = monotonic()
        try:
            request = Request(url, headers={"User-Agent": "HSI-NSE-Stock-Manager/1.0",
                "Accept-Encoding": "identity", "Accept": "application/json,text/csv,*/*"})
            with build_opener(_NoRedirect()).open(request, timeout=TIMEOUT_SECONDS) as response:
                status = response.status
                if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                    return SurveillanceFetch(family, status, b"", None, False, "ENCODING_UNSUPPORTED")
                content_type = response.headers.get_content_type()
                allowed = {"application/json", "text/csv", "application/csv", "text/plain", "application/octet-stream", "application/vnd.ms-excel"}
                if content_type not in allowed:
                    return SurveillanceFetch(family, status, b"", None, False, "CONTENT_TYPE_UNSUPPORTED")
                raw_length = response.headers.get("Content-Length")
                length = int(raw_length) if raw_length and raw_length.isdigit() else None
                if length is not None and length > MAX_BYTES:
                    return SurveillanceFetch(family, status, b"", length, False, "SIZE_BOUND")
                while True:
                    if monotonic() - started > TIMEOUT_SECONDS:
                        raise TimeoutError
                    chunk = response.read1(min(65536, MAX_BYTES + 1 - len(body)))
                    if len(body) + len(chunk) > MAX_BYTES:
                        return SurveillanceFetch(family, status, body, length, False, "SIZE_BOUND")
                    if not chunk:
                        break
                    body += chunk
                if length is not None and len(body) != length:
                    return SurveillanceFetch(family, status, body, length, False, "LENGTH_MISMATCH")
                return SurveillanceFetch(family, status, body, length, True)
        except HTTPError as error:
            error.close()
            return SurveillanceFetch(family, error.code, b"", None, False, "HTTP_REJECTED")
        except (TimeoutError, socket.timeout):
            reason = "TIMEOUT"
        except ssl.SSLError:
            reason = "TLS_FAILED"
        except (URLError, OSError, HTTPException):
            reason = "NETWORK_FAILED"
        return SurveillanceFetch(family, status, body, length, False, reason)


@dataclass(frozen=True, slots=True)
class SurveillanceRawSnapshot:
    family: SurveillanceFamily
    raw_base64: str
    payload_fingerprint: str
    first_observed_at: datetime
    adapter_version: str = VERSION

    def __post_init__(self):
        source_url(self.family)
        object.__setattr__(self, "first_observed_at", utc(self.first_observed_at))
        raw = self.raw_payload()
        if not raw or len(raw) > MAX_BYTES or _digest(raw) != self.payload_fingerprint or self.adapter_version != VERSION:
            raise ValueError("SURVEILLANCE_RAW_INVALID")

    def raw_payload(self) -> bytes:
        return b64decode(self.raw_base64, validate=True)

    @property
    def record_id(self) -> str:
        return "surveillance-raw:" + content_fingerprint((source_url(self.family), self.adapter_version, self.payload_fingerprint))[7:]

    @property
    def fingerprint(self) -> str:
        return content_fingerprint(self)


@dataclass(frozen=True, slots=True)
class SurveillancePollReceipt:
    family: SurveillanceFamily
    requested_at: datetime
    completed_at: datetime
    raw: SurveillanceRawSnapshot | None
    http_status: int | None
    bytes_received: int
    declared_length: int | None
    transfer_complete: bool
    reason: str | None
    adapter_version: str = VERSION

    def __post_init__(self):
        object.__setattr__(self, "requested_at", utc(self.requested_at))
        object.__setattr__(self, "completed_at", utc(self.completed_at))
        raw = self.raw.raw_payload() if self.raw else b""
        SurveillanceFetch(self.family, self.http_status, raw, self.declared_length, self.transfer_complete, self.reason)
        if self.raw:
            self.raw.__post_init__()
        if (self.adapter_version != VERSION or self.completed_at < self.requested_at
                or self.bytes_received != len(raw)
                or (self.raw and (self.raw.family != self.family or self.raw.first_observed_at > self.completed_at))):
            raise ValueError("SURVEILLANCE_POLL_INVALID")

    @property
    def record_id(self) -> str:
        return "surveillance-poll:" + self.fingerprint[7:]

    @property
    def fingerprint(self) -> str:
        return content_fingerprint(self)


class SurveillanceEvidenceStore:
    """Thin insert-only wrapper, same canonical snapshot database and serializer."""
    family = CoreApiSnapshotFamily.NSE_SURVEILLANCE_PROSPECTIVE

    def __init__(self, repository: CoreApiSnapshotRepository):
        self.repository = repository

    def get(self, record_id: str):
        row = self.repository.get_snapshot(record_id)
        if row is None:
            return None
        value = row.payload
        value.__post_init__()
        created = (value.first_observed_at if isinstance(value, SurveillanceRawSnapshot) else
            value.completed_at if isinstance(value, SurveillancePollReceipt) else value.processed_at)
        if (row.family is not self.family or row.schema_version != "v1" or row.created_at != created
                or row.record_type != type(value).__name__ or row.snapshot_id != value.record_id
                or row.fingerprint != value.fingerprint):
            raise ValueError("SURVEILLANCE_STORED_LINEAGE_INVALID")
        return value

    def save(self, value, at: datetime):
        value.__post_init__()
        existing = self.get(value.record_id)
        if existing is not None:
            if existing != value:
                raise ValueError("SURVEILLANCE_IMMUTABILITY_CONFLICT")
            return existing
        self.repository.save_snapshot(CoreApiSnapshot(value.record_id, self.family, "v1",
            type(value).__name__, value.fingerprint, utc(at), value))
        return value

    def retain_raw(self, family: SurveillanceFamily, body: bytes, observed_at: datetime) -> SurveillanceRawSnapshot:
        value = SurveillanceRawSnapshot(family, b64encode(body).decode("ascii"), _digest(body), observed_at)
        existing = self.get(value.record_id)
        if existing is not None:
            if (not isinstance(existing, SurveillanceRawSnapshot) or existing.raw_payload() != body
                    or existing.family is not family or existing.first_observed_at > value.first_observed_at):
                raise ValueError("SURVEILLANCE_RAW_COLLISION_OR_CLOCK_REGRESSION")
            return existing
        return self.save(value, value.first_observed_at)


class ProspectiveSurveillanceCollector:
    def __init__(self, store: SurveillanceEvidenceStore, transport: OfficialSurveillanceTransport,
                 *, clock: CollectorClock | None = None):
        self.store, self.transport = store, transport
        self.clock = clock or SystemUtcClock()

    def collect_once(self) -> tuple[SurveillancePollReceipt, ...]:
        """Exactly three sequential requests; every completed poll checkpointed.

        Observation is captured after the bounded body read, before parsing.
        There is deliberately no production caller-supplied historical cutoff.
        """
        polls = []
        for family in SurveillanceFamily:
            started = utc(self.clock.now())
            response = self.transport.get(family)
            completed = utc(self.clock.now())
            if response.family is not family or completed < started:
                raise ValueError("SURVEILLANCE_RESPONSE_OR_CLOCK_INVALID")
            # Never retain a credential-bearing/error payload as public raw
            # evidence. No redacted bytes masquerade as the original artifact.
            if re.search(rb'(?i)(?:"|\b)(?:access_token|api_secret|api_key|client_secret|password|authorization|set-cookie|cookie)(?:"|\s*[:=])', response.body):
                response = SurveillanceFetch(family, response.status, b"", response.declared_length, False, "SENSITIVE_PAYLOAD_REJECTED")
            raw = self.store.retain_raw(family, response.body, completed) if response.body else None
            poll = SurveillancePollReceipt(family, started, completed, raw, response.status,
                len(response.body), response.declared_length, response.transfer_complete, response.reason)
            polls.append(self.store.save(poll, completed))
        return tuple(polls)
