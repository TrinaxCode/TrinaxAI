"""Small pure helpers shared by backend, CLI and tests."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

VALID_PROFILES = frozenset(
    {
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
)


def normalize_http_base_url(value: Any, fallback: str = "") -> str:
    """Return a normalized HTTP(S) base URL or the supplied safe fallback."""
    text = str(value or "").strip()
    try:
        parsed = urlsplit(text)
        valid = (
            parsed.scheme in {"http", "https"}
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
            and parsed.path in {"", "/"}
            and not parsed.query
            and not parsed.fragment
            and not any(char.isspace() for char in parsed.netloc)
        )
        if valid:
            parsed.port  # Validate malformed ports while parsing.
    except ValueError:
        valid = False
    return text.rstrip("/") if valid else str(fallback).rstrip("/")


def sanitize_collection_id(value: str | None, *, fallback: str = "collection") -> str:
    slug = re.sub(r"[^a-z0-9_-]+", "-", (value or "").strip().lower()).strip("-_")
    return (slug or fallback)[:48]


def source_id_for_root(root: str, *, explicit_id: str | None = None) -> str:
    """Return the stable source id shared by indexer and backend deletion."""
    canonical_root = os.path.realpath(os.path.abspath(os.path.expanduser(root)))
    identity_path = os.path.normcase(canonical_root).replace("\\", "/")
    root_digest = hashlib.sha256(identity_path.encode("utf-8", errors="surrogatepass")).hexdigest()[:12]
    basename = os.path.basename(canonical_root.rstrip(os.sep)) or "root"
    generated_id = f"{sanitize_collection_id(basename, fallback='root')[:24]}-{root_digest}"
    return sanitize_collection_id(explicit_id, fallback=generated_id) if explicit_id else generated_id


def _process_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        if sys.platform == "win32":
            try:
                os.kill(pid, 0)
            except PermissionError:
                return True
            except OSError:
                pass
        try:
            import ctypes

            process_query_limited_information = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(  # type: ignore[attr-defined]
                process_query_limited_information,
                False,
                pid,
            )
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)  # type: ignore[attr-defined]
                return True
            return False
        except (AttributeError, OSError):
            pass
    # ``os.kill(pid, 0)`` is portable and lets the OS report process state.
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True
    return False


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
                claimed = lock_dir.with_name(f".{lock_dir.name}.stale-{uuid.uuid4().hex}")
                try:
                    os.replace(lock_dir, claimed)
                except OSError:
                    continue
                try:
                    shutil.rmtree(claimed)
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


def _positive_float(value: Any, fallback: float, *, minimum: float = 0.0, maximum: float | None = None) -> float:
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError):
        return fallback
    parsed = max(minimum, parsed)
    if maximum is not None:
        parsed = min(maximum, parsed)
    return parsed
