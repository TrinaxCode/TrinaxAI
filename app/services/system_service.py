"""System operations: shutdown, startup, reload, reset, watcher, health.

Extracted from rag_api.py — process management, file watcher control,
factory reset, health checks, and document extraction.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from io import BytesIO
from typing import Any

from fastapi import HTTPException

import config
from app.services.collection_service import _default_collection, write_collections
from app.services.engine_state import clear_index_runtime_caches, state

LOG = logging.getLogger("trinaxai.system_service")

APP_STATE_PATH = os.path.join(config.PERSIST_DIR, "app_state.json")
APP_STATE_MAX_BYTES = int(
    os.getenv("TRINAXAI_APP_STATE_MAX_BYTES", str(6 * 1024 * 1024))
)

_SAFE_SEGMENT = re.compile(r"[^A-Za-z0-9._ -]+")

DOC_EXTRACT_MAX_BYTES = int(
    os.getenv("TRINAXAI_DOC_EXTRACT_MAX_BYTES", str(250 * 1024 * 1024))
)
DOC_EXTRACT_MAX_CHARS = int(os.getenv("TRINAXAI_DOC_EXTRACT_MAX_CHARS", "120000"))


# ── App state ──
def read_app_state() -> dict[str, str]:
    try:
        with open(APP_STATE_PATH, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        return {
            k: v
            for k, v in data.items()
            if isinstance(k, str) and k.startswith("tc-") and isinstance(v, str)
        }
    except (OSError, ValueError):
        return {}


def write_app_state(values: dict[str, str]) -> None:
    os.makedirs(config.PERSIST_DIR, exist_ok=True)
    encoded = json.dumps(values, ensure_ascii=False)
    if len(encoded.encode("utf-8")) > APP_STATE_MAX_BYTES:
        raise HTTPException(status_code=413, detail="Shared app state is too large.")
    tmp = f"{APP_STATE_PATH}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(encoded)
    for attempt in range(3):
        try:
            os.replace(tmp, APP_STATE_PATH)
            break
        except OSError:
            if attempt < 2:
                time.sleep(0.05 + attempt * 0.05)
            else:
                raise


# ── Factory reset ──
def _clear_directory_contents(path: str) -> list[str]:
    removed: list[str] = []
    base = os.path.abspath(config.BASE_DIR)
    target = os.path.abspath(path)
    if target == base or not target.startswith(base + os.sep):
        raise HTTPException(status_code=500, detail=f"Refusing to clear unsafe path: {path}")
    if not os.path.isdir(target):
        return removed
    for name in os.listdir(target):
        item = os.path.join(target, name)
        try:
            if os.path.isdir(item) and not os.path.islink(item):
                shutil.rmtree(item)
            else:
                os.remove(item)
            removed.append(os.path.relpath(item, config.BASE_DIR))
        except OSError as exc:
            LOG.warning("Could not remove reset target %s: %s", item, exc)
    return removed


def _stop_watcher_for_reset() -> None:
    with state.watcher_state["lock"]:
        observer = state.watcher_state.get("observer")
        if observer is not None:
            try:
                observer.stop()
                observer.join(timeout=2)
            except Exception:
                pass
        state.watcher_state["observer"] = None
        state.watcher_state["handler"] = None
        state.watcher_state["paths"] = []
        state.watcher_state["started_at"] = None
        state.watcher_state["events_seen"] = 0


def _cancel_index_jobs_for_reset() -> None:
    with state.index_jobs_lock:
        for job in state.index_jobs.values():
            process = job.get("process")
            if process and process.poll() is None:
                try:
                    process.terminate()
                except Exception:
                    pass
        state.index_jobs.clear()


def factory_reset_runtime_state(reset_state: dict[str, str]) -> dict[str, Any]:
    """Reset TrinaxAI to a fresh-installed local state without deleting code/.env."""
    _stop_watcher_for_reset()
    _cancel_index_jobs_for_reset()
    with state.engine_lock:
        state.fusion_retriever = None
        state.index_docstore = None
        state.known_projects = []
        clear_index_runtime_caches()

    removed: list[str] = []
    removed.extend(_clear_directory_contents(config.LOCAL_SOURCES_DIR))
    removed.extend(_clear_directory_contents(config.PERSIST_DIR))

    os.makedirs(config.PERSIST_DIR, exist_ok=True)
    with state.collections_lock:
        write_collections([_default_collection()])
    with state.app_state_lock:
        write_app_state(reset_state)

    return {
        "removed": removed,
        "indexed": False,
        "collections": [_default_collection()],
    }


# ── Service manager spawn ──
def spawn_service_manager(script: str, action: str) -> None:
    kwargs: dict[str, Any] = {
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = (
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
        kwargs["startupinfo"] = startupinfo
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(
        [sys.executable, script, action, "--base-dir", os.path.dirname(__file__)],
        **kwargs,
    )


# ── Health ──
def ollama_available_cached() -> bool:
    now = time.time()
    if now - state.health_ollama_checked_at < 5:
        return state.health_ollama_ok
    try:
        import urllib.request as _ureq

        url = f"{config.OLLAMA_BASE_URL.rstrip('/')}/api/tags"
        with _ureq.urlopen(_ureq.Request(url), timeout=0.8) as response:
            state.health_ollama_ok = 200 <= int(response.status) < 300
    except Exception:
        state.health_ollama_ok = False
    state.health_ollama_checked_at = now
    return state.health_ollama_ok


# ── Safe path helpers ──
def _safe_rel_path(filename: str) -> str | None:
    cleaned = filename.replace("\\", "/").lstrip("/")
    parts = []
    for raw in cleaned.split("/"):
        if raw in {"", ".", ".."}:
            continue
        part = _SAFE_SEGMENT.sub("_", raw).strip()
        if part:
            parts.append(part[:120])
    if not parts:
        return None
    return os.path.join(*parts)


def _safe_label(label: str) -> str:
    label = _SAFE_SEGMENT.sub("_", label).strip(" ._")
    return (label or "import")[:80]


# ── Document extraction ──
def _decode_text_bytes(data: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _extract_pdf_text(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except Exception as exc:
        raise HTTPException(
            status_code=501, detail="PDF extraction requires pypdf."
        ) from exc
    try:
        reader = PdfReader(BytesIO(data))
        pages: list[str] = []
        for index, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            if text.strip():
                pages.append(f"[Page {index}]\n{text.strip()}")
        text_result = "\n\n".join(pages).strip()
        if config.TRINAXAI_OCR and len(text_result) < 50:
            try:
                import pytesseract
                from pdf2image import convert_from_bytes

                images = convert_from_bytes(data, dpi=200)
                ocr_pages: list[str] = []
                for i, img in enumerate(images, start=1):
                    ocr_text = pytesseract.image_to_string(img, lang="eng+spa") or ""
                    if ocr_text.strip():
                        ocr_pages.append(f"[Page {i}]\n{ocr_text.strip()}")
                ocr_result = "\n\n".join(ocr_pages).strip()
                if ocr_result and len(ocr_result) > len(text_result):
                    return ocr_result
            except Exception:
                pass
        return text_result
    except Exception as exc:
        raise HTTPException(
            status_code=422, detail=f"Could not extract PDF text: {str(exc)[:180]}"
        ) from exc


def _extract_docx_text(data: bytes) -> str:
    try:
        import docx2txt
    except Exception as exc:
        raise HTTPException(
            status_code=501, detail="DOCX extraction requires docx2txt."
        ) from exc
    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
            tmp.write(data)
            tmp_path = tmp.name
        return (docx2txt.process(tmp_path) or "").strip()
    except Exception as exc:
        raise HTTPException(
            status_code=422, detail=f"Could not extract DOCX text: {str(exc)[:180]}"
        ) from exc
    finally:
        if tmp_path:
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def extract_document_text(filename: str, data: bytes) -> str:
    ext = os.path.splitext(filename.lower())[1]
    if ext == ".pdf":
        return _extract_pdf_text(data)
    if ext == ".docx":
        return _extract_docx_text(data)
    if ext in {
        ".txt", ".md", ".mdx", ".rst", ".csv", ".json",
        ".xml", ".yml", ".yaml", ".toml", ".ini", ".log",
    }:
        return _decode_text_bytes(data).strip()
    return _decode_text_bytes(data).strip()


# ── Index job management ──
def new_index_job(label: str, target: str, collection_id: str, collection_name: str) -> dict:
    now = time.time()
    job = {
        "id": uuid.uuid4().hex,
        "label": label,
        "path": target,
        "status": "saving",
        "phase": "saving",
        "progress": 2,
        "saved": 0,
        "skipped": 0,
        "bytes": 0,
        "output": "",
        "error": "",
        "projects": [],
        "collection_id": collection_id,
        "collection_name": collection_name,
        "indexed": False,
        "created_at": now,
        "updated_at": now,
        "started_at": None,
        "finished_at": None,
        "cancel_requested": False,
        "process": None,
    }
    with state.index_jobs_lock:
        state.index_jobs[job["id"]] = job
    return job
