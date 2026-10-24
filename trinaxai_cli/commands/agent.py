"""``trinaxai agent`` — agentic assistant that reads, writes and runs code.

Local-first by design: the agent uses file and shell
tools in :mod:`trinaxai_agent` to accomplish a task, asking for confirmation
before every dangerous action (write / edit / shell) unless ``--yolo`` is set.

Interactive REPL by default; ``--prompt`` runs a single task and exits. The
agent operates on ``--workspace`` (default: the current directory) and cannot
touch anything outside it.
"""

from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from trinaxai import config as runtime_config
from trinaxai_agent import DEFAULT_TOOLS, AgentEngine, Tool, default_system_prompt, format_tool_failure
from trinaxai_cli.agent_ui import (
    TODO_PROMPT,
    AgentRenderer,
    ApprovalPolicy,
    TodoStore,
    build_todo_tool,
    load_project_instructions,
    normalize_mode,
)
from trinaxai_cli.commands import _system
from trinaxai_cli.i18n import text
from trinaxai_cli.session import Session

_DANGER_HINT = {
    "write_file": "will create/overwrite a file",
    "edit_file": "will modify a file",
    "run_command": "will run a shell command",
    "git": "will run git on this computer",
}


def _research_tool_text(result: Any) -> str:
    """Keep API research evidence compact enough for the agent context."""
    if not isinstance(result, dict):
        return str(result or "No result returned.")
    answer = str(result.get("answer") or "").strip()
    lines = [answer] if answer else []
    for index, source in enumerate(result.get("sources") or [], start=1):
        if not isinstance(source, dict):
            continue
        label = source.get("title") or source.get("file") or source.get("url") or "source"
        location = source.get("url") or source.get("file") or ""
        page = f" p. {source['page']}" if source.get("page") else ""
        lines.append(f"[{index}] {label}{page}\n{location}".strip())
    return "\n\n".join(lines) or "No evidence returned."


def build_api_tools(client: Any, collections: list[str] | None = None) -> tuple[Tool, ...]:
    """Add web/RAG/memory tools backed by the already-running TrinaxAI API."""
    default_collections = list(collections or [])

    def search_knowledge(_workspace_root: Path, query: str = "", collection_id: str = "", **_kwargs: Any) -> str:
        q = query.strip()
        if not q:
            return format_tool_failure("search_knowledge", "The query must not be empty.")
        scope = [collection_id.strip()] if collection_id.strip() else default_collections
        try:
            return _research_tool_text(client.research(q, collections=scope, depth=1, web_search=False))
        except Exception as exc:  # noqa: BLE001 - return a model-readable degraded tool result
            return format_tool_failure("search_knowledge", exc)

    def web_search(_workspace_root: Path, query: str = "", **_kwargs: Any) -> str:
        q = query.strip()
        if not q:
            return format_tool_failure("web_search", "The query must not be empty.", external=True)
        try:
            result = client.research(q, depth=1, web_search=True, search_query=q)
            return _research_tool_text(result)
        except Exception as exc:  # noqa: BLE001 - return a model-readable degraded tool result
            return format_tool_failure("web_search", exc, external=True)

    def deep_research(_workspace_root: Path, query: str = "", **_kwargs: Any) -> str:
        q = query.strip()
        if not q:
            return format_tool_failure("deep_research", "The query must not be empty.", external=True)
        try:
            result = client.research(q, depth=3, web_search=True, search_query=q)
            return _research_tool_text(result)
        except Exception as exc:  # noqa: BLE001 - return a model-readable degraded tool result
            return format_tool_failure("deep_research", exc, external=True)

    def search_memory(_workspace_root: Path, query: str = "", **_kwargs: Any) -> str:
        q = query.strip()
        if not q:
            return format_tool_failure("search_memory", "The query must not be empty.")
        try:
            memories = client.memory_context(q)
            return _research_tool_text({"answer": str(memories)})
        except Exception as exc:  # noqa: BLE001 - return a model-readable degraded tool result
            return format_tool_failure("search_memory", exc)

    def list_collections(_workspace_root: Path, **_kwargs: Any) -> str:
        try:
            return _research_tool_text({"answer": str(client.list_collections())})
        except Exception as exc:  # noqa: BLE001 - return a model-readable degraded tool result
            return format_tool_failure("list_collections", exc)

    api_tools = (
        Tool(
            name="search_knowledge",
            description="Search the user's indexed RAG documents for relevant passages.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "What to find in indexed documents."},
                    "collection_id": {"type": "string", "description": "Optional collection identifier."},
                },
                "required": ["query"],
            },
            handler=search_knowledge,
            dangerous=False,
        ),
        Tool(
            name="web_search",
            description="Search the public web for current or public facts and source URLs.",
            parameters={
                "type": "object",
                "properties": {"query": {"type": "string", "description": "The public web query."}},
                "required": ["query"],
            },
            handler=web_search,
            dangerous=False,
            external=True,
        ),
        Tool(
            name="deep_research",
            description="Run multi-pass web research for comparisons, detailed reports, or several sources.",
            parameters={
                "type": "object",
                "properties": {"query": {"type": "string", "description": "The research question."}},
                "required": ["query"],
            },
            handler=deep_research,
            dangerous=False,
            external=True,
        ),
        Tool(
            name="search_memory",
            description="Search saved user memories for personal context relevant to the request.",
            parameters={
                "type": "object",
                "properties": {"query": {"type": "string", "description": "The personal context to find."}},
                "required": ["query"],
            },
            handler=search_memory,
            dangerous=False,
        ),
        Tool(
            name="list_collections",
            description="List indexed RAG collections when a collection scope is unclear.",
            parameters={"type": "object", "properties": {}},
            handler=list_collections,
            dangerous=False,
        ),
    )
    return (*DEFAULT_TOOLS, *api_tools)


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


def _make_callbacks(
    ui: Any,
    yolo: bool,
    policy: ApprovalPolicy | None = None,
    renderer: AgentRenderer | None = None,
) -> dict[str, Any]:
    """Callbacks for the dedicated ``trinaxai agent`` command.

    ``yolo`` keeps its historical meaning: ``on_confirm`` is ``None`` so the engine
    never asks. Pass ``policy``/``renderer`` to share them with the REPL.
    """
    policy = policy or ApprovalPolicy(mode=normalize_mode(None, yolo=yolo))
    renderer = renderer or AgentRenderer(ui, policy)
    callbacks = renderer.callbacks()
    if yolo:
        callbacks["on_confirm"] = None
    return callbacks


def make_dynamic_callbacks(
    ui: Any,
    yolo_getter: Any,
    policy: ApprovalPolicy | None = None,
    renderer: AgentRenderer | None = None,
) -> dict[str, Any]:
    """Callbacks whose auto-approve state is read live from ``yolo_getter()``.

    Used by the unified REPL where ``/yolo`` toggles approval mid-session, so we
    cannot bake the flag in at engine-construction time the way the dedicated
    ``trinaxai agent`` subcommand does.
    """
    policy = policy or ApprovalPolicy()
    renderer = renderer or AgentRenderer(ui, policy)
    callbacks = renderer.callbacks()
    ask = renderer.on_confirm

    def on_confirm(tool: Tool, args: dict[str, Any]) -> bool:
        if yolo_getter():
            return True
        if policy.yolo:  # the toggle was switched off: fall back to asking
            policy.mode = "default"
        return ask(tool, args)

    # Always route through on_confirm; it consults yolo_getter() each call.
    callbacks["on_confirm"] = on_confirm
    return callbacks


def build_agent_engine(
    ui: Any,
    *,
    workspace: str | None = None,
    model: str | None = None,
    max_steps: int = 25,
    num_ctx: int | None = None,
    config: Any = None,
    callbacks: dict[str, Any] | None = None,
    tools: tuple[Tool, ...] | None = None,
    renderer: AgentRenderer | None = None,
    policy: ApprovalPolicy | None = None,
) -> AgentEngine:
    """Construct an :class:`AgentEngine` for the REPL or the subcommand.

    ``callbacks`` lets the caller supply dynamic (live-yolo) callbacks; when
    omitted they come from ``renderer`` (or a fresh confirming one). The engine
    also gets the ``todo_write`` checklist tool and any ``TRINAXAI.md`` /
    ``AGENTS.md`` / ``CLAUDE.md`` guidance found in the workspace.
    """
    root = Path(workspace or ".").expanduser().resolve()
    if not root.is_dir():
        raise ValueError(text("invalid_workspace", getattr(ui, "language", "en"), path=root))
    ollama_url = _system.env_value("OLLAMA_BASE_URL") or "http://localhost:11434"
    resolved_model = model or _resolve_model(SimpleNamespace(model=model))
    resolved_ctx = num_ctx if num_ctx is not None else _resolve_num_ctx(config)
    todos = TodoStore()
    if renderer is not None:
        renderer.workspace_root = root
        renderer.todos = todos
    if callbacks is not None:
        cbs = callbacks
    elif renderer is not None:
        cbs = renderer.callbacks()
    else:
        cbs = _make_callbacks(ui, False)
    instructions, project_files = load_project_instructions(root)
    base_tools = tools if tools is not None else DEFAULT_TOOLS
    engine = AgentEngine(
        model=resolved_model,
        verifier_model=_resolve_verifier_model(),
        workspace_root=root,
        ollama_url=ollama_url,
        max_steps=max_steps,
        num_ctx=resolved_ctx,
        tools=(*base_tools, build_todo_tool(todos)),
        system_prompt=default_system_prompt(root) + TODO_PROMPT + instructions,
        **cbs,
    )
    # Plain attributes: the CLI reads them for /status, /todos and Shift+Tab.
    engine.todos = todos
    engine.project_files = project_files
    engine.renderer = renderer
    engine.policy = policy
    return engine


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


def _task_from_args(args: Any) -> str:
    """Non-interactive task: ``--prompt``, positional words, then piped stdin."""
    prompt = getattr(args, "prompt", None)
    if prompt:
        return str(prompt)
    words = getattr(args, "task", None)
    if words:
        return " ".join(words)
    if getattr(args, "read_stdin", False):
        try:
            return sys.stdin.read(1_048_577)[:1_048_576].strip()
        except (OSError, ValueError):
            return ""
    return ""


def _build_engine(args: Any, ui: Any, yolo: bool, config: Any = None) -> AgentEngine:
    invocation_cwd = Path(getattr(args, "invocation_cwd", None) or ".").expanduser().resolve()
    requested = Path(getattr(args, "workspace", None) or ".").expanduser()
    workspace = (requested if requested.is_absolute() else invocation_cwd / requested).resolve()
    if not workspace.is_dir():
        raise ValueError(f"workspace does not exist or is not a directory: {workspace}")
    max_steps = int(getattr(args, "max_steps", None) or 25)
    mode = normalize_mode(getattr(args, "permission_mode", None), yolo=yolo)
    policy = ApprovalPolicy(mode=mode)
    one_shot = bool(_task_from_args_peek(args))
    output_format = str(getattr(args, "output_format", "text") or "text")
    # A task run from a script prints only the answer; progress chatter would
    # corrupt pipes and JSON consumers.
    quiet = output_format == "json" or (one_shot and not sys.stdout.isatty())
    renderer = AgentRenderer(
        ui,
        policy,
        workspace_root=workspace,
        quiet=quiet,
        interactive=sys.stdin.isatty() and output_format != "json",
    )
    return build_agent_engine(
        ui,
        workspace=str(workspace),
        model=_resolve_model(args, config, getattr(args, "prompt", None) or ""),
        max_steps=max_steps,
        num_ctx=_resolve_num_ctx(config),
        config=config,
        callbacks=renderer.callbacks() if not policy.yolo else _make_callbacks(ui, True, policy, renderer),
        renderer=renderer,
        policy=policy,
    )


def _task_from_args_peek(args: Any) -> bool:
    """True when the invocation carries a task (without consuming stdin)."""
    return bool(getattr(args, "prompt", None) or getattr(args, "task", None) or getattr(args, "read_stdin", False))


def _run_task(engine: AgentEngine, ui: Any, messages: list[dict[str, Any]], task: str, session: Session) -> str:
    """Run one turn with Claude-Code-style rollback when interrupted."""
    from trinaxai_cli.commands.agent_repl import run_turn

    return run_turn(engine, ui, messages, task, session)


def _load_resume(args: Any) -> tuple[str | None, list[dict[str, Any]]]:
    """Return ``(session_name, messages)`` for ``--resume`` / ``--continue``."""
    name = getattr(args, "resume", None)
    if not name and getattr(args, "continue_last", False):
        recent = Session.list_recent("agent-", limit=1)
        name = recent[0]["name"] if recent else None
    if not name:
        return None, []
    history = [
        {"role": record["role"], "content": str(record.get("content") or "")}
        for record in Session.load(name)
        if record.get("role") in {"user", "assistant"} and record.get("content")
    ]
    return name, history


def run(args: Any, client: Any, ui: Any, config: Any) -> int:
    yolo = bool(getattr(args, "yolo", False))
    try:
        engine = _build_engine(args, ui, yolo, config)
    except Exception as exc:  # noqa: BLE001 - surface setup errors cleanly
        ui.failure("Agent setup", exc)
        return 1

    resumed_name, messages = _load_resume(args)
    session_name = getattr(args, "session", None) or resumed_name or _new_session_name()
    task = _task_from_args(args)

    with Session(session_name) as session:
        if task:
            return _run_one_shot(engine, ui, messages, task, session, session_name, args)
        from trinaxai_cli.commands.agent_repl import run_repl

        return run_repl(args, client, ui, config, engine, session, session_name, messages, resumed=bool(resumed_name))


def _run_one_shot(
    engine: Any,
    ui: Any,
    messages: list[dict[str, Any]],
    task: str,
    session: Session,
    session_name: str,
    args: Any,
) -> int:
    started = time.monotonic()
    usage_before = dict(getattr(engine, "usage", {}) or {})
    try:
        answer = _run_task(engine, ui, messages, task, session)
    except KeyboardInterrupt:
        ui.warn("\ninterrupted.")
        return 130
    except Exception as exc:  # noqa: BLE001
        ui.failure("Agent task", exc)
        return 1
    degraded = getattr(engine, "completion_status", "complete") == "degraded"
    renderer = getattr(engine, "renderer", None)
    if getattr(args, "output_format", "text") == "json":
        usage = dict(getattr(engine, "usage", {}) or {})
        ui.say(
            json.dumps(
                {
                    "result": answer,
                    "status": "degraded" if degraded else "complete",
                    "session": session_name,
                    "model": getattr(engine, "model", ""),
                    "tool_calls": getattr(renderer, "tool_calls", 0),
                    "duration_s": round(time.monotonic() - started, 2),
                    "tokens": {
                        "prompt": usage.get("prompt", 0) - usage_before.get("prompt", 0),
                        "completion": usage.get("completion", 0) - usage_before.get("completion", 0),
                    },
                },
                ensure_ascii=False,
            )
        )
    elif renderer is not None and renderer.quiet:
        ui.say(answer)
    if degraded:
        ui.warn("Agent response is degraded: the model request failed, so the displayed answer may be incomplete.")
    return 0
