"""PIT-safe assurance over an injected, completed Core comparison.

This Post-V1 boundary does not calculate a comparison or inspect a portfolio.
It preserves only whether supplied Core-comparison provenance is trustworthy
enough to be a research observation.  It deliberately has no action surface.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
import hashlib
import json
import re


FAST_ROTATION_ASSURANCE_CONTRACT = "fast-rotation-comparison-assurance/v1"
FAST_ROTATION_ASSURANCE_FINGERPRINT_SCHEME = "fast-rotation-comparison/sha256/v1"
_ID = re.compile(r"[A-Za-z0-9._:-]+")
_FINGERPRINT = re.compile(r"sha256:[0-9a-f]{64}")


class FastRotationAssuranceError(ValueError):
    """Raised for malformed or tampered immutable comparison evidence."""


class FastRotationAlternativeKind(StrEnum):
    INCUMBENT = "INCUMBENT"
    CASH = "CASH"


class FastRotationEvidenceDomain(StrEnum):
    COMMON_SCORE_SCALE = "COMMON_SCORE_SCALE"
    RISK_REWARD = "RISK_REWARD"
    FRICTION_LIQUIDITY_TRADABILITY = "FRICTION_LIQUIDITY_TRADABILITY"
    CORRELATION_CONCENTRATION = "CORRELATION_CONCENTRATION"
    BUCKET_ASSIGNMENT = "BUCKET_ASSIGNMENT"
    PERSISTENCE_CHURN = "PERSISTENCE_CHURN"
    INVALIDATION_CONTEXT = "INVALIDATION_CONTEXT"


class FastRotationEvidenceState(StrEnum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    STALE = "STALE"
    CONFLICTED = "CONFLICTED"
    NON_COMPARABLE = "NON_COMPARABLE"


class FastRotationObservationState(StrEnum):
    CORE_COMPARISON_OBSERVED = "CORE_COMPARISON_OBSERVED"
    DATA_INSUFFICIENT = "DATA_INSUFFICIENT"
    CONFLICTED = "CONFLICTED"
    TEMPORALLY_INVALID = "TEMPORALLY_INVALID"
    UNVERIFIABLE = "UNVERIFIABLE"


class FastRotationPolicyReadiness(StrEnum):
    POLICY_PARAMETER_UNAVAILABLE = "POLICY_PARAMETER_UNAVAILABLE"
    NOT_EVALUATED = "NOT_EVALUATED"


class FastRotationReason(StrEnum):
    SOURCE_COMPARISON_UNVERIFIABLE = "SOURCE_COMPARISON_UNVERIFIABLE"
    SOURCE_COMPARISON_AFTER_AS_OF = "SOURCE_COMPARISON_AFTER_AS_OF"
    EVIDENCE_AFTER_AS_OF = "EVIDENCE_AFTER_AS_OF"
    EVIDENCE_CONFLICTED = "EVIDENCE_CONFLICTED"
    EVIDENCE_UNAVAILABLE = "EVIDENCE_UNAVAILABLE"
    EVIDENCE_STALE = "EVIDENCE_STALE"
    EVIDENCE_NON_COMPARABLE = "EVIDENCE_NON_COMPARABLE"
    BUCKET_POLICY_UNAVAILABLE = "BUCKET_POLICY_UNAVAILABLE"
    CROSS_BUCKET_POLICY_UNAVAILABLE = "CROSS_BUCKET_POLICY_UNAVAILABLE"
    IMPROVEMENT_HURDLE_UNAVAILABLE = "IMPROVEMENT_HURDLE_UNAVAILABLE"
    RISK_REWARD_POLICY_UNAVAILABLE = "RISK_REWARD_POLICY_UNAVAILABLE"
    FRICTION_TAX_POLICY_UNAVAILABLE = "FRICTION_TAX_POLICY_UNAVAILABLE"
    CORRELATION_CONCENTRATION_POLICY_UNAVAILABLE = "CORRELATION_CONCENTRATION_POLICY_UNAVAILABLE"
    PERSISTENCE_CHURN_POLICY_UNAVAILABLE = "PERSISTENCE_CHURN_POLICY_UNAVAILABLE"


_POLICY_GAPS = tuple(sorted((
    FastRotationReason.BUCKET_POLICY_UNAVAILABLE,
    FastRotationReason.CROSS_BUCKET_POLICY_UNAVAILABLE,
    FastRotationReason.IMPROVEMENT_HURDLE_UNAVAILABLE,
    FastRotationReason.RISK_REWARD_POLICY_UNAVAILABLE,
    FastRotationReason.FRICTION_TAX_POLICY_UNAVAILABLE,
    FastRotationReason.CORRELATION_CONCENTRATION_POLICY_UNAVAILABLE,
    FastRotationReason.PERSISTENCE_CHURN_POLICY_UNAVAILABLE,
), key=lambda item: item.value))


@dataclass(frozen=True, slots=True)
class FastRotationLineageReference:
    """One exact, immutable upstream evidence reference; it carries no value."""

    reference_id: str
    fingerprint: str
    available_at: datetime

    def __post_init__(self) -> None:
        _require_id(self.reference_id, "FAST_ROTATION_LINEAGE_ID_INVALID")
        _require_fingerprint(self.fingerprint, "FAST_ROTATION_LINEAGE_FINGERPRINT_INVALID")
        _require_aware(self.available_at, "FAST_ROTATION_LINEAGE_TIMESTAMP_INVALID")


@dataclass(frozen=True, slots=True)
class FastRotationDomainEvidence:
    domain: FastRotationEvidenceDomain
    state: FastRotationEvidenceState
    source_id: str
    source_fingerprint: str
    available_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.domain, FastRotationEvidenceDomain) or not isinstance(self.state, FastRotationEvidenceState):
            raise FastRotationAssuranceError("FAST_ROTATION_DOMAIN_STATE_INVALID")
        _require_id(self.source_id, "FAST_ROTATION_DOMAIN_SOURCE_ID_INVALID")
        _require_fingerprint(self.source_fingerprint, "FAST_ROTATION_DOMAIN_SOURCE_FINGERPRINT_INVALID")
        _require_aware(self.available_at, "FAST_ROTATION_DOMAIN_TIMESTAMP_INVALID")


@dataclass(frozen=True, slots=True)
class FastRotationComparisonCandidate:
    """An untrusted caller-supplied observation of one completed comparison."""

    source_evaluation_id: str
    source_comparison_id: str
    source_configuration_version: str
    source_content_fingerprint: str
    source_as_of: datetime
    source_available_at: datetime
    challenger_instrument_id: str
    alternative_kind: FastRotationAlternativeKind
    alternative_identity: str
    challenger_lineage: tuple[FastRotationLineageReference, ...]
    alternative_lineage: tuple[FastRotationLineageReference, ...]
    domain_evidence: tuple[FastRotationDomainEvidence, ...]
    stored_fingerprint: str
    fingerprint_scheme: str = FAST_ROTATION_ASSURANCE_FINGERPRINT_SCHEME

    def __post_init__(self) -> None:
        _require_id(self.source_evaluation_id, "FAST_ROTATION_SOURCE_EVALUATION_ID_INVALID")
        _require_id(self.source_comparison_id, "FAST_ROTATION_SOURCE_COMPARISON_ID_INVALID")
        _require_text(self.source_configuration_version, "FAST_ROTATION_SOURCE_VERSION_INVALID")
        _require_fingerprint(self.source_content_fingerprint, "FAST_ROTATION_SOURCE_FINGERPRINT_INVALID")
        _require_aware(self.source_as_of, "FAST_ROTATION_SOURCE_TIMESTAMP_INVALID")
        _require_aware(self.source_available_at, "FAST_ROTATION_SOURCE_TIMESTAMP_INVALID")
        _require_id(self.challenger_instrument_id, "FAST_ROTATION_CHALLENGER_ID_INVALID")
        if not isinstance(self.alternative_kind, FastRotationAlternativeKind):
            raise FastRotationAssuranceError("FAST_ROTATION_ALTERNATIVE_KIND_INVALID")
        _require_id(self.alternative_identity, "FAST_ROTATION_ALTERNATIVE_ID_INVALID")
        if self.alternative_kind is FastRotationAlternativeKind.CASH:
            if self.alternative_identity != "CASH":
                raise FastRotationAssuranceError("FAST_ROTATION_CASH_IDENTITY_INVALID")
        elif self.alternative_identity == "CASH" or self.alternative_identity == self.challenger_instrument_id:
            raise FastRotationAssuranceError("FAST_ROTATION_INCUMBENT_IDENTITY_INVALID")
        _require_text(self.fingerprint_scheme, "FAST_ROTATION_FINGERPRINT_SCHEME_INVALID")
        _require_fingerprint(self.stored_fingerprint, "FAST_ROTATION_STORED_FINGERPRINT_INVALID")
        _validate_lineage(self.challenger_lineage, "FAST_ROTATION_CHALLENGER_LINEAGE")
        _validate_lineage(self.alternative_lineage, "FAST_ROTATION_ALTERNATIVE_LINEAGE")
        _validate_domains(self.domain_evidence)


def fast_rotation_comparison_candidate(
    *,
    source_evaluation_id: str,
    source_comparison_id: str,
    source_configuration_version: str,
    source_content_fingerprint: str,
    source_as_of: datetime,
    source_available_at: datetime,
    challenger_instrument_id: str,
    alternative_kind: FastRotationAlternativeKind,
    alternative_identity: str,
    challenger_lineage: tuple[FastRotationLineageReference, ...],
    alternative_lineage: tuple[FastRotationLineageReference, ...],
    domain_evidence: tuple[FastRotationDomainEvidence, ...],
    fingerprint_scheme: str = FAST_ROTATION_ASSURANCE_FINGERPRINT_SCHEME,
) -> FastRotationComparisonCandidate:
    """Construct a canonical candidate; duplicate/conflicting input is rejected."""
    candidate = FastRotationComparisonCandidate(
        source_evaluation_id, source_comparison_id, source_configuration_version, source_content_fingerprint,
        _utc(source_as_of), _utc(source_available_at), challenger_instrument_id, alternative_kind,
        alternative_identity, _canonical_lineage(challenger_lineage, "FAST_ROTATION_CHALLENGER_LINEAGE"),
        _canonical_lineage(alternative_lineage, "FAST_ROTATION_ALTERNATIVE_LINEAGE"),
        _canonical_domains(domain_evidence), "sha256:" + "0" * 64, fingerprint_scheme,
    )
    return FastRotationComparisonCandidate(**{**_candidate_values(candidate), "stored_fingerprint": _candidate_fingerprint(candidate)})


@dataclass(frozen=True, slots=True)
class FastRotationAssuranceContext:
    as_of: datetime
    expected_configuration_version: str
    expected_fingerprint_scheme: str = FAST_ROTATION_ASSURANCE_FINGERPRINT_SCHEME

    def __post_init__(self) -> None:
        _require_aware(self.as_of, "FAST_ROTATION_CONTEXT_TIMESTAMP_INVALID")
        _require_text(self.expected_configuration_version, "FAST_ROTATION_CONTEXT_VERSION_INVALID")
        _require_text(self.expected_fingerprint_scheme, "FAST_ROTATION_CONTEXT_FINGERPRINT_SCHEME_INVALID")


@dataclass(frozen=True, slots=True)
class FastRotationComparisonAssurance:
    context: FastRotationAssuranceContext
    observation_state: FastRotationObservationState
    policy_readiness: FastRotationPolicyReadiness
    challenger_instrument_id: str | None
    alternative_kind: FastRotationAlternativeKind | None
    alternative_identity: str | None
    source_evaluation_id: str | None
    source_comparison_id: str | None
    source_configuration_version: str | None
    source_content_fingerprint: str | None
    source_as_of: datetime | None
    source_lineage: tuple[FastRotationLineageReference, ...]
    domain_evidence: tuple[FastRotationDomainEvidence, ...]
    reason_codes: tuple[FastRotationReason, ...]
    contract_version: str = FAST_ROTATION_ASSURANCE_CONTRACT
    assurance_id: str = field(init=False)
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        _validate_assurance(self)
        object.__setattr__(self, "assurance_id", "fast-rotation-assurance:" + _hash(_identity_payload(self))[:24])
        object.__setattr__(self, "fingerprint", "sha256:" + _hash(_payload(self)))

    def verify(self) -> None:
        _validate_assurance(self)
        if self.assurance_id != "fast-rotation-assurance:" + _hash(_identity_payload(self))[:24]:
            raise FastRotationAssuranceError("FAST_ROTATION_ASSURANCE_IDENTITY_MISMATCH")
        if self.fingerprint != "sha256:" + _hash(_payload(self)):
            raise FastRotationAssuranceError("FAST_ROTATION_ASSURANCE_FINGERPRINT_MISMATCH")


def assess_fast_rotation_comparison(
    context: FastRotationAssuranceContext,
    candidate: FastRotationComparisonCandidate,
) -> FastRotationComparisonAssurance:
    """Verify a single injected source observation without any I/O or policy choice."""
    if not isinstance(context, FastRotationAssuranceContext) or not isinstance(candidate, FastRotationComparisonCandidate):
        raise FastRotationAssuranceError("FAST_ROTATION_ASSURANCE_INPUT_TYPE_INVALID")
    reasons = _verify_candidate(context, candidate)
    if FastRotationReason.SOURCE_COMPARISON_UNVERIFIABLE in reasons:
        return _assurance(context, FastRotationObservationState.UNVERIFIABLE, candidate, reasons)
    if any(value in reasons for value in (FastRotationReason.SOURCE_COMPARISON_AFTER_AS_OF, FastRotationReason.EVIDENCE_AFTER_AS_OF)):
        return _assurance(context, FastRotationObservationState.TEMPORALLY_INVALID, candidate, reasons)
    if FastRotationReason.EVIDENCE_CONFLICTED in reasons:
        return _assurance(context, FastRotationObservationState.CONFLICTED, candidate, reasons)
    if reasons:
        return _assurance(context, FastRotationObservationState.DATA_INSUFFICIENT, candidate, reasons)
    return _assurance(context, FastRotationObservationState.CORE_COMPARISON_OBSERVED, candidate, ())


def fast_rotation_assurance_payload(value: FastRotationComparisonAssurance) -> dict[str, object]:
    if not isinstance(value, FastRotationComparisonAssurance):
        raise FastRotationAssuranceError("FAST_ROTATION_ASSURANCE_REQUIRED")
    value.verify()
    return _payload(value) | {"fingerprint": value.fingerprint}


def serialize_fast_rotation_assurance(value: FastRotationComparisonAssurance) -> str:
    return json.dumps(fast_rotation_assurance_payload(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _verify_candidate(context: FastRotationAssuranceContext, candidate: FastRotationComparisonCandidate) -> tuple[FastRotationReason, ...]:
    if candidate.fingerprint_scheme != context.expected_fingerprint_scheme or candidate.source_configuration_version != context.expected_configuration_version or candidate.stored_fingerprint != _candidate_fingerprint(candidate):
        return (FastRotationReason.SOURCE_COMPARISON_UNVERIFIABLE,)
    all_times = (candidate.source_as_of, candidate.source_available_at, *(item.available_at for item in candidate.challenger_lineage), *(item.available_at for item in candidate.alternative_lineage), *(item.available_at for item in candidate.domain_evidence))
    if candidate.source_as_of > context.as_of or candidate.source_available_at > context.as_of:
        return (FastRotationReason.SOURCE_COMPARISON_AFTER_AS_OF,)
    if any(value > context.as_of for value in all_times):
        return (FastRotationReason.EVIDENCE_AFTER_AS_OF,)
    states = {item.state for item in candidate.domain_evidence}
    if FastRotationEvidenceState.CONFLICTED in states:
        return (FastRotationReason.EVIDENCE_CONFLICTED,)
    reasons: list[FastRotationReason] = []
    if FastRotationEvidenceState.UNAVAILABLE in states:
        reasons.append(FastRotationReason.EVIDENCE_UNAVAILABLE)
    if FastRotationEvidenceState.STALE in states:
        reasons.append(FastRotationReason.EVIDENCE_STALE)
    if FastRotationEvidenceState.NON_COMPARABLE in states:
        reasons.append(FastRotationReason.EVIDENCE_NON_COMPARABLE)
    return tuple(reasons)


def _assurance(context: FastRotationAssuranceContext, state: FastRotationObservationState, candidate: FastRotationComparisonCandidate, reasons: tuple[FastRotationReason, ...]) -> FastRotationComparisonAssurance:
    policy = FastRotationPolicyReadiness.POLICY_PARAMETER_UNAVAILABLE if state is FastRotationObservationState.CORE_COMPARISON_OBSERVED else FastRotationPolicyReadiness.NOT_EVALUATED
    return FastRotationComparisonAssurance(
        context, state, policy, candidate.challenger_instrument_id, candidate.alternative_kind,
        candidate.alternative_identity, candidate.source_evaluation_id, candidate.source_comparison_id,
        candidate.source_configuration_version, candidate.source_content_fingerprint, candidate.source_as_of,
        _canonical_lineage((*candidate.challenger_lineage, *candidate.alternative_lineage), "FAST_ROTATION_SOURCE_LINEAGE"),
        candidate.domain_evidence,
        tuple(sorted(set((*reasons, *(_POLICY_GAPS if policy is FastRotationPolicyReadiness.POLICY_PARAMETER_UNAVAILABLE else ()))), key=lambda item: item.value)),
    )


def _validate_assurance(value: FastRotationComparisonAssurance) -> None:
    if value.contract_version != FAST_ROTATION_ASSURANCE_CONTRACT or not isinstance(value.context, FastRotationAssuranceContext):
        raise FastRotationAssuranceError("FAST_ROTATION_ASSURANCE_CONTRACT_INVALID")
    if not isinstance(value.observation_state, FastRotationObservationState) or not isinstance(value.policy_readiness, FastRotationPolicyReadiness):
        raise FastRotationAssuranceError("FAST_ROTATION_ASSURANCE_STATE_INVALID")
    if not all(isinstance(item, FastRotationReason) for item in value.reason_codes):
        raise FastRotationAssuranceError("FAST_ROTATION_ASSURANCE_REASON_INVALID")
    if value.reason_codes != tuple(sorted(set(value.reason_codes), key=lambda item: item.value)):
        raise FastRotationAssuranceError("FAST_ROTATION_ASSURANCE_REASONS_NONCANONICAL")
    usable = value.observation_state is FastRotationObservationState.CORE_COMPARISON_OBSERVED
    selected = (value.challenger_instrument_id, value.alternative_kind, value.alternative_identity, value.source_evaluation_id, value.source_comparison_id, value.source_configuration_version, value.source_content_fingerprint, value.source_as_of)
    if usable:
        if any(item is None for item in selected) or value.policy_readiness is not FastRotationPolicyReadiness.POLICY_PARAMETER_UNAVAILABLE:
            raise FastRotationAssuranceError("FAST_ROTATION_ASSURANCE_OBSERVED_SELECTION_INVALID")
        if value.reason_codes != _POLICY_GAPS:
            raise FastRotationAssuranceError("FAST_ROTATION_ASSURANCE_POLICY_GAPS_REQUIRED")
    else:
        if value.policy_readiness is not FastRotationPolicyReadiness.NOT_EVALUATED:
            raise FastRotationAssuranceError("FAST_ROTATION_ASSURANCE_POLICY_READINESS_CONTRADICTION")
        if any(item in _POLICY_GAPS for item in value.reason_codes):
            raise FastRotationAssuranceError("FAST_ROTATION_ASSURANCE_POLICY_GAPS_CONTRADICTION")
    if value.source_lineage != _canonical_lineage(value.source_lineage, "FAST_ROTATION_SOURCE_LINEAGE"):
        raise FastRotationAssuranceError("FAST_ROTATION_ASSURANCE_LINEAGE_NONCANONICAL")
    _validate_domains(value.domain_evidence)


def _candidate_values(value: FastRotationComparisonCandidate) -> dict[str, object]:
    return {name: getattr(value, name) for name in value.__dataclass_fields__}


def _candidate_fingerprint(value: FastRotationComparisonCandidate) -> str:
    return "sha256:" + _hash(_candidate_payload(value))


def _candidate_payload(value: FastRotationComparisonCandidate) -> dict[str, object]:
    return {
        "source_evaluation_id": value.source_evaluation_id, "source_comparison_id": value.source_comparison_id,
        "source_configuration_version": value.source_configuration_version, "source_content_fingerprint": value.source_content_fingerprint,
        "source_as_of": _timestamp(value.source_as_of), "source_available_at": _timestamp(value.source_available_at),
        "challenger_instrument_id": value.challenger_instrument_id, "alternative_kind": value.alternative_kind.value,
        "alternative_identity": value.alternative_identity, "challenger_lineage": tuple(_lineage_payload(item) for item in value.challenger_lineage),
        "alternative_lineage": tuple(_lineage_payload(item) for item in value.alternative_lineage),
        "domain_evidence": tuple(_domain_payload(item) for item in value.domain_evidence), "fingerprint_scheme": value.fingerprint_scheme,
    }


def _identity_payload(value: FastRotationComparisonAssurance) -> dict[str, object]:
    return {
        "contract_version": value.contract_version, "as_of": _timestamp(value.context.as_of),
        "source_evaluation_id": value.source_evaluation_id, "source_comparison_id": value.source_comparison_id,
        "source_configuration_version": value.source_configuration_version,
        "source_content_fingerprint": value.source_content_fingerprint, "challenger_instrument_id": value.challenger_instrument_id,
        "alternative_kind": None if value.alternative_kind is None else value.alternative_kind.value,
        "alternative_identity": value.alternative_identity, "state": value.observation_state.value,
    }


def _payload(value: FastRotationComparisonAssurance) -> dict[str, object]:
    return _identity_payload(value) | {
        "context": {"expected_configuration_version": value.context.expected_configuration_version, "expected_fingerprint_scheme": value.context.expected_fingerprint_scheme},
        "policy_readiness": value.policy_readiness.value, "source_as_of": None if value.source_as_of is None else _timestamp(value.source_as_of),
        "source_lineage": tuple(_lineage_payload(item) for item in value.source_lineage),
        "domain_evidence": tuple(_domain_payload(item) for item in value.domain_evidence),
        "reason_codes": tuple(item.value for item in value.reason_codes), "assurance_id": value.assurance_id,
    }


def _lineage_payload(value: FastRotationLineageReference) -> dict[str, str]:
    return {"reference_id": value.reference_id, "fingerprint": value.fingerprint, "available_at": _timestamp(value.available_at)}


def _domain_payload(value: FastRotationDomainEvidence) -> dict[str, str]:
    return {"domain": value.domain.value, "state": value.state.value, "source_id": value.source_id, "source_fingerprint": value.source_fingerprint, "available_at": _timestamp(value.available_at)}


def _canonical_lineage(values: tuple[FastRotationLineageReference, ...], code: str) -> tuple[FastRotationLineageReference, ...]:
    _validate_lineage(values, code)
    ordered = tuple(sorted(values, key=lambda item: (item.reference_id, item.fingerprint, _timestamp(item.available_at))))
    if len({item.reference_id for item in ordered}) != len(ordered):
        raise FastRotationAssuranceError(code + "_DUPLICATE")
    return ordered


def _validate_lineage(values: tuple[FastRotationLineageReference, ...], code: str) -> None:
    if not values or not all(isinstance(item, FastRotationLineageReference) for item in values):
        raise FastRotationAssuranceError(code + "_REQUIRED")
    if len({item.reference_id for item in values}) != len(values):
        raise FastRotationAssuranceError(code + "_DUPLICATE")


def _canonical_domains(values: tuple[FastRotationDomainEvidence, ...]) -> tuple[FastRotationDomainEvidence, ...]:
    _validate_domain_coverage(values)
    return tuple(sorted(values, key=lambda item: item.domain.value))


def _validate_domains(values: tuple[FastRotationDomainEvidence, ...]) -> None:
    _validate_domain_coverage(values)
    if tuple(values) != tuple(sorted(values, key=lambda item: item.domain.value)):
        raise FastRotationAssuranceError("FAST_ROTATION_DOMAIN_ORDER_NONCANONICAL")


def _validate_domain_coverage(values: tuple[FastRotationDomainEvidence, ...]) -> None:
    required = frozenset(FastRotationEvidenceDomain)
    if not all(isinstance(item, FastRotationDomainEvidence) for item in values) or frozenset(item.domain for item in values) != required or len(values) != len(required):
        raise FastRotationAssuranceError("FAST_ROTATION_DOMAIN_COVERAGE_INVALID")


def _require_id(value: object, code: str) -> None:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise FastRotationAssuranceError(code)


def _require_text(value: object, code: str) -> None:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise FastRotationAssuranceError(code)


def _require_fingerprint(value: object, code: str) -> None:
    if not isinstance(value, str) or not _FINGERPRINT.fullmatch(value):
        raise FastRotationAssuranceError(code)


def _require_aware(value: object, code: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise FastRotationAssuranceError(code)


def _utc(value: datetime) -> datetime:
    _require_aware(value, "FAST_ROTATION_TIMESTAMP_INVALID")
    return value.astimezone(UTC)


def _timestamp(value: datetime) -> str:
    return _utc(value).isoformat()


def _hash(value: dict[str, object]) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()


__all__ = (
    "FAST_ROTATION_ASSURANCE_CONTRACT", "FAST_ROTATION_ASSURANCE_FINGERPRINT_SCHEME",
    "FastRotationAlternativeKind", "FastRotationAssuranceContext", "FastRotationAssuranceError",
    "FastRotationComparisonAssurance", "FastRotationComparisonCandidate", "FastRotationDomainEvidence",
    "FastRotationEvidenceDomain", "FastRotationEvidenceState", "FastRotationLineageReference",
    "FastRotationObservationState", "FastRotationPolicyReadiness", "FastRotationReason",
    "assess_fast_rotation_comparison", "fast_rotation_assurance_payload", "fast_rotation_comparison_candidate",
    "serialize_fast_rotation_assurance",
)
