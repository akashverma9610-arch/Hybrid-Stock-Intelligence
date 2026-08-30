from __future__ import annotations

"""Historical entry-window selection; the paper engine retains fill and exit logic."""

from dataclasses import dataclass
from datetime import timedelta

from app.gates.engine import ExchangeCalendar
from app.historical.guard import BacktestLookaheadGuard, manifest_fingerprint
from app.historical.models import Eligibility, HistoricalFact
from app.paper.models import PaperBar
from app.signals.models import SignalRecord, TradePlan, TriggerObservation

from .models import (
    BacktestRun, ExecutionTimingPolicy, ExecutionTimingStatus,
    HistoricalExecutionTimingContext, HistoricalTriggerTimingContext,
)


@dataclass(frozen=True, slots=True)
class ResolvedExecutionWindow:
    trigger: HistoricalTriggerTimingContext
    context: HistoricalExecutionTimingContext
    entry_and_management_bars: tuple[PaperBar, ...]


class HistoricalExecutionTimingAdapter:
    """Resolves *when* a canonical paper simulation may start.

    It deliberately never derives a fill price, gap price, stop, target, or
    outcome.  Those decisions remain in :class:`PaperTradingEngine`.
    """

    def __init__(self, calendar: ExchangeCalendar) -> None:
        self.calendar = calendar

    def resolve(self, *, run: BacktestRun, policy: ExecutionTimingPolicy, signal: SignalRecord,
                plan: TradePlan, trigger: TriggerObservation, bars: tuple[PaperBar, ...],
                replay_timestamp, replay_step_number: int) -> ResolvedExecutionWindow:
        if trigger.observed_at > replay_timestamp or trigger.known_at > replay_timestamp:
            raise ValueError("Future trigger observation cannot resolve historical execution timing.")
        trigger_bar = self._bar_for_trigger(trigger, bars)
        close_required = any(x.confirmation_required for x in plan.trigger_conditions)
        trigger_id = "timing-trigger-" + manifest_fingerprint(signal=signal.signal_id, observation=trigger.observation_id, policy=policy.value)[:24]
        warnings: list[str] = []
        if trigger_bar is None:
            warnings.append("TRIGGER_BAR_NOT_PRESENT_IN_FROZEN_PAPER_BARS")
            trigger_bar_id = trigger.observation_id
        else:
            trigger_bar_id = trigger_bar.bar_id
        trigger_context = HistoricalTriggerTimingContext(
            trigger_id, signal.signal_id, trigger_bar_id, trigger.observed_at, trigger.known_at,
            next((x.trigger_type.value for x in plan.trigger_conditions if x.timeframe == trigger.timeframe), "UNKNOWN"),
            close_required, replay_step_number, policy, tuple(warnings),
            manifest_fingerprint(signal=signal.signal_id, trigger=trigger.observation_id, observed=trigger.observed_at, known=trigger.known_at, policy=policy.value),
        )
        eligible = self._historically_eligible_bars(bars, replay_timestamp)
        selected, skipped, sessions, status, reason = self._select(policy, trigger, trigger_bar, eligible)
        context = HistoricalExecutionTimingContext(
            "timing-window-" + manifest_fingerprint(run=run.backtest_run_id, trigger=trigger_context.fingerprint, replay=replay_timestamp, policy=policy.value, selected=selected.bar_id if selected else None, skipped=[x.bar_id for x in skipped])[:24],
            run.backtest_run_id, signal.signal_id, trigger_context.trigger_context_id, policy,
            selected.bar_id if selected else None, tuple(x.bar_id for x in skipped), tuple(sessions), reason, status,
            self.calendar.calendar_id, replay_timestamp, tuple(warnings),
            manifest_fingerprint(run=run.fingerprint, trigger=trigger_context.fingerprint, policy=policy.value, calendar=self.calendar.calendar_id, selected=selected.bar_id if selected else None, skipped=[x.bar_id for x in skipped], sessions=sessions, status=status.value),
        )
        # The selected entry bar is first; later bars remain available solely for
        # existing paper-engine management/outcome simulation.
        window = tuple(bar for bar in eligible if selected is not None and bar.timestamp >= selected.timestamp) if selected else ()
        return ResolvedExecutionWindow(trigger_context, context, window)

    def _bar_for_trigger(self, trigger: TriggerObservation, bars: tuple[PaperBar, ...]) -> PaperBar | None:
        matches = [bar for bar in bars if bar.timestamp == trigger.observed_at]
        return sorted(matches, key=lambda bar: bar.bar_id)[0] if matches else None

    def _select(self, policy, trigger, trigger_bar, bars):
        skipped: list[PaperBar] = []
        skipped_sessions: list[str] = []
        if policy is ExecutionTimingPolicy.SIGNAL_CLOSE:
            if trigger_bar is None or trigger.known_at > trigger.observed_at or trigger_bar.known_at > trigger.observed_at:
                return None, skipped, skipped_sessions, ExecutionTimingStatus.INVALID_TIMING, "SIGNAL_CLOSE_NOT_KNOWN_AT_TRIGGER_CLOSE"
            if not self._tradable(trigger_bar):
                skipped.append(trigger_bar)
                return None, skipped, skipped_sessions, ExecutionTimingStatus.NON_TRADABLE, "TRIGGER_CLOSE_BAR_NOT_TRADABLE"
            return trigger_bar, skipped, skipped_sessions, ExecutionTimingStatus.ELIGIBLE, "SIGNAL_CLOSE_KNOWN_AND_TRADABLE"

        candidates = [bar for bar in bars if bar.timestamp > trigger.observed_at]
        if not candidates:
            return None, skipped, skipped_sessions, ExecutionTimingStatus.WAITING_FOR_NEXT_BAR if policy is ExecutionTimingPolicy.NEXT_BAR_OPEN else ExecutionTimingStatus.WAITING_FOR_ELIGIBLE_BAR, "NO_SUBSEQUENT_ELIGIBLE_BAR_AS_OF_REPLAY_TIMESTAMP"
        first_session = None
        for bar in candidates:
            if not self.calendar.is_trading_day(bar.timestamp.date()):
                skipped.append(bar); skipped_sessions.append(bar.timestamp.date().isoformat()); continue
            if first_session is None:
                first_session = bar.timestamp.date()
                skipped_sessions.extend(self._calendar_gaps(trigger.observed_at.date(), first_session))
                expected = self._next_trading_session(trigger.observed_at.date())
                missing_sessions = self._missing_trading_sessions(expected, first_session)
                if missing_sessions:
                    skipped_sessions.extend(missing_sessions)
                    if policy is ExecutionTimingPolicy.NEXT_BAR_OPEN:
                        return None, skipped, skipped_sessions, ExecutionTimingStatus.INSUFFICIENT_DATA, "NEXT_BAR_OPEN_MISSING_TRADABLE_SESSION"
            if self._tradable(bar):
                return bar, skipped, skipped_sessions, ExecutionTimingStatus.ELIGIBLE, "NEXT_BAR_OPEN" if policy is ExecutionTimingPolicy.NEXT_BAR_OPEN else "NEXT_ELIGIBLE_TRADABLE_BAR"
            skipped.append(bar)
            if policy is ExecutionTimingPolicy.NEXT_BAR_OPEN:
                return None, skipped, skipped_sessions, ExecutionTimingStatus.NON_TRADABLE, "NEXT_BAR_OPEN_UNAVAILABLE_OR_NON_TRADABLE"
        return None, skipped, skipped_sessions, ExecutionTimingStatus.WAITING_FOR_ELIGIBLE_BAR, "SUBSEQUENT_BARS_NOT_TRADABLE"

    @staticmethod
    def _tradable(bar: PaperBar) -> bool:
        return bar.valid and not bar.stale

    @staticmethod
    def _historically_eligible_bars(bars: tuple[PaperBar, ...], replay_timestamp) -> tuple[PaperBar, ...]:
        guard = BacktestLookaheadGuard()
        permitted = []
        for bar in bars:
            # Validity/tradability is retained for the resolver to record as a
            # skipped bar. The guard here is the independent point-in-time test.
            fact = HistoricalFact(bar.bar_id, "PAPER_BAR", bar.timestamp, bar.known_at, bar.known_at, valid=True)
            if guard.evaluate(fact, replay_timestamp) is Eligibility.ELIGIBLE:
                permitted.append(bar)
        return tuple(sorted(permitted, key=lambda bar: (bar.timestamp, bar.bar_id)))

    def _calendar_gaps(self, start, first) -> list[str]:
        value, gaps = start + timedelta(days=1), []
        while value < first:
            if not self.calendar.is_trading_day(value): gaps.append(value.isoformat())
            value += timedelta(days=1)
        return gaps

    def _next_trading_session(self, start):
        value = start + timedelta(days=1)
        while not self.calendar.is_trading_day(value):
            value += timedelta(days=1)
        return value

    def _missing_trading_sessions(self, expected, first) -> list[str]:
        missing = []
        while expected < first:
            if self.calendar.is_trading_day(expected): missing.append(expected.isoformat())
            expected += timedelta(days=1)
        return missing
