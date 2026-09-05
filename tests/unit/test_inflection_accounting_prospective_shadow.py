from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
import ast
import inspect

import pytest

from tests.unit import test_inflection_testable_derived_metrics_and_event_alignment as source
from app.fundamentals.models import FinancialMetric
from app.intelligence.inflection_accounting_prospective_shadow import (
    AccountingOutcomeMaturity, ExactIntradayEventTimeState, InflectionAccountingObservationState,
    InflectionAccountingProspectiveShadowError, InflectionAccountingProspectiveStore,
    InflectionAccountingReadinessState, InflectionProspectiveWriteOutcome,
    PROSPECTIVE_LEDGER_ACTIVATED_AT,
    assess_inflection_accounting_prospective_readiness, frozen_inflection_accounting_candidate_grid_plan,
    initial_inflection_accounting_outcome, run_inflection_accounting_prospective_batch,
    serialize_inflection_accounting_observation,
)
from app.intelligence.inflection_testable_derived_metrics_and_event_alignment import (
    InflectionDerivedMetricsState, evaluate_inflection_testable_derived_metrics_and_event_alignment,
)
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository


AS_OF = datetime(2026, 9, 5, tzinfo=UTC)


def _evaluation(*, facts=None):
    return evaluate_inflection_testable_derived_metrics_and_event_alignment(
        facts=source._facts() if facts is None else facts, filings=(source._filing(),),
        company_type_receipt=source._company_type_receipt(), statement_scope=source.StatementScope.CONSOLIDATED,
        as_of=AS_OF, calendar=None,
    )


def _ready(*, facts=None):
    evaluation = _evaluation(facts=facts)
    return assess_inflection_accounting_prospective_readiness(
        evaluation=evaluation, company_type_receipt=source._company_type_receipt(),
        candidate_grid=frozen_inflection_accounting_candidate_grid_plan(),
    )


def test_nonfinancial_pit_receipt_freezes_both_metric_accounting_observation_deterministically():
    first, second = _ready(), _ready()
    assert first.state is InflectionAccountingReadinessState.OBSERVATION_READY
    assert first.observation is not None and second.observation is not None
    assert first.observation.fingerprint == second.observation.fingerprint
    assert first.observation.observation_state is InflectionAccountingObservationState.ACCOUNTING_INFLECTION_OBSERVATION_AVAILABLE
    assert first.observation.revenue.state is first.observation.pat.state is InflectionDerivedMetricsState.ACCELERATION_OBSERVED
    assert first.observation.exact_intraday_event_time is ExactIntradayEventTimeState.EXACT_INTRADAY_EVENT_TIME_UNAVAILABLE
    assert serialize_inflection_accounting_observation(first.observation) == serialize_inflection_accounting_observation(second.observation)


def test_metric_specific_readiness_never_requires_both_metrics():
    facts = tuple(item for item in source._facts() if not (item.metric is FinancialMetric.REVENUE and item.fiscal_year == 2024))
    result = _ready(facts=facts)
    assert result.state is InflectionAccountingReadinessState.OBSERVATION_READY
    assert result.observation is not None
    assert result.observation.revenue.state is InflectionDerivedMetricsState.YOY_OBSERVED
    assert result.observation.pat.state is InflectionDerivedMetricsState.ACCELERATION_OBSERVED


def test_special_loss_and_base_transition_is_retained_not_represented_as_percentage_acceleration():
    result = _ready(facts=source._facts(pat=("8", "-10", "12", "14")))
    assert result.state is InflectionAccountingReadinessState.OBSERVATION_READY
    assert result.observation is not None
    assert result.observation.observation_state is InflectionAccountingObservationState.ACCOUNTING_INFLECTION_OBSERVATION_AVAILABLE
    assert result.observation.pat.acceleration is None
    assert result.observation.pat.state is InflectionDerivedMetricsState.NON_COMPARABLE


def test_future_fact_is_excluded_by_existing_pit_selector_before_prospective_freeze():
    future = replace(source._fact(FinancialMetric.REVENUE, 2026, 1, "999", filing_id="filing:2026:Q1"), fact_id="future-current", published_at=AS_OF + timedelta(seconds=1), received_at=AS_OF + timedelta(days=1))
    result = _ready(facts=source._facts() + (future,))
    assert result.observation is not None
    assert "future-current" not in {item.fact_id for item in result.observation.revenue.input_facts}


def test_conflict_and_incomplete_metrics_fail_closed_without_observation():
    conflict = replace(source._fact(FinancialMetric.REVENUE, 2026, 1, "999", filing_id="filing:2026:Q1"), fact_id="revenue-conflict")
    assert _ready(facts=source._facts() + (conflict,)).state is InflectionAccountingReadinessState.EVIDENCE_CONFLICTED
    sparse = tuple(item for item in source._facts() if item.fiscal_year != 2024)
    assert _ready(facts=sparse).state is InflectionAccountingReadinessState.DATA_INSUFFICIENT


def test_observation_and_initial_outcome_are_immutable_and_initially_immature():
    observation = _ready().observation
    assert observation is not None
    outcome = initial_inflection_accounting_outcome(observation)
    assert outcome.maturity is AccountingOutcomeMaturity.IMMATURE
    assert outcome.future_metric_receipt_fingerprints == ()
    with pytest.raises(FrozenInstanceError): observation.as_of = AS_OF  # type: ignore[misc]
    with pytest.raises(InflectionAccountingProspectiveShadowError, match="IMMATURE"):
        replace(outcome, future_metric_receipt_fingerprints=("sha256:" + "0" * 64,))


def test_store_is_insert_only_and_replay_does_not_duplicate_observation_or_outcome(tmp_path):
    receipt = source._company_type_receipt(); facts = source._facts(); filings = (source._filing(),)
    store = InflectionAccountingProspectiveStore(SQLiteCoreApiSnapshotRepository(tmp_path / "inflection.sqlite"))
    first, _ = run_inflection_accounting_prospective_batch(as_of=AS_OF, company_type_receipts=(receipt,), facts_for_instrument=lambda _: facts, filings_for_instrument=lambda _: filings, store=store)
    second, _ = run_inflection_accounting_prospective_batch(as_of=AS_OF, company_type_receipts=(receipt,), facts_for_instrument=lambda _: facts, filings_for_instrument=lambda _: filings, store=store)
    assert first.observations_inserted == 1 and first.outcomes_inserted == 1
    assert second.observations_already_present == 1 and second.outcomes_already_present == 1
    assert len(store.observations()) == 1
    assert len(store.outcomes()) == 1 and store.outcomes()[0].maturity is AccountingOutcomeMaturity.IMMATURE


def test_batch_refuses_historical_backdating_even_when_historical_facts_are_available(tmp_path):
    store = InflectionAccountingProspectiveStore(SQLiteCoreApiSnapshotRepository(tmp_path / "inflection.sqlite"))
    with pytest.raises(InflectionAccountingProspectiveShadowError, match="HISTORICAL_BACKDATING"):
        run_inflection_accounting_prospective_batch(as_of=PROSPECTIVE_LEDGER_ACTIVATED_AT - timedelta(seconds=1),
            company_type_receipts=(source._company_type_receipt(),), facts_for_instrument=lambda _: source._facts(),
            filings_for_instrument=lambda _: (source._filing(),), store=store)


def test_candidate_grid_is_frozen_lineage_not_executed_and_no_forbidden_surface_or_dependency_exists():
    observation = _ready().observation
    assert observation is not None
    plan = frozen_inflection_accounting_candidate_grid_plan()
    assert plan.persistence_windows == ("ONE_QUARTER", "TWO_CONSECUTIVE_QUARTERS", "THREE_CONSECUTIVE_QUARTERS")
    fields = set(observation.__dataclass_fields__)
    assert not fields & {"candidate", "qualification", "score", "rank", "entry", "stop", "target", "price", "quantity", "allocation"}
    import app.intelligence.inflection_accounting_prospective_shadow as module
    text = Path(inspect.getfile(module)).read_text(encoding="utf-8")
    imports = {item.name for node in ast.walk(ast.parse(text)) if isinstance(node, ast.Import) for item in node.names} | {node.module or "" for node in ast.walk(ast.parse(text)) if isinstance(node, ast.ImportFrom)}
    assert not any(item.startswith(prefix) for item in imports for prefix in ("app.portfolio", "app.broker", "app.orders", "app.api", "app.signals", "app.market_data"))
    assert "datetime.now" not in text and "SHADOW_CANDIDATE" not in text


def test_tampered_nested_lineage_or_posture_is_rejected():
    observation = _ready().observation
    assert observation is not None
    with pytest.raises(InflectionAccountingProspectiveShadowError, match="GRID_PLAN_LINEAGE|FINGERPRINT"):
        replace(observation, candidate_grid_fingerprint="sha256:" + "0" * 64)
    with pytest.raises(InflectionAccountingProspectiveShadowError, match="OBSERVATION_INVALID"):
        replace(observation, actionability="BUY")
