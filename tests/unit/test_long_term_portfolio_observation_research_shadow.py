from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import inspect

import pytest

from app.intelligence.fundamental_compounder_research_shadow import (
    FundamentalCompounderBusinessBranch,
    evaluate_fundamental_compounder_research_shadow,
)
from app.intelligence.fundamental_inflection_research_shadow import (
    FundamentalInflectionBusinessBranch,
    evaluate_fundamental_inflection_research_shadow,
)
from app.intelligence.long_term_portfolio_observation_research_shadow import *
from app.intelligence.long_term_thesis_invalidation_research_shadow import (
    LongTermThesisLifecycleState,
    review_long_term_thesis_invalidation,
)
from app.intelligence.long_term_thesis_research_shadow import (
    LongTermCoverageObservation,
    ResearchShadowCoverageState,
    required_coverage_domains,
    review_long_term_research_shadow,
)
from app.intelligence.long_term_thesis_review import (
    DossierEvidenceState,
    LongTermThesisFamily,
    LongTermThesisReviewContext,
    ThesisLineageReference,
    deep_analysis_dossier_candidate,
    review_long_term_thesis,
)
from app.portfolio.models import (
    CashPosition,
    CashState,
    PortfolioDataStatus,
    PortfolioExposureSummary,
    PortfolioHolding,
    PortfolioRiskSummary,
    PortfolioSnapshot,
    PortfolioState,
)


T = datetime(2026, 9, 3, 10, tzinfo=UTC)
FP = "sha256:" + "a" * 64
INSTRUMENT = "NSE:INE000000001"


def snapshot(*, as_of=T, holdings=None, cash_state=CashState.KNOWN):
    if holdings is None:
        holdings = (holding(),)
    cash = CashPosition(
        Decimal("100" if cash_state is CashState.KNOWN else "0") if cash_state is CashState.KNOWN else None,
        "INR", Decimal("0"), as_of, cash_state,
    )
    return PortfolioSnapshot(
        "snapshot:1", "portfolio:1", as_of, as_of, tuple(holdings), cash, (),
        None, Decimal("0"), None, Decimal("0"),
        PortfolioExposureSummary({}, None, {}, len(holdings), None),
        PortfolioRiskSummary(None, Decimal("0"), PortfolioDataStatus.PARTIAL, {}),
        PortfolioState.PARTIALLY_INVESTED if holdings else PortfolioState.ALL_CASH,
        PortfolioDataStatus.PARTIAL, "weighted-average-cost-v1", None,
    )


def holding(identifier="holding:1", instrument=INSTRUMENT):
    return PortfolioHolding(
        identifier, instrument, Decimal("1"), Decimal("10"), Decimal("10"),
        T - timedelta(days=4), Decimal("0"), "UNKNOWN", None, None, True,
        None, None, None, None, None, None, 4, 3, None,
    )


def source_receipt(family, at, coverage=ResearchShadowCoverageState.AVAILABLE):
    reference = ThesisLineageReference("diagnostic:1", FP, at - timedelta(minutes=3))
    candidate = deep_analysis_dossier_candidate(
        canonical_instrument_id=INSTRUMENT,
        dossier_id="dossier:1",
        dossier_fingerprint=FP,
        source_policy_version="brain-output-v1",
        dossier_as_of=at - timedelta(minutes=4),
        available_at=at - timedelta(minutes=3),
        evidence_state=DossierEvidenceState.AVAILABLE,
        diagnostic_lineage=(reference,),
        evidence_lineage=(ThesisLineageReference("evidence:1", FP, at - timedelta(minutes=3)),),
    )
    review = review_long_term_thesis(
        LongTermThesisReviewContext(at, "brain-output-v1", "long-term-thesis-review/sha256/v1"),
        family,
        candidate,
    )
    return review_long_term_research_shadow(review, tuple(
        LongTermCoverageObservation(domain, coverage, "coverage:" + domain.value.lower(), FP, at - timedelta(minutes=1))
        for domain in required_coverage_domains(family)
    ))


def lifecycle(
    *,
    at=T - timedelta(minutes=1),
    coverage=ResearchShadowCoverageState.AVAILABLE,
    compounder_branch=FundamentalCompounderBusinessBranch.NON_FINANCIAL_CORPORATE,
    inflection_branch=FundamentalInflectionBusinessBranch.NON_FINANCIAL_CORPORATE,
):
    compounder = evaluate_fundamental_compounder_research_shadow(
        source_receipt(LongTermThesisFamily.FUNDAMENTAL_COMPOUNDER, at, coverage), compounder_branch,
    )
    inflection = evaluate_fundamental_inflection_research_shadow(
        source_receipt(LongTermThesisFamily.FUNDAMENTAL_INFLECTION, at, coverage), inflection_branch,
    )
    return review_long_term_thesis_invalidation((compounder, inflection))


def test_exact_pit_compatible_receipt_is_associated_without_interpretation():
    receipt = lifecycle()
    result = observe_long_term_portfolio_research_shadow(snapshot(), (receipt,))
    observation = result.holdings[0]
    assert observation.lifecycle_id == receipt.lifecycle_id
    assert observation.lifecycle_fingerprint == receipt.fingerprint
    assert observation.lifecycle_state is LongTermThesisLifecycleState.POLICY_DEFINITION_MISSING
    assert observation.state is PortfolioObservationState.POLICY_DEFINITION_MISSING
    assert observation.reasons == (PortfolioObservationReason.LIFECYCLE_POLICY_DEFINITION_MISSING,)
    assert result.actionability == "WATCH_ONLY" and result.execution_status == "NON_EXECUTABLE"


def test_identical_input_is_deterministic_immutable_and_serializable():
    receipt = lifecycle()
    first = observe_long_term_portfolio_research_shadow(snapshot(), (receipt,))
    second = observe_long_term_portfolio_research_shadow(snapshot(), (receipt,))
    assert first.observation_id == second.observation_id
    assert first.fingerprint == second.fingerprint
    assert serialize_long_term_portfolio_observation(first) == serialize_long_term_portfolio_observation(second)
    with pytest.raises(FrozenInstanceError):
        first.holdings = ()


@pytest.mark.parametrize(("coverage", "expected"), (
    (ResearchShadowCoverageState.UNAVAILABLE, PortfolioObservationState.DATA_INSUFFICIENT),
    (ResearchShadowCoverageState.CONFLICTED, PortfolioObservationState.EVIDENCE_CONFLICTED),
))
def test_lifecycle_insufficiency_and_conflict_remain_descriptive(coverage, expected):
    result = observe_long_term_portfolio_research_shadow(snapshot(), (lifecycle(coverage=coverage),))
    assert result.holdings[0].state is expected


def test_no_receipt_and_future_receipt_are_not_negative_associations():
    absent = observe_long_term_portfolio_research_shadow(snapshot(), ())
    assert absent.holdings[0].state is PortfolioObservationState.LIFECYCLE_RECEIPT_UNAVAILABLE
    assert absent.holdings[0].reasons == (PortfolioObservationReason.LIFECYCLE_RECEIPT_UNAVAILABLE,)
    future = observe_long_term_portfolio_research_shadow(snapshot(), (lifecycle(at=T + timedelta(seconds=1)),))
    assert future.holdings[0].state is PortfolioObservationState.LIFECYCLE_RECEIPT_UNAVAILABLE
    assert future.holdings[0].reasons == (PortfolioObservationReason.FUTURE_LIFECYCLE_RECEIPT_EXCLUDED,)
    assert future.holdings[0].lifecycle_id is None


def test_multiple_pit_eligible_receipts_fail_closed_without_a_selector():
    first = lifecycle(at=T - timedelta(minutes=2))
    second = lifecycle(at=T - timedelta(minutes=1))
    result = observe_long_term_portfolio_research_shadow(snapshot(), (second, first))
    observation = result.holdings[0]
    assert observation.state is PortfolioObservationState.LIFECYCLE_RECEIPT_AMBIGUOUS
    assert observation.reasons == (PortfolioObservationReason.LIFECYCLE_SELECTION_UNGOVERNED,)
    assert observation.lifecycle_id is None


def test_invalid_identity_and_non_comparable_or_unknown_branches_do_not_get_inferred():
    invalid = observe_long_term_portfolio_research_shadow(
        snapshot(holdings=(holding(instrument="not canonical"),)), (),
    )
    assert invalid.holdings[0].state is PortfolioObservationState.IDENTITY_UNAVAILABLE
    non_comparable = observe_long_term_portfolio_research_shadow(snapshot(), (lifecycle(
        compounder_branch=FundamentalCompounderBusinessBranch.STRUCTURALLY_NON_COMPARABLE,
        inflection_branch=FundamentalInflectionBusinessBranch.STRUCTURALLY_NON_COMPARABLE,
    ),))
    assert non_comparable.holdings[0].state is PortfolioObservationState.NON_COMPARABLE
    unknown = observe_long_term_portfolio_research_shadow(snapshot(), (lifecycle(
        compounder_branch=FundamentalCompounderBusinessBranch.UNKNOWN,
        inflection_branch=FundamentalInflectionBusinessBranch.UNKNOWN,
    ),))
    assert unknown.holdings[0].state is PortfolioObservationState.NOT_APPLICABLE


def test_cash_is_a_valid_non_thesis_allocation_and_mixed_portfolio_is_not_ranked():
    result = observe_long_term_portfolio_research_shadow(snapshot(cash_state=CashState.UNKNOWN), (lifecycle(),))
    assert result.cash.cash_state is CashState.UNKNOWN
    assert result.cash.state is PortfolioObservationState.NOT_APPLICABLE
    assert result.cash.reasons == (PortfolioObservationReason.CASH_IS_VALID_ALLOCATION,)
    assert not hasattr(result, "weakest_holding") and not hasattr(result, "ranking")
    assert not hasattr(result, "recommendation") and not hasattr(result, "decision_score")


def test_tampered_or_duplicate_lifecycle_input_is_rejected_not_attached():
    receipt = lifecycle()
    object.__setattr__(receipt, "fingerprint", FP)
    with pytest.raises(LongTermPortfolioObservationError, match="LIFECYCLE_UNVERIFIABLE"):
        observe_long_term_portfolio_research_shadow(snapshot(), (receipt,))
    duplicate = lifecycle()
    with pytest.raises(LongTermPortfolioObservationError, match="LIFECYCLE_DUPLICATE"):
        observe_long_term_portfolio_research_shadow(snapshot(), (duplicate, duplicate))


def test_contradictory_or_future_association_construction_is_rejected():
    receipt = lifecycle()
    with pytest.raises(LongTermPortfolioObservationError, match="STATE_REASON_CONTRADICTION"):
        PortfolioHoldingObservation(
            "holding:1", INSTRUMENT, PortfolioObservationState.DATA_INSUFFICIENT,
            (PortfolioObservationReason.LIFECYCLE_POLICY_DEFINITION_MISSING,),
            receipt.lifecycle_id, receipt.fingerprint, T, receipt.state,
        )
    result = observe_long_term_portfolio_research_shadow(snapshot(), (receipt,))
    object.__setattr__(result.holdings[0], "lifecycle_as_of", T + timedelta(seconds=1))
    with pytest.raises(LongTermPortfolioObservationError, match="FUTURE_LIFECYCLE_ASSOCIATION"):
        result.verify()


def test_stable_reason_order_and_no_forbidden_dependencies_or_action_surface():
    source = inspect.getsource(__import__(
        "app.intelligence.long_term_portfolio_observation_research_shadow", fromlist=("x",),
    ))
    assert not {"BUY", "SELL", "HOLD", "ADD", "TRIM", "EXIT", "ROTATE"} & {
        value.value for value in PortfolioObservationState
    }
    for forbidden in ("app.signals", "app.storage", "app.api", "app.broker", "app.orders", "app.gates"):
        assert forbidden not in source
    result = observe_long_term_portfolio_research_shadow(snapshot(), ())
    assert result.holdings == tuple(sorted(result.holdings, key=lambda item: item.holding_id))
    assert tuple(sorted(result.holdings[0].reasons, key=lambda item: item.value)) == result.holdings[0].reasons
