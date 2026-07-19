"""``trinaxai agent`` — agentic assistant that reads, writes and runs code.

Local-first by design: the agent uses file and shell
tools in :mod:`trinaxai_cli.agent` to accomplish a task, asking for confirmation
before every dangerous action (write / edit / shell) unless ``--yolo`` is set.

Interactive REPL by default; ``--prompt`` runs a single task and exits. The
agent operates on ``--workspace`` (default: the current directory) and cannot
touch anything outside it.
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import config as runtime_config
from trinaxai_cli.agent import AgentEngine, Tool
from trinaxai_cli.commands import _system
from trinaxai_cli.session import Session

_DANGER_HINT = {
    "write_file": "will create/overwrite a file",
    "edit_file": "will modify a file",
    "run_command": "will run a shell command",
}


def _new_session_name() -> str:
    return f"agent-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"


def _resolve_model(args: Any, config: Any = None, text: str = "") -> str:
    requested = getattr(args, "model", None)
    if requested:
        return requested
    router_config = config if callable(getattr(config, "route_model", None)) else runtime_config
    if text:
        selected = router_config.route_model(text)
        if selected == getattr(router_config, "MODEL_CODE", None):
            return getattr(router_config, "MODEL_GENERAL", None) or getattr(router_config, "MODEL_DEEP", selected)
        return selected
    # The general model reliably emits native tool calls. A separate deep coder
    # model audits evidence-based review answers after the files have been read.
    return (
        _system.env_value("TRINAXAI_MODEL_GENERAL")
        or _system.env_value("TRINAXAI_MODEL_DEEP")
        or _system.env_value("TRINAXAI_MODEL_CODE")
        or "qwen3.5:4b"
    )


def _resolve_verifier_model() -> str | None:
    return _system.env_value("TRINAXAI_MODEL_DEEP") or _system.env_value("TRINAXAI_MODEL_CODE")


def _format_args(args: dict[str, Any]) -> str:
    parts = []
    for key, value in args.items():
        text = str(value).replace("\n", "\\n")
        if len(text) > 80:
            text = text[:77] + "..."
        parts.append(f"{key}={text}")
    return ", ".join(parts)


def _preview_dangerous(ui: Any, tool: Tool, args: dict[str, Any]) -> None:
    """Show what a dangerous action will do before asking to confirm."""
    if tool.name == "write_file":
        content = str(args.get("content", ""))
        ui.print(f"  → write {args.get('path', '?')} ({len(content)} chars)")
        ui.code("\n".join(content.splitlines()[:20]) or "(empty)")
    elif tool.name == "edit_file":
        ui.print(f"  → edit {args.get('path', '?')}")
        ui.code(f"- {str(args.get('old', ''))[:400]}\n+ {str(args.get('new', ''))[:400]}", "diff")
    elif tool.name == "run_command":
        ui.print("  → run command:")
        ui.code(str(args.get("command", "")), "bash")


def _make_callbacks(ui: Any, yolo: bool) -> dict[str, Any]:
    def on_tool_start(tool: Tool, args: dict[str, Any]) -> None:
        marker = "[!]" if tool.dangerous else "[*]"
        ui.print(f"{marker} {tool.name}({_format_args(args)})")

    def on_tool_result(tool: Tool, result: str) -> None:
        first = result.splitlines()[0] if result else ""
        ui.print(f"    {first[:160]}")

    def on_confirm(tool: Tool, args: dict[str, Any]) -> bool:
        if yolo:
            return True
        _preview_dangerous(ui, tool, args)
        hint = _DANGER_HINT.get(tool.name, "will run a side-effecting action")
        return ui.confirm(f"Allow {tool.name}? ({hint})", default=False)

    def on_token(text: str) -> None:
        ui.print(text, end="")

    return {
        "on_tool_start": on_tool_start,
        "on_tool_result": on_tool_result,
        "on_confirm": None if yolo else on_confirm,
        "on_token": on_token,
    }


def make_dynamic_callbacks(ui: Any, yolo_getter: Any) -> dict[str, Any]:
    """Callbacks whose auto-approve state is read live from ``yolo_getter()``.

    Used by the unified REPL where ``/yolo`` toggles approval mid-session, so we
    cannot bake the flag in at engine-construction time the way the dedicated
    ``trinaxai agent`` subcommand does.
    """

    def on_tool_start(tool: Tool, args: dict[str, Any]) -> None:
        marker = "[!]" if tool.dangerous else "[*]"
        ui.print(f"{marker} {tool.name}({_format_args(args)})")

    def on_tool_result(tool: Tool, result: str) -> None:
        first = result.splitlines()[0] if result else ""
        ui.print(f"    {first[:160]}")

    def on_confirm(tool: Tool, args: dict[str, Any]) -> bool:
        if yolo_getter():
            return True
        _preview_dangerous(ui, tool, args)
        hint = _DANGER_HINT.get(tool.name, "will run a side-effecting action")
        return ui.confirm(f"Allow {tool.name}? ({hint})", default=False)

    def on_token(text: str) -> None:
        ui.print(text, end="")

    return {
        "on_tool_start": on_tool_start,
        "on_tool_result": on_tool_result,
        # Always route through on_confirm; it consults yolo_getter() each call.
        "on_confirm": on_confirm,
        "on_token": on_token,
    }


def build_agent_engine(
    ui: Any,
    *,
    workspace: str | None = None,
    model: str | None = None,
    max_steps: int = 25,
    num_ctx: int | None = None,
    config: Any = None,
    callbacks: dict[str, Any] | None = None,
) -> AgentEngine:
    """Construct an :class:`AgentEngine` for the REPL or the subcommand.

    ``callbacks`` lets the caller supply dynamic (live-yolo) callbacks; when
    omitted, static confirming callbacks are used.
    """
    root = Path(workspace or ".").expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"workspace does not exist or is not a directory: {root}")
    ollama_url = _system.env_value("OLLAMA_BASE_URL") or "http://localhost:11434"
    resolved_model = model or _resolve_model(SimpleNamespace(model=model))
    resolved_ctx = num_ctx if num_ctx is not None else _resolve_num_ctx(config)
    cbs = callbacks if callbacks is not None else _make_callbacks(ui, False)
    return AgentEngine(
        model=resolved_model,
        verifier_model=_resolve_verifier_model(),
        workspace_root=root,
        ollama_url=ollama_url,
        max_steps=max_steps,
        num_ctx=resolved_ctx,
        **cbs,
    )


def _resolve_num_ctx(config: Any) -> int:
    """Agent context window: roomy enough for tool transcripts, capped for CPU.

    Falls back to a sane default when config lacks NUM_CTX. Env override wins.
    """
    override = _system.env_value("TRINAXAI_AGENT_NUM_CTX")
    if override:
        try:
            return max(2048, min(int(override), 131072))
        except ValueError:
            pass
    configured = int(getattr(config, "NUM_CTX", 8192) or 8192)
    return max(8192, min(configured, 16384))


def _build_engine(args: Any, ui: Any, yolo: bool, config: Any = None) -> AgentEngine:
    invocation_cwd = Path(getattr(args, "invocation_cwd", None) or ".").expanduser().resolve()
    requested = Path(getattr(args, "workspace", None) or ".").expanduser()
    workspace = (requested if requested.is_absolute() else invocation_cwd / requested).resolve()
    if not workspace.is_dir():
        raise ValueError(f"workspace does not exist or is not a directory: {workspace}")
    ollama_url = _system.env_value("OLLAMA_BASE_URL") or "http://localhost:11434"
    max_steps = int(getattr(args, "max_steps", None) or 25)
    callbacks = _make_callbacks(ui, yolo)
    return AgentEngine(
        model=_resolve_model(args, config, getattr(args, "prompt", None) or ""),
        verifier_model=_resolve_verifier_model(),
        workspace_root=workspace,
        ollama_url=ollama_url,
        max_steps=max_steps,
        num_ctx=_resolve_num_ctx(config),
        **callbacks,
    )


def _run_task(engine: AgentEngine, ui: Any, messages: list[dict[str, Any]], task: str, session: Session) -> None:
    messages.append({"role": "user", "content": task})
    session.append("user", task)
    ui.print("")
    answer = engine.run(messages)
    ui.print("")
    session.append("assistant", answer)


def run(args: Any, client: Any, ui: Any, config: Any) -> int:
    yolo = bool(getattr(args, "yolo", False))
    try:
        engine = _build_engine(args, ui, yolo, config)
    except Exception as exc:  # noqa: BLE001 - surface setup errors cleanly
        ui.error(f"agent: {exc}")
        return 1

    session_name = getattr(args, "session", None) or _new_session_name()
    messages: list[dict[str, Any]] = []

    with Session(session_name) as session:
        prompt = getattr(args, "prompt", None)
        if prompt:
            try:
                _run_task(engine, ui, messages, prompt, session)
            except Exception as exc:  # noqa: BLE001
                ui.error(f"agent: {exc}")
                return 1
            return 0

        ui.clear()
        ui.set_title("TrinaxAI Agent")
        ui.banner()
        ui.panel(
            "\n".join(
                [
                    "TrinaxAI Agent — local-first coding agent.",
                    "",
                    f"Workspace: {engine.workspace_root}",
                    f"Model: {engine.model}" + ("  (yolo: auto-approve)" if yolo else ""),
                    "",
                    "Describe a task and the agent will read, write and run code to do it.",
                    "Dangerous actions ask for confirmation unless you passed --yolo.",
                    "",
                    "Commands:  /exit  quit   ·   /clear  reset conversation",
                ]
            ),
            title="TrinaxAI Agent",
        )
        while True:
            try:
                task = ui.prompt("agent")
            except (EOFError, KeyboardInterrupt):
                ui.info("\nbye.")
                return 0
            if not task:
                continue
            lowered = task.strip().lower()
            if lowered in {"/exit", "/quit", "exit", "quit"}:
                ui.info("bye.")
                return 0
            if lowered == "/clear":
                messages.clear()
                ui.success("Conversation cleared.")
                continue
            try:
                engine.model = _resolve_model(args, config, task)
                _run_task(engine, ui, messages, task, session)
            except KeyboardInterrupt:
                ui.warn("\ninterrupted.")
                continue
            except Exception as exc:  # noqa: BLE001
                ui.error(f"agent: {exc}")
                ui.info("Is TrinaxAI running? Start it with: trinaxai start")
                continue
    return 0
