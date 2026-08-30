from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.forward_paper.composition import StoredForwardPaperComposition
from app.intelligence.shared_brain_application import _OhlcvConflictEvidenceSource
from app.intelligence.unified_state import IntelligenceEvidenceAvailability, IntelligenceEvidenceDomain
from app.market_data.ohlcv_readiness import OhlcvReadinessService, OhlcvReadinessStatus
from app.market_data.models import Timeframe


T = datetime(2026, 8, 30, tzinfo=UTC)


class _History:
    def __init__(self, *, bars: dict[str, tuple[object, ...]] = (), conflicts: set[str] | None = None) -> None:
        self._bars = dict(bars)
        self._conflicts = set(conflicts or ())
        self.provider_calls = 0

    def latest(self, instrument_id, timeframe, count, *, as_of=None):
        assert timeframe is Timeframe.DAILY
        return self._bars.get(instrument_id, ())[-count:]

    def list_conflict_artifacts(self, *, instrument_id=None):
        if instrument_id in self._conflicts:
            return (SimpleNamespace(conflict_fingerprint=f"conflict:{instrument_id}", detected_at=T),)
        return ()

    def has_conflict_artifact(self, instrument_id):
        return instrument_id in self._conflicts

    def range(self, instrument_id, timeframe, start, end, *, as_of=None):
        return self._bars.get(instrument_id, ())


def _bars(count: int, *, latest: datetime = T) -> tuple[object, ...]:
    return tuple(SimpleNamespace(end_time=latest - timedelta(days=count - index - 1)) for index in range(count))


def test_conflict_is_instrument_local_and_healthy_peer_remains_ready() -> None:
    history = _History(bars={"NSE:CONFLICT": _bars(252), "NSE:HEALTHY": _bars(252)}, conflicts={"NSE:CONFLICT"})
    service = OhlcvReadinessService(history)

    conflict = service.assess("NSE:CONFLICT", required_latest_at=T)
    healthy = service.assess("NSE:HEALTHY", required_latest_at=T)

    assert conflict.status is OhlcvReadinessStatus.CONFLICTED
    assert conflict.conflict_fingerprints == ("conflict:NSE:CONFLICT",)
    assert healthy.status is OhlcvReadinessStatus.READY
    assert healthy.conflict_fingerprints == () and history.provider_calls == 0


def test_insufficient_stale_unmapped_and_unavailable_remain_distinct() -> None:
    service = OhlcvReadinessService(_History(bars={"NSE:SHORT": _bars(251), "NSE:STALE": _bars(252, latest=T - timedelta(days=1))}))

    assert service.assess("NSE:SHORT", required_latest_at=T).status is OhlcvReadinessStatus.INSUFFICIENT_HISTORY
    assert service.assess("NSE:STALE", required_latest_at=T).status is OhlcvReadinessStatus.STALE
    assert service.assess("NSE:UNMAPPED", mapping_available=False).status is OhlcvReadinessStatus.MAPPING_UNAVAILABLE
    assert service.assess("NSE:EMPTY").status is OhlcvReadinessStatus.UNAVAILABLE


def test_coverage_is_factual_and_has_no_percentage_threshold() -> None:
    history = _History(bars={"NSE:HEALTHY": _bars(252), "NSE:SHORT": _bars(10)}, conflicts={"NSE:CONFLICT"})
    service = OhlcvReadinessService(history)
    coverage, rows = service.coverage(("NSE:HEALTHY", "NSE:SHORT", "NSE:CONFLICT", "NSE:UNMAPPED"), mapping_available=lambda value: value != "NSE:UNMAPPED", required_latest_at=T)

    assert [item.status for item in rows] == [
        OhlcvReadinessStatus.CONFLICTED, OhlcvReadinessStatus.READY,
        OhlcvReadinessStatus.INSUFFICIENT_HISTORY, OhlcvReadinessStatus.MAPPING_UNAVAILABLE,
    ]
    assert (coverage.total, coverage.healthy_ready, coverage.conflicted, coverage.insufficient, coverage.unmapped) == (4, 1, 1, 1, 1)
    assert "percent" not in OhlcvReadinessService.__doc__.lower()


def test_forward_paper_composition_never_admits_or_binds_conflicted_ohlcv() -> None:
    history = _History(conflicts={"NSE:CONFLICT"})
    setup = SimpleNamespace(canonical_instrument_id="NSE:CONFLICT", admission=lambda: "admission")
    composition = StoredForwardPaperComposition(SimpleNamespace(list=lambda *, as_of: (setup,)), history)

    assert composition.admissions(as_of=T) == ()
    with pytest.raises(ValueError, match="OHLCV_CONFLICTED"):
        composition.bars_for(SimpleNamespace(canonical_instrument_id="NSE:CONFLICT"), start=T - timedelta(days=1), end=T)


def test_shared_brain_conflict_evidence_preserves_auditable_market_blocker() -> None:
    source = _OhlcvConflictEvidenceSource(_History(conflicts={"NSE:CONFLICT"}))
    artifact = source.list_stored_intelligence_artifacts("NSE:CONFLICT", as_of=T)[0]

    assert artifact.domain is IntelligenceEvidenceDomain.MARKET_DATA
    assert artifact.availability is IntelligenceEvidenceAvailability.CONFLICTED
    assert artifact.warnings == ("OHLCV_CONFLICTED",)
    assert source.list_stored_intelligence_artifacts("NSE:HEALTHY", as_of=T) == ()
