"""Primary-source filing adapter contracts; adapters never perform network I/O here."""

from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from typing import Protocol

from app.filings.models import CorporateFiling, FilingType, PrimarySourceFilingRecord
from app.market_data.models import MarketDataProvenance


class CorporateFilingsProvider(Protocol):
    def list_filings(self, *, instrument_id: str | None, start: datetime, end: datetime, filing_types: tuple[FilingType, ...] = (), cursor: str | None = None) -> tuple[PrimarySourceFilingRecord, ...]: ...
    def get_filing_document(self, source_reference: str) -> object | None: ...


def filing_type_for(raw_category: str | None) -> FilingType:
    text = (raw_category or "").upper()
    for needle, filing_type in (("DIVIDEND", FilingType.DIVIDEND), ("BONUS", FilingType.BONUS), ("SPLIT", FilingType.SPLIT), ("RESULT", FilingType.FINANCIAL_RESULTS), ("BOARD", FilingType.BOARD_MEETING), ("PRESENTATION", FilingType.INVESTOR_PRESENTATION), ("SHAREHOLD", FilingType.SHAREHOLDING_PATTERN), ("ACQUIS", FilingType.ACQUISITION_MERGER), ("ORDER", FilingType.ORDER_CONTRACT), ("BUYBACK", FilingType.BUYBACK), ("RIGHT", FilingType.RIGHTS)):
        if needle in text:
            return filing_type
    return FilingType.CORPORATE_ANNOUNCEMENT if text else FilingType.OTHER


def normalize_primary_filing(record: PrimarySourceFilingRecord) -> CorporateFiling:
    filing_type = record.action.action_type if record.action is not None else filing_type_for(record.raw_category)
    identity = record.source_reference or sha256("|".join((record.source, record.exchange.value, record.instrument.instrument_id, record.subject, record.announced_at.isoformat(), record.document_reference or "")).encode()).hexdigest()
    filing_id = f"{record.source}:{record.exchange.value}:{identity}"
    provenance = MarketDataProvenance(record.source, record.source_reference, record.announced_at, record.announced_at, record.received_at, "corporate-filings-v1", identity, record.document_reference)
    return CorporateFiling(filing_id, record.instrument, record.exchange, record.source, record.source_quality, filing_type, record.raw_category, record.subject, record.announced_at, record.received_at, record.source_reference, record.document_reference, provenance, record.effective_at, record.period_end, record.board_meeting_date, record.text_availability, record.attachments, record.revision_of_filing_id, record.action, record.financial_result, record.board_meeting, record.reporting_as_of)


class NSECorporateFilingsAdapter:
    """Normalizes supplied NSE primary records; no endpoint or session is assumed."""
    source = "nse"

    def normalize(self, record: PrimarySourceFilingRecord) -> CorporateFiling:
        if record.source != self.source:
            raise ValueError("NSE adapter accepts NSE source records only.")
        return normalize_primary_filing(record)


class BSECorporateFilingsAdapter:
    """Normalizes supplied BSE primary records; no endpoint or session is assumed."""
    source = "bse"

    def normalize(self, record: PrimarySourceFilingRecord) -> CorporateFiling:
        if record.source != self.source:
            raise ValueError("BSE adapter accepts BSE source records only.")
        return normalize_primary_filing(record)


class MockPrimarySourceFilingsProvider:
    """Deterministic supplied-record provider for tests and local composition."""

    def __init__(self, records: tuple[PrimarySourceFilingRecord, ...]) -> None:
        self._records = records

    def list_filings(self, *, instrument_id: str | None, start: datetime, end: datetime, filing_types: tuple[FilingType, ...] = (), cursor: str | None = None) -> tuple[PrimarySourceFilingRecord, ...]:
        del cursor
        values = tuple(record for record in self._records if (instrument_id is None or record.instrument.instrument_id == instrument_id) and start <= record.announced_at <= end)
        return tuple(record for record in values if not filing_types or filing_type_for(record.raw_category) in filing_types)

    def get_filing_document(self, source_reference: str) -> object | None:
        del source_reference
        return None
