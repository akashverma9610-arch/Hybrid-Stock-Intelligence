from __future__ import annotations

import ast
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from app.domain.models import DataQuality
from app.historical.nse_capital_market_session_evidence_2022_2026 import nse_capital_market_calendar_2022_2026
from app.historical.nse_udiff_identity_promotion import (
    NSE_UDIFF_SOURCE_FAMILY,
    NSE_UDIFF_SOURCE_VERSION,
    POLICY_VERSION as IDENTITY_POLICY_VERSION,
    NseUdiffHistoricalSourceIdentityInterval,
    _fp as identity_fingerprint,
)
from app.historical.nse_udiff_effective_identity_coverage import (
    NseUdiffEffectiveIdentityCoverageIndex, NseUdiffIdentityAnchor,
    NseUdiffIdentitySourceObservation, build_effective_identity_coverage_plan,
)
from app.historical.security_master import CorporateActionKind, HistoricalCorporateAction
from app.market_data.models import (
    AdjustmentStatus,
    CanonicalOHLCVBar,
    Exchange,
    InstrumentIdentity,
    InstrumentType,
    MarketDataProvenance,
    Timeframe,
)
from app.market_data.nse_udiff_daily_integrity import (
    NseUdiffConflictAssessment,
    NseUdiffConflictCause,
    NseUdiffConflictState,
    _conflict_payload,
    _fingerprint as conflict_fingerprint,
    build_udiff_session_coverage_manifest,
)
from app.market_data.nse_udiff_daily_history import NseUdiffDailyStatus, _receipt as acquisition_receipt
from app.market_data.nse_udiff_source_identity import source_fields
from app.market_data.nse_udiff_daily_technical_eligibility import (
    CurrentDescriptiveDailyTechnicalState,
    DailyTechnicalEligibilityError,
    DailyTechnicalEligibilityReason,
    DailyTechnicalEligibilityState,
    DailyTechnicalPriceContinuityState,
    DailyTechnicalRequirement,
    DailyTechnicalRequirementProfile,
    DailyTechnicalSeriesSelectionState,
    DailyTechnicalVolumeContinuityState,
    StrictHistoricalPitTechnicalState,
    certify_daily_technical_eligibility,
    expected_nse_daily_sessions,
    expected_udiff_daily_sessions,
    ordinary_nse_udiff_daily_technical_series_policy,
    read_eligible_udiff_daily_bars,
    serialize_daily_technical_eligibility,
)
from app.market_data.technical_source_basis_action_coverage import (
    CorporateActionCoverageReason,
    CorporateActionCoverageState,
    SourceBasisEvidence,
    create_corporate_action_coverage_assertion,
)


AT = datetime(2026, 9, 6, 12, tzinfo=UTC)
INSTRUMENT = InstrumentIdentity(
    "NSE:INE000A01001", Exchange.NSE, "ALPHA", "ALPHA", "INE000A01001", "EQ",
    InstrumentType.NSE_EQUITY, "Alpha", "INR",
)
D1, D2, D3 = date(2024, 7, 8), date(2024, 7, 9), date(2024, 7, 10)


def bar(day: date, *, series: str = "EQ", symbol: str = "ALPHA", token: str = "101", volume: int | None = 1_000, provider: str = "nse_udiff_official") -> CanonicalOHLCVBar:
    start = datetime.combine(day, datetime.min.time(), tzinfo=UTC) - timedelta(hours=5, minutes=30)
    instrument = replace(INSTRUMENT, symbol=symbol, trading_symbol=symbol, series=series)
    return CanonicalOHLCVBar(
        f"udiff:{day.isoformat()}:{series}:{token}", instrument, Timeframe.DAILY, start, start + timedelta(days=1),
        Decimal("100"), Decimal("105"), Decimal("99"), Decimal("102"), volume, Decimal("102000"), 50,
        AdjustmentStatus.RAW,
        MarketDataProvenance(provider, f"NSE:CM:{token}", start, None, AT, "nse-udiff-final-bhavcopy-v1", "fixture", "https://nsearchives.nseindia.com/content/cm/fixture.zip"),
        DataQuality.HIGH,
        (f"NSE_UDIFF_BIZ_DATE:{day.isoformat()}", f"NSE_UDIFF_SERIES:{series}", "NSE_UDIFF_SESSION:F1"),
    )


def interval(value: CanonicalOHLCVBar) -> NseUdiffHistoricalSourceIdentityInterval:
    from app.market_data.nse_udiff_source_identity import source_fields

    fields = source_fields(value)
    values = dict(
        canonical_instrument_id=INSTRUMENT.instrument_id, isin=INSTRUMENT.isin,
        fin_instrm_id=fields["FinInstrmId"], source_symbol=fields["TckrSymb"], source_series=fields["SctySrs"],
        observed_trade_start=date.fromisoformat(fields["TradDt"]), observed_trade_end=date.fromisoformat(fields["TradDt"]),
        source_observation_ids=(value.source_observation_identity,), source_artifact_ids=("nse-udiff-artifact:fixture",),
        source_session_ids=("F1",), session_coverage_fingerprints=("sha256:" + "1" * 64,), known_at=AT,
        historical_known_at=None, source_family=NSE_UDIFF_SOURCE_FAMILY, source_version=NSE_UDIFF_SOURCE_VERSION,
        source_date_semantics="EXACT_NSE_UDIFF_TRADE_DATE_FACT", policy_version=IDENTITY_POLICY_VERSION,
    )
    fingerprint = identity_fingerprint(values)
    return NseUdiffHistoricalSourceIdentityInterval(
        interval_id="nse-udiff-identity-interval:" + fingerprint.removeprefix("sha256:")[:32],
        **values, fingerprint=fingerprint,
    )


def coverage(start: date = D1, end: date = D3, *, ready: bool = True):
    evidence = SourceBasisEvidence("nse-corporate-action-primary", "sha256:" + "2" * 64, True)
    reasons = (CorporateActionCoverageReason.OFFICIAL_SOURCE_WINDOW_COMPLETE,) if ready else (CorporateActionCoverageReason.SOURCE_WINDOW_NOT_ESTABLISHED,)
    return create_corporate_action_coverage_assertion(
        coverage_id="nse-action-coverage:fixture", canonical_instrument_id=INSTRUMENT.instrument_id,
        window_start=datetime.combine(start, datetime.min.time(), tzinfo=UTC),
        window_end=datetime.combine(end, datetime.max.time(), tzinfo=UTC), source_known_at=AT,
        source_evidence=evidence, covered_action_kinds=tuple(CorporateActionKind),
        coverage_state=CorporateActionCoverageState.READY if ready else CorporateActionCoverageState.NOT_READY,
        reasons=reasons,
    )


def action(kind: CorporateActionKind, day: date, *, action_id: str | None = None, as_of: datetime = AT):
    effective = datetime.combine(day, datetime.min.time(), tzinfo=UTC)
    return HistoricalCorporateAction(
        action_id or f"action:{kind.value}:{day.isoformat()}", INSTRUMENT.instrument_id, kind, effective, effective,
        effective, effective, Decimal("2") if kind in {CorporateActionKind.SPLIT, CorporateActionKind.BONUS} else None,
        Decimal("1") if kind in {CorporateActionKind.SPLIT, CorporateActionKind.BONUS} else None,
        kind.value, "NSE_OFFICIAL", "v1", as_of,
    )


_DEFAULT = object()


def receipt(*, bars=(bar(D1), bar(D2), bar(D3)), profile=DailyTechnicalRequirementProfile.PRICE_ONLY, actions=(), action_coverage=_DEFAULT, intervals=None, conflicts=(), expected=(D1, D2, D3)):
    values = tuple(bars)
    return certify_daily_technical_eligibility(
        canonical_instrument_id=INSTRUMENT.instrument_id, start_session=D1, end_session=D3,
        requirement=DailyTechnicalRequirement(profile), evaluation_as_of=AT, expected_sessions=expected,
        observed_bars=values, identity_intervals=tuple(interval(item) for item in values) if intervals is None else intervals,
        action_coverage=coverage() if action_coverage is _DEFAULT else action_coverage, actions=actions, conflicts=conflicts,
    )


def test_eq_series_selection_is_deterministic_and_current_descriptive_ready():
    first = receipt()
    second = receipt(bars=tuple(reversed((bar(D1), bar(D2), bar(D3)))))
    assert first == second
    assert first.eligibility is DailyTechnicalEligibilityState.READY
    assert first.series_state is DailyTechnicalSeriesSelectionState.SERIES_CONTINUITY_READY
    assert first.current_descriptive_state is CurrentDescriptiveDailyTechnicalState.READY


def test_compact_exact_isin_identity_intervals_feed_the_existing_certifier_without_bar_receipts():
    rows = (bar(D1), bar(D2), bar(D3))
    facts = []
    for item in rows:
        fields = source_fields(item)
        facts.append(NseUdiffIdentitySourceObservation(
            INSTRUMENT.instrument_id, INSTRUMENT.isin, fields["FinInstrmId"], fields["TckrSymb"], fields["SctySrs"],
            date.fromisoformat(fields["TradDt"]), fields["SsnId"], item.source_observation_identity,
            "nse-udiff-artifact:compact-fixture", AT,
        ))
    plan = build_effective_identity_coverage_plan(
        observations=facts, anchors=(NseUdiffIdentityAnchor(INSTRUMENT.instrument_id, INSTRUMENT.isin, "universe-snapshot:fixture", "sha256:" + "a" * 64),),
        session_dates=(D1, D2, D3), session_manifest_id="nse-udiff-session-manifest:fixture", session_manifest_fingerprint="sha256:" + "b" * 64,
    )
    assert not hasattr(plan.intervals[0], "source_observation_ids")
    value = receipt(bars=rows, intervals=NseUdiffEffectiveIdentityCoverageIndex(plan.intervals))
    assert value.eligibility is DailyTechnicalEligibilityState.READY


def test_ambiguous_identity_intervals_remain_a_fail_closed_certificate_reason():
    rows = (bar(D1), bar(D2), bar(D3))
    evidence = tuple(item for row in rows for item in (interval(row), interval(row)))
    value = receipt(bars=rows, intervals=evidence)
    assert DailyTechnicalEligibilityReason.HISTORICAL_IDENTITY_AMBIGUOUS in value.reasons


def test_bl_is_excluded_from_ordinary_daily_technical_read():
    value = receipt(bars=(bar(D1, series="BL"), bar(D2, series="BL"), bar(D3, series="BL")))
    assert value.eligibility is DailyTechnicalEligibilityState.NOT_READY
    assert DailyTechnicalEligibilityReason.BL_NOT_ORDINARY_DAILY_TECHNICAL_PRICE_SERIES in value.reasons


def test_coexisting_bl_does_not_substitute_for_or_contaminate_eq_selection():
    values = (
        bar(D1, series="EQ", token="101"), bar(D1, series="BL", token="201"),
        bar(D2, series="EQ", token="102"), bar(D3, series="EQ", token="103"),
    )
    value = receipt(bars=values, intervals=tuple(interval(item) for item in values))
    assert value.eligibility is DailyTechnicalEligibilityState.READY
    assert value.selected_series == ("EQ",)
    assert all(":BL:" not in bar_id for bar_id in value.source_bar_ids)


def test_t0_is_excluded_from_ordinary_daily_technical_read():
    value = receipt(bars=(bar(D1, series="T0"), bar(D2, series="T0"), bar(D3, series="T0")))
    assert value.series_state is DailyTechnicalSeriesSelectionState.SERIES_NON_COMPARABLE
    assert DailyTechnicalEligibilityReason.T0_DISTINCT_SETTLEMENT_SERIES in value.reasons


@pytest.mark.parametrize("series", ("BE", "BZ"))
def test_same_surveillance_series_is_independently_certifiable(series):
    value = receipt(bars=(bar(D1, series=series), bar(D2, series=series), bar(D3, series=series)))
    assert value.eligibility is DailyTechnicalEligibilityState.READY
    assert value.selected_series == (series,)


def test_eq_to_be_transition_is_not_silently_merged():
    value = receipt(bars=(bar(D1, series="EQ"), bar(D2, series="BE"), bar(D3, series="BE")))
    assert value.series_state is DailyTechnicalSeriesSelectionState.SERIES_REGIME_CHANGED
    assert value.price_continuity is DailyTechnicalPriceContinuityState.SERIES_TRANSITION_BLOCKED
    assert DailyTechnicalEligibilityReason.SERIES_TRANSITION_REQUIRES_TECHNICAL_POLICY in value.reasons


def test_unknown_series_fails_closed():
    value = receipt(bars=(bar(D1, series="XZ"), bar(D2, series="XZ"), bar(D3, series="XZ")))
    assert value.series_state is DailyTechnicalSeriesSelectionState.SERIES_POLICY_UNRESOLVED


def test_ambiguous_two_rows_for_one_security_session_fails_closed():
    values = (bar(D1, token="101"), bar(D1, token="102"), bar(D2), bar(D3))
    value = receipt(bars=values, intervals=tuple(interval(item) for item in values))
    assert DailyTechnicalEligibilityReason.AMBIGUOUS_SECURITY_SESSION in value.reasons


def test_expected_sessions_use_reconciled_udiff_manifest_and_exclude_confirmed_holiday():
    def acquired(day: date, status: NseUdiffDailyStatus):
        return acquisition_receipt(
            acquisition_id="nse-udiff-acquisition:fixture", trade_date=day, status=status, observed_at=AT,
            artifact_id="nse-udiff-artifact:fixture" if status is NseUdiffDailyStatus.ARTIFACT_VALID else None,
            source_url="https://nsearchives.nseindia.com/content/cm/fixture.zip", rows_seen=0, eligible_rows=0,
            exact_identity_rows=0, identity_discontinuities=0, unresolved_identity_rows=0, invalid_rows=0,
            zero_volume_rows=0, inserted=0, duplicates=0, conflicts=0,
            error_code=None if status is NseUdiffDailyStatus.ARTIFACT_VALID else "NSE_UDIFF_ARTIFACT_UNAVAILABLE",
        )
    manifest = build_udiff_session_coverage_manifest(
        acquisition_id="nse-udiff-acquisition:fixture", requested_dates=(date(2025, 8, 14), date(2025, 8, 15), date(2025, 8, 18)),
        receipts=(acquired(date(2025, 8, 14), NseUdiffDailyStatus.ARTIFACT_VALID), acquired(date(2025, 8, 15), NseUdiffDailyStatus.SOURCE_UNAVAILABLE), acquired(date(2025, 8, 18), NseUdiffDailyStatus.ARTIFACT_VALID)),
        calendar=nse_capital_market_calendar_2022_2026(), as_of=AT,
    )
    sessions = expected_udiff_daily_sessions(coverage=manifest, start_session=date(2025, 8, 14), end_session=date(2025, 8, 18))
    assert date(2025, 8, 15) not in sessions
    assert sessions == (date(2025, 8, 14), date(2025, 8, 18))


def test_unresolved_expected_session_fails_closed():
    with pytest.raises(DailyTechnicalEligibilityError, match="EXPECTED_SESSION_UNRESOLVED"):
        expected_nse_daily_sessions(
            calendar=nse_capital_market_calendar_2022_2026(), start_session=date(2027, 1, 4),
            end_session=date(2027, 1, 4), as_of=AT,
        )


def test_missing_required_security_session_blocks_window():
    value = receipt(bars=(bar(D1), bar(D3)))
    assert DailyTechnicalEligibilityReason.MISSING_REQUIRED_SECURITY_SESSION in value.reasons
    assert value.price_continuity is DailyTechnicalPriceContinuityState.SOURCE_GAP


def test_invalid_source_row_blocks_window():
    invalid = replace(bar(D2), provenance=replace(bar(D2).provenance, normalization_version="other"))
    value = receipt(bars=(bar(D1), invalid, bar(D3)), intervals=(interval(bar(D1)), interval(bar(D3))))
    assert DailyTechnicalEligibilityReason.SOURCE_ROW_INVALID in value.reasons


def test_effective_dated_identity_is_required_without_current_symbol_inference():
    value = receipt(intervals=())
    assert DailyTechnicalEligibilityReason.HISTORICAL_IDENTITY_REQUIRED in value.reasons
    assert value.price_continuity is DailyTechnicalPriceContinuityState.IDENTITY_GAP


def test_split_crossing_requires_derived_adjustment_but_does_not_materialise_one():
    value = receipt(actions=(action(CorporateActionKind.SPLIT, D2),))
    assert value.price_continuity is DailyTechnicalPriceContinuityState.ACTION_ADJUSTMENT_REQUIRED
    assert value.volume_continuity is DailyTechnicalVolumeContinuityState.VOLUME_ADJUSTMENT_REQUIRED
    assert DailyTechnicalEligibilityReason.SPLIT_ADJUSTMENT_REQUIRED in value.reasons


def test_bonus_crossing_requires_derived_adjustment():
    value = receipt(actions=(action(CorporateActionKind.BONUS, D2),))
    assert DailyTechnicalEligibilityReason.BONUS_ADJUSTMENT_REQUIRED in value.reasons


def test_rights_crossing_fails_closed_without_adjustment_formula():
    value = receipt(actions=(action(CorporateActionKind.RIGHTS, D2),))
    assert value.price_continuity is DailyTechnicalPriceContinuityState.COMPLEX_ACTION_NON_COMPARABLE
    assert DailyTechnicalEligibilityReason.RIGHTS_ADJUSTMENT_NOT_READY in value.reasons


@pytest.mark.parametrize("kind", (CorporateActionKind.DEMERGER, CorporateActionKind.MERGER, CorporateActionKind.SUSPENSION))
def test_complex_actions_are_non_comparable(kind):
    value = receipt(actions=(action(kind, D2),))
    assert value.price_continuity is DailyTechnicalPriceContinuityState.COMPLEX_ACTION_NON_COMPARABLE


def test_dividend_policy_remains_unresolved_and_is_not_total_return():
    value = receipt(actions=(action(CorporateActionKind.DIVIDEND, D2),))
    assert DailyTechnicalEligibilityReason.DIVIDEND_PRICE_POLICY_NOT_APPROVED in value.reasons
    assert value.eligibility is DailyTechnicalEligibilityState.NOT_READY


def test_action_after_requested_window_does_not_leak_backward():
    value = receipt(actions=(action(CorporateActionKind.SPLIT, date(2024, 7, 11)),))
    assert value.eligibility is DailyTechnicalEligibilityState.READY
    assert not {DailyTechnicalEligibilityReason.SPLIT_ADJUSTMENT_REQUIRED} & set(value.reasons)


def test_symbol_change_does_not_break_proven_identity_continuity():
    value = receipt(actions=(action(CorporateActionKind.SYMBOL_CHANGE, D2),))
    assert value.eligibility is DailyTechnicalEligibilityState.READY


def test_price_only_keeps_valid_zero_volume_fact_without_failing_price_continuity():
    value = receipt(bars=(bar(D1), bar(D2, volume=0), bar(D3)))
    assert value.eligibility is DailyTechnicalEligibilityState.READY
    assert value.volume_continuity is DailyTechnicalVolumeContinuityState.VOLUME_NOT_REQUIRED


def test_price_and_volume_requires_positive_volume_but_price_remains_ready():
    value = receipt(bars=(bar(D1), bar(D2, volume=0), bar(D3)), profile=DailyTechnicalRequirementProfile.PRICE_AND_VOLUME)
    assert value.price_continuity is DailyTechnicalPriceContinuityState.PRICE_CONTINUITY_READY
    assert value.volume_continuity is DailyTechnicalVolumeContinuityState.VOLUME_NOT_READY


def test_raw_exchange_history_profile_makes_no_continuity_claim():
    value = receipt(profile=DailyTechnicalRequirementProfile.RAW_EXCHANGE_HISTORY_ONLY, actions=(action(CorporateActionKind.SPLIT, D2),))
    assert value.eligibility is DailyTechnicalEligibilityState.READY
    assert value.price_continuity is DailyTechnicalPriceContinuityState.NOT_APPLICABLE
    assert value.volume_continuity is DailyTechnicalVolumeContinuityState.NOT_APPLICABLE


def test_action_coverage_is_required_and_an_absent_receipt_is_not_no_action():
    value = receipt(action_coverage=None)
    assert value.eligibility is DailyTechnicalEligibilityState.NOT_READY
    assert DailyTechnicalEligibilityReason.ACTION_COVERAGE_REQUIRED in value.reasons


def test_incomplete_action_coverage_blocks_continuity():
    value = receipt(action_coverage=coverage(ready=False))
    assert DailyTechnicalEligibilityReason.ACTION_COVERAGE_NOT_READY in value.reasons


def test_same_provider_conflict_blocks_without_upstox_fallback():
    source = bar(D2)
    values = dict(
        conflict_fingerprint="a" * 64, canonical_instrument_id=INSTRUMENT.instrument_id, trade_date=D2,
        state=NseUdiffConflictState.CONFLICT_UNRESOLVED, cause=NseUdiffConflictCause.SAME_KEY_DIFFERING_OHLCV,
        stored_provider_reference="NSE:CM:101", incoming_provider_reference="NSE:CM:101",
        source_identity="https://nsearchives.nseindia.com/content/cm/fixture.zip", differing_fields=("close",),
    )
    conflict = NseUdiffConflictAssessment(**values, fingerprint=conflict_fingerprint(_conflict_payload(values)))
    value = receipt(conflicts=(conflict,))
    assert value.price_continuity is DailyTechnicalPriceContinuityState.SOURCE_CONFLICT
    assert DailyTechnicalEligibilityReason.SAME_PROVIDER_CONFLICT in value.reasons
    assert source.provenance.provider == "nse_udiff_official"


def test_eligible_read_returns_only_receipt_selected_udiff_bars():
    values = (bar(D1), bar(D2), bar(D3))
    value = receipt(bars=values)
    read = read_eligible_udiff_daily_bars(receipt=value, observed_bars=tuple(reversed(values)))
    assert read.bars == values


def test_eligible_read_fails_closed_when_receipt_is_not_ready():
    with pytest.raises(DailyTechnicalEligibilityError, match="NOT_READY"):
        read_eligible_udiff_daily_bars(receipt=receipt(intervals=()), observed_bars=(bar(D1), bar(D2), bar(D3)))


def test_strict_historical_pit_remains_not_ready_while_current_descriptive_use_can_be_ready():
    value = receipt()
    assert value.strict_historical_pit_state is StrictHistoricalPitTechnicalState.NOT_READY
    assert DailyTechnicalEligibilityReason.HISTORICAL_SOURCE_AVAILABILITY_UNAVAILABLE in value.reasons


def test_exact_lookback_window_completeness_is_per_window_not_a_global_boolean():
    recent = certify_daily_technical_eligibility(
        canonical_instrument_id=INSTRUMENT.instrument_id, start_session=D2, end_session=D3,
        requirement=DailyTechnicalRequirement(DailyTechnicalRequirementProfile.PRICE_ONLY), evaluation_as_of=AT,
        expected_sessions=(D2, D3), observed_bars=(bar(D2), bar(D3)), identity_intervals=(interval(bar(D2)), interval(bar(D3))),
        action_coverage=coverage(D2, D3),
    )
    assert recent.eligibility is DailyTechnicalEligibilityState.READY
    assert receipt(bars=(bar(D1), bar(D2))).eligibility is DailyTechnicalEligibilityState.NOT_READY


def test_receipt_serialization_and_fingerprint_are_stable():
    value = receipt()
    assert serialize_daily_technical_eligibility(value) == serialize_daily_technical_eligibility(receipt())
    with pytest.raises(DailyTechnicalEligibilityError, match="RECEIPT_INVALID"):
        replace(value, selected_series=("BE",))


def test_duplicate_actions_fail_closed_without_silent_deduplication():
    first = action(CorporateActionKind.SPLIT, D2, action_id="action:duplicate")
    value = receipt(actions=(first, replace(first, details="different")))
    assert DailyTechnicalEligibilityReason.DUPLICATE_ACTION_ID in value.reasons


def test_no_indicator_weekly_or_execution_dependency_exists():
    source = Path("app/market_data/nse_udiff_daily_technical_eligibility.py").read_text(encoding="utf-8")
    imports = tuple(item.module for item in ast.walk(ast.parse(source)) if isinstance(item, ast.ImportFrom) and item.module)
    forbidden = ("app.analysis", "app.diagnostics", "app.signals", "app.portfolio", "app.broker", "app.orders", "app.api", "app.ui")
    assert not any(module == name or module.startswith(name + ".") for module in imports for name in forbidden)
    assert "datetime.now" not in source and "Timeframe.WEEKLY" not in source
