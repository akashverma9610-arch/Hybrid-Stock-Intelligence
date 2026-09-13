"""One bounded official poll or network-free replay; source evidence only.

Requires the existing canonical database. Never schedules itself, fetches a
master, loads prices, evaluates gates or changes policy activation.
"""
from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.filings.earnings_schedule_identity import EarningsScheduleCanonicalIdentityBridge
from app.fundamentals.diagnostic_comparability import content_fingerprint
from app.market_data.surveillance_prospective import (
    OfficialSurveillanceTransport, ProspectiveSurveillanceCollector,
    SurveillanceEvidenceStore, SurveillanceFamily, SurveillancePollReceipt,
)
from app.market_data.surveillance_observations import project_poll, summary
from app.storage.core_api_snapshot_repository import snapshot_json_from
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository


def read_identity_inputs(database: Path, as_of: datetime):
    """One bounded read of retained canonical NSE scope and latest dated master.

    The existing identity bridge owns exact security resolution. Master rows
    remain date-point evidence; their date is never relabelled as current.
    """
    with closing(sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True)) as c:
        c.execute('PRAGMA query_only=ON')
        c.execute('BEGIN')
        raw = c.execute("SELECT payload_json FROM core_api_snapshots WHERE family='NSE_UNIVERSE' ORDER BY snapshot_id LIMIT 20001").fetchall()
        if len(raw) > 20000:
            raise ValueError('SURVEILLANCE_IDENTITY_READ_BOUND')
        universe = tuple(snapshot_json_from(row[0]) for row in raw)
        parents = tuple(snapshot_json_from(row[0]) for row in c.execute(
            "SELECT payload_json FROM core_api_snapshots WHERE family='HISTORICAL_NSE_SECURITY_MASTER_SNAPSHOT' AND record_type='nse-historical-mii-security-master-snapshot-acquisition' ORDER BY snapshot_id LIMIT 101"))
        if len(parents) > 100:
            raise ValueError('SURVEILLANCE_MASTER_READ_BOUND')
        eligible = tuple(s for s in parents if s.created_at <= as_of and s.payload.report_date <= as_of.date())
        latest_date = max((s.payload.report_date for s in eligible), default=None)
        latest = tuple(s for s in eligible if s.payload.report_date == latest_date)
        # Equal-date independent masters are not resolved by input order.
        if len(latest) > 1:
            raise ValueError('SURVEILLANCE_CURRENT_MASTER_CONFLICT')
        rows = []
        if latest:
            raw = c.execute("SELECT payload_json FROM core_api_snapshots WHERE family='HISTORICAL_NSE_SECURITY_MASTER_SNAPSHOT' AND record_type='nse-mii-security-master-row-v1' AND json_extract(payload_json,'$.payload.fields.snapshot_id')=? ORDER BY snapshot_id LIMIT 50001",
                (latest[0].snapshot_id,)).fetchall()
            if len(raw) > 50000:
                raise ValueError('SURVEILLANCE_MASTER_READ_BOUND')
            rows = [snapshot_json_from(row[0]) for row in raw]
            if len(rows) != latest[0].payload.row_count:
                raise ValueError('SURVEILLANCE_MASTER_CAPTURE_INCOMPLETE')
    return EarningsScheduleCanonicalIdentityBridge(universe), latest + tuple(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--replay-poll', nargs=3, metavar=('ASM_ID', 'GSM_ID', 'PRICE_BAND_ID'),
        help='Reuse the three existing immutable poll IDs; no network request')
    args = parser.parse_args()
    if not args.database.is_file():
        parser.error('Existing canonical database required; no new database is created')
    repository = SQLiteCoreApiSnapshotRepository(args.database)
    store = SurveillanceEvidenceStore(repository)
    try:
        polls = (tuple(store.get(key) for key in args.replay_poll) if args.replay_poll else
            ProspectiveSurveillanceCollector(store, OfficialSurveillanceTransport()).collect_once())
        if (len(polls) != 3 or any(not isinstance(p, SurveillancePollReceipt) for p in polls)
                or tuple(p.family for p in polls) != tuple(SurveillanceFamily)):
            raise ValueError('SURVEILLANCE_EXACT_THREE_POLLS_REQUIRED')
        bridge, masters = read_identity_inputs(args.database, max(p.completed_at for p in polls))
        receipts = tuple(project_poll(store, p.record_id, identity_bridge=bridge, master_snapshots=masters) for p in polls)
        receipt_ids = tuple(r.record_id for r in receipts)
        fingerprints = tuple(r.fingerprint for r in receipts)
        raw_originals = tuple((p.raw.record_id, p.raw.first_observed_at) for p in polls if p.raw)
    finally:
        repository.close()
    # Mandatory disk reopen, no source refetch and no second universe scan.
    repository = SQLiteCoreApiSnapshotRepository(args.database)
    try:
        store = SurveillanceEvidenceStore(repository)
        if tuple(store.get(key).fingerprint for key in receipt_ids) != fingerprints:
            raise ValueError('SURVEILLANCE_RECEIPT_REOPEN_MISMATCH')
        if not all(store.get(key).first_observed_at == at for key, at in raw_originals):
            raise ValueError('SURVEILLANCE_FIRST_OBSERVATION_REOPEN_MISMATCH')
    finally:
        repository.close()
    body = dict(collector='nse-surveillance-prospective/v1', polls=[p.record_id for p in polls],
        network_requests=0 if args.replay_poll else 3, receipts=[summary(r) for r in receipts],
        retained_universe_snapshots=len(bridge.snapshots), master_rows=len(masters)-1 if masters else 0,
        master_report_date=masters[0].payload.report_date.isoformat() if masters else None,
        restart_first_observed_verified=True, receipt_reopen_verified=True,
        gate_policy_v2_active=False, source_evidence_only=True,
        readiness=('GATE3_OFFICIAL_SOURCE_RUNTIME_BLOCKED' if any(p.http_status != 200 or p.raw is None for p in polls)
            else 'GATE3_SOURCE_CAPTURE_COMPLETENESS_BLOCKED'))
    print(json.dumps(body | {'fingerprint':content_fingerprint(body)}, sort_keys=True, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
