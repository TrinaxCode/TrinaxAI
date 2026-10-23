"""Reject requests whose ``Host`` header names a foreign DNS domain.

A web page can make a victim's browser resolve the page's own domain to
127.0.0.1 (DNS rebinding). The browser then treats requests to the local API as
same-origin, sends no ``Origin`` header on GET, and the API sees a loopback
peer. Checking the ``Host`` header closes that gap: such a request still names
the attacker's domain.

IP literals, single-label names (``localhost``, Docker service names, the test
client's ``testserver``), ``*.localhost`` and mDNS ``*.local`` names cannot be
served by a remote attacker's DNS, so they stay allowed. Any other name must be
listed in ``TRINAXAI_ALLOWED_HOSTS``.
"""

from __future__ import annotations

import ipaddress
import os

from starlette.responses import JSONResponse

ALLOWED_HOSTS_ENV = "TRINAXAI_ALLOWED_HOSTS"


def _hostname(host_header: str) -> str:
    """Return the lower-case hostname of a ``Host`` header, without port."""
    value = host_header.strip().lower()
    if value.startswith("["):
        return value[1 : value.find("]")] if "]" in value else ""
    if value.count(":") == 1:
        value = value.split(":", 1)[0]
    return value.rstrip(".")


def _configured_hosts() -> set[str]:
    raw = os.getenv(ALLOWED_HOSTS_ENV, "")
    return {item.strip().lower().rstrip(".") for item in raw.split(",") if item.strip()}


def is_trusted_host(host_header: str | None) -> bool:
    """Return whether a request's ``Host`` header is safe from DNS rebinding."""
    if not host_header:
        # Rebinding always comes from a browser, which always sends Host.
        return True
    configured = _configured_hosts()
    if "*" in configured:
        return True
    hostname = _hostname(host_header)
    if not hostname:
        return False
    try:
        ipaddress.ip_address(hostname)
        return True
    except ValueError:
        pass
    if "." not in hostname or hostname.endswith((".localhost", ".local")):
        return True
    return hostname in configured


class TrustedHostGuardMiddleware:
    """ASGI middleware that answers 421 for an untrusted ``Host`` header."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        host = next(
            (value.decode("latin-1") for name, value in scope.get("headers") or () if name == b"host"),
            None,
        )
        if is_trusted_host(host):
            await self.app(scope, receive, send)
            return
        response = JSONResponse(
            status_code=421,
            content={
                "detail": {
                    "code": "untrusted_host",
                    "message": f"Untrusted Host header. Add the host name to {ALLOWED_HOSTS_ENV} if you use it.",
                }
            },
        )
        await response(scope, receive, send)


__all__ = ["ALLOWED_HOSTS_ENV", "TrustedHostGuardMiddleware", "is_trusted_host"]
