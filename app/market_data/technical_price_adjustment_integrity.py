"""Pure, PIT-safe technical price-adjustment integrity.

Raw provider OHLCV is an immutable input.  This module can only produce an
in-memory, versioned split/bonus derivative where the existing official NSE
corporate-action receipt proves the exact factor semantics.  It deliberately
does not persist, select a provider, alter a source bar, calculate an
indicator, or infer a corporate action from a price move.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from hashlib import sha256
import json
import re

from app.historical.security_master import (
    CorporateActionKind, HistoricalCorporateAction, PriceAdjustmentBasis,
)
from app.market_data.models import AdjustmentStatus, CanonicalOHLCVBar, InstrumentType


CONTRACT_ID = "canonical-technical-price-adjustment-and-corporate-action-integrity"
CONTRACT_VERSION = "v1"
POLICY_ID = "technical-price-adjustment"
POLICY_VERSION = "v1"
_ID = re.compile(r"[A-Za-z0-9._:-]+\Z")
_FP = re.compile(r"sha256:[0-9a-f]{64}\Z")
_SPLIT_FACE_VALUE = re.compile(
    r"\bFROM\s+RS\.?\s*(\d+(?:\.\d+)?)\s*/?-?\s*PER\s+SHARE\s+TO\s+RS\.?\s*(\d+(?:\.\d+)?)\s*/?-?\s*PER\s+SHARE\b",
    re.IGNORECASE,
)
_BONUS_RATIO = re.compile(r"\bBONUS\s+(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)\b", re.IGNORECASE)


class TechnicalPriceAdjustmentError(ValueError):
    """Stable fail-closed error for malformed adjustment-contract input."""


class AdjustmentReadiness(StrEnum):
    READY = "READY"
    PARTIAL = "PARTIAL"
    NOT_READY = "NOT_READY"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class PriceContinuityState(StrEnum):
    CONTINUOUS = "CONTINUOUS"
    NON_COMPARABLE = "NON_COMPARABLE"
    UNRESOLVED = "UNRESOLVED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class VolumeAdjustmentState(StrEnum):
    READY = "READY"
    NOT_READY = "NOT_READY"
    NOT_REQUIRED = "NOT_REQUIRED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class TechnicalCorporateActionClass(StrEnum):
    STOCK_SPLIT = "STOCK_SPLIT"
    BONUS = "BONUS"
    RIGHTS = "RIGHTS"
    CASH_DIVIDEND = "CASH_DIVIDEND"
    MERGER_DEMERGER_SPINOFF = "MERGER_DEMERGER_SPINOFF"
    SECURITY_CONTINUITY = "SECURITY_CONTINUITY"
    CAPITAL_REDUCTION_OR_FACE_VALUE_CHANGE = "CAPITAL_REDUCTION_OR_FACE_VALUE_CHANGE"
    OTHER_UNKNOWN = "OTHER_UNKNOWN"


class TechnicalAdjustmentReason(StrEnum):
    RAW_BARS_IMMUTABLE = "RAW_BARS_IMMUTABLE"
    MIXED_OR_UNKNOWN_SOURCE_BASIS = "MIXED_OR_UNKNOWN_SOURCE_BASIS"
    PROVIDER_ADJUSTMENT_BASIS_UNKNOWN = "PROVIDER_ADJUSTMENT_BASIS_UNKNOWN"
    YFINANCE_SECONDARY_RESEARCH_ONLY = "YFINANCE_SECONDARY_RESEARCH_ONLY"
    INDEX_BASIS_SOURCE_SPECIFIC = "INDEX_BASIS_SOURCE_SPECIFIC"
    ACTION_NOT_KNOWN_AS_OF = "ACTION_NOT_KNOWN_AS_OF"
    ACTION_EFFECTIVE_AFTER_AS_OF = "ACTION_EFFECTIVE_AFTER_AS_OF"
    EXACT_INSTRUMENT_MISMATCH = "EXACT_INSTRUMENT_MISMATCH"
    DUPLICATE_ACTION_ID = "DUPLICATE_ACTION_ID"
    AMBIGUOUS_ACTION_EFFECTIVE_BOUNDARY = "AMBIGUOUS_ACTION_EFFECTIVE_BOUNDARY"
    SPLIT_RATIO_SEMANTICS_UNVERIFIED = "SPLIT_RATIO_SEMANTICS_UNVERIFIED"
    BONUS_RATIO_SEMANTICS_UNVERIFIED = "BONUS_RATIO_SEMANTICS_UNVERIFIED"
    RIGHTS_ADJUSTMENT_NOT_READY = "RIGHTS_ADJUSTMENT_NOT_READY"
    DIVIDEND_PRICE_POLICY_NOT_APPROVED = "DIVIDEND_PRICE_POLICY_NOT_APPROVED"
    COMPLEX_ACTION_NON_COMPARABLE = "COMPLEX_ACTION_NON_COMPARABLE"
    SECURITY_CONTINUITY_NON_COMPARABLE = "SECURITY_CONTINUITY_NON_COMPARABLE"
    OTHER_ACTION_NON_COMPARABLE = "OTHER_ACTION_NON_COMPARABLE"
    TARGET_BASIS_POLICY_UNAVAILABLE = "TARGET_BASIS_POLICY_UNAVAILABLE"
    ACTION_WINDOW_NON_COMPARABLE = "ACTION_WINDOW_NON_COMPARABLE"
    VOLUME_NOT_PRESENT = "VOLUME_NOT_PRESENT"


class ProviderPriceBasisState(StrEnum):
    RAW = "RAW"
    UNKNOWN = "UNKNOWN"
    PROVIDER_ADJUSTED_UNKNOWN_METHOD = "PROVIDER_ADJUSTED_UNKNOWN_METHOD"
    INDEX_SOURCE_SPECIFIC = "INDEX_SOURCE_SPECIFIC"


@dataclass(frozen=True, slots=True)
class ProviderPriceBasisAssessment:
    provider: str
    normalization_version: str
    instrument_type: InstrumentType
    provider_basis: ProviderPriceBasisState
    hsi_stored_basis: AdjustmentStatus
    raw_recoverable: bool
    transformation_documented: bool
    canonical_technical_allowed: bool
    reasons: tuple[TechnicalAdjustmentReason, ...]
    fingerprint: str

    def __post_init__(self) -> None:
        reasons = _reasons(self.reasons)
        expected = _fingerprint(_basis_payload(self, reasons))
        if (
            not _ID.fullmatch(self.provider)
            or not _ID.fullmatch(self.normalization_version)
            or not isinstance(self.instrument_type, InstrumentType)
            or not isinstance(self.provider_basis, ProviderPriceBasisState)
            or not isinstance(self.hsi_stored_basis, AdjustmentStatus)
            or self.reasons != reasons
            or self.fingerprint != expected
        ):
            raise TechnicalPriceAdjustmentError("PROVIDER_PRICE_BASIS_ASSESSMENT_INVALID")


@dataclass(frozen=True, slots=True)
class TechnicalActionReceipt:
    action_id: str
    canonical_instrument_id: str
    action_class: TechnicalCorporateActionClass
    effective_at: datetime
    source_known_at: datetime
    source_fingerprint: str
    price_factor: Decimal | None
    volume_factor: Decimal | None
    reasons: tuple[TechnicalAdjustmentReason, ...]
    fingerprint: str

    def __post_init__(self) -> None:
        reasons = _reasons(self.reasons)
        expected = _fingerprint(_action_payload(self, reasons))
        if (
            not _ID.fullmatch(self.action_id)
            or not _ID.fullmatch(self.canonical_instrument_id)
            or not _aware(self.effective_at) or not _aware(self.source_known_at)
            or not _FP.fullmatch(self.source_fingerprint)
            or not _positive_or_none(self.price_factor) or not _positive_or_none(self.volume_factor)
            or (self.price_factor is None) != (self.volume_factor is None)
            or self.reasons != reasons or self.fingerprint != expected
        ):
            raise TechnicalPriceAdjustmentError("TECHNICAL_ACTION_RECEIPT_INVALID")


@dataclass(frozen=True, slots=True)
class DerivedTechnicalOHLCVBar:
    """A non-persisted adjusted value with complete raw/action lineage."""

    derived_bar_id: str
    raw_bar_id: str
    raw_bar_fingerprint: str
    start_time: datetime
    end_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal | None
    price_factor: Decimal
    volume_factor: Decimal
    action_ids: tuple[str, ...]
    adjustment_basis: PriceAdjustmentBasis
    as_of: datetime
    fingerprint: str

    def __post_init__(self) -> None:
        action_ids = tuple(sorted(self.action_ids))
        expected = _fingerprint(_derived_payload(self, action_ids))
        if (
            not _ID.fullmatch(self.derived_bar_id) or not _ID.fullmatch(self.raw_bar_id)
            or not _FP.fullmatch(self.raw_bar_fingerprint) or not _aware(self.start_time)
            or not _aware(self.end_time) or not _aware(self.as_of)
            or self.end_time < self.start_time or not all(_positive(value) for value in (self.open, self.high, self.low, self.close, self.price_factor, self.volume_factor))
            or (self.volume is not None and (not isinstance(self.volume, Decimal) or self.volume < 0))
            or self.action_ids != action_ids or len(set(action_ids)) != len(action_ids)
            or self.adjustment_basis is not PriceAdjustmentBasis.SPLIT_BONUS_ADJUSTED
            or self.fingerprint != expected
        ):
            raise TechnicalPriceAdjustmentError("DERIVED_TECHNICAL_BAR_INVALID")


@dataclass(frozen=True, slots=True)
class TechnicalPriceAdjustmentResult:
    assessment_id: str
    canonical_instrument_id: str
    as_of: datetime
    target_basis: PriceAdjustmentBasis
    price_readiness: AdjustmentReadiness
    continuity: PriceContinuityState
    volume_readiness: VolumeAdjustmentState
    raw_bar_ids: tuple[str, ...]
    raw_bar_fingerprints: tuple[str, ...]
    action_receipts: tuple[TechnicalActionReceipt, ...]
    derived_bars: tuple[DerivedTechnicalOHLCVBar, ...]
    reasons: tuple[TechnicalAdjustmentReason, ...]
    policy_id: str
    policy_version: str
    fingerprint: str

    def __post_init__(self) -> None:
        bars = tuple(sorted(zip(self.raw_bar_ids, self.raw_bar_fingerprints)))
        actions = tuple(sorted(self.action_receipts, key=lambda item: item.action_id))
        derived = tuple(sorted(self.derived_bars, key=lambda item: item.derived_bar_id))
        reasons = _reasons(self.reasons)
        expected = _fingerprint(_result_payload(self, bars, actions, derived, reasons))
        if (
            not _ID.fullmatch(self.assessment_id) or not _ID.fullmatch(self.canonical_instrument_id)
            or not _aware(self.as_of) or not isinstance(self.target_basis, PriceAdjustmentBasis)
            or not isinstance(self.price_readiness, AdjustmentReadiness)
            or not isinstance(self.continuity, PriceContinuityState)
            or not isinstance(self.volume_readiness, VolumeAdjustmentState)
            or not _ID.fullmatch(self.policy_id) or not _ID.fullmatch(self.policy_version)
            or tuple(zip(self.raw_bar_ids, self.raw_bar_fingerprints)) != bars
            or any(not _ID.fullmatch(bar_id) or not _FP.fullmatch(fingerprint) for bar_id, fingerprint in bars)
            or self.action_receipts != actions or len({item.action_id for item in actions}) != len(actions)
            or self.derived_bars != derived or len({item.raw_bar_id for item in derived}) != len(derived)
            or any(item.as_of != _utc(self.as_of) for item in derived)
            or self.reasons != reasons or self.fingerprint != expected
            or (self.price_readiness is AdjustmentReadiness.READY and self.continuity is not PriceContinuityState.CONTINUOUS)
            or (self.target_basis is PriceAdjustmentBasis.SPLIT_BONUS_ADJUSTED and self.price_readiness is AdjustmentReadiness.READY and len(derived) != len(bars))
            or (self.target_basis is not PriceAdjustmentBasis.SPLIT_BONUS_ADJUSTED and derived)
        ):
            raise TechnicalPriceAdjustmentError("TECHNICAL_PRICE_ADJUSTMENT_RESULT_INVALID")


def audit_provider_price_basis(bar: CanonicalOHLCVBar) -> ProviderPriceBasisAssessment:
    """State only what the retained adapter/documentation actually establishes."""
    provider = bar.provenance.provider
    version = bar.provenance.normalization_version
    index = bar.instrument.instrument_type in {InstrumentType.BROAD_INDEX, InstrumentType.SECTOR_INDEX, InstrumentType.VOLATILITY_INDEX}
    reasons: list[TechnicalAdjustmentReason] = []
    if index:
        state = ProviderPriceBasisState.INDEX_SOURCE_SPECIFIC
        allowed = False
        reasons.append(TechnicalAdjustmentReason.INDEX_BASIS_SOURCE_SPECIFIC)
    elif provider == "yfinance" and version == "yfinance-history-v1" and bar.adjustment_status is AdjustmentStatus.RAW:
        state = ProviderPriceBasisState.RAW
        allowed = False
        reasons.append(TechnicalAdjustmentReason.YFINANCE_SECONDARY_RESEARCH_ONLY)
    elif bar.adjustment_status is AdjustmentStatus.UNKNOWN:
        state = ProviderPriceBasisState.UNKNOWN
        allowed = False
        reasons.append(TechnicalAdjustmentReason.PROVIDER_ADJUSTMENT_BASIS_UNKNOWN)
    elif bar.adjustment_status is AdjustmentStatus.ADJUSTED:
        state = ProviderPriceBasisState.PROVIDER_ADJUSTED_UNKNOWN_METHOD
        allowed = False
        reasons.append(TechnicalAdjustmentReason.PROVIDER_ADJUSTMENT_BASIS_UNKNOWN)
    else:
        state = ProviderPriceBasisState.RAW
        allowed = True
    values = dict(provider=provider, normalization_version=version, instrument_type=bar.instrument.instrument_type, provider_basis=state, hsi_stored_basis=bar.adjustment_status, raw_recoverable=True, transformation_documented=False, canonical_technical_allowed=allowed, reasons=_reasons(reasons))
    return ProviderPriceBasisAssessment(**values, fingerprint=_fingerprint(_basis_payload_values(values)))


def derive_technical_price_adjustment(
    *, canonical_instrument_id: str, raw_bars: tuple[CanonicalOHLCVBar, ...],
    actions: tuple[HistoricalCorporateAction, ...], as_of: datetime,
    target_basis: PriceAdjustmentBasis = PriceAdjustmentBasis.SPLIT_BONUS_ADJUSTED,
) -> TechnicalPriceAdjustmentResult:
    """Return a deterministic as-of version; never write or alter source bars."""
    if not _ID.fullmatch(canonical_instrument_id) or not _aware(as_of) or not raw_bars:
        raise TechnicalPriceAdjustmentError("TECHNICAL_PRICE_ADJUSTMENT_INPUT_INVALID")
    at = _utc(as_of)
    bars = tuple(sorted(raw_bars, key=lambda bar: (bar.start_time, bar.end_time, bar.bar_id)))
    if len({bar.bar_id for bar in bars}) != len(bars) or any(bar.instrument.instrument_id != canonical_instrument_id for bar in bars):
        raise TechnicalPriceAdjustmentError("TECHNICAL_PRICE_ADJUSTMENT_BAR_IDENTITY_INVALID")
    raw_ids = tuple(bar.bar_id for bar in bars)
    raw_fingerprints = tuple(_raw_bar_fingerprint(bar) for bar in bars)
    reasons: list[TechnicalAdjustmentReason] = [TechnicalAdjustmentReason.RAW_BARS_IMMUTABLE]
    if bars[0].instrument.instrument_type in {InstrumentType.BROAD_INDEX, InstrumentType.SECTOR_INDEX, InstrumentType.VOLATILITY_INDEX}:
        reasons.append(TechnicalAdjustmentReason.INDEX_BASIS_SOURCE_SPECIFIC)
        return _result(canonical_instrument_id, at, target_basis, AdjustmentReadiness.NOT_APPLICABLE, PriceContinuityState.NOT_APPLICABLE, VolumeAdjustmentState.NOT_APPLICABLE, raw_ids, raw_fingerprints, (), (), reasons)
    basis_audits = tuple(audit_provider_price_basis(bar) for bar in bars)
    if any(not item.canonical_technical_allowed for item in basis_audits):
        reasons.extend(reason for item in basis_audits for reason in item.reasons)
        if {bar.adjustment_status for bar in bars} != {AdjustmentStatus.RAW}:
            reasons.append(TechnicalAdjustmentReason.MIXED_OR_UNKNOWN_SOURCE_BASIS)
        return _result(canonical_instrument_id, at, target_basis, AdjustmentReadiness.NOT_READY, PriceContinuityState.UNRESOLVED, VolumeAdjustmentState.NOT_READY, raw_ids, raw_fingerprints, (), (), reasons)
    states = {bar.adjustment_status for bar in bars}
    if states != {AdjustmentStatus.RAW}:
        reasons.append(TechnicalAdjustmentReason.MIXED_OR_UNKNOWN_SOURCE_BASIS)
        return _result(canonical_instrument_id, at, target_basis, AdjustmentReadiness.NOT_READY, PriceContinuityState.UNRESOLVED, VolumeAdjustmentState.NOT_READY, raw_ids, raw_fingerprints, (), (), reasons)
    action_result = _eligible_actions(canonical_instrument_id, actions, at)
    reasons.extend(action_result[1])
    receipts = action_result[0]
    reasons.extend(reason for receipt in receipts for reason in receipt.reasons)
    if any(reason in {
        TechnicalAdjustmentReason.DUPLICATE_ACTION_ID,
        TechnicalAdjustmentReason.AMBIGUOUS_ACTION_EFFECTIVE_BOUNDARY,
    } for reason in action_result[1]):
        return _result(canonical_instrument_id, at, target_basis, AdjustmentReadiness.NOT_READY, PriceContinuityState.NON_COMPARABLE, VolumeAdjustmentState.NOT_READY, raw_ids, raw_fingerprints, receipts, (), reasons)
    crossing = tuple(item for item in receipts if any(_utc(bar.end_time) < item.effective_at for bar in bars))
    if target_basis is PriceAdjustmentBasis.RAW:
        if crossing:
            reasons.append(TechnicalAdjustmentReason.ACTION_WINDOW_NON_COMPARABLE)
        continuity = PriceContinuityState.NON_COMPARABLE if crossing else PriceContinuityState.CONTINUOUS
        volume = VolumeAdjustmentState.NOT_REQUIRED if not crossing else VolumeAdjustmentState.NOT_READY
        return _result(canonical_instrument_id, at, target_basis, AdjustmentReadiness.PARTIAL if crossing else AdjustmentReadiness.READY, continuity, volume, raw_ids, raw_fingerprints, receipts, (), reasons)
    if target_basis is not PriceAdjustmentBasis.SPLIT_BONUS_ADJUSTED:
        reasons.append(TechnicalAdjustmentReason.TARGET_BASIS_POLICY_UNAVAILABLE)
        return _result(canonical_instrument_id, at, target_basis, AdjustmentReadiness.NOT_READY, PriceContinuityState.UNRESOLVED, VolumeAdjustmentState.NOT_READY, raw_ids, raw_fingerprints, receipts, (), reasons)
    blocked = tuple(item for item in crossing if item.price_factor is None)
    if blocked:
        reasons.append(TechnicalAdjustmentReason.ACTION_WINDOW_NON_COMPARABLE)
        return _result(canonical_instrument_id, at, target_basis, AdjustmentReadiness.NOT_READY, PriceContinuityState.NON_COMPARABLE, VolumeAdjustmentState.NOT_READY, raw_ids, raw_fingerprints, receipts, (), reasons)
    derived: list[DerivedTechnicalOHLCVBar] = []
    for bar, raw_fp in zip(bars, raw_fingerprints, strict=True):
        applied = tuple(item for item in crossing if _utc(bar.end_time) < item.effective_at)
        price = _product(item.price_factor for item in applied)
        volume = _product(item.volume_factor for item in applied)
        actual_volume = None if bar.volume is None else Decimal(bar.volume) * volume
        values = dict(derived_bar_id=_derived_id(bar.bar_id, at, tuple(item.action_id for item in applied)), raw_bar_id=bar.bar_id, raw_bar_fingerprint=raw_fp, start_time=_utc(bar.start_time), end_time=_utc(bar.end_time), open=bar.open * price, high=bar.high * price, low=bar.low * price, close=bar.close * price, volume=actual_volume, price_factor=price, volume_factor=volume, action_ids=tuple(item.action_id for item in applied), adjustment_basis=PriceAdjustmentBasis.SPLIT_BONUS_ADJUSTED, as_of=at)
        derived.append(DerivedTechnicalOHLCVBar(**values, fingerprint=_fingerprint(_derived_payload_values(values))))
    volume_state = VolumeAdjustmentState.READY if all(bar.volume is not None for bar in bars) else VolumeAdjustmentState.NOT_READY
    if volume_state is VolumeAdjustmentState.NOT_READY:
        reasons.append(TechnicalAdjustmentReason.VOLUME_NOT_PRESENT)
    return _result(canonical_instrument_id, at, target_basis, AdjustmentReadiness.READY, PriceContinuityState.CONTINUOUS, volume_state, raw_ids, raw_fingerprints, receipts, tuple(derived), reasons)


def serialize_technical_price_adjustment(value: TechnicalPriceAdjustmentResult) -> str:
    value.__post_init__()
    return _canonical(_result_payload(value, tuple(zip(value.raw_bar_ids, value.raw_bar_fingerprints)), value.action_receipts, value.derived_bars, value.reasons) | {"fingerprint": value.fingerprint})


def _eligible_actions(instrument_id: str, actions: tuple[HistoricalCorporateAction, ...], at: datetime) -> tuple[tuple[TechnicalActionReceipt, ...], tuple[TechnicalAdjustmentReason, ...]]:
    reasons: list[TechnicalAdjustmentReason] = []
    seen: set[str] = set()
    candidates: list[HistoricalCorporateAction] = []
    for action in actions:
        if action.action_id in seen:
            reasons.append(TechnicalAdjustmentReason.DUPLICATE_ACTION_ID)
            continue
        seen.add(action.action_id)
        if action.canonical_instrument_id != instrument_id:
            reasons.append(TechnicalAdjustmentReason.EXACT_INSTRUMENT_MISMATCH)
            continue
        if not _aware(action.as_of) or not _aware(action.effective_date):
            raise TechnicalPriceAdjustmentError("CORPORATE_ACTION_TIMESTAMP_INVALID")
        if _utc(action.as_of) > at:
            reasons.append(TechnicalAdjustmentReason.ACTION_NOT_KNOWN_AS_OF)
            continue
        if _utc(action.effective_date) > at:
            reasons.append(TechnicalAdjustmentReason.ACTION_EFFECTIVE_AFTER_AS_OF)
            continue
        candidates.append(action)
    # Multiple same-kind actions on one exact effective boundary have no
    # approved ordering/identity policy.  Different kinds (split + bonus) are
    # composable by multiplication and remain explicitly lineaged.
    keys: dict[tuple[datetime, CorporateActionKind], list[HistoricalCorporateAction]] = {}
    for action in candidates:
        keys.setdefault((_utc(action.effective_date), action.kind), []).append(action)
    if any(len(group) > 1 for group in keys.values()):
        reasons.append(TechnicalAdjustmentReason.AMBIGUOUS_ACTION_EFFECTIVE_BOUNDARY)
        candidates = [action for action in candidates if len(keys[(_utc(action.effective_date), action.kind)]) == 1]
    receipts = tuple(_receipt(action) for action in sorted(candidates, key=lambda item: (_utc(item.effective_date), item.kind.value, item.action_id)))
    return receipts, _reasons(reasons)


def _receipt(action: HistoricalCorporateAction) -> TechnicalActionReceipt:
    category = _classify(action)
    source_fp = _action_source_fingerprint(action)
    price = volume = None
    reasons: list[TechnicalAdjustmentReason] = []
    if category is TechnicalCorporateActionClass.STOCK_SPLIT:
        if _is_nse_v1(action) and _split_face_value_terms(action) is not None:
            old, new = _split_face_value_terms(action) or (None, None)
            assert old is not None and new is not None
            price, volume = new / old, old / new
        else:
            reasons.append(TechnicalAdjustmentReason.SPLIT_RATIO_SEMANTICS_UNVERIFIED)
    elif category is TechnicalCorporateActionClass.BONUS:
        terms = _bonus_terms(action)
        if _is_nse_v1(action) and terms is not None:
            additional, existing = terms
            assert additional is not None and existing is not None
            price, volume = existing / (existing + additional), (existing + additional) / existing
        else:
            reasons.append(TechnicalAdjustmentReason.BONUS_RATIO_SEMANTICS_UNVERIFIED)
    elif category is TechnicalCorporateActionClass.RIGHTS:
        reasons.append(TechnicalAdjustmentReason.RIGHTS_ADJUSTMENT_NOT_READY)
    elif category is TechnicalCorporateActionClass.CASH_DIVIDEND:
        reasons.append(TechnicalAdjustmentReason.DIVIDEND_PRICE_POLICY_NOT_APPROVED)
    elif category is TechnicalCorporateActionClass.MERGER_DEMERGER_SPINOFF:
        reasons.append(TechnicalAdjustmentReason.COMPLEX_ACTION_NON_COMPARABLE)
    elif category is TechnicalCorporateActionClass.SECURITY_CONTINUITY:
        reasons.append(TechnicalAdjustmentReason.SECURITY_CONTINUITY_NON_COMPARABLE)
    else:
        reasons.append(TechnicalAdjustmentReason.OTHER_ACTION_NON_COMPARABLE)
    values = dict(action_id=action.action_id, canonical_instrument_id=action.canonical_instrument_id, action_class=category, effective_at=_utc(action.effective_date), source_known_at=_utc(action.as_of), source_fingerprint=source_fp, price_factor=price, volume_factor=volume, reasons=_reasons(reasons))
    return TechnicalActionReceipt(**values, fingerprint=_fingerprint(_action_payload_values(values)))


def _classify(action: HistoricalCorporateAction) -> TechnicalCorporateActionClass:
    return {
        CorporateActionKind.SPLIT: TechnicalCorporateActionClass.STOCK_SPLIT,
        CorporateActionKind.BONUS: TechnicalCorporateActionClass.BONUS,
        CorporateActionKind.RIGHTS: TechnicalCorporateActionClass.RIGHTS,
        CorporateActionKind.DIVIDEND: TechnicalCorporateActionClass.CASH_DIVIDEND,
        CorporateActionKind.MERGER: TechnicalCorporateActionClass.MERGER_DEMERGER_SPINOFF,
        CorporateActionKind.DEMERGER: TechnicalCorporateActionClass.MERGER_DEMERGER_SPINOFF,
        CorporateActionKind.SYMBOL_CHANGE: TechnicalCorporateActionClass.SECURITY_CONTINUITY,
    }.get(action.kind, TechnicalCorporateActionClass.OTHER_UNKNOWN)


def _is_nse_v1(action: HistoricalCorporateAction) -> bool:
    return action.source == "NSE_OFFICIAL_CORPORATE_ACTION_EXPORT" and action.revision == "nse-corporate-action-v1"


def _split_face_value_terms(action: HistoricalCorporateAction) -> tuple[Decimal, Decimal] | None:
    if action.details is None:
        return None
    try:
        purpose = json.loads(action.details).get("original_purpose", "")
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    matched = _SPLIT_FACE_VALUE.search(str(purpose))
    if matched is None:
        return None
    old, new = Decimal(matched.group(1)), Decimal(matched.group(2))
    if not _positive(old) or not _positive(new):
        return None
    # The action receipt's separately parsed values must agree with the
    # explicit source text.  A stale/tampered parsed ratio never gets repaired.
    if action.ratio_numerator != old or action.ratio_denominator != new:
        return None
    return old, new


def _bonus_terms(action: HistoricalCorporateAction) -> tuple[Decimal, Decimal] | None:
    if action.details is None:
        return None
    try:
        purpose = json.loads(action.details).get("original_purpose", "")
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    matched = _BONUS_RATIO.search(str(purpose))
    if matched is None:
        return None
    additional, existing = Decimal(matched.group(1)), Decimal(matched.group(2))
    if not _positive(additional) or not _positive(existing):
        return None
    if action.ratio_numerator != additional or action.ratio_denominator != existing:
        return None
    return additional, existing


def _result(instrument_id: str, at: datetime, target: PriceAdjustmentBasis, price: AdjustmentReadiness, continuity: PriceContinuityState, volume: VolumeAdjustmentState, raw_ids: tuple[str, ...], raw_fps: tuple[str, ...], actions: tuple[TechnicalActionReceipt, ...], derived: tuple[DerivedTechnicalOHLCVBar, ...], reasons: list[TechnicalAdjustmentReason]) -> TechnicalPriceAdjustmentResult:
    bars = tuple(sorted(zip(raw_ids, raw_fps)))
    actions = tuple(sorted(actions, key=lambda item: item.action_id))
    derived = tuple(sorted(derived, key=lambda item: item.derived_bar_id))
    values = dict(assessment_id=_assessment_id(instrument_id, at, target, tuple(item[0] for item in bars), actions), canonical_instrument_id=instrument_id, as_of=at, target_basis=target, price_readiness=price, continuity=continuity, volume_readiness=volume, raw_bar_ids=tuple(item[0] for item in bars), raw_bar_fingerprints=tuple(item[1] for item in bars), action_receipts=actions, derived_bars=derived, reasons=_reasons(reasons), policy_id=POLICY_ID, policy_version=POLICY_VERSION)
    return TechnicalPriceAdjustmentResult(**values, fingerprint=_fingerprint(_result_payload_values(values)))


def _raw_bar_fingerprint(bar: CanonicalOHLCVBar) -> str:
    return _fingerprint({"bar_id": bar.bar_id, "instrument_id": bar.instrument.instrument_id, "timeframe": bar.timeframe.value, "start_time": _time(bar.start_time), "end_time": _time(bar.end_time), "open": _decimal(bar.open), "high": _decimal(bar.high), "low": _decimal(bar.low), "close": _decimal(bar.close), "volume": bar.volume, "turnover": _decimal(bar.turnover), "trade_count": bar.trade_count, "adjustment_status": bar.adjustment_status.value, "provider": bar.provenance.provider, "normalization_version": bar.provenance.normalization_version, "received_at": _time(bar.provenance.received_at), "source_reference": bar.provenance.source_reference})


def _action_source_fingerprint(action: HistoricalCorporateAction) -> str:
    return _fingerprint({"action_id": action.action_id, "canonical_instrument_id": action.canonical_instrument_id, "kind": action.kind.value, "announcement_date": _time(action.announcement_date), "record_date": _time(action.record_date), "ex_date": _time(action.ex_date), "effective_date": _time(action.effective_date), "ratio_numerator": _decimal(action.ratio_numerator), "ratio_denominator": _decimal(action.ratio_denominator), "details": action.details, "source": action.source, "revision": action.revision, "as_of": _time(action.as_of), "source_reference": action.source_reference, "warnings": sorted(action.warnings)})


def _assessment_id(instrument_id: str, at: datetime, target: PriceAdjustmentBasis, raw_ids: tuple[str, ...], actions: tuple[TechnicalActionReceipt, ...]) -> str:
    return "technical-price-adjustment:" + sha256(_canonical({"instrument": instrument_id, "as_of": _time(at), "target": target.value, "raw_bars": raw_ids, "action_fingerprints": [item.fingerprint for item in actions], "policy": POLICY_VERSION}).encode()).hexdigest()[:24]


def _derived_id(raw_bar_id: str, at: datetime, action_ids: tuple[str, ...]) -> str:
    return "derived-technical-bar:" + sha256(_canonical({"raw_bar": raw_bar_id, "as_of": _time(at), "actions": action_ids, "policy": POLICY_VERSION}).encode()).hexdigest()[:24]


def _basis_payload(value: ProviderPriceBasisAssessment, reasons: tuple[TechnicalAdjustmentReason, ...]) -> dict[str, object]: return _basis_payload_values({name: getattr(value, name) for name in ProviderPriceBasisAssessment.__dataclass_fields__ if name != "fingerprint"} | {"reasons": reasons})
def _basis_payload_values(value: dict[str, object]) -> dict[str, object]: return {"contract": CONTRACT_ID, "version": CONTRACT_VERSION, "provider": value["provider"], "normalization_version": value["normalization_version"], "instrument_type": _enum(value["instrument_type"]), "provider_basis": _enum(value["provider_basis"]), "hsi_stored_basis": _enum(value["hsi_stored_basis"]), "raw_recoverable": value["raw_recoverable"], "transformation_documented": value["transformation_documented"], "canonical_technical_allowed": value["canonical_technical_allowed"], "reasons": [_enum(item) for item in value["reasons"]]}
def _action_payload(value: TechnicalActionReceipt, reasons: tuple[TechnicalAdjustmentReason, ...]) -> dict[str, object]: return _action_payload_values({name: getattr(value, name) for name in TechnicalActionReceipt.__dataclass_fields__ if name != "fingerprint"} | {"reasons": reasons})
def _action_payload_values(value: dict[str, object]) -> dict[str, object]: return {"contract": CONTRACT_ID, "version": CONTRACT_VERSION, "action_id": value["action_id"], "canonical_instrument_id": value["canonical_instrument_id"], "action_class": _enum(value["action_class"]), "effective_at": _time(value["effective_at"]), "source_known_at": _time(value["source_known_at"]), "source_fingerprint": value["source_fingerprint"], "price_factor": _decimal(value["price_factor"]), "volume_factor": _decimal(value["volume_factor"]), "reasons": [_enum(item) for item in value["reasons"]]}
def _derived_payload(value: DerivedTechnicalOHLCVBar, action_ids: tuple[str, ...]) -> dict[str, object]: return _derived_payload_values({name: getattr(value, name) for name in DerivedTechnicalOHLCVBar.__dataclass_fields__ if name != "fingerprint"} | {"action_ids": action_ids})
def _derived_payload_values(value: dict[str, object]) -> dict[str, object]: return {"contract": CONTRACT_ID, "version": CONTRACT_VERSION, "derived_bar_id": value["derived_bar_id"], "raw_bar_id": value["raw_bar_id"], "raw_bar_fingerprint": value["raw_bar_fingerprint"], "start_time": _time(value["start_time"]), "end_time": _time(value["end_time"]), "open": _decimal(value["open"]), "high": _decimal(value["high"]), "low": _decimal(value["low"]), "close": _decimal(value["close"]), "volume": _decimal(value["volume"]), "price_factor": _decimal(value["price_factor"]), "volume_factor": _decimal(value["volume_factor"]), "action_ids": list(value["action_ids"]), "adjustment_basis": _enum(value["adjustment_basis"]), "as_of": _time(value["as_of"])}
def _result_payload(value: TechnicalPriceAdjustmentResult, bars: tuple[tuple[str, str], ...], actions: tuple[TechnicalActionReceipt, ...], derived: tuple[DerivedTechnicalOHLCVBar, ...], reasons: tuple[TechnicalAdjustmentReason, ...]) -> dict[str, object]: return _result_payload_values({name: getattr(value, name) for name in TechnicalPriceAdjustmentResult.__dataclass_fields__ if name != "fingerprint"} | {"raw_bar_ids": tuple(item[0] for item in bars), "raw_bar_fingerprints": tuple(item[1] for item in bars), "action_receipts": actions, "derived_bars": derived, "reasons": reasons})
def _result_payload_values(value: dict[str, object]) -> dict[str, object]: return {"contract": CONTRACT_ID, "version": CONTRACT_VERSION, "assessment_id": value["assessment_id"], "canonical_instrument_id": value["canonical_instrument_id"], "as_of": _time(value["as_of"]), "target_basis": _enum(value["target_basis"]), "price_readiness": _enum(value["price_readiness"]), "continuity": _enum(value["continuity"]), "volume_readiness": _enum(value["volume_readiness"]), "raw_bars": [{"id": key, "fingerprint": fp} for key, fp in zip(value["raw_bar_ids"], value["raw_bar_fingerprints"], strict=True)], "actions": [{"id": item.action_id, "fingerprint": item.fingerprint} for item in value["action_receipts"]], "derived_bars": [{"id": item.derived_bar_id, "fingerprint": item.fingerprint} for item in value["derived_bars"]], "reasons": [_enum(item) for item in value["reasons"]], "policy_id": value["policy_id"], "policy_version": value["policy_version"]}

def _reasons(values) -> tuple[TechnicalAdjustmentReason, ...]: return tuple(sorted(set(values), key=lambda item: item.value))
def _canonical(value: object) -> str: return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
def _fingerprint(value: object) -> str: return "sha256:" + sha256(_canonical(value).encode()).hexdigest()
def _aware(value: object) -> bool: return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None
def _utc(value: datetime) -> datetime:
    if not _aware(value): raise TechnicalPriceAdjustmentError("TECHNICAL_PRICE_ADJUSTMENT_TIMESTAMP_AWARE_REQUIRED")
    return value.astimezone(UTC)
def _time(value: datetime | None) -> str | None: return None if value is None else _utc(value).isoformat()
def _decimal(value: Decimal | None) -> str | None: return None if value is None else format(value, "f")
def _enum(value: object) -> str: return value.value if isinstance(value, StrEnum) else str(value)
def _positive(value: object) -> bool: return isinstance(value, Decimal) and value > 0
def _positive_or_none(value: object) -> bool: return value is None or _positive(value)
def _product(values) -> Decimal:
    result = Decimal("1")
    for value in values:
        assert value is not None
        result *= value
    return result
__all__ = (
    "AdjustmentReadiness", "CONTRACT_ID", "CONTRACT_VERSION", "DerivedTechnicalOHLCVBar",
    "POLICY_ID", "POLICY_VERSION", "PriceContinuityState", "ProviderPriceBasisAssessment",
    "ProviderPriceBasisState", "TechnicalActionReceipt", "TechnicalAdjustmentReason",
    "TechnicalCorporateActionClass", "TechnicalPriceAdjustmentError", "TechnicalPriceAdjustmentResult",
    "VolumeAdjustmentState", "audit_provider_price_basis", "derive_technical_price_adjustment",
    "serialize_technical_price_adjustment",
)
