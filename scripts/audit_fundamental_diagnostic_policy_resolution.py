"""Read-only readiness audit for Rules 16, 17, 19, 25, 26, and 29.

The tool measures only exact, PIT-visible reported-accounting parent coverage.
It never calculates a ratio, derives an earnings metric, changes a rule, or
writes to SQLite.  Issuer-reported ratios are deliberately counted as absent
until a distinct, approved ratio-evidence contract exists.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
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
    FinancialValueBasis,
)
from app.fundamentals.store import _fact
from scripts.audit_ebitda_ebit_diagnostic_alternatives import (
    UNKNOWN_NON_COMPARABLE,
    _load_company_type_receipts,
    classify_company_types,
)


POLICY_VERSION = "fundamental-diagnostic-policy-unresolved-research-v1"
ENTITY_BUCKETS = ("NON_FINANCIAL", "BANK", "NBFC", "INSURER", UNKNOWN_NON_COMPARABLE)
RATIO_CONTRACT_STATE = "NO_CANONICAL_ISSUER_REPORTED_RATIO_CONTRACT"


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=_json_default)


def _json_default(value: object) -> str:
    if isinstance(value, datetime):
        return _utc(value).isoformat()
    raise TypeError(f"Unsupported audit value: {type(value).__name__}")


def _fingerprint(value: object) -> str:
    return "sha256:" + sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("POLICY_AUDIT_TIMEZONE_REQUIRED")
    return value.astimezone(UTC)


def parse_as_of(value: str) -> datetime:
    return _utc(datetime.fromisoformat(value.replace("Z", "+00:00")))


def _selected_reported_facts(
    facts: Iterable[FinancialFact], *, instrument_id: str, as_of: datetime,
) -> tuple[FinancialFact, ...]:
    values = tuple(sorted(facts, key=lambda item: item.fact_id))
    selection = select_financial_fact_vintages(
        values,
        canonical_instrument_id=instrument_id,
        as_of=as_of,
        policy=CURRENT_FROZEN_FINANCIAL_FACT_VINTAGE_SELECTION_POLICY,
    )
    by_id = {fact.fact_id: fact for fact in values}
    return tuple(
        by_id[item.selected_fact_id]
        for item in selection.selections
        if item.status is FinancialFactVintageSelectionStatus.SELECTED
        and item.selected_fact_id is not None
        and by_id[item.selected_fact_id].fact_kind.value == "REPORTED"
    )


def _flow_coordinate(fact: FinancialFact) -> tuple[object, ...]:
    return (
        fact.statement_scope.value,
        fact.currency,
        fact.unit,
        fact.scale.value,
        fact.normalization_version,
        fact.value_basis.value,
        _utc(fact.period_start).isoformat() if fact.period_start is not None else None,
        _utc(fact.period_end).isoformat(),
        fact.fiscal_year,
        fact.fiscal_quarter,
    )


def _flow_series_key(coordinate: tuple[object, ...]) -> tuple[object, ...]:
    return coordinate[:6]


def _flow_depth(
    facts: Iterable[FinancialFact], metrics: tuple[FinancialMetric, ...], *, period_type: FinancialPeriodType,
    basis: FinancialValueBasis,
) -> int:
    groups: dict[tuple[object, ...], set[FinancialMetric]] = defaultdict(set)
    for fact in facts:
        if fact.metric in metrics and fact.period_type is period_type and fact.value_basis is basis:
            groups[_flow_coordinate(fact)].add(fact.metric)
    series: dict[tuple[object, ...], set[str]] = defaultdict(set)
    for coordinate, observed in groups.items():
        if all(metric in observed for metric in metrics):
            series[_flow_series_key(coordinate)].add(str(coordinate[7]))
    return max((len(periods) for periods in series.values()), default=0)


def _balance_flow_aligned_depth(
    facts: Iterable[FinancialFact], *, flow_metrics: tuple[FinancialMetric, ...],
    balance_metrics: tuple[FinancialMetric, ...],
) -> int:
    """Count annual ends with all exact flow and point-balance parents, no values."""
    flows: dict[tuple[object, ...], set[FinancialMetric]] = defaultdict(set)
    balances: dict[tuple[object, ...], set[FinancialMetric]] = defaultdict(set)
    for fact in facts:
        common = (
            fact.statement_scope.value, fact.currency, fact.unit, fact.scale.value,
            fact.normalization_version, _utc(fact.period_end).isoformat(), fact.fiscal_year,
        )
        if fact.metric in flow_metrics and fact.period_type is FinancialPeriodType.ANNUAL and fact.value_basis is FinancialValueBasis.FULL_YEAR:
            flows[common].add(fact.metric)
        if fact.metric in balance_metrics and fact.period_type is FinancialPeriodType.POINT_IN_TIME:
            balances[common].add(fact.metric)
    series: dict[tuple[object, ...], set[str]] = defaultdict(set)
    candidate_keys = set(flows) if flow_metrics else set(balances)
    for key in candidate_keys:
        if all(metric in flows.get(key, set()) for metric in flow_metrics) and all(metric in balances.get(key, set()) for metric in balance_metrics):
            series[key[:5]].add(str(key[5]))
    return max((len(ends) for ends in series.values()), default=0)


def _rule_flags(facts: Iterable[FinancialFact]) -> dict[str, bool]:
    values = tuple(facts)
    annual = lambda metrics: _flow_depth(
        values, metrics, period_type=FinancialPeriodType.ANNUAL, basis=FinancialValueBasis.FULL_YEAR,
    )
    quarterly = lambda metrics: _flow_depth(
        values, metrics, period_type=FinancialPeriodType.QUARTERLY, basis=FinancialValueBasis.QUARTER_ONLY,
    )
    annual_core_16 = annual((FinancialMetric.REVENUE, FinancialMetric.PAT, FinancialMetric.EPS_BASIC))
    annual_strict_16 = annual((FinancialMetric.REVENUE, FinancialMetric.EBITDA, FinancialMetric.PAT, FinancialMetric.EPS_BASIC))
    roe = _balance_flow_aligned_depth(
        values, flow_metrics=(FinancialMetric.PAT,), balance_metrics=(FinancialMetric.TOTAL_EQUITY,),
    )
    roce = _balance_flow_aligned_depth(
        values,
        flow_metrics=(FinancialMetric.EBIT,),
        balance_metrics=(FinancialMetric.TOTAL_EQUITY, FinancialMetric.TOTAL_DEBT, FinancialMetric.CASH_AND_EQUIVALENTS),
    )
    debt_equity = _balance_flow_aligned_depth(
        values, flow_metrics=(), balance_metrics=(FinancialMetric.TOTAL_DEBT, FinancialMetric.TOTAL_EQUITY),
    )
    net_debt = _balance_flow_aligned_depth(
        values, flow_metrics=(), balance_metrics=(FinancialMetric.TOTAL_DEBT, FinancialMetric.CASH_AND_EQUIVALENTS),
    )
    interest_coverage = annual((FinancialMetric.EBIT, FinancialMetric.FINANCE_COST))
    return {
        "rule_16_current_strict": annual_strict_16 >= 6,
        "rule_16_revenue_pat_eps_core": annual_core_16 >= 6,
        "rule_17_roe_parent_alignment": roe >= 2,
        "rule_17_roce_parent_alignment": roce >= 1,
        "rule_19_debt_equity_parent_alignment": debt_equity >= 1,
        "rule_19_net_debt_parent_alignment": net_debt >= 1,
        "rule_19_interest_coverage_parent_alignment": interest_coverage >= 1,
        "rule_25_revenue_component": quarterly((FinancialMetric.REVENUE,)) >= 5,
        "rule_25_pat_component": quarterly((FinancialMetric.PAT,)) >= 5,
        "rule_25_eps_component": quarterly((FinancialMetric.EPS_BASIC,)) >= 5,
        "rule_25_ebitda_component": quarterly((FinancialMetric.EBITDA,)) >= 5,
        "rule_26_ebitda_margin_parent_alignment": quarterly((FinancialMetric.REVENUE, FinancialMetric.EBITDA)) >= 5,
        "rule_26_gross_margin_parent_alignment": False,
        "rule_29_financial_only_eps_annual": annual((FinancialMetric.EPS_BASIC,)) >= 1,
        "rule_29_forward_pe": False,
        "rule_29_peg": False,
        "rule_29_ev_ebitda": False,
        "rule_29_pb": False,
        "issuer_reported_ratio_evidence": False,
    }


def policy_readiness_report(
    facts_by_instrument: Mapping[str, Iterable[FinancialFact]], *, as_of: datetime,
    company_types: Mapping[str, str],
) -> dict[str, object]:
    """Build deterministic coverage counts; no output contains financial values."""
    as_of = _utc(as_of)
    instruments = tuple(sorted(facts_by_instrument))
    per_instrument = []
    for instrument_id in instruments:
        selected = _selected_reported_facts(
            facts_by_instrument[instrument_id], instrument_id=instrument_id, as_of=as_of,
        )
        per_instrument.append({
            "instrument_id": instrument_id,
            "entity_type": company_types.get(instrument_id, UNKNOWN_NON_COMPARABLE),
            "flags": tuple(sorted(_rule_flags(selected).items())),
            "selected_fact_ids": tuple(sorted(fact.fact_id for fact in selected)),
        })
    buckets = []
    for entity_type in ENTITY_BUCKETS:
        values = [item for item in per_instrument if item["entity_type"] == entity_type]
        counters = Counter(
            flag for item in values for flag, present in item["flags"] if present
        )
        buckets.append({
            "entity_type": entity_type,
            "denominator": len(values),
            "potential_ready_counts": tuple(sorted(counters.items())),
        })
    payload = {
        "policy_version": POLICY_VERSION,
        "as_of": as_of,
        "selector_policy": (
            CURRENT_FROZEN_FINANCIAL_FACT_VINTAGE_SELECTION_POLICY.policy_id,
            CURRENT_FROZEN_FINANCIAL_FACT_VINTAGE_SELECTION_POLICY.version,
            CURRENT_FROZEN_FINANCIAL_FACT_VINTAGE_SELECTION_POLICY.fingerprint,
        ),
        "issuer_reported_ratio_contract_state": RATIO_CONTRACT_STATE,
        "ratio_values_calculated": False,
        "derived_metrics_calculated": False,
        "buckets": tuple(buckets),
        "instruments": tuple(per_instrument),
    }
    report_id = "fundamental-diagnostic-policy:" + _fingerprint({
        "policy_version": POLICY_VERSION, "as_of": as_of, "instruments": instruments,
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
    return {instrument_id: tuple(facts) for instrument_id, facts in sorted(values.items())}


def run_audit(*, database: Path, as_of: datetime) -> dict[str, object]:
    database = database.resolve()
    if not database.is_file():
        raise ValueError("POLICY_AUDIT_DATABASE_NOT_FOUND")
    connection = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)
    try:
        connection.execute("PRAGMA query_only=ON")
        facts = _load_facts(connection)
        types = classify_company_types(_load_company_type_receipts(connection), as_of=as_of)
        return policy_readiness_report(facts, as_of=as_of, company_types=types)
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
