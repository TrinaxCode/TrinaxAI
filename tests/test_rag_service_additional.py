from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

import config
from app.schemas import ChatRequest
from app.services import rag_service


def _local_request() -> Request:
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/v1/chat/completions",
            "raw_path": b"/v1/chat/completions",
            "query_string": b"",
            "scheme": "https",
            "server": ("localhost", 3333),
            "client": ("127.0.0.1", 50000),
            "headers": [],
        }
    )
    request.state.request_id = "request-1"
    return request


def test_knowledge_collection_state_distinguishes_missing_empty_and_ready(monkeypatch) -> None:
    monkeypatch.setattr(
        rag_service,
        "_read_collections_unlocked",
        lambda: [{"id": "default"}, {"id": "docs"}],
    )
    monkeypatch.setattr(rag_service.state, "index_docstore", SimpleNamespace(docs={}))

    assert rag_service._knowledge_collection_state(["docs"]) == "empty"
    with pytest.raises(HTTPException) as exc:
        rag_service._knowledge_collection_state(["../../private"])
    assert exc.value.status_code == 404
    assert exc.value.detail["collection"] == "private"

    rag_service.state.index_docstore.docs["one"] = SimpleNamespace(metadata={"collection_id": "docs"})
    assert rag_service._knowledge_collection_state(["docs"]) == "ready"


def test_cancel_ollama_is_best_effort(monkeypatch) -> None:
    requests = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    monkeypatch.setattr(
        rag_service.urllib.request,
        "urlopen",
        lambda request, timeout: requests.append((request, timeout)) or Response(),
    )
    rag_service._cancel_ollama_model(None)
    rag_service._cancel_ollama_model("general")

    assert len(requests) == 1
    assert json.loads(requests[0][0].data) == {"model": "general", "keep_alive": 0}

    monkeypatch.setattr(
        rag_service.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("offline")),
    )
    rag_service._cancel_ollama_model("general")


def test_project_detection_and_catalog_answer_use_metadata(monkeypatch) -> None:
    monkeypatch.setattr(rag_service.state, "known_projects", ["AI", "Aurora Platform", "test-documents"])
    assert rag_service.detect_project("Explain Aurora Platform") == "Aurora Platform"
    assert rag_service.detect_project("What is in my indexed documents?") is None
    assert rag_service.detect_project("Explain an unrelated topic") is None

    docs = {
        "one": SimpleNamespace(
            metadata={
                "collection_id": "docs",
                "rel_path": "guide.md",
                "project": "Aurora",
            }
        ),
        "duplicate": SimpleNamespace(
            metadata={
                "collection_id": "docs",
                "rel_path": "guide.md",
                "project": "Aurora",
            }
        ),
        "other": SimpleNamespace(metadata={"collection_id": "other", "rel_path": "secret.md"}),
        "legacy": SimpleNamespace(
            metadata={"collection_id": "docs", "file_path": "/home/private/legacy.md"},
        ),
    }
    monkeypatch.setattr(rag_service.state, "index_docstore", SimpleNamespace(docs=docs))

    answer = rag_service._catalog_answer(["docs"], spanish=False)
    assert "Projects: Aurora" in answer
    assert "- docs: 2 file(s)" in answer
    assert "secret.md" not in answer
    assert "legacy.md" in answer
    assert "/home/private/legacy.md" not in answer

    monkeypatch.setattr(rag_service.state, "index_docstore", SimpleNamespace(docs={}))
    assert rag_service._catalog_answer(["docs"], spanish=True) == rag_service.EMPTY_COLLECTION_MSG


def test_memory_failure_and_existing_marker_do_not_duplicate_messages(monkeypatch) -> None:
    messages = [
        {
            "role": "system",
            "content": "Persistent memory summary (untrusted user-managed data)",
        },
        {"role": "user", "content": "hello"},
    ]
    assert rag_service._with_persistent_memory(messages) is messages

    from app.services import memory_service

    monkeypatch.setattr(
        memory_service,
        "memory_context_for_query",
        lambda _query: (_ for _ in ()).throw(RuntimeError("unreadable")),
    )
    plain = [{"role": "user", "content": "hello"}]
    assert rag_service._with_persistent_memory(plain) is plain


def test_cached_retrieval_filters_project_reranks_and_caches(monkeypatch) -> None:
    alpha = SimpleNamespace(metadata={"project": "Aurora"}, score=0.4)
    beta = SimpleNamespace(metadata={"project": "Other"}, score=0.9)
    retriever = SimpleNamespace(retrieve=lambda _query: [beta, alpha])
    reranker = SimpleNamespace(postprocess_nodes=lambda nodes, query_bundle: list(reversed(nodes)))
    monkeypatch.setattr(rag_service, "_retriever_for_collections", lambda _collections: retriever)
    monkeypatch.setattr(rag_service.state, "reranker", reranker)
    monkeypatch.setattr(config, "RETRIEVAL_CACHE_SECONDS", 30)
    rag_service.state.retrieval_cache.clear()

    first = rag_service._cached_retrieve("query", "current", ["docs"], "Aurora")
    second = rag_service._cached_retrieve("query", "current", ["docs"], "Aurora")

    assert first == [alpha]
    assert second == [alpha]
    assert rag_service.state.retrieval_cache


def test_cached_retrieval_prioritizes_exact_identifiers(monkeypatch) -> None:
    noise = SimpleNamespace(metadata={}, score=0.9, get_content=lambda: "unrelated text")
    exact = SimpleNamespace(
        metadata={},
        score=0.1,
        get_content=lambda: "marker TRINAXAI_RAG_ROUND2_MARKER_84721",
    )
    retriever = SimpleNamespace(retrieve=lambda _query: [noise, exact])
    monkeypatch.setattr(rag_service, "_retriever_for_collections", lambda _collections: retriever)
    monkeypatch.setattr(rag_service.state, "reranker", None)
    monkeypatch.setattr(config, "RETRIEVAL_CACHE_SECONDS", 0)
    monkeypatch.setattr(config, "SIMILARITY_TOP_K", 2)

    nodes = rag_service._cached_retrieve(
        "What is TRINAXAI_RAG_ROUND2_MARKER_84721?",
        "What is TRINAXAI_RAG_ROUND2_MARKER_84721?",
        None,
        None,
    )

    assert nodes == [exact]


def test_text_response_deliverables_relevance_and_sources_are_stable() -> None:
    response = rag_service._TextResponse(gen=iter(["one", "two"]))
    assert response.response == "onetwo"
    assert list(rag_service._TextResponse(text="ready").response_gen) == ["ready"]
    assert rag_service._wanted_deliverables("tests benchmark FAQ chat responsive animation") == (
        "tests",
        "benchmark",
        "faq",
        "chat",
        "responsive",
        "animation",
    )

    assert not rag_service._retrieval_is_relevant([])
    assert rag_service._retrieval_is_relevant([SimpleNamespace(score=None)])
    assert not rag_service._retrieval_is_relevant([SimpleNamespace(score="invalid"), SimpleNamespace(score=0.0)])

    node = SimpleNamespace(
        metadata={
            "rel_path": "guide.md",
            "page": 2,
            "collection_id": "docs",
            "collection_name": "Docs",
        },
        score=0.8765,
        get_content=lambda: " useful excerpt ",
    )
    sources = rag_service.sources_payload([node, node])
    assert sources == [
        {
            "file": "guide.md",
            "project": "",
            "collection_id": "docs",
            "collection": "Docs",
            "page": 2,
            "snippet": "useful excerpt",
            "score": 0.876,
        }
    ]

    node.metadata["rel_path"] = r"C:\private\secret.md"
    legacy_sources = rag_service.sources_payload([node])
    assert legacy_sources[0]["file"] == "secret.md"


@pytest.mark.asyncio
async def test_empty_knowledge_collection_returns_complete_stream_and_json(monkeypatch) -> None:
    monkeypatch.setattr(rag_service, "enforce_rate_limit", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(rag_service, "_knowledge_collection_state", lambda _collections: "empty")
    request = _local_request()

    stream = await rag_service.chat(
        ChatRequest(
            model="general",
            messages=[{"role": "user", "content": "question"}],
            stream=True,
            mode="knowledge",
            collections=["docs"],
        ),
        request,
    )
    body = "".join([chunk async for chunk in stream.body_iterator])
    assert rag_service.EMPTY_COLLECTION_MSG in body
    assert "[DONE]" in body

    result = await rag_service.chat(
        ChatRequest(
            model="general",
            messages=[{"role": "user", "content": "question"}],
            stream=False,
            mode="knowledge",
            collections=["docs"],
        ),
        request,
    )
    assert result["choices"][0]["message"]["content"] == rag_service.EMPTY_COLLECTION_MSG
    assert result["trinaxai"]["result_count"] == 0
    assert result["trinaxai"]["abstained"] is True
