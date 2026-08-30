"""U17 persistence bridge for factual official NSE corporate announcements."""
from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
from typing import Callable

from app.data_operations.models import (
    EvidenceRefreshFailureKind, EvidenceRefreshOutcome, EvidenceRefreshRequest,
    EvidenceRefreshStatus, ReconciliationStatus,
)
from app.data_sources.models import DataFamily, SourceRecordProvenance
from app.news.models import NewsArticleEvidence, NewsEventCategory, NewsSourceQuality
from app.news.nse_official import (
    NSE_CORPORATE_ANNOUNCEMENTS_ENDPOINT, NSE_OFFICIAL_NEWS_PROVIDER,
    NseAnnouncementSourceError, NseCorporateAnnouncement, NseCorporateAnnouncementsSource,
)
from app.news.store import NewsEvidenceStore
from app.universe_analysis.models import NseEquityInstrument
from app.universe_analysis.service import CoreUniverseAnalysisStore


class NseCorporateAnnouncementsRefreshJob:
    """Append exact-symbol NSE disclosures through the canonical news store.

    The job deliberately performs no event categorisation, sentiment, impact,
    recommendation, or fallback generation.  It records only exchange fields
    returned by the official source and a deterministic raw-record identity.
    """

    def __init__(
        self,
        *,
        universe: CoreUniverseAnalysisStore,
        news: NewsEvidenceStore,
        source: NseCorporateAnnouncementsSource | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._universe, self._news, self._source, self._clock = universe, news, source or NseCorporateAnnouncementsSource(), clock

    def refresh(self, request: EvidenceRefreshRequest) -> EvidenceRefreshOutcome:
        snapshot = self._universe.latest_universe_snapshot()
        if snapshot is None:
            return _unavailable("NSE_UNIVERSE_SNAPSHOT_REQUIRED")
        try:
            records, received_at = self._source.fetch()
        except NseAnnouncementSourceError as error:
            return _source_failure(error.code)
        values = self._universe.instruments_as_of(snapshot.as_of)
        instruments, by_isin = _exact_symbols(values), _exact_isins(values)
        accepted = duplicates = unresolved = conflicts = rejected = 0
        latest: datetime | None = None
        findings: list[tuple[ReconciliationStatus, str, str]] = []
        references: list[str] = []
        for record in records:
            matches = _resolve(record, instruments, by_isin)
            if len(matches) != 1:
                unresolved += 1
                findings.append((ReconciliationStatus.GAP_FOUND, record.symbol, "NSE_ANNOUNCEMENT_EXACT_SYMBOL_UNRESOLVED"))
                continue
            try:
                evidence = _evidence(record, matches[0], received_at)
                existing = self._news.get(evidence.article_id)
                if existing is not None and _same_source_event(existing, evidence):
                    # ``received_at`` is a first-observed fact.  Re-fetching
                    # the unchanged source row must not mutate it or turn a
                    # stable source event into a conflict.
                    duplicates += 1
                elif self._news.save(evidence):
                    accepted += 1
                else:
                    duplicates += 1
                latest = max((item for item in (latest, evidence.published_at) if item is not None), default=latest)
                references.append("NSE_ANNOUNCEMENT:" + record.event_identity)
            except ValueError:
                conflicts += 1
                findings.append((ReconciliationStatus.CONFLICT_FOUND, record.symbol, "NSE_ANNOUNCEMENT_IMMUTABLE_EVIDENCE_CONFLICT"))
        status = (
            EvidenceRefreshStatus.PARTIAL if unresolved or conflicts
            else EvidenceRefreshStatus.NO_CHANGE if not accepted
            else EvidenceRefreshStatus.COMPLETE
        )
        return EvidenceRefreshOutcome(
            status=status,
            provider=NSE_OFFICIAL_NEWS_PROVIDER,
            discovered_count=len(records), accepted_count=accepted, duplicate_count=duplicates,
            conflict_count=conflicts, gap_count=unresolved,
            accepted_through=latest,
            source_fingerprint=sha256("|".join(sorted(references)).encode()).hexdigest() if references else None,
            verified_from_store=bool(accepted or duplicates),
            warnings=tuple(sorted({
                *( ("NSE_ANNOUNCEMENT_EXACT_SYMBOL_UNRESOLVED",) if unresolved else () ),
                *( ("NSE_ANNOUNCEMENT_IMMUTABLE_EVIDENCE_CONFLICT",) if conflicts else () ),
                "NO_SENTIMENT_OR_IMPACT_INTERPRETATION",
            })),
            source_references=tuple(sorted(set(references))), findings=tuple(findings),
        )


def _exact_symbols(values: tuple[NseEquityInstrument, ...]) -> dict[str, tuple[NseEquityInstrument, ...]]:
    mapped: dict[str, dict[str, NseEquityInstrument]] = {}
    for item in values:
        if item.exchange.upper() != "NSE" or not item.symbol:
            continue
        key = item.symbol.upper()
        # ``instruments_as_of`` can expose an identical immutable identity
        # from multiple source snapshots at one as-of.  That is not an
        # ambiguous announcement mapping.  Different canonical IDs remain a
        # strict unresolved ambiguity and are never selected here.
        mapped.setdefault(key, {}).setdefault(item.instrument_id, item)
    return {key: tuple(by_id.values()) for key, by_id in mapped.items()}


def _exact_isins(values: tuple[NseEquityInstrument, ...]) -> dict[str, tuple[NseEquityInstrument, ...]]:
    mapped: dict[str, dict[str, NseEquityInstrument]] = {}
    for item in values:
        if item.exchange.upper() != "NSE" or not item.isin:
            continue
        mapped.setdefault(item.isin.upper(), {}).setdefault(item.instrument_id, item)
    return {key: tuple(by_id.values()) for key, by_id in mapped.items()}


def _resolve(
    record: NseCorporateAnnouncement,
    by_symbol: dict[str, tuple[NseEquityInstrument, ...]],
    by_isin: dict[str, tuple[NseEquityInstrument, ...]],
) -> tuple[NseEquityInstrument, ...]:
    symbols = by_symbol.get(record.symbol, ())
    if record.isin is None:
        return symbols
    isin_values = by_isin.get(record.isin, ())
    # The source supplied both values.  Retain only their exact intersection;
    # a mismatch or multiple intersection fails closed as unresolved.
    by_id = {item.instrument_id: item for item in symbols}
    return tuple(item for item in isin_values if item.instrument_id in by_id)


def _evidence(record: NseCorporateAnnouncement, instrument: NseEquityInstrument, received_at: datetime) -> NewsArticleEvidence:
    published = record.published_at.astimezone(UTC)
    received = max(received_at.astimezone(UTC), published)
    article_id = "nse-announcement:" + sha256(record.event_identity.encode()).hexdigest()[:24]
    source_reference = f"{record.source_sequence_id}:{record.source_fingerprint}"
    attachment = _event_url(record)
    warnings = ["OFFICIAL_NSE_CORPORATE_ANNOUNCEMENT", "NO_SENTIMENT_OR_IMPACT_INTERPRETATION"]
    if record.attachment_identity is None:
        warnings.append("NSE_ANNOUNCEMENT_ATTACHMENT_NOT_PUBLISHED")
    if record.xbrl_identity is not None:
        warnings.append(record.xbrl_identity)
    return NewsArticleEvidence(
        article_id=article_id,
        source_provider=NSE_OFFICIAL_NEWS_PROVIDER,
        publisher="National Stock Exchange of India",
        publisher_url="https://www.nseindia.com/",
        url=attachment,
        title=record.subject,
        description=record.details,
        published_at=published,
        received_at=received,
        language=None,
        country="in",
        instrument_ids=(instrument.instrument_id,),
        sectors=(instrument.sector,) if instrument.sector else (),
        themes=(),
        source_quality=NewsSourceQuality.PRIMARY_EXCHANGE,
        provenance=SourceRecordProvenance(
            source_id=article_id, provider=NSE_OFFICIAL_NEWS_PROVIDER, source_reference=source_reference,
            observed_at=record.exchange_received_at or published, published_at=published, received_at=received,
            effective_from=None, effective_to=None, family=DataFamily.NEWS_RESEARCH,
            schema_version="nse-corporate-announcement-v1", normalization_version="nse-corporate-announcement-v1",
        ),
        event_category=NewsEventCategory.UNCLASSIFIED,
        match_warnings=(), warnings=tuple(sorted(warnings)), normalization_version="nse-corporate-announcement-v1",
        company_name=record.company_name,
    )


def _unavailable(code: str) -> EvidenceRefreshOutcome:
    return EvidenceRefreshOutcome(
        EvidenceRefreshStatus.SOURCE_UNAVAILABLE, NSE_OFFICIAL_NEWS_PROVIDER,
        failure_kind=EvidenceRefreshFailureKind.SOURCE_UNAVAILABLE, error_summary=code, warnings=(code,),
    )


def _event_url(record: NseCorporateAnnouncement) -> str:
    """Keep an official attachment link while making a rebroadcast version unique.

    ``NewsEvidenceStore`` intentionally has a provider+URL idempotency guard.
    An NSE correction can retain the same PDF path and sequence while changing
    the factual row, so its deterministic source version belongs in a harmless
    fragment rather than being silently discarded as a duplicate.
    """
    base = record.attachment_url or NSE_CORPORATE_ANNOUNCEMENTS_ENDPOINT
    separator = "&" if "#" in base else "#"
    return base + separator + "nse_event=" + record.event_identity


def _same_source_event(existing: NewsArticleEvidence, incoming: NewsArticleEvidence) -> bool:
    """Compare source semantics while deliberately retaining first receipt."""
    adjusted_provenance = replace(incoming.provenance, received_at=existing.provenance.received_at)
    adjusted = replace(incoming, received_at=existing.received_at, provenance=adjusted_provenance)
    return existing == adjusted


def _source_failure(code: str) -> EvidenceRefreshOutcome:
    return EvidenceRefreshOutcome(
        EvidenceRefreshStatus.SOURCE_UNAVAILABLE, NSE_OFFICIAL_NEWS_PROVIDER,
        failure_kind=EvidenceRefreshFailureKind.TRANSIENT,
        error_summary=code, warnings=(code,), source_references=(NSE_CORPORATE_ANNOUNCEMENTS_ENDPOINT,),
    )


__all__ = ("NseCorporateAnnouncementsRefreshJob",)
