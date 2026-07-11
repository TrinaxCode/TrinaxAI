"""TrinaxAI — simple token-bucket rate limiter.

Rate limiting compartido para endpoints del RAG API. Se extrae de rag_api.py
para poderlo reutilizar en nuevos routers sin crear importaciones circulares.

Shared rate limiter for RAG API endpoints. Extracted from rag_api.py so new
routers can reuse it without circular imports.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections import defaultdict
from typing import Any

from fastapi import HTTPException, Request

from trinaxai_core import _positive_float, _positive_int

LOG = logging.getLogger("trinaxai.rate_limit")

_rate_limit_state: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT_MAX = _positive_int(
    os.getenv("TRINAXAI_RATE_LIMIT_PER_MINUTE"), 30, minimum=1, maximum=1_000_000
)
_RATE_LIMIT_WINDOW = _positive_float(
    os.getenv("TRINAXAI_RATE_LIMIT_WINDOW_SECONDS"), 60.0, minimum=1.0, maximum=86400.0
)
_RATE_LIMIT_MAX_CLIENTS = 2000
_rate_limit_last_prune = 0.0
_rate_limit_lock = threading.Lock()


def _check_rate_limit(ip: str) -> bool:
    """True if request is allowed under the rate limit."""
    global _rate_limit_last_prune
    with _rate_limit_lock:
        now = time.time()
        if (
            len(_rate_limit_state) > _RATE_LIMIT_MAX_CLIENTS
            or now - _rate_limit_last_prune > _RATE_LIMIT_WINDOW
        ):
            stale = [
                key
                for key, values in _rate_limit_state.items()
                if not values
                or all(now - stamp >= _RATE_LIMIT_WINDOW for stamp in values)
            ]
            for key in stale:
                _rate_limit_state.pop(key, None)
            _rate_limit_last_prune = now
        window = [t for t in _rate_limit_state[ip] if now - t < _RATE_LIMIT_WINDOW]
        _rate_limit_state[ip] = window
        if len(window) >= _RATE_LIMIT_MAX:
            return False
        window.append(now)
        return True


def _client_host(request: Request) -> str:
    return request.client.host if request.client else "127.0.0.1"


def enforce_rate_limit(request: Request, *, bucket: str = "chat") -> None:
    """Raise HTTPException 429 if the request exceeds the rate limit."""
    key = f"{bucket}:{_client_host(request)}"
    if not _check_rate_limit(key):
        LOG.warning("Rate limit exceeded for %s", bucket)
        raise HTTPException(status_code=429, detail="Too many requests. Slow down.")


def get_rate_limit_state() -> dict[str, Any]:
    """Expose state for tests; do not mutate directly."""
    return dict(_rate_limit_state)
