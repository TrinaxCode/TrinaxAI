"""Small pure helpers shared by backend, CLI and tests."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

SAFE_DEFAULTS = {
    "profile": "16gb",
    "ollama_base_url": "http://localhost:11434",
    "default_collection_id": "default",
    "num_ctx": 4096,
    "embed_workers": 2,
    "allow_lan_system": False,
}

_VALID_PROFILES = {
    "4gb",
    "4g",
    "8gb",
    "8g",
    "16gb",
    "max",
    "high",
    "ultra",
    "gpu",
    "64gb",
    "64g",
    "4090",
    "rtx",
    "workstation",
    "max_quality",
    "quality",
    "potente",
    "32gb",
    "32g",
    "alto",
    "low",
    "min",
    "minimo",
    "lite",
    "light",
    "bajo",
}


def sanitize_collection_id(value: str | None, *, fallback: str = "collection") -> str:
    slug = re.sub(r"[^a-z0-9_-]+", "-", (value or "").strip().lower()).strip("-_")
    return (slug or fallback)[:48]


def _positive_int(value: Any, fallback: int, *, minimum: int = 1, maximum: int | None = None) -> int:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return fallback
    parsed = max(minimum, parsed)
    if maximum is not None:
        parsed = min(maximum, parsed)
    return parsed


def validate_runtime_config(env: Mapping[str, str]) -> dict[str, Any]:
    profile = str(env.get("TRINAXAI_PROFILE", SAFE_DEFAULTS["profile"])).strip().lower()
    if profile not in _VALID_PROFILES:
        profile = str(SAFE_DEFAULTS["profile"])

    base_url = str(env.get("OLLAMA_BASE_URL", SAFE_DEFAULTS["ollama_base_url"])).strip()
    if not base_url.startswith(("http://", "https://")):
        base_url = str(SAFE_DEFAULTS["ollama_base_url"])

    allow_lan = str(env.get("TRINAXAI_ALLOW_LAN_SYSTEM", "0")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    return {
        "profile": profile,
        "ollama_base_url": base_url.rstrip("/"),
        "default_collection_id": sanitize_collection_id(
            str(env.get("TRINAXAI_DEFAULT_COLLECTION_ID", SAFE_DEFAULTS["default_collection_id"])),
            fallback=str(SAFE_DEFAULTS["default_collection_id"]),
        ),
        "num_ctx": _positive_int(env.get("TRINAXAI_NUM_CTX"), int(SAFE_DEFAULTS["num_ctx"]), minimum=512),
        "embed_workers": _positive_int(
            env.get("TRINAXAI_EMBED_WORKERS"),
            int(SAFE_DEFAULTS["embed_workers"]),
            minimum=1,
            maximum=16,
        ),
        "allow_lan_system": allow_lan,
    }
