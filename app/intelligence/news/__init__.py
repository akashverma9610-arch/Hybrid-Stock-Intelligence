"""Uses the canonical app.news event-clustering and provenance contracts."""
from app.news.hardening import NewsEventCluster, NewsEventClusteringService

__all__ = ("NewsEventCluster", "NewsEventClusteringService")
