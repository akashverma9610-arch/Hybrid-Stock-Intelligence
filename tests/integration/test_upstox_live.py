"""One explicit opt-in Upstox V3 smoke; never runs in the default suite."""
from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import pytest

from app.market_data.historical import HistoricalIngestionService, SQLiteHistoricalBarStore
from app.market_data.models import Exchange, HistoricalBarsRequest, InstrumentIdentity, InstrumentType, ProviderInstrumentMapping, Timeframe
from app.market_data.upstox import UPSTOX_PROVIDER, UpstoxHistoricalProvider


_ENABLED = all((
    os.getenv("UPSTOX_LIVE_VALIDATION") == "true",
    os.getenv("UPSTOX_ACCESS_TOKEN"),
    os.getenv("UPSTOX_TEST_INSTRUMENT_KEY"),
))


@pytest.mark.skipif(not _ENABLED, reason="Upstox V3 live validation is disabled or local token/test mapping is incomplete.")
def test_upstox_v3_daily_history_is_explicit_and_bounded() -> None:
    """Exactly one bounded provider request and canonical persistence check."""
    now = datetime.now(UTC)
    key = os.environ["UPSTOX_TEST_INSTRUMENT_KEY"]
    symbol = os.getenv("UPSTOX_TEST_SYMBOL", "UPSTOX_TEST")
    instrument = InstrumentIdentity(
        f"UPSTOX_TEST:{key}", Exchange.NSE, symbol, symbol, None, None,
        InstrumentType.NSE_EQUITY, None,
        provider_mappings=(ProviderInstrumentMapping(UPSTOX_PROVIDER, key, symbol, "upstox-v3", "NSE_EQ"),),
    )
    request = HistoricalBarsRequest(instrument, Timeframe.DAILY, now - timedelta(days=7), now, provider_preference=UPSTOX_PROVIDER)
    report = HistoricalIngestionService(UpstoxHistoricalProvider(os.environ["UPSTOX_ACCESS_TOKEN"]), SQLiteHistoricalBarStore(), clock=lambda: now + timedelta(days=1)).ingest(request)
    assert report.received_count >= report.accepted_count >= 1
    assert report.provider == UPSTOX_PROVIDER
