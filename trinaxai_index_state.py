"""Manifest, fingerprint and mutation state for the incremental indexer."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from trinaxai_core import sanitize_collection_id
from trinaxai_index_documents import SourceContext
from trinaxai_index_storage import atomic_write_json

if TYPE_CHECKING:
    from llama_index.core import VectorStoreIndex


def _runtime():
    """Resolve the legacy ``index`` facade at call time.

    The facade is intentionally late-bound: tests and older integrations patch
    indexer helpers, and those patches must remain effective after the split.
    """
    import index

    return index


def _manifest_entry(value: object, context: SourceContext, relative: str) -> dict:
    entry = dict(value) if isinstance(value, dict) else {"legacy_fingerprint": value}
    entry.setdefault("schema_version", 1)
    entry["source_id"] = context.source_id
    entry["source_root"] = context.root
    entry["rel_path"] = relative
    return entry


def _migrate_manifest_for_context(raw: dict, context: SourceContext) -> dict:
    """Adopt pre-source manifests into the active root without losing peers."""
    runtime = _runtime()
    migrated: dict[str, object] = {}
    active_prefix = f"{context.collection_id}:"
    for raw_key, value in raw.items():
        key = str(raw_key)
        if ":" not in key and context.collection_id == runtime.config.DEFAULT_COLLECTION_ID:
            key = f"{context.collection_id}:{key}"
        if not key.startswith(active_prefix):
            migrated[key] = value
            continue
        if isinstance(value, dict) and value.get("source_id"):
            migrated[key] = value
            continue
        relative = key[len(active_prefix) :]
        migrated[context.source_key_for_relative(relative)] = _manifest_entry(value, context, relative)
    return migrated


def _expand_stored_manifest(raw: dict) -> dict:
    """Expand the backend-compatible on-disk envelope into source-flat state."""
    runtime = _runtime()
    expanded: dict[str, object] = {}
    for raw_key, value in raw.items():
        key = str(raw_key)
        if not isinstance(value, dict) or value.get("manifest_schema") != runtime.MANIFEST_SCHEMA_VERSION:
            expanded[key] = value
            continue
        sources = value.get("sources")
        if not isinstance(sources, dict) or ":" not in key:
            expanded[key] = value
            continue
        collection_id, relative = key.split(":", 1)
        legacy = value.get("legacy")
        if legacy is not None:
            expanded[key] = legacy
        for source_id, entry in sources.items():
            safe_source_id = sanitize_collection_id(str(source_id), fallback="source")
            modern_key = f"{collection_id}:{safe_source_id}:{relative}"
            if isinstance(entry, dict):
                normalized = dict(entry)
                normalized["source_id"] = safe_source_id
                normalized.setdefault("rel_path", relative)
                expanded[modern_key] = normalized
            else:
                expanded[modern_key] = entry
    return expanded


def _manifest_for_storage(state: dict) -> dict:
    """Collapse source-flat state while keeping legacy backend delete keys."""
    runtime = _runtime()
    stored: dict[str, object] = {}
    modern: dict[str, dict[str, object]] = {}
    for raw_key, value in state.items():
        key = str(raw_key)
        source_id = str(value.get("source_id") or "") if isinstance(value, dict) else ""
        if source_id and ":" in key:
            collection_id = key.split(":", 1)[0]
            modern_prefix = f"{collection_id}:{source_id}:"
            if key.startswith(modern_prefix):
                relative = key[len(modern_prefix) :]
                external_key = f"{collection_id}:{relative}"
                envelope = modern.setdefault(
                    external_key,
                    {"manifest_schema": runtime.MANIFEST_SCHEMA_VERSION, "sources": {}},
                )
                envelope["sources"][source_id] = value
                continue
        stored[key] = value
    for external_key, envelope in modern.items():
        if external_key in stored:
            envelope["legacy"] = stored.pop(external_key)
        stored[external_key] = envelope
    return stored


def read_manifest(context: SourceContext | None = None) -> dict:
    runtime = _runtime()
    try:
        with open(runtime.config.MANIFEST_PATH, encoding="utf-8") as stream:
            raw = json.load(stream)
    except (OSError, ValueError):
        return {}
    if not isinstance(raw, dict):
        return {}
    canonical = {}
    for key, value in _expand_stored_manifest(raw).items():
        if ":" not in key:
            if runtime.COLLECTION_ID == runtime.config.DEFAULT_COLLECTION_ID:
                canonical[f"{runtime.COLLECTION_ID}:{key}"] = value
            else:
                canonical[key] = value
        else:
            canonical[key] = value
    return _migrate_manifest_for_context(canonical, context) if context is not None else canonical


def write_manifest(manifest: dict) -> None:
    runtime = _runtime()
    os.makedirs(runtime.config.PERSIST_DIR, exist_ok=True)
    atomic_write_json(runtime.config.MANIFEST_PATH, _manifest_for_storage(manifest))


def _content_hash(path: str) -> str:
    runtime = _runtime()
    digest = hashlib.blake2b(digest_size=32)
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(runtime._HASH_BLOCK_BYTES), b""):
            digest.update(block)
    return digest.hexdigest()


def current_state(paths: list[str], context: SourceContext | None = None) -> dict:
    """Return content-addressed, pipeline-versioned file fingerprints."""
    runtime = _runtime()
    state = {}
    source_context = context or runtime._default_source_context()
    pipeline_version = runtime._pipeline_version()
    for path in paths:
        try:
            stat = os.stat(path)
            relative = source_context.relative_path(path) if context is not None else runtime._rel(path)
            key = source_context.source_key_for_relative(relative) if context is not None else runtime._source_key(path)
            state[key] = {
                "schema_version": runtime.MANIFEST_SCHEMA_VERSION,
                "pipeline_version": pipeline_version,
                "hash_algorithm": runtime.FINGERPRINT_ALGORITHM,
                "content_hash": runtime._content_hash(path),
                "mtime_ns": stat.st_mtime_ns,
                "size": stat.st_size,
                "source_id": source_context.source_id,
                "source_root": source_context.root,
                "rel_path": relative,
            }
        except (OSError, ValueError):
            pass
    return state


def _entry_belongs_to_source(key: str, value: object, context: SourceContext) -> bool:
    if isinstance(value, dict) and str(value.get("source_id") or "") == context.source_id:
        return key.startswith(f"{context.collection_id}:")
    return key.startswith(f"{context.collection_id}:{context.source_id}:")


def diff_manifest(
    old_state: dict,
    new_state: dict,
    rel_to_path: dict[str, str],
    context: SourceContext | None = None,
) -> tuple[list[str], list[str], list[str]]:
    runtime = _runtime()
    new_files: list[str] = []
    changed: list[str] = []
    for key, path in rel_to_path.items():
        if key not in new_state:
            continue
        if key in old_state:
            if old_state[key] != new_state[key]:
                changed.append(path)
        else:
            new_files.append(path)
    if runtime.APPEND_ONLY:
        deleted = []
    elif context is None:
        prefix = f"{runtime.COLLECTION_ID}:"
        deleted = [key for key in old_state if key.startswith(prefix) and key not in new_state]
    else:
        deleted = [
            key
            for key, value in old_state.items()
            if _entry_belongs_to_source(key, value, context) and key not in new_state
        ]
    return new_files, changed, deleted


def _relative_from_source_key(key: str, context: SourceContext | None = None) -> str:
    if context is not None:
        modern_prefix = f"{context.collection_id}:{context.source_id}:"
        if key.startswith(modern_prefix):
            return key[len(modern_prefix) :]
        collection_prefix = f"{context.collection_id}:"
        if key.startswith(collection_prefix):
            return key[len(collection_prefix) :]
    return key.split(":", 1)[1] if ":" in key else key


def remove_obsolete_nodes(
    index: VectorStoreIndex,
    changed: list[str],
    deleted: list[str],
    context: SourceContext | None = None,
) -> int:
    runtime = _runtime()
    source_keys_to_remove = (
        {context.source_key(path) for path in changed}
        if context is not None
        else {runtime._source_key(path) for path in changed}
    ) | set(deleted)
    rels_to_remove = {_relative_from_source_key(key, context) for key in source_keys_to_remove}
    node_ids = []
    for node_id, node in index.docstore.docs.items():
        metadata = node.metadata or {}
        source_key = str(metadata.get("source_key") or "")
        collection_id = str(metadata.get("collection_id") or runtime.config.DEFAULT_COLLECTION_ID)
        node_source_id = str(metadata.get("source_id") or "")
        if source_key in source_keys_to_remove:
            node_ids.append(node_id)
            continue
        active_collection = context.collection_id if context is not None else runtime.COLLECTION_ID
        same_source = context is None or node_source_id in {"", context.source_id}
        legacy_key = f"{active_collection}:{metadata.get('rel_path', '')}"
        legacy_match = not node_source_id and (not source_key or source_key == legacy_key)
        if (
            legacy_match
            and same_source
            and collection_id == active_collection
            and metadata.get("rel_path") in rels_to_remove
        ):
            node_ids.append(node_id)
    if node_ids:
        index.delete_nodes(node_ids, delete_from_docstore=True)
    return len(node_ids)


@dataclass
class IndexUpdateResult:
    total_nodes: int = 0
    removed_nodes: int = 0
    indexed_paths: set[str] = field(default_factory=set)
    failures: dict[str, str] = field(default_factory=dict)


def apply_file_updates(
    index: VectorStoreIndex,
    paths: list[str],
    *,
    changed: set[str] | None = None,
    deleted: list[str] | None = None,
    context: SourceContext | None = None,
) -> IndexUpdateResult:
    """Extract, chunk and insert files without discarding good old chunks."""
    runtime = _runtime()
    result = IndexUpdateResult()
    changed = changed or set()
    deleted = deleted or []
    if deleted:
        result.removed_nodes += (
            runtime.remove_obsolete_nodes(index, [], deleted, context)
            if context
            else runtime.remove_obsolete_nodes(index, [], deleted)
        )
    if not paths:
        return result
    print("✂️  Troceando cambios...")
    files_total = len(paths)
    files_processed = 0
    for batch_number, batch in enumerate(runtime.iter_batches(paths), start=1):
        prepared = runtime.prepare_batch(batch, batch_number=batch_number, context=context)
        result.failures.update(prepared.failures)
        files_processed += len(batch)
        successful_changes = sorted(prepared.indexed_paths & changed)
        if successful_changes:
            result.removed_nodes += (
                runtime.remove_obsolete_nodes(index, successful_changes, [], context)
                if context
                else runtime.remove_obsolete_nodes(index, successful_changes, [])
            )
        if not prepared.nodes:
            runtime.emit_progress(
                "chunking",
                files_total=files_total,
                files_processed=files_processed,
                chunks_generated=result.total_nodes,
                determinate=True,
            )
            continue
        result.total_nodes += len(prepared.nodes)
        runtime.emit_progress(
            "chunking",
            files_total=files_total,
            files_processed=files_processed,
            chunks_generated=result.total_nodes,
            determinate=True,
        )
        runtime.insert_node_batches(index, prepared.nodes)
        result.indexed_paths.update(prepared.indexed_paths)
    return result


def insert_files(index: VectorStoreIndex, paths: list[str], context: SourceContext | None = None) -> int:
    return _runtime().apply_file_updates(index, paths, context=context).total_nodes


def state_after_failures(
    old_state: dict,
    new_state: dict,
    failed_paths: set[str],
    context: SourceContext | None = None,
) -> dict:
    runtime = _runtime()
    effective = dict(new_state)
    for path in failed_paths:
        key = context.source_key(path) if context is not None else runtime._source_key(path)
        if key in old_state:
            effective[key] = old_state[key]
        else:
            effective.pop(key, None)
    return effective


def merge_final_state(
    old_state: dict,
    new_state: dict,
    *,
    incremental: bool,
    context: SourceContext | None = None,
) -> dict:
    runtime = _runtime()
    if incremental and runtime.APPEND_ONLY:
        merged_state = dict(old_state)
        merged_state.update(new_state)
        return merged_state
    if context is None:
        prefix = f"{runtime.COLLECTION_ID}:"
        merged_state = {key: value for key, value in old_state.items() if not key.startswith(prefix)}
    else:
        merged_state = {
            key: value for key, value in old_state.items() if not _entry_belongs_to_source(key, value, context)
        }
    merged_state.update(new_state)
    return merged_state
