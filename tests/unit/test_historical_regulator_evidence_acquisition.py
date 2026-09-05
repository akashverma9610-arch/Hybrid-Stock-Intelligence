from __future__ import annotations

import ast
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.historical import historical_regulator_evidence_acquisition as acquisition
from app.historical import regulator_company_type_evidence as regulator
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository


OBSERVED = datetime(2026, 9, 5, 10, tzinfo=UTC)
CIN = "L65190GJ1994PLC021012"


def _bank_table() -> bytes:
    return b"<table><tr><td>Private Sector Banks</td></tr><tr><td>Sr. No.</td><td>Name of the Bank</td></tr><tr><td>1</td><td>Exact Bank Limited</td></tr></table>"


def _xlsx(tmp_path: Path) -> bytes:
    from openpyxl import Workbook

    book = Workbook(); sheet = book.active
    sheet.append(["Name of the Company", "Category", "CoR No", "CIN", "Layer"])
    sheet.append(["Exact NBFC Limited", "ICC", "N-1", CIN, "Upper"])
    path = tmp_path / "nbfc.xlsx"; book.save(path)
    return path.read_bytes()


def _bridge() -> SimpleNamespace:
    return SimpleNamespace(
        cin=CIN, isin="INE090A01021", observation_id="issuer:exact", later_session_date=date(2024, 8, 1),
        anchor_known_ats=(datetime(2024, 8, 1, tzinfo=UTC),),
    )


def test_historical_rbi_bank_table_preserves_release_knownness_and_subtype():
    batch = acquisition.rbi_trend_progress_bank_batch(
        payload=_bank_table(), observed_at=OBSERVED, source_as_of_date=date(2023, 3, 31),
        source_known_on=acquisition.RBI_TREND_PROGRESS_2022_23_RELEASED_ON,
    )
    item = batch.evidence[0]
    assert (item.legal_name, item.regulator_subtype, item.source_as_of_date, item.source_known_on) == (
        "Exact Bank Limited", "Private Sector Banks", date(2023, 3, 31), date(2023, 12, 27),
    )


def test_rbi_narrative_mention_is_not_a_bank_row():
    with pytest.raises(regulator.RegulatorCompanyTypeEvidenceError, match="NO_SUPPORTED_ENTITY_ROWS"):
        acquisition.rbi_trend_progress_bank_batch(
            payload=b"<p>Exact Bank Limited is mentioned in the annual report narrative.</p>", observed_at=OBSERVED,
            source_as_of_date=date(2023, 3, 31), source_known_on=date(2023, 12, 27),
        )


def test_exact_nbfc_cin_snapshot_preserves_vintage_and_does_not_leak_to_february(tmp_path):
    batch = regulator.rbi_nbfc_arc_batch(
        payload=_xlsx(tmp_path), source=regulator.RegulatorEvidenceSource.RBI_REGISTERED_NBFC_ARC,
        observed_at=OBSERVED, source_as_of_date=date(2024, 6, 30), source_known_on=date(2024, 7, 31),
        source_reference="https://rbi.example/nbfc-june-2024.xlsx",
    )
    item = batch.evidence[0]
    february = regulator.audit_exact_regulator_issuer_links(
        evidence=(item,), active_bridges=(_bridge(),), as_of=datetime(2024, 2, 5, 23, 59, tzinfo=UTC),
    )[0]
    august = regulator.audit_exact_regulator_issuer_links(
        evidence=(item,), active_bridges=(_bridge(),), as_of=datetime(2024, 8, 2, 23, 59, tzinfo=UTC),
    )[0]
    assert (item.cin, item.regulator_subtype, item.source_as_of_date) == (CIN, "ICC", date(2024, 6, 30))
    assert not february.pit_eligible and february.reason == "SOURCE_KNOWN_AFTER_AS_OF"
    assert august.linkage_status is regulator.IssuerLinkageStatus.EXACT_CIN_LINKED


def test_cancellation_press_release_preserves_cor_dates_without_creating_registration_interval():
    payload = b"""<table><tr><th>Sr. No.</th><th>Name of the Company</th><th>Registered Office Address</th><th>CoR No.</th><th>CoR Issued On</th><th>Cancellation Order Date</th></tr><tr><td>1</td><td>Exact Cancelled NBFC Ltd.</td><td>Official Address</td><td>N-10.00001</td><td>May 18, 2018</td><td>January 17, 2024</td></tr></table>"""
    batch = acquisition.rbi_nbfc_cancellation_press_release_batch(
        payload=payload, observed_at=OBSERVED, published_on=date(2024, 2, 9), source_reference="https://rbi.example/cancel",
    )
    item = batch.evidence[0]
    assert (item.regulator_registration_id, item.cor_issued_on, item.cancellation_on, item.effective_on) == (
        "N-10.00001", date(2018, 5, 18), date(2024, 1, 17), None,
    )
    assert item.entity_status is regulator.RegulatorEntityStatus.CANCELLED


def test_historical_irdai_annexure_extracts_life_general_health_and_rejects_specialists(monkeypatch):
    lines = (
        (110.0, "LEFT", "Life Insurers"), (120.0, "LEFT", "Public Sector"),
        (130.0, "LEFT", "1. Exact Life Insurance Co. Ltd."),
        (110.0, "RIGHT", "Non-Life Insurers"), (120.0, "RIGHT", "Private Sector"),
        (130.0, "RIGHT", "1. Exact General Insurance Co. Ltd."),
        (140.0, "RIGHT", "Specialized Insurers (Public Sector)"),
        (150.0, "RIGHT", "1. Excluded Specialist Ltd."),
        (160.0, "RIGHT", "Standalone Health Insurers (Private Sector)"),
        (170.0, "RIGHT", "1. Exact Health Insurance Co. Ltd."),
    )
    monkeypatch.setattr(acquisition, "_irdai_annexure_one_lines", lambda _payload: (339, lines))
    batches = acquisition.irdai_annual_report_2022_23_insurer_batches(payload=b"official-pdf", observed_at=OBSERVED)
    by_source = {batch.artifact.source: batch for batch in batches}
    assert [item.legal_name for item in by_source[regulator.RegulatorEvidenceSource.IRDAI_LIFE_INSURERS].evidence] == ["Exact Life Insurance Co. Ltd."]
    assert [item.legal_name for item in by_source[regulator.RegulatorEvidenceSource.IRDAI_GENERAL_INSURERS].evidence] == ["Exact General Insurance Co. Ltd."]
    health = by_source[regulator.RegulatorEvidenceSource.IRDAI_HEALTH_INSURERS].evidence[0]
    assert health.legal_name == "Exact Health Insurance Co. Ltd."
    assert all(item.source_known_on == date(2023, 12, 27) for batch in batches for item in batch.evidence)
    assert all("Specialist" not in item.legal_name for batch in batches for item in batch.evidence)


def test_source_known_date_makes_historical_publication_pit_eligible_without_rewriting_current_sources():
    historical = acquisition.rbi_trend_progress_bank_batch(
        payload=_bank_table(), observed_at=OBSERVED, source_as_of_date=date(2023, 3, 31), source_known_on=date(2023, 12, 27),
    ).evidence[0]
    current = regulator.rbi_scheduled_bank_batch(
        payload=_bank_table(), observed_at=OBSERVED, source_as_of_date=date(2023, 3, 31),
    ).evidence[0]
    as_of = datetime(2024, 2, 5, 23, 59, tzinfo=UTC)
    assert regulator._evidence_pit_eligible(historical, as_of)
    assert not regulator._evidence_pit_eligible(current, as_of)


def test_new_optional_historical_fields_preserve_legacy_current_artifact_and_evidence_identity():
    batch = regulator.rbi_scheduled_bank_batch(
        payload=_bank_table(), observed_at=OBSERVED, source_as_of_date=date(2026, 8, 31),
    )
    artifact = batch.artifact
    legacy_artifact_identity = {
        "source": artifact.source.value, "source_reference": artifact.source_reference,
        "source_fingerprint": artifact.source_fingerprint, "source_as_of_date": "2026-08-31",
        "temporal_status": artifact.temporal_status.value,
    }
    assert artifact.source_artifact_id == "regulator-source:" + regulator._hash(legacy_artifact_identity)[7:39]
    item = batch.evidence[0]
    legacy_record = {
        "source_artifact": artifact.source_fingerprint, "record": item.source_record_id, "legal_name": item.legal_name,
        "registration": None, "cin": None, "subtype": item.regulator_subtype, "address": None,
        "effective": None, "cancelled": None,
    }
    assert item.source_record_fingerprint == regulator._hash(legacy_record)
    assert item.source_known_on is item.cor_issued_on is item.event_reason is None


def test_historical_and_current_vintages_persist_without_overwrite(tmp_path):
    store = regulator.RegulatorCompanyTypeEvidenceStore(SQLiteCoreApiSnapshotRepository(tmp_path / "evidence.sqlite"))
    historical = acquisition.rbi_trend_progress_bank_batch(
        payload=_bank_table(), observed_at=OBSERVED, source_as_of_date=date(2023, 3, 31), source_known_on=date(2023, 12, 27),
    )
    current = regulator.rbi_scheduled_bank_batch(
        payload=_bank_table(), observed_at=OBSERVED, source_as_of_date=date(2026, 8, 31),
    )
    assert regulator.persist_regulator_evidence(store=store, batch=historical) == (1, 0, 1, 0)
    assert regulator.persist_regulator_evidence(store=store, batch=current) == (1, 0, 1, 0)
    assert len(store.artifacts()) == len(store.evidence()) == 2


def test_replay_is_idempotent_and_allows_no_company_type_or_execution_dependency(monkeypatch, tmp_path):
    lines = (
        (110.0, "LEFT", "Life Insurers"), (120.0, "LEFT", "Public Sector"),
        (130.0, "LEFT", "1. Exact Life Insurance Co. Ltd."),
        (110.0, "RIGHT", "Non-Life Insurers"), (120.0, "RIGHT", "Public Sector"),
        (130.0, "RIGHT", "1. Exact General Insurance Co. Ltd."),
        (160.0, "RIGHT", "Standalone Health Insurers (Private Sector)"),
        (170.0, "RIGHT", "1. Exact Health Insurance Co. Ltd."),
    )
    monkeypatch.setattr(acquisition, "_irdai_annexure_one_lines", lambda _payload: (339, lines))
    batches = acquisition.irdai_annual_report_2022_23_insurer_batches(payload=b"official-pdf", observed_at=OBSERVED)
    store = regulator.RegulatorCompanyTypeEvidenceStore(SQLiteCoreApiSnapshotRepository(tmp_path / "evidence.sqlite"))
    assert [regulator.persist_regulator_evidence(store=store, batch=item) for item in batches] == [(1, 0, 1, 0)] * 3
    assert [regulator.persist_regulator_evidence(store=store, batch=item) for item in batches] == [(0, 1, 0, 1)] * 3
    source = Path(acquisition.__file__).read_text(encoding="utf-8")
    imports = [node.module or "" for node in ast.walk(ast.parse(source)) if isinstance(node, ast.ImportFrom)]
    forbidden = ("company_type", "compounder", "portfolio", "broker", "order", "api", "intelligence")
    assert not any(any(value in module for value in forbidden) for module in imports)
