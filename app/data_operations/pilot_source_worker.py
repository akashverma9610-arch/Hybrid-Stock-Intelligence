"""Explicit bounded current-EOD worker; no timer, API or daemon activation.

Uses the existing operations receipts/health and an additive single-host lease.
Legacy CLI is frozen and does not take this lease: do not run it concurrently.
The API remains a read-only health consumer, not a competing acquirer.
"""
from __future__ import annotations

import argparse
from datetime import UTC, datetime
from contextlib import ExitStack
from pathlib import Path

from app.data_operations.current_nse_eod import CurrentNseEodRefreshJob
from app.data_operations.local_source_lease import local_source_lease
from app.data_operations.models import EvidenceDataFamily, EvidenceRefreshStatus
from app.data_operations.service import DataOperationsService, RetryPolicy
from app.data_operations.store import DataOperationsStore
from app.historical.nse_capital_market_session_evidence_2022_2026 import nse_capital_market_calendar_2022_2026
from app.market_data.historical import SQLiteHistoricalBarStore
from app.market_data.nse_udiff_daily_history import NseOfficialUdiffDailySource, NseUdiffDailyHistoryStore, NseUdiffDailyTarget
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository
from app.universe_analysis.service import CoreUniverseAnalysisStore


def compose_current_eod_service(*, repository, bars, source, clock=lambda: datetime.now(UTC)):
    """One injected shared-universe job definition, reusable by host dispatchers."""
    universe = CoreUniverseAnalysisStore(repository)
    snapshot = universe.latest_universe_snapshot()
    if snapshot is None:
        raise ValueError("CURRENT_EOD_UNIVERSE_REQUIRED")
    identities = {}
    for item in universe.instruments_as_of(snapshot.as_of):
        if item.instrument_id in snapshot.instrument_ids:
            previous = identities.get(item.instrument_id)
            if previous is not None and (previous.isin, previous.symbol) != (item.isin, item.symbol):
                raise ValueError("CURRENT_EOD_UNIVERSE_IDENTITY_CONFLICT")
            identities[item.instrument_id] = item
    if set(snapshot.instrument_ids) != set(identities):
        raise ValueError("CURRENT_EOD_UNIVERSE_IDENTITY_MISSING")
    targets = tuple(NseUdiffDailyTarget.from_instrument(identities[key]) for key in sorted(identities))
    job = CurrentNseEodRefreshJob(source=source, evidence=NseUdiffDailyHistoryStore(repository),
        bars=bars, targets=targets, calendar=nse_capital_market_calendar_2022_2026(),
        universe_reference=snapshot.snapshot_id, universe_as_of=snapshot.as_of)
    return DataOperationsService(DataOperationsStore(repository), {EvidenceDataFamily.OHLCV: job},
                                 retry_policy=RetryPolicy(maximum_attempts=2), clock=clock)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--once", required=True, action="store_true")
    args = parser.parse_args(argv)
    # Lock before constructing any store. Operators must protect a backup before
    # the first material write; this command neither invents one nor deletes it.
    with local_source_lease(args.database), ExitStack() as resources:
        repository = SQLiteCoreApiSnapshotRepository(args.database)
        resources.callback(repository.close)
        bars = SQLiteHistoricalBarStore(args.database)
        resources.callback(bars.close)
        service = compose_current_eod_service(repository=repository, bars=bars, source=NseOfficialUdiffDailySource())
        result = service.run(EvidenceDataFamily.OHLCV)
        print(f"family=OHLCV run_id={result.run_id} status={result.status.value} "
              f"accepted={result.accepted_count} duplicates={result.duplicate_count} "
              f"gaps={result.gap_count} conflicts={result.conflict_count}")
        return 0 if result.status in {EvidenceRefreshStatus.COMPLETE, EvidenceRefreshStatus.NO_CHANGE} else 2


if __name__ == "__main__":
    raise SystemExit(main())
