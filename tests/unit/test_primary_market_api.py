from datetime import UTC,datetime
from fastapi.testclient import TestClient
from app.api.main import create_app
from app.api.primary_market_query import RepositoryPrimaryMarketQueryService
from app.primary_market.store import SQLitePrimaryMarketStore
from tests.unit.test_primary_market import issue
T=datetime(2026,8,23,tzinfo=UTC)
def test_primary_market_read_only_api_list_detail_summary():
 s=SQLitePrimaryMarketStore();s.save_issue(issue());client=TestClient(create_app(primary_market_query_service=RepositoryPrimaryMarketQueryService(s)))
 assert client.get("/api/v1/primary-market/issues").status_code==200
 assert client.get("/api/v1/primary-market/issues/issue-1").status_code==200
 assert client.get("/api/v1/primary-market/summary",params={"as_of":T.isoformat()}).status_code==200
