"""Focused proofs for the discovery-only HSI Internal Technical Radar."""
from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

import app.intelligence.internal_technical_radar as module
from app.intelligence.internal_technical_radar import (
    FifteenMinuteTechnicalInputState,
    INTERNAL_TECHNICAL_RADAR_POLICY_FINGERPRINT,
    InternalTechnicalRadarError,
    PreBreakoutRadarEvidence,
    PreBreakoutRadarEvidenceState,
    TechnicalRadarAuthority,
    TechnicalRadarDiscoveryState,
    TechnicalRadarLiveProductionState,
    TechnicalRadarReason,
    TechnicalRadarRuntimeState,
    TechnicalRadarUniverseScope,
    evaluate_internal_technical_radar,
    internal_technical_radar_payload,
    serialize_internal_technical_radar,
)
from app.market_data.canonical_fifteen_minute_technical_reader import (
    CanonicalFifteenMinuteTechnicalReadMode,
    CanonicalFifteenMinuteTechnicalReadReason,
    read_canonical_prospective_fifteen_minute_bars,
)
from app.market_data.prospective_fifteen_minute_bar import ProspectiveMinuteEvidenceState
from app.production_v1.canonical_setup_activation import CanonicalSetupOpportunity
import app.production_v1.canonical_setup_activation as setup_source
from app.strategies.pre_breakout.candidate_assembly import prebreakout_candidate_fingerprint
from tests.unit.pre_breakout_setup_fixture import assessment
from tests.unit.test_canonical_fifteen_minute_technical_reader import (
    AS_OF as READER_AS_OF,
    _receipt,
    _repository,
    _request,
    _save,
    _session,
)


AS_OF = datetime(2026, 9, 8, 16, tzinfo=UTC)
SECURITY = "NSE:INE000000001"
OTHER_SECURITY = "NSE:INE000000002"
SNAPSHOT_FP = "sha256:" + "b" * 64
POLICY_FP = "sha256:" + "a" * 64


def _opportunity(*, at: datetime = AS_OF - timedelta(minutes=1)) -> CanonicalSetupOpportunity:
    value = CanonicalSetupOpportunity.from_assessment(assessment(at=at))
    object.__setattr__(value.candidate, "instrument_id", SECURITY)
    object.__setattr__(value.candidate, "policy_fingerprint", POLICY_FP)
    object.__setattr__(value.candidate, "fingerprint", prebreakout_candidate_fingerprint(value.candidate))
    object.__setattr__(value, "canonical_instrument_id", SECURITY)
    object.__setattr__(value, "policy_fingerprint", POLICY_FP)
    object.__setattr__(value, "fingerprint", setup_source._fingerprint(value))
    return value


def _scope(
    *,
    selected: tuple[str, ...] = (SECURITY,),
    eligible: tuple[str, ...] = (SECURITY,),
    ready: tuple[str, ...] = (SECURITY,),
    blocked: tuple[str, ...] = (),
    live: tuple[str, ...] = (),
) -> TechnicalRadarUniverseScope:
    return TechnicalRadarUniverseScope(
        "nse-universe:fixture", SNAPSHOT_FP, selected, eligible, ready, blocked, live,
    )


def _available(*, source_as_of: datetime | None = None) -> PreBreakoutRadarEvidence:
    value = _opportunity(at=source_as_of or AS_OF - timedelta(minutes=1))
    return PreBreakoutRadarEvidence(
        SECURITY, PreBreakoutRadarEvidenceState.GOVERNED_SETUP_AVAILABLE,
        value.decision_as_of, value,
    )


def _state(state: PreBreakoutRadarEvidenceState, reason: TechnicalRadarReason) -> PreBreakoutRadarEvidence:
    return PreBreakoutRadarEvidence(SECURITY, state, AS_OF - timedelta(minutes=1), None, (reason,))


def _run(*, evidence: tuple[PreBreakoutRadarEvidence, ...] = (), reads=(), scope=None, as_of=AS_OF):
    return evaluate_internal_technical_radar(
        as_of=as_of, universe_scope=scope or _scope(), pre_breakout_evidence=evidence,
        fifteen_minute_reads=reads,
    )


def _strict_15m(tmp_path, *, state=ProspectiveMinuteEvidenceState.CLOSED, changed=False):
    repository = _repository(tmp_path); session = _session()
    receipt = _receipt(session, state=state)
    _save(repository, receipt)
    if changed:
        _save(repository, _receipt(session, price_offset=100))
    return read_canonical_prospective_fifteen_minute_bars(
        repository=repository,
        request=_request(as_of=READER_AS_OF),
    )


def test_governed_prebreakout_is_the_only_active_v1_discovery_trigger():
    result = _run(evidence=(_available(),))
    outcome = result.outcomes[0]
    assert outcome.discovery_state is TechnicalRadarDiscoveryState.DISCOVERED
    assert outcome.lead is not None
    assert outcome.lead.funnel_id.value == "PRE_BREAKOUT"
    assert result.discovery_leads == (outcome.lead,)
    assert result.triggered_lead_count == 1
    assert result.authority is TechnicalRadarAuthority.DISCOVERY_ONLY
    assert result.runtime_state is TechnicalRadarRuntimeState.NOT_ACTIVE
    assert result.live_production_state is TechnicalRadarLiveProductionState.NOT_READY


@pytest.mark.parametrize("state,reason,expected", [
    (PreBreakoutRadarEvidenceState.NO_CURRENT_GOVERNED_SETUP, TechnicalRadarReason.NO_CURRENT_GOVERNED_SETUP, TechnicalRadarDiscoveryState.NOT_TRIGGERED),
    (PreBreakoutRadarEvidenceState.DATA_INSUFFICIENT, TechnicalRadarReason.PREBREAKOUT_DATA_INSUFFICIENT, TechnicalRadarDiscoveryState.DATA_INSUFFICIENT),
    (PreBreakoutRadarEvidenceState.EVIDENCE_CONFLICTED, TechnicalRadarReason.PREBREAKOUT_EVIDENCE_CONFLICTED, TechnicalRadarDiscoveryState.EVIDENCE_CONFLICTED),
    (PreBreakoutRadarEvidenceState.POLICY_BLOCKED, TechnicalRadarReason.PREBREAKOUT_POLICY_BLOCKED, TechnicalRadarDiscoveryState.POLICY_BLOCKED),
])
def test_nontrigger_and_not_evaluable_states_remain_distinct(state, reason, expected):
    result = _run(evidence=(_state(state, reason),))
    assert result.outcomes[0].discovery_state is expected
    assert result.outcomes[0].lead is None
    assert result.evaluated_count == (1 if expected is TechnicalRadarDiscoveryState.NOT_TRIGGERED else 0)


def test_missing_prebreakout_query_evidence_is_data_insufficient_not_not_triggered():
    result = _run()
    assert result.outcomes[0].discovery_state is TechnicalRadarDiscoveryState.DATA_INSUFFICIENT
    assert result.outcomes[0].reason_codes == (TechnicalRadarReason.PREBREAKOUT_EVIDENCE_NOT_SUPPLIED,)
    assert result.not_evaluable_count == 1 and result.triggered_lead_count == 0


def test_future_canonical_source_evidence_is_excluded_from_earlier_cutoff():
    future_source = _available(source_as_of=AS_OF + timedelta(microseconds=1))
    result = _run(evidence=(future_source,))
    assert result.outcomes[0].reason_codes == (TechnicalRadarReason.PREBREAKOUT_SOURCE_AS_OF_AFTER_CUTOFF,)


def test_duplicate_exact_evidence_is_idempotent_but_conflicting_duplicate_is_rejected():
    evidence = _available()
    first = _run(evidence=(evidence, evidence))
    second = _run(evidence=(evidence,))
    assert first == second and first.run_id == second.run_id
    changed = _available(source_as_of=evidence.source_as_of + timedelta(seconds=1))
    conflicted = _run(evidence=(evidence, changed))
    assert conflicted.outcomes[0].discovery_state is TechnicalRadarDiscoveryState.EVIDENCE_CONFLICTED


def test_exact_canonical_security_scope_and_provider_capacity_accounting_are_retained():
    scope = _scope(selected=(SECURITY, OTHER_SECURITY), eligible=(SECURITY,), ready=(SECURITY,), blocked=(OTHER_SECURITY,))
    result = _run(evidence=(_state(PreBreakoutRadarEvidenceState.NO_CURRENT_GOVERNED_SETUP, TechnicalRadarReason.NO_CURRENT_GOVERNED_SETUP),), scope=scope)
    assert result.selected_universe_count == 2
    assert result.canonical_eligible_input_count == 1
    assert result.provider_exact_ready_capacity == 1
    assert result.blocked_identity_count == 1
    with pytest.raises(InternalTechnicalRadarError, match="OUTSIDE_SCOPE"):
        _run(evidence=(PreBreakoutRadarEvidence(OTHER_SECURITY, PreBreakoutRadarEvidenceState.NO_CURRENT_GOVERNED_SETUP, AS_OF, reason_codes=(TechnicalRadarReason.NO_CURRENT_GOVERNED_SETUP,)),))


def test_15m_reader_is_strict_pit_provider_neutral_input_only_and_never_a_discovery_trigger(tmp_path):
    read = _strict_15m(tmp_path)
    result = _run(evidence=(_state(PreBreakoutRadarEvidenceState.NO_CURRENT_GOVERNED_SETUP, TechnicalRadarReason.NO_CURRENT_GOVERNED_SETUP),), reads=(read,), as_of=READER_AS_OF)
    assert result.fifteen_minute_coverage.state is FifteenMinuteTechnicalInputState.DATA_INSUFFICIENT
    assert TechnicalRadarReason.CANONICAL_15M_CONTINUITY_POLICY_UNSET in result.fifteen_minute_coverage.reason_codes
    assert result.triggered_lead_count == 0
    assert result.actual_live_fifteen_minute_coverage == 0


@pytest.mark.parametrize("state,reason", [
    (ProspectiveMinuteEvidenceState.INCOMPLETE, TechnicalRadarReason.CANONICAL_15M_OBSERVATION_GAP_OR_INCOMPLETE),
    (ProspectiveMinuteEvidenceState.NO_TRADE_OBSERVED, TechnicalRadarReason.CANONICAL_15M_NO_TRADE_UNMATERIALIZED),
    (ProspectiveMinuteEvidenceState.EVIDENCE_CONFLICTED, TechnicalRadarReason.CANONICAL_15M_EVIDENCE_CONFLICTED),
])
def test_15m_gap_no_trade_and_conflict_preserve_fail_closed_coverage(tmp_path, state, reason):
    read = _strict_15m(tmp_path, state=state)
    result = _run(reads=(read,), as_of=READER_AS_OF)
    assert reason in result.fifteen_minute_coverage.reason_codes
    assert result.fifteen_minute_coverage.ready_security_count == 0
    assert result.triggered_lead_count == 0


def test_15m_future_request_and_current_descriptive_mode_are_rejected_without_substitution(tmp_path):
    read = _strict_15m(tmp_path)
    with pytest.raises(InternalTechnicalRadarError, match="READ_CONTEXT_INVALID"):
        _run(reads=(read,), as_of=READER_AS_OF - timedelta(microseconds=1))
    repository = _repository(tmp_path / "current"); session = _session(); _save(repository, _receipt(session))
    request = _request(mode=CanonicalFifteenMinuteTechnicalReadMode.CURRENT_DESCRIPTIVE, as_of=None)
    current = read_canonical_prospective_fifteen_minute_bars(repository=repository, request=request)
    with pytest.raises(InternalTechnicalRadarError, match="READ_CONTEXT_INVALID"):
        _run(reads=(current,), as_of=READER_AS_OF)


def test_actual_live_coverage_is_explicit_scope_fact_not_test_fixture_coverage(tmp_path):
    read = _strict_15m(tmp_path)
    scope = _scope(live=(SECURITY,))
    result = _run(reads=(read,), scope=scope, as_of=READER_AS_OF)
    assert result.actual_live_fifteen_minute_coverage == 1
    assert result.fifteen_minute_coverage.supplied_security_count == 1


def test_scope_rejects_ambiguous_identity_partition_and_out_of_scope_live_coverage():
    with pytest.raises(InternalTechnicalRadarError, match="PARTITION"):
        _scope(ready=(SECURITY,), blocked=(SECURITY,))
    with pytest.raises(InternalTechnicalRadarError, match="OUTSIDE_UNIVERSE"):
        _scope(live=(OTHER_SECURITY,))
    with pytest.raises(InternalTechnicalRadarError, match="SECURITY_IDS_INVALID"):
        _scope(selected=("NSE:BAD",))


def test_deterministic_replay_timezone_normalization_and_stable_serialization():
    source = _available()
    first = _run(evidence=(source,))
    other = _run(evidence=(source,), as_of=AS_OF.astimezone(timezone(timedelta(hours=5, minutes=30))))
    assert first == other
    assert serialize_internal_technical_radar(first) == serialize_internal_technical_radar(other)
    payload = internal_technical_radar_payload(first)
    assert payload["fingerprint"] == first.fingerprint and payload["policy_fingerprint"] == INTERNAL_TECHNICAL_RADAR_POLICY_FINGERPRINT


def test_identity_and_content_fingerprint_are_distinct_and_tamper_evident():
    discovered = _run(evidence=(_available(),))
    blocked = _run(evidence=(_state(PreBreakoutRadarEvidenceState.POLICY_BLOCKED, TechnicalRadarReason.PREBREAKOUT_POLICY_BLOCKED),))
    assert discovered.run_id != blocked.run_id
    object.__setattr__(discovered, "fingerprint", "sha256:" + "0" * 64)
    with pytest.raises(InternalTechnicalRadarError, match="RUN_TAMPERED"):
        discovered.verify()


def test_contracts_are_immutable_and_forbidden_action_surface_is_absent():
    result = _run(evidence=(_available(),))
    with pytest.raises(FrozenInstanceError):
        result.as_of = AS_OF
    payload = internal_technical_radar_payload(result)
    forbidden = {"buy", "sell", "hold", "rotate", "harvest", "entry", "target", "stop", "score", "six_gates", "portfolio", "order", "broker", "alert"}
    assert forbidden.isdisjoint(payload)
    assert forbidden.isdisjoint(payload["outcomes"][0]["lead"])


def test_no_raw_provider_data_and_no_30m_1h_4h_substitution_or_forbidden_dependencies_exist():
    with pytest.raises(InternalTechnicalRadarError, match="READ_TUPLE_REQUIRED"):
        _run(reads=(object(),))
    source = Path(module.__file__).read_text(encoding="utf-8").lower()
    forbidden_imports = (
        "app.signals", "app.api", "app.portfolio", "app.broker", "app.orders",
        "app.dhan", "websocket", "requests.", "httpx", "sqlite", "postgres",
    )
    assert all(item not in source for item in forbidden_imports)
    assert "datetime.now" not in source and "time.time" not in source
    assert "thirty_minutes" not in source and "one_hour" not in source and "four_hours" not in source


def test_no_rule_registry_mutation_or_new_score_or_prebreakout_threshold_definition_exists():
    source = Path(module.__file__).read_text(encoding="utf-8").lower()
    assert "radar_score" not in source and "technical_radar_score" not in source
    assert "canonicaldiagnostic" not in source and "sixgate" not in source
    assert "prebreakoutpolicy" not in source


def test_reason_codes_are_bounded_and_nonsecret_even_for_bad_canonical_source():
    source = _available()
    object.__setattr__(source.opportunity, "fingerprint", "sha256:" + "0" * 64)
    result = _run(evidence=(source,))
    assert result.outcomes[0].discovery_state is TechnicalRadarDiscoveryState.EVIDENCE_CONFLICTED
    assert result.outcomes[0].reason_codes == (TechnicalRadarReason.PREBREAKOUT_CANONICAL_SOURCE_INVALID,)
    assert "secret" not in serialize_internal_technical_radar(result).lower()


def test_canonical_15m_reader_reason_is_preserved_without_forward_fill(tmp_path):
    read = _strict_15m(tmp_path, state=ProspectiveMinuteEvidenceState.NO_TRADE_OBSERVED)
    assert CanonicalFifteenMinuteTechnicalReadReason.RECEIPT_NO_TRADE_NOT_MATERIALIZED in read.reasons
    result = _run(reads=(read,), as_of=READER_AS_OF)
    assert result.fifteen_minute_coverage.no_trade_unmaterialized_security_count == 1
