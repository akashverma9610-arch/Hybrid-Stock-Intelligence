from __future__ import annotations

from datetime import UTC, datetime

from app.filings.store import SQLiteCorporateFilingsStore
from app.fundamentals.adapter import FundamentalsEngineAdapter
from app.fundamentals.models import FinancialMetric, StatementScope
from app.fundamentals.store import SQLiteFinancialFactStore
from app.market_data.models import Exchange, InstrumentIdentity, InstrumentType
from app.nse_import.service import (
    ExportFamily,
    FrozenCohortInstrumentResolver,
    ImportRunStore,
    ImportStatus,
    NSEOfficialExportProvider,
    OfficialExchangeImportService,
)


T = datetime(2026, 8, 25, 12, tzinfo=UTC)


def _identity(identifier: str, symbol: str, isin: str) -> InstrumentIdentity:
    return InstrumentIdentity(identifier, Exchange.NSE, symbol, symbol, isin, None, InstrumentType.NSE_EQUITY, symbol)


def _service(tmp_path):
    alpha = _identity("NSE:ALPHA", "ALPHA", "INE000A01000")
    outside = _identity("NSE:OUTSIDE", "OUTSIDE", "INE000B01000")
    resolver = FrozenCohortInstrumentResolver((alpha, outside), (alpha.instrument_id,))
    filings = SQLiteCorporateFilingsStore(tmp_path / "filings.sqlite")
    facts = SQLiteFinancialFactStore(tmp_path / "facts.sqlite")
    return (
        OfficialExchangeImportService(
            NSEOfficialExportProvider(), resolver, filings, facts,
            ImportRunStore(tmp_path / "runs.sqlite"), clock=lambda: T,
        ),
        filings,
        facts,
        alpha,
    )


def test_frozen_cohort_resolver_uses_exact_isin_then_canonical_id_then_unique_symbol() -> None:
    alpha = _identity("NSE:ALPHA", "ALPHA", "INE000A01000")
    beta = _identity("NSE:BETA", "BETA", "INE000B01000")
    resolver = FrozenCohortInstrumentResolver((alpha, beta), (alpha.instrument_id,))

    assert resolver.resolve("OTHER", "INE000A01000") == alpha
    assert resolver.resolve("OTHER", None, "NSE:ALPHA") == alpha
    assert resolver.resolve("ALPHA") == alpha
    assert resolver.resolve("ALPHA", "INE000B01000") is None
    assert resolver.resolve("BETA") is None


def test_frozen_official_xbrl_import_is_dry_run_safe_and_never_maps_outside_the_40(tmp_path) -> None:
    service, filings, facts, alpha = _service(tmp_path)
    path = tmp_path / "official-xbrl.csv"
    path.write_text(
        "Symbol,ISIN,Broadcast Date,Period End,Metric,Value,Scope,Event ID\n"
        "ALPHA,INE000A01000,2026-08-20T10:00:00+05:30,2026-06-30,REVENUE,100,CONSOLIDATED,alpha-revenue\n"
        "OUTSIDE,INE000B01000,2026-08-20T10:00:00+05:30,2026-06-30,PAT,10,CONSOLIDATED,outside-pat\n",
        encoding="utf-8",
    )

    dry = service.import_file(path, family=ExportFamily.XBRL_CONVERTED_RESULTS, dry_run=True)
    assert (dry.accepted, dry.unresolved_symbols, dry.status) == (1, 1, ImportStatus.PARTIAL)
    assert filings.list(limit=10) == ()
    assert facts.facts(alpha.instrument_id, limit=10) == ()

    imported = service.import_file(path, family=ExportFamily.XBRL_CONVERTED_RESULTS)
    stored = facts.series(alpha.instrument_id, FinancialMetric.REVENUE, as_of=T)
    assert (imported.accepted, imported.unresolved_symbols, imported.status) == (1, 1, ImportStatus.PARTIAL)
    assert len(filings.list(instrument_id=alpha.instrument_id, as_of=T, limit=10)) == 1
    assert len(stored) == 1 and stored[0].statement_scope is StatementScope.CONSOLIDATED


def test_missing_official_metrics_remain_missing_without_zero_fabrication(tmp_path) -> None:
    service, filings, facts, alpha = _service(tmp_path)
    path = tmp_path / "revenue-only.csv"
    path.write_text(
        "Symbol,ISIN,Broadcast Date,Period End,Metric,Value,Scope,Event ID\n"
        "ALPHA,INE000A01000,2026-08-20T10:00:00+05:30,2026-06-30,REVENUE,100,CONSOLIDATED,revenue-only\n",
        encoding="utf-8",
    )
    assert service.import_file(path, family=ExportFamily.XBRL_CONVERTED_RESULTS).accepted == 1

    input_ = FundamentalsEngineAdapter(facts, filings).build(alpha.instrument_id, as_of=T)
    assert input_.statement_scope is StatementScope.CONSOLIDATED
    assert input_.completeness == "PARTIAL"
    assert input_.snapshot.observations[0].payload["revenue"] == 100.0
    assert "pat" not in input_.snapshot.observations[0].payload
    assert "eps" not in input_.snapshot.observations[0].payload


def test_official_annual_metadata_is_preserved_without_quarterly_coercion(tmp_path) -> None:
    service, _filings, facts, alpha = _service(tmp_path)
    path = tmp_path / "annual.csv"
    path.write_text(
        "Symbol,ISIN,Broadcast Date,Period End,Metric,Value,Scope,Period Type,Value Basis,Scale,Fiscal Year,Event ID\n"
        "ALPHA,INE000A01000,2026-05-20T10:00:00+05:30,2026-03-31,REVENUE,250,CONSOLIDATED,ANNUAL,FULL_YEAR,CRORES,2026,annual-revenue\n",
        encoding="utf-8",
    )

    assert service.import_file(path, family=ExportFamily.XBRL_CONVERTED_RESULTS).accepted == 1
    stored = facts.series(alpha.instrument_id, FinancialMetric.REVENUE, as_of=T)
    assert len(stored) == 1
    assert stored[0].period_type.value == "ANNUAL"
    assert stored[0].value_basis.value == "FULL_YEAR"
    assert stored[0].scale.value == "CRORES"
    assert stored[0].fiscal_quarter is None
