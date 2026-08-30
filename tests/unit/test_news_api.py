from datetime import UTC, datetime
from fastapi.testclient import TestClient
from app.api.main import create_app
from app.api.news_query import RepositoryNewsQueryService
from app.news.models import NewsArticleEvidence, NewsSourceQuality
from app.news.store import SQLiteNewsEvidenceStore
from app.data_sources.models import DataFamily, SourceRecordProvenance

T=datetime(2026,8,23,tzinfo=UTC)
def test_read_only_news_api_returns_metadata_not_credentials_or_content():
    store=SQLiteNewsEvidenceStore(); evidence=NewsArticleEvidence("article","gnews","Publisher",None,"https://example.test/a","Title","Allowed snippet",T,T,"en","in",("NSE:ALPHA",),("Industrials",),(),NewsSourceQuality.REPUTABLE_NEWS,SourceRecordProvenance("article","gnews","provider",T,T,T,None,None,DataFamily.NEWS_RESEARCH,"v1","v1"))
    store.save(evidence);client=TestClient(create_app(news_query_service=RepositoryNewsQueryService(store)))
    listed=client.get("/api/v1/news",params={"symbol":"NSE:ALPHA"});assert listed.status_code==200 and listed.json()["items"][0]["article_id"]=="article"
    assert client.get("/api/v1/news/article").status_code==200
