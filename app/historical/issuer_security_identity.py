"""Immutable, primary-evidence issuer-to-listed-security bridge receipts.

This is a deliberately narrow identity boundary.  It binds one *exact* NSE
session-security receipt to one stable issuer identifier supplied by an
approved primary source.  It neither creates an issuer/company master nor
uses a name, ticker, ISIN continuity, or group relationship as an issuer
inference.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
import hashlib
import json
import re
from typing import Iterable

from app.historical.nse_session_identity import (
    NseSessionIdentitySemantic,
    NseSessionPointIdentity,
    nse_session_point_identity_fingerprint,
)


CONTRACT_ID = "issuer-legal-entity-security-identity-bridge"
CONTRACT_VERSION = "v1"
_ID = re.compile(r"[A-Za-z0-9._:-]+\Z")
_ISSUER_KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{1,127}\Z")
_ISIN = re.compile(r"[A-Z]{2}[A-Z0-9]{9}[0-9]\Z")
_FP = re.compile(r"sha256:[0-9a-f]{64}\Z")
_CIN = re.compile(r"[LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}\Z")
_LEI = re.compile(r"[A-Z0-9]{20}\Z")


class IssuerIdentifierType(StrEnum):
    """Stable identifier types; a legal name is intentionally not one."""

    CANONICAL_ISSUER_ID = "CANONICAL_ISSUER_ID"
    CIN = "CIN"
    LEI = "LEI"
    REGULATOR_REGISTRATION_ID = "REGULATOR_REGISTRATION_ID"
    OFFICIAL_LISTING_ISSUER_ID = "OFFICIAL_LISTING_ISSUER_ID"


class IssuerSecurityBridgeSourceType(StrEnum):
    """Only primary source families that can prove both sides of a bridge."""

    NSE_OFFICIAL_LISTING_RECORD = "NSE_OFFICIAL_LISTING_RECORD"
    BSE_OFFICIAL_LISTING_RECORD = "BSE_OFFICIAL_LISTING_RECORD"
    OFFICIAL_CORPORATE_FILING_STRUCTURED_IDENTITY = "OFFICIAL_CORPORATE_FILING_STRUCTURED_IDENTITY"
    APPROVED_DEPOSITORY_SECURITY_REFERENCE = "APPROVED_DEPOSITORY_SECURITY_REFERENCE"
    OFFICIAL_REGULATOR_ENTITY_RECORD = "OFFICIAL_REGULATOR_ENTITY_RECORD"


class IssuerSecurityBridgeTemporalSemantics(StrEnum):
    """The source's asserted temporal scope, never an inferred interval."""

    EXACT_SESSION_DATE = "EXACT_SESSION_DATE"
    EXPLICIT_EFFECTIVE_INTERVAL = "EXPLICIT_EFFECTIVE_INTERVAL"


class IssuerSecurityBridgeReadiness(StrEnum):
    EXACT_ISSUER_BRIDGE = "EXACT_ISSUER_BRIDGE"
    ISSUER_EVIDENCE_UNAVAILABLE = "ISSUER_EVIDENCE_UNAVAILABLE"
    SECURITY_IDENTITY_UNRESOLVED = "SECURITY_IDENTITY_UNRESOLVED"
    PIT_DATE_UNSUPPORTED = "PIT_DATE_UNSUPPORTED"
    EVIDENCE_CONFLICTED = "EVIDENCE_CONFLICTED"
    NON_COMPARABLE = "NON_COMPARABLE"


class IssuerSecurityBridgeReason(StrEnum):
    EXACT_PRIMARY_BRIDGE_PRESENT = "EXACT_PRIMARY_BRIDGE_PRESENT"
    EXACT_ISSUER_EVIDENCE_REQUIRED = "EXACT_ISSUER_EVIDENCE_REQUIRED"
    EXACT_SESSION_SECURITY_REQUIRED = "EXACT_SESSION_SECURITY_REQUIRED"
    SESSION_SCOPED_BRIDGE_REQUIRED = "SESSION_SCOPED_BRIDGE_REQUIRED"
    CONFLICTING_EXACT_ISSUER_EVIDENCE = "CONFLICTING_EXACT_ISSUER_EVIDENCE"


class IssuerSecurityBridgeError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class IssuerSecurityBridge:
    """One exact, immutable link; it is not an issuer master record.

    ``issuer_legal_entity_id`` is derived only from the supplied stable
    identifier type and value.  It is deliberately not a name normalisation,
    parent/group relationship, or a canonical company registry.
    """

    bridge_id: str
    session_security_receipt_id: str
    session_security_fingerprint: str
    session_date: date
    exchange: str
    symbol: str
    isin: str
    issuer_identifier_type: IssuerIdentifierType
    issuer_identifier_value: str
    issuer_legal_entity_id: str
    source_evidence_id: str
    source_evidence_fingerprint: str
    source_type: IssuerSecurityBridgeSourceType
    source_reference: str
    source_as_of_date: date
    source_observed_at: datetime
    historical_known_at: datetime | None
    temporal_semantics: IssuerSecurityBridgeTemporalSemantics
    effective_from: date | None
    effective_to: date | None
    fingerprint: str
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        _validate_bridge(self)
        if self.bridge_id != "issuer-security-bridge:" + _hash(_bridge_identity(self))[:32]:
            raise IssuerSecurityBridgeError("ISSUER_SECURITY_BRIDGE_IDENTITY_MISMATCH")
        if self.fingerprint != _hash(_bridge_payload(self)):
            raise IssuerSecurityBridgeError("ISSUER_SECURITY_BRIDGE_FINGERPRINT_MISMATCH")

    def verify(self) -> None:
        _validate_bridge(self)
        if self.bridge_id != "issuer-security-bridge:" + _hash(_bridge_identity(self))[:32]:
            raise IssuerSecurityBridgeError("ISSUER_SECURITY_BRIDGE_IDENTITY_MISMATCH")
        if self.fingerprint != _hash(_bridge_payload(self)):
            raise IssuerSecurityBridgeError("ISSUER_SECURITY_BRIDGE_FINGERPRINT_MISMATCH")


@dataclass(frozen=True, slots=True)
class IssuerSecurityBridgeResolution:
    """Read-only readiness result for one supplied session-security receipt."""

    session_security_receipt_id: str | None
    session_security_fingerprint: str | None
    session_date: date | None
    readiness: IssuerSecurityBridgeReadiness
    bridges: tuple[IssuerSecurityBridge, ...]
    reasons: tuple[IssuerSecurityBridgeReason, ...]
    fingerprint: str
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        _validate_resolution(self)
        if self.fingerprint != _hash(_resolution_payload(self)):
            raise IssuerSecurityBridgeError("ISSUER_SECURITY_BRIDGE_RESOLUTION_FINGERPRINT_MISMATCH")


def create_issuer_security_bridge(
    *,
    session_security: NseSessionPointIdentity,
    issuer_identifier_type: IssuerIdentifierType,
    issuer_identifier_value: str,
    source_evidence_id: str,
    source_evidence_fingerprint: str,
    source_type: IssuerSecurityBridgeSourceType,
    source_reference: str,
    source_as_of_date: date,
    source_observed_at: datetime,
    historical_known_at: datetime | None = None,
    temporal_semantics: IssuerSecurityBridgeTemporalSemantics = IssuerSecurityBridgeTemporalSemantics.EXACT_SESSION_DATE,
    effective_from: date | None = None,
    effective_to: date | None = None,
) -> IssuerSecurityBridge:
    """Create a bridge only from an already exact session-security receipt.

    Source interpretation is intentionally supplied by the approved source
    adapter.  This pure contract verifies the resulting binding and refuses to
    promote an observation for a different session into historical evidence.
    """
    _validate_session_security(session_security)
    if not isinstance(issuer_identifier_type, IssuerIdentifierType):
        raise IssuerSecurityBridgeError("ISSUER_SECURITY_BRIDGE_IDENTIFIER_TYPE_INVALID")
    if not isinstance(source_type, IssuerSecurityBridgeSourceType):
        raise IssuerSecurityBridgeError("ISSUER_SECURITY_BRIDGE_SOURCE_TYPE_INVALID")
    if not isinstance(temporal_semantics, IssuerSecurityBridgeTemporalSemantics):
        raise IssuerSecurityBridgeError("ISSUER_SECURITY_BRIDGE_TEMPORAL_SEMANTICS_INVALID")
    issuer_legal_entity_id = _issuer_legal_entity_id(issuer_identifier_type, issuer_identifier_value)
    values = {
        "session_security_receipt_id": session_security.receipt_id,
        "session_security_fingerprint": session_security.fingerprint,
        "session_date": session_security.session_date,
        "exchange": session_security.exchange,
        "symbol": session_security.symbol,
        "isin": session_security.isin,
        "issuer_identifier_type": issuer_identifier_type,
        "issuer_identifier_value": issuer_identifier_value,
        "issuer_legal_entity_id": issuer_legal_entity_id,
        "source_evidence_id": source_evidence_id,
        "source_evidence_fingerprint": source_evidence_fingerprint,
        "source_type": source_type,
        "source_reference": source_reference,
        "source_as_of_date": source_as_of_date,
        "source_observed_at": _utc(source_observed_at),
        "historical_known_at": _utc(historical_known_at) if historical_known_at is not None else None,
        "temporal_semantics": temporal_semantics,
        "effective_from": effective_from,
        "effective_to": effective_to,
    }
    bridge_id = "issuer-security-bridge:" + _hash(_bridge_identity_from_values(values))[:32]
    return IssuerSecurityBridge(
        bridge_id=bridge_id,
        **values,
        fingerprint=_hash(_bridge_payload_from_values(values | {"bridge_id": bridge_id})),
    )


def resolve_issuer_security_bridge(
    session_security: NseSessionPointIdentity | None,
    *,
    bridges: Iterable[IssuerSecurityBridge],
) -> IssuerSecurityBridgeResolution:
    """Resolve only exact same-session evidence, never current data backward.

    The function intentionally does not look up storage or use wall-clock
    state.  Repeating it with equivalent inputs produces the same receipt.
    """
    canonical = _canonical_bridges(bridges)
    if session_security is None or not _session_security_valid(session_security):
        return _resolution(None, IssuerSecurityBridgeReadiness.SECURITY_IDENTITY_UNRESOLVED, (), (
            IssuerSecurityBridgeReason.EXACT_SESSION_SECURITY_REQUIRED,
        ))
    exact = tuple(
        value for value in canonical
        if value.session_security_receipt_id == session_security.receipt_id
        and value.session_security_fingerprint == session_security.fingerprint
        and value.session_date == session_security.session_date
        and (value.exchange, value.symbol, value.isin) == (
            session_security.exchange, session_security.symbol, session_security.isin,
        )
    )
    if not exact:
        same_security_other_session = tuple(
            value for value in canonical
            if (value.exchange, value.symbol, value.isin) == (
                session_security.exchange, session_security.symbol, session_security.isin,
            )
        )
        if same_security_other_session:
            return _resolution(
                session_security, IssuerSecurityBridgeReadiness.PIT_DATE_UNSUPPORTED,
                same_security_other_session, (IssuerSecurityBridgeReason.SESSION_SCOPED_BRIDGE_REQUIRED,),
            )
        return _resolution(
            session_security, IssuerSecurityBridgeReadiness.ISSUER_EVIDENCE_UNAVAILABLE, (),
            (IssuerSecurityBridgeReason.EXACT_ISSUER_EVIDENCE_REQUIRED,),
        )
    issuer_ids = {item.issuer_legal_entity_id for item in exact}
    if len(issuer_ids) != 1:
        return _resolution(
            session_security, IssuerSecurityBridgeReadiness.EVIDENCE_CONFLICTED, exact,
            (IssuerSecurityBridgeReason.CONFLICTING_EXACT_ISSUER_EVIDENCE,),
        )
    return _resolution(
        session_security, IssuerSecurityBridgeReadiness.EXACT_ISSUER_BRIDGE, exact,
        (IssuerSecurityBridgeReason.EXACT_PRIMARY_BRIDGE_PRESENT,),
    )


def issuer_security_bridge_payload(value: IssuerSecurityBridge) -> dict[str, object]:
    value.verify()
    return _bridge_payload(value) | {"fingerprint": value.fingerprint}


def serialize_issuer_security_bridge(value: IssuerSecurityBridge) -> str:
    return json.dumps(issuer_security_bridge_payload(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def issuer_security_bridge_resolution_payload(value: IssuerSecurityBridgeResolution) -> dict[str, object]:
    _validate_resolution(value)
    return _resolution_payload(value) | {"fingerprint": value.fingerprint}


def serialize_issuer_security_bridge_resolution(value: IssuerSecurityBridgeResolution) -> str:
    return json.dumps(
        issuer_security_bridge_resolution_payload(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    )


def _resolution(
    session_security: NseSessionPointIdentity | None,
    readiness: IssuerSecurityBridgeReadiness,
    bridges: tuple[IssuerSecurityBridge, ...],
    reasons: tuple[IssuerSecurityBridgeReason, ...],
) -> IssuerSecurityBridgeResolution:
    body = {
        "session_security_receipt_id": session_security.receipt_id if session_security is not None else None,
        "session_security_fingerprint": session_security.fingerprint if session_security is not None else None,
        "session_date": session_security.session_date if session_security is not None else None,
        "readiness": readiness,
        "bridges": bridges,
        "reasons": tuple(sorted(set(reasons), key=lambda value: value.value)),
    }
    return IssuerSecurityBridgeResolution(**body, fingerprint=_hash(_resolution_payload_from_values(body)))


def _validate_bridge(value: IssuerSecurityBridge) -> None:
    if (
        not all((
            _identifier(value.bridge_id), _identifier(value.session_security_receipt_id),
            _fingerprint(value.session_security_fingerprint), _date(value.session_date),
            value.exchange == "NSE", _nonblank(value.symbol), _ISIN.fullmatch(value.isin) is not None,
            isinstance(value.issuer_identifier_type, IssuerIdentifierType),
            _issuer_identifier_valid(value.issuer_identifier_type, value.issuer_identifier_value),
            value.issuer_legal_entity_id == _issuer_legal_entity_id(value.issuer_identifier_type, value.issuer_identifier_value),
            _identifier(value.source_evidence_id), _fingerprint(value.source_evidence_fingerprint),
            isinstance(value.source_type, IssuerSecurityBridgeSourceType), _nonblank(value.source_reference),
            _date(value.source_as_of_date), _aware(value.source_observed_at),
            value.historical_known_at is None or _aware(value.historical_known_at),
            isinstance(value.temporal_semantics, IssuerSecurityBridgeTemporalSemantics),
            value.effective_from is None or _date(value.effective_from),
            value.effective_to is None or _date(value.effective_to),
            value.contract_id == CONTRACT_ID, value.contract_version == CONTRACT_VERSION,
        ))
        or (value.effective_from is not None and value.effective_to is not None and value.effective_to < value.effective_from)
    ):
        raise IssuerSecurityBridgeError("ISSUER_SECURITY_BRIDGE_INVALID")
    if value.temporal_semantics is IssuerSecurityBridgeTemporalSemantics.EXACT_SESSION_DATE:
        if value.source_as_of_date != value.session_date or value.effective_from is not None or value.effective_to is not None:
            raise IssuerSecurityBridgeError("ISSUER_SECURITY_BRIDGE_EXACT_SESSION_SEMANTICS_INVALID")
    else:
        if value.effective_from is None:
            raise IssuerSecurityBridgeError("ISSUER_SECURITY_BRIDGE_EFFECTIVE_INTERVAL_REQUIRED")
        if value.source_as_of_date > value.session_date or value.effective_from > value.session_date or (
            value.effective_to is not None and value.effective_to < value.session_date
        ):
            raise IssuerSecurityBridgeError("ISSUER_SECURITY_BRIDGE_FUTURE_OR_OUTSIDE_EFFECTIVE_EVIDENCE")
    if value.historical_known_at is not None and _utc(value.historical_known_at).date() > value.session_date:
        raise IssuerSecurityBridgeError("ISSUER_SECURITY_BRIDGE_FUTURE_EVIDENCE")


def _validate_resolution(value: IssuerSecurityBridgeResolution) -> None:
    if (
        not isinstance(value.readiness, IssuerSecurityBridgeReadiness)
        or value.bridges != _canonical_bridges(value.bridges)
        or value.reasons != tuple(sorted(set(value.reasons), key=lambda item: item.value))
        or not all(isinstance(item, IssuerSecurityBridgeReason) for item in value.reasons)
        or value.contract_id != CONTRACT_ID
        or value.contract_version != CONTRACT_VERSION
    ):
        raise IssuerSecurityBridgeError("ISSUER_SECURITY_BRIDGE_RESOLUTION_INVALID")
    has_session = all((value.session_security_receipt_id, value.session_security_fingerprint, value.session_date))
    if any(item is not None for item in (
        value.session_security_receipt_id, value.session_security_fingerprint, value.session_date,
    )) and not has_session:
        raise IssuerSecurityBridgeError("ISSUER_SECURITY_BRIDGE_RESOLUTION_SESSION_PARTIAL")
    if has_session and not (
        _identifier(value.session_security_receipt_id)
        and _fingerprint(value.session_security_fingerprint)
        and _date(value.session_date)
    ):
        raise IssuerSecurityBridgeError("ISSUER_SECURITY_BRIDGE_RESOLUTION_SESSION_INVALID")
    expected = {
        IssuerSecurityBridgeReadiness.EXACT_ISSUER_BRIDGE: (True, True, (IssuerSecurityBridgeReason.EXACT_PRIMARY_BRIDGE_PRESENT,)),
        IssuerSecurityBridgeReadiness.ISSUER_EVIDENCE_UNAVAILABLE: (True, False, (IssuerSecurityBridgeReason.EXACT_ISSUER_EVIDENCE_REQUIRED,)),
        IssuerSecurityBridgeReadiness.SECURITY_IDENTITY_UNRESOLVED: (False, False, (IssuerSecurityBridgeReason.EXACT_SESSION_SECURITY_REQUIRED,)),
        IssuerSecurityBridgeReadiness.PIT_DATE_UNSUPPORTED: (True, True, (IssuerSecurityBridgeReason.SESSION_SCOPED_BRIDGE_REQUIRED,)),
        IssuerSecurityBridgeReadiness.EVIDENCE_CONFLICTED: (True, True, (IssuerSecurityBridgeReason.CONFLICTING_EXACT_ISSUER_EVIDENCE,)),
        # Retained as an explicit consumer vocabulary value; this identity
        # contract does not create it without a separately approved context.
        IssuerSecurityBridgeReadiness.NON_COMPARABLE: (True, False, ()),
    }[value.readiness]
    session_required, bridges_required, reasons = expected
    if bool(has_session) is not session_required or bool(value.bridges) is not bridges_required or value.reasons != reasons:
        raise IssuerSecurityBridgeError("ISSUER_SECURITY_BRIDGE_RESOLUTION_STATE_CONTRADICTION")
    if value.readiness is IssuerSecurityBridgeReadiness.EXACT_ISSUER_BRIDGE:
        if len({item.issuer_legal_entity_id for item in value.bridges}) != 1:
            raise IssuerSecurityBridgeError("ISSUER_SECURITY_BRIDGE_RESOLUTION_EXACT_CONFLICT")
    if value.readiness is IssuerSecurityBridgeReadiness.EVIDENCE_CONFLICTED:
        if len({item.issuer_legal_entity_id for item in value.bridges}) < 2:
            raise IssuerSecurityBridgeError("ISSUER_SECURITY_BRIDGE_RESOLUTION_CONFLICT_MISSING")
    if has_session:
        for item in value.bridges:
            if value.readiness is not IssuerSecurityBridgeReadiness.PIT_DATE_UNSUPPORTED and (
                item.session_security_receipt_id != value.session_security_receipt_id
                or item.session_security_fingerprint != value.session_security_fingerprint
                or item.session_date != value.session_date
            ):
                raise IssuerSecurityBridgeError("ISSUER_SECURITY_BRIDGE_RESOLUTION_LINEAGE_MISMATCH")


def _validate_session_security(value: object) -> None:
    if not _session_security_valid(value):
        raise IssuerSecurityBridgeError("ISSUER_SECURITY_BRIDGE_SESSION_SECURITY_INVALID")


def _session_security_valid(value: object) -> bool:
    return (
        isinstance(value, NseSessionPointIdentity)
        and value.semantic is NseSessionIdentitySemantic.KNOWN_FOR_SESSION_D
        and value.fingerprint == nse_session_point_identity_fingerprint(value)
    )


def _canonical_bridges(values: Iterable[IssuerSecurityBridge]) -> tuple[IssuerSecurityBridge, ...]:
    supplied = tuple(values)
    if not all(isinstance(item, IssuerSecurityBridge) for item in supplied):
        raise IssuerSecurityBridgeError("ISSUER_SECURITY_BRIDGE_INPUT_INVALID")
    for item in supplied:
        item.verify()
    unique: dict[tuple[str, str], IssuerSecurityBridge] = {}
    for item in supplied:
        key = (item.bridge_id, item.fingerprint)
        existing = unique.get(key)
        if existing is not None and existing != item:
            raise IssuerSecurityBridgeError("ISSUER_SECURITY_BRIDGE_DUPLICATE_CONFLICT")
        unique[key] = item
    return tuple(sorted(unique.values(), key=lambda item: (item.session_date, item.bridge_id, item.fingerprint)))


def _issuer_identifier_valid(kind: IssuerIdentifierType, value: object) -> bool:
    if not isinstance(value, str):
        return False
    if kind is IssuerIdentifierType.CIN:
        return _CIN.fullmatch(value) is not None
    if kind is IssuerIdentifierType.LEI:
        return _LEI.fullmatch(value) is not None
    return _ISSUER_KEY.fullmatch(value) is not None


def _issuer_legal_entity_id(kind: IssuerIdentifierType, value: str) -> str:
    if not _issuer_identifier_valid(kind, value):
        raise IssuerSecurityBridgeError("ISSUER_SECURITY_BRIDGE_ISSUER_IDENTIFIER_INVALID")
    return "issuer:" + kind.value.lower() + ":" + value


def _bridge_identity(value: IssuerSecurityBridge) -> dict[str, object]:
    return _bridge_identity_from_values({name: getattr(value, name) for name in value.__dataclass_fields__ if name not in {
        "bridge_id", "fingerprint", "contract_id", "contract_version",
    }})


def _bridge_identity_from_values(value: dict[str, object]) -> dict[str, object]:
    return {
        "contract_id": CONTRACT_ID,
        "contract_version": CONTRACT_VERSION,
        "session_security_receipt_id": value["session_security_receipt_id"],
        "session_security_fingerprint": value["session_security_fingerprint"],
        "session_date": value["session_date"].isoformat(),
        "exchange": value["exchange"],
        "symbol": value["symbol"],
        "isin": value["isin"],
        "issuer_identifier_type": value["issuer_identifier_type"].value,
        "issuer_identifier_value": value["issuer_identifier_value"],
        "issuer_legal_entity_id": value["issuer_legal_entity_id"],
        "source_evidence_id": value["source_evidence_id"],
        "source_evidence_fingerprint": value["source_evidence_fingerprint"],
        "source_type": value["source_type"].value,
        "source_reference": value["source_reference"],
        "source_as_of_date": value["source_as_of_date"].isoformat(),
        "historical_known_at": _time(value["historical_known_at"]) if value["historical_known_at"] else None,
        "temporal_semantics": value["temporal_semantics"].value,
        "effective_from": value["effective_from"].isoformat() if value["effective_from"] else None,
        "effective_to": value["effective_to"].isoformat() if value["effective_to"] else None,
    }


def _bridge_payload(value: IssuerSecurityBridge) -> dict[str, object]:
    return _bridge_payload_from_values({name: getattr(value, name) for name in value.__dataclass_fields__ if name not in {
        "fingerprint", "contract_id", "contract_version",
    }})


def _bridge_payload_from_values(value: dict[str, object]) -> dict[str, object]:
    return _bridge_identity_from_values(value) | {
        "bridge_id": value["bridge_id"],
        "source_observed_at": _time(value["source_observed_at"]),
    }


def _resolution_payload(value: IssuerSecurityBridgeResolution) -> dict[str, object]:
    return _resolution_payload_from_values({name: getattr(value, name) for name in value.__dataclass_fields__ if name not in {
        "fingerprint", "contract_id", "contract_version",
    }})


def _resolution_payload_from_values(value: dict[str, object]) -> dict[str, object]:
    return {
        "contract_id": CONTRACT_ID,
        "contract_version": CONTRACT_VERSION,
        "session_security_receipt_id": value["session_security_receipt_id"],
        "session_security_fingerprint": value["session_security_fingerprint"],
        "session_date": value["session_date"].isoformat() if value["session_date"] else None,
        "readiness": value["readiness"].value,
        "bridges": tuple(issuer_security_bridge_payload(item) for item in value["bridges"]),
        "reasons": tuple(item.value for item in value["reasons"]),
    }


def _identifier(value: object) -> bool:
    return isinstance(value, str) and _ID.fullmatch(value) is not None


def _nonblank(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _fingerprint(value: object) -> bool:
    return isinstance(value, str) and _FP.fullmatch(value) is not None


def _date(value: object) -> bool:
    return isinstance(value, date) and not isinstance(value, datetime)


def _aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def _utc(value: datetime) -> datetime:
    if not _aware(value):
        raise IssuerSecurityBridgeError("ISSUER_SECURITY_BRIDGE_TIMESTAMP_INVALID")
    return value.astimezone(UTC)


def _time(value: datetime) -> str:
    return _utc(value).isoformat()


def _hash(value: object) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(),
    ).hexdigest()


__all__ = (
    "CONTRACT_ID", "CONTRACT_VERSION", "IssuerIdentifierType", "IssuerSecurityBridge",
    "IssuerSecurityBridgeError", "IssuerSecurityBridgeReadiness", "IssuerSecurityBridgeReason",
    "IssuerSecurityBridgeResolution", "IssuerSecurityBridgeSourceType", "IssuerSecurityBridgeTemporalSemantics",
    "create_issuer_security_bridge", "issuer_security_bridge_payload", "issuer_security_bridge_resolution_payload",
    "resolve_issuer_security_bridge", "serialize_issuer_security_bridge", "serialize_issuer_security_bridge_resolution",
)
