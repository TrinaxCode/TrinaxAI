from __future__ import annotations

import queue
import threading
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.schemas import AgentCancelRequest, AgentRequest
from app.services import agent_service, web_search_service


def _request(identity: dict | None = None) -> SimpleNamespace:
    return SimpleNamespace(state=SimpleNamespace(trinaxai_identity=identity), query_params={"path": None})


def test_agent_shutdown_drops_active_sessions() -> None:
    session_id, _session = agent_service._register_session()
    agent_service.shutdown_runtime()
    assert session_id not in agent_service._SESSIONS


def test_agent_workspace_and_configuration_edges(monkeypatch, tmp_path: Path) -> None:
    real_resolve = Path.resolve

    def resolve(path, *args, **kwargs):
        if str(path) == "/broken":
            raise OSError("unreadable path")
        return real_resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolve)
    monkeypatch.setenv("TRINAXAI_AGENT_WORKSPACE_ROOTS", "/broken")
    monkeypatch.setattr(agent_service.config, "BASE_DIR", str(tmp_path))
    assert agent_service._configured_workspace_roots() == (tmp_path.resolve(),)

    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: tmp_path))
    with pytest.raises(HTTPException, match="No narrow agent project root"):
        agent_service._default_workspace((tmp_path, tmp_path / "Documents"))

    monkeypatch.setattr(agent_service.config, "NUM_CTX", 4096)
    monkeypatch.setenv("TRINAXAI_AGENT_NUM_CTX", "not-an-int")
    assert agent_service._agent_num_ctx() == 4096
    monkeypatch.setenv("TRINAXAI_AGENT_NUM_CTX", "200000")
    assert agent_service._agent_num_ctx() == 131072

    child = tmp_path / "child"
    child.mkdir()

    def resolve_child(path, *args, **kwargs):
        if path == child:
            raise OSError("resolve failed")
        return real_resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolve_child)
    monkeypatch.setenv("TRINAXAI_AGENT_WORKSPACE_ROOTS", str(tmp_path))
    with pytest.raises(HTTPException, match="Invalid workspace"):
        agent_service._resolve_workspace(str(child))
    fallback = tmp_path / "fallback"
    monkeypatch.setattr(agent_service, "_default_workspace", lambda _roots: fallback)
    monkeypatch.setattr(agent_service, "_read_app_state", lambda: {agent_service._AGENT_WORKSPACE_KEY: str(child)})
    assert agent_service._resolve_workspace("") == fallback

    monkeypatch.setattr(Path, "resolve", real_resolve)
    monkeypatch.setattr(agent_service, "_read_app_state", lambda: {agent_service._AGENT_WORKSPACE_KEY: str(tmp_path)})
    monkeypatch.setattr(agent_service, "_default_workspace", lambda _roots: fallback)
    assert agent_service._resolve_workspace("") == fallback
    agent_service._authorize_http_yolo(AgentRequest(messages=[{"role": "user", "content": "hello"}]), _request())


def test_agent_queue_terminal_and_session_edges(monkeypatch) -> None:
    session_id, session = agent_service._register_session()
    try:
        assert agent_service._discard_queued(object()) is None

        retained_queue = queue.Queue()
        retained_queue.put({"type": "done"})
        assert agent_service._discard_queued(retained_queue) == {"type": "done"}

        session["sentinel_queued"] = True
        assert not agent_service._queue_terminal(session, None)
        session["sentinel_queued"] = False
        session["terminal_event"] = {"type": "done"}
        assert not agent_service._queue_terminal(session, {"type": "error"})
        session["terminal_event"] = None
        session["closed"] = True
        assert not agent_service._queue_terminal(session, {"type": "error"})
        session["closed"] = False

        class AlwaysFull:
            def put_nowait(self, _item):
                raise queue.Full

            def get_nowait(self):
                raise queue.Empty

        session["queue"] = AlwaysFull()
        assert agent_service._queue_terminal(session, None)

        class RetainedFull:
            def __init__(self):
                self.calls = 0
                self.items = []

            def put_nowait(self, item):
                self.calls += 1
                if self.calls < 3:
                    raise queue.Full
                raise AttributeError("fallback queue")

            def get_nowait(self):
                if not self.items:
                    self.items.append({"type": "done"})
                    return self.items[0]
                raise queue.Empty

            def put(self, item):
                self.items.append(item)

        session["queue"] = RetainedFull()
        session["sentinel_queued"] = False
        assert agent_service._queue_terminal(session, None)
        assert session["queue"].items[-1] is None
    finally:
        agent_service._drop_session(session_id)

    class AttributeQueue:
        def __init__(self):
            self.items = []
            self.read = True

        def put_nowait(self, _item):
            raise AttributeError("not queue-like")

        def get_nowait(self):
            if self.read:
                self.read = False
                return {"type": "done"}
            raise queue.Empty

        def put(self, item):
            self.items.append(item)

    _, attr_session = agent_service._register_session()
    try:
        attr_session["queue"] = AttributeQueue()
        assert agent_service._queue_terminal(attr_session, {"type": "error"})
        assert attr_session["terminal_event"] == {"type": "done"}
        assert attr_session["queue"].items == [{"type": "done"}]
        attr_session["closed"] = True
        assert not agent_service._queue_event(attr_session, {"type": "token"})
    finally:
        agent_service._drop_session(attr_session["session_id"])

    anonymous = {"queue": queue.Queue(), "approvals": {}, "closed": True, "cancelled": threading.Event()}
    assert not agent_service._wait_for_approval(anonymous, SimpleNamespace(name="write_file"), {})

    approval_session_id, approval_session = agent_service._register_session()
    try:
        monkeypatch.setattr(agent_service, "_queue_event", lambda *_args, **_kwargs: False)
        assert not agent_service._wait_for_approval(approval_session, SimpleNamespace(name="write_file"), {})
        assert approval_session["approvals"] == {}
    finally:
        agent_service._drop_session(approval_session_id)

    assert agent_service._remove_session({}) is None


def test_agent_tools_report_retrieval_and_external_failures(monkeypatch) -> None:
    monkeypatch.setattr(agent_service, "_collection_scope", lambda _collections: (("missing",), "collection_not_found"))
    assert "Collection not found" in agent_service._search_knowledge(None, "query", collection_id="missing")

    monkeypatch.setattr(agent_service, "_collection_scope", lambda _collections: (("docs",), None))
    monkeypatch.setattr(agent_service.state, "fusion_retriever", object())
    monkeypatch.setattr(agent_service, "_retriever_for_collections", lambda _collections: None)
    assert "selected collection" in agent_service._search_knowledge(None, "query", collection_id="docs")

    monkeypatch.setattr(agent_service, "_collection_scope", lambda _collections: ((), None))
    empty_retriever = SimpleNamespace(retrieve=lambda _query: [])
    monkeypatch.setattr(agent_service.state, "fusion_retriever", empty_retriever)
    assert agent_service._search_knowledge(None, "query").startswith("No indexed passages")

    monkeypatch.setattr(web_search_service, "search_web", lambda _query: (_ for _ in ()).throw(ValueError("bad")))
    result = agent_service._web_search(None, "current question")
    assert "tool_status=degraded" in result


def test_agent_scope_and_capability_edges(monkeypatch, tmp_path: Path) -> None:
    assert agent_service._request_scopes(_request(None)) is None
    assert agent_service._request_scopes(_request({"scopes": "invalid"})) == frozenset()

    req = AgentRequest(
        messages=[{"role": "user", "content": "run a command"}],
        web_search=True,
        knowledge_search=True,
        deep_research=True,
    )
    monkeypatch.setattr(agent_service, "_bubblewrap_argv", lambda *_args: None)
    monkeypatch.setattr(agent_service.state, "fusion_retriever", object())
    names = agent_service._available_agent_tool_names(req, _request({"scopes": ["*"]}), tmp_path)
    assert "run_command" not in names


def test_agent_worker_runs_guard_and_handles_cancellation(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(agent_service, "_model_slots", nullcontext())
    monkeypatch.setattr(agent_service, "_inference_process_lock", nullcontext)

    class SuccessfulEngine:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def cancel(self):
            pass

        def run(self, _messages):
            session["closed"] = True
            assert self.kwargs["on_confirm"](SimpleNamespace(name="run_command"), {}) is False
            session["closed"] = False
            monkeypatch.setattr(agent_service, "_wait_for_approval", lambda *_args: True)
            assert self.kwargs["on_confirm"](SimpleNamespace(name="run_command"), {}) is True
            with self.kwargs["inference_guard"]():
                pass
            return "answer"

    session_id, session = agent_service._register_session()
    monkeypatch.setattr(agent_service, "AgentEngine", SuccessfulEngine)
    try:
        agent_service._run_engine_worker(
            session,
            AgentRequest(messages=[{"role": "user", "content": "hello"}]),
            tmp_path,
            "model",
        )
        assert session["queue"].get_nowait()["type"] == "done"
        assert session["queue"].get_nowait() is None
    finally:
        agent_service._drop_session(session_id)

    class CancelledEngine:
        def __init__(self, **_kwargs):
            pass

        def cancel(self):
            pass

        def run(self, _messages):
            raise agent_service.AgentCancelled()

    session_id, session = agent_service._register_session()
    monkeypatch.setattr(agent_service, "AgentEngine", CancelledEngine)
    try:
        agent_service._run_engine_worker(
            session,
            AgentRequest(messages=[{"role": "user", "content": "cancel"}]),
            tmp_path,
            "model",
        )
        assert session["queue"].get_nowait()["finish_reason"] == "cancelled"
    finally:
        agent_service._drop_session(session_id)


def test_agent_event_stream_handles_closed_timeout_and_status(monkeypatch, tmp_path: Path) -> None:
    class NoopThread:
        def __init__(self, *args, **kwargs):
            pass

        def start(self):
            pass

        def join(self, timeout=None):
            pass

    monkeypatch.setattr(agent_service.threading, "Thread", NoopThread)
    session_id, session = agent_service._register_session()
    session["closed"] = True
    try:
        stream = agent_service._agent_event_stream(
            session_id, session, AgentRequest(messages=[{"role": "user", "content": "hello"}]), tmp_path, "model"
        )
        assert next(stream) == "data: [DONE]\n\n"
    finally:
        stream.close()

    class ProbeQueue:
        def __init__(self):
            self.items = []
            self.calls = 0

        def put(self, item, timeout=None):
            self.items.append(item)

        def get(self, timeout=None):
            self.calls += 1
            if self.calls == 1:
                return self.items.pop(0)
            if self.calls == 2:
                raise queue.Empty
            return None

    session_id, session = agent_service._register_session()
    session["queue"] = ProbeQueue()
    monkeypatch.setattr(agent_service, "_AGENT_STATUS_INTERVAL_SECONDS", 0)
    try:
        stream = agent_service._agent_event_stream(
            session_id, session, AgentRequest(messages=[{"role": "user", "content": "hello"}]), tmp_path, "model"
        )
        assert '"type":"start"' in next(stream)
        assert '"type":"status"' in next(stream)
        assert next(stream) == "data: [DONE]\n\n"
    finally:
        stream.close()

    session_id, session = agent_service._register_session()
    session["queue"] = ProbeQueue()
    session["started_at"] = 0
    session["engine"] = SimpleNamespace(cancel=lambda: session.__setitem__("cancelled_by_engine", True))
    monkeypatch.setattr(agent_service, "_AGENT_MAX_SECONDS", 0)
    try:
        stream = agent_service._agent_event_stream(
            session_id, session, AgentRequest(messages=[{"role": "user", "content": "hello"}]), tmp_path, "model"
        )
        next(stream)
        assert '"type":"error"' in next(stream)
        assert session.get("cancelled_by_engine") is True
    finally:
        stream.close()


@pytest.mark.asyncio
async def test_agent_endpoint_and_cancel_pending_approval(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(agent_service, "_authorize_system", lambda _request: None)
    monkeypatch.setattr(agent_service, "_authorize_http_yolo", lambda *_args: None)
    monkeypatch.setattr(agent_service, "enforce_rate_limit", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(agent_service, "_resolve_workspace", lambda _workspace: tmp_path)
    monkeypatch.setattr(agent_service, "_resolve_model", lambda *_args: "model")
    monkeypatch.setattr(agent_service, "_agent_tools", lambda **_kwargs: ())
    request = _request({"kind": "device", "id": "device-a"})
    req = AgentRequest(messages=[{"role": "user", "content": "hello"}], workspace=str(tmp_path))
    response = await agent_service.agent(req, request)
    assert response.media_type == "text/event-stream"
    session_id = next(reversed(agent_service._SESSIONS))
    session = agent_service._SESSIONS[session_id]
    pending = {"event": threading.Event(), "approved": True}
    session["approvals"]["approval"] = pending
    result = await agent_service.agent_cancel(AgentCancelRequest(session_id=session_id), request)
    assert result == {"ok": True, "cancelled": True}
    assert pending["approved"] is False and pending["event"].is_set()
    agent_service._drop_session(session_id)


@pytest.mark.asyncio
async def test_agent_browse_handles_unreadable_children_and_permission(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    bad = root / "bad"
    bad.mkdir()
    monkeypatch.setattr(agent_service, "_authorize_system", lambda _request: None)
    monkeypatch.setattr(agent_service, "_browse_start_dir", lambda _path: root)
    monkeypatch.setattr(agent_service, "_configured_workspace_roots", lambda: (root,))
    real_resolve = Path.resolve

    def resolve_bad(path, *args, **kwargs):
        if path == bad:
            raise OSError("gone")
        return real_resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolve_bad)
    result = await agent_service.agent_browse(_request())
    assert result["directories"] == []

    monkeypatch.setattr(Path, "resolve", real_resolve)
    monkeypatch.setattr(agent_service, "_workspace_is_allowed", lambda *_args: False)
    assert (await agent_service.agent_browse(_request()))["directories"] == []
    monkeypatch.setattr(
        agent_service,
        "_workspace_is_allowed",
        lambda path, roots: any(path == root or root in path.parents for root in roots),
    )
    monkeypatch.setattr(agent_service.os, "access", lambda *_args: (_ for _ in ()).throw(OSError("access")))
    result = await agent_service.agent_browse(_request())
    assert result["directories"][0]["readable"] is False

    monkeypatch.setattr(Path, "iterdir", lambda _path: (_ for _ in ()).throw(PermissionError("denied")))
    with pytest.raises(HTTPException, match="Permission denied"):
        await agent_service.agent_browse(_request())


def test_agent_remaining_workspace_model_queue_and_approval_edges(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("TRINAXAI_AGENT_WORKSPACE_ROOTS", raising=False)
    monkeypatch.setattr(agent_service.config, "PROJECTS_DIRS", ("/", str(tmp_path)))
    monkeypatch.setattr(agent_service.config, "BASE_DIR", str(tmp_path))
    assert agent_service._configured_workspace_roots() == (tmp_path.resolve(),)

    monkeypatch.setattr(agent_service, "_configured_workspace_roots", lambda: ())
    with pytest.raises(HTTPException, match="workspace root"):
        agent_service._resolve_workspace("")

    monkeypatch.setattr(agent_service, "_configured_workspace_roots", lambda: (tmp_path,))
    monkeypatch.setattr(agent_service, "_read_app_state", lambda: (_ for _ in ()).throw(OSError("offline")))
    monkeypatch.setattr(agent_service, "_default_workspace", lambda _roots: tmp_path)
    assert agent_service._resolve_workspace("") == tmp_path

    monkeypatch.setattr(
        agent_service.config,
        "route_model_for_messages",
        lambda _messages: (_ for _ in ()).throw(RuntimeError("router unavailable")),
    )
    monkeypatch.setattr(agent_service.config, "MODEL_GENERAL", "general", raising=False)
    assert agent_service._resolve_model(None, [{"role": "user", "content": "hello"}]) == "general"

    class PutOnlyQueue:
        def __init__(self):
            self.items = []

        def put(self, item):
            self.items.append(item)

    put_only = PutOnlyQueue()
    session = {"queue": put_only, "closed": False, "cancelled": threading.Event()}
    assert agent_service._queue_event(session, {"type": "token"})
    assert put_only.items == [{"type": "token"}]

    session_id, approval_session = agent_service._register_session()
    try:
        monkeypatch.setattr(agent_service, "_APPROVAL_TIMEOUT_SECONDS", 0)
        assert not agent_service._wait_for_approval(approval_session, SimpleNamespace(name="write_file"), {})
        assert approval_session["queue"].qsize() == 2
        assert approval_session["queue"].get_nowait()["type"] == "approval_request"
        assert approval_session["queue"].get_nowait()["type"] == "approval_timeout"
    finally:
        agent_service._drop_session(session_id)


def test_agent_external_tool_output_edges(monkeypatch) -> None:
    monkeypatch.setattr(agent_service, "_collection_scope", lambda _collections: ((), None))
    monkeypatch.setattr(
        agent_service.state,
        "fusion_retriever",
        SimpleNamespace(
            retrieve=lambda _query: [
                SimpleNamespace(metadata={"rel_path": "docs/file.md"}, get_content=lambda: "x" * 601)
            ]
        ),
    )
    result = agent_service._search_knowledge(None, "query")
    assert "…" in result

    assert "web_search" in agent_service._web_search(None, "")
    from app.services.web_search_service import WebSearchError

    monkeypatch.setattr(
        web_search_service,
        "search_web",
        lambda _query: (_ for _ in ()).throw(WebSearchError("offline")),
    )
    assert "tool_status=degraded" in agent_service._web_search(None, "query")
    monkeypatch.setattr(web_search_service, "search_web", lambda _query: ([], "provider"))
    assert "no results" in agent_service._web_search(None, "query")
    monkeypatch.setattr(
        web_search_service,
        "search_web",
        lambda _query: ([{"title": "", "url": "https://example.test", "snippet": "x" * 601}], "provider"),
    )
    assert "…" in agent_service._web_search(None, "query")

    from app.services import research_service

    assert "deep_research" in agent_service._deep_research(None, "")
    monkeypatch.setattr(
        research_service,
        "_research_sync",
        lambda _request: {"error_code": "offline", "answer": "", "error_detail": "unavailable"},
    )
    assert "tool_status=degraded" in agent_service._deep_research(None, "query")
    monkeypatch.setattr(research_service, "_research_sync", lambda _request: {"answer": "fallback", "sources": []})
    assert "fallback" in agent_service._deep_research(None, "query")
