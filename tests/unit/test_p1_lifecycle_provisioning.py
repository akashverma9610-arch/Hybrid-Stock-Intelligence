"""Isolated SQLite provisioning proof; these fixtures are not live emissions."""
from contextlib import closing
from pathlib import Path
import sqlite3

import pytest

from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository
from app.storage.sqlite_p1_lifecycle_migration import provision, TABLES, FAMILY
from app.storage.readonly_p1_signal_lifecycle import ReadOnlyP1SignalLifecycleReader
from tests.unit.test_p1_signal_lifecycle_runtime import T, I


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "canonical.db"
    repo = SQLiteCoreApiSnapshotRepository(path)
    repo.close()
    return path, tmp_path / "backup.db"


def test_provision_is_additive_backed_up_idempotent_and_not_activation(database):
    path, backup = database
    original = path.read_bytes()
    result = provision(path, backup)
    assert result['status'] == 'PROVISIONED_NOT_ACTIVE'
    assert result['prospective_start'] is None
    with closing(sqlite3.connect(backup)) as old, closing(sqlite3.connect(path)) as new:
        old_schema = dict(old.execute("SELECT name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"))
        new_schema = dict(new.execute("SELECT name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"))
        assert {k: v for k, v in new_schema.items() if k not in TABLES} == old_schema
        assert new.execute('SELECT count(*) FROM core_api_snapshots').fetchone() == (0,)
        assert new.execute('PRAGMA integrity_check').fetchone() == ('ok',)
        assert new.execute('PRAGMA foreign_key_check').fetchall() == []
    after = path.read_bytes()
    assert after != original
    assert provision(path, backup)['status'] == 'ALREADY_PROVISIONED'
    assert path.read_bytes() == after
    reader = ReadOnlyP1SignalLifecycleReader(path)
    try:
        assert reader.read(I, as_of=T).last_transition is None
    finally:
        reader.close()


def test_existing_backup_never_overwritten(database):
    path, backup = database
    backup.write_bytes(b'keep')
    before = path.read_bytes()
    with pytest.raises(ValueError, match='BACKUP_EXISTS'):
        provision(path, backup)
    assert backup.read_bytes() == b'keep'
    assert path.read_bytes() == before


@pytest.mark.parametrize('partial', [True, False])
def test_partial_or_wrong_schema_rejected_not_repaired(database, partial):
    path, backup = database
    with closing(sqlite3.connect(path)) as connection:
        connection.execute('CREATE TABLE p1_signal_lifecycle_heads (wrong TEXT)')
        if not partial:
            connection.execute('CREATE TABLE p1_signal_lifecycle_batch_index (wrong TEXT)')
    before = path.read_bytes()
    with pytest.raises(ValueError, match='SCHEMA_CONFLICT'):
        provision(path, backup)
    assert path.read_bytes() == before
    assert not backup.exists()


def test_existing_history_not_relabelled_or_backfilled(database):
    path, backup = database
    with closing(sqlite3.connect(path)) as connection:
        connection.execute('INSERT INTO core_api_snapshots VALUES (?,?,?,?,?,?,?)',
                           ('old', FAMILY, 'v1', 'test', 'fp', T.isoformat(), '{}'))
        connection.commit()
    before = path.read_bytes()
    with pytest.raises(ValueError, match='EXISTING_HISTORY_REQUIRES_REVIEW'):
        provision(path, backup)
    assert path.read_bytes() == before
    assert not backup.exists()


def test_missing_database_not_created(tmp_path):
    path = tmp_path / 'absent.db'
    with pytest.raises(ValueError, match='DATABASE_REQUIRED'):
        provision(path, tmp_path / 'backup.db')
    assert not path.exists()


def test_foreign_key_failure_rejected_before_backup(database):
    path, backup = database
    with closing(sqlite3.connect(path)) as connection:
        connection.execute('CREATE TABLE child (id TEXT REFERENCES core_api_snapshots(snapshot_id))')
        connection.execute("INSERT INTO child VALUES ('missing')")
        connection.commit()
    with pytest.raises(ValueError, match='FOREIGN_KEY_FAILED'):
        provision(path, backup)
    assert not backup.exists()


def test_migration_has_no_producer_or_private_dependency():
    import ast
    import app.storage.sqlite_p1_lifecycle_migration as module
    tree = ast.parse(Path(module.__file__).read_text(encoding='utf-8'))
    imported = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert imported == {'contextlib', 'pathlib', 'app.storage.sqlite_p1_signal_lifecycle'}
    assert not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                   and n.func.attr in {'submit', 'evaluate', 'save_snapshot', 'now', 'utcnow'}
                   for n in ast.walk(tree))


def test_failed_ddl_rolls_back_but_retains_verified_backup(database, monkeypatch):
    import app.storage.sqlite_p1_lifecycle_migration as module
    path, backup = database
    with closing(sqlite3.connect(path)) as connection:
        before = module._objects(connection)
    monkeypatch.setattr(module, 'SCHEMA', (module.SCHEMA[0], 'INVALID SQL'))
    with pytest.raises(sqlite3.OperationalError):
        provision(path, backup)
    assert backup.is_file()
    with closing(sqlite3.connect(path)) as connection, closing(sqlite3.connect(backup)) as archive:
        assert module._objects(connection) == before == module._objects(archive)
        assert archive.execute('PRAGMA integrity_check').fetchone() == ('ok',)
