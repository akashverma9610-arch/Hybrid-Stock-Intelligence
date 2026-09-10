"""Focused proofs for the bounded Radar -> canonical-61 orchestration bridge."""
from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, timedelta, timezone
import ast
import inspect

import pytest

import app.intelligence.radar_diagnostic_orchestration as module
from app.intelligence.multi_funnel_discovery import (
    CanonicalDiscoveryLead,
    DiscoveryDataQualityState,
    DiscoveryFunnelId,
    DiscoveryLeadReadiness,
    DiscoveryLineageReference,
    DiscoveryReferenceKind,
    DiscoverySourceLayer,
    DiscoveryTriggerCode,
)
from app.intelligence.radar_diagnostic_orchestration import (
    CanonicalDiagnosticHorizon,
    CanonicalRuleReadinessState,
    RadarDiagnosticActionability,
    RadarDiagnosticAuthority,
    RadarDiagnosticEvaluationState,
    RadarDiagnosticExecutionStatus,
    RadarDiagnosticReason,
    RadarToHsiDiagnosticOrchestrator,
    RuleHorizonApplicabilityState,
    TemporalReadinessState,
    serialize_radar_diagnostic_receipt,
)
from app.universe_analysis.service import Canonical61DiagnosticRunner, StockDiagnosticInputAssembler
from tests.unit.test_technical_diagnostic_input import AT, INSTRUMENT, _input, _instrument


FP = "sha256:" + "a" * 64


class _StoredFacts:
    def observations_as_of(self, at):
        return ()


class _EvidenceAssembler:
    def __init__(self, *, mismatch: str | None = None, fail: bool = False) -> None:
        self.mismatch, self.fail, self.calls = mismatch, fail, 0

    def assemble_for_radar(self, *, canonical_security_id: str, evaluation_as_of):
        self.calls += 1
        if self.fail:
            raise RuntimeError("source unavailable")
        instrument = _instrument()
        evidence = StockDiagnosticInputAssembler(_StoredFacts()).assemble(
            instrument, AT, technical_input=_input(),
        )
        if self.mismatch == "instrument":
            return replace(evidence, instrument_id="NSE:INE000000002")
        if self.mismatch == "as_of":
            return replace(evidence, as_of=evaluation_as_of + timedelta(microseconds=1))
        return replace(evidence, technical_input=None) if self.mismatch == "technical" else evidence


def _lead(*, as_of=AT, known_at=AT, horizon=True) -> CanonicalDiscoveryLead:
    return CanonicalDiscoveryLead(
        canonical_instrument_id=INSTRUMENT.instrument_id,
        funnel_id=DiscoveryFunnelId.PRE_BREAKOUT,
        funnel_version="v1",
        discovery_as_of=as_of,
        source_layer=DiscoverySourceLayer.INTERPRETATION,
        trigger_codes=(DiscoveryTriggerCode.GOVERNED_PREBREAKOUT_SETUP_AVAILABLE,),
        readiness=DiscoveryLeadReadiness.READY_FOR_INSPECTION,
        data_quality=DiscoveryDataQualityState.VERIFIED,
        lineage=(DiscoveryLineageReference("canonical-setup:fixture", FP, DiscoveryReferenceKind.RECEIPT, known_at),),
        intended_horizons=(() if not horizon else (module.DiscoveryHorizon.POSITIONAL,)),
    )


def _orchestrator(*, mismatch: str | None = None, fail: bool = False) -> RadarToHsiDiagnosticOrchestrator:
    return RadarToHsiDiagnosticOrchestrator(
        evidence_assembler=_EvidenceAssembler(mismatch=mismatch, fail=fail),
        runner=Canonical61DiagnosticRunner(),
    )


def _accepted():
    result = _orchestrator().evaluate_one_lead(
        _lead(), evaluation_as_of=AT, canonical_horizon=CanonicalDiagnosticHorizon.POSITIONAL,
    )
    assert result.state is RadarDiagnosticEvaluationState.ACCEPTED and result.receipt is not None
    return result.receipt


def test_canonical_prebreakout_lead_runs_through_the_existing_full_61_registry_without_a_score():
    receipt = _accepted()
    assert tuple(item.rule_id for item in receipt.rule_references) == tuple(range(1, 62))
    assert len(receipt.rule_references) == 61
    assert receipt.evaluated_rule_count <= 61
    assert receipt.source_discovery_family is DiscoveryFunnelId.PRE_BREAKOUT
    assert receipt.authority is RadarDiagnosticAuthority.RESEARCH
    assert receipt.actionability is RadarDiagnosticActionability.WATCH_ONLY
    assert receipt.execution_status is RadarDiagnosticExecutionStatus.NON_EXECUTABLE
    assert receipt.technical_temporal_readiness is TemporalReadinessState.CURRENT_DESCRIPTIVE
    assert {item.horizon_applicability for item in receipt.rule_references} == {RuleHorizonApplicabilityState.POLICY_UNSET}


def test_rule_limitations_remain_explicit_without_15m_peer_vwap_or_event_substitution():
    receipt = _accepted()
    by_rule = {item.rule_id: item for item in receipt.rule_references}
    assert by_rule[6].readiness is CanonicalRuleReadinessState.PARTIAL
    assert by_rule[6].reason_codes == (RadarDiagnosticReason.AUTHORITATIVE_PEER_COHORT_UNAVAILABLE,)
    assert by_rule[14].readiness is CanonicalRuleReadinessState.PARTIAL
    assert by_rule[14].reason_codes == (RadarDiagnosticReason.INTRADAY_15M_EVIDENCE_UNAVAILABLE,)
    assert by_rule[35].readiness is CanonicalRuleReadinessState.SOURCE_NOT_READY
    assert by_rule[35].diagnostic_result == "INSUFFICIENT_DATA"
    assert by_rule[57].readiness is CanonicalRuleReadinessState.SOURCE_NOT_READY
    assert all(item.rule_id != 62 for item in receipt.rule_references)


def test_fundamental_rules_are_retained_by_the_same_brain_not_bypassed_by_technical_discovery():
    receipt = _accepted()
    by_rule = {item.rule_id: item for item in receipt.rule_references}
    assert tuple(sorted(item.rule_id for item in receipt.rule_references if 15 <= item.rule_id <= 30)) == tuple(range(15, 31))
    assert by_rule[16].readiness is CanonicalRuleReadinessState.INSUFFICIENT_DATA
    assert by_rule[23].readiness is CanonicalRuleReadinessState.INSUFFICIENT_DATA


@pytest.mark.parametrize("tamper", ("lead_id", "fingerprint", "security"))
def test_tampered_lead_fails_closed_without_assembling_evidence(tamper):
    lead = _lead()
    object.__setattr__(lead, tamper if tamper != "security" else "canonical_instrument_id", "tampered")
    source = _EvidenceAssembler()
    result = RadarToHsiDiagnosticOrchestrator(evidence_assembler=source, runner=Canonical61DiagnosticRunner()).evaluate_one_lead(
        lead, evaluation_as_of=AT, canonical_horizon=CanonicalDiagnosticHorizon.POSITIONAL,
    )
    assert result.state is RadarDiagnosticEvaluationState.REJECTED_INVALID_LEAD
    assert result.reason_codes == (RadarDiagnosticReason.DISCOVERY_LEAD_INVALID,)
    assert source.calls == 0


def test_future_lead_or_lineage_is_excluded_before_evidence_assembly():
    source = _EvidenceAssembler()
    orchestrator = RadarToHsiDiagnosticOrchestrator(evidence_assembler=source, runner=Canonical61DiagnosticRunner())
    # Canonical DiscoveryLead construction itself rejects lineage later than
    # discovery_as_of.  A valid lead wholly after this replay cutoff is the
    # remaining bridge-level look-ahead case.
    result = orchestrator.evaluate_one_lead(
        _lead(as_of=AT + timedelta(microseconds=1), known_at=AT + timedelta(microseconds=1)),
        evaluation_as_of=AT, canonical_horizon=CanonicalDiagnosticHorizon.POSITIONAL,
    )
    assert result.state is RadarDiagnosticEvaluationState.REJECTED_FUTURE_EVIDENCE
    assert result.reason_codes == (RadarDiagnosticReason.DISCOVERY_LINEAGE_AFTER_EVALUATION_AS_OF,)
    assert source.calls == 0


def test_explicit_governed_positional_context_is_required_and_setup_type_never_becomes_a_horizon():
    result = _orchestrator().evaluate_one_lead(
        _lead(horizon=False), evaluation_as_of=AT, canonical_horizon=CanonicalDiagnosticHorizon.POSITIONAL,
    )
    assert result.state is RadarDiagnosticEvaluationState.REJECTED_HORIZON_CONTEXT
    assert result.reason_codes == (RadarDiagnosticReason.DISCOVERY_HORIZON_NOT_GOVERNED,)
    assert "PRE_BREAKOUT_HORIZON" not in inspect.getsource(module)


def test_registered_but_not_active_discovery_family_fails_closed_without_hard_coding_prebreakout():
    lead = replace(_lead(), funnel_id=DiscoveryFunnelId.MOMENTUM)
    source = _EvidenceAssembler()
    result = RadarToHsiDiagnosticOrchestrator(evidence_assembler=source, runner=Canonical61DiagnosticRunner()).evaluate_one_lead(
        lead, evaluation_as_of=AT, canonical_horizon=CanonicalDiagnosticHorizon.POSITIONAL,
    )
    assert result.state is RadarDiagnosticEvaluationState.REJECTED_UNSUPPORTED_FAMILY
    assert result.reason_codes == (RadarDiagnosticReason.DISCOVERY_FAMILY_NOT_ACTIVE,)
    assert source.calls == 0


def test_unknown_or_malformed_discovery_family_fails_closed_without_an_exception_leak():
    lead = _lead()
    object.__setattr__(lead, "funnel_id", "UNKNOWN_DISCOVERY_FAMILY")
    result = _orchestrator().evaluate_one_lead(
        lead, evaluation_as_of=AT, canonical_horizon=CanonicalDiagnosticHorizon.POSITIONAL,
    )
    assert result.state is RadarDiagnosticEvaluationState.REJECTED_INVALID_LEAD
    assert result.reason_codes == (RadarDiagnosticReason.DISCOVERY_LEAD_INVALID,)


@pytest.mark.parametrize("mismatch, reason", (
    ("instrument", RadarDiagnosticReason.EVIDENCE_INSTRUMENT_MISMATCH),
    ("as_of", RadarDiagnosticReason.EVIDENCE_AS_OF_MISMATCH),
    ("technical", RadarDiagnosticReason.CANONICAL_TECHNICAL_INPUT_REQUIRED),
))
def test_evidence_identity_as_of_and_named_technical_input_must_match_the_lead_and_cutoff(mismatch, reason):
    result = _orchestrator(mismatch=mismatch).evaluate_one_lead(
        _lead(), evaluation_as_of=AT, canonical_horizon=CanonicalDiagnosticHorizon.POSITIONAL,
    )
    assert result.state is RadarDiagnosticEvaluationState.REJECTED_EVIDENCE_INVALID
    assert result.receipt is None
    assert result.reason_codes == (reason,)


def test_assembly_failure_is_nonsecret_and_fail_closed():
    result = _orchestrator(fail=True).evaluate_one_lead(
        _lead(), evaluation_as_of=AT, canonical_horizon=CanonicalDiagnosticHorizon.POSITIONAL,
    )
    assert result.state is RadarDiagnosticEvaluationState.REJECTED_EVIDENCE_INVALID
    assert result.reason_codes == (RadarDiagnosticReason.CANONICAL_EVIDENCE_ASSEMBLY_FAILED,)


class _MalformedRunner:
    def __init__(self, *, mode: str) -> None:
        self.mode = mode

    def run(self, evidence):
        result = Canonical61DiagnosticRunner().run(evidence)
        if self.mode == "missing_rule":
            return replace(result, evaluations=result.evaluations[:-1])
        values = list(result.evaluations)
        rule_35 = next(index for index, item in enumerate(values) if item.canonical_rule_id == 35)
        values[rule_35] = replace(values[rule_35], record=replace(values[rule_35].record, result="PASS"))
        return replace(result, evaluations=tuple(values))


@pytest.mark.parametrize("mode", ("missing_rule", "vwap_repaired"))
def test_malformed_runner_coverage_or_vwap_repair_is_rejected_not_silently_normalized(mode):
    result = RadarToHsiDiagnosticOrchestrator(
        evidence_assembler=_EvidenceAssembler(), runner=_MalformedRunner(mode=mode),
    ).evaluate_one_lead(_lead(), evaluation_as_of=AT, canonical_horizon=CanonicalDiagnosticHorizon.POSITIONAL)
    assert result.state is RadarDiagnosticEvaluationState.REJECTED_EVIDENCE_INVALID
    assert result.receipt is None


def test_equivalent_replay_is_idempotent_and_changed_lead_evidence_is_distinguishable():
    orchestrator = _orchestrator()
    first = orchestrator.evaluate_one_lead(_lead(), evaluation_as_of=AT, canonical_horizon=CanonicalDiagnosticHorizon.POSITIONAL)
    second = orchestrator.evaluate_one_lead(_lead(), evaluation_as_of=AT.astimezone(timezone(timedelta(hours=5, minutes=30))), canonical_horizon=CanonicalDiagnosticHorizon.POSITIONAL)
    changed = orchestrator.evaluate_one_lead(_lead(known_at=AT - timedelta(microseconds=1)), evaluation_as_of=AT, canonical_horizon=CanonicalDiagnosticHorizon.POSITIONAL)
    assert first == second
    assert first.receipt is not None and changed.receipt is not None
    assert first.receipt.receipt_id != changed.receipt.receipt_id
    assert serialize_radar_diagnostic_receipt(first.receipt) == serialize_radar_diagnostic_receipt(second.receipt)


def test_batch_deduplicates_equivalent_leads_and_rejects_conflicting_identity_deterministically():
    lead = _lead()
    batch = _orchestrator().evaluate_leads((lead, lead), evaluation_as_of=AT, canonical_horizon=CanonicalDiagnosticHorizon.POSITIONAL)
    assert batch.input_lead_count == 2 and batch.deduplicated_count == 1
    assert batch.accepted_count == 1 and batch.rule_receipt_count == 61
    assert sum(count for _, count in batch.rule_readiness_distribution) == 61
    assert batch.horizon_distribution == ((CanonicalDiagnosticHorizon.POSITIONAL, 1),)
    assert batch.data_insufficient_count >= 1
    # Lead identity intentionally excludes data-quality posture, while its
    # tamper-evident content fingerprint includes it.  This is the exact
    # valid same-identity/conflicting-content case the batch must reject.
    changed = replace(lead, data_quality=DiscoveryDataQualityState.PARTIAL)
    conflicted = _orchestrator().evaluate_leads((lead, changed), evaluation_as_of=AT, canonical_horizon=CanonicalDiagnosticHorizon.POSITIONAL)
    assert conflicted.accepted_count == 0
    assert conflicted.evaluations[0].state is RadarDiagnosticEvaluationState.REJECTED_CONFLICTED_LEAD
    assert conflicted.conflicted_count == 1


def test_receipt_is_immutable_tamper_evident_and_has_no_execution_surface():
    receipt = _accepted()
    with pytest.raises(FrozenInstanceError):
        receipt.canonical_security_id = "NSE:INE000000002"  # type: ignore[misc]
    object.__setattr__(receipt, "fingerprint", "tampered")
    with pytest.raises(ValueError, match="TAMPERED"):
        receipt.verify()
    fields = {field.name.lower() for field in __import__("dataclasses").fields(type(receipt))}
    forbidden = {"buy", "sell", "entry", "stop", "target", "quantity", "allocation", "portfolio", "broker", "order", "score", "signal", "alert"}
    assert not any(any(word in field for word in forbidden) for field in fields)


def test_contract_has_no_forbidden_dependencies_clock_or_persistence_and_no_full_market_work_on_import():
    source = inspect.getsource(module)
    tree = ast.parse(source)
    imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
    forbidden = ("app.api", "app.portfolio", "app.orders", "app.broker", "app.storage", "app.signals", "app.market_data.dhan")
    assert not any(name.startswith(forbidden) for name in imports)
    assert "datetime.now" not in source and "time.time" not in source
    assert "DecisionScore" not in source and "SixGate" not in source
    assert "evaluate_leads(" not in source.split("class RadarToHsiDiagnosticOrchestrator", 1)[0]


def test_registry_and_receipt_serialization_are_stable_and_all_rule_inputs_are_retained():
    receipt = _accepted()
    payload = module.radar_diagnostic_receipt_payload(receipt)
    assert payload["fingerprint"] == receipt.fingerprint
    assert payload["registry"] == "diagnostic-registry-v1"
    assert tuple(item["rule_id"] for item in payload["rules"]) == tuple(range(1, 62))
    assert len({item["diagnostic_result_id"] for item in payload["rules"]}) == 61
