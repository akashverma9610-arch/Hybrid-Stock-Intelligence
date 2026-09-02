"""Stored-only non-company evidence adapters for unified intelligence state.

Only existing PIT-safe stores are read here.  Current-only sector rotation,
non-durable technical materialization, and reliability decisions without a
durable instrument/as-of read contract deliberately remain outside this slice.
"""
from __future__ import annotations

from datetime import datetime
from typing import Protocol

from app.domain.models import FreshnessStatus
from app.historical.guard import manifest_fingerprint
from app.historical.security_master import HistoricalIntegrityStatus, HistoricalPriceIntegrity, HistoricalSecurityIdentity, HistoricalSecurityMasterStore
from app.market_data.current_sector_rotation import CurrentSectorRankingStore
from app.intelligence.unified_state import IntelligenceEvidenceAvailability, IntelligenceEvidenceDomain, IntelligenceInvalidationDomain
from app.intelligence.unified_state_builder import StoredIntelligenceArtifact, UnifiedIntelligenceStoredSource
from app.market_data.reference_data.resolver import TickSizeReferenceResolver, TickSizeResolutionStatus
from app.reliability.models import ReliabilityStatus, StoredReliabilityDecision
from app.taxonomy.models import ClassificationSourceStatus, InstrumentTaxonomyClassification
from app.taxonomy.service import TaxonomySnapshotStore


class SectorAndReferenceEvidenceAdapter:
    """Reads only immutable taxonomy classifications eligible at ``as_of``."""

    def __init__(self, taxonomy: TaxonomySnapshotStore, rankings: CurrentSectorRankingStore | None = None) -> None:
        self._taxonomy, self._rankings = taxonomy, rankings

    def artifacts(self, canonical_instrument_id: str, *, as_of: datetime) -> tuple[StoredIntelligenceArtifact, ...]:
        classification = self._taxonomy.classification_as_of(canonical_instrument_id, as_of)
        if classification is None:
            return ()
        reference = _taxonomy_artifact(classification, IntelligenceEvidenceDomain.REFERENCE_DATA)
        sector = (
            _taxonomy_artifact(classification, IntelligenceEvidenceDomain.SECTOR)
            if self._rankings is None else _sector_ranking_artifact(classification, self._rankings, as_of=as_of)
        )
        return sector, reference


class HistoricalReferenceAndIntegrityEvidenceAdapter:
    """Reads historical identity intervals and already-stored integrity results."""

    def __init__(self, store: HistoricalSecurityMasterStore) -> None:
        self._store = store

    def artifacts(self, canonical_instrument_id: str, *, as_of: datetime) -> tuple[StoredIntelligenceArtifact, ...]:
        identities = tuple(value for value in self._store.identities_as_of(as_of) if value.canonical_instrument_id == canonical_instrument_id)
        integrity = self._store.integrities_as_of(canonical_instrument_id, as_of)
        return tuple(sorted(
            (*(_identity_artifact(value) for value in identities), *(_integrity_artifact(value) for value in integrity)),
            key=_artifact_key,
        ))


class TickReferenceEvidenceAdapter:
    """Projects an existing pure tick resolver result; it never infers a tick size."""

    def __init__(self, resolver: TickSizeReferenceResolver) -> None:
        self._resolver = resolver

    def artifacts(self, canonical_instrument_id: str, *, as_of: datetime) -> tuple[StoredIntelligenceArtifact, ...]:
        result = self._resolver.resolve_tick_size(canonical_instrument_id, as_of=as_of)
        if result.status is TickSizeResolutionStatus.TICK_SIZE_UNAVAILABLE_FOR_AS_OF:
            # Explicitly retain the unavailable reference fact without inventing a tick.
            return (StoredIntelligenceArtifact(
                canonical_instrument_id=canonical_instrument_id,
                domain=IntelligenceEvidenceDomain.REFERENCE_DATA,
                artifact_id="tick-resolution:unavailable",
                artifact_fingerprint=manifest_fingerprint(status=result.status.value, as_of=as_of, warnings=result.warnings),
                availability=IntelligenceEvidenceAvailability.PARTIAL,
                evidence_as_of=None,
                observed_at=None,
                available_at=None,
                freshness_status=FreshnessStatus.UNKNOWN,
                freshness_policy_reference=None,
                source_provenance_fingerprint=None,
                historical_integrity_reference=None,
                invalidation_domain=IntelligenceInvalidationDomain.REFERENCE_DATA,
                warnings=tuple(sorted({result.status.value, *result.warnings})),
            ),)
        availability = (
            IntelligenceEvidenceAvailability.AVAILABLE if result.status is TickSizeResolutionStatus.AVAILABLE
            else IntelligenceEvidenceAvailability.CONFLICTED
        )
        identifiers = tuple(sorted({*result.eligible_official_record_ids, *result.eligible_licensed_record_ids, *result.conflicting_record_ids}))
        return (StoredIntelligenceArtifact(
            canonical_instrument_id=canonical_instrument_id,
            domain=IntelligenceEvidenceDomain.REFERENCE_DATA,
            artifact_id="tick-resolution:" + (result.selected_record_id or "conflict:" + ",".join(identifiers)),
            artifact_fingerprint=manifest_fingerprint(
                status=result.status.value, as_of=as_of, selected_record_id=result.selected_record_id,
                record_ids=identifiers, tick_size=None if result.tick_size is None else str(result.tick_size),
                selected_source_class=None if result.selected_source_class is None else result.selected_source_class.value,
                selected_source_name=result.selected_source_name, warnings=result.warnings,
            ),
            availability=availability,
            evidence_as_of=as_of,
            observed_at=as_of,
            available_at=as_of,
            freshness_status=FreshnessStatus.UNKNOWN,
            freshness_policy_reference=None,
            source_provenance_fingerprint=manifest_fingerprint(record_ids=identifiers, selected_source_name=result.selected_source_name),
            historical_integrity_reference=manifest_fingerprint(status=result.status.value, as_of=as_of),
            invalidation_domain=IntelligenceInvalidationDomain.REFERENCE_DATA,
            warnings=tuple(sorted({result.status.value, *result.warnings})),
        ),)


class ReliabilityDecisionStoredSource(Protocol):
    def list_stored_reliability_decisions(
        self, canonical_instrument_id: str, *, as_of: datetime
    ) -> tuple[StoredReliabilityDecision, ...]: ...


class ReliabilityEvidenceAdapter:
    """Projects stored reliability decisions without recomputing source routing."""

    def __init__(self, source: ReliabilityDecisionStoredSource) -> None:
        self._source = source

    def artifacts(self, canonical_instrument_id: str, *, as_of: datetime) -> tuple[StoredIntelligenceArtifact, ...]:
        values = tuple(value for value in self._source.list_stored_reliability_decisions(canonical_instrument_id, as_of=as_of)
                       if value.canonical_instrument_id == canonical_instrument_id and value.observed_at <= as_of and value.available_at <= as_of)
        return tuple(sorted((_reliability_artifact(value) for value in values), key=_artifact_key))


class ReliabilityRepositoryStoredSource:
    """Repository adapter: stored decisions only, never reliability routing."""

    def __init__(self, repository) -> None:
        self._repository = repository

    def list_stored_reliability_decisions(
        self, canonical_instrument_id: str, *, as_of: datetime,
    ) -> tuple[StoredReliabilityDecision, ...]:
        return tuple(value for value in self._repository.list_reliability_decisions(
            canonical_instrument_id=canonical_instrument_id,
        ) if value.evaluation_as_of is not None and value.evaluation_as_of <= as_of)


class ReliabilityIntegrityStoredSource(Protocol):
    def list_stored_intelligence_artifacts(
        self, canonical_instrument_id: str, *, as_of: datetime,
    ) -> tuple[StoredIntelligenceArtifact, ...]: ...


class ReliabilityIntegrityEvidenceAdapter:
    """Pass through one immutable Reliability / Integrity artifact source."""

    def __init__(self, source: ReliabilityIntegrityStoredSource) -> None:
        self._source = source

    def artifacts(self, canonical_instrument_id: str, *, as_of: datetime) -> tuple[StoredIntelligenceArtifact, ...]:
        return self._source.list_stored_intelligence_artifacts(canonical_instrument_id, as_of=as_of)


class NonCompanyEvidenceStoredSource:
    """Composes the U14B-3B adapters through the existing stored-source protocol."""

    def __init__(
        self,
        *,
        taxonomy: TaxonomySnapshotStore | None = None,
        sector_rankings: CurrentSectorRankingStore | None = None,
        historical_security_master: HistoricalSecurityMasterStore | None = None,
        tick_resolver: TickSizeReferenceResolver | None = None,
        reliability_source: ReliabilityDecisionStoredSource | None = None,
        reliability_integrity_source: ReliabilityIntegrityStoredSource | None = None,
    ) -> None:
        self._adapters = tuple(adapter for adapter in (
            SectorAndReferenceEvidenceAdapter(taxonomy, sector_rankings) if taxonomy is not None else None,
            HistoricalReferenceAndIntegrityEvidenceAdapter(historical_security_master) if historical_security_master is not None else None,
            TickReferenceEvidenceAdapter(tick_resolver) if tick_resolver is not None else None,
            ReliabilityEvidenceAdapter(reliability_source) if reliability_source is not None else None,
            ReliabilityIntegrityEvidenceAdapter(reliability_integrity_source) if reliability_integrity_source is not None else None,
        ) if adapter is not None)

    def list_stored_intelligence_artifacts(self, canonical_instrument_id: str, *, as_of: datetime) -> tuple[StoredIntelligenceArtifact, ...]:
        values = tuple(artifact for adapter in self._adapters for artifact in adapter.artifacts(canonical_instrument_id, as_of=as_of))
        return tuple(sorted(values, key=_artifact_key))


def _taxonomy_artifact(value: InstrumentTaxonomyClassification, domain: IntelligenceEvidenceDomain) -> StoredIntelligenceArtifact:
    availability = IntelligenceEvidenceAvailability.AVAILABLE if value.source_type in {ClassificationSourceStatus.OFFICIAL, ClassificationSourceStatus.PRIMARY_SOURCE_DERIVED, ClassificationSourceStatus.MANUALLY_REVIEWED} else IntelligenceEvidenceAvailability.PARTIAL
    sector_warning = ("SECTOR_ROTATION_DERIVED_READ_BOUNDARY_UNAVAILABLE",) if domain is IntelligenceEvidenceDomain.SECTOR else ()
    warnings = tuple(sorted({*value.warnings, *sector_warning, *( () if availability is IntelligenceEvidenceAvailability.AVAILABLE else ("TAXONOMY_SECONDARY_OR_UNKNOWN",) )}))
    return StoredIntelligenceArtifact(
        canonical_instrument_id=value.instrument_id,
        domain=domain,
        artifact_id=f"taxonomy:{value.classification_id}",
        artifact_fingerprint=manifest_fingerprint(
            classification_id=value.classification_id, source=value.source, source_type=value.source_type.value,
            effective_from=value.effective_from, effective_to=value.effective_to, classification_as_of=value.as_of,
            version=value.classification_version, source_reference=value.source_reference, source_sha256=value.source_sha256,
        ),
        availability=availability,
        evidence_as_of=value.as_of,
        observed_at=value.as_of,
        available_at=value.as_of,
        freshness_status=FreshnessStatus.UNKNOWN,
        freshness_policy_reference=None,
        source_provenance_fingerprint=manifest_fingerprint(source=value.source, source_reference=value.source_reference, source_sha256=value.source_sha256),
        historical_integrity_reference=manifest_fingerprint(effective_from=value.effective_from, effective_to=value.effective_to, classification_as_of=value.as_of),
        invalidation_domain=IntelligenceInvalidationDomain.SECTOR if domain is IntelligenceEvidenceDomain.SECTOR else IntelligenceInvalidationDomain.REFERENCE_DATA,
        warnings=warnings,
    )


def _sector_ranking_artifact(
    classification: InstrumentTaxonomyClassification, rankings: CurrentSectorRankingStore, *, as_of: datetime,
) -> StoredIntelligenceArtifact:
    """Project a stored ranking only; no RS, breadth, or Top-3 calculation lives here."""
    ranking = rankings.latest(as_of=as_of)
    if ranking is None:
        return StoredIntelligenceArtifact(
            canonical_instrument_id=classification.instrument_id, domain=IntelligenceEvidenceDomain.SECTOR,
            artifact_id=f"taxonomy:{classification.classification_id}:sector-ranking-unavailable",
            artifact_fingerprint=manifest_fingerprint(classification_id=classification.classification_id, status="CURRENT_SECTOR_RANKING_UNAVAILABLE"),
            availability=IntelligenceEvidenceAvailability.PARTIAL, evidence_as_of=classification.as_of,
            observed_at=classification.as_of, available_at=classification.as_of,
            freshness_status=FreshnessStatus.UNKNOWN, freshness_policy_reference=None,
            source_provenance_fingerprint=manifest_fingerprint(source=classification.source, source_reference=classification.source_reference),
            historical_integrity_reference=None, invalidation_domain=IntelligenceInvalidationDomain.SECTOR,
            warnings=("SECTOR_RANKING_UNAVAILABLE", "CURRENT_SECTOR_RANKING_NOT_MATERIALIZED"),
        )
    rs = next((item for item in ranking.report.relative_strength if item.sector == classification.sector), None)
    breadth = next((item for item in ranking.report.breadth if item.sector == classification.sector), None)
    rank = (ranking.report.ranked_sectors.index(classification.sector) + 1) if classification.sector in ranking.report.ranked_sectors else None
    sufficient = rs is not None and rs.exclusion_reason is None and breadth is not None and breadth.status == "READY" and rank is not None
    warnings = [f"SECTOR_RANKING_ID:{ranking.ranking_id}", f"SECTOR_RANKING_POLICY:{ranking.ranking_policy_version}"]
    if sufficient:
        warnings.extend((f"SECTOR_RANK:{rank}", "SECTOR_TOP3" if classification.sector in ranking.report.top3 else "SECTOR_NOT_TOP3"))
        availability = IntelligenceEvidenceAvailability.AVAILABLE
    else:
        availability = IntelligenceEvidenceAvailability.PARTIAL
        warnings.append("SECTOR_RANKING_UNAVAILABLE")
        if rs is None or rs.exclusion_reason is not None:
            warnings.append("SECTOR_RS_INSUFFICIENT")
        if breadth is None:
            warnings.append("SECTOR_BREADTH_UNAVAILABLE")
        elif breadth.status != "READY":
            warnings.extend((f"SECTOR_BREADTH_{breadth.status}", f"SECTOR_BREADTH_COVERAGE_{breadth.coverage_pct}"))
    return StoredIntelligenceArtifact(
        canonical_instrument_id=classification.instrument_id, domain=IntelligenceEvidenceDomain.SECTOR,
        artifact_id=f"sector-ranking:{ranking.ranking_id}:{classification.classification_id}",
        artifact_fingerprint=manifest_fingerprint(
            ranking_id=ranking.ranking_id, ranking_fingerprint=ranking.fingerprint,
            classification_id=classification.classification_id, sector=classification.sector, rank=rank,
            top3=classification.sector in ranking.report.top3,
            breadth_status=None if breadth is None else breadth.status,
            rs_exclusion=None if rs is None else rs.exclusion_reason,
        ),
        availability=availability, evidence_as_of=ranking.ranking_as_of,
        observed_at=ranking.latest_completed_session, available_at=ranking.ranking_as_of,
        freshness_status=FreshnessStatus.UNKNOWN, freshness_policy_reference=ranking.ranking_policy_version,
        source_provenance_fingerprint=manifest_fingerprint(
            ranking_id=ranking.ranking_id, ranking_fingerprint=ranking.fingerprint,
            benchmark_identity=ranking.benchmark_identity, taxonomy_source=classification.source,
        ),
        historical_integrity_reference=manifest_fingerprint(
            latest_completed_session=ranking.latest_completed_session,
            ranking_policy_version=ranking.ranking_policy_version,
        ),
        invalidation_domain=IntelligenceInvalidationDomain.SECTOR,
        warnings=tuple(sorted(set(warnings))),
    )


def _identity_artifact(value: HistoricalSecurityIdentity) -> StoredIntelligenceArtifact:
    return StoredIntelligenceArtifact(
        canonical_instrument_id=value.canonical_instrument_id,
        domain=IntelligenceEvidenceDomain.REFERENCE_DATA,
        artifact_id=f"historical-security:{value.identity_id}",
        artifact_fingerprint=manifest_fingerprint(
            identity_id=value.identity_id, isin=value.isin, exchange=value.exchange, symbol=value.symbol,
            effective_from=value.symbol_effective_from, effective_to=value.symbol_effective_to,
            identity_as_of=value.as_of, version=value.version, source=value.source,
        ),
        availability=IntelligenceEvidenceAvailability.AVAILABLE,
        evidence_as_of=value.as_of,
        observed_at=value.as_of,
        available_at=value.as_of,
        freshness_status=FreshnessStatus.UNKNOWN,
        freshness_policy_reference=None,
        source_provenance_fingerprint=manifest_fingerprint(source=value.source, source_reference=value.source_reference),
        historical_integrity_reference=manifest_fingerprint(listed_from=value.listed_from, listed_until=value.listed_until, effective_from=value.symbol_effective_from, effective_to=value.symbol_effective_to),
        invalidation_domain=IntelligenceInvalidationDomain.REFERENCE_DATA,
        warnings=value.warnings,
    )


def _integrity_artifact(value: HistoricalPriceIntegrity) -> StoredIntelligenceArtifact:
    availability = {
        HistoricalIntegrityStatus.VALID: IntelligenceEvidenceAvailability.AVAILABLE,
        HistoricalIntegrityStatus.PARTIAL: IntelligenceEvidenceAvailability.PARTIAL,
        HistoricalIntegrityStatus.INVALID: IntelligenceEvidenceAvailability.CONFLICTED,
        HistoricalIntegrityStatus.UNAVAILABLE: IntelligenceEvidenceAvailability.UNAVAILABLE,
    }[value.status]
    return StoredIntelligenceArtifact(
        canonical_instrument_id=value.instrument_id,
        domain=IntelligenceEvidenceDomain.HISTORICAL_INTEGRITY,
        artifact_id=f"historical-integrity:{value.assessment_id}",
        artifact_fingerprint=manifest_fingerprint(
            assessment_id=value.assessment_id, integrity_as_of=value.as_of, status=value.status.value,
            basis=value.basis.value, bar_ids=value.bar_ids, action_ids=value.action_ids, warnings=value.warnings,
        ),
        availability=availability,
        evidence_as_of=value.as_of,
        observed_at=value.as_of,
        available_at=value.as_of,
        freshness_status=FreshnessStatus.UNKNOWN,
        freshness_policy_reference=None,
        source_provenance_fingerprint=manifest_fingerprint(assessment_id=value.assessment_id, basis=value.basis.value),
        historical_integrity_reference=manifest_fingerprint(status=value.status.value, bar_ids=value.bar_ids, action_ids=value.action_ids),
        invalidation_domain=IntelligenceInvalidationDomain.REFERENCE_DATA,
        warnings=value.warnings,
    )


def _reliability_artifact(value: StoredReliabilityDecision) -> StoredIntelligenceArtifact:
    status = value.decision.availability.status
    availability = {
        ReliabilityStatus.READY: IntelligenceEvidenceAvailability.AVAILABLE,
        ReliabilityStatus.STALE: IntelligenceEvidenceAvailability.STALE,
        ReliabilityStatus.CONFLICTED: IntelligenceEvidenceAvailability.CONFLICTED,
        ReliabilityStatus.UNAVAILABLE: IntelligenceEvidenceAvailability.UNAVAILABLE,
        ReliabilityStatus.PRIMARY_UNAVAILABLE: IntelligenceEvidenceAvailability.UNAVAILABLE,
        ReliabilityStatus.DEGRADED: IntelligenceEvidenceAvailability.PARTIAL,
        ReliabilityStatus.FALLBACK_USED: IntelligenceEvidenceAvailability.PARTIAL,
        ReliabilityStatus.LAST_KNOWN_GOOD: IntelligenceEvidenceAvailability.PARTIAL,
    }[status]
    return StoredIntelligenceArtifact(
        canonical_instrument_id=value.canonical_instrument_id,
        domain=IntelligenceEvidenceDomain.RELIABILITY,
        artifact_id=f"reliability:{value.decision_id}",
        artifact_fingerprint=manifest_fingerprint(
            envelope_fingerprint=value.fingerprint, family=value.decision.family.value,
            status=status.value, selected_source=value.decision.selected_source_id,
            selected_tier=value.decision.selected_tier, fallback=value.decision.fallback_used,
            lkg=value.decision.last_known_good_used, conflict=value.decision.conflict_detected,
            warnings=value.decision.warnings, observed_at=value.observed_at, available_at=value.available_at,
        ),
        availability=availability,
        evidence_as_of=value.available_at,
        observed_at=value.observed_at,
        available_at=value.available_at,
        freshness_status=FreshnessStatus.STALE if status in {ReliabilityStatus.STALE, ReliabilityStatus.LAST_KNOWN_GOOD} else FreshnessStatus.UNKNOWN,
        freshness_policy_reference=None,
        source_provenance_fingerprint=manifest_fingerprint(family=value.decision.family.value, source=value.decision.selected_source_id, tier=value.decision.selected_tier),
        historical_integrity_reference=None,
        invalidation_domain=IntelligenceInvalidationDomain.REFERENCE_DATA,
        warnings=tuple(sorted({f"RELIABILITY_STATUS_{status.value}", *value.decision.warnings})),
    )


def _artifact_key(value: StoredIntelligenceArtifact) -> tuple[str, str, str]:
    return value.domain.value, value.artifact_id, value.artifact_fingerprint


__all__ = (
    "HistoricalReferenceAndIntegrityEvidenceAdapter", "NonCompanyEvidenceStoredSource",
    "ReliabilityEvidenceAdapter", "ReliabilityDecisionStoredSource", "ReliabilityIntegrityEvidenceAdapter", "ReliabilityIntegrityStoredSource", "ReliabilityRepositoryStoredSource", "SectorAndReferenceEvidenceAdapter",
    "StoredReliabilityDecision", "TickReferenceEvidenceAdapter",
)
