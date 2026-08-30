"""Seeded SQLite read-path integration: repository snapshots feed existing APIs."""
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.api.main import create_app
from app.api.settings import APISettings
from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily
from app.storage.database import DatabaseBackend, DatabaseSettings
from app.storage.repository_factory import create_core_api_snapshot_repository
from tests.unit.test_market_sector_api import regime, sector
from tests.unit.test_performance_governance_api import _records as governance_records
from tests.unit.test_portfolio_api import snapshot as portfolio_snapshot
from tests.unit.test_signal_paper_api import _records as signal_paper_records
from tests.unit.test_stock_analysis_api import stock_result
from tests.unit.test_capital_rotation import evaluate


T = datetime(2026, 8, 22, 12, tzinfo=UTC)


def _save(repository, identifier, family, payload, offset, *, schema_version="v1"):
    value = CoreApiSnapshot(
        identifier,
        family,
        schema_version,
        "api-read-model-v1",
        f"fingerprint-{identifier}",
        T + timedelta(seconds=offset),
        payload,
    )
    repository.save_snapshot(value)
    return value


def seed(repository):
    signal, completed, _active, _paper_report = signal_paper_records()
    performance, benchmark, version, activation, promotion = governance_records()
    values = (
        _save(repository,"portfolio",CoreApiSnapshotFamily.PORTFOLIO,portfolio_snapshot(),1),
        _save(repository,"regime",CoreApiSnapshotFamily.MARKET_REGIME,regime(),2),
        _save(repository,"sector-energy",CoreApiSnapshotFamily.SECTOR_ANALYSIS,sector(),3),
        _save(repository,"stock-coforge",CoreApiSnapshotFamily.STOCK_ANALYSIS,stock_result(),4),
        _save(repository,"signal",CoreApiSnapshotFamily.SIGNAL,signal,5),
        _save(repository,"paper",CoreApiSnapshotFamily.PAPER_TRADE,completed,6),
        _save(repository,"performance",CoreApiSnapshotFamily.PERFORMANCE_REPORT,performance,7),
        _save(repository,"benchmark",CoreApiSnapshotFamily.BENCHMARK_COMPARISON,benchmark,8),
        _save(repository,"version",CoreApiSnapshotFamily.APPROVED_STRATEGY_VERSION,version,9),
        _save(repository,"promotion",CoreApiSnapshotFamily.PROMOTION_PROPOSAL,promotion,10),
        _save(repository,"activation",CoreApiSnapshotFamily.STRATEGY_ACTIVATION,activation,11),
        _save(repository,"rotation",CoreApiSnapshotFamily.CAPITAL_ROTATION,evaluate(),12),
    )
    return (
        values,
        signal.signal.signal_id,
        completed.trade.paper_trade_id,
        performance.report.report_id,
        benchmark.comparison_id,
        promotion.proposal.proposal_id,
    )


def test_app_lifespan_constructs_default_sqlite_read_source_for_an_empty_store(tmp_path):
    settings = DatabaseSettings(DatabaseBackend.SQLITE, f"sqlite:///{tmp_path / 'default.db'}")
    app = create_app(api_settings=APISettings(database=settings))
    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.get("/api/v1/portfolio").status_code == 503
        assert app.state.core_api_snapshot_repository.__class__.__name__ == "SQLiteCoreApiSnapshotRepository"
        assert app.state.owns_core_api_snapshot_repository is True


def test_empty_sqlite_default_remains_safe_and_seeded_snapshots_serve_all_api_families(tmp_path):
    settings = DatabaseSettings(DatabaseBackend.SQLITE, f"sqlite:///{tmp_path / 'api.db'}")
    repository = create_core_api_snapshot_repository(settings)
    with TestClient(
        create_app(api_settings=APISettings(database=settings), core_api_snapshot_repository=repository),
        raise_server_exceptions=False,
    ) as client:
        assert client.get("/api/v1/portfolio").status_code == 503
    seeded, signal_id, paper_id, report_id, comparison_id, proposal_id = seed(repository)
    before = tuple(repository.get_snapshot(item.snapshot_id) for item in seeded)
    app = create_app(api_settings=APISettings(database=settings), core_api_snapshot_repository=repository)
    with TestClient(app) as client:
        responses = (
            client.get("/api/v1/portfolio"), client.get("/api/v1/market/regime"), client.get("/api/v1/sectors"),
            client.get("/api/v1/sectors/energy"), client.get("/api/v1/stocks/COFORGE/analysis"),
            client.get("/api/v1/stocks"),
            client.get("/api/v1/signals"), client.get(f"/api/v1/signals/{signal_id}"),
            client.get("/api/v1/paper-trades"), client.get(f"/api/v1/paper-trades/{paper_id}"), client.get("/api/v1/paper-trades/performance"),
            client.get("/api/v1/performance"), client.get(f"/api/v1/performance/{report_id}"), client.get("/api/v1/benchmarks"), client.get(f"/api/v1/benchmarks/{comparison_id}"),
            client.get("/api/v1/governance/strategy-versions"), client.get("/api/v1/governance/active-strategy"), client.get("/api/v1/governance/promotions"), client.get(f"/api/v1/governance/promotions/{proposal_id}"),
            client.get("/api/v1/capital-rotation"),
        )
    assert all(response.status_code == 200 for response in responses)
    assert responses[0].json()["portfolio_id"] == "api-portfolio"
    assert responses[4].json()["identity"]["symbol"] == "COFORGE"
    assert responses[5].json()["total"] == 1 and responses[6].json()["total"] == 1
    assert responses[11].json()["items"][0]["mode"] == "TEST" and responses[13].json()["items"][0]["mode"] == "TEST"
    assert responses[16].json()["active"] is True and responses[17].json()["total"] == 1
    assert responses[-1].json()["overall_status"] == "READY"
    assert tuple(repository.get_snapshot(item.snapshot_id) for item in seeded) == before


def test_stock_symbol_scoping_and_unsupported_snapshot_schema_fail_safely(tmp_path):
    settings = DatabaseSettings(DatabaseBackend.SQLITE, f"sqlite:///{tmp_path / 'scoped.db'}")
    repository = create_core_api_snapshot_repository(settings)
    _save(repository, "stock-coforge", CoreApiSnapshotFamily.STOCK_ANALYSIS, stock_result(), 1)
    _save(
        repository,
        "stock-coforge-latest",
        CoreApiSnapshotFamily.STOCK_ANALYSIS,
        replace(stock_result(), name="Latest Coforge"),
        2,
    )
    app = create_app(api_settings=APISettings(database=settings), core_api_snapshot_repository=repository)
    with TestClient(app, raise_server_exceptions=False) as client:
        latest = client.get("/api/v1/stocks/COFORGE/analysis")
        assert client.get("/api/v1/stocks/OTHER/analysis").status_code == 404
    assert latest.status_code == 200
    assert latest.json()["identity"]["name"] == "Latest Coforge"

    unsupported_repository = create_core_api_snapshot_repository(
        DatabaseSettings(DatabaseBackend.SQLITE, f"sqlite:///{tmp_path / 'unsupported.db'}")
    )
    _save(
        unsupported_repository,
        "stock-unsupported",
        CoreApiSnapshotFamily.STOCK_ANALYSIS,
        stock_result(),
        1,
        schema_version="v2",
    )
    unsupported_app = create_app(
        api_settings=APISettings(database=settings),
        core_api_snapshot_repository=unsupported_repository,
    )
    with TestClient(unsupported_app, raise_server_exceptions=False) as client:
        response = client.get("/api/v1/stocks/COFORGE/analysis")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "SNAPSHOT_SCHEMA_UNSUPPORTED"
