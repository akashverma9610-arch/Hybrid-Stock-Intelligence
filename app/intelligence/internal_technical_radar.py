"""Provider-neutral, discovery-only HSI Internal Technical Radar.

The radar is a small read-only bridge from already canonical/governed
technical evidence to the existing ``CanonicalDiscoveryLead`` contract.  It
does not calculate an indicator, rank securities, create a setup, run a
diagnostic, persist a result, or perform an action.  The only V1 discovery
path is the already governed Pre-Breakout setup opportunity.  Fifteen-minute
bars are accepted solely as canonical input coverage; no 15m discovery
condition is activated without a separately governed policy.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
import json
import re

from app.historical.guard import manifest_fingerprint
from app.intelligence.multi_funnel_discovery import (
    CanonicalDiscoveryLead,
    DiscoveryFunnelId,
    discovery_lead_payload,
)
from app.intelligence.multi_funnel_discovery_adapters import (
    DiscoveryAdapterCoverageState,
    adapt_pre_breakout,
)
from app.market_data.canonical_fifteen_minute_technical_reader import (
    CanonicalFifteenMinuteContinuityState,
    CanonicalFifteenMinuteTechnicalRead,
    CanonicalFifteenMinuteTechnicalReadMode,
    CanonicalFifteenMinuteTechnicalReadReason,
    CanonicalFifteenMinuteTechnicalReadState,
)
from app.production_v1.canonical_setup_activation import CanonicalSetupOpportunity


INTERNAL_TECHNICAL_RADAR_CONTRACT = "hsi-internal-technical-radar/v1"
INTERNAL_TECHNICAL_RADAR_POLICY_ID = "hsi-internal-technical-radar-policy"
INTERNAL_TECHNICAL_RADAR_POLICY_VERSION = "v1"
INTERNAL_TECHNICAL_RADAR_POLICY_FINGERPRINT = (
    "sha256:1ec92b512bd5eac9695e48e9b30f77f396cba60e5e0d3d9776862145a8ef711c"
)
_NSE_SECURITY = re.compile(r"NSE:[A-Z]{2}[A-Z0-9]{9}[0-9]\Z")
_ID = re.compile(r"[A-Za-z0-9._:-]+\Z")
_FP = re.compile(r"(?:sha256:)?[0-9a-f]{64}\Z")
_MAX_BATCH_SECURITIES = 3_000


class InternalTechnicalRadarError(ValueError):
    """Stable fail-closed error for a malformed radar input or result."""


class TechnicalRadarAuthority(StrEnum):
    DISCOVERY_ONLY = "DISCOVERY_ONLY"


class TechnicalRadarRuntimeState(StrEnum):
    NOT_ACTIVE = "NOT_ACTIVE"


class TechnicalRadarLiveProductionState(StrEnum):
    NOT_READY = "NOT_READY"


class TechnicalRadarDiscoveryState(StrEnum):
    DISCOVERED = "DISCOVERED"
    NOT_TRIGGERED = "NOT_TRIGGERED"
    DATA_INSUFFICIENT = "DATA_INSUFFICIENT"
    EVIDENCE_CONFLICTED = "EVIDENCE_CONFLICTED"
    POLICY_BLOCKED = "POLICY_BLOCKED"


class PreBreakoutRadarEvidenceState(StrEnum):
    GOVERNED_SETUP_AVAILABLE = "GOVERNED_SETUP_AVAILABLE"
    NO_CURRENT_GOVERNED_SETUP = "NO_CURRENT_GOVERNED_SETUP"
    DATA_INSUFFICIENT = "DATA_INSUFFICIENT"
    EVIDENCE_CONFLICTED = "EVIDENCE_CONFLICTED"
    POLICY_BLOCKED = "POLICY_BLOCKED"


class FifteenMinuteTechnicalInputState(StrEnum):
    NO_CANONICAL_INPUT = "NO_CANONICAL_INPUT"
    INPUT_READY_POLICY_BLOCKED = "INPUT_READY_POLICY_BLOCKED"
    DATA_INSUFFICIENT = "DATA_INSUFFICIENT"
    EVIDENCE_CONFLICTED = "EVIDENCE_CONFLICTED"


class TechnicalRadarReason(StrEnum):
    PREBREAKOUT_EVIDENCE_NOT_SUPPLIED = "PREBREAKOUT_EVIDENCE_NOT_SUPPLIED"
    NO_CURRENT_GOVERNED_SETUP = "NO_CURRENT_GOVERNED_SETUP"
    PREBREAKOUT_DATA_INSUFFICIENT = "PREBREAKOUT_DATA_INSUFFICIENT"
    PREBREAKOUT_EVIDENCE_CONFLICTED = "PREBREAKOUT_EVIDENCE_CONFLICTED"
    PREBREAKOUT_POLICY_BLOCKED = "PREBREAKOUT_POLICY_BLOCKED"
    PREBREAKOUT_SOURCE_AS_OF_AFTER_CUTOFF = "PREBREAKOUT_SOURCE_AS_OF_AFTER_CUTOFF"
    PREBREAKOUT_CANONICAL_SOURCE_INVALID = "PREBREAKOUT_CANONICAL_SOURCE_INVALID"
    PREBREAKOUT_ADAPTER_OUTPUT_INVALID = "PREBREAKOUT_ADAPTER_OUTPUT_INVALID"
    CANONICAL_15M_INPUT_NOT_SUPPLIED = "CANONICAL_15M_INPUT_NOT_SUPPLIED"
    CANONICAL_15M_TECHNICAL_DISCOVERY_POLICY_UNAVAILABLE = "CANONICAL_15M_TECHNICAL_DISCOVERY_POLICY_UNAVAILABLE"
    CANONICAL_15M_CONTINUITY_POLICY_UNSET = "CANONICAL_15M_CONTINUITY_POLICY_UNSET"
    CANONICAL_15M_OBSERVATION_GAP_OR_INCOMPLETE = "CANONICAL_15M_OBSERVATION_GAP_OR_INCOMPLETE"
    CANONICAL_15M_NO_TRADE_UNMATERIALIZED = "CANONICAL_15M_NO_TRADE_UNMATERIALIZED"
    CANONICAL_15M_EVIDENCE_CONFLICTED = "CANONICAL_15M_EVIDENCE_CONFLICTED"
    CANONICAL_15M_INPUT_INSUFFICIENT = "CANONICAL_15M_INPUT_INSUFFICIENT"


@dataclass(frozen=True, slots=True)
class TechnicalRadarUniverseScope:
    """A caller-supplied, immutable canonical universe scope and coverage facts.

    Provider mapping facts are coverage denominators only.  They are never
    used as market evidence, a discovery trigger, or a provider call.
    """

    universe_snapshot_id: str
    universe_snapshot_fingerprint: str
    selected_canonical_security_ids: tuple[str, ...]
    canonical_eligible_security_ids: tuple[str, ...]
    provider_exact_ready_security_ids: tuple[str, ...]
    blocked_identity_security_ids: tuple[str, ...]
    actual_live_fifteen_minute_security_ids: tuple[str, ...]
    scope_id: str = field(init=False)
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        for value, code in (
            (self.universe_snapshot_id, "TECHNICAL_RADAR_UNIVERSE_ID_INVALID"),
            (self.universe_snapshot_fingerprint, "TECHNICAL_RADAR_UNIVERSE_FINGERPRINT_INVALID"),
        ):
            if not isinstance(value, str) or not value:
                raise InternalTechnicalRadarError(code)
        if not _ID.fullmatch(self.universe_snapshot_id) or not _FP.fullmatch(self.universe_snapshot_fingerprint):
            raise InternalTechnicalRadarError("TECHNICAL_RADAR_UNIVERSE_LINEAGE_INVALID")
        for name in (
            "selected_canonical_security_ids", "canonical_eligible_security_ids",
            "provider_exact_ready_security_ids", "blocked_identity_security_ids",
            "actual_live_fifteen_minute_security_ids",
        ):
            object.__setattr__(self, name, _security_ids(getattr(self, name), "TECHNICAL_RADAR_SCOPE_SECURITY_IDS_INVALID"))
        selected = set(self.selected_canonical_security_ids)
        eligible = set(self.canonical_eligible_security_ids)
        ready = set(self.provider_exact_ready_security_ids)
        blocked = set(self.blocked_identity_security_ids)
        live = set(self.actual_live_fifteen_minute_security_ids)
        if not eligible <= selected or not ready <= selected or not blocked <= selected or not live <= eligible:
            raise InternalTechnicalRadarError("TECHNICAL_RADAR_SCOPE_COVERAGE_OUTSIDE_UNIVERSE")
        if ready & blocked:
            raise InternalTechnicalRadarError("TECHNICAL_RADAR_SCOPE_IDENTITY_PARTITION_INVALID")
        if len(self.canonical_eligible_security_ids) > _MAX_BATCH_SECURITIES:
            raise InternalTechnicalRadarError("TECHNICAL_RADAR_BATCH_BOUND_EXCEEDED")
        object.__setattr__(self, "scope_id", "technical-radar-scope:" + manifest_fingerprint(**_scope_identity(self))[:32])
        object.__setattr__(self, "fingerprint", manifest_fingerprint(**_scope_payload(self)))

    def verify(self) -> None:
        if replace(self) != self:
            raise InternalTechnicalRadarError("TECHNICAL_RADAR_SCOPE_TAMPERED")


@dataclass(frozen=True, slots=True)
class PreBreakoutRadarEvidence:
    """A descriptive projection of one canonical Pre-Breakout query result."""

    canonical_security_id: str
    state: PreBreakoutRadarEvidenceState
    source_as_of: datetime
    opportunity: CanonicalSetupOpportunity | None = None
    reason_codes: tuple[TechnicalRadarReason, ...] = ()
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_as_of", _utc(self.source_as_of, "TECHNICAL_RADAR_PREBREAKOUT_SOURCE_AS_OF_INVALID"))
        object.__setattr__(self, "reason_codes", _reasons(self.reason_codes, "TECHNICAL_RADAR_PREBREAKOUT_REASONS_INVALID"))
        if not _security(self.canonical_security_id) or not isinstance(self.state, PreBreakoutRadarEvidenceState):
            raise InternalTechnicalRadarError("TECHNICAL_RADAR_PREBREAKOUT_EVIDENCE_INVALID")
        available = self.state is PreBreakoutRadarEvidenceState.GOVERNED_SETUP_AVAILABLE
        if available != (self.opportunity is not None) or (available and self.reason_codes):
            raise InternalTechnicalRadarError("TECHNICAL_RADAR_PREBREAKOUT_AVAILABILITY_INVALID")
        if not available and self.opportunity is not None:
            raise InternalTechnicalRadarError("TECHNICAL_RADAR_PREBREAKOUT_STATE_CONTRADICTION")
        if available:
            try:
                self.opportunity.__post_init__()
            except ValueError as error:
                raise InternalTechnicalRadarError("TECHNICAL_RADAR_PREBREAKOUT_CANONICAL_SOURCE_INVALID") from error
            if (
                self.opportunity.canonical_instrument_id != self.canonical_security_id
                or _utc(self.opportunity.decision_as_of, "TECHNICAL_RADAR_PREBREAKOUT_SOURCE_AS_OF_INVALID") != self.source_as_of
            ):
                raise InternalTechnicalRadarError("TECHNICAL_RADAR_PREBREAKOUT_SOURCE_MISMATCH")
        elif not self.reason_codes:
            raise InternalTechnicalRadarError("TECHNICAL_RADAR_PREBREAKOUT_REASON_REQUIRED")
        object.__setattr__(self, "fingerprint", manifest_fingerprint(**_prebreakout_evidence_payload(self)))

    def verify(self) -> None:
        if replace(self) != self:
            raise InternalTechnicalRadarError("TECHNICAL_RADAR_PREBREAKOUT_EVIDENCE_TAMPERED")


@dataclass(frozen=True, slots=True)
class FifteenMinuteTechnicalInputCoverage:
    """Descriptive canonical 15m input coverage; it activates no discovery rule."""

    state: FifteenMinuteTechnicalInputState
    supplied_security_count: int
    ready_security_count: int
    data_insufficient_security_count: int
    conflicted_security_count: int
    no_trade_unmaterialized_security_count: int
    reason_codes: tuple[TechnicalRadarReason, ...]
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason_codes", _reasons(self.reason_codes, "TECHNICAL_RADAR_15M_REASONS_INVALID"))
        counts = (
            self.supplied_security_count, self.ready_security_count,
            self.data_insufficient_security_count, self.conflicted_security_count,
            self.no_trade_unmaterialized_security_count,
        )
        if not isinstance(self.state, FifteenMinuteTechnicalInputState) or not all(type(value) is int and value >= 0 for value in counts):
            raise InternalTechnicalRadarError("TECHNICAL_RADAR_15M_COVERAGE_INVALID")
        if self.ready_security_count + self.data_insufficient_security_count + self.conflicted_security_count != self.supplied_security_count:
            raise InternalTechnicalRadarError("TECHNICAL_RADAR_15M_COVERAGE_PARTITION_INVALID")
        if self.no_trade_unmaterialized_security_count > self.data_insufficient_security_count:
            raise InternalTechnicalRadarError("TECHNICAL_RADAR_15M_NO_TRADE_COUNT_INVALID")
        if self.state is FifteenMinuteTechnicalInputState.NO_CANONICAL_INPUT and self.supplied_security_count:
            raise InternalTechnicalRadarError("TECHNICAL_RADAR_15M_EMPTY_STATE_INVALID")
        if self.state is FifteenMinuteTechnicalInputState.INPUT_READY_POLICY_BLOCKED and not self.ready_security_count:
            raise InternalTechnicalRadarError("TECHNICAL_RADAR_15M_POLICY_STATE_INVALID")
        if self.state is FifteenMinuteTechnicalInputState.EVIDENCE_CONFLICTED and not self.conflicted_security_count:
            raise InternalTechnicalRadarError("TECHNICAL_RADAR_15M_CONFLICT_STATE_INVALID")
        object.__setattr__(self, "fingerprint", manifest_fingerprint(**_fifteen_coverage_payload(self)))

    def verify(self) -> None:
        if replace(self) != self:
            raise InternalTechnicalRadarError("TECHNICAL_RADAR_15M_COVERAGE_TAMPERED")


@dataclass(frozen=True, slots=True)
class TechnicalRadarSecurityOutcome:
    """One evaluated exact security in the sole active V1 discovery family."""

    canonical_security_id: str
    discovery_state: TechnicalRadarDiscoveryState
    reason_codes: tuple[TechnicalRadarReason, ...]
    lead: CanonicalDiscoveryLead | None
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason_codes", _reasons(self.reason_codes, "TECHNICAL_RADAR_OUTCOME_REASONS_INVALID"))
        if not _security(self.canonical_security_id) or not isinstance(self.discovery_state, TechnicalRadarDiscoveryState):
            raise InternalTechnicalRadarError("TECHNICAL_RADAR_OUTCOME_INVALID")
        discovered = self.discovery_state is TechnicalRadarDiscoveryState.DISCOVERED
        if discovered != (self.lead is not None):
            raise InternalTechnicalRadarError("TECHNICAL_RADAR_OUTCOME_LEAD_CONTRADICTION")
        if discovered:
            self.lead.verify()
            if (
                self.lead.canonical_instrument_id != self.canonical_security_id
                or self.lead.funnel_id is not DiscoveryFunnelId.PRE_BREAKOUT
                or self.lead.readiness.value != "READY_FOR_INSPECTION"
                or self.reason_codes
            ):
                raise InternalTechnicalRadarError("TECHNICAL_RADAR_OUTCOME_LEAD_INVALID")
        elif not self.reason_codes:
            raise InternalTechnicalRadarError("TECHNICAL_RADAR_OUTCOME_REASON_REQUIRED")
        object.__setattr__(self, "fingerprint", manifest_fingerprint(**_outcome_payload(self)))

    def verify(self) -> None:
        if replace(self) != self:
            raise InternalTechnicalRadarError("TECHNICAL_RADAR_OUTCOME_TAMPERED")


@dataclass(frozen=True, slots=True)
class InternalTechnicalRadarRun:
    """A bounded, deterministic, non-persistent batch result.

    The batch is intentionally not a scheduler receipt, user alert, signal,
    candidate pool, score, setup, or action.  Downstream shared-Brain
    evaluation remains a separate explicit boundary.
    """

    as_of: datetime
    universe_scope: TechnicalRadarUniverseScope
    outcomes: tuple[TechnicalRadarSecurityOutcome, ...]
    fifteen_minute_coverage: FifteenMinuteTechnicalInputCoverage
    authority: TechnicalRadarAuthority = TechnicalRadarAuthority.DISCOVERY_ONLY
    runtime_state: TechnicalRadarRuntimeState = TechnicalRadarRuntimeState.NOT_ACTIVE
    live_production_state: TechnicalRadarLiveProductionState = TechnicalRadarLiveProductionState.NOT_READY
    policy_id: str = INTERNAL_TECHNICAL_RADAR_POLICY_ID
    policy_version: str = INTERNAL_TECHNICAL_RADAR_POLICY_VERSION
    policy_fingerprint: str = INTERNAL_TECHNICAL_RADAR_POLICY_FINGERPRINT
    run_id: str = field(init=False)
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "as_of", _utc(self.as_of, "TECHNICAL_RADAR_AS_OF_INVALID"))
        object.__setattr__(self, "outcomes", tuple(sorted(self.outcomes, key=lambda item: item.canonical_security_id)))
        if not isinstance(self.universe_scope, TechnicalRadarUniverseScope) or not isinstance(self.fifteen_minute_coverage, FifteenMinuteTechnicalInputCoverage):
            raise InternalTechnicalRadarError("TECHNICAL_RADAR_RUN_INPUT_INVALID")
        self.universe_scope.verify(); self.fifteen_minute_coverage.verify()
        if (
            self.authority is not TechnicalRadarAuthority.DISCOVERY_ONLY
            or self.runtime_state is not TechnicalRadarRuntimeState.NOT_ACTIVE
            or self.live_production_state is not TechnicalRadarLiveProductionState.NOT_READY
            or (self.policy_id, self.policy_version, self.policy_fingerprint) != (
                INTERNAL_TECHNICAL_RADAR_POLICY_ID,
                INTERNAL_TECHNICAL_RADAR_POLICY_VERSION,
                INTERNAL_TECHNICAL_RADAR_POLICY_FINGERPRINT,
            )
        ):
            raise InternalTechnicalRadarError("TECHNICAL_RADAR_AUTHORITY_OR_POLICY_INVALID")
        if (
            len(self.outcomes) != len(self.universe_scope.canonical_eligible_security_ids)
            or tuple(item.canonical_security_id for item in self.outcomes) != self.universe_scope.canonical_eligible_security_ids
        ):
            raise InternalTechnicalRadarError("TECHNICAL_RADAR_OUTCOME_SCOPE_INVALID")
        for outcome in self.outcomes:
            outcome.verify()
        object.__setattr__(self, "run_id", "internal-technical-radar:" + manifest_fingerprint(**_run_identity(self))[:32])
        object.__setattr__(self, "fingerprint", manifest_fingerprint(**_run_payload(self)))

    @property
    def evaluated_count(self) -> int:
        return sum(item.discovery_state in (TechnicalRadarDiscoveryState.DISCOVERED, TechnicalRadarDiscoveryState.NOT_TRIGGERED) for item in self.outcomes)

    @property
    def not_evaluable_count(self) -> int:
        return len(self.outcomes) - self.evaluated_count

    @property
    def triggered_lead_count(self) -> int:
        return sum(item.lead is not None for item in self.outcomes)

    @property
    def data_insufficient_count(self) -> int:
        return sum(item.discovery_state is TechnicalRadarDiscoveryState.DATA_INSUFFICIENT for item in self.outcomes)

    @property
    def blocked_identity_count(self) -> int:
        return len(self.universe_scope.blocked_identity_security_ids)

    @property
    def canonical_eligible_input_count(self) -> int:
        return len(self.universe_scope.canonical_eligible_security_ids)

    @property
    def selected_universe_count(self) -> int:
        return len(self.universe_scope.selected_canonical_security_ids)

    @property
    def provider_exact_ready_capacity(self) -> int:
        return len(self.universe_scope.provider_exact_ready_security_ids)

    @property
    def actual_live_fifteen_minute_coverage(self) -> int:
        return len(self.universe_scope.actual_live_fifteen_minute_security_ids)

    @property
    def discovery_leads(self) -> tuple[CanonicalDiscoveryLead, ...]:
        return tuple(item.lead for item in self.outcomes if item.lead is not None)

    def verify(self) -> None:
        if replace(self) != self:
            raise InternalTechnicalRadarError("TECHNICAL_RADAR_RUN_TAMPERED")


def evaluate_internal_technical_radar(
    *,
    as_of: datetime,
    universe_scope: TechnicalRadarUniverseScope,
    pre_breakout_evidence: tuple[PreBreakoutRadarEvidence, ...],
    fifteen_minute_reads: tuple[CanonicalFifteenMinuteTechnicalRead, ...] = (),
) -> InternalTechnicalRadarRun:
    """Evaluate one explicit bounded scope with no I/O, scheduler, or clock.

    Supplying a one-security scope is the single-security interface; supplying
    the current canonical eligible universe is the whole-universe-capable
    interface.  The caller owns invocation and source reads.
    """
    cutoff = _utc(as_of, "TECHNICAL_RADAR_AS_OF_INVALID")
    if not isinstance(universe_scope, TechnicalRadarUniverseScope):
        raise InternalTechnicalRadarError("TECHNICAL_RADAR_SCOPE_REQUIRED")
    universe_scope.verify()
    evidence_by_security, invalid_evidence_security_ids = _evidence_by_security(pre_breakout_evidence, universe_scope)
    coverage = _fifteen_minute_coverage(fifteen_minute_reads, cutoff, universe_scope)
    outcomes = tuple(
        _pre_breakout_outcome(
            canonical_security_id, evidence_by_security.get(canonical_security_id), cutoff,
            canonical_security_id in invalid_evidence_security_ids,
        )
        for canonical_security_id in universe_scope.canonical_eligible_security_ids
    )
    return InternalTechnicalRadarRun(cutoff, universe_scope, outcomes, coverage)


def internal_technical_radar_payload(value: InternalTechnicalRadarRun) -> dict[str, object]:
    value.verify()
    return _run_payload(value) | {"run_id": value.run_id, "fingerprint": value.fingerprint}


def serialize_internal_technical_radar(value: InternalTechnicalRadarRun) -> str:
    return json.dumps(internal_technical_radar_payload(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _evidence_by_security(values, scope):
    if not isinstance(values, tuple) or not all(isinstance(item, PreBreakoutRadarEvidence) for item in values):
        raise InternalTechnicalRadarError("TECHNICAL_RADAR_PREBREAKOUT_EVIDENCE_TUPLE_REQUIRED")
    grouped: dict[str, list[PreBreakoutRadarEvidence]] = {}
    invalid: set[str] = set()
    for item in values:
        security = item.canonical_security_id
        if not _security(security) or security not in scope.canonical_eligible_security_ids:
            raise InternalTechnicalRadarError("TECHNICAL_RADAR_PREBREAKOUT_EVIDENCE_OUTSIDE_SCOPE")
        try:
            item.verify()
        except InternalTechnicalRadarError:
            invalid.add(security)
            continue
        grouped.setdefault(security, []).append(item)
    result: dict[str, PreBreakoutRadarEvidence] = {}
    for security, items in grouped.items():
        fingerprints = {item.fingerprint for item in items}
        if len(fingerprints) != 1:
            invalid.add(security)
            continue
        result[security] = items[0]
    return result, frozenset(invalid)


def _pre_breakout_outcome(security, evidence, cutoff, invalid):
    if invalid:
        return _outcome(security, TechnicalRadarDiscoveryState.EVIDENCE_CONFLICTED, (TechnicalRadarReason.PREBREAKOUT_CANONICAL_SOURCE_INVALID,))
    if evidence is None:
        return _outcome(security, TechnicalRadarDiscoveryState.DATA_INSUFFICIENT, (TechnicalRadarReason.PREBREAKOUT_EVIDENCE_NOT_SUPPLIED,))
    if evidence.source_as_of > cutoff:
        return _outcome(security, TechnicalRadarDiscoveryState.DATA_INSUFFICIENT, (TechnicalRadarReason.PREBREAKOUT_SOURCE_AS_OF_AFTER_CUTOFF,))
    mapping = {
        PreBreakoutRadarEvidenceState.NO_CURRENT_GOVERNED_SETUP: (TechnicalRadarDiscoveryState.NOT_TRIGGERED, TechnicalRadarReason.NO_CURRENT_GOVERNED_SETUP),
        PreBreakoutRadarEvidenceState.DATA_INSUFFICIENT: (TechnicalRadarDiscoveryState.DATA_INSUFFICIENT, TechnicalRadarReason.PREBREAKOUT_DATA_INSUFFICIENT),
        PreBreakoutRadarEvidenceState.EVIDENCE_CONFLICTED: (TechnicalRadarDiscoveryState.EVIDENCE_CONFLICTED, TechnicalRadarReason.PREBREAKOUT_EVIDENCE_CONFLICTED),
        PreBreakoutRadarEvidenceState.POLICY_BLOCKED: (TechnicalRadarDiscoveryState.POLICY_BLOCKED, TechnicalRadarReason.PREBREAKOUT_POLICY_BLOCKED),
    }
    if evidence.state in mapping:
        state, reason = mapping[evidence.state]
        return _outcome(security, state, tuple(sorted(set((*evidence.reason_codes, reason)), key=lambda item: item.value)))
    try:
        adapted = adapt_pre_breakout(as_of=cutoff, opportunities=(evidence.opportunity,))
        adapted.verify()
    except (ValueError, TypeError, AttributeError):
        return _outcome(security, TechnicalRadarDiscoveryState.EVIDENCE_CONFLICTED, (TechnicalRadarReason.PREBREAKOUT_CANONICAL_SOURCE_INVALID,))
    if adapted.coverage.state is not DiscoveryAdapterCoverageState.LEADS_EMITTED or len(adapted.leads) != 1:
        return _outcome(security, TechnicalRadarDiscoveryState.EVIDENCE_CONFLICTED, (TechnicalRadarReason.PREBREAKOUT_ADAPTER_OUTPUT_INVALID,))
    lead = adapted.leads[0]
    if lead.canonical_instrument_id != security or lead.discovery_as_of > cutoff:
        return _outcome(security, TechnicalRadarDiscoveryState.EVIDENCE_CONFLICTED, (TechnicalRadarReason.PREBREAKOUT_ADAPTER_OUTPUT_INVALID,))
    return TechnicalRadarSecurityOutcome(security, TechnicalRadarDiscoveryState.DISCOVERED, (), lead)


def _fifteen_minute_coverage(values, cutoff, scope):
    if not isinstance(values, tuple) or not all(isinstance(item, CanonicalFifteenMinuteTechnicalRead) for item in values):
        raise InternalTechnicalRadarError("TECHNICAL_RADAR_15M_READ_TUPLE_REQUIRED")
    if not values:
        return FifteenMinuteTechnicalInputCoverage(
            FifteenMinuteTechnicalInputState.NO_CANONICAL_INPUT, 0, 0, 0, 0, 0,
            (TechnicalRadarReason.CANONICAL_15M_INPUT_NOT_SUPPLIED,),
        )
    by_security: dict[str, CanonicalFifteenMinuteTechnicalRead] = {}
    reasons: set[TechnicalRadarReason] = set()
    ready = insufficient = conflicted = no_trade = 0
    for read in values:
        if replace(read) != read:
            raise InternalTechnicalRadarError("TECHNICAL_RADAR_15M_READ_TAMPERED")
        request = read.request
        if (
            request.mode is not CanonicalFifteenMinuteTechnicalReadMode.AS_OF_PROSPECTIVE_PIT
            or request.as_of is None or _utc(request.as_of, "TECHNICAL_RADAR_15M_AS_OF_INVALID") > cutoff
            or request.canonical_security_id not in scope.canonical_eligible_security_ids
            or request.canonical_security_id in by_security
        ):
            raise InternalTechnicalRadarError("TECHNICAL_RADAR_15M_READ_CONTEXT_INVALID")
        by_security[request.canonical_security_id] = read
        continuity = set(read.continuity_states)
        reader_reasons = set(read.reasons)
        if (
            CanonicalFifteenMinuteContinuityState.EVIDENCE_CONFLICTED in continuity
            or CanonicalFifteenMinuteTechnicalReadReason.CONFLICT_ARTIFACT_PRESENT in reader_reasons
            or CanonicalFifteenMinuteTechnicalReadReason.RECEIPT_CONFLICTED in reader_reasons
        ):
            conflicted += 1; reasons.add(TechnicalRadarReason.CANONICAL_15M_EVIDENCE_CONFLICTED)
        elif read.state is not CanonicalFifteenMinuteTechnicalReadState.READY:
            insufficient += 1; reasons.add(TechnicalRadarReason.CANONICAL_15M_INPUT_INSUFFICIENT)
            if CanonicalFifteenMinuteContinuityState.NO_TRADE_UNMATERIALIZED in continuity:
                no_trade += 1; reasons.add(TechnicalRadarReason.CANONICAL_15M_NO_TRADE_UNMATERIALIZED)
            if CanonicalFifteenMinuteContinuityState.OBSERVATION_GAP_OR_INCOMPLETE in continuity:
                reasons.add(TechnicalRadarReason.CANONICAL_15M_OBSERVATION_GAP_OR_INCOMPLETE)
        elif CanonicalFifteenMinuteContinuityState.CONTINUITY_POLICY_UNSET in continuity:
            insufficient += 1; reasons.add(TechnicalRadarReason.CANONICAL_15M_CONTINUITY_POLICY_UNSET)
        else:
            ready += 1; reasons.add(TechnicalRadarReason.CANONICAL_15M_TECHNICAL_DISCOVERY_POLICY_UNAVAILABLE)
    state = (
        FifteenMinuteTechnicalInputState.EVIDENCE_CONFLICTED if conflicted else
        FifteenMinuteTechnicalInputState.DATA_INSUFFICIENT if insufficient else
        FifteenMinuteTechnicalInputState.INPUT_READY_POLICY_BLOCKED
    )
    return FifteenMinuteTechnicalInputCoverage(state, len(values), ready, insufficient, conflicted, no_trade,
        tuple(sorted(reasons, key=lambda item: item.value)))


def _outcome(security, state, reasons):
    return TechnicalRadarSecurityOutcome(security, state, tuple(sorted(set(reasons), key=lambda item: item.value)), None)


def _security_ids(values, code):
    result = tuple(sorted(values))
    if result != tuple(values) or len(result) != len(set(result)) or not all(_security(value) for value in result):
        raise InternalTechnicalRadarError(code)
    return result


def _security(value) -> bool:
    return isinstance(value, str) and _NSE_SECURITY.fullmatch(value) is not None


def _reasons(values, code):
    result = tuple(sorted(values, key=lambda item: item.value if isinstance(item, TechnicalRadarReason) else ""))
    if result != tuple(values) or len(result) != len(set(result)) or not all(isinstance(item, TechnicalRadarReason) for item in result):
        raise InternalTechnicalRadarError(code)
    return result


def _utc(value, code):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise InternalTechnicalRadarError(code)
    return value.astimezone(UTC)


def _scope_identity(value):
    return {
        "contract": INTERNAL_TECHNICAL_RADAR_CONTRACT,
        "universe_snapshot_id": value.universe_snapshot_id,
        "universe_snapshot_fingerprint": value.universe_snapshot_fingerprint,
        "selected_canonical_security_ids": value.selected_canonical_security_ids,
    }


def _scope_payload(value):
    return _scope_identity(value) | {
        "canonical_eligible_security_ids": value.canonical_eligible_security_ids,
        "provider_exact_ready_security_ids": value.provider_exact_ready_security_ids,
        "blocked_identity_security_ids": value.blocked_identity_security_ids,
        "actual_live_fifteen_minute_security_ids": value.actual_live_fifteen_minute_security_ids,
    }


def _prebreakout_evidence_payload(value):
    return {
        "canonical_security_id": value.canonical_security_id,
        "state": value.state.value,
        "source_as_of": value.source_as_of.isoformat(),
        "opportunity_id": None if value.opportunity is None else value.opportunity.opportunity_id,
        "opportunity_fingerprint": None if value.opportunity is None else value.opportunity.fingerprint,
        "reason_codes": tuple(item.value for item in value.reason_codes),
    }


def _fifteen_coverage_payload(value):
    return {
        "state": value.state.value,
        "supplied_security_count": value.supplied_security_count,
        "ready_security_count": value.ready_security_count,
        "data_insufficient_security_count": value.data_insufficient_security_count,
        "conflicted_security_count": value.conflicted_security_count,
        "no_trade_unmaterialized_security_count": value.no_trade_unmaterialized_security_count,
        "reason_codes": tuple(item.value for item in value.reason_codes),
    }


def _outcome_payload(value):
    return {
        "canonical_security_id": value.canonical_security_id,
        "discovery_state": value.discovery_state.value,
        "reason_codes": tuple(item.value for item in value.reason_codes),
        "lead": None if value.lead is None else discovery_lead_payload(value.lead),
    }


def _run_identity(value):
    return {
        "contract": INTERNAL_TECHNICAL_RADAR_CONTRACT,
        "as_of": value.as_of.isoformat(),
        "scope_id": value.universe_scope.scope_id,
        "policy_id": value.policy_id,
        "policy_version": value.policy_version,
        "policy_fingerprint": value.policy_fingerprint,
        "outcome_identities": tuple((item.canonical_security_id, item.discovery_state.value, None if item.lead is None else item.lead.lead_id) for item in value.outcomes),
    }


def _run_payload(value):
    return _run_identity(value) | {
        "universe_scope": _scope_payload(value.universe_scope) | {"scope_id": value.universe_scope.scope_id, "fingerprint": value.universe_scope.fingerprint},
        "outcomes": tuple(_outcome_payload(item) | {"fingerprint": item.fingerprint} for item in value.outcomes),
        "fifteen_minute_coverage": _fifteen_coverage_payload(value.fifteen_minute_coverage) | {"fingerprint": value.fifteen_minute_coverage.fingerprint},
        "authority": value.authority.value,
        "runtime_state": value.runtime_state.value,
        "live_production_state": value.live_production_state.value,
    }


__all__ = (
    "FifteenMinuteTechnicalInputCoverage", "FifteenMinuteTechnicalInputState",
    "INTERNAL_TECHNICAL_RADAR_CONTRACT", "INTERNAL_TECHNICAL_RADAR_POLICY_FINGERPRINT",
    "INTERNAL_TECHNICAL_RADAR_POLICY_ID", "INTERNAL_TECHNICAL_RADAR_POLICY_VERSION",
    "InternalTechnicalRadarError", "InternalTechnicalRadarRun", "PreBreakoutRadarEvidence",
    "PreBreakoutRadarEvidenceState", "TechnicalRadarAuthority", "TechnicalRadarDiscoveryState",
    "TechnicalRadarLiveProductionState", "TechnicalRadarReason", "TechnicalRadarRuntimeState",
    "TechnicalRadarSecurityOutcome", "TechnicalRadarUniverseScope", "evaluate_internal_technical_radar",
    "internal_technical_radar_payload", "serialize_internal_technical_radar",
)
