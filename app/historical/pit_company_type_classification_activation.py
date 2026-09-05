"""Activated, immutable PIT company-type classification receipts.

This module consumes already-canonical issuer continuity, exact regulator
linkage, regulator evidence, and exact-code NSE taxonomy category evidence.
It never reads a clock, retrieves a provider, infers from names, or performs
investment qualification.  The taxonomy and regulator records remain inputs;
this is their separately auditable, final company-type projection.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
import json
import re
from typing import Iterable

from app.historical.isin_issuer_bridge_continuity import (
    IsinIssuerBridgeState,
    IsinIssuerForwardObservation,
)
from app.historical.nse_taxonomy_company_type_map_activation import (
    NseTaxonomyCategoryEvidenceReceipt,
    NseTaxonomyCategoryEvidenceState,
)
from app.historical.regulator_company_type_evidence import (
    RegulatorEntityEvidence,
    RegulatorEntityEvidenceKind,
    RegulatorEntityStatus,
    RegulatorEvidenceSource,
)
from app.historical.regulator_issuer_raw_exact_linkage import (
    RawExactLinkageState,
    RawExactRegulatorIssuerLink,
)
from app.intelligence.nse_taxonomy_company_type_map_proposal import NseTaxonomyResearchCategory
from app.storage.core_api_snapshot_repository import (
    CoreApiSnapshot,
    CoreApiSnapshotFamily,
    CoreApiSnapshotRepository,
)


POLICY_ID = "pit-company-type-classification-policy"
POLICY_VERSION = "v1"
CONTRACT_ID = "pit-company-type-classification-activation"
CONTRACT_VERSION = "v1"
_ID = re.compile(r"[A-Za-z0-9._:-]+\Z")
_FP = re.compile(r"sha256:[0-9a-f]{64}\Z")
_CIN = re.compile(r"[LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}\Z")
_ISIN = re.compile(r"[A-Z]{2}[A-Z0-9]{9}[0-9]\Z")


class PitCompanyTypeClassificationError(ValueError):
    """Stable fail-closed error at the final company-type boundary."""


class PitCompanyTypeClassificationSemantic(StrEnum):
    EXACT_ACTIVE_ISSUER_OBSERVATION_REQUIRED = "EXACT_ACTIVE_ISSUER_OBSERVATION_REQUIRED"
    TAXONOMY_POSITIVE_NON_FINANCIAL_ONLY = "TAXONOMY_POSITIVE_NON_FINANCIAL_ONLY"
    TAXONOMY_NEVER_PROVES_FINANCIAL_SUBTYPE = "TAXONOMY_NEVER_PROVES_FINANCIAL_SUBTYPE"
    RAW_EXACT_REGULATOR_LINK_REQUIRED = "RAW_EXACT_REGULATOR_LINK_REQUIRED"
    REGULATOR_ABSENCE_IS_NOT_NON_FINANCIAL_EVIDENCE = "REGULATOR_ABSENCE_IS_NOT_NON_FINANCIAL_EVIDENCE"
    RBI_BANK_EXACT_LINK_ONLY = "RBI_BANK_EXACT_LINK_ONLY"
    RBI_NBFC_EXACT_LINK_ONLY = "RBI_NBFC_EXACT_LINK_ONLY"
    IRDAI_INSURER_EXACT_LINK_ONLY = "IRDAI_INSURER_EXACT_LINK_ONLY"
    PIT_KNOWNNESS_REQUIRED = "PIT_KNOWNNESS_REQUIRED"
    NO_BACKWARD_PROPAGATION = "NO_BACKWARD_PROPAGATION"
    INCOMPATIBLE_EXACT_EVIDENCE_CONFLICTS = "INCOMPATIBLE_EXACT_EVIDENCE_CONFLICTS"
    UNSUPPORTED_FINANCIAL_FAILS_CLOSED = "UNSUPPORTED_FINANCIAL_FAILS_CLOSED"
    NO_COMPOUNDER_OR_INVESTMENT_OUTPUT = "NO_COMPOUNDER_OR_INVESTMENT_OUTPUT"
    WATCH_ONLY_NON_EXECUTABLE = "WATCH_ONLY_NON_EXECUTABLE"


class PitCompanyTypeApprovalState(StrEnum):
    APPROVED = "APPROVED"


class PitCompanyTypeActivationState(StrEnum):
    ACTIVE = "ACTIVE"


class PitCompanyType(StrEnum):
    NON_FINANCIAL = "NON_FINANCIAL"
    BANK = "BANK"
    NBFC = "NBFC"
    INSURER = "INSURER"


class PitInsurerSubtype(StrEnum):
    LIFE = "LIFE"
    GENERAL = "GENERAL"
    HEALTH = "HEALTH"


class PitCompanyTypeClassificationState(StrEnum):
    CLASSIFIED = "CLASSIFIED"
    DATA_INSUFFICIENT = "DATA_INSUFFICIENT"
    EVIDENCE_CONFLICTED = "EVIDENCE_CONFLICTED"
    UNSUPPORTED_FINANCIAL = "UNSUPPORTED_FINANCIAL"
    NON_COMPARABLE = "NON_COMPARABLE"


class PitCompanyTypeReason(StrEnum):
    EXACT_ISSUER_OBSERVATION_REQUIRED = "EXACT_ISSUER_OBSERVATION_REQUIRED"
    TAXONOMY_EVIDENCE_UNAVAILABLE = "TAXONOMY_EVIDENCE_UNAVAILABLE"
    REGULATOR_LINKAGE_UNAVAILABLE = "REGULATOR_LINKAGE_UNAVAILABLE"
    REGULATOR_EVIDENCE_UNAVAILABLE = "REGULATOR_EVIDENCE_UNAVAILABLE"
    FUTURE_EVIDENCE_EXCLUDED = "FUTURE_EVIDENCE_EXCLUDED"
    NON_FINANCIAL_TAXONOMY_EVIDENCE = "NON_FINANCIAL_TAXONOMY_EVIDENCE"
    RBI_BANK_EXACT_EVIDENCE = "RBI_BANK_EXACT_EVIDENCE"
    RBI_NBFC_EXACT_EVIDENCE = "RBI_NBFC_EXACT_EVIDENCE"
    IRDAI_INSURER_EXACT_EVIDENCE = "IRDAI_INSURER_EXACT_EVIDENCE"
    UNSUPPORTED_FINANCIAL_TAXONOMY_EVIDENCE = "UNSUPPORTED_FINANCIAL_TAXONOMY_EVIDENCE"
    NON_COMPARABLE_TAXONOMY_EVIDENCE = "NON_COMPARABLE_TAXONOMY_EVIDENCE"
    INCOMPATIBLE_EXACT_COMPANY_TYPE_EVIDENCE = "INCOMPATIBLE_EXACT_COMPANY_TYPE_EVIDENCE"
    REGULATOR_LINKAGE_LINEAGE_INVALID = "REGULATOR_LINKAGE_LINEAGE_INVALID"


class PitCompanyTypeClassificationWriteOutcome(StrEnum):
    INSERTED = "INSERTED"
    ALREADY_PRESENT = "ALREADY_PRESENT"


_SEMANTICS = (
    PitCompanyTypeClassificationSemantic.EXACT_ACTIVE_ISSUER_OBSERVATION_REQUIRED,
    PitCompanyTypeClassificationSemantic.TAXONOMY_POSITIVE_NON_FINANCIAL_ONLY,
    PitCompanyTypeClassificationSemantic.TAXONOMY_NEVER_PROVES_FINANCIAL_SUBTYPE,
    PitCompanyTypeClassificationSemantic.RAW_EXACT_REGULATOR_LINK_REQUIRED,
    PitCompanyTypeClassificationSemantic.REGULATOR_ABSENCE_IS_NOT_NON_FINANCIAL_EVIDENCE,
    PitCompanyTypeClassificationSemantic.RBI_BANK_EXACT_LINK_ONLY,
    PitCompanyTypeClassificationSemantic.RBI_NBFC_EXACT_LINK_ONLY,
    PitCompanyTypeClassificationSemantic.IRDAI_INSURER_EXACT_LINK_ONLY,
    PitCompanyTypeClassificationSemantic.PIT_KNOWNNESS_REQUIRED,
    PitCompanyTypeClassificationSemantic.NO_BACKWARD_PROPAGATION,
    PitCompanyTypeClassificationSemantic.INCOMPATIBLE_EXACT_EVIDENCE_CONFLICTS,
    PitCompanyTypeClassificationSemantic.UNSUPPORTED_FINANCIAL_FAILS_CLOSED,
    PitCompanyTypeClassificationSemantic.NO_COMPOUNDER_OR_INVESTMENT_OUTPUT,
    PitCompanyTypeClassificationSemantic.WATCH_ONLY_NON_EXECUTABLE,
)


@dataclass(frozen=True, slots=True)
class PitCompanyTypeClassificationPolicy:
    policy_id: str
    policy_version: str
    semantics: tuple[PitCompanyTypeClassificationSemantic, ...]
    fingerprint: str
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not (
            (self.policy_id, self.policy_version) == (POLICY_ID, POLICY_VERSION)
            and self.semantics == _SEMANTICS
            and (self.contract_id, self.contract_version) == (CONTRACT_ID, CONTRACT_VERSION)
            and self.fingerprint == _hash(_policy_payload(self))
        ):
            raise PitCompanyTypeClassificationError("PIT_COMPANY_TYPE_POLICY_INVALID")

    def verify(self) -> None:
        self.__post_init__()


@dataclass(frozen=True, slots=True)
class PitCompanyTypeClassificationApproval:
    approval_id: str
    policy_id: str
    policy_version: str
    policy_fingerprint: str
    approved_by: str
    approved_at: datetime
    state: PitCompanyTypeApprovalState
    fingerprint: str
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not (
            _identifier(self.approval_id)
            and (self.policy_id, self.policy_version, self.policy_fingerprint) == _policy_identity()
            and self.approved_by.startswith("human:")
            and _aware(self.approved_at)
            and self.state is PitCompanyTypeApprovalState.APPROVED
            and (self.contract_id, self.contract_version) == (CONTRACT_ID, CONTRACT_VERSION)
            and self.fingerprint == _hash(_approval_payload(self))
        ):
            raise PitCompanyTypeClassificationError("PIT_COMPANY_TYPE_APPROVAL_INVALID")

    def verify(self) -> None:
        self.__post_init__()


@dataclass(frozen=True, slots=True)
class PitCompanyTypeClassificationActivation:
    selection_id: str
    approval_id: str
    approval_fingerprint: str
    policy_id: str
    policy_version: str
    policy_fingerprint: str
    activated_by: str
    activated_at: datetime
    state: PitCompanyTypeActivationState
    fingerprint: str
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not (
            _identifier(self.selection_id)
            and _identifier(self.approval_id)
            and _fingerprint(self.approval_fingerprint)
            and (self.policy_id, self.policy_version, self.policy_fingerprint) == _policy_identity()
            and self.activated_by.startswith("human:")
            and _aware(self.activated_at)
            and self.state is PitCompanyTypeActivationState.ACTIVE
            and (self.contract_id, self.contract_version) == (CONTRACT_ID, CONTRACT_VERSION)
            and self.fingerprint == _hash(_activation_payload(self))
        ):
            raise PitCompanyTypeClassificationError("PIT_COMPANY_TYPE_ACTIVATION_INVALID")

    def verify(self) -> None:
        self.__post_init__()


@dataclass(frozen=True, slots=True)
class PitCompanyTypeClassificationReceipt:
    """One final immutable issuer company-type result at an explicit cutoff."""

    receipt_id: str
    policy_id: str
    policy_version: str
    policy_fingerprint: str
    approval_id: str
    activation_id: str
    canonical_issuer_id: str
    canonical_instrument_id: str
    issuer_observation_id: str
    issuer_observation_fingerprint: str
    evaluated_as_of: datetime
    company_type: PitCompanyType | None
    insurer_subtype: PitInsurerSubtype | None
    state: PitCompanyTypeClassificationState
    taxonomy_receipt_ids: tuple[str, ...]
    taxonomy_receipt_fingerprints: tuple[str, ...]
    regulator_link_ids: tuple[str, ...]
    regulator_link_fingerprints: tuple[str, ...]
    regulator_evidence_ids: tuple[str, ...]
    regulator_evidence_fingerprints: tuple[str, ...]
    reasons: tuple[PitCompanyTypeReason, ...]
    fingerprint: str
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION
    actionability: str = "WATCH_ONLY"
    execution_status: str = "NON_EXECUTABLE"

    def __post_init__(self) -> None:
        if not _receipt_valid(self):
            raise PitCompanyTypeClassificationError("PIT_COMPANY_TYPE_RECEIPT_INVALID")
        if self.receipt_id != _receipt_id(_receipt_identity(self)):
            raise PitCompanyTypeClassificationError("PIT_COMPANY_TYPE_RECEIPT_IDENTITY_MISMATCH")
        if self.fingerprint != _hash(_receipt_payload(self)):
            raise PitCompanyTypeClassificationError("PIT_COMPANY_TYPE_RECEIPT_FINGERPRINT_MISMATCH")

    def verify(self) -> None:
        self.__post_init__()


@dataclass(frozen=True, slots=True)
class PitCompanyTypeClassificationReport:
    """Immutable deterministic coverage result for one explicitly supplied as-of."""

    report_id: str
    policy_id: str
    policy_version: str
    policy_fingerprint: str
    activation_id: str
    evaluated_as_of: datetime
    active_issuer_observations: int
    distinct_issuers: int
    receipts: tuple[PitCompanyTypeClassificationReceipt, ...]
    non_financial: int
    banks: int
    nbfcs: int
    insurers: int
    unsupported_financial: int
    data_insufficient: int
    evidence_conflicted: int
    non_comparable: int
    taxonomy_unavailable: int
    regulator_linkage_unavailable: int
    fingerprint: str
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        counts = _counts(self.receipts)
        if not (
            _identifier(self.report_id)
            and (self.policy_id, self.policy_version, self.policy_fingerprint) == _policy_identity()
            and _identifier(self.activation_id)
            and _aware(self.evaluated_as_of)
            and self.active_issuer_observations == len(self.receipts)
            and self.distinct_issuers == len({item.canonical_issuer_id for item in self.receipts})
            and self.receipts == _canonical_receipts(self.receipts)
            and (
                self.non_financial, self.banks, self.nbfcs, self.insurers,
                self.unsupported_financial, self.data_insufficient,
                self.evidence_conflicted, self.non_comparable,
                self.taxonomy_unavailable, self.regulator_linkage_unavailable,
            ) == counts
            and (self.contract_id, self.contract_version) == (CONTRACT_ID, CONTRACT_VERSION)
            and self.report_id == _report_id(_report_identity(self))
            and self.fingerprint == _hash(_report_payload(self))
        ):
            raise PitCompanyTypeClassificationError("PIT_COMPANY_TYPE_REPORT_INVALID")

    def verify(self) -> None:
        self.__post_init__()


class PitCompanyTypeClassificationStore:
    """Append-only company-type governance, report, and receipt snapshots."""

    def __init__(self, repository: CoreApiSnapshotRepository) -> None:
        self._repository = repository

    def save_policy(self, value: PitCompanyTypeClassificationPolicy) -> PitCompanyTypeClassificationWriteOutcome:
        return self._save("pit-company-type-policy:" + value.policy_id + ":" + value.policy_version, value, datetime(1970, 1, 1, tzinfo=UTC))

    def save_approval(self, value: PitCompanyTypeClassificationApproval) -> PitCompanyTypeClassificationWriteOutcome:
        return self._save("pit-company-type-approval:" + value.approval_id, value, value.approved_at)

    def save_activation(self, value: PitCompanyTypeClassificationActivation) -> PitCompanyTypeClassificationWriteOutcome:
        return self._save("pit-company-type-activation:" + value.selection_id, value, value.activated_at)

    def save_receipt(self, value: PitCompanyTypeClassificationReceipt) -> PitCompanyTypeClassificationWriteOutcome:
        value.verify()
        return self._save(value.receipt_id, value, value.evaluated_as_of)

    def save_report(self, value: PitCompanyTypeClassificationReport) -> PitCompanyTypeClassificationWriteOutcome:
        value.verify()
        return self._save(value.report_id, value, value.evaluated_as_of)

    def receipts(self) -> tuple[PitCompanyTypeClassificationReceipt, ...]:
        return tuple(sorted((item.payload for item in self._all() if isinstance(item.payload, PitCompanyTypeClassificationReceipt)), key=lambda item: item.receipt_id))

    def reports(self) -> tuple[PitCompanyTypeClassificationReport, ...]:
        return tuple(sorted((item.payload for item in self._all() if isinstance(item.payload, PitCompanyTypeClassificationReport)), key=lambda item: item.report_id))

    def _save(self, snapshot_id: str, value: object, created_at: datetime) -> PitCompanyTypeClassificationWriteOutcome:
        existing = self._repository.get_snapshot(snapshot_id)
        if existing is not None:
            if existing.family is CoreApiSnapshotFamily.PIT_COMPANY_TYPE_CLASSIFICATION and existing.payload == value:
                return PitCompanyTypeClassificationWriteOutcome.ALREADY_PRESENT
            raise PitCompanyTypeClassificationError("PIT_COMPANY_TYPE_IMMUTABILITY_CONFLICT")
        self._repository.save_snapshot(CoreApiSnapshot(
            snapshot_id, CoreApiSnapshotFamily.PIT_COMPANY_TYPE_CLASSIFICATION, "v1", type(value).__name__,
            getattr(value, "fingerprint"), _utc(created_at), value,
        ))
        return PitCompanyTypeClassificationWriteOutcome.INSERTED

    def _all(self) -> tuple[CoreApiSnapshot, ...]:
        result: list[CoreApiSnapshot] = []
        offset = 0
        while True:
            page = self._repository.list_snapshots(CoreApiSnapshotFamily.PIT_COMPANY_TYPE_CLASSIFICATION, limit=100, offset=offset)
            result.extend(page)
            if len(page) < 100:
                return tuple(result)
            offset += len(page)


def create_pit_company_type_classification_policy() -> PitCompanyTypeClassificationPolicy:
    values = dict(policy_id=POLICY_ID, policy_version=POLICY_VERSION, semantics=_SEMANTICS)
    return PitCompanyTypeClassificationPolicy(**values, fingerprint=_hash(_payload(values)))


def approve_pit_company_type_classification_policy(*, approval_id: str, approved_by: str, approved_at: datetime) -> PitCompanyTypeClassificationApproval:
    policy = create_pit_company_type_classification_policy()
    values = dict(
        approval_id=approval_id, policy_id=policy.policy_id, policy_version=policy.policy_version,
        policy_fingerprint=policy.fingerprint, approved_by=approved_by, approved_at=_utc(approved_at),
        state=PitCompanyTypeApprovalState.APPROVED,
    )
    return PitCompanyTypeClassificationApproval(**values, fingerprint=_hash(_payload(values)))


def activate_pit_company_type_classification_policy(*, selection_id: str, approval: PitCompanyTypeClassificationApproval, activated_by: str, activated_at: datetime) -> PitCompanyTypeClassificationActivation:
    approval.verify()
    when = _utc(activated_at)
    if when < _utc(approval.approved_at):
        raise PitCompanyTypeClassificationError("PIT_COMPANY_TYPE_ACTIVATION_PRECEDES_APPROVAL")
    values = dict(
        selection_id=selection_id, approval_id=approval.approval_id, approval_fingerprint=approval.fingerprint,
        policy_id=approval.policy_id, policy_version=approval.policy_version, policy_fingerprint=approval.policy_fingerprint,
        activated_by=activated_by, activated_at=when, state=PitCompanyTypeActivationState.ACTIVE,
    )
    return PitCompanyTypeClassificationActivation(**values, fingerprint=_hash(_payload(values)))


def activate_pit_company_type_classifications(
    *,
    activation: PitCompanyTypeClassificationActivation,
    issuer_observations: Iterable[IsinIssuerForwardObservation],
    taxonomy_receipts: Iterable[NseTaxonomyCategoryEvidenceReceipt],
    regulator_links: Iterable[RawExactRegulatorIssuerLink],
    regulator_evidence: Iterable[RegulatorEntityEvidence],
    as_of: datetime,
) -> PitCompanyTypeClassificationReport:
    """Classify only exact, PIT-valid supplied evidence at ``as_of``.

    The supplied source collections are verified and canonicalized before use.
    Evidence observed after the cutoff is excluded rather than repaired or
    projected backward; source absence never creates a positive type.
    """
    activation.verify()
    cutoff = _utc(as_of)
    observations = _canonical_observations(issuer_observations, cutoff)
    taxonomy = _canonical_taxonomy_receipts(taxonomy_receipts)
    links = _canonical_regulator_links(regulator_links)
    evidence = _canonical_regulator_evidence(regulator_evidence)
    evidence_by_id = {item.evidence_id: item for item in evidence}
    taxonomy_by_observation: dict[str, list[NseTaxonomyCategoryEvidenceReceipt]] = {}
    for item in taxonomy:
        if _utc(item.evaluated_as_of) <= cutoff:
            taxonomy_by_observation.setdefault(item.issuer_observation_id, []).append(item)
    links_by_cin: dict[str, list[RawExactRegulatorIssuerLink]] = {}
    for item in links:
        if _utc(item.link_known_at) <= cutoff:
            links_by_cin.setdefault(item.cin, []).append(item)

    results = tuple(
        _receipt_for(
            activation, observation, cutoff,
            tuple(taxonomy_by_observation.get(observation.observation_id, ())),
            tuple(links_by_cin.get(observation.cin, ())), evidence_by_id,
        )
        for observation in observations
    )
    canonical = _canonical_receipts(results)
    counts = _counts(canonical)
    values = dict(
        policy_id=activation.policy_id, policy_version=activation.policy_version,
        policy_fingerprint=activation.policy_fingerprint, activation_id=activation.selection_id,
        evaluated_as_of=cutoff, active_issuer_observations=len(observations),
        distinct_issuers=len({item.cin for item in observations}), receipts=canonical,
        non_financial=counts[0], banks=counts[1], nbfcs=counts[2], insurers=counts[3],
        unsupported_financial=counts[4], data_insufficient=counts[5], evidence_conflicted=counts[6],
        non_comparable=counts[7], taxonomy_unavailable=counts[8], regulator_linkage_unavailable=counts[9],
    )
    report_id = _report_id(_report_identity_from_values(values))
    return PitCompanyTypeClassificationReport(
        report_id=report_id, **values,
        fingerprint=_hash(_report_payload_from_values(values | {"report_id": report_id})),
    )


def persist_pit_company_type_classifications(
    *, store: PitCompanyTypeClassificationStore, policy: PitCompanyTypeClassificationPolicy,
    approval: PitCompanyTypeClassificationApproval, activation: PitCompanyTypeClassificationActivation,
    report: PitCompanyTypeClassificationReport,
) -> tuple[int, int]:
    """Insert governance, final receipts, and coverage report; exact replay is a no-op."""
    policy.verify(); approval.verify(); activation.verify(); report.verify()
    if (
        (approval.policy_id, approval.policy_version, approval.policy_fingerprint) != (policy.policy_id, policy.policy_version, policy.fingerprint)
        or (activation.approval_id, activation.approval_fingerprint, activation.policy_fingerprint) != (approval.approval_id, approval.fingerprint, policy.fingerprint)
        or (report.policy_id, report.policy_version, report.policy_fingerprint, report.activation_id) != (policy.policy_id, policy.policy_version, policy.fingerprint, activation.selection_id)
    ):
        raise PitCompanyTypeClassificationError("PIT_COMPANY_TYPE_GOVERNANCE_LINEAGE_INVALID")
    inserted = present = 0
    for value, save in ((policy, store.save_policy), (approval, store.save_approval), (activation, store.save_activation)):
        outcome = save(value)
        inserted += outcome is PitCompanyTypeClassificationWriteOutcome.INSERTED
        present += outcome is PitCompanyTypeClassificationWriteOutcome.ALREADY_PRESENT
    for receipt in report.receipts:
        outcome = store.save_receipt(receipt)
        inserted += outcome is PitCompanyTypeClassificationWriteOutcome.INSERTED
        present += outcome is PitCompanyTypeClassificationWriteOutcome.ALREADY_PRESENT
    outcome = store.save_report(report)
    inserted += outcome is PitCompanyTypeClassificationWriteOutcome.INSERTED
    present += outcome is PitCompanyTypeClassificationWriteOutcome.ALREADY_PRESENT
    return inserted, present


def classify_pit_company_types_from_repository(
    *, repository: CoreApiSnapshotRepository, activation: PitCompanyTypeClassificationActivation, as_of: datetime,
) -> PitCompanyTypeClassificationReport:
    """Read canonical immutable inputs and produce one deterministic report.

    This is deliberately a read-only composition helper.  Callers choose an
    explicit cutoff and separately opt into append-only persistence.
    """
    bridge_values = _all_family(repository, CoreApiSnapshotFamily.HISTORICAL_ISSUER_SECURITY_BRIDGE)
    return activate_pit_company_type_classifications(
        activation=activation,
        issuer_observations=(item.payload for item in bridge_values if isinstance(item.payload, IsinIssuerForwardObservation)),
        taxonomy_receipts=(
            item.payload for item in _all_family(repository, CoreApiSnapshotFamily.TAXONOMY_CATEGORY_EVIDENCE)
            if isinstance(item.payload, NseTaxonomyCategoryEvidenceReceipt)
        ),
        regulator_links=(item.payload for item in bridge_values if isinstance(item.payload, RawExactRegulatorIssuerLink)),
        regulator_evidence=(
            item.payload for item in _all_family(repository, CoreApiSnapshotFamily.HISTORICAL_REGULATOR_ENTITY_EVIDENCE)
            if isinstance(item.payload, RegulatorEntityEvidence)
        ),
        as_of=as_of,
    )


def pit_company_type_classification_payload(value: PitCompanyTypeClassificationReceipt) -> dict[str, object]:
    value.verify()
    return _receipt_payload(value) | {"fingerprint": value.fingerprint}


def serialize_pit_company_type_classification(value: PitCompanyTypeClassificationReceipt) -> str:
    return json.dumps(pit_company_type_classification_payload(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _receipt_for(
    activation: PitCompanyTypeClassificationActivation,
    observation: IsinIssuerForwardObservation,
    cutoff: datetime,
    taxonomy: tuple[NseTaxonomyCategoryEvidenceReceipt, ...],
    links: tuple[RawExactRegulatorIssuerLink, ...],
    evidence_by_id: dict[str, RegulatorEntityEvidence],
) -> PitCompanyTypeClassificationReceipt:
    taxonomy = _canonical_taxonomy_receipts(taxonomy)
    raw_links = _canonical_regulator_links(links)
    if any(
        (item.canonical_issuer_id, item.canonical_instrument_id, item.issuer_observation_fingerprint)
        != (observation.cin, "NSE:" + observation.isin, observation.fingerprint)
        for item in taxonomy
    ):
        raise PitCompanyTypeClassificationError("PIT_COMPANY_TYPE_TAXONOMY_ISSUER_LINEAGE_INVALID")
    regulatory, valid_links, valid_evidence, lineage_invalid = _regulatory_types(raw_links, evidence_by_id, cutoff)
    taxonomy_types = _taxonomy_types(taxonomy)
    taxonomy_conflicted = len({item.category for item in taxonomy}) > 1
    supported = set(regulatory)
    all_types = supported | taxonomy_types
    reasons: set[PitCompanyTypeReason] = set()
    if not taxonomy:
        reasons.add(PitCompanyTypeReason.TAXONOMY_EVIDENCE_UNAVAILABLE)
    if not raw_links:
        reasons.add(PitCompanyTypeReason.REGULATOR_LINKAGE_UNAVAILABLE)
    if raw_links and not valid_links:
        reasons.add(PitCompanyTypeReason.REGULATOR_EVIDENCE_UNAVAILABLE)
    if lineage_invalid:
        reasons.add(PitCompanyTypeReason.REGULATOR_LINKAGE_LINEAGE_INVALID)

    company_type: PitCompanyType | None
    subtype: PitInsurerSubtype | None = None
    if lineage_invalid or taxonomy_conflicted or len(all_types) > 1 or (
        _has_taxonomy_category(taxonomy, NseTaxonomyResearchCategory.UNKNOWN_NON_COMPARABLE) and regulatory
    ):
        state = PitCompanyTypeClassificationState.EVIDENCE_CONFLICTED
        company_type = None
        reasons.add(PitCompanyTypeReason.INCOMPATIBLE_EXACT_COMPANY_TYPE_EVIDENCE)
    elif regulatory:
        company_type = next(iter(regulatory))
        state = PitCompanyTypeClassificationState.CLASSIFIED
        if company_type is PitCompanyType.BANK:
            reasons.add(PitCompanyTypeReason.RBI_BANK_EXACT_EVIDENCE)
        elif company_type is PitCompanyType.NBFC:
            reasons.add(PitCompanyTypeReason.RBI_NBFC_EXACT_EVIDENCE)
        else:
            reasons.add(PitCompanyTypeReason.IRDAI_INSURER_EXACT_EVIDENCE)
            subtype = _insurer_subtype(valid_evidence)
            if subtype is None:
                state = PitCompanyTypeClassificationState.DATA_INSUFFICIENT
                company_type = None
                reasons.add(PitCompanyTypeReason.REGULATOR_EVIDENCE_UNAVAILABLE)
    elif PitCompanyType.NON_FINANCIAL in taxonomy_types:
        company_type = PitCompanyType.NON_FINANCIAL
        state = PitCompanyTypeClassificationState.CLASSIFIED
        reasons.add(PitCompanyTypeReason.NON_FINANCIAL_TAXONOMY_EVIDENCE)
    elif _has_taxonomy_category(taxonomy, NseTaxonomyResearchCategory.UNSUPPORTED_FINANCIAL):
        company_type = None
        state = PitCompanyTypeClassificationState.UNSUPPORTED_FINANCIAL
        reasons.add(PitCompanyTypeReason.UNSUPPORTED_FINANCIAL_TAXONOMY_EVIDENCE)
    elif _has_taxonomy_category(taxonomy, NseTaxonomyResearchCategory.UNKNOWN_NON_COMPARABLE):
        company_type = None
        state = PitCompanyTypeClassificationState.NON_COMPARABLE
        reasons.add(PitCompanyTypeReason.NON_COMPARABLE_TAXONOMY_EVIDENCE)
    else:
        company_type = None
        state = PitCompanyTypeClassificationState.DATA_INSUFFICIENT

    values = dict(
        policy_id=activation.policy_id, policy_version=activation.policy_version, policy_fingerprint=activation.policy_fingerprint,
        approval_id=activation.approval_id, activation_id=activation.selection_id,
        canonical_issuer_id=observation.cin, canonical_instrument_id="NSE:" + observation.isin,
        issuer_observation_id=observation.observation_id, issuer_observation_fingerprint=observation.fingerprint,
        evaluated_as_of=cutoff, company_type=company_type, insurer_subtype=subtype, state=state,
        taxonomy_receipt_ids=tuple(item.receipt_id for item in taxonomy),
        taxonomy_receipt_fingerprints=tuple(item.fingerprint for item in taxonomy),
        regulator_link_ids=tuple(item.link_id for item in valid_links),
        regulator_link_fingerprints=tuple(item.fingerprint for item in valid_links),
        regulator_evidence_ids=tuple(item.evidence_id for item in valid_evidence),
        regulator_evidence_fingerprints=tuple(item.fingerprint for item in valid_evidence),
        reasons=tuple(sorted(reasons, key=lambda item: item.value)),
    )
    receipt_id = _receipt_id(_receipt_identity_from_values(values))
    return PitCompanyTypeClassificationReceipt(
        receipt_id=receipt_id, **values,
        fingerprint=_hash(_receipt_payload_from_values(values | {"receipt_id": receipt_id})),
    )


def _regulatory_types(
    links: tuple[RawExactRegulatorIssuerLink, ...], evidence_by_id: dict[str, RegulatorEntityEvidence], cutoff: datetime,
) -> tuple[set[PitCompanyType], tuple[RawExactRegulatorIssuerLink, ...], tuple[RegulatorEntityEvidence, ...], bool]:
    types: set[PitCompanyType] = set()
    accepted_links: list[RawExactRegulatorIssuerLink] = []
    accepted_evidence: list[RegulatorEntityEvidence] = []
    invalid = False
    for link in links:
        evidence = evidence_by_id.get(link.regulator_evidence_id)
        if (
            evidence is None
            or evidence.fingerprint != link.regulator_evidence_fingerprint
            or evidence.source is not link.regulator_family
            or evidence.regulator_subtype != link.regulator_subtype
        ):
            invalid = True
            continue
        if _utc(link.link_known_at) > cutoff or _utc(evidence.observed_at) > cutoff:
            continue
        category = _regulator_type(evidence, link)
        if category is None:
            continue
        types.add(category)
        accepted_links.append(link)
        accepted_evidence.append(evidence)
    return (
        types,
        tuple(sorted(accepted_links, key=lambda item: item.link_id)),
        tuple(sorted(accepted_evidence, key=lambda item: item.evidence_id)),
        invalid,
    )


def _regulator_type(evidence: RegulatorEntityEvidence, link: RawExactRegulatorIssuerLink) -> PitCompanyType | None:
    if link.state is not RawExactLinkageState.ACTIVE or evidence.entity_status is not RegulatorEntityStatus.LISTED:
        return None
    if (evidence.source, evidence.entity_kind) == (
        RegulatorEvidenceSource.RBI_SCHEDULED_COMMERCIAL_BANKS,
        RegulatorEntityEvidenceKind.SCHEDULED_COMMERCIAL_BANK,
    ):
        return PitCompanyType.BANK
    if (evidence.source, evidence.entity_kind) == (
        RegulatorEvidenceSource.RBI_REGISTERED_NBFC_ARC,
        RegulatorEntityEvidenceKind.RBI_REGISTERED_NBFC,
    ):
        return PitCompanyType.NBFC
    if (evidence.source, evidence.entity_kind) in {
        (RegulatorEvidenceSource.IRDAI_LIFE_INSURERS, RegulatorEntityEvidenceKind.IRDAI_LIFE_INSURER),
        (RegulatorEvidenceSource.IRDAI_GENERAL_INSURERS, RegulatorEntityEvidenceKind.IRDAI_GENERAL_INSURER),
        (RegulatorEvidenceSource.IRDAI_HEALTH_INSURERS, RegulatorEntityEvidenceKind.IRDAI_HEALTH_INSURER),
    }:
        return PitCompanyType.INSURER
    return None


def _insurer_subtype(values: tuple[RegulatorEntityEvidence, ...]) -> PitInsurerSubtype | None:
    subtypes = {
        PitInsurerSubtype.LIFE if item.entity_kind is RegulatorEntityEvidenceKind.IRDAI_LIFE_INSURER else
        PitInsurerSubtype.GENERAL if item.entity_kind is RegulatorEntityEvidenceKind.IRDAI_GENERAL_INSURER else
        PitInsurerSubtype.HEALTH
        for item in values if item.entity_kind in {
            RegulatorEntityEvidenceKind.IRDAI_LIFE_INSURER,
            RegulatorEntityEvidenceKind.IRDAI_GENERAL_INSURER,
            RegulatorEntityEvidenceKind.IRDAI_HEALTH_INSURER,
        }
    }
    return next(iter(subtypes)) if len(subtypes) == 1 else None


def _taxonomy_types(values: tuple[NseTaxonomyCategoryEvidenceReceipt, ...]) -> set[PitCompanyType]:
    return {PitCompanyType.NON_FINANCIAL for item in values if item.category is NseTaxonomyResearchCategory.NON_FINANCIAL_CANDIDATE}


def _has_taxonomy_category(values: tuple[NseTaxonomyCategoryEvidenceReceipt, ...], category: NseTaxonomyResearchCategory) -> bool:
    return any(item.category is category for item in values)


def _canonical_observations(values: Iterable[IsinIssuerForwardObservation], cutoff: datetime) -> tuple[IsinIssuerForwardObservation, ...]:
    unique: dict[str, IsinIssuerForwardObservation] = {}
    for value in values:
        if not isinstance(value, IsinIssuerForwardObservation):
            raise PitCompanyTypeClassificationError("PIT_COMPANY_TYPE_ISSUER_INPUT_INVALID")
        value.verify()
        if value.state is not IsinIssuerBridgeState.ACTIVE:
            raise PitCompanyTypeClassificationError("PIT_COMPANY_TYPE_ISSUER_STATE_INVALID")
        prior = unique.get(value.observation_id)
        if prior is not None and prior != value:
            raise PitCompanyTypeClassificationError("PIT_COMPANY_TYPE_ISSUER_INPUT_CONFLICTED")
        if value.later_session_date <= cutoff.date() and all(_utc(item) <= cutoff for item in value.anchor_known_ats):
            unique[value.observation_id] = value
    return tuple(sorted(unique.values(), key=lambda item: item.observation_id))


def _canonical_taxonomy_receipts(values: Iterable[NseTaxonomyCategoryEvidenceReceipt]) -> tuple[NseTaxonomyCategoryEvidenceReceipt, ...]:
    unique: dict[str, NseTaxonomyCategoryEvidenceReceipt] = {}
    for value in values:
        if not isinstance(value, NseTaxonomyCategoryEvidenceReceipt):
            raise PitCompanyTypeClassificationError("PIT_COMPANY_TYPE_TAXONOMY_INPUT_INVALID")
        value.verify()
        if value.state is not NseTaxonomyCategoryEvidenceState.ACTIVE:
            raise PitCompanyTypeClassificationError("PIT_COMPANY_TYPE_TAXONOMY_STATE_INVALID")
        prior = unique.get(value.receipt_id)
        if prior is not None and prior != value:
            raise PitCompanyTypeClassificationError("PIT_COMPANY_TYPE_TAXONOMY_INPUT_CONFLICTED")
        unique[value.receipt_id] = value
    return tuple(sorted(unique.values(), key=lambda item: item.receipt_id))


def _canonical_regulator_links(values: Iterable[RawExactRegulatorIssuerLink]) -> tuple[RawExactRegulatorIssuerLink, ...]:
    unique: dict[str, RawExactRegulatorIssuerLink] = {}
    for value in values:
        if not isinstance(value, RawExactRegulatorIssuerLink):
            raise PitCompanyTypeClassificationError("PIT_COMPANY_TYPE_REGULATOR_LINK_INPUT_INVALID")
        value.verify()
        prior = unique.get(value.link_id)
        if prior is not None and prior != value:
            raise PitCompanyTypeClassificationError("PIT_COMPANY_TYPE_REGULATOR_LINK_INPUT_CONFLICTED")
        unique[value.link_id] = value
    return tuple(sorted(unique.values(), key=lambda item: item.link_id))


def _canonical_regulator_evidence(values: Iterable[RegulatorEntityEvidence]) -> tuple[RegulatorEntityEvidence, ...]:
    unique: dict[str, RegulatorEntityEvidence] = {}
    for value in values:
        if not isinstance(value, RegulatorEntityEvidence):
            raise PitCompanyTypeClassificationError("PIT_COMPANY_TYPE_REGULATOR_EVIDENCE_INPUT_INVALID")
        value.verify()
        prior = unique.get(value.evidence_id)
        if prior is not None and prior != value:
            raise PitCompanyTypeClassificationError("PIT_COMPANY_TYPE_REGULATOR_EVIDENCE_INPUT_CONFLICTED")
        unique[value.evidence_id] = value
    return tuple(sorted(unique.values(), key=lambda item: item.evidence_id))


def _canonical_receipts(values: Iterable[PitCompanyTypeClassificationReceipt]) -> tuple[PitCompanyTypeClassificationReceipt, ...]:
    unique: dict[str, PitCompanyTypeClassificationReceipt] = {}
    for value in values:
        value.verify()
        prior = unique.get(value.receipt_id)
        if prior is not None and prior != value:
            raise PitCompanyTypeClassificationError("PIT_COMPANY_TYPE_RECEIPT_CONFLICTED")
        unique[value.receipt_id] = value
    return tuple(sorted(unique.values(), key=lambda item: item.receipt_id))


def _counts(values: tuple[PitCompanyTypeClassificationReceipt, ...]) -> tuple[int, int, int, int, int, int, int, int, int, int]:
    return (
        sum(item.company_type is PitCompanyType.NON_FINANCIAL for item in values),
        sum(item.company_type is PitCompanyType.BANK for item in values),
        sum(item.company_type is PitCompanyType.NBFC for item in values),
        sum(item.company_type is PitCompanyType.INSURER for item in values),
        sum(item.state is PitCompanyTypeClassificationState.UNSUPPORTED_FINANCIAL for item in values),
        sum(item.state is PitCompanyTypeClassificationState.DATA_INSUFFICIENT for item in values),
        sum(item.state is PitCompanyTypeClassificationState.EVIDENCE_CONFLICTED for item in values),
        sum(item.state is PitCompanyTypeClassificationState.NON_COMPARABLE for item in values),
        sum(PitCompanyTypeReason.TAXONOMY_EVIDENCE_UNAVAILABLE in item.reasons for item in values),
        sum(PitCompanyTypeReason.REGULATOR_LINKAGE_UNAVAILABLE in item.reasons for item in values),
    )


def _receipt_valid(value: PitCompanyTypeClassificationReceipt) -> bool:
    type_rules = {
        PitCompanyTypeClassificationState.CLASSIFIED: value.company_type is not None,
        PitCompanyTypeClassificationState.DATA_INSUFFICIENT: value.company_type is None,
        PitCompanyTypeClassificationState.EVIDENCE_CONFLICTED: value.company_type is None,
        PitCompanyTypeClassificationState.UNSUPPORTED_FINANCIAL: value.company_type is None,
        PitCompanyTypeClassificationState.NON_COMPARABLE: value.company_type is None,
    }
    id_fp_pairs = (
        (value.taxonomy_receipt_ids, value.taxonomy_receipt_fingerprints),
        (value.regulator_link_ids, value.regulator_link_fingerprints),
        (value.regulator_evidence_ids, value.regulator_evidence_fingerprints),
    )
    return (
        _identifier(value.receipt_id)
        and (value.policy_id, value.policy_version, value.policy_fingerprint) == _policy_identity()
        and _identifier(value.approval_id) and _identifier(value.activation_id)
        and _CIN.fullmatch(value.canonical_issuer_id) is not None
        and value.canonical_instrument_id == "NSE:" + _instrument_isin(value.canonical_instrument_id)
        and _identifier(value.issuer_observation_id) and _fingerprint(value.issuer_observation_fingerprint)
        and _aware(value.evaluated_as_of)
        and isinstance(value.state, PitCompanyTypeClassificationState)
        and type_rules[value.state]
        and (value.company_type is PitCompanyType.INSURER) == (value.insurer_subtype is not None)
        and (value.insurer_subtype is None or isinstance(value.insurer_subtype, PitInsurerSubtype))
        and all(
            len(ids) == len(fingerprints)
            and ids == tuple(sorted(set(ids)) or ())
            and fingerprints == tuple(fingerprints)
            and all(_identifier(item) for item in ids)
            and all(_fingerprint(item) for item in fingerprints)
            for ids, fingerprints in id_fp_pairs
        )
        and value.reasons == tuple(sorted(set(value.reasons), key=lambda item: item.value))
        and bool(value.reasons) and all(isinstance(item, PitCompanyTypeReason) for item in value.reasons)
        and (value.contract_id, value.contract_version) == (CONTRACT_ID, CONTRACT_VERSION)
        and value.actionability == "WATCH_ONLY" and value.execution_status == "NON_EXECUTABLE"
    )


def _policy_identity() -> tuple[str, str, str]:
    policy = create_pit_company_type_classification_policy()
    return policy.policy_id, policy.policy_version, policy.fingerprint


def _receipt_identity(value: PitCompanyTypeClassificationReceipt) -> dict[str, object]:
    return _receipt_identity_from_values(_values(value, exclude={"receipt_id", "fingerprint", "company_type", "insurer_subtype", "state", "reasons", "actionability", "execution_status"}))


def _receipt_identity_from_values(values: dict[str, object]) -> dict[str, object]:
    keys = (
        "policy_id", "policy_version", "policy_fingerprint", "approval_id", "activation_id", "canonical_issuer_id",
        "canonical_instrument_id", "issuer_observation_id", "issuer_observation_fingerprint", "evaluated_as_of",
        "taxonomy_receipt_ids", "taxonomy_receipt_fingerprints", "regulator_link_ids", "regulator_link_fingerprints",
        "regulator_evidence_ids", "regulator_evidence_fingerprints", "contract_id", "contract_version",
    )
    return _payload({key: values.get(key, CONTRACT_ID if key == "contract_id" else CONTRACT_VERSION if key == "contract_version" else None) for key in keys})


def _receipt_id(identity: dict[str, object]) -> str:
    return "pit-company-type-classification:" + _hash(identity)[7:39]


def _report_identity(value: PitCompanyTypeClassificationReport) -> dict[str, object]:
    return _report_identity_from_values(_values(value, exclude={"report_id", "fingerprint", "receipts", "active_issuer_observations", "distinct_issuers", "non_financial", "banks", "nbfcs", "insurers", "unsupported_financial", "data_insufficient", "evidence_conflicted", "non_comparable", "taxonomy_unavailable", "regulator_linkage_unavailable"}))


def _report_identity_from_values(values: dict[str, object]) -> dict[str, object]:
    keys = ("policy_id", "policy_version", "policy_fingerprint", "activation_id", "evaluated_as_of", "contract_id", "contract_version")
    return _payload({key: values.get(key, CONTRACT_ID if key == "contract_id" else CONTRACT_VERSION if key == "contract_version" else None) for key in keys})


def _report_id(identity: dict[str, object]) -> str:
    return "pit-company-type-classification-report:" + _hash(identity)[7:39]


def _policy_payload(value: PitCompanyTypeClassificationPolicy) -> dict[str, object]:
    return _payload(_values(value, exclude={"fingerprint"}))


def _approval_payload(value: PitCompanyTypeClassificationApproval) -> dict[str, object]:
    return _payload(_values(value, exclude={"fingerprint"}))


def _activation_payload(value: PitCompanyTypeClassificationActivation) -> dict[str, object]:
    return _payload(_values(value, exclude={"fingerprint"}))


def _receipt_payload(value: PitCompanyTypeClassificationReceipt) -> dict[str, object]:
    return _receipt_payload_from_values(_values(value, exclude={"fingerprint"}))


def _receipt_payload_from_values(values: dict[str, object]) -> dict[str, object]:
    return _payload({
        **values,
        "actionability": values.get("actionability", "WATCH_ONLY"),
        "execution_status": values.get("execution_status", "NON_EXECUTABLE"),
    })


def _report_payload(value: PitCompanyTypeClassificationReport) -> dict[str, object]:
    return _report_payload_from_values(_values(value, exclude={"fingerprint"}))


def _report_payload_from_values(values: dict[str, object]) -> dict[str, object]:
    receipts = tuple(values.get("receipts", ()))
    return _payload({key: item for key, item in values.items() if key != "receipts"} | {"receipt_fingerprints": tuple(item.fingerprint for item in receipts)})


def _values(value: object, *, exclude: set[str]) -> dict[str, object]:
    return {item.name: getattr(value, item.name) for item in fields(value) if item.name not in exclude}


def _payload(values: dict[str, object]) -> dict[str, object]:
    canonical = {**values, "contract_id": values.get("contract_id", CONTRACT_ID), "contract_version": values.get("contract_version", CONTRACT_VERSION)}
    return {key: _scalar(value) for key, value in canonical.items()}


def _scalar(value: object) -> object:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime):
        return _utc(value).isoformat()
    if isinstance(value, tuple):
        return tuple(_scalar(item) for item in value)
    return value


def _hash(value: object) -> str:
    return "sha256:" + sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def _identifier(value: object) -> bool:
    return isinstance(value, str) and _ID.fullmatch(value) is not None


def _fingerprint(value: object) -> bool:
    return isinstance(value, str) and _FP.fullmatch(value) is not None


def _instrument_isin(value: str) -> str:
    exchange, separator, isin = value.partition(":")
    return isin if exchange == "NSE" and separator == ":" and _ISIN.fullmatch(isin) else ""


def _aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def _utc(value: datetime) -> datetime:
    if not _aware(value):
        raise PitCompanyTypeClassificationError("PIT_COMPANY_TYPE_AWARE_TIMESTAMP_REQUIRED")
    return value.astimezone(UTC)


def _all_family(repository: CoreApiSnapshotRepository, family: CoreApiSnapshotFamily) -> tuple[CoreApiSnapshot, ...]:
    values: list[CoreApiSnapshot] = []
    offset = 0
    while True:
        page = repository.list_snapshots(family, limit=100, offset=offset)
        values.extend(page)
        if len(page) < 100:
            return tuple(values)
        offset += len(page)


__all__ = (
    "CONTRACT_ID", "CONTRACT_VERSION", "POLICY_ID", "POLICY_VERSION", "PitCompanyType", "PitCompanyTypeActivationState",
    "PitCompanyTypeApprovalState", "PitCompanyTypeClassificationActivation", "PitCompanyTypeClassificationApproval",
    "PitCompanyTypeClassificationError", "PitCompanyTypeClassificationPolicy", "PitCompanyTypeClassificationReceipt",
    "PitCompanyTypeClassificationReport", "PitCompanyTypeClassificationSemantic", "PitCompanyTypeClassificationState",
    "PitCompanyTypeClassificationStore", "PitCompanyTypeClassificationWriteOutcome", "PitCompanyTypeReason", "PitInsurerSubtype",
    "activate_pit_company_type_classification_policy", "activate_pit_company_type_classifications",
    "classify_pit_company_types_from_repository",
    "approve_pit_company_type_classification_policy", "create_pit_company_type_classification_policy",
    "persist_pit_company_type_classifications", "pit_company_type_classification_payload", "serialize_pit_company_type_classification",
)
