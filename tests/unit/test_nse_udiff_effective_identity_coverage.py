from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime

import pytest

from app.historical.nse_udiff_effective_identity_coverage import (
    NseUdiffActionWindowCoverageState, NseUdiffEffectiveIdentityCoverageIndex,
    NseUdiffIdentityAnchor, NseUdiffIdentitySourceObservation,
    build_effective_identity_coverage_plan, compose_action_window_coverage,
)
from app.historical.nse_corporate_action_coverage import NseCorporateActionQueryStatus


AT = datetime(2026, 9, 6, 12, tzinfo=UTC)
INSTRUMENT = "NSE:INE000A01001"
ISIN = "INE000A01001"
DAYS = (date(2024, 7, 8), date(2024, 7, 9), date(2024, 7, 10))


def observation(day: date, *, series: str = "EQ", symbol: str = "ALPHA", token: str = "101", isin: str = ISIN, source_id: str | None = None):
    return NseUdiffIdentitySourceObservation(
        INSTRUMENT, isin, token, symbol, series, day, "F1",
        source_id or f"nse-udiff-source-row:{day:%Y%m%d}:{series}:{token}",
        "nse-udiff-artifact:fixture", AT,
    )


def anchor():
    return NseUdiffIdentityAnchor(INSTRUMENT, ISIN, "universe-snapshot:fixture", "sha256:" + "a" * 64)


def plan(rows=DAYS, **kwargs):
    return build_effective_identity_coverage_plan(
        observations=tuple(observation(day) for day in rows), anchors=(anchor(),), session_dates=DAYS,
        session_manifest_id="nse-udiff-session-manifest:fixture", session_manifest_fingerprint="sha256:" + "b" * 64,
        **kwargs,
    )


def test_ordinary_unchanged_history_is_one_compact_interval_not_one_receipt_per_bar():
    value = plan()
    assert len(value.intervals) == 1
    assert value.intervals[0].source_observation_count == 3
    assert not hasattr(value.intervals[0], "source_observation_ids")
    assert value.receipt.compact_source_observation_count == 3


def test_index_is_deterministic_and_never_uses_current_symbol_fallback():
    value = plan()
    index = NseUdiffEffectiveIdentityCoverageIndex(reversed(value.intervals))
    assert index.resolve(canonical_instrument_id=INSTRUMENT, isin=ISIN, fin_instrm_id="101", source_symbol="ALPHA", source_series="EQ", trade_date=DAYS[1], source_observation_id="nse-udiff-source-row:any") == value.intervals[0]
    assert index.resolve(canonical_instrument_id=INSTRUMENT, isin=ISIN, fin_instrm_id="101", source_symbol="RENAMED", source_series="EQ", trade_date=DAYS[1], source_observation_id="nse-udiff-source-row:any") is None


def test_changed_isin_and_contrary_lifecycle_rows_fail_closed():
    value = build_effective_identity_coverage_plan(
        observations=(observation(DAYS[0], isin="INE999A01001"), observation(DAYS[1], source_id="nse-udiff-source-row:blocked")),
        anchors=(anchor(),), session_dates=DAYS, session_manifest_id="nse-udiff-session-manifest:fixture",
        session_manifest_fingerprint="sha256:" + "b" * 64,
        contrary_lifecycle_observation_ids=("nse-udiff-source-row:blocked",),
    )
    assert not value.intervals
    assert value.receipt.unresolved_source_observation_count == 2


@pytest.mark.parametrize("series", ("BL", "T0"))
def test_identity_may_cover_nonordinary_series_without_technical_selection(series):
    value = build_effective_identity_coverage_plan(
        observations=tuple(observation(day, series=series) for day in DAYS), anchors=(anchor(),), session_dates=DAYS,
        session_manifest_id="nse-udiff-session-manifest:fixture", session_manifest_fingerprint="sha256:" + "b" * 64,
    )
    assert value.intervals[0].source_series == series


@dataclass(frozen=True)
class Receipt:
    receipt_id: str
    fingerprint: str
    status: NseCorporateActionQueryStatus
    window: object
    observed_at: datetime


@dataclass(frozen=True)
class Window:
    start_date: date
    end_date: date


def success_receipt(start: date, end: date):
    return Receipt("nse-ca-receipt:fixture", "sha256:" + "c" * 64, NseCorporateActionQueryStatus.SUCCESS_EMPTY, Window(start, end), AT)


def test_successful_exchange_wide_empty_window_is_distinct_from_missing_query_evidence():
    intervals = plan().intervals
    ready = compose_action_window_coverage(canonical_instrument_id=INSTRUMENT, window_start=DAYS[0], window_end=DAYS[-1], identity_intervals=intervals, query_receipts=(success_receipt(DAYS[0], DAYS[-1]),), actions=(), evaluation_as_of=AT)
    missing = compose_action_window_coverage(canonical_instrument_id=INSTRUMENT, window_start=DAYS[0], window_end=DAYS[-1], identity_intervals=intervals, query_receipts=(), actions=(), evaluation_as_of=AT)
    assert ready.state is NseUdiffActionWindowCoverageState.READY
    assert ready.no_action_found_with_complete_query_coverage
    assert ready.assertion() is not None
    assert missing.state is NseUdiffActionWindowCoverageState.QUERY_COVERAGE_INCOMPLETE


def test_action_coverage_fails_closed_for_source_known_after_as_of_and_replay_is_identical():
    intervals = plan().intervals
    later = datetime(2026, 9, 7, tzinfo=UTC)
    first = compose_action_window_coverage(canonical_instrument_id=INSTRUMENT, window_start=DAYS[0], window_end=DAYS[-1], identity_intervals=intervals, query_receipts=(Receipt("nse-ca-receipt:fixture", "sha256:" + "c" * 64, NseCorporateActionQueryStatus.SUCCESS_EMPTY, Window(DAYS[0], DAYS[-1]), later),), actions=(), evaluation_as_of=AT)
    second = plan()
    assert first.state is NseUdiffActionWindowCoverageState.SOURCE_KNOWN_AFTER_AS_OF
    assert plan() == second


def test_source_gap_splits_intervals_and_blocks_required_window_lifecycle_coverage():
    gapped = plan(rows=(DAYS[0], DAYS[2]))
    assert len(gapped.intervals) == 2
    coverage = compose_action_window_coverage(
        canonical_instrument_id=INSTRUMENT, window_start=DAYS[0], window_end=DAYS[-1], identity_intervals=gapped.intervals,
        query_receipts=(success_receipt(DAYS[0], DAYS[-1]),), actions=(), evaluation_as_of=AT, required_sessions=DAYS,
    )
    assert coverage.state is NseUdiffActionWindowCoverageState.IDENTITY_COVERAGE_REQUIRED


def test_duplicate_source_rows_are_rejected():
    with pytest.raises(ValueError, match="SOURCE_DUPLICATE"):
        build_effective_identity_coverage_plan(
            observations=(observation(DAYS[0]), observation(DAYS[0])), anchors=(anchor(),), session_dates=DAYS,
            session_manifest_id="nse-udiff-session-manifest:fixture", session_manifest_fingerprint="sha256:" + "b" * 64,
        )
