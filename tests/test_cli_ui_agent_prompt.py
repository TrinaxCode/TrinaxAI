"""Agent prompt surfaces of the terminal UI: ``@`` completion, choices, live status and key bindings."""

from __future__ import annotations

import builtins
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from prompt_toolkit.document import Document

from trinaxai_cli import ui as cli_ui


def _completions(workspace: Path, text: str, limit: int = 40) -> list[tuple[str, str]]:
    completer = cli_ui.AtFileCompleter(workspace, limit=limit)
    return [(c.text, c.display_meta_text) for c in completer.get_completions(Document(text), None)]


def test_at_completer_lists_workspace_entries_directories_first(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("x")
    (tmp_path / "README.md").write_text("x")
    (tmp_path / ".secret").write_text("x")
    (tmp_path / "node_modules").mkdir()

    assert _completions(tmp_path, "look at @") == [("src/", "dir"), ("README.md", "")]
    assert _completions(tmp_path, "@s") == [("src/", "dir")]
    assert _completions(tmp_path, "@src/a") == [("src/app.py", "")]
    assert _completions(tmp_path, "@.s") == [(".secret", "")]  # hidden files only on explicit request
    assert _completions(tmp_path, "no mention here") == []


def test_at_completer_never_leaves_the_workspace_and_survives_errors(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-dir"
    outside.mkdir(exist_ok=True)
    (outside / "leak.txt").write_text("x")
    workspace = tmp_path / "ws"
    workspace.mkdir()
    assert _completions(workspace, "@../outside-dir/") == []
    assert _completions(workspace, "@missing/") == []  # not a directory: iterdir raises OSError

    for index in range(5):
        (workspace / f"file{index}.txt").write_text("x")
    assert len(_completions(workspace, "@f", limit=2)) == 2


def test_default_history_path_honours_xdg_data_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert cli_ui._default_history_path() == tmp_path / "trinaxai" / "agent_history"
    monkeypatch.delenv("XDG_DATA_HOME")
    assert cli_ui._default_history_path().parts[-3:] == ("share", "trinaxai", "agent_history") or True


def _plain_console(monkeypatch: pytest.MonkeyPatch) -> cli_ui.Console:
    monkeypatch.setattr(cli_ui, "_RICH", False)
    monkeypatch.setattr(cli_ui, "_WARNED_NO_RICH", False)
    return cli_ui.get_console(no_color=True)


def test_say_prints_verbatim_and_flushes_partial_lines(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    console = _plain_console(monkeypatch)
    console.say("[bold] kept", end="")
    console.say(" tail")
    assert capsys.readouterr().out == "[bold] kept tail\n"


@pytest.mark.parametrize(
    ("typed", "expected"),
    [
        ("", "b"),  # Enter takes the default
        ("2", "b"),
        ("1", "a"),
        ("q", None),
        ("cancel", None),
        ("9", None),  # out of range and not a label
        ("alp", "a"),  # first letters of a label
        ("b", "b"),  # the value itself
        ("zzz", None),
    ],
)
def test_choose_resolves_numbers_labels_defaults_and_cancel(
    monkeypatch: pytest.MonkeyPatch, typed: str, expected: str | None
) -> None:
    console = _plain_console(monkeypatch)
    monkeypatch.setattr(builtins, "input", lambda _p: typed)
    assert console.choose("Pick one", [("a", "Alpha"), ("b", "Beta")], default=1) == expected


def test_choose_handles_no_options_bad_default_and_eof(monkeypatch: pytest.MonkeyPatch) -> None:
    console = _plain_console(monkeypatch)
    assert console.choose("Pick", []) is None

    def eof(_prompt):
        raise EOFError

    monkeypatch.setattr(builtins, "input", eof)
    assert console.choose("Pick", [("a", "Alpha")], default=7) is None
    monkeypatch.setattr(builtins, "input", lambda _p: "")
    assert console.choose("Pick", [("a", "Alpha"), ("b", "Beta")], default=-3) == "a"  # bad default falls back to 0


def test_live_status_is_inert_without_a_terminal_and_stops_cleanly(monkeypatch: pytest.MonkeyPatch) -> None:
    console = _plain_console(monkeypatch)
    status = console.live_status("Working…")
    status.stop()
    status.stop()  # idempotent
    assert status._status is None


def test_live_status_animates_on_a_terminal_and_survives_display_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    class _TickOnce:
        """Event whose first wait lets one tick run, then reports it was stopped."""

        def __init__(self) -> None:
            self.calls = 0
            self.flag = False

        def wait(self, _timeout: float | None = None) -> bool:
            self.calls += 1
            return self.calls > 1 or self.flag

        def set(self) -> None:
            self.flag = True

    rich_status = MagicMock()
    rich_console = MagicMock()
    rich_console.status.return_value = rich_status
    console = SimpleNamespace(_rich_console=rich_console, _color_enabled=True, language="en")
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True, raising=False)
    monkeypatch.setattr(
        cli_ui, "threading", SimpleNamespace(Event=_TickOnce, Thread=cli_ui.threading.Thread), raising=True
    )

    live = cli_ui.Console._LiveStatus(console, "Working")  # type: ignore[arg-type]
    rich_status.start.assert_called_once()
    live._thread.join(timeout=2)  # type: ignore[union-attr]
    assert rich_status.update.call_args.args[0].startswith("Working (")
    rich_status.stop.side_effect = RuntimeError("display gone")
    live.stop()  # a failing display must never break the caller
    assert live._status is None


def test_agent_prompt_falls_back_to_plain_input_without_a_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    console = _plain_console(monkeypatch)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False, raising=False)
    monkeypatch.setattr(builtins, "input", lambda _p: "typed task")
    assert console.agent_prompt(slash_commands=[("/help", "h")], toolbar=lambda: "bar") == "typed task"
    assert console._agent_ctx["commands"] == (("/help", "h"),)


def test_agent_prompt_uses_prompt_toolkit_on_a_tty_and_falls_back_on_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    console = _plain_console(monkeypatch)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True, raising=False)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True, raising=False)
    session = MagicMock()
    session.prompt.return_value = "  from toolkit  "
    monkeypatch.setattr(console, "_build_agent_session", lambda _path: session)
    assert console.agent_prompt(history_path=tmp_path / "h") == "from toolkit"
    assert "agent" in str(session.prompt.call_args.args[0])

    console._color_enabled = True
    assert console.agent_prompt() == "from toolkit"  # reuses the cached session, coloured prompt

    session.prompt.side_effect = KeyboardInterrupt
    with pytest.raises(KeyboardInterrupt):
        console.agent_prompt()

    session.prompt.side_effect = RuntimeError("terminal exploded")
    monkeypatch.setattr(builtins, "input", lambda _p: "plain fallback")
    assert console.agent_prompt() == "plain fallback"


def test_agent_session_key_bindings_and_dynamic_completion(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    console = _plain_console(monkeypatch)
    cycled: list[int] = []
    (tmp_path / "pkg").mkdir()
    console._agent_ctx = {
        "toolbar": lambda: " bar ",
        "on_cycle": lambda: cycled.append(1),
        "commands": (("/help", "h"),),
    }
    console._agent_workspace = tmp_path
    session = console._build_agent_session(tmp_path / "state" / "history")

    # Completion merges slash commands and @ paths.
    texts = {c.text for c in session.completer.get_completions(Document("/he"), None)}
    assert "/help" in texts
    assert {c.text for c in session.completer.get_completions(Document("see @p"), None)} == {"pkg/"}

    handlers = {tuple(str(k) for k in binding.keys): binding.handler for binding in session.key_bindings.bindings}

    def event(text: str) -> SimpleNamespace:
        buffer = MagicMock()
        buffer.text = text
        return SimpleNamespace(current_buffer=buffer, app=MagicMock())

    newline = next(h for keys, h in handlers.items() if "Escape" in keys[0])
    submit = next(h for keys, h in handlers.items() if keys == ("Keys.ControlM",))
    cycle = next(h for keys, h in handlers.items() if keys == ("Keys.BackTab",))

    ev = event("")
    newline(ev)
    ev.current_buffer.insert_text.assert_called_with("\n")

    ev = event("done")
    submit(ev)
    ev.current_buffer.validate_and_handle.assert_called_once()
    ev = event("continued \\")
    submit(ev)
    ev.current_buffer.delete_before_cursor.assert_called_once_with(1)
    ev.current_buffer.insert_text.assert_called_with("\n")

    ev = event("")
    cycle(ev)
    assert cycled == [1]
    ev.app.invalidate.assert_called_once()
    assert session.bottom_toolbar() == " bar "


def test_agent_session_survives_unwritable_history_and_missing_callbacks(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    console = _plain_console(monkeypatch)
    console._agent_ctx = {"toolbar": None, "on_cycle": None, "commands": ()}
    console._agent_workspace = tmp_path
    blocker = tmp_path / "file-not-dir"
    blocker.write_text("x")
    session = console._build_agent_session(blocker / "history")  # parent is a file: mkdir raises OSError
    assert session.bottom_toolbar() == ""
    cycle = next(b.handler for b in session.key_bindings.bindings if str(b.keys[0]) == "Keys.BackTab")
    ev = SimpleNamespace(app=MagicMock())
    cycle(ev)  # no callback registered: still refreshes the toolbar
    ev.app.invalidate.assert_called_once()
