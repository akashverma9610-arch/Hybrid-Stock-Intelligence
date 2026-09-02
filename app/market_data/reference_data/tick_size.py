"""Immutable NSE cash tick-reference evidence; no source acquisition or resolver."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
import re

from app.historical.guard import manifest_fingerprint
from app.market_data.models import Exchange


class TickSizeSourceClass(StrEnum):
    OFFICIAL_EXCHANGE = "OFFICIAL_EXCHANGE"
    LICENSED_REFERENCE_DATA = "LICENSED_REFERENCE_DATA"


class TickSizeAvailabilitySemantics(StrEnum):
    EXPLICIT_EFFECTIVE_PERIOD = "EXPLICIT_EFFECTIVE_PERIOD"
    FIRST_OBSERVED_ONLY = "FIRST_OBSERVED_ONLY"


class TickSizeEvidenceKind(StrEnum):
    """Whether a tick value was directly supplied or derived from NSE policy."""

    DIRECT_SOURCE = "DIRECT_SOURCE"
    OFFICIAL_RULE_DERIVED = "OFFICIAL_RULE_DERIVED"


class TickSizeEvidenceSufficiency(StrEnum):
    SUFFICIENT = "SUFFICIENT"
    INSUFFICIENT = "INSUFFICIENT"


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
    evidence_kind: TickSizeEvidenceKind = TickSizeEvidenceKind.DIRECT_SOURCE,
    symbol: str | None = None,
    series: str | None = None,
    effective_month: str | None = None,
    reference_trading_session: datetime | None = None,
    reference_close: Decimal | None = None,
    rule_id: str | None = None,
    source_circular_reference: str | None = None,
    source_artifact_reference: str | None = None,
    derivation_details: tuple[str, ...] = (),
    evidence_sufficiency: TickSizeEvidenceSufficiency = TickSizeEvidenceSufficiency.SUFFICIENT,
) -> str:
    """Fingerprint every semantic input, excluding only its stored digest."""
    values = dict(
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
    # Keep legacy direct-source fingerprints stable. Rule-derived records add
    # their complete policy lineage to the immutable semantic identity.
    if evidence_kind is TickSizeEvidenceKind.OFFICIAL_RULE_DERIVED:
        values.update(
            evidence_kind=evidence_kind.value,
            symbol=symbol,
            series=series,
            effective_month=effective_month,
            reference_trading_session=reference_trading_session.isoformat() if reference_trading_session else None,
            reference_close=str(reference_close) if reference_close is not None else None,
            rule_id=rule_id,
            source_circular_reference=source_circular_reference,
            source_artifact_reference=source_artifact_reference,
            derivation_details=derivation_details,
            evidence_sufficiency=evidence_sufficiency.value,
        )
    return manifest_fingerprint(**values)


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
    evidence_kind: TickSizeEvidenceKind = TickSizeEvidenceKind.DIRECT_SOURCE
    symbol: str | None = None
    series: str | None = None
    effective_month: str | None = None
    reference_trading_session: datetime | None = None
    reference_close: Decimal | None = None
    rule_id: str | None = None
    source_circular_reference: str | None = None
    source_artifact_reference: str | None = None
    derivation_details: tuple[str, ...] = ()
    evidence_sufficiency: TickSizeEvidenceSufficiency = TickSizeEvidenceSufficiency.SUFFICIENT

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
        if not isinstance(self.evidence_kind, TickSizeEvidenceKind):
            raise ValueError("NSE_TICK_EVIDENCE_KIND_INVALID")
        if not isinstance(self.evidence_sufficiency, TickSizeEvidenceSufficiency):
            raise ValueError("NSE_TICK_EVIDENCE_SUFFICIENCY_INVALID")
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
        _rule_derived_fields_valid(self)
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
            evidence_kind=self.evidence_kind,
            symbol=self.symbol,
            series=self.series,
            effective_month=self.effective_month,
            reference_trading_session=self.reference_trading_session,
            reference_close=self.reference_close,
            rule_id=self.rule_id,
            source_circular_reference=self.source_circular_reference,
            source_artifact_reference=self.source_artifact_reference,
            derivation_details=self.derivation_details,
            evidence_sufficiency=self.evidence_sufficiency,
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


def _rule_derived_fields_valid(value: NseTickSizeObservation) -> None:
    fields = (
        value.symbol, value.series, value.effective_month, value.reference_trading_session,
        value.reference_close, value.rule_id, value.source_circular_reference,
        value.source_artifact_reference,
    )
    if value.evidence_kind is TickSizeEvidenceKind.DIRECT_SOURCE:
        if any(item is not None for item in fields) or value.derivation_details:
            raise ValueError("NSE_TICK_DIRECT_SOURCE_DERIVATION_FIELDS_FORBIDDEN")
        return
    if value.availability_semantics is not TickSizeAvailabilitySemantics.EXPLICIT_EFFECTIVE_PERIOD:
        raise ValueError("NSE_TICK_RULE_DERIVED_EFFECTIVE_PERIOD_REQUIRED")
    if value.source_class is not TickSizeSourceClass.OFFICIAL_EXCHANGE:
        raise ValueError("NSE_TICK_RULE_DERIVED_OFFICIAL_SOURCE_REQUIRED")
    if not all(isinstance(item, str) and item.strip() for item in (
        value.symbol, value.series, value.effective_month, value.rule_id,
        value.source_circular_reference, value.source_artifact_reference,
    )):
        raise ValueError("NSE_TICK_RULE_DERIVED_LINEAGE_REQUIRED")
    if not re.fullmatch(r"\d{4}-\d{2}", value.effective_month):
        raise ValueError("NSE_TICK_RULE_DERIVED_EFFECTIVE_MONTH_INVALID")
    _aware(value.reference_trading_session, "NSE_TICK_RULE_DERIVED_REFERENCE_SESSION_NAIVE")
    if not isinstance(value.reference_close, Decimal) or not value.reference_close.is_finite() or value.reference_close <= 0:
        raise ValueError("NSE_TICK_RULE_DERIVED_REFERENCE_CLOSE_INVALID")
    if not isinstance(value.derivation_details, tuple) or not value.derivation_details or any(
        not isinstance(item, str) or not item for item in value.derivation_details
    ):
        raise ValueError("NSE_TICK_RULE_DERIVED_DETAILS_REQUIRED")
