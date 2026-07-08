"""Shared mutable state for the TrinaxAI RAG engine.

This module centralizes all the global singletons, caches, and locks
that were previously scattered at module level in rag_api.py.

All state is namespaced under a single ``EngineState`` dataclass-like
namespace so tests can patch it predictably.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Any


class EngineState:
    """Namespace for all mutable global engine state."""

    # Core retriever
    fusion_retriever: Any = None
    index_docstore: Any = None
    known_projects: list[str] = []

    # LLM cache
    llm_cache: dict[str, Any] = {}

    # Retrieval caches
    retrieval_cache: dict[tuple, tuple[float, list]] = {}
    retrieval_cache_lock = threading.Lock()

    sources_cache: dict[tuple, tuple[float, Any]] = {}
    sources_cache_lock = threading.Lock()

    # Rate limiting
    rate_limit_state: dict[str, list[float]] = defaultdict(list)
    rate_limit_max: int = 30
    rate_limit_window: float = 60.0
    rate_limit_max_clients: int = 2000
    rate_limit_last_prune: float = 0.0
    rate_limit_lock = threading.Lock()

    # Index jobs
    index_jobs: dict[str, dict] = {}
    index_jobs_lock = threading.Lock()

    # Concurrency locks
    app_state_lock = threading.Lock()
    collections_lock = threading.Lock()
    engine_lock = threading.RLock()
    usage_lock = threading.Lock()

    # Watcher
    watcher_state: dict[str, Any] = {
        "observer": None,
        "handler": None,
        "paths": [],
        "started_at": None,
        "events_seen": 0,
        "lock": threading.Lock(),
    }

    # Health cache
    health_ollama_ok: bool = False
    health_ollama_checked_at: float = 0.0


# Singleton instance — import this everywhere.
state = EngineState()


# ── Cache helpers (operate on EngineState) ──
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
    with state.retrieval_cache_lock:
        state.retrieval_cache.clear()
    with state.sources_cache_lock:
        state.sources_cache.clear()
