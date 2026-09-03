from __future__ import annotations

import ast
from datetime import UTC, datetime
import inspect
import json
from pathlib import Path

from app.filings.store import SQLiteCorporateFilingsStore
from app.fundamentals.bse_official import BSEOfficialLocalXbrlIngestionService, parse_bse_xbrl
from app.fundamentals.bse_staged_annual_backfill import (
    BseStagedAnnualBackfillDisposition, BseStagedAnnualBackfillTarget,
    BseStagedAnnualFactBackfillService,
)
from app.fundamentals.models import FinancialMetric
from app.fundamentals.store import SQLiteFinancialFactStore
from app.market_data.models import Exchange, InstrumentIdentity, InstrumentType

T = datetime(2026, 9, 3, 10, tzinfo=UTC)
ISIN, CODE = "INE000A01001", "500001"


def _identity() -> InstrumentIdentity:
    return InstrumentIdentity("NSE:ALPHA", Exchange.NSE, "ALPHA", "ALPHA", ISIN, "EQ", InstrumentType.NSE_EQUITY, "Alpha")


def _xml() -> str:
    return f'''<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:x="urn:test">
 <xbrli:context id="annual"><xbrli:period><xbrli:startDate>2024-04-01</xbrli:startDate><xbrli:endDate>2025-03-31</xbrli:endDate></xbrli:period></xbrli:context>
 <xbrli:context id="instant"><xbrli:period><xbrli:instant>2025-03-31</xbrli:instant></xbrli:period></xbrli:context>
 <x:ScripCode>{CODE}</x:ScripCode><x:ISIN>{ISIN}</x:ISIN><x:NameOfTheCompany>Alpha</x:NameOfTheCompany><x:DateOfStartOfReportingPeriod>2024-04-01</x:DateOfStartOfReportingPeriod><x:DateOfEndOfReportingPeriod>2025-03-31</x:DateOfEndOfReportingPeriod><x:TypeOfReportingPeriod>Annual</x:TypeOfReportingPeriod><x:DescriptionOfPresentationCurrency>INR</x:DescriptionOfPresentationCurrency><x:LevelOfRounding>Crores</x:LevelOfRounding><x:NatureOfReportStandaloneConsolidated>Consolidated</x:NatureOfReportStandaloneConsolidated>
 <x:RevenueFromOperations contextRef="annual">100</x:RevenueFromOperations><x:ProfitLoss contextRef="annual">10</x:ProfitLoss><x:CashFlowsFromUsedInOperatingActivities contextRef="annual">15</x:CashFlowsFromUsedInOperatingActivities><x:PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities contextRef="annual">-5</x:PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities>
 <x:Equity contextRef="instant">40</x:Equity><x:CashAndCashEquivalents contextRef="instant">9</x:CashAndCashEquivalents><x:BorrowingsCurrent contextRef="instant">3</x:BorrowingsCurrent><x:BorrowingsNoncurrent contextRef="instant">7</x:BorrowingsNoncurrent><x:BankBalanceOtherThanCashAndCashEquivalents contextRef="instant">2</x:BankBalanceOtherThanCashAndCashEquivalents>
 </xbrli:xbrl>'''


def _stage(root: Path, *, hash_value: str | None = None, annual: bool = True) -> Path:
    root.mkdir(); stem = "bse-500001-INE000A01001-2025-03-31-consolidated-fixture"
    xml = root / (stem + ".xml"); raw = _xml().encode(); xml.write_bytes(raw)
    payload = {"canonical_instrument_id": "NSE:ALPHA", "isin": ISIN, "security_code": CODE, "content_sha256": hash_value or __import__("hashlib").sha256(raw).hexdigest(), "document_identifier": "https://www.bseindia.com/XBRLFILES/alpha.xml", "aliases": ([{"filing_at":"2025-05-01T10:00:00+00:00","financial_year":"2024-2025","quarter_label":"Consolidated-Mar-25","filing_type":"Year","status":"New","revised_at":None,"revision_reason":None,"statement_scope":"CONSOLIDATED","period_end":"2025-03-31T00:00:00+00:00","period_type":"ANNUAL","value_basis":"FULL_YEAR","source_page":"https://api.bseindia.com/archive","timestamp_status":"EXCHANGE_LOCAL_ASSUMPTION"}] if annual else [])}
    (root / (stem + ".aliases.json")).write_text(json.dumps(payload), encoding="utf-8")
    return xml


def test_exact_bse_concepts_map_to_components_without_debt_or_capex_synthesis() -> None:
    document = parse_bse_xbrl(_xml(), "https://www.bseindia.com/XBRLFILES/alpha.xml", period_end=datetime(2025, 3, 31, tzinfo=UTC))
    metrics = {value.metric for value in document.context_facts}
    assert {FinancialMetric.CFO, FinancialMetric.PURCHASE_OF_PROPERTY_PLANT_EQUIPMENT, FinancialMetric.TOTAL_EQUITY, FinancialMetric.CASH_AND_EQUIVALENTS, FinancialMetric.CURRENT_BORROWINGS, FinancialMetric.NONCURRENT_BORROWINGS, FinancialMetric.OTHER_BANK_BALANCES} <= metrics
    assert FinancialMetric.TOTAL_DEBT not in metrics and FinancialMetric.CAPEX not in metrics


def test_staged_annual_backfill_is_idempotent_and_preserves_publication_time(tmp_path: Path) -> None:
    root = tmp_path / "stage"; _stage(root)
    facts = SQLiteFinancialFactStore(tmp_path / "facts.sqlite")
    service = BseStagedAnnualFactBackfillService(BSEOfficialLocalXbrlIngestionService(SQLiteCorporateFilingsStore(tmp_path / "filings.sqlite"), facts, clock=lambda: T), root)
    target = BseStagedAnnualBackfillTarget(_identity(), CODE)
    first, second = service.backfill((target,)), service.backfill((target,))
    assert first.items[0].disposition is BseStagedAnnualBackfillDisposition.IMPORTED
    assert second.items[0].disposition is BseStagedAnnualBackfillDisposition.UNCHANGED
    assert first.facts_inserted == 9 and second.facts_duplicate == 9
    cfo = facts.series("NSE:ALPHA", FinancialMetric.CFO, limit=10)[0]
    assert cfo.published_at == datetime(2025, 5, 1, 10, tzinfo=UTC)


def test_staged_backfill_rejects_hash_mismatch_or_absent_annual_alias(tmp_path: Path) -> None:
    for name, kwargs, expected in (("hash", {"hash_value":"bad"}, BseStagedAnnualBackfillDisposition.SOURCE_HASH_MISMATCH), ("alias", {"annual":False}, BseStagedAnnualBackfillDisposition.SOURCE_ALIAS_MISSING)):
        root = tmp_path / name; _stage(root, **kwargs)
        service = BseStagedAnnualFactBackfillService(BSEOfficialLocalXbrlIngestionService(SQLiteCorporateFilingsStore(tmp_path / (name + "-filings.sqlite")), SQLiteFinancialFactStore(tmp_path / (name + "-facts.sqlite")), clock=lambda: T), root)
        assert service.backfill((BseStagedAnnualBackfillTarget(_identity(), CODE),)).items[0].disposition is expected


def test_target_without_a_staged_alias_receives_a_deterministic_fail_closed_receipt(tmp_path: Path) -> None:
    root = tmp_path / "empty"; root.mkdir()
    service = BseStagedAnnualFactBackfillService(
        BSEOfficialLocalXbrlIngestionService(
            SQLiteCorporateFilingsStore(tmp_path / "filings.sqlite"),
            SQLiteFinancialFactStore(tmp_path / "facts.sqlite"), clock=lambda: T,
        ), root,
    )
    report = service.backfill((BseStagedAnnualBackfillTarget(_identity(), CODE),))
    assert report.items[0].disposition is BseStagedAnnualBackfillDisposition.SOURCE_ALIAS_MISSING
    assert report.items[0].reason == "STAGED_ALIAS_FOR_TARGET_MISSING"


def test_backfill_has_no_network_upstox_portfolio_or_execution_dependency() -> None:
    import app.fundamentals.bse_staged_annual_backfill as module
    parsed = ast.parse(inspect.getsource(module))
    imports = {
        alias.name for node in ast.walk(parsed) if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module for node in ast.walk(parsed) if isinstance(node, ast.ImportFrom) and node.module
    }
    assert not any(value.startswith((
        "app.api", "app.broker", "app.orders", "app.portfolio", "app.signals",
        "app.market_data.upstox", "app.market_data.dhan", "requests", "httpx", "urllib",
    )) for value in imports)
