"""Declarative slash-command registry for the unified chat REPL."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

from trinaxai_cli.commands import _system
from trinaxai_cli.commands.chat_state import ChatState


@dataclass(frozen=True)
class SlashContext:
    """Dependencies supplied to a slash-command handler."""

    messages: list[dict[str, str]]
    client: Any
    ui: Any
    config: Any
    state: ChatState


SlashHandler = Callable[[str, SlashContext], int | None]


@dataclass(frozen=True)
class SlashCommand:
    """One command and all aliases that dispatch to the same handler."""

    names: tuple[str, ...]
    summary: str
    section: str
    handler: SlashHandler

    @property
    def canonical_name(self) -> str:
        return self.names[0]


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
    for index, (_, label) in enumerate(options, start=1):
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
    except Exception as exc:  # noqa: BLE001 - user-facing CLI boundary
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
        collection_id = str(item.get("id") or "")
        name = str(item.get("name") or collection_id)
        if wanted in {collection_id.casefold(), name.casefold()}:
            return collection_id
    return None


def _select_collection(client: Any, ui: Any, requested: str = "") -> str | None:
    try:
        collections = client.list_collections()
    except Exception as exc:  # noqa: BLE001 - user-facing CLI boundary
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


def _exit(_arg: str, _ctx: SlashContext) -> int:
    return 0


def _help(_arg: str, ctx: SlashContext) -> None:
    _slash_help(ctx.ui)


def _clear(_arg: str, ctx: SlashContext) -> None:
    ctx.messages.clear()
    ctx.ui.success("Conversation cleared.")


def _status(_arg: str, ctx: SlashContext) -> None:
    _system.run_service_action("status", ctx.ui, timeout=30)


def _index(arg: str, ctx: SlashContext) -> None:
    from trinaxai_cli.commands import index as index_cmd

    idx_args = SimpleNamespace(path=arg or ".", folder=None, collection="default", append=False)
    index_cmd.run(idx_args, None, ctx.ui, ctx.config)


def _model(arg: str, ctx: SlashContext) -> None:
    _configure_model(arg, ctx.client, ctx.ui, ctx.state)


def _rag(arg: str, ctx: SlashContext) -> None:
    selected = _select_collection(ctx.client, ctx.ui, arg)
    if selected:
        ctx.state.engine = "rag"
        ctx.state.forced_mode = "rag"
        ctx.state.collections = [selected]
        ctx.ui.success(f"RAG enabled with collection: {selected} | Model: {ctx.state.model or 'auto'}")


def _chat(_arg: str, ctx: SlashContext) -> None:
    ctx.state.engine = "ollama"
    ctx.state.forced_mode = "chat"
    ctx.state.web_mode = False
    ctx.state.research_mode = False
    ctx.state.collections = []
    ctx.ui.success(f"General chat pinned | Model: {ctx.state.model or 'auto'}")


def _auto(_arg: str, ctx: SlashContext) -> None:
    ctx.state.forced_mode = None
    ctx.state.web_mode = False
    ctx.state.research_mode = False
    ctx.ui.success("Automatic mode routing enabled. TrinaxAI picks the best mode per turn.")


def _agent(arg: str, ctx: SlashContext) -> None:
    ctx.state.forced_mode = "agent"
    approval = "auto-approve ON" if ctx.state.yolo else "confirm each action"
    ctx.ui.success(f"Agent mode pinned | Workspace: {ctx.state.workspace} | {approval}")
    ctx.state.pending_input = arg or None


def _web(arg: str, ctx: SlashContext) -> None:
    ctx.state.forced_mode = "web"
    ctx.state.web_mode = True
    ctx.state.research_mode = False
    ctx.ui.success("Web-search mode pinned.")
    ctx.state.pending_input = arg or None


def _research(arg: str, ctx: SlashContext) -> None:
    ctx.state.forced_mode = "deep_research"
    ctx.state.research_mode = True
    ctx.ui.success("Deep-research mode pinned.")
    ctx.state.pending_input = arg or None


def _workspace(arg: str, ctx: SlashContext) -> None:
    ctx.state.workspace = arg or "."
    ctx.state.agent_engine = None
    resolved = Path(ctx.state.workspace).expanduser().resolve()
    ctx.ui.success(f"Agent workspace set to: {resolved}")


def _yolo(_arg: str, ctx: SlashContext) -> None:
    ctx.state.yolo = not ctx.state.yolo
    ctx.ui.warn(
        "Agent auto-approve ENABLED — dangerous actions run without asking."
        if ctx.state.yolo
        else "Agent auto-approve disabled — actions ask for confirmation."
    )


def _memory(_arg: str, ctx: SlashContext) -> None:
    try:
        memories = ctx.client.list_memories()
    except Exception as exc:  # noqa: BLE001 - user-facing CLI boundary
        ctx.ui.error(f"memory: {exc}")
        return
    if not memories:
        ctx.ui.info("No memories stored yet.")
        return
    for item in memories[:20]:
        ctx.ui.print(f"  • {str(item.get('text') or '').strip()[:120]}")


def _collections(_arg: str, ctx: SlashContext) -> None:
    try:
        collections = ctx.client.list_collections()
    except Exception as exc:  # noqa: BLE001 - user-facing CLI boundary
        ctx.ui.error(f"collections: {exc}")
        return
    if not collections:
        ctx.ui.info("No collections yet. Index a folder with /index PATH.")
        return
    for item in collections:
        ctx.ui.print(f"  • {item.get('name') or item.get('id')}  (id: {item.get('id')})")


def _watch(_arg: str, ctx: SlashContext) -> None:
    try:
        status = ctx.client.watch_status()
    except Exception as exc:  # noqa: BLE001 - user-facing CLI boundary
        ctx.ui.error(f"watch: {exc}")
        return
    running = status.get("running")
    watching = ", ".join(status.get("watching") or []) or "nothing"
    ctx.ui.info(f"Watcher: {'running' if running else 'stopped'} · watching: {watching}")
    job = status.get("job") if isinstance(status.get("job"), dict) else {}
    if job.get("status") and job.get("status") != "idle":
        ctx.ui.info(f"Indexer: {job['status']} · queued: {int(job.get('pending_events') or 0)}")
    if job.get("last_error"):
        ctx.ui.error(f"Last watcher error: {job['last_error']}")


SLASH_COMMANDS: tuple[SlashCommand, ...] = (
    SlashCommand(("/help",), "Show this help", "session", _help),
    SlashCommand(("/exit", "/quit"), "Exit chat", "session", _exit),
    SlashCommand(("/clear",), "Clear the in-memory conversation", "session", _clear),
    SlashCommand(("/chat", "/general", "/ollama"), "General chat (isolated Ollama)", "modes", _chat),
    SlashCommand(("/agent",), "Agentic mode; optional inline task", "modes", _agent),
    SlashCommand(("/web",), "Web-search-grounded answer; optional query", "modes", _web),
    SlashCommand(("/research",), "Multi-pass deep research; optional query", "modes", _research),
    SlashCommand(("/rag",), "Ground answers on an indexed collection", "modes", _rag),
    SlashCommand(("/auto",), "Back to automatic mode routing", "modes", _auto),
    SlashCommand(("/model",), "Select an installed model and mode", "tools", _model),
    SlashCommand(("/workspace",), "Set the agent workspace", "tools", _workspace),
    SlashCommand(("/yolo",), "Toggle agent auto-approve (dangerous)", "tools", _yolo),
    SlashCommand(("/index",), "Index a folder", "tools", _index),
    SlashCommand(("/memory",), "List persistent memories", "tools", _memory),
    SlashCommand(("/collections",), "List indexed collections", "tools", _collections),
    SlashCommand(("/watch",), "Show the file-watcher status", "tools", _watch),
    SlashCommand(("/status",), "Show local service status", "tools", _status),
)


def _build_registry(commands: tuple[SlashCommand, ...]) -> dict[str, SlashCommand]:
    registry: dict[str, SlashCommand] = {}
    for command in commands:
        for raw_name in command.names:
            name = raw_name.casefold()
            if name in registry:
                raise ValueError(f"Duplicate slash command alias: {raw_name}")
            registry[name] = command
    return registry


SLASH_REGISTRY = _build_registry(SLASH_COMMANDS)


def _slash_help(ui: Any) -> None:
    """Render stable help while the registry remains the source of commands."""
    ui.print(
        "\n".join(
            [
                "Slash commands:",
                "  /help              Show this help",
                "  /exit              Exit chat",
                "  /clear             Clear the in-memory conversation",
                "",
                "  Modes (auto-detected each turn, or pin one):",
                "  /chat              General chat (isolated Ollama)",
                "  /agent (task)      Agentic mode: read/write/run code in a workspace",
                "  /web (query)       Web-search-grounded answer",
                "  /research (query)  Multi-pass deep research",
                "  /rag (collection)  Ground answers on an indexed collection",
                "  /general           Alias of /chat",
                "  /auto              Back to automatic mode routing",
                "",
                "  Tools & session:",
                "  /model             Select an installed model and Ollama/RAG mode",
                "  /model NAME MODE   Set directly, e.g. /model qwen2.5-coder:1.5b rag",
                "  /workspace (path)  Set the agent workspace (default: current dir)",
                "  /yolo              Toggle agent auto-approve (dangerous)",
                "  /index (path)      Index a folder, default: current directory",
                "  /memory            List persistent memories",
                "  /collections       List indexed collections",
                "  /watch             Show the file-watcher status",
                "  /status            Show local service status",
            ]
        )
    )


def handle_slash(
    command: str,
    messages: list[dict[str, str]],
    client: Any,
    ui: Any,
    config: Any,
    state: ChatState,
) -> tuple[bool, int | None]:
    """Dispatch one slash command through :data:`SLASH_REGISTRY`."""
    if command.strip() == "/":
        _slash_help(ui)
        return True, None
    parts = command.strip().split(maxsplit=1)
    if not parts:
        return False, None
    registered = SLASH_REGISTRY.get(parts[0].casefold())
    if registered is None:
        return False, None
    arg = parts[1].strip() if len(parts) > 1 else ""
    context = SlashContext(messages=messages, client=client, ui=ui, config=config, state=state)
    return True, registered.handler(arg, context)
