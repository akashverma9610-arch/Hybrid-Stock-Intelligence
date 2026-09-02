"""Deterministic routing for the single HSI Market-Wide Watch.

This module is deliberately a classifier, not a ranking or execution engine.
It consumes immutable diagnostic and external-intelligence evidence and emits
descriptive Watch archetypes.  It never creates a score, setup, gate result,
portfolio mutation, or trade instruction.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.domain.models import DiagnosticResult
from app.intelligence.external_intelligence import (
    EvidenceVersion, EventType, ExposureType, Materiality, PolicyStage,
)


ROUTING_POLICY = "opportunity-archetype-routing-policy/v1"


class OpportunityArchetype(StrEnum):
    PRE_BREAKOUT = "PRE_BREAKOUT"
    QUALITY_COMPOUNDER_WATCH = "QUALITY_COMPOUNDER_WATCH"
    EARNINGS_INFLECTION = "EARNINGS_INFLECTION"
    POLICY_LED_INFLECTION = "POLICY_LED_INFLECTION"
    ORDER_BOOK_ACCELERATION = "ORDER_BOOK_ACCELERATION"
    MARGIN_INFLECTION = "MARGIN_INFLECTION"
    BALANCE_SHEET_IMPROVEMENT = "BALANCE_SHEET_IMPROVEMENT"
    TURNAROUND_INFLECTION_WATCH = "TURNAROUND_INFLECTION_WATCH"
    RELATIVE_STRENGTH_WATCH = "RELATIVE_STRENGTH_WATCH"
    CATALYST_WATCH = "CATALYST_WATCH"
    RISK_WATCH = "RISK_WATCH"


class SetupPolicyRoute(StrEnum):
    PRE_BREAKOUT_POLICY = "PRE_BREAKOUT_POLICY"
    SETUP_POLICY_UNAVAILABLE_FOR_ARCHETYPE = "SETUP_POLICY_UNAVAILABLE_FOR_ARCHETYPE"


@dataclass(frozen=True, slots=True)
class ExternalEvidenceReference:
    canonical_event_id: str
    evidence_version_id: str
    event_type: str
    materiality: str
    policy_stage: str | None
    primary_source_type: str
    exposure_type: str
    exposure_verification_status: str
    evidence_fingerprint: str


@dataclass(frozen=True, slots=True)
class RoutingResult:
    archetypes: tuple[OpportunityArchetype, ...]
    external_evidence_references: tuple[ExternalEvidenceReference, ...]
    policy_maturity: str | None
    historical_quality_state: str
    current_inflection_state: str
    setup_policy_routes: tuple[tuple[str, str], ...]
    lifecycle_flags: tuple[str, ...]
    evidence_domain_coverage: tuple[str, ...]
    blocker_codes: tuple[str, ...]


class OpportunityArchetypeRouter:
    """Pure deterministic router; external evidence is pre-filtered by PIT."""

    def route(
        self,
        *,
        instrument_id: str,
        diagnostics: tuple[DiagnosticResult, ...],
        setup_state: str,
        decision_score_status: str,
        six_gates_state: str,
        external_evidence: tuple[EvidenceVersion, ...] = (),
    ) -> RoutingResult:
        by_rule = {str(value.rule_id): value for value in diagnostics}
        archetypes: set[OpportunityArchetype] = set()
        references: list[ExternalEvidenceReference] = []
        blockers: set[str] = set()

        if setup_state == "CURRENT_VALID_SETUP":
            # The existing CanonicalSetupOpportunity artifact is only created
            # after the approved Pre-Breakout policy passes.
            archetypes.add(OpportunityArchetype.PRE_BREAKOUT)
        if _result(by_rule, "24") == "ACCELERATING":
            archetypes.add(OpportunityArchetype.EARNINGS_INFLECTION)
        if _result(by_rule, "27") == "GROWING":
            archetypes.add(OpportunityArchetype.ORDER_BOOK_ACCELERATION)
        if _result(by_rule, "26") == "EXPANDING":
            archetypes.add(OpportunityArchetype.MARGIN_INFLECTION)
        if _result(by_rule, "6") in {"LEADING", "EMERGING_LEADER"}:
            archetypes.add(OpportunityArchetype.RELATIVE_STRENGTH_WATCH)
        if _risk(by_rule):
            archetypes.add(OpportunityArchetype.RISK_WATCH)

        historic = _historical_quality(by_rule)
        inflection = _inflection_state(by_rule)
        if historic == "WEAK" and any(item in archetypes for item in (
            OpportunityArchetype.EARNINGS_INFLECTION,
            OpportunityArchetype.MARGIN_INFLECTION,
            OpportunityArchetype.ORDER_BOOK_ACCELERATION,
        )):
            archetypes.add(OpportunityArchetype.TURNAROUND_INFLECTION_WATCH)
        if _quality_compounder(by_rule):
            archetypes.add(OpportunityArchetype.QUALITY_COMPOUNDER_WATCH)

        policy_stages: list[PolicyStage] = []
        for evidence in external_evidence:
            exposure = _verified_exact_exposure(evidence, instrument_id)
            if exposure is None:
                continue
            reference = ExternalEvidenceReference(
                canonical_event_id=evidence.event.canonical_event_id,
                evidence_version_id=evidence.evidence_version_id,
                event_type=evidence.event.event_type.value,
                materiality=evidence.event.materiality.value,
                policy_stage=evidence.event.policy_stage.value if evidence.event.policy_stage else None,
                primary_source_type=evidence.primary_source.source_type,
                exposure_type=exposure.exposure_type.value,
                exposure_verification_status=exposure.verification_status,
                evidence_fingerprint=evidence.fingerprint,
            )
            if _policy_led_qualified(evidence, exposure, by_rule):
                archetypes.add(OpportunityArchetype.POLICY_LED_INFLECTION)
                references.append(reference)
                assert evidence.event.policy_stage is not None
                policy_stages.append(evidence.event.policy_stage)
            elif _catalyst_qualified(evidence, exposure):
                archetypes.add(OpportunityArchetype.CATALYST_WATCH)
                references.append(reference)

        if any(item is OpportunityArchetype.POLICY_LED_INFLECTION for item in archetypes):
            blockers.update((
                "POLICY_TRANSMISSION_IS_INTERPRETATION_OR_INFERENCE_UNTIL_REPORTED",
                "EARNINGS_CONFIRMATION_NOT_YET_CONFIRMED",
            ))
        if historic == "WEAK":
            blockers.add("HISTORICAL_FUNDAMENTALS_WEAK_PRESERVED")
        if OpportunityArchetype.TURNAROUND_INFLECTION_WATCH in archetypes:
            blockers.add("TURNAROUND_NOT_COMPLETED")

        ordered = tuple(sorted(archetypes, key=lambda item: item.value))
        routes = tuple((item.value, (
            SetupPolicyRoute.PRE_BREAKOUT_POLICY.value
            if item is OpportunityArchetype.PRE_BREAKOUT
            else SetupPolicyRoute.SETUP_POLICY_UNAVAILABLE_FOR_ARCHETYPE.value
        )) for item in ordered)
        lifecycle: list[str] = []
        if ordered:
            lifecycle.extend(("DISCOVERED", "WATCH"))
            if any(_ready(item) for item in diagnostics):
                lifecycle.append("CONFIRMED_EVIDENCE")
            if any(route == SetupPolicyRoute.PRE_BREAKOUT_POLICY.value for _, route in routes):
                lifecycle.append("SETUP_POLICY_ELIGIBLE")
            if setup_state == "CURRENT_VALID_SETUP":
                lifecycle.append("SETUP_AVAILABLE")
            if decision_score_status == "COMPLETE":
                lifecycle.append("DECISION_SCORE_READY")
            if six_gates_state != "NOT_EVALUATED":
                lifecycle.append("SIX_GATES_READY")
        return RoutingResult(
            archetypes=ordered,
            external_evidence_references=tuple(sorted(set(references), key=lambda item: (item.canonical_event_id, item.evidence_version_id))),
            policy_maturity=max(policy_stages, key=_stage_rank).value if policy_stages else None,
            historical_quality_state=historic,
            current_inflection_state=inflection,
            setup_policy_routes=routes,
            lifecycle_flags=tuple(lifecycle),
            evidence_domain_coverage=tuple(sorted({
                "CANONICAL_DIAGNOSTICS:READY" if any(_ready(item) for item in diagnostics) else "CANONICAL_DIAGNOSTICS:PARTIAL",
                "EXTERNAL_INTELLIGENCE:VERIFIED" if references else "EXTERNAL_INTELLIGENCE:UNAVAILABLE",
                "SETUP:AVAILABLE" if setup_state == "CURRENT_VALID_SETUP" else "SETUP:NOT_AVAILABLE",
                "DECISION_SCORE:READY" if decision_score_status == "COMPLETE" else "DECISION_SCORE:UNSCORED",
                "SIX_GATES:EVALUATED" if six_gates_state != "NOT_EVALUATED" else "SIX_GATES:NOT_EVALUATED",
            })),
            blocker_codes=tuple(sorted(blockers)),
        )


def _result(values: dict[str, DiagnosticResult], rule_id: str) -> str:
    value = values.get(rule_id)
    return "" if value is None else value.result.upper()


def _ready(value: DiagnosticResult) -> bool:
    return value.result.upper() not in {"", "INSUFFICIENT_DATA", "UNVERIFIED", "NOT_APPLICABLE"}


def _risk(values: dict[str, DiagnosticResult]) -> bool:
    return (_result(values, "19") == "STRESSED" or _result(values, "24") == "DETERIORATING"
            or _result(values, "26") == "CONTRACTING")


def _historical_quality(values: dict[str, DiagnosticResult]) -> str:
    quality = (_result(values, "16"), _result(values, "17"), _result(values, "18"), _result(values, "19"), _result(values, "23"))
    if any(value in {"WEAK", "DETERIORATING", "STRESSED"} for value in quality):
        return "WEAK"
    if any(value == "INSUFFICIENT_DATA" for value in quality):
        return "PARTIAL"
    if any(value in {"HEALTHY", "ACCELERATING"} for value in quality):
        return "GOVERNED_STRONG"
    return "UNAVAILABLE"


def _inflection_state(values: dict[str, DiagnosticResult]) -> str:
    improvements = tuple((rule, _result(values, rule)) for rule in ("24", "26", "27"))
    if any(value in {"ACCELERATING", "EXPANDING", "GROWING"} for _, value in improvements):
        return "DIRECTIONAL_IMPROVEMENT"
    if any(value in {"DETERIORATING", "CONTRACTING", "DECLINING"} for _, value in improvements):
        return "DIRECTIONAL_DETERIORATION"
    return "UNRESOLVED"


def _quality_compounder(values: dict[str, DiagnosticResult]) -> bool:
    # Existing governed states only; two independent durable financial domains
    # are required.  This is a classification rule, not a new numeric score.
    positive = sum(_result(values, rule) in {"HEALTHY", "ACCELERATING", "MODERATE"} for rule in ("16", "17", "18", "19"))
    return positive >= 2 and _result(values, "19") != "STRESSED"


def _verified_exact_exposure(evidence: EvidenceVersion, instrument_id: str):
    return next((item for item in evidence.company_exposures if (
        item.canonical_instrument_id == instrument_id
        and item.verification_status == "VERIFIED"
        and item.exposure_type in {ExposureType.DIRECT, ExposureType.SUPPLY_CHAIN}
    )), None)


def _policy_led_qualified(evidence: EvidenceVersion, exposure, values: dict[str, DiagnosticResult]) -> bool:
    event = evidence.event
    # RUMOUR and STATEMENT are deliberately not implementation evidence.  The
    # event still remains visible to external intelligence, but is not routed.
    return (
        event.event_type in {EventType.GOVERNMENT_POLICY, EventType.REGULATORY}
        and event.policy_stage not in {None, PolicyStage.RUMOUR, PolicyStage.STATEMENT}
        and event.materiality in {Materiality.HIGH, Materiality.CRITICAL}
        and _authoritative(evidence.primary_source.source_type)
        and bool(evidence.interpretation or evidence.inferences)
        and _result(values, "19") not in {"", "INSUFFICIENT_DATA", "STRESSED"}
        and exposure.verification_status == "VERIFIED"
    )


def _catalyst_qualified(evidence: EvidenceVersion, exposure) -> bool:
    return (
        evidence.event.event_type in {EventType.ORDER_WIN, EventType.CAPEX, EventType.CORPORATE_DISCLOSURE, EventType.GUIDANCE}
        and evidence.event.materiality in {Materiality.HIGH, Materiality.CRITICAL}
        and _authoritative(evidence.primary_source.source_type)
        and exposure.verification_status == "VERIFIED"
    )


def _authoritative(source_type: str) -> bool:
    return source_type.strip().upper() in {"OFFICIAL", "OFFICIAL_PRIMARY", "GOVERNMENT", "REGULATOR", "EXCHANGE"}


def _stage_rank(value: PolicyStage) -> int:
    return tuple(PolicyStage).index(value)


__all__ = (
    "ExternalEvidenceReference", "OpportunityArchetype", "OpportunityArchetypeRouter", "ROUTING_POLICY",
    "RoutingResult", "SetupPolicyRoute",
)
