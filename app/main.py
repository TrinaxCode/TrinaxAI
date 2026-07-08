"""TrinaxAI FastAPI application entry point.

Provides a clean import path for the FastAPI app.
During incremental migration from rag_api.py, this module
re-exports the existing app for backward compatibility.

Usage:
    from app.main import app
    # or: uvicorn app.main:app
"""

from __future__ import annotations

# The canonical FastAPI app lives in rag_api.py.
# As routes migrate to app/routes/*.py, they'll be registered here.
# Re-export key symbols for backward-compatible imports by tests and CLI.
from rag_api import (  # noqa: F401, E402
    APP_STATE_PATH,
    KNOWN_PROJECTS,
    _app_state_lock,
    _collections_lock,
    _engine_lock,
    _factory_reset_runtime_state,
    _fusion_retriever,
    _index_docstore,
    _read_app_state,
    _research_iter_nodes,
    _retrieval_cache,
    _retrieval_cache_lock,
    _sources_cache,
    _sources_cache_lock,
    _write_app_state,
    app,  # noqa: F401, E402
    build_engine,
)
