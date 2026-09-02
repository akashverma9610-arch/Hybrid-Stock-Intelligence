from __future__ import annotations

import inspect
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

from app.diagnostics.models import EvaluatedDiagnostic, EvaluationEligibility
from app.domain.models import DiagnosticResult
from app.portfolio.holding_intelligence import compose_holding_intelligence
from app.portfolio.models import CashPosition, HoldingAnalytics, PortfolioDataStatus, PortfolioExposureSummary, PortfolioHolding, PortfolioRiskSummary, PortfolioSnapshot, PortfolioState
from app.portfolio.sell_side_policy import SellSideDecision
from app.portfolio.sell_side_runtime import PortfolioSellSideInput, evaluate_portfolio_sell_side_action
from app.registry.canonical import DIAGNOSTIC_REGISTRY_VERSION


T = datetime(2026, 8, 30, tzinfo=UTC)


def _holding(*, pnl: Decimal | None = Decimal("10")):
    return PortfolioHolding("holding-A", "NSE:A", Decimal("1"), Decimal("100"), Decimal("100"), T, Decimal("0"), "TECH", None, None, True, Decimal("110"), "mark-A", Decimal("110"), pnl, Decimal(".1") if pnl is not None else None, None, 1, 1, None)


def _snapshot(holding=None):
    value = holding or _holding()
    return PortfolioSnapshot("portfolio-A", "portfolio-A", T, T, (value,), CashPosition(Decimal("0"), "INR", Decimal("0"), T), (), Decimal("110"), Decimal("0"), Decimal("10"), Decimal("0"), PortfolioExposureSummary({}, Decimal("0"), {}, 1, Decimal("1")), PortfolioRiskSummary(None, Decimal("0"), PortfolioDataStatus.PARTIAL, {}), PortfolioState.FULLY_INVESTED, PortfolioDataStatus.PARTIAL, "v1", None)


def _brain(*, instrument="NSE:A", status="COMPLETE", as_of=T, conflicted=False, paper_marker="ignored"):
    domains = (("MARKET_DATA", "CONFLICTED" if conflicted else "AVAILABLE"),)
    return SimpleNamespace(
        canonical_instrument_id=instrument, as_of=as_of, evidence_status=status, evidence_domains=domains,
        snapshot_fingerprint="brain-fingerprint", context_projection_fingerprint="brain-context",
        unified_state_fingerprint="unified", brain_research_state_v2_fingerprint="research",
        financial_semantic_section_fingerprint="financial", forward_performance_intelligence=paper_marker,
    )


def _diagnostic(rule: int, result="HEALTHY", *, at=T):
    record = DiagnosticResult(f"diagnostic-{rule}-{result}-{at.isoformat()}", "NSE:A", str(rule), "strategy/v1", result, None, .8, (), (), at, at)
    return EvaluatedDiagnostic(record, rule, DIAGNOSTIC_REGISTRY_VERSION, EvaluationEligibility.ELIGIBLE, (), ())


def _complete_diagnostics():
    return tuple(_diagnostic(rule) for rule in (4, 6, 10, 16, 17, 18, 19, 23, 37, 38, 41, 43, 45, 46))


def _compose(*, holding=None, brain=None, diagnostics=()):
    value = holding or _holding(); snapshot = _snapshot(value)
    return compose_holding_intelligence(holding=value, portfolio_snapshot=snapshot, shared_brain=brain or _brain(), diagnostics=diagnostics), value, snapshot


def test_complete_governed_thesis_evidence_reuses_existing_synthesis_for_intact_state():
    composition, holding, snapshot = _compose(diagnostics=_complete_diagnostics())
    assert composition.analytics.trading_thesis == "STRONG"
    assert composition.analytics.investment_thesis == "STRONG"
    assert composition.analytics.invalidation_status is None
    assert composition.evidence_comparable and set(composition.populated_fields) >= {"trading_thesis", "investment_thesis"}


def test_incomplete_stale_or_conflicted_brain_evidence_fails_closed():
    partial, _, _ = _compose(brain=_brain(status="PARTIAL"), diagnostics=_complete_diagnostics())
    stale, _, _ = _compose(brain=_brain(as_of=T.replace(year=2025)), diagnostics=_complete_diagnostics())
    conflicted, _, _ = _compose(brain=_brain(conflicted=True), diagnostics=_complete_diagnostics())
    for value in (partial, stale, conflicted):
        assert value.analytics.trading_thesis is None and not value.evidence_comparable
    assert "SHARED_BRAIN_EVIDENCE_CONFLICTED" in conflicted.blockers


def test_future_diagnostics_are_excluded_and_cannot_create_a_thesis():
    future = _diagnostic(46, at=T.replace(year=2027))
    value, _, _ = _compose(diagnostics=(future,))
    assert value.analytics.trading_thesis is None
    assert "FUTURE_DIAGNOSTIC_EXCLUDED" in value.blockers


def test_current_intelligence_uses_later_evidence_without_rewriting_the_snapshot():
    intelligence_at = T.replace(day=31)
    diagnostics = tuple(_diagnostic(rule, at=intelligence_at) for rule in (4, 6, 10, 16, 17, 18, 19, 23, 37, 38, 41, 43, 45, 46))
    _, holding, snapshot = _compose()
    composition = compose_holding_intelligence(
        holding=holding, portfolio_snapshot=snapshot, shared_brain=_brain(as_of=intelligence_at),
        diagnostics=diagnostics, intelligence_as_of=intelligence_at,
    )
    decision = evaluate_portfolio_sell_side_action(PortfolioSellSideInput(
        snapshot, replace(holding, analytics=composition.analytics), None,
        composition.shared_brain_fingerprint, composition.evidence_conflicted, composition.evidence_comparable,
        intelligence_as_of=intelligence_at, latest_completed_market_session=T,
    ))
    assert composition.portfolio_snapshot_as_of == snapshot.as_of_timestamp
    assert composition.intelligence_as_of == intelligence_at
    assert composition.analytics.as_of_timestamp == intelligence_at
    assert decision.portfolio_snapshot_as_of == snapshot.as_of_timestamp
    assert decision.intelligence_as_of == intelligence_at
    assert decision.latest_completed_market_session == T
    assert snapshot.cash.as_of_timestamp == T and snapshot.cash.amount == Decimal("0")


def test_pnl_valuation_score_and_paper_intelligence_do_not_change_thesis():
    diagnostics = _complete_diagnostics()
    first, _, _ = _compose(diagnostics=diagnostics)
    unrelated_score = HoldingAnalytics("NSE:A", T, T, raw_decision_score=Decimal("0"), score_status="LOW")
    second_holding = replace(_holding(), current_price=Decimal("10000"), market_value=Decimal("10000"), unrealized_pnl=Decimal("9900"), unrealized_pnl_percent=Decimal("99"), analytics=unrelated_score)
    second, _, _ = _compose(holding=second_holding, brain=_brain(paper_marker="different-paper-outcome"), diagnostics=diagnostics)
    assert first.analytics.trading_thesis == second.analytics.trading_thesis == "STRONG"
    assert first.analytics.invalidation_status == second.analytics.invalidation_status is None


def test_triggered_existing_invalidation_is_preserved_and_sell_side_consumes_composed_analytics():
    diagnostics = tuple(_diagnostic(rule, "TRIGGERED" if rule == 46 else "HEALTHY") for rule in (4, 6, 10, 16, 17, 18, 19, 23, 37, 38, 41, 43, 45, 46))
    composition, holding, snapshot = _compose(diagnostics=diagnostics)
    composed_holding = replace(holding, analytics=composition.analytics)
    decision = evaluate_portfolio_sell_side_action(PortfolioSellSideInput(snapshot, composed_holding, None, composition.shared_brain_fingerprint, composition.evidence_conflicted, composition.evidence_comparable))
    assert composition.analytics.invalidation_status == "TRIGGERED"
    assert decision.thesis_state.value == "INVALIDATED"
    assert "TRIM" not in {item.value for item in SellSideDecision}


def test_five_holding_composition_integration_preserves_insufficient_evidence_per_holding():
    symbols = ("APARINDS", "DEEPINDS", "GENUSPOWER", "GLAND", "ICICIBANK")
    holdings = tuple(replace(_holding(), holding_id=f"holding-{symbol}", instrument_id=f"NSE:{symbol}") for symbol in symbols)
    snapshot = replace(_snapshot(holdings[0]), holdings=holdings)
    outputs = tuple(
        compose_holding_intelligence(
            holding=holding, portfolio_snapshot=snapshot,
            shared_brain=_brain(instrument=holding.instrument_id, status="PARTIAL"),
        )
        for holding in holdings
    )
    assert len(outputs) == 5
    assert all(value.analytics.trading_thesis is None for value in outputs)
    assert all("SHARED_BRAIN_EVIDENCE_INCOMPLETE" in value.blockers for value in outputs)


def test_fingerprint_and_shared_brain_lineage_are_deterministic_and_module_has_no_store_or_paper_import():
    first, _, _ = _compose(diagnostics=_complete_diagnostics())
    second, _, _ = _compose(diagnostics=_complete_diagnostics())
    assert first.fingerprint == second.fingerprint
    assert first.shared_brain_fingerprint == "brain-fingerprint"
    source = inspect.getsource(__import__("app.portfolio.holding_intelligence", fromlist=["*"]))
    assert "forward_paper" not in source and "sqlite" not in source and "save_" not in source
