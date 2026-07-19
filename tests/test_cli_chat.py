from __future__ import annotations

import json
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any, Iterator

from trinaxai_cli import prompts
from trinaxai_cli.commands import ask, chat
from trinaxai_cli.config import CLIConfig
from trinaxai_cli.ui import SlashCommandCompleter


def test_slash_command_completer_opens_on_slash_and_filters() -> None:
    from prompt_toolkit.completion import CompleteEvent
    from prompt_toolkit.document import Document

    completer = SlashCommandCompleter(
        (("/agent", "Agentic mode"), ("/auto", "Automatic routing"), ("/web", "Web search"))
    )
    all_names = [item.text for item in completer.get_completions(Document("/", cursor_position=1), CompleteEvent())]
    filtered = [item.text for item in completer.get_completions(Document("/ag", cursor_position=3), CompleteEvent())]

    assert all_names == ["/agent", "/auto", "/web"]
    assert filtered == ["/agent"]


def test_bare_slash_prints_the_command_menu() -> None:
    ui = FakeUI()

    handled, exit_code = chat._handle_slash("/", [], object(), ui, CLIConfig(), chat.ChatState())

    assert handled is True
    assert exit_code is None
    assert "Slash commands:" in ui.output
    assert "/research" in ui.output


class FakeResponse:
    status_code = 200

    def __init__(self, lines: list[str]) -> None:
        self.lines = lines

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *exc: Any) -> None:
        return None

    def iter_lines(self) -> Iterator[str]:
        yield from self.lines


def test_cli_identity_answers_are_complete_and_deterministic() -> None:
    identity = prompts.canonical_identity_answer([{"role": "user", "content": "quien eres"}])
    creator = prompts.canonical_identity_answer([{"role": "user", "content": "quien te creo"}])
    assert identity and "TrinaxAI" in identity and "github.com/TrinaxCode/TrinaxAI" in identity
    assert creator and "Full Stack Web Developer" in creator and "Tuxtla Gutiérrez" in creator


class FakeClient:
    def __init__(self, response: FakeResponse, *, models: list[dict[str, Any]] | None = None) -> None:
        self.response = response
        self.base_url = ""
        self.payload: dict[str, Any] = {}
        self.models = models or []
        self.collections = [
            {"id": "default", "name": "General Knowledge"},
            {"id": "code", "name": "Code Projects"},
        ]
        self.relevant_memories: list[dict[str, Any]] = []

    def stream_ollama(self, base_url: str, body: dict[str, Any], *, timeout: float) -> FakeResponse:
        self.base_url = base_url
        self.payload = body
        return self.response

    def list_ollama_models(self, base_url: str) -> list[dict[str, Any]]:
        self.base_url = base_url
        return self.models

    def list_collections(self) -> list[dict[str, Any]]:
        return self.collections

    def memory_context(self, _query: str) -> list[dict[str, Any]]:
        return self.relevant_memories


def test_rag_stream_payload_forces_knowledge_mode() -> None:
    response = FakeResponse(['data: {"choices":[{"delta":{"content":"ok"}}]}', "data: [DONE]"])
    client = FakeClient(response)
    client._client = SimpleNamespace(stream=lambda *args, **kwargs: response)

    chat._stream_from_rag(client, FakeUI(), [{"role": "user", "content": "marker"}], ["docs"])

    # Capture the shared constructor used by both ask and chat.
    def capture(_method, _path, **kwargs):
        client.payload = kwargs["json"]
        return response

    client._client.stream = capture
    chat._stream_from_rag(client, FakeUI(), [{"role": "user", "content": "marker"}], ["docs"])
    assert client.payload["mode"] == "knowledge"
    assert client.payload["collections"] == ["docs"]


def test_stream_answer_injects_only_relevant_memory_into_general_cli(monkeypatch) -> None:
    client = FakeClient(FakeResponse([json.dumps({"message": {"content": "ok"}, "done": True})]))
    client.relevant_memories = [{"id": "pref", "kind": "preference", "text": "Prefiere ejemplos en Python."}]
    ui = FakeUI()
    monkeypatch.setattr(chat._system, "env_value", lambda _key: "")

    chat._stream_answer(
        client,
        ui,
        [{"role": "user", "content": "Ayúdame"}],
        "ollama",
        [],
        None,
    )

    assert client.payload["messages"][1]["role"] == "system"
    assert "UNTRUSTED_MEMORY_DATA" in client.payload["messages"][1]["content"]
    assert "Prefiere ejemplos en Python" in client.payload["messages"][1]["content"]


class FakeUI:
    def __init__(self, answers: list[str] | None = None) -> None:
        self.output = ""
        self.thinking_started = 0
        self.thinking_stopped = 0
        self.answers = list(answers or [])
        self.successes: list[str] = []
        self.warnings: list[str] = []
        self.errors: list[str] = []

    @contextmanager
    def thinking(self, text: str = "TrinaxAI is thinking..."):
        self.thinking_started += 1
        stopped = False

        def stop() -> None:
            nonlocal stopped
            if not stopped:
                stopped = True
                self.thinking_stopped += 1

        try:
            yield stop
        finally:
            stop()

    def print(self, value: Any = "", *, end: str = "\n") -> None:
        self.output += f"{value}{end}"

    def assistant_label(self, name: str = "TrinaxAI") -> None:
        self.print("")
        self.print(f"● {name}")

    def prompt(self, question: str) -> str:
        return self.answers.pop(0)

    def success(self, value: str) -> None:
        self.successes.append(value)

    def warn(self, value: str) -> None:
        self.warnings.append(value)

    def error(self, value: str) -> None:
        self.errors.append(value)

    def info(self, value: str) -> None:
        self.output += f"{value}\n"


def test_general_chat_streams_and_stops_thinking_on_first_token(monkeypatch) -> None:
    lines = [
        json.dumps({"message": {"content": "¡Hola"}, "done": False}),
        json.dumps({"message": {"content": "!"}, "done": True}),
    ]
    client = FakeClient(FakeResponse(lines))
    ui = FakeUI()
    values = {
        "OLLAMA_BASE_URL": "http://ollama.test:11434",
        "TRINAXAI_MODEL_GENERAL": "llama-fast",
        "TRINAXAI_KEEP_ALIVE": "10m",
    }
    monkeypatch.setattr(chat._system, "env_value", lambda key: values.get(key, ""))

    answer = chat._stream_from_ollama(client, ui, [{"role": "user", "content": "hola"}])

    assert answer == "¡Hola!"
    assert ui.thinking_started == 1
    assert ui.thinking_stopped == 1
    assert ui.output == "\n● TrinaxAI\n¡Hola!\n"
    assert client.base_url == "http://ollama.test:11434"
    assert client.payload["model"] == "llama-fast"


def test_general_payload_contains_only_current_chat_messages(monkeypatch) -> None:
    client = FakeClient(FakeResponse([json.dumps({"message": {"content": "ok"}, "done": True})]))
    ui = FakeUI()
    monkeypatch.setattr(chat._system, "env_value", lambda key: "")
    current_chat = [
        {"role": "user", "content": "mi color es azul"},
        {"role": "assistant", "content": "entendido"},
        {"role": "user", "content": "¿cuál es mi color?"},
    ]

    chat._stream_from_ollama(client, ui, current_chat)

    sent = client.payload["messages"]
    assert sent[1:] == current_chat
    assert all("otro chat" not in message["content"] for message in sent)
    assert "otras conversaciones" in sent[0]["content"]


def test_default_engine_matches_pwa_general_chat() -> None:
    config = CLIConfig()
    assert config.api_verify_tls is True
    no_flags = SimpleNamespace(engine=None)
    assert config.engine == "ollama"
    assert chat._resolve_engine(no_flags, config, []) == "ollama"
    assert chat._resolve_engine(no_flags, config, ["docs"]) == "rag"
    assert chat._resolve_engine(SimpleNamespace(engine="general"), config, ["docs"]) == "ollama"


def test_ask_rag_uses_configured_default_collection(monkeypatch) -> None:
    config = CLIConfig(engine="rag", collections=["docs"], active_collection="docs")
    ui = FakeUI()
    captured: dict[str, Any] = {}

    def stream_answer(client, ui_arg, messages, engine, collections, model):
        captured.update(engine=engine, collections=collections)
        return "ok"

    monkeypatch.setattr(ask, "_stream_answer", stream_answer)
    result = ask.run(
        SimpleNamespace(prompt=["consulta"], collections=None, engine=None, session=None),
        object(),
        ui,
        config,
    )

    assert result == 0
    assert captured == {"engine": "rag", "collections": ["docs"]}


def test_new_cli_chats_get_isolated_session_names() -> None:
    first = chat.new_session_name()
    second = chat.new_session_name()
    assert first.startswith("chat-")
    assert second.startswith("chat-")
    assert first != second


def test_model_selector_uses_installed_chat_models_and_general_mode(monkeypatch) -> None:
    models = [
        {"name": "llama3.2:3b"},
        {"name": "qwen2.5-coder:3b"},
        {"name": "bge-m3:latest"},
    ]
    client = FakeClient(FakeResponse([]), models=models)
    ui = FakeUI(["2", "1"])
    state = chat.ChatState(engine="rag", collections=["code"])
    monkeypatch.setattr(chat._system, "env_value", lambda key: "")

    handled, exit_code = chat._handle_slash("/model", [], client, ui, CLIConfig(), state)

    assert handled is True and exit_code is None
    assert state.model == "qwen2.5-coder:3b"
    assert state.engine == "ollama"
    assert state.collections == []
    assert "bge-m3" not in ui.output


def test_model_selector_can_enable_rag_and_choose_pwa_collection(monkeypatch) -> None:
    client = FakeClient(FakeResponse([]), models=[{"name": "llama3.2:3b"}])
    ui = FakeUI(["1", "2", "2"])
    state = chat.ChatState()
    monkeypatch.setattr(chat._system, "env_value", lambda key: "")

    chat._handle_slash("/model", [], client, ui, CLIConfig(), state)

    assert state.model == "llama3.2:3b"
    assert state.engine == "rag"
    assert state.collections == ["code"]


def test_rag_command_asks_for_pwa_collection() -> None:
    client = FakeClient(FakeResponse([]))
    ui = FakeUI(["2"])
    state = chat.ChatState(engine="ollama")

    chat._handle_slash("/rag", [], client, ui, CLIConfig(), state)

    assert "PWA collections available for RAG" in ui.output
    assert state.engine == "rag"
    assert state.collections == ["code"]


def test_direct_model_and_rag_collection_commands(monkeypatch) -> None:
    client = FakeClient(FakeResponse([]), models=[{"name": "llama3.2:3b"}])
    ui = FakeUI(["1"])
    state = chat.ChatState()
    monkeypatch.setattr(chat._system, "env_value", lambda key: "")

    chat._handle_slash("/model llama3.2:3b rag", [], client, ui, CLIConfig(), state)
    chat._handle_slash("/rag Code Projects", [], client, ui, CLIConfig(), state)

    assert state.model == "llama3.2:3b"
    assert state.engine == "rag"
    assert state.collections == ["code"]


def test_slash_registry_has_unique_aliases_and_expected_public_commands() -> None:
    aliases = [alias for command in chat.SLASH_COMMANDS for alias in command.names]

    assert len(aliases) == len(set(aliases)) == len(chat.SLASH_REGISTRY)
    assert {"/help", "/chat", "/agent", "/web", "/research", "/rag", "/status"} <= set(aliases)
    assert chat.SLASH_REGISTRY["/general"] is chat.SLASH_REGISTRY["/chat"]


def test_slash_registry_dispatches_inline_prompt_and_rejects_unknown() -> None:
    client = FakeClient(FakeResponse([]))
    ui = FakeUI()
    state = chat.ChatState()

    handled, exit_code = chat._handle_slash("/web latest local AI news", [], client, ui, CLIConfig(), state)
    unknown, unknown_exit = chat._handle_slash("/does-not-exist", [], client, ui, CLIConfig(), state)

    assert handled is True and exit_code is None
    assert state.forced_mode == "web"
    assert state.pending_input == "latest local AI news"
    assert unknown is False and unknown_exit is None
