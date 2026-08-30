from datetime import datetime
from pydantic import BaseModel


class FilingAttachmentResponse(BaseModel):
    attachment_id: str; document_type: str; title: str | None; filename: str | None; source_reference: str; mime_type: str | None; published_at: datetime | None; checksum: str | None; parse_status: str; is_xbrl: bool

class CorporateFilingResponse(BaseModel):
    filing_id: str; instrument_id: str; symbol: str; exchange: str; source: str; source_quality: str; filing_type: str; raw_category: str | None; subject: str; announced_at: datetime; received_at: datetime; source_reference: str | None; document_reference: str | None; effective_at: datetime | None; period_end: datetime | None; board_meeting_date: datetime | None; reporting_as_of: datetime | None; revision_of_filing_id: str | None; warnings: tuple[str, ...]; attachments: tuple[FilingAttachmentResponse, ...]

class CorporateFilingListResponse(BaseModel): items: tuple[CorporateFilingResponse, ...]
