"""Activated RAW_EXACT regulator-to-issuer evidence linkage.

This module is intentionally narrower than company-type classification.  It
links independent primary records only after the approved NFC-and-trim legal
name comparison, strict uniqueness, and PIT knownness checks all succeed.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
import json
import re
import unicodedata
from typing import Iterable

from app.historical.isin_issuer_bridge_continuity import IsinIssuerAnchorBridge, IsinIssuerForwardObservation
from app.historical.issuer_identifier_acquisition import ExactIssuerIdentifierEvidence, IssuerIdentifierEvidenceSource
from app.historical.issuer_security_identity import IssuerIdentifierType
from app.historical.regulator_company_type_evidence import RegulatorEntityEvidence, RegulatorEvidenceSource
from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily, CoreApiSnapshotRepository


POLICY_ID = "regulator-issuer-raw-exact-linkage-policy"
POLICY_VERSION = "v1"
CONTRACT_ID = "regulator-issuer-raw-exact-linkage-activation"
CONTRACT_VERSION = "v1"
_ID = re.compile(r"[A-Za-z0-9._:-]+\Z")
_FP = re.compile(r"sha256:[0-9a-f]{64}\Z")
_CIN = re.compile(r"[LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}\Z")


class RegulatorIssuerRawExactLinkageError(ValueError):
    """Stable fail-closed error for the activated RAW_EXACT boundary."""


class RawExactLinkageSemantic(StrEnum):
    UNICODE_NFC_ONLY = "UNICODE_NFC_ONLY"
    LEADING_TRAILING_WHITESPACE_ONLY = "LEADING_TRAILING_WHITESPACE_ONLY"
    ONE_TO_ONE_REQUIRED = "ONE_TO_ONE_REQUIRED"
    REGULATOR_FAMILY_ISOLATION = "REGULATOR_FAMILY_ISOLATION"
    LATER_EVIDENCE_KNOWN_AT = "LATER_EVIDENCE_KNOWN_AT"
    NO_COMPANY_TYPE_CLASSIFICATION = "NO_COMPANY_TYPE_CLASSIFICATION"
    NO_REPRESENTATION_EXACT = "NO_REPRESENTATION_EXACT"


class RawExactLinkageApprovalState(StrEnum): APPROVED = "APPROVED"
class RawExactLinkageActivationState(StrEnum): ACTIVE = "ACTIVE"
class RawExactLinkageState(StrEnum): ACTIVE = "ACTIVE"


class RawExactLinkageStatus(StrEnum):
    IDENTITY_VALID = "IDENTITY_VALID"
    ACTIVE_LINK = "ACTIVE_LINK"
    PIT_EVIDENCE_TOO_LATE = "PIT_EVIDENCE_TOO_LATE"
    EVIDENCE_CONFLICTED = "EVIDENCE_CONFLICTED"
    DATA_UNAVAILABLE = "DATA_UNAVAILABLE"


class RawExactLinkageReason(StrEnum):
    RAW_EXACT_UNIQUE = "RAW_EXACT_UNIQUE"
    REGULATOR_EVIDENCE_AFTER_AS_OF = "REGULATOR_EVIDENCE_AFTER_AS_OF"
    ISSUER_EVIDENCE_AFTER_AS_OF = "ISSUER_EVIDENCE_AFTER_AS_OF"
    CANONICAL_CIN_NAME_AMBIGUOUS = "CANONICAL_CIN_NAME_AMBIGUOUS"
    REGULATOR_NAME_AMBIGUOUS = "REGULATOR_NAME_AMBIGUOUS"
    CROSS_REGULATOR_FAMILY_CONFLICT = "CROSS_REGULATOR_FAMILY_CONFLICT"
    NO_RAW_EXACT_REGULATOR_CORRESPONDENCE = "NO_RAW_EXACT_REGULATOR_CORRESPONDENCE"
    NBFC_ARC_DATA_UNAVAILABLE = "NBFC_ARC_DATA_UNAVAILABLE"


class RawExactLinkageWriteOutcome(StrEnum): INSERTED = "INSERTED"; ALREADY_PRESENT = "ALREADY_PRESENT"


_SEMANTICS = (
    RawExactLinkageSemantic.UNICODE_NFC_ONLY, RawExactLinkageSemantic.LEADING_TRAILING_WHITESPACE_ONLY,
    RawExactLinkageSemantic.ONE_TO_ONE_REQUIRED, RawExactLinkageSemantic.REGULATOR_FAMILY_ISOLATION,
    RawExactLinkageSemantic.LATER_EVIDENCE_KNOWN_AT, RawExactLinkageSemantic.NO_COMPANY_TYPE_CLASSIFICATION,
    RawExactLinkageSemantic.NO_REPRESENTATION_EXACT,
)


@dataclass(frozen=True, slots=True)
class RawExactLinkagePolicy:
    policy_id: str; policy_version: str; semantics: tuple[RawExactLinkageSemantic, ...]; fingerprint: str
    contract_id: str = CONTRACT_ID; contract_version: str = CONTRACT_VERSION
    def __post_init__(self) -> None:
        if (self.policy_id, self.policy_version, self.semantics, self.contract_id, self.contract_version) != (POLICY_ID, POLICY_VERSION, _SEMANTICS, CONTRACT_ID, CONTRACT_VERSION) or self.fingerprint != _hash(_policy_payload(self)):
            raise RegulatorIssuerRawExactLinkageError("RAW_EXACT_LINKAGE_POLICY_INVALID")


@dataclass(frozen=True, slots=True)
class RawExactLinkageApproval:
    approval_id: str; policy_id: str; policy_version: str; policy_fingerprint: str; approved_by: str; approved_at: datetime; state: RawExactLinkageApprovalState; fingerprint: str
    contract_id: str = CONTRACT_ID; contract_version: str = CONTRACT_VERSION
    def __post_init__(self) -> None:
        policy = create_raw_exact_linkage_policy()
        if not (_identifier(self.approval_id) and (self.policy_id, self.policy_version, self.policy_fingerprint) == (policy.policy_id, policy.policy_version, policy.fingerprint) and self.approved_by.startswith("human:") and _aware(self.approved_at) and self.state is RawExactLinkageApprovalState.APPROVED and self.contract_id == CONTRACT_ID and self.contract_version == CONTRACT_VERSION and self.fingerprint == _hash(_approval_payload(self))):
            raise RegulatorIssuerRawExactLinkageError("RAW_EXACT_LINKAGE_APPROVAL_INVALID")


@dataclass(frozen=True, slots=True)
class RawExactLinkageActivation:
    selection_id: str; approval_id: str; approval_fingerprint: str; policy_id: str; policy_version: str; policy_fingerprint: str; activated_by: str; activated_at: datetime; state: RawExactLinkageActivationState; fingerprint: str
    contract_id: str = CONTRACT_ID; contract_version: str = CONTRACT_VERSION
    def __post_init__(self) -> None:
        if not (_identifier(self.selection_id) and _identifier(self.approval_id) and _fingerprint(self.approval_fingerprint) and (self.policy_id, self.policy_version, self.policy_fingerprint) == _policy_identity() and self.activated_by.startswith("human:") and _aware(self.activated_at) and self.state is RawExactLinkageActivationState.ACTIVE and self.contract_id == CONTRACT_ID and self.contract_version == CONTRACT_VERSION and self.fingerprint == _hash(_activation_payload(self))):
            raise RegulatorIssuerRawExactLinkageError("RAW_EXACT_LINKAGE_ACTIVATION_INVALID")


@dataclass(frozen=True, slots=True)
class RawExactIssuerNameFact:
    cin: str; legal_name: str; issuer_evidence_id: str; issuer_evidence_fingerprint: str; issuer_known_at: datetime; forward_observation_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RawExactLinkageEvaluation:
    cin: str | None; canonical_legal_name: str | None; issuer_evidence_id: str | None; issuer_evidence_fingerprint: str | None; regulator_evidence_id: str | None; regulator_evidence_fingerprint: str | None; regulator_family: RegulatorEvidenceSource | None; regulator_subtype: str | None; status: RawExactLinkageStatus; reasons: tuple[RawExactLinkageReason, ...]; issuer_known_at: datetime | None; regulator_known_at: datetime | None


@dataclass(frozen=True, slots=True)
class RawExactLinkageAudit:
    as_of: datetime; active_issuer_cins: int; identity_candidates: int; active_links: int; evaluations: tuple[RawExactLinkageEvaluation, ...]; fingerprint: str
    def __post_init__(self) -> None:
        candidates = sum(item.status in {RawExactLinkageStatus.IDENTITY_VALID, RawExactLinkageStatus.PIT_EVIDENCE_TOO_LATE} for item in self.evaluations)
        links = sum(item.status is RawExactLinkageStatus.IDENTITY_VALID for item in self.evaluations)
        if not _aware(self.as_of) or min(self.active_issuer_cins, self.identity_candidates, self.active_links) < 0 or (self.identity_candidates, self.active_links) != (candidates, links) or self.evaluations != tuple(sorted(self.evaluations, key=_evaluation_key)) or self.fingerprint != _hash(_audit_payload(self)):
            raise RegulatorIssuerRawExactLinkageError("RAW_EXACT_LINKAGE_AUDIT_INVALID")


@dataclass(frozen=True, slots=True)
class RawExactRegulatorIssuerLink:
    link_id: str; policy_id: str; policy_version: str; policy_fingerprint: str; approval_id: str; activation_id: str; cin: str; canonical_legal_name: str; issuer_evidence_id: str; issuer_evidence_fingerprint: str; issuer_known_at: datetime; regulator_evidence_id: str; regulator_evidence_fingerprint: str; regulator_legal_name: str; regulator_family: RegulatorEvidenceSource; regulator_subtype: str | None; regulator_known_at: datetime; link_known_at: datetime; state: RawExactLinkageState; fingerprint: str
    contract_id: str = CONTRACT_ID; contract_version: str = CONTRACT_VERSION
    def __post_init__(self) -> None:
        if not (_link_valid(self) and self.link_id == _link_id(_link_identity(self)) and self.fingerprint == _hash(_link_payload(self))):
            raise RegulatorIssuerRawExactLinkageError("RAW_EXACT_REGULATOR_ISSUER_LINK_INVALID")
    def verify(self) -> None: self.__post_init__()


class RawExactLinkageStore:
    def __init__(self, repository: CoreApiSnapshotRepository) -> None: self._repository = repository
    def save_policy(self, value: RawExactLinkagePolicy) -> RawExactLinkageWriteOutcome: return self._save("raw-exact-linkage-policy:" + value.policy_id + ":" + value.policy_version, value, datetime(1970, 1, 1, tzinfo=UTC))
    def save_approval(self, value: RawExactLinkageApproval) -> RawExactLinkageWriteOutcome: return self._save(value.approval_id, value, value.approved_at)
    def save_activation(self, value: RawExactLinkageActivation) -> RawExactLinkageWriteOutcome: return self._save(value.selection_id, value, value.activated_at)
    def save_link(self, value: RawExactRegulatorIssuerLink) -> RawExactLinkageWriteOutcome: return self._save(value.link_id, value, value.link_known_at)
    def _save(self, snapshot_id: str, value: object, created_at: datetime) -> RawExactLinkageWriteOutcome:
        existing = self._repository.get_snapshot(snapshot_id)
        if existing is not None:
            if existing.family is not CoreApiSnapshotFamily.HISTORICAL_ISSUER_SECURITY_BRIDGE or existing.payload != value: raise RegulatorIssuerRawExactLinkageError("RAW_EXACT_LINKAGE_IMMUTABILITY_CONFLICT")
            return RawExactLinkageWriteOutcome.ALREADY_PRESENT
        self._repository.save_snapshot(CoreApiSnapshot(snapshot_id, CoreApiSnapshotFamily.HISTORICAL_ISSUER_SECURITY_BRIDGE, "v1", type(value).__name__, getattr(value, "fingerprint"), created_at, value)); return RawExactLinkageWriteOutcome.INSERTED


def create_raw_exact_linkage_policy() -> RawExactLinkagePolicy:
    values = dict(policy_id=POLICY_ID, policy_version=POLICY_VERSION, semantics=_SEMANTICS)
    return RawExactLinkagePolicy(**values, fingerprint=_hash(values | {"contract_id": CONTRACT_ID, "contract_version": CONTRACT_VERSION}))


def approve_raw_exact_linkage_policy(*, approval_id: str, approved_by: str, approved_at: datetime) -> RawExactLinkageApproval:
    policy = create_raw_exact_linkage_policy(); values = dict(approval_id=approval_id, policy_id=policy.policy_id, policy_version=policy.policy_version, policy_fingerprint=policy.fingerprint, approved_by=approved_by, approved_at=_utc(approved_at), state=RawExactLinkageApprovalState.APPROVED)
    return RawExactLinkageApproval(**values, fingerprint=_hash(values))


def activate_raw_exact_linkage_policy(*, selection_id: str, approval: RawExactLinkageApproval, activated_by: str, activated_at: datetime) -> RawExactLinkageActivation:
    approval.__post_init__(); activated_at = _utc(activated_at)
    if activated_at < _utc(approval.approved_at): raise RegulatorIssuerRawExactLinkageError("RAW_EXACT_LINKAGE_ACTIVATION_PRECEDES_APPROVAL")
    values = dict(selection_id=selection_id, approval_id=approval.approval_id, approval_fingerprint=approval.fingerprint, policy_id=approval.policy_id, policy_version=approval.policy_version, policy_fingerprint=approval.policy_fingerprint, activated_by=activated_by, activated_at=activated_at, state=RawExactLinkageActivationState.ACTIVE)
    return RawExactLinkageActivation(**values, fingerprint=_hash(values))


def audit_raw_exact_linkage(*, forwards: Iterable[IsinIssuerForwardObservation], anchors: Iterable[IsinIssuerAnchorBridge], issuer_evidence: Iterable[ExactIssuerIdentifierEvidence], regulator_evidence: Iterable[RegulatorEntityEvidence], as_of: datetime) -> RawExactLinkageAudit:
    """Read-only RAW_EXACT audit. No name is transformed beyond NFC/trim."""
    if not _aware(as_of): raise RegulatorIssuerRawExactLinkageError("RAW_EXACT_LINKAGE_AS_OF_INVALID")
    facts = _issuer_name_facts(forwards, anchors, issuer_evidence, _utc(as_of)); regulators = tuple(sorted(regulator_evidence, key=lambda value: value.evidence_id))
    names: dict[str, set[str]] = {}; names_by_cin: dict[str, set[str]] = {}
    for item in facts:
        key = _raw(item.legal_name); names.setdefault(key, set()).add(item.cin); names_by_cin.setdefault(item.cin, set()).add(key)
    by_family_name: dict[tuple[RegulatorEvidenceSource, str], list[RegulatorEntityEvidence]] = {}
    for item in regulators: by_family_name.setdefault((item.source, _raw(item.legal_name)), []).append(item)
    candidates: list[tuple[RawExactIssuerNameFact, RegulatorEntityEvidence]] = []
    evaluations: list[RawExactLinkageEvaluation] = []
    for (family, name), rows in sorted(by_family_name.items(), key=lambda item: (item[0][0].value, item[0][1])):
        cins = names.get(name, set())
        if not cins: continue
        if len(rows) != 1:
            evaluations.extend(_evaluation(None, None, row, RawExactLinkageStatus.EVIDENCE_CONFLICTED, (RawExactLinkageReason.REGULATOR_NAME_AMBIGUOUS,)) for row in rows); continue
        if len(cins) != 1:
            evaluations.append(_evaluation(None, None, rows[0], RawExactLinkageStatus.EVIDENCE_CONFLICTED, (RawExactLinkageReason.CANONICAL_CIN_NAME_AMBIGUOUS,))); continue
        cin = next(iter(cins))
        if len(names_by_cin[cin]) != 1:
            evaluations.append(_evaluation(cin, None, rows[0], RawExactLinkageStatus.EVIDENCE_CONFLICTED, (RawExactLinkageReason.CANONICAL_CIN_NAME_AMBIGUOUS,))); continue
        fact = next(item for item in facts if item.cin == cin and _raw(item.legal_name) == name)
        candidates.append((fact, rows[0]))
    conflicting_cins = {fact.cin for fact, row in candidates if len({other.source for other_fact, other in candidates if other_fact.cin == fact.cin}) > 1}
    for fact, row in candidates:
        if fact.cin in conflicting_cins:
            evaluations.append(_evaluation(fact.cin, fact, row, RawExactLinkageStatus.EVIDENCE_CONFLICTED, (RawExactLinkageReason.CROSS_REGULATOR_FAMILY_CONFLICT,))); continue
        reason = RawExactLinkageReason.RAW_EXACT_UNIQUE
        status = RawExactLinkageStatus.IDENTITY_VALID if _utc(fact.issuer_known_at) <= _utc(as_of) and _utc(row.observed_at) <= _utc(as_of) else RawExactLinkageStatus.PIT_EVIDENCE_TOO_LATE
        if _utc(fact.issuer_known_at) > _utc(as_of): reason = RawExactLinkageReason.ISSUER_EVIDENCE_AFTER_AS_OF
        elif _utc(row.observed_at) > _utc(as_of): reason = RawExactLinkageReason.REGULATOR_EVIDENCE_AFTER_AS_OF
        evaluations.append(_evaluation(fact.cin, fact, row, status, (reason,)))
    values = tuple(sorted(evaluations, key=_evaluation_key))
    # A candidate has passed the approved name/uniqueness boundary even when it
    # is not yet usable at this as-of.  Keep that structural result distinct
    # from PIT-valid links: a later observed regulator list cannot rewrite
    # history into an identity match that was known at an earlier point.
    identity_candidates = sum(
        item.status in {RawExactLinkageStatus.IDENTITY_VALID, RawExactLinkageStatus.PIT_EVIDENCE_TOO_LATE}
        for item in values
    )
    active_links = sum(item.status is RawExactLinkageStatus.IDENTITY_VALID for item in values)
    counts = (len({item.cin for item in facts}), identity_candidates, active_links)
    return RawExactLinkageAudit(_utc(as_of), *counts, values, _hash(_audit_payload_values(_utc(as_of), *counts, values)))


def activate_raw_exact_links(*, activation: RawExactLinkageActivation, audit: RawExactLinkageAudit, forwards: Iterable[IsinIssuerForwardObservation], anchors: Iterable[IsinIssuerAnchorBridge], issuer_evidence: Iterable[ExactIssuerIdentifierEvidence], regulator_evidence: Iterable[RegulatorEntityEvidence]) -> tuple[RawExactRegulatorIssuerLink, ...]:
    """Create links only from identity/PIT-valid audit rows; never classify."""
    activation.__post_init__(); audit.__post_init__()
    supplied_forwards, supplied_anchors, supplied_issuer_evidence, supplied_regulator_evidence = tuple(forwards), tuple(anchors), tuple(issuer_evidence), tuple(regulator_evidence)
    if audit != audit_raw_exact_linkage(forwards=supplied_forwards, anchors=supplied_anchors, issuer_evidence=supplied_issuer_evidence, regulator_evidence=supplied_regulator_evidence, as_of=audit.as_of):
        raise RegulatorIssuerRawExactLinkageError("RAW_EXACT_LINKAGE_AUDIT_LINEAGE_UNAVAILABLE")
    facts = _issuer_name_facts(supplied_forwards, supplied_anchors, supplied_issuer_evidence, audit.as_of); by_issuer_evidence = {(item.cin, item.issuer_evidence_id): item for item in facts}; by_regulator = {item.evidence_id: item for item in supplied_regulator_evidence}
    links: list[RawExactRegulatorIssuerLink] = []
    for item in audit.evaluations:
        if item.status is not RawExactLinkageStatus.IDENTITY_VALID or item.cin is None or item.regulator_evidence_id is None: continue
        fact, regulator = by_issuer_evidence.get((item.cin, item.issuer_evidence_id)), by_regulator.get(item.regulator_evidence_id)
        if fact is None or regulator is None or (fact.legal_name, fact.issuer_evidence_id, fact.issuer_evidence_fingerprint, _utc(fact.issuer_known_at)) != (item.canonical_legal_name, item.issuer_evidence_id, item.issuer_evidence_fingerprint, item.issuer_known_at) or regulator.fingerprint != item.regulator_evidence_fingerprint:
            raise RegulatorIssuerRawExactLinkageError("RAW_EXACT_LINKAGE_AUDIT_LINEAGE_UNAVAILABLE")
        values = dict(policy_id=activation.policy_id, policy_version=activation.policy_version, policy_fingerprint=activation.policy_fingerprint, approval_id=activation.approval_id, activation_id=activation.selection_id, cin=fact.cin, canonical_legal_name=fact.legal_name, issuer_evidence_id=fact.issuer_evidence_id, issuer_evidence_fingerprint=fact.issuer_evidence_fingerprint, issuer_known_at=_utc(fact.issuer_known_at), regulator_evidence_id=regulator.evidence_id, regulator_evidence_fingerprint=regulator.fingerprint, regulator_legal_name=regulator.legal_name, regulator_family=regulator.source, regulator_subtype=regulator.regulator_subtype, regulator_known_at=_utc(regulator.observed_at), link_known_at=max(_utc(fact.issuer_known_at), _utc(regulator.observed_at)), state=RawExactLinkageState.ACTIVE)
        link_id = _link_id(_link_identity_values(values)); links.append(RawExactRegulatorIssuerLink(link_id=link_id, **values, fingerprint=_hash(_link_payload_values(values | {"link_id": link_id}))))
    return tuple(sorted(links, key=lambda value: value.link_id))


def persist_raw_exact_linkage(*, store: RawExactLinkageStore, policy: RawExactLinkagePolicy, approval: RawExactLinkageApproval, activation: RawExactLinkageActivation, links: Iterable[RawExactRegulatorIssuerLink]) -> tuple[int, int]:
    inserted = present = 0
    for value, save in ((policy, store.save_policy), (approval, store.save_approval), (activation, store.save_activation)):
        outcome = save(value); inserted += outcome is RawExactLinkageWriteOutcome.INSERTED; present += outcome is RawExactLinkageWriteOutcome.ALREADY_PRESENT
    for value in links:
        outcome = store.save_link(value); inserted += outcome is RawExactLinkageWriteOutcome.INSERTED; present += outcome is RawExactLinkageWriteOutcome.ALREADY_PRESENT
    return inserted, present


def _issuer_name_facts(forwards: Iterable[IsinIssuerForwardObservation], anchors: Iterable[IsinIssuerAnchorBridge], evidence: Iterable[ExactIssuerIdentifierEvidence], as_of: datetime) -> tuple[RawExactIssuerNameFact, ...]:
    by_anchor = {item.bridge_id: item for item in anchors}; by_evidence = {item.evidence_id: item for item in evidence}; collected: dict[tuple[str, str, str], list[str]] = {}; known: dict[tuple[str, str, str], datetime] = {}; fingerprints: dict[tuple[str, str, str], str] = {}
    for forward in forwards:
        if forward.later_session_date > as_of.date() or any(_utc(value) > as_of for value in forward.anchor_known_ats): continue
        for bridge_id in forward.anchor_bridge_ids:
            bridge = by_anchor.get(bridge_id)
            item = None if bridge is None else by_evidence.get(bridge.brsr_evidence_id)
            if bridge is None or item is None or item.source is not IssuerIdentifierEvidenceSource.NSE_BRSR_ARCHIVE or item.issuer_identifier_type is not IssuerIdentifierType.CIN or item.issuer_identifier_value != forward.cin or not item.issuer_legal_name or item.historical_known_at is None: continue
            if _utc(item.historical_known_at) != _utc(bridge.issuer_known_at): raise RegulatorIssuerRawExactLinkageError("RAW_EXACT_LINKAGE_ISSUER_KNOWNNESS_CONFLICT")
            key = (forward.cin, item.issuer_legal_name, item.evidence_id); collected.setdefault(key, []).append(forward.observation_id); known[key] = _utc(item.historical_known_at); fingerprints[key] = item.fingerprint
    return tuple(sorted((RawExactIssuerNameFact(cin, name, evidence_id, fingerprints[(cin, name, evidence_id)], known[(cin, name, evidence_id)], tuple(sorted(set(observations)))) for (cin, name, evidence_id), observations in collected.items()), key=lambda value: (value.cin, value.legal_name, value.issuer_evidence_id)))


def _evaluation(cin: str | None, fact: RawExactIssuerNameFact | None, row: RegulatorEntityEvidence, status: RawExactLinkageStatus, reasons: tuple[RawExactLinkageReason, ...]) -> RawExactLinkageEvaluation:
    return RawExactLinkageEvaluation(cin, None if fact is None else fact.legal_name, None if fact is None else fact.issuer_evidence_id, None if fact is None else fact.issuer_evidence_fingerprint, row.evidence_id, row.fingerprint, row.source, row.regulator_subtype, status, reasons, None if fact is None else fact.issuer_known_at, row.observed_at)
def _evaluation_key(value: RawExactLinkageEvaluation) -> tuple[str, str, str]: return (value.regulator_family.value if value.regulator_family else "", value.regulator_evidence_id or "", value.cin or "")
def _raw(value: str) -> str: return unicodedata.normalize("NFC", value).strip()
def _policy_identity() -> tuple[str, str, str]:
    policy = create_raw_exact_linkage_policy(); return policy.policy_id, policy.policy_version, policy.fingerprint
def _policy_payload(value: RawExactLinkagePolicy) -> dict[str, object]: return {"policy_id": value.policy_id, "policy_version": value.policy_version, "semantics": tuple(item.value for item in value.semantics), "contract_id": value.contract_id, "contract_version": value.contract_version}
def _approval_payload(value: RawExactLinkageApproval) -> dict[str, object]: return _payload(value, {"fingerprint", "contract_id", "contract_version"})
def _activation_payload(value: RawExactLinkageActivation) -> dict[str, object]: return _payload(value, {"fingerprint", "contract_id", "contract_version"})
def _audit_payload(value: RawExactLinkageAudit) -> dict[str, object]: return _audit_payload_values(value.as_of, value.active_issuer_cins, value.identity_candidates, value.active_links, value.evaluations)
def _audit_payload_values(as_of: datetime, cins: int, candidates: int, links: int, values: tuple[RawExactLinkageEvaluation, ...]) -> dict[str, object]: return {"as_of": _time(as_of), "active_issuer_cins": cins, "identity_candidates": candidates, "active_links": links, "evaluations": tuple(_payload(item, set()) for item in values)}
def _link_identity(value: RawExactRegulatorIssuerLink) -> dict[str, object]: return _link_identity_values({field.name: getattr(value, field.name) for field in fields(value)})
def _link_identity_values(value: dict[str, object]) -> dict[str, object]: return {key: _scalar(value[key]) for key in ("policy_id", "policy_version", "policy_fingerprint", "cin", "issuer_evidence_id", "issuer_evidence_fingerprint", "regulator_evidence_id", "regulator_evidence_fingerprint")}
def _link_id(value: dict[str, object]) -> str: return "regulator-issuer-raw-exact:" + _hash(value)[7:39]
def _link_payload(value: RawExactRegulatorIssuerLink) -> dict[str, object]: return _link_payload_values({field.name: getattr(value, field.name) for field in fields(value) if field.name not in {"fingerprint", "contract_id", "contract_version"}})
def _link_payload_values(value: dict[str, object]) -> dict[str, object]: return {key: _scalar(item) for key, item in value.items()}
def _link_valid(value: RawExactRegulatorIssuerLink) -> bool: return all((_identifier(value.link_id), (value.policy_id, value.policy_version, value.policy_fingerprint) == _policy_identity(), _identifier(value.approval_id), _identifier(value.activation_id), _CIN.fullmatch(value.cin) is not None, _nonblank(value.canonical_legal_name), _identifier(value.issuer_evidence_id), _fingerprint(value.issuer_evidence_fingerprint), _identifier(value.regulator_evidence_id), _fingerprint(value.regulator_evidence_fingerprint), _nonblank(value.regulator_legal_name), _raw(value.canonical_legal_name) == _raw(value.regulator_legal_name), isinstance(value.regulator_family, RegulatorEvidenceSource), value.regulator_subtype is None or _nonblank(value.regulator_subtype), _aware(value.issuer_known_at) and _aware(value.regulator_known_at) and _aware(value.link_known_at), value.link_known_at == max(_utc(value.issuer_known_at), _utc(value.regulator_known_at)), value.state is RawExactLinkageState.ACTIVE, value.contract_id == CONTRACT_ID and value.contract_version == CONTRACT_VERSION))
def _payload(value: object, omit: set[str]) -> dict[str, object]: return {field.name: _scalar(getattr(value, field.name)) for field in fields(value) if field.name not in omit}
def _hash(value: object) -> str: return "sha256:" + sha256(json.dumps(_scalar(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()
def _scalar(value: object) -> object:
    if isinstance(value, StrEnum): return value.value
    if isinstance(value, datetime): return _time(value)
    if isinstance(value, tuple): return tuple(_scalar(item) for item in value)
    if isinstance(value, dict): return {str(key): _scalar(item) for key, item in value.items()}
    return value
def _identifier(value: object) -> bool: return isinstance(value, str) and _ID.fullmatch(value) is not None
def _fingerprint(value: object) -> bool: return isinstance(value, str) and _FP.fullmatch(value) is not None
def _nonblank(value: object) -> bool: return isinstance(value, str) and bool(value.strip())
def _aware(value: object) -> bool: return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None
def _utc(value: datetime) -> datetime:
    if not _aware(value): raise RegulatorIssuerRawExactLinkageError("RAW_EXACT_LINKAGE_AWARE_TIMESTAMP_REQUIRED")
    return value.astimezone(UTC)
def _time(value: datetime) -> str: return _utc(value).isoformat()


__all__ = ("CONTRACT_ID", "CONTRACT_VERSION", "POLICY_ID", "POLICY_VERSION", "RawExactLinkageActivation", "RawExactLinkageApproval", "RawExactLinkageApprovalState", "RawExactLinkageAudit", "RawExactLinkagePolicy", "RawExactLinkageReason", "RawExactLinkageState", "RawExactLinkageStatus", "RawExactLinkageStore", "RawExactRegulatorIssuerLink", "RawExactLinkageSemantic", "activate_raw_exact_linkage_policy", "activate_raw_exact_links", "approve_raw_exact_linkage_policy", "audit_raw_exact_linkage", "create_raw_exact_linkage_policy", "persist_raw_exact_linkage")
