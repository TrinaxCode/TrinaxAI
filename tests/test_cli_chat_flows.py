from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from trinaxai_cli.commands import chat
from trinaxai_cli.commands import chat_slash as slash
from trinaxai_cli.commands.chat_state import ChatState
from trinaxai_cli.config import CLIConfig
from trinaxai_cli.router import RouteDecision


def _ui() -> MagicMock:
    ui = MagicMock()
    ui.thinking.return_value = nullcontext(lambda: None)
    ui.spinner.return_value = nullcontext()
    return ui


class _Response:
    def __init__(self, lines=(), *, status=200, body=b"") -> None:
        self.status_code = status
        self._lines = list(lines)
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def iter_lines(self):
        yield from self._lines

    def read(self):
        return self._body


def test_rag_stream_ignores_noise_and_reports_safe_protocol_errors() -> None:
    ui = _ui()
    response = _Response(
        [
            "",
            "event: ping",
            "data: not-json",
            'data: {"choices":[{"delta":{"content":"hello"}}]}',
            "data: [DONE]",
        ]
    )
    client = SimpleNamespace(_client=SimpleNamespace(stream=lambda *_args, **_kwargs: response))

    assert chat._stream_from_rag(client, ui, [], ["docs"], "model") == "hello"

    client._client.stream = lambda *_args, **_kwargs: _Response(status=503, body=b"backend unavailable")
    with pytest.raises(RuntimeError, match="HTTP 503"):
        chat._stream_from_rag(client, ui, [])

    client._client.stream = lambda *_args, **_kwargs: _Response(['data: {"trinaxai_error":"typed failure"}'])
    with pytest.raises(RuntimeError, match="typed failure"):
        chat._stream_from_rag(client, ui, [])


def test_ollama_stream_sends_identity_and_handles_provider_errors(monkeypatch) -> None:
    ui = _ui()
    client = MagicMock()
    monkeypatch.setattr(chat._system, "env_value", lambda _name: "")
    client.stream_ollama.return_value = _Response(['{"message":{"content":"model identity"},"done":true}'])
    assert chat._stream_from_ollama(client, ui, [{"role": "user", "content": "who are you"}]) == "model identity"
    assert client.stream_ollama.call_args.args[1]["think"] is False

    client.stream_ollama.return_value = _Response(["not-json", '{"done":true}'])
    assert chat._stream_from_ollama(client, ui, []) == "(no answer)"

    client.stream_ollama.return_value = _Response(['{"error":"model missing"}'])
    with pytest.raises(RuntimeError, match="model missing"):
        chat._stream_from_ollama(client, ui, [])


def test_stream_answer_survives_memory_failure_and_injects_creator_facts(monkeypatch) -> None:
    client = MagicMock()
    client.memory_context.side_effect = RuntimeError("memory offline")
    captured: dict = {}
    monkeypatch.setattr(
        chat,
        "_stream_from_rag",
        lambda _client, _ui, messages, collections, model: (
            captured.update(messages=messages, collections=collections, model=model) or "answer"
        ),
    )
    from trinaxai_cli import prompts

    monkeypatch.setattr(
        prompts,
        "creator_facts_message",
        lambda _messages: {"role": "system", "content": "Verified creator facts"},
    )

    answer = chat._stream_answer(
        client,
        _ui(),
        [{"role": "user", "content": "Who created this?"}],
        "rag",
        ["docs"],
        "model",
    )

    assert answer == "answer"
    assert captured["messages"][0]["role"] == "system"
    assert captured["collections"] == ["docs"]


def test_language_research_rendering_and_query_context(monkeypatch) -> None:
    ui = _ui()
    monkeypatch.setattr(chat.time, "strftime", lambda _format: "2026-07-26")
    result = {
        "answer": "Verified",
        "passes": 2,
        "model": "general",
        "web_provider": "brave",
        "sub_questions": ["one"],
        "sources": [{"file": "source.md", "page": 2}],
    }

    assert chat._detect_lang("¿Qué pasó?") == "es"
    assert chat._detect_lang("What happened?") == "en"
    assert chat._render_research(ui, result, web=True) == "Verified"
    query, context = chat._build_web_query(
        "latest season?",
        [
            {"role": "user", "content": "Fortnite"},
            {"role": "assistant", "content": "game"},
        ],
    )
    assert "2026-07-26" in query
    assert "official source" in query
    assert context == "User: Fortnite"


def test_web_research_reports_failure_and_success() -> None:
    ui = _ui()
    client = MagicMock()
    client.research.return_value = {"answer": "result"}

    assert (
        chat._run_web_or_research(
            client,
            ui,
            "current topic",
            [],
            mode="web",
            web_search=True,
            depth=1,
        )
        == "result"
    )

    client.research.side_effect = RuntimeError("offline")
    assert (
        chat._run_web_or_research(
            client,
            ui,
            "current topic",
            [],
            mode="web",
            web_search=True,
            depth=1,
        )
        == ""
    )
    ui.failure.assert_called()


def test_cd_validates_syntax_and_directory(tmp_path: Path) -> None:
    ui = _ui()
    state = ChatState(workspace=str(tmp_path))

    assert not chat._handle_cd("echo cd", state, ui)
    assert chat._handle_cd("cd 'unterminated", state, ui)
    assert chat._handle_cd("cd one two", state, ui)
    assert chat._handle_cd("cd missing", state, ui)
    assert ui.error.call_count == 3


def test_forced_modes_override_router() -> None:
    state = ChatState(forced_mode="deep_research", web_mode=True)

    route = chat._resolve_turn_mode("anything", state, CLIConfig(), [])

    assert route.source == "manual"
    assert route.mode == "deep_research"
    assert route.web_search is True
    assert route.depth == 3


class _Session:
    def __init__(self) -> None:
        self.rows: list[tuple] = []

    def append(self, *args) -> None:
        self.rows.append(args)


def test_dispatch_turn_covers_chat_web_agent_and_recovery(monkeypatch) -> None:
    ui = _ui()
    client = MagicMock()
    session = _Session()
    messages: list[dict[str, str]] = []
    state = ChatState(collections=["docs"])
    config = CLIConfig()
    route = lambda mode, **kwargs: RouteDecision(  # noqa: E731
        mode=mode,
        source=kwargs.get("source", "manual"),
        reason="test",
        web_search=kwargs.get("web_search", False),
        depth=kwargs.get("depth", 1),
        announce=kwargs.get("announce", False),
    )

    monkeypatch.setattr(chat, "_stream_answer", lambda *_args: "chat answer")
    chat._dispatch_turn("hello", route("chat"), messages, client, ui, config, state, session)
    assert messages[-1]["content"] == "chat answer"

    monkeypatch.setattr(chat, "_run_web_or_research", lambda *_args, **_kwargs: "web answer")
    chat._dispatch_turn(
        "latest",
        route("web", web_search=True, announce=True, source="rule"),
        messages,
        client,
        ui,
        config,
        state,
        session,
    )
    assert messages[-1]["content"] == "web answer"

    monkeypatch.setattr(chat, "_run_agent_turn", lambda *_args: "agent answer")
    chat._dispatch_turn("edit file", route("agent"), messages, client, ui, config, state, session)
    assert session.rows[-1][1] == "agent answer"

    monkeypatch.setattr(
        chat,
        "_stream_answer",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("offline")),
    )
    before = list(messages)
    chat._dispatch_turn("retry", route("chat"), messages, client, ui, config, state, session)
    assert messages == before
    ui.failure.assert_called()


def test_agent_turn_builds_engine_once(monkeypatch, tmp_path: Path) -> None:
    engine = SimpleNamespace(
        workspace_root=tmp_path,
        model="model",
        run=lambda messages: f"answer to {messages[-1]['content']}",
    )
    from trinaxai_cli.commands import agent as agent_cmd

    monkeypatch.setattr(agent_cmd, "make_dynamic_callbacks", lambda *_args: object())
    monkeypatch.setattr(agent_cmd, "build_agent_engine", lambda *_args, **_kwargs: engine)
    state = ChatState(workspace=str(tmp_path), model="model")
    ui = _ui()

    assert chat._run_agent_turn(state, MagicMock(), ui, "task", CLIConfig()) == "answer to task"
    assert chat._run_agent_turn(state, MagicMock(), ui, "again", CLIConfig()) == "answer to again"
    assert len(state.agent_messages) == 2


def test_agent_api_tools_keep_web_and_rag_scopes_distinct(tmp_path: Path) -> None:
    from trinaxai_cli.commands import agent as agent_cmd

    class Client:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        def research(self, query: str, **kwargs):
            self.calls.append({"query": query, **kwargs})
            return {"answer": "grounded answer", "sources": [{"file": "project.md", "page": 2}]}

        def memory_context(self, _query: str):
            return [{"text": "saved context"}]

        def list_collections(self):
            return [{"id": "docs"}]

    client = Client()
    tools = {tool.name: tool for tool in agent_cmd.build_api_tools(client, ["docs"])}

    tools["search_knowledge"].handler(tmp_path, query="when I made the project")
    tools["web_search"].handler(tmp_path, query="last Real Madrid match")
    tools["deep_research"].handler(tmp_path, query="compare several sources")

    assert client.calls[0]["web_search"] is False
    assert client.calls[0]["collections"] == ["docs"]
    assert client.calls[1]["web_search"] is True
    assert client.calls[2]["depth"] == 3


def test_slash_handlers_update_state_and_render_operational_data(monkeypatch, tmp_path: Path) -> None:
    ui = _ui()
    client = MagicMock()
    client.list_memories.return_value = [{"text": "Remember this"}]
    client.list_collections.return_value = [{"id": "docs", "name": "Docs"}]
    client.watch_status.return_value = {
        "running": True,
        "watching": ["/docs"],
        "job": {"status": "indexing", "pending_events": 2, "last_error": "retrying"},
    }
    messages = [{"role": "user", "content": "old"}]
    state = ChatState(
        workspace=str(tmp_path),
        agent_engine=object(),
        agent_messages=[{"role": "user", "content": "old agent context"}],
    )
    monkeypatch.setattr(slash._system, "run_service_action", lambda *_args, **_kwargs: 0)
    from trinaxai_cli.commands import index as index_cmd

    monkeypatch.setattr(index_cmd, "run", lambda *_args, **_kwargs: 0)

    for command in (
        f"/workspace {tmp_path}",
        "/clear",
        "/chat",
        "/auto",
        "/agent do work",
        "/research investigate",
        "/yolo",
        "/memory",
        "/collections",
        "/watch",
        "/status",
        "/index",
    ):
        handled, code = slash.handle_slash(command, messages, client, ui, CLIConfig(), state)
        assert handled and code is None
        if command.startswith("/workspace"):
            assert state.agent_engine is None
            assert state.agent_messages == []

    assert messages == []
    assert state.agent_messages == []
    assert state.yolo is True
    assert state.workspace == str(tmp_path)
    assert ui.print.called
    assert ui.error.called


def test_slash_selection_failures_are_actionable(monkeypatch) -> None:
    ui = _ui()
    ui.prompt.return_value = "invalid"
    client = MagicMock()
    client.list_ollama_models.side_effect = RuntimeError("offline")
    client.list_collections.side_effect = RuntimeError("offline")
    monkeypatch.setattr(slash._system, "env_value", lambda _name: "")

    assert slash._numbered_choice(ui, "Empty", []) is None
    assert slash._numbered_choice(ui, "Models", [("one", "One")]) is None
    assert slash._installed_models(client, ui) == []
    assert slash._select_collection(client, ui) is None
    assert slash._select_engine(ui, "invalid") is None
    assert slash._resolve_model_name("llama", ["llama:3b"]) == "llama:3b"
    assert slash._resolve_model_name("llama", ["llama:3b", "llama:8b"]) is None


def test_repl_handles_pending_slash_input_then_exit(monkeypatch) -> None:
    ui = _ui()
    ui.chat_prompt.side_effect = ["/web current topic", "/exit"]
    dispatched: list[str] = []

    class ContextSession(_Session):
        def __init__(self, _name):
            super().__init__()

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    monkeypatch.setattr(chat, "Session", ContextSession)
    monkeypatch.setattr(chat, "_welcome", lambda *_args: None)
    monkeypatch.setattr(
        chat,
        "_dispatch_turn",
        lambda user, *_args: dispatched.append(user),
    )

    result = chat.run(
        SimpleNamespace(
            session="test",
            collections=None,
            engine=None,
            workspace=None,
            prompt=None,
            invocation_cwd=".",
        ),
        MagicMock(),
        ui,
        CLIConfig(),
    )

    assert result == 0
    assert dispatched == ["current topic"]
    ui.reset_title.assert_called_once()
