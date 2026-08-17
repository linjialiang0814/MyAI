from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.runtime.error_model import AppError, ErrorCode, ErrorInfo, classify_exception
from app.runtime.storage_redaction import sanitize_text_for_storage


logger = logging.getLogger(__name__)


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = (request.headers.get("x-request-id") or "").strip() or str(uuid4())
        request.state.request_id = request_id[:128]
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response


def register_error_handlers(application: FastAPI) -> None:
    application.add_middleware(RequestIdMiddleware)

    @application.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError):
        return _response(request, exc.info)

    @application.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        details = [
            {
                "location": ".".join(str(part) for part in item.get("loc", ())),
                "message": item.get("msg", "invalid value"),
                "type": item.get("type", "validation_error"),
            }
            for item in exc.errors()
        ]
        return _response(
            request,
            ErrorInfo(
                code=ErrorCode.INVALID_ARGUMENT,
                message="The request is invalid.",
                details={"violations": details},
            ),
            status_code=422,
        )

    @application.exception_handler(HTTPException)
    async def handle_http_error(request: Request, exc: HTTPException):
        info = ErrorInfo(
            code=_code_for_http_status(exc.status_code),
            message=(
                sanitize_text_for_storage(str(exc.detail), max_chars=1_024)
                if isinstance(exc.detail, str)
                else "The request failed."
            ),
            retryable=exc.status_code in {429, 502, 503, 504},
        )
        return _response(request, info, status_code=exc.status_code, headers=exc.headers)

    @application.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", "unknown")
        info = classify_exception(exc, operation=f"api.{request.method.lower()}")
        if info.code == ErrorCode.INTERNAL_ERROR:
            logger.error(
                "Unhandled API error request_id=%s error_type=%s error_code=%s",
                request_id,
                type(exc).__name__,
                info.code.value,
            )
        return _response(request, info)


def _response(
    request: Request,
    info: ErrorInfo,
    *,
    status_code: int | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None) or str(uuid4())
    payload = info.to_dict()
    effective_status = status_code or info.http_status
    payload["http_status"] = effective_status
    payload["request_id"] = request_id
    response_headers = dict(headers or {})
    response_headers["X-Request-ID"] = request_id
    return JSONResponse(
        status_code=effective_status,
        content={"error": payload},
        headers=response_headers,
    )


def _code_for_http_status(status_code: int) -> ErrorCode:
    if status_code in {400, 422}:
        return ErrorCode.INVALID_ARGUMENT
    if status_code in {401, 403}:
        return ErrorCode.FORBIDDEN
    if status_code == 404:
        return ErrorCode.NOT_FOUND
    if status_code == 409:
        return ErrorCode.CONFLICT
    if status_code == 429:
        return ErrorCode.RATE_LIMITED
    if status_code == 504:
        return ErrorCode.OPERATION_TIMEOUT
    if status_code in {502, 503}:
        return ErrorCode.DEPENDENCY_UNAVAILABLE
    return ErrorCode.INTERNAL_ERROR
