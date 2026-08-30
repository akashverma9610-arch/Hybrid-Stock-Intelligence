from datetime import datetime
from typing import Protocol

from app.api.errors import APIRequestError
from app.news.models import NewsArticleEvidence
from app.news.store import NewsEvidenceStore


class NewsQueryService(Protocol):
    def list_news(self, *, instrument_id: str | None, sector: str | None, start: datetime | None, end: datetime | None, provider: str | None, limit: int) -> tuple[NewsArticleEvidence, ...]: ...
    def news(self, article_id: str) -> NewsArticleEvidence: ...

class UnavailableNewsQueryService:
    def list_news(self, **kwargs): raise APIRequestError(status_code=503,code="NEWS_RESEARCH_UNAVAILABLE",message="Optional news evidence is unavailable.")
    def news(self, article_id: str): raise APIRequestError(status_code=503,code="NEWS_RESEARCH_UNAVAILABLE",message="Optional news evidence is unavailable.")

class RepositoryNewsQueryService:
    def __init__(self, store: NewsEvidenceStore) -> None: self._store=store
    def list_news(self, *, instrument_id, sector, start, end, provider, limit): return self._store.list(instrument_id=instrument_id,sector=sector,start=start,end=end,provider=provider,limit=limit)
    def news(self, article_id):
        value=self._store.get(article_id)
        if value is None: raise APIRequestError(status_code=404,code="NEWS_EVIDENCE_NOT_FOUND",message="News evidence was not found.")
        return value
