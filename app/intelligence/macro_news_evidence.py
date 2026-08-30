"""Stored-only macro and news/catalyst evidence adapters.

This module deliberately projects bounded metadata from already durable
artifacts.  It never fetches, classifies, scores, persists, or copies source
payloads into a :class:`UnifiedIntelligenceState`.
"""
from __future__ import annotations

from datetime import datetime
from typing import Protocol

from app.domain.models import FreshnessStatus
from app.filings.models import CorporateFiling, FilingType, PrimarySourceQuality
from app.filings.store import CorporateFilingsStore
from app.historical.guard import manifest_fingerprint
from app.intelligence.catalysts import CatalystEvent
from app.intelligence.macro import MacroEvidence, MacroState
from app.intelligence.macro.service import IntelligenceSourceTier
from app.intelligence.unified_state import (
    IntelligenceEvidenceAvailability,
    IntelligenceEvidenceDomain,
    IntelligenceInvalidationDomain,
)
from app.intelligence.unified_state_builder import StoredIntelligenceArtifact
from app.news.models import NewsArticleEvidence, NewsSourceQuality
from app.news.store import NewsEvidenceStore
from app.storage.core_api_snapshot_repository import CoreApiSnapshotFamily, CoreApiSnapshotRepository


class StoredMacroEvidenceSource(Protocol):
    """Read boundary for durable raw macro observations, when one exists."""

    def list_stored_macro_evidence(self, *, as_of: datetime) -> tuple[MacroEvidence, ...]: ...


class StoredCatalystEvidenceSource(Protocol):
    """Read boundary for durable catalyst artifacts, when one exists."""

    def list_stored_catalyst_events(
        self, canonical_instrument_id: str, *, as_of: datetime,
    ) -> tuple[CatalystEvent, ...]: ...


class MacroEvidenceAdapter:
    """Projects durable macro observations or immutable first-observed states.

    Macro is market-wide by nature.  The same underlying artifact ID is
    therefore referenced by each instrument rather than copied per company.
    """

    def __init__(
        self,
        *,
        evidence_source: StoredMacroEvidenceSource | None = None,
        snapshots: CoreApiSnapshotRepository | None = None,
    ) -> None:
        self._evidence_source = evidence_source
        self._snapshots = snapshots

    def artifacts(self, canonical_instrument_id: str, *, as_of: datetime) -> tuple[StoredIntelligenceArtifact, ...]:
        values: list[StoredIntelligenceArtifact] = []
        if self._evidence_source is not None:
            for item in self._evidence_source.list_stored_macro_evidence(as_of=as_of):
                if item.eligible_as_of(as_of):
                    values.append(_macro_evidence_artifact(canonical_instrument_id, item))
        if self._snapshots is not None:
            for snapshot in _snapshots(self._snapshots, CoreApiSnapshotFamily.MACRO_STATE):
                state = snapshot.payload
                if not isinstance(state, MacroState):
                    continue
                if _eligible_macro_state(state, created_at=snapshot.created_at, as_of=as_of):
                    values.append(_macro_state_artifact(canonical_instrument_id, state, snapshot))
        if values:
            return tuple(sorted(values, key=_artifact_key))
        warning = (
            "MACRO_DURABLE_READ_BOUNDARY_MISSING"
            if self._evidence_source is None and self._snapshots is None
            else "MACRO_EVIDENCE_UNAVAILABLE"
        )
        return (_unavailable_artifact(canonical_instrument_id, IntelligenceEvidenceDomain.MACRO, warning),)


class NewsCatalystEvidenceAdapter:
    """Projects durable disclosures, news metadata, and stored catalyst lineage."""

    def __init__(
        self,
        *,
        filings: CorporateFilingsStore | None = None,
        news: NewsEvidenceStore | None = None,
        catalyst_source: StoredCatalystEvidenceSource | None = None,
        catalyst_snapshots: CoreApiSnapshotRepository | None = None,
    ) -> None:
        self._filings = filings
        self._news = news
        self._catalyst_source = catalyst_source
        self._catalyst_snapshots = catalyst_snapshots

    def artifacts(self, canonical_instrument_id: str, *, as_of: datetime) -> tuple[StoredIntelligenceArtifact, ...]:
        values: list[StoredIntelligenceArtifact] = []
        if self._filings is not None:
            values.extend(
                _filing_artifact(item)
                for item in self._filings.list(instrument_id=canonical_instrument_id, as_of=as_of, limit=500)
                if item.filing_type is not FilingType.SHAREHOLDING_PATTERN
            )
        if self._news is not None:
            values.extend(
                _news_artifact(item, canonical_instrument_id=canonical_instrument_id)
                for item in self._news.list(instrument_id=canonical_instrument_id, as_of=as_of, limit=100)
                if canonical_instrument_id in item.instrument_ids and item.eligible_as_of(as_of)
            )
        if self._catalyst_source is not None:
            values.extend(
                _catalyst_artifact(item)
                for item in self._catalyst_source.list_stored_catalyst_events(canonical_instrument_id, as_of=as_of)
                if _eligible_catalyst(item, canonical_instrument_id, as_of)
            )
        if self._catalyst_snapshots is not None:
            for snapshot in _snapshots(self._catalyst_snapshots, CoreApiSnapshotFamily.CATALYST_EVENT):
                event = snapshot.payload
                if isinstance(event, CatalystEvent) and _eligible_catalyst(
                    event, canonical_instrument_id, as_of, created_at=snapshot.created_at,
                ):
                    values.append(_catalyst_artifact(event, snapshot_fingerprint=snapshot.fingerprint))
        if values:
            return tuple(sorted(values, key=_artifact_key))
        warning = (
            "NEWS_DURABLE_READ_BOUNDARY_MISSING"
            if all(value is None for value in (self._filings, self._news, self._catalyst_source, self._catalyst_snapshots))
            else "NEWS_EVIDENCE_UNAVAILABLE"
        )
        return (_unavailable_artifact(canonical_instrument_id, IntelligenceEvidenceDomain.NEWS_CATALYSTS, warning),)


class MacroNewsEvidenceStoredSource:
    """U14B-3D composition source; it has no persistence or provider behavior."""

    def __init__(
        self,
        *,
        macro_evidence_source: StoredMacroEvidenceSource | None = None,
        macro_snapshots: CoreApiSnapshotRepository | None = None,
        filings: CorporateFilingsStore | None = None,
        news: NewsEvidenceStore | None = None,
        catalyst_source: StoredCatalystEvidenceSource | None = None,
        catalyst_snapshots: CoreApiSnapshotRepository | None = None,
    ) -> None:
        self._adapters = (
            MacroEvidenceAdapter(evidence_source=macro_evidence_source, snapshots=macro_snapshots),
            NewsCatalystEvidenceAdapter(
                filings=filings, news=news, catalyst_source=catalyst_source,
                catalyst_snapshots=catalyst_snapshots,
            ),
        )

    def list_stored_intelligence_artifacts(
        self, canonical_instrument_id: str, *, as_of: datetime,
    ) -> tuple[StoredIntelligenceArtifact, ...]:
        return tuple(sorted(
            (artifact for adapter in self._adapters for artifact in adapter.artifacts(canonical_instrument_id, as_of=as_of)),
            key=_artifact_key,
        ))


def _macro_evidence_artifact(canonical_instrument_id: str, value: MacroEvidence) -> StoredIntelligenceArtifact:
    freshness, warnings = _freshness(value.freshness, value.warnings)
    return StoredIntelligenceArtifact(
        canonical_instrument_id=canonical_instrument_id,
        domain=IntelligenceEvidenceDomain.MACRO,
        artifact_id=f"macro-evidence:{value.evidence_id}",
        artifact_fingerprint=manifest_fingerprint(
            evidence_id=value.evidence_id, family=value.family.value, component=value.component,
            state=value.state, source_tier=value.source_tier.value, source_reference=value.source_reference,
            observed_at=value.observed_at, published_at=value.published_at, available_at=value.available_at,
            effective_at=value.effective_at, received_at=value.received_at, value=value.value,
            unit=value.unit, frequency=value.frequency.value if value.frequency else None,
            source_artifact_fingerprint=value.source_artifact_fingerprint,
            revision_of=value.revision_of, warnings=value.warnings,
        ),
        availability=_macro_availability(value.source_tier, value.warnings),
        evidence_as_of=value.effective_at or value.published_at or value.available_at,
        observed_at=value.observed_at,
        available_at=value.available_at,
        freshness_status=freshness,
        freshness_policy_reference=None,
        source_provenance_fingerprint=manifest_fingerprint(
            source_tier=value.source_tier.value, source_reference=value.source_reference, revision_of=value.revision_of,
        ),
        historical_integrity_reference=manifest_fingerprint(
            observed_at=value.observed_at, published_at=value.published_at,
            effective_at=value.effective_at, available_at=value.available_at, received_at=value.received_at,
        ),
        invalidation_domain=IntelligenceInvalidationDomain.MACRO,
        warnings=warnings,
    )


def _macro_state_artifact(canonical_instrument_id: str, value: MacroState, snapshot) -> StoredIntelligenceArtifact:
    warnings = tuple(sorted({"MACRO_DERIVED_STATE_FIRST_OBSERVED_ONLY", *value.warnings}))
    return StoredIntelligenceArtifact(
        canonical_instrument_id=canonical_instrument_id,
        domain=IntelligenceEvidenceDomain.MACRO,
        artifact_id=f"macro-state:{value.state_id}",
        artifact_fingerprint=manifest_fingerprint(
            snapshot_fingerprint=snapshot.fingerprint, state_id=value.state_id, state_as_of=value.as_of,
            evidence_ids=value.evidence_ids, version=value.version, warnings=value.warnings,
        ),
        availability=(
            IntelligenceEvidenceAvailability.CONFLICTED
            if any(item.startswith("MACRO_SOURCE_CONFLICT:") for item in value.warnings)
            else IntelligenceEvidenceAvailability.PARTIAL
        ),
        evidence_as_of=value.as_of,
        observed_at=snapshot.created_at,
        available_at=snapshot.created_at,
        freshness_status=FreshnessStatus.UNKNOWN,
        freshness_policy_reference=None,
        source_provenance_fingerprint=manifest_fingerprint(
            snapshot_id=snapshot.snapshot_id, family=snapshot.family.value, record_type=snapshot.record_type,
        ),
        historical_integrity_reference=manifest_fingerprint(state_as_of=value.as_of, first_observed_at=snapshot.created_at),
        invalidation_domain=IntelligenceInvalidationDomain.MACRO,
        warnings=warnings,
    )


def _filing_artifact(value: CorporateFiling) -> StoredIntelligenceArtifact:
    source_warning = (
        "OFFICIAL_EXCHANGE_DISCLOSURE"
        if value.source_quality is PrimarySourceQuality.PRIMARY_EXCHANGE
        else "OFFICIAL_COMPANY_DISCLOSURE"
    )
    return StoredIntelligenceArtifact(
        canonical_instrument_id=value.instrument.instrument_id,
        domain=IntelligenceEvidenceDomain.NEWS_CATALYSTS,
        artifact_id=f"exchange-disclosure:{value.filing_id}",
        artifact_fingerprint=manifest_fingerprint(
            filing_id=value.filing_id, filing_type=value.filing_type.value, source=value.source,
            source_quality=value.source_quality.value, announced_at=value.announced_at, received_at=value.received_at,
            source_reference=value.source_reference, document_reference=value.document_reference,
            revision_of=value.revision_of_filing_id, reporting_as_of=value.reporting_as_of, warnings=value.warnings,
        ),
        availability=_conflicted_or(IntelligenceEvidenceAvailability.AVAILABLE, value.warnings),
        evidence_as_of=value.announced_at,
        observed_at=value.announced_at,
        available_at=value.received_at,
        freshness_status=FreshnessStatus.UNKNOWN,
        freshness_policy_reference=None,
        source_provenance_fingerprint=manifest_fingerprint(
            source=value.source, source_quality=value.source_quality.value,
            source_reference=value.source_reference, document_reference=value.document_reference,
        ),
        historical_integrity_reference=manifest_fingerprint(
            announced_at=value.announced_at, first_observed_at=value.received_at,
            revision_of=value.revision_of_filing_id,
        ),
        invalidation_domain=IntelligenceInvalidationDomain.NEWS,
        warnings=tuple(sorted({source_warning, *value.warnings})),
    )


def _news_artifact(
    value: NewsArticleEvidence, *, canonical_instrument_id: str,
) -> StoredIntelligenceArtifact:
    availability = _conflicted_or(_news_availability(value.source_quality), value.warnings)
    warning = _news_authority_warning(value.source_quality)
    return StoredIntelligenceArtifact(
        canonical_instrument_id=canonical_instrument_id,
        domain=IntelligenceEvidenceDomain.NEWS_CATALYSTS,
        artifact_id=f"news-evidence:{value.article_id}",
        artifact_fingerprint=manifest_fingerprint(
            article_id=value.article_id, provider=value.source_provider, source_quality=value.source_quality.value,
            published_at=value.published_at, received_at=value.received_at, linked_filing_id=value.linked_filing_id,
            event_category=value.event_category.value, provenance=value.provenance, warnings=value.warnings,
        ),
        availability=availability,
        evidence_as_of=value.published_at,
        observed_at=value.published_at,
        available_at=value.received_at,
        freshness_status=FreshnessStatus.UNKNOWN,
        freshness_policy_reference=None,
        source_provenance_fingerprint=manifest_fingerprint(
            provider=value.source_provider, source_reference=value.provenance.source_reference,
            source_quality=value.source_quality.value,
        ),
        historical_integrity_reference=manifest_fingerprint(
            published_at=value.published_at, first_observed_at=value.received_at,
        ),
        invalidation_domain=IntelligenceInvalidationDomain.NEWS,
        warnings=tuple(sorted({warning, *value.match_warnings, *value.warnings})),
    )


def _catalyst_artifact(value: CatalystEvent, *, snapshot_fingerprint: str | None = None) -> StoredIntelligenceArtifact:
    warning = _news_authority_warning(value.source_quality)
    return StoredIntelligenceArtifact(
        canonical_instrument_id=value.company_id or "",
        domain=IntelligenceEvidenceDomain.NEWS_CATALYSTS,
        artifact_id=f"catalyst-event:{value.event_id}",
        artifact_fingerprint=manifest_fingerprint(
            snapshot_fingerprint=snapshot_fingerprint, event_id=value.event_id, event_type=value.event_type.value,
            company_id=value.company_id, sector=value.sector, event_date=value.event_date,
            publication_date=value.publication_date, retrieved_at=value.retrieved_at,
            source_quality=value.source_quality.value, primary_source_confirmation=value.primary_source_confirmation,
            exchange_filing_match=value.exchange_filing_match, expected_financial_impact=value.expected_financial_impact,
            expected_time_horizon=value.expected_time_horizon, already_priced_in=value.already_priced_in.value,
            cluster_id=value.cluster_id, evidence_ids=value.evidence_ids, warnings=value.warnings,
        ),
        availability=_conflicted_or(_news_availability(value.source_quality), value.warnings),
        evidence_as_of=value.publication_date,
        observed_at=value.publication_date,
        available_at=value.retrieved_at,
        freshness_status=FreshnessStatus.UNKNOWN,
        freshness_policy_reference=None,
        source_provenance_fingerprint=manifest_fingerprint(
            source_quality=value.source_quality.value, primary_source_confirmation=value.primary_source_confirmation,
            exchange_filing_match=value.exchange_filing_match,
        ),
        historical_integrity_reference=manifest_fingerprint(
            event_date=value.event_date, publication_date=value.publication_date, first_observed_at=value.retrieved_at,
        ),
        invalidation_domain=IntelligenceInvalidationDomain.NEWS,
        warnings=tuple(sorted({"STORED_CATALYST_ARTIFACT", warning, *value.warnings})),
    )


def _unavailable_artifact(
    canonical_instrument_id: str, domain: IntelligenceEvidenceDomain, warning: str,
) -> StoredIntelligenceArtifact:
    return StoredIntelligenceArtifact(
        canonical_instrument_id=canonical_instrument_id,
        domain=domain,
        artifact_id=f"{domain.value.lower()}:unavailable",
        artifact_fingerprint=manifest_fingerprint(domain=domain.value, warning=warning),
        availability=IntelligenceEvidenceAvailability.UNAVAILABLE,
        evidence_as_of=None,
        observed_at=None,
        available_at=None,
        freshness_status=FreshnessStatus.UNKNOWN,
        freshness_policy_reference=None,
        source_provenance_fingerprint=None,
        historical_integrity_reference=None,
        invalidation_domain=(
            IntelligenceInvalidationDomain.MACRO
            if domain is IntelligenceEvidenceDomain.MACRO
            else IntelligenceInvalidationDomain.NEWS
        ),
        warnings=(warning,),
    )


def _eligible_macro_state(value: MacroState, *, created_at: datetime, as_of: datetime) -> bool:
    return _aware(value.as_of) and _aware(created_at) and value.as_of <= as_of and created_at <= as_of


def _eligible_catalyst(
    value: CatalystEvent,
    canonical_instrument_id: str,
    as_of: datetime,
    *,
    created_at: datetime | None = None,
) -> bool:
    times = (value.event_date, value.publication_date, value.retrieved_at, created_at)
    return (
        value.company_id == canonical_instrument_id
        and all(item is None or (_aware(item) and item <= as_of) for item in times)
    )


def _snapshots(repository: CoreApiSnapshotRepository, family: CoreApiSnapshotFamily):
    offset = 0
    while True:
        page = repository.list_snapshots(family, limit=100, offset=offset)
        yield from page
        if len(page) < 100:
            return
        offset += len(page)


def _macro_availability(tier: IntelligenceSourceTier, warnings: tuple[str, ...]) -> IntelligenceEvidenceAvailability:
    base = (
        IntelligenceEvidenceAvailability.AVAILABLE
        if tier in {IntelligenceSourceTier.OFFICIAL, IntelligenceSourceTier.PRIMARY}
        else IntelligenceEvidenceAvailability.PARTIAL
    )
    return _conflicted_or(base, warnings)


def _news_availability(quality: NewsSourceQuality) -> IntelligenceEvidenceAvailability:
    return (
        IntelligenceEvidenceAvailability.AVAILABLE
        if quality in {NewsSourceQuality.PRIMARY_EXCHANGE, NewsSourceQuality.PRIMARY_ISSUER}
        else IntelligenceEvidenceAvailability.PARTIAL
    )


def _news_authority_warning(quality: NewsSourceQuality) -> str:
    return {
        NewsSourceQuality.PRIMARY_EXCHANGE: "OFFICIAL_EXCHANGE_DISCLOSURE",
        NewsSourceQuality.PRIMARY_ISSUER: "OFFICIAL_COMPANY_DISCLOSURE",
        NewsSourceQuality.REPUTABLE_NEWS: "SECONDARY_RESEARCH_EVIDENCE",
        NewsSourceQuality.SECONDARY_RESEARCH: "SECONDARY_RESEARCH_EVIDENCE",
        NewsSourceQuality.UNKNOWN: "SECONDARY_OR_UNKNOWN_NEWS_EVIDENCE",
    }[quality]


def _conflicted_or(
    availability: IntelligenceEvidenceAvailability, warnings: tuple[str, ...],
) -> IntelligenceEvidenceAvailability:
    return IntelligenceEvidenceAvailability.CONFLICTED if "CONFLICTED" in warnings else availability


def _freshness(value: str, warnings: tuple[str, ...]) -> tuple[FreshnessStatus, tuple[str, ...]]:
    try:
        return FreshnessStatus(value.lower()), tuple(sorted(set(warnings)))
    except ValueError:
        return FreshnessStatus.UNKNOWN, tuple(sorted({"MACRO_FRESHNESS_UNRECOGNIZED", *warnings}))


def _aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


def _artifact_key(value: StoredIntelligenceArtifact) -> tuple[str, str, str]:
    return value.domain.value, value.artifact_id, value.artifact_fingerprint


__all__ = (
    "MacroEvidenceAdapter", "MacroNewsEvidenceStoredSource", "NewsCatalystEvidenceAdapter",
    "StoredCatalystEvidenceSource", "StoredMacroEvidenceSource",
)
