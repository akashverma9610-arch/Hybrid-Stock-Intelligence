from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import inspect

import pytest

from app.data_sources.models import FundamentalFactKind
from app.fundamentals.compounder_canonical_annual_facts import (
    CanonicalAnnualFactReadinessReason,
    CanonicalAnnualFactReadinessStatus,
    CompounderAnnualMeasureFamily,
    assess_canonical_annual_facts,
    serialize_canonical_annual_facts_readiness,
)
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


T = datetime(2026, 9, 1, 10, tzinfo=UTC)


def _instrument() -> InstrumentIdentity:
    return InstrumentIdentity(
        "NSE:ALPHA", Exchange.NSE, "ALPHA", "ALPHA", "INE000A01001", "EQ",
        InstrumentType.NSE_EQUITY, "Alpha",
    )


def _fact(
    identifier: str, *, metric: FinancialMetric = FinancialMetric.REVENUE,
    fiscal_year: int = 2025, published: datetime = T - timedelta(days=20),
    received: datetime | None = None, scope: StatementScope = StatementScope.CONSOLIDATED,
    basis: FinancialValueBasis = FinancialValueBasis.FULL_YEAR,
    period_start: datetime | None = None, revision_of_fact_id: str | None = None,
    value: str = "100",
) -> FinancialFact:
    end = datetime(fiscal_year, 3, 31, tzinfo=UTC)
    return FinancialFact(
        identifier, _instrument(), metric, Decimal(value), "INR", "INR", NumericScale.CRORES,
        FinancialPeriodType.ANNUAL, basis,
        period_start if period_start is not None else datetime(fiscal_year - 1, 4, 1, tzinfo=UTC),
        end, fiscal_year, None, scope, FundamentalFactKind.REPORTED, "BSE_OFFICIAL",
        "filing-" + identifier, "source-" + identifier, published, received or published,
        "bse-official-xbrl-v1", ("BSE_OFFICIAL_XBRL",), (), revision_of_fact_id,
        (FinancialQualityFlag.COMPLETE,),
    )


def _cover(receipt, family: CompounderAnnualMeasureFamily):
    return next(item for item in receipt.covers if item.measure_family is family)


def test_empty_coverage_is_deterministic_immutable_and_never_qualifies() -> None:
    left = assess_canonical_annual_facts((), canonical_instrument_id="NSE:ALPHA", statement_scope=StatementScope.CONSOLIDATED, as_of=T)
    right = assess_canonical_annual_facts((), canonical_instrument_id="NSE:ALPHA", statement_scope=StatementScope.CONSOLIDATED, as_of=T)
    revenue = _cover(left, CompounderAnnualMeasureFamily.REVENUE)
    assert left.fingerprint == right.fingerprint
    assert revenue.status is CanonicalAnnualFactReadinessStatus.CANONICAL_DATA_MISSING
    assert revenue.reasons == (CanonicalAnnualFactReadinessReason.NO_DIRECT_CANONICAL_FACT,)
    assert not revenue.usable_for_two_period_comparison
    with pytest.raises(FrozenInstanceError):
        revenue.status = CanonicalAnnualFactReadinessStatus.PIT_READY


def test_direct_measure_families_do_not_imply_ebitda_or_period_end_share_mapping() -> None:
    receipt = assess_canonical_annual_facts((), canonical_instrument_id="NSE:ALPHA", statement_scope=StatementScope.CONSOLIDATED, as_of=T)
    operating = _cover(receipt, CompounderAnnualMeasureFamily.EBIT_OR_EBITDA)
    shares = _cover(receipt, CompounderAnnualMeasureFamily.PERIOD_END_SHARES_OUTSTANDING)
    assert operating.status is CanonicalAnnualFactReadinessStatus.DEFINITION_MAPPING_UNAVAILABLE
    assert operating.metric is None
    assert shares.status is CanonicalAnnualFactReadinessStatus.DEFINITION_MAPPING_UNAVAILABLE
    assert shares.reasons == (CanonicalAnnualFactReadinessReason.SHARE_COUNT_SEMANTIC_MAPPING_REQUIRED,)


def test_pit_selection_preserves_revision_vintages_and_excludes_future() -> None:
    original = _fact("revenue-original", fiscal_year=2025, published=T - timedelta(days=50), value="100")
    revision = _fact("revenue-revision", fiscal_year=2025, published=T + timedelta(days=1), value="110", revision_of_fact_id=original.fact_id)
    historical = assess_canonical_annual_facts((revision, original), canonical_instrument_id="NSE:ALPHA", statement_scope=StatementScope.CONSOLIDATED, as_of=T)
    current = assess_canonical_annual_facts((original, revision), canonical_instrument_id="NSE:ALPHA", statement_scope=StatementScope.CONSOLIDATED, as_of=T + timedelta(days=2))
    assert _cover(historical, CompounderAnnualMeasureFamily.REVENUE).selected_fact_ids == ("revenue-original",)
    assert _cover(historical, CompounderAnnualMeasureFamily.REVENUE).excluded_future_fact_ids == ("revenue-revision",)
    assert _cover(current, CompounderAnnualMeasureFamily.REVENUE).selected_fact_ids == ("revenue-revision",)


def test_conflicting_same_period_evidence_fails_closed_without_input_order_dependence() -> None:
    first = _fact("revenue-one", fiscal_year=2025, value="100")
    second = _fact("revenue-two", fiscal_year=2025, value="101")
    left = assess_canonical_annual_facts((first, second), canonical_instrument_id="NSE:ALPHA", statement_scope=StatementScope.CONSOLIDATED, as_of=T)
    right = assess_canonical_annual_facts((second, first), canonical_instrument_id="NSE:ALPHA", statement_scope=StatementScope.CONSOLIDATED, as_of=T)
    coverage = _cover(left, CompounderAnnualMeasureFamily.REVENUE)
    assert coverage.status is CanonicalAnnualFactReadinessStatus.EVIDENCE_CONFLICTED
    assert coverage.conflicted_fact_ids == ("revenue-one", "revenue-two")
    assert left.fingerprint == right.fingerprint


def test_any_conflicted_or_invalid_period_blocks_all_comparison_readiness() -> None:
    values = (
        _fact("complete-2023", fiscal_year=2023),
        _fact("complete-2024", fiscal_year=2024),
        _fact("conflict-a", fiscal_year=2025, value="100"),
        _fact("conflict-b", fiscal_year=2025, value="101"),
    )
    receipt = assess_canonical_annual_facts(values, canonical_instrument_id="NSE:ALPHA", statement_scope=StatementScope.CONSOLIDATED, as_of=T)
    coverage = _cover(receipt, CompounderAnnualMeasureFamily.REVENUE)
    assert coverage.status is CanonicalAnnualFactReadinessStatus.EVIDENCE_CONFLICTED
    assert coverage.comparable_annual_period_count == 2
    assert not coverage.usable_for_two_period_comparison


def test_scope_and_full_year_basis_are_never_silently_substituted() -> None:
    standalone = _fact("standalone", scope=StatementScope.STANDALONE)
    ytd = _fact("ytd", basis=FinancialValueBasis.YEAR_TO_DATE)
    receipt = assess_canonical_annual_facts((standalone, ytd), canonical_instrument_id="NSE:ALPHA", statement_scope=StatementScope.CONSOLIDATED, as_of=T)
    coverage = _cover(receipt, CompounderAnnualMeasureFamily.REVENUE)
    assert coverage.status is CanonicalAnnualFactReadinessStatus.BASIS_MISMATCH
    assert coverage.reasons == (
        CanonicalAnnualFactReadinessReason.EXACT_SCOPE_REQUIRED,
        CanonicalAnnualFactReadinessReason.FULL_YEAR_BASIS_REQUIRED,
    )


def test_complete_period_identity_controls_comparable_depth_not_raw_fact_availability() -> None:
    incomplete = _fact("without-start", fiscal_year=2025, period_start=None)
    # The helper's default is complete; replace it to represent legacy facts that
    # retain only a full-year end and fiscal year.
    incomplete = replace(incomplete, period_start=None)
    complete = _fact("complete", fiscal_year=2024)
    receipt = assess_canonical_annual_facts((incomplete, complete), canonical_instrument_id="NSE:ALPHA", statement_scope=StatementScope.CONSOLIDATED, as_of=T)
    coverage = _cover(receipt, CompounderAnnualMeasureFamily.REVENUE)
    assert coverage.status is CanonicalAnnualFactReadinessStatus.PERIOD_IDENTITY_INCOMPLETE
    assert coverage.annual_period_count == 2
    assert coverage.comparable_annual_period_count == 1
    assert not coverage.usable_for_two_period_comparison


def test_comparable_depth_is_factual_and_not_a_compounder_score() -> None:
    facts = tuple(_fact("rev-" + str(year), fiscal_year=year) for year in range(2021, 2026))
    receipt = assess_canonical_annual_facts(facts, canonical_instrument_id="NSE:ALPHA", statement_scope=StatementScope.CONSOLIDATED, as_of=T)
    coverage = _cover(receipt, CompounderAnnualMeasureFamily.REVENUE)
    assert coverage.status is CanonicalAnnualFactReadinessStatus.PIT_READY
    assert coverage.comparable_annual_period_count == 5
    assert coverage.usable_for_two_period_comparison and coverage.usable_for_three_year_research and coverage.usable_for_five_year_research
    assert "CANDIDATE" not in serialize_canonical_annual_facts_readiness(receipt)


def test_annual_end_balance_sheet_stock_is_not_rejected_for_lacking_a_flow_duration() -> None:
    value = _fact("equity", metric=FinancialMetric.TOTAL_EQUITY, fiscal_year=2025)
    value = replace(value, period_type=FinancialPeriodType.POINT_IN_TIME, value_basis=FinancialValueBasis.UNKNOWN, period_start=None)
    receipt = assess_canonical_annual_facts((value,), canonical_instrument_id="NSE:ALPHA", statement_scope=StatementScope.CONSOLIDATED, as_of=T)
    coverage = _cover(receipt, CompounderAnnualMeasureFamily.SHAREHOLDERS_EQUITY)
    assert coverage.status is CanonicalAnnualFactReadinessStatus.PIT_READY
    assert coverage.comparable_annual_period_count == 1


def test_balance_sheet_stock_rejects_flow_period_or_non_unknown_basis() -> None:
    value = _fact("equity-flow", metric=FinancialMetric.TOTAL_EQUITY)
    receipt = assess_canonical_annual_facts(
        (value,), canonical_instrument_id="NSE:ALPHA",
        statement_scope=StatementScope.CONSOLIDATED, as_of=T,
    )
    coverage = _cover(receipt, CompounderAnnualMeasureFamily.SHAREHOLDERS_EQUITY)
    assert coverage.status is CanonicalAnnualFactReadinessStatus.BASIS_MISMATCH
    assert coverage.reasons == (CanonicalAnnualFactReadinessReason.FULL_YEAR_BASIS_REQUIRED,)


def test_serialization_is_stable_and_tampering_is_rejected() -> None:
    receipt = assess_canonical_annual_facts((_fact("revenue"),), canonical_instrument_id="NSE:ALPHA", statement_scope=StatementScope.CONSOLIDATED, as_of=T)
    assert serialize_canonical_annual_facts_readiness(receipt) == serialize_canonical_annual_facts_readiness(receipt)
    with pytest.raises(ValueError, match="FINGERPRINT"):
        serialize_canonical_annual_facts_readiness(replace(receipt, fingerprint="sha256:tampered"))


def test_rejects_ambiguous_input_and_has_no_repository_provider_or_trade_dependency() -> None:
    fact = _fact("revenue")
    with pytest.raises(ValueError, match="DUPLICATE"):
        assess_canonical_annual_facts((fact, fact), canonical_instrument_id="NSE:ALPHA", statement_scope=StatementScope.CONSOLIDATED, as_of=T)
    import app.fundamentals.compounder_canonical_annual_facts as module
    parsed = ast.parse(inspect.getsource(module))
    imports = {
        alias.name for node in ast.walk(parsed) if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module for node in ast.walk(parsed) if isinstance(node, ast.ImportFrom) and node.module
    }
    assert not any(
        value.startswith(("app.signals", "app.portfolio", "app.broker", "app.orders", "app.storage", "app.api"))
        for value in imports
    )
