"""Materialise current-descriptive Weekly bars from certified UDiFF Daily reads.

This is an explicit, bounded local-data operation.  It performs no network
access and writes only additive ``nse_udiff_weekly_technical_bar*`` tables in
the supplied existing SQLite database plus one optional JSON receipt.  Raw
Daily UDiFF observations are used only to compose the evidence passed into the
existing certified-Daily reader; the Weekly contract itself never reads them.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import closing
from datetime import UTC, date, timedelta
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import sys
from typing import Iterable


# Keep this explicit operational script runnable from its repository path.
_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))

from app.historical.nse_capital_market_session_evidence_2022_2026 import nse_capital_market_calendar_2022_2026
from app.historical.nse_udiff_effective_identity_coverage import (
    NseUdiffEffectiveIdentityCoverageIndex,
    compose_action_window_coverage,
)
from app.market_data.historical import _bar_from_mapping, _conflict_artifact_from_payload
from app.market_data.nse_udiff_archive_verification import UdiffArchiveVerifier
from app.market_data.nse_udiff_conflict_resolution import reconcile_udiff_conflict
from app.market_data.nse_udiff_conflict_semantics import NseUdiffSourceRowEvidence
from app.market_data.nse_udiff_daily_integrity import audit_udiff_same_provider_conflicts
from app.market_data.nse_udiff_daily_technical_eligibility import (
    DailyTechnicalRequirement,
    DailyTechnicalRequirementProfile,
)
from app.market_data.nse_udiff_daily_technical_read import (
    NseUdiffDailyTechnicalReadEvidence,
    NseUdiffDailyTechnicalReadRequest,
    NseUdiffDailyTechnicalUseMode,
    read_certified_daily_technical_bars,
)
from app.market_data.nse_udiff_weekly_technical_bar import (
    NseUdiffWeeklyTechnicalDerivationRequest,
    NseUdiffWeeklyTechnicalState,
    NseUdiffWeeklyTechnicalBarWriteOutcome,
    SQLiteNseUdiffWeeklyTechnicalBarStore,
    build_nse_udiff_weekly_session_plan,
    derive_nse_udiff_weekly_technical_bar,
)
from app.storage.core_api_snapshot_repository import snapshot_json_from


SOURCE_ERA_START = date(2024, 7, 8)
FIVE_HOLDINGS = {
    "NSE:INE372A01015": "APARINDS",
    "NSE:INE0FHS01024": "DEEPINDS",
    "NSE:INE955D01029": "GENUSPOWER",
    "NSE:INE068V01023": "GLAND",
    "NSE:INE090A01021": "ICICIBANK",
}


def _encoded(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _snapshots(connection: sqlite3.Connection, family: str) -> tuple[object, ...]:
    return tuple(
        snapshot_json_from(row[0]).payload
        for row in connection.execute(
            "SELECT payload_json FROM core_api_snapshots WHERE family=? ORDER BY snapshot_id", (family,)
        )
    )


def _udiff_bars(connection: sqlite3.Connection, start: date, end: date) -> dict[str, tuple[object, ...]]:
    groups: dict[str, list[object]] = defaultdict(list)
    rows = connection.execute(
        "SELECT * FROM historical_bars WHERE provider_identity='nse_udiff_official' "
        "AND timeframe='1D' AND date(start_time,'+330 minutes') BETWEEN ? AND ? "
        "ORDER BY instrument_id,start_time,bar_id",
        (start.isoformat(), end.isoformat()),
    )
    for row in rows:
        bar = _bar_from_mapping(row)
        groups[bar.instrument.instrument_id].append(bar)
    return {key: tuple(value) for key, value in groups.items()}


def _udiff_bars_for_week(database: Path, start: date) -> dict[str, tuple[object, ...]]:
    """Read one bounded exchange week without retaining the source era."""
    with closing(sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        return _udiff_bars(connection, start, date.fromordinal(start.toordinal() + 6))


def _reconciled_conflicts(
    connection: sqlite3.Connection, *, accepted_audit: Path, repair_receipt: Path,
) -> tuple[object, ...]:
    """Rebuild the accepted structural-resolution proofs from immutable input."""
    audit = json.loads(accepted_audit.read_text(encoding="utf-8"))
    prior = {item["conflict_fingerprint"]: item for item in json.loads(repair_receipt.read_text(encoding="utf-8"))}
    if len(prior) != 784 or audit.get("classification_counts") != {"DISTINCT_SERIES": 784}:
        raise ValueError("WEEKLY_UDIFF_ACCEPTED_CONFLICT_BASELINE_INVALID")
    artifacts = tuple(_conflict_artifact_from_payload(row[0]) for row in connection.execute(
        "SELECT payload_json FROM historical_bar_conflicts ORDER BY conflict_fingerprint"
    ))
    udiff = {
        item.conflict_fingerprint: item for item in artifacts
        if item.stored_lineage.provider_identity == "nse_udiff_official"
        and item.incoming_lineage.provider_identity == "nse_udiff_official"
    }

    def source(identifier: str):
        row = connection.execute("SELECT payload_json FROM core_api_snapshots WHERE snapshot_id=?", (identifier,)).fetchone()
        if row is None:
            raise ValueError("WEEKLY_UDIFF_CONFLICT_SOURCE_ARCHIVE_MISSING")
        return snapshot_json_from(row[0]).payload

    verifier = UdiffArchiveVerifier(source)
    proofs = []
    for item in audit["conflicts"]:
        artifact = udiff.get(item["conflict_fingerprint"])
        if artifact is None:
            raise ValueError("WEEKLY_UDIFF_CONFLICT_ARTIFACT_MISSING")
        evidence = []
        for side in ("stored", "incoming"):
            raw = item[side]
            archive, parsed = verifier._parsed(raw["artifact_id"])
            row_index = raw["row_index"]
            source_row = NseUdiffSourceRowEvidence(
                archive.artifact_id, archive.fingerprint, archive.content_sha256, archive.source_url,
                archive.observed_at, row_index, tuple(tuple(pair) for pair in raw["fields"]), raw["fingerprint"],
            )
            if dict(source_row.fields) != parsed.rows[row_index]:
                raise ValueError("WEEKLY_UDIFF_CONFLICT_ARCHIVE_ROW_TAMPERED")
            evidence.append(source_row)
        retained = tuple(
            _bar_from_mapping(row) for row in connection.execute(
                "SELECT * FROM historical_bars WHERE instrument_id=? AND provider_identity='nse_udiff_official' "
                "AND date(start_time,'+330 minutes')=? ORDER BY start_time,bar_id",
                (artifact.canonical_instrument_id, item["trade_date"]),
            )
        )
        source_ids = {item.source_row_id for item in evidence}
        retained = tuple(item for item in retained if item.source_observation_identity in source_ids)
        for bar in retained:
            verifier(bar)
        proof = reconcile_udiff_conflict(
            artifact=artifact, stored_row=evidence[0], incoming_row=evidence[1], retained_bars=retained,
        )
        expected = prior.get(artifact.conflict_fingerprint)
        actual = sorted((bar.source_observation_identity, bar.bar_id) for bar in retained)
        if expected is None or expected.get("status") != "DISTINCT_SERIES/STRUCTURAL_COLLISION_RESOLVED" or actual != sorted(
            (entry["source_identity"], entry["bar_id"]) for entry in expected["observations"]
        ):
            raise ValueError("WEEKLY_UDIFF_CONFLICT_REPAIR_RECEIPT_MISMATCH")
        proofs.append(proof)
    if set(prior) != {item.artifact.conflict_fingerprint for item in proofs}:
        raise ValueError("WEEKLY_UDIFF_CONFLICT_REPAIR_POPULATION_MISMATCH")
    return audit_udiff_same_provider_conflicts(artifacts, reconciliations=proofs)


def derive(
    *, database: Path, accepted_audit: Path, repair_receipt: Path,
    report: Path | None = None, week_limit: int | None = None,
) -> dict[str, object]:
    """Run one full deterministic source-era derivation/replay pass."""
    if week_limit is not None and week_limit < 1:
        raise ValueError("WEEKLY_UDIFF_WEEK_LIMIT_INVALID")
    with closing(sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)) as source:
        source.row_factory = sqlite3.Row
        manifests = _snapshots(source, "NSE_UDIFF_DAILY_SESSION_COVERAGE_MANIFEST")
        if len(manifests) != 1:
            raise ValueError("WEEKLY_UDIFF_SESSION_MANIFEST_REQUIRED")
        coverage = manifests[0]
        if coverage.requested_dates[0] != SOURCE_ERA_START:
            raise ValueError("WEEKLY_UDIFF_SOURCE_ERA_BOUNDARY_INVALID")
        calendar = nse_capital_market_calendar_2022_2026()
        if (coverage.calendar_id, coverage.calendar_fingerprint) != (calendar.calendar_id, calendar.fingerprint):
            raise ValueError("WEEKLY_UDIFF_SESSION_CALENDAR_MISMATCH")
        identities = (*_snapshots(source, "NSE_UDIFF_EFFECTIVE_IDENTITY_INTERVAL"),
                      *_snapshots(source, "NSE_UDIFF_HISTORICAL_IDENTITY_INTERVAL"))
        identity_index = NseUdiffEffectiveIdentityCoverageIndex(identities)
        query_receipts = _snapshots(source, "NSE_CORPORATE_ACTION_QUERY_RECEIPT")
        actions = _snapshots(source, "HISTORICAL_CORPORATE_ACTION")
        actions_by_instrument: dict[str, tuple[object, ...]] = {}
        for action in actions:
            actions_by_instrument.setdefault(action.canonical_instrument_id, []).append(action)
        actions_by_instrument = {
            key: tuple(sorted(value, key=lambda item: (item.effective_date, item.action_id)))
            for key, value in actions_by_instrument.items()
        }
        conflicts = _reconciled_conflicts(source, accepted_audit=accepted_audit, repair_receipt=repair_receipt)
        conflicts_by_instrument: dict[str, tuple[object, ...]] = {}
        for conflict in conflicts:
            conflicts_by_instrument.setdefault(conflict.canonical_instrument_id, []).append(conflict)
        conflicts_by_instrument = {
            key: tuple(sorted(value, key=lambda item: (item.trade_date, item.conflict_fingerprint)))
            for key, value in conflicts_by_instrument.items()
        }
        instruments = tuple(row[0] for row in source.execute(
            "SELECT DISTINCT instrument_id FROM historical_bars WHERE provider_identity='nse_udiff_official' AND timeframe='1D' ORDER BY instrument_id"
        ))
        max_received = source.execute(
            "SELECT MAX(json_extract(provenance_json, '$.received_at')) FROM historical_bars WHERE provider_identity='nse_udiff_official' AND timeframe='1D'"
        ).fetchone()[0]
        if max_received is None or max_received > coverage.as_of.astimezone(UTC).isoformat():
            raise ValueError("WEEKLY_UDIFF_EVALUATION_AS_OF_INVALID")
        starts: list[date] = []
        cursor = SOURCE_ERA_START
        final = coverage.requested_dates[-1]
        while cursor <= final:
            starts.append(cursor)
            cursor += timedelta(days=7)
        if week_limit is not None:
            starts = starts[:week_limit]
    store = SQLiteNseUdiffWeeklyTechnicalBarStore(database)
    try:
        outcomes: Counter[str] = Counter()
        reasons: Counter[str] = Counter()
        latest_by_instrument: dict[str, object] = {}
        latest_by_holding: dict[str, object] = {}
        holder: dict[str, dict[str, object]] = {name: {"intervals_considered": 0, "derived": 0, "blocked": Counter()} for name in FIVE_HOLDINGS.values()}
        complete_weeks = incomplete_weeks = special_blocked_weeks = 0
        for index, start in enumerate(starts, start=1):
            session_plan = build_nse_udiff_weekly_session_plan(week_start=start, coverage=coverage, calendar=calendar)
            complete_weeks += int(session_plan.is_complete)
            incomplete_weeks += int(not session_plan.is_complete)
            special_blocked_weeks += int(bool(set(session_plan.missing_session_dates) & set(session_plan.special_expected_sessions)))
            if not session_plan.is_complete:
                for instrument in instruments:
                    request = NseUdiffWeeklyTechnicalDerivationRequest(
                        instrument, session_plan, DailyTechnicalRequirement(DailyTechnicalRequirementProfile.PRICE_AND_VOLUME),
                        NseUdiffDailyTechnicalUseMode.CURRENT_DESCRIPTIVE_TECHNICAL,
                    )
                    value = derive_nse_udiff_weekly_technical_bar(request=request, daily_read=None)
                    outcomes[value.state.value] += 1
                    reasons.update(value.reasons)
                    name = FIVE_HOLDINGS.get(instrument)
                    if name: holder[name]["intervals_considered"] += 1; holder[name]["blocked"].update(value.reasons)
                continue
            raw_for_week = _udiff_bars_for_week(database, start)
            materialised = []
            for instrument in instruments:
                assertion = compose_action_window_coverage(
                    canonical_instrument_id=instrument, window_start=session_plan.expected_sessions[0],
                    window_end=session_plan.expected_sessions[-1], identity_intervals=identity_index,
                    query_receipts=query_receipts, actions=actions_by_instrument.get(instrument, ()),
                    evaluation_as_of=coverage.as_of, required_sessions=session_plan.expected_sessions,
                ).assertion()
                request = NseUdiffDailyTechnicalReadRequest(
                    instrument, session_plan.expected_sessions[0], session_plan.expected_sessions[-1],
                    DailyTechnicalRequirement(DailyTechnicalRequirementProfile.PRICE_AND_VOLUME),
                    NseUdiffDailyTechnicalUseMode.CURRENT_DESCRIPTIVE_TECHNICAL, coverage.as_of,
                )
                evidence = NseUdiffDailyTechnicalReadEvidence(
                    session_plan.expected_sessions, raw_for_week.get(instrument, ()), identity_index,
                    assertion, actions_by_instrument.get(instrument, ()), conflicts_by_instrument.get(instrument, ()),
                )
                daily = read_certified_daily_technical_bars(request=request, evidence=evidence)
                value = derive_nse_udiff_weekly_technical_bar(
                    request=NseUdiffWeeklyTechnicalDerivationRequest(
                        instrument, session_plan, request.requirement, request.use_mode,
                    ), daily_read=daily,
                )
                outcomes[value.state.value] += 1
                reasons.update(value.reasons)
                name = FIVE_HOLDINGS.get(instrument)
                if name:
                    holder[name]["intervals_considered"] += 1
                    if value.state is NseUdiffWeeklyTechnicalState.READY:
                        holder[name]["derived"] += 1
                        latest_by_holding[name] = value
                    else:
                        holder[name]["blocked"].update(value.reasons)
                if value.state is NseUdiffWeeklyTechnicalState.READY:
                    materialised.append(value)
                    latest_by_instrument[instrument] = value
            writes = store.save_many(materialised)
            outcomes.update("STORE_" + item.value for item in writes)
            print(_encoded({"week": index, "start": start.isoformat(), "complete": True,
                            "ready": len(materialised), "inserted": writes.count(NseUdiffWeeklyTechnicalBarWriteOutcome.INSERTED),
                            "identical": writes.count(NseUdiffWeeklyTechnicalBarWriteOutcome.IDENTICAL),
                            "conflict": writes.count(NseUdiffWeeklyTechnicalBarWriteOutcome.CONFLICT)}), flush=True)
        five = {}
        for name, state in holder.items():
            item = latest_by_holding.get(name)
            five[name] = {
                "intervals_considered": state["intervals_considered"], "derived": state["derived"],
                "latest": None if item is None else {
                    "week_start": item.request.session_plan.week_start.isoformat(),
                    "bar_id": item.weekly_bar_id, "child_count": len(item.technical_bar.source_lineage),
                    "series": list(item.daily_read.certification.selected_series),
                    "price_continuity": item.daily_read.certification.price_continuity.value,
                    "volume_continuity": item.daily_read.certification.volume_continuity.value,
                    "lineage_count": len(item.technical_bar.source_lineage),
                },
                "blocked_reasons": dict(sorted(state["blocked"].items())),
            }
        result = {
            "contract": "canonical-weekly-technical-bar-derivation-v1",
            "source_era": [SOURCE_ERA_START.isoformat(), coverage.requested_dates[-1].isoformat()],
            "current_descriptive_state": "ACTIVE_FOR_CURRENT_DESCRIPTIVE_READS",
            "strict_historical_pit_state": "NOT_READY",
            "strict_historical_pit_reason": "STRICT_HISTORICAL_PIT_SOURCE_AVAILABILITY_UNAVAILABLE",
            "instruments": len(instruments), "weekly_intervals": len(starts),
            "complete_weekly_intervals": complete_weeks, "incomplete_weekly_intervals": incomplete_weeks,
            "special_session_blocked_intervals": special_blocked_weeks,
            "outcomes": dict(sorted(outcomes.items())), "blocked_reason_distribution": dict(sorted(reasons.items())),
            "stored_weekly_bars": store.count(), "stored_conflicts": store.conflict_count(),
            "securities_with_latest_complete_week": len(latest_by_instrument),
            "five_holdings": five,
        }
    finally:
        store.close()
    if report is not None:
        encoded = _encoded(result)
        if report.exists() and report.read_text(encoding="utf-8") != encoded:
            raise ValueError("WEEKLY_UDIFF_DERIVATION_REPORT_IMMUTABILITY_CONFLICT")
        report.parent.mkdir(parents=True, exist_ok=True)
        if not report.exists():
            report.write_text(encoded, encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--accepted-audit", type=Path, required=True)
    parser.add_argument("--repair-receipt", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--week-limit", type=int)
    args = parser.parse_args()
    print(_encoded(derive(
        database=args.database, accepted_audit=args.accepted_audit,
        repair_receipt=args.repair_receipt, report=args.report, week_limit=args.week_limit,
    )), flush=True)
