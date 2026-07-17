"""The single mutable runtime state for TrinaxAI's backend.

Keeping process state in one explicit object avoids stale snapshots when the
engine is rebuilt and lets tests replace the whole state deterministically.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any


def _watcher_state() -> dict[str, Any]:
    return {
        "observer": None,
        "handler": None,
        "paths": [],
        "started_at": None,
        "events_seen": 0,
        "job_status": "idle",
        "pending_events": 0,
        "active_root": None,
        "last_started_at": None,
        "last_finished_at": None,
        "last_duration_seconds": None,
        "last_exit_code": None,
        "last_error": None,
        "last_stdout": "",
        "last_stderr": "",
        "runs_completed": 0,
        "runs_failed": 0,
        "runs_timed_out": 0,
        "runs_cancelled": 0,
        "lock": threading.Lock(),
    }


@dataclass
class EngineState:
    """All mutable backend singletons, caches and synchronization primitives."""

    fusion_retriever: Any = None
    index_docstore: Any = None
    vector_index: Any = None
    reranker: Any = None
    known_projects: list[str] = field(default_factory=list)

    llm_cache: dict[tuple, Any] = field(default_factory=dict)
    llm_cache_lock: threading.Lock = field(default_factory=threading.Lock)
    collection_retrievers: OrderedDict[tuple[str, ...], Any] = field(default_factory=OrderedDict)
    collection_retrievers_lock: threading.Lock = field(default_factory=threading.Lock)
    retrieval_cache: dict[tuple, tuple[float, list]] = field(default_factory=dict)
    retrieval_cache_lock: threading.Lock = field(default_factory=threading.Lock)
    sources_cache: dict[tuple, tuple[float, Any]] = field(default_factory=dict)
    sources_cache_lock: threading.Lock = field(default_factory=threading.Lock)

    index_jobs: dict[str, dict] = field(default_factory=dict)
    index_jobs_lock: threading.Lock = field(default_factory=threading.Lock)
    app_state_lock: threading.Lock = field(default_factory=threading.Lock)
    collections_lock: threading.Lock = field(default_factory=threading.Lock)
    memory_lock: threading.Lock = field(default_factory=threading.Lock)
    attachment_lock: threading.Lock = field(default_factory=threading.Lock)
    engine_lock: threading.RLock = field(default_factory=threading.RLock)
    usage_lock: threading.Lock = field(default_factory=threading.Lock)

    watcher: dict[str, Any] = field(default_factory=_watcher_state)
    health_ollama_ok: bool = False
    health_ollama_checked_at: float = 0.0

    # Rate limiting shares this state too; app.security.rate_limit owns policy.
    # key -> (available tokens, last monotonic refill timestamp)
    rate_limit_clients: dict[str, tuple[float, float]] = field(default_factory=dict)
    rate_limit_last_prune: float = 0.0
    rate_limit_lock: threading.Lock = field(default_factory=threading.Lock)


state = EngineState()


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
            oldest = sorted(cache.items(), key=lambda item: item[1][0])[: max_entries // 4]
            for stale_key, _ in oldest:
                cache.pop(stale_key, None)
        cache[key] = (time.time(), value)


def clear_index_runtime_caches() -> None:
    with state.collection_retrievers_lock:
        state.collection_retrievers.clear()
    with state.retrieval_cache_lock:
        state.retrieval_cache.clear()
    with state.sources_cache_lock:
        state.sources_cache.clear()


def lru_get(cache: OrderedDict, key: Any) -> Any | None:
    """Return and promote a cached value. Caller must hold the cache lock."""
    value = cache.get(key)
    if value is not None:
        cache.move_to_end(key)
    return value


def lru_set(cache: OrderedDict, key: Any, value: Any, *, max_entries: int) -> None:
    """Insert a value and evict least-recently-used entries deterministically."""
    if max_entries < 1:
        raise ValueError("max_entries must be positive")
    cache[key] = value
    cache.move_to_end(key)
    while len(cache) > max_entries:
        cache.popitem(last=False)
