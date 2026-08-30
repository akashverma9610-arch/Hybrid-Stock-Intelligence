from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.rotation.engine import CapitalRotationEngine
from app.rotation.models import (
    RotationCandidate, RotationConfig, RotationDecisionState, RotationEvaluationContext,
    RotationHoldingState, RotationStance,
)


ASOF = datetime(2026, 8, 20, 10, tzinfo=UTC)
CONFIG = RotationConfig("rotation-v1", Decimal("0.8"), .7, Decimal("2.0"), True, True, False, "friction-v1", 1, 0)


def holding(score=Decimal("7.8"), *, adjustment=Decimal("0"), invalidation="INTACT", confidence=.8, instrument="holding"):
    return RotationHoldingState(instrument, ASOF, ASOF, score, confidence, "EXECUTABLE", "TECH", True, "VALID", "VALID", invalidation,
        Decimal("2.2"), Decimal("1.8"), Decimal(".20"), Decimal(".03"), 10, adjustment, Decimal("10000"), Decimal("500"), Decimal("90"))


def candidate(score=Decimal("8.9"), *, instrument="candidate", gate="EXECUTABLE", rr=Decimal("2.2"), confidence=.8, sector_ok=True, confirmation=1):
    return RotationCandidate(instrument, ASOF, ASOF, f"score-{instrument}", score, "COMPLETE", confidence, f"gate-{instrument}", gate,
        "HEALTH", sector_ok, "LOW", "VALID", "VALID", rr, True, True, True, "near-term", (), False, "clear", sector_ok, False, None, None, confirmation, (f"evidence-{instrument}",))


def context(holdings=(holding(),), candidates=(candidate(),), *, cash=Decimal("1000"), last=None):
    return RotationEvaluationContext("portfolio-snapshot-1", "strategy/0.1", "registry-v1", "score-v1", "gates-v1", ASOF,
        tuple(holdings), cash, tuple(candidates), "friction-v1", last)


def evaluate(ctx=None, config=CONFIG): return CapitalRotationEngine(config).evaluate(ctx or context(), ASOF)


def test_superior_eligible_candidate_creates_analytical_rotation_opportunity_only():
    result = evaluate()
    assert result.stance is RotationStance.ROTATION_OPPORTUNITY and result.decision is RotationDecisionState.ROTATE_CANDIDATE_PREFERRED
    assert result.preferred_candidate_id == "candidate" and "NO_ORDER_OR_CAPITAL_MOVEMENT_CREATED" in result.warnings


def test_candidate_below_hurdle_leaves_portfolio_unchanged_analytically():
    result = evaluate(context(candidates=(candidate(Decimal("8.5")),)))
    assert result.stance is RotationStance.NO_ROTATION and result.comparisons[0].result is RotationDecisionState.KEEP_EXISTING


def test_invalidated_holding_without_eligible_candidate_prefers_cash():
    blocked = candidate(gate="BLOCKED")
    result = evaluate(context(holdings=(holding(invalidation="TRIGGERED"),), candidates=(blocked,)))
    assert result.stance is RotationStance.DEFENSIVE_CASH and result.decision is RotationDecisionState.CASH_PREFERRED


def test_blocked_low_confidence_low_rr_and_sector_cap_candidates_cannot_win():
    candidates = (candidate(Decimal("9.3"), gate="BLOCKED", instrument="gate-blocked"), candidate(Decimal("9.0"), confidence=.5, instrument="low-confidence"), candidate(Decimal("9.2"), rr=Decimal("1.4"), instrument="bad-rr"), candidate(Decimal("8.8"), sector_ok=False, instrument="sector-cap"))
    result = evaluate(context(candidates=candidates))
    assert not result.ranked_candidates and set(result.blocked_candidate_ids) == {x.instrument_id for x in candidates}


def test_multiple_candidates_rank_deterministically_without_hidden_score():
    result = evaluate(context(candidates=(candidate(Decimal("9.2"), instrument="A"), candidate(Decimal("9.1"), instrument="B"))))
    assert [x.candidate.instrument_id for x in result.ranked_candidates] == ["A", "B"]
    assert result.ranked_candidates[0].ranking_inputs["score"] == "9.2"


def test_velocity_adjustment_changes_comparison_not_persisted_raw_score():
    state = holding(Decimal("8.2"), adjustment=Decimal("-0.5"))
    result = evaluate(context(holdings=(state,), candidates=(candidate(Decimal("8.6")),)))
    assert state.raw_decision_score == Decimal("8.2") and state.comparison_score == Decimal("7.7")
    assert result.comparisons[0].holding_comparison_score == Decimal("7.7")


def test_missing_holding_score_and_missing_required_friction_fail_closed():
    no_score = evaluate(context(holdings=(holding(score=None),)))
    strict = replace(CONFIG, require_friction_check=True)
    no_friction = evaluate(context(), strict)
    assert no_score.stance is RotationStance.INSUFFICIENT_DATA
    assert no_friction.stance is RotationStance.NO_ROTATION and no_friction.blocked_candidate_ids == ("candidate",)


def test_hysteresis_confirmation_and_cooldown_prevent_churn():
    config = replace(CONFIG, min_confirmations=2, cooldown_days=3)
    unconfirmed = evaluate(context(candidates=(candidate(confirmation=1),)), config)
    cooled = evaluate(context(candidates=(candidate(confirmation=2),), last=ASOF - timedelta(days=1)), config)
    confirmed = evaluate(context(candidates=(candidate(confirmation=2),)), config)
    assert unconfirmed.stance is RotationStance.NO_ROTATION and cooled.stance is RotationStance.NO_ROTATION
    assert confirmed.stance is RotationStance.ROTATION_OPPORTUNITY


def test_cash_only_context_keeps_cash_or_reports_deployment_opportunity_without_purchase():
    result = evaluate(context(holdings=(), candidates=(candidate(),), cash=Decimal("20000")))
    assert result.stance in {RotationStance.NO_ROTATION, RotationStance.ROTATION_OPPORTUNITY}
    assert result.decision is not RotationDecisionState.ROTATE_CANDIDATE_PREFERRED or result.preferred_candidate_id == "candidate"


def test_future_candidate_holding_score_gate_sector_thesis_and_friction_are_excluded():
    current = evaluate()
    future = ASOF + timedelta(days=1)
    future_candidate = replace(candidate(Decimal("10"), instrument="future-candidate"), as_of_timestamp=future, known_at=future, decision_scorecard_id="future-score", gate_evaluation_id="future-gate", sector="future-sector", trading_thesis_status="FUTURE", modeled_switching_friction=Decimal("0"))
    future_holding = replace(holding(), as_of_timestamp=future, known_at=future, raw_decision_score=Decimal("1"), invalidation_status="TRIGGERED")
    with pytest.raises(ValueError): evaluate(context(holdings=(future_holding,), candidates=(future_candidate,)))
    reconstructed = evaluate(context(candidates=(candidate(), future_candidate)))
    assert current == reconstructed and "future" not in str(reconstructed)
