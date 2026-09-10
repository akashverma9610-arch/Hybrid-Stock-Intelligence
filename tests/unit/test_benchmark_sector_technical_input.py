from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from app.market_data.official_nse_index_ohlc import CanonicalOfficialIndexOhlcObservation
from app.taxonomy.nse_sector_indices import NseSectorIndexMapping, SectorIndexMappingStatus
from app.universe_analysis.benchmark_sector_technical_input import (
    BenchmarkSectorTechnicalInputError,
    BenchmarkSectorTechnicalState,
    PeerCohortState,
    assemble_current_descriptive_benchmark_sector_input,
    canonical_sector_index_id,
)
from app.universe_analysis.service import Canonical61DiagnosticRunner, StockDiagnosticInputAssembler
from app.universe_analysis.technical_diagnostic_input import technical_diagnostic_readiness
from tests.unit.test_technical_diagnostic_input import AT, StoredFacts, _input, _instrument


def _mapping(*, status=SectorIndexMappingStatus.EXACT_OFFICIAL):
    return NseSectorIndexMapping(
        "mapping:capital-goods", "Capital Goods", "Nifty Capital Goods",
        "https://www.niftyindices.com/indices/equity/sectoral-indices/nifty-capital-goods",
        status, ("OFFICIAL",), "a" * 64, AT,
    )


def _index_rows(index_id: str, name: str, technical, *, missing: bool = False):
    daily = technical.daily_snapshot
    assert daily is not None
    values = daily.observations[-3:] if missing else daily.observations
    rows = []
    for number, observation in enumerate(values):
        session = observation.provenance.market_timestamp
        rows.append(CanonicalOfficialIndexOhlcObservation.create(
            canonical_index_id=index_id, official_index_name=name, session=session,
            open=Decimal(100 + number), high=Decimal(102 + number), low=Decimal(99 + number), close=Decimal(101 + number),
            retrieved_at=AT, raw_artifact_sha256=("a" if index_id == "NIFTY_50" else "b") * 64,
        ))
    return tuple(rows)


def _context(*, mapping=_mapping(), missing_benchmark=False, missing_sector=False):
    technical = _input()
    sector_id = canonical_sector_index_id("Capital Goods")
    sector_rows = () if mapping.status is not SectorIndexMappingStatus.EXACT_OFFICIAL else _index_rows(
        sector_id, "Nifty Capital Goods", technical, missing=missing_sector,
    )
    return assemble_current_descriptive_benchmark_sector_input(
        canonical_instrument_id=_instrument().instrument_id, as_of=AT, technical_input=technical,
        benchmark_observations=_index_rows("NIFTY_50", "Nifty 50", technical, missing=missing_benchmark),
        sector_mapping=mapping, sector_observations=sector_rows,
    )


def test_context_uses_exact_governed_pri_indices_and_current_peer_state_is_not_applicable() -> None:
    context = _context()
    assert context.benchmark_state is BenchmarkSectorTechnicalState.READY
    assert context.sector_state is BenchmarkSectorTechnicalState.READY
    assert context.peer_cohort_state is PeerCohortState.NOT_APPLICABLE
    assert context.strict_historical_pit_state.value == "NOT_READY"
    for rule_id in (1, 2, 3, 6):
        snapshot, reason, sector = context.rule_input(rule_id)
        assert snapshot is not None and reason is None
        assert sector == canonical_sector_index_id("Capital Goods") if rule_id in {2, 3, 6} else sector is None
    assert all("volume" not in item.payload for item in context.combined_snapshot.observations if item.instrument.id.startswith("NSE_SECTOR_INDEX") or item.instrument.id == "NIFTY_50")


def test_missing_session_and_unmapped_sector_fail_closed_without_fill() -> None:
    context = _context(missing_benchmark=True)
    assert context.rule_input(1)[1] == "BENCHMARK_HISTORY_NOT_READY"
    context = _context(missing_sector=True)
    assert context.rule_input(2)[1] == "SECTOR_HISTORY_NOT_READY"
    assert context.rule_input(6)[0] is not None  # current evaluator does not gate its classification on sector/peers
    context = _context(mapping=_mapping(status=SectorIndexMappingStatus.NO_OFFICIAL_SECTOR_INDEX))
    assert context.rule_input(2)[1] == "SECTOR_INDEX_NOT_MAPPED"
    assert context.rule_input(6)[0] is not None
    with pytest.raises(BenchmarkSectorTechnicalInputError, match="OBSERVATIONS_UNMAPPED"):
        assemble_current_descriptive_benchmark_sector_input(
            canonical_instrument_id=_instrument().instrument_id, as_of=AT, technical_input=_input(),
            benchmark_observations=_index_rows("NIFTY_50", "Nifty 50", _input()),
            sector_mapping=_mapping(status=SectorIndexMappingStatus.NO_OFFICIAL_SECTOR_INDEX),
            sector_observations=_index_rows(canonical_sector_index_id("Capital Goods"), "Nifty Capital Goods", _input()),
        )


def test_rule_six_rejects_one_missing_stock_window_session_without_forward_fill() -> None:
    technical = _input()
    benchmark = list(_index_rows("NIFTY_50", "Nifty 50", technical))
    benchmark.pop(-2)
    context = assemble_current_descriptive_benchmark_sector_input(
        canonical_instrument_id=_instrument().instrument_id, as_of=AT, technical_input=technical,
        benchmark_observations=benchmark, sector_mapping=_mapping(),
        sector_observations=_index_rows(canonical_sector_index_id("Capital Goods"), "Nifty Capital Goods", technical),
    )
    assert context.benchmark_state is BenchmarkSectorTechnicalState.READY
    assert context.rule_input(6)[1] == "SESSION_ALIGNMENT_FAILED"


def test_runner_reuses_existing_evaluators_for_rules_1_to_3_and_6() -> None:
    technical = _input()
    context = _context()
    evidence = StockDiagnosticInputAssembler(StoredFacts()).assemble(
        _instrument(), AT, technical_input=technical, benchmark_sector_input=context,
    )
    run = Canonical61DiagnosticRunner().run(evidence)
    values = {item.canonical_rule_id: item for item in run.evaluations}
    assert all(values[rule].eligibility.value == "eligible" for rule in (1, 2, 3, 6))
    assert values[6].record.instrument_id == _instrument().instrument_id
    assert values[35].record.result == "INSUFFICIENT_DATA"
    assert values[57].record.result == "INSUFFICIENT_DATA"
    # The exact audit corrects an old readiness claim, not evaluator policy:
    # Rule 6 has no peer numeric/classification dependency.
    receipt = technical_diagnostic_readiness(technical, 6)
    assert "PEER_COHORT_NOT_READY" not in {item.value for item in receipt.blockers}
    source = (Path(__file__).parents[2] / "app" / "universe_analysis" / "benchmark_sector_technical_input.py").read_text(encoding="utf-8")
    assert "upstox" not in source.lower() and "datetime.now" not in source


def test_context_rejects_future_or_duplicate_index_lineage() -> None:
    technical = _input()
    benchmark = _index_rows("NIFTY_50", "Nifty 50", technical)
    with pytest.raises(BenchmarkSectorTechnicalInputError, match="LINEAGE_INVALID"):
        assemble_current_descriptive_benchmark_sector_input(
            canonical_instrument_id=_instrument().instrument_id, as_of=AT, technical_input=technical,
            benchmark_observations=(*benchmark, benchmark[-1]), sector_mapping=None,
        )


def test_newer_sector_tail_selects_exact_benchmark_endpoint_without_rewriting_history():
    technical = _input()
    benchmark = _index_rows("NIFTY_50", "Nifty 50", technical)
    sector = _index_rows(canonical_sector_index_id("Capital Goods"), "Nifty Capital Goods", technical)
    newer = CanonicalOfficialIndexOhlcObservation.create(
        canonical_index_id=sector[-1].canonical_index_id, official_index_name="Nifty Capital Goods",
        session=sector[-1].session + timedelta(days=1),
        open=Decimal(999), high=Decimal(1001), low=Decimal(998), close=Decimal(1000),
        retrieved_at=AT, raw_artifact_sha256="c" * 64,
    )
    supplied = (*sector, newer)
    context = assemble_current_descriptive_benchmark_sector_input(
        canonical_instrument_id=_instrument().instrument_id, as_of=AT, technical_input=technical,
        benchmark_observations=benchmark, sector_mapping=_mapping(), sector_observations=supplied,
    )
    assert context.sector_state is BenchmarkSectorTechnicalState.READY
    assert context.sector_observations == sector and supplied[-1] is newer
    assert context.fingerprint == _context().fingerprint
    assert all(context.rule_input(rule)[1] is None for rule in (2,3))
    assert newer.observation_id not in {o.id for o in context.combined_snapshot.observations}


def test_alignment_does_not_backfill_missing_sector_session_or_hide_future_lineage():
    technical = _input()
    benchmark = _index_rows("NIFTY_50", "Nifty 50", technical)
    sector = _index_rows(canonical_sector_index_id("Capital Goods"), "Nifty Capital Goods", technical)
    context = assemble_current_descriptive_benchmark_sector_input(
        canonical_instrument_id=_instrument().instrument_id, as_of=AT, technical_input=technical,
        benchmark_observations=benchmark, sector_mapping=_mapping(), sector_observations=sector[:-2]+sector[-1:],
    )
    assert context.rule_input(2)[1] == "SECTOR_HISTORY_NOT_READY"
    future = CanonicalOfficialIndexOhlcObservation.create(
        canonical_index_id=sector[-1].canonical_index_id, official_index_name="Nifty Capital Goods",
        session=AT + timedelta(days=1), open=Decimal(100), high=Decimal(102), low=Decimal(99), close=Decimal(101),
        retrieved_at=AT + timedelta(days=2), raw_artifact_sha256="c" * 64,
    )
    with pytest.raises(BenchmarkSectorTechnicalInputError, match="LINEAGE_INVALID"):
        assemble_current_descriptive_benchmark_sector_input(
            canonical_instrument_id=_instrument().instrument_id, as_of=AT, technical_input=technical,
            benchmark_observations=benchmark, sector_mapping=_mapping(), sector_observations=(*sector,future),
        )
