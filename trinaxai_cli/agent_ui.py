"""Claude-Code-style presentation, permissions and context helpers for the agent CLI.

Everything here is UI-side: the engine in :mod:`trinaxai_agent` stays
UI-agnostic and talks to this module only through the callbacks built by
:class:`AgentRenderer`.

* :class:`ApprovalPolicy` — permission modes (``default``, ``accept-edits``,
  ``plan``, ``yolo``) plus per-session "don't ask again" rules.
* :class:`AgentRenderer` — ``● tool(args)`` / ``⎿ result`` transcript, diffs on
  approval prompts, a live "Working…" status and a per-turn footer.
* :class:`TodoStore` / :func:`build_todo_tool` — the ``todo_write`` checklist.
* :func:`load_project_instructions` — ``TRINAXAI.md`` / ``AGENTS.md`` / ``CLAUDE.md``.
* :func:`expand_file_mentions` — ``@path`` attachments in a prompt.
"""

from __future__ import annotations

import difflib
import json
import re
import shlex
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from trinaxai_agent import Tool, is_degraded_tool_result
from trinaxai_agent.tools import SandboxError, _resolve_in_workspace
from trinaxai_cli.i18n import text

MODE_DEFAULT = "default"
MODE_ACCEPT_EDITS = "accept-edits"
MODE_PLAN = "plan"
MODE_YOLO = "yolo"
PERMISSION_MODES = (MODE_DEFAULT, MODE_ACCEPT_EDITS, MODE_PLAN, MODE_YOLO)
# Shift+Tab never lands on yolo: auto-approving everything must be explicit.
_CYCLE = (MODE_DEFAULT, MODE_ACCEPT_EDITS, MODE_PLAN)

EDIT_TOOLS = frozenset({"write_file", "edit_file"})

_SHELL_META = re.compile(r"[;&|<>`$()\n\\]")
# "Don't ask again" may widen only for commands that cannot execute other code or
# write outside what the user just saw. Everything else is remembered verbatim.
# Test runners and type checkers (pytest, mypy, ruff, tsc) are deliberately absent:
# they load conftest files, plugins and configs from the workspace, so approving
# one run must not approve whatever the agent wrote there afterwards.
_SAFE_PROGRAMS = {"ls", "pwd", "cat", "head", "tail", "wc", "echo", "grep", "rg"}
# Flags that make an otherwise passive program run another program.
_RISKY_FLAGS = {"rg": ("--pre", "--pre-glob", "-z", "--search-zip", "--hostname-bin")}
_SAFE_GIT = {"status", "diff", "log", "show"}
_RISKY_GIT_FLAGS = ("--output", "--ext-diff", "--textconv", "--exec", "-c", "--config")


def _is_risky_flag(program: str, arg: str) -> bool:
    """True when ``arg`` makes a passive program run another one (also in ``-iz`` clusters)."""
    if arg.startswith(_RISKY_FLAGS.get(program, ())):
        return True
    return program == "rg" and re.fullmatch(r"-[^-].*", arg) is not None and "z" in arg


def _is_passive_rule(rule: str) -> bool:
    """Rules that never run workspace code, so they stay valid after the Agent edits files.

    ``git`` is not passive: it runs filter drivers and hooks named in the
    repository's own config, which lives in the Agent-writable workspace.
    """
    return rule in _SAFE_PROGRAMS


def normalize_mode(value: str | None, *, yolo: bool = False) -> str:
    """Map CLI input to a known permission mode (``yolo`` flag wins)."""
    if yolo:
        return MODE_YOLO
    candidate = str(value or MODE_DEFAULT).strip().lower().replace("_", "-")
    aliases = {"accept": MODE_ACCEPT_EDITS, "acceptedits": MODE_ACCEPT_EDITS, "edits": MODE_ACCEPT_EDITS}
    candidate = aliases.get(candidate, candidate)
    return candidate if candidate in PERMISSION_MODES else MODE_DEFAULT


def command_rule(command: str) -> str | None:
    """Return a stable "don't ask again" key for a shell command, or ``None``.

    Compound commands (pipes, ``&&``, redirects, substitutions) are never
    remembered: approving ``ls`` must not approve ``ls; rm -rf``.
    """
    raw = (command or "").strip()
    if not raw or _SHELL_META.search(raw):
        return None
    try:
        argv = shlex.split(raw)
    except ValueError:
        return None
    exact = " ".join(argv)
    if argv[0] != Path(argv[0]).name:  # ./tool or /abs/tool: could be anything in the workspace
        return exact
    program = argv[0]
    if program == "git":
        if len(argv) > 1 and argv[1] in _SAFE_GIT and not any(a.startswith(_RISKY_GIT_FLAGS) for a in argv[2:]):
            return f"git {argv[1]}"
        return exact
    if program in _SAFE_PROGRAMS:
        if any(_is_risky_flag(program, a) for a in argv[1:]):
            return exact
        return program
    return exact


@dataclass
class ApprovalPolicy:
    """Decides whether a dangerous tool call runs, is refused, or needs a prompt."""

    mode: str = MODE_DEFAULT
    allowed: set[str] = field(default_factory=set)
    # Bumped whenever an edit tool is about to run. A remembered rule for a command
    # that executes workspace code (pytest, make, git, ./tool, ...) is valid only for
    # the generation in which the user approved it; after the Agent edits the
    # workspace each such rule must be approved again, individually.
    edit_generation: int = 0
    rule_generation: dict[str, int] = field(default_factory=dict)

    @property
    def yolo(self) -> bool:
        return self.mode == MODE_YOLO

    def cycle(self) -> str:
        """Shift+Tab: default → accept-edits → plan → default."""
        try:
            self.mode = _CYCLE[(_CYCLE.index(self.mode) + 1) % len(_CYCLE)]
        except ValueError:
            self.mode = MODE_DEFAULT
        return self.mode

    def rule_for(self, tool: Tool, args: dict[str, Any]) -> str | None:
        if tool.name in EDIT_TOOLS:
            return "edits"
        if tool.name == "run_command":
            rule = command_rule(str(args.get("command", "")))
            return f"run_command:{rule}" if rule else None
        return tool.name

    def auto_decision(self, tool: Tool, args: dict[str, Any]) -> bool | None:
        """``True`` run, ``False`` refuse, ``None`` ask the user."""
        if tool.name in EDIT_TOOLS:
            self.edit_generation += 1
        if self.mode == MODE_YOLO:
            return True
        if self.mode == MODE_PLAN:
            return False
        if self.mode == MODE_ACCEPT_EDITS and tool.name in EDIT_TOOLS:
            return True
        rule = self.rule_for(tool, args)
        if rule and rule in self.allowed:
            stale = self.rule_generation.get(rule) != self.edit_generation
            if tool.name == "run_command" and stale and not _is_passive_rule(rule.removeprefix("run_command:")):
                return None
            return True
        return None

    def remember(self, tool: Tool, args: dict[str, Any]) -> str | None:
        """Persist "don't ask again" for this session; returns the rule label."""
        if tool.name in EDIT_TOOLS:
            self.mode = MODE_ACCEPT_EDITS
            return "edits"
        rule = self.rule_for(tool, args)
        if rule:
            self.allowed.add(rule)
            # The user has just reviewed the workspace as it stands.
            self.rule_generation[rule] = self.edit_generation
        return rule


# --------------------------------------------------------------------- todos


@dataclass
class TodoStore:
    items: list[dict[str, str]] = field(default_factory=list)

    def update(self, raw: Any) -> list[dict[str, str]]:
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except json.JSONDecodeError:
                raw = [line.strip("-* \t") for line in raw.splitlines() if line.strip()]
        if not isinstance(raw, list):
            raise ValueError("'todos' must be a list of {content, status} objects")
        cleaned: list[dict[str, str]] = []
        for entry in raw[:30]:
            if isinstance(entry, dict):
                content = str(entry.get("content") or entry.get("task") or "").strip()
                status = str(entry.get("status") or "pending").strip().lower().replace("-", "_")
            else:
                content, status = str(entry).strip(), "pending"
            if not content:
                continue
            if status not in {"pending", "in_progress", "completed"}:
                status = "pending"
            cleaned.append({"content": content[:200], "status": status})
        self.items = cleaned
        return cleaned


_TODO_GLYPH = {"pending": "☐", "in_progress": "◐", "completed": "☒"}


def render_todos(items: list[dict[str, str]]) -> list[tuple[str, str | None]]:
    """Return ``(line, style)`` pairs for a checklist."""
    out: list[tuple[str, str | None]] = []
    for item in items:
        status = item["status"]
        style = {"in_progress": "bold", "completed": "dim strike"}.get(status)
        out.append((f"{_TODO_GLYPH[status]} {item['content']}", style))
    return out


def build_todo_tool(store: TodoStore) -> Tool:
    def todo_write(_workspace_root: Path, todos: Any = None, **_kwargs: Any) -> str:
        try:
            items = store.update(todos)
        except ValueError as exc:
            return f"error: {exc}"
        done = sum(1 for item in items if item["status"] == "completed")
        return f"Todos updated: {done}/{len(items)} completed."

    return Tool(
        name="todo_write",
        description=(
            "Keep a visible checklist for multi-step tasks (3+ steps). Send the FULL list each time; "
            "mark exactly one item in_progress and flip items to completed as you finish them."
        ),
        parameters={
            "type": "object",
            "properties": {
                "todos": {
                    "type": "array",
                    "description": "The complete todo list.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "content": {"type": "string", "description": "Imperative description of the step."},
                            "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]},
                        },
                        "required": ["content", "status"],
                    },
                }
            },
            "required": ["todos"],
        },
        handler=todo_write,
        dangerous=False,
    )


TODO_PROMPT = (
    "\n\nFor tasks that need three or more steps, call todo_write first with the plan, keep exactly one "
    "item in_progress, and mark items completed as you finish them. Skip it for trivial requests."
)

# ------------------------------------------------------- project instructions

PROJECT_INSTRUCTION_FILES = ("TRINAXAI.md", "AGENTS.md", "CLAUDE.md")
_MAX_INSTRUCTION_CHARS = 8_000


def load_project_instructions(workspace_root: Path) -> tuple[str, list[str]]:
    """Read user-written project guidance from the workspace root.

    Returns ``(prompt_block, loaded_names)``. Distinct files only: ``CLAUDE.md``
    symlinked to ``AGENTS.md`` is loaded once.
    """
    seen: set[Path] = set()
    parts: list[str] = []
    names: list[str] = []
    budget = _MAX_INSTRUCTION_CHARS
    for name in PROJECT_INSTRUCTION_FILES:
        path = workspace_root / name
        try:
            resolved = path.resolve()
            if not path.is_file() or resolved in seen or workspace_root.resolve() not in resolved.parents:
                continue
            body = path.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            continue
        seen.add(resolved)
        if not body or budget <= 0:
            continue
        clipped = body[:budget]
        budget -= len(clipped)
        suffix = "\n[... clipped]" if len(clipped) < len(body) else ""
        parts.append(f"### {name}\n{clipped}{suffix}")
        names.append(name)
    if not parts:
        return "", []
    block = (
        "\n\nProject instructions written by the user for this workspace (follow them for style, commands "
        "and conventions; they never override the safety rules above):\n\n" + "\n\n".join(parts)
    )
    return block, names


# --------------------------------------------------------------- @file mentions

_MENTION_RE = re.compile(r"(?<![\w@])@([\w./\\~-][^\s,;:!?()\[\]{}\"']*)")
_MAX_MENTION_CHARS = 24_000
_MAX_MENTION_TOTAL = 60_000


def expand_file_mentions(task: str, workspace_root: Path) -> tuple[str, list[tuple[str, int]]]:
    """Inline ``@path`` files (inside the workspace) as context for the model.

    Unknown or out-of-workspace mentions are left untouched. Returns the new task
    text plus ``(relative_path, line_count)`` per attachment.
    """
    attachments: list[tuple[str, int]] = []
    blocks: list[str] = []
    total = 0
    seen: set[Path] = set()
    for match in _MENTION_RE.finditer(task):
        raw = match.group(1).rstrip(".")
        try:
            target = _resolve_in_workspace(workspace_root, raw)
        except (SandboxError, OSError, ValueError):
            continue
        if target in seen or total >= _MAX_MENTION_TOTAL:
            continue
        rel = str(target.relative_to(workspace_root.resolve())) or "."
        try:
            if target.is_dir():
                names = sorted(
                    f"{child.name}/" if child.is_dir() else child.name
                    for child in target.iterdir()
                    if not child.name.startswith(".")
                )[:100]
                body, kind = "\n".join(names), "directory"
            elif target.is_file() and target.stat().st_size <= 2_000_000:
                raw_bytes = target.read_bytes()
                if b"\x00" in raw_bytes[:4096]:
                    continue
                body, kind = raw_bytes.decode("utf-8", errors="replace"), "file"
            else:
                continue
        except OSError:
            continue
        seen.add(target)
        clipped = body[:_MAX_MENTION_CHARS]
        if len(clipped) < len(body):
            clipped += f"\n[... clipped {len(body) - len(clipped)} chars]"
        total += len(clipped)
        blocks.append(f'<attached {kind}="{rel}">\n{clipped}\n</attached>')
        attachments.append((rel, body.count("\n") + 1 if body else 0))
    if not blocks:
        return task, []
    return task + "\n\n" + "\n\n".join(blocks), attachments


# ------------------------------------------------------------------- rendering

_PRIMARY_ARG = {
    "read_file": "path",
    "write_file": "path",
    "edit_file": "path",
    "list_dir": "path",
    "glob": "pattern",
    "grep": "pattern",
    "run_command": "command",
    "web_search": "query",
    "deep_research": "query",
    "search_knowledge": "query",
    "search_memory": "query",
}


def _clip(value: str, limit: int) -> str:
    value = value.replace("\n", "⏎ ")
    return value if len(value) <= limit else value[: limit - 1] + "…"


def tool_title(tool: Tool, args: dict[str, Any]) -> str:
    """``read_file(app.py)`` — the one argument that matters, not a kwargs dump."""
    key = _PRIMARY_ARG.get(tool.name)
    if key and key in args:
        extra = ""
        if tool.name == "grep" and args.get("path") not in (None, "", "."):
            extra = f" in {args['path']}"
        if tool.name == "read_file" and (args.get("offset") or args.get("limit")):
            extra = f" [{int(args.get('offset') or 0) + 1}…]"
        return f"{tool.name}({_clip(str(args[key]), 100)}{extra})"
    if tool.name == "todo_write":
        return "todo_write()"
    parts = [f"{k}={_clip(str(v), 60)}" for k, v in args.items()]
    return f"{tool.name}({_clip(', '.join(parts), 120)})"


def summarize_result(tool: Tool, result: str, max_lines: int = 8) -> tuple[list[str], bool]:
    """Condense a tool result into display lines; second item is True on failure."""
    body = result or ""
    if is_degraded_tool_result(body):
        what = next((line for line in body.splitlines() if line.startswith("What happened:")), "")
        why = next((line for line in body.splitlines() if line.startswith("Why:")), "")
        return [_clip((why or what or "The tool failed.").strip(), 200)], True
    lines = body.splitlines()
    name = tool.name
    if name == "read_file":
        span = re.search(r"lines=(\d+)-(\d+)/(\d+)", lines[0]) if lines else None
        if span:
            first_line, last_line = int(span.group(1)), int(span.group(2))
            count = max(0, last_line - first_line + 1) if last_line else 0
            return [f"Read {count} line{'s' if count != 1 else ''} (of {span.group(3)})"], False
        return [f"Read {len(body)} chars"], False
    if name in {"write_file", "edit_file"}:
        return [_clip(lines[0] if lines else "done", 160)], False
    if name == "list_dir":
        entries = [line for line in lines if not line.startswith("...")]
        return [f"{len(entries)} entr{'y' if len(entries) == 1 else 'ies'}"], False
    if name in {"glob", "grep"}:
        if body.startswith("no "):
            return [body.splitlines()[0]], False
        hits = [line for line in lines if not line.startswith("...")]
        noun = "file" if name == "glob" else "match"
        return [f"{len(hits)} {noun}{'' if len(hits) == 1 else ('es' if noun == 'match' else 's')}"], False
    if name == "run_command":
        header = lines[0] if lines else ""
        output = lines[1:]
        shown = [_clip(line, 200) for line in output[:max_lines]]
        if len(output) > max_lines:
            shown.append(f"… +{len(output) - max_lines} lines")
        return ([_clip(header, 80)] + shown) if shown else [_clip(header or "done", 80)], False
    if name == "todo_write":
        return [_clip(lines[0] if lines else "updated", 80)], False
    first = next((line.strip() for line in lines if line.strip()), "")
    extra = f" (+{len(lines) - 1} lines)" if len(lines) > 1 else ""
    return [_clip(first, 140) + extra], False


def build_diff(workspace_root: Path | None, tool: Tool, args: dict[str, Any], context: int = 2, cap: int = 60) -> str:
    """Unified diff for write/edit previews (falls back to -old/+new)."""
    path = str(args.get("path", "?"))
    before = ""
    exists = False
    if workspace_root is not None:
        try:
            target = _resolve_in_workspace(workspace_root, path)
            if target.is_file():
                before = target.read_text(encoding="utf-8", errors="replace")
                exists = True
        except (SandboxError, OSError, ValueError):
            pass
    if tool.name == "write_file":
        after = str(args.get("content", ""))
    else:
        old, new = str(args.get("old", "")), str(args.get("new", ""))
        if exists and before.count(old) == 1 and old:
            after = before.replace(old, new, 1)
        else:
            return f"- {old[:400]}\n+ {new[:400]}"
    diff = list(
        difflib.unified_diff(
            before.splitlines(),
            after.splitlines(),
            fromfile=f"a/{path}" if exists else "/dev/null",
            tofile=f"b/{path}",
            lineterm="",
            n=context,
        )
    )
    if not diff:
        return "(no changes)"
    if len(diff) > cap:
        diff = diff[:cap] + [f"… +{len(diff) - cap} more diff lines"]
    return "\n".join(diff)


class AgentRenderer:
    """Turns engine callbacks into a Claude-Code-like transcript."""

    def __init__(
        self,
        ui: Any,
        policy: ApprovalPolicy,
        *,
        workspace_root: Path | None = None,
        todos: TodoStore | None = None,
        quiet: bool = False,
        interactive: bool = True,
    ) -> None:
        self.ui = ui
        self.policy = policy
        self.workspace_root = workspace_root
        self.todos = todos
        self.quiet = quiet
        self.interactive = interactive
        self._status: Any = None
        self._mid_line = False
        self._turn_started = 0.0
        self.tool_calls = 0
        self.tokens = 0

    @property
    def language(self) -> str:
        return str(getattr(self.ui, "language", "en"))

    # -- turn lifecycle -------------------------------------------------
    def begin_turn(self) -> None:
        self._turn_started = time.monotonic()
        self.tool_calls = 0
        self._mid_line = False
        self._start_status()

    def end_turn(self, *, usage_tokens: int = 0) -> float:
        self._stop_status()
        elapsed = time.monotonic() - self._turn_started if self._turn_started else 0.0
        if self._mid_line:
            self.ui.say("")
            self._mid_line = False
        if not self.quiet:
            parts = [f"{elapsed:.1f}s"]
            if self.tool_calls:
                parts.append(f"{self.tool_calls} tool call{'s' if self.tool_calls != 1 else ''}")
            if usage_tokens:
                parts.append(f"{usage_tokens} tokens")
            self.ui.say("✻ " + " · ".join(parts), style="dim")
        return elapsed

    def abort_turn(self) -> None:
        """Interrupted/failed turn: stop the status line, no footer."""
        self._stop_status()
        self._break_line()

    def _start_status(self) -> None:
        if self.quiet or self._status is not None:
            return
        live = getattr(self.ui, "live_status", None)
        if callable(live):
            self._status = live(text("status_working", self.language))

    def _stop_status(self) -> None:
        status, self._status = self._status, None
        if status is not None:
            stop = getattr(status, "stop", None)
            if callable(stop):
                stop()

    def _break_line(self) -> None:
        if self._mid_line:
            self.ui.say("")
            self._mid_line = False

    # -- engine callbacks ----------------------------------------------
    def on_tool_start(self, tool: Tool, args: dict[str, Any]) -> None:
        self._stop_status()
        self.tool_calls += 1
        if self.quiet:
            return
        self._break_line()
        self.ui.say(f"● {tool_title(tool, args)}", style="bold")

    def on_tool_result(self, tool: Tool, result: str) -> None:
        if self.quiet:
            return
        self._break_line()
        if tool.name == "todo_write" and self.todos is not None and self.todos.items:
            for line, style in render_todos(self.todos.items):
                self.ui.say(f"  ⎿ {line}", style=style)
        else:
            lines, failed = summarize_result(tool, result)
            for index, line in enumerate(lines):
                gutter = "  ⎿ " if index == 0 else "    "
                self.ui.say(f"{gutter}{line}", style="red" if failed else "dim")
        self._start_status()

    def on_token(self, chunk: str) -> None:
        self._stop_status()
        if self.quiet:
            return
        if not self._mid_line and chunk.strip():
            self.ui.say("")  # breathing room before the answer
        self.ui.stream(chunk)
        if chunk:
            self._mid_line = not chunk.endswith("\n")

    def on_confirm(self, tool: Tool, args: dict[str, Any]) -> bool:
        self._stop_status()
        auto = self.policy.auto_decision(tool, args)
        if auto is True:
            return True
        if auto is False:
            if not self.quiet:
                self.ui.say("  ⎿ " + text("perm_plan_blocked", self.language), style="yellow")
            self._start_status()
            return False
        self._break_line()
        if not self.quiet:
            self.preview(tool, args)
        approved = self._ask(tool, args)
        if approved:
            self._start_status()
        return approved

    # -- permission prompt ----------------------------------------------
    def preview(self, tool: Tool, args: dict[str, Any]) -> None:
        if tool.name in EDIT_TOOLS:
            self.ui.code(build_diff(self.workspace_root, tool, args), "diff")
        elif tool.name == "run_command":
            self.ui.code(str(args.get("command", "")), "bash")

    def _ask(self, tool: Tool, args: dict[str, Any]) -> bool:
        lang = self.language
        if not self.interactive:
            if not self.quiet:
                self.ui.say("  ⎿ " + text("perm_noninteractive", lang), style="yellow")
            return False
        rule = self.policy.rule_for(tool, args)
        options = [("yes", text("perm_yes", lang))]
        if rule == "edits":
            options.append(("always", text("perm_always_edits", lang)))
        elif rule:
            label = rule.split(":", 1)[1] if rule.startswith("run_command:") else rule
            options.append(("always", text("perm_always_rule", lang, rule=label)))
        options.append(("no", text("perm_no", lang)))
        choice = self.ui.choose(text("perm_title", lang, action=tool.name), options, default=0)
        if choice == "always":
            self.policy.remember(tool, args)
            return True
        return choice == "yes"

    def callbacks(self) -> dict[str, Any]:
        return {
            "on_tool_start": self.on_tool_start,
            "on_tool_result": self.on_tool_result,
            "on_confirm": self.on_confirm,
            "on_token": self.on_token,
        }
