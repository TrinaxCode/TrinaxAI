"""Knowledge collection services."""

from __future__ import annotations

# ruff: noqa: F405
from .shared_runtime import *  # noqa: F403


def _delete_collection_nodes_unlocked(collection_id: str) -> int:
    if collection_id == config.DEFAULT_COLLECTION_ID:
        raise HTTPException(status_code=400, detail="The default collection cannot be deleted.")
    deleted_nodes = 0
    if os.path.exists(os.path.join(config.PERSIST_DIR, "docstore.json")):
        storage_context = StorageContext.from_defaults(persist_dir=config.PERSIST_DIR)
        index = load_index_from_storage(storage_context)
        node_ids = [
            node_id
            for node_id, node in index.docstore.docs.items()
            if node.metadata.get("collection_id", config.DEFAULT_COLLECTION_ID) == collection_id
        ]
        if node_ids:
            index.delete_nodes(node_ids, delete_from_docstore=True)
            index.storage_context.persist(persist_dir=config.PERSIST_DIR)
            deleted_nodes = len(node_ids)

    try:
        with open(config.MANIFEST_PATH, encoding="utf-8") as f:
            manifest = json.load(f)
        if isinstance(manifest, dict):
            prefix = f"{collection_id}:"
            trimmed = {k: v for k, v in manifest.items() if not str(k).startswith(prefix)}
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
    return deleted_nodes


def _delete_collection_nodes(collection_id: str) -> int:
    with _index_process_lock():
        deleted_nodes = _delete_collection_nodes_unlocked(collection_id)
    build_engine()
    return deleted_nodes


async def collections_get(request: Request):
    """List all RAG collections, ensuring the default collection exists.

    Lista todas las colecciones RAG, garantizando la colección por defecto.
    """
    _authorize_system(request)
    with state.collections_lock:
        collections = _read_collections_unlocked()
        _write_collections_unlocked(collections)
    return {"ok": True, "collections": collections}


async def collections_create(req: CollectionCreateRequest, request: Request):
    """Create a RAG collection with a unique slug derived from its name.

    Crea una colección RAG con un slug único derivado de su nombre.
    """
    _authorize_system(request)
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Collection name is required.")
    with state.collections_lock:
        collections = _read_collections_unlocked()
        used = {item["id"] for item in collections}
        base = _collection_slug(name)
        cid = base
        n = 2
        while cid in used:
            cid = f"{base}-{n}"
            n += 1
        now = time.time()
        item = {"id": cid, "name": name[:80], "created_at": now, "updated_at": now}
        collections.append(item)
        _write_collections_unlocked(collections)
    return {"ok": True, "collection": item}


async def collections_update(collection_id: str, req: CollectionUpdateRequest, request: Request):
    """Rename an existing RAG collection. 404 if the id does not exist.

    Renombra una colección RAG existente. 404 si el id no existe.
    """
    _authorize_system(request)
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Collection name is required.")
    with state.collections_lock:
        collections = _read_collections_unlocked()
        for item in collections:
            if item["id"] == collection_id:
                item["name"] = name[:80]
                item["updated_at"] = time.time()
                _write_collections_unlocked(collections)
                return {"ok": True, "collection": item}
    raise HTTPException(status_code=404, detail="Collection not found.")


async def collections_delete(collection_id: str, request: Request):
    """Delete a RAG collection and all its indexed nodes. Default is protected.

    Elimina una colección RAG y todos sus nodos indexados. La colección por
    defecto está protegida y no puede borrarse.
    """
    _authorize_system(request)
    if collection_id == config.DEFAULT_COLLECTION_ID:
        raise HTTPException(status_code=400, detail="The default collection cannot be deleted.")
    with state.collections_lock:
        collections = _read_collections_unlocked()
        if not any(item["id"] == collection_id for item in collections):
            raise HTTPException(status_code=404, detail="Collection not found.")
    deleted_nodes = await run_in_threadpool(_delete_collection_nodes, collection_id)
    with state.collections_lock:
        collections = _read_collections_unlocked()
        _write_collections_unlocked([item for item in collections if item["id"] != collection_id])
    return {"ok": True, "deleted_nodes": deleted_nodes}


__all__ = [name for name in globals() if not name.startswith("__")]
