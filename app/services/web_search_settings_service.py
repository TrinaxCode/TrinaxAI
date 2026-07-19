"""Host-local, write-only-secret settings for web search."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

import httpx
from fastapi import HTTPException, Request

import config
from app.schemas.api import WebSearchConnectionTest, WebSearchSettingsUpdate
from app.security.admin_auth import authorize_system
from app.services import web_search_service

_PATH = Path(config.PERSIST_DIR) / "web_search_settings.json"
_PROVIDERS = {"auto", "duckduckgo", "brave", "searxng"}
_ENV = {
    "preferred_provider": "TRINAXAI_WEB_SEARCH_PROVIDER",
    "brave_api_key": "TRINAXAI_BRAVE_SEARCH_API_KEY",
    "searxng_url": "TRINAXAI_SEARXNG_URL",
}
_SETTINGS_LOCK = threading.RLock()


def _read() -> dict:
    try:
        data = json.loads(_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except (OSError, ValueError, TypeError):
        return {}


def _write(data: dict) -> None:
    tmp = _PATH.with_suffix(".tmp")
    try:
        _PATH.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, separators=(",", ":"))
        os.replace(tmp, _PATH)
        os.chmod(_PATH, 0o600)
    except OSError as exc:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise HTTPException(status_code=500, detail={"code": "settings_write_failed"}) from exc


def _externally_managed(field: str) -> bool:
    return bool(os.getenv(_ENV[field], "").strip())


def _apply(data: dict | None = None) -> dict:
    with _SETTINGS_LOCK:
        data = data or _read()
        provider = os.getenv(_ENV["preferred_provider"], "").strip().lower()
        if not provider:
            provider = str(data.get("preferred_provider") or "auto").lower()
            if not bool(data.get("enabled", True)):
                provider = "disabled"
        config.WEB_SEARCH_PROVIDER = provider if provider in _PROVIDERS | {"disabled"} else "auto"
        config.WEB_SEARCH_BRAVE_API_KEY = (
            os.getenv(_ENV["brave_api_key"], "").strip() or str(data.get("brave_api_key") or "").strip()
        )
        config.WEB_SEARCH_SEARXNG_URL = (
            os.getenv(_ENV["searxng_url"], "").strip() or str(data.get("searxng_url") or "").strip()
        )
        with web_search_service._SEARCH_CACHE_LOCK:
            web_search_service._SEARCH_CACHE.clear()
        return data


def _validate_searxng_url(value: str) -> str:
    normalized = value.strip().rstrip("/")
    if not normalized:
        return ""
    try:
        web_search_service._validated_target(normalized)
    except web_search_service.PageFetchError as exc:
        raise HTTPException(status_code=422, detail={"code": "invalid_searxng_url", "message": str(exc)}) from exc
    return normalized


def _public(data: dict | None = None) -> dict:
    data = _apply(data)
    provider = web_search_service.configured_provider()
    env_provider = _externally_managed("preferred_provider")
    return {
        "enabled": config.WEB_SEARCH_PROVIDER != "disabled",
        "preferred_provider": config.WEB_SEARCH_PROVIDER,
        "active_provider": provider,
        "externally_managed": {field: _externally_managed(field) for field in _ENV},
        "providers": {
            "duckduckgo": {"available": True, "configured": True, "requires_api_key": False},
            "brave": {
                "available": True,
                "configured": bool(config.WEB_SEARCH_BRAVE_API_KEY),
                "requires_api_key": True,
            },
            "searxng": {
                "available": True,
                "configured": bool(config.WEB_SEARCH_SEARXNG_URL),
                "requires_api_key": False,
                "base_url": config.WEB_SEARCH_SEARXNG_URL or None,
            },
        },
        "source": "environment" if env_provider else "managed" if _PATH.exists() else "default",
    }


async def get_web_search_settings(request: Request):
    authorize_system(request)
    return _public()


async def update_web_search_settings(req: WebSearchSettingsUpdate, request: Request):
    authorize_system(request)
    with _SETTINGS_LOCK:
        data = _read()
        changes = req.model_fields_set
        if "enabled" in changes:
            data["enabled"] = req.enabled
        if "preferred_provider" in changes:
            data["preferred_provider"] = req.preferred_provider
        if "brave_api_key" in changes and req.brave_api_key and req.brave_api_key.strip():
            if _externally_managed("brave_api_key"):
                raise HTTPException(status_code=409, detail={"code": "externally_managed", "field": "brave_api_key"})
            data["brave_api_key"] = req.brave_api_key.strip()
        if "searxng_url" in changes:
            if _externally_managed("searxng_url"):
                raise HTTPException(status_code=409, detail={"code": "externally_managed", "field": "searxng_url"})
            data["searxng_url"] = _validate_searxng_url(req.searxng_url or "")
        _write(data)
        return _public(data)


async def delete_web_search_credential(provider: str, request: Request):
    authorize_system(request)
    if provider != "brave":
        raise HTTPException(status_code=404, detail={"code": "credential_not_found", "provider": provider})
    if _externally_managed("brave_api_key"):
        raise HTTPException(status_code=409, detail={"code": "externally_managed", "field": "brave_api_key"})
    with _SETTINGS_LOCK:
        data = _read()
        data.pop("brave_api_key", None)
        _write(data)
        return _public(data)


async def reset_web_search_settings(request: Request):
    authorize_system(request)
    with _SETTINGS_LOCK:
        try:
            _PATH.unlink()
        except FileNotFoundError:
            pass
        except OSError as exc:
            raise HTTPException(status_code=500, detail={"code": "settings_reset_failed"}) from exc
        return _public({})


async def test_web_search_connection(req: WebSearchConnectionTest, request: Request):
    authorize_system(request)
    _apply()
    provider = req.provider or web_search_service.configured_provider()
    if provider == "brave" and not config.WEB_SEARCH_BRAVE_API_KEY:
        raise HTTPException(status_code=424, detail={"code": "provider_not_configured", "provider": provider})
    if provider == "searxng" and not config.WEB_SEARCH_SEARXNG_URL:
        raise HTTPException(status_code=424, detail={"code": "provider_not_configured", "provider": provider})
    try:
        results, used = web_search_service.search_web(req.query, limit=1, provider=provider)
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail={"code": "provider_timeout", "provider": provider}) from exc
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        code = "rate_limited" if status == 429 else "invalid_credential" if status in {401, 403} else "provider_error"
        raise HTTPException(status_code=status, detail={"code": code, "provider": provider}) from exc
    except (web_search_service.WebSearchError, httpx.HTTPError, ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=502,
            detail={"code": "provider_unavailable", "provider": provider, "message": str(exc)[:300]},
        ) from exc
    if not results:
        raise HTTPException(status_code=502, detail={"code": "invalid_provider_response", "provider": provider})
    return {"ok": True, "provider": used, "result_count": len(results)}


_apply()
