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
from typing import Any, Iterator, Sequence

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
        if _RICH and _rich_progress_cls is not None:
            try:
                with _rich_progress_cls(
                    _rich_spinner_column_cls(),
                    _rich_text_column_cls(text),
                    transient=True,
                    console=self._rich_console,
                ) as progress:
                    progress.start()
                    yield
                return
            except Exception:
                pass
        print(f"... {text}")
        yield
        print("    done")

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
