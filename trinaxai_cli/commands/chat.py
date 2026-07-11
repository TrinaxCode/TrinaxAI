"""``trinaxai chat`` — interactive REPL or single-shot prompt.

Without arguments starts a REPL. With ``--prompt`` runs a single request.
The ``Session`` class in :mod:`trinaxai_cli.session` persists every exchange
to ``~/.local/share/trinaxai/sessions/<name>.jsonl``.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

from trinaxai_cli.commands import _system
from trinaxai_cli.session import Session


def new_session_name() -> str:
    """Create a sortable ID so separate CLI launches never share a chat log."""
    return f"chat-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"


@dataclass
class ChatState:
    engine: str = "ollama"
    collections: list[str] = field(default_factory=list)
    model: str | None = None


def _stream_from_rag(
    client: Any,
    ui: Any,
    messages: list[dict[str, str]],
    collections: list[str] | None = None,
    model: str | None = None,
) -> str:
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "collections": collections or [],
    }
    full = ""
    started = False
    with ui.thinking() as ready:
        with client._client.stream("POST", "/v1/chat/completions", json=payload, timeout=120.0) as response:  # noqa: SLF001
            if response.status_code >= 400:
                detail = response.read().decode("utf-8", errors="replace")[:200]
                raise RuntimeError(f"chat: HTTP {response.status_code} — {detail}")
            for line in response.iter_lines():
                text = line.strip()
                if not text or not text.startswith("data: "):
                    continue
                data = text[6:]
                if data == "[DONE]":
                    break
                try:
                    parsed = json.loads(data)
                except json.JSONDecodeError:
                    continue
                error = parsed.get("trinaxai_error")
                if error:
                    raise RuntimeError(str(error))
                token = (((parsed.get("choices") or [{}])[0].get("delta") or {}).get("content") or "")
                if token:
                    if not started:
                        ready()
                        ui.print("trinaxai: ", end="")
                        started = True
                    full += token
                    ui.print(token, end="")
    ui.print("")
    return full or "(no answer)"


def _general_system_prompt() -> str:
    return (
        "You are TrinaxAI, a fast local AI assistant. Answer the current request directly "
        "and in the same language as the user's latest message. Keep simple greetings brief. "
        "Use only messages from this conversation; never assume facts from other chats or indexed documents. "
        "Do not invent personal details, credentials, projects, or links that the user did not mention here."
    )


def _stream_from_ollama(client: Any, ui: Any, messages: list[dict[str, str]], model: str | None = None) -> str:
    """Stream a context-isolated general chat directly from Ollama."""
    base_url = _system.env_value("OLLAMA_BASE_URL") or "http://localhost:11434"
    selected_model = model or _system.env_value("TRINAXAI_MODEL_GENERAL") or "qwen3:4b-instruct-2507-q4_K_M"
    payload = {
        "model": selected_model,
        "messages": [{"role": "system", "content": _general_system_prompt()}, *messages],
        "stream": True,
        "keep_alive": _system.env_value("TRINAXAI_KEEP_ALIVE") or "30m",
    }
    full = ""
    started = False
    with ui.thinking() as ready:
        with client.stream_ollama(base_url, payload, timeout=120.0) as response:
            if response.status_code >= 400:
                detail = response.read().decode("utf-8", errors="replace")[:200]
                raise RuntimeError(f"ollama: HTTP {response.status_code} — {detail}")
            for line in response.iter_lines():
                if not line.strip():
                    continue
                try:
                    parsed = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if parsed.get("error"):
                    raise RuntimeError(str(parsed["error"]))
                token = str((parsed.get("message") or {}).get("content") or "")
                if token:
                    if not started:
                        ready()
                        ui.print("trinaxai: ", end="")
                        started = True
                    full += token
                    ui.print(token, end="")
                if parsed.get("done"):
                    break
    ui.print("")
    return full or "(no answer)"


def _resolve_engine(args: Any, config: Any, collections: list[str]) -> str:
    requested = getattr(args, "engine", None)
    engine = requested or ("rag" if collections else getattr(config, "engine", "ollama"))
    return "ollama" if engine == "general" else engine


def _stream_answer(
    client: Any,
    ui: Any,
    messages: list[dict[str, str]],
    engine: str,
    collections: list[str],
    model: str | None,
) -> str:
    if engine == "rag":
        return _stream_from_rag(client, ui, messages, collections, model)
    return _stream_from_ollama(client, ui, messages, model)


def _slash_help(ui: Any) -> None:
    ui.print(
        "\n".join(
            [
                "Slash commands:",
                "  /help              Show this help",
                "  /exit              Exit chat",
                "  /clear             Clear in-memory conversation",
                "  /model             Select an installed model and Ollama/RAG mode",
                "  /model NAME MODE   Set directly, for example: /model qwen2.5-coder:3b rag",
                "  /rag COLLECTION    Select a PWA collection and enable RAG",
                "  /general           Switch back to isolated Ollama chat",
                "  /index [path]      Index a folder, default: current directory",
                "  /status            Show local service status",
            ]
        )
    )


def _chat_capable_models(models: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    for item in models:
        name = str(item.get("name") or "").strip()
        lowered = name.lower()
        if not name or "embed" in lowered or lowered.startswith("bge-"):
            continue
        names.append(name)
    return sorted(set(names), key=str.casefold)


def _numbered_choice(ui: Any, title: str, options: list[tuple[str, str]]) -> str | None:
    if not options:
        ui.warn(f"No options available for {title}.")
        return None
    ui.print(title)
    for index, (value, label) in enumerate(options, start=1):
        ui.print(f"  {index}) {label}")
    raw = ui.prompt("Select number (or q to cancel)").strip()
    if raw.lower() in {"q", "quit", "cancel", "0", ""}:
        return None
    if raw.isdigit() and 1 <= int(raw) <= len(options):
        return options[int(raw) - 1][0]
    for value, label in options:
        if raw.casefold() in {value.casefold(), label.casefold()}:
            return value
    ui.warn(f"Invalid selection: {raw}")
    return None


def _installed_models(client: Any, ui: Any) -> list[str]:
    base_url = _system.env_value("OLLAMA_BASE_URL") or "http://localhost:11434"
    try:
        return _chat_capable_models(client.list_ollama_models(base_url))
    except Exception as exc:
        ui.error(f"Cannot list Ollama models: {exc}")
        ui.info("Start TrinaxAI with: trinaxai start")
        return []


def _resolve_model_name(requested: str, installed: list[str]) -> str | None:
    exact = next((name for name in installed if name.casefold() == requested.casefold()), None)
    if exact:
        return exact
    base_matches = [name for name in installed if name.split(":", 1)[0].casefold() == requested.casefold()]
    return base_matches[0] if len(base_matches) == 1 else None


def _select_model(client: Any, ui: Any, requested: str = "") -> str | None:
    installed = _installed_models(client, ui)
    if not installed:
        return None
    if requested:
        selected = _resolve_model_name(requested, installed)
        if selected is None:
            ui.warn(f"Model is not installed or is not chat-capable: {requested}")
        return selected
    return _numbered_choice(ui, "Installed TrinaxAI models:", [(name, name) for name in installed])


def _select_engine(ui: Any, requested: str = "") -> str | None:
    normalized = requested.strip().lower()
    aliases = {"general": "ollama", "ollama": "ollama", "rag": "rag"}
    if normalized:
        selected = aliases.get(normalized)
        if selected is None:
            ui.warn("Mode must be 'ollama', 'general', or 'rag'.")
        return selected
    return _numbered_choice(
        ui,
        "Use this model in:",
        [
            ("ollama", "General / Ollama (isolated, no indexed context)"),
            ("rag", "RAG (uses one PWA collection)"),
        ],
    )


def _resolve_collection(requested: str, collections: list[dict[str, Any]]) -> str | None:
    wanted = requested.casefold()
    for item in collections:
        cid = str(item.get("id") or "")
        name = str(item.get("name") or cid)
        if wanted in {cid.casefold(), name.casefold()}:
            return cid
    return None


def _select_collection(client: Any, ui: Any, requested: str = "") -> str | None:
    try:
        collections = client.list_collections()
    except Exception as exc:
        ui.error(f"Cannot list PWA collections: {exc}")
        ui.info("Make sure the TrinaxAI RAG service is running.")
        return None
    if not collections:
        ui.warn("No PWA collections exist yet. Create or index one first.")
        return None
    if requested:
        selected = _resolve_collection(requested, collections)
        if selected is None:
            ui.warn(f"Collection not found: {requested}")
        return selected
    options = [
        (str(item.get("id") or ""), f"{item.get('name') or item.get('id')} (id: {item.get('id')})")
        for item in collections
        if item.get("id")
    ]
    return _numbered_choice(ui, "PWA collections available for RAG:", options)


def _configure_model(command_arg: str, client: Any, ui: Any, state: ChatState) -> None:
    parts = command_arg.split()
    selected_model = _select_model(client, ui, parts[0] if parts else "")
    if selected_model is None:
        return
    selected_engine = _select_engine(ui, parts[1] if len(parts) > 1 else "")
    if selected_engine is None:
        return
    selected_collection: str | None = None
    if selected_engine == "rag":
        selected_collection = _select_collection(client, ui)
        if selected_collection is None:
            return
    state.model = selected_model
    state.engine = selected_engine
    state.collections = [selected_collection] if selected_collection else []
    detail = f"RAG collection: {selected_collection}" if selected_collection else "isolated general chat"
    ui.success(f"Model: {state.model} | Mode: {state.engine} | {detail}")


def _handle_slash(
    command: str,
    messages: list[dict[str, str]],
    client: Any,
    ui: Any,
    config: Any,
    state: ChatState,
) -> tuple[bool, int | None]:
    parts = command.strip().split(maxsplit=1)
    name = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""
    if name in {"/exit", "/quit"}:
        return True, 0
    if name == "/help":
        _slash_help(ui)
        return True, None
    if name == "/clear":
        messages.clear()
        ui.success("Conversation cleared.")
        return True, None
    if name == "/status":
        _system.run_service_action("status", ui, timeout=30)
        return True, None
    if name == "/index":
        from trinaxai_cli.commands import index as index_cmd

        idx_args = SimpleNamespace(path=arg or ".", folder=None, collection="default", append=False)
        index_cmd.run(idx_args, None, ui, config)
        return True, None
    if name == "/model":
        _configure_model(arg, client, ui, state)
        return True, None
    if name == "/rag":
        selected = _select_collection(client, ui, arg)
        if selected:
            state.engine = "rag"
            state.collections = [selected]
            ui.success(f"RAG enabled with collection: {selected} | Model: {state.model or 'auto'}")
        return True, None
    if name in {"/general", "/ollama"}:
        state.engine = "ollama"
        state.collections = []
        ui.success(f"General Ollama chat enabled | Model: {state.model or 'auto'}")
        return True, None
    return False, None


def run(args: Any, client: Any, ui: Any, config: Any) -> int:
    session_name = getattr(args, "session", None) or new_session_name()
    collections = getattr(args, "collections", None) or []
    if isinstance(collections, str):
        collections = [c.strip() for c in collections.split(",") if c.strip()]
    engine = _resolve_engine(args, config, collections)
    state = ChatState(engine=engine, collections=list(collections))

    with Session(session_name) as session:
        messages: list[dict[str, str]] = []

        prompt = getattr(args, "prompt", None)
        if prompt:
            messages.append({"role": "user", "content": prompt})
            session.append("user", prompt)
            try:
                answer = _stream_answer(client, ui, messages, state.engine, state.collections, state.model)
            except Exception as exc:
                ui.error(f"chat: {exc}")
                return 1
            session.append("assistant", answer)
            return 0

        ui.panel(
            "\n".join(
                [
                    "TrinaxAI CLI — your local-first AI assistant.",
                    "",
                    "Type a question to chat with the AI, or use these commands:",
                    "",
                    "  /help              Show slash commands",
                    "  /exit              Exit chat",
                    "  /clear             Clear conversation history",
                    "  /model             Select model and Ollama/RAG mode",
                    "  /rag               Select a PWA collection for RAG",
                    "  /general           Switch to isolated Ollama chat",
                    "  /index PATH        Index a folder into RAG (default: current dir)",
                    "  /status            Show local service status",
                    "",
                    "[bold]Quick start:[/]  trinaxai start   → starts services",
                    "               trinaxai index .  → indexes current folder",
                    "               trinaxai doctor   → health check",
                    "               trinaxai help     → full command list",
                ]
            ),
            title="Welcome to TrinaxAI",
        )
        ui.print("")
        ui.info(f"Session: {session_name} | Engine: {state.engine} | Type /help for commands, /exit or Ctrl-D to quit.")
        while True:
            try:
                user = ui.prompt("you")
            except (EOFError, KeyboardInterrupt):
                ui.info("\nbye.")
                return 0
            if not user:
                continue
            if user.strip().lower() in {"exit", "quit", "/exit", "/quit"}:
                ui.info("bye.")
                return 0
            if user.strip().startswith("/"):
                handled, exit_code = _handle_slash(user, messages, client, ui, config, state)
                if exit_code is not None:
                    ui.info("bye.")
                    return exit_code
                if handled:
                    continue
            messages.append({"role": "user", "content": user})
            session.append("user", user)
            try:
                answer = _stream_answer(client, ui, messages, state.engine, state.collections, state.model)
            except Exception as exc:
                ui.error(f"Cannot reach the local AI service: {exc}")
                ui.info("Start TrinaxAI with: trinaxai start")
                continue
            session.append("assistant", answer)
            messages.append({"role": "assistant", "content": answer})
    return 0
