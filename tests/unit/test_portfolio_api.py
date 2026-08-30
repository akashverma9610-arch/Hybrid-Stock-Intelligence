import inspect
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi.testclient import TestClient

from app.api.dependencies import get_portfolio_query_service
from app.api.errors import APIRequestError
from app.api.main import create_app
from app.api.portfolio_query import SnapshotPortfolioQueryService
from app.api.schemas.portfolio import (
    PortfolioHoldingResponse,
    PortfolioResponse,
    PortfolioSummaryResponse,
)
from app.api.routes import portfolio as portfolio_routes
from app.gates.engine import ExchangeCalendar
from app.portfolio.engine import PortfolioEngine
from app.portfolio.models import (
    CashPosition, CashState,
    HoldingAnalytics,
    Portfolio,
    PortfolioStatus,
    PortfolioTransaction,
    PriceReference,
    TransactionType,
)


T0 = datetime(2026, 8, 3, 10, tzinfo=UTC)
AS_OF = datetime(2026, 8, 20, 10, tzinfo=UTC)


def snapshot(*, empty: bool = False, marked: bool = True):
    portfolio = Portfolio("api-portfolio", "API fixture", "INR", T0, "strategy/1", None, PortfolioStatus.ACTIVE, {})
    cash = CashPosition(Decimal("20000"), "INR", Decimal("0"), T0)
    transactions = () if empty else (
        PortfolioTransaction(
            "api-buy", portfolio.portfolio_id, TransactionType.BUY, T0, T0, "fixture", "api-buy",
            "RELIANCE", Decimal("100"), Decimal("100"), Decimal("10000"), Decimal("0"), Decimal("0"), Decimal("-10000"),
        ),
    )
    prices = () if not marked else (PriceReference("api-price", "RELIANCE", Decimal("120"), AS_OF, AS_OF),)
    analytics = () if empty else (
        HoldingAnalytics(
            "RELIANCE", AS_OF, AS_OF, raw_decision_score=Decimal("8.8"), score_status="COMPLETE",
            data_confidence=.9, gate_status="EXECUTABLE", structural_stop=Decimal("90"), sector="ENERGY",
        ),
    )
    return PortfolioEngine(ExchangeCalendar("nse-api", frozenset({date(2026, 8, 19)}))).reconstruct(
        portfolio=portfolio,
        as_of_timestamp=AS_OF,
        initial_cash=cash,
        transactions=transactions,
        actions=(),
        prices=prices,
        analytics=analytics,
    )


def client_for(value):
    return TestClient(create_app(portfolio_query_service=SnapshotPortfolioQueryService(value)))


def test_portfolio_holdings_and_summary_expose_existing_snapshot_values():
    value = snapshot()
    with client_for(value) as client:
        portfolio = client.get("/api/v1/portfolio")
        holdings = client.get("/api/v1/portfolio/holdings")
        summary = client.get("/api/v1/portfolio/summary")

    response = PortfolioResponse.model_validate(portfolio.json())
    holding = PortfolioHoldingResponse.model_validate(holdings.json()[0])
    compact = PortfolioSummaryResponse.model_validate(summary.json())
    assert portfolio.status_code == holdings.status_code == summary.status_code == 200
    assert response.portfolio_id == value.portfolio_id and response.as_of == AS_OF
    assert response.invested_value == Decimal("10000") and response.marked_value == Decimal("12000")
    assert holding.instrument_id == "RELIANCE" and holding.market_price == Decimal("120")
    assert holding.data_as_of == AS_OF and compact.largest_position.instrument_id == "RELIANCE"
    assert isinstance(portfolio.json()["invested_value"], str)
    assert portfolio.json()["as_of"].endswith(("Z", "+00:00"))


def test_empty_and_partial_portfolios_are_visible_without_fabricated_marks():
    with client_for(snapshot(empty=True)) as client:
        empty = client.get("/api/v1/portfolio")
        empty_holdings = client.get("/api/v1/portfolio/holdings")
    with client_for(snapshot(marked=False)) as client:
        partial = client.get("/api/v1/portfolio")
        partial_holdings = client.get("/api/v1/portfolio/holdings")

    assert empty.status_code == empty_holdings.status_code == 200
    assert empty.json()["holding_count"] == 0 and empty.json()["marked_value"] == "0"
    assert empty_holdings.json() == []
    assert partial.status_code == partial_holdings.status_code == 200
    assert partial.json()["marked_value"] is None and partial.json()["total_equity"] is None
    assert "MARK_DATA_PARTIAL" in partial.json()["warnings"]
    assert partial_holdings.json()[0]["market_price"] is None


def test_unknown_cash_is_explicit_and_never_serialized_as_zero():
    value = snapshot(marked=False)
    value = replace(value, cash=CashPosition(None, "INR", Decimal("0"), value.as_of_timestamp, CashState.UNKNOWN))
    with client_for(value) as client:
        response = client.get("/api/v1/portfolio")
    assert response.status_code == 200
    assert response.json()["cash"] is None and response.json()["cash_status"] == "UNKNOWN"
    assert "CASH_UNKNOWN" in response.json()["warnings"]


def test_portfolio_dependency_override_is_read_only_and_preserves_snapshot():
    value = snapshot()
    application = create_app()
    application.dependency_overrides[get_portfolio_query_service] = lambda: SnapshotPortfolioQueryService(value)
    before = value
    with TestClient(application) as client:
        assert client.get("/api/v1/portfolio").status_code == 200
        assert client.get("/api/v1/portfolio/holdings").status_code == 200
        assert client.get("/api/v1/portfolio/summary").status_code == 200
    assert value == before


def test_unavailable_or_not_found_portfolio_returns_safe_standard_error():
    with TestClient(create_app(), raise_server_exceptions=False) as client:
        unavailable = client.get("/api/v1/portfolio")

    class MissingPortfolio:
        def get_snapshot(self):
            raise APIRequestError(status_code=404, code="PORTFOLIO_NOT_FOUND", message="Portfolio was not found.")

    with TestClient(create_app(portfolio_query_service=MissingPortfolio()), raise_server_exceptions=False) as client:
        missing = client.get("/api/v1/portfolio")

    assert unavailable.status_code == 503 and unavailable.json()["error"]["code"] == "PORTFOLIO_UNAVAILABLE"
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "PORTFOLIO_NOT_FOUND"
    assert "Traceback" not in unavailable.text and "C:\\" not in unavailable.text


def test_routes_are_thin_and_do_not_embed_portfolio_engine_calculations():
    source = inspect.getsource(portfolio_routes)

    assert "PortfolioEngine" not in source
    assert "CapitalRotationEngine" not in source
    assert ".reconstruct(" not in source
