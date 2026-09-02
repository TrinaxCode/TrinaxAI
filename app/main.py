"""Canonical FastAPI application for TrinaxAI."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.errors import (
    generic_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from app.routes import ROUTERS
from app.security.admin_auth import SAFE_DEFAULT_ORIGIN_REGEX, SAFE_DEFAULT_ORIGINS
from app.security.observability import SecurityObservabilityMiddleware
from app.services import shared_runtime as runtime
from app.services import system_service as lifecycle_runtime

LOG = logging.getLogger("trinaxai.app")


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
    application.add_middleware(SecurityObservabilityMiddleware)
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
