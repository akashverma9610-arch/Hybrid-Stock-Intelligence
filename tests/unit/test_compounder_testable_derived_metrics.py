from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import ast
import inspect
from pathlib import Path

import pytest

import app.fundamentals.compounder_testable_derived_metrics as module
from app.data_sources.models import FundamentalFactKind
from app.fundamentals.compounder_testable_derived_metrics import *
from app.fundamentals.models import FinancialFact, FinancialMetric, FinancialPeriodType, FinancialValueBasis, NumericScale, StatementScope
from app.market_data.models import Exchange, InstrumentIdentity, InstrumentType

T = datetime(2026, 9, 3, 10, tzinfo=UTC)
I = InstrumentIdentity("NSE:ALPHA", Exchange.NSE, "ALPHA", "ALPHA", "INE000A01001", None, InstrumentType.NSE_EQUITY, "Alpha")


def fact(metric: FinancialMetric, year: int, value: str, *, scope=StatementScope.CONSOLIDATED, received=T, kind=FundamentalFactKind.REPORTED) -> FinancialFact:
    point = metric in {FinancialMetric.TOTAL_EQUITY, FinancialMetric.CASH_AND_EQUIVALENTS}
    return FinancialFact(
        f"{metric.value}:{scope.value}:{year}:{value}", I, metric, Decimal(value), "INR", "INR", NumericScale.CRORES,
        FinancialPeriodType.POINT_IN_TIME if point else FinancialPeriodType.ANNUAL,
        FinancialValueBasis.UNKNOWN if point else FinancialValueBasis.FULL_YEAR,
        None if point else datetime(year - 1, 4, 1, tzinfo=UTC), datetime(year, 3, 31, tzinfo=UTC), year, None,
        scope, kind, "BSE_OFFICIAL", f"filing:{metric.value}:{year}", "source", datetime(year, 5, 1, tzinfo=UTC), received,
        "bse-official-local-xbrl-v1",
    )


def evaluate(*, revenue=("100", "120", "144", "172.8", "207.36"), pat=("10", "12", "14.4", "17.28", "20.736"), cfo=("8", "10", "12", "14", "16"), equity=("50", "60", "70", "80", "90"), cash=("5", "6", "7", "8", "9"), scope=StatementScope.CONSOLIDATED, received=T):
    values = []
    for metric, sequence in ((FinancialMetric.REVENUE, revenue), (FinancialMetric.PAT, pat), (FinancialMetric.CFO, cfo), (FinancialMetric.TOTAL_EQUITY, equity), (FinancialMetric.CASH_AND_EQUIVALENTS, cash)):
        values.extend(fact(metric, 2022 + index, value, scope=scope, received=received) for index, value in enumerate(sequence))
    return evaluate_compounder_testable_derived_metrics(values, canonical_instrument_id=I.instrument_id, statement_scope=scope, as_of=T), values


def records(value, metric): return tuple(item for item in value.receipts if item.metric is metric)


def test_revenue_yoy_cagr_and_elapsed_interval_count_are_deterministic():
    result, _ = evaluate()
    yoy = records(result, CompounderDerivedMetric.REVENUE_YOY)
    assert len(yoy) == 4 and all(item.status is CompounderDerivedStatus.AVAILABLE for item in yoy)
    assert yoy[0].values[0][1] == Decimal("0.2")
    cagr = records(result, CompounderDerivedMetric.REVENUE_CAGR_5Y)[0]
    assert cagr.status is CompounderDerivedStatus.AVAILABLE and dict(cagr.values)["elapsed_intervals"] == Decimal("4")
    assert serialize_compounder_derived_research(result) == serialize_compounder_derived_research(result)


@pytest.mark.parametrize(("metric", "sequence", "reason"), ((FinancialMetric.REVENUE, ("0", "20", "30", "40", "50"), CompounderDerivedReason.ZERO_OR_NEAR_ZERO_DENOMINATOR), (FinancialMetric.REVENUE, ("-1", "20", "30", "40", "50"), CompounderDerivedReason.POSITIVE_GROWTH_BASE_REQUIRED), (FinancialMetric.PAT, ("-1", "2", "3", "4", "5"), CompounderDerivedReason.LOSS_TO_PROFIT), (FinancialMetric.PAT, ("2", "-1", "3", "4", "5"), CompounderDerivedReason.PROFIT_TO_LOSS), (FinancialMetric.PAT, ("-2", "-1", "3", "4", "5"), CompounderDerivedReason.LOSS_TO_LOSS)))
def test_invalid_growth_bases_and_pat_sign_transitions_never_emit_percentage(metric, sequence, reason):
    kwargs = {"revenue": sequence} if metric is FinancialMetric.REVENUE else {"pat": sequence}
    result, _ = evaluate(**kwargs)
    target = CompounderDerivedMetric.REVENUE_YOY if metric is FinancialMetric.REVENUE else CompounderDerivedMetric.PAT_YOY
    first = records(result, target)[0]
    assert first.status is CompounderDerivedStatus.NON_COMPARABLE and first.reasons == (reason,) and not first.values


def test_persistence_is_descriptive_not_qualification():
    result, _ = evaluate(revenue=("100", "120", "100", "110", "99"))
    receipt = records(result, CompounderDerivedMetric.REVENUE_PERSISTENCE)[0]
    assert receipt.status is CompounderDerivedStatus.AVAILABLE
    assert dict(receipt.values) == {"comparable_intervals": Decimal("4"), "negative_intervals": Decimal("2"), "non_comparable_intervals": Decimal("0"), "positive_intervals": Decimal("2")}
    assert "QUALIFIED" not in serialize_compounder_derived_research(result)


def test_roe_closing_average_summary_and_missing_opening_are_explicit():
    result, values = evaluate()
    closing = records(result, CompounderDerivedMetric.ROE_CLOSING_EQUITY)
    average = records(result, CompounderDerivedMetric.ROE_AVERAGE_EQUITY)
    assert closing[0].status is CompounderDerivedStatus.AVAILABLE and dict(closing[0].values)["2022"] == Decimal("0.2")
    assert average[0].status is CompounderDerivedStatus.DATA_INSUFFICIENT and average[0].reasons == (CompounderDerivedReason.OPENING_EQUITY_REQUIRED,)
    summary = records(result, CompounderDerivedMetric.ROE_SUMMARY_3)[0]
    assert summary.status is CompounderDerivedStatus.AVAILABLE and dict(summary.values)["valid_period_count"] == Decimal("3")
    no_equity, _ = evaluate(equity=("0", "60", "70", "80", "90"))
    assert records(no_equity, CompounderDerivedMetric.ROE_CLOSING_EQUITY)[0].reasons == (CompounderDerivedReason.POSITIVE_EQUITY_REQUIRED,)


def test_cash_conversion_preserves_negative_cfo_and_rejects_nonpositive_cumulative_pat():
    result, _ = evaluate(cfo=("-8", "10", "12", "14", "16"))
    annual = records(result, CompounderDerivedMetric.CFO_PAT_ANNUAL)[0]
    assert annual.status is CompounderDerivedStatus.AVAILABLE and dict(annual.values)["2022"] < 0
    cumulative = records(result, CompounderDerivedMetric.CFO_PAT_CUMULATIVE_3)[0]
    assert cumulative.status is CompounderDerivedStatus.AVAILABLE
    invalid, _ = evaluate(pat=("-10", "-10", "-10", "-10", "-10"))
    assert records(invalid, CompounderDerivedMetric.CFO_PAT_CUMULATIVE_3)[0].reasons == (CompounderDerivedReason.POSITIVE_CUMULATIVE_PAT_REQUIRED,)


def test_cash_trajectory_is_only_an_observation():
    result, _ = evaluate(cash=("5", "4", "4", "6", "7"))
    receipt = records(result, CompounderDerivedMetric.CASH_TRAJECTORY)[0]
    assert receipt.status is CompounderDerivedStatus.AVAILABLE and receipt.observation is CashTrajectoryObservation.MIXED
    assert dict(receipt.values)["cash:2022"] == Decimal("5") and dict(receipt.values)["change:2023"] == Decimal("-1")


def test_scope_pit_conflict_tamper_and_immutability_fail_closed():
    result, values = evaluate()
    shuffled = evaluate_compounder_testable_derived_metrics(tuple(reversed(values)), canonical_instrument_id=I.instrument_id, statement_scope=StatementScope.CONSOLIDATED, as_of=T)
    assert shuffled.fingerprint == result.fingerprint
    standalone = [replace(item, statement_scope=StatementScope.STANDALONE, fact_id=item.fact_id + ":s") for item in values]
    isolated = evaluate_compounder_testable_derived_metrics(tuple(values) + tuple(standalone), canonical_instrument_id=I.instrument_id, statement_scope=StatementScope.CONSOLIDATED, as_of=T)
    assert isolated.fingerprint == result.fingerprint
    future = [replace(item, received_at=T + timedelta(days=1), fact_id=item.fact_id + ":future") for item in values]
    future_only = evaluate_compounder_testable_derived_metrics(future, canonical_instrument_id=I.instrument_id, statement_scope=StatementScope.CONSOLIDATED, as_of=T)
    assert all(item.status is not CompounderDerivedStatus.AVAILABLE for item in future_only.receipts)
    conflict = replace(values[0], fact_id="conflict-revenue", value=Decimal("999"))
    conflicted = evaluate_compounder_testable_derived_metrics(tuple(values) + (conflict,), canonical_instrument_id=I.instrument_id, statement_scope=StatementScope.CONSOLIDATED, as_of=T)
    assert all(item.status is CompounderDerivedStatus.EVIDENCE_CONFLICTED for item in records(conflicted, CompounderDerivedMetric.REVENUE_YOY))
    roe = records(result, CompounderDerivedMetric.ROE_CLOSING_EQUITY)[0]
    assert len(roe.input_fact_ids) == len(roe.input_fact_fingerprints) == 2 and len(roe.source_coverage_fingerprints) == 2
    with pytest.raises(FrozenInstanceError): result.receipts[0].status = CompounderDerivedStatus.AVAILABLE
    object.__setattr__(result.receipts[0], "fingerprint", "sha256:tampered")
    with pytest.raises(ValueError, match="FINGERPRINT"): serialize_compounder_derived_research(result)


def test_no_qualification_threshold_or_forbidden_dependency_surface():
    source = Path(inspect.getfile(module)).read_text(encoding="utf-8")
    imports = {item.name for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Import) for item in node.names} | {node.module or "" for node in ast.walk(ast.parse(source)) if isinstance(node, ast.ImportFrom)}
    assert not any(value.startswith(prefix) for value in imports for prefix in ("app.portfolio", "app.storage", "app.api", "app.broker", "app.orders", "app.signals", "app.intelligence"))
    assert "datetime.now" not in source and not any(word in source for word in ("SHADOW_CANDIDATE", "SHADOW_NOT_QUALIFIED", "DecisionScore", "SixGates"))
    forbidden = {"price", "entry", "stop", "target", "quantity", "allocation", "portfolio", "order", "broker", "score", "forecast"}
    assert not (set(CompounderDerivedResearchReceipt.__dataclass_fields__) & forbidden)
