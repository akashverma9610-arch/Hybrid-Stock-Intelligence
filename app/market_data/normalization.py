"""Raw-provider mapping to canonical facts; no analytical interpretation."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from app.domain.models import DataQuality
from app.market_data.models import (
    AdjustmentStatus,
    CanonicalOHLCVBar,
    CanonicalQuote,
    ErrorCode,
    FreshnessAssessment,
    InstrumentIdentity,
    MarketDataError,
    MarketDataProvenance,
    Timeframe,
)


class MarketDataNormalizer:
    """Converts supplied provider fields without filling missing data or guessing."""

    def quote(
        self,
        raw: Mapping[str, Any],
        *,
        quote_id: str,
        instrument: InstrumentIdentity,
        provenance: MarketDataProvenance,
        freshness: FreshnessAssessment,
        quality: DataQuality = DataQuality.UNKNOWN,
    ) -> CanonicalQuote:
        return CanonicalQuote(
            quote_id=quote_id, instrument=instrument,
            last_price=_decimal(raw.get("last_price")), previous_close=_decimal(raw.get("previous_close")),
            open=_decimal(raw.get("open")), high=_decimal(raw.get("high")), low=_decimal(raw.get("low")),
            volume=_integer(raw.get("volume")), turnover=_decimal(raw.get("turnover")),
            change=_decimal(raw.get("change")), change_percent=_decimal(raw.get("change_percent")),
            bid=_decimal(raw.get("bid")), ask=_decimal(raw.get("ask")),
            bid_quantity=_integer(raw.get("bid_quantity")), ask_quantity=_integer(raw.get("ask_quantity")),
            provenance=provenance, freshness=freshness, quality=quality,
            warnings=tuple(str(item) for item in raw.get("warnings", ())),
        )

    def bar(
        self,
        raw: Mapping[str, Any],
        *,
        bar_id: str,
        instrument: InstrumentIdentity,
        timeframe: Timeframe,
        provenance: MarketDataProvenance,
        quality: DataQuality = DataQuality.UNKNOWN,
    ) -> CanonicalOHLCVBar:
        return CanonicalOHLCVBar(
            bar_id=bar_id, instrument=instrument, timeframe=timeframe,
            start_time=_timestamp(raw.get("start_time"), "start_time"), end_time=_timestamp(raw.get("end_time"), "end_time"),
            open=_required_decimal(raw.get("open"), "open"), high=_required_decimal(raw.get("high"), "high"),
            low=_required_decimal(raw.get("low"), "low"), close=_required_decimal(raw.get("close"), "close"),
            volume=_integer(raw.get("volume")), turnover=_decimal(raw.get("turnover")),
            trade_count=_integer(raw.get("trade_count")),
            adjustment_status=AdjustmentStatus(raw.get("adjustment_status", AdjustmentStatus.UNKNOWN)),
            provenance=provenance, quality=quality,
            warnings=tuple(str(item) for item in raw.get("warnings", ())),
        )


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise MarketDataError(ErrorCode.MALFORMED_RESPONSE, "Provider returned a malformed numeric value.")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise MarketDataError(ErrorCode.MALFORMED_RESPONSE, "Provider returned a malformed numeric value.") from error


def _required_decimal(value: Any, name: str) -> Decimal:
    result = _decimal(value)
    if result is None:
        raise MarketDataError(ErrorCode.MALFORMED_RESPONSE, f"Provider response omitted required {name}.")
    return result


def _integer(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise MarketDataError(ErrorCode.MALFORMED_RESPONSE, "Provider returned a malformed integer value.")
    return value


def _timestamp(value: Any, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise MarketDataError(ErrorCode.MALFORMED_RESPONSE, f"Provider response omitted timezone-aware {name}.")
    return value
