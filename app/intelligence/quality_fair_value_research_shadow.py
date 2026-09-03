"""Read-only Quality-at-Fair-Value Research Shadow V1 state propagation."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC
from enum import StrEnum
import hashlib
import json

from app.intelligence.long_term_thesis_research_shadow import (
    LongTermResearchShadowState,
    LongTermThesisResearchShadow,
)
from app.intelligence.long_term_thesis_review import LongTermThesisFamily

CONTRACT_VERSION = "quality-fair-value-research-shadow/v1"


class QualityFairValueResearchShadowError(ValueError):
    pass


class QualityFairValueBusinessBranch(StrEnum):
    NON_FINANCIAL_CORPORATE = "NON_FINANCIAL_CORPORATE"
    BANK = "BANK"
    NBFC = "NBFC"
    INSURER = "INSURER"
    STRUCTURALLY_NON_COMPARABLE = "STRUCTURALLY_NON_COMPARABLE"
    UNKNOWN = "UNKNOWN"


class QualityFairValueState(StrEnum):
    SHADOW_CANDIDATE = "SHADOW_CANDIDATE"
    SHADOW_NOT_QUALIFIED = "SHADOW_NOT_QUALIFIED"
    DATA_INSUFFICIENT = "DATA_INSUFFICIENT"
    EVIDENCE_CONFLICTED = "EVIDENCE_CONFLICTED"
    POLICY_PARAMETER_UNAVAILABLE = "POLICY_PARAMETER_UNAVAILABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class QualityFairValueReason(StrEnum):
    SOURCE_RECEIPT_UNVERIFIABLE = "SOURCE_RECEIPT_UNVERIFIABLE"
    SOURCE_RECEIPT_TEMPORALLY_INVALID = "SOURCE_RECEIPT_TEMPORALLY_INVALID"
    SOURCE_EVIDENCE_CONFLICTED = "SOURCE_EVIDENCE_CONFLICTED"
    SOURCE_DATA_INSUFFICIENT = "SOURCE_DATA_INSUFFICIENT"
    FINANCIAL_SECTOR_POLICY_UNAVAILABLE = "FINANCIAL_SECTOR_POLICY_UNAVAILABLE"
    BUSINESS_CLASSIFICATION_UNAVAILABLE = "BUSINESS_CLASSIFICATION_UNAVAILABLE"
    QUALITY_PARAMETER_UNAVAILABLE = "QUALITY_PARAMETER_UNAVAILABLE"
    VALUATION_COMPARABILITY_UNAVAILABLE = "VALUATION_COMPARABILITY_UNAVAILABLE"
    CASH_CONVERSION_POLICY_UNAVAILABLE = "CASH_CONVERSION_POLICY_UNAVAILABLE"
    LIFECYCLE_CALIBRATION_UNAVAILABLE = "LIFECYCLE_CALIBRATION_UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class QualityFairValueResearchShadow:
    source_receipt: LongTermThesisResearchShadow
    business_branch: QualityFairValueBusinessBranch
    state: QualityFairValueState
    reasons: tuple[QualityFairValueReason, ...]
    result_id: str = field(init=False)
    fingerprint: str = field(init=False)
    contract_version: str = CONTRACT_VERSION
    actionability: str = "WATCH_ONLY"
    execution_status: str = "NON_EXECUTABLE"
    research_status: str = "RESEARCH_SHADOW_V1"

    def __post_init__(self) -> None:
        _validate(self)
        object.__setattr__(self, "result_id", "quality-fair-value:" + _hash(_identity(self))[:24])
        object.__setattr__(self, "fingerprint", "sha256:" + _hash(_payload(self)))

    def verify(self) -> None:
        _validate(self)
        if self.result_id != "quality-fair-value:" + _hash(_identity(self))[:24]:
            raise QualityFairValueResearchShadowError("QUALITY_FAIR_VALUE_IDENTITY_MISMATCH")
        if self.fingerprint != "sha256:" + _hash(_payload(self)):
            raise QualityFairValueResearchShadowError("QUALITY_FAIR_VALUE_FINGERPRINT_MISMATCH")


def evaluate_quality_fair_value_research_shadow(
    source_receipt: LongTermThesisResearchShadow,
    business_branch: QualityFairValueBusinessBranch,
) -> QualityFairValueResearchShadow:
    if not isinstance(source_receipt, LongTermThesisResearchShadow) or not isinstance(business_branch, QualityFairValueBusinessBranch):
        raise QualityFairValueResearchShadowError("QUALITY_FAIR_VALUE_INPUT_INVALID")
    try:
        source_receipt.verify()
    except ValueError:
        return _result(source_receipt, business_branch, QualityFairValueState.DATA_INSUFFICIENT, (QualityFairValueReason.SOURCE_RECEIPT_UNVERIFIABLE,))
    if source_receipt.source_review.family is not LongTermThesisFamily.QUALITY_FAIR_VALUE:
        raise QualityFairValueResearchShadowError("QUALITY_FAIR_VALUE_SOURCE_FAMILY_INVALID")
    if business_branch is not QualityFairValueBusinessBranch.NON_FINANCIAL_CORPORATE:
        reason = QualityFairValueReason.BUSINESS_CLASSIFICATION_UNAVAILABLE if business_branch in {QualityFairValueBusinessBranch.UNKNOWN, QualityFairValueBusinessBranch.STRUCTURALLY_NON_COMPARABLE} else QualityFairValueReason.FINANCIAL_SECTOR_POLICY_UNAVAILABLE
        return _result(source_receipt, business_branch, QualityFairValueState.NOT_APPLICABLE, (reason,))
    if source_receipt.state is LongTermResearchShadowState.CONFLICTED:
        return _result(source_receipt, business_branch, QualityFairValueState.EVIDENCE_CONFLICTED, (QualityFairValueReason.SOURCE_EVIDENCE_CONFLICTED,))
    if source_receipt.state is LongTermResearchShadowState.TEMPORALLY_INVALID:
        return _result(source_receipt, business_branch, QualityFairValueState.DATA_INSUFFICIENT, (QualityFairValueReason.SOURCE_RECEIPT_TEMPORALLY_INVALID,))
    if source_receipt.state in {LongTermResearchShadowState.DATA_INSUFFICIENT, LongTermResearchShadowState.UNVERIFIABLE}:
        return _result(source_receipt, business_branch, QualityFairValueState.DATA_INSUFFICIENT, (QualityFairValueReason.SOURCE_DATA_INSUFFICIENT,))
    return _result(source_receipt, business_branch, QualityFairValueState.POLICY_PARAMETER_UNAVAILABLE, (
        QualityFairValueReason.CASH_CONVERSION_POLICY_UNAVAILABLE,
        QualityFairValueReason.LIFECYCLE_CALIBRATION_UNAVAILABLE,
        QualityFairValueReason.QUALITY_PARAMETER_UNAVAILABLE,
        QualityFairValueReason.VALUATION_COMPARABILITY_UNAVAILABLE,
    ))


def quality_fair_value_payload(value: QualityFairValueResearchShadow) -> dict[str, object]:
    value.verify()
    return _payload(value) | {"fingerprint": value.fingerprint}


def serialize_quality_fair_value(value: QualityFairValueResearchShadow) -> str:
    return json.dumps(quality_fair_value_payload(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _result(source: LongTermThesisResearchShadow, branch: QualityFairValueBusinessBranch, state: QualityFairValueState, reasons: tuple[QualityFairValueReason, ...]) -> QualityFairValueResearchShadow:
    return QualityFairValueResearchShadow(source, branch, state, tuple(sorted(set(reasons), key=lambda value: value.value)))


def _validate(value: QualityFairValueResearchShadow) -> None:
    if not isinstance(value.source_receipt, LongTermThesisResearchShadow) or not isinstance(value.business_branch, QualityFairValueBusinessBranch) or not isinstance(value.state, QualityFairValueState):
        raise QualityFairValueResearchShadowError("QUALITY_FAIR_VALUE_CONTRACT_INVALID")
    if value.reasons != tuple(sorted(set(value.reasons), key=lambda item: item.value)) or not all(isinstance(item, QualityFairValueReason) for item in value.reasons):
        raise QualityFairValueResearchShadowError("QUALITY_FAIR_VALUE_REASONS_NONCANONICAL")
    if value.contract_version != CONTRACT_VERSION or (value.actionability, value.execution_status, value.research_status) != ("WATCH_ONLY", "NON_EXECUTABLE", "RESEARCH_SHADOW_V1"):
        raise QualityFairValueResearchShadowError("QUALITY_FAIR_VALUE_BOUNDARY_INVALID")
    if value.state in {QualityFairValueState.SHADOW_CANDIDATE, QualityFairValueState.SHADOW_NOT_QUALIFIED}:
        raise QualityFairValueResearchShadowError("QUALITY_FAIR_VALUE_V1_POSITIVE_STATE_FORBIDDEN")
    if value.state is QualityFairValueState.NOT_APPLICABLE and value.business_branch is QualityFairValueBusinessBranch.NON_FINANCIAL_CORPORATE:
        raise QualityFairValueResearchShadowError("QUALITY_FAIR_VALUE_BRANCH_STATE_CONTRADICTION")


def _identity(value: QualityFairValueResearchShadow) -> dict[str, str]:
    source = value.source_receipt
    return {"contract": value.contract_version, "result_family": "LONG_TERM_QUALITY_FAIR_VALUE", "instrument": source.source_review.canonical_instrument_id, "as_of": source.source_review.context.as_of.astimezone(UTC).isoformat(), "receipt_id": source.receipt_id, "receipt_fingerprint": source.fingerprint, "branch": value.business_branch.value}


def _payload(value: QualityFairValueResearchShadow) -> dict[str, object]:
    return _identity(value) | {"state": value.state.value, "reasons": tuple(reason.value for reason in value.reasons), "result_id": value.result_id, "actionability": value.actionability, "execution_status": value.execution_status, "research_status": value.research_status}


def _hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()
