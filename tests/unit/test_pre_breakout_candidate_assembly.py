from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.strategies.common.models import CandidateStatus, StrategyFamily
from app.strategies.pre_breakout.candidate_assembly import (
    PreBreakoutCandidateAssemblyError,
    PreBreakoutCandidateResearchStatus,
    PreBreakoutCandidateRole,
    assemble_prebreakout_candidate,
    prebreakout_setup_assessment_fingerprint,
)
from app.strategies.pre_breakout.materialization import (
    GovernedPreBreakoutBaseWindow,
    GovernedPreBreakoutPivot,
    GovernedPreBreakoutResolvedInputs,
    GovernedPreBreakoutStructuralResult,
    PreBreakoutResolvedInputStatus,
    PreBreakoutStructuralStatus,
)
from app.strategies.pre_breakout.setup_assessment import (
    GovernedPreBreakoutSetupAssessment,
    PreBreakoutSetupAssessmentStatus,
    PreBreakoutSetupBlocker,
    PreBreakoutSetupBlockerCategory,
)


T = datetime(2026, 8, 28, 12, tzinfo=UTC)
INSTRUMENT_ID = "NSE:CANDIDATE"


def _technical() -> GovernedPreBreakoutResolvedInputs:
    return GovernedPreBreakoutResolvedInputs(
        INSTRUMENT_ID, T, T, PreBreakoutResolvedInputStatus.PARTIAL_POLICY_BLOCKED,
        "pre-breakout-policy-v1", "v1.3-draft", "policy-fingerprint", "selection-id", "selection-fingerprint",
        252, Decimal("470"), Decimal("8"), True, Decimal("1"), (Decimal("2"),) * 5,
        Decimal("2"), True, T, Decimal("60"), True, Decimal("61"), True,
        Decimal("500"), 252, Decimal("6"), True, 499_999, Decimal("1000000"), "PASS",
        (1_000_000,) * 20, Decimal("1000000"), Decimal("0.50"), Decimal("500000"),
        "STRICT_LESS_THAN", True, T, (), (),
    )


def _structural() -> GovernedPreBreakoutStructuralResult:
    high = GovernedPreBreakoutPivot("h", T - timedelta(days=10), Decimal("500"), T - timedelta(days=7))
    low = GovernedPreBreakoutPivot("l", T - timedelta(days=9), Decimal("450"), T - timedelta(days=6))
    base = GovernedPreBreakoutBaseWindow(T - timedelta(days=20), T, 20, (high, high), (low, low), Decimal("500"), high.session)
    return GovernedPreBreakoutStructuralResult(
        INSTRUMENT_ID, T, T, PreBreakoutStructuralStatus.STRUCTURAL_ENTRY_READY,
        "pre-breakout-policy-v1", "v1.3-draft", "policy-fingerprint", "selection-id", "selection-fingerprint",
        252, 1, base, Decimal("500"), Decimal("500"), low, Decimal("450"), False,
        "AVAILABLE", Decimal("0.05"), "tick-id", True, Decimal("449.95"), Decimal("550"), True,
        None, None, None, None, (), Decimal("500"), "CONFIRMATION_NOT_INITIAL_ENTRY",
        Decimal("470"), T, "PASS", Decimal("474.9625"), Decimal("474.95"), Decimal("20.05"),
        Decimal("80"), Decimal("80") / Decimal("20.05"), True, None, "NOT_EVALUATED_AT_SCAN", "PASS", False,
    )


def _assessment(**changes) -> GovernedPreBreakoutSetupAssessment:
    value = GovernedPreBreakoutSetupAssessment(
        INSTRUMENT_ID, T, T, PreBreakoutSetupAssessmentStatus.ELIGIBLE_TO_FORM_CANDIDATE, True,
        "pre-breakout-policy-v1", "v1.3-draft", "policy-fingerprint", "selection-id", "selection-fingerprint",
        "Metals", "TOP3_ELIGIBLE", True, T, ("STORED_ONLY",), _technical(), _structural(),
        "NOT_EVALUATED_AT_SCAN", (), (),
    )
    return replace(value, **changes)


def _blocked(category: PreBreakoutSetupBlockerCategory, code: str) -> GovernedPreBreakoutSetupAssessment:
    statuses = {
        PreBreakoutSetupBlockerCategory.GOVERNANCE_BLOCKER: PreBreakoutSetupAssessmentStatus.BLOCKED_GOVERNANCE,
        PreBreakoutSetupBlockerCategory.DATA_BLOCKER: PreBreakoutSetupAssessmentStatus.BLOCKED_DATA,
        PreBreakoutSetupBlockerCategory.SECTOR_BLOCKER: PreBreakoutSetupAssessmentStatus.BLOCKED_SECTOR,
        PreBreakoutSetupBlockerCategory.TECHNICAL_SETUP_FAIL: PreBreakoutSetupAssessmentStatus.BLOCKED_TECHNICAL_SETUP,
        PreBreakoutSetupBlockerCategory.STRUCTURAL_SETUP_FAIL: PreBreakoutSetupAssessmentStatus.BLOCKED_STRUCTURAL_SETUP,
        PreBreakoutSetupBlockerCategory.ENTRY_ECONOMICS_FAIL: PreBreakoutSetupAssessmentStatus.BLOCKED_ENTRY_ECONOMICS,
    }
    return _assessment(status=statuses[category], candidate_formation_eligible=False,
                       blockers=(PreBreakoutSetupBlocker(category, code),))


def test_eligible_governed_assessment_assembles_exact_immutable_opportunity_candidate() -> None:
    assessment = _assessment()
    candidate = assemble_prebreakout_candidate(assessment)
    assert candidate.candidate_role is PreBreakoutCandidateRole.OPPORTUNITY_CANDIDATE
    assert candidate.strategy_family is StrategyFamily.PRE_BREAKOUT
    assert candidate.candidate_status is CandidateStatus.CANDIDATE_GENERATED
    assert candidate.research_status is PreBreakoutCandidateResearchStatus.RESEARCH_PENDING
    assert candidate.brain_evaluation_required and candidate.formation_blockers == ()
    assert candidate.assessment_fingerprint == prebreakout_setup_assessment_fingerprint(assessment)
    assert (candidate.instrument_id, candidate.evaluation_session, candidate.policy_fingerprint, candidate.sector) == (
        INSTRUMENT_ID, T, "policy-fingerprint", "Metals",
    )
    assert (candidate.bbw_percentile, candidate.current_atr14, candidate.official_delivery_pct, candidate.rsi14) == (
        Decimal("8"), Decimal("1"), Decimal("61"), Decimal("60"),
    )
    assert (candidate.base_top, candidate.breakout_confirmation_trigger, candidate.final_structural_stop,
            candidate.measured_move_target, candidate.maximum_executable_entry_price) == (
        Decimal("500"), Decimal("500"), Decimal("449.95"), Decimal("550"), Decimal("474.95"),
    )
    assert candidate.actual_execution_price is None and candidate.actual_execution_status == "NOT_EVALUATED_AT_SCAN"


@pytest.mark.parametrize(
    ("category", "code"),
    (
        (PreBreakoutSetupBlockerCategory.SECTOR_BLOCKER, "NOT_IN_TOP3_SECTOR"),
        (PreBreakoutSetupBlockerCategory.TECHNICAL_SETUP_FAIL, "RSI_OUTSIDE_RANGE"),
        (PreBreakoutSetupBlockerCategory.STRUCTURAL_SETUP_FAIL, "NO_VALID_WINDOW"),
        (PreBreakoutSetupBlockerCategory.ENTRY_ECONOMICS_FAIL, "ENTRY_RR_FAIL"),
        (PreBreakoutSetupBlockerCategory.DATA_BLOCKER, "TICK_SIZE_UNAVAILABLE_FOR_AS_OF"),
        (PreBreakoutSetupBlockerCategory.GOVERNANCE_BLOCKER, "POLICY_SEMANTIC_CONFLICT"),
    ),
)
def test_every_ineligible_blocker_category_fails_closed_without_candidate(category, code) -> None:
    with pytest.raises(PreBreakoutCandidateAssemblyError, match="PRE_BREAKOUT_CANDIDATE_NOT_ELIGIBLE"):
        assemble_prebreakout_candidate(_blocked(category, code))


def test_assessment_status_or_blockers_cannot_be_bypassed_by_setting_eligibility_true() -> None:
    invalid = _blocked(PreBreakoutSetupBlockerCategory.DATA_BLOCKER, "BBW_PERCENTILE_UNAVAILABLE")
    invalid = replace(invalid, candidate_formation_eligible=True)
    with pytest.raises(PreBreakoutCandidateAssemblyError, match="PRE_BREAKOUT_CANDIDATE_NOT_ELIGIBLE"):
        assemble_prebreakout_candidate(invalid)


def test_candidate_identity_is_deterministic_and_changes_for_assessment_or_policy_lineage() -> None:
    assessment = _assessment()
    first, second = assemble_prebreakout_candidate(assessment), assemble_prebreakout_candidate(assessment)
    changed_time = assemble_prebreakout_candidate(replace(assessment, evaluation_as_of=T + timedelta(seconds=1)))
    changed_policy = assemble_prebreakout_candidate(replace(assessment, policy_fingerprint="different-policy"))
    assert first.candidate_id == second.candidate_id and first.fingerprint == second.fingerprint
    assert changed_time.candidate_id != first.candidate_id
    assert changed_policy.candidate_id != first.candidate_id


def test_candidate_is_frozen_and_semantic_tampering_fails_fingerprint_validation() -> None:
    candidate = assemble_prebreakout_candidate(_assessment())
    with pytest.raises(FrozenInstanceError):
        candidate.sector = "Other"  # type: ignore[misc]
    with pytest.raises(PreBreakoutCandidateAssemblyError, match="FINGERPRINT_MISMATCH"):
        replace(candidate, measured_move_target=Decimal("560"))


def test_assembly_accepts_only_assessments_and_never_fabricates_execution() -> None:
    with pytest.raises(PreBreakoutCandidateAssemblyError, match="ASSESSMENT_REQUIRED"):
        assemble_prebreakout_candidate(object())  # type: ignore[arg-type]
    inconsistent = _assessment(structural=replace(_structural(), actual_execution_price=Decimal("471")))
    with pytest.raises(PreBreakoutCandidateAssemblyError, match="ASSESSMENT_INCONSISTENT"):
        assemble_prebreakout_candidate(inconsistent)


def test_candidate_contains_no_buy_score_ranking_research_or_trading_artifacts() -> None:
    candidate = assemble_prebreakout_candidate(_assessment())
    assert not any(hasattr(candidate, name) for name in (
        "buy", "sell", "recommendation", "score", "ranking", "decision_score", "research_result",
        "six_gates", "signal", "order", "paper_trade", "position", "portfolio_action",
    ))
