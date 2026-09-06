from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
import sqlite3

import pytest

from app.market_data.historical import (
    SQLiteHistoricalBarStore, BarWriteOutcome, HistoricalBarConflictArtifact,
    _provider_bar_values, sqlite_provider_versioned_historical_bars_schema,
)
from app.market_data.nse_udiff_daily_history import _artifact_from_bytes, _parse_valid_archive, _bar_from_row
from app.market_data.nse_udiff_archive_verification import UdiffArchiveVerifier
from app.market_data.nse_udiff_source_identity import observation_key, source_row_id
from app.market_data.sqlite_udiff_series_migration import migrate, RETAINED
from app.market_data.models import Timeframe
from tests.unit.test_nse_udiff_daily_history import row, archive, result, target, backfill, Source, D, T


def observations(*rows):
    artifact = _artifact_from_bytes("nse-udiff-acquisition:test", result(archive(rows)))
    parsed = _parse_valid_archive(artifact)
    bars = tuple(_bar_from_row(artifact, parsed, i, r, target())[0] for i, r in enumerate(parsed.rows))
    return artifact, bars


@pytest.mark.parametrize("series", ["BL", "BE", "T0", "EQ"])
@pytest.mark.parametrize("reverse", [False, True])
def test_distinct_source_identity_coexists_no_canonical_winner(tmp_path, series, reverse):
    a, bars = observations(row(), {**row(), "SctySrs": series, "FinInstrmId": "777"})
    store = SQLiteHistoricalBarStore(tmp_path / "bars.db")
    assert all(x == BarWriteOutcome.INSERTED for x in store.upsert_many(tuple(reversed(bars)) if reverse else bars))
    assert all(x == BarWriteOutcome.IDENTICAL for x in store.upsert_many(bars))
    raw = store.raw_range(target().canonical_instrument_id, Timeframe.DAILY, datetime(2024, 7, 7, tzinfo=UTC), T)
    assert len(raw) == 2 and len({b.source_observation_identity for b in raw}) == 2
    assert store.latest(target().canonical_instrument_id, Timeframe.DAILY, 10) == ()
    assert store.range(target().canonical_instrument_id, Timeframe.DAILY, datetime(2024, 7, 7, tzinfo=UTC), T) == ()
    store.close()


def test_exact_identity_excludes_canonical_current_instrument_and_artifact_ordinal():
    a, (bar,) = observations(row())
    assert observation_key(bar) == source_row_id(row())
    renamed_id = replace(bar, instrument=replace(bar.instrument, instrument_id="unrelated-canonical-id"))
    assert observation_key(renamed_id) == observation_key(bar)


def test_source_identity_rejects_noncanonical_daily_interval():
    from datetime import timedelta
    _, (bar,) = observations(row())
    with pytest.raises(ValueError, match="INTERVAL_INVALID"):
        observation_key(replace(bar, end_time=bar.end_time + timedelta(hours=1)))


def test_true_value_amendment_blocks_and_retains_conflict(tmp_path):
    _, (bar,) = observations(row())
    store = SQLiteHistoricalBarStore(tmp_path / "bars.db")
    assert store.upsert(bar) == BarWriteOutcome.INSERTED
    altered = replace(bar, close=Decimal("101"))
    assert store.upsert(altered) == BarWriteOutcome.CONFLICT
    conflict = HistoricalBarConflictArtifact.from_bars(bar, altered, detected_at=T)
    store.save_conflict_artifact(conflict)
    assert store.same_provider_bar(bar) == bar
    assert store.list_conflict_artifacts() == (conflict,)
    store.close()


def legacy(tmp_path):
    artifact, bars = observations(row(), {**row(), "SctySrs": "BL", "FinInstrmId": "777"})
    db = tmp_path / "old.db"
    with sqlite3.connect(db) as c:
        c.execute(sqlite_provider_versioned_historical_bars_schema())
        c.execute("INSERT INTO historical_bars VALUES (" + ",".join("?" for _ in range(18)) + ")", _provider_bar_values(bars[0], "nse_udiff_official"))
    return db, artifact, bars


def test_migration_preserves_ids_values_backup_and_old_table_then_reopen(tmp_path):
    db, artifact, bars = legacy(tmp_path)
    verify = UdiffArchiveVerifier(lambda _: artifact)
    report = migrate(db, tmp_path / "backup.db", verify_archive=verify)
    assert report["before"] == report["after"] == report["archive_verified"] == 1
    with sqlite3.connect(db) as c:
        assert c.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert c.execute("PRAGMA foreign_key_check").fetchall() == []
        assert c.execute(f"SELECT * FROM {RETAINED}").fetchone() == _provider_bar_values(bars[0], "nse_udiff_official")
        with pytest.raises(sqlite3.IntegrityError, match="IMMUTABLE"):
            c.execute(f"DELETE FROM {RETAINED}")
    store = SQLiteHistoricalBarStore(db)
    assert store.upsert(bars[0]) == BarWriteOutcome.IDENTICAL
    assert store.upsert(bars[1]) == BarWriteOutcome.INSERTED
    store.close()
    assert migrate(db, tmp_path / "backup.db", verify_archive=verify)["status"] == "ALREADY_CURRENT"
    store = SQLiteHistoricalBarStore(db)
    assert store.same_provider_bar(bars[0]) == bars[0]
    assert store.same_provider_bar(bars[1]) == bars[1]
    store.close()


def test_migration_fault_is_atomic_and_preserves_backup(tmp_path):
    db, artifact, bars = legacy(tmp_path)
    def fail():
        raise RuntimeError("injected")
    with pytest.raises(RuntimeError, match="injected"):
        migrate(db, tmp_path / "backup.db", verify_archive=UdiffArchiveVerifier(lambda _: artifact), before_swap=fail)
    with sqlite3.connect(db) as c:
        assert len(c.execute("PRAGMA table_info(historical_bars)").fetchall()) == 18
        assert c.execute("SELECT * FROM historical_bars").fetchone() == _provider_bar_values(bars[0], "nse_udiff_official")
        assert not c.execute("SELECT name FROM sqlite_master WHERE name=?", (RETAINED,)).fetchone()


def test_tampered_archive_bar_and_stored_identity_fail_closed(tmp_path):
    db, artifact, bars = legacy(tmp_path)
    verify = UdiffArchiveVerifier(lambda _: artifact)
    with pytest.raises(ValueError, match="OBSERVATION_MISMATCH"):
        verify(replace(bars[0], close=Decimal("101")))
    migrate(db, tmp_path / "backup.db", verify_archive=verify)
    with sqlite3.connect(db) as c:
        c.execute("UPDATE historical_bars SET source_observation_identity='tampered'")
    store = SQLiteHistoricalBarStore(db)
    with pytest.raises(ValueError, match="IDENTITY_MISMATCH"):
        store.raw_range(target().canonical_instrument_id, Timeframe.DAILY, datetime(2024, 7, 7, tzinfo=UTC), T)
    store.close()


def test_retained_pipeline_replay_twice_preserves_receipts_and_invalid_exclusion(tmp_path):
    source = Source(result(archive((row(), {**row(), "SctySrs": "BL", "FinInstrmId": "777"}, row(high="1")))))
    service, store, repository = backfill(tmp_path, source)
    first = service.run()
    artifact = service._evidence.artifact(first.acquisition_id, D)
    receipts = service._evidence.receipts(first.acquisition_id)
    a = service.replay_retained_artifact(artifact)
    b = service.replay_retained_artifact(artifact)
    assert a == b and a.inserted == a.conflicts == 0 and a.duplicates == 2 and a.invalid_rows == 1
    assert service._evidence.receipts(first.acquisition_id) == receipts and source.calls == 1
    store.close()


def test_snapshot_bridge_rejects_all_udiff_series():
    from app.market_data.bridge import price_bar_observation
    _, bars = observations(row(), {**row(), "SctySrs": "BL"})
    for bar in bars:
        with pytest.raises(ValueError, match="SERIES_SELECTION_NOT_ACTIVE"):
            price_bar_observation(bar)


def test_new_true_conflicts_are_series_bound_and_legacy_payloads_still_verify():
    from app.market_data.historical import _conflict_artifact_payload, _conflict_artifact_from_payload
    _, bars = observations(row(), {**row(), "SctySrs": "BL"})
    conflicts = [HistoricalBarConflictArtifact.from_bars(b, replace(b, close=Decimal("101")), detected_at=T) for b in bars]
    assert len({c.conflict_fingerprint for c in conflicts}) == 2
    for c in conflicts:
        assert c.stored_lineage.source_observation_identity == c.incoming_lineage.source_observation_identity
        assert _conflict_artifact_from_payload(_conflict_artifact_payload(c)) == c
    with pytest.raises(ValueError, match="DISTINCT_SOURCE"):
        HistoricalBarConflictArtifact.from_bars(bars[0], replace(bars[1], close=Decimal("101")), detected_at=T)
    from tests.unit.test_historical_bar_conflicts import _bar
    old = HistoricalBarConflictArtifact.from_bars(_bar(), _bar(close="101"), detected_at=T)
    payload = _conflict_artifact_payload(old)
    assert "source_observation_identity" not in payload
    assert _conflict_artifact_from_payload(payload) == old


def test_backup_reader_is_available_under_exclusive_migration_lock(tmp_path):
    db, artifact, bars = legacy(tmp_path)
    backup = tmp_path / "backup.db"
    def verify(bar):
        # Read backup independently of the live migration transaction.
        with sqlite3.connect(backup) as c:
            assert c.execute("SELECT bar_id FROM historical_bars").fetchone()[0] == bar.bar_id
        UdiffArchiveVerifier(lambda _: artifact)(bar)
    def exclusive():
        with sqlite3.connect(backup) as c:
            assert c.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert migrate(db, backup, verify_archive=verify, before_swap=exclusive)["status"] == "MIGRATED"
    with sqlite3.connect(db) as writer:
        writer.execute("BEGIN EXCLUSIVE")
        exclusive()
        writer.rollback()


def test_pre_migration_udiff_writes_fail_closed(tmp_path):
    db, _, bars = legacy(tmp_path)
    store = SQLiteHistoricalBarStore(db)
    with pytest.raises(RuntimeError, match="SERIES_MIGRATION_REQUIRED"):
        store.upsert(bars[1])
    store.close()


def test_same_values_new_archive_lineage_is_equivalent_not_amendment(tmp_path):
    _, (first,) = observations(row())
    _, (_, second) = observations({**row(), "ISIN": "INE000A01002"}, row())
    assert first.provenance.request_reference != second.provenance.request_reference
    store = SQLiteHistoricalBarStore(tmp_path / "bars.db")
    store.upsert(first)
    assert store.upsert(second) == BarWriteOutcome.IDENTICAL
    assert store.upsert(replace(second, close=Decimal("102.000"))) == BarWriteOutcome.IDENTICAL
    assert store.same_provider_bar(second) == first
    store.close()


def test_readiness_and_pit_do_not_count_ambiguous_series(tmp_path):
    _, bars = observations(row(), {**row(), "SctySrs": "T0"})
    store = SQLiteHistoricalBarStore(tmp_path / "bars.db")
    store.upsert_many(bars)
    iid = target().canonical_instrument_id
    assert store.readiness_evidence((iid,), Timeframe.DAILY) == {}
    assert store.raw_range(iid, Timeframe.DAILY, bars[0].start_time, T, as_of=bars[0].end_time) == ()
    assert len(store.raw_range(iid, Timeframe.DAILY, bars[0].start_time, T, as_of=T)) == 2
    store.close()


def test_postgresql_row_roundtrip_and_migration_contract():
    from app.market_data.historical import _bar_from_pg_row
    _, (bar,) = observations(row())
    values = (*_provider_bar_values(bar, "nse_udiff_official", postgresql=True), observation_key(bar))
    assert _bar_from_pg_row(values) == bar
    import ast
    from pathlib import Path
    source = Path("migrations/versions/20260906_10_udiff_series_observations.py").read_text()
    ast.parse(source)
    assert 'down_revision = "20260830_09"' in source
    assert '"end_time", "provider_identity", "source_observation_identity"' in source
    assert 'UDIFF_SERIES_EVIDENCE_PRESERVING_FORWARD_MIGRATION_REQUIRED' in source
    assert "UdiffArchiveVerifier(load)" in source


def test_snapshot_reader_blocks_udiff_even_when_bridge_bypassed():
    from app.domain.models import AsOfSnapshot
    from app.analysis.series import price_bar_series
    from app.market_data.bridge import price_bar_observation
    _, (bar,) = observations(row())
    non_udiff = replace(bar, provenance=replace(bar.provenance, provider="fixture"))
    observation = price_bar_observation(non_udiff)
    observation = replace(observation, provenance=replace(observation.provenance, source="NSE_UDIFF_OFFICIAL"))
    snapshot = AsOfSnapshot("isolated", T, T, "test", (observation,))
    series = price_bar_series(snapshot, bar.instrument.instrument_id)
    assert not series.bars and series.reason == "NSE_UDIFF_TECHNICAL_SERIES_SELECTION_NOT_ACTIVE"


def test_postgresql_repository_uses_source_identity_for_insert_and_lookup():
    from contextlib import contextmanager
    from types import SimpleNamespace
    from app.market_data.historical import PostgreSQLHistoricalBarStore
    from app.storage.database import DatabaseBackend
    class Cursor:
        def __init__(self):
            self.rows, self.result = {}, None
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def execute(self, query, params):
            assert "source_observation_identity" in query
            if query.startswith("SELECT"):
                self.result = self.rows.get(tuple(params))
            else:
                assert len(params) == 19
                key = tuple(v.isoformat() if isinstance(v, datetime) else v for v in params[:5])
                self.rows[(*key, params[-1])] = params
        def fetchone(self):
            return self.result
    cursor = Cursor()
    @contextmanager
    def transaction():
        yield SimpleNamespace(cursor=lambda: cursor)
    store = PostgreSQLHistoricalBarStore(SimpleNamespace(settings=SimpleNamespace(backend=DatabaseBackend.POSTGRESQL), transaction=transaction))
    _, bars = observations(row(), {**row(), "SctySrs": "BL"})
    for bar in bars:
        assert store.upsert(bar) == BarWriteOutcome.INSERTED
        assert store.upsert(bar) == BarWriteOutcome.IDENTICAL
        assert store.same_provider_bar(bar) == bar
    assert len(cursor.rows) == 2


def test_be_bl_and_session_identity_remain_distinct_in_ingestion(tmp_path):
    rows = ({**row(), "SctySrs": "BE"}, {**row(), "SctySrs": "BL"}, {**row(), "SctySrs": "BE", "SsnId": "F2"})
    source = Source(result(archive(rows)))
    service, store, _ = backfill(tmp_path, source)
    receipt = service.run().receipts[0]
    assert (receipt.inserted, receipt.conflicts, receipt.duplicates) == (3, 0, 0)
    store.close()


def test_generic_ingestion_duplicate_key_preserves_source_series(tmp_path):
    from app.market_data.historical import HistoricalIngestionService
    from app.market_data.models import HistoricalBarsRequest, AdjustmentStatus
    _, bars = observations(row(), {**row(), "SctySrs": "BL"})
    class Provider:
        def get_historical_bars(self, request):
            return bars
    store = SQLiteHistoricalBarStore(tmp_path / "generic.db")
    request = HistoricalBarsRequest(bars[0].instrument, Timeframe.DAILY, bars[0].start_time, bars[0].end_time, AdjustmentStatus.RAW, "nse_udiff_official")
    report = HistoricalIngestionService(Provider(), store, clock=lambda: T).ingest(request)
    assert report.accepted_count == 2
    assert store.raw_count(bars[0].instrument.instrument_id, Timeframe.DAILY) == 2
    store.close()
