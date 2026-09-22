"""Current-acquisition tests use isolated stores, not production evidence."""
from datetime import UTC, date, datetime, timedelta
from dataclasses import replace

import pytest

from app.data_operations.current_nse_eod import CurrentNseEodRefreshJob, latest_completed_session
from app.data_operations.models import EvidenceDataFamily, EvidenceRefreshMode, EvidenceRefreshRequest, EvidenceRefreshStatus
from app.historical.nse_capital_market_session_evidence_2022_2026 import nse_capital_market_calendar_2022_2026
from app.market_data.nse_udiff_daily_history import NSE_UDIFF_END, NseUdiffDailyHistoryStore, NseUdiffDailyFetchResult, NseUdiffDailyStatus, nse_udiff_daily_url
from app.market_data.historical import SQLiteHistoricalBarStore
from app.market_data.models import Timeframe
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository
from test_nse_udiff_daily_history import Source, archive, row, target

T = datetime(2026, 9, 22, 16, tzinfo=UTC)
D = date(2026, 9, 22)


def request(at=T):
    return EvidenceRefreshRequest("current-test", EvidenceDataFamily.OHLCV, EvidenceRefreshMode.INCREMENTAL, at, at, None, 2)


def current_row(**kwargs):
    return {**row(**kwargs), "TradDt": str(D), "BizDt": str(D)}


def job(tmp_path, rows=None, *, observed=T, targets=None):
    source = Source(NseUdiffDailyFetchResult(NseUdiffDailyStatus.ARTIFACT_VALID, D, nse_udiff_daily_url(D), observed,
        archive(tuple(rows or [current_row()]), filename="BhavCopy_NSE_CM_0_0_0_20260922_F_0000.csv")))
    repo = SQLiteCoreApiSnapshotRepository(tmp_path / "receipts.db")
    bars = SQLiteHistoricalBarStore(tmp_path / "bars.db")
    value = CurrentNseEodRefreshJob(source=source, evidence=NseUdiffDailyHistoryStore(repo), bars=bars,
        targets=targets or (target(),), calendar=nse_capital_market_calendar_2022_2026(),
        universe_reference="fixture-universe", universe_as_of=T - timedelta(days=1))
    return value, source, bars, repo


def test_canonical_completed_session_and_in_progress_previous_session():
    calendar = nse_capital_market_calendar_2022_2026()
    assert latest_completed_session(calendar, as_of=T) == (D, datetime(2026, 9, 22, 10, tzinfo=UTC))
    assert latest_completed_session(calendar, as_of=T.replace(hour=8))[0] == date(2026, 9, 21)
    assert latest_completed_session(calendar, as_of=T.replace(day=20))[0] == date(2026, 9, 18)
    assert latest_completed_session(calendar, as_of=T.replace(day=14))[0] == date(2026, 9, 11)


def test_no_calendar_fallback_or_naive_timestamp():
    calendar = nse_capital_market_calendar_2022_2026()
    with pytest.raises(ValueError, match="AWARE"):
        latest_completed_session(calendar, as_of=T.replace(tzinfo=None))
    with pytest.raises(ValueError, match="CALENDAR_UNRESOLVED"):
        latest_completed_session(calendar, as_of=T.replace(month=8))


def test_preserves_source_timestamp_and_first_receipt_replay(tmp_path):
    value, source, bars, repo = job(tmp_path)
    first = value.refresh(request())
    second = value.refresh(request(T + timedelta(hours=1)))
    assert first.status is EvidenceRefreshStatus.COMPLETE and first.accepted_count == 1
    assert second.status is EvidenceRefreshStatus.NO_CHANGE and second.duplicate_count == 1
    assert source.calls == 1 and first.source_fingerprint == second.source_fingerprint
    stored = bars.raw_range(target().canonical_instrument_id, Timeframe.DAILY, T - timedelta(days=2), T + timedelta(days=1))[0]
    assert stored.provenance.received_at == T and stored.provenance.provider_timestamp is None
    assert stored.provenance.exchange_timestamp == datetime(2026, 9, 21, 18, 30, tzinfo=UTC)
    assert first.accepted_through == datetime(2026, 9, 22, 10, tzinfo=UTC)
    assert NSE_UDIFF_END == date(2026, 8, 31)
    assert value.acquisition_id.startswith("nse-udiff-acquisition:current:")


@pytest.mark.parametrize("rows", [[current_row(symbol="RENAMED")], [current_row(), current_row()], [current_row(high="90")]])
def test_identity_ambiguity_and_bad_rows_fail_closed(tmp_path, rows):
    value, _, bars, _ = job(tmp_path, rows)
    result = value.refresh(request())
    assert result.status is EvidenceRefreshStatus.PARTIAL
    assert result.accepted_count == 0 and result.gap_count > 0
    assert bars.raw_count(target().canonical_instrument_id, Timeframe.DAILY) == 0


def test_missing_target_prevents_complete_coverage(tmp_path):
    value, _, _, _ = job(tmp_path, targets=(target(), target("BETA", "INE000B01002")))
    result = value.refresh(request())
    assert result.status is EvidenceRefreshStatus.PARTIAL and result.accepted_count == 1
    assert any(x[2] == "CURRENT_EOD_TARGET_MISSING" for x in result.findings)


def test_receipt_before_close_rejected_without_ingestion(tmp_path):
    value, _, bars, _ = job(tmp_path, observed=T.replace(hour=8))
    assert value.refresh(request()).error_summary == "CURRENT_EOD_SOURCE_SESSION_OR_RECEIPT_INVALID"
    assert bars.raw_count(target().canonical_instrument_id, Timeframe.DAILY) == 0


def test_future_universe_not_used(tmp_path):
    value, source, _, _ = job(tmp_path)
    assert value.refresh(request(T - timedelta(days=2))).error_summary == "CURRENT_EOD_UNIVERSE_NOT_PIT_VISIBLE"
    assert source.calls == 0


def test_shared_scope_order_independent_and_duplicate_targets_rejected(tmp_path):
    a, _, _, _ = job(tmp_path, targets=(target(), target("BETA", "INE000B01002")))
    b, _, _, _ = job(tmp_path, targets=(target("BETA", "INE000B01002"), target()))
    assert a.acquisition_id == b.acquisition_id
    with pytest.raises(ValueError, match="AMBIGUOUS"):
        job(tmp_path, targets=(target(), target()))
