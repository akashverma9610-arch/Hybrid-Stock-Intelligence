from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Mapping

from app.domain.models import (
    AnalyticalDecisionReconstruction, ApprovalStatus, AuthorReviewerMetadata,
    ConfigurationValueStatus, DataQuality, DiagnosticResult, Evidence, EvidenceType,
    GateDecision, GateOutcome, Scorecard, ScorecardComponent, StrategyConfiguration,
    StrategyDefinition, StrategyLifecycleEvent, StrategyStatus, StrategyValidationStatus,
    StrategyVersionReference,
)
from app.storage.governance_repository import StrategyGovernanceRepository
from app.storage.sqlite_repository import SQLiteMarketDataRepository, _parse_timestamp, _provenance_from_dict, _provenance_to_dict, _timestamp
from app.scoring.engine import DecisionScorecard, ScoredComponent
from decimal import Decimal
from app.gates.engine import ActionContext, ExecutionEligibility, ExecutionGateEvaluation, GateDecisionRecord, GateOutcome as ExecutionGateOutcome
from app.portfolio.models import CorporateAction, Portfolio, PortfolioSnapshot, PortfolioTransaction
from app.portfolio.serialization import corporate_action_from, dumps as portfolio_dumps, portfolio_from, snapshot_from, transaction_from
from app.rotation.models import PortfolioRotationEvaluation
from app.rotation.serialization import dumps as rotation_dumps, loads as rotation_from
from app.signals.models import SignalLifecycleEvent, SignalRecord, TradePlan
from app.signals.serialization import dumps as signal_dumps, event_from, plan_from, signal_from
from app.paper.models import PaperFill, PaperLifecycleEvent, PaperOutcome, PaperTrade
from app.paper.serialization import dumps as paper_dumps, trade_from as paper_trade_from
from app.performance.models import PerformanceEvaluationDataset, PerformanceReport
from app.portfolio.serialization import dumps as performance_dumps
from app.performance.serialization import comparison_from, dataset_from, dump as perf_dump, report_from, run_from
from app.performance.models import BenchmarkComparison
from app.performance.benchmarks import BenchmarkRun
from app.historical.models import HistoricalDatasetManifest, HistoricalPartition, UniverseMembership, DatasetQuality, GapType, InstrumentLifecycle, PartitionType, SurvivorshipStatus
from app.backtest.models import BacktestDataGapPolicy, BacktestEvent, BacktestReplayStep, BacktestRun, ReplaySchedule, HistoricalAnalyticalEvaluation, HistoricalAnalyticalSnapshot, HistoricalRotationCandidateContext, HistoricalRotationHistory, HistoricalRotationEvaluation, HistoricalSignalReplayReference, HistoricalPaperReplayReference, HistoricalTriggerTimingContext, HistoricalExecutionTimingContext, HistoricalCapitalAllocation, HistoricalPaperLedgerLink, HistoricalEquityPoint, HistoricalEquitySeries, SignalConfigSnapshot, PaperTradingConfigSnapshot
from app.backtest.serialization import event_from as backtest_event_from, gap_policy_from, historical_evaluation_from, historical_snapshot_from, holding_gate_context_from, portfolio_gate_evaluation_from, rotation_candidate_context_from, rotation_history_from, rotation_evaluation_from, signal_replay_reference_from, paper_replay_reference_from, trigger_timing_context_from, execution_timing_context_from, capital_allocation_from, paper_ledger_link_from, historical_equity_point_from, historical_equity_series_from, signal_config_snapshot_from, paper_config_snapshot_from, run_from as backtest_run_from, schedule_from, step_from as backtest_step_from
from app.backtest.serialization import dump as backtest_dump
from app.backtest.portfolio import BacktestPortfolioLedgerEvent, BacktestPortfolioState, ledger_from as backtest_ledger_from, state_dump as backtest_state_dump, state_from as backtest_state_from
from app.backtest.walk_forward import WalkForwardPlan, StrategyCandidate, WalkForwardWindow, WalkForwardRun, WalkForwardWindowResult
from app.backtest.walk_forward_serialization import dump as walk_forward_dump, plan_from as walk_forward_plan_from, candidate_from as strategy_candidate_from, window_from as walk_forward_window_from, run_from as walk_forward_run_from, result_from as walk_forward_result_from
from app.backtest.oos_aggregation import WalkForwardValidationConfig, OOSStitchedEquityObservation, WalkForwardOOSEquitySeries, ValidationDegradationAnalysis, WalkForwardAggregateResult, HistoricalBenchmarkObservation
from app.backtest.oos_aggregation_serialization import dump as oos_dump, config_from as oos_config_from, observation_from as oos_observation_from, series_from as oos_series_from, degradation_from as oos_degradation_from, aggregate_from as oos_aggregate_from
from app.backtest.experiments import ExperimentBudget, StrategyCandidateDelta, StrategyExperiment, CandidateEvaluationEvidence, CandidateRobustnessResult, CandidateSelectionPolicy, CandidateSelectionResult
from app.backtest.experiments_serialization import dump as experiment_dump, budget_from, delta_from, experiment_from, evidence_from, robustness_from, policy_from, selection_from
from app.backtest.promotion import StrategyPromotionPolicy, StrategyPromotionProposal, PromotionEligibilityResult, StrategyPromotionReview, ApprovedStrategyVersion, StrategyActivation, StrategyRollback
from app.backtest.promotion_serialization import dump as promotion_dump, policy_from as promotion_policy_from, proposal_from as promotion_proposal_from, eligibility_from as promotion_eligibility_from, review_from as promotion_review_from, approved_from as approved_strategy_from, activation_from as activation_from, rollback_from
from app.self_improvement.models import SelfImprovementRun, SelfImprovementObservation, SelfImprovementEvidencePolicy, AttributionRuleSet, StrategyErrorAttribution, StrategySuccessAttribution, RecurringStrategyPattern, StrategyErrorSummary, StrategySuccessSummary, ImprovementHypothesis, HypothesisRankingPolicy, HypothesisProposalBudget, HypothesisGenerationPolicy, StrategyImprovementHypothesis, StrategyHypothesisRanking, HypothesisReview, HypothesisExperimentLink, AutomatedResearchRun, FutureOOSCandidateQueueEntry, AutomatedResearchCycleResult, FutureOOSAssignmentPolicy, FutureOOSAssignment, FutureOOSExecutionResult, ResearchCandidateOOSRecord, PromotionEvidencePackage, hypothesis_review_fingerprint, future_oos_assignment_policy_fingerprint, future_oos_assignment_fingerprint, future_oos_execution_fingerprint, promotion_evidence_package_fingerprint
from app.self_improvement.serialization import dump as self_improvement_dump, run_from as self_improvement_run_from, observation_from as self_improvement_observation_from, evidence_policy_from as self_improvement_evidence_policy_from, rule_set_from as attribution_rule_set_from, error_from as strategy_error_attribution_from, success_from as strategy_success_attribution_from, pattern_from as recurring_strategy_pattern_from, error_summary_from as strategy_error_summary_from, success_summary_from as strategy_success_summary_from, hypothesis_from as improvement_hypothesis_from, ranking_policy_from as hypothesis_ranking_policy_from, proposal_budget_from as hypothesis_proposal_budget_from, generation_policy_from as hypothesis_generation_policy_from, strategy_hypothesis_from, ranking_from as strategy_hypothesis_ranking_from, hypothesis_review_from, hypothesis_experiment_link_from, automated_research_run_from, future_oos_queue_from, automated_research_cycle_from, future_oos_assignment_policy_from, future_oos_assignment_from, future_oos_execution_from, research_candidate_oos_from, promotion_evidence_package_from
from app.strategies.pre_breakout.policy import PreBreakoutPolicyApproval, PreBreakoutPolicySelection
from app.strategies.pre_breakout.policy_serialization import (
    approval_from as prebreakout_approval_from,
    approval_to as prebreakout_approval_to,
    selection_from as prebreakout_selection_from,
    selection_to as prebreakout_selection_to,
)
from app.strategies.pre_breakout.setup_assessment import GovernedPreBreakoutSetupAssessment
from app.strategies.pre_breakout.setup_assessment_serialization import assessment_from as prebreakout_setup_assessment_from, assessment_to as prebreakout_setup_assessment_to
from app.reliability.models import StoredReliabilityDecision, ReliabilityStatus
from app.reliability.serialization import reliability_decision_from, reliability_decision_to
from app.research.handoff import BrainResearchHandoff, BrainResearchHandoffStatus, BrainResearchOriginType, BrainResearchStage
from app.research.handoff_serialization import handoff_from as brain_research_handoff_from, handoff_to as brain_research_handoff_to


class SQLiteStrategyGovernanceRepository(SQLiteMarketDataRepository, StrategyGovernanceRepository):
    """SQLite adapter that adds immutable Phase 2 governance records to Phase 1 data storage."""

    def __init__(self, database_path: str = ":memory:") -> None:
        super().__init__(database_path)
        self._create_governance_schema()

    def save_strategy_definition(self, definition: StrategyDefinition) -> None:
        try:
            self._connection.execute(
                """INSERT INTO strategy_versions (
                   strategy_id, version, name, initial_status, created_at, effective_from, effective_to,
                   description, configuration_json, rule_definition_version, scoring_configuration_version,
                   execution_gate_configuration_version, risk_configuration_version, benchmark_configuration_version,
                   author_reviewer_json, initial_approval_status, initial_validation_status,
                   parent_strategy_id, parent_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    definition.strategy_id, definition.version, definition.name, definition.status.value,
                    _timestamp(definition.created_at), _optional_timestamp(definition.effective_from),
                    _optional_timestamp(definition.effective_to), definition.description,
                    _json(definition.configuration), _configuration_version(definition.rule_definition_version),
                    _configuration_version(definition.scoring_configuration_version),
                    _configuration_version(definition.execution_gate_configuration_version),
                    _configuration_version(definition.risk_configuration_version),
                    _configuration_version(definition.benchmark_configuration_version),
                    _json(definition.author_reviewer), definition.approval_status.value,
                    definition.validation_status.value,
                    definition.parent_strategy_version.strategy_id if definition.parent_strategy_version else None,
                    definition.parent_strategy_version.version if definition.parent_strategy_version else None,
                ),
            )
            self._connection.commit()
        except sqlite3.IntegrityError as error:
            raise ValueError("Strategy versions are immutable and cannot be overwritten.") from error

    def get_strategy_definition(self, reference: StrategyVersionReference) -> StrategyDefinition | None:
        row = self._connection.execute(
            "SELECT * FROM strategy_versions WHERE strategy_id = ? AND version = ?",
            (reference.strategy_id, reference.version),
        ).fetchone()
        return self._strategy_from_row(row) if row else None

    def append_strategy_lifecycle_event(self, event: StrategyLifecycleEvent) -> None:
        if self.get_strategy_definition(event.strategy_version) is None:
            raise ValueError("A lifecycle event requires an existing strategy version.")
        try:
            self._connection.execute(
                """INSERT INTO strategy_lifecycle_events
                   (id, strategy_id, version, status, approval_status, validation_status, occurred_at, actor_id, rationale)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (event.id, event.strategy_version.strategy_id, event.strategy_version.version, event.status.value,
                 event.approval_status.value, event.validation_status.value, _timestamp(event.occurred_at),
                 event.actor_id, event.rationale),
            )
            self._connection.commit()
        except sqlite3.IntegrityError as error:
            raise ValueError("Lifecycle events are append-only and cannot be overwritten.") from error

    def latest_strategy_lifecycle_event(self, reference: StrategyVersionReference) -> StrategyLifecycleEvent | None:
        row = self._connection.execute(
            """SELECT * FROM strategy_lifecycle_events WHERE strategy_id = ? AND version = ?
               ORDER BY occurred_at DESC, id DESC LIMIT 1""",
            (reference.strategy_id, reference.version),
        ).fetchone()
        return self._lifecycle_from_row(row) if row else None

    def save_evidence(self, evidence: Evidence) -> None:
        try:
            self._connection.execute(
                """INSERT INTO evidence_records
                   (id, source, source_identifier, timestamp, observation_ids_json, evidence_type,
                    factual_content_reference, confidence, provenance_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (evidence.id, evidence.source, evidence.source_identifier, _timestamp(evidence.timestamp),
                 _json(list(evidence.observation_ids)), evidence.evidence_type.value,
                 evidence.factual_content_reference, evidence.confidence, _json(_provenance_to_dict(evidence.provenance))),
            )
            self._connection.commit()
        except sqlite3.IntegrityError as error:
            raise ValueError("Evidence records are immutable and cannot be overwritten.") from error

    def get_evidence(self, evidence_ids: tuple[str, ...]) -> tuple[Evidence, ...]:
        if not evidence_ids:
            return ()
        placeholders = ",".join("?" for _ in evidence_ids)
        rows = self._connection.execute(
            f"SELECT * FROM evidence_records WHERE id IN ({placeholders}) ORDER BY id", evidence_ids
        ).fetchall()
        return tuple(self._evidence_from_row(row) for row in rows)

    def save_diagnostic_result(self, result: DiagnosticResult) -> None:
        self._require_historical_context(result.strategy_version, result.as_of_timestamp)
        self._insert_immutable(
            """INSERT INTO diagnostic_results
               (id, instrument_id, rule_id, strategy_id, version, result, score, confidence,
                evidence_ids_json, input_observation_ids_json, evaluated_at, as_of_timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (result.id, result.instrument_id, result.rule_id, result.strategy_version.strategy_id,
             result.strategy_version.version, result.result, result.score, result.confidence,
             _json(list(result.evidence_ids)), _json(list(result.input_observation_ids)),
             _timestamp(result.evaluated_at), _timestamp(result.as_of_timestamp)),
            "Diagnostic results are immutable and cannot be overwritten.",
        )

    def list_diagnostic_results(self, reference: StrategyVersionReference, as_of_timestamp: datetime) -> tuple[DiagnosticResult, ...]:
        rows = self._connection.execute(
            """SELECT * FROM diagnostic_results WHERE strategy_id = ? AND version = ? AND as_of_timestamp = ?
               ORDER BY id""",
            (reference.strategy_id, reference.version, _timestamp(as_of_timestamp)),
        ).fetchall()
        return tuple(self._diagnostic_from_row(row) for row in rows)

    def save_scorecard(self, scorecard: Scorecard) -> None:
        self._require_historical_context(scorecard.strategy_version, scorecard.as_of_timestamp)
        self._insert_immutable(
            """INSERT INTO scorecards
               (id, instrument_id, strategy_id, version, evaluated_at, as_of_timestamp, components_json, aggregate_score)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (scorecard.id, scorecard.instrument_id, scorecard.strategy_version.strategy_id,
             scorecard.strategy_version.version, _timestamp(scorecard.evaluated_at),
             _timestamp(scorecard.as_of_timestamp), _json(list(scorecard.components)), scorecard.aggregate_score),
            "Scorecards are immutable and cannot be overwritten.",
        )

    def get_scorecard(self, scorecard_id: str) -> Scorecard | None:
        row = self._connection.execute("SELECT * FROM scorecards WHERE id = ?", (scorecard_id,)).fetchone()
        return self._scorecard_from_row(row) if row else None

    def save_decision_scorecard(self, scorecard: DecisionScorecard) -> None:
        self._require_historical_context(scorecard.strategy_version, scorecard.as_of_timestamp)
        diagnostic_ids={x for component in scorecard.components for x in component.diagnostic_ids}
        if diagnostic_ids:
            placeholders=",".join("?" for _ in diagnostic_ids)
            rows=self._connection.execute(f"SELECT id, instrument_id, as_of_timestamp FROM diagnostic_results WHERE id IN ({placeholders})",tuple(diagnostic_ids)).fetchall()
            if {row["id"] for row in rows}!=diagnostic_ids: raise ValueError("Decision scorecard references missing persisted diagnostics.")
            if any(row["instrument_id"]!=scorecard.instrument_id or _parse_timestamp(row["as_of_timestamp"])>scorecard.as_of_timestamp for row in rows): raise ValueError("Decision scorecard diagnostic references violate instrument/as-of integrity.")
        try:
            self._connection.execute("INSERT INTO decision_scorecards (id,instrument_id,strategy_id,version,registry_version,configuration_version,as_of_timestamp,evaluated_at,final_score,score_status,data_confidence,warnings_json,components_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",(scorecard.id,scorecard.instrument_id,scorecard.strategy_version.strategy_id,scorecard.strategy_version.version,scorecard.registry_version,scorecard.configuration_version,_timestamp(scorecard.as_of_timestamp),_timestamp(scorecard.evaluated_at),str(scorecard.final_score) if scorecard.final_score is not None else None,scorecard.score_status,scorecard.data_confidence,_json(list(scorecard.warnings)),_json(_decision_components(scorecard.components))))
            self._connection.commit()
        except sqlite3.IntegrityError as error: raise ValueError("Decision scorecards are immutable and cannot be overwritten.") from error

    def get_decision_scorecard(self, scorecard_id: str) -> DecisionScorecard | None:
        row=self._connection.execute("SELECT * FROM decision_scorecards WHERE id=?",(scorecard_id,)).fetchone()
        if not row:return None
        components=tuple(_decision_component_from_dict(x) for x in json.loads(row["components_json"]))
        return DecisionScorecard(row["id"],row["instrument_id"],StrategyVersionReference(row["strategy_id"],row["version"]),row["registry_version"],row["configuration_version"],_parse_timestamp(row["as_of_timestamp"]),_parse_timestamp(row["evaluated_at"]),components,Decimal(row["final_score"]) if row["final_score"] is not None else None,row["score_status"],row["data_confidence"],tuple(json.loads(row["warnings_json"])))

    def save_execution_gate_evaluation(self, evaluation: ExecutionGateEvaluation) -> None:
        self._require_historical_context(evaluation.strategy_version, evaluation.as_of_timestamp)
        scorecard = self.get_decision_scorecard(evaluation.scorecard_id)
        if scorecard is None:
            raise ValueError("Execution gate evaluation requires a persisted decision scorecard.")
        if scorecard.instrument_id != evaluation.instrument_id or scorecard.strategy_version != evaluation.strategy_version or scorecard.as_of_timestamp != evaluation.as_of_timestamp:
            raise ValueError("Execution gate evaluation scorecard reference violates strategy, instrument, or as-of integrity.")
        if len(evaluation.decisions) != 6:
            raise ValueError("Execution gate evaluation requires exactly six gate decisions.")
        self._insert_immutable(
            "INSERT INTO execution_gate_evaluations (id,instrument_id,strategy_id,version,scorecard_id,as_of_timestamp,evaluated_at,payload_json) VALUES (?,?,?,?,?,?,?,?)",
            (evaluation.id, evaluation.instrument_id, evaluation.strategy_version.strategy_id, evaluation.strategy_version.version,
             evaluation.scorecard_id, _timestamp(evaluation.as_of_timestamp), _timestamp(evaluation.evaluated_at), _json(_execution_evaluation_to_dict(evaluation))),
            "Execution gate evaluations are immutable and cannot be overwritten.",
        )
        for decision in evaluation.decisions:
            self._insert_immutable(
                "INSERT INTO execution_gate_decisions (evaluation_id,gate_id,outcome,detail,confidence,evidence_ids_json,parameters_json) VALUES (?,?,?,?,?,?,?)",
                (evaluation.id, decision.gate_id, decision.outcome.value, decision.detail, decision.confidence,
                 _json(list(decision.evidence_ids)), _json(dict(decision.parameters))),
                "Execution gate decisions are immutable and cannot be overwritten.",
            )

    def get_execution_gate_evaluation(self, evaluation_id: str) -> ExecutionGateEvaluation | None:
        row = self._connection.execute("SELECT * FROM execution_gate_evaluations WHERE id = ?", (evaluation_id,)).fetchone()
        return _execution_evaluation_from_dict(json.loads(row["payload_json"])) if row else None

    def save_portfolio(self, portfolio: Portfolio) -> None:
        self._insert_immutable("INSERT INTO portfolios (id,created_at,payload_json) VALUES (?,?,?)", (portfolio.portfolio_id, _timestamp(portfolio.created_at), _json(portfolio_dumps(portfolio))), "Portfolios are immutable and cannot be overwritten.")

    def get_portfolio(self, portfolio_id: str) -> Portfolio | None:
        row = self._connection.execute("SELECT payload_json FROM portfolios WHERE id = ?", (portfolio_id,)).fetchone()
        return portfolio_from(json.loads(row["payload_json"])) if row else None

    def append_portfolio_transaction(self, transaction: PortfolioTransaction) -> None:
        if self.get_portfolio(transaction.portfolio_id) is None: raise ValueError("Portfolio transactions require an existing portfolio.")
        self._insert_immutable("INSERT INTO portfolio_transactions (id,portfolio_id,effective_at,known_at,payload_json) VALUES (?,?,?,?,?)", (transaction.transaction_id, transaction.portfolio_id, _timestamp(transaction.effective_at), _timestamp(transaction.known_at), _json(portfolio_dumps(transaction))), "Portfolio transactions are append-only and cannot be overwritten.")

    def list_portfolio_transactions_as_of(self, portfolio_id: str, as_of_timestamp: datetime) -> tuple[PortfolioTransaction, ...]:
        rows = self._connection.execute("SELECT payload_json FROM portfolio_transactions WHERE portfolio_id = ? AND effective_at <= ? AND known_at <= ? ORDER BY effective_at, id", (portfolio_id, _timestamp(as_of_timestamp), _timestamp(as_of_timestamp))).fetchall()
        return tuple(transaction_from(json.loads(row["payload_json"])) for row in rows)

    def save_corporate_action(self, action: CorporateAction) -> None:
        if self.get_portfolio(action.portfolio_id) is None: raise ValueError("Corporate actions require an existing portfolio.")
        self._insert_immutable("INSERT INTO portfolio_corporate_actions (id,portfolio_id,effective_at,known_at,payload_json) VALUES (?,?,?,?,?)", (action.action_id, action.portfolio_id, _timestamp(action.effective_at), _timestamp(action.known_at), _json(portfolio_dumps(action))), "Corporate actions are append-only and cannot be overwritten.")

    def list_corporate_actions_as_of(self, portfolio_id: str, as_of_timestamp: datetime) -> tuple[CorporateAction, ...]:
        rows = self._connection.execute("SELECT payload_json FROM portfolio_corporate_actions WHERE portfolio_id = ? AND effective_at <= ? AND known_at <= ? ORDER BY effective_at, id", (portfolio_id, _timestamp(as_of_timestamp), _timestamp(as_of_timestamp))).fetchall()
        return tuple(corporate_action_from(json.loads(row["payload_json"])) for row in rows)

    def save_portfolio_snapshot(self, snapshot: PortfolioSnapshot) -> None:
        if self.get_portfolio(snapshot.portfolio_id) is None: raise ValueError("Portfolio snapshots require an existing portfolio.")
        self._insert_immutable("INSERT INTO portfolio_snapshots (id,portfolio_id,as_of_timestamp,payload_json) VALUES (?,?,?,?)", (snapshot.snapshot_id, snapshot.portfolio_id, _timestamp(snapshot.as_of_timestamp), _json(portfolio_dumps(snapshot))), "Portfolio snapshots are immutable and cannot be overwritten.")

    def get_portfolio_snapshot(self, snapshot_id: str) -> PortfolioSnapshot | None:
        row = self._connection.execute("SELECT payload_json FROM portfolio_snapshots WHERE id = ?", (snapshot_id,)).fetchone()
        return snapshot_from(json.loads(row["payload_json"])) if row else None

    def save_portfolio_rotation_evaluation(self, evaluation: PortfolioRotationEvaluation) -> None:
        snapshot = self.get_portfolio_snapshot(evaluation.context.portfolio_snapshot_id)
        if snapshot is None:
            raise ValueError("Rotation evaluation requires a persisted portfolio snapshot.")
        if snapshot.as_of_timestamp != evaluation.context.as_of_timestamp:
            raise ValueError("Rotation evaluation must match its portfolio snapshot as-of timestamp.")
        self._insert_immutable("INSERT INTO portfolio_rotation_evaluations (id,portfolio_snapshot_id,as_of_timestamp,payload_json) VALUES (?,?,?,?)", (evaluation.evaluation_id, evaluation.context.portfolio_snapshot_id, _timestamp(evaluation.context.as_of_timestamp), _json(rotation_dumps(evaluation))), "Portfolio rotation evaluations are immutable and cannot be overwritten.")
        for comparison in evaluation.comparisons:
            self._insert_immutable("INSERT INTO rotation_comparisons (evaluation_id,holding_instrument_id,candidate_instrument_id,payload_json) VALUES (?,?,?,?)", (evaluation.evaluation_id, comparison.holding_instrument_id, comparison.candidate_instrument_id, _json(rotation_dumps(comparison))), "Rotation comparisons are immutable and cannot be overwritten.")

    def get_portfolio_rotation_evaluation(self, evaluation_id: str) -> PortfolioRotationEvaluation | None:
        row = self._connection.execute("SELECT payload_json FROM portfolio_rotation_evaluations WHERE id = ?", (evaluation_id,)).fetchone()
        return rotation_from(json.loads(row["payload_json"])) if row else None

    def save_signal(self, signal: SignalRecord) -> None:
        self._insert_immutable("INSERT INTO signals (id,portfolio_snapshot_id,as_of_timestamp,payload_json) VALUES (?,?,?,?)", (signal.signal_id, signal.portfolio_snapshot_id, _timestamp(signal.as_of_timestamp), _json(signal_dumps(signal))), "Signals are immutable and cannot be overwritten.")

    def get_signal(self, signal_id: str) -> SignalRecord | None:
        row = self._connection.execute("SELECT payload_json FROM signals WHERE id = ?", (signal_id,)).fetchone()
        return signal_from(json.loads(row["payload_json"])) if row else None

    def save_trade_plan(self, plan: TradePlan) -> None:
        self._insert_immutable("INSERT INTO trade_plans (id,payload_json) VALUES (?,?)", (plan.plan_id, _json(signal_dumps(plan))), "Trade plans are immutable and cannot be overwritten.")
        for condition in plan.trigger_conditions:
            self._insert_immutable("INSERT INTO signal_trigger_conditions (plan_id,id,payload_json) VALUES (?,?,?)", (plan.plan_id, condition.condition_id, _json(signal_dumps(condition))), "Trigger conditions are immutable and cannot be overwritten.")

    def get_trade_plan(self, plan_id: str) -> TradePlan | None:
        row = self._connection.execute("SELECT payload_json FROM trade_plans WHERE id = ?", (plan_id,)).fetchone()
        return plan_from(json.loads(row["payload_json"])) if row else None

    def append_signal_event(self, event: SignalLifecycleEvent) -> None:
        if self.get_signal(event.signal_id) is None: raise ValueError("Signal lifecycle events require an existing signal.")
        self._insert_immutable("INSERT INTO signal_lifecycle_events (id,signal_id,as_of_timestamp,payload_json) VALUES (?,?,?,?)", (event.event_id, event.signal_id, _timestamp(event.as_of_timestamp), _json(signal_dumps(event))), "Signal lifecycle events are append-only and cannot be overwritten.")

    def list_signal_events(self, signal_id: str) -> tuple[SignalLifecycleEvent, ...]:
        rows = self._connection.execute("SELECT payload_json FROM signal_lifecycle_events WHERE signal_id = ? ORDER BY as_of_timestamp, id", (signal_id,)).fetchall()
        return tuple(event_from(json.loads(row["payload_json"])) for row in rows)

    def save_paper_trade(self, trade: PaperTrade) -> None:
        if self.get_signal(trade.source_signal_id) is None: raise ValueError("Paper trades require an existing signal.")
        self._insert_immutable("INSERT INTO paper_trades (id,signal_id,as_of_timestamp,payload_json) VALUES (?,?,?,?)", (trade.paper_trade_id, trade.source_signal_id, _timestamp(trade.as_of_timestamp), _json(paper_dumps(trade))), "Paper trades are immutable and cannot be overwritten.")

    def get_paper_trade(self, trade_id: str) -> PaperTrade | None:
        row=self._connection.execute("SELECT payload_json FROM paper_trades WHERE id=?",(trade_id,)).fetchone()
        return paper_trade_from(json.loads(row["payload_json"])) if row else None

    def append_paper_fill(self, fill: PaperFill) -> None:
        if self.get_paper_trade(fill.paper_trade_id) is None: raise ValueError("Paper fills require an existing paper trade.")
        self._insert_immutable("INSERT INTO paper_fills (id,paper_trade_id,payload_json) VALUES (?,?,?)", (fill.fill_id, fill.paper_trade_id, _json(paper_dumps(fill))), "Paper fills are append-only and cannot be overwritten.")

    def append_paper_lifecycle_event(self, event: PaperLifecycleEvent) -> None:
        if self.get_paper_trade(event.paper_trade_id) is None: raise ValueError("Paper lifecycle events require an existing paper trade.")
        self._insert_immutable("INSERT INTO paper_lifecycle_events (id,paper_trade_id,payload_json) VALUES (?,?,?)", (event.event_id, event.paper_trade_id, _json(paper_dumps(event))), "Paper lifecycle events are append-only and cannot be overwritten.")

    def save_paper_outcome(self, outcome: PaperOutcome) -> None:
        if self.get_paper_trade(outcome.paper_trade_id) is None: raise ValueError("Paper outcomes require an existing paper trade.")
        self._insert_immutable("INSERT INTO paper_outcomes (paper_trade_id,payload_json) VALUES (?,?)", (outcome.paper_trade_id, _json(paper_dumps(outcome))), "Paper outcomes are immutable and cannot be overwritten.")
    def get_paper_outcome(self, paper_trade_id):
        row=self._connection.execute("SELECT payload_json FROM paper_outcomes WHERE paper_trade_id=?",(paper_trade_id,)).fetchone()
        if not row: return None
        value=json.loads(row["payload_json"])
        from app.paper.models import PaperOutcome, PaperTradeState
        for key in ("entry_timestamp","final_exit_timestamp"):
            value[key]=datetime.fromisoformat(value[key]) if value[key] else None
        for key in ("entry_price","final_exit_price","gross_pnl","costs","net_pnl","percentage_return","r_multiple","mfe","mae","mfe_r","mae_r"):
            value[key]=Decimal(value[key]) if value[key] is not None else None
        value["state"]=PaperTradeState(value["state"]); value["price_bar_ids"]=tuple(value["price_bar_ids"])
        return PaperOutcome(**value)

    def save_performance_dataset(self, dataset: PerformanceEvaluationDataset) -> None:
        self._insert_immutable("INSERT INTO performance_datasets (id,end_timestamp,payload_json) VALUES (?,?,?)", (dataset.dataset_id,_timestamp(dataset.end),_json(perf_dump(dataset))), "Performance datasets are immutable and cannot be overwritten.")

    def get_performance_dataset(self, dataset_id: str) -> PerformanceEvaluationDataset | None:
        row=self._connection.execute("SELECT payload_json FROM performance_datasets WHERE id=?",(dataset_id,)).fetchone();return dataset_from(json.loads(row["payload_json"])) if row else None

    def save_performance_report(self, report: PerformanceReport, dataset_id: str) -> None:
        exists=self._connection.execute("SELECT 1 FROM performance_datasets WHERE id=?",(dataset_id,)).fetchone()
        if not exists: raise ValueError("Performance reports require a frozen persisted dataset.")
        self._insert_immutable("INSERT INTO performance_reports (id,dataset_id,end_timestamp,payload_json) VALUES (?,?,?,?)", (report.report_id,dataset_id,_timestamp(report.end),_json(perf_dump(report))), "Performance reports are immutable and cannot be overwritten.")
        for point in report.equity_curve:self._insert_immutable("INSERT INTO performance_equity_points (report_id,timestamp,trade_id,payload_json) VALUES (?,?,?,?)",(report.report_id,_timestamp(point.timestamp),point.trade_id,_json(perf_dump(point))),"Equity-curve records are immutable and cannot be overwritten.")

    def get_performance_report(self, report_id: str) -> PerformanceReport | None:
        row=self._connection.execute("SELECT payload_json FROM performance_reports WHERE id=?",(report_id,)).fetchone();return report_from(json.loads(row["payload_json"])) if row else None
    def list_performance_report_ids(self) -> tuple[str, ...]:
        return tuple(row["id"] for row in self._connection.execute("SELECT id FROM performance_reports ORDER BY id").fetchall())
    def get_performance_dataset_for_report(self, report_id: str) -> PerformanceEvaluationDataset | None:
        row=self._connection.execute("SELECT d.payload_json FROM performance_reports r JOIN performance_datasets d ON d.id=r.dataset_id WHERE r.id=?",(report_id,)).fetchone();return dataset_from(json.loads(row["payload_json"])) if row else None

    def save_benchmark_run(self, run_id, report_id, run, input_ids, methodology_version, window_end):
        if self.get_performance_report(report_id) is None: raise ValueError("Benchmark runs require an existing performance report.")
        self._insert_immutable("INSERT INTO benchmark_runs (id,report_id,window_end,input_ids_json,methodology_version,payload_json) VALUES (?,?,?,?,?,?)",(run_id,report_id,_timestamp(window_end),_json(list(input_ids)),methodology_version,_json(perf_dump(run))),"Benchmark runs are immutable and cannot be overwritten.")
    def save_benchmark_comparison(self, comparison_id, report_id, comparison):
        if self.get_performance_report(report_id) is None: raise ValueError("Benchmark comparisons require an existing performance report.")
        self._insert_immutable("INSERT INTO benchmark_comparisons (id,report_id,payload_json) VALUES (?,?,?)",(comparison_id,report_id,_json(perf_dump(comparison))),"Benchmark comparisons are immutable and cannot be overwritten.")
    def list_benchmark_runs(self,report_id):
        return tuple(run_from(json.loads(x["payload_json"])) for x in self._connection.execute("SELECT payload_json FROM benchmark_runs WHERE report_id=? ORDER BY id",(report_id,)))
    def list_benchmark_comparisons(self,report_id):
        return tuple(comparison_from(json.loads(x["payload_json"])) for x in self._connection.execute("SELECT payload_json FROM benchmark_comparisons WHERE report_id=? ORDER BY id",(report_id,)))
    def save_historical_manifest(self,m): self._insert_immutable("INSERT INTO historical_manifests (id,payload_json) VALUES (?,?)",(m.dataset_id,_json(_hist_dump(m))),"Historical manifests are immutable and cannot be overwritten.")
    def get_historical_manifest(self,i):
        r=self._connection.execute("SELECT payload_json FROM historical_manifests WHERE id=?",(i,)).fetchone();return _manifest_from(json.loads(r['payload_json'])) if r else None
    def save_historical_partition(self,p): self._insert_immutable("INSERT INTO historical_partitions (id,payload_json) VALUES (?,?)",(p.partition_id,_json(_hist_dump(p))),"Historical partitions are immutable and cannot be overwritten.")
    def get_historical_partition(self,i):
        r=self._connection.execute("SELECT payload_json FROM historical_partitions WHERE id=?",(i,)).fetchone();return _partition_from(json.loads(r['payload_json'])) if r else None
    def save_universe_membership(self,m): self._insert_immutable("INSERT INTO historical_memberships (id,payload_json) VALUES (?,?)",(m.membership_id,_json(_hist_dump(m))),"Universe memberships are immutable and cannot be overwritten.")
    def get_universe_membership(self,i):
        r=self._connection.execute("SELECT payload_json FROM historical_memberships WHERE id=?",(i,)).fetchone();return _membership_from(json.loads(r['payload_json'])) if r else None
    def list_universe_memberships_as_of(self, universe_id, as_of_timestamp):
        rows=self._connection.execute("SELECT payload_json FROM historical_memberships").fetchall()
        items=tuple(_membership_from(json.loads(x['payload_json'])) for x in rows)
        return tuple(sorted((x for x in items if x.universe_id==universe_id and x.known_at<=as_of_timestamp and x.effective_from<=as_of_timestamp and (x.effective_to is None or as_of_timestamp<=x.effective_to)),key=lambda x:(x.instrument_id,x.membership_id)))

    def save_replay_schedule(self, schedule: ReplaySchedule) -> None:
        self._insert_immutable("INSERT INTO replay_schedules (id,payload_json) VALUES (?,?)", (schedule.schedule_id, _json(backtest_dump(schedule))), "Replay schedules are immutable and cannot be overwritten.")

    def get_replay_schedule(self, schedule_id: str) -> ReplaySchedule | None:
        row = self._connection.execute("SELECT payload_json FROM replay_schedules WHERE id=?", (schedule_id,)).fetchone()
        return schedule_from(json.loads(row["payload_json"])) if row else None

    def save_backtest_data_gap_policy(self, policy: BacktestDataGapPolicy) -> None:
        self._insert_immutable("INSERT INTO backtest_data_gap_policies (id,payload_json) VALUES (?,?)", (policy.policy_id, _json(backtest_dump(policy))), "Backtest data-gap policies are immutable and cannot be overwritten.")

    def get_backtest_data_gap_policy(self, policy_id: str) -> BacktestDataGapPolicy | None:
        row = self._connection.execute("SELECT payload_json FROM backtest_data_gap_policies WHERE id=?", (policy_id,)).fetchone()
        return gap_policy_from(json.loads(row["payload_json"])) if row else None

    def save_backtest_run(self, run: BacktestRun) -> None:
        manifest = self.get_historical_manifest(run.dataset_manifest_id)
        if manifest is None or manifest.dataset_version != run.dataset_manifest_version or manifest.fingerprint != run.dataset_fingerprint:
            raise ValueError("Backtest runs require their exact persisted historical dataset manifest.")
        self._insert_immutable("INSERT INTO backtest_runs (id,payload_json) VALUES (?,?)", (run.backtest_run_id, _json(backtest_dump(run))), "Backtest runs are immutable and cannot be overwritten.")

    def get_backtest_run(self, backtest_run_id: str) -> BacktestRun | None:
        row = self._connection.execute("SELECT payload_json FROM backtest_runs WHERE id=?", (backtest_run_id,)).fetchone()
        return backtest_run_from(json.loads(row["payload_json"])) if row else None

    def save_backtest_replay_step(self, step: BacktestReplayStep) -> None:
        if self.get_backtest_run(step.backtest_run_id) is None:
            raise ValueError("Replay steps require an existing backtest run.")
        self._insert_immutable("INSERT INTO backtest_replay_steps (id,run_id,step_number,payload_json) VALUES (?,?,?,?)", (step.replay_step_id, step.backtest_run_id, step.step_number, _json(backtest_dump(step))), "Replay steps are immutable and cannot be overwritten.")

    def get_backtest_replay_step(self, replay_step_id: str) -> BacktestReplayStep | None:
        row = self._connection.execute("SELECT payload_json FROM backtest_replay_steps WHERE id=?", (replay_step_id,)).fetchone()
        return backtest_step_from(json.loads(row["payload_json"])) if row else None

    def list_backtest_replay_steps(self, backtest_run_id: str) -> tuple[BacktestReplayStep, ...]:
        rows = self._connection.execute("SELECT payload_json FROM backtest_replay_steps WHERE run_id=? ORDER BY step_number,id", (backtest_run_id,)).fetchall()
        return tuple(backtest_step_from(json.loads(row["payload_json"])) for row in rows)

    def append_backtest_event(self, event: BacktestEvent) -> None:
        run = self.get_backtest_run(event.backtest_run_id)
        if run is None:
            raise ValueError("Backtest events require an existing backtest run.")
        from app.backtest.engine import validate_event_sequence
        existing = self.list_backtest_events(event.backtest_run_id)
        try:
            validate_event_sequence(existing + (event,), run.status)
        except ValueError as error:
            raise ValueError(f"Invalid append-only backtest event sequence: {error}") from error
        next_sequence = self._connection.execute("SELECT COALESCE(MAX(sequence_number), 0) + 1 FROM backtest_events WHERE run_id=?", (event.backtest_run_id,)).fetchone()[0]
        self._insert_immutable("INSERT INTO backtest_events (id,run_id,sequence_number,step_number,event_timestamp,payload_json) VALUES (?,?,?,?,?,?)", (event.event_id, event.backtest_run_id, next_sequence, event.replay_step_number, _timestamp(event.event_timestamp), _json(backtest_dump(event))), "Backtest events are append-only and cannot be overwritten.")

    def get_backtest_event(self, event_id: str) -> BacktestEvent | None:
        row = self._connection.execute("SELECT payload_json FROM backtest_events WHERE id=?", (event_id,)).fetchone()
        return backtest_event_from(json.loads(row["payload_json"])) if row else None

    def list_backtest_events(self, backtest_run_id: str) -> tuple[BacktestEvent, ...]:
        rows = self._connection.execute("SELECT payload_json FROM backtest_events WHERE run_id=? ORDER BY sequence_number", (backtest_run_id,)).fetchall()
        return tuple(backtest_event_from(json.loads(row["payload_json"])) for row in rows)

    def save_historical_analytical_snapshot(self, snapshot: HistoricalAnalyticalSnapshot) -> None:
        if self.get_backtest_run(snapshot.backtest_run_id) is None: raise ValueError("Historical analytical snapshots require an existing backtest run.")
        self._insert_immutable("INSERT INTO historical_analytical_snapshots (id,run_id,payload_json) VALUES (?,?,?)",(snapshot.historical_snapshot_id,snapshot.backtest_run_id,_json(backtest_dump(snapshot))),"Historical analytical snapshots are immutable and cannot be overwritten.")
    def get_historical_analytical_snapshot(self, historical_snapshot_id):
        row=self._connection.execute("SELECT payload_json FROM historical_analytical_snapshots WHERE id=?",(historical_snapshot_id,)).fetchone();return historical_snapshot_from(json.loads(row['payload_json'])) if row else None
    def save_historical_analytical_evaluation(self, evaluation: HistoricalAnalyticalEvaluation) -> None:
        if self.get_historical_analytical_snapshot(evaluation.historical_snapshot_id) is None: raise ValueError("Historical analytical evaluations require a persisted snapshot reference.")
        self._insert_immutable("INSERT INTO historical_analytical_evaluations (id,run_id,step_number,payload_json) VALUES (?,?,?,?)",(evaluation.evaluation_id,evaluation.backtest_run_id,evaluation.replay_step_number,_json(backtest_dump(evaluation))),"Historical analytical evaluations are immutable and cannot be overwritten.")
    def get_historical_analytical_evaluation(self, evaluation_id):
        row=self._connection.execute("SELECT payload_json FROM historical_analytical_evaluations WHERE id=?",(evaluation_id,)).fetchone();return historical_evaluation_from(json.loads(row['payload_json'])) if row else None
    def list_historical_analytical_evaluations(self, run_id, step_number):
        rows=self._connection.execute("SELECT payload_json FROM historical_analytical_evaluations WHERE run_id=? AND step_number=? ORDER BY id",(run_id,step_number)).fetchall();return tuple(historical_evaluation_from(json.loads(x['payload_json'])) for x in rows)

    def append_backtest_portfolio_ledger_event(self, event: BacktestPortfolioLedgerEvent) -> None:
        if self.get_backtest_run(event.backtest_run_id) is None: raise ValueError("Backtest portfolio ledger events require an existing backtest run.")
        self._insert_immutable("INSERT INTO backtest_portfolio_ledger_events (id,run_id,effective_at,known_at,payload_json) VALUES (?,?,?,?,?)",(event.ledger_event_id,event.backtest_run_id,_timestamp(event.effective_at),_timestamp(event.known_at),_json(backtest_dump(event))),"Backtest portfolio ledger events are append-only and cannot be overwritten.")
    def get_backtest_portfolio_ledger_event(self, ledger_event_id):
        row=self._connection.execute("SELECT payload_json FROM backtest_portfolio_ledger_events WHERE id=?",(ledger_event_id,)).fetchone();return backtest_ledger_from(json.loads(row['payload_json'])) if row else None
    def list_backtest_portfolio_ledger_events(self, run_id):
        rows=self._connection.execute("SELECT payload_json FROM backtest_portfolio_ledger_events WHERE run_id=? ORDER BY effective_at,id",(run_id,)).fetchall();return tuple(backtest_ledger_from(json.loads(x['payload_json'])) for x in rows)
    def save_backtest_portfolio_state(self, state: BacktestPortfolioState) -> None:
        if self.get_backtest_run(state.backtest_run_id) is None: raise ValueError("Backtest portfolio states require an existing backtest run.")
        self._insert_immutable("INSERT INTO backtest_portfolio_states (id,run_id,step_number,payload_json) VALUES (?,?,?,?)",(state.backtest_portfolio_state_id,state.backtest_run_id,state.replay_step_number,_json(backtest_state_dump(state))),"Backtest portfolio states are immutable and cannot be overwritten.")
    def get_backtest_portfolio_state(self, state_id):
        row=self._connection.execute("SELECT payload_json FROM backtest_portfolio_states WHERE id=?",(state_id,)).fetchone();return backtest_state_from(json.loads(row['payload_json'])) if row else None
    def save_historical_holding_gate_context(self, context):
        self._insert_immutable("INSERT INTO historical_holding_gate_contexts (id,payload_json) VALUES (?,?)",(context.context_id,_json(backtest_dump(context))),"Historical holding gate contexts are immutable and cannot be overwritten.")
    def get_historical_holding_gate_context(self, context_id):
        row=self._connection.execute("SELECT payload_json FROM historical_holding_gate_contexts WHERE id=?",(context_id,)).fetchone();return holding_gate_context_from(json.loads(row['payload_json'])) if row else None
    def save_historical_portfolio_gate_evaluation(self, evaluation):
        if self.get_backtest_portfolio_state(evaluation.backtest_portfolio_state_id) is None: raise ValueError("Portfolio-context gate evaluations require a persisted backtest portfolio state.")
        self._insert_immutable("INSERT INTO historical_portfolio_gate_evaluations (id,run_id,payload_json) VALUES (?,?,?)",(evaluation.portfolio_gate_evaluation_id,evaluation.backtest_run_id,_json(backtest_dump(evaluation))),"Historical portfolio gate evaluations are immutable and cannot be overwritten.")
    def get_historical_portfolio_gate_evaluation(self, evaluation_id):
        row=self._connection.execute("SELECT payload_json FROM historical_portfolio_gate_evaluations WHERE id=?",(evaluation_id,)).fetchone();return portfolio_gate_evaluation_from(json.loads(row['payload_json'])) if row else None
    def save_historical_rotation_candidate_context(self, context):
        self._insert_immutable("INSERT INTO historical_rotation_candidate_contexts (id,payload_json) VALUES (?,?)",(context.context_id,_json(backtest_dump(context))),"Historical rotation candidate contexts are immutable and cannot be overwritten.")
    def get_historical_rotation_candidate_context(self, context_id):
        row=self._connection.execute("SELECT payload_json FROM historical_rotation_candidate_contexts WHERE id=?",(context_id,)).fetchone();return rotation_candidate_context_from(json.loads(row['payload_json'])) if row else None
    def save_historical_rotation_history(self, history):
        if self.get_backtest_run(history.backtest_run_id) is None: raise ValueError("Historical rotation history requires an existing backtest run.")
        self._insert_immutable("INSERT INTO historical_rotation_history (id,run_id,payload_json) VALUES (?,?,?)",(history.history_id,history.backtest_run_id,_json(backtest_dump(history))),"Historical rotation history is immutable and cannot be overwritten.")
    def get_historical_rotation_history(self, history_id):
        row=self._connection.execute("SELECT payload_json FROM historical_rotation_history WHERE id=?",(history_id,)).fetchone();return rotation_history_from(json.loads(row['payload_json'])) if row else None
    def save_historical_rotation_evaluation(self, evaluation):
        if self.get_backtest_portfolio_state(evaluation.backtest_portfolio_state_id) is None: raise ValueError("Historical rotation evaluations require a persisted portfolio state.")
        self._insert_immutable("INSERT INTO historical_rotation_evaluations (id,run_id,payload_json) VALUES (?,?,?)",(evaluation.rotation_evaluation_id,evaluation.backtest_run_id,_json(backtest_dump(evaluation))),"Historical rotation evaluations are immutable and cannot be overwritten.")
    def get_historical_rotation_evaluation(self, evaluation_id):
        row=self._connection.execute("SELECT payload_json FROM historical_rotation_evaluations WHERE id=?",(evaluation_id,)).fetchone();return rotation_evaluation_from(json.loads(row['payload_json'])) if row else None
    def save_historical_signal_replay_reference(self, reference):
        if self.get_signal(reference.signal_id) is None: raise ValueError("Historical signal replay reference requires a persisted signal.")
        self._insert_immutable("INSERT INTO historical_signal_replay_references (id,run_id,payload_json) VALUES (?,?,?)",(reference.reference_id,reference.backtest_run_id,_json(backtest_dump(reference))),"Historical signal replay references are immutable and cannot be overwritten.")
    def get_historical_signal_replay_reference(self, reference_id):
        row=self._connection.execute("SELECT payload_json FROM historical_signal_replay_references WHERE id=?",(reference_id,)).fetchone();return signal_replay_reference_from(json.loads(row['payload_json'])) if row else None
    def save_historical_paper_replay_reference(self, reference):
        if self.get_paper_trade(reference.paper_trade_id) is None: raise ValueError("Historical paper replay reference requires a persisted paper trade.")
        self._insert_immutable("INSERT INTO historical_paper_replay_references (id,run_id,payload_json) VALUES (?,?,?)",(reference.reference_id,reference.backtest_run_id,_json(backtest_dump(reference))),"Historical paper replay references are immutable and cannot be overwritten.")
    def get_historical_paper_replay_reference(self, reference_id):
        row=self._connection.execute("SELECT payload_json FROM historical_paper_replay_references WHERE id=?",(reference_id,)).fetchone();return paper_replay_reference_from(json.loads(row['payload_json'])) if row else None
    def save_historical_trigger_timing_context(self, context):
        if self.get_signal(context.signal_id) is None: raise ValueError("Historical trigger timing context requires a persisted signal.")
        self._insert_immutable("INSERT INTO historical_trigger_timing_contexts (id,payload_json) VALUES (?,?)",(context.trigger_context_id,_json(backtest_dump(context))),"Historical trigger timing contexts are immutable and cannot be overwritten.")
    def get_historical_trigger_timing_context(self, context_id):
        row=self._connection.execute("SELECT payload_json FROM historical_trigger_timing_contexts WHERE id=?",(context_id,)).fetchone();return trigger_timing_context_from(json.loads(row['payload_json'])) if row else None
    def save_historical_execution_timing_context(self, context):
        if self.get_backtest_run(context.backtest_run_id) is None or self.get_historical_trigger_timing_context(context.trigger_context_id) is None: raise ValueError("Historical execution timing context requires a persisted run and trigger context.")
        self._insert_immutable("INSERT INTO historical_execution_timing_contexts (id,run_id,payload_json) VALUES (?,?,?)",(context.context_id,context.backtest_run_id,_json(backtest_dump(context))),"Historical execution timing contexts are immutable and cannot be overwritten.")
    def get_historical_execution_timing_context(self, context_id):
        row=self._connection.execute("SELECT payload_json FROM historical_execution_timing_contexts WHERE id=?",(context_id,)).fetchone();return execution_timing_context_from(json.loads(row['payload_json'])) if row else None
    def save_historical_capital_allocation(self, allocation):
        if self.get_backtest_run(allocation.backtest_run_id) is None: raise ValueError("Historical capital allocation requires a persisted backtest run.")
        self._insert_immutable("INSERT INTO historical_capital_allocations (id,run_id,payload_json) VALUES (?,?,?)",(allocation.allocation_id,allocation.backtest_run_id,_json(backtest_dump(allocation))),"Historical capital allocations are immutable and cannot be overwritten.")
    def get_historical_capital_allocation(self, allocation_id):
        row=self._connection.execute("SELECT payload_json FROM historical_capital_allocations WHERE id=?",(allocation_id,)).fetchone();return capital_allocation_from(json.loads(row['payload_json'])) if row else None
    def save_historical_paper_ledger_link(self, link):
        if self.get_backtest_run(link.backtest_run_id) is None or self.get_paper_trade(link.paper_trade_id) is None: raise ValueError("Historical paper ledger link requires a persisted run and paper trade.")
        self._insert_immutable("INSERT INTO historical_paper_ledger_links (id,run_id,payload_json) VALUES (?,?,?)",(link.link_id,link.backtest_run_id,_json(backtest_dump(link))),"Historical paper ledger links are immutable and cannot be overwritten.")
    def get_historical_paper_ledger_link(self, link_id):
        row=self._connection.execute("SELECT payload_json FROM historical_paper_ledger_links WHERE id=?",(link_id,)).fetchone();return paper_ledger_link_from(json.loads(row['payload_json'])) if row else None
    def save_historical_equity_point(self, point):
        if self.get_backtest_portfolio_state(point.backtest_portfolio_state_id) is None: raise ValueError("Historical equity point requires a persisted portfolio state.")
        self._insert_immutable("INSERT INTO historical_equity_points (id,run_id,payload_json) VALUES (?,?,?)",(point.point_id,point.backtest_run_id,_json(backtest_dump(point))),"Historical equity points are immutable and cannot be overwritten.")
    def get_historical_equity_point(self, point_id):
        row=self._connection.execute("SELECT payload_json FROM historical_equity_points WHERE id=?",(point_id,)).fetchone();return historical_equity_point_from(json.loads(row['payload_json'])) if row else None
    def save_historical_equity_series(self, series):
        if self.get_backtest_run(series.backtest_run_id) is None or any(self.get_historical_equity_point(point_id) is None for point_id in series.point_ids): raise ValueError("Historical equity series requires persisted run and points.")
        self._insert_immutable("INSERT INTO historical_equity_series (id,run_id,payload_json) VALUES (?,?,?)",(series.series_id,series.backtest_run_id,_json(backtest_dump(series))),"Historical equity series are immutable and cannot be overwritten.")
    def get_historical_equity_series(self, series_id):
        row=self._connection.execute("SELECT payload_json FROM historical_equity_series WHERE id=?",(series_id,)).fetchone();return historical_equity_series_from(json.loads(row['payload_json'])) if row else None
    def save_signal_config_snapshot(self, snapshot):
        self._insert_immutable("INSERT INTO signal_config_snapshots (id,payload_json) VALUES (?,?)",(snapshot.snapshot_id,_json(backtest_dump(snapshot))),"Signal config snapshots are immutable and cannot be overwritten.")
    def get_signal_config_snapshot(self, snapshot_id):
        row=self._connection.execute("SELECT payload_json FROM signal_config_snapshots WHERE id=?",(snapshot_id,)).fetchone();return signal_config_snapshot_from(json.loads(row['payload_json'])) if row else None
    def save_paper_config_snapshot(self, snapshot):
        self._insert_immutable("INSERT INTO paper_config_snapshots (id,payload_json) VALUES (?,?)",(snapshot.snapshot_id,_json(backtest_dump(snapshot))),"Paper config snapshots are immutable and cannot be overwritten.")
    def get_paper_config_snapshot(self, snapshot_id):
        row=self._connection.execute("SELECT payload_json FROM paper_config_snapshots WHERE id=?",(snapshot_id,)).fetchone();return paper_config_snapshot_from(json.loads(row['payload_json'])) if row else None

    def save_walk_forward_plan(self, plan: WalkForwardPlan) -> None:
        manifest=self.get_historical_manifest(plan.dataset_id)
        if manifest is None or manifest.dataset_version != plan.dataset_version:
            raise ValueError("Walk-forward plans require their exact persisted historical dataset manifest.")
        self._insert_immutable("INSERT INTO walk_forward_plans (id,payload_json) VALUES (?,?)",(plan.plan_id,_json(walk_forward_dump(plan))),"Walk-forward plans are immutable and cannot be overwritten.")
    def get_walk_forward_plan(self, plan_id: str):
        row=self._connection.execute("SELECT payload_json FROM walk_forward_plans WHERE id=?",(plan_id,)).fetchone(); return walk_forward_plan_from(json.loads(row['payload_json'])) if row else None
    def save_strategy_candidate(self, candidate: StrategyCandidate) -> None:
        self._insert_immutable("INSERT INTO strategy_candidates (id,payload_json) VALUES (?,?)",(candidate.candidate_id,_json(walk_forward_dump(candidate))),"Strategy candidates are immutable and cannot be overwritten.")
    def get_strategy_candidate(self, candidate_id: str):
        row=self._connection.execute("SELECT payload_json FROM strategy_candidates WHERE id=?",(candidate_id,)).fetchone(); return strategy_candidate_from(json.loads(row['payload_json'])) if row else None
    def save_walk_forward_window(self, window: WalkForwardWindow) -> None:
        if self.get_walk_forward_plan(window.plan_id) is None or self.get_strategy_candidate(window.selected_candidate_id) is None:
            raise ValueError("Walk-forward windows require persisted plan and selected candidate.")
        for partition in (window.train, window.validation, window.test):
            if partition is not None:
                existing=self.get_historical_partition(partition.partition_id)
                if existing is None: self.save_historical_partition(partition)
                elif existing != partition: raise ValueError("Walk-forward partition IDs are immutable.")
        self._insert_immutable("INSERT INTO walk_forward_windows (id,plan_id,ordinal,payload_json) VALUES (?,?,?,?)",(window.window_id,window.plan_id,window.ordinal,_json(walk_forward_dump(window))),"Walk-forward windows are immutable and cannot be overwritten.")
    def get_walk_forward_window(self, window_id: str):
        row=self._connection.execute("SELECT payload_json FROM walk_forward_windows WHERE id=?",(window_id,)).fetchone(); return walk_forward_window_from(json.loads(row['payload_json'])) if row else None
    def list_walk_forward_windows(self, plan_id: str):
        rows=self._connection.execute("SELECT payload_json FROM walk_forward_windows WHERE plan_id=? ORDER BY ordinal,id",(plan_id,)).fetchall(); return tuple(walk_forward_window_from(json.loads(row['payload_json'])) for row in rows)
    def save_walk_forward_run(self, run: WalkForwardRun) -> None:
        if self.get_walk_forward_plan(run.plan_id) is None: raise ValueError("Walk-forward run requires a persisted plan.")
        windows=tuple(self.get_walk_forward_window(window_id) for window_id in run.ordered_window_ids)
        if any(window is None for window in windows) or tuple(window.window_id for window in windows) != run.ordered_window_ids:
            raise ValueError("Walk-forward run requires its exact persisted ordered windows.")
        if tuple(sorted(window.ordinal for window in windows)) != tuple(range(1,len(windows)+1)):
            raise ValueError("Walk-forward run windows must be a contiguous deterministic ordinal sequence.")
        if any(self.get_strategy_candidate(candidate_id) is None for candidate_id in run.candidate_ids): raise ValueError("Walk-forward run requires persisted candidates.")
        self._insert_immutable("INSERT INTO walk_forward_runs (id,plan_id,payload_json) VALUES (?,?,?)",(run.run_id,run.plan_id,_json(walk_forward_dump(run))),"Walk-forward runs are immutable and cannot be overwritten.")
    def get_walk_forward_run(self, run_id: str):
        row=self._connection.execute("SELECT payload_json FROM walk_forward_runs WHERE id=?",(run_id,)).fetchone(); return walk_forward_run_from(json.loads(row['payload_json'])) if row else None
    def save_walk_forward_window_result(self, result: WalkForwardWindowResult) -> None:
        run=self.get_walk_forward_run(result.walk_forward_run_id); window=self.get_walk_forward_window(result.walk_forward_window_id); candidate=self.get_strategy_candidate(result.selected_candidate_id)
        if run is None or window is None or candidate is None or result.walk_forward_window_id not in run.ordered_window_ids:
            raise ValueError("Walk-forward result requires persisted run, window, and candidate.")
        if candidate.fingerprint != result.selected_candidate_fingerprint or window.test.start != result.test_start or window.test.end != result.test_end:
            raise ValueError("Walk-forward result does not match its frozen candidate or TEST window.")
        if result.test_backtest_run_id is not None and self.get_backtest_run(result.test_backtest_run_id) is None:
            raise ValueError("Walk-forward result references a missing TEST backtest run.")
        if result.performance_report_id is not None and self.get_performance_report(result.performance_report_id) is None:
            raise ValueError("Walk-forward result references a missing performance report.")
        self._insert_immutable("INSERT INTO walk_forward_window_results (id,run_id,window_id,payload_json) VALUES (?,?,?,?)",(result.result_id,result.walk_forward_run_id,result.walk_forward_window_id,_json(walk_forward_dump(result))),"Walk-forward window results are immutable and cannot be overwritten.")
    def get_walk_forward_window_result(self, result_id: str):
        row=self._connection.execute("SELECT payload_json FROM walk_forward_window_results WHERE id=?",(result_id,)).fetchone(); return walk_forward_result_from(json.loads(row['payload_json'])) if row else None
    def list_walk_forward_window_results(self, run_id: str):
        rows=self._connection.execute("SELECT payload_json FROM walk_forward_window_results WHERE run_id=? ORDER BY id",(run_id,)).fetchall(); return tuple(walk_forward_result_from(json.loads(row['payload_json'])) for row in rows)
    def save_walk_forward_validation_config(self, config: WalkForwardValidationConfig) -> None:
        self._insert_immutable("INSERT INTO walk_forward_validation_configs (id,payload_json) VALUES (?,?)",(config.config_id,_json(oos_dump(config))),"Walk-forward validation configs are immutable and cannot be overwritten.")
    def get_walk_forward_validation_config(self, config_id: str):
        row=self._connection.execute("SELECT payload_json FROM walk_forward_validation_configs WHERE id=?",(config_id,)).fetchone(); return oos_config_from(json.loads(row['payload_json'])) if row else None
    def save_oos_stitched_equity_observation(self, observation: OOSStitchedEquityObservation) -> None:
        if self.get_walk_forward_run(observation.walk_forward_run_id) is None: raise ValueError("OOS equity observations require a persisted walk-forward run.")
        self._insert_immutable("INSERT INTO oos_stitched_equity_observations (id,run_id,timestamp,payload_json) VALUES (?,?,?,?)",(observation.observation_id,observation.walk_forward_run_id,_timestamp(observation.timestamp),_json(oos_dump(observation))),"OOS equity observations are immutable and cannot be overwritten.")
    def get_oos_stitched_equity_observation(self, observation_id: str):
        row=self._connection.execute("SELECT payload_json FROM oos_stitched_equity_observations WHERE id=?",(observation_id,)).fetchone(); return oos_observation_from(json.loads(row['payload_json'])) if row else None
    def save_walk_forward_oos_equity_series(self, series: WalkForwardOOSEquitySeries) -> None:
        if self.get_walk_forward_run(series.walk_forward_run_id) is None: raise ValueError("OOS equity series requires a persisted walk-forward run.")
        self._insert_immutable("INSERT INTO walk_forward_oos_equity_series (id,run_id,payload_json) VALUES (?,?,?)",(series.series_id,series.walk_forward_run_id,_json(oos_dump(series))),"OOS equity series are immutable and cannot be overwritten.")
    def get_walk_forward_oos_equity_series(self, series_id: str):
        row=self._connection.execute("SELECT payload_json FROM walk_forward_oos_equity_series WHERE id=?",(series_id,)).fetchone(); return oos_series_from(json.loads(row['payload_json'])) if row else None
    def save_validation_degradation_analysis(self, analysis: ValidationDegradationAnalysis) -> None:
        self._insert_immutable("INSERT INTO validation_degradation_analyses (id,run_id,payload_json) VALUES (?,?,?)",(analysis.analysis_id,analysis.walk_forward_run_id,_json(oos_dump(analysis))),"Validation degradation analyses are immutable and cannot be overwritten.")
    def get_validation_degradation_analysis(self, analysis_id: str):
        row=self._connection.execute("SELECT payload_json FROM validation_degradation_analyses WHERE id=?",(analysis_id,)).fetchone(); return oos_degradation_from(json.loads(row['payload_json'])) if row else None
    def save_walk_forward_aggregate_result(self, result: WalkForwardAggregateResult) -> None:
        if self.get_walk_forward_run(result.walk_forward_run_id) is None or self.get_walk_forward_validation_config(result.validation_config_id) is None or self.get_walk_forward_oos_equity_series(result.oos_equity_series_id) is None: raise ValueError("OOS aggregate requires persisted run, config, and stitched equity series.")
        self._insert_immutable("INSERT INTO walk_forward_aggregate_results (id,run_id,payload_json) VALUES (?,?,?)",(result.aggregate_result_id,result.walk_forward_run_id,_json(oos_dump(result))),"Walk-forward aggregate results are immutable and cannot be overwritten.")
    def get_walk_forward_aggregate_result(self, result_id: str):
        row=self._connection.execute("SELECT payload_json FROM walk_forward_aggregate_results WHERE id=?",(result_id,)).fetchone(); return oos_aggregate_from(json.loads(row['payload_json'])) if row else None
    def save_historical_benchmark_observation(self, observation: HistoricalBenchmarkObservation) -> None:
        self._insert_immutable("INSERT INTO historical_benchmark_observations (id,benchmark_run_id,timestamp,payload_json) VALUES (?,?,?,?)",(observation.observation_id,observation.benchmark_run_id,_timestamp(observation.timestamp),_json(oos_dump(observation))),"Historical benchmark observations are immutable and cannot be overwritten.")
    def list_historical_benchmark_observations(self, benchmark_run_id: str):
        rows=self._connection.execute("SELECT payload_json FROM historical_benchmark_observations WHERE benchmark_run_id=? ORDER BY timestamp,id",(benchmark_run_id,)).fetchall(); return tuple(HistoricalBenchmarkObservation(**{**json.loads(row['payload_json']),"timestamp":datetime.fromisoformat(json.loads(row['payload_json'])["timestamp"]),"value":Decimal(json.loads(row['payload_json'])["value"])}) for row in rows)
    def save_experiment_budget(self,budget):self._insert_immutable("INSERT INTO experiment_budgets (id,payload_json) VALUES (?,?)",(budget.budget_id,_json(experiment_dump(budget))),"Experiment budgets are immutable and cannot be overwritten.")
    def get_experiment_budget(self,identifier):
        row=self._connection.execute("SELECT payload_json FROM experiment_budgets WHERE id=?",(identifier,)).fetchone();return budget_from(json.loads(row['payload_json'])) if row else None
    def save_strategy_candidate_delta(self,delta):
        self._insert_immutable("INSERT INTO strategy_candidate_deltas (id,experiment_id,payload_json) VALUES (?,?,?)",(delta.delta_id,delta.experiment_id,_json(experiment_dump(delta))),"Strategy candidate deltas are immutable and cannot be overwritten.")
    def list_strategy_candidate_deltas(self,experiment_id):
        rows=self._connection.execute("SELECT payload_json FROM strategy_candidate_deltas WHERE experiment_id=? ORDER BY id",(experiment_id,)).fetchall();return tuple(delta_from(json.loads(row['payload_json'])) for row in rows)
    def save_strategy_experiment(self,experiment):
        if self.get_experiment_budget(experiment.budget_id) is None:raise ValueError("Strategy experiment requires its frozen budget.")
        self._insert_immutable("INSERT INTO strategy_experiments (id,payload_json) VALUES (?,?)",(experiment.experiment_id,_json(experiment_dump(experiment))),"Strategy experiments are immutable and cannot be overwritten.")
    def get_strategy_experiment(self,identifier):
        row=self._connection.execute("SELECT payload_json FROM strategy_experiments WHERE id=?",(identifier,)).fetchone();return experiment_from(json.loads(row['payload_json'])) if row else None
    def save_candidate_evaluation_evidence(self,evidence):
        if self.get_strategy_experiment(evidence.experiment_id) is None:raise ValueError("Candidate evidence requires its experiment.")
        self._insert_immutable("INSERT INTO candidate_evaluation_evidence (id,experiment_id,payload_json) VALUES (?,?,?)",(evidence.evidence_id,evidence.experiment_id,_json(experiment_dump(evidence))),"Candidate evaluation evidence is immutable and cannot be overwritten.")
    def list_candidate_evaluation_evidence(self,experiment_id):
        rows=self._connection.execute("SELECT payload_json FROM candidate_evaluation_evidence WHERE experiment_id=? ORDER BY id",(experiment_id,)).fetchall();return tuple(sorted((evidence_from(json.loads(row['payload_json'])) for row in rows),key=lambda item:(item.evaluated_at,item.evidence_id)))
    def save_candidate_robustness_result(self,result):self._insert_immutable("INSERT INTO candidate_robustness_results (id,payload_json) VALUES (?,?)",(result.robustness_id,_json(experiment_dump(result))),"Candidate robustness results are immutable and cannot be overwritten.")
    def get_candidate_robustness_result(self,identifier):
        row=self._connection.execute("SELECT payload_json FROM candidate_robustness_results WHERE id=?",(identifier,)).fetchone();return robustness_from(json.loads(row['payload_json'])) if row else None
    def save_candidate_selection_policy(self,policy):self._insert_immutable("INSERT INTO candidate_selection_policies (id,payload_json) VALUES (?,?)",(policy.policy_id,_json(experiment_dump(policy))),"Candidate selection policies are immutable and cannot be overwritten.")
    def get_candidate_selection_policy(self,identifier):
        row=self._connection.execute("SELECT payload_json FROM candidate_selection_policies WHERE id=?",(identifier,)).fetchone();return policy_from(json.loads(row['payload_json'])) if row else None
    def save_candidate_selection_result(self,result):
        if self.get_strategy_experiment(result.experiment_id) is None or self.get_candidate_selection_policy(result.policy_id) is None:raise ValueError("Candidate selection requires frozen experiment and policy.")
        self._insert_immutable("INSERT INTO candidate_selection_results (id,experiment_id,payload_json) VALUES (?,?,?)",(result.selection_id,result.experiment_id,_json(experiment_dump(result))),"Candidate selection results are immutable and cannot be overwritten.")
    def get_candidate_selection_result(self,identifier):
        row=self._connection.execute("SELECT payload_json FROM candidate_selection_results WHERE id=?",(identifier,)).fetchone();return selection_from(json.loads(row['payload_json'])) if row else None
    def _promotion_save(self,table,identifier,value,message):self._insert_immutable(f"INSERT INTO {table} (id,payload_json) VALUES (?,?)",(identifier,_json(promotion_dump(value))),message)
    def save_strategy_promotion_policy(self,value):self._promotion_save("strategy_promotion_policies",value.policy_id,value,"Promotion policies are immutable and cannot be overwritten.")
    def get_strategy_promotion_policy(self,i):
        r=self._connection.execute("SELECT payload_json FROM strategy_promotion_policies WHERE id=?",(i,)).fetchone();return promotion_policy_from(json.loads(r['payload_json'])) if r else None
    def save_strategy_promotion_proposal(self,value):self._promotion_save("strategy_promotion_proposals",value.proposal_id,value,"Promotion proposals are immutable and cannot be overwritten.")
    def get_strategy_promotion_proposal(self,i):
        r=self._connection.execute("SELECT payload_json FROM strategy_promotion_proposals WHERE id=?",(i,)).fetchone();return promotion_proposal_from(json.loads(r['payload_json'])) if r else None
    def save_promotion_eligibility_result(self,value):self._promotion_save("promotion_eligibility_results",value.eligibility_id,value,"Promotion eligibility results are immutable and cannot be overwritten.")
    def get_promotion_eligibility_result(self,i):
        r=self._connection.execute("SELECT payload_json FROM promotion_eligibility_results WHERE id=?",(i,)).fetchone();return promotion_eligibility_from(json.loads(r['payload_json'])) if r else None
    def save_strategy_promotion_review(self,value):
        if not value.reviewer_id.strip() or value.reviewer_id.lower().startswith(("system:","automation:","service:")):raise ValueError("Promotion review requires an explicit human reviewer identity.")
        if self.get_strategy_promotion_proposal(value.proposal_id) is None:raise ValueError("Promotion review requires a persisted proposal.")
        self._promotion_save("strategy_promotion_reviews",value.review_id,value,"Promotion reviews are immutable and cannot be overwritten.")
    def get_strategy_promotion_review(self,i):
        r=self._connection.execute("SELECT payload_json FROM strategy_promotion_reviews WHERE id=?",(i,)).fetchone();return promotion_review_from(json.loads(r['payload_json'])) if r else None
    def save_approved_strategy_version(self,value):
        proposal=self.get_strategy_promotion_proposal(value.proposal_id); review=self.get_strategy_promotion_review(value.review_id)
        if proposal is None or review is None or review.proposal_id!=value.proposal_id or review.decision.value!="APPROVE":raise ValueError("Approved strategy version requires a matching explicit human APPROVE review.")
        if value.approved_at<review.reviewed_at or value.effective_from<value.approved_at:raise ValueError("Approved strategy version has invalid human-review or effective-from chronology.")
        if value.parent_approved_id is not None:
            parent=self.get_approved_strategy_version(value.parent_approved_id)
            if parent is None or parent.strategy_id!=value.strategy_id or parent.effective_from>value.effective_from:raise ValueError("Approved strategy version has invalid immutable parent lineage.")
        duplicate=self._connection.execute("SELECT payload_json FROM approved_strategy_versions").fetchall()
        if any((item:=approved_strategy_from(json.loads(row['payload_json']))).strategy_id==value.strategy_id and item.version==value.version for row in duplicate):raise ValueError("Approved strategy semantic versions are immutable and unique.")
        self._promotion_save("approved_strategy_versions",value.approved_id,value,"Approved strategy versions are immutable and cannot be overwritten.")
    def get_approved_strategy_version(self,i):
        r=self._connection.execute("SELECT payload_json FROM approved_strategy_versions WHERE id=?",(i,)).fetchone();return approved_strategy_from(json.loads(r['payload_json'])) if r else None
    def list_approved_strategy_versions(self):
        rows=self._connection.execute("SELECT payload_json FROM approved_strategy_versions ORDER BY id").fetchall()
        return tuple(approved_strategy_from(json.loads(row['payload_json'])) for row in rows)
    def save_strategy_activation(self,value):
        version=self.get_approved_strategy_version(value.approved_id);review=self.get_strategy_promotion_review(value.review_id)
        if version is None or review is None or version.review_id!=review.review_id or review.decision.value!="APPROVE":raise ValueError("Strategy activation requires the approved version's explicit human APPROVE review.")
        if value.effective_at<version.effective_from or value.effective_at<review.reviewed_at:raise ValueError("Strategy activation must be prospective of approved version and review.")
        self._promotion_save("strategy_activations",value.activation_id,value,"Strategy activations are immutable and cannot be overwritten.")
    def get_strategy_activation(self,i):
        r=self._connection.execute("SELECT payload_json FROM strategy_activations WHERE id=?",(i,)).fetchone();return activation_from(json.loads(r['payload_json'])) if r else None
    def save_strategy_rollback(self,value):
        source=self.get_approved_strategy_version(value.from_approved_id);target=self.get_approved_strategy_version(value.to_approved_id);activation=self.get_strategy_activation(value.activation_id);review=self.get_strategy_promotion_review(value.review_id)
        if source is None or target is None or activation is None or review is None or review.decision.value!="APPROVE" or activation.approved_id!=target.approved_id or activation.previous_approved_id!=source.approved_id or activation.review_id!=review.review_id:raise ValueError("Rollback requires an explicit human-approved activation of an existing immutable target version.")
        self._promotion_save("strategy_rollbacks",value.rollback_id,value,"Strategy rollbacks are immutable and cannot be overwritten.")
    def get_strategy_rollback(self,i):
        r=self._connection.execute("SELECT payload_json FROM strategy_rollbacks WHERE id=?",(i,)).fetchone();return rollback_from(json.loads(r['payload_json'])) if r else None

    def save_prebreakout_policy_approval(self, value):
        self._insert_immutable("INSERT INTO prebreakout_policy_approvals (id,payload_json) VALUES (?,?)", (value.approval_id, _json(prebreakout_approval_to(value))), "Pre-Breakout policy approvals are immutable and cannot be overwritten.")
    def get_prebreakout_policy_approval(self, approval_id):
        row=self._connection.execute("SELECT payload_json FROM prebreakout_policy_approvals WHERE id=?",(approval_id,)).fetchone()
        return prebreakout_approval_from(json.loads(row['payload_json'])) if row else None
    def list_prebreakout_policy_approvals(self, policy_id=None):
        rows=self._connection.execute("SELECT payload_json FROM prebreakout_policy_approvals ORDER BY id").fetchall(); values=tuple(prebreakout_approval_from(json.loads(row['payload_json'])) for row in rows)
        return tuple(item for item in values if policy_id is None or item.policy_id==policy_id)
    def save_prebreakout_policy_selection(self, value):
        self._insert_immutable("INSERT INTO prebreakout_policy_selections (id,payload_json) VALUES (?,?)", (value.selection_id, _json(prebreakout_selection_to(value))), "Pre-Breakout policy selections are immutable and cannot be overwritten.")
    def get_prebreakout_policy_selection(self, selection_id):
        row=self._connection.execute("SELECT payload_json FROM prebreakout_policy_selections WHERE id=?",(selection_id,)).fetchone(); return prebreakout_selection_from(json.loads(row['payload_json'])) if row else None
    def list_prebreakout_policy_selections(self, policy_id=None, context=None):
        rows=self._connection.execute("SELECT payload_json FROM prebreakout_policy_selections ORDER BY id").fetchall(); values=tuple(prebreakout_selection_from(json.loads(row['payload_json'])) for row in rows)
        return tuple(item for item in values if (policy_id is None or item.policy_id==policy_id) and (context is None or item.selection_context==context))

    def save_prebreakout_setup_assessment(self, value: GovernedPreBreakoutSetupAssessment) -> None:
        self._insert_immutable(
            "INSERT INTO prebreakout_setup_assessments (id,payload_json) VALUES (?,?)",
            (value.assessment_id, _json(prebreakout_setup_assessment_to(value))),
            "Pre-Breakout setup assessments are immutable and cannot be overwritten.",
        )

    def get_prebreakout_setup_assessment(self, assessment_id: str) -> GovernedPreBreakoutSetupAssessment | None:
        row = self._connection.execute(
            "SELECT payload_json FROM prebreakout_setup_assessments WHERE id=?", (assessment_id,)
        ).fetchone()
        return prebreakout_setup_assessment_from(json.loads(row["payload_json"])) if row else None

    def list_prebreakout_setup_assessments(self, canonical_instrument_id=None, policy_fingerprint=None):
        query = "SELECT payload_json FROM prebreakout_setup_assessments"
        parameters: tuple[object, ...] = ()
        # Assessments are immutable payloads, but a current stored-only scan
        # must not deserialize every historical assessment merely to find an
        # exact instrument.  SQLite's JSON extraction is an exact field match,
        # not a fuzzy or substring identity lookup.
        if canonical_instrument_id is not None:
            query += " WHERE json_extract(payload_json, '$.assessment.fields.instrument_id') = ?"
            parameters = (canonical_instrument_id,)
        query += " ORDER BY id"
        rows = self._connection.execute(query, parameters).fetchall()
        values = tuple(prebreakout_setup_assessment_from(json.loads(row["payload_json"])) for row in rows)
        return tuple(sorted(
            (item for item in values if (canonical_instrument_id is None or item.instrument_id == canonical_instrument_id)
             and (policy_fingerprint is None or item.policy_fingerprint == policy_fingerprint)),
            key=lambda item: (item.evaluation_as_of, item.assessment_id),
        ))

    def save_reliability_decision(self, value: StoredReliabilityDecision) -> None:
        self._insert_immutable(
            "INSERT INTO reliability_decisions (id,payload_json) VALUES (?,?)",
            (value.decision_id, _json(reliability_decision_to(value))),
            "Reliability decisions are immutable and cannot be overwritten.",
        )

    def get_reliability_decision(self, decision_id: str) -> StoredReliabilityDecision | None:
        row = self._connection.execute(
            "SELECT payload_json FROM reliability_decisions WHERE id=?", (decision_id,)
        ).fetchone()
        return reliability_decision_from(json.loads(row["payload_json"])) if row else None

    def list_reliability_decisions(self, canonical_instrument_id=None, evidence_domain=None, outcome=None):
        rows = self._connection.execute("SELECT payload_json FROM reliability_decisions ORDER BY id").fetchall()
        values = tuple(reliability_decision_from(json.loads(row["payload_json"])) for row in rows)
        return tuple(sorted(
            (item for item in values if (canonical_instrument_id is None or item.canonical_instrument_id == canonical_instrument_id)
             and (evidence_domain is None or item.decision.family is evidence_domain)
             and (outcome is None or item.decision.availability.status is outcome)),
            key=lambda item: (item.evaluation_as_of, item.decision_id),
        ))

    def latest_reliability_decision_as_of(self, canonical_instrument_id, evidence_domain, as_of):
        values = tuple(item for item in self.list_reliability_decisions(canonical_instrument_id, evidence_domain)
                       if item.evaluation_as_of is not None and item.evaluation_as_of <= as_of)
        return max(values, key=lambda item: (item.evaluation_as_of, item.decision_id)) if values else None

    def save_brain_research_handoff(self, value: BrainResearchHandoff) -> None:
        self._insert_immutable(
            "INSERT INTO brain_research_handoffs (id,payload_json) VALUES (?,?)",
            (value.handoff_id, _json(brain_research_handoff_to(value))),
            "Brain research handoffs are immutable and cannot be overwritten.",
        )

    def get_brain_research_handoff(self, handoff_id: str) -> BrainResearchHandoff | None:
        row = self._connection.execute(
            "SELECT payload_json FROM brain_research_handoffs WHERE id=?", (handoff_id,)
        ).fetchone()
        return brain_research_handoff_from(json.loads(row["payload_json"])) if row else None

    def list_brain_research_handoffs(
        self,
        canonical_instrument_id: str | None = None,
        origin_type: BrainResearchOriginType | None = None,
        requested_brain_stage: BrainResearchStage | None = None,
        status: BrainResearchHandoffStatus | None = None,
    ) -> tuple[BrainResearchHandoff, ...]:
        if origin_type is not None and not isinstance(origin_type, BrainResearchOriginType):
            raise ValueError("BRAIN_RESEARCH_HANDOFF_ORIGIN_TYPE_INVALID")
        if requested_brain_stage is not None and not isinstance(requested_brain_stage, BrainResearchStage):
            raise ValueError("BRAIN_RESEARCH_HANDOFF_STAGE_INVALID")
        if status is not None and not isinstance(status, BrainResearchHandoffStatus):
            raise ValueError("BRAIN_RESEARCH_HANDOFF_STATUS_INVALID")
        rows = self._connection.execute("SELECT payload_json FROM brain_research_handoffs").fetchall()
        values = tuple(brain_research_handoff_from(json.loads(row["payload_json"])) for row in rows)
        filtered = (
            value for value in values
            if (canonical_instrument_id is None or value.canonical_instrument_id == canonical_instrument_id)
            and (origin_type is None or value.origin_type is origin_type)
            and (requested_brain_stage is None or value.requested_brain_stage is requested_brain_stage)
            and (status is None or value.research_status is status)
        )
        return tuple(sorted(filtered, key=lambda value: (value.evaluation_as_of, value.handoff_id)))

    def _self_improvement_save(self, table, identifier, value, message):
        self._insert_immutable(f"INSERT INTO {table} (id,payload_json) VALUES (?,?)", (identifier, _json(self_improvement_dump(value))), message)
    def _self_improvement_get(self, table, identifier, parser):
        row=self._connection.execute(f"SELECT payload_json FROM {table} WHERE id=?",(identifier,)).fetchone()
        return parser(json.loads(row['payload_json'])) if row else None
    def save_self_improvement_run(self, value):
        self._self_improvement_save("self_improvement_runs",value.run_id,value,"Self-improvement runs are immutable and cannot be overwritten.")
    def get_self_improvement_run(self, identifier):
        return self._self_improvement_get("self_improvement_runs",identifier,self_improvement_run_from)
    def save_self_improvement_observation(self, value):
        if self.get_self_improvement_run(value.run_id) is None: raise ValueError("Self-improvement observation requires its persisted run.")
        self._self_improvement_save("self_improvement_observations",value.observation_id,value,"Self-improvement observations are immutable and cannot be overwritten.")
    def get_self_improvement_observation(self, identifier):
        return self._self_improvement_get("self_improvement_observations",identifier,self_improvement_observation_from)
    def list_self_improvement_observations(self, run_id):
        rows=self._connection.execute("SELECT payload_json FROM self_improvement_observations").fetchall()
        return tuple(sorted((self_improvement_observation_from(json.loads(row['payload_json'])) for row in rows if json.loads(row['payload_json'])["run_id"]==run_id),key=lambda value:(value.occurred_at,value.observation_id)))
    def save_self_improvement_evidence_policy(self, value):
        self._self_improvement_save("self_improvement_evidence_policies",value.policy_id,value,"Self-improvement evidence policies are immutable and cannot be overwritten.")
    def get_self_improvement_evidence_policy(self, identifier):
        return self._self_improvement_get("self_improvement_evidence_policies",identifier,self_improvement_evidence_policy_from)
    def save_attribution_rule_set(self, value):
        self._self_improvement_save("attribution_rule_sets",value.rule_set_id,value,"Attribution rule sets are immutable and cannot be overwritten.")
    def get_attribution_rule_set(self, identifier):
        return self._self_improvement_get("attribution_rule_sets",identifier,attribution_rule_set_from)
    def save_strategy_error_attribution(self, value):
        if self.get_self_improvement_run(value.run_id) is None or self.get_self_improvement_observation(value.source_observation_id) is None: raise ValueError("Error attribution requires its persisted run and observation.")
        self._self_improvement_save("strategy_error_attributions",value.attribution_id,value,"Strategy error attributions are immutable and cannot be overwritten.")
    def get_strategy_error_attribution(self, identifier):
        return self._self_improvement_get("strategy_error_attributions",identifier,strategy_error_attribution_from)
    def list_strategy_error_attributions(self, run_id):
        rows=self._connection.execute("SELECT payload_json FROM strategy_error_attributions").fetchall()
        return tuple(sorted((strategy_error_attribution_from(json.loads(row['payload_json'])) for row in rows if json.loads(row['payload_json'])["run_id"]==run_id),key=lambda value:value.attribution_id))
    def save_strategy_success_attribution(self, value):
        if self.get_self_improvement_run(value.run_id) is None or self.get_self_improvement_observation(value.source_observation_id) is None: raise ValueError("Success attribution requires its persisted run and observation.")
        self._self_improvement_save("strategy_success_attributions",value.attribution_id,value,"Strategy success attributions are immutable and cannot be overwritten.")
    def get_strategy_success_attribution(self, identifier):
        return self._self_improvement_get("strategy_success_attributions",identifier,strategy_success_attribution_from)
    def list_strategy_success_attributions(self, run_id):
        rows=self._connection.execute("SELECT payload_json FROM strategy_success_attributions").fetchall()
        return tuple(sorted((strategy_success_attribution_from(json.loads(row['payload_json'])) for row in rows if json.loads(row['payload_json'])["run_id"]==run_id),key=lambda value:value.attribution_id))
    def save_recurring_strategy_pattern(self, value):
        if self.get_self_improvement_run(value.run_id) is None: raise ValueError("Recurring pattern requires its persisted run.")
        self._self_improvement_save("recurring_strategy_patterns",value.pattern_id,value,"Recurring strategy patterns are immutable and cannot be overwritten.")
    def get_recurring_strategy_pattern(self, identifier):
        return self._self_improvement_get("recurring_strategy_patterns",identifier,recurring_strategy_pattern_from)
    def list_recurring_strategy_patterns(self, run_id):
        rows=self._connection.execute("SELECT payload_json FROM recurring_strategy_patterns").fetchall()
        return tuple(sorted((recurring_strategy_pattern_from(json.loads(row['payload_json'])) for row in rows if json.loads(row['payload_json'])["run_id"]==run_id),key=lambda value:value.pattern_id))
    def save_strategy_error_summary(self, value):
        if self.get_self_improvement_run(value.run_id) is None: raise ValueError("Error summary requires its persisted run.")
        self._self_improvement_save("strategy_error_summaries",value.summary_id,value,"Strategy error summaries are immutable and cannot be overwritten.")
    def get_strategy_error_summary(self, identifier):
        return self._self_improvement_get("strategy_error_summaries",identifier,strategy_error_summary_from)
    def list_strategy_error_summaries(self, run_id):
        rows=self._connection.execute("SELECT payload_json FROM strategy_error_summaries").fetchall()
        return tuple(sorted((strategy_error_summary_from(json.loads(row['payload_json'])) for row in rows if json.loads(row['payload_json'])["run_id"]==run_id),key=lambda value:value.summary_id))
    def save_strategy_success_summary(self, value):
        if self.get_self_improvement_run(value.run_id) is None: raise ValueError("Success summary requires its persisted run.")
        self._self_improvement_save("strategy_success_summaries",value.summary_id,value,"Strategy success summaries are immutable and cannot be overwritten.")
    def get_strategy_success_summary(self, identifier):
        return self._self_improvement_get("strategy_success_summaries",identifier,strategy_success_summary_from)
    def list_strategy_success_summaries(self, run_id):
        rows=self._connection.execute("SELECT payload_json FROM strategy_success_summaries").fetchall()
        return tuple(sorted((strategy_success_summary_from(json.loads(row['payload_json'])) for row in rows if json.loads(row['payload_json'])["run_id"]==run_id),key=lambda value:value.summary_id))
    def save_improvement_hypothesis(self, value):
        if self.get_self_improvement_run(value.run_id) is None: raise ValueError("Improvement hypothesis requires its persisted run.")
        for attribution_id in value.source_attribution_ids:
            if self.get_strategy_error_attribution(attribution_id) is None and self.get_strategy_success_attribution(attribution_id) is None: raise ValueError("Improvement hypothesis requires persisted source attributions.")
        self._self_improvement_save("improvement_hypotheses",value.hypothesis_id,value,"Improvement hypotheses are immutable and cannot be overwritten.")
    def get_improvement_hypothesis(self, identifier):
        return self._self_improvement_get("improvement_hypotheses",identifier,improvement_hypothesis_from)
    def save_hypothesis_ranking_policy(self, value):
        self._self_improvement_save("hypothesis_ranking_policies",value.policy_id,value,"Hypothesis ranking policies are immutable and cannot be overwritten.")
    def get_hypothesis_ranking_policy(self, identifier):
        return self._self_improvement_get("hypothesis_ranking_policies",identifier,hypothesis_ranking_policy_from)
    def save_hypothesis_proposal_budget(self, value):
        self._self_improvement_save("hypothesis_proposal_budgets",value.budget_id,value,"Hypothesis proposal budgets are immutable and cannot be overwritten.")
    def get_hypothesis_proposal_budget(self, identifier):
        return self._self_improvement_get("hypothesis_proposal_budgets",identifier,hypothesis_proposal_budget_from)
    def save_hypothesis_generation_policy(self, value):
        self._self_improvement_save("hypothesis_generation_policies",value.policy_id,value,"Hypothesis generation policies are immutable and cannot be overwritten.")
    def get_hypothesis_generation_policy(self, identifier):
        return self._self_improvement_get("hypothesis_generation_policies",identifier,hypothesis_generation_policy_from)
    def save_strategy_improvement_hypothesis(self, value):
        if self.get_self_improvement_run(value.run_id) is None or self.get_approved_strategy_version(value.target_approved_strategy_id) is None or self.get_hypothesis_generation_policy(value.generation_policy_id) is None: raise ValueError("Improvement hypothesis requires persisted frozen run, approved target, and generation policy.")
        self._self_improvement_save("strategy_improvement_hypotheses",value.hypothesis_id,value,"Strategy improvement hypotheses are immutable and cannot be overwritten.")
    def get_strategy_improvement_hypothesis(self, identifier):
        return self._self_improvement_get("strategy_improvement_hypotheses",identifier,strategy_hypothesis_from)
    def list_strategy_improvement_hypotheses(self, run_id):
        rows=self._connection.execute("SELECT payload_json FROM strategy_improvement_hypotheses").fetchall()
        return tuple(sorted((strategy_hypothesis_from(json.loads(row['payload_json'])) for row in rows if json.loads(row['payload_json'])["run_id"]==run_id),key=lambda value:value.hypothesis_id))
    def save_strategy_hypothesis_ranking(self, value):
        if self.get_self_improvement_run(value.run_id) is None or any(self.get_strategy_improvement_hypothesis(identifier) is None for identifier in value.ordered_hypothesis_ids): raise ValueError("Hypothesis ranking requires persisted frozen run and hypotheses.")
        self._self_improvement_save("strategy_hypothesis_rankings",value.ranking_id,value,"Hypothesis rankings are immutable and cannot be overwritten.")
    def get_strategy_hypothesis_ranking(self, identifier):
        return self._self_improvement_get("strategy_hypothesis_rankings",identifier,strategy_hypothesis_ranking_from)
    def save_hypothesis_review(self, value):
        hypothesis=self.get_strategy_improvement_hypothesis(value.hypothesis_id)
        if hypothesis is None: raise ValueError("Hypothesis review requires a persisted hypothesis.")
        if not value.reviewer_id.startswith("human:"): raise ValueError("Hypothesis review requires an explicitly attested human reviewer.")
        if value.reviewed_at<hypothesis.created_at or value.evidence_fingerprint!=hypothesis.evidence_fingerprint or value.fingerprint!=hypothesis_review_fingerprint(value): raise ValueError("Hypothesis review must reference exact frozen evidence with an intact human-review fingerprint.")
        self._self_improvement_save("hypothesis_reviews",value.review_id,value,"Hypothesis reviews are immutable and cannot be overwritten.")
    def get_hypothesis_review(self, identifier):
        return self._self_improvement_get("hypothesis_reviews",identifier,hypothesis_review_from)
    def save_hypothesis_experiment_link(self, value):
        if self.get_strategy_improvement_hypothesis(value.hypothesis_id) is None or self.get_hypothesis_review(value.review_id) is None or self.get_strategy_experiment(value.experiment_id) is None or self.get_strategy_candidate(value.baseline_candidate_id) is None or self.get_experiment_budget(value.experiment_budget_id) is None: raise ValueError("Hypothesis experiment link requires persisted frozen research and experiment records.")
        if any(delta_id not in {item.delta_id for item in self.list_strategy_candidate_deltas(value.experiment_id)} for delta_id in value.candidate_delta_ids): raise ValueError("Hypothesis experiment link references a missing candidate delta.")
        self._self_improvement_save("hypothesis_experiment_links",value.link_id,value,"Hypothesis experiment links are immutable and cannot be overwritten.")
    def get_hypothesis_experiment_link(self, identifier):
        return self._self_improvement_get("hypothesis_experiment_links",identifier,hypothesis_experiment_link_from)
    def save_automated_research_run(self, value):
        if self.get_strategy_experiment(value.experiment_id) is None or self.get_hypothesis_experiment_link(value.hypothesis_experiment_link_id) is None or self.get_experiment_budget(value.experiment_budget_id) is None or self.get_candidate_selection_policy(value.candidate_selection_policy_id) is None: raise ValueError("Automated research run requires persisted frozen experiment, bridge link, budget, and selection policy.")
        self._self_improvement_save("automated_research_runs",value.research_run_id,value,"Automated research runs are immutable and cannot be overwritten.")
    def get_automated_research_run(self, identifier):
        return self._self_improvement_get("automated_research_runs",identifier,automated_research_run_from)
    def list_automated_research_runs(self):
        rows=self._connection.execute("SELECT payload_json FROM automated_research_runs ORDER BY id").fetchall(); return tuple(automated_research_run_from(json.loads(row['payload_json'])) for row in rows)
    def save_future_oos_candidate_queue_entry(self, value):
        selection=self.get_candidate_selection_result(value.selection_id)
        if selection is None or selection.selected_candidate_id!=value.selected_candidate_id or value.earliest_test_timestamp<=value.selection_timestamp: raise ValueError("Future OOS queue requires a selected frozen candidate strictly before its future TEST boundary.")
        self._self_improvement_save("future_oos_candidate_queue_entries",value.queue_id,value,"Future OOS queue entries are immutable and cannot be overwritten.")
    def get_future_oos_candidate_queue_entry(self, identifier):
        return self._self_improvement_get("future_oos_candidate_queue_entries",identifier,future_oos_queue_from)
    def save_automated_research_cycle_result(self, value):
        if self.get_automated_research_run(value.research_run_id) is None or self.get_candidate_selection_result(value.selection_id) is None: raise ValueError("Automated research cycle requires persisted frozen run and selection.")
        self._self_improvement_save("automated_research_cycle_results",value.cycle_result_id,value,"Automated research cycle results are immutable and cannot be overwritten.")
    def get_automated_research_cycle_result(self, identifier):
        return self._self_improvement_get("automated_research_cycle_results",identifier,automated_research_cycle_from)
    def save_future_oos_assignment_policy(self,value):
        if value.minimum_lead_seconds<0 or value.maximum_concurrent_assignments<1 or value.expiration_seconds is not None and value.expiration_seconds<0 or value.fingerprint!=future_oos_assignment_policy_fingerprint(value): raise ValueError("Future OOS assignment policy is invalid or has an incorrect frozen fingerprint.")
        self._self_improvement_save("future_oos_assignment_policies",value.policy_id,value,"Future OOS assignment policies are immutable and cannot be overwritten.")
    def get_future_oos_assignment_policy(self,identifier): return self._self_improvement_get("future_oos_assignment_policies",identifier,future_oos_assignment_policy_from)
    def save_future_oos_assignment(self,value):
        queue=self.get_future_oos_candidate_queue_entry(value.queue_id); policy=self.get_future_oos_assignment_policy(value.policy_id); candidate=self.get_strategy_candidate(value.selected_candidate_id); selection=self.get_candidate_selection_result(value.selection_id)
        if queue is None or policy is None or candidate is None or selection is None or queue.status.value!="QUEUED" or value.status.value!="ASSIGNED" or queue.selection_id!=value.selection_id or queue.selected_candidate_id!=value.selected_candidate_id or selection.selected_candidate_id!=value.selected_candidate_id or value.selected_candidate_id not in selection.candidate_ids or selection.selection_timestamp!=queue.selection_timestamp or queue.candidate_fingerprint!=value.candidate_fingerprint or candidate.fingerprint!=value.candidate_fingerprint or policy.version!=value.policy_version or value.fingerprint!=future_oos_assignment_fingerprint(value): raise ValueError("Future OOS assignment must retain exact frozen queue, candidate, policy, and fingerprint references.")
        if value.test_end<=value.test_start or value.assigned_at>=value.test_start or queue.selection_timestamp>=value.test_start or value.test_start<queue.earliest_test_timestamp or value.test_start-value.assigned_at<timedelta(seconds=policy.minimum_lead_seconds): raise ValueError("Future OOS assignment violates the strict pre-TEST chronology or lead-time policy.")
        if policy.allowed_plan_ids and value.plan_id not in policy.allowed_plan_ids or value.plan_id!=queue.target_plan_id: raise ValueError("Future OOS assignment does not match its permitted frozen plan.")
        if policy.expiration_seconds is not None and value.assigned_at>queue.selection_timestamp+timedelta(seconds=policy.expiration_seconds): raise ValueError("Future OOS assignment queue has expired and must be reselected.")
        assignments=tuple(future_oos_assignment_from(json.loads(row['payload_json'])) for row in self._connection.execute("SELECT payload_json FROM future_oos_assignments").fetchall()); completed_assignment_ids={future_oos_execution_from(json.loads(row['payload_json'])).assignment_id for row in self._connection.execute("SELECT payload_json FROM future_oos_execution_results").fetchall()}; active=tuple(item for item in assignments if item.status.value in {"ASSIGNED","EXECUTING"} and item.assignment_id not in completed_assignment_ids)
        if len(active)>=policy.maximum_concurrent_assignments: raise ValueError("Future OOS assignment policy maximum concurrent assignments has been reached.")
        if any(item.queue_id==value.queue_id and item.window_id==value.window_id or not policy.allow_multiple_windows and item.selected_candidate_id==value.selected_candidate_id for item in active): raise ValueError("Future OOS assignment already has an immutable active assignment path.")
        self._self_improvement_save("future_oos_assignments",value.assignment_id,value,"Future OOS assignments are immutable and cannot be overwritten.")
    def get_future_oos_assignment(self,identifier): return self._self_improvement_get("future_oos_assignments",identifier,future_oos_assignment_from)
    def list_future_oos_assignments(self,selection_id):
        rows=self._connection.execute("SELECT payload_json FROM future_oos_assignments ORDER BY id").fetchall(); return tuple(sorted((value for value in (future_oos_assignment_from(json.loads(row['payload_json'])) for row in rows) if value.selection_id==selection_id),key=lambda value:(value.test_start,value.assignment_id)))
    def save_future_oos_execution_result(self,value):
        assignment=self.get_future_oos_assignment(value.assignment_id); window_result=self.get_walk_forward_window_result(value.walk_forward_window_result_id)
        if assignment is None or window_result is None or value.test_backtest_run_id!=window_result.test_backtest_run_id or value.performance_report_id!=window_result.performance_report_id or value.benchmark_comparison_id!=window_result.benchmark_comparison_id or value.fingerprint!=future_oos_execution_fingerprint(value): raise ValueError("Future OOS execution result must retain exact assignment and canonical window-result references.")
        self._self_improvement_save("future_oos_execution_results",value.execution_result_id,value,"Future OOS execution results are immutable and cannot be overwritten.")
    def get_future_oos_execution_result(self,identifier): return self._self_improvement_get("future_oos_execution_results",identifier,future_oos_execution_from)
    def list_future_oos_execution_results(self,selection_id):
        assignments={value.assignment_id for value in self.list_future_oos_assignments(selection_id)}; rows=self._connection.execute("SELECT payload_json FROM future_oos_execution_results ORDER BY id").fetchall(); return tuple(sorted((value for value in (future_oos_execution_from(json.loads(row['payload_json'])) for row in rows) if value.assignment_id in assignments),key=lambda value:(value.executed_at,value.execution_result_id)))
    def save_research_candidate_oos_record(self,value):
        candidate=self.get_strategy_candidate(value.selected_candidate_id)
        if self.get_candidate_selection_result(value.selection_id) is None or candidate is None or candidate.fingerprint!=value.candidate_fingerprint or any(self.get_future_oos_assignment(identifier) is None for identifier in value.assignment_ids) or any(self.get_future_oos_execution_result(identifier) is None for identifier in value.execution_result_ids) or any(self.get_walk_forward_window_result(identifier) is None for identifier in value.window_result_ids): raise ValueError("Research-candidate OOS record requires persisted frozen selection, candidate, assignments, executions, and window results.")
        self._self_improvement_save("research_candidate_oos_records",value.record_id,value,"Research candidate OOS records are immutable and cannot be overwritten.")
    def get_research_candidate_oos_record(self,identifier): return self._self_improvement_get("research_candidate_oos_records",identifier,research_candidate_oos_from)
    def save_promotion_evidence_package(self,value):
        candidate=self.get_strategy_candidate(value.selected_candidate_id); baseline=self.get_strategy_candidate(value.baseline_candidate_id)
        if self.get_self_improvement_run(value.source_self_improvement_run_id) is None or self.get_strategy_improvement_hypothesis(value.hypothesis_id) is None or self.get_hypothesis_review(value.hypothesis_review_id) is None or self.get_hypothesis_experiment_link(value.hypothesis_experiment_link_id) is None or self.get_strategy_experiment(value.experiment_id) is None or self.get_automated_research_run(value.automated_research_run_id) is None or self.get_candidate_selection_result(value.selection_id) is None or candidate is None or baseline is None or candidate.fingerprint!=value.candidate_fingerprint or baseline.fingerprint!=value.baseline_candidate_fingerprint or any(self.get_future_oos_candidate_queue_entry(identifier) is None for identifier in value.queue_ids) or any(self.get_future_oos_assignment(identifier) is None for identifier in value.assignment_ids) or any(self.get_future_oos_execution_result(identifier) is None for identifier in value.execution_result_ids) or any(self.get_walk_forward_window_result(identifier) is None for identifier in value.window_result_ids) or any(self.get_candidate_robustness_result(identifier) is None for identifier in value.robustness_result_ids) or value.fingerprint!=promotion_evidence_package_fingerprint(value): raise ValueError("Promotion evidence package requires only exact persisted frozen research and OOS evidence.")
        self._self_improvement_save("promotion_evidence_packages",value.package_id,value,"Promotion evidence packages are immutable and cannot be overwritten.")
    def get_promotion_evidence_package(self,identifier): return self._self_improvement_get("promotion_evidence_packages",identifier,promotion_evidence_package_from)

    def save_gate_decision(self, decision: GateDecision) -> None:
        self._require_historical_context(decision.strategy_version, decision.as_of_timestamp)
        self._insert_immutable(
            """INSERT INTO gate_decisions
               (id, gate_name, strategy_id, version, outcome, rationale, evidence_ids_json,
                parameters_json, evaluated_at, as_of_timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (decision.id, decision.gate_name, decision.strategy_version.strategy_id,
             decision.strategy_version.version, decision.outcome.value, decision.rationale,
             _json(list(decision.evidence_ids)), _json(decision.parameters_used),
             _timestamp(decision.evaluated_at), _timestamp(decision.as_of_timestamp)),
            "Gate decisions are immutable and cannot be overwritten.",
        )

    def list_gate_decisions(self, reference: StrategyVersionReference, as_of_timestamp: datetime) -> tuple[GateDecision, ...]:
        rows = self._connection.execute(
            """SELECT * FROM gate_decisions WHERE strategy_id = ? AND version = ? AND as_of_timestamp = ?
               ORDER BY id""",
            (reference.strategy_id, reference.version, _timestamp(as_of_timestamp)),
        ).fetchall()
        return tuple(self._gate_from_row(row) for row in rows)

    def _require_historical_context(self, reference: StrategyVersionReference | None, as_of_timestamp: datetime | None) -> None:
        if reference is None or self.get_strategy_definition(reference) is None:
            raise ValueError("Historical analytical records require an existing strategy version.")
        if as_of_timestamp is None:
            raise ValueError("Historical analytical records require an as-of timestamp.")

    def _insert_immutable(self, statement: str, values: tuple[Any, ...], error_message: str) -> None:
        try:
            self._connection.execute(statement, values)
            self._connection.commit()
        except sqlite3.IntegrityError as error:
            raise ValueError(error_message) from error

    def _create_governance_schema(self) -> None:
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS strategy_versions (
                strategy_id TEXT NOT NULL, version TEXT NOT NULL, name TEXT NOT NULL, initial_status TEXT NOT NULL,
                created_at TEXT NOT NULL, effective_from TEXT, effective_to TEXT, description TEXT NOT NULL,
                configuration_json TEXT NOT NULL, rule_definition_version TEXT NOT NULL,
                scoring_configuration_version TEXT NOT NULL, execution_gate_configuration_version TEXT NOT NULL,
                risk_configuration_version TEXT NOT NULL, benchmark_configuration_version TEXT NOT NULL,
                author_reviewer_json TEXT NOT NULL, initial_approval_status TEXT NOT NULL,
                initial_validation_status TEXT NOT NULL, parent_strategy_id TEXT, parent_version TEXT,
                PRIMARY KEY (strategy_id, version)
            );
            CREATE TABLE IF NOT EXISTS strategy_lifecycle_events (
                id TEXT PRIMARY KEY, strategy_id TEXT NOT NULL, version TEXT NOT NULL, status TEXT NOT NULL,
                approval_status TEXT NOT NULL, validation_status TEXT NOT NULL, occurred_at TEXT NOT NULL,
                actor_id TEXT NOT NULL, rationale TEXT NOT NULL,
                FOREIGN KEY (strategy_id, version) REFERENCES strategy_versions(strategy_id, version)
            );
            CREATE TABLE IF NOT EXISTS evidence_records (
                id TEXT PRIMARY KEY, source TEXT NOT NULL, source_identifier TEXT, timestamp TEXT NOT NULL,
                observation_ids_json TEXT NOT NULL, evidence_type TEXT NOT NULL,
                factual_content_reference TEXT NOT NULL, confidence REAL, provenance_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS diagnostic_results (
                id TEXT PRIMARY KEY, instrument_id TEXT NOT NULL, rule_id TEXT NOT NULL,
                strategy_id TEXT NOT NULL, version TEXT NOT NULL, result TEXT NOT NULL, score REAL, confidence REAL,
                evidence_ids_json TEXT NOT NULL, input_observation_ids_json TEXT NOT NULL,
                evaluated_at TEXT NOT NULL, as_of_timestamp TEXT NOT NULL,
                FOREIGN KEY (strategy_id, version) REFERENCES strategy_versions(strategy_id, version)
            );
            CREATE TABLE IF NOT EXISTS scorecards (
                id TEXT PRIMARY KEY, instrument_id TEXT NOT NULL, strategy_id TEXT NOT NULL, version TEXT NOT NULL,
                evaluated_at TEXT NOT NULL, as_of_timestamp TEXT NOT NULL, components_json TEXT NOT NULL,
                aggregate_score REAL, FOREIGN KEY (strategy_id, version) REFERENCES strategy_versions(strategy_id, version)
            );
            CREATE TABLE IF NOT EXISTS gate_decisions (
                id TEXT PRIMARY KEY, gate_name TEXT NOT NULL, strategy_id TEXT NOT NULL, version TEXT NOT NULL,
                outcome TEXT NOT NULL, rationale TEXT NOT NULL, evidence_ids_json TEXT NOT NULL,
                parameters_json TEXT NOT NULL, evaluated_at TEXT NOT NULL, as_of_timestamp TEXT NOT NULL,
                FOREIGN KEY (strategy_id, version) REFERENCES strategy_versions(strategy_id, version)
            );
            CREATE TABLE IF NOT EXISTS decision_scorecards (
                id TEXT PRIMARY KEY, instrument_id TEXT NOT NULL, strategy_id TEXT NOT NULL, version TEXT NOT NULL,
                registry_version TEXT NOT NULL, configuration_version TEXT NOT NULL, as_of_timestamp TEXT NOT NULL,
                evaluated_at TEXT NOT NULL, final_score TEXT, score_status TEXT NOT NULL, data_confidence REAL,
                warnings_json TEXT NOT NULL, components_json TEXT NOT NULL,
                FOREIGN KEY (strategy_id, version) REFERENCES strategy_versions(strategy_id, version)
            );
            CREATE TABLE IF NOT EXISTS execution_gate_evaluations (
                id TEXT PRIMARY KEY, instrument_id TEXT NOT NULL, strategy_id TEXT NOT NULL, version TEXT NOT NULL,
                scorecard_id TEXT NOT NULL, as_of_timestamp TEXT NOT NULL, evaluated_at TEXT NOT NULL, payload_json TEXT NOT NULL,
                FOREIGN KEY (strategy_id, version) REFERENCES strategy_versions(strategy_id, version),
                FOREIGN KEY (scorecard_id) REFERENCES decision_scorecards(id)
            );
            CREATE TABLE IF NOT EXISTS execution_gate_decisions (
                evaluation_id TEXT NOT NULL, gate_id TEXT NOT NULL, outcome TEXT NOT NULL, detail TEXT NOT NULL,
                confidence REAL, evidence_ids_json TEXT NOT NULL, parameters_json TEXT NOT NULL,
                PRIMARY KEY (evaluation_id, gate_id),
                FOREIGN KEY (evaluation_id) REFERENCES execution_gate_evaluations(id)
            );
            CREATE TABLE IF NOT EXISTS portfolios (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS portfolio_transactions (
                id TEXT PRIMARY KEY, portfolio_id TEXT NOT NULL, effective_at TEXT NOT NULL, known_at TEXT NOT NULL, payload_json TEXT NOT NULL,
                FOREIGN KEY (portfolio_id) REFERENCES portfolios(id)
            );
            CREATE TABLE IF NOT EXISTS portfolio_corporate_actions (
                id TEXT PRIMARY KEY, portfolio_id TEXT NOT NULL, effective_at TEXT NOT NULL, known_at TEXT NOT NULL, payload_json TEXT NOT NULL,
                FOREIGN KEY (portfolio_id) REFERENCES portfolios(id)
            );
            CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                id TEXT PRIMARY KEY, portfolio_id TEXT NOT NULL, as_of_timestamp TEXT NOT NULL, payload_json TEXT NOT NULL,
                FOREIGN KEY (portfolio_id) REFERENCES portfolios(id)
            );
            CREATE TABLE IF NOT EXISTS portfolio_rotation_evaluations (
                id TEXT PRIMARY KEY, portfolio_snapshot_id TEXT NOT NULL, as_of_timestamp TEXT NOT NULL, payload_json TEXT NOT NULL,
                FOREIGN KEY (portfolio_snapshot_id) REFERENCES portfolio_snapshots(id)
            );
            CREATE TABLE IF NOT EXISTS rotation_comparisons (
                evaluation_id TEXT NOT NULL, holding_instrument_id TEXT, candidate_instrument_id TEXT NOT NULL, payload_json TEXT NOT NULL,
                PRIMARY KEY (evaluation_id, holding_instrument_id, candidate_instrument_id),
                FOREIGN KEY (evaluation_id) REFERENCES portfolio_rotation_evaluations(id)
            );
            CREATE TABLE IF NOT EXISTS trade_plans (id TEXT PRIMARY KEY, payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS signal_trigger_conditions (
                plan_id TEXT NOT NULL, id TEXT NOT NULL, payload_json TEXT NOT NULL, PRIMARY KEY (plan_id,id),
                FOREIGN KEY (plan_id) REFERENCES trade_plans(id)
            );
            CREATE TABLE IF NOT EXISTS signals (
                id TEXT PRIMARY KEY, portfolio_snapshot_id TEXT, as_of_timestamp TEXT NOT NULL, payload_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS signal_lifecycle_events (
                id TEXT PRIMARY KEY, signal_id TEXT NOT NULL, as_of_timestamp TEXT NOT NULL, payload_json TEXT NOT NULL,
                FOREIGN KEY (signal_id) REFERENCES signals(id)
            );
            CREATE TABLE IF NOT EXISTS paper_trades (id TEXT PRIMARY KEY, signal_id TEXT NOT NULL, as_of_timestamp TEXT NOT NULL, payload_json TEXT NOT NULL, FOREIGN KEY (signal_id) REFERENCES signals(id));
            CREATE TABLE IF NOT EXISTS paper_fills (id TEXT PRIMARY KEY, paper_trade_id TEXT NOT NULL, payload_json TEXT NOT NULL, FOREIGN KEY (paper_trade_id) REFERENCES paper_trades(id));
            CREATE TABLE IF NOT EXISTS paper_lifecycle_events (id TEXT PRIMARY KEY, paper_trade_id TEXT NOT NULL, payload_json TEXT NOT NULL, FOREIGN KEY (paper_trade_id) REFERENCES paper_trades(id));
            CREATE TABLE IF NOT EXISTS paper_outcomes (paper_trade_id TEXT PRIMARY KEY, payload_json TEXT NOT NULL, FOREIGN KEY (paper_trade_id) REFERENCES paper_trades(id));
            CREATE TABLE IF NOT EXISTS performance_datasets (id TEXT PRIMARY KEY,end_timestamp TEXT NOT NULL,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS performance_reports (id TEXT PRIMARY KEY,dataset_id TEXT NOT NULL,end_timestamp TEXT NOT NULL,payload_json TEXT NOT NULL,FOREIGN KEY(dataset_id) REFERENCES performance_datasets(id));
            CREATE TABLE IF NOT EXISTS performance_equity_points (report_id TEXT NOT NULL,timestamp TEXT NOT NULL,trade_id TEXT NOT NULL,payload_json TEXT NOT NULL,PRIMARY KEY(report_id,timestamp,trade_id),FOREIGN KEY(report_id) REFERENCES performance_reports(id));
            CREATE TABLE IF NOT EXISTS benchmark_runs (id TEXT PRIMARY KEY,report_id TEXT NOT NULL,window_end TEXT NOT NULL,input_ids_json TEXT NOT NULL,methodology_version TEXT NOT NULL,payload_json TEXT NOT NULL,FOREIGN KEY(report_id) REFERENCES performance_reports(id));
            CREATE TABLE IF NOT EXISTS benchmark_comparisons (id TEXT PRIMARY KEY,report_id TEXT NOT NULL,payload_json TEXT NOT NULL,FOREIGN KEY(report_id) REFERENCES performance_reports(id));
            CREATE TABLE IF NOT EXISTS historical_manifests (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS historical_partitions (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS historical_memberships (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS replay_schedules (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS backtest_data_gap_policies (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS backtest_runs (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS backtest_replay_steps (id TEXT PRIMARY KEY,run_id TEXT NOT NULL,step_number INTEGER NOT NULL,payload_json TEXT NOT NULL,UNIQUE(run_id,step_number),FOREIGN KEY(run_id) REFERENCES backtest_runs(id));
            CREATE TABLE IF NOT EXISTS backtest_events (id TEXT PRIMARY KEY,run_id TEXT NOT NULL,sequence_number INTEGER NOT NULL,step_number INTEGER NOT NULL,event_timestamp TEXT NOT NULL,payload_json TEXT NOT NULL,UNIQUE(run_id,sequence_number),FOREIGN KEY(run_id) REFERENCES backtest_runs(id));
            CREATE TABLE IF NOT EXISTS historical_analytical_snapshots (id TEXT PRIMARY KEY,run_id TEXT NOT NULL,payload_json TEXT NOT NULL,FOREIGN KEY(run_id) REFERENCES backtest_runs(id));
            CREATE TABLE IF NOT EXISTS historical_analytical_evaluations (id TEXT PRIMARY KEY,run_id TEXT NOT NULL,step_number INTEGER NOT NULL,payload_json TEXT NOT NULL,FOREIGN KEY(run_id) REFERENCES backtest_runs(id));
            CREATE TABLE IF NOT EXISTS backtest_portfolio_ledger_events (id TEXT PRIMARY KEY,run_id TEXT NOT NULL,effective_at TEXT NOT NULL,known_at TEXT NOT NULL,payload_json TEXT NOT NULL,FOREIGN KEY(run_id) REFERENCES backtest_runs(id));
            CREATE TABLE IF NOT EXISTS backtest_portfolio_states (id TEXT PRIMARY KEY,run_id TEXT NOT NULL,step_number INTEGER NOT NULL,payload_json TEXT NOT NULL,FOREIGN KEY(run_id) REFERENCES backtest_runs(id));
            CREATE TABLE IF NOT EXISTS historical_holding_gate_contexts (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS historical_portfolio_gate_evaluations (id TEXT PRIMARY KEY,run_id TEXT NOT NULL,payload_json TEXT NOT NULL,FOREIGN KEY(run_id) REFERENCES backtest_runs(id));
            CREATE TABLE IF NOT EXISTS historical_rotation_candidate_contexts (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS historical_rotation_history (id TEXT PRIMARY KEY,run_id TEXT NOT NULL,payload_json TEXT NOT NULL,FOREIGN KEY(run_id) REFERENCES backtest_runs(id));
            CREATE TABLE IF NOT EXISTS historical_rotation_evaluations (id TEXT PRIMARY KEY,run_id TEXT NOT NULL,payload_json TEXT NOT NULL,FOREIGN KEY(run_id) REFERENCES backtest_runs(id));
            CREATE TABLE IF NOT EXISTS historical_signal_replay_references (id TEXT PRIMARY KEY,run_id TEXT NOT NULL,payload_json TEXT NOT NULL,FOREIGN KEY(run_id) REFERENCES backtest_runs(id));
            CREATE TABLE IF NOT EXISTS historical_paper_replay_references (id TEXT PRIMARY KEY,run_id TEXT NOT NULL,payload_json TEXT NOT NULL,FOREIGN KEY(run_id) REFERENCES backtest_runs(id));
            CREATE TABLE IF NOT EXISTS historical_trigger_timing_contexts (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS historical_execution_timing_contexts (id TEXT PRIMARY KEY,run_id TEXT NOT NULL,payload_json TEXT NOT NULL,FOREIGN KEY(run_id) REFERENCES backtest_runs(id));
            CREATE TABLE IF NOT EXISTS historical_capital_allocations (id TEXT PRIMARY KEY,run_id TEXT NOT NULL,payload_json TEXT NOT NULL,FOREIGN KEY(run_id) REFERENCES backtest_runs(id));
            CREATE TABLE IF NOT EXISTS historical_paper_ledger_links (id TEXT PRIMARY KEY,run_id TEXT NOT NULL,payload_json TEXT NOT NULL,FOREIGN KEY(run_id) REFERENCES backtest_runs(id));
            CREATE TABLE IF NOT EXISTS historical_equity_points (id TEXT PRIMARY KEY,run_id TEXT NOT NULL,payload_json TEXT NOT NULL,FOREIGN KEY(run_id) REFERENCES backtest_runs(id));
            CREATE TABLE IF NOT EXISTS historical_equity_series (id TEXT PRIMARY KEY,run_id TEXT NOT NULL,payload_json TEXT NOT NULL,FOREIGN KEY(run_id) REFERENCES backtest_runs(id));
            CREATE TABLE IF NOT EXISTS signal_config_snapshots (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS paper_config_snapshots (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS walk_forward_plans (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS strategy_candidates (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS walk_forward_windows (id TEXT PRIMARY KEY,plan_id TEXT NOT NULL,ordinal INTEGER NOT NULL,payload_json TEXT NOT NULL,UNIQUE(plan_id,ordinal),FOREIGN KEY(plan_id) REFERENCES walk_forward_plans(id));
            CREATE TABLE IF NOT EXISTS walk_forward_runs (id TEXT PRIMARY KEY,plan_id TEXT NOT NULL,payload_json TEXT NOT NULL,FOREIGN KEY(plan_id) REFERENCES walk_forward_plans(id));
            CREATE TABLE IF NOT EXISTS walk_forward_window_results (id TEXT PRIMARY KEY,run_id TEXT NOT NULL,window_id TEXT NOT NULL,payload_json TEXT NOT NULL,UNIQUE(run_id,window_id),FOREIGN KEY(run_id) REFERENCES walk_forward_runs(id),FOREIGN KEY(window_id) REFERENCES walk_forward_windows(id));
            CREATE TABLE IF NOT EXISTS walk_forward_validation_configs (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS oos_stitched_equity_observations (id TEXT PRIMARY KEY,run_id TEXT NOT NULL,timestamp TEXT NOT NULL,payload_json TEXT NOT NULL,FOREIGN KEY(run_id) REFERENCES walk_forward_runs(id));
            CREATE TABLE IF NOT EXISTS walk_forward_oos_equity_series (id TEXT PRIMARY KEY,run_id TEXT NOT NULL,payload_json TEXT NOT NULL,FOREIGN KEY(run_id) REFERENCES walk_forward_runs(id));
            CREATE TABLE IF NOT EXISTS validation_degradation_analyses (id TEXT PRIMARY KEY,run_id TEXT NOT NULL,payload_json TEXT NOT NULL,FOREIGN KEY(run_id) REFERENCES walk_forward_runs(id));
            CREATE TABLE IF NOT EXISTS walk_forward_aggregate_results (id TEXT PRIMARY KEY,run_id TEXT NOT NULL,payload_json TEXT NOT NULL,FOREIGN KEY(run_id) REFERENCES walk_forward_runs(id));
            CREATE TABLE IF NOT EXISTS historical_benchmark_observations (id TEXT PRIMARY KEY,benchmark_run_id TEXT NOT NULL,timestamp TEXT NOT NULL,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS experiment_budgets (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS strategy_experiments (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS strategy_candidate_deltas (id TEXT PRIMARY KEY,experiment_id TEXT NOT NULL,payload_json TEXT NOT NULL,FOREIGN KEY(experiment_id) REFERENCES strategy_experiments(id));
            CREATE TABLE IF NOT EXISTS candidate_evaluation_evidence (id TEXT PRIMARY KEY,experiment_id TEXT NOT NULL,payload_json TEXT NOT NULL,FOREIGN KEY(experiment_id) REFERENCES strategy_experiments(id));
            CREATE TABLE IF NOT EXISTS candidate_robustness_results (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS candidate_selection_policies (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS candidate_selection_results (id TEXT PRIMARY KEY,experiment_id TEXT NOT NULL,payload_json TEXT NOT NULL,FOREIGN KEY(experiment_id) REFERENCES strategy_experiments(id));
            CREATE TABLE IF NOT EXISTS strategy_promotion_policies (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS strategy_promotion_proposals (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS promotion_eligibility_results (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS strategy_promotion_reviews (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS approved_strategy_versions (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS prebreakout_policy_approvals (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS prebreakout_policy_selections (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS prebreakout_setup_assessments (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS reliability_decisions (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS brain_research_handoffs (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS strategy_activations (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS strategy_rollbacks (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS self_improvement_runs (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS self_improvement_observations (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS self_improvement_evidence_policies (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS attribution_rule_sets (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS strategy_error_attributions (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS strategy_success_attributions (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS recurring_strategy_patterns (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS strategy_error_summaries (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS strategy_success_summaries (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS improvement_hypotheses (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS hypothesis_ranking_policies (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS hypothesis_proposal_budgets (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS hypothesis_generation_policies (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS strategy_improvement_hypotheses (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS strategy_hypothesis_rankings (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS hypothesis_reviews (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS hypothesis_experiment_links (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS automated_research_runs (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS future_oos_candidate_queue_entries (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS automated_research_cycle_results (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS future_oos_assignment_policies (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS future_oos_assignments (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS future_oos_execution_results (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS research_candidate_oos_records (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS promotion_evidence_packages (id TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
            """
        )
        # Lightweight forward migration for development databases created before replay-event sequencing.
        event_columns = {row["name"] for row in self._connection.execute("PRAGMA table_info(backtest_events)")}
        if "sequence_number" not in event_columns:
            self._connection.execute("ALTER TABLE backtest_events ADD COLUMN sequence_number INTEGER")
            self._connection.execute("UPDATE backtest_events SET sequence_number=rowid WHERE sequence_number IS NULL")
        self._connection.commit()

    @staticmethod
    def _strategy_from_row(row: sqlite3.Row) -> StrategyDefinition:
        author = json.loads(row["author_reviewer_json"])
        parent = (
            StrategyVersionReference(row["parent_strategy_id"], row["parent_version"])
            if row["parent_strategy_id"] else None
        )
        return StrategyDefinition(
            strategy_id=row["strategy_id"], version=row["version"], name=row["name"],
            status=StrategyStatus(row["initial_status"]), created_at=_parse_timestamp(row["created_at"]),
            effective_from=_optional_parse_timestamp(row["effective_from"]), effective_to=_optional_parse_timestamp(row["effective_to"]),
            description=row["description"], configuration=_configuration_from_dict(json.loads(row["configuration_json"])),
            rule_definition_version=_configuration_version_from(row["rule_definition_version"]),
            scoring_configuration_version=_configuration_version_from(row["scoring_configuration_version"]),
            execution_gate_configuration_version=_configuration_version_from(row["execution_gate_configuration_version"]),
            risk_configuration_version=_configuration_version_from(row["risk_configuration_version"]),
            benchmark_configuration_version=_configuration_version_from(row["benchmark_configuration_version"]),
            author_reviewer=AuthorReviewerMetadata(**author), approval_status=ApprovalStatus(row["initial_approval_status"]),
            validation_status=StrategyValidationStatus(row["initial_validation_status"]), parent_strategy_version=parent,
        )

    @staticmethod
    def _lifecycle_from_row(row: sqlite3.Row) -> StrategyLifecycleEvent:
        return StrategyLifecycleEvent(
            row["id"], StrategyVersionReference(row["strategy_id"], row["version"]), StrategyStatus(row["status"]),
            ApprovalStatus(row["approval_status"]), StrategyValidationStatus(row["validation_status"]),
            _parse_timestamp(row["occurred_at"]), row["actor_id"], row["rationale"],
        )

    @staticmethod
    def _evidence_from_row(row: sqlite3.Row) -> Evidence:
        return Evidence(
            row["id"], row["source"], row["source_identifier"], _parse_timestamp(row["timestamp"]),
            tuple(json.loads(row["observation_ids_json"])), EvidenceType(row["evidence_type"]),
            row["factual_content_reference"], row["confidence"], _provenance_from_dict(json.loads(row["provenance_json"])),
        )

    @staticmethod
    def _diagnostic_from_row(row: sqlite3.Row) -> DiagnosticResult:
        return DiagnosticResult(
            row["id"], row["instrument_id"], row["rule_id"], StrategyVersionReference(row["strategy_id"], row["version"]),
            row["result"], row["score"], row["confidence"], tuple(json.loads(row["evidence_ids_json"])),
            tuple(json.loads(row["input_observation_ids_json"])), _parse_timestamp(row["evaluated_at"]),
            _parse_timestamp(row["as_of_timestamp"]),
        )

    @staticmethod
    def _scorecard_from_row(row: sqlite3.Row) -> Scorecard:
        return Scorecard(
            row["id"], row["instrument_id"], StrategyVersionReference(row["strategy_id"], row["version"]),
            _parse_timestamp(row["evaluated_at"]), _parse_timestamp(row["as_of_timestamp"]),
            tuple(_component_from_dict(item) for item in json.loads(row["components_json"])), row["aggregate_score"],
        )

    @staticmethod
    def _gate_from_row(row: sqlite3.Row) -> GateDecision:
        return GateDecision(
            row["id"], row["gate_name"], StrategyVersionReference(row["strategy_id"], row["version"]),
            GateOutcome(row["outcome"]), row["rationale"], tuple(json.loads(row["evidence_ids_json"])),
            json.loads(row["parameters_json"]), _parse_timestamp(row["evaluated_at"]), _parse_timestamp(row["as_of_timestamp"]),
        )


def _json(value: Any) -> str:
    return json.dumps(_plain(value), sort_keys=True, separators=(",", ":"))


def _plain(value: Any) -> Any:
    if isinstance(value, datetime):
        return _timestamp(value)
    if isinstance(value, (StrategyStatus, ApprovalStatus, StrategyValidationStatus, ConfigurationValueStatus, EvidenceType, GateOutcome, DataQuality)):
        return value.value
    if hasattr(value, "__dataclass_fields__"):
        return {name: _plain(getattr(value, name)) for name in value.__dataclass_fields__}
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def _configuration_version(value: str | ConfigurationValueStatus) -> str:
    return value.value if isinstance(value, ConfigurationValueStatus) else value


def _configuration_version_from(value: str) -> str | ConfigurationValueStatus:
    try:
        return ConfigurationValueStatus(value)
    except ValueError:
        return value


def _configuration_from_dict(value: dict[str, Any]) -> StrategyConfiguration:
    return StrategyConfiguration(
        scoring_weights={key: _configuration_version_from(item) if isinstance(item, str) else item for key, item in value["scoring_weights"].items()},
        rotation_threshold=_configuration_version_from(value["rotation_threshold"]) if isinstance(value["rotation_threshold"], str) else value["rotation_threshold"],
        minimum_risk_reward=_configuration_version_from(value["minimum_risk_reward"]) if isinstance(value["minimum_risk_reward"], str) else value["minimum_risk_reward"],
        execution_gate_parameters=value["execution_gate_parameters"], portfolio_heat_limits=value["portfolio_heat_limits"],
        sector_exposure_limits=value["sector_exposure_limits"], position_limits=value["position_limits"],
        capital_velocity_rule=_configuration_value_or_mapping(value["capital_velocity_rule"]),
        earnings_blackout=_configuration_value_or_mapping(value["earnings_blackout"]), risk_parameters=value["risk_parameters"],
    )


def _configuration_value_or_mapping(value: Any) -> Mapping[str, Any] | ConfigurationValueStatus:
    return _configuration_version_from(value) if isinstance(value, str) else value


def _component_from_dict(value: dict[str, Any]) -> ScorecardComponent:
    weight = _configuration_version_from(value["weight"]) if isinstance(value["weight"], str) else value["weight"]
    treatment = _configuration_version_from(value["missing_data_treatment"]) if isinstance(value["missing_data_treatment"], str) else value["missing_data_treatment"]
    return ScorecardComponent(value["component_id"], weight, value["score"], value["confidence"], tuple(value["evidence_ids"]), treatment)

def _decision_components(components: tuple[ScoredComponent,...]) -> list[dict[str,Any]]:
    return [{"component_id":x.component_id,"status":x.status,"score":str(x.score) if x.score is not None else None,"weight":str(x.weight),"weighted_contribution":str(x.weighted_contribution) if x.weighted_contribution is not None else None,"available_rules":list(x.available_rules),"missing_rules":list(x.missing_rules),"diagnostic_ids":list(x.diagnostic_ids),"evidence_ids":list(x.evidence_ids),"confidence":x.confidence,"contradictions":list(x.contradictions)} for x in components]
def _decision_component_from_dict(x:dict[str,Any])->ScoredComponent:
    return ScoredComponent(x["component_id"],x["status"],Decimal(x["score"]) if x["score"] is not None else None,Decimal(x["weight"]),Decimal(x["weighted_contribution"]) if x["weighted_contribution"] is not None else None,tuple(x["available_rules"]),tuple(x["missing_rules"]),tuple(x["diagnostic_ids"]),tuple(x["evidence_ids"]),x["confidence"],tuple(x["contradictions"]))


def _execution_evaluation_to_dict(value: ExecutionGateEvaluation) -> dict[str, Any]:
    return {
        "id": value.id, "instrument_id": value.instrument_id,
        "strategy_id": value.strategy_version.strategy_id, "strategy_version": value.strategy_version.version,
        "registry_version": value.registry_version, "scoring_configuration_version": value.scoring_configuration_version,
        "gate_configuration_version": value.gate_configuration_version, "scorecard_id": value.scorecard_id, "input_snapshot_id": value.input_snapshot_id,
        "action_context": value.action_context.value, "as_of_timestamp": _timestamp(value.as_of_timestamp),
        "evaluated_at": _timestamp(value.evaluated_at), "raw_decision_score": _decimal_or_none(value.raw_decision_score),
        "rotation_adjustment": _decimal_or_none(value.rotation_adjustment), "comparison_score": _decimal_or_none(value.comparison_score),
        "decisions": [{"gate_id": x.gate_id, "outcome": x.outcome.value, "detail": x.detail, "confidence": x.confidence,
                       "evidence_ids": list(x.evidence_ids), "parameters": dict(x.parameters)} for x in value.decisions],
        "eligibility": value.eligibility.value, "failed_gate_ids": list(value.failed_gate_ids),
        "insufficient_gate_ids": list(value.insufficient_gate_ids), "warnings": list(value.warnings),
        "evidence_ids": list(value.evidence_ids), "diagnostic_ids": list(value.diagnostic_ids),
        "configuration_parameters": dict(value.configuration_parameters),
    }


def _execution_evaluation_from_dict(value: dict[str, Any]) -> ExecutionGateEvaluation:
    decisions = tuple(GateDecisionRecord(x["gate_id"], ExecutionGateOutcome(x["outcome"]), x["detail"], x["confidence"],
                                         tuple(x["evidence_ids"]), x["parameters"]) for x in value["decisions"])
    return ExecutionGateEvaluation(value["id"], value["instrument_id"], StrategyVersionReference(value["strategy_id"], value["strategy_version"]),
        value["registry_version"], value["scoring_configuration_version"], value["gate_configuration_version"], value["scorecard_id"], value.get("input_snapshot_id"),
        ActionContext(value["action_context"]), _parse_timestamp(value["as_of_timestamp"]), _parse_timestamp(value["evaluated_at"]),
        Decimal(value["raw_decision_score"]) if value["raw_decision_score"] is not None else None,
        Decimal(value["rotation_adjustment"]) if value["rotation_adjustment"] is not None else None,
        Decimal(value["comparison_score"]) if value["comparison_score"] is not None else None, decisions,
        ExecutionEligibility(value["eligibility"]), tuple(value["failed_gate_ids"]), tuple(value["insufficient_gate_ids"]),
        tuple(value["warnings"]), tuple(value["evidence_ids"]), tuple(value["diagnostic_ids"]), value["configuration_parameters"])


def _decimal_or_none(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None

def _hist_dump(x):
    return {k: (getattr(x,k).value if hasattr(getattr(x,k),'value') else _timestamp(getattr(x,k)) if isinstance(getattr(x,k),datetime) else [v.value if hasattr(v,'value') else v for v in getattr(x,k)] if isinstance(getattr(x,k),tuple) else getattr(x,k)) for k in x.__dataclass_fields__}
def _manifest_from(x):
    for k in ('created_at','coverage_start','coverage_end'):x[k]=_parse_timestamp(x[k])
    x['quality']=DatasetQuality(x['quality']);x['known_gaps']=tuple(GapType(v) for v in x['known_gaps']);x['survivorship']=SurvivorshipStatus(x['survivorship']);x['warnings']=tuple(x['warnings']);return HistoricalDatasetManifest(**x)
def _partition_from(x):
    for k in ('start','end','created_at'):x[k]=_parse_timestamp(x[k])
    x['partition_type']=PartitionType(x['partition_type']);return HistoricalPartition(**x)
def _membership_from(x):
    for k in ('effective_from','effective_to','known_at'):
        if x[k]:x[k]=_parse_timestamp(x[k])
    x['status']=InstrumentLifecycle(x['status']);return UniverseMembership(**x)


def _optional_timestamp(value: datetime | None) -> str | None:
    return _timestamp(value) if value else None


def _optional_parse_timestamp(value: str | None) -> datetime | None:
    return _parse_timestamp(value) if value else None
