from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest

from app.schemas import ResearchRequest
from app.services import research_service as research


def test_research_retrieval_normalizes_collections_and_bounds_results(monkeypatch) -> None:
    nodes = [
        SimpleNamespace(metadata={"collection_id": "alpha"}),
        SimpleNamespace(metadata={"collection_id": "beta"}),
    ]
    selected: list[tuple[str, ...]] = []
    retriever = SimpleNamespace(retrieve=lambda _query: nodes)
    monkeypatch.setattr(research.state, "fusion_retriever", object())
    monkeypatch.setattr(
        research,
        "_retriever_for_collections",
        lambda collections: selected.append(collections) or retriever,
    )

    result = research._research_retrieve("query", [" alpha ", "alpha"], top_k=1)

    assert selected == [("alpha",)]
    assert result == [nodes[0]]


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        ('["first", " second ", ""]', ["first", "second"]),
        ("not json", ["question"]),
        ('{"item":"not a list"}', ["question"]),
        ("[]", ["question"]),
    ],
)
def test_research_decomposition_accepts_only_nonempty_json_lists(response, expected) -> None:
    llm = SimpleNamespace(complete=lambda _prompt: SimpleNamespace(text=response))

    assert research._research_decompose(llm, "question", 2) == expected
    assert research._research_decompose(llm, "question", 1) == ["question"]


def test_research_decomposition_recovers_from_model_failure() -> None:
    llm = SimpleNamespace(complete=lambda _prompt: (_ for _ in ()).throw(RuntimeError("offline")))

    assert research._research_decompose(llm, "question", 3) == ["question"]


def test_research_fallback_matches_the_query_language() -> None:
    chunks = [
        {
            "text": "A useful excerpt",
            "metadata": {
                "title": "Official source",
                "url": "https://example.com",
                "content_scope": "snippet_only",
            },
        }
    ]

    english = research._research_fallback(chunks, web_search=True, language="English")
    spanish = research._research_fallback([], web_search=False, language="Spanish")

    assert english.startswith("I could not synthesize a complete answer")
    assert "snippet del buscador" in english
    assert "Official source" in english
    assert spanish == "No se encontraron fuentes suficientes para responder con confianza."


def test_local_research_fallback_strips_fake_citations_and_survives_model_failure() -> None:
    answer = research._research_local_fallback(
        SimpleNamespace(complete=lambda _prompt: SimpleNamespace(text="General answer [99].")),
        "what happened",
        "search timed out",
    )
    failed = research._research_local_fallback(
        SimpleNamespace(complete=lambda _prompt: (_ for _ in ()).throw(RuntimeError("offline"))),
        "¿qué pasó?",
        "search timed out",
    )

    assert "General answer ." in answer
    assert "[99]" not in answer
    assert "not live-web verified" in answer
    assert "No pude generar una respuesta local" in failed


def test_research_synthesis_uses_localized_fallback_and_valid_citations_only() -> None:
    chunks = [
        {
            "id": "one",
            "text": "Verified fact",
            "metadata": {"title": "Source", "url": "https://example.com"},
            "score": 0.9,
        }
    ]
    empty = research._research_synthesize(
        SimpleNamespace(complete=lambda _prompt: SimpleNamespace(text="")),
        "What is verified?",
        ["Verify it"],
        chunks,
        web_search=True,
    )
    cited = research._research_synthesize(
        SimpleNamespace(complete=lambda _prompt: SimpleNamespace(text="Fact [1], unsupported [9].")),
        "What is verified?",
        ["Verify it"],
        chunks,
        web_search=True,
    )

    assert empty.startswith("I could not synthesize a complete answer")
    assert cited == "Fact [1], unsupported ."


def test_research_without_index_returns_actionable_no_index_result(monkeypatch) -> None:
    monkeypatch.setattr(research.state, "fusion_retriever", None)
    monkeypatch.setattr(research, "wants_web_search", lambda _query: False)

    result = research._research_sync(ResearchRequest(query="local question", web_search=False))

    assert result == {
        "answer": research.NO_INDEX_MSG,
        "sub_questions": [],
        "sources": [],
        "passes": 0,
        "model": research.config.MODEL_GENERAL,
    }


def test_research_continues_with_local_sources_when_web_search_fails(monkeypatch) -> None:
    node = SimpleNamespace(
        node_id="local-1",
        text="Local verified context",
        metadata={"rel_path": "doc.md", "collection_id": "default"},
        score=0.8,
    )
    llm = SimpleNamespace(complete=lambda _prompt: SimpleNamespace(text="Local answer [1]."))
    monkeypatch.setattr(research.state, "fusion_retriever", object())
    monkeypatch.setattr(research, "get_llm", lambda *_args, **_kwargs: llm)
    monkeypatch.setattr(research, "_research_retrieve", lambda *_args, **_kwargs: [node])
    monkeypatch.setattr(
        research,
        "search_web",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(research.WebSearchError("timeout")),
    )
    monkeypatch.setattr(research, "read_web_results", lambda rows, limit: rows)

    result = research._research_sync(
        ResearchRequest(query="current topic", web_search=True, include_local=True, depth=1)
    )

    assert result["degraded"] is True
    assert result["sources"][0]["kind"] == "local"
    assert "Some web research passes failed" in result["answer"]
    assert "timeout" not in result["answer"]


class _TagsResponse:
    def __init__(self, models: list[str], *, error: Exception | None = None) -> None:
        self.models = models
        self.error = error

    def raise_for_status(self) -> None:
        if self.error:
            raise self.error

    def json(self) -> dict:
        return {"models": [{"name": name} for name in self.models]}


class _Client:
    def __init__(self, response: _TagsResponse) -> None:
        self.response = response

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def get(self, _url: str):
        return self.response


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("models", "retriever", "provider", "expected_code"),
    [
        (["other:latest"], object(), "duckduckgo", "model_unavailable"),
        (["general:latest"], None, "duckduckgo", "collection_empty"),
        (["general:latest"], object(), "disabled", "web_search_disabled"),
    ],
)
async def test_research_preflight_reports_missing_dependencies(
    monkeypatch,
    models,
    retriever,
    provider,
    expected_code,
) -> None:
    monkeypatch.setattr(research, "_authorize_system", lambda _request: None)
    monkeypatch.setattr(research, "authorize_scope", lambda _request, _scope: None)
    monkeypatch.setattr(research.config, "MODEL_GENERAL", "general")
    monkeypatch.setattr(research.state, "fusion_retriever", retriever)
    monkeypatch.setattr(research, "configured_provider", lambda: provider)
    monkeypatch.setattr(research.httpx, "Client", lambda **_kwargs: _Client(_TagsResponse(models)))
    request = ResearchRequest(
        query="search current topic" if expected_code == "web_search_disabled" else "local topic",
        web_search=expected_code == "web_search_disabled",
    )

    result = await research.research_preflight(request, object())

    assert result["ok"] is False
    assert result["error_code"] == expected_code
    assert "error_contract" in result


@pytest.mark.asyncio
async def test_research_preflight_reports_ollama_failure_and_accepts_latest_alias(monkeypatch) -> None:
    monkeypatch.setattr(research, "_authorize_system", lambda _request: None)
    monkeypatch.setattr(research.config, "MODEL_GENERAL", "general")
    monkeypatch.setattr(research.state, "fusion_retriever", object())
    failure = httpx.ConnectError("offline")
    monkeypatch.setattr(
        research.httpx,
        "Client",
        lambda **_kwargs: _Client(_TagsResponse([], error=failure)),
    )

    unavailable = await research.research_preflight(ResearchRequest(query="local"), object())
    assert unavailable["error_code"] == "ollama_unavailable"
    assert "offline" not in unavailable["error_detail"]

    monkeypatch.setattr(
        research.httpx,
        "Client",
        lambda **_kwargs: _Client(_TagsResponse(["general:latest"])),
    )
    ready = await research.research_preflight(ResearchRequest(query="local"), object())

    assert ready == {
        "ok": True,
        "model": "general",
        "indexed": True,
        "web_provider": None,
    }


@pytest.mark.asyncio
async def test_research_endpoint_uses_scope_specific_auth_and_threadpool(monkeypatch) -> None:
    auth: list[str] = []
    monkeypatch.setattr(research, "authorize_scope", lambda _request, scope: auth.append(scope))
    monkeypatch.setattr(research, "_authorize_system", lambda _request: auth.append("system"))
    monkeypatch.setattr(research, "_research_sync", lambda req: {"query": req.query})
    monkeypatch.setattr(research, "_run_model_task", lambda func, *args: func(*args))

    async def direct(func, *args):
        return func(*args)

    monkeypatch.setattr(research, "run_in_threadpool", direct)

    web_result = await research.research(
        ResearchRequest(query="current", web_search=True, include_local=False),
        object(),
    )
    local_result = await research.research(
        ResearchRequest(query="local", web_search=False, include_local=True),
        object(),
    )

    assert web_result == {"query": "current"}
    assert local_result == {"query": "local"}
    assert auth == ["web", "system"]
