"""Deterministic event clustering; article count never increases catalyst weight."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .models import NewsArticleEvidence


@dataclass(frozen=True, slots=True)
class NewsEventCluster:
    cluster_id: str
    article_ids: tuple[str, ...]
    event_category: str
    instrument_ids: tuple[str, ...]
    original_event_at: datetime
    latest_retrieved_at: datetime
    primary_article_ids: tuple[str, ...]
    filing_ids: tuple[str, ...]
    company_confirmed: bool
    warnings: tuple[str, ...] = ()


class NewsEventClusteringService:
    def cluster(self, evidence: tuple[NewsArticleEvidence, ...]) -> tuple[NewsEventCluster, ...]:
        groups: dict[tuple, list[NewsArticleEvidence]] = {}
        for item in evidence:
            key = (item.linked_filing_id or item.event_category.value, tuple(sorted(item.instrument_ids)), item.published_at.date())
            groups.setdefault(key, []).append(item)
        output = []
        for key, items in sorted(groups.items(), key=lambda item: str(item[0])):
            ordered = tuple(sorted(items, key=lambda value: (value.published_at, value.article_id)))
            original = ordered[0].published_at
            primary = tuple(item.article_id for item in ordered if item.source_quality.value.startswith("PRIMARY"))
            filings = tuple(sorted({item.linked_filing_id for item in ordered if item.linked_filing_id}))
            output.append(NewsEventCluster("news-event:" + "|".join(map(str, key)), tuple(item.article_id for item in ordered), ordered[0].event_category.value, tuple(sorted({identifier for item in ordered for identifier in item.instrument_ids})), original, max(item.received_at for item in ordered), primary, filings, bool(primary or filings), ("REPUBLISHED_ARTICLES_RETAIN_ORIGINAL_EVENT_TIME",) if len(ordered) > 1 else ()))
        return tuple(output)
