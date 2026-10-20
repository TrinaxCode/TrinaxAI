"""Thin wrapper around :mod:`rich` for the TrinaxAI CLI.

The wrapper degrades gracefully when ``rich`` is not installed: in that case
all methods become thin shims over :func:`print` and :func:`input`.  The
underlying library is only imported once at module load time; a failure is
remembered in the ``_RICH`` flag so subsequent instantiations stay cheap.

Honour ``NO_COLOR`` (https://no-color.org/) and the ``--no-color`` flag by
forcing the rich console to ``no_color=True`` when either is set.
"""

from __future__ import annotations

import logging
import os
import re
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator, Sequence

from trinaxai_cli.i18n import resolve_lang, text, translate

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.completion import Completer, Completion
    from prompt_toolkit.formatted_text import HTML
    from prompt_toolkit.history import FileHistory, InMemoryHistory
    from prompt_toolkit.key_binding import KeyBindings

    _PROMPT_TOOLKIT = True
except ImportError:  # pragma: no cover - fallback for minimal installations
    PromptSession = None  # type: ignore[assignment,misc]
    Completer = object  # type: ignore[assignment,misc]
    Completion = None  # type: ignore[assignment,misc]
    HTML = None  # type: ignore[assignment,misc]
    InMemoryHistory = None  # type: ignore[assignment,misc]
    FileHistory = None  # type: ignore[assignment,misc]
    KeyBindings = None  # type: ignore[assignment,misc]
    _PROMPT_TOOLKIT = False


class SlashCommandCompleter(Completer):
    """Show and filter slash commands while the first token is being typed."""

    def __init__(self, commands: Sequence[tuple[str, str]]) -> None:
        self.commands = tuple(commands)

    def get_completions(self, document: Any, complete_event: Any) -> Iterator[Any]:
        before = document.text_before_cursor
        if not before.startswith("/") or any(char.isspace() for char in before):
            return
        needle = before.casefold()
        for name, summary in self.commands:
            if name.casefold().startswith(needle):
                yield Completion(name, start_position=-len(before), display_meta=summary)


_AT_SKIP_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".mypy_cache",
    ".pytest_cache",
    "dist",
    "build",
}


class AtFileCompleter(Completer):
    """Complete ``@path`` mentions with entries from inside the workspace."""

    def __init__(self, workspace: Any = ".", limit: int = 40) -> None:
        self.workspace = workspace
        self.limit = limit

    def get_completions(self, document: Any, complete_event: Any) -> Iterator[Any]:
        match = re.search(r"(?:^|\s)@([^\s]*)$", document.text_before_cursor)
        if not match:
            return
        fragment = match.group(1)
        root = Path(self.workspace).expanduser().resolve()
        directory_part, _, prefix = fragment.rpartition("/")
        try:
            directory = (root / directory_part).resolve() if directory_part else root
            if directory != root and root not in directory.parents:
                return
            entries = sorted(directory.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        except OSError:
            return
        shown = 0
        for entry in entries:
            if entry.name in _AT_SKIP_DIRS or not entry.name.casefold().startswith(prefix.casefold()):
                continue
            if entry.name.startswith(".") and not prefix.startswith("."):
                continue
            completed = (f"{directory_part}/" if directory_part else "") + entry.name + ("/" if entry.is_dir() else "")
            yield Completion(completed, start_position=-len(fragment), display_meta="dir" if entry.is_dir() else "")
            shown += 1
            if shown >= self.limit:
                return


# ----------------------------------------------------------------- rich import
_RICH: bool = False
_rich_console_cls: Any = None
_rich_table_cls: Any = None
_rich_panel_cls: Any = None
_rich_markdown_cls: Any = None
_rich_syntax_cls: Any = None
_rich_prompt_cls: Any = None
_rich_confirm_cls: Any = None
_rich_progress_cls: Any = None
_rich_spinner_column_cls: Any = None
_rich_text_column_cls: Any = None

try:  # pragma: no cover - exercised by tests via sys.modules patching
    from rich.console import Console as _rich_console_cls  # type: ignore
    from rich.markdown import Markdown as _rich_markdown_cls  # type: ignore
    from rich.panel import Panel as _rich_panel_cls  # type: ignore
    from rich.progress import (  # type: ignore
        Progress as _rich_progress_cls,
    )
    from rich.progress import (
        SpinnerColumn as _rich_spinner_column_cls,
    )
    from rich.progress import (
        TextColumn as _rich_text_column_cls,
    )
    from rich.prompt import Confirm as _rich_confirm_cls
    from rich.prompt import Prompt as _rich_prompt_cls  # type: ignore
    from rich.syntax import Syntax as _rich_syntax_cls  # type: ignore
    from rich.table import Table as _rich_table_cls  # type: ignore

    _RICH = True
except ImportError:
    _RICH = False

_WARNED_NO_RICH = False


def _want_color(no_color: bool) -> bool:
    if no_color:
        return False
    if os.environ.get("NO_COLOR"):
        return False
    return not os.environ.get("TRINAXAI_NO_COLOR")


def _default_history_path() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or os.path.join("~", ".local", "share")
    return Path(base).expanduser() / "trinaxai" / "agent_history"


def get_console(no_color: bool = False, language: str | None = None) -> "Console":
    """Return a console honoring color settings and the selected locale."""
    return Console(no_color=no_color, language=language)


class Console:
    """UI facade.  Backed by :mod:`rich` when available, otherwise plain stdio."""

    def __init__(self, no_color: bool = False, language: str | None = None) -> None:
        global _WARNED_NO_RICH
        self.language = resolve_lang(language)
        self.no_color = not _want_color(no_color)
        self._color_enabled = not self.no_color
        self._rich_console: Any = None
        self._chat_session: Any = None
        if _RICH:
            try:
                self._rich_console = _rich_console_cls(no_color=self.no_color, force_terminal=None)
            except TypeError:
                # Older rich versions don't accept no_color - fall back.
                self._rich_console = _rich_console_cls()
        else:
            if not _WARNED_NO_RICH:
                _WARNED_NO_RICH = True
                print(
                    "warning: 'rich' is not installed; falling back to plain text output. "
                    "Install with: pip install rich",
                    file=sys.stderr,
                )

    # ------------------------------------------------------------------- text
    def print(self, msg: Any = "", *, end: str = "\n") -> None:
        if self._rich_console is not None:
            self._rich_console.print(msg, end=end)
        else:
            print(msg, end=end)

    def say(self, msg: Any = "", *, style: str | None = None, end: str = "\n") -> None:
        """Print model/tool/user text verbatim: no rich markup, no auto-highlight.

        ``print`` interprets ``[bold]``-style markup, which silently eats
        bracketed text in streamed answers and file contents. Anything that is
        not authored by the CLI itself must go through this method.
        """
        if self._rich_console is not None:
            self._rich_console.print(
                msg,
                style=style if (style and self._color_enabled) else None,
                end=end,
                markup=False,
                highlight=False,
                soft_wrap=True,
            )
        else:
            print(msg, end=end)
        if end != "\n":
            try:
                sys.stdout.flush()
            except (OSError, ValueError):  # pragma: no cover - closed pipe
                pass

    def stream(self, chunk: str) -> None:
        """Append a streamed fragment without a trailing newline."""
        self.say(chunk, end="")

    def info(self, msg: Any) -> None:
        self._styled(msg, "info")

    def warn(self, msg: Any) -> None:
        self._styled(msg, "warn")

    def error(self, msg: Any) -> None:
        self._styled(msg, "error")

    def failure(self, action: str, exc: BaseException) -> None:
        """Log technical context at DEBUG and show only a safe explanation."""
        logging.getLogger("trinaxai_cli").debug(
            "%s failed",
            action,
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        action = translate(action, self.language)
        if type(exc).__name__ == "TrinaxAPIError":
            self.error(f"{action}: {exc}")
            return
        self.error(text("failure_generic", self.language, action=action))

    def success(self, msg: Any) -> None:
        self._styled(msg, "success")

    def _styled(self, msg: Any, level: str) -> None:
        msg = translate(msg, self.language)
        if self._rich_console is not None:
            styles = {
                "info": "cyan",
                "warn": "yellow",
                "error": "bold red",
                "success": "bold green",
            }
            prefix = {
                "info": "[*]",
                "warn": "[!]",
                "error": "[x]",
                "success": "[+]",
            }
            self._rich_console.print(f"[{styles[level]}]{prefix[level]} {msg}[/{styles[level]}]")
        else:
            prefix = {
                "info": "*",
                "warn": "!",
                "error": "x",
                "success": "+",
            }
            print(f"{prefix[level]} {msg}")

    # ----------------------------------------------------------------- prompt
    def prompt(self, question: str, default: str | None = None) -> str:
        question = translate(question, self.language)
        if _RICH and _rich_prompt_cls is not None:
            try:
                return _rich_prompt_cls.ask(
                    question,
                    default=default,
                    console=self._rich_console,
                )
            except Exception:
                # Fall through to plain input on any rich failure.
                pass
        suffix = f" [{default}]" if default is not None else ""
        try:
            value = input(f"{question}{suffix}: ").strip()
        except EOFError:
            return default or ""
        if not value and default is not None:
            return default
        return value

    def confirm(self, question: str, default: bool = False) -> bool:
        question = translate(question, self.language)
        if _RICH and _rich_confirm_cls is not None:
            try:
                return _rich_confirm_cls.ask(
                    question,
                    default=default,
                    console=self._rich_console,
                )
            except Exception:
                pass
        suffix = " [Y/n]" if default else " [y/N]"
        try:
            raw = input(f"{question}{suffix}: ").strip().lower()
        except EOFError:
            return default
        if not raw:
            return default
        return raw in {"y", "yes", "s", "si"}

    def choose(
        self,
        question: str,
        options: Sequence[tuple[str, str]],
        default: int = 0,
    ) -> str | None:
        """Numbered single-choice prompt; returns the chosen value or ``None``.

        ``None`` means the user cancelled (``q``/``Esc``-style input, EOF or
        Ctrl-C), so callers can treat it as a refusal. Typing a number or the
        first letters of a label both work.
        """
        if not options:
            return None
        default = default if 0 <= default < len(options) else 0
        self.say(translate(question, self.language), style="bold")
        for index, (_, label) in enumerate(options, start=1):
            marker = "›" if index - 1 == default else " "
            self.say(f" {marker} {index}. {translate(label, self.language)}")
        hint = text("choose_hint", self.language, default=default + 1)
        try:
            raw = input(f"{hint} ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return None
        if not raw:
            return options[default][0]
        if raw in {"q", "esc", "cancel", "c"}:
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1][0]
        for value, label in options:
            if raw == value.lower() or label.lower().startswith(raw):
                return value
        return None

    class _LiveStatus:
        """Transient ``Working… (12s)`` line that must be stopped before printing."""

        def __init__(self, console: "Console", label: str) -> None:
            self._status: Any = None
            self._stop = threading.Event()
            self._thread: threading.Thread | None = None
            rich_console = console._rich_console
            if rich_console is None or not console._color_enabled or not sys.stdout.isatty():
                return
            started = time.monotonic()
            hint = text("status_interrupt_hint", console.language)
            self._status = rich_console.status(f"{label} (0s · {hint})", spinner="dots")
            self._status.start()

            def tick() -> None:
                while not self._stop.wait(1.0):
                    elapsed = int(time.monotonic() - started)
                    try:
                        self._status.update(f"{label} ({elapsed}s · {hint})")
                    except Exception:  # pragma: no cover - display only
                        return

            self._thread = threading.Thread(target=tick, daemon=True)
            self._thread.start()

        def stop(self) -> None:
            self._stop.set()
            status, self._status = self._status, None
            if status is not None:
                try:
                    status.stop()
                except Exception:  # pragma: no cover - display only
                    pass

    def live_status(self, label: str = "Working…") -> "Console._LiveStatus":
        """Start an animated status line; call ``.stop()`` before any output."""
        return Console._LiveStatus(self, translate(label, self.language))

    # --------------------------------------------------------------- spinner
    @contextmanager
    def spinner(self, label: str) -> Iterator[None]:
        message = translate(label, self.language)
        progress: Any = None
        if _RICH and _rich_progress_cls is not None:
            try:
                progress = _rich_progress_cls(
                    _rich_spinner_column_cls(),
                    _rich_text_column_cls(message),
                    transient=True,
                    console=self._rich_console,
                )
            except Exception:
                progress = None
        if progress is not None:
            # Do not catch exceptions raised by the command body here. A
            # contextmanager may only yield once, and swallowing such an
            # exception before falling back would trigger "generator didn't
            # stop after throw()" instead of showing the real command error.
            with progress:
                try:
                    progress.start()
                    yield
                finally:
                    progress.stop()
            return
        print(f"... {message}")
        try:
            yield
        finally:
            print(f"    {text('spinner_done', self.language)}")

    @contextmanager
    def thinking(self, text: str = "TrinaxAI is thinking...") -> Iterator[Callable[[], None]]:
        """Show a transient status that callers can stop on the first token."""
        text = translate(text, self.language)
        stopped = False
        status: Any = None

        def stop() -> None:
            nonlocal stopped
            if stopped:
                return
            stopped = True
            if status is not None:
                status.stop()

        if self._rich_console is not None:
            status = self._rich_console.status(text, spinner="dots")
            status.start()
        else:
            print(text)
        try:
            yield stop
        finally:
            stop()

    # ---------------------------------------------------------------- branding
    def banner(self, subtitle: str | None = None) -> None:
        """Render the big TrinaxAI banner (gradient when colour is enabled)."""
        try:
            from trinaxai_cli import branding

            branding.render_banner(self, subtitle=subtitle)
        except Exception:
            # Branding must never break startup.
            self.print("TrinaxAI")

    def clear(self) -> None:
        """Clear terminal history for an immersive interactive launch."""
        try:
            from trinaxai_cli import branding

            branding.clear_terminal()
        except Exception:
            pass

    def set_title(self, title: str = "TrinaxAI") -> None:
        """Set the terminal title (no-op without a TTY or with colour off)."""
        if self.no_color:
            return
        try:
            from trinaxai_cli import branding

            branding.set_terminal_title(title)
        except Exception:
            pass

    # ------------------------------------------------------------------ chat
    def chat_prompt(
        self,
        mode: str | None = None,
        slash_commands: Sequence[tuple[str, str]] = (),
    ) -> str:
        """Ask the user for a chat turn with a distinct, coloured speaker marker.

        Renders as a green ``● You`` label so the user's turns are visually
        separated from TrinaxAI's blue replies for quick visual scanning.
        A leading blank line gives each turn breathing room. Raises
        ``EOFError``/``KeyboardInterrupt`` so the REPL loop can exit on Ctrl-D.
        """
        hint = f" ({mode})" if mode else ""
        you = text("you_label", self.language)
        if _PROMPT_TOOLKIT and sys.stdin.isatty() and sys.stdout.isatty():
            if self._chat_session is None:
                self._chat_session = PromptSession(history=InMemoryHistory())
            completer = SlashCommandCompleter(slash_commands)
            label = f"● {you}{hint}  "
            try:
                return self._chat_session.prompt(
                    HTML(f"<b><ansigreen>{label}</ansigreen></b>"),
                    completer=completer,
                    complete_while_typing=True,
                    reserve_space_for_menu=min(12, max(4, len(slash_commands))),
                ).strip()
            except (EOFError, KeyboardInterrupt):
                raise
            except Exception:
                # Keep the CLI usable on unusual terminals.
                pass
        if _RICH and _rich_prompt_cls is not None and self._rich_console is not None:
            try:
                from trinaxai_cli import branding

                self._rich_console.print("")
                if self._color_enabled:
                    question = f"[bold {branding.USER_ACCENT}]● {you}[/][dim]{hint}[/dim]"
                else:
                    question = f"● {you}{hint}"
                prompt_obj = _rich_prompt_cls(question, console=self._rich_console)
                prompt_obj.prompt_suffix = "  "
                return prompt_obj()
            except (EOFError, KeyboardInterrupt):
                raise
            except Exception:
                pass
        print("")
        return input(f"● {you}{hint}  ").strip()

    def agent_prompt(
        self,
        *,
        slash_commands: Sequence[tuple[str, str]] = (),
        workspace: Any = ".",
        toolbar: Callable[[], str] | None = None,
        on_cycle_mode: Callable[[], None] | None = None,
        history_path: Path | str | None = None,
        label: str = "agent",
    ) -> str:
        """Prompt for one agent task.

        Enter submits, ``Alt+Enter`` (or a trailing ``\\``) inserts a newline,
        ``Shift+Tab`` cycles the permission mode, ``/`` completes slash commands
        and ``@`` completes workspace paths. History persists across sessions.
        Raises ``EOFError``/``KeyboardInterrupt`` so callers can exit cleanly.
        """
        self._agent_ctx = {"toolbar": toolbar, "on_cycle": on_cycle_mode, "commands": tuple(slash_commands)}
        self._agent_workspace = workspace
        if _PROMPT_TOOLKIT and sys.stdin.isatty() and sys.stdout.isatty():
            try:
                if getattr(self, "_agent_session", None) is None:
                    self._agent_session = self._build_agent_session(history_path)
                if self._color_enabled:
                    message = HTML(f"<b><ansigreen>● {label} ›</ansigreen></b> ")
                else:
                    message = f"● {label} › "
                return self._agent_session.prompt(message).strip()
            except (EOFError, KeyboardInterrupt):
                raise
            except Exception:
                logging.getLogger("trinaxai_cli").debug("agent prompt fell back to plain input", exc_info=True)
        return self.prompt(label)

    def _build_agent_session(self, history_path: Path | str | None) -> Any:
        from prompt_toolkit.completion import merge_completers

        history: Any
        try:
            path = Path(history_path) if history_path else _default_history_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            history = FileHistory(str(path))
        except OSError:
            history = InMemoryHistory()

        class _Dynamic(Completer):
            def __init__(inner, console: "Console") -> None:  # noqa: N805
                inner.console = console

            def get_completions(inner, document: Any, complete_event: Any) -> Iterator[Any]:  # noqa: N805
                ctx = inner.console._agent_ctx
                merged = merge_completers(
                    [SlashCommandCompleter(ctx["commands"]), AtFileCompleter(inner.console._agent_workspace)]
                )
                yield from merged.get_completions(document, complete_event)

        bindings = KeyBindings()

        @bindings.add("escape", "enter")
        def _newline(event: Any) -> None:
            event.current_buffer.insert_text("\n")

        @bindings.add("enter")
        def _submit(event: Any) -> None:
            buffer = event.current_buffer
            if buffer.text.endswith("\\"):
                buffer.delete_before_cursor(1)
                buffer.insert_text("\n")
            else:
                buffer.validate_and_handle()

        @bindings.add("s-tab")
        def _cycle(event: Any) -> None:
            callback = self._agent_ctx.get("on_cycle")
            if callable(callback):
                callback()
            event.app.invalidate()

        def _toolbar() -> str:
            provider = self._agent_ctx.get("toolbar")
            return provider() if callable(provider) else ""

        return PromptSession(
            history=history,
            completer=_Dynamic(self),
            complete_while_typing=True,
            key_bindings=bindings,
            bottom_toolbar=_toolbar,
            reserve_space_for_menu=8,
        )

    def assistant_label(self, name: str = "TrinaxAI") -> None:
        """Print the blue ``● TrinaxAI`` speaker label on its own line.

        Callers stream the answer on the lines that follow, so the transcript
        reads as a chat with clearly attributed turns.
        """
        if self._rich_console is not None and self._color_enabled:
            try:
                from trinaxai_cli import branding

                self._rich_console.print("")
                self._rich_console.print(f"[bold {branding.BRAND_BLUE}]● {name}[/]")
                return
            except Exception:
                pass
        self.print("")
        self.print(f"● {name}")

    def reset_title(self) -> None:
        try:
            from trinaxai_cli import branding

            branding.reset_terminal_title()
        except Exception:
            pass

    # ----------------------------------------------------------------- table
    def table(
        self,
        columns: Sequence[str],
        rows: Sequence[Sequence[Any]],
        title: str | None = None,
    ) -> None:
        columns = [str(translate(column, self.language)) for column in columns]
        title = translate(title, self.language) if title else title
        rows = [[translate(cell, self.language) if isinstance(cell, str) else cell for cell in row] for row in rows]
        if _RICH and _rich_table_cls is not None:
            try:
                t = _rich_table_cls(title=title or "", show_header=True, header_style="bold")
                for col in columns:
                    t.add_column(col)
                for row in rows:
                    t.add_row(*[str(c) for c in row])
                if self._rich_console is not None:
                    self._rich_console.print(t)
                else:
                    print(t)
                return
            except Exception:
                pass
        # Plain fallback: simple columnar text.
        widths = [len(c) for c in columns]
        for row in rows:
            for i, cell in enumerate(row):
                widths[i] = max(widths[i], len(str(cell)))
        if title:
            print(title)
            print("-" * len(title))
        print("  ".join(c.ljust(widths[i]) for i, c in enumerate(columns)))
        print("  ".join("-" * w for w in widths))
        for row in rows:
            print("  ".join(str(c).ljust(widths[i]) for i, c in enumerate(row)))

    # ----------------------------------------------------------------- panel
    def panel(self, text: str, title: str | None = None) -> None:
        title = translate(title, self.language) if title else title
        if _RICH and _rich_panel_cls is not None:
            try:
                p = _rich_panel_cls.fit(text, title=title or "")
                if self._rich_console is not None:
                    self._rich_console.print(p)
                else:
                    print(p)
                return
            except Exception:
                pass
        border = "-" * 60
        if title:
            print(f"--- {title} ---")
        print(text)
        print(border)

    # --------------------------------------------------------------- markdown
    def markdown(self, text: str) -> None:
        text = translate(text, self.language)
        if _RICH and _rich_markdown_cls is not None:
            try:
                md = _rich_markdown_cls(text)
                if self._rich_console is not None:
                    self._rich_console.print(md)
                else:
                    print(md)
                return
            except Exception:
                pass
        print(text)

    # ------------------------------------------------------------------ code
    def code(self, text: str, language: str | None = None) -> None:
        if _RICH and _rich_syntax_cls is not None:
            try:
                s = _rich_syntax_cls(text, language or "text", theme="monokai", line_numbers=False)
                if self._rich_console is not None:
                    self._rich_console.print(s)
                else:
                    print(s)
                return
            except Exception:
                pass
        print(text)
