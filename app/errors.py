"""FastAPI adapter for the shared, non-leaking error contract."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from trinaxai_errors import ErrorCategory, ErrorInfo, classify_error

LOG = logging.getLogger("trinaxai.errors")


def _request_id(request: Request) -> str | None:
    value = getattr(request.state, "request_id", None)
    return value if isinstance(value, str) and value else None


def _request_is_spanish(request: Request) -> bool:
    value = request.headers.get("accept-language", "").lower()
    return value.split(",", 1)[0].strip().startswith("es")


def _log_failure(request: Request, info: ErrorInfo, exc: BaseException) -> None:
    # Keep exception text and tracebacks out of logs too: provider errors can
    # contain credentials, URLs, prompts, or local paths.
    LOG.error(
        "request failure request_id=%s category=%s code=%s exception_type=%s developer_log=%s",
        _request_id(request) or "unknown",
        info.category.value,
        info.code,
        type(exc).__name__,
        info.definition.developer_log,
    )


def _response(
    request: Request,
    exc: BaseException,
    *,
    status_code: int,
    hint: Any = "",
    category: ErrorCategory | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    info = classify_error(exc, status_code=status_code, hint=hint, category=category)
    _log_failure(request, info, exc)
    canonical = info.to_client_dict(spanish=_request_is_spanish(request))
    detail: dict[str, Any] = {
        key: hint[key]
        for key in ("code", "provider", "field", "collection", "collection_id")
        if status_code < 500 and isinstance(hint, dict) and key in hint
    }
    legacy_code = detail.get("code")
    detail.update(canonical)
    detail["error_code"] = info.code
    if isinstance(legacy_code, str) and legacy_code and legacy_code != info.code:
        detail["code"] = legacy_code
        detail["legacy_code"] = legacy_code
    response_headers = dict(headers or {})
    request_id = _request_id(request)
    if request_id:
        response_headers["X-Request-ID"] = request_id
    if info.retryable and "Retry-After" not in response_headers:
        response_headers["Retry-After"] = "1"
    return JSONResponse(
        status_code=status_code,
        content={"detail": detail, "error": canonical, "request_id": request_id},
        headers=response_headers,
    )


async def http_exception_handler(request: Request, exc: HTTPException | StarletteHTTPException) -> JSONResponse:
    return _response(
        request,
        exc,
        status_code=exc.status_code,
        hint=getattr(exc, "detail", ""),
        headers=getattr(exc, "headers", None),
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return _response(request, exc, status_code=422, category=ErrorCategory.INVALID_INPUT)


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return _response(request, exc, status_code=500)


__all__ = ["generic_exception_handler", "http_exception_handler", "validation_exception_handler"]
