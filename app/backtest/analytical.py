"""Historical orchestration adapter for the existing diagnostic, scoring, and gate engines."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal

from app.analysis.models import MarketRegimeRules, RelativeStrengthRules, TrendRules
from app.backtest.engine import ExchangeCalendarProtocol, ReplayStepContext, ReplayStepHandlerResult
from app.diagnostics.evaluators import DeterministicDiagnosticEvaluators, WeinsteinRules
from app.diagnostics.models import EvaluatedDiagnostic, EvaluationEligibility
from app.domain.models import AsOfSnapshot, FinancialObservation, MarketObservation, StrategyVersionReference
from app.gates.engine import ActionContext, ExecutionGateConfig, ExecutionGateEngine, GateInput, SurveillanceObservation
from app.historical.guard import BacktestLookaheadGuard, manifest_fingerprint
from app.historical.models import HistoricalFact
from app.registry.canonical import DIAGNOSTIC_REGISTRY_VERSION, DIAGNOSTIC_RULES
from app.scoring.engine import build_scorecard
from app.storage.sqlite_repository import deterministic_snapshot_id

from .models import (
    BacktestEvent, BacktestEventType, BacktestRun, HistoricalAnalyticalEvaluation,
    HistoricalAnalyticalSnapshot, HistoricalAnalyticalStatus,
)


@dataclass(frozen=True, slots=True)
class HistoricalAnalyticalReplayConfig:
    strategy_reference: StrategyVersionReference
    benchmark_instrument_id: str
    gate_config: ExecutionGateConfig
    calendar: ExchangeCalendarProtocol
    action_context: ActionContext = ActionContext.ROTATE_IN
    configuration_version: str = "historical-analytical-replay-v1"


class HistoricalSnapshotBuilder:
    """Builds a validated domain snapshot and a separate immutable replay provenance record."""
    def __init__(self, repository, guard: BacktestLookaheadGuard | None = None) -> None:
        self.repository, self.guard = repository, guard or BacktestLookaheadGuard()

    def build(self, run: BacktestRun, step_number: int, instrument_id: str, at: datetime) -> tuple[AsOfSnapshot, HistoricalAnalyticalSnapshot]:
        eligible = []
        for record_key, observation in self.repository.eligible_observations_as_of(at):
            if self.guard.evaluate(_fact(observation), at).value == "ELIGIBLE":
                eligible.append((record_key, observation))
        observations = tuple(item for _, item in eligible)
        source = AsOfSnapshot(deterministic_snapshot_id(at, observations, "historical-replay-v1"), at, at,
                              "domain-valid;point-in-time-guard", observations)
        self.repository.save_snapshot(source, tuple(key for key, _ in eligible))
        selected = tuple(item.id for item in observations)
        latest = _latest_ids(observations)
        fingerprint = manifest_fingerprint(run_id=run.backtest_run_id, step=step_number, instrument=instrument_id,
                                           timestamp=at, inputs=selected)
        record = HistoricalAnalyticalSnapshot(
            f"historical-snapshot-{fingerprint[:24]}", run.backtest_run_id, step_number, at, instrument_id,
            run.dataset_manifest_id, source.id, selected, latest, selected, (), (), fingerprint,
        )
        self.repository.save_historical_analytical_snapshot(record)
        return source, record


class HistoricalAnalyticalReplayService:
    """Coordinates frozen inputs through existing engines; missing data stays missing."""
    def __init__(self, repository, config: HistoricalAnalyticalReplayConfig, guard: BacktestLookaheadGuard | None = None) -> None:
        self.repository, self.config, self.guard = repository, config, guard or BacktestLookaheadGuard()
        self.snapshots = HistoricalSnapshotBuilder(repository, self.guard)
        self.evaluator = DeterministicDiagnosticEvaluators()

    def evaluate_step(self, run: BacktestRun, context: ReplayStepContext) -> ReplayStepHandlerResult:
        self._validate_frozen_versions(run)
        memberships = self.repository.list_universe_memberships_as_of(run.universe_definition, context.evaluation_timestamp)
        evaluations = []
        for membership in memberships:
            snapshot, snapshot_record = self.snapshots.build(run, context.step_number, membership.instrument_id, context.evaluation_timestamp)
            self._event(run, BacktestEventType.SNAPSHOT_BUILT, context, membership.instrument_id, snapshot_record.historical_snapshot_id)
            diagnostics = self._diagnostics(run, snapshot, membership.instrument_id, context.evaluation_timestamp)
            for diagnostic in diagnostics:
                self._persist_diagnostic(run, diagnostic)
            self._event(run, BacktestEventType.DIAGNOSTICS_EVALUATED, context, membership.instrument_id, *[x.record.id for x in diagnostics])
            scorecard = build_scorecard(instrument_id=membership.instrument_id, strategy_version=self.config.strategy_reference,
                registry_version=run.registry_version, as_of_timestamp=context.evaluation_timestamp,
                evaluated_at=context.evaluation_timestamp, diagnostics=diagnostics, configuration_version=run.scoring_config_version)
            scorecard = replace(scorecard, id=f"{run.backtest_run_id}|{scorecard.id}")
            self.repository.save_decision_scorecard(scorecard)
            self._event(run, BacktestEventType.SCORECARD_CREATED, context, membership.instrument_id, scorecard.id)
            gate = self._gates(run, snapshot_record, membership.instrument_id, context.evaluation_timestamp, scorecard, diagnostics, snapshot)
            self.repository.save_execution_gate_evaluation(gate)
            self._event(run, BacktestEventType.GATES_EVALUATED, context, membership.instrument_id, gate.id)
            missing = tuple(str(x.canonical_rule_id) for x in diagnostics if x.eligibility is not EvaluationEligibility.ELIGIBLE)
            status = HistoricalAnalyticalStatus.COMPLETED if not missing else HistoricalAnalyticalStatus.INSUFFICIENT_DATA
            fingerprint = manifest_fingerprint(run=run.fingerprint, snapshot=snapshot_record.fingerprint,
                diagnostics=tuple(x.record.id for x in diagnostics), scorecard=scorecard.id, gates=gate.id)
            evaluation = HistoricalAnalyticalEvaluation(
                f"historical-evaluation-{fingerprint[:24]}", run.backtest_run_id, context.step_number,
                context.evaluation_timestamp, membership.instrument_id, snapshot_record.historical_snapshot_id,
                run.strategy_version, run.registry_version, run.scoring_config_version, run.gate_config_version,
                tuple(x.record.id for x in diagnostics), scorecard.id, scorecard.data_confidence, gate.id, status,
                tuple(scorecard.warnings) + tuple(gate.warnings), tuple(f"RULE_{x}" for x in missing), fingerprint,
            )
            self.repository.save_historical_analytical_evaluation(evaluation); evaluations.append(evaluation)
            self._event(run, BacktestEventType.ANALYTICAL_EVALUATION_COMPLETED if status is HistoricalAnalyticalStatus.COMPLETED else BacktestEventType.ANALYTICAL_EVALUATION_INSUFFICIENT, context, membership.instrument_id, evaluation.evaluation_id)
        return ReplayStepHandlerResult(snapshot_references=tuple(x.historical_snapshot_id for x in evaluations),
                                       warnings=tuple(sorted({warning for x in evaluations for warning in x.warnings})))

    def _validate_frozen_versions(self, run):
        if self.repository.get_strategy_definition(self.config.strategy_reference) is None:
            raise ValueError("Historical analytical replay requires the frozen strategy version.")
        if run.strategy_version != f"{self.config.strategy_reference.strategy_id}:{self.config.strategy_reference.version}":
            raise ValueError("Backtest run strategy version does not match the frozen analytical strategy.")
        if run.registry_version != DIAGNOSTIC_REGISTRY_VERSION:
            raise ValueError("Referenced diagnostic registry is unavailable; replay fails closed.")
        if run.gate_config_version != self.config.gate_config.version:
            raise ValueError("Referenced execution-gate configuration is unavailable; replay fails closed.")

    def _diagnostics(self, run, snapshot, instrument, at):
        results: dict[int, EvaluatedDiagnostic] = {}
        try:
            results[1] = self.evaluator.market_regime(snapshot, self.config.benchmark_instrument_id, self.config.strategy_reference,
                MarketRegimeRules(2,3,2,3,.2,.1,.02,-.02,-.1,-.4,.3), at)
            results[4] = self.evaluator.primary_trend(None, snapshot, instrument, self.config.strategy_reference, TrendRules(3,5,True,1), at)
            results[5] = self.evaluator.weinstein(snapshot, instrument, self.config.strategy_reference, WeinsteinRules(3,2), at)
            results[6] = self.evaluator.relative_strength(snapshot, instrument, self.config.benchmark_instrument_id, None, (), self.config.strategy_reference, RelativeStrengthRules(3,.1,.03,-.03), at)
            results[10] = self.evaluator.market_structure(snapshot, instrument, self.config.strategy_reference, 1, at)
            results[39] = self.evaluator.indicator_layer(snapshot, instrument, self.config.strategy_reference, 3,70,30,20,2,at)
        except Exception:
            # A malformed otherwise eligible historical input becomes an explicit missing rule below.
            results = {}
        return tuple(self._clone(run, instrument, results.get(rule.rule_id) or self.evaluator._missing(rule.rule_id, instrument, self.config.strategy_reference, at, "required historical inputs unavailable")) for rule in DIAGNOSTIC_RULES)

    def _clone(self, run, instrument, diagnostic):
        evidence = tuple(replace(x, id=f"{run.backtest_run_id}|{x.id}") for x in diagnostic.evidence)
        record = replace(diagnostic.record, id=f"{run.backtest_run_id}|{diagnostic.record.id}", instrument_id=instrument, evidence_ids=tuple(x.id for x in evidence))
        return replace(diagnostic, record=record, evidence=evidence)

    def _persist_diagnostic(self, run, diagnostic):
        for evidence in diagnostic.evidence: self.repository.save_evidence(evidence)
        self.repository.save_diagnostic_result(diagnostic.record)

    def _gates(self, run, snapshot_record, instrument, at, scorecard, diagnostics, snapshot):
        surveillance = _surveillance(snapshot, instrument)
        earnings_at, earnings_verified_at = _earnings_schedule(snapshot, instrument)
        gate_input = GateInput(scorecard.id, scorecard.final_score, snapshot_record.source_snapshot_id, at,
            comparison_score=None, evidence_ids=tuple(x for component in scorecard.components for x in component.evidence_ids),
            diagnostic_ids=tuple(x.record.id for x in diagnostics), surveillance=surveillance,
            earnings_scheduled_at=earnings_at, earnings_schedule_verified_at=earnings_verified_at)
        return ExecutionGateEngine(self.config.gate_config, self.config.calendar).evaluate(
            instrument_id=instrument, strategy_version=self.config.strategy_reference, registry_version=run.registry_version,
            scoring_configuration_version=run.scoring_config_version, action_context=self.config.action_context,
            as_of_timestamp=at, evaluated_at=at, inputs=gate_input)

    def _event(self, run, event_type, context, instrument, *artifact_ids):
        event = BacktestEvent(f"{run.backtest_run_id}:event:{len(self.repository.list_backtest_events(run.backtest_run_id))+1:06d}", run.backtest_run_id,
            event_type, context.evaluation_timestamp, context.step_number, context.evaluation_timestamp, tuple(artifact_ids),
            event_type.value, {"instrument_id": instrument}, context.evaluation_timestamp)
        self.repository.append_backtest_event(event)


def _fact(observation: MarketObservation) -> HistoricalFact:
    published = observation.publication_timestamp if isinstance(observation, FinancialObservation) else None
    if published is None and isinstance(observation.payload, dict): published = observation.payload.get("publication_timestamp")
    return HistoricalFact(observation.id, str(observation.kind), observation.provenance.market_timestamp, published, observation.provenance.retrieved_timestamp)


def _latest_ids(observations: tuple[MarketObservation, ...]) -> tuple[str, ...]:
    latest: dict[tuple[str,str], MarketObservation] = {}
    for observation in observations:
        key = (observation.instrument.id, str(observation.kind))
        if key not in latest or observation.provenance.market_timestamp > latest[key].provenance.market_timestamp:
            latest[key] = observation
    return tuple(sorted(x.id for x in latest.values()))


def _as_datetime(value):
    return datetime.fromisoformat(value) if isinstance(value, str) else value if isinstance(value, datetime) else None


def _surveillance(snapshot, instrument):
    candidates = [x for x in snapshot.observations if x.instrument.id == instrument and isinstance(x.payload, dict) and "asm_stage" in x.payload]
    if not candidates: return None
    item = max(candidates, key=lambda x: x.provenance.market_timestamp)
    payload = item.payload
    circuit = payload.get("circuit_limit")
    return SurveillanceObservation(item.id, item.provenance.market_timestamp, item.provenance.source,
        bool(payload.get("authoritative", False)), payload.get("asm_stage"), payload.get("gsm_stage"),
        Decimal(str(circuit)) if circuit is not None else None, (item.id,))


def _earnings_schedule(snapshot, instrument):
    candidates = [x for x in snapshot.observations if x.instrument.id == instrument and isinstance(x.payload, dict) and "earnings_scheduled_at" in x.payload]
    if not candidates: return None, None
    item = max(candidates, key=lambda x: x.provenance.market_timestamp)
    return _as_datetime(item.payload.get("earnings_scheduled_at")), _as_datetime(item.payload.get("earnings_schedule_verified_at")) or item.provenance.market_timestamp
