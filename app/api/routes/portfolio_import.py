from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile

from app.api.dependencies import get_portfolio_import_service
from app.api.errors import APIRequestError
from app.api.schemas.portfolio_import import (
    ExtractedHoldingCandidateResponse, PortfolioImportConfirmationResponse,
    PortfolioImportConfirmRequest, PortfolioScreenshotImportResponse,
)
from app.portfolio_import.models import ReviewedHolding, UploadedScreenshot
from app.portfolio_import.service import PortfolioImportError, PortfolioImportService


router = APIRouter(prefix="/portfolio/import", tags=["portfolio"])

_ALLOWED_CONTENT_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})
_MAX_IMAGES = 5
_MAX_IMAGE_BYTES = 5 * 1024 * 1024


@router.post("/screenshots", response_model=PortfolioScreenshotImportResponse)
async def import_screenshots(
    files: list[UploadFile] = File(...),
    service: PortfolioImportService = Depends(get_portfolio_import_service),
) -> PortfolioScreenshotImportResponse:
    if not files or len(files) > _MAX_IMAGES:
        raise APIRequestError(status_code=422, code="IMAGE_COUNT_INVALID", message=f"Upload between 1 and {_MAX_IMAGES} images.")
    images: list[UploadedScreenshot] = []
    for index, upload in enumerate(files):
        if upload.content_type not in _ALLOWED_CONTENT_TYPES:
            raise APIRequestError(status_code=415, code="UNSUPPORTED_IMAGE", message="Only JPG, PNG, and WebP images are supported.")
        content = await upload.read(_MAX_IMAGE_BYTES + 1)
        if not content or len(content) > _MAX_IMAGE_BYTES:
            raise APIRequestError(status_code=413, code="FILE_TOO_LARGE", message="Image is empty or exceeds the upload size limit.")
        # Filename is metadata only.  No file is written or exposed by the API.
        images.append(UploadedScreenshot(index, upload.filename or f"upload-{index}", upload.content_type, content))
    try:
        return _draft_response(service.create_draft(tuple(images)))
    except PortfolioImportError as error:
        raise _service_error(error) from error
    finally:
        # Drafts retain extracted fields only.  The local `images` collection,
        # including its raw bytes, goes out of scope after this request.
        images.clear()


@router.post("/{import_id}/confirm", response_model=PortfolioImportConfirmationResponse)
def confirm_import(
    import_id: str,
    payload: PortfolioImportConfirmRequest,
    service: PortfolioImportService = Depends(get_portfolio_import_service),
) -> PortfolioImportConfirmationResponse:
    rows = tuple(ReviewedHolding(**row.model_dump()) for row in payload.holdings)
    try:
        result = service.confirm(import_id, rows, mode=payload.mode)
    except PortfolioImportError as error:
        raise _service_error(error) from error
    return PortfolioImportConfirmationResponse(
        status=result.status.value, portfolio_id=result.portfolio_id, portfolio_snapshot_id=result.portfolio_snapshot_id,
        holdings_imported=result.holdings_imported, warnings=result.warnings, data_as_of=result.data_as_of,
    )


@router.post("/{import_id}/cancel", response_model=PortfolioScreenshotImportResponse)
def cancel_import(import_id: str, service: PortfolioImportService = Depends(get_portfolio_import_service)) -> PortfolioScreenshotImportResponse:
    try:
        return _draft_response(service.cancel(import_id))
    except PortfolioImportError as error:
        raise _service_error(error) from error


def _draft_response(draft) -> PortfolioScreenshotImportResponse:
    return PortfolioScreenshotImportResponse(
        import_id=draft.import_id, status=draft.status.value, created_at=draft.created_at, expires_at=draft.expires_at,
        image_count=draft.image_count, warnings=draft.warnings,
        holdings=tuple(ExtractedHoldingCandidateResponse(
            row_id=candidate.row_id, symbol=candidate.symbol, instrument_name=candidate.instrument_name,
            quantity=candidate.quantity, average_price=candidate.average_price, current_price=candidate.current_price,
            invested_value=candidate.invested_value, current_value=candidate.current_value, pnl=candidate.pnl,
            pnl_percent=candidate.pnl_percent, extraction_confidence=candidate.extraction_confidence,
            field_warnings=candidate.field_warnings, source_image_index=candidate.source_image_index,
            resolution_status=candidate.resolution_status.value, instrument_id=candidate.instrument_id,
        ) for candidate in draft.holdings),
    )


def _service_error(error: PortfolioImportError) -> APIRequestError:
    codes = {
        "PROVIDER_UNAVAILABLE": 503, "PORTFOLIO_PERSISTENCE_UNAVAILABLE": 503,
        "IMPORT_NOT_FOUND": 404, "IMPORT_EXPIRED": 410, "UNSUPPORTED_IMAGE": 415,
        "FILE_TOO_LARGE": 413,
    }
    return APIRequestError(status_code=codes.get(error.code, 422), code=error.code, message=error.message)
