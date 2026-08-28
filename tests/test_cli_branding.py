from __future__ import annotations

import ctypes

from trinaxai_cli import branding


class RecordingUI:
    def __init__(self, *, rich: bool, color: bool) -> None:
        self._rich_console = object() if rich else None
        self._color_enabled = color
        self.lines: list[str] = []

    def print(self, msg: str = "", *, end: str = "\n") -> None:
        self.lines.append(str(msg))


def test_banner_lines_pick_wide_art_for_normal_terminals() -> None:
    lines = branding.banner_lines(width=80)
    assert any("█" in line for line in lines)


def test_banner_lines_fall_back_to_narrow_art_when_cramped() -> None:
    lines = branding.banner_lines(width=40)
    assert all("█" not in line for line in lines)


def test_render_banner_plain_without_rich_still_emits_art() -> None:
    ui = RecordingUI(rich=False, color=False)
    branding.render_banner(ui)
    joined = "\n".join(ui.lines)
    assert "TrinaxAI" in joined or any(ch in joined for ch in ("█", "_"))
    assert branding.TAGLINE in joined


def test_set_terminal_title_is_noop_without_tty(monkeypatch, capsys) -> None:
    monkeypatch.setattr(branding.sys.stdout, "isatty", lambda: False, raising=False)
    branding.set_terminal_title("TrinaxAI")
    out = capsys.readouterr().out
    assert "\033]0;" not in out


def test_clear_terminal_erases_viewport_and_scrollback_on_tty(monkeypatch, capsys) -> None:
    monkeypatch.setattr(branding.sys.stdout, "isatty", lambda: True, raising=False)
    monkeypatch.setattr(branding.os, "name", "posix")
    branding.clear_terminal()
    out = capsys.readouterr().out
    assert "\033[2J" in out
    assert "\033[3J" in out


def test_windows_branding_uses_native_console_apis(monkeypatch, capsys) -> None:
    monkeypatch.setattr(branding, "_is_tty", lambda: True)
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("TRINAXAI_NO_COLOR", raising=False)
    monkeypatch.setattr(branding.os, "name", "nt")
    calls: list[str] = []

    class Kernel32:
        def SetConsoleTitleW(self, title: str) -> None:
            calls.append(title)

    class Ctypes:
        windll = type("Windll", (), {"kernel32": Kernel32()})()

    monkeypatch.setattr(branding, "os", branding.os)
    monkeypatch.setattr(ctypes, "windll", Ctypes.windll, raising=False)
    branding.set_terminal_title("TrinaxAI")
    branding.reset_terminal_title()
    assert calls == ["TrinaxAI", ""]
    assert "\033]0;" not in capsys.readouterr().out
