"""Collection management: CRUD, persistence, node deletion.

Extracted from rag_api.py — collection JSON file operations
and the logic to delete nodes belonging to a specific collection.
"""

from __future__ import annotations

import json
import os
import shutil
import time

from fastapi import HTTPException
from llama_index.core import StorageContext, load_index_from_storage

import config
from app.services.engine_state import state
from app.services.rag_service import build_engine
from trinaxai_core import sanitize_collection_id


def _collection_slug(name: str) -> str:
    return sanitize_collection_id(name)


def _collection_public(item: dict) -> dict:
    now = time.time()
    return {
        "id": str(item.get("id") or config.DEFAULT_COLLECTION_ID),
        "name": str(item.get("name") or config.DEFAULT_COLLECTION_NAME),
        "created_at": float(item.get("created_at") or now),
        "updated_at": float(item.get("updated_at") or item.get("created_at") or now),
    }


def _default_collection() -> dict:
    now = time.time()
    return {
        "id": config.DEFAULT_COLLECTION_ID,
        "name": config.DEFAULT_COLLECTION_NAME,
        "created_at": now,
        "updated_at": now,
    }


def read_collections() -> list[dict]:
    """Read all collections from disk, ensuring the default exists."""
    try:
        with open(config.COLLECTIONS_PATH, encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError):
        raw = {}
    items = raw.get("collections") if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        items = []
    collections = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        public = _collection_public(item)
        if public["id"] in seen:
            continue
        seen.add(public["id"])
        collections.append(public)
    if config.DEFAULT_COLLECTION_ID not in seen:
        collections.insert(0, _default_collection())
    return collections


def write_collections(collections: list[dict]) -> None:
    os.makedirs(config.PERSIST_DIR, exist_ok=True)
    tmp = f"{config.COLLECTIONS_PATH}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"collections": collections}, f, ensure_ascii=False, indent=2)
    os.replace(tmp, config.COLLECTIONS_PATH)


def get_collection(collection_id: str) -> dict | None:
    for item in read_collections():
        if item["id"] == collection_id:
            return item
    return None


def ensure_collection(collection_id: str | None, name: str | None = None) -> dict:
    cid = (
        collection_id or config.DEFAULT_COLLECTION_ID
    ).strip() or config.DEFAULT_COLLECTION_ID
    with state.collections_lock:
        collections = read_collections()
        for item in collections:
            if item["id"] == cid:
                return item
        now = time.time()
        created = {
            "id": cid,
            "name": (name or cid).strip()[:80] or cid,
            "created_at": now,
            "updated_at": now,
        }
        collections.append(created)
        write_collections(collections)
        return created


def delete_collection_nodes(collection_id: str) -> int:
    """Remove all nodes belonging to a collection from the vector store and manifest."""
    if collection_id == config.DEFAULT_COLLECTION_ID:
        raise HTTPException(
            status_code=400, detail="The default collection cannot be deleted."
        )
    deleted_nodes = 0
    try:
        storage_context = StorageContext.from_defaults(persist_dir=config.PERSIST_DIR)
        index = load_index_from_storage(storage_context)
        node_ids = [
            node_id
            for node_id, node in index.docstore.docs.items()
            if node.metadata.get("collection_id", config.DEFAULT_COLLECTION_ID)
            == collection_id
        ]
        if node_ids:
            index.delete_nodes(node_ids, delete_from_docstore=True)
            index.storage_context.persist(persist_dir=config.PERSIST_DIR)
            deleted_nodes = len(node_ids)
    except Exception:
        deleted_nodes = 0

    try:
        with open(config.MANIFEST_PATH, encoding="utf-8") as f:
            manifest = json.load(f)
        if isinstance(manifest, dict):
            prefix = f"{collection_id}:"
            trimmed = {
                k: v for k, v in manifest.items() if not str(k).startswith(prefix)
            }
            if len(trimmed) != len(manifest):
                tmp = f"{config.MANIFEST_PATH}.tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(trimmed, f)
                os.replace(tmp, config.MANIFEST_PATH)
    except (OSError, ValueError):
        pass
    shutil.rmtree(
        os.path.join(config.LOCAL_SOURCES_DIR, "collections", collection_id),
        ignore_errors=True,
    )
    build_engine()
    return deleted_nodes
