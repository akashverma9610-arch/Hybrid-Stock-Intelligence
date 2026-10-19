from dataclasses import replace
from datetime import timedelta

import pytest

from app.lens_knowledge.universe import assess_universe_batch
from app.universe_analysis.service import (Canonical61DiagnosticRunner,
    StockDiagnosticInputAssembler, build_universe_snapshot)
from tests.fixtures.analytical_observations import ANALYSIS_TIME, bars
from tests.unit.test_universe_analysis import StoredFacts, instrument


def test_real_brain_results_are_reused_for_bounded_universe_without_shortlist():
    members = (instrument("a"), instrument("b"))
    universe = build_universe_snapshot(snapshot_id="snapshot", as_of=ANALYSIS_TIME,
                                       source="stored", instruments=members)
    source = StoredFacts(bars("a", [10, 11, 12, 13, 14, 15]) + bars("NIFTY_50", [100, 101, 102, 103, 104, 105]))
    evidence = StockDiagnosticInputAssembler(source).assemble(members[0], ANALYSIS_TIME)
    diagnostics = Canonical61DiagnosticRunner().run(evidence).evaluations
    assert len(diagnostics) == 61
    calls_before = source.calls
    first = assess_universe_batch(universe=universe, as_of=ANALYSIS_TIME,
        diagnostics_by_instrument={"a": diagnostics}, cursor=0, batch_size=1)
    second = assess_universe_batch(universe=universe, as_of=ANALYSIS_TIME,
        diagnostics_by_instrument={}, cursor=first.next_cursor, batch_size=1)
    assert source.calls == calls_before  # Coverage evaluation does not load or recalculate data.
    assert [x.instrument_id for x in first.securities + second.securities] == ["a", "b"]
    assert (first.securities_with_results, second.securities_without_results) == (1, 1)
    assert not first.completed and second.completed
    assert all(len(row.assessments) == 35 for row in first.securities + second.securities)
    assert all(lens.status == "UNKNOWN" for row in first.securities + second.securities for lens in row.assessments)
    assert second.securities[0].diagnostic_source_state == "UNAVAILABLE"


def test_rejects_future_snapshot_wrong_population_and_out_of_page_results():
    universe = build_universe_snapshot(snapshot_id="snapshot", as_of=ANALYSIS_TIME,
        source="stored", instruments=(instrument("a"), instrument("b")))
    with pytest.raises(ValueError, match="newer"):
        assess_universe_batch(universe=replace(universe, as_of=ANALYSIS_TIME + timedelta(days=1)),
                              as_of=ANALYSIS_TIME, diagnostics_by_instrument={})
    with pytest.raises(ValueError, match="counts"):
        assess_universe_batch(universe=replace(universe, eligible_security_count=3),
                              as_of=ANALYSIS_TIME, diagnostics_by_instrument={})
    with pytest.raises(ValueError, match="outside"):
        assess_universe_batch(universe=universe, as_of=ANALYSIS_TIME,
                              diagnostics_by_instrument={"b": ()}, batch_size=1)


@pytest.mark.parametrize("cursor,size", [(-1, 1), (3, 1), (0, 0), (0, 1001), (True, 1)])
def test_invalid_batch_boundaries_fail_closed(cursor, size):
    universe = build_universe_snapshot(snapshot_id="snapshot", as_of=ANALYSIS_TIME,
        source="stored", instruments=(instrument("a"), instrument("b")))
    with pytest.raises(ValueError, match="cursor"):
        assess_universe_batch(universe=universe, as_of=ANALYSIS_TIME,
                              diagnostics_by_instrument={}, cursor=cursor, batch_size=size)
