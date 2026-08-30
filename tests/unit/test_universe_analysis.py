from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest

from app.registry.canonical import DIAGNOSTIC_RULES
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository
from app.universe_analysis import DIAGNOSTIC_INPUT_REQUIREMENTS
from app.universe_analysis.models import NseEquityInstrument, UniverseAnalysisJobStatus
from app.universe_analysis.service import (
    Canonical61DiagnosticRunner, CoreUniverseAnalysisStore, StockDiagnosticInputAssembler,
    UniverseAnalysisService,
)
from tests.fixtures.analytical_observations import ANALYSIS_TIME, bars


class StoredFacts:
    def __init__(self, values): self.values = tuple(values); self.calls = 0
    def observations_as_of(self, at): self.calls += 1; return self.values


class StoredUniverse:
    def __init__(self, values): self.values = tuple(values)
    def instruments_as_of(self, at): return self.values


def instrument(identifier: str, *, active: bool = True, security_type: str = "EQUITY") -> NseEquityInstrument:
    return NseEquityInstrument(identifier, identifier.upper(), None, "Industrials", None, "ACTIVE" if active else "SUSPENDED", None,
                                active, ANALYSIS_TIME, "official-import", f"fixture:{identifier}", security_type)


def test_registry_requirements_and_runner_are_registry_wide_with_partial_missing_semantics() -> None:
    values = bars("stock", [10, 11, 12, 13, 14, 15], volumes=[10, 11, 12, 13, 14, 15]) + bars("NIFTY_50", [100, 101, 102, 103, 104, 105])
    assembled = StockDiagnosticInputAssembler(StoredFacts(values)).assemble(instrument("stock"), ANALYSIS_TIME)
    result = Canonical61DiagnosticRunner().run(assembled)
    assert tuple(item.diagnostic_id for item in DIAGNOSTIC_INPUT_REQUIREMENTS) == tuple(item.rule_id for item in DIAGNOSTIC_RULES) == tuple(range(1, 62))
    assert tuple(item.canonical_rule_id for item in result.evaluations) == tuple(range(1, 62))
    assert result.evaluated + result.missing == 61
    assert result.completeness.value in {"PARTIAL", "COMPLETE"}
    assert all(item.record.instrument_id == "stock" for item in result.evaluations)


def test_assembler_excludes_future_facts_and_runner_never_fetches_provider_data() -> None:
    future = replace(bars("stock", [99])[0], id="future-bar", provenance=replace(bars("stock", [99])[0].provenance, market_timestamp=ANALYSIS_TIME + timedelta(days=1), retrieved_timestamp=ANALYSIS_TIME + timedelta(days=1)))
    base = bars("stock", [10, 11, 12])
    assembled = StockDiagnosticInputAssembler(StoredFacts(base + (future,))).assemble(instrument("stock"), ANALYSIS_TIME)
    assert "future-bar" not in tuple(item.id for item in assembled.snapshot.observations)
    assert "FUTURE_EVIDENCE_EXCLUDED" in assembled.warnings
    assert Canonical61DiagnosticRunner().run(assembled).evaluations


def test_scan_reuses_one_frozen_as_of_evidence_set_across_symbols() -> None:
    source = StoredFacts(bars("a", [10, 11, 12]) + bars("b", [10, 11, 12]) + bars("NIFTY_50", [100, 101, 102]))
    assembler = StockDiagnosticInputAssembler(source)
    first = assembler.assemble(instrument("a"), ANALYSIS_TIME)
    second = assembler.assemble(instrument("b"), ANALYSIS_TIME)
    assert source.calls == 1 and first.snapshot.id == second.snapshot.id


def test_bounded_job_is_resumable_accounts_for_exclusions_and_publishes_distilled_snapshot(tmp_path) -> None:
    observations = bars("a", [10, 11, 12]) + bars("b", [10, 11, 12]) + bars("NIFTY_50", [100, 101, 102])
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "universe.sqlite")
    store = CoreUniverseAnalysisStore(repository)
    service = UniverseAnalysisService(
        universe=StoredUniverse((instrument("a"), instrument("b"), instrument("bad", active=False))),
        assembler=StockDiagnosticInputAssembler(StoredFacts(observations)), runner=Canonical61DiagnosticRunner(), store=store,
        clock=lambda: ANALYSIS_TIME,
    )
    requested = service.request(universe_id="NSE_EQUITY", universe_as_of=ANALYSIS_TIME, as_of=ANALYSIS_TIME, batch_size=1)
    first = service.run_next_batch()
    assert first is not None and first.status is UniverseAnalysisJobStatus.RUNNING and first.cursor == 1
    second = service.run_next_batch(); third = service.run_next_batch()
    assert second is not None and third is not None and third.status is UniverseAnalysisJobStatus.PARTIAL
    assert third.processed == 3 and third.unavailable_count >= 1
    latest = service.latest_opportunity()
    assert latest is not None and latest.analyzed_count == 3 and latest.universe_count == 3
    assert service.get_job(requested.job_id) == third


def test_universe_job_has_no_shortlist_or_governance_or_live_side_effects() -> None:
    import inspect
    import app.universe_analysis.service as service
    source = inspect.getsource(service).lower()
    assert not any(value in source for value in ("bel", "hal", "icici bank", "mtar", "paras", "place_order", "broker", "demat", "strategyactivation", "strategypromotionproposal"))


def test_eligibility_does_not_rank_and_non_equity_is_retained_as_excluded(tmp_path) -> None:
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "excluded.sqlite")
    service = UniverseAnalysisService(universe=StoredUniverse((instrument("etf", security_type="ETF"),)),
        assembler=StockDiagnosticInputAssembler(StoredFacts(())), runner=Canonical61DiagnosticRunner(), store=CoreUniverseAnalysisStore(repository), clock=lambda: ANALYSIS_TIME)
    service.request(universe_id="NSE_EQUITY", universe_as_of=ANALYSIS_TIME, as_of=ANALYSIS_TIME)
    result = service.run_next_batch()
    assert result is not None and result.unavailable_count == 1 and result.complete_count == 0


def test_public_opportunity_read_model_is_distilled_and_never_runs_a_scan(tmp_path) -> None:
    from fastapi.testclient import TestClient
    from app.api.main import create_app
    from app.api.universe_opportunity_query import CoreSnapshotUniverseOpportunityQueryService
    from app.universe_analysis.models import UniverseOpportunity, UniverseOpportunitySnapshot
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "api.sqlite")
    store = CoreUniverseAnalysisStore(repository)
    store.save_opportunity(UniverseOpportunitySnapshot("snapshot", "job", ANALYSIS_TIME, 5, 4, 4, 1, 3, 1, 1,
        (UniverseOpportunity("ABC", "Industrials", 8, .8, "ACCEPTABLE", "EXECUTABLE", "QUALIFIED", None, "FRESH"),),
        ("UNIVERSE_ANALYSIS_PARTIAL",), "AS_OF_SNAPSHOT"))
    app = create_app(core_api_snapshot_repository=repository,
        universe_opportunity_query_service=CoreSnapshotUniverseOpportunityQueryService(store))
    with TestClient(app) as client:
        response = client.get("/api/v1/opportunities")
    assert response.status_code == 200
    body = response.json()
    assert body["opportunities"][0]["symbol"] == "ABC"
    assert "diagnostic" not in str(body).lower() and "gate_id" not in str(body).lower()


def test_imported_universe_is_immutable_and_as_of_selectable(tmp_path) -> None:
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "universe-source.sqlite")
    store = CoreUniverseAnalysisStore(repository)
    first = instrument("abc")
    later = replace(first, data_as_of=ANALYSIS_TIME + timedelta(days=1), sector="Technology")
    store.save_instrument(first)
    with pytest.raises(ValueError, match="immutable"):
        store.save_instrument(first)
    store.save_instrument(later)
    assert store.instruments_as_of(ANALYSIS_TIME) == (first,)
    assert store.instruments_as_of(ANALYSIS_TIME + timedelta(days=1)) == (later,)
