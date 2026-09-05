from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import json

import pytest

from app.historical.security_master import CorporateActionKind, HistoricalCorporateAction, PriceAdjustmentBasis
from app.market_data.models import (
    AdjustmentStatus, CanonicalOHLCVBar, Exchange, InstrumentIdentity,
    InstrumentType, MarketDataProvenance, Timeframe,
)
from app.market_data.technical_price_adjustment_integrity import (
    AdjustmentReadiness, PriceContinuityState, ProviderPriceBasisState,
    TechnicalAdjustmentReason, TechnicalPriceAdjustmentError, VolumeAdjustmentState,
    audit_provider_price_basis, derive_technical_price_adjustment,
    serialize_technical_price_adjustment,
)


T = datetime(2026, 9, 5, 16, 47, tzinfo=UTC)
I = InstrumentIdentity("NSE:INE000A01001", Exchange.NSE, "ALPHA", "ALPHA", "INE000A01001", "EQ", InstrumentType.NSE_EQUITY, "Alpha Ltd")
INDEX = InstrumentIdentity("NSE_INDEX:NIFTY_50", Exchange.INDEX, "NIFTY 50", "NIFTY 50", None, None, InstrumentType.BROAD_INDEX, "NIFTY 50")
SECTOR = InstrumentIdentity("NSE_INDEX:NIFTY_BANK", Exchange.INDEX, "NIFTY BANK", "NIFTY BANK", None, None, InstrumentType.SECTOR_INDEX, "NIFTY Bank")


def _bar(identifier: str, day: int, *, close: str = "100", volume: int | None = 100, adjustment: AdjustmentStatus = AdjustmentStatus.RAW, identity: InstrumentIdentity = I, provider: str = "nse_official", version: str = "nse-full-bhavcopy-v1") -> CanonicalOHLCVBar:
    end = T - timedelta(days=day)
    value = Decimal(close)
    return CanonicalOHLCVBar(identifier, identity, Timeframe.DAILY, end - timedelta(days=1), end, value, value + 1, value - 1, value, volume, None, None, adjustment, MarketDataProvenance(provider, None, end, end, end, version))


def _action(identifier: str, kind: CorporateActionKind, *, effective_days_ago: int = 2, known_days_ago: int = 3, details: str | None = None, numerator: str | None = None, denominator: str | None = None, instrument: str = I.instrument_id, source: str = "NSE_OFFICIAL_CORPORATE_ACTION_EXPORT", revision: str = "nse-corporate-action-v1") -> HistoricalCorporateAction:
    effective = T - timedelta(days=effective_days_ago)
    return HistoricalCorporateAction(identifier, instrument, kind, T - timedelta(days=known_days_ago), None, effective, effective, None if numerator is None else Decimal(numerator), None if denominator is None else Decimal(denominator), details, source, revision, T - timedelta(days=known_days_ago))


def _split(identifier: str = "split", **changes) -> HistoricalCorporateAction:
    details = json.dumps({"original_purpose": "Face Value Split (Sub-Division) - From Rs 10/- Per Share To Rs 2/- Per Share"}, sort_keys=True)
    return _action(identifier, CorporateActionKind.SPLIT, details=details, numerator="10", denominator="2", **changes)


def _bonus(identifier: str = "bonus", **changes) -> HistoricalCorporateAction:
    return _action(identifier, CorporateActionKind.BONUS, details=json.dumps({"original_purpose": "Bonus 1:1"}), numerator="1", denominator="1", **changes)


def test_split_adjustment_derives_new_values_without_mutating_raw_bars():
    before, after = _bar("before", 5), _bar("after", 1, close="20")
    result = derive_technical_price_adjustment(canonical_instrument_id=I.instrument_id, raw_bars=(before, after), actions=(_split(),), as_of=T)
    assert result.price_readiness is AdjustmentReadiness.READY
    assert result.continuity is PriceContinuityState.CONTINUOUS
    by_raw = {item.raw_bar_id: item for item in result.derived_bars}
    assert by_raw["before"].close == Decimal("20")
    assert by_raw["before"].volume == Decimal("500")
    assert by_raw["after"].close == Decimal("20")
    assert before.close == Decimal("100") and before.volume == 100
    assert result.derived_bars[0].raw_bar_id == before.bar_id


def test_bonus_adjustment_uses_explicit_additional_to_existing_ratio_and_volume_factor():
    result = derive_technical_price_adjustment(canonical_instrument_id=I.instrument_id, raw_bars=(_bar("before", 5), _bar("after", 1, close="50")), actions=(_bonus(),), as_of=T)
    derived = {item.raw_bar_id: item for item in result.derived_bars}["before"]
    assert (derived.price_factor, derived.volume_factor, derived.close, derived.volume) == (Decimal("0.5"), Decimal("2"), Decimal("50"), Decimal("200"))


def test_future_effective_action_is_excluded_even_when_announced_and_known():
    future = _split(effective_days_ago=-1, known_days_ago=3)
    result = derive_technical_price_adjustment(canonical_instrument_id=I.instrument_id, raw_bars=(_bar("one", 5),), actions=(future,), as_of=T)
    assert result.price_readiness is AdjustmentReadiness.READY
    assert result.action_receipts == ()
    assert TechnicalAdjustmentReason.ACTION_EFFECTIVE_AFTER_AS_OF in result.reasons
    assert {item.raw_bar_id: item for item in result.derived_bars}["one"].close == Decimal("100")


def test_action_known_after_as_of_is_excluded_even_when_effective_date_is_past():
    late = _split(effective_days_ago=2, known_days_ago=-1)
    result = derive_technical_price_adjustment(canonical_instrument_id=I.instrument_id, raw_bars=(_bar("one", 5),), actions=(late,), as_of=T)
    assert result.action_receipts == ()
    assert TechnicalAdjustmentReason.ACTION_NOT_KNOWN_AS_OF in result.reasons


def test_announcement_is_descriptive_and_never_substituted_for_effective_boundary():
    future = _split(effective_days_ago=-2, known_days_ago=3)
    assert future.announcement_date < T and future.effective_date > T
    result = derive_technical_price_adjustment(canonical_instrument_id=I.instrument_id, raw_bars=(_bar("one", 5),), actions=(future,), as_of=T)
    assert not result.action_receipts


def test_exact_security_match_is_required_and_other_security_action_is_not_used():
    wrong = _split(instrument="NSE:OTHER")
    result = derive_technical_price_adjustment(canonical_instrument_id=I.instrument_id, raw_bars=(_bar("one", 5),), actions=(wrong,), as_of=T)
    assert result.derived_bars[0].close == Decimal("100")
    assert TechnicalAdjustmentReason.EXACT_INSTRUMENT_MISMATCH in result.reasons


def test_split_without_explicit_old_new_face_value_semantics_fails_closed():
    ambiguous = _action("ambiguous", CorporateActionKind.SPLIT, details=json.dumps({"original_purpose": "Split 2:1"}), numerator="2", denominator="1")
    result = derive_technical_price_adjustment(canonical_instrument_id=I.instrument_id, raw_bars=(_bar("before", 5), _bar("after", 1)), actions=(ambiguous,), as_of=T)
    assert result.price_readiness is AdjustmentReadiness.NOT_READY
    assert result.continuity is PriceContinuityState.NON_COMPARABLE
    assert TechnicalAdjustmentReason.SPLIT_RATIO_SEMANTICS_UNVERIFIED in result.reasons


def test_bonus_without_exact_ratio_fails_closed():
    result = derive_technical_price_adjustment(canonical_instrument_id=I.instrument_id, raw_bars=(_bar("before", 5), _bar("after", 1)), actions=(_action("bad-bonus", CorporateActionKind.BONUS),), as_of=T)
    assert result.price_readiness is AdjustmentReadiness.NOT_READY
    assert TechnicalAdjustmentReason.BONUS_RATIO_SEMANTICS_UNVERIFIED in result.reasons


def test_bonus_source_text_and_parsed_ratio_must_agree_without_repairing_tampering():
    tampered = _bonus()
    tampered = replace(tampered, ratio_numerator=Decimal("2"))
    result = derive_technical_price_adjustment(canonical_instrument_id=I.instrument_id, raw_bars=(_bar("before", 5), _bar("after", 1)), actions=(tampered,), as_of=T)
    assert result.price_readiness is AdjustmentReadiness.NOT_READY
    assert TechnicalAdjustmentReason.BONUS_RATIO_SEMANTICS_UNVERIFIED in result.reasons


def test_rights_issue_never_invents_terp_or_subscription_price_adjustment():
    rights = _action("rights", CorporateActionKind.RIGHTS, numerator="3", denominator="8", details=json.dumps({"original_purpose": "Rights 3:8 @ Premium Rs 247"}))
    result = derive_technical_price_adjustment(canonical_instrument_id=I.instrument_id, raw_bars=(_bar("before", 5), _bar("after", 1)), actions=(rights,), as_of=T)
    assert result.price_readiness is AdjustmentReadiness.NOT_READY
    assert TechnicalAdjustmentReason.RIGHTS_ADJUSTMENT_NOT_READY in result.reasons


def test_cash_dividend_is_not_price_or_total_return_adjusted_by_this_contract():
    dividend = _action("dividend", CorporateActionKind.DIVIDEND)
    result = derive_technical_price_adjustment(canonical_instrument_id=I.instrument_id, raw_bars=(_bar("before", 5), _bar("after", 1)), actions=(dividend,), as_of=T)
    assert result.target_basis is PriceAdjustmentBasis.SPLIT_BONUS_ADJUSTED
    assert result.price_readiness is AdjustmentReadiness.NOT_READY
    assert TechnicalAdjustmentReason.DIVIDEND_PRICE_POLICY_NOT_APPROVED in result.reasons
    total_return = derive_technical_price_adjustment(canonical_instrument_id=I.instrument_id, raw_bars=(_bar("one", 5),), actions=(), as_of=T, target_basis=PriceAdjustmentBasis.TOTAL_RETURN_ADJUSTED)
    assert total_return.price_readiness is AdjustmentReadiness.NOT_READY
    assert TechnicalAdjustmentReason.TARGET_BASIS_POLICY_UNAVAILABLE in total_return.reasons


@pytest.mark.parametrize("kind", (CorporateActionKind.MERGER, CorporateActionKind.DEMERGER, CorporateActionKind.SYMBOL_CHANGE))
def test_complex_actions_are_non_comparable(kind: CorporateActionKind):
    result = derive_technical_price_adjustment(canonical_instrument_id=I.instrument_id, raw_bars=(_bar("before", 5), _bar("after", 1)), actions=(_action("complex", kind),), as_of=T)
    assert result.continuity is PriceContinuityState.NON_COMPARABLE
    assert result.price_readiness is AdjustmentReadiness.NOT_READY


def test_raw_target_preserves_values_but_marks_action_crossing_window_partial():
    result = derive_technical_price_adjustment(canonical_instrument_id=I.instrument_id, raw_bars=(_bar("before", 5), _bar("after", 1)), actions=(_split(),), as_of=T, target_basis=PriceAdjustmentBasis.RAW)
    assert result.price_readiness is AdjustmentReadiness.PARTIAL
    assert result.continuity is PriceContinuityState.NON_COMPARABLE
    assert result.derived_bars == ()


def test_no_action_window_is_raw_continuous_and_derived_factor_is_one():
    result = derive_technical_price_adjustment(canonical_instrument_id=I.instrument_id, raw_bars=(_bar("one", 1),), actions=(), as_of=T)
    assert result.price_readiness is AdjustmentReadiness.READY
    derived = result.derived_bars[0]
    assert derived.price_factor == Decimal("1")
    assert derived.action_ids == ()


def test_mixed_and_unknown_bases_remain_blocked_not_reclassified():
    mixed = derive_technical_price_adjustment(canonical_instrument_id=I.instrument_id, raw_bars=(_bar("raw", 2), _bar("unknown", 1, adjustment=AdjustmentStatus.UNKNOWN)), actions=(), as_of=T)
    assert mixed.price_readiness is AdjustmentReadiness.NOT_READY
    assert TechnicalAdjustmentReason.MIXED_OR_UNKNOWN_SOURCE_BASIS in mixed.reasons


def test_volume_readiness_is_separate_when_price_derivation_is_valid():
    result = derive_technical_price_adjustment(canonical_instrument_id=I.instrument_id, raw_bars=(_bar("before", 5, volume=None), _bar("after", 1)), actions=(_split(),), as_of=T)
    assert result.price_readiness is AdjustmentReadiness.READY
    assert result.volume_readiness is VolumeAdjustmentState.NOT_READY
    assert {item.raw_bar_id: item for item in result.derived_bars}["before"].volume is None
    assert TechnicalAdjustmentReason.VOLUME_NOT_PRESENT in result.reasons


def test_duplicate_and_conflicting_action_inputs_fail_closed_without_input_order_dependence():
    split = _split()
    one = derive_technical_price_adjustment(canonical_instrument_id=I.instrument_id, raw_bars=(_bar("before", 5), _bar("after", 1)), actions=(split, split), as_of=T)
    two = derive_technical_price_adjustment(canonical_instrument_id=I.instrument_id, raw_bars=(_bar("before", 5), _bar("after", 1)), actions=(split, split), as_of=T)
    assert one.price_readiness is AdjustmentReadiness.NOT_READY
    assert one.fingerprint == two.fingerprint
    assert TechnicalAdjustmentReason.DUPLICATE_ACTION_ID in one.reasons
    conflict = derive_technical_price_adjustment(canonical_instrument_id=I.instrument_id, raw_bars=(_bar("before", 5), _bar("after", 1)), actions=(_split("s1"), _split("s2")), as_of=T)
    assert TechnicalAdjustmentReason.AMBIGUOUS_ACTION_EFFECTIVE_BOUNDARY in conflict.reasons
    assert conflict.price_readiness is AdjustmentReadiness.NOT_READY


def test_corrections_create_distinct_as_of_versioned_derived_receipts_without_mutating_old_result():
    bars = (_bar("before", 5), _bar("after", 1))
    first = derive_technical_price_adjustment(canonical_instrument_id=I.instrument_id, raw_bars=bars, actions=(_split(),), as_of=T)
    later = derive_technical_price_adjustment(canonical_instrument_id=I.instrument_id, raw_bars=bars, actions=(_split("corrected", effective_days_ago=3),), as_of=T + timedelta(days=1))
    assert first.assessment_id != later.assessment_id
    first_before = {item.raw_bar_id: item for item in first.derived_bars}["before"]
    later_before = {item.raw_bar_id: item for item in later.derived_bars}["before"]
    assert first_before.fingerprint != later_before.fingerprint
    assert first_before.close == Decimal("20")


def test_serialization_and_fingerprint_are_deterministic_across_equivalent_timezone_input():
    action = _split()
    bars = (_bar("before", 5), _bar("after", 1))
    utc = derive_technical_price_adjustment(canonical_instrument_id=I.instrument_id, raw_bars=bars, actions=(action,), as_of=T)
    offset = derive_technical_price_adjustment(canonical_instrument_id=I.instrument_id, raw_bars=tuple(reversed(bars)), actions=(action,), as_of=T.astimezone(datetime.fromisoformat("2026-09-05T22:17:00+05:30").tzinfo))
    assert utc.fingerprint == offset.fingerprint
    assert serialize_technical_price_adjustment(utc) == serialize_technical_price_adjustment(offset)


def test_tampered_lineage_or_result_fingerprint_is_rejected():
    result = derive_technical_price_adjustment(canonical_instrument_id=I.instrument_id, raw_bars=(_bar("one", 1),), actions=(), as_of=T)
    with pytest.raises(TechnicalPriceAdjustmentError, match="TECHNICAL_PRICE_ADJUSTMENT_RESULT_INVALID"):
        replace(result, raw_bar_ids=("other",))
    with pytest.raises(TechnicalPriceAdjustmentError, match="DERIVED_TECHNICAL_BAR_INVALID"):
        replace(result.derived_bars[0], action_ids=("fake",))


def test_provider_basis_audit_preserves_upstox_nse_yfinance_and_index_boundaries():
    upstox = audit_provider_price_basis(_bar("upstox", 1, adjustment=AdjustmentStatus.UNKNOWN, provider="upstox", version="upstox-history-v3"))
    nse = audit_provider_price_basis(_bar("nse", 1, adjustment=AdjustmentStatus.UNKNOWN))
    yahoo = audit_provider_price_basis(_bar("yahoo", 1, provider="yfinance", version="yfinance-history-v1"))
    index = audit_provider_price_basis(_bar("index", 1, identity=INDEX, adjustment=AdjustmentStatus.UNKNOWN))
    assert upstox.provider_basis is ProviderPriceBasisState.UNKNOWN and not upstox.canonical_technical_allowed
    assert nse.provider_basis is ProviderPriceBasisState.UNKNOWN and not nse.canonical_technical_allowed
    assert yahoo.provider_basis is ProviderPriceBasisState.RAW and not yahoo.canonical_technical_allowed
    assert TechnicalAdjustmentReason.YFINANCE_SECONDARY_RESEARCH_ONLY in yahoo.reasons
    assert index.provider_basis is ProviderPriceBasisState.INDEX_SOURCE_SPECIFIC


def test_yfinance_raw_values_cannot_be_promoted_to_a_canonical_derived_series():
    raw = _bar("yahoo", 1, provider="yfinance", version="yfinance-history-v1")
    result = derive_technical_price_adjustment(canonical_instrument_id=I.instrument_id, raw_bars=(raw,), actions=(), as_of=T)
    assert result.price_readiness is AdjustmentReadiness.NOT_READY
    assert result.derived_bars == ()
    assert TechnicalAdjustmentReason.YFINANCE_SECONDARY_RESEARCH_ONLY in result.reasons


def test_index_and_sector_series_never_receive_equity_action_policy():
    result = derive_technical_price_adjustment(canonical_instrument_id=INDEX.instrument_id, raw_bars=(_bar("index", 1, identity=INDEX),), actions=(), as_of=T)
    assert result.price_readiness is AdjustmentReadiness.NOT_APPLICABLE
    assert TechnicalAdjustmentReason.INDEX_BASIS_SOURCE_SPECIFIC in result.reasons
    sector = derive_technical_price_adjustment(canonical_instrument_id=SECTOR.instrument_id, raw_bars=(_bar("sector", 1, identity=SECTOR),), actions=(), as_of=T)
    assert sector.price_readiness is AdjustmentReadiness.NOT_APPLICABLE


def test_target_price_adjusted_and_provider_adjusted_unknown_method_stay_policy_unavailable():
    for target in (PriceAdjustmentBasis.PRICE_ADJUSTED, PriceAdjustmentBasis.PROVIDER_ADJUSTED_UNKNOWN_METHOD):
        result = derive_technical_price_adjustment(canonical_instrument_id=I.instrument_id, raw_bars=(_bar("one", 1),), actions=(), as_of=T, target_basis=target)
        assert result.price_readiness is AdjustmentReadiness.NOT_READY
        assert TechnicalAdjustmentReason.TARGET_BASIS_POLICY_UNAVAILABLE in result.reasons


def test_contract_has_no_portfolio_execution_or_runtime_clock_dependency():
    import app.market_data.technical_price_adjustment_integrity as module

    source = open(module.__file__, encoding="utf-8").read()
    forbidden_imports = ("app.signals", "app.portfolio", "app.broker", "app.orders", "app.persistence", "app.api", "datetime.now", "time.time", "MACD", "Stochastic", "CCI", "Williams", "horizon", "technical_score")
    assert not any(token in source for token in forbidden_imports)
