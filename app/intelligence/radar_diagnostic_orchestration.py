"""Read-only handoff from canonical discovery leads to the canonical 61 rules.

This module is intentionally an orchestration boundary, not a diagnostic
engine.  It validates an immutable ``CanonicalDiscoveryLead``, requests an
already-assembled canonical evidence view through dependency injection, and
delegates every rule to ``Canonical61DiagnosticRunner``.  It neither fetches
data nor persists a receipt, scores a security, constructs a setup, or reaches
an execution/portfolio boundary.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
import json
import re
from typing import Protocol

from app.diagnostics.models import EvaluatedDiagnostic, EvaluationEligibility
from app.historical.guard import manifest_fingerprint
from app.intelligence.multi_funnel_discovery import (
    CanonicalDiscoveryLead,
    DiscoveryFunnelId,
    DiscoveryFunnelStatus,
    DiscoveryHorizon,
    multi_funnel_discovery_registry,
)
from app.registry.canonical import DIAGNOSTIC_REGISTRY_VERSION, DIAGNOSTIC_RULES
from app.universe_analysis.service import AssembledStockEvidence, Canonical61DiagnosticRunner
from app.universe_analysis.technical_diagnostic_input import (
    CurrentDescriptiveTechnicalState,
    StrictHistoricalPitTechnicalState,
)


RADAR_DIAGNOSTIC_ORCHESTRATION_CONTRACT = "radar-to-hsi-diagnostic-orchestration/v1"
RADAR_DIAGNOSTIC_ORCHESTRATION_POLICY_ID = "radar-to-hsi-diagnostic-orchestration-policy"
RADAR_DIAGNOSTIC_ORCHESTRATION_POLICY_VERSION = "v1"
RADAR_DIAGNOSTIC_ORCHESTRATION_POLICY_FINGERPRINT = (
    "sha256:f1f20cd8c72ce0b8dfcee5b5290710f2a0efec2d3bbf8abf9c39c2c446345eb2"
)
RADAR_DIAGNOSTIC_BATCH_LIMIT = 100

_NSE_SECURITY = re.compile(r"NSE:[A-Z]{2}[A-Z0-9]{9}[0-9]\Z")
_REFERENCE = re.compile(r"[A-Za-z0-9._:|+\-]+\Z")
_FINGERPRINT = re.compile(r"(?:sha256:)?[0-9a-f]{64}\Z")


class RadarDiagnosticOrchestrationError(ValueError):
    """Stable fail-closed error for a malformed immutable orchestration value."""


class RadarDiagnosticAuthority(StrEnum):
    RESEARCH = "RESEARCH"


class RadarDiagnosticActionability(StrEnum):
    WATCH_ONLY = "WATCH_ONLY"


class RadarDiagnosticExecutionStatus(StrEnum):
    NON_EXECUTABLE = "NON_EXECUTABLE"


class CanonicalDiagnosticHorizon(StrEnum):
    SHORT_TERM = "SHORT_TERM"
    POSITIONAL = "POSITIONAL"
    LONG_TERM = "LONG_TERM"


class RadarDiagnosticEvaluationState(StrEnum):
    ACCEPTED = "ACCEPTED"
    REJECTED_INVALID_LEAD = "REJECTED_INVALID_LEAD"
    REJECTED_CONFLICTED_LEAD = "REJECTED_CONFLICTED_LEAD"
    REJECTED_UNSUPPORTED_FAMILY = "REJECTED_UNSUPPORTED_FAMILY"
    REJECTED_HORIZON_CONTEXT = "REJECTED_HORIZON_CONTEXT"
    REJECTED_FUTURE_EVIDENCE = "REJECTED_FUTURE_EVIDENCE"
    REJECTED_EVIDENCE_INVALID = "REJECTED_EVIDENCE_INVALID"


class CanonicalRuleReadinessState(StrEnum):
    EVALUATED = "EVALUATED"
    PARTIAL = "PARTIAL"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    EVIDENCE_CONFLICTED = "EVIDENCE_CONFLICTED"
    POLICY_BLOCKED = "POLICY_BLOCKED"
    SOURCE_NOT_READY = "SOURCE_NOT_READY"


class RuleHorizonApplicabilityState(StrEnum):
    """Runtime applicability is deliberately unset until the candidate activates."""

    POLICY_UNSET = "POLICY_UNSET"


class TemporalReadinessState(StrEnum):
    PROSPECTIVE_PIT_READY = "PROSPECTIVE_PIT_READY"
    CURRENT_DESCRIPTIVE = "CURRENT_DESCRIPTIVE"
    HISTORICAL_PIT_NOT_READY = "HISTORICAL_PIT_NOT_READY"
    TEMPORAL_EVIDENCE_UNAVAILABLE = "TEMPORAL_EVIDENCE_UNAVAILABLE"


class RadarDiagnosticReason(StrEnum):
    DISCOVERY_LEAD_INVALID = "DISCOVERY_LEAD_INVALID"
    DISCOVERY_LEAD_CONFLICTED = "DISCOVERY_LEAD_CONFLICTED"
    DISCOVERY_FAMILY_UNSUPPORTED = "DISCOVERY_FAMILY_UNSUPPORTED"
    DISCOVERY_FAMILY_NOT_ACTIVE = "DISCOVERY_FAMILY_NOT_ACTIVE"
    DISCOVERY_HORIZON_NOT_GOVERNED = "DISCOVERY_HORIZON_NOT_GOVERNED"
    DISCOVERY_LINEAGE_AFTER_EVALUATION_AS_OF = "DISCOVERY_LINEAGE_AFTER_EVALUATION_AS_OF"
    CANONICAL_EVIDENCE_ASSEMBLY_FAILED = "CANONICAL_EVIDENCE_ASSEMBLY_FAILED"
    EVIDENCE_INSTRUMENT_MISMATCH = "EVIDENCE_INSTRUMENT_MISMATCH"
    EVIDENCE_AS_OF_MISMATCH = "EVIDENCE_AS_OF_MISMATCH"
    CANONICAL_TECHNICAL_INPUT_REQUIRED = "CANONICAL_TECHNICAL_INPUT_REQUIRED"
    CANONICAL_TECHNICAL_INPUT_INVALID = "CANONICAL_TECHNICAL_INPUT_INVALID"
    NAMED_VWAP_SEMANTICS_UNAVAILABLE = "NAMED_VWAP_SEMANTICS_UNAVAILABLE"
    AUTHORITATIVE_PEER_COHORT_UNAVAILABLE = "AUTHORITATIVE_PEER_COHORT_UNAVAILABLE"
    EVENT_SESSION_EVIDENCE_UNAVAILABLE = "EVENT_SESSION_EVIDENCE_UNAVAILABLE"
    INTRADAY_15M_EVIDENCE_UNAVAILABLE = "INTRADAY_15M_EVIDENCE_UNAVAILABLE"


class CanonicalRadarEvidenceAssembler(Protocol):
    """Existing evidence assembly supplied by a future read-only integration seam."""

    def assemble_for_radar(
        self, *, canonical_security_id: str, evaluation_as_of: datetime,
    ) -> AssembledStockEvidence: ...


@dataclass(frozen=True, slots=True)
class CanonicalDiagnosticRuleReference:
    """A reference to one existing canonical runner result; not a new result."""

    rule_id: int
    diagnostic_result_id: str
    diagnostic_result: str
    eligibility: EvaluationEligibility
    horizon_applicability: RuleHorizonApplicabilityState
    readiness: CanonicalRuleReadinessState
    reason_codes: tuple[RadarDiagnosticReason, ...]
    evidence_ids: tuple[str, ...]
    input_observation_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason_codes", _enum_tuple(self.reason_codes, RadarDiagnosticReason, "RADAR_DIAGNOSTIC_RULE_REASONS_INVALID"))
        object.__setattr__(self, "evidence_ids", _references(self.evidence_ids, "RADAR_DIAGNOSTIC_RULE_EVIDENCE_IDS_INVALID"))
        object.__setattr__(self, "input_observation_ids", _references(self.input_observation_ids, "RADAR_DIAGNOSTIC_RULE_INPUT_IDS_INVALID"))
        if (
            self.rule_id not in range(1, 62)
            or not _reference(self.diagnostic_result_id)
            or not isinstance(self.diagnostic_result, str)
            or not self.diagnostic_result
            or not isinstance(self.eligibility, EvaluationEligibility)
            or self.horizon_applicability is not RuleHorizonApplicabilityState.POLICY_UNSET
            or not isinstance(self.readiness, CanonicalRuleReadinessState)
            or (self.readiness is CanonicalRuleReadinessState.EVALUATED and self.reason_codes)
        ):
            raise RadarDiagnosticOrchestrationError("RADAR_DIAGNOSTIC_RULE_REFERENCE_INVALID")


@dataclass(frozen=True, slots=True)
class RadarDiagnosticReceipt:
    """Immutable read-only trace from one Discovery Lead to all canonical rules."""

    canonical_security_id: str
    source_discovery_lead_id: str
    source_discovery_lead_fingerprint: str
    source_discovery_family: DiscoveryFunnelId
    evaluation_as_of: datetime
    canonical_horizon: CanonicalDiagnosticHorizon
    evidence_input_fingerprint: str
    technical_temporal_readiness: TemporalReadinessState
    rule_references: tuple[CanonicalDiagnosticRuleReference, ...]
    registry_version: str = DIAGNOSTIC_REGISTRY_VERSION
    registry_fingerprint: str = field(init=False)
    authority: RadarDiagnosticAuthority = RadarDiagnosticAuthority.RESEARCH
    actionability: RadarDiagnosticActionability = RadarDiagnosticActionability.WATCH_ONLY
    execution_status: RadarDiagnosticExecutionStatus = RadarDiagnosticExecutionStatus.NON_EXECUTABLE
    policy_id: str = RADAR_DIAGNOSTIC_ORCHESTRATION_POLICY_ID
    policy_version: str = RADAR_DIAGNOSTIC_ORCHESTRATION_POLICY_VERSION
    policy_fingerprint: str = RADAR_DIAGNOSTIC_ORCHESTRATION_POLICY_FINGERPRINT
    receipt_id: str = field(init=False)
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "evaluation_as_of", _utc(self.evaluation_as_of, "RADAR_DIAGNOSTIC_EVALUATION_AS_OF_INVALID"))
        object.__setattr__(self, "rule_references", tuple(sorted(self.rule_references, key=lambda item: item.rule_id)))
        expected = tuple(range(1, 62))
        if (
            not _security(self.canonical_security_id)
            or not _reference(self.source_discovery_lead_id)
            or not _fingerprint(self.source_discovery_lead_fingerprint)
            or not isinstance(self.source_discovery_family, DiscoveryFunnelId)
            or not isinstance(self.canonical_horizon, CanonicalDiagnosticHorizon)
            or not _fingerprint(self.evidence_input_fingerprint)
            or not isinstance(self.technical_temporal_readiness, TemporalReadinessState)
            or tuple(item.rule_id for item in self.rule_references) != expected
            or self.registry_version != DIAGNOSTIC_REGISTRY_VERSION
            or self.authority is not RadarDiagnosticAuthority.RESEARCH
            or self.actionability is not RadarDiagnosticActionability.WATCH_ONLY
            or self.execution_status is not RadarDiagnosticExecutionStatus.NON_EXECUTABLE
            or self.policy_id != RADAR_DIAGNOSTIC_ORCHESTRATION_POLICY_ID
            or self.policy_version != RADAR_DIAGNOSTIC_ORCHESTRATION_POLICY_VERSION
            or self.policy_fingerprint != RADAR_DIAGNOSTIC_ORCHESTRATION_POLICY_FINGERPRINT
        ):
            raise RadarDiagnosticOrchestrationError("RADAR_DIAGNOSTIC_RECEIPT_INVALID")
        registry_fingerprint = manifest_fingerprint(
            registry_version=DIAGNOSTIC_REGISTRY_VERSION,
            rule_ids=tuple(item.rule_id for item in DIAGNOSTIC_RULES),
        )
        object.__setattr__(self, "registry_fingerprint", registry_fingerprint)
        object.__setattr__(self, "receipt_id", "radar-diagnostic:" + manifest_fingerprint(**_receipt_identity(self))[:32])
        object.__setattr__(self, "fingerprint", manifest_fingerprint(**_receipt_payload(self)))

    def verify(self) -> None:
        if replace(self) != self:
            raise RadarDiagnosticOrchestrationError("RADAR_DIAGNOSTIC_RECEIPT_TAMPERED")

    @property
    def evaluated_rule_count(self) -> int:
        return sum(item.readiness is CanonicalRuleReadinessState.EVALUATED for item in self.rule_references)


@dataclass(frozen=True, slots=True)
class RadarDiagnosticEvaluation:
    state: RadarDiagnosticEvaluationState
    reason_codes: tuple[RadarDiagnosticReason, ...]
    receipt: RadarDiagnosticReceipt | None
    source_lead_id: str | None
    source_lead_fingerprint: str | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason_codes", _enum_tuple(self.reason_codes, RadarDiagnosticReason, "RADAR_DIAGNOSTIC_EVALUATION_REASONS_INVALID"))
        accepted = self.state is RadarDiagnosticEvaluationState.ACCEPTED
        if (
            not isinstance(self.state, RadarDiagnosticEvaluationState)
            or accepted != (self.receipt is not None)
            or (accepted and self.reason_codes)
            or (not accepted and (not self.reason_codes or self.receipt is not None))
            or (self.source_lead_id is not None and not _reference(self.source_lead_id))
            or (self.source_lead_fingerprint is not None and not _fingerprint(self.source_lead_fingerprint))
        ):
            raise RadarDiagnosticOrchestrationError("RADAR_DIAGNOSTIC_EVALUATION_INVALID")


@dataclass(frozen=True, slots=True)
class RadarDiagnosticBatch:
    """Bounded immutable audit only; it is neither a queue nor persistence."""

    evaluation_as_of: datetime
    canonical_horizon: CanonicalDiagnosticHorizon
    evaluations: tuple[RadarDiagnosticEvaluation, ...]
    input_lead_count: int
    deduplicated_count: int
    batch_id: str = field(init=False)
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "evaluation_as_of", _utc(self.evaluation_as_of, "RADAR_DIAGNOSTIC_BATCH_AS_OF_INVALID"))
        object.__setattr__(self, "evaluations", tuple(sorted(self.evaluations, key=_evaluation_sort_key)))
        if (
            not isinstance(self.canonical_horizon, CanonicalDiagnosticHorizon)
            or not isinstance(self.input_lead_count, int) or self.input_lead_count < 0
            or not isinstance(self.deduplicated_count, int) or self.deduplicated_count < 0
            or self.input_lead_count > RADAR_DIAGNOSTIC_BATCH_LIMIT
            or self.deduplicated_count > self.input_lead_count
            or len({(item.source_lead_id, item.source_lead_fingerprint) for item in self.evaluations if item.source_lead_id is not None}) != len(
                tuple(item for item in self.evaluations if item.source_lead_id is not None)
            )
        ):
            raise RadarDiagnosticOrchestrationError("RADAR_DIAGNOSTIC_BATCH_INVALID")
        object.__setattr__(self, "batch_id", "radar-diagnostic-batch:" + manifest_fingerprint(**_batch_identity(self))[:32])
        object.__setattr__(self, "fingerprint", manifest_fingerprint(**_batch_payload(self)))

    @property
    def accepted_count(self) -> int:
        return sum(item.state is RadarDiagnosticEvaluationState.ACCEPTED for item in self.evaluations)

    @property
    def rejected_count(self) -> int:
        return len(self.evaluations) - self.accepted_count

    @property
    def evaluated_security_count(self) -> int:
        return len({item.receipt.canonical_security_id for item in self.evaluations if item.receipt is not None})

    @property
    def rule_receipt_count(self) -> int:
        return sum(len(item.receipt.rule_references) for item in self.evaluations if item.receipt is not None)

    @property
    def rule_readiness_distribution(self) -> tuple[tuple[CanonicalRuleReadinessState, int], ...]:
        """Stable audit counts across accepted receipts, never a score."""
        counts = {state: 0 for state in CanonicalRuleReadinessState}
        for evaluation in self.evaluations:
            if evaluation.receipt is not None:
                for rule in evaluation.receipt.rule_references:
                    counts[rule.readiness] += 1
        return tuple((state, counts[state]) for state in CanonicalRuleReadinessState)

    @property
    def data_insufficient_count(self) -> int:
        return dict(self.rule_readiness_distribution)[CanonicalRuleReadinessState.INSUFFICIENT_DATA]

    @property
    def conflicted_count(self) -> int:
        return (
            dict(self.rule_readiness_distribution)[CanonicalRuleReadinessState.EVIDENCE_CONFLICTED]
            + sum(item.state is RadarDiagnosticEvaluationState.REJECTED_CONFLICTED_LEAD for item in self.evaluations)
        )

    @property
    def horizon_distribution(self) -> tuple[tuple[CanonicalDiagnosticHorizon, int], ...]:
        return ((self.canonical_horizon, self.accepted_count),)


class RadarToHsiDiagnosticOrchestrator:
    """Run qualified Discovery Leads through the existing canonical 61 runner."""

    def __init__(self, *, evidence_assembler: CanonicalRadarEvidenceAssembler,
                 runner: Canonical61DiagnosticRunner, batch_limit: int = RADAR_DIAGNOSTIC_BATCH_LIMIT) -> None:
        if not 1 <= batch_limit <= RADAR_DIAGNOSTIC_BATCH_LIMIT:
            raise RadarDiagnosticOrchestrationError("RADAR_DIAGNOSTIC_BATCH_LIMIT_INVALID")
        self._evidence_assembler = evidence_assembler
        self._runner = runner
        self._batch_limit = batch_limit

    def evaluate_one_lead(
        self, lead: CanonicalDiscoveryLead, *, evaluation_as_of: datetime,
        canonical_horizon: CanonicalDiagnosticHorizon,
    ) -> RadarDiagnosticEvaluation:
        cutoff = _utc(evaluation_as_of, "RADAR_DIAGNOSTIC_EVALUATION_AS_OF_INVALID")
        identity = _lead_identity_or_none(lead)
        try:
            _validate_lead_for_evaluation(lead, cutoff, canonical_horizon)
        except _LeadFailure as failure:
            return RadarDiagnosticEvaluation(failure.state, (failure.reason,), None, *identity)
        try:
            evidence = self._evidence_assembler.assemble_for_radar(
                canonical_security_id=lead.canonical_instrument_id, evaluation_as_of=cutoff,
            )
        except Exception:
            return RadarDiagnosticEvaluation(
                RadarDiagnosticEvaluationState.REJECTED_EVIDENCE_INVALID,
                (RadarDiagnosticReason.CANONICAL_EVIDENCE_ASSEMBLY_FAILED,), None, *identity,
            )
        try:
            _validate_evidence(evidence, lead, cutoff)
            diagnostic_run = self._runner.run(evidence)
            references = tuple(_rule_reference(value, evidence) for value in diagnostic_run.evaluations)
            receipt = RadarDiagnosticReceipt(
                lead.canonical_instrument_id, lead.lead_id, lead.fingerprint, lead.funnel_id,
                cutoff, canonical_horizon, _evidence_fingerprint(evidence),
                _technical_temporal_readiness(evidence), references,
            )
        except RadarDiagnosticOrchestrationError as error:
            reason = {
                "EVIDENCE_INSTRUMENT_MISMATCH": RadarDiagnosticReason.EVIDENCE_INSTRUMENT_MISMATCH,
                "EVIDENCE_AS_OF_MISMATCH": RadarDiagnosticReason.EVIDENCE_AS_OF_MISMATCH,
                "CANONICAL_TECHNICAL_INPUT_REQUIRED": RadarDiagnosticReason.CANONICAL_TECHNICAL_INPUT_REQUIRED,
                "NAMED_VWAP_SEMANTICS_UNAVAILABLE": RadarDiagnosticReason.NAMED_VWAP_SEMANTICS_UNAVAILABLE,
            }.get(str(error), RadarDiagnosticReason.CANONICAL_TECHNICAL_INPUT_INVALID)
            return RadarDiagnosticEvaluation(
                RadarDiagnosticEvaluationState.REJECTED_EVIDENCE_INVALID,
                (reason,), None, *identity,
            )
        except Exception:
            return RadarDiagnosticEvaluation(
                RadarDiagnosticEvaluationState.REJECTED_EVIDENCE_INVALID,
                (RadarDiagnosticReason.CANONICAL_TECHNICAL_INPUT_INVALID,), None, *identity,
            )
        return RadarDiagnosticEvaluation(RadarDiagnosticEvaluationState.ACCEPTED, (), receipt, *identity)

    def evaluate_leads(
        self, leads: tuple[CanonicalDiscoveryLead, ...], *, evaluation_as_of: datetime,
        canonical_horizon: CanonicalDiagnosticHorizon,
    ) -> RadarDiagnosticBatch:
        if len(leads) > self._batch_limit:
            raise RadarDiagnosticOrchestrationError("RADAR_DIAGNOSTIC_BATCH_BOUND_EXCEEDED")
        cutoff = _utc(evaluation_as_of, "RADAR_DIAGNOSTIC_EVALUATION_AS_OF_INVALID")
        unique: dict[str, CanonicalDiscoveryLead] = {}
        conflicts: set[str] = set()
        invalid: list[RadarDiagnosticEvaluation] = []
        deduplicated = 0
        for lead in leads:
            identity = _lead_identity_or_none(lead)
            try:
                lead.verify()
            except Exception:
                invalid.append(RadarDiagnosticEvaluation(
                    RadarDiagnosticEvaluationState.REJECTED_INVALID_LEAD,
                    (RadarDiagnosticReason.DISCOVERY_LEAD_INVALID,), None, *identity,
                ))
                continue
            current = unique.get(lead.lead_id)
            if current is None:
                unique[lead.lead_id] = lead
            elif current.fingerprint == lead.fingerprint:
                deduplicated += 1
            else:
                conflicts.add(lead.lead_id)
        outcomes = list(invalid)
        for lead_id in sorted(conflicts):
            value = unique.pop(lead_id)
            outcomes.append(RadarDiagnosticEvaluation(
                RadarDiagnosticEvaluationState.REJECTED_CONFLICTED_LEAD,
                (RadarDiagnosticReason.DISCOVERY_LEAD_CONFLICTED,), None, value.lead_id, value.fingerprint,
            ))
        outcomes.extend(
            self.evaluate_one_lead(lead, evaluation_as_of=cutoff, canonical_horizon=canonical_horizon)
            for _, lead in sorted(unique.items())
        )
        return RadarDiagnosticBatch(cutoff, canonical_horizon, tuple(outcomes), len(leads), deduplicated)


@dataclass(frozen=True, slots=True)
class _LeadFailure(Exception):
    state: RadarDiagnosticEvaluationState
    reason: RadarDiagnosticReason


def radar_diagnostic_receipt_payload(value: RadarDiagnosticReceipt) -> dict[str, object]:
    value.verify()
    return _receipt_payload(value) | {"receipt_id": value.receipt_id, "fingerprint": value.fingerprint}


def serialize_radar_diagnostic_receipt(value: RadarDiagnosticReceipt) -> str:
    return json.dumps(radar_diagnostic_receipt_payload(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _validate_lead_for_evaluation(lead: CanonicalDiscoveryLead, cutoff: datetime, horizon: CanonicalDiagnosticHorizon) -> None:
    try:
        lead.verify()
    except Exception as error:
        raise _LeadFailure(RadarDiagnosticEvaluationState.REJECTED_INVALID_LEAD, RadarDiagnosticReason.DISCOVERY_LEAD_INVALID) from error
    if not _security(lead.canonical_instrument_id):
        raise _LeadFailure(RadarDiagnosticEvaluationState.REJECTED_INVALID_LEAD, RadarDiagnosticReason.DISCOVERY_LEAD_INVALID)
    try:
        entry = multi_funnel_discovery_registry().get(lead.funnel_id)
    except Exception as error:
        raise _LeadFailure(RadarDiagnosticEvaluationState.REJECTED_UNSUPPORTED_FAMILY, RadarDiagnosticReason.DISCOVERY_FAMILY_UNSUPPORTED) from error
    if entry.status is not DiscoveryFunnelStatus.OPERATIONAL or entry.version != lead.funnel_version:
        raise _LeadFailure(RadarDiagnosticEvaluationState.REJECTED_UNSUPPORTED_FAMILY, RadarDiagnosticReason.DISCOVERY_FAMILY_NOT_ACTIVE)
    if lead.discovery_as_of > cutoff or any(item.known_at > cutoff for item in lead.lineage):
        raise _LeadFailure(RadarDiagnosticEvaluationState.REJECTED_FUTURE_EVIDENCE, RadarDiagnosticReason.DISCOVERY_LINEAGE_AFTER_EVALUATION_AS_OF)
    governed = {_map_horizon(item) for item in lead.intended_horizons}
    if horizon not in governed:
        raise _LeadFailure(RadarDiagnosticEvaluationState.REJECTED_HORIZON_CONTEXT, RadarDiagnosticReason.DISCOVERY_HORIZON_NOT_GOVERNED)


def _validate_evidence(evidence: AssembledStockEvidence, lead: CanonicalDiscoveryLead, cutoff: datetime) -> None:
    if evidence.instrument_id != lead.canonical_instrument_id:
        raise RadarDiagnosticOrchestrationError("EVIDENCE_INSTRUMENT_MISMATCH")
    if _utc(evidence.as_of, "EVIDENCE_AS_OF_MISMATCH") != cutoff:
        raise RadarDiagnosticOrchestrationError("EVIDENCE_AS_OF_MISMATCH")
    if evidence.technical_input is None:
        raise RadarDiagnosticOrchestrationError("CANONICAL_TECHNICAL_INPUT_REQUIRED")
    evidence.technical_input.__post_init__()
    if (
        evidence.technical_input.canonical_instrument_id != lead.canonical_instrument_id
        or _utc(evidence.technical_input.as_of, "CANONICAL_TECHNICAL_INPUT_INVALID") != cutoff
        or evidence.technical_input.current_descriptive_state is not CurrentDescriptiveTechnicalState.READY
        or evidence.technical_input.strict_historical_pit_state is not StrictHistoricalPitTechnicalState.NOT_READY
    ):
        raise RadarDiagnosticOrchestrationError("CANONICAL_TECHNICAL_INPUT_INVALID")


def _rule_reference(value: EvaluatedDiagnostic, evidence: AssembledStockEvidence) -> CanonicalDiagnosticRuleReference:
    record = value.record
    reasons: tuple[RadarDiagnosticReason, ...] = ()
    # These four states retain already-governed limitations independently of
    # the legacy evaluator's descriptive result.  They never repair a missing
    # diagnostic or make its inputs available.
    if value.canonical_rule_id == 6:
        readiness = CanonicalRuleReadinessState.PARTIAL
        reasons = (RadarDiagnosticReason.AUTHORITATIVE_PEER_COHORT_UNAVAILABLE,)
    elif value.canonical_rule_id == 35:
        readiness = CanonicalRuleReadinessState.SOURCE_NOT_READY
        reasons = (RadarDiagnosticReason.NAMED_VWAP_SEMANTICS_UNAVAILABLE,)
    elif value.canonical_rule_id == 57:
        readiness = CanonicalRuleReadinessState.SOURCE_NOT_READY
        reasons = (RadarDiagnosticReason.EVENT_SESSION_EVIDENCE_UNAVAILABLE,)
    elif value.canonical_rule_id == 14:
        readiness = CanonicalRuleReadinessState.PARTIAL
        reasons = (RadarDiagnosticReason.INTRADAY_15M_EVIDENCE_UNAVAILABLE,)
    elif record.result == "EVIDENCE_CONFLICTED":
        readiness = CanonicalRuleReadinessState.EVIDENCE_CONFLICTED
    elif record.result == "POLICY_BLOCKED":
        readiness = CanonicalRuleReadinessState.POLICY_BLOCKED
    elif record.result == "SOURCE_NOT_READY":
        readiness = CanonicalRuleReadinessState.SOURCE_NOT_READY
    elif record.result == "NOT_APPLICABLE":
        readiness = CanonicalRuleReadinessState.NOT_APPLICABLE
    elif value.eligibility is not EvaluationEligibility.ELIGIBLE:
        readiness = CanonicalRuleReadinessState.INSUFFICIENT_DATA
    else:
        readiness = CanonicalRuleReadinessState.EVALUATED
    if value.canonical_rule_id == 35 and record.result != "INSUFFICIENT_DATA":
        raise RadarDiagnosticOrchestrationError("NAMED_VWAP_SEMANTICS_UNAVAILABLE")
    return CanonicalDiagnosticRuleReference(
        value.canonical_rule_id, record.id, record.result, value.eligibility,
        RuleHorizonApplicabilityState.POLICY_UNSET, readiness, reasons,
        record.evidence_ids, record.input_observation_ids,
    )


def _technical_temporal_readiness(evidence: AssembledStockEvidence) -> TemporalReadinessState:
    if evidence.technical_input is None:
        return TemporalReadinessState.TEMPORAL_EVIDENCE_UNAVAILABLE
    if evidence.technical_input.strict_historical_pit_state is StrictHistoricalPitTechnicalState.NOT_READY:
        return TemporalReadinessState.CURRENT_DESCRIPTIVE
    return TemporalReadinessState.HISTORICAL_PIT_NOT_READY


def _evidence_fingerprint(value: AssembledStockEvidence) -> str:
    return "sha256:" + manifest_fingerprint(
        snapshot_id=value.snapshot.id,
        snapshot_observation_ids=tuple(item.id for item in value.snapshot.observations),
        technical_input_fingerprint=None if value.technical_input is None else value.technical_input.fingerprint,
        benchmark_sector_input_fingerprint=None if value.benchmark_sector_input is None else value.benchmark_sector_input.fingerprint,
        research_as_of=value.research.as_of_timestamp,
        crowd_as_of=value.crowd.as_of_timestamp,
    )


def _receipt_identity(value: RadarDiagnosticReceipt) -> dict[str, object]:
    return {
        "contract": RADAR_DIAGNOSTIC_ORCHESTRATION_CONTRACT,
        "security": value.canonical_security_id,
        "lead_id": value.source_discovery_lead_id,
        "lead_fingerprint": value.source_discovery_lead_fingerprint,
        "family": value.source_discovery_family.value,
        "as_of": value.evaluation_as_of.isoformat(),
        "horizon": value.canonical_horizon.value,
        "evidence": value.evidence_input_fingerprint,
        "registry": value.registry_version,
        "policy": value.policy_fingerprint,
    }


def _receipt_payload(value: RadarDiagnosticReceipt) -> dict[str, object]:
    return _receipt_identity(value) | {
        "registry_fingerprint": value.registry_fingerprint,
        "technical_temporal_readiness": value.technical_temporal_readiness.value,
        "authority": value.authority.value,
        "actionability": value.actionability.value,
        "execution_status": value.execution_status.value,
        "policy_id": value.policy_id,
        "policy_version": value.policy_version,
        "rules": tuple({
            "rule_id": item.rule_id,
            "diagnostic_result_id": item.diagnostic_result_id,
            "diagnostic_result": item.diagnostic_result,
            "eligibility": item.eligibility.value,
            "horizon_applicability": item.horizon_applicability.value,
            "readiness": item.readiness.value,
            "reason_codes": tuple(reason.value for reason in item.reason_codes),
            "evidence_ids": item.evidence_ids,
            "input_observation_ids": item.input_observation_ids,
        } for item in value.rule_references),
    }


def _batch_identity(value: RadarDiagnosticBatch) -> dict[str, object]:
    return {
        "contract": RADAR_DIAGNOSTIC_ORCHESTRATION_CONTRACT,
        "as_of": value.evaluation_as_of.isoformat(),
        "horizon": value.canonical_horizon.value,
        "evaluations": tuple(
            (item.state.value, item.source_lead_id, item.source_lead_fingerprint,
             None if item.receipt is None else item.receipt.receipt_id)
            for item in value.evaluations
        ),
    }


def _batch_payload(value: RadarDiagnosticBatch) -> dict[str, object]:
    return _batch_identity(value) | {
        "input_lead_count": value.input_lead_count,
        "deduplicated_count": value.deduplicated_count,
        "accepted_count": value.accepted_count,
        "rejected_count": value.rejected_count,
    }


def _map_horizon(value: DiscoveryHorizon) -> CanonicalDiagnosticHorizon:
    if value is DiscoveryHorizon.POSITIONAL:
        return CanonicalDiagnosticHorizon.POSITIONAL
    if value is DiscoveryHorizon.LONG_TERM:
        return CanonicalDiagnosticHorizon.LONG_TERM
    raise RadarDiagnosticOrchestrationError("DISCOVERY_HORIZON_NOT_GOVERNED")


def _lead_identity_or_none(value: object) -> tuple[str | None, str | None]:
    identifier = getattr(value, "lead_id", None)
    fingerprint = getattr(value, "fingerprint", None)
    return (identifier if isinstance(identifier, str) and _reference(identifier) else None,
            fingerprint if isinstance(fingerprint, str) and _fingerprint(fingerprint) else None)


def _evaluation_sort_key(value: RadarDiagnosticEvaluation) -> tuple[str, str, str]:
    return (value.source_lead_id or "", value.source_lead_fingerprint or "", value.state.value)


def _references(values: tuple[str, ...], error: str) -> tuple[str, ...]:
    # Existing diagnostic inputs retain chronological source ordering.  It is
    # deterministic lineage, not an unordered set to be silently resorted.
    result = tuple(values)
    if not all(_reference(item) for item in result):
        raise RadarDiagnosticOrchestrationError(error)
    return result


def _enum_tuple(values, expected, error: str):
    result = tuple(sorted(values, key=lambda item: item.value if isinstance(item, expected) else ""))
    if result != tuple(values) or len(result) != len(set(result)) or not all(isinstance(item, expected) for item in result):
        raise RadarDiagnosticOrchestrationError(error)
    return result


def _utc(value: datetime, error: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise RadarDiagnosticOrchestrationError(error)
    return value.astimezone(UTC)


def _security(value: object) -> bool:
    return isinstance(value, str) and bool(_NSE_SECURITY.fullmatch(value))


def _reference(value: object) -> bool:
    return isinstance(value, str) and bool(_REFERENCE.fullmatch(value))


def _fingerprint(value: object) -> bool:
    return isinstance(value, str) and bool(_FINGERPRINT.fullmatch(value))


__all__ = (
    "CanonicalDiagnosticHorizon", "CanonicalDiagnosticRuleReference", "CanonicalRadarEvidenceAssembler",
    "CanonicalRuleReadinessState", "RADAR_DIAGNOSTIC_BATCH_LIMIT", "RADAR_DIAGNOSTIC_ORCHESTRATION_CONTRACT",
    "RadarDiagnosticActionability", "RadarDiagnosticAuthority", "RadarDiagnosticBatch",
    "RadarDiagnosticEvaluation", "RadarDiagnosticEvaluationState", "RadarDiagnosticExecutionStatus",
    "RadarDiagnosticOrchestrationError", "RadarDiagnosticReason", "RadarDiagnosticReceipt",
    "RadarToHsiDiagnosticOrchestrator", "RuleHorizonApplicabilityState", "TemporalReadinessState", "radar_diagnostic_receipt_payload",
    "serialize_radar_diagnostic_receipt",
)
