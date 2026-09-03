"""Fail-closed Policy Transmission Research Shadow V1 evidence projection.

This module establishes only the retained policy-to-company evidence path.  It
does not interpret that path as a benefit, detriment, ranking, or action.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC
from enum import StrEnum
import hashlib
import json

from app.intelligence.external_intelligence import (
    EvidenceVersion,
    EventType,
    ExposureType,
    PolicyStage,
)
from app.intelligence.long_term_thesis_research_shadow import (
    LongTermCoverageDomain,
    LongTermResearchShadowState,
    LongTermThesisResearchShadow,
)
from app.intelligence.long_term_thesis_review import LongTermThesisFamily


CONTRACT_VERSION = "long-term-policy-transmission-research-shadow/v1"
_PRIMARY_SOURCE_TYPES = frozenset({
    "OFFICIAL", "OFFICIAL_PRIMARY", "GOVERNMENT", "REGULATOR", "EXCHANGE",
})
_POLICY_EVENT_TYPES = frozenset({
    EventType.GOVERNMENT_POLICY, EventType.REGULATORY, EventType.MONETARY_POLICY,
})
_NON_POLICY_STAGES = frozenset({PolicyStage.RUMOUR, PolicyStage.STATEMENT})


class PolicyTransmissionResearchShadowError(ValueError):
    """Raised when an immutable Policy Transmission receipt is malformed."""


class PolicyTransmissionBusinessBranch(StrEnum):
    NON_FINANCIAL_CORPORATE = "NON_FINANCIAL_CORPORATE"
    BANK = "BANK"
    NBFC = "NBFC"
    INSURER = "INSURER"
    STRUCTURALLY_NON_COMPARABLE = "STRUCTURALLY_NON_COMPARABLE"
    UNKNOWN = "UNKNOWN"


class PolicyTransmissionState(StrEnum):
    DATA_INSUFFICIENT = "DATA_INSUFFICIENT"
    EVIDENCE_CONFLICTED = "EVIDENCE_CONFLICTED"
    POLICY_DEFINITION_MISSING = "POLICY_DEFINITION_MISSING"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class PolicyTransmissionReason(StrEnum):
    SOURCE_RECEIPT_UNVERIFIABLE = "SOURCE_RECEIPT_UNVERIFIABLE"
    SOURCE_RECEIPT_TEMPORALLY_INVALID = "SOURCE_RECEIPT_TEMPORALLY_INVALID"
    SOURCE_EVIDENCE_CONFLICTED = "SOURCE_EVIDENCE_CONFLICTED"
    SOURCE_DATA_INSUFFICIENT = "SOURCE_DATA_INSUFFICIENT"
    PRIMARY_POLICY_COVERAGE_LINEAGE_UNVERIFIABLE = "PRIMARY_POLICY_COVERAGE_LINEAGE_UNVERIFIABLE"
    PRIMARY_SOURCE_PROVENANCE_INSUFFICIENT = "PRIMARY_SOURCE_PROVENANCE_INSUFFICIENT"
    POLICY_EVENT_TYPE_UNSUPPORTED = "POLICY_EVENT_TYPE_UNSUPPORTED"
    POLICY_STAGE_INSUFFICIENT = "POLICY_STAGE_INSUFFICIENT"
    POLICY_EFFECTIVE_TIME_UNAVAILABLE = "POLICY_EFFECTIVE_TIME_UNAVAILABLE"
    POLICY_SCOPE_UNAVAILABLE = "POLICY_SCOPE_UNAVAILABLE"
    COMPANY_EXPOSURE_UNAVAILABLE = "COMPANY_EXPOSURE_UNAVAILABLE"
    COMPANY_NOT_APPLICABLE_TO_POLICY_SCOPE = "COMPANY_NOT_APPLICABLE_TO_POLICY_SCOPE"
    EXPOSURE_LINEAGE_CONFLICTED = "EXPOSURE_LINEAGE_CONFLICTED"
    BUSINESS_CLASSIFICATION_UNAVAILABLE = "BUSINESS_CLASSIFICATION_UNAVAILABLE"
    POLICY_DIRECTION_DEFINITION_MISSING = "POLICY_DIRECTION_DEFINITION_MISSING"
    EXPOSURE_TYPE_SEMANTICS_MISSING = "EXPOSURE_TYPE_SEMANTICS_MISSING"
    MATERIALITY_DEFINITION_MISSING = "MATERIALITY_DEFINITION_MISSING"
    TRANSMISSION_LAG_DEFINITION_MISSING = "TRANSMISSION_LAG_DEFINITION_MISSING"
    IMPLEMENTATION_EFFECTIVENESS_DEFINITION_MISSING = "IMPLEMENTATION_EFFECTIVENESS_DEFINITION_MISSING"
    ECONOMIC_SENSITIVITY_DEFINITION_MISSING = "ECONOMIC_SENSITIVITY_DEFINITION_MISSING"
    POLICY_PERSISTENCE_DEFINITION_MISSING = "POLICY_PERSISTENCE_DEFINITION_MISSING"


@dataclass(frozen=True, slots=True)
class PolicyTransmissionResearchShadow:
    """Immutable receipt for an exact primary-policy/exposure evidence path."""

    source_receipt: LongTermThesisResearchShadow
    policy_evidence: EvidenceVersion
    business_branch: PolicyTransmissionBusinessBranch
    state: PolicyTransmissionState
    reasons: tuple[PolicyTransmissionReason, ...]
    policy_event_id: str = field(init=False)
    policy_evidence_id: str = field(init=False)
    policy_evidence_fingerprint: str = field(init=False)
    result_id: str = field(init=False)
    fingerprint: str = field(init=False)
    contract_version: str = CONTRACT_VERSION
    actionability: str = "WATCH_ONLY"
    execution_status: str = "NON_EXECUTABLE"
    research_status: str = "RESEARCH_SHADOW_V1"

    def __post_init__(self) -> None:
        _validate_static(self)
        object.__setattr__(self, "policy_event_id", self.policy_evidence.event.canonical_event_id)
        object.__setattr__(self, "policy_evidence_id", self.policy_evidence.evidence_version_id)
        object.__setattr__(self, "policy_evidence_fingerprint", self.policy_evidence.fingerprint)
        object.__setattr__(self, "result_id", "policy-transmission:" + _hash(_identity(self))[:24])
        object.__setattr__(self, "fingerprint", "sha256:" + _hash(_payload(self)))

    def verify(self) -> None:
        _validate_static(self)
        if self.policy_event_id != self.policy_evidence.event.canonical_event_id:
            raise PolicyTransmissionResearchShadowError("POLICY_TRANSMISSION_EVENT_IDENTITY_MISMATCH")
        if self.policy_evidence_id != self.policy_evidence.evidence_version_id:
            raise PolicyTransmissionResearchShadowError("POLICY_TRANSMISSION_EVIDENCE_IDENTITY_MISMATCH")
        if self.policy_evidence_fingerprint != self.policy_evidence.fingerprint:
            raise PolicyTransmissionResearchShadowError("POLICY_TRANSMISSION_EVIDENCE_FINGERPRINT_MISMATCH")
        if self.result_id != "policy-transmission:" + _hash(_identity(self))[:24]:
            raise PolicyTransmissionResearchShadowError("POLICY_TRANSMISSION_IDENTITY_MISMATCH")
        if self.fingerprint != "sha256:" + _hash(_payload(self)):
            raise PolicyTransmissionResearchShadowError("POLICY_TRANSMISSION_FINGERPRINT_MISMATCH")


def evaluate_policy_transmission_research_shadow(
    source_receipt: LongTermThesisResearchShadow,
    policy_evidence: EvidenceVersion,
    business_branch: PolicyTransmissionBusinessBranch,
) -> PolicyTransmissionResearchShadow:
    """Project canonical provenance only; no policy-benefit interpretation."""
    if not isinstance(source_receipt, LongTermThesisResearchShadow):
        raise PolicyTransmissionResearchShadowError("POLICY_TRANSMISSION_SOURCE_RECEIPT_INVALID")
    if not isinstance(policy_evidence, EvidenceVersion):
        raise PolicyTransmissionResearchShadowError("POLICY_TRANSMISSION_EVIDENCE_INVALID")
    if not isinstance(business_branch, PolicyTransmissionBusinessBranch):
        raise PolicyTransmissionResearchShadowError("POLICY_TRANSMISSION_BRANCH_INVALID")
    try:
        source_receipt.verify()
    except ValueError:
        return _result(source_receipt, policy_evidence, business_branch, PolicyTransmissionState.DATA_INSUFFICIENT, (
            PolicyTransmissionReason.SOURCE_RECEIPT_UNVERIFIABLE,
        ))
    if source_receipt.source_review.family is not LongTermThesisFamily.POLICY_TRANSMISSION:
        raise PolicyTransmissionResearchShadowError("POLICY_TRANSMISSION_SOURCE_FAMILY_INVALID")
    if business_branch in {
        PolicyTransmissionBusinessBranch.UNKNOWN,
        PolicyTransmissionBusinessBranch.STRUCTURALLY_NON_COMPARABLE,
    }:
        return _result(source_receipt, policy_evidence, business_branch, PolicyTransmissionState.NOT_APPLICABLE, (
            PolicyTransmissionReason.BUSINESS_CLASSIFICATION_UNAVAILABLE,
        ))
    if source_receipt.state is LongTermResearchShadowState.CONFLICTED:
        return _result(source_receipt, policy_evidence, business_branch, PolicyTransmissionState.EVIDENCE_CONFLICTED, (
            PolicyTransmissionReason.SOURCE_EVIDENCE_CONFLICTED,
        ))
    if source_receipt.state is LongTermResearchShadowState.TEMPORALLY_INVALID:
        return _result(source_receipt, policy_evidence, business_branch, PolicyTransmissionState.DATA_INSUFFICIENT, (
            PolicyTransmissionReason.SOURCE_RECEIPT_TEMPORALLY_INVALID,
        ))
    if source_receipt.state is not LongTermResearchShadowState.POLICY_UNAVAILABLE:
        return _result(source_receipt, policy_evidence, business_branch, PolicyTransmissionState.DATA_INSUFFICIENT, (
            PolicyTransmissionReason.SOURCE_DATA_INSUFFICIENT,
        ))

    primary_coverage = next(
        item for item in source_receipt.coverage
        if item.domain is LongTermCoverageDomain.PRIMARY_POLICY_EVIDENCE
    )
    if (primary_coverage.reference_id != policy_evidence.evidence_version_id
            or primary_coverage.fingerprint != policy_evidence.fingerprint):
        return _result(source_receipt, policy_evidence, business_branch, PolicyTransmissionState.DATA_INSUFFICIENT, (
            PolicyTransmissionReason.PRIMARY_POLICY_COVERAGE_LINEAGE_UNVERIFIABLE,
        ))

    as_of = source_receipt.source_review.context.as_of.astimezone(UTC)
    evidence = policy_evidence
    if any(value.astimezone(UTC) > as_of for value in (
        evidence.event.first_received_at, evidence.received_at, evidence.published_at, evidence.discovered_at,
    )):
        return _result(source_receipt, evidence, business_branch, PolicyTransmissionState.DATA_INSUFFICIENT, (
            PolicyTransmissionReason.SOURCE_RECEIPT_TEMPORALLY_INVALID,
        ))
    source_type = evidence.primary_source.source_type.strip().upper()
    if (evidence.primary_source.source_type != source_type
            or source_type not in _PRIMARY_SOURCE_TYPES
            or not evidence.primary_source.source_reference):
        return _result(source_receipt, evidence, business_branch, PolicyTransmissionState.DATA_INSUFFICIENT, (
            PolicyTransmissionReason.PRIMARY_SOURCE_PROVENANCE_INSUFFICIENT,
        ))
    if evidence.event.event_type not in _POLICY_EVENT_TYPES:
        return _result(source_receipt, evidence, business_branch, PolicyTransmissionState.DATA_INSUFFICIENT, (
            PolicyTransmissionReason.POLICY_EVENT_TYPE_UNSUPPORTED,
        ))
    if evidence.event.policy_stage in {None, *_NON_POLICY_STAGES}:
        return _result(source_receipt, evidence, business_branch, PolicyTransmissionState.DATA_INSUFFICIENT, (
            PolicyTransmissionReason.POLICY_STAGE_INSUFFICIENT,
        ))
    if evidence.effective_at is None or evidence.effective_at.astimezone(UTC) > as_of:
        return _result(source_receipt, evidence, business_branch, PolicyTransmissionState.DATA_INSUFFICIENT, (
            PolicyTransmissionReason.POLICY_EFFECTIVE_TIME_UNAVAILABLE,
        ))
    if not any(value.strip() for value in (*evidence.affected_sectors, *evidence.affected_industries)):
        return _result(source_receipt, evidence, business_branch, PolicyTransmissionState.DATA_INSUFFICIENT, (
            PolicyTransmissionReason.POLICY_SCOPE_UNAVAILABLE,
        ))
    instrument_id = source_receipt.source_review.canonical_instrument_id
    exact = tuple(item for item in evidence.company_exposures if item.canonical_instrument_id == instrument_id)
    verified = tuple(item for item in exact if item.verification_status == "VERIFIED" and item.exposure_type is not ExposureType.NONE)
    if not exact:
        other_verified = any(
            item.verification_status == "VERIFIED" and item.canonical_instrument_id is not None
            for item in evidence.company_exposures
        )
        return _result(source_receipt, evidence, business_branch,
                       PolicyTransmissionState.NOT_APPLICABLE if other_verified else PolicyTransmissionState.DATA_INSUFFICIENT, (
            PolicyTransmissionReason.COMPANY_NOT_APPLICABLE_TO_POLICY_SCOPE if other_verified
            else PolicyTransmissionReason.COMPANY_EXPOSURE_UNAVAILABLE,
        ))
    if not verified:
        return _result(source_receipt, evidence, business_branch, PolicyTransmissionState.DATA_INSUFFICIENT, (
            PolicyTransmissionReason.COMPANY_EXPOSURE_UNAVAILABLE,
        ))
    if len(verified) != 1:
        return _result(source_receipt, evidence, business_branch, PolicyTransmissionState.EVIDENCE_CONFLICTED, (
            PolicyTransmissionReason.EXPOSURE_LINEAGE_CONFLICTED,
        ))
    return _result(source_receipt, evidence, business_branch, PolicyTransmissionState.POLICY_DEFINITION_MISSING, (
        PolicyTransmissionReason.ECONOMIC_SENSITIVITY_DEFINITION_MISSING,
        PolicyTransmissionReason.EXPOSURE_TYPE_SEMANTICS_MISSING,
        PolicyTransmissionReason.IMPLEMENTATION_EFFECTIVENESS_DEFINITION_MISSING,
        PolicyTransmissionReason.MATERIALITY_DEFINITION_MISSING,
        PolicyTransmissionReason.POLICY_DIRECTION_DEFINITION_MISSING,
        PolicyTransmissionReason.POLICY_PERSISTENCE_DEFINITION_MISSING,
        PolicyTransmissionReason.TRANSMISSION_LAG_DEFINITION_MISSING,
    ))


def policy_transmission_payload(value: PolicyTransmissionResearchShadow) -> dict[str, object]:
    value.verify()
    return _payload(value) | {"fingerprint": value.fingerprint}


def serialize_policy_transmission(value: PolicyTransmissionResearchShadow) -> str:
    return json.dumps(policy_transmission_payload(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _result(source_receipt, evidence, branch, state, reasons) -> PolicyTransmissionResearchShadow:
    return PolicyTransmissionResearchShadow(source_receipt, evidence, branch, state, tuple(sorted(set(reasons), key=lambda value: value.value)))


def _validate_static(value: PolicyTransmissionResearchShadow) -> None:
    if not isinstance(value.source_receipt, LongTermThesisResearchShadow):
        raise PolicyTransmissionResearchShadowError("POLICY_TRANSMISSION_SOURCE_RECEIPT_INVALID")
    if not isinstance(value.policy_evidence, EvidenceVersion):
        raise PolicyTransmissionResearchShadowError("POLICY_TRANSMISSION_EVIDENCE_INVALID")
    if not isinstance(value.business_branch, PolicyTransmissionBusinessBranch):
        raise PolicyTransmissionResearchShadowError("POLICY_TRANSMISSION_BRANCH_INVALID")
    if not isinstance(value.state, PolicyTransmissionState):
        raise PolicyTransmissionResearchShadowError("POLICY_TRANSMISSION_STATE_INVALID")
    if (value.reasons != tuple(sorted(set(value.reasons), key=lambda item: item.value))
            or not value.reasons
            or not all(isinstance(item, PolicyTransmissionReason) for item in value.reasons)):
        raise PolicyTransmissionResearchShadowError("POLICY_TRANSMISSION_REASONS_NONCANONICAL")
    if (value.contract_version != CONTRACT_VERSION
            or (value.actionability, value.execution_status, value.research_status)
            != ("WATCH_ONLY", "NON_EXECUTABLE", "RESEARCH_SHADOW_V1")):
        raise PolicyTransmissionResearchShadowError("POLICY_TRANSMISSION_BOUNDARY_INVALID")
    expected_reasons = {
        PolicyTransmissionState.POLICY_DEFINITION_MISSING: frozenset({
            PolicyTransmissionReason.ECONOMIC_SENSITIVITY_DEFINITION_MISSING,
            PolicyTransmissionReason.EXPOSURE_TYPE_SEMANTICS_MISSING,
            PolicyTransmissionReason.IMPLEMENTATION_EFFECTIVENESS_DEFINITION_MISSING,
            PolicyTransmissionReason.MATERIALITY_DEFINITION_MISSING,
            PolicyTransmissionReason.POLICY_DIRECTION_DEFINITION_MISSING,
            PolicyTransmissionReason.POLICY_PERSISTENCE_DEFINITION_MISSING,
            PolicyTransmissionReason.TRANSMISSION_LAG_DEFINITION_MISSING,
        }),
    }.get(value.state)
    if expected_reasons is not None and frozenset(value.reasons) != expected_reasons:
        raise PolicyTransmissionResearchShadowError("POLICY_TRANSMISSION_STATE_REASON_CONTRADICTION")
    if (value.state is PolicyTransmissionState.EVIDENCE_CONFLICTED
            and frozenset(value.reasons) not in {
                frozenset({PolicyTransmissionReason.SOURCE_EVIDENCE_CONFLICTED}),
                frozenset({PolicyTransmissionReason.EXPOSURE_LINEAGE_CONFLICTED}),
            }):
        raise PolicyTransmissionResearchShadowError("POLICY_TRANSMISSION_STATE_REASON_CONTRADICTION")
    if (value.state is PolicyTransmissionState.NOT_APPLICABLE
            and frozenset(value.reasons) not in {
                frozenset({PolicyTransmissionReason.BUSINESS_CLASSIFICATION_UNAVAILABLE}),
                frozenset({PolicyTransmissionReason.COMPANY_NOT_APPLICABLE_TO_POLICY_SCOPE}),
            }):
        raise PolicyTransmissionResearchShadowError("POLICY_TRANSMISSION_STATE_REASON_CONTRADICTION")
    if (value.state is PolicyTransmissionState.NOT_APPLICABLE
            and value.reasons == (PolicyTransmissionReason.BUSINESS_CLASSIFICATION_UNAVAILABLE,)
            and value.business_branch not in {
                PolicyTransmissionBusinessBranch.UNKNOWN,
                PolicyTransmissionBusinessBranch.STRUCTURALLY_NON_COMPARABLE,
            }):
        raise PolicyTransmissionResearchShadowError("POLICY_TRANSMISSION_STATE_BRANCH_CONTRADICTION")


def _identity(value: PolicyTransmissionResearchShadow) -> dict[str, object]:
    source = value.source_receipt
    return {
        "contract": value.contract_version,
        "family": LongTermThesisFamily.POLICY_TRANSMISSION.value,
        "instrument": source.source_review.canonical_instrument_id,
        "as_of": source.source_review.context.as_of.astimezone(UTC).isoformat(),
        "source_receipt_id": source.receipt_id,
        "source_receipt_fingerprint": source.fingerprint,
        "policy_event_id": value.policy_event_id,
        "policy_evidence_id": value.policy_evidence_id,
        "policy_evidence_fingerprint": value.policy_evidence_fingerprint,
        "business_branch": value.business_branch.value,
    }


def _payload(value: PolicyTransmissionResearchShadow) -> dict[str, object]:
    return _identity(value) | {
        "state": value.state.value,
        "reasons": tuple(item.value for item in value.reasons),
        "result_id": value.result_id,
        "actionability": value.actionability,
        "execution_status": value.execution_status,
        "research_status": value.research_status,
    }


def _hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


__all__ = (
    "CONTRACT_VERSION", "PolicyTransmissionBusinessBranch", "PolicyTransmissionReason",
    "PolicyTransmissionResearchShadow", "PolicyTransmissionResearchShadowError",
    "PolicyTransmissionState", "evaluate_policy_transmission_research_shadow",
    "policy_transmission_payload", "serialize_policy_transmission",
)
