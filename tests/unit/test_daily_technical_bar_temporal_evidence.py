from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

import pytest

from app.historical.canonical_market_session_event_time import (
    SessionPhaseType, TradingDayState, make_annual_holiday_schedule,
    make_canonical_market_session_calendar, make_effective_session_phase_timing,
    make_first_party_session_source, make_special_trading_day,
    make_weekday_trading_convention,
)
from app.market_data.daily_technical_bar_temporal_evidence import (
    DailyBarSourceTimingEvidence, DailyCompletenessState, DailyKnownAtState,
    DailySessionIdentityState, DailySourceAvailabilitySemantics,
    DailyStrictPitUsability, DailyTemporalReason,
    resolve_daily_technical_bar_temporal_evidence,
    serialize_daily_technical_bar_temporal_receipt,
)
from app.market_data.models import (
    AdjustmentStatus, CanonicalOHLCVBar, Exchange, InstrumentIdentity,
    InstrumentType, MarketDataProvenance, Timeframe,
)
from app.market_data.technical_bar_contract import TechnicalVolumeReadiness


T = datetime(2026, 8, 25, 12, tzinfo=UTC)
FP = "sha256:" + "a" * 64


def _source(name: str):
    return make_first_party_session_source(source_id=name, source_reference=f"https://nseindia.com/{name}", published_at=datetime(2025, 1, 1, tzinfo=UTC))


def _calendar(*, special: tuple = ()):
    holiday, weekday, phase = _source("holidays"), _source("weekdays"), _source("phase")
    return make_canonical_market_session_calendar(
        calendar_id="nse-daily-temporal-fixture", coverage_start=date(2026, 1, 1), coverage_end=date(2026, 12, 31),
        annual_holiday_schedules=(make_annual_holiday_schedule(calendar_year=2026, source=holiday, holidays=(date(2026, 8, 26),)),),
        weekday_conventions=(make_weekday_trading_convention(convention_id="weekdays", effective_from=date(2026, 1, 1), effective_to=date(2026, 12, 31), trading_weekdays=range(5), source=weekday),),
        special_trading_days=special,
        phase_timings=(make_effective_session_phase_timing(timing_id="regular", effective_from=date(2026, 1, 1), effective_to=date(2026, 12, 31), applies_to_states=(TradingDayState.REGULAR_TRADING_DAY, TradingDayState.SPECIAL_TRADING_DAY), phase_type=SessionPhaseType.REGULAR_CONTINUOUS, starts_at_local=time(9, 15), ends_at_local=time(15, 30), source=phase),),
    )


def _bar(*, volume: int | None = 100, adjustment: AdjustmentStatus = AdjustmentStatus.UNKNOWN):
    identity = InstrumentIdentity("NSE:ALPHA", Exchange.NSE, "ALPHA", "ALPHA", "INE000A01001", "EQ", InstrumentType.NSE_EQUITY, "Alpha")
    return CanonicalOHLCVBar("bar-alpha", identity, Timeframe.DAILY, T - timedelta(days=1), T, Decimal("100"), Decimal("105"), Decimal("99"), Decimal("102"), volume, None, None, adjustment, MarketDataProvenance("fixture", "fixture-alpha", T, T, T + timedelta(hours=1), "fixture-v1"))


def _timing(*, session: date | None = date(2026, 8, 25), semantics=DailySourceAvailabilitySemantics.PROVIDER_CONTRACT_AFTER_SESSION_CLOSE, known: datetime | None = None):
    return DailyBarSourceTimingEvidence("fixture", session, semantics, known, "provider-daily-contract", FP) if semantics is not DailySourceAvailabilitySemantics.UNRESOLVED else DailyBarSourceTimingEvidence("fixture", session, semantics, None, None, None)


def test_daily_bar_is_closed_only_from_explicit_session_and_provider_after_close_contract():
    result = resolve_daily_technical_bar_temporal_evidence(canonical_bar_id="technical-bar:alpha", bar=_bar(), calendar=_calendar(), evaluation_as_of=T, source_timing=_timing())
    assert result.session_identity is DailySessionIdentityState.RESOLVED
    assert result.completeness is DailyCompletenessState.CLOSED
    assert result.known_at_state is DailyKnownAtState.RESOLVED_SESSION_CLOSE
    assert result.known_at <= T and result.strict_pit_usability is DailyStrictPitUsability.USABLE
    assert serialize_daily_technical_bar_temporal_receipt(result) == serialize_daily_technical_bar_temporal_receipt(result)


def test_current_session_is_in_progress_and_fetched_at_never_becomes_known_at():
    result = resolve_daily_technical_bar_temporal_evidence(canonical_bar_id="technical-bar:alpha", bar=_bar(), calendar=_calendar(), evaluation_as_of=datetime(2026, 8, 25, 5, tzinfo=UTC), source_timing=_timing())
    assert result.completeness is DailyCompletenessState.IN_PROGRESS
    assert result.known_at is None and result.source_received_at == T + timedelta(hours=1)
    assert DailyTemporalReason.CURRENT_SESSION_IN_PROGRESS in result.reasons


def test_source_timing_and_session_date_are_never_invented_from_stored_bar_timestamps():
    result = resolve_daily_technical_bar_temporal_evidence(canonical_bar_id="technical-bar:alpha", bar=_bar(), calendar=_calendar(), evaluation_as_of=T, source_timing=_timing(session=None, semantics=DailySourceAvailabilitySemantics.UNRESOLVED))
    assert result.session_identity is DailySessionIdentityState.SESSION_UNRESOLVED
    assert result.known_at_state is DailyKnownAtState.SOURCE_TIMING_UNRESOLVED
    assert result.strict_pit_usability is DailyStrictPitUsability.BLOCKED
    assert DailyTemporalReason.SOURCE_SESSION_DATE_UNRESOLVED in result.reasons


def test_holiday_bar_is_conflicted_but_special_weekend_session_is_valid_when_source_backed():
    holiday = resolve_daily_technical_bar_temporal_evidence(canonical_bar_id="technical-bar:holiday", bar=_bar(), calendar=_calendar(), evaluation_as_of=T, source_timing=_timing(session=date(2026, 8, 26)))
    assert holiday.session_identity is DailySessionIdentityState.NON_TRADING_SESSION
    assert holiday.completeness is DailyCompletenessState.EVIDENCE_CONFLICTED
    special_source = _source("budget")
    special = make_special_trading_day(session_date=date(2026, 8, 29), state=TradingDayState.SPECIAL_TRADING_DAY, source=special_source)
    weekend = resolve_daily_technical_bar_temporal_evidence(canonical_bar_id="technical-bar:special", bar=_bar(), calendar=_calendar(special=(special,)), evaluation_as_of=datetime(2026, 8, 30, tzinfo=UTC), source_timing=_timing(session=date(2026, 8, 29)))
    assert weekend.session_identity is DailySessionIdentityState.RESOLVED
    assert weekend.completeness is DailyCompletenessState.CLOSED


def test_explicit_publication_before_close_and_after_pit_cutoff_fail_closed():
    before_close = _timing(semantics=DailySourceAvailabilitySemantics.EXPLICIT_PUBLICATION_TIMESTAMP, known=datetime(2026, 8, 25, 9, tzinfo=UTC))
    result = resolve_daily_technical_bar_temporal_evidence(canonical_bar_id="technical-bar:alpha", bar=_bar(), calendar=_calendar(), evaluation_as_of=T, source_timing=before_close)
    assert result.completeness is DailyCompletenessState.COMPLETENESS_UNRESOLVED
    late = _timing(semantics=DailySourceAvailabilitySemantics.EXPLICIT_PUBLICATION_TIMESTAMP, known=T + timedelta(days=1))
    result = resolve_daily_technical_bar_temporal_evidence(canonical_bar_id="technical-bar:late", bar=_bar(), calendar=_calendar(), evaluation_as_of=T, source_timing=late)
    assert result.completeness is DailyCompletenessState.CLOSED
    assert result.strict_pit_usability is DailyStrictPitUsability.BLOCKED


def test_volume_and_adjustment_readiness_remain_separate_from_temporal_readiness():
    result = resolve_daily_technical_bar_temporal_evidence(canonical_bar_id="technical-bar:alpha", bar=_bar(volume=None, adjustment=AdjustmentStatus.UNKNOWN), calendar=_calendar(), evaluation_as_of=T, source_timing=_timing())
    assert result.strict_pit_usability is DailyStrictPitUsability.USABLE
    assert result.volume_readiness is TechnicalVolumeReadiness.VOLUME_NOT_READY
    assert result.adjustment_status is AdjustmentStatus.UNKNOWN


def test_receipt_is_deterministic_and_requires_daily_provider_match():
    first = resolve_daily_technical_bar_temporal_evidence(canonical_bar_id="technical-bar:alpha", bar=_bar(), calendar=_calendar(), evaluation_as_of=T, source_timing=_timing())
    second = resolve_daily_technical_bar_temporal_evidence(canonical_bar_id="technical-bar:alpha", bar=_bar(), calendar=_calendar(), evaluation_as_of=T, source_timing=_timing())
    assert first.fingerprint == second.fingerprint
    with pytest.raises(Exception, match="RESOLUTION_INPUT"):
        resolve_daily_technical_bar_temporal_evidence(canonical_bar_id="technical-bar:alpha", bar=_bar(), calendar=_calendar(), evaluation_as_of=T, source_timing=DailyBarSourceTimingEvidence("other", date(2026, 8, 25), DailySourceAvailabilitySemantics.UNRESOLVED, None, None, None))
