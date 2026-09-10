from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from hashlib import sha256
from inspect import getsource

import pytest

from app.data_operations.financial_period_identity_repair import (
    FinancialPeriodIdentityCorrectionStore,
    FinancialPeriodIdentityCorrection,
    FinancialPeriodIdentityProjection,
    PeriodIdentityRepairDisposition,
    FinancialPeriodIdentityRepairService,
    PeriodIdentityRepairWriteStatus,
    PIT_STATUS,
    audit_json,
)
from app.data_sources.models import FundamentalFactKind
from app.filings.models import (
    AttachmentParseStatus,
    CorporateFiling,
    FilingAttachment,
    FilingTextAvailability,
    FilingType,
    FinancialResultMetadata,
    PrimarySourceQuality,
)
from app.filings.store import SQLiteCorporateFilingsStore
from app.fundamentals.adapter import FundamentalsEngineAdapter
from app.fundamentals.models import (
    FinancialFact,
    FinancialMetric,
    FinancialPeriodType,
    FinancialValueBasis,
    NumericScale,
    StatementScope,
)
from app.fundamentals.store import SQLiteFinancialFactStore
from app.market_data.models import Exchange, InstrumentIdentity, InstrumentType, MarketDataProvenance
from app.runtime.cli import parser
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository


T = datetime(2026, 9, 10, 9, tzinfo=UTC)
PUBLISHED = datetime(2026, 1, 15, 9, tzinfo=UTC)
END = datetime(2025, 9, 30, tzinfo=UTC)
INSTRUMENT = InstrumentIdentity(
    "NSE:INE000A01001", Exchange.NSE, "APARINDS", "APARINDS", "INE000A01001",
    "EQ", InstrumentType.NSE_EQUITY, "Synthetic APARINDS",
)


def _xml(*, duplicate_semantics: bool = False, scope: str = "Standalone") -> str:
    ytd_value = "100" if duplicate_semantics else "200"
    return f'''<?xml version="1.0"?><xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:in-capmkt="http://www.sebi.gov.in/xbrl">
    <xbrli:context id="quarter"><xbrli:period><xbrli:startDate>2025-07-01</xbrli:startDate><xbrli:endDate>2025-09-30</xbrli:endDate></xbrli:period></xbrli:context>
    <xbrli:context id="ytd"><xbrli:period><xbrli:startDate>2025-04-01</xbrli:startDate><xbrli:endDate>2025-09-30</xbrli:endDate></xbrli:period></xbrli:context>
    <xbrli:context id="instant"><xbrli:period><xbrli:instant>2025-09-30</xbrli:instant></xbrli:period></xbrli:context>
    <in-capmkt:ScripCode>999999</in-capmkt:ScripCode><in-capmkt:ISIN>INE000A01001</in-capmkt:ISIN><in-capmkt:NameOfTheCompany>Synthetic APARINDS</in-capmkt:NameOfTheCompany>
    <in-capmkt:DescriptionOfPresentationCurrency>INR</in-capmkt:DescriptionOfPresentationCurrency><in-capmkt:LevelOfRounding>Units</in-capmkt:LevelOfRounding><in-capmkt:NatureOfReportStandaloneConsolidated>{scope}</in-capmkt:NatureOfReportStandaloneConsolidated>
    <in-capmkt:RevenueFromOperations contextRef="quarter">100</in-capmkt:RevenueFromOperations><in-capmkt:RevenueFromOperations contextRef="ytd">{ytd_value}</in-capmkt:RevenueFromOperations><in-capmkt:ProfitLoss contextRef="quarter">10</in-capmkt:ProfitLoss><in-capmkt:Assets contextRef="instant">1000</in-capmkt:Assets></xbrli:xbrl>'''


def _fact(
    fact_id: str,
    metric: FinancialMetric,
    value: str,
    *,
    period_type: FinancialPeriodType = FinancialPeriodType.QUARTERLY,
    value_basis: FinancialValueBasis = FinancialValueBasis.QUARTER_ONLY,
    period_start: datetime | None = datetime(2025, 4, 1, tzinfo=UTC),
    period_end: datetime = END,
    scope: StatementScope = StatementScope.STANDALONE,
    fiscal_year: int = 2026,
    fiscal_quarter: int = 2,
) -> FinancialFact:
    return FinancialFact(
        fact_id, INSTRUMENT, metric, Decimal(value), "INR", "INR", NumericScale.UNITS,
        period_type, value_basis, period_start, period_end, fiscal_year, fiscal_quarter, scope,
        FundamentalFactKind.REPORTED, "BSE_OFFICIAL", "filing:period", "https://example.test/period.xml",
        PUBLISHED, PUBLISHED, "bse-official-staged-xbrl-v1", ("BSE_OFFICIAL_XBRL",),
    )


def _seed(tmp_path, facts: tuple[FinancialFact, ...], *, xml: str | None = None):
    source_directory = tmp_path / "collector"
    source_directory.mkdir()
    raw = source_directory / "period.xml"
    raw.write_text(_xml() if xml is None else xml, encoding="utf-8")
    raw_sha256 = sha256(raw.read_bytes()).hexdigest()
    instrument = facts[0].instrument
    fact_store = SQLiteFinancialFactStore(tmp_path / "facts.sqlite")
    filing_store = SQLiteCorporateFilingsStore(tmp_path / "filings.sqlite")
    filing_store.save(CorporateFiling(
        "filing:period", instrument, Exchange.BSE, "BSE_OFFICIAL", PrimarySourceQuality.PRIMARY_EXCHANGE,
        FilingType.FINANCIAL_RESULTS, "Financial Results", "Synthetic period filing", PUBLISHED, PUBLISHED,
        "https://example.test/period.xml", "https://example.test/period.xml",
        MarketDataProvenance("BSE_OFFICIAL", "999999", PUBLISHED, PUBLISHED, PUBLISHED, "bse-official-staged-xbrl-v1", "retained", "https://example.test/period.xml"),
        period_end=END, text_availability=FilingTextAvailability.DOCUMENT_ONLY,
        attachments=(FilingAttachment("attachment:period", "XBRL", "Synthetic XBRL", raw.name,
                                      "https://example.test/period.xml", "application/xml", PUBLISHED,
                                      raw_sha256, AttachmentParseStatus.PARSED, True),),
        financial_result=FinancialResultMetadata(END, "STANDALONE", "Quarter", False),
    ))
    for fact in facts:
        assert fact_store.save(fact).value == "INSERTED"
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "core.sqlite")
    corrections = FinancialPeriodIdentityCorrectionStore(repository)
    service = FinancialPeriodIdentityRepairService(
        facts=fact_store, filings=filing_store, corrections=corrections,
        source_directory=source_directory, clock=lambda: T,
    )
    return fact_store, filing_store, corrections, service, repository


def test_source_proven_projection_repairs_quarter_and_instant_without_mutating_values_or_lineage(tmp_path):
    quarterly = _fact("fact:quarter", FinancialMetric.REVENUE, "100")
    instant = _fact("fact:instant", FinancialMetric.TOTAL_ASSETS, "1000")
    facts, _filings, corrections, service, repository = _seed(tmp_path, (quarterly, instant))
    try:
        result = service.audit_and_apply((INSTRUMENT.instrument_id,))
        assert result.new_corrections == 2 and result.audit_written
        assert {item.disposition for item in result.audit.observations} == {PeriodIdentityRepairDisposition.READY_CORRECTION}
        # The durable source fact is exactly unchanged; no destructive rewrite occurred.
        assert facts.get(quarterly.fact_id) == quarterly and facts.get(instant.fact_id) == instant
        before = FinancialPeriodIdentityProjection(corrections).project((quarterly, instant), as_of=T - timedelta(microseconds=1))
        assert before == (quarterly, instant)
        projected = FinancialPeriodIdentityProjection(corrections).project((quarterly, instant), as_of=T)
        by_id = {item.fact_id: item for item in projected}
        assert by_id[quarterly.fact_id].period_start == datetime(2025, 7, 1, tzinfo=UTC)
        assert by_id[quarterly.fact_id].period_type is FinancialPeriodType.QUARTERLY
        assert by_id[quarterly.fact_id].value_basis is FinancialValueBasis.QUARTER_ONLY
        assert by_id[instant.fact_id].period_type is FinancialPeriodType.POINT_IN_TIME
        assert by_id[instant.fact_id].value_basis is FinancialValueBasis.UNKNOWN
        assert by_id[instant.fact_id].period_start is None
        for original, repaired in zip((quarterly, instant), projected):
            assert (repaired.value, repaired.currency, repaired.unit, repaired.scale, repaired.statement_scope,
                    repaired.fiscal_year, repaired.fiscal_quarter, repaired.filing_id) == (
                original.value, original.currency, original.unit, original.scale, original.statement_scope,
                original.fiscal_year, original.fiscal_quarter, original.filing_id,
            )
        assert all(value.source_semantics_status == PIT_STATUS for value in corrections.corrections())
    finally:
        repository.close()


def test_explicit_xbrl_ytd_is_separated_from_quarter_only_and_never_enters_quarter_series(tmp_path):
    ytd = _fact("fact:ytd", FinancialMetric.REVENUE, "200")
    facts, filings, corrections, service, repository = _seed(tmp_path, (ytd,))
    try:
        assert service.audit_and_apply((INSTRUMENT.instrument_id,)).new_corrections == 1
        adapter = FundamentalsEngineAdapter(facts, filings, FinancialPeriodIdentityProjection(corrections))
        input_ = adapter.diagnostic_input(INSTRUMENT.instrument_id, as_of=T)
        quarter_series = input_.comparable.series(FinancialMetric.REVENUE, FinancialPeriodType.QUARTERLY, FinancialValueBasis.QUARTER_ONLY)
        ytd_series = input_.comparable.series(FinancialMetric.REVENUE, FinancialPeriodType.QUARTERLY, FinancialValueBasis.YEAR_TO_DATE)
        assert quarter_series.observations == ()
        assert {item.source_fact_id for item in ytd_series.observations} == {ytd.fact_id}
        assert all(item.period_identity.value_basis is FinancialValueBasis.YEAR_TO_DATE for item in ytd_series.observations)
    finally:
        repository.close()


def test_explicit_nine_month_ytd_maps_to_ytd_only_when_the_retained_context_proves_it(tmp_path):
    period_end = datetime(2025, 12, 31, tzinfo=UTC)
    xml = _xml().replace(
        "<xbrli:startDate>2025-07-01</xbrli:startDate><xbrli:endDate>2025-09-30</xbrli:endDate>",
        "<xbrli:startDate>2025-10-01</xbrli:startDate><xbrli:endDate>2025-12-31</xbrli:endDate>",
    ).replace(
        "<xbrli:startDate>2025-04-01</xbrli:startDate><xbrli:endDate>2025-09-30</xbrli:endDate>",
        "<xbrli:startDate>2025-04-01</xbrli:startDate><xbrli:endDate>2025-12-31</xbrli:endDate>",
    ).replace("2025-09-30</xbrli:instant>", "2025-12-31</xbrli:instant>")
    ytd = _fact(
        "fact:nine-month-ytd", FinancialMetric.REVENUE, "200", period_end=period_end,
        fiscal_quarter=3,
    )
    facts, filings, corrections, service, repository = _seed(tmp_path, (ytd,), xml=xml)
    try:
        assert service.audit_and_apply((INSTRUMENT.instrument_id,)).new_corrections == 1
        adapter = FundamentalsEngineAdapter(facts, filings, FinancialPeriodIdentityProjection(corrections))
        input_ = adapter.diagnostic_input(INSTRUMENT.instrument_id, as_of=T)
        quarter_series = input_.comparable.series(
            FinancialMetric.REVENUE, FinancialPeriodType.QUARTERLY, FinancialValueBasis.QUARTER_ONLY,
        )
        ytd_series = input_.comparable.series(
            FinancialMetric.REVENUE, FinancialPeriodType.QUARTERLY, FinancialValueBasis.YEAR_TO_DATE,
        )
        assert quarter_series.observations == ()
        assert {item.source_fact_id for item in ytd_series.observations} == {ytd.fact_id}
        assert ytd_series.observations[0].period_identity.period_start == datetime(2025, 4, 1, tzinfo=UTC)
    finally:
        repository.close()


def test_duration_without_matching_source_context_fails_closed(tmp_path):
    missing = _fact("fact:missing", FinancialMetric.PAT, "999")
    _facts, _filings, _corrections, service, repository = _seed(tmp_path, (missing,))
    try:
        result = service.audit_and_apply((INSTRUMENT.instrument_id,))
        assert result.new_corrections == 0
        assert result.audit.observations[0].disposition is PeriodIdentityRepairDisposition.SOURCE_EVIDENCE_INSUFFICIENT
        assert result.audit.observations[0].reason == "EXACT_XBRL_CONTEXT_VALUE_MATCH_REQUIRED"
    finally:
        repository.close()


def test_conflicting_explicit_context_semantics_are_ambiguous_and_not_repaired(tmp_path):
    fact = _fact("fact:ambiguous", FinancialMetric.REVENUE, "100")
    _facts, _filings, corrections, service, repository = _seed(tmp_path, (fact,), xml=_xml(duplicate_semantics=True))
    try:
        result = service.audit_and_apply((INSTRUMENT.instrument_id,))
        assert result.new_corrections == 0
        assert result.audit.observations[0].disposition is PeriodIdentityRepairDisposition.AMBIGUOUS
        assert corrections.corrections() == ()
    finally:
        repository.close()


def test_replay_is_idempotent_and_the_artifact_is_deterministic(tmp_path):
    fact = _fact("fact:replay", FinancialMetric.REVENUE, "100")
    _facts, _filings, corrections, service, repository = _seed(tmp_path, (fact,))
    try:
        first = service.audit_and_apply((INSTRUMENT.instrument_id,))
        second = service.audit_and_apply((INSTRUMENT.instrument_id,))
        assert first.new_corrections == 1 and second.new_corrections == 0
        assert second.existing_corrections == 1
        assert second.outcomes[0].status is PeriodIdentityRepairWriteStatus.IDENTICAL
        assert first.audit.audit_id == second.audit.audit_id
        assert first.audit.fingerprint == second.audit.fingerprint
        service._clock = lambda: T + timedelta(days=1)
        third = service.audit_and_apply((INSTRUMENT.instrument_id,))
        assert third.audit.created_at == first.audit.created_at
        assert audit_json(first.audit) == audit_json(second.audit)
        assert len(corrections.corrections()) == 1
    finally:
        repository.close()


@pytest.mark.parametrize("symbol", ("APARINDS", "GLAND", "GENUSPOWER", "DEEPINDS"))
def test_named_target_case_is_source_proven_and_scope_preserving(tmp_path, symbol):
    fact = replace(_fact("fact:" + symbol, FinancialMetric.REVENUE, "100"), instrument=replace(INSTRUMENT, symbol=symbol))
    _facts, _filings, corrections, service, repository = _seed(tmp_path, (fact,))
    try:
        result = service.audit_and_apply((fact.instrument.instrument_id,))
        audit = result.audit.observations[0]
        repaired = FinancialPeriodIdentityProjection(corrections).project((fact,), as_of=T)[0]
        assert audit.symbol == symbol and audit.disposition is PeriodIdentityRepairDisposition.READY_CORRECTION
        assert repaired.statement_scope is fact.statement_scope and repaired.value == fact.value
    finally:
        repository.close()


def test_already_valid_annual_and_point_in_time_are_not_candidates(tmp_path):
    annual = _fact("fact:annual", FinancialMetric.REVENUE, "400", period_type=FinancialPeriodType.ANNUAL,
                   value_basis=FinancialValueBasis.FULL_YEAR, period_start=datetime(2024, 4, 1, tzinfo=UTC),
                   period_end=datetime(2025, 3, 31, tzinfo=UTC))
    point = _fact("fact:point", FinancialMetric.TOTAL_ASSETS, "1000", period_type=FinancialPeriodType.POINT_IN_TIME,
                  value_basis=FinancialValueBasis.UNKNOWN, period_start=None)
    _facts, _filings, corrections, service, repository = _seed(tmp_path, (annual, point))
    try:
        result = service.audit_and_apply((INSTRUMENT.instrument_id,))
        assert result.audit.observations == () and corrections.corrections() == ()
    finally:
        repository.close()


def test_scope_mismatch_and_tampered_source_fact_fail_closed(tmp_path):
    fact = _fact("fact:scope", FinancialMetric.REVENUE, "100")
    _facts, _filings, corrections, service, repository = _seed(tmp_path, (fact,), xml=_xml(scope="Consolidated"))
    try:
        result = service.audit_and_apply((INSTRUMENT.instrument_id,))
        assert result.audit.observations[0].disposition is PeriodIdentityRepairDisposition.SOURCE_EVIDENCE_INSUFFICIENT
        assert corrections.corrections() == ()
    finally:
        repository.close()


def test_invalid_fiscal_identity_is_not_repaired_from_a_correct_context(tmp_path):
    fact = replace(_fact("fact:fiscal", FinancialMetric.REVENUE, "100"), fiscal_quarter=3)
    _facts, _filings, corrections, service, repository = _seed(tmp_path, (fact,))
    try:
        result = service.audit_and_apply((INSTRUMENT.instrument_id,))
        assert result.new_corrections == 0
        assert result.audit.observations[0].reason == "EXACT_BSE_FISCAL_IDENTITY_REQUIRED"
        assert corrections.corrections() == ()
    finally:
        repository.close()


def test_projection_rejects_a_tampered_source_fact_and_conflicting_correction_lineage(tmp_path):
    fact = _fact("fact:tampered", FinancialMetric.REVENUE, "100")
    _facts, _filings, corrections, service, repository = _seed(tmp_path, (fact,))
    try:
        assert service.audit_and_apply((INSTRUMENT.instrument_id,)).new_corrections == 1
        projection = FinancialPeriodIdentityProjection(corrections)
        with pytest.raises(ValueError, match="SOURCE_TAMPERED"):
            projection.project((replace(fact, value=Decimal("101")),), as_of=T)
        original = corrections.corrections()[0]
        values = {
            field: getattr(original, field)
            for field in original.__dataclass_fields__
            if field not in {"correction_id", "fingerprint", "source_artifact_sha256"}
        }
        values["source_artifact_sha256"] = "f" * 64
        fingerprint = financial_period_identity_correction_fingerprint_values_for_test(values)
        conflicting = FinancialPeriodIdentityCorrection(
            correction_id="financial-period-identity-correction:conflicting",
            **values,
            fingerprint=fingerprint,
        )
        assert corrections.save(conflicting)
        with pytest.raises(ValueError, match="PROJECTION_CONFLICTED"):
            FinancialPeriodIdentityProjection(corrections).project((fact,), as_of=T)
    finally:
        repository.close()


def financial_period_identity_correction_fingerprint_values_for_test(values):
    from app.data_operations.financial_period_identity_repair import _correction_fingerprint_values
    return _correction_fingerprint_values(values)


def test_repair_module_has_no_network_api_portfolio_or_order_dependency():
    source = getsource(__import__("app.data_operations.financial_period_identity_repair", fromlist=["*"]))
    for forbidden in ("urlopen", "requests", "http.client", "FastAPI", "APIRouter", "broker", "order", "portfolio"):
        assert forbidden not in source


def test_repair_command_is_explicit_and_has_no_provider_arguments():
    parsed = parser().parse_args(["repair-canonical-financial-period-identities"])
    assert parsed.command == "repair-canonical-financial-period-identities"
    assert vars(parsed) == {"command": "repair-canonical-financial-period-identities"}
