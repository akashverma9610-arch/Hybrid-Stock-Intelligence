from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path

import pytest
import requests

from app.data_operations.nse_shareholding_acquisition import (
    NSE_SHAREHOLDING_EXPORT_URL, NSE_SHAREHOLDING_PAGE_URL,
    NseOfficialShareholdingAcquirer, NseReg31Target, NseShareholdingAcquisitionError,
    _nse_timestamp_to_iso,
)
from app.data_operations.nse_reg31_identity import (
    Reg31IdentityEvidence, Reg31SecurityClass, classify_reg31_identity,
)


TARGET = NseReg31Target("APARINDS", "INE372A01015")
CSV = b'\xef\xbb\xbf"COMPANY","PROMOTER & PROMOTER GROUP (A)","PUBLIC (B)","SHARES HELD BY EMPLOYEE TRUSTS (C2)","STATUS","AS ON DATE","SUBMISSION DATE","REVISION DATE","ACTION","BROADCAST DATE/TIME"\n"Apar Industries Limited","55.42","44.58","0","-","13-AUG-2026","20-AUG-2026",,"https://nsearchives.nseindia.com/corporate/xbrl/SHP_1.xml","20-AUG-2026 15:13:12"\n'
IDENTITY = b'[{"symbol":"APARINDS","isin":"INE372A01015","name":"Apar Industries Limited"}]'


class FakeSession:
    def __init__(self, *, csv: bytes = CSV, identity: bytes = IDENTITY) -> None:
        self.csv, self.identity, self.calls = csv, identity, []

    def get(self, url: str, **kwargs: object) -> requests.Response:
        self.calls.append((url, kwargs))
        response = requests.Response()
        response.status_code = 200
        response.url = url
        params = kwargs.get("params") or {}
        if url == NSE_SHAREHOLDING_PAGE_URL:
            response.headers["Content-Type"] = "text/html"
            response._content = b"<html></html>"
        elif params.get("csv") == "true":
            response.headers["Content-Type"] = "text/csv"
            response.headers["Content-Disposition"] = "attachment; filename=CF-Shareholding-Pattern-equities-APARINDS-01-Sep-2026.csv"
            response._content = self.csv
        else:
            response.headers["Content-Type"] = "application/json"
            response._content = self.identity
        return response


def _acquirer(tmp_path: Path, session: FakeSession) -> NseOfficialShareholdingAcquirer:
    return NseOfficialShareholdingAcquirer(
        tmp_path, session=session, clock=lambda: datetime(2026, 9, 1, 4, 0, tzinfo=UTC),
    )


def test_official_csv_is_exact_target_checked_and_staged_with_deterministic_provenance(tmp_path: Path) -> None:
    session = FakeSession()
    staged = _acquirer(tmp_path, session).acquire((TARGET,))

    assert len(staged) == 1
    item = staged[0]
    assert item.status == "STAGED"
    assert item.path.name == "CF-Shareholding-Pattern-equities-APARINDS-01-Sep-2026.csv"
    assert item.path.read_bytes() == CSV
    assert item.sha256 == sha256(CSV).hexdigest()
    provenance = item.path.with_suffix(".csv.provenance.json").read_text(encoding="utf-8")
    assert '"isin":"INE372A01015"' in provenance and NSE_SHAREHOLDING_EXPORT_URL in provenance
    assert [call[0] for call in session.calls] == [NSE_SHAREHOLDING_PAGE_URL, NSE_SHAREHOLDING_EXPORT_URL, NSE_SHAREHOLDING_EXPORT_URL]


def test_second_acquisition_is_identical_and_does_not_overwrite(tmp_path: Path) -> None:
    first = _acquirer(tmp_path, FakeSession()).acquire((TARGET,))[0]
    second = _acquirer(tmp_path, FakeSession()).acquire((TARGET,))[0]

    assert first.path == second.path and second.status == "IDENTICAL"
    assert len(list(tmp_path.glob("*.csv"))) == 1


def test_mismatched_official_identity_fails_closed_without_staging(tmp_path: Path) -> None:
    session = FakeSession(identity=b'[{"symbol":"APARINDS","isin":"INE000A01001"}]')

    with pytest.raises(NseShareholdingAcquisitionError, match="EXACT_IDENTITY_MISMATCH"):
        _acquirer(tmp_path, session).acquire((TARGET,))
    assert not tuple(tmp_path.iterdir())


def test_changed_same_filename_is_retained_as_conflict_raw_evidence(tmp_path: Path) -> None:
    first = _acquirer(tmp_path, FakeSession()).acquire((TARGET,))[0]
    changed = CSV.replace(b'"55.42"', b'"55.43"')
    second = _acquirer(tmp_path, FakeSession(csv=changed)).acquire((TARGET,))[0]

    assert second.status == "CONFLICT_RETAINED"
    assert first.path.read_bytes() == CSV and second.path.read_bytes() == changed
    assert "sha256-" in second.path.name


def test_rejects_nonapproved_target_and_does_not_make_request(tmp_path: Path) -> None:
    session = FakeSession()
    with pytest.raises(ValueError, match="not approved"):
        _acquirer(tmp_path, session).acquire((NseReg31Target("OTHER", "INE000A01001"),))
    assert session.calls == []


def test_cohort_identity_failure_happens_before_any_artifact_is_staged(tmp_path: Path) -> None:
    session = FakeSession()
    failed = NseReg31Target("DEEPINDS", "INE0FHS01024")
    with pytest.raises(NseShareholdingAcquisitionError, match="EXACT_IDENTITY_MISMATCH"):
        _acquirer(tmp_path, session).acquire((TARGET, failed))
    assert not tuple(tmp_path.iterdir())


def test_nonofficial_final_response_is_rejected(tmp_path: Path) -> None:
    class RedirectedSession(FakeSession):
        def get(self, url: str, **kwargs: object) -> requests.Response:
            response = super().get(url, **kwargs)
            if url == NSE_SHAREHOLDING_EXPORT_URL:
                response.url = "https://www.nseindia.com.evil.example/response"
            return response

    with pytest.raises(NseShareholdingAcquisitionError, match="NON_OFFICIAL_RESPONSE"):
        _acquirer(tmp_path, RedirectedSession()).acquire((TARGET,))
    assert not tuple(tmp_path.iterdir())


def test_only_verified_predecessor_with_current_xbrl_can_pass_the_acquisition_gate(tmp_path: Path) -> None:
    target = NseReg31Target("DEEPINDS", "INE0FHS01024")
    xbrl = b'<?xml version="1.0"?><xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:link="http://www.xbrl.org/2003/linkbase"><link:schemaRef href="in-bse-shp-2025-10-31.xsd"/><ISIN>INE0FHS01024</ISIN><Symbol>DEEPINDS</Symbol><NameOfTheCompany>Deep Industries Limited</NameOfTheCompany></xbrli:xbrl>'
    current = Reg31IdentityEvidence(target.isin, target.symbol, "Deep Industries Limited", Reg31SecurityClass.EQUITY, datetime(2026, 9, 1, tzinfo=UTC), "https://nsearchives.nseindia.com/current.xml", sha256(xbrl).hexdigest())
    legacy = Reg31IdentityEvidence("INE0FHS01016", target.symbol, "Deep Industries Limited", Reg31SecurityClass.EQUITY, datetime(2026, 9, 1, tzinfo=UTC), "https://www.nseindia.com/api/corporate-share-holdings-master", sha256(b"legacy").hexdigest())
    reconciliation = classify_reg31_identity(
        canonical_instrument_id="NSE:" + target.isin, current_identity=current, returned_identity=legacy,
        known_at=datetime(2026, 9, 1, tzinfo=UTC), effective_date=datetime(2023, 4, 10, tzinfo=UTC),
        predecessor_proven=True, official_evidence_references=tuple(sorted((current.source_reference, legacy.source_reference))),
    )

    class Store:
        def get(self, **kwargs):
            return reconciliation

    class Session(FakeSession):
        def __init__(self):
            super().__init__(
                csv=CSV.replace(b"Apar Industries Limited", b"Deep Industries Limited"),
                identity=b'[{"symbol":"DEEPINDS","isin":"INE0FHS01016","name":"Deep Industries Limited","xbrl":"https://nsearchives.nseindia.com/current.xml"}]',
            )
        def get(self, url: str, **kwargs: object) -> requests.Response:
            if url == "https://nsearchives.nseindia.com/current.xml":
                response = requests.Response(); response.status_code = 200; response.url = url
                response.headers["Content-Type"] = "application/xml"; response._content = xbrl
                return response
            return super().get(url, **kwargs)

    staged = NseOfficialShareholdingAcquirer(
        tmp_path, session=Session(), identity_reconciliation_store=Store(),
        clock=lambda: datetime(2026, 9, 1, 4, tzinfo=UTC),
    ).acquire((target,))
    assert staged[0].status == "STAGED" and staged[0].target == target


def test_icici_current_xbrl_is_independent_while_legacy_csv_identity_remains_quarantined(tmp_path: Path) -> None:
    target = NseReg31Target("ICICIBANK", "INE090A01021")
    xbrl = b'<?xml version="1.0"?><xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:link="http://www.xbrl.org/2003/linkbase"><link:schemaRef href="in-bse-shp-2025-10-31.xsd"/><xbrli:context><xbrli:period><xbrli:instant>2026-06-30</xbrli:instant></xbrli:period></xbrli:context><ISIN>INE090A01021</ISIN><Symbol>ICICIBANK</Symbol><NameOfTheCompany>ICICI Bank Limited</NameOfTheCompany></xbrli:xbrl>'
    identity = b'[{"symbol":"ICICIBANK","isin":"IN9090A01011","name":"ICICI Bank Limited","date":"30-JUN-2026","broadcastDate":"17-JUL-2026 13:54:27","recordId":"1694984","xbrl":"https://nsearchives.nseindia.com/current-icici.xml"}]'

    class Session(FakeSession):
        def __init__(self) -> None:
            super().__init__(identity=identity)
        def get(self, url: str, **kwargs: object) -> requests.Response:
            if url == "https://nsearchives.nseindia.com/current-icici.xml":
                response = requests.Response(); response.status_code = 200; response.url = url
                response.headers["Content-Type"] = "application/xml"; response._content = xbrl
                return response
            return super().get(url, **kwargs)

    acquirer = _acquirer(tmp_path, Session())
    with pytest.raises(NseShareholdingAcquisitionError, match="EXACT_IDENTITY_MISMATCH"):
        acquirer.acquire((target,))
    staged = acquirer.acquire_current_xbrl((target,))[0]
    assert staged.path.suffix == ".xml" and staged.path.read_bytes() == xbrl
    assert '"isin":"INE090A01021"' in staged.path.with_suffix(".xml.provenance.json").read_text(encoding="utf-8")


def test_nse_broadcast_timestamp_is_interpreted_in_the_exchange_timezone_for_pit() -> None:
    assert _nse_timestamp_to_iso("17-JUL-2026 13:54:27") == "2026-07-17T08:24:27+00:00"


def test_current_xbrl_reacquisition_accepts_existing_raw_only_with_a_matching_append_only_pit_manifest(tmp_path: Path) -> None:
    target = NseReg31Target("ICICIBANK", "INE090A01021")
    xbrl = b'<?xml version="1.0"?><xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:link="http://www.xbrl.org/2003/linkbase"><link:schemaRef href="in-bse-shp-2025-10-31.xsd"/><xbrli:context><xbrli:period><xbrli:instant>2026-06-30</xbrli:instant></xbrli:period></xbrli:context><ISIN>INE090A01021</ISIN><Symbol>ICICIBANK</Symbol><NameOfTheCompany>ICICI Bank Limited</NameOfTheCompany></xbrli:xbrl>'
    identity = b'[{"symbol":"ICICIBANK","isin":"IN9090A01011","name":"ICICI Bank Limited","date":"30-JUN-2026","broadcastDate":"17-JUL-2026 13:54:27","recordId":"1694984","xbrl":"https://nsearchives.nseindia.com/current-icici.xml"}]'
    class Session(FakeSession):
        def __init__(self) -> None: super().__init__(identity=identity)
        def get(self, url: str, **kwargs: object) -> requests.Response:
            if url == "https://nsearchives.nseindia.com/current-icici.xml":
                response = requests.Response(); response.status_code = 200; response.url = url
                response.headers["Content-Type"] = "application/xml"; response._content = xbrl
                return response
            return super().get(url, **kwargs)
    first = _acquirer(tmp_path, Session()).acquire_current_xbrl((target,))[0]
    original_manifest = first.path.with_suffix(".xml.provenance.json")
    old = json.loads(original_manifest.read_text(encoding="utf-8")); old["official_publication_timestamp"] = "2026-07-17T13:54:27+00:00"
    original_manifest.write_text(json.dumps(old, sort_keys=True), encoding="utf-8")
    correction = {"raw_sha256": first.sha256, "source_url": first.source_url, "policy": "nse-reg31-pit-timestamp-correction / v1", "corrected_published_at": "2026-07-17T08:24:27+00:00"}
    first.path.with_name(first.path.name + ".metadata-correction-v1.json").write_text(json.dumps(correction), encoding="utf-8")
    assert _acquirer(tmp_path, Session()).acquire_current_xbrl((target,))[0].status == "IDENTICAL"
