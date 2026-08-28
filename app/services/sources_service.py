"""Indexed source browsing and deletion services."""

from __future__ import annotations

# ruff: noqa: F405
from .shared_runtime import (
    LOG,
    HTTPException,
    Request,
    _authorize_system,
    _cache_get,
    _cache_set,
    _clear_index_runtime_caches,
    _delete_indexed_collection,
    _delete_indexed_rel_paths,
    _manifest_without_prefix,
    _public_rel_path,
    _read_manifest_unlocked,
    _research_serialize_node,
    atomic_write_json,
    build_engine,
    config,
    run_in_threadpool,
    state,
)


def _research_iter_nodes(collection: str | None = None):
    """Yield (node_id, node) pairs from the docstore, optionally filtered by collection."""
    docstore = state.index_docstore
    if docstore is None:
        return
    docs = getattr(docstore, "docs", None)
    if not docs:
        return
    target = (collection or "").strip() or config.DEFAULT_COLLECTION_ID
    for node_id, node in docs.items():
        meta = getattr(node, "metadata", {}) or {}
        cid = meta.get("collection_id", config.DEFAULT_COLLECTION_ID)
        if collection is not None and cid != target:
            continue
        yield node_id, node


def sources_list(collection: str | None = None, request: Request = None):
    """List source files in a collection with chunk counts and a preview snippet.

    Response: ``{"collection": str, "sources": [{"file", "source_id",
    "chunks", "size", "mtime", "preview"}]}``
    """
    _authorize_system(request)
    target = (collection or "").strip() or config.DEFAULT_COLLECTION_ID
    cache_key = ("sources:list", target)
    cached = _cache_get(
        state.sources_cache,
        state.sources_cache_lock,
        cache_key,
        config.SOURCES_CACHE_SECONDS,
    )
    if cached is not None:
        return {"collection": target, "sources": cached}
    grouped: dict[tuple[str | None, str], dict] = {}
    if state.fusion_retriever is None:
        return {"collection": target, "sources": []}
    for _nid, node in _research_iter_nodes(target):
        meta = getattr(node, "metadata", {}) or {}
        rel = _public_rel_path(meta)
        source_id = str(meta.get("source_id") or "").strip() or None
        text = node.get_content() if hasattr(node, "get_content") else str(node)
        size = len(text.encode("utf-8"))
        mtime = float(meta.get("mtime") or meta.get("file_mtime") or 0.0)
        bucket = grouped.setdefault(
            (source_id, rel),
            {
                "file": rel,
                "source_id": source_id,
                "chunks": 0,
                "size": 0,
                "mtime": mtime,
                "preview": "",
            },
        )
        bucket["chunks"] += 1
        bucket["size"] += size
        if mtime > bucket["mtime"]:
            bucket["mtime"] = mtime
        if not bucket["preview"]:
            bucket["preview"] = text[:200].strip()
    sources = sorted(
        grouped.values(),
        key=lambda b: (-b["chunks"], b["file"], b["source_id"] or ""),
    )
    _cache_set(state.sources_cache, state.sources_cache_lock, cache_key, sources, max_entries=64)
    return {"collection": target, "sources": sources}


def sources_chunks(
    collection: str,
    file: str,
    limit: int = 50,
    offset: int = 0,
    q: str | None = None,
    source_id: str | None = None,
    request: Request = None,
):
    """List individual chunks for a given file within a collection.

    Optional ``q`` filters by case-insensitive substring match across chunk text.
    When ``q`` is provided, ``total`` reflects the filtered count and the
    ``limit``/``offset`` paginate over the matches instead of all chunks.

    Response: ``{"collection": str, "file": str, "total": int,
    "chunks": [{"id", "text", "metadata", "score"}], "query": str}``
    """
    _authorize_system(request)
    limit = max(1, min(500, int(limit)))
    offset = max(0, int(offset))
    rel_path = file  # FastAPI already URL-decodes {file:path}.
    target_source_id = (source_id or "").strip() or None
    cache_key = ("sources:chunks", collection, rel_path, target_source_id)
    cached = _cache_get(
        state.sources_cache,
        state.sources_cache_lock,
        cache_key,
        config.SOURCES_CACHE_SECONDS,
    )
    chunks: list[dict]
    if cached is not None:
        chunks = list(cached)
    else:
        chunks = []
        if state.fusion_retriever is not None:
            for _nid, node in _research_iter_nodes(collection):
                meta = getattr(node, "metadata", {}) or {}
                rel = _public_rel_path(meta)
                if rel != rel_path:
                    continue
                if target_source_id is not None and str(meta.get("source_id") or "") != target_source_id:
                    continue
                chunks.append(_research_serialize_node(node))
        _cache_set(state.sources_cache, state.sources_cache_lock, cache_key, chunks, max_entries=128)
    query = (q or "").strip()
    if query:
        needle = query.lower()
        chunks = [c for c in chunks if needle in (c.get("text") or "").lower()]
    total = len(chunks)
    page = chunks[offset : offset + limit]
    return {
        "collection": collection,
        "file": rel_path,
        "source_id": target_source_id,
        "total": total,
        "chunks": page,
        "query": query,
    }


async def sources_delete(
    collection: str,
    file: str,
    request: Request,
    source_id: str | None = None,
):
    """Delete all indexed chunks belonging to a single file inside a collection.

    Removes nodes from the docstore and index, persists the change, and
    clears the in-memory sources cache so the UI reflects the removal
    immediately.  Returns the number of deleted chunks.
    """
    _authorize_system(request)
    rel_path = file  # FastAPI URL-decodes {file:path} automatically.
    target_source_id = (source_id or "").strip() or None
    try:
        deleted = await run_in_threadpool(
            _delete_indexed_rel_paths,
            collection,
            {rel_path},
            source_id=target_source_id,
        )
    except Exception as exc:
        LOG.exception("Failed to delete source %s in %s", rel_path, collection)
        raise HTTPException(status_code=500, detail="Failed to delete source.") from exc
    # The publisher has committed the index and manifest before caches move.
    _clear_index_runtime_caches()
    await run_in_threadpool(build_engine)
    return {
        "deleted": deleted,
        "collection": collection,
        "file": rel_path,
        "source_id": target_source_id,
    }


async def sources_delete_collection(collection: str, request: Request):
    """Delete ALL indexed chunks in a collection (keeps the collection metadata).

    This is a bulk operation that removes every node belonging to the
    collection without deleting the collection itself.  Use
    ``DELETE /collections/{id}`` if you want to remove the collection too.
    """
    _authorize_system(request)
    try:
        deleted = await run_in_threadpool(_delete_collection_sources_sync, collection)
    except Exception as exc:
        LOG.exception("Failed to bulk-delete sources in %s", collection)
        raise HTTPException(status_code=500, detail="Failed to delete sources.") from exc
    # The publisher has committed the index and manifest before caches move.
    _clear_index_runtime_caches()
    await run_in_threadpool(build_engine)
    return {"deleted": deleted, "collection": collection}


def _delete_collection_sources_sync(collection: str) -> int:
    return _delete_indexed_collection(collection)


def _trim_manifest_prefix(prefix: str) -> None:
    """Compatibility helper for callers that only need manifest cleanup."""
    manifest = _read_manifest_unlocked()
    trimmed, changed = _manifest_without_prefix(manifest, prefix)
    if changed:
        atomic_write_json(config.MANIFEST_PATH, trimmed)


__all__ = [name for name in globals() if not name.startswith("__")]
