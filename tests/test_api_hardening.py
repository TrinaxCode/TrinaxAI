from __future__ import annotations

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from starlette.testclient import TestClient

from app.schemas import ResearchRequest
from app.security.observability import SecurityObservabilityMiddleware
from app.services import research_service as research


@pytest.mark.parametrize("depth", [1, 2, 3])
def test_research_depth_accepts_supported_bounds(depth: int) -> None:
    assert ResearchRequest(query="question", depth=depth).depth == depth


@pytest.mark.parametrize("depth", [0, 4])
def test_research_depth_rejects_out_of_range_values(depth: int) -> None:
    with pytest.raises(ValidationError):
        ResearchRequest(query="question", depth=depth)


@pytest.mark.asyncio
async def test_research_rate_limit_runs_after_authorization_before_worker(monkeypatch) -> None:
    events: list[object] = []

    monkeypatch.setattr(
        research,
        "_authorize_research_request",
        lambda *_args, **_kwargs: events.append("authorize"),
    )
    monkeypatch.setattr(
        research,
        "enforce_rate_limit",
        lambda _request, *, bucket: events.append(("rate", bucket)),
    )
    monkeypatch.setattr(research, "wants_web_search", lambda _query: False)
    monkeypatch.setattr(research, "_research_sync", lambda _req: {"answer": "ok"})
    monkeypatch.setattr(research, "_run_model_task", lambda function, *args: function(*args))

    async def direct(function, *args):
        events.append("work")
        return function(*args)

    monkeypatch.setattr(research, "run_in_threadpool", direct)

    result = await research.research(ResearchRequest(query="question", web_search=False), object())

    assert result == {"answer": "ok", "finish_reason": "stop", "completion_status": "complete"}
    assert events == ["authorize", ("rate", "research"), "work"]


@pytest.mark.asyncio
async def test_research_preflight_rate_limit_runs_after_authorization_before_http(monkeypatch) -> None:
    events: list[object] = []

    monkeypatch.setattr(
        research,
        "_authorize_research_request",
        lambda *_args, **_kwargs: events.append("authorize"),
    )
    monkeypatch.setattr(
        research,
        "enforce_rate_limit",
        lambda _request, *, bucket: events.append(("rate", bucket)),
    )
    monkeypatch.setattr(research, "wants_web_search", lambda _query: False)
    monkeypatch.setattr(research.config, "MODEL_GENERAL", "general")
    monkeypatch.setattr(research, "configured_provider", lambda: "duckduckgo")

    class _Response:
        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict:
            events.append("work")
            return {"models": [{"name": "general:latest"}]}

    class _Client:
        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            pass

        def get(self, _url: str) -> _Response:
            return _Response()

    monkeypatch.setattr(research.httpx, "Client", lambda **_kwargs: _Client())

    result = await research.research_preflight(
        ResearchRequest(query="question", web_search=True),
        object(),
    )

    assert result["ok"] is True
    assert events == ["authorize", ("rate", "research_preflight"), "work"]


class _StaticASGIApp:
    async def __call__(self, scope, receive, send) -> None:
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})


@pytest.mark.parametrize("path", ["/collections", "/collections/docs", "/v1/stats"])
def test_private_api_paths_disable_caching_without_storage(path: str) -> None:
    client = TestClient(SecurityObservabilityMiddleware(_StaticASGIApp()))

    response = client.get(path)

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"


def test_authorization_failure_still_precedes_research_rate_limit(monkeypatch) -> None:
    events: list[str] = []

    def deny(*_args, **_kwargs):
        events.append("authorize")
        raise HTTPException(status_code=403, detail="denied")

    monkeypatch.setattr(research, "_authorize_research_request", deny)
    monkeypatch.setattr(research, "enforce_rate_limit", lambda *_args, **_kwargs: events.append("rate"))

    async def invoke() -> None:
        await research.research(ResearchRequest(query="question"), object())

    with pytest.raises(HTTPException) as exc_info:
        import asyncio

        asyncio.run(invoke())

    assert exc_info.value.status_code == 403
    assert events == ["authorize"]
