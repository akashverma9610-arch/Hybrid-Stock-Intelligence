from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
import gzip

import pytest

from app.historical.nse_mii_security_master import (
    PROSPECTIVE_CAPTURE_CONTRACT_VERSION,
    NseMiiCurrentMasterCaptureReceipt,
    NseMiiSecurityMasterError,
    NseMiiSecurityMasterEvidenceStore,
    NseMiiSecurityMasterHttpResponse,
    extract_nse_mii_security_master,
    nse_mii_security_master_url,
)
from app.historical.guard import manifest_fingerprint
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository
from scripts.collect_nse_execution_master_current import latest_completed_nse_session
from scripts.collect_gate3_surveillance import read_identity_inputs
from tests.unit.test_earnings_schedule_identity import master, snap


T = datetime(2026, 9, 13, 10, tzinfo=UTC)
D = date(2026, 9, 11)
HEADERS = (
    "FinInstrmId,TckrSymb,SctySrs,FinInstrmNm,ISIN,SctyStsNrmlMkt,"
    "ListgDt,RmvlDt,FinInstrmTp,SctyTp\n"
)


def _body() -> bytes:
    return gzip.compress((HEADERS + "\n".join((
        "100,ALPHA,EQ,Alpha Ltd,INE000A01001,6,100,0,EQ,EQUITY",
        "101,BETA,BE,Beta Ltd,INE000A01002,6,100,0,EQ,EQUITY",
        "102,INVALID,EQ,Invalid Ltd,INVALID,6,100,0,EQ,EQUITY",
    )) + "\n").encode())


def _extraction(*, observed_at: datetime = T):
    body = _body()
    return extract_nse_mii_security_master(NseMiiSecurityMasterHttpResponse(
        requested_date=D, source_reference=nse_mii_security_master_url(D), content_type="application/x-gzip",
        body=body, document_observed_at=observed_at, declared_length=len(body), transfer_complete=True,
    ), contract_version=PROSPECTIVE_CAPTURE_CONTRACT_VERSION)


def test_complete_current_capture_is_distinct_from_a_prior_partial_checkpoint_and_counts_every_stage(tmp_path):
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "master.sqlite")
    store = NseMiiSecurityMasterEvidenceStore(repository)
    legacy = extract_nse_mii_security_master(NseMiiSecurityMasterHttpResponse(
        D, nse_mii_security_master_url(D), "application/x-gzip", _body(), T,
    ))
    store.save_rows(legacy, offset=0, limit=1)
    current = _extraction(observed_at=T + timedelta(minutes=1))
    receipt = store.save_complete_current_capture(current, page_size=1)

    assert receipt.completeness.value == "COMPLETE"
    assert (receipt.source_declared_rows, receipt.raw_captured_rows, receipt.parsed_rows) == (None, 3, 3)
    assert (receipt.retained_rows, receipt.canonical_eligible_rows, receipt.identity_ineligible_rows) == (2, 2, 1)
    assert (receipt.structural_rejected_rows, receipt.pagination_state, receipt.transfer_complete) == (0, "SINGLE_FILE_NO_PAGINATION", True)
    assert legacy.snapshot.snapshot_id != current.snapshot.snapshot_id
    assert store.snapshot(legacy.snapshot.snapshot_id) == legacy.snapshot
    assert sum(store.row(row.row_id) is not None for row in legacy.rows) == 1
    assert store.reopen_complete_current_capture(receipt.receipt_id) == receipt
    repository.close()


def test_replay_is_network_free_and_preserves_first_observed_and_fingerprint(tmp_path):
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "master.sqlite")
    store = NseMiiSecurityMasterEvidenceStore(repository)
    first = store.save_complete_current_capture(_extraction(), page_size=1)
    replay = store.save_complete_current_capture(_extraction(), page_size=1)

    assert first == replay
    assert replay.first_observed_at == T
    assert replay.raw_file_fingerprint == first.raw_file_fingerprint
    repository.close()


def test_prospective_snapshot_identity_is_capture_specific_but_legacy_identity_is_not():
    one = _extraction(observed_at=T)
    two = _extraction(observed_at=T + timedelta(minutes=1))
    assert one.snapshot.snapshot_id != two.snapshot.snapshot_id
    legacy_one = extract_nse_mii_security_master(NseMiiSecurityMasterHttpResponse(D, nse_mii_security_master_url(D), "application/x-gzip", _body(), T))
    legacy_two = extract_nse_mii_security_master(NseMiiSecurityMasterHttpResponse(D, nse_mii_security_master_url(D), "application/x-gzip", _body(), T + timedelta(minutes=1)))
    assert legacy_one.snapshot.snapshot_id == legacy_two.snapshot.snapshot_id


def test_legacy_v1_extraction_fingerprint_and_counter_surface_are_unchanged():
    legacy = extract_nse_mii_security_master(NseMiiSecurityMasterHttpResponse(
        D, nse_mii_security_master_url(D), "application/x-gzip", _body(), T,
    ))
    assert (
        legacy.raw_captured_rows, legacy.parsed_rows, legacy.structural_rejected_rows,
        legacy.bytes_received, legacy.declared_length, legacy.transfer_complete,
    ) == (None, None, None, None, None, None)
    assert legacy.fingerprint == "sha256:" + manifest_fingerprint(
        snapshot_id=legacy.snapshot.snapshot_id,
        row_ids=tuple(row.row_id for row in legacy.rows),
        invalid_identity_rows=legacy.invalid_identity_rows,
    )


def test_transport_length_mismatch_and_partial_transfer_cannot_become_a_capture():
    with pytest.raises(NseMiiSecurityMasterError, match="RESPONSE_INVALID"):
        NseMiiSecurityMasterHttpResponse(D, nse_mii_security_master_url(D), "application/x-gzip", _body(), T, 1, True)
    with pytest.raises(NseMiiSecurityMasterError, match="RESPONSE_INVALID"):
        NseMiiSecurityMasterHttpResponse(D, nse_mii_security_master_url(D), "application/x-gzip", _body(), T, None, False)


def test_latest_completed_session_uses_existing_calendar_and_never_assumes_weekend_or_holiday_is_a_session():
    assert latest_completed_nse_session(T) == D


def test_current_capture_receipt_rejects_tampered_lineage_and_count_values(tmp_path):
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "master.sqlite")
    store = NseMiiSecurityMasterEvidenceStore(repository)
    receipt = store.save_complete_current_capture(_extraction(), page_size=1)
    with pytest.raises(NseMiiSecurityMasterError, match="RECEIPT_INVALID"):
        NseMiiCurrentMasterCaptureReceipt(
            snapshot_id=receipt.snapshot_id, snapshot_fingerprint=receipt.snapshot_fingerprint,
            report_date=receipt.report_date, source_reference=receipt.source_reference,
            raw_file_fingerprint=receipt.raw_file_fingerprint, extraction_fingerprint=receipt.extraction_fingerprint,
            source_declared_rows=None,
            raw_captured_rows=receipt.raw_captured_rows, parsed_rows=receipt.parsed_rows,
            retained_rows=receipt.retained_rows - 1, canonical_eligible_rows=receipt.canonical_eligible_rows,
            structural_rejected_rows=receipt.structural_rejected_rows,
            identity_ineligible_rows=receipt.identity_ineligible_rows, bytes_received=receipt.bytes_received,
            declared_length=receipt.declared_length, transfer_complete=True,
            pagination_state=receipt.pagination_state, first_observed_at=receipt.first_observed_at,
            completeness=receipt.completeness, fingerprint=receipt.fingerprint,
        )
    repository.close()


def test_gate3_master_reader_prefers_complete_prospective_capture_over_same_date_partial_legacy_checkpoint(tmp_path):
    database = tmp_path / "master.sqlite"
    repository = SQLiteCoreApiSnapshotRepository(database)
    store = NseMiiSecurityMasterEvidenceStore(repository)
    repository.save_snapshot(snap(master(data_as_of=T - timedelta(days=1))))
    legacy = extract_nse_mii_security_master(NseMiiSecurityMasterHttpResponse(
        D, nse_mii_security_master_url(D), "application/x-gzip", _body(), T,
    ))
    store.save_rows(legacy, offset=0, limit=1)
    current = _extraction(observed_at=T + timedelta(minutes=1))
    receipt = store.save_complete_current_capture(current, page_size=1)
    repository.close()

    _, snapshots, continuity = read_identity_inputs(database, T + timedelta(hours=1))
    assert snapshots[0].payload.snapshot_id == receipt.snapshot_id
    assert len(snapshots) == 1 + receipt.retained_rows
    assert continuity == "CURRENT_COMPLETE_PROSPECTIVE_MASTER_DATE_LEVEL_ONLY"


def test_current_capture_module_has_no_execution_or_identity_promotion_dependencies():
    import app.historical.nse_mii_security_master as module

    source = open(module.__file__, encoding="utf-8").read()
    collector_source = open("scripts/collect_nse_execution_master_current.py", encoding="utf-8").read()
    selector_source = open("scripts/collect_gate3_surveillance.py", encoding="utf-8").read()
    for forbidden in ("app.signals", "app.portfolio", "app.broker", "app.orders", "app.api", "app.runtime", "app.gates", "place_order"):
        assert forbidden not in source
        assert forbidden not in collector_source
        assert forbidden not in selector_source
