from __future__ import annotations

"""Immutable walk-forward planning and clean-OOS orchestration primitives."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Callable

from app.historical.guard import manifest_fingerprint
from app.historical.models import HistoricalPartition, PartitionType


class WalkForwardMode(str, Enum):
    ROLLING = "ROLLING"
    EXPANDING = "EXPANDING"


class WalkForwardStatus(str, Enum):
    PLANNED = "PLANNED"
    VALID = "VALID"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    DEGRADED = "DEGRADED"
    UNSTABLE = "UNSTABLE"
    FAILED_AUDIT = "FAILED_AUDIT"


class WalkForwardRunStatus(str, Enum):
    PLANNED = "PLANNED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_WARNINGS = "COMPLETED_WITH_WARNINGS"
    INSUFFICIENT = "INSUFFICIENT"
    FAILED = "FAILED"


class WalkForwardWindowResultStatus(str, Enum):
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_WARNINGS = "COMPLETED_WITH_WARNINGS"
    INSUFFICIENT = "INSUFFICIENT"
    FAILED = "FAILED"
    FAILED_AUDIT = "FAILED_AUDIT"


class OOSStartingCapitalMethodology(str, Enum):
    INDEPENDENT_WINDOW_CAPITAL = "INDEPENDENT_WINDOW_CAPITAL"


@dataclass(frozen=True, slots=True)
class WalkForwardPlan:
    plan_id: str; dataset_id: str; dataset_version: str; strategy_family: str; validation_methodology_version: str
    mode: WalkForwardMode; train_sessions: int; validation_sessions: int; test_sessions: int; step_sessions: int
    purge_sessions: int; embargo_sessions: int; minimum_observations: int; calendar_reference: str; generated_at: datetime
    warnings: tuple[str, ...]; fingerprint: str


@dataclass(frozen=True, slots=True)
class StrategyCandidate:
    """Authoritative immutable version references selected before TEST begins."""
    candidate_id: str; strategy_version: str; registry_version: str; scoring_version: str; gate_version: str; rotation_version: str
    signal_config_snapshot_id: str; paper_config_snapshot_id: str; allocation_policy_version: str; performance_config_version: str; fingerprint: str


@dataclass(frozen=True, slots=True)
class WalkForwardWindow:
    window_id: str; plan_id: str; ordinal: int; train: HistoricalPartition; validation: HistoricalPartition | None; test: HistoricalPartition
    selected_candidate_id: str; status: WalkForwardStatus; warnings: tuple[str, ...]; fingerprint: str
    candidate_selection_result_id: str | None = None
    selection_timestamp: datetime | None = None
    selected_candidate_fingerprint: str | None = None


@dataclass(frozen=True, slots=True)
class WalkForwardRun:
    run_id: str; plan_id: str; ordered_window_ids: tuple[str, ...]; candidate_ids: tuple[str, ...]
    selection_policy: str; selection_policy_version: str; methodology_version: str; status: WalkForwardRunStatus
    started_at: datetime; completed_at: datetime | None; warnings: tuple[str, ...]; fingerprint: str

    @property
    def planned_window_count(self) -> int:
        return len(self.ordered_window_ids)


@dataclass(frozen=True, slots=True)
class WalkForwardWindowResult:
    result_id: str; walk_forward_run_id: str; walk_forward_window_id: str; selected_candidate_id: str; selected_candidate_fingerprint: str
    selection_evidence_ids: tuple[str, ...]; selection_timestamp: datetime; selection_policy: str; selection_policy_version: str
    oos_starting_capital_methodology: OOSStartingCapitalMethodology; test_backtest_run_id: str | None; performance_report_id: str | None; benchmark_comparison_id: str | None
    test_start: datetime; test_end: datetime; starting_equity: Decimal; ending_equity: Decimal | None; absolute_return: Decimal | None; max_drawdown: Decimal | None
    sharpe: Decimal | None; sortino: Decimal | None; expectancy: Decimal | None; profit_factor: Decimal | None; win_rate: Decimal | None
    trade_count: int; total_costs: Decimal | None; status: WalkForwardWindowResultStatus; warnings: tuple[str, ...]; fingerprint: str


@dataclass(frozen=True, slots=True)
class WalkForwardRunCoverage:
    planned_windows: int
    completed_valid_windows: int
    insufficient_windows: int
    failed_windows: int
    benchmark_covered_windows: int
    status: WalkForwardRunStatus


class WalkForwardWindowGenerator:
    """Pure deterministic generator; it never examines TEST outcomes."""

    def generate(self, *, plan: WalkForwardPlan, sessions: tuple[datetime, ...], candidate: StrategyCandidate) -> tuple[WalkForwardWindow, ...]:
        if len(sessions) != len(set(sessions)):
            raise ValueError("Duplicate frozen replay sessions are not valid for walk-forward generation.")
        sessions = tuple(sorted(sessions))
        if len(sessions) < plan.minimum_observations:
            raise ValueError("Insufficient frozen replay sessions.")
        windows: list[WalkForwardWindow] = []
        anchor, ordinal = 0, 1
        while True:
            train_start = 0 if plan.mode is WalkForwardMode.EXPANDING else anchor
            train_end = anchor + plan.train_sessions - 1
            validation_start = train_end + 1 + plan.purge_sessions
            validation_end = validation_start + plan.validation_sessions - 1
            test_start = validation_end + 1 + plan.embargo_sessions if plan.validation_sessions else train_end + 1 + plan.purge_sessions + plan.embargo_sessions
            test_end = test_start + plan.test_sessions - 1
            if test_end >= len(sessions):
                break
            train = self._partition(plan, "train", PartitionType.TRAIN, sessions[train_start], sessions[train_end], plan.purge_sessions, plan.embargo_sessions)
            validation = self._partition(plan, "validation", PartitionType.VALIDATION, sessions[validation_start], sessions[validation_end], plan.purge_sessions, plan.embargo_sessions) if plan.validation_sessions else None
            test = self._partition(plan, "test", PartitionType.TEST, sessions[test_start], sessions[test_end], plan.purge_sessions, plan.embargo_sessions)
            fingerprint = manifest_fingerprint(plan=plan.fingerprint, ordinal=ordinal, train=[train.start, train.end], validation=[validation.start, validation.end] if validation else None, test=[test.start, test.end], candidate=candidate.fingerprint)
            windows.append(WalkForwardWindow("walk-window-" + fingerprint[:24], plan.plan_id, ordinal, train, validation, test, candidate.candidate_id, WalkForwardStatus.PLANNED, (), fingerprint))
            ordinal += 1; anchor += plan.step_sessions
        return tuple(windows)

    @staticmethod
    def _partition(plan: WalkForwardPlan, name: str, kind: PartitionType, start: datetime, end: datetime, purge: int, embargo: int) -> HistoricalPartition:
        return HistoricalPartition(f"{plan.plan_id}:{name}:{start.isoformat()}:{end.isoformat()}", plan.dataset_id, kind, start, end, purge, embargo, f"walk-forward {name}", plan.generated_at)


def assert_test_isolation(window: WalkForwardWindow, observation_timestamp: datetime, *, purpose: PartitionType) -> None:
    """Fail closed if TEST data enters selection or OOS uses non-TEST observations."""
    if purpose in {PartitionType.TRAIN, PartitionType.VALIDATION} and window.test.start <= observation_timestamp <= window.test.end:
        raise ValueError("TEST/OOS observation cannot enter TRAIN or VALIDATION selection.")
    if purpose is PartitionType.TEST and not window.test.start <= observation_timestamp <= window.test.end:
        raise ValueError("Pre-TEST or post-TEST observation cannot enter clean OOS execution.")


class WalkForwardExecutionService:
    """Thin coordinator that delegates all analytical action to existing Phase 8A services."""

    def __init__(self, repository) -> None:
        self.repository = repository

    def freeze_selection(self, *, run: WalkForwardRun, window: WalkForwardWindow, candidate: StrategyCandidate, selected_at: datetime, evidence_ids: tuple[str, ...] = ()) -> None:
        if window.selected_candidate_id != candidate.candidate_id or candidate.candidate_id not in run.candidate_ids:
            raise ValueError("Walk-forward selection must use a candidate frozen on the run.")
        if selected_at >= window.test.start:
            raise ValueError("Candidate selection must be frozen strictly before TEST start.")
        if any("TEST" in evidence_id.upper() for evidence_id in evidence_ids):
            raise ValueError("TEST artifacts cannot be used as candidate-selection evidence.")
        if window.candidate_selection_result_id is not None:
            selection=self.repository.get_candidate_selection_result(window.candidate_selection_result_id)
            if selection is None or selection.selected_candidate_id!=candidate.candidate_id or selection.selection_timestamp!=window.selection_timestamp or selection.selection_timestamp>window.test.start:
                raise ValueError("Walk-forward selection handoff is missing, mismatched, or retroactive.")

    def coverage(self, run_id: str) -> WalkForwardRunCoverage:
        """Derive lifecycle completion from immutable window results; never rewrite a run."""
        run = self.repository.get_walk_forward_run(run_id)
        if run is None:
            raise ValueError("Walk-forward run does not exist.")
        results = self.repository.list_walk_forward_window_results(run_id)
        by_window = {result.walk_forward_window_id: result for result in results}
        planned = len(run.ordered_window_ids)
        completed = sum(result.status in {WalkForwardWindowResultStatus.COMPLETED, WalkForwardWindowResultStatus.COMPLETED_WITH_WARNINGS} for result in results)
        insufficient = sum(result.status is WalkForwardWindowResultStatus.INSUFFICIENT for result in results)
        failed = sum(result.status in {WalkForwardWindowResultStatus.FAILED, WalkForwardWindowResultStatus.FAILED_AUDIT} for result in results)
        benchmark = sum(result.benchmark_comparison_id is not None for result in results)
        if len(by_window) < planned:
            status = WalkForwardRunStatus.RUNNING if results else WalkForwardRunStatus.PLANNED
        elif failed:
            status = WalkForwardRunStatus.FAILED
        elif insufficient:
            status = WalkForwardRunStatus.COMPLETED_WITH_WARNINGS
        elif any(result.status is WalkForwardWindowResultStatus.COMPLETED_WITH_WARNINGS for result in results):
            status = WalkForwardRunStatus.COMPLETED_WITH_WARNINGS
        else:
            status = WalkForwardRunStatus.COMPLETED
        return WalkForwardRunCoverage(planned, completed, insufficient, failed, benchmark, status)

    def execute_window(self, *, run: WalkForwardRun, window: WalkForwardWindow, candidate: StrategyCandidate, selected_at: datetime, test_run, phase8_executor: Callable, selection_evidence_ids: tuple[str, ...] = (), post_replay_performance_integrator: Callable | None = None) -> WalkForwardWindowResult:
        self.freeze_selection(run=run, window=window, candidate=candidate, selected_at=selected_at, evidence_ids=selection_evidence_ids)
        self._validate_clean_test_run(window, candidate, test_run)
        try:
            execution = phase8_executor(test_run, window.test)
            stored_run = self.repository.get_backtest_run(test_run.backtest_run_id)
            status = getattr(execution, "status", getattr(stored_run, "status", test_run.status))
            if status.value == "INSUFFICIENT_DATA":
                return self._persist_result(run, window, candidate, selected_at, test_run, None, None, selection_evidence_ids, WalkForwardWindowResultStatus.INSUFFICIENT, ("TEST_BACKTEST_INSUFFICIENT_DATA",))
            if status.value != "COMPLETED":
                return self._persist_result(run, window, candidate, selected_at, test_run, None, None, selection_evidence_ids, WalkForwardWindowResultStatus.FAILED, (f"TEST_BACKTEST_{status.value}",))
            if post_replay_performance_integrator is not None:
                generated=post_replay_performance_integrator(test_run)
                report_id=getattr(getattr(generated,"report",generated),"report_id",None)
                report=self.repository.get_performance_report(report_id) if report_id else None
                if report is None or f"BACKTEST_RUN:{test_run.backtest_run_id}" not in report.methodology_notes:
                    raise ValueError("Post-replay performance integration must persist a report for the exact TEST BacktestRun.")
            report = self._report_for_test_run(test_run.backtest_run_id)
            if report is None:
                return self._persist_result(run, window, candidate, selected_at, test_run, None, None, selection_evidence_ids, WalkForwardWindowResultStatus.COMPLETED_WITH_WARNINGS, ("PERFORMANCE_REPORT_UNAVAILABLE", "BENCHMARK_UNAVAILABLE"))
            comparisons = self.repository.list_benchmark_comparisons(report.report_id)
            comparison_id = None if not comparisons else "historical-comparison-" + manifest_fingerprint(report=report.report_id, benchmark=comparisons[0].benchmark_id)[:24]
            warnings = () if comparisons else ("BENCHMARK_UNAVAILABLE",)
            return self._persist_result(run, window, candidate, selected_at, test_run, report, comparison_id, selection_evidence_ids, WalkForwardWindowResultStatus.COMPLETED_WITH_WARNINGS if warnings else WalkForwardWindowResultStatus.COMPLETED, warnings)
        except Exception as error:
            return self._persist_result(run, window, candidate, selected_at, test_run, None, None, selection_evidence_ids, WalkForwardWindowResultStatus.FAILED, (f"TEST_EXECUTION_FAILED:{type(error).__name__}",))

    def _validate_clean_test_run(self, window: WalkForwardWindow, candidate: StrategyCandidate, test_run) -> None:
        if test_run.partition_id != window.test.partition_id or test_run.evaluation_start != window.test.start or test_run.evaluation_end != window.test.end:
            raise ValueError("TEST BacktestRun must be scoped exactly to the frozen TEST partition.")
        if test_run.initial_paper_capital <= 0:
            raise ValueError("Independent TEST starting capital must be positive.")
        versions = (test_run.strategy_version, test_run.registry_version, test_run.scoring_config_version, test_run.gate_config_version, test_run.rotation_config_version, test_run.signal_config_version, test_run.paper_config_version, test_run.performance_config_version)
        expected = (candidate.strategy_version, candidate.registry_version, candidate.scoring_version, candidate.gate_version, candidate.rotation_version, candidate.signal_config_snapshot_id, candidate.paper_config_snapshot_id, candidate.performance_config_version)
        if versions != expected:
            raise ValueError("TEST BacktestRun does not match the selected frozen candidate configuration.")
        if "INDEPENDENT_WINDOW_CAPITAL" not in test_run.methodology_notes:
            raise ValueError("TEST BacktestRun must declare independent-window capital methodology.")

    def _report_for_test_run(self, test_run_id: str):
        for report_id in self.repository.list_performance_report_ids():
            report = self.repository.get_performance_report(report_id)
            if report and f"BACKTEST_RUN:{test_run_id}" in report.methodology_notes:
                return report
        return None

    def _persist_result(self, run, window, candidate, selected_at, test_run, report, comparison_id, evidence_ids, status, warnings):
        metrics = report.metrics if report else {}
        result = WalkForwardWindowResult(
            "walk-result-" + manifest_fingerprint(run=run.fingerprint, window=window.fingerprint, test_run=test_run.backtest_run_id, status=status.value)[:24],
            run.run_id, window.window_id, candidate.candidate_id, candidate.fingerprint, tuple(evidence_ids), selected_at, run.selection_policy, run.selection_policy_version, OOSStartingCapitalMethodology.INDEPENDENT_WINDOW_CAPITAL,
            test_run.backtest_run_id, report.report_id if report else None, comparison_id, window.test.start, window.test.end, test_run.initial_paper_capital,
            metrics.get("ending_equity"), metrics.get("portfolio_return"), metrics.get("max_drawdown"), metrics.get("sharpe"), metrics.get("sortino"), metrics.get("expectancy"), metrics.get("profit_factor"), metrics.get("win_rate"), int(metrics.get("trade_count", 0)), metrics.get("total_costs"), status, tuple(warnings),
            manifest_fingerprint(run=run.fingerprint, window=window.fingerprint, candidate=candidate.fingerprint, report=report.report_id if report else None, status=status.value, metrics=metrics),
        )
        self.repository.save_walk_forward_window_result(result)
        return result
