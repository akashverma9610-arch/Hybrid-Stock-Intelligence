from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
import inspect
import sys
import types

import pytest

from app.market_data.kotak_neo import (
    KOTAK_NEO_LOGIN_URL,
    KOTAK_NEO_VALIDATE_URL,
    KotakNeoCredentials,
    KotakNeoHttpResponse,
    KotakNeoInstrumentMaster,
    KotakNeoInstrumentRecord,
    KotakNeoMarketDataProvider,
    HttpxKotakNeoTransport,
    KotakNeoAuthenticationError,
    _identity,
    _master_records,
)
from app.market_data.models import CapabilityState, ErrorCode, InstrumentType, MarketDataError, Timeframe
from app.market_data.providers import configured_market_data_provider
from app.market_data.models import HistoricalBarsRequest


T = datetime(2026, 8, 26, 10, tzinfo=UTC)


class FakeKotakTransport:
    def __init__(self, *responses: KotakNeoHttpResponse) -> None:
        self.responses = list(responses)
        self.requests: list[dict[str, object]] = []

    def request(self, *, method, url, headers, json_body, timeout_seconds):
        self.requests.append({"method": method, "url": url, "headers": dict(headers), "json_body": json_body, "timeout_seconds": timeout_seconds})
        if not self.responses:
            raise AssertionError("Unexpected Kotak transport request")
        return self.responses.pop(0)


def credentials(**changes) -> KotakNeoCredentials:
    values = {"tradeapi_access_token": "tradeapi-access-token", "mobile_number": "+919999999999", "ucc": "UCC123", "mpin": "123456"}
    values.update(changes)
    return KotakNeoCredentials(**values)


def master() -> KotakNeoInstrumentMaster:
    return KotakNeoInstrumentMaster((
        KotakNeoInstrumentRecord("nse_cm", "2885", "RELIANCE", "RELIANCE-EQ", "Equity", "INE002A01018", "EQ", "Reliance"),
        KotakNeoInstrumentRecord("bse_cm", "500325", "RELIANCE", "RELIANCE", "Equity", "INE002A01018", "A", "Reliance BSE"),
        KotakNeoInstrumentRecord("nse_cm", "Nifty 50", "NIFTY 50", "NIFTY 50", "Index"),
        KotakNeoInstrumentRecord("nse_cm", "INDIA VIX", "INDIA VIX", "INDIA VIX", "Index"),
    ))


def quote_row(token="2885", segment="nse_cm", *, ltp="1400.25", volume="1000", timestamp=None):
    return {
        "exchange_token": token, "exchange": segment, "lstup_time": str(int(T.timestamp())) if timestamp is None else timestamp,
        "ltp": ltp, "last_volume": volume, "change": "4.25", "per_change": "0.30",
        "ohlc": {"open": "1395", "high": "1410", "low": "1390", "close": "1396"},
        "depth": {"buy": [{"price": "1400", "quantity": "10"}], "sell": [{"price": "1400.50", "quantity": "20"}]},
    }


def provider(*responses, creds=None) -> tuple[KotakNeoMarketDataProvider, FakeKotakTransport]:
    transport = FakeKotakTransport(*responses)
    return KotakNeoMarketDataProvider(creds or credentials(), transport, instrument_master=master(), clock=lambda: T), transport


def test_registry_selects_kotak_and_construction_or_import_does_not_call_network() -> None:
    transport = FakeKotakTransport()
    selected = configured_market_data_provider("kotak_neo", kotak_credentials=credentials(), kotak_transport=transport)
    assert isinstance(selected, KotakNeoMarketDataProvider)
    assert transport.requests == []
    import app.market_data.kotak_neo as kotak
    assert "https://mis.kotaksecurities.com/login/1.0/tradeApiLogin" == KOTAK_NEO_LOGIN_URL
    source = inspect.getsource(kotak)
    assert "tradeApiLogin" in source
    assert "napi.kotaksecurities.com" not in source and "/oauth2/token" not in source


def test_missing_tradeapi_access_token_fails_on_operation_not_construction() -> None:
    value, transport = provider(creds=credentials(tradeapi_access_token=None))
    assert transport.requests == []
    with pytest.raises(MarketDataError) as caught:
        value.get_quote(master().resolve("NSE:RELIANCE-EQ"))
    assert caught.value.code is ErrorCode.AUTHENTICATION_REQUIRED
    assert transport.requests == []


def test_current_totp_mpin_auth_flow_uses_dynamic_base_url_and_redacts_secrets() -> None:
    value, transport = provider(
        KotakNeoHttpResponse(200, {"data": {"token": "view-token", "sid": "session-id"}}),
        KotakNeoHttpResponse(200, {"data": {"token": "trade-token", "sid": "session-id", "baseUrl": "https://dynamic.kotak.example"}}),
        KotakNeoHttpResponse(200, {"data": ["https://master.kotak.example/nse.csv"]}),
    )
    session = value.establish_session(current_totp="123456")
    assert session.base_url == "https://dynamic.kotak.example"
    assert value.master_file_paths() == ("https://master.kotak.example/nse.csv",)
    assert transport.requests[0]["url"] == KOTAK_NEO_LOGIN_URL
    assert transport.requests[0]["headers"] == {"Authorization": "tradeapi-access-token", "neo-fin-key": "neotradeapi", "Content-Type": "application/json"}
    assert transport.requests[0]["json_body"] == {"mobileNumber": "+919999999999", "ucc": "UCC123", "totp": "123456"}
    assert transport.requests[1]["url"] == KOTAK_NEO_VALIDATE_URL
    assert transport.requests[1]["headers"] == {"Authorization": "tradeapi-access-token", "neo-fin-key": "neotradeapi", "sid": "session-id", "Auth": "view-token", "Content-Type": "application/json"}
    assert transport.requests[2]["url"] == "https://mis.kotaksecurities.com/script-details/1.0/masterscrip/file-paths"
    exposed = repr(credentials()) + repr(session) + str(MarketDataError(ErrorCode.AUTHENTICATION_REQUIRED, "Kotak Neo authentication is required."))
    for secret in ("tradeapi-access-token", "9999999999", "123456", "trade-token", "view-token", "session-id"):
        assert secret not in exposed


def test_authentication_stage_failures_are_sanitized_without_returning_provider_payload() -> None:
    access, _ = provider(KotakNeoHttpResponse(401, {"message": "TradeAPI access token rejected: private-value"}))
    with pytest.raises(KotakNeoAuthenticationError) as access_error:
        access.establish_session(current_totp="123456")
    assert access_error.value.category == "ACCESS_TOKEN_REJECTED"
    assert "private-value" not in str(access_error.value)

    mpin, _ = provider(
        KotakNeoHttpResponse(200, {"data": {"token": "view-token", "sid": "session-id"}}),
        KotakNeoHttpResponse(401, {"message": "MPIN invalid: private-value"}),
    )
    with pytest.raises(KotakNeoAuthenticationError) as mpin_error:
        mpin.establish_session(current_totp="123456")
    assert mpin_error.value.category == "MPIN_VALIDATION_FAILED"
    assert "private-value" not in str(mpin_error.value)


def test_provider_reported_ip_restriction_is_classified_without_guessing_an_ip() -> None:
    denied, _ = provider(KotakNeoHttpResponse(403, {"message": "IP allowlist restriction: private-value"}))
    with pytest.raises(KotakNeoAuthenticationError) as caught:
        denied.establish_session(current_totp="123456")
    assert caught.value.category == "IP_NOT_ALLOWED"
    assert "private-value" not in str(caught.value)


def test_authenticated_nse_cash_master_loads_only_canonical_nse_equity_records() -> None:
    value, transport = provider(
        KotakNeoHttpResponse(200, {"data": ["https://files.kotaksecurities.com/nse_cm.csv"]}),
        KotakNeoHttpResponse(200, None, content=(
            b"pExchSeg,pSymbol,pSymbolName,pTrdSymbol,pISIN,pSeries,pInstType\n"
            b"nse_cm,2885,RELIANCE,RELIANCE-EQ,INE002A01018,EQ,Equity\n"
            b"bse_cm,500325,RELIANCE,RELIANCE,INE002A01018,A,Equity\n"
        )),
    )
    loaded = value.load_instrument_master()
    identity = loaded.resolve("RELIANCE")
    assert identity.instrument_id == "NSE:RELIANCE-EQ"
    assert len(loaded.identities) == 1
    assert transport.requests[0]["url"] == "https://mis.kotaksecurities.com/script-details/1.0/masterscrip/file-paths"
    assert transport.requests[-1]["url"] == "https://files.kotaksecurities.com/nse_cm.csv"


def test_transformed_v1_nse_master_csv_maps_required_identity_fields_without_fuzzy_matching() -> None:
    """Redacted fixture shaped like the live SDK's ``nse_cm-v1.csv`` export."""
    response = KotakNeoHttpResponse(
        200,
        None,
        content=(
            b"pSymbol,pGroup,pExchSeg,pInstType,pSymbolName,pTrdSymbol,pISIN,dTickSize ,iPermittedToTrade,CASEligible\n"
            b"12345,EQ,nse_cm,EQUITY,ALPHA,ALPHA-EQ,INE000A01001,0.05,1,Y\n"
        ),
    )
    records = _master_records(response)
    assert len(records) == 1
    record = records[0]
    identity = _identity(record)
    mapping = identity.provider_mappings[0]
    assert (record.exchange_segment, record.symbol, record.isin, record.instrument_token) == ("nse_cm", "ALPHA", "INE000A01001", "12345")
    assert (identity.exchange.value, identity.instrument_type.value, mapping.provider, mapping.provider_exchange_segment) == ("NSE", "NSE_EQUITY", "KOTAK_NEO", "nse_cm")
    assert mapping.provider_instrument_reference == "12345"


def test_official_sdk_quote_only_path_uses_consumer_key_scrip_master_and_one_quote() -> None:
    calls: list[tuple[str, object]] = []

    class FakeSdk:
        def scrip_master(self, *, exchange_segment=None):
            calls.append(("scrip_master", exchange_segment))
            return "https://files.kotaksecurities.com/nse_cm.csv"
        def quotes(self, *, instrument_tokens=None, quote_type=None):
            calls.append(("quotes", (instrument_tokens, quote_type)))
            return {"data": [quote_row()]}
        def totp_login(self, **kwargs): raise AssertionError("quote-only path must not log in")
        def totp_validate(self, **kwargs): raise AssertionError("quote-only path must not validate MPIN")

    initialized: list[dict[str, str]] = []
    def sdk_factory(**kwargs):
        initialized.append(kwargs)
        return FakeSdk()

    value, transport = provider(
        KotakNeoHttpResponse(200, None, content=(
            b"pExchSeg,pSymbol,pSymbolName,pTrdSymbol,pISIN,pSeries,pInstType\n"
            b"nse_cm,2885,RELIANCE,RELIANCE-EQ,INE002A01018,EQ,Equity\n"
        )),
    )
    value = KotakNeoMarketDataProvider(credentials(), transport=transport, clock=lambda: T, sdk_factory=sdk_factory)
    instrument = value.load_instrument_master().resolve("NSE:RELIANCE-EQ")
    quote = value.get_quote(instrument)
    assert initialized == [{"consumer_key": "tradeapi-access-token", "environment": "prod"}]
    assert calls == [
        ("scrip_master", "nse_cm"),
        ("quotes", ([{"exchange_segment": "nse_cm", "instrument_token": "2885"}], "all")),
    ]
    assert len(transport.requests) == 1 and transport.requests[0]["url"] == "https://files.kotaksecurities.com/nse_cm.csv"
    assert transport.requests[0]["headers"] == {}
    assert quote.last_price is not None


def test_official_sdk_direct_quote_list_shape_is_accepted_without_an_envelope() -> None:
    """The real 3.0.1 SDK returned a one-record list during bounded validation."""
    class FakeSdk:
        def quotes(self, *, instrument_tokens=None, quote_type=None):
            assert instrument_tokens == [{"exchange_segment": "nse_cm", "instrument_token": "2885"}]
            assert quote_type == "all"
            return [quote_row()]
        def scrip_master(self, **kwargs): raise AssertionError("not used")
        def totp_login(self, **kwargs): raise AssertionError("not used")
        def totp_validate(self, **kwargs): raise AssertionError("not used")

    value = KotakNeoMarketDataProvider(
        credentials(), transport=FakeKotakTransport(), instrument_master=master(), clock=lambda: T,
        sdk_factory=lambda **kwargs: FakeSdk(),
    )
    quote = value.get_quote(master().resolve("NSE:RELIANCE-EQ"))
    assert quote.last_price == Decimal("1400.25")
    assert quote.provenance.exchange_timestamp == T


def test_unparseable_optional_kotak_timestamp_keeps_quote_but_never_fabricates_observed_time() -> None:
    value, _ = provider(KotakNeoHttpResponse(200, {"data": [quote_row(timestamp="provider-format-not-supported")]}))
    quote = value.get_quote(master().resolve("NSE:RELIANCE-EQ"))
    assert quote.last_price == Decimal("1400.25")
    assert quote.provenance.provider_timestamp is None
    assert quote.provenance.exchange_timestamp is None
    assert quote.warnings == ("KOTAK_PROVIDER_TIMESTAMP_UNPARSEABLE",)


def test_non_positive_optional_kotak_depth_prices_are_unavailable_not_fabricated() -> None:
    row = quote_row(timestamp="provider-format-not-supported")
    row["depth"] = {
        "buy": [{"price": "0", "quantity": "0"}],
        "sell": [{"price": "0", "quantity": "0"}],
    }
    value, _ = provider(KotakNeoHttpResponse(200, {"data": [row]}))
    quote = value.get_quote(master().resolve("NSE:RELIANCE-EQ"))
    assert quote.last_price == Decimal("1400.25")
    assert quote.bid is None and quote.ask is None
    assert "KOTAK_PROVIDER_TIMESTAMP_UNPARSEABLE" in quote.warnings


def test_official_sdk_session_uses_current_totp_then_mpin_without_persisting_a_seed() -> None:
    calls: list[tuple[str, object]] = []
    class FakeSdk:
        def scrip_master(self, **kwargs): raise AssertionError("not used")
        def quotes(self, **kwargs): raise AssertionError("not used")
        def totp_login(self, *, mobile_number=None, ucc=None, totp=None):
            calls.append(("totp_login", (mobile_number, ucc, totp)))
            return {"data": {"token": "view-token", "sid": "sid"}}
        def totp_validate(self, *, mpin=None):
            calls.append(("totp_validate", mpin))
            return {"data": {"token": "session-token", "sid": "sid", "baseUrl": "https://dynamic.kotak.example"}}
    value = KotakNeoMarketDataProvider(credentials(), transport=FakeKotakTransport(), clock=lambda: T, sdk_factory=lambda **kwargs: FakeSdk())
    session = value.establish_session(current_totp="654321")
    assert calls == [("totp_login", ("+919999999999", "UCC123", "654321")), ("totp_validate", "123456")]
    assert session.base_url == "https://dynamic.kotak.example"


def test_exact_instrument_resolution_distinguishes_nse_bse_index_vix_and_ambiguity() -> None:
    catalog = master()
    nse = catalog.resolve("NSE:RELIANCE-EQ")
    bse = catalog.resolve("BSE:RELIANCE")
    assert nse.instrument_type is InstrumentType.NSE_EQUITY
    assert bse.instrument_type is InstrumentType.BSE_EQUITY and bse.instrument_id != nse.instrument_id
    assert catalog.resolve("NIFTY 50").instrument_type is InstrumentType.BROAD_INDEX
    assert catalog.resolve("INDIA VIX").instrument_type is InstrumentType.VOLATILITY_INDEX
    with pytest.raises(MarketDataError) as ambiguous:
        catalog.resolve("RELIANCE")
    assert ambiguous.value.code is ErrorCode.AMBIGUOUS_INSTRUMENT
    with pytest.raises(MarketDataError) as unknown:
        catalog.resolve("NOT-A-SCRIP")
    assert unknown.value.code is ErrorCode.INSTRUMENT_NOT_FOUND


def test_quote_batch_partial_normalization_decimal_timezone_provenance_and_freshness() -> None:
    value, transport = provider(KotakNeoHttpResponse(200, {"data": [quote_row(), quote_row("500325", "bse_cm", ltp="3000.10")]}))
    nse, bse, vix = master().resolve("NSE:RELIANCE-EQ"), master().resolve("BSE:RELIANCE"), master().resolve("INDIA VIX")
    result = value.get_quotes((nse, bse, vix))
    assert [item.instrument.instrument_id for item in result.quotes] == [nse.instrument_id, bse.instrument_id]
    assert result.quotes[0].last_price.as_tuple().exponent == -2
    assert result.quotes[0].provenance.provider == "KOTAK_NEO"
    assert result.quotes[0].provenance.provider_instrument_reference == "2885"
    assert result.quotes[0].provenance.exchange_timestamp == T
    assert result.quotes[0].freshness.state.value == "FRESH"
    assert result.failures[vix.instrument_id].code is ErrorCode.INSTRUMENT_NOT_FOUND
    assert "tradeapi-access-token" not in str(result.quotes[0].provenance)
    assert "/script-details/1.0/quotes/neosymbol/nse_cm|2885,bse_cm|500325,nse_cm|INDIA VIX/all" in str(transport.requests[0]["url"])


def test_index_vix_conversion_and_current_unsupported_historical_market_status_breadth_are_truthful() -> None:
    value, _ = provider(KotakNeoHttpResponse(200, {"data": [quote_row("INDIA VIX", "nse_cm", ltp="14.50")]}))
    vix = value.get_index_observation(master().resolve("INDIA VIX"))
    assert vix is not None and vix.value is not None
    assert value.capabilities().historical_candles is CapabilityState.UNSUPPORTED
    assert value.capabilities().websocket is CapabilityState.UNSUPPORTED
    with pytest.raises(MarketDataError, match="historical"):
        value.get_historical_bars(HistoricalBarsRequest(master().resolve("NSE:RELIANCE-EQ"), Timeframe.DAILY, T - timedelta(days=1), T))
    with pytest.raises(MarketDataError, match="breadth"):
        value.get_market_breadth("NIFTY500")
    with pytest.raises(MarketDataError, match="market status"):
        value.get_market_status("NSE")


@pytest.mark.parametrize(
    ("status", "expected", "retry"),
    ((401, ErrorCode.AUTHENTICATION_REQUIRED, False), (429, ErrorCode.RATE_LIMITED, True), (503, ErrorCode.PROVIDER_UNAVAILABLE, True)),
)
def test_http_error_mapping_is_sanitized(status, expected, retry) -> None:
    value, _ = provider(KotakNeoHttpResponse(status, {"error": [{"message": "consumer-secret should never leak"}]}))
    with pytest.raises(MarketDataError) as caught:
        value.get_quote(master().resolve("NSE:RELIANCE-EQ"))
    assert caught.value.code is expected
    assert (caught.value.retry.value == "RETRYABLE") is retry
    assert "consumer-secret" not in str(caught.value)


def test_malformed_or_corrupt_provider_data_fails_closed_without_repair() -> None:
    malformed, _ = provider(KotakNeoHttpResponse(200, {"data": {"unexpected": "object"}}))
    with pytest.raises(MarketDataError) as caught:
        malformed.get_quote(master().resolve("NSE:RELIANCE-EQ"))
    assert caught.value.code is ErrorCode.MALFORMED_RESPONSE
    corrupt, _ = provider(KotakNeoHttpResponse(200, {"data": [quote_row(ltp="-1", volume="-3")]}))
    with pytest.raises(MarketDataError) as quality:
        corrupt.get_quote(master().resolve("NSE:RELIANCE-EQ"))
    assert quality.value.code is ErrorCode.QUALITY_FAILURE


def test_timeout_mapping_is_retryable_and_does_not_chain_transport_details(monkeypatch) -> None:
    class TimeoutException(Exception):
        pass
    class Client:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): return None
        def request(self, *args, **kwargs): raise TimeoutException("consumer-secret")
    monkeypatch.setitem(sys.modules, "httpx", types.SimpleNamespace(Client=Client))
    with pytest.raises(MarketDataError) as caught:
        HttpxKotakNeoTransport().request(method="GET", url="https://example.invalid", headers={"Authorization": "consumer-secret"}, json_body=None, timeout_seconds=1)
    assert caught.value.code is ErrorCode.PROVIDER_UNAVAILABLE
    assert caught.value.retry.value == "RETRYABLE" and caught.value.__cause__ is None
    assert "consumer-secret" not in str(caught.value)


def test_kotak_canonical_quote_and_vix_supply_only_market_extreme_fact_inputs() -> None:
    value, _ = provider(KotakNeoHttpResponse(200, {"data": [quote_row()]}))
    quote = value.get_quote(master().resolve("NSE:RELIANCE-EQ"))
    assert quote.last_price is not None and quote.high is not None and quote.low is not None
    assert quote.volume == 1000 and quote.bid is not None and quote.ask is not None
    assert quote.provenance.exchange_timestamp is not None
    assert not hasattr(quote, "crisis_state") and not hasattr(quote, "euphoria_score")


def test_kotak_adapter_has_no_trading_websocket_or_fastapi_side_effect_path() -> None:
    import app.api.main as api_main
    import app.market_data.kotak_neo as kotak
    source = inspect.getsource(kotak).lower()
    assert not any(token in source for token in ("def place_order", "def modify_order", "def cancel_order", "quick/order", "def holdings", "def positions", "create_websocket", "subscribe_", "def auto_ingest"))
    assert "kotak" not in inspect.getsource(api_main).lower()
