from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request, Response

from app.api.dependencies import get_external_intelligence_application_service
from app.api.errors import APIRequestError
from app.api.intelligence_auth import AuthenticatedIntelligenceProducer, IntelligenceScope, require_intelligence_scope
from app.api.schemas.intelligence import ExternalIntelligenceEventRequest, ExternalIntelligenceReceiptResponse
from app.intelligence.external_intelligence_application import ExternalIntelligenceApplicationDisposition

router = APIRouter(prefix="/intelligence", tags=["intelligence"])
MAX_EXTERNAL_INTELLIGENCE_EVENT_BYTES = 256 * 1024

@router.get("/auth-check")
def auth_check(producer: AuthenticatedIntelligenceProducer = Depends(require_intelligence_scope(IntelligenceScope.INGEST))):
    return {"producer_id": producer.producer_id, "credential_id": producer.credential_id, "scopes": sorted(item.value for item in producer.scopes)}


def _enforce_event_payload_bound(request: Request) -> None:
    value = request.headers.get("content-length")
    if value is None:
        raise APIRequestError(status_code=411, code="CONTENT_LENGTH_REQUIRED", message="Intelligence event input requires a declared content length.")
    try:
        size = int(value)
    except ValueError as error:
        raise APIRequestError(status_code=400, code="INVALID_CONTENT_LENGTH", message="Intelligence event request content length is invalid.") from error
    if size < 0 or size > MAX_EXTERNAL_INTELLIGENCE_EVENT_BYTES:
        raise APIRequestError(status_code=413, code="INTELLIGENCE_EVENT_TOO_LARGE", message="Intelligence event request exceeds the 256 KiB limit.")


@router.post(
    "/events",
    response_model=ExternalIntelligenceReceiptResponse,
    dependencies=[Depends(_enforce_event_payload_bound)],
    operation_id="ingest_external_intelligence_event",
)
def ingest_external_intelligence_event(
    payload: ExternalIntelligenceEventRequest,
    request: Request,
    response: Response,
    producer: AuthenticatedIntelligenceProducer = Depends(require_intelligence_scope(IntelligenceScope.INGEST)),
) -> ExternalIntelligenceReceiptResponse:
    """Ingest one bounded, authenticated event; supplied references are never fetched."""
    try:
        command = payload.to_command(producer.producer_id, datetime.now(UTC))
        receipt = get_external_intelligence_application_service(request).record_event(command)
    except ValueError as error:
        raise APIRequestError(status_code=422, code="INVALID_INTELLIGENCE_EVENT", message="Intelligence event payload is invalid.") from error
    result = ExternalIntelligenceReceiptResponse.from_receipt(receipt)
    if receipt.disposition is ExternalIntelligenceApplicationDisposition.REJECTED_CONFLICT:
        response.status_code = 409
    elif receipt.disposition is not ExternalIntelligenceApplicationDisposition.ACCEPTED_EXISTING:
        response.status_code = 201
    return result
