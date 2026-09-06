"""Read-only feasibility probe for first-party NSE Indices Daily OHLC.

This module deliberately does not use the canonical observation store.  It is
for source-contract proof only: a positive result is not permission to write
production observations or to alter Rule 2/3 readiness.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import date, datetime
from enum import StrEnum
from hashlib import sha256
from time import sleep
from typing import Callable, Iterable, Protocol

import requests

from app.market_data.index_close_series import NSE_INDICES_HISTORICAL_URL


PROBE_VERSION = "official-nse-index-ohlc-feasibility-v1"
SOURCE_FAMILY = "NSE_INDICES_HISTORICAL_INDEX_DATA"
_FIELDS = ("DATE", "OPEN", "HIGH", "LOW", "CLOSE")


class OfficialIndexOhlcAvailability(StrEnum):
    OFFICIAL_OHLC_VERIFIED = "OFFICIAL_OHLC_VERIFIED"
    OFFICIAL_CLOSE_ONLY = "OFFICIAL_CLOSE_ONLY"
    OFFICIAL_INDEX_EXISTS_OHLC_NOT_FOUND = "OFFICIAL_INDEX_EXISTS_OHLC_NOT_FOUND"
    OFFICIAL_NO_DATA = "OFFICIAL_NO_DATA"
    OFFICIAL_NAME_OR_PARAMETER_MISMATCH = "OFFICIAL_NAME_OR_PARAMETER_MISMATCH"
    OFFICIAL_ACCESS_BLOCKED = "OFFICIAL_ACCESS_BLOCKED"
    SEMANTIC_MISMATCH = "SEMANTIC_MISMATCH"
    NOT_VERIFIED = "NOT_VERIFIED"


class OfficialIndexReturnFamily(StrEnum):
    PRICE_RETURN_INDEX = "PRICE_RETURN_INDEX"
    TOTAL_RETURN_INDEX = "TOTAL_RETURN_INDEX"
    NOT_VERIFIED = "NOT_VERIFIED"


@dataclass(frozen=True, slots=True)
class OfficialNseIndexOhlcProbeTarget:
    """An exact configured sector path plus separately evidenced query names."""

    canonical_sector: str
    canonical_index_id: str
    configured_official_name: str
    historical_query_names: tuple[str, ...]
    return_family: OfficialIndexReturnFamily
    affected_security_count: int

    def __post_init__(self) -> None:
        canonical = (self.configured_official_name, *tuple(sorted({
            item for item in self.historical_query_names
            if item.casefold() != self.configured_official_name.casefold()
        }, key=str.casefold)))
        if (
            not self.canonical_sector
            or not self.canonical_index_id
            or not self.configured_official_name
            or self.historical_query_names != canonical
            or not isinstance(self.return_family, OfficialIndexReturnFamily)
            or self.return_family is OfficialIndexReturnFamily.TOTAL_RETURN_INDEX
            or self.affected_security_count < 0
        ):
            raise ValueError("OFFICIAL_INDEX_OHLC_PROBE_TARGET_INVALID")


@dataclass(frozen=True, slots=True)
class OfficialNseIndexOhlcFeasibilityResult:
    """One deterministic, non-persistent first-party source receipt."""

    canonical_sector: str
    canonical_index_id: str
    configured_official_name: str
    observed_official_name: str | None
    source_url: str
    source_family: str
    availability: OfficialIndexOhlcAvailability
    observed_fields: tuple[str, ...]
    first_session: date | None
    last_session: date | None
    session_count: int
    duplicate_count: int
    conflict_count: int
    missing_expected_session_count: int | None
    return_family: OfficialIndexReturnFamily
    reason_code: str
    raw_artifact_sha256: str | None
    affected_security_count: int
    potential_rule_2_3_coverage_gain: int

    def __post_init__(self) -> None:
        fields = tuple(sorted(set(self.observed_fields), key=_FIELDS.index))
        eligible_gain = (
            self.availability is OfficialIndexOhlcAvailability.OFFICIAL_OHLC_VERIFIED
            or (
                self.availability is OfficialIndexOhlcAvailability.OFFICIAL_NAME_OR_PARAMETER_MISMATCH
                and self.reason_code == "NSE_INDICES_HISTORICAL_CONFIGURED_NAME_NOT_RETRIEVABLE_ALTERNATE_VERIFIED"
            )
        )
        if (
            not self.canonical_sector
            or not self.canonical_index_id
            or not self.configured_official_name
            or self.source_url != NSE_INDICES_HISTORICAL_URL
            or self.source_family != SOURCE_FAMILY
            or not isinstance(self.availability, OfficialIndexOhlcAvailability)
            or self.observed_fields != fields
            or any(item not in _FIELDS for item in fields)
            or self.session_count < 0
            or self.duplicate_count < 0
            or self.conflict_count < 0
            or (self.session_count == 0 and (self.first_session is not None or self.last_session is not None))
            or (self.session_count > 0 and (self.first_session is None or self.last_session is None or self.first_session > self.last_session))
            or (self.missing_expected_session_count is not None and self.missing_expected_session_count < 0)
            or not isinstance(self.return_family, OfficialIndexReturnFamily)
            or not self.reason_code
            or (self.raw_artifact_sha256 is not None and not _sha256(self.raw_artifact_sha256))
            or self.affected_security_count < 0
            or self.potential_rule_2_3_coverage_gain != (self.affected_security_count if eligible_gain else 0)
        ):
            raise ValueError("OFFICIAL_INDEX_OHLC_FEASIBILITY_RESULT_INVALID")


class OfficialNseIndexOhlcProbeTransport(Protocol):
    def fetch(self, *, official_index_name: str, start: date, end: date) -> bytes: ...


class NseIndicesHistoricalOhlcProbeTransport:
    """A bounded first-party fetcher with no retry, cache, or persistence."""

    def __init__(
        self, *, session: requests.Session | None = None, timeout_seconds: int = 45,
    ) -> None:
        self._session = session or requests.Session()
        self._timeout_seconds = timeout_seconds

    def fetch(self, *, official_index_name: str, start: date, end: date) -> bytes:
        if end < start or (end - start).days > 365:
            raise ValueError("NSE_INDICES_HISTORICAL_PROBE_DATE_RANGE_INVALID")
        cinfo = "{'name':'%s','startDate':'%s','endDate':'%s','indexName':'%s'}" % (
            official_index_name.upper(), start.isoformat(), end.isoformat(), official_index_name,
        )
        response = self._session.post(
            NSE_INDICES_HISTORICAL_URL,
            json={"cinfo": cinfo},
            timeout=self._timeout_seconds,
            headers={"Accept": "application/json", "User-Agent": "HSI-NSE-Stock-Manager/1.0"},
        )
        response.raise_for_status()
        return response.content


class OfficialNseIndexOhlcFeasibilityProbe:
    """Read-only exact-name feasibility evaluator for source-contract evidence."""

    def __init__(
        self, *, transport: OfficialNseIndexOhlcProbeTransport | None = None,
        request_interval_seconds: float = 1.0,
        sleeper: Callable[[float], None] = sleep,
    ) -> None:
        if request_interval_seconds < 0:
            raise ValueError("OFFICIAL_INDEX_OHLC_PROBE_INTERVAL_INVALID")
        self._transport = transport or NseIndicesHistoricalOhlcProbeTransport()
        self._interval, self._sleeper = request_interval_seconds, sleeper

    def probe(
        self, *, target: OfficialNseIndexOhlcProbeTarget, start: date, end: date,
        expected_sessions: Iterable[date],
    ) -> OfficialNseIndexOhlcFeasibilityResult:
        target.__post_init__()
        expected = _expected_sessions(expected_sessions)
        attempts: list[OfficialNseIndexOhlcFeasibilityResult] = []
        for number, name in enumerate(target.historical_query_names):
            if number:
                self._sleeper(self._interval)
            try:
                raw = self._transport.fetch(official_index_name=name, start=start, end=end)
            except (requests.RequestException, OSError, TimeoutError):
                attempts.append(_result(
                    target, name, OfficialIndexOhlcAvailability.OFFICIAL_ACCESS_BLOCKED,
                    (), (), 0, 0, 0, None, "NSE_INDICES_HISTORICAL_ACCESS_BLOCKED", None,
                ))
                continue
            attempts.append(_assess_raw(target, name, raw, expected))
        return _select_target_result(target, tuple(attempts))


def serialize_official_nse_index_ohlc_feasibility(
    value: OfficialNseIndexOhlcFeasibilityResult,
) -> str:
    """Stable report serialization; it never includes raw provider payloads."""
    value.__post_init__()
    return json.dumps({
        "canonical_sector": value.canonical_sector,
        "canonical_index_id": value.canonical_index_id,
        "configured_official_name": value.configured_official_name,
        "observed_official_name": value.observed_official_name,
        "source_url": value.source_url,
        "source_family": value.source_family,
        "availability": value.availability.value,
        "observed_fields": value.observed_fields,
        "first_session": None if value.first_session is None else value.first_session.isoformat(),
        "last_session": None if value.last_session is None else value.last_session.isoformat(),
        "session_count": value.session_count,
        "duplicate_count": value.duplicate_count,
        "conflict_count": value.conflict_count,
        "missing_expected_session_count": value.missing_expected_session_count,
        "return_family": value.return_family.value,
        "reason_code": value.reason_code,
        "raw_artifact_sha256": value.raw_artifact_sha256,
        "affected_security_count": value.affected_security_count,
        "potential_rule_2_3_coverage_gain": value.potential_rule_2_3_coverage_gain,
        "probe_version": PROBE_VERSION,
    }, sort_keys=True, separators=(",", ":"))


def _assess_raw(
    target: OfficialNseIndexOhlcProbeTarget, queried_name: str, raw: bytes,
    expected_sessions: tuple[date, ...],
) -> OfficialNseIndexOhlcFeasibilityResult:
    raw_hash = sha256(raw).hexdigest()
    try:
        payload = _payload(raw)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        return _result(target, queried_name, OfficialIndexOhlcAvailability.NOT_VERIFIED, (), (), 0, 0, 0, None, "NSE_INDICES_HISTORICAL_RESPONSE_MALFORMED", raw_hash)
    if not payload:
        return _result(target, queried_name, OfficialIndexOhlcAvailability.OFFICIAL_NO_DATA, (), (), 0, 0, 0, len(expected_sessions), "NSE_INDICES_HISTORICAL_NO_DATA", raw_hash)
    rows: dict[date, tuple[str, str, str, str]] = {}
    duplicates = conflicts = 0
    names: set[str] = set()
    fields: set[str] = {"DATE"}
    for row in payload:
        if not isinstance(row, dict):
            return _result(target, queried_name, OfficialIndexOhlcAvailability.NOT_VERIFIED, (), (), 0, duplicates, conflicts, None, "NSE_INDICES_HISTORICAL_RESPONSE_SCHEMA_UNSUPPORTED", raw_hash)
        name = str(row.get("INDEX_NAME", "")).strip()
        if not name or name.casefold() != queried_name.casefold():
            return _result(target, queried_name, OfficialIndexOhlcAvailability.OFFICIAL_NAME_OR_PARAMETER_MISMATCH, (), (), 0, duplicates, conflicts, None, "NSE_INDICES_HISTORICAL_EXACT_INDEX_IDENTITY_REQUIRED", raw_hash)
        names.add(name)
        try:
            session = datetime.strptime(str(row["HistoricalDate"]), "%d %b %Y").date()
        except (KeyError, TypeError, ValueError):
            return _result(target, queried_name, OfficialIndexOhlcAvailability.NOT_VERIFIED, (), (), 0, duplicates, conflicts, None, "NSE_INDICES_HISTORICAL_DATE_INVALID", raw_hash)
        values = tuple(str(row.get(field, "")).strip() for field in ("OPEN", "HIGH", "LOW", "CLOSE"))
        if _decimal(values[3]) is not None:
            fields.add("CLOSE")
        for field, value in zip(("OPEN", "HIGH", "LOW"), values[:3], strict=True):
            if _decimal(value) is not None:
                fields.add(field)
        prior = rows.get(session)
        if prior is not None:
            duplicates += 1
            if prior != values:
                conflicts += 1
        else:
            rows[session] = values
    sessions = tuple(sorted(rows))
    missing = len(set(expected_sessions) - set(sessions))
    if conflicts:
        return _result(target, _one_name(names), OfficialIndexOhlcAvailability.NOT_VERIFIED, fields, sessions, len(sessions), duplicates, conflicts, missing, "NSE_INDICES_HISTORICAL_DUPLICATE_SESSION_CONFLICT", raw_hash)
    if missing:
        return _result(target, _one_name(names), OfficialIndexOhlcAvailability.NOT_VERIFIED, fields, sessions, len(sessions), duplicates, conflicts, missing, "NSE_INDICES_HISTORICAL_SESSION_ALIGNMENT_FAILED", raw_hash)
    if not all(_decimal(value) is not None for values in rows.values() for value in values):
        availability = (
            OfficialIndexOhlcAvailability.OFFICIAL_CLOSE_ONLY
            if fields == {"DATE", "CLOSE"}
            else OfficialIndexOhlcAvailability.OFFICIAL_INDEX_EXISTS_OHLC_NOT_FOUND
        )
        return _result(target, _one_name(names), availability, fields, sessions, len(sessions), duplicates, conflicts, missing, "NSE_INDICES_HISTORICAL_FULL_OHLC_UNAVAILABLE", raw_hash)
    return _result(target, _one_name(names), OfficialIndexOhlcAvailability.OFFICIAL_OHLC_VERIFIED, fields, sessions, len(sessions), duplicates, conflicts, missing, "NSE_INDICES_HISTORICAL_FULL_OHLC_VERIFIED", raw_hash)


def _select_target_result(
    target: OfficialNseIndexOhlcProbeTarget,
    attempts: tuple[OfficialNseIndexOhlcFeasibilityResult, ...],
) -> OfficialNseIndexOhlcFeasibilityResult:
    if not attempts:
        raise ValueError("OFFICIAL_INDEX_OHLC_PROBE_ATTEMPT_REQUIRED")
    configured = attempts[0]
    if configured.availability is OfficialIndexOhlcAvailability.OFFICIAL_OHLC_VERIFIED:
        return configured
    alternate = next((item for item in attempts[1:] if item.availability is OfficialIndexOhlcAvailability.OFFICIAL_OHLC_VERIFIED), None)
    if alternate is None:
        return configured
    return replace(
        alternate,
        availability=OfficialIndexOhlcAvailability.OFFICIAL_NAME_OR_PARAMETER_MISMATCH,
        reason_code="NSE_INDICES_HISTORICAL_CONFIGURED_NAME_NOT_RETRIEVABLE_ALTERNATE_VERIFIED",
        potential_rule_2_3_coverage_gain=alternate.affected_security_count,
    )


def _result(
    target: OfficialNseIndexOhlcProbeTarget, observed_name: str | None,
    availability: OfficialIndexOhlcAvailability, fields: Iterable[str], sessions: Iterable[date],
    count: int, duplicates: int, conflicts: int, missing: int | None,
    reason: str, raw_hash: str | None,
) -> OfficialNseIndexOhlcFeasibilityResult:
    ordered = tuple(sorted(set(sessions)))
    if count != len(ordered):
        raise ValueError("OFFICIAL_INDEX_OHLC_FEASIBILITY_SESSION_COUNT_INVALID")
    return OfficialNseIndexOhlcFeasibilityResult(
        target.canonical_sector, target.canonical_index_id, target.configured_official_name,
        observed_name, NSE_INDICES_HISTORICAL_URL, SOURCE_FAMILY, availability,
        tuple(sorted(set(fields), key=_FIELDS.index)), ordered[0] if ordered else None,
        ordered[-1] if ordered else None, count, duplicates, conflicts, missing,
        target.return_family, reason, raw_hash, target.affected_security_count,
        target.affected_security_count if availability is OfficialIndexOhlcAvailability.OFFICIAL_OHLC_VERIFIED else 0,
    )


def _payload(raw: bytes) -> list[object]:
    payload: object = json.loads(raw.decode("utf-8-sig"))
    if isinstance(payload, str):
        payload = json.loads(payload)
    if isinstance(payload, dict) and isinstance(payload.get("d"), str):
        payload = json.loads(payload["d"])
    if not isinstance(payload, list):
        raise ValueError("NSE_INDICES_HISTORICAL_RESPONSE_SCHEMA_UNSUPPORTED")
    return payload


def _decimal(value: str) -> float | None:
    try:
        parsed = float(value.replace(",", ""))
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def _expected_sessions(values: Iterable[date]) -> tuple[date, ...]:
    source = tuple(values)
    result = tuple(sorted(set(source)))
    if not result or len(result) != len(source):
        raise ValueError("OFFICIAL_INDEX_OHLC_EXPECTED_SESSIONS_INVALID")
    return result


def _one_name(values: set[str]) -> str | None:
    if len({value.casefold() for value in values}) != 1:
        return None
    return min(values, key=lambda value: (value.casefold(), value))


def _sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


__all__ = (
    "NseIndicesHistoricalOhlcProbeTransport", "OfficialIndexOhlcAvailability",
    "OfficialIndexReturnFamily", "OfficialNseIndexOhlcFeasibilityProbe",
    "OfficialNseIndexOhlcFeasibilityResult", "OfficialNseIndexOhlcProbeTarget",
    "PROBE_VERSION", "SOURCE_FAMILY", "serialize_official_nse_index_ohlc_feasibility",
)
