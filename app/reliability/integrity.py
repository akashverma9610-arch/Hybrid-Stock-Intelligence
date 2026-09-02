"""Immutable, provider-neutral Reliability / Integrity observations.

The observation is deliberately a bounded projection of existing Unified
Intelligence evidence references.  It does not fetch providers, choose data,
rank sources, or turn evidence quality into an investment opinion.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from hashlib import sha256
import json

from app.domain.models import FreshnessStatus
from app.historical.guard import manifest_fingerprint
from app.intelligence.unified_state import (
    IntelligenceEvidenceAvailability,
    IntelligenceEvidenceDomain,
    IntelligenceEvidenceReference,
    IntelligenceInvalidationDomain,
    UnifiedIntelligenceState,
)
from app.intelligence.unified_state_builder import StoredIntelligenceArtifact
from app.storage.core_api_snapshot_repository import (
    CoreApiSnapshot, CoreApiSnapshotFamily, CoreApiSnapshotRepository,
)


ARTIFACT_ID = "reliability-integrity-observation"
ARTIFACT_VERSION = "v1"

# These are evidence-quality dimensions, not a decision-score input policy.
RELIABILITY_INTEGRITY_DOMAINS = (
    IntelligenceEvidenceDomain.MARKET_DATA,
    IntelligenceEvidenceDomain.TECHNICAL,
    IntelligenceEvidenceDomain.FUNDAMENTALS,
    IntelligenceEvidenceDomain.EARNINGS,
    IntelligenceEvidenceDomain.OWNERSHIP,
    IntelligenceEvidenceDomain.NEWS_CATALYSTS,
    IntelligenceEvidenceDomain.SECTOR,
    IntelligenceEvidenceDomain.MACRO,
    IntelligenceEvidenceDomain.CORPORATE_ACTIONS,
    IntelligenceEvidenceDomain.HISTORICAL_INTEGRITY,
    IntelligenceEvidenceDomain.REFERENCE_DATA,
)


class ReliabilityProvenanceState(StrEnum):
    RETAINED = "RETAINED"
    NOT_REPORTED = "NOT_REPORTED"


class ReliabilityFallbackState(StrEnum):
    NOT_REPORTED = "NOT_REPORTED"
    FALLBACK_USED = "FALLBACK_USED"
    LAST_KNOWN_GOOD = "LAST_KNOWN_GOOD"
    DEGRADED = "DEGRADED"


@dataclass(frozen=True, slots=True)
class ReliabilityIntegrityDimension:
    domain: IntelligenceEvidenceDomain
    evidence_state: IntelligenceEvidenceAvailability
    freshness_state: FreshnessStatus
    provenance_state: ReliabilityProvenanceState
    source_provenance_fingerprint: str | None
    historical_integrity_reference: str | None
    conflict_detected: bool
    fallback_state: ReliabilityFallbackState
    evidence_count: int
    pit_valid: bool
    blockers: tuple[str, ...]

    def verify(self) -> None:
        if self.evidence_count < 0:
            raise ValueError("RELIABILITY_INTEGRITY_EVIDENCE_COUNT_INVALID")
        if self.blockers != tuple(sorted(set(self.blockers))):
            raise ValueError("RELIABILITY_INTEGRITY_BLOCKERS_NONCANONICAL")
        if self.conflict_detected != (self.evidence_state is IntelligenceEvidenceAvailability.CONFLICTED):
            raise ValueError("RELIABILITY_INTEGRITY_CONFLICT_STATE_MISMATCH")
        if self.provenance_state is ReliabilityProvenanceState.RETAINED and not self.source_provenance_fingerprint:
            raise ValueError("RELIABILITY_INTEGRITY_PROVENANCE_REQUIRED")


@dataclass(frozen=True, slots=True)
class ReliabilityIntegrityObservation:
    artifact_id: str
    canonical_instrument_id: str
    contract_id: str
    contract_version: str
    intelligence_as_of: datetime
    evidence_visibility_cutoff: datetime
    known_at: datetime
    evidence_state: IntelligenceEvidenceAvailability
    freshness_state: FreshnessStatus
    source_provenance_fingerprint: str | None
    historical_integrity_reference: str | None
    conflict_detected: bool
    fallback_state: ReliabilityFallbackState
    dimensions: tuple[ReliabilityIntegrityDimension, ...]
    blockers: tuple[str, ...]
    fingerprint: str

    def verify(self) -> None:
        for value in (self.intelligence_as_of, self.evidence_visibility_cutoff, self.known_at):
            _require_aware(value)
        if self.contract_id != ARTIFACT_ID or self.contract_version != ARTIFACT_VERSION:
            raise ValueError("RELIABILITY_INTEGRITY_CONTRACT_MISMATCH")
        if self.evidence_visibility_cutoff != self.intelligence_as_of or self.known_at > self.intelligence_as_of:
            raise ValueError("RELIABILITY_INTEGRITY_PIT_INVALID")
        if tuple(item.domain for item in self.dimensions) != RELIABILITY_INTEGRITY_DOMAINS:
            raise ValueError("RELIABILITY_INTEGRITY_DIMENSIONS_NONCANONICAL")
        if self.blockers != tuple(sorted(set(self.blockers))):
            raise ValueError("RELIABILITY_INTEGRITY_BLOCKERS_NONCANONICAL")
        if self.conflict_detected != any(item.conflict_detected for item in self.dimensions):
            raise ValueError("RELIABILITY_INTEGRITY_CONFLICT_AGGREGATE_MISMATCH")
        if self.fingerprint != reliability_integrity_fingerprint(self):
            raise ValueError("RELIABILITY_INTEGRITY_FINGERPRINT_MISMATCH")
        for item in self.dimensions:
            item.verify()


def build_reliability_integrity_observation(
    state: UnifiedIntelligenceState,
) -> ReliabilityIntegrityObservation:
    """Project only pre-filtered, PIT-visible Unified State references."""
    references = {item.domain: item for item in state.evidence_references}
    dimensions = tuple(_dimension(references[domain], cutoff=state.as_of) for domain in RELIABILITY_INTEGRITY_DOMAINS)
    values = dict(
        artifact_id="",
        canonical_instrument_id=state.canonical_instrument_id,
        contract_id=ARTIFACT_ID,
        contract_version=ARTIFACT_VERSION,
        intelligence_as_of=state.as_of,
        evidence_visibility_cutoff=state.as_of,
        known_at=state.as_of,
        evidence_state=_aggregate_availability(tuple(item.evidence_state for item in dimensions)),
        freshness_state=_aggregate_freshness(tuple(item.freshness_state for item in dimensions)),
        source_provenance_fingerprint=_combined_fingerprint(
            tuple(item.source_provenance_fingerprint for item in dimensions),
        ),
        historical_integrity_reference=_combined_fingerprint(
            tuple(item.historical_integrity_reference for item in dimensions),
        ),
        conflict_detected=any(item.conflict_detected for item in dimensions),
        fallback_state=_aggregate_fallback(tuple(item.fallback_state for item in dimensions)),
        dimensions=dimensions,
        blockers=tuple(sorted({blocker for item in dimensions for blocker in item.blockers})),
    )
    provisional = ReliabilityIntegrityObservation(**values, fingerprint="")
    artifact_id = f"{ARTIFACT_ID}:{reliability_integrity_fingerprint(provisional)[7:27]}"
    value = replace(provisional, artifact_id=artifact_id)
    return replace(value, fingerprint=reliability_integrity_fingerprint(value))


class ReliabilityIntegrityObservationStore:
    """Typed append-only persistence using the existing immutable snapshot store."""

    def __init__(self, repository: CoreApiSnapshotRepository) -> None:
        self._repository = repository

    def save(self, value: ReliabilityIntegrityObservation) -> ReliabilityIntegrityObservation:
        value.verify()
        existing = self._repository.get_snapshot(value.artifact_id)
        if existing is not None:
            if existing.fingerprint != value.fingerprint or existing.payload != value:
                raise ValueError("RELIABILITY_INTEGRITY_OBSERVATION_IMMUTABILITY_CONFLICT")
            return value
        self._repository.save_snapshot(CoreApiSnapshot(
            value.artifact_id, CoreApiSnapshotFamily.RELIABILITY_INTEGRITY_OBSERVATION,
            "v1", ARTIFACT_ID, value.fingerprint, value.known_at, value,
        ))
        return value

    def list(
        self, *, canonical_instrument_id: str | None = None, as_of: datetime | None = None,
    ) -> tuple[ReliabilityIntegrityObservation, ...]:
        values: list[ReliabilityIntegrityObservation] = []
        offset = 0
        while True:
            page = self._repository.list_snapshots(
                CoreApiSnapshotFamily.RELIABILITY_INTEGRITY_OBSERVATION, limit=100, offset=offset,
            )
            for snapshot in page:
                value = snapshot.payload
                if not isinstance(value, ReliabilityIntegrityObservation):
                    raise ValueError("RELIABILITY_INTEGRITY_OBSERVATION_PAYLOAD_INVALID")
                value.verify()
                if canonical_instrument_id is not None and value.canonical_instrument_id != canonical_instrument_id:
                    continue
                if as_of is not None and (value.intelligence_as_of > as_of or value.known_at > as_of):
                    continue
                values.append(value)
            if len(page) < 100:
                break
            offset += len(page)
        return tuple(sorted(values, key=lambda item: (item.intelligence_as_of, item.artifact_id)))


class ReliabilityIntegrityEvidenceSource:
    """Read stored observations only; no recalculation or source selection occurs here."""

    def __init__(self, store: ReliabilityIntegrityObservationStore) -> None:
        self._store = store

    def list_stored_intelligence_artifacts(
        self, canonical_instrument_id: str, *, as_of: datetime,
    ) -> tuple[StoredIntelligenceArtifact, ...]:
        values = self._store.list(canonical_instrument_id=canonical_instrument_id, as_of=as_of)
        if not values:
            return ()
        value = values[-1]
        return (StoredIntelligenceArtifact(
            canonical_instrument_id=value.canonical_instrument_id,
            domain=IntelligenceEvidenceDomain.RELIABILITY,
            artifact_id=value.artifact_id,
            artifact_fingerprint=value.fingerprint,
            availability=value.evidence_state,
            evidence_as_of=value.intelligence_as_of,
            observed_at=value.intelligence_as_of,
            available_at=value.known_at,
            freshness_status=value.freshness_state,
            freshness_policy_reference=f"{value.contract_id}/{value.contract_version}",
            source_provenance_fingerprint=value.source_provenance_fingerprint,
            historical_integrity_reference=value.historical_integrity_reference,
            invalidation_domain=IntelligenceInvalidationDomain.REFERENCE_DATA,
            warnings=tuple(sorted({"RELIABILITY_INTEGRITY_V1", *value.blockers})),
        ),)


def reliability_integrity_fingerprint(value: ReliabilityIntegrityObservation) -> str:
    payload = {
        "artifact_id": value.artifact_id,
        "canonical_instrument_id": value.canonical_instrument_id,
        "contract_id": value.contract_id,
        "contract_version": value.contract_version,
        "intelligence_as_of": value.intelligence_as_of.isoformat(),
        "evidence_visibility_cutoff": value.evidence_visibility_cutoff.isoformat(),
        "known_at": value.known_at.isoformat(),
        "evidence_state": value.evidence_state.value,
        "freshness_state": value.freshness_state.value,
        "source_provenance_fingerprint": value.source_provenance_fingerprint,
        "historical_integrity_reference": value.historical_integrity_reference,
        "conflict_detected": value.conflict_detected,
        "fallback_state": value.fallback_state.value,
        "dimensions": tuple((
            item.domain.value, item.evidence_state.value, item.freshness_state.value,
            item.provenance_state.value, item.source_provenance_fingerprint,
            item.historical_integrity_reference, item.conflict_detected,
            item.fallback_state.value, item.evidence_count, item.pit_valid, item.blockers,
        ) for item in value.dimensions),
        "blockers": value.blockers,
    }
    return "sha256:" + sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _dimension(value: IntelligenceEvidenceReference, *, cutoff: datetime) -> ReliabilityIntegrityDimension:
    fallback = _fallback(value.warnings)
    blockers = set(value.warnings)
    if value.availability is not IntelligenceEvidenceAvailability.AVAILABLE:
        blockers.add(f"{value.domain.value}_{value.availability.value}")
    if value.source_provenance_fingerprint is None:
        blockers.add(f"{value.domain.value}_PROVENANCE_NOT_REPORTED")
    return ReliabilityIntegrityDimension(
        domain=value.domain,
        evidence_state=value.availability,
        freshness_state=value.freshness_status,
        provenance_state=(ReliabilityProvenanceState.RETAINED if value.source_provenance_fingerprint else ReliabilityProvenanceState.NOT_REPORTED),
        source_provenance_fingerprint=value.source_provenance_fingerprint,
        historical_integrity_reference=value.historical_integrity_reference,
        conflict_detected=value.availability is IntelligenceEvidenceAvailability.CONFLICTED,
        fallback_state=fallback,
        evidence_count=len(value.artifact_ids),
        pit_valid=all(item is None or item <= cutoff for item in (
            value.evidence_as_of, value.observed_at,
        )),
        blockers=tuple(sorted(blockers)),
    )


def _aggregate_availability(values: tuple[IntelligenceEvidenceAvailability, ...]) -> IntelligenceEvidenceAvailability:
    # Reuse the Unified State conflict/stale precedence, then keep missing
    # required-domain coverage explicit rather than allowing an unrelated
    # AVAILABLE domain to mask it.
    states = set(values)
    if IntelligenceEvidenceAvailability.CONFLICTED in states:
        return IntelligenceEvidenceAvailability.CONFLICTED
    if IntelligenceEvidenceAvailability.STALE in states:
        return IntelligenceEvidenceAvailability.STALE
    if IntelligenceEvidenceAvailability.PARTIAL in states:
        return IntelligenceEvidenceAvailability.PARTIAL
    if IntelligenceEvidenceAvailability.UNAVAILABLE in states:
        return (
            IntelligenceEvidenceAvailability.UNAVAILABLE
            if states == {IntelligenceEvidenceAvailability.UNAVAILABLE}
            else IntelligenceEvidenceAvailability.PARTIAL
        )
    if IntelligenceEvidenceAvailability.AVAILABLE in states:
        return IntelligenceEvidenceAvailability.AVAILABLE
    if IntelligenceEvidenceAvailability.NOT_APPLICABLE in states:
        return IntelligenceEvidenceAvailability.NOT_APPLICABLE
    return IntelligenceEvidenceAvailability.UNAVAILABLE


def _aggregate_freshness(values: tuple[FreshnessStatus, ...]) -> FreshnessStatus:
    states = set(values)
    if FreshnessStatus.FUTURE in states:
        return FreshnessStatus.FUTURE
    if FreshnessStatus.STALE in states:
        return FreshnessStatus.STALE
    if FreshnessStatus.FRESH in states:
        return FreshnessStatus.FRESH
    return FreshnessStatus.UNKNOWN


def _aggregate_fallback(values: tuple[ReliabilityFallbackState, ...]) -> ReliabilityFallbackState:
    # A mixed route is intentionally not ordered or collapsed into a stronger
    # claim.  Per-domain routing facts remain present in ``dimensions``.
    explicit = {item for item in values if item is not ReliabilityFallbackState.NOT_REPORTED}
    return next(iter(explicit)) if len(explicit) == 1 else ReliabilityFallbackState.NOT_REPORTED


def _fallback(warnings: tuple[str, ...]) -> ReliabilityFallbackState:
    values = set(warnings)
    if "RELIABILITY_STATUS_FALLBACK_USED" in values:
        return ReliabilityFallbackState.FALLBACK_USED
    if "RELIABILITY_STATUS_LAST_KNOWN_GOOD" in values:
        return ReliabilityFallbackState.LAST_KNOWN_GOOD
    if "RELIABILITY_STATUS_DEGRADED" in values:
        return ReliabilityFallbackState.DEGRADED
    return ReliabilityFallbackState.NOT_REPORTED


def _combined_fingerprint(values: tuple[str | None, ...]) -> str | None:
    retained = tuple(sorted({item for item in values if item is not None}))
    return manifest_fingerprint(values=retained) if retained else None


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("RELIABILITY_INTEGRITY_TIMEZONE_REQUIRED")


__all__ = (
    "ARTIFACT_ID", "ARTIFACT_VERSION", "RELIABILITY_INTEGRITY_DOMAINS",
    "ReliabilityFallbackState", "ReliabilityIntegrityDimension",
    "ReliabilityIntegrityEvidenceSource", "ReliabilityIntegrityObservation",
    "ReliabilityIntegrityObservationStore", "ReliabilityProvenanceState",
    "build_reliability_integrity_observation", "reliability_integrity_fingerprint",
)
