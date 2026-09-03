"""Bounded BSE-official XBRL financial-results adapter.

This is an exchange-edge adapter only.  It reads the public BSE result page
and the XML documents it links, verifies an exact ISIN before any persistence,
and writes the pre-existing canonical filing and financial-fact contracts.
It never reads PDFs, derives EBITDA/cash-flow, or invokes diagnostics.
"""
from __future__ import annotations

import hashlib
import csv
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from html.parser import HTMLParser
from io import StringIO
from pathlib import Path
from typing import Callable, Iterable, Protocol
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from app.data_sources.models import FundamentalFactKind
from app.filings.models import (
    AttachmentParseStatus, CorporateFiling, FilingAttachment,
    FilingTextAvailability, FilingType, FinancialResultMetadata,
    PrimarySourceQuality,
)
from app.filings.store import CorporateFilingsStore, FilingWriteOutcome
from app.fundamentals.models import (
    FinancialFact, FinancialMetric, FinancialPeriodType, FinancialQualityFlag,
    FinancialValueBasis, NumericScale, StatementScope, StructuredFinancialRecord,
)
from app.fundamentals.service import FinancialFactNormalizationService
from app.fundamentals.store import FinancialFactStore, FinancialFactWriteOutcome
from app.market_data.models import Exchange, InstrumentIdentity, MarketDataProvenance, ProviderInstrumentMapping


BSE_OFFICIAL_PROVIDER = "BSE_OFFICIAL"
BSE_RESULT_PAGE = "https://www.bseindia.com/corporates/Comp_Results.aspx?Code={security_code}"
BSE_RESULT_ARCHIVE = "https://api.bseindia.com/BseIndiaAPI/api/Result_Arch_Download/w?scrip_cd={security_code}"
_BSE_ORIGIN = "https://www.bseindia.com/"
_IST = ZoneInfo("Asia/Kolkata")


class BseTimestampStatus(StrEnum):
    DOCUMENTED = "DOCUMENTED"
    EXCHANGE_LOCAL_ASSUMPTION = "EXCHANGE_LOCAL_ASSUMPTION"
    UNKNOWN = "UNKNOWN"


class BsePublicationAvailability(StrEnum):
    SOURCE_PUBLICATION_KNOWN = "SOURCE_PUBLICATION_KNOWN"
    SYSTEM_FIRST_OBSERVED = "SYSTEM_FIRST_OBSERVED"


class BseOfficialError(ValueError):
    """A source/identity/timing error that must fail closed before persistence."""


@dataclass(frozen=True, slots=True)
class BseSecurityIdentity:
    canonical_instrument_id: str
    isin: str
    security_code: str
    security_name: str | None
    source_reference: str
    mapping_method: str
    effective_as_of: datetime

    def __post_init__(self) -> None:
        if not all((self.canonical_instrument_id, self.isin, self.security_code, self.source_reference, self.mapping_method)):
            raise ValueError("BSE security identity fields are required.")
        if self.effective_as_of.tzinfo is None:
            raise ValueError("BSE security identity effective_as_of must be timezone-aware.")

    def provider_mapping(self) -> ProviderInstrumentMapping:
        return ProviderInstrumentMapping(BSE_OFFICIAL_PROVIDER, self.security_code, None, "bse-xbrl-v1", "BSE_EQ")


@dataclass(frozen=True, slots=True)
class BseResultMetadata:
    security_code: str
    financial_year: str
    quarter_label: str
    filing_type: str
    status: str
    filing_at: datetime
    revised_at: datetime | None
    revision_reason: str | None
    scope: StatementScope
    period_end: datetime
    period_type: FinancialPeriodType
    value_basis: FinancialValueBasis
    xbrl_url: str
    source_page: str
    timestamp_status: BseTimestampStatus

    @property
    def is_revised(self) -> bool:
        return self.status.upper() == "REVISED" or self.revised_at is not None


@dataclass(frozen=True, slots=True)
class BseResultMetadataAliases:
    """Every archive-row identity referring to one official XBRL URL.

    ``preferred`` is retained solely for legacy discovery ordering.  Context
    facts are never derived from it; all aliases remain available for audit
    lineage.
    """

    document_url: str
    aliases: tuple[BseResultMetadata, ...]
    preferred: BseResultMetadata


@dataclass(frozen=True, slots=True)
class BseXbrlDocument:
    security_code: str
    isin: str
    security_name: str | None
    schema_version: str | None
    audit_status: str | None
    scope: StatementScope | None
    currency: str | None
    scale: NumericScale | None
    facts: tuple[tuple[FinancialMetric, Decimal], ...]
    source_url: str
    checksum: str
    raw_concepts: tuple[str, ...]
    warnings: tuple[str, ...] = ()
    contexts: tuple["BseXbrlContext", ...] = ()
    context_facts: tuple["BseXbrlContextFact", ...] = ()


@dataclass(frozen=True, slots=True)
class BseXbrlContext:
    """One declared XBRL accounting context, separate from archive metadata."""

    context_id: str
    period_start: datetime | None
    period_end: datetime
    instant: bool


@dataclass(frozen=True, slots=True)
class BseXbrlContextFact:
    """A canonical metric candidate paired with its actual XBRL context."""

    metric: FinancialMetric
    value: Decimal
    concept: str
    context: BseXbrlContext
    period_type: FinancialPeriodType
    value_basis: FinancialValueBasis


@dataclass(frozen=True, slots=True)
class BseIngestionReport:
    instrument_id: str
    security_code: str
    metadata_seen: int
    xbrl_parsed: int
    filings_inserted: int
    filings_duplicate: int
    facts_inserted: int
    facts_duplicate: int
    facts_conflicted: int
    revisions: int
    rejected: int
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BseLocalXbrlInspection:
    path: Path
    checksum: str
    document: BseXbrlDocument
    period_start: datetime | None
    period_end: datetime
    period_type: FinancialPeriodType
    value_basis: FinancialValueBasis
    filing_type: str
    audit_status: str | None
    source_publication_at: datetime | None = None
    publication_availability: BsePublicationAvailability = BsePublicationAvailability.SYSTEM_FIRST_OBSERVED


@dataclass(frozen=True, slots=True)
class BseLocalIngestionReport:
    instrument_id: str
    security_code: str
    filename: str
    identity_verified: bool
    filing_outcome: FilingWriteOutcome | None
    facts_inserted: int
    facts_duplicate: int
    facts_conflicted: int
    pit_available_from: datetime | None
    publication_availability: BsePublicationAvailability | None
    warnings: tuple[str, ...]


class BseMappingStore(Protocol):
    def capture_provider_mapping(
        self, instrument: InstrumentIdentity, *, provider: str, effective_as_of: datetime,
        resolved_instrument: InstrumentIdentity | None = None, source_reference: str | None = None,
        source_checksum: str | None = None,
    ) -> object: ...


class BSEOfficialFinancialResultsProvider:
    """Official public BSE results/XBRL reader with injectable bounded transport."""

    def __init__(
        self, *, fetch_text: Callable[[str], str] | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        timestamp_status: BseTimestampStatus = BseTimestampStatus.EXCHANGE_LOCAL_ASSUMPTION,
    ) -> None:
        self._fetch_text = fetch_text or _fetch_bse_text
        self._clock = clock
        self._timestamp_status = timestamp_status

    def result_metadata(self, security_code: str) -> tuple[BseResultMetadata, ...]:
        if not security_code.isdigit():
            raise BseOfficialError("BSE security code must be numeric.")
        page = BSE_RESULT_PAGE.format(security_code=security_code)
        rows = _parse_result_page(self._fetch_text(page), page)
        values: list[BseResultMetadata] = []
        seen: set[str] = set()
        for row in rows:
            for scope, href in ((StatementScope.STANDALONE, row.standalone_xbrl), (StatementScope.CONSOLIDATED, row.consolidated_xbrl)):
                if not href:
                    continue
                absolute = _official_xbrl_url(href, page)
                # A March annual and a March quarterly entry can reference the
                # same XBRL.  Retain the annual representation and never create
                # duplicate/conflicting facts from the same filing document.
                key = absolute
                candidate = _metadata_from_row(row, security_code, scope, absolute, page, self._timestamp_status)
                prior = next((item for item in values if item.xbrl_url == key), None)
                if prior is not None:
                    if prior.period_type is FinancialPeriodType.ANNUAL:
                        continue
                    if candidate.period_type is FinancialPeriodType.ANNUAL:
                        values.remove(prior)
                    else:
                        continue
                values.append(candidate); seen.add(key)
        return tuple(sorted(values, key=lambda item: (item.filing_at, item.xbrl_url)))

    def xbrl(self, url: str, *, period_end: datetime | None = None) -> BseXbrlDocument:
        return parse_bse_xbrl(self._fetch_text(_official_xbrl_url(url, _BSE_ORIGIN)), url, period_end=period_end)

    def resolve_identity(self, instrument: InstrumentIdentity, security_code: str, metadata: BseResultMetadata) -> BseSecurityIdentity:
        document = self.xbrl(metadata.xbrl_url)
        if not instrument.isin:
            raise BseOfficialError("BSE identity requires a canonical ISIN.")
        if document.security_code != security_code or document.isin.upper() != instrument.isin.upper():
            raise BseOfficialError("BSE XBRL identity does not match the canonical ISIN/security code.")
        return BseSecurityIdentity(
            instrument.instrument_id, document.isin.upper(), security_code, document.security_name,
            document.source_url, "EXACT_ISIN_BSE_XBRL", self._clock(),
        )


class BSEOfficialFinancialResultsArchiveProvider:
    """Read BSE's structured Financial Results archive for its linked XBRLs.

    The BSE client downloads this public CSV archive for a single BSE security
    code. It is a discovery boundary only: the canonical importer still
    verifies the ISIN and security code inside every XBRL before persistence.
    """

    def __init__(
        self, *, fetch_csv: Callable[[str], str],
        timestamp_status: BseTimestampStatus = BseTimestampStatus.EXCHANGE_LOCAL_ASSUMPTION,
    ) -> None:
        self._fetch_csv = fetch_csv
        self._timestamp_status = timestamp_status

    def result_metadata(self, security_code: str) -> tuple[BseResultMetadata, ...]:
        return tuple(group.preferred for group in self.result_metadata_aliases(security_code))

    def result_metadata_aliases(self, security_code: str) -> tuple[BseResultMetadataAliases, ...]:
        if not re.fullmatch(r"\d{6}", security_code):
            raise BseOfficialError("BSE security code must be a six-digit BSE code.")
        archive = BSE_RESULT_ARCHIVE.format(security_code=security_code)
        rows = _parse_result_archive(self._fetch_csv(archive))
        aliases: dict[str, list[BseResultMetadata]] = {}
        for row in rows:
            for scope, href in ((StatementScope.STANDALONE, row.standalone_xbrl), (StatementScope.CONSOLIDATED, row.consolidated_xbrl)):
                if not href:
                    continue
                try:
                    candidate = _metadata_from_row(
                        row, security_code, scope, _official_xbrl_url(href, _BSE_ORIGIN), archive, self._timestamp_status,
                        archive_timestamp=True,
                    )
                except BseOfficialError:
                    # An unsupported archival period or malformed row is not
                    # canonical evidence. Other complete rows remain usable,
                    # and each XBRL is independently identity-verified later.
                    continue
                values = aliases.setdefault(candidate.xbrl_url, [])
                if candidate not in values:
                    values.append(candidate)
        groups: list[BseResultMetadataAliases] = []
        for document_url, values in aliases.items():
            ordered = tuple(sorted(values, key=lambda item: (
                item.filing_at, item.period_type.value, item.scope.value, item.quarter_label,
                item.filing_type, item.status, item.xbrl_url,
            )))
            # Preserve the old Annual-first display convention as a deterministic
            # compatibility view only. It has no authority over fact periods.
            preferred = next((item for item in ordered if item.period_type is FinancialPeriodType.ANNUAL), ordered[-1])
            groups.append(BseResultMetadataAliases(document_url, ordered, preferred))
        return tuple(sorted(groups, key=lambda item: (item.preferred.filing_at, item.document_url)))


class BSEOfficialFinancialResultsIngestionService:
    """Persist only exact-ISIN BSE XBRL filings/facts through canonical stores."""

    def __init__(
        self, provider: BSEOfficialFinancialResultsProvider, filings: CorporateFilingsStore,
        facts: FinancialFactStore, *, mapping_store: BseMappingStore | None = None,
        normalizer: FinancialFactNormalizationService | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._provider, self._filings, self._facts = provider, filings, facts
        self._mapping_store = mapping_store
        self._normalizer, self._clock = normalizer or FinancialFactNormalizationService(), clock

    def ingest(self, instrument: InstrumentIdentity, security_code: str, *, limit: int = 12) -> BseIngestionReport:
        if limit < 1 or limit > 24:
            raise ValueError("BSE XBRL import limit must be between 1 and 24.")
        metadata = self._provider.result_metadata(security_code)
        selected = metadata[-limit:]
        inserted = duplicate = facts_inserted = facts_duplicate = conflicts = revisions = rejected = parsed = 0
        warnings: list[str] = []
        mapping_done = False
        for item in selected:
            try:
                document = self._provider.xbrl(item.xbrl_url, period_end=item.period_end); parsed += 1
                identity = _identity_from_document(instrument, security_code, document, self._clock())
                if not mapping_done and self._mapping_store is not None:
                    mapped = InstrumentIdentity(
                        instrument.instrument_id, instrument.exchange, instrument.symbol, instrument.trading_symbol,
                        instrument.isin, instrument.series, instrument.instrument_type, instrument.name, instrument.currency,
                        instrument.provider_mappings + (identity.provider_mapping(),),
                    )
                    self._mapping_store.capture_provider_mapping(
                        instrument, provider=BSE_OFFICIAL_PROVIDER, effective_as_of=identity.effective_as_of,
                        resolved_instrument=mapped, source_reference=identity.source_reference,
                        source_checksum=document.checksum,
                    )
                    mapping_done = True
                filing = self._filing(instrument, item, document)
                outcome = self._filings.save(filing)
                if outcome is FilingWriteOutcome.INSERTED:
                    inserted += 1; revisions += int(filing.revision_of_filing_id is not None)
                else:
                    duplicate += 1
                for metric, value in document.facts:
                    result = self._save_fact(instrument, filing, item, document, metric, value)
                    if result is FinancialFactWriteOutcome.INSERTED: facts_inserted += 1
                    elif result is FinancialFactWriteOutcome.IDENTICAL: facts_duplicate += 1
                    else: conflicts += 1
                warnings.extend(document.warnings)
            except (BseOfficialError, ValueError):
                rejected += 1; warnings.append("BSE_XBRL_REJECTED")
        return BseIngestionReport(
            instrument.instrument_id, security_code, len(metadata), parsed, inserted, duplicate,
            facts_inserted, facts_duplicate, conflicts, revisions, rejected, tuple(sorted(set(warnings))),
        )

    def _filing(self, instrument: InstrumentIdentity, metadata: BseResultMetadata, document: BseXbrlDocument) -> CorporateFiling:
        parent = _prior_filing(self._filings, instrument.instrument_id, metadata)
        identity = _filing_id(instrument, metadata)
        # ``received_at`` in the canonical fact/filing contract is the source
        # availability time used by point-in-time queries.  The local retrieval
        # instant is retained separately in provenance, so a historic BSE filing
        # does not become invisible before today's import date.
        retrieved = self._clock()
        available = metadata.filing_at
        attachment = FilingAttachment(
            "bse-xbrl:" + document.checksum[:24], "XBRL", "BSE Financial Results XBRL", None,
            document.source_url, "text/xml", metadata.filing_at, document.checksum,
            AttachmentParseStatus.PARSED, True,
        )
        provenance = MarketDataProvenance(
            BSE_OFFICIAL_PROVIDER, metadata.security_code, metadata.filing_at, metadata.filing_at,
            retrieved, "bse-official-xbrl-v1", identity, document.source_url,
            document.schema_version or "bse-xbrl-unknown",
        )
        warnings = ["BSE_OFFICIAL_XBRL", "TIMESTAMP_" + metadata.timestamp_status.value]
        if metadata.revision_reason:
            warnings.append("BSE_REVISION_REASON_PRESENT")
        if document.scale is None:
            raise BseOfficialError("BSE XBRL unit/scale is not explicit.")
        return CorporateFiling(
            identity, instrument, Exchange.BSE, BSE_OFFICIAL_PROVIDER, PrimarySourceQuality.PRIMARY_EXCHANGE,
            FilingType.FINANCIAL_RESULTS, metadata.filing_type, "BSE Financial Results " + metadata.quarter_label,
            metadata.filing_at, available, metadata.xbrl_url, metadata.xbrl_url, provenance,
            period_end=metadata.period_end, text_availability=FilingTextAvailability.SOURCE_TEXT,
            attachments=(attachment,), revision_of_filing_id=parent, financial_result=FinancialResultMetadata(
                metadata.period_end, metadata.scope.value, metadata.period_type.value, metadata.is_revised,
            ), normalization_version="bse-official-xbrl-v1", warnings=tuple(warnings),
        )

    def _save_fact(self, instrument: InstrumentIdentity, filing: CorporateFiling, metadata: BseResultMetadata,
                   document: BseXbrlDocument, metric: FinancialMetric, value: Decimal) -> FinancialFactWriteOutcome:
        if document.scale is None or document.currency is None:
            raise BseOfficialError("BSE XBRL unit/scale is not explicit.")
        prior = _prior_fact(self._facts, instrument.instrument_id, metric, metadata)
        record = StructuredFinancialRecord(
            instrument, metric, value, document.currency, document.currency, _raw_xbrl_value_scale(metric, document.scale),
            metadata.period_type, metadata.value_basis, None, metadata.period_end,
            _fiscal_year(metadata.period_end), _fiscal_quarter(metadata.period_end), metadata.scope,
            BSE_OFFICIAL_PROVIDER, filing.filing_id, filing.announced_at, filing.received_at,
            metadata.xbrl_url, document.source_url, "bse-official-xbrl-v1", prior,
            ("BSE_OFFICIAL_XBRL", "SOURCE_LEVEL_OF_ROUNDING_" + document.scale.value, "RAW_XBRL_UNIT_VALUE"),
        )
        fact = self._normalizer.normalize(record, filing)
        return self._facts.save(fact)


class BSEOfficialLocalXbrlIngestionService:
    """Import one manually obtained official BSE XBRL without any network path.

    A source publication timestamp is not invented.  If it is absent from the
    XML, the immutable record becomes available only from the system's first
    observation instant.  That is deliberately distinct from an asserted BSE
    publication timestamp and preserves point-in-time safety.
    """

    def __init__(self, filings: CorporateFilingsStore, facts: FinancialFactStore, *,
                 mapping_store: BseMappingStore | None = None,
                 normalizer: FinancialFactNormalizationService | None = None,
                 clock: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        self._filings, self._facts, self._mapping_store = filings, facts, mapping_store
        self._normalizer, self._clock = normalizer or FinancialFactNormalizationService(), clock

    def inspect(self, path: str | Path, *, maximum_bytes: int = 5 * 1024 * 1024) -> BseLocalXbrlInspection:
        target = Path(path)
        if not target.is_file() or target.suffix.lower() not in {".xml", ".xbrl"}:
            raise BseOfficialError("BSE local XBRL file is unavailable.")
        raw = target.read_bytes()
        if maximum_bytes < 1 or len(raw) > maximum_bytes:
            raise BseOfficialError("BSE local XBRL exceeds the bounded adapter limit.")
        try:
            text = raw.decode("utf-8-sig")
            root = ET.fromstring(text)
        except (UnicodeDecodeError, ET.ParseError) as error:
            raise BseOfficialError("BSE local XBRL is malformed.") from error
        values = {_local(item.tag): (item.text or "").strip() for item in root.iter() if (item.text or "").strip()}
        end_text = values.get("DateOfEndOfReportingPeriod")
        if not end_text:
            raise BseOfficialError("BSE local XBRL has no reporting period end.")
        try:
            end = datetime.combine(date.fromisoformat(end_text), datetime.min.time(), UTC)
            start = datetime.combine(date.fromisoformat(values["DateOfStartOfReportingPeriod"]), datetime.min.time(), UTC) if values.get("DateOfStartOfReportingPeriod") else None
        except ValueError as error:
            raise BseOfficialError("BSE local XBRL reporting period is malformed.") from error
        type_text = values.get("TypeOfReportingPeriod", "").strip().upper()
        if type_text == "QUARTERLY":
            period_type, basis, filing_type = FinancialPeriodType.QUARTERLY, FinancialValueBasis.QUARTER_ONLY, "Quarter"
        elif type_text in {"ANNUAL", "YEARLY"}:
            period_type, basis, filing_type = FinancialPeriodType.ANNUAL, FinancialValueBasis.FULL_YEAR, "Year"
        else:
            raise BseOfficialError("BSE local XBRL result basis is unsupported.")
        checksum = hashlib.sha256(raw).hexdigest()
        document = parse_bse_xbrl(text, "bse-local-xbrl:" + checksum, period_end=end)
        # Board-approval date/time is source metadata, not a BSE exchange
        # publication timestamp, and is intentionally not converted here.
        return BseLocalXbrlInspection(target, checksum, document, start, end, period_type, basis, filing_type, values.get("WhetherResultsAreAuditedOrUnaudited"))

    def ingest(self, instrument: InstrumentIdentity, security_code: str, path: str | Path) -> BseLocalIngestionReport:
        inspection = self.inspect(path)
        observed = self._clock()
        identity = _identity_from_document(instrument, security_code, inspection.document, observed)
        source_reference = "BSE_OFFICIAL_XBRL_SHA256:" + inspection.checksum
        filing_id = "bse-local:" + hashlib.sha256("|".join((instrument.instrument_id, security_code, inspection.checksum)).encode()).hexdigest()[:24]
        filing = self._filings.get(filing_id)
        outcome: FilingWriteOutcome
        if filing is None:
            if self._mapping_store is not None:
                mapped = InstrumentIdentity(
                    instrument.instrument_id, instrument.exchange, instrument.symbol, instrument.trading_symbol,
                    instrument.isin, instrument.series, instrument.instrument_type, instrument.name, instrument.currency,
                    instrument.provider_mappings + (identity.provider_mapping(),),
                )
                self._mapping_store.capture_provider_mapping(
                    instrument, provider=BSE_OFFICIAL_PROVIDER, effective_as_of=observed,
                    resolved_instrument=mapped, source_reference=source_reference,
                    source_checksum=inspection.checksum,
                )
            provenance = MarketDataProvenance(
                BSE_OFFICIAL_PROVIDER, security_code, None, None, observed,
                "bse-official-local-xbrl-v1", filing_id, source_reference,
                inspection.document.schema_version or "bse-xbrl-unknown",
            )
            attachment = FilingAttachment(
                "bse-local-xbrl:" + inspection.checksum[:24], "XBRL", "BSE Financial Results XBRL",
                inspection.path.name, source_reference, "text/xml", None, inspection.checksum,
                AttachmentParseStatus.PARSED, True,
            )
            # The local observation instant is the canonical availability bound;
            # warnings/provenance make clear it is not asserted source publication.
            filing = CorporateFiling(
                filing_id, instrument, Exchange.BSE, BSE_OFFICIAL_PROVIDER, PrimarySourceQuality.PRIMARY_EXCHANGE,
                FilingType.FINANCIAL_RESULTS, inspection.filing_type, "BSE Financial Results local XBRL",
                observed, observed, source_reference, source_reference, provenance,
                period_end=inspection.period_end, text_availability=FilingTextAvailability.SOURCE_TEXT,
                attachments=(attachment,), financial_result=FinancialResultMetadata(
                    inspection.period_end, inspection.document.scope.value if inspection.document.scope else None,
                    inspection.period_type.value, False,
                ), normalization_version="bse-official-local-xbrl-v1",
                warnings=("SOURCE_PUBLICATION_TIMESTAMP_UNKNOWN", "PIT_AVAILABLE_FROM_SYSTEM_FIRST_OBSERVED", "BSE_OFFICIAL_LOCAL_XBRL"),
            )
            outcome = self._filings.save(filing)
        else:
            outcome = FilingWriteOutcome.IDENTICAL
        inserted = duplicate = conflicts = 0
        for metric, value in inspection.document.facts:
            if inspection.document.scale is None or inspection.document.currency is None:
                raise BseOfficialError("BSE local XBRL unit/scale is not explicit.")
            record = StructuredFinancialRecord(
                instrument, metric, value, inspection.document.currency, inspection.document.currency,
                _raw_xbrl_value_scale(metric, inspection.document.scale), inspection.period_type, inspection.value_basis,
                inspection.period_start, inspection.period_end, _fiscal_year(inspection.period_end),
                _fiscal_quarter(inspection.period_end), inspection.document.scope or StatementScope.UNKNOWN,
                BSE_OFFICIAL_PROVIDER, filing.filing_id, filing.announced_at, filing.received_at,
                source_reference, source_reference, "bse-official-local-xbrl-v1", None,
                ("BSE_OFFICIAL_LOCAL_XBRL", "PIT_AVAILABLE_FROM_SYSTEM_FIRST_OBSERVED", "SOURCE_LEVEL_OF_ROUNDING_" + inspection.document.scale.value, "RAW_XBRL_UNIT_VALUE"),
            )
            result = self._facts.save(self._normalizer.normalize(record, filing))
            if result is FinancialFactWriteOutcome.INSERTED: inserted += 1
            elif result is FinancialFactWriteOutcome.IDENTICAL: duplicate += 1
            else: conflicts += 1
        return BseLocalIngestionReport(
            instrument.instrument_id, security_code, inspection.path.name, True, outcome, inserted, duplicate,
            conflicts, filing.available_at if hasattr(filing, "available_at") else filing.announced_at,
            inspection.publication_availability,
            ("SOURCE_PUBLICATION_TIMESTAMP_UNKNOWN", "PIT_AVAILABLE_FROM_SYSTEM_FIRST_OBSERVED"),
        )

    def ingest_official_staged(
        self,
        instrument: InstrumentIdentity,
        security_code: str,
        path: str | Path,
        *,
        metadata: BseResultMetadata,
    ) -> BseLocalIngestionReport:
        """Import a collector-staged BSE XBRL with verified official metadata.

        The collector has already restricted and downloaded the official URL;
        this method remains the one canonical local XBRL parser/normalizer and
        fact writer.  Unlike a manually supplied local file, it may retain the
        BSE publication timestamp because it is supplied from the official
        result metadata rather than inferred from the accounting period.
        """
        if metadata.security_code != security_code:
            raise BseOfficialError("BSE staged metadata security code does not match the requested identity.")
        # Only this collector-staged BSE path may use the separately governed
        # 8 MiB acquisition bound. Generic/manual local inspection stays 5 MiB.
        inspection = self.inspect(path, maximum_bytes=8 * 1024 * 1024)
        if inspection.document.scope is not None and inspection.document.scope is not metadata.scope:
            raise BseOfficialError("BSE staged XBRL statement scope conflicts with official metadata.")
        if inspection.period_end != metadata.period_end:
            raise BseOfficialError("BSE staged XBRL period conflicts with official metadata.")
        context_facts = _selected_context_facts(inspection.document, metadata.period_end)
        if not context_facts:
            raise BseOfficialError("BSE staged XBRL has no eligible current-period fact contexts.")
        observed = self._clock()
        identity = _identity_from_document(instrument, security_code, inspection.document, observed)
        source_reference = metadata.xbrl_url
        filing_id = _filing_id(instrument, metadata)
        filing = self._filings.get(filing_id)
        outcome: FilingWriteOutcome
        if filing is None:
            if self._mapping_store is not None:
                mapped = InstrumentIdentity(
                    instrument.instrument_id, instrument.exchange, instrument.symbol, instrument.trading_symbol,
                    instrument.isin, instrument.series, instrument.instrument_type, instrument.name, instrument.currency,
                    instrument.provider_mappings + (identity.provider_mapping(),),
                )
                self._mapping_store.capture_provider_mapping(
                    instrument, provider=BSE_OFFICIAL_PROVIDER, effective_as_of=observed,
                    resolved_instrument=mapped, source_reference=source_reference,
                    source_checksum=inspection.checksum,
                )
            provenance = MarketDataProvenance(
                BSE_OFFICIAL_PROVIDER, security_code, metadata.filing_at, metadata.filing_at, observed,
                "bse-official-staged-xbrl-v1", filing_id, source_reference,
                inspection.document.schema_version or "bse-xbrl-unknown",
            )
            attachment = FilingAttachment(
                "bse-staged-xbrl:" + inspection.checksum[:24], "XBRL", "BSE Financial Results XBRL",
                inspection.path.name, source_reference, "text/xml", metadata.filing_at, inspection.checksum,
                AttachmentParseStatus.PARSED, True,
            )
            warnings = ["BSE_OFFICIAL_XBRL", "BSE_OFFICIAL_STAGED_XBRL", "TIMESTAMP_" + metadata.timestamp_status.value]
            if metadata.revision_reason:
                warnings.append("BSE_REVISION_REASON_PRESENT")
            filing = CorporateFiling(
                filing_id, instrument, Exchange.BSE, BSE_OFFICIAL_PROVIDER, PrimarySourceQuality.PRIMARY_EXCHANGE,
                FilingType.FINANCIAL_RESULTS, metadata.filing_type, "BSE Financial Results " + metadata.quarter_label,
                metadata.filing_at, observed, source_reference, source_reference, provenance,
                period_end=metadata.period_end, text_availability=FilingTextAvailability.SOURCE_TEXT,
                attachments=(attachment,), revision_of_filing_id=_prior_filing(self._filings, instrument.instrument_id, metadata),
                financial_result=FinancialResultMetadata(
                    metadata.period_end, metadata.scope.value, metadata.period_type.value, metadata.is_revised,
                ), normalization_version="bse-official-staged-xbrl-v1", warnings=tuple(warnings),
            )
            outcome = self._filings.save(filing)
        else:
            outcome = FilingWriteOutcome.IDENTICAL
        inserted = duplicate = conflicts = 0
        for context_fact in context_facts:
            if inspection.document.scale is None or inspection.document.currency is None:
                raise BseOfficialError("BSE staged XBRL unit/scale is not explicit.")
            context = context_fact.context
            record = StructuredFinancialRecord(
                instrument, context_fact.metric, context_fact.value, inspection.document.currency, inspection.document.currency,
                _raw_xbrl_value_scale(context_fact.metric, inspection.document.scale), context_fact.period_type,
                context_fact.value_basis, context.period_start, context.period_end, _fiscal_year(context.period_end),
                _fiscal_quarter(context.period_end), metadata.scope,
                BSE_OFFICIAL_PROVIDER, filing.filing_id, metadata.filing_at, filing.received_at,
                source_reference, source_reference, "bse-official-staged-xbrl-v1",
                _prior_context_fact(self._facts, instrument.instrument_id, context_fact.metric, metadata, context_fact),
                ("BSE_OFFICIAL_XBRL", "BSE_OFFICIAL_STAGED_XBRL", "BSE_XBRL_CONTEXT_" + context.context_id,
                 "SOURCE_LEVEL_OF_ROUNDING_" + inspection.document.scale.value, "RAW_XBRL_UNIT_VALUE"),
            )
            result = self._facts.save(self._normalizer.normalize(record, filing))
            if result is FinancialFactWriteOutcome.INSERTED:
                inserted += 1
            elif result is FinancialFactWriteOutcome.IDENTICAL:
                duplicate += 1
            else:
                conflicts += 1
        return BseLocalIngestionReport(
            instrument.instrument_id, security_code, inspection.path.name, True, outcome, inserted, duplicate,
            conflicts, metadata.filing_at, BsePublicationAvailability.SOURCE_PUBLICATION_KNOWN,
            ("BSE_OFFICIAL_STAGED_XBRL", "TIMESTAMP_" + metadata.timestamp_status.value),
        )


@dataclass(frozen=True, slots=True)
class _ResultRow:
    financial_year: str
    quarter: str
    filing_type: str
    status: str
    filing_time: str
    revised_time: str
    revision_reason: str
    standalone_xbrl: str | None
    consolidated_xbrl: str | None


class _ResultPageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(); self._rows: list[list[tuple[str, str | None]]] = []; self._row: list[tuple[str, str | None]] | None = None
        self._cell: list[str] | None = None; self._href: str | None = None
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr": self._row = []
        elif tag in {"td", "th"} and self._row is not None: self._cell = []; self._href = None
        elif tag == "a" and self._cell is not None:
            self._href = dict(attrs).get("href")
    def handle_data(self, data: str) -> None:
        if self._cell is not None: self._cell.append(data)
    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._cell is not None and self._row is not None:
            self._row.append((" ".join("".join(self._cell).split()), self._href)); self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row: self._rows.append(self._row)
            self._row = None

    def rows(self) -> tuple[_ResultRow, ...]:
        header_index = next((index for index, row in enumerate(self._rows) if {item[0] for item in row} >= {"Financial Year", "Quarter", "Filing Date Time"}), None)
        if header_index is None:
            raise BseOfficialError("BSE results page has no recognised results table.")
        headers = [_header(item[0]) for item in self._rows[header_index]]
        values: list[_ResultRow] = []
        for row in self._rows[header_index + 1:]:
            if len(row) != len(headers):
                continue
            data = {header: cell for header, cell in zip(headers, row)}
            if not data.get("financial_year", ("", None))[0] or not data.get("quarter", ("", None))[0]:
                continue
            values.append(_ResultRow(
                data["financial_year"][0], data["quarter"][0], data.get("type", ("", None))[0],
                data.get("status", ("", None))[0], data.get("filing_date_time", ("", None))[0],
                data.get("revised_date_time", ("", None))[0], data.get("revision_reason", ("", None))[0],
                data.get("standalone_xbrl", ("", None))[1], data.get("consolidate_xbrl", ("", None))[1],
            ))
        return tuple(values)


def _parse_result_page(payload: str, page: str) -> tuple[_ResultRow, ...]:
    del page
    if "Financial Year" not in payload and "Comp_Results" not in payload:
        raise BseOfficialError("BSE_PUBLIC_RESULTS_INTERFACE_UNAVAILABLE")
    parser = _ResultPageParser(); parser.feed(payload)
    return parser.rows()


def _parse_result_archive(payload: str) -> tuple[_ResultRow, ...]:
    """Parse the BSE Results.csv shape without scraping client-rendered text."""
    try:
        reader = csv.DictReader(StringIO(payload))
        if reader.fieldnames is None:
            raise BseOfficialError("BSE results archive has no header.")
        headers = {_header(field) for field in reader.fieldnames if field}
        required = {"financial_year", "quarter", "type", "status", "filing_date_time"}
        if not required <= headers or not {"standalone_xbrl", "consolidate_xbrl"} & headers:
            raise BseOfficialError("BSE results archive has an unrecognised schema.")
        values: list[_ResultRow] = []
        for source in reader:
            row = {_header(key): (value or "").strip() for key, value in source.items() if key}
            label = row.get("quarter", "").split(";", 1)[0].strip()
            if not row.get("financial_year") or not label:
                continue
            values.append(_ResultRow(
                row["financial_year"], label, row.get("type", ""), row.get("status", ""),
                row.get("filing_date_time", ""), row.get("revised_date_time", ""), row.get("revision_reason", ""),
                _blank(row.get("standalone_xbrl")), _blank(row.get("consolidate_xbrl")),
            ))
        return tuple(values)
    except (csv.Error, UnicodeError) as error:
        raise BseOfficialError("BSE results archive is malformed.") from error


def _metadata_from_row(row: _ResultRow, security_code: str, scope: StatementScope, url: str, page: str,
                       status: BseTimestampStatus, *, archive_timestamp: bool = False) -> BseResultMetadata:
    period_end, period_type, basis = _period(row.quarter, row.filing_type)
    revised = _bse_timestamp(row.revised_time, status, optional=True, archive_timestamp=archive_timestamp)
    filing = revised if row.status.upper() == "REVISED" else _bse_timestamp(
        row.filing_time, status, archive_timestamp=archive_timestamp,
    )
    if filing is None and row.status.upper() == "REVISED":
        filing = _bse_timestamp(row.filing_time, status, archive_timestamp=archive_timestamp)
    if filing is None:
        raise BseOfficialError("BSE filing timestamp is unavailable or timezone-unknown.")
    return BseResultMetadata(
        security_code, row.financial_year, row.quarter, row.filing_type, row.status, filing, revised,
        _blank(row.revision_reason), scope, period_end, period_type, basis, url, page, status,
    )


def parse_bse_xbrl(payload: str, source_url: str, *, period_end: datetime | None = None) -> BseXbrlDocument:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as error:
        raise BseOfficialError("BSE XBRL is malformed.") from error
    values: dict[str, list[tuple[str, dict[str, str]]]] = {}
    contexts: dict[str, BseXbrlContext] = {}
    concepts: list[str] = []
    for element in root.iter():
        local = _local(element.tag); concepts.append(local)
        if local == "context" and element.attrib.get("id"):
            context = _context_from_element(element)
            if context is not None:
                contexts[context.context_id] = context
        text = (element.text or "").strip()
        if text:
            values.setdefault(local, []).append((text, dict(element.attrib)))
    isin = _required_single(values, "ISIN")
    security_code = _required_single(values, "ScripCode")
    name = _first(values, "NameOfTheCompany")
    schema_version = _schema_version(payload)
    audit_status = _first(values, "WhetherResultsAreAuditedOrUnaudited")
    scope = _scope(_first(values, "NatureOfReportStandaloneConsolidated"))
    currency = _currency(_first(values, "DescriptionOfPresentationCurrency"))
    scale = _scale(_first(values, "LevelOfRounding"))
    if currency is None or scale is None:
        raise BseOfficialError("BSE XBRL omits an explicit recognised currency or scale.")
    selected_end = period_end.date() if period_end is not None else None
    fact_values = values if selected_end is None else {
        name: tuple((text, attrs) for text, attrs in entries if contexts.get(attrs.get("contextRef", "")) and contexts[attrs["contextRef"]].period_end.date() == selected_end)
        for name, entries in values.items()
    }
    facts: list[tuple[FinancialMetric, Decimal]] = []
    for concept, metric in _CONCEPTS:
        item = _first_decimal(fact_values, concept)
        if item is not None:
            facts.append((metric, item))
    context_facts: list[BseXbrlContextFact] = []
    seen_context_metrics: set[tuple[FinancialMetric, str]] = set()
    for concept, metric in _CONCEPTS:
        for text, attrs in values.get(concept, ()):
            context = contexts.get(attrs.get("contextRef", ""))
            if context is None:
                continue
            semantics = _context_semantics(context)
            if semantics is None:
                continue
            try:
                number = Decimal(text.replace(",", ""))
            except __import__("decimal").InvalidOperation:
                continue
            key = metric, context.context_id
            # Concept order is an existing deterministic mapping priority. Do
            # not turn synonymous XBRL tags into duplicate canonical facts.
            if key in seen_context_metrics:
                continue
            seen_context_metrics.add(key)
            context_facts.append(BseXbrlContextFact(metric, number, concept, context, *semantics))
    return BseXbrlDocument(
        security_code=security_code, isin=isin.upper(), security_name=name,
        schema_version=schema_version, audit_status=audit_status, scope=scope,
        currency=currency, scale=scale, facts=tuple(facts), source_url=source_url,
        checksum=hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        raw_concepts=tuple(sorted(set(concepts))),
        contexts=tuple(sorted(contexts.values(), key=lambda item: item.context_id)),
        context_facts=tuple(sorted(
            context_facts,
            key=lambda item: (
                item.metric.value, item.context.period_end,
                item.context.period_start or item.context.period_end,
                item.context.context_id, item.concept,
            ),
        )),
    )


def _context_from_element(element: ET.Element) -> BseXbrlContext | None:
    identifier = element.attrib.get("id")
    instant = next((node.text for node in element.iter() if _local(node.tag) == "instant" and node.text), None)
    end = next((node.text for node in element.iter() if _local(node.tag) == "endDate" and node.text), None)
    start = next((node.text for node in element.iter() if _local(node.tag) == "startDate" and node.text), None)
    try:
        if instant:
            return BseXbrlContext(identifier, None, datetime.combine(date.fromisoformat(instant.strip()), datetime.min.time(), UTC), True)
        if end and start:
            return BseXbrlContext(identifier, datetime.combine(date.fromisoformat(start.strip()), datetime.min.time(), UTC), datetime.combine(date.fromisoformat(end.strip()), datetime.min.time(), UTC), False)
    except ValueError:
        return None
    return None


def _context_semantics(context: BseXbrlContext) -> tuple[FinancialPeriodType, FinancialValueBasis] | None:
    if context.instant:
        return FinancialPeriodType.POINT_IN_TIME, FinancialValueBasis.UNKNOWN
    if context.period_start is None:
        return None
    days = (context.period_end.date() - context.period_start.date()).days + 1
    if 80 <= days <= 100:
        return FinancialPeriodType.QUARTERLY, FinancialValueBasis.QUARTER_ONLY
    if context.period_start.month == 4 and context.period_start.day == 1 and context.period_end.month == 3 and context.period_end.day == 31 and 360 <= days <= 367:
        return FinancialPeriodType.ANNUAL, FinancialValueBasis.FULL_YEAR
    if context.period_start.month == 4 and context.period_start.day == 1 and 150 <= days <= 300:
        return FinancialPeriodType.QUARTERLY, FinancialValueBasis.YEAR_TO_DATE
    return None


def _selected_context_facts(document: BseXbrlDocument, period_end: datetime) -> tuple[BseXbrlContextFact, ...]:
    """Return only current-period, canonically comparable XBRL fact contexts.

    Contexts for prior periods are retained in the immutable source document but
    are deliberately not backfilled by this archive-row importer.  That keeps
    a selected filing from silently becoming evidence for a different filing
    period.  Balance-sheet metrics are the only mapped instant facts.
    """
    instant_metrics = {
        FinancialMetric.TOTAL_ASSETS, FinancialMetric.TOTAL_LIABILITIES,
        FinancialMetric.TOTAL_EQUITY, FinancialMetric.CASH_AND_EQUIVALENTS,
        FinancialMetric.OTHER_BANK_BALANCES, FinancialMetric.CURRENT_BORROWINGS,
        FinancialMetric.NONCURRENT_BORROWINGS,
    }
    return tuple(
        item for item in document.context_facts
        if item.context.period_end == period_end
        and (not item.context.instant or item.metric in instant_metrics)
    )


# The mappings are deliberately one-way: an ambiguous/unsupported BSE concept
# creates no canonical numerical fact.  In particular, no mapping derives
# EBITDA, total debt, aggregate capex, or period-end shares.
_CONCEPTS = (
    ("RevenueFromOperations", FinancialMetric.REVENUE),
    ("OtherIncome", FinancialMetric.OTHER_INCOME),
    ("ProfitLossBeforeTax", FinancialMetric.PBT),
    ("ProfitBeforeTax", FinancialMetric.PBT),
    ("ProfitLoss", FinancialMetric.PAT),
    ("ProfitAfterTax", FinancialMetric.PAT),
    ("ProfitLossForPeriod", FinancialMetric.PAT),
    ("BasicEarningsPerShare", FinancialMetric.EPS_BASIC),
    ("EarningsPerShareBasic", FinancialMetric.EPS_BASIC),
    ("BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations", FinancialMetric.EPS_BASIC),
    ("FinanceCosts", FinancialMetric.FINANCE_COST),
    ("FinanceCost", FinancialMetric.FINANCE_COST),
    ("DepreciationDepletionAndAmortisationExpense", FinancialMetric.DEPRECIATION),
    ("DepreciationAndAmortisationExpense", FinancialMetric.DEPRECIATION),
    ("Assets", FinancialMetric.TOTAL_ASSETS),
    ("Liabilities", FinancialMetric.TOTAL_LIABILITIES),
    ("Equity", FinancialMetric.TOTAL_EQUITY),
    ("CashAndCashEquivalents", FinancialMetric.CASH_AND_EQUIVALENTS),
    ("BankBalanceOtherThanCashAndCashEquivalents", FinancialMetric.OTHER_BANK_BALANCES),
    ("BorrowingsCurrent", FinancialMetric.CURRENT_BORROWINGS),
    ("BorrowingsNoncurrent", FinancialMetric.NONCURRENT_BORROWINGS),
    ("CashFlowsFromUsedInOperatingActivities", FinancialMetric.CFO),
    ("PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities", FinancialMetric.PURCHASE_OF_PROPERTY_PLANT_EQUIPMENT),
    ("PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities", FinancialMetric.PURCHASE_OF_INTANGIBLE_ASSETS),
)


def _identity_from_document(instrument: InstrumentIdentity, code: str, document: BseXbrlDocument, now: datetime) -> BseSecurityIdentity:
    if not instrument.isin:
        raise BseOfficialError("BSE identity requires a canonical ISIN.")
    if document.isin.upper() != instrument.isin.upper() or document.security_code != code:
        raise BseOfficialError("BSE XBRL identity mismatch.")
    return BseSecurityIdentity(instrument.instrument_id, document.isin.upper(), code, document.security_name,
                               document.source_url, "EXACT_ISIN_BSE_XBRL", now)


def _prior_filing(store: CorporateFilingsStore, instrument_id: str, metadata: BseResultMetadata) -> str | None:
    values = store.list(instrument_id=instrument_id, filing_type=FilingType.FINANCIAL_RESULTS, limit=500)
    candidates = tuple(item for item in values if item.source == BSE_OFFICIAL_PROVIDER and item.period_end == metadata.period_end
                       and item.financial_result is not None and item.financial_result.result_scope == metadata.scope.value
                       and item.announced_at < metadata.filing_at)
    return max(candidates, key=lambda item: (item.announced_at, item.filing_id)).filing_id if candidates and metadata.is_revised else None


def _prior_fact(store: FinancialFactStore, instrument_id: str, metric: FinancialMetric, metadata: BseResultMetadata) -> str | None:
    values = store.series(instrument_id, metric, period_type=metadata.period_type, scope=metadata.scope, limit=500)
    candidates = tuple(item for item in values if item.source == BSE_OFFICIAL_PROVIDER and item.period_end == metadata.period_end and item.published_at < metadata.filing_at)
    return max(candidates, key=lambda item: (item.published_at, item.fact_id)).fact_id if candidates and metadata.is_revised else None


def _prior_context_fact(
    store: FinancialFactStore,
    instrument_id: str,
    metric: FinancialMetric,
    metadata: BseResultMetadata,
    candidate: BseXbrlContextFact,
) -> str | None:
    values = store.series(instrument_id, metric, period_type=candidate.period_type, scope=metadata.scope, limit=500)
    matches = tuple(
        item for item in values
        if item.source == BSE_OFFICIAL_PROVIDER
        and item.period_end == candidate.context.period_end
        and item.period_start == candidate.context.period_start
        and item.value_basis is candidate.value_basis
        and item.published_at < metadata.filing_at
    )
    return max(matches, key=lambda item: (item.published_at, item.fact_id)).fact_id if matches and metadata.is_revised else None


def _filing_id(instrument: InstrumentIdentity, metadata: BseResultMetadata) -> str:
    digest = hashlib.sha256("|".join((instrument.instrument_id, metadata.security_code, metadata.xbrl_url, metadata.filing_at.isoformat())).encode()).hexdigest()[:24]
    return "bse-official:" + digest


def _header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def _official_xbrl_url(value: str, base: str) -> str:
    target = urljoin(base, value)
    parsed = urlparse(target)
    if parsed.scheme != "https" or parsed.netloc.lower() != "www.bseindia.com" or not parsed.path.startswith("/XBRLFILES/"):
        raise BseOfficialError("BSE result page referenced a non-official XBRL location.")
    return target


def _fetch_bse_text(url: str) -> str:
    try:
        with urlopen(Request(url, headers={"Accept": "text/html,application/xml", "User-Agent": "nse-stock-manager/1.0"}, method="GET"), timeout=20) as response:  # nosec B310 - explicit BSE public URL only
            data = response.read(5 * 1024 * 1024 + 1)
    except OSError as error:
        raise BseOfficialError("BSE public result/XBRL source is unavailable.") from error
    if len(data) > 5 * 1024 * 1024:
        raise BseOfficialError("BSE response exceeds the bounded adapter limit.")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise BseOfficialError("BSE response is not UTF-8 XML/HTML.") from error


def _bse_timestamp(
    value: str,
    status: BseTimestampStatus,
    *,
    optional: bool = False,
    archive_timestamp: bool = False,
) -> datetime | None:
    text = _blank(value)
    if text is None:
        return None if optional else _raise("BSE filing timestamp is absent.")
    if status is BseTimestampStatus.UNKNOWN:
        return _raise("BSE filing timestamp timezone is unknown.")
    patterns = ["%d-%m-%Y %H:%M:%S", "%m/%d/%Y %I:%M:%S %p"]
    # The immutable GENUSPOWER Result_Arch_Download snapshot proves this exact
    # 24-hour month/day form. Keep it at the structured-archive boundary;
    # legacy result-page parsing remains unchanged and does not locale-guess.
    if archive_timestamp:
        patterns.append("%m/%d/%Y %H:%M:%S")
    parsed = next((
        datetime.strptime(text, pattern)
        for pattern in patterns
        if _matches_timestamp(text, pattern)
    ), None)
    if parsed is None:
        raise BseOfficialError("BSE filing timestamp is malformed.")
    return parsed.replace(tzinfo=_IST).astimezone(UTC)


def _matches_timestamp(value: str, pattern: str) -> bool:
    try:
        datetime.strptime(value, pattern)
        return True
    except ValueError:
        return False


def _period(label: str, filing_type: str) -> tuple[datetime, FinancialPeriodType, FinancialValueBasis]:
    parts = label.split("-")
    if len(parts) < 2:
        raise BseOfficialError("BSE result period label is malformed.")
    month_token, year_token = parts[-2], parts[-1]
    months = {"JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6, "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12}
    month = months.get(month_token.upper())
    if month is None or not re.fullmatch(r"\d{2}", year_token):
        raise BseOfficialError("BSE result period label is unsupported.")
    year = 2000 + int(year_token)
    next_month = date(year + (month == 12), (month % 12) + 1, 1)
    end = datetime.combine(next_month.fromordinal(next_month.toordinal() - 1), datetime.min.time(), UTC)
    kind = filing_type.strip().upper()
    if kind == "QUARTER": return end, FinancialPeriodType.QUARTERLY, FinancialValueBasis.QUARTER_ONLY
    if kind == "YEAR": return end, FinancialPeriodType.ANNUAL, FinancialValueBasis.FULL_YEAR
    raise BseOfficialError("BSE half-year/unspecified result basis is not canonicalised.")


def _fiscal_year(end: datetime) -> int: return end.year if end.month == 3 else end.year + 1
def _fiscal_quarter(end: datetime) -> int | None: return {6: 1, 9: 2, 12: 3, 3: 4}.get(end.month)
def _blank(value: str | None) -> str | None:
    text = value.strip() if value else ""
    return text if text and text not in {"-", "--"} else None
def _local(tag: str) -> str: return tag.rsplit("}", 1)[-1].split(":")[-1]
def _first(values: dict[str, list[tuple[str, dict[str, str]]]], name: str) -> str | None:
    items = values.get(name, ())
    return items[0][0] if items else None
def _required_single(values: dict[str, list[tuple[str, dict[str, str]]]], name: str) -> str:
    value = _first(values, name)
    if not value: raise BseOfficialError("BSE XBRL identity is incomplete.")
    return value
def _first_decimal(values: dict[str, list[tuple[str, dict[str, str]]]], name: str) -> Decimal | None:
    raw = _first(values, name)
    if raw is None: return None
    try: return Decimal(raw.replace(",", ""))
    except InvalidOperation: raise BseOfficialError("BSE XBRL numerical fact is malformed.") from None
def _scope(value: str | None) -> StatementScope | None:
    text = (value or "").upper()
    return StatementScope.CONSOLIDATED if "CONSOLIDATED" in text else StatementScope.STANDALONE if "STANDALONE" in text else None
def _currency(value: str | None) -> str | None:
    text = (value or "").strip().upper()
    return "INR" if text in {"INR", "INDIAN RUPEES", "RUPEES", "RS."} else None
def _scale(value: str | None) -> NumericScale | None:
    text = (value or "").strip().upper().replace(" ", "")
    mapping = {"RUPEES": NumericScale.UNITS, "UNITS": NumericScale.UNITS, "THOUSANDS": NumericScale.THOUSANDS,
               "LAKHS": NumericScale.LAKHS, "LACS": NumericScale.LAKHS, "CRORES": NumericScale.CRORES,
               "MILLIONS": NumericScale.MILLIONS}
    return mapping.get(text)


def _raw_xbrl_value_scale(metric: FinancialMetric, source_level_of_rounding: NumericScale) -> NumericScale:
    """Store direct XBRL numeric facts in their declared raw unit.

    ``LevelOfRounding`` is retained in provenance as statement display
    metadata. It is not a multiplier for the XBRL numeric value itself. This
    also keeps per-share metrics, notably EPS, out of statement-wide monetary
    display-scale conversions.
    """
    _ = metric, source_level_of_rounding
    return NumericScale.UNITS
def _schema_version(payload: str) -> str | None:
    match = re.search(r"IFIndAs\s+V([\d.]+)", payload, re.IGNORECASE)
    return "IFIndAs-V" + match.group(1) if match else None
def _raise(message: str): raise BseOfficialError(message)
