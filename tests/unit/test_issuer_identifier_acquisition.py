from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from dataclasses import replace
from io import BytesIO
from zipfile import ZipFile

import gzip

import pytest

import app.historical.issuer_identifier_acquisition as acquisition
from app.historical.issuer_security_identity import (
    IssuerIdentifierType, IssuerSecurityBridgeReadiness, resolve_issuer_security_bridge,
)
from app.historical.nse_mii_security_master import (
    NseMiiSecurityMasterHttpResponse, extract_nse_mii_security_master, nse_mii_security_master_url,
)
from app.historical.nse_session_identity import (
    activate_nse_session_identity_policy, approve_nse_session_identity_policy, session_point_identity_from_row,
)
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository


T = datetime(2026, 9, 4, 10, tzinfo=UTC)
HEADERS = "FinInstrmId,TckrSymb,SctySrs,FinInstrmNm,ISIN,SctyStsNrmlMkt,ListgDt,RmvlDt,FinInstrmTp,SctyTp\n"


def _session(day: date = date(2026, 8, 31), *, symbol: str = "EXACT", isin: str = "INE000A01001"):
    extraction = extract_nse_mii_security_master(NseMiiSecurityMasterHttpResponse(
        day, nse_mii_security_master_url(day), "application/x-gzip",
        gzip.compress((HEADERS + f"100,{symbol},EQ,Exact Limited,{isin},6,100,0,EQ,EQUITY\n").encode()), T,
    ))
    approval = approve_nse_session_identity_policy(
        approval_id="issuer-acquisition-approval", approved_by="human:approved", approved_at=T,
    )
    activation = activate_nse_session_identity_policy(
        selection_id="issuer-acquisition-activation", approval=approval, activated_by="human:approved", activated_at=T,
    )
    return session_point_identity_from_row(activation=activation, snapshot=extraction.snapshot, row=extraction.rows[0])


def _store(tmp_path):
    return acquisition.IssuerIdentifierEvidenceStore(SQLiteCoreApiSnapshotRepository(tmp_path / "issuer.sqlite"))


def _nse_csv(*, day: str = "2026-08-31", symbol: str = "EXACT", isin: str = "INE000A01001", cin: str = "L12345MH2010PLC123456") -> bytes:
    return (
        "Symbol,Company Name,ISIN,Corporate Identity Number (CIN) of the Listed Entity,Date of Submission\n"
        f"{symbol},Exact Limited,{isin},{cin},{day}\n"
    ).encode()


def _gleif_zip(*, isin: str = "INE000A01001", lei: str = "5493001KJTIIGC8Y1R12") -> bytes:
    stream = BytesIO()
    with ZipFile(stream, "w") as archive:
        archive.writestr("isin_lei.csv", f"ISIN,LEI\n{isin},{lei}\n")
    return stream.getvalue()


def test_exact_nse_isin_to_cin_mapping_persists_a_same_session_bridge_and_target_audit(tmp_path):
    session = _session(); payload = _nse_csv()
    evidence = acquisition.extract_nse_structured_identity_csv(
        payload=payload, source_reference="https://www.nseindia.com/structured/qip.csv", source_observed_at=T,
    )
    store = _store(tmp_path)
    receipt = acquisition.acquire_exact_issuer_bridges(
        store=store, session_securities=(session,), evidence=evidence,
        source=acquisition.IssuerIdentifierEvidenceSource.NSE_STRUCTURED_FILING,
        source_document_fingerprint="sha256:" + __import__("hashlib").sha256(payload).hexdigest(),
        source_as_of_date=session.session_date, source_observed_at=T,
    )
    assert receipt.bridge_inserted == 1 and receipt.symbol_conflicts == 0
    bridge = store.bridges()[0]
    assert bridge.issuer_identifier_type is IssuerIdentifierType.CIN
    assert bridge.issuer_legal_name == "Exact Limited"
    assert resolve_issuer_security_bridge(session, bridges=store.bridges()).readiness is IssuerSecurityBridgeReadiness.EXACT_ISSUER_BRIDGE
    audit = acquisition.audit_target_issuer_coverage(
        session_securities=(session,), bridges=store.bridges(), evidence=store.evidence(), targets=("EXACT",), session_date=session.session_date,
    )[0]
    assert audit.bridge_available and audit.cin == "L12345MH2010PLC123456"
    assert audit.sources == (acquisition.IssuerIdentifierEvidenceSource.NSE_STRUCTURED_FILING,)


def test_exact_bse_isin_scrip_to_cin_mapping_accepts_only_labelled_fields(tmp_path):
    session = _session(); payload = b"official-bse-corporate-information"
    evidence = acquisition.extract_bse_structured_identity_rows(
        rows=({"Scrip Code": "500001", "ISIN": session.isin, "CIN": "L12345MH2010PLC123456", "NSE Symbol": "EXACT", "Company Name": "Exact Limited", "Publication Date": "31-08-2026"},),
        source_document=payload, source_reference="https://www.bseindia.com/corporates/issuer", source_observed_at=T,
    )
    receipt = acquisition.acquire_exact_issuer_bridges(
        store=_store(tmp_path), session_securities=(session,), evidence=evidence,
        source=acquisition.IssuerIdentifierEvidenceSource.BSE_STRUCTURED_FILING,
        source_document_fingerprint=evidence[0].source_document_fingerprint, source_as_of_date=session.session_date, source_observed_at=T,
    )
    assert receipt.bridge_inserted == 1
    with pytest.raises(acquisition.IssuerIdentifierAcquisitionError, match="REQUIRED_FIELDS"):
        acquisition.extract_bse_structured_identity_rows(
            rows=({"Company Name": "Exact Limited", "CIN": "L12345MH2010PLC123456"},), source_document=payload,
            source_reference="https://www.bseindia.com/corporates/issuer", source_observed_at=T,
        )


def test_exact_gleif_isin_to_lei_mapping_and_level1_registration_authority_are_preserved(tmp_path):
    session = _session(); payload = _gleif_zip()
    evidence = acquisition.extract_gleif_isin_lei_zip(
        payload=payload, source_reference="https://mapping.gleif.org/api/v2/isin-lei/example/download",
        source_as_of_date=session.session_date, source_observed_at=T, allowed_isins=(session.isin,),
    )
    assert evidence[0].issuer_identifier_value == "5493001KJTIIGC8Y1R12"
    level1 = acquisition.gleif_level1_reference_from_payload(
        lei="5493001KJTIIGC8Y1R12",
        payload={"data": {"attributes": {"entity": {
            "legalName": {"name": "Exact Limited"},
            "registrationAuthority": {"registrationAuthorityID": "RA000394", "registrationAuthorityEntityID": "L12345MH2010PLC123456"},
        }}}}, source_reference="https://api.gleif.org/api/v1/lei-records/5493001KJTIIGC8Y1R12", source_as_of_date=session.session_date,
    )
    assert (level1.registration_authority_id, level1.registration_authority_entity_id) == ("RA000394", "L12345MH2010PLC123456")
    store = _store(tmp_path)
    receipt = acquisition.acquire_exact_issuer_bridges(
        store=store, session_securities=(session,), evidence=evidence,
        source=acquisition.IssuerIdentifierEvidenceSource.GLEIF_ANNA_ISIN_LEI,
        source_document_fingerprint=evidence[0].source_document_fingerprint, source_as_of_date=session.session_date, source_observed_at=T,
    )
    assert receipt.bridge_inserted == 1
    assert store.bridges()[0].issuer_identifier_type is IssuerIdentifierType.LEI
    assert not acquisition.extract_gleif_isin_lei_zip(
        payload=payload, source_reference="https://mapping.gleif.org/api/v2/isin-lei/example/download",
        source_as_of_date=session.session_date, source_observed_at=T, allowed_isins=("INE000A01002",),
    )


def test_fuzzy_linkage_and_cin_format_guessing_are_rejected():
    with pytest.raises(acquisition.IssuerIdentifierAcquisitionError, match="REQUIRED_FIELDS"):
        acquisition.extract_nse_structured_identity_csv(
            payload=b"Company Name,CIN\nExact Limited,L12345MH2010PLC123456\n",
            source_reference="https://www.nseindia.com/qip", source_observed_at=T,
        )
    with pytest.raises(acquisition.IssuerIdentifierAcquisitionError, match="INVALID"):
        acquisition.evidence_from_structured_row(
            source=acquisition.IssuerIdentifierEvidenceSource.NSE_STRUCTURED_FILING, source_document=b"x",
            source_reference="https://www.nseindia.com/qip", source_record_id="row:1", source_as_of_date=date(2026, 8, 31),
            source_observed_at=T, isin="INE000A01001", issuer_identifier_type=IssuerIdentifierType.CIN,
            issuer_identifier_value="CIN L12345MH2010PLC123456",
        )


def test_conflicting_exact_issuer_evidence_is_retained_and_fails_closed(tmp_path):
    session = _session(); source = _nse_csv(); store = _store(tmp_path)
    cin = acquisition.extract_nse_structured_identity_csv(payload=source, source_reference="https://www.nseindia.com/qip", source_observed_at=T)
    lei = acquisition.extract_gleif_isin_lei_zip(payload=_gleif_zip(), source_reference="https://mapping.gleif.org/example", source_as_of_date=session.session_date, source_observed_at=T)
    for values, kind in ((cin, acquisition.IssuerIdentifierEvidenceSource.NSE_STRUCTURED_FILING), (lei, acquisition.IssuerIdentifierEvidenceSource.GLEIF_ANNA_ISIN_LEI)):
        acquisition.acquire_exact_issuer_bridges(
            store=store, session_securities=(session,), evidence=values, source=kind,
            source_document_fingerprint=values[0].source_document_fingerprint, source_as_of_date=session.session_date, source_observed_at=T,
        )
    result = resolve_issuer_security_bridge(session, bridges=store.bridges())
    assert result.readiness is IssuerSecurityBridgeReadiness.EVIDENCE_CONFLICTED
    assert len(result.bridges) == 2


def test_future_evidence_is_not_bound_to_an_earlier_session(tmp_path):
    historical = _session(date(2024, 2, 5)); payload = _nse_csv(day="2026-08-31")
    evidence = acquisition.extract_nse_structured_identity_csv(payload=payload, source_reference="https://www.nseindia.com/qip", source_observed_at=T)
    receipt = acquisition.acquire_exact_issuer_bridges(
        store=_store(tmp_path), session_securities=(historical,), evidence=evidence,
        source=acquisition.IssuerIdentifierEvidenceSource.NSE_STRUCTURED_FILING,
        source_document_fingerprint=evidence[0].source_document_fingerprint, source_as_of_date=date(2026, 8, 31), source_observed_at=T,
    )
    assert receipt.bridge_inserted == 0 and receipt.exact_isin_candidates == 0


def test_tampered_lineage_and_future_known_time_are_rejected():
    payload = _nse_csv()
    evidence = acquisition.extract_nse_structured_identity_csv(
        payload=payload, source_reference="https://www.nseindia.com/qip", source_observed_at=T,
    )[0]
    with pytest.raises(acquisition.IssuerIdentifierAcquisitionError, match="INVALID"):
        replace(evidence, source_record_fingerprint="sha256:" + "0" * 64)
    with pytest.raises(acquisition.IssuerIdentifierAcquisitionError, match="FUTURE_KNOWN_TIME"):
        acquisition.evidence_from_structured_row(
            source=acquisition.IssuerIdentifierEvidenceSource.NSE_STRUCTURED_FILING, source_document=payload,
            source_reference="https://www.nseindia.com/qip", source_record_id="nse:future", source_as_of_date=date(2026, 8, 31),
            source_observed_at=T, historical_known_at=T + timedelta(days=1), isin="INE000A01001",
            issuer_identifier_type=IssuerIdentifierType.CIN, issuer_identifier_value="L12345MH2010PLC123456",
        )


def test_source_replay_is_idempotent_and_does_not_create_another_bridge(tmp_path):
    session = _session(); payload = _nse_csv(); store = _store(tmp_path)
    evidence = acquisition.extract_nse_structured_identity_csv(payload=payload, source_reference="https://www.nseindia.com/qip", source_observed_at=T)
    kwargs = dict(
        store=store, session_securities=(session,), evidence=evidence,
        source=acquisition.IssuerIdentifierEvidenceSource.NSE_STRUCTURED_FILING,
        source_document_fingerprint=evidence[0].source_document_fingerprint,
        source_as_of_date=session.session_date, source_observed_at=T,
    )
    assert acquisition.acquire_exact_issuer_bridges(**kwargs).bridge_inserted == 1
    replay = acquisition.acquire_exact_issuer_bridges(**kwargs)
    assert replay.bridge_inserted == 0 and replay.bridge_already_present == 1
    assert len(store.bridges()) == 1 and len(store.evidence()) == 1


def test_deterministic_fingerprint_symbol_conflict_and_no_forbidden_dependencies(tmp_path):
    session = _session(symbol="EXACT"); payload = _nse_csv(symbol="OTHER")
    evidence = acquisition.extract_nse_structured_identity_csv(payload=payload, source_reference="https://www.nseindia.com/qip", source_observed_at=T)
    assert acquisition.extract_nse_structured_identity_csv(payload=payload, source_reference="https://www.nseindia.com/qip", source_observed_at=T) == evidence
    receipt = acquisition.acquire_exact_issuer_bridges(
        store=_store(tmp_path), session_securities=(session,), evidence=evidence,
        source=acquisition.IssuerIdentifierEvidenceSource.NSE_STRUCTURED_FILING,
        source_document_fingerprint=evidence[0].source_document_fingerprint, source_as_of_date=session.session_date, source_observed_at=T,
    )
    assert receipt.symbol_conflicts == 1 and receipt.bridge_inserted == 0
    source = open(acquisition.__file__, encoding="utf-8").read().lower()
    for forbidden in ("app.portfolio", "app.broker", "app.orders", "app.api", "app.runtime", "app.intelligence.pit_company_type", "backtest", "place_order", "buy", "sell", "rotate", "datetime.now", "time.time"):
        assert forbidden not in source
