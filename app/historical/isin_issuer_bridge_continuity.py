"""Activated, exact ISIN-to-CIN continuity receipts.

This module consumes only approved BRSR/MII anchor evidence plus later exact
NSE session-point identities.  It is deliberately not an issuer master: an
anchor is known only at its BRSR timestamp and a later issuer observation is
created only for a strictly later, exact same-ISIN session receipt.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
import hashlib
import json
import re
from typing import Iterable

from app.historical.brsr_issuer_anchor_backfill import (
    BrsrIssuerAnchorReady,
    POLICY_ID as ANCHOR_POLICY_ID,
    POLICY_VERSION as ANCHOR_POLICY_VERSION,
)
from app.historical.nse_session_identity import NseSessionPointIdentity, NseSessionIdentitySemantic
from app.storage.core_api_snapshot_repository import (
    CoreApiSnapshot, CoreApiSnapshotFamily, CoreApiSnapshotRepository,
)


POLICY_ID = "isin-issuer-bridge-continuity-policy"
POLICY_VERSION = "v1"
CONTRACT_ID = "isin-issuer-bridge-continuity-activation"
CONTRACT_VERSION = "v1"
_ID = re.compile(r"[A-Za-z0-9._:-]+\Z")
_FP = re.compile(r"sha256:[0-9a-f]{64}\Z")
_CIN = re.compile(r"[LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}\Z")
_ISIN = re.compile(r"[A-Z]{2}[A-Z0-9]{9}[0-9]\Z")


class IsinIssuerBridgeContinuityError(ValueError):
    """Stable fail-closed error at the activated issuer-continuity boundary."""


class IsinIssuerBridgeContinuitySemantic(StrEnum):
    EXACT_ANCHOR_REQUIRED = "EXACT_ANCHOR_REQUIRED"
    ANCHOR_KNOWN_AT_BRSR_SUBMISSION_TIMESTAMP = "ANCHOR_KNOWN_AT_BRSR_SUBMISSION_TIMESTAMP"
    STRICTLY_FORWARD_SAME_ISIN_ONLY = "STRICTLY_FORWARD_SAME_ISIN_ONLY"
    SAME_SYMBOL_CHANGED_ISIN_NOT_CONTINUITY = "SAME_SYMBOL_CHANGED_ISIN_NOT_CONTINUITY"
    NO_BACKWARD_PROPAGATION = "NO_BACKWARD_PROPAGATION"
    EXACT_LIFECYCLE_DISCONTINUITY_BLOCKS = "EXACT_LIFECYCLE_DISCONTINUITY_BLOCKS"


class IsinIssuerBridgeContinuityApprovalState(StrEnum):
    APPROVED = "APPROVED"


class IsinIssuerBridgeContinuityActivationState(StrEnum):
    ACTIVE = "ACTIVE"


class IsinIssuerBridgeState(StrEnum):
    ACTIVE = "ACTIVE"


class IsinIssuerBridgeResolutionStatus(StrEnum):
    ISSUER_ANCHOR_PRESENT = "ISSUER_ANCHOR_PRESENT"
    PRE_ANCHOR_KNOWN_AT = "PRE_ANCHOR_KNOWN_AT"
    ISSUER_BRIDGE_UNAVAILABLE = "ISSUER_BRIDGE_UNAVAILABLE"
    EVIDENCE_CONFLICTED = "EVIDENCE_CONFLICTED"


class IsinIssuerBridgeReason(StrEnum):
    EXACT_ACTIVE_ANCHOR_PRESENT = "EXACT_ACTIVE_ANCHOR_PRESENT"
    ANCHOR_KNOWN_AT_NOT_REACHED = "ANCHOR_KNOWN_AT_NOT_REACHED"
    EXACT_ACTIVE_ANCHOR_REQUIRED = "EXACT_ACTIVE_ANCHOR_REQUIRED"
    CONFLICTING_ISIN_CIN_ANCHORS = "CONFLICTING_ISIN_CIN_ANCHORS"


class IsinIssuerBridgeWriteOutcome(StrEnum):
    INSERTED = "INSERTED"
    ALREADY_PRESENT = "ALREADY_PRESENT"


@dataclass(frozen=True, slots=True)
class IsinIssuerBridgeContinuityPolicy:
    policy_id: str
    policy_version: str
    semantics: tuple[IsinIssuerBridgeContinuitySemantic, ...]
    fingerprint: str
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        if (
            self.policy_id != POLICY_ID
            or self.policy_version != POLICY_VERSION
            or self.semantics != _SEMANTICS
            or self.contract_id != CONTRACT_ID
            or self.contract_version != CONTRACT_VERSION
            or self.fingerprint != _hash(_policy_payload(self))
        ):
            raise IsinIssuerBridgeContinuityError("ISIN_ISSUER_CONTINUITY_POLICY_INVALID")


_SEMANTICS = (
    IsinIssuerBridgeContinuitySemantic.EXACT_ANCHOR_REQUIRED,
    IsinIssuerBridgeContinuitySemantic.ANCHOR_KNOWN_AT_BRSR_SUBMISSION_TIMESTAMP,
    IsinIssuerBridgeContinuitySemantic.STRICTLY_FORWARD_SAME_ISIN_ONLY,
    IsinIssuerBridgeContinuitySemantic.SAME_SYMBOL_CHANGED_ISIN_NOT_CONTINUITY,
    IsinIssuerBridgeContinuitySemantic.NO_BACKWARD_PROPAGATION,
    IsinIssuerBridgeContinuitySemantic.EXACT_LIFECYCLE_DISCONTINUITY_BLOCKS,
)


@dataclass(frozen=True, slots=True)
class IsinIssuerBridgeContinuityPolicyApproval:
    approval_id: str
    policy_id: str
    policy_version: str
    policy_fingerprint: str
    approved_by: str
    approved_at: datetime
    state: IsinIssuerBridgeContinuityApprovalState
    fingerprint: str
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        policy = create_isin_issuer_bridge_continuity_policy()
        if not (
            _identifier(self.approval_id)
            and (self.policy_id, self.policy_version, self.policy_fingerprint)
            == (policy.policy_id, policy.policy_version, policy.fingerprint)
            and self.approved_by.startswith("human:")
            and _aware(self.approved_at)
            and self.state is IsinIssuerBridgeContinuityApprovalState.APPROVED
            and self.contract_id == CONTRACT_ID
            and self.contract_version == CONTRACT_VERSION
            and self.fingerprint == _hash(_approval_payload(self))
        ):
            raise IsinIssuerBridgeContinuityError("ISIN_ISSUER_CONTINUITY_APPROVAL_INVALID")


@dataclass(frozen=True, slots=True)
class IsinIssuerBridgeContinuityActivation:
    selection_id: str
    approval_id: str
    approval_fingerprint: str
    policy_id: str
    policy_version: str
    policy_fingerprint: str
    activated_by: str
    activated_at: datetime
    state: IsinIssuerBridgeContinuityActivationState
    fingerprint: str
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not (
            _identifier(self.selection_id)
            and _identifier(self.approval_id)
            and _fingerprint(self.approval_fingerprint)
            and (self.policy_id, self.policy_version, self.policy_fingerprint)
            == _policy_identity()
            and self.activated_by.startswith("human:")
            and _aware(self.activated_at)
            and self.state is IsinIssuerBridgeContinuityActivationState.ACTIVE
            and self.contract_id == CONTRACT_ID
            and self.contract_version == CONTRACT_VERSION
            and self.fingerprint == _hash(_activation_payload(self))
        ):
            raise IsinIssuerBridgeContinuityError("ISIN_ISSUER_CONTINUITY_ACTIVATION_INVALID")


@dataclass(frozen=True, slots=True)
class IsinIssuerAnchorBridge:
    """One active exact anchor receipt; never a timeless issuer master."""

    bridge_id: str
    policy_id: str
    policy_version: str
    policy_fingerprint: str
    approval_id: str
    activation_id: str
    anchor_id: str
    anchor_fingerprint: str
    isin: str
    cin: str
    anchor_symbol: str
    anchor_session_date: date
    issuer_known_at: datetime
    brsr_evidence_id: str
    brsr_evidence_fingerprint: str
    mii_snapshot_id: str
    mii_snapshot_fingerprint: str
    mii_row_ids: tuple[str, ...]
    mii_row_fingerprints: tuple[str, ...]
    state: IsinIssuerBridgeState
    fingerprint: str
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not _anchor_bridge_valid(self) or self.bridge_id != _anchor_bridge_id(_anchor_bridge_identity(self)) or self.fingerprint != _hash(_anchor_bridge_payload(self)):
            raise IsinIssuerBridgeContinuityError("ISIN_ISSUER_ANCHOR_BRIDGE_INVALID")

    def verify(self) -> None:
        self.__post_init__()


@dataclass(frozen=True, slots=True)
class IsinIssuerForwardObservation:
    """A later same-ISIN observation with every compatible anchor retained."""

    observation_id: str
    policy_id: str
    policy_version: str
    policy_fingerprint: str
    approval_id: str
    activation_id: str
    later_session_receipt_ids: tuple[str, ...]
    later_session_fingerprints: tuple[str, ...]
    later_session_date: date
    isin: str
    later_symbol: str
    cin: str
    anchor_bridge_ids: tuple[str, ...]
    anchor_bridge_fingerprints: tuple[str, ...]
    anchor_known_ats: tuple[datetime, ...]
    state: IsinIssuerBridgeState
    fingerprint: str
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not _forward_observation_valid(self) or self.observation_id != _forward_observation_id(_forward_observation_identity(self)) or self.fingerprint != _hash(_forward_observation_payload(self)):
            raise IsinIssuerBridgeContinuityError("ISIN_ISSUER_FORWARD_OBSERVATION_INVALID")

    def verify(self) -> None:
        self.__post_init__()


@dataclass(frozen=True, slots=True)
class ExactNseLifecycleDiscontinuity:
    """Optional, supplied exact NSE discontinuity input; BSE evidence is excluded."""

    evidence_id: str
    evidence_fingerprint: str
    isin: str
    known_at: datetime
    effective_on: date
    source_reference: str

    def __post_init__(self) -> None:
        if not (
            _identifier(self.evidence_id) and _fingerprint(self.evidence_fingerprint)
            and _ISIN.fullmatch(self.isin) is not None and _aware(self.known_at)
            and isinstance(self.effective_on, date) and self.effective_on >= _utc(self.known_at).date()
            and self.source_reference.startswith("https://www.nseindia.com/")
        ):
            raise IsinIssuerBridgeContinuityError("ISIN_ISSUER_NSE_LIFECYCLE_DISCONTINUITY_INVALID")


@dataclass(frozen=True, slots=True)
class IsinIssuerAnchorActivationResult:
    activation_id: str
    bridges: tuple[IsinIssuerAnchorBridge, ...]
    conflicted_anchor_ids: tuple[str, ...]
    fingerprint: str

    def __post_init__(self) -> None:
        if (
            not _identifier(self.activation_id)
            or self.bridges != tuple(sorted(set(self.bridges), key=lambda value: value.bridge_id))
            or self.conflicted_anchor_ids != tuple(sorted(set(self.conflicted_anchor_ids)))
            or set(self.conflicted_anchor_ids) & {value.anchor_id for value in self.bridges}
            or self.fingerprint != _hash(_anchor_result_payload(self))
        ):
            raise IsinIssuerBridgeContinuityError("ISIN_ISSUER_ANCHOR_ACTIVATION_RESULT_INVALID")


@dataclass(frozen=True, slots=True)
class IsinIssuerForwardActivationResult:
    activation_id: str
    observations: tuple[IsinIssuerForwardObservation, ...]
    absent_anchor_isins: tuple[str, ...]
    conflicted_isins: tuple[str, ...]
    lifecycle_blocked_isins: tuple[str, ...]
    non_forward_anchor_ids: tuple[str, ...]
    fingerprint: str

    def __post_init__(self) -> None:
        collections = (
            (self.observations, tuple(sorted(set(self.observations), key=lambda value: value.observation_id))),
            (self.absent_anchor_isins, tuple(sorted(set(self.absent_anchor_isins)))),
            (self.conflicted_isins, tuple(sorted(set(self.conflicted_isins)))),
            (self.lifecycle_blocked_isins, tuple(sorted(set(self.lifecycle_blocked_isins)))),
            (self.non_forward_anchor_ids, tuple(sorted(set(self.non_forward_anchor_ids)))),
        )
        if not _identifier(self.activation_id) or any(left != right for left, right in collections) or not all(_ISIN.fullmatch(value) for value in self.absent_anchor_isins + self.conflicted_isins + self.lifecycle_blocked_isins) or not all(_identifier(value) for value in self.non_forward_anchor_ids) or self.fingerprint != _hash(_forward_result_payload(self)):
            raise IsinIssuerBridgeContinuityError("ISIN_ISSUER_FORWARD_ACTIVATION_RESULT_INVALID")


@dataclass(frozen=True, slots=True)
class IsinIssuerBridgeResolution:
    isin: str
    as_of: datetime
    status: IsinIssuerBridgeResolutionStatus
    bridges: tuple[IsinIssuerAnchorBridge, ...]
    reasons: tuple[IsinIssuerBridgeReason, ...]
    fingerprint: str

    def __post_init__(self) -> None:
        if not (
            _ISIN.fullmatch(self.isin) and _aware(self.as_of)
            and self.bridges == tuple(sorted(set(self.bridges), key=lambda value: value.bridge_id))
            and self.reasons == tuple(sorted(set(self.reasons), key=lambda value: value.value))
            and all(isinstance(value, IsinIssuerBridgeReason) for value in self.reasons)
            and self.fingerprint == _hash(_resolution_payload(self))
        ):
            raise IsinIssuerBridgeContinuityError("ISIN_ISSUER_BRIDGE_RESOLUTION_INVALID")
        expected = {
            IsinIssuerBridgeResolutionStatus.ISSUER_ANCHOR_PRESENT: (True, (IsinIssuerBridgeReason.EXACT_ACTIVE_ANCHOR_PRESENT,)),
            IsinIssuerBridgeResolutionStatus.PRE_ANCHOR_KNOWN_AT: (False, (IsinIssuerBridgeReason.ANCHOR_KNOWN_AT_NOT_REACHED,)),
            IsinIssuerBridgeResolutionStatus.ISSUER_BRIDGE_UNAVAILABLE: (False, (IsinIssuerBridgeReason.EXACT_ACTIVE_ANCHOR_REQUIRED,)),
            IsinIssuerBridgeResolutionStatus.EVIDENCE_CONFLICTED: (True, (IsinIssuerBridgeReason.CONFLICTING_ISIN_CIN_ANCHORS,)),
        }[self.status]
        if bool(self.bridges) is not expected[0] or self.reasons != expected[1]:
            raise IsinIssuerBridgeContinuityError("ISIN_ISSUER_BRIDGE_RESOLUTION_STATE_CONTRADICTION")
        if self.status is IsinIssuerBridgeResolutionStatus.ISSUER_ANCHOR_PRESENT and any(_utc(value.issuer_known_at) > _utc(self.as_of) for value in self.bridges):
            raise IsinIssuerBridgeContinuityError("ISIN_ISSUER_BRIDGE_RESOLUTION_FUTURE_ANCHOR")


class IsinIssuerBridgeContinuityStore:
    """Append-only active continuity receipts in the existing bridge family."""

    def __init__(self, repository: CoreApiSnapshotRepository) -> None:
        self._repository = repository

    def save_approval(self, value: IsinIssuerBridgeContinuityPolicyApproval) -> IsinIssuerBridgeWriteOutcome:
        return self._save("isin-issuer-continuity-approval:" + value.approval_id, "isin-issuer-continuity-approval-v1", value, value.approved_at)

    def save_activation(self, value: IsinIssuerBridgeContinuityActivation) -> IsinIssuerBridgeWriteOutcome:
        return self._save("isin-issuer-continuity-activation:" + value.selection_id, "isin-issuer-continuity-activation-v1", value, value.activated_at)

    def save_anchor_bridge(self, value: IsinIssuerAnchorBridge, *, observed_at: datetime) -> IsinIssuerBridgeWriteOutcome:
        value.verify()
        return self._save(value.bridge_id, "isin-issuer-anchor-bridge-v1", value, observed_at)

    def save_forward_observation(self, value: IsinIssuerForwardObservation, *, observed_at: datetime) -> IsinIssuerBridgeWriteOutcome:
        value.verify()
        return self._save(value.observation_id, "isin-issuer-forward-observation-v1", value, observed_at)

    def anchor_bridges(self) -> tuple[IsinIssuerAnchorBridge, ...]:
        return tuple(sorted((item.payload for item in self._all() if isinstance(item.payload, IsinIssuerAnchorBridge)), key=lambda value: value.bridge_id))

    def forward_observations(self) -> tuple[IsinIssuerForwardObservation, ...]:
        return tuple(sorted((item.payload for item in self._all() if isinstance(item.payload, IsinIssuerForwardObservation)), key=lambda value: value.observation_id))

    def _save(self, snapshot_id: str, record_type: str, value: object, observed_at: datetime) -> IsinIssuerBridgeWriteOutcome:
        if not _aware(observed_at):
            raise IsinIssuerBridgeContinuityError("ISIN_ISSUER_CONTINUITY_OBSERVED_AT_REQUIRED")
        existing = self._repository.get_snapshot(snapshot_id)
        if existing is not None:
            if existing.family is CoreApiSnapshotFamily.HISTORICAL_ISSUER_SECURITY_BRIDGE and existing.payload == value:
                return IsinIssuerBridgeWriteOutcome.ALREADY_PRESENT
            raise IsinIssuerBridgeContinuityError("ISIN_ISSUER_CONTINUITY_IMMUTABLE_COLLISION")
        self._repository.save_snapshot(CoreApiSnapshot(snapshot_id, CoreApiSnapshotFamily.HISTORICAL_ISSUER_SECURITY_BRIDGE, "v1", record_type, getattr(value, "fingerprint"), _utc(observed_at), value))
        return IsinIssuerBridgeWriteOutcome.INSERTED

    def _all(self) -> tuple[CoreApiSnapshot, ...]:
        values: list[CoreApiSnapshot] = []
        offset = 0
        while True:
            page = self._repository.list_snapshots(CoreApiSnapshotFamily.HISTORICAL_ISSUER_SECURITY_BRIDGE, limit=100, offset=offset)
            values.extend(page)
            if len(page) < 100:
                return tuple(values)
            offset += len(page)


def create_isin_issuer_bridge_continuity_policy() -> IsinIssuerBridgeContinuityPolicy:
    values = dict(policy_id=POLICY_ID, policy_version=POLICY_VERSION, semantics=_SEMANTICS)
    return IsinIssuerBridgeContinuityPolicy(**values, fingerprint=_hash(values | {"contract_id": CONTRACT_ID, "contract_version": CONTRACT_VERSION}))


def approve_isin_issuer_bridge_continuity_policy(*, approval_id: str, approved_by: str, approved_at: datetime) -> IsinIssuerBridgeContinuityPolicyApproval:
    policy = create_isin_issuer_bridge_continuity_policy()
    values = dict(approval_id=approval_id, policy_id=policy.policy_id, policy_version=policy.policy_version, policy_fingerprint=policy.fingerprint, approved_by=approved_by, approved_at=_utc(approved_at), state=IsinIssuerBridgeContinuityApprovalState.APPROVED)
    return IsinIssuerBridgeContinuityPolicyApproval(**values, fingerprint=_hash(values | {"contract_id": CONTRACT_ID, "contract_version": CONTRACT_VERSION}))


def activate_isin_issuer_bridge_continuity_policy(*, selection_id: str, approval: IsinIssuerBridgeContinuityPolicyApproval, activated_by: str, activated_at: datetime) -> IsinIssuerBridgeContinuityActivation:
    approval.__post_init__()
    values = dict(selection_id=selection_id, approval_id=approval.approval_id, approval_fingerprint=approval.fingerprint, policy_id=approval.policy_id, policy_version=approval.policy_version, policy_fingerprint=approval.policy_fingerprint, activated_by=activated_by, activated_at=_utc(activated_at), state=IsinIssuerBridgeContinuityActivationState.ACTIVE)
    if values["activated_at"] < _utc(approval.approved_at):
        raise IsinIssuerBridgeContinuityError("ISIN_ISSUER_CONTINUITY_ACTIVATION_PRECEDES_APPROVAL")
    return IsinIssuerBridgeContinuityActivation(**values, fingerprint=_hash(values | {"contract_id": CONTRACT_ID, "contract_version": CONTRACT_VERSION}))


def activate_isin_issuer_anchor_bridges(*, activation: IsinIssuerBridgeContinuityActivation, anchors: Iterable[BrsrIssuerAnchorReady]) -> IsinIssuerAnchorActivationResult:
    _validate_active_activation(activation)
    canonical = _canonical_anchors(anchors)
    conflicted = {anchor.anchor_id for group in _group_by_isin(canonical).values() if len({item.cin for item in group}) > 1 for anchor in group}
    bridges = tuple(sorted(
        (_anchor_bridge_from_anchor(activation, anchor) for anchor in canonical if anchor.anchor_id not in conflicted),
        key=lambda value: value.bridge_id,
    ))
    values = dict(activation_id=activation.selection_id, bridges=bridges, conflicted_anchor_ids=tuple(sorted(conflicted)))
    return IsinIssuerAnchorActivationResult(**values, fingerprint=_hash(_anchor_result_payload_from_values(values)))


def activate_forward_issuer_observations(*, activation: IsinIssuerBridgeContinuityActivation, anchor_bridges: Iterable[IsinIssuerAnchorBridge], later_session_receipts: Iterable[NseSessionPointIdentity], lifecycle_discontinuities: Iterable[ExactNseLifecycleDiscontinuity] = ()) -> IsinIssuerForwardActivationResult:
    _validate_active_activation(activation)
    anchors = _canonical_anchor_bridges(anchor_bridges)
    later = _canonical_later_receipts(later_session_receipts)
    lifecycle = _canonical_lifecycle(lifecycle_discontinuities)
    by_isin = _group_by_isin(anchors)
    conflicting = {isin for isin, group in by_isin.items() if len({item.cin for item in group}) > 1}
    observations: list[IsinIssuerForwardObservation] = []
    blocked: set[str] = set(); non_forward: set[str] = set(); present: set[str] = set()
    for (session_date, isin, _symbol), group in _group_later_by_session_isin_symbol(later).items():
        anchors_for_isin = by_isin.get(isin)
        if not anchors_for_isin:
            continue
        present.add(isin)
        # A group may contain compatible same-ISIN/same-symbol session
        # receipts from more than one official immutable snapshot. Preserve
        # every lineage rather than choosing one by input order. A different
        # same-ISIN symbol is a separate exact descriptive observation, not a
        # synthetic rename interval or an issuer-identity conflict.
        if isin in conflicting:
            blocked.add(isin)
            continue
        if any(session_date <= item.anchor_session_date for item in anchors_for_isin):
            non_forward.update(item.anchor_id for item in anchors_for_isin)
            continue
        if _lifecycle_blocks(lifecycle, isin=isin, session_date=session_date):
            blocked.add(isin)
            continue
        observations.append(_forward_observation_from(activation, anchors_for_isin, group))
    absent = tuple(sorted(set(by_isin) - present))
    lifecycle_isins = tuple(sorted(isin for isin in blocked if _lifecycle_blocks(lifecycle, isin=isin, session_date=max((item.session_date for item in later if item.isin == isin), default=date.min))))
    values = dict(activation_id=activation.selection_id, observations=tuple(sorted(observations, key=lambda value: value.observation_id)), absent_anchor_isins=absent, conflicted_isins=tuple(sorted(conflicting)), lifecycle_blocked_isins=lifecycle_isins, non_forward_anchor_ids=tuple(sorted(non_forward)))
    return IsinIssuerForwardActivationResult(**values, fingerprint=_hash(_forward_result_payload_from_values(values)))


def resolve_isin_issuer_anchor_at(*, bridges: Iterable[IsinIssuerAnchorBridge], isin: str, as_of: datetime) -> IsinIssuerBridgeResolution:
    if _ISIN.fullmatch(isin) is None or not _aware(as_of):
        raise IsinIssuerBridgeContinuityError("ISIN_ISSUER_BRIDGE_RESOLUTION_INPUT_INVALID")
    exact = tuple(value for value in _canonical_anchor_bridges(bridges) if value.isin == isin)
    if not exact:
        return _resolution(isin, as_of, IsinIssuerBridgeResolutionStatus.ISSUER_BRIDGE_UNAVAILABLE, (), (IsinIssuerBridgeReason.EXACT_ACTIVE_ANCHOR_REQUIRED,))
    if len({item.cin for item in exact}) != 1:
        return _resolution(isin, as_of, IsinIssuerBridgeResolutionStatus.EVIDENCE_CONFLICTED, exact, (IsinIssuerBridgeReason.CONFLICTING_ISIN_CIN_ANCHORS,))
    available = tuple(item for item in exact if _utc(item.issuer_known_at) <= _utc(as_of))
    if not available:
        return _resolution(isin, as_of, IsinIssuerBridgeResolutionStatus.PRE_ANCHOR_KNOWN_AT, (), (IsinIssuerBridgeReason.ANCHOR_KNOWN_AT_NOT_REACHED,))
    return _resolution(isin, as_of, IsinIssuerBridgeResolutionStatus.ISSUER_ANCHOR_PRESENT, available, (IsinIssuerBridgeReason.EXACT_ACTIVE_ANCHOR_PRESENT,))


def persist_isin_issuer_continuity(*, store: IsinIssuerBridgeContinuityStore, approval: IsinIssuerBridgeContinuityPolicyApproval, activation: IsinIssuerBridgeContinuityActivation, anchors: IsinIssuerAnchorActivationResult, forwards: IsinIssuerForwardActivationResult, observed_at: datetime) -> tuple[int, int, int, int]:
    """Persist only supplied immutable receipts, returning insert/present counts."""
    _validate_active_activation(activation)
    if anchors.activation_id != activation.selection_id or forwards.activation_id != activation.selection_id:
        raise IsinIssuerBridgeContinuityError("ISIN_ISSUER_CONTINUITY_RESULT_ACTIVATION_MISMATCH")
    inserted = present = 0
    for value in (approval, activation):
        outcome = store.save_approval(value) if isinstance(value, IsinIssuerBridgeContinuityPolicyApproval) else store.save_activation(value)
        inserted += outcome is IsinIssuerBridgeWriteOutcome.INSERTED; present += outcome is IsinIssuerBridgeWriteOutcome.ALREADY_PRESENT
    anchor_inserted = anchor_present = forward_inserted = forward_present = 0
    for value in anchors.bridges:
        outcome = store.save_anchor_bridge(value, observed_at=observed_at)
        anchor_inserted += outcome is IsinIssuerBridgeWriteOutcome.INSERTED; anchor_present += outcome is IsinIssuerBridgeWriteOutcome.ALREADY_PRESENT
    for value in forwards.observations:
        outcome = store.save_forward_observation(value, observed_at=observed_at)
        forward_inserted += outcome is IsinIssuerBridgeWriteOutcome.INSERTED; forward_present += outcome is IsinIssuerBridgeWriteOutcome.ALREADY_PRESENT
    if inserted + present != 2:
        raise IsinIssuerBridgeContinuityError("ISIN_ISSUER_CONTINUITY_GOVERNANCE_PERSISTENCE_INVALID")
    return anchor_inserted, anchor_present, forward_inserted, forward_present


def _anchor_bridge_from_anchor(activation: IsinIssuerBridgeContinuityActivation, anchor: BrsrIssuerAnchorReady) -> IsinIssuerAnchorBridge:
    anchor.verify()
    if (anchor.policy_id, anchor.policy_version) != (ANCHOR_POLICY_ID, ANCHOR_POLICY_VERSION):
        raise IsinIssuerBridgeContinuityError("ISIN_ISSUER_CONTINUITY_ANCHOR_POLICY_INVALID")
    rows = tuple(sorted(anchor.mii_rows, key=lambda value: value.mii_row_id))
    values = dict(policy_id=activation.policy_id, policy_version=activation.policy_version, policy_fingerprint=activation.policy_fingerprint, approval_id=activation.approval_id, activation_id=activation.selection_id, anchor_id=anchor.anchor_id, anchor_fingerprint=anchor.fingerprint, isin=anchor.isin, cin=anchor.cin, anchor_symbol=anchor.symbol, anchor_session_date=anchor.session_date, issuer_known_at=_utc(anchor.anchor_known_at), brsr_evidence_id=anchor.brsr_evidence_id, brsr_evidence_fingerprint=anchor.brsr_evidence_fingerprint, mii_snapshot_id=anchor.mii_snapshot_id, mii_snapshot_fingerprint=anchor.mii_raw_file_fingerprint, mii_row_ids=tuple(value.mii_row_id for value in rows), mii_row_fingerprints=tuple(value.mii_row_source_fingerprint for value in rows), state=IsinIssuerBridgeState.ACTIVE)
    bridge_id = _anchor_bridge_id(_anchor_bridge_identity_from_values(values))
    return IsinIssuerAnchorBridge(bridge_id=bridge_id, **values, fingerprint=_hash(_anchor_bridge_payload_from_values(values | {"bridge_id": bridge_id})))


def _forward_observation_from(activation: IsinIssuerBridgeContinuityActivation, anchors: tuple[IsinIssuerAnchorBridge, ...], later: tuple[NseSessionPointIdentity, ...]) -> IsinIssuerForwardObservation:
    later = tuple(sorted(later, key=lambda value: value.receipt_id))
    if not later:
        raise IsinIssuerBridgeContinuityError("ISIN_ISSUER_CONTINUITY_FORWARD_LINEAGE_INVALID")
    for receipt in later:
        _validate_later_receipt(receipt)
    if len({(item.session_date, item.isin, item.symbol) for item in later}) != 1:
        raise IsinIssuerBridgeContinuityError("ISIN_ISSUER_CONTINUITY_FORWARD_LINEAGE_INVALID")
    anchors = tuple(sorted(anchors, key=lambda value: value.bridge_id))
    canonical_later = later[0]
    if not anchors or any(item.isin != canonical_later.isin or item.cin != anchors[0].cin or canonical_later.session_date <= item.anchor_session_date for item in anchors):
        raise IsinIssuerBridgeContinuityError("ISIN_ISSUER_CONTINUITY_FORWARD_LINEAGE_INVALID")
    values = dict(policy_id=activation.policy_id, policy_version=activation.policy_version, policy_fingerprint=activation.policy_fingerprint, approval_id=activation.approval_id, activation_id=activation.selection_id, later_session_receipt_ids=tuple(item.receipt_id for item in later), later_session_fingerprints=tuple(item.fingerprint for item in later), later_session_date=canonical_later.session_date, isin=canonical_later.isin, later_symbol=canonical_later.symbol, cin=anchors[0].cin, anchor_bridge_ids=tuple(item.bridge_id for item in anchors), anchor_bridge_fingerprints=tuple(item.fingerprint for item in anchors), anchor_known_ats=tuple(_utc(item.issuer_known_at) for item in anchors), state=IsinIssuerBridgeState.ACTIVE)
    observation_id = _forward_observation_id(_forward_observation_identity_from_values(values))
    return IsinIssuerForwardObservation(observation_id=observation_id, **values, fingerprint=_hash(_forward_observation_payload_from_values(values | {"observation_id": observation_id})))


def _validate_active_activation(value: object) -> None:
    if not isinstance(value, IsinIssuerBridgeContinuityActivation):
        raise IsinIssuerBridgeContinuityError("ISIN_ISSUER_CONTINUITY_ACTIVATION_REQUIRED")
    value.__post_init__()


def _anchor_bridge_valid(value: IsinIssuerAnchorBridge) -> bool:
    return (
        _identifier(value.bridge_id) and _policy_fields(value) and _identifier(value.approval_id) and _identifier(value.activation_id)
        and _identifier(value.anchor_id) and _fingerprint(value.anchor_fingerprint) and _ISIN.fullmatch(value.isin) is not None and _CIN.fullmatch(value.cin) is not None
        # The anchor session is the exchange-labelled BRSR filing date.  Its
        # already-validated submission timestamp is normalized to UTC and may
        # fall on the preceding UTC calendar date; equating the two would
        # reject valid primary evidence rather than improve PIT safety.
        and _symbol(value.anchor_symbol) and isinstance(value.anchor_session_date, date) and _aware(value.issuer_known_at)
        and _identifier(value.brsr_evidence_id) and _fingerprint(value.brsr_evidence_fingerprint)
        and _identifier(value.mii_snapshot_id) and _fingerprint(value.mii_snapshot_fingerprint)
        and value.mii_row_ids == tuple(sorted(set(value.mii_row_ids))) and value.mii_row_ids and all(_identifier(item) for item in value.mii_row_ids)
        and len(value.mii_row_fingerprints) == len(value.mii_row_ids) and all(_fingerprint(item) for item in value.mii_row_fingerprints)
        and value.state is IsinIssuerBridgeState.ACTIVE and value.contract_id == CONTRACT_ID and value.contract_version == CONTRACT_VERSION
    )


def _forward_observation_valid(value: IsinIssuerForwardObservation) -> bool:
    return (
        _identifier(value.observation_id) and _policy_fields(value) and _identifier(value.approval_id) and _identifier(value.activation_id)
        and value.later_session_receipt_ids == tuple(sorted(set(value.later_session_receipt_ids))) and value.later_session_receipt_ids and all(_identifier(item) for item in value.later_session_receipt_ids)
        and len(value.later_session_fingerprints) == len(value.later_session_receipt_ids) and all(_fingerprint(item) for item in value.later_session_fingerprints) and isinstance(value.later_session_date, date)
        and _ISIN.fullmatch(value.isin) is not None and _symbol(value.later_symbol) and _CIN.fullmatch(value.cin) is not None
        and value.anchor_bridge_ids == tuple(sorted(set(value.anchor_bridge_ids))) and value.anchor_bridge_ids and all(_identifier(item) for item in value.anchor_bridge_ids)
        and len(value.anchor_bridge_fingerprints) == len(value.anchor_bridge_ids) and all(_fingerprint(item) for item in value.anchor_bridge_fingerprints)
        # The three anchor-lineage tuples are positionally paired in canonical
        # bridge-ID order.  Sorting timestamps independently would corrupt
        # that immutable ID/fingerprint/known-at association.
        and len(value.anchor_known_ats) == len(value.anchor_bridge_ids) and all(_aware(item) for item in value.anchor_known_ats)
        and value.state is IsinIssuerBridgeState.ACTIVE and value.contract_id == CONTRACT_ID and value.contract_version == CONTRACT_VERSION
    )


def _validate_later_receipt(value: object) -> None:
    if not isinstance(value, NseSessionPointIdentity) or value.semantic is not NseSessionIdentitySemantic.KNOWN_FOR_SESSION_D:
        raise IsinIssuerBridgeContinuityError("ISIN_ISSUER_CONTINUITY_LATER_SESSION_REQUIRED")
    value.__post_init__()


def _canonical_anchors(values: Iterable[BrsrIssuerAnchorReady]) -> tuple[BrsrIssuerAnchorReady, ...]:
    supplied = tuple(values); unique: dict[str, BrsrIssuerAnchorReady] = {}
    for value in supplied:
        if not isinstance(value, BrsrIssuerAnchorReady):
            raise IsinIssuerBridgeContinuityError("ISIN_ISSUER_CONTINUITY_ANCHOR_INPUT_INVALID")
        value.verify(); previous = unique.get(value.anchor_id)
        if previous is not None and previous != value:
            raise IsinIssuerBridgeContinuityError("ISIN_ISSUER_CONTINUITY_ANCHOR_INPUT_CONFLICTED")
        unique[value.anchor_id] = value
    return tuple(sorted(unique.values(), key=lambda value: value.anchor_id))


def _canonical_anchor_bridges(values: Iterable[IsinIssuerAnchorBridge]) -> tuple[IsinIssuerAnchorBridge, ...]:
    supplied = tuple(values); unique: dict[str, IsinIssuerAnchorBridge] = {}
    for value in supplied:
        if not isinstance(value, IsinIssuerAnchorBridge):
            raise IsinIssuerBridgeContinuityError("ISIN_ISSUER_CONTINUITY_BRIDGE_INPUT_INVALID")
        value.verify(); previous = unique.get(value.bridge_id)
        if previous is not None and previous != value:
            raise IsinIssuerBridgeContinuityError("ISIN_ISSUER_CONTINUITY_BRIDGE_INPUT_CONFLICTED")
        unique[value.bridge_id] = value
    return tuple(sorted(unique.values(), key=lambda value: value.bridge_id))


def _canonical_later_receipts(values: Iterable[NseSessionPointIdentity]) -> tuple[NseSessionPointIdentity, ...]:
    supplied = tuple(values); unique: dict[str, NseSessionPointIdentity] = {}
    for value in supplied:
        _validate_later_receipt(value); previous = unique.get(value.receipt_id)
        if previous is not None and previous != value:
            raise IsinIssuerBridgeContinuityError("ISIN_ISSUER_CONTINUITY_LATER_SESSION_CONFLICTED")
        unique[value.receipt_id] = value
    return tuple(sorted(unique.values(), key=lambda value: value.receipt_id))


def _canonical_lifecycle(values: Iterable[ExactNseLifecycleDiscontinuity]) -> tuple[ExactNseLifecycleDiscontinuity, ...]:
    supplied = tuple(values); unique: dict[str, ExactNseLifecycleDiscontinuity] = {}
    for value in supplied:
        if not isinstance(value, ExactNseLifecycleDiscontinuity):
            raise IsinIssuerBridgeContinuityError("ISIN_ISSUER_CONTINUITY_LIFECYCLE_INPUT_INVALID")
        previous = unique.get(value.evidence_id)
        if previous is not None and previous != value:
            raise IsinIssuerBridgeContinuityError("ISIN_ISSUER_CONTINUITY_LIFECYCLE_CONFLICTED")
        unique[value.evidence_id] = value
    return tuple(sorted(unique.values(), key=lambda value: value.evidence_id))


def _group_by_isin(values):
    groups = {}
    for value in values:
        groups.setdefault(value.isin, []).append(value)
    return {key: tuple(sorted(group, key=lambda value: getattr(value, "anchor_id", getattr(value, "bridge_id", "")))) for key, group in groups.items()}


def _group_later_by_session_isin_symbol(values: tuple[NseSessionPointIdentity, ...]) -> dict[tuple[date, str, str], tuple[NseSessionPointIdentity, ...]]:
    groups: dict[tuple[date, str, str], list[NseSessionPointIdentity]] = {}
    for value in values:
        groups.setdefault((value.session_date, value.isin, value.symbol), []).append(value)
    return {key: tuple(sorted(group, key=lambda value: value.receipt_id)) for key, group in groups.items()}


def _lifecycle_blocks(values: tuple[ExactNseLifecycleDiscontinuity, ...], *, isin: str, session_date: date) -> bool:
    return any(value.isin == isin and value.effective_on <= session_date and _utc(value.known_at).date() <= session_date for value in values)


def _resolution(isin, as_of, status, bridges, reasons) -> IsinIssuerBridgeResolution:
    values = dict(isin=isin, as_of=_utc(as_of), status=status, bridges=tuple(sorted(bridges, key=lambda value: value.bridge_id)), reasons=tuple(sorted(set(reasons), key=lambda value: value.value)))
    return IsinIssuerBridgeResolution(**values, fingerprint=_hash(_resolution_payload_from_values(values)))


def _policy_identity() -> tuple[str, str, str]:
    policy = create_isin_issuer_bridge_continuity_policy()
    return policy.policy_id, policy.policy_version, policy.fingerprint


def _policy_fields(value: object) -> bool:
    return isinstance(value, (IsinIssuerAnchorBridge, IsinIssuerForwardObservation)) and (value.policy_id, value.policy_version, value.policy_fingerprint) == _policy_identity()


def _policy_payload(value: IsinIssuerBridgeContinuityPolicy) -> dict[str, object]:
    return {"policy_id": value.policy_id, "policy_version": value.policy_version, "semantics": value.semantics, "contract_id": value.contract_id, "contract_version": value.contract_version}


def _approval_payload(value: IsinIssuerBridgeContinuityPolicyApproval) -> dict[str, object]:
    return _approval_payload_from_values({name: getattr(value, name) for name in value.__dataclass_fields__ if name != "fingerprint"})


def _approval_payload_from_values(value: dict[str, object]) -> dict[str, object]:
    return {**value, "contract_id": CONTRACT_ID, "contract_version": CONTRACT_VERSION}


def _activation_payload(value: IsinIssuerBridgeContinuityActivation) -> dict[str, object]:
    return _activation_payload_from_values({name: getattr(value, name) for name in value.__dataclass_fields__ if name != "fingerprint"})


def _activation_payload_from_values(value: dict[str, object]) -> dict[str, object]:
    return {**value, "contract_id": CONTRACT_ID, "contract_version": CONTRACT_VERSION}


def _anchor_bridge_id(value: dict[str, object]) -> str:
    return "isin-issuer-anchor-bridge:" + _hash(value)[7:39]


def _anchor_bridge_identity(value: IsinIssuerAnchorBridge) -> dict[str, object]:
    return _anchor_bridge_identity_from_values({name: getattr(value, name) for name in value.__dataclass_fields__})


def _anchor_bridge_identity_from_values(value: dict[str, object]) -> dict[str, object]:
    return {key: value[key] for key in ("policy_id", "policy_version", "policy_fingerprint", "approval_id", "activation_id", "anchor_id", "anchor_fingerprint", "isin", "cin", "anchor_session_date", "issuer_known_at", "brsr_evidence_id", "brsr_evidence_fingerprint", "mii_snapshot_id", "mii_snapshot_fingerprint", "mii_row_ids", "mii_row_fingerprints")} | {"contract_id": CONTRACT_ID, "contract_version": CONTRACT_VERSION}


def _anchor_bridge_payload(value: IsinIssuerAnchorBridge) -> dict[str, object]:
    return _anchor_bridge_payload_from_values({name: getattr(value, name) for name in value.__dataclass_fields__ if name != "fingerprint"})


def _anchor_bridge_payload_from_values(value: dict[str, object]) -> dict[str, object]:
    return {"bridge_id": value["bridge_id"], **_anchor_bridge_identity_from_values(value), "anchor_symbol": value["anchor_symbol"], "state": value["state"], "contract_id": CONTRACT_ID, "contract_version": CONTRACT_VERSION}


def _forward_observation_id(value: dict[str, object]) -> str:
    return "isin-issuer-forward-observation:" + _hash(value)[7:39]


def _forward_observation_identity(value: IsinIssuerForwardObservation) -> dict[str, object]:
    return _forward_observation_identity_from_values({name: getattr(value, name) for name in value.__dataclass_fields__})


def _forward_observation_identity_from_values(value: dict[str, object]) -> dict[str, object]:
    return {key: value[key] for key in ("policy_id", "policy_version", "policy_fingerprint", "approval_id", "activation_id", "later_session_receipt_ids", "later_session_fingerprints", "later_session_date", "isin", "later_symbol", "cin", "anchor_bridge_ids", "anchor_bridge_fingerprints", "anchor_known_ats")} | {"contract_id": CONTRACT_ID, "contract_version": CONTRACT_VERSION}


def _forward_observation_payload(value: IsinIssuerForwardObservation) -> dict[str, object]:
    return _forward_observation_payload_from_values({name: getattr(value, name) for name in value.__dataclass_fields__ if name != "fingerprint"})


def _forward_observation_payload_from_values(value: dict[str, object]) -> dict[str, object]:
    return {"observation_id": value["observation_id"], **_forward_observation_identity_from_values(value), "later_symbol": value["later_symbol"], "state": value["state"], "contract_id": CONTRACT_ID, "contract_version": CONTRACT_VERSION}


def _anchor_result_payload(value: IsinIssuerAnchorActivationResult) -> dict[str, object]:
    return _anchor_result_payload_from_values({name: getattr(value, name) for name in value.__dataclass_fields__ if name != "fingerprint"})


def _anchor_result_payload_from_values(value: dict[str, object]) -> dict[str, object]:
    return {"activation_id": value["activation_id"], "bridge_fingerprints": tuple(item.fingerprint for item in value["bridges"]), "conflicted_anchor_ids": value["conflicted_anchor_ids"]}


def _forward_result_payload(value: IsinIssuerForwardActivationResult) -> dict[str, object]:
    return _forward_result_payload_from_values({name: getattr(value, name) for name in value.__dataclass_fields__ if name != "fingerprint"})


def _forward_result_payload_from_values(value: dict[str, object]) -> dict[str, object]:
    return {"activation_id": value["activation_id"], "observation_fingerprints": tuple(item.fingerprint for item in value["observations"]), "absent_anchor_isins": value["absent_anchor_isins"], "conflicted_isins": value["conflicted_isins"], "lifecycle_blocked_isins": value["lifecycle_blocked_isins"], "non_forward_anchor_ids": value["non_forward_anchor_ids"]}


def _resolution_payload(value: IsinIssuerBridgeResolution) -> dict[str, object]:
    return _resolution_payload_from_values({name: getattr(value, name) for name in value.__dataclass_fields__ if name != "fingerprint"})


def _resolution_payload_from_values(value: dict[str, object]) -> dict[str, object]:
    return {"isin": value["isin"], "as_of": value["as_of"], "status": value["status"], "bridge_fingerprints": tuple(item.fingerprint for item in value["bridges"]), "reasons": value["reasons"], "contract_id": CONTRACT_ID, "contract_version": CONTRACT_VERSION}


def _hash(value: object) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=_json_default).encode()).hexdigest()


def _json_default(value: object) -> str:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, tuple):
        return tuple(value)
    raise TypeError(type(value).__name__)


def _aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def _utc(value: datetime) -> datetime:
    if not _aware(value):
        raise IsinIssuerBridgeContinuityError("ISIN_ISSUER_CONTINUITY_AWARE_TIMESTAMP_REQUIRED")
    return value.astimezone(UTC)


def _identifier(value: object) -> bool:
    return isinstance(value, str) and _ID.fullmatch(value) is not None


def _fingerprint(value: object) -> bool:
    return isinstance(value, str) and _FP.fullmatch(value) is not None


def _symbol(value: object) -> bool:
    return isinstance(value, str) and bool(value) and value == value.strip() and " " not in value


__all__ = (
    "CONTRACT_ID", "CONTRACT_VERSION", "POLICY_ID", "POLICY_VERSION", "ExactNseLifecycleDiscontinuity",
    "IsinIssuerAnchorActivationResult", "IsinIssuerAnchorBridge", "IsinIssuerBridgeContinuityActivation",
    "IsinIssuerBridgeContinuityActivationState", "IsinIssuerBridgeContinuityError", "IsinIssuerBridgeContinuityPolicy",
    "IsinIssuerBridgeContinuityPolicyApproval", "IsinIssuerBridgeContinuityApprovalState", "IsinIssuerBridgeContinuitySemantic",
    "IsinIssuerBridgeContinuityStore", "IsinIssuerBridgeReason", "IsinIssuerBridgeResolution", "IsinIssuerBridgeResolutionStatus",
    "IsinIssuerBridgeState", "IsinIssuerBridgeWriteOutcome", "IsinIssuerForwardActivationResult", "IsinIssuerForwardObservation",
    "activate_forward_issuer_observations", "activate_isin_issuer_anchor_bridges", "activate_isin_issuer_bridge_continuity_policy",
    "approve_isin_issuer_bridge_continuity_policy", "create_isin_issuer_bridge_continuity_policy", "persist_isin_issuer_continuity",
    "resolve_isin_issuer_anchor_at",
)
