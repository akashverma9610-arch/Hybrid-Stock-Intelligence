"""Read-only current-descriptive technical diagnostic-input readiness audit.

The audit reads persisted canonical Weekly artifacts and their embedded
certified Daily reads.  It does not acquire data, rebuild Weekly bars, call a
provider, write SQLite, execute diagnostics, or create a score/action.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys


_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.market_data.nse_udiff_weekly_technical_bar import SQLITE_WEEKLY_TABLE
from app.storage.core_api_snapshot_repository import snapshot_json_from
from app.universe_analysis.technical_diagnostic_input import (
    assemble_current_descriptive_technical_input, technical_diagnostic_readiness,
    technical_diagnostic_rule_requirements,
)


FIVE_HOLDINGS = {
    "NSE:INE372A01015": "APARINDS",
    "NSE:INE0FHS01024": "DEEPINDS",
    "NSE:INE955D01029": "GENUSPOWER",
    "NSE:INE068V01023": "GLAND",
    "NSE:INE090A01021": "ICICIBANK",
}

_AUDIT_WEEKLY_WINDOW = 6


def audit(*, database: Path) -> dict[str, object]:
    """Return one deterministic readiness audit from immutable stored evidence.

    A current evaluator needs at most six genuine Weekly observations.  The
    audit therefore reads only the latest contiguous suffix for each
    instrument rather than materializing every historic artifact.  This is an
    audit-input selection, not a history rewrite: an interrupted suffix stays
    visibly insufficient instead of being bridged with an older artifact.
    """
    with closing(sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)) as connection:
        total_artifacts = int(connection.execute(
            f"SELECT COUNT(*) FROM {SQLITE_WEEKLY_TABLE}"
        ).fetchone()[0])
        groups: dict[str, list[object]] = {}
        # Use the persisted instrument/week lookup index.  A window function
        # would scan the complete 224k-row payload table before selecting the
        # same six rows per instrument.
        instrument_ids = tuple(row[0] for row in connection.execute(
            f"SELECT DISTINCT canonical_instrument_id FROM {SQLITE_WEEKLY_TABLE} ORDER BY canonical_instrument_id"
        ))
        for instrument_id in instrument_ids:
            rows = connection.execute(
                f"""
                SELECT payload_json FROM {SQLITE_WEEKLY_TABLE}
                WHERE canonical_instrument_id = ?
                ORDER BY week_start DESC, weekly_bar_id DESC
                LIMIT ?
                """,
                (instrument_id, _AUDIT_WEEKLY_WINDOW),
            ).fetchall()
            groups[instrument_id] = [snapshot_json_from(str(row[0])).payload for row in reversed(rows)]
    inputs = {}
    continuity_limited = 0
    for instrument_id, values in groups.items():
        values = _latest_contiguous_suffix(values)
        if len(values) < _AUDIT_WEEKLY_WINDOW:
            continuity_limited += 1
        if not values:
            continue
        cutoff = max(
            [item.daily_read.request.evaluation_as_of for item in values if item.daily_read is not None]
            + [item.known_at for item in values if item.known_at is not None]
        )
        inputs[instrument_id] = assemble_current_descriptive_technical_input(
            canonical_instrument_id=instrument_id, as_of=cutoff,
            daily_reads=tuple(item.daily_read for item in values if item.daily_read is not None),
            weekly_bars=tuple(values),
        )
    rules: dict[str, object] = {}
    for requirement in technical_diagnostic_rule_requirements():
        states = Counter()
        blockers = Counter()
        for value in inputs.values():
            receipt = technical_diagnostic_readiness(value, requirement.rule_id)
            states[receipt.current_descriptive_operational.value] += 1
            blockers.update(item.value for item in receipt.blockers)
        rules[str(requirement.rule_id)] = {
            "evidence_class": requirement.evidence_class.value,
            "minimum_daily_observations": requirement.minimum_daily_observations,
            "minimum_weekly_observations": requirement.minimum_weekly_observations,
            "requires_price_continuity": requirement.requires_price_continuity,
            "requires_volume_continuity": requirement.requires_volume_continuity,
            "requires_benchmark": requirement.requires_benchmark,
            "requires_sector": requirement.requires_sector,
            "requires_peers": requirement.requires_peers,
            "requires_event": requirement.requires_event,
            "securities_evaluated": len(inputs),
            "states": dict(sorted(states.items())),
            "blockers": dict(sorted(blockers.items())),
        }
    five = {}
    for instrument_id, symbol in FIVE_HOLDINGS.items():
        value = inputs.get(instrument_id)
        five[symbol] = {
            "instrument_id": instrument_id,
            "daily_observations": 0 if value is None or value.daily_snapshot is None else len(value.daily_snapshot.observations),
            "weekly_observations": 0 if value is None or value.weekly_snapshot is None else len(value.weekly_snapshot.observations),
            "rules": {} if value is None else {
                str(requirement.rule_id): {
                    "state": technical_diagnostic_readiness(value, requirement.rule_id).current_descriptive_operational.value,
                    "blockers": [item.value for item in technical_diagnostic_readiness(value, requirement.rule_id).blockers],
                }
                for requirement in technical_diagnostic_rule_requirements()
            },
        }
    return {
        "contract": "daily-weekly-existing-technical-diagnostics-operationalization-v1",
        "current_descriptive_only": True,
        "strict_historical_pit": "NOT_READY",
        "strict_historical_pit_reason": "STRICT_HISTORICAL_PIT_SOURCE_AVAILABILITY_UNAVAILABLE",
        "securities_with_certified_daily_and_weekly_input": len(inputs),
        "persisted_weekly_artifacts": total_artifacts,
        "weekly_window_per_instrument": _AUDIT_WEEKLY_WINDOW,
        "continuity_limited_latest_weekly_suffixes": continuity_limited,
        "rules": rules,
        "five_holdings": five,
        "no_execution_or_portfolio_side_effects": True,
    }


def _latest_contiguous_suffix(values: list[object]) -> tuple[object, ...]:
    """Keep the latest sequential Weekly suffix without filling a gap."""
    ordered = sorted(values, key=lambda item: item.request.session_plan.week_start)
    suffix: list[object] = []
    latest_start = None
    for value in reversed(ordered):
        start = value.request.session_plan.week_start
        if latest_start is not None and (latest_start - start).days != 7:
            break
        suffix.append(value)
        latest_start = start
    return tuple(reversed(suffix))


def _encoded(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = audit(database=args.database)
    encoded = _encoded(result)
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        if args.report.exists() and args.report.read_text(encoding="utf-8") != encoded:
            raise ValueError("TECHNICAL_DIAGNOSTIC_READINESS_REPORT_IMMUTABILITY_CONFLICT")
        if not args.report.exists():
            args.report.write_text(encoded, encoding="utf-8")
    print(encoded)
