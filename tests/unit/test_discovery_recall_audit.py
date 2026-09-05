from __future__ import annotations

import ast
import json
from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

import app.intelligence.discovery_recall_audit as module
from app.intelligence.discovery_recall_audit import (
    ActionReference, ActionState, AttributionClassification, BrainDecisionReference,
    BrainDecisionState, DiscoveryBatchReference, DiscoveryCapabilityState,
    DiscoveryFunnelAuditEvidence, DiscoveryProcessClassification, DiscoveryRecallAuditBatch,
    DiscoveryRecallAuditError, DiscoveryRecallAuditRecord, DiscoveryState, OutcomeMaturity,
    PerSecurityEvaluationState, RecallArtifactReference, RecallReason,
    ReferenceOpportunityOutcome, ReferenceOpportunityState,
    ReferenceOutcomeDefinitionAvailability, ReferenceOutcomeDefinitionReference,
    UniverseMembershipState,
    serialize_discovery_recall_audit,
)
from app.intelligence.multi_funnel_discovery import DiscoveryFunnelId as F, DiscoveryHorizon as H
from app.intelligence.multi_funnel_discovery_adapters import DiscoveryAdapterCoverageState as C
from app.intelligence.multi_funnel_orchestration import DiscoveryExecutionState as X


T = datetime(2026, 9, 4, 19, 30, 59, 533938, tzinfo=UTC)
FP = "sha256:" + "a" * 64
INSTRUMENT = "NSE:INE000A01001"


def ref(identifier: str, *, at: datetime = T) -> RecallArtifactReference:
    return RecallArtifactReference(identifier, FP, at)


def batch() -> DiscoveryBatchReference:
    return DiscoveryBatchReference(
        "whole-market-discovery:fixture", FP, T, "nse-universe:fixture", FP,
        "hsi-multi-funnel-discovery-registry", "v1", FP,
    )


def definition(horizon: H = H.POSITIONAL) -> ReferenceOutcomeDefinitionReference:
    return ReferenceOutcomeDefinitionReference("recall-reference:fixture", "v1", FP, horizon)


def outcome(state: ReferenceOpportunityState, maturity: OutcomeMaturity = OutcomeMaturity.MATURE,
            *, horizon: H = H.POSITIONAL, cutoff: datetime = T) -> ReferenceOpportunityOutcome:
    return ReferenceOpportunityOutcome(ref("reference-outcome:fixture", at=cutoff + timedelta(days=10)),
        definition(horizon), INSTRUMENT, cutoff, cutoff + timedelta(days=9), maturity, state)


def evidence(state: PerSecurityEvaluationState = PerSecurityEvaluationState.TRIGGER_EMITTED,
             capability: DiscoveryCapabilityState = DiscoveryCapabilityState.CAPABILITY_AVAILABLE,
             execution: X = X.EVALUATED, coverage: C = C.LEADS_EMITTED,
             *, horizon: H = H.POSITIONAL, emitted_leads=None, candidate_pool_item=None) -> DiscoveryFunnelAuditEvidence:
    emitted = ((ref("discovery-lead:fixture"),) if state is PerSecurityEvaluationState.TRIGGER_EMITTED else ()) if emitted_leads is None else emitted_leads
    candidate = (ref("discovery-pool:fixture") if state is PerSecurityEvaluationState.TRIGGER_EMITTED else None) if candidate_pool_item is None else candidate_pool_item
    return DiscoveryFunnelAuditEvidence(F.SECTOR_ROTATION, horizon, execution, coverage, capability, state, emitted, candidate)


def record(*, funnel: DiscoveryFunnelAuditEvidence | None = None,
           brain: BrainDecisionReference | None = None,
           action: ActionReference | None = None,
           reference_outcome: ReferenceOpportunityOutcome | None = None,
           discovery_state: DiscoveryState | None = None) -> DiscoveryRecallAuditRecord:
    funnel = funnel or evidence()
    state = discovery_state or {
        PerSecurityEvaluationState.TRIGGER_EMITTED: DiscoveryState.DISCOVERED,
        PerSecurityEvaluationState.EVALUATED_NO_TRIGGER: DiscoveryState.NOT_DISCOVERED,
        PerSecurityEvaluationState.IDENTITY_BLOCKED: DiscoveryState.IDENTITY_BLOCKED,
        PerSecurityEvaluationState.FUNNEL_NOT_EVALUATED: DiscoveryState.DISCOVERY_NOT_EVALUABLE,
        PerSecurityEvaluationState.PER_SECURITY_EVALUATION_UNKNOWN: DiscoveryState.DISCOVERY_COVERAGE_INCOMPLETE,
        PerSecurityEvaluationState.PER_SECURITY_DATA_BLOCKED: DiscoveryState.DISCOVERY_COVERAGE_INCOMPLETE,
    }[funnel.per_security_state]
    return DiscoveryRecallAuditRecord(
        batch(), INSTRUMENT, funnel, state,
        brain or BrainDecisionReference(BrainDecisionState.NOT_EVALUATED_BY_BRAIN),
        action or ActionReference(ActionState.NOT_APPLICABLE), reference_outcome,
        UniverseMembershipState.ELIGIBLE, ref("universe-membership:fixture"),
    )


def test_discovered_is_factual_success_not_trade_or_outcome_claim():
    value = record()
    assert value.discovery_state is DiscoveryState.DISCOVERED
    assert value.process_classification is DiscoveryProcessClassification.DISCOVERY_SUCCESS
    assert value.attribution_classification is AttributionClassification.NOT_YET_ATTRIBUTABLE
    assert RecallReason.REFERENCE_OUTCOME_NOT_DEFINED in value.reason_codes
    assert not {"score", "confidence", "entry_price", "target_price", "quantity", "actionability"} & {item.name for item in fields(value)}


def test_discovered_but_rejected_is_process_not_failure():
    value = record(brain=BrainDecisionReference(BrainDecisionState.REJECTED, ref("brain-decision:fixture")))
    assert value.process_classification is DiscoveryProcessClassification.DISCOVERED_BUT_REJECTED
    assert value.attribution_classification is AttributionClassification.NOT_YET_ATTRIBUTABLE
    assert "FAILURE" not in value.process_classification.value


@pytest.mark.parametrize("state", (ReferenceOpportunityState.REJECTION_SUPPORTED, ReferenceOpportunityState.REFERENCE_OPPORTUNITY_CONFIRMED))
def test_mature_outcome_distinguishes_correct_and_wrong_rejection(state):
    value = record(brain=BrainDecisionReference(BrainDecisionState.GATE_BLOCKED, ref("six-gates:fixture")), reference_outcome=outcome(state))
    expected = (AttributionClassification.CORRECTLY_REJECTED if state is ReferenceOpportunityState.REJECTION_SUPPORTED else AttributionClassification.DECISION_FAILURE)
    assert value.process_classification is DiscoveryProcessClassification.DISCOVERED_BUT_REJECTED
    assert value.attribution_classification is expected


def test_discovery_failure_needs_timely_mature_reference_and_operational_funnel():
    funnel = evidence(PerSecurityEvaluationState.EVALUATED_NO_TRIGGER, coverage=C.EVALUATED_NO_LEADS)
    value = record(funnel=funnel, reference_outcome=outcome(ReferenceOpportunityState.REFERENCE_OPPORTUNITY_CONFIRMED))
    assert value.discovery_state is DiscoveryState.NOT_DISCOVERED
    assert value.attribution_classification is AttributionClassification.DISCOVERY_FAILURE
    immature = record(funnel=funnel, reference_outcome=outcome(ReferenceOpportunityState.REFERENCE_OPPORTUNITY_CONFIRMED, OutcomeMaturity.IMMATURE))
    assert immature.attribution_classification is AttributionClassification.NOT_YET_ATTRIBUTABLE
    partially_mature = record(funnel=funnel, reference_outcome=outcome(
        ReferenceOpportunityState.REFERENCE_OPPORTUNITY_CONFIRMED,
        OutcomeMaturity.PARTIALLY_MATURE,
    ))
    assert partially_mature.attribution_classification is AttributionClassification.NOT_YET_ATTRIBUTABLE


def test_stock_movement_cannot_be_supplied_as_discovery_failure():
    funnel = evidence(PerSecurityEvaluationState.EVALUATED_NO_TRIGGER, coverage=C.EVALUATED_NO_LEADS)
    value = record(funnel=funnel)
    assert value.attribution_classification is AttributionClassification.NOT_YET_ATTRIBUTABLE
    assert not any("return" in item.name or "price" in item.name for item in fields(value))


def test_capability_gap_is_never_an_operational_miss():
    funnel = evidence(PerSecurityEvaluationState.FUNNEL_NOT_EVALUATED,
        DiscoveryCapabilityState.DISCOVERY_CAPABILITY_GAP, X.NOT_EXECUTABLE, C.SOURCE_NOT_OPERATIONAL)
    value = record(funnel=funnel, reference_outcome=outcome(ReferenceOpportunityState.REFERENCE_OPPORTUNITY_CONFIRMED))
    assert value.discovery_state is DiscoveryState.DISCOVERY_NOT_EVALUABLE
    assert value.process_classification is DiscoveryProcessClassification.UNAUDITABLE
    assert value.attribution_classification is AttributionClassification.UNAUDITABLE
    assert {RecallReason.FUNNEL_NOT_OPERATIONAL, RecallReason.DISCOVERY_CAPABILITY_GAP} <= set(value.reason_codes)


def test_unresolved_or_late_universe_membership_cannot_be_attributed():
    funnel = evidence(PerSecurityEvaluationState.EVALUATED_NO_TRIGGER, coverage=C.EVALUATED_NO_LEADS)
    value = DiscoveryRecallAuditRecord(
        batch(), INSTRUMENT, funnel, DiscoveryState.NOT_DISCOVERED,
        BrainDecisionReference(BrainDecisionState.NOT_EVALUATED_BY_BRAIN),
        ActionReference(ActionState.NOT_APPLICABLE),
        outcome(ReferenceOpportunityState.REFERENCE_OPPORTUNITY_CONFIRMED),
    )
    assert value.attribution_classification is AttributionClassification.UNAUDITABLE
    assert RecallReason.UNIVERSE_MEMBERSHIP_UNRESOLVED in value.reason_codes
    with pytest.raises(DiscoveryRecallAuditError, match="UNIVERSE_MEMBERSHIP_LOOKAHEAD_INVALID"):
        DiscoveryRecallAuditRecord(
            batch(), INSTRUMENT, funnel, DiscoveryState.NOT_DISCOVERED,
            BrainDecisionReference(BrainDecisionState.NOT_EVALUATED_BY_BRAIN),
            ActionReference(ActionState.NOT_APPLICABLE), None,
            UniverseMembershipState.ELIGIBLE, ref("universe-membership:late", at=T + timedelta(seconds=1)),
        )


@pytest.mark.parametrize("per_security,coverage,reason", [
    (PerSecurityEvaluationState.PER_SECURITY_EVALUATION_UNKNOWN, C.LEADS_EMITTED, RecallReason.PER_SECURITY_EVALUATION_UNKNOWN),
    (PerSecurityEvaluationState.PER_SECURITY_DATA_BLOCKED, C.DATA_BLOCKED, RecallReason.DATA_BLOCKED),
    (PerSecurityEvaluationState.IDENTITY_BLOCKED, C.IDENTITY_BLOCKED, RecallReason.IDENTITY_UNRESOLVED),
])
def test_unauditable_per_security_states_are_not_reconstructed(per_security, coverage, reason):
    state = X.EVALUATED if per_security is not PerSecurityEvaluationState.IDENTITY_BLOCKED else X.SOURCE_VALIDATION_FAILED
    capability = DiscoveryCapabilityState.CAPABILITY_AVAILABLE if state is X.EVALUATED else DiscoveryCapabilityState.CAPABILITY_UNRESOLVED
    value = record(funnel=evidence(per_security, capability, state, coverage))
    assert value.attribution_classification is AttributionClassification.UNAUDITABLE
    assert reason in value.reason_codes


def test_action_failure_is_downstream_of_discovery_and_brain_acceptance():
    value = record(brain=BrainDecisionReference(BrainDecisionState.ACCEPTED, ref("brain-decision:accepted")),
        action=ActionReference(ActionState.ACTION_TAKEN, ref("action:fixture")),
        reference_outcome=outcome(ReferenceOpportunityState.ACTION_FAILURE_SUPPORTED))
    assert value.attribution_classification is AttributionClassification.ACTION_FAILURE
    with pytest.raises(DiscoveryRecallAuditError, match="ACTION_WITHOUT_BRAIN_ACCEPTANCE"):
        record(brain=BrainDecisionReference(BrainDecisionState.REJECTED, ref("brain-decision:rejected")),
            action=ActionReference(ActionState.ACTION_TAKEN, ref("action:fixture")))


def test_future_outcome_is_opaque_and_cannot_feed_historical_discovery():
    with pytest.raises(DiscoveryRecallAuditError, match="NOT_FUTURE"):
        ReferenceOpportunityOutcome(ref("outcome:bad", at=T), definition(), INSTRUMENT, T, T, OutcomeMaturity.MATURE,
            ReferenceOpportunityState.REFERENCE_OPPORTUNITY_CONFIRMED)
    with pytest.raises(DiscoveryRecallAuditError, match="OUTCOME_BINDING_INVALID"):
        record(reference_outcome=outcome(ReferenceOpportunityState.REFERENCE_OPPORTUNITY_CONFIRMED, cutoff=T - timedelta(seconds=1)))
    with pytest.raises(DiscoveryRecallAuditError, match="DISCOVERY_CUTOFF_NOT_TIMELY"):
        late_funnel = evidence(
            emitted_leads=(ref("discovery-lead:late", at=T + timedelta(microseconds=1)),),
            candidate_pool_item=ref("discovery-pool:fixture"),
        )
        record(funnel=late_funnel)


def test_horizon_and_funnel_are_independent_audit_axes():
    value = record(funnel=evidence(horizon=H.LONG_TERM))
    assert value.funnel.horizon is H.LONG_TERM
    assert value.funnel.funnel_id is F.SECTOR_ROTATION
    assert value.audit_id != record().audit_id
    with pytest.raises(DiscoveryRecallAuditError, match="BATCH_REFERENCE_HORIZON_MISMATCH"):
        DiscoveryRecallAuditBatch(batch(), H.POSITIONAL, ReferenceOutcomeDefinitionAvailability.AVAILABLE,
            definition(H.LONG_TERM), (record(),))


def test_batch_is_immutable_and_reference_definition_not_active_blocks_outcomes():
    values = (record(),)
    batch_value = DiscoveryRecallAuditBatch(batch(), H.POSITIONAL, ReferenceOutcomeDefinitionAvailability.NOT_ACTIVE, None, values)
    assert (batch_value.auditable_count, batch_value.unauditable_count) == (1, 0)
    assert batch_value.classification_counts == (("NOT_YET_ATTRIBUTABLE", 1),)
    assert ("REFERENCE_OUTCOME_NOT_DEFINED", 1) in batch_value.missing_dependency_counts
    with pytest.raises(DiscoveryRecallAuditError, match="OUTCOME_BEFORE_DEFINITION"):
        DiscoveryRecallAuditBatch(batch(), H.POSITIONAL, ReferenceOutcomeDefinitionAvailability.NOT_ACTIVE, None,
            (record(reference_outcome=outcome(ReferenceOpportunityState.REFERENCE_OPPORTUNITY_CONFIRMED)),))
    with pytest.raises(FrozenInstanceError):
        batch_value.horizon = H.LONG_TERM


def test_batch_uses_available_definition_only_for_matching_horizon_outcome_receipts():
    audited = record(reference_outcome=outcome(ReferenceOpportunityState.REFERENCE_OPPORTUNITY_CONFIRMED))
    batch_value = DiscoveryRecallAuditBatch(batch(), H.POSITIONAL, ReferenceOutcomeDefinitionAvailability.AVAILABLE,
        definition(), (audited,))
    assert batch_value.audits == (audited,)
    assert batch_value.classification_counts == (("NOT_YET_ATTRIBUTABLE", 1),)
    batch_value.verify()


def test_identity_fingerprint_timestamp_normalization_and_serialization_are_stable():
    utc_value = record()
    local_batch = replace(batch(), discovery_as_of=T.astimezone(timezone(timedelta(hours=5, minutes=30))))
    local_value = DiscoveryRecallAuditRecord(local_batch, INSTRUMENT, evidence(), DiscoveryState.DISCOVERED,
        BrainDecisionReference(BrainDecisionState.NOT_EVALUATED_BY_BRAIN), ActionReference(ActionState.NOT_APPLICABLE),
        None, UniverseMembershipState.ELIGIBLE, ref("universe-membership:fixture"))
    assert utc_value == local_value
    assert serialize_discovery_recall_audit(utc_value) == serialize_discovery_recall_audit(local_value)
    assert json.loads(serialize_discovery_recall_audit(utc_value))["fingerprint"] == utc_value.fingerprint


def test_tampering_and_conflicting_lineage_are_rejected_not_repaired():
    value = record()
    object.__setattr__(value, "fingerprint", "sha256:" + "0" * 64)
    with pytest.raises(DiscoveryRecallAuditError, match="FINGERPRINT_MISMATCH"):
        value.verify()
    duplicate = ref("discovery-lead:fixture")
    with pytest.raises(DiscoveryRecallAuditError, match="LEAD_REFERENCE_CONFLICT"):
        evidence(PerSecurityEvaluationState.TRIGGER_EMITTED, emitted_leads=(duplicate, duplicate))


def test_invalid_orthogonal_combinations_fail_closed():
    with pytest.raises(DiscoveryRecallAuditError, match="DISCOVERED_LINEAGE_REQUIRED"):
        DiscoveryFunnelAuditEvidence(F.SECTOR_ROTATION, H.POSITIONAL, X.EVALUATED, C.LEADS_EMITTED,
            DiscoveryCapabilityState.CAPABILITY_AVAILABLE, PerSecurityEvaluationState.TRIGGER_EMITTED)
    with pytest.raises(DiscoveryRecallAuditError, match="DISCOVERY_STATE_EVIDENCE_CONTRADICTION"):
        DiscoveryRecallAuditRecord(batch(), INSTRUMENT,
            evidence(PerSecurityEvaluationState.EVALUATED_NO_TRIGGER, coverage=C.EVALUATED_NO_LEADS), DiscoveryState.DISCOVERED,
            BrainDecisionReference(BrainDecisionState.NOT_EVALUATED_BY_BRAIN), ActionReference(ActionState.NOT_APPLICABLE))
    with pytest.raises(DiscoveryRecallAuditError, match="BRAIN_WITHOUT_DISCOVERY"):
        DiscoveryRecallAuditRecord(batch(), INSTRUMENT,
            evidence(PerSecurityEvaluationState.EVALUATED_NO_TRIGGER, coverage=C.EVALUATED_NO_LEADS), DiscoveryState.NOT_DISCOVERED,
            BrainDecisionReference(BrainDecisionState.ACCEPTED, ref("brain:fixture")), ActionReference(ActionState.NOT_APPLICABLE))


def test_static_boundaries_no_discovery_mutation_or_action_dependencies():
    source = Path(module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = [item.module for item in ast.walk(tree) if isinstance(item, ast.ImportFrom)]
    forbidden_imports = ("app.api", "app.portfolio", "app.paper", "app.signals", "app.storage", "app.backtest", "sqlite3")
    assert not any(item and item.startswith(forbidden_imports) for item in imports)
    calls = {item.func.attr for item in ast.walk(tree) if isinstance(item, ast.Call) and isinstance(item.func, ast.Attribute)}
    assert not calls & {"save", "write", "execute", "connect", "open", "now", "utcnow", "run", "evaluate", "score", "rank"}
    for name in ("MultiFunnelDiscoveryBatch", "WholeMarketDiscoveryBatch", "CanonicalDiscoveryLead"):
        assert name not in source
    record_fields = {item.name for item in fields(DiscoveryRecallAuditRecord)}
    assert not record_fields & {"decision_score", "confidence", "entry", "target", "stop", "quantity", "portfolio", "order", "broker"}
