"""Pure-forward evaluation and descriptive evidence for internal paper studies."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from statistics import median
from threading import Event, Lock, Thread
from typing import Callable, Iterable, Protocol
from uuid import uuid4

from app.forward_paper.models import (
    ForwardPaperBar, ForwardPaperEvent, ForwardPaperHealth, ForwardPaperSnapshot,
    ForwardPaperStudy, PaperEventKind, PaperExitReason, PaperStudyAdmission,
    PaperStudyState, PaperTradingPerformanceEvidence, is_strictly_future_nse_session,
    nse_session_date,
)
from app.forward_paper.store import ForwardPaperStore
from app.strategies.pre_breakout.candidate_assembly import PreBreakoutCandidate


class GovernedSetupSource(Protocol):
    def executable_prebreakout_candidates(self, *, as_of: datetime) -> tuple[PreBreakoutCandidate, ...]: ...


@dataclass(frozen=True, slots=True)
class PaperTradingSettings:
    enabled: bool = False
    poll_seconds: int = 300

    def __post_init__(self) -> None:
        if self.poll_seconds < 1: raise ValueError("PAPER_TRADING_POLL_SECONDS_INVALID")

    @classmethod
    def from_environment(cls, environ=None) -> "PaperTradingSettings":
        import os
        values = os.environ if environ is None else environ
        raw = values.get("PAPER_TRADING_ENABLED", "false").strip().lower()
        accepted = {"true": True, "1": True, "yes": True, "on": True, "false": False, "0": False, "no": False, "off": False}
        if raw not in accepted: raise ValueError("PAPER_TRADING_ENABLED must be a boolean value.")
        try: poll = int(values.get("PAPER_TRADING_POLL_SECONDS", "300"))
        except ValueError as error: raise ValueError("PAPER_TRADING_POLL_SECONDS must be an integer.") from error
        return cls(accepted[raw], poll)


@dataclass(frozen=True, slots=True)
class ForwardPaperRun:
    run_id: str
    started_at: datetime
    completed_at: datetime
    health: ForwardPaperHealth
    admitted: int = 0
    sessions_processed: int = 0
    entries: int = 0
    exits: int = 0
    marks: int = 0
    misses: int = 0
    ambiguous: int = 0
    failures: int = 0
    reason: str | None = None

    def __post_init__(self) -> None:
        for field in ("started_at", "completed_at"):
            value = getattr(self, field)
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("FORWARD_PAPER_RUN_TIMESTAMP_REQUIRED")
        if self.completed_at < self.started_at:
            raise ValueError("FORWARD_PAPER_RUN_CHRONOLOGY_INVALID")
        if any(value < 0 for value in (
            self.admitted, self.sessions_processed, self.entries, self.exits,
            self.marks, self.misses, self.ambiguous, self.failures,
        )):
            raise ValueError("FORWARD_PAPER_RUN_COUNTS_INVALID")


def admission_from_prebreakout(candidate: PreBreakoutCandidate, *, time_stop_sessions: int,
                               source_artifact_fingerprint: str | None = None,
                               brain_version: str | None = None, brain_fingerprint: str | None = None,
                               diagnostic_fingerprint: str | None = None,
                               financial_semantic_fingerprint: str | None = None) -> PaperStudyAdmission:
    """The single V1 adapter; it never derives economics from a score."""
    if candidate.actual_execution_price is not None or candidate.formation_blockers:
        raise ValueError("PAPER_STUDY_PREBREAKOUT_NOT_EXECUTABLE")
    return PaperStudyAdmission(
        canonical_instrument_id=candidate.instrument_id, setup_id=candidate.candidate_id,
        setup_fingerprint=candidate.fingerprint,
        source_artifact_fingerprint=source_artifact_fingerprint or candidate.assessment_fingerprint,
        strategy_version=candidate.policy_version, policy_fingerprint=candidate.policy_fingerprint,
        decision_as_of=candidate.evaluation_as_of,
        trigger=candidate.breakout_confirmation_trigger, structural_stop=candidate.final_structural_stop,
        target=candidate.measured_move_target, maximum_entry=candidate.maximum_executable_entry_price,
        time_stop_sessions=time_stop_sessions, sector=candidate.sector,
        sector_context_fingerprint=candidate.selection_fingerprint, brain_version=brain_version,
        brain_fingerprint=brain_fingerprint, decision_score=None,
        diagnostic_fingerprint=diagnostic_fingerprint,
        financial_semantic_fingerprint=financial_semantic_fingerprint,
    )


def rebuild_snapshot(study: ForwardPaperStudy, events: Iterable[ForwardPaperEvent]) -> ForwardPaperSnapshot:
    ordered = tuple(sorted(events, key=lambda item: (item.session_at or item.occurred_at, item.occurred_at, item.event_id)))
    entry = next((item for item in ordered if item.kind is PaperEventKind.ENTRY_FILLED), None)
    exit_event = next((item for item in reversed(ordered) if item.kind in {
        PaperEventKind.STOP_EXIT, PaperEventKind.TARGET_EXIT, PaperEventKind.TIME_STOP_EXIT,
    }), None)
    ambiguous = any(item.kind is PaperEventKind.PATH_AMBIGUOUS for item in ordered)
    invalid = any(item.kind in {PaperEventKind.DATA_INVALIDATED, PaperEventKind.CORPORATE_ACTION_REVIEW_REQUIRED} for item in ordered)
    missed = any(item.kind is PaperEventKind.ENTRY_MISSED_DO_NOT_CHASE for item in ordered)
    expired = any(item.kind is PaperEventKind.EXPIRED_UNFILLED for item in ordered)
    marks = tuple(item for item in ordered if item.kind is PaperEventKind.SESSION_MARK)
    last = max((item.session_at for item in ordered if item.session_at is not None), default=None)
    if invalid: state = PaperStudyState.INVALID_DATA
    elif ambiguous: state = PaperStudyState.AMBIGUOUS
    elif exit_event is not None: state = PaperStudyState.CLOSED
    elif missed: state = PaperStudyState.MISSED_DO_NOT_CHASE
    elif expired: state = PaperStudyState.EXPIRED_UNFILLED
    elif entry is not None: state = PaperStudyState.OPEN
    else: state = PaperStudyState.WAITING_FOR_TRIGGER
    exit_reason = ({PaperEventKind.STOP_EXIT: PaperExitReason.STOP, PaperEventKind.TARGET_EXIT: PaperExitReason.TARGET,
                    PaperEventKind.TIME_STOP_EXIT: PaperExitReason.TIME_STOP}.get(exit_event.kind) if exit_event else
                   PaperExitReason.AMBIGUOUS_PATH if ambiguous else
                   PaperExitReason.DATA_INVALIDATED if any(item.kind is PaperEventKind.DATA_INVALIDATED for item in ordered) else
                   PaperExitReason.CORPORATE_ACTION_REVIEW_REQUIRED if invalid else None)
    excursions = (*marks, *((exit_event,) if exit_event is not None else ()))
    mfe = max((item.mfe_r for item in excursions if item.mfe_r is not None), default=None)
    mae = min((item.mae_r for item in excursions if item.mae_r is not None), default=None)
    return ForwardPaperSnapshot(study.study_id, state, entry.price if entry else None,
        entry.session_at if entry else None, exit_event.price if exit_event else None,
        exit_event.session_at if exit_event else None, exit_reason,
        exit_event.gross_r if exit_event else None, exit_event.net_r if exit_event else None,
        mfe, mae, exit_event.sessions_held if exit_event and exit_event.sessions_held is not None else
        (marks[-1].sessions_held if marks and marks[-1].sessions_held is not None else 0),
        exit_event.benchmark_return if exit_event else None,
        exit_event.sector_benchmark_return if exit_event else None, len(ordered), last)


class ForwardPaperEvaluator:
    """Stored-bar evaluator.  Its input contract intentionally has no provider."""
    def evaluate(self, study: ForwardPaperStudy, events: Iterable[ForwardPaperEvent], bars: Iterable[ForwardPaperBar], *,
                 processing_as_of: datetime) -> tuple[ForwardPaperEvent, ...]:
        if processing_as_of.tzinfo is None or processing_as_of.utcoffset() is None:
            raise ValueError("PAPER_PROCESSING_CUTOFF_REQUIRED")
        prior = tuple(events); view = rebuild_snapshot(study, prior)
        if view.state not in {PaperStudyState.WAITING_FOR_TRIGGER, PaperStudyState.OPEN}: return ()
        values = tuple(
            bar for bar in bars
            if bar.known_at <= processing_as_of
            and bar.session_at <= processing_as_of
            and is_strictly_future_nse_session(bar.session_at, study.admission.decision_as_of)
            and (view.last_session is None or nse_session_date(bar.session_at) > nse_session_date(view.last_session))
        )
        previous_session = None
        for bar in values:
            session = nse_session_date(bar.session_at)
            if previous_session is not None and session <= previous_session:
                raise ValueError("FORWARD_PAPER_CANONICAL_SESSION_SEQUENCE_INVALID")
            previous_session = session
        produced: list[ForwardPaperEvent] = []
        for bar in values:
            if not bar.valid:
                produced.append(self._event(study, PaperEventKind.DATA_INVALIDATED, bar, "INVALID_MARKET_DATA")); break
            if bar.corporate_action_requires_review:
                produced.append(self._event(study, PaperEventKind.CORPORATE_ACTION_REVIEW_REQUIRED, bar, "CORPORATE_ACTION_REVIEW_REQUIRED")); break
            current = rebuild_snapshot(study, (*prior, *produced))
            if current.state is PaperStudyState.WAITING_FOR_TRIGGER:
                produced.extend(self._waiting(study, prior, produced, bar))
            elif current.state is PaperStudyState.OPEN:
                produced.extend(self._open(study, prior, produced, bar, current))
            current = rebuild_snapshot(study, (*prior, *produced))
            if current.state not in {PaperStudyState.WAITING_FOR_TRIGGER, PaperStudyState.OPEN}: break
        return tuple(produced)

    def _waiting(self, study, prior, produced, bar):
        waiting_sessions = sum(1 for item in (*prior, *produced) if item.kind in {PaperEventKind.SESSION_MARK, PaperEventKind.TRIGGER_OBSERVED})
        a = study.admission
        if bar.open >= a.trigger and a.maximum_entry is not None and bar.open > a.maximum_entry:
            return [self._event(study, PaperEventKind.ENTRY_MISSED_DO_NOT_CHASE, bar, "OPEN_ABOVE_MAXIMUM_ENTRY")]
        triggered = bar.open >= a.trigger or (bar.low <= a.trigger <= bar.high)
        if not triggered:
            if waiting_sessions >= a.time_stop_sessions:
                return [self._event(study, PaperEventKind.EXPIRED_UNFILLED, bar, "UNFILLED_HORIZON_EXPIRED")]
            return [self._event(study, PaperEventKind.SESSION_MARK, bar, "WAITING_SESSION", sessions_held=0)]
        fill = (bar.open if bar.open >= a.trigger else a.trigger) + study.execution_model.entry_slippage
        if a.maximum_entry is not None and fill > a.maximum_entry:
            return [self._event(study, PaperEventKind.ENTRY_MISSED_DO_NOT_CHASE, bar, "FILL_ABOVE_MAXIMUM_ENTRY")]
        base = [self._event(study, PaperEventKind.TRIGGER_OBSERVED, bar, "GOVERNED_TRIGGER_CROSSED"),
                self._event(study, PaperEventKind.ENTRY_FILLED, bar, "FORWARD_SIMULATED_ENTRY", price=fill,
                            close=bar.benchmark_close, high=bar.sector_benchmark_close)]
        if bar.low <= a.structural_stop or bar.high >= a.target:
            base.append(self._event(study, PaperEventKind.PATH_AMBIGUOUS, bar, "ENTRY_BAR_PATH_UNRESOLVED", price=fill))
        else:
            base.append(self._mark(study, bar, fill, bar.high, bar.low, 1, bar.benchmark_close, bar.sector_benchmark_close))
        return base

    def _open(self, study, prior, produced, bar, view):
        assert view.entry_price is not None and view.entry_session is not None
        entry, a = view.entry_price, study.admission
        sessions = view.sessions_held + 1
        if bar.open <= a.structural_stop:
            price = bar.open - study.execution_model.exit_slippage
            return [self._exit(study, PaperEventKind.STOP_EXIT, bar, entry, price, sessions, "GAP_THROUGH_STOP", prior, produced)]
        stop_hit, target_hit = bar.low <= a.structural_stop, bar.high >= a.target
        if stop_hit and target_hit:
            return [self._event(study, PaperEventKind.PATH_AMBIGUOUS, bar, "STOP_TARGET_PATH_UNRESOLVED", sessions_held=sessions)]
        if stop_hit:
            return [self._exit(study, PaperEventKind.STOP_EXIT, bar, entry, a.structural_stop - study.execution_model.exit_slippage, sessions, "STRUCTURAL_STOP", prior, produced)]
        if target_hit:
            return [self._exit(study, PaperEventKind.TARGET_EXIT, bar, entry, a.target - study.execution_model.exit_slippage, sessions, "GOVERNED_TARGET", prior, produced)]
        mark = self._mark(study, bar, entry, bar.high, bar.low, sessions, bar.benchmark_close, bar.sector_benchmark_close)
        if sessions >= a.time_stop_sessions:
            exit_event = self._exit(study, PaperEventKind.TIME_STOP_EXIT, bar, entry, bar.close - study.execution_model.exit_slippage,
                                    sessions, "GOVERNED_TIME_STOP", prior, (*produced, mark))
            return [mark, exit_event]
        return [mark]

    def _mark(self, study, bar, entry, high, low, sessions, benchmark_start, sector_start):
        risk = entry - study.admission.structural_stop
        return self._event(study, PaperEventKind.SESSION_MARK, bar, "FORWARD_MARK", close=bar.close, high=high, low=low,
                           gross_r=(bar.close-entry)/risk, mfe_r=(high-entry)/risk, mae_r=(low-entry)/risk,
                           sessions_held=sessions)

    def _exit(self, study, kind, bar, entry, price, sessions, reason, prior, produced):
        risk = entry - study.admission.structural_stop
        gross, net = (price-entry)/risk, (price-entry-study.execution_model.round_trip_friction)/risk
        entered = next(item for item in (*prior, *produced) if item.kind is PaperEventKind.ENTRY_FILLED)
        marks = tuple(item for item in (*prior, *produced) if item.kind is PaperEventKind.SESSION_MARK)
        mfe = max((*(item.mfe_r for item in marks if item.mfe_r is not None), (bar.high-entry)/risk), default=None)
        mae = min((*(item.mae_r for item in marks if item.mae_r is not None), (bar.low-entry)/risk), default=None)
        benchmark = ((bar.benchmark_close-entered.close)/entered.close if entered.close and bar.benchmark_close is not None else None)
        sector = ((bar.sector_benchmark_close-entered.high)/entered.high if entered.high and bar.sector_benchmark_close is not None else None)
        return self._event(study, kind, bar, reason, price=price, gross_r=gross, net_r=net, sessions_held=sessions,
                           mfe_r=mfe, mae_r=mae, benchmark_return=benchmark, sector_benchmark_return=sector)

    def _event(self, study, kind, bar, reason, **values):
        return ForwardPaperEvent.create(event_id=f"{study.study_id}:{kind.value}:{bar.bar_id}", study_id=study.study_id,
            kind=kind, occurred_at=bar.known_at, session_at=bar.session_at, bar_id=bar.bar_id, reason=reason, **values)


class ForwardPaperService:
    _locks: defaultdict[str, Lock] = defaultdict(Lock)
    def __init__(self, store: ForwardPaperStore, evaluator: ForwardPaperEvaluator | None = None) -> None:
        self._store, self._evaluator = store, evaluator or ForwardPaperEvaluator()

    def admit(self, admission: PaperStudyAdmission, execution_model, *, created_at: datetime) -> tuple[ForwardPaperStudy, bool]:
        study = ForwardPaperStudy.create(admission, execution_model, created_at=created_at)
        inserted = self._store.save_study(study)
        if inserted:
            self._store.save_event(ForwardPaperEvent.create(event_id=f"{study.study_id}:STUDY_ADMITTED", study_id=study.study_id,
                kind=PaperEventKind.STUDY_ADMITTED, occurred_at=created_at, session_at=None, bar_id=None, reason="GOVERNED_EXECUTABLE_SETUP_ADMITTED"))
        return study, inserted

    def evaluate(self, study_id: str, bars: Iterable[ForwardPaperBar], *, processing_as_of: datetime) -> ForwardPaperSnapshot:
        lock = self._locks[study_id]
        with lock:
            study = self._store.get_study(study_id)
            if study is None: raise ValueError("FORWARD_PAPER_STUDY_NOT_FOUND")
            existing = self._store.events(study_id)
            for item in self._evaluator.evaluate(study, existing, bars, processing_as_of=processing_as_of): self._store.save_event(item)
            return rebuild_snapshot(study, self._store.events(study_id))

    def snapshot(self, study_id: str) -> ForwardPaperSnapshot:
        study = self._store.get_study(study_id)
        if study is None: raise ValueError("FORWARD_PAPER_STUDY_NOT_FOUND")
        return rebuild_snapshot(study, self._store.events(study_id))

    def performance(self, *, generated_at: datetime, strategy_version: str | None = None,
                    brain_version: str | None = None, sector: str | None = None,
                    market_regime: str | None = None) -> PaperTradingPerformanceEvidence:
        selected = tuple(study for study in self._store.studies() if
                         (strategy_version is None or study.admission.strategy_version == strategy_version) and
                         (brain_version is None or study.admission.brain_version == brain_version) and
                         (sector is None or study.admission.sector == sector) and
                         (market_regime is None or study.admission.market_regime == market_regime))
        views = tuple(rebuild_snapshot(study, self._store.events(study.study_id)) for study in selected)
        eligible = tuple(item for item in views if item.state is PaperStudyState.CLOSED and item.net_r is not None)
        values = tuple(item.net_r for item in eligible if item.net_r is not None)
        def average(source): return sum(source, Decimal("0")) / Decimal(len(source)) if source else None
        def middle(source): return Decimal(str(median(source))) if source else None
        positive = sum((value for value in values if value > 0), Decimal("0")); negative = -sum((value for value in values if value < 0), Decimal("0"))
        groups: dict[str, list[Decimal]] = defaultdict(list)
        for study, view in zip(selected, views):
            if view.net_r is not None: groups[f"strategy={study.admission.strategy_version}|brain={study.admission.brain_version or 'UNAVAILABLE'}"].append(view.net_r)
        count = Decimal(len(eligible))
        return PaperTradingPerformanceEvidence(generated_at, len(selected), len(eligible),
            sum(value > 0 for value in values), sum(value < 0 for value in values),
            sum(item.state is PaperStudyState.EXPIRED_UNFILLED for item in views),
            sum(item.state is PaperStudyState.MISSED_DO_NOT_CHASE for item in views),
            sum(item.state is PaperStudyState.AMBIGUOUS for item in views), sum(item.state is PaperStudyState.INVALID_DATA for item in views),
            (Decimal(sum(value > 0 for value in values))/count if count else None), average(values), average(values), middle(values),
            average(tuple(item.mfe_r for item in eligible if item.mfe_r is not None)), middle(tuple(item.mfe_r for item in eligible if item.mfe_r is not None)),
            average(tuple(item.mae_r for item in eligible if item.mae_r is not None)), middle(tuple(item.mae_r for item in eligible if item.mae_r is not None)),
            (positive/negative if negative else None),
            (Decimal(sum(item.exit_reason is PaperExitReason.TARGET for item in eligible))/count if count else None),
            (Decimal(sum(item.exit_reason is PaperExitReason.STOP for item in eligible))/count if count else None),
            (Decimal(sum(item.exit_reason is PaperExitReason.TIME_STOP for item in eligible))/count if count else None),
            middle(tuple(Decimal(item.sessions_held) for item in eligible)),
            tuple((key, len(value), average(value)) for key, value in sorted(groups.items())))


class ForwardPaperOrchestrator:
    """Explicit, dependency-injected automatic loop; it never fetches providers."""
    def __init__(self, service: ForwardPaperService, *, execution_model, admissions: Callable[[datetime], Iterable[PaperStudyAdmission]],
                 bars_for: Callable[[ForwardPaperStudy, datetime], Iterable[ForwardPaperBar]],
                 data_ready: Callable[[datetime], bool], clock: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        self._service, self._execution_model, self._admissions, self._bars_for, self._data_ready, self._clock = service, execution_model, admissions, bars_for, data_ready, clock

    def run_once(self, *, processing_as_of: datetime | None = None) -> ForwardPaperRun:
        started = self._clock(); cutoff = processing_as_of or started
        if not self._data_ready(cutoff):
            return ForwardPaperRun(f"forward-paper-run:{uuid4()}", started, self._clock(), ForwardPaperHealth.BLOCKED_DATA, reason="REQUIRED_STORED_DATA_UNAVAILABLE")
        admitted = entries = exits = marks = misses = ambiguous = sessions = failures = 0
        for admission in self._admissions(cutoff):
            try:
                study, added = self._service.admit(admission, self._execution_model, created_at=cutoff); admitted += int(added)
                before = self._service.snapshot(study.study_id)
                after = self._service.evaluate(study.study_id, self._bars_for(study, cutoff), processing_as_of=cutoff)
                events = self._service._store.events(study.study_id)
                added_events = events[before.event_count:]
                entries += sum(item.kind is PaperEventKind.ENTRY_FILLED for item in added_events)
                exits += sum(item.kind in {PaperEventKind.STOP_EXIT, PaperEventKind.TARGET_EXIT, PaperEventKind.TIME_STOP_EXIT} for item in added_events)
                marks += sum(item.kind is PaperEventKind.SESSION_MARK for item in added_events)
                misses += sum(item.kind is PaperEventKind.ENTRY_MISSED_DO_NOT_CHASE for item in added_events)
                ambiguous += sum(item.kind is PaperEventKind.PATH_AMBIGUOUS for item in added_events)
                sessions += max(0, after.event_count - before.event_count)
            except ValueError as error:
                # StoredForwardPaperComposition raises this only after its
                # durable per-instrument conflict lookup.  Do not turn it
                # into a generic evaluator failure or continue processing
                # the study as if canonical OHLCV were clean.
                if str(error) == "OHLCV_CONFLICTED":
                    return ForwardPaperRun(
                        f"forward-paper-run:{uuid4()}", started, self._clock(),
                        ForwardPaperHealth.BLOCKED_DATA, admitted, sessions, entries, exits,
                        marks, misses, ambiguous, failures, reason="OHLCV_CONFLICTED",
                    )
                failures += 1
        health = ForwardPaperHealth.HEALTHY if not failures else ForwardPaperHealth.DEGRADED
        return ForwardPaperRun(f"forward-paper-run:{uuid4()}", started, self._clock(), health, admitted, sessions, entries, exits, marks, misses, ambiguous, failures)


class ForwardPaperWorker:
    """Optional local timer around the stored-only paper orchestrator.

    It is never started by imports, FastAPI startup, or a production-cycle
    invocation.  The caller must explicitly provide ``enabled=True`` through
    :class:`PaperTradingSettings`.
    """

    def __init__(
        self,
        orchestrator: ForwardPaperOrchestrator,
        settings: PaperTradingSettings,
        *,
        record_run: Callable[[ForwardPaperRun], object] | None = None,
        wait: Callable[[float], bool] | None = None,
        thread_factory: Callable[..., Thread] = Thread,
    ) -> None:
        self._orchestrator, self._settings, self._record_run = orchestrator, settings, record_run
        self._stop = Event()
        self._wait = wait or self._stop.wait
        self._thread_factory, self._thread = thread_factory, None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> bool:
        if not self._settings.enabled or self.running:
            return False
        self._stop.clear()
        self._thread = self._thread_factory(target=self.run_forever, name="forward-paper-worker", daemon=True)
        self._thread.start()
        return True

    def stop(self, *, join_timeout: float = 2.0) -> bool:
        if not self.running:
            return False
        self._stop.set()
        self._thread.join(join_timeout)
        return True

    def run_forever(self, *, max_ticks: int | None = None) -> bool:
        if not self._settings.enabled:
            return False
        ticks = 0
        while not self._stop.is_set():
            result = self._orchestrator.run_once()
            if self._record_run is not None:
                self._record_run(result)
            ticks += 1
            if max_ticks is not None and ticks >= max_ticks:
                break
            if self._wait(self._settings.poll_seconds):
                break
        return True
