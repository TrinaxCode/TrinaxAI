"""Knowledge collection services."""

from __future__ import annotations

# ruff: noqa: F405
from .shared_runtime import (
    CollectionCreateRequest,
    CollectionUpdateRequest,
    HTTPException,
    Request,
    _authorize_system,
    _clear_index_runtime_caches,
    _collection_slug,
    _delete_indexed_collection,
    _read_collections_unlocked,
    _write_collections_unlocked,
    build_engine,
    config,
    os,
    run_in_threadpool,
    shutil,
    state,
    time,
)


def _delete_collection_nodes(collection_id: str) -> int:
    """Compatibility shim for callers of the legacy collection delete helper."""
    return _delete_indexed_collection(collection_id)


async def collections_get(request: Request):
    """List all RAG collections without mutating persistent state.

    Lista todas las colecciones RAG. Si aún no existe el archivo, el valor por
    defecto se devuelve en memoria y se persiste cuando el usuario muta la
    configuración.
    """
    _authorize_system(request)
    with state.collections_lock:
        collections = _read_collections_unlocked()
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
    _clear_index_runtime_caches()
    shutil.rmtree(
        os.path.join(config.LOCAL_SOURCES_DIR, "collections", collection_id),
        ignore_errors=True,
    )
    await run_in_threadpool(build_engine)
    return {"ok": True, "deleted_nodes": deleted_nodes}


__all__ = [name for name in globals() if not name.startswith("__")]
