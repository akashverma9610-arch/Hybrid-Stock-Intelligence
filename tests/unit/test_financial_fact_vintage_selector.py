from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import inspect
import random

import pytest

import app.fundamentals.financial_fact_vintage_selector as selector_module
from app.data_sources.models import FundamentalFactKind
from app.fundamentals.financial_fact_vintage_selection_policy import (
    CURRENT_FROZEN_FINANCIAL_FACT_VINTAGE_SELECTION_POLICY,
    FinancialFactVintageSelectionReason,
    FinancialFactVintageSelectionStatus,
    FinancialFactVintageSelectionWarning,
    create_frozen_financial_fact_vintage_selection_policy,
)
from app.fundamentals.financial_fact_vintage_selector import (
    FinancialFactSemanticKey,
    FinancialFactVintageSelection,
    FinancialFactVintageSelectionBatch,
    select_financial_fact_vintages,
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


T = datetime(2026, 8, 29, 10, tzinfo=UTC)
POLICY = CURRENT_FROZEN_FINANCIAL_FACT_VINTAGE_SELECTION_POLICY


def _instrument(identifier: str = "NSE:ALPHA") -> InstrumentIdentity:
    symbol = identifier.rsplit(":", 1)[-1]
    return InstrumentIdentity(
        identifier, Exchange.NSE, symbol, symbol, "INE000A01001", "EQ",
        InstrumentType.NSE_EQUITY, symbol,
    )


def _fact(
    identifier: str,
    *,
    instrument_id: str = "NSE:ALPHA",
    metric: FinancialMetric = FinancialMetric.REVENUE,
    value: str = "100",
    published: datetime = T - timedelta(days=3),
    received: datetime | None = None,
    period_end: datetime = datetime(2026, 6, 30, tzinfo=UTC),
    scope: StatementScope = StatementScope.CONSOLIDATED,
    period_type: FinancialPeriodType = FinancialPeriodType.QUARTERLY,
    basis: FinancialValueBasis = FinancialValueBasis.QUARTER_ONLY,
    currency: str = "INR",
    unit: str = "INR",
    scale: NumericScale = NumericScale.CRORES,
    source: str = "BSE_OFFICIAL",
    filing_id: str | None = None,
    source_reference: str | None = None,
    revision_of_fact_id: str | None = None,
    quality_flags: tuple[FinancialQualityFlag, ...] = (FinancialQualityFlag.COMPLETE,),
    normalization_version: str = "financial-facts-v1",
) -> FinancialFact:
    return FinancialFact(
        identifier,
        _instrument(instrument_id),
        metric,
        Decimal(value),
        currency,
        unit,
        scale,
        period_type,
        basis,
        None,
        period_end,
        2027 if period_type is FinancialPeriodType.QUARTERLY else 2026,
        1 if period_type is FinancialPeriodType.QUARTERLY else None,
        scope,
        FundamentalFactKind.REPORTED,
        source,
        filing_id or "filing-" + identifier,
        source_reference or "reference-" + identifier,
        published,
        received or published,
        normalization_version,
        (),
        (),
        revision_of_fact_id,
        quality_flags,
    )


def _selection(batch: FinancialFactVintageSelectionBatch, fact_id: str) -> FinancialFactVintageSelection:
    return next(value for value in batch.selections if fact_id in value.candidate_fact_ids)


def test_contracts_are_immutable_and_fingerprints_are_deterministic() -> None:
    result = select_financial_fact_vintages((_fact("f1"),), canonical_instrument_id="NSE:ALPHA", as_of=T, policy=POLICY)
    selection = result.selections[0]
    assert isinstance(selection.semantic_key, FinancialFactSemanticKey)
    assert selection.status is FinancialFactVintageSelectionStatus.SELECTED
    assert selection.fingerprint == _selection(
        select_financial_fact_vintages((_fact("f1"),), canonical_instrument_id="NSE:ALPHA", as_of=T, policy=POLICY),
        "f1",
    ).fingerprint
    with pytest.raises(FrozenInstanceError):
        selection.status = FinancialFactVintageSelectionStatus.CONFLICTED
    with pytest.raises(FrozenInstanceError):
        result.selections = ()


def test_policy_must_be_exact_frozen_approved_and_inactive() -> None:
    assert not POLICY.active and not POLICY.selected_for_future_selector
    bad = create_frozen_financial_fact_vintage_selection_policy(
        policy_id="financial-fact-vintage-selection-policy",
        version="v2-approved",
        proposal_policy_id="financial-fact-vintage-selection-policy",
        proposal_version="v1-proposed",
        approved_by="human:Akash-Verma",
        provenance=(("scope", "FACTUAL_PIT_SELECTION_ONLY"),),
    )
    with pytest.raises(ValueError, match="POLICY_UNSUPPORTED"):
        select_financial_fact_vintages((), canonical_instrument_id="NSE:ALPHA", as_of=T, policy=bad)
    wrong_fingerprint = create_frozen_financial_fact_vintage_selection_policy(
        policy_id="financial-fact-vintage-selection-policy",
        version="v1-approved",
        proposal_policy_id="financial-fact-vintage-selection-policy",
        proposal_version="v1-proposed",
        approved_by="human:Akash-Verma",
        provenance=(("scope", "DIFFERENT_BUT_VALID_FROZEN_ARTIFACT"),),
    )
    with pytest.raises(ValueError, match="POLICY_UNSUPPORTED"):
        select_financial_fact_vintages((), canonical_instrument_id="NSE:ALPHA", as_of=T, policy=wrong_fingerprint)
    with pytest.raises(ValueError, match="POLICY_INVALID"):
        select_financial_fact_vintages((), canonical_instrument_id="NSE:ALPHA", as_of=T, policy=object())  # type: ignore[arg-type]


def test_pit_boundary_future_exclusion_and_unknown_publication_visibility() -> None:
    visible = _fact("visible", published=T)
    future = _fact("future", published=T + timedelta(microseconds=1))
    result = select_financial_fact_vintages((visible, future), canonical_instrument_id="NSE:ALPHA", as_of=T, policy=POLICY)
    selection = _selection(result, "visible")
    assert selection.selected_fact_id == "visible"
    assert selection.excluded_future_fact_ids == ("future",)

    first_observed = _fact(
        "first-observed",
        published=T + timedelta(days=1),
        received=T + timedelta(days=1),
        period_end=datetime(2025, 3, 31, tzinfo=UTC),
    )
    unavailable = select_financial_fact_vintages((first_observed,), canonical_instrument_id="NSE:ALPHA", as_of=T, policy=POLICY)
    value = _selection(unavailable, "first-observed")
    assert value.status is FinancialFactVintageSelectionStatus.UNAVAILABLE
    assert value.reasons == (FinancialFactVintageSelectionReason.NO_PIT_ELIGIBLE_FACT,)


def test_linear_revisions_are_pit_safe_across_three_vintages() -> None:
    first = _fact("f1", published=T - timedelta(days=20))
    second = _fact("f2", value="101", published=T - timedelta(days=10), revision_of_fact_id="f1")
    third = _fact("f3", value="102", published=T - timedelta(days=2), revision_of_fact_id="f2")
    before_second = select_financial_fact_vintages((third, first, second), canonical_instrument_id="NSE:ALPHA", as_of=T - timedelta(days=15), policy=POLICY)
    after_second = select_financial_fact_vintages((first, third, second), canonical_instrument_id="NSE:ALPHA", as_of=T - timedelta(days=5), policy=POLICY)
    after_third = select_financial_fact_vintages((second, first, third), canonical_instrument_id="NSE:ALPHA", as_of=T, policy=POLICY)
    assert _selection(before_second, "f1").selected_fact_id == "f1"
    assert _selection(after_second, "f1").selected_fact_id == "f2"
    final = _selection(after_third, "f1")
    assert final.selected_fact_id == "f3"
    assert final.superseded_fact_ids == ("f1", "f2")


def test_scope_period_and_representation_identites_never_compete() -> None:
    values = (
        _fact("consolidated"),
        _fact("standalone", scope=StatementScope.STANDALONE),
        _fact("unknown", scope=StatementScope.UNKNOWN),
        _fact("annual", period_type=FinancialPeriodType.ANNUAL, basis=FinancialValueBasis.FULL_YEAR),
        _fact("usd", currency="USD", unit="USD"),
        _fact("millions", scale=NumericScale.MILLIONS),
    )
    batch = select_financial_fact_vintages(values, canonical_instrument_id="NSE:ALPHA", as_of=T, policy=POLICY)
    assert len(batch.selections) == len(values)
    assert all(value.status is FinancialFactVintageSelectionStatus.SELECTED for value in batch.selections)


def test_insufficient_identity_is_preserved_not_silently_dropped() -> None:
    invalid = _fact("invalid", normalization_version="")
    batch = select_financial_fact_vintages((invalid,), canonical_instrument_id="NSE:ALPHA", as_of=T, policy=POLICY)
    value = _selection(batch, "invalid")
    assert value.semantic_key is None
    assert value.status is FinancialFactVintageSelectionStatus.INSUFFICIENT_IDENTITY
    assert value.reasons == (FinancialFactVintageSelectionReason.AMBIGUOUS_SEMANTIC_KEY,)


def test_revised_without_parent_warning_or_conflict_is_frozen() -> None:
    revised = _fact(
        "revised",
        quality_flags=(FinancialQualityFlag.COMPLETE, FinancialQualityFlag.REVISED),
    )
    sole = select_financial_fact_vintages((revised,), canonical_instrument_id="NSE:ALPHA", as_of=T, policy=POLICY)
    assert _selection(sole, "revised").warnings == (
        FinancialFactVintageSelectionWarning.REVISED_WITHOUT_EXPLICIT_PARENT,
    )

    competitor = _fact("competitor", value="101", published=T - timedelta(days=1))
    conflicted = select_financial_fact_vintages((revised, competitor), canonical_instrument_id="NSE:ALPHA", as_of=T, policy=POLICY)
    value = _selection(conflicted, "revised")
    assert value.status is FinancialFactVintageSelectionStatus.CONFLICTED
    assert value.reasons == (FinancialFactVintageSelectionReason.UNRESOLVED_FACT_CONFLICT,)


@pytest.mark.parametrize(
    ("facts", "reason"),
    (
        ((_fact("child", revision_of_fact_id="missing"),), FinancialFactVintageSelectionReason.REVISION_PARENT_MISSING),
        ((_fact("parent", metric=FinancialMetric.PAT), _fact("child", revision_of_fact_id="parent")), FinancialFactVintageSelectionReason.CROSS_SEMANTIC_REVISION),
        ((_fact("parent", published=T), _fact("child", published=T - timedelta(days=1), revision_of_fact_id="parent")), FinancialFactVintageSelectionReason.INVALID_REVISION_CHRONOLOGY),
        ((_fact("f1", revision_of_fact_id="f2"), _fact("f2", revision_of_fact_id="f1")), FinancialFactVintageSelectionReason.REVISION_CYCLE),
        ((_fact("f1"), _fact("f2", value="101", revision_of_fact_id="f1"), _fact("f3", value="102", revision_of_fact_id="f1")), FinancialFactVintageSelectionReason.REVISION_BRANCH_CONFLICT),
    ),
)
def test_broken_revision_lineage_fails_closed(
    facts: tuple[FinancialFact, ...],
    reason: FinancialFactVintageSelectionReason,
) -> None:
    batch = select_financial_fact_vintages(facts, canonical_instrument_id="NSE:ALPHA", as_of=T, policy=POLICY)
    affected = next(
        value for value in batch.selections
        if reason in value.reasons
    )
    assert affected.status is FinancialFactVintageSelectionStatus.INVALID_LINEAGE


def test_exact_duplicates_retain_provenance_but_value_equality_is_not_enough() -> None:
    duplicate_a = _fact("a", filing_id="filing", source_reference="document")
    duplicate_b = _fact("b", filing_id="filing", source_reference="document")
    duplicate_batch = select_financial_fact_vintages((duplicate_b, duplicate_a), canonical_instrument_id="NSE:ALPHA", as_of=T, policy=POLICY)
    duplicate = _selection(duplicate_batch, "a")
    assert duplicate.selected_fact_id == "a"
    assert duplicate.duplicate_fact_ids == ("b",)

    equal_other_filing = _fact("c", filing_id="other-filing", source_reference="other-document")
    conflict = select_financial_fact_vintages((duplicate_a, equal_other_filing), canonical_instrument_id="NSE:ALPHA", as_of=T, policy=POLICY)
    value = _selection(conflict, "a")
    assert value.status is FinancialFactVintageSelectionStatus.CONFLICTED
    assert value.conflicting_fact_ids == ("a", "c")


def test_batch_partial_success_reason_counts_and_order_independence() -> None:
    revenue = _fact("revenue", metric=FinancialMetric.REVENUE)
    pat = _fact("pat", metric=FinancialMetric.PAT)
    debt_a = _fact("debt-a", metric=FinancialMetric.TOTAL_DEBT)
    debt_b = _fact("debt-b", metric=FinancialMetric.TOTAL_DEBT, value="101", source="SECONDARY", filing_id="secondary", source_reference="secondary")
    cash = _fact("cash", metric=FinancialMetric.CASH_AND_EQUIVALENTS, published=T + timedelta(days=1))
    values = [revenue, pat, debt_a, debt_b, cash]
    shuffled = values[:]
    random.Random(7).shuffle(shuffled)
    first = select_financial_fact_vintages(values, canonical_instrument_id="NSE:ALPHA", as_of=T, policy=POLICY)
    second = select_financial_fact_vintages(shuffled, canonical_instrument_id="NSE:ALPHA", as_of=T, policy=POLICY)
    assert first == second
    assert first.fingerprint == second.fingerprint
    assert {
        value.status for value in first.selections
    } == {
        FinancialFactVintageSelectionStatus.SELECTED,
        FinancialFactVintageSelectionStatus.CONFLICTED,
        FinancialFactVintageSelectionStatus.UNAVAILABLE,
    }
    assert dict(first.reason_counts) == {
        FinancialFactVintageSelectionReason.NO_PIT_ELIGIBLE_FACT: 1,
        FinancialFactVintageSelectionReason.UNRESOLVED_FACT_CONFLICT: 1,
    }


def test_foundational_input_validation_is_fail_closed() -> None:
    with pytest.raises(ValueError, match="AS_OF_TIMEZONE"):
        select_financial_fact_vintages((), canonical_instrument_id="NSE:ALPHA", as_of=datetime(2026, 8, 29), policy=POLICY)
    with pytest.raises(ValueError, match="FACT_TYPE"):
        select_financial_fact_vintages((object(),), canonical_instrument_id="NSE:ALPHA", as_of=T, policy=POLICY)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="MIXED_INSTRUMENT"):
        select_financial_fact_vintages((_fact("one"), _fact("two", instrument_id="NSE:BETA")), canonical_instrument_id="NSE:ALPHA", as_of=T, policy=POLICY)


def test_selector_is_pure_and_does_not_implement_downstream_layers() -> None:
    source = inspect.getsource(selector_module)
    for forbidden in (
        "SQLite",
        "PostgreSQL",
        "sqlite3",
        "requests",
        "urllib",
        "FastAPI",
        "APIRouter",
        "FinancialMetricObservation",
        "FinancialMetricTrajectory",
        "financial_fact_fingerprint",
    ):
        assert forbidden not in source
