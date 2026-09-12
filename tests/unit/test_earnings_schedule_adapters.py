"""Synthetic fixtures of observed public markup; never live coverage proof."""
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, date, datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import ast

import pytest

from app.filings.earnings_schedule_source import (
    BSE_BOARD, NSE_RSS, MAX_BYTES, BSEOfficialEarningsScheduleSource,
    NSEOfficialEarningsScheduleSource, BoundedOfficialTransport, Fetch, RawSchedule,
    SourceState, classify, parse_bse_detail, parse_meeting_date,
    parse_nse_prior_intimation, parse_nse_rss, public_url,
)
from app.filings.earnings_schedule_ingestion import coverage_receipt, normalize_schedule
from app.filings.earnings_schedule_store import SQLiteEarningsScheduleStore
from app.gates.official_earnings_schedule_candidate import (
    CandidateVerificationState, PurposeClassification as P, ScheduleLifecycleState as L,
    SourceExchange as X, make_official_earnings_schedule_candidate,
)
from app.historical.security_master import HistoricalSecurityIdentity, HistoricalSecurityStatus

T = datetime(2026, 9, 12, 10, tzinfo=UTC)
INSTRUMENT = "NSE:INE372A01015"
XML_URL = "https://nsearchives.nseindia.com/corporate/xbrl/PRIOR_INTIMATION_123_WebXMLFile_20260912.xml"
BSE_URL = "https://m.bseindia.com/MAnnDet.aspx?Form=STR&newsid=15bec8ef-4d88-44f6-bccc-4b0d111db3b3&scrpcd=532259"
FP = "sha256:" + "a" * 64


def rss(purpose="Financial Results", stamp="12-Sep-2026 10:00:00", copies=1):
    item = f"<item><title>Synthetic issuer</title><link>{XML_URL}</link><description>{purpose} |Meeting Date: 16-Oct-2026</description><pubDate>{stamp}</pubDate></item>"
    return ("<rss><channel><title>NSE News - Board Meetings</title>" + item * copies + "</channel></rss>").encode()


def xbrl(purpose="Financial Results", kind="New", isin="INE372A01015"):
    fields = {"NSESymbol": "APARINDS", "ISIN": isin, "NameOfTheCompany": "Synthetic issuer",
              "TypeOfMeeting": "Board Meeting", "TypeOfIntimation": kind,
              "DateOfProposedMeeting": "2026-10-16", "Agenda1": purpose}
    return ('<xbrl xmlns="http://www.xbrl.org/2003/instance" xmlns:p="https://www.sebi.gov.in/xbrl/2023-05-31/in-capmkt">' + ''.join(f"<p:{k}>{v}</p:{k}>" for k, v in fields.items()) + '</xbrl>').encode()


def bse_html(details="to consider and approve quarterly financial results", stamp="2026-09-12T10:00:00+00:00", code="532259"):
    fields = {"Security Code": code, "Company": "Synthetic issuer", "Exchange Received Time": stamp, "Exchange Disseminated Time": stamp}
    return ("<table>" + "".join(f"<tr><td class='resultgreyhead'>{k}</td><td class='resultleft'>{v}</td></tr>" for k, v in fields.items()) + "</table><table><tr><td class='ann01'>Board Meeting Intimation for Financial Results | display date</td></tr>" + f"<tr><td class='ann02'>Synthetic issuer has informed BSE that the meeting is scheduled on 16/10/2026 ,inter alia, {details}</td></tr></table>").encode()


def nse_row(**changes):
    row = parse_nse_prior_intimation(xbrl(), parse_nse_rss(rss(stamp=T.isoformat()))[0])
    return replace(row, raw=tuple(sorted((dict(row.raw) | changes).items())))


def identity(exchange=X.NSE, **changes):
    data = dict(identity_id="identity:test:" + exchange.value, canonical_instrument_id=INSTRUMENT,
                isin="INE372A01015", exchange=exchange.value, symbol="APARINDS", series="EQ",
                listed_from=None, listed_until=None, tradable_from=None, tradable_until=None,
                symbol_effective_from=T - timedelta(days=100), symbol_effective_to=None,
                status=HistoricalSecurityStatus.ACTIVE, source="OFFICIAL_FIXTURE", as_of=T - timedelta(days=1),
                version="v1", source_reference="official-fixture", exchange_security_code="532259", source_fingerprint=FP)
    return HistoricalSecurityIdentity(**(data | changes))


def normalized(row=None, identities=None, received=T + timedelta(seconds=2)):
    row = row or nse_row()
    return normalize_schedule(row, canonical_instrument_id=INSTRUMENT,
                              identities=identities if identities is not None else (identity(row.exchange),), retrieved_at=received)


class Fake:
    def __init__(self, body, status=200, error=None):
        self.body, self.status, self.error = body, status, error
        self.calls = []

    def get(self, url):
        self.calls.append(url)
        if self.error:
            raise self.error
        return Fetch(url, self.status, self.body)


@pytest.mark.parametrize("url", [NSE_RSS, XML_URL, BSE_BOARD, BSE_URL])
def test_exact_official_public_paths_accepted(url):
    assert public_url(url) == url


@pytest.mark.parametrize("url", [NSE_RSS.replace("https:", "http:"), NSE_RSS.replace("nseindia.com", "nseindia.com.evil.test"),
    BSE_URL.replace("bseindia.com", "bseindia.com.evil.test"), BSE_URL.replace("m.bseindia.com", "user:secret@m.bseindia.com"),
    "https://www.nseindia.com/api/undocumented", BSE_URL + "&secret=x", NSE_RSS + "#fragment"])
def test_nonofficial_or_arbitrary_routes_rejected(url):
    with pytest.raises(ValueError):
        public_url(url)


@pytest.mark.parametrize("error", [TimeoutError("secret"), OSError("secret")])
def test_transport_failure_never_empty_success_or_secret(error):
    value = NSEOfficialEarningsScheduleSource(Fake(b"", error=error)).fetch(retrieved_at=T)
    assert value.state == SourceState.SOURCE_UNAVAILABLE
    assert "secret" not in value.to_json()


@pytest.mark.parametrize("status", [401, 403, 429, 500])
def test_http_failure_is_distinct(status):
    value = BSEOfficialEarningsScheduleSource(Fake(b"provider error", status)).fetch(retrieved_at=T)
    assert value.state == SourceState.SOURCE_UNAVAILABLE
    assert value.reason == f"HTTP_{status}"


def test_size_bound_before_parser():
    value = NSEOfficialEarningsScheduleSource(Fake(b"x" * (MAX_BYTES + 1))).fetch(retrieved_at=T)
    assert value.state == SourceState.SOURCE_RESPONSE_TOO_LARGE and not value.rows


@pytest.mark.parametrize("body", [b"not xml", b"<rss><broken>", b'<!DOCTYPE rss [<!ENTITY x SYSTEM "file:///secret">]><rss/>', b"<rss><channel/></rss>"])
def test_malformed_nonxml_or_entity_not_success(body):
    value = NSEOfficialEarningsScheduleSource(Fake(body)).fetch(retrieved_at=T)
    assert value.state == SourceState.SOURCE_MALFORMED


def test_nse_rss_preserves_date_and_naive_broadcast_without_mapping_names():
    row = parse_nse_rss(rss())[0]
    assert row.field("disseminated") == "12-Sep-2026 10:00:00"
    assert row.field("symbol") is None
    assert parse_meeting_date(row.field("meeting_date")) == date(2026, 10, 16)
    assert classify(row).classification == P.FINANCIAL_RESULTS_UNSPECIFIED
    assert classify(parse_nse_rss(rss("Board Meeting Intimation"))[0]).classification == P.AMBIGUOUS


def test_nse_xbrl_exact_fields_linkage_and_date_consistency():
    row = nse_row()
    assert row.field("symbol") == "APARINDS" and row.field("isin") == "INE372A01015"
    with pytest.raises(ValueError, match="CONFLICT"):
        parse_nse_prior_intimation(xbrl().replace(b"2026-10-16", b"2026-10-17"), parse_nse_rss(rss())[0])
    with pytest.raises(ValueError):
        parse_nse_prior_intimation(xbrl()[:-7] + b'<p:Agenda2>Dividend</p:Agenda2></xbrl>', parse_nse_rss(rss())[0])


def test_bse_observed_detail_structure_retains_both_exchange_times():
    row = parse_bse_detail(bse_html(), BSE_URL)[0]
    assert row.field("received") == row.field("disseminated") == T.isoformat()
    assert row.field("security_code") == "532259"
    assert classify(row).classification == P.QUARTERLY_FINANCIAL_RESULTS
    value = normalized(row)
    assert value.candidate.scheduled_date == date(2026, 10, 16)
    assert value.candidate.scheduled_time is None
    assert value.candidate.exchange_received_at == value.candidate.known_at == T


def test_bse_no_guessed_record_from_desktop_shell_or_wrong_security():
    result = BSEOfficialEarningsScheduleSource(Fake(b"<html><app-root/></html>")).fetch(retrieved_at=T)
    assert result.state == SourceState.SOURCE_PARTIAL and result.reason == "SOURCE_TRANSPORT_NOT_READY"
    with pytest.raises(ValueError, match="SECURITY_CONFLICT"):
        parse_bse_detail(bse_html(code="544176"), BSE_URL)


@pytest.mark.parametrize("purpose,expected", [
    ("Financial Results", P.FINANCIAL_RESULTS_UNSPECIFIED), ("Quarterly Results", P.QUARTERLY_FINANCIAL_RESULTS),
    ("Half-Yearly Financial Results", P.HALF_YEARLY_FINANCIAL_RESULTS), ("Annual Financial Results", P.ANNUAL_FINANCIAL_RESULTS),
    ("Audited Financial Results", P.AUDITED_FINANCIAL_RESULTS), ("Unaudited Financial Results", P.UNAUDITED_FINANCIAL_RESULTS),
    ("Financial Results / Dividend", P.FINANCIAL_RESULTS_UNSPECIFIED), ("Dividend", P.NON_QUALIFYING),
    ("Fund Raising", P.NON_QUALIFYING), ("General", P.AMBIGUOUS), ("Board Meeting Intimation", P.AMBIGUOUS),
])
def test_versioned_exact_purpose_classifier(purpose, expected):
    receipt = classify(nse_row(purpose=purpose))
    assert receipt.classification == expected
    assert receipt.version == "official-results-purpose/v1"
    assert receipt.raw_purpose == purpose and receipt.source_fingerprint.startswith("sha256:")


@pytest.mark.parametrize("details,qualifies", [
    ("Meeting to consider and approve financial results", True),
    ("Meeting may approve financial results", False), ("Not to consider financial results", False),
    ("Consider dividend; financial results discussed last year", False), ("Financial results reported yesterday", False),
])
def test_generic_plus_detail_only_bounded_affirmative_clause(details, qualifies):
    receipt = classify(nse_row(purpose="General", details=details))
    assert (receipt.classification == P.FINANCIAL_RESULTS_UNSPECIFIED) == qualifies


@pytest.mark.parametrize("field", ["symbol", "isin"])
def test_exact_identity_conflicts_not_fuzzy_names(field):
    result = normalized(nse_row(**{field: "wrong", "company": "APAR Industries Limited"}))
    assert result.state == SourceState.IDENTITY_UNRESOLVED and result.candidate is None


@pytest.mark.parametrize("changes", [dict(as_of=T+timedelta(seconds=1)), dict(symbol_effective_from=T+timedelta(seconds=1)),
    dict(symbol_effective_to=T-timedelta(seconds=1)), dict(source_fingerprint=None), dict(status=HistoricalSecurityStatus.INACTIVE)])
def test_future_inactive_historical_mapping_rejected(changes):
    assert normalized(identities=(identity(**changes),)).state == SourceState.IDENTITY_UNRESOLVED


def test_bse_exact_effective_code_not_company():
    row = parse_bse_detail(bse_html(), BSE_URL)[0]
    assert normalized(row, (identity(X.BSE, exchange_security_code="111111"),)).state == SourceState.IDENTITY_UNRESOLVED


@pytest.mark.parametrize("stamp", ["12-Sep-2026 10:00:00", "12/09/2026 10:00:00", "2026-09-12", ""])
def test_no_timezone_meeting_date_or_hsi_receipt_substitution(stamp):
    result = normalized(nse_row(disseminated=stamp))
    assert result.state == SourceState.TIMESTAMP_UNAVAILABLE and result.candidate is None


def test_pit_and_utc_and_date_only():
    result = normalized()
    assert result.state == SourceState.SUCCESS_WITH_ROWS
    c = result.candidate
    assert not c.visible_at(T-timedelta(microseconds=1)) and c.visible_at(T)
    assert c.hsi_received_at != c.known_at and c.scheduled_time is None
    assert c.verification_state == CandidateVerificationState.UNVERIFIED_SOURCE_AUTHORITY
    zone = timezone(timedelta(hours=5, minutes=30))
    assert normalized(received=(T+timedelta(seconds=2)).astimezone(zone)).to_json() == result.to_json()
    assert normalized(nse_row(disseminated=(T+timedelta(days=1)).isoformat())).state == SourceState.TIMESTAMP_UNAVAILABLE


def test_revision_no_parent_not_inferred_from_same_date():
    assert normalized(nse_row(intimation_type="Revision")).state == SourceState.REVISION_LINEAGE_UNRESOLVED


def test_immutable_raw_and_duplicate_fields_rejected():
    row = nse_row()
    with pytest.raises(FrozenInstanceError):
        row.reference = "x"
    with pytest.raises(ValueError):
        replace(row, raw=tuple(sorted((*row.raw, row.raw[0]))))


def test_partial_and_zero_rows_coverage_not_gate_clearance():
    for body in (rss(), rss(copies=0)):
        batch = NSEOfficialEarningsScheduleSource(Fake(body)).fetch(retrieved_at=T)
        assert batch.state == SourceState.SOURCE_PARTIAL
        args = dict(instruments=(INSTRUMENT,), window_start=T.date(), window_end=date(2026, 10, 31))
        a = coverage_receipt(batch, **args)
        assert a == coverage_receipt(batch, **args)
        report = json.loads(a)
        assert report["query_attempted"] and not report["query_succeeded"]
        assert report["freshness"] == "POLICY_BLOCKED" and report["gate6_clearance"] is False


def test_round_trip_reopen_exact_replay_and_coverage(tmp_path):
    path = tmp_path / "schedules.db"
    store = SQLiteEarningsScheduleStore(path)
    result = normalized()
    assert store.save(result.candidate, source=result.source) == "INSERTED"
    assert store.save(result.candidate, source=result.source) == "IDENTICAL"
    later = normalized(received=T+timedelta(days=1))
    assert store.save(later.candidate, source=later.source) == "IDENTICAL"
    coverage = coverage_receipt(NSEOfficialEarningsScheduleSource(Fake(rss())).fetch(retrieved_at=T), instruments=(INSTRUMENT,), window_start=T.date(), window_end=date(2026,10,31))
    assert store.save_coverage(coverage) == "INSERTED"
    assert store.save_coverage(coverage) == "IDENTICAL"
    store.close()
    reopened = SQLiteEarningsScheduleStore(path)
    assert reopened.get(result.candidate.schedule_id) == result.candidate
    view = reopened.effective_schedule_as_of(INSTRUMENT, T)
    assert view.state == "ONE_EXCHANGE_CANDIDATE" and not view.gate_eligible
    assert view.to_json() == reopened.effective_schedule_as_of(INSTRUMENT, T).to_json()
    assert reopened.effective_schedule_as_of(INSTRUMENT,T-timedelta(seconds=1)).state == "PIT_NOT_VISIBLE"
    reopened.close()


def revised(original, *, state=L.RESCHEDULED, stamp=T+timedelta(days=1), filing="synthetic-revision", parent=None):
    parent = parent or original.candidate.schedule_id
    source = nse_row(filing_identity=filing, lifecycle=state.value, revision_of_schedule_id=parent,
                     meeting_date="17-Oct-2026", meeting_date_iso="2026-10-17", disseminated=stamp.isoformat())
    data = {f: getattr(original.candidate, f) for f in original.candidate.__dataclass_fields__ if f not in {"schedule_id", "fingerprint"}}
    data.update(source_filing_identity=filing, source_fingerprint=source.fingerprint, revision_state=state,
                revision_of_schedule_id=parent, scheduled_date=date(2026,10,17), known_at=stamp,
                exchange_disseminated_at=stamp, hsi_received_at=stamp+timedelta(seconds=1))
    return make_official_earnings_schedule_candidate(**data), source


@pytest.mark.parametrize("state", [L.REVISED, L.RESCHEDULED, L.CANCELLED])
def test_append_only_explicit_revision_cancel_reschedule_pit(tmp_path, state):
    store = SQLiteEarningsScheduleStore(tmp_path/'schedule.db')
    original = normalized()
    store.save(original.candidate, source=original.source)
    c, r = revised(original,state=state)
    store.save(c,source=r)
    assert store.get(original.candidate.schedule_id) == original.candidate
    assert store.effective_schedule_as_of(INSTRUMENT,T).candidates == (original.candidate,)
    view = store.effective_schedule_as_of(INSTRUMENT,T+timedelta(days=2))
    assert view.candidates == (c,) and len(view.lineage_ids) == 2
    assert view.state == ("CANCELLED_CANDIDATE" if state == L.CANCELLED else "ONE_EXCHANGE_CANDIDATE")
    store.close()


def test_unresolved_parent_and_revision_fork_fail_closed(tmp_path):
    store = SQLiteEarningsScheduleStore(tmp_path/'schedule.db')
    original = normalized()
    c,r = revised(original)
    with pytest.raises(ValueError,match="REVISION_LINEAGE"):
        store.save(c,source=r)
    store.save(original.candidate,source=original.source)
    store.save(c,source=r)
    c2,r2 = revised(original,filing="another-revision")
    store.save(c2,source=r2)
    assert store.effective_schedule_as_of(INSTRUMENT,T+timedelta(days=2)).state == "EVIDENCE_CONFLICTED"
    store.close()


def test_same_filing_changed_data_quarantined_no_overwrite(tmp_path):
    store = SQLiteEarningsScheduleStore(tmp_path/'schedule.db')
    original = normalized()
    store.save(original.candidate,source=original.source)
    changed = normalized(nse_row(meeting_date="17-Oct-2026",meeting_date_iso="2026-10-17"),received=T+timedelta(days=1))
    assert store.save(changed.candidate,source=changed.source) == "EVIDENCE_CONFLICTED"
    assert store.get(original.candidate.schedule_id) == original.candidate
    assert store.effective_schedule_as_of(INSTRUMENT,T).state == "ONE_EXCHANGE_CANDIDATE"
    assert store.effective_schedule_as_of(INSTRUMENT,T+timedelta(days=2)).state == "EVIDENCE_CONFLICTED"
    assert store.save(changed.candidate,source=changed.source) == "EVIDENCE_CONFLICTED"
    assert len(store.effective_schedule_as_of(INSTRUMENT,T+timedelta(days=2)).conflict_ids) == 1
    store.close()


@pytest.mark.parametrize("conflict", [False,True])
def test_dual_exchange_semantics_not_raw_words_or_source_priority(tmp_path, conflict):
    store = SQLiteEarningsScheduleStore(tmp_path/'schedule.db')
    first = normalized(nse_row(purpose="Quarterly Results"))
    second = normalized(parse_bse_detail(bse_html(),BSE_URL)[0])
    if conflict:
        second = normalized(replace(second.source,raw=tuple(sorted((dict(second.source.raw)|{"meeting_date":"17/10/2026"}).items()))))
    for value in (second,first):
        store.save(value.candidate,source=value.source)
    view = store.effective_schedule_as_of(INSTRUMENT,T)
    assert len(view.candidates)==2 and len(view.lineage_ids)==2
    assert view.state == ("EVIDENCE_CONFLICTED" if conflict else "DUAL_EXCHANGE_AGREEMENT")
    store.close()


def test_different_filing_same_day_retained_and_tamper_rejected(tmp_path):
    store = SQLiteEarningsScheduleStore(tmp_path/'schedule.db')
    original = normalized()
    other = normalized(nse_row(filing_identity="distinct-filing"))
    for value in (original, other):
        store.save(value.candidate,source=value.source)
    assert len(store.effective_schedule_as_of(INSTRUMENT,T).lineage_ids) == 2
    with pytest.raises(ValueError):
        replace(original.candidate,fingerprint=FP)
    with pytest.raises(ValueError,match="SOURCE_LINEAGE"):
        store.save(original.candidate,source=other.source)
    store.close()


def test_gate_authority_and_forbidden_dependencies_unchanged():
    for name in ('earnings_schedule_source','earnings_schedule_ingestion','earnings_schedule_store'):
        path=Path('app/filings')/(name+'.py')
        source=path.read_text(encoding='utf-8')
        imports=[n.module for n in ast.walk(ast.parse(source)) if isinstance(n,ast.ImportFrom)]
        assert not any(m and m.startswith(('app.api','app.portfolio','app.rotation','app.gates.engine','app.ai','app.runtime')) for m in imports)
        assert 'datetime.now' not in source and 'CERT_NONE' not in source
        assert not any(x in source for x in ('yfinance','truedata','gemini','openai','INSERT INTO financial_facts','INSERT INTO corporate_filings'))
    assert 'gate_result' not in normalized().candidate.__dataclass_fields__


def test_bounded_real_transport_stream_closes_and_uses_no_credentials(monkeypatch):
    import app.filings.earnings_schedule_source as mod
    class Response:
        url, status, headers = NSE_RSS, 200, {}
        closed = False
        chunks = [b'x' * 65536] * 33
        def __enter__(self): return self
        def __exit__(self, *args): self.closed = True
        def read1(self, size): return self.chunks.pop(0)[:size] if self.chunks else b''
    response = Response()
    class Opener:
        def open(self, request, timeout):
            assert timeout == 10
            assert set(k.lower() for k in request.headers) == {'user-agent','accept-encoding'}
            return response
    monkeypatch.setattr(mod,'build_opener',lambda *args: Opener())
    with pytest.raises(mod.SourceFailure) as failure:
        BoundedOfficialTransport().get(NSE_RSS)
    assert failure.value.state == SourceState.SOURCE_RESPONSE_TOO_LARGE and response.closed


def test_public_redirect_never_promotes_private_host():
    from app.filings.earnings_schedule_source import _PublicRedirect
    with pytest.raises(ValueError):
        _PublicRedirect().redirect_request(None,None,302,'',{},'https://evil.test/secret')


def test_explicit_linked_xml_acquisition_is_one_bounded_request():
    transport = Fake(xbrl())
    source = NSEOfficialEarningsScheduleSource(transport)
    result = source.fetch_linked_prior_intimation(parse_nse_rss(rss())[0],retrieved_at=T)
    assert len(result.rows) == 1 and result.state == SourceState.SOURCE_PARTIAL
    assert transport.calls == [XML_URL]
    assert normalized(result.rows[0]).state == SourceState.TIMESTAMP_UNAVAILABLE


@pytest.mark.parametrize('text',['Cancelled financial results meeting','Meeting rescheduled to consider financial results'])
def test_no_guessed_cancel_reschedule_link(text):
    assert normalized(nse_row(details=text)).state == SourceState.REVISION_LINEAGE_UNRESOLVED


def test_nonresults_meeting_not_schedule_and_not_absence_clearance():
    row = parse_bse_detail(bse_html(details='to consider dividend'),BSE_URL)[0]
    assert classify(row).classification == P.AMBIGUOUS
    assert normalized(row).candidate is None
    assert normalized(nse_row(purpose='Dividend')).state == SourceState.SUCCESS_NO_QUALIFYING_ROWS


def test_conflicting_same_exchange_different_dates_and_tampered_view(tmp_path):
    store=SQLiteEarningsScheduleStore(tmp_path/'schedule.db')
    original=normalized()
    second=normalized(nse_row(filing_identity='another',meeting_date_iso='2026-10-17',meeting_date='17-Oct-2026'))
    for value in (original,second): store.save(value.candidate,source=value.source)
    assert store.effective_schedule_as_of(INSTRUMENT,T).state=='EVIDENCE_CONFLICTED'
    object.__setattr__(original.candidate,'known_at',T-timedelta(days=1))
    with pytest.raises(ValueError): original.candidate.visible_at(T)
    store.close()


def test_unresolved_exchange_received_not_used_as_dissemination():
    assert normalized(nse_row(disseminated='',received=T.isoformat())).candidate is None
    assert normalized(nse_row(received='12-Sep-2026 10:00:00')).state==SourceState.TIMESTAMP_UNAVAILABLE


def test_finite_query_and_cross_exchange_transport_guards():
    with pytest.raises(ValueError):
        NSEOfficialEarningsScheduleSource(Fake(rss())).fetch(retrieved_at=T,url=BSE_URL)
    value=NSEOfficialEarningsScheduleSource(Fake(rss(copies=129))).fetch(retrieved_at=T)
    assert value.state==SourceState.SOURCE_PARTIAL and value.reason=='ITEM_BOUND_EXCEEDED'


def test_publication_date_without_clock_cannot_be_resolved_by_timezone_rule(monkeypatch):
    import app.filings.earnings_schedule_ingestion as module
    def forbidden(*args, **kwargs):
        raise AssertionError('Date-only publication must not reach timezone resolution')
    monkeypatch.setattr(module,'resolve_filing_timestamp',forbidden)
    assert normalized(nse_row(disseminated='2026-09-12')).state==SourceState.TIMESTAMP_UNAVAILABLE
