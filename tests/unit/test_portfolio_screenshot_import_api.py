from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient

from app.api.main import create_app
from app.gates.engine import ExchangeCalendar
from app.portfolio_import.models import ExtractedHoldingCandidate, SymbolResolutionStatus
from app.portfolio_import.service import (
    GovernancePortfolioImportPersister, MappingInstrumentResolver, PortfolioImportService,
)
from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository


T = datetime(2026, 8, 23, 10, tzinfo=UTC)


class FixtureExtractor:
    """Deterministic test-only extraction adapter; it retains no upload bytes."""

    def extract(self, images, *, now):
        values = [
            ExtractedHoldingCandidate("row-reliance", "RELIANCE", "Reliance Industries", Decimal("10"), Decimal("2500"), Decimal("2800"), None, None, None, None, Decimal("0.91"), (), 0),
        ]
        if len(images) > 1:
            values.extend((
                ExtractedHoldingCandidate("row-reliance-copy", "RELIANCE", "Reliance Industries", Decimal("10"), Decimal("2500"), None, None, None, None, None, Decimal("0.70"), (), 1),
                ExtractedHoldingCandidate("row-ambiguous", "ABC", "Ambiguous Co", None, None, None, None, None, None, None, Decimal("0.40"), (), 1),
            ))
        return tuple(values)


def service(tmp_path, *, now=T, ttl=timedelta(minutes=15)):
    repository = SQLiteStrategyGovernanceRepository(tmp_path / "portfolio-import.db")
    resolver = MappingInstrumentResolver({"RELIANCE": "NSE:RELIANCE", "ABC": (SymbolResolutionStatus.AMBIGUOUS, None)})
    value = PortfolioImportService(
        extractor=FixtureExtractor(), resolver=resolver,
        persister=GovernancePortfolioImportPersister(repository, calendar=ExchangeCalendar("test", frozenset())),
        clock=lambda: now, draft_ttl=ttl,
    )
    return value, repository


def client_for(service):
    return TestClient(create_app(portfolio_import_service=service))


def upload(client, count=1):
    files = [("files", (f"holding-{index}.png", b"not-a-real-image-but-safe-fixture", "image/png")) for index in range(count)]
    return client.post("/api/v1/portfolio/import/screenshots", files=files)


def test_screenshot_import_draft_is_provisional_resolved_conservatively_and_does_not_persist_portfolio(tmp_path):
    value, repository = service(tmp_path)
    with client_for(value) as client:
        response = upload(client, 2)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "DRAFT" and body["image_count"] == 2
    assert body["holdings"][0]["instrument_id"] == "NSE:RELIANCE"
    assert body["holdings"][0]["resolution_status"] == "MATCHED"
    assert body["holdings"][1]["current_price"] is None
    assert "POSSIBLE_DUPLICATE" in body["holdings"][1]["field_warnings"]
    assert body["holdings"][2]["resolution_status"] == "AMBIGUOUS"
    assert "AMBIGUOUS_SYMBOL" in body["holdings"][2]["field_warnings"]
    assert repository.get_portfolio(f"imported-{body['import_id']}") is None
    assert "not-a-real-image" not in response.text


def test_confirm_only_persists_user_reviewed_valid_rows_and_screenshot_ltp_is_not_a_market_mark(tmp_path):
    value, repository = service(tmp_path)
    with client_for(value) as client:
        draft = upload(client).json()
        confirm = client.post(f"/api/v1/portfolio/import/{draft['import_id']}/confirm", json={
            "mode": "REPLACE", "holdings": [{"row_id": "row-reliance", "instrument_id": "NSE:RELIANCE", "symbol": "RELIANCE", "quantity": "10", "average_price": "2500"}],
        })
    assert confirm.status_code == 200
    body = confirm.json()
    assert body["status"] == "CONFIRMED" and body["holdings_imported"] == 1
    assert "SCREENSHOT_CURRENT_PRICE_IS_INFORMATIONAL_ONLY" in body["warnings"]
    snapshot = repository.get_portfolio_snapshot(body["portfolio_snapshot_id"])
    assert snapshot is not None and snapshot.holdings[0].instrument_id == "NSE:RELIANCE"
    assert snapshot.holdings[0].average_cost == Decimal("2500")
    assert snapshot.holdings[0].current_price is None  # screenshot LTP never becomes canonical market data
    transactions = repository.list_portfolio_transactions_as_of(body["portfolio_id"], T)
    assert len(transactions) == 1 and transactions[0].source == "USER_CONFIRMED_SCREENSHOT"
    assert repository.get_portfolio(f"imported-{draft['import_id']}") is not None


def test_invalid_ambiguous_or_unreviewed_rows_do_not_mutate_portfolio_and_cancel_expiry_cleanup_draft_fields(tmp_path):
    value, repository = service(tmp_path)
    with client_for(value) as client:
        draft = upload(client, 2).json()
        invalid = client.post(f"/api/v1/portfolio/import/{draft['import_id']}/confirm", json={
            "mode": "REPLACE", "holdings": [{"row_id": "row-ambiguous", "quantity": "1", "average_price": "10"}],
        })
        cancelled = client.post(f"/api/v1/portfolio/import/{draft['import_id']}/cancel")
    assert invalid.status_code == 422 and invalid.json()["error"]["code"] == "VALIDATION_ERROR"
    assert repository.get_portfolio(f"imported-{draft['import_id']}") is None
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "CANCELLED" and cancelled.json()["holdings"] == []

    expired_path = tmp_path / "expired"
    expired_path.mkdir()
    expiring, _ = service(expired_path, now=T, ttl=timedelta(0))
    with client_for(expiring) as client:
        expired = upload(client)
        rejected = client.post(f"/api/v1/portfolio/import/{expired.json()['import_id']}/confirm", json={"mode": "REPLACE", "holdings": []})
    assert rejected.status_code == 410 and rejected.json()["error"]["code"] == "IMPORT_EXPIRED"


def test_upload_bounds_and_default_unavailable_extractor_are_safe(tmp_path):
    value, _ = service(tmp_path)
    with client_for(value) as client:
        unsupported = client.post("/api/v1/portfolio/import/screenshots", files={"files": ("a.txt", b"x", "text/plain")})
    assert unsupported.status_code == 415 and unsupported.json()["error"]["code"] == "UNSUPPORTED_IMAGE"
    with TestClient(create_app()) as client:
        unavailable = client.post("/api/v1/portfolio/import/screenshots", files={"files": ("a.png", b"x", "image/png")})
    assert unavailable.status_code == 503 and unavailable.json()["error"]["code"] == "PROVIDER_UNAVAILABLE"
