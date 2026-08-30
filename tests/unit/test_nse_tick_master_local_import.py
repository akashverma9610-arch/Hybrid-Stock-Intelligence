from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
import gzip

import pytest

from app.market_data.reference_data.nse_master import NseTickMasterLocalImporter
from app.market_data.reference_data.sqlite_repository import SQLiteTickSizeObservationRepository
from app.market_data.reference_data.tick_size import (
    TickSizeAvailabilitySemantics,
    TickSizeSourceClass,
)
from app.runtime.cli import main
from app.universe_analysis.models import NseEquityInstrument


OBSERVED = datetime(2026, 8, 28, 16, tzinfo=UTC)


def canonical(symbol: str = "RELIANCE", isin: str = "INE002A01018", instrument_id: str = "NSE:RELIANCE") -> NseEquityInstrument:
    return NseEquityInstrument(
        instrument_id=instrument_id, symbol=symbol, isin=isin, sector=None, industry=None,
        listing_status="LISTED", listing_date=None, tradable=True, data_as_of=OBSERVED,
        source="NSE_UNIVERSE", security_type="EQUITY", exchange="NSE",
    )


def master_row(
    *, token: str = "500325", symbol: str = "RELIANCE", series: str = "EQ",
    instrument_type: str = "0", tick: str = "5", deleted: str = "N", isin: str = "INE002A01018",
) -> str:
    fields = [""] * 43
    fields[0], fields[1], fields[2], fields[3] = token, symbol, series, instrument_type
    fields[5], fields[9], fields[40], fields[42] = "1", tick, deleted, isin
    return "|".join(fields)


def master(*rows: str) -> bytes:
    return ("NEATCM|01.00.00|1470000000\n" + "\n".join(rows) + "\n").encode()


def importer(tmp_path, *instruments: NseEquityInstrument):
    repository = SQLiteTickSizeObservationRepository(tmp_path / "ticks.sqlite")
    return NseTickMasterLocalImporter(repository, instruments), repository


def write_master(tmp_path, content: bytes, *, gz: bool = False):
    path = tmp_path / ("security.gz" if gz else "security.txt")
    path.write_bytes(gzip.compress(content) if gz else content)
    return path


@pytest.mark.parametrize("raw_tick, expected", [("5", Decimal("0.05")), ("10", Decimal("0.10")), ("100", Decimal("1"))])
def test_documented_security_txt_decodes_paise_and_persists_official_evidence(tmp_path, raw_tick, expected) -> None:
    service, repository = importer(tmp_path, canonical())
    path = write_master(tmp_path, master(master_row(tick=raw_tick)))
    report = service.import_file(path, observed_at=OBSERVED)
    assert report.accepted == 1
    value = repository.list_tick_size_observations()[0]
    assert value.tick_size == expected
    assert value.source_class is TickSizeSourceClass.OFFICIAL_EXCHANGE
    assert value.source_name == "NSE/NDAL Masters Data CM"
    assert value.availability_semantics is TickSizeAvailabilitySemantics.FIRST_OBSERVED_ONLY
    assert value.eligible_from == OBSERVED
    assert not value.is_eligible_as_of(OBSERVED - timedelta(seconds=1))
    assert value.is_eligible_as_of(OBSERVED)


def test_documented_security_gz_parses_locally_with_exact_identity(tmp_path) -> None:
    service, repository = importer(tmp_path, canonical())
    report = service.import_file(write_master(tmp_path, master(master_row()), gz=True), observed_at=OBSERVED)
    assert report.accepted == 1
    value = repository.list_tick_size_observations()[0]
    assert value.canonical_instrument_id == "NSE:RELIANCE"
    assert value.isin == "INE002A01018"
    assert value.source_artifact_fingerprint == report.source_fingerprint
    assert "SOURCE_FILE:security.gz" in value.warnings
    assert "SOURCE_HEADER_DATE_SECONDS:1470000000" in value.warnings


def test_deterministic_same_artifact_reimport_is_idempotent_and_reopens(tmp_path) -> None:
    path = write_master(tmp_path, master(master_row()))
    service, repository = importer(tmp_path, canonical())
    first = service.import_file(path, observed_at=OBSERVED)
    second = service.import_file(path, observed_at=OBSERVED)
    assert first.accepted == 1
    assert second.accepted == 0
    assert second.duplicates == 1
    first_value = repository.list_tick_size_observations()[0]
    repository.close()
    reopened = SQLiteTickSizeObservationRepository(tmp_path / "ticks.sqlite")
    assert reopened.get_tick_size_observation(first_value.record_id) == first_value


def test_unresolved_identity_is_not_persisted(tmp_path) -> None:
    service, repository = importer(tmp_path, canonical())
    report = service.import_file(write_master(tmp_path, master(master_row(isin="INE009A01021"))), observed_at=OBSERVED)
    assert report.unresolved_identity == 1
    assert report.accepted == 0
    assert repository.list_tick_size_observations() == ()


@pytest.mark.parametrize("tick", ["", "0", "-5", "five", "5.0"])
def test_missing_zero_negative_or_malformed_tick_is_rejected_per_row(tmp_path, tick) -> None:
    service, repository = importer(tmp_path, canonical())
    report = service.import_file(write_master(tmp_path, master(master_row(tick=tick))), observed_at=OBSERVED)
    assert report.invalid_tick == 1
    assert report.accepted == 0
    assert repository.list_tick_size_observations() == ()


def test_identical_duplicate_source_row_is_deterministic_but_conflicting_tick_fails_closed(tmp_path) -> None:
    service, repository = importer(tmp_path, canonical())
    identical = service.import_file(
        write_master(tmp_path, master(master_row(), master_row())), observed_at=OBSERVED
    )
    assert identical.accepted == 1
    assert identical.duplicates == 1

    conflict_dir = tmp_path / "conflict"
    conflict_dir.mkdir()
    conflict_service, conflict_repository = importer(conflict_dir, canonical())
    conflict_path = write_master(conflict_dir, master(master_row(tick="5"), master_row(tick="10")))
    conflict = conflict_service.import_file(conflict_path, observed_at=OBSERVED)
    assert conflict.conflicts == 1
    assert conflict.accepted == 0
    assert conflict_repository.list_tick_size_observations() == ()


@pytest.mark.parametrize(
    "row",
    [
        master_row(series="BE"),
        master_row(instrument_type="1"),
        master_row(deleted="Y"),
        master_row(isin="NOT-AN-ISIN"),
    ],
)
def test_non_cash_or_malformed_identity_rows_are_rejected(tmp_path, row) -> None:
    service, repository = importer(tmp_path, canonical())
    report = service.import_file(write_master(tmp_path, master(row)), observed_at=OBSERVED)
    assert report.malformed == 1
    assert report.accepted == 0
    assert repository.list_tick_size_observations() == ()


def test_wrong_documented_schema_fails_the_entire_import(tmp_path) -> None:
    service, repository = importer(tmp_path, canonical())
    path = write_master(tmp_path, b"NEATCM|1.0|1470000000\n1|RELIANCE|EQ\n")
    with pytest.raises(ValueError, match="NSE_TICK_MASTER_SCHEMA_UNSUPPORTED"):
        service.import_file(path, observed_at=OBSERVED)
    assert repository.list_tick_size_observations() == ()


def test_observed_at_must_be_aware_and_record_identity_changes_forward_only(tmp_path) -> None:
    path = write_master(tmp_path, master(master_row()))
    service, repository = importer(tmp_path, canonical())
    with pytest.raises(ValueError, match="NSE_TICK_OBSERVED_AT_NAIVE"):
        service.import_file(path, observed_at=datetime(2026, 8, 28, 16))
    first = service.import_file(path, observed_at=OBSERVED)
    later = service.import_file(path, observed_at=OBSERVED + timedelta(days=1))
    assert first.accepted == later.accepted == 1
    values = repository.list_tick_size_observations()
    assert len(values) == 2
    assert values[0].record_id != values[1].record_id


def test_importer_has_no_resolver_or_grid_or_provider_api(tmp_path) -> None:
    service, _ = importer(tmp_path, canonical())
    methods = set(type(service).__dict__)
    assert not {"get_tick_size_as_of", "resolve", "validate_price_grid", "download", "fetch"} & methods


def test_cli_imports_only_the_explicit_local_master_file(tmp_path) -> None:
    service, repository = importer(tmp_path, canonical())
    path = write_master(tmp_path, master(master_row()))
    output: list[str] = []
    result = main(
        ["import-nse-tick-master", str(path), "--observed-at", OBSERVED.isoformat()],
        nse_tick_master_importer_factory=lambda: (service, repository),
        output=output.append,
    )
    assert result == 0
    assert any("accepted=1" in line for line in output)
    reopened = SQLiteTickSizeObservationRepository(tmp_path / "ticks.sqlite")
    assert len(reopened.list_tick_size_observations()) == 1
