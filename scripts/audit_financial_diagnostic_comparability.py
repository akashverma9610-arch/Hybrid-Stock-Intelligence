"""One read-only financial-source/metric/approved-nine-rule audit; no acquisition.

Supply explicit current and historical cutoffs. Output is an audit artifact,
never a diagnostic registry, policy selection or persisted diagnostic result.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import closing
from datetime import datetime
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.analysis import fundamentals as legacy
from app.analysis.valuation_trade import valuation, ValuationRules
from app.fundamentals.adapter import FundamentalsEngineAdapter
from app.fundamentals.diagnostic_comparability import (
    assemble_financial_comparability, content_fingerprint, canonical_json, ComparabilityState,
)
from app.fundamentals.diagnostic_input import CanonicalFinancialDiagnosticInput, APPROVED_FINANCIAL_RULE_IDS
from app.fundamentals.models import FinancialMetric, FinancialPeriodType as P, FinancialValueBasis as B, StatementScope
from app.fundamentals.store import _fact, _filter
from app.filings.store import _filing
from app.registry.canonical import DIAGNOSTIC_RULES
from app.storage.core_api_snapshot_repository import snapshot_json_from
from app.universe_analysis.technical_diagnostic_input import assemble_current_descriptive_technical_input

_FUNCTIONS = {16: legacy.five_year_trend, 17: legacy.return_ratios, 18: legacy.cash_flow,
    19: legacy.leverage, 20: legacy.working_capital, 24: legacy.earnings_acceleration,
    25: legacy.latest_quarter, 26: legacy.margins, 29: valuation}
_RULES = legacy.FundamentalRules(.1, -.1, .1, 1.5, 2, .02)
_PERIODS = ((P.ANNUAL, B.FULL_YEAR), (P.QUARTERLY, B.QUARTER_ONLY),
    (P.QUARTERLY, B.YEAR_TO_DATE), (P.POINT_IN_TIME, B.UNKNOWN))


class _Facts:
    def __init__(self, values): self.values = values
    def facts(self, instrument_id, **kwargs):
        return tuple(f for metric in FinancialMetric for f in _filter(
            tuple(f for f in self.values if f.instrument.instrument_id == instrument_id and f.metric is metric), **kwargs))


class _Filings:
    def __init__(self, values): self.values = values
    def list(self, *, instrument_id, as_of, limit):
        return tuple(sorted((f for f in self.values if f.instrument.instrument_id == instrument_id
            and max(f.announced_at, f.received_at) <= as_of), key=lambda f: (f.announced_at, f.filing_id), reverse=True))[:limit]


def _market(connection, instrument_id, as_of):
    # One latest immutable weekly artifact carries certified daily evidence.
    # No universe scan, re-certification, timeframe change or old-window retreat.
    row = connection.execute("SELECT payload_json FROM nse_udiff_weekly_technical_bars WHERE canonical_instrument_id=? ORDER BY week_start DESC, weekly_bar_id DESC LIMIT 1", (instrument_id,)).fetchone()
    if row is None:
        return None, "CERTIFIED_PRICE_UNAVAILABLE"
    weekly = snapshot_json_from(row[0]).payload
    if weekly.daily_read is None or weekly.known_at is None or weekly.known_at > as_of:
        return None, "CERTIFIED_PRICE_NOT_VISIBLE_AT_CUTOFF"
    value = assemble_current_descriptive_technical_input(canonical_instrument_id=instrument_id,
        as_of=as_of, daily_reads=(weekly.daily_read,), weekly_bars=(weekly,))
    return value.daily_snapshot, "CURRENT_DESCRIPTIVE_CERTIFIED_1D;STRICT_HISTORICAL_PIT_NOT_READY"


def _evaluate(rule, snapshot, instrument, market):
    if snapshot is None or rule == 29 and market is None:
        return {"status": "INSUFFICIENT_DATA", "state": "INSUFFICIENT_DATA"}
    try:
        result = _FUNCTIONS[rule](market, snapshot, instrument, ValuationRules(15, 35)) if rule == 29 else _FUNCTIONS[rule](snapshot, instrument, _RULES)
        return {"status": result.status.value, "state": result.state, "details": dict(result.details)}
    except (ValueError, TypeError, KeyError, ZeroDivisionError) as error:
        return {"status": "INVALID_DATA", "state": "INSUFFICIENT_DATA", "safe_error_class": type(error).__name__}


def audit(connection, *, as_of, historical_as_of):
    connection.execute("PRAGMA query_only=ON")
    facts = tuple(_fact(json.loads(r[0])) for r in connection.execute("SELECT payload_json FROM financial_facts ORDER BY fact_id"))
    filings = tuple(_filing(json.loads(r[0])) for r in connection.execute("SELECT payload_json FROM corporate_filings ORDER BY filing_id"))
    companies = defaultdict(list)
    for fact in facts:
        companies[fact.instrument.instrument_id].append(fact)
    source_adapter = FundamentalsEngineAdapter(_Facts(facts), _Filings(filings))
    rows = []
    states = {str(rule): Counter() for rule in APPROVED_FINANCIAL_RULE_IDS}
    old_eligible = Counter()
    new_eligible = Counter()
    selections = Counter()
    selections_reasons = Counter()
    series_counts = defaultdict(Counter)
    scope_counts = defaultdict(Counter)
    for instrument_id, data in sorted(companies.items()):
        own_filings = tuple(f for f in filings if f.instrument.instrument_id == instrument_id)
        current = assemble_financial_comparability(tuple(data), own_filings, canonical_instrument_id=instrument_id, as_of=as_of)
        selections.update({s.value: n for s, n in current.vintage.status_counts})
        selections_reasons.update({s.value: n for s, n in current.vintage.reason_counts})
        for scope in (StatementScope.CONSOLIDATED, StatementScope.STANDALONE):
            exact = assemble_financial_comparability(tuple(f for f in data if f.statement_scope is scope), own_filings,
                canonical_instrument_id=instrument_id, as_of=as_of, preferred_scope=scope)
            for metric in FinancialMetric:
                for period, basis in _PERIODS:
                    s = exact.series(metric, period, basis)
                    key = (metric.value, period.value, basis.value, scope.value)
                    scope_counts[key][s.state.value] += 1
        bridge = CanonicalFinancialDiagnosticInput(current)
        old = source_adapter.build(instrument_id, as_of=as_of)
        market, price_state = _market(connection, instrument_id, as_of)
        rule_rows = {}
        for rule in APPROVED_FINANCIAL_RULE_IDS:
            value = bridge.rule_input(rule, market if rule == 29 else None)
            before = _evaluate(rule, old.snapshot, instrument_id, market)
            after = _evaluate(rule, value.snapshot, instrument_id, market)
            states[str(rule)][value.state.value] += 1
            old_eligible[str(rule)] += before["status"] == "valid"
            new_eligible[str(rule)] += after["status"] == "valid"
            rule_rows[str(rule)] = {"state": value.state.value, "reasons": value.reasons,
                "metrics": value.metric_states, "fact_ids": value.fact_ids, "input_fingerprint": value.fingerprint,
                "before_uncertified_wrapper": before, "after_certified_wrapper": after,
                "prospective_as_of_input_usable": value.snapshot is not None and rule != 29,
                "strict_historical_input_usable": False}
        metric_rows = []
        for metric in FinancialMetric:
            for period, basis in _PERIODS:
                s = current.series(metric, period, basis)
                series_counts[(metric.value, period.value, basis.value)][s.state.value] += 1
                if s.candidate_fact_ids:
                    metric_rows.append({"metric": metric.value, "period": period.value, "basis": basis.value,
                        "state": s.state.value, "reasons": s.reasons,
                        "selected_periods": [o.period_identity.period_end.isoformat() for o in s.observations],
                        "fact_ids": [o.source_fact_id for o in s.observations], "fingerprint": s.fingerprint})
        historical = assemble_financial_comparability(tuple(data), own_filings, canonical_instrument_id=instrument_id, as_of=historical_as_of)
        historical_input = CanonicalFinancialDiagnosticInput(historical)
        for rule in APPROVED_FINANCIAL_RULE_IDS:
            historical_result = historical_input.rule_input(rule)
            rule_rows[str(rule)]["strict_historical_state"] = historical_result.state.value
            rule_rows[str(rule)]["strict_historical_input_usable"] = historical_result.snapshot is not None
        rows.append({"instrument_id": instrument_id, "symbol": data[0].instrument.symbol,
            "facts": len(data), "scope": current.scope.value, "fingerprint": current.fingerprint,
            "known_at_first": min(f.available_at for f in data).isoformat(),
            "known_at_last": max(f.available_at for f in data).isoformat(),
            "vintage_counts": dict((s.value, n) for s, n in current.vintage.status_counts),
            "price_state": price_state, "price_timestamp": market.observations[-1].provenance.market_timestamp.isoformat() if market else None,
            "price_known_at": market.observations[-1].provenance.retrieved_timestamp.isoformat() if market else None,
            "rules": rule_rows, "series": metric_rows,
            "historical_visible_observations": len(historical.observations)})
    metric_counts = []
    for metric in FinancialMetric:
        for period, basis in _PERIODS:
            selected = tuple(f for f in facts if f.metric is metric and f.period_type is period and f.value_basis is basis)
            metric_counts.append({"metric": metric.value, "period": period.value, "basis": basis.value,
                "raw_rows": len(selected), "raw_companies": len({f.instrument.instrument_id for f in selected}),
                "scope_unit_counts": [{"scope": key[0], "currency": key[1], "unit": key[2], "scale": key[3], "rows": n}
                    for key, n in sorted(Counter((f.statement_scope.value, f.currency, f.unit, f.scale.value) for f in selected).items())],
                "preferred_scope_series_states": dict(sorted(series_counts[(metric.value, period.value, basis.value)].items()))})
    rule_counts = []
    for rule in DIAGNOSTIC_RULES:
        if rule.rule_id not in APPROVED_FINANCIAL_RULE_IDS:
            continue
        key = str(rule.rule_id)
        rule_counts.append({"rule_id": rule.rule_id, "name": rule.canonical_name, "evaluator": _FUNCTIONS[rule.rule_id].__name__,
            "security_denominator": len(companies), "states": {s.value: states[key][s.value] for s in ComparabilityState},
            "uncertified_wrapper_eligible_before": old_eligible[key], "certified_wrapper_eligible_after": new_eligible[key],
            "prospective_as_of_usable": sum(r["rules"][key]["prospective_as_of_input_usable"] for r in rows),
            "strict_historical_as_of_usable": sum(r["rules"][key]["strict_historical_input_usable"] for r in rows),
            "conflicted_companies": states[key]["EVIDENCE_CONFLICTED"]})
    protected = {}
    for table in ("financial_facts", "corporate_filings", "portfolio_snapshots", "paper_trades", "trade_plans", "strategy_versions", "diagnostic_results", "canonical_diagnostic_strategy_definitions", "canonical_diagnostic_results"):
        table_rows = [tuple(r) for r in connection.execute('SELECT * FROM "' + table + '"')]
        protected[table] = {"rows": len(table_rows), "fingerprint": content_fingerprint(sorted(table_rows, key=repr))}
    payload = {"contract_id": "canonical-financial-diagnostic-input-comparability", "version": "v1",
        "audit_as_of": as_of.isoformat(), "strict_historical_audit_as_of": historical_as_of.isoformat(),
        "approved_rule_ids": APPROVED_FINANCIAL_RULE_IDS, "financial_facts": len(facts), "corporate_filings": len(filings),
        "financial_source_companies": len(companies), "universe_size_from_accepted_audit": 2553,
        "counts_by_period_basis": [{"period": p, "basis": b, "rows": n} for (p,b), n in sorted(Counter((f.period_type.value, f.value_basis.value) for f in facts).items())],
        "vintage_states": dict(sorted(selections.items())), "vintage_reasons": dict(sorted(selections_reasons.items())),
        "rules": rule_counts, "metrics": metric_counts,
        "exact_scope_series_coverage": [{"metric": m, "period": p, "basis": b, "scope": s, "states": dict(sorted(counts.items()))}
            for (m,p,b,s), counts in sorted(scope_counts.items())],
        "companies": rows, "protected_tables": protected,
        "snapshot_family_counts": dict(connection.execute("SELECT family,COUNT(*) FROM core_api_snapshots GROUP BY family")),
        "contracts": {"scope": "CONSOLIDATED_ELSE_STANDALONE_SINGLE_SCOPE;EXPLICIT_EXACT_SCOPE_AUDITED_SEPARATELY",
            "periods": ["ANNUAL_FULL_YEAR", "QUARTER_ONLY", "QUARTERLY_YTD", "POINT_IN_TIME_UNKNOWN_DURATION", "TTM_NOT_DERIVED"],
            "fiscal": "EXPLICIT_YEAR_QUARTER_EXACT_START_END_CONTIGUITY;NO_NEAREST_DATE",
            "units": "EXACT_INR_CURRENCY_UNIT_SCALE_NORMALIZATION;NO_CONVERSION;PE_REQUIRES_RAW_UNITS",
            "vintage": "EXISTING_FROZEN_APPROVED_SELECTOR;NO_IMPLICIT_LATEST_REVISION",
            "pit": "MAX_FACT_AND_FILING_PUBLISHED_RECEIVED_LE_ASOF;PERIOD_END_LE_ASOF",
            "conflict": "UNRESOLVED_OR_AMBIGUOUS_LINEAGE_FAILS_CLOSED;NO_NUMERIC_RECONCILIATION",
            "source": "EXACT_PRIMARY_FINANCIAL_RESULTS_FILING;DIRECT_REPORTED_FACTS_ONLY"},
        "unresolved": ["SIX_ANNUAL_ENDPOINTS", "DIRECT_EBITDA_EBIT_CAPEX_TOTAL_DEBT", "CAPEX_SIGN_BRIDGE",
            "CANONICAL_COGS_AND_GROSS_MARGIN", "PERIOD_END_SHARE_COUNT_SEMANTICS", "FORWARD_EPS_AND_GROWTH_POLICY",
            "ORGANIC_ONE_OFF_ATTRIBUTION", "SPECIALIZED_FINANCIAL_COMPANY_RULE_POLICIES",
            "EXACT_ASOF_COMPANY_TYPE_INTAKE", "STRICT_HISTORICAL_SOURCE_KNOWABILITY", "UNRESOLVED_VINTAGE_CONFLICTS"],
        "no_production_writes": True, "no_external_acquisition": True, "not_a_second_rule_registry": True}
    return payload | {"fingerprint": content_fingerprint(payload)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--as-of", type=datetime.fromisoformat, required=True)
    parser.add_argument("--historical-as-of", type=datetime.fromisoformat, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output must not overwrite an existing artifact")
    with closing(sqlite3.connect(args.database.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
        connection.execute("BEGIN")
        result = audit(connection, as_of=args.as_of, historical_as_of=args.historical_as_of)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(canonical_json({k: result[k] for k in ("financial_facts", "corporate_filings", "financial_source_companies", "vintage_states", "rules", "fingerprint")}))
