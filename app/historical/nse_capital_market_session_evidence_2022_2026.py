"""Bounded first-party NSE CM calendar evidence recovered for 2022--2026.

Annual Capital Market holiday circulars and exact special-session circulars
remain the historical record.  A retained current NSE equity-timings page is
also a *forward-only* rule from its immutable ``known_at``: it establishes
Monday--Friday ordinary trading and the 09:15--15:30 regular-continuous phase
only from 2026-09-05.  It is never projected into earlier years or even an
earlier PIT cutoff on that date.
"""
from __future__ import annotations

from datetime import UTC, date, datetime, time

from app.historical.canonical_market_session_event_time import (
    CanonicalMarketSessionCalendar,
    SessionPhaseType,
    TradingDayState,
    make_annual_holiday_schedule,
    make_canonical_market_session_calendar,
    make_effective_session_phase_timing,
    make_first_party_session_source,
    make_special_trading_day,
    make_weekday_trading_convention,
)


COVERAGE_START = date(2022, 1, 1)
COVERAGE_END = date(2026, 12, 31)


def nse_capital_market_calendar_2022_2026() -> CanonicalMarketSessionCalendar:
    """Return the bounded source-backed calendar with a forward-only weekday rule.

    Every source was published before the dated holiday or special session it
    controls, except the retained current timing page, whose explicit known-at
    bounds its prospective rule. The function performs no retrieval and has no
    system-clock dependency. Historical ordinary weekdays remain incomplete.
    """
    holidays_2022 = make_first_party_session_source(
        source_id="nse-cmtr-50560-2022-holidays",
        source_reference="https://archives.nseindia.com/content/circulars/CMTR50560.pdf",
        published_on=date(2021, 12, 10),
    )
    holidays_2023 = make_first_party_session_source(
        source_id="nse-cmtr-54757-2023-holidays",
        source_reference="https://archives.nseindia.com/content/circulars/CMTR54757.pdf",
        published_on=date(2022, 12, 8),
    )
    holidays_2024 = make_first_party_session_source(
        source_id="nse-cmtr-59722-2024-holidays",
        source_reference="https://archives.nseindia.com/content/circulars/CMTR59722.pdf",
        published_on=date(2023, 12, 12),
    )
    holidays_2025 = make_first_party_session_source(
        source_id="nse-cmtr-65587-2025-holidays",
        source_reference="https://nsearchives.nseindia.com/content/circulars/CMTR65587.pdf",
        published_on=date(2024, 12, 13),
    )
    holidays_2026 = make_first_party_session_source(
        source_id="nse-cmtr-71775-2026-holidays",
        source_reference="https://nsearchives.nseindia.com/content/circulars/CMTR71775.pdf",
        published_on=date(2025, 12, 12),
    )
    muhurat_2022 = make_first_party_session_source(
        source_id="nse-cmtr-54023-2022-muhurat",
        source_reference="https://archives.nseindia.com/content/circulars/CMTR54023.pdf",
        published_on=date(2022, 10, 11),
    )
    muhurat_2023 = make_first_party_session_source(
        source_id="nse-cmtr-59124-2023-muhurat",
        source_reference="https://nsearchives.nseindia.com/content/circulars/CMTR59124.pdf",
        published_on=date(2023, 10, 27),
    )
    muhurat_2024 = make_first_party_session_source(
        source_id="nse-cmtr-64628-2024-muhurat",
        source_reference="https://nsearchives.nseindia.com/content/circulars/CMTR64628.pdf",
        published_on=date(2024, 10, 19),
    )
    budget_2025 = make_first_party_session_source(
        source_id="nse-cmtr-65729-2025-budget-session",
        source_reference="https://nsearchives.nseindia.com/content/circulars/CMTR65729.pdf",
        published_on=date(2024, 12, 23),
    )
    muhurat_2025 = make_first_party_session_source(
        source_id="nse-cmtr-70319-2025-muhurat",
        source_reference="https://nsearchives.nseindia.com/content/circulars/CMTR70319.pdf",
        published_on=date(2025, 9, 22),
    )
    budget_2026 = make_first_party_session_source(
        source_id="nse-cmtr-72349-2026-budget-session",
        source_reference="https://nsearchives.nseindia.com/content/circulars/CMTR72349.pdf",
        published_on=date(2026, 1, 16),
    )
    # The current NSE page has no stable publication timestamp.  This is the
    # immutable HSI knowledge cutoff for the retained page, not a claim that
    # NSE published the page at that instant.  Its current wording is scoped
    # prospectively; it cannot settle ordinary-session identity before either
    # this cutoff or its declared effective date.
    ordinary_2026_current = make_first_party_session_source(
        source_id="nse-equity-market-timings-current-2026-09-05",
        source_reference="https://nseindia.com/resources/exchange-communication-holidays",
        known_at=datetime(2026, 9, 5, 16, 47, tzinfo=UTC),
    )
    schedules = (
        make_annual_holiday_schedule(calendar_year=2022, source=holidays_2022, holidays=_days("2022-01-26", "2022-03-01", "2022-03-18", "2022-04-14", "2022-04-15", "2022-05-03", "2022-08-09", "2022-08-15", "2022-08-31", "2022-10-05", "2022-10-24", "2022-10-26", "2022-11-08")),
        make_annual_holiday_schedule(calendar_year=2023, source=holidays_2023, holidays=_days("2023-01-26", "2023-03-07", "2023-03-30", "2023-04-04", "2023-04-07", "2023-04-14", "2023-05-01", "2023-06-28", "2023-08-15", "2023-09-19", "2023-10-02", "2023-10-24", "2023-11-14", "2023-11-27", "2023-12-25")),
        make_annual_holiday_schedule(calendar_year=2024, source=holidays_2024, holidays=_days("2024-01-26", "2024-03-08", "2024-03-25", "2024-03-29", "2024-04-11", "2024-04-17", "2024-05-01", "2024-06-17", "2024-07-17", "2024-08-15", "2024-10-02", "2024-11-01", "2024-11-15", "2024-12-25")),
        make_annual_holiday_schedule(calendar_year=2025, source=holidays_2025, holidays=_days("2025-02-26", "2025-03-14", "2025-03-31", "2025-04-10", "2025-04-14", "2025-04-18", "2025-05-01", "2025-08-15", "2025-08-27", "2025-10-02", "2025-10-21", "2025-10-22", "2025-11-05", "2025-12-25")),
        make_annual_holiday_schedule(calendar_year=2026, source=holidays_2026, holidays=_days("2026-01-26", "2026-03-03", "2026-03-26", "2026-03-31", "2026-04-03", "2026-04-14", "2026-05-01", "2026-05-28", "2026-06-26", "2026-09-14", "2026-10-02", "2026-10-20", "2026-11-10", "2026-11-24", "2026-12-25")),
    )
    specials = (
        make_special_trading_day(session_date=date(2022, 10, 24), state=TradingDayState.MUHURAT_TRADING, source=muhurat_2022),
        make_special_trading_day(session_date=date(2023, 11, 12), state=TradingDayState.MUHURAT_TRADING, source=muhurat_2023),
        make_special_trading_day(session_date=date(2024, 11, 1), state=TradingDayState.MUHURAT_TRADING, source=muhurat_2024),
        make_special_trading_day(session_date=date(2025, 2, 1), state=TradingDayState.SPECIAL_TRADING_DAY, source=budget_2025),
        make_special_trading_day(session_date=date(2025, 10, 21), state=TradingDayState.MUHURAT_TRADING, source=muhurat_2025),
        make_special_trading_day(session_date=date(2026, 2, 1), state=TradingDayState.SPECIAL_TRADING_DAY, source=budget_2026),
        # The current NSE timing/holiday page identifies the date and the
        # forthcoming Muhurat session, but explicitly says timings will be
        # notified later.  Retain only the descriptive day state.
        make_special_trading_day(session_date=date(2026, 11, 8), state=TradingDayState.MUHURAT_TRADING, source=ordinary_2026_current),
    )
    # NSE Clearing explicitly quotes CMTR57285 and the June 28 -> 29 change.
    # Retain the amendment as a separate PIT-visible record, never edit the base.
    amendment_2023 = make_first_party_session_source(
        source_id="nse-cmpt-57296-referencing-cmtr-57285",
        source_reference="https://nsearchives.nseindia.com/content/circulars/CMPT57296.pdf",
        published_on=date(2023, 6, 27),
    )
    base_2023 = schedules[1]
    schedules += (make_annual_holiday_schedule(
        calendar_year=2023, source=amendment_2023,
        holidays=tuple(day for day in base_2023.holidays if day != date(2023, 6, 28)) + (date(2023, 6, 29),),
        supersedes_source_ids=(holidays_2023.source_id,),
    ),)
    timings = (
        _phase("nse-cm-2022-muhurat-pre-open", date(2022, 10, 24), TradingDayState.MUHURAT_TRADING, SessionPhaseType.PRE_OPEN, time(18), time(18, 8), muhurat_2022),
        _phase("nse-cm-2022-muhurat-regular", date(2022, 10, 24), TradingDayState.MUHURAT_TRADING, SessionPhaseType.REGULAR_CONTINUOUS, time(18, 15), time(19, 15), muhurat_2022),
        _phase("nse-cm-2022-muhurat-closing", date(2022, 10, 24), TradingDayState.MUHURAT_TRADING, SessionPhaseType.CLOSING_SESSION, time(19, 25), time(19, 35), muhurat_2022),
        _phase("nse-cm-2023-muhurat-pre-open", date(2023, 11, 12), TradingDayState.MUHURAT_TRADING, SessionPhaseType.PRE_OPEN, time(18), time(18, 8), muhurat_2023),
        _phase("nse-cm-2023-muhurat-regular", date(2023, 11, 12), TradingDayState.MUHURAT_TRADING, SessionPhaseType.REGULAR_CONTINUOUS, time(18, 15), time(19, 15), muhurat_2023),
        _phase("nse-cm-2023-muhurat-closing", date(2023, 11, 12), TradingDayState.MUHURAT_TRADING, SessionPhaseType.CLOSING_SESSION, time(19, 25), time(19, 35), muhurat_2023),
        _phase("nse-cm-2024-muhurat-pre-open", date(2024, 11, 1), TradingDayState.MUHURAT_TRADING, SessionPhaseType.PRE_OPEN, time(17, 45), time(18), muhurat_2024),
        _phase("nse-cm-2024-muhurat-regular", date(2024, 11, 1), TradingDayState.MUHURAT_TRADING, SessionPhaseType.REGULAR_CONTINUOUS, time(18), time(19), muhurat_2024),
        _phase("nse-cm-2024-muhurat-closing", date(2024, 11, 1), TradingDayState.MUHURAT_TRADING, SessionPhaseType.CLOSING_SESSION, time(19, 10), time(19, 20), muhurat_2024),
        _phase("nse-cm-2025-budget-regular", date(2025, 2, 1), TradingDayState.SPECIAL_TRADING_DAY, SessionPhaseType.REGULAR_CONTINUOUS, time(9, 15), time(15, 30), budget_2025),
        _phase("nse-cm-2025-muhurat-pre-open", date(2025, 10, 21), TradingDayState.MUHURAT_TRADING, SessionPhaseType.PRE_OPEN, time(13, 30), time(13, 45), muhurat_2025),
        _phase("nse-cm-2025-muhurat-regular", date(2025, 10, 21), TradingDayState.MUHURAT_TRADING, SessionPhaseType.REGULAR_CONTINUOUS, time(13, 45), time(14, 45), muhurat_2025),
        _phase("nse-cm-2025-muhurat-closing", date(2025, 10, 21), TradingDayState.MUHURAT_TRADING, SessionPhaseType.CLOSING_SESSION, time(14, 55), time(15, 5), muhurat_2025),
        _phase("nse-cm-2026-budget-regular", date(2026, 2, 1), TradingDayState.SPECIAL_TRADING_DAY, SessionPhaseType.REGULAR_CONTINUOUS, time(9, 15), time(15, 30), budget_2026),
        make_effective_session_phase_timing(
            timing_id="nse-cm-ordinary-regular-2026-09-05-current",
            effective_from=date(2026, 9, 5), effective_to=COVERAGE_END,
            applies_to_states=(TradingDayState.REGULAR_TRADING_DAY,),
            phase_type=SessionPhaseType.REGULAR_CONTINUOUS,
            starts_at_local=time(9, 15), ends_at_local=time(15, 30),
            source=ordinary_2026_current,
        ),
    )
    return make_canonical_market_session_calendar(
        calendar_id="nse-capital-market-first-party-2022-2026-v2-ordinary-forward",
        coverage_start=COVERAGE_START,
        coverage_end=COVERAGE_END,
        annual_holiday_schedules=schedules,
        weekday_conventions=(make_weekday_trading_convention(
            convention_id="nse-cm-ordinary-weekdays-2026-09-05-current",
            effective_from=date(2026, 9, 5), effective_to=COVERAGE_END,
            trading_weekdays=range(5), source=ordinary_2026_current,
        ),),
        special_trading_days=specials,
        phase_timings=timings,
    )


def _phase(identifier: str, session_date: date, state: TradingDayState, kind: SessionPhaseType, start: time, end: time, source):
    return make_effective_session_phase_timing(
        timing_id=identifier, effective_from=session_date, effective_to=session_date,
        applies_to_states=(state,), phase_type=kind, starts_at_local=start, ends_at_local=end, source=source,
    )


def _days(*values: str) -> tuple[date, ...]:
    return tuple(date.fromisoformat(value) for value in values)


__all__ = ("COVERAGE_END", "COVERAGE_START", "nse_capital_market_calendar_2022_2026")
