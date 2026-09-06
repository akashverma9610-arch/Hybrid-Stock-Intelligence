from __future__ import annotations

import ast
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
import inspect
from pathlib import Path

import pytest

from app.historical.nse_capital_market_session_evidence_2022_2026 import nse_capital_market_calendar_2022_2026
from app.market_data.nse_udiff_daily_history import NseUdiffDailyStatus, _receipt as acquisition_receipt
from app.market_data.nse_udiff_daily_integrity import build_udiff_session_coverage_manifest
from app.market_data.nse_udiff_daily_technical_eligibility import (
    DailyTechnicalRequirement,
    DailyTechnicalRequirementProfile,
)
from app.market_data.nse_udiff_daily_technical_read import (
    NseUdiffDailyTechnicalReadEvidence,
    NseUdiffDailyTechnicalReadRequest,
    NseUdiffDailyTechnicalReadState,
    NseUdiffDailyTechnicalUseMode,
    read_certified_daily_technical_bars,
)
from app.market_data.nse_udiff_weekly_technical_bar import (
    NseUdiffWeeklyTechnicalBarError,
    NseUdiffWeeklyTechnicalBarWriteOutcome,
    NseUdiffWeeklyTechnicalDerivationRequest,
    NseUdiffWeeklyTechnicalReason,
    NseUdiffWeeklyTechnicalState,
    SQLiteNseUdiffWeeklyTechnicalBarStore,
    build_nse_udiff_weekly_session_plan,
    derive_nse_udiff_weekly_technical_bar,
    serialize_nse_udiff_weekly_technical_bar,
)
from tests.unit.test_nse_udiff_daily_technical_eligibility import AT, INSTRUMENT, action, bar, coverage, interval
from app.historical.security_master import CorporateActionKind


ACQUISITION = "nse-udiff-acquisition:fixture-weekly"


def weekdays(week_start: date) -> tuple[date, ...]:
    return tuple(date.fromordinal(week_start.toordinal() + offset) for offset in range(5))


def manifest(week_start: date, *, holidays: tuple[date, ...] = (), requested: tuple[date, ...] | None = None):
    values = weekdays(week_start) if requested is None else requested

    def receipt(day: date):
        state = NseUdiffDailyStatus.SOURCE_UNAVAILABLE if day in holidays else NseUdiffDailyStatus.ARTIFACT_VALID
        return acquisition_receipt(
            acquisition_id=ACQUISITION, trade_date=day, status=state, observed_at=AT,
            artifact_id="nse-udiff-artifact:fixture-" + day.isoformat() if state is NseUdiffDailyStatus.ARTIFACT_VALID else None,
            source_url="https://nsearchives.nseindia.com/content/cm/fixture.zip", rows_seen=0,
            eligible_rows=0, exact_identity_rows=0, identity_discontinuities=0,
            unresolved_identity_rows=0, invalid_rows=0, zero_volume_rows=0,
            inserted=0, duplicates=0, conflicts=0,
            error_code=None if state is NseUdiffDailyStatus.ARTIFACT_VALID else "NSE_UDIFF_ARTIFACT_UNAVAILABLE",
        )

    return build_udiff_session_coverage_manifest(
        acquisition_id=ACQUISITION, requested_dates=values, receipts=tuple(receipt(item) for item in values),
        calendar=nse_capital_market_calendar_2022_2026(), as_of=AT,
    )


def plan(week_start: date, *, holidays: tuple[date, ...] = (), requested: tuple[date, ...] | None = None):
    coverage_manifest = manifest(week_start, holidays=holidays, requested=requested)
    return build_nse_udiff_weekly_session_plan(
        week_start=week_start, coverage=coverage_manifest,
        calendar=nse_capital_market_calendar_2022_2026(),
    )


def daily_read(
    session_plan, *, series: str = "EQ", include: tuple[date, ...] | None = None,
    actions=(), provider: str = "nse_udiff_official", price_delta: int = 0,
):
    sessions = session_plan.expected_sessions
    selected = sessions if include is None else include
    rows = []
    for index, item in enumerate(selected):
        source = bar(item, series=series, token=str(100 + index), provider=provider)
        rows.append(replace(
            source, bar_id=f"weekly:{item.isoformat()}:{series}:{100 + index}",
            open=Decimal(100 + index + price_delta), high=Decimal(105 + index + price_delta),
            low=Decimal(99 - index + price_delta), close=Decimal(102 + index + price_delta),
            volume=1_000 + index, trade_count=50 + index,
        ))
    evidence = NseUdiffDailyTechnicalReadEvidence(
        sessions, tuple(rows), tuple(sorted((interval(item) for item in rows), key=lambda item: item.interval_id)),
        coverage(sessions[0], sessions[-1]), tuple(sorted(actions, key=lambda item: (item.effective_date, item.action_id))), (),
    )
    request = NseUdiffDailyTechnicalReadRequest(
        INSTRUMENT.instrument_id, sessions[0], sessions[-1],
        DailyTechnicalRequirement(DailyTechnicalRequirementProfile.PRICE_AND_VOLUME),
        NseUdiffDailyTechnicalUseMode.CURRENT_DESCRIPTIVE_TECHNICAL, AT,
    )
    return read_certified_daily_technical_bars(request=request, evidence=evidence)


def weekly_request(session_plan, *, mode=NseUdiffDailyTechnicalUseMode.CURRENT_DESCRIPTIVE_TECHNICAL):
    return NseUdiffWeeklyTechnicalDerivationRequest(
        INSTRUMENT.instrument_id, session_plan,
        DailyTechnicalRequirement(DailyTechnicalRequirementProfile.PRICE_AND_VOLUME), mode,
    )


def test_normal_five_session_week_aggregates_exact_ohlcv_trade_count_and_lineage():
    session_plan = plan(date(2024, 7, 8))
    read = daily_read(session_plan)
    value = derive_nse_udiff_weekly_technical_bar(request=weekly_request(session_plan), daily_read=read)
    assert value.state is NseUdiffWeeklyTechnicalState.READY
    assert value.technical_bar is not None
    market = value.technical_bar.market_bar
    assert (market.open, market.high, market.low, market.close, market.volume, market.trade_count) == (
        Decimal("100"), Decimal("109"), Decimal("95"), Decimal("106"), 5_010, 260,
    )
    assert value.technical_bar.receipt.period is not None
    assert value.technical_bar.receipt.period.session_dates == session_plan.expected_sessions
    assert len(value.technical_bar.source_lineage) == 5
    assert value.source_daily_observation_ids == read.source_observation_ids
    assert value.technical_bar.market_bar.provenance.provider == "hsi_derived_from_nse_udiff_daily"


def test_holiday_shortened_four_session_week_has_no_synthetic_holiday_child():
    week = date(2025, 8, 11)
    session_plan = plan(week, holidays=(date(2025, 8, 15),))
    assert session_plan.expected_sessions == weekdays(week)[:-1]
    assert date(2025, 8, 15) in session_plan.confirmed_non_trading_dates
    value = derive_nse_udiff_weekly_technical_bar(
        request=weekly_request(session_plan), daily_read=daily_read(session_plan),
    )
    assert value.state is NseUdiffWeeklyTechnicalState.READY
    assert value.technical_bar is not None
    assert value.technical_bar.market_bar.volume == 4_006
    assert len(value.technical_bar.source_lineage) == 4


def test_multiple_holiday_and_special_session_coverage_never_assumes_five_bars():
    week = date(2025, 4, 14)
    session_plan = plan(week, holidays=(date(2025, 4, 14), date(2025, 4, 18)))
    assert session_plan.expected_sessions == (date(2025, 4, 15), date(2025, 4, 16), date(2025, 4, 17))
    assert derive_nse_udiff_weekly_technical_bar(
        request=weekly_request(session_plan), daily_read=daily_read(session_plan),
    ).state is NseUdiffWeeklyTechnicalState.READY

    # 2025-02-01 was an officially evidenced NSE Budget special session.  It
    # was not part of this weekday-only fixture manifest, so the Week blocks.
    special = plan(date(2025, 1, 27))
    assert date(2025, 2, 1) in special.special_expected_sessions
    blocked = derive_nse_udiff_weekly_technical_bar(request=weekly_request(special), daily_read=None)
    assert blocked.state is NseUdiffWeeklyTechnicalState.NOT_READY
    assert NseUdiffWeeklyTechnicalReason.SPECIAL_SESSION_SOURCE_MISSING.value in blocked.reasons


def test_open_or_incomplete_week_is_never_emitted_closed():
    week = date(2026, 8, 31)
    session_plan = plan(week, requested=(date(2026, 8, 31),))
    assert session_plan.missing_session_dates == (
        date(2026, 9, 1), date(2026, 9, 2), date(2026, 9, 3), date(2026, 9, 4),
    )
    value = derive_nse_udiff_weekly_technical_bar(request=weekly_request(session_plan), daily_read=None)
    assert value.state is NseUdiffWeeklyTechnicalState.NOT_READY
    assert value.technical_bar is None
    assert NseUdiffWeeklyTechnicalReason.WEEK_NOT_COMPLETE.value in value.reasons


@pytest.mark.parametrize("series, reason", (("BL", "BL_NOT_ORDINARY_DAILY_TECHNICAL_PRICE_SERIES"), ("T0", "T0_DISTINCT_SETTLEMENT_SERIES")))
def test_nonordinary_daily_series_cannot_contaminate_weekly(series, reason):
    session_plan = plan(date(2024, 7, 8))
    read = daily_read(session_plan, series=series)
    assert read.state is NseUdiffDailyTechnicalReadState.NOT_READY
    value = derive_nse_udiff_weekly_technical_bar(request=weekly_request(session_plan), daily_read=read)
    assert value.state is NseUdiffWeeklyTechnicalState.NOT_READY
    assert reason in value.reasons


def test_series_action_and_missing_child_blocks_remain_authoritative_to_daily_reader():
    session_plan = plan(date(2024, 7, 8))
    transition = daily_read(session_plan, series="BE")
    # A fully uninterrupted BE window is eligible under the existing Daily policy.
    assert transition.state is NseUdiffDailyTechnicalReadState.READY
    assert derive_nse_udiff_weekly_technical_bar(request=weekly_request(session_plan), daily_read=transition).state is NseUdiffWeeklyTechnicalState.READY

    mixed_rows = daily_read(session_plan, include=session_plan.expected_sessions[:-1])
    assert mixed_rows.state is NseUdiffDailyTechnicalReadState.NOT_READY
    missing = derive_nse_udiff_weekly_technical_bar(request=weekly_request(session_plan), daily_read=mixed_rows)
    assert "MISSING_REQUIRED_SECURITY_SESSION" in missing.reasons

    rights = daily_read(session_plan, actions=(action(CorporateActionKind.RIGHTS, date(2024, 7, 10)),))
    assert rights.state is NseUdiffDailyTechnicalReadState.NOT_READY
    blocked = derive_nse_udiff_weekly_technical_bar(request=weekly_request(session_plan), daily_read=rights)
    assert "RIGHTS_ADJUSTMENT_NOT_READY" in blocked.reasons

    post_week = plan(date(2024, 7, 15))
    assert derive_nse_udiff_weekly_technical_bar(
        request=weekly_request(post_week), daily_read=daily_read(post_week),
    ).state is NseUdiffWeeklyTechnicalState.READY


def test_daily_window_source_and_use_mode_mismatches_fail_closed_without_next_week_leakage():
    session_plan = plan(date(2024, 7, 8))
    other = plan(date(2024, 7, 15))
    mismatch = derive_nse_udiff_weekly_technical_bar(
        request=weekly_request(session_plan), daily_read=daily_read(other),
    )
    assert mismatch.state is NseUdiffWeeklyTechnicalState.NOT_READY
    assert mismatch.reasons == (NseUdiffWeeklyTechnicalReason.DAILY_READ_WINDOW_MISMATCH.value,)

    strict = derive_nse_udiff_weekly_technical_bar(
        request=weekly_request(session_plan, mode=NseUdiffDailyTechnicalUseMode.STRICT_HISTORICAL_PIT_TECHNICAL),
        daily_read=None,
    )
    assert strict.state is NseUdiffWeeklyTechnicalState.NOT_READY
    assert strict.reasons == (NseUdiffWeeklyTechnicalReason.STRICT_HISTORICAL_PIT_SOURCE_AVAILABILITY_UNAVAILABLE.value,)


def test_deterministic_fingerprint_serialization_order_and_tampering_rejection():
    session_plan = plan(date(2024, 7, 8))
    first = derive_nse_udiff_weekly_technical_bar(request=weekly_request(session_plan), daily_read=daily_read(session_plan))
    second = derive_nse_udiff_weekly_technical_bar(request=weekly_request(session_plan), daily_read=daily_read(session_plan))
    assert first == second
    assert serialize_nse_udiff_weekly_technical_bar(first) == serialize_nse_udiff_weekly_technical_bar(second)
    assert first.technical_bar is not None
    with pytest.raises(ValueError, match="RESULT_INVALID"):
        replace(first, fingerprint="sha256:" + "0" * 64)
    with pytest.raises(ValueError, match="CANONICAL_TECHNICAL_BAR_INVALID"):
        replace(first.technical_bar, source_lineage=())


def test_additive_sqlite_store_is_replay_safe_and_preserves_revision_conflict(tmp_path: Path):
    session_plan = plan(date(2024, 7, 8))
    value = derive_nse_udiff_weekly_technical_bar(request=weekly_request(session_plan), daily_read=daily_read(session_plan))
    store = SQLiteNseUdiffWeeklyTechnicalBarStore(tmp_path / "weekly.db")
    try:
        assert store.save(value) is NseUdiffWeeklyTechnicalBarWriteOutcome.INSERTED
        assert store.save(value) is NseUdiffWeeklyTechnicalBarWriteOutcome.IDENTICAL
        assert store.count() == 1
        assert store.get(value.weekly_bar_id or "") == value
        assert store.list(canonical_instrument_id=INSTRUMENT.instrument_id) == (value,)

        # A different complete child set for the same governed Week cannot
        # overwrite the original immutable artifact.
        changed_read = daily_read(session_plan, price_delta=1)
        changed = derive_nse_udiff_weekly_technical_bar(request=weekly_request(session_plan), daily_read=changed_read)
        assert changed != value and changed.weekly_bar_id == value.weekly_bar_id
        assert store.save(changed) is NseUdiffWeeklyTechnicalBarWriteOutcome.CONFLICT
        assert store.count() == 1 and store.conflict_count() == 1
    finally:
        store.close()


def test_store_rejects_non_ready_and_contract_has_no_forbidden_dependencies():
    session_plan = plan(date(2026, 8, 31), requested=(date(2026, 8, 31),))
    blocked = derive_nse_udiff_weekly_technical_bar(request=weekly_request(session_plan), daily_read=None)
    store = SQLiteNseUdiffWeeklyTechnicalBarStore()
    try:
        with pytest.raises(ValueError, match="READY_ARTIFACT_REQUIRED"):
            store.save(blocked)
    finally:
        store.close()
    source = inspect.getsource(__import__("app.market_data.nse_udiff_weekly_technical_bar", fromlist=["*"]))
    imports = {
        node.module for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom) and node.module
    }
    forbidden = ("app.signals", "app.portfolio", "app.orders", "app.broker", "app.api", "upstox", "yfinance")
    assert not any(name.startswith(forbidden) for name in imports)
    assert "datetime.now" not in source and "nse_udiff_daily_technical_read" in source
