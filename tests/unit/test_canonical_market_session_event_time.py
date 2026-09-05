from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, date, datetime, time
import ast
import inspect
from pathlib import Path

import pytest

import app.historical.canonical_market_session_event_time as module
from app.market_data.models import Exchange
from app.historical.canonical_market_session_event_time import (
    CalendarResolutionReason,
    CanonicalMarketSessionError,
    DailyBarContaminationState,
    EventSessionState,
    EventTimestampState,
    SessionPhaseType,
    TradingDayState,
    align_event_to_canonical_session,
    make_annual_holiday_schedule,
    make_canonical_event_timestamp,
    make_canonical_market_session_calendar,
    make_effective_session_phase_timing,
    make_first_party_session_source,
    make_special_trading_day,
    make_weekday_trading_convention,
    serialize_event_session_alignment,
)
from app.historical.nse_capital_market_session_evidence_2022_2026 import nse_capital_market_calendar_2022_2026


AS_OF = datetime(2025, 6, 2, 12, tzinfo=UTC)
VENUE = Exchange.NSE
INSTRUMENT = "NSE:INE372A01015"


def _source(identifier: str, published: date = date(2024, 12, 1)):
    return make_first_party_session_source(
        source_id=identifier,
        source_reference=f"https://nsearchives.nseindia.com/content/circulars/{identifier}.pdf",
        published_on=published,
    )


def _calendar(*, source_date: date = date(2024, 12, 1), phase_start: date = date(2025, 1, 1), weekday_start: date = date(2025, 1, 1)):
    annual = _source("CMTR-HOLIDAYS-2025", source_date)
    weekday = _source("CMTR-WEEKDAY-2025", source_date)
    phase = _source("CMTR-PHASE-2025", source_date)
    special = _source("CMTR-SPECIAL-2025", source_date)
    return make_canonical_market_session_calendar(
        calendar_id="nse-cm-fixture-v1",
        coverage_start=date(2025, 1, 1), coverage_end=date(2025, 12, 31),
        annual_holiday_schedules=(make_annual_holiday_schedule(calendar_year=2025, source=annual, holidays=(date(2025, 1, 26), date(2025, 3, 14))),),
        weekday_conventions=(make_weekday_trading_convention(convention_id="nse-cm-weekdays-v1", effective_from=weekday_start, effective_to=date(2025, 12, 31), trading_weekdays=range(5), source=weekday),),
        special_trading_days=(
            make_special_trading_day(session_date=date(2025, 2, 1), state=TradingDayState.SPECIAL_TRADING_DAY, source=special),
            make_special_trading_day(session_date=date(2025, 10, 21), state=TradingDayState.MUHURAT_TRADING, source=special),
        ),
        phase_timings=(make_effective_session_phase_timing(
            timing_id="nse-cm-regular-v1", effective_from=phase_start, effective_to=date(2025, 12, 31),
            applies_to_states=(TradingDayState.REGULAR_TRADING_DAY,), phase_type=SessionPhaseType.REGULAR_CONTINUOUS,
            starts_at_local=time(9, 15), ends_at_local=time(15, 30), source=phase,
        ),),
    )


def _event(at: datetime | None, *, state: EventTimestampState = EventTimestampState.EXACT_TIMEZONE_AWARE, timezone_id: str | None = "UTC"):
    return make_canonical_event_timestamp(
        event_id="bse-filing:fixture", occurred_at=at, timezone_id=timezone_id, state=state,
        source_id="bse-filing-lineage", source_fingerprint="sha256:" + "a" * 64,
    )


def _align(at: datetime | None, **kwargs):
    return align_event_to_canonical_session(calendar=_calendar(**kwargs), canonical_instrument_id=INSTRUMENT, trading_venue=VENUE, event=_event(at))


def test_calendar_is_immutable_deterministic_and_never_uses_a_runtime_clock():
    one, two = _calendar(), _calendar()
    assert one == two and one.fingerprint == two.fingerprint
    with pytest.raises(FrozenInstanceError):
        one.coverage_end = date(2026, 1, 1)  # type: ignore[misc]
    source = Path(inspect.getfile(module)).read_text(encoding="utf-8")
    assert "datetime.now" not in source and "sqlite3" not in source


def test_regular_weekday_declared_holiday_and_weekend_are_distinct_facts():
    calendar = _calendar()
    regular = calendar.resolve_trading_day(date(2025, 6, 2), as_of=AS_OF)
    holiday = calendar.resolve_trading_day(date(2025, 3, 14), as_of=AS_OF)
    weekend = calendar.resolve_trading_day(date(2025, 6, 1), as_of=AS_OF)
    assert regular.state is TradingDayState.REGULAR_TRADING_DAY and not regular.reasons
    assert holiday.state is TradingDayState.HOLIDAY and not holiday.reasons
    assert weekend.state is TradingDayState.WEEKEND_NON_TRADING and not weekend.reasons


def test_exact_special_weekend_and_muhurat_overrides_never_become_regular_sessions():
    calendar = _calendar()
    assert calendar.resolve_trading_day(date(2025, 2, 1), as_of=AS_OF).state is TradingDayState.SPECIAL_TRADING_DAY
    assert calendar.resolve_trading_day(date(2025, 10, 21), as_of=datetime(2025, 11, 1, tzinfo=UTC)).state is TradingDayState.MUHURAT_TRADING
    result = _align(datetime(2025, 2, 1, 10, tzinfo=UTC))
    assert result.state is EventSessionState.SPECIAL_SESSION
    assert result.regular_continuous_open is result.regular_continuous_close is None


def test_exact_regular_phase_is_timezone_aware_and_effective_dated():
    calendar = _calendar()
    phases = calendar.phases_for(date(2025, 6, 2), as_of=AS_OF)
    assert len(phases) == 1 and phases[0].phase_type is SessionPhaseType.REGULAR_CONTINUOUS
    assert phases[0].starts_at.isoformat().endswith("+05:30") and phases[0].ends_at.hour == 15
    earlier = _calendar(phase_start=date(2025, 6, 3))
    assert earlier.phases_for(date(2025, 6, 2), as_of=AS_OF) == ()


def test_source_current_or_future_visibility_never_leaks_backward():
    calendar = _calendar(source_date=date(2025, 6, 2))
    unknown = calendar.resolve_trading_day(date(2025, 6, 2), as_of=datetime(2025, 6, 2, 12, tzinfo=UTC))
    assert unknown.state is TradingDayState.UNKNOWN
    assert unknown.reasons == (CalendarResolutionReason.SOURCE_NOT_PIT_VISIBLE,)
    known = calendar.resolve_trading_day(date(2025, 6, 2), as_of=datetime(2025, 6, 3, tzinfo=UTC))
    assert known.state is TradingDayState.REGULAR_TRADING_DAY


def test_missing_phase_timing_fails_closed_without_default_market_hours():
    result = _align(datetime(2025, 6, 2, 6, tzinfo=UTC), phase_start=date(2025, 6, 3))
    assert result.state is EventSessionState.SESSION_TIMING_UNAVAILABLE
    assert result.reasons == (CalendarResolutionReason.SESSION_PHASE_TIMING_UNAVAILABLE,)
    assert result.daily_bar_contamination is DailyBarContaminationState.NOT_EVALUABLE


@pytest.mark.parametrize(("at", "expected", "contamination"), (
    (datetime(2025, 6, 2, 3, 44, tzinfo=UTC), EventSessionState.BEFORE_REGULAR_SESSION, DailyBarContaminationState.NOT_CONTAMINATED),
    (datetime(2025, 6, 2, 6, 0, tzinfo=UTC), EventSessionState.DURING_REGULAR_SESSION, DailyBarContaminationState.DAILY_BAR_EVENT_CONTAMINATED),
    (datetime(2025, 6, 2, 10, 1, tzinfo=UTC), EventSessionState.AFTER_REGULAR_SESSION, DailyBarContaminationState.NOT_CONTAMINATED),
))
def test_before_during_and_after_regular_continuous_boundary(at, expected, contamination):
    result = _align(at)
    assert result.state is expected and result.daily_bar_contamination is contamination
    assert result.trading_venue is Exchange.NSE


def test_regular_close_is_after_not_during_even_if_later_exchange_phases_exist():
    result = _align(datetime(2025, 6, 2, 10, 0, tzinfo=UTC))  # 15:30 Asia/Kolkata
    assert result.state is EventSessionState.AFTER_REGULAR_SESSION


def test_non_trading_day_and_timezone_or_timestamp_unavailability_fail_closed():
    weekend = _align(datetime(2025, 6, 1, 6, tzinfo=UTC))
    assert weekend.state is EventSessionState.NON_TRADING_DAY
    missing = align_event_to_canonical_session(calendar=_calendar(), canonical_instrument_id=INSTRUMENT, trading_venue=VENUE, event=_event(None, state=EventTimestampState.EVENT_TIMESTAMP_UNAVAILABLE, timezone_id=None))
    assert missing.state is EventSessionState.EVENT_TIMESTAMP_UNAVAILABLE
    unresolved = align_event_to_canonical_session(calendar=_calendar(), canonical_instrument_id=INSTRUMENT, trading_venue=VENUE, event=_event(None, state=EventTimestampState.TIMEZONE_UNRESOLVED, timezone_id=None))
    assert unresolved.state is EventSessionState.TIMEZONE_UNRESOLVED


def test_timestamp_preserves_declared_timezone_and_rejects_ambiguous_zone_semantics():
    event = _event(datetime(2025, 6, 2, 9, 15, tzinfo=UTC), timezone_id="UTC")
    assert event.occurred_at is not None and event.occurred_at.tzinfo is not None
    with pytest.raises(CanonicalMarketSessionError, match="EVENT_TIMESTAMP_INVALID"):
        _event(datetime(2025, 6, 2, 9, 15), timezone_id="Asia/Kolkata")
    with pytest.raises(CanonicalMarketSessionError, match="EVENT_TIMESTAMP_INVALID"):
        _event(datetime(2025, 6, 2, 9, 15, tzinfo=UTC), timezone_id="Not/AZone")


def test_previous_next_sessions_cross_holiday_and_weekend_without_calendar_day_approximation():
    calendar = _calendar()
    assert calendar.adjacent_trading_session(date(2025, 3, 14), as_of=AS_OF, direction=-1) == date(2025, 3, 13)
    assert calendar.adjacent_trading_session(date(2025, 3, 14), as_of=AS_OF, direction=1) == date(2025, 3, 17)


def test_adjacent_session_stops_when_intervening_calendar_evidence_is_unknown():
    calendar = _calendar(phase_start=date(2025, 6, 3))
    assert calendar.adjacent_trading_session(date(2025, 6, 2), as_of=AS_OF, direction=1) == date(2025, 6, 3)
    no_calendar = make_canonical_market_session_calendar(
        calendar_id="empty", coverage_start=date(2025, 1, 1), coverage_end=date(2025, 12, 31),
        annual_holiday_schedules=(), weekday_conventions=(),
    )
    assert no_calendar.adjacent_trading_session(date(2025, 6, 2), as_of=AS_OF, direction=1) is None


def test_conflicting_first_party_holiday_or_special_sources_are_not_selected_by_order():
    first, second = _source("CMTR-A"), _source("CMTR-B")
    calendar = make_canonical_market_session_calendar(
        calendar_id="conflict", coverage_start=date(2025, 1, 1), coverage_end=date(2025, 12, 31),
        annual_holiday_schedules=(
            make_annual_holiday_schedule(calendar_year=2025, source=first, holidays=(date(2025, 3, 14),)),
            make_annual_holiday_schedule(calendar_year=2025, source=second, holidays=(date(2025, 3, 15),)),
        ), weekday_conventions=(),
    )
    day = calendar.resolve_trading_day(date(2025, 6, 2), as_of=AS_OF)
    assert day.state is TradingDayState.UNKNOWN and day.reasons == (CalendarResolutionReason.EVIDENCE_CONFLICTED,)
    assert day.source_ids == ("CMTR-A", "CMTR-B")
    aligned = align_event_to_canonical_session(calendar=calendar, canonical_instrument_id=INSTRUMENT, trading_venue=VENUE, event=_event(AS_OF))
    assert aligned.state is EventSessionState.EVIDENCE_CONFLICTED
    assert aligned.trading_day == day


def test_original_ambiguous_timestamp_is_preserved_without_becoming_classifiable():
    event = make_canonical_event_timestamp(
        event_id="bse:raw", occurred_at=None, timezone_id=None,
        original_timestamp="2025-06-02 17:30:00", original_timezone="exchange local (unverified)",
        state=EventTimestampState.TIMEZONE_UNRESOLVED,
        source_id="bse:source", source_fingerprint="sha256:" + "a" * 64,
    )
    result = align_event_to_canonical_session(calendar=_calendar(), canonical_instrument_id=INSTRUMENT, trading_venue=VENUE, event=event)
    assert result.state is EventSessionState.TIMEZONE_UNRESOLVED
    payload = serialize_event_session_alignment(result)
    assert event.original_timestamp in payload and event.original_timezone in payload
    assert event.occurred_at is None and result.session_date is None
    with pytest.raises(CanonicalMarketSessionError):
        replace(event, original_timestamp="tampered")


def test_phase_conflict_is_unavailable_not_an_arbitrary_latest_rule():
    calendar = _calendar()
    phase_source = _source("CMTR-OTHER")
    conflict = make_effective_session_phase_timing(
        timing_id="conflict", effective_from=date(2025, 1, 1), effective_to=date(2025, 12, 31),
        applies_to_states=(TradingDayState.REGULAR_TRADING_DAY,), phase_type=SessionPhaseType.REGULAR_CONTINUOUS,
        starts_at_local=time(9), ends_at_local=time(15), source=phase_source,
    )
    conflicted = make_canonical_market_session_calendar(
        calendar_id=calendar.calendar_id, coverage_start=calendar.coverage_start, coverage_end=calendar.coverage_end,
        annual_holiday_schedules=calendar.annual_holiday_schedules, weekday_conventions=calendar.weekday_conventions,
        special_trading_days=calendar.special_trading_days, phase_timings=(*calendar.phase_timings, conflict),
    )
    assert conflicted.phases_for(date(2025, 6, 2), as_of=AS_OF) == ()
    result = align_event_to_canonical_session(
        calendar=conflicted, canonical_instrument_id=INSTRUMENT, trading_venue=VENUE,
        event=_event(datetime(2025, 6, 2, 6, tzinfo=UTC)),
    )
    assert result.state is EventSessionState.EVIDENCE_CONFLICTED
    assert result.phase_source_ids == ("CMTR-OTHER", "CMTR-PHASE-2025")


def test_replay_identity_serialization_and_tamper_rejection_are_stable():
    one = _align(datetime(2025, 6, 2, 6, tzinfo=UTC))
    two = _align(datetime(2025, 6, 2, 6, tzinfo=UTC))
    assert one == two and serialize_event_session_alignment(one) == serialize_event_session_alignment(two)
    with pytest.raises(CanonicalMarketSessionError, match="ALIGNMENT_INVALID"):
        replace(one, canonical_instrument_id="NSE:TAMPERED")


def test_bse_filing_source_cannot_select_bse_as_reaction_venue_and_no_returns_or_qualification_surface_exists():
    result = _align(datetime(2025, 6, 2, 6, tzinfo=UTC))
    assert result.trading_venue is Exchange.NSE and result.actionability == "WATCH_ONLY" and result.execution_status == "NON_EXECUTABLE"
    assert not (set(result.__dataclass_fields__) & {"price", "return", "gap", "volume", "score", "candidate", "buy", "sell", "portfolio"})
    with pytest.raises(CanonicalMarketSessionError, match="ALIGNMENT_INPUT_INVALID"):
        align_event_to_canonical_session(calendar=_calendar(), canonical_instrument_id=INSTRUMENT, trading_venue=Exchange.BSE, event=_event(datetime(2025, 6, 2, 6, tzinfo=UTC)))


def test_static_boundaries_exclude_storage_api_portfolio_broker_order_and_price_calculation_dependencies():
    source = Path(inspect.getfile(module)).read_text(encoding="utf-8")
    imports = {item.name for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Import) for item in node.names} | {node.module or "" for node in ast.walk(ast.parse(source)) if isinstance(node, ast.ImportFrom)}
    assert not any(value.startswith(prefix) for value in imports for prefix in ("app.portfolio", "app.broker", "app.orders", "app.api", "app.signals", "sqlite3", "requests"))
    for forbidden in ("market_return", "gap_return", "volume_ratio", "place_order", "datetime.now"):
        assert forbidden not in source


def test_bounded_first_party_2022_to_2026_catalogue_preserves_only_recovered_holidays_and_special_phases():
    calendar = nse_capital_market_calendar_2022_2026()
    as_of = datetime(2026, 9, 5, tzinfo=UTC)
    assert calendar.coverage_start == date(2022, 1, 1) and calendar.coverage_end == date(2026, 12, 31)
    assert calendar.resolve_trading_day(date(2024, 3, 29), as_of=as_of).state is TradingDayState.HOLIDAY
    assert calendar.resolve_trading_day(date(2025, 2, 1), as_of=as_of).state is TradingDayState.SPECIAL_TRADING_DAY
    assert calendar.resolve_trading_day(date(2023, 11, 12), as_of=as_of).state is TradingDayState.MUHURAT_TRADING
    assert calendar.resolve_trading_day(date(2025, 6, 2), as_of=as_of).state is TradingDayState.UNKNOWN
    for session_date, start, end in (
        (date(2022, 10, 24), time(18, 15), time(19, 15)),
        (date(2023, 11, 12), time(18, 15), time(19, 15)),
        (date(2024, 11, 1), time(18), time(19)),
        (date(2025, 10, 21), time(13, 45), time(14, 45)),
    ):
        phases = calendar.phases_for(session_date, as_of=as_of)
        regular = next(value for value in phases if value.phase_type is SessionPhaseType.REGULAR_CONTINUOUS)
        assert (regular.starts_at.timetz().replace(tzinfo=None), regular.ends_at.timetz().replace(tzinfo=None)) == (start, end)


def test_holiday_amendment_is_pit_visible_and_preserves_base_provenance():
    calendar = nse_capital_market_calendar_2022_2026()
    before = datetime(2023, 6, 26, tzinfo=UTC)
    after = datetime(2023, 6, 28, tzinfo=UTC)
    assert calendar.resolve_trading_day(date(2023, 6, 28), as_of=before).state is TradingDayState.HOLIDAY
    assert calendar.resolve_trading_day(date(2023, 6, 28), as_of=after).state is TradingDayState.UNKNOWN
    revised = calendar.resolve_trading_day(date(2023, 6, 29), as_of=after)
    assert revised.state is TradingDayState.HOLIDAY
    assert len(revised.source_ids) == 2


def test_special_day_does_not_require_annual_schedule_and_exposes_missing_phases():
    special = make_special_trading_day(session_date=date(2025, 2, 1), state=TradingDayState.SPECIAL_TRADING_DAY, source=_source("special"))
    calendar = make_canonical_market_session_calendar(calendar_id="special-only", coverage_start=date(2025, 1, 1), coverage_end=date(2025, 12, 31), annual_holiday_schedules=(), weekday_conventions=(), special_trading_days=(special,))
    result = align_event_to_canonical_session(calendar=calendar, canonical_instrument_id=INSTRUMENT, trading_venue=VENUE, event=_event(datetime(2025, 2, 1, 6, tzinfo=UTC)))
    assert result.state is EventSessionState.SPECIAL_SESSION
    assert result.trading_day.state is TradingDayState.SPECIAL_TRADING_DAY
    assert result.reasons == (CalendarResolutionReason.SESSION_PHASE_TIMING_UNAVAILABLE,)


def test_special_exact_phase_boundaries_are_retained_without_regular_day_classification():
    calendar = nse_capital_market_calendar_2022_2026()
    result = align_event_to_canonical_session(calendar=calendar, canonical_instrument_id=INSTRUMENT, trading_venue=VENUE, event=_event(datetime(2025, 10, 21, 8, 30, tzinfo=UTC)))
    assert result.state is EventSessionState.SPECIAL_SESSION
    assert result.regular_continuous_open.hour == 13
    assert result.regular_continuous_close.hour == 14
    assert result.phase_source_ids == ("nse-cmtr-70319-2025-muhurat",)
    assert result.reasons == ()


def test_nontrading_dates_cannot_receive_a_trading_phase():
    for state in (TradingDayState.HOLIDAY, TradingDayState.WEEKEND_NON_TRADING, TradingDayState.UNKNOWN):
        with pytest.raises(CanonicalMarketSessionError):
            make_effective_session_phase_timing(timing_id="invalid", effective_from=date(2025, 1, 1), effective_to=None, applies_to_states=(state,), phase_type=SessionPhaseType.REGULAR_CONTINUOUS, starts_at_local=time(9, 15), ends_at_local=time(15, 30), source=_source("invalid-phase"))
