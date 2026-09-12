from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from app.data_sources.models import FundamentalFactKind
from app.fundamentals.models import (
    FinancialFact,
    FinancialMetric,
    FinancialPeriodType,
    FinancialQualityFlag,
    FinancialValueBasis,
    NumericScale,
    StatementScope,
)
from app.market_data.models import Exchange, InstrumentIdentity, InstrumentType
from scripts.audit_ebitda_ebit_diagnostic_alternatives import (
    CANDIDATES,
    UNKNOWN_NON_COMPARABLE,
    _candidate_coordinates,
    assess_instrument,
    canonical_json,
    feasibility_report,
)


T = datetime(2026, 9, 12, tzinfo=UTC)
INSTRUMENT = InstrumentIdentity("NSE:ALPHA", Exchange.NSE, "ALPHA", "ALPHA", "INE000A01001", "EQ", InstrumentType.NSE_EQUITY, "Alpha")


def fact(metric: FinancialMetric, *, suffix: str, period_end: datetime = T, received_at: datetime = T, scope: StatementScope = StatementScope.CONSOLIDATED, unit: str = "INR", scale: NumericScale = NumericScale.CRORES) -> FinancialFact:
    return FinancialFact(
        fact_id=f"fact-{metric.value}-{suffix}", instrument=INSTRUMENT, metric=metric,
        value=Decimal("123.45"), currency="INR", unit=unit, scale=scale,
        period_type=FinancialPeriodType.ANNUAL, value_basis=FinancialValueBasis.FULL_YEAR,
        period_start=period_end - timedelta(days=365), period_end=period_end,
        fiscal_year=period_end.year, fiscal_quarter=None, statement_scope=scope,
        fact_kind=FundamentalFactKind.REPORTED, source="TEST_OFFICIAL", filing_id=f"filing-{suffix}",
        source_reference="test", published_at=received_at, received_at=received_at,
        normalization_version="financial-facts-v1", provenance=("test",),
        quality_flags=(FinancialQualityFlag.COMPLETE,),
    )


def full_components(*, suffix: str = "one", period_end: datetime = T, received_at: datetime = T, **kwargs) -> tuple[FinancialFact, ...]:
    return tuple(fact(metric, suffix=suffix, period_end=period_end, received_at=received_at, **kwargs) for metric in (
        FinancialMetric.PBT, FinancialMetric.FINANCE_COST, FinancialMetric.DEPRECIATION, FinancialMetric.OTHER_INCOME,
    ))


def test_candidate_coordinates_are_metadata_only_and_exact_parent_compatible():
    coordinates = _candidate_coordinates(full_components(), CANDIDATES[2])

    assert len(coordinates) == 1
    assert coordinates[0].parent_fact_ids == (
        "fact-PBT-one", "fact-FINANCE_COST-one", "fact-DEPRECIATION-one", "fact-OTHER_INCOME-one",
    )
    assert "123.45" not in repr(coordinates[0])
    assert not hasattr(coordinates[0], "value")


def test_missing_component_and_representation_mismatch_are_not_candidate_coverage():
    values = full_components()
    assert _candidate_coordinates(values[:-1], CANDIDATES[2]) == ()

    mismatched = (*values[:2], fact(FinancialMetric.DEPRECIATION, suffix="one", unit="USD"), values[3])
    assert _candidate_coordinates(mismatched, CANDIDATES[2]) == ()


def test_future_parent_is_pit_excluded_from_candidate_feasibility():
    values = full_components(received_at=T)[:-1] + (fact(FinancialMetric.OTHER_INCOME, suffix="one", received_at=T + timedelta(days=1)),)
    result = assess_instrument(values, instrument_id=INSTRUMENT.instrument_id, as_of=T)

    candidate_c = result["candidates"][2]
    assert candidate_c["period_observations_available"] == 0
    assert candidate_c["missing_components"] == ("OTHER_INCOME",)


def test_annual_depth_is_deterministic_and_requires_exact_compatible_periods():
    values = tuple(
        component
        for year in range(2021, 2027)
        for component in full_components(suffix=str(year), period_end=datetime(year, 3, 31, tzinfo=UTC))
    )
    first = feasibility_report({INSTRUMENT.instrument_id: values}, as_of=T, company_types={INSTRUMENT.instrument_id: "NON_FINANCIAL"})
    second = feasibility_report({INSTRUMENT.instrument_id: tuple(reversed(values))}, as_of=T, company_types={INSTRUMENT.instrument_id: "NON_FINANCIAL"})

    assert first == second
    assert first["candidates"][0]["companies_annual_6_periods"] == 1
    assert first["fingerprint"].startswith("sha256:")
    assert "123.45" not in canonical_json(first)


def test_unknown_company_type_is_explicit_not_not_applicable():
    report = feasibility_report({INSTRUMENT.instrument_id: full_components()}, as_of=T, company_types={})

    assert report["entity_type_counts"] == ((UNKNOWN_NON_COMPARABLE, 1),)


def test_audit_script_has_no_runtime_clock_persistence_or_execution_dependencies():
    source = Path("scripts/audit_ebitda_ebit_diagnostic_alternatives.py").read_text(encoding="utf-8")

    for forbidden in (
        "datetime.now", "FinancialFactStore", "INSERT INTO", "UPDATE ", "DELETE FROM",
        "app.broker", "app.orders", "app.portfolio", "SELECT value_numeric",
    ):
        assert forbidden not in source
