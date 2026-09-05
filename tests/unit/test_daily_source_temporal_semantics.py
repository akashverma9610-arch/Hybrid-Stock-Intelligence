from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.domain.models import DataQuality
from app.market_data.daily_source_temporal_semantics import (
    DailySourceAvailabilityState, DailySourceLegacyState,
    DailySourceTimestampRole, daily_interval_end_is_trusted,
    daily_source_timing_from_temporal_facts, nse_bhavcopy_daily_semantics,
    resolve_daily_source_temporal_facts, upstox_v3_daily_legacy_semantics,
    upstox_v4_daily_interval_start_semantics, yfinance_daily_semantics,
)
from app.market_data.models import (
    AdjustmentStatus, CanonicalOHLCVBar, Exchange, InstrumentIdentity,
    InstrumentType, MarketDataProvenance, Timeframe,
)


RAW = datetime(2026, 8, 21, 18, 30, tzinfo=UTC)
OBSERVED = datetime(2026, 8, 22, 4, tzinfo=UTC)


def _bar(
    *, provider: str, version: str, start: datetime, end: datetime,
    raw: datetime | None = RAW,
) -> CanonicalOHLCVBar:
    instrument = InstrumentIdentity(
        "NSE:ALPHA", Exchange.NSE, "ALPHA", "ALPHA", "INE000A01001", "EQ",
        InstrumentType.NSE_EQUITY, "Alpha",
    )
    return CanonicalOHLCVBar(
        "bar-alpha", instrument, Timeframe.DAILY, start, end,
        Decimal("100"), Decimal("105"), Decimal("99"), Decimal("102"), 100,
        None, None, AdjustmentStatus.UNKNOWN,
        MarketDataProvenance(provider, "provider-alpha", raw, raw, OBSERVED, version),
        DataQuality.HIGH,
    )


def test_retained_upstox_raw_start_is_recoverable_but_legacy_end_is_ambiguous() -> None:
    bar = _bar(provider="upstox", version="upstox-history-v3", start=RAW.replace(day=20), end=RAW)

    facts = resolve_daily_source_temporal_facts(bar, upstox_v3_daily_legacy_semantics())

    assert facts.raw_timestamp == RAW
    assert facts.raw_timestamp_role is DailySourceTimestampRole.INTERVAL_START
    assert facts.session_date.isoformat() == "2026-08-22"
    assert facts.legacy_state is DailySourceLegacyState.LEGACY_SEMANTICS_AMBIGUOUS
    assert facts.availability_state is DailySourceAvailabilityState.HSI_OBSERVED_AT_ONLY
    assert facts.forward_known_at is None
    assert not daily_interval_end_is_trusted(bar, facts)
    with pytest.raises(ValueError, match="TIMING_BRIDGE_UNAVAILABLE"):
        daily_source_timing_from_temporal_facts(facts)


def test_mismatched_retained_upstox_raw_and_end_is_conflicted_not_repaired() -> None:
    bar = _bar(provider="upstox", version="upstox-history-v3", start=RAW, end=RAW + timedelta(hours=1))

    facts = resolve_daily_source_temporal_facts(bar, upstox_v3_daily_legacy_semantics())

    assert facts.legacy_state is DailySourceLegacyState.SOURCE_SEMANTICS_CONFLICTED
    assert facts.availability_state is DailySourceAvailabilityState.HISTORICAL_KNOWN_AT_UNAVAILABLE
    assert facts.forward_known_at is None


def test_corrected_upstox_path_preserves_interval_start_and_only_uses_observation_forward() -> None:
    bar = _bar(provider="upstox", version="upstox-history-v4-interval-start", start=RAW, end=RAW)

    facts = resolve_daily_source_temporal_facts(bar, upstox_v4_daily_interval_start_semantics())
    timing = daily_source_timing_from_temporal_facts(facts)

    assert facts.raw_timestamp == RAW
    assert facts.session_date.isoformat() == "2026-08-22"
    assert facts.legacy_state is DailySourceLegacyState.SOURCE_SEMANTICS_RESOLVED
    assert facts.source_available_at is None
    assert facts.availability_state is DailySourceAvailabilityState.HSI_OBSERVED_AT_ONLY
    assert timing.hsi_observed_at == OBSERVED
    assert timing.explicit_known_at is None
    assert not daily_interval_end_is_trusted(bar, facts)


def test_nse_bhavcopy_date_is_a_session_label_not_a_publication_instant() -> None:
    bar = _bar(
        provider="NSE_OFFICIAL", version="nse-full-bhavcopy-v1",
        start=RAW, end=RAW,
    )

    facts = resolve_daily_source_temporal_facts(bar, nse_bhavcopy_daily_semantics())

    assert facts.raw_timestamp_role is DailySourceTimestampRole.TRADING_DATE
    assert facts.session_date.isoformat() == "2026-08-22"
    assert facts.source_available_at is None
    assert facts.availability_state is DailySourceAvailabilityState.HSI_OBSERVED_AT_ONLY
    assert facts.legacy_state is DailySourceLegacyState.SOURCE_SEMANTICS_RESOLVED


def test_yfinance_secondary_rows_are_not_upgraded_to_temporal_authority() -> None:
    bar = _bar(provider="yfinance", version="yfinance-history-v1", start=RAW, end=RAW)

    facts = resolve_daily_source_temporal_facts(bar, yfinance_daily_semantics())

    assert facts.raw_timestamp_role is DailySourceTimestampRole.UNKNOWN
    assert facts.session_date is None
    assert facts.availability_state is DailySourceAvailabilityState.HISTORICAL_KNOWN_AT_UNAVAILABLE
    assert facts.legacy_state is DailySourceLegacyState.LEGACY_SEMANTICS_AMBIGUOUS
    with pytest.raises(ValueError, match="TIMING_BRIDGE_UNAVAILABLE"):
        daily_source_timing_from_temporal_facts(facts)


@pytest.mark.parametrize(
    ("instrument_id", "instrument_type"),
    (("NIFTY_50", InstrumentType.BROAD_INDEX), ("NIFTY_SECTOR_BANK", InstrumentType.SECTOR_INDEX)),
)
def test_benchmark_and_sector_upstox_rows_share_the_same_legacy_source_contract(
    instrument_id: str, instrument_type: InstrumentType,
) -> None:
    bar = replace(
        _bar(provider="upstox", version="upstox-history-v3", start=RAW.replace(day=20), end=RAW),
        instrument=InstrumentIdentity(
            instrument_id, Exchange.INDEX, instrument_id, instrument_id, None, None,
            instrument_type, instrument_id,
        ),
    )

    facts = resolve_daily_source_temporal_facts(bar, upstox_v3_daily_legacy_semantics())

    assert facts.raw_timestamp_role is DailySourceTimestampRole.INTERVAL_START
    assert facts.legacy_state is DailySourceLegacyState.LEGACY_SEMANTICS_AMBIGUOUS
    assert not daily_interval_end_is_trusted(bar, facts)


def test_source_contracts_and_fact_fingerprints_are_deterministic_and_tamper_evident() -> None:
    semantics = upstox_v4_daily_interval_start_semantics()
    first = resolve_daily_source_temporal_facts(
        _bar(provider="upstox", version="upstox-history-v4-interval-start", start=RAW, end=RAW), semantics,
    )
    second = resolve_daily_source_temporal_facts(
        _bar(provider="upstox", version="upstox-history-v4-interval-start", start=RAW, end=RAW), semantics,
    )

    assert semantics.fingerprint == upstox_v4_daily_interval_start_semantics().fingerprint
    assert first.fingerprint == second.fingerprint
    with pytest.raises(ValueError, match="FACTS_INVALID"):
        type(first)(**{**{name: getattr(first, name) for name in first.__dataclass_fields__}, "session_date": RAW.date()})
