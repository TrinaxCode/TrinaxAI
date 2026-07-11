"""User memory storage: CRUD, summarization, persistence.

Extracted from rag_api.py — in-memory fact storage backed by
a JSON file on disk, plus LLM-powered summarization.
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from typing import Any

import config
from app.services.rag_service import get_llm

USER_MEMORY_PATH = os.path.join(config.PERSIST_DIR, "user_memory.json")
SUMMARY_PATH = os.path.join(config.PERSIST_DIR, "user_memory_summary.json")

_memory_lock = threading.Lock()


def _atomic_write_json(path: str, payload: object) -> None:
    """Write JSON atomically via a unique temp file + os.replace."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = f"{path}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def memory_load() -> dict:
    try:
        with open(USER_MEMORY_PATH, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"memories": []}
        mems = data.get("memories")
        if not isinstance(mems, list):
            return {"memories": []}
        return {"memories": mems}
    except (OSError, ValueError):
        return {"memories": []}


def memory_save(data: dict) -> None:
    _atomic_write_json(USER_MEMORY_PATH, data)


def memory_create(text: str, tags: list[str] | None = None) -> dict:
    mem = {
        "id": uuid.uuid4().hex,
        "text": text,
        "created_at": time.time(),
        "tags": [str(t).strip() for t in (tags or []) if str(t).strip()],
    }
    with _memory_lock:
        data = memory_load()
        data.setdefault("memories", []).append(mem)
        memory_save(data)
    return mem


def memory_delete(memory_id: str) -> bool:
    with _memory_lock:
        data = memory_load()
        before = len(data.get("memories", []))
        data["memories"] = [
            m for m in data.get("memories", []) if m.get("id") != memory_id
        ]
        deleted = len(data["memories"]) < before
        if deleted:
            memory_save(data)
    return deleted


def memory_refresh() -> dict[str, Any]:
    """Summarise all stored memories into a context-injectable note."""
    with _memory_lock:
        data = memory_load()
    mems = data.get("memories", [])
    if not mems:
        summary = {"summary": "", "count": 0, "updated_at": time.time()}
        _atomic_write_json(SUMMARY_PATH, summary)
        return {"status": "refreshed", "summary": "", "count": 0}

    bullets = "\n".join(f"- {m.get('text', '')}" for m in mems[:200])
    prompt = (
        "Summarise these notes about the user's project and preferences in 3-5 "
        "concise sentences for context injection. Preserve concrete names, file "
        "paths, preferences and decisions. Do not invent details.\n\n"
        f"Notes:\n{bullets}\n\nSummary:"
    )
    try:
        llm = get_llm(config.LLM_MODEL)
        resp = llm.complete(prompt)
        text = (resp.text if hasattr(resp, "text") else str(resp)).strip()
    except Exception as exc:
        text = f"(LLM unavailable: {exc}) " + " | ".join(
            m.get("text", "") for m in mems[:5]
        )
    summary = {"summary": text, "count": len(mems), "updated_at": time.time()}
    _atomic_write_json(SUMMARY_PATH, summary)
    return {"status": "refreshed", "summary": text, "count": len(mems)}


def memory_read_summary() -> dict:
    if not os.path.isfile(SUMMARY_PATH):
        return {"summary": "", "count": 0, "updated_at": 0.0}
    try:
        with open(SUMMARY_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return {
            "summary": str(data.get("summary") or ""),
            "count": int(data.get("count") or 0),
            "updated_at": float(data.get("updated_at") or 0.0),
        }
    except Exception:
        return {"summary": "", "count": 0, "updated_at": 0.0}
