"""Immutable, non-predictive records for a bounded stored-evidence trial.

The records intentionally contain no return, ranking, trade, or alpha fields.
They describe evidence availability and canonical analytical attempts only.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from app.data_coverage.models import DataCoverageRecord, StrategyCoverageReadiness


class RealBrainTrialStatus(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class RealBrainStockResult:
    """Internal, public-safe distilled output; diagnostic identities are excluded."""

    result_id: str
    trial_id: str
    instrument_id: str
    symbol: str
    as_of: datetime
    status: RealBrainTrialStatus
    coverage: DataCoverageRecord
    diagnostic_total: int
    diagnostic_evaluated: int
    diagnostic_missing: int
    decision_score: Decimal | None
    confidence: float | None
    technical_ready: bool
    fundamental_ready: bool
    ownership_ready: bool
    delivery_ready: bool
    news_catalyst_ready: bool
    market_context_ready: bool
    sector_context_ready: bool
    macro_context_ready: bool
    execution_eligibility: str
    pre_breakout: StrategyCoverageReadiness
    inflection: StrategyCoverageReadiness
    historical_integrity_status: str | None
    evidence_ids: tuple[str, ...]
    blockers: tuple[str, ...]
    warnings: tuple[str, ...] = ()
    elapsed_milliseconds: int = 0


@dataclass(frozen=True, slots=True)
class RealBrainBlocker:
    code: str
    affected_stock_count: int


@dataclass(frozen=True, slots=True)
class RealBrainCoverageDelta:
    domain: str
    before_ready: int
    after_ready: int


@dataclass(frozen=True, slots=True)
class RealBrainTrialComparison:
    before_trial_id: str
    after_trial_id: str
    cohort_size: int
    coverage: tuple[RealBrainCoverageDelta, ...]
    before_complete: int
    after_complete: int
    before_partial: int
    after_partial: int
    before_unavailable: int
    after_unavailable: int
    before_diagnostic_evaluated: int
    after_diagnostic_evaluated: int
    before_diagnostic_missing: int
    after_diagnostic_missing: int


@dataclass(frozen=True, slots=True)
class RealBrainTrial:
    """Frozen report of one 30–50 instrument real-evidence execution attempt."""

    trial_id: str
    sample_version: str
    universe_snapshot_id: str
    universe_checksum: str
    as_of: datetime
    created_at: datetime
    requested_sample_size: int
    selected_instrument_ids: tuple[str, ...]
    selected_symbols: tuple[str, ...]
    selection_method: str
    source_mode: str
    provider_calls: int
    complete_count: int
    partial_count: int
    unavailable_count: int
    diagnostic_total_per_stock: int
    diagnostic_evaluated_total: int
    diagnostic_missing_total: int
    valid_decision_score_count: int
    valid_confidence_count: int
    technical_ready_count: int
    fundamental_ready_count: int
    ownership_ready_count: int
    delivery_ready_count: int
    news_catalyst_ready_count: int
    macro_ready_count: int
    sector_ready_count: int
    execution_feasible_count: int
    pre_breakout_ready_count: int
    pre_breakout_partial_count: int
    pre_breakout_unavailable_count: int
    inflection_ready_count: int
    inflection_partial_count: int
    inflection_unavailable_count: int
    blockers: tuple[RealBrainBlocker, ...]
    result_ids: tuple[str, ...]
    audit_reference: str
    total_elapsed_milliseconds: int
    warnings: tuple[str, ...] = ()
    portfolio_status: str = "PORTFOLIO_NOT_PRESENT"
    diagnostic_registry_version: str = "canonical-61-v1"
    analysis_engine_version: str = "canonical-61-runner-v1"
    decision_score_configuration_version: str = "decision-score-v1"
    frozen_cohort_reference: str | None = None
