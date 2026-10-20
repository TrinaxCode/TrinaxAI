from __future__ import annotations

import asyncio
import queue
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

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
    assert "example.test" in web

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


def test_agent_tool_list_uses_live_scopes_and_services(monkeypatch) -> None:
    private_web = SimpleNamespace(state=SimpleNamespace(trinaxai_identity={"scopes": ["agent"]}))
    request = AgentRequest(messages=[{"role": "user", "content": "compare sources"}])
    monkeypatch.setattr(agent_service.state, "fusion_retriever", MagicMock())
    monkeypatch.setattr(agent_service.config, "WEB_SEARCH_PROVIDER", "auto")

    restricted = agent_service._agent_tools(
        available_names=agent_service._available_agent_tool_names(request, private_web),
    )
    restricted_names = {tool.name for tool in restricted}
    assert "read_file" in restricted_names
    assert {"search_memory", "search_knowledge", "web_search", "deep_research"}.isdisjoint(restricted_names)

    # Legacy LAN credentials with the retired host-only agent scope must not
    # make the HTTP agent reachable; the route authorizer rejects them first.
    assert agent_service._available_agent_tool_names(request, private_web) == {
        tool.name for tool in agent_service.DEFAULT_TOOLS
    }

    full = SimpleNamespace(state=SimpleNamespace(trinaxai_identity={"scopes": ["agent", "read_private", "web"]}))
    available = agent_service._agent_tools(
        available_names=agent_service._available_agent_tool_names(request, full),
    )
    assert {"search_memory", "search_knowledge", "list_collections", "web_search", "deep_research"}.issubset(
        {tool.name for tool in available}
    )

    monkeypatch.setattr(agent_service.config, "WEB_SEARCH_PROVIDER", "disabled")
    disabled_web = agent_service._agent_tools(
        available_names=agent_service._available_agent_tool_names(request, full),
    )
    assert {"web_search", "deep_research"}.isdisjoint({tool.name for tool in disabled_web})


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
    assert events[-1]["finish_reason"] == "stop"
    assert events[-1]["completion_status"] == "complete"
    assert session["steps"] == 1
    agent_service._drop_session(session_id)


def test_agent_worker_reports_degraded_model_fallback(monkeypatch, tmp_path) -> None:
    class Engine:
        completion_status = "degraded"

        def __init__(self, **_kwargs):
            pass

        def run(self, _messages):
            return "Useful fallback after Ollama failure"

        def cancel(self):
            return None

    session_id, session = agent_service._register_session()
    monkeypatch.setattr(agent_service, "AgentEngine", Engine)
    try:
        agent_service._run_engine_worker(
            session, AgentRequest(messages=[{"role": "user", "content": "inspect"}]), tmp_path, "test-model"
        )
        done = session["queue"].get_nowait()
        assert done == {
            "type": "done",
            "answer": "Useful fallback after Ollama failure",
            "finish_reason": "stop",
            "completion_status": "degraded",
        }
    finally:
        agent_service._drop_session(session_id)


def test_terminal_done_survives_a_full_session_queue(monkeypatch) -> None:
    monkeypatch.setattr(agent_service, "_AGENT_QUEUE_MAXSIZE", 4)
    session_id, session = agent_service._register_session()
    try:
        for index in range(session["queue"].maxsize):
            assert agent_service._queue_event(session, {"type": "token", "content": str(index)})

        assert agent_service._queue_event(
            session,
            {"type": "done", "answer": "complete", "finish_reason": "stop", "completion_status": "complete"},
            terminal=True,
        )

        events = []
        while True:
            try:
                event = session["queue"].get_nowait()
            except queue.Empty:
                break
            if event is not None:
                events.append(event)
        assert events == [
            {"type": "done", "answer": "complete", "finish_reason": "stop", "completion_status": "complete"}
        ]
    finally:
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


def _device_request(**query) -> SimpleNamespace:
    return SimpleNamespace(
        query_params=query,
        state=SimpleNamespace(trinaxai_identity={"kind": "device", "id": "dev1", "scopes": ["agent"]}),
    )


@pytest.fixture
def install_layout(monkeypatch, tmp_path):
    """A projects root that also contains the TrinaxAI install, like a real host."""
    projects = tmp_path / "projects"
    install = projects / "ai-rag"
    (install / "storage").mkdir(parents=True)
    (install / ".env").write_text("TRINAXAI_ADMIN_TOKEN=secret", encoding="utf-8")
    (install / "storage" / ".device_secret").write_text("ab" * 32, encoding="ascii")
    other = projects / "client-site"
    other.mkdir()
    monkeypatch.setattr(agent_service.config, "BASE_DIR", str(install))
    monkeypatch.setattr(agent_service.config, "PERSIST_DIR", str(install / "storage"))
    monkeypatch.setattr(agent_service.config, "LOCAL_SOURCES_DIR", str(install / "local_sources"))
    monkeypatch.setattr(
        agent_service, "credential_files", lambda: (install / "storage" / "r.json", install / "storage" / ".s")
    )
    monkeypatch.setattr(agent_service, "proxy_secret_file", lambda: install / "storage" / ".proxy_secret")
    monkeypatch.setattr(agent_service, "_configured_workspace_roots", lambda: (projects.resolve(), install.resolve()))
    monkeypatch.setattr(agent_service, "_authorize_system", lambda _request: None)
    return SimpleNamespace(projects=projects.resolve(), install=install.resolve(), other=other.resolve())


def test_device_workspace_never_includes_trinaxai_own_files(install_layout) -> None:
    confine = agent_service._confine_device_workspace
    device = _device_request()
    # An explicit request for the install, its storage, or a parent that contains it is refused.
    for path in (install_layout.install, install_layout.install / "storage", install_layout.projects):
        with pytest.raises(HTTPException) as denied:
            confine(path, device, explicit=True)
        assert denied.value.status_code == 403
    # A sibling project is fine.
    assert confine(install_layout.other, device, explicit=True) == install_layout.other
    # Here every root holds the install, so there is no default to fall back to.
    with pytest.raises(HTTPException):
        confine(install_layout.install, device, explicit=False)
    # The localhost operator is unaffected.
    local = SimpleNamespace(state=SimpleNamespace(trinaxai_identity={"kind": "local"}))
    assert confine(install_layout.install, local, explicit=True) == install_layout.install
    assert confine(install_layout.install, SimpleNamespace(), explicit=True) == install_layout.install


def test_device_default_workspace_is_replaced_by_a_root_that_is_safe(monkeypatch, install_layout) -> None:
    monkeypatch.setattr(
        agent_service, "_configured_workspace_roots", lambda: (install_layout.install, install_layout.other)
    )
    chosen = agent_service._confine_device_workspace(install_layout.install, _device_request(), explicit=False)
    assert chosen == install_layout.other
    monkeypatch.setattr(agent_service, "_configured_workspace_roots", lambda: (install_layout.install,))
    with pytest.raises(HTTPException) as denied:
        agent_service._confine_device_workspace(install_layout.install, _device_request(), explicit=False)
    assert denied.value.status_code == 403


def test_device_browse_hides_trinaxai_own_folders_and_refuses_to_enter_them(install_layout) -> None:
    listing = asyncio.run(agent_service.agent_browse(_device_request(path=str(install_layout.projects))))
    assert [entry["name"] for entry in listing["directories"]] == ["client-site"]

    for inside in (install_layout.install, install_layout.install / "storage"):
        with pytest.raises(HTTPException) as denied:
            asyncio.run(agent_service.agent_browse(_device_request(path=str(inside))))
        assert denied.value.status_code == 403

    # No path given: the default would be the install, so a navigable root is offered instead.
    default = asyncio.run(agent_service.agent_browse(_device_request()))
    assert default["path"] == str(install_layout.projects)
    assert default["home"] == str(install_layout.projects)

    # The host still sees everything.
    local = SimpleNamespace(
        query_params={"path": str(install_layout.projects)},
        state=SimpleNamespace(trinaxai_identity={"kind": "local"}),
    )
    names = [entry["name"] for entry in asyncio.run(agent_service.agent_browse(local))["directories"]]
    assert names == ["ai-rag", "client-site"]


def test_agent_endpoint_refuses_a_device_workspace_that_holds_credentials(monkeypatch, install_layout) -> None:
    monkeypatch.setattr(agent_service, "_authorize_http_yolo", lambda *_args: None)
    monkeypatch.setattr(agent_service, "enforce_rate_limit", lambda *_args, **_kwargs: None)
    request = _device_request()
    with pytest.raises(HTTPException) as denied:
        asyncio.run(
            agent_service.agent(
                AgentRequest(messages=[{"role": "user", "content": "x"}], workspace=str(install_layout.install)),
                request,
            )
        )
    assert denied.value.status_code == 403
