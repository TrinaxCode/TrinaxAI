"""Thin wrapper around :mod:`rich` for the TrinaxAI CLI.

The wrapper degrades gracefully when ``rich`` is not installed: in that case
all methods become thin shims over :func:`print` and :func:`input`.  The
underlying library is only imported once at module load time; a failure is
remembered in the ``_RICH`` flag so subsequent instantiations stay cheap.

Honour ``NO_COLOR`` (https://no-color.org/) and the ``--no-color`` flag by
forcing the rich console to ``no_color=True`` when either is set.
"""
from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from typing import Any, Callable, Iterator, Sequence

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.completion import Completer, Completion
    from prompt_toolkit.formatted_text import HTML
    from prompt_toolkit.history import InMemoryHistory

    _PROMPT_TOOLKIT = True
except ImportError:  # pragma: no cover - fallback for minimal installations
    PromptSession = None  # type: ignore[assignment,misc]
    Completer = object  # type: ignore[assignment,misc]
    Completion = None  # type: ignore[assignment,misc]
    HTML = None  # type: ignore[assignment,misc]
    InMemoryHistory = None  # type: ignore[assignment,misc]
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
    if os.environ.get("TRINAXAI_NO_COLOR"):
        return False
    return True


def get_console(no_color: bool = False) -> "Console":
    """Return a console honouring the ``NO_COLOR`` env var and the flag."""
    return Console(no_color=no_color)


class Console:
    """UI facade.  Backed by :mod:`rich` when available, otherwise plain stdio."""

    def __init__(self, no_color: bool = False) -> None:
        global _WARNED_NO_RICH
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

    def info(self, msg: Any) -> None:
        self._styled(msg, "info")

    def warn(self, msg: Any) -> None:
        self._styled(msg, "warn")

    def error(self, msg: Any) -> None:
        self._styled(msg, "error")

    def success(self, msg: Any) -> None:
        self._styled(msg, "success")

    def _styled(self, msg: Any, level: str) -> None:
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

    # --------------------------------------------------------------- spinner
    @contextmanager
    def spinner(self, text: str) -> Iterator[None]:
        progress: Any = None
        if _RICH and _rich_progress_cls is not None:
            try:
                progress = _rich_progress_cls(
                    _rich_spinner_column_cls(),
                    _rich_text_column_cls(text),
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
        print(f"... {text}")
        try:
            yield
        finally:
            print("    done")

    @contextmanager
    def thinking(self, text: str = "TrinaxAI is thinking...") -> Iterator[Callable[[], None]]:
        """Show a transient status that callers can stop on the first token."""
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
        if _PROMPT_TOOLKIT and sys.stdin.isatty() and sys.stdout.isatty():
            if self._chat_session is None:
                self._chat_session = PromptSession(history=InMemoryHistory())
            completer = SlashCommandCompleter(slash_commands)
            label = f"● You{hint}  "
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
                    question = (
                        f"[bold {branding.USER_ACCENT}]● You[/]"
                        f"[dim]{hint}[/dim]"
                    )
                else:
                    question = f"● You{hint}"
                prompt_obj = _rich_prompt_cls(question, console=self._rich_console)
                prompt_obj.prompt_suffix = "  "
                return prompt_obj()
            except (EOFError, KeyboardInterrupt):
                raise
            except Exception:
                pass
        print("")
        return input(f"● You{hint}  ").strip()

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
