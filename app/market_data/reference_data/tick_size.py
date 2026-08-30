"""Immutable NSE cash tick-reference evidence; no source acquisition or resolver."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from app.historical.guard import manifest_fingerprint
from app.market_data.models import Exchange


class TickSizeSourceClass(StrEnum):
    OFFICIAL_EXCHANGE = "OFFICIAL_EXCHANGE"
    LICENSED_REFERENCE_DATA = "LICENSED_REFERENCE_DATA"


class TickSizeAvailabilitySemantics(StrEnum):
    EXPLICIT_EFFECTIVE_PERIOD = "EXPLICIT_EFFECTIVE_PERIOD"
    FIRST_OBSERVED_ONLY = "FIRST_OBSERVED_ONLY"


class NseTickSizeSegment(StrEnum):
    NSE_CASH_EQUITY = "NSE_CASH_EQUITY"


def _aware(value: datetime, code: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(code)


def _required(value: str, code: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(code)


def nse_tick_size_observation_fingerprint(
    *,
    record_id: str,
    canonical_instrument_id: str,
    exchange: Exchange,
    segment: NseTickSizeSegment,
    isin: str | None,
    tick_size: Decimal,
    source_class: TickSizeSourceClass,
    source_name: str,
    source_artifact_fingerprint: str,
    observed_at: datetime,
    effective_from: datetime | None,
    effective_to: datetime | None,
    availability_semantics: TickSizeAvailabilitySemantics,
    warnings: tuple[str, ...],
) -> str:
    """Fingerprint every semantic input, excluding only its stored digest."""
    return manifest_fingerprint(
        record_id=record_id,
        canonical_instrument_id=canonical_instrument_id,
        exchange=exchange.value,
        segment=segment.value,
        isin=isin,
        tick_size=str(tick_size),
        source_class=source_class.value,
        source_name=source_name,
        source_artifact_fingerprint=source_artifact_fingerprint,
        observed_at=observed_at.isoformat(),
        effective_from=effective_from.isoformat() if effective_from else None,
        effective_to=effective_to.isoformat() if effective_to else None,
        availability_semantics=availability_semantics.value,
        warnings=warnings,
    )


@dataclass(frozen=True, slots=True)
class NseTickSizeObservation:
    """A single immutable, exact-identity NSE cash tick reference observation.

    ``tick_size`` is already-decoded INR ``Decimal`` evidence. Raw master-file
    decoding intentionally belongs to a later source-ingestion boundary.
    """

    record_id: str
    canonical_instrument_id: str
    exchange: Exchange
    segment: NseTickSizeSegment
    isin: str | None
    tick_size: Decimal
    source_class: TickSizeSourceClass
    source_name: str
    source_artifact_fingerprint: str
    observed_at: datetime
    effective_from: datetime | None
    effective_to: datetime | None
    availability_semantics: TickSizeAvailabilitySemantics
    warnings: tuple[str, ...] = ()
    evidence_fingerprint: str = ""

    def __post_init__(self) -> None:
        _required(self.record_id, "NSE_TICK_RECORD_ID_REQUIRED")
        _required(self.canonical_instrument_id, "NSE_TICK_CANONICAL_INSTRUMENT_REQUIRED")
        _required(self.source_name, "NSE_TICK_SOURCE_NAME_REQUIRED")
        _required(self.source_artifact_fingerprint, "NSE_TICK_ARTIFACT_FINGERPRINT_REQUIRED")
        if self.exchange is not Exchange.NSE:
            raise ValueError("NSE_TICK_EXCHANGE_INVALID")
        if self.segment is not NseTickSizeSegment.NSE_CASH_EQUITY:
            raise ValueError("NSE_TICK_SEGMENT_INVALID")
        if not isinstance(self.source_class, TickSizeSourceClass):
            raise ValueError("NSE_TICK_SOURCE_CLASS_INVALID")
        if not isinstance(self.availability_semantics, TickSizeAvailabilitySemantics):
            raise ValueError("NSE_TICK_AVAILABILITY_SEMANTICS_INVALID")
        if self.isin is not None and (not isinstance(self.isin, str) or not self.isin.strip()):
            raise ValueError("NSE_TICK_ISIN_INVALID")
        if not isinstance(self.tick_size, Decimal):
            raise ValueError("NSE_TICK_DECIMAL_REQUIRED")
        if not self.tick_size.is_finite() or self.tick_size <= Decimal("0"):
            raise ValueError("NSE_TICK_VALUE_INVALID")
        _aware(self.observed_at, "NSE_TICK_OBSERVED_AT_NAIVE")
        if self.effective_from is not None:
            _aware(self.effective_from, "NSE_TICK_EFFECTIVE_FROM_NAIVE")
        if self.effective_to is not None:
            _aware(self.effective_to, "NSE_TICK_EFFECTIVE_TO_NAIVE")
        if self.availability_semantics is TickSizeAvailabilitySemantics.EXPLICIT_EFFECTIVE_PERIOD and self.effective_from is None:
            raise ValueError("NSE_TICK_EXPLICIT_EFFECTIVE_FROM_REQUIRED")
        if self.availability_semantics is TickSizeAvailabilitySemantics.FIRST_OBSERVED_ONLY and (self.effective_from is not None or self.effective_to is not None):
            raise ValueError("NSE_TICK_FIRST_OBSERVED_EFFECTIVITY_FORBIDDEN")
        if self.effective_from is not None and self.effective_to is not None and self.effective_to <= self.effective_from:
            raise ValueError("NSE_TICK_EFFECTIVE_INTERVAL_INVALID")
        if not isinstance(self.warnings, tuple) or any(not isinstance(item, str) or not item for item in self.warnings):
            raise ValueError("NSE_TICK_WARNINGS_INVALID")
        expected = nse_tick_size_observation_fingerprint(
            record_id=self.record_id,
            canonical_instrument_id=self.canonical_instrument_id,
            exchange=self.exchange,
            segment=self.segment,
            isin=self.isin,
            tick_size=self.tick_size,
            source_class=self.source_class,
            source_name=self.source_name,
            source_artifact_fingerprint=self.source_artifact_fingerprint,
            observed_at=self.observed_at,
            effective_from=self.effective_from,
            effective_to=self.effective_to,
            availability_semantics=self.availability_semantics,
            warnings=self.warnings,
        )
        if not self.evidence_fingerprint:
            object.__setattr__(self, "evidence_fingerprint", expected)
        elif self.evidence_fingerprint != expected:
            raise ValueError("NSE_TICK_EVIDENCE_FINGERPRINT_MISMATCH")

    @property
    def eligible_from(self) -> datetime:
        return max(self.observed_at, self.effective_from) if self.effective_from else self.observed_at

    def is_eligible_as_of(self, as_of: datetime) -> bool:
        _aware(as_of, "NSE_TICK_AS_OF_NAIVE")
        return as_of >= self.eligible_from and (self.effective_to is None or as_of < self.effective_to)
