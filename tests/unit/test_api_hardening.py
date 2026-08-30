"""Cross-cutting Phase 10 API hardening contracts."""

import inspect
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import create_app
from app.api.routes import capital_rotation, data_operations, data_sources, filings, fundamentals, market, news, opportunities, primary_market, performance_governance, portfolio, portfolio_analysis, portfolio_import, runtime, signals, stocks, system
from app.api.routes import connections


EXPECTED_PATHS = {
    "/health",
    "/api/v1/system/status", "/api/v1/system/version",
    "/api/v1/runtime/status",
    "/api/v1/data-operations/health",
    "/api/v1/data-sources/status",
    "/api/v1/filings", "/api/v1/filings/{filing_id}",
    "/api/v1/news", "/api/v1/news/{article_id}",
    "/api/v1/primary-market/issues", "/api/v1/primary-market/issues/{issue_id}", "/api/v1/primary-market/summary",
    "/api/v1/fundamentals/{symbol}", "/api/v1/fundamentals/{symbol}/series",
    "/api/v1/portfolio", "/api/v1/portfolio/holdings", "/api/v1/portfolio/summary", "/api/v1/portfolio/sell-side",
    "/api/v1/portfolio/import/screenshots", "/api/v1/portfolio/import/{import_id}/confirm", "/api/v1/portfolio/import/{import_id}/cancel",
    "/api/v1/portfolio/analysis-jobs", "/api/v1/portfolio/analysis-jobs/{job_id}",
    "/api/v1/capital-rotation",
    "/api/v1/opportunities", "/api/v1/universe-analysis/jobs/{job_id}",
    "/api/v1/market/regime", "/api/v1/market/breadth", "/api/v1/market/extremes", "/api/v1/market/crisis", "/api/v1/sectors", "/api/v1/sectors/{sector_id}",
    "/api/v1/stocks", "/api/v1/stocks/{symbol}/analysis", "/api/v1/stocks/{symbol}/shared-brain", "/api/v1/signals", "/api/v1/signals/{signal_id}",
    "/api/v1/paper-trades", "/api/v1/paper-trades/{trade_id}", "/api/v1/paper-trades/performance",
    "/api/v1/performance", "/api/v1/performance/{report_id}",
    "/api/v1/benchmarks", "/api/v1/benchmarks/{benchmark_id}",
    "/api/v1/governance/strategy-versions", "/api/v1/governance/active-strategy",
    "/api/v1/governance/promotions", "/api/v1/governance/promotions/{proposal_id}",
    "/api/v1/connections", "/api/v1/connections/kotak-neo",
    "/api/v1/connections/kotak-neo/test", "/api/v1/connections/kotak-neo/session/test", "/api/v1/connections/kotak-neo/credentials",
    "/api/v1/connections/global-datafeeds", "/api/v1/connections/global-datafeeds/credentials",
    "/api/v1/connections/upstox", "/api/v1/connections/upstox/test", "/api/v1/connections/upstox/credentials",
    "/api/v1/connections/gnews", "/api/v1/connections/gnews/test", "/api/v1/connections/gnews/credentials",
}


def test_complete_route_inventory_openapi_operations_and_read_only_methods_are_stable():
    application = create_app()
    with TestClient(application) as client:
        document = client.get("/openapi.json")
        docs = client.get("/docs")

    assert document.status_code == docs.status_code == 200
    paths = document.json()["paths"]
    assert EXPECTED_PATHS - {"/health"} == set(paths)
    mutable_paths = {"/api/v1/connections/kotak-neo", "/api/v1/connections/kotak-neo/test", "/api/v1/connections/kotak-neo/session/test", "/api/v1/connections/kotak-neo/credentials", "/api/v1/connections/global-datafeeds", "/api/v1/connections/global-datafeeds/credentials", "/api/v1/connections/upstox", "/api/v1/connections/upstox/test", "/api/v1/connections/upstox/credentials", "/api/v1/connections/gnews", "/api/v1/connections/gnews/test", "/api/v1/connections/gnews/credentials", "/api/v1/portfolio/import/screenshots", "/api/v1/portfolio/import/{import_id}/confirm", "/api/v1/portfolio/import/{import_id}/cancel", "/api/v1/portfolio/analysis-jobs"}
    assert all(set(item) == {"get"} for path, item in paths.items() if path not in mutable_paths)
    assert set(paths["/api/v1/connections/kotak-neo"]) == {"get", "put"}
    assert set(paths["/api/v1/connections/kotak-neo/test"]) == {"post"}
    assert set(paths["/api/v1/connections/kotak-neo/session/test"]) == {"post"}
    assert set(paths["/api/v1/connections/kotak-neo/credentials"]) == {"delete"}
    assert set(paths["/api/v1/connections/global-datafeeds"]) == {"get", "put"}
    assert set(paths["/api/v1/connections/global-datafeeds/credentials"]) == {"delete"}
    assert set(paths["/api/v1/connections/upstox"]) == {"get", "put"}
    assert set(paths["/api/v1/connections/upstox/test"]) == {"post"}
    assert set(paths["/api/v1/connections/upstox/credentials"]) == {"delete"}
    assert set(paths["/api/v1/connections/gnews"]) == {"get", "put"}
    assert set(paths["/api/v1/connections/gnews/test"]) == {"post"}
    assert set(paths["/api/v1/connections/gnews/credentials"]) == {"delete"}
    assert set(paths["/api/v1/portfolio/import/screenshots"]) == {"post"}
    assert set(paths["/api/v1/portfolio/import/{import_id}/confirm"]) == {"post"}
    assert set(paths["/api/v1/portfolio/import/{import_id}/cancel"]) == {"post"}
    assert set(paths["/api/v1/portfolio/analysis-jobs"]) == {"get", "post"}
    assert set(paths["/api/v1/portfolio/analysis-jobs/{job_id}"]) == {"get"}
    operation_ids = [operation["operationId"] for item in paths.values() for operation in item.values()]
    assert len(operation_ids) == len(set(operation_ids))


def test_default_unavailable_errors_empty_semantics_validation_and_request_ids_are_safe():
    application = create_app()
    with TestClient(application, raise_server_exceptions=False) as client:
        unavailable = {
            "/api/v1/portfolio": "PORTFOLIO_UNAVAILABLE",
            "/api/v1/market/regime": "MARKET_REGIME_UNAVAILABLE",
            "/api/v1/stocks/COFORGE/analysis": "STOCK_ANALYSIS_UNAVAILABLE",
            "/api/v1/signals": "SIGNALS_UNAVAILABLE",
            "/api/v1/paper-trades": "PAPER_TRADES_UNAVAILABLE",
            "/api/v1/performance": "PERFORMANCE_UNAVAILABLE",
            "/api/v1/benchmarks": "BENCHMARKS_UNAVAILABLE",
            "/api/v1/governance/promotions": "GOVERNANCE_UNAVAILABLE",
        }
        results = {path: client.get(path) for path in unavailable}
        not_found = client.get("/api/v1/signals/missing")
        invalid_page = client.get("/api/v1/signals", params={"limit": 101})

    for path, code in unavailable.items():
        response = results[path]
        assert response.status_code == 503 and response.json()["error"]["code"] == code
        assert response.headers["x-request-id"] == response.json()["error"]["request_id"]
        assert "Traceback" not in response.text and "C:\\Users\\" not in response.text
    assert not_found.status_code == 503  # backing source is unavailable before an ID lookup
    assert invalid_page.status_code == 422 and "x-request-id" in invalid_page.headers


def test_routes_are_thin_no_write_endpoints_or_direct_execution_network_imports():
    modules = (system, runtime, data_operations, data_sources, filings, fundamentals, news, primary_market, portfolio, portfolio_import, portfolio_analysis, capital_rotation, opportunities, market, stocks, signals, performance_governance, connections)
    source = "\n".join(inspect.getsource(module) for module in modules)
    forbidden = (
        ".patch(", "requests", "httpx", "broker", "demat",
        "PaperTradingEngine", "SignalOrchestrator", "PerformanceEngine", "StrategyPromotionService",
        "WalkForwardExecutionService", "buy_hold(", "save_",
    )
    assert not any(item in source for item in forbidden)
    assert ".post(" in inspect.getsource(connections) and ".put(" in inspect.getsource(connections) and ".delete(" in inspect.getsource(connections)
    application = create_app()
    assert not hasattr(application.state, "runtime_started")
    with TestClient(application):
        assert application.state.runtime_started is True
    assert application.state.runtime_started is False


def test_frontend_contract_hides_diagnostic_inventory_and_allows_only_explicit_safe_mutations():
    with TestClient(create_app()) as client:
        schemas = client.get("/openapi.json").json()["components"]["schemas"]
        paths = client.get("/openapi.json").json()["paths"]

    stock = schemas["StockAnalysisResponse"]["properties"]
    decision = schemas["DecisionScoreResponse"]["properties"]
    gates = schemas["ExecutionGatesResponse"]["properties"]
    signal = schemas["SignalResponse"]["properties"]
    rotation = schemas["CapitalRotationOpportunityResponse"]["properties"]
    assert "analysis_coverage" in stock and "diagnostics" not in stock
    assert "provenance_ids" not in schemas["StockDataStatusResponse"]["properties"]
    assert set(decision) == {"final_score", "score_status", "confidence", "warnings"}
    assert set(gates) == {"overall_status", "warnings"}
    assert "diagnostic_ids" not in signal
    assert {"hurdle", "gate_evaluation_id", "evidence_ids", "reasons_for", "reasons_against"}.isdisjoint(rotation)
    non_read_methods = {
        (path, method)
        for path, operations in paths.items()
        for method in operations
        if method != "get"
    }
    assert non_read_methods == {
        ("/api/v1/connections/kotak-neo", "put"),
        ("/api/v1/connections/kotak-neo/test", "post"),
        ("/api/v1/connections/kotak-neo/session/test", "post"),
        ("/api/v1/connections/kotak-neo/credentials", "delete"),
        ("/api/v1/connections/global-datafeeds", "put"),
        ("/api/v1/connections/global-datafeeds/credentials", "delete"),
        ("/api/v1/connections/upstox", "put"),
        ("/api/v1/connections/upstox/test", "post"),
        ("/api/v1/connections/upstox/credentials", "delete"),
        ("/api/v1/connections/gnews", "put"),
        ("/api/v1/connections/gnews/test", "post"),
        ("/api/v1/connections/gnews/credentials", "delete"),
        ("/api/v1/portfolio/import/screenshots", "post"),
        ("/api/v1/portfolio/import/{import_id}/confirm", "post"),
        ("/api/v1/portfolio/import/{import_id}/cancel", "post"),
        ("/api/v1/portfolio/analysis-jobs", "post"),
    }


def test_frontend_upstox_card_uses_only_the_published_connection_routes():
    """Keep browser credential actions pinned to the FastAPI OpenAPI contract."""

    root = Path(__file__).resolve().parents[2]
    client = (root / "frontend" / "src" / "api" / "httpClient.ts").read_text(encoding="utf-8")
    settings = (root / "frontend" / "src" / "pages" / "SettingsPage.tsx").read_text(encoding="utf-8")

    assert "profile: '/api/v1/connections/upstox'" in client
    assert "credentials: '/api/v1/connections/upstox/credentials'" in client
    assert "test: '/api/v1/connections/upstox/test'" in client
    assert "CONNECTION_ROUTES.upstox.test" in client
    assert "/connections/upstox-api" not in client
    assert "/connections/upstox/test-historical" not in client
    assert "/connections/upstox/historical-test" not in client
    assert "/settings/connections/upstox" not in client
    assert "Corporate Action Adjustment" not in client
    assert "{ access_token: token }" in settings
    assert "accessToken: token" not in settings
