"""Canonical FastAPI application for TrinaxAI."""

from __future__ import annotations

import logging
import os
import re
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from app.routes import ROUTERS
from app.security.admin_auth import SAFE_DEFAULT_ORIGINS
from app.services import shared_runtime as runtime

LOG = logging.getLogger("trinaxai.app")
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_PRIVATE_CACHE_PREFIXES = (
    "/app-state",
    "/attachments",
    "/v1/memory",
    "/v1/sources",
    "/v1/agent",
    "/v1/pairing",
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
    yield


def create_app() -> FastAPI:
    application = FastAPI(title="TrinaxAI RAG API", lifespan=lifespan)
    application.middleware("http")(_security_and_observability)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_origin_regex=os.getenv(
            "TRINAXAI_CORS_ORIGIN_REGEX",
            r"https?://(localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+):(3334|3335)",
        ),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    for router in ROUTERS:
        application.include_router(router)
    application.add_exception_handler(HTTPException, runtime._trinaxai_http_exception_handler)
    application.add_exception_handler(Exception, runtime._trinaxai_generic_exception_handler)
    return application


app = create_app()
