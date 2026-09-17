"""P1 lifetime reducer. Explicit canonical cutoffs, never execution authority.

The source reader is a trust boundary: it reads exact immutable references and
their dependency closure from owning stores. It must never synthesize known-at
from an assessment's evaluation time. No production source adapter is installed
by this module. Missing retained availability is a blocked evaluation.
"""
from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum, StrEnum
from hashlib import sha256
import json
import re
from typing import Protocol

from app.historical.security_master import (
    CorporateActionKind, HistoricalCorporateAction, HistoricalSecurityIdentity,
    HistoricalSecurityStatus,
)
from app.intelligence.hsi_signal import StrategyResolutionStatus, serialize_hsi_signal
from app.intelligence.hsi_signal_projection import project_watch_to_hsi_signal
from app.intelligence.hsi_signal_strategy_registry import (
    HSISignalStrategyRegistry, WatchStrategyRoutingContext,
    serialize_strategy_registry_resolution,
)
from app.intelligence.market_wide_watch import MarketWideWatchRecord
from app.intelligence.opportunity_archetypes import OpportunityArchetype
from app.production_v1.canonical_setup_activation import CanonicalSetupOpportunity
from app.strategies.pre_breakout.candidate_assembly import assemble_prebreakout_candidate
from app.strategies.pre_breakout.governance import PreBreakoutPolicyGovernanceService
from app.strategies.pre_breakout.materialization import PreBreakoutResolvedInputStatus
from app.strategies.pre_breakout.policy import (
    PreBreakoutPolicyApproval, PreBreakoutPolicySelection,
)
from app.strategies.pre_breakout.setup_assessment import GovernedPreBreakoutSetupAssessment


CONTRACT = "hsi-signal-lifecycle-p1/v1"
GEOMETRY_FIELDS = (
    "base_start", "base_end", "base_duration", "base_top", "resistance",
    "breakout_confirmation_trigger", "structural_support", "final_structural_stop",
    "measured_move_target", "tick_size",
)
TECHNICAL_FAILURES = {
    "BBW_NOT_COMPRESSED": "bbw_pass", "ATR_NOT_CONTRACTING": "atr_contraction_pass",
    "VOLUME_NOT_DRY": "volume_dry_up_pass", "DELIVERY_NOT_ABOVE_THRESHOLD": "delivery_pass",
    "HIGH_DISTANCE_OUTSIDE_RANGE": "distance_from_high_pass", "RSI_OUTSIDE_RANGE": "rsi_pass",
}
STRUCTURAL_FAILURES = {
    "BASE_STRUCTURE_BROKEN": "BASE_STRUCTURE_BROKEN", "NO_VALID_WINDOW": "NO_VALID_BASE_WINDOW",
}


class State(StrEnum):
    CURRENT = "CURRENT"
    INVALIDATED = "INVALIDATED"
    SUPERSEDED = "SUPERSEDED"


class Outcome(StrEnum):
    ACCEPTED = "ACCEPTED"
    NO_CHANGE = "NO_CHANGE"
    SOURCE_BLOCKED = "SOURCE_BLOCKED"
    POLICY_BLOCKED = "POLICY_BLOCKED"
    CONFLICTED = "CONFLICTED"


class Reason(StrEnum):
    EVIDENCE_KNOWN_AT_UNAVAILABLE = "EVIDENCE_KNOWN_AT_UNAVAILABLE"
    EVIDENCE_CONFLICT = "EVIDENCE_CONFLICT"
    SOURCE_LINEAGE_UNAVAILABLE = "SOURCE_LINEAGE_UNAVAILABLE"
    SOURCE_NOT_ELIGIBLE = "SOURCE_NOT_ELIGIBLE"
    STRATEGY_AUTHORITY_UNAVAILABLE = "STRATEGY_AUTHORITY_UNAVAILABLE"
    SECURITY_NOT_ELIGIBLE = "SECURITY_NOT_ELIGIBLE"
    PREDICATE_NOT_LIFECYCLE_MAPPED = "PREDICATE_NOT_LIFECYCLE_MAPPED"
    REEVALUATION_REQUIRED = "REEVALUATION_REQUIRED"
    OUT_OF_ORDER_REQUIRES_REEVALUATION = "OUT_OF_ORDER_REQUIRES_REEVALUATION"
    CUTOFF_CONFLICT = "CUTOFF_CONFLICT"
    INPUT_CONFLICT = "INPUT_CONFLICT"
    CHAIN_CONFLICT = "CHAIN_CONFLICT"


class LifecycleError(ValueError):
    def __init__(self, reason: Reason, outcome: Outcome = Outcome.CONFLICTED, detail: str | None = None):
        self.reason, self.outcome, self.detail = reason, outcome, detail
        super().__init__(reason.value)


def utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise LifecycleError(Reason.SOURCE_NOT_ELIGIBLE, Outcome.SOURCE_BLOCKED)
    return value.astimezone(UTC)


def _semantic(value):
    if isinstance(value, datetime):
        return utc(value).isoformat(timespec="microseconds")
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise LifecycleError(Reason.EVIDENCE_CONFLICT)
        result = format(value, "f")
        return "0" if value == 0 else result.rstrip("0").rstrip(".") if "." in result else result
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {f.name: _semantic(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, tuple):
        return [_semantic(x) for x in value]
    if isinstance(value, dict):
        return {k: _semantic(v) for k, v in value.items()}
    if value is None or type(value) in (str, int, bool):
        return value
    raise LifecycleError(Reason.EVIDENCE_CONFLICT)


def canonical_json(value) -> str:
    return json.dumps(_semantic(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(prefix: str, **values) -> str:
    return prefix + sha256(canonical_json({"contract": CONTRACT, **values}).encode("utf-8")).hexdigest()


def slot_key(instrument: str) -> str:
    if not isinstance(instrument, str) or not re.fullmatch(r"NSE:[A-Za-z0-9._:-]+", instrument):
        raise LifecycleError(Reason.SECURITY_NOT_ELIGIBLE, Outcome.SOURCE_BLOCKED)
    return digest("hsi-signal-slot:", instrument=instrument, strategy="PRE_BREAKOUT", horizon="HORIZON_UNAVAILABLE")


@dataclass(frozen=True, slots=True)
class SourceReference:
    kind: str
    source_id: str
    fingerprint: str
    canonical_instrument_id: str
    evidence_as_of: datetime
    evidence_known_at: datetime | None
    effective_at: datetime | None = None

    def __post_init__(self):
        if self.kind not in {"WATCH", "ASSESSMENT", "OPPORTUNITY", "CANDIDATE", "APPROVAL",
                             "SELECTION", "SECURITY_IDENTITY", "CORPORATE_ACTION", "DIAGNOSTIC",
                             "EXTERNAL", "EVIDENCE"}:
            raise LifecycleError(Reason.SOURCE_LINEAGE_UNAVAILABLE, Outcome.SOURCE_BLOCKED)
        if not all(isinstance(x, str) and x.strip() == x and x for x in (self.kind, self.source_id)):
            raise LifecycleError(Reason.SOURCE_LINEAGE_UNAVAILABLE, Outcome.SOURCE_BLOCKED)
        if not re.fullmatch(r"(?:sha256:)?[0-9a-f]{64}", self.fingerprint):
            raise LifecycleError(Reason.EVIDENCE_CONFLICT)
        slot_key(self.canonical_instrument_id)
        utc(self.evidence_as_of)
        for name in ("evidence_as_of", "evidence_known_at", "effective_at"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, utc(value))


class CanonicalSourceReader(Protocol):
    """Injected owning-store adapter, NOT caller-supplied timing assertions.

    verify must check the retained fingerprint, native source eligibility and
    known-at ledger at T. dependencies must return the full direct dependency
    set (including price-basis/reference-data checks) for a verified source;
    None means lineage unavailable, () means a verified leaf. No latest lookup.
    """
    def verify(self, reference: SourceReference, *, as_of: datetime) -> bool: ...
    def dependencies(self, reference: SourceReference) -> tuple[SourceReference, ...] | None: ...


@dataclass(frozen=True, slots=True)
class Evaluation:
    canonical_instrument_id: str
    as_of: datetime
    references: tuple[SourceReference, ...]
    identities: tuple[HistoricalSecurityIdentity, ...]
    actions: tuple[HistoricalCorporateAction, ...] = ()
    watch: MarketWideWatchRecord | None = None
    assessments: tuple[GovernedPreBreakoutSetupAssessment, ...] = ()
    opportunity: CanonicalSetupOpportunity | None = None
    approvals: tuple[PreBreakoutPolicyApproval, ...] = ()
    selections: tuple[PreBreakoutPolicySelection, ...] = ()
    p1_json: str | None = None

    def __post_init__(self):
        object.__setattr__(self, "as_of", utc(self.as_of))
        slot_key(self.canonical_instrument_id)
        for name in ("references", "identities", "actions", "assessments", "approvals", "selections"):
            values = getattr(self, name)
            if not isinstance(values, tuple):
                raise LifecycleError(Reason.EVIDENCE_CONFLICT)
            # Exact duplicates coalesce; contradictory same IDs stay visible.
            ordered = {canonical_json(x): x for x in values}
            object.__setattr__(self, name, tuple(ordered[k] for k in sorted(ordered)))
        object.__setattr__(self, "references", tuple(sorted(self.references,
            key=lambda r: (r.kind, r.source_id, r.fingerprint, canonical_json(r)))))


class _RetainedGovernance:
    def __init__(self, value: Evaluation):
        self.value = value

    def get_prebreakout_policy_approval(self, approval_id):
        items = tuple(x for x in self.value.approvals if x.approval_id == approval_id)
        return items[0] if len(items) == 1 else None

    def list_prebreakout_policy_approvals(self, policy_id=None):
        return tuple(x for x in self.value.approvals if policy_id is None or x.policy_id == policy_id)

    def list_prebreakout_policy_selections(self, policy_id=None, context=None):
        return tuple(x for x in self.value.selections if (policy_id is None or x.policy_id == policy_id)
                     and (context is None or x.selection_context == context))


@dataclass(frozen=True, slots=True)
class Qualification:
    request_kind: str
    input_key: str
    setup_key: str | None
    provenance_key: str | None
    registry_json: str | None
    known_at: datetime
    cessation_effective_at: datetime | None = None


def _reference(value: Evaluation, kind: str, source_id: str, fingerprint: str) -> SourceReference:
    matches = tuple(x for x in value.references if (x.kind, x.source_id) == (kind, source_id))
    if not matches:
        if kind in ("ASSESSMENT", "WATCH", "CANDIDATE", "OPPORTUNITY") and any(x.kind == kind for x in value.references):
            raise LifecycleError(Reason.EVIDENCE_CONFLICT)
        raise LifecycleError(Reason.SOURCE_LINEAGE_UNAVAILABLE, Outcome.SOURCE_BLOCKED)
    if len(matches) != 1 or matches[0].fingerprint != fingerprint:
        raise LifecycleError(Reason.EVIDENCE_CONFLICT)
    return matches[0]


def verify_source_closure(value: Evaluation, reader: CanonicalSourceReader) -> None:
    """Validate full closure before an accepted write, including exact retries."""
    dependencies = {}
    errors = []
    for ref in value.references:
        if ref.evidence_known_at is None:
            errors.append(LifecycleError(Reason.EVIDENCE_KNOWN_AT_UNAVAILABLE, Outcome.SOURCE_BLOCKED))
        if reader.verify(ref, as_of=value.as_of) is not True:
            errors.append(LifecycleError(Reason.SOURCE_NOT_ELIGIBLE, Outcome.SOURCE_BLOCKED))
        children = reader.dependencies(ref)
        if not isinstance(children, tuple) or any(child not in value.references for child in children):
            errors.append(LifecycleError(Reason.SOURCE_LINEAGE_UNAVAILABLE, Outcome.SOURCE_BLOCKED))
            continue
        if ref.kind in ("WATCH", "ASSESSMENT") and not children:
            errors.append(LifecycleError(Reason.SOURCE_LINEAGE_UNAVAILABLE, Outcome.SOURCE_BLOCKED))
        dependencies[ref] = children
    visiting, complete = set(), set()
    def visit(ref):
        if ref in visiting:
            raise LifecycleError(Reason.EVIDENCE_CONFLICT)
        if ref in complete:
            return
        visiting.add(ref)
        for child in dependencies.get(ref, ()):
            visit(child)
        visiting.remove(ref)
        complete.add(ref)
    for ref in value.references:
        visit(ref)
    if errors:
        raise _primary_error(errors)


def _primary_error(errors):
    """LC-11 category priority; finite-code tie break, never source/hash order."""
    priority = {Outcome.CONFLICTED: 0, Outcome.POLICY_BLOCKED: 1, Outcome.SOURCE_BLOCKED: 2}
    return min(errors, key=lambda e: (priority[e.outcome], e.reason.value, e.detail or ""))


def _verify_assessment_timestamps(value, T):
    if isinstance(value, datetime):
        if utc(value) > T:
            raise LifecycleError(Reason.SOURCE_NOT_ELIGIBLE, Outcome.SOURCE_BLOCKED)
    elif is_dataclass(value):
        for f in fields(value):
            _verify_assessment_timestamps(getattr(value, f.name), T)
    elif isinstance(value, tuple):
        for item in value:
            _verify_assessment_timestamps(item, T)


def _negative_selection(value, reader):
    """Native selected-policy lookup; no fabricated CURRENT_VALID_SETUP route."""
    selections = reader.list_prebreakout_policy_selections()
    eligible = tuple(s for s in selections if s.effective_from <= value.as_of and s.selected_at <= value.as_of)
    if not eligible:
        raise LifecycleError(Reason.STRATEGY_AUTHORITY_UNAVAILABLE, Outcome.POLICY_BLOCKED)
    if len({s.selection_id for s in selections}) != len(selections):
        raise LifecycleError(Reason.EVIDENCE_CONFLICT)
    latest = max(s.effective_from for s in eligible)
    provenance = {(s.approval_id, s.policy_id, s.policy_version, s.policy_fingerprint)
                  for s in eligible if s.effective_from == latest}
    if len(provenance) != 1:
        raise LifecycleError(Reason.EVIDENCE_CONFLICT)
    from app.strategies.pre_breakout.policy import PreBreakoutPolicySelectionContext
    view = PreBreakoutPolicyGovernanceService(reader).get_selected_prebreakout_policy(
        context=PreBreakoutPolicySelectionContext.CURRENT_STORED_SCAN, as_of=value.as_of)
    if view is None or view.approval.created_at > value.as_of or view.approval.reviewed_at > value.as_of:
        raise LifecycleError(Reason.STRATEGY_AUTHORITY_UNAVAILABLE, Outcome.POLICY_BLOCKED)
    return view.selection


def qualify(value: Evaluation) -> Qualification:
    """Revalidate retained native objects; no recalculation or hash repair."""
    T, instrument = value.as_of, value.canonical_instrument_id
    if not value.references:
        raise LifecycleError(Reason.SOURCE_LINEAGE_UNAVAILABLE, Outcome.SOURCE_BLOCKED)
    ids = [(r.kind, r.source_id) for r in value.references]
    if len(ids) != len(set(ids)) or len(value.assessments) > 1:
        raise LifecycleError(Reason.EVIDENCE_CONFLICT)
    source_errors = []
    def reference(kind, source_id, fingerprint):
        # Retain unavailable linkage while inspecting the other supplied native
        # objects. Absence must not hide a policy blocker or contradictory fact.
        try:
            return _reference(value, kind, source_id, fingerprint)
        except LifecycleError as error:
            if error.outcome is not Outcome.SOURCE_BLOCKED:
                raise
            source_errors.append(error)
            return None

    for ref in value.references:
        ref.__post_init__()
        if ref.canonical_instrument_id != instrument:
            raise LifecycleError(Reason.EVIDENCE_CONFLICT)
        if ref.evidence_known_at is None:
            source_errors.append(LifecycleError(Reason.EVIDENCE_KNOWN_AT_UNAVAILABLE, Outcome.SOURCE_BLOCKED))
        if any(x is not None and x > T for x in (ref.evidence_as_of, ref.evidence_known_at, ref.effective_at)):
            source_errors.append(LifecycleError(Reason.SOURCE_NOT_ELIGIBLE, Outcome.SOURCE_BLOCKED))
    endings = []
    eligible = []
    for identity in value.identities:
        # HistoricalSecurityMasterStore retains this exact native hash.
        ref = reference("SECURITY_IDENTITY", identity.identity_id, sha256(repr(identity).encode()).hexdigest())
        if identity.canonical_instrument_id != instrument:
            raise LifecycleError(Reason.EVIDENCE_CONFLICT)
        if not identity.eligible_as_of(T):
            source_errors.append(LifecycleError(Reason.SECURITY_NOT_ELIGIBLE, Outcome.SOURCE_BLOCKED))
        if ref is not None and (ref.effective_at != identity.symbol_effective_from or ref.evidence_as_of != identity.as_of):
            raise LifecycleError(Reason.EVIDENCE_CONFLICT)
        eligible.append(identity)
        if identity.status in (HistoricalSecurityStatus.DELISTED, HistoricalSecurityStatus.MERGED):
            endings.append(identity.symbol_effective_from)
    for action in value.actions:
        ref = reference("CORPORATE_ACTION", action.action_id, sha256(repr(action).encode()).hexdigest())
        if action.canonical_instrument_id != instrument:
            raise LifecycleError(Reason.EVIDENCE_CONFLICT)
        if not action.eligible_as_of(T):
            source_errors.append(LifecycleError(Reason.SECURITY_NOT_ELIGIBLE, Outcome.SOURCE_BLOCKED))
        if ref is not None and (ref.effective_at != action.effective_date or ref.evidence_as_of != action.as_of):
            raise LifecycleError(Reason.EVIDENCE_CONFLICT)
        if action.kind in (CorporateActionKind.DELISTING, CorporateActionKind.MERGER):
            endings.append(action.effective_date)
    if len(eligible) > 1:
        raise LifecycleError(Reason.EVIDENCE_CONFLICT)
    # Validate all supplied positive/negative objects even on cessation.
    assessment = value.assessments[0] if value.assessments else None
    if assessment is not None:
        reference("ASSESSMENT", assessment.assessment_id, assessment.fingerprint)
        if assessment.instrument_id != instrument or assessment.evaluation_as_of != T:
            raise LifecycleError(Reason.EVIDENCE_CONFLICT)
        try:
            _verify_assessment_timestamps(assessment, T)
        except LifecycleError as error:
            source_errors.append(error)
    for item in value.approvals:
        item.__post_init__()
        ref = reference("APPROVAL", item.approval_id, item.fingerprint)
        if ref is not None and ref.evidence_as_of != item.created_at:
            raise LifecycleError(Reason.EVIDENCE_CONFLICT)
    for item in value.selections:
        item.__post_init__()
        ref = reference("SELECTION", item.selection_id, item.fingerprint)
        if ref is not None and (ref.evidence_as_of != item.selected_at or ref.effective_at != item.effective_from):
            raise LifecycleError(Reason.EVIDENCE_CONFLICT)
    if value.watch is not None:
        value.watch.verify()
        reference("WATCH", value.watch.watch_id, value.watch.fingerprint)
        if value.watch.canonical_instrument_id != instrument or value.watch.watch_as_of != T:
            raise LifecycleError(Reason.EVIDENCE_CONFLICT)
        if value.watch.last_evidence_as_of is not None and utc(value.watch.last_evidence_as_of) > T:
            source_errors.append(LifecycleError(Reason.SOURCE_NOT_ELIGIBLE, Outcome.SOURCE_BLOCKED))
        for item in value.watch.evidence_references:
            reference("DIAGNOSTIC", item.artifact_id, item.artifact_fingerprint)
        for item in value.watch.external_evidence_references:
            reference("EXTERNAL", item.evidence_version_id, item.evidence_fingerprint)
    if value.opportunity is not None:
        value.opportunity.__post_init__()
        value.opportunity.candidate.__post_init__()
        reference("OPPORTUNITY", value.opportunity.opportunity_id, value.opportunity.fingerprint)
        reference("CANDIDATE", value.opportunity.candidate.candidate_id, value.opportunity.candidate.fingerprint)
        if assessment is None or CanonicalSetupOpportunity.from_assessment(assessment) != value.opportunity:
            raise LifecycleError(Reason.EVIDENCE_CONFLICT)
    reader = _RetainedGovernance(value)
    registry = HSISignalStrategyRegistry(reader)
    # P1 decoding is deliberately its native projector, never a generic
    # dataclass decoder that could pass derived init=False fields through.
    signal = None
    if value.p1_json is not None:
        if value.watch is None or value.opportunity is None:
            raise LifecycleError(Reason.SOURCE_LINEAGE_UNAVAILABLE, Outcome.SOURCE_BLOCKED)
        signal = project_watch_to_hsi_signal(watch=value.watch, archetype=OpportunityArchetype.PRE_BREAKOUT, registry=registry)
        if serialize_hsi_signal(signal) != value.p1_json:
            raise LifecycleError(Reason.EVIDENCE_CONFLICT)
        if signal.horizon is not None or signal.expires_at is not None:
            source_errors.append(LifecycleError(Reason.SOURCE_NOT_ELIGIBLE, Outcome.SOURCE_BLOCKED))
    if endings:
        kind, setup, provenance, resolution_json = "SECURITY_CESSATION", None, None, None
    else:
        if len(eligible) != 1 or eligible[0].status not in (HistoricalSecurityStatus.ACTIVE, HistoricalSecurityStatus.RELISTED):
            source_errors.append(LifecycleError(Reason.SECURITY_NOT_ELIGIBLE, Outcome.SOURCE_BLOCKED))
        if assessment is None:
            raise LifecycleError(Reason.SOURCE_LINEAGE_UNAVAILABLE, Outcome.SOURCE_BLOCKED)
        if assessment.candidate_formation_eligible:
            if value.watch is None:
                raise LifecycleError(Reason.SOURCE_LINEAGE_UNAVAILABLE, Outcome.SOURCE_BLOCKED)
            context = WatchStrategyRoutingContext(
                instrument, value.watch.watch_id, value.watch.fingerprint, T,
                OpportunityArchetype.PRE_BREAKOUT, value.watch.archetypes,
                value.watch.setup_state, value.watch.setup_policy_routes,
            )
            resolution = registry.resolve(context)
            if resolution.resolution.status is not StrategyResolutionStatus.RESOLVED:
                raise LifecycleError(Reason.STRATEGY_AUTHORITY_UNAVAILABLE, Outcome.POLICY_BLOCKED,
                                     resolution.reason_code.value if resolution.reason_code else None)
            selected = next(x for x in value.selections if x.selection_id == resolution.resolution.selection_id)
            resolution_json = serialize_strategy_registry_resolution(resolution)
        else:
            selected = _negative_selection(value, reader)
            resolution_json = None
        approved = reader.get_prebreakout_policy_approval(selected.approval_id)
        reference("SELECTION", selected.selection_id, selected.fingerprint)
        reference("APPROVAL", approved.approval_id, approved.fingerprint)
        view = PreBreakoutPolicyGovernanceService(reader).validate_selection(selected)
        if view.unresolved_fields:
            raise LifecycleError(Reason.STRATEGY_AUTHORITY_UNAVAILABLE, Outcome.POLICY_BLOCKED)
        expected = (selected.policy_id, selected.policy_version, selected.policy_fingerprint,
                    selected.selection_id, selected.fingerprint)
        for native in (assessment, assessment.technical_inputs, assessment.structural):
            actual = tuple(getattr(native, name) for name in
                           ("policy_id", "policy_version", "policy_fingerprint", "selection_id", "selection_fingerprint"))
            if actual != expected or native.instrument_id != instrument or native.evaluation_as_of != T:
                raise LifecycleError(Reason.EVIDENCE_CONFLICT)
        if (assessment.technical_inputs.unresolved_fields
                or assessment.technical_inputs.status in (PreBreakoutResolvedInputStatus.DATA_UNAVAILABLE,
                                                          PreBreakoutResolvedInputStatus.GOVERNANCE_UNAVAILABLE)
                or assessment.technical_inputs.blockers
                or any(getattr(assessment.technical_inputs, field) is None for field in TECHNICAL_FAILURES.values())
                or any(x.category.value in ("DATA_BLOCKER", "GOVERNANCE_BLOCKER") for x in assessment.blockers)
                or assessment.structural.policy_semantic_conflict):
            raise LifecycleError(Reason.SOURCE_NOT_ELIGIBLE, Outcome.SOURCE_BLOCKED)
        provenance = digest("hsi-signal-provenance:", registry=registry.registry_identity,
                            policy=expected[:3], approval=(approved.approval_id, approved.fingerprint),
                            selection=(selected.selection_id, selected.fingerprint))
        if assessment.candidate_formation_eligible:
            if value.watch is None or value.opportunity is None or value.p1_json is None:
                raise LifecycleError(Reason.SOURCE_LINEAGE_UNAVAILABLE, Outcome.SOURCE_BLOCKED)
            if signal is None or signal.strategy_resolution != resolution.resolution:
                raise LifecycleError(Reason.EVIDENCE_CONFLICT)
            candidate = assemble_prebreakout_candidate(assessment)
            if any(getattr(assessment.technical_inputs, field) is not True for field in TECHNICAL_FAILURES.values()):
                raise LifecycleError(Reason.EVIDENCE_CONFLICT)
            setup = digest("hsi-setup-instance:", instrument=instrument, strategy="PRE_BREAKOUT",
                           geometry={name: getattr(candidate, name) for name in GEOMETRY_FIELDS})
            kind = "POSITIVE_ASSESSMENT"
        else:
            if value.opportunity is not None or value.p1_json is not None:
                raise LifecycleError(Reason.EVIDENCE_CONFLICT)
            matched = False
            for blocker in assessment.blockers:
                if blocker.category.value == "TECHNICAL_SETUP_FAIL" and blocker.code in TECHNICAL_FAILURES:
                    matched |= (assessment.status.value == "BLOCKED_TECHNICAL_SETUP"
                                and getattr(assessment.technical_inputs, TECHNICAL_FAILURES[blocker.code]) is False)
                if blocker.category.value == "STRUCTURAL_SETUP_FAIL" and blocker.code in STRUCTURAL_FAILURES:
                    matched |= (assessment.status.value == "BLOCKED_STRUCTURAL_SETUP"
                                and assessment.structural.status.value == STRUCTURAL_FAILURES[blocker.code])
            if not matched:
                raise LifecycleError(Reason.PREDICATE_NOT_LIFECYCLE_MAPPED, Outcome.SOURCE_BLOCKED)
            kind, setup = "NEGATIVE_ASSESSMENT", None
    if source_errors:
        raise _primary_error(source_errors)
    key = digest("hsi-signal-lifecycle-input:", slot=slot_key(instrument), T=T,
                 request_kind=kind, evaluation=value, registry=resolution_json)
    return Qualification(kind, key, setup, provenance, resolution_json,
                         max(r.evidence_known_at for r in value.references),
                         max(endings) if endings else None)


@dataclass(frozen=True, slots=True)
class Transition:
    lifetime_id: str
    prior_state: State | None
    next_state: State
    reason_code: str
    transition_as_of: datetime
    known_at: datetime
    setup_key: str
    provenance_key: str
    origin_input_key: str
    initial_as_of: datetime
    previous_transition_id: str | None
    previous_transition_fingerprint: str | None
    predecessor_terminal_id: str | None
    replacement_lifetime_id: str | None
    transition_id: str
    fingerprint: str


@dataclass(frozen=True, slots=True)
class Batch:
    contract: str
    slot_key: str
    input_key: str
    prior_batch_id: str | None
    prior_batch_fingerprint: str | None
    evaluation: Evaluation
    qualification: Qualification
    transitions: tuple[Transition, ...]
    batch_id: str
    fingerprint: str


@dataclass(frozen=True, slots=True)
class Result:
    outcome: Outcome
    reason: Reason | None
    batch: Batch | None
    detail: str | None = None
    actionability: str = "WATCH_ONLY"
    execution_status: str = "NON_EXECUTABLE"

    def __post_init__(self):
        if self.actionability != "WATCH_ONLY" or self.execution_status != "NON_EXECUTABLE":
            raise LifecycleError(Reason.EVIDENCE_CONFLICT)
        accepted = self.outcome in (Outcome.ACCEPTED, Outcome.NO_CHANGE)
        if accepted != (self.batch is not None) or accepted != (self.reason is None):
            raise LifecycleError(Reason.EVIDENCE_CONFLICT)


def _transition(value, qualification, *, lifetime, previous, state, reason, origin=None,
                predecessor=None, replacement=None):
    origin = origin or previous
    prior_state = previous.next_state if previous else None
    identity = digest("hsi-signal-lifecycle-transition:", slot=slot_key(value.canonical_instrument_id),
                      lifetime=lifetime, prior_transition=previous.transition_id if previous else None,
                      T=value.as_of, prior_state=prior_state, next_state=state, reason=reason,
                      input_key=qualification.input_key)
    values = dict(lifetime_id=lifetime, prior_state=prior_state, next_state=state, reason_code=reason,
                  transition_as_of=value.as_of, known_at=qualification.known_at,
                  setup_key=origin.setup_key if origin else qualification.setup_key,
                  provenance_key=origin.provenance_key if origin else qualification.provenance_key,
                  origin_input_key=origin.origin_input_key if origin else qualification.input_key,
                  initial_as_of=origin.initial_as_of if origin else value.as_of,
                  previous_transition_id=previous.transition_id if previous else None,
                  previous_transition_fingerprint=previous.fingerprint if previous else None,
                  predecessor_terminal_id=predecessor, replacement_lifetime_id=replacement,
                  transition_id=identity)
    return Transition(**values, fingerprint=digest("sha256:", **values))


def _make_batch(value: Evaluation, q: Qualification, prior: Batch | None) -> Batch:
    last = prior.transitions[-1] if prior else None
    current = last if last and last.next_state is State.CURRENT else None
    events = []
    if q.request_kind == "POSITIVE_ASSESSMENT":
        if current and (current.setup_key, current.provenance_key) == (q.setup_key, q.provenance_key):
            events.append(_transition(value, q, lifetime=current.lifetime_id, previous=current,
                                      state=State.CURRENT, reason="SETUP_CONTINUED"))
        else:
            terminal = last
            if current:
                terminal = _transition(value, q, lifetime=current.lifetime_id, previous=current,
                                       state=State.SUPERSEDED, reason="REPLACED_BY_QUALIFYING_SETUP")
            predecessor = terminal.transition_id if terminal else None
            p1 = json.loads(value.p1_json)
            lifetime = digest("hsi-signal-lifetime:", slot=slot_key(value.canonical_instrument_id),
                              setup=q.setup_key, provenance=q.provenance_key,
                              observation=(p1["signal_id"], p1["fingerprint"]), initial_T=value.as_of,
                              predecessor_terminal=predecessor)
            if current:
                values = {f.name: getattr(terminal, f.name) for f in fields(terminal) if f.name != "fingerprint"}
                values["replacement_lifetime_id"] = lifetime
                terminal = Transition(**values, fingerprint=digest("sha256:", **values))
                events.append(terminal)
            events.append(_transition(value, q, lifetime=lifetime, previous=None, state=State.CURRENT,
                                      reason="INITIAL_QUALIFICATION", predecessor=predecessor))
    else:
        if current is None:
            raise LifecycleError(Reason.SOURCE_NOT_ELIGIBLE, Outcome.SOURCE_BLOCKED)
        if q.request_kind == "NEGATIVE_ASSESSMENT" and q.provenance_key != current.provenance_key:
            raise LifecycleError(Reason.STRATEGY_AUTHORITY_UNAVAILABLE, Outcome.POLICY_BLOCKED)
        if q.request_kind == "SECURITY_CESSATION" and q.cessation_effective_at < current.initial_as_of:
            raise LifecycleError(Reason.SECURITY_NOT_ELIGIBLE, Outcome.SOURCE_BLOCKED)
        events.append(_transition(value, q, lifetime=current.lifetime_id, previous=current,
                                  state=State.INVALIDATED, reason="SECURITY_LIFECYCLE_ENDED"
                                  if q.request_kind == "SECURITY_CESSATION" else "SETUP_PREDICATE_FAILED"))
    values = dict(contract=CONTRACT, slot_key=slot_key(value.canonical_instrument_id), input_key=q.input_key,
                  prior_batch_id=prior.batch_id if prior else None,
                  prior_batch_fingerprint=prior.fingerprint if prior else None,
                  evaluation=value, qualification=q, transitions=tuple(events))
    return Batch(**values, batch_id=digest("hsi-signal-lifecycle-batch:", **values),
                 fingerprint=digest("sha256:", **values))


def verify_chain(chain: tuple[Batch, ...]) -> None:
    prior = None
    for batch in chain:
        if prior and (batch.slot_key != prior.slot_key or batch.evaluation.as_of <= prior.evaluation.as_of):
            raise LifecycleError(Reason.CHAIN_CONFLICT)
        if _make_batch(batch.evaluation, qualify(batch.evaluation), prior) != batch:
            raise LifecycleError(Reason.CHAIN_CONFLICT)
        prior = batch


def evaluate(value: Evaluation, chain: tuple[Batch, ...], reader: CanonicalSourceReader) -> Result:
    try:
        verify_chain(chain)
        errors = []
        q = None
        for validation in (lambda: qualify(value), lambda: verify_source_closure(value, reader)):
            try:
                result = validation()
                if isinstance(result, Qualification):
                    q = result
            except LifecycleError as error:
                errors.append(error)
            except (ValueError, TypeError, AttributeError, KeyError):
                errors.append(LifecycleError(Reason.EVIDENCE_CONFLICT))
            except OSError:
                errors.append(LifecycleError(Reason.SOURCE_NOT_ELIGIBLE, Outcome.SOURCE_BLOCKED))
        if errors:
            raise _primary_error(errors)
        if chain and chain[-1].slot_key != slot_key(value.canonical_instrument_id):
            raise LifecycleError(Reason.CHAIN_CONFLICT)
        for batch in chain:
            if batch.input_key == q.input_key:
                if canonical_json(batch.evaluation) != canonical_json(value):
                    raise LifecycleError(Reason.INPUT_CONFLICT)
                return Result(Outcome.NO_CHANGE, None, batch)
        if chain and value.as_of <= chain[-1].evaluation.as_of:
            reason = Reason.CUTOFF_CONFLICT if value.as_of == chain[-1].evaluation.as_of else Reason.OUT_OF_ORDER_REQUIRES_REEVALUATION
            return Result(Outcome.CONFLICTED, reason, None)
        return Result(Outcome.ACCEPTED, None, _make_batch(value, q, chain[-1] if chain else None))
    except LifecycleError as error:
        return Result(error.outcome, error.reason, None, error.detail)
    except (ValueError, TypeError, AttributeError, KeyError):
        return Result(Outcome.CONFLICTED, Reason.EVIDENCE_CONFLICT, None)
    except OSError:
        return Result(Outcome.SOURCE_BLOCKED, Reason.SOURCE_NOT_ELIGIBLE, None)


@dataclass(frozen=True, slots=True)
class View:
    as_of: datetime
    last_transition: Transition | None
    transition_ids: tuple[str, ...]
    outcome: Outcome
    reason: Reason | None
    slot_key: str | None = None
    observation_references: tuple[tuple[str, str], ...] = ()
    actionability: str = "WATCH_ONLY"
    execution_status: str = "NON_EXECUTABLE"
    expiry: str = "EXPIRY_NOT_GOVERNED_FOR_THIS_PATH"

    def __post_init__(self):
        if (self.actionability, self.execution_status, self.expiry) != (
            "WATCH_ONLY", "NON_EXECUTABLE", "EXPIRY_NOT_GOVERNED_FOR_THIS_PATH"
        ):
            raise LifecycleError(Reason.EVIDENCE_CONFLICT)


def replay(chain: tuple[Batch, ...], *, as_of: datetime) -> View:
    Q = utc(as_of)
    # A historical query never evaluates newer Watch/setup/policy payloads.
    chain = tuple(b for b in chain if b.evaluation.as_of <= Q)
    try:
        verify_chain(chain)
    except (LifecycleError, ValueError, TypeError, AttributeError):
        return View(Q, None, (), Outcome.CONFLICTED, Reason.CHAIN_CONFLICT)
    events = tuple(t for b in chain if b.evaluation.as_of <= Q for t in b.transitions if t.known_at <= Q)
    visible = tuple(b for b in chain if b.evaluation.as_of <= Q and b.qualification.known_at <= Q)
    observations = tuple((p["signal_id"], p["fingerprint"]) for b in visible
                         if b.evaluation.p1_json is not None for p in (json.loads(b.evaluation.p1_json),))
    last = events[-1] if events else None
    stale = last is None or (last.next_state is State.CURRENT and last.transition_as_of < Q)
    return View(Q, last, tuple(t.transition_id for t in events),
                Outcome.SOURCE_BLOCKED if stale else Outcome.ACCEPTED,
                Reason.REEVALUATION_REQUIRED if stale else None,
                visible[-1].slot_key if visible else None, observations)
