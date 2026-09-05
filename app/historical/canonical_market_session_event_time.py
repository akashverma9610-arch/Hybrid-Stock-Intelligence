"""Immutable, source-injected NSE capital-market calendar and event-time facts.

This module deliberately has no transport, storage, clock, price, portfolio, or
execution dependency.  A caller supplies retained first-party source evidence
and an explicit ``as_of``.  It can then resolve only factual trading-day,
phase, and event-session information.  Missing historical evidence remains
``UNKNOWN`` / unavailable; current NSE timing pages are never inferred backward.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import UTC, date, datetime, time, timedelta
from enum import StrEnum
import hashlib
import json
import re
from typing import Iterable
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.market_data.models import Exchange


CONTRACT_ID = "canonical-market-session-calendar-and-event-time"
CONTRACT_VERSION = "v1"
IST_TIMEZONE = "Asia/Kolkata"
_IDENTIFIER = re.compile(r"[A-Za-z0-9._:-]+\Z")
_FINGERPRINT = re.compile(r"sha256:[0-9a-f]{64}\Z")
_PRIMARY_HOSTS = frozenset({"nseindia.com", "nsearchives.nseindia.com", "archives.nseindia.com", "sebi.gov.in"})


class CanonicalMarketSessionError(ValueError):
    """Stable fail-closed error for malformed session evidence."""


class TradingDayState(StrEnum):
    REGULAR_TRADING_DAY = "REGULAR_TRADING_DAY"
    HOLIDAY = "HOLIDAY"
    WEEKEND_NON_TRADING = "WEEKEND_NON_TRADING"
    SPECIAL_TRADING_DAY = "SPECIAL_TRADING_DAY"
    MUHURAT_TRADING = "MUHURAT_TRADING"
    UNKNOWN = "UNKNOWN"


class SessionPhaseType(StrEnum):
    PRE_OPEN = "PRE_OPEN"
    SPECIAL_PRE_OPEN = "SPECIAL_PRE_OPEN"
    REGULAR_CONTINUOUS = "REGULAR_CONTINUOUS"
    CLOSING_SESSION = "CLOSING_SESSION"
    CLOSING_AUCTION = "CLOSING_AUCTION"
    BLOCK_DEAL = "BLOCK_DEAL"
    AUCTION = "AUCTION"
    SPECIAL_SESSION = "SPECIAL_SESSION"


class CalendarResolutionReason(StrEnum):
    DATE_OUTSIDE_COVERAGE = "DATE_OUTSIDE_COVERAGE"
    ANNUAL_HOLIDAY_EVIDENCE_UNAVAILABLE = "ANNUAL_HOLIDAY_EVIDENCE_UNAVAILABLE"
    WEEKDAY_CONVENTION_UNAVAILABLE = "WEEKDAY_CONVENTION_UNAVAILABLE"
    SOURCE_NOT_PIT_VISIBLE = "SOURCE_NOT_PIT_VISIBLE"
    EVIDENCE_CONFLICTED = "EVIDENCE_CONFLICTED"
    SESSION_PHASE_TIMING_UNAVAILABLE = "SESSION_PHASE_TIMING_UNAVAILABLE"
    ADJACENT_SESSION_UNAVAILABLE = "ADJACENT_SESSION_UNAVAILABLE"


class EventTimestampState(StrEnum):
    EXACT_TIMEZONE_AWARE = "EXACT_TIMEZONE_AWARE"
    EVENT_TIMESTAMP_UNAVAILABLE = "EVENT_TIMESTAMP_UNAVAILABLE"
    TIMEZONE_UNRESOLVED = "TIMEZONE_UNRESOLVED"


class EventSessionState(StrEnum):
    BEFORE_REGULAR_SESSION = "BEFORE_REGULAR_SESSION"
    DURING_REGULAR_SESSION = "DURING_REGULAR_SESSION"
    AFTER_REGULAR_SESSION = "AFTER_REGULAR_SESSION"
    NON_TRADING_DAY = "NON_TRADING_DAY"
    SPECIAL_SESSION = "SPECIAL_SESSION"
    SESSION_TIMING_UNAVAILABLE = "SESSION_TIMING_UNAVAILABLE"
    EVENT_TIMESTAMP_UNAVAILABLE = "EVENT_TIMESTAMP_UNAVAILABLE"
    TIMEZONE_UNRESOLVED = "TIMEZONE_UNRESOLVED"
    EVIDENCE_CONFLICTED = "EVIDENCE_CONFLICTED"


class DailyBarContaminationState(StrEnum):
    DAILY_BAR_EVENT_CONTAMINATED = "DAILY_BAR_EVENT_CONTAMINATED"
    NOT_CONTAMINATED = "NOT_CONTAMINATED"
    NOT_EVALUABLE = "NOT_EVALUABLE"


@dataclass(frozen=True, slots=True)
class FirstPartySessionSource:
    """A source identity, not an assertion about runtime retrieval time."""

    source_id: str
    exchange: Exchange
    segment: str
    source_reference: str
    published_at: datetime | None
    published_on: date | None
    known_at: datetime | None
    fingerprint: str

    def __post_init__(self) -> None:
        if (
            not _identifier(self.source_id)
            or self.exchange is not Exchange.NSE
            or self.segment != "CAPITAL_MARKET"
            or not _primary_nse_or_sebi_url(self.source_reference)
            or not _aware_or_none(self.published_at)
            or not _date_or_none(self.published_on)
            or not _aware_or_none(self.known_at)
            or (self.published_at is None and self.published_on is None and self.known_at is None)
            or (self.known_at is not None and self.published_at is not None and _utc(self.known_at) < _utc(self.published_at))
            or self.fingerprint != _fingerprint(_source_payload(self))
        ):
            raise CanonicalMarketSessionError("MARKET_SESSION_SOURCE_INVALID")


@dataclass(frozen=True, slots=True)
class AnnualTradingHolidaySchedule:
    calendar_year: int
    source: FirstPartySessionSource
    holidays: tuple[date, ...]
    fingerprint: str
    supersedes_source_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if (
            not _year(self.calendar_year)
            or not isinstance(self.source, FirstPartySessionSource)
            or self.holidays != tuple(sorted(set(self.holidays)))
            or not self.holidays
            or self.supersedes_source_ids != tuple(sorted(set(self.supersedes_source_ids)))
            or any(not _identifier(value) or value == self.source.source_id for value in self.supersedes_source_ids)
            or any(not _date(value) or value.year != self.calendar_year for value in self.holidays)
            or self.fingerprint != _fingerprint(_holiday_schedule_payload(self))
        ):
            raise CanonicalMarketSessionError("MARKET_SESSION_HOLIDAY_SCHEDULE_INVALID")


@dataclass(frozen=True, slots=True)
class WeekdayTradingConvention:
    """An effective-dated, first-party rule for regular weekday trading only."""

    convention_id: str
    effective_from: date
    effective_to: date | None
    trading_weekdays: tuple[int, ...]
    source: FirstPartySessionSource
    fingerprint: str

    def __post_init__(self) -> None:
        if (
            not _identifier(self.convention_id)
            or not _date(self.effective_from)
            or (self.effective_to is not None and (not _date(self.effective_to) or self.effective_to < self.effective_from))
            or self.trading_weekdays != tuple(sorted(set(self.trading_weekdays)))
            or not self.trading_weekdays
            or any(value not in range(7) for value in self.trading_weekdays)
            or not isinstance(self.source, FirstPartySessionSource)
            or self.fingerprint != _fingerprint(_weekday_convention_payload(self))
        ):
            raise CanonicalMarketSessionError("MARKET_SESSION_WEEKDAY_CONVENTION_INVALID")


@dataclass(frozen=True, slots=True)
class SpecialTradingDay:
    """An exact source-backed override; it is never inferred from weekday rules."""

    session_date: date
    state: TradingDayState
    source: FirstPartySessionSource
    fingerprint: str

    def __post_init__(self) -> None:
        if (
            not _date(self.session_date)
            or self.state not in {TradingDayState.SPECIAL_TRADING_DAY, TradingDayState.MUHURAT_TRADING}
            or not isinstance(self.source, FirstPartySessionSource)
            or self.fingerprint != _fingerprint(_special_day_payload(self))
        ):
            raise CanonicalMarketSessionError("MARKET_SESSION_SPECIAL_DAY_INVALID")


@dataclass(frozen=True, slots=True)
class EffectiveSessionPhaseTiming:
    """One source-backed phase definition with a declared historical range."""

    timing_id: str
    effective_from: date
    effective_to: date | None
    applies_to_states: tuple[TradingDayState, ...]
    phase_type: SessionPhaseType
    starts_at_local: time
    ends_at_local: time
    timezone_id: str
    source: FirstPartySessionSource
    fingerprint: str

    def __post_init__(self) -> None:
        if (
            not _identifier(self.timing_id)
            or not _date(self.effective_from)
            or (self.effective_to is not None and (not _date(self.effective_to) or self.effective_to < self.effective_from))
            or self.applies_to_states != tuple(sorted(set(self.applies_to_states), key=lambda value: value.value))
            or not self.applies_to_states
            or any(value not in {TradingDayState.REGULAR_TRADING_DAY, TradingDayState.SPECIAL_TRADING_DAY, TradingDayState.MUHURAT_TRADING} for value in self.applies_to_states)
            or not isinstance(self.phase_type, SessionPhaseType)
            or not isinstance(self.starts_at_local, time)
            or not isinstance(self.ends_at_local, time)
            or self.starts_at_local.tzinfo is not None
            or self.ends_at_local.tzinfo is not None
            or self.starts_at_local >= self.ends_at_local
            or self.timezone_id != IST_TIMEZONE
            or not isinstance(self.source, FirstPartySessionSource)
            or self.fingerprint != _fingerprint(_phase_timing_payload(self))
        ):
            raise CanonicalMarketSessionError("MARKET_SESSION_PHASE_TIMING_INVALID")


@dataclass(frozen=True, slots=True)
class CanonicalTradingDay:
    session_date: date
    exchange: Exchange
    segment: str
    state: TradingDayState
    reasons: tuple[CalendarResolutionReason, ...]
    source_ids: tuple[str, ...]
    source_fingerprints: tuple[str, ...]
    calendar_fingerprint: str
    fingerprint: str

    def __post_init__(self) -> None:
        available = self.state is not TradingDayState.UNKNOWN
        if (
            not _date(self.session_date)
            or self.exchange is not Exchange.NSE
            or self.segment != "CAPITAL_MARKET"
            or self.reasons != tuple(sorted(set(self.reasons), key=lambda value: value.value))
            or any(not isinstance(value, CalendarResolutionReason) for value in self.reasons)
            or self.source_ids != tuple(sorted(set(self.source_ids)))
            or self.source_fingerprints != tuple(sorted(set(self.source_fingerprints)))
            or len(self.source_ids) != len(self.source_fingerprints)
            or not _fingerprint_value(self.calendar_fingerprint)
            or (available and (self.reasons or not self.source_ids))
            or (not available and not self.reasons)
            or (not available and self.source_ids and CalendarResolutionReason.EVIDENCE_CONFLICTED not in self.reasons)
            or self.fingerprint != _fingerprint(_trading_day_payload(self))
        ):
            raise CanonicalMarketSessionError("CANONICAL_TRADING_DAY_INVALID")


@dataclass(frozen=True, slots=True)
class CanonicalSessionPhase:
    session_date: date
    phase_type: SessionPhaseType
    starts_at: datetime
    ends_at: datetime
    timezone_id: str
    timing_id: str
    source_id: str
    source_fingerprint: str
    fingerprint: str

    def __post_init__(self) -> None:
        if (
            not _date(self.session_date)
            or not isinstance(self.phase_type, SessionPhaseType)
            or not _aware(self.starts_at)
            or not _aware(self.ends_at)
            or self.starts_at >= self.ends_at
            or self.timezone_id != IST_TIMEZONE
            or self.starts_at.tzinfo != ZoneInfo(IST_TIMEZONE)
            or self.ends_at.tzinfo != ZoneInfo(IST_TIMEZONE)
            or self.starts_at.date() != self.session_date
            or self.ends_at.date() != self.session_date
            or not _identifier(self.timing_id)
            or not _identifier(self.source_id)
            or not _fingerprint_value(self.source_fingerprint)
            or self.fingerprint != _fingerprint(_phase_payload(self))
        ):
            raise CanonicalMarketSessionError("CANONICAL_SESSION_PHASE_INVALID")


@dataclass(frozen=True, slots=True)
class CanonicalEventTimestamp:
    event_id: str
    state: EventTimestampState
    occurred_at: datetime | None
    timezone_id: str | None
    original_timestamp: str | None
    original_timezone: str | None
    source_id: str
    source_fingerprint: str
    fingerprint: str

    def __post_init__(self) -> None:
        exact = self.state is EventTimestampState.EXACT_TIMEZONE_AWARE
        if (
            not _identifier(self.event_id)
            or not isinstance(self.state, EventTimestampState)
            or not _identifier(self.source_id)
            or not _fingerprint_value(self.source_fingerprint)
            or (self.original_timestamp is not None and (not isinstance(self.original_timestamp, str) or not self.original_timestamp.strip()))
            or (self.original_timezone is not None and (not isinstance(self.original_timezone, str) or not self.original_timezone.strip()))
            or (exact and self.original_timestamp is None)
            or (exact and (not _aware(self.occurred_at) or not _valid_timezone_timestamp(self.occurred_at, self.timezone_id)))
            or (not exact and (self.occurred_at is not None or self.timezone_id is not None))
            or self.fingerprint != _fingerprint(_event_timestamp_payload(self))
        ):
            raise CanonicalMarketSessionError("CANONICAL_EVENT_TIMESTAMP_INVALID")


@dataclass(frozen=True, slots=True)
class EventSessionAlignment:
    """Factual event timing; it contains no price, return, or signal fields."""

    canonical_instrument_id: str
    trading_venue: Exchange
    segment: str
    event: CanonicalEventTimestamp
    session_date: date | None
    trading_day: CanonicalTradingDay | None
    state: EventSessionState
    regular_continuous_open: datetime | None
    regular_continuous_close: datetime | None
    phase_source_ids: tuple[str, ...]
    phase_source_fingerprints: tuple[str, ...]
    previous_session: date | None
    next_session: date | None
    daily_bar_contamination: DailyBarContaminationState
    reasons: tuple[CalendarResolutionReason, ...]
    calendar_fingerprint: str
    fingerprint: str
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION
    actionability: str = "WATCH_ONLY"
    execution_status: str = "NON_EXECUTABLE"

    def __post_init__(self) -> None:
        timed = self.state in {EventSessionState.BEFORE_REGULAR_SESSION, EventSessionState.DURING_REGULAR_SESSION, EventSessionState.AFTER_REGULAR_SESSION}
        has_day = self.state in {EventSessionState.NON_TRADING_DAY, EventSessionState.SPECIAL_SESSION} or timed
        if (
            not _identifier(self.canonical_instrument_id)
            or self.trading_venue is not Exchange.NSE
            or self.segment != "CAPITAL_MARKET"
            or not isinstance(self.event, CanonicalEventTimestamp)
            or not isinstance(self.state, EventSessionState)
            or not isinstance(self.daily_bar_contamination, DailyBarContaminationState)
            or self.reasons != tuple(sorted(set(self.reasons), key=lambda value: value.value))
            or any(not isinstance(value, CalendarResolutionReason) for value in self.reasons)
            or not _fingerprint_value(self.calendar_fingerprint)
            or self.phase_source_ids != tuple(sorted(set(self.phase_source_ids)))
            or self.phase_source_fingerprints != tuple(sorted(set(self.phase_source_fingerprints)))
            or len(self.phase_source_ids) != len(self.phase_source_fingerprints)
            or (self.contract_id, self.contract_version, self.actionability, self.execution_status) != (CONTRACT_ID, CONTRACT_VERSION, "WATCH_ONLY", "NON_EXECUTABLE")
            or (timed and (self.session_date is None or self.trading_day is None or self.trading_day.state is not TradingDayState.REGULAR_TRADING_DAY or not _aware(self.regular_continuous_open) or not _aware(self.regular_continuous_close) or self.regular_continuous_open >= self.regular_continuous_close or self.reasons or len(self.phase_source_ids) != 1))
            or (self.state is EventSessionState.DURING_REGULAR_SESSION and self.daily_bar_contamination is not DailyBarContaminationState.DAILY_BAR_EVENT_CONTAMINATED)
            or (self.state in {EventSessionState.BEFORE_REGULAR_SESSION, EventSessionState.AFTER_REGULAR_SESSION} and self.daily_bar_contamination is not DailyBarContaminationState.NOT_CONTAMINATED)
            or (self.state in {EventSessionState.NON_TRADING_DAY, EventSessionState.SPECIAL_SESSION} and (self.session_date is None or self.trading_day is None or self.daily_bar_contamination is not DailyBarContaminationState.NOT_EVALUABLE))
            or (self.state is EventSessionState.NON_TRADING_DAY and (self.regular_continuous_open is not None or self.regular_continuous_close is not None or self.phase_source_ids))
            or (self.state is EventSessionState.SPECIAL_SESSION and (self.regular_continuous_open is None) != (self.regular_continuous_close is None))
            or (self.state is EventSessionState.SPECIAL_SESSION and self.regular_continuous_open is None and CalendarResolutionReason.SESSION_PHASE_TIMING_UNAVAILABLE not in self.reasons)
            or (self.state in {EventSessionState.SESSION_TIMING_UNAVAILABLE, EventSessionState.EVENT_TIMESTAMP_UNAVAILABLE, EventSessionState.TIMEZONE_UNRESOLVED, EventSessionState.EVIDENCE_CONFLICTED} and (self.regular_continuous_open is not None or self.regular_continuous_close is not None or self.daily_bar_contamination is not DailyBarContaminationState.NOT_EVALUABLE))
            or (self.state in {EventSessionState.SESSION_TIMING_UNAVAILABLE, EventSessionState.EVIDENCE_CONFLICTED} and not self.reasons)
            or (self.state not in {EventSessionState.EVIDENCE_CONFLICTED, EventSessionState.SPECIAL_SESSION} and self.phase_source_ids and not timed)
            or (self.state is EventSessionState.EVIDENCE_CONFLICTED and self.phase_source_ids and len(self.phase_source_ids) < 2)
            or (not has_day and (self.previous_session is not None or self.next_session is not None))
            or (not has_day and self.trading_day is not None and self.state is not EventSessionState.EVIDENCE_CONFLICTED)
            or (self.state in {EventSessionState.EVENT_TIMESTAMP_UNAVAILABLE, EventSessionState.TIMEZONE_UNRESOLVED} and self.session_date is not None)
            or self.fingerprint != _fingerprint(_alignment_payload(self))
        ):
            raise CanonicalMarketSessionError("EVENT_SESSION_ALIGNMENT_INVALID")


@dataclass(frozen=True, slots=True)
class CanonicalMarketSessionCalendar:
    """Immutable first-party evidence set; no source is fetched at evaluation time."""

    calendar_id: str
    exchange: Exchange
    segment: str
    coverage_start: date
    coverage_end: date
    timezone_id: str
    annual_holiday_schedules: tuple[AnnualTradingHolidaySchedule, ...]
    weekday_conventions: tuple[WeekdayTradingConvention, ...]
    special_trading_days: tuple[SpecialTradingDay, ...]
    phase_timings: tuple[EffectiveSessionPhaseTiming, ...]
    fingerprint: str

    def __post_init__(self) -> None:
        if (
            not _identifier(self.calendar_id)
            or self.exchange is not Exchange.NSE
            or self.segment != "CAPITAL_MARKET"
            or not _date(self.coverage_start)
            or not _date(self.coverage_end)
            or self.coverage_end < self.coverage_start
            or self.timezone_id != IST_TIMEZONE
            or self.annual_holiday_schedules != tuple(sorted(self.annual_holiday_schedules, key=lambda value: (value.calendar_year, value.source.source_id)))
            or self.weekday_conventions != tuple(sorted(self.weekday_conventions, key=lambda value: (value.effective_from, value.effective_to or date.max, value.convention_id)))
            or self.special_trading_days != tuple(sorted(self.special_trading_days, key=lambda value: (value.session_date, value.state.value, value.source.source_id)))
            or self.phase_timings != tuple(sorted(self.phase_timings, key=lambda value: (value.effective_from, value.effective_to or date.max, value.phase_type.value, value.timing_id)))
            or any(not isinstance(value, AnnualTradingHolidaySchedule) for value in self.annual_holiday_schedules)
            or any(not isinstance(value, WeekdayTradingConvention) for value in self.weekday_conventions)
            or any(not isinstance(value, SpecialTradingDay) for value in self.special_trading_days)
            or any(not isinstance(value, EffectiveSessionPhaseTiming) for value in self.phase_timings)
            or self.fingerprint != _fingerprint(_calendar_payload(self))
        ):
            raise CanonicalMarketSessionError("CANONICAL_MARKET_SESSION_CALENDAR_INVALID")

    def resolve_trading_day(self, session_date: date, *, as_of: datetime) -> CanonicalTradingDay:
        """Resolve a date using only sources PIT-visible at the explicit cutoff."""
        _require_as_of(as_of)
        if not _date(session_date):
            raise CanonicalMarketSessionError("CANONICAL_MARKET_SESSION_DATE_REQUIRED")
        if not self.coverage_start <= session_date <= self.coverage_end:
            return _unknown_day(self, session_date, CalendarResolutionReason.DATE_OUTSIDE_COVERAGE)
        schedules = tuple(value for value in self.annual_holiday_schedules if value.calendar_year == session_date.year)
        visible_schedules = tuple(value for value in schedules if _source_visible(value.source, as_of, self.timezone_id))
        special = tuple(value for value in self.special_trading_days if value.session_date == session_date and _source_visible(value.source, as_of, self.timezone_id))
        if special:
            if len({value.state for value in special}) != 1:
                return _unknown_day(self, session_date, CalendarResolutionReason.EVIDENCE_CONFLICTED, tuple(value.source for value in special))
            return _known_day(self, session_date, special[0].state, tuple(value.source for value in special))
        if not visible_schedules:
            return _unknown_day(self, session_date, CalendarResolutionReason.SOURCE_NOT_PIT_VISIBLE if schedules else CalendarResolutionReason.ANNUAL_HOLIDAY_EVIDENCE_UNAVAILABLE)
        superseded = {source_id for value in visible_schedules for source_id in value.supersedes_source_ids}
        effective_schedules = tuple(value for value in visible_schedules if value.source.source_id not in superseded)
        holiday_sets = {value.holidays for value in effective_schedules}
        if len(holiday_sets) != 1:
            return _unknown_day(self, session_date, CalendarResolutionReason.EVIDENCE_CONFLICTED, tuple(value.source for value in visible_schedules))
        holidays = next(iter(holiday_sets))
        if session_date in holidays:
            return _known_day(self, session_date, TradingDayState.HOLIDAY, tuple(value.source for value in visible_schedules))
        rules = tuple(value for value in self.weekday_conventions if _effective(value.effective_from, value.effective_to, session_date) and _source_visible(value.source, as_of, self.timezone_id))
        if not rules:
            return _unknown_day(self, session_date, CalendarResolutionReason.WEEKDAY_CONVENTION_UNAVAILABLE)
        weekday_sets = {value.trading_weekdays for value in rules}
        if len(weekday_sets) != 1:
            return _unknown_day(self, session_date, CalendarResolutionReason.EVIDENCE_CONFLICTED, tuple(value.source for value in rules))
        state = TradingDayState.REGULAR_TRADING_DAY if session_date.weekday() in next(iter(weekday_sets)) else TradingDayState.WEEKEND_NON_TRADING
        return _known_day(self, session_date, state, tuple(value.source for value in (*visible_schedules, *rules)))

    def phases_for(self, session_date: date, *, as_of: datetime) -> tuple[CanonicalSessionPhase, ...]:
        day = self.resolve_trading_day(session_date, as_of=as_of)
        if day.state is TradingDayState.UNKNOWN:
            return ()
        candidates = tuple(value for value in self.phase_timings if day.state in value.applies_to_states and _effective(value.effective_from, value.effective_to, session_date) and _source_visible(value.source, as_of, self.timezone_id))
        phase_groups: dict[SessionPhaseType, list[EffectiveSessionPhaseTiming]] = {}
        for value in candidates:
            phase_groups.setdefault(value.phase_type, []).append(value)
        if any(len({(item.starts_at_local, item.ends_at_local) for item in values}) > 1 for values in phase_groups.values()):
            return ()
        zone = ZoneInfo(self.timezone_id)
        return tuple(
            _phase(session_date, values[0], zone)
            for _, values in sorted(phase_groups.items(), key=lambda item: item[0].value)
        )

    def adjacent_trading_session(self, session_date: date, *, as_of: datetime, direction: int) -> date | None:
        _require_as_of(as_of)
        if not _date(session_date) or direction not in {-1, 1}:
            raise CanonicalMarketSessionError("CANONICAL_MARKET_SESSION_ADJACENT_INPUT_INVALID")
        cursor = session_date + timedelta(days=direction)
        while self.coverage_start <= cursor <= self.coverage_end:
            state = self.resolve_trading_day(cursor, as_of=as_of).state
            if state in {TradingDayState.REGULAR_TRADING_DAY, TradingDayState.SPECIAL_TRADING_DAY, TradingDayState.MUHURAT_TRADING}:
                return cursor
            if state is TradingDayState.UNKNOWN:
                return None
            cursor += timedelta(days=direction)
        return None


def make_first_party_session_source(*, source_id: str, source_reference: str, published_at: datetime | None = None, published_on: date | None = None, known_at: datetime | None = None) -> FirstPartySessionSource:
    values = dict(source_id=source_id, exchange=Exchange.NSE, segment="CAPITAL_MARKET", source_reference=source_reference, published_at=_utc(published_at) if published_at else None, published_on=published_on, known_at=_utc(known_at) if known_at else None)
    return FirstPartySessionSource(**values, fingerprint=_fingerprint(values))


def make_annual_holiday_schedule(*, calendar_year: int, source: FirstPartySessionSource, holidays: Iterable[date], supersedes_source_ids: Iterable[str] = ()) -> AnnualTradingHolidaySchedule:
    values = dict(calendar_year=calendar_year, source=source, holidays=tuple(sorted(set(holidays))), supersedes_source_ids=tuple(sorted(set(supersedes_source_ids))))
    return AnnualTradingHolidaySchedule(**values, fingerprint=_fingerprint(_holiday_schedule_values(values)))


def make_weekday_trading_convention(*, convention_id: str, effective_from: date, effective_to: date | None, trading_weekdays: Iterable[int], source: FirstPartySessionSource) -> WeekdayTradingConvention:
    values = dict(convention_id=convention_id, effective_from=effective_from, effective_to=effective_to, trading_weekdays=tuple(sorted(set(trading_weekdays))), source=source)
    return WeekdayTradingConvention(**values, fingerprint=_fingerprint(_weekday_convention_values(values)))


def make_special_trading_day(*, session_date: date, state: TradingDayState, source: FirstPartySessionSource) -> SpecialTradingDay:
    values = dict(session_date=session_date, state=state, source=source)
    return SpecialTradingDay(**values, fingerprint=_fingerprint(_special_day_values(values)))


def make_effective_session_phase_timing(*, timing_id: str, effective_from: date, effective_to: date | None, applies_to_states: Iterable[TradingDayState], phase_type: SessionPhaseType, starts_at_local: time, ends_at_local: time, source: FirstPartySessionSource) -> EffectiveSessionPhaseTiming:
    values = dict(timing_id=timing_id, effective_from=effective_from, effective_to=effective_to, applies_to_states=tuple(sorted(set(applies_to_states), key=lambda value: value.value)), phase_type=phase_type, starts_at_local=starts_at_local, ends_at_local=ends_at_local, timezone_id=IST_TIMEZONE, source=source)
    return EffectiveSessionPhaseTiming(**values, fingerprint=_fingerprint(_phase_timing_values(values)))


def make_canonical_market_session_calendar(*, calendar_id: str, coverage_start: date, coverage_end: date, annual_holiday_schedules: Iterable[AnnualTradingHolidaySchedule], weekday_conventions: Iterable[WeekdayTradingConvention], special_trading_days: Iterable[SpecialTradingDay] = (), phase_timings: Iterable[EffectiveSessionPhaseTiming] = ()) -> CanonicalMarketSessionCalendar:
    values = dict(calendar_id=calendar_id, exchange=Exchange.NSE, segment="CAPITAL_MARKET", coverage_start=coverage_start, coverage_end=coverage_end, timezone_id=IST_TIMEZONE, annual_holiday_schedules=tuple(sorted(annual_holiday_schedules, key=lambda value: (value.calendar_year, value.source.source_id))), weekday_conventions=tuple(sorted(weekday_conventions, key=lambda value: (value.effective_from, value.effective_to or date.max, value.convention_id))), special_trading_days=tuple(sorted(special_trading_days, key=lambda value: (value.session_date, value.state.value, value.source.source_id))), phase_timings=tuple(sorted(phase_timings, key=lambda value: (value.effective_from, value.effective_to or date.max, value.phase_type.value, value.timing_id))))
    return CanonicalMarketSessionCalendar(**values, fingerprint=_fingerprint(_calendar_values(values)))


def make_canonical_event_timestamp(*, event_id: str, occurred_at: datetime | None, timezone_id: str | None, state: EventTimestampState, source_id: str, source_fingerprint: str, original_timestamp: str | None = None, original_timezone: str | None = None) -> CanonicalEventTimestamp:
    values = dict(event_id=event_id, state=state, occurred_at=_normalise_event_time(occurred_at, timezone_id) if occurred_at else None, timezone_id=timezone_id, original_timestamp=original_timestamp if original_timestamp is not None else (occurred_at.isoformat() if occurred_at is not None else None), original_timezone=original_timezone if original_timezone is not None else timezone_id, source_id=source_id, source_fingerprint=source_fingerprint)
    return CanonicalEventTimestamp(**values, fingerprint=_fingerprint(_event_timestamp_values(values)))


def align_event_to_canonical_session(*, calendar: CanonicalMarketSessionCalendar, canonical_instrument_id: str, trading_venue: Exchange, event: CanonicalEventTimestamp) -> EventSessionAlignment:
    """Classify factual timing only.  Filing exchange is intentionally absent."""
    if not isinstance(calendar, CanonicalMarketSessionCalendar) or not _identifier(canonical_instrument_id) or trading_venue is not Exchange.NSE or not isinstance(event, CanonicalEventTimestamp):
        raise CanonicalMarketSessionError("EVENT_SESSION_ALIGNMENT_INPUT_INVALID")
    if event.state is EventTimestampState.EVENT_TIMESTAMP_UNAVAILABLE:
        return _alignment_unavailable(calendar, canonical_instrument_id, trading_venue, event, EventSessionState.EVENT_TIMESTAMP_UNAVAILABLE)
    if event.state is EventTimestampState.TIMEZONE_UNRESOLVED:
        return _alignment_unavailable(calendar, canonical_instrument_id, trading_venue, event, EventSessionState.TIMEZONE_UNRESOLVED)
    assert event.occurred_at is not None
    local_event = event.occurred_at.astimezone(ZoneInfo(calendar.timezone_id))
    day = calendar.resolve_trading_day(local_event.date(), as_of=event.occurred_at)
    if day.state is TradingDayState.UNKNOWN:
        return _alignment_unavailable(calendar, canonical_instrument_id, trading_venue, event, EventSessionState.EVIDENCE_CONFLICTED if CalendarResolutionReason.EVIDENCE_CONFLICTED in day.reasons else EventSessionState.SESSION_TIMING_UNAVAILABLE, session_date=local_event.date(), reasons=day.reasons, conflicted_day=day if CalendarResolutionReason.EVIDENCE_CONFLICTED in day.reasons else None)
    previous = calendar.adjacent_trading_session(local_event.date(), as_of=event.occurred_at, direction=-1)
    following = calendar.adjacent_trading_session(local_event.date(), as_of=event.occurred_at, direction=1)
    if day.state in {TradingDayState.HOLIDAY, TradingDayState.WEEKEND_NON_TRADING}:
        return _alignment(calendar, canonical_instrument_id, trading_venue, event, local_event.date(), day, EventSessionState.NON_TRADING_DAY, None, None, previous, following, DailyBarContaminationState.NOT_EVALUABLE, ())
    if day.state in {TradingDayState.SPECIAL_TRADING_DAY, TradingDayState.MUHURAT_TRADING}:
        conflicts = _phase_conflicts(calendar, local_event.date(), day.state, event.occurred_at)
        if conflicts:
            return _alignment_unavailable(calendar, canonical_instrument_id, trading_venue, event, EventSessionState.EVIDENCE_CONFLICTED, session_date=local_event.date(), phase_sources=conflicts, conflicted_day=day)
        regular = tuple(value for value in calendar.phases_for(local_event.date(), as_of=event.occurred_at) if value.phase_type is SessionPhaseType.REGULAR_CONTINUOUS)
        phase = regular[0] if len(regular) == 1 else None
        return _alignment(calendar, canonical_instrument_id, trading_venue, event, local_event.date(), day, EventSessionState.SPECIAL_SESSION, phase.starts_at if phase else None, phase.ends_at if phase else None, previous, following, DailyBarContaminationState.NOT_EVALUABLE, () if phase else (CalendarResolutionReason.SESSION_PHASE_TIMING_UNAVAILABLE,), phase_sources=((phase.source_id, phase.source_fingerprint),) if phase else ())
    phases = calendar.phases_for(local_event.date(), as_of=event.occurred_at)
    regular = tuple(value for value in phases if value.phase_type is SessionPhaseType.REGULAR_CONTINUOUS)
    if len(regular) != 1:
        conflicts = _phase_conflicts(calendar, local_event.date(), day.state, event.occurred_at)
        return _alignment_unavailable(calendar, canonical_instrument_id, trading_venue, event, EventSessionState.EVIDENCE_CONFLICTED if conflicts else EventSessionState.SESSION_TIMING_UNAVAILABLE, session_date=local_event.date(), reasons=(CalendarResolutionReason.EVIDENCE_CONFLICTED,) if conflicts else (CalendarResolutionReason.SESSION_PHASE_TIMING_UNAVAILABLE,), phase_sources=conflicts)
    phase = regular[0]
    if local_event < phase.starts_at:
        state, contamination = EventSessionState.BEFORE_REGULAR_SESSION, DailyBarContaminationState.NOT_CONTAMINATED
    elif local_event < phase.ends_at:
        state, contamination = EventSessionState.DURING_REGULAR_SESSION, DailyBarContaminationState.DAILY_BAR_EVENT_CONTAMINATED
    else:
        state, contamination = EventSessionState.AFTER_REGULAR_SESSION, DailyBarContaminationState.NOT_CONTAMINATED
    return _alignment(calendar, canonical_instrument_id, trading_venue, event, local_event.date(), day, state, phase.starts_at, phase.ends_at, previous, following, contamination, (), phase_sources=((phase.source_id, phase.source_fingerprint),))


def serialize_event_session_alignment(value: EventSessionAlignment) -> str:
    value.__post_init__()
    return json.dumps(_alignment_payload(value) | {"fingerprint": value.fingerprint}, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _known_day(calendar: CanonicalMarketSessionCalendar, session_date: date, state: TradingDayState, sources: tuple[FirstPartySessionSource, ...]) -> CanonicalTradingDay:
    ids = tuple(sorted({value.source_id for value in sources}))
    fps = tuple(sorted({value.fingerprint for value in sources}))
    values = dict(session_date=session_date, exchange=calendar.exchange, segment=calendar.segment, state=state, reasons=(), source_ids=ids, source_fingerprints=fps, calendar_fingerprint=calendar.fingerprint)
    return CanonicalTradingDay(**values, fingerprint=_fingerprint(_trading_day_values(values)))


def _unknown_day(calendar: CanonicalMarketSessionCalendar, session_date: date, reason: CalendarResolutionReason, sources: tuple[FirstPartySessionSource, ...] = ()) -> CanonicalTradingDay:
    values = dict(session_date=session_date, exchange=calendar.exchange, segment=calendar.segment, state=TradingDayState.UNKNOWN, reasons=(reason,), source_ids=tuple(sorted({value.source_id for value in sources})), source_fingerprints=tuple(sorted({value.fingerprint for value in sources})), calendar_fingerprint=calendar.fingerprint)
    return CanonicalTradingDay(**values, fingerprint=_fingerprint(_trading_day_values(values)))


def _phase(session_date: date, timing: EffectiveSessionPhaseTiming, zone: ZoneInfo) -> CanonicalSessionPhase:
    values = dict(session_date=session_date, phase_type=timing.phase_type, starts_at=datetime.combine(session_date, timing.starts_at_local, zone), ends_at=datetime.combine(session_date, timing.ends_at_local, zone), timezone_id=IST_TIMEZONE, timing_id=timing.timing_id, source_id=timing.source.source_id, source_fingerprint=timing.source.fingerprint)
    return CanonicalSessionPhase(**values, fingerprint=_fingerprint(_phase_values(values)))


def _alignment_unavailable(calendar: CanonicalMarketSessionCalendar, instrument: str, venue: Exchange, event: CanonicalEventTimestamp, state: EventSessionState, *, session_date: date | None = None, reasons: tuple[CalendarResolutionReason, ...] | None = None, phase_sources: tuple[tuple[str, str], ...] = (), conflicted_day: CanonicalTradingDay | None = None) -> EventSessionAlignment:
    actual_reasons = reasons or ({
        EventSessionState.EVENT_TIMESTAMP_UNAVAILABLE: (), EventSessionState.TIMEZONE_UNRESOLVED: (),
        EventSessionState.SESSION_TIMING_UNAVAILABLE: (CalendarResolutionReason.SESSION_PHASE_TIMING_UNAVAILABLE,),
        EventSessionState.EVIDENCE_CONFLICTED: (CalendarResolutionReason.EVIDENCE_CONFLICTED,),
    }[state])
    values = dict(canonical_instrument_id=instrument, trading_venue=venue, segment=calendar.segment, event=event, session_date=session_date, trading_day=conflicted_day, state=state, regular_continuous_open=None, regular_continuous_close=None, phase_source_ids=tuple(sorted({item[0] for item in phase_sources})), phase_source_fingerprints=tuple(sorted({item[1] for item in phase_sources})), previous_session=None, next_session=None, daily_bar_contamination=DailyBarContaminationState.NOT_EVALUABLE, reasons=tuple(sorted(set(actual_reasons), key=lambda value: value.value)), calendar_fingerprint=calendar.fingerprint)
    return EventSessionAlignment(**values, fingerprint=_fingerprint(_alignment_fingerprint_values(values)))


def _alignment(calendar: CanonicalMarketSessionCalendar, instrument: str, venue: Exchange, event: CanonicalEventTimestamp, session_date: date, day: CanonicalTradingDay, state: EventSessionState, opening: datetime | None, closing: datetime | None, previous: date | None, following: date | None, contamination: DailyBarContaminationState, reasons: tuple[CalendarResolutionReason, ...], *, phase_sources: tuple[tuple[str, str], ...] = ()) -> EventSessionAlignment:
    values = dict(canonical_instrument_id=instrument, trading_venue=venue, segment=calendar.segment, event=event, session_date=session_date, trading_day=day, state=state, regular_continuous_open=opening, regular_continuous_close=closing, phase_source_ids=tuple(sorted({item[0] for item in phase_sources})), phase_source_fingerprints=tuple(sorted({item[1] for item in phase_sources})), previous_session=previous, next_session=following, daily_bar_contamination=contamination, reasons=reasons, calendar_fingerprint=calendar.fingerprint)
    return EventSessionAlignment(**values, fingerprint=_fingerprint(_alignment_fingerprint_values(values)))


def _source_visible(source: FirstPartySessionSource, as_of: datetime, timezone_id: str) -> bool:
    cutoff = _utc(as_of)
    if source.known_at is not None:
        return _utc(source.known_at) <= cutoff
    if source.published_at is not None:
        return _utc(source.published_at) <= cutoff
    assert source.published_on is not None
    return source.published_on < cutoff.astimezone(ZoneInfo(timezone_id)).date()


def _effective(start: date, end: date | None, value: date) -> bool:
    return start <= value and (end is None or value <= end)


def _phase_conflicts(calendar: CanonicalMarketSessionCalendar, session_date: date, day_state: TradingDayState, as_of: datetime) -> tuple[tuple[str, str], ...]:
    candidates = tuple(value for value in calendar.phase_timings if day_state in value.applies_to_states and value.phase_type is SessionPhaseType.REGULAR_CONTINUOUS and _effective(value.effective_from, value.effective_to, session_date) and _source_visible(value.source, as_of, calendar.timezone_id))
    if len({(value.starts_at_local, value.ends_at_local) for value in candidates}) <= 1:
        return ()
    return tuple(sorted({(value.source.source_id, value.source.fingerprint) for value in candidates}))


def _normalise_event_time(value: datetime, timezone_id: str | None) -> datetime:
    if not _valid_timezone_timestamp(value, timezone_id):
        return value
    assert timezone_id is not None
    return value.astimezone(ZoneInfo(timezone_id))


def _valid_timezone_timestamp(value: object, timezone_id: object) -> bool:
    if not _aware(value) or not isinstance(timezone_id, str) or not timezone_id:
        return False
    try:
        zone = ZoneInfo(timezone_id)
    except ZoneInfoNotFoundError:
        return False
    assert isinstance(value, datetime)
    return value.astimezone(zone).utcoffset() == value.utcoffset()


def _source_payload(value: FirstPartySessionSource) -> dict[str, object]: return _source_values(_without(value, "fingerprint"))
def _holiday_schedule_payload(value: AnnualTradingHolidaySchedule) -> dict[str, object]: return _holiday_schedule_values(_without(value, "fingerprint"))
def _weekday_convention_payload(value: WeekdayTradingConvention) -> dict[str, object]: return _weekday_convention_values(_without(value, "fingerprint"))
def _special_day_payload(value: SpecialTradingDay) -> dict[str, object]: return _special_day_values(_without(value, "fingerprint"))
def _phase_timing_payload(value: EffectiveSessionPhaseTiming) -> dict[str, object]: return _phase_timing_values(_without(value, "fingerprint"))
def _trading_day_payload(value: CanonicalTradingDay) -> dict[str, object]: return _trading_day_values(_without(value, "fingerprint"))
def _phase_payload(value: CanonicalSessionPhase) -> dict[str, object]: return _phase_values(_without(value, "fingerprint"))
def _event_timestamp_payload(value: CanonicalEventTimestamp) -> dict[str, object]: return _event_timestamp_values(_without(value, "fingerprint"))
def _calendar_payload(value: CanonicalMarketSessionCalendar) -> dict[str, object]: return _calendar_values(_without(value, "fingerprint"))
def _alignment_payload(value: EventSessionAlignment) -> dict[str, object]: return _alignment_values(_without(value, "fingerprint", "contract_id", "contract_version", "actionability", "execution_status")) | {"contract_id": value.contract_id, "contract_version": value.contract_version, "actionability": value.actionability, "execution_status": value.execution_status}


def _source_values(values: dict[str, object]) -> dict[str, object]: return _scalar(values)
def _holiday_schedule_values(values: dict[str, object]) -> dict[str, object]: return _scalar(values)
def _weekday_convention_values(values: dict[str, object]) -> dict[str, object]: return _scalar(values)
def _special_day_values(values: dict[str, object]) -> dict[str, object]: return _scalar(values)
def _phase_timing_values(values: dict[str, object]) -> dict[str, object]: return _scalar(values)
def _trading_day_values(values: dict[str, object]) -> dict[str, object]: return _scalar(values)
def _phase_values(values: dict[str, object]) -> dict[str, object]: return _scalar(values)
def _event_timestamp_values(values: dict[str, object]) -> dict[str, object]: return _scalar(values)
def _calendar_values(values: dict[str, object]) -> dict[str, object]: return _scalar(values)
def _alignment_values(values: dict[str, object]) -> dict[str, object]: return _scalar(values)
def _alignment_fingerprint_values(values: dict[str, object]) -> dict[str, object]:
    return _alignment_values(values) | {"contract_id": CONTRACT_ID, "contract_version": CONTRACT_VERSION, "actionability": "WATCH_ONLY", "execution_status": "NON_EXECUTABLE"}


def _without(value: object, *names: str) -> dict[str, object]: return {field.name: getattr(value, field.name) for field in fields(value) if field.name not in names}


def _scalar(value: object) -> object:
    if isinstance(value, StrEnum): return value.value
    if isinstance(value, Exchange): return value.value
    if isinstance(value, datetime): return value.astimezone(UTC).isoformat()
    if isinstance(value, date): return value.isoformat()
    if isinstance(value, time): return value.isoformat()
    if isinstance(value, tuple): return tuple(_scalar(item) for item in value)
    if hasattr(value, "fingerprint") and hasattr(value, "__dataclass_fields__"):
        return {field.name: _scalar(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, dict): return {key: _scalar(item) for key, item in value.items()}
    return value


def _fingerprint(values: dict[str, object]) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(_scalar(values), sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def _identifier(value: object) -> bool: return isinstance(value, str) and _IDENTIFIER.fullmatch(value) is not None
def _fingerprint_value(value: object) -> bool: return isinstance(value, str) and _FINGERPRINT.fullmatch(value) is not None
def _date(value: object) -> bool: return isinstance(value, date) and not isinstance(value, datetime)
def _date_or_none(value: object) -> bool: return value is None or _date(value)
def _year(value: object) -> bool: return isinstance(value, int) and 2000 <= value <= 2100
def _aware(value: object) -> bool: return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None
def _aware_or_none(value: object) -> bool: return value is None or _aware(value)
def _utc(value: datetime) -> datetime:
    if not _aware(value): raise CanonicalMarketSessionError("MARKET_SESSION_AWARE_TIMESTAMP_REQUIRED")
    return value.astimezone(UTC)
def _require_as_of(value: datetime) -> None:
    if not _aware(value): raise CanonicalMarketSessionError("MARKET_SESSION_AS_OF_REQUIRED")
def _primary_nse_or_sebi_url(value: object) -> bool:
    if not isinstance(value, str): return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and (parsed.hostname or "").lower() in _PRIMARY_HOSTS


__all__ = (
    "CONTRACT_ID", "CONTRACT_VERSION", "IST_TIMEZONE", "AnnualTradingHolidaySchedule", "CalendarResolutionReason",
    "CanonicalEventTimestamp", "CanonicalMarketSessionCalendar", "CanonicalMarketSessionError", "CanonicalSessionPhase",
    "CanonicalTradingDay", "DailyBarContaminationState", "EffectiveSessionPhaseTiming", "EventSessionAlignment",
    "EventSessionState", "EventTimestampState", "FirstPartySessionSource", "SessionPhaseType", "SpecialTradingDay",
    "TradingDayState", "WeekdayTradingConvention", "align_event_to_canonical_session", "make_annual_holiday_schedule",
    "make_canonical_event_timestamp", "make_canonical_market_session_calendar", "make_effective_session_phase_timing",
    "make_first_party_session_source", "make_special_trading_day", "make_weekday_trading_convention", "serialize_event_session_alignment",
)
