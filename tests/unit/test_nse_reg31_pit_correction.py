from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

import pytest

from app.data_operations.nse_reg31_pit_correction import (
    NseReg31PitTimestampCorrectionService, NseReg31PitTimestampCorrectionStore,
    _Target, is_pit_timestamp_correction,
)
from app.filings.models import CorporateFiling, FilingTextAvailability, FilingType, PrimarySourceQuality
from app.filings.store import SQLiteCorporateFilingsStore
from app.market_data.models import Exchange, InstrumentIdentity, InstrumentType, MarketDataProvenance
from app.storage.core_api_snapshot_repository import CoreApiSnapshotFamily
from app.storage.database import DatabaseBackend, DatabaseSettings
from app.storage.repository_factory import create_core_api_snapshot_repository


CREATED = datetime(2026, 9, 1, 6, tzinfo=UTC)
PERIOD = datetime(2026, 6, 30, tzinfo=UTC)


def _fixture(tmp_path: Path):
    source = tmp_path / "nse"; source.mkdir()
    filings = SQLiteCorporateFilingsStore(tmp_path / "filings.sqlite")
    repository = create_core_api_snapshot_repository(DatabaseSettings(DatabaseBackend.SQLITE, f"sqlite:///{tmp_path / 'core.sqlite'}"))
    targets: list[_Target] = []; originals: list[CorporateFiling] = []
    symbols = ("APARINDS", "DEEPINDS", "GENUSPOWER", "GLAND", "ICICIBANK")
    isins = ("INE372A01015", "INE0FHS01024", "INE955D01029", "INE068V01023", "INE090A01021")
    for index, (symbol, isin) in enumerate(zip(symbols, isins), start=1):
        raw = f"<xbrl>{symbol}</xbrl>".encode(); digest = sha256(raw).hexdigest()
        old = datetime(2026, 7, 17, 13, 54, 20 + index, tzinfo=UTC)
        filing_id = f"nse:NSE:reg31-xbrl:{index}"; filename = f"SHP-Reg31-equities-{symbol}-2026-06-30-{index}.xml"
        url = f"https://nsearchives.nseindia.com/corporate/xbrl/SHP_{index}_17072026.xml"
        (source / filename).write_bytes(raw)
        manifest = {"filename": filename, "sha256": digest, "source_url": url, "official_publication_timestamp": old.isoformat()}
        (source / (filename + ".provenance.json")).write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
        instrument = InstrumentIdentity("NSE:" + isin, Exchange.NSE, symbol, symbol, isin, None, InstrumentType.NSE_EQUITY, symbol)
        provenance = MarketDataProvenance("NSE", f"reg31-xbrl:{index}", old, old, CREATED, "nse-official-export-v1", "fixture", url)
        original = CorporateFiling(filing_id, instrument, Exchange.NSE, "NSE", PrimarySourceQuality.PRIMARY_EXCHANGE, FilingType.SHAREHOLDING_PATTERN, "REGULATION_31_SHAREHOLDING_PATTERN", "fixture", old, CREATED, f"reg31-xbrl:{index}", url, provenance, period_end=PERIOD, text_availability=FilingTextAvailability.SOURCE_TEXT, warnings=("NSE_REG31_ARTIFACT_SHA256:" + digest,))
        filings.save(original); originals.append(original)
        targets.append(_Target(instrument.instrument_id, filing_id, digest, "2026-06-30", filename))
    service = NseReg31PitTimestampCorrectionService(filings=filings, corrections=NseReg31PitTimestampCorrectionStore(repository), source_directory=source, targets=tuple(targets), clock=lambda: CREATED)
    return service, filings, repository, tuple(targets), tuple(originals), source


def test_exact_five_append_only_corrections_resolve_one_effective_pit_view_and_are_idempotent(tmp_path: Path) -> None:
    service, filings, repository, targets, originals, source = _fixture(tmp_path)
    first = service.apply()
    assert [item.status for item in first] == ["INSERTED"] * 5
    assert len(repository.list_snapshots(CoreApiSnapshotFamily.RECONCILIATION_RESULT, limit=20)) == 5
    for target, original, outcome in zip(targets, originals, first):
        corrected = filings.get(outcome.corrected_filing_id)
        assert corrected is not None and corrected.revision_of_filing_id == original.filing_id and is_pit_timestamp_correction(corrected)
        assert filings.get(original.filing_id) == original and len(filings.revisions(original.filing_id)) == 1
        corrected_at = datetime(2026, 7, 17, 8, 24, 20 + int(original.filing_id.rsplit(":", 1)[-1]), tzinfo=UTC)
        assert corrected.announced_at == corrected_at and corrected.provenance.received_at == CREATED
        assert filings.list(instrument_id=target.canonical_instrument_id, as_of=corrected_at - timedelta(microseconds=1), limit=10) == ()
        between = filings.list(instrument_id=target.canonical_instrument_id, as_of=corrected_at, limit=10)
        after = filings.list(instrument_id=target.canonical_instrument_id, as_of=original.announced_at, limit=10)
        assert [item.filing_id for item in between] == [corrected.filing_id] == [item.filing_id for item in after]
        manifest = source / f"{target.artifact_filename}.metadata-correction-v1.json"
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        assert payload["raw_sha256"] == target.raw_sha256 and payload["supersedes_filing_id"] == original.filing_id
    assert [item.status for item in service.apply()] == ["IDENTICAL"] * 5


def test_correction_requires_exactly_five_and_rejects_any_raw_or_target_mismatch(tmp_path: Path) -> None:
    service, _filings, _repository, targets, _originals, source = _fixture(tmp_path)
    too_few = NseReg31PitTimestampCorrectionService(filings=service._filings, corrections=service._corrections, source_directory=source, targets=targets[:4], clock=lambda: CREATED)
    with pytest.raises(ValueError, match="EXACT_FIVE_REQUIRED"):
        too_few.apply()
    changed = (*targets[:4], _Target(targets[-1].canonical_instrument_id, targets[-1].filing_id, "0" * 64, targets[-1].reporting_period_end, targets[-1].artifact_filename))
    conflict = NseReg31PitTimestampCorrectionService(filings=service._filings, corrections=service._corrections, source_directory=source, targets=changed, clock=lambda: CREATED)
    with pytest.raises(ValueError, match="RAW_HASH_MISMATCH"):
        conflict.apply()
    assert list(source.glob("*.metadata-correction-v1.json")) == []


def test_correction_fingerprint_is_deterministic_and_original_source_timestamp_text_is_retained(tmp_path: Path) -> None:
    service, _filings, repository, _targets, _originals, _source = _fixture(tmp_path)
    first = service.apply(); values = [NseReg31PitTimestampCorrectionStore(repository).get(item.correction_id) for item in first]
    assert all(value is not None for value in values)
    assert [value.fingerprint for value in values] == [NseReg31PitTimestampCorrectionStore(repository).get(item.correction_id).fingerprint for item in first]
    assert values[-1].original_source_timestamp_text == "17-JUL-2026 13:54:25"
    assert values[-1].timezone_interpretation == "Asia/Kolkata"
