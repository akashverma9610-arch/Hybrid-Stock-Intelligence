from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.connections.credentials import InMemoryCredentialStore
from app.connections.models import ConnectionMode
from app.connections.repository import SQLiteConnectionProfileRepository
from app.connections.service import ProviderConnectionService, UpstoxHistoricalConnectionTester, _automatic_upstox_test_instrument
from app.market_data.models import ErrorCode, MarketDataError, Timeframe
from app.market_data.historical import SQLiteHistoricalBarStore
from app.market_data.upstox import (
    UPSTOX_PROVIDER,
    UpstoxHistoricalProvider,
    UpstoxInstrumentMaster,
    parse_upstox_instrument_records,
)
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository
from app.universe_analysis.models import NseEquityInstrument
from app.universe_analysis.service import CoreUniverseAnalysisStore


T = datetime(2026, 8, 24, 12, tzinfo=UTC)


def _master() -> UpstoxInstrumentMaster:
    return UpstoxInstrumentMaster(
        "https://example.invalid/upstox-nse-bod.json.gz", "master-checksum",
        parse_upstox_instrument_records([{
            "instrument_key": "NSE_EQ|INE002A01018", "segment": "NSE_EQ", "exchange": "NSE",
            "isin": "INE002A01018", "instrument_type": "EQ", "trading_symbol": "RELIANCE",
        }]),
    )


def _payload() -> dict:
    return {"status": "success", "data": {"candles": [
        [(T - timedelta(days=4)).isoformat(), "100.01", "103", "99", "102.50", 1234],
        [(T - timedelta(days=3)).isoformat(), "102.50", "105", "101", "104.25", 2345],
    ]}}


def _service(tmp_path: Path, *, records=None, historical_error: MarketDataError | None = None, save_optional_token: bool = True):
    core = CoreUniverseAnalysisStore(SQLiteCoreApiSnapshotRepository(tmp_path / "core.sqlite"))
    core.save_instrument(NseEquityInstrument(
        "NSE:RELIANCE", "RELIANCE", "INE002A01018", None, None, "ACTIVE", None,
        True, T - timedelta(days=1), "NSE_OFFICIAL_EXPORT", main_board=True,
    ))
    calls: list[object] = []

    def provider_factory(token: str) -> UpstoxHistoricalProvider:
        assert token == "secure-token"
        def transport(request):
            calls.append(request)
            if historical_error is not None:
                raise historical_error
            return _payload()
        return UpstoxHistoricalProvider(token, transport=transport, clock=lambda: T)

    tester = UpstoxHistoricalConnectionTester(
        provider_factory=provider_factory,
        universe_store_provider=lambda: core,
        historical_store_provider=lambda: SQLiteHistoricalBarStore(tmp_path / "history.sqlite"),
        instrument_master_loader=lambda: records if records is not None else _master(),
        clock=lambda: T,
    )
    service = ProviderConnectionService(
        SQLiteConnectionProfileRepository(str(tmp_path / "profiles.sqlite")),
        InMemoryCredentialStore(), {UPSTOX_PROVIDER: tester}, clock=lambda: T,
    )
    if save_optional_token:
        service.update_upstox({"access_token": "secure-token"})
    return service, core, calls


def test_upstox_connection_test_auto_resolves_persists_and_ingests_one_bounded_history_request(tmp_path) -> None:
    service, core, calls = _service(tmp_path)

    result = service.test_upstox()

    assert result.status.value == "CONNECTED"
    assert result.mode is ConnectionMode.HISTORICAL_OHLCV
    assert result.test_symbol == "RELIANCE"
    assert result.validation_flow == {
        "credentials": "VALIDATED", "instrument_resolution": "VALIDATED",
        "historical_access": "VALIDATED", "normalization": "VALIDATED",
        "persistence": "VALIDATED", "last_tested_timestamp": T.isoformat(),
        "error_message": None,
    }
    assert len(calls) == 1
    mapping = core.provider_mapping(canonical_instrument_id="NSE:RELIANCE", provider=UPSTOX_PROVIDER, as_of=T)
    assert mapping is not None
    assert mapping.provider_instrument_reference == "NSE_EQ|INE002A01018"
    assert mapping.source_checksum == "master-checksum"
    persisted = SQLiteHistoricalBarStore(tmp_path / "history.sqlite")
    try:
        assert len(persisted.latest("NSE:RELIANCE", Timeframe.DAILY, 2)) == 2
    finally:
        persisted.close()
    assert service.upstox_profile().capabilities == (ConnectionMode.HISTORICAL_OHLCV,)


def test_upstox_connection_test_fails_closed_when_master_has_no_exact_local_intersection(tmp_path) -> None:
    service, core, calls = _service(tmp_path, records=UpstoxInstrumentMaster(
        "https://example.invalid/master", "other-checksum", parse_upstox_instrument_records([{
            "instrument_key": "NSE_EQ|OTHER", "segment": "NSE_EQ", "exchange": "NSE",
            "isin": "INE000000000", "instrument_type": "EQ", "trading_symbol": "OTHER",
        }]),
    ))

    result = service.test_upstox()

    assert result.error_code == "INSTRUMENT_RESOLUTION_FAILED"
    assert result.validation_flow is not None
    assert result.validation_flow["instrument_resolution"] == "FAILED"
    assert result.validation_flow["historical_access"] == "NOT_TESTED"
    assert not calls
    assert core.provider_mapping(canonical_instrument_id="NSE:RELIANCE", provider=UPSTOX_PROVIDER, as_of=T) is None


def test_upstox_missing_token_returns_a_stage_aware_configuration_failure(tmp_path) -> None:
    service, _core, calls = _service(tmp_path, save_optional_token=False)

    result = service.test_upstox()

    assert not calls
    assert result.error_code == "MISSING_CONFIGURATION"
    assert result.validation_flow == {
        "credentials": "FAILED", "instrument_resolution": "NOT_TESTED",
        "historical_access": "UNAVAILABLE", "normalization": "NOT_TESTED",
        "persistence": "NOT_TESTED", "last_tested_timestamp": T.isoformat(),
        "error_message": "Upstox Analytics Token is not configured.",
    }


def test_upstox_authorization_failure_from_the_real_provider_boundary_is_not_mislabeled_as_normalization(tmp_path) -> None:
    # Sanitized fixture for the observed provider HTTP 403 boundary: the
    # provider maps it to AUTHORIZATION_FAILURE before any candle payload is
    # parsed, so no raw provider body is retained by the test or application.
    service, core, calls = _service(
        tmp_path,
        historical_error=MarketDataError(ErrorCode.AUTHORIZATION_FAILURE, "Upstox historical access is not authorized."),
    )

    result = service.test_upstox()

    assert len(calls) == 1
    assert result.error_code == "HISTORICAL_ACCESS_FAILED"
    assert result.validation_flow == {
        "credentials": "VALIDATED", "instrument_resolution": "VALIDATED",
        "historical_access": "FAILED", "normalization": "NOT_TESTED",
        "persistence": "NOT_TESTED", "last_tested_timestamp": T.isoformat(),
        "error_message": "Upstox historical access is not authorized.",
    }
    assert core.provider_mapping(canonical_instrument_id="NSE:RELIANCE", provider=UPSTOX_PROVIDER, as_of=T) is not None


def test_upstox_automatic_selection_prioritizes_any_exact_isin_over_an_earlier_symbol_fallback(tmp_path) -> None:
    core = CoreUniverseAnalysisStore(SQLiteCoreApiSnapshotRepository(tmp_path / "core.sqlite"))
    core.save_instrument(NseEquityInstrument("NSE:ALPHA", "ALPHA", None, None, None, "ACTIVE", None, True, T, "NSE", main_board=True))
    core.save_instrument(NseEquityInstrument("NSE:ZETA", "ZETA", "INE000000001", None, None, "ACTIVE", None, True, T, "NSE", main_board=True))
    records = parse_upstox_instrument_records([
        {"instrument_key": "NSE_EQ|ALPHA", "segment": "NSE_EQ", "exchange": "NSE", "instrument_type": "EQ", "trading_symbol": "ALPHA"},
        {"instrument_key": "NSE_EQ|INE000000001", "segment": "NSE_EQ", "exchange": "NSE", "isin": "INE000000001", "instrument_type": "EQ", "trading_symbol": "ZETA"},
    ])

    selected = _automatic_upstox_test_instrument(core, records, as_of=T)

    assert selected is not None
    identity, method = selected
    assert (identity.instrument_id, method) == ("NSE:ZETA", "EXACT_ISIN_NSE_CASH")
