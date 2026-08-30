from app.feature_settings import (
    FeatureLifecycleStatus,
    FeatureMaturity,
    FeatureName,
    FeatureSettings,
    RuntimeFeatureDisabledError,
)
from app.backtest.promotion import (
    ApprovedStrategyStatus,
    ApprovedStrategyVersion,
    PromotionProposalStatus,
    ReviewDecision,
    StrategyActivation,
    StrategyPromotionProposal,
    StrategyPromotionReview,
)
from app.historical.guard import manifest_fingerprint
from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository
from datetime import UTC, datetime, timedelta


def _governed_records():
    timestamp = datetime(2026, 12, 1, tzinfo=UTC)
    proposal = StrategyPromotionProposal(
        "feature-proposal", "feature-candidate", "feature-strategy", "1.0",
        "feature-experiment", "feature-selection", (), (), (), (), (), "", timestamp,
        PromotionProposalStatus.READY_FOR_REVIEW, (), manifest_fingerprint(feature="proposal"),
    )
    review = StrategyPromotionReview(
        "feature-review", proposal.proposal_id, "human:feature-owner", timestamp,
        ReviewDecision.APPROVE, "", (), "1", "", manifest_fingerprint(feature="review"),
    )
    approved = ApprovedStrategyVersion(
        "feature-approved", "feature-strategy", "1.0", None, proposal.proposal_id,
        review.review_id, "feature-candidate", (), timestamp, timestamp,
        ApprovedStrategyStatus.APPROVED, (), manifest_fingerprint(feature="approved"),
    )
    activation = StrategyActivation(
        "feature-activation", approved.approved_id, None, review.review_id,
        timestamp + timedelta(days=1), "human activation", manifest_fingerprint(feature="activation"),
    )
    return proposal, review, approved, activation


def test_default_feature_settings_fail_closed_and_expose_deferred_capability():
    settings = FeatureSettings()

    status = settings.automated_self_improvement_research

    assert status.name is FeatureName.AUTOMATED_SELF_IMPROVEMENT_RESEARCH
    assert status.enabled is False
    assert status.maturity is FeatureMaturity.EXPERIMENTAL
    assert status.lifecycle_status is FeatureLifecycleStatus.DEFERRED
    assert status.production_blocking is False
    assert settings.capability_statuses() == {"automated_self_improvement_research": status}
    assert status.as_dict() == {
        "name": "AUTOMATED_SELF_IMPROVEMENT_RESEARCH",
        "enabled": False,
        "maturity": "EXPERIMENTAL",
        "status": "DEFERRED",
        "production_blocking": False,
    }


def test_runtime_guard_rejects_default_disabled_feature_without_side_effects(tmp_path):
    repository = SQLiteStrategyGovernanceRepository(tmp_path / "feature-settings.db")
    proposal, review, approved, activation = _governed_records()
    repository.save_strategy_promotion_proposal(proposal)
    repository.save_strategy_promotion_review(review)
    repository.save_approved_strategy_version(approved)
    repository.save_strategy_activation(activation)
    protected_tables = (
        "automated_research_runs",
        "future_oos_candidate_queue_entries",
        "future_oos_assignments",
        "future_oos_execution_results",
        "promotion_evidence_packages",
        "strategy_promotion_proposals",
        "promotion_eligibility_results",
        "strategy_promotion_reviews",
        "approved_strategy_versions",
        "strategy_activations",
    )
    before = {
        table: repository._connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in protected_tables
    }

    try:
        FeatureSettings().require_automated_self_improvement_research_enabled()
    except RuntimeFeatureDisabledError as error:
        assert error.code == "AUTOMATED_RESEARCH_DISABLED"
    else:
        raise AssertionError("The default runtime capability must fail closed.")

    after = {
        table: repository._connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in protected_tables
    }
    assert after == before
    assert repository.get_approved_strategy_version(approved.approved_id) == approved
    assert repository.get_strategy_activation(activation.activation_id) == activation


def test_explicit_opt_in_and_environment_hook_only_permit_future_runtime_use():
    settings = FeatureSettings(automated_self_improvement_research_enabled=True)

    assert settings.require_automated_self_improvement_research_enabled().enabled is True
    assert FeatureSettings.from_environment({}).automated_self_improvement_research_enabled is False
    assert FeatureSettings.from_environment(
        {"ENABLE_AUTOMATED_SELF_IMPROVEMENT_RESEARCH": "true"}
    ).automated_self_improvement_research_enabled is True
