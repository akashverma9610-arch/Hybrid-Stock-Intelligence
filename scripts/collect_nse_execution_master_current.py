"""One bounded current NSE execution-master capture or network-free reopen.

The direct MII file is source evidence only.  This command neither evaluates a
Gate nor invokes a broker, portfolio, order, API, or UI surface.
"""
from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sqlite3
import sys
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.historical.canonical_market_session_event_time import TradingDayState
from app.historical.nse_capital_market_session_evidence_2022_2026 import nse_capital_market_calendar_2022_2026
from app.historical.nse_mii_security_master import (
    PROSPECTIVE_CAPTURE_CONTRACT_VERSION,
    NseMiiCurrentMasterCaptureReceipt,
    NseMiiSecurityMasterEvidenceStore,
    NseOfficialMiiSecurityMasterTransport,
    extract_nse_mii_security_master,
)
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository


_IST = ZoneInfo("Asia/Kolkata")


def latest_completed_nse_session(as_of: datetime):
    """Use the existing source-backed calendar; never substitute calendar days."""
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("NSE_CURRENT_MASTER_AS_OF_TIMEZONE_REQUIRED")
    calendar = nse_capital_market_calendar_2022_2026()
    local_day = as_of.astimezone(_IST).date()
    day = calendar.resolve_trading_day(local_day, as_of=as_of)
    if day.state in {TradingDayState.REGULAR_TRADING_DAY, TradingDayState.SPECIAL_TRADING_DAY, TradingDayState.MUHURAT_TRADING}:
        phases = calendar.phases_for(local_day, as_of=as_of)
        close = next((item.ends_at for item in phases if item.phase_type.value == "REGULAR_CONTINUOUS"), None)
        if close is not None and as_of >= close:
            return local_day
    return calendar.adjacent_trading_session(local_day, as_of=as_of, direction=-1)


def _integrity(database: Path) -> tuple[str, int]:
    connection = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        connection.execute("PRAGMA query_only=ON")
        return connection.execute("PRAGMA integrity_check").fetchone()[0], len(connection.execute("PRAGMA foreign_key_check").fetchall())
    finally:
        connection.close()


def _summary(receipt: NseMiiCurrentMasterCaptureReceipt, *, replay: bool, integrity: str, fk_violations: int) -> dict[str, object]:
    return {
        "collector": "nse-execution-master-current-capture/v1",
        "network_requests": 0 if replay else 1,
        "receipt_id": receipt.receipt_id,
        "report_date": receipt.report_date.isoformat(),
        "source_reference": receipt.source_reference,
        "source_declared_rows": receipt.source_declared_rows,
        "raw_captured_rows": receipt.raw_captured_rows,
        "parsed_rows": receipt.parsed_rows,
        "retained_rows": receipt.retained_rows,
        "canonical_eligible_rows": receipt.canonical_eligible_rows,
        "structural_rejected_rows": receipt.structural_rejected_rows,
        "identity_ineligible_rows": receipt.identity_ineligible_rows,
        "bytes_received": receipt.bytes_received,
        "declared_length": receipt.declared_length,
        "transfer_complete": receipt.transfer_complete,
        "pagination_state": receipt.pagination_state,
        "completeness": receipt.completeness.value,
        "first_observed_at": receipt.first_observed_at.isoformat(),
        "source_fingerprint": receipt.raw_file_fingerprint,
        "extraction_fingerprint": receipt.extraction_fingerprint,
        "receipt_fingerprint": receipt.fingerprint,
        "sqlite_integrity": integrity,
        "foreign_key_violations": fk_violations,
        "gate_policy_v2_active": False,
        "source_evidence_only": True,
        "execution_status": "NON_EXECUTABLE",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--replay-capture", metavar="RECEIPT_ID", help="Reopen one saved complete capture; no network request")
    args = parser.parse_args()
    if not args.database.is_file():
        parser.error("Existing canonical database required; no new database is created")
    repository = SQLiteCoreApiSnapshotRepository(args.database)
    store = NseMiiSecurityMasterEvidenceStore(repository)
    try:
        if args.replay_capture:
            receipt = store.reopen_complete_current_capture(args.replay_capture)
            replay = True
        else:
            target = latest_completed_nse_session(datetime.now(UTC))
            if target is None:
                raise ValueError("NSE_CURRENT_MASTER_COMPLETED_SESSION_UNPROVEN")
            response = NseOfficialMiiSecurityMasterTransport().fetch(target)
            extraction = extract_nse_mii_security_master(
                response, contract_version=PROSPECTIVE_CAPTURE_CONTRACT_VERSION,
            )
            receipt = store.save_complete_current_capture(extraction)
            replay = False
    finally:
        repository.close()
    integrity, fk_violations = _integrity(args.database)
    print(json.dumps(_summary(receipt, replay=replay, integrity=integrity, fk_violations=fk_violations), sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
