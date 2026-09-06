"""Explicit offline UDiFF v1 repair and two-pass retained-artifact replay.

No runtime configuration, credentials, network, or historical identity promotion.
Run as python -m scripts.repair_nse_udiff_series_storage with explicit paths.
Reports are immutable, exclusive-created local receipts, not source observations.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

from app.market_data.historical import SQLiteHistoricalBarStore, _bar_from_mapping
from app.market_data.nse_udiff_archive_verification import UdiffArchiveVerifier
from app.market_data.nse_udiff_daily_history import (
    NseUdiffDailyHistoryBackfill, NseUdiffDailyHistoryStore, NseUdiffDailySource,
    NseUdiffDailyTarget, nse_udiff_acquisition_id, _parse_valid_archive,
)
from app.market_data.nse_udiff_source_identity import source_row_id
from app.market_data.sqlite_udiff_series_migration import migrate, RETAINED
from app.storage.core_api_snapshot_repository import snapshot_json_from
from app.storage.database import DatabaseBackend, DatabaseSettings
from app.storage.repository_factory import create_core_api_snapshot_repository
from app.universe_analysis.service import CoreUniverseAnalysisStore


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str, allow_nan=False)


def receipt(path, value):
    body = encoded(value)
    if path.exists():
        if path.read_text(encoding="utf-8") != body:
            raise ValueError("UDIFF_REPAIR_RECEIPT_ALREADY_EXISTS_DIFFERENT")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as f:
        f.write(body)


def readonly(path):
    c = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    c.execute("PRAGMA query_only=ON")
    return c


def inventory(c):
    series = Counter()
    for raw, in c.execute("SELECT warnings_json FROM historical_bars WHERE provider_identity='nse_udiff_official'"):
        labels = [x.split(":", 1)[1] for x in json.loads(raw) if x.startswith("NSE_UDIFF_SERIES:")]
        if len(labels) != 1:
            raise ValueError("UDIFF_REPAIR_SERIES_AMBIGUOUS")
        series[labels[0]] += 1
    return {"historical_bars": c.execute("SELECT count(*) FROM historical_bars").fetchone()[0],
            "provider_counts": dict(c.execute("SELECT provider_identity,count(*) FROM historical_bars GROUP BY provider_identity")),
            "series": dict(sorted(series.items())),
            "snapshot_families": dict(c.execute("SELECT family,count(*) FROM core_api_snapshots GROUP BY family")),
            "conflicts": c.execute("SELECT count(*) FROM historical_bar_conflicts").fetchone()[0]}


def unchanged_tables(c):
    """Aggregate exact bytes/values, never display private table contents."""
    values = {}
    names = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    for name in names:
        if name == "historical_bars" or name.startswith("historical_bars_"):
            continue
        quoted = '"' + name.replace('"', '""') + '"'
        digest, count = sha256(), 0
        # All local tables have stable rowids; no maintenance/rewrite is run here.
        for row in c.execute(f"SELECT * FROM {quoted} ORDER BY rowid"):
            digest.update(encoded(tuple(row)).encode())
            digest.update(b"\n")
            count += 1
        values[name] = {"count": count, "digest": digest.hexdigest()}
    return values


class NoNetwork(NseUdiffDailySource):
    def fetch(self, trade_date):
        raise AssertionError("UDIFF_REPAIR_NETWORK_FORBIDDEN")


def run(database, backup, output, audit_path):
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    if audit["classification_counts"] != {"DISTINCT_SERIES": 784}:
        raise ValueError("UDIFF_REPAIR_ACCEPTED_AUDIT_REQUIRED")
    with closing(readonly(database)) as c:
        before = inventory(c)
        preserved = unchanged_tables(c)
        def load(identifier):
            # The verified backup exists before this callback. Avoid a second
            # reader contending with migration cache-spill locks on the live DB.
            with closing(readonly(backup)) as archive_connection:
                raw = archive_connection.execute("SELECT payload_json FROM core_api_snapshots WHERE snapshot_id=?", (identifier,)).fetchone()
            if raw is None:
                raise ValueError("UDIFF_REPAIR_ARCHIVE_MISSING")
            return snapshot_json_from(raw[0]).payload
        receipt(output / "before.json", {"inventory": before, "preserved": preserved, "database_bytes": database.stat().st_size,
                                         "audit_sha256": sha256(audit_path.read_bytes()).hexdigest()})
        print("Pre-migration inventory sealed; verifying backup and archived observations", flush=True)
        migration = migrate(database, backup, verify_archive=UdiffArchiveVerifier(load),
                            progress=lambda n: print(f"Archive-verified migrated rows: {n}", flush=True))
    receipt(output / "migration.json", migration)
    print(encoded(migration), flush=True)

    repository = create_core_api_snapshot_repository(DatabaseSettings(DatabaseBackend.SQLITE, "sqlite:///" + str(database.resolve())))
    bars = SQLiteHistoricalBarStore(database)
    try:
        universe_store = CoreUniverseAnalysisStore(repository)
        universe = universe_store.latest_universe_snapshot()
        if universe.snapshot_id != audit["universe_id"] or universe.checksum != audit["universe_checksum"]:
            raise ValueError("UDIFF_REPAIR_UNIVERSE_CHANGED")
        instruments = {v.instrument_id: v for v in universe_store.instruments_as_of(universe.as_of)}
        targets = tuple(NseUdiffDailyTarget.from_instrument(instruments[i]) for i in universe.instrument_ids)
        evidence = NseUdiffDailyHistoryStore(repository)
        acquisition = nse_udiff_acquisition_id(universe)
        service = NseUdiffDailyHistoryBackfill(source=NoNetwork(), evidence=evidence, bars=bars, targets=targets,
                                             acquisition_id=acquisition, universe_snapshot=universe)
        artifacts = evidence.artifacts(acquisition)
        if len(artifacts) != 532 or {(a.artifact_id, a.fingerprint) for a in artifacts} != {tuple(x) for x in audit["source_artifacts"]}:
            raise ValueError("UDIFF_REPAIR_ARCHIVE_INVENTORY_CHANGED")
        # Replay all retained sessions, not just collision rows; no hand insertion.
        runs = []
        for number in (1, 2):
            totals = Counter()
            for index, artifact in enumerate(artifacts, 1):
                result = service.replay_retained_artifact(artifact)
                receipt(output / f"replay-{number}" / f"{artifact.trade_date}.json", asdict(result))
                for key in ("inserted", "duplicates", "conflicts", "invalid_rows", "identity_discontinuities", "unresolved_identity_rows", "rows_seen"):
                    totals[key] += getattr(result, key)
                if result.conflicts or (number == 2 and result.inserted):
                    raise ValueError("UDIFF_REPAIR_UNEXPECTED_CONFLICT_OR_NON_IDEMPOTENCY")
                if index % 25 == 0 or index == len(artifacts):
                    print(encoded({"pass": number, "sessions": index, **totals}), flush=True)
            runs.append(dict(totals))
        # Reproduce both old conflict sides from archived source rows and match
        # exact normalized values. Old conflict artifacts remain unchanged.
        by_id = {a.artifact_id: a for a in artifacts}
        resolved, affected = [], set()
        for conflict in audit["conflicts"]:
            sides = []
            for side in ("stored", "incoming"):
                evidence_row = conflict[side]
                fields = dict(evidence_row["fields"])
                identity = source_row_id(fields)
                rows = bars._connection.execute("SELECT * FROM historical_bars WHERE instrument_id=? AND provider_identity='nse_udiff_official' AND source_observation_identity=?", (conflict["canonical_instrument_id"], identity)).fetchall()
                if len(rows) != 1:
                    raise ValueError("UDIFF_REPAIR_CONFLICT_SIDE_NOT_UNIQUE")
                bar = _bar_from_mapping(rows[0])
                UdiffArchiveVerifier(lambda identifier: by_id[identifier])(bar)
                values = conflict["legacy_artifact"][side + "_values"]
                for name in ("open", "high", "low", "close", "volume", "turnover", "trade_count"):
                    from decimal import Decimal
                    if Decimal(str(getattr(bar, name))) != Decimal(str(values[name])):
                        raise ValueError("UDIFF_REPAIR_CONFLICT_VALUES_CHANGED")
                sides.append({"source_identity": identity, "bar_id": bar.bar_id, "series": fields["SctySrs"]})
            resolved.append({"conflict_fingerprint": conflict["conflict_fingerprint"], "status": "DISTINCT_SERIES/STRUCTURAL_COLLISION_RESOLVED", "observations": sides})
            affected.add(conflict["canonical_instrument_id"])
        receipt(output / "structural-resolutions.json", resolved)
    finally:
        bars.close()
        close = getattr(repository, "close", None)
        if callable(close):
            close()
    with closing(readonly(database)) as c:
        after = inventory(c)
        now = unchanged_tables(c)
        if preserved != now:
            raise ValueError("UDIFF_REPAIR_UNRELATED_EVIDENCE_CHANGED")
        old_columns = [r[1] for r in c.execute(f"PRAGMA table_info({RETAINED})")]
        columns = ",".join(old_columns)
        if c.execute(f"SELECT {columns} FROM {RETAINED} EXCEPT SELECT {columns} FROM historical_bars LIMIT 1").fetchone():
            raise ValueError("UDIFF_REPAIR_ORIGINAL_BAR_CHANGED")
        integrity = c.execute("PRAGMA integrity_check").fetchall()
        fk = c.execute("PRAGMA foreign_key_check").fetchall()
        if integrity != [("ok",)] or fk:
            raise ValueError("UDIFF_REPAIR_FINAL_INTEGRITY_FAILED")
        holdings = {}
        for symbol, isin in (("APARINDS", "INE372A01015"), ("DEEPINDS", "INE0FHS01024"), ("GENUSPOWER", "INE955D01029"), ("GLAND", "INE068V01023"), ("ICICIBANK", "INE090A01021")):
            counts = Counter()
            for raw, in c.execute("SELECT warnings_json FROM historical_bars WHERE instrument_id=? AND provider_identity='nse_udiff_official'", ("NSE:" + isin,)):
                counts.update(x.split(":", 1)[1] for x in json.loads(raw) if x.startswith("NSE_UDIFF_SERIES:"))
            holdings[symbol] = dict(sorted(counts.items()))
    final = {"migration": migration, "before": before, "after": after, "replays": runs,
             "affected_instruments_repaired": len(affected), "historical_conflicts_resolved": len(resolved),
             "current_unresolved_structural_conflicts": 0, "unchanged_other_tables": True,
             "original_bar_values_preserved": True, "integrity": "ok", "fk_violations": 0,
             "holdings": holdings, "identity_promotion": "NOT_ACTIVE", "technical_selection": "NOT_ACTIVE"}
    receipt(output / "final.json", final)
    print(encoded(final), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("database", "backup", "output", "audit"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    run(args.database, args.backup, args.output, args.audit)
