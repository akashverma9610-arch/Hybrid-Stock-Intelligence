"""Immutable, attribution-safe Discovery Recall audit contracts.

This module does not query discovery, run a Brain, read a portfolio, calculate
an outcome, or persist an audit.  It accepts only immutable references produced
by those separately governed boundaries.  Future outcome evidence may be used
for audit attribution, never for historical discovery reconstruction.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from app.historical.guard import manifest_fingerprint
from app.intelligence.multi_funnel_discovery import DiscoveryFunnelId, DiscoveryHorizon
from app.intelligence.multi_funnel_discovery_adapters import DiscoveryAdapterCoverageState
from app.intelligence.multi_funnel_orchestration import DiscoveryExecutionState


DISCOVERY_RECALL_AUDIT_CONTRACT = "discovery-recall-audit/v1"
_ID = re.compile(r"[A-Za-z0-9._:-]+\Z")
_FP = re.compile(r"(?:sha256:)?[0-9a-f]{64}\Z")


class DiscoveryRecallAuditError(ValueError):
    """Stable fail-closed contract error; no raw provider/action detail is kept."""


class DiscoveryState(StrEnum):
    DISCOVERED = "DISCOVERED"
    NOT_DISCOVERED = "NOT_DISCOVERED"
    DISCOVERY_NOT_EVALUABLE = "DISCOVERY_NOT_EVALUABLE"
    DISCOVERY_COVERAGE_INCOMPLETE = "DISCOVERY_COVERAGE_INCOMPLETE"
    IDENTITY_BLOCKED = "IDENTITY_BLOCKED"


class UniverseMembershipState(StrEnum):
    """Whether the audit can prove membership in the frozen eligible universe."""

    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE = "INELIGIBLE"
    UNRESOLVED = "UNRESOLVED"


class BrainDecisionState(StrEnum):
    """Audit-normalized references; no Brain result is calculated in this module."""

    NOT_EVALUATED_BY_BRAIN = "NOT_EVALUATED_BY_BRAIN"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    GATE_BLOCKED = "GATE_BLOCKED"
    UNRESOLVED = "UNRESOLVED"


class ActionState(StrEnum):
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NO_ACTION = "NO_ACTION"
    ACTION_TAKEN = "ACTION_TAKEN"
    ACTION_BLOCKED = "ACTION_BLOCKED"
    ACTION_NOT_YET_AVAILABLE = "ACTION_NOT_YET_AVAILABLE"


class OutcomeMaturity(StrEnum):
    IMMATURE = "IMMATURE"
    PARTIALLY_MATURE = "PARTIALLY_MATURE"
    MATURE = "MATURE"
    DATA_MISSING = "DATA_MISSING"
    NON_COMPARABLE = "NON_COMPARABLE"


class DiscoveryCapabilityState(StrEnum):
    CAPABILITY_AVAILABLE = "CAPABILITY_AVAILABLE"
    DISCOVERY_CAPABILITY_GAP = "DISCOVERY_CAPABILITY_GAP"
    CAPABILITY_UNRESOLVED = "CAPABILITY_UNRESOLVED"


class PerSecurityEvaluationState(StrEnum):
    TRIGGER_EMITTED = "TRIGGER_EMITTED"
    EVALUATED_NO_TRIGGER = "EVALUATED_NO_TRIGGER"
    PER_SECURITY_EVALUATION_UNKNOWN = "PER_SECURITY_EVALUATION_UNKNOWN"
    PER_SECURITY_DATA_BLOCKED = "PER_SECURITY_DATA_BLOCKED"
    IDENTITY_BLOCKED = "IDENTITY_BLOCKED"
    FUNNEL_NOT_EVALUATED = "FUNNEL_NOT_EVALUATED"


class DiscoveryProcessClassification(StrEnum):
    DISCOVERY_SUCCESS = "DISCOVERY_SUCCESS"
    DISCOVERED_BUT_REJECTED = "DISCOVERED_BUT_REJECTED"
    NOT_DISCOVERED_PROCESS = "NOT_DISCOVERED_PROCESS"
    UNAUDITABLE = "UNAUDITABLE"


class AttributionClassification(StrEnum):
    NOT_YET_ATTRIBUTABLE = "NOT_YET_ATTRIBUTABLE"
    DISCOVERY_FAILURE = "DISCOVERY_FAILURE"
    CORRECTLY_REJECTED = "CORRECTLY_REJECTED"
    DECISION_FAILURE = "DECISION_FAILURE"
    ACTION_FAILURE = "ACTION_FAILURE"
    UNAUDITABLE = "UNAUDITABLE"


class ReferenceOutcomeDefinitionAvailability(StrEnum):
    NOT_ACTIVE = "NOT_ACTIVE"
    AVAILABLE = "AVAILABLE"


class ReferenceOpportunityState(StrEnum):
    """A future outcome receipt's assertion, not an outcome calculation rule."""

    REFERENCE_OPPORTUNITY_CONFIRMED = "REFERENCE_OPPORTUNITY_CONFIRMED"
    REFERENCE_OPPORTUNITY_NOT_CONFIRMED = "REFERENCE_OPPORTUNITY_NOT_CONFIRMED"
    REJECTION_SUPPORTED = "REJECTION_SUPPORTED"
    ACTION_FAILURE_SUPPORTED = "ACTION_FAILURE_SUPPORTED"
    OUTCOME_UNAVAILABLE = "OUTCOME_UNAVAILABLE"
    OUTCOME_NON_COMPARABLE = "OUTCOME_NON_COMPARABLE"


class RecallReason(StrEnum):
    REFERENCE_OUTCOME_NOT_DEFINED = "REFERENCE_OUTCOME_NOT_DEFINED"
    OUTCOME_IMMATURE = "OUTCOME_IMMATURE"
    OUTCOME_DATA_MISSING = "OUTCOME_DATA_MISSING"
    OUTCOME_NON_COMPARABLE = "OUTCOME_NON_COMPARABLE"
    FUNNEL_NOT_OPERATIONAL = "FUNNEL_NOT_OPERATIONAL"
    FUNNEL_NOT_EVALUATED = "FUNNEL_NOT_EVALUATED"
    PER_SECURITY_EVALUATION_UNKNOWN = "PER_SECURITY_EVALUATION_UNKNOWN"
    IDENTITY_UNRESOLVED = "IDENTITY_UNRESOLVED"
    UNIVERSE_MEMBERSHIP_UNRESOLVED = "UNIVERSE_MEMBERSHIP_UNRESOLVED"
    UNIVERSE_NOT_ELIGIBLE = "UNIVERSE_NOT_ELIGIBLE"
    DATA_BLOCKED = "DATA_BLOCKED"
    POLICY_BLOCKED = "POLICY_BLOCKED"
    BRAIN_NOT_EVALUATED = "BRAIN_NOT_EVALUATED"
    ACTION_LAYER_NOT_AVAILABLE = "ACTION_LAYER_NOT_AVAILABLE"
    DISCOVERY_CUTOFF_NOT_TIMELY = "DISCOVERY_CUTOFF_NOT_TIMELY"
    REFERENCE_OUTCOME_AFTER_CUTOFF_REQUIRED = "REFERENCE_OUTCOME_AFTER_CUTOFF_REQUIRED"
    DISCOVERY_CAPABILITY_GAP = "DISCOVERY_CAPABILITY_GAP"


@dataclass(frozen=True, slots=True)
class RecallArtifactReference:
    reference_id: str
    fingerprint: str
    available_at: datetime

    def __post_init__(self) -> None:
        _id(self.reference_id, "DISCOVERY_RECALL_REFERENCE_ID_INVALID")
        _fp(self.fingerprint, "DISCOVERY_RECALL_REFERENCE_FINGERPRINT_INVALID")
        object.__setattr__(self, "available_at", _utc(self.available_at, "DISCOVERY_RECALL_REFERENCE_TIMESTAMP_INVALID"))


@dataclass(frozen=True, slots=True)
class DiscoveryBatchReference:
    batch_id: str
    batch_fingerprint: str
    discovery_as_of: datetime
    universe_snapshot_id: str
    universe_snapshot_fingerprint: str
    registry_id: str
    registry_version: str
    registry_fingerprint: str

    def __post_init__(self) -> None:
        for value in (self.batch_id, self.universe_snapshot_id, self.registry_id):
            _id(value, "DISCOVERY_RECALL_BATCH_IDENTITY_INVALID")
        for value in (self.batch_fingerprint, self.universe_snapshot_fingerprint, self.registry_fingerprint):
            _fp(value, "DISCOVERY_RECALL_BATCH_FINGERPRINT_INVALID")
        _text(self.registry_version, "DISCOVERY_RECALL_REGISTRY_VERSION_INVALID")
        object.__setattr__(self, "discovery_as_of", _utc(self.discovery_as_of, "DISCOVERY_RECALL_DISCOVERY_AS_OF_INVALID"))


@dataclass(frozen=True, slots=True)
class ReferenceOutcomeDefinitionReference:
    definition_id: str
    definition_version: str
    definition_fingerprint: str
    horizon: DiscoveryHorizon

    def __post_init__(self) -> None:
        _id(self.definition_id, "DISCOVERY_RECALL_REFERENCE_DEFINITION_ID_INVALID")
        _text(self.definition_version, "DISCOVERY_RECALL_REFERENCE_DEFINITION_VERSION_INVALID")
        _fp(self.definition_fingerprint, "DISCOVERY_RECALL_REFERENCE_DEFINITION_FINGERPRINT_INVALID")
        if not isinstance(self.horizon, DiscoveryHorizon):
            raise DiscoveryRecallAuditError("DISCOVERY_RECALL_REFERENCE_DEFINITION_HORIZON_INVALID")


@dataclass(frozen=True, slots=True)
class ReferenceOpportunityOutcome:
    """Opaque, future-produced result for a pre-registered outcome definition.

    It has no price, return, alpha, threshold, score, benchmark or formula. A
    future definition/matcher must produce this immutable receipt separately.
    """

    outcome: RecallArtifactReference
    definition: ReferenceOutcomeDefinitionReference
    canonical_instrument_id: str
    discovery_cutoff: datetime
    outcome_observed_at: datetime
    outcome_maturity: OutcomeMaturity
    reference_state: ReferenceOpportunityState

    def __post_init__(self) -> None:
        if not isinstance(self.outcome, RecallArtifactReference) or not isinstance(self.definition, ReferenceOutcomeDefinitionReference):
            raise DiscoveryRecallAuditError("DISCOVERY_RECALL_REFERENCE_OUTCOME_REFERENCE_INVALID")
        _id(self.canonical_instrument_id, "DISCOVERY_RECALL_REFERENCE_OUTCOME_INSTRUMENT_INVALID")
        object.__setattr__(self, "discovery_cutoff", _utc(self.discovery_cutoff, "DISCOVERY_RECALL_REFERENCE_CUTOFF_INVALID"))
        object.__setattr__(self, "outcome_observed_at", _utc(self.outcome_observed_at, "DISCOVERY_RECALL_OUTCOME_TIMESTAMP_INVALID"))
        if self.outcome_observed_at <= self.discovery_cutoff:
            raise DiscoveryRecallAuditError("DISCOVERY_RECALL_REFERENCE_OUTCOME_NOT_FUTURE")
        if not isinstance(self.outcome_maturity, OutcomeMaturity) or not isinstance(self.reference_state, ReferenceOpportunityState):
            raise DiscoveryRecallAuditError("DISCOVERY_RECALL_REFERENCE_OUTCOME_STATE_INVALID")
        # A future matcher may record its preliminary state before the approved
        # horizon has matured.  Attribution below deliberately consumes only a
        # MATURE receipt, so this contract preserves that fact without turning
        # it into a premature recall claim.
        if self.reference_state is ReferenceOpportunityState.OUTCOME_UNAVAILABLE and self.outcome_maturity is not OutcomeMaturity.DATA_MISSING:
            raise DiscoveryRecallAuditError("DISCOVERY_RECALL_REFERENCE_OUTCOME_UNAVAILABLE_CONTRADICTION")
        if self.reference_state is ReferenceOpportunityState.OUTCOME_NON_COMPARABLE and self.outcome_maturity is not OutcomeMaturity.NON_COMPARABLE:
            raise DiscoveryRecallAuditError("DISCOVERY_RECALL_REFERENCE_OUTCOME_NONCOMPARABLE_CONTRADICTION")


@dataclass(frozen=True, slots=True)
class DiscoveryFunnelAuditEvidence:
    funnel_id: DiscoveryFunnelId
    horizon: DiscoveryHorizon
    execution_state: DiscoveryExecutionState
    coverage_state: DiscoveryAdapterCoverageState
    capability_state: DiscoveryCapabilityState
    per_security_state: PerSecurityEvaluationState
    emitted_leads: tuple[RecallArtifactReference, ...] = ()
    candidate_pool_item: RecallArtifactReference | None = None

    def __post_init__(self) -> None:
        if not all(isinstance(value, expected) for value, expected in (
            (self.funnel_id, DiscoveryFunnelId), (self.horizon, DiscoveryHorizon),
            (self.execution_state, DiscoveryExecutionState), (self.coverage_state, DiscoveryAdapterCoverageState),
            (self.capability_state, DiscoveryCapabilityState), (self.per_security_state, PerSecurityEvaluationState),
        )):
            raise DiscoveryRecallAuditError("DISCOVERY_RECALL_FUNNEL_EVIDENCE_ENUM_INVALID")
        leads = _references(self.emitted_leads, "DISCOVERY_RECALL_LEAD_REFERENCES_INVALID")
        object.__setattr__(self, "emitted_leads", leads)
        if self.candidate_pool_item is not None and not isinstance(self.candidate_pool_item, RecallArtifactReference):
            raise DiscoveryRecallAuditError("DISCOVERY_RECALL_CANDIDATE_REFERENCE_INVALID")
        _validate_funnel_evidence(self)


@dataclass(frozen=True, slots=True)
class BrainDecisionReference:
    state: BrainDecisionState
    artifact: RecallArtifactReference | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.state, BrainDecisionState):
            raise DiscoveryRecallAuditError("DISCOVERY_RECALL_BRAIN_STATE_INVALID")
        if self.state is BrainDecisionState.NOT_EVALUATED_BY_BRAIN:
            if self.artifact is not None:
                raise DiscoveryRecallAuditError("DISCOVERY_RECALL_BRAIN_REFERENCE_FORBIDDEN")
        elif not isinstance(self.artifact, RecallArtifactReference):
            raise DiscoveryRecallAuditError("DISCOVERY_RECALL_BRAIN_REFERENCE_REQUIRED")


@dataclass(frozen=True, slots=True)
class ActionReference:
    state: ActionState
    artifact: RecallArtifactReference | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.state, ActionState):
            raise DiscoveryRecallAuditError("DISCOVERY_RECALL_ACTION_STATE_INVALID")
        needs_reference = self.state is ActionState.ACTION_TAKEN
        if needs_reference != isinstance(self.artifact, RecallArtifactReference):
            raise DiscoveryRecallAuditError("DISCOVERY_RECALL_ACTION_REFERENCE_CONTRADICTION")


@dataclass(frozen=True, slots=True)
class DiscoveryRecallAuditRecord:
    """One immutable security/funnel/horizon audit, never an outcome calculator."""

    discovery_batch: DiscoveryBatchReference
    canonical_instrument_id: str
    funnel: DiscoveryFunnelAuditEvidence
    discovery_state: DiscoveryState
    brain: BrainDecisionReference
    action: ActionReference
    reference_outcome: ReferenceOpportunityOutcome | None = None
    universe_membership_state: UniverseMembershipState = UniverseMembershipState.UNRESOLVED
    universe_membership: RecallArtifactReference | None = None
    audit_id: str = field(init=False)
    process_classification: DiscoveryProcessClassification = field(init=False)
    attribution_classification: AttributionClassification = field(init=False)
    reason_codes: tuple[RecallReason, ...] = field(init=False)
    schema_version: str = DISCOVERY_RECALL_AUDIT_CONTRACT
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        _validate_record(self)
        process = _process_classification(self)
        attribution = _attribution_classification(self)
        reasons = _reasons(self, attribution)
        object.__setattr__(self, "process_classification", process)
        object.__setattr__(self, "attribution_classification", attribution)
        object.__setattr__(self, "reason_codes", reasons)
        object.__setattr__(self, "audit_id", "discovery-recall-audit:" + manifest_fingerprint(**_identity(self))[:32])
        object.__setattr__(self, "fingerprint", "sha256:" + manifest_fingerprint(**_payload(self)))

    def verify(self) -> None:
        _validate_record(self)
        if self.process_classification is not _process_classification(self):
            raise DiscoveryRecallAuditError("DISCOVERY_RECALL_PROCESS_CLASSIFICATION_MISMATCH")
        if self.attribution_classification is not _attribution_classification(self):
            raise DiscoveryRecallAuditError("DISCOVERY_RECALL_ATTRIBUTION_CLASSIFICATION_MISMATCH")
        if self.reason_codes != _reasons(self, self.attribution_classification):
            raise DiscoveryRecallAuditError("DISCOVERY_RECALL_REASON_CODES_MISMATCH")
        if self.audit_id != "discovery-recall-audit:" + manifest_fingerprint(**_identity(self))[:32]:
            raise DiscoveryRecallAuditError("DISCOVERY_RECALL_AUDIT_IDENTITY_MISMATCH")
        if self.fingerprint != "sha256:" + manifest_fingerprint(**_payload(self)):
            raise DiscoveryRecallAuditError("DISCOVERY_RECALL_AUDIT_FINGERPRINT_MISMATCH")


@dataclass(frozen=True, slots=True)
class DiscoveryRecallAuditBatch:
    discovery_batch: DiscoveryBatchReference
    horizon: DiscoveryHorizon
    reference_definition_availability: ReferenceOutcomeDefinitionAvailability
    reference_definition: ReferenceOutcomeDefinitionReference | None
    audits: tuple[DiscoveryRecallAuditRecord, ...]
    batch_id: str = field(init=False)
    auditable_count: int = field(init=False)
    unauditable_count: int = field(init=False)
    classification_counts: tuple[tuple[str, int], ...] = field(init=False)
    missing_dependency_counts: tuple[tuple[str, int], ...] = field(init=False)
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.discovery_batch, DiscoveryBatchReference) or not isinstance(self.horizon, DiscoveryHorizon) or not isinstance(self.reference_definition_availability, ReferenceOutcomeDefinitionAvailability):
            raise DiscoveryRecallAuditError("DISCOVERY_RECALL_BATCH_INPUT_INVALID")
        if (self.reference_definition_availability is ReferenceOutcomeDefinitionAvailability.AVAILABLE) != isinstance(self.reference_definition, ReferenceOutcomeDefinitionReference):
            raise DiscoveryRecallAuditError("DISCOVERY_RECALL_BATCH_REFERENCE_DEFINITION_CONTRADICTION")
        if self.reference_definition is not None and self.reference_definition.horizon is not self.horizon:
            raise DiscoveryRecallAuditError("DISCOVERY_RECALL_BATCH_REFERENCE_HORIZON_MISMATCH")
        audits = tuple(sorted(self.audits, key=lambda value: value.audit_id))
        if not audits or any(not isinstance(value, DiscoveryRecallAuditRecord) for value in audits):
            raise DiscoveryRecallAuditError("DISCOVERY_RECALL_BATCH_AUDITS_REQUIRED")
        if len({value.audit_id for value in audits}) != len(audits):
            raise DiscoveryRecallAuditError("DISCOVERY_RECALL_BATCH_AUDIT_DUPLICATE")
        if any(value.discovery_batch != self.discovery_batch or value.funnel.horizon is not self.horizon for value in audits):
            raise DiscoveryRecallAuditError("DISCOVERY_RECALL_BATCH_AUDIT_BINDING_INVALID")
        if self.reference_definition_availability is ReferenceOutcomeDefinitionAvailability.NOT_ACTIVE and any(value.reference_outcome is not None for value in audits):
            raise DiscoveryRecallAuditError("DISCOVERY_RECALL_BATCH_OUTCOME_BEFORE_DEFINITION")
        object.__setattr__(self, "audits", audits)
        counts = _counts(value.attribution_classification.value for value in audits)
        missing = _counts(reason.value for value in audits for reason in value.reason_codes)
        unauditable = sum(value.attribution_classification is AttributionClassification.UNAUDITABLE for value in audits)
        object.__setattr__(self, "auditable_count", len(audits) - unauditable)
        object.__setattr__(self, "unauditable_count", unauditable)
        object.__setattr__(self, "classification_counts", counts)
        object.__setattr__(self, "missing_dependency_counts", missing)
        object.__setattr__(self, "batch_id", "discovery-recall-batch:" + manifest_fingerprint(**_batch_identity(self))[:32])
        object.__setattr__(self, "fingerprint", "sha256:" + manifest_fingerprint(**_batch_payload(self)))

    def verify(self) -> None:
        for audit in self.audits:
            audit.verify()
        unauditable = sum(value.attribution_classification is AttributionClassification.UNAUDITABLE for value in self.audits)
        if self.auditable_count != len(self.audits) - unauditable or self.unauditable_count != unauditable:
            raise DiscoveryRecallAuditError("DISCOVERY_RECALL_BATCH_AUDITABILITY_COUNTS_MISMATCH")
        if self.classification_counts != _counts(value.attribution_classification.value for value in self.audits):
            raise DiscoveryRecallAuditError("DISCOVERY_RECALL_BATCH_CLASSIFICATION_COUNTS_MISMATCH")
        if self.missing_dependency_counts != _counts(reason.value for value in self.audits for reason in value.reason_codes):
            raise DiscoveryRecallAuditError("DISCOVERY_RECALL_BATCH_MISSING_COUNTS_MISMATCH")
        if self.batch_id != "discovery-recall-batch:" + manifest_fingerprint(**_batch_identity(self))[:32]:
            raise DiscoveryRecallAuditError("DISCOVERY_RECALL_BATCH_IDENTITY_MISMATCH")
        if self.fingerprint != "sha256:" + manifest_fingerprint(**_batch_payload(self)):
            raise DiscoveryRecallAuditError("DISCOVERY_RECALL_BATCH_FINGERPRINT_MISMATCH")


def discovery_recall_audit_payload(value: DiscoveryRecallAuditRecord | DiscoveryRecallAuditBatch) -> dict[str, object]:
    if not isinstance(value, (DiscoveryRecallAuditRecord, DiscoveryRecallAuditBatch)):
        raise DiscoveryRecallAuditError("DISCOVERY_RECALL_VALUE_REQUIRED")
    value.verify()
    if isinstance(value, DiscoveryRecallAuditRecord):
        return _payload(value) | {"fingerprint": value.fingerprint}
    return _batch_payload(value) | {"fingerprint": value.fingerprint}


def serialize_discovery_recall_audit(value: DiscoveryRecallAuditRecord | DiscoveryRecallAuditBatch) -> str:
    return json.dumps(discovery_recall_audit_payload(value), sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def _validate_funnel_evidence(value: DiscoveryFunnelAuditEvidence) -> None:
    active = value.capability_state is DiscoveryCapabilityState.CAPABILITY_AVAILABLE
    if active != (value.execution_state is DiscoveryExecutionState.EVALUATED):
        raise DiscoveryRecallAuditError("DISCOVERY_RECALL_CAPABILITY_EXECUTION_CONTRADICTION")
    if value.capability_state is DiscoveryCapabilityState.DISCOVERY_CAPABILITY_GAP and value.execution_state is not DiscoveryExecutionState.NOT_EXECUTABLE:
        raise DiscoveryRecallAuditError("DISCOVERY_RECALL_CAPABILITY_GAP_CONTRADICTION")
    if value.per_security_state is PerSecurityEvaluationState.TRIGGER_EMITTED:
        if not value.emitted_leads or value.candidate_pool_item is None or not active:
            raise DiscoveryRecallAuditError("DISCOVERY_RECALL_DISCOVERED_LINEAGE_REQUIRED")
    elif value.emitted_leads or value.candidate_pool_item is not None:
        raise DiscoveryRecallAuditError("DISCOVERY_RECALL_NONDISCOVERED_LEAD_CONTRADICTION")
    if value.per_security_state is PerSecurityEvaluationState.EVALUATED_NO_TRIGGER and not active:
        raise DiscoveryRecallAuditError("DISCOVERY_RECALL_NO_TRIGGER_NOT_EVALUATED")
    if value.per_security_state is PerSecurityEvaluationState.FUNNEL_NOT_EVALUATED and value.execution_state is DiscoveryExecutionState.EVALUATED:
        raise DiscoveryRecallAuditError("DISCOVERY_RECALL_FUNNEL_NOT_EVALUATED_CONTRADICTION")
    if value.per_security_state is PerSecurityEvaluationState.IDENTITY_BLOCKED and value.coverage_state is not DiscoveryAdapterCoverageState.IDENTITY_BLOCKED:
        raise DiscoveryRecallAuditError("DISCOVERY_RECALL_IDENTITY_BLOCKED_COVERAGE_REQUIRED")


def _validate_record(value: DiscoveryRecallAuditRecord) -> None:
    if value.schema_version != DISCOVERY_RECALL_AUDIT_CONTRACT or not isinstance(value.discovery_batch, DiscoveryBatchReference):
        raise DiscoveryRecallAuditError("DISCOVERY_RECALL_CONTRACT_INVALID")
    _id(value.canonical_instrument_id, "DISCOVERY_RECALL_INSTRUMENT_ID_INVALID")
    if not isinstance(value.funnel, DiscoveryFunnelAuditEvidence) or not isinstance(value.discovery_state, DiscoveryState) or not isinstance(value.brain, BrainDecisionReference) or not isinstance(value.action, ActionReference):
        raise DiscoveryRecallAuditError("DISCOVERY_RECALL_RECORD_STATE_INVALID")
    if not isinstance(value.universe_membership_state, UniverseMembershipState):
        raise DiscoveryRecallAuditError("DISCOVERY_RECALL_UNIVERSE_MEMBERSHIP_STATE_INVALID")
    if value.universe_membership_state is UniverseMembershipState.ELIGIBLE:
        if not isinstance(value.universe_membership, RecallArtifactReference):
            raise DiscoveryRecallAuditError("DISCOVERY_RECALL_UNIVERSE_MEMBERSHIP_PROOF_REQUIRED")
        if value.universe_membership.available_at > value.discovery_batch.discovery_as_of:
            raise DiscoveryRecallAuditError("DISCOVERY_RECALL_UNIVERSE_MEMBERSHIP_LOOKAHEAD_INVALID")
    elif value.universe_membership_state is UniverseMembershipState.INELIGIBLE:
        if not isinstance(value.universe_membership, RecallArtifactReference):
            raise DiscoveryRecallAuditError("DISCOVERY_RECALL_UNIVERSE_INELIGIBILITY_PROOF_REQUIRED")
        if value.discovery_state in (DiscoveryState.DISCOVERED, DiscoveryState.NOT_DISCOVERED):
            raise DiscoveryRecallAuditError("DISCOVERY_RECALL_UNIVERSE_INELIGIBILITY_CONTRADICTION")
    elif value.universe_membership is not None:
        raise DiscoveryRecallAuditError("DISCOVERY_RECALL_UNIVERSE_MEMBERSHIP_UNRESOLVED_CONTRADICTION")
    if value.reference_outcome is not None:
        if not isinstance(value.reference_outcome, ReferenceOpportunityOutcome):
            raise DiscoveryRecallAuditError("DISCOVERY_RECALL_OUTCOME_REFERENCE_INVALID")
        if value.reference_outcome.canonical_instrument_id != value.canonical_instrument_id or value.reference_outcome.discovery_cutoff != value.discovery_batch.discovery_as_of or value.reference_outcome.definition.horizon is not value.funnel.horizon:
            raise DiscoveryRecallAuditError("DISCOVERY_RECALL_OUTCOME_BINDING_INVALID")
    expected = _expected_discovery_state(value.funnel)
    if value.discovery_state is not expected:
        raise DiscoveryRecallAuditError("DISCOVERY_RECALL_DISCOVERY_STATE_EVIDENCE_CONTRADICTION")
    discovery_artifacts = (*value.funnel.emitted_leads, value.funnel.candidate_pool_item)
    if any(artifact is not None and artifact.available_at > value.discovery_batch.discovery_as_of for artifact in discovery_artifacts):
        raise DiscoveryRecallAuditError("DISCOVERY_RECALL_DISCOVERY_CUTOFF_NOT_TIMELY")
    if value.brain.state is not BrainDecisionState.NOT_EVALUATED_BY_BRAIN and value.discovery_state is not DiscoveryState.DISCOVERED:
        raise DiscoveryRecallAuditError("DISCOVERY_RECALL_BRAIN_WITHOUT_DISCOVERY")
    if value.action.state is ActionState.ACTION_TAKEN and value.brain.state is not BrainDecisionState.ACCEPTED:
        raise DiscoveryRecallAuditError("DISCOVERY_RECALL_ACTION_WITHOUT_BRAIN_ACCEPTANCE")
    if value.reference_outcome is not None and value.reference_outcome.outcome.available_at <= value.discovery_batch.discovery_as_of:
        raise DiscoveryRecallAuditError("DISCOVERY_RECALL_OUTCOME_LOOKAHEAD_INVALID")


def _expected_discovery_state(funnel: DiscoveryFunnelAuditEvidence) -> DiscoveryState:
    return {
        PerSecurityEvaluationState.TRIGGER_EMITTED: DiscoveryState.DISCOVERED,
        PerSecurityEvaluationState.EVALUATED_NO_TRIGGER: DiscoveryState.NOT_DISCOVERED,
        PerSecurityEvaluationState.IDENTITY_BLOCKED: DiscoveryState.IDENTITY_BLOCKED,
        PerSecurityEvaluationState.FUNNEL_NOT_EVALUATED: DiscoveryState.DISCOVERY_NOT_EVALUABLE,
        PerSecurityEvaluationState.PER_SECURITY_EVALUATION_UNKNOWN: DiscoveryState.DISCOVERY_COVERAGE_INCOMPLETE,
        PerSecurityEvaluationState.PER_SECURITY_DATA_BLOCKED: DiscoveryState.DISCOVERY_COVERAGE_INCOMPLETE,
    }[funnel.per_security_state]


def _process_classification(value: DiscoveryRecallAuditRecord) -> DiscoveryProcessClassification:
    if value.discovery_state is DiscoveryState.DISCOVERED:
        if value.brain.state in (BrainDecisionState.REJECTED, BrainDecisionState.GATE_BLOCKED):
            return DiscoveryProcessClassification.DISCOVERED_BUT_REJECTED
        return DiscoveryProcessClassification.DISCOVERY_SUCCESS
    if value.discovery_state is DiscoveryState.NOT_DISCOVERED:
        return DiscoveryProcessClassification.NOT_DISCOVERED_PROCESS
    return DiscoveryProcessClassification.UNAUDITABLE


def _attribution_classification(value: DiscoveryRecallAuditRecord) -> AttributionClassification:
    outcome = value.reference_outcome
    if value.universe_membership_state is not UniverseMembershipState.ELIGIBLE:
        return AttributionClassification.UNAUDITABLE
    if value.discovery_state is not DiscoveryState.DISCOVERED:
        if value.discovery_state is DiscoveryState.NOT_DISCOVERED and outcome is not None and outcome.outcome_maturity is OutcomeMaturity.MATURE and outcome.reference_state is ReferenceOpportunityState.REFERENCE_OPPORTUNITY_CONFIRMED and value.funnel.capability_state is DiscoveryCapabilityState.CAPABILITY_AVAILABLE:
            return AttributionClassification.DISCOVERY_FAILURE
        return AttributionClassification.UNAUDITABLE if value.discovery_state is not DiscoveryState.NOT_DISCOVERED else AttributionClassification.NOT_YET_ATTRIBUTABLE
    if value.brain.state in (BrainDecisionState.REJECTED, BrainDecisionState.GATE_BLOCKED):
        if outcome is not None and outcome.outcome_maturity is OutcomeMaturity.MATURE:
            if outcome.reference_state is ReferenceOpportunityState.REJECTION_SUPPORTED:
                return AttributionClassification.CORRECTLY_REJECTED
            if outcome.reference_state is ReferenceOpportunityState.REFERENCE_OPPORTUNITY_CONFIRMED:
                return AttributionClassification.DECISION_FAILURE
    if value.brain.state is BrainDecisionState.ACCEPTED and value.action.state is ActionState.ACTION_TAKEN:
        if outcome is not None and outcome.outcome_maturity is OutcomeMaturity.MATURE and outcome.reference_state is ReferenceOpportunityState.ACTION_FAILURE_SUPPORTED:
            return AttributionClassification.ACTION_FAILURE
    return AttributionClassification.NOT_YET_ATTRIBUTABLE


def _reasons(value: DiscoveryRecallAuditRecord, attribution: AttributionClassification) -> tuple[RecallReason, ...]:
    reasons: set[RecallReason] = set()
    if value.funnel.capability_state is DiscoveryCapabilityState.DISCOVERY_CAPABILITY_GAP:
        reasons.update((RecallReason.FUNNEL_NOT_OPERATIONAL, RecallReason.DISCOVERY_CAPABILITY_GAP))
    elif value.funnel.capability_state is DiscoveryCapabilityState.CAPABILITY_UNRESOLVED:
        reasons.add(RecallReason.FUNNEL_NOT_EVALUATED)
    per_security = value.funnel.per_security_state
    if per_security is PerSecurityEvaluationState.PER_SECURITY_EVALUATION_UNKNOWN:
        reasons.add(RecallReason.PER_SECURITY_EVALUATION_UNKNOWN)
    elif per_security is PerSecurityEvaluationState.PER_SECURITY_DATA_BLOCKED:
        reasons.add(RecallReason.DATA_BLOCKED)
    elif per_security is PerSecurityEvaluationState.IDENTITY_BLOCKED:
        reasons.add(RecallReason.IDENTITY_UNRESOLVED)
    if value.universe_membership_state is UniverseMembershipState.UNRESOLVED:
        reasons.add(RecallReason.UNIVERSE_MEMBERSHIP_UNRESOLVED)
    elif value.universe_membership_state is UniverseMembershipState.INELIGIBLE:
        reasons.add(RecallReason.UNIVERSE_NOT_ELIGIBLE)
    if value.brain.state is BrainDecisionState.NOT_EVALUATED_BY_BRAIN:
        reasons.add(RecallReason.BRAIN_NOT_EVALUATED)
    elif value.brain.state is BrainDecisionState.GATE_BLOCKED:
        reasons.add(RecallReason.POLICY_BLOCKED)
    if value.action.state is ActionState.ACTION_NOT_YET_AVAILABLE:
        reasons.add(RecallReason.ACTION_LAYER_NOT_AVAILABLE)
    outcome = value.reference_outcome
    if outcome is None:
        reasons.add(RecallReason.REFERENCE_OUTCOME_NOT_DEFINED)
    elif outcome.outcome_maturity is OutcomeMaturity.IMMATURE:
        reasons.add(RecallReason.OUTCOME_IMMATURE)
    elif outcome.outcome_maturity is OutcomeMaturity.DATA_MISSING:
        reasons.add(RecallReason.OUTCOME_DATA_MISSING)
    elif outcome.outcome_maturity is OutcomeMaturity.NON_COMPARABLE:
        reasons.add(RecallReason.OUTCOME_NON_COMPARABLE)
    if attribution is AttributionClassification.DISCOVERY_FAILURE and value.funnel.capability_state is not DiscoveryCapabilityState.CAPABILITY_AVAILABLE:
        raise DiscoveryRecallAuditError("DISCOVERY_RECALL_FAILURE_WITH_CAPABILITY_GAP")
    return tuple(sorted(reasons, key=lambda item: item.value))


def _references(values: tuple[RecallArtifactReference, ...], code: str) -> tuple[RecallArtifactReference, ...]:
    if not isinstance(values, tuple) or any(not isinstance(value, RecallArtifactReference) for value in values):
        raise DiscoveryRecallAuditError(code)
    result = tuple(sorted(values, key=lambda item: (item.reference_id, item.fingerprint, item.available_at)))
    if len({item.reference_id for item in result}) != len(result):
        raise DiscoveryRecallAuditError("DISCOVERY_RECALL_LEAD_REFERENCE_CONFLICT")
    return result


def _identity(value: DiscoveryRecallAuditRecord) -> dict[str, object]:
    return {
        "contract": value.schema_version, "batch_id": value.discovery_batch.batch_id,
        "batch_fingerprint": value.discovery_batch.batch_fingerprint, "instrument": value.canonical_instrument_id,
        "funnel": value.funnel.funnel_id.value, "horizon": value.funnel.horizon.value,
        "discovery_as_of": _time(value.discovery_batch.discovery_as_of),
        "universe_membership_state": value.universe_membership_state.value,
        "universe_membership_id": None if value.universe_membership is None else value.universe_membership.reference_id,
        "universe_membership_fingerprint": None if value.universe_membership is None else value.universe_membership.fingerprint,
        "lead_ids": tuple(item.reference_id for item in value.funnel.emitted_leads),
        "candidate": None if value.funnel.candidate_pool_item is None else value.funnel.candidate_pool_item.reference_id,
    }


def _payload(value: DiscoveryRecallAuditRecord) -> dict[str, object]:
    outcome = value.reference_outcome
    return _identity(value) | {
        "discovery_batch": _batch_reference(value.discovery_batch), "funnel": _funnel(value.funnel),
        "universe_membership": {
            "state": value.universe_membership_state.value,
            "artifact": None if value.universe_membership is None else _ref(value.universe_membership),
        },
        "discovery_state": value.discovery_state.value, "brain": _brain(value.brain), "action": _action(value.action),
        "reference_outcome": None if outcome is None else _outcome(outcome),
        "process_classification": value.process_classification.value,
        "attribution_classification": value.attribution_classification.value,
        "reason_codes": tuple(item.value for item in value.reason_codes), "audit_id": value.audit_id,
    }


def _batch_identity(value: DiscoveryRecallAuditBatch) -> dict[str, object]:
    return {"contract": DISCOVERY_RECALL_AUDIT_CONTRACT, "discovery_batch": _batch_reference(value.discovery_batch),
        "horizon": value.horizon.value, "reference_definition_availability": value.reference_definition_availability.value,
        "reference_definition": None if value.reference_definition is None else _definition(value.reference_definition),
        "audit_ids": tuple(item.audit_id for item in value.audits)}


def _batch_payload(value: DiscoveryRecallAuditBatch) -> dict[str, object]:
    return _batch_identity(value) | {"batch_id": value.batch_id, "audits": tuple(_payload(item) for item in value.audits),
        "auditable_count": value.auditable_count, "unauditable_count": value.unauditable_count,
        "classification_counts": value.classification_counts, "missing_dependency_counts": value.missing_dependency_counts}


def _batch_reference(value: DiscoveryBatchReference) -> dict[str, object]:
    return {"batch_id": value.batch_id, "fingerprint": value.batch_fingerprint, "discovery_as_of": _time(value.discovery_as_of),
        "universe_snapshot_id": value.universe_snapshot_id, "universe_snapshot_fingerprint": value.universe_snapshot_fingerprint,
        "registry_id": value.registry_id, "registry_version": value.registry_version, "registry_fingerprint": value.registry_fingerprint}


def _funnel(value: DiscoveryFunnelAuditEvidence) -> dict[str, object]:
    return {"funnel": value.funnel_id.value, "horizon": value.horizon.value, "execution": value.execution_state.value,
        "coverage": value.coverage_state.value, "capability": value.capability_state.value,
        "per_security": value.per_security_state.value, "leads": tuple(_ref(item) for item in value.emitted_leads),
        "candidate": None if value.candidate_pool_item is None else _ref(value.candidate_pool_item)}


def _brain(value: BrainDecisionReference) -> dict[str, object]:
    return {"state": value.state.value, "artifact": None if value.artifact is None else _ref(value.artifact)}


def _action(value: ActionReference) -> dict[str, object]:
    return {"state": value.state.value, "artifact": None if value.artifact is None else _ref(value.artifact)}


def _definition(value: ReferenceOutcomeDefinitionReference) -> dict[str, object]:
    return {"id": value.definition_id, "version": value.definition_version, "fingerprint": value.definition_fingerprint, "horizon": value.horizon.value}


def _outcome(value: ReferenceOpportunityOutcome) -> dict[str, object]:
    return {"outcome": _ref(value.outcome), "definition": _definition(value.definition), "instrument": value.canonical_instrument_id,
        "discovery_cutoff": _time(value.discovery_cutoff), "outcome_observed_at": _time(value.outcome_observed_at),
        "maturity": value.outcome_maturity.value, "reference_state": value.reference_state.value}


def _ref(value: RecallArtifactReference) -> dict[str, object]:
    return {"id": value.reference_id, "fingerprint": value.fingerprint, "available_at": _time(value.available_at)}


def _counts(values) -> tuple[tuple[str, int], ...]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return tuple(sorted(counts.items()))


def _id(value: str | None, code: str) -> None:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise DiscoveryRecallAuditError(code)


def _fp(value: str | None, code: str) -> None:
    if not isinstance(value, str) or not _FP.fullmatch(value):
        raise DiscoveryRecallAuditError(code)


def _text(value: str | None, code: str) -> None:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise DiscoveryRecallAuditError(code)


def _utc(value: datetime, code: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise DiscoveryRecallAuditError(code)
    return value.astimezone(UTC)


def _time(value: datetime) -> str:
    return _utc(value, "DISCOVERY_RECALL_TIMESTAMP_INVALID").isoformat()


__all__ = [
    "ActionReference", "ActionState", "AttributionClassification", "BrainDecisionReference", "BrainDecisionState",
    "DISCOVERY_RECALL_AUDIT_CONTRACT", "DiscoveryBatchReference", "DiscoveryCapabilityState", "DiscoveryFunnelAuditEvidence",
    "DiscoveryProcessClassification", "DiscoveryRecallAuditBatch", "DiscoveryRecallAuditError", "DiscoveryRecallAuditRecord",
    "DiscoveryState", "OutcomeMaturity", "PerSecurityEvaluationState", "RecallArtifactReference", "RecallReason",
    "ReferenceOpportunityOutcome", "ReferenceOpportunityState", "ReferenceOutcomeDefinitionAvailability",
    "ReferenceOutcomeDefinitionReference", "UniverseMembershipState", "discovery_recall_audit_payload",
    "serialize_discovery_recall_audit",
]
