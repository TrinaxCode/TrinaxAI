"""Imports, constants and process configuration shared by API services."""

# Imports are intentionally re-exported to the split domain service modules.
# ruff: noqa: F401

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from io import BytesIO
from typing import Any

from fastapi import File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from llama_index.core import (
    QueryBundle,
    Settings,
    StorageContext,
    load_index_from_storage,
)
from llama_index.core.response_synthesizers import (
    ResponseMode,
    get_response_synthesizer,
)
from llama_index.core.retrievers import QueryFusionRetriever
from llama_index.core.vector_stores import FilterCondition, MetadataFilter, MetadataFilters
from llama_index.retrievers.bm25 import BM25Retriever
from starlette.concurrency import run_in_threadpool

import config
from app.generation.presets import build_task_spec
from app.generation.prompts import (
    build_generation_prompt,
    grounded_template,
    wants_creator_bio,
)
from app.generation.spec import Regime
from app.generation.validate import validate_output
from app.schemas import (
    AgentApprovalRequest,
    AgentCancelRequest,
    AgentRequest,
    AppStateRequest,
    ChatRequest,
    CollectionCreateRequest,
    CollectionUpdateRequest,
    IndexImportDeleteRequest,
    MemoryContextRequest,
    MemoryCreateRequest,
    MemoryRefreshRequest,
    MemoryUpdateRequest,
    ResearchRequest,
    UsageRecordRequest,
    WatchStartRequest,
)
from app.security.rate_limit import _client_host, enforce_rate_limit
from app.services.engine_state import (
    cache_get as _cache_get,
)
from app.services.engine_state import (
    cache_set as _cache_set,
)
from app.services.engine_state import (
    clear_index_runtime_caches as _clear_index_runtime_caches,
)
from app.services.engine_state import lru_get as _lru_get
from app.services.engine_state import lru_set as _lru_set
from app.services.engine_state import (
    state,
)
from trinaxai_core import exclusive_process_lock, sanitize_collection_id, source_id_for_root

if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
    import codecs

    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "replace")

LOG = logging.getLogger("trinaxai.rag_api")

NO_INDEX_MSG = (
    "No index yet. Run `python index.py` to index your projects folder and "
    "reload from Settings or with POST /system/reload."
)

NO_INDEX_MSG_ES = (
    "Aún no hay índice. Ejecuta `python index.py` para indexar "
    "tu carpeta de proyectos y luego recarga desde Configuración o con "
    "POST /system/reload."
)


def no_index_message(language: str | None = None) -> str:
    """Return the no-index notice in the language requested by the client."""
    return NO_INDEX_MSG_ES if str(language or "").lower().startswith("es") else NO_INDEX_MSG


def request_language(request: Any = None) -> str:
    """Return ``es``/``en`` for an incoming request, defaulting to English."""
    try:
        value = str(request.headers.get("accept-language", "")).lower()
    except Exception:  # noqa: BLE001 - a missing request must not break a turn
        return "en"
    return "es" if value.split(",", 1)[0].strip().startswith("es") else "en"


_SAFE_SEGMENT = re.compile(r"[^A-Za-z0-9._ -]+")

APP_STATE_PATH = os.path.join(config.PERSIST_DIR, "app_state.json")

CHAT_ATTACHMENTS_DIR = os.path.join(config.PERSIST_DIR, "chat_attachments")

PRIVATE_DIRECTORY_MODE = 0o700
PRIVATE_FILE_MODE = 0o600


def _ensure_private_directory(path: str) -> None:
    os.makedirs(path, mode=PRIVATE_DIRECTORY_MODE, exist_ok=True)
    try:
        os.chmod(path, PRIVATE_DIRECTORY_MODE)
    except OSError:
        # Windows and filesystems without chmod support enforce permissions
        # through their native ACLs instead.
        pass


def _ensure_private_file(path: str) -> None:
    try:
        os.chmod(path, PRIVATE_FILE_MODE)
    except OSError:
        # Windows and filesystems without chmod support enforce permissions
        # through their native ACLs instead.
        pass


def _open_private_file(path: str, flags: int) -> int:
    descriptor = os.open(path, flags | getattr(os, "O_BINARY", 0), PRIVATE_FILE_MODE)
    _ensure_private_file(path)
    return descriptor


def _try_fchmod(descriptor: int, mode: int) -> bool:
    fchmod = getattr(os, "fchmod", None)
    if fchmod is None:
        return False
    try:
        fchmod(descriptor, mode)
    except OSError:
        return False
    return True


def _harden_private_directory_fd(descriptor: int) -> None:
    """Recursively restrict a directory tree without traversing symlinks."""
    if not _try_fchmod(descriptor, PRIVATE_DIRECTORY_MODE):
        # Windows and filesystems without POSIX modes use their native ACLs.
        return
    with os.scandir(descriptor) as entries:
        for entry in entries:
            try:
                entry_stat = os.stat(entry.name, dir_fd=descriptor, follow_symlinks=False)
            except OSError:
                continue
            flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
            if stat.S_ISDIR(entry_stat.st_mode):
                flags |= getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
                try:
                    child = os.open(entry.name, flags, dir_fd=descriptor)
                except OSError:
                    continue
                try:
                    if stat.S_ISDIR(os.fstat(child).st_mode):
                        _harden_private_directory_fd(child)
                finally:
                    os.close(child)
            elif stat.S_ISREG(entry_stat.st_mode):
                flags |= getattr(os, "O_NOFOLLOW", 0)
                try:
                    child = os.open(entry.name, flags, dir_fd=descriptor)
                except OSError:
                    continue
                try:
                    if stat.S_ISREG(os.fstat(child).st_mode):
                        _try_fchmod(child, PRIVATE_FILE_MODE)
                except OSError:
                    pass
                finally:
                    os.close(child)


def harden_persist_directory(path: str) -> None:
    """Ensure persisted local data is private, without touching symlink targets."""
    root = os.path.abspath(path)
    try:
        root_stat = os.lstat(root)
    except FileNotFoundError:
        os.makedirs(root, mode=PRIVATE_DIRECTORY_MODE, exist_ok=True)
        root_stat = os.lstat(root)
    if stat.S_ISLNK(root_stat.st_mode) or not stat.S_ISDIR(root_stat.st_mode):
        raise RuntimeError(f"Persistent storage must be a real directory: {root}")
    if getattr(os, "fchmod", None) is None:
        _ensure_private_directory(root)
        return
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(root, flags)
    except OSError as exc:
        raise RuntimeError(f"Could not secure persistent storage: {root}") from exc
    try:
        if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
            raise RuntimeError(f"Persistent storage must be a directory: {root}")
        _harden_private_directory_fd(descriptor)
    finally:
        os.close(descriptor)


APP_STATE_MAX_BYTES = config._env_int("TRINAXAI_APP_STATE_MAX_BYTES", 6 * 1024 * 1024, minimum=1024)

_DELIVERABLE_KEYWORDS = (
    "tests",
    "benchmark",
    "faq",
    "chat",
    "responsive",
    "animation",
    "docstring",
    "types",
)

_MODEL_MAX_CONCURRENCY = config._env_int("TRINAXAI_MODEL_MAX_CONCURRENCY", 1, minimum=1, maximum=8)

_RETRIEVER_CACHE_MAX_COMBINATIONS = config._env_int(
    "TRINAXAI_RETRIEVER_CACHE_MAX_COMBINATIONS", 32, minimum=1, maximum=1024
)

_model_slots = threading.BoundedSemaphore(_MODEL_MAX_CONCURRENCY)

_document_slots = threading.BoundedSemaphore(
    config._env_int("TRINAXAI_DOCUMENT_MAX_CONCURRENCY", 1, minimum=1, maximum=4)
)

USER_MEMORY_PATH = os.path.join(config.PERSIST_DIR, "user_memory.json")

try:
    from watchdog.events import (
        FileSystemEventHandler as _WDFileSystemEventHandler,  # type: ignore
    )
except Exception:
    _WDFileSystemEventHandler = object

USAGE_PATH = os.path.join(config.PERSIST_DIR, "usage.jsonl")

USAGE_SUMMARY_PATH = os.path.join(config.PERSIST_DIR, "usage_summary.json")

DOC_EXTRACT_MAX_BYTES = config._env_int("TRINAXAI_DOC_EXTRACT_MAX_BYTES", 128 * 1024 * 1024, minimum=1024)

DOC_EXTRACT_MAX_CHARS = config._env_int("TRINAXAI_DOC_EXTRACT_MAX_CHARS", 120000, minimum=1000)

CHAT_ATTACHMENT_MAX_BYTES = config._env_int("TRINAXAI_CHAT_ATTACHMENT_MAX_BYTES", 512 * 1024 * 1024, minimum=1024)

CHAT_ATTACHMENTS_MAX_BYTES = config._env_int(
    "TRINAXAI_CHAT_ATTACHMENTS_MAX_BYTES", 4 * 1024 * 1024 * 1024, minimum=1024
)

CHAT_ATTACHMENTS_MAX_FILES = config._env_int("TRINAXAI_CHAT_ATTACHMENTS_MAX_FILES", 1000, minimum=1)

_SAFE_INLINE_ATTACHMENT_TYPES = {
    "application/pdf",
    "image/gif",
    "image/jpeg",
    "image/png",
    "image/webp",
    "text/plain",
}

_SAFE_ATTACHMENT_TYPES = _SAFE_INLINE_ATTACHMENT_TYPES | {
    "application/msword",
    "application/vnd.ms-excel",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.oasis.opendocument.presentation",
    "application/vnd.oasis.opendocument.spreadsheet",
    "application/vnd.oasis.opendocument.text",
    "application/rtf",
}

_MULTILINGUAL_500 = {
    "en": (
        "TrinaxAI could not complete this action. Your other features remain "
        "available; please try again, then check the service status if it continues."
    ),
    "es": (
        "TrinaxAI no pudo completar esta acción. Las demás funciones siguen "
        "disponibles; inténtalo de nuevo y revisa el estado del servicio si continúa."
    ),
}

__all__ = [name for name in globals() if not name.startswith("__")]
