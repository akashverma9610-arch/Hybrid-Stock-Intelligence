"""Activated exact NSE taxonomy-category evidence; never a company-type result.

This boundary turns the human-approved, fixed NSE code-pair map into immutable
evidence receipts.  It consumes only a PIT-valid canonical taxonomy assignment
and an existing active ISIN-to-issuer forward observation.  The receipt is an
input to a future classifier, not a classification of an issuer.
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
from app.intelligence.nse_taxonomy_company_type_map_proposal import (
    NSE_TAXONOMY_SEMANTICS,
    NSE_TAXONOMY_SOURCE,
    NSE_TAXONOMY_VERSION,
    NseTaxonomyCompanyTypeMapEntry,
    NseTaxonomyMapAuditReason,
    NseTaxonomyResearchCategory,
    assess_proposed_nse_taxonomy_map,
    create_proposed_nse_taxonomy_company_type_map,
)
from app.storage.core_api_snapshot_repository import (
    CoreApiSnapshot,
    CoreApiSnapshotFamily,
    CoreApiSnapshotRepository,
)
from app.taxonomy.models import InstrumentTaxonomyClassification


POLICY_ID = "nse-taxonomy-company-type-code-map"
POLICY_VERSION = "v1"
CONTRACT_ID = "nse-taxonomy-company-type-code-map-activation"
CONTRACT_VERSION = "v1"
_ID = re.compile(r"[A-Za-z0-9._:-]+\Z")
_FP = re.compile(r"sha256:[0-9a-f]{64}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_ISIN = re.compile(r"[A-Z]{2}[A-Z0-9]{9}[0-9]\Z")
_CIN = re.compile(r"[LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}\Z")


class NseTaxonomyCategoryEvidenceError(ValueError):
    """Stable fail-closed error at the activated taxonomy evidence boundary."""


class NseTaxonomyCategoryEvidenceSemantic(StrEnum):
    EXACT_CODE_PAIR_ONLY = "EXACT_CODE_PAIR_ONLY"
    FIXED_NINETEEN_CODE_PAIRS = "FIXED_NINETEEN_CODE_PAIRS"
    SOURCE_VERSION_BOUND = "SOURCE_VERSION_BOUND"
    TAXONOMY_PIT_REQUIRED = "TAXONOMY_PIT_REQUIRED"
    EXACT_ACTIVE_ISSUER_OBSERVATION_REQUIRED = "EXACT_ACTIVE_ISSUER_OBSERVATION_REQUIRED"
    NO_BACKWARD_TAXONOMY_PROPAGATION = "NO_BACKWARD_TAXONOMY_PROPAGATION"
    REGULATOR_EVIDENCE_INDEPENDENT = "REGULATOR_EVIDENCE_INDEPENDENT"
    NO_FINAL_COMPANY_TYPE = "NO_FINAL_COMPANY_TYPE"
    UNMAPPED_CODES_FAIL_CLOSED = "UNMAPPED_CODES_FAIL_CLOSED"


class NseTaxonomyMapApprovalState(StrEnum):
    APPROVED = "APPROVED"


class NseTaxonomyMapActivationState(StrEnum):
    ACTIVE = "ACTIVE"


class NseTaxonomyCategoryEvidenceState(StrEnum):
    ACTIVE = "ACTIVE"


class NseTaxonomyCategoryEvidenceWriteOutcome(StrEnum):
    INSERTED = "INSERTED"
    ALREADY_PRESENT = "ALREADY_PRESENT"


_SEMANTICS = (
    NseTaxonomyCategoryEvidenceSemantic.EXACT_CODE_PAIR_ONLY,
    NseTaxonomyCategoryEvidenceSemantic.FIXED_NINETEEN_CODE_PAIRS,
    NseTaxonomyCategoryEvidenceSemantic.SOURCE_VERSION_BOUND,
    NseTaxonomyCategoryEvidenceSemantic.TAXONOMY_PIT_REQUIRED,
    NseTaxonomyCategoryEvidenceSemantic.EXACT_ACTIVE_ISSUER_OBSERVATION_REQUIRED,
    NseTaxonomyCategoryEvidenceSemantic.NO_BACKWARD_TAXONOMY_PROPAGATION,
    NseTaxonomyCategoryEvidenceSemantic.REGULATOR_EVIDENCE_INDEPENDENT,
    NseTaxonomyCategoryEvidenceSemantic.NO_FINAL_COMPANY_TYPE,
    NseTaxonomyCategoryEvidenceSemantic.UNMAPPED_CODES_FAIL_CLOSED,
)


@dataclass(frozen=True, slots=True)
class NseTaxonomyCategoryMapPolicy:
    policy_id: str
    policy_version: str
    approved_map_fingerprint: str
    proposal_policy_id: str
    proposal_policy_version: str
    taxonomy_source: str
    taxonomy_version: str
    semantics: tuple[NseTaxonomyCategoryEvidenceSemantic, ...]
    fingerprint: str
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        proposal = create_proposed_nse_taxonomy_company_type_map()
        valid = (
            (self.policy_id, self.policy_version) == (POLICY_ID, POLICY_VERSION)
            and self.approved_map_fingerprint == proposal.fingerprint
            and (self.proposal_policy_id, self.proposal_policy_version) == (proposal.policy_id, proposal.policy_version)
            and (self.taxonomy_source, self.taxonomy_version) == (NSE_TAXONOMY_SOURCE, NSE_TAXONOMY_VERSION)
            and self.semantics == _SEMANTICS
            and (self.contract_id, self.contract_version) == (CONTRACT_ID, CONTRACT_VERSION)
            and self.fingerprint == _hash(_policy_payload(self))
        )
        if not valid:
            raise NseTaxonomyCategoryEvidenceError("NSE_TAXONOMY_CATEGORY_MAP_POLICY_INVALID")

    def verify(self) -> None:
        self.__post_init__()


@dataclass(frozen=True, slots=True)
class NseTaxonomyCategoryMapApproval:
    approval_id: str
    policy_id: str
    policy_version: str
    policy_fingerprint: str
    approved_by: str
    approved_at: datetime
    state: NseTaxonomyMapApprovalState
    fingerprint: str
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        policy = create_nse_taxonomy_category_map_policy()
        valid = (
            _identifier(self.approval_id)
            and (self.policy_id, self.policy_version, self.policy_fingerprint) == _policy_identity()
            and self.approved_by.startswith("human:")
            and _aware(self.approved_at)
            and self.state is NseTaxonomyMapApprovalState.APPROVED
            and (self.contract_id, self.contract_version) == (CONTRACT_ID, CONTRACT_VERSION)
            and self.fingerprint == _hash(_approval_payload(self))
        )
        if not valid:
            raise NseTaxonomyCategoryEvidenceError("NSE_TAXONOMY_CATEGORY_MAP_APPROVAL_INVALID")

    def verify(self) -> None:
        self.__post_init__()


@dataclass(frozen=True, slots=True)
class NseTaxonomyCategoryMapActivation:
    selection_id: str
    approval_id: str
    approval_fingerprint: str
    policy_id: str
    policy_version: str
    policy_fingerprint: str
    taxonomy_source: str
    taxonomy_version: str
    activated_by: str
    activated_at: datetime
    state: NseTaxonomyMapActivationState
    fingerprint: str
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        valid = (
            _identifier(self.selection_id)
            and _identifier(self.approval_id)
            and _fingerprint(self.approval_fingerprint)
            and (self.policy_id, self.policy_version, self.policy_fingerprint) == _policy_identity()
            and (self.taxonomy_source, self.taxonomy_version) == (NSE_TAXONOMY_SOURCE, NSE_TAXONOMY_VERSION)
            and self.activated_by.startswith("human:")
            and _aware(self.activated_at)
            and self.state is NseTaxonomyMapActivationState.ACTIVE
            and (self.contract_id, self.contract_version) == (CONTRACT_ID, CONTRACT_VERSION)
            and self.fingerprint == _hash(_activation_payload(self))
        )
        if not valid:
            raise NseTaxonomyCategoryEvidenceError("NSE_TAXONOMY_CATEGORY_MAP_ACTIVATION_INVALID")

    def verify(self) -> None:
        self.__post_init__()


@dataclass(frozen=True, slots=True)
class NseTaxonomyCategoryEvidenceReceipt:
    """One immutable taxonomy-category evidence receipt, never final type."""

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
    taxonomy_assignment_id: str
    taxonomy_assignment_source_sha256: str
    taxonomy_source: str
    taxonomy_version: str
    macro_economic_sector_code: str
    sector_code: str
    taxonomy_effective_from: datetime
    taxonomy_as_of: datetime
    taxonomy_observation_semantics: str
    map_entry_id: str
    map_entry_fingerprint: str
    category: NseTaxonomyResearchCategory
    evaluated_as_of: datetime
    state: NseTaxonomyCategoryEvidenceState
    fingerprint: str
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION
    actionability: str = "WATCH_ONLY"
    execution_status: str = "NON_EXECUTABLE"

    def __post_init__(self) -> None:
        valid = _receipt_valid(self)
        if valid:
            valid = self.receipt_id == _receipt_id(_receipt_identity(self)) and self.fingerprint == _hash(_receipt_payload(self))
        if not valid:
            raise NseTaxonomyCategoryEvidenceError("NSE_TAXONOMY_CATEGORY_EVIDENCE_RECEIPT_INVALID")

    def verify(self) -> None:
        self.__post_init__()


@dataclass(frozen=True, slots=True)
class NseTaxonomyCategoryEvidenceActivationReport:
    as_of: datetime
    active_issuer_observations: int
    exact_taxonomy_assignments: int
    receipts: tuple[NseTaxonomyCategoryEvidenceReceipt, ...]
    non_financial_candidates: int
    unsupported_financial: int
    unknown_non_comparable: int
    unmapped: int
    missing_taxonomy: int
    conflicts: int
    fingerprint: str
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        counts = _receipt_counts(self.receipts)
        valid = (
            _aware(self.as_of)
            and min(self.active_issuer_observations, self.exact_taxonomy_assignments, self.unmapped, self.missing_taxonomy, self.conflicts) >= 0
            and self.receipts == _canonical_receipts(self.receipts)
            and (self.non_financial_candidates, self.unsupported_financial, self.unknown_non_comparable) == counts
            and self.exact_taxonomy_assignments == len(self.receipts) + self.unmapped
            and self.active_issuer_observations == self.exact_taxonomy_assignments + self.missing_taxonomy + self.conflicts
            and self.conflicts == 0
            and (self.contract_id, self.contract_version) == (CONTRACT_ID, CONTRACT_VERSION)
            and self.fingerprint == _hash(_report_payload(self))
        )
        if not valid:
            raise NseTaxonomyCategoryEvidenceError("NSE_TAXONOMY_CATEGORY_EVIDENCE_REPORT_INVALID")

    def verify(self) -> None:
        self.__post_init__()


class NseTaxonomyCategoryEvidenceStore:
    """Append-only receipts in the dedicated taxonomy-evidence snapshot family."""

    def __init__(self, repository: CoreApiSnapshotRepository) -> None:
        self._repository = repository

    def save_policy(self, value: NseTaxonomyCategoryMapPolicy) -> NseTaxonomyCategoryEvidenceWriteOutcome:
        return self._save("nse-taxonomy-category-map-policy:" + value.policy_id + ":" + value.policy_version, value, datetime(1970, 1, 1, tzinfo=UTC))

    def save_approval(self, value: NseTaxonomyCategoryMapApproval) -> NseTaxonomyCategoryEvidenceWriteOutcome:
        return self._save("nse-taxonomy-category-map-approval:" + value.approval_id, value, value.approved_at)

    def save_activation(self, value: NseTaxonomyCategoryMapActivation) -> NseTaxonomyCategoryEvidenceWriteOutcome:
        return self._save("nse-taxonomy-category-map-activation:" + value.selection_id, value, value.activated_at)

    def save_receipt(self, value: NseTaxonomyCategoryEvidenceReceipt) -> NseTaxonomyCategoryEvidenceWriteOutcome:
        value.verify()
        return self._save(value.receipt_id, value, value.evaluated_as_of)

    def receipts(self) -> tuple[NseTaxonomyCategoryEvidenceReceipt, ...]:
        return tuple(sorted((item.payload for item in self._all() if isinstance(item.payload, NseTaxonomyCategoryEvidenceReceipt)), key=lambda item: item.receipt_id))

    def _save(self, snapshot_id: str, value: object, created_at: datetime) -> NseTaxonomyCategoryEvidenceWriteOutcome:
        existing = self._repository.get_snapshot(snapshot_id)
        if existing is not None:
            if existing.family is CoreApiSnapshotFamily.TAXONOMY_CATEGORY_EVIDENCE and existing.payload == value:
                return NseTaxonomyCategoryEvidenceWriteOutcome.ALREADY_PRESENT
            raise NseTaxonomyCategoryEvidenceError("NSE_TAXONOMY_CATEGORY_EVIDENCE_IMMUTABILITY_CONFLICT")
        self._repository.save_snapshot(CoreApiSnapshot(snapshot_id, CoreApiSnapshotFamily.TAXONOMY_CATEGORY_EVIDENCE, "v1", type(value).__name__, getattr(value, "fingerprint"), _utc(created_at), value))
        return NseTaxonomyCategoryEvidenceWriteOutcome.INSERTED

    def _all(self) -> tuple[CoreApiSnapshot, ...]:
        result: list[CoreApiSnapshot] = []
        offset = 0
        while True:
            page = self._repository.list_snapshots(CoreApiSnapshotFamily.TAXONOMY_CATEGORY_EVIDENCE, limit=100, offset=offset)
            result.extend(page)
            if len(page) < 100:
                return tuple(result)
            offset += len(page)


def create_nse_taxonomy_category_map_policy() -> NseTaxonomyCategoryMapPolicy:
    proposal = create_proposed_nse_taxonomy_company_type_map()
    values = dict(
        policy_id=POLICY_ID, policy_version=POLICY_VERSION, approved_map_fingerprint=proposal.fingerprint,
        proposal_policy_id=proposal.policy_id, proposal_policy_version=proposal.policy_version,
        taxonomy_source=NSE_TAXONOMY_SOURCE, taxonomy_version=NSE_TAXONOMY_VERSION, semantics=_SEMANTICS,
    )
    return NseTaxonomyCategoryMapPolicy(**values, fingerprint=_hash(_policy_payload_from_values(values)))


def approve_nse_taxonomy_category_map_policy(*, approval_id: str, approved_by: str, approved_at: datetime) -> NseTaxonomyCategoryMapApproval:
    policy = create_nse_taxonomy_category_map_policy()
    values = dict(
        approval_id=approval_id, policy_id=policy.policy_id, policy_version=policy.policy_version,
        policy_fingerprint=policy.fingerprint, approved_by=approved_by, approved_at=_utc(approved_at),
        state=NseTaxonomyMapApprovalState.APPROVED,
    )
    return NseTaxonomyCategoryMapApproval(**values, fingerprint=_hash(_approval_payload_from_values(values)))


def activate_nse_taxonomy_category_map_policy(*, selection_id: str, approval: NseTaxonomyCategoryMapApproval, activated_by: str, activated_at: datetime) -> NseTaxonomyCategoryMapActivation:
    approval.verify()
    normalized = _utc(activated_at)
    if normalized < _utc(approval.approved_at):
        raise NseTaxonomyCategoryEvidenceError("NSE_TAXONOMY_CATEGORY_MAP_ACTIVATION_PRECEDES_APPROVAL")
    values = dict(
        selection_id=selection_id, approval_id=approval.approval_id, approval_fingerprint=approval.fingerprint,
        policy_id=approval.policy_id, policy_version=approval.policy_version, policy_fingerprint=approval.policy_fingerprint,
        taxonomy_source=NSE_TAXONOMY_SOURCE, taxonomy_version=NSE_TAXONOMY_VERSION,
        activated_by=activated_by, activated_at=normalized, state=NseTaxonomyMapActivationState.ACTIVE,
    )
    return NseTaxonomyCategoryMapActivation(**values, fingerprint=_hash(_activation_payload_from_values(values)))


def activate_nse_taxonomy_category_evidence(*, activation: NseTaxonomyCategoryMapActivation, classifications: Iterable[InstrumentTaxonomyClassification], issuer_observations: Iterable[IsinIssuerForwardObservation], as_of: datetime) -> NseTaxonomyCategoryEvidenceActivationReport:
    """Derive evidence from exact PIT taxonomy and active issuer observations.

    This performs no regulator lookup and exposes no final company-type field.
    ``activation`` is governance provenance, whereas ``as_of`` remains the
    historical evidence cutoff; later activation never changes taxonomy
    knownness or propagates a current assignment backward.
    """
    activation.verify()
    cutoff = _utc(as_of)
    taxonomy = _canonical_classifications(classifications)
    observations = _canonical_active_observations(issuer_observations, cutoff)
    selected = _taxonomy_at(taxonomy, cutoff)
    proposal = create_proposed_nse_taxonomy_company_type_map()
    entries = {item.entry_id: item for item in proposal.entries}
    receipts: list[NseTaxonomyCategoryEvidenceReceipt] = []
    exact = unmapped = missing = 0
    for observation in observations:
        canonical_instrument_id = "NSE:" + observation.isin
        classification = selected.get(canonical_instrument_id)
        if classification is None:
            missing += 1
            continue
        exact += 1
        assessment = assess_proposed_nse_taxonomy_map(classification, as_of=cutoff)
        if assessment.category is NseTaxonomyResearchCategory.UNMAPPED:
            unmapped += 1
            continue
        entry = entries.get(assessment.map_entry_id or "")
        if entry is None:
            raise NseTaxonomyCategoryEvidenceError("NSE_TAXONOMY_CATEGORY_MAP_ENTRY_LINEAGE_INVALID")
        receipts.append(_receipt_from(activation, observation, classification, entry, cutoff))
    canonical = _canonical_receipts(receipts)
    values = dict(
        as_of=cutoff, active_issuer_observations=len(observations), exact_taxonomy_assignments=exact,
        receipts=canonical, non_financial_candidates=_receipt_counts(canonical)[0],
        unsupported_financial=_receipt_counts(canonical)[1], unknown_non_comparable=_receipt_counts(canonical)[2],
        unmapped=unmapped, missing_taxonomy=missing, conflicts=0,
    )
    return NseTaxonomyCategoryEvidenceActivationReport(**values, fingerprint=_hash(_report_payload_from_values(values)))


def persist_nse_taxonomy_category_evidence(*, store: NseTaxonomyCategoryEvidenceStore, policy: NseTaxonomyCategoryMapPolicy, approval: NseTaxonomyCategoryMapApproval, activation: NseTaxonomyCategoryMapActivation, report: NseTaxonomyCategoryEvidenceActivationReport) -> tuple[int, int]:
    """Insert immutable governance and receipt records; exact replay is a no-op."""
    policy.verify(); approval.verify(); activation.verify(); report.verify()
    if (approval.policy_id, approval.policy_version, approval.policy_fingerprint) != (policy.policy_id, policy.policy_version, policy.fingerprint) or (activation.approval_id, activation.approval_fingerprint, activation.policy_fingerprint) != (approval.approval_id, approval.fingerprint, policy.fingerprint):
        raise NseTaxonomyCategoryEvidenceError("NSE_TAXONOMY_CATEGORY_EVIDENCE_GOVERNANCE_LINEAGE_INVALID")
    inserted = present = 0
    for value, save in ((policy, store.save_policy), (approval, store.save_approval), (activation, store.save_activation)):
        outcome = save(value)
        inserted += outcome is NseTaxonomyCategoryEvidenceWriteOutcome.INSERTED
        present += outcome is NseTaxonomyCategoryEvidenceWriteOutcome.ALREADY_PRESENT
    for receipt in report.receipts:
        outcome = store.save_receipt(receipt)
        inserted += outcome is NseTaxonomyCategoryEvidenceWriteOutcome.INSERTED
        present += outcome is NseTaxonomyCategoryEvidenceWriteOutcome.ALREADY_PRESENT
    return inserted, present


def nse_taxonomy_category_evidence_payload(value: NseTaxonomyCategoryEvidenceReceipt) -> dict[str, object]:
    value.verify()
    return _receipt_payload(value) | {"fingerprint": value.fingerprint}


def serialize_nse_taxonomy_category_evidence(value: NseTaxonomyCategoryEvidenceReceipt) -> str:
    return json.dumps(nse_taxonomy_category_evidence_payload(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _receipt_from(activation: NseTaxonomyCategoryMapActivation, observation: IsinIssuerForwardObservation, classification: InstrumentTaxonomyClassification, entry: NseTaxonomyCompanyTypeMapEntry, as_of: datetime) -> NseTaxonomyCategoryEvidenceReceipt:
    values = dict(
        policy_id=activation.policy_id, policy_version=activation.policy_version, policy_fingerprint=activation.policy_fingerprint,
        approval_id=activation.approval_id, activation_id=activation.selection_id, canonical_issuer_id=observation.cin,
        canonical_instrument_id=classification.instrument_id, issuer_observation_id=observation.observation_id,
        issuer_observation_fingerprint=observation.fingerprint, taxonomy_assignment_id=classification.classification_id,
        taxonomy_assignment_source_sha256=classification.source_sha256, taxonomy_source=classification.source,
        taxonomy_version=classification.classification_version, macro_economic_sector_code=classification.macro_economic_sector_code,
        sector_code=classification.sector_code, taxonomy_effective_from=_utc(classification.effective_from),
        taxonomy_as_of=_utc(classification.as_of), taxonomy_observation_semantics=classification.effective_observation_semantics,
        map_entry_id=entry.entry_id, map_entry_fingerprint=entry.fingerprint, category=entry.category,
        evaluated_as_of=_utc(as_of), state=NseTaxonomyCategoryEvidenceState.ACTIVE,
        actionability="WATCH_ONLY", execution_status="NON_EXECUTABLE",
    )
    receipt_id = _receipt_id(_receipt_identity_from_values(values))
    return NseTaxonomyCategoryEvidenceReceipt(receipt_id=receipt_id, **values, fingerprint=_hash(_receipt_payload_from_values(values | {"receipt_id": receipt_id})))


def _canonical_classifications(values: Iterable[InstrumentTaxonomyClassification]) -> tuple[InstrumentTaxonomyClassification, ...]:
    unique: dict[str, InstrumentTaxonomyClassification] = {}
    for value in values:
        if not isinstance(value, InstrumentTaxonomyClassification):
            raise NseTaxonomyCategoryEvidenceError("NSE_TAXONOMY_CATEGORY_EVIDENCE_TAXONOMY_INPUT_INVALID")
        prior = unique.get(value.classification_id)
        if prior is not None and prior != value:
            raise NseTaxonomyCategoryEvidenceError("NSE_TAXONOMY_CATEGORY_EVIDENCE_TAXONOMY_INPUT_CONFLICTED")
        unique[value.classification_id] = value
    return tuple(sorted(unique.values(), key=lambda value: value.classification_id))


def _canonical_active_observations(values: Iterable[IsinIssuerForwardObservation], as_of: datetime) -> tuple[IsinIssuerForwardObservation, ...]:
    unique: dict[str, IsinIssuerForwardObservation] = {}
    for value in values:
        if not isinstance(value, IsinIssuerForwardObservation):
            raise NseTaxonomyCategoryEvidenceError("NSE_TAXONOMY_CATEGORY_EVIDENCE_ISSUER_INPUT_INVALID")
        value.verify()
        if value.state is not IsinIssuerBridgeState.ACTIVE:
            raise NseTaxonomyCategoryEvidenceError("NSE_TAXONOMY_CATEGORY_EVIDENCE_ISSUER_STATE_INVALID")
        prior = unique.get(value.observation_id)
        if prior is not None and prior != value:
            raise NseTaxonomyCategoryEvidenceError("NSE_TAXONOMY_CATEGORY_EVIDENCE_ISSUER_INPUT_CONFLICTED")
        unique[value.observation_id] = value
    return tuple(sorted((value for value in unique.values() if value.later_session_date <= as_of.date() and all(_utc(item) <= as_of for item in value.anchor_known_ats)), key=lambda value: value.observation_id))


def _taxonomy_at(values: tuple[InstrumentTaxonomyClassification, ...], as_of: datetime) -> dict[str, InstrumentTaxonomyClassification]:
    resolved: dict[str, InstrumentTaxonomyClassification] = {}
    for value in values:
        if not value.eligible_as_of(as_of):
            continue
        prior = resolved.get(value.instrument_id)
        if prior is None or (value.effective_from, value.as_of, value.classification_id) > (prior.effective_from, prior.as_of, prior.classification_id):
            resolved[value.instrument_id] = value
    return resolved


def _canonical_receipts(values: Iterable[NseTaxonomyCategoryEvidenceReceipt]) -> tuple[NseTaxonomyCategoryEvidenceReceipt, ...]:
    unique: dict[str, NseTaxonomyCategoryEvidenceReceipt] = {}
    for value in values:
        if not isinstance(value, NseTaxonomyCategoryEvidenceReceipt):
            raise NseTaxonomyCategoryEvidenceError("NSE_TAXONOMY_CATEGORY_EVIDENCE_RECEIPT_INPUT_INVALID")
        value.verify()
        prior = unique.get(value.receipt_id)
        if prior is not None and prior != value:
            raise NseTaxonomyCategoryEvidenceError("NSE_TAXONOMY_CATEGORY_EVIDENCE_RECEIPT_INPUT_CONFLICTED")
        unique[value.receipt_id] = value
    return tuple(sorted(unique.values(), key=lambda value: value.receipt_id))


def _receipt_counts(values: Iterable[NseTaxonomyCategoryEvidenceReceipt]) -> tuple[int, int, int]:
    canonical = tuple(values)
    return (
        sum(item.category is NseTaxonomyResearchCategory.NON_FINANCIAL_CANDIDATE for item in canonical),
        sum(item.category is NseTaxonomyResearchCategory.UNSUPPORTED_FINANCIAL for item in canonical),
        sum(item.category is NseTaxonomyResearchCategory.UNKNOWN_NON_COMPARABLE for item in canonical),
    )


def _receipt_valid(value: NseTaxonomyCategoryEvidenceReceipt) -> bool:
    proposal = create_proposed_nse_taxonomy_company_type_map()
    entries = {item.entry_id: item for item in proposal.entries}
    entry = entries.get(value.map_entry_id)
    return (
        _identifier(value.receipt_id) and (value.policy_id, value.policy_version, value.policy_fingerprint) == _policy_identity()
        and _identifier(value.approval_id) and _identifier(value.activation_id) and _CIN.fullmatch(value.canonical_issuer_id) is not None
        and value.canonical_instrument_id == "NSE:" + _isin_from_instrument(value.canonical_instrument_id)
        and _identifier(value.issuer_observation_id) and _fingerprint(value.issuer_observation_fingerprint)
        and _identifier(value.taxonomy_assignment_id) and _SHA.fullmatch(value.taxonomy_assignment_source_sha256) is not None
        and (value.taxonomy_source, value.taxonomy_version) == (NSE_TAXONOMY_SOURCE, NSE_TAXONOMY_VERSION)
        and _identifier(value.macro_economic_sector_code) and _identifier(value.sector_code)
        and _aware(value.taxonomy_effective_from) and _aware(value.taxonomy_as_of) and value.taxonomy_effective_from <= value.evaluated_as_of and value.taxonomy_as_of <= value.evaluated_as_of
        and value.taxonomy_observation_semantics == NSE_TAXONOMY_SEMANTICS
        and entry is not None and entry.fingerprint == value.map_entry_fingerprint and (entry.macro_economic_sector_code, entry.sector_code, entry.category) == (value.macro_economic_sector_code, value.sector_code, value.category)
        and value.category in {NseTaxonomyResearchCategory.NON_FINANCIAL_CANDIDATE, NseTaxonomyResearchCategory.UNSUPPORTED_FINANCIAL, NseTaxonomyResearchCategory.UNKNOWN_NON_COMPARABLE}
        and _aware(value.evaluated_as_of) and value.state is NseTaxonomyCategoryEvidenceState.ACTIVE
        and (value.contract_id, value.contract_version) == (CONTRACT_ID, CONTRACT_VERSION)
        and value.actionability == "WATCH_ONLY" and value.execution_status == "NON_EXECUTABLE"
    )


def _isin_from_instrument(value: str) -> str:
    exchange, separator, isin = value.partition(":")
    return isin if exchange == "NSE" and separator == ":" and _ISIN.fullmatch(isin) else ""


def _policy_identity() -> tuple[str, str, str]:
    policy = create_nse_taxonomy_category_map_policy()
    return policy.policy_id, policy.policy_version, policy.fingerprint


def _policy_payload(value: NseTaxonomyCategoryMapPolicy) -> dict[str, object]:
    return _policy_payload_from_values(_values(value, exclude={"fingerprint"}))


def _policy_payload_from_values(values: dict[str, object]) -> dict[str, object]:
    return _payload(values)


def _approval_payload(value: NseTaxonomyCategoryMapApproval) -> dict[str, object]:
    return _approval_payload_from_values(_values(value, exclude={"fingerprint"}))


def _approval_payload_from_values(values: dict[str, object]) -> dict[str, object]:
    return _payload(values)


def _activation_payload(value: NseTaxonomyCategoryMapActivation) -> dict[str, object]:
    return _activation_payload_from_values(_values(value, exclude={"fingerprint"}))


def _activation_payload_from_values(values: dict[str, object]) -> dict[str, object]:
    return _payload(values)


def _receipt_identity(value: NseTaxonomyCategoryEvidenceReceipt) -> dict[str, object]:
    return _receipt_identity_from_values(_values(value, exclude={"receipt_id", "fingerprint", "state", "actionability", "execution_status"}))


def _receipt_identity_from_values(values: dict[str, object]) -> dict[str, object]:
    keys = (
        "policy_id", "policy_version", "policy_fingerprint", "approval_id", "activation_id", "canonical_issuer_id",
        "canonical_instrument_id", "issuer_observation_id", "issuer_observation_fingerprint", "taxonomy_assignment_id",
        "taxonomy_assignment_source_sha256", "taxonomy_source", "taxonomy_version", "macro_economic_sector_code", "sector_code",
        "taxonomy_effective_from", "taxonomy_as_of", "taxonomy_observation_semantics", "map_entry_id", "map_entry_fingerprint",
        "category", "evaluated_as_of", "contract_id", "contract_version",
    )
    return _payload({key: values.get(key, CONTRACT_ID if key == "contract_id" else CONTRACT_VERSION if key == "contract_version" else None) for key in keys})


def _receipt_id(value: dict[str, object]) -> str:
    return "nse-taxonomy-category-evidence:" + _hash(value)[7:39]


def _receipt_payload(value: NseTaxonomyCategoryEvidenceReceipt) -> dict[str, object]:
    return _receipt_payload_from_values(_values(value, exclude={"fingerprint"}))


def _receipt_payload_from_values(values: dict[str, object]) -> dict[str, object]:
    return _payload(values)


def _report_payload(value: NseTaxonomyCategoryEvidenceActivationReport) -> dict[str, object]:
    return _report_payload_from_values(_values(value, exclude={"fingerprint"}))


def _report_payload_from_values(values: dict[str, object]) -> dict[str, object]:
    receipts = tuple(values.get("receipts", ()))
    return _payload({key: value for key, value in values.items() if key != "receipts"} | {"receipt_fingerprints": tuple(item.fingerprint for item in receipts)})


def _values(value: object, *, exclude: set[str]) -> dict[str, object]:
    return {item.name: getattr(value, item.name) for item in fields(value) if item.name not in exclude}


def _payload(values: dict[str, object]) -> dict[str, object]:
    canonical = {
        **values,
        "contract_id": values.get("contract_id", CONTRACT_ID),
        "contract_version": values.get("contract_version", CONTRACT_VERSION),
    }
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


def _aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def _utc(value: datetime) -> datetime:
    if not _aware(value):
        raise NseTaxonomyCategoryEvidenceError("NSE_TAXONOMY_CATEGORY_EVIDENCE_AWARE_TIMESTAMP_REQUIRED")
    return value.astimezone(UTC)


__all__ = (
    "CONTRACT_ID", "CONTRACT_VERSION", "POLICY_ID", "POLICY_VERSION", "NseTaxonomyCategoryEvidenceActivationReport",
    "NseTaxonomyCategoryEvidenceError", "NseTaxonomyCategoryEvidenceReceipt", "NseTaxonomyCategoryEvidenceSemantic",
    "NseTaxonomyCategoryEvidenceState", "NseTaxonomyCategoryEvidenceStore", "NseTaxonomyCategoryEvidenceWriteOutcome",
    "NseTaxonomyCategoryMapActivation", "NseTaxonomyMapActivationState", "NseTaxonomyCategoryMapApproval",
    "NseTaxonomyMapApprovalState", "NseTaxonomyCategoryMapPolicy", "activate_nse_taxonomy_category_evidence",
    "activate_nse_taxonomy_category_map_policy", "approve_nse_taxonomy_category_map_policy",
    "create_nse_taxonomy_category_map_policy", "nse_taxonomy_category_evidence_payload",
    "persist_nse_taxonomy_category_evidence", "serialize_nse_taxonomy_category_evidence",
)
