from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import pytest

from app.filings.store import SQLiteCorporateFilingsStore
from app.fundamentals.store import SQLiteFinancialFactStore
from app.market_data.models import Exchange, InstrumentIdentity, InstrumentType
from app.nse_import.service import (
    ExportFamily, FrozenCohortInstrumentResolver, ImportRunStore,
    NSEOfficialExportProvider, OfficialExchangeImportService,
)


T = datetime(2026, 9, 1, 10, tzinfo=UTC)
IDENTITY = InstrumentIdentity("NSE:APAR", Exchange.NSE, "APARINDS", "APARINDS", "INE372A01015", None, InstrumentType.NSE_EQUITY, "Apar Industries Limited")


def _xbrl(*, isin: str = IDENTITY.isin, symbol: str = IDENTITY.symbol, issuer: str = IDENTITY.name, period: str = "2026-08-13", schema: str = "in-bse-shp-2025-10-31.xsd") -> bytes:
    return f'''<?xml version="1.0"?><xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:link="http://www.xbrl.org/2003/linkbase" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:shp="urn:shp"><link:schemaRef xlink:href="{schema}" xlink:type="simple"/><xbrli:context id="MainI"><xbrli:period><xbrli:instant>{period}</xbrli:instant></xbrli:period></xbrli:context><shp:ISIN>{isin}</shp:ISIN><shp:Symbol>{symbol}</shp:Symbol><shp:NameOfTheCompany>{issuer}</shp:NameOfTheCompany><shp:ShareholdingPattern>lineage only</shp:ShareholdingPattern></xbrli:xbrl>'''.encode()


def _stage(tmp_path: Path, content: bytes, **overrides: object) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    artifact = tmp_path / "SHP-Reg31-equities-APARINDS-2026-08-13-213063.xml"
    artifact.write_bytes(content)
    manifest: dict[str, object] = {
        "provider": "NSE_OFFICIAL", "source_url": "https://nsearchives.nseindia.com/corporate/xbrl/SHP_1716338_20082026031300_WEB.xml",
        "symbol": "APARINDS", "isin": "INE372A01015", "canonical_instrument_id": "NSE:APAR",
        "issuer": "Apar Industries Limited", "reporting_period_end": "2026-08-13",
        "official_publication_timestamp": "2026-08-20T09:43:12+00:00", "retrieved_at": "2026-09-01T10:00:00+00:00",
        "official_document_id": "213063", "file_format": "XBRL/XML", "filing_type": "REGULATION_31_SHAREHOLDING_PATTERN",
        "filename": artifact.name, "sha256": sha256(content).hexdigest(),
    }
    manifest.update(overrides)
    artifact.with_suffix(".xml.provenance.json").write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    return artifact


def _service(tmp_path: Path):
    filings = SQLiteCorporateFilingsStore(tmp_path / "filings.sqlite")
    facts = SQLiteFinancialFactStore(tmp_path / "facts.sqlite")
    resolver = FrozenCohortInstrumentResolver((IDENTITY,), (IDENTITY.instrument_id,))
    return OfficialExchangeImportService(NSEOfficialExportProvider(), resolver, filings, facts, ImportRunStore(tmp_path / "runs.sqlite"), clock=lambda: T), filings, facts


def test_official_current_reg31_xbrl_import_is_pit_safe_raw_byte_preserving_and_idempotent(tmp_path: Path) -> None:
    raw = _xbrl(); path = _stage(tmp_path, raw); importer, filings, facts = _service(tmp_path)
    _path, checksum, _family, _rows = NSEOfficialExportProvider().read(path, family=ExportFamily.REGULATION_31)
    report = importer.import_file(path, family=ExportFamily.REGULATION_31)
    stored = filings.list(instrument_id=IDENTITY.instrument_id, as_of=T, limit=10)
    before_publication = filings.list(instrument_id=IDENTITY.instrument_id, as_of=datetime(2026, 8, 20, 9, 43, 11, tzinfo=UTC), limit=10)
    assert checksum == sha256(raw).hexdigest() and (report.accepted, report.conflicts, report.rejected, report.duplicates) == (1, 0, 0, 0)
    assert len(stored) == 1 and not before_publication
    assert stored[0].document_reference.endswith("SHP_1716338_20082026031300_WEB.xml")
    assert f"NSE_REG31_ARTIFACT_SHA256:{checksum}" in stored[0].warnings
    assert facts.facts(IDENTITY.instrument_id, limit=10) == ()
    assert importer.import_file(path, family=ExportFamily.REGULATION_31).duplicates == 1


@pytest.mark.parametrize(("raw", "manifest", "reason"), [
    (b"<html>error</html>", {}, "REG31_XBRL_UNSUPPORTED_STRUCTURE"),
    (b"<xbrl", {}, "REG31_XBRL_MALFORMED"),
    (_xbrl(isin="INE000A01001"), {}, "REG31_XBRL_IDENTITY_MISMATCH"),
    (_xbrl(symbol="WRONG"), {}, "REG31_XBRL_SYMBOL_MISMATCH"),
    (_xbrl(issuer="Wrong Company"), {}, "REG31_XBRL_ISSUER_MISMATCH"),
    (_xbrl(period="2026-06-30"), {}, "REG31_XBRL_PERIOD_MISMATCH"),
    (_xbrl(schema="financial-results.xsd"), {}, "REG31_XBRL_FILING_TYPE_MISMATCH"),
    (_xbrl(), {"source_url": "https://example.invalid/x.xml"}, "REG31_XBRL_OFFICIAL_SOURCE_REQUIRED"),
])
def test_reg31_xbrl_rejections_are_typed_and_fail_closed(tmp_path: Path, raw: bytes, manifest: dict[str, object], reason: str) -> None:
    path = _stage(tmp_path, raw, **manifest)
    importer, filings, _facts = _service(tmp_path)
    with pytest.raises(ValueError, match=reason):
        importer.import_file(path, family=ExportFamily.REGULATION_31)
    assert filings.list(instrument_id=IDENTITY.instrument_id, as_of=T, limit=10) == ()


def test_arbitrary_xml_requires_official_provenance_manifest(tmp_path: Path) -> None:
    path = tmp_path / "untrusted.xml"; path.write_bytes(_xbrl())
    with pytest.raises(ValueError, match="REG31_XBRL_OFFICIAL_SOURCE_REQUIRED"):
        NSEOfficialExportProvider().read(path, family=ExportFamily.REGULATION_31)


def test_changed_current_reg31_xbrl_retains_raw_conflict_without_duplicate_filing(tmp_path: Path) -> None:
    first = _xbrl(); second = first.replace(b"lineage only", b"changed lineage")
    path = _stage(tmp_path, first); importer, filings, _facts = _service(tmp_path)
    assert importer.import_file(path, family=ExportFamily.REGULATION_31).accepted == 1
    changed = _stage(tmp_path / "changed", second)
    report = importer.import_file(changed, family=ExportFamily.REGULATION_31)
    assert report.conflicts == 1 and len(filings.list(instrument_id=IDENTITY.instrument_id, as_of=T, limit=10)) == 1


def test_rejected_current_xbrl_can_be_retried_after_a_resolver_block_without_replacing_completed_runs(tmp_path: Path) -> None:
    path = _stage(tmp_path, _xbrl()); filings = SQLiteCorporateFilingsStore(tmp_path / "filings.sqlite")
    runs = ImportRunStore(tmp_path / "runs.sqlite")
    blocked = OfficialExchangeImportService(NSEOfficialExportProvider(), FrozenCohortInstrumentResolver((), ()), filings, SQLiteFinancialFactStore(tmp_path / "facts.sqlite"), runs, clock=lambda: T)
    assert blocked.import_file(path, family=ExportFamily.REGULATION_31).unresolved_symbols == 1
    recovered = OfficialExchangeImportService(NSEOfficialExportProvider(), FrozenCohortInstrumentResolver((IDENTITY,), (IDENTITY.instrument_id,)), filings, SQLiteFinancialFactStore(tmp_path / "facts.sqlite"), ImportRunStore(tmp_path / "runs.sqlite"), clock=lambda: T)
    assert recovered.import_file(path, family=ExportFamily.REGULATION_31).accepted == 1
    assert recovered.import_file(path, family=ExportFamily.REGULATION_31).duplicates == 1


def test_deep_current_xbrl_identity_is_direct_and_icici_legacy_csv_cannot_be_used_as_current_xbrl(tmp_path: Path) -> None:
    deep = InstrumentIdentity("NSE:INE0FHS01024", Exchange.NSE, "DEEPINDS", "DEEPINDS", "INE0FHS01024", None, InstrumentType.NSE_EQUITY, "Deep Industries Limited")
    raw = _xbrl(isin=deep.isin, symbol=deep.symbol, issuer=deep.name)
    path = _stage(tmp_path, raw, symbol=deep.symbol, isin=deep.isin, canonical_instrument_id=deep.instrument_id, issuer=deep.name)
    importer = OfficialExchangeImportService(NSEOfficialExportProvider(), FrozenCohortInstrumentResolver((deep,), (deep.instrument_id,)), SQLiteCorporateFilingsStore(tmp_path / "deep.sqlite"), SQLiteFinancialFactStore(tmp_path / "deep-facts.sqlite"), ImportRunStore(tmp_path / "deep-runs.sqlite"), clock=lambda: T)
    assert importer.import_file(path, family=ExportFamily.REGULATION_31).accepted == 1
    legacy = _stage(tmp_path / "icici", _xbrl(isin="IN9090A01011", symbol="ICICIBANK", issuer="ICICI Bank Limited"), symbol="ICICIBANK", isin="INE090A01021", canonical_instrument_id="NSE:INE090A01021", issuer="ICICI Bank Limited")
    with pytest.raises(ValueError, match="REG31_XBRL_IDENTITY_MISMATCH"):
        NSEOfficialExportProvider().read(legacy, family=ExportFamily.REGULATION_31)
