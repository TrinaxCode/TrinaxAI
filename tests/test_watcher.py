from __future__ import annotations

import json

import rag_api


def test_watcher_reindexes_the_changed_collection(tmp_path, monkeypatch) -> None:
    local_sources = tmp_path / "local_sources"
    collection_root = local_sources / "collections" / "docs"
    collection_root.mkdir(parents=True)
    changed = collection_root / "notes.txt"
    changed.write_text("updated", encoding="utf-8")
    storage = tmp_path / "storage"
    storage.mkdir()
    (storage / "collections.json").write_text(
        json.dumps({"collections": [{"id": "docs", "name": "Documents"}]}),
        encoding="utf-8",
    )

    monkeypatch.setattr(rag_api.config, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr(rag_api.config, "LOCAL_SOURCES_DIR", str(local_sources))
    monkeypatch.setattr(rag_api.config, "PERSIST_DIR", str(storage))
    monkeypatch.setattr(rag_api.config, "COLLECTIONS_PATH", str(storage / "collections.json"))
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))

    monkeypatch.setattr(rag_api.subprocess, "run", fake_run)
    handler = rag_api._watch_Handler([str(collection_root)])
    handler._pending.add(str(changed))

    handler._fire()

    assert len(calls) == 1
    command, kwargs = calls[0]
    assert command[-1] == str(tmp_path / "index.py")
    assert kwargs["env"]["TRINAXAI_INDEX_DIR"] == str(collection_root)
    assert kwargs["env"]["TRINAXAI_COLLECTION_ID"] == "docs"
    assert kwargs["env"]["TRINAXAI_COLLECTION_NAME"] == "Documents"
    assert kwargs["env"]["TRINAXAI_INDEX_APPEND"] == "0"
