"""Selected-security, stored-only projection of the governed Pre-Breakout setup.

No materializer, candidate builder, score or gate engine is invoked here.
Native repository decoders verify immutable stored payload fingerprints.
"""
from dataclasses import fields, is_dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.api.schemas.agent_tools import CanonicalSecurity, ToolEnvelope
from app.intelligence.decision_score_evidence import CanonicalDecisionScorecardSource, DecisionScoreEvidenceAdapter
from app.intelligence.six_gates_evidence import CanonicalSixGatesEvaluationSource, SixGatesEvidenceAdapter
from app.strategies.pre_breakout.governance import PreBreakoutPolicyGovernanceService


Readiness = Literal["READY", "PARTIAL", "BLOCKED", "NOT_APPLICABLE"]


class SetupComponent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    component: str
    status: Readiness
    blockers: tuple[str, ...] = ()


class StoredContextReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    status: Readiness
    artifact_id: str | None = None
    fingerprint: str | None = None
    source_availability: str | None = None
    source_as_of: datetime | None = None
    available_at: datetime | None = None
    freshness: str | None = None
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


class SetupResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    canonical_security_id: CanonicalSecurity
    requested_as_of: datetime
    assessment_id: str
    assessment_fingerprint: str
    source_as_of: datetime
    evaluation_session: datetime | None
    setup_state: str
    candidate_formation_eligible: bool
    technical_state: str
    structural_state: str
    policy_id: str
    policy_version: str
    policy_fingerprint: str
    selection_id: str
    selection_fingerprint: str
    approval_id: str
    approval_fingerprint: str
    freshness: Literal["UNKNOWN"] = "UNKNOWN"
    temporal_scope: Literal["STORED_ASSESSMENT_ONLY"] = "STORED_ASSESSMENT_ONLY"
    entry_reference_price: Decimal | None
    entry_reference_session: datetime | None
    maximum_acceptable_entry_price: Decimal | None
    maximum_executable_entry_price: Decimal | None
    breakout_confirmation_trigger: Decimal | None
    breakout_trigger_role: str | None
    structural_support: Decimal | None
    support_breached: bool | None
    structural_stop: Decimal | None
    target_1: Decimal | None
    target_2: None = None
    extended_target: None = None
    exact_invalidation: None = None
    horizon: None = None
    entry_risk: Decimal | None
    entry_reward: Decimal | None
    entry_rr: Decimal | None
    entry_rr_pass: bool | None
    entry_economics_status: str | None
    actual_execution_status: str | None
    official_delivery_pct: Decimal | None
    delivery_pass: bool | None
    components: tuple[SetupComponent, ...]
    decision_score: StoredContextReference
    six_gates: StoredContextReference
    execution_gate_v2: Literal["NOT_ACTIVE"] = "NOT_ACTIVE"


def _times_at_or_before(value, cutoff: datetime) -> bool:
    """All native nested sessions/confirmations must satisfy the source cutoff."""
    if isinstance(value, datetime):
        return value.utcoffset() is not None and value <= cutoff
    if is_dataclass(value):
        return all(_times_at_or_before(getattr(value, f.name), cutoff) for f in fields(value))
    if isinstance(value, tuple):
        return all(_times_at_or_before(item, cutoff) for item in value)
    return True


def _governance(repository, assessment):
    selection = repository.get_prebreakout_policy_selection(assessment.selection_id)
    if selection is None:
        raise ValueError("SETUP_SELECTION_MISSING")
    # Reuse approval reconstruction, fingerprints and canonical selection rules.
    view = PreBreakoutPolicyGovernanceService(repository).validate_selection(selection)
    at = assessment.evaluation_as_of
    if not all(_times_at_or_before(t, at) for t in (
        selection.selected_at, selection.effective_from, view.approval.reviewed_at, view.approval.created_at,
    )):
        raise ValueError("SETUP_GOVERNANCE_FUTURE")
    expected = (selection.policy_id, selection.policy_version, view.policy_fingerprint,
                selection.selection_id, view.selection_fingerprint)
    for part in (assessment, assessment.technical_inputs, assessment.structural):
        if (part.instrument_id != assessment.instrument_id or part.evaluation_as_of != at
                or (part.policy_id, part.policy_version, part.policy_fingerprint,
                    part.selection_id, part.selection_fingerprint) != expected):
            raise ValueError("SETUP_LINEAGE_MISMATCH")
    return view


def _context(repository, security: str, cutoff: datetime, *, gates: bool) -> StoredContextReference:
    name = "SIX_GATES" if gates else "DECISION_SCORE"
    try:
        adapter = (SixGatesEvidenceAdapter(CanonicalSixGatesEvaluationSource(repository)) if gates
                   else DecisionScoreEvidenceAdapter(CanonicalDecisionScorecardSource(repository)))
        artifact, = adapter.artifacts(security, as_of=cutoff)
        if (artifact.canonical_instrument_id != security
                or not _times_at_or_before(artifact, cutoff)
                or artifact.availability.value not in {"AVAILABLE", "PARTIAL"}):
            return StoredContextReference(status="BLOCKED", blockers=(name + "_NOT_AVAILABLE_AT_CUTOFF",),
                warnings=artifact.warnings)
        # Reference only: neither stock-level scores nor context-specific gates
        # establish compatibility with this setup or authorize any action.
        return StoredContextReference(status="PARTIAL", artifact_id=artifact.artifact_id,
            fingerprint=artifact.artifact_fingerprint, source_availability=artifact.availability.value,
            source_as_of=artifact.evidence_as_of, available_at=artifact.available_at,
            freshness=artifact.freshness_status.value, blockers=(name + "_NOT_BOUND_TO_SETUP_CONTEXT",),
            warnings=artifact.warnings)
    except Exception:
        return StoredContextReference(status="BLOCKED", blockers=(name + "_STORED_LINEAGE_UNAVAILABLE",))


def setup_response(repository, canonical_security_id: str, *, as_of: datetime) -> ToolEnvelope[SetupResponse]:
    """Read one latest native assessment; never substitute an older invalid result."""
    cutoff = as_of.astimezone(UTC)
    if repository is None:
        return ToolEnvelope(status="BLOCKED", as_of=cutoff, blockers=("SETUP_READ_REPOSITORY_UNAVAILABLE",))
    try:
        values = repository.list_prebreakout_setup_assessments(canonical_instrument_id=canonical_security_id)
        eligible = [v for v in values if v.instrument_id == canonical_security_id and v.evaluation_as_of <= cutoff]
        if not eligible:
            return ToolEnvelope(status="BLOCKED", as_of=cutoff, blockers=("SETUP_ASSESSMENT_NOT_AVAILABLE_AT_CUTOFF",))
        latest_at = max(v.evaluation_as_of for v in eligible)
        latest = {v.assessment_id: v for v in eligible if v.evaluation_as_of == latest_at}
        if len(latest) != 1:
            return ToolEnvelope(status="BLOCKED", as_of=cutoff, blockers=("SETUP_ASSESSMENT_AMBIGUOUS",))
        value, = latest.values()
        if not _times_at_or_before(value, latest_at):
            return ToolEnvelope(status="BLOCKED", as_of=cutoff, blockers=("SETUP_SOURCE_TIME_INVALID",))
        governance = _governance(repository, value)
        s, t = value.structural, value.technical_inputs
        component_values = (
            ("entry_reference", s.entry_reference_price), ("confirmation_trigger", s.breakout_confirmation_trigger),
            ("structural_support", s.structural_support), ("stop", s.final_stop), ("T1", s.target),
            ("entry_rr", s.entry_reference_rr),
        )
        components = tuple(SetupComponent(component=name, status="READY" if field is not None else "BLOCKED",
            blockers=() if field is not None else ("CANONICAL_FIELD_UNAVAILABLE",)) for name, field in component_values)
        components += tuple(SetupComponent(component=name, status="BLOCKED", blockers=(reason,)) for name, reason in (
            ("T2", "T2_NOT_GOVERNED_IN_ASSESSMENT"), ("extended_target", "EXTENDED_TARGET_NOT_GOVERNED_IN_ASSESSMENT"),
            ("horizon", "SETUP_HORIZON_NOT_GOVERNED"), ("exact_invalidation", "EXACT_INVALIDATION_TEXT_NOT_STORED"),
        ))
        components += (SetupComponent(component="liquidity", status="PARTIAL" if t.official_delivery_pct is not None else "BLOCKED",
            blockers=("DELIVERY_IS_NOT_FULL_LIQUIDITY_OR_GATE3_PROOF",)),)
        refs = [value.assessment_id, governance.selection.selection_id, governance.approval.approval_id]
        if s.tick_record_id:
            refs.append(s.tick_record_id)
        if s.selected_base:
            refs.extend(p.bar_id for p in (*s.selected_base.pivot_highs, *s.selected_base.pivot_lows))
        data = SetupResponse(canonical_security_id=canonical_security_id, requested_as_of=cutoff,
            assessment_id=value.assessment_id, assessment_fingerprint=value.fingerprint,
            source_as_of=value.evaluation_as_of, evaluation_session=value.evaluation_session,
            setup_state=value.status.value, candidate_formation_eligible=value.candidate_formation_eligible,
            technical_state=t.status.value, structural_state=s.status.value, policy_id=value.policy_id, policy_version=value.policy_version,
            policy_fingerprint=value.policy_fingerprint, selection_id=value.selection_id,
            selection_fingerprint=value.selection_fingerprint, approval_id=governance.approval.approval_id,
            approval_fingerprint=governance.approval_fingerprint,
            entry_reference_price=s.entry_reference_price, entry_reference_session=s.entry_reference_session,
            maximum_acceptable_entry_price=s.maximum_acceptable_entry_price,
            maximum_executable_entry_price=s.maximum_executable_entry_price,
            breakout_confirmation_trigger=s.breakout_confirmation_trigger, breakout_trigger_role=s.breakout_trigger_role,
            structural_support=s.structural_support, support_breached=s.support_breached, structural_stop=s.final_stop,
            target_1=s.target, entry_risk=s.entry_reference_risk, entry_reward=s.entry_reference_reward,
            entry_rr=s.entry_reference_rr, entry_rr_pass=s.entry_reference_rr_pass,
            entry_economics_status=s.entry_economics_status, actual_execution_status=value.actual_execution_status,
            official_delivery_pct=t.official_delivery_pct, delivery_pass=t.delivery_pass, components=components,
            decision_score=_context(repository, canonical_security_id, cutoff, gates=False),
            six_gates=_context(repository, canonical_security_id, cutoff, gates=True))
        blockers = tuple(sorted({b.code for b in value.blockers} | set(t.blockers) | set(s.blockers)))
        return ToolEnvelope(status="PARTIAL" if value.candidate_formation_eligible else "BLOCKED",
            as_of=cutoff, data=data, evidence_refs=tuple(sorted(set(refs))), blockers=blockers,
            warnings=tuple(sorted(set(value.warnings) | set(value.sector_rotation_warnings)
                | set(t.unresolved_fields) | set(governance.unresolved_fields) | {
                "STORED_ASSESSMENT_NOT_CURRENT_EXECUTION_VALIDATION", "SOURCE_KNOWN_AT_NOT_SEPARATELY_STORED",
                "COMPONENT_READY_MEANS_STORED_VALUE_ONLY", "TRIGGER_IS_NOT_INITIAL_ENTRY",
                "NO_TRADE_PLAN_OR_THESIS_CONSTRUCTED", "NO_EXECUTION_AUTHORITY",
            })), provenance=(value.fingerprint, governance.policy_fingerprint, governance.selection_fingerprint, governance.approval_fingerprint))
    except Exception:
        # Never expose corrupt payloads, provider text, SQL or exception inputs.
        return ToolEnvelope(status="BLOCKED", as_of=cutoff, blockers=("SETUP_GOVERNANCE_OR_STORED_LINEAGE_INVALID",))
