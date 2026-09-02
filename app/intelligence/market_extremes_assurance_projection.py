"""Pure Post-V1 usability assurance over immutable Core Market-Extremes inputs.

This module deliberately does not calculate an extreme, read a repository, or
turn a regime into a product action.  It verifies explicitly supplied
``UpsideExcessAssessment`` candidates for a consumer at an explicit cutoff.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
import json
import re

from app.crisis.models import (
    DistributionRisk,
    LeadershipQuality,
    MarketCycleStage,
    MarketExtremeLevel,
    PriceEarningsDivergence,
    UpsideExcessAssessment,
    UpsideExcessFactor,
    UpsideExcessState,
)
from app.historical.guard import manifest_fingerprint


MARKET_EXTREMES_ASSURANCE_CONTRACT = "market-extremes-assurance-projection/v1"
MARKET_EXTREMES_ASSURANCE_FINGERPRINT_SCHEME = "market-extremes-assurance-candidate/sha256/v1"
_IDENTIFIER = re.compile(r"[A-Za-z0-9._:-]+")
_FINGERPRINT = re.compile(r"sha256:[0-9a-f]{64}")


class MarketExtremesAssuranceError(ValueError):
    """Raised when assurance context or an output contract is malformed."""


class MarketExtremesAssuranceState(StrEnum):
    READY = "READY"
    CONFLICTED = "CONFLICTED"
    UNAVAILABLE = "UNAVAILABLE"
    STALE = "STALE"
    TEMPORALLY_INVALID = "TEMPORALLY_INVALID"
    UNVERIFIABLE = "UNVERIFIABLE"


class MarketExtremesAssuranceReason(StrEnum):
    MARKET_EXTREMES_SNAPSHOT_UNAVAILABLE = "MARKET_EXTREMES_SNAPSHOT_UNAVAILABLE"
    MARKET_EXTREMES_FINGERPRINT_MISMATCH = "MARKET_EXTREMES_FINGERPRINT_MISMATCH"
    MARKET_EXTREMES_IDENTITY_INVALID = "MARKET_EXTREMES_IDENTITY_INVALID"
    MARKET_EXTREMES_POLICY_VERSION_MISMATCH = "MARKET_EXTREMES_POLICY_VERSION_MISMATCH"
    MARKET_EXTREMES_TIMESTAMP_INVALID = "MARKET_EXTREMES_TIMESTAMP_INVALID"
    MARKET_EXTREMES_AFTER_REQUESTED_AS_OF = "MARKET_EXTREMES_AFTER_REQUESTED_AS_OF"
    MARKET_EXTREMES_STALE_AT_FRESHNESS_FLOOR = "MARKET_EXTREMES_STALE_AT_FRESHNESS_FLOOR"
    MARKET_EXTREMES_SELECTED_TIMESTAMP_CONFLICT = "MARKET_EXTREMES_SELECTED_TIMESTAMP_CONFLICT"
    MARKET_EXTREMES_PROVENANCE_UNVERIFIABLE = "MARKET_EXTREMES_PROVENANCE_UNVERIFIABLE"
    FRESHNESS_FLOOR_AFTER_AS_OF = "FRESHNESS_FLOOR_AFTER_AS_OF"
    MARKET_EXTREMES_EXACT_DUPLICATE_CANDIDATE = "MARKET_EXTREMES_EXACT_DUPLICATE_CANDIDATE"


@dataclass(frozen=True, slots=True)
class MarketExtremesAssuranceContext:
    as_of: datetime
    freshness_floor: datetime
    expected_policy_version: str
    expected_fingerprint_scheme: str = MARKET_EXTREMES_ASSURANCE_FINGERPRINT_SCHEME
    expected_entity_id: str | None = None

    def __post_init__(self) -> None:
        _require_aware(self.as_of, "MARKET_EXTREMES_TIMESTAMP_INVALID")
        _require_aware(self.freshness_floor, "MARKET_EXTREMES_TIMESTAMP_INVALID")
        if _utc(self.freshness_floor) > _utc(self.as_of):
            raise MarketExtremesAssuranceError(MarketExtremesAssuranceReason.FRESHNESS_FLOOR_AFTER_AS_OF.value)
        _require_text(self.expected_policy_version, "MARKET_EXTREMES_POLICY_VERSION_MISMATCH")
        _require_text(self.expected_fingerprint_scheme, "MARKET_EXTREMES_PROVENANCE_UNVERIFIABLE")
        if self.expected_entity_id is not None:
            _require_identifier(self.expected_entity_id, "MARKET_EXTREMES_IDENTITY_INVALID")


@dataclass(frozen=True, slots=True)
class MarketExtremesAssuranceCandidate:
    """An untrusted immutable wrapper around an unchanged Core assessment."""

    snapshot_id: str
    stored_fingerprint: str
    fingerprint_scheme: str
    assessment: UpsideExcessAssessment


def market_extremes_assurance_candidate(
    *,
    snapshot_id: str,
    assessment: UpsideExcessAssessment,
    fingerprint_scheme: str = MARKET_EXTREMES_ASSURANCE_FINGERPRINT_SCHEME,
) -> MarketExtremesAssuranceCandidate:
    """Build a verifiable candidate without changing the Core assessment."""
    candidate = MarketExtremesAssuranceCandidate(snapshot_id, "", fingerprint_scheme, assessment)
    return MarketExtremesAssuranceCandidate(
        snapshot_id, _candidate_fingerprint(candidate), fingerprint_scheme, assessment,
    )


@dataclass(frozen=True, slots=True)
class MarketExtremesCandidateReference:
    reference_id: str
    snapshot_id: str | None
    stored_fingerprint: str | None
    effective_as_of: datetime | None
    reason_codes: tuple[MarketExtremesAssuranceReason, ...]


@dataclass(frozen=True, slots=True)
class MarketExtremesAssuranceVerificationSummary:
    supplied_candidates: int
    unique_candidates: int
    duplicate_candidates: int
    verified_candidates: int
    pit_eligible_candidates: int
    rejected_candidates: int
    future_candidates: int


@dataclass(frozen=True, slots=True)
class MarketExtremesAssuranceProjection:
    context: MarketExtremesAssuranceContext
    assurance_state: MarketExtremesAssuranceState
    candidate_references: tuple[MarketExtremesCandidateReference, ...]
    rejected_candidate_references: tuple[MarketExtremesCandidateReference, ...]
    verification_summary: MarketExtremesAssuranceVerificationSummary
    reason_codes: tuple[MarketExtremesAssuranceReason, ...]
    selected_regime: UpsideExcessState | None
    selected_snapshot_id: str | None
    selected_snapshot_fingerprint: str | None
    selected_effective_as_of: datetime | None
    contract_version: str = MARKET_EXTREMES_ASSURANCE_CONTRACT
    projection_id: str = field(init=False)
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        _validate_projection(self)
        object.__setattr__(self, "projection_id", "market-extremes-assurance:" + manifest_fingerprint(**_identity_payload(self))[:24])
        object.__setattr__(self, "fingerprint", "sha256:" + manifest_fingerprint(**_full_payload(self)))

    def verify(self) -> None:
        _validate_projection(self)
        expected_id = "market-extremes-assurance:" + manifest_fingerprint(**_identity_payload(self))[:24]
        if self.projection_id != expected_id:
            raise MarketExtremesAssuranceError("MARKET_EXTREMES_ASSURANCE_IDENTITY_MISMATCH")
        if self.fingerprint != "sha256:" + manifest_fingerprint(**_full_payload(self)):
            raise MarketExtremesAssuranceError("MARKET_EXTREMES_ASSURANCE_FINGERPRINT_MISMATCH")


@dataclass(frozen=True, slots=True)
class _VerifiedCandidate:
    candidate: MarketExtremesAssuranceCandidate
    reference: MarketExtremesCandidateReference
    effective_as_of: datetime
    content_fingerprint: str


def project_market_extremes_assurance(
    context: MarketExtremesAssuranceContext,
    candidates: tuple[MarketExtremesAssuranceCandidate, ...],
) -> MarketExtremesAssuranceProjection:
    """Select one verified, PIT-valid candidate without reading external state."""
    if not isinstance(context, MarketExtremesAssuranceContext):
        raise MarketExtremesAssuranceError("MARKET_EXTREMES_ASSURANCE_CONTEXT_REQUIRED")
    if not all(isinstance(item, MarketExtremesAssuranceCandidate) for item in candidates):
        raise MarketExtremesAssuranceError("MARKET_EXTREMES_ASSURANCE_CANDIDATE_TYPE_INVALID")

    ordered = tuple(sorted(candidates, key=_candidate_sort_key))
    references: list[MarketExtremesCandidateReference] = []
    rejected: list[MarketExtremesCandidateReference] = []
    verified: list[_VerifiedCandidate] = []
    duplicate_count = 0
    previous: MarketExtremesAssuranceCandidate | None = None
    for candidate in ordered:
        if previous is not None and candidate == previous:
            duplicate_count += 1
            reference = _reference(candidate, (MarketExtremesAssuranceReason.MARKET_EXTREMES_EXACT_DUPLICATE_CANDIDATE,))
            references.append(reference)
            rejected.append(reference)
            continue
        previous = candidate
        outcome = _verify_candidate(candidate, context)
        references.append(outcome.reference)
        if outcome.verified is None:
            rejected.append(outcome.reference)
        else:
            verified.append(outcome.verified)

    future: list[_VerifiedCandidate] = []
    eligible: list[_VerifiedCandidate] = []
    for candidate in verified:
        if _utc(candidate.candidate.assessment.data_as_of) > _utc(context.as_of) or _utc(candidate.candidate.assessment.assessed_at) > _utc(context.as_of):
            reference = _with_reasons(candidate.reference, (MarketExtremesAssuranceReason.MARKET_EXTREMES_AFTER_REQUESTED_AS_OF,))
            references[references.index(candidate.reference)] = reference
            rejected.append(reference)
            future.append(candidate)
        else:
            eligible.append(candidate)

    summary = MarketExtremesAssuranceVerificationSummary(
        supplied_candidates=len(candidates), unique_candidates=len(ordered) - duplicate_count,
        duplicate_candidates=duplicate_count, verified_candidates=len(verified),
        pit_eligible_candidates=len(eligible), rejected_candidates=len(rejected),
        future_candidates=len(future),
    )
    canonical_references = tuple(sorted(references, key=_reference_key))
    canonical_rejected = tuple(sorted(rejected, key=_reference_key))
    if not candidates:
        return _projection(context, MarketExtremesAssuranceState.UNAVAILABLE, canonical_references, canonical_rejected, summary,
                           (MarketExtremesAssuranceReason.MARKET_EXTREMES_SNAPSHOT_UNAVAILABLE,), None)
    if not eligible:
        if verified and len(future) == len(verified):
            return _projection(context, MarketExtremesAssuranceState.TEMPORALLY_INVALID, canonical_references, canonical_rejected, summary,
                               (MarketExtremesAssuranceReason.MARKET_EXTREMES_AFTER_REQUESTED_AS_OF,), None)
        reasons = _all_rejection_reasons(canonical_rejected) or (MarketExtremesAssuranceReason.MARKET_EXTREMES_PROVENANCE_UNVERIFIABLE,)
        return _projection(context, MarketExtremesAssuranceState.UNVERIFIABLE, canonical_references, canonical_rejected, summary, reasons, None)

    selected_time = max(_utc(item.effective_as_of) for item in eligible)
    selected = tuple(item for item in eligible if _utc(item.effective_as_of) == selected_time)
    fingerprints = {item.content_fingerprint for item in selected}
    if len(fingerprints) > 1:
        return _projection(context, MarketExtremesAssuranceState.CONFLICTED, canonical_references, canonical_rejected, summary,
                           (MarketExtremesAssuranceReason.MARKET_EXTREMES_SELECTED_TIMESTAMP_CONFLICT,), None)
    chosen = selected[0]
    state = (
        MarketExtremesAssuranceState.STALE
        if _utc(chosen.effective_as_of) < _utc(context.freshness_floor)
        else MarketExtremesAssuranceState.READY
    )
    reasons = (
        (MarketExtremesAssuranceReason.MARKET_EXTREMES_STALE_AT_FRESHNESS_FLOOR,)
        if state is MarketExtremesAssuranceState.STALE else ()
    )
    return _projection(context, state, canonical_references, canonical_rejected, summary, reasons, chosen)


def market_extremes_assurance_payload(value: MarketExtremesAssuranceProjection) -> dict[str, object]:
    if not isinstance(value, MarketExtremesAssuranceProjection):
        raise MarketExtremesAssuranceError("MARKET_EXTREMES_ASSURANCE_PROJECTION_REQUIRED")
    value.verify()
    return _full_payload(value) | {"fingerprint": value.fingerprint}


def serialize_market_extremes_assurance(value: MarketExtremesAssuranceProjection) -> str:
    return json.dumps(market_extremes_assurance_payload(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _projection(
    context: MarketExtremesAssuranceContext,
    state: MarketExtremesAssuranceState,
    references: tuple[MarketExtremesCandidateReference, ...],
    rejected: tuple[MarketExtremesCandidateReference, ...],
    summary: MarketExtremesAssuranceVerificationSummary,
    reasons: tuple[MarketExtremesAssuranceReason, ...],
    chosen: _VerifiedCandidate | None,
) -> MarketExtremesAssuranceProjection:
    usable = state is MarketExtremesAssuranceState.READY
    return MarketExtremesAssuranceProjection(
        context, state, references, rejected, summary, tuple(sorted(set(reasons), key=lambda item: item.value)),
        chosen.candidate.assessment.excess_state if usable and chosen is not None else None,
        chosen.candidate.snapshot_id if state in {MarketExtremesAssuranceState.READY, MarketExtremesAssuranceState.STALE} and chosen is not None else None,
        chosen.content_fingerprint if state in {MarketExtremesAssuranceState.READY, MarketExtremesAssuranceState.STALE} and chosen is not None else None,
        chosen.effective_as_of if state in {MarketExtremesAssuranceState.READY, MarketExtremesAssuranceState.STALE} and chosen is not None else None,
    )


@dataclass(frozen=True, slots=True)
class _VerificationOutcome:
    reference: MarketExtremesCandidateReference
    verified: _VerifiedCandidate | None


def _verify_candidate(candidate: MarketExtremesAssuranceCandidate, context: MarketExtremesAssuranceContext) -> _VerificationOutcome:
    reasons: set[MarketExtremesAssuranceReason] = set()
    if not _is_identifier(candidate.snapshot_id):
        reasons.add(MarketExtremesAssuranceReason.MARKET_EXTREMES_IDENTITY_INVALID)
    if candidate.fingerprint_scheme != context.expected_fingerprint_scheme:
        reasons.add(MarketExtremesAssuranceReason.MARKET_EXTREMES_PROVENANCE_UNVERIFIABLE)
    assessment = candidate.assessment
    if not isinstance(assessment, UpsideExcessAssessment):
        reasons.add(MarketExtremesAssuranceReason.MARKET_EXTREMES_PROVENANCE_UNVERIFIABLE)
    else:
        reasons.update(_assessment_reasons(assessment, context))
    if reasons:
        return _VerificationOutcome(_reference(candidate, tuple(sorted(reasons, key=lambda item: item.value))), None)
    expected = _candidate_fingerprint(candidate)
    if candidate.stored_fingerprint != expected:
        return _VerificationOutcome(_reference(candidate, (MarketExtremesAssuranceReason.MARKET_EXTREMES_FINGERPRINT_MISMATCH,)), None)
    effective = assessment.data_as_of
    return _VerificationOutcome(_reference(candidate, ()), _VerifiedCandidate(candidate, _reference(candidate, ()), effective, expected))


def _assessment_reasons(value: UpsideExcessAssessment, context: MarketExtremesAssuranceContext) -> set[MarketExtremesAssuranceReason]:
    reasons: set[MarketExtremesAssuranceReason] = set()
    if not all((_is_identifier(value.assessment_id), _is_identifier(value.entity_id), isinstance(value.policy_version, str) and value.policy_version.strip())):
        reasons.add(MarketExtremesAssuranceReason.MARKET_EXTREMES_IDENTITY_INVALID)
    if value.policy_version != context.expected_policy_version:
        reasons.add(MarketExtremesAssuranceReason.MARKET_EXTREMES_POLICY_VERSION_MISMATCH)
    if context.expected_entity_id is not None and value.entity_id != context.expected_entity_id:
        reasons.add(MarketExtremesAssuranceReason.MARKET_EXTREMES_IDENTITY_INVALID)
    if not _assessment_types_valid(value) or not _assessment_timestamps_valid(value):
        reasons.add(MarketExtremesAssuranceReason.MARKET_EXTREMES_TIMESTAMP_INVALID)
    if not _lineage_valid(value):
        reasons.add(MarketExtremesAssuranceReason.MARKET_EXTREMES_PROVENANCE_UNVERIFIABLE)
    return reasons


def _assessment_types_valid(value: UpsideExcessAssessment) -> bool:
    return (
        isinstance(value.level, MarketExtremeLevel) and isinstance(value.excess_state, UpsideExcessState)
        and isinstance(value.cycle_stage, MarketCycleStage) and isinstance(value.distribution_risk, DistributionRisk)
        and isinstance(value.leadership_quality, LeadershipQuality)
        and isinstance(value.price_earnings_divergence, PriceEarningsDivergence)
        and isinstance(value.top_confirmed, bool) and isinstance(value.transition_reason, str) and bool(value.transition_reason.strip())
        and _factors_valid(value.supporting_factors) and _factors_valid(value.contradicting_factors)
        and _factors_valid(value.unavailable_factors)
    )


def _assessment_timestamps_valid(value: UpsideExcessAssessment) -> bool:
    try:
        _require_aware(value.assessed_at, "MARKET_EXTREMES_TIMESTAMP_INVALID")
        _require_aware(value.data_as_of, "MARKET_EXTREMES_TIMESTAMP_INVALID")
        return _utc(value.data_as_of) <= _utc(value.assessed_at)
    except MarketExtremesAssuranceError:
        return False


def _lineage_valid(value: UpsideExcessAssessment) -> bool:
    return bool(value.evidence_ids) and bool(value.provenance_ids) and all(
        _is_identifier(item) for item in (*value.evidence_ids, *value.provenance_ids)
    )


def _factors_valid(values: tuple[UpsideExcessFactor, ...]) -> bool:
    return isinstance(values, tuple) and all(isinstance(item, UpsideExcessFactor) for item in values)


def _candidate_fingerprint(value: MarketExtremesAssuranceCandidate) -> str:
    return "sha256:" + manifest_fingerprint(
        contract=MARKET_EXTREMES_ASSURANCE_CONTRACT,
        fingerprint_scheme=value.fingerprint_scheme,
        snapshot_id=value.snapshot_id,
        assessment=_assessment_payload(value.assessment),
    )


def _assessment_payload(value: UpsideExcessAssessment) -> dict[str, object]:
    return {
        "assessment_id": value.assessment_id, "policy_version": value.policy_version,
        "level": value.level.value, "entity_id": value.entity_id,
        "excess_state": value.excess_state.value, "cycle_stage": value.cycle_stage.value,
        "excess_score": None if value.excess_score is None else str(value.excess_score),
        "confidence": value.confidence, "top_confirmed": value.top_confirmed,
        "distribution_risk": value.distribution_risk.value,
        "leadership_quality": value.leadership_quality.value,
        "price_earnings_divergence": value.price_earnings_divergence.value,
        "assessed_at": _timestamp(value.assessed_at), "data_as_of": _timestamp(value.data_as_of),
        "previous_state": None if value.previous_state is None else value.previous_state.value,
        "transition_reason": value.transition_reason,
        "supporting_factors": tuple(sorted(item.value for item in value.supporting_factors)),
        "contradicting_factors": tuple(sorted(item.value for item in value.contradicting_factors)),
        "unavailable_factors": tuple(sorted(item.value for item in value.unavailable_factors)),
        "warnings": tuple(sorted(value.warnings)), "evidence_ids": tuple(sorted(value.evidence_ids)),
        "provenance_ids": tuple(sorted(value.provenance_ids)),
    }


def _reference(candidate: MarketExtremesAssuranceCandidate, reasons: tuple[MarketExtremesAssuranceReason, ...]) -> MarketExtremesCandidateReference:
    assessment = candidate.assessment
    effective = assessment.data_as_of if isinstance(assessment, UpsideExcessAssessment) and _is_aware(assessment.data_as_of) else None
    snapshot_id = candidate.snapshot_id if _is_identifier(candidate.snapshot_id) else None
    stored = candidate.stored_fingerprint if isinstance(candidate.stored_fingerprint, str) else None
    reference_id = "market-extremes-candidate:" + manifest_fingerprint(
        snapshot_id=candidate.snapshot_id, stored_fingerprint=candidate.stored_fingerprint,
        fingerprint_scheme=candidate.fingerprint_scheme,
        assessment_id=assessment.assessment_id if isinstance(assessment, UpsideExcessAssessment) else None,
        effective_at=None if effective is None else _timestamp(effective),
    )[:24]
    return MarketExtremesCandidateReference(reference_id, snapshot_id, stored, effective, tuple(sorted(set(reasons), key=lambda item: item.value)))


def _with_reasons(value: MarketExtremesCandidateReference, reasons: tuple[MarketExtremesAssuranceReason, ...]) -> MarketExtremesCandidateReference:
    return MarketExtremesCandidateReference(
        value.reference_id, value.snapshot_id, value.stored_fingerprint, value.effective_as_of,
        tuple(sorted(set((*value.reason_codes, *reasons)), key=lambda item: item.value)),
    )


def _candidate_sort_key(value: MarketExtremesAssuranceCandidate) -> tuple[str, str, str, str, str]:
    assessment = value.assessment
    effective = _timestamp(assessment.data_as_of) if isinstance(assessment, UpsideExcessAssessment) and _is_aware(assessment.data_as_of) else ""
    assessment_id = assessment.assessment_id if isinstance(assessment, UpsideExcessAssessment) and isinstance(assessment.assessment_id, str) else ""
    return str(value.snapshot_id), str(value.stored_fingerprint), str(value.fingerprint_scheme), effective, assessment_id


def _reference_key(value: MarketExtremesCandidateReference) -> tuple[str, str, str, str, tuple[str, ...]]:
    return (
        value.reference_id, value.snapshot_id or "", value.stored_fingerprint or "",
        "" if value.effective_as_of is None else _timestamp(value.effective_as_of),
        tuple(item.value for item in value.reason_codes),
    )


def _all_rejection_reasons(values: tuple[MarketExtremesCandidateReference, ...]) -> tuple[MarketExtremesAssuranceReason, ...]:
    return tuple(sorted({reason for value in values for reason in value.reason_codes if reason is not MarketExtremesAssuranceReason.MARKET_EXTREMES_EXACT_DUPLICATE_CANDIDATE}, key=lambda item: item.value))


def _validate_projection(value: MarketExtremesAssuranceProjection) -> None:
    if value.contract_version != MARKET_EXTREMES_ASSURANCE_CONTRACT or not isinstance(value.context, MarketExtremesAssuranceContext):
        raise MarketExtremesAssuranceError("MARKET_EXTREMES_ASSURANCE_CONTRACT_INVALID")
    if not isinstance(value.assurance_state, MarketExtremesAssuranceState):
        raise MarketExtremesAssuranceError("MARKET_EXTREMES_ASSURANCE_STATE_INVALID")
    if value.candidate_references != tuple(sorted(value.candidate_references, key=_reference_key)):
        raise MarketExtremesAssuranceError("MARKET_EXTREMES_ASSURANCE_REFERENCES_NONCANONICAL")
    if value.rejected_candidate_references != tuple(sorted(value.rejected_candidate_references, key=_reference_key)):
        raise MarketExtremesAssuranceError("MARKET_EXTREMES_ASSURANCE_REJECTIONS_NONCANONICAL")
    if any(not isinstance(item, MarketExtremesCandidateReference) for item in (*value.candidate_references, *value.rejected_candidate_references)):
        raise MarketExtremesAssuranceError("MARKET_EXTREMES_ASSURANCE_REFERENCE_INVALID")
    if value.reason_codes != tuple(sorted(set(value.reason_codes), key=lambda item: item.value)):
        raise MarketExtremesAssuranceError("MARKET_EXTREMES_ASSURANCE_REASONS_NONCANONICAL")
    usable = value.assurance_state is MarketExtremesAssuranceState.READY
    selected_metadata = (value.selected_snapshot_id, value.selected_snapshot_fingerprint, value.selected_effective_as_of)
    if usable:
        if not isinstance(value.selected_regime, UpsideExcessState) or any(item is None for item in selected_metadata):
            raise MarketExtremesAssuranceError("MARKET_EXTREMES_ASSURANCE_READY_SELECTION_REQUIRED")
    elif value.selected_regime is not None:
        raise MarketExtremesAssuranceError("MARKET_EXTREMES_ASSURANCE_NONUSABLE_REGIME_FORBIDDEN")
    if value.assurance_state in {MarketExtremesAssuranceState.CONFLICTED, MarketExtremesAssuranceState.UNAVAILABLE, MarketExtremesAssuranceState.TEMPORALLY_INVALID, MarketExtremesAssuranceState.UNVERIFIABLE} and any(item is not None for item in selected_metadata):
        raise MarketExtremesAssuranceError("MARKET_EXTREMES_ASSURANCE_NONUSABLE_SELECTION_FORBIDDEN")
    if value.selected_effective_as_of is not None:
        _require_aware(value.selected_effective_as_of, "MARKET_EXTREMES_TIMESTAMP_INVALID")
    if value.selected_snapshot_id is not None:
        _require_identifier(value.selected_snapshot_id, "MARKET_EXTREMES_IDENTITY_INVALID")
    if value.selected_snapshot_fingerprint is not None:
        _require_fingerprint(value.selected_snapshot_fingerprint, "MARKET_EXTREMES_FINGERPRINT_MISMATCH")


def _identity_payload(value: MarketExtremesAssuranceProjection) -> dict[str, object]:
    return {
        "contract_version": value.contract_version, "context": _context_payload(value.context),
        "state": value.assurance_state.value, "references": tuple(_reference_payload(item) for item in value.candidate_references),
        "rejected": tuple(_reference_payload(item) for item in value.rejected_candidate_references),
        "reason_codes": tuple(item.value for item in value.reason_codes),
        "selected_snapshot_id": value.selected_snapshot_id,
        "selected_snapshot_fingerprint": value.selected_snapshot_fingerprint,
        "selected_effective_as_of": None if value.selected_effective_as_of is None else _timestamp(value.selected_effective_as_of),
    }


def _full_payload(value: MarketExtremesAssuranceProjection) -> dict[str, object]:
    return _identity_payload(value) | {
        "projection_id": value.projection_id,
        "selected_regime": None if value.selected_regime is None else value.selected_regime.value,
        "verification_summary": {
            "supplied_candidates": value.verification_summary.supplied_candidates,
            "unique_candidates": value.verification_summary.unique_candidates,
            "duplicate_candidates": value.verification_summary.duplicate_candidates,
            "verified_candidates": value.verification_summary.verified_candidates,
            "pit_eligible_candidates": value.verification_summary.pit_eligible_candidates,
            "rejected_candidates": value.verification_summary.rejected_candidates,
            "future_candidates": value.verification_summary.future_candidates,
        },
    }


def _context_payload(value: MarketExtremesAssuranceContext) -> dict[str, object]:
    return {
        "as_of": _timestamp(value.as_of), "freshness_floor": _timestamp(value.freshness_floor),
        "expected_policy_version": value.expected_policy_version,
        "expected_fingerprint_scheme": value.expected_fingerprint_scheme,
        "expected_entity_id": value.expected_entity_id,
    }


def _reference_payload(value: MarketExtremesCandidateReference) -> dict[str, object]:
    return {
        "reference_id": value.reference_id, "snapshot_id": value.snapshot_id,
        "stored_fingerprint": value.stored_fingerprint,
        "effective_as_of": None if value.effective_as_of is None else _timestamp(value.effective_as_of),
        "reason_codes": tuple(item.value for item in value.reason_codes),
    }


def _is_identifier(value: object) -> bool:
    return isinstance(value, str) and bool(_IDENTIFIER.fullmatch(value))


def _require_identifier(value: str, code: str) -> None:
    if not _is_identifier(value):
        raise MarketExtremesAssuranceError(code)


def _require_text(value: str, code: str) -> None:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise MarketExtremesAssuranceError(code)


def _require_fingerprint(value: str, code: str) -> None:
    if not isinstance(value, str) or not _FINGERPRINT.fullmatch(value):
        raise MarketExtremesAssuranceError(code)


def _require_aware(value: datetime, code: str) -> None:
    if not _is_aware(value):
        raise MarketExtremesAssuranceError(code)


def _is_aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def _utc(value: datetime) -> datetime:
    _require_aware(value, "MARKET_EXTREMES_TIMESTAMP_INVALID")
    return value.astimezone(UTC)


def _timestamp(value: datetime) -> str:
    return _utc(value).isoformat()


__all__ = (
    "MARKET_EXTREMES_ASSURANCE_CONTRACT", "MARKET_EXTREMES_ASSURANCE_FINGERPRINT_SCHEME",
    "MarketExtremesAssuranceCandidate", "MarketExtremesAssuranceContext", "MarketExtremesAssuranceError",
    "MarketExtremesAssuranceProjection", "MarketExtremesAssuranceReason", "MarketExtremesAssuranceState",
    "MarketExtremesAssuranceVerificationSummary", "MarketExtremesCandidateReference",
    "market_extremes_assurance_candidate", "market_extremes_assurance_payload",
    "project_market_extremes_assurance", "serialize_market_extremes_assurance",
)
