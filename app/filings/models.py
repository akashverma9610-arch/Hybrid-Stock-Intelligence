from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from app.market_data.models import Exchange, InstrumentIdentity, MarketDataProvenance


class FilingType(StrEnum):
    CORPORATE_ANNOUNCEMENT="CORPORATE_ANNOUNCEMENT"; FINANCIAL_RESULTS="FINANCIAL_RESULTS"; BOARD_MEETING="BOARD_MEETING"; INVESTOR_PRESENTATION="INVESTOR_PRESENTATION"; EARNINGS_CALL_OR_INVESTOR_MEET="EARNINGS_CALL_OR_INVESTOR_MEET"; CORPORATE_ACTION="CORPORATE_ACTION"; SHAREHOLDING_PATTERN="SHAREHOLDING_PATTERN"; FUND_RAISE="FUND_RAISE"; ACQUISITION_MERGER="ACQUISITION_MERGER"; ORDER_CONTRACT="ORDER_CONTRACT"; MANAGEMENT_CHANGE="MANAGEMENT_CHANGE"; REGULATORY_LEGAL="REGULATORY_LEGAL"; DIVIDEND="DIVIDEND"; BONUS="BONUS"; SPLIT="SPLIT"; RIGHTS="RIGHTS"; BUYBACK="BUYBACK"; OTHER="OTHER"


class PrimarySourceQuality(StrEnum):
    PRIMARY_EXCHANGE="PRIMARY_EXCHANGE"; PRIMARY_ISSUER="PRIMARY_ISSUER"


class AttachmentParseStatus(StrEnum):
    NOT_FETCHED="NOT_FETCHED"; AVAILABLE="AVAILABLE"; PARSED="PARSED"; UNSUPPORTED="UNSUPPORTED"; FAILED="FAILED"


class FilingTextAvailability(StrEnum):
    NOT_AVAILABLE="NOT_AVAILABLE"; SOURCE_TEXT="SOURCE_TEXT"; DOCUMENT_ONLY="DOCUMENT_ONLY"


class FilingIngestionStatus(StrEnum):
    COMPLETED="COMPLETED"; PARTIAL="PARTIAL"; FAILED="FAILED"


@dataclass(frozen=True, slots=True)
class FilingAttachment:
    attachment_id: str
    document_type: str
    title: str | None
    filename: str | None
    source_reference: str
    mime_type: str | None
    published_at: datetime | None
    checksum: str | None = None
    parse_status: AttachmentParseStatus = AttachmentParseStatus.NOT_FETCHED
    is_xbrl: bool = False


@dataclass(frozen=True, slots=True)
class CorporateActionDisclosure:
    action_type: FilingType
    record_date: datetime | None = None
    ex_date: datetime | None = None
    effective_date: datetime | None = None
    ratio: Decimal | None = None
    amount: Decimal | None = None
    terms_text: str | None = None


@dataclass(frozen=True, slots=True)
class FinancialResultMetadata:
    period_end: datetime
    result_scope: str | None = None
    result_type: str | None = None
    revised: bool = False


@dataclass(frozen=True, slots=True)
class BoardMeetingMetadata:
    meeting_date: datetime
    purpose: str | None = None
    related_filing_id: str | None = None


@dataclass(frozen=True, slots=True)
class CorporateFiling:
    filing_id: str
    instrument: InstrumentIdentity
    exchange: Exchange
    source: str
    source_quality: PrimarySourceQuality
    filing_type: FilingType
    raw_category: str | None
    subject: str
    announced_at: datetime
    received_at: datetime
    source_reference: str | None
    document_reference: str | None
    provenance: MarketDataProvenance
    effective_at: datetime | None = None
    period_end: datetime | None = None
    board_meeting_date: datetime | None = None
    text_availability: FilingTextAvailability = FilingTextAvailability.NOT_AVAILABLE
    attachments: tuple[FilingAttachment, ...] = ()
    revision_of_filing_id: str | None = None
    action: CorporateActionDisclosure | None = None
    financial_result: FinancialResultMetadata | None = None
    board_meeting: BoardMeetingMetadata | None = None
    reporting_as_of: datetime | None = None
    normalization_version: str = "corporate-filings-v1"
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PrimarySourceFilingRecord:
    source: str
    exchange: Exchange
    instrument: InstrumentIdentity
    source_reference: str | None
    raw_category: str | None
    subject: str
    announced_at: datetime
    received_at: datetime
    document_reference: str | None = None
    effective_at: datetime | None = None
    period_end: datetime | None = None
    board_meeting_date: datetime | None = None
    text_availability: FilingTextAvailability = FilingTextAvailability.NOT_AVAILABLE
    attachments: tuple[FilingAttachment, ...] = ()
    revision_of_filing_id: str | None = None
    action: CorporateActionDisclosure | None = None
    financial_result: FinancialResultMetadata | None = None
    board_meeting: BoardMeetingMetadata | None = None
    reporting_as_of: datetime | None = None
    source_quality: PrimarySourceQuality = PrimarySourceQuality.PRIMARY_EXCHANGE


@dataclass(frozen=True, slots=True)
class CorporateFilingsIngestionReport:
    source: str
    requested_start: datetime
    requested_end: datetime
    received_count: int
    accepted_count: int
    duplicate_count: int
    revision_count: int
    rejected_count: int
    attachment_count: int
    earliest_announced_at: datetime | None
    latest_announced_at: datetime | None
    status: FilingIngestionStatus
    warnings: tuple[str, ...]
    started_at: datetime
    completed_at: datetime
