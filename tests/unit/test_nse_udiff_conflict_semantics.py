from dataclasses import FrozenInstanceError, replace
from datetime import timedelta, timezone
import inspect
import json
import sqlite3

import pytest

from app.market_data.nse_udiff_conflict_semantics import (
    NseUdiffConflictClass as Kind, classify_source_rows, source_row_evidence,
)
from app.market_data.nse_udiff_daily_history import _artifact_from_bytes
from scripts.audit_nse_udiff_identity_boundary import open_readonly
from tests.unit.test_nse_udiff_daily_history import archive, result, row, backfill, Source


def evidence(*rows):
    artifact = _artifact_from_bytes("nse-udiff-acquisition:test", result(archive(rows)))
    return tuple(source_row_evidence(artifact, i) for i in range(len(rows)))


def test_identity_replay_and_serialization_are_deterministic():
    a, = evidence(row())
    b, = evidence(dict(reversed(tuple(row().items()))))
    assert a.source_row_id == b.source_row_id
    artifact = _artifact_from_bytes("nse-udiff-acquisition:test", result(archive()))
    assert source_row_evidence(artifact, 0).to_dict() == source_row_evidence(artifact, 0).to_dict()
    assert json.loads(json.dumps(a.to_dict(), sort_keys=True))["fingerprint"] == a.fingerprint
    with pytest.raises(FrozenInstanceError):
        a.row_index = 4


def test_content_and_source_identity_are_not_circular_or_ordinal_dependent():
    a, b = evidence(row(), row())
    assert a.source_row_id == b.source_row_id
    assert a.fingerprint != b.fingerprint
    assert classify_source_rows(a, b) is Kind.DUPLICATE_EQUIVALENT
    c, = evidence({**row(), "ClsPric": "101"})
    assert c.source_row_id == a.source_row_id
    assert c.fingerprint != a.fingerprint


@pytest.mark.parametrize("change,expected", [
    ({"SctySrs": "BL", "FinInstrmId": "777"}, Kind.DISTINCT_SERIES),
    ({"SctySrs": "T0"}, Kind.DISTINCT_SERIES),
    ({"SctySrs": "BE"}, Kind.DISTINCT_SERIES),
    ({"FinInstrmId": "777"}, Kind.DISTINCT_SOURCE_SECURITY_IDENTITY),
    ({"SsnId": "S1"}, Kind.DISTINCT_SESSION),
    ({"ISIN": "INE000B01001"}, Kind.HISTORICAL_IDENTITY_DISCONTINUITY),
    ({"TckrSymb": "HISTORICAL"}, Kind.HISTORICAL_IDENTITY_DISCONTINUITY),
    ({"ClsPric": "101"}, Kind.TRUE_SOURCE_VALUE_CONFLICT),
    ({"Rmks": "different metadata"}, Kind.UNRESOLVED),
    ({"OpnPric": "100.00"}, Kind.UNRESOLVED),
    ({"OpnPric": "NaN"}, Kind.UNRESOLVED),
    ({"OpnPric": "invalid"}, Kind.UNRESOLVED),
])
def test_classification_is_symmetric_without_winner(change, expected):
    a, b = evidence(row(), {**row(), **change})
    assert classify_source_rows(a, b) is expected
    assert classify_source_rows(b, a) is expected
    if any(k in change for k in ("ISIN", "SctySrs", "FinInstrmId", "TckrSymb", "SsnId")):
        assert a.source_row_id != b.source_row_id


def test_historical_symbol_exact_isin_and_series_are_not_current_remapped():
    a, = evidence(row(symbol="OLDNAME"))
    assert dict(a.fields)["TckrSymb"] == "OLDNAME"
    assert dict(a.fields)["ISIN"] == row()["ISIN"]
    assert dict(a.fields)["SctySrs"] == "EQ"
    assert "canonical_instrument_id" not in a.to_dict()
    assert "effective_from" not in a.to_dict()  # no manufactured continuous interval


def test_timezone_normalization_does_not_change_evidence():
    a, = evidence(row())
    b = replace(a, observed_at=a.observed_at.astimezone(timezone(timedelta(hours=5, minutes=30))))
    assert a.to_dict() == b.to_dict()
    assert a.source_row_id == b.source_row_id


@pytest.mark.parametrize("change", [
    {"fingerprint": "sha256:" + "0" * 64},
    {"row_index": -1}, {"source_url": "https://example.com/"},
    {"content_sha256": ""}, {"artifact_fingerprint": ""},
])
def test_tampered_lineage_is_rejected(change):
    a, = evidence(row())
    with pytest.raises(ValueError, match="NSE_UDIFF_SOURCE_ROW"):
        replace(a, **change)


def test_duplicate_or_mutable_fields_rejected():
    a, = evidence(row())
    for fields in (list(a.fields), a.fields + (a.fields[0],)):
        with pytest.raises(ValueError, match="SCHEMA_INVALID"):
            replace(a, fields=fields)


@pytest.mark.parametrize("change", [{"ISIN": "BAD"}, {"FinInstrmId": ""}, {"SctySrs": " "}])
def test_malformed_source_identity_rejected(change):
    with pytest.raises(ValueError, match="IDENTITY_INVALID"):
        evidence({**row(), **change})


def test_archive_tampering_rejected_before_row_projection():
    artifact = _artifact_from_bytes("nse-udiff-acquisition:test", result(archive()))
    object.__setattr__(artifact, "content_sha256", "0" * 64)
    with pytest.raises(ValueError, match="ARTIFACT_INVALID"):
        source_row_evidence(artifact, 0)


def test_same_key_different_archives_never_infer_revision_precedence():
    a, = evidence(row())
    b, = evidence({**row(), "ClsPric": "101"})
    assert classify_source_rows(a, b) is Kind.TRUE_SOURCE_VALUE_CONFLICT
    assert classify_source_rows(b, a) is Kind.TRUE_SOURCE_VALUE_CONFLICT


def test_existing_storage_defect_is_reproduced_without_repair(tmp_path):
    # Regression witness, not approval of this behaviour. Replacing the primary
    # key alone must not be mistaken for a complete series-aware read repair.
    block = {**row(), "SctySrs": "BL", "FinInstrmId": "777", "ClsPric": "101"}
    service, store, _ = backfill(tmp_path, Source(result(archive((block, row())))))
    report = service.run()
    assert report.receipts[0].conflicts == 1
    stored = store._connection.execute("SELECT warnings_json FROM historical_bars").fetchone()[0]
    assert "NSE_UDIFF_SERIES:BL" in stored
    assert len(store.list_conflict_artifacts()) == 1
    service.run()
    assert len(store.list_conflict_artifacts()) == 1
    assert store._connection.execute("SELECT count(*) FROM historical_bars").fetchone()[0] == 1
    store.close()


def test_audit_connection_cannot_write_or_create_database(tmp_path):
    missing = tmp_path / "missing.db"
    with pytest.raises(sqlite3.OperationalError):
        open_readonly(missing)
    assert not missing.exists()
    db = tmp_path / "isolated.db"
    with sqlite3.connect(db) as c:
        c.execute("CREATE TABLE proof (id INTEGER)")
    c = open_readonly(db)
    try:
        with pytest.raises(sqlite3.OperationalError):
            c.execute("INSERT INTO proof VALUES (1)")
    finally:
        c.close()


def test_no_calculation_selection_or_execution_dependency():
    import app.market_data.nse_udiff_conflict_semantics as module
    source = inspect.getsource(module)
    for name in ("datetime.now(", "time.time(", "app.portfolio", "app.execution",
                 "app.broker", "app.signals", "app.api", "upstox", "sqlite3", "requests."):
        assert name not in source
