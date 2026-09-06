"""Explicit conversion from canonical facts to the existing domain observation boundary."""
from __future__ import annotations

from app.domain.models import Instrument, MarketObservation, ObservationKind, Provenance
from app.market_data.models import CanonicalOHLCVBar, IndexMarketObservation


def price_bar_observation(value: CanonicalOHLCVBar) -> MarketObservation:
    """Creates an unvalidated domain fact; FoundationService remains the validator."""
    from app.market_data.nse_udiff_source_identity import is_udiff
    if is_udiff(value):
        raise ValueError("NSE_UDIFF_TECHNICAL_SERIES_SELECTION_NOT_ACTIVE")
    return MarketObservation(
        id=value.bar_id,
        instrument=Instrument(value.instrument.instrument_id, value.instrument.symbol, value.instrument.exchange.value, value.instrument.isin),
        kind=ObservationKind.PRICE_BAR,
        payload={
            "open": float(value.open), "high": float(value.high), "low": float(value.low), "close": float(value.close),
            "volume": value.volume, "turnover": _number(value.turnover), "timeframe": value.timeframe.value,
            "adjustment_status": value.adjustment_status.value,
        },
        provenance=Provenance(
            source=value.provenance.provider,
            source_identifier=value.provenance.provider_instrument_reference,
            market_timestamp=value.provenance.exchange_timestamp or value.end_time,
            retrieved_timestamp=value.provenance.received_at,
            data_quality=value.quality,
            original_record={"canonical_bar_id": value.bar_id, "normalization_version": value.provenance.normalization_version},
        ),
    )


def index_observation(value: IndexMarketObservation) -> MarketObservation:
    return MarketObservation(
        id=value.observation_id,
        instrument=Instrument(value.instrument.instrument_id, value.instrument.symbol, value.instrument.exchange.value, value.instrument.isin),
        kind=ObservationKind.INDEX,
        payload={"value": _number(value.value), "previous_close": _number(value.previous_close), "open": _number(value.open), "high": _number(value.high), "low": _number(value.low)},
        provenance=Provenance(
            source=value.provenance.provider,
            source_identifier=value.provenance.provider_instrument_reference,
            market_timestamp=value.provenance.exchange_timestamp or value.observed_at,
            retrieved_timestamp=value.provenance.received_at,
            data_quality=value.quality,
            original_record={"canonical_index_observation_id": value.observation_id, "normalization_version": value.provenance.normalization_version},
        ),
    )


def _number(value: object) -> float | None:
    return float(value) if value is not None else None
