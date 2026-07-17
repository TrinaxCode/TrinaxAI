from __future__ import annotations

import asyncio
import json
from contextlib import contextmanager
from pathlib import Path

import config
from app.services import shared_runtime, sources_service
from app.services.engine_state import state


def test_build_engine_uses_process_lock_and_allows_owned_lock(monkeypatch) -> None:
    events: list[str] = []

    @contextmanager
    def fake_process_lock():
        events.append("lock-enter")
        try:
            yield
        finally:
            events.append("lock-exit")

    def fake_load() -> bool:
        events.append("load")
        return True

    monkeypatch.setattr(shared_runtime, "_index_process_lock", fake_process_lock)
    monkeypatch.setattr(shared_runtime, "_build_engine_from_disk", fake_load)

    assert shared_runtime.build_engine() is True
    assert events == ["lock-enter", "load", "lock-exit"]

    events.clear()
    with fake_process_lock():
        assert shared_runtime.build_engine(acquire_process_lock=False) is True
    assert events == ["lock-enter", "load", "lock-exit"]


def test_engine_refuses_to_load_when_crash_recovery_cannot_complete(monkeypatch) -> None:
    disk_load_attempted = False

    class FakeStorageContext:
        @classmethod
        def from_defaults(cls, **_kwargs):
            nonlocal disk_load_attempted
            disk_load_attempted = True
            return object()

    def broken_recovery(*_args, **_kwargs):
        raise RuntimeError("rollback backup is missing")

    monkeypatch.setattr(shared_runtime, "StorageContext", FakeStorageContext)
    monkeypatch.setattr(shared_runtime, "recover_interrupted_transaction", broken_recovery)

    assert shared_runtime._build_engine_from_disk() is False
    assert disk_load_attempted is False


class _Node:
    def __init__(self, node_id: str, source_id: str, text: str) -> None:
        self.node_id = node_id
        self.metadata = {
            "collection_id": "default",
            "collection_name": "General",
            "rel_path": "shared.md",
            "source_id": source_id,
            "source_key": f"default:{source_id}:shared.md",
        }
        self._text = text

    def get_content(self) -> str:
        return self._text


class _Docstore:
    def __init__(self, docs: dict[str, _Node]) -> None:
        self.docs = docs


def test_sources_list_and_chunks_are_partitioned_by_source_id(monkeypatch) -> None:
    docs = {
        "alpha": _Node("alpha", "alpha-root", "alpha content"),
        "beta": _Node("beta", "beta-root", "beta content"),
    }
    monkeypatch.setattr(state, "index_docstore", _Docstore(docs))
    monkeypatch.setattr(state, "fusion_retriever", object())
    monkeypatch.setattr(state, "sources_cache", {})
    monkeypatch.setattr(sources_service, "_authorize_system", lambda _request: None)

    listed = sources_service.sources_list("default", request=object())
    assert [(row["file"], row["source_id"]) for row in listed["sources"]] == [
        ("shared.md", "alpha-root"),
        ("shared.md", "beta-root"),
    ]

    chunks = sources_service.sources_chunks(
        "default",
        "shared.md",
        source_id="beta-root",
        request=object(),
    )
    assert chunks["source_id"] == "beta-root"
    assert chunks["total"] == 1
    assert chunks["chunks"][0]["id"] == "beta"
    assert chunks["chunks"][0]["metadata"]["source_id"] == "beta-root"


def test_targeted_source_delete_preserves_peer_nodes_and_manifest(tmp_path, monkeypatch) -> None:
    storage = tmp_path / "storage"
    storage.mkdir()
    manifest_path = storage / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "default:shared.md": {
                    "manifest_schema": 2,
                    "sources": {
                        "alpha-root": {"source_id": "alpha-root", "content_hash": "a"},
                        "beta-root": {"source_id": "beta-root", "content_hash": "b"},
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    docs = {
        "alpha": _Node("alpha", "alpha-root", "alpha content"),
        "beta": _Node("beta", "beta-root", "beta content"),
    }

    class FakePersistedStorage:
        def persist(self, persist_dir: str) -> None:
            Path(persist_dir).mkdir(parents=True, exist_ok=True)

    class FakeIndex:
        def __init__(self) -> None:
            self.docstore = _Docstore(docs)
            self.storage_context = FakePersistedStorage()
            self.deleted: list[str] = []

        def delete_nodes(self, node_ids: list[str], delete_from_docstore: bool = True) -> None:
            self.deleted.extend(node_ids)

    class FakeStorageContext:
        @classmethod
        def from_defaults(cls, **_kwargs):
            return object()

    fake_index = FakeIndex()
    monkeypatch.setattr(config, "PERSIST_DIR", str(storage))
    monkeypatch.setattr(config, "MANIFEST_PATH", str(manifest_path))
    monkeypatch.setattr(shared_runtime, "StorageContext", FakeStorageContext)
    monkeypatch.setattr(shared_runtime, "load_index_from_storage", lambda _storage: fake_index)

    deleted = shared_runtime._delete_indexed_rel_paths_unlocked(
        "default",
        {"shared.md"},
        source_id="alpha-root",
    )

    assert deleted == 1
    assert fake_index.deleted == ["alpha"]
    stored = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert set(stored["default:shared.md"]["sources"]) == {"beta-root"}


def test_sources_delete_forwards_source_id_and_returns_it(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_delete(collection: str, rel_paths: set[str], *, source_id: str | None = None) -> int:
        captured.update(collection=collection, rel_paths=rel_paths, source_id=source_id)
        return 3

    monkeypatch.setattr(sources_service, "_authorize_system", lambda _request: None)
    monkeypatch.setattr(sources_service, "_delete_indexed_rel_paths", fake_delete)
    monkeypatch.setattr(sources_service, "build_engine", lambda: True)
    monkeypatch.setattr(state, "sources_cache", {})
    monkeypatch.setattr(state, "retrieval_cache", {})

    result = asyncio.run(
        sources_service.sources_delete(
            "default",
            "shared.md",
            object(),
            source_id="alpha-root",
        )
    )

    assert captured == {
        "collection": "default",
        "rel_paths": {"shared.md"},
        "source_id": "alpha-root",
    }
    assert result == {
        "deleted": 3,
        "collection": "default",
        "file": "shared.md",
        "source_id": "alpha-root",
    }


def test_legacy_delete_without_source_id_keeps_all_sources_behavior(tmp_path, monkeypatch) -> None:
    storage = tmp_path / "storage"
    storage.mkdir()
    manifest_path = storage / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "default:shared.md": {
                    "manifest_schema": 2,
                    "sources": {
                        "alpha-root": {"source_id": "alpha-root"},
                        "beta-root": {"source_id": "beta-root"},
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    docs = {
        "alpha": _Node("alpha", "alpha-root", "alpha content"),
        "beta": _Node("beta", "beta-root", "beta content"),
    }

    class FakeStorage:
        def persist(self, persist_dir: str) -> None:
            Path(persist_dir).mkdir(parents=True, exist_ok=True)

    class FakeIndex:
        docstore = _Docstore(docs)
        storage_context = FakeStorage()

        def __init__(self) -> None:
            self.deleted: list[str] = []

        def delete_nodes(self, node_ids: list[str], delete_from_docstore: bool = True) -> None:
            self.deleted.extend(node_ids)

    class FakeStorageContext:
        @classmethod
        def from_defaults(cls, **_kwargs):
            return object()

    fake_index = FakeIndex()
    monkeypatch.setattr(config, "PERSIST_DIR", str(storage))
    monkeypatch.setattr(config, "MANIFEST_PATH", str(manifest_path))
    monkeypatch.setattr(shared_runtime, "StorageContext", FakeStorageContext)
    monkeypatch.setattr(shared_runtime, "load_index_from_storage", lambda _storage: fake_index)

    deleted = shared_runtime._delete_indexed_rel_paths_unlocked("default", {"shared.md"})

    assert deleted == 2
    assert set(fake_index.deleted) == {"alpha", "beta"}
    assert json.loads(manifest_path.read_text(encoding="utf-8")) == {}
