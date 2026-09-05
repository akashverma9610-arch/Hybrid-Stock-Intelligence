from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
import ast
import inspect

import pytest

from app.market_data.models import AdjustmentStatus, CanonicalOHLCVBar, Exchange, InstrumentIdentity, InstrumentType, MarketDataProvenance, Timeframe
from app.market_data.technical_bar_contract import (
    CanonicalTechnicalBar,
    CanonicalTechnicalInterval,
    DerivedTechnicalBarAggregation,
    ProviderIntervalRepresentation,
    TechnicalBarCompletenessState,
    TechnicalBarContractError,
    TechnicalBarOrigin,
    TechnicalBarReadiness,
    TechnicalBarReason,
    TechnicalIntervalSemantics,
    TechnicalIntervalUnit,
    TechnicalTradingPeriod,
    TechnicalVolumeReadiness,
    derive_closed_bar,
    make_bar_receipt,
    make_native_technical_bar,
    serialize_derived_technical_bar,
    serialize_technical_bar_receipt,
)


T = datetime(2026, 8, 25, 10, tzinfo=UTC)
FP = "sha256:" + "a" * 64


def identity() -> InstrumentIdentity:
    return InstrumentIdentity("NSE:ALPHA", Exchange.NSE, "ALPHA", "ALPHA", "INE000A01001", "EQ", InstrumentType.NSE_EQUITY, "Alpha")


def period(*, start: datetime = T - timedelta(hours=1), end: datetime = T, sessions: tuple[date, ...] = (date(2026, 8, 25),)) -> TechnicalTradingPeriod:
    return TechnicalTradingPeriod(Exchange.NSE, "CAPITAL_MARKET", f"period:{start.date().isoformat()}:{end.date().isoformat()}", sessions, start, end, "Asia/Kolkata", "nse-calendar-v1", FP, ("session-source",), (FP,))


def bar(identifier: str, *, start: datetime = T - timedelta(hours=1), end: datetime = T, close: str = "102", volume: int | None = 100, adjustment: AdjustmentStatus = AdjustmentStatus.RAW) -> CanonicalOHLCVBar:
    return CanonicalOHLCVBar(identifier, identity(), Timeframe.DAILY, start, end, Decimal("100"), Decimal("105"), Decimal("99"), Decimal(close), volume, None, None, adjustment, MarketDataProvenance("fixture", "fixture-alpha", end, end, end + timedelta(minutes=2), "fixture-v1"))


def native(identifier: str, *, start: datetime = T - timedelta(hours=1), end: datetime = T, close: str = "102", volume: int | None = 100, adjustment: AdjustmentStatus = AdjustmentStatus.RAW) -> CanonicalTechnicalBar:
    item = bar(identifier, start=start, end=end, close=close, volume=volume, adjustment=adjustment)
    return make_native_technical_bar(market_bar=item, period=period(start=start, end=end), state=TechnicalBarCompletenessState.CLOSED, readiness=TechnicalBarReadiness.READY if adjustment is not AdjustmentStatus.UNKNOWN else TechnicalBarReadiness.PARTIAL, known_at=end + timedelta(minutes=2), provider_interval=ProviderIntervalRepresentation("fixture", "1D"))


def test_interval_identity_is_typed_and_four_hour_is_explicitly_unresolved() -> None:
    fifteen = CanonicalTechnicalInterval(TechnicalIntervalUnit.MINUTE, 15)
    monthly = CanonicalTechnicalInterval(TechnicalIntervalUnit.MONTH, 1)
    four_hour = CanonicalTechnicalInterval(TechnicalIntervalUnit.HOUR, 4, TechnicalIntervalSemantics.FOUR_HOUR_SEMANTICS_UNRESOLVED)
    assert (fifteen.interval_id, monthly.interval_id, monthly.stored_timeframe, four_hour.interval_id) == ("15m", "1M", None, "4H")
    with pytest.raises(TechnicalBarContractError, match="SEMANTICS"):
        CanonicalTechnicalInterval(TechnicalIntervalUnit.HOUR, 4)


def test_closed_native_bar_is_deterministic_and_requires_known_at_after_close() -> None:
    first = native("native-a")
    second = native("native-a")
    assert first.canonical_bar_id == second.canonical_bar_id
    assert first.fingerprint == second.fingerprint
    assert first.receipt.known_at == T + timedelta(minutes=2)
    assert serialize_technical_bar_receipt(first.receipt) == serialize_technical_bar_receipt(second.receipt)
    with pytest.raises(TechnicalBarContractError, match="CLOSED_BAR"):
        make_native_technical_bar(market_bar=bar("bad"), period=period(), state=TechnicalBarCompletenessState.CLOSED, readiness=TechnicalBarReadiness.READY, known_at=T - timedelta(seconds=1), provider_interval=ProviderIntervalRepresentation("fixture", "1D"))


def test_receipts_keep_missing_conflict_and_unknown_adjustment_explicit() -> None:
    interval = CanonicalTechnicalInterval(TechnicalIntervalUnit.HOUR, 4, TechnicalIntervalSemantics.FOUR_HOUR_SEMANTICS_UNRESOLVED)
    receipt = make_bar_receipt(canonical_bar_id="technical-bar:missing", interval=interval, period=None, state=TechnicalBarCompletenessState.EVIDENCE_CONFLICTED, readiness=TechnicalBarReadiness.SEMANTICS_UNRESOLVED, adjustment_status=AdjustmentStatus.UNKNOWN, reasons=(TechnicalBarReason.INTERVAL_SEMANTICS_UNRESOLVED, TechnicalBarReason.PROVIDER_EVIDENCE_CONFLICTED))
    assert receipt.adjustment_status is AdjustmentStatus.UNKNOWN
    assert receipt.state is TechnicalBarCompletenessState.EVIDENCE_CONFLICTED
    assert "PROVIDER_EVIDENCE_CONFLICTED" in serialize_technical_bar_receipt(receipt)
    with pytest.raises(TechnicalBarContractError, match="RECEIPT"):
        make_bar_receipt(canonical_bar_id="technical-bar:bad", interval=CanonicalTechnicalInterval(TechnicalIntervalUnit.DAY, 1), period=None, state=TechnicalBarCompletenessState.DATA_MISSING, readiness=TechnicalBarReadiness.NOT_READY, expected_source_bar_ids=("",), reasons=(TechnicalBarReason.SOURCE_BAR_MISSING,))


def test_derived_weekly_aggregation_is_exact_closed_and_known_after_sources() -> None:
    first_end = T - timedelta(days=1)
    first = native("source-a", start=first_end - timedelta(hours=1), end=first_end, close="102", volume=100)
    second = native("source-b", start=T - timedelta(hours=1), end=T, close="104", volume=200)
    target = period(start=first.market_bar.start_time, end=T, sessions=(date(2026, 8, 24), date(2026, 8, 25)))
    result = derive_closed_bar(interval=CanonicalTechnicalInterval(TechnicalIntervalUnit.WEEK, 1), period=target, expected_source_bar_ids=(first.canonical_bar_id, second.canonical_bar_id), source_bars=(second, first))
    assert (result.open, result.high, result.low, result.close, result.volume) == (Decimal("100"), Decimal("105"), Decimal("99"), Decimal("104"), 300)
    assert result.known_at == T + timedelta(minutes=2)
    assert result.volume_readiness is TechnicalVolumeReadiness.READY
    assert serialize_derived_technical_bar(result) == serialize_derived_technical_bar(result)


def test_derived_bar_fails_closed_for_gap_adjustment_or_unclosed_source() -> None:
    first, second = native("source-a"), native("source-b", start=T + timedelta(days=1), end=T + timedelta(days=1, hours=1))
    target = period(start=T - timedelta(hours=1), end=T + timedelta(days=1, hours=1), sessions=(date(2026, 8, 25), date(2026, 8, 26)))
    with pytest.raises(TechnicalBarContractError, match="COVERAGE"):
        derive_closed_bar(interval=CanonicalTechnicalInterval(TechnicalIntervalUnit.WEEK, 1), period=target, expected_source_bar_ids=(first.canonical_bar_id,), source_bars=(first, second))
    unknown_end = T - timedelta(days=1)
    unknown = native("unknown", start=unknown_end - timedelta(hours=1), end=unknown_end, adjustment=AdjustmentStatus.UNKNOWN)
    adjustment_target = period(start=unknown.market_bar.start_time, end=T, sessions=(date(2026, 8, 24), date(2026, 8, 25)))
    with pytest.raises(TechnicalBarContractError, match="ADJUSTMENT"):
        derive_closed_bar(interval=CanonicalTechnicalInterval(TechnicalIntervalUnit.WEEK, 1), period=adjustment_target, expected_source_bar_ids=(first.canonical_bar_id, unknown.canonical_bar_id), source_bars=(first, unknown))
    incomplete = make_native_technical_bar(market_bar=bar("in-progress"), period=period(), state=TechnicalBarCompletenessState.IN_PROGRESS, readiness=TechnicalBarReadiness.NOT_READY, known_at=None, provider_interval=ProviderIntervalRepresentation("fixture", "1D"), reasons=(TechnicalBarReason.BAR_NOT_CLOSED,))
    with pytest.raises(TechnicalBarContractError, match="SOURCE_BAR_NOT_CLOSED"):
        derive_closed_bar(interval=CanonicalTechnicalInterval(TechnicalIntervalUnit.WEEK, 1), period=period(), expected_source_bar_ids=(incomplete.canonical_bar_id,), source_bars=(incomplete,))


def test_missing_volume_remains_explicit_without_invalidating_price_bar() -> None:
    value = native("no-volume", volume=None)
    assert value.receipt.volume_readiness is TechnicalVolumeReadiness.VOLUME_NOT_READY
    assert value.market_bar.close == Decimal("102")


def test_monthly_holiday_shortened_aggregation_preserves_no_synthetic_volume_or_session() -> None:
    first_end = T - timedelta(days=2)
    first = native("month-source-a", start=first_end - timedelta(hours=1), end=first_end, volume=100)
    second = native("month-source-b", start=T - timedelta(hours=1), end=T, volume=None)
    shortened = period(start=first.market_bar.start_time, end=T, sessions=(date(2026, 8, 23), date(2026, 8, 25)))
    result = derive_closed_bar(interval=CanonicalTechnicalInterval(TechnicalIntervalUnit.MONTH, 1), period=shortened, expected_source_bar_ids=(first.canonical_bar_id, second.canonical_bar_id), source_bars=(first, second))
    assert result.volume is None
    assert result.volume_readiness is TechnicalVolumeReadiness.VOLUME_NOT_READY
    assert result.period.session_dates == (date(2026, 8, 23), date(2026, 8, 25))


def test_derived_bar_rejects_cross_session_source_and_unresolved_four_hour() -> None:
    source = native("cross-session")
    other_calendar = TechnicalTradingPeriod(Exchange.NSE, "CAPITAL_MARKET", "other-period", (date(2026, 8, 25),), T - timedelta(hours=1), T, "Asia/Kolkata", "other-calendar", "sha256:" + "b" * 64, ("other-source",), ("sha256:" + "b" * 64,))
    with pytest.raises(TechnicalBarContractError, match="SESSION"):
        derive_closed_bar(interval=CanonicalTechnicalInterval(TechnicalIntervalUnit.WEEK, 1), period=other_calendar, expected_source_bar_ids=(source.canonical_bar_id,), source_bars=(source,))
    with pytest.raises(TechnicalBarContractError, match="FOUR_HOUR"):
        derive_closed_bar(interval=CanonicalTechnicalInterval(TechnicalIntervalUnit.HOUR, 4, TechnicalIntervalSemantics.FOUR_HOUR_SEMANTICS_UNRESOLVED), period=period(), expected_source_bar_ids=(source.canonical_bar_id,), source_bars=(source,))


def test_contract_is_immutable_and_has_no_forbidden_runtime_dependencies() -> None:
    value = native("immutable")
    with pytest.raises(AttributeError):
        value.canonical_bar_id = "changed"  # type: ignore[misc]
    source = inspect.getsource(__import__("app.market_data.technical_bar_contract", fromlist=["*"]))
    imports = [node.module or "" for node in ast.walk(ast.parse(source)) if isinstance(node, ast.ImportFrom)]
    imports += [name.name for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Import) for name in node.names]
    assert not any(name.startswith(("app.signals", "app.portfolio", "app.api", "sqlite")) for name in imports)
