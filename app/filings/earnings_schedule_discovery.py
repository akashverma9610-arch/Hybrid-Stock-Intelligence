"""Public discovery and exact-join inspection, not a schedule authority producer.

The observed inventories do not prove company/window completeness. No caller
flag can turn them into an absence certificate. Descriptive identity is checked
at supplied observation time, separately from historical publication authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from hashlib import sha256
from html.parser import HTMLParser
import re
from urllib.parse import parse_qs, urljoin, urlsplit

from app.filings.earnings_schedule_ingestion import normalize_schedule
from app.filings.earnings_schedule_source import (
    Fetch, MAX_BYTES, MAX_ITEMS, RawSchedule, SourceBatch, SourceFailure,
    SourceState, Transport, classify, parse_meeting_date, parse_nse_prior_intimation, public_url, utc,
)
from app.fundamentals.diagnostic_comparability import canonical_json, content_fingerprint
from app.gates.official_earnings_schedule_candidate import PurposeClassification, SourceExchange
from app.filings.earnings_schedule_identity import EarningsScheduleCanonicalIdentityBridge, IdentityState
from app.historical.security_master import HistoricalSecurityIdentity

BSE_CORPORATES = "https://m.bseindia.com/corporates.aspx"
VERSION = "official-earnings-discovery/v1"


class _PublicLinks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links, self.href, self.texts = [], None, []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.href, self.texts = dict(attrs).get("href"), []

    def handle_data(self, data):
        if self.href is not None:
            self.texts.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.href is not None:
            self.links.append((self.href, " ".join("".join(self.texts).split())))
            self.href = None


def parse_bse_discovery(body: bytes, url: str = BSE_CORPORATES) -> tuple[RawSchedule, ...]:
    public_url(url)
    if urlsplit(url).hostname != "m.bseindia.com" or urlsplit(url).path.lower() != "/corporates.aspx":
        raise ValueError("BSE_DISCOVERY_ROUTE_UNSUPPORTED")
    if len(body) > MAX_BYTES:
        raise SourceFailure(SourceState.SOURCE_RESPONSE_TOO_LARGE, "RESPONSE_SIZE_BOUND")
    parser = _PublicLinks()
    parser.feed(body.decode("utf-8-sig"))
    rows, seen = [], set()
    for href, subject in parser.links:
        reference = urljoin(url, href)
        if urlsplit(reference).path != "/MAnnDet.aspx":
            continue
        public_url(reference)
        if urlsplit(reference).hostname != "m.bseindia.com":
            raise ValueError("BSE_DISCOVERY_LINK_REJECTED")
        if reference in seen:
            # A repeated rendered link is not another filing. Conflicts are not
            # silently deduplicated or selected by input order.
            raise ValueError("BSE_DISCOVERY_DUPLICATE_LINK")
        seen.add(reference)
        q = parse_qs(urlsplit(reference).query)
        values = {"link": reference, "subject": subject, "filing_identity": q["newsid"][0],
                  "security_code": q.get("scrpcd", q.get("scrip_CD", []))[0],
                  "inventory_reference": url}
        rows.append(RawSchedule(SourceExchange.BSE, reference, tuple(sorted(values.items())), "bse-public-corporates/v1"))
    if len(rows) > MAX_ITEMS:
        raise SourceFailure(SourceState.SOURCE_PARTIAL, "ITEM_BOUND_EXCEEDED")
    if not rows:
        raise SourceFailure(SourceState.SOURCE_PARTIAL, "SOURCE_DISCOVERY_NOT_READY")
    return tuple(rows)


def discover_bse(transport: Transport, *, retrieved_at: datetime) -> SourceBatch:
    """One public recent-list GET. No desktop shell retry or private fallback."""
    point, checksum, status, size = utc(retrieved_at), None, None, 0
    try:
        response = transport.get(BSE_CORPORATES)
        if response.url not in {BSE_CORPORATES, BSE_CORPORATES.replace("corporates", "Corporates")}:
            raise ValueError("BSE_DISCOVERY_REDIRECT_REJECTED")
        status, size = response.status, min(len(response.body), MAX_BYTES + 1)
        if size > MAX_BYTES:
            raise SourceFailure(SourceState.SOURCE_RESPONSE_TOO_LARGE, "RESPONSE_SIZE_BOUND")
        checksum = "sha256:" + sha256(response.body).hexdigest()
        if status != 200:
            raise SourceFailure(SourceState.SOURCE_UNAVAILABLE, f"HTTP_{status}")
        rows = parse_bse_discovery(response.body, response.url)
        return SourceBatch(SourceExchange.BSE, BSE_CORPORATES, point, SourceState.SOURCE_PARTIAL,
                           "RECENT_LIST_WINDOW_COVERAGE_UNPROVEN", rows, checksum, status, size)
    except SourceFailure as exc:
        state, reason = exc.state, exc.reason
    except OSError:
        state, reason = SourceState.SOURCE_UNAVAILABLE, "TRANSPORT_FAILURE"
    except ValueError:
        state, reason = SourceState.SOURCE_MALFORMED, "SOURCE_SHAPE_UNSUPPORTED"
    return SourceBatch(SourceExchange.BSE, BSE_CORPORATES, point, state, reason, (), checksum, status, size)


@dataclass(frozen=True, slots=True)
class LinkedScheduleInspection:
    canonical_instrument_id: str
    source: RawSchedule
    observed_at: datetime
    identity_state: str
    identity_fingerprint: str | None
    purpose: PurposeClassification
    current_descriptive_ready: bool
    known_at_state: str
    reasons: tuple[str, ...]

    def __post_init__(self):
        self.source.__post_init__()
        object.__setattr__(self, "observed_at", utc(self.observed_at))
        resolved = self.identity_state == "EXACT_IDENTITY_RESOLVED"
        qualifying = self.purpose not in {PurposeClassification.AMBIGUOUS, PurposeClassification.NON_QUALIFYING}
        if (not re.fullmatch(r"NSE:IN[A-Z0-9]{9}[0-9]", self.canonical_instrument_id)
                or not isinstance(self.purpose, PurposeClassification)
                or self.identity_state not in {"EXACT_IDENTITY_RESOLVED", "IDENTITY_UNRESOLVED", "IDENTITY_CONFLICTED"}
                or resolved != (self.identity_fingerprint is not None)
                or (resolved and re.fullmatch(r"sha256:[0-9a-f]{64}", self.identity_fingerprint) is None)
                or type(self.current_descriptive_ready) is not bool
                or self.current_descriptive_ready != (resolved and qualifying and self.source.field("intimation_type") in {"New", "Original"})
                or self.known_at_state not in {"KNOWN_AT_NOT_STRICT_PIT", "TIMEZONE_RESOLVED_AUTHORITY_UNVERIFIED"}
                or self.reasons != tuple(sorted(set(self.reasons))) or self.known_at_state not in self.reasons
                or self.source.exchange != SourceExchange.NSE
                or not self.source.parser_version.startswith("nse-reg29-")):
            raise ValueError("EARNINGS_LINKED_INSPECTION_INVALID")

    @property
    def strict_pit_ready(self) -> bool:
        # Even a timezone-resolved existing candidate remains
        # UNVERIFIED_SOURCE_AUTHORITY; this repair cannot promote that status.
        return False

    @property
    def fingerprint(self) -> str:
        return content_fingerprint(self.to_json())

    def to_json(self) -> str:
        self.__post_init__()
        return canonical_json({"version": VERSION, "inspection": self,
                               "strict_pit_ready": False, "gate6_clearance": False,
                               "freshness": "POLICY_BLOCKED"})


def inspect_nse_join(inventory: RawSchedule, document: Fetch, *, canonical_instrument_id: str,
                     identities: tuple[HistoricalSecurityIdentity, ...] = (), observed_at: datetime,
                     identity_bridge: EarningsScheduleCanonicalIdentityBridge | None = None) -> LinkedScheduleInspection:
    """Reparse exact joined bytes; observation time never becomes known_at.

    Current descriptive identity does not authorize historical mapping reuse.
    Existing normalization independently checks identity at publication time.
    """
    point = utc(observed_at)
    if not re.fullmatch(r"NSE:IN[A-Z0-9]{9}[0-9]", canonical_instrument_id):
        raise ValueError("EARNINGS_CANONICAL_IDENTITY_INVALID")
    if document.status != 200:
        raise ValueError("NSE_JOIN_DOCUMENT_UNAVAILABLE")
    row = parse_nse_prior_intimation(document.body, inventory, document_url=document.url)
    if identity_bridge is not None and identities:
        raise ValueError("EARNINGS_IDENTITY_INPUT_AMBIGUOUS")
    bridge = identity_bridge or EarningsScheduleCanonicalIdentityBridge(identities=identities)
    selected = bridge.resolve_nse(row.field("symbol"), row.field("isin"), point)
    identity_state, identity_fp = "IDENTITY_UNRESOLVED", None
    if selected.resolution_state in {IdentityState.IDENTITY_CONFLICTED, IdentityState.AMBIGUOUS}:
        identity_state = "IDENTITY_CONFLICTED"
    elif selected.resolution_state == IdentityState.RESOLVED:
        if selected.canonical_instrument_id != canonical_instrument_id:
            identity_state = "IDENTITY_CONFLICTED"
        else:
            identity_state, identity_fp = "EXACT_IDENTITY_RESOLVED", selected.fingerprint
    purpose = classify(row).classification
    qualifying = purpose not in {PurposeClassification.AMBIGUOUS, PurposeClassification.NON_QUALIFYING}
    original = row.field("intimation_type") in {"New", "Original"}
    reasons = []
    if identity_fp is None:
        reasons.append(identity_state)
    if not qualifying:
        reasons.append("STRUCTURED_RESULTS_PURPOSE_UNPROVEN")
    if not original:
        reasons.append("EXACT_PARENT_FILING_REQUIRED")
    normalized = normalize_schedule(row, canonical_instrument_id=canonical_instrument_id,
                                    identity_bridge=bridge, retrieved_at=point)
    timestamp = normalized.timestamp_receipt
    known_state = ("TIMEZONE_RESOLVED_AUTHORITY_UNVERIFIED" if timestamp is not None
                   and timestamp.normalized_utc_timestamp is not None
                   and timestamp.normalized_utc_timestamp <= point else "KNOWN_AT_NOT_STRICT_PIT")
    reasons.append(known_state)
    return LinkedScheduleInspection(canonical_instrument_id, row, point, identity_state, identity_fp,
                                    purpose, identity_fp is not None and qualifying and original,
                                    known_state, tuple(sorted(reasons)))


def company_window_receipt(batch: SourceBatch, *, instrument: str, window_start: date,
                           window_end: date, inspections: tuple[LinkedScheduleInspection, ...] = ()) -> str:
    """Deterministic per-company local inspection of a *partial* inventory.

    Neither admitted discovery route currently implements company filters or
    complete pagination. Therefore no complete/no-event state is constructible.
    Query-success states are reserved until an actual source protocol proves them.
    """
    batch.__post_init__()
    if (not re.fullmatch(r"NSE:IN[A-Z0-9]{9}[0-9]", instrument)
            or type(window_start) is not date or type(window_end) is not date or window_end < window_start):
        raise ValueError("EARNINGS_COVERAGE_REQUEST_INVALID")
    fingerprints = tuple(sorted(x.fingerprint for x in inspections))
    if len(fingerprints) != len(set(fingerprints)):
        raise ValueError("EARNINGS_COVERAGE_DUPLICATE_INSPECTION")
    inventory_fps = {r.fingerprint for r in batch.rows}
    for x in inspections:
        if (x.canonical_instrument_id != instrument or x.observed_at < batch.retrieved_at
                or x.source.exchange != batch.exchange
                or x.source.field("inventory_fingerprint") not in inventory_fps):
            raise ValueError("EARNINGS_COVERAGE_SOURCE_JOIN_UNPROVEN")
    error = batch.state not in {SourceState.SOURCE_PARTIAL, SourceState.SUCCESS_WITH_ROWS,
                               SourceState.SUCCESS_NO_QUALIFYING_ROWS}
    identity_bad = any(x.identity_state != "EXACT_IDENTITY_RESOLVED" for x in inspections)
    state = ("SOURCE_FAILED" if error else "IDENTITY_UNRESOLVED" if identity_bad
             else "SOURCE_PARTIAL" if inspections else "WINDOW_COVERAGE_UNPROVEN")
    body = dict(version=VERSION, source=batch.exchange, source_url=batch.url, instrument=instrument,
                window_start=window_start.isoformat(), window_end=window_end.isoformat(),
                retrieved_at=batch.retrieved_at, query_state=state, source_state=batch.state,
                reason=batch.reason, source_fingerprint=batch.source_fingerprint, batch_fingerprint=batch.fingerprint,
                inspection_fingerprints=fingerprints, individually_queried=False,
                local_identity_inspection_attempted=True, pagination_complete=False,
                response_complete=False, window_applied_by_source=False, complete_success=False,
                current_descriptive_ready=sum(x.current_descriptive_ready and window_start <= parse_meeting_date(
                    x.source.field("meeting_date_iso")) <= window_end for x in inspections),
                strict_pit_ready=0, freshness="POLICY_BLOCKED", gate6_clearance=False)
    return canonical_json(body | {"fingerprint": content_fingerprint(body)})
