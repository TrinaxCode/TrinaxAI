from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import index


def test_manifest_storage_round_trip_preserves_colliding_sources(tmp_path: Path, monkeypatch) -> None:
    context_a = index.SourceContext.create(str(tmp_path / "a"), source_id="source-a", collection_id="docs")
    context_b = index.SourceContext.create(str(tmp_path / "b"), source_id="source-b", collection_id="docs")
    state = {
        context_a.source_key_for_relative("guide.md"): {
            "content_hash": "a",
            "source_id": context_a.source_id,
            "rel_path": "guide.md",
        },
        context_b.source_key_for_relative("guide.md"): {
            "content_hash": "b",
            "source_id": context_b.source_id,
            "rel_path": "guide.md",
        },
        "other:legacy.md": 1,
    }
    stored = index._manifest_for_storage(state)
    assert set(stored["docs:guide.md"]["sources"]) == {"source-a", "source-b"}
    assert index._expand_stored_manifest(stored) == state

    manifest = tmp_path / "manifest.json"
    persist = tmp_path / "storage"
    monkeypatch.setattr(index.config, "MANIFEST_PATH", str(manifest))
    monkeypatch.setattr(index.config, "PERSIST_DIR", str(persist))
    index.write_manifest(state)
    assert index.read_manifest() == state
    manifest.write_text("[]", encoding="utf-8")
    assert index.read_manifest() == {}
    manifest.write_text("{broken", encoding="utf-8")
    assert index.read_manifest() == {}


def test_manifest_migration_adopts_only_active_legacy_entries(tmp_path: Path) -> None:
    context = index.SourceContext.create(str(tmp_path), source_id="source", collection_id="default")
    modern = {"source_id": "existing", "rel_path": "modern.md"}
    migrated = index._migrate_manifest_for_context(
        {
            "plain.md": 1,
            "default:legacy.md": {"size": 2},
            "default:existing:modern.md": modern,
            "other:foreign.md": 3,
        },
        context,
    )
    legacy = migrated[context.source_key_for_relative("legacy.md")]
    assert legacy["source_id"] == context.source_id
    assert legacy["legacy_fingerprint"] if "legacy_fingerprint" in legacy else legacy["size"] == 2
    assert migrated["default:existing:modern.md"] is modern
    assert migrated["other:foreign.md"] == 3


def test_current_state_hashes_content_and_ignores_unreadable_files(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "root"
    root.mkdir()
    readable = root / "note.txt"
    readable.write_text("first", encoding="utf-8")
    missing = root / "missing.txt"
    context = index.SourceContext.create(str(root), source_id="source", collection_id="docs")

    first = index.current_state([str(readable), str(missing)], context)
    readable.write_text("second", encoding="utf-8")
    second = index.current_state([str(readable)], context)
    key = context.source_key(str(readable))
    assert first[key]["content_hash"] != second[key]["content_hash"]
    assert first[key]["source_root"] == str(root.resolve())
    assert len(first) == 1

    monkeypatch.setattr(index, "_content_hash", lambda _path: (_ for _ in ()).throw(OSError()))
    assert index.current_state([str(readable)], context) == {}


def test_diff_and_merge_are_scoped_to_one_source(tmp_path: Path, monkeypatch) -> None:
    context = index.SourceContext.create(str(tmp_path), source_id="source", collection_id="docs")
    active = context.source_key_for_relative("active.md")
    removed = context.source_key_for_relative("removed.md")
    foreign = "docs:other:removed.md"
    old = {
        active: {"hash": "old", "source_id": context.source_id},
        removed: {"hash": "old", "source_id": context.source_id},
        foreign: {"hash": "other", "source_id": "other"},
    }
    new = {active: {"hash": "new", "source_id": context.source_id}}
    new_files, changed, deleted = index.diff_manifest(old, new, {active: "/active.md"}, context)
    assert new_files == []
    assert changed == ["/active.md"]
    assert deleted == [removed]

    merged = index._merge_final_state(old, new, incremental=False, context=context)
    assert merged[foreign]["source_id"] == "other"
    assert removed not in merged
    monkeypatch.setattr(index, "APPEND_ONLY", True)
    assert index.diff_manifest(old, new, {active: "/active.md"}, context)[2] == []
    assert removed in index._merge_final_state(old, new, incremental=True, context=context)


def test_apply_file_updates_removes_only_successful_changes(monkeypatch) -> None:
    first = "/docs/first.md"
    second = "/docs/second.md"
    deleted = "default:deleted.md"
    batches = iter(
        [
            index.PreparedBatch(nodes=["one"], indexed_paths={first}),
            index.PreparedBatch(failures={second: "parse failed"}),
        ]
    )
    removed = []
    inserted = []
    monkeypatch.setattr(index, "iter_batches", lambda _paths: [[first], [second]])
    monkeypatch.setattr(index, "prepare_batch", lambda *_args, **_kwargs: next(batches))
    monkeypatch.setattr(
        index,
        "remove_obsolete_nodes",
        lambda _index, changed, deleted_keys: (
            removed.append((changed, deleted_keys)) or len(changed) + len(deleted_keys)
        ),
    )
    monkeypatch.setattr(index, "insert_node_batches", lambda _index, nodes: inserted.extend(nodes))
    result = index.apply_file_updates(
        SimpleNamespace(),
        [first, second],
        changed={first, second},
        deleted=[deleted],
    )
    assert removed == [([], [deleted]), ([first], [])]
    assert result.total_nodes == 1 and result.removed_nodes == 2
    assert result.failures == {second: "parse failed"}
    assert inserted == ["one"]


def test_node_source_keys_adopt_legacy_metadata(tmp_path: Path) -> None:
    context = index.SourceContext.create(str(tmp_path), source_id="source", collection_id="docs")
    legacy = SimpleNamespace(metadata={"collection_id": "docs", "rel_path": "guide.md"})
    modern = SimpleNamespace(
        metadata={
            "collection_id": "docs",
            "source_id": "other",
            "rel_path": "guide.md",
        }
    )
    explicit = SimpleNamespace(metadata={"source_key": "docs:key", "rel_path": "ignored"})
    empty = SimpleNamespace(metadata={})
    assert index._node_source_key(legacy, context) == context.source_key_for_relative("guide.md")
    assert index._node_source_key(modern) == "docs:other:guide.md"
    assert index._node_source_key(explicit) == "docs:key"
    assert index._node_source_key(empty) is None


def test_prepare_batch_records_chunking_failures(monkeypatch) -> None:
    document = SimpleNamespace(metadata={"source_key": "default:good.md"})
    monkeypatch.setattr(
        index,
        "load_docs_with_status",
        lambda *_args: index.LoadResult(documents=[document], loaded_paths=["/good.md"]),
    )
    monkeypatch.setattr(index, "build_nodes", lambda _docs: (_ for _ in ()).throw(RuntimeError("bad chunk")))
    monkeypatch.setattr(
        index, "_default_source_context", lambda: SimpleNamespace(source_key=lambda _path: "default:good.md")
    )
    result = index.prepare_batch(["/good.md"])
    assert result.failures == {"/good.md": "bad chunk"}
    assert result.nodes == []
