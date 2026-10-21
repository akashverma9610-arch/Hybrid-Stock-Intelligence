"""Explicit research-only composition of existing stored-data brain and lens coverage.

No scheduler, API, provider client, fit classification, or trading authority is
created. The caller is responsible for injecting stored-only input sources.
"""
from __future__ import annotations

from datetime import datetime

from app.lens_knowledge.storage import DraftLensCoverageStore
from app.lens_knowledge.universe import UniverseLensCoverageBatch, assess_universe_batch
from app.universe_analysis.models import NseEquityInstrument, UniverseSnapshot
from app.universe_analysis.service import Canonical61DiagnosticRunner, StockDiagnosticInputAssembler, build_universe_snapshot


def run_stored_coverage_page(*, universe: UniverseSnapshot,
                             instruments: tuple[NseEquityInstrument, ...],
                             as_of: datetime, cursor: int, batch_size: int,
                             assembler: StockDiagnosticInputAssembler,
                             runner: Canonical61DiagnosticRunner,
                             store: DraftLensCoverageStore,
                             recorded_at: datetime) -> tuple[str, UniverseLensCoverageBatch]:
    """Compute each selected stock's existing diagnostic run once per call.

    No work is saved unless the full page succeeds. A caller must explicitly
    supply stored-only assembler sources; this API cannot prove their origin.
    The snapshot check proves consistency with supplied instruments, not NSE
    completeness or point-in-time correctness of upstream records.
    """
    if (as_of.tzinfo is None or as_of.utcoffset() is None or universe.as_of.tzinfo is None
            or universe.as_of.utcoffset() is None or universe.as_of > as_of):
        raise ValueError("Invalid snapshot or analysis cutoff")
    if (type(cursor) is not int or type(batch_size) is not int
            or not 0 <= cursor <= len(universe.instrument_ids) or not 1 <= batch_size <= 1000):
        raise ValueError("Invalid page bounds")
    by_id = {item.instrument_id: item for item in instruments}
    if len(by_id) != len(instruments) or any(
            item.data_as_of.tzinfo is None or item.data_as_of.utcoffset() is None
            or item.data_as_of > universe.as_of for item in instruments):
        raise ValueError("Invalid, duplicate, or future-dated universe instrument")
    rebuilt = build_universe_snapshot(snapshot_id=universe.snapshot_id, as_of=universe.as_of,
        source=universe.source, instruments=instruments, version=universe.version)
    if (not universe.snapshot_id or not universe.checksum or rebuilt.checksum != universe.checksum
            or rebuilt.instrument_ids != universe.instrument_ids
            or rebuilt.total_records != universe.total_records
            or rebuilt.eligible_security_count != universe.eligible_security_count
            or rebuilt.excluded_count != universe.excluded_count):
        raise ValueError("Stored universe does not match frozen snapshot")
    selected = universe.instrument_ids[cursor:cursor + batch_size]
    diagnostic_results = {}
    for instrument_id in selected:
        evidence = assembler.assemble(by_id[instrument_id], as_of)
        diagnostic_results[instrument_id] = runner.run(evidence).evaluations
    batch = assess_universe_batch(universe=universe, as_of=as_of,
        diagnostics_by_instrument=diagnostic_results, cursor=cursor, batch_size=batch_size)
    return store.save(batch, recorded_at=recorded_at), batch
