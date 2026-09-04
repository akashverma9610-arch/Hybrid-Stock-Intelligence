from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from zipfile import ZipFile

import pytest
from openpyxl import Workbook

import app.historical.brsr_issuer_identifier_acquisition as brsr
from app.historical.issuer_identifier_acquisition import IssuerIdentifierEvidenceStore
from app.historical.issuer_identifier_acquisition import (
    IssuerIdentifierAcquisitionError, IssuerIdentifierEvidenceSource, evidence_from_structured_row,
)
from app.historical.issuer_security_identity import IssuerIdentifierType
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository


T = datetime(2026, 9, 4, 12, tzinfo=UTC)
SOURCE = "https://nsearchives.nseindia.com/web/sites/default/files/inline-files/BRSR_Data_Dump.zip"
HEADERS = (
    "APP_ID", "TLA_SUBMITTED_DT", "SYMB_SYMBOL",
    "Corporate Identity Number (CIN) of the Listed Entity", "Name of the Listed Entity",
)
VALID = (45705, "20-JUN-2024 16:08:09", "DEEPINDS", "L14292GJ2006PLC049371", "Deep Industries Limited")


def _xlsx(*rows: tuple[object, ...], headers: tuple[str, ...] = HEADERS) -> bytes:
    workbook = Workbook(); sheet = workbook.active; sheet.title = "Export Worksheet"
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    stream = BytesIO(); workbook.save(stream)
    return stream.getvalue()


def _zip(member: str, payload: bytes) -> bytes:
    stream = BytesIO()
    with ZipFile(stream, "w") as archive:
        archive.writestr(member, payload)
    return stream.getvalue()


def _store(tmp_path) -> IssuerIdentifierEvidenceStore:
    return IssuerIdentifierEvidenceStore(SQLiteCoreApiSnapshotRepository(tmp_path / "brsr.sqlite"))


def test_exact_brsr_row_retains_cin_symbol_filing_identity_and_exchange_known_time():
    extraction = brsr.extract_nse_brsr_general_xlsx(
        payload=_xlsx(VALID), source_reference=SOURCE, financial_year="FY23-24", source_observed_at=T,
    )
    assert extraction.rows_inspected == 1 and extraction.rows_rejected == 0
    evidence = extraction.evidence[0]
    assert evidence.isin is None
    assert evidence.nse_symbol == "DEEPINDS"
    assert evidence.issuer_identifier_value == "L14292GJ2006PLC049371"
    assert evidence.issuer_legal_name == "Deep Industries Limited"
    assert evidence.source_record_id == "nse-brsr-application:45705"
    assert evidence.source_as_of_date.isoformat() == "2024-06-20"
    assert evidence.historical_known_at == datetime(2024, 6, 20, 10, 38, 9, tzinfo=UTC)


def test_exact_brsr_general_workbook_can_be_selected_only_by_explicit_zip_member_path():
    member = "BRSR_Data_Dump/BRSR_General/brsr_general 1.xlsx"
    extraction = brsr.extract_nse_brsr_general_zip(
        payload=_zip(member, _xlsx(VALID)), source_reference=SOURCE, financial_year="FY23-24",
        source_observed_at=T, workbook_member_path=member,
    )
    assert extraction.workbook_member_path == member
    assert extraction.evidence[0].source_reference == SOURCE + "#" + member
    with pytest.raises(brsr.BrsrIssuerIdentifierAcquisitionError, match="MEMBER"):
        brsr.extract_nse_brsr_general_zip(
            payload=_zip(member, _xlsx(VALID)), source_reference=SOURCE, financial_year="FY23-24",
            source_observed_at=T, workbook_member_path="../brsr.xlsx",
        )


def test_malformed_cin_and_incomplete_rows_are_rejected_without_name_fallback():
    extraction = brsr.extract_nse_brsr_general_xlsx(
        payload=_xlsx(
            ("1", "20-JUN-2024 16:08:09", "DEEPINDS", "CIN L14292GJ2006PLC049371", "Deep Industries Limited"),
            ("2", "20-JUN-2024 16:08:09", "", "L14292GJ2006PLC049371", "Deep Industries Limited"),
        ), source_reference=SOURCE, financial_year="FY23-24", source_observed_at=T,
    )
    assert extraction.evidence == () and extraction.rows_rejected == 2


def test_brsr_source_cannot_be_recast_as_an_isin_or_bse_security_bridge():
    with pytest.raises(IssuerIdentifierAcquisitionError, match="BRSR_FILING_SECURITY_LOCATOR_INVALID"):
        evidence_from_structured_row(
            source=IssuerIdentifierEvidenceSource.NSE_BRSR_ARCHIVE, source_document=b"official-brsr",
            source_reference=SOURCE, source_record_id="nse-brsr-application:45705",
            source_as_of_date=datetime(2024, 6, 20, tzinfo=UTC).date(), source_observed_at=T,
            historical_known_at=datetime(2024, 6, 20, 10, 38, 9, tzinfo=UTC), isin="INE0FHS01024",
            nse_symbol="DEEPINDS", issuer_identifier_type=IssuerIdentifierType.CIN,
            issuer_identifier_value="L14292GJ2006PLC049371",
        )


def test_missing_or_ambiguous_document_headers_fail_closed():
    with pytest.raises(brsr.BrsrIssuerIdentifierAcquisitionError, match="SHEET_AMBIGUOUS"):
        brsr.extract_nse_brsr_general_xlsx(
            payload=_xlsx(VALID, headers=("APP_ID", "SYMB_SYMBOL", "CIN", "Name of the Listed Entity")),
            source_reference=SOURCE, financial_year="FY23-24", source_observed_at=T,
        )
    with pytest.raises(brsr.BrsrIssuerIdentifierAcquisitionError, match="HEADER_ALIAS_AMBIGUOUS"):
        brsr.extract_nse_brsr_general_xlsx(
            payload=_xlsx(VALID + ("duplicate",), headers=HEADERS + ("SYMBOL",)),
            source_reference=SOURCE, financial_year="FY23-24", source_observed_at=T,
        )


def test_conflicting_duplicate_application_rows_are_rejected_instead_of_resolved_by_order():
    with pytest.raises(brsr.BrsrIssuerIdentifierAcquisitionError, match="FILING_ROW_AMBIGUOUS"):
        brsr.extract_nse_brsr_general_xlsx(
            payload=_xlsx(VALID, ("45705", "20-JUN-2024 16:08:09", "DEEPINDS", "L91110GJ1989PLC012802", "Deep Industries Limited")),
            source_reference=SOURCE, financial_year="FY23-24", source_observed_at=T,
        )


def test_persistence_is_idempotent_and_creates_no_session_bridge(tmp_path):
    extraction = brsr.extract_nse_brsr_general_xlsx(
        payload=_xlsx(VALID), source_reference=SOURCE, financial_year="FY23-24", source_observed_at=T,
    )
    store = _store(tmp_path)
    first = brsr.persist_brsr_issuer_identifier_evidence(store=store, extraction=extraction)
    replay = brsr.persist_brsr_issuer_identifier_evidence(store=store, extraction=extraction)
    assert (first.evidence_inserted, first.evidence_already_present) == (1, 0)
    assert (replay.evidence_inserted, replay.evidence_already_present) == (0, 1)
    assert len(store.evidence()) == 1 and store.bridges() == ()


def test_filing_level_symbol_cin_evidence_reopens_without_becoming_an_isin_bridge(tmp_path):
    path = tmp_path / "brsr-reopen.sqlite"
    extraction = brsr.extract_nse_brsr_general_xlsx(
        payload=_xlsx(VALID), source_reference=SOURCE, financial_year="FY23-24", source_observed_at=T,
    )
    repository = SQLiteCoreApiSnapshotRepository(path)
    brsr.persist_brsr_issuer_identifier_evidence(
        store=IssuerIdentifierEvidenceStore(repository), extraction=extraction,
    )
    repository.close()
    reopened = SQLiteCoreApiSnapshotRepository(path)
    retained = IssuerIdentifierEvidenceStore(reopened)
    assert len(retained.evidence()) == 1
    assert retained.evidence()[0].isin is None
    assert retained.bridges() == ()
    reopened.close()


def test_target_audit_uses_exact_symbol_only_and_retains_conflict_state():
    extraction = brsr.extract_nse_brsr_general_xlsx(
        payload=_xlsx(
            VALID,
            ("52562", "31-JUL-2024 17:11:17", "APARINDS", "L91110GJ1989PLC012802", "APAR Industries Limited"),
            ("99999", "01-AUG-2024 12:00:00", "DEEPINDS", "L91110GJ1989PLC012802", "Different Entity"),
        ), source_reference=SOURCE, financial_year="FY23-24", source_observed_at=T,
    )
    audits = {item.symbol: item for item in brsr.audit_brsr_target_evidence(
        evidence=extraction.evidence, targets=("DEEPINDS", "APARINDS", "Deep Industries Limited"),
    )}
    assert audits["APARINDS"].status == "EXACT_FILING_EVIDENCE_RETAINED"
    assert audits["DEEPINDS"].status == "EVIDENCE_CONFLICTED"
    assert audits["Deep Industries Limited"].status == "NO_EXACT_BRSR_SYMBOL_EVIDENCE"


def test_deterministic_extraction_fingerprint_and_tamper_rejection():
    payload = _xlsx(VALID)
    first = brsr.extract_nse_brsr_general_xlsx(
        payload=payload, source_reference=SOURCE, financial_year="FY23-24", source_observed_at=T,
    )
    second = brsr.extract_nse_brsr_general_xlsx(
        payload=payload, source_reference=SOURCE, financial_year="FY23-24", source_observed_at=T,
    )
    assert first == second
    with pytest.raises(brsr.BrsrIssuerIdentifierAcquisitionError, match="EXTRACTION_INVALID"):
        __import__("dataclasses").replace(first, rows_rejected=1)


def test_no_company_type_backtest_portfolio_or_execution_dependency_is_present():
    source = open(brsr.__file__, encoding="utf-8").read().lower()
    for forbidden in (
        "app.intelligence.pit_company_type", "app.portfolio", "app.broker", "app.orders", "app.api", "app.runtime",
        "backtest", "compounder", "buy", "sell", "rotate", "datetime.now", "time.time",
    ):
        assert forbidden not in source
