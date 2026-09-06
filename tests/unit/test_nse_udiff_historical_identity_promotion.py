from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from app.historical.bse_lifecycle import BseLifecycleEventType, BsePrimaryLifecycleEvidence
from app.historical.nse_capital_market_session_evidence_2022_2026 import nse_capital_market_calendar_2022_2026
from app.historical.nse_udiff_identity_promotion import (
    NseUdiffHistoricalIdentityPromotionService,
    NseUdiffHistoricalIdentityState,
    NseUdiffPromotionOutcome,
    build_nse_udiff_historical_identity_promotion_plan,
)
from app.market_data.historical import SQLiteHistoricalBarStore
from app.market_data.models import Timeframe
from app.market_data.nse_udiff_daily_history import (
    NseUdiffDailyFetchResult, NseUdiffDailyStatus, NseUdiffDailyTarget,
    _artifact_from_bytes, _receipt, nse_udiff_daily_url,
)
from app.market_data.nse_udiff_daily_integrity import build_udiff_session_coverage_manifest
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository
from app.universe_analysis.models import NseEquityInstrument
from tests.unit.test_nse_udiff_daily_history import archive, row


T = datetime(2026, 9, 6, 12, tzinfo=UTC)
ACQUISITION = "nse-udiff-acquisition:identity-fixture"
ISIN = "INE000A01001"
CURRENT = "CURRENT"
OLD = "OLDNAME"


def target(*, isin: str = ISIN, symbol: str = CURRENT) -> NseUdiffDailyTarget:
    return NseUdiffDailyTarget.from_instrument(NseEquityInstrument(
        f"NSE:{isin}", symbol, isin, None, None, "LISTED", None, True, T,
        "NSE", security_type="EQUITY", exchange="NSE",
    ))


def source_row(day: date, *, symbol: str, isin: str = ISIN, series: str = "EQ", token: str = "4963") -> dict[str, str]:
    return {
        **row(symbol=symbol, isin=isin), "TradDt": day.isoformat(), "BizDt": day.isoformat(),
        "SctySrs": series, "FinInstrmId": token,
    }


def artifact(day: date, *rows: dict[str, str]):
    raw = archive(rows, filename=f"BhavCopy_NSE_CM_0_0_0_{day:%Y%m%d}_F_0000.csv")
    return _artifact_from_bytes(ACQUISITION, NseUdiffDailyFetchResult(
        NseUdiffDailyStatus.ARTIFACT_VALID, day, nse_udiff_daily_url(day), T, raw,
    ))


def coverage(*artifacts):
    return build_udiff_session_coverage_manifest(
        acquisition_id=ACQUISITION,
        requested_dates=tuple(item.trade_date for item in artifacts),
        receipts=tuple(_receipt(
            acquisition_id=ACQUISITION, trade_date=item.trade_date,
            status=NseUdiffDailyStatus.ARTIFACT_VALID, observed_at=T,
            artifact_id=item.artifact_id, source_url=item.source_url, rows_seen=item.row_count,
            eligible_rows=0, exact_identity_rows=0, identity_discontinuities=0,
            unresolved_identity_rows=0, invalid_rows=0, zero_volume_rows=0,
            inserted=0, duplicates=0, conflicts=0, error_code=None,
        ) for item in artifacts), calendar=nse_capital_market_calendar_2022_2026(), as_of=T,
        artifact_session_ids={item.trade_date: ("F1",) for item in artifacts},
    )


def service(tmp_path: Path, *artifacts, targets=(target(),), lifecycle=()):
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "core.sqlite")
    bars = SQLiteHistoricalBarStore(tmp_path / "bars.sqlite")
    return NseUdiffHistoricalIdentityPromotionService(
        repository=repository, bars=bars, artifacts=artifacts, targets=targets,
        session_coverage=coverage(*artifacts), lifecycle_evidence=lifecycle,
    ), bars, repository


def test_same_isin_symbol_change_preserves_historical_source_symbol_and_replays_idempotently(tmp_path: Path):
    old_day, current_day = date(2024, 7, 8), date(2024, 7, 9)
    first, second = artifact(old_day, source_row(old_day, symbol=OLD)), artifact(current_day, source_row(current_day, symbol=CURRENT))
    value, bars, _ = service(tmp_path, first, second)
    plan = value.plan()
    receipt = plan.receipts[0]
    assert receipt.continuity_state is NseUdiffHistoricalIdentityState.SAME_SECURITY_SYMBOL_CHANGE_PROVEN
    assert receipt.outcome is NseUdiffPromotionOutcome.PROMOTED_ADDRESSABLE
    assert plan.intervals[0].source_symbol == OLD and plan.identities[0].symbol == OLD
    a, b = value.promote(), value.promote()
    assert (a.source_rows_addressable, a.bars_inserted, a.bars_already_present) == (1, 1, 0)
    assert (b.intervals_inserted, b.identities_inserted, b.receipts_inserted, b.bars_inserted, b.bars_already_present) == (0, 0, 0, 0, 1)
    raw = bars.raw_range(f"NSE:{ISIN}", Timeframe.DAILY, datetime(2024, 7, 7, tzinfo=UTC), T)
    old_bar = next(item for item in raw if item.instrument.symbol == OLD)
    assert old_bar.instrument.trading_symbol == OLD and old_bar.instrument.symbol != CURRENT
    assert bars.range(f"NSE:{ISIN}", Timeframe.DAILY, datetime(2024, 7, 7, tzinfo=UTC), T) == ()
    bars.close()


def test_series_variants_remain_distinct_and_bl_t0_never_become_eq(tmp_path: Path):
    old_day, current_day = date(2024, 7, 8), date(2024, 7, 9)
    first = artifact(old_day, source_row(old_day, symbol=OLD, series="BL", token="100"), source_row(old_day, symbol=OLD, series="T0", token="200"))
    second = artifact(current_day, source_row(current_day, symbol=CURRENT, series="BL", token="100"), source_row(current_day, symbol=CURRENT, series="T0", token="200"))
    value, bars, _ = service(tmp_path, first, second)
    plan = value.plan()
    receipt = plan.receipts[0]
    assert receipt.continuity_state is NseUdiffHistoricalIdentityState.SAME_ISIN_SERIES_VARIANT
    assert receipt.series_technical_state is NseUdiffHistoricalIdentityState.SERIES_TRANSITION_REQUIRES_TECHNICAL_POLICY
    assert {item.source_series for item in plan.intervals} == {"BL", "T0"}
    report = value.promote()
    assert (report.source_rows_addressable, report.bars_inserted) == (2, 2)
    raw = bars.raw_range(f"NSE:{ISIN}", Timeframe.DAILY, datetime(2024, 7, 7, tzinfo=UTC), T)
    labels = {next(w.removeprefix("NSE_UDIFF_SERIES:") for w in item.warnings if w.startswith("NSE_UDIFF_SERIES:")) for item in raw}
    assert labels == {"BL", "T0"} and bars.latest(f"NSE:{ISIN}", Timeframe.DAILY, 10) == ()
    bars.close()


def test_source_intervals_follow_observed_sessions_not_calendar_dates(tmp_path: Path):
    friday, monday, tuesday = date(2024, 7, 12), date(2024, 7, 15), date(2024, 7, 16)
    old_one = artifact(friday, source_row(friday, symbol=OLD))
    old_two = artifact(monday, source_row(monday, symbol=OLD))
    current = artifact(tuesday, source_row(tuesday, symbol=CURRENT))
    value, bars, _ = service(tmp_path, old_one, old_two, current)
    interval = value.plan().intervals[0]
    assert (interval.observed_trade_start, interval.observed_trade_end, len(interval.source_observation_ids)) == (friday, monday, 2)
    bars.close()


def test_token_change_is_not_a_break_when_exact_isin_and_current_chronology_are_present(tmp_path: Path):
    first_day, second_day, third_day = date(2024, 7, 8), date(2024, 7, 9), date(2024, 7, 10)
    old_one = artifact(first_day, source_row(first_day, symbol=OLD, token="100"))
    old_two = artifact(second_day, source_row(second_day, symbol=OLD, token="200"))
    current = artifact(third_day, source_row(third_day, symbol=CURRENT, token="100"), source_row(third_day, symbol=CURRENT, token="200"))
    value, bars, _ = service(tmp_path, old_one, old_two, current)
    receipt = value.plan().receipts[0]
    assert receipt.continuity_state is NseUdiffHistoricalIdentityState.TOKEN_CHANGE_SAME_SECURITY_PROVEN
    assert receipt.outcome is NseUdiffPromotionOutcome.PROMOTED_ADDRESSABLE
    assert value.promote().bars_inserted == 2
    bars.close()


def test_token_change_without_current_chronology_remains_unresolved(tmp_path: Path):
    first_day, second_day = date(2024, 7, 8), date(2024, 7, 9)
    value, bars, _ = service(
        tmp_path, artifact(first_day, source_row(first_day, symbol=OLD, token="100")),
        artifact(second_day, source_row(second_day, symbol=OLD, token="200")),
    )
    receipt = value.plan().receipts[0]
    assert receipt.continuity_state is NseUdiffHistoricalIdentityState.HISTORICAL_IDENTITY_UNRESOLVED
    assert receipt.outcome is NseUdiffPromotionOutcome.STILL_BLOCKED
    assert value.promote().bars_inserted == 0
    bars.close()


def test_changed_isin_is_not_heuristically_linked_or_replayed(tmp_path: Path):
    old_day = date(2024, 7, 8)
    first = artifact(old_day, source_row(old_day, symbol=OLD, isin="INE000A01002"))
    value, bars, _ = service(tmp_path, first)
    assert value.plan().receipts == ()
    report = value.promote()
    assert report.source_rows_addressable == report.bars_inserted == 0
    assert bars.raw_count(f"NSE:{ISIN}", Timeframe.DAILY) == 0
    bars.close()


def test_exact_contrary_lifecycle_evidence_fails_closed(tmp_path: Path):
    old_day, current_day = date(2024, 7, 8), date(2024, 7, 10)
    lifecycle = BsePrimaryLifecycleEvidence(
        "20240708-1", "https://example.test/notice", "sha256:" + "a" * 64, T, datetime(2024, 7, 9, tzinfo=UTC),
        BseLifecycleEventType.DELISTING, None, ISIN, None, None, "Fixture",
    )
    value, bars, _ = service(
        tmp_path, artifact(old_day, source_row(old_day, symbol=OLD)), artifact(current_day, source_row(current_day, symbol=CURRENT)), lifecycle=(lifecycle,),
    )
    receipt = value.plan().receipts[0]
    assert receipt.continuity_state is NseUdiffHistoricalIdentityState.LIFECYCLE_BREAK
    assert receipt.outcome is NseUdiffPromotionOutcome.STILL_BLOCKED and receipt.historical_identity_ids == ()
    assert value.promote().source_rows_still_blocked == 1
    assert bars.raw_count(f"NSE:{ISIN}", Timeframe.DAILY) == 0
    bars.close()


def test_all_pairs_are_classified_and_every_source_row_is_accounted(tmp_path: Path):
    first_day, second_day = date(2024, 7, 8), date(2024, 7, 9)
    targets = tuple(target(isin=f"INE{i:03d}A01001", symbol=f"NOW{i:02d}") for i in range(1, 64))
    old = artifact(first_day, *(source_row(first_day, symbol=f"OLD{index:02d}", isin=item.isin, token=str(1000 + index)) for index, item in enumerate(targets, start=1)))
    current = artifact(second_day, *(source_row(second_day, symbol=item.current_symbol, isin=item.isin, token=str(1000 + index)) for index, item in enumerate(targets, start=1)))
    value, bars, _ = service(tmp_path, old, current, targets=targets)
    plan = value.plan()
    assert len(plan.receipts) == 63
    assert all(item.outcome is NseUdiffPromotionOutcome.PROMOTED_ADDRESSABLE for item in plan.receipts)
    assert sum(len(item.source_observation_ids) for item in plan.receipts) == 63
    bars.close()


def test_receipt_tampering_and_current_chronology_absence_fail_closed(tmp_path: Path):
    old_day = date(2024, 7, 8)
    value, bars, _ = service(tmp_path, artifact(old_day, source_row(old_day, symbol=OLD)))
    receipt = value.plan().receipts[0]
    assert receipt.continuity_state is NseUdiffHistoricalIdentityState.HISTORICAL_IDENTITY_UNRESOLVED
    assert receipt.outcome is NseUdiffPromotionOutcome.STILL_BLOCKED
    with pytest.raises(ValueError, match="PROMOTION_RECEIPT_INVALID"):
        replace(receipt, current_symbol="OTHER")
    interval = value.plan().intervals[0]
    with pytest.raises(ValueError, match="IDENTITY_INTERVAL_INVALID"):
        replace(interval, source_symbol="OTHER")
    bars.close()


def test_identity_boundary_has_no_technical_or_execution_dependencies():
    import ast

    source = Path("app/historical/nse_udiff_identity_promotion.py").read_text(encoding="utf-8")
    imports = tuple(
        item.module for item in ast.walk(ast.parse(source))
        if isinstance(item, ast.ImportFrom) and item.module is not None
    )
    forbidden = ("app.signals", "app.portfolio", "app.orders", "app.broker", "app.api", "app.ui")
    assert not any(module == item or module.startswith(item + ".") for module in imports for item in forbidden)
    assert "NSE_UDIFF_TECHNICAL_SERIES_SELECTION_NOT_ACTIVE" in source
