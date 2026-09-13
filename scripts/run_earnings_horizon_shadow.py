"""Bounded, network-free admission/lifecycle run from stored collector receipts.

Market enrichment uses run_shadow_once's typed canonical-input interface. This
operator command never fabricates a calendar, source timing or result relation.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.filings.earnings_horizon_shadow_runner import run_shadow_once
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--as-of", type=datetime.fromisoformat, required=True, help="Explicit timezone-aware cutoff; never source known-at")
    parser.add_argument("--max-receipts", type=int, default=1000)
    args = parser.parse_args()
    if not args.database.is_file():
        parser.error("Existing canonical database required; no new database is created")
    repository = SQLiteCoreApiSnapshotRepository(args.database)
    try:
        value = run_shadow_once(repository, as_of=args.as_of, max_receipts=args.max_receipts)
        print(json.dumps({
            "run_id": value.record_id, "fingerprint": value.fingerprint,
            "collector_receipts_inspected": len(value.collector_receipts), "qualified_events": value.qualified_count,
            "logical_events_admitted": value.admitted_count, "conflicted": value.conflicted_count,
            "cancelled": value.cancelled_count, "open_events": value.admitted_count,
            "session_observations": len(value.sessions), "result_links": value.linked_count,
            "outcomes_ready": value.outcomes_ready, "source_partial": value.source_partial,
            "source_failed": value.source_failed, "bse_unsupported_shape": value.bse_unsupported_shape,
            "status": value.status, "live_shadow_event": value.live_event_proof,
            "live_outcome": value.live_outcome_proof, "reasons": value.reasons,
            "horizon_state": value.horizon_state, "gate_policy_v2_active": value.gate_policy_v2_active,
        }, sort_keys=True))
    finally:
        repository.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
