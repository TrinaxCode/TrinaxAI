from __future__ import annotations

import json

import rag_api


class _FakeNode:
    metadata = {"rel_path": "demo/file.py", "project": "demo"}

    def get_content(self) -> str:
        return "print('hello')"


class _FakeDocstore:
    docs = {"node-1": _FakeNode()}


def test_research_iter_nodes_reads_loaded_docstore(monkeypatch) -> None:
    monkeypatch.setattr(rag_api, "_fusion_retriever", object())
    monkeypatch.setattr(rag_api, "_index_docstore", _FakeDocstore())

    rows = list(rag_api._research_iter_nodes("default"))

    assert len(rows) == 1
    assert rows[0][0] == "node-1"
    assert rows[0][1] is _FakeDocstore.docs["node-1"]
    assert rows[0][1].metadata["rel_path"] == "demo/file.py"
    assert list(rag_api._research_iter_nodes("other")) == []


def test_factory_reset_clears_runtime_index_data(tmp_path, monkeypatch) -> None:
    base = tmp_path / "repo"
    storage = base / "storage"
    local_sources = base / "local_sources"
    storage.mkdir(parents=True)
    local_sources.mkdir(parents=True)
    (storage / "docstore.json").write_text("{}", encoding="utf-8")
    (storage / "usage.jsonl").write_text("{}", encoding="utf-8")
    (local_sources / "indexed.txt").write_text("indexed", encoding="utf-8")

    monkeypatch.setattr(rag_api.config, "BASE_DIR", str(base))
    monkeypatch.setattr(rag_api.config, "PERSIST_DIR", str(storage))
    monkeypatch.setattr(rag_api.config, "LOCAL_SOURCES_DIR", str(local_sources))
    monkeypatch.setattr(rag_api.config, "COLLECTIONS_PATH", str(storage / "collections.json"))
    monkeypatch.setattr(rag_api, "APP_STATE_PATH", str(storage / "app_state.json"))
    monkeypatch.setattr(rag_api, "_fusion_retriever", object())
    monkeypatch.setattr(rag_api, "_index_docstore", object())
    monkeypatch.setattr(rag_api, "KNOWN_PROJECTS", ["demo"])
    rag_api._retrieval_cache[("q",)] = (1.0, [])
    rag_api._sources_cache[("sources",)] = (1.0, [])

    result = rag_api._factory_reset_runtime_state({"tc-reset-at": "123"})

    assert result["indexed"] is False
    assert rag_api._fusion_retriever is None
    assert rag_api._index_docstore is None
    assert rag_api.KNOWN_PROJECTS == []
    assert rag_api._retrieval_cache == {}
    assert rag_api._sources_cache == {}
    assert not (storage / "docstore.json").exists()
    assert not (storage / "usage.jsonl").exists()
    assert not (local_sources / "indexed.txt").exists()
    assert json.loads((storage / "app_state.json").read_text(encoding="utf-8")) == {
        "tc-reset-at": "123"
    }
    collections = json.loads((storage / "collections.json").read_text(encoding="utf-8"))
    assert collections["collections"][0]["id"] == "default"
