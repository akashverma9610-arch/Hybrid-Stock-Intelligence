from datetime import UTC,datetime
from pathlib import Path
import pytest
from app.primary_market.importer import NSEOfficialPrimaryMarketExportProvider,OfficialPrimaryMarketImportService
from app.primary_market.store import SQLitePrimaryMarketStore
T=datetime(2026,8,23,tzinfo=UTC)
def test_official_local_export_normalizes_idempotently_and_rejects_unknown_schema(tmp_path):
 path=tmp_path/"issues.csv";path.write_text("Issue ID,Company,Issue Type,Published At,Open Date,Close Date,Issue Price,Total Issue Size,Fresh Issue,OFS\nI1,Alpha,MAINBOARD_IPO,2026-08-01T00:00:00Z,2026-08-02T00:00:00Z,2026-08-03T00:00:00Z,100,100,70,30\n",encoding="utf-8")
 service=OfficialPrimaryMarketImportService(NSEOfficialPrimaryMarketExportProvider(),SQLitePrimaryMarketStore(tmp_path/"pm.sqlite"),clock=lambda:T);first=service.import_file(path);second=service.import_file(path)
 assert first["accepted"]==1 and second["duplicates"]==1 and first["checksum"]
 bad=tmp_path/"bad.csv";bad.write_text("foo\nbar\n",encoding="utf-8")
 with pytest.raises(ValueError):NSEOfficialPrimaryMarketExportProvider().read(bad)
