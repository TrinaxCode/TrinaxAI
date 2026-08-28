"""Canonical FastAPI application for TrinaxAI."""

from __future__ import annotations

import logging
import os
import re
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.datastructures import MutableHeaders
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.errors import (
    generic_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from app.routes import ROUTERS
from app.security.admin_auth import SAFE_DEFAULT_ORIGIN_REGEX, SAFE_DEFAULT_ORIGINS
from app.services import shared_runtime as runtime
from app.services import system_service as lifecycle_runtime

LOG = logging.getLogger("trinaxai.app")
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_PRIVATE_CACHE_PREFIXES = (
    "/app-state",
    "/attachments",
    "/collections",
    "/documents/",
    "/system/",
    "/v1/",
)


def _request_id(request: Request) -> str:
    supplied = request.headers.get("X-Request-ID", "").strip()
    return supplied if _REQUEST_ID_RE.fullmatch(supplied) else uuid.uuid4().hex


async def _security_and_observability(request: Request, call_next):
    """Attach a correlation id, local timing, and defensive API headers.

    Only method/path/status/timing are logged. Prompts, chunks, filenames,
    tokens and response bodies remain private by default.
    """
    request_id = _request_id(request)
    request.state.request_id = request_id
    started = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - started) * 1000

    response.headers["X-Request-ID"] = request_id
    response.headers["Server-Timing"] = f"app;dur={duration_ms:.1f}"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
    response.headers["Permissions-Policy"] = "camera=(), geolocation=(), payment=(), usb=()"
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000"
    if request.url.path.startswith(_PRIVATE_CACHE_PREFIXES):
        response.headers["Cache-Control"] = "no-store"

    peer = request.client.host if request.client else "unknown"
    LOG.info(
        "request id=%s method=%s path=%s status=%s duration_ms=%.1f peer=%s",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
        peer,
    )
    return response


class _SecurityObservabilityMiddleware:
    """ASGI-native equivalent that preserves streaming response semantics."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        scope.setdefault("state", {})
        request = Request(scope, receive)
        request_id = _request_id(request)
        request.state.request_id = request_id
        started = time.perf_counter()

        async def send_with_headers(message):
            if message.get("type") == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-Request-ID"] = request_id
                headers["Server-Timing"] = f"app;dur={(time.perf_counter() - started) * 1000:.1f}"
                headers["X-Content-Type-Options"] = "nosniff"
                headers["Referrer-Policy"] = "no-referrer"
                headers["X-Frame-Options"] = "DENY"
                headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
                headers["Permissions-Policy"] = "camera=(), geolocation=(), payment=(), usb=()"
                if request.url.scheme == "https":
                    headers["Strict-Transport-Security"] = "max-age=31536000"
                if request.url.path.startswith(_PRIVATE_CACHE_PREFIXES):
                    headers["Cache-Control"] = "no-store"
                LOG.info(
                    "request id=%s method=%s path=%s status=%s duration_ms=%.1f peer=%s",
                    request_id,
                    request.method,
                    request.url.path,
                    message.get("status"),
                    (time.perf_counter() - started) * 1000,
                    request.client.host if request.client else "unknown",
                )
            await send(message)

        await self.app(scope, receive, send_with_headers)


def _cors_origins() -> list[str]:
    configured = os.getenv("TRINAXAI_CORS_ORIGINS", ",".join(SAFE_DEFAULT_ORIGINS)).strip()
    if configured == "*":
        return ["*"]
    origins = [origin.strip() for origin in configured.split(",") if origin.strip()]
    if not origins:
        LOG.warning("Empty CORS allowlist; using safe localhost defaults")
        return list(SAFE_DEFAULT_ORIGINS)
    return origins


@asynccontextmanager
async def lifespan(_app: FastAPI):
    runtime.initialize_runtime()
    try:
        yield
    finally:
        lifecycle_runtime.shutdown_runtime()


def create_app() -> FastAPI:
    application = FastAPI(title="TrinaxAI RAG API", lifespan=lifespan)
    application.add_middleware(_SecurityObservabilityMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_origin_regex=os.getenv(
            "TRINAXAI_CORS_ORIGIN_REGEX",
            SAFE_DEFAULT_ORIGIN_REGEX,
        ),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    for router in ROUTERS:
        application.include_router(router)
    application.add_exception_handler(StarletteHTTPException, http_exception_handler)
    application.add_exception_handler(RequestValidationError, validation_exception_handler)
    application.add_exception_handler(Exception, generic_exception_handler)
    return application


app = create_app()
