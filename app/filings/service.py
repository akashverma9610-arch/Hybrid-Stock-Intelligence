"""Validation and immutable ingestion for supplied primary-source records."""

from __future__ import annotations

from datetime import UTC, datetime

from app.filings.models import CorporateFilingsIngestionReport, FilingIngestionStatus, FilingType
from app.filings.providers import CorporateFilingsProvider, normalize_primary_filing
from app.filings.store import CorporateFilingsStore, FilingWriteOutcome


class CorporateFilingsIngestionService:
    def __init__(self, provider: CorporateFilingsProvider, store: CorporateFilingsStore, *, clock=lambda: datetime.now(UTC)) -> None:
        self._provider, self._store, self._clock = provider, store, clock

    def ingest(self, *, instrument_id: str | None, start: datetime, end: datetime, filing_types: tuple[FilingType, ...] = ()) -> CorporateFilingsIngestionReport:
        started = self._clock(); records = self._provider.list_filings(instrument_id=instrument_id, start=start, end=end, filing_types=filing_types)
        accepted = duplicates = revisions = rejected = attachments = 0; warnings: list[str] = []; announced: list[datetime] = []
        source = records[0].source if records else "unconfigured"
        for record in records:
            try:
                filing = normalize_primary_filing(record)
                _validate(filing)
                outcome = self._store.save(filing)
            except (TypeError, ValueError):
                rejected += 1; warnings.append("FILING_VALIDATION_REJECTED"); continue
            announced.append(filing.announced_at); attachments += len(filing.attachments)
            if outcome is FilingWriteOutcome.INSERTED:
                accepted += 1; revisions += int(filing.revision_of_filing_id is not None)
            else:
                duplicates += 1
        status = FilingIngestionStatus.FAILED if records and rejected == len(records) else FilingIngestionStatus.PARTIAL if rejected else FilingIngestionStatus.COMPLETED
        return CorporateFilingsIngestionReport(source, start, end, len(records), accepted, duplicates, revisions, rejected, attachments, min(announced) if announced else None, max(announced) if announced else None, status, tuple(sorted(set(warnings))), started, self._clock())


def _validate(value) -> None:
    if not value.instrument.instrument_id or value.exchange.value not in {"NSE", "BSE"}:
        raise ValueError("Filing requires a canonical NSE/BSE instrument.")
    if value.announced_at.tzinfo is None or value.received_at.tzinfo is None:
        raise ValueError("Filing timestamps must be timezone aware.")
    if not value.filing_id or not value.subject.strip() or value.received_at < value.announced_at:
        raise ValueError("Filing identity or timestamps are invalid.")
    if value.period_end is not None and value.period_end > value.announced_at:
        raise ValueError("Filing period cannot end after its announcement.")
    if any(not attachment.attachment_id or not attachment.source_reference for attachment in value.attachments):
        raise ValueError("Filing attachment metadata is malformed.")
