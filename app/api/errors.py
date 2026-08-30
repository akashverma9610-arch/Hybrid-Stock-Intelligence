"""Safe API error responses."""

from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.schemas.errors import APIErrorDetail, APIErrorResponse


logger = logging.getLogger(__name__)


class APIRequestError(Exception):
    """Expected, safe API error with no internal details."""

    def __init__(self, *, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


async def api_request_error_handler(request: Request, error: APIRequestError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", uuid4().hex)
    payload = APIErrorResponse(
        error=APIErrorDetail(code=error.code, message=error.message, request_id=request_id)
    )
    return JSONResponse(
        status_code=error.status_code,
        content=payload.model_dump(),
        headers={"X-Request-ID": request_id},
    )


async def unexpected_exception_handler(request: Request, error: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", uuid4().hex)
    logger.exception("unhandled_api_exception request_id=%s", request_id, exc_info=error)
    payload = APIErrorResponse(
        error=APIErrorDetail(
            code="INTERNAL_ERROR",
            message="An unexpected error occurred.",
            request_id=request_id,
        )
    )
    return JSONResponse(
        status_code=500,
        content=payload.model_dump(),
        headers={"X-Request-ID": request_id},
    )


async def request_validation_error_handler(request: Request, error: RequestValidationError) -> JSONResponse:
    """Avoid FastAPI's default echo of invalid request values, including secrets."""
    del error
    request_id = getattr(request.state, "request_id", uuid4().hex)
    payload = APIErrorResponse(
        error=APIErrorDetail(
            code="INVALID_REQUEST",
            message="The request is invalid.",
            request_id=request_id,
        )
    )
    return JSONResponse(status_code=422, content=payload.model_dump(), headers={"X-Request-ID": request_id})
