"""Imports, constants and process configuration shared by API services."""

# Imports are intentionally re-exported to the split domain service modules.
# ruff: noqa: F401

from __future__ import annotations

import json
import logging
import os
import re
import shutil
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
    "Aún no hay índice. Ejecuta `python index.py` para indexar "
    "tu carpeta de proyectos y luego recarga desde Configuración o con "
    "POST /system/reload."
)

_SAFE_SEGMENT = re.compile(r"[^A-Za-z0-9._ -]+")

APP_STATE_PATH = os.path.join(config.PERSIST_DIR, "app_state.json")

CHAT_ATTACHMENTS_DIR = os.path.join(config.PERSIST_DIR, "chat_attachments")

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

_MULTILINGUAL_500 = {
    "en": (
        "⚠️  Make sure TrinaxAI is turned on. Please verify that Ollama is "
        "active and the index is built (run `python index.py`)."
    ),
    "es": (
        "⚠️  Asegúrate de que TrinaxAI esté encendido. Verifica que Ollama "
        "esté funcionando y el índice esté construido "
        "(ejecuta `python index.py`)."
    ),
}

__all__ = [name for name in globals() if not name.startswith("__")]
