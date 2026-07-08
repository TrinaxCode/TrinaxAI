"""Admin authentication and LAN access control for TrinaxAI system endpoints.

Extracted from rag_api.py to keep the authorization logic in one place.
"""

from __future__ import annotations

import ipaddress
import os

from fastapi import HTTPException, Request

_LOCAL_HOSTS: set[str] = {"127.0.0.1", "::1", "localhost", "::ffff:127.0.0.1"}

ADMIN_TOKEN: str = os.getenv("TRINAXAI_ADMIN_TOKEN", "")

ALLOW_LAN_SYSTEM: bool = os.getenv(
    "TRINAXAI_ALLOW_LAN_SYSTEM", "0"
).strip().lower() not in {"0", "false", "no", "off"}


def _is_lan_client(host: str) -> bool:
    """Check if a host IP is loopback, private, or link-local."""
    try:
        ip = ipaddress.ip_address(host.removeprefix("::ffff:"))
    except ValueError:
        return host in _LOCAL_HOSTS
    return ip.is_loopback or ip.is_private or ip.is_link_local


def _is_local_client(host: str) -> bool:
    """Check if a host is any loopback address."""
    try:
        ip = ipaddress.ip_address(host.removeprefix("::ffff:"))
    except ValueError:
        return host in {"localhost"}
    return ip.is_loopback


def _client_host(request: Request) -> str:
    """Extract the real client IP from the request, never from X-Forwarded-For."""
    return request.client.host if request.client else "127.0.0.1"


def authorize_system(request: Request) -> None:
    """Validate admin token or localhost/LAN access for system endpoints.

    When ADMIN_TOKEN is set:
      - Requests with the correct X-Admin-Token header are allowed.
      - Requests with a wrong token are rejected immediately.
      - Requests without a token fall through to localhost/LAN check.

    When ADMIN_TOKEN is NOT set:
      - Localhost requests are always allowed.
      - LAN access is allowed only when TRINAXAI_ALLOW_LAN_SYSTEM is enabled.
    """
    if ADMIN_TOKEN:
        token = request.headers.get("X-Admin-Token", "")
        if token == ADMIN_TOKEN:
            return
        if token:
            raise HTTPException(
                status_code=403,
                detail="Invalid admin token.",
            )
    client_ip = _client_host(request)
    if not _is_local_client(client_ip) and not (
        ALLOW_LAN_SYSTEM and _is_lan_client(client_ip)
    ):
        if ADMIN_TOKEN:
            raise HTTPException(
                status_code=403,
                detail="System operations require X-Admin-Token header when accessed remotely.",
            )
        raise HTTPException(
            status_code=403,
            detail="Operaci\u00f3n solo permitida desde localhost. Configure TRINAXAI_ADMIN_TOKEN para acceso remoto.",
        )
