"""Interactive REPL for ``trinaxai agent`` (slash commands, turn control, status).

Split from :mod:`trinaxai_cli.commands.agent`, which owns engine construction and
the non-interactive paths. The REPL mirrors the Claude Code workflow:

* ``/help /clear /compact /model /mode /yolo /tools /status /todos /diff /init /resume /exit``
* ``@path`` mentions attach files, ``Shift+Tab`` cycles the permission mode,
  ``Alt+Enter`` adds a newline, ``Ctrl-C`` interrupts a running turn and rolls
  the conversation back to before the request.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from trinaxai_cli.agent_ui import (
    MODE_ACCEPT_EDITS,
    MODE_DEFAULT,
    MODE_PLAN,
    MODE_YOLO,
    PERMISSION_MODES,
    ApprovalPolicy,
    expand_file_mentions,
    render_todos,
)
from trinaxai_cli.session import Session

PLAN_SUFFIX = (
    "\n\n[Plan mode is ON: do not modify files or run commands. Investigate with read-only tools, "
    "then answer with a short numbered plan and wait for approval.]"
)

INIT_PROMPT = (
    "Analyze this workspace (README, manifests, directory layout, test setup) with the read-only tools and "
    "create a TRINAXAI.md at the root with: what the project is, how to run/test/lint/build it, the layout, "
    "and the conventions a new contributor must follow. Keep it under 80 lines and only state facts you verified."
)


def _t(ui: Any, en: str, es: str) -> str:
    return es if str(getattr(ui, "language", "en")).startswith("es") else en


# ------------------------------------------------------------------ one turn


def run_turn(engine: Any, ui: Any, messages: list[dict[str, Any]], task: str, session: Any | None) -> str:
    """Run one task. On Ctrl-C or failure the conversation is rolled back.

    Rolling back matters: an interrupted run would otherwise leave a user turn
    (or tool calls without results) in history and confuse the next request.
    """
    renderer = getattr(engine, "renderer", None)
    policy = getattr(engine, "policy", None)
    root = getattr(engine, "workspace_root", None)
    attached: list[tuple[str, int]] = []
    model_task = task
    if root is not None:
        model_task, attached = expand_file_mentions(task, Path(root))
    if policy is not None and policy.mode == MODE_PLAN:
        model_task += PLAN_SUFFIX
    snapshot = len(messages)
    messages.append({"role": "user", "content": model_task})
    if session is not None:
        session.append("user", task)
    if renderer is None or not renderer.quiet:
        ui.print("")
    for rel, lines in attached if (renderer is None or not renderer.quiet) else ():
        ui.say(_t(ui, f"  ⎿ Attached {rel} ({lines} lines)", f"  ⎿ Adjuntado {rel} ({lines} líneas)"), style="dim")
    usage_before = int((getattr(engine, "usage", None) or {}).get("completion", 0))
    if renderer is not None:
        renderer.begin_turn()
    try:
        answer = engine.run(messages)
    except BaseException:
        cancel = getattr(engine, "cancel", None)
        if callable(cancel):
            cancel()
        del messages[snapshot:]
        if renderer is not None:
            renderer.abort_turn()
        raise
    if renderer is not None:
        generated = int((getattr(engine, "usage", None) or {}).get("completion", 0)) - usage_before
        renderer.end_turn(usage_tokens=max(0, generated))
    if session is not None:
        session.append("assistant", answer)
    return answer


# ----------------------------------------------------------------- the REPL


@dataclass
class ReplContext:
    args: Any
    client: Any
    ui: Any
    config: Any
    engine: Any
    session: Session
    session_name: str
    messages: list[dict[str, Any]]
    policy: ApprovalPolicy
    pinned_model: str | None = None
    turns: int = 0
    pending: str | None = None

    @property
    def workspace(self) -> Path:
        return Path(getattr(self.engine, "workspace_root", ".")).resolve()


SlashFn = Callable[[str, ReplContext], "int | None"]


def _cmd_help(_arg: str, ctx: ReplContext) -> None:
    ui = ctx.ui
    ui.say(_t(ui, "Commands", "Comandos"), style="bold")
    for names, summary_en, summary_es, _fn in COMMANDS:
        ui.say(f"  {names[0]:<10} {_t(ui, summary_en, summary_es)}")
    ui.say("")
    ui.say(
        _t(
            ui,
            "Tips: @path attaches a file · Shift+Tab cycles permission mode · Alt+Enter = newline · Ctrl-C interrupts",
            "Consejos: @ruta adjunta un archivo · Shift+Tab cambia el modo de permisos · Alt+Enter = nueva línea · "
            "Ctrl-C interrumpe",
        ),
        style="dim",
    )


def _cmd_exit(_arg: str, _ctx: ReplContext) -> int:
    return 0


def _cmd_clear(_arg: str, ctx: ReplContext) -> None:
    ctx.messages.clear()
    todos = getattr(ctx.engine, "todos", None)
    if todos is not None:
        todos.items = []
    ctx.ui.success("Conversation cleared.")


def _cmd_compact(_arg: str, ctx: ReplContext) -> None:
    compact = getattr(ctx.engine, "compact", None)
    if not callable(compact) or not ctx.messages:
        ctx.ui.info(_t(ctx.ui, "Nothing to compact yet.", "Aún no hay nada que compactar."))
        return
    before = len(ctx.messages)
    live = getattr(ctx.ui, "live_status", None)
    status = live(_t(ctx.ui, "Compacting…", "Compactando…")) if callable(live) else None
    try:
        summary = compact(ctx.messages)
    finally:
        if status is not None:
            status.stop()
    if summary is None:
        ctx.ui.warn(
            _t(
                ctx.ui,
                "Could not compact; the conversation is unchanged.",
                "No se pudo compactar; la conversación queda igual.",
            )
        )
        return
    ctx.ui.success(
        _t(
            ctx.ui,
            f"Compacted {before} messages into a summary ({len(summary)} chars).",
            f"Se compactaron {before} mensajes en un resumen ({len(summary)} caracteres).",
        )
    )


def _cmd_model(arg: str, ctx: ReplContext) -> None:
    from trinaxai_cli.commands import chat_slash

    selected = chat_slash._select_model(ctx.client, ctx.ui, arg.strip())
    if selected:
        ctx.pinned_model = selected
        ctx.engine.model = selected
        ctx.ui.success(_t(ctx.ui, f"Model pinned: {selected}", f"Modelo fijado: {selected}"))


def _set_mode(ctx: ReplContext, mode: str) -> None:
    ctx.policy.mode = mode
    if mode == MODE_YOLO:
        ctx.ui.warn(
            _t(
                ctx.ui,
                "Mode yolo: every action runs without asking.",
                "Modo yolo: todas las acciones se ejecutan sin preguntar.",
            )
        )
    else:
        ctx.ui.success(_t(ctx.ui, f"Permission mode: {mode}", f"Modo de permisos: {mode}"))


def _cmd_mode(arg: str, ctx: ReplContext) -> None:
    wanted = arg.strip().lower().replace("_", "-")
    if not wanted:
        ctx.ui.say(
            _t(ctx.ui, f"Current mode: {ctx.policy.mode}", f"Modo actual: {ctx.policy.mode}")
            + "  ("
            + ", ".join(PERMISSION_MODES)
            + ")"
        )
        return
    if wanted not in PERMISSION_MODES:
        ctx.ui.warn(
            _t(
                ctx.ui,
                f"Unknown mode. Use: {', '.join(PERMISSION_MODES)}",
                f"Modo desconocido. Usa: {', '.join(PERMISSION_MODES)}",
            )
        )
        return
    _set_mode(ctx, wanted)


def _cmd_yolo(_arg: str, ctx: ReplContext) -> None:
    _set_mode(ctx, MODE_DEFAULT if ctx.policy.mode == MODE_YOLO else MODE_YOLO)


def _cmd_tools(_arg: str, ctx: ReplContext) -> None:
    for tool in getattr(ctx.engine, "tools", ()) or ():
        marker = "!" if tool.dangerous else " "
        first = tool.description.split(". ")[0].strip()
        ctx.ui.say(f"  [{marker}] {tool.name:<16} {first[:90]}")
    ctx.ui.say(_t(ctx.ui, "  [!] asks for approval", "  [!] pide aprobación"), style="dim")


def _context_bar(ctx: ReplContext) -> tuple[int, int]:
    estimate = getattr(ctx.engine, "estimate_context_tokens", None)
    used = int(estimate(ctx.messages)) if callable(estimate) else 0
    return used, int(getattr(ctx.engine, "num_ctx", 0) or 0)


def _cmd_status(_arg: str, ctx: ReplContext) -> None:
    ui, engine = ctx.ui, ctx.engine
    used, window = _context_bar(ctx)
    usage = getattr(engine, "usage", None) or {}
    rows = [
        (_t(ui, "Model", "Modelo"), str(getattr(engine, "model", "?")) + (" (pinned)" if ctx.pinned_model else "")),
        ("Workspace", str(ctx.workspace)),
        (_t(ui, "Permissions", "Permisos"), ctx.policy.mode),
        (_t(ui, "Context", "Contexto"), f"~{used} / {window} tokens" if window else f"~{used} tokens"),
        (
            _t(ui, "Tokens used", "Tokens usados"),
            f"{usage.get('prompt', 0)} in · {usage.get('completion', 0)} out · {usage.get('requests', 0)} requests",
        ),
        (_t(ui, "Turns", "Turnos"), str(ctx.turns)),
        (_t(ui, "Session", "Sesión"), ctx.session_name),
    ]
    project = getattr(engine, "project_files", None) or []
    if project:
        rows.append((_t(ui, "Instructions", "Instrucciones"), ", ".join(project)))
    for label, value in rows:
        ui.say(f"  {label + ':':<14} {value}")


def _cmd_todos(_arg: str, ctx: ReplContext) -> None:
    todos = getattr(ctx.engine, "todos", None)
    if todos is None or not todos.items:
        ctx.ui.info(_t(ctx.ui, "No todos yet.", "Aún no hay tareas."))
        return
    for line, style in render_todos(todos.items):
        ctx.ui.say(f"  {line}", style=style)


def _cmd_diff(_arg: str, ctx: ReplContext) -> None:
    try:
        stat = subprocess.run(  # noqa: S603,S607 - fixed argv, read-only git
            ["git", "-C", str(ctx.workspace), "diff", "--stat", "--no-color"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        full = subprocess.run(  # noqa: S603,S607
            ["git", "-C", str(ctx.workspace), "diff", "--no-color", "-U2"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        ctx.ui.warn(_t(ctx.ui, "git is not available here.", "git no está disponible aquí."))
        return
    if stat.returncode != 0:
        ctx.ui.info(_t(ctx.ui, "Not a git repository.", "No es un repositorio git."))
        return
    if not stat.stdout.strip():
        ctx.ui.info(_t(ctx.ui, "No uncommitted changes.", "Sin cambios sin confirmar."))
        return
    ctx.ui.say(stat.stdout.rstrip())
    lines = full.stdout.splitlines()
    ctx.ui.code("\n".join(lines[:200]) + (f"\n… +{len(lines) - 200} lines" if len(lines) > 200 else ""), "diff")


def _cmd_init(_arg: str, ctx: ReplContext) -> None:
    ctx.pending = INIT_PROMPT


def _cmd_resume(arg: str, ctx: ReplContext) -> None:
    from trinaxai_cli.commands import chat_slash

    recent = Session.list_recent("agent-", limit=10)
    if not recent:
        ctx.ui.info(_t(ctx.ui, "No earlier agent sessions.", "No hay sesiones anteriores del agente."))
        return
    options = [(item["name"], f"{item['name']}  ({item['turns']} turns)  {item['preview']}") for item in recent]
    name = arg.strip() or chat_slash._numbered_choice(ctx.ui, "Resume which session?", options)
    if not name:
        return
    history = [
        {"role": r["role"], "content": str(r.get("content") or "")}
        for r in Session.load(name)
        if r.get("role") in {"user", "assistant"} and r.get("content")
    ]
    if not history:
        ctx.ui.warn(_t(ctx.ui, f"Session not found or empty: {name}", f"Sesión no encontrada o vacía: {name}"))
        return
    ctx.messages[:] = history
    ctx.ui.success(
        _t(
            ctx.ui,
            f"Loaded {len(history)} messages from {name} (tool details are not restored).",
            f"Se cargaron {len(history)} mensajes de {name} (no se restauran los detalles de herramientas).",
        )
    )


COMMANDS: tuple[tuple[tuple[str, ...], str, str, SlashFn], ...] = (
    (("/help", "/?"), "Show commands and shortcuts", "Mostrar comandos y atajos", _cmd_help),
    (("/exit", "/quit"), "Leave the agent", "Salir del agente", _cmd_exit),
    (("/clear",), "Reset the conversation", "Reiniciar la conversación", _cmd_clear),
    (("/compact",), "Summarize history to free context", "Resumir el historial para liberar contexto", _cmd_compact),
    (("/model",), "Pick the Ollama model", "Elegir el modelo de Ollama", _cmd_model),
    (("/mode",), "Permission mode: default|accept-edits|plan|yolo", "Modo de permisos", _cmd_mode),
    (("/yolo",), "Toggle auto-approve (dangerous)", "Alternar aprobación automática (peligroso)", _cmd_yolo),
    (("/tools",), "List the agent's tools", "Listar las herramientas del agente", _cmd_tools),
    (("/status",), "Model, workspace, context and usage", "Modelo, workspace, contexto y uso", _cmd_status),
    (("/todos",), "Show the current checklist", "Mostrar la lista de tareas", _cmd_todos),
    (("/diff",), "Show uncommitted git changes", "Mostrar cambios de git sin confirmar", _cmd_diff),
    (("/init",), "Create TRINAXAI.md for this project", "Crear TRINAXAI.md para este proyecto", _cmd_init),
    (("/resume",), "Reload an earlier session", "Recargar una sesión anterior", _cmd_resume),
)

REGISTRY: dict[str, SlashFn] = {name: fn for names, _en, _es, fn in COMMANDS for name in names}


def slash_menu() -> tuple[tuple[str, str], ...]:
    return tuple((names[0], summary) for names, summary, _es, _fn in COMMANDS)


def _toolbar(ctx: ReplContext) -> str:
    used, window = _context_bar(ctx)
    pct = f" · ctx {min(99, int(100 * used / window))}%" if window else ""
    home = str(Path.home())
    workspace = str(ctx.workspace)
    workspace = "~" + workspace[len(home) :] if workspace.startswith(home) else workspace
    mode = {MODE_DEFAULT: "default", MODE_ACCEPT_EDITS: "accept edits", MODE_PLAN: "plan", MODE_YOLO: "YOLO"}.get(
        ctx.policy.mode, ctx.policy.mode
    )
    return f" {getattr(ctx.engine, 'model', '?')} · {workspace} · {mode}{pct} · shift+tab: mode · /help "


def _welcome(ctx: ReplContext, resumed: bool) -> None:
    ui, engine = ctx.ui, ctx.engine
    ui.clear()
    ui.set_title("TrinaxAI Agent")
    ui.banner()
    lines = [
        _t(ui, "TrinaxAI Agent - local-first coding agent.", "Agente de TrinaxAI - agente de código local-first."),
        "",
        f"Workspace: {engine.workspace_root}",
        _t(ui, "Model: ", "Modelo: ") + str(engine.model),
        _t(ui, "Permissions: ", "Permisos: ") + ctx.policy.mode,
    ]
    project = getattr(engine, "project_files", None) or []
    if project:
        lines.append(_t(ui, "Instructions: ", "Instrucciones: ") + ", ".join(project))
    if resumed:
        lines.append(_t(ui, f"Resumed {len(ctx.messages)} messages.", f"Se retomaron {len(ctx.messages)} mensajes."))
    lines += [
        "",
        _t(
            ui,
            "Describe a task. The agent reads, edits and runs code; changes ask for approval.",
            "Describe una tarea. El agente lee, edita y ejecuta código; los cambios piden aprobación.",
        ),
        _t(
            ui,
            "/help commands · @file attach · Shift+Tab permission mode · Ctrl-C interrupt",
            "/help comandos · @archivo adjuntar · Shift+Tab modo de permisos · Ctrl-C interrumpir",
        ),
    ]
    ui.panel("\n".join(lines), title=_t(ui, "TrinaxAI Agent", "Agente de TrinaxAI"))


def run_repl(
    args: Any,
    client: Any,
    ui: Any,
    config: Any,
    engine: Any,
    session: Session,
    session_name: str,
    messages: list[dict[str, Any]],
    *,
    resumed: bool = False,
) -> int:
    from trinaxai_cli.commands import agent as agent_cmd

    policy = getattr(engine, "policy", None) or ApprovalPolicy()
    ctx = ReplContext(
        args=args,
        client=client,
        ui=ui,
        config=config,
        engine=engine,
        session=session,
        session_name=session_name,
        messages=messages,
        policy=policy,
        pinned_model=getattr(args, "model", None),
    )
    _welcome(ctx, resumed)
    menu = slash_menu()
    while True:
        if ctx.pending:
            task, ctx.pending = ctx.pending, None
        else:
            try:
                task = ui.agent_prompt(
                    slash_commands=menu,
                    workspace=ctx.workspace,
                    toolbar=lambda: _toolbar(ctx),
                    on_cycle_mode=policy.cycle,
                )
            except (EOFError, KeyboardInterrupt):
                ui.info("\nbye.")
                return 0
        task = (task or "").strip() if isinstance(task, str) else ""
        if not task:
            continue
        lowered = task.lower()
        if lowered in {"exit", "quit"}:
            ui.info("bye.")
            return 0
        if task.startswith("/"):
            command, _, rest = task.partition(" ")
            handler = REGISTRY.get(command.lower())
            if handler is not None:
                result = handler(rest.strip(), ctx)
                if result is not None:
                    ui.info("bye.")
                    return int(result)
                if ctx.pending is None:
                    continue
                task, ctx.pending = ctx.pending, None
            elif "/" not in command[1:]:
                ui.warn(
                    _t(
                        ui,
                        f"Unknown command {command}. Type /help.",
                        f"Comando desconocido {command}. Escribe /help.",
                    )
                )
                continue
        try:
            if not ctx.pinned_model:
                engine.model = agent_cmd._resolve_model(args, ctx.config, task)
            ctx.turns += 1
            run_turn(engine, ui, messages, task, session)
        except KeyboardInterrupt:
            ui.warn("\ninterrupted.")
            ui.info(
                _t(
                    ui,
                    "Request rolled back; press ↑ to edit and resend it.",
                    "Petición revertida; pulsa ↑ para editarla y reenviarla.",
                )
            )
            continue
        except Exception as exc:  # noqa: BLE001
            ui.failure("Agent task", exc)
            ui.info("Is TrinaxAI running? Start it with: trinaxai start")
            continue
        if getattr(engine, "completion_status", "complete") == "degraded":
            ui.warn("Agent response is degraded: the model request failed, so the displayed answer may be incomplete.")
