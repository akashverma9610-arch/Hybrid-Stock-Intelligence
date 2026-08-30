from dataclasses import replace
from decimal import Decimal

from fastapi.testclient import TestClient

from app.api.capital_rotation_query import SnapshotCapitalRotationQueryService
from app.api.main import create_app
from app.rotation.models import RotationDecisionState, RotationStance
from tests.unit.test_capital_rotation import CONFIG, candidate, context, evaluate


def _client(evaluation, *, regime="MARKUP"):
    return TestClient(create_app(capital_rotation_query_service=SnapshotCapitalRotationQueryService(evaluation, market_regime=regime)))


def test_public_rotation_view_projects_existing_canonical_rotate_result_without_private_engine_details():
    result = evaluate()
    with _client(result) as client:
        response = client.get("/api/v1/capital-rotation")

    assert response.status_code == 200
    body = response.json()
    opportunity = body["opportunities"][0]
    assert body["overall_status"] == "READY"
    assert body["market_regime"] == "MARKUP"
    assert body["data_as_of"] == "2026-08-20T10:00:00Z"
    assert body["portfolio_reference"] is None
    assert opportunity["current_holding_symbol"] == "holding"
    assert opportunity["candidate_symbol"] == "candidate"
    assert opportunity["recommended_action"] == "ROTATE"
    assert opportunity["execution_eligibility"] == "ELIGIBLE"
    assert opportunity["catalyst_context"] == "near-term"
    private = {"hurdle", "gate_evaluation_id", "evidence_ids", "reasons_for", "reasons_against", "friction_status", "ranking_inputs", "rotation_configuration_version", "diagnostic"}
    assert not (private & set(opportunity))
    assert all(item not in response.text.lower() for item in ("gate-candidate", "score-candidate", "friction-v1", "diagnostic"))


def test_public_rotation_view_retains_hold_partial_empty_and_unavailable_semantics_without_engine_recalculation():
    hold = evaluate(context(candidates=(candidate(score=CONFIG.min_score_advantage + context().holdings[0].raw_decision_score - 1),)))
    partial = evaluate(context(holdings=(replace(context().holdings[0], raw_decision_score=None),)))
    empty = evaluate(context(holdings=(), candidates=()))
    cases = ((hold, "READY", "HOLD"), (partial, "PARTIAL", None), (empty, "EMPTY", None))
    for evaluation, status, action in cases:
        with _client(evaluation) as client:
            response = client.get("/api/v1/capital-rotation")
        assert response.status_code == 200
        assert response.json()["overall_status"] == status
        if action:
            assert response.json()["opportunities"][0]["recommended_action"] == action

    with _client(None) as client:
        unavailable = client.get("/api/v1/capital-rotation")
    assert unavailable.status_code == 200
    assert unavailable.json()["overall_status"] == "UNAVAILABLE"


def test_rotation_query_filters_are_bounded_and_route_is_read_only():
    result = evaluate(context(candidates=(candidate(instrument="A", score=Decimal("9")), candidate(instrument="B", score=Decimal("8.9")))))
    with _client(result) as client:
        filtered = client.get("/api/v1/capital-rotation", params={"candidate_symbol": "B", "limit": 1})
        invalid = client.get("/api/v1/capital-rotation", params={"limit": 101})
        openapi = client.get("/openapi.json").json()

    assert filtered.status_code == 200
    assert [item["candidate_symbol"] for item in filtered.json()["opportunities"]] == ["B"]
    assert invalid.status_code == 422
    assert set(openapi["paths"]["/api/v1/capital-rotation"]) == {"get"}


def test_blocked_candidate_is_retained_as_a_distilled_warning_without_exposing_its_internal_gate_or_rule():
    result = evaluate(context(candidates=(candidate(gate="BLOCKED"),)))
    with _client(result) as client:
        response = client.get("/api/v1/capital-rotation")

    assert response.status_code == 200
    assert response.json()["warnings"] == ["ROTATION_CANDIDATES_BLOCKED"]
    assert response.json()["opportunities"] == []
    assert "gate-candidate" not in response.text


def test_canonical_engine_output_is_unchanged_by_public_projection():
    result = evaluate()
    before = result
    response = SnapshotCapitalRotationQueryService(result).get_rotation()
    assert result == before
    assert response.opportunities[0].recommended_action == "ROTATE"
    assert result.decision is RotationDecisionState.ROTATE_CANDIDATE_PREFERRED
    assert result.stance is RotationStance.ROTATION_OPPORTUNITY
