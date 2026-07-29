from __future__ import annotations

import asyncio
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.schemas import AgentRequest
from app.services import agent_service, memory_service, research_service, web_search_service
from trinaxai_cli.agent import Tool


def test_optional_agent_tools_return_grounded_results_and_degrade_cleanly(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(agent_service.state, "fusion_retriever", None)
    assert "What happened:" in agent_service._search_knowledge(tmp_path, query="release")
    monkeypatch.setattr(agent_service.state, "fusion_retriever", MagicMock())
    assert "What happened:" in agent_service._search_knowledge(tmp_path, query="")

    failing = MagicMock()
    failing.retrieve.side_effect = RuntimeError("index offline")
    monkeypatch.setattr(agent_service.state, "fusion_retriever", failing)
    assert "What happened:" in agent_service._search_knowledge(tmp_path, query="release")

    monkeypatch.setattr(memory_service, "memory_context_for_query", lambda query: f"memory for {query}")
    assert agent_service._search_memory(tmp_path, query="preferences") == "memory for preferences"
    assert "must not be empty" in agent_service._search_memory(tmp_path, query="")

    monkeypatch.setattr(
        agent_service,
        "_read_collections_unlocked",
        lambda: [{"id": "docs", "name": "Documentation"}],
    )
    assert '"id": "docs"' in agent_service._list_collections(tmp_path)

    monkeypatch.setattr(
        web_search_service,
        "search_web",
        lambda query: ([{"title": "Release", "url": "https://example.test", "snippet": query}], "test"),
    )
    web = agent_service._web_search(tmp_path, query="current release")
    assert "source=external; provider=test" in web
    assert "https://example.test" in web

    monkeypatch.setattr(
        research_service,
        "_research_sync",
        lambda _request: {
            "answer": "Compared sources",
            "sources": [{"title": "Primary", "url": "https://example.test/source"}],
        },
    )
    research = agent_service._deep_research(tmp_path, query="compare releases")
    assert "Compared sources" in research
    assert "https://example.test/source" in research


def test_agent_worker_emits_tool_activity_tokens_and_completion(monkeypatch, tmp_path) -> None:
    session_id, session = agent_service._register_session()
    tool = Tool(
        name="read_test",
        description="Read test evidence",
        parameters={"type": "object", "properties": {}},
        handler=lambda _root: "evidence",
        dangerous=False,
    )

    class Engine:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def run(self, _messages):
            self.kwargs["on_tool_start"](tool, {"path": "file.txt"})
            self.kwargs["on_tool_result"](tool, "evidence")
            self.kwargs["on_token"]("final")
            return "final answer"

        def cancel(self):
            return None

    monkeypatch.setattr(agent_service, "AgentEngine", Engine)
    request = AgentRequest(messages=[{"role": "user", "content": "inspect"}])

    agent_service._run_engine_worker(session, request, tmp_path, "test-model")

    events = []
    while True:
        event = session["queue"].get_nowait()
        if event is None:
            break
        events.append(event)
    assert [event["type"] for event in events] == ["tool_start", "tool_result", "token", "done"]
    assert session["steps"] == 1
    agent_service._drop_session(session_id)


def test_agent_event_stream_runs_worker_and_cleans_session(monkeypatch, tmp_path) -> None:
    session_id, session = agent_service._register_session()

    def worker(active_session, *_args):
        active_session["queue"].put({"type": "done", "answer": "complete"})
        active_session["queue"].put(None)

    class Thread:
        def __init__(self, *, target, args, **_kwargs):
            self.target = target
            self.args = args

        def start(self):
            self.target(*self.args)

        def join(self, timeout=None):
            return None

    monkeypatch.setattr(agent_service, "_run_engine_worker", worker)
    monkeypatch.setattr(agent_service.threading, "Thread", Thread)
    request = AgentRequest(messages=[{"role": "user", "content": "inspect"}])

    events = list(agent_service._agent_event_stream(session_id, session, request, tmp_path, "test-model"))

    assert '"type":"start"' in events[0]
    assert '"type":"done"' in events[1]
    assert events[-1] == "data: [DONE]\n\n"
    assert session_id not in agent_service._SESSIONS


def test_agent_browse_lists_only_safe_visible_directories(monkeypatch, tmp_path) -> None:
    visible = tmp_path / "visible"
    hidden = tmp_path / ".hidden"
    visible.mkdir()
    hidden.mkdir()
    (tmp_path / "file.txt").write_text("not a directory", encoding="utf-8")
    request = SimpleNamespace(query_params={"path": str(tmp_path)})
    monkeypatch.setattr(agent_service, "_authorize_system", lambda _request: None)
    monkeypatch.setattr(agent_service, "_configured_workspace_roots", lambda: (tmp_path.resolve(),))
    monkeypatch.setattr(agent_service, "_default_workspace", lambda _roots: tmp_path.resolve())

    result = asyncio.run(agent_service.agent_browse(request))

    assert result["path"] == str(tmp_path.resolve())
    assert result["parent"] is None
    assert result["directories"] == [{"name": "visible", "path": str(visible.resolve()), "readable": True}]


def test_agent_inference_slot_uses_both_local_and_process_guards(monkeypatch) -> None:
    entered = []

    @contextmanager
    def slot():
        entered.append("slot")
        yield

    @contextmanager
    def process():
        entered.append("process")
        yield

    monkeypatch.setattr(agent_service, "_model_slots", slot())
    monkeypatch.setattr(agent_service, "_inference_process_lock", process)

    with agent_service._agent_inference_slot():
        entered.append("body")

    assert entered == ["slot", "process", "body"]
