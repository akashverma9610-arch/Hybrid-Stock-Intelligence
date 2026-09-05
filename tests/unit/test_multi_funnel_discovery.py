from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

import app.intelligence.multi_funnel_discovery as module
from app.intelligence.multi_funnel_discovery import (
    CanonicalDiscoveryLead,
    DiscoveryCoverageState,
    DiscoveryDataQualityState,
    DiscoveryFunnelId,
    DiscoveryFunnelStatus,
    DiscoveryHorizon,
    DiscoveryLeadReadiness,
    DiscoveryLineageReference,
    DiscoveryReferenceKind,
    DiscoverySourceLayer,
    DiscoveryTriggerCode,
    FunnelCoverage,
    MultiFunnelDiscoveryBatch,
    MultiFunnelDiscoveryError,
    discovery_lead_payload,
    multi_funnel_discovery_registry,
    serialize_discovery_lead,
)


AS_OF = datetime(2026, 9, 5, 9, 0, tzinfo=UTC)
FP_A = "sha256:" + "a" * 64
FP_B = "sha256:" + "b" * 64


def _lineage(*, known_at: datetime = AS_OF, reference_id: str = "receipt:one") -> DiscoveryLineageReference:
    return DiscoveryLineageReference(reference_id, FP_A, DiscoveryReferenceKind.RECEIPT, known_at)


def _lead(**changes) -> CanonicalDiscoveryLead:
    values = dict(
        canonical_instrument_id="NSE:INE000A01001",
        funnel_id=DiscoveryFunnelId.PRE_BREAKOUT,
        funnel_version="v1",
        discovery_as_of=AS_OF,
        source_layer=DiscoverySourceLayer.INTERPRETATION,
        trigger_codes=(DiscoveryTriggerCode.GOVERNED_PREBREAKOUT_SETUP_AVAILABLE,),
        readiness=DiscoveryLeadReadiness.READY_FOR_INSPECTION,
        data_quality=DiscoveryDataQualityState.VERIFIED,
        lineage=(_lineage(),),
        intended_horizons=(DiscoveryHorizon.POSITIONAL,),
    )
    values.update(changes)
    return CanonicalDiscoveryLead(**values)


def test_registry_is_complete_deterministic_and_inventory_truthful():
    first, second = multi_funnel_discovery_registry(), multi_funnel_discovery_registry()
    assert first == second
    assert first.fingerprint == second.fingerprint
    assert {entry.funnel_id for entry in first.entries} == set(DiscoveryFunnelId)
    states = {status: sum(entry.status is status for entry in first.entries) for status in DiscoveryFunnelStatus}
    assert states == {
        DiscoveryFunnelStatus.OPERATIONAL: 2,
        DiscoveryFunnelStatus.PARTIAL: 6,
        DiscoveryFunnelStatus.RESEARCH_SHADOW: 3,
        DiscoveryFunnelStatus.CONTRACT_ONLY: 0,
        DiscoveryFunnelStatus.DATA_BLOCKED: 0,
        DiscoveryFunnelStatus.POLICY_BLOCKED: 1,
        DiscoveryFunnelStatus.NOT_IMPLEMENTED: 2,
    }
    assert first.get(DiscoveryFunnelId.FUNDAMENTAL_INFLECTION).status is DiscoveryFunnelStatus.RESEARCH_SHADOW
    assert first.get(DiscoveryFunnelId.EMERGING_COMPOUNDER).status is DiscoveryFunnelStatus.NOT_IMPLEMENTED


def test_registry_rejects_missing_or_tampered_catalogue():
    registry = multi_funnel_discovery_registry()
    with pytest.raises(MultiFunnelDiscoveryError, match="CATALOGUE_INCOMPLETE"):
        type(registry)(registry.entries[:-1])
    object.__setattr__(registry, "fingerprint", FP_A)
    with pytest.raises(MultiFunnelDiscoveryError, match="FINGERPRINT_MISMATCH"):
        registry.verify()


def test_lead_is_immutable_pit_safe_and_stably_serialized():
    first = _lead()
    equivalent_as_of = AS_OF.astimezone(timezone(timedelta(hours=5, minutes=30)))
    second = _lead(discovery_as_of=equivalent_as_of)
    assert first.discovery_as_of == second.discovery_as_of == AS_OF
    assert first.lead_id == second.lead_id
    assert serialize_discovery_lead(first) == serialize_discovery_lead(second)
    assert first.readiness is DiscoveryLeadReadiness.READY_FOR_INSPECTION
    assert "decision" not in serialize_discovery_lead(first).lower()
    with pytest.raises((AttributeError, TypeError)):
        first.funnel_id = DiscoveryFunnelId.COMPOUNDER


def test_future_lineage_and_empty_or_conflicting_lineage_fail_closed():
    with pytest.raises(MultiFunnelDiscoveryError, match="FUTURE_LINEAGE"):
        _lead(lineage=(_lineage(known_at=AS_OF + timedelta(microseconds=1)),))
    with pytest.raises(MultiFunnelDiscoveryError, match="LINEAGE_REQUIRED"):
        _lead(lineage=())
    with pytest.raises(MultiFunnelDiscoveryError, match="DUPLICATE_OR_CONFLICT"):
        _lead(lineage=(_lineage(), DiscoveryLineageReference("receipt:one", FP_B, DiscoveryReferenceKind.RECEIPT, AS_OF)))


def test_lead_rejects_noncanonical_collections_and_invalid_ids():
    with pytest.raises(MultiFunnelDiscoveryError, match="TRIGGER_CODES_INVALID"):
        _lead(trigger_codes=(DiscoveryTriggerCode.GOVERNED_PREBREAKOUT_SETUP_AVAILABLE, DiscoveryTriggerCode.GOVERNED_PREBREAKOUT_SETUP_AVAILABLE))
    with pytest.raises(MultiFunnelDiscoveryError, match="INSTRUMENT_INVALID"):
        _lead(canonical_instrument_id="bad id")
    with pytest.raises(MultiFunnelDiscoveryError, match="FUNNEL_VERSION_INVALID"):
        _lead(funnel_version="v 1")


def test_research_shadow_posture_is_limited_to_registered_shadow_families():
    with pytest.raises(MultiFunnelDiscoveryError, match="RESEARCH_POSTURE_INVALID"):
        _lead(readiness=DiscoveryLeadReadiness.RESEARCH_INSPECTION)
    shadow = _lead(
        funnel_id=DiscoveryFunnelId.COMPOUNDER,
        source_layer=DiscoverySourceLayer.DATA,
        trigger_codes=(DiscoveryTriggerCode.COMPOUNDER_PROSPECTIVE_OBSERVATION_AVAILABLE,),
        readiness=DiscoveryLeadReadiness.RESEARCH_INSPECTION,
        intended_horizons=(DiscoveryHorizon.LONG_TERM,),
    )
    assert shadow.readiness is DiscoveryLeadReadiness.RESEARCH_INSPECTION


def test_identity_and_content_fingerprint_are_separate_and_tamper_evident():
    value = _lead()
    changed = _lead(blocker_codes=("EVIDENCE_PARTIAL",))
    assert value.lead_id == changed.lead_id
    assert value.fingerprint != changed.fingerprint
    object.__setattr__(value, "fingerprint", FP_A)
    with pytest.raises(MultiFunnelDiscoveryError, match="FINGERPRINT_MISMATCH"):
        value.verify()


def test_payload_contains_only_inspection_contract_fields():
    payload = discovery_lead_payload(_lead())
    forbidden = {"buy", "sell", "hold", "score", "six_gates", "allocation", "quantity", "target", "stop", "portfolio", "order", "broker"}
    assert forbidden.isdisjoint(payload)
    assert payload["trigger_codes"] == ("GOVERNED_PREBREAKOUT_SETUP_AVAILABLE",)
    assert payload["source_layer"] == "INTERPRETATION"


def _coverage(*, state: DiscoveryCoverageState, leads: tuple[str, ...] = ()) -> FunnelCoverage:
    return FunnelCoverage(DiscoveryFunnelId.PRE_BREAKOUT, 100, 100 if state is not DiscoveryCoverageState.NOT_EVALUATED else 0, 90 if state is not DiscoveryCoverageState.NOT_EVALUATED else 0, leads, 5, 0, 3, 1, 1, 0, state)


def test_coverage_makes_no_leads_distinct_from_not_evaluated_and_blocked():
    assert _coverage(state=DiscoveryCoverageState.EVALUATED_NO_LEADS).state is DiscoveryCoverageState.EVALUATED_NO_LEADS
    assert _coverage(state=DiscoveryCoverageState.NOT_EVALUATED).securities_examined == 0
    with pytest.raises(MultiFunnelDiscoveryError, match="LEADS_REQUIRED"):
        _coverage(state=DiscoveryCoverageState.LEADS_EMITTED)
    with pytest.raises(MultiFunnelDiscoveryError, match="NO_LEADS_CONTRADICTION"):
        _coverage(state=DiscoveryCoverageState.EVALUATED_NO_LEADS, leads=("discovery-lead:one",))


def test_batch_is_explicit_as_of_and_preserves_per_funnel_coverage_without_union():
    registry = multi_funnel_discovery_registry()
    lead = _lead()
    coverage = _coverage(state=DiscoveryCoverageState.LEADS_EMITTED, leads=(lead.lead_id,))
    batch = MultiFunnelDiscoveryBatch(AS_OF, "nifty500:snapshot", FP_A, registry, (DiscoveryFunnelId.PRE_BREAKOUT,), (DiscoveryFunnelId.PRE_BREAKOUT,), (), (coverage,), (lead.lead_id,))
    batch.verify()
    assert batch.as_of == AS_OF
    assert batch.emitted_lead_ids == (lead.lead_id,)
    assert "candidate" not in module._batch_payload(batch)


def test_batch_rejects_missing_requested_or_untracked_funnel_coverage():
    registry = multi_funnel_discovery_registry()
    coverage = _coverage(state=DiscoveryCoverageState.EVALUATED_NO_LEADS)
    with pytest.raises(MultiFunnelDiscoveryError, match="FUNNEL_NOT_REQUESTED"):
        MultiFunnelDiscoveryBatch(AS_OF, "nifty500:snapshot", FP_A, registry, (DiscoveryFunnelId.COMPOUNDER,), (DiscoveryFunnelId.PRE_BREAKOUT,), (), (coverage,), ())
    with pytest.raises(MultiFunnelDiscoveryError, match="COVERAGE_INVALID"):
        MultiFunnelDiscoveryBatch(AS_OF, "nifty500:snapshot", FP_A, registry, (DiscoveryFunnelId.PRE_BREAKOUT,), (), (), (coverage,), ())


def test_no_runtime_clock_or_forbidden_dependency_imports_exist():
    source = Path(module.__file__).read_text(encoding="utf-8")
    assert "datetime.now" not in source and "time.time" not in source
    assert "from app.signals" not in source and "import app.signals" not in source
    assert "from app.portfolio" not in source and "from app.storage" not in source
    assert "from app.api" not in source and "from app.broker" not in source and "from app.orders" not in source


def test_no_registry_entry_is_an_active_trade_or_candidate_qualification():
    registry = multi_funnel_discovery_registry()
    rendered = "\n".join(entry.output_lead_type for entry in registry.entries)
    assert "CANDIDATE" not in rendered
    assert "BUY" not in rendered and "SELL" not in rendered and "ROTATE" not in rendered
