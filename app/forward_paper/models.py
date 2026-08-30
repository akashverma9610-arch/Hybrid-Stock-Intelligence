"""Immutable contracts for internal forward paper studies.

The records in this module are research evidence only.  They deliberately do
not contain a broker, portfolio, recommendation, or allocation concept.
"""
from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from zoneinfo import ZoneInfo

from app.historical.guard import manifest_fingerprint


_NSE_SESSION_TIMEZONE = ZoneInfo("Asia/Kolkata")


def is_strictly_future_nse_session(session_at: datetime, decision_as_of: datetime) -> bool:
    """Return whether a daily bar belongs to an NSE session after the decision session.

    This intentionally compares exchange-local *session dates*, not UTC
    timestamps.  A decision made during (or after) T0 must never use a second
    T0 timestamp as a forward-paper fill/evaluation bar.
    """
    _aware(session_at, "session_at")
    _aware(decision_as_of, "decision_as_of")
    return session_at.astimezone(_NSE_SESSION_TIMEZONE).date() > decision_as_of.astimezone(_NSE_SESSION_TIMEZONE).date()


def nse_session_date(session_at: datetime):
    """Canonical local date identity for one NSE daily session."""
    _aware(session_at, "session_at")
    return session_at.astimezone(_NSE_SESSION_TIMEZONE).date()


class PaperStudyMode(StrEnum):
    FORWARD_PAPER = "FORWARD_PAPER"


class PaperStudyState(StrEnum):
    WAITING_FOR_TRIGGER = "WAITING_FOR_TRIGGER"
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    EXPIRED_UNFILLED = "EXPIRED_UNFILLED"
    MISSED_DO_NOT_CHASE = "MISSED_DO_NOT_CHASE"
    AMBIGUOUS = "AMBIGUOUS"
    INVALID_DATA = "INVALID_DATA"


class PaperEventKind(StrEnum):
    STUDY_ADMITTED = "STUDY_ADMITTED"
    TRIGGER_OBSERVED = "TRIGGER_OBSERVED"
    ENTRY_FILLED = "ENTRY_FILLED"
    ENTRY_MISSED_DO_NOT_CHASE = "ENTRY_MISSED_DO_NOT_CHASE"
    SESSION_MARK = "SESSION_MARK"
    STOP_EXIT = "STOP_EXIT"
    TARGET_EXIT = "TARGET_EXIT"
    TIME_STOP_EXIT = "TIME_STOP_EXIT"
    EXPIRED_UNFILLED = "EXPIRED_UNFILLED"
    PATH_AMBIGUOUS = "PATH_AMBIGUOUS"
    DATA_INVALIDATED = "DATA_INVALIDATED"
    CORPORATE_ACTION_REVIEW_REQUIRED = "CORPORATE_ACTION_REVIEW_REQUIRED"
    STUDY_CLOSED = "STUDY_CLOSED"


class PaperExitReason(StrEnum):
    TARGET = "TARGET"
    STOP = "STOP"
    TIME_STOP = "TIME_STOP"
    AMBIGUOUS_PATH = "AMBIGUOUS_PATH"
    DATA_INVALIDATED = "DATA_INVALIDATED"
    CORPORATE_ACTION_REVIEW_REQUIRED = "CORPORATE_ACTION_REVIEW_REQUIRED"


class EntryGapRule(StrEnum):
    OPEN_OR_TRIGGER = "OPEN_OR_TRIGGER"


class StopGapRule(StrEnum):
    OPEN_IF_GAPPED_THROUGH = "OPEN_IF_GAPPED_THROUGH"


class TargetFillRule(StrEnum):
    TARGET_PRICE = "TARGET_PRICE"


class IntrabarAmbiguityRule(StrEnum):
    PATH_AMBIGUOUS = "PATH_AMBIGUOUS"


class ForwardPaperHealth(StrEnum):
    DISABLED = "DISABLED"
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    BLOCKED_DATA = "BLOCKED_DATA"
    FAILED = "FAILED"


def _aware(value: datetime, field: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware.")


def _decimal(value: Decimal | None, field: str, *, positive: bool = False) -> None:
    if not isinstance(value, Decimal) or not value.is_finite() or (positive and value <= 0):
        raise ValueError(f"{field} must be a {'positive ' if positive else ''}finite Decimal.")


def _fingerprint(value: object, *, exclude: tuple[str, ...] = ("fingerprint",)) -> str:
    return manifest_fingerprint(**{
        item.name: _semantic(getattr(value, item.name))
        for item in fields(value) if item.name not in exclude
    })


def _semantic(value):
    if isinstance(value, StrEnum): return value.value
    if isinstance(value, datetime): return value.isoformat()
    if isinstance(value, Decimal): return str(value)
    if isinstance(value, tuple): return tuple(_semantic(item) for item in value)
    if is_dataclass(value): return {item.name: _semantic(getattr(value, item.name)) for item in fields(value)}
    return value


@dataclass(frozen=True, slots=True)
class PaperExecutionModel:
    version: str
    entry_gap_rule: EntryGapRule
    stop_gap_rule: StopGapRule
    target_fill_rule: TargetFillRule
    intrabar_ambiguity_rule: IntrabarAmbiguityRule
    entry_slippage: Decimal
    exit_slippage: Decimal
    round_trip_friction: Decimal
    fingerprint: str

    def __post_init__(self) -> None:
        if not self.version.strip(): raise ValueError("PAPER_EXECUTION_MODEL_VERSION_REQUIRED")
        for name in ("entry_slippage", "exit_slippage", "round_trip_friction"):
            _decimal(getattr(self, name), name)
            if getattr(self, name) < 0: raise ValueError(f"{name} must not be negative.")
        if self.fingerprint != _fingerprint(self): raise ValueError("PAPER_EXECUTION_MODEL_FINGERPRINT_MISMATCH")

    @classmethod
    def create(cls, *, version: str, entry_slippage: Decimal, exit_slippage: Decimal,
               round_trip_friction: Decimal) -> "PaperExecutionModel":
        values = dict(version=version, entry_gap_rule=EntryGapRule.OPEN_OR_TRIGGER,
                      stop_gap_rule=StopGapRule.OPEN_IF_GAPPED_THROUGH,
                      target_fill_rule=TargetFillRule.TARGET_PRICE,
                      intrabar_ambiguity_rule=IntrabarAmbiguityRule.PATH_AMBIGUOUS,
                      entry_slippage=entry_slippage, exit_slippage=exit_slippage,
                      round_trip_friction=round_trip_friction)
        return cls(**values, fingerprint=manifest_fingerprint(**{key: _semantic(value) for key, value in values.items()}))


@dataclass(frozen=True, slots=True)
class PaperStudyAdmission:
    canonical_instrument_id: str
    setup_id: str
    setup_fingerprint: str
    source_artifact_fingerprint: str
    strategy_version: str
    policy_fingerprint: str
    decision_as_of: datetime
    trigger: Decimal
    structural_stop: Decimal
    target: Decimal
    maximum_entry: Decimal | None
    time_stop_sessions: int
    market_regime: str | None = None
    market_regime_fingerprint: str | None = None
    sector: str | None = None
    sector_context_fingerprint: str | None = None
    brain_version: str | None = None
    brain_fingerprint: str | None = None
    decision_score: Decimal | None = None
    diagnostic_fingerprint: str | None = None
    financial_semantic_fingerprint: str | None = None
    benchmark_id: str | None = "NIFTY500"

    def __post_init__(self) -> None:
        if not all((self.canonical_instrument_id, self.setup_id, self.setup_fingerprint,
                    self.source_artifact_fingerprint, self.strategy_version, self.policy_fingerprint)):
            raise ValueError("PAPER_STUDY_ADMISSION_IDENTITY_REQUIRED")
        _aware(self.decision_as_of, "decision_as_of")
        for name in ("trigger", "structural_stop", "target"):
            _decimal(getattr(self, name), name, positive=True)
        if self.maximum_entry is not None: _decimal(self.maximum_entry, "maximum_entry", positive=True)
        if not self.structural_stop < self.trigger < self.target:
            raise ValueError("PAPER_STUDY_EXECUTABLE_ECONOMICS_INVALID")
        if self.maximum_entry is not None and self.maximum_entry < self.trigger:
            raise ValueError("PAPER_STUDY_MAXIMUM_ENTRY_BELOW_TRIGGER")
        if self.time_stop_sessions < 1: raise ValueError("PAPER_STUDY_TIME_STOP_REQUIRED")


@dataclass(frozen=True, slots=True)
class ForwardPaperStudy:
    study_id: str
    fingerprint: str
    mode: PaperStudyMode
    admission: PaperStudyAdmission
    execution_model: PaperExecutionModel
    created_at: datetime

    def __post_init__(self) -> None:
        _aware(self.created_at, "created_at")
        if self.mode is not PaperStudyMode.FORWARD_PAPER: raise ValueError("PAPER_STUDY_FORWARD_MODE_REQUIRED")
        if self.fingerprint != _fingerprint(self, exclude=("fingerprint", "study_id")):
            raise ValueError("PAPER_STUDY_FINGERPRINT_MISMATCH")

    @classmethod
    def create(cls, admission: PaperStudyAdmission, execution_model: PaperExecutionModel, *, created_at: datetime) -> "ForwardPaperStudy":
        values = dict(mode=PaperStudyMode.FORWARD_PAPER, admission=admission,
                      execution_model=execution_model, created_at=created_at)
        fingerprint = manifest_fingerprint(**{key: _semantic(value) for key, value in values.items()})
        return cls(study_id=f"forward-paper:{fingerprint[:32]}", fingerprint=fingerprint, **values)


@dataclass(frozen=True, slots=True)
class ForwardPaperBar:
    bar_id: str
    session_at: datetime
    known_at: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    valid: bool = True
    corporate_action_requires_review: bool = False
    benchmark_close: Decimal | None = None
    sector_benchmark_close: Decimal | None = None

    def __post_init__(self) -> None:
        if not self.bar_id: raise ValueError("PAPER_BAR_ID_REQUIRED")
        _aware(self.session_at, "session_at"); _aware(self.known_at, "known_at")
        for name in ("open", "high", "low", "close"):
            _decimal(getattr(self, name), name, positive=True)
        if self.low > min(self.open, self.close) or self.high < max(self.open, self.close) or self.high < self.low:
            raise ValueError("PAPER_BAR_OHLC_INVALID")


@dataclass(frozen=True, slots=True)
class ForwardPaperEvent:
    event_id: str
    study_id: str
    kind: PaperEventKind
    occurred_at: datetime
    session_at: datetime | None
    bar_id: str | None
    reason: str
    price: Decimal | None = None
    close: Decimal | None = None
    high: Decimal | None = None
    low: Decimal | None = None
    gross_r: Decimal | None = None
    net_r: Decimal | None = None
    mfe_r: Decimal | None = None
    mae_r: Decimal | None = None
    sessions_held: int | None = None
    benchmark_return: Decimal | None = None
    sector_benchmark_return: Decimal | None = None
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if not all((self.event_id, self.study_id, self.reason)): raise ValueError("PAPER_EVENT_IDENTITY_REQUIRED")
        _aware(self.occurred_at, "occurred_at")
        if self.session_at is not None: _aware(self.session_at, "session_at")
        if self.sessions_held is not None and self.sessions_held < 0: raise ValueError("PAPER_EVENT_SESSIONS_INVALID")
        if self.fingerprint != _fingerprint(self): raise ValueError("PAPER_EVENT_FINGERPRINT_MISMATCH")

    @classmethod
    def create(cls, *, event_id: str, study_id: str, kind: PaperEventKind, occurred_at: datetime,
               session_at: datetime | None, bar_id: str | None, reason: str, **values) -> "ForwardPaperEvent":
        payload = dict(event_id=event_id, study_id=study_id, kind=kind, occurred_at=occurred_at,
                       session_at=session_at, bar_id=bar_id, reason=reason, price=None, close=None,
                       high=None, low=None, gross_r=None, net_r=None, mfe_r=None, mae_r=None,
                       sessions_held=None, benchmark_return=None, sector_benchmark_return=None)
        payload.update(values)
        return cls(**payload, fingerprint=manifest_fingerprint(**{key: _semantic(value) for key, value in payload.items()}))


@dataclass(frozen=True, slots=True)
class ForwardPaperSnapshot:
    study_id: str
    state: PaperStudyState
    entry_price: Decimal | None
    entry_session: datetime | None
    exit_price: Decimal | None
    exit_session: datetime | None
    exit_reason: PaperExitReason | None
    gross_r: Decimal | None
    net_r: Decimal | None
    mfe_r: Decimal | None
    mae_r: Decimal | None
    sessions_held: int
    benchmark_return: Decimal | None
    sector_benchmark_return: Decimal | None
    event_count: int
    last_session: datetime | None


@dataclass(frozen=True, slots=True)
class PaperTradingPerformanceEvidence:
    generated_at: datetime
    study_count: int
    eligible_closed_count: int
    wins: int
    losses: int
    unfilled_count: int
    missed_count: int
    ambiguous_count: int
    invalid_count: int
    win_rate: Decimal | None
    expectancy_r: Decimal | None
    average_r: Decimal | None
    median_r: Decimal | None
    average_mfe_r: Decimal | None
    median_mfe_r: Decimal | None
    average_mae_r: Decimal | None
    median_mae_r: Decimal | None
    profit_factor: Decimal | None
    target_hit_rate: Decimal | None
    stop_hit_rate: Decimal | None
    time_stop_rate: Decimal | None
    median_holding_sessions: Decimal | None
    groups: tuple[tuple[str, int, Decimal | None], ...]
