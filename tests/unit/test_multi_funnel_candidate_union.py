from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

import app.intelligence.multi_funnel_candidate_union as module
from app.intelligence.multi_funnel_candidate_union import (
    CandidatePoolStatus,
    CandidateUnionError,
    CandidateUnionExclusion,
    CandidateUnionExclusionState,
    CandidateUnionReason,
    CanonicalDiscoveryPoolItem,
    DiscoveryCandidateOrigin,
    candidate_union_payload,
    serialize_candidate_union,
    union_discovery_candidates,
)
from app.intelligence.multi_funnel_discovery import (
    CanonicalDiscoveryLead,
    DiscoveryDataQualityState,
    DiscoveryFunnelId,
    DiscoveryHorizon,
    DiscoveryLeadReadiness,
    DiscoveryLineageReference,
    DiscoveryReferenceKind,
    DiscoverySourceLayer,
    DiscoveryTriggerCode,
)
from app.intelligence.multi_funnel_discovery_adapters import (
    DiscoveryAdapterCoverage,
    DiscoveryAdapterCoverageState,
    DiscoveryAdapterResult,
    DiscoveryAdapterState,
)


AS_OF = datetime(2026, 9, 4, 19, 30, 59, 533938, tzinfo=UTC)
FP_A = "sha256:" + "a" * 64
FP_B = "sha256:" + "b" * 64


def _lead(
    *,
    instrument: str = "NSE:INE000A01001",
    funnel: DiscoveryFunnelId = DiscoveryFunnelId.PRE_BREAKOUT,
    source: str = "receipt:one",
    fingerprint: str = FP_A,
    as_of: datetime = AS_OF,
    known_at: datetime | None = None,
    issuer: str | None = "issuer:one",
    blockers: tuple[str, ...] = (),
) -> CanonicalDiscoveryLead:
    trigger = {
        DiscoveryFunnelId.PRE_BREAKOUT: DiscoveryTriggerCode.GOVERNED_PREBREAKOUT_SETUP_AVAILABLE,
        DiscoveryFunnelId.SECTOR_ROTATION: DiscoveryTriggerCode.SECTOR_ROTATION_STATE,
        DiscoveryFunnelId.FUNDAMENTAL_INFLECTION: DiscoveryTriggerCode.INFLECTION_ACCOUNTING_OBSERVATION_AVAILABLE,
    }[funnel]
    readiness = DiscoveryLeadReadiness.RESEARCH_INSPECTION if funnel is DiscoveryFunnelId.FUNDAMENTAL_INFLECTION else DiscoveryLeadReadiness.READY_FOR_INSPECTION
    horizons = (DiscoveryHorizon.LONG_TERM, DiscoveryHorizon.POSITIONAL) if funnel is DiscoveryFunnelId.FUNDAMENTAL_INFLECTION else (DiscoveryHorizon.POSITIONAL,)
    return CanonicalDiscoveryLead(
        canonical_instrument_id=instrument,
        issuer_id=issuer,
        funnel_id=funnel,
        funnel_version="v1",
        discovery_as_of=as_of,
        source_layer=DiscoverySourceLayer.DATA if funnel is not DiscoveryFunnelId.PRE_BREAKOUT else DiscoverySourceLayer.INTERPRETATION,
        trigger_codes=(trigger,),
        readiness=readiness,
        data_quality=DiscoveryDataQualityState.VERIFIED,
        lineage=(DiscoveryLineageReference(source, fingerprint, DiscoveryReferenceKind.RECEIPT, known_at or as_of),),
        intended_horizons=horizons,
        blocker_codes=blockers,
    )


def _adapter(
    funnel: DiscoveryFunnelId,
    leads: tuple[CanonicalDiscoveryLead, ...],
    *,
    state: DiscoveryAdapterCoverageState | None = None,
) -> DiscoveryAdapterResult:
    coverage = DiscoveryAdapterCoverage(
        funnel, DiscoveryAdapterState.ADAPTER_ACTIVE,
        state or (DiscoveryAdapterCoverageState.LEADS_EMITTED if leads else DiscoveryAdapterCoverageState.EVALUATED_NO_LEADS),
        len(leads), len({item.canonical_instrument_id for item in leads}),
        tuple(sorted(item.lead_id for item in leads)),
    )
    return DiscoveryAdapterResult(funnel, AS_OF, leads, coverage)


def test_union_key_is_existing_exact_nse_security_identity_not_issuer_or_symbol():
    first = _lead(instrument="NSE:INE000A01001", issuer="issuer:shared")
    second = _lead(instrument="NSE:INE000A01002", issuer="issuer:shared", source="receipt:two")
    batch = union_discovery_candidates(as_of=AS_OF, adapter_results=(_adapter(DiscoveryFunnelId.PRE_BREAKOUT, (first, second)),))
    assert [item.canonical_instrument_id for item in batch.candidates] == ["NSE:INE000A01001", "NSE:INE000A01002"]
    assert all(item.issuer_ids == ("issuer:shared",) for item in batch.candidates)
    assert "symbol" not in module.CanonicalDiscoveryPoolItem.__dataclass_fields__


def test_cross_funnel_same_security_is_one_pool_item_with_all_origins():
    pre = _lead()
    sector = _lead(funnel=DiscoveryFunnelId.SECTOR_ROTATION, source="sector:one", fingerprint=FP_B)
    batch = union_discovery_candidates(as_of=AS_OF, adapter_results=(
        _adapter(DiscoveryFunnelId.PRE_BREAKOUT, (pre,)), _adapter(DiscoveryFunnelId.SECTOR_ROTATION, (sector,)),
    ))
    item = batch.candidates[0]
    assert item.status is CandidatePoolStatus.CANDIDATE_FOR_SHARED_BRAIN_INSPECTION
    assert tuple(value.value for value in item.funnel_ids) == ("PRE_BREAKOUT", "SECTOR_ROTATION")
    assert item.distinct_funnel_count == 2
    assert {origin.origin_id for origin in item.origins} == {pre.lead_id, sector.lead_id}
    assert batch.multi_funnel_security_count == 1


def test_same_lead_replay_is_deduplicated_without_duplicate_coverage():
    result = _adapter(DiscoveryFunnelId.PRE_BREAKOUT, (_lead(),))
    batch = union_discovery_candidates(as_of=AS_OF, adapter_results=(result, result))
    assert batch.input_lead_count == 2
    assert batch.exact_duplicate_lead_count == 1
    assert len(batch.candidates[0].origins) == 1
    assert len(batch.funnel_coverage) == 1


def test_same_funnel_distinct_source_receipts_remain_distinct_origins():
    first = _lead(source="inflection:consolidated", fingerprint=FP_A, funnel=DiscoveryFunnelId.FUNDAMENTAL_INFLECTION)
    second = _lead(source="inflection:standalone", fingerprint=FP_B, funnel=DiscoveryFunnelId.FUNDAMENTAL_INFLECTION)
    batch = union_discovery_candidates(as_of=AS_OF, adapter_results=(_adapter(DiscoveryFunnelId.FUNDAMENTAL_INFLECTION, (first, second)),))
    item = batch.candidates[0]
    assert len(item.origins) == 2
    assert item.distinct_funnel_count == 1
    assert {origin.lead.lineage[0].reference_id for origin in item.origins} == {"inflection:consolidated", "inflection:standalone"}
    assert all(origin.lead.readiness is DiscoveryLeadReadiness.RESEARCH_INSPECTION for origin in item.origins)


def test_horizon_and_trigger_lineage_are_factual_and_no_primary_horizon_is_selected():
    pre = _lead()
    inflection = _lead(funnel=DiscoveryFunnelId.FUNDAMENTAL_INFLECTION, source="inflection:one", fingerprint=FP_B)
    item = union_discovery_candidates(as_of=AS_OF, adapter_results=(
        _adapter(DiscoveryFunnelId.PRE_BREAKOUT, (pre,)), _adapter(DiscoveryFunnelId.FUNDAMENTAL_INFLECTION, (inflection,)),
    )).candidates[0]
    assert tuple(item.value for item in item.horizon_lineage) == ("LONG_TERM", "POSITIONAL")
    assert not hasattr(item, "primary_horizon") and not hasattr(item, "score")
    assert {code.value for origin in item.origins for code in origin.lead.trigger_codes} == {
        "GOVERNED_PREBREAKOUT_SETUP_AVAILABLE", "INFLECTION_ACCOUNTING_OBSERVATION_AVAILABLE",
    }


def test_invalid_exact_security_identity_is_explicitly_excluded_not_matched_by_text():
    invalid = _lead(instrument="NSE:NOT_AN_ISIN", issuer="issuer:one")
    batch = union_discovery_candidates(as_of=AS_OF, adapter_results=(_adapter(DiscoveryFunnelId.PRE_BREAKOUT, (invalid,)),))
    assert not batch.candidates
    assert batch.identity_blocked_lead_count == 1
    assert batch.exclusions[0].state is CandidateUnionExclusionState.IDENTITY_BLOCKED
    assert batch.exclusions[0].reason is CandidateUnionReason.CANONICAL_NSE_SECURITY_IDENTITY_REQUIRED


def test_future_lead_is_excluded_at_union_cutoff_and_never_reaches_candidate():
    future = _lead(as_of=AS_OF + timedelta(microseconds=1), known_at=AS_OF + timedelta(microseconds=1))
    batch = union_discovery_candidates(as_of=AS_OF, adapter_results=(_adapter(DiscoveryFunnelId.PRE_BREAKOUT, (future,)),))
    assert not batch.candidates
    assert batch.exclusions[0].state is CandidateUnionExclusionState.FUTURE_LEAD_EXCLUDED


def test_conflicting_adapter_results_for_same_funnel_fail_closed_without_input_order_choice():
    first = _adapter(DiscoveryFunnelId.PRE_BREAKOUT, (_lead(),))
    changed = _adapter(DiscoveryFunnelId.PRE_BREAKOUT, (_lead(blockers=("EVIDENCE_PARTIAL",)),))
    with pytest.raises(CandidateUnionError, match="ADAPTER_RESULT_CONFLICT"):
        union_discovery_candidates(as_of=AS_OF, adapter_results=(first, changed))
    with pytest.raises(CandidateUnionError, match="ADAPTER_RESULT_CONFLICT"):
        union_discovery_candidates(as_of=AS_OF, adapter_results=(changed, first))


def test_adapter_coverage_is_retained_and_blocked_is_not_misrepresented_as_no_leads():
    lead_result = _adapter(DiscoveryFunnelId.PRE_BREAKOUT, (_lead(),))
    blocked = _adapter(DiscoveryFunnelId.SECTOR_ROTATION, (), state=DiscoveryAdapterCoverageState.DATA_BLOCKED)
    batch = union_discovery_candidates(as_of=AS_OF, adapter_results=(lead_result, blocked))
    coverage = {item.funnel_id: item.adapter_coverage.state for item in batch.funnel_coverage}
    assert coverage[DiscoveryFunnelId.PRE_BREAKOUT] is DiscoveryAdapterCoverageState.LEADS_EMITTED
    assert coverage[DiscoveryFunnelId.SECTOR_ROTATION] is DiscoveryAdapterCoverageState.DATA_BLOCKED


def test_tampered_adapter_coverage_fails_closed_before_union_can_preserve_it():
    result = _adapter(DiscoveryFunnelId.PRE_BREAKOUT, (_lead(),))
    object.__setattr__(result.coverage, "state", DiscoveryAdapterCoverageState.DATA_BLOCKED)
    with pytest.raises(CandidateUnionError, match="ADAPTER_COVERAGE_FINGERPRINT_MISMATCH"):
        union_discovery_candidates(as_of=AS_OF, adapter_results=(result,))


def test_candidate_identity_and_content_fingerprint_are_distinct_and_tamper_evident():
    first = DiscoveryCandidateOrigin(_lead())
    second = DiscoveryCandidateOrigin(_lead(source="receipt:two", fingerprint=FP_B))
    one = CanonicalDiscoveryPoolItem("NSE:INE000A01001", "INE000A01001", AS_OF, (first,), ("issuer:one",))
    two = CanonicalDiscoveryPoolItem("NSE:INE000A01001", "INE000A01001", AS_OF, (first, second), ("issuer:one",))
    assert one.candidate_id == two.candidate_id
    assert one.fingerprint != two.fingerprint
    object.__setattr__(one, "fingerprint", FP_A)
    with pytest.raises(CandidateUnionError, match="POOL_FINGERPRINT_MISMATCH"):
        one.verify()


def test_input_order_is_deterministic_and_serialization_is_stable():
    pre = _adapter(DiscoveryFunnelId.PRE_BREAKOUT, (_lead(),))
    sector = _adapter(DiscoveryFunnelId.SECTOR_ROTATION, (_lead(funnel=DiscoveryFunnelId.SECTOR_ROTATION, source="sector:one", fingerprint=FP_B),))
    first = union_discovery_candidates(as_of=AS_OF, adapter_results=(pre, sector))
    second = union_discovery_candidates(as_of=AS_OF, adapter_results=(sector, pre))
    assert first == second
    assert first.fingerprint == second.fingerprint
    assert serialize_candidate_union(first) == serialize_candidate_union(second)
    assert candidate_union_payload(first)["final_distinct_security_pool_count"] == 1
    assert first.eligible_lead_count == 2


def test_exclusion_construction_rejects_contradictory_state_and_reason():
    origin = DiscoveryCandidateOrigin(_lead(instrument="NSE:NOT_AN_ISIN"))
    with pytest.raises(CandidateUnionError, match="EXCLUSION_REASON_INVALID"):
        CandidateUnionExclusion(origin, CandidateUnionExclusionState.IDENTITY_BLOCKED, CandidateUnionReason.LEAD_AFTER_BATCH_AS_OF)


def test_batch_requires_explicit_matching_adapter_as_of_and_never_uses_runtime_time():
    adapter = _adapter(DiscoveryFunnelId.PRE_BREAKOUT, (_lead(),))
    with pytest.raises(CandidateUnionError, match="ADAPTER_AS_OF_MISMATCH"):
        union_discovery_candidates(as_of=AS_OF + timedelta(microseconds=1), adapter_results=(adapter,))
    with pytest.raises(CandidateUnionError, match="AS_OF_INVALID"):
        union_discovery_candidates(as_of=datetime(2026, 9, 4, 19, 30), adapter_results=(adapter,))


def test_static_boundaries_exclude_scoring_brain_runner_and_forbidden_dependencies():
    source = Path(module.__file__).read_text(encoding="utf-8")
    for forbidden in ("datetime.now", "time.time", "app.storage", "app.portfolio", "app.api", "app.broker", "app.orders", "app.signals", "requests", "httpx"):
        assert forbidden not in source
    assert "DecisionScore" not in source and "SixGates" not in source
    payload = candidate_union_payload(union_discovery_candidates(as_of=AS_OF, adapter_results=(_adapter(DiscoveryFunnelId.PRE_BREAKOUT, (_lead(),)),)))
    forbidden_fields = {"buy", "sell", "hold", "score", "six_gates", "allocation", "quantity", "target", "stop", "portfolio", "order", "broker", "rank"}
    assert forbidden_fields.isdisjoint(payload)
