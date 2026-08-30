"""Pure, explicit-policy interpretation of immutable intelligence deltas.

This is a domain contract only.  It neither persists nor publishes an
interpretation, and callers must explicitly pass the approved frozen policy.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.historical.guard import manifest_fingerprint
from app.intelligence.intelligence_delta import IntelligenceDelta, IntelligenceDeltaChangeKind, IntelligenceDomainDelta
from app.intelligence.intelligence_delta_interpretation_policy import (
    CURRENT_FROZEN_OBJECTIVE_INTELLIGENCE_DELTA_INTERPRETATION_POLICY,
    FrozenObjectiveIntelligenceDeltaInterpretationPolicy,
    ObjectiveDeltaInterpretationCondition,
    ObjectiveDeltaInterpretationDimension,
    ObjectiveDeltaInterpretationKind,
)
from app.intelligence.unified_state import IntelligenceEvidenceAvailability, IntelligenceEvidenceDomain


class IntelligenceDeltaInterpretationError(ValueError):
    pass


class IntelligenceInterpretationEvidenceSufficiency(StrEnum):
    SUFFICIENT = "SUFFICIENT"
    INSUFFICIENT = "INSUFFICIENT"
    NON_COMPARABLE = "NON_COMPARABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True, slots=True)
class IntelligenceDomainTypedInterpretationEvidence:
    """Typed lineage required where a bounded state delta is intentionally lossy."""

    domain: IntelligenceEvidenceDomain
    dimension: ObjectiveDeltaInterpretationDimension
    source_domain_delta_fingerprint: str
    previous_status: str | None
    current_status: str | None
    previous_selected_usable_route: bool | None
    current_selected_usable_route: bool | None
    fingerprint: str

    def __post_init__(self) -> None:
        if self.dimension not in {
            ObjectiveDeltaInterpretationDimension.RELIABILITY,
            ObjectiveDeltaInterpretationDimension.HISTORICAL_INTEGRITY,
        }:
            raise IntelligenceDeltaInterpretationError("INTELLIGENCE_DELTA_TYPED_EVIDENCE_DIMENSION_UNSUPPORTED")
        expected_domain = (
            IntelligenceEvidenceDomain.RELIABILITY
            if self.dimension is ObjectiveDeltaInterpretationDimension.RELIABILITY
            else IntelligenceEvidenceDomain.HISTORICAL_INTEGRITY
        )
        if self.domain is not expected_domain or not self.source_domain_delta_fingerprint:
            raise IntelligenceDeltaInterpretationError("INTELLIGENCE_DELTA_TYPED_EVIDENCE_LINEAGE_REQUIRED")
        if self.dimension is ObjectiveDeltaInterpretationDimension.HISTORICAL_INTEGRITY and (
            self.previous_selected_usable_route is not None or self.current_selected_usable_route is not None
        ):
            raise IntelligenceDeltaInterpretationError("INTELLIGENCE_DELTA_TYPED_EVIDENCE_ROUTE_INTEGRITY_CONFLICT")
        if self.fingerprint != intelligence_domain_typed_interpretation_evidence_fingerprint(self):
            raise IntelligenceDeltaInterpretationError("INTELLIGENCE_DELTA_TYPED_EVIDENCE_FINGERPRINT_MISMATCH")


def create_intelligence_domain_typed_interpretation_evidence(
    *,
    domain: IntelligenceEvidenceDomain,
    dimension: ObjectiveDeltaInterpretationDimension,
    source_domain_delta_fingerprint: str,
    previous_status: str | None,
    current_status: str | None,
    previous_selected_usable_route: bool | None = None,
    current_selected_usable_route: bool | None = None,
) -> IntelligenceDomainTypedInterpretationEvidence:
    values = dict(
        domain=domain,
        dimension=dimension,
        source_domain_delta_fingerprint=source_domain_delta_fingerprint,
        previous_status=previous_status,
        current_status=current_status,
        previous_selected_usable_route=previous_selected_usable_route,
        current_selected_usable_route=current_selected_usable_route,
    )
    return IntelligenceDomainTypedInterpretationEvidence(
        **values,
        fingerprint=intelligence_domain_typed_interpretation_evidence_fingerprint_values(values),
    )


def intelligence_domain_typed_interpretation_evidence_fingerprint(
    value: IntelligenceDomainTypedInterpretationEvidence,
) -> str:
    return intelligence_domain_typed_interpretation_evidence_fingerprint_values({
        field: getattr(value, field) for field in value.__dataclass_fields__ if field != "fingerprint"
    })


def intelligence_domain_typed_interpretation_evidence_fingerprint_values(values: dict) -> str:
    return manifest_fingerprint(
        domain=values["domain"].value,
        dimension=values["dimension"].value,
        source_domain_delta_fingerprint=values["source_domain_delta_fingerprint"],
        previous_status=values["previous_status"],
        current_status=values["current_status"],
        previous_selected_usable_route=values["previous_selected_usable_route"],
        current_selected_usable_route=values["current_selected_usable_route"],
    )


@dataclass(frozen=True, slots=True)
class IntelligenceDomainInterpretation:
    domain: IntelligenceEvidenceDomain
    dimension: ObjectiveDeltaInterpretationDimension
    previous_status: str | None
    current_status: str | None
    interpretation: ObjectiveDeltaInterpretationKind
    evidence_sufficiency: IntelligenceInterpretationEvidenceSufficiency
    rule_key: str
    rationale_code: str
    source_domain_delta_fingerprint: str
    typed_evidence_fingerprint: str | None
    fingerprint: str

    def __post_init__(self) -> None:
        if not all((self.rule_key, self.rationale_code, self.source_domain_delta_fingerprint)):
            raise IntelligenceDeltaInterpretationError("INTELLIGENCE_DOMAIN_INTERPRETATION_REQUIRED_FIELD")
        if self.interpretation is ObjectiveDeltaInterpretationKind.NON_COMPARABLE and self.evidence_sufficiency is IntelligenceInterpretationEvidenceSufficiency.SUFFICIENT:
            raise IntelligenceDeltaInterpretationError("INTELLIGENCE_DOMAIN_INTERPRETATION_NONCOMPARABLE_SUFFICIENCY_CONFLICT")
        if self.fingerprint != intelligence_domain_interpretation_fingerprint(self):
            raise IntelligenceDeltaInterpretationError("INTELLIGENCE_DOMAIN_INTERPRETATION_FINGERPRINT_MISMATCH")


@dataclass(frozen=True, slots=True)
class IntelligenceDeltaInterpretation:
    """Rebuildable objective-only interpretation of one immutable delta."""

    interpretation_id: str
    canonical_instrument_id: str
    source_delta_id: str
    source_delta_fingerprint: str
    previous_state_id: str
    previous_state_fingerprint: str
    previous_as_of: object
    current_state_id: str
    current_state_fingerprint: str
    current_as_of: object
    policy_id: str
    policy_version: str
    policy_fingerprint: str
    domain_interpretations: tuple[IntelligenceDomainInterpretation, ...]
    fingerprint: str

    def __post_init__(self) -> None:
        if not all((self.interpretation_id, self.canonical_instrument_id, self.source_delta_id,
                    self.source_delta_fingerprint, self.previous_state_id,
                    self.previous_state_fingerprint, self.current_state_id,
                    self.current_state_fingerprint, self.policy_id, self.policy_version,
                    self.policy_fingerprint)):
            raise IntelligenceDeltaInterpretationError("INTELLIGENCE_DELTA_INTERPRETATION_REQUIRED_FIELD")
        if self.previous_as_of >= self.current_as_of:
            raise IntelligenceDeltaInterpretationError("INTELLIGENCE_DELTA_INTERPRETATION_CHRONOLOGY_REQUIRED")
        if self.domain_interpretations != tuple(sorted(self.domain_interpretations, key=_domain_interpretation_key)):
            raise IntelligenceDeltaInterpretationError("INTELLIGENCE_DELTA_INTERPRETATION_NONCANONICAL")
        if self.fingerprint != intelligence_delta_interpretation_fingerprint(self):
            raise IntelligenceDeltaInterpretationError("INTELLIGENCE_DELTA_INTERPRETATION_FINGERPRINT_MISMATCH")


def _domain_interpretation_key(value: IntelligenceDomainInterpretation) -> tuple[str, str, str]:
    return value.domain.value, value.dimension.value, value.fingerprint


def intelligence_domain_interpretation_fingerprint(value: IntelligenceDomainInterpretation) -> str:
    return intelligence_domain_interpretation_fingerprint_values({
        field: getattr(value, field) for field in value.__dataclass_fields__ if field != "fingerprint"
    })


def intelligence_domain_interpretation_fingerprint_values(values: dict) -> str:
    return manifest_fingerprint(
        domain=values["domain"].value,
        dimension=values["dimension"].value,
        previous_status=values["previous_status"],
        current_status=values["current_status"],
        interpretation=values["interpretation"].value,
        evidence_sufficiency=values["evidence_sufficiency"].value,
        rule_key=values["rule_key"],
        rationale_code=values["rationale_code"],
        source_domain_delta_fingerprint=values["source_domain_delta_fingerprint"],
        typed_evidence_fingerprint=values["typed_evidence_fingerprint"],
    )


def intelligence_delta_interpretation_fingerprint(value: IntelligenceDeltaInterpretation) -> str:
    return intelligence_delta_interpretation_fingerprint_values({
        field: getattr(value, field) for field in value.__dataclass_fields__ if field != "fingerprint"
    })


def intelligence_delta_interpretation_fingerprint_values(values: dict) -> str:
    return manifest_fingerprint(
        interpretation_id=values["interpretation_id"],
        canonical_instrument_id=values["canonical_instrument_id"],
        source_delta_id=values["source_delta_id"],
        source_delta_fingerprint=values["source_delta_fingerprint"],
        previous_state_id=values["previous_state_id"],
        previous_state_fingerprint=values["previous_state_fingerprint"],
        previous_as_of=values["previous_as_of"].isoformat(),
        current_state_id=values["current_state_id"],
        current_state_fingerprint=values["current_state_fingerprint"],
        current_as_of=values["current_as_of"].isoformat(),
        policy_id=values["policy_id"],
        policy_version=values["policy_version"],
        policy_fingerprint=values["policy_fingerprint"],
        domain_interpretations=tuple(item.fingerprint for item in values["domain_interpretations"]),
    )


def interpret_intelligence_delta(
    delta: IntelligenceDelta,
    *,
    policy: FrozenObjectiveIntelligenceDeltaInterpretationPolicy,
    typed_evidence: tuple[IntelligenceDomainTypedInterpretationEvidence, ...] = (),
) -> IntelligenceDeltaInterpretation:
    """Interpret only approved objective transitions; no store, engine, or I/O is used."""
    _require_frozen_policy(policy)
    if not isinstance(delta, IntelligenceDelta):
        raise IntelligenceDeltaInterpretationError("INTELLIGENCE_DELTA_INTERPRETATION_DELTA_REQUIRED")
    evidence = _typed_evidence_by_domain(delta, typed_evidence)
    values = tuple(
        interpretation
        for domain_delta in delta.domain_deltas
        for interpretation in _interpret_domain_delta(domain_delta, policy, evidence.get(domain_delta.domain))
    )
    ordered = tuple(sorted(values, key=_domain_interpretation_key))
    seed = manifest_fingerprint(
        source_delta_id=delta.delta_id,
        source_delta_fingerprint=delta.fingerprint,
        policy_fingerprint=policy.fingerprint,
        domain_interpretation_fingerprints=tuple(item.fingerprint for item in ordered),
    )
    result = dict(
        interpretation_id=f"intelligence-delta-interpretation-{seed[:24]}",
        canonical_instrument_id=delta.canonical_instrument_id,
        source_delta_id=delta.delta_id,
        source_delta_fingerprint=delta.fingerprint,
        previous_state_id=delta.previous_state_id,
        previous_state_fingerprint=delta.previous_state_fingerprint,
        previous_as_of=delta.previous_as_of,
        current_state_id=delta.current_state_id,
        current_state_fingerprint=delta.current_state_fingerprint,
        current_as_of=delta.current_as_of,
        policy_id=policy.policy_id,
        policy_version=policy.version,
        policy_fingerprint=policy.fingerprint,
        domain_interpretations=ordered,
    )
    return IntelligenceDeltaInterpretation(
        **result,
        fingerprint=intelligence_delta_interpretation_fingerprint_values({
            **result,
            "interpretation_id": result["interpretation_id"],
        }),
    )


def _require_frozen_policy(policy: FrozenObjectiveIntelligenceDeltaInterpretationPolicy) -> None:
    expected = CURRENT_FROZEN_OBJECTIVE_INTELLIGENCE_DELTA_INTERPRETATION_POLICY
    if not isinstance(policy, FrozenObjectiveIntelligenceDeltaInterpretationPolicy):
        raise IntelligenceDeltaInterpretationError("INTELLIGENCE_DELTA_INTERPRETATION_POLICY_REQUIRED")
    if (policy.policy_id, policy.version, policy.fingerprint) != (expected.policy_id, expected.version, expected.fingerprint):
        raise IntelligenceDeltaInterpretationError("INTELLIGENCE_DELTA_INTERPRETATION_POLICY_UNSUPPORTED")
    if policy.active or policy.selected_for_future_interpreter:
        raise IntelligenceDeltaInterpretationError("INTELLIGENCE_DELTA_INTERPRETATION_POLICY_ACTIVE_CONFLICT")


def _typed_evidence_by_domain(
    delta: IntelligenceDelta,
    typed_evidence: tuple[IntelligenceDomainTypedInterpretationEvidence, ...],
) -> dict[IntelligenceEvidenceDomain, IntelligenceDomainTypedInterpretationEvidence]:
    available = {item.domain: item for item in delta.domain_deltas}
    values: dict[IntelligenceEvidenceDomain, IntelligenceDomainTypedInterpretationEvidence] = {}
    for item in typed_evidence:
        if not isinstance(item, IntelligenceDomainTypedInterpretationEvidence):
            raise IntelligenceDeltaInterpretationError("INTELLIGENCE_DELTA_TYPED_EVIDENCE_REQUIRED")
        source = available.get(item.domain)
        if source is None or item.source_domain_delta_fingerprint != source.fingerprint:
            raise IntelligenceDeltaInterpretationError("INTELLIGENCE_DELTA_TYPED_EVIDENCE_DELTA_LINEAGE_MISMATCH")
        if item.domain in values:
            raise IntelligenceDeltaInterpretationError("INTELLIGENCE_DELTA_TYPED_EVIDENCE_DUPLICATE")
        values[item.domain] = item
    return values


def _interpret_domain_delta(
    domain_delta: IntelligenceDomainDelta,
    policy: FrozenObjectiveIntelligenceDeltaInterpretationPolicy,
    typed: IntelligenceDomainTypedInterpretationEvidence | None,
) -> tuple[IntelligenceDomainInterpretation, ...]:
    values: list[IntelligenceDomainInterpretation] = []
    previous, current = domain_delta.previous_reference, domain_delta.current_reference
    if previous is None or current is None:
        values.append(_result(
            domain_delta, ObjectiveDeltaInterpretationDimension.INTELLIGENCE_AVAILABILITY,
            None, None, ObjectiveDeltaInterpretationKind.NON_COMPARABLE,
            IntelligenceInterpretationEvidenceSufficiency.NON_COMPARABLE,
            "EVIDENCE_ADDED_OR_REMOVED_ONLY", "EVIDENCE_PRESENCE_DIRECTION_FORBIDDEN",
        ))
    else:
        values.extend((
            _standard_transition(
                domain_delta, policy, ObjectiveDeltaInterpretationDimension.FRESHNESS,
                previous.freshness_status.value.upper(), current.freshness_status.value.upper(),
            ),
            _standard_transition(
                domain_delta, policy, ObjectiveDeltaInterpretationDimension.INTELLIGENCE_AVAILABILITY,
                previous.availability.value, current.availability.value,
            ),
        ))
    if domain_delta.domain is IntelligenceEvidenceDomain.RELIABILITY:
        values.append(_reliability_transition(domain_delta, policy, typed))
    if domain_delta.domain is IntelligenceEvidenceDomain.HISTORICAL_INTEGRITY:
        values.append(_historical_integrity_transition(domain_delta, policy, typed))
    return tuple(values)


def _standard_transition(
    domain_delta: IntelligenceDomainDelta,
    policy: FrozenObjectiveIntelligenceDeltaInterpretationPolicy,
    dimension: ObjectiveDeltaInterpretationDimension,
    previous: str,
    current: str,
) -> IntelligenceDomainInterpretation:
    if previous == current:
        return _result(domain_delta, dimension, previous, current,
                       ObjectiveDeltaInterpretationKind.NO_DIRECTIONAL_CHANGE,
                       IntelligenceInterpretationEvidenceSufficiency.SUFFICIENT,
                       "IDENTICAL_GOVERNED_STATE", "GOVERNED_STATE_UNCHANGED")
    rule = _find_rule(policy, dimension, previous, current, None)
    if rule is None:
        return _result(domain_delta, dimension, previous, current,
                       ObjectiveDeltaInterpretationKind.NON_COMPARABLE,
                       IntelligenceInterpretationEvidenceSufficiency.NON_COMPARABLE,
                       "UNSUPPORTED_GOVERNED_TRANSITION", "GOVERNED_TRANSITION_UNSUPPORTED")
    return _result(domain_delta, dimension, previous, current, rule.interpretation,
                   IntelligenceInterpretationEvidenceSufficiency.SUFFICIENT,
                   _rule_key(rule), "APPROVED_OBJECTIVE_TRANSITION")


def _reliability_transition(
    domain_delta: IntelligenceDomainDelta,
    policy: FrozenObjectiveIntelligenceDeltaInterpretationPolicy,
    typed: IntelligenceDomainTypedInterpretationEvidence | None,
) -> IntelligenceDomainInterpretation:
    if typed is None or typed.previous_status is None or typed.current_status is None:
        return _result(domain_delta, ObjectiveDeltaInterpretationDimension.RELIABILITY, None, None,
                       ObjectiveDeltaInterpretationKind.NON_COMPARABLE,
                       IntelligenceInterpretationEvidenceSufficiency.INSUFFICIENT,
                       "RELIABILITY_TYPED_STATUS_REQUIRED", "RELIABILITY_COMPOSITE_STATUS_NOT_IN_DELTA")
    previous, current = typed.previous_status, typed.current_status
    if previous == current:
        return _result(domain_delta, typed.dimension, previous, current,
                       ObjectiveDeltaInterpretationKind.NO_DIRECTIONAL_CHANGE,
                       IntelligenceInterpretationEvidenceSufficiency.SUFFICIENT,
                       "IDENTICAL_GOVERNED_STATE", "GOVERNED_STATE_UNCHANGED", typed)
    if {previous, current} == {"STALE", "READY"}:
        return _result(domain_delta, typed.dimension, previous, current,
                       ObjectiveDeltaInterpretationKind.NO_DIRECTIONAL_CHANGE,
                       IntelligenceInterpretationEvidenceSufficiency.NOT_APPLICABLE,
                       "RELIABILITY_FRESHNESS_SEPARATED", "FRESHNESS_DIMENSION_OWNS_TRANSITION", typed)
    if {previous, current}.intersection({"CONFLICTED", "FALLBACK_USED", "LAST_KNOWN_GOOD"}):
        return _result(domain_delta, typed.dimension, previous, current,
                       ObjectiveDeltaInterpretationKind.NON_COMPARABLE,
                       IntelligenceInterpretationEvidenceSufficiency.NON_COMPARABLE,
                       "RELIABILITY_COMPOSITE_NONCOMPARABLE", "RELIABILITY_COMPOSITE_STATUS_PROTECTED", typed)
    if {previous, current} == {"PRIMARY_UNAVAILABLE", "UNAVAILABLE"}:
        return _result(domain_delta, typed.dimension, previous, current,
                       ObjectiveDeltaInterpretationKind.NON_COMPARABLE,
                       IntelligenceInterpretationEvidenceSufficiency.NON_COMPARABLE,
                       "RELIABILITY_ROUTE_CAUSE_NONCOMPARABLE", "NO_ROUTE_CAUSE_NOT_ORDINAL", typed)
    rule = _find_rule(policy, typed.dimension, previous, current, typed)
    if rule is None:
        return _result(domain_delta, typed.dimension, previous, current,
                       ObjectiveDeltaInterpretationKind.NON_COMPARABLE,
                       IntelligenceInterpretationEvidenceSufficiency.INSUFFICIENT,
                       "RELIABILITY_TYPED_PROOF_REQUIRED", "APPROVED_ROUTE_PROOF_ABSENT", typed)
    return _result(domain_delta, typed.dimension, previous, current, rule.interpretation,
                   IntelligenceInterpretationEvidenceSufficiency.SUFFICIENT,
                   _rule_key(rule), "APPROVED_OBJECTIVE_TRANSITION", typed)


def _historical_integrity_transition(
    domain_delta: IntelligenceDomainDelta,
    policy: FrozenObjectiveIntelligenceDeltaInterpretationPolicy,
    typed: IntelligenceDomainTypedInterpretationEvidence | None,
) -> IntelligenceDomainInterpretation:
    if typed is None or typed.previous_status is None or typed.current_status is None:
        return _result(domain_delta, ObjectiveDeltaInterpretationDimension.HISTORICAL_INTEGRITY, None, None,
                       ObjectiveDeltaInterpretationKind.NON_COMPARABLE,
                       IntelligenceInterpretationEvidenceSufficiency.NON_COMPARABLE,
                       "HISTORICAL_INTEGRITY_FINGERPRINT_ONLY", "NATIVE_TYPED_STATUS_NOT_AVAILABLE")
    previous, current = typed.previous_status, typed.current_status
    if previous not in {"VALID", "PARTIAL", "INVALID", "UNAVAILABLE"} or current not in {"VALID", "PARTIAL", "INVALID", "UNAVAILABLE"}:
        return _result(domain_delta, typed.dimension, previous, current,
                       ObjectiveDeltaInterpretationKind.NON_COMPARABLE,
                       IntelligenceInterpretationEvidenceSufficiency.NON_COMPARABLE,
                       "HISTORICAL_INTEGRITY_PROJECTED_CONFLICTED", "NATIVE_STATUS_REQUIRED_NO_RECONSTRUCTION", typed)
    if previous == current:
        return _result(domain_delta, typed.dimension, previous, current,
                       ObjectiveDeltaInterpretationKind.NO_DIRECTIONAL_CHANGE,
                       IntelligenceInterpretationEvidenceSufficiency.SUFFICIENT,
                       "IDENTICAL_GOVERNED_STATE", "GOVERNED_STATE_UNCHANGED", typed)
    if "UNAVAILABLE" in {previous, current}:
        return _result(domain_delta, typed.dimension, previous, current,
                       ObjectiveDeltaInterpretationKind.NON_COMPARABLE,
                       IntelligenceInterpretationEvidenceSufficiency.NON_COMPARABLE,
                       "HISTORICAL_INTEGRITY_NATIVE_UNAVAILABLE", "INTEGRITY_ABSENCE_NOT_QUALITY_ORDER", typed)
    rule = _find_rule(policy, typed.dimension, previous, current, typed)
    if rule is None:
        return _result(domain_delta, typed.dimension, previous, current,
                       ObjectiveDeltaInterpretationKind.NON_COMPARABLE,
                       IntelligenceInterpretationEvidenceSufficiency.NON_COMPARABLE,
                       "HISTORICAL_INTEGRITY_TRANSITION_UNSUPPORTED", "APPROVED_INTEGRITY_TRANSITION_ABSENT", typed)
    return _result(domain_delta, typed.dimension, previous, current, rule.interpretation,
                   IntelligenceInterpretationEvidenceSufficiency.SUFFICIENT,
                   _rule_key(rule), "APPROVED_OBJECTIVE_TRANSITION", typed)


def _find_rule(
    policy: FrozenObjectiveIntelligenceDeltaInterpretationPolicy,
    dimension: ObjectiveDeltaInterpretationDimension,
    previous: str,
    current: str,
    typed: IntelligenceDomainTypedInterpretationEvidence | None,
):
    for rule in policy.rules:
        if rule.dimension is not dimension:
            continue
        if rule.previous_state == previous and rule.current_state == current:
            return rule if not rule.required_conditions else None
        if (
            rule.previous_state == "SELECTED_USABLE_ROUTE"
            and rule.current_state == current
            and typed is not None
            and typed.previous_selected_usable_route is True
        ):
            if rule.required_conditions == (ObjectiveDeltaInterpretationCondition.PREVIOUS_SELECTED_USABLE_ROUTE,):
                return rule
        if (
            rule.current_state == "SELECTED_USABLE_ROUTE"
            and rule.previous_state == previous
            and typed is not None
            and typed.current_selected_usable_route is True
            and rule.required_conditions == (ObjectiveDeltaInterpretationCondition.CURRENT_SELECTED_USABLE_ROUTE,)
        ):
            return rule
    return None


def _rule_key(rule) -> str:
    conditions = ",".join(item.value for item in rule.required_conditions)
    return f"{rule.dimension.value}:{rule.previous_state}->{rule.current_state}" + (f":{conditions}" if conditions else "")


def _result(
    domain_delta: IntelligenceDomainDelta,
    dimension: ObjectiveDeltaInterpretationDimension,
    previous: str | None,
    current: str | None,
    interpretation: ObjectiveDeltaInterpretationKind,
    sufficiency: IntelligenceInterpretationEvidenceSufficiency,
    rule_key: str,
    rationale_code: str,
    typed: IntelligenceDomainTypedInterpretationEvidence | None = None,
) -> IntelligenceDomainInterpretation:
    values = dict(
        domain=domain_delta.domain,
        dimension=dimension,
        previous_status=previous,
        current_status=current,
        interpretation=interpretation,
        evidence_sufficiency=sufficiency,
        rule_key=rule_key,
        rationale_code=rationale_code,
        source_domain_delta_fingerprint=domain_delta.fingerprint,
        typed_evidence_fingerprint=None if typed is None else typed.fingerprint,
    )
    return IntelligenceDomainInterpretation(
        **values,
        fingerprint=intelligence_domain_interpretation_fingerprint_values(values),
    )


__all__ = (
    "IntelligenceDeltaInterpretation",
    "IntelligenceDeltaInterpretationError",
    "IntelligenceDomainInterpretation",
    "IntelligenceDomainTypedInterpretationEvidence",
    "IntelligenceInterpretationEvidenceSufficiency",
    "create_intelligence_domain_typed_interpretation_evidence",
    "intelligence_delta_interpretation_fingerprint",
    "interpret_intelligence_delta",
)
