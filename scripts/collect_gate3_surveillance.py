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
from app.market_data.surveillance_observations import (
    certify_product_capture, completeness_summary, project_poll, summary,
)
from app.historical.nse_mii_security_master import NseMiiCurrentMasterCaptureReceipt
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
            "SELECT payload_json FROM core_api_snapshots WHERE family='HISTORICAL_NSE_SECURITY_MASTER_SNAPSHOT' AND record_type IN ('nse-historical-mii-security-master-snapshot-acquisition','nse-mii-security-master-prospective-snapshot-v2') ORDER BY snapshot_id LIMIT 101"))
        if len(parents) > 100:
            raise ValueError('SURVEILLANCE_MASTER_READ_BOUND')
        eligible = tuple(s for s in parents if s.created_at <= as_of and s.payload.report_date <= as_of.date())
        row_counts = {
            parent.snapshot_id: c.execute(
                "SELECT count(*) FROM core_api_snapshots WHERE family='HISTORICAL_NSE_SECURITY_MASTER_SNAPSHOT' AND record_type IN ('nse-mii-security-master-row-v1','nse-mii-security-master-prospective-row-v2') AND json_extract(payload_json,'$.payload.fields.snapshot_id')=?",
                (parent.snapshot_id,),
            ).fetchone()[0]
            for parent in eligible
        }
        receipts = tuple(snapshot_json_from(row[0]) for row in c.execute(
            "SELECT payload_json FROM core_api_snapshots WHERE family='HISTORICAL_NSE_SECURITY_MASTER_SNAPSHOT' AND record_type='nse-mii-security-master-prospective-capture-receipt-v1' ORDER BY snapshot_id LIMIT 101"))
        if len(receipts) > 100:
            raise ValueError('SURVEILLANCE_MASTER_RECEIPT_READ_BOUND')
        admitted = []
        for candidate in receipts:
            if not isinstance(candidate.payload, NseMiiCurrentMasterCaptureReceipt):
                raise ValueError('SURVEILLANCE_CURRENT_MASTER_RECEIPT_TYPE_INVALID')
            receipt = candidate.payload
            receipt.__post_init__()
            parent = next((item for item in eligible if item.snapshot_id == receipt.snapshot_id), None)
            if (
                candidate.created_at > as_of or receipt.first_observed_at > as_of or parent is None
                or parent.payload.fingerprint != receipt.snapshot_fingerprint
                or parent.payload.report_date != receipt.report_date
                or row_counts[parent.snapshot_id] != receipt.retained_rows
            ):
                continue
            admitted.append(parent)
        # A prospective receipt is the only current-master admission proof.
        complete = tuple(sorted(admitted, key=lambda item: (item.payload.report_date, item.created_at, item.snapshot_id)))
        if not complete:
            complete = tuple(parent for parent in eligible if row_counts[parent.snapshot_id] == parent.payload.row_count)
        latest_complete_date = max((s.payload.report_date for s in complete), default=None)
        latest = tuple(s for s in complete if s.payload.report_date == latest_complete_date)
        # Equal-date independent masters are not resolved by input order.
        if len(latest) > 1:
            raise ValueError('SURVEILLANCE_CURRENT_MASTER_CONFLICT')
        observed_latest_date = max((s.payload.report_date for s in eligible), default=None)
        master_continuity = (
            'CURRENT_COMPLETE_PROSPECTIVE_MASTER_DATE_LEVEL_ONLY'
            if any(parent.payload.contract_version == 'v2-prospective-complete-capture' for parent in latest)
            and latest_complete_date == observed_latest_date and latest_complete_date is not None
            else ('CURRENT_ENOUGH_DATE_LEVEL_MASTER_ONLY'
                  if latest_complete_date == observed_latest_date and latest_complete_date is not None
            else ('PARTIAL_LATEST_MASTER_CAPTURE_INCOMPLETE' if observed_latest_date is not None
                  else 'PARTIAL_NO_MASTER_VISIBLE'))
        )
        rows = []
        if latest:
            raw = c.execute("SELECT payload_json FROM core_api_snapshots WHERE family='HISTORICAL_NSE_SECURITY_MASTER_SNAPSHOT' AND record_type IN ('nse-mii-security-master-row-v1','nse-mii-security-master-prospective-row-v2') AND json_extract(payload_json,'$.payload.fields.snapshot_id')=? ORDER BY snapshot_id LIMIT 50001",
                (latest[0].snapshot_id,)).fetchall()
            if len(raw) > 50000:
                raise ValueError('SURVEILLANCE_MASTER_READ_BOUND')
            rows = [snapshot_json_from(row[0]) for row in raw]
            if len(rows) != latest[0].payload.row_count:
                raise ValueError('SURVEILLANCE_MASTER_CAPTURE_INCOMPLETE')
    return EarningsScheduleCanonicalIdentityBridge(universe), latest + tuple(rows), master_continuity


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
        bridge, masters, master_continuity = read_identity_inputs(args.database, max(p.completed_at for p in polls))
        receipts = tuple(project_poll(store, p.record_id, identity_bridge=bridge, master_snapshots=masters) for p in polls)
        completeness = tuple(certify_product_capture(store, p.record_id, r.record_id) for p, r in zip(polls, receipts, strict=True))
        receipt_ids = tuple(r.record_id for r in receipts)
        fingerprints = tuple(r.fingerprint for r in receipts)
        completeness_ids = tuple(r.record_id for r in completeness)
        completeness_fingerprints = tuple(r.fingerprint for r in completeness)
        raw_originals = tuple((p.raw.record_id, p.raw.first_observed_at) for p in polls if p.raw)
    finally:
        repository.close()
    # Mandatory disk reopen, no source refetch and no second universe scan.
    repository = SQLiteCoreApiSnapshotRepository(args.database)
    try:
        store = SurveillanceEvidenceStore(repository)
        if tuple(store.get(key).fingerprint for key in receipt_ids) != fingerprints:
            raise ValueError('SURVEILLANCE_RECEIPT_REOPEN_MISMATCH')
        if tuple(store.get(key).fingerprint for key in completeness_ids) != completeness_fingerprints:
            raise ValueError('SURVEILLANCE_COMPLETENESS_REOPEN_MISMATCH')
        if not all(store.get(key).first_observed_at == at for key, at in raw_originals):
            raise ValueError('SURVEILLANCE_FIRST_OBSERVATION_REOPEN_MISMATCH')
    finally:
        repository.close()
    capture_ready = all(item.collector_capture_state.value == 'COMPLETE' for item in completeness)
    body = dict(collector='nse-surveillance-prospective/v1', polls=[p.record_id for p in polls],
        network_requests=0 if args.replay_poll else 3, receipts=[summary(r) for r in receipts],
        completeness_receipts=[completeness_summary(r) for r in completeness],
        retained_universe_snapshots=len(bridge.snapshots), master_rows=len(masters)-1 if masters else 0,
        master_report_date=masters[0].payload.report_date.isoformat() if masters else None,
        master_current_continuity=master_continuity,
        restart_first_observed_verified=True, receipt_reopen_verified=True,
        gate_policy_v2_active=False, source_evidence_only=True,
        readiness=('GATE3_OFFICIAL_SOURCE_RUNTIME_BLOCKED' if any(p.http_status != 200 or p.raw is None for p in polls)
            else ('READY_FOR_EVIDENCE_ADAPTER' if capture_ready
                  else 'GATE3_SOURCE_CAPTURE_COMPLETENESS_NOT_PROVABLE_FROM_CURRENT_OFFICIAL_PATH')))
    print(json.dumps(body | {'fingerprint':content_fingerprint(body)}, sort_keys=True, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
