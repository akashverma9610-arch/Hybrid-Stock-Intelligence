from dataclasses import replace
import subprocess
import sys

import pytest

from app.data_operations.local_source_lease import local_source_lease
from app.data_operations.models import EvidenceDataFamily
from app.data_operations.pilot_source_worker import compose_current_eod_service, main
from app.data_operations.service import DataOperationsService
from app.data_operations.store import DataOperationsStore
from app.market_data.nse_udiff_daily_history import NseUdiffDailyFetchResult, NseUdiffDailyStatus, nse_udiff_daily_url
from app.universe_analysis.service import CoreUniverseAnalysisStore
from app.universe_analysis.models import NseEquityInstrument
from test_current_nse_eod import T, D, job
from test_nse_udiff_daily_history import snapshot


def test_os_lease_excludes_other_process_and_releases_on_exit(tmp_path):
    db = tmp_path / "test.db"
    db.touch()
    code = "from app.data_operations.local_source_lease import local_source_lease\nimport sys\ntry:\n with local_source_lease(sys.argv[1]): print('ACQUIRED')\nexcept RuntimeError: print('BUSY')\n"
    with local_source_lease(db):
        child = subprocess.run([sys.executable, "-", str(db)], input=code, text=True, capture_output=True, timeout=20)
        assert child.returncode == 0 and child.stdout.strip() == "BUSY"
    child = subprocess.run([sys.executable, "-", str(db)], input=code, text=True, capture_output=True, timeout=20)
    assert child.returncode == 0 and child.stdout.strip() == "ACQUIRED"
    assert db.with_name(db.name + ".source-worker.lock").exists()


def test_lease_failure_starts_no_job(tmp_path):
    value, source, bars, repo = job(tmp_path)
    db = tmp_path / "receipts.db"
    with local_source_lease(db), pytest.raises(RuntimeError, match="ALREADY_ACTIVE"):
        main(["--database", str(db), "--once"])
    assert source.calls == 0 and DataOperationsStore(repo).runs() == ()


def test_retry_updates_health_and_replay_does_not_duplicate_bars(tmp_path):
    value, source, bars, repo = job(tmp_path)
    result = source.result
    class FlakySource:
        calls = 0
        def fetch(self, trade_date):
            self.calls += 1
            if self.calls == 1:
                return NseUdiffDailyFetchResult(NseUdiffDailyStatus.SOURCE_TRANSPORT_FAILURE, D, nse_udiff_daily_url(D), T, None, "TIMEOUT")
            return result
    flaky = FlakySource()
    value._source = flaky
    service = DataOperationsService(DataOperationsStore(repo), {EvidenceDataFamily.OHLCV:value}, clock=lambda:T)
    first = service.run(EvidenceDataFamily.OHLCV)
    second = service.run(EvidenceDataFamily.OHLCV)
    assert first.retry_count == 1 and first.accepted_count == 1
    assert second.duplicate_count == 1 and flaky.calls == 2
    assert service.health(now=T).families[0].last_run in (first, second)
    assert len(DataOperationsStore(repo).runs()) == 2


def test_composition_uses_exact_shared_universe_and_only_current_eod(tmp_path):
    value, source, bars, repo = job(tmp_path)
    universe = CoreUniverseAnalysisStore(repo)
    universe.save_instrument(NseEquityInstrument("NSE:INE000A01001", "ALPHA", "INE000A01001", None, None,
        "LISTED", None, True, T, "NSE"))
    universe.save_universe_snapshot(replace(snapshot(), as_of=T))
    one = compose_current_eod_service(repository=repo, bars=bars, source=source, clock=lambda:T)
    two = compose_current_eod_service(repository=repo, bars=bars, source=source, clock=lambda:T)
    assert one.registered_families == (EvidenceDataFamily.OHLCV,)
    assert one._jobs[EvidenceDataFamily.OHLCV].acquisition_id == two._jobs[EvidenceDataFamily.OHLCV].acquisition_id
    assert one.run(EvidenceDataFamily.OHLCV).accepted_count == 1
    assert two.run(EvidenceDataFamily.OHLCV).duplicate_count == 1
