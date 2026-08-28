"""Crash-recoverable publication of a LlamaIndex generation.

LlamaIndex persists its document/index state plus vector data.  Replacing those files one by one and
then writing ``manifest.json`` leaves a window where a killed indexer can expose
an index from one generation and a manifest from another.  This module stages a
complete generation, records durable rollback information, publishes the
manifest after the index files, and finally swaps a unique commit marker.

The active files intentionally remain in the historical storage directory so
existing backend/CLI consumers do not need to understand a new pointer format.
Document/index state remains LlamaIndex-compatible JSON while embeddings use an
embedded SQLite snapshot (``vectors.sqlite3``).  Legacy vector JSON is read once
and migrated when the store is opened.
If the process is killed before the unique marker swap, the next indexing run
restores the previous generation from the journal.  Once the marker is durable,
the new generation is kept and only transaction debris is removed.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import sqlite3
import struct
import tempfile
import uuid
from pathlib import Path
from typing import Any, Callable, Sequence

from llama_index.core.bridge.pydantic import PrivateAttr
from llama_index.core.schema import BaseNode
from llama_index.core.vector_stores.simple import SimpleVectorStore
from llama_index.core.vector_stores.types import (
    BasePydanticVectorStore,
    MetadataFilters,
    VectorStoreQuery,
    VectorStoreQueryMode,
    VectorStoreQueryResult,
)
from llama_index.core.vector_stores.utils import build_metadata_filter_fn, node_to_metadata_dict

TRANSACTION_SCHEMA_VERSION = 1
TRANSACTION_JOURNAL_NAME = ".index-transaction.json"
TRANSACTION_DIR_NAME = ".index-transactions"
GENERATION_MARKER_NAME = ".index-generation.json"
SQLITE_VECTOR_STORE_NAME = "vectors.sqlite3"
SQLITE_VECTOR_STORE_SCHEMA = 1


class SQLiteVectorStore(BasePydanticVectorStore):
    """Small embedded vector store with atomic SQLite snapshots.

    The in-memory mapping is intentional: indexing mutates a private snapshot
    and ``persist`` writes it only into the publisher's staging directory.
    That keeps a failed indexing run from modifying the active generation.
    """

    stores_text: bool = False
    db_path: str
    _entries: dict[str, tuple[list[float], str, dict[str, Any]]] = PrivateAttr(default_factory=dict)

    def __init__(
        self,
        db_path: str,
        *,
        entries: dict[str, tuple[list[float], str, dict[str, Any]]] | None = None,
        **data: Any,
    ) -> None:
        data.setdefault("stores_text", False)
        data.setdefault("is_embedding_query", True)
        super().__init__(db_path=db_path, **data)
        self._entries = entries if entries is not None else self._read_snapshot(Path(db_path))

    @classmethod
    def class_name(cls) -> str:
        return "SQLiteVectorStore"

    @classmethod
    def empty(cls, persist_dir: str | os.PathLike[str]) -> "SQLiteVectorStore":
        """Create a fresh staging store without loading the active snapshot."""
        return cls(str(Path(persist_dir) / SQLITE_VECTOR_STORE_NAME), entries={})

    @classmethod
    def for_persist_dir(cls, persist_dir: str | os.PathLike[str]) -> "SQLiteVectorStore":
        root = Path(persist_dir)
        path = root / SQLITE_VECTOR_STORE_NAME
        if path.is_file():
            return cls(str(path))

        store = cls(str(path), entries={})
        for legacy_name in ("default__vector_store.json", "vector_store.json"):
            legacy_path = root / legacy_name
            if not legacy_path.is_file():
                continue
            store._entries = store._read_legacy(legacy_path)
            store._write_snapshot(path)
            break
        return store

    @property
    def client(self) -> None:
        return None

    @staticmethod
    def _pack_embedding(embedding: Sequence[float]) -> tuple[bytes, int]:
        values = [float(value) for value in embedding]
        return struct.pack(f"<{len(values)}f", *values), len(values)

    @staticmethod
    def _unpack_embedding(blob: bytes, dimensions: int) -> list[float]:
        if dimensions < 0 or len(blob) != dimensions * 4:
            raise RuntimeError("Invalid SQLite vector dimensions")
        return list(struct.unpack(f"<{dimensions}f", blob))

    @classmethod
    def _read_snapshot(cls, path: Path) -> dict[str, tuple[list[float], str, dict[str, Any]]]:
        if not path.is_file():
            return {}
        entries: dict[str, tuple[list[float], str, dict[str, Any]]] = {}
        try:
            with sqlite3.connect(path) as connection:
                rows = connection.execute("SELECT node_id, ref_doc_id, dimensions, embedding, metadata FROM embeddings")
                for node_id, ref_doc_id, dimensions, blob, metadata_json in rows:
                    metadata = json.loads(metadata_json)
                    if not isinstance(metadata, dict):
                        metadata = {}
                    entries[str(node_id)] = (
                        cls._unpack_embedding(bytes(blob), int(dimensions)),
                        str(ref_doc_id),
                        metadata,
                    )
        except (OSError, sqlite3.DatabaseError, TypeError, ValueError) as exc:
            raise RuntimeError(f"Unable to load SQLite vector store: {path}") from exc
        return entries

    @staticmethod
    def _read_legacy(path: Path) -> dict[str, tuple[list[float], str, dict[str, Any]]]:
        legacy = SimpleVectorStore.from_persist_path(str(path))
        metadata_dict = legacy.data.metadata_dict or {}
        return {
            str(node_id): (
                [float(value) for value in embedding],
                str(legacy.data.text_id_to_ref_doc_id.get(node_id) or "None"),
                dict(metadata_dict.get(node_id) or {}),
            )
            for node_id, embedding in legacy.data.embedding_dict.items()
        }

    def _write_snapshot(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        connection: sqlite3.Connection | None = None
        try:
            connection = sqlite3.connect(temporary)
            connection.execute(f"PRAGMA user_version = {SQLITE_VECTOR_STORE_SCHEMA}")
            connection.execute(
                """
                CREATE TABLE embeddings (
                    node_id TEXT PRIMARY KEY,
                    ref_doc_id TEXT NOT NULL,
                    dimensions INTEGER NOT NULL,
                    embedding BLOB NOT NULL,
                    metadata TEXT NOT NULL
                )
                """
            )
            connection.executemany(
                "INSERT INTO embeddings(node_id, ref_doc_id, dimensions, embedding, metadata) VALUES (?, ?, ?, ?, ?)",
                (
                    (
                        node_id,
                        ref_doc_id,
                        dimensions,
                        blob,
                        json.dumps(metadata, ensure_ascii=False, sort_keys=True, default=str),
                    )
                    for node_id, (embedding, ref_doc_id, metadata) in self._entries.items()
                    for blob, dimensions in (self._pack_embedding(embedding),)
                ),
            )
            connection.commit()
            connection.close()
            connection = None
            _fsync_file(temporary)
            os.replace(temporary, path)
            _fsync_directory(path.parent)
        finally:
            if connection is not None:
                connection.close()
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass

    def add(self, nodes: Sequence[BaseNode], **_: Any) -> list[str]:
        for node in nodes:
            metadata = node_to_metadata_dict(node, remove_text=True, flat_metadata=False)
            metadata.pop("_node_content", None)
            embedding, _ = self._pack_embedding(node.get_embedding())
            self._entries[node.node_id] = (
                self._unpack_embedding(embedding, len(embedding) // 4),
                node.ref_doc_id or "None",
                metadata,
            )
        return [node.node_id for node in nodes]

    def delete(self, ref_doc_id: str, **_: Any) -> None:
        self._entries = {node_id: entry for node_id, entry in self._entries.items() if entry[1] != ref_doc_id}

    def delete_nodes(
        self,
        node_ids: list[str] | None = None,
        filters: MetadataFilters | None = None,
        **_: Any,
    ) -> None:
        filter_fn = build_metadata_filter_fn(lambda node_id: self._entries[node_id][2], filters)
        allowed = set(node_ids) if node_ids is not None else None
        self._entries = {
            node_id: entry
            for node_id, entry in self._entries.items()
            if (allowed is not None and node_id not in allowed) or not filter_fn(node_id)
        }

    def clear(self) -> None:
        self._entries.clear()

    @staticmethod
    def _similarity(left: Sequence[float], right: Sequence[float]) -> float:
        if len(left) != len(right):
            raise ValueError("Embedding dimensions do not match")
        left_norm = math.sqrt(sum(value * value for value in left))
        right_norm = math.sqrt(sum(value * value for value in right))
        if not left_norm or not right_norm:
            return 0.0
        return sum(a * b for a, b in zip(left, right, strict=True)) / (left_norm * right_norm)

    def query(self, query: VectorStoreQuery, **kwargs: Any) -> VectorStoreQueryResult:
        if query.query_embedding is None:
            raise ValueError("SQLiteVectorStore requires a query embedding")
        filter_fn = build_metadata_filter_fn(lambda node_id: self._entries[node_id][2], query.filters)
        requested = set(query.node_ids) if query.node_ids is not None else None
        documents = set(query.doc_ids) if query.doc_ids is not None else None
        # ponytail: brute-force O(n) scan; move to sqlite-vec only when corpus size makes it measurable.
        candidates = [
            (node_id, entry[0])
            for node_id, entry in self._entries.items()
            if (requested is None or node_id in requested)
            and (documents is None or entry[1] in documents)
            and filter_fn(node_id)
            and len(entry[0]) == len(query.query_embedding)
        ]
        ids = [node_id for node_id, _ in candidates]
        embeddings = [embedding for _, embedding in candidates]
        if query.mode == VectorStoreQueryMode.DEFAULT:
            scored = sorted(
                ((self._similarity(query.query_embedding, embedding), node_id) for node_id, embedding in candidates),
                reverse=True,
            )[: query.similarity_top_k]
            return VectorStoreQueryResult(
                similarities=[score for score, _ in scored],
                ids=[node_id for _, node_id in scored],
            )
        if query.mode == VectorStoreQueryMode.MMR:
            from llama_index.core.indices.query.embedding_utils import get_top_k_mmr_embeddings

            similarities, top_ids = get_top_k_mmr_embeddings(
                query.query_embedding,
                embeddings,
                similarity_fn=self._similarity,
                similarity_top_k=query.similarity_top_k,
                embedding_ids=ids,
                mmr_threshold=query.mmr_threshold if query.mmr_threshold is not None else kwargs.get("mmr_threshold"),
            )
            return VectorStoreQueryResult(similarities=list(similarities), ids=list(top_ids))
        raise ValueError(f"Invalid query mode: {query.mode}")

    def persist(self, persist_path: str = "./storage/vector_store.json", fs: Any = None) -> None:
        if fs is not None:
            raise ValueError("SQLiteVectorStore only supports local filesystems")
        target = Path(persist_path)
        if target.suffix != ".sqlite3":
            target = target.parent / SQLITE_VECTOR_STORE_NAME
        self._write_snapshot(target)


def new_storage_context(persist_dir: str | os.PathLike[str]) -> Any:
    """Return an empty LlamaIndex context backed by a fresh vector snapshot."""
    from llama_index.core import StorageContext

    return StorageContext.from_defaults(vector_store=SQLiteVectorStore.empty(persist_dir))


def storage_context_for_persist_dir(persist_dir: str | os.PathLike[str]) -> Any:
    """Load a persisted index with its SQLite vector snapshot."""
    from llama_index.core import StorageContext

    return StorageContext.from_defaults(
        persist_dir=persist_dir,
        vector_store=SQLiteVectorStore.for_persist_dir(persist_dir),
    )


def _fsync_file(path: Path) -> None:
    try:
        with path.open("rb") as stream:
            os.fsync(stream.fileno())
    except OSError:
        # Some filesystems/platforms do not expose fsync for every file type.
        pass


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def atomic_write_json(path: str | os.PathLike[str], value: Any) -> None:
    """Write JSON with deterministic bytes and an atomic final rename."""
    _atomic_write(Path(path), _json_bytes(value))


def _copy_for_replace(source: Path, target: Path, transaction_id: str) -> None:
    """Copy *source* beside *target* and atomically replace the target."""
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{transaction_id}.tmp")
    try:
        shutil.copy2(source, temporary)
        _fsync_file(temporary)
        os.replace(temporary, target)
        _fsync_directory(target.parent)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _safe_relative_files(root: Path) -> list[str]:
    files: list[str] = []
    for candidate in root.rglob("*"):
        if candidate.is_symlink():
            raise RuntimeError(f"Refusing symlink in staged index: {candidate}")
        if candidate.is_file():
            files.append(candidate.relative_to(root).as_posix())
    return sorted(files)


def _load_journal(journal_path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(journal_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"Index transaction journal is unreadable: {journal_path}") from exc
    if not isinstance(value, dict) or value.get("schema_version") != TRANSACTION_SCHEMA_VERSION:
        raise RuntimeError(f"Unsupported index transaction journal: {journal_path}")
    return value


def _cleanup_transaction(persist_dir: Path, journal_path: Path, transaction_id: str) -> None:
    # The active generation is already known-good.  Remove the journal first:
    # a crash after this point can only leave harmless staging debris.  Removing
    # backups first would make an interrupted rollback impossible to repeat.
    try:
        journal_path.unlink()
    except FileNotFoundError:
        pass
    _fsync_directory(persist_dir)
    shutil.rmtree(persist_dir / TRANSACTION_DIR_NAME / transaction_id, ignore_errors=True)
    transactions = persist_dir / TRANSACTION_DIR_NAME
    try:
        transactions.rmdir()
    except OSError:
        pass
    _fsync_directory(persist_dir)


def recover_interrupted_transaction(
    persist_dir: str | os.PathLike[str],
    manifest_path: str | os.PathLike[str],
) -> str | None:
    """Finish or roll back a transaction left by a killed indexer.

    Returns ``"committed"`` when the unique generation marker proves the new
    generation was fully published, ``"rolled_back"`` when the previous
    generation was restored, and ``None`` when no journal exists.
    """
    persist = Path(persist_dir)
    manifest = Path(manifest_path)
    journal_path = persist / TRANSACTION_JOURNAL_NAME
    journal = _load_journal(journal_path)
    if journal is None:
        return None

    transaction_id = str(journal.get("transaction_id") or "")
    if not transaction_id or Path(transaction_id).name != transaction_id:
        raise RuntimeError("Invalid transaction id in index journal")
    transaction_root = persist / TRANSACTION_DIR_NAME / transaction_id
    backup_root = transaction_root / "backup"
    expected_manifest_hash = str(journal.get("manifest_sha256") or "")
    generation_marker = persist / GENERATION_MARKER_NAME

    # A unique generation marker is replaced only after the manifest.  A hash
    # alone is insufficient because two valid generations can have an identical
    # manifest while their serialized index files differ.
    try:
        marker_value = json.loads(generation_marker.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        marker_value = {}
    if (
        isinstance(marker_value, dict)
        and marker_value.get("transaction_id") == transaction_id
        and marker_value.get("manifest_sha256") == expected_manifest_hash
    ):
        _cleanup_transaction(persist, journal_path, transaction_id)
        return "committed"

    targets = journal.get("targets")
    if not isinstance(targets, list):
        raise RuntimeError("Invalid target list in index transaction journal")
    for item in targets:
        if not isinstance(item, dict):
            raise RuntimeError("Invalid target entry in index transaction journal")
        relative = str(item.get("relative") or "")
        relative_path = Path(relative)
        if not relative or relative_path.is_absolute() or ".." in relative_path.parts:
            raise RuntimeError("Unsafe target path in index transaction journal")
        target = persist / relative_path
        backup = backup_root / relative_path
        if bool(item.get("existed")):
            if not backup.is_file():
                raise RuntimeError(f"Missing rollback file for index target: {relative}")
            _copy_for_replace(backup, target, f"rollback-{transaction_id}")
        else:
            try:
                target.unlink()
            except FileNotFoundError:
                pass

    manifest_backup = backup_root / "__manifest__.json"
    if bool(journal.get("manifest_existed")):
        if not manifest_backup.is_file():
            raise RuntimeError("Missing rollback manifest for interrupted index transaction")
        _copy_for_replace(manifest_backup, manifest, f"rollback-{transaction_id}")
    else:
        try:
            manifest.unlink()
        except FileNotFoundError:
            pass
    marker_backup = backup_root / "__generation__.json"
    if bool(journal.get("generation_marker_existed")):
        if not marker_backup.is_file():
            raise RuntimeError("Missing rollback generation marker for interrupted transaction")
        _copy_for_replace(marker_backup, generation_marker, f"rollback-{transaction_id}")
    else:
        try:
            generation_marker.unlink()
        except FileNotFoundError:
            pass
    _fsync_directory(persist)
    _cleanup_transaction(persist, journal_path, transaction_id)
    return "rolled_back"


def publish_index_generation(
    index: Any,
    manifest_value: dict[str, Any],
    *,
    persist_dir: str | os.PathLike[str],
    manifest_path: str | os.PathLike[str],
    before_publish: Callable[[str, Path], None] | None = None,
) -> None:
    """Stage and crash-safely publish an index plus its manifest.

    ``before_publish`` is an intentionally small fault-injection seam used by
    regression tests.  Production callers leave it unset.
    """
    persist = Path(persist_dir)
    manifest = Path(manifest_path)
    persist.mkdir(parents=True, exist_ok=True)
    recover_interrupted_transaction(persist, manifest)

    transaction_id = uuid.uuid4().hex
    transaction_root = persist / TRANSACTION_DIR_NAME / transaction_id
    staged_root = transaction_root / "staged"
    backup_root = transaction_root / "backup"
    staged_manifest = transaction_root / "manifest.json"
    staged_root.mkdir(parents=True)
    backup_root.mkdir(parents=True)

    try:
        index.storage_context.persist(persist_dir=str(staged_root))
        staged_files = _safe_relative_files(staged_root)
        if not staged_files:
            raise RuntimeError("Index persistence produced no files")
        for relative in staged_files:
            _fsync_file(staged_root / relative)

        manifest_payload = _json_bytes(manifest_value)
        _atomic_write(staged_manifest, manifest_payload)
        targets: list[dict[str, Any]] = []
        for relative in staged_files:
            target = persist / relative
            existed = target.is_file()
            targets.append({"relative": relative, "existed": existed})
            if existed:
                backup = backup_root / relative
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup)
                _fsync_file(backup)

        manifest_existed = manifest.is_file()
        if manifest_existed:
            shutil.copy2(manifest, backup_root / "__manifest__.json")
            _fsync_file(backup_root / "__manifest__.json")
        generation_marker = persist / GENERATION_MARKER_NAME
        generation_marker_existed = generation_marker.is_file()
        if generation_marker_existed:
            shutil.copy2(generation_marker, backup_root / "__generation__.json")
            _fsync_file(backup_root / "__generation__.json")

        journal = {
            "schema_version": TRANSACTION_SCHEMA_VERSION,
            "transaction_id": transaction_id,
            "manifest_path": str(manifest),
            "manifest_sha256": _sha256_bytes(manifest_payload),
            "manifest_existed": manifest_existed,
            "generation_marker_existed": generation_marker_existed,
            "targets": targets,
        }
        journal_path = persist / TRANSACTION_JOURNAL_NAME
        _atomic_write(journal_path, _json_bytes(journal))
        _fsync_directory(transaction_root)

        for relative in staged_files:
            if before_publish is not None:
                before_publish(relative, persist / relative)
            _copy_for_replace(staged_root / relative, persist / relative, transaction_id)

        if before_publish is not None:
            before_publish("manifest.json", manifest)
        _copy_for_replace(staged_manifest, manifest, transaction_id)
        atomic_write_json(
            generation_marker,
            {
                "schema_version": TRANSACTION_SCHEMA_VERSION,
                "transaction_id": transaction_id,
                "manifest_sha256": _sha256_bytes(manifest_payload),
            },
        )
        _fsync_directory(persist)
        _cleanup_transaction(persist, journal_path, transaction_id)
    except Exception:
        # Ordinary failures are rolled back immediately.  Base-level process
        # interruption (KeyboardInterrupt/SystemExit), SIGKILL, or power loss
        # leaves the durable journal for the next run to recover.
        if (persist / TRANSACTION_JOURNAL_NAME).exists():
            recover_interrupted_transaction(persist, manifest)
        else:
            shutil.rmtree(transaction_root, ignore_errors=True)
        raise
