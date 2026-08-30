"""Stored-only deterministic reconstruction for UnifiedIntelligenceState.

This module reads bounded artifact metadata through a strategy-agnostic source
protocol.  It neither fetches providers nor invokes research, scores, gates,
or output actions.  Canonical stores remain authoritative; the state is always
rebuildable from their as-of eligible artifact references.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.domain.models import FreshnessStatus, ObservationKind, ValidationStatus
from app.historical.guard import manifest_fingerprint
from app.intelligence.unified_state import (
    IntelligenceDependencyReference,
    IntelligenceEvidenceAvailability,
    IntelligenceEvidenceDomain,
    IntelligenceEvidenceReference,
    IntelligenceInvalidationDomain,
    IntelligenceStateCompleteness,
    UnifiedIntelligenceState,
    UnifiedIntelligenceStateError,
    create_unified_intelligence_state,
)
from app.storage.repository import MarketDataRepository


@dataclass(frozen=True, slots=True)
class StoredIntelligenceArtifact:
    """Minimal metadata projection of one already-stored canonical artifact."""

    canonical_instrument_id: str
    domain: IntelligenceEvidenceDomain
    artifact_id: str
    artifact_fingerprint: str
    availability: IntelligenceEvidenceAvailability
    evidence_as_of: datetime | None
    observed_at: datetime | None
    available_at: datetime | None
    freshness_status: FreshnessStatus
    freshness_policy_reference: str | None
    source_provenance_fingerprint: str | None
    historical_integrity_reference: str | None
    invalidation_domain: IntelligenceInvalidationDomain
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not all((self.canonical_instrument_id, self.artifact_id, self.artifact_fingerprint)):
            raise UnifiedIntelligenceStateError("UNIFIED_INTELLIGENCE_STORED_ARTIFACT_REQUIRED_FIELD")
        for name in ("evidence_as_of", "observed_at", "available_at"):
            value = getattr(self, name)
            if value is not None and (value.tzinfo is None or value.utcoffset() is None):
                raise UnifiedIntelligenceStateError("UNIFIED_INTELLIGENCE_STORED_ARTIFACT_TIMEZONE_REQUIRED")


class UnifiedIntelligenceStoredSource(Protocol):
    """Read-only composition boundary; implementations must not fetch providers."""

    def list_stored_intelligence_artifacts(
        self, canonical_instrument_id: str, *, as_of: datetime
    ) -> tuple[StoredIntelligenceArtifact, ...]: ...


class MarketDataRepositoryIntelligenceSource:
    """Direct canonical observation reader for the existing market-data repository."""

    def __init__(self, repository: MarketDataRepository) -> None:
        self._repository = repository

    def list_stored_intelligence_artifacts(
        self, canonical_instrument_id: str, *, as_of: datetime
    ) -> tuple[StoredIntelligenceArtifact, ...]:
        observations = tuple(
            observation for _, observation in self._repository.eligible_observations_as_of(as_of)
            if observation.instrument.id == canonical_instrument_id
        )
        if not observations:
            return ()
        identity = observations[0].instrument
        identity_fingerprint = manifest_fingerprint(
            instrument_id=identity.id, symbol=identity.symbol, exchange=identity.exchange, isin=identity.isin,
        )
        values: list[StoredIntelligenceArtifact] = [StoredIntelligenceArtifact(
            canonical_instrument_id=canonical_instrument_id,
            domain=IntelligenceEvidenceDomain.REFERENCE_DATA,
            artifact_id=f"canonical-instrument:{canonical_instrument_id}",
            artifact_fingerprint=identity_fingerprint,
            availability=IntelligenceEvidenceAvailability.AVAILABLE,
            evidence_as_of=as_of,
            observed_at=None,
            available_at=as_of,
            freshness_status=FreshnessStatus.UNKNOWN,
            freshness_policy_reference=None,
            source_provenance_fingerprint=None,
            historical_integrity_reference=None,
            invalidation_domain=IntelligenceInvalidationDomain.REFERENCE_DATA,
        )]
        for observation in observations:
            domain = _observation_domain(observation.kind)
            if domain is None:
                continue
            provenance = observation.provenance
            observed = provenance.market_timestamp if isinstance(provenance.market_timestamp, datetime) else None
            available = provenance.retrieved_timestamp if isinstance(provenance.retrieved_timestamp, datetime) else None
            validation = observation.validation
            freshness = validation.freshness.status if validation and validation.freshness else FreshnessStatus.UNKNOWN
            availability = IntelligenceEvidenceAvailability.STALE if validation and validation.status is ValidationStatus.STALE else IntelligenceEvidenceAvailability.AVAILABLE
            values.append(StoredIntelligenceArtifact(
                canonical_instrument_id=canonical_instrument_id,
                domain=domain,
                artifact_id=observation.id,
                artifact_fingerprint=manifest_fingerprint(
                    observation_id=observation.id, kind=str(observation.kind), instrument_id=canonical_instrument_id,
                    observed_at=None if observed is None else observed.isoformat(), available_at=None if available is None else available.isoformat(),
                    source=provenance.source,
                ),
                availability=availability,
                evidence_as_of=observed,
                observed_at=observed,
                available_at=available,
                freshness_status=freshness,
                freshness_policy_reference=None,
                source_provenance_fingerprint=manifest_fingerprint(source=provenance.source, identifier=provenance.source_identifier),
                historical_integrity_reference=None,
                invalidation_domain=_invalidation_domain(domain),
            ))
        return tuple(sorted(values, key=_artifact_key))


class UnifiedIntelligenceStateBuilder:
    """Builds a deterministic state from existing as-of eligible artifacts only."""

    def __init__(
        self,
        source: UnifiedIntelligenceStoredSource,
        *,
        state_schema_version: str = "unified-intelligence-state-v1",
        intelligence_contract_version: str = "shared-brain-v1",
    ) -> None:
        self._source = source
        self._state_schema_version = state_schema_version
        self._intelligence_contract_version = intelligence_contract_version

    def build(
        self,
        canonical_instrument_id: str,
        *,
        as_of: datetime,
        evaluation_session: datetime | None = None,
        previous_state_fingerprint: str | None = None,
    ) -> UnifiedIntelligenceState:
        if not canonical_instrument_id:
            raise UnifiedIntelligenceStateError("UNIFIED_INTELLIGENCE_STATE_CANONICAL_INSTRUMENT_REQUIRED")
        _require_aware(as_of)
        _require_aware(evaluation_session) if evaluation_session is not None else None
        source_values = self._source.list_stored_intelligence_artifacts(canonical_instrument_id, as_of=as_of)
        values = tuple(sorted(source_values, key=_artifact_key))
        if any(item.canonical_instrument_id != canonical_instrument_id for item in values):
            raise UnifiedIntelligenceStateError("UNIFIED_INTELLIGENCE_STATE_INSTRUMENT_MISMATCH")
        eligible = tuple(item for item in values if _eligible_as_of(item, as_of))
        references = tuple(_reference(domain, eligible, as_of) for domain in IntelligenceEvidenceDomain)
        identity = next(item for item in references if item.domain is IntelligenceEvidenceDomain.REFERENCE_DATA)
        if identity.availability is IntelligenceEvidenceAvailability.CONFLICTED:
            raise UnifiedIntelligenceStateError("UNIFIED_INTELLIGENCE_STATE_CANONICAL_IDENTITY_CONFLICT")
        # Reference-data may be PARTIAL because a non-core fact such as tick
        # size is unavailable.  State formation still requires at least one
        # available canonical identity/reference artifact, never a fabricated
        # reference-data aggregate.
        identity_artifacts = tuple(
            item for item in eligible
            if item.domain is IntelligenceEvidenceDomain.REFERENCE_DATA
        )
        if not any(item.availability is IntelligenceEvidenceAvailability.AVAILABLE for item in identity_artifacts):
            raise UnifiedIntelligenceStateError("UNIFIED_INTELLIGENCE_STATE_CANONICAL_IDENTITY_UNAVAILABLE")
        market = next(item for item in references if item.domain is IntelligenceEvidenceDomain.MARKET_DATA)
        if market.availability is IntelligenceEvidenceAvailability.CONFLICTED:
            raise UnifiedIntelligenceStateError("UNIFIED_INTELLIGENCE_STATE_MARKET_CONFLICT")
        degraded = tuple(reference.domain for reference in references if reference.availability is not IntelligenceEvidenceAvailability.AVAILABLE)
        dependencies = tuple(sorted({
            IntelligenceDependencyReference(item.invalidation_domain, item.artifact_id, item.artifact_fingerprint)
            for item in eligible
        }, key=lambda item: (item.invalidation_domain.value, item.artifact_id, item.artifact_fingerprint)))
        completeness = IntelligenceStateCompleteness.COMPLETE if not degraded else IntelligenceStateCompleteness.PARTIAL
        return create_unified_intelligence_state(
            canonical_instrument_id=canonical_instrument_id,
            as_of=as_of,
            evaluation_session=evaluation_session,
            state_schema_version=self._state_schema_version,
            intelligence_contract_version=self._intelligence_contract_version,
            evidence_references=references,
            completeness=completeness,
            blocking_domains=(),
            degraded_domains=degraded,
            dependency_lineage=dependencies,
            previous_state_fingerprint=previous_state_fingerprint,
        )

    def reconstruct(
        self,
        canonical_instrument_id: str,
        *,
        as_of: datetime,
        expected_state: UnifiedIntelligenceState,
    ) -> UnifiedIntelligenceState:
        """Rebuild from current stored evidence and fail closed on identity mismatch."""
        rebuilt = self.build(canonical_instrument_id, as_of=as_of, evaluation_session=expected_state.evaluation_session, previous_state_fingerprint=expected_state.previous_state_fingerprint)
        if (rebuilt.state_id, rebuilt.fingerprint) != (expected_state.state_id, expected_state.fingerprint):
            raise UnifiedIntelligenceStateError("UNIFIED_INTELLIGENCE_STATE_RECONSTRUCTION_MISMATCH")
        return rebuilt


def _reference(
    domain: IntelligenceEvidenceDomain,
    artifacts: tuple[StoredIntelligenceArtifact, ...],
    as_of: datetime,
) -> IntelligenceEvidenceReference:
    values = tuple(item for item in artifacts if item.domain is domain)
    if not values:
        return IntelligenceEvidenceReference(
            domain=domain, availability=IntelligenceEvidenceAvailability.UNAVAILABLE,
            artifact_ids=(), artifact_fingerprints=(), evidence_as_of=None, observed_at=None,
            freshness_status=FreshnessStatus.UNKNOWN, freshness_policy_reference=None,
            source_provenance_fingerprint=None, historical_integrity_reference=None,
            warnings=("NOT_YET_COMPUTED",),
        )
    availability = _availability(values)
    return IntelligenceEvidenceReference(
        domain=domain,
        availability=availability,
        artifact_ids=tuple(sorted({item.artifact_id for item in values})),
        artifact_fingerprints=tuple(sorted({item.artifact_fingerprint for item in values})),
        evidence_as_of=max((item.evidence_as_of for item in values if item.evidence_as_of is not None), default=None),
        observed_at=max((item.observed_at for item in values if item.observed_at is not None), default=None),
        freshness_status=_freshness(values),
        freshness_policy_reference=_one_or_none(item.freshness_policy_reference for item in values),
        source_provenance_fingerprint=_combined_fingerprint(item.source_provenance_fingerprint for item in values),
        historical_integrity_reference=_combined_fingerprint(item.historical_integrity_reference for item in values),
        warnings=tuple(sorted({warning for item in values for warning in item.warnings})),
    )


def _eligible_as_of(item: StoredIntelligenceArtifact, as_of: datetime) -> bool:
    return all(value is None or value <= as_of for value in (item.evidence_as_of, item.observed_at, item.available_at))


def _availability(values: tuple[StoredIntelligenceArtifact, ...]) -> IntelligenceEvidenceAvailability:
    statuses = {item.availability for item in values}
    if IntelligenceEvidenceAvailability.CONFLICTED in statuses:
        return IntelligenceEvidenceAvailability.CONFLICTED
    if IntelligenceEvidenceAvailability.STALE in statuses or any(item.freshness_status is FreshnessStatus.STALE for item in values):
        return IntelligenceEvidenceAvailability.STALE
    if IntelligenceEvidenceAvailability.PARTIAL in statuses:
        return IntelligenceEvidenceAvailability.PARTIAL
    if IntelligenceEvidenceAvailability.AVAILABLE in statuses:
        return IntelligenceEvidenceAvailability.AVAILABLE
    if IntelligenceEvidenceAvailability.NOT_APPLICABLE in statuses:
        return IntelligenceEvidenceAvailability.NOT_APPLICABLE
    return IntelligenceEvidenceAvailability.UNAVAILABLE


def _freshness(values: tuple[StoredIntelligenceArtifact, ...]) -> FreshnessStatus:
    statuses = {item.freshness_status for item in values}
    if FreshnessStatus.FUTURE in statuses:
        return FreshnessStatus.FUTURE
    if FreshnessStatus.STALE in statuses:
        return FreshnessStatus.STALE
    if FreshnessStatus.FRESH in statuses:
        return FreshnessStatus.FRESH
    return FreshnessStatus.UNKNOWN


def _one_or_none(values) -> str | None:
    non_empty = tuple(sorted({value for value in values if value is not None}))
    return non_empty[0] if len(non_empty) == 1 else None


def _combined_fingerprint(values) -> str | None:
    non_empty = tuple(sorted({value for value in values if value is not None}))
    return manifest_fingerprint(values=non_empty) if non_empty else None


def _artifact_key(item: StoredIntelligenceArtifact) -> tuple[str, str, str]:
    return (item.domain.value, item.artifact_id, item.artifact_fingerprint)


def _observation_domain(kind: object) -> IntelligenceEvidenceDomain | None:
    return {
        ObservationKind.PRICE_BAR: IntelligenceEvidenceDomain.MARKET_DATA,
        ObservationKind.VOLUME: IntelligenceEvidenceDomain.MARKET_DATA,
        ObservationKind.INDEX: IntelligenceEvidenceDomain.MARKET_DATA,
        ObservationKind.FUNDAMENTAL: IntelligenceEvidenceDomain.FUNDAMENTALS,
        ObservationKind.CORPORATE_EVENT: IntelligenceEvidenceDomain.CORPORATE_ACTIONS,
        ObservationKind.RESEARCH: IntelligenceEvidenceDomain.NEWS_CATALYSTS,
    }.get(kind)


def _invalidation_domain(domain: IntelligenceEvidenceDomain) -> IntelligenceInvalidationDomain:
    return {
        IntelligenceEvidenceDomain.MARKET_DATA: IntelligenceInvalidationDomain.PRICE,
        IntelligenceEvidenceDomain.FUNDAMENTALS: IntelligenceInvalidationDomain.FUNDAMENTALS,
        IntelligenceEvidenceDomain.EARNINGS: IntelligenceInvalidationDomain.EARNINGS,
        IntelligenceEvidenceDomain.NEWS_CATALYSTS: IntelligenceInvalidationDomain.NEWS,
        IntelligenceEvidenceDomain.MACRO: IntelligenceInvalidationDomain.MACRO,
        IntelligenceEvidenceDomain.SECTOR: IntelligenceInvalidationDomain.SECTOR,
    }.get(domain, IntelligenceInvalidationDomain.REFERENCE_DATA)


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise UnifiedIntelligenceStateError("UNIFIED_INTELLIGENCE_STATE_AS_OF_TIMEZONE_REQUIRED")
