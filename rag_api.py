"""Backward-compatible entry point for the canonical :mod:`app.main` API.

New code should import ``app`` from ``app.main`` and services from ``app``.
Legacy helper imports remain available while downstream integrations migrate.
"""

from __future__ import annotations

import os
import sys
import types

from app import api_runtime as _runtime
from app.main import app as app
from app.services.engine_state import state

_STATE_ALIASES = {
    "_fusion_retriever": "fusion_retriever",
    "_index_docstore": "index_docstore",
    "_vector_index": "vector_index",
    "KNOWN_PROJECTS": "known_projects",
    "_llm_cache": "llm_cache",
    "_llm_cache_lock": "llm_cache_lock",
    "_collection_retrievers": "collection_retrievers",
    "_collection_retrievers_lock": "collection_retrievers_lock",
    "_retrieval_cache": "retrieval_cache",
    "_retrieval_cache_lock": "retrieval_cache_lock",
    "_sources_cache": "sources_cache",
    "_sources_cache_lock": "sources_cache_lock",
    "_index_jobs": "index_jobs",
    "_index_jobs_lock": "index_jobs_lock",
    "_app_state_lock": "app_state_lock",
    "_collections_lock": "collections_lock",
    "_memory_lock": "memory_lock",
    "_engine_lock": "engine_lock",
    "_watcher_state": "watcher",
    "_health_ollama_ok": "health_ollama_ok",
    "_health_ollama_checked_at": "health_ollama_checked_at",
    "_attachment_lock": "attachment_lock",
}


class _CompatibilityModule(types.ModuleType):
    def __getattr__(self, name: str):
        state_name = _STATE_ALIASES.get(name)
        if state_name:
            return getattr(state, state_name)
        try:
            return getattr(_runtime, name)
        except AttributeError as exc:
            raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc

    def __setattr__(self, name: str, value) -> None:
        state_name = _STATE_ALIASES.get(name)
        if state_name:
            setattr(state, state_name, value)
        elif hasattr(_runtime, name):
            setattr(_runtime, name, value)
        else:
            super().__setattr__(name, value)

    def __delattr__(self, name: str) -> None:
        state_name = _STATE_ALIASES.get(name)
        if state_name:
            delattr(state, state_name)
        elif hasattr(_runtime, name):
            delattr(_runtime, name)
        else:
            super().__delattr__(name)

    def __dir__(self) -> list[str]:
        return sorted(set(super().__dir__()) | set(dir(_runtime)) | set(_STATE_ALIASES))


sys.modules[__name__].__class__ = _CompatibilityModule


if __name__ == "__main__":
    import uvicorn

    import config

    configured_host = os.getenv("TRINAXAI_HOST", "127.0.0.1")
    allow_unsafe_bind = os.getenv("TRINAXAI_UNSAFE_BIND_BACKEND", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if configured_host not in {"127.0.0.1", "::1", "localhost"} and not allow_unsafe_bind:
        configured_host = "127.0.0.1"
    uvicorn.run(
        "app.main:app",
        host=configured_host,
        port=config._env_int("TRINAXAI_PORT", 3333, minimum=1, maximum=65535),
        reload=False,
    )
