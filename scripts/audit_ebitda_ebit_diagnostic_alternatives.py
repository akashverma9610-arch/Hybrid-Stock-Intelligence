"""Read-only feasibility audit for non-standard EBITDA/EBIT alternatives.

This research tool deliberately selects factual PIT vintages but never adds,
subtracts, stores, or emits their values.  Its candidate names are descriptive
only: neither is EBIT or EBITDA, and neither is a new canonical metric.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import sys
from typing import Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.fundamentals.financial_fact_vintage_selection_policy import (
    CURRENT_FROZEN_FINANCIAL_FACT_VINTAGE_SELECTION_POLICY,
)
from app.fundamentals.financial_fact_vintage_selector import (
    FinancialFactVintageSelectionStatus,
    select_financial_fact_vintages,
)
from app.fundamentals.models import (
    FinancialFact,
    FinancialMetric,
    FinancialPeriodType,
)
from app.fundamentals.store import _fact
from app.historical.pit_company_type_classification_activation import (
    PitCompanyTypeClassificationReceipt,
    PitCompanyTypeClassificationState,
)
from app.storage.core_api_snapshot_repository import snapshot_json_from


POLICY_VERSION = "ebitda-ebit-diagnostic-policy-alternative-research-v1"
REPORT_KIND = "READ_ONLY_CANDIDATE_FEASIBILITY"
UNKNOWN_NON_COMPARABLE = "UNKNOWN_NON_COMPARABLE"


@dataclass(frozen=True, slots=True)
class CandidateFormula:
    candidate_id: str
    descriptive_name: str
    parent_metrics: tuple[FinancialMetric, ...]
    comparison_status: str


CANDIDATES = (
    CandidateFormula(
        "CANDIDATE_A_PBT_PLUS_FINANCE_COST",
        "PRE_FINANCE_COST_PRE_TAX_PROFIT",
        (FinancialMetric.PBT, FinancialMetric.FINANCE_COST),
        "NOT_EBIT",
    ),
    CandidateFormula(
        "CANDIDATE_B_PBT_PLUS_FINANCE_COST_PLUS_DEPRECIATION",
        "PRE_FINANCE_COST_PRE_DA_PRE_TAX_PROFIT",
        (FinancialMetric.PBT, FinancialMetric.FINANCE_COST, FinancialMetric.DEPRECIATION),
        "NOT_EBITDA",
    ),
    CandidateFormula(
        "CANDIDATE_C_B_MINUS_OTHER_INCOME",
        "PRE_FINANCE_COST_PRE_DA_PRE_TAX_PROFIT_MINUS_OTHER_INCOME",
        (
            FinancialMetric.PBT,
            FinancialMetric.FINANCE_COST,
            FinancialMetric.DEPRECIATION,
            FinancialMetric.OTHER_INCOME,
        ),
        "NOT_EBITDA_AND_OTHER_INCOME_SUBTRACTION_UNAPPROVED",
    ),
)


@dataclass(frozen=True, slots=True)
class CandidateCoordinate:
    """One exact parent-compatible coordinate; it deliberately has no value."""

    formula_id: str
    period_type: str
    statement_scope: str
    value_basis: str
    period_start: str | None
    period_end: str
    fiscal_year: int | None
    fiscal_quarter: int | None
    currency: str
    unit: str
    scale: str
    normalization_version: str
    parent_fact_ids: tuple[str, ...]

    def series_key(self) -> tuple[str, ...]:
        return (
            self.period_type,
            self.statement_scope,
            self.value_basis,
            self.currency,
            self.unit,
            self.scale,
            self.normalization_version,
        )

    def ordering_key(self) -> tuple[str, ...]:
        return (
            self.period_type,
            self.statement_scope,
            self.value_basis,
            self.period_start or "",
            self.period_end,
            "" if self.fiscal_year is None else str(self.fiscal_year),
            "" if self.fiscal_quarter is None else str(self.fiscal_quarter),
            self.currency,
            self.unit,
            self.scale,
            self.normalization_version,
            *self.parent_fact_ids,
        )


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=_json_default)


def _json_default(value: object) -> str:
    if isinstance(value, datetime):
        return _utc(value).isoformat()
    if isinstance(value, CandidateCoordinate):
        return {
            field: getattr(value, field)
            for field in value.__dataclass_fields__
        }
    raise TypeError(f"Unsupported audit value: {type(value).__name__}")


def _fingerprint(value: object) -> str:
    return "sha256:" + sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("AUDIT_AS_OF_TIMEZONE_REQUIRED")
    return value.astimezone(UTC)


def parse_as_of(value: str) -> datetime:
    return _utc(datetime.fromisoformat(value.replace("Z", "+00:00")))


def _fact_coordinate(fact: FinancialFact) -> tuple[object, ...]:
    return (
        fact.period_type.value,
        fact.statement_scope.value,
        fact.value_basis.value,
        _utc(fact.period_start).isoformat() if fact.period_start is not None else None,
        _utc(fact.period_end).isoformat(),
        fact.fiscal_year,
        fact.fiscal_quarter,
        fact.currency,
        fact.unit,
        fact.scale.value,
        fact.normalization_version,
    )


def _candidate_coordinates(
    selected_facts: Iterable[FinancialFact], candidate: CandidateFormula,
) -> tuple[CandidateCoordinate, ...]:
    """Return only exact, parent-compatible coordinates; never calculate values."""
    grouped: dict[tuple[object, ...], dict[FinancialMetric, FinancialFact]] = defaultdict(dict)
    for fact in selected_facts:
        if fact.metric not in candidate.parent_metrics:
            continue
        key = _fact_coordinate(fact)
        existing = grouped[key].get(fact.metric)
        if existing is not None and existing.fact_id != fact.fact_id:
            raise ValueError("AUDIT_SELECTED_COMPONENT_AMBIGUOUS")
        grouped[key][fact.metric] = fact

    values: list[CandidateCoordinate] = []
    for key, components in grouped.items():
        if not all(metric in components for metric in candidate.parent_metrics):
            continue
        period_type, scope, basis, start, end, year, quarter, currency, unit, scale, version = key
        values.append(CandidateCoordinate(
            formula_id=candidate.candidate_id,
            period_type=str(period_type),
            statement_scope=str(scope),
            value_basis=str(basis),
            period_start=start if isinstance(start, str) else None,
            period_end=str(end),
            fiscal_year=year if isinstance(year, int) else None,
            fiscal_quarter=quarter if isinstance(quarter, int) else None,
            currency=str(currency), unit=str(unit), scale=str(scale),
            normalization_version=str(version),
            parent_fact_ids=tuple(components[metric].fact_id for metric in candidate.parent_metrics),
        ))
    return tuple(sorted(values, key=lambda value: value.ordering_key()))


def _selected_reported_facts(
    facts: Iterable[FinancialFact], *, instrument_id: str, as_of: datetime,
) -> tuple[tuple[FinancialFact, ...], Counter[str], tuple[tuple[str, str], ...]]:
    """Apply the existing frozen factual-vintage selector; it has no writes."""
    values = tuple(sorted(facts, key=lambda value: value.fact_id))
    selection = select_financial_fact_vintages(
        values,
        canonical_instrument_id=instrument_id,
        as_of=as_of,
        policy=CURRENT_FROZEN_FINANCIAL_FACT_VINTAGE_SELECTION_POLICY,
    )
    by_id = {fact.fact_id: fact for fact in values}
    selected = tuple(
        by_id[item.selected_fact_id]
        for item in selection.selections
        if item.status is FinancialFactVintageSelectionStatus.SELECTED
        and item.selected_fact_id is not None
        and by_id[item.selected_fact_id].fact_kind.value == "REPORTED"
    )
    statuses = tuple(
        (item.semantic_key.metric.value, item.status.value)
        for item in selection.selections
        if item.semantic_key is not None
    )
    return selected, Counter(item.status.value for item in selection.selections), statuses


def _depth(coordinates: Iterable[CandidateCoordinate], period_type: str) -> int:
    """Maximum exact-compatible historical depth in one series, without values."""
    series: dict[tuple[str, ...], set[str]] = defaultdict(set)
    for item in coordinates:
        if item.period_type == period_type:
            series[item.series_key()].add(item.period_end)
    return max((len(periods) for periods in series.values()), default=0)


def _representation_or_period_conflicts(
    selected_facts: Iterable[FinancialFact], candidate: CandidateFormula,
) -> tuple[int, int]:
    """Count only incompatible parent presentations, not valid multi-scope facts."""
    broad: dict[tuple[object, ...], dict[FinancialMetric, set[tuple[object, ...]]]] = defaultdict(lambda: defaultdict(set))
    for fact in selected_facts:
        if fact.metric not in candidate.parent_metrics:
            continue
        broad_key = (
            fact.period_type.value, fact.value_basis.value,
            _utc(fact.period_end).isoformat(), fact.fiscal_year, fact.fiscal_quarter,
        )
        broad[broad_key][fact.metric].add((
            fact.statement_scope.value, fact.currency, fact.unit, fact.scale.value,
            fact.normalization_version,
            _utc(fact.period_start).isoformat() if fact.period_start is not None else None,
        ))
    unit_scope = period_identity = 0
    for metric_sets in broad.values():
        if not all(metric in metric_sets for metric in candidate.parent_metrics):
            continue
        shared = set.intersection(*(metric_sets[metric] for metric in candidate.parent_metrics))
        # Multiple complete standalone/consolidated coordinates are legitimate
        # facts.  A conflict exists only when no one exact coordinate can join
        # all required parent metrics.
        if shared:
            continue
        union = set().union(*(metric_sets[metric] for metric in candidate.parent_metrics))
        if len({item[:5] for item in union}) > 1:
            unit_scope += 1
        if len({item[5] for item in union}) > 1:
            period_identity += 1
    return unit_scope, period_identity


def assess_instrument(
    facts: Iterable[FinancialFact], *, instrument_id: str, as_of: datetime,
) -> dict[str, object]:
    selected, selection_statuses, selection_metric_statuses = _selected_reported_facts(
        facts, instrument_id=instrument_id, as_of=as_of,
    )
    result: dict[str, object] = {
        "instrument_id": instrument_id,
        "selector_status_counts": tuple(sorted(selection_statuses.items())),
        "candidates": (),
    }
    candidates: list[dict[str, object]] = []
    for candidate in CANDIDATES:
        coordinates = _candidate_coordinates(selected, candidate)
        unit_scope, period_identity = _representation_or_period_conflicts(selected, candidate)
        available_metrics = {fact.metric for fact in selected}
        candidates.append({
            "candidate_id": candidate.candidate_id,
            "descriptive_name": candidate.descriptive_name,
            "comparison_status": candidate.comparison_status,
            "parent_metrics": tuple(metric.value for metric in candidate.parent_metrics),
            "annual_depth": _depth(coordinates, FinancialPeriodType.ANNUAL.value),
            "quarterly_depth": _depth(coordinates, FinancialPeriodType.QUARTERLY.value),
            "period_observations_available": len(coordinates),
            "unit_scope_conflicts": unit_scope,
            "period_identity_conflicts": period_identity,
            "candidate_vintage_conflicts": sum(
                status in {"CONFLICTED", "INVALID_LINEAGE"}
                for metric, status in selection_metric_statuses
                if metric in {item.value for item in candidate.parent_metrics}
            ),
            "missing_components": tuple(
                metric.value for metric in candidate.parent_metrics if metric not in available_metrics
            ),
            "coordinates": coordinates,
        })
    result["candidates"] = tuple(candidates)
    return result


def classify_company_types(
    receipts: Iterable[PitCompanyTypeClassificationReceipt], *, as_of: datetime,
) -> Mapping[str, str]:
    """Choose one exact, PIT-visible classification receipt per instrument.

    A tie with distinct latest receipts is intentionally not resolved by input
    order; it is returned as unknown/non-comparable for this audit.
    """
    grouped: dict[str, list[PitCompanyTypeClassificationReceipt]] = defaultdict(list)
    for receipt in receipts:
        receipt.verify()
        if receipt.evaluated_as_of <= as_of:
            grouped[receipt.canonical_instrument_id].append(receipt)
    result: dict[str, str] = {}
    for instrument_id, values in grouped.items():
        latest_time = max(_utc(item.evaluated_as_of) for item in values)
        latest = [item for item in values if _utc(item.evaluated_as_of) == latest_time]
        fingerprints = {item.fingerprint for item in latest}
        if len(fingerprints) != 1:
            result[instrument_id] = UNKNOWN_NON_COMPARABLE
            continue
        receipt = latest[0]
        if (
            receipt.state is PitCompanyTypeClassificationState.CLASSIFIED
            and receipt.company_type is not None
        ):
            result[instrument_id] = receipt.company_type.value
        else:
            result[instrument_id] = UNKNOWN_NON_COMPARABLE
    return dict(sorted(result.items()))


def feasibility_report(
    facts_by_instrument: Mapping[str, Iterable[FinancialFact]],
    *, as_of: datetime, company_types: Mapping[str, str],
) -> dict[str, object]:
    """Build a replayable metadata-only report. It never contains fact values."""
    as_of = _utc(as_of)
    instruments = tuple(sorted(facts_by_instrument))
    items = tuple(
        assess_instrument(facts_by_instrument[instrument_id], instrument_id=instrument_id, as_of=as_of)
        for instrument_id in instruments
    )
    aggregate: list[dict[str, object]] = []
    for candidate in CANDIDATES:
        matches = [
            item["candidates"][index]
            for item in items
            for index, current in enumerate(CANDIDATES)
            if current.candidate_id == candidate.candidate_id
        ]
        aggregate.append({
            "candidate_id": candidate.candidate_id,
            "descriptive_name": candidate.descriptive_name,
            "comparison_status": candidate.comparison_status,
            "companies_annual_1_period": sum(value["annual_depth"] >= 1 for value in matches),
            "companies_annual_2_periods": sum(value["annual_depth"] >= 2 for value in matches),
            "companies_annual_5_periods": sum(value["annual_depth"] >= 5 for value in matches),
            "companies_annual_6_periods": sum(value["annual_depth"] >= 6 for value in matches),
            "companies_quarterly_comparable_depth_5": sum(value["quarterly_depth"] >= 5 for value in matches),
            "period_observations_available": sum(value["period_observations_available"] for value in matches),
            "unit_scope_conflicts": sum(value["unit_scope_conflicts"] for value in matches),
            "period_identity_conflicts": sum(value["period_identity_conflicts"] for value in matches),
            "vintage_conflicts": sum(value["candidate_vintage_conflicts"] for value in matches),
            "missing_component_distribution": tuple(
                (metric.value, sum(metric.value in value["missing_components"] for value in matches))
                for metric in candidate.parent_metrics
            ),
        })
    type_counts = Counter(company_types.get(instrument_id, UNKNOWN_NON_COMPARABLE) for instrument_id in instruments)
    payload = {
        "policy_version": POLICY_VERSION,
        "report_kind": REPORT_KIND,
        "as_of": as_of,
        "selector_policy": {
            "policy_id": CURRENT_FROZEN_FINANCIAL_FACT_VINTAGE_SELECTION_POLICY.policy_id,
            "version": CURRENT_FROZEN_FINANCIAL_FACT_VINTAGE_SELECTION_POLICY.version,
            "fingerprint": CURRENT_FROZEN_FINANCIAL_FACT_VINTAGE_SELECTION_POLICY.fingerprint,
        },
        "candidate_derivation_status": "UNAPPROVED_NO_VALUES_CALCULATED",
        "correlation_redundancy_status": "NOT_EVALUATED_NO_FORMULA_APPROVED",
        "entity_type_counts": tuple(sorted(type_counts.items())),
        "candidates": tuple(aggregate),
        "instruments": items,
    }
    report_id = "ebitda-ebit-alternatives:" + _fingerprint({
        "policy_version": POLICY_VERSION,
        "as_of": as_of,
        "instruments": instruments,
    }).removeprefix("sha256:")[:32]
    return {
        "report_id": report_id,
        **payload,
        "fingerprint": _fingerprint({"report_id": report_id, **payload}),
    }


def _load_facts(connection: sqlite3.Connection) -> dict[str, tuple[FinancialFact, ...]]:
    rows = connection.execute(
        "SELECT instrument_id, payload_json FROM financial_facts "
        "WHERE source='BSE_OFFICIAL' ORDER BY instrument_id, fact_id"
    ).fetchall()
    values: dict[str, list[FinancialFact]] = defaultdict(list)
    for instrument_id, payload_json in rows:
        values[instrument_id].append(_fact(json.loads(payload_json)))
    return {key: tuple(value) for key, value in sorted(values.items())}


def _load_company_type_receipts(connection: sqlite3.Connection) -> tuple[PitCompanyTypeClassificationReceipt, ...]:
    rows = connection.execute(
        "SELECT payload_json FROM core_api_snapshots "
        "WHERE family='PIT_COMPANY_TYPE_CLASSIFICATION' "
        "AND record_type='PitCompanyTypeClassificationReceipt' ORDER BY snapshot_id"
    ).fetchall()
    values = []
    for (payload_json,) in rows:
        payload = snapshot_json_from(payload_json).payload
        if not isinstance(payload, PitCompanyTypeClassificationReceipt):
            raise ValueError("AUDIT_COMPANY_TYPE_RECEIPT_TYPE_INVALID")
        values.append(payload)
    return tuple(values)


def run_audit(*, database: Path, as_of: datetime) -> dict[str, object]:
    database = database.resolve()
    if not database.is_file():
        raise ValueError("AUDIT_DATABASE_NOT_FOUND")
    connection = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)
    try:
        connection.execute("PRAGMA query_only=ON")
        facts = _load_facts(connection)
        company_types = classify_company_types(_load_company_type_receipts(connection), as_of=as_of)
        return feasibility_report(facts, as_of=as_of, company_types=company_types)
    finally:
        connection.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--as-of", required=True, type=parse_as_of)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    report = run_audit(database=args.database, as_of=args.as_of)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(canonical_json(report) + "\n", encoding="utf-8")
    print(f"{report['report_id']} {report['fingerprint']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
