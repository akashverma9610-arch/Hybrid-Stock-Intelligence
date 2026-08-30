"""Kotak Neo streaming boundary; live transport remains explicit opt-in and pending."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Mapping

from app.domain.models import DataQuality
from app.market_data.models import (
    CanonicalQuote,
    ErrorCode,
    FreshnessThresholds,
    InstrumentIdentity,
    MarketDataError,
    MarketDataProvenance,
    MarketSessionState,
    SessionAwareFreshnessEvaluator,
)
from app.market_data.normalization import MarketDataNormalizer
from app.market_data.streaming import StreamingSubscription


@dataclass(frozen=True, slots=True)
class KotakNeoStreamingSettings:
    """Real networking stays disabled until an explicitly approved provider contract exists."""

    live_streaming_enabled: bool = False


class KotakNeoStreamingQuoteAdapter:
    """Normalizes injected/mock Kotak quote payloads into existing canonical quotes."""

    def __init__(
        self,
        instruments: Mapping[str, InstrumentIdentity],
        *,
        normalizer: MarketDataNormalizer | None = None,
        freshness: SessionAwareFreshnessEvaluator | None = None,
    ) -> None:
        self._instruments = dict(instruments)
        self._normalizer = normalizer or MarketDataNormalizer()
        self._freshness = freshness or SessionAwareFreshnessEvaluator(
            FreshnessThresholds(
                quote=timedelta(seconds=15), intraday_bar=timedelta(minutes=5),
                daily_bar=timedelta(days=1), index=timedelta(seconds=15), breadth=timedelta(minutes=5),
            )
        )

    def normalize(self, payload: Mapping[str, Any], subscription: StreamingSubscription, received_at: datetime) -> CanonicalQuote:
        reference = payload.get("instrument_token", payload.get("token"))
        if reference != subscription.provider_instrument_reference:
            raise MarketDataError(ErrorCode.INSTRUMENT_NOT_FOUND, "Streaming payload does not match its subscription.")
        instrument = self._instruments.get(subscription.instrument_id)
        if instrument is None:
            raise MarketDataError(ErrorCode.INSTRUMENT_NOT_FOUND, "Streaming subscription instrument is unavailable.")
        timestamp = payload.get("exchange_timestamp", payload.get("timestamp"))
        if not isinstance(timestamp, datetime) or timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise MarketDataError(ErrorCode.MALFORMED_RESPONSE, "Streaming payload timestamp is malformed.")
        sequence = payload.get("sequence", payload.get("event_id"))
        if not isinstance(sequence, (str, int)) or isinstance(sequence, bool):
            raise MarketDataError(ErrorCode.MALFORMED_RESPONSE, "Streaming payload sequence is malformed.")
        raw = {
            "last_price": payload.get("last_price", payload.get("ltp")),
            "previous_close": payload.get("previous_close"),
            "open": payload.get("open"), "high": payload.get("high"), "low": payload.get("low"),
            "volume": payload.get("volume", payload.get("last_volume")),
            "bid": payload.get("bid"), "ask": payload.get("ask"),
        }
        provenance = MarketDataProvenance(
            "KOTAK_NEO", subscription.provider_instrument_reference, timestamp, timestamp, received_at,
            "kotak-neo-streaming-v1", "stream", "injected-kotak-stream-payload",
        )
        return self._normalizer.quote(
            raw,
            quote_id=f"kotak-stream:{subscription.provider_instrument_reference}:{sequence}",
            instrument=instrument,
            provenance=provenance,
            freshness=self._freshness.evaluate(observed_at=timestamp, evaluated_at=received_at, kind="quote", session_state=MarketSessionState.OPEN),
            quality=DataQuality.UNKNOWN,
        )


class KotakNeoLiveStreamingTransport:
    """Non-network placeholder: live WebSocket wiring is opt-in and intentionally pending."""

    def __init__(self, settings: KotakNeoStreamingSettings = KotakNeoStreamingSettings()) -> None:
        self._settings = settings

    def connect(self) -> None:
        if not self._settings.live_streaming_enabled:
            raise MarketDataError(ErrorCode.CONFIGURATION_ERROR, "Kotak Neo live streaming is disabled.")
        raise MarketDataError(ErrorCode.UNSUPPORTED_CAPABILITY, "Kotak Neo live streaming transport is pending explicit provider validation.")

    def close(self) -> None: pass
    def subscribe(self, subscription: StreamingSubscription) -> None: raise MarketDataError(ErrorCode.UNSUPPORTED_CAPABILITY, "Kotak Neo live streaming transport is pending explicit provider validation.")
    def unsubscribe(self, subscription: StreamingSubscription) -> None: raise MarketDataError(ErrorCode.UNSUPPORTED_CAPABILITY, "Kotak Neo live streaming transport is pending explicit provider validation.")
    def heartbeat(self) -> None: raise MarketDataError(ErrorCode.UNSUPPORTED_CAPABILITY, "Kotak Neo live streaming transport is pending explicit provider validation.")
