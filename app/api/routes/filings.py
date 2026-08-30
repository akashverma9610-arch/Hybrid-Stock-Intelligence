from datetime import datetime
from fastapi import APIRouter, Depends, Query
from app.api.dependencies import get_filings_query_service
from app.api.filings_query import FilingsQueryService
from app.api.schemas.filings import CorporateFilingListResponse, CorporateFilingResponse, FilingAttachmentResponse
from app.filings.models import CorporateFiling, FilingType

router=APIRouter(tags=["filings"])

@router.get("/filings",response_model=CorporateFilingListResponse)
def filings(symbol:str|None=None, filing_type:FilingType|None=Query(default=None,alias="type"), start:datetime|None=Query(default=None,alias="from"), end:datetime|None=Query(default=None,alias="to"), limit:int=Query(default=50,ge=1,le=100), service:FilingsQueryService=Depends(get_filings_query_service)):
    return CorporateFilingListResponse(items=tuple(_filing(item) for item in service.list_filings(instrument_id=symbol,filing_type=filing_type,start=start,end=end,limit=limit)))

@router.get("/filings/{filing_id}",response_model=CorporateFilingResponse)
def filing(filing_id:str,service:FilingsQueryService=Depends(get_filings_query_service)):
    return _filing(service.filing(filing_id))

def _filing(value:CorporateFiling)->CorporateFilingResponse:
    return CorporateFilingResponse(
        filing_id=value.filing_id, instrument_id=value.instrument.instrument_id, symbol=value.instrument.symbol,
        exchange=value.exchange.value, source=value.source, source_quality=value.source_quality.value,
        filing_type=value.filing_type.value, raw_category=value.raw_category, subject=value.subject,
        announced_at=value.announced_at, received_at=value.received_at, source_reference=value.source_reference,
        document_reference=value.document_reference, effective_at=value.effective_at, period_end=value.period_end,
        board_meeting_date=value.board_meeting_date, reporting_as_of=value.reporting_as_of,
        revision_of_filing_id=value.revision_of_filing_id, warnings=value.warnings,
        attachments=tuple(FilingAttachmentResponse(
            attachment_id=item.attachment_id, document_type=item.document_type, title=item.title,
            filename=item.filename, source_reference=item.source_reference, mime_type=item.mime_type,
            published_at=item.published_at, checksum=item.checksum, parse_status=item.parse_status.value,
            is_xbrl=item.is_xbrl,
        ) for item in value.attachments),
    )
