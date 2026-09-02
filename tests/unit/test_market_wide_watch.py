from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.domain.models import DiagnosticResult, DiagnosticStrategyLineageType, StrategyVersionReference
from app.api.schemas.market_wide_watch import MarketWideWatchResponse
from app.api.dependencies import get_market_wide_watch_service
from app.api.main import create_app
from app.historical.models import InstrumentLifecycle, UniverseMembership
from app.historical.security_master import HistoricalSecurityMasterStore
from app.intelligence.market_wide_watch import (
    MarketWideWatchService,
    MarketWideWatchStore,
    WatchClassification,
    WatchStatus,
)
from app.intelligence.external_intelligence import (
    CompanyExposure, EvidenceVersion, EventType, ExternalEvent, ExposureType, Fact,
    Interpretation, Materiality, PolicyStage, SourceEvidence,
)
from app.intelligence.opportunity_archetypes import OpportunityArchetype, OpportunityArchetypeRouter, SetupPolicyRoute
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository
from app.universe_analysis.models import NseEquityInstrument
from app.universe_analysis.service import CoreUniverseAnalysisStore


T = datetime(2026, 9, 1, tzinfo=UTC)


class _Diagnostics:
    def __init__(self, values): self.values = values
    def latest_canonical_diagnostic_results(self, canonical_instrument_id, *, as_of): return self.values.get(canonical_instrument_id, ())


class _Governance:
    def list_canonical_decision_scorecards(self, _instrument_id): return ()
    def list_canonical_execution_gate_evaluations(self, _instrument_id): return ()
    def list_prebreakout_setup_assessments(self, canonical_instrument_id=None): return ()


def _result(instrument_id: str, rule_id: str, result: str) -> DiagnosticResult:
    return DiagnosticResult(
        id=f"diagnostic:{instrument_id}:{rule_id}", instrument_id=instrument_id, rule_id=rule_id,
        strategy_version=StrategyVersionReference("canonical-universe-analysis", "v1"), result=result,
        score=None, confidence=1.0, evidence_ids=(f"evidence:{rule_id}",), input_observation_ids=(),
        evaluated_at=T, as_of_timestamp=T,
        strategy_lineage_type=DiagnosticStrategyLineageType.CANONICAL_DIAGNOSTIC_STRATEGY,
        canonical_strategy_fingerprint="strategy-fingerprint", canonical_limitations_fingerprint="limitations-fingerprint",
        diagnostic_fingerprint=f"sha256:diagnostic-{rule_id}",
    )


def _instrument(identifier: str, symbol: str) -> NseEquityInstrument:
    return NseEquityInstrument(identifier, symbol, identifier.removeprefix("NSE:"), "Industrials", None, "ACTIVE", None, True, T, "NSE_OFFICIAL", main_board=True, company_name=f"{symbol} Ltd")


def test_market_wide_watch_projects_existing_diagnostics_without_top3_or_actionability_mutation():
    repository = SQLiteCoreApiSnapshotRepository()
    universe = CoreUniverseAnalysisStore(repository)
    alpha, beta = _instrument("NSE:INE000000001", "ALPHA"), _instrument("NSE:INE000000002", "BETA")
    universe.save_instrument(alpha); universe.save_instrument(beta)
    memberships = HistoricalSecurityMasterStore(repository)
    for index, instrument in enumerate((alpha, beta)):
        memberships.save_membership(UniverseMembership(f"membership:{index}", instrument.instrument_id, "NIFTY_500", T, None, T, "NSE", "exact", InstrumentLifecycle.ACTIVE), as_of=T)
    diagnostics = _Diagnostics({
        alpha.instrument_id: (_result(alpha.instrument_id, "24", "ACCELERATING"), _result(alpha.instrument_id, "6", "EMERGING_LEADER")),
        beta.instrument_id: (_result(beta.instrument_id, "19", "STRESSED"),),
    })
    service = MarketWideWatchService(repository=repository, universe=universe, memberships=memberships, diagnostics=diagnostics, governance=_Governance())

    first = service.run(as_of=T)
    second = service.run(as_of=T)

    assert first == second
    assert MarketWideWatchStore(repository).latest(as_of=T) == first
    assert service.latest(as_of=T) == first
    future = service.run(as_of=T + timedelta(days=1))
    assert service.latest(as_of=T) == first
    assert service.latest(as_of=T + timedelta(days=1)) == future
    by_symbol = {item.symbol: item for item in first.records}
    assert WatchClassification.EARNINGS_INFLECTION in by_symbol["ALPHA"].classifications
    assert WatchClassification.RELATIVE_STRENGTH_WATCH in by_symbol["ALPHA"].classifications
    assert by_symbol["ALPHA"].top3_eligible is False
    assert by_symbol["ALPHA"].setup_state == "NOT_EVALUATED"
    assert by_symbol["ALPHA"].six_gates_state == "NOT_EVALUATED"
    assert by_symbol["BETA"].status is WatchStatus.WATCH_RISK
    assert first.watch_candidate_count == 2
    assert first.decision_score_ready_count == first.valid_setup_count == first.six_gates_evaluated_count == 0
    assert "BALANCE_SHEET_IMPROVEMENT_POLICY_UNRESOLVED" in first.unsupported_classifications
    assert OpportunityArchetype.EARNINGS_INFLECTION in by_symbol["ALPHA"].archetypes
    assert by_symbol["ALPHA"].setup_policy_routes == (
        ("EARNINGS_INFLECTION", "SETUP_POLICY_UNAVAILABLE_FOR_ARCHETYPE"),
        ("RELATIVE_STRENGTH_WATCH", "SETUP_POLICY_UNAVAILABLE_FOR_ARCHETYPE"),
    )
    assert by_symbol["ALPHA"].comparison_readiness == "UNSCORED_NOT_WEAK"
    assert first.actual_rotation_candidate_count == 0
    response = MarketWideWatchResponse.model_validate(first, from_attributes=True)
    assert response.archetype_counts
    assert response.rotation_funnel[-1] == ("WATCH_CHALLENGERS", 2)


def test_market_wide_watch_route_reads_service_latest_and_preserves_governed_unavailable_response():
    class _Service:
        def __init__(self, value): self.value = value
        def latest(self): return self.value

    repository = SQLiteCoreApiSnapshotRepository()
    universe = CoreUniverseAnalysisStore(repository)
    alpha = _instrument("NSE:INE000000001", "ALPHA")
    universe.save_instrument(alpha)
    memberships = HistoricalSecurityMasterStore(repository)
    memberships.save_membership(
        UniverseMembership("membership:api", alpha.instrument_id, "NIFTY_500", T, None, T, "NSE", "exact", InstrumentLifecycle.ACTIVE),
        as_of=T,
    )
    value = MarketWideWatchService(repository=repository, universe=universe, memberships=memberships, diagnostics=_Diagnostics({}), governance=_Governance()).run(as_of=T)
    application = create_app()
    application.dependency_overrides[get_market_wide_watch_service] = lambda: _Service(value)
    with TestClient(application) as client:
        response = client.get("/api/v1/market-wide-watch")
    assert response.status_code == 200
    assert MarketWideWatchResponse.model_validate(response.json()).run_id == value.run_id

    unavailable = create_app()
    unavailable.dependency_overrides[get_market_wide_watch_service] = lambda: _Service(None)
    with TestClient(unavailable, raise_server_exceptions=False) as client:
        missing = client.get("/api/v1/market-wide-watch")
    assert missing.status_code == 503
    assert missing.json()["error"]["code"] == "MARKET_WIDE_WATCH_UNAVAILABLE"


def _policy_evidence(instrument_id: str, *, verified: bool = True, stage: PolicyStage = PolicyStage.NOTIFIED) -> EvidenceVersion:
    event = ExternalEvent("TEST_DESK", "policy-001", EventType.GOVERNMENT_POLICY, "Synthetic notified policy", "IN", "TEST", Materiality.HIGH, T, stage)
    source = SourceEvidence("PIB", "OFFICIAL", "PIB:001", .99)
    return EvidenceVersion(
        event, T, T, T, "Policy notification", "Implementation rules are published", source,
        facts=(Fact("Official policy fact", ("PIB:001",), .99),),
        interpretation=(Interpretation("Transmission remains an interpretation until reported results.", .8),),
        company_exposures=(CompanyExposure(instrument_id, None, ExposureType.DIRECT, .99, "VERIFIED" if verified else "UNVERIFIED_INFERENCE"),),
    )


def test_policy_led_turnaround_is_watch_only_and_does_not_use_pre_breakout_gate():
    instrument_id = "NSE:INE000000099"
    router = OpportunityArchetypeRouter()
    outcome = router.route(
        instrument_id=instrument_id,
        diagnostics=(
            _result(instrument_id, "16", "WEAK"), _result(instrument_id, "19", "HEALTHY"),
            _result(instrument_id, "24", "ACCELERATING"), _result(instrument_id, "6", "LEADING"),
        ),
        setup_state="NOT_EVALUATED", decision_score_status="UNSCORED", six_gates_state="NOT_EVALUATED",
        external_evidence=(_policy_evidence(instrument_id),),
    )
    assert OpportunityArchetype.POLICY_LED_INFLECTION in outcome.archetypes
    assert OpportunityArchetype.TURNAROUND_INFLECTION_WATCH in outcome.archetypes
    assert OpportunityArchetype.EARNINGS_INFLECTION in outcome.archetypes
    assert OpportunityArchetype.PRE_BREAKOUT not in outcome.archetypes
    assert outcome.policy_maturity == "NOTIFIED"
    assert outcome.historical_quality_state == "WEAK"
    assert "EXTERNAL_INTELLIGENCE:VERIFIED" in outcome.evidence_domain_coverage
    assert "HISTORICAL_FUNDAMENTALS_WEAK_PRESERVED" in outcome.blocker_codes
    assert all(route == SetupPolicyRoute.SETUP_POLICY_UNAVAILABLE_FOR_ARCHETYPE.value for _, route in outcome.setup_policy_routes)


def test_thematic_or_announcement_policy_evidence_cannot_create_policy_led_archetype():
    instrument_id = "NSE:INE000000099"
    router = OpportunityArchetypeRouter()
    inputs = (_result(instrument_id, "19", "HEALTHY"),)
    thematic = router.route(
        instrument_id=instrument_id, diagnostics=inputs, setup_state="NOT_EVALUATED",
        decision_score_status="UNSCORED", six_gates_state="NOT_EVALUATED",
        external_evidence=(_policy_evidence(instrument_id, verified=False),),
    )
    announcement = router.route(
        instrument_id=instrument_id, diagnostics=inputs, setup_state="NOT_EVALUATED",
        decision_score_status="UNSCORED", six_gates_state="NOT_EVALUATED",
        external_evidence=(_policy_evidence(instrument_id, stage=PolicyStage.STATEMENT),),
    )
    assert OpportunityArchetype.POLICY_LED_INFLECTION not in thematic.archetypes
    assert OpportunityArchetype.POLICY_LED_INFLECTION not in announcement.archetypes


def test_pre_breakout_is_only_routed_from_existing_approved_setup_and_archetypes_can_stack():
    instrument_id = "NSE:INE000000077"
    outcome = OpportunityArchetypeRouter().route(
        instrument_id=instrument_id,
        diagnostics=(
            _result(instrument_id, "24", "ACCELERATING"), _result(instrument_id, "26", "EXPANDING"),
            _result(instrument_id, "27", "GROWING"), _result(instrument_id, "6", "LEADING"),
        ),
        setup_state="CURRENT_VALID_SETUP", decision_score_status="COMPLETE", six_gates_state="EVALUATED",
    )
    assert OpportunityArchetype.PRE_BREAKOUT in outcome.archetypes
    assert OpportunityArchetype.EARNINGS_INFLECTION in outcome.archetypes
    assert OpportunityArchetype.MARGIN_INFLECTION in outcome.archetypes
    assert OpportunityArchetype.ORDER_BOOK_ACCELERATION in outcome.archetypes
    assert ("PRE_BREAKOUT", "PRE_BREAKOUT_POLICY") in outcome.setup_policy_routes
    assert "SIX_GATES_READY" in outcome.lifecycle_flags
