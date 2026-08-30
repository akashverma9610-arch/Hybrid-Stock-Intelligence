from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.backtest.promotion import (
    ApprovedStrategyStatus, ApprovedStrategyVersion, PromotionEligibilityResult,
    PromotionEligibilityStatus, PromotionProposalStatus, ReviewDecision,
    StrategyActivation, StrategyPromotionPolicy, StrategyPromotionProposal,
    StrategyPromotionReview,
)
from app.historical.guard import manifest_fingerprint
from app.self_improvement.models import (
    AttributionStrength, ErrorCategory, HypothesisProposalBudget,
    HypothesisRankingPolicy, ImprovementHypothesis, ObservationSource,
    SelfImprovementEvidencePolicy, SelfImprovementObservation, SelfImprovementRun,
    StrategyErrorAttribution, StrategySuccessAttribution, SuccessCategory,
)
from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository


T = datetime(2026, 8, 1, 9, tzinfo=UTC)


def records():
    run = SelfImprovementRun(
        "improvement-run-v1", "strategy-2.1", T, T + timedelta(days=30),
        ("backtest-1",), ("walk-forward-1",), ("aggregate-1",),
        ("paper-1",), ("benchmark-1",), "self-improvement-v1", T,
        "COMPLETED", ("RESEARCH_ONLY",), manifest_fingerprint(run="v1"),
    )
    observation = SelfImprovementObservation(
        "observation-1", run.run_id, ObservationSource.WALK_FORWARD_OOS,
        "aggregate-1", T + timedelta(days=1), run.strategy_version,
        {"regime": "BULL", "sample_size": 12, "return": "0.12"},
        ("aggregate-1", "walk-forward-1"), ("SOURCE_TYPED",),
        manifest_fingerprint(observation="v1"),
    )
    policy = SelfImprovementEvidencePolicy(
        "evidence-policy-1", "1", 10, 5, "evidence-policy-v1",
        manifest_fingerprint(policy="evidence-v1"),
    )
    error = StrategyErrorAttribution(
        "error-attribution-1", run.run_id, observation.observation_id,
        run.strategy_version, ErrorCategory.FALSE_BREAKOUT,
        AttributionStrength.ASSOCIATED_WITH, "MEDIUM", ("aggregate-1",),
        ("diagnostic-11",), "Counterfactual outcome is not asserted.",
        ("ASSOCIATION_NOT_CAUSATION",), manifest_fingerprint(error="v1"),
    )
    success = StrategySuccessAttribution(
        "success-attribution-1", run.run_id, observation.observation_id,
        run.strategy_version, SuccessCategory.REGIME_MATCH_SUCCESS,
        AttributionStrength.LIKELY_CONTRIBUTOR, "LOW", ("aggregate-1",),
        ("EVIDENCE_LIMITED",), manifest_fingerprint(success="v1"),
    )
    hypothesis = ImprovementHypothesis(
        "hypothesis-1", run.run_id, "Validate regime threshold",
        "Test whether the existing regime threshold warrants a controlled experiment.",
        (error.attribution_id, success.attribution_id), "EXPERIMENT_PROPOSAL_ONLY",
        "LOW", ("NO_STRATEGY_MUTATION",), manifest_fingerprint(hypothesis="v1"),
    )
    ranking = HypothesisRankingPolicy(
        "ranking-policy-1", "1", 3, "hypothesis-ranking-v1",
        manifest_fingerprint(ranking="v1"),
    )
    budget = HypothesisProposalBudget(
        "proposal-budget-1", "1", 2, "proposal-budget-v1",
        manifest_fingerprint(budget="v1"),
    )
    return run, observation, policy, error, success, hypothesis, ranking, budget


def governed_strategy_records():
    policy = StrategyPromotionPolicy(
        "promotion-policy", "1", 2, Decimal(".6"), 10, Decimal(".2"),
        Decimal("0"), Decimal(".1"), None, ("VALID",), True, 2,
        Decimal(".01"), True, "promotion-v1", manifest_fingerprint(policy="promotion"),
    )
    proposal = StrategyPromotionProposal(
        "promotion-proposal", "candidate", "strategy", "2.2", "experiment",
        "selection", ("walk-forward",), ("aggregate",), ("benchmark",),
        ("robustness",), ("candidate-fingerprint",), "hypothesis", T,
        PromotionProposalStatus.READY_FOR_REVIEW, (), manifest_fingerprint(proposal="promotion"),
    )
    eligibility = PromotionEligibilityResult(
        "promotion-eligibility", proposal.proposal_id, policy.policy_id, policy.version,
        PromotionEligibilityStatus.ELIGIBLE_FOR_REVIEW, ("OOS_OK",), (), T,
        manifest_fingerprint(eligibility="promotion"),
    )
    review = StrategyPromotionReview(
        "promotion-review", proposal.proposal_id, "human:reviewer", T,
        ReviewDecision.APPROVE, "approved", (), policy.version, "evidence-fingerprint",
        manifest_fingerprint(review="promotion"),
    )
    version = ApprovedStrategyVersion(
        "approved-version", "strategy", "2.2", None, proposal.proposal_id,
        review.review_id, "candidate", ("candidate-fingerprint",), T,
        T + timedelta(days=1), ApprovedStrategyStatus.APPROVED, (),
        manifest_fingerprint(version="promotion"),
    )
    activation = StrategyActivation(
        "strategy-activation", version.approved_id, None, review.review_id,
        T + timedelta(days=1), "human activation", manifest_fingerprint(activation="promotion"),
    )
    return policy, proposal, eligibility, review, version, activation


def test_self_improvement_artifacts_round_trip_and_are_insert_only(tmp_path):
    repository = SQLiteStrategyGovernanceRepository(tmp_path / "self-improvement.db")
    values = records()
    run, observation, policy, error, success, hypothesis, ranking, budget = values
    promotion_policy, proposal, eligibility, review, approved, activation = governed_strategy_records()
    repository.save_strategy_promotion_policy(promotion_policy)
    repository.save_strategy_promotion_proposal(proposal)
    repository.save_promotion_eligibility_result(eligibility)
    repository.save_strategy_promotion_review(review)
    repository.save_approved_strategy_version(approved)
    repository.save_strategy_activation(activation)
    actions = (
        (repository.save_self_improvement_run, repository.get_self_improvement_run, run.run_id, run),
        (repository.save_self_improvement_observation, repository.get_self_improvement_observation, observation.observation_id, observation),
        (repository.save_self_improvement_evidence_policy, repository.get_self_improvement_evidence_policy, policy.policy_id, policy),
        (repository.save_strategy_error_attribution, repository.get_strategy_error_attribution, error.attribution_id, error),
        (repository.save_strategy_success_attribution, repository.get_strategy_success_attribution, success.attribution_id, success),
        (repository.save_improvement_hypothesis, repository.get_improvement_hypothesis, hypothesis.hypothesis_id, hypothesis),
        (repository.save_hypothesis_ranking_policy, repository.get_hypothesis_ranking_policy, ranking.policy_id, ranking),
        (repository.save_hypothesis_proposal_budget, repository.get_hypothesis_proposal_budget, budget.budget_id, budget),
    )
    approved_before = repository.get_approved_strategy_version(approved.approved_id)
    active_before = repository.get_strategy_activation(activation.activation_id)
    for save, get, identifier, value in actions:
        save(value)
        assert get(identifier) == value
    assert repository.get_self_improvement_observation(observation.observation_id).source is ObservationSource.WALK_FORWARD_OOS
    assert repository.get_self_improvement_observation(observation.observation_id).provenance_ids == observation.provenance_ids
    assert repository.get_self_improvement_run(run.run_id).fingerprint == run.fingerprint
    for save, _get, _identifier, value in actions:
        with pytest.raises(ValueError, match="immutable"):
            save(value)
    later = SelfImprovementObservation(
        "observation-2", run.run_id, ObservationSource.HISTORICAL_BACKTEST,
        "backtest-2", T + timedelta(days=31), run.strategy_version,
        {"return": "-0.05"}, ("backtest-2",), ("LATER_EVIDENCE",),
        manifest_fingerprint(observation="v2"),
    )
    repository.save_self_improvement_observation(later)
    assert tuple(get(identifier) for _save, get, identifier, _value in actions) == values
    assert repository.get_self_improvement_observation(later.observation_id) == later
    assert repository.get_approved_strategy_version(approved.approved_id) == approved_before
    assert repository.get_strategy_activation(activation.activation_id) == active_before
