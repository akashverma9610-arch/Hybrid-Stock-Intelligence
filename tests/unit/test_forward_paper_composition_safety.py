from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.domain.models import DataQuality
from app.forward_paper.composition import (
    StoredExecutableSetup,
    StoredExecutableSetupStore,
    StoredForwardPaperComposition,
)
from app.forward_paper.models import ForwardPaperBar, PaperExecutionModel, PaperStudyAdmission
from app.forward_paper.service import ForwardPaperOrchestrator, ForwardPaperService, PaperTradingSettings
from app.forward_paper.store import ForwardPaperStore
from app.market_data.models import AdjustmentStatus, CanonicalOHLCVBar, MarketDataProvenance, Timeframe
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository


T0 = datetime(2026, 8, 3, 9, tzinfo=UTC)  # 14:30 Asia/Kolkata, during T0.
T1 = T0 + timedelta(days=1)


def setup() -> StoredExecutableSetup:
    return StoredExecutableSetup.create(
        setup_id="setup:fixture", canonical_instrument_id="NSE:FIXTURE", setup_fingerprint="setup-fingerprint",
        source_candidate_fingerprint="assessment-fingerprint", strategy_version="v1.3", policy_fingerprint="policy-fingerprint",
        decision_as_of=T0, trigger=Decimal("100"), structural_stop=Decimal("95"), target=Decimal("115"),
        maximum_entry=Decimal("103"), time_stop_sessions=5, sector="Metals & Mining",
        sector_context_fingerprint="selection-fingerprint",
    )


def canonical_bar(name: str, at: datetime, *, instrument_id: str = "NSE:FIXTURE") -> CanonicalOHLCVBar:
    return CanonicalOHLCVBar(
        name, SimpleNamespace(instrument_id=instrument_id), Timeframe.DAILY,
        at - timedelta(hours=6), at, Decimal("99"), Decimal("101"), Decimal("98"), Decimal("100"),
        10, None, None, AdjustmentStatus.UNKNOWN,
        MarketDataProvenance("fixture", "fixture", at, at, at, "v1"), DataQuality.HIGH,
    )


class _History:
    def __init__(self, bars=(), *, conflicted: bool = False) -> None:
        self._bars = tuple(bars)
        self._conflicted = conflicted
        self.calls = 0

    def has_conflict_artifact(self, _instrument_id: str) -> bool:
        return self._conflicted

    def range(self, *_args, **_kwargs):
        self.calls += 1
        return self._bars


def composition(history: _History):
    repository = SQLiteCoreApiSnapshotRepository(":memory:")
    setups = StoredExecutableSetupStore(repository)
    assert setups.save(setup())
    return StoredForwardPaperComposition(setups, history), setup().admission()


def model() -> PaperExecutionModel:
    return PaperExecutionModel.create(
        version="paper-execution-v1", entry_slippage=Decimal("0"),
        exit_slippage=Decimal("0"), round_trip_friction=Decimal("0"),
    )


def test_stored_composition_excludes_t0_by_nse_session_date_and_admits_t1_only() -> None:
    source, admission = composition(_History((
        canonical_bar("t0-after-decision", T0 + timedelta(hours=2)),
        canonical_bar("t1", T1 + timedelta(hours=2)),
    )))

    bars = source.bars_for(admission, start=T0 - timedelta(days=1), end=T1 + timedelta(days=2))

    assert tuple(item.bar_id for item in bars) == ("t1",)


def test_evaluator_excludes_same_nse_session_even_when_timestamp_is_after_decision() -> None:
    repository = SQLiteCoreApiSnapshotRepository(":memory:")
    from app.forward_paper.store import ForwardPaperStore
    paper = ForwardPaperService(ForwardPaperStore(repository))
    study, _ = paper.admit(setup().admission(), model(), created_at=T0)
    t0_later = ForwardPaperBar("t0-later", T0 + timedelta(hours=2), T0 + timedelta(hours=2), Decimal("99"), Decimal("101"), Decimal("98"), Decimal("100"))
    t1 = ForwardPaperBar("t1", T1, T1, Decimal("99"), Decimal("101"), Decimal("98"), Decimal("100"))

    snapshot = paper.evaluate(study.study_id, (t0_later, t1), processing_as_of=T1)

    assert snapshot.entry_session == T1


def test_composition_fails_closed_for_duplicate_or_nonmonotonic_canonical_sessions() -> None:
    duplicate, admission = composition(_History((
        canonical_bar("one", T1), canonical_bar("two", T1 + timedelta(hours=1)),
    )))
    with pytest.raises(ValueError, match="FORWARD_PAPER_CANONICAL_SESSION_SEQUENCE_INVALID"):
        duplicate.bars_for(admission, start=T0, end=T1 + timedelta(days=2))

    nonmonotonic, admission = composition(_History((
        canonical_bar("t2", T1 + timedelta(days=1)), canonical_bar("t1", T1),
    )))
    with pytest.raises(ValueError, match="FORWARD_PAPER_CANONICAL_SESSION_SEQUENCE_INVALID"):
        nonmonotonic.bars_for(admission, start=T0, end=T1 + timedelta(days=2))


def test_composition_blocks_conflicted_or_mismatched_canonical_identity() -> None:
    conflicted, admission = composition(_History(conflicted=True))
    with pytest.raises(ValueError, match="OHLCV_CONFLICTED"):
        conflicted.bars_for(admission, start=T0, end=T1)

    mismatched, admission = composition(_History((canonical_bar("wrong", T1, instrument_id="NSE:OTHER"),)))
    with pytest.raises(ValueError, match="FORWARD_PAPER_CANONICAL_INSTRUMENT_IDENTITY_MISMATCH"):
        mismatched.bars_for(admission, start=T0, end=T1)


def test_study_admission_is_immutable_idempotent_and_future_bars_do_not_mutate_setup() -> None:
    repository = SQLiteCoreApiSnapshotRepository(":memory:")
    from app.forward_paper.store import ForwardPaperStore
    paper = ForwardPaperService(ForwardPaperStore(repository))
    admission = setup().admission()
    first, inserted = paper.admit(admission, model(), created_at=T0)
    second, duplicate = paper.admit(admission, model(), created_at=T0)
    t1 = ForwardPaperBar("t1", T1, T1, Decimal("99"), Decimal("101"), Decimal("98"), Decimal("100"))
    paper.evaluate(first.study_id, (t1,), processing_as_of=T1)

    assert inserted is True and duplicate is False and first == second
    assert first.admission == admission


def test_no_future_bar_is_waiting_not_a_source_failure_and_no_provider_is_available() -> None:
    history = _History(())
    source, admission = composition(history)

    assert source.bars_for(admission, start=T0, end=T1) == ()
    assert history.calls == 1
    assert PaperTradingSettings.from_environment({}).enabled is False


def test_worker_consumes_only_the_durable_setup_composition_and_t1_canonical_bar() -> None:
    history = _History((canonical_bar("t1", T1),))
    source, _ = composition(history)
    repository = SQLiteCoreApiSnapshotRepository(":memory:")
    paper = ForwardPaperService(ForwardPaperStore(repository))
    worker = ForwardPaperOrchestrator(
        paper, execution_model=model(), admissions=lambda at: source.admissions(as_of=at),
        bars_for=lambda study, at: source.bars_for(study.admission, start=study.admission.decision_as_of, end=at),
        data_ready=lambda _: True, clock=lambda: T1,
    )

    result = worker.run_once()

    assert result.admitted == 1 and history.calls == 1
    assert len(paper._store.studies()) == 1
