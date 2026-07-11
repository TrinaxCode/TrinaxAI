"""Small pure helpers shared by backend, CLI and tests."""

from __future__ import annotations

import json
import os
import re
import shutil
import time
from collections.abc import Mapping
from contextlib import contextmanager
from pathlib import Path
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
# Public alias — single source of truth for valid hardware profiles.
VALID_PROFILES = _VALID_PROFILES


def sanitize_collection_id(value: str | None, *, fallback: str = "collection") -> str:
    slug = re.sub(r"[^a-z0-9_-]+", "-", (value or "").strip().lower()).strip("-_")
    return (slug or fallback)[:48]


def _process_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


@contextmanager
def exclusive_process_lock(
    path: str | os.PathLike[str],
    *,
    timeout: float = 3600.0,
    poll_interval: float = 0.25,
):
    """Portable inter-process lock based on atomic directory creation.

    The owner PID is recorded so locks left by a crashed indexer can be safely
    reclaimed. A directory is used instead of platform-specific flock APIs so
    the same index store behaves consistently on Linux, macOS, and Windows.
    """
    lock_dir = Path(path)
    owner_file = lock_dir / "owner.json"
    deadline = time.monotonic() + max(0.0, timeout)
    lock_dir.parent.mkdir(parents=True, exist_ok=True)

    while True:
        try:
            lock_dir.mkdir()
            owner_file.write_text(
                json.dumps({"pid": os.getpid(), "created_at": time.time()}),
                encoding="utf-8",
            )
            break
        except FileExistsError:
            stale = False
            try:
                owner = json.loads(owner_file.read_text(encoding="utf-8"))
                stale = not _process_is_alive(int(owner.get("pid", 0)))
            except (OSError, ValueError, TypeError):
                try:
                    stale = time.time() - lock_dir.stat().st_mtime > 24 * 60 * 60
                except OSError:
                    stale = False
            if stale:
                try:
                    shutil.rmtree(lock_dir)
                except OSError:
                    pass
                continue
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Timed out waiting for process lock: {lock_dir}")
            time.sleep(max(0.01, poll_interval))

    try:
        yield
    finally:
        try:
            owner = json.loads(owner_file.read_text(encoding="utf-8"))
            if int(owner.get("pid", -1)) == os.getpid():
                shutil.rmtree(lock_dir)
        except (OSError, ValueError, TypeError):
            pass


def _positive_int(value: Any, fallback: int, *, minimum: int = 1, maximum: int | None = None) -> int:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return fallback
    parsed = max(minimum, parsed)
    if maximum is not None:
        parsed = min(maximum, parsed)
    return parsed


def _positive_float(
    value: Any, fallback: float, *, minimum: float = 0.0, maximum: float | None = None
) -> float:
    try:
        parsed = float(str(value).strip())
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
