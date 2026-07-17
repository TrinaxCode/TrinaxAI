from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

import config
import index
import trinaxai_index_storage as index_storage
from trinaxai_index_storage import (
    TRANSACTION_JOURNAL_NAME,
    publish_index_generation,
    recover_interrupted_transaction,
)


class _FakeStorage:
    def __init__(self, files: dict[str, str]) -> None:
        self.files = files

    def persist(self, persist_dir: str) -> None:
        root = Path(persist_dir)
        for relative, value in self.files.items():
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(value, encoding="utf-8")


class _FakeIndex:
    def __init__(self, files: dict[str, str]) -> None:
        self.storage_context = _FakeStorage(files)


def test_content_hash_detects_change_with_same_size_and_mtime(tmp_path) -> None:
    root = tmp_path / "source"
    root.mkdir()
    source = root / "same.txt"
    source.write_text("aaaa", encoding="utf-8")
    original = source.stat()
    context = index.SourceContext.create(str(root), source_id="source-a")
    first = index.current_state([str(source)], context)

    source.write_text("bbbb", encoding="utf-8")
    os.utime(source, ns=(original.st_atime_ns, original.st_mtime_ns))
    second = index.current_state([str(source)], context)

    key = context.source_key(str(source))
    assert first[key]["size"] == second[key]["size"]
    assert first[key]["mtime_ns"] == second[key]["mtime_ns"]
    assert first[key]["content_hash"] != second[key]["content_hash"]


def test_pipeline_change_invalidates_fingerprint(tmp_path, monkeypatch) -> None:
    root = tmp_path / "source"
    root.mkdir()
    source = root / "doc.txt"
    source.write_text("stable", encoding="utf-8")
    context = index.SourceContext.create(str(root), source_id="source-a")
    first = index.current_state([str(source)], context)

    monkeypatch.setattr(config, "CHUNK_SIZE", config.CHUNK_SIZE + 1)
    second = index.current_state([str(source)], context)

    key = context.source_key(str(source))
    assert first[key]["content_hash"] == second[key]["content_hash"]
    assert first[key]["pipeline_version"] != second[key]["pipeline_version"]


def test_document_metadata_comes_from_explicit_source_context(tmp_path) -> None:
    root = tmp_path / "explicit-project"
    nested = root / "docs"
    nested.mkdir(parents=True)
    source = nested / "guide.txt"
    source.write_text("Explicit source metadata", encoding="utf-8")
    context = index.SourceContext.create(
        str(root),
        source_id="handbook",
        collection_id="knowledge",
        collection_name="Knowledge Base",
    )

    document = index.load_docs([str(source)], context)[0]

    assert document.metadata["project"] == "explicit-project"
    assert document.metadata["rel_path"] == "docs/guide.txt"
    assert document.metadata["source_id"] == "handbook"
    assert document.metadata["source_key"] == "knowledge:handbook:docs/guide.txt"
    assert document.metadata["collection_name"] == "Knowledge Base"
    assert document.id_ == "knowledge:handbook:docs/guide.txt"


def test_multiple_roots_in_one_collection_do_not_delete_each_other(tmp_path) -> None:
    root_a = tmp_path / "alpha"
    root_b = tmp_path / "beta"
    root_a.mkdir()
    root_b.mkdir()
    path_a = root_a / "README.md"
    path_b = root_b / "README.md"
    path_a.write_text("alpha", encoding="utf-8")
    path_b.write_text("beta", encoding="utf-8")
    context_a = index.SourceContext.create(str(root_a), source_id="alpha")
    context_b = index.SourceContext.create(str(root_b), source_id="beta")
    state_a = index.current_state([str(path_a)], context_a)
    state_b = index.current_state([str(path_b)], context_b)
    old_state = {**state_a, **state_b}

    new_files, changed, deleted = index.diff_manifest(old_state, {}, {}, context_a)
    merged = index._merge_final_state(old_state, {}, incremental=True, context=context_a)

    assert new_files == []
    assert changed == []
    assert deleted == [context_a.source_key(str(path_a))]
    assert context_b.source_key(str(path_b)) in merged
    assert context_a.source_key(str(path_a)) not in merged


def test_sync_and_delete_target_only_the_selected_source_root(tmp_path) -> None:
    root_a = tmp_path / "alpha"
    root_b = tmp_path / "beta"
    root_a.mkdir()
    root_b.mkdir()
    path_a = root_a / "shared.md"
    path_b = root_b / "shared.md"
    path_a.write_text("alpha", encoding="utf-8")
    path_b.write_text("beta", encoding="utf-8")
    context_a = index.SourceContext.create(str(root_a), source_id="alpha")
    context_b = index.SourceContext.create(str(root_b), source_id="beta")

    class Node:
        def __init__(self, context: index.SourceContext, relative: str) -> None:
            self.metadata = {
                "source_key": context.source_key_for_relative(relative),
                "source_id": context.source_id,
                "collection_id": context.collection_id,
                "rel_path": relative,
            }

    class Docstore:
        docs = {
            "alpha-node": Node(context_a, "shared.md"),
            "beta-node": Node(context_b, "shared.md"),
        }

    class FakeIndex:
        docstore = Docstore()

        def __init__(self) -> None:
            self.deleted: list[str] = []

        def delete_nodes(self, node_ids: list[str], delete_from_docstore: bool = True) -> None:
            self.deleted.extend(node_ids)

    fake = FakeIndex()
    assert index.remove_obsolete_nodes(fake, [str(path_a)], [], context_a) == 1
    assert fake.deleted == ["alpha-node"]

    fake.deleted.clear()
    assert index.remove_obsolete_nodes(fake, [], [context_b.source_key(str(path_b))], context_b) == 1
    assert fake.deleted == ["beta-node"]


def test_legacy_manifest_is_adopted_by_active_source(tmp_path, monkeypatch) -> None:
    storage = tmp_path / "storage"
    storage.mkdir()
    manifest = storage / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "default:notes/readme.md": {"mtime_ns": 1, "size": 10},
                "other:foreign.md": {"mtime_ns": 2, "size": 20},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(config, "PERSIST_DIR", str(storage))
    monkeypatch.setattr(config, "MANIFEST_PATH", str(manifest))
    context = index.SourceContext.create(str(tmp_path / "source"), source_id="legacy-source")

    migrated = index.read_manifest(context)

    modern_key = context.source_key_for_relative("notes/readme.md")
    assert modern_key in migrated
    assert migrated[modern_key]["source_id"] == "legacy-source"
    assert "default:notes/readme.md" not in migrated
    assert migrated["other:foreign.md"] == {"mtime_ns": 2, "size": 20}


def test_manifest_roundtrip_nests_colliding_roots_under_legacy_delete_key(tmp_path, monkeypatch) -> None:
    storage = tmp_path / "storage"
    storage.mkdir()
    manifest = storage / "manifest.json"
    monkeypatch.setattr(config, "PERSIST_DIR", str(storage))
    monkeypatch.setattr(config, "MANIFEST_PATH", str(manifest))
    context_a = index.SourceContext.create(str(tmp_path / "alpha"), source_id="alpha")
    context_b = index.SourceContext.create(str(tmp_path / "beta"), source_id="beta")
    key_a = context_a.source_key_for_relative("shared.md")
    key_b = context_b.source_key_for_relative("shared.md")
    state = {
        key_a: {"source_id": "alpha", "rel_path": "shared.md", "content_hash": "a"},
        key_b: {"source_id": "beta", "rel_path": "shared.md", "content_hash": "b"},
    }

    index.write_manifest(state)

    stored = json.loads(manifest.read_text(encoding="utf-8"))
    assert set(stored) == {"default:shared.md"}
    assert set(stored["default:shared.md"]["sources"]) == {"alpha", "beta"}
    assert index.read_manifest() == state


def test_atomic_publish_rolls_back_an_ordinary_failure(tmp_path) -> None:
    storage = tmp_path / "storage"
    storage.mkdir()
    manifest = storage / "manifest.json"
    (storage / "docstore.json").write_text("old-docstore", encoding="utf-8")
    (storage / "default__vector_store.json").write_text("old-vector", encoding="utf-8")
    manifest.write_text('{"old":1}', encoding="utf-8")
    fake = _FakeIndex(
        {
            "docstore.json": "new-docstore",
            "default__vector_store.json": "new-vector",
        }
    )
    calls = 0

    def fail_on_second_file(_relative: str, _target: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated disk failure")

    with pytest.raises(OSError, match="simulated disk failure"):
        publish_index_generation(
            fake,
            {"new": 2},
            persist_dir=storage,
            manifest_path=manifest,
            before_publish=fail_on_second_file,
        )

    assert (storage / "docstore.json").read_text(encoding="utf-8") == "old-docstore"
    assert (storage / "default__vector_store.json").read_text(encoding="utf-8") == "old-vector"
    assert json.loads(manifest.read_text(encoding="utf-8")) == {"old": 1}
    assert not (storage / TRANSACTION_JOURNAL_NAME).exists()


def test_interrupted_publish_is_rolled_back_on_next_run(tmp_path) -> None:
    class SimulatedInterruption(BaseException):
        pass

    storage = tmp_path / "storage"
    storage.mkdir()
    manifest = storage / "manifest.json"
    (storage / "docstore.json").write_text("old-docstore", encoding="utf-8")
    (storage / "default__vector_store.json").write_text("old-vector", encoding="utf-8")
    manifest.write_text('{"old":1}', encoding="utf-8")
    fake = _FakeIndex(
        {
            "docstore.json": "new-docstore",
            "default__vector_store.json": "new-vector",
        }
    )

    def interrupt_after_first(relative: str, _target: Path) -> None:
        if relative == "docstore.json":
            raise SimulatedInterruption

    with pytest.raises(SimulatedInterruption):
        publish_index_generation(
            fake,
            {"new": 2},
            persist_dir=storage,
            manifest_path=manifest,
            before_publish=interrupt_after_first,
        )

    assert (storage / TRANSACTION_JOURNAL_NAME).is_file()
    assert (storage / "default__vector_store.json").read_text(encoding="utf-8") == "new-vector"
    assert recover_interrupted_transaction(storage, manifest) == "rolled_back"
    assert (storage / "docstore.json").read_text(encoding="utf-8") == "old-docstore"
    assert (storage / "default__vector_store.json").read_text(encoding="utf-8") == "old-vector"
    assert json.loads(manifest.read_text(encoding="utf-8")) == {"old": 1}
    assert not (storage / TRANSACTION_JOURNAL_NAME).exists()


def test_atomic_publish_commits_manifest_last(tmp_path) -> None:
    storage = tmp_path / "storage"
    manifest = storage / "manifest.json"
    fake = _FakeIndex({"docstore.json": "generation-one", "nested/vector.json": "vectors"})
    order: list[str] = []

    publish_index_generation(
        fake,
        {"source:file": {"content_hash": "abc"}},
        persist_dir=storage,
        manifest_path=manifest,
        before_publish=lambda relative, _target: order.append(relative),
    )

    assert order[-1] == "manifest.json"
    assert (storage / "docstore.json").read_text(encoding="utf-8") == "generation-one"
    assert (storage / "nested/vector.json").read_text(encoding="utf-8") == "vectors"
    assert json.loads(manifest.read_text(encoding="utf-8")) == {"source:file": {"content_hash": "abc"}}
    assert not (storage / TRANSACTION_JOURNAL_NAME).exists()


def test_recovery_keeps_generation_when_unique_commit_marker_was_written(tmp_path, monkeypatch) -> None:
    class SimulatedInterruption(BaseException):
        pass

    storage = tmp_path / "storage"
    storage.mkdir()
    manifest = storage / "manifest.json"
    (storage / "docstore.json").write_text("old", encoding="utf-8")
    manifest.write_text('{"same":1}', encoding="utf-8")
    fake = _FakeIndex({"docstore.json": "new"})
    cleanup = index_storage._cleanup_transaction

    def interrupt_cleanup(*_args, **_kwargs) -> None:
        raise SimulatedInterruption

    monkeypatch.setattr(index_storage, "_cleanup_transaction", interrupt_cleanup)
    with pytest.raises(SimulatedInterruption):
        publish_index_generation(
            fake,
            {"same": 1},
            persist_dir=storage,
            manifest_path=manifest,
        )
    assert (storage / TRANSACTION_JOURNAL_NAME).is_file()
    assert (storage / "docstore.json").read_text(encoding="utf-8") == "new"

    monkeypatch.setattr(index_storage, "_cleanup_transaction", cleanup)
    assert recover_interrupted_transaction(storage, manifest) == "committed"
    assert (storage / "docstore.json").read_text(encoding="utf-8") == "new"
    assert json.loads(manifest.read_text(encoding="utf-8")) == {"same": 1}
