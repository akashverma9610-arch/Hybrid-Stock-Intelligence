"""Read-only, exhaustive UDiFF collision audit. No acquisition or DB repair.

Run from the repository root with explicit --database and --output paths.
The output is local audit evidence, never a canonical eligibility receipt.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import closing
from datetime import datetime
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo

from app.market_data.historical import _conflict_artifact_from_payload
from app.market_data.nse_udiff_conflict_semantics import (
    IDENTITY_FIELDS, VALUE_FIELDS, classify_source_rows, source_row_evidence,
)
from app.market_data.nse_udiff_daily_history import _parse_valid_archive
from app.storage.core_api_snapshot_repository import snapshot_json_from


def open_readonly(database: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
    connection.execute("PRAGMA query_only=ON")
    connection.execute("BEGIN")
    return connection


def _values(row):
    return tuple(Decimal(row[k]) for k in VALUE_FIELDS)


def audit(database: Path) -> dict:
    with closing(open_readonly(database)) as c:
        conflicts = defaultdict(list)
        for raw, in c.execute("SELECT payload_json FROM historical_bar_conflicts ORDER BY conflict_fingerprint"):
            value = _conflict_artifact_from_payload(raw)  # verify sealed legacy artifact
            if value.incoming_lineage.provider_identity == "nse_udiff_official":
                conflicts[value.incoming_lineage.source_identity].append(json.loads(raw))
        universe = snapshot_json_from(c.execute(
            "SELECT payload_json FROM core_api_snapshots WHERE family='UNIVERSE_SNAPSHOT' ORDER BY created_at DESC,snapshot_id LIMIT 1"
        ).fetchone()[0]).payload
        # This is a present-universe audit, not a historical PIT selection.
        targets = {}
        for raw, in c.execute("SELECT payload_json FROM core_api_snapshots WHERE family='NSE_UNIVERSE' ORDER BY created_at,snapshot_id"):
            value = snapshot_json_from(raw).payload
            if value.instrument_id in universe.instrument_ids:
                targets[value.isin] = value.symbol
        details, artifacts = [], []
        pairings = defaultdict(list)
        variants, dated_current = defaultdict(set), defaultdict(set)
        all_rows = 0
        for raw, in c.execute("SELECT payload_json FROM core_api_snapshots WHERE family='NSE_UDIFF_DAILY_SOURCE_ARTIFACT' ORDER BY snapshot_id"):
            artifact = snapshot_json_from(raw).payload
            parsed = _parse_valid_archive(artifact)
            artifacts.append((artifact.artifact_id, artifact.fingerprint))
            by_token = defaultdict(list)
            for index, row in enumerate(parsed.rows):
                all_rows += 1
                by_token[row["FinInstrmId"]].append((index, row))
                isin = row["ISIN"]
                if isin not in targets:
                    continue
                signature = (row["TckrSymb"], row["SctySrs"], row["FinInstrmId"])
                variants[isin].add(signature)
                if row["TckrSymb"] == targets[isin]:
                    dated_current[isin].add((str(artifact.trade_date), *signature[1:]))
                else:
                    pairings[(targets[isin], row["TckrSymb"], isin)].append({
                        "date": str(artifact.trade_date), "series": row["SctySrs"],
                        "token": row["FinInstrmId"], "artifact_id": artifact.artifact_id,
                        "row_index": index,
                    })
            for conflict in conflicts[artifact.source_url]:
                selected = {}
                expected_day = datetime.fromisoformat(conflict["start_time"]).astimezone(ZoneInfo("Asia/Kolkata")).date()
                if expected_day != artifact.trade_date:
                    raise ValueError("UDIFF_AUDIT_CONFLICT_DATE_MISMATCH")
                for side in ("stored", "incoming"):
                    lineage = conflict[side + "_lineage"]
                    if lineage["source_identity"] != artifact.source_url:
                        raise ValueError("UDIFF_AUDIT_OTHER_ARTIFACT_REQUIRES_RECONCILIATION")
                    token = lineage["provider_instrument_reference"].removeprefix("NSE:CM:")
                    numbers = conflict[side + "_values"]
                    expected = tuple(Decimal(str(numbers[k])) for k in (
                        "open", "high", "low", "close", "volume", "turnover", "trade_count",
                    ))
                    matches = [(i, r) for i, r in by_token[token]
                               if conflict["canonical_instrument_id"] == "NSE:" + r["ISIN"]
                               and _values(r) == expected]
                    if len(matches) != 1:
                        raise ValueError("UDIFF_AUDIT_EXACT_SOURCE_ROW_NOT_UNIQUE")
                    selected[side] = source_row_evidence(artifact, matches[0][0])
                left, right = selected["stored"], selected["incoming"]
                a, b = dict(left.fields), dict(right.fields)
                details.append({
                    "conflict_fingerprint": conflict["conflict_fingerprint"],
                    "canonical_instrument_id": conflict["canonical_instrument_id"],
                    "trade_date": str(artifact.trade_date),
                    "existing_persistence_key": [conflict[k] for k in (
                        "canonical_instrument_id", "timeframe", "start_time", "end_time",
                    )] + ["nse_udiff_official"],
                    "classification": classify_source_rows(left, right).value,
                    "differing_identity_dimensions": [k for k in IDENTITY_FIELDS if a[k] != b[k]],
                    "stored": left.to_dict(), "incoming": right.to_dict(),
                    "legacy_artifact": conflict,
                })
        if len(details) != sum(map(len, conflicts.values())):
            raise ValueError("UDIFF_AUDIT_CONFLICT_JOIN_INCOMPLETE")
        if len({v["conflict_fingerprint"] for v in details}) != len(details):
            raise ValueError("UDIFF_AUDIT_MULTIPLE_ARCHIVE_VERSIONS")
        pairing_report = []
        for (current, historical, isin), observations in sorted(pairings.items()):
            old_codes = {(r["series"], r["token"]) for r in observations}
            matching_new = sorted(p for p in dated_current[isin] if (p[1], p[2]) in old_codes)
            pairing_report.append({
                "current_symbol": current, "historical_symbol": historical, "isin": isin,
                "classification": "SAME_ISIN_DIFFERENT_SOURCE_SYMBOL",
                "continuity": "NOT_CERTIFIED_PENDING_IDENTITY_BOUNDARY_REPAIR",
                "same_token_series_current_symbol_observed": bool(matching_new),
                "current_symbol_source_points": matching_new,
                "row_count": len(observations), "observations": sorted(observations, key=lambda r: (r["date"], r["row_index"])),
            })
        stored_series = Counter()
        for raw, in c.execute("SELECT warnings_json FROM historical_bars WHERE provider_identity='nse_udiff_official'"):
            labels = [v.removeprefix("NSE_UDIFF_SERIES:") for v in json.loads(raw) if v.startswith("NSE_UDIFF_SERIES:")]
            if len(labels) != 1:
                raise ValueError("UDIFF_AUDIT_STORED_SERIES_AMBIGUOUS")
            stored_series[labels[0]] += 1
        family_counts = dict(c.execute("SELECT family,count(*) FROM core_api_snapshots GROUP BY family"))
        mii_dates = Counter()
        for raw, in c.execute("SELECT payload_json FROM core_api_snapshots WHERE family='HISTORICAL_NSE_SECURITY_MASTER_SNAPSHOT'"):
            fields = json.loads(raw)["payload"].get("fields", {})
            if "report_date" in fields:
                mii_dates[fields["report_date"]["value"]] += 1
        series_pairs = Counter((dict(d["stored"]["fields"])["SctySrs"], dict(d["incoming"]["fields"])["SctySrs"]) for d in details)
        result = {
            "contract": "nse-udiff-identity-boundary-audit-v1",
            "status": "SYSTEMIC_PERSISTENCE_KEY_REPAIR_REQUIRED",
            "universe_id": universe.snapshot_id, "universe_checksum": universe.checksum,
            "universe_count": len(targets), "source_artifacts": sorted(artifacts),
            "source_rows": all_rows, "conflicts": sorted(details, key=lambda d: d["conflict_fingerprint"]),
            "classification_counts": dict(sorted(Counter(d["classification"] for d in details).items())),
            "series_pairs": [{"stored": a, "incoming": b, "count": n} for (a, b), n in sorted(series_pairs.items())],
            "pairings": pairing_report, "identity_variants": {k: sorted(v) for k, v in sorted(variants.items())},
            "stored_udiff_series": dict(sorted(stored_series.items())),
            "mii_report_date_row_counts": dict(sorted(mii_dates.items())),
            "snapshot_family_counts": family_counts,
            "historical_bar_counts": dict(c.execute("SELECT provider_identity,count(*) FROM historical_bars GROUP BY provider_identity")),
            "integrity": [r[0] for r in c.execute("PRAGMA integrity_check")],
            "fk_violations": len(c.execute("PRAGMA foreign_key_check").fetchall()),
            "historical_bar_schema": c.execute("SELECT sql FROM sqlite_master WHERE name='historical_bars'").fetchone()[0],
        }
        return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.database)
    body = json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    fingerprint = sha256(body.encode()).hexdigest()
    # Immutable content-addressed local report; never stage reports or raw data.
    args.output.mkdir(parents=True, exist_ok=True)
    target = args.output / ("audit-" + fingerprint + ".json")
    if target.exists():
        if target.read_text(encoding="utf-8") != body:
            raise ValueError("UDIFF_AUDIT_REPORT_TAMPERED")
    else:
        with target.open("x", encoding="utf-8") as handle:
            handle.write(body)
    print(json.dumps({"report": str(target), "fingerprint": fingerprint,
                      "classifications": result["classification_counts"],
                      "integrity": result["integrity"], "fk_violations": result["fk_violations"]}))


if __name__ == "__main__":
    main()
