"""One explicit, certified NSE UDiFF Daily technical read boundary.

The UDiFF archive is a current descriptive source: its archive retrieval time
does not prove that HSI had the file at its original trade date.  This module
therefore makes the caller choose a use mode.  Only the current-descriptive
mode delegates to the existing per-window certifier.  Strict historical PIT
mode fails closed before any bar is selected.

This is a data-read boundary, not technical interpretation.  It does not
calculate indicators, construct analysis snapshots, persist a receipt, fetch a
provider, choose another provider, or merge provider observations.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from hashlib import sha256
import json
import re
from typing import Iterable

from app.historical.nse_udiff_effective_identity_coverage import (
    IdentityInterval,
    NseUdiffEffectiveIdentityCoverageIndex,
)
from app.historical.security_master import HistoricalCorporateAction
from app.market_data.models import CanonicalOHLCVBar
from app.market_data.nse_udiff_daily_integrity import NseUdiffConflictAssessment
from app.market_data.nse_udiff_daily_technical_eligibility import (
    CONTRACT_VERSION as CERTIFICATION_VERSION,
    DailyTechnicalEligibilityError,
    DailyTechnicalEligibilityReceipt,
    DailyTechnicalEligibilityState,
    DailyTechnicalRequirement,
    certify_daily_technical_eligibility,
    read_eligible_udiff_daily_bars,
)
from app.market_data.technical_source_basis_action_coverage import CorporateActionCoverageAssertion


CONTRACT_ID = "nse-udiff-daily-technical-read"
CONTRACT_VERSION = "v1"
POLICY_ID = "nse-udiff-daily-technical-read-policy"
POLICY_VERSION = "v1"
_ID = re.compile(r"[A-Za-z0-9._:-]+\Z")
_FP = re.compile(r"sha256:[0-9a-f]{64}\Z")


class NseUdiffDailyTechnicalUseMode(StrEnum):
    """A caller must state whether it asks for present descriptive data or PIT."""

    CURRENT_DESCRIPTIVE_TECHNICAL = "CURRENT_DESCRIPTIVE_TECHNICAL"
    STRICT_HISTORICAL_PIT_TECHNICAL = "STRICT_HISTORICAL_PIT_TECHNICAL"


class NseUdiffDailyTechnicalReadState(StrEnum):
    READY = "READY"
    NOT_READY = "NOT_READY"


class NseUdiffDailyTechnicalReadReason(StrEnum):
    STRICT_HISTORICAL_PIT_SOURCE_AVAILABILITY_UNAVAILABLE = "STRICT_HISTORICAL_PIT_SOURCE_AVAILABILITY_UNAVAILABLE"
    CERTIFICATION_NOT_READY = "CERTIFICATION_NOT_READY"
    CERTIFIED_SOURCE_MISMATCH = "CERTIFIED_SOURCE_MISMATCH"


class NseUdiffDailyTechnicalReadError(ValueError):
    """Stable error for malformed read inputs or tampered read results."""


@dataclass(frozen=True, slots=True)
class NseUdiffDailyTechnicalReadRequest:
    """One exact Daily window and its explicitly non-interchangeable use mode."""

    canonical_instrument_id: str
    start_session: date
    end_session: date
    requirement: DailyTechnicalRequirement
    use_mode: NseUdiffDailyTechnicalUseMode
    evaluation_as_of: datetime
    policy_id: str = POLICY_ID
    policy_version: str = POLICY_VERSION
    certification_version: str = CERTIFICATION_VERSION

    def __post_init__(self) -> None:
        if (
            not _ID.fullmatch(self.canonical_instrument_id)
            or not isinstance(self.start_session, date)
            or not isinstance(self.end_session, date)
            or self.start_session > self.end_session
            or not isinstance(self.requirement, DailyTechnicalRequirement)
            or not isinstance(self.use_mode, NseUdiffDailyTechnicalUseMode)
            or not _aware(self.evaluation_as_of)
            or (self.policy_id, self.policy_version, self.certification_version)
            != (POLICY_ID, POLICY_VERSION, CERTIFICATION_VERSION)
        ):
            raise NseUdiffDailyTechnicalReadError("NSE_UDIFF_DAILY_TECHNICAL_READ_REQUEST_INVALID")


@dataclass(frozen=True, slots=True)
class NseUdiffDailyTechnicalReadEvidence:
    """Caller-supplied canonical evidence; this boundary owns no repository."""

    expected_sessions: tuple[date, ...]
    observed_bars: tuple[CanonicalOHLCVBar, ...]
    identity_intervals: tuple[IdentityInterval, ...] | NseUdiffEffectiveIdentityCoverageIndex
    action_coverage: CorporateActionCoverageAssertion | None
    actions: tuple[HistoricalCorporateAction, ...] = ()
    conflicts: tuple[NseUdiffConflictAssessment, ...] = ()

    def __post_init__(self) -> None:
        expected = tuple(sorted(set(self.expected_sessions)))
        if not expected or self.expected_sessions != expected:
            raise NseUdiffDailyTechnicalReadError("NSE_UDIFF_DAILY_TECHNICAL_READ_EXPECTED_SESSIONS_INVALID")
        if self.observed_bars != tuple(sorted(self.observed_bars, key=lambda item: (item.start_time, item.bar_id))):
            raise NseUdiffDailyTechnicalReadError("NSE_UDIFF_DAILY_TECHNICAL_READ_BARS_ORDER_INVALID")
        if not isinstance(self.identity_intervals, NseUdiffEffectiveIdentityCoverageIndex):
            if self.identity_intervals != tuple(sorted(self.identity_intervals, key=lambda item: item.interval_id)):
                raise NseUdiffDailyTechnicalReadError("NSE_UDIFF_DAILY_TECHNICAL_READ_IDENTITIES_ORDER_INVALID")
            if len({item.interval_id for item in self.identity_intervals}) != len(self.identity_intervals):
                raise NseUdiffDailyTechnicalReadError("NSE_UDIFF_DAILY_TECHNICAL_READ_IDENTITIES_DUPLICATE")
        if self.actions != tuple(sorted(self.actions, key=lambda item: (item.effective_date, item.action_id))):
            raise NseUdiffDailyTechnicalReadError("NSE_UDIFF_DAILY_TECHNICAL_READ_ACTIONS_ORDER_INVALID")
        if self.conflicts != tuple(sorted(self.conflicts, key=lambda item: (item.trade_date, item.conflict_fingerprint))):
            raise NseUdiffDailyTechnicalReadError("NSE_UDIFF_DAILY_TECHNICAL_READ_CONFLICTS_ORDER_INVALID")


@dataclass(frozen=True, slots=True)
class NseUdiffCertifiedDailyTechnicalRead:
    """A complete eligible raw Daily window, or a typed no-bars failure result."""

    request: NseUdiffDailyTechnicalReadRequest
    state: NseUdiffDailyTechnicalReadState
    certification: DailyTechnicalEligibilityReceipt | None
    bars: tuple[CanonicalOHLCVBar, ...]
    source_observation_ids: tuple[str, ...]
    source_references: tuple[str, ...]
    reasons: tuple[str, ...]
    fingerprint: str

    def __post_init__(self) -> None:
        reasons = tuple(sorted(set(self.reasons)))
        source_ids = tuple(sorted(set(self.source_observation_ids)))
        references = tuple(sorted(set(self.source_references)))
        values = _result_payload(self, reasons=reasons, source_ids=source_ids, references=references)
        strict = self.request.use_mode is NseUdiffDailyTechnicalUseMode.STRICT_HISTORICAL_PIT_TECHNICAL
        ready = self.state is NseUdiffDailyTechnicalReadState.READY
        certification_ready = self.certification is not None and self.certification.eligibility is DailyTechnicalEligibilityState.READY
        expected_count = len(self.certification.expected_sessions) if certification_ready else 0
        selected_ids = () if self.certification is None else self.certification.source_bar_ids
        if (
            not isinstance(self.request, NseUdiffDailyTechnicalReadRequest)
            or not isinstance(self.state, NseUdiffDailyTechnicalReadState)
            or self.reasons != reasons
            or self.source_observation_ids != source_ids
            or self.source_references != references
            or any(not _ID.fullmatch(item) for item in reasons)
            or not _FP.fullmatch(self.fingerprint)
            or self.fingerprint != _fingerprint(values)
            or self.bars != tuple(sorted(self.bars, key=lambda item: (item.start_time, item.bar_id)))
            or len({item.bar_id for item in self.bars}) != len(self.bars)
            or (strict and (
                ready or self.certification is not None or self.bars or source_ids or references
                or reasons != (NseUdiffDailyTechnicalReadReason.STRICT_HISTORICAL_PIT_SOURCE_AVAILABILITY_UNAVAILABLE.value,)
            ))
            or (ready and not certification_ready)
            or (ready and (
                not self.bars
                or not references
                or len(self.bars) != expected_count
                # The certificate canonicalizes its lineage pairs by immutable
                # bar ID, while a usable Daily read must stay in exchange
                # session chronology.  Both exact sets must match; neither
                # ordering can be substituted for the other.
                or {item.bar_id for item in self.bars} != set(selected_ids)
                or source_ids != tuple(sorted(item.source_observation_identity for item in self.bars))
                or references != _source_references(self.bars)
                or reasons
            ))
            or (not strict and self.certification is None)
            or (not strict and not ready and (self.bars or source_ids or references))
        ):
            raise NseUdiffDailyTechnicalReadError("NSE_UDIFF_DAILY_TECHNICAL_READ_RESULT_INVALID")


def read_certified_daily_technical_bars(
    *, request: NseUdiffDailyTechnicalReadRequest, evidence: NseUdiffDailyTechnicalReadEvidence | None,
) -> NseUdiffCertifiedDailyTechnicalRead:
    """Read exactly one certified UDiFF window with no provider fallback.

    A strict historical PIT request deliberately does not call the certifier or
    examine candidate bars.  That prevents a successful current-descriptive
    cache/result from being mistaken for historical availability evidence.
    """
    request.__post_init__()
    if request.use_mode is NseUdiffDailyTechnicalUseMode.STRICT_HISTORICAL_PIT_TECHNICAL:
        return _blocked(
            request,
            None,
            (NseUdiffDailyTechnicalReadReason.STRICT_HISTORICAL_PIT_SOURCE_AVAILABILITY_UNAVAILABLE.value,),
        )
    if not isinstance(evidence, NseUdiffDailyTechnicalReadEvidence):
        raise NseUdiffDailyTechnicalReadError("NSE_UDIFF_DAILY_TECHNICAL_READ_EVIDENCE_REQUIRED")
    evidence.__post_init__()
    certification = certify_daily_technical_eligibility(
        canonical_instrument_id=request.canonical_instrument_id,
        start_session=request.start_session,
        end_session=request.end_session,
        requirement=request.requirement,
        evaluation_as_of=_utc(request.evaluation_as_of),
        expected_sessions=evidence.expected_sessions,
        observed_bars=evidence.observed_bars,
        identity_intervals=evidence.identity_intervals,
        action_coverage=evidence.action_coverage,
        actions=evidence.actions,
        conflicts=evidence.conflicts,
    )
    if certification.eligibility is not DailyTechnicalEligibilityState.READY:
        return _blocked(
            request,
            certification,
            (NseUdiffDailyTechnicalReadReason.CERTIFICATION_NOT_READY.value, *(
                item.value for item in certification.reasons
            )),
        )
    try:
        selected = read_eligible_udiff_daily_bars(receipt=certification, observed_bars=evidence.observed_bars).bars
    except (DailyTechnicalEligibilityError, ValueError):
        return _blocked(request, certification, (NseUdiffDailyTechnicalReadReason.CERTIFIED_SOURCE_MISMATCH.value,))
    references = _source_references(selected)
    if not references:
        return _blocked(request, certification, (NseUdiffDailyTechnicalReadReason.CERTIFIED_SOURCE_MISMATCH.value,))
    values = dict(
        request=request,
        state=NseUdiffDailyTechnicalReadState.READY,
        certification=certification,
        bars=selected,
        source_observation_ids=tuple(sorted(item.source_observation_identity for item in selected)),
        source_references=references,
        reasons=(),
    )
    return NseUdiffCertifiedDailyTechnicalRead(**values, fingerprint=_fingerprint(_result_payload_values(values)))


def serialize_nse_udiff_certified_daily_technical_read(value: NseUdiffCertifiedDailyTechnicalRead) -> str:
    """Canonical deterministic serialization; it includes every result fingerprint input."""
    value.__post_init__()
    return _canonical(_result_payload(value, reasons=value.reasons, source_ids=value.source_observation_ids, references=value.source_references) | {"fingerprint": value.fingerprint})


def _blocked(
    request: NseUdiffDailyTechnicalReadRequest,
    certification: DailyTechnicalEligibilityReceipt | None,
    reasons: tuple[str, ...],
) -> NseUdiffCertifiedDailyTechnicalRead:
    values = dict(
        request=request,
        state=NseUdiffDailyTechnicalReadState.NOT_READY,
        certification=certification,
        bars=(),
        source_observation_ids=(),
        source_references=(),
        reasons=tuple(sorted(set(reasons))),
    )
    return NseUdiffCertifiedDailyTechnicalRead(**values, fingerprint=_fingerprint(_result_payload_values(values)))


def _result_payload(
    value: NseUdiffCertifiedDailyTechnicalRead, *, reasons: tuple[str, ...], source_ids: tuple[str, ...], references: tuple[str, ...],
) -> dict[str, object]:
    return _result_payload_values({
        "request": value.request,
        "state": value.state,
        "certification": value.certification,
        "bars": value.bars,
        "source_observation_ids": source_ids,
        "source_references": references,
        "reasons": reasons,
    })


def _result_payload_values(values: dict[str, object]) -> dict[str, object]:
    request = values["request"]
    assert isinstance(request, NseUdiffDailyTechnicalReadRequest)
    certification = values["certification"]
    assert certification is None or isinstance(certification, DailyTechnicalEligibilityReceipt)
    bars = values["bars"]
    assert isinstance(bars, tuple)
    return {
        "contract": CONTRACT_ID,
        "version": CONTRACT_VERSION,
        "policy": {"id": request.policy_id, "version": request.policy_version},
        "request": {
            "instrument": request.canonical_instrument_id,
            "start_session": request.start_session.isoformat(),
            "end_session": request.end_session.isoformat(),
            "requirement": {"profile": request.requirement.profile.value, "version": request.requirement.profile_version},
            "use_mode": request.use_mode.value,
            "evaluation_as_of": _utc(request.evaluation_as_of).isoformat(),
            "certification_version": request.certification_version,
        },
        "state": _enum(values["state"]),
        "certification": None if certification is None else {
            "id": certification.receipt_id,
            "fingerprint": certification.fingerprint,
            "policy": {
                "id": certification.source_policy_id,
                "version": certification.source_policy_version,
                "fingerprint": certification.source_policy_fingerprint,
            },
            "identity_intervals": list(zip(certification.identity_interval_ids, certification.identity_interval_fingerprints, strict=True)),
            "action_coverage_fingerprint": certification.action_coverage_fingerprint,
            "actions": list(zip(certification.action_ids, certification.action_fingerprints, strict=True)),
            "price_continuity": certification.price_continuity.value,
            "volume_continuity": certification.volume_continuity.value,
        },
        "bars": [item.bar_id for item in bars],
        "source_observation_ids": list(values["source_observation_ids"]),
        "source_references": list(values["source_references"]),
        "reasons": list(values["reasons"]),
    }


def _source_references(bars: tuple[CanonicalOHLCVBar, ...]) -> tuple[str, ...]:
    if any(not item.provenance.source_reference for item in bars):
        return ()
    return tuple(sorted({item.provenance.source_reference for item in bars if item.provenance.source_reference}))


def _aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def _utc(value: datetime) -> datetime:
    if not _aware(value):
        raise NseUdiffDailyTechnicalReadError("NSE_UDIFF_DAILY_TECHNICAL_READ_TIMESTAMP_AWARE_REQUIRED")
    return value.astimezone(UTC)


def _enum(value: object) -> str:
    return value.value if isinstance(value, StrEnum) else str(value)


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _fingerprint(value: object) -> str:
    return "sha256:" + sha256(_canonical(value).encode("utf-8")).hexdigest()


__all__ = (
    "CONTRACT_ID", "CONTRACT_VERSION", "POLICY_ID", "POLICY_VERSION",
    "NseUdiffCertifiedDailyTechnicalRead", "NseUdiffDailyTechnicalReadError",
    "NseUdiffDailyTechnicalReadEvidence", "NseUdiffDailyTechnicalReadReason",
    "NseUdiffDailyTechnicalReadRequest", "NseUdiffDailyTechnicalReadState",
    "NseUdiffDailyTechnicalUseMode", "read_certified_daily_technical_bars",
    "serialize_nse_udiff_certified_daily_technical_read",
)
