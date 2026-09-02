"""Typed, fail-closed identity reconciliation for NSE Regulation 31 exports.

This module records a source-identity relationship.  It does not change the
canonical security master and it never derives ownership percentages.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from hashlib import sha256

from app.storage.core_api_snapshot_repository import (
    CoreApiSnapshot, CoreApiSnapshotFamily, CoreApiSnapshotRepository,
)


class Reg31IdentityRelationship(StrEnum):
    CURRENT_MATCH = "CURRENT_MATCH"
    VERIFIED_PREDECESSOR = "VERIFIED_PREDECESSOR"
    DISTINCT_LEGACY_SECURITY = "DISTINCT_LEGACY_SECURITY"
    SOURCE_METADATA_ANOMALY = "SOURCE_METADATA_ANOMALY"
    UNRESOLVED = "UNRESOLVED"


class Reg31SecurityClass(StrEnum):
    EQUITY = "EQUITY"
    EQUITY_PARTLY_PAID = "EQUITY_PARTLY_PAID"
    UNKNOWN = "UNKNOWN"


class Reg31IdentitySufficiency(StrEnum):
    SUFFICIENT = "SUFFICIENT"
    INSUFFICIENT = "INSUFFICIENT"


@dataclass(frozen=True, slots=True)
class Reg31IdentityEvidence:
    """One exact official observation; no inference is implicit in it."""

    isin: str
    symbol: str
    issuer_name: str
    security_class: Reg31SecurityClass
    observed_at: datetime
    source_reference: str
    source_checksum: str

    def __post_init__(self) -> None:
        if not all((self.isin, self.symbol, self.issuer_name, self.source_reference, self.source_checksum)):
            raise ValueError("NSE Reg31 identity evidence is incomplete.")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("NSE Reg31 identity evidence must be point-in-time safe.")
        if len(self.source_checksum) != 64:
            raise ValueError("NSE Reg31 identity evidence checksum must be SHA-256.")


@dataclass(frozen=True, slots=True)
class Reg31IdentityReconciliation:
    """Immutable relationship between a canonical ISIN and source-returned ISIN."""

    canonical_instrument_id: str
    current_identity: Reg31IdentityEvidence
    returned_identity: Reg31IdentityEvidence
    relationship: Reg31IdentityRelationship
    effective_date: datetime | None
    issuer_continuity: bool
    symbol_continuity: bool
    security_class_continuity: bool
    sufficiency: Reg31IdentitySufficiency
    official_evidence_references: tuple[str, ...]
    known_at: datetime
    fingerprint: str

    def __post_init__(self) -> None:
        if not self.canonical_instrument_id or not self.official_evidence_references or not self.fingerprint:
            raise ValueError("NSE Reg31 reconciliation identity and official evidence are required.")
        if self.known_at.tzinfo is None or self.known_at.utcoffset() is None:
            raise ValueError("NSE Reg31 reconciliation must be point-in-time safe.")
        if self.effective_date is not None and (self.effective_date.tzinfo is None or self.effective_date.utcoffset() is None):
            raise ValueError("NSE Reg31 reconciliation effective date must be timezone-aware.")
        if tuple(sorted(set(self.official_evidence_references))) != self.official_evidence_references:
            raise ValueError("NSE Reg31 official evidence references must be canonical.")
        if self.fingerprint != reconciliation_fingerprint(
            self.canonical_instrument_id, self.current_identity, self.returned_identity,
            self.relationship, self.effective_date, self.issuer_continuity,
            self.symbol_continuity, self.security_class_continuity, self.sufficiency,
            self.official_evidence_references,
        ):
            raise ValueError("NSE Reg31 reconciliation fingerprint is invalid.")

    @property
    def acquisition_permitted(self) -> bool:
        """Only a proven predecessor may be considered by a later artifact gate.

        This is deliberately not an import permission: the caller must still
        prove that the specific current-period attachment names the current
        security.  Distinct, anomalous and unresolved source identities stay
        quarantined.
        """
        return self.relationship in {
            Reg31IdentityRelationship.CURRENT_MATCH,
            Reg31IdentityRelationship.VERIFIED_PREDECESSOR,
        } and self.sufficiency is Reg31IdentitySufficiency.SUFFICIENT


def reconciliation_fingerprint(
    canonical_instrument_id: str,
    current_identity: Reg31IdentityEvidence,
    returned_identity: Reg31IdentityEvidence,
    relationship: Reg31IdentityRelationship,
    effective_date: datetime | None,
    issuer_continuity: bool,
    symbol_continuity: bool,
    security_class_continuity: bool,
    sufficiency: Reg31IdentitySufficiency,
    official_evidence_references: tuple[str, ...],
) -> str:
    parts = (
        canonical_instrument_id, current_identity.isin, current_identity.symbol, current_identity.issuer_name,
        current_identity.security_class.value, current_identity.observed_at.isoformat(), current_identity.source_reference,
        current_identity.source_checksum, returned_identity.isin, returned_identity.symbol, returned_identity.issuer_name,
        returned_identity.security_class.value, returned_identity.observed_at.isoformat(), returned_identity.source_reference,
        returned_identity.source_checksum, relationship.value, effective_date.isoformat() if effective_date else "",
        str(issuer_continuity), str(symbol_continuity), str(security_class_continuity), sufficiency.value,
        *official_evidence_references,
    )
    return sha256("|".join(parts).encode("utf-8")).hexdigest()


def classify_reg31_identity(
    *,
    canonical_instrument_id: str,
    current_identity: Reg31IdentityEvidence,
    returned_identity: Reg31IdentityEvidence,
    known_at: datetime,
    effective_date: datetime | None = None,
    predecessor_proven: bool = False,
    official_evidence_references: tuple[str, ...],
) -> Reg31IdentityReconciliation:
    """Classify only exact, supplied official evidence; never fuzzy-match."""
    issuer_continuity = current_identity.issuer_name.casefold() == returned_identity.issuer_name.casefold()
    symbol_continuity = current_identity.symbol == returned_identity.symbol
    security_class_continuity = current_identity.security_class == returned_identity.security_class
    if current_identity.isin == returned_identity.isin:
        relationship = Reg31IdentityRelationship.CURRENT_MATCH
    elif returned_identity.security_class is Reg31SecurityClass.EQUITY_PARTLY_PAID:
        relationship = Reg31IdentityRelationship.DISTINCT_LEGACY_SECURITY
    elif predecessor_proven and issuer_continuity and symbol_continuity and security_class_continuity and effective_date is not None:
        relationship = Reg31IdentityRelationship.VERIFIED_PREDECESSOR
    elif issuer_continuity and symbol_continuity and security_class_continuity:
        relationship = Reg31IdentityRelationship.SOURCE_METADATA_ANOMALY
    else:
        relationship = Reg31IdentityRelationship.UNRESOLVED
    sufficient = (
        relationship is Reg31IdentityRelationship.CURRENT_MATCH
        or (
            relationship is Reg31IdentityRelationship.VERIFIED_PREDECESSOR
            and predecessor_proven and effective_date is not None
        )
    )
    references = tuple(sorted(set(official_evidence_references)))
    sufficiency = Reg31IdentitySufficiency.SUFFICIENT if sufficient else Reg31IdentitySufficiency.INSUFFICIENT
    fingerprint = reconciliation_fingerprint(
        canonical_instrument_id, current_identity, returned_identity, relationship, effective_date,
        issuer_continuity, symbol_continuity, security_class_continuity, sufficiency, references,
    )
    return Reg31IdentityReconciliation(
        canonical_instrument_id, current_identity, returned_identity, relationship, effective_date,
        issuer_continuity, symbol_continuity, security_class_continuity, sufficiency, references, known_at, fingerprint,
    )


class NseReg31IdentityReconciliationStore:
    """Reuse immutable core reconciliation snapshots; no new security master."""

    def __init__(self, repository: CoreApiSnapshotRepository) -> None:
        self._repository = repository

    def save(self, value: Reg31IdentityReconciliation) -> None:
        identifier = "nse-reg31-identity:" + value.fingerprint
        existing = self._repository.get_snapshot(identifier)
        if existing is not None:
            if existing.family is CoreApiSnapshotFamily.RECONCILIATION_RESULT and existing.payload == value:
                return
            raise ValueError("NSE Reg31 identity reconciliation is immutable and cannot be overwritten.")
        self._repository.save_snapshot(CoreApiSnapshot(
            identifier, CoreApiSnapshotFamily.RECONCILIATION_RESULT, "v1",
            "nse-reg31-identity-reconciliation-v1", value.fingerprint, value.known_at, value,
        ))

    def get(self, *, canonical_instrument_id: str, returned_isin: str, as_of: datetime) -> Reg31IdentityReconciliation | None:
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("NSE Reg31 identity lookup must be point-in-time safe.")
        values: list[Reg31IdentityReconciliation] = []
        offset = 0
        while True:
            page = self._repository.list_snapshots(CoreApiSnapshotFamily.RECONCILIATION_RESULT, limit=100, offset=offset)
            values.extend(
                item.payload for item in page
                if isinstance(item.payload, Reg31IdentityReconciliation)
                and item.payload.canonical_instrument_id == canonical_instrument_id
                and item.payload.returned_identity.isin == returned_isin
                and item.payload.known_at <= as_of
            )
            if len(page) < 100:
                break
            offset += len(page)
        if not values:
            return None
        return max(values, key=lambda item: (item.known_at, item.fingerprint))


__all__ = (
    "NseReg31IdentityReconciliationStore", "Reg31IdentityEvidence", "Reg31IdentityReconciliation",
    "Reg31IdentityRelationship", "Reg31IdentitySufficiency", "Reg31SecurityClass",
    "classify_reg31_identity", "reconciliation_fingerprint",
)
