"""Health and resource inspection services."""

from __future__ import annotations

import httpx
from fastapi import Request

from app.security import admin_auth
from app.security.device_auth import DEVICE_TOKEN_HEADER, device_for_token  # noqa: F401

# ruff: noqa: F405
from .shared_runtime import (
    Any,
    JSONResponse,
    _read_collections_unlocked,
    config,
    os,
    run_in_threadpool,
    state,
    time,
)


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


def _health_authority(request: Request | None) -> tuple[bool, set[str], bool]:
    if request is None:
        return True, set(), True
    local = admin_auth._is_local_client(admin_auth._client_host(request))
    admin = admin_auth._valid_admin_token(request)
    token = admin_auth._device_token(request)
    device = device_for_token(token) if token else None
    scopes = set(device.get("scopes", [])) if device else set()
    return bool(local or admin or "read_private" in scopes), scopes, local


async def health(request: Request | None = None):
    """Estado del servicio para la PWA: índice listo, proyectos, modelos."""
    private, _, local_authority = _health_authority(request)
    payload = {
        "ok": True,
        "indexed": state.fusion_retriever is not None,
        "ollama": await run_in_threadpool(_ollama_available_cached),
        "profile": config.TRINAXAI_PROFILE,
        "features": {
            "folder_upload_indexing": True,
            "hybrid_retrieval": True,
            "sources": True,
            "collections": True,
            "local_app_state": True,
            "resources": True,
            "lan_system_actions": False,
            "profiles": ["8gb", "16gb", "32gb", "64gb"],
        },
        "capabilities": {
            # Pairing never grants host administration. This flag drives
            # controls such as pairing inventory and lifecycle actions.
            "manage_system": local_authority,
        },
    }
    if private:
        with state.collections_lock:
            payload.update(
                {
                    "projects": state.known_projects,
                    "collections": _read_collections_unlocked(),
                    "models": config.MODEL_FLEET,
                    "model_recommendations": config.MODEL_RECOMMENDATIONS,
                    "detected_profile": config.DETECTED_PROFILE,
                    "profile_source": config.PROFILE_SOURCE,
                    "hardware": config.HARDWARE,
                    "ollama_num_gpu": config.OLLAMA_NUM_GPU,
                    "num_ctx": config.NUM_CTX,
                    "embed_workers": config.EMBED_WORKERS,
                    "embed_batch_size": config.EMBED_BATCH_SIZE,
                    "embed_keep_alive": config.EMBED_KEEP_ALIVE,
                    "performance_mode": config.TRINAXAI_PERFORMANCE_MODE,
                    "fusion_candidates": config.FUSION_CANDIDATES,
                    "similarity_top_k": config.SIMILARITY_TOP_K,
                    "retrieval_cache_seconds": config.RETRIEVAL_CACHE_SECONDS,
                    "rerank": config.RERANK_ENABLED,
                }
            )
    return payload


async def ready(request: Request | None = None):
    """Readiness probe: the API is ready when its local model provider responds."""
    status = await health(request)
    status["ok"] = bool(status["ollama"])
    if not status["ok"]:
        return JSONResponse(status_code=503, content=status)
    return status


async def resources(request: Request | None = None):
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
            pages = os.sysconf("SC_PHYS_PAGES")  # type: ignore[attr-defined]
            page_size = os.sysconf("SC_PAGE_SIZE")  # type: ignore[attr-defined]
            total = int(pages * page_size)
            ram = {"total": total, "available": None, "used": None, "percent": None}
        except Exception:
            ram = None
    gpu = config.HARDWARE.get("gpu") or {}
    vram_total = gpu.get("vram_bytes")
    if gpu.get("unified_memory"):
        vram_total = int(config.HARDWARE.get("ram", {}).get("total_bytes") or 0) or None
    vram = None
    if vram_total:
        vram = {
            "total": int(vram_total),
            "available": None,
            "used": None,
            "percent": None,
            "vendor": gpu.get("vendor"),
            "name": gpu.get("name"),
            "unified_memory": bool(gpu.get("unified_memory")),
        }
    private, _, _ = _health_authority(request)
    payload = {
        "ok": True,
        "ram": ram if private else ({"percent": ram.get("percent")} if ram else None),
        "vram": vram if private else None,
        "profile": config.TRINAXAI_PROFILE,
    }
    if private:
        payload.update(
            {
                "hardware": config.HARDWARE,
                "detected_profile": config.DETECTED_PROFILE,
                "profile_source": config.PROFILE_SOURCE,
                "models": config.MODEL_FLEET,
                "model_recommendations": config.MODEL_RECOMMENDATIONS,
                "ollama_num_gpu": config.OLLAMA_NUM_GPU,
            }
        )
    return payload


__all__ = [name for name in globals() if not name.startswith("__")]
