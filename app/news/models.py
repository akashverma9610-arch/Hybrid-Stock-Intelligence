"""Immutable factual metadata for optional secondary news/research evidence."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.data_sources.models import SourceRecordProvenance


class NewsSourceQuality(StrEnum):
    PRIMARY_EXCHANGE = "PRIMARY_EXCHANGE"
    PRIMARY_ISSUER = "PRIMARY_ISSUER"
    REPUTABLE_NEWS = "REPUTABLE_NEWS"
    SECONDARY_RESEARCH = "SECONDARY_RESEARCH"
    UNKNOWN = "UNKNOWN"


class NewsEventCategory(StrEnum):
    EARNINGS_RESULTS = "EARNINGS_RESULTS"
    ORDER_CONTRACT = "ORDER_CONTRACT"
    ACQUISITION_DIVESTMENT = "ACQUISITION_DIVESTMENT"
    FUNDRAISE = "FUNDRAISE"
    REGULATORY_LEGAL = "REGULATORY_LEGAL"
    MANAGEMENT_CHANGE = "MANAGEMENT_CHANGE"
    CAPACITY_EXPANSION = "CAPACITY_EXPANSION"
    PRODUCT_CUSTOMER = "PRODUCT_CUSTOMER"
    SECTOR_REGULATORY = "SECTOR_REGULATORY"
    MACRO = "MACRO"
    UNCLASSIFIED = "UNCLASSIFIED"


@dataclass(frozen=True, slots=True)
class NewsSearchRequest:
    query: str
    aliases: tuple[str, ...] = ()
    sector: str | None = None
    start: datetime | None = None
    end: datetime | None = None
    language: str = "en"
    country: str = "in"
    maximum: int = 10
    page: int = 1
    sort_by: str = "publishedAt"

    def __post_init__(self) -> None:
        if not self.query.strip() or len(self.query) > 200:
            raise ValueError("News query must be non-empty and at most 200 characters.")
        if not 1 <= self.maximum <= 100 or self.page < 1:
            raise ValueError("News maximum/page is outside the documented bounded range.")
        if self.start and self.end and self.start > self.end:
            raise ValueError("News search start cannot be after end.")
        if self.sort_by not in {"publishedAt", "relevance"}:
            raise ValueError("Unsupported news sort order.")


@dataclass(frozen=True, slots=True)
class ProviderNewsArticle:
    provider_article_id: str | None
    url: str
    title: str
    description: str | None
    publisher: str | None
    publisher_url: str | None
    published_at: datetime
    language: str | None = None
    country: str | None = None


@dataclass(frozen=True, slots=True)
class NewsArticleEvidence:
    article_id: str
    source_provider: str
    publisher: str | None
    publisher_url: str | None
    url: str
    title: str
    description: str | None
    published_at: datetime
    received_at: datetime
    language: str | None
    country: str | None
    instrument_ids: tuple[str, ...]
    sectors: tuple[str, ...]
    themes: tuple[str, ...]
    source_quality: NewsSourceQuality
    provenance: SourceRecordProvenance
    event_category: NewsEventCategory = NewsEventCategory.UNCLASSIFIED
    linked_filing_id: str | None = None
    match_warnings: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    normalization_version: str = "news-evidence-v1"
    company_name: str | None = None

    def __post_init__(self) -> None:
        if not self.article_id or not self.url.startswith(("https://", "http://")) or not self.title.strip():
            raise ValueError("News evidence requires an identity, URL and title metadata.")
        if self.published_at.tzinfo is None or self.received_at.tzinfo is None:
            raise ValueError("News evidence timestamps must be timezone aware.")
        if self.received_at < self.published_at:
            raise ValueError("News receipt time cannot precede publication time.")

    @property
    def deduplication_key(self) -> str:
        return self.url

    def eligible_as_of(self, as_of: datetime) -> bool:
        return self.published_at <= as_of and self.received_at <= as_of


class NewsIngestionStatus(StrEnum):
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class NewsEvidenceIngestionReport:
    provider: str
    request: NewsSearchRequest
    received_count: int
    accepted_count: int
    duplicate_count: int
    ambiguous_or_unmatched_count: int
    rejected_count: int
    earliest_published_at: datetime | None
    latest_published_at: datetime | None
    warnings: tuple[str, ...]
    provenance: tuple[SourceRecordProvenance, ...]
    started_at: datetime
    completed_at: datetime
    status: NewsIngestionStatus


@dataclass(frozen=True, slots=True)
class NewsEntity:
    instrument_id: str
    canonical_name: str
    aliases: tuple[str, ...] = ()
    ticker: str | None = None
    isin: str | None = None
    sector: str | None = None
