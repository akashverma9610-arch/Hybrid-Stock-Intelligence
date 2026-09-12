"""Bounded public exchange schedule acquisition; never an absence certificate.

NSE's published rolling RSS and its directly linked prior-intimation XML are
admitted representations. BSE's public mobile announcement detail is admitted;
the current desktop board-meeting shell is not a usable discovery feed.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from hashlib import sha256
from html.parser import HTMLParser
import re
import socket
import ssl
from time import monotonic
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
import xml.etree.ElementTree as ET

from app.fundamentals.diagnostic_comparability import canonical_json, content_fingerprint
from app.gates.official_earnings_schedule_candidate import PurposeClassification, SourceExchange


VERSION = "official-earnings-schedule-source/v1"
CLASSIFIER_VERSION = "official-results-purpose/v1"
NSE_RSS = "https://nsearchives.nseindia.com//content/RSS/Board_Meetings.xml"
BSE_BOARD = "https://www.bseindia.com/corporates/board_meeting.aspx"
MAX_BYTES = 2 * 1024 * 1024
TIMEOUT_SECONDS = 10
MAX_ITEMS = 128


class SourceState(StrEnum):
    SUCCESS_WITH_ROWS = "SUCCESS_WITH_ROWS"
    SUCCESS_NO_QUALIFYING_ROWS = "SUCCESS_NO_QUALIFYING_ROWS"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    SOURCE_MALFORMED = "SOURCE_MALFORMED"
    SOURCE_RESPONSE_TOO_LARGE = "SOURCE_RESPONSE_TOO_LARGE"
    SOURCE_PARTIAL = "SOURCE_PARTIAL"
    IDENTITY_UNRESOLVED = "IDENTITY_UNRESOLVED"
    PURPOSE_AMBIGUOUS = "PURPOSE_AMBIGUOUS"
    TIMESTAMP_UNAVAILABLE = "TIMESTAMP_UNAVAILABLE"
    REVISION_LINEAGE_UNRESOLVED = "REVISION_LINEAGE_UNRESOLVED"


def utc(value: datetime) -> datetime:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("EARNINGS_SOURCE_AWARE_TIMESTAMP_REQUIRED")
    return value.astimezone(UTC)


def public_url(url: str) -> str:
    """Exact observed public routes, not an arbitrary official-host HTTP proxy."""
    p = urlsplit(url)
    if (p.scheme != "https" or p.username or p.password or p.port not in (None, 443)
            or p.fragment or "\\" in url or any(ord(c) < 32 for c in url)):
        raise ValueError("EARNINGS_SOURCE_URL_REJECTED")
    allowed = False
    if p.hostname == "nsearchives.nseindia.com" and not p.query:
        allowed = p.path == "//content/RSS/Board_Meetings.xml" or bool(re.fullmatch(
            r"/corporate/xbrl/PRIOR_INTIMATION_[A-Za-z0-9_]+\.xml", p.path))
    if p.hostname == "www.nseindia.com" and not p.query:
        allowed = p.path == "/companies-listing/corporate-filings-board-meetings"
    if p.hostname == "www.bseindia.com" and not p.query:
        allowed = p.path in ("/corporates/board_meeting.aspx", "/corporates/board_meeting")
    if p.hostname == "m.bseindia.com" and p.path == "/MAnnDet.aspx":
        q = parse_qs(p.query, keep_blank_values=True)
        allowed = (set(q) == {"Form", "newsid", "scrpcd"} and q["Form"] == ["STR"]
                   and len(q["newsid"]) == len(q["scrpcd"]) == 1
                   and re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", q["newsid"][0])
                   and re.fullmatch(r"[0-9]{6}", q["scrpcd"][0]))
    if not allowed:
        raise ValueError("EARNINGS_SOURCE_URL_REJECTED")
    return url


@dataclass(frozen=True, slots=True)
class Fetch:
    url: str
    status: int
    body: bytes


class Transport(Protocol):
    def get(self, url: str) -> Fetch: ...


class SourceFailure(Exception):
    def __init__(self, state: SourceState, reason: str):
        self.state, self.reason = state, reason
        super().__init__(reason)


class _PublicRedirect(HTTPRedirectHandler):
    max_redirections = 2
    max_repeats = 1

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class BoundedOfficialTransport:
    """One GET, no cookies/auth/retries, verified TLS, bounded streaming."""
    def get(self, url: str) -> Fetch:
        public_url(url)
        started = monotonic()
        try:
            req = Request(url, headers={"User-Agent": "HSI-official-schedule/1.0", "Accept-Encoding": "identity"})
            with build_opener(_PublicRedirect()).open(req, timeout=TIMEOUT_SECONDS) as response:
                public_url(response.url)
                if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                    raise SourceFailure(SourceState.SOURCE_MALFORMED, "ENCODING_UNSUPPORTED")
                length = response.headers.get("Content-Length")
                if length is not None and int(length) > MAX_BYTES:
                    raise SourceFailure(SourceState.SOURCE_RESPONSE_TOO_LARGE, "RESPONSE_SIZE_BOUND")
                chunks, size = [], 0
                while True:
                    if monotonic() - started > TIMEOUT_SECONDS:
                        raise TimeoutError
                    chunk = response.read1(min(65536, MAX_BYTES + 1 - size))
                    size += len(chunk)
                    if size > MAX_BYTES:
                        raise SourceFailure(SourceState.SOURCE_RESPONSE_TOO_LARGE, "RESPONSE_SIZE_BOUND")
                    if not chunk:
                        break
                    chunks.append(chunk)
                return Fetch(response.url, response.status, b"".join(chunks))
        except HTTPError as exc:
            raise SourceFailure(SourceState.SOURCE_UNAVAILABLE, f"HTTP_{exc.code}") from None
        except (TimeoutError, socket.timeout):
            raise SourceFailure(SourceState.SOURCE_UNAVAILABLE, "TIMEOUT") from None
        except (URLError, ssl.SSLError, OSError):
            raise SourceFailure(SourceState.SOURCE_UNAVAILABLE, "NETWORK_OR_TLS_UNAVAILABLE") from None


@dataclass(frozen=True, slots=True)
class RawSchedule:
    exchange: SourceExchange
    reference: str
    raw: tuple[tuple[str, str], ...]
    parser_version: str

    def __post_init__(self):
        public_url(self.reference)
        if (not isinstance(self.exchange, SourceExchange) or not self.parser_version
                or type(self.raw) is not tuple or not self.raw
                or any(type(x) is not tuple or len(x) != 2 or any(type(s) is not str for s in x) for x in self.raw)
                or self.raw != tuple(sorted(self.raw)) or len({k for k, _ in self.raw}) != len(self.raw)
                or any(not k or len(v) > 65536 for k, v in self.raw)):
            raise ValueError("EARNINGS_SOURCE_RAW_INVALID")

    def field(self, name: str) -> str | None:
        return dict(self.raw).get(name)

    @property
    def fingerprint(self) -> str:
        return content_fingerprint(self)


@dataclass(frozen=True, slots=True)
class SourceBatch:
    exchange: SourceExchange
    url: str
    retrieved_at: datetime
    state: SourceState
    reason: str
    rows: tuple[RawSchedule, ...]
    source_fingerprint: str | None
    http_status: int | None
    bytes_received: int

    def __post_init__(self):
        public_url(self.url)
        object.__setattr__(self, "retrieved_at", utc(self.retrieved_at))
        if (not isinstance(self.exchange, SourceExchange) or not isinstance(self.state, SourceState)
                or type(self.rows) is not tuple or not self.reason
                or self.bytes_received < 0 or self.bytes_received > MAX_BYTES + 1
                or (self.source_fingerprint is not None and re.fullmatch(r"sha256:[0-9a-f]{64}", self.source_fingerprint) is None)
                or any(row.exchange != self.exchange for row in self.rows)
                or (self.rows and self.state not in {SourceState.SUCCESS_WITH_ROWS, SourceState.SOURCE_PARTIAL})):
            raise ValueError("EARNINGS_SOURCE_BATCH_INVALID")

    @property
    def fingerprint(self) -> str:
        return content_fingerprint(self)

    def to_json(self) -> str:
        return canonical_json(self)


@dataclass(frozen=True, slots=True)
class PurposeReceipt:
    raw_purpose: str | None
    raw_details: str | None
    classification: PurposeClassification
    rule: str
    source_fingerprint: str
    version: str = CLASSIFIER_VERSION


def classify(row: RawSchedule) -> PurposeReceipt:
    """Exact labels, or one explicit affirmative bounded results clause.

    Ambiguous negation/conditional/cancellation text is not semantically guessed.
    The original source text is always retained independently of normalization.
    """
    purpose, details = row.field("purpose"), row.field("details")
    norm = lambda s: " ".join((s or "").upper().replace("-", " ").split())
    p, d = norm(purpose), norm(details)
    labels = {
        "FINANCIAL RESULTS": PurposeClassification.FINANCIAL_RESULTS_UNSPECIFIED,
        "QUARTERLY": PurposeClassification.QUARTERLY_FINANCIAL_RESULTS,
        "HALF YEARLY": PurposeClassification.HALF_YEARLY_FINANCIAL_RESULTS,
        "ANNUAL": PurposeClassification.ANNUAL_FINANCIAL_RESULTS,
        "AUDITED": PurposeClassification.AUDITED_FINANCIAL_RESULTS,
        "UNAUDITED": PurposeClassification.UNAUDITED_FINANCIAL_RESULTS,
    }
    exact = {"FINANCIAL RESULTS": labels["FINANCIAL RESULTS"]}
    for label, value in labels.items():
        if label != "FINANCIAL RESULTS":
            exact[label + " RESULTS"] = exact[label + " FINANCIAL RESULTS"] = value
    tokens = tuple(t.strip() for t in p.split("/"))
    results = {exact[t] for t in tokens if t in exact}
    ambiguous = bool(re.search(r"\b(NOT|NO|MAY|MIGHT|IF|CANCELLED|CANCELED|POSTPONED|WITHDRAWN)\b", p + " " + d))
    status, rule = PurposeClassification.AMBIGUOUS, "EXPLICIT_RESULTS_REQUIRED"
    if not ambiguous and len(results) == 1 and all(t in exact or t == "DIVIDEND" for t in tokens):
        status, rule = next(iter(results)), "EXACT_STRUCTURED_RESULTS_LABEL"
    elif not ambiguous:
        match = re.search(r"\b(?:CONSIDER AND APPROVE|CONSIDER|APPROVE|TAKE ON RECORD) (?:THE )?(?:(UNAUDITED|AUDITED|QUARTERLY|HALF YEARLY|ANNUAL) )?FINANCIAL RESULTS?\b", d)
        if match:
            status, rule = labels[match[1] or "FINANCIAL RESULTS"], "EXPLICIT_AFFIRMATIVE_RESULTS_CLAUSE"
        elif p in {"DIVIDEND", "FUND RAISING", "FUND RAISE", "BONUS", "PREFERENTIAL ISSUE", "BUYBACK", "AGM", "INVESTOR MEET", "AMALGAMATION", "OTHER BUSINESS MATTERS"}:
            status, rule = PurposeClassification.NON_QUALIFYING, "EXACT_NON_RESULTS_PURPOSE"
    return PurposeReceipt(purpose, details, status, rule, row.fingerprint)


def _xml(body: bytes):
    if len(body) > MAX_BYTES:
        raise SourceFailure(SourceState.SOURCE_RESPONSE_TOO_LARGE, "RESPONSE_SIZE_BOUND")
    # UTF-8 only; reject DTD/entity declarations before any XML processing.
    text = body.decode("utf-8-sig")
    if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper() or "\x00" in text:
        raise ValueError("XML_DECLARATION_REJECTED")
    return ET.fromstring(text)


def _raw(exchange, reference, values, version):
    return RawSchedule(exchange, reference, tuple(sorted(values.items())), version)


def parse_nse_rss(body: bytes) -> tuple[RawSchedule, ...]:
    root = _xml(body)
    channel = root.find("channel")
    if root.tag != "rss" or channel is None or channel.findtext("title") != "NSE News - Board Meetings":
        raise ValueError("NSE_RSS_SHAPE_UNSUPPORTED")
    items = channel.findall("item")
    if len(items) > MAX_ITEMS:
        raise SourceFailure(SourceState.SOURCE_PARTIAL, "ITEM_BOUND_EXCEEDED")
    rows = []
    for item in items:
        values = {}
        for key in ("title", "link", "description", "pubDate"):
            nodes = item.findall(key)
            if len(nodes) != 1 or not nodes[0].text:
                raise ValueError("NSE_RSS_ITEM_INCOMPLETE")
            values[key] = nodes[0].text
        # PDF links are raw lineage only. No PDF inference or automatic download.
        p = urlsplit(values["link"])
        if p.scheme != "https" or p.hostname != "nsearchives.nseindia.com" or p.username or p.password:
            raise ValueError("NSE_RSS_LINK_REJECTED")
        match = re.fullmatch(r"(.+?)\s*\|Meeting Date: ([0-9]{2}-[A-Za-z]{3}-[0-9]{4})", values["description"])
        if not match:
            raise ValueError("NSE_RSS_DESCRIPTION_UNSUPPORTED")
        values.update(purpose=match[1].strip(), meeting_date=match[2], disseminated=values["pubDate"])
        rows.append(_raw(SourceExchange.NSE, NSE_RSS, values, "nse-board-rss/v1"))
    return tuple(rows)


def parse_nse_prior_intimation(body: bytes, rss: RawSchedule) -> RawSchedule:
    """Join only the exact XML href published in this RSS item, never names."""
    reference = public_url(rss.field("link") or "")
    root = _xml(body)
    if root.tag != "{http://www.xbrl.org/2003/instance}xbrl":
        raise ValueError("NSE_PRIOR_INTIMATION_SHAPE_UNSUPPORTED")
    namespace = "{https://www.sebi.gov.in/xbrl/2023-05-31/in-capmkt}"
    mapping = {"NSESymbol": "symbol", "ISIN": "isin", "NameOfTheCompany": "company",
               "TypeOfMeeting": "meeting_type", "TypeOfIntimation": "intimation_type",
               "DateOfProposedMeeting": "meeting_date_iso", "Agenda1": "purpose"}
    values = dict(rss.raw)
    for key, output in mapping.items():
        found = root.findall(namespace + key)
        if len(found) != 1 or not found[0].text:
            raise ValueError("NSE_PRIOR_INTIMATION_FIELD_UNSUPPORTED")
        values[output] = found[0].text
    if values["meeting_type"] != "Board Meeting" or parse_meeting_date(values["meeting_date"]) != date.fromisoformat(values["meeting_date_iso"]):
        raise ValueError("NSE_PRIOR_INTIMATION_RSS_CONFLICT")
    # Unknown additional agendas are not silently ignored.
    if any(e.tag.startswith(namespace + "Agenda") and e.tag != namespace + "Agenda1" for e in root):
        raise ValueError("NSE_MULTIPLE_AGENDAS_UNSUPPORTED")
    values["xml_checksum"] = "sha256:" + sha256(body).hexdigest()
    return _raw(SourceExchange.NSE, reference, values, "nse-reg29-2023-05-31/v1")


class _BseCells(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.cells, self.stack = [], []

    def handle_starttag(self, tag, attrs):
        if tag == "td":
            self.stack.append((dict(attrs).get("class", ""), []))

    def handle_data(self, data):
        if self.stack:
            self.stack[-1][1].append(data)

    def handle_endtag(self, tag):
        if tag == "td" and self.stack:
            cls, texts = self.stack.pop()
            value = " ".join("".join(texts).split())
            if value:
                self.cells.append((cls, value))


def parse_bse_detail(body: bytes, url: str) -> tuple[RawSchedule, ...]:
    public_url(url)
    if urlsplit(url).hostname != "m.bseindia.com":
        if b"<html" not in body.lower():
            raise ValueError("BSE_NON_HTML_RESPONSE")
        raise SourceFailure(SourceState.SOURCE_PARTIAL, "SOURCE_TRANSPORT_NOT_READY")
    parser = _BseCells()
    parser.feed(body.decode("utf-8-sig"))
    values = {}
    labels = {"Security Code": "security_code", "Company": "company",
              "Exchange Received Time": "received", "Exchange Disseminated Time": "disseminated"}
    for (cls, text), (next_cls, value) in zip(parser.cells, parser.cells[1:]):
        if cls == "resultgreyhead" and text in labels and next_cls == "resultleft":
            key = labels[text]
            if key in values:
                raise ValueError("BSE_DETAIL_DUPLICATE_FIELD")
            values[key] = value
    subjects = [v.split("|")[0].strip() for c, v in parser.cells if c == "ann01" and v.startswith("Board Meeting Intimation")]
    details = [v for c, v in parser.cells if c == "ann02" and "has informed BSE" in v]
    if len(subjects) != 1 or len(details) != 1 or "security_code" not in values:
        raise ValueError("BSE_DETAIL_SHAPE_UNSUPPORTED")
    query = parse_qs(urlsplit(url).query)
    if values["security_code"] != query["scrpcd"][0]:
        raise ValueError("BSE_DETAIL_SECURITY_CONFLICT")
    dates = re.findall(r"\bis scheduled on ([0-9]{2}/[0-9]{2}/[0-9]{4})\b", details[0])
    if len(dates) != 1:
        raise ValueError("BSE_MEETING_DATE_UNAVAILABLE")
    values.update(purpose=subjects[0], details=details[0], meeting_date=dates[0], filing_identity=query["newsid"][0])
    return (_raw(SourceExchange.BSE, url, values, "bse-mobile-reg29-detail/v1"),)


def parse_meeting_date(text: str) -> date:
    if re.fullmatch(r"\d{2}-[A-Za-z]{3}-\d{4}", text):
        d, m, y = text.split("-")
        months = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")
        return date(int(y), months.index(m.upper()) + 1, int(d))
    if re.fullmatch(r"\d{2}/\d{2}/\d{4}", text):
        d, m, y = text.split("/")
        return date(int(y), int(m), int(d))
    return date.fromisoformat(text)


class _OfficialSource:
    exchange: SourceExchange
    url: str

    def __init__(self, transport: Transport):
        self.transport = transport

    def fetch(self, *, retrieved_at: datetime, url: str | None = None) -> SourceBatch:
        target = public_url(url or self.url)
        host = urlsplit(target).hostname
        if (self.exchange == SourceExchange.NSE and host not in {"www.nseindia.com", "nsearchives.nseindia.com"}
                or self.exchange == SourceExchange.BSE and host not in {"www.bseindia.com", "m.bseindia.com"}):
            raise ValueError("EARNINGS_SOURCE_EXCHANGE_HOST_MISMATCH")
        point, checksum, status, size = utc(retrieved_at), None, None, 0
        try:
            response = self.transport.get(target)
            public_url(response.url)
            if urlsplit(response.url).hostname != host:
                raise ValueError("EARNINGS_SOURCE_REDIRECT_REJECTED")
            status, size = response.status, min(len(response.body), MAX_BYTES + 1)
            if size > MAX_BYTES:
                raise SourceFailure(SourceState.SOURCE_RESPONSE_TOO_LARGE, "RESPONSE_SIZE_BOUND")
            checksum = "sha256:" + sha256(response.body).hexdigest()
            if status != 200:
                raise SourceFailure(SourceState.SOURCE_UNAVAILABLE, f"HTTP_{status}")
            rows = parse_nse_rss(response.body) if self.exchange == SourceExchange.NSE else parse_bse_detail(response.body, target)
            # Neither observed representation establishes complete window coverage.
            return SourceBatch(self.exchange, target, point, SourceState.SOURCE_PARTIAL,
                               "ROLLING_FEED_NOT_COMPLETE" if self.exchange == SourceExchange.NSE else "DETAIL_NOT_DISCOVERY_COVERAGE",
                               rows, checksum, status, size)
        except SourceFailure as exc:
            return SourceBatch(self.exchange, target, point, exc.state, exc.reason, (), checksum, status, size)
        except (TimeoutError, OSError, URLError):
            return SourceBatch(self.exchange, target, point, SourceState.SOURCE_UNAVAILABLE, "TRANSPORT_FAILURE", (), checksum, status, size)
        except (ValueError, ET.ParseError):
            return SourceBatch(self.exchange, target, point, SourceState.SOURCE_MALFORMED, "SOURCE_SHAPE_UNSUPPORTED", (), checksum, status, size)


class NSEOfficialEarningsScheduleSource(_OfficialSource):
    exchange, url = SourceExchange.NSE, NSE_RSS

    def fetch_linked_prior_intimation(self, rss: RawSchedule, *, retrieved_at: datetime) -> SourceBatch:
        """One explicitly selected RSS-linked XML; never an automatic broad crawl."""
        rss.__post_init__()
        target = public_url(rss.field("link") or "")
        if rss.parser_version != "nse-board-rss/v1" or rss.reference != NSE_RSS or rss.exchange != SourceExchange.NSE:
            raise ValueError("NSE_RSS_PROVENANCE_REQUIRED")
        point, checksum, status, size = utc(retrieved_at), None, None, 0
        try:
            response = self.transport.get(target)
            if response.url != target:
                raise ValueError("NSE_LINKED_XML_REDIRECT_REJECTED")
            status, size = response.status, min(len(response.body), MAX_BYTES + 1)
            if size > MAX_BYTES:
                raise SourceFailure(SourceState.SOURCE_RESPONSE_TOO_LARGE, "RESPONSE_SIZE_BOUND")
            checksum = "sha256:" + sha256(response.body).hexdigest()
            if status != 200:
                raise SourceFailure(SourceState.SOURCE_UNAVAILABLE, f"HTTP_{status}")
            row = parse_nse_prior_intimation(response.body, rss)
            return SourceBatch(self.exchange, target, point, SourceState.SOURCE_PARTIAL, "LINKED_FILING_NOT_DISCOVERY_COVERAGE", (row,), checksum, status, size)
        except SourceFailure as exc:
            return SourceBatch(self.exchange, target, point, exc.state, exc.reason, (), checksum, status, size)
        except (TimeoutError, OSError, URLError):
            return SourceBatch(self.exchange, target, point, SourceState.SOURCE_UNAVAILABLE, "TRANSPORT_FAILURE", (), checksum, status, size)
        except (ValueError, ET.ParseError):
            return SourceBatch(self.exchange, target, point, SourceState.SOURCE_MALFORMED, "SOURCE_SHAPE_UNSUPPORTED", (), checksum, status, size)


class BSEOfficialEarningsScheduleSource(_OfficialSource):
    exchange, url = SourceExchange.BSE, BSE_BOARD
