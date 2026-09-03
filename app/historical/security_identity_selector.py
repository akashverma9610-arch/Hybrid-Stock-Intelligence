"""Pure PIT selection of existing immutable historical security identities.

This module consumes only ``HistoricalSecurityIdentity`` receipts already
obtained through an approved source.  It neither imports a current master nor
infers listing, delisting, symbol, ISIN, or successor continuity.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Iterable

from app.historical.guard import manifest_fingerprint
from app.historical.security_master import HistoricalSecurityIdentity, HistoricalSecurityStatus


CONTRACT_ID = "historical-security-identity-pit-selector"
CONTRACT_VERSION = "v1"


class HistoricalSecurityIdentityResolutionStatus(StrEnum):
    RESOLVED = "RESOLVED"
    DATA_UNAVAILABLE = "DATA_UNAVAILABLE"
    EVIDENCE_CONFLICTED = "EVIDENCE_CONFLICTED"
    NOT_EFFECTIVE = "NOT_EFFECTIVE"
    NOT_LISTED = "NOT_LISTED"


class HistoricalSecurityIdentityResolutionReason(StrEnum):
    IDENTITY_EVIDENCE_REQUIRED = "IDENTITY_EVIDENCE_REQUIRED"
    IDENTITY_NOT_KNOWN_AT_AS_OF = "IDENTITY_NOT_KNOWN_AT_AS_OF"
    IDENTITY_NOT_EFFECTIVE_AT_AS_OF = "IDENTITY_NOT_EFFECTIVE_AT_AS_OF"
    LISTING_INTERVAL_EXCLUDES_AS_OF = "LISTING_INTERVAL_EXCLUDES_AS_OF"
    LIFECYCLE_NOT_ACTIVE = "LIFECYCLE_NOT_ACTIVE"
    AMBIGUOUS_EFFECTIVE_IDENTITY = "AMBIGUOUS_EFFECTIVE_IDENTITY"


@dataclass(frozen=True, slots=True)
class HistoricalSecurityIdentityResolution:
    canonical_instrument_id: str
    as_of: datetime
    status: HistoricalSecurityIdentityResolutionStatus
    reasons: tuple[HistoricalSecurityIdentityResolutionReason, ...]
    identity_id: str | None
    exchange: str | None
    symbol: str | None
    isin: str | None
    listing_status: HistoricalSecurityStatus | None
    listed: bool | None
    eligible: bool | None
    source: str | None
    source_reference: str | None
    source_as_of: datetime | None
    effective_from: datetime | None
    effective_to: datetime | None
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if not self.canonical_instrument_id or not _aware(self.as_of):
            raise ValueError("HISTORICAL_SECURITY_IDENTITY_RESOLUTION_REQUEST_INVALID")
        if self.reasons != tuple(sorted(set(self.reasons), key=lambda item: item.value)):
            raise ValueError("HISTORICAL_SECURITY_IDENTITY_RESOLUTION_REASONS_NONCANONICAL")
        if self.status is HistoricalSecurityIdentityResolutionStatus.RESOLVED:
            if (not self.identity_id or not self.exchange or not self.symbol or
                    self.listing_status is None or self.listed is not True or self.eligible is not True or self.reasons):
                raise ValueError("HISTORICAL_SECURITY_IDENTITY_RESOLUTION_RESOLVED_FIELDS_REQUIRED")
        elif any(value is not None for value in (self.identity_id, self.exchange, self.symbol, self.isin, self.listing_status, self.listed, self.eligible, self.source, self.source_reference, self.source_as_of, self.effective_from, self.effective_to)):
            raise ValueError("HISTORICAL_SECURITY_IDENTITY_RESOLUTION_UNAVAILABLE_FIELDS_FORBIDDEN")
        if self.contract_id != CONTRACT_ID or self.contract_version != CONTRACT_VERSION or self.fingerprint != historical_security_identity_resolution_fingerprint(self):
            raise ValueError("HISTORICAL_SECURITY_IDENTITY_RESOLUTION_FINGERPRINT_MISMATCH")


def resolve_historical_security_identity(
    identities: Iterable[HistoricalSecurityIdentity], *, canonical_instrument_id: str, as_of: datetime,
) -> HistoricalSecurityIdentityResolution:
    """Resolve one exact identity at a supplied historical cutoff.

    ``HistoricalSecurityIdentity.as_of`` is the immutable observation/known
    boundary.  Symbol/listing intervals are separately checked, so announced
    future identity changes never replace an identity before their effective
    timestamp.
    """
    if not _aware(as_of):
        raise ValueError("HISTORICAL_SECURITY_IDENTITY_AS_OF_REQUIRED")
    all_values = tuple(item for item in identities if item.canonical_instrument_id == canonical_instrument_id)
    known = tuple(item for item in all_values if item.as_of <= as_of)
    if not all_values:
        return _unavailable(canonical_instrument_id, as_of, HistoricalSecurityIdentityResolutionStatus.DATA_UNAVAILABLE, HistoricalSecurityIdentityResolutionReason.IDENTITY_EVIDENCE_REQUIRED)
    if not known:
        return _unavailable(canonical_instrument_id, as_of, HistoricalSecurityIdentityResolutionStatus.DATA_UNAVAILABLE, HistoricalSecurityIdentityResolutionReason.IDENTITY_NOT_KNOWN_AT_AS_OF)
    effective = tuple(item for item in known if item.symbol_effective_from <= as_of and (item.symbol_effective_to is None or as_of <= item.symbol_effective_to))
    if not effective:
        return _unavailable(canonical_instrument_id, as_of, HistoricalSecurityIdentityResolutionStatus.NOT_EFFECTIVE, HistoricalSecurityIdentityResolutionReason.IDENTITY_NOT_EFFECTIVE_AT_AS_OF)
    semantic = {_semantic_key(item) for item in effective}
    if len(semantic) != 1:
        return _unavailable(canonical_instrument_id, as_of, HistoricalSecurityIdentityResolutionStatus.EVIDENCE_CONFLICTED, HistoricalSecurityIdentityResolutionReason.AMBIGUOUS_EFFECTIVE_IDENTITY)
    selected = min(effective, key=lambda item: item.identity_id)
    listed = (selected.listed_from is None or selected.listed_from <= as_of) and (selected.listed_until is None or as_of <= selected.listed_until)
    tradable = (selected.tradable_from is None or selected.tradable_from <= as_of) and (selected.tradable_until is None or as_of <= selected.tradable_until)
    if not listed or not tradable:
        return _unavailable(canonical_instrument_id, as_of, HistoricalSecurityIdentityResolutionStatus.NOT_LISTED, HistoricalSecurityIdentityResolutionReason.LISTING_INTERVAL_EXCLUDES_AS_OF)
    if selected.status is not HistoricalSecurityStatus.ACTIVE:
        return _unavailable(canonical_instrument_id, as_of, HistoricalSecurityIdentityResolutionStatus.NOT_LISTED, HistoricalSecurityIdentityResolutionReason.LIFECYCLE_NOT_ACTIVE)
    body = dict(canonical_instrument_id=canonical_instrument_id, as_of=as_of, status=HistoricalSecurityIdentityResolutionStatus.RESOLVED, reasons=(), identity_id=selected.identity_id, exchange=selected.exchange, symbol=selected.symbol, isin=selected.isin, listing_status=selected.status, listed=True, eligible=True, source=selected.source, source_reference=selected.source_reference, source_as_of=selected.as_of, effective_from=selected.symbol_effective_from, effective_to=selected.symbol_effective_to, contract_id=CONTRACT_ID, contract_version=CONTRACT_VERSION)
    return HistoricalSecurityIdentityResolution(**body, fingerprint=_fingerprint(body))


def historical_security_identity_resolution_fingerprint(value: HistoricalSecurityIdentityResolution) -> str:
    return _fingerprint({name: getattr(value, name) for name in value.__dataclass_fields__ if name != "fingerprint"})


def _unavailable(instrument, as_of, status, reason):
    body = dict(canonical_instrument_id=instrument, as_of=as_of, status=status, reasons=(reason,), identity_id=None, exchange=None, symbol=None, isin=None, listing_status=None, listed=None, eligible=None, source=None, source_reference=None, source_as_of=None, effective_from=None, effective_to=None, contract_id=CONTRACT_ID, contract_version=CONTRACT_VERSION)
    return HistoricalSecurityIdentityResolution(**body, fingerprint=_fingerprint(body))


def _semantic_key(value):
    return (value.exchange, value.symbol, value.isin, value.series, value.listed_from, value.listed_until, value.tradable_from, value.tradable_until, value.symbol_effective_from, value.symbol_effective_to, value.status, value.source, value.source_reference, value.as_of, value.version)


def _fingerprint(values):
    def convert(value):
        if isinstance(value, StrEnum): return value.value
        if isinstance(value, datetime): return value.astimezone(UTC).isoformat()
        if isinstance(value, tuple): return tuple(convert(item) for item in value)
        return value
    return "sha256:" + manifest_fingerprint(**{key: convert(value) for key, value in values.items()}).removeprefix("sha256:")


def _aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


__all__ = (
    "CONTRACT_ID", "CONTRACT_VERSION", "HistoricalSecurityIdentityResolution",
    "HistoricalSecurityIdentityResolutionReason", "HistoricalSecurityIdentityResolutionStatus",
    "historical_security_identity_resolution_fingerprint", "resolve_historical_security_identity",
)
