"""Stored-only company-evidence adapters for unified intelligence state.

The adapters intentionally project only immutable metadata from existing
canonical stores.  They do not retrieve providers, calculate company metrics,
or copy financial/action/shareholding payloads into the state projection.
"""
from __future__ import annotations

from datetime import datetime
from typing import Protocol

from app.domain.models import FreshnessStatus
from app.filings.models import CorporateFiling, FilingType, PrimarySourceQuality
from app.filings.store import CorporateFilingsStore
from app.fundamentals.models import FinancialFact, FinancialMetric
from app.fundamentals.store import FinancialFactStore
from app.historical.guard import manifest_fingerprint
from app.historical.security_master import HistoricalCorporateAction, HistoricalSecurityMasterStore
from app.intelligence.unified_state import (
    IntelligenceEvidenceAvailability,
    IntelligenceEvidenceDomain,
    IntelligenceInvalidationDomain,
)
from app.intelligence.unified_state_builder import StoredIntelligenceArtifact, UnifiedIntelligenceStoredSource


class CompanyEvidenceAdapter(Protocol):
    """Narrow stored-only adapter boundary for one company evidence family."""

    def artifacts(self, canonical_instrument_id: str, *, as_of: datetime) -> tuple[StoredIntelligenceArtifact, ...]: ...


class CompositeStoredIntelligenceSource:
    """Combines independently safe stored sources without changing builder semantics."""

    def __init__(self, *sources: UnifiedIntelligenceStoredSource) -> None:
        self._sources = tuple(sources)

    def list_stored_intelligence_artifacts(
        self, canonical_instrument_id: str, *, as_of: datetime
    ) -> tuple[StoredIntelligenceArtifact, ...]:
        values = tuple(
            artifact
            for source in self._sources
            for artifact in source.list_stored_intelligence_artifacts(canonical_instrument_id, as_of=as_of)
        )
        return tuple(sorted(values, key=lambda item: (item.domain.value, item.artifact_id, item.artifact_fingerprint)))


class FinancialFactsEvidenceAdapter:
    """Projects canonical financial-fact lineage into FUNDAMENTALS/EARNINGS."""

    def __init__(self, store: FinancialFactStore) -> None:
        self._store = store

    def artifacts(self, canonical_instrument_id: str, *, as_of: datetime) -> tuple[StoredIntelligenceArtifact, ...]:
        facts = self._store.facts(canonical_instrument_id, as_of=as_of, limit=500)
        values: list[StoredIntelligenceArtifact] = []
        for fact in facts:
            values.append(_financial_artifact(fact, IntelligenceEvidenceDomain.FUNDAMENTALS))
            if fact.metric in _EARNINGS_METRICS:
                values.append(_financial_artifact(fact, IntelligenceEvidenceDomain.EARNINGS))
        return tuple(sorted(values, key=_artifact_key))


class ShareholdingFilingsEvidenceAdapter:
    """Projects primary shareholding disclosure lineage, never holding percentages."""

    def __init__(self, store: CorporateFilingsStore) -> None:
        self._store = store

    def artifacts(self, canonical_instrument_id: str, *, as_of: datetime) -> tuple[StoredIntelligenceArtifact, ...]:
        filings = self._store.list(
            instrument_id=canonical_instrument_id,
            filing_type=FilingType.SHAREHOLDING_PATTERN,
            as_of=as_of,
            limit=500,
        )
        return tuple(sorted((_shareholding_artifact(value) for value in filings), key=_artifact_key))


class CorporateActionsEvidenceAdapter:
    """Projects official historical-action lineage from the security master."""

    def __init__(self, store: HistoricalSecurityMasterStore) -> None:
        self._store = store

    def artifacts(self, canonical_instrument_id: str, *, as_of: datetime) -> tuple[StoredIntelligenceArtifact, ...]:
        return tuple(sorted(
            (_corporate_action_artifact(value) for value in self._store.actions_as_of(canonical_instrument_id, as_of)),
            key=_artifact_key,
        ))


class CompanyEvidenceStoredSource:
    """The U14B-3A stored-only source for company evidence domains."""

    def __init__(
        self,
        *,
        financial_facts: FinancialFactStore | None = None,
        filings: CorporateFilingsStore | None = None,
        historical_security_master: HistoricalSecurityMasterStore | None = None,
    ) -> None:
        self._adapters: tuple[CompanyEvidenceAdapter, ...] = tuple(
            adapter for adapter in (
                FinancialFactsEvidenceAdapter(financial_facts) if financial_facts is not None else None,
                ShareholdingFilingsEvidenceAdapter(filings) if filings is not None else None,
                CorporateActionsEvidenceAdapter(historical_security_master) if historical_security_master is not None else None,
            ) if adapter is not None
        )

    def list_stored_intelligence_artifacts(
        self, canonical_instrument_id: str, *, as_of: datetime
    ) -> tuple[StoredIntelligenceArtifact, ...]:
        values = tuple(
            artifact for adapter in self._adapters
            for artifact in adapter.artifacts(canonical_instrument_id, as_of=as_of)
        )
        return tuple(sorted(values, key=_artifact_key))


_EARNINGS_METRICS = frozenset({
    FinancialMetric.REVENUE, FinancialMetric.OTHER_INCOME, FinancialMetric.EBITDA,
    FinancialMetric.OPERATING_PROFIT, FinancialMetric.EBIT, FinancialMetric.DEPRECIATION,
    FinancialMetric.FINANCE_COST, FinancialMetric.PBT, FinancialMetric.TAX,
    FinancialMetric.PAT, FinancialMetric.MINORITY_INTEREST, FinancialMetric.EPS_BASIC,
    FinancialMetric.EPS_DILUTED,
})


def _financial_artifact(fact: FinancialFact, domain: IntelligenceEvidenceDomain) -> StoredIntelligenceArtifact:
    availability, warnings = _financial_availability(fact)
    return StoredIntelligenceArtifact(
        canonical_instrument_id=fact.instrument.instrument_id,
        domain=domain,
        artifact_id=f"financial-fact:{fact.fact_id}",
        artifact_fingerprint=manifest_fingerprint(
            fact_id=fact.fact_id, metric=fact.metric.value, period_end=fact.period_end,
            published_at=fact.published_at, received_at=fact.received_at,
            source=fact.source, filing_id=fact.filing_id, source_reference=fact.source_reference,
            revision_of_fact_id=fact.revision_of_fact_id, quality_flags=fact.quality_flags,
        ),
        availability=availability,
        evidence_as_of=fact.available_at,
        observed_at=fact.published_at,
        available_at=fact.received_at,
        freshness_status=FreshnessStatus.UNKNOWN,
        freshness_policy_reference=None,
        source_provenance_fingerprint=manifest_fingerprint(
            source=fact.source, source_reference=fact.source_reference, filing_id=fact.filing_id,
            provenance=fact.provenance,
        ),
        historical_integrity_reference=manifest_fingerprint(
            publication=fact.published_at, first_observed=fact.received_at,
        ),
        invalidation_domain=(
            IntelligenceInvalidationDomain.EARNINGS
            if domain is IntelligenceEvidenceDomain.EARNINGS
            else IntelligenceInvalidationDomain.FUNDAMENTALS
        ),
        warnings=warnings,
    )


def _shareholding_artifact(filing: CorporateFiling) -> StoredIntelligenceArtifact:
    # The filing store retains primary disclosure lineage, not normalized FII/DII values.
    return StoredIntelligenceArtifact(
        canonical_instrument_id=filing.instrument.instrument_id,
        domain=IntelligenceEvidenceDomain.OWNERSHIP,
        artifact_id=f"shareholding-filing:{filing.filing_id}",
        artifact_fingerprint=manifest_fingerprint(
            filing_id=filing.filing_id, announced_at=filing.announced_at,
            received_at=filing.received_at, source=filing.source,
            source_reference=filing.source_reference, revision_of=filing.revision_of_filing_id,
        ),
        availability=IntelligenceEvidenceAvailability.PARTIAL,
        evidence_as_of=max(filing.announced_at, filing.received_at),
        observed_at=filing.announced_at,
        available_at=filing.received_at,
        freshness_status=FreshnessStatus.UNKNOWN,
        freshness_policy_reference=None,
        source_provenance_fingerprint=manifest_fingerprint(
            source=filing.source, source_quality=filing.source_quality.value,
            source_reference=filing.source_reference, provenance=filing.provenance,
        ),
        historical_integrity_reference=manifest_fingerprint(
            announced_at=filing.announced_at, received_at=filing.received_at,
        ),
        invalidation_domain=IntelligenceInvalidationDomain.FUNDAMENTALS,
        warnings=("SHAREHOLDING_FACTS_NOT_MATERIALIZED",),
    )


def _corporate_action_artifact(action: HistoricalCorporateAction) -> StoredIntelligenceArtifact:
    availability = IntelligenceEvidenceAvailability.AVAILABLE if _official_source(action.source) else IntelligenceEvidenceAvailability.PARTIAL
    warnings = tuple(sorted({*action.warnings, *( () if availability is IntelligenceEvidenceAvailability.AVAILABLE else ("SECONDARY_OR_UNGOVERNED_CORPORATE_ACTION",) )}))
    return StoredIntelligenceArtifact(
        canonical_instrument_id=action.canonical_instrument_id,
        domain=IntelligenceEvidenceDomain.CORPORATE_ACTIONS,
        artifact_id=f"corporate-action:{action.action_id}",
        artifact_fingerprint=manifest_fingerprint(
            action_id=action.action_id, kind=action.kind.value,
            announcement_date=action.announcement_date, record_date=action.record_date,
            ex_date=action.ex_date, effective_date=action.effective_date,
            source=action.source, revision=action.revision, action_as_of=action.as_of,
            source_reference=action.source_reference,
        ),
        availability=availability,
        evidence_as_of=action.as_of,
        observed_at=action.announcement_date or action.as_of,
        available_at=action.as_of,
        freshness_status=FreshnessStatus.UNKNOWN,
        freshness_policy_reference=None,
        source_provenance_fingerprint=manifest_fingerprint(
            source=action.source, source_reference=action.source_reference, revision=action.revision,
        ),
        historical_integrity_reference=manifest_fingerprint(
            announcement_date=action.announcement_date, record_date=action.record_date,
            ex_date=action.ex_date, effective_date=action.effective_date, action_as_of=action.as_of,
        ),
        invalidation_domain=IntelligenceInvalidationDomain.REFERENCE_DATA,
        warnings=warnings,
    )


def _financial_availability(fact: FinancialFact) -> tuple[IntelligenceEvidenceAvailability, tuple[str, ...]]:
    if _official_source(fact.source) or any(_official_source(value) for value in fact.provenance):
        return IntelligenceEvidenceAvailability.AVAILABLE, ()
    return IntelligenceEvidenceAvailability.PARTIAL, ("SECONDARY_OR_UNGOVERNED_FINANCIAL_SOURCE",)


def _official_source(value: str) -> bool:
    source = value.upper()
    return "BSE_OFFICIAL" in source or "NSE_OFFICIAL" in source or source == "NSE"


def _artifact_key(value: StoredIntelligenceArtifact) -> tuple[str, str, str]:
    return value.domain.value, value.artifact_id, value.artifact_fingerprint


__all__ = (
    "CompanyEvidenceStoredSource", "CompositeStoredIntelligenceSource",
    "CorporateActionsEvidenceAdapter", "FinancialFactsEvidenceAdapter",
    "ShareholdingFilingsEvidenceAdapter",
)
