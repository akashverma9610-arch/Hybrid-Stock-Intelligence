from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from app.data_sources.models import FundamentalFactKind
from app.fundamentals.models import (
    FinancialFact,
    FinancialMetric as M,
    FinancialPeriodType as P,
    FinancialQualityFlag,
    FinancialValueBasis as B,
    NumericScale,
    StatementScope,
)
from app.market_data.models import Exchange, InstrumentIdentity, InstrumentType
from scripts.audit_fundamental_diagnostic_policy_resolution import (
    RATIO_CONTRACT_STATE,
    canonical_json,
    policy_readiness_report,
)


T = datetime(2026, 9, 12, tzinfo=UTC)
INSTRUMENT = InstrumentIdentity("NSE:ALPHA", Exchange.NSE, "ALPHA", "ALPHA", "INE000A01001", "EQ", InstrumentType.NSE_EQUITY, "Alpha")


def fact(metric: M, *, year: int = 2026, period_type: P = P.ANNUAL, basis: B = B.FULL_YEAR, received_at: datetime = T, scope: StatementScope = StatementScope.CONSOLIDATED) -> FinancialFact:
    end = datetime(year, 3, 31, tzinfo=UTC) if period_type is P.ANNUAL else datetime(year, 6, 30, tzinfo=UTC)
    start = None if period_type is P.POINT_IN_TIME else end - timedelta(days=365 if period_type is P.ANNUAL else 90)
    return FinancialFact(
        fact_id=f"{metric.value}-{period_type.value}-{basis.value}-{year}-{scope.value}", instrument=INSTRUMENT,
        metric=metric, value=Decimal("100"), currency="INR", unit="INR", scale=NumericScale.CRORES,
        period_type=period_type, value_basis=basis, period_start=start, period_end=end, fiscal_year=year,
        fiscal_quarter=None if period_type is not P.QUARTERLY else 1, statement_scope=scope,
        fact_kind=FundamentalFactKind.REPORTED, source="TEST_OFFICIAL", filing_id=f"filing-{year}-{metric.value}",
        source_reference="test", published_at=received_at, received_at=received_at,
        normalization_version="financial-facts-v1", provenance=("test",), quality_flags=(FinancialQualityFlag.COMPLETE,),
    )


def test_rule_16_core_readiness_never_substitutes_pbt_for_ebitda():
    values = tuple(
        fact(metric, year=year)
        for year in range(2021, 2027)
        for metric in (M.REVENUE, M.PAT, M.EPS_BASIC, M.PBT)
    )
    report = policy_readiness_report({INSTRUMENT.instrument_id: values}, as_of=T, company_types={INSTRUMENT.instrument_id: "NON_FINANCIAL"})
    counts = dict(report["buckets"][0]["potential_ready_counts"])

    assert counts["rule_16_revenue_pat_eps_core"] == 1
    assert "rule_16_current_strict" not in counts
    assert "100" not in canonical_json(report)


def test_future_facts_are_excluded_and_issuer_ratios_are_not_invented():
    values = (fact(M.EPS_BASIC, received_at=T + timedelta(days=1)),)
    report = policy_readiness_report({INSTRUMENT.instrument_id: values}, as_of=T, company_types={})
    unknown = report["buckets"][-1]

    assert unknown["denominator"] == 1
    assert unknown["potential_ready_counts"] == ()
    assert report["issuer_reported_ratio_contract_state"] == RATIO_CONTRACT_STATE


def test_rule_25_counts_existing_components_independently_and_never_derives_ebitda():
    values = tuple(
        fact(metric, year=year, period_type=P.QUARTERLY, basis=B.QUARTER_ONLY)
        for year in range(2022, 2027)
        for metric in (M.REVENUE, M.PAT, M.EPS_BASIC)
    )
    report = policy_readiness_report({INSTRUMENT.instrument_id: values}, as_of=T, company_types={INSTRUMENT.instrument_id: "NON_FINANCIAL"})
    counts = dict(report["buckets"][0]["potential_ready_counts"])

    assert {"rule_25_revenue_component", "rule_25_pat_component", "rule_25_eps_component"} <= set(counts)
    assert "rule_25_ebitda_component" not in counts


def test_alignment_requires_exact_scope_and_balance_parents():
    values = (
        fact(M.PAT, year=2025), fact(M.PAT, year=2026),
        fact(M.TOTAL_EQUITY, year=2025, period_type=P.POINT_IN_TIME, basis=B.UNKNOWN, scope=StatementScope.STANDALONE),
        fact(M.TOTAL_EQUITY, year=2026, period_type=P.POINT_IN_TIME, basis=B.UNKNOWN, scope=StatementScope.STANDALONE),
    )
    report = policy_readiness_report({INSTRUMENT.instrument_id: values}, as_of=T, company_types={INSTRUMENT.instrument_id: "NON_FINANCIAL"})

    assert "rule_17_roe_parent_alignment" not in dict(report["buckets"][0]["potential_ready_counts"])


def test_report_is_deterministic_across_input_order_and_has_no_values():
    values = (fact(M.EPS_BASIC), fact(M.REVENUE), fact(M.PAT))
    first = policy_readiness_report({INSTRUMENT.instrument_id: values}, as_of=T, company_types={})
    second = policy_readiness_report({INSTRUMENT.instrument_id: tuple(reversed(values))}, as_of=T, company_types={})

    assert first == second
    assert first["fingerprint"].startswith("sha256:")
    assert "100" not in canonical_json(first)


def test_audit_has_no_runtime_clock_writes_or_execution_dependencies():
    source = Path("scripts/audit_fundamental_diagnostic_policy_resolution.py").read_text(encoding="utf-8")
    for forbidden in (
        "datetime.now", "FinancialFactStore", "INSERT INTO", "UPDATE ", "DELETE FROM",
        "app.broker", "app.orders", "app.portfolio", "SELECT value_numeric",
    ):
        assert forbidden not in source
