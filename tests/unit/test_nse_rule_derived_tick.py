from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from app.market_data.reference_data.nse_rule_derived_tick import (
    NSE_CMTR_67133_RULE_ID,
    NseRuleDerivedTickMaterializer,
    NseRuleDerivedTickTarget,
    NseTickRuleEligibility,
    nse_cmtr_67133_tick_size,
)
from app.market_data.reference_data.resolver import TickSizeReferenceResolver, TickSizeResolutionStatus
from app.market_data.reference_data.sqlite_repository import SQLiteTickSizeObservationRepository
from app.universe_analysis.models import NseEquityInstrument


REFERENCE = datetime(2026, 8, 31, tzinfo=UTC)
RECEIVED = datetime(2026, 9, 1, 14, 30, tzinfo=UTC)
SOURCE = "https://archives.nseindia.com/products/content/sec_bhavdata_full_31082026.csv"


def _instrument(*, symbol: str = "ALPHA", isin: str = "INE000A01001", security_type: str = "EQUITY", listing_date=None) -> NseEquityInstrument:
    return NseEquityInstrument(
        f"NSE:{isin}", symbol, isin, None, None, "LISTED", listing_date, True,
        datetime(2026, 8, 1, tzinfo=UTC), "NSE", security_type=security_type, exchange="NSE",
    )


def _file(path: Path, *rows: tuple[str, str, str]) -> Path:
    content = "SYMBOL, SERIES, DATE1, CLOSE_PRICE\n" + "\n".join(
        f"{symbol}, {series}, 31-Aug-2026, {close}" for symbol, series, close in rows
    ) + "\n"
    path.write_text(content, encoding="utf-8")
    return path


@pytest.mark.parametrize(("price", "expected"), (
    ("249.99", "0.01"), ("250", "0.05"), ("1000", "0.05"), ("1000.01", "0.10"),
    ("5000", "0.10"), ("5000.01", "0.50"), ("10000", "0.50"), ("10000.01", "1.00"),
    ("20000", "1.00"), ("20000.01", "5.00"),
))
def test_nse_cmtr_67133_exact_bucket_boundaries(price: str, expected: str) -> None:
    assert nse_cmtr_67133_tick_size(Decimal(price)) == Decimal(expected)


def test_official_bhavcopy_derives_immutable_monthly_tick_and_resolver_is_pit_safe(tmp_path: Path) -> None:
    path = _file(tmp_path / "sec_bhavdata_full_31082026.csv", ("ALPHA", "EQ", "250.00"))
    repository = SQLiteTickSizeObservationRepository(tmp_path / "ticks.sqlite")
    target = NseRuleDerivedTickTarget.from_instrument(_instrument())
    report = NseRuleDerivedTickMaterializer(repository, (target,)).materialize(
        path, source_url=SOURCE, received_at=RECEIVED, effective_month="2026-09", reference_trade_date=REFERENCE,
    )
    result = report.results[0]
    assert (report.eligible, report.derived, report.exceptions, report.blocked, report.conflicts) == (1, 1, 0, 0, 0)
    assert result.reference_close == Decimal("250.00") and result.tick_size == Decimal("0.05")
    assert result.observation_id and report.reference_session == datetime(2026, 8, 30, 18, 30, tzinfo=UTC)
    observation = repository.get_tick_size_observation(result.observation_id)
    assert observation is not None
    assert observation.rule_id == NSE_CMTR_67133_RULE_ID
    assert observation.effective_month == "2026-09"
    assert observation.reference_close == Decimal("250.00")
    assert observation.source_artifact_reference == SOURCE
    assert "NSE_SECURITY_FILE_TICKSZ_BLANK_PRESERVED" in observation.warnings
    resolver = TickSizeReferenceResolver(repository)
    assert resolver.resolve_tick_size(target.canonical_instrument_id, as_of=RECEIVED.replace(minute=29)).status is TickSizeResolutionStatus.TICK_SIZE_UNAVAILABLE_FOR_AS_OF
    available = resolver.resolve_tick_size(target.canonical_instrument_id, as_of=RECEIVED)
    assert available.status is TickSizeResolutionStatus.AVAILABLE and available.tick_size == Decimal("0.05")
    assert resolver.resolve_tick_size(target.canonical_instrument_id, as_of=datetime(2026, 10, 1, tzinfo=UTC)).status is TickSizeResolutionStatus.TICK_SIZE_UNAVAILABLE_FOR_AS_OF


def test_same_rule_run_is_idempotent_and_reopens_with_full_lineage(tmp_path: Path) -> None:
    path = _file(tmp_path / "sec_bhavdata_full_31082026.csv", ("ALPHA", "EQ", "5000.01"))
    database = tmp_path / "ticks.sqlite"; repository = SQLiteTickSizeObservationRepository(database)
    materializer = NseRuleDerivedTickMaterializer(repository, (NseRuleDerivedTickTarget.from_instrument(_instrument()),))
    first = materializer.materialize(path, source_url=SOURCE, received_at=RECEIVED, effective_month="2026-09", reference_trade_date=REFERENCE)
    second = materializer.materialize(path, source_url=SOURCE, received_at=RECEIVED, effective_month="2026-09", reference_trade_date=REFERENCE)
    assert (first.derived, second.derived, second.duplicates, second.conflicts) == (1, 0, 1, 0)
    reopened = SQLiteTickSizeObservationRepository(database)
    assert reopened.get_tick_size_observation(first.results[0].observation_id) == repository.get_tick_size_observation(first.results[0].observation_id)


def test_etf_and_new_listing_and_corporate_action_are_not_derived(tmp_path: Path) -> None:
    path = _file(tmp_path / "sec_bhavdata_full_31082026.csv", ("ETF", "EQ", "100"), ("IPO", "EQ", "100"), ("CA", "EQ", "100"))
    targets = (
        NseRuleDerivedTickTarget.from_instrument(_instrument(symbol="ETF", isin="INF000A01001", security_type="ETF")),
        NseRuleDerivedTickTarget.from_instrument(_instrument(symbol="IPO", isin="INE000A01002", listing_date=REFERENCE)),
        NseRuleDerivedTickTarget.from_instrument(_instrument(symbol="CA", isin="INE000A01003"), corporate_action_exception=True),
    )
    report = NseRuleDerivedTickMaterializer(SQLiteTickSizeObservationRepository(tmp_path / "ticks.sqlite"), targets).materialize(
        path, source_url=SOURCE, received_at=RECEIVED, effective_month="2026-09", reference_trade_date=REFERENCE,
    )
    assert report.derived == 0 and report.exceptions == 3 and report.blocked == 3
    assert {row.eligibility for row in report.results} == {
        NseTickRuleEligibility.ETF_EXCLUDED, NseTickRuleEligibility.NEW_LISTING_SPECIAL_CASE,
        NseTickRuleEligibility.CORPORATE_ACTION_SPECIAL_CASE,
    }


def test_invalid_source_identity_missing_close_and_unsupported_security_fail_closed(tmp_path: Path) -> None:
    path = _file(tmp_path / "sec_bhavdata_full_31082026.csv", ("OTHER", "EQ", "100"))
    ordinary = NseRuleDerivedTickTarget.from_instrument(_instrument())
    unsupported = NseRuleDerivedTickTarget.from_instrument(_instrument(symbol="BOND", isin="INE000A01009", security_type="BOND"))
    materializer = NseRuleDerivedTickMaterializer(SQLiteTickSizeObservationRepository(tmp_path / "ticks.sqlite"), (ordinary, unsupported))
    with pytest.raises(ValueError, match="OFFICIAL_SOURCE"):
        materializer.materialize(path, source_url="https://example.invalid/bhavcopy.csv", received_at=RECEIVED, effective_month="2026-09", reference_trade_date=REFERENCE)
    report = materializer.materialize(path, source_url=SOURCE, received_at=RECEIVED, effective_month="2026-09", reference_trade_date=REFERENCE)
    assert {row.blocker for row in report.results} == {"OFFICIAL_NSE_REFERENCE_CLOSE_UNAVAILABLE", NseTickRuleEligibility.UNSUPPORTED_SECURITY_CLASS}


def test_setup_does_not_embed_the_nse_price_bucket_rule() -> None:
    source = (Path(__file__).parents[2] / "app" / "strategies" / "pre_breakout" / "setup_assessment.py").read_text(encoding="utf-8")
    assert "NSE_CMTR_67133" not in source and "nse_cmtr_67133_tick_size" not in source
