from __future__ import annotations

from unittest.mock import MagicMock

import rag_api


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
