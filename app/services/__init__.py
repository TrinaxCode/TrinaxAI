"""Backend services and their canonical shared state."""

from .engine_state import (
    EngineState,
    cache_get,
    cache_set,
    clear_index_runtime_caches,
    state,
)

__all__ = [
    "EngineState",
    "cache_get",
    "cache_set",
    "clear_index_runtime_caches",
    "state",
]
