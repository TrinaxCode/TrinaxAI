from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import rag_api
from app.services import rag_service, shared_runtime


def test_collection_retrieval_is_scoped_before_query(monkeypatch) -> None:
    global_retriever = MagicMock()
    scoped_retriever = MagicMock()
    scoped_retriever.retrieve.return_value = []
    monkeypatch.setattr(rag_api, "_fusion_retriever", global_retriever)
    monkeypatch.setattr(rag_api, "_retriever_for_collections", lambda collections: scoped_retriever)
    monkeypatch.setattr(rag_api.config, "RETRIEVAL_CACHE_SECONDS", 0)

    rag_api._cached_retrieve("query", "query", ["selected"], None)

    scoped_retriever.retrieve.assert_called_once_with("query")
    global_retriever.retrieve.assert_not_called()


def test_prepare_query_bounds_large_history_and_system_prompt() -> None:
    messages = [
        {"role": "system", "content": "s" * 50_000},
        {"role": "user", "content": "u" * 50_000},
        {"role": "assistant", "content": "a" * 50_000},
        {"role": "user", "content": "current" * 10_000},
    ]

    retrieval, synthesis = rag_api.prepare_query(messages)

    assert len(retrieval) <= 16_001
    assert len(synthesis) < 25_000
    assert "[...truncated...]" in synthesis


def test_knowledge_retrieval_rejects_near_zero_scores() -> None:
    assert not rag_service._retrieval_is_relevant([SimpleNamespace(score=0.014)])
    assert rag_service._retrieval_is_relevant([SimpleNamespace(score=0.016)])
    assert rag_service._retrieval_is_relevant([SimpleNamespace(score=0.2)])


def test_index_collections_are_reconciled_idempotently(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(shared_runtime.config, "COLLECTIONS_PATH", str(tmp_path / "collections.json"))
    monkeypatch.setattr(shared_runtime.config, "PERSIST_DIR", str(tmp_path))
    (tmp_path / "collections.json").write_text('{"collections": [{"id": "default", "name": "General"}]}')
    node = SimpleNamespace(metadata={"collection_id": "prueba-1", "collection_name": "prueba 1"})
    docstore = SimpleNamespace(docs={"node": node})

    shared_runtime._reconcile_index_collections(docstore)
    shared_runtime._reconcile_index_collections(docstore)

    collections = shared_runtime._read_collections_unlocked()
    assert [item["id"] for item in collections] == ["default", "prueba-1"]
    assert collections[1]["name"] == "prueba 1"


def test_collection_scope_distinguishes_missing_empty_and_populated(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(shared_runtime.config, "COLLECTIONS_PATH", str(tmp_path / "collections.json"))
    (tmp_path / "collections.json").write_text(
        '{"collections": [{"id": "default", "name": "General"}, '
        '{"id": "docs", "name": "Docs"}, {"id": "empty", "name": "Empty"}]}'
    )
    monkeypatch.setattr(
        shared_runtime.state,
        "index_docstore",
        SimpleNamespace(docs={"node": SimpleNamespace(metadata={"collection_id": "docs"})}),
    )

    assert shared_runtime._collection_scope([" docs "]) == (("docs",), None)
    assert shared_runtime._collection_scope(["empty"]) == (("empty",), "collection_empty")
    assert shared_runtime._collection_scope(["missing"]) == (("missing",), "collection_not_found")
