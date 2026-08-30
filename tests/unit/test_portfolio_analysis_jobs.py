from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi.testclient import TestClient
import pytest

from app.api.main import create_app
from app.gates.engine import ExchangeCalendar
from app.portfolio.engine import PortfolioEngine
from app.portfolio.models import CashPosition, Portfolio, PortfolioStatus, PortfolioTransaction, TransactionType
from app.portfolio_analysis.audit import diagnostic_registry_audit
from app.portfolio_analysis.models import DiagnosticCompleteness, PortfolioAnalysisJobStatus, PortfolioAnalysisRunResult
from app.portfolio_analysis.service import CoreSnapshotPortfolioAnalysisJobStore, PortfolioAnalysisError, PortfolioAnalysisJobService
from app.storage.database import DatabaseBackend, DatabaseSettings
from app.storage.repository_factory import create_core_api_snapshot_repository


T = datetime(2026, 8, 23, 10, tzinfo=UTC)


def snapshot(identifier="portfolio-a", *, empty=False):
    portfolio = Portfolio(identifier, "Imported", "INR", T, None, None, PortfolioStatus.ACTIVE, {})
    transactions = () if empty else (PortfolioTransaction("tx-" + identifier, identifier, TransactionType.ADD, T, T, "USER_CONFIRMED_SCREENSHOT", "draft", "NSE:RELIANCE", Decimal("2"), Decimal("100"), Decimal("200"), Decimal("0"), Decimal("0"), Decimal("0")),)
    return PortfolioEngine(ExchangeCalendar("nse", frozenset({date(2026, 8, 22)}))).reconstruct(portfolio=portfolio, as_of_timestamp=T, initial_cash=CashPosition(Decimal("0"), "INR", Decimal("0"), T), transactions=transactions, actions=(), prices=(), analytics=())


class Source:
    def __init__(self, *values): self.values = {value.snapshot_id: value for value in values}; self.current = values[0]
    def get_snapshot(self, snapshot_id=None):
        if snapshot_id is None: return self.current
        if snapshot_id not in self.values: raise PortfolioAnalysisError("PORTFOLIO_SNAPSHOT_NOT_FOUND", "missing")
        return self.values[snapshot_id]


class Runner:
    def __init__(self, *, partial=False): self.partial = partial; self.calls = []
    def run(self, value):
        self.calls.append(value.snapshot_id)
        ids = tuple(item.instrument_id for item in value.holdings)
        return PortfolioAnalysisRunResult(ids if not self.partial else (), ids if self.partial else (), ("HISTORICAL_DATA_UNAVAILABLE",) if self.partial else (), True, False, DiagnosticCompleteness.PARTIAL)


def service(tmp_path, *, source=None, runner=None):
    repo = create_core_api_snapshot_repository(DatabaseSettings(DatabaseBackend.SQLITE, f"sqlite:///{tmp_path / 'jobs.db'}"))
    return PortfolioAnalysisJobService(snapshots=source or Source(snapshot()), store=CoreSnapshotPortfolioAnalysisJobStore(repo), runner=runner or Runner(), clock=lambda: T)


def test_internal_diagnostic_audit_is_exact_but_truthfully_not_a_live_61_rule_portfolio_pipeline():
    audit = diagnostic_registry_audit()
    assert audit.canonical_count == audit.evaluator_wrapper_count == 61
    assert audit.unique_ids and not audit.all_61_executable
    assert audit.end_to_end_portfolio_pipeline_count == 6 and audit.gap


def test_job_is_snapshot_pinned_deduplicated_immutable_and_operational_completion_stays_partial(tmp_path):
    first, later = snapshot("portfolio-a"), snapshot("portfolio-b")
    source, runner = Source(first, later), Runner()
    value = service(tmp_path, source=source, runner=runner)
    job = value.request(first.snapshot_id)
    assert value.request(first.snapshot_id) == job
    source.current = later
    done = value.run_next()
    assert done is not None and done.status is PortfolioAnalysisJobStatus.COMPLETED
    assert done.analysis_completeness is DiagnosticCompleteness.PARTIAL
    assert done.portfolio_snapshot_id == first.snapshot_id and runner.calls == [first.snapshot_id]
    assert "CANDIDATE_UNIVERSE_NOT_ANALYZED" in done.warnings
    assert value.get(job.job_id) == done


def test_empty_and_unavailable_holding_processing_are_explicit_partial_not_fake_completion(tmp_path):
    empty = service(tmp_path, source=Source(snapshot(empty=True)))
    with pytest.raises(PortfolioAnalysisError, match="at least one"):
        empty.request()
    runner = Runner(partial=True)
    partial_path = tmp_path / "partial"; partial_path.mkdir()
    value = service(partial_path, runner=runner)
    queued = value.request(); result = value.run_next()
    assert result is not None and result.status is PortfolioAnalysisJobStatus.PARTIAL
    assert result.holdings_completed == 0 and result.analysis_completeness is DiagnosticCompleteness.PARTIAL
    assert value.get(queued.job_id) == result and "HISTORICAL_DATA_UNAVAILABLE" in result.warnings


def test_api_only_queues_and_exposes_public_safe_job_status_without_diagnostic_inventory(tmp_path):
    value = service(tmp_path)
    with TestClient(create_app(portfolio_analysis_job_service=value)) as client:
        created = client.post("/api/v1/portfolio/analysis-jobs", json={"portfolio_snapshot_id": snapshot().snapshot_id})
        duplicate = client.post("/api/v1/portfolio/analysis-jobs", json={"portfolio_snapshot_id": snapshot().snapshot_id})
        listed = client.get("/api/v1/portfolio/analysis-jobs")
        detail = client.get(f"/api/v1/portfolio/analysis-jobs/{created.json()['job_id']}")
    assert created.status_code == duplicate.status_code == listed.status_code == detail.status_code == 200
    assert created.json()["job_id"] == duplicate.json()["job_id"] and created.json()["status"] == "QUEUED"
    assert detail.json()["progress"] == "0/1"
    forbidden = {"diagnostic", "rule_id", "weights", "evidence", "gate"}
    assert forbidden.isdisjoint(detail.json())
    stored = value.get(created.json()["job_id"])
    assert stored.status is PortfolioAnalysisJobStatus.QUEUED


def test_default_api_fails_closed_when_no_persisted_portfolio_snapshot_exists():
    with TestClient(create_app(), raise_server_exceptions=False) as client:
        response = client.post("/api/v1/portfolio/analysis-jobs", json={})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "PORTFOLIO_SNAPSHOT_UNAVAILABLE"
