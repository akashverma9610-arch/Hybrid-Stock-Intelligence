from dataclasses import replace
from datetime import timedelta

import pytest

from app.config.freshness import FreshnessPolicyConfig
from app.diagnostics.evaluators import DeterministicDiagnosticEvaluators
from app.domain.models import AsOfSnapshot, ObservationKind
from app.services.foundation_service import FoundationService
from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository
from app.validation.freshness import FreshnessEngine
from app.validation.observation_validator import ObservationValidator
from tests.fixtures.analytical_observations import ANALYSIS_TIME, STRATEGY_REFERENCE, bars


def _history():
    return (
        bars("sector", [10, 11, 12, 13, 14, 15, 16, 17]),
        bars("benchmark", [10, 10.2, 10.4, 10.6, 10.8, 11, 11.2, 11.4]),
        bars("stock", [10, 11, 12, 11, 13, 14, 15, 16], volumes=[100, 100, 90, 110, 120, 130, 140, 400]),
    )


def _future(instrument):
    return replace(bars(instrument, [1], start=ANALYSIS_TIME + timedelta(days=1), volumes=[10000])[0], id=f"{instrument}-future-collapse")


def _pair(tmp_path):
    repo = SQLiteStrategyGovernanceRepository(tmp_path / "new-rules.db")
    service = FoundationService(repo, ObservationValidator(FreshnessEngine(FreshnessPolicyConfig({ObservationKind.PRICE_BAR: timedelta(days=90)}, timedelta(days=90)))))
    for group in _history():
        for item in group: service.ingest(item, evaluated_timestamp=ANALYSIS_TIME + timedelta(days=10))
    before = service.build_as_of_snapshot(as_of_timestamp=ANALYSIS_TIME)
    future = tuple(_future(name) for name in ("sector", "benchmark", "stock"))
    for item in future: service.ingest(item, evaluated_timestamp=ANALYSIS_TIME + timedelta(days=10))
    return repo, before, service.build_as_of_snapshot(as_of_timestamp=ANALYSIS_TIME), tuple(item.id for item in future)


def _evaluate(rule, snapshot):
    engine = DeterministicDiagnosticEvaluators()
    common = (snapshot, "stock", STRATEGY_REFERENCE)
    return {
        2: lambda: engine.sector_health(snapshot, "sector", "benchmark", STRATEGY_REFERENCE, 3, .05, -.05, ANALYSIS_TIME),
        3: lambda: engine.sector_rotation(snapshot, "sector", "benchmark", STRATEGY_REFERENCE, 3, .05, -.05, ANALYSIS_TIME),
        11: lambda: engine.volume(*common, 3, 1.5, .7, ANALYSIS_TIME),
        12: lambda: engine.ichimoku(*common, 2, 3, 4, 1, ANALYSIS_TIME),
        13: lambda: engine.chikou(*common, 2, 3, 4, 1, ANALYSIS_TIME),
        14: lambda: engine.mtf({"daily": snapshot, "weekly": snapshot}, "stock", STRATEGY_REFERENCE, ANALYSIS_TIME),
        35: lambda: engine.vwap(*common, ANALYSIS_TIME),
        36: lambda: engine.obv(*common, 3, ANALYSIS_TIME),
    }[rule]()


@pytest.mark.parametrize("rule", (2, 3, 11, 12, 13, 14, 35, 36))
def test_each_new_rule_excludes_future_observations_through_its_normal_evaluator_path(tmp_path, rule):
    repo, before, after, future_ids = _pair(tmp_path)
    first, second = _evaluate(rule, before), _evaluate(rule, after)
    assert first == second
    assert first.record.input_observation_ids == second.record.input_observation_ids
    assert first.record.evidence_ids == second.record.evidence_ids
    assert first.record.confidence == second.record.confidence
    rendered = repr(first)
    assert all(item not in rendered for item in future_ids)
    repo.close()


@pytest.mark.parametrize("rule", (2, 3, 11, 12, 13, 14, 35, 36))
def test_each_new_rule_fails_closed_when_a_raw_future_bar_bypasses_snapshot_construction(rule):
    historical = tuple(item for group in _history() for item in group)
    affected_instrument = "sector" if rule in (2, 3) else "stock"
    contaminated = AsOfSnapshot("manual", ANALYSIS_TIME, ANALYSIS_TIME, "manual", historical + (_future(affected_instrument),))
    result = _evaluate(rule, contaminated)
    assert result.eligibility.value == "ineligible_invalid_data"
    assert f"{affected_instrument}-future-collapse" not in result.record.input_observation_ids
