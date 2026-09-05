from __future__ import annotations

import ast
import json
from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

import app.intelligence.discovery_recall_reference_matching as module
from app.intelligence.discovery_recall_reference_matching import (
    DISCOVERY_RECALL_MATCHING_CONTRACT,
    DISCOVERY_RECALL_REFERENCE_CONTRACT,
    DiscoveryPosture,
    DiscoveryRecallReferenceError,
    DiscoveryReferenceMatchState,
    IndependentReferenceOutcome,
    IndependentReferenceOutcomeState,
    PerSecurityDiscoveryEvaluation,
    PerSecurityDiscoveryState,
    ReferenceEvidence,
    ReferenceFunnelEligibility,
    ReferenceFunnelRelevance,
    ReferenceInputRequirement,
    ReferenceMeasurementFamily,
    ReferenceOpportunityHorizon,
    ReferenceOpportunitySpecification,
    ReferenceOutcomeMaturity,
    ReferenceParameter,
    ReferenceParameterState,
    ReferencePolicyStatus,
    match_reference_outcome,
    serialize_reference,
)
from app.intelligence.multi_funnel_discovery import DiscoveryFunnelId as F, DiscoveryLeadReadiness
from tests.unit.test_multi_funnel_discovery_adapters import _sector_run
from tests.unit.test_multi_funnel_orchestration import SECURITY, T, _run


FP = "sha256:" + "b" * 64


def evidence(identifier: str, requirement: ReferenceInputRequirement, *, known_at: datetime = T - timedelta(days=5)) -> ReferenceEvidence:
    return ReferenceEvidence(identifier, FP, known_at, requirement)


def specification(*, status: ReferencePolicyStatus = ReferencePolicyStatus.ACTIVE,
                  horizon: ReferenceOpportunityHorizon = ReferenceOpportunityHorizon.POSITIONAL,
                  parameters: tuple[ReferenceParameter, ...] | None = None) -> ReferenceOpportunitySpecification:
    family = {
        ReferenceOpportunityHorizon.SHORT_TERM: ReferenceMeasurementFamily.SHORT_TERM_CATALYST,
        ReferenceOpportunityHorizon.POSITIONAL: ReferenceMeasurementFamily.POSITIONAL_MARKET_PATH,
        ReferenceOpportunityHorizon.LONG_TERM: ReferenceMeasurementFamily.LONG_TERM_BUSINESS_PERSISTENCE,
    }[horizon]
    params = parameters if parameters is not None else (ReferenceParameter("reference-window", ReferenceParameterState.FROZEN, "fixture-v1"),)
    return ReferenceOpportunitySpecification(
        "reference-spec:fixture", "v1", horizon, family, "historical-universe:fixture", FP,
        T - timedelta(days=4), "observation-at", "discovery-deadline", "outcome-end",
        (ReferenceInputRequirement.CANONICAL_IDENTITY, ReferenceInputRequirement.HISTORICAL_UNIVERSE),
        params, (), status,
        (evidence("spec-provenance:fixture", ReferenceInputRequirement.HISTORICAL_UNIVERSE, known_at=T - timedelta(days=5)),),
    )


def outcome(*, spec: ReferenceOpportunitySpecification | None = None,
            state: IndependentReferenceOutcomeState = IndependentReferenceOutcomeState.REFERENCE_OPPORTUNITY,
            maturity: ReferenceOutcomeMaturity = ReferenceOutcomeMaturity.MATURE,
            deadline: datetime = T) -> IndependentReferenceOutcome:
    spec = spec or specification()
    return IndependentReferenceOutcome(
        spec, SECURITY,
        evidence("universe-membership:fixture", ReferenceInputRequirement.HISTORICAL_UNIVERSE),
        T - timedelta(days=1), None, deadline, T + timedelta(days=10), maturity, state,
        (
            evidence("identity:fixture", ReferenceInputRequirement.CANONICAL_IDENTITY, known_at=T),
            evidence("universe:fixture", ReferenceInputRequirement.HISTORICAL_UNIVERSE, known_at=T),
        ), (),
    )


def eligibility(*, horizon: ReferenceOpportunityHorizon = ReferenceOpportunityHorizon.POSITIONAL,
                relevance: ReferenceFunnelRelevance = ReferenceFunnelRelevance.RELEVANT) -> tuple[ReferenceFunnelEligibility, ...]:
    return (ReferenceFunnelEligibility(horizon, F.SECTOR_ROTATION, relevance,
        evidence("funnel-mapping:fixture", ReferenceInputRequirement.CANONICAL_IDENTITY)),)


def test_specification_contract_is_versioned_frozen_and_parameter_safe():
    value = specification()
    value.verify()
    assert value.fingerprint.startswith("sha256:")
    assert DISCOVERY_RECALL_REFERENCE_CONTRACT in serialize_reference(value)
    with pytest.raises(FrozenInstanceError):
        value.version = "v2"
    with pytest.raises(DiscoveryRecallReferenceError, match="ACTIVE_PARAMETER_UNSELECTED"):
        specification(parameters=(ReferenceParameter("reference-window", ReferenceParameterState.UNSELECTED),))
    with pytest.raises(DiscoveryRecallReferenceError, match="FAMILY_HORIZON_MISMATCH"):
        replace(value, horizon=ReferenceOpportunityHorizon.LONG_TERM)


def test_reference_outcome_is_independent_of_discovery_brain_and_action():
    value = outcome()
    serialized = serialize_reference(value)
    names = {item.name for item in fields(IndependentReferenceOutcome)}
    assert not names & {"lead", "discovery", "brain", "decision", "score", "gate", "portfolio", "action", "order", "broker", "return", "price"}
    empty_discovery = _run()
    emitted_discovery = _run({F.SECTOR_ROTATION: (_sector_run(),)})
    assert serialize_reference(value) == serialize_reference(value)
    assert value.outcome_id == outcome().outcome_id
    assert empty_discovery.batch_id != emitted_discovery.batch_id
    match_reference_outcome(outcome=value, discovery=empty_discovery, funnel_eligibility=eligibility())
    match_reference_outcome(outcome=value, discovery=emitted_discovery, funnel_eligibility=eligibility())
    assert serialize_reference(value) == serialized


def test_mature_reference_opportunity_requires_pre_registered_active_policy_and_inputs():
    with pytest.raises(DiscoveryRecallReferenceError, match="POLICY_NOT_ACTIVE"):
        outcome(spec=specification(status=ReferencePolicyStatus.RESEARCH_ONLY), state=IndependentReferenceOutcomeState.REFERENCE_OPPORTUNITY)
    with pytest.raises(DiscoveryRecallReferenceError, match="REQUIRED_INPUT_MISSING"):
        replace(outcome(), evidence=(evidence("identity:fixture", ReferenceInputRequirement.CANONICAL_IDENTITY, known_at=T),))
    with pytest.raises(DiscoveryRecallReferenceError, match="POLICY_AFTER_OBSERVATION"):
        late = replace(specification(), effective_at=T)
        IndependentReferenceOutcome(late, SECURITY, evidence("membership", ReferenceInputRequirement.HISTORICAL_UNIVERSE), T - timedelta(days=1), None, T, T + timedelta(days=1), ReferenceOutcomeMaturity.MATURE, IndependentReferenceOutcomeState.REFERENCE_OPPORTUNITY, (evidence("identity", ReferenceInputRequirement.CANONICAL_IDENTITY, known_at=T), evidence("universe", ReferenceInputRequirement.HISTORICAL_UNIVERSE, known_at=T)), ())


@pytest.mark.parametrize(("state", "maturity"), [
    (IndependentReferenceOutcomeState.IMMATURE, ReferenceOutcomeMaturity.IMMATURE),
    (IndependentReferenceOutcomeState.DATA_MISSING, ReferenceOutcomeMaturity.DATA_MISSING),
    (IndependentReferenceOutcomeState.NON_COMPARABLE, ReferenceOutcomeMaturity.NON_COMPARABLE),
    (IndependentReferenceOutcomeState.POLICY_NOT_ACTIVE, ReferenceOutcomeMaturity.NOT_EVALUATED),
])
def test_non_binary_outcome_states_preserve_insufficiency(state, maturity):
    spec = specification(status=ReferencePolicyStatus.RESEARCH_ONLY) if state is IndependentReferenceOutcomeState.POLICY_NOT_ACTIVE else specification()
    value = outcome(spec=spec, state=state, maturity=maturity)
    assert value.state is state


def test_historical_universe_and_evidence_timing_fail_closed():
    with pytest.raises(DiscoveryRecallReferenceError, match="MATURE_OUTCOME_LINEAGE_REQUIRED"):
        replace(outcome(), historical_universe_membership=None)
    with pytest.raises(DiscoveryRecallReferenceError, match="UNIVERSE_MEMBERSHIP_TIMING"):
        IndependentReferenceOutcome(specification(), SECURITY,
            evidence("late-membership", ReferenceInputRequirement.HISTORICAL_UNIVERSE, known_at=T),
            T - timedelta(days=1), None, T, T + timedelta(days=1), ReferenceOutcomeMaturity.MATURE,
            IndependentReferenceOutcomeState.REFERENCE_OPPORTUNITY,
            (evidence("identity", ReferenceInputRequirement.CANONICAL_IDENTITY, known_at=T), evidence("universe", ReferenceInputRequirement.HISTORICAL_UNIVERSE, known_at=T)), ())
    with pytest.raises(DiscoveryRecallReferenceError, match="EVIDENCE_AFTER_HORIZON"):
        replace(outcome(), evidence=(
            evidence("identity", ReferenceInputRequirement.CANONICAL_IDENTITY, known_at=T + timedelta(days=11)),
            evidence("universe", ReferenceInputRequirement.HISTORICAL_UNIVERSE, known_at=T),
        ))


def test_unknown_market_reference_input_cannot_be_promoted_to_opportunity():
    market_spec = replace(specification(), required_inputs=(
        ReferenceInputRequirement.CANONICAL_IDENTITY,
        ReferenceInputRequirement.HISTORICAL_UNIVERSE,
        ReferenceInputRequirement.PRICE_INTEGRITY,
    ))
    with pytest.raises(DiscoveryRecallReferenceError, match="REQUIRED_INPUT_MISSING"):
        outcome(spec=market_spec)
    unavailable = outcome(spec=market_spec, state=IndependentReferenceOutcomeState.DATA_MISSING,
        maturity=ReferenceOutcomeMaturity.DATA_MISSING)
    assert unavailable.state is IndependentReferenceOutcomeState.DATA_MISSING


def test_timely_and_late_matches_preserve_posture_and_never_emit_failure():
    timely = match_reference_outcome(outcome=outcome(), discovery=_run({F.SECTOR_ROTATION: (_sector_run(),)}), funnel_eligibility=eligibility())
    assert timely.system_state is DiscoveryReferenceMatchState.TIMELY_DISCOVERY_MATCH
    assert timely.relevant_funnel_coverage == ((F.SECTOR_ROTATION, DiscoveryReferenceMatchState.TIMELY_DISCOVERY_MATCH),)
    assert DiscoveryPosture.OPERATIONAL_DISCOVERY in timely.postures
    late = match_reference_outcome(outcome=outcome(deadline=T - timedelta(microseconds=1)), discovery=_run({F.SECTOR_ROTATION: (_sector_run(),)}), funnel_eligibility=eligibility())
    assert late.system_state is DiscoveryReferenceMatchState.LATE_DISCOVERY_MATCH
    assert late.relevant_funnel_coverage == ((F.SECTOR_ROTATION, DiscoveryReferenceMatchState.LATE_DISCOVERY_MATCH),)
    assert late.late_lead_ids and not late.timely_lead_ids
    assert "FAILURE" not in timely.system_state.value
    assert module._posture(DiscoveryLeadReadiness.RESEARCH_INSPECTION) is DiscoveryPosture.RESEARCH_SHADOW_DISCOVERY


def test_no_discovery_match_requires_explicit_per_security_trace():
    discovery = _run()
    result = match_reference_outcome(outcome=outcome(), discovery=discovery, funnel_eligibility=eligibility())
    assert result.system_state is DiscoveryReferenceMatchState.PER_SECURITY_EVALUATION_UNKNOWN
    trace = PerSecurityDiscoveryEvaluation(discovery.batch_id, discovery.fingerprint, SECURITY, F.SECTOR_ROTATION,
        PerSecurityDiscoveryState.EVALUATED_NO_TRIGGER,
        evidence("per-security-trace:fixture", ReferenceInputRequirement.CANONICAL_IDENTITY, known_at=T))
    traced = match_reference_outcome(outcome=outcome(), discovery=discovery, funnel_eligibility=eligibility(), per_security_evaluations=(trace,))
    assert traced.system_state is DiscoveryReferenceMatchState.NO_DISCOVERY_MATCH


def test_blocked_and_immature_preconditions_are_not_algorithmic_misses():
    discovery = _run()
    blocked = match_reference_outcome(outcome=outcome(), discovery=discovery, funnel_eligibility=(ReferenceFunnelEligibility(ReferenceOpportunityHorizon.POSITIONAL, F.NEWS_CATALYST, ReferenceFunnelRelevance.RELEVANT, evidence("news-mapping", ReferenceInputRequirement.CANONICAL_IDENTITY)),))
    assert blocked.system_state is DiscoveryReferenceMatchState.FUNNEL_NOT_CAPABLE
    immature = outcome(state=IndependentReferenceOutcomeState.IMMATURE, maturity=ReferenceOutcomeMaturity.IMMATURE)
    value = match_reference_outcome(outcome=immature, discovery=discovery, funnel_eligibility=eligibility())
    assert value.system_state is DiscoveryReferenceMatchState.REFERENCE_OUTCOME_IMMATURE


def test_exact_identity_order_independence_serialization_and_tamper_rejection():
    source = _run({F.SECTOR_ROTATION: (_sector_run(),)})
    value = match_reference_outcome(outcome=outcome(), discovery=source, funnel_eligibility=eligibility())
    mapping = eligibility() + (ReferenceFunnelEligibility(ReferenceOpportunityHorizon.POSITIONAL, F.MOMENTUM, ReferenceFunnelRelevance.IRRELEVANT, evidence("momentum-mapping", ReferenceInputRequirement.CANONICAL_IDENTITY)),)
    assert value == match_reference_outcome(outcome=outcome(), discovery=source, funnel_eligibility=tuple(reversed(mapping)))
    assert json.loads(serialize_reference(value))["fingerprint"] == value.fingerprint
    object.__setattr__(value, "fingerprint", "sha256:" + "0" * 64)
    with pytest.raises(DiscoveryRecallReferenceError, match="MATCH_TAMPERED"):
        value.verify()
    wrong = replace(outcome(), canonical_instrument_id="NSE:INE000A01002")
    assert match_reference_outcome(outcome=wrong, discovery=source, funnel_eligibility=eligibility()).system_state is DiscoveryReferenceMatchState.PER_SECURITY_EVALUATION_UNKNOWN
    research_only = outcome(spec=specification(status=ReferencePolicyStatus.RESEARCH_ONLY), state=IndependentReferenceOutcomeState.POLICY_NOT_ACTIVE, maturity=ReferenceOutcomeMaturity.NOT_EVALUATED)
    assert match_reference_outcome(outcome=research_only, discovery=source, funnel_eligibility=eligibility()).system_state is DiscoveryReferenceMatchState.REFERENCE_POLICY_NOT_ACTIVE


def test_static_boundaries_no_execution_or_discovery_failure_classifier():
    source = Path(module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = [item.module for item in ast.walk(tree) if isinstance(item, ast.ImportFrom)]
    forbidden = ("app.api", "app.portfolio", "app.paper", "app.signals", "app.storage", "app.backtest", "sqlite3")
    assert not any(item and item.startswith(forbidden) for item in imports)
    calls = {item.func.attr for item in ast.walk(tree) if isinstance(item, ast.Call) and isinstance(item.func, ast.Attribute)}
    assert not calls & {"save", "write", "execute", "connect", "open", "now", "utcnow", "run", "evaluate", "score", "rank"}
    assert "DISCOVERY_FAILURE" not in source
    assert DISCOVERY_RECALL_MATCHING_CONTRACT in source
