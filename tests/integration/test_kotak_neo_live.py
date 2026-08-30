"""Opt-in, read-only Kotak Neo smoke test; disabled unless isolated test env is set."""
from __future__ import annotations

import os

import pytest

from app.market_data.kotak_neo import KotakNeoCredentials, KotakNeoInstrumentMaster, KotakNeoInstrumentRecord, KotakNeoMarketDataProvider


_required = ("KOTAK_NEO_TEST_ENABLED", "KOTAK_NEO_TRADEAPI_ACCESS_TOKEN", "KOTAK_NEO_TEST_EXCHANGE_SEGMENT", "KOTAK_NEO_TEST_INSTRUMENT_TOKEN", "KOTAK_NEO_TEST_SYMBOL")
pytestmark = pytest.mark.skipif(
    os.environ.get("KOTAK_NEO_TEST_ENABLED", "").lower() != "true" or any(not os.environ.get(name) for name in _required[1:]),
    reason="Kotak Neo live validation is disabled or isolated test credentials are incomplete.",
)


def test_opt_in_read_only_quote_smoke() -> None:
    record = KotakNeoInstrumentRecord(os.environ["KOTAK_NEO_TEST_EXCHANGE_SEGMENT"], os.environ["KOTAK_NEO_TEST_INSTRUMENT_TOKEN"], os.environ["KOTAK_NEO_TEST_SYMBOL"])
    provider = KotakNeoMarketDataProvider(KotakNeoCredentials.from_environment(), instrument_master=KotakNeoInstrumentMaster((record,)))
    quote = provider.get_quote(provider.resolve_instrument(record.symbol))
    assert quote.instrument.symbol == record.symbol
