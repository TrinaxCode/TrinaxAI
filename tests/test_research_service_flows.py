from __future__ import annotations

import json
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
        ('["one", "two", "three", "four", "five"]', ["one", "two", "three", "four"]),
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

    local = research._research_synthesize(
        SimpleNamespace(complete=lambda _prompt: SimpleNamespace(text="Fuente [n]ALFA-7319.")),
        "¿Cuál es el identificador?",
        ["Identificarlo"],
        [{"id": "local", "text": "ALFA-7319", "metadata": {"rel_path": "first.txt"}, "score": 0.03}],
        web_search=False,
    )
    assert local == "Fuente ALFA-7319."


def test_research_synthesis_streams_tokens_closes_stream_and_adds_missing_citations() -> None:
    closed: list[bool] = []

    class Stream:
        def __iter__(self):
            return iter([SimpleNamespace(delta="Fact "), SimpleNamespace(delta=""), "[1]"])

        def close(self) -> None:
            closed.append(True)

    llm = SimpleNamespace(stream_complete=lambda _prompt: Stream())
    tokens: list[str] = []
    answer = research._research_synthesize(
        llm,
        "What is verified?",
        ["Verify it"],
        [{"id": "one", "text": "Verified fact", "metadata": {"title": "Source"}, "score": 0.9}],
        web_search=True,
        on_token=tokens.append,
    )

    assert answer == "Fact [1]"
    assert tokens == ["Fact ", "[1]"]
    assert closed == [True]


def test_research_synthesis_handles_empty_and_cancelled_streams() -> None:
    empty_tokens: list[str] = []
    empty = research._research_synthesize(
        SimpleNamespace(complete=lambda _prompt: SimpleNamespace(text="unused")),
        "¿Qué ocurrió?",
        [],
        [],
        on_token=empty_tokens.append,
    )
    assert empty == "No se encontró contexto relevante en los documentos indexados."
    assert empty_tokens == [empty]

    cancelled = research.threading.Event()
    cancelled.set()
    with pytest.raises(research._ResearchCancelled):
        research._research_synthesize(
            SimpleNamespace(complete=lambda _prompt: SimpleNamespace(text="unused")),
            "What happened?",
            [],
            [{"text": "context", "metadata": {}}],
            cancel_event=cancelled,
        )

    fallback_tokens: list[str] = []
    fallback = research._research_synthesize(
        SimpleNamespace(stream_complete=lambda _prompt: iter(())),
        "What happened?",
        ["Find it"],
        [{"text": "context", "metadata": {}}],
        on_token=fallback_tokens.append,
    )
    assert fallback_tokens == [fallback]

    closed: list[bool] = []
    event = research.threading.Event()

    class CancellingStream:
        def __iter__(self):
            yield SimpleNamespace(delta="partial")
            event.set()
            yield SimpleNamespace(delta="discarded")

        def close(self) -> None:
            closed.append(True)

    tokens: list[str] = []
    with pytest.raises(research._ResearchCancelled):
        research._research_synthesize(
            SimpleNamespace(stream_complete=lambda _prompt: CancellingStream()),
            "What happened?",
            ["Find it"],
            [{"text": "context", "metadata": {}}],
            on_token=tokens.append,
            cancel_event=event,
        )
    assert tokens == ["partial"]
    assert closed == [True]


def test_research_synthesis_stream_failure_emits_safe_fallback() -> None:
    tokens: list[str] = []
    answer = research._research_synthesize(
        SimpleNamespace(stream_complete=lambda _prompt: (_ for _ in ()).throw(RuntimeError("offline"))),
        "What happened?",
        ["Find it"],
        [{"text": "context", "metadata": {}}],
        on_token=tokens.append,
    )

    assert answer
    assert tokens == [answer]


def test_research_sync_stops_before_starting_work_when_cancelled() -> None:
    event = research.threading.Event()
    event.set()
    result = research._research_sync(ResearchRequest(query="cancelled"), cancel_event=event)
    assert result["cancelled"] is True


def test_research_sync_stops_after_model_setup_when_cancelled(monkeypatch) -> None:
    event = research.threading.Event()
    monkeypatch.setattr(research.state, "fusion_retriever", object())
    monkeypatch.setattr(research, "wants_web_search", lambda _query: False)
    monkeypatch.setattr(research, "get_llm", lambda *_args, **_kwargs: object())

    def decompose(*_args):
        event.set()
        return ["question"]

    monkeypatch.setattr(research, "_research_decompose", decompose)

    result = research._research_sync(ResearchRequest(query="question"), cancel_event=event)

    assert result["cancelled"] is True


def test_research_without_index_returns_actionable_no_index_result(monkeypatch) -> None:
    monkeypatch.setattr(research.state, "fusion_retriever", None)
    monkeypatch.setattr(research, "wants_web_search", lambda _query: False)

    tokens: list[str] = []
    result = research._research_sync(
        ResearchRequest(query="local question", web_search=False),
        on_token=tokens.append,
    )

    assert result == {
        "answer": research.NO_INDEX_MSG,
        "sub_questions": [],
        "sources": [],
        "passes": 0,
        "model": research.config.MODEL_GENERAL,
    }
    assert tokens == [research.NO_INDEX_MSG]


def test_research_rejects_empty_selected_collection(monkeypatch, tmp_path) -> None:
    (tmp_path / "collections.json").write_text(
        '{"collections": [{"id": "default", "name": "General"}, {"id": "empty", "name": "Empty"}]}'
    )
    monkeypatch.setattr(research.config, "COLLECTIONS_PATH", str(tmp_path / "collections.json"))
    monkeypatch.setattr(research.state, "fusion_retriever", object())
    monkeypatch.setattr(research.state, "index_docstore", SimpleNamespace(docs={}))

    tokens: list[str] = []
    result = research._research_sync(
        ResearchRequest(query="local question", collections=["empty"], web_search=False),
        on_token=tokens.append,
    )

    assert result["error_code"] == "collection_empty"
    assert result["sources"] == []
    assert "contains no indexed documents" in result["answer"]
    assert tokens == [result["answer"]]


def test_research_web_only_does_not_require_local_collection(monkeypatch) -> None:
    monkeypatch.setattr(research.state, "fusion_retriever", None)
    monkeypatch.setattr(research, "wants_web_search", lambda _query: False)
    monkeypatch.setattr(research, "configured_provider", lambda: "duckduckgo")
    monkeypatch.setattr(
        research,
        "get_llm",
        lambda *_args, **_kwargs: SimpleNamespace(complete=lambda _prompt: SimpleNamespace(text="respuesta")),
    )
    monkeypatch.setattr(
        research,
        "search_web",
        lambda *_args, **_kwargs: (
            [{"url": "https://example.test", "title": "Source", "snippet": "Fact"}],
            "duckduckgo",
        ),
    )
    monkeypatch.setattr(research, "read_web_results", lambda rows, limit: rows)

    result = research._research_sync(ResearchRequest(query="current question", web_search=True, include_local=False))

    assert result["web_search"] is True
    assert result["sources"][0]["kind"] == "web"


def test_research_continues_with_local_sources_when_web_search_fails(monkeypatch) -> None:
    node = SimpleNamespace(
        node_id="local-1",
        text="Local verified context",
        metadata={"rel_path": r"C:\private\doc.md", "collection_id": "default"},
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
    assert result["sources"][0]["file"] == "doc.md"
    assert "Some web research passes failed" in result["answer"]
    assert "timeout" not in result["answer"]


def test_research_reports_embedding_failure(monkeypatch) -> None:
    monkeypatch.setattr(research.state, "fusion_retriever", object())
    monkeypatch.setattr(research, "get_llm", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(
        research, "_research_retrieve", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("embedder"))
    )

    result = research._research_sync(ResearchRequest(query="local question", include_local=True))

    assert result["error_code"] == "embedding_error"
    assert result["sources"] == []


def test_research_web_provider_runs_multiple_passes_and_enriches_sources(monkeypatch) -> None:
    monkeypatch.setattr(research.state, "fusion_retriever", None)
    monkeypatch.setattr(research, "configured_provider", lambda: "brave")
    monkeypatch.setattr(research, "_research_decompose", lambda *_args: ["first facet", "second facet"])
    monkeypatch.setattr(
        research,
        "get_llm",
        lambda *_args, **_kwargs: SimpleNamespace(complete=lambda _prompt: SimpleNamespace(text="Grounded answer")),
    )
    monkeypatch.setattr(
        research,
        "search_web",
        lambda query, **_kwargs: (
            [{"url": f"https://example.test/{query.replace(' ', '-')}", "title": query, "snippet": "fact"}],
            "brave",
        ),
    )
    monkeypatch.setattr(
        research,
        "read_web_results",
        lambda rows, **_kwargs: [dict(row, content="full fact", content_scope="full_page") for row in rows],
    )

    result = research._research_sync(
        ResearchRequest(query="current topic", web_search=True, include_local=False, depth=2),
    )

    assert result["passes"] == 2
    assert result["web_provider"] == "brave"
    assert result["sources"][0]["content_scope"] == "full_page"
    assert "[1]" in result["answer"]


def test_research_web_outage_returns_typed_local_fallback(monkeypatch) -> None:
    monkeypatch.setattr(research.state, "fusion_retriever", None)
    monkeypatch.setattr(research, "configured_provider", lambda: "duckduckgo")
    monkeypatch.setattr(
        research,
        "get_llm",
        lambda *_args, **_kwargs: SimpleNamespace(complete=lambda _prompt: SimpleNamespace(text="Local fallback")),
    )
    monkeypatch.setattr(
        research, "search_web", lambda *_args, **_kwargs: (_ for _ in ()).throw(research.WebSearchError("offline"))
    )
    monkeypatch.setattr(research, "read_web_results", lambda _rows, **_kwargs: [])

    result = research._research_sync(ResearchRequest(query="current topic", web_search=True, include_local=False))

    assert result["error_code"] == "web_search_unavailable"
    assert result["degraded"] is True
    assert result["sources"] == []


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
    monkeypatch.setattr(research, "authorize_scope", lambda _request, _scope: None)
    monkeypatch.setattr(research, "enforce_rate_limit", lambda *_args, **_kwargs: None)
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
    monkeypatch.setattr(research, "authorize_scope", lambda _request, _scope: None)
    monkeypatch.setattr(research, "enforce_rate_limit", lambda *_args, **_kwargs: None)
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
    monkeypatch.setattr(research, "enforce_rate_limit", lambda *_args, **_kwargs: None)
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
    assert auth == ["web", "read_private"]

    combined_result = await research.research(
        ResearchRequest(query="current local", web_search=True, include_local=True),
        object(),
    )

    assert combined_result == {"query": "current local"}
    assert auth == ["web", "read_private", "web", "read_private"]


@pytest.mark.asyncio
async def test_research_stream_emits_tokens_sources_metadata_and_done(monkeypatch) -> None:
    monkeypatch.setattr(research, "_run_model_task", lambda function, *args: function(*args))
    monkeypatch.setattr(
        research,
        "_research_sync",
        lambda _req, on_token, _cancel_event: (
            on_token("Primero "),
            on_token("segundo"),
            {
                "answer": "Primero segundo",
                "sources": [{"title": "Artículo", "url": "https://example.test"}],
                "web_search": True,
                "web_provider": "duckduckgo",
                "search_query": "current official source",
                "passes": 1,
                "sub_questions": ["consulta"],
            },
        )[-1],
    )

    events = [event async for event in research._research_stream(ResearchRequest(query="current", stream=True))]
    payloads = [json.loads(line[6:]) for line in events[:-1] if line.startswith("data: {")]

    assert payloads[0]["choices"][0]["delta"]["content"] == "Primero "
    assert payloads[1]["choices"][0]["delta"]["content"] == "segundo"
    assert payloads[2]["trinaxai_sources"][0]["title"] == "Artículo"
    assert payloads[2]["trinaxai_research"]["web_provider"] == "duckduckgo"
    assert payloads[2]["trinaxai_research"]["search_query"] == "current official source"
    assert payloads[2]["trinaxai_finish"] == {
        "reason": "stop",
        "status": "complete",
        "can_continue": False,
        "max_continuations": research.config.MAX_CONTINUATIONS,
    }
    assert events[-1] == "data: [DONE]\n\n"
