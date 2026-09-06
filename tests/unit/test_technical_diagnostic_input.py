from __future__ import annotations

import ast
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
import inspect

import pytest

from app.diagnostics.evaluators import DeterministicDiagnosticEvaluators
from app.domain.models import AsOfSnapshot, StrategyVersionReference
from app.market_data.nse_udiff_weekly_technical_bar import (
    NseUdiffWeeklyTechnicalState,
    derive_nse_udiff_weekly_technical_bar,
)
from app.universe_analysis.models import NseEquityInstrument
from app.universe_analysis.service import Canonical61DiagnosticRunner, StockDiagnosticInputAssembler
from app.universe_analysis.technical_diagnostic_input import (
    StrictHistoricalPitTechnicalState,
    TechnicalDiagnosticBlocker,
    TechnicalDiagnosticInputError,
    TechnicalDiagnosticReadiness,
    assemble_current_descriptive_technical_input,
    serialize_technical_diagnostic_input,
    technical_diagnostic_readiness,
    technical_diagnostic_rule_requirements,
)
from tests.unit.test_nse_udiff_daily_technical_eligibility import AT, INSTRUMENT
from tests.unit.test_nse_udiff_weekly_technical_bar import daily_read, plan, weekly_request


class StoredFacts:
    def observations_as_of(self, at):
        return ()


def _weekly_values():
    values = []
    for offset in range(6):
        start = date(2024, 7, 8) + timedelta(days=7 * offset)
        session_plan = plan(start)
        read = daily_read(session_plan, price_delta=offset * 10)
        value = derive_nse_udiff_weekly_technical_bar(
            request=weekly_request(session_plan), daily_read=read,
        )
        assert value.state is NseUdiffWeeklyTechnicalState.READY
        values.append(value)
    return tuple(values)


def _input(*, as_of=AT):
    weekly = _weekly_values()
    return assemble_current_descriptive_technical_input(
        canonical_instrument_id=INSTRUMENT.instrument_id,
        as_of=as_of,
        daily_reads=tuple(value.daily_read for value in weekly if value.daily_read is not None),
        weekly_bars=weekly,
    )


def _instrument():
    return NseEquityInstrument(
        INSTRUMENT.instrument_id, INSTRUMENT.symbol, INSTRUMENT.isin,
        None, None, "ACTIVE", None, True, AT, "FIXTURE",
    )


def test_current_descriptive_adapter_builds_distinct_genuine_daily_and_weekly_snapshots():
    value = _input()
    assert value.daily_snapshot is not None and value.weekly_snapshot is not None
    assert len(value.daily_snapshot.observations) == 30
    assert len(value.weekly_snapshot.observations) == 6
    assert value.daily_snapshot.id != value.weekly_snapshot.id
    assert not {item.id for item in value.daily_snapshot.observations} & {item.id for item in value.weekly_snapshot.observations}
    assert value.daily_snapshot.inclusion_policy.endswith("timeframe=1D")
    assert value.weekly_snapshot.inclusion_policy.endswith("timeframe=1W")
    assert value.strict_historical_pit_state is StrictHistoricalPitTechnicalState.NOT_READY
    assert serialize_technical_diagnostic_input(value) == serialize_technical_diagnostic_input(_input())


def test_adapter_rejects_duplicate_or_future_certified_lineage():
    weekly = _weekly_values()
    with pytest.raises(TechnicalDiagnosticInputError, match="DAILY_LINEAGE_DUPLICATE"):
        assemble_current_descriptive_technical_input(
            canonical_instrument_id=INSTRUMENT.instrument_id, as_of=AT,
            daily_reads=(weekly[0].daily_read, weekly[0].daily_read), weekly_bars=weekly,
        )
    with pytest.raises(TechnicalDiagnosticInputError, match="DAILY_READ_INVALID"):
        _input(as_of=AT - timedelta(days=1))
    with pytest.raises(TechnicalDiagnosticInputError, match="WEEKLY_BAR_INVALID"):
        assemble_current_descriptive_technical_input(
            canonical_instrument_id=INSTRUMENT.instrument_id, as_of=AT,
            daily_reads=tuple(value.daily_read for value in weekly if value.daily_read is not None),
            weekly_bars=(weekly[0], weekly[0]),
        )
    with pytest.raises(TechnicalDiagnosticInputError, match="WEEKLY_CONTINUITY_GAP"):
        assemble_current_descriptive_technical_input(
            canonical_instrument_id=INSTRUMENT.instrument_id, as_of=AT,
            daily_reads=(),
            weekly_bars=(weekly[0], weekly[2]),
        )


def test_rule_readiness_is_rule_level_and_keeps_vwap_benchmark_and_event_gaps_explicit():
    value = _input()
    trend = technical_diagnostic_readiness(value, 4)
    mtf = technical_diagnostic_readiness(value, 14)
    assert trend.current_descriptive_operational is TechnicalDiagnosticReadiness.READY
    assert mtf.current_descriptive_operational is TechnicalDiagnosticReadiness.READY
    assert trend.strict_historical_pit_operational is StrictHistoricalPitTechnicalState.NOT_READY
    rs = technical_diagnostic_readiness(value, 6)
    assert rs.current_descriptive_operational is TechnicalDiagnosticReadiness.PARTIAL
    assert rs.blockers == (TechnicalDiagnosticBlocker.BENCHMARK_HISTORY_NOT_READY,)
    # Existing Rule 6 calculates/classifies from stock versus benchmark only.
    # Sector and peers are descriptive outputs, so the readiness contract must
    # not invent gates the evaluator does not actually consume.
    vwap = technical_diagnostic_readiness(value, 35)
    assert vwap.current_descriptive_operational is TechnicalDiagnosticReadiness.NOT_READY
    assert vwap.blockers == (TechnicalDiagnosticBlocker.NAMED_VWAP_SEMANTICS_UNAVAILABLE,)
    event = technical_diagnostic_readiness(value, 57)
    assert TechnicalDiagnosticBlocker.EVENT_EVIDENCE_NOT_READY in event.blockers


def test_rule_inventory_has_current_technical_rules_once_and_no_second_registry():
    rules = technical_diagnostic_rule_requirements()
    assert tuple(item.rule_id for item in rules) == tuple(sorted({item.rule_id for item in rules}))
    assert {4, 5, 6, 11, 12, 13, 14, 35, 36, 39, 46, 57, 58}.issubset({item.rule_id for item in rules})
    assert all(item.evaluator_implemented for item in rules)
    with pytest.raises(TechnicalDiagnosticInputError, match="NOT_TECHNICAL"):
        technical_diagnostic_readiness(_input(), 15)


def test_runner_uses_distinct_genuine_timeframes_and_does_not_relabel_daily_as_weekly():
    technical = _input()
    evidence = StockDiagnosticInputAssembler(StoredFacts()).assemble(_instrument(), AT, technical_input=technical)
    runner = Canonical61DiagnosticRunner()
    daily, weekly, reason = runner._technical_timeframes(evidence, 4)
    assert reason is None and daily is technical.daily_snapshot and weekly is technical.weekly_snapshot
    assert daily is not None and weekly is not None
    assert daily.id != weekly.id
    assert not {item.id for item in daily.observations} & {item.id for item in weekly.observations}
    mtf = DeterministicDiagnosticEvaluators().mtf(
        {"daily": daily, "weekly": weekly}, INSTRUMENT.instrument_id,
        StrategyVersionReference("canonical-universe-analysis", "v1"), AT,
    )
    assert mtf.eligibility.value == "eligible"
    fake_mtf = DeterministicDiagnosticEvaluators().mtf(
        {"daily": daily, "weekly": daily}, INSTRUMENT.instrument_id,
        StrategyVersionReference("canonical-universe-analysis", "v1"), AT,
    )
    assert fake_mtf.record.result == "INSUFFICIENT_DATA"
    assert "distinct canonical timeframe snapshots" in dict(fake_mtf.details)["reason"]
    result = runner.run(evidence)
    rule_14 = next(item for item in result.evaluations if item.canonical_rule_id == 14)
    assert rule_14.eligibility.value == "eligible"
    rule_35 = next(item for item in result.evaluations if item.canonical_rule_id == 35)
    assert rule_35.record.result == "INSUFFICIENT_DATA"
    assert "named canonical VWAP semantics are unavailable" in dict(rule_35.details)["reason"]
    rule_6 = next(item for item in result.evaluations if item.canonical_rule_id == 6)
    assert rule_6.record.result == "INSUFFICIENT_DATA"
    assert "BENCHMARK_HISTORY_NOT_READY" in dict(rule_6.details)["reason"]
    rule_57 = next(item for item in result.evaluations if item.canonical_rule_id == 57)
    assert rule_57.record.result == "INSUFFICIENT_DATA"
    assert "EVENT_EVIDENCE_NOT_READY" in dict(rule_57.details)["reason"]


def test_adapter_is_pure_without_forbidden_runtime_or_execution_dependencies():
    source = inspect.getsource(__import__("app.universe_analysis.technical_diagnostic_input", fromlist=["*"]))
    tree = ast.parse(source)
    imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
    forbidden = ("app.signals", "app.portfolio", "app.orders", "app.broker", "app.api", "app.storage", "app.market_data.upstox")
    assert not any(name.startswith(forbidden) for name in imports)
    assert "datetime.now" not in source and "time.time" not in source
