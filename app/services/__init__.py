"""Shared global state for the TrinaxAI RAG engine.

This module holds the singleton retriever, caches, locks, and collection state
that was previously global in rag_api.py.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Any

# ── Core engine state ──
_fusion_retriever: Any = None
_index_docstore: Any = None
KNOWN_PROJECTS: list[str] = []

# ── LLM cache ──
_llm_cache: dict[str, Any] = {}

# ── Retrieval cache ──
_retrieval_cache: dict[tuple, tuple[float, list]] = {}
_retrieval_cache_lock = threading.Lock()

# ── Sources cache ──
_sources_cache: dict[tuple, tuple[float, Any]] = {}
_sources_cache_lock = threading.Lock()

# ── Rate limiting ──
_rate_limit_state: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT_MAX = 30
_RATE_LIMIT_WINDOW = 60.0
_RATE_LIMIT_MAX_CLIENTS = 2000
_rate_limit_last_prune = 0.0
_rate_limit_lock = threading.Lock()

# ── Index jobs ──
_index_jobs: dict[str, dict] = {}
_index_jobs_lock = threading.Lock()

# ── App state ──
_app_state_lock = threading.Lock()
_collections_lock = threading.Lock()
_engine_lock = threading.RLock()
USAGE_LOCK = threading.Lock()

# ── Watcher state ──
_watcher_state: dict[str, Any] = {
    "observer": None,
    "handler": None,
    "paths": [],
    "started_at": None,
    "events_seen": 0,
    "lock": threading.Lock(),
}

# ── Health cache ──
_health_ollama_ok = False
_health_ollama_checked_at = 0.0


# ── Cache helpers ──
def cache_get(
    cache: dict[tuple, tuple[float, Any]],
    lock: threading.Lock,
    key: tuple,
    ttl: int,
) -> Any | None:
    if ttl <= 0:
        return None
    now = time.time()
    with lock:
        cached = cache.get(key)
        if cached and now - cached[0] <= ttl:
            return cached[1]
        if cached:
            cache.pop(key, None)
    return None


def cache_set(
    cache: dict[tuple, tuple[float, Any]],
    lock: threading.Lock,
    key: tuple,
    value: Any,
    *,
    max_entries: int = 256,
) -> None:
    with lock:
        if len(cache) > max_entries:
            oldest = sorted(cache.items(), key=lambda item: item[1][0])[
                : max_entries // 4
            ]
            for stale_key, _ in oldest:
                cache.pop(stale_key, None)
        cache[key] = (time.time(), value)


def clear_index_runtime_caches() -> None:
    with _retrieval_cache_lock:
        _retrieval_cache.clear()
    with _sources_cache_lock:
        _sources_cache.clear()
