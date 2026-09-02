"""ASGI request correlation, timing and defensive response headers."""

from __future__ import annotations

import logging
import re
import time
import uuid

from fastapi import Request
from starlette.datastructures import MutableHeaders

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


class SecurityObservabilityMiddleware:
    """Attach request metadata without buffering streaming responses."""

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


__all__ = ["SecurityObservabilityMiddleware"]
