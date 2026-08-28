"""Crash-safe manifest and indexed-node mutations."""

from __future__ import annotations


def _runtime():
    from . import shared_runtime

    return shared_runtime


def _read_manifest_unlocked() -> dict:
    runtime = _runtime()
    try:
        with open(runtime.config.MANIFEST_PATH, encoding="utf-8") as stream:
            manifest = runtime.json.load(stream)
    except (OSError, ValueError):
        return {}
    return manifest if isinstance(manifest, dict) else {}


def _manifest_without_keys(
    manifest: dict,
    keys: set[str],
    *,
    source_id: str | None = None,
) -> tuple[dict, bool]:
    """Return a source-aware manifest copy and whether anything was removed."""
    if not keys:
        return dict(manifest), False
    trimmed = dict(manifest)
    changed = False
    for key in keys:
        if key not in trimmed:
            continue
        if source_id is None:
            trimmed.pop(key, None)
            changed = True
            continue
        value = trimmed.get(key)
        if not isinstance(value, dict):
            continue
        sources = value.get("sources")
        if isinstance(sources, dict) and source_id in sources:
            updated_value = dict(value)
            updated_sources = dict(sources)
            updated_sources.pop(source_id, None)
            updated_value["sources"] = updated_sources
            if updated_sources or "legacy" in updated_value:
                trimmed[key] = updated_value
            else:
                trimmed.pop(key, None)
            changed = True
        elif str(value.get("source_id") or "") == source_id:
            trimmed.pop(key, None)
            changed = True
    return trimmed, changed


def _trim_manifest_keys(keys: set[str], *, source_id: str | None = None) -> None:
    """Remove exact manifest keys, optionally for just one source root."""
    runtime = _runtime()
    manifest = runtime._read_manifest_unlocked()
    trimmed, changed = runtime._manifest_without_keys(manifest, keys, source_id=source_id)
    if changed:
        runtime.atomic_write_json(runtime.config.MANIFEST_PATH, trimmed)


def _manifest_without_prefix(manifest: dict, prefix: str) -> tuple[dict, bool]:
    trimmed = {key: value for key, value in manifest.items() if not str(key).startswith(prefix)}
    return trimmed, len(trimmed) != len(manifest)


def _delete_indexed_rel_paths_unlocked(
    collection: str,
    rel_paths: set[str],
    *,
    source_id: str | None = None,
) -> int:
    """Delete indexed nodes for a set of relative source paths in one collection."""
    runtime = _runtime()
    if not rel_paths:
        return 0
    deleted = 0
    source_keys = {f"{collection}:{rel}" for rel in rel_paths}
    if source_id is not None:
        source_keys.update(f"{collection}:{source_id}:{rel}" for rel in rel_paths)
    storage_context = runtime.storage_context_for_persist_dir(runtime.config.PERSIST_DIR)
    index = runtime.load_index_from_storage(storage_context)
    node_ids: list[str] = []
    for node_id, node in index.docstore.docs.items():
        meta = getattr(node, "metadata", {}) or {}
        collection_id = meta.get("collection_id", runtime.config.DEFAULT_COLLECTION_ID)
        if collection_id != collection:
            continue
        rel = meta.get("rel_path") or meta.get("file_path") or ""
        public_rel = runtime._public_rel_path(meta)
        source_key = meta.get("source_key") or f"{collection_id}:{rel}"
        if source_id is not None and str(meta.get("source_id") or "") != source_id:
            continue
        if rel in rel_paths or public_rel in rel_paths or source_key in source_keys:
            node_ids.append(node_id)
    manifest = runtime._read_manifest_unlocked()
    trimmed_manifest, manifest_changed = runtime._manifest_without_keys(
        manifest,
        source_keys,
        source_id=source_id,
    )
    if node_ids:
        index.delete_nodes(node_ids, delete_from_docstore=True)
        deleted = len(node_ids)
    if node_ids or manifest_changed:
        runtime.publish_index_generation(
            index,
            trimmed_manifest,
            persist_dir=runtime.config.PERSIST_DIR,
            manifest_path=runtime.config.MANIFEST_PATH,
        )
    return deleted


def _delete_indexed_rel_paths(
    collection: str,
    rel_paths: set[str],
    *,
    source_id: str | None = None,
) -> int:
    runtime = _runtime()
    with runtime._index_process_lock():
        return runtime._delete_indexed_rel_paths_unlocked(collection, rel_paths, source_id=source_id)


def _delete_indexed_collection_unlocked(collection: str) -> int:
    """Delete one collection through the existing crash-recoverable publisher."""
    runtime = _runtime()
    if not runtime.os.path.exists(runtime.os.path.join(runtime.config.PERSIST_DIR, "docstore.json")):
        return 0
    storage_context = runtime.storage_context_for_persist_dir(runtime.config.PERSIST_DIR)
    index = runtime.load_index_from_storage(storage_context)
    node_ids = [
        node_id
        for node_id, node in index.docstore.docs.items()
        if (getattr(node, "metadata", {}) or {}).get("collection_id", runtime.config.DEFAULT_COLLECTION_ID)
        == collection
    ]
    manifest = runtime._read_manifest_unlocked()
    trimmed_manifest, manifest_changed = runtime._manifest_without_prefix(manifest, f"{collection}:")
    if node_ids:
        index.delete_nodes(node_ids, delete_from_docstore=True)
    if node_ids or manifest_changed:
        runtime.publish_index_generation(
            index,
            trimmed_manifest,
            persist_dir=runtime.config.PERSIST_DIR,
            manifest_path=runtime.config.MANIFEST_PATH,
        )
    return len(node_ids)


def _delete_indexed_collection(collection: str) -> int:
    runtime = _runtime()
    with runtime._index_process_lock():
        return runtime._delete_indexed_collection_unlocked(collection)


__all__ = [name for name in globals() if not name.startswith("__")]
