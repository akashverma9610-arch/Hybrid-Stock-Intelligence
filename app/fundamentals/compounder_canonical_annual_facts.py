"""PIT-safe readiness receipts for existing canonical annual reported facts.

This module deliberately does not ingest, persist, derive, rank, or interpret
financial data.  ``FinancialFact`` and ``FinancialFactStore`` remain the sole
canonical fact and persistence contracts.  The receipt here only states which
directly mapped annual facts are safely selectable at a supplied historical
as-of for a *single* reporting scope.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
import json
from typing import Iterable

from app.data_sources.models import FundamentalFactKind
from app.fundamentals.financial_fact_vintage_selection_policy import (
    CURRENT_FROZEN_FINANCIAL_FACT_VINTAGE_SELECTION_POLICY,
    FinancialFactVintageSelectionStatus,
    FrozenFinancialFactVintageSelectionPolicy,
)
from app.fundamentals.financial_fact_vintage_selector import (
    FinancialFactVintageSelection,
    select_financial_fact_vintages,
)
from app.fundamentals.models import (
    FinancialFact,
    FinancialMetric,
    FinancialPeriodType,
    FinancialValueBasis,
    StatementScope,
)
from app.historical.guard import manifest_fingerprint


CONTRACT_ID = "long-term-compounder-canonical-annual-facts"
CONTRACT_VERSION = "v1"


class CompounderAnnualMeasureFamily(StrEnum):
    REVENUE = "REVENUE"
    EBIT_OR_EBITDA = "EBIT_OR_EBITDA"
    PROFIT_AFTER_TAX = "PROFIT_AFTER_TAX"
    CASH_FLOW_FROM_OPERATIONS = "CASH_FLOW_FROM_OPERATIONS"
    CAPITAL_EXPENDITURE = "CAPITAL_EXPENDITURE"
    DEBT_OR_BORROWINGS = "DEBT_OR_BORROWINGS"
    SHAREHOLDERS_EQUITY = "SHAREHOLDERS_EQUITY"
    CASH_AND_CASH_EQUIVALENTS = "CASH_AND_CASH_EQUIVALENTS"
    PERIOD_END_SHARES_OUTSTANDING = "PERIOD_END_SHARES_OUTSTANDING"


class AnnualStatementFamily(StrEnum):
    INCOME_STATEMENT = "INCOME_STATEMENT"
    BALANCE_SHEET = "BALANCE_SHEET"
    CASH_FLOW = "CASH_FLOW"
    SHARE_CAPITAL = "SHARE_CAPITAL"


class CanonicalAnnualFactReadinessStatus(StrEnum):
    PIT_READY = "PIT_READY"
    CANONICAL_DATA_MISSING = "CANONICAL_DATA_MISSING"
    PIT_UNAVAILABLE = "PIT_UNAVAILABLE"
    EVIDENCE_CONFLICTED = "EVIDENCE_CONFLICTED"
    INVALID_LINEAGE = "INVALID_LINEAGE"
    BASIS_MISMATCH = "BASIS_MISMATCH"
    PERIOD_IDENTITY_INCOMPLETE = "PERIOD_IDENTITY_INCOMPLETE"
    DEFINITION_MAPPING_UNAVAILABLE = "DEFINITION_MAPPING_UNAVAILABLE"


class CanonicalAnnualFactReadinessReason(StrEnum):
    DIRECT_REPORTED_MAPPING_REQUIRED = "DIRECT_REPORTED_MAPPING_REQUIRED"
    SHARE_COUNT_SEMANTIC_MAPPING_REQUIRED = "SHARE_COUNT_SEMANTIC_MAPPING_REQUIRED"
    NO_DIRECT_CANONICAL_FACT = "NO_DIRECT_CANONICAL_FACT"
    NO_PIT_ELIGIBLE_FACT = "NO_PIT_ELIGIBLE_FACT"
    UNRESOLVED_FACT_CONFLICT = "UNRESOLVED_FACT_CONFLICT"
    INVALID_FACT_LINEAGE = "INVALID_FACT_LINEAGE"
    FULL_YEAR_BASIS_REQUIRED = "FULL_YEAR_BASIS_REQUIRED"
    EXACT_SCOPE_REQUIRED = "EXACT_SCOPE_REQUIRED"
    COMPLETE_ANNUAL_PERIOD_IDENTITY_REQUIRED = "COMPLETE_ANNUAL_PERIOD_IDENTITY_REQUIRED"
    TWO_COMPARABLE_ANNUAL_PERIODS_REQUIRED = "TWO_COMPARABLE_ANNUAL_PERIODS_REQUIRED"
    THREE_COMPARABLE_ANNUAL_PERIODS_REQUIRED = "THREE_COMPARABLE_ANNUAL_PERIODS_REQUIRED"
    FIVE_COMPARABLE_ANNUAL_PERIODS_REQUIRED = "FIVE_COMPARABLE_ANNUAL_PERIODS_REQUIRED"


@dataclass(frozen=True, slots=True)
class CanonicalAnnualFactCoverage:
    """A factual, non-qualifying measure-family coverage receipt.

    ``selected_fact_ids`` are references to stored ``FinancialFact`` records,
    never copied values. A flow is comparable only when it is directly
    reported, full-year, scope-exact, PIT-selected, and has an explicit annual
    start/end/fiscal-year identity. A stock is comparable only when it is an
    exact point-in-time observation at the fiscal annual end; it never needs a
    fabricated duration.
    """

    measure_family: CompounderAnnualMeasureFamily
    statement_family: AnnualStatementFamily
    metric: FinancialMetric | None
    canonical_instrument_id: str
    statement_scope: StatementScope
    as_of: datetime
    status: CanonicalAnnualFactReadinessStatus
    reasons: tuple[CanonicalAnnualFactReadinessReason, ...]
    selected_fact_ids: tuple[str, ...]
    selected_period_ends: tuple[datetime, ...]
    selected_fact_fingerprints: tuple[str, ...]
    excluded_future_fact_ids: tuple[str, ...]
    conflicted_fact_ids: tuple[str, ...]
    annual_period_count: int
    comparable_annual_period_count: int
    usable_for_two_period_comparison: bool
    usable_for_three_year_research: bool
    usable_for_five_year_research: bool
    selection_policy_id: str | None
    selection_policy_version: str | None
    selection_policy_fingerprint: str | None
    fingerprint: str

    def __post_init__(self) -> None:
        if not self.canonical_instrument_id or not _aware(self.as_of):
            raise ValueError("CANONICAL_ANNUAL_FACT_COVERAGE_REQUEST_INVALID")
        if self.reasons != _ordered_reasons(self.reasons):
            raise ValueError("CANONICAL_ANNUAL_FACT_COVERAGE_REASONS_NONCANONICAL")
        if self.selected_fact_ids != tuple(sorted(set(self.selected_fact_ids))):
            raise ValueError("CANONICAL_ANNUAL_FACT_COVERAGE_FACT_IDS_NONCANONICAL")
        if self.selected_fact_fingerprints != tuple(sorted(set(self.selected_fact_fingerprints))):
            raise ValueError("CANONICAL_ANNUAL_FACT_COVERAGE_FACT_FINGERPRINTS_NONCANONICAL")
        if self.excluded_future_fact_ids != tuple(sorted(set(self.excluded_future_fact_ids))):
            raise ValueError("CANONICAL_ANNUAL_FACT_COVERAGE_FUTURE_FACTS_NONCANONICAL")
        if self.conflicted_fact_ids != tuple(sorted(set(self.conflicted_fact_ids))):
            raise ValueError("CANONICAL_ANNUAL_FACT_COVERAGE_CONFLICTS_NONCANONICAL")
        if self.selected_period_ends != tuple(sorted(set(self.selected_period_ends), key=_time)):
            raise ValueError("CANONICAL_ANNUAL_FACT_COVERAGE_PERIODS_NONCANONICAL")
        if self.annual_period_count != len(self.selected_period_ends):
            raise ValueError("CANONICAL_ANNUAL_FACT_COVERAGE_PERIOD_COUNT_INVALID")
        if not 0 <= self.comparable_annual_period_count <= self.annual_period_count:
            raise ValueError("CANONICAL_ANNUAL_FACT_COVERAGE_COMPARABILITY_COUNT_INVALID")
        usable = self.status is CanonicalAnnualFactReadinessStatus.PIT_READY
        if self.usable_for_two_period_comparison != (usable and self.comparable_annual_period_count >= 2):
            raise ValueError("CANONICAL_ANNUAL_FACT_COVERAGE_TWO_PERIOD_CONTRACT_INVALID")
        if self.usable_for_three_year_research != (usable and self.comparable_annual_period_count >= 3):
            raise ValueError("CANONICAL_ANNUAL_FACT_COVERAGE_THREE_YEAR_CONTRACT_INVALID")
        if self.usable_for_five_year_research != (usable and self.comparable_annual_period_count >= 5):
            raise ValueError("CANONICAL_ANNUAL_FACT_COVERAGE_FIVE_YEAR_CONTRACT_INVALID")
        if self.metric is None:
            if self.status is not CanonicalAnnualFactReadinessStatus.DEFINITION_MAPPING_UNAVAILABLE:
                raise ValueError("CANONICAL_ANNUAL_FACT_COVERAGE_MAPPING_STATUS_REQUIRED")
            if self.selected_fact_ids or self.selection_policy_id is not None:
                raise ValueError("CANONICAL_ANNUAL_FACT_COVERAGE_UNMAPPED_FACTS_FORBIDDEN")
        elif not all((self.selection_policy_id, self.selection_policy_version, self.selection_policy_fingerprint)):
            raise ValueError("CANONICAL_ANNUAL_FACT_COVERAGE_SELECTOR_LINEAGE_REQUIRED")
        if self.status is CanonicalAnnualFactReadinessStatus.PIT_READY and not self.selected_fact_ids:
            raise ValueError("CANONICAL_ANNUAL_FACT_COVERAGE_PIT_READY_FACT_REQUIRED")
        if self.fingerprint != canonical_annual_fact_coverage_fingerprint(self):
            raise ValueError("CANONICAL_ANNUAL_FACT_COVERAGE_FINGERPRINT_MISMATCH")


@dataclass(frozen=True, slots=True)
class CanonicalAnnualFactsReadinessReceipt:
    """Deterministic, on-demand annual-fact coverage for one instrument/as-of."""

    canonical_instrument_id: str
    statement_scope: StatementScope
    as_of: datetime
    covers: tuple[CanonicalAnnualFactCoverage, ...]
    contract_id: str
    contract_version: str
    fingerprint: str

    def __post_init__(self) -> None:
        if not self.canonical_instrument_id or not _aware(self.as_of):
            raise ValueError("CANONICAL_ANNUAL_FACT_RECEIPT_REQUEST_INVALID")
        if self.contract_id != CONTRACT_ID or self.contract_version != CONTRACT_VERSION:
            raise ValueError("CANONICAL_ANNUAL_FACT_RECEIPT_CONTRACT_INVALID")
        if self.covers != tuple(sorted(self.covers, key=lambda value: value.measure_family.value)):
            raise ValueError("CANONICAL_ANNUAL_FACT_RECEIPT_COVERS_NONCANONICAL")
        if tuple(value.measure_family for value in self.covers) != tuple(sorted(CompounderAnnualMeasureFamily, key=lambda value: value.value)):
            raise ValueError("CANONICAL_ANNUAL_FACT_RECEIPT_FAMILIES_REQUIRED")
        if self.fingerprint != canonical_annual_facts_readiness_fingerprint(self):
            raise ValueError("CANONICAL_ANNUAL_FACT_RECEIPT_FINGERPRINT_MISMATCH")


_DIRECT_METRICS: dict[CompounderAnnualMeasureFamily, FinancialMetric | None] = {
    CompounderAnnualMeasureFamily.REVENUE: FinancialMetric.REVENUE,
    # A future policy must choose one exact operating-profit definition; this
    # factual contract deliberately does not substitute EBIT for EBITDA.
    CompounderAnnualMeasureFamily.EBIT_OR_EBITDA: None,
    CompounderAnnualMeasureFamily.PROFIT_AFTER_TAX: FinancialMetric.PAT,
    CompounderAnnualMeasureFamily.CASH_FLOW_FROM_OPERATIONS: FinancialMetric.CFO,
    CompounderAnnualMeasureFamily.CAPITAL_EXPENDITURE: FinancialMetric.CAPEX,
    CompounderAnnualMeasureFamily.DEBT_OR_BORROWINGS: FinancialMetric.TOTAL_DEBT,
    CompounderAnnualMeasureFamily.SHAREHOLDERS_EQUITY: FinancialMetric.TOTAL_EQUITY,
    CompounderAnnualMeasureFamily.CASH_AND_CASH_EQUIVALENTS: FinancialMetric.CASH_AND_EQUIVALENTS,
    # Existing SHARES_OUTSTANDING does not identify period-end versus weighted
    # average, nor link corporate actions.  It therefore cannot be admitted.
    CompounderAnnualMeasureFamily.PERIOD_END_SHARES_OUTSTANDING: None,
}

_STATEMENT_FAMILIES = {
    CompounderAnnualMeasureFamily.REVENUE: AnnualStatementFamily.INCOME_STATEMENT,
    CompounderAnnualMeasureFamily.EBIT_OR_EBITDA: AnnualStatementFamily.INCOME_STATEMENT,
    CompounderAnnualMeasureFamily.PROFIT_AFTER_TAX: AnnualStatementFamily.INCOME_STATEMENT,
    CompounderAnnualMeasureFamily.CASH_FLOW_FROM_OPERATIONS: AnnualStatementFamily.CASH_FLOW,
    CompounderAnnualMeasureFamily.CAPITAL_EXPENDITURE: AnnualStatementFamily.CASH_FLOW,
    CompounderAnnualMeasureFamily.DEBT_OR_BORROWINGS: AnnualStatementFamily.BALANCE_SHEET,
    CompounderAnnualMeasureFamily.SHAREHOLDERS_EQUITY: AnnualStatementFamily.BALANCE_SHEET,
    CompounderAnnualMeasureFamily.CASH_AND_CASH_EQUIVALENTS: AnnualStatementFamily.BALANCE_SHEET,
    CompounderAnnualMeasureFamily.PERIOD_END_SHARES_OUTSTANDING: AnnualStatementFamily.SHARE_CAPITAL,
}

_POINT_IN_TIME_METRICS = frozenset({
    FinancialMetric.TOTAL_EQUITY, FinancialMetric.CASH_AND_EQUIVALENTS,
})


def assess_canonical_annual_facts(
    facts: Iterable[FinancialFact],
    *,
    canonical_instrument_id: str,
    statement_scope: StatementScope,
    as_of: datetime,
    policy: FrozenFinancialFactVintageSelectionPolicy = CURRENT_FROZEN_FINANCIAL_FACT_VINTAGE_SELECTION_POLICY,
) -> CanonicalAnnualFactsReadinessReceipt:
    """Return a rebuildable reported-fact coverage receipt without persistence.

    The supplied collection must be complete for the requested factual view.
    The function deliberately has no repository argument so a caller cannot
    accidentally invoke a "latest now" query while rebuilding historical data.
    """
    if not canonical_instrument_id or not _aware(as_of):
        raise ValueError("CANONICAL_ANNUAL_FACTS_REQUEST_INVALID")
    if not isinstance(statement_scope, StatementScope):
        raise ValueError("CANONICAL_ANNUAL_FACTS_SCOPE_INVALID")
    values = tuple(facts)
    if not all(isinstance(value, FinancialFact) for value in values):
        raise ValueError("CANONICAL_ANNUAL_FACTS_FACT_TYPE_INVALID")
    if any(value.instrument.instrument_id != canonical_instrument_id for value in values):
        raise ValueError("CANONICAL_ANNUAL_FACTS_INSTRUMENT_MISMATCH")
    if len({value.fact_id for value in values}) != len(values):
        raise ValueError("CANONICAL_ANNUAL_FACTS_DUPLICATE_ID_INPUT")

    covers = tuple(
        _coverage(values, family, canonical_instrument_id, statement_scope, as_of, policy)
        for family in CompounderAnnualMeasureFamily
    )
    covers = tuple(sorted(covers, key=lambda value: value.measure_family.value))
    payload = dict(
        canonical_instrument_id=canonical_instrument_id,
        statement_scope=statement_scope,
        as_of=as_of,
        covers=covers,
        contract_id=CONTRACT_ID,
        contract_version=CONTRACT_VERSION,
    )
    return CanonicalAnnualFactsReadinessReceipt(
        **payload,
        fingerprint=canonical_annual_facts_readiness_fingerprint_values(payload),
    )


def canonical_annual_fact_coverage_fingerprint(value: CanonicalAnnualFactCoverage) -> str:
    return canonical_annual_fact_coverage_fingerprint_values(
        {field: getattr(value, field) for field in value.__dataclass_fields__ if field != "fingerprint"}
    )


def canonical_annual_fact_coverage_fingerprint_values(values: dict[str, object]) -> str:
    return manifest_fingerprint(
        measure_family=values["measure_family"].value,
        statement_family=values["statement_family"].value,
        metric=None if values["metric"] is None else values["metric"].value,
        canonical_instrument_id=values["canonical_instrument_id"],
        statement_scope=values["statement_scope"].value,
        as_of=_time(values["as_of"]), status=values["status"].value,
        reasons=tuple(value.value for value in values["reasons"]),
        selected_fact_ids=values["selected_fact_ids"],
        selected_period_ends=tuple(_time(value) for value in values["selected_period_ends"]),
        selected_fact_fingerprints=values["selected_fact_fingerprints"],
        excluded_future_fact_ids=values["excluded_future_fact_ids"],
        conflicted_fact_ids=values["conflicted_fact_ids"],
        annual_period_count=values["annual_period_count"],
        comparable_annual_period_count=values["comparable_annual_period_count"],
        usable_for_two_period_comparison=values["usable_for_two_period_comparison"],
        usable_for_three_year_research=values["usable_for_three_year_research"],
        usable_for_five_year_research=values["usable_for_five_year_research"],
        selection_policy_id=values["selection_policy_id"],
        selection_policy_version=values["selection_policy_version"],
        selection_policy_fingerprint=values["selection_policy_fingerprint"],
    )


def canonical_annual_facts_readiness_fingerprint(value: CanonicalAnnualFactsReadinessReceipt) -> str:
    return canonical_annual_facts_readiness_fingerprint_values(
        {field: getattr(value, field) for field in value.__dataclass_fields__ if field != "fingerprint"}
    )


def canonical_annual_facts_readiness_fingerprint_values(values: dict[str, object]) -> str:
    return manifest_fingerprint(
        canonical_instrument_id=values["canonical_instrument_id"],
        statement_scope=values["statement_scope"].value,
        as_of=_time(values["as_of"]),
        covers=tuple(value.fingerprint for value in values["covers"]),
        contract_id=values["contract_id"], contract_version=values["contract_version"],
    )


def serialize_canonical_annual_facts_readiness(value: CanonicalAnnualFactsReadinessReceipt) -> str:
    """Stable, explicit serialization for audit/export; it never writes data."""
    if value.fingerprint != canonical_annual_facts_readiness_fingerprint(value):
        raise ValueError("CANONICAL_ANNUAL_FACT_RECEIPT_FINGERPRINT_MISMATCH")
    return json.dumps(_receipt_payload(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _coverage(
    values: tuple[FinancialFact, ...], family: CompounderAnnualMeasureFamily,
    canonical_instrument_id: str, statement_scope: StatementScope, as_of: datetime,
    policy: FrozenFinancialFactVintageSelectionPolicy,
) -> CanonicalAnnualFactCoverage:
    metric = _DIRECT_METRICS[family]
    if metric is None:
        reason = (
            CanonicalAnnualFactReadinessReason.SHARE_COUNT_SEMANTIC_MAPPING_REQUIRED
            if family is CompounderAnnualMeasureFamily.PERIOD_END_SHARES_OUTSTANDING
            else CanonicalAnnualFactReadinessReason.DIRECT_REPORTED_MAPPING_REQUIRED
        )
        return _make_coverage(
            family, metric, canonical_instrument_id, statement_scope, as_of,
            CanonicalAnnualFactReadinessStatus.DEFINITION_MAPPING_UNAVAILABLE,
            (reason,), (), (), (), (), 0, 0, None,
        )

    relevant = tuple(value for value in values if value.metric is metric)
    admitted = tuple(
        value for value in relevant
        if value.fact_kind is FundamentalFactKind.REPORTED
        and _admitted_period(value, metric)
        and value.statement_scope is statement_scope
    )
    wrong_basis = any(
        value.fact_kind is FundamentalFactKind.REPORTED
        and value.statement_scope is statement_scope
        and not _admitted_period(value, metric)
        for value in relevant
    )
    wrong_scope = any(
        value.fact_kind is FundamentalFactKind.REPORTED
        and _admitted_period(value, metric)
        and value.statement_scope is not statement_scope
        for value in relevant
    )
    if not admitted:
        status = (CanonicalAnnualFactReadinessStatus.BASIS_MISMATCH if wrong_basis or wrong_scope
                  else CanonicalAnnualFactReadinessStatus.CANONICAL_DATA_MISSING)
        reasons: tuple[CanonicalAnnualFactReadinessReason, ...] = ()
        if wrong_basis:
            reasons += (CanonicalAnnualFactReadinessReason.FULL_YEAR_BASIS_REQUIRED,)
        if wrong_scope:
            reasons += (CanonicalAnnualFactReadinessReason.EXACT_SCOPE_REQUIRED,)
        if not reasons:
            reasons = (CanonicalAnnualFactReadinessReason.NO_DIRECT_CANONICAL_FACT,)
        return _make_coverage(
            family, metric, canonical_instrument_id, statement_scope, as_of,
            status, reasons, (), (), (), (), 0, 0, policy,
        )

    batch = select_financial_fact_vintages(
        admitted, canonical_instrument_id=canonical_instrument_id, as_of=as_of, policy=policy,
    )
    by_id = {value.fact_id: value for value in admitted}
    selections = tuple(sorted(batch.selections, key=lambda value: value.ordering_key()))
    selected = tuple(
        by_id[value.selected_fact_id] for value in selections
        if value.status is FinancialFactVintageSelectionStatus.SELECTED and value.selected_fact_id is not None
    )
    selected = tuple(sorted(selected, key=lambda value: (value.period_end.astimezone(UTC), value.fact_id)))
    future = tuple(sorted({fact_id for value in selections for fact_id in value.excluded_future_fact_ids}))
    conflicts = tuple(sorted({fact_id for value in selections for fact_id in value.conflicting_fact_ids}))
    has_invalid = any(value.status is FinancialFactVintageSelectionStatus.INVALID_LINEAGE for value in selections)
    has_conflict = any(value.status is FinancialFactVintageSelectionStatus.CONFLICTED for value in selections)
    no_visible = bool(selections) and not selected and all(
        value.status is FinancialFactVintageSelectionStatus.UNAVAILABLE for value in selections
    )
    periods = tuple(sorted({value.period_end for value in selected}, key=_time))
    complete = tuple(value for value in selected if _complete_annual_identity(value))
    comparable_periods = tuple(sorted({value.period_end for value in complete}, key=_time))
    if has_invalid:
        status, reasons = CanonicalAnnualFactReadinessStatus.INVALID_LINEAGE, (CanonicalAnnualFactReadinessReason.INVALID_FACT_LINEAGE,)
    elif has_conflict:
        status, reasons = CanonicalAnnualFactReadinessStatus.EVIDENCE_CONFLICTED, (CanonicalAnnualFactReadinessReason.UNRESOLVED_FACT_CONFLICT,)
    elif no_visible:
        status, reasons = CanonicalAnnualFactReadinessStatus.PIT_UNAVAILABLE, (CanonicalAnnualFactReadinessReason.NO_PIT_ELIGIBLE_FACT,)
    elif selected and len(complete) != len(selected):
        status, reasons = CanonicalAnnualFactReadinessStatus.PERIOD_IDENTITY_INCOMPLETE, (CanonicalAnnualFactReadinessReason.COMPLETE_ANNUAL_PERIOD_IDENTITY_REQUIRED,)
    elif selected:
        status, reasons = CanonicalAnnualFactReadinessStatus.PIT_READY, ()
    else:
        status, reasons = CanonicalAnnualFactReadinessStatus.CANONICAL_DATA_MISSING, (CanonicalAnnualFactReadinessReason.NO_DIRECT_CANONICAL_FACT,)
    return _make_coverage(
        family, metric, canonical_instrument_id, statement_scope, as_of, status, reasons,
        tuple(value.fact_id for value in selected), periods,
        tuple(_fact_fingerprint(value) for value in selected), future, len(periods),
        len(comparable_periods), policy, conflicts,
    )


def _make_coverage(
    family: CompounderAnnualMeasureFamily, metric: FinancialMetric | None,
    canonical_instrument_id: str, statement_scope: StatementScope, as_of: datetime,
    status: CanonicalAnnualFactReadinessStatus,
    reasons: tuple[CanonicalAnnualFactReadinessReason, ...], selected_ids: tuple[str, ...],
    periods: tuple[datetime, ...], selected_fingerprints: tuple[str, ...],
    future: tuple[str, ...], annual_count: int, comparable_count: int,
    policy: FrozenFinancialFactVintageSelectionPolicy | None,
    conflicts: tuple[str, ...] = (),
) -> CanonicalAnnualFactCoverage:
    values = dict(
        measure_family=family, statement_family=_STATEMENT_FAMILIES[family], metric=metric,
        canonical_instrument_id=canonical_instrument_id, statement_scope=statement_scope,
        as_of=as_of, status=status, reasons=_ordered_reasons(reasons),
        selected_fact_ids=tuple(sorted(set(selected_ids))),
        selected_period_ends=tuple(sorted(set(periods), key=_time)),
        selected_fact_fingerprints=tuple(sorted(set(selected_fingerprints))),
        excluded_future_fact_ids=tuple(sorted(set(future))),
        conflicted_fact_ids=tuple(sorted(set(conflicts))), annual_period_count=annual_count,
        comparable_annual_period_count=comparable_count,
        usable_for_two_period_comparison=(
            status is CanonicalAnnualFactReadinessStatus.PIT_READY and comparable_count >= 2
        ),
        usable_for_three_year_research=(
            status is CanonicalAnnualFactReadinessStatus.PIT_READY and comparable_count >= 3
        ),
        usable_for_five_year_research=(
            status is CanonicalAnnualFactReadinessStatus.PIT_READY and comparable_count >= 5
        ),
        selection_policy_id=None if policy is None else policy.policy_id,
        selection_policy_version=None if policy is None else policy.version,
        selection_policy_fingerprint=None if policy is None else policy.fingerprint,
    )
    return CanonicalAnnualFactCoverage(
        **values, fingerprint=canonical_annual_fact_coverage_fingerprint_values(values),
    )


def _complete_annual_identity(value: FinancialFact) -> bool:
    if value.period_type is FinancialPeriodType.POINT_IN_TIME:
        return value.fiscal_year is not None
    return value.period_start is not None and value.fiscal_year is not None and value.period_start < value.period_end


def _admitted_period(value: FinancialFact, metric: FinancialMetric) -> bool:
    if metric in _POINT_IN_TIME_METRICS:
        return value.period_type is FinancialPeriodType.POINT_IN_TIME and value.value_basis is FinancialValueBasis.UNKNOWN
    return value.period_type is FinancialPeriodType.ANNUAL and value.value_basis is FinancialValueBasis.FULL_YEAR


def _fact_fingerprint(value: FinancialFact) -> str:
    return manifest_fingerprint(
        fact_id=value.fact_id, canonical_instrument_id=value.instrument.instrument_id,
        metric=value.metric.value, value=str(value.value), currency=value.currency, unit=value.unit,
        scale=value.scale.value, period_type=value.period_type.value, value_basis=value.value_basis.value,
        period_start=_time(value.period_start), period_end=_time(value.period_end), fiscal_year=value.fiscal_year,
        fiscal_quarter=value.fiscal_quarter, value_dimension=value.value_dimension.value,
        statement_scope=value.statement_scope.value, fact_kind=value.fact_kind.value, source=value.source,
        filing_id=value.filing_id, source_reference=value.source_reference,
        published_at=_time(value.published_at), received_at=_time(value.received_at),
        normalization_version=value.normalization_version, provenance=value.provenance,
        parent_fact_ids=value.parent_fact_ids, revision_of_fact_id=value.revision_of_fact_id,
        quality_flags=tuple(flag.value for flag in value.quality_flags),
    )


def _receipt_payload(value: CanonicalAnnualFactsReadinessReceipt) -> dict[str, object]:
    return {
        "canonical_instrument_id": value.canonical_instrument_id,
        "statement_scope": value.statement_scope.value, "as_of": _time(value.as_of),
        "contract_id": value.contract_id, "contract_version": value.contract_version,
        "covers": tuple({
            "measure_family": cover.measure_family.value, "statement_family": cover.statement_family.value,
            "metric": None if cover.metric is None else cover.metric.value,
            "status": cover.status.value, "reasons": tuple(reason.value for reason in cover.reasons),
            "selected_fact_ids": cover.selected_fact_ids,
            "selected_period_ends": tuple(_time(period) for period in cover.selected_period_ends),
            "selected_fact_fingerprints": cover.selected_fact_fingerprints,
            "excluded_future_fact_ids": cover.excluded_future_fact_ids,
            "conflicted_fact_ids": cover.conflicted_fact_ids,
            "annual_period_count": cover.annual_period_count,
            "comparable_annual_period_count": cover.comparable_annual_period_count,
            "usable_for_two_period_comparison": cover.usable_for_two_period_comparison,
            "usable_for_three_year_research": cover.usable_for_three_year_research,
            "usable_for_five_year_research": cover.usable_for_five_year_research,
            "selection_policy_id": cover.selection_policy_id,
            "selection_policy_version": cover.selection_policy_version,
            "selection_policy_fingerprint": cover.selection_policy_fingerprint,
            "fingerprint": cover.fingerprint,
        } for cover in value.covers),
        "fingerprint": value.fingerprint,
    }


def _ordered_reasons(values: Iterable[CanonicalAnnualFactReadinessReason]) -> tuple[CanonicalAnnualFactReadinessReason, ...]:
    return tuple(sorted(set(values), key=lambda value: value.value))


def _aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


def _time(value: datetime | None) -> str | None:
    return None if value is None else value.astimezone(UTC).isoformat()


__all__ = (
    "AnnualStatementFamily", "CanonicalAnnualFactCoverage", "CanonicalAnnualFactReadinessReason",
    "CanonicalAnnualFactReadinessStatus", "CanonicalAnnualFactsReadinessReceipt",
    "CompounderAnnualMeasureFamily", "CONTRACT_ID", "CONTRACT_VERSION",
    "assess_canonical_annual_facts", "canonical_annual_fact_coverage_fingerprint",
    "canonical_annual_facts_readiness_fingerprint", "serialize_canonical_annual_facts_readiness",
)
