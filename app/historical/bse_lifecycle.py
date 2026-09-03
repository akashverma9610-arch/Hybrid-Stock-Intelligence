"""Bounded primary-BSE lifecycle notice ingestion.

This module preserves an official lifecycle document before attempting a
canonical-security link.  It deliberately has no company-name matching and
uses no current clock: the BSE notice's publication and effective timestamps
are supplied by the source document itself.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from hashlib import sha256
from html import unescape
import re
from typing import Iterable

from app.fundamentals.bse_collector import BseOfficialHttpResponse, BseOfficialHttpTransport
from app.historical.guard import manifest_fingerprint
from app.historical.security_master import HistoricalSecurityIdentity, HistoricalSecurityMasterStore, HistoricalSecurityStatus
from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily, CoreApiSnapshotRepository


CONTRACT_ID = "bse-primary-security-lifecycle-notice-ingestion"
CONTRACT_VERSION = "v1"
BSE_PRIMARY_SOURCE = "BSE_NOTICES_AND_CIRCULARS"


class BseLifecycleEventType(StrEnum):
    NAME_OR_SCRIP_ID_CHANGE = "NAME_OR_SCRIP_ID_CHANGE"
    DELISTING = "DELISTING"
    MERGER_OR_CESSATION = "MERGER_OR_CESSATION"
    LISTING = "LISTING"
    RELISTING = "RELISTING"
    SUSPENSION = "SUSPENSION"
    REVOCATION_OF_SUSPENSION = "REVOCATION_OF_SUSPENSION"


class BseLifecycleReceiptStatus(StrEnum):
    INSERTED = "INSERTED"
    ALREADY_PRESENT = "ALREADY_PRESENT"
    STAGED_UNRESOLVED = "STAGED_UNRESOLVED"
    EVIDENCE_CONFLICTED = "EVIDENCE_CONFLICTED"


@dataclass(frozen=True, slots=True)
class ExactCanonicalSecurityLink:
    """An exact, current mapping usable only to link—not date—a BSE notice."""

    canonical_instrument_id: str
    bse_scrip_code: str | None
    isin: str | None
    source_reference: str

    def __post_init__(self) -> None:
        if not self.canonical_instrument_id or not self.source_reference:
            raise ValueError("BSE_LIFECYCLE_CANONICAL_LINK_REQUIRED")
        if self.bse_scrip_code is not None and not re.fullmatch(r"\d{6}", self.bse_scrip_code):
            raise ValueError("BSE_LIFECYCLE_SCRIP_CODE_INVALID")
        if self.isin is not None and not re.fullmatch(r"[A-Z0-9]{12}", self.isin.upper()):
            raise ValueError("BSE_LIFECYCLE_ISIN_INVALID")
        if self.bse_scrip_code is None and self.isin is None:
            raise ValueError("BSE_LIFECYCLE_CANONICAL_LINK_KEY_REQUIRED")


@dataclass(frozen=True, slots=True)
class BsePrimaryLifecycleEvidence:
    notice_id: str
    source_reference: str
    content_fingerprint: str
    published_at: datetime
    effective_at: datetime
    event_type: BseLifecycleEventType
    bse_scrip_code: str | None
    isin: str | None
    symbol_before: str | None
    symbol_after: str | None
    company_name: str | None
    explicit_successor_reference: str | None = None
    source_kind: str = BSE_PRIMARY_SOURCE
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        if (not re.fullmatch(r"(?:\d{8}-\d{1,3}|COMPULSORY-DELISTED-[a-f0-9]{16,64})", self.notice_id)
                or not self.source_reference or not self.content_fingerprint.startswith("sha256:")
                or not _aware(self.published_at) or not _aware(self.effective_at)):
            raise ValueError("BSE_LIFECYCLE_EVIDENCE_INVALID")
        if self.bse_scrip_code is not None and not re.fullmatch(r"\d{6}", self.bse_scrip_code):
            raise ValueError("BSE_LIFECYCLE_SCRIP_CODE_INVALID")
        if self.isin is not None and not re.fullmatch(r"[A-Z0-9]{12}", self.isin.upper()):
            raise ValueError("BSE_LIFECYCLE_ISIN_INVALID")
        if self.bse_scrip_code is None and self.isin is None:
            raise ValueError("BSE_LIFECYCLE_EXACT_KEY_REQUIRED")
        if self.event_type is BseLifecycleEventType.NAME_OR_SCRIP_ID_CHANGE and not (self.symbol_before and self.symbol_after):
            raise ValueError("BSE_LIFECYCLE_CHANGE_SYMBOLS_REQUIRED")
        if self.source_kind != BSE_PRIMARY_SOURCE or self.contract_id != CONTRACT_ID or self.contract_version != CONTRACT_VERSION:
            raise ValueError("BSE_LIFECYCLE_CONTRACT_INVALID")

    @property
    def evidence_id(self) -> str:
        return "bse-lifecycle-evidence:" + _fingerprint(_evidence_manifest(self))[:32]


@dataclass(frozen=True, slots=True)
class BseLifecycleIngestionReceipt:
    evidence_id: str
    notice_id: str
    status: BseLifecycleReceiptStatus
    identity_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]
    fingerprint: str

    def __post_init__(self) -> None:
        if self.identity_ids != tuple(sorted(set(self.identity_ids))) or self.reason_codes != tuple(sorted(set(self.reason_codes))):
            raise ValueError("BSE_LIFECYCLE_RECEIPT_NONCANONICAL")
        if self.status in {BseLifecycleReceiptStatus.INSERTED, BseLifecycleReceiptStatus.ALREADY_PRESENT} and (not self.identity_ids or self.reason_codes):
            raise ValueError("BSE_LIFECYCLE_RECEIPT_LINKED_FIELDS_INVALID")
        if self.status in {BseLifecycleReceiptStatus.STAGED_UNRESOLVED, BseLifecycleReceiptStatus.EVIDENCE_CONFLICTED} and (self.identity_ids or not self.reason_codes):
            raise ValueError("BSE_LIFECYCLE_RECEIPT_UNLINKED_FIELDS_INVALID")
        if self.fingerprint != "sha256:" + manifest_fingerprint(**_receipt_manifest(self)):
            raise ValueError("BSE_LIFECYCLE_RECEIPT_FINGERPRINT_MISMATCH")


class BsePrimaryLifecycleEvidenceStore:
    def __init__(self, repository: CoreApiSnapshotRepository) -> None:
        self._repository = repository

    def evidence(self, evidence_id: str) -> BsePrimaryLifecycleEvidence | None:
        snapshot = self._repository.get_snapshot(evidence_id)
        return snapshot.payload if snapshot is not None and isinstance(snapshot.payload, BsePrimaryLifecycleEvidence) else None

    def save(self, value: BsePrimaryLifecycleEvidence) -> bool:
        existing = self.evidence(value.evidence_id)
        if existing is not None:
            if existing != value:
                raise ValueError("BSE_LIFECYCLE_EVIDENCE_ID_COLLISION")
            return False
        self._repository.save_snapshot(CoreApiSnapshot(
            value.evidence_id, CoreApiSnapshotFamily.HISTORICAL_SECURITY_LIFECYCLE_EVIDENCE, "v1",
            CONTRACT_ID, "sha256:" + _fingerprint(_evidence_manifest(value)), value.published_at, value,
        ))
        return True


class BsePrimaryLifecycleIngestor:
    """Append-only conversion of exact BSE lifecycle evidence to identities."""

    def __init__(self, *, evidence_store: BsePrimaryLifecycleEvidenceStore, identity_store: HistoricalSecurityMasterStore) -> None:
        self._evidence_store, self._identity_store = evidence_store, identity_store

    def ingest(self, evidence: BsePrimaryLifecycleEvidence, *, links: Iterable[ExactCanonicalSecurityLink]) -> BseLifecycleIngestionReceipt:
        inserted_evidence = self._evidence_store.save(evidence)
        matches = _exact_links(evidence, links)
        if not matches:
            return _receipt(evidence, BseLifecycleReceiptStatus.STAGED_UNRESOLVED, (), ("EXACT_CANONICAL_LINK_REQUIRED",))
        canonical_ids = {item.canonical_instrument_id for item in matches}
        if len(canonical_ids) != 1:
            return _receipt(evidence, BseLifecycleReceiptStatus.EVIDENCE_CONFLICTED, (), ("EXACT_CANONICAL_LINK_AMBIGUOUS",))
        identities = _identities(evidence, matches[0].canonical_instrument_id)
        saved: list[str] = []
        duplicate = not inserted_evidence
        for value in identities:
            snapshot_id = "historical-security:" + value.identity_id
            # Immutable snapshot semantics make immediate replay explicit,
            # rather than relying on an exception as normal flow.
            existing = self._identity_store.identity(value.identity_id)
            if existing is not None:
                if existing != value:
                    return _receipt(evidence, BseLifecycleReceiptStatus.EVIDENCE_CONFLICTED, (), ("IDENTITY_IMMUTABLE_CONFLICT",))
                duplicate = True
                saved.append(value.identity_id)
                continue
            self._identity_store.save_identity(value)
            saved.append(value.identity_id)
        return _receipt(evidence, BseLifecycleReceiptStatus.ALREADY_PRESENT if duplicate else BseLifecycleReceiptStatus.INSERTED, tuple(saved), ())


class BsePrimaryLifecycleSource:
    """Strict fixed-path BSE lifecycle-document source; no crawler is exposed."""

    def __init__(self, transport: BseOfficialHttpTransport) -> None:
        self._transport = transport

    def notice(self, notice_id: str) -> BsePrimaryLifecycleEvidence:
        return parse_bse_lifecycle_notice(self._transport.fetch_lifecycle_notice(notice_id))

    def compulsory_delisted_document(self) -> BseOfficialHttpResponse:
        """Fetch only the fixed official PDF; extraction is intentionally separate."""
        return self._transport.fetch_compulsory_delisted_list()


def parse_bse_lifecycle_notice(response: BseOfficialHttpResponse) -> BsePrimaryLifecycleEvidence:
    """Parse only one explicit lifecycle fact from an official BSE notice HTML.

    Missing fields are a source insufficiency, never an invitation to infer a
    security or dates from the present master.
    """
    try:
        text = _visible_text(response.body.decode("utf-8-sig"))
    except UnicodeDecodeError as error:
        raise ValueError("BSE_LIFECYCLE_NOTICE_NOT_UTF8") from error
    notice_id = _one(r"Notice\s+No\.?\s*(\d{8}-\d{1,3})", text)
    published = _parse_bse_date(_one(r"Notice\s+Date\s*([^\n]+?)(?=\s+(?:Category|Subject|Segment)\b|$)", text))
    event_type = _event_type(text)
    effective = _effective_date(text)
    code = _one_or_none(r"(?:Scrip\s+Code\s*:?\s*|Scrip\s+Code\s+Company\s+Name\s+(?:\d+\s+)?)?(\d{6})(?=\s*(?:\)|[A-Z]))", text)
    # The code pattern is deliberately conservative.  Notices without an
    # explicit code remain valid staged evidence only when an ISIN is present.
    isin = _one_or_none(r"\b(INE[A-Z0-9]{9})\b", text)
    if code is None and isin is None:
        raise ValueError("BSE_LIFECYCLE_NOTICE_EXACT_KEY_REQUIRED")
    before, after = _symbol_change(text) if event_type is BseLifecycleEventType.NAME_OR_SCRIP_ID_CHANGE else (None, None)
    name = _one_or_none(r"(?:Company\s+Name|shares\s+of)\s*:?\s*([A-Za-z][A-Za-z0-9 .,&()'-]{2,120})", text)
    return BsePrimaryLifecycleEvidence(
        notice_id=notice_id, source_reference=response.url,
        content_fingerprint="sha256:" + sha256(response.body).hexdigest(), published_at=published,
        effective_at=effective, event_type=event_type, bse_scrip_code=code,
        isin=isin.upper() if isin else None, symbol_before=before, symbol_after=after,
        company_name=name, explicit_successor_reference=None,
    )


def parse_compulsory_delisted_list_text(*, text: str, source_reference: str, published_at: datetime) -> tuple[BsePrimaryLifecycleEvidence, ...]:
    """Parse a text extraction of BSE's fixed compulsory-delisted list.

    PDF decoding is not a hidden dependency of the transport.  A caller must
    provide an auditable text extraction; name-only rows are rejected rather
    than fuzzy-linked.
    """
    if not _aware(published_at):
        raise ValueError("BSE_LIFECYCLE_PUBLISHED_TIME_REQUIRED")
    records: list[BsePrimaryLifecycleEvidence] = []
    for line in text.splitlines():
        match = re.fullmatch(r"\s*(?P<name>.+?)\s*\|\s*(?P<isin>INE[A-Z0-9]{9})\s*\|\s*(?P<date>[A-Za-z]+\s+\d{1,2},\s+\d{4})\s*", line)
        if match is None:
            continue
        material = "|".join((match.group("name"), match.group("isin"), match.group("date")))
        records.append(BsePrimaryLifecycleEvidence(
            notice_id="COMPULSORY-DELISTED-" + sha256(material.encode()).hexdigest()[:24], source_reference=source_reference,
            content_fingerprint="sha256:" + sha256(material.encode()).hexdigest(), published_at=published_at,
            effective_at=_parse_bse_date(match.group("date")), event_type=BseLifecycleEventType.DELISTING,
            bse_scrip_code=None, isin=match.group("isin"), symbol_before=None, symbol_after=None,
            company_name=match.group("name").strip(),
        ))
    return tuple(records)


def _identities(value: BsePrimaryLifecycleEvidence, canonical_instrument_id: str) -> tuple[HistoricalSecurityIdentity, ...]:
    seed = _fingerprint(_evidence_manifest(value))
    common = dict(canonical_instrument_id=canonical_instrument_id, isin=value.isin, exchange="BSE", series=None,
                  source=BSE_PRIMARY_SOURCE, as_of=value.published_at, version=CONTRACT_VERSION,
                  source_reference=value.source_reference, warnings=("LIFECYCLE_INTERVAL_PARTIAL",),
                  exchange_security_code=value.bse_scrip_code, lifecycle_event_id=value.evidence_id,
                  source_fingerprint=value.content_fingerprint)
    code_symbol = value.bse_scrip_code or value.isin
    if code_symbol is None:
        raise ValueError("BSE_LIFECYCLE_EXACT_KEY_REQUIRED")
    if value.event_type is BseLifecycleEventType.NAME_OR_SCRIP_ID_CHANGE:
        old_id = "bse-lifecycle-identity:" + sha256((seed + "|old").encode()).hexdigest()[:24]
        new_id = "bse-lifecycle-identity:" + sha256((seed + "|new").encode()).hexdigest()[:24]
        return (
            HistoricalSecurityIdentity(old_id, symbol=value.symbol_before or code_symbol, listed_from=None, listed_until=None,
                                       tradable_from=None, tradable_until=value.effective_at - timedelta(microseconds=1),
                                       symbol_effective_from=value.published_at, symbol_effective_to=value.effective_at - timedelta(microseconds=1),
                                       status=HistoricalSecurityStatus.ACTIVE, successor_identity_id=new_id, **common),
            HistoricalSecurityIdentity(new_id, symbol=value.symbol_after or code_symbol, listed_from=None, listed_until=None,
                                       tradable_from=value.effective_at, tradable_until=None, symbol_effective_from=value.effective_at,
                                       symbol_effective_to=None, status=HistoricalSecurityStatus.ACTIVE, predecessor_identity_id=old_id, **common),
        )
    status = {
        BseLifecycleEventType.DELISTING: HistoricalSecurityStatus.DELISTED,
        BseLifecycleEventType.MERGER_OR_CESSATION: HistoricalSecurityStatus.MERGED,
        BseLifecycleEventType.SUSPENSION: HistoricalSecurityStatus.SUSPENDED,
        BseLifecycleEventType.LISTING: HistoricalSecurityStatus.ACTIVE,
        BseLifecycleEventType.RELISTING: HistoricalSecurityStatus.RELISTED,
        BseLifecycleEventType.REVOCATION_OF_SUSPENSION: HistoricalSecurityStatus.ACTIVE,
    }[value.event_type]
    identity_id = "bse-lifecycle-identity:" + sha256((seed + "|event").encode()).hexdigest()[:24]
    return (HistoricalSecurityIdentity(
        identity_id, symbol=code_symbol, listed_from=value.effective_at if status in {HistoricalSecurityStatus.ACTIVE, HistoricalSecurityStatus.RELISTED} else None,
        listed_until=value.effective_at if status in {HistoricalSecurityStatus.DELISTED, HistoricalSecurityStatus.MERGED} else None,
        tradable_from=value.effective_at if status in {HistoricalSecurityStatus.ACTIVE, HistoricalSecurityStatus.RELISTED} else None,
        tradable_until=value.effective_at if status in {HistoricalSecurityStatus.DELISTED, HistoricalSecurityStatus.MERGED, HistoricalSecurityStatus.SUSPENDED} else None,
        symbol_effective_from=value.effective_at, symbol_effective_to=None, status=status, **common,
    ),)


def _exact_links(value: BsePrimaryLifecycleEvidence, links: Iterable[ExactCanonicalSecurityLink]) -> tuple[ExactCanonicalSecurityLink, ...]:
    matches = []
    for link in links:
        code_match = value.bse_scrip_code is not None and link.bse_scrip_code == value.bse_scrip_code
        isin_match = value.isin is not None and link.isin is not None and link.isin.upper() == value.isin.upper()
        # A link may be established by either exact exchange identifier.  When
        # both are supplied by the notice they must both agree.
        if (code_match or isin_match) and not ((value.bse_scrip_code and link.bse_scrip_code and not code_match) or (value.isin and link.isin and not isin_match)):
            matches.append(link)
    return tuple(sorted(matches, key=lambda item: (item.canonical_instrument_id, item.bse_scrip_code or "", item.isin or "")))


def _receipt(value, status, ids, reasons):
    canonical_ids, reason_codes = tuple(sorted(set(ids))), tuple(sorted(set(reasons)))
    body = dict(evidence_id=value.evidence_id, notice_id=value.notice_id, status=status, identity_ids=canonical_ids, reason_codes=reason_codes)
    return BseLifecycleIngestionReceipt(**body, fingerprint="sha256:" + manifest_fingerprint(**body))


def _event_type(text: str) -> BseLifecycleEventType:
    folded = text.upper()
    if "REVOCATION OF SUSPENSION" in folded:
        return BseLifecycleEventType.REVOCATION_OF_SUSPENSION
    if "SUSPENSION" in folded:
        return BseLifecycleEventType.SUSPENSION
    if "DELIST" in folded or "DISCONTINUATION OF TRADING" in folded:
        return BseLifecycleEventType.DELISTING
    if "AMALGAMATION" in folded or "MERGER" in folded or "CESSATION" in folded:
        return BseLifecycleEventType.MERGER_OR_CESSATION
    if "RELIST" in folded:
        return BseLifecycleEventType.RELISTING
    if "CHANGE IN" in folded and ("SCRIP" in folded or "NAME" in folded):
        return BseLifecycleEventType.NAME_OR_SCRIP_ID_CHANGE
    if "LISTING" in folded:
        return BseLifecycleEventType.LISTING
    raise ValueError("BSE_LIFECYCLE_EVENT_TYPE_UNSUPPORTED")


def _effective_date(text: str) -> datetime:
    patterns = (r"(?:with\s+effect\s+from|w\.e\.f\.?|effective\s+from)\s*(?:Friday,?\s*)?([A-Za-z]+\s+\d{1,2},\s+\d{4})",)
    for pattern in patterns:
        found = _one_or_none(pattern, text, flags=re.IGNORECASE)
        if found:
            return _parse_bse_date(found)
    raise ValueError("BSE_LIFECYCLE_EFFECTIVE_DATE_REQUIRED")


def _symbol_change(text: str) -> tuple[str, str]:
    found = re.search(r"(?:from|old)\s+(?:scrip\s*(?:id|code)?\s*)?['\"]?([A-Z][A-Z0-9-]{1,31})['\"]?\s+(?:to|new)\s+(?:scrip\s*(?:id|code)?\s*)?['\"]?([A-Z][A-Z0-9-]{1,31})['\"]?", text, flags=re.IGNORECASE)
    if found is None:
        raise ValueError("BSE_LIFECYCLE_CHANGE_SYMBOLS_REQUIRED")
    return found.group(1).upper(), found.group(2).upper()


def _visible_text(raw: str) -> str:
    text = re.sub(r"<(?:script|style)\b[^>]*>.*?</(?:script|style)>", " ", raw, flags=re.IGNORECASE | re.DOTALL)
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", text))).strip()


def _one(pattern: str, value: str, *, flags: int = 0) -> str:
    found = _one_or_none(pattern, value, flags=flags)
    if found is None:
        raise ValueError("BSE_LIFECYCLE_NOTICE_METADATA_REQUIRED")
    return found


def _one_or_none(pattern: str, value: str, *, flags: int = 0) -> str | None:
    values = tuple(dict.fromkeys(item.strip() for item in re.findall(pattern, value, flags)))
    return values[0] if len(values) == 1 else None


def _parse_bse_date(value: str) -> datetime:
    for pattern in ("%d %b %Y", "%B %d, %Y", "%d %B %Y"):
        try:
            return datetime.strptime(value.strip(), pattern).replace(tzinfo=UTC)
        except ValueError:
            pass
    raise ValueError("BSE_LIFECYCLE_DATE_INVALID")


def _evidence_manifest(value: BsePrimaryLifecycleEvidence) -> dict[str, object]:
    return {name: getattr(value, name).astimezone(UTC).isoformat() if isinstance(getattr(value, name), datetime) else getattr(value, name).value if isinstance(getattr(value, name), StrEnum) else getattr(value, name) for name in value.__dataclass_fields__}


def _receipt_manifest(value: BseLifecycleIngestionReceipt) -> dict[str, object]:
    return {name: getattr(value, name).value if isinstance(getattr(value, name), StrEnum) else getattr(value, name) for name in value.__dataclass_fields__ if name != "fingerprint"}


def _fingerprint(values: dict[str, object]) -> str:
    return manifest_fingerprint(**values)


def _aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


__all__ = (
    "BSE_PRIMARY_SOURCE", "CONTRACT_ID", "CONTRACT_VERSION", "BseLifecycleEventType", "BseLifecycleIngestionReceipt",
    "BseLifecycleReceiptStatus", "BsePrimaryLifecycleEvidence", "BsePrimaryLifecycleEvidenceStore", "BsePrimaryLifecycleIngestor",
    "BsePrimaryLifecycleSource", "ExactCanonicalSecurityLink", "parse_bse_lifecycle_notice", "parse_compulsory_delisted_list_text",
)
