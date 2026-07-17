"""Health and resource inspection services."""

from __future__ import annotations

import httpx

from app.security import admin_auth

# ruff: noqa: F405
from .shared_runtime import *  # noqa: F403


def _ollama_available_cached() -> bool:
    """Fast best-effort Ollama reachability for status indicators."""
    now = time.time()
    if now - state.health_ollama_checked_at < 5:
        return state.health_ollama_ok
    try:
        url = f"{config.OLLAMA_BASE_URL.rstrip('/')}/api/tags"
        # Local Ollama checks must not be routed through HTTP(S)_PROXY.
        with httpx.Client(trust_env=False, timeout=0.8, follow_redirects=False) as client:
            response = client.get(url)
        state.health_ollama_ok = 200 <= int(response.status_code) < 300
    except Exception:
        state.health_ollama_ok = False
    state.health_ollama_checked_at = now
    return state.health_ollama_ok


async def health():
    """Estado del servicio para la PWA: índice listo, proyectos, modelos."""
    with state.collections_lock:
        collections = _read_collections_unlocked()
    return {
        "ok": True,
        "indexed": state.fusion_retriever is not None,
        "projects": state.known_projects,
        "collections": collections,
        "models": config.MODEL_FLEET,
        "ollama": _ollama_available_cached(),
        "profile": config.TRINAXAI_PROFILE,
        "num_ctx": config.NUM_CTX,
        "embed_workers": config.EMBED_WORKERS,
        "embed_batch_size": config.EMBED_BATCH_SIZE,
        "embed_keep_alive": config.EMBED_KEEP_ALIVE,
        "performance_mode": config.TRINAXAI_PERFORMANCE_MODE,
        "fusion_candidates": config.FUSION_CANDIDATES,
        "similarity_top_k": config.SIMILARITY_TOP_K,
        "retrieval_cache_seconds": config.RETRIEVAL_CACHE_SECONDS,
        "rerank": config.RERANK_ENABLED,
        "features": {
            "folder_upload_indexing": True,
            "hybrid_retrieval": True,
            "sources": True,
            "collections": True,
            "local_app_state": True,
            "resources": True,
            "lan_system_actions": admin_auth.ALLOW_LAN_SYSTEM,
            "profiles": ["8gb", "16gb", "max", "ultra"],
        },
    }


async def resources():
    """Basic local resource telemetry for the PWA. Fully offline."""
    ram: dict[str, Any] | None = None
    try:
        import psutil

        vm = psutil.virtual_memory()
        ram = {
            "total": int(vm.total),
            "available": int(vm.available),
            "used": int(vm.used),
            "percent": float(vm.percent),
        }
    except Exception:
        try:
            pages = os.sysconf("SC_PHYS_PAGES")
            page_size = os.sysconf("SC_PAGE_SIZE")
            total = int(pages * page_size)
            ram = {"total": total, "available": None, "used": None, "percent": None}
        except Exception:
            ram = None
    return {"ok": True, "ram": ram, "vram": None}


__all__ = [name for name in globals() if not name.startswith("__")]
