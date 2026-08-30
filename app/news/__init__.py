"""Provider-neutral, secondary news evidence.  This package never fetches publisher pages."""

from app.news.models import NewsArticleEvidence, NewsSourceQuality
from app.news.service import NewsEvidenceIngestionService, NewsResearchInputBuilder
from app.news.store import SQLiteNewsEvidenceStore

__all__ = ("NewsArticleEvidence", "NewsSourceQuality", "NewsEvidenceIngestionService", "NewsResearchInputBuilder", "SQLiteNewsEvidenceStore")
from .hardening import NewsEventCluster, NewsEventClusteringService

__all__ = ("NewsEventCluster", "NewsEventClusteringService")
