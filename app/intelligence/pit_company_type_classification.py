"""Proposed, pure PIT company-type research contract.

This module records only whether exact primary evidence could support a future
issuer/legal-entity company-type receipt for one exact NSE session security.
It has no selection, persistence, metric, scoring, or execution behaviour.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from enum import StrEnum
import hashlib
import json
import re
from typing import Iterable

from app.historical.nse_session_identity import (
    NseSessionIdentitySemantic,
    NseSessionPointIdentity,
    nse_session_point_identity_fingerprint,
)


POLICY_ID = "pit-company-type-classification-research-policy"
POLICY_VERSION = "v1"
CONTRACT_ID = "pit-company-type-classification-research-contract"
CONTRACT_VERSION = "v1"
_ID = re.compile(r"[A-Za-z0-9._:-]+\Z")
_FP = re.compile(r"sha256:[0-9a-f]{64}\Z")


class PitCompanyTypePolicyStatus(StrEnum):
    PROPOSED = "PROPOSED"
    NOT_APPROVED = "NOT_APPROVED"
    NOT_ACTIVE = "NOT_ACTIVE"
    RESEARCH_ONLY = "RESEARCH_ONLY"
    NON_EXECUTABLE = "NON_EXECUTABLE"


class PitCompanyTypeBranch(StrEnum):
    BANK = "BANK"
    NBFC = "NBFC"
    INSURER = "INSURER"
    NON_FINANCIAL = "NON_FINANCIAL"
    FINANCIAL_TYPE_UNSUPPORTED = "FINANCIAL_TYPE_UNSUPPORTED"
    STRUCTURALLY_NON_COMPARABLE = "STRUCTURALLY_NON_COMPARABLE"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class PitCompanyTypeReceiptState(StrEnum):
    EXACT_CLASSIFICATION_EVIDENCE_AVAILABLE = "EXACT_CLASSIFICATION_EVIDENCE_AVAILABLE"
    DATA_EVIDENCE_UNAVAILABLE = "DATA_EVIDENCE_UNAVAILABLE"
    IDENTITY_LINKAGE_UNAVAILABLE = "IDENTITY_LINKAGE_UNAVAILABLE"
    PIT_DATE_UNSUPPORTED = "PIT_DATE_UNSUPPORTED"
    EVIDENCE_CONFLICTED = "EVIDENCE_CONFLICTED"
    FINANCIAL_TYPE_UNSUPPORTED = "FINANCIAL_TYPE_UNSUPPORTED"
    NON_COMPARABLE = "NON_COMPARABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class PitCompanyTypeReason(StrEnum):
    EXACT_PRIMARY_EVIDENCE_PRESENT = "EXACT_PRIMARY_EVIDENCE_PRESENT"
    PRIMARY_EVIDENCE_REQUIRED = "PRIMARY_EVIDENCE_REQUIRED"
    EXACT_ISSUER_SECURITY_BRIDGE_REQUIRED = "EXACT_ISSUER_SECURITY_BRIDGE_REQUIRED"
    SESSION_IDENTITY_DATE_MISMATCH = "SESSION_IDENTITY_DATE_MISMATCH"
    FUTURE_EVIDENCE_EXCLUDED = "FUTURE_EVIDENCE_EXCLUDED"
    SOURCE_EVIDENCE_NOT_EFFECTIVE = "SOURCE_EVIDENCE_NOT_EFFECTIVE"
    CONFLICTING_PRIMARY_CLASSIFICATIONS = "CONFLICTING_PRIMARY_CLASSIFICATIONS"
    UNSUPPORTED_FINANCIAL_ENTITY = "UNSUPPORTED_FINANCIAL_ENTITY"
    STRUCTURALLY_NON_COMPARABLE_ENTITY = "STRUCTURALLY_NON_COMPARABLE_ENTITY"
    NON_FINANCIAL_POSITIVE_TAXONOMY_CODE_REQUIRED = "NON_FINANCIAL_POSITIVE_TAXONOMY_CODE_REQUIRED"


class PitCompanyTypeSourceFamily(StrEnum):
    RBI_SCHEDULED_COMMERCIAL_BANK = "RBI_SCHEDULED_COMMERCIAL_BANK"
    RBI_REGISTERED_NBFC_OR_ARC = "RBI_REGISTERED_NBFC_OR_ARC"
    IRDAI_REGISTERED_INSURER = "IRDAI_REGISTERED_INSURER"
    NSE_INDICES_INDUSTRY_CLASSIFICATION = "NSE_INDICES_INDUSTRY_CLASSIFICATION"


class PitCompanyTypeEvidenceCategory(StrEnum):
    RBI_BANK = "RBI_BANK"
    RBI_NBFC = "RBI_NBFC"
    RBI_ARC = "RBI_ARC"
    IRDAI_LIFE_INSURER = "IRDAI_LIFE_INSURER"
    IRDAI_GENERAL_INSURER = "IRDAI_GENERAL_INSURER"
    IRDAI_HEALTH_INSURER = "IRDAI_HEALTH_INSURER"
    NSE_NON_FINANCIAL_TAXONOMY_CODE = "NSE_NON_FINANCIAL_TAXONOMY_CODE"
    NSE_UNSUPPORTED_FINANCIAL_TAXONOMY_CODE = "NSE_UNSUPPORTED_FINANCIAL_TAXONOMY_CODE"
    NSE_NON_COMPARABLE_TAXONOMY_CODE = "NSE_NON_COMPARABLE_TAXONOMY_CODE"


class PitCompanyTypeTemporalSemantics(StrEnum):
    EXACT_SNAPSHOT_DATE = "EXACT_SNAPSHOT_DATE"
    EXPLICIT_EFFECTIVE_INTERVAL = "EXPLICIT_EFFECTIVE_INTERVAL"
    FIRST_OBSERVED_FROM_SOURCE_DATE = "FIRST_OBSERVED_FROM_SOURCE_DATE"


class PitCompanyTypeBridgeKind(StrEnum):
    CIN = "CIN"
    LEI = "LEI"
    REGULATOR_REGISTRATION_AND_CANONICAL_ENTITY = "REGULATOR_REGISTRATION_AND_CANONICAL_ENTITY"
    CANONICAL_ISSUER_ID = "CANONICAL_ISSUER_ID"
    OFFICIAL_ISIN = "OFFICIAL_ISIN"
    EXACT_SECURITY_ISIN_AND_SYMBOL = "EXACT_SECURITY_ISIN_AND_SYMBOL"


_POLICY_STATUS = (
    PitCompanyTypePolicyStatus.PROPOSED,
    PitCompanyTypePolicyStatus.NOT_APPROVED,
    PitCompanyTypePolicyStatus.NOT_ACTIVE,
    PitCompanyTypePolicyStatus.RESEARCH_ONLY,
    PitCompanyTypePolicyStatus.NON_EXECUTABLE,
)


@dataclass(frozen=True, slots=True)
class ProposedPitCompanyTypePolicy:
    policy_id: str
    policy_version: str
    status: tuple[PitCompanyTypePolicyStatus, ...]
    source_families: tuple[PitCompanyTypeSourceFamily, ...]
    fingerprint: str

    def __post_init__(self) -> None:
        if (
            self.policy_id != POLICY_ID
            or self.policy_version != POLICY_VERSION
            or self.status != _POLICY_STATUS
            or self.source_families != tuple(sorted(PitCompanyTypeSourceFamily, key=lambda item: item.value))
            or self.fingerprint != _hash(_policy_payload(self))
        ):
            raise PitCompanyTypeClassificationError("PIT_COMPANY_TYPE_POLICY_INVALID")


@dataclass(frozen=True, slots=True)
class ExactIssuerSecurityBridge:
    """A pre-verified bridge, never a name/alias/parent inference."""

    bridge_id: str
    issuer_legal_entity_id: str
    issuer_identity_fingerprint: str
    session_security_receipt_id: str
    session_security_fingerprint: str
    bridge_kind: PitCompanyTypeBridgeKind
    exact_key_reference: str
    fingerprint: str

    def __post_init__(self) -> None:
        if (
            not all((_identifier(self.bridge_id), _identifier(self.issuer_legal_entity_id), _fingerprint(self.issuer_identity_fingerprint), _identifier(self.session_security_receipt_id), _fingerprint(self.session_security_fingerprint), _identifier(self.exact_key_reference)))
            or not isinstance(self.bridge_kind, PitCompanyTypeBridgeKind)
            or self.fingerprint != _hash(_bridge_payload(self))
        ):
            raise PitCompanyTypeClassificationError("PIT_COMPANY_TYPE_EXACT_BRIDGE_INVALID")


@dataclass(frozen=True, slots=True)
class PitCompanyTypeEvidence:
    """One exact primary evidence item; raw legal names are intentionally absent."""

    evidence_id: str
    source_family: PitCompanyTypeSourceFamily
    source_category: PitCompanyTypeEvidenceCategory
    source_snapshot_id: str
    source_fingerprint: str
    issuer_legal_entity_id: str
    issuer_identity_fingerprint: str
    source_as_of_date: date
    known_at: datetime | None
    effective_from: date | None
    effective_to: date | None
    temporal_semantics: PitCompanyTypeTemporalSemantics
    proposed_branch: PitCompanyTypeBranch
    source_subtype_code: str | None
    taxonomy_code: str | None
    fingerprint: str

    def __post_init__(self) -> None:
        if (
            not all((_identifier(self.evidence_id), _identifier(self.source_snapshot_id), _fingerprint(self.source_fingerprint), _identifier(self.issuer_legal_entity_id), _fingerprint(self.issuer_identity_fingerprint), _date(self.source_as_of_date)))
            or not isinstance(self.source_family, PitCompanyTypeSourceFamily)
            or not isinstance(self.source_category, PitCompanyTypeEvidenceCategory)
            or not isinstance(self.temporal_semantics, PitCompanyTypeTemporalSemantics)
            or not isinstance(self.proposed_branch, PitCompanyTypeBranch)
            or (self.known_at is not None and not _aware(self.known_at))
            or (self.effective_from is not None and not _date(self.effective_from))
            or (self.effective_to is not None and not _date(self.effective_to))
            or (self.effective_from is not None and self.effective_to is not None and self.effective_to < self.effective_from)
            or not _category_consistent(self)
            or self.fingerprint != _hash(_evidence_payload(self))
        ):
            raise PitCompanyTypeClassificationError("PIT_COMPANY_TYPE_PRIMARY_EVIDENCE_INVALID")


@dataclass(frozen=True, slots=True)
class PitCompanyTypeResearchReceipt:
    """A descriptive proposed-policy receipt, never an authoritative selection."""

    receipt_id: str
    policy_id: str
    policy_version: str
    policy_fingerprint: str
    evaluation_session_date: date
    session_security_receipt_id: str
    session_security_fingerprint: str
    issuer_legal_entity_id: str | None
    bridge_id: str | None
    bridge_fingerprint: str | None
    branch: PitCompanyTypeBranch
    state: PitCompanyTypeReceiptState
    evidence: tuple[PitCompanyTypeEvidence, ...]
    reasons: tuple[PitCompanyTypeReason, ...]
    fingerprint: str
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION
    actionability: str = "WATCH_ONLY"
    execution_status: str = "NON_EXECUTABLE"

    def __post_init__(self) -> None:
        _validate_receipt(self)
        if self.receipt_id != "pit-company-type-research:" + _hash(_receipt_identity(self))[:24]:
            raise PitCompanyTypeClassificationError("PIT_COMPANY_TYPE_RECEIPT_IDENTITY_MISMATCH")
        if self.fingerprint != _hash(_receipt_payload(self)):
            raise PitCompanyTypeClassificationError("PIT_COMPANY_TYPE_RECEIPT_FINGERPRINT_MISMATCH")

    def verify(self) -> None:
        _validate_receipt(self)
        if self.receipt_id != "pit-company-type-research:" + _hash(_receipt_identity(self))[:24]:
            raise PitCompanyTypeClassificationError("PIT_COMPANY_TYPE_RECEIPT_IDENTITY_MISMATCH")
        if self.fingerprint != _hash(_receipt_payload(self)):
            raise PitCompanyTypeClassificationError("PIT_COMPANY_TYPE_RECEIPT_FINGERPRINT_MISMATCH")


class PitCompanyTypeClassificationError(ValueError):
    pass


def create_proposed_pit_company_type_policy() -> ProposedPitCompanyTypePolicy:
    values = {
        "policy_id": POLICY_ID,
        "policy_version": POLICY_VERSION,
        "status": _POLICY_STATUS,
        "source_families": tuple(sorted(PitCompanyTypeSourceFamily, key=lambda item: item.value)),
    }
    return ProposedPitCompanyTypePolicy(**values, fingerprint=_hash(values))


def create_exact_issuer_security_bridge(
    *,
    bridge_id: str,
    issuer_legal_entity_id: str,
    issuer_identity_fingerprint: str,
    session_security_receipt_id: str,
    session_security_fingerprint: str,
    bridge_kind: PitCompanyTypeBridgeKind,
    exact_key_reference: str,
) -> ExactIssuerSecurityBridge:
    if not isinstance(bridge_kind, PitCompanyTypeBridgeKind):
        raise PitCompanyTypeClassificationError("PIT_COMPANY_TYPE_EXACT_BRIDGE_INVALID")
    values = {
        "bridge_id": bridge_id,
        "issuer_legal_entity_id": issuer_legal_entity_id,
        "issuer_identity_fingerprint": issuer_identity_fingerprint,
        "session_security_receipt_id": session_security_receipt_id,
        "session_security_fingerprint": session_security_fingerprint,
        "bridge_kind": bridge_kind,
        "exact_key_reference": exact_key_reference,
    }
    return ExactIssuerSecurityBridge(**values, fingerprint=_hash({
        **values, "bridge_kind": bridge_kind.value,
    }))


def create_pit_company_type_evidence(
    *,
    evidence_id: str,
    source_family: PitCompanyTypeSourceFamily,
    source_category: PitCompanyTypeEvidenceCategory,
    source_snapshot_id: str,
    source_fingerprint: str,
    issuer_legal_entity_id: str,
    issuer_identity_fingerprint: str,
    source_as_of_date: date,
    known_at: datetime | None,
    effective_from: date | None,
    effective_to: date | None,
    temporal_semantics: PitCompanyTypeTemporalSemantics,
    proposed_branch: PitCompanyTypeBranch,
    source_subtype_code: str | None = None,
    taxonomy_code: str | None = None,
) -> PitCompanyTypeEvidence:
    if not all((
        isinstance(source_family, PitCompanyTypeSourceFamily),
        isinstance(source_category, PitCompanyTypeEvidenceCategory),
        isinstance(temporal_semantics, PitCompanyTypeTemporalSemantics),
        isinstance(proposed_branch, PitCompanyTypeBranch),
    )):
        raise PitCompanyTypeClassificationError("PIT_COMPANY_TYPE_PRIMARY_EVIDENCE_INVALID")
    values = {
        "evidence_id": evidence_id,
        "source_family": source_family,
        "source_category": source_category,
        "source_snapshot_id": source_snapshot_id,
        "source_fingerprint": source_fingerprint,
        "issuer_legal_entity_id": issuer_legal_entity_id,
        "issuer_identity_fingerprint": issuer_identity_fingerprint,
        "source_as_of_date": source_as_of_date,
        "known_at": known_at,
        "effective_from": effective_from,
        "effective_to": effective_to,
        "temporal_semantics": temporal_semantics,
        "proposed_branch": proposed_branch,
        "source_subtype_code": source_subtype_code,
        "taxonomy_code": taxonomy_code,
    }
    payload = {
        **values,
        "source_family": source_family.value,
        "source_category": source_category.value,
        "source_as_of_date": source_as_of_date.isoformat(),
        "known_at": _time(known_at) if known_at else None,
        "effective_from": effective_from.isoformat() if effective_from else None,
        "effective_to": effective_to.isoformat() if effective_to else None,
        "temporal_semantics": temporal_semantics.value,
        "proposed_branch": proposed_branch.value,
    }
    return PitCompanyTypeEvidence(**values, fingerprint=_hash(payload))


def assess_proposed_pit_company_type(
    session_security: NseSessionPointIdentity,
    *,
    bridge: ExactIssuerSecurityBridge | None,
    evidence: Iterable[PitCompanyTypeEvidence] = (),
) -> PitCompanyTypeResearchReceipt:
    """Assess exact supplied evidence at the receipt's exact session date.

    The function consumes no source, clock, store, or current master.  It does
    not convert absent regulator evidence into a non-financial classification.
    """
    _validate_session_security(session_security)
    canonical_evidence = _canonical_evidence(tuple(evidence))
    if bridge is None:
        if canonical_evidence:
            raise PitCompanyTypeClassificationError("PIT_COMPANY_TYPE_UNBRIDGED_EVIDENCE_FORBIDDEN")
        return _receipt(
            session_security, None, PitCompanyTypeBranch.UNKNOWN,
            PitCompanyTypeReceiptState.IDENTITY_LINKAGE_UNAVAILABLE, (),
            (PitCompanyTypeReason.EXACT_ISSUER_SECURITY_BRIDGE_REQUIRED,),
        )
    if not _bridge_matches_session(bridge, session_security):
        return _receipt(
            session_security, None, PitCompanyTypeBranch.UNKNOWN,
            PitCompanyTypeReceiptState.IDENTITY_LINKAGE_UNAVAILABLE, (),
            (PitCompanyTypeReason.EXACT_ISSUER_SECURITY_BRIDGE_REQUIRED,),
        )
    if any(item.issuer_legal_entity_id != bridge.issuer_legal_entity_id or item.issuer_identity_fingerprint != bridge.issuer_identity_fingerprint for item in canonical_evidence):
        raise PitCompanyTypeClassificationError("PIT_COMPANY_TYPE_EVIDENCE_ENTITY_MISMATCH")
    eligible, temporal_reason = _pit_eligible(canonical_evidence, session_security.session_date)
    if not eligible:
        return _receipt(
            session_security, bridge, PitCompanyTypeBranch.UNKNOWN,
            PitCompanyTypeReceiptState.DATA_EVIDENCE_UNAVAILABLE if not canonical_evidence else PitCompanyTypeReceiptState.PIT_DATE_UNSUPPORTED,
            canonical_evidence, (PitCompanyTypeReason.PRIMARY_EVIDENCE_REQUIRED,) if not canonical_evidence else (temporal_reason,),
        )
    branches = tuple(sorted({item.proposed_branch for item in eligible}, key=lambda item: item.value))
    if len(branches) != 1:
        return _receipt(
            session_security, bridge, PitCompanyTypeBranch.UNKNOWN,
            PitCompanyTypeReceiptState.EVIDENCE_CONFLICTED, eligible,
            (PitCompanyTypeReason.CONFLICTING_PRIMARY_CLASSIFICATIONS,),
        )
    branch = branches[0]
    if branch is PitCompanyTypeBranch.FINANCIAL_TYPE_UNSUPPORTED:
        return _receipt(session_security, bridge, branch, PitCompanyTypeReceiptState.FINANCIAL_TYPE_UNSUPPORTED, eligible, (PitCompanyTypeReason.UNSUPPORTED_FINANCIAL_ENTITY,))
    if branch is PitCompanyTypeBranch.STRUCTURALLY_NON_COMPARABLE:
        return _receipt(session_security, bridge, branch, PitCompanyTypeReceiptState.NON_COMPARABLE, eligible, (PitCompanyTypeReason.STRUCTURALLY_NON_COMPARABLE_ENTITY,))
    if branch is PitCompanyTypeBranch.NON_FINANCIAL and any(not item.taxonomy_code for item in eligible):
        return _receipt(session_security, bridge, PitCompanyTypeBranch.UNKNOWN, PitCompanyTypeReceiptState.DATA_EVIDENCE_UNAVAILABLE, eligible, (PitCompanyTypeReason.NON_FINANCIAL_POSITIVE_TAXONOMY_CODE_REQUIRED,))
    return _receipt(
        session_security, bridge, branch, PitCompanyTypeReceiptState.EXACT_CLASSIFICATION_EVIDENCE_AVAILABLE,
        eligible, (PitCompanyTypeReason.EXACT_PRIMARY_EVIDENCE_PRESENT,),
    )


def pit_company_type_receipt_payload(value: PitCompanyTypeResearchReceipt) -> dict[str, object]:
    value.verify()
    return _receipt_payload(value) | {"fingerprint": value.fingerprint}


def serialize_pit_company_type_receipt(value: PitCompanyTypeResearchReceipt) -> str:
    return json.dumps(pit_company_type_receipt_payload(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _receipt(session, bridge, branch, state, evidence, reasons) -> PitCompanyTypeResearchReceipt:
    policy = create_proposed_pit_company_type_policy()
    values = {
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "policy_fingerprint": policy.fingerprint,
        "evaluation_session_date": session.session_date,
        "session_security_receipt_id": session.receipt_id,
        "session_security_fingerprint": session.fingerprint,
        "issuer_legal_entity_id": bridge.issuer_legal_entity_id if bridge else None,
        "bridge_id": bridge.bridge_id if bridge else None,
        "bridge_fingerprint": bridge.fingerprint if bridge else None,
        "branch": branch,
        "state": state,
        "evidence": evidence,
        "reasons": tuple(sorted(set(reasons), key=lambda item: item.value)),
    }
    receipt_id = "pit-company-type-research:" + _hash(_receipt_identity_from_values(values))[:24]
    return PitCompanyTypeResearchReceipt(
        receipt_id=receipt_id, **values,
        fingerprint=_hash(_receipt_payload_from_values(values | {"receipt_id": receipt_id})),
    )


def _pit_eligible(values: tuple[PitCompanyTypeEvidence, ...], session_date: date) -> tuple[tuple[PitCompanyTypeEvidence, ...], PitCompanyTypeReason]:
    if not values:
        return (), PitCompanyTypeReason.PRIMARY_EVIDENCE_REQUIRED
    eligible = tuple(item for item in values if _effective_on(item, session_date))
    if eligible:
        return eligible, PitCompanyTypeReason.EXACT_PRIMARY_EVIDENCE_PRESENT
    if any(item.source_as_of_date > session_date or (item.known_at is not None and _utc(item.known_at).date() > session_date) for item in values):
        return (), PitCompanyTypeReason.FUTURE_EVIDENCE_EXCLUDED
    return (), PitCompanyTypeReason.SOURCE_EVIDENCE_NOT_EFFECTIVE


def _effective_on(value: PitCompanyTypeEvidence, session_date: date) -> bool:
    if value.known_at is not None and _utc(value.known_at).date() > session_date:
        return False
    if value.temporal_semantics is PitCompanyTypeTemporalSemantics.EXACT_SNAPSHOT_DATE:
        return value.source_as_of_date == session_date
    if value.temporal_semantics is PitCompanyTypeTemporalSemantics.FIRST_OBSERVED_FROM_SOURCE_DATE:
        return value.source_as_of_date <= session_date
    return value.effective_from is not None and value.effective_from <= session_date and (value.effective_to is None or session_date <= value.effective_to)


def _category_consistent(value: PitCompanyTypeEvidence) -> bool:
    expected = {
        PitCompanyTypeBranch.BANK: (PitCompanyTypeSourceFamily.RBI_SCHEDULED_COMMERCIAL_BANK, PitCompanyTypeEvidenceCategory.RBI_BANK),
        PitCompanyTypeBranch.NBFC: (PitCompanyTypeSourceFamily.RBI_REGISTERED_NBFC_OR_ARC, PitCompanyTypeEvidenceCategory.RBI_NBFC),
        PitCompanyTypeBranch.INSURER: (PitCompanyTypeSourceFamily.IRDAI_REGISTERED_INSURER, None),
        PitCompanyTypeBranch.NON_FINANCIAL: (PitCompanyTypeSourceFamily.NSE_INDICES_INDUSTRY_CLASSIFICATION, PitCompanyTypeEvidenceCategory.NSE_NON_FINANCIAL_TAXONOMY_CODE),
        PitCompanyTypeBranch.FINANCIAL_TYPE_UNSUPPORTED: (None, None),
        PitCompanyTypeBranch.STRUCTURALLY_NON_COMPARABLE: (PitCompanyTypeSourceFamily.NSE_INDICES_INDUSTRY_CLASSIFICATION, PitCompanyTypeEvidenceCategory.NSE_NON_COMPARABLE_TAXONOMY_CODE),
    }
    if value.proposed_branch in {PitCompanyTypeBranch.UNKNOWN, PitCompanyTypeBranch.NOT_APPLICABLE}:
        return False
    family, category = expected[value.proposed_branch]
    if family is not None and value.source_family is not family:
        return False
    if category is not None and value.source_category is not category:
        return False
    if value.source_subtype_code is not None and not _identifier(value.source_subtype_code):
        return False
    if value.taxonomy_code is not None and not _identifier(value.taxonomy_code):
        return False
    if value.proposed_branch is PitCompanyTypeBranch.INSURER:
        return value.source_category in {
            PitCompanyTypeEvidenceCategory.IRDAI_LIFE_INSURER,
            PitCompanyTypeEvidenceCategory.IRDAI_GENERAL_INSURER,
            PitCompanyTypeEvidenceCategory.IRDAI_HEALTH_INSURER,
        }
    if value.proposed_branch is PitCompanyTypeBranch.FINANCIAL_TYPE_UNSUPPORTED:
        if (value.source_family, value.source_category) not in {
            (PitCompanyTypeSourceFamily.RBI_REGISTERED_NBFC_OR_ARC, PitCompanyTypeEvidenceCategory.RBI_ARC),
            (PitCompanyTypeSourceFamily.NSE_INDICES_INDUSTRY_CLASSIFICATION, PitCompanyTypeEvidenceCategory.NSE_UNSUPPORTED_FINANCIAL_TAXONOMY_CODE),
        }:
            return False
        return value.source_family is not PitCompanyTypeSourceFamily.NSE_INDICES_INDUSTRY_CLASSIFICATION or value.taxonomy_code is not None
    if value.proposed_branch is PitCompanyTypeBranch.NON_FINANCIAL:
        return value.taxonomy_code is not None
    if value.proposed_branch is PitCompanyTypeBranch.STRUCTURALLY_NON_COMPARABLE:
        return value.taxonomy_code is not None
    return True


def _canonical_evidence(values: tuple[PitCompanyTypeEvidence, ...]) -> tuple[PitCompanyTypeEvidence, ...]:
    if not all(isinstance(item, PitCompanyTypeEvidence) for item in values):
        raise PitCompanyTypeClassificationError("PIT_COMPANY_TYPE_EVIDENCE_INPUT_INVALID")
    if len({item.evidence_id for item in values}) != len(values):
        raise PitCompanyTypeClassificationError("PIT_COMPANY_TYPE_EVIDENCE_ID_DUPLICATE")
    if len({item.fingerprint for item in values}) != len(values):
        raise PitCompanyTypeClassificationError("PIT_COMPANY_TYPE_EVIDENCE_FINGERPRINT_DUPLICATE")
    for item in values:
        if item.fingerprint != _hash(_evidence_payload(item)):
            raise PitCompanyTypeClassificationError("PIT_COMPANY_TYPE_EVIDENCE_FINGERPRINT_MISMATCH")
    return tuple(sorted(values, key=lambda item: (item.source_as_of_date, item.evidence_id, item.fingerprint)))


def _validate_session_security(value: object) -> None:
    if (
        not isinstance(value, NseSessionPointIdentity)
        or value.semantic is not NseSessionIdentitySemantic.KNOWN_FOR_SESSION_D
        or value.fingerprint != nse_session_point_identity_fingerprint(value)
    ):
        raise PitCompanyTypeClassificationError("PIT_COMPANY_TYPE_SESSION_SECURITY_INVALID")


def _bridge_matches_session(bridge: ExactIssuerSecurityBridge, session: NseSessionPointIdentity) -> bool:
    return bridge.session_security_receipt_id == session.receipt_id and bridge.session_security_fingerprint == session.fingerprint


def _validate_receipt(value: PitCompanyTypeResearchReceipt) -> None:
    if (
        not _identifier(value.receipt_id)
        or value.policy_id != POLICY_ID
        or value.policy_version != POLICY_VERSION
        or value.policy_fingerprint != create_proposed_pit_company_type_policy().fingerprint
        or not _date(value.evaluation_session_date)
        or not _identifier(value.session_security_receipt_id)
        or not _fingerprint(value.session_security_fingerprint)
        or not isinstance(value.branch, PitCompanyTypeBranch)
        or not isinstance(value.state, PitCompanyTypeReceiptState)
        or value.evidence != _canonical_evidence(value.evidence)
        or value.reasons != tuple(sorted(set(value.reasons), key=lambda item: item.value))
        or not all(isinstance(item, PitCompanyTypeReason) for item in value.reasons)
        or value.contract_id != CONTRACT_ID
        or value.contract_version != CONTRACT_VERSION
        or (value.actionability, value.execution_status) != ("WATCH_ONLY", "NON_EXECUTABLE")
    ):
        raise PitCompanyTypeClassificationError("PIT_COMPANY_TYPE_RECEIPT_INVALID")
    has_bridge = all((value.issuer_legal_entity_id, value.bridge_id, value.bridge_fingerprint))
    if any(item is not None for item in (value.issuer_legal_entity_id, value.bridge_id, value.bridge_fingerprint)) and not has_bridge:
        raise PitCompanyTypeClassificationError("PIT_COMPANY_TYPE_RECEIPT_BRIDGE_PARTIAL")
    if has_bridge and not all((_identifier(value.issuer_legal_entity_id), _identifier(value.bridge_id), _fingerprint(value.bridge_fingerprint))):
        raise PitCompanyTypeClassificationError("PIT_COMPANY_TYPE_RECEIPT_BRIDGE_INVALID")
    _validate_state(value, has_bridge)


def _validate_state(value: PitCompanyTypeResearchReceipt, has_bridge: bool) -> None:
    expected = {
        PitCompanyTypeReceiptState.EXACT_CLASSIFICATION_EVIDENCE_AVAILABLE: (True, True, (PitCompanyTypeReason.EXACT_PRIMARY_EVIDENCE_PRESENT,)),
        PitCompanyTypeReceiptState.DATA_EVIDENCE_UNAVAILABLE: (None, False, (PitCompanyTypeReason.PRIMARY_EVIDENCE_REQUIRED, PitCompanyTypeReason.NON_FINANCIAL_POSITIVE_TAXONOMY_CODE_REQUIRED)),
        PitCompanyTypeReceiptState.IDENTITY_LINKAGE_UNAVAILABLE: (False, False, (PitCompanyTypeReason.EXACT_ISSUER_SECURITY_BRIDGE_REQUIRED,)),
        PitCompanyTypeReceiptState.PIT_DATE_UNSUPPORTED: (True, None, (PitCompanyTypeReason.FUTURE_EVIDENCE_EXCLUDED, PitCompanyTypeReason.SOURCE_EVIDENCE_NOT_EFFECTIVE)),
        PitCompanyTypeReceiptState.EVIDENCE_CONFLICTED: (True, True, (PitCompanyTypeReason.CONFLICTING_PRIMARY_CLASSIFICATIONS,)),
        PitCompanyTypeReceiptState.FINANCIAL_TYPE_UNSUPPORTED: (True, True, (PitCompanyTypeReason.UNSUPPORTED_FINANCIAL_ENTITY,)),
        PitCompanyTypeReceiptState.NON_COMPARABLE: (True, True, (PitCompanyTypeReason.STRUCTURALLY_NON_COMPARABLE_ENTITY,)),
        PitCompanyTypeReceiptState.NOT_APPLICABLE: (None, False, ()),
    }[value.state]
    bridge_expected, evidence_expected, allowed_reasons = expected
    if bridge_expected is not None and has_bridge is not bridge_expected:
        raise PitCompanyTypeClassificationError("PIT_COMPANY_TYPE_RECEIPT_STATE_BRIDGE_CONTRADICTION")
    if evidence_expected is not None and bool(value.evidence) is not evidence_expected:
        raise PitCompanyTypeClassificationError("PIT_COMPANY_TYPE_RECEIPT_STATE_EVIDENCE_CONTRADICTION")
    if value.reasons not in tuple((reason,) for reason in allowed_reasons) and value.reasons != allowed_reasons:
        raise PitCompanyTypeClassificationError("PIT_COMPANY_TYPE_RECEIPT_STATE_REASON_CONTRADICTION")
    if value.state is PitCompanyTypeReceiptState.EXACT_CLASSIFICATION_EVIDENCE_AVAILABLE and value.branch in {
        PitCompanyTypeBranch.UNKNOWN, PitCompanyTypeBranch.NOT_APPLICABLE,
        PitCompanyTypeBranch.FINANCIAL_TYPE_UNSUPPORTED, PitCompanyTypeBranch.STRUCTURALLY_NON_COMPARABLE,
    }:
        raise PitCompanyTypeClassificationError("PIT_COMPANY_TYPE_RECEIPT_EXACT_BRANCH_INVALID")
    if value.state in {PitCompanyTypeReceiptState.IDENTITY_LINKAGE_UNAVAILABLE, PitCompanyTypeReceiptState.DATA_EVIDENCE_UNAVAILABLE, PitCompanyTypeReceiptState.PIT_DATE_UNSUPPORTED, PitCompanyTypeReceiptState.EVIDENCE_CONFLICTED} and value.branch is not PitCompanyTypeBranch.UNKNOWN:
        raise PitCompanyTypeClassificationError("PIT_COMPANY_TYPE_RECEIPT_UNAVAILABLE_BRANCH_INVALID")


def _policy_payload(value: ProposedPitCompanyTypePolicy) -> dict[str, object]:
    return {
        "policy_id": value.policy_id,
        "policy_version": value.policy_version,
        "status": tuple(item.value for item in value.status),
        "source_families": tuple(item.value for item in value.source_families),
    }


def _bridge_payload(value: ExactIssuerSecurityBridge) -> dict[str, str]:
    return {
        "bridge_id": value.bridge_id,
        "issuer_legal_entity_id": value.issuer_legal_entity_id,
        "issuer_identity_fingerprint": value.issuer_identity_fingerprint,
        "session_security_receipt_id": value.session_security_receipt_id,
        "session_security_fingerprint": value.session_security_fingerprint,
        "bridge_kind": value.bridge_kind.value,
        "exact_key_reference": value.exact_key_reference,
    }


def _evidence_payload(value: PitCompanyTypeEvidence) -> dict[str, object]:
    return {
        "evidence_id": value.evidence_id,
        "source_family": value.source_family.value,
        "source_category": value.source_category.value,
        "source_snapshot_id": value.source_snapshot_id,
        "source_fingerprint": value.source_fingerprint,
        "issuer_legal_entity_id": value.issuer_legal_entity_id,
        "issuer_identity_fingerprint": value.issuer_identity_fingerprint,
        "source_as_of_date": value.source_as_of_date.isoformat(),
        "known_at": _time(value.known_at) if value.known_at else None,
        "effective_from": value.effective_from.isoformat() if value.effective_from else None,
        "effective_to": value.effective_to.isoformat() if value.effective_to else None,
        "temporal_semantics": value.temporal_semantics.value,
        "proposed_branch": value.proposed_branch.value,
        "source_subtype_code": value.source_subtype_code,
        "taxonomy_code": value.taxonomy_code,
    }


def _receipt_identity(value: PitCompanyTypeResearchReceipt) -> dict[str, object]:
    return _receipt_identity_from_values({name: getattr(value, name) for name in value.__dataclass_fields__ if name not in {"receipt_id", "fingerprint", "contract_id", "contract_version", "actionability", "execution_status"}})


def _receipt_identity_from_values(values: dict[str, object]) -> dict[str, object]:
    return {
        "contract_id": CONTRACT_ID,
        "contract_version": CONTRACT_VERSION,
        "policy_id": values["policy_id"],
        "policy_version": values["policy_version"],
        "policy_fingerprint": values["policy_fingerprint"],
        "evaluation_session_date": values["evaluation_session_date"].isoformat(),
        "session_security_receipt_id": values["session_security_receipt_id"],
        "session_security_fingerprint": values["session_security_fingerprint"],
        "issuer_legal_entity_id": values["issuer_legal_entity_id"],
        "bridge_id": values["bridge_id"],
        "bridge_fingerprint": values["bridge_fingerprint"],
        "evidence": tuple(_evidence_payload(item) | {"fingerprint": item.fingerprint} for item in values["evidence"]),
    }


def _receipt_payload(value: PitCompanyTypeResearchReceipt) -> dict[str, object]:
    return _receipt_payload_from_values({name: getattr(value, name) for name in value.__dataclass_fields__ if name not in {"fingerprint", "contract_id", "contract_version", "actionability", "execution_status"}})


def _receipt_payload_from_values(values: dict[str, object]) -> dict[str, object]:
    return _receipt_identity_from_values(values) | {
        "receipt_id": values["receipt_id"],
        "branch": values["branch"].value,
        "state": values["state"].value,
        "reasons": tuple(item.value for item in values["reasons"]),
        "actionability": "WATCH_ONLY",
        "execution_status": "NON_EXECUTABLE",
    }


def _identifier(value: object) -> bool:
    return isinstance(value, str) and _ID.fullmatch(value) is not None


def _fingerprint(value: object) -> bool:
    return isinstance(value, str) and _FP.fullmatch(value) is not None


def _date(value: object) -> bool:
    return isinstance(value, date) and not isinstance(value, datetime)


def _aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def _utc(value: datetime) -> datetime:
    if not _aware(value):
        raise PitCompanyTypeClassificationError("PIT_COMPANY_TYPE_TIMESTAMP_INVALID")
    return value.astimezone(UTC)


def _time(value: datetime) -> str:
    return _utc(value).isoformat()


def _hash(value: object) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


__all__ = (
    "CONTRACT_ID", "CONTRACT_VERSION", "POLICY_ID", "POLICY_VERSION",
    "ExactIssuerSecurityBridge", "PitCompanyTypeBranch", "PitCompanyTypeBridgeKind",
    "PitCompanyTypeClassificationError", "PitCompanyTypeEvidence", "PitCompanyTypeEvidenceCategory",
    "PitCompanyTypePolicyStatus", "PitCompanyTypeReceiptState", "PitCompanyTypeReason",
    "PitCompanyTypeResearchReceipt", "PitCompanyTypeSourceFamily", "PitCompanyTypeTemporalSemantics",
    "ProposedPitCompanyTypePolicy", "assess_proposed_pit_company_type",
    "create_exact_issuer_security_bridge", "create_pit_company_type_evidence",
    "create_proposed_pit_company_type_policy", "pit_company_type_receipt_payload",
    "serialize_pit_company_type_receipt",
)
