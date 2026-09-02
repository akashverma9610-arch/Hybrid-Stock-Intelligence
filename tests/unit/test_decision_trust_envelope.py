"""Decision Trust Envelope V1 remains a deterministic read-only composition."""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.main import create_app
from app.api.schemas.decision_trust import DecisionTrustEnvelopeResponse
from app.intelligence.decision_trust_envelope import (
    ENVELOPE_VERSION,
    decision_trust_envelope_from_shared_brain,
)
from app.intelligence.unified_state import BrainOutputContext, IntelligenceEvidenceAvailability
from app.market_data.dhan_live import DhanLiveFeedHealth
from test_shared_brain_application import T, _service


def _view():
    service, _, _ = _service()
    return service.analyze_stock("ALPHA", context=BrainOutputContext.DEEP_ANALYSIS, as_of=T)


def _score():
    return SimpleNamespace(
        score_status="COMPLETE",
        final_score=Decimal("5.7144"),
        id="canonical-score:alpha",
        scoring_policy_version="v1",
        scoring_policy_fingerprint="score-policy-fingerprint",
        as_of_timestamp=T,
        latest_completed_market_session=datetime(2026, 8, 30, tzinfo=UTC),
        warnings=("EXISTING_SCORE_WARNING",),
    )


def _setup():
    candidate = SimpleNamespace(
        strategy_family=SimpleNamespace(value="PRE_BREAKOUT"),
        breakout_confirmation_trigger=Decimal("101"),
        final_structural_stop=Decimal("95"),
        measured_move_target=Decimal("112"),
        reference_reward_risk=Decimal("1.83"),
        maximum_executable_entry_price=Decimal("102"),
        warnings=("EXISTING_SETUP_WARNING",),
    )
    return SimpleNamespace(opportunity_id="setup:alpha", decision_as_of=T, candidate=candidate)


def _gates():
    decisions = (
        SimpleNamespace(gate_id="GATE_1", outcome=SimpleNamespace(value="PASS")),
        SimpleNamespace(gate_id="GATE_2", outcome=SimpleNamespace(value="INSUFFICIENT_DATA")),
    )
    evaluation = SimpleNamespace(
        id="gates:alpha",
        as_of_timestamp=T,
        eligibility=SimpleNamespace(value="INSUFFICIENT_DATA"),
        decisions=decisions,
        failed_gate_ids=(),
        insufficient_gate_ids=("GATE_2",),
        warnings=("EXISTING_GATE_WARNING",),
    )
    return SimpleNamespace(evaluation=evaluation)


def test_envelope_reuses_existing_state_with_transparent_coverage_and_no_score_rescaling():
    view = _view()
    envelope = decision_trust_envelope_from_shared_brain(view, decision_scorecard=_score())

    expected_available = sum(state == IntelligenceEvidenceAvailability.AVAILABLE.value for _, state in view.evidence_domains[:-1])
    assert envelope.version == ENVELOPE_VERSION
    assert envelope.shared_brain_state == view.evidence_status
    assert (envelope.coverage_count, envelope.coverage_total) == (expected_available, len(view.evidence_references))
    assert envelope.coverage_pct == (Decimal(expected_available) * Decimal("100") / Decimal(len(view.evidence_references))).quantize(Decimal("0.01"))
    assert envelope.decision_score.value == Decimal("5.7144")
    assert envelope.decision_score.state == "COMPLETE"
    assert envelope.decision_score.policy_fingerprint == "score-policy-fingerprint"
    assert envelope.latest_completed_market_session == datetime(2026, 8, 30, tzinfo=UTC)
    assert set(envelope.missing_domains) == {item.domain for item in envelope.domains if item.availability != "AVAILABLE"}
    assert any(item.freshness for item in envelope.domains)
    assert envelope.decision_readiness == "DECISION_READINESS_UNRESOLVED"


def test_absent_artifacts_remain_explicit_and_live_context_cannot_mutate_score():
    view = _view()
    live = SimpleNamespace(
        ltp=Decimal("123.45"),
        received_at=datetime(2026, 9, 1, 10, 0, tzinfo=UTC),
        freshness=DhanLiveFeedHealth.LIVE,
    )
    absent = decision_trust_envelope_from_shared_brain(view)
    augmented = decision_trust_envelope_from_shared_brain(view, decision_scorecard=_score(), live_market_state=live)

    assert absent.setup.state == "NO_CURRENT_SETUP"
    assert absent.six_gates.state == "NOT_EVALUATED"
    assert absent.thesis.trading_thesis is None
    assert absent.decision_score.value is None and absent.decision_score.state == "UNSCORED"
    assert augmented.live_market.ltp == Decimal("123.45")
    assert augmented.live_market.received_at != augmented.intelligence_as_of
    assert augmented.decision_score.value == Decimal("5.7144")
    assert augmented.fingerprint == decision_trust_envelope_from_shared_brain(
        view, decision_scorecard=_score(), live_market_state=live,
    ).fingerprint


def test_valid_setup_and_evaluated_six_gates_are_exact_projections_not_actions():
    envelope = decision_trust_envelope_from_shared_brain(
        _view(),
        setup_opportunity=_setup(),
        six_gates_evaluation=_gates(),
        six_gates_policy=SimpleNamespace(policy_id="six-gates-production", version="v1", fingerprint="policy-fingerprint"),
    )

    assert envelope.setup.state == "CURRENT_SETUP_READY"
    assert envelope.setup.entry == Decimal("101")
    assert envelope.setup.structural_invalidation == Decimal("95")
    assert envelope.six_gates.state == "EVALUATED"
    assert envelope.six_gates.aggregate_state == "INSUFFICIENT_DATA"
    assert envelope.six_gates.gate_results == (("GATE_1", "PASS"), ("GATE_2", "INSUFFICIENT_DATA"))
    assert "BUY" not in str(envelope) and "SELL" not in str(envelope)


def test_api_serializes_ui_safe_read_model_without_provider_specific_live_fields():
    service, _, _ = _service()
    with TestClient(create_app(shared_brain_application_service=service)) as client:
        response = client.get(
            "/api/v1/stocks/ALPHA/decision-trust-envelope",
            params={"context": "DEEP_ANALYSIS", "as_of": T.isoformat()},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["version"] == ENVELOPE_VERSION
    assert payload["decision_score"]["state"] == "UNSCORED"
    assert payload["setup"]["state"] == "NO_CURRENT_SETUP"
    assert payload["six_gates"]["state"] == "NOT_EVALUATED"
    assert "provider" not in str(payload).lower()
    assert DecisionTrustEnvelopeResponse.model_validate(payload).coverage_total == len(payload["domains"])
