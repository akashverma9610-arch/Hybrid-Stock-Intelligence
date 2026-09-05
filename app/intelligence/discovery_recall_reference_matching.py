"""Independent reference-outcome and frozen-discovery matching contracts.

Reference ground truth contains no HSI discovery, Brain, action, portfolio, or
performance result.  The matcher consumes that independent record and an
already-frozen discovery batch without altering either boundary.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from app.historical.guard import manifest_fingerprint
from app.intelligence.multi_funnel_discovery import (
    CanonicalDiscoveryLead,
    DiscoveryFunnelId,
    DiscoveryLeadReadiness,
)
from app.intelligence.multi_funnel_orchestration import (
    DiscoveryExecutionState,
    WholeMarketDiscoveryBatch,
)


DISCOVERY_RECALL_REFERENCE_CONTRACT = "discovery-recall-reference-outcome/v1"
DISCOVERY_RECALL_MATCHING_CONTRACT = "discovery-recall-matching/v1"
_ID = re.compile(r"[A-Za-z0-9._:-]+\Z")
_FP = re.compile(r"(?:sha256:)?[0-9a-f]{64}\Z")


class DiscoveryRecallReferenceError(ValueError):
    """Stable fail-closed error; no provider, action, or market detail leaks."""


class ReferenceOpportunityHorizon(StrEnum):
    SHORT_TERM = "SHORT_TERM"
    POSITIONAL = "POSITIONAL"
    LONG_TERM = "LONG_TERM"


class ReferenceMeasurementFamily(StrEnum):
    SHORT_TERM_CATALYST = "SHORT_TERM_CATALYST"
    POSITIONAL_MARKET_PATH = "POSITIONAL_MARKET_PATH"
    LONG_TERM_BUSINESS_PERSISTENCE = "LONG_TERM_BUSINESS_PERSISTENCE"


class ReferencePolicyStatus(StrEnum):
    PROPOSED = "PROPOSED"
    RESEARCH_ONLY = "RESEARCH_ONLY"
    ACTIVE = "ACTIVE"


class ReferenceInputRequirement(StrEnum):
    HISTORICAL_UNIVERSE = "HISTORICAL_UNIVERSE"
    CANONICAL_IDENTITY = "CANONICAL_IDENTITY"
    PRICE_INTEGRITY = "PRICE_INTEGRITY"
    BENCHMARK = "BENCHMARK"
    SECTOR_BENCHMARK = "SECTOR_BENCHMARK"
    LIQUIDITY_TRADABILITY = "LIQUIDITY_TRADABILITY"
    EVENT_PUBLIC_TIME = "EVENT_PUBLIC_TIME"
    BUSINESS_OUTCOME = "BUSINESS_OUTCOME"


class ReferenceParameterState(StrEnum):
    UNSELECTED = "UNSELECTED"
    FROZEN = "FROZEN"


class ReferenceOutcomeMaturity(StrEnum):
    NOT_EVALUATED = "NOT_EVALUATED"
    IMMATURE = "IMMATURE"
    PARTIALLY_MATURE = "PARTIALLY_MATURE"
    MATURE = "MATURE"
    DATA_MISSING = "DATA_MISSING"
    NON_COMPARABLE = "NON_COMPARABLE"


class IndependentReferenceOutcomeState(StrEnum):
    REFERENCE_OPPORTUNITY = "REFERENCE_OPPORTUNITY"
    REFERENCE_NON_OPPORTUNITY = "REFERENCE_NON_OPPORTUNITY"
    INCONCLUSIVE = "INCONCLUSIVE"
    IMMATURE = "IMMATURE"
    DATA_MISSING = "DATA_MISSING"
    NON_COMPARABLE = "NON_COMPARABLE"
    UNIVERSE_INELIGIBLE = "UNIVERSE_INELIGIBLE"
    IDENTITY_UNRESOLVED = "IDENTITY_UNRESOLVED"
    POLICY_NOT_ACTIVE = "POLICY_NOT_ACTIVE"


class ReferenceFunnelRelevance(StrEnum):
    RELEVANT = "RELEVANT"
    IRRELEVANT = "IRRELEVANT"
    UNRESOLVED = "UNRESOLVED"


class PerSecurityDiscoveryState(StrEnum):
    EVALUATED_NO_TRIGGER = "EVALUATED_NO_TRIGGER"
    DATA_BLOCKED = "DATA_BLOCKED"
    IDENTITY_BLOCKED = "IDENTITY_BLOCKED"
    NOT_EVALUATED = "NOT_EVALUATED"


class DiscoveryPosture(StrEnum):
    OPERATIONAL_DISCOVERY = "OPERATIONAL_DISCOVERY"
    RESEARCH_SHADOW_DISCOVERY = "RESEARCH_SHADOW_DISCOVERY"
    PARTIAL_DISCOVERY_EVIDENCE = "PARTIAL_DISCOVERY_EVIDENCE"


class DiscoveryReferenceMatchState(StrEnum):
    TIMELY_DISCOVERY_MATCH = "TIMELY_DISCOVERY_MATCH"
    LATE_DISCOVERY_MATCH = "LATE_DISCOVERY_MATCH"
    NO_DISCOVERY_MATCH = "NO_DISCOVERY_MATCH"
    DISCOVERY_NOT_AUDITABLE = "DISCOVERY_NOT_AUDITABLE"
    SECURITY_NOT_IN_UNIVERSE = "SECURITY_NOT_IN_UNIVERSE"
    FUNNEL_NOT_CAPABLE = "FUNNEL_NOT_CAPABLE"
    FUNNEL_NOT_EVALUATED = "FUNNEL_NOT_EVALUATED"
    PER_SECURITY_EVALUATION_UNKNOWN = "PER_SECURITY_EVALUATION_UNKNOWN"
    IDENTITY_CONFLICTED = "IDENTITY_CONFLICTED"
    REFERENCE_OUTCOME_IMMATURE = "REFERENCE_OUTCOME_IMMATURE"
    REFERENCE_POLICY_NOT_ACTIVE = "REFERENCE_POLICY_NOT_ACTIVE"
    REFERENCE_NON_OPPORTUNITY = "REFERENCE_NON_OPPORTUNITY"


@dataclass(frozen=True, slots=True)
class ReferenceEvidence:
    evidence_id: str
    fingerprint: str
    known_at: datetime
    requirement: ReferenceInputRequirement

    def __post_init__(self) -> None:
        _id(self.evidence_id, "DISCOVERY_RECALL_REFERENCE_EVIDENCE_ID_INVALID")
        _fp(self.fingerprint, "DISCOVERY_RECALL_REFERENCE_EVIDENCE_FINGERPRINT_INVALID")
        if not isinstance(self.requirement, ReferenceInputRequirement):
            raise DiscoveryRecallReferenceError("DISCOVERY_RECALL_REFERENCE_EVIDENCE_REQUIREMENT_INVALID")
        object.__setattr__(self, "known_at", _utc(self.known_at, "DISCOVERY_RECALL_REFERENCE_EVIDENCE_TIME_INVALID"))


@dataclass(frozen=True, slots=True)
class ReferenceParameter:
    parameter_id: str
    state: ReferenceParameterState
    frozen_value: str | None = None

    def __post_init__(self) -> None:
        _id(self.parameter_id, "DISCOVERY_RECALL_REFERENCE_PARAMETER_ID_INVALID")
        if not isinstance(self.state, ReferenceParameterState):
            raise DiscoveryRecallReferenceError("DISCOVERY_RECALL_REFERENCE_PARAMETER_STATE_INVALID")
        if self.state is ReferenceParameterState.UNSELECTED:
            if self.frozen_value is not None:
                raise DiscoveryRecallReferenceError("DISCOVERY_RECALL_REFERENCE_PARAMETER_UNSELECTED_VALUE")
        else:
            _text(self.frozen_value, "DISCOVERY_RECALL_REFERENCE_PARAMETER_FROZEN_VALUE_REQUIRED")


@dataclass(frozen=True, slots=True)
class ReferenceOpportunitySpecification:
    specification_id: str
    version: str
    horizon: ReferenceOpportunityHorizon
    measurement_family: ReferenceMeasurementFamily
    historical_universe_id: str
    historical_universe_fingerprint: str
    effective_at: datetime
    observation_semantics_id: str
    discovery_deadline_semantics_id: str
    outcome_horizon_semantics_id: str
    required_inputs: tuple[ReferenceInputRequirement, ...]
    parameters: tuple[ReferenceParameter, ...]
    exclusion_ids: tuple[str, ...]
    policy_status: ReferencePolicyStatus
    provenance: tuple[ReferenceEvidence, ...]
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        for value in (
            self.specification_id,
            self.historical_universe_id,
            self.observation_semantics_id,
            self.discovery_deadline_semantics_id,
            self.outcome_horizon_semantics_id,
        ):
            _id(value, "DISCOVERY_RECALL_REFERENCE_SPECIFICATION_ID_INVALID")
        _text(self.version, "DISCOVERY_RECALL_REFERENCE_SPECIFICATION_VERSION_INVALID")
        _fp(self.historical_universe_fingerprint, "DISCOVERY_RECALL_REFERENCE_UNIVERSE_FINGERPRINT_INVALID")
        object.__setattr__(self, "effective_at", _utc(self.effective_at, "DISCOVERY_RECALL_REFERENCE_SPECIFICATION_EFFECTIVE_TIME_INVALID"))
        if not isinstance(self.horizon, ReferenceOpportunityHorizon) or not isinstance(self.measurement_family, ReferenceMeasurementFamily) or not isinstance(self.policy_status, ReferencePolicyStatus):
            raise DiscoveryRecallReferenceError("DISCOVERY_RECALL_REFERENCE_SPECIFICATION_ENUM_INVALID")
        _family_matches_horizon(self.measurement_family, self.horizon)
        inputs = _enum_values(self.required_inputs, ReferenceInputRequirement, "DISCOVERY_RECALL_REFERENCE_INPUTS_INVALID")
        parameters = _parameters(self.parameters)
        provenance = _evidence_tuple(self.provenance)
        exclusions = _ids(self.exclusion_ids, "DISCOVERY_RECALL_REFERENCE_EXCLUSIONS_INVALID")
        if not inputs or not provenance:
            raise DiscoveryRecallReferenceError("DISCOVERY_RECALL_REFERENCE_SPECIFICATION_LINEAGE_REQUIRED")
        if any(item.known_at > self.effective_at for item in provenance):
            raise DiscoveryRecallReferenceError("DISCOVERY_RECALL_REFERENCE_SPECIFICATION_PROVENANCE_AFTER_EFFECTIVE")
        if self.policy_status is ReferencePolicyStatus.ACTIVE and any(item.state is not ReferenceParameterState.FROZEN for item in parameters):
            raise DiscoveryRecallReferenceError("DISCOVERY_RECALL_REFERENCE_ACTIVE_PARAMETER_UNSELECTED")
        object.__setattr__(self, "required_inputs", inputs)
        object.__setattr__(self, "parameters", parameters)
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(self, "exclusion_ids", exclusions)
        object.__setattr__(self, "fingerprint", "sha256:" + manifest_fingerprint(**_specification_payload(self)))

    def verify(self) -> None:
        _verify(self, "DISCOVERY_RECALL_REFERENCE_SPECIFICATION_TAMPERED")


@dataclass(frozen=True, slots=True)
class IndependentReferenceOutcome:
    """Independent ground-truth receipt; it intentionally has no HSI fields."""

    specification: ReferenceOpportunitySpecification
    canonical_instrument_id: str
    historical_universe_membership: ReferenceEvidence | None
    observation_at: datetime
    opportunity_onset: datetime | None
    discovery_deadline: datetime
    outcome_horizon_end: datetime
    maturity: ReferenceOutcomeMaturity
    state: IndependentReferenceOutcomeState
    evidence: tuple[ReferenceEvidence, ...]
    reason_codes: tuple[str, ...]
    outcome_id: str = field(init=False)
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.specification, ReferenceOpportunitySpecification):
            raise DiscoveryRecallReferenceError("DISCOVERY_RECALL_REFERENCE_OUTCOME_SPECIFICATION_REQUIRED")
        self.specification.verify()
        _id(self.canonical_instrument_id, "DISCOVERY_RECALL_REFERENCE_OUTCOME_INSTRUMENT_INVALID")
        if self.historical_universe_membership is not None and not isinstance(self.historical_universe_membership, ReferenceEvidence):
            raise DiscoveryRecallReferenceError("DISCOVERY_RECALL_REFERENCE_UNIVERSE_MEMBERSHIP_INVALID")
        object.__setattr__(self, "observation_at", _utc(self.observation_at, "DISCOVERY_RECALL_REFERENCE_OBSERVATION_TIME_INVALID"))
        if self.opportunity_onset is not None:
            object.__setattr__(self, "opportunity_onset", _utc(self.opportunity_onset, "DISCOVERY_RECALL_REFERENCE_ONSET_TIME_INVALID"))
        object.__setattr__(self, "discovery_deadline", _utc(self.discovery_deadline, "DISCOVERY_RECALL_REFERENCE_DEADLINE_INVALID"))
        object.__setattr__(self, "outcome_horizon_end", _utc(self.outcome_horizon_end, "DISCOVERY_RECALL_REFERENCE_HORIZON_END_INVALID"))
        if not self.observation_at <= self.discovery_deadline <= self.outcome_horizon_end:
            raise DiscoveryRecallReferenceError("DISCOVERY_RECALL_REFERENCE_TIMELINE_INVALID")
        if self.historical_universe_membership is not None and (
            self.historical_universe_membership.requirement is not ReferenceInputRequirement.HISTORICAL_UNIVERSE
            or self.historical_universe_membership.known_at > self.observation_at
        ):
            raise DiscoveryRecallReferenceError("DISCOVERY_RECALL_REFERENCE_UNIVERSE_MEMBERSHIP_TIMING_INVALID")
        if self.opportunity_onset is not None and self.opportunity_onset > self.discovery_deadline:
            raise DiscoveryRecallReferenceError("DISCOVERY_RECALL_REFERENCE_ONSET_AFTER_DEADLINE")
        if not isinstance(self.maturity, ReferenceOutcomeMaturity) or not isinstance(self.state, IndependentReferenceOutcomeState):
            raise DiscoveryRecallReferenceError("DISCOVERY_RECALL_REFERENCE_OUTCOME_ENUM_INVALID")
        evidence = _evidence_tuple(self.evidence)
        reasons = _ids(self.reason_codes, "DISCOVERY_RECALL_REFERENCE_REASONS_INVALID")
        _validate_outcome_state(self, evidence)
        if any(item.known_at > self.outcome_horizon_end for item in evidence):
            raise DiscoveryRecallReferenceError("DISCOVERY_RECALL_REFERENCE_OUTCOME_EVIDENCE_AFTER_HORIZON")
        object.__setattr__(self, "evidence", evidence)
        object.__setattr__(self, "reason_codes", reasons)
        object.__setattr__(self, "outcome_id", "reference-outcome:" + manifest_fingerprint(**_outcome_identity(self))[:32])
        object.__setattr__(self, "fingerprint", "sha256:" + manifest_fingerprint(**_outcome_payload(self)))

    def verify(self) -> None:
        self.specification.verify()
        _verify(self, "DISCOVERY_RECALL_REFERENCE_OUTCOME_TAMPERED")


@dataclass(frozen=True, slots=True)
class ReferenceFunnelEligibility:
    horizon: ReferenceOpportunityHorizon
    funnel_id: DiscoveryFunnelId
    relevance: ReferenceFunnelRelevance
    evidence: ReferenceEvidence

    def __post_init__(self) -> None:
        if not isinstance(self.horizon, ReferenceOpportunityHorizon) or not isinstance(self.funnel_id, DiscoveryFunnelId) or not isinstance(self.relevance, ReferenceFunnelRelevance) or not isinstance(self.evidence, ReferenceEvidence):
            raise DiscoveryRecallReferenceError("DISCOVERY_RECALL_REFERENCE_FUNNEL_ELIGIBILITY_INVALID")


@dataclass(frozen=True, slots=True)
class PerSecurityDiscoveryEvaluation:
    discovery_batch_id: str
    discovery_batch_fingerprint: str
    canonical_instrument_id: str
    funnel_id: DiscoveryFunnelId
    state: PerSecurityDiscoveryState
    evidence: ReferenceEvidence

    def __post_init__(self) -> None:
        _id(self.discovery_batch_id, "DISCOVERY_RECALL_PER_SECURITY_BATCH_INVALID")
        _fp(self.discovery_batch_fingerprint, "DISCOVERY_RECALL_PER_SECURITY_BATCH_FINGERPRINT_INVALID")
        _id(self.canonical_instrument_id, "DISCOVERY_RECALL_PER_SECURITY_INSTRUMENT_INVALID")
        if not isinstance(self.funnel_id, DiscoveryFunnelId) or not isinstance(self.state, PerSecurityDiscoveryState) or not isinstance(self.evidence, ReferenceEvidence):
            raise DiscoveryRecallReferenceError("DISCOVERY_RECALL_PER_SECURITY_STATE_INVALID")


@dataclass(frozen=True, slots=True)
class ReferenceDiscoveryMatch:
    reference_outcome_id: str
    reference_outcome_fingerprint: str
    discovery_batch_id: str
    discovery_batch_fingerprint: str
    canonical_instrument_id: str
    horizon: ReferenceOpportunityHorizon
    system_state: DiscoveryReferenceMatchState
    matching_lead_ids: tuple[str, ...]
    timely_lead_ids: tuple[str, ...]
    late_lead_ids: tuple[str, ...]
    matching_funnels: tuple[DiscoveryFunnelId, ...]
    postures: tuple[DiscoveryPosture, ...]
    relevant_funnel_coverage: tuple[tuple[DiscoveryFunnelId, DiscoveryReferenceMatchState], ...]
    audit_readiness: DiscoveryReferenceMatchState
    match_id: str = field(init=False)
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        _id(self.reference_outcome_id, "DISCOVERY_RECALL_MATCH_OUTCOME_ID_INVALID")
        _fp(self.reference_outcome_fingerprint, "DISCOVERY_RECALL_MATCH_OUTCOME_FINGERPRINT_INVALID")
        _id(self.discovery_batch_id, "DISCOVERY_RECALL_MATCH_BATCH_ID_INVALID")
        _fp(self.discovery_batch_fingerprint, "DISCOVERY_RECALL_MATCH_BATCH_FINGERPRINT_INVALID")
        _id(self.canonical_instrument_id, "DISCOVERY_RECALL_MATCH_INSTRUMENT_INVALID")
        if not isinstance(self.horizon, ReferenceOpportunityHorizon) or not isinstance(self.system_state, DiscoveryReferenceMatchState) or not isinstance(self.audit_readiness, DiscoveryReferenceMatchState):
            raise DiscoveryRecallReferenceError("DISCOVERY_RECALL_MATCH_STATE_INVALID")
        object.__setattr__(self, "matching_lead_ids", _ids(self.matching_lead_ids, "DISCOVERY_RECALL_MATCH_LEAD_IDS_INVALID"))
        object.__setattr__(self, "timely_lead_ids", _ids(self.timely_lead_ids, "DISCOVERY_RECALL_MATCH_TIMELY_IDS_INVALID"))
        object.__setattr__(self, "late_lead_ids", _ids(self.late_lead_ids, "DISCOVERY_RECALL_MATCH_LATE_IDS_INVALID"))
        if set(self.timely_lead_ids) | set(self.late_lead_ids) != set(self.matching_lead_ids) or set(self.timely_lead_ids) & set(self.late_lead_ids):
            raise DiscoveryRecallReferenceError("DISCOVERY_RECALL_MATCH_LEAD_PARTITION_INVALID")
        funnels = _enum_values(self.matching_funnels, DiscoveryFunnelId, "DISCOVERY_RECALL_MATCH_FUNNELS_INVALID", allow_empty=True)
        postures = _enum_values(self.postures, DiscoveryPosture, "DISCOVERY_RECALL_MATCH_POSTURES_INVALID", allow_empty=True)
        if not isinstance(self.relevant_funnel_coverage, tuple) or any(
            not isinstance(item, tuple)
            or len(item) != 2
            or not isinstance(item[0], DiscoveryFunnelId)
            or not isinstance(item[1], DiscoveryReferenceMatchState)
            for item in self.relevant_funnel_coverage
        ):
            raise DiscoveryRecallReferenceError("DISCOVERY_RECALL_MATCH_COVERAGE_INVALID")
        coverage = tuple(sorted(self.relevant_funnel_coverage, key=lambda item: item[0].value))
        if not coverage or len({item[0] for item in coverage}) != len(coverage):
            raise DiscoveryRecallReferenceError("DISCOVERY_RECALL_MATCH_COVERAGE_INVALID")
        object.__setattr__(self, "matching_funnels", funnels)
        object.__setattr__(self, "postures", postures)
        object.__setattr__(self, "relevant_funnel_coverage", coverage)
        object.__setattr__(self, "match_id", "reference-discovery-match:" + manifest_fingerprint(**_match_identity(self))[:32])
        object.__setattr__(self, "fingerprint", "sha256:" + manifest_fingerprint(**_match_payload(self)))

    def verify(self) -> None:
        _verify(self, "DISCOVERY_RECALL_MATCH_TAMPERED")


def match_reference_outcome(*, outcome: IndependentReferenceOutcome, discovery: WholeMarketDiscoveryBatch,
                            funnel_eligibility: tuple[ReferenceFunnelEligibility, ...],
                            per_security_evaluations: tuple[PerSecurityDiscoveryEvaluation, ...] = ()) -> ReferenceDiscoveryMatch:
    """Read immutable inputs only; never creates a recall failure or modifies discovery."""
    if not isinstance(outcome, IndependentReferenceOutcome) or not isinstance(discovery, WholeMarketDiscoveryBatch):
        raise DiscoveryRecallReferenceError("DISCOVERY_RECALL_MATCH_INPUT_INVALID")
    outcome.verify(); discovery.verify()
    eligibility = _eligibility(funnel_eligibility, outcome.specification.horizon)
    if any(item.evidence.known_at > outcome.observation_at for item in eligibility):
        raise DiscoveryRecallReferenceError("DISCOVERY_RECALL_REFERENCE_FUNNEL_MAPPING_AFTER_OBSERVATION")
    evaluations = _evaluations(per_security_evaluations, discovery, outcome.canonical_instrument_id)
    relevant = tuple(item for item in eligibility if item.relevance is ReferenceFunnelRelevance.RELEVANT)
    base = _precondition_state(outcome)
    candidates = tuple(item for item in discovery.candidate_union.candidates if item.canonical_instrument_id == outcome.canonical_instrument_id)
    if len(candidates) > 1:
        raise DiscoveryRecallReferenceError("DISCOVERY_RECALL_MATCH_CANDIDATE_IDENTITY_CONFLICT")
    leads = () if not candidates else tuple(origin.lead for origin in candidates[0].origins if origin.lead.funnel_id in {item.funnel_id for item in relevant})
    timely = tuple(sorted(item.lead_id for item in leads if discovery.as_of <= outcome.discovery_deadline and _posture(item.readiness) is not DiscoveryPosture.PARTIAL_DISCOVERY_EVIDENCE))
    late = tuple(sorted(
        item.lead_id
        for item in leads
        if discovery.as_of > outcome.discovery_deadline
        and _posture(item.readiness) is not DiscoveryPosture.PARTIAL_DISCOVERY_EVIDENCE
    ))
    matching = tuple(sorted((*timely, *late)))
    postures = tuple(sorted({_posture(item.readiness) for item in leads}, key=lambda item: item.value))
    funnels = tuple(sorted({item.funnel_id for item in leads}, key=lambda item: item.value))
    coverage = tuple((item.funnel_id, _funnel_match_state(
        discovery=discovery,
        funnel=item.funnel_id,
        deadline=outcome.discovery_deadline,
        leads=tuple(lead for lead in leads if lead.funnel_id is item.funnel_id),
        evaluations=tuple(evaluation for evaluation in evaluations if evaluation.funnel_id is item.funnel_id),
    )) for item in relevant)
    if base is not None:
        state = readiness = base
    elif any(item is DiscoveryReferenceMatchState.TIMELY_DISCOVERY_MATCH for _, item in coverage):
        state = readiness = DiscoveryReferenceMatchState.TIMELY_DISCOVERY_MATCH
    elif any(item is DiscoveryReferenceMatchState.LATE_DISCOVERY_MATCH for _, item in coverage):
        state = readiness = DiscoveryReferenceMatchState.LATE_DISCOVERY_MATCH
    elif any(item is DiscoveryReferenceMatchState.NO_DISCOVERY_MATCH for _, item in coverage):
        state = readiness = DiscoveryReferenceMatchState.NO_DISCOVERY_MATCH
    elif any(item is DiscoveryReferenceMatchState.IDENTITY_CONFLICTED for _, item in coverage):
        state = readiness = DiscoveryReferenceMatchState.IDENTITY_CONFLICTED
    elif any(item is DiscoveryReferenceMatchState.DISCOVERY_NOT_AUDITABLE for _, item in coverage):
        state = readiness = DiscoveryReferenceMatchState.DISCOVERY_NOT_AUDITABLE
    elif any(item is DiscoveryReferenceMatchState.FUNNEL_NOT_EVALUATED for _, item in coverage):
        state = readiness = DiscoveryReferenceMatchState.FUNNEL_NOT_EVALUATED
    elif any(item is DiscoveryReferenceMatchState.FUNNEL_NOT_CAPABLE for _, item in coverage):
        state = readiness = DiscoveryReferenceMatchState.FUNNEL_NOT_CAPABLE
    else:
        state = readiness = DiscoveryReferenceMatchState.PER_SECURITY_EVALUATION_UNKNOWN
    return ReferenceDiscoveryMatch(outcome.outcome_id, outcome.fingerprint, discovery.batch_id, discovery.fingerprint,
        outcome.canonical_instrument_id, outcome.specification.horizon, state, matching, timely, late, funnels,
        postures, coverage, readiness)


def serialize_reference(value: ReferenceOpportunitySpecification | IndependentReferenceOutcome | ReferenceDiscoveryMatch) -> str:
    value.verify()
    payload = _specification_payload(value) if isinstance(value, ReferenceOpportunitySpecification) else _outcome_payload(value) if isinstance(value, IndependentReferenceOutcome) else _match_payload(value)
    return json.dumps(payload | {"fingerprint": value.fingerprint}, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def _validate_outcome_state(value: IndependentReferenceOutcome, evidence: tuple[ReferenceEvidence, ...]) -> None:
    state, maturity = value.state, value.maturity
    mature = {IndependentReferenceOutcomeState.REFERENCE_OPPORTUNITY, IndependentReferenceOutcomeState.REFERENCE_NON_OPPORTUNITY, IndependentReferenceOutcomeState.INCONCLUSIVE}
    if state in mature:
        if value.specification.policy_status is not ReferencePolicyStatus.ACTIVE:
            raise DiscoveryRecallReferenceError("DISCOVERY_RECALL_REFERENCE_POLICY_NOT_ACTIVE")
        if maturity is not ReferenceOutcomeMaturity.MATURE or value.historical_universe_membership is None:
            raise DiscoveryRecallReferenceError("DISCOVERY_RECALL_REFERENCE_MATURE_OUTCOME_LINEAGE_REQUIRED")
        requirements = set(value.specification.required_inputs)
        if not requirements <= {item.requirement for item in evidence}:
            raise DiscoveryRecallReferenceError("DISCOVERY_RECALL_REFERENCE_REQUIRED_INPUT_MISSING")
        if value.specification.effective_at > value.observation_at:
            raise DiscoveryRecallReferenceError("DISCOVERY_RECALL_REFERENCE_POLICY_AFTER_OBSERVATION")
    elif state is IndependentReferenceOutcomeState.IMMATURE and maturity not in {ReferenceOutcomeMaturity.IMMATURE, ReferenceOutcomeMaturity.PARTIALLY_MATURE}:
        raise DiscoveryRecallReferenceError("DISCOVERY_RECALL_REFERENCE_IMMATURE_STATE_CONTRADICTION")
    elif state is IndependentReferenceOutcomeState.DATA_MISSING and maturity is not ReferenceOutcomeMaturity.DATA_MISSING:
        raise DiscoveryRecallReferenceError("DISCOVERY_RECALL_REFERENCE_DATA_MISSING_CONTRADICTION")
    elif state is IndependentReferenceOutcomeState.NON_COMPARABLE and maturity is not ReferenceOutcomeMaturity.NON_COMPARABLE:
        raise DiscoveryRecallReferenceError("DISCOVERY_RECALL_REFERENCE_NONCOMPARABLE_CONTRADICTION")
    elif state in {IndependentReferenceOutcomeState.UNIVERSE_INELIGIBLE, IndependentReferenceOutcomeState.IDENTITY_UNRESOLVED, IndependentReferenceOutcomeState.POLICY_NOT_ACTIVE} and maturity is not ReferenceOutcomeMaturity.NOT_EVALUATED:
        raise DiscoveryRecallReferenceError("DISCOVERY_RECALL_REFERENCE_NOT_EVALUATED_CONTRADICTION")
    if state is IndependentReferenceOutcomeState.POLICY_NOT_ACTIVE and value.specification.policy_status is ReferencePolicyStatus.ACTIVE:
        raise DiscoveryRecallReferenceError("DISCOVERY_RECALL_REFERENCE_POLICY_STATE_CONTRADICTION")


def _precondition_state(value: IndependentReferenceOutcome) -> DiscoveryReferenceMatchState | None:
    return {
        IndependentReferenceOutcomeState.POLICY_NOT_ACTIVE: DiscoveryReferenceMatchState.REFERENCE_POLICY_NOT_ACTIVE,
        IndependentReferenceOutcomeState.IMMATURE: DiscoveryReferenceMatchState.REFERENCE_OUTCOME_IMMATURE,
        IndependentReferenceOutcomeState.UNIVERSE_INELIGIBLE: DiscoveryReferenceMatchState.SECURITY_NOT_IN_UNIVERSE,
        IndependentReferenceOutcomeState.IDENTITY_UNRESOLVED: DiscoveryReferenceMatchState.IDENTITY_CONFLICTED,
        IndependentReferenceOutcomeState.REFERENCE_NON_OPPORTUNITY: DiscoveryReferenceMatchState.REFERENCE_NON_OPPORTUNITY,
        IndependentReferenceOutcomeState.INCONCLUSIVE: DiscoveryReferenceMatchState.DISCOVERY_NOT_AUDITABLE,
        IndependentReferenceOutcomeState.DATA_MISSING: DiscoveryReferenceMatchState.DISCOVERY_NOT_AUDITABLE,
        IndependentReferenceOutcomeState.NON_COMPARABLE: DiscoveryReferenceMatchState.DISCOVERY_NOT_AUDITABLE,
    }.get(value.state)


def _funnel_match_state(*, discovery: WholeMarketDiscoveryBatch, funnel: DiscoveryFunnelId, deadline: datetime,
                        leads: tuple[CanonicalDiscoveryLead, ...], evaluations: tuple[PerSecurityDiscoveryEvaluation, ...]) -> DiscoveryReferenceMatchState:
    valid = tuple(item for item in leads if _posture(item.readiness) is not DiscoveryPosture.PARTIAL_DISCOVERY_EVIDENCE)
    if valid and discovery.as_of <= deadline:
        return DiscoveryReferenceMatchState.TIMELY_DISCOVERY_MATCH
    if valid:
        return DiscoveryReferenceMatchState.LATE_DISCOVERY_MATCH
    if leads:
        return DiscoveryReferenceMatchState.DISCOVERY_NOT_AUDITABLE
    if any(item.state is PerSecurityDiscoveryState.EVALUATED_NO_TRIGGER for item in evaluations):
        return DiscoveryReferenceMatchState.NO_DISCOVERY_MATCH
    if any(item.state is PerSecurityDiscoveryState.IDENTITY_BLOCKED for item in evaluations):
        return DiscoveryReferenceMatchState.IDENTITY_CONFLICTED
    if any(item.state is PerSecurityDiscoveryState.DATA_BLOCKED for item in evaluations):
        return DiscoveryReferenceMatchState.DISCOVERY_NOT_AUDITABLE
    if any(item.state is PerSecurityDiscoveryState.NOT_EVALUATED for item in evaluations):
        return DiscoveryReferenceMatchState.FUNNEL_NOT_EVALUATED
    execution = next(item for item in discovery.executions if item.original.funnel_id is funnel)
    if execution.state is DiscoveryExecutionState.NOT_EXECUTABLE:
        return DiscoveryReferenceMatchState.FUNNEL_NOT_CAPABLE
    if execution.state is not DiscoveryExecutionState.EVALUATED:
        return DiscoveryReferenceMatchState.FUNNEL_NOT_EVALUATED
    return DiscoveryReferenceMatchState.PER_SECURITY_EVALUATION_UNKNOWN


def _eligibility(values: tuple[ReferenceFunnelEligibility, ...], horizon: ReferenceOpportunityHorizon) -> tuple[ReferenceFunnelEligibility, ...]:
    if not isinstance(values, tuple) or not values or any(not isinstance(item, ReferenceFunnelEligibility) for item in values):
        raise DiscoveryRecallReferenceError("DISCOVERY_RECALL_REFERENCE_FUNNEL_ELIGIBILITY_REQUIRED")
    result = tuple(sorted((item for item in values if item.horizon is horizon), key=lambda item: item.funnel_id.value))
    if not result or not any(item.relevance is ReferenceFunnelRelevance.RELEVANT for item in result) or len({item.funnel_id for item in result}) != len(result):
        raise DiscoveryRecallReferenceError("DISCOVERY_RECALL_REFERENCE_FUNNEL_ELIGIBILITY_AMBIGUOUS")
    return result


def _evaluations(values: tuple[PerSecurityDiscoveryEvaluation, ...], discovery: WholeMarketDiscoveryBatch, instrument: str) -> tuple[PerSecurityDiscoveryEvaluation, ...]:
    if not isinstance(values, tuple) or any(not isinstance(item, PerSecurityDiscoveryEvaluation) for item in values):
        raise DiscoveryRecallReferenceError("DISCOVERY_RECALL_PER_SECURITY_EVALUATIONS_INVALID")
    result = tuple(sorted((item for item in values if item.canonical_instrument_id == instrument), key=lambda item: item.funnel_id.value))
    if any(item.discovery_batch_id != discovery.batch_id or item.discovery_batch_fingerprint != discovery.fingerprint for item in result):
        raise DiscoveryRecallReferenceError("DISCOVERY_RECALL_PER_SECURITY_BATCH_BINDING_INVALID")
    if any(item.evidence.known_at > discovery.as_of for item in result):
        raise DiscoveryRecallReferenceError("DISCOVERY_RECALL_PER_SECURITY_EVIDENCE_LOOKAHEAD_INVALID")
    if len({item.funnel_id for item in result}) != len(result):
        raise DiscoveryRecallReferenceError("DISCOVERY_RECALL_PER_SECURITY_EVALUATION_AMBIGUOUS")
    return result


def _posture(value: DiscoveryLeadReadiness) -> DiscoveryPosture:
    return {
        DiscoveryLeadReadiness.READY_FOR_INSPECTION: DiscoveryPosture.OPERATIONAL_DISCOVERY,
        DiscoveryLeadReadiness.RESEARCH_INSPECTION: DiscoveryPosture.RESEARCH_SHADOW_DISCOVERY,
        DiscoveryLeadReadiness.DATA_PARTIAL: DiscoveryPosture.PARTIAL_DISCOVERY_EVIDENCE,
    }[value]


def _family_matches_horizon(family: ReferenceMeasurementFamily, horizon: ReferenceOpportunityHorizon) -> None:
    expected = {
        ReferenceMeasurementFamily.SHORT_TERM_CATALYST: ReferenceOpportunityHorizon.SHORT_TERM,
        ReferenceMeasurementFamily.POSITIONAL_MARKET_PATH: ReferenceOpportunityHorizon.POSITIONAL,
        ReferenceMeasurementFamily.LONG_TERM_BUSINESS_PERSISTENCE: ReferenceOpportunityHorizon.LONG_TERM,
    }
    if expected[family] is not horizon:
        raise DiscoveryRecallReferenceError("DISCOVERY_RECALL_REFERENCE_FAMILY_HORIZON_MISMATCH")


def _specification_payload(value: ReferenceOpportunitySpecification) -> dict[str, object]:
    return {"contract": DISCOVERY_RECALL_REFERENCE_CONTRACT, "id": value.specification_id, "version": value.version,
        "horizon": value.horizon.value, "family": value.measurement_family.value, "universe": value.historical_universe_id,
        "universe_fingerprint": value.historical_universe_fingerprint, "effective_at": _time(value.effective_at), "observation": value.observation_semantics_id,
        "deadline": value.discovery_deadline_semantics_id, "outcome_horizon": value.outcome_horizon_semantics_id,
        "inputs": tuple(item.value for item in value.required_inputs), "parameters": tuple(_parameter(item) for item in value.parameters),
        "exclusions": value.exclusion_ids, "policy": value.policy_status.value, "provenance": tuple(_evidence_payload(item) for item in value.provenance)}


def _outcome_identity(value: IndependentReferenceOutcome) -> dict[str, object]:
    return {"contract": DISCOVERY_RECALL_REFERENCE_CONTRACT, "specification": value.specification.specification_id,
        "specification_version": value.specification.version, "specification_fingerprint": value.specification.fingerprint,
        "instrument": value.canonical_instrument_id, "universe": value.specification.historical_universe_id,
        "observation_at": _time(value.observation_at), "deadline": _time(value.discovery_deadline), "end": _time(value.outcome_horizon_end)}


def _outcome_payload(value: IndependentReferenceOutcome) -> dict[str, object]:
    return _outcome_identity(value) | {"outcome_id": value.outcome_id, "onset": None if value.opportunity_onset is None else _time(value.opportunity_onset),
        "maturity": value.maturity.value, "state": value.state.value, "membership": None if value.historical_universe_membership is None else _evidence_payload(value.historical_universe_membership),
        "evidence": tuple(_evidence_payload(item) for item in value.evidence), "reasons": value.reason_codes}


def _match_identity(value: ReferenceDiscoveryMatch) -> dict[str, object]:
    return {"contract": DISCOVERY_RECALL_MATCHING_CONTRACT, "outcome": value.reference_outcome_id,
        "outcome_fingerprint": value.reference_outcome_fingerprint, "batch": value.discovery_batch_id,
        "batch_fingerprint": value.discovery_batch_fingerprint, "instrument": value.canonical_instrument_id,
        "horizon": value.horizon.value}


def _match_payload(value: ReferenceDiscoveryMatch) -> dict[str, object]:
    return _match_identity(value) | {"match_id": value.match_id, "system_state": value.system_state.value,
        "matching_leads": value.matching_lead_ids, "timely_leads": value.timely_lead_ids, "late_leads": value.late_lead_ids,
        "funnels": tuple(item.value for item in value.matching_funnels), "postures": tuple(item.value for item in value.postures),
        "coverage": tuple((item[0].value, item[1].value) for item in value.relevant_funnel_coverage), "audit_readiness": value.audit_readiness.value}


def _parameter(value: ReferenceParameter) -> dict[str, object]:
    return {"id": value.parameter_id, "state": value.state.value, "value": value.frozen_value}


def _evidence_payload(value: ReferenceEvidence) -> dict[str, object]:
    return {"id": value.evidence_id, "fingerprint": value.fingerprint, "known_at": _time(value.known_at), "requirement": value.requirement.value}


def _evidence_tuple(values: tuple[ReferenceEvidence, ...]) -> tuple[ReferenceEvidence, ...]:
    if not isinstance(values, tuple) or not values or any(not isinstance(item, ReferenceEvidence) for item in values):
        raise DiscoveryRecallReferenceError("DISCOVERY_RECALL_REFERENCE_EVIDENCE_REQUIRED")
    result = tuple(sorted(values, key=lambda item: (item.requirement.value, item.evidence_id, item.fingerprint, item.known_at)))
    if len({(item.requirement, item.evidence_id) for item in result}) != len(result):
        raise DiscoveryRecallReferenceError("DISCOVERY_RECALL_REFERENCE_EVIDENCE_CONFLICT")
    return result


def _parameters(values: tuple[ReferenceParameter, ...]) -> tuple[ReferenceParameter, ...]:
    if not isinstance(values, tuple) or any(not isinstance(item, ReferenceParameter) for item in values):
        raise DiscoveryRecallReferenceError("DISCOVERY_RECALL_REFERENCE_PARAMETERS_INVALID")
    result = tuple(sorted(values, key=lambda item: item.parameter_id))
    if len({item.parameter_id for item in result}) != len(result):
        raise DiscoveryRecallReferenceError("DISCOVERY_RECALL_REFERENCE_PARAMETER_CONFLICT")
    return result


def _enum_values(values: tuple[StrEnum, ...], kind: type[StrEnum], code: str, *, allow_empty: bool = False) -> tuple[StrEnum, ...]:
    if not isinstance(values, tuple) or (not allow_empty and not values) or any(not isinstance(item, kind) for item in values):
        raise DiscoveryRecallReferenceError(code)
    result = tuple(sorted(set(values), key=lambda item: item.value))
    if len(result) != len(values):
        raise DiscoveryRecallReferenceError(code)
    return result


def _ids(values: tuple[str, ...], code: str) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise DiscoveryRecallReferenceError(code)
    for value in values: _id(value, code)
    result = tuple(sorted(values))
    if len(set(result)) != len(result):
        raise DiscoveryRecallReferenceError(code)
    return result


def _verify(value: object, code: str) -> None:
    rebuilt = type(value)(**{name: getattr(value, name) for name in value.__dataclass_fields__ if name not in {"fingerprint", "outcome_id", "match_id"}})
    if rebuilt != value:
        raise DiscoveryRecallReferenceError(code)


def _id(value: str | None, code: str) -> None:
    if not isinstance(value, str) or not _ID.fullmatch(value): raise DiscoveryRecallReferenceError(code)


def _fp(value: str | None, code: str) -> None:
    if not isinstance(value, str) or not _FP.fullmatch(value): raise DiscoveryRecallReferenceError(code)


def _text(value: str | None, code: str) -> None:
    if not isinstance(value, str) or not value.strip() or value != value.strip(): raise DiscoveryRecallReferenceError(code)


def _utc(value: datetime, code: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None: raise DiscoveryRecallReferenceError(code)
    return value.astimezone(UTC)


def _time(value: datetime) -> str: return _utc(value, "DISCOVERY_RECALL_REFERENCE_TIME_INVALID").isoformat()


__all__ = (
    "DISCOVERY_RECALL_MATCHING_CONTRACT", "DISCOVERY_RECALL_REFERENCE_CONTRACT", "DiscoveryPosture", "DiscoveryRecallReferenceError",
    "DiscoveryReferenceMatchState", "IndependentReferenceOutcome", "IndependentReferenceOutcomeState", "PerSecurityDiscoveryEvaluation",
    "PerSecurityDiscoveryState", "ReferenceEvidence", "ReferenceFunnelEligibility", "ReferenceFunnelRelevance", "ReferenceMeasurementFamily",
    "ReferenceOpportunityHorizon", "ReferenceOpportunitySpecification", "ReferenceOutcomeMaturity", "ReferenceParameter", "ReferenceParameterState",
    "ReferencePolicyStatus", "ReferenceInputRequirement", "ReferenceDiscoveryMatch", "match_reference_outcome", "serialize_reference",
)
