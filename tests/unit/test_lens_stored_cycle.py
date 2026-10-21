from dataclasses import replace
from datetime import timedelta

import pytest

from app.lens_knowledge.storage import DraftLensCoverageStore
from app.lens_knowledge.stored_cycle import run_stored_coverage_page
from app.storage.core_api_snapshot_repository import CoreApiSnapshotFamily
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository
from app.universe_analysis.service import Canonical61DiagnosticRunner, StockDiagnosticInputAssembler, build_universe_snapshot
from tests.fixtures.analytical_observations import ANALYSIS_TIME, bars
from tests.unit.test_universe_analysis import StoredFacts, instrument


def setup_cycle(tmp_path):
    members = (instrument("a"), instrument("b"))
    universe = build_universe_snapshot(snapshot_id="frozen", as_of=ANALYSIS_TIME, source="stored", instruments=members)
    facts = StoredFacts(bars("a", [10, 11, 12, 13, 14, 15]) + bars("b", [15, 16, 17, 18, 19, 20])
                        + bars("NIFTY_50", [100, 101, 102, 103, 104, 105]))
    repo = SQLiteCoreApiSnapshotRepository(tmp_path / "store.sqlite")
    return members, universe, facts, repo


def test_real_stored_assembler_and_brain_feed_all_lenses_and_durable_pages(tmp_path):
    members, universe, facts, repo = setup_cycle(tmp_path)
    assembler, runner, store = StockDiagnosticInputAssembler(facts), Canonical61DiagnosticRunner(), DraftLensCoverageStore(repo)
    results = []
    for cursor in range(2):
        key, batch = run_stored_coverage_page(universe=universe, instruments=members, as_of=ANALYSIS_TIME,
            cursor=cursor, batch_size=1, assembler=assembler, runner=runner, store=store, recorded_at=ANALYSIS_TIME)
        assert store.get(key) == batch
        assert len(batch.securities[0].assessments) == 35
        assert batch.securities[0].diagnostic_source_state == "SUPPLIED"
        assert all(item.status == "UNKNOWN" for item in batch.securities[0].assessments)
        results.append(batch)
    assert facts.calls == 1  # Existing assembler freezes stored observations across the two pages.
    assert [row.securities[0].instrument_id for row in results] == ["a", "b"]
    assert results[1].completed
    assert len(repo.list_snapshots(CoreApiSnapshotFamily.DRAFT_LENS_COVERAGE)) == 2
    repo.close()


def test_future_or_mismatching_universe_fails_before_source_read_or_write(tmp_path):
    members, universe, facts, repo = setup_cycle(tmp_path)
    for changed in (replace(universe, checksum="invalid"), replace(universe, as_of=ANALYSIS_TIME + timedelta(days=1))):
        with pytest.raises(ValueError):
            run_stored_coverage_page(universe=changed, instruments=members, as_of=ANALYSIS_TIME,
                cursor=0, batch_size=1, assembler=StockDiagnosticInputAssembler(facts),
                runner=Canonical61DiagnosticRunner(), store=DraftLensCoverageStore(repo), recorded_at=ANALYSIS_TIME)
    assert facts.calls == 0
    assert repo.list_snapshots(CoreApiSnapshotFamily.DRAFT_LENS_COVERAGE) == ()
    repo.close()


def test_failed_page_is_not_partially_persisted(tmp_path):
    members, universe, facts, repo = setup_cycle(tmp_path)
    real = StockDiagnosticInputAssembler(facts)

    class BrokenAssembler:
        def assemble(self, item, as_of):
            if item.instrument_id == "b":
                raise ValueError("stored source unavailable")
            return real.assemble(item, as_of)

    with pytest.raises(ValueError, match="stored source unavailable"):
        run_stored_coverage_page(universe=universe, instruments=members, as_of=ANALYSIS_TIME,
            cursor=0, batch_size=2, assembler=BrokenAssembler(),
            runner=Canonical61DiagnosticRunner(), store=DraftLensCoverageStore(repo), recorded_at=ANALYSIS_TIME)
    assert repo.list_snapshots(CoreApiSnapshotFamily.DRAFT_LENS_COVERAGE) == ()
    repo.close()
