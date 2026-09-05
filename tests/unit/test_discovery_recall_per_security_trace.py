from __future__ import annotations

import ast
import json
from dataclasses import FrozenInstanceError, replace
from datetime import timedelta
from pathlib import Path

import pytest

import app.intelligence.discovery_recall_per_security_trace as module
from app.intelligence.discovery_recall_audit import UniverseMembershipState
from app.intelligence.discovery_recall_per_security_trace import (
    DISCOVERY_RECALL_PER_SECURITY_TRACE_CONTRACT,
    DiscoveryRecallTraceError,
    FunnelScopeState,
    PerSecurityTraceBasis,
    PerSecurityTraceState,
    RequiredInputReadiness,
    SourceFreshnessState,
    as_reference_matching_evaluation,
    audit_per_security_traces,
    emitted_lead_traces,
    serialize_per_security_trace,
    trace_security,
)
from app.intelligence.multi_funnel_discovery import DiscoveryFunnelId as F
from app.intelligence.multi_funnel_discovery_adapters import DiscoveryAdapterCoverageState as Coverage
from app.intelligence.discovery_recall_reference_matching import PerSecurityDiscoveryState
from tests.unit.test_multi_funnel_discovery_adapters import _inflection, _sector_run
from tests.unit.test_multi_funnel_orchestration import SECURITY, T, _run


OTHER = "NSE:INE000A01002"


def sector_batch(*, ids=(SECURITY,), sources=None):
    return _run(sources or {F.SECTOR_ROTATION: (_sector_run(ids=ids),)}, ids=ids)


def emitted_trace():
    return trace_security(discovery=sector_batch(), canonical_instrument_id=SECURITY, funnel_id=F.SECTOR_ROTATION)


def test_exact_identity_explicit_as_of_immutable_and_stable_serialization():
    trace = emitted_trace()
    assert trace.canonical_instrument_id == SECURITY
    assert trace.isin == SECURITY.removeprefix("NSE:")
    assert trace.as_of == T
    assert trace.state is PerSecurityTraceState.LEAD_EMITTED
    assert trace.trace_basis is PerSecurityTraceBasis.EXACT_SECURITY_EVALUATION
    assert json.loads(serialize_per_security_trace(trace))["fingerprint"] == trace.fingerprint
    with pytest.raises(FrozenInstanceError):
        trace.as_of = T
    assert trace == emitted_trace()
    assert DISCOVERY_RECALL_PER_SECURITY_TRACE_CONTRACT in serialize_per_security_trace(trace)


def test_lead_emitted_trace_reuses_existing_lead_and_never_creates_another_lead():
    batch = sector_batch()
    trace = trace_security(discovery=batch, canonical_instrument_id=SECURITY, funnel_id=F.SECTOR_ROTATION)
    original = next(item for item in batch.executions if item.original.funnel_id is F.SECTOR_ROTATION)
    assert trace.lead_ids == tuple(item.lead_id for item in original.original.leads)
    assert trace.source_lineage == original.original.leads[0].lineage
    assert trace.evaluation_attempted
    assert trace.required_input_readiness is RequiredInputReadiness.READY
    assert trace.source_freshness is SourceFreshnessState.TIMELY
    assert len(emitted_lead_traces(discovery=batch)) == 1


def test_absence_from_a_lead_list_is_per_security_unknown_not_no_trigger():
    batch = sector_batch(ids=(SECURITY, OTHER), sources={F.SECTOR_ROTATION: (_sector_run(ids=(SECURITY,)),)})
    trace = trace_security(discovery=batch, canonical_instrument_id=OTHER, funnel_id=F.SECTOR_ROTATION)
    assert trace.state is PerSecurityTraceState.PER_SECURITY_EVALUATION_UNKNOWN
    assert trace.scope_state is FunnelScopeState.SCOPE_UNKNOWN
    assert not trace.evaluation_attempted
    assert trace.required_input_readiness is RequiredInputReadiness.PARTIAL
    assert trace.no_trigger_reason_code is None


def test_evaluated_no_trigger_requires_affirmative_exact_security_proof():
    base = emitted_trace()
    valid = replace(
        base,
        state=PerSecurityTraceState.EVALUATED_NO_TRIGGER,
        lead_ids=(),
        no_trigger_reason_code="COMPRESSION_CRITERIA_NOT_MET",
    )
    assert valid.state is PerSecurityTraceState.EVALUATED_NO_TRIGGER
    with pytest.raises(DiscoveryRecallTraceError, match="NO_TRIGGER_PROOF_REQUIRED"):
        replace(valid, evaluation_attempted=False)
    with pytest.raises(DiscoveryRecallTraceError, match="NO_TRIGGER_PROOF_REQUIRED"):
        replace(valid, scope_state=FunnelScopeState.SCOPE_UNKNOWN)
    with pytest.raises(DiscoveryRecallTraceError, match="NO_TRIGGER_PROOF_REQUIRED"):
        replace(valid, no_trigger_reason_code=None)
    with pytest.raises(DiscoveryRecallTraceError, match="NO_TRIGGER_PROOF_REQUIRED"):
        replace(valid, source_lineage=())


def test_explicit_scope_and_universe_states_cannot_be_reinterpreted_as_negative_trigger():
    base = emitted_trace()
    scoped = replace(
        base,
        state=PerSecurityTraceState.NOT_IN_FUNNEL_SCOPE,
        scope_state=FunnelScopeState.NOT_IN_SCOPE,
        trace_basis=PerSecurityTraceBasis.BATCH_FUNNEL_CAPABILITY,
        evaluation_attempted=False,
        required_input_readiness=RequiredInputReadiness.NOT_APPLICABLE,
        source_freshness=SourceFreshnessState.NOT_APPLICABLE,
        lead_ids=(), source_lineage=(), blocker_reason_codes=("CONTEXTUAL_SCOPE_EXCLUDED",),
    )
    assert scoped.state is PerSecurityTraceState.NOT_IN_FUNNEL_SCOPE
    with pytest.raises(DiscoveryRecallTraceError, match="SCOPE_CONTRADICTION"):
        replace(scoped, evaluation_attempted=True)
    outside = trace_security(discovery=sector_batch(), canonical_instrument_id=OTHER, funnel_id=F.SECTOR_ROTATION)
    assert outside.universe_membership is UniverseMembershipState.INELIGIBLE
    assert outside.state is PerSecurityTraceState.UNIVERSE_INELIGIBLE


@pytest.mark.parametrize(("funnel", "expected"), [
    (F.NEWS_CATALYST, PerSecurityTraceState.POLICY_BLOCKED),
    (F.EMERGING_COMPOUNDER, PerSecurityTraceState.NOT_IMPLEMENTED),
    (F.MOMENTUM, PerSecurityTraceState.SOURCE_NOT_OPERATIONAL),
])
def test_global_capability_is_not_a_fake_per_security_evaluation(funnel, expected):
    trace = trace_security(discovery=sector_batch(), canonical_instrument_id=SECURITY, funnel_id=funnel)
    assert trace.state is expected
    assert trace.trace_basis is PerSecurityTraceBasis.BATCH_FUNNEL_CAPABILITY
    assert trace.scope_state is FunnelScopeState.SCOPE_UNKNOWN
    assert not trace.evaluation_attempted
    assert not trace.lead_ids


def test_inflection_and_compounder_absence_remain_unknown_without_source_level_proof():
    batch = _run({F.FUNDAMENTAL_INFLECTION: (_inflection(),)}, ids=(SECURITY, OTHER))
    unknown = trace_security(discovery=batch, canonical_instrument_id=OTHER, funnel_id=F.FUNDAMENTAL_INFLECTION)
    compounder = trace_security(discovery=batch, canonical_instrument_id=SECURITY, funnel_id=F.COMPOUNDER)
    assert unknown.state is PerSecurityTraceState.PER_SECURITY_EVALUATION_UNKNOWN
    assert compounder.state is PerSecurityTraceState.PER_SECURITY_EVALUATION_UNKNOWN
    assert not unknown.evaluation_attempted and not compounder.evaluation_attempted


@pytest.mark.parametrize(("state", "readiness", "freshness", "reason"), [
    (PerSecurityTraceState.DATA_INSUFFICIENT, RequiredInputReadiness.MISSING, SourceFreshnessState.NOT_APPLICABLE, "FINANCIAL_FACTS_MISSING"),
    (PerSecurityTraceState.EVIDENCE_CONFLICTED, RequiredInputReadiness.CONFLICTED, SourceFreshnessState.NOT_APPLICABLE, "SOURCE_CONFLICT"),
    (PerSecurityTraceState.STALE, RequiredInputReadiness.STALE, SourceFreshnessState.STALE, "SOURCE_STALE"),
])
def test_exact_individual_blockers_require_lineage_readiness_and_reason(state, readiness, freshness, reason):
    blocked = replace(
        emitted_trace(), state=state, lead_ids=(), no_trigger_reason_code=None,
        required_input_readiness=readiness, source_freshness=freshness,
        blocker_reason_codes=(reason,),
    )
    assert blocked.state is state
    with pytest.raises(DiscoveryRecallTraceError, match="INDIVIDUAL_BLOCKER_PROOF_REQUIRED"):
        replace(blocked, source_lineage=())
    with pytest.raises(DiscoveryRecallTraceError, match="BLOCKER_REASON_REQUIRED"):
        replace(blocked, blocker_reason_codes=())


@pytest.mark.parametrize("funnel", (F.PRE_BREAKOUT, F.COMPOUNDER, F.POLICY_TRANSMISSION))
def test_executed_empty_pre_breakout_compounder_and_policy_reads_remain_unknown(funnel):
    trace = trace_security(discovery=sector_batch(), canonical_instrument_id=SECURITY, funnel_id=funnel)
    assert trace.state is PerSecurityTraceState.PER_SECURITY_EVALUATION_UNKNOWN
    assert trace.scope_state is FunnelScopeState.SCOPE_UNKNOWN
    assert not trace.evaluation_attempted


def test_audit_is_compact_deterministic_and_preserves_capability_vs_trace_counts():
    inflection = _inflection()
    batch = _run({
        F.SECTOR_ROTATION: (_sector_run(ids=(SECURITY, OTHER)),),
        F.FUNDAMENTAL_INFLECTION: (inflection,),
    }, ids=(SECURITY, OTHER, inflection.canonical_instrument_id))
    first = audit_per_security_traces(discovery=batch)
    second = audit_per_security_traces(discovery=batch)
    assert first == second
    assert len(first.capability_traces) == 14
    assert len(first.emitted_traces) == 3
    sector = next(item for item in first.per_funnel if item.funnel_id is F.SECTOR_ROTATION)
    assert sector.executed and sector.lead_emitted_trace_count == 2
    assert sector.evaluated_no_trigger_trace_count == 0
    assert sector.per_security_unknown_query_count == 1
    news = next(item for item in first.per_funnel if item.funnel_id is F.NEWS_CATALYST)
    assert not news.executed and news.capability_state is PerSecurityTraceState.POLICY_BLOCKED
    assert json.loads(serialize_per_security_trace(first))["fingerprint"] == first.fingerprint


def test_source_input_order_cannot_change_emitted_trace_or_audit_identity():
    first_run = _sector_run(ids=(SECURITY,))
    second_run = _sector_run(ids=(OTHER,))
    first = _run({F.SECTOR_ROTATION: (first_run, second_run)}, ids=(SECURITY, OTHER))
    second = _run({F.SECTOR_ROTATION: (second_run, first_run)}, ids=(SECURITY, OTHER))
    assert emitted_lead_traces(discovery=first) == emitted_lead_traces(discovery=second)
    assert audit_per_security_traces(discovery=first) == audit_per_security_traces(discovery=second)


def test_tampering_future_evidence_duplicates_and_conflicts_fail_closed():
    trace = emitted_trace()
    future = replace(trace.source_lineage[0], known_at=T + timedelta(microseconds=1))
    with pytest.raises(DiscoveryRecallTraceError, match="FUTURE_EVIDENCE"):
        replace(trace, source_lineage=(future,))
    conflicting = replace(trace.source_lineage[0], reference_fingerprint="sha256:" + "0" * 64)
    with pytest.raises(DiscoveryRecallTraceError, match="LINEAGE_CONFLICT"):
        replace(trace, source_lineage=(trace.source_lineage[0], conflicting))
    object.__setattr__(trace, "fingerprint", "sha256:" + "0" * 64)
    with pytest.raises(DiscoveryRecallTraceError, match="TRACE_TAMPERED"):
        trace.verify()


def test_audit_rejects_duplicate_traces_and_tampered_nested_capability():
    audit = audit_per_security_traces(discovery=sector_batch())
    with pytest.raises(DiscoveryRecallTraceError, match="TRACES_CONFLICT"):
        replace(audit, emitted_traces=(audit.emitted_traces[0], audit.emitted_traces[0]))
    capability = audit.capability_traces[0]
    object.__setattr__(capability, "fingerprint", "sha256:" + "0" * 64)
    with pytest.raises(DiscoveryRecallTraceError, match="CAPABILITY_TAMPERED"):
        audit.verify()


def test_reference_matcher_receipt_is_a_safe_narrowing_not_a_failure_classification():
    base = emitted_trace()
    no_trigger = replace(
        base, state=PerSecurityTraceState.EVALUATED_NO_TRIGGER, lead_ids=(),
        no_trigger_reason_code="COMPRESSION_CRITERIA_NOT_MET",
    )
    receipt = as_reference_matching_evaluation(no_trigger)
    assert receipt.state is PerSecurityDiscoveryState.EVALUATED_NO_TRIGGER
    assert receipt.discovery_batch_id == no_trigger.discovery_batch_id
    unknown = as_reference_matching_evaluation(trace_security(
        discovery=sector_batch(ids=(SECURITY, OTHER), sources={F.SECTOR_ROTATION: (_sector_run(ids=(SECURITY,)),)}),
        canonical_instrument_id=OTHER, funnel_id=F.SECTOR_ROTATION,
    ))
    assert unknown.state is PerSecurityDiscoveryState.NOT_EVALUATED


def test_static_boundaries_no_clock_io_brain_action_or_discovery_mutation():
    source = Path(module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    calls = {item.func.attr for item in ast.walk(tree) if isinstance(item, ast.Call) and isinstance(item.func, ast.Attribute)}
    assert not calls & {"now", "utcnow", "connect", "execute", "save", "write", "open", "run", "score", "rank"}
    imports = [item.module for item in ast.walk(tree) if isinstance(item, ast.ImportFrom)]
    assert not any(item and item.startswith(("app.api", "app.portfolio", "app.paper", "app.signals", "app.storage", "app.runtime", "app.broker", "sqlite3")) for item in imports)
    assert "DISCOVERY_FAILURE" not in source
    assert not any(word in source for word in ("BUY", "SELL", "ROTATE", "entry_price", "target_price", "quantity"))
