from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from decimal import Decimal
from enum import Enum
from typing import Mapping

from app.historical.models import DatasetQuality
from app.signals.models import SignalConfig
from app.paper.models import PaperTradingConfig


class BacktestRunStatus(str, Enum):
    CREATED = "CREATED"
    READY = "READY"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class ReplayFrequency(str, Enum):
    DAILY_CLOSE = "DAILY_CLOSE"
    WEEKLY = "WEEKLY"
    EVENT_DRIVEN = "EVENT_DRIVEN"
    INTRADAY = "INTRADAY"


class ExecutionTimingPolicy(str, Enum):
    NEXT_BAR_OPEN = "NEXT_BAR_OPEN"
    NEXT_ELIGIBLE_BAR = "NEXT_ELIGIBLE_BAR"
    SIGNAL_CLOSE = "SIGNAL_CLOSE"


class ExecutionTimingStatus(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    WAITING_FOR_NEXT_BAR = "WAITING_FOR_NEXT_BAR"
    WAITING_FOR_ELIGIBLE_BAR = "WAITING_FOR_ELIGIBLE_BAR"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    INVALID_TIMING = "INVALID_TIMING"
    NON_TRADABLE = "NON_TRADABLE"


class BacktestDataGapBehavior(str, Enum):
    FAIL_RUN = "FAIL_RUN"
    SKIP_STEP = "SKIP_STEP"
    MARK_INSUFFICIENT_DATA = "MARK_INSUFFICIENT_DATA"


class EvaluationLabel(str, Enum):
    IN_SAMPLE = "IN_SAMPLE"
    VALIDATION = "VALIDATION"
    OUT_OF_SAMPLE_TEST = "OUT_OF_SAMPLE_TEST"


class ReplayStepStatus(str, Enum):
    COMPLETED = "COMPLETED"
    SKIPPED = "SKIPPED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    FAILED = "FAILED"


class BacktestEventType(str, Enum):
    REPLAY_STARTED = "REPLAY_STARTED"
    REPLAY_STEP_STARTED = "REPLAY_STEP_STARTED"
    REPLAY_STEP_COMPLETED = "REPLAY_STEP_COMPLETED"
    DATA_INSUFFICIENT = "DATA_INSUFFICIENT"
    LOOKAHEAD_REJECTED = "LOOKAHEAD_REJECTED"
    ARTIFACT_RECORDED = "ARTIFACT_RECORDED"
    REPLAY_COMPLETED = "REPLAY_COMPLETED"
    REPLAY_FAILED = "REPLAY_FAILED"
    REPLAY_CANCELLED = "REPLAY_CANCELLED"
    # Reserved for later phases. This foundation never emits them.
    SIGNAL_CREATED = "SIGNAL_CREATED"
    SIGNAL_TRIGGERED = "SIGNAL_TRIGGERED"
    PAPER_TRADE_OPENED = "PAPER_TRADE_OPENED"
    PAPER_TRADE_CLOSED = "PAPER_TRADE_CLOSED"
    SIGNAL_INVALIDATED = "SIGNAL_INVALIDATED"
    SIGNAL_EXPIRED = "SIGNAL_EXPIRED"
    SIGNAL_CANCELLED = "SIGNAL_CANCELLED"
    PAPER_TRADE_CREATED = "PAPER_TRADE_CREATED"
    PAPER_TRADE_PARTIAL_EXIT = "PAPER_TRADE_PARTIAL_EXIT"
    PAPER_TRADE_INSUFFICIENT = "PAPER_TRADE_INSUFFICIENT"
    EXECUTION_TIMING_RESOLVED = "EXECUTION_TIMING_RESOLVED"
    EXECUTION_WAITING = "EXECUTION_WAITING"
    EXECUTION_INSUFFICIENT = "EXECUTION_INSUFFICIENT"
    BACKTEST_FILL_APPLIED = "BACKTEST_FILL_APPLIED"
    BACKTEST_PARTIAL_EXIT_APPLIED = "BACKTEST_PARTIAL_EXIT_APPLIED"
    BACKTEST_EXIT_APPLIED = "BACKTEST_EXIT_APPLIED"
    BACKTEST_ALLOCATION_REJECTED = "BACKTEST_ALLOCATION_REJECTED"
    BACKTEST_CAPITAL_RESERVED = "BACKTEST_CAPITAL_RESERVED"
    ROTATION_EVALUATED = "ROTATION_EVALUATED"
    BENCHMARK_REBALANCE = "BENCHMARK_REBALANCE"
    SNAPSHOT_BUILT = "SNAPSHOT_BUILT"
    DIAGNOSTICS_EVALUATED = "DIAGNOSTICS_EVALUATED"
    SCORECARD_CREATED = "SCORECARD_CREATED"
    GATES_EVALUATED = "GATES_EVALUATED"
    ANALYTICAL_EVALUATION_COMPLETED = "ANALYTICAL_EVALUATION_COMPLETED"
    ANALYTICAL_EVALUATION_INSUFFICIENT = "ANALYTICAL_EVALUATION_INSUFFICIENT"
    PORTFOLIO_RECONSTRUCTED = "PORTFOLIO_RECONSTRUCTED"
    PORTFOLIO_VALUED = "PORTFOLIO_VALUED"
    PORTFOLIO_INSUFFICIENT = "PORTFOLIO_INSUFFICIENT"
    PORTFOLIO_GATES_EVALUATED = "PORTFOLIO_GATES_EVALUATED"
    PORTFOLIO_GATES_INSUFFICIENT = "PORTFOLIO_GATES_INSUFFICIENT"
    ROTATION_APPROVED_ANALYTICALLY = "ROTATION_APPROVED_ANALYTICALLY"
    ROTATION_REJECTED = "ROTATION_REJECTED"
    CASH_SELECTED = "CASH_SELECTED"


class HistoricalAnalyticalStatus(str, Enum):
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    LOOKAHEAD_REJECTED = "LOOKAHEAD_REJECTED"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class ReplaySchedule:
    schedule_id: str
    version: str
    frequency: ReplayFrequency
    timezone: str
    exchange_calendar_reference: str
    evaluation_cutoff_semantics: str
    execution_timing_policy: ExecutionTimingPolicy
    start: datetime
    end: datetime
    warnings: tuple[str, ...] = ()
    daily_close_time: time = time(15, 30)


@dataclass(frozen=True, slots=True)
class BacktestDataGapPolicy:
    policy_id: str
    version: str
    behavior: BacktestDataGapBehavior
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class BacktestRun:
    backtest_run_id: str
    dataset_manifest_id: str
    dataset_manifest_version: str
    dataset_fingerprint: str
    partition_id: str | None
    strategy_version: str
    registry_version: str
    scoring_config_version: str
    gate_config_version: str
    rotation_config_version: str
    signal_config_version: str
    paper_config_version: str
    performance_config_version: str
    backtest_config_version: str
    replay_schedule_id: str
    replay_schedule_version: str
    data_gap_policy_id: str
    data_gap_policy_version: str
    calendar_reference: str
    calendar_version: str
    evaluation_start: datetime
    evaluation_end: datetime
    initial_paper_capital: Decimal
    cost_model_reference: str
    slippage_model_reference: str
    universe_definition: str
    random_seeds: tuple[int, ...]
    status: BacktestRunStatus
    quality: DatasetQuality
    evaluation_label: EvaluationLabel
    warnings: tuple[str, ...]
    methodology_notes: tuple[str, ...]
    fingerprint: str
    created_at: datetime
    completed_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class BacktestReplayStep:
    replay_step_id: str
    backtest_run_id: str
    step_number: int
    evaluation_timestamp: datetime
    trading_session: str
    status: ReplayStepStatus
    snapshot_references: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    failure_reason: str | None = None


@dataclass(frozen=True, slots=True)
class BacktestEvent:
    event_id: str
    backtest_run_id: str
    event_type: BacktestEventType
    event_timestamp: datetime
    replay_step_number: int
    evaluation_timestamp: datetime
    referenced_artifact_ids: tuple[str, ...]
    message: str
    metadata: Mapping[str, object]
    created_at: datetime


@dataclass(frozen=True, slots=True)
class BacktestReplayResult:
    backtest_run_id: str
    status: BacktestRunStatus
    timestamps: tuple[datetime, ...]
    steps: tuple[BacktestReplayStep, ...]
    events: tuple[BacktestEvent, ...]


@dataclass(frozen=True, slots=True)
class HistoricalAnalyticalSnapshot:
    historical_snapshot_id: str
    backtest_run_id: str
    replay_step_number: int
    evaluation_timestamp: datetime
    instrument_id: str
    dataset_manifest_id: str
    source_snapshot_id: str
    selected_input_ids: tuple[str, ...]
    latest_eligible_input_ids: tuple[str, ...]
    provenance_references: tuple[str, ...]
    missing_data_fields: tuple[str, ...]
    warnings: tuple[str, ...]
    fingerprint: str


@dataclass(frozen=True, slots=True)
class HistoricalAnalyticalEvaluation:
    evaluation_id: str
    backtest_run_id: str
    replay_step_number: int
    evaluation_timestamp: datetime
    instrument_id: str
    historical_snapshot_id: str
    strategy_version: str
    registry_version: str
    scoring_config_version: str
    gate_config_version: str
    diagnostic_result_ids: tuple[str, ...]
    decision_scorecard_id: str
    data_confidence: float | None
    execution_gate_evaluation_id: str
    status: HistoricalAnalyticalStatus
    warnings: tuple[str, ...]
    insufficient_reasons: tuple[str, ...]
    fingerprint: str


@dataclass(frozen=True, slots=True)
class HistoricalHoldingGateContext:
    context_id: str
    instrument_id: str
    historical_analytical_evaluation_id: str | None
    raw_score: str | None
    comparison_score: str | None
    data_confidence: float | None
    forward_risk_reward: str | None
    gate_2_adjustment: str | None
    sector: str | None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class HistoricalPortfolioGateEvaluation:
    portfolio_gate_evaluation_id: str
    backtest_run_id: str
    replay_step_number: int
    evaluation_timestamp: datetime
    historical_analytical_evaluation_id: str
    original_execution_gate_evaluation_id: str
    backtest_portfolio_state_id: str
    gate_config_version: str
    holding_context_ids: tuple[str, ...]
    resulting_execution_gate_evaluation_id: str
    status: str
    warnings: tuple[str, ...]
    fingerprint: str
    candidate_sector: str | None = None
    candidate_risk_amount: str | None = None
    candidate_allocation: str | None = None
    expected_incremental_return: str | None = None
    modeled_switching_friction: str | None = None


@dataclass(frozen=True, slots=True)
class HistoricalRotationCandidateContext:
    context_id: str
    historical_analytical_evaluation_id: str
    contextual_gate_evaluation_id: str
    sector: str | None
    sector_supportive: bool | None
    structural_risk_reward: str | None
    entry_valid: bool | None
    stop_valid: bool | None
    invalidation_valid: bool | None
    expected_incremental_benefit: str | None
    modeled_switching_friction: str | None
    confirmation_count: int
    known_at: datetime
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class HistoricalRotationHistory:
    history_id: str
    backtest_run_id: str
    candidate_instrument_id: str
    decision: str
    occurred_at: datetime
    confirmation_count: int
    cooldown_anchor: datetime | None
    rotation_config_version: str
    source_rotation_evaluation_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class HistoricalRotationEvaluation:
    rotation_evaluation_id: str
    backtest_run_id: str
    replay_step_number: int
    evaluation_timestamp: datetime
    backtest_portfolio_state_id: str
    candidate_context_ids: tuple[str, ...]
    holding_context_ids: tuple[str, ...]
    rotation_history_ids: tuple[str, ...]
    rotation_config_version: str
    source_rotation_evaluation_id: str
    ranked_candidate_ids: tuple[str, ...]
    weakest_holding_id: str | None
    decision: str
    stance: str
    preferred_candidate_id: str | None
    warnings: tuple[str, ...]
    fingerprint: str


@dataclass(frozen=True, slots=True)
class HistoricalSignalReplayReference:
    reference_id: str; backtest_run_id: str; replay_step_number: int; generation_timestamp: datetime
    historical_analytical_evaluation_id: str; historical_portfolio_gate_evaluation_id: str
    historical_rotation_evaluation_id: str | None; backtest_portfolio_state_id: str; signal_id: str
    signal_config_version: str; trade_plan_id: str; trade_plan_version: str; lifecycle_state: str
    trigger_timestamp: datetime | None; warnings: tuple[str, ...]; fingerprint: str
    signal_config_snapshot_id: str | None = None; signal_config_fingerprint: str | None = None


@dataclass(frozen=True, slots=True)
class HistoricalPaperReplayReference:
    reference_id: str; backtest_run_id: str; signal_id: str; paper_trade_id: str; paper_outcome_id: str | None
    replay_step_numbers: tuple[int, ...]; frozen_bar_ids: tuple[str, ...]; paper_config_version: str
    cost_model_version: str; fill_policy: str; same_bar_policy: str; gap_policy: str; final_state: str
    warnings: tuple[str, ...]; fingerprint: str
    paper_config_snapshot_id: str | None = None; paper_config_fingerprint: str | None = None


@dataclass(frozen=True, slots=True)
class HistoricalTriggerTimingContext:
    """The immutable distinction between a market trigger and knowledge of it."""
    trigger_context_id: str
    signal_id: str
    trigger_bar_id: str
    trigger_timestamp: datetime
    trigger_known_at: datetime
    trigger_condition_type: str
    close_confirmation_required: bool
    replay_step_number: int
    execution_timing_policy: ExecutionTimingPolicy
    warnings: tuple[str, ...]
    fingerprint: str


@dataclass(frozen=True, slots=True)
class HistoricalExecutionTimingContext:
    context_id: str
    backtest_run_id: str
    signal_id: str
    trigger_context_id: str
    execution_timing_policy: ExecutionTimingPolicy
    selected_fill_bar_id: str | None
    skipped_bar_ids: tuple[str, ...]
    skipped_session_dates: tuple[str, ...]
    eligibility_reason: str
    status: ExecutionTimingStatus
    calendar_reference: str
    replay_timestamp: datetime
    warnings: tuple[str, ...]
    fingerprint: str

@dataclass(frozen=True, slots=True)
class SignalConfigSnapshot:
    snapshot_id: str; config: SignalConfig; created_at: datetime; methodology_notes: tuple[str, ...]; fingerprint: str

@dataclass(frozen=True, slots=True)
class PaperTradingConfigSnapshot:
    snapshot_id: str; config: PaperTradingConfig; created_at: datetime; methodology_notes: tuple[str, ...]; fingerprint: str
    sizing_specification: "FrozenSizingSpecification | None" = None


@dataclass(frozen=True, slots=True)
class FrozenSizingSpecification:
    sizing_basis: str; fixed_notional_amount: Decimal | None; fixed_risk_capital_amount: Decimal | None
    quantity_rounding_policy: str; minimum_quantity: Decimal; fractional_shares_allowed: bool
    currency: str; methodology_version: str; fingerprint: str


@dataclass(frozen=True, slots=True)
class HistoricalCapitalAllocation:
    allocation_id: str; backtest_run_id: str; replay_step_number: int; evaluation_timestamp: datetime
    candidate_signal_ids: tuple[str, ...]; ranking_inputs: Mapping[str, tuple[str, str, str, str]]
    available_cash_before: Decimal; reserved_capital: Decimal; selected_signal_ids: tuple[str, ...]
    rejected_signal_ids: tuple[str, ...]; reason: str; allocation_policy_version: str
    execution_ordering: str; paper_ledger_link_ids: tuple[str, ...]; warnings: tuple[str, ...]; fingerprint: str


@dataclass(frozen=True, slots=True)
class HistoricalPaperLedgerLink:
    link_id: str; backtest_run_id: str; signal_id: str; paper_trade_id: str; paper_outcome_id: str | None
    entry_fill_id: str | None; entry_ledger_event_id: str | None; partial_exit_ledger_event_ids: tuple[str, ...]
    final_exit_ledger_event_id: str | None; quantity: Decimal; entry_value: Decimal; exit_proceeds: Decimal
    realized_pnl: Decimal | None; costs: Decimal; net_pnl: Decimal | None; sizing_basis: str
    paper_config_version: str; source_bar_ids: tuple[str, ...]; warnings: tuple[str, ...]; fingerprint: str
    sizing_config_snapshot_id: str | None = None; sizing_config_fingerprint: str | None = None
    raw_quantity: Decimal | None = None; required_cash: Decimal | None = None; sizing_reason: str | None = None


@dataclass(frozen=True, slots=True)
class HistoricalEquityPoint:
    point_id: str; backtest_run_id: str; evaluation_timestamp: datetime; cash: Decimal; holdings_market_value: Decimal
    equity: Decimal; invested_capital: Decimal; gross_exposure: Decimal; realized_pnl: Decimal; unrealized_pnl: Decimal | None
    cumulative_costs: Decimal; open_position_count: int; backtest_portfolio_state_id: str; frozen_mark_ids: tuple[str, ...]
    warnings: tuple[str, ...]; fingerprint: str


@dataclass(frozen=True, slots=True)
class HistoricalEquitySeries:
    series_id: str; backtest_run_id: str; point_ids: tuple[str, ...]; starting_capital: Decimal; start: datetime; end: datetime
    generated_at: datetime; methodology_version: str; warnings: tuple[str, ...]; fingerprint: str


@dataclass(frozen=True, slots=True)
class BacktestAuditReconstruction:
    run: BacktestRun
    schedule: ReplaySchedule
    timestamps: tuple[datetime, ...]
    steps: tuple[BacktestReplayStep, ...]
    events: tuple[BacktestEvent, ...]
    final_status: BacktestRunStatus
