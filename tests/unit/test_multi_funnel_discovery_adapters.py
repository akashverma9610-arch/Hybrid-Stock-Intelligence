from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

import app.intelligence.multi_funnel_discovery_adapters as module
from app.intelligence.multi_funnel_discovery import DiscoveryFunnelId
from app.intelligence.multi_funnel_discovery_adapters import (
    DiscoveryAdapterCoverageState,
    DiscoveryAdapterError,
    DiscoveryAdapterReason,
    DiscoveryAdapterState,
    adapt_compounder,
    adapt_fundamental_inflection,
    adapt_policy_transmission,
    adapt_pre_breakout,
    adapt_sector_rotation,
    unavailable_adapter,
)
from app.production_v1.canonical_setup_activation import CanonicalSetupOpportunity
import app.production_v1.canonical_setup_activation as setup_source
from app.strategies.pre_breakout.candidate_assembly import prebreakout_candidate_fingerprint
from app.production_v1.top3_opportunity_finder import Top3OpportunityFinderRun
from tests.unit import test_compounder_prospective_shadow_validation as compounder_source
from tests.unit import test_inflection_accounting_prospective_shadow as inflection_source
from tests.unit import test_long_term_policy_transmission_research_shadow as policy_source
from tests.unit.pre_breakout_setup_fixture import T, assessment


FP = "sha256:" + "a" * 64


def _pre_breakout() -> CanonicalSetupOpportunity:
    value = CanonicalSetupOpportunity.from_assessment(assessment())
    # The existing setup fixture deliberately uses an opaque compatibility
    # string.  The adapter's canonical lineage boundary correctly requires the
    # production contract's sha256 policy fingerprint.
    object.__setattr__(value.candidate, "policy_fingerprint", FP)
    object.__setattr__(value.candidate, "fingerprint", prebreakout_candidate_fingerprint(value.candidate))
    object.__setattr__(value, "policy_fingerprint", FP)
    object.__setattr__(value, "fingerprint", setup_source._fingerprint(value))
    return value


def _sector_run(*, ids=("NSE:INE000A01001",)) -> Top3OpportunityFinderRun:
    return Top3OpportunityFinderRun.create(
        as_of=T, ranking_id="sector-ranking:fixture", latest_completed_session=T,
        top3=("Industrials",), candidate_ids=ids, excluded=(), assessment_ids=(),
        opportunity_ids=(), data_blocked_count=0, condition_not_met_count=0,
        valid_count=0, near_misses=(),
    )


def _inflection():
    value = inflection_source._ready().observation
    assert value is not None
    return value


def _compounder():
    value = compounder_source._ready()[0].observation
    assert value is not None
    return value


def test_pre_breakout_adapter_preserves_governed_source_without_recalculation():
    source = _pre_breakout()
    result = adapt_pre_breakout(as_of=source.decision_as_of, opportunities=(source, source))
    assert result.coverage.state is DiscoveryAdapterCoverageState.LEADS_EMITTED
    assert result.coverage.source_observations_examined == 2
    assert len(result.leads) == 1
    lead = result.leads[0]
    assert lead.funnel_id is DiscoveryFunnelId.PRE_BREAKOUT
    assert lead.trigger_codes[0].value == "GOVERNED_PREBREAKOUT_SETUP_AVAILABLE"
    assert lead.intended_horizons[0].value == "POSITIONAL"
    assert {item.reference_id for item in lead.lineage} >= {source.opportunity_id, source.assessment_id, source.candidate.policy_id}


def test_pre_breakout_future_and_tampered_lineage_fail_closed():
    source = _pre_breakout()
    stale = adapt_pre_breakout(as_of=source.decision_as_of - timedelta(microseconds=1), opportunities=(source,))
    assert stale.coverage.state is DiscoveryAdapterCoverageState.STALE
    object.__setattr__(source, "fingerprint", FP)
    conflicted = adapt_pre_breakout(as_of=source.decision_as_of, opportunities=(source,))
    assert conflicted.coverage.state is DiscoveryAdapterCoverageState.EVIDENCE_CONFLICTED


def test_sector_adapter_uses_stored_exact_candidate_ids_only():
    run = _sector_run(ids=("NSE:INE000A01001", "NSE:INE000A01002"))
    result = adapt_sector_rotation(as_of=T, runs=(run,))
    assert result.coverage.state is DiscoveryAdapterCoverageState.LEADS_EMITTED
    assert {item.canonical_instrument_id for item in result.leads} == {"NSE:INE000A01001", "NSE:INE000A01002"}
    assert all(item.parent_discovery_id == run.run_id for item in result.leads)


def test_sector_adapter_rejects_bad_constituent_identity():
    run = _sector_run(ids=("NSE:INE000A01001",))
    object.__setattr__(run, "candidate_ids", ("bad identity",))
    result = adapt_sector_rotation(as_of=T, runs=(run,))
    assert result.coverage.state is DiscoveryAdapterCoverageState.IDENTITY_BLOCKED
    assert result.coverage.reason_codes == (DiscoveryAdapterReason.SOURCE_IDENTITY_INVALID,)


def test_inflection_adapter_preserves_research_shadow_without_qualification():
    source = _inflection()
    result = adapt_fundamental_inflection(as_of=source.as_of, observations=(source,))
    lead = result.leads[0]
    assert result.coverage.adapter_state is DiscoveryAdapterState.ADAPTER_PARTIAL
    assert lead.readiness.value == "RESEARCH_INSPECTION"
    assert not hasattr(lead, "actionability") and not hasattr(lead, "execution_status")
    assert lead.trigger_codes[0].value == "INFLECTION_ACCOUNTING_OBSERVATION_AVAILABLE"
    assert {source.revenue.receipt_id, source.pat.receipt_id} <= {item.reference_id for item in lead.lineage}


def test_inflection_adapter_no_observation_and_future_source_are_explicit():
    source = _inflection()
    result = adapt_fundamental_inflection(as_of=source.as_of, observations=())
    assert result.coverage.state is DiscoveryAdapterCoverageState.EVALUATED_NO_LEADS
    future = adapt_fundamental_inflection(as_of=source.as_of - timedelta(microseconds=1), observations=(source,))
    assert future.coverage.state is DiscoveryAdapterCoverageState.STALE


def test_compounder_adapter_requires_actual_prospective_observation():
    source = _compounder()
    result = adapt_compounder(as_of=source.as_of, observations=(source,))
    assert result.leads[0].readiness.value == "RESEARCH_INSPECTION"
    assert result.leads[0].trigger_codes[0].value == "COMPOUNDER_PROSPECTIVE_OBSERVATION_AVAILABLE"
    assert adapt_compounder(as_of=source.as_of, observations=()).coverage.state is DiscoveryAdapterCoverageState.EVALUATED_NO_LEADS


def test_policy_adapter_emits_only_exact_factual_exposure_path_not_benefit():
    source = policy_source.evaluate()
    result = adapt_policy_transmission(as_of=policy_source.T, observations=(source,))
    assert result.coverage.state is DiscoveryAdapterCoverageState.LEADS_EMITTED
    lead = result.leads[0]
    assert lead.readiness.value == "RESEARCH_INSPECTION"
    assert lead.trigger_codes[0].value == "POLICY_TRANSMISSION_RESEARCH_OBSERVATION"
    assert "BENEFICIARY" not in " ".join(lead.blocker_codes)
    assert "BULLISH" not in " ".join(lead.blocker_codes)


def test_policy_adapter_rejects_insufficient_or_future_evidence_without_lead():
    insufficient = policy_source.evaluate(effective_at=None)
    result = adapt_policy_transmission(as_of=policy_source.T, observations=(insufficient,))
    assert result.coverage.state is DiscoveryAdapterCoverageState.EVALUATED_NO_LEADS
    source = policy_source.evaluate()
    future = adapt_policy_transmission(as_of=policy_source.T - timedelta(microseconds=1), observations=(source,))
    assert future.coverage.state is DiscoveryAdapterCoverageState.STALE


@pytest.mark.parametrize("funnel", (
    DiscoveryFunnelId.MOMENTUM, DiscoveryFunnelId.EARNINGS_ACCELERATION,
    DiscoveryFunnelId.ORDERBOOK_CAPEX, DiscoveryFunnelId.NEWS_CATALYST,
    DiscoveryFunnelId.MARKET_DISLOCATION, DiscoveryFunnelId.HOLDING_STATE_CHANGE,
    DiscoveryFunnelId.EMERGING_COMPOUNDER, DiscoveryFunnelId.VALUATION_RECOVERY,
    DiscoveryFunnelId.WATCHLIST_STATE_CHANGE,
))
def test_unadapted_funnels_are_explicit_not_silent(funnel):
    result = unavailable_adapter(funnel_id=funnel, as_of=T)
    assert not result.leads
    assert result.coverage.state is not DiscoveryAdapterCoverageState.EVALUATED_NO_LEADS
    assert result.coverage.reason_codes


def test_unavailable_adapter_cannot_hide_a_source_adapted_funnel():
    with pytest.raises(DiscoveryAdapterError, match="HAS_SOURCE_ADAPTER"):
        unavailable_adapter(funnel_id=DiscoveryFunnelId.PRE_BREAKOUT, as_of=T)


def test_result_identity_serialization_is_deterministic_and_no_cross_funnel_union_exists():
    source = _pre_breakout()
    first = adapt_pre_breakout(as_of=source.decision_as_of, opportunities=(source,))
    second = adapt_pre_breakout(as_of=source.decision_as_of, opportunities=(source,))
    assert first.fingerprint == second.fingerprint and first.leads == second.leads
    assert not hasattr(first, "candidate") and not hasattr(first, "union")


def test_static_boundaries_exclude_clock_provider_portfolio_and_execution_dependencies():
    source = Path(module.__file__).read_text(encoding="utf-8")
    for forbidden in ("datetime.now", "time.time", "app.storage", "app.portfolio", "app.api", "app.broker", "app.orders", "app.signals", "requests", "httpx"):
        assert forbidden not in source
    assert "DecisionScore" not in source and "SixGates" not in source
