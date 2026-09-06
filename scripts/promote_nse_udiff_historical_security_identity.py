"""Run the explicit local UDiFF historical-security identity promotion.

This operation consumes retained local exchange artifacts only.  It neither
fetches a provider nor activates technical reads, indicators, portfolio
changes, broker calls, or orders.
"""
from __future__ import annotations

import json
from collections import Counter

from app.historical.nse_udiff_identity_promotion import build_local_nse_udiff_historical_identity_promotion


def main() -> None:
    service, resources = build_local_nse_udiff_historical_identity_promotion()
    try:
        report = service.promote()
    finally:
        resources[0].close()
    plan = report.plan
    payload = {
        "contract": "NSE_UDIFF_HISTORICAL_SECURITY_IDENTITY_CONTINUITY_PROMOTION_V1",
        "intervals": len(plan.intervals),
        "historical_security_identities": len(plan.identities),
        "pairing_receipts": len(plan.receipts),
        "pairing_states": dict(sorted(Counter(item.continuity_state.value for item in plan.receipts).items())),
        "pairing_outcomes": dict(sorted(Counter(item.outcome.value for item in plan.receipts).items())),
        "intervals_inserted": report.intervals_inserted,
        "intervals_already_present": report.intervals_already_present,
        "identities_inserted": report.identities_inserted,
        "identities_already_present": report.identities_already_present,
        "receipts_inserted": report.receipts_inserted,
        "receipts_already_present": report.receipts_already_present,
        "source_rows_addressable": report.source_rows_addressable,
        "source_rows_still_blocked": report.source_rows_still_blocked,
        "bars_inserted": report.bars_inserted,
        "bars_already_present": report.bars_already_present,
        "bar_conflicts": report.bar_conflicts,
        "invalid_source_rows": report.invalid_source_rows,
        "replay_errors": report.replay_errors,
        "technical_selection": "NOT_ACTIVE",
    }
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
