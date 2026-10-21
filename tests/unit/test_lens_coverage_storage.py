from dataclasses import replace

import pytest

from app.lens_knowledge.storage import DraftLensCoverageStore
from app.lens_knowledge.universe import assess_universe_batch
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository
from app.universe_analysis.service import build_universe_snapshot
from tests.fixtures.analytical_observations import ANALYSIS_TIME
from tests.unit.test_universe_analysis import instrument


def batch():
    universe = build_universe_snapshot(snapshot_id="stored-universe", as_of=ANALYSIS_TIME,
        source="fixture", instruments=(instrument("a"), instrument("b")))
    return assess_universe_batch(universe=universe, as_of=ANALYSIS_TIME, diagnostics_by_instrument={}, batch_size=1)


def test_snapshot_survives_restart_and_is_idempotent(tmp_path):
    path = tmp_path / "snapshots.sqlite"
    repo = SQLiteCoreApiSnapshotRepository(path)
    store = DraftLensCoverageStore(repo)
    value = batch()
    key = store.save(value, recorded_at=ANALYSIS_TIME)
    assert store.save(value, recorded_at=ANALYSIS_TIME) == key
    repo.close()
    repo = SQLiteCoreApiSnapshotRepository(path)
    assert DraftLensCoverageStore(repo).get(key) == value
    assert DraftLensCoverageStore(repo).get("missing") is None
    repo.close()


def test_changed_content_at_same_page_and_as_of_is_conflict(tmp_path):
    repo = SQLiteCoreApiSnapshotRepository(tmp_path / "snapshots.sqlite")
    store = DraftLensCoverageStore(repo)
    value = batch()
    key = store.save(value, recorded_at=ANALYSIS_TIME)
    row = value.securities[0]
    altered = replace(row.assessments[0], reasons=("changed",))
    changed_row = replace(row, assessments=(altered,) + row.assessments[1:])
    with pytest.raises(ValueError, match="CONFLICT"):
        store.save(replace(value, securities=(changed_row,)), recorded_at=ANALYSIS_TIME)
    assert store.get(key) == value
    repo.close()


def test_snapshot_corruption_is_not_returned_as_valid(tmp_path):
    repo = SQLiteCoreApiSnapshotRepository(tmp_path / "snapshots.sqlite")
    store = DraftLensCoverageStore(repo)
    key = store.save(batch(), recorded_at=ANALYSIS_TIME)
    repo._connection.execute("UPDATE core_api_snapshots SET payload_json = replace(payload_json, 'LENS_POLICY_NOT_APPROVED', 'ALTERED') WHERE snapshot_id = ?", (key,))
    repo._connection.commit()
    with pytest.raises(ValueError, match="integrity"):
        store.get(key)
    repo.close()
