"""U17 handoff tests for the acquisition-only NSE delivery adapter."""
from __future__ import annotations

from datetime import UTC, date, datetime
from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace

from app.data_operations.files import DeliveryAcquisitionManifest, FileStagingLayout, NodeDeliveryAcquirer, NseDeliveryStagingJob
from app.data_operations.models import EvidenceDataFamily, EvidenceRefreshMode, EvidenceRefreshRequest, EvidenceRefreshStatus
from app.market_data.nse_delivery import NseDeliveryReportImporter, NseDeliveryStore
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository


T = datetime(2026, 8, 29, 12, tzinfo=UTC)
SESSION = date(2026, 8, 28)
FILENAME = "sec_bhavdata_full_28082026.csv"
SOURCE_URL = f"https://archives.nseindia.com/products/content/{FILENAME}"
VALID_CSV = "SYMBOL,SERIES,DATE1,TOTTRDQTY,DELIV_QTY,DELIV_PER\nALPHA,EQ,28-Aug-2026,100,50,50\n"


class Acquirer:
    def __init__(self, manifest: DeliveryAcquisitionManifest) -> None:
        self.manifest = manifest
        self.sessions: list[date] = []

    def acquire(self, requested_session: date) -> DeliveryAcquisitionManifest:
        self.sessions.append(requested_session)
        return self.manifest


def _request() -> EvidenceRefreshRequest:
    return EvidenceRefreshRequest("run-delivery", EvidenceDataFamily.DELIVERY, EvidenceRefreshMode.INCREMENTAL, T, T, None, 0)


def _manifest(path: Path, *, status: str = "ACQUIRED") -> DeliveryAcquisitionManifest:
    content = path.read_bytes()
    return DeliveryAcquisitionManifest(
        SESSION, FILENAME, SOURCE_URL, T, len(content), sha256(content).hexdigest(),
        None, path, status,
    )


def _job(tmp_path: Path, manifest: DeliveryAcquisitionManifest) -> tuple[NseDeliveryStagingJob, FileStagingLayout, Acquirer, NseDeliveryStore]:
    layout = FileStagingLayout(tmp_path / "data")
    layout.ensure("delivery")
    store = NseDeliveryStore(SQLiteCoreApiSnapshotRepository(tmp_path / "core.sqlite"))
    acquirer = Acquirer(manifest)
    job = NseDeliveryStagingJob(
        NseDeliveryReportImporter(store),
        {"ALPHA": ("NSE:ALPHA", "INE000A01001")},
        layout,
        acquirer=acquirer,
        session_selector=lambda _request: SESSION,
    )
    return job, layout, acquirer, store


def test_acquired_official_bytes_flow_only_through_existing_importer_and_archive(tmp_path: Path) -> None:
    staged = tmp_path / "data" / "incoming" / "delivery" / FILENAME
    staged.parent.mkdir(parents=True)
    staged.write_text(VALID_CSV, encoding="utf-8")
    manifest = _manifest(staged)
    job, layout, acquirer, store = _job(tmp_path, manifest)

    result = job.refresh(_request())

    assert result.status is EvidenceRefreshStatus.COMPLETE
    assert result.accepted_count == 1
    assert result.source_references == (SOURCE_URL, "nse-delivery:" + manifest.sha256[:24])
    assert acquirer.sessions == [SESSION]
    assert store.latest("NSE:ALPHA", as_of=T) is not None
    assert not tuple(layout.incoming("delivery").glob("*.csv"))
    assert len(tuple(layout.archive("delivery").glob("*.csv"))) == 1

    repeated = layout.incoming("delivery") / FILENAME
    repeated.write_text(VALID_CSV, encoding="utf-8")
    acquirer.manifest = _manifest(repeated)
    rerun = job.refresh(_request())

    assert rerun.status is EvidenceRefreshStatus.NO_CHANGE
    assert rerun.accepted_count == 0 and rerun.duplicate_count == 1 and rerun.conflict_count == 0
    assert len(tuple(layout.archive("delivery").glob("*.csv"))) == 1


def test_malformed_acquired_bytes_are_quarantined_without_canonical_evidence(tmp_path: Path) -> None:
    staged = tmp_path / "data" / "incoming" / "delivery" / FILENAME
    staged.parent.mkdir(parents=True)
    staged.write_text("SYMBOL,SERIES\nALPHA,EQ\n", encoding="utf-8")
    job, layout, acquirer, store = _job(tmp_path, _manifest(staged))

    result = job.refresh(_request())

    assert result.status is EvidenceRefreshStatus.INVALID_EVIDENCE
    assert result.accepted_count == 0
    assert acquirer.sessions == [SESSION]
    assert store.latest("NSE:ALPHA", as_of=T) is None
    assert not tuple(layout.incoming("delivery").glob("*.csv"))
    assert len(tuple(layout.quarantine("delivery").glob("*.csv"))) == 1


def test_not_yet_available_acquisition_leaves_importer_and_staging_untouched(tmp_path: Path) -> None:
    placeholder = tmp_path / "placeholder.csv"
    placeholder.write_text("unused", encoding="utf-8")
    manifest = _manifest(placeholder, status="NOT_YET_AVAILABLE")
    job, layout, acquirer, store = _job(tmp_path, manifest)

    result = job.refresh(_request())

    assert result.status is EvidenceRefreshStatus.NO_CHANGE
    assert result.warnings == ("DELIVERY_NOT_YET_AVAILABLE",)
    assert acquirer.sessions == [SESSION]
    assert store.latest("NSE:ALPHA", as_of=T) is None
    assert not tuple(layout.incoming("delivery").glob("*.csv"))


def test_python_bridge_invokes_only_the_node_cli_with_an_explicit_session(monkeypatch, tmp_path: Path) -> None:
    script = tmp_path / "automation" / "nse_data_bot" / "src" / "delivery_acquirer.ts"
    script.parent.mkdir(parents=True)
    script.write_text("// fixture", encoding="utf-8")
    staged = tmp_path / "data" / "incoming" / "delivery" / FILENAME
    staged.parent.mkdir(parents=True)
    staged.write_text(VALID_CSV, encoding="utf-8")
    payload = {
        "family": "DELIVERY", "requestedSession": SESSION.isoformat(), "source": "NSE_OFFICIAL",
        "sourceFilename": FILENAME, "sourceUrl": SOURCE_URL, "acquiredAt": T.isoformat(),
        "byteCount": staged.stat().st_size, "sha256": sha256(staged.read_bytes()).hexdigest(),
        "temporaryPath": None, "stagedPath": str(staged), "status": "ACQUIRED", "errorCode": None,
    }
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(stdout=json.dumps(payload), returncode=0)

    monkeypatch.setattr("app.data_operations.files.subprocess.run", fake_run)
    result = NodeDeliveryAcquirer(tmp_path).acquire(SESSION)

    assert result.status == "ACQUIRED" and result.staged_path == staged.resolve()
    assert calls[0][0][0:3] == ("node", "--experimental-strip-types", str(script))
    assert calls[0][0][3:6] == ("acquire-delivery", "--date", SESSION.isoformat())
