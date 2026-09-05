from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from app.historical.security_master import CorporateActionKind, HistoricalCorporateAction
from app.market_data.models import Timeframe
from app.market_data.technical_price_adjustment_integrity import ProviderPriceBasisState
from app.market_data.technical_source_basis_action_coverage import (
    ActionFreeWindowReason, ActionFreeWindowState, CorporateActionCoverageReason,
    CorporateActionCoverageState, SourceBasisReadiness, SourceBasisReason,
    TechnicalSourceBasisCoverageError, TechnicalWindowReadiness, TechnicalWindowReason,
    assess_action_free_window, assess_technical_window_source_integrity,
    create_corporate_action_coverage_assertion, create_source_basis_decision,
    dhan_live_forward_basis_readiness, official_dhan_daily_historical_basis,
    official_nse_bhavcopy_basis, official_upstox_historical_v3_basis,
    serialize_action_free_window, serialize_source_basis_decision,
)


T = datetime(2026, 9, 5, 16, 47, tzinfo=UTC)
I = "NSE:INE000A01001"


def _action(identifier: str = "action", kind: CorporateActionKind = CorporateActionKind.SPLIT, *, effective_days_ago: int = 2, known_days_ago: int = 3, instrument: str = I) -> HistoricalCorporateAction:
    effective = T - timedelta(days=effective_days_ago)
    return HistoricalCorporateAction(
        identifier, instrument, kind, None, None, effective, effective,
        Decimal("10"), Decimal("2"), '{"original_purpose":"test"}',
        "NSE_OFFICIAL_CORPORATE_ACTION_EXPORT", "nse-corporate-action-v1",
        T - timedelta(days=known_days_ago), "source:test",
    )


def _coverage(*, state: CorporateActionCoverageState = CorporateActionCoverageState.READY, known_at: datetime = T - timedelta(days=1), kinds: tuple[CorporateActionKind, ...] = tuple(CorporateActionKind)):
    evidence = official_upstox_historical_v3_basis(timeframe=Timeframe.DAILY).supporting_evidence[0]
    return create_corporate_action_coverage_assertion(
        coverage_id="nse-action-coverage", canonical_instrument_id=I,
        window_start=T - timedelta(days=10), window_end=T, source_known_at=known_at,
        source_evidence=evidence, covered_action_kinds=kinds, coverage_state=state,
        reasons=(CorporateActionCoverageReason.OFFICIAL_SOURCE_WINDOW_COMPLETE,)
        if state is CorporateActionCoverageState.READY
        else (CorporateActionCoverageReason.SOURCE_WINDOW_PARTIAL,),
    )


def test_official_upstox_basis_remains_unknown_and_hsi_no_adjustment_does_not_mean_raw():
    decision = official_upstox_historical_v3_basis(timeframe=Timeframe.DAILY)
    assert decision.provider_basis is ProviderPriceBasisState.UNKNOWN
    assert decision.historical_readiness is SourceBasisReadiness.NOT_READY
    assert SourceBasisReason.HSI_NO_TRANSFORMATION_DOES_NOT_PROVE_RAW in decision.reasons


def test_dhan_daily_history_is_provider_adjusted_not_promoted_to_a_canonical_method():
    decision = official_dhan_daily_historical_basis()
    assert decision.provider_basis is ProviderPriceBasisState.PROVIDER_ADJUSTED_UNKNOWN_METHOD
    assert decision.historical_readiness is SourceBasisReadiness.PARTIAL
    assert SourceBasisReason.PROVIDER_ADJUSTMENT_METHOD_UNVERIFIED in decision.reasons


def test_nse_bhavcopy_and_dhan_live_keep_basis_readiness_explicit():
    nse = official_nse_bhavcopy_basis()
    live = dhan_live_forward_basis_readiness()
    assert nse.provider_basis is ProviderPriceBasisState.UNKNOWN
    assert nse.historical_readiness is SourceBasisReadiness.NOT_READY
    assert live.historical_readiness is SourceBasisReadiness.NOT_APPLICABLE
    assert live.forward_readiness is SourceBasisReadiness.PARTIAL
    assert SourceBasisReason.PROSPECTIVE_IMMUTABLE_BAR_CAPTURE_NOT_IMPLEMENTED in live.reasons


def test_no_corporate_action_receipt_is_not_action_free_when_coverage_is_partial():
    result = assess_action_free_window(
        canonical_instrument_id=I, window_start=T - timedelta(days=5), window_end=T,
        as_of=T, coverage=_coverage(state=CorporateActionCoverageState.PARTIAL), actions=(),
    )
    assert result.state is ActionFreeWindowState.NOT_CERTIFIED
    assert ActionFreeWindowReason.COVERAGE_NOT_COMPLETE in result.reasons


def test_complete_known_coverage_and_no_action_certifies_only_no_known_discontinuity():
    result = assess_action_free_window(
        canonical_instrument_id=I, window_start=T - timedelta(days=5), window_end=T,
        as_of=T, coverage=_coverage(), actions=(),
    )
    assert result.state is ActionFreeWindowState.NO_KNOWN_PRICE_DISCONTINUITY_WITHIN_WINDOW
    assert result.action_ids == ()


def test_split_or_bonus_in_window_requires_the_separate_derivation_gate():
    result = assess_action_free_window(
        canonical_instrument_id=I, window_start=T - timedelta(days=5), window_end=T,
        as_of=T, coverage=_coverage(), actions=(_action(),),
    )
    assert result.state is ActionFreeWindowState.KNOWN_SPLIT_BONUS_REQUIRES_DERIVATION_GATE
    assert ActionFreeWindowReason.SPLIT_BONUS_ACTION_IN_WINDOW in result.reasons


@pytest.mark.parametrize(
    "kind",
    (
        CorporateActionKind.RIGHTS,
        CorporateActionKind.MERGER,
        CorporateActionKind.DEMERGER,
        CorporateActionKind.SYMBOL_CHANGE,
        CorporateActionKind.DELISTING,
        CorporateActionKind.SUSPENSION,
        CorporateActionKind.RELISTING,
    ),
)
def test_rights_and_complex_actions_fail_closed_across_the_window(kind: CorporateActionKind):
    result = assess_action_free_window(
        canonical_instrument_id=I, window_start=T - timedelta(days=5), window_end=T,
        as_of=T, coverage=_coverage(), actions=(_action(kind=kind),),
    )
    assert result.state is ActionFreeWindowState.NON_COMPARABLE_ACROSS_WINDOW
    assert ActionFreeWindowReason.RIGHTS_OR_COMPLEX_ACTION_IN_WINDOW in result.reasons


def test_cash_dividend_never_creates_total_return_or_action_free_price_continuity():
    result = assess_action_free_window(
        canonical_instrument_id=I, window_start=T - timedelta(days=5), window_end=T,
        as_of=T, coverage=_coverage(), actions=(_action(kind=CorporateActionKind.DIVIDEND),),
    )
    assert result.state is ActionFreeWindowState.NON_COMPARABLE_ACROSS_WINDOW
    assert ActionFreeWindowReason.CASH_DISTRIBUTION_POLICY_UNAVAILABLE in result.reasons


def test_ready_coverage_requires_authoritative_complete_provenance_and_all_continuity_families():
    original = _coverage()
    non_authoritative = type(original.source_evidence)(
        original.source_evidence.evidence_id,
        original.source_evidence.evidence_fingerprint,
        False,
    )
    with pytest.raises(TechnicalSourceBasisCoverageError, match="CORPORATE_ACTION_COVERAGE_ASSERTION_INVALID"):
        create_corporate_action_coverage_assertion(
            coverage_id=original.coverage_id,
            canonical_instrument_id=I,
            window_start=original.window_start,
            window_end=original.window_end,
            source_known_at=original.source_known_at,
            source_evidence=non_authoritative,
            covered_action_kinds=tuple(CorporateActionKind),
            coverage_state=CorporateActionCoverageState.READY,
            reasons=(CorporateActionCoverageReason.OFFICIAL_SOURCE_WINDOW_COMPLETE,),
        )
    with pytest.raises(TechnicalSourceBasisCoverageError, match="CORPORATE_ACTION_COVERAGE_ASSERTION_INVALID"):
        create_corporate_action_coverage_assertion(
            coverage_id=original.coverage_id,
            canonical_instrument_id=I,
            window_start=original.window_start,
            window_end=original.window_end,
            source_known_at=original.source_known_at,
            source_evidence=original.source_evidence,
            covered_action_kinds=tuple(kind for kind in CorporateActionKind if kind is not CorporateActionKind.SUSPENSION),
            coverage_state=CorporateActionCoverageState.READY,
            reasons=(CorporateActionCoverageReason.OFFICIAL_SOURCE_WINDOW_COMPLETE,),
        )


def test_future_effective_or_future_known_action_cannot_leak_backward():
    future_effective = _action(effective_days_ago=-1)
    future_known = _action("future-known", known_days_ago=-1)
    result = assess_action_free_window(
        canonical_instrument_id=I, window_start=T - timedelta(days=5), window_end=T,
        as_of=T, coverage=_coverage(), actions=(future_effective, future_known),
    )
    assert result.state is ActionFreeWindowState.NO_KNOWN_PRICE_DISCONTINUITY_WITHIN_WINDOW
    assert result.action_ids == ()
    assert ActionFreeWindowReason.ACTION_EFFECTIVE_AFTER_AS_OF in result.reasons
    assert ActionFreeWindowReason.ACTION_NOT_KNOWN_AS_OF in result.reasons


def test_exact_security_match_is_required_without_turning_other_security_into_an_action():
    result = assess_action_free_window(
        canonical_instrument_id=I, window_start=T - timedelta(days=5), window_end=T,
        as_of=T, coverage=_coverage(), actions=(_action(instrument="NSE:OTHER"),),
    )
    assert result.state is ActionFreeWindowState.NO_KNOWN_PRICE_DISCONTINUITY_WITHIN_WINDOW
    assert ActionFreeWindowReason.EXACT_INSTRUMENT_MISMATCH in result.reasons


def test_duplicate_actions_fail_closed_and_order_is_deterministic():
    action = _action()
    first = assess_action_free_window(
        canonical_instrument_id=I, window_start=T - timedelta(days=5), window_end=T,
        as_of=T, coverage=_coverage(), actions=(action, action),
    )
    second = assess_action_free_window(
        canonical_instrument_id=I, window_start=T - timedelta(days=5), window_end=T,
        as_of=T, coverage=_coverage(), actions=(action, action),
    )
    assert first.state is ActionFreeWindowState.NOT_CERTIFIED
    assert first.fingerprint == second.fingerprint
    assert ActionFreeWindowReason.DUPLICATE_ACTION_ID in first.reasons


def test_unknown_source_basis_stays_not_ready_even_when_action_coverage_is_complete():
    source = official_upstox_historical_v3_basis(timeframe=Timeframe.DAILY)
    window = assess_action_free_window(
        canonical_instrument_id=I, window_start=T - timedelta(days=5), window_end=T,
        as_of=T, coverage=_coverage(), actions=(),
    )
    integrity = assess_technical_window_source_integrity(source_basis=source, action_window=window)
    assert integrity.readiness is TechnicalWindowReadiness.NOT_READY
    assert TechnicalWindowReason.SOURCE_BASIS_UNKNOWN in integrity.reasons


def test_documented_raw_source_and_complete_action_free_window_can_be_ready_without_hsi_adjustment():
    evidence = official_upstox_historical_v3_basis(timeframe=Timeframe.DAILY).supporting_evidence
    source = create_source_basis_decision(
        source_family="official-test", source_version="v1", timeframe=Timeframe.DAILY,
        provider_basis=ProviderPriceBasisState.RAW, historical_readiness=SourceBasisReadiness.READY,
        forward_readiness=SourceBasisReadiness.READY, supporting_evidence=evidence, reasons=(),
    )
    window = assess_action_free_window(
        canonical_instrument_id=I, window_start=T - timedelta(days=5), window_end=T,
        as_of=T, coverage=_coverage(), actions=(),
    )
    assert assess_technical_window_source_integrity(source_basis=source, action_window=window).readiness is TechnicalWindowReadiness.READY


def test_coverage_and_window_fingerprints_are_tamper_evident_and_serialization_is_stable():
    coverage = _coverage()
    window = assess_action_free_window(
        canonical_instrument_id=I, window_start=T - timedelta(days=5), window_end=T,
        as_of=T, coverage=coverage, actions=(),
    )
    with pytest.raises(TechnicalSourceBasisCoverageError, match="CORPORATE_ACTION_COVERAGE_ASSERTION_INVALID"):
        replace(coverage, coverage_state=CorporateActionCoverageState.PARTIAL)
    with pytest.raises(TechnicalSourceBasisCoverageError, match="ACTION_FREE_WINDOW_ASSESSMENT_INVALID"):
        replace(window, coverage_id="other")
    source = official_upstox_historical_v3_basis(timeframe=Timeframe.DAILY)
    assert serialize_source_basis_decision(source) == serialize_source_basis_decision(source)
    assert serialize_action_free_window(window) == serialize_action_free_window(window)


def test_equivalent_timezone_window_inputs_have_the_same_identity_and_fingerprint():
    coverage = _coverage()
    utc = assess_action_free_window(
        canonical_instrument_id=I, window_start=T - timedelta(days=5), window_end=T,
        as_of=T, coverage=coverage, actions=(),
    )
    offset = assess_action_free_window(
        canonical_instrument_id=I,
        window_start=(T - timedelta(days=5)).astimezone(datetime.fromisoformat("2026-09-05T22:17:00+05:30").tzinfo),
        window_end=T.astimezone(datetime.fromisoformat("2026-09-05T22:17:00+05:30").tzinfo),
        as_of=T.astimezone(datetime.fromisoformat("2026-09-05T22:17:00+05:30").tzinfo),
        coverage=coverage, actions=(),
    )
    assert utc.assessment_id == offset.assessment_id
    assert utc.fingerprint == offset.fingerprint


def test_contract_has_no_storage_provider_api_portfolio_or_execution_dependency():
    import app.market_data.technical_source_basis_action_coverage as module

    source = Path(module.__file__).read_text(encoding="utf-8")
    forbidden = (
        "app.storage", "app.api", "app.portfolio", "app.broker", "app.orders", "app.signals",
        "app.data_operations", "app.runtime", "app.providers", "requests.", "sqlite", "datetime.now",
        "time.time", "MACD", "Stochastic", "CCI", "Williams",
    )
    assert not any(value in source for value in forbidden)
