"""TrinaxAI — bounded monotonic token-bucket rate limiter.

Rate limiting compartido para endpoints del RAG API. Se extrae de rag_api.py
para poderlo reutilizar en nuevos routers sin crear importaciones circulares.

Shared rate limiter for RAG API endpoints. Extracted from rag_api.py so new
routers can reuse it without circular imports.
"""

from __future__ import annotations

import logging
import math
import os
import time
from typing import Any

from fastapi import HTTPException, Request

from app.security.admin_auth import _client_host
from app.services.engine_state import state
from trinaxai_core import _positive_float, _positive_int

LOG = logging.getLogger("trinaxai.rate_limit")

_RATE_LIMIT_MAX = _positive_int(
    os.getenv("TRINAXAI_RATE_LIMIT_PER_MINUTE"), 30, minimum=1, maximum=1_000_000
)
_RATE_LIMIT_WINDOW = _positive_float(
    os.getenv("TRINAXAI_RATE_LIMIT_WINDOW_SECONDS"), 60.0, minimum=1.0, maximum=86400.0
)
_RATE_LIMIT_MAX_CLIENTS = 2000


def _check_rate_limit(ip: str) -> bool:
    """True if request is allowed under the rate limit."""
    with state.rate_limit_lock:
        now = time.monotonic()
        refill_per_second = _RATE_LIMIT_MAX / _RATE_LIMIT_WINDOW
        if (
            len(state.rate_limit_clients) > _RATE_LIMIT_MAX_CLIENTS
            or now - state.rate_limit_last_prune > _RATE_LIMIT_WINDOW
        ):
            stale = [
                key
                for key, (_tokens, updated_at) in state.rate_limit_clients.items()
                if now - updated_at >= _RATE_LIMIT_WINDOW
            ]
            for key in stale:
                state.rate_limit_clients.pop(key, None)
            state.rate_limit_last_prune = now

        if ip not in state.rate_limit_clients and len(state.rate_limit_clients) >= _RATE_LIMIT_MAX_CLIENTS:
            oldest_key = min(
                state.rate_limit_clients,
                key=lambda key: state.rate_limit_clients[key][1],
            )
            state.rate_limit_clients.pop(oldest_key, None)

        tokens, updated_at = state.rate_limit_clients.get(ip, (float(_RATE_LIMIT_MAX), now))
        tokens = min(float(_RATE_LIMIT_MAX), tokens + (now - updated_at) * refill_per_second)
        if tokens < 1.0:
            state.rate_limit_clients[ip] = (tokens, now)
            return False
        state.rate_limit_clients[ip] = (tokens - 1.0, now)
        return True


def enforce_rate_limit(request: Request, *, bucket: str = "chat") -> None:
    """Rate-limit by verified original peer (or the direct transport peer)."""
    key = f"{bucket}:{_client_host(request)}"
    if not _check_rate_limit(key):
        LOG.warning("Rate limit exceeded for %s", bucket)
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Slow down.",
            headers={"Retry-After": str(max(1, math.ceil(_RATE_LIMIT_WINDOW / _RATE_LIMIT_MAX)))},
        )


def get_rate_limit_state() -> dict[str, Any]:
    """Expose state for tests; do not mutate directly."""
    return dict(state.rate_limit_clients)
