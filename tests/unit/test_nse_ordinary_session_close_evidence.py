"""Focused forward-only ordinary NSE session/close evidence tests."""
from __future__ import annotations

import ast
from datetime import UTC, date, datetime, time
from decimal import Decimal
import inspect
from pathlib import Path

import pytest

import app.historical.nse_capital_market_session_evidence_2022_2026 as evidence_module
from app.domain.models import DataQuality
from app.historical.canonical_market_session_event_time import (
    CalendarResolutionReason, SessionPhaseType, TradingDayState,
)
from app.historical.nse_capital_market_session_evidence_2022_2026 import (
    nse_capital_market_calendar_2022_2026,
)
from app.market_data.daily_source_temporal_semantics import (
    daily_source_timing_from_temporal_facts, nse_bhavcopy_daily_semantics,
    resolve_daily_source_temporal_facts, upstox_v3_daily_legacy_semantics,
    upstox_v4_daily_interval_start_semantics,
)
from app.market_data.daily_technical_bar_temporal_evidence import (
    DailyCompletenessState, DailyKnownAtState, DailyStrictPitUsability,
    resolve_daily_technical_bar_temporal_evidence,
)
from app.market_data.models import (
    AdjustmentStatus, CanonicalOHLCVBar, Exchange, InstrumentIdentity,
    InstrumentType, MarketDataProvenance, Timeframe,
)


CURRENT_RULE_KNOWN_AT = datetime(2026, 9, 5, 16, 47, tzinfo=UTC)
FORWARD_AS_OF = datetime(2026, 9, 7, 12, tzinfo=UTC)
RAW_SESSION_START = datetime(2026, 9, 6, 18, 30, tzinfo=UTC)
OBSERVED_AFTER_CLOSE = datetime(2026, 9, 7, 11, tzinfo=UTC)


def _bar(
    *, provider: str, version: str, exchange: Exchange = Exchange.NSE,
    instrument_type: InstrumentType = InstrumentType.NSE_EQUITY,
) -> CanonicalOHLCVBar:
    instrument_id = (
        "NSE:ALPHA" if instrument_type is InstrumentType.NSE_EQUITY
        else "NIFTY_50" if instrument_type is InstrumentType.BROAD_INDEX
        else "NIFTY_SECTOR_BANK"
    )
    instrument = InstrumentIdentity(
        instrument_id, exchange, instrument_id, instrument_id,
        "INE000A01001" if instrument_type is InstrumentType.NSE_EQUITY else None,
        "EQ" if instrument_type is InstrumentType.NSE_EQUITY else None,
        instrument_type, instrument_id,
    )
    return CanonicalOHLCVBar(
        "bar:" + instrument_id.lower(), instrument, Timeframe.DAILY,
        RAW_SESSION_START, RAW_SESSION_START,
        Decimal("100"), Decimal("105"), Decimal("99"), Decimal("102"),
        100, None, None, AdjustmentStatus.UNKNOWN,
        MarketDataProvenance(
            provider, "provider:" + instrument_id, RAW_SESSION_START,
            RAW_SESSION_START, OBSERVED_AFTER_CLOSE, version,
        ),
        DataQuality.HIGH,
    )


def test_catalogue_is_static_and_has_no_storage_provider_execution_or_runtime_clock_dependency() -> None:
    source = Path(inspect.getfile(evidence_module)).read_text(encoding="utf-8")
    imports = {
        item.name
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Import)
        for item in node.names
    } | {
        node.module or ""
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom)
    }
    forbidden_prefixes = (
        "app.api", "app.broker", "app.orders", "app.portfolio", "app.signals",
        "sqlite3", "requests", "httpx",
    )
    assert not any(value.startswith(prefix) for value in imports for prefix in forbidden_prefixes)
    assert "datetime.now" not in source and "datetime.utcnow" not in source


def test_current_nse_equity_rule_is_effective_dated_and_uses_regular_continuous_close_only() -> None:
    calendar = nse_capital_market_calendar_2022_2026()

    day = calendar.resolve_trading_day(date(2026, 9, 7), as_of=FORWARD_AS_OF)
    phases = calendar.phases_for(date(2026, 9, 7), as_of=FORWARD_AS_OF)

    assert calendar.calendar_id == "nse-capital-market-first-party-2022-2026-v2-ordinary-forward"
    assert day.state is TradingDayState.REGULAR_TRADING_DAY
    regular = [phase for phase in phases if phase.phase_type is SessionPhaseType.REGULAR_CONTINUOUS]
    assert len(regular) == 1
    assert regular[0].starts_at.timetz().replace(tzinfo=None) == time(9, 15)
    assert regular[0].ends_at.timetz().replace(tzinfo=None) == time(15, 30)
    assert regular[0].source_id == "nse-equity-market-timings-current-2026-09-05"
    assert all(phase.phase_type is not SessionPhaseType.CLOSING_SESSION for phase in phases)


def test_current_timing_evidence_never_leaks_to_an_earlier_cutoff_or_prior_years() -> None:
    calendar = nse_capital_market_calendar_2022_2026()

    not_yet_known = calendar.resolve_trading_day(
        date(2026, 9, 7), as_of=CURRENT_RULE_KNOWN_AT.replace(minute=46),
    )
    assert not_yet_known.state is TradingDayState.UNKNOWN
    assert not_yet_known.reasons == (CalendarResolutionReason.WEEKDAY_CONVENTION_UNAVAILABLE,)
    assert calendar.resolve_trading_day(
        date(2026, 9, 7), as_of=CURRENT_RULE_KNOWN_AT,
    ).state is TradingDayState.REGULAR_TRADING_DAY
    for ordinary_date in (
        date(2022, 6, 6), date(2023, 6, 5), date(2024, 6, 3),
        date(2025, 6, 2), date(2026, 9, 4),
    ):
        result = calendar.resolve_trading_day(ordinary_date, as_of=FORWARD_AS_OF)
        assert result.state is TradingDayState.UNKNOWN
        assert result.reasons == (CalendarResolutionReason.WEEKDAY_CONVENTION_UNAVAILABLE,)


def test_holidays_and_source_backed_special_overrides_win_over_the_ordinary_weekday_rule() -> None:
    calendar = nse_capital_market_calendar_2022_2026()

    assert calendar.resolve_trading_day(date(2026, 9, 14), as_of=FORWARD_AS_OF).state is TradingDayState.HOLIDAY
    budget = calendar.resolve_trading_day(date(2026, 2, 1), as_of=FORWARD_AS_OF)
    assert budget.state is TradingDayState.SPECIAL_TRADING_DAY
    budget_regular = [
        phase for phase in calendar.phases_for(date(2026, 2, 1), as_of=FORWARD_AS_OF)
        if phase.phase_type is SessionPhaseType.REGULAR_CONTINUOUS
    ]
    assert len(budget_regular) == 1
    pending_muhurat = calendar.resolve_trading_day(date(2026, 11, 8), as_of=FORWARD_AS_OF)
    assert pending_muhurat.state is TradingDayState.MUHURAT_TRADING
    assert calendar.phases_for(date(2026, 11, 8), as_of=FORWARD_AS_OF) == ()


@pytest.mark.parametrize(
    ("exchange", "instrument_type"),
    (
        (Exchange.NSE, InstrumentType.NSE_EQUITY),
        (Exchange.INDEX, InstrumentType.BROAD_INDEX),
        (Exchange.INDEX, InstrumentType.SECTOR_INDEX),
    ),
)
def test_forward_upstox_observation_is_strict_pit_usable_only_after_current_session_close(
    exchange: Exchange, instrument_type: InstrumentType,
) -> None:
    bar = _bar(
        provider="upstox", version="upstox-history-v4-interval-start",
        exchange=exchange, instrument_type=instrument_type,
    )
    facts = resolve_daily_source_temporal_facts(bar, upstox_v4_daily_interval_start_semantics())
    receipt = resolve_daily_technical_bar_temporal_evidence(
        canonical_bar_id="technical:" + bar.bar_id,
        bar=bar, calendar=nse_capital_market_calendar_2022_2026(),
        evaluation_as_of=FORWARD_AS_OF,
        source_timing=daily_source_timing_from_temporal_facts(facts),
    )

    assert receipt.regular_session_close == datetime(2026, 9, 7, 10, tzinfo=UTC)
    assert receipt.completeness is DailyCompletenessState.CLOSED
    assert receipt.known_at_state is DailyKnownAtState.KNOWN_AT_FROM_HSI_OBSERVATION
    assert receipt.known_at == OBSERVED_AFTER_CLOSE
    assert receipt.strict_pit_usability is DailyStrictPitUsability.USABLE


def test_bhavcopy_can_use_the_same_forward_observation_bridge_but_legacy_upstox_cannot() -> None:
    bhavcopy = _bar(provider="NSE_OFFICIAL", version="nse-full-bhavcopy-v1")
    facts = resolve_daily_source_temporal_facts(bhavcopy, nse_bhavcopy_daily_semantics())
    receipt = resolve_daily_technical_bar_temporal_evidence(
        canonical_bar_id="technical:bhavcopy", bar=bhavcopy,
        calendar=nse_capital_market_calendar_2022_2026(),
        evaluation_as_of=FORWARD_AS_OF,
        source_timing=daily_source_timing_from_temporal_facts(facts),
    )
    assert receipt.strict_pit_usability is DailyStrictPitUsability.USABLE
    legacy = _bar(provider="upstox", version="upstox-history-v3")
    legacy_facts = resolve_daily_source_temporal_facts(legacy, upstox_v3_daily_legacy_semantics())
    with pytest.raises(ValueError, match="TIMING_BRIDGE_UNAVAILABLE"):
        daily_source_timing_from_temporal_facts(legacy_facts)
