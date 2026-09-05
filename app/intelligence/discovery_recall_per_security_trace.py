"""Immutable, read-only per-security Discovery Recall evaluation traces.

This boundary consumes a frozen whole-market discovery batch.  It preserves
exact positive lead lineage and compact funnel capability facts, but never
turns aggregate no-lead coverage into a per-security negative evaluation.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from app.historical.guard import manifest_fingerprint
from app.intelligence.discovery_recall_audit import UniverseMembershipState
from app.intelligence.discovery_recall_reference_matching import (
    PerSecurityDiscoveryEvaluation,
    PerSecurityDiscoveryState,
    ReferenceEvidence,
    ReferenceInputRequirement,
)
from app.intelligence.multi_funnel_discovery import (
    DiscoveryFunnelId,
    DiscoveryFunnelStatus,
    DiscoveryHorizon,
    DiscoveryLineageReference,
)
from app.intelligence.multi_funnel_discovery_adapters import (
    DiscoveryAdapterCoverageState,
    DiscoveryAdapterState,
)
from app.intelligence.multi_funnel_orchestration import (
    DiscoveryExecutionState,
    WholeMarketDiscoveryBatch,
)


DISCOVERY_RECALL_PER_SECURITY_TRACE_CONTRACT = "discovery-recall-per-security-evaluation-trace/v1"
_ID = re.compile(r"[A-Za-z0-9._:-]+\Z")
_FP = re.compile(r"(?:sha256:)?[0-9a-f]{64}\Z")
_NSE_INSTRUMENT = re.compile(r"NSE:(?P<isin>[A-Z]{2}[A-Z0-9]{9}[0-9])\Z")


class DiscoveryRecallTraceError(ValueError):
    """Stable fail-closed error for malformed trace evidence."""


class PerSecurityTraceState(StrEnum):
    LEAD_EMITTED = "LEAD_EMITTED"
    EVALUATED_NO_TRIGGER = "EVALUATED_NO_TRIGGER"
    NOT_IN_FUNNEL_SCOPE = "NOT_IN_FUNNEL_SCOPE"
    SOURCE_NOT_OPERATIONAL = "SOURCE_NOT_OPERATIONAL"
    ADAPTER_NOT_AVAILABLE = "ADAPTER_NOT_AVAILABLE"
    DATA_INSUFFICIENT = "DATA_INSUFFICIENT"
    IDENTITY_BLOCKED = "IDENTITY_BLOCKED"
    POLICY_BLOCKED = "POLICY_BLOCKED"
    EVIDENCE_CONFLICTED = "EVIDENCE_CONFLICTED"
    STALE = "STALE"
    PER_SECURITY_EVALUATION_UNKNOWN = "PER_SECURITY_EVALUATION_UNKNOWN"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    UNIVERSE_INELIGIBLE = "UNIVERSE_INELIGIBLE"


class PerSecurityTraceBasis(StrEnum):
    EXACT_SECURITY_EVALUATION = "EXACT_SECURITY_EVALUATION"
    BATCH_FUNNEL_CAPABILITY = "BATCH_FUNNEL_CAPABILITY"


class FunnelScopeState(StrEnum):
    IN_SCOPE = "IN_SCOPE"
    NOT_IN_SCOPE = "NOT_IN_SCOPE"
    SCOPE_UNKNOWN = "SCOPE_UNKNOWN"


class RequiredInputReadiness(StrEnum):
    READY = "READY"
    PARTIAL = "PARTIAL"
    MISSING = "MISSING"
    CONFLICTED = "CONFLICTED"
    STALE = "STALE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class SourceFreshnessState(StrEnum):
    TIMELY = "TIMELY"
    STALE = "STALE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True, slots=True)
class PerSecurityDiscoveryTrace:
    """One factual batch × funnel × exact NSE security trace.

    ``EVALUATED_NO_TRIGGER`` is accepted only with affirmative individual
    evidence.  The batch-derived factory deliberately never emits that state
    from an omitted lead.
    """

    discovery_batch_id: str
    discovery_batch_fingerprint: str
    as_of: datetime
    canonical_instrument_id: str
    isin: str
    issuer_ids: tuple[str, ...]
    funnel_id: DiscoveryFunnelId
    funnel_version: str
    adapter_id: str
    adapter_version: str
    funnel_posture: DiscoveryFunnelStatus
    horizons: tuple[DiscoveryHorizon, ...]
    universe_membership: UniverseMembershipState
    scope_state: FunnelScopeState
    trace_basis: PerSecurityTraceBasis
    state: PerSecurityTraceState
    evaluation_attempted: bool
    required_input_readiness: RequiredInputReadiness
    source_freshness: SourceFreshnessState
    lead_ids: tuple[str, ...]
    source_lineage: tuple[DiscoveryLineageReference, ...]
    no_trigger_reason_code: str | None
    blocker_reason_codes: tuple[str, ...]
    trace_id: str = field(init=False)
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        _id(self.discovery_batch_id, "DISCOVERY_RECALL_TRACE_BATCH_ID_INVALID")
        _fp(self.discovery_batch_fingerprint, "DISCOVERY_RECALL_TRACE_BATCH_FINGERPRINT_INVALID")
        object.__setattr__(self, "as_of", _utc(self.as_of, "DISCOVERY_RECALL_TRACE_AS_OF_INVALID"))
        _instrument(self.canonical_instrument_id, self.isin)
        object.__setattr__(self, "issuer_ids", _ids(self.issuer_ids, "DISCOVERY_RECALL_TRACE_ISSUERS_INVALID", allow_empty=True))
        _text(self.funnel_version, "DISCOVERY_RECALL_TRACE_FUNNEL_VERSION_INVALID")
        _id(self.adapter_id, "DISCOVERY_RECALL_TRACE_ADAPTER_ID_INVALID")
        _text(self.adapter_version, "DISCOVERY_RECALL_TRACE_ADAPTER_VERSION_INVALID")
        if not all(isinstance(item, expected) for item, expected in (
            (self.funnel_id, DiscoveryFunnelId), (self.funnel_posture, DiscoveryFunnelStatus),
            (self.universe_membership, UniverseMembershipState), (self.scope_state, FunnelScopeState),
            (self.trace_basis, PerSecurityTraceBasis), (self.state, PerSecurityTraceState),
            (self.required_input_readiness, RequiredInputReadiness),
            (self.source_freshness, SourceFreshnessState),
        )) or not isinstance(self.evaluation_attempted, bool):
            raise DiscoveryRecallTraceError("DISCOVERY_RECALL_TRACE_ENUM_INVALID")
        object.__setattr__(self, "horizons", _enums(self.horizons, DiscoveryHorizon, "DISCOVERY_RECALL_TRACE_HORIZONS_INVALID", allow_empty=True))
        object.__setattr__(self, "lead_ids", _ids(self.lead_ids, "DISCOVERY_RECALL_TRACE_LEAD_IDS_INVALID", allow_empty=True))
        object.__setattr__(self, "source_lineage", _lineage(self.source_lineage))
        if any(item.known_at > self.as_of for item in self.source_lineage):
            raise DiscoveryRecallTraceError("DISCOVERY_RECALL_TRACE_FUTURE_EVIDENCE_FORBIDDEN")
        if self.no_trigger_reason_code is not None:
            _id(self.no_trigger_reason_code, "DISCOVERY_RECALL_TRACE_NO_TRIGGER_REASON_INVALID")
        object.__setattr__(self, "blocker_reason_codes", _ids(self.blocker_reason_codes, "DISCOVERY_RECALL_TRACE_BLOCKERS_INVALID", allow_empty=True))
        _validate_trace(self)
        object.__setattr__(self, "trace_id", "discovery-evaluation-trace:" + manifest_fingerprint(**_trace_identity(self))[:32])
        object.__setattr__(self, "fingerprint", "sha256:" + manifest_fingerprint(**_trace_payload(self)))

    def verify(self) -> None:
        _verify(self, "DISCOVERY_RECALL_TRACE_TAMPERED")


@dataclass(frozen=True, slots=True)
class DiscoveryFunnelCapabilityTrace:
    """Compact factual capability receipt; not a per-security evaluation."""

    discovery_batch_id: str
    discovery_batch_fingerprint: str
    as_of: datetime
    funnel_id: DiscoveryFunnelId
    funnel_version: str
    funnel_posture: DiscoveryFunnelStatus
    adapter_id: str
    adapter_version: str
    adapter_state: DiscoveryAdapterState
    execution_state: DiscoveryExecutionState
    coverage_state: DiscoveryAdapterCoverageState
    source_records_supplied: int | None
    source_references: tuple[tuple[str, str], ...]
    reason_codes: tuple[str, ...]
    capability_id: str = field(init=False)
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        _id(self.discovery_batch_id, "DISCOVERY_RECALL_CAPABILITY_BATCH_ID_INVALID")
        _fp(self.discovery_batch_fingerprint, "DISCOVERY_RECALL_CAPABILITY_BATCH_FINGERPRINT_INVALID")
        object.__setattr__(self, "as_of", _utc(self.as_of, "DISCOVERY_RECALL_CAPABILITY_AS_OF_INVALID"))
        _text(self.funnel_version, "DISCOVERY_RECALL_CAPABILITY_FUNNEL_VERSION_INVALID")
        _id(self.adapter_id, "DISCOVERY_RECALL_CAPABILITY_ADAPTER_ID_INVALID")
        _text(self.adapter_version, "DISCOVERY_RECALL_CAPABILITY_ADAPTER_VERSION_INVALID")
        if not all(isinstance(item, expected) for item, expected in (
            (self.funnel_id, DiscoveryFunnelId), (self.funnel_posture, DiscoveryFunnelStatus),
            (self.adapter_state, DiscoveryAdapterState), (self.execution_state, DiscoveryExecutionState),
            (self.coverage_state, DiscoveryAdapterCoverageState),
        )):
            raise DiscoveryRecallTraceError("DISCOVERY_RECALL_CAPABILITY_ENUM_INVALID")
        if self.source_records_supplied is not None and (not isinstance(self.source_records_supplied, int) or self.source_records_supplied < 0):
            raise DiscoveryRecallTraceError("DISCOVERY_RECALL_CAPABILITY_SOURCE_COUNT_INVALID")
        object.__setattr__(self, "source_references", _references(self.source_references))
        object.__setattr__(self, "reason_codes", _ids(self.reason_codes, "DISCOVERY_RECALL_CAPABILITY_REASONS_INVALID", allow_empty=True))
        object.__setattr__(self, "capability_id", "discovery-funnel-capability:" + manifest_fingerprint(**_capability_identity(self))[:32])
        object.__setattr__(self, "fingerprint", "sha256:" + manifest_fingerprint(**_capability_payload(self)))

    def verify(self) -> None:
        _verify(self, "DISCOVERY_RECALL_CAPABILITY_TAMPERED")


@dataclass(frozen=True, slots=True)
class PerFunnelTraceAudit:
    """Read-only observability counts, never recall or performance metrics."""

    funnel_id: DiscoveryFunnelId
    executed: bool
    eligible_universe_count: int
    lead_emitted_trace_count: int
    evaluated_no_trigger_trace_count: int
    per_security_unknown_query_count: int
    capability_state: PerSecurityTraceState | None

    def __post_init__(self) -> None:
        if not isinstance(self.funnel_id, DiscoveryFunnelId) or not isinstance(self.executed, bool):
            raise DiscoveryRecallTraceError("DISCOVERY_RECALL_TRACE_AUDIT_TYPE_INVALID")
        if not all(isinstance(item, int) and item >= 0 for item in (
            self.eligible_universe_count, self.lead_emitted_trace_count,
            self.evaluated_no_trigger_trace_count, self.per_security_unknown_query_count,
        )):
            raise DiscoveryRecallTraceError("DISCOVERY_RECALL_TRACE_AUDIT_COUNT_INVALID")
        if self.lead_emitted_trace_count + self.evaluated_no_trigger_trace_count + self.per_security_unknown_query_count > self.eligible_universe_count:
            raise DiscoveryRecallTraceError("DISCOVERY_RECALL_TRACE_AUDIT_COUNT_CONTRADICTION")
        if self.executed != (self.capability_state is None):
            raise DiscoveryRecallTraceError("DISCOVERY_RECALL_TRACE_AUDIT_CAPABILITY_CONTRADICTION")
        if self.capability_state is not None and not isinstance(self.capability_state, PerSecurityTraceState):
            raise DiscoveryRecallTraceError("DISCOVERY_RECALL_TRACE_AUDIT_CAPABILITY_INVALID")


@dataclass(frozen=True, slots=True)
class PerSecurityTraceAudit:
    discovery_batch_id: str
    discovery_batch_fingerprint: str
    as_of: datetime
    capability_traces: tuple[DiscoveryFunnelCapabilityTrace, ...]
    emitted_traces: tuple[PerSecurityDiscoveryTrace, ...]
    per_funnel: tuple[PerFunnelTraceAudit, ...]
    audit_id: str = field(init=False)
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        _id(self.discovery_batch_id, "DISCOVERY_RECALL_TRACE_AUDIT_BATCH_ID_INVALID")
        _fp(self.discovery_batch_fingerprint, "DISCOVERY_RECALL_TRACE_AUDIT_BATCH_FINGERPRINT_INVALID")
        object.__setattr__(self, "as_of", _utc(self.as_of, "DISCOVERY_RECALL_TRACE_AUDIT_AS_OF_INVALID"))
        capabilities = _capabilities(self.capability_traces)
        emitted = _traces(self.emitted_traces)
        per_funnel = _per_funnel(self.per_funnel)
        for item in capabilities:
            item.verify()
        for item in emitted:
            item.verify()
        expected = tuple(item.funnel_id for item in capabilities)
        if tuple(item.funnel_id for item in per_funnel) != expected:
            raise DiscoveryRecallTraceError("DISCOVERY_RECALL_TRACE_AUDIT_FUNNELS_INVALID")
        if any(item.discovery_batch_id != self.discovery_batch_id or item.discovery_batch_fingerprint != self.discovery_batch_fingerprint or item.as_of != self.as_of for item in capabilities):
            raise DiscoveryRecallTraceError("DISCOVERY_RECALL_TRACE_AUDIT_CAPABILITY_BINDING_INVALID")
        if any(item.discovery_batch_id != self.discovery_batch_id or item.discovery_batch_fingerprint != self.discovery_batch_fingerprint or item.as_of != self.as_of for item in emitted):
            raise DiscoveryRecallTraceError("DISCOVERY_RECALL_TRACE_AUDIT_TRACE_BINDING_INVALID")
        object.__setattr__(self, "capability_traces", capabilities)
        object.__setattr__(self, "emitted_traces", emitted)
        object.__setattr__(self, "per_funnel", per_funnel)
        object.__setattr__(self, "audit_id", "discovery-trace-audit:" + manifest_fingerprint(**_audit_identity(self))[:32])
        object.__setattr__(self, "fingerprint", "sha256:" + manifest_fingerprint(**_audit_payload(self)))

    def verify(self) -> None:
        _verify(self, "DISCOVERY_RECALL_TRACE_AUDIT_TAMPERED")


def trace_security(*, discovery: WholeMarketDiscoveryBatch, canonical_instrument_id: str,
                   funnel_id: DiscoveryFunnelId) -> PerSecurityDiscoveryTrace:
    """Return one exact trace without scanning or materializing the universe."""
    _verify_batch(discovery)
    _id(canonical_instrument_id, "DISCOVERY_RECALL_TRACE_INSTRUMENT_INVALID")
    if not isinstance(funnel_id, DiscoveryFunnelId):
        raise DiscoveryRecallTraceError("DISCOVERY_RECALL_TRACE_FUNNEL_INVALID")
    execution = _execution(discovery, funnel_id)
    entry = discovery.registry.get(funnel_id)
    instrument = next((item for item in discovery.instruments if item.instrument_id == canonical_instrument_id), None)
    if instrument is None or canonical_instrument_id not in discovery.universe.instrument_ids:
        return _trace(
            discovery, execution, entry, canonical_instrument_id, _isin(canonical_instrument_id), (),
            UniverseMembershipState.INELIGIBLE, FunnelScopeState.NOT_IN_SCOPE,
            PerSecurityTraceBasis.BATCH_FUNNEL_CAPABILITY, PerSecurityTraceState.UNIVERSE_INELIGIBLE,
            False, RequiredInputReadiness.NOT_APPLICABLE, SourceFreshnessState.NOT_APPLICABLE,
            (), (), None, ("UNIVERSE_INELIGIBLE",),
        )
    item = next((value for value in discovery.candidate_union.candidates if value.canonical_instrument_id == canonical_instrument_id), None)
    leads = () if item is None else tuple(origin.lead for origin in item.origins if origin.lead.funnel_id is funnel_id)
    if leads:
        lineage = tuple(reference for lead in leads for reference in lead.lineage)
        return _trace(
            discovery, execution, entry, canonical_instrument_id, instrument.isin, item.issuer_ids,
            UniverseMembershipState.ELIGIBLE, FunnelScopeState.IN_SCOPE,
            PerSecurityTraceBasis.EXACT_SECURITY_EVALUATION, PerSecurityTraceState.LEAD_EMITTED,
            True, RequiredInputReadiness.READY, SourceFreshnessState.TIMELY,
            tuple(lead.lead_id for lead in leads), lineage, None, (),
        )
    capability = _capability_state(execution)
    if capability is None:
        return _trace(
            discovery, execution, entry, canonical_instrument_id, instrument.isin, (),
            UniverseMembershipState.ELIGIBLE, FunnelScopeState.SCOPE_UNKNOWN,
            PerSecurityTraceBasis.BATCH_FUNNEL_CAPABILITY, PerSecurityTraceState.PER_SECURITY_EVALUATION_UNKNOWN,
            False, RequiredInputReadiness.PARTIAL, SourceFreshnessState.NOT_APPLICABLE,
            (), (), None, ("PER_SECURITY_EVALUATION_UNAVAILABLE",),
        )
    return _trace(
        discovery, execution, entry, canonical_instrument_id, instrument.isin, (),
        UniverseMembershipState.ELIGIBLE, FunnelScopeState.SCOPE_UNKNOWN,
        PerSecurityTraceBasis.BATCH_FUNNEL_CAPABILITY, capability,
        False, _input_readiness(capability), _freshness(capability),
        (), (), None, tuple(reason.value for reason in execution.original.coverage.reason_codes),
    )


def emitted_lead_traces(*, discovery: WholeMarketDiscoveryBatch) -> tuple[PerSecurityDiscoveryTrace, ...]:
    """Materialize only exact existing emitted lead evidence; never negative rows."""
    _verify_batch(discovery)
    pairs = {
        (item.canonical_instrument_id, origin.lead.funnel_id)
        for item in discovery.candidate_union.candidates
        for origin in item.origins
    }
    return tuple(trace_security(discovery=discovery, canonical_instrument_id=instrument, funnel_id=funnel)
                 for instrument, funnel in sorted(pairs, key=lambda item: (item[1].value, item[0])))


def audit_per_security_traces(*, discovery: WholeMarketDiscoveryBatch) -> PerSecurityTraceAudit:
    """Create compact trace observability facts without a 14 × universe expansion."""
    _verify_batch(discovery)
    capabilities = tuple(_capability_trace(discovery, execution) for execution in discovery.executions)
    emitted = emitted_lead_traces(discovery=discovery)
    universe_count = discovery.universe.eligible_security_count
    per_funnel = tuple(
        PerFunnelTraceAudit(
            capability.funnel_id,
            capability.execution_state is DiscoveryExecutionState.EVALUATED,
            universe_count,
            sum(item.funnel_id is capability.funnel_id for item in emitted),
            0,
            universe_count - sum(item.funnel_id is capability.funnel_id for item in emitted)
            if capability.execution_state is DiscoveryExecutionState.EVALUATED else 0,
            _capability_state(_execution(discovery, capability.funnel_id)),
        )
        for capability in capabilities
    )
    return PerSecurityTraceAudit(discovery.batch_id, discovery.fingerprint, discovery.as_of,
                                 capabilities, emitted, per_funnel)


def as_reference_matching_evaluation(trace: PerSecurityDiscoveryTrace) -> PerSecurityDiscoveryEvaluation:
    """Safely narrow a trace into the active reference matcher input contract."""
    if not isinstance(trace, PerSecurityDiscoveryTrace):
        raise DiscoveryRecallTraceError("DISCOVERY_RECALL_TRACE_REFERENCE_INPUT_INVALID")
    trace.verify()
    state = {
        PerSecurityTraceState.EVALUATED_NO_TRIGGER: PerSecurityDiscoveryState.EVALUATED_NO_TRIGGER,
        PerSecurityTraceState.DATA_INSUFFICIENT: PerSecurityDiscoveryState.DATA_BLOCKED,
        PerSecurityTraceState.IDENTITY_BLOCKED: PerSecurityDiscoveryState.IDENTITY_BLOCKED,
    }.get(trace.state, PerSecurityDiscoveryState.NOT_EVALUATED)
    evidence = ReferenceEvidence(trace.trace_id, trace.fingerprint, trace.as_of,
                                 ReferenceInputRequirement.CANONICAL_IDENTITY)
    return PerSecurityDiscoveryEvaluation(trace.discovery_batch_id, trace.discovery_batch_fingerprint,
                                          trace.canonical_instrument_id, trace.funnel_id, state, evidence)


def serialize_per_security_trace(value: PerSecurityDiscoveryTrace | DiscoveryFunnelCapabilityTrace | PerSecurityTraceAudit) -> str:
    value.verify()
    payload = _trace_payload(value) if isinstance(value, PerSecurityDiscoveryTrace) else (
        _capability_payload(value) if isinstance(value, DiscoveryFunnelCapabilityTrace) else _audit_payload(value)
    )
    return json.dumps(payload | {"fingerprint": value.fingerprint}, sort_keys=True, ensure_ascii=True,
                      separators=(",", ":"))


def _trace(discovery, execution, entry, instrument, isin, issuer_ids, membership, scope, basis, state,
           attempted, readiness, freshness, leads, lineage, no_trigger, blockers):
    return PerSecurityDiscoveryTrace(
        discovery.batch_id, discovery.fingerprint, discovery.as_of, instrument, isin, issuer_ids,
        entry.funnel_id, discovery.registry.version, execution.original.adapter_id,
        execution.original.adapter_version, entry.status, entry.horizons, membership, scope, basis, state,
        attempted, readiness, freshness, leads, lineage, no_trigger, blockers,
    )


def _capability_trace(discovery, execution) -> DiscoveryFunnelCapabilityTrace:
    entry = discovery.registry.get(execution.original.funnel_id)
    coverage = execution.original.coverage
    return DiscoveryFunnelCapabilityTrace(
        discovery.batch_id, discovery.fingerprint, discovery.as_of, entry.funnel_id,
        discovery.registry.version, entry.status,
        execution.original.adapter_id, execution.original.adapter_version, coverage.adapter_state,
        execution.state, coverage.state, execution.source_records_supplied,
        execution.source_references, tuple(reason.value for reason in coverage.reason_codes),
    )


def _capability_state(execution) -> PerSecurityTraceState | None:
    if execution.state is DiscoveryExecutionState.EVALUATED:
        return None
    coverage = execution.original.coverage
    if coverage.adapter_state is DiscoveryAdapterState.NOT_IMPLEMENTED:
        return PerSecurityTraceState.NOT_IMPLEMENTED
    if coverage.state is DiscoveryAdapterCoverageState.POLICY_BLOCKED:
        return PerSecurityTraceState.POLICY_BLOCKED
    if coverage.state is DiscoveryAdapterCoverageState.SOURCE_NOT_OPERATIONAL:
        return PerSecurityTraceState.SOURCE_NOT_OPERATIONAL
    if coverage.state is DiscoveryAdapterCoverageState.EVIDENCE_CONFLICTED:
        return PerSecurityTraceState.EVIDENCE_CONFLICTED
    if coverage.state is DiscoveryAdapterCoverageState.IDENTITY_BLOCKED:
        return PerSecurityTraceState.IDENTITY_BLOCKED
    if coverage.state is DiscoveryAdapterCoverageState.STALE:
        return PerSecurityTraceState.STALE
    if execution.state is DiscoveryExecutionState.ADAPTER_FAILED:
        return PerSecurityTraceState.ADAPTER_NOT_AVAILABLE
    return PerSecurityTraceState.DATA_INSUFFICIENT


def _input_readiness(state: PerSecurityTraceState) -> RequiredInputReadiness:
    return {
        PerSecurityTraceState.DATA_INSUFFICIENT: RequiredInputReadiness.MISSING,
        PerSecurityTraceState.IDENTITY_BLOCKED: RequiredInputReadiness.PARTIAL,
        PerSecurityTraceState.EVIDENCE_CONFLICTED: RequiredInputReadiness.CONFLICTED,
        PerSecurityTraceState.STALE: RequiredInputReadiness.STALE,
    }.get(state, RequiredInputReadiness.NOT_APPLICABLE)


def _freshness(state: PerSecurityTraceState) -> SourceFreshnessState:
    return SourceFreshnessState.STALE if state is PerSecurityTraceState.STALE else SourceFreshnessState.NOT_APPLICABLE


def _execution(discovery: WholeMarketDiscoveryBatch, funnel_id: DiscoveryFunnelId):
    return next(item for item in discovery.executions if item.original.funnel_id is funnel_id)


def _verify_batch(value: WholeMarketDiscoveryBatch) -> None:
    if not isinstance(value, WholeMarketDiscoveryBatch):
        raise DiscoveryRecallTraceError("DISCOVERY_RECALL_TRACE_BATCH_REQUIRED")
    try:
        value.verify()
    except ValueError as error:
        raise DiscoveryRecallTraceError("DISCOVERY_RECALL_TRACE_BATCH_TAMPERED") from error


def _validate_trace(value: PerSecurityDiscoveryTrace) -> None:
    emitted = value.state is PerSecurityTraceState.LEAD_EMITTED
    no_trigger = value.state is PerSecurityTraceState.EVALUATED_NO_TRIGGER
    individual_blocker_states = {
        PerSecurityTraceState.DATA_INSUFFICIENT,
        PerSecurityTraceState.IDENTITY_BLOCKED,
        PerSecurityTraceState.EVIDENCE_CONFLICTED,
        PerSecurityTraceState.STALE,
    }
    global_capability_states = {
        PerSecurityTraceState.SOURCE_NOT_OPERATIONAL,
        PerSecurityTraceState.ADAPTER_NOT_AVAILABLE,
        PerSecurityTraceState.POLICY_BLOCKED,
        PerSecurityTraceState.NOT_IMPLEMENTED,
    }
    if value.universe_membership is UniverseMembershipState.INELIGIBLE:
        if not (
            value.state is PerSecurityTraceState.UNIVERSE_INELIGIBLE
            and value.trace_basis is PerSecurityTraceBasis.BATCH_FUNNEL_CAPABILITY
            and value.scope_state is FunnelScopeState.NOT_IN_SCOPE
            and not value.evaluation_attempted
            and value.required_input_readiness is RequiredInputReadiness.NOT_APPLICABLE
            and value.source_freshness is SourceFreshnessState.NOT_APPLICABLE
            and not value.lead_ids
            and not value.source_lineage
        ):
            raise DiscoveryRecallTraceError("DISCOVERY_RECALL_TRACE_UNIVERSE_CONTRADICTION")
        return
    if value.state is PerSecurityTraceState.UNIVERSE_INELIGIBLE:
        raise DiscoveryRecallTraceError("DISCOVERY_RECALL_TRACE_UNIVERSE_CONTRADICTION")
    if emitted:
        if not (value.evaluation_attempted and value.trace_basis is PerSecurityTraceBasis.EXACT_SECURITY_EVALUATION
                and value.scope_state is FunnelScopeState.IN_SCOPE and value.lead_ids and value.source_lineage
                and value.required_input_readiness is RequiredInputReadiness.READY
                and value.source_freshness is SourceFreshnessState.TIMELY
                and value.no_trigger_reason_code is None and not value.blocker_reason_codes):
            raise DiscoveryRecallTraceError("DISCOVERY_RECALL_TRACE_EMITTED_CONTRADICTION")
        return
    if no_trigger:
        if not (value.evaluation_attempted and value.trace_basis is PerSecurityTraceBasis.EXACT_SECURITY_EVALUATION
                and value.scope_state is FunnelScopeState.IN_SCOPE
                and value.required_input_readiness is RequiredInputReadiness.READY
                and value.source_freshness is SourceFreshnessState.TIMELY
                and value.no_trigger_reason_code is not None and not value.lead_ids and value.source_lineage
                and not value.blocker_reason_codes):
            raise DiscoveryRecallTraceError("DISCOVERY_RECALL_TRACE_NO_TRIGGER_PROOF_REQUIRED")
        return
    if value.lead_ids or value.no_trigger_reason_code is not None:
        raise DiscoveryRecallTraceError("DISCOVERY_RECALL_TRACE_NON_EMISSION_CONTRADICTION")
    if not value.blocker_reason_codes:
        raise DiscoveryRecallTraceError("DISCOVERY_RECALL_TRACE_BLOCKER_REASON_REQUIRED")
    if value.state is PerSecurityTraceState.NOT_IN_FUNNEL_SCOPE and (
        value.scope_state is not FunnelScopeState.NOT_IN_SCOPE
        or value.trace_basis is not PerSecurityTraceBasis.BATCH_FUNNEL_CAPABILITY
        or value.evaluation_attempted
        or value.source_lineage
    ):
        raise DiscoveryRecallTraceError("DISCOVERY_RECALL_TRACE_SCOPE_CONTRADICTION")
    if value.state is PerSecurityTraceState.PER_SECURITY_EVALUATION_UNKNOWN and (
        value.scope_state is not FunnelScopeState.SCOPE_UNKNOWN
        or value.trace_basis is not PerSecurityTraceBasis.BATCH_FUNNEL_CAPABILITY
        or value.evaluation_attempted
        or value.source_lineage
    ):
        raise DiscoveryRecallTraceError("DISCOVERY_RECALL_TRACE_UNKNOWN_CONTRADICTION")
    if value.state in global_capability_states and (
        value.trace_basis is not PerSecurityTraceBasis.BATCH_FUNNEL_CAPABILITY
        or value.scope_state is not FunnelScopeState.SCOPE_UNKNOWN
        or value.evaluation_attempted
        or value.source_lineage
        or value.required_input_readiness is not RequiredInputReadiness.NOT_APPLICABLE
        or value.source_freshness is not SourceFreshnessState.NOT_APPLICABLE
    ):
        raise DiscoveryRecallTraceError("DISCOVERY_RECALL_TRACE_GLOBAL_CAPABILITY_CONTRADICTION")
    if value.state in individual_blocker_states and (
        value.trace_basis is PerSecurityTraceBasis.EXACT_SECURITY_EVALUATION
        and (
            value.scope_state is not FunnelScopeState.IN_SCOPE
            or not value.evaluation_attempted
            or not value.source_lineage
            or value.required_input_readiness is not _input_readiness(value.state)
            or value.source_freshness is not _freshness(value.state)
        )
    ):
        raise DiscoveryRecallTraceError("DISCOVERY_RECALL_TRACE_INDIVIDUAL_BLOCKER_PROOF_REQUIRED")
    if value.trace_basis is PerSecurityTraceBasis.BATCH_FUNNEL_CAPABILITY and value.evaluation_attempted:
        raise DiscoveryRecallTraceError("DISCOVERY_RECALL_TRACE_CAPABILITY_NOT_EVALUATION")


def _trace_identity(value: PerSecurityDiscoveryTrace) -> dict[str, object]:
    return {
        "contract": DISCOVERY_RECALL_PER_SECURITY_TRACE_CONTRACT,
        "batch": value.discovery_batch_id,
        "batch_fingerprint": value.discovery_batch_fingerprint,
        "as_of": _time(value.as_of),
        "instrument": value.canonical_instrument_id,
        "funnel": value.funnel_id.value,
        "funnel_version": value.funnel_version,
        "adapter": value.adapter_id,
        "adapter_version": value.adapter_version,
    }


def _trace_payload(value: PerSecurityDiscoveryTrace) -> dict[str, object]:
    return _trace_identity(value) | {
        "isin": value.isin, "issuers": value.issuer_ids, "posture": value.funnel_posture.value,
        "horizons": tuple(item.value for item in value.horizons), "universe": value.universe_membership.value,
        "scope": value.scope_state.value, "basis": value.trace_basis.value, "state": value.state.value,
        "attempted": value.evaluation_attempted, "readiness": value.required_input_readiness.value,
        "freshness": value.source_freshness.value, "leads": value.lead_ids,
        "lineage": tuple(_lineage_payload(item) for item in value.source_lineage),
        "no_trigger_reason": value.no_trigger_reason_code, "blockers": value.blocker_reason_codes,
        "trace_id": value.trace_id,
    }


def _capability_identity(value: DiscoveryFunnelCapabilityTrace) -> dict[str, object]:
    return {
        "contract": DISCOVERY_RECALL_PER_SECURITY_TRACE_CONTRACT,
        "batch": value.discovery_batch_id, "batch_fingerprint": value.discovery_batch_fingerprint,
        "as_of": _time(value.as_of), "funnel": value.funnel_id.value,
        "funnel_version": value.funnel_version, "adapter": value.adapter_id,
        "adapter_version": value.adapter_version,
    }


def _capability_payload(value: DiscoveryFunnelCapabilityTrace) -> dict[str, object]:
    return _capability_identity(value) | {
        "posture": value.funnel_posture.value, "adapter_state": value.adapter_state.value,
        "execution_state": value.execution_state.value, "coverage_state": value.coverage_state.value,
        "source_count": value.source_records_supplied, "sources": value.source_references,
        "reasons": value.reason_codes, "capability_id": value.capability_id,
    }


def _audit_identity(value: PerSecurityTraceAudit) -> dict[str, object]:
    return {
        "contract": DISCOVERY_RECALL_PER_SECURITY_TRACE_CONTRACT,
        "batch": value.discovery_batch_id, "batch_fingerprint": value.discovery_batch_fingerprint,
        "as_of": _time(value.as_of),
    }


def _audit_payload(value: PerSecurityTraceAudit) -> dict[str, object]:
    return _audit_identity(value) | {
        "audit_id": value.audit_id,
        "capabilities": tuple(_capability_payload(item) for item in value.capability_traces),
        "emitted": tuple(_trace_payload(item) for item in value.emitted_traces),
        "per_funnel": tuple({
            "funnel": item.funnel_id.value, "executed": item.executed,
            "eligible": item.eligible_universe_count, "emitted": item.lead_emitted_trace_count,
            "no_trigger": item.evaluated_no_trigger_trace_count,
            "unknown_queries": item.per_security_unknown_query_count,
            "capability": None if item.capability_state is None else item.capability_state.value,
        } for item in value.per_funnel),
    }


def _lineage_payload(value: DiscoveryLineageReference) -> dict[str, object]:
    return {"id": value.reference_id, "fingerprint": value.reference_fingerprint,
            "kind": value.kind.value, "known_at": _time(value.known_at)}


def _lineage(values: tuple[DiscoveryLineageReference, ...]) -> tuple[DiscoveryLineageReference, ...]:
    if not isinstance(values, tuple) or any(not isinstance(item, DiscoveryLineageReference) for item in values):
        raise DiscoveryRecallTraceError("DISCOVERY_RECALL_TRACE_LINEAGE_INVALID")
    result = tuple(sorted(values, key=lambda item: (item.kind.value, item.reference_id, item.reference_fingerprint, item.known_at)))
    by_identity: dict[tuple[object, str], DiscoveryLineageReference] = {}
    for item in result:
        key = (item.kind, item.reference_id)
        prior = by_identity.get(key)
        if prior is not None and prior != item:
            raise DiscoveryRecallTraceError("DISCOVERY_RECALL_TRACE_LINEAGE_CONFLICT")
        by_identity[key] = item
    return tuple(sorted(by_identity.values(), key=lambda item: (item.kind.value, item.reference_id, item.reference_fingerprint, item.known_at)))


def _references(values: tuple[tuple[str, str], ...]) -> tuple[tuple[str, str], ...]:
    if not isinstance(values, tuple) or any(not isinstance(item, tuple) or len(item) != 2 for item in values):
        raise DiscoveryRecallTraceError("DISCOVERY_RECALL_CAPABILITY_REFERENCES_INVALID")
    for identifier, fingerprint in values:
        _id(identifier, "DISCOVERY_RECALL_CAPABILITY_REFERENCE_ID_INVALID")
        _fp(fingerprint, "DISCOVERY_RECALL_CAPABILITY_REFERENCE_FINGERPRINT_INVALID")
    return tuple(sorted(values))


def _traces(values: tuple[PerSecurityDiscoveryTrace, ...]) -> tuple[PerSecurityDiscoveryTrace, ...]:
    if not isinstance(values, tuple) or any(not isinstance(item, PerSecurityDiscoveryTrace) for item in values):
        raise DiscoveryRecallTraceError("DISCOVERY_RECALL_TRACE_AUDIT_TRACES_INVALID")
    result = tuple(sorted(values, key=lambda item: (item.funnel_id.value, item.canonical_instrument_id)))
    if len({(item.funnel_id, item.canonical_instrument_id) for item in result}) != len(result):
        raise DiscoveryRecallTraceError("DISCOVERY_RECALL_TRACE_AUDIT_TRACES_CONFLICT")
    return result


def _capabilities(values: tuple[DiscoveryFunnelCapabilityTrace, ...]) -> tuple[DiscoveryFunnelCapabilityTrace, ...]:
    if not isinstance(values, tuple) or any(not isinstance(item, DiscoveryFunnelCapabilityTrace) for item in values):
        raise DiscoveryRecallTraceError("DISCOVERY_RECALL_TRACE_AUDIT_CAPABILITIES_INVALID")
    result = tuple(sorted(values, key=lambda item: item.funnel_id.value))
    if len({item.funnel_id for item in result}) != len(result):
        raise DiscoveryRecallTraceError("DISCOVERY_RECALL_TRACE_AUDIT_CAPABILITIES_CONFLICT")
    return result


def _per_funnel(values: tuple[PerFunnelTraceAudit, ...]) -> tuple[PerFunnelTraceAudit, ...]:
    if not isinstance(values, tuple) or any(not isinstance(item, PerFunnelTraceAudit) for item in values):
        raise DiscoveryRecallTraceError("DISCOVERY_RECALL_TRACE_AUDIT_ROWS_INVALID")
    result = tuple(sorted(values, key=lambda item: item.funnel_id.value))
    if len({item.funnel_id for item in result}) != len(result):
        raise DiscoveryRecallTraceError("DISCOVERY_RECALL_TRACE_AUDIT_ROWS_CONFLICT")
    return result


def _enums(values, kind, code, *, allow_empty: bool) -> tuple:
    if not isinstance(values, tuple) or (not allow_empty and not values) or any(not isinstance(item, kind) for item in values):
        raise DiscoveryRecallTraceError(code)
    result = tuple(sorted(values, key=lambda item: item.value))
    if len(set(result)) != len(result):
        raise DiscoveryRecallTraceError(code)
    return result


def _ids(values, code, *, allow_empty: bool) -> tuple[str, ...]:
    if not isinstance(values, tuple) or (not allow_empty and not values):
        raise DiscoveryRecallTraceError(code)
    for value in values:
        _id(value, code)
    result = tuple(sorted(values))
    if len(set(result)) != len(result):
        raise DiscoveryRecallTraceError(code)
    return result


def _instrument(value: str, isin: str) -> None:
    matched = _NSE_INSTRUMENT.fullmatch(value) if isinstance(value, str) else None
    if matched is None or not isinstance(isin, str) or matched.group("isin") != isin:
        raise DiscoveryRecallTraceError("DISCOVERY_RECALL_TRACE_CANONICAL_IDENTITY_INVALID")


def _isin(value: str) -> str:
    matched = _NSE_INSTRUMENT.fullmatch(value)
    if matched is None:
        raise DiscoveryRecallTraceError("DISCOVERY_RECALL_TRACE_CANONICAL_IDENTITY_INVALID")
    return matched.group("isin")


def _verify(value: object, code: str) -> None:
    fields = {name: getattr(value, name) for name in value.__dataclass_fields__
              if name not in {"trace_id", "capability_id", "audit_id", "fingerprint"}}
    rebuilt = type(value)(**fields)
    if rebuilt != value:
        raise DiscoveryRecallTraceError(code)


def _id(value: object, code: str) -> None:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise DiscoveryRecallTraceError(code)


def _fp(value: object, code: str) -> None:
    if not isinstance(value, str) or _FP.fullmatch(value) is None:
        raise DiscoveryRecallTraceError(code)


def _text(value: object, code: str) -> None:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise DiscoveryRecallTraceError(code)


def _utc(value: object, code: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise DiscoveryRecallTraceError(code)
    return value.astimezone(UTC)


def _time(value: datetime) -> str:
    return _utc(value, "DISCOVERY_RECALL_TRACE_TIME_INVALID").isoformat()


__all__ = (
    "DISCOVERY_RECALL_PER_SECURITY_TRACE_CONTRACT", "DiscoveryFunnelCapabilityTrace",
    "DiscoveryRecallTraceError", "FunnelScopeState", "PerFunnelTraceAudit",
    "PerSecurityDiscoveryTrace", "PerSecurityTraceAudit", "PerSecurityTraceBasis",
    "PerSecurityTraceState", "RequiredInputReadiness", "SourceFreshnessState",
    "as_reference_matching_evaluation", "audit_per_security_traces", "emitted_lead_traces",
    "serialize_per_security_trace", "trace_security",
)
