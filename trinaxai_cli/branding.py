"""Branding for the TrinaxAI CLI: the big ``TrinaxAI`` banner and the terminal
title.

Everything here degrades gracefully:

* The banner is plain embedded ASCII art (no ``figlet`` dependency). When
  ``rich`` is available it is coloured with a cyan→magenta gradient; otherwise
  it prints as-is.
* The terminal title uses the OSC escape sequence understood by virtually every
  modern terminal emulator. It is a no-op when stdout is not a TTY or colour is
  disabled, so it never leaks raw escape codes into pipes or logs.

The module keeps no import-time side effects and no hard dependency on
``rich`` — callers pass in the :class:`~trinaxai_cli.ui.Console` and let it
decide how to render.
"""
from __future__ import annotations

import os
import sys
from typing import Any

# Big block letters for "TrinaxAI". Kept as a raw string so the alignment is
# obvious in source. ~72 cols wide, safe for an 80-col terminal.
BANNER_ART = r"""
 ████████╗██████╗ ██╗███╗   ██╗ █████╗ ██╗  ██╗ █████╗ ██╗
 ╚══██╔══╝██╔══██╗██║████╗  ██║██╔══██╗╚██╗██╔╝██╔══██╗██║
    ██║   ██████╔╝██║██╔██╗ ██║███████║ ╚███╔╝ ███████║██║
    ██║   ██╔══██╗██║██║╚██╗██║██╔══██║ ██╔██╗ ██╔══██║██║
    ██║   ██║  ██║██║██║ ╚████║██║  ██║██╔╝ ██╗██║  ██║██║
    ╚═╝   ╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝
""".strip("\n")

# A compact fallback for very narrow terminals (< 62 columns).
BANNER_ART_NARROW = r"""
 _____     _                  _    ___
|_   _|_ _(_)_ _  __ ___ __ _| |  / _ \_ _
  | || '_| | ' \/ _` \ \ / _` | | | (_) | ' \
  |_||_| |_|_||_\__,_/_\_\__,_|_|  \___/|_||_|
""".strip("\n")

TAGLINE = "Local-first AI in your terminal · chat · search · research · agent"

# Shared brand palette. TrinaxAI speaks in blue everywhere; the user gets a
# contrasting accent so the two are never confused in the transcript.
BRAND_BLUE = "#3b82f6"  # blue-500 — the one TrinaxAI colour
USER_ACCENT = "#34d399"  # emerald-400 — "You" marker, distinct from blue

# Gradient applied line by line to the banner when rich is available. Blue only,
# a soft glow from bright to deep and back so the wordmark reads as one colour.
_GRADIENT = [
    "#60a5fa",  # blue-400
    "#3b82f6",  # blue-500
    "#2563eb",  # blue-600
    "#2563eb",  # blue-600
    "#3b82f6",  # blue-500
    "#60a5fa",  # blue-400
]


def _terminal_width(default: int = 80) -> int:
    try:
        return os.get_terminal_size().columns
    except OSError:
        return default


def _is_tty() -> bool:
    try:
        return bool(sys.stdout.isatty())
    except Exception:
        return False


def clear_terminal() -> None:
    """Clear the visible terminal and scrollback before an interactive UI."""
    if not _is_tty():
        return
    try:
        # 2J clears the viewport, H homes the cursor and 3J clears scrollback.
        sys.stdout.write("\033[2J\033[H\033[3J")
        sys.stdout.flush()
    except Exception:
        pass


def banner_lines(width: int | None = None) -> list[str]:
    """Return the banner as a list of lines, picking wide vs narrow art."""
    cols = width if width is not None else _terminal_width()
    art = BANNER_ART if cols >= 62 else BANNER_ART_NARROW
    return art.splitlines()


def render_banner(ui: Any, *, subtitle: str | None = None) -> None:
    """Print the big TrinaxAI banner via ``ui``.

    Uses a per-line colour gradient when the console supports rich styling,
    and falls back to plain text otherwise. ``subtitle`` is shown dimmed
    beneath the art (defaults to :data:`TAGLINE`).
    """
    lines = banner_lines()
    rich_console = getattr(ui, "_rich_console", None)
    color_enabled = getattr(ui, "_color_enabled", False)
    tag = TAGLINE if subtitle is None else subtitle

    if rich_console is not None and color_enabled:
        try:
            from rich.text import Text  # type: ignore

            ui.print("")
            for index, line in enumerate(lines):
                color = _GRADIENT[index % len(_GRADIENT)]
                rich_console.print(Text(line, style=f"bold {color}"))
            if tag:
                rich_console.print(Text(f"  {tag}", style="dim italic"))
            ui.print("")
            return
        except Exception:
            pass

    # Plain fallback.
    ui.print("")
    for line in lines:
        ui.print(line)
    if tag:
        ui.print(f"  {tag}")
    ui.print("")


def set_terminal_title(title: str = "TrinaxAI") -> None:
    """Set the terminal window/tab title via the OSC escape sequence.

    No-op when stdout is not a TTY (so pipes and log files stay clean) or when
    ``NO_COLOR``/``TRINAXAI_NO_COLOR`` is set — a user who disabled ANSI output
    does not want us writing escape codes either.
    """
    if not _is_tty():
        return
    if os.environ.get("NO_COLOR") or os.environ.get("TRINAXAI_NO_COLOR"):
        return
    try:
        sys.stdout.write(f"\033]0;{title}\007")
        sys.stdout.flush()
    except Exception:
        pass


def reset_terminal_title() -> None:
    """Best-effort clear of the title we set (empty title restores default)."""
    set_terminal_title("")
