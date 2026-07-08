"""User memory storage: CRUD, summarization, persistence.

Extracted from rag_api.py — in-memory fact storage backed by
a JSON file on disk, plus LLM-powered summarization.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any

import config
from app.services.rag_service import get_llm

USER_MEMORY_PATH = os.path.join(config.PERSIST_DIR, "user_memory.json")
SUMMARY_PATH = os.path.join(config.PERSIST_DIR, "user_memory_summary.json")


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
    os.makedirs(config.PERSIST_DIR, exist_ok=True)
    tmp = f"{USER_MEMORY_PATH}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, USER_MEMORY_PATH)


def memory_create(text: str, tags: list[str] | None = None) -> dict:
    data = memory_load()
    mem = {
        "id": uuid.uuid4().hex,
        "text": text,
        "created_at": time.time(),
        "tags": [str(t).strip() for t in (tags or []) if str(t).strip()],
    }
    data.setdefault("memories", []).append(mem)
    memory_save(data)
    return mem


def memory_delete(memory_id: str) -> bool:
    data = memory_load()
    before = len(data.get("memories", []))
    data["memories"] = [m for m in data.get("memories", []) if m.get("id") != memory_id]
    deleted = len(data["memories"]) < before
    if deleted:
        memory_save(data)
    return deleted


def memory_refresh() -> dict[str, Any]:
    """Summarise all stored memories into a context-injectable note."""
    data = memory_load()
    mems = data.get("memories", [])
    if not mems:
        summary = {"summary": "", "count": 0, "updated_at": time.time()}
        with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
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
    os.makedirs(config.PERSIST_DIR, exist_ok=True)
    with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
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
