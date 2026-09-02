from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.market_data.dhan import DhanInstrumentMaster, DhanInstrumentRecord, parse_dhan_instrument_master
from app.market_data.dhan_mapping import (
    DhanMappingStatus,
    DhanProviderMappingService,
    current_dhan_targets,
)
from app.runtime.cli import parser
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository
from app.universe_analysis.models import NseEquityInstrument
from app.universe_analysis.service import CoreUniverseAnalysisStore


T = datetime(2026, 9, 1, 10, tzinfo=UTC)


class _Portfolio:
    def __init__(self, identifiers: tuple[str, ...]) -> None:
        self._snapshot = SimpleNamespace(holdings=tuple(
            SimpleNamespace(instrument_id=item, active=True) for item in identifiers
        ))

    def get_snapshot(self):
        return self._snapshot


class _Top3Runs:
    def __init__(self, identifiers: tuple[str, ...]) -> None:
        self._run = SimpleNamespace(candidate_ids=identifiers)

    def list(self):
        return (self._run,)


class _Setups:
    def __init__(self, identifiers: tuple[str, ...]) -> None:
        self._values = tuple(SimpleNamespace(canonical_instrument_id=item) for item in identifiers)

    def list(self, *, as_of):
        return self._values


def _instrument(index: int) -> NseEquityInstrument:
    return NseEquityInstrument(
        f"NSE:INE{index:07d}A01", f"SYM{index:02d}", f"INE{index:07d}A01", "Sector", None,
        "ACTIVE", None, True, T, "fixture", security_type="EQUITY", company_name=f"Company {index}",
    )


def _master(instruments: tuple[NseEquityInstrument, ...]) -> DhanInstrumentMaster:
    return DhanInstrumentMaster(
        "https://images.dhan.co/api-data/api-scrip-master-detailed.csv", "a" * 64,
        tuple(DhanInstrumentRecord(index + 1000, "NSE", "EQ", item.isin, item.symbol, "EQUITY", item.company_name)
              for index, item in enumerate(instruments)), T,
    )


def _official_rows() -> tuple[NseEquityInstrument, DhanInstrumentRecord]:
    """Representative non-secret rows from the official detailed-master schema."""
    csv = """EXCH_ID,SEGMENT,SECURITY_ID,ISIN,INSTRUMENT,SYMBOL_NAME,DISPLAY_NAME,INSTRUMENT_TYPE,SERIES\nNSE,E,11491,INE372A01015,EQUITY,APAR INDUSTRIES LTD.,Apar Industries,ES,EQ\nNSE,E,3292,INE0FHS01024,EQUITY,DEEP INDUSTRIES LIMITED,Deep Industries,ES,EQ\nNSE,E,11905,INE955D01029,EQUITY,GENUS POWER INFRASTRU LTD,Genus Power Infrastructure,ES,EQ\nNSE,E,1186,INE068V01023,EQUITY,GLAND PHARMA LIMITED,Gland Pharma,ES,EQ\nNSE,E,4963,INE090A01021,EQUITY,ICICI BANK LTD.,ICICI Bank,ES,EQ\n"""
    records = parse_dhan_instrument_master(csv)
    instruments = (
        NseEquityInstrument("NSE:INE372A01015", "APARINDS", "INE372A01015", None, None, "ACTIVE", None, True, T, "fixture"),
        NseEquityInstrument("NSE:INE0FHS01024", "DEEPINDS", "INE0FHS01024", None, None, "ACTIVE", None, True, T, "fixture"),
        NseEquityInstrument("NSE:INE955D01029", "GENUSPOWER", "INE955D01029", None, None, "ACTIVE", None, True, T, "fixture"),
        NseEquityInstrument("NSE:INE068V01023", "GLAND", "INE068V01023", None, None, "ACTIVE", None, True, T, "fixture"),
        NseEquityInstrument("NSE:INE090A01021", "ICICIBANK", "INE090A01021", None, None, "ACTIVE", None, True, T, "fixture"),
    )
    return instruments, records


def test_official_detailed_master_normalizes_raw_equity_schema_without_conflation(tmp_path) -> None:
    instruments, records = _official_rows()
    assert {(item.exchange, item.segment, item.instrument, item.raw_instrument_type, item.series) for item in records} == {("NSE", "E", "EQUITY", "ES", "EQ")}
    assert {item.trading_symbol for item in records} == {None}  # descriptive SYMBOL_NAME is not a ticker alias
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "dhan-official.sqlite")
    universe = CoreUniverseAnalysisStore(repository)
    for item in instruments:
        universe.save_instrument(item)
    targets = current_dhan_targets(
        portfolio=_Portfolio(tuple(item.instrument_id for item in instruments)), top3_runs=_Top3Runs(()),
    )
    master = DhanInstrumentMaster("official", "d" * 64, records, T)
    result = DhanProviderMappingService(universe).materialize(targets=targets, master=master, as_of=T)
    assert result.created_count == 5 and result.blocked_count == 0
    stored = universe.provider_mappings(provider="DHAN", as_of=T)
    assert {item.provider_exchange_segment for item in stored} == {"NSE_EQ"}
    assert {item.normalized_instrument for item in stored} == {"EQUITY"}
    assert {(item.raw_provider_exchange, item.raw_provider_segment, item.raw_provider_instrument, item.raw_provider_instrument_type, item.raw_provider_series) for item in stored} == {("NSE", "E", "EQUITY", "ES", "EQ")}
    repository.close()


def test_current_target_union_materializes_48_exact_immutable_mappings_idempotently(tmp_path) -> None:
    instruments = tuple(_instrument(index) for index in range(48))
    portfolio_ids = tuple(item.instrument_id for item in instruments[:5])
    top3_ids = tuple(item.instrument_id for item in instruments[5:])
    targets = current_dhan_targets(portfolio=_Portfolio(portfolio_ids), top3_runs=_Top3Runs(top3_ids))
    assert targets.portfolio_ids == tuple(sorted(portfolio_ids))
    assert targets.top3_ids == tuple(sorted(top3_ids)) and targets.count == 48

    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "dhan-mapping.sqlite")
    universe = CoreUniverseAnalysisStore(repository)
    for item in instruments:
        universe.save_instrument(item)
    service = DhanProviderMappingService(universe)
    first = service.materialize(targets=targets, master=_master(instruments), as_of=T)
    second = service.materialize(targets=targets, master=_master(instruments), as_of=T)

    assert first.created_count == 48 and first.blocked_count == 0
    assert second.created_count == second.blocked_count == 0 and second.identical_count == 48
    stored = universe.provider_mappings(provider="DHAN", as_of=T)
    assert len(stored) == 48
    assert all(item.mapping_id.startswith("mapping:dhan:") and item.source_checksum == "a" * 64 for item in stored)
    assert all(item.raw_provider_instrument == "EQUITY" and item.provider_name for item in stored)
    assert service.ltp_targets(targets=targets, as_of=T)[0].security_id == 1000
    repository.close()


def test_current_target_union_includes_existing_setup_monitoring_and_deduplicates_exact_ids() -> None:
    targets = current_dhan_targets(
        portfolio=_Portfolio(("NSE:PORT",)), top3_runs=_Top3Runs(("NSE:SCAN", "NSE:PORT")),
        setup_opportunities=_Setups(("NSE:SETUP", "NSE:PORT")), as_of=T,
    )
    assert targets.portfolio_ids == ("NSE:PORT",)
    assert targets.top3_ids == ("NSE:PORT", "NSE:SCAN")
    assert targets.setup_ids == ("NSE:PORT", "NSE:SETUP")
    assert targets.canonical_instrument_ids == ("NSE:PORT", "NSE:SCAN", "NSE:SETUP")


def test_dhan_ltp_canary_scope_is_five_by_default_and_all_targets_is_explicit() -> None:
    assert parser().parse_args(["dhan-ltp-canary"]).scope == "portfolio"
    assert parser().parse_args(["dhan-ltp-canary", "--scope", "all-current-targets"]).scope == "all-current-targets"


def test_new_master_version_does_not_silently_rewrite_a_dhan_mapping(tmp_path) -> None:
    instrument = _instrument(0)
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "dhan-immutable.sqlite")
    universe = CoreUniverseAnalysisStore(repository); universe.save_instrument(instrument)
    target = current_dhan_targets(portfolio=_Portfolio((instrument.instrument_id,)), top3_runs=_Top3Runs(()))
    service = DhanProviderMappingService(universe)
    first_master = _master((instrument,))
    assert service.materialize(targets=target, master=first_master, as_of=T).created_count == 1
    changed_master = DhanInstrumentMaster(first_master.source_url, "c" * 64, first_master.records, T)
    outcome = service.materialize(targets=target, master=changed_master, as_of=T).outcomes[0]
    assert outcome.status is DhanMappingStatus.EXISTING_MAPPING_CONFLICT
    stored = universe.provider_mappings(provider="DHAN", as_of=T)
    assert len(stored) == 1 and stored[0].source_checksum == "a" * 64
    repository.close()


def test_dhan_live_ltp_requires_a_persisted_mapping(tmp_path) -> None:
    instrument = _instrument(0)
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "dhan-missing.sqlite")
    universe = CoreUniverseAnalysisStore(repository); universe.save_instrument(instrument)
    target = current_dhan_targets(portfolio=_Portfolio((instrument.instrument_id,)), top3_runs=_Top3Runs(()))
    with pytest.raises(ValueError, match="DHAN_CURRENT_TARGET_MAPPING_MISSING"):
        DhanProviderMappingService(universe).ltp_targets(targets=target, as_of=T)
    repository.close()


@pytest.mark.parametrize(
    ("records", "expected"),
    (
        ((DhanInstrumentRecord(1000, "NSE", "FO", "INE0000000A01", "SYM00", "FUTIDX", "Company"),), DhanMappingStatus.SECURITY_CLASS_MISMATCH),
        ((DhanInstrumentRecord(1000, "NSE", "EQ", "INE0000000A01", "OTHER", "EQUITY", "Company"),), DhanMappingStatus.SYMBOL_CONFLICT),
        ((DhanInstrumentRecord(1000, "NSE", "EQ", "INE0000000A01", "SYM00", "EQUITY", "Company"), DhanInstrumentRecord(1001, "NSE", "EQ", "INE0000000A01", "SYM00", "EQUITY", "Company")), DhanMappingStatus.AMBIGUOUS_PROVIDER_IDENTITY),
    ),
)
def test_dhan_mapping_fails_closed_for_security_symbol_and_ambiguity(tmp_path, records, expected) -> None:
    instrument = _instrument(0)
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "dhan-reject.sqlite")
    universe = CoreUniverseAnalysisStore(repository); universe.save_instrument(instrument)
    target = current_dhan_targets(portfolio=_Portfolio((instrument.instrument_id,)), top3_runs=_Top3Runs(()))
    master = DhanInstrumentMaster("https://images.dhan.co/api-data/api-scrip-master-detailed.csv", "b" * 64, records, T)
    outcome = DhanProviderMappingService(universe).materialize(targets=target, master=master, as_of=T).outcomes[0]
    assert outcome.status is expected
    assert universe.provider_mappings(provider="DHAN", as_of=T) == ()
    repository.close()
