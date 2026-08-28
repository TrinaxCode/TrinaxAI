from __future__ import annotations

import builtins
import runpy
from types import SimpleNamespace

import pytest

from trinaxai_cli import branding
from trinaxai_cli import ui as cli_ui
from trinaxai_cli.client import TrinaxAPIError


def test_slash_command_completion_only_matches_the_first_token() -> None:
    completer = cli_ui.SlashCommandCompleter([("/help", "Help"), ("/history", "History"), ("/clear", "Clear")])

    matches = list(
        completer.get_completions(
            SimpleNamespace(text_before_cursor="/he"),
            None,
        )
    )

    assert [item.text for item in matches] == ["/help"]
    assert (
        list(
            completer.get_completions(
                SimpleNamespace(text_before_cursor="hello"),
                None,
            )
        )
        == []
    )
    assert (
        list(
            completer.get_completions(
                SimpleNamespace(text_before_cursor="/help now"),
                None,
            )
        )
        == []
    )


def test_color_preference_honors_flags_and_environment(monkeypatch) -> None:
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("TRINAXAI_NO_COLOR", raising=False)
    assert cli_ui._want_color(False)
    assert not cli_ui._want_color(True)

    monkeypatch.setenv("NO_COLOR", "1")
    assert not cli_ui._want_color(False)
    monkeypatch.delenv("NO_COLOR")
    monkeypatch.setenv("TRINAXAI_NO_COLOR", "1")
    assert not cli_ui._want_color(False)


def test_plain_console_supports_prompts_tables_and_content(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli_ui, "_RICH", False)
    monkeypatch.setattr(cli_ui, "_WARNED_NO_RICH", False)
    answers = iter(["", "yes", "typed"])
    monkeypatch.setattr(builtins, "input", lambda _prompt: next(answers))
    console = cli_ui.get_console(no_color=True)

    console.print("plain", end="!")
    console.info("info")
    console.warn("warn")
    console.error("error")
    console.success("success")
    assert console.prompt("Default", default="value") == "value"
    assert console.confirm("Continue?") is True
    assert console.prompt("Typed") == "typed"
    console.table(["name", "count"], [["docs", 2]], title="Collections")
    console.panel("body", title="Panel")
    console.markdown("# heading")
    console.code("print('ok')", "python")

    captured = capsys.readouterr()
    assert "falling back to plain text" in captured.err
    assert "Collections" in captured.out
    assert "docs" in captured.out
    assert "Panel" in captured.out
    assert "# heading" in captured.out


def test_plain_prompt_and_confirm_recover_from_eof(monkeypatch) -> None:
    monkeypatch.setattr(cli_ui, "_RICH", False)
    monkeypatch.setattr(cli_ui, "_WARNED_NO_RICH", True)
    monkeypatch.setattr(
        builtins,
        "input",
        lambda _prompt: (_ for _ in ()).throw(EOFError()),
    )
    console = cli_ui.Console(no_color=True)

    assert console.prompt("Name", default="TrinaxAI") == "TrinaxAI"
    assert console.prompt("Name") == ""
    assert console.confirm("Continue?", default=True) is True


def test_plain_spinner_and_thinking_always_finish(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli_ui, "_RICH", False)
    monkeypatch.setattr(cli_ui, "_WARNED_NO_RICH", True)
    console = cli_ui.Console(no_color=True)

    with console.spinner("Working"):
        pass
    with console.thinking("Thinking") as stop:
        stop()
        stop()

    output = capsys.readouterr().out
    assert "... Working" in output
    assert "done" in output
    assert "Thinking" in output


def test_branding_helpers_are_best_effort(monkeypatch) -> None:
    monkeypatch.setattr(cli_ui, "_RICH", False)
    monkeypatch.setattr(cli_ui, "_WARNED_NO_RICH", True)
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("TRINAXAI_NO_COLOR", raising=False)
    calls: list[tuple[str, object]] = []
    monkeypatch.setattr(
        branding,
        "render_banner",
        lambda _console, subtitle=None: calls.append(("banner", subtitle)),
    )
    monkeypatch.setattr(branding, "clear_terminal", lambda: calls.append(("clear", None)))
    monkeypatch.setattr(
        branding,
        "set_terminal_title",
        lambda title: calls.append(("title", title)),
    )
    monkeypatch.setattr(
        branding,
        "reset_terminal_title",
        lambda: calls.append(("reset", None)),
    )
    console = cli_ui.Console(no_color=False)

    console.banner("Ready")
    console.clear()
    console.set_title("Assistant")
    console.reset_title()

    assert calls == [
        ("banner", "Ready"),
        ("clear", None),
        ("title", "Assistant"),
        ("reset", None),
    ]

    console.no_color = True
    console.set_title("ignored")
    assert calls[-1] == ("reset", None)


def test_branding_failures_never_break_console(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli_ui, "_RICH", False)
    monkeypatch.setattr(cli_ui, "_WARNED_NO_RICH", True)
    monkeypatch.setattr(
        branding,
        "render_banner",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("broken")),
    )
    monkeypatch.setattr(
        branding,
        "clear_terminal",
        lambda: (_ for _ in ()).throw(RuntimeError("broken")),
    )
    monkeypatch.setattr(
        branding,
        "reset_terminal_title",
        lambda: (_ for _ in ()).throw(RuntimeError("broken")),
    )
    console = cli_ui.Console(no_color=True)

    console.banner()
    console.clear()
    console.reset_title()

    assert "TrinaxAI" in capsys.readouterr().out


class _FakeStatus:
    def __init__(self) -> None:
        self.started = 0
        self.stopped = 0

    def start(self) -> None:
        self.started += 1

    def stop(self) -> None:
        self.stopped += 1


class _FakeRichConsole:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.printed: list[tuple[object, str]] = []
        self.current_status = _FakeStatus()

    def print(self, value="", *, end="\n") -> None:
        self.printed.append((value, end))

    def status(self, _text, spinner=None):
        return self.current_status


def test_rich_console_renders_all_surface_types(monkeypatch) -> None:
    rich_console = _FakeRichConsole()
    monkeypatch.setattr(cli_ui, "_RICH", True)
    monkeypatch.setattr(cli_ui, "_rich_console_cls", lambda **_kwargs: rich_console)
    monkeypatch.setattr(
        cli_ui,
        "_rich_prompt_cls",
        SimpleNamespace(ask=lambda *_args, **_kwargs: "answer"),
    )
    monkeypatch.setattr(
        cli_ui,
        "_rich_confirm_cls",
        SimpleNamespace(ask=lambda *_args, **_kwargs: True),
    )

    class Table:
        def __init__(self, **_kwargs):
            self.columns = []
            self.rows = []

        def add_column(self, value):
            self.columns.append(value)

        def add_row(self, *values):
            self.rows.append(values)

    monkeypatch.setattr(cli_ui, "_rich_table_cls", Table)
    monkeypatch.setattr(
        cli_ui,
        "_rich_panel_cls",
        SimpleNamespace(fit=lambda text, title="": ("panel", title, text)),
    )
    monkeypatch.setattr(cli_ui, "_rich_markdown_cls", lambda text: ("markdown", text))
    monkeypatch.setattr(cli_ui, "_rich_syntax_cls", lambda text, *args, **kwargs: ("code", text))

    console = cli_ui.Console()
    console.print("message", end="")
    console.info("info")
    console.warn("warn")
    console.error("error")
    console.success("success")
    assert console.prompt("Question") == "answer"
    assert console.confirm("Continue?") is True
    console.table(["name"], [["docs"]], title="Rows")
    console.panel("body", "Title")
    console.markdown("**bold**")
    console.code("x = 1", "python")
    with console.thinking() as stop:
        stop()

    assert rich_console.current_status.started == 1
    assert rich_console.current_status.stopped == 1
    assert len(rich_console.printed) == 9


def test_rich_spinner_starts_and_stops(monkeypatch) -> None:
    events: list[str] = []

    class Progress:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            events.append("enter")
            return self

        def __exit__(self, *_args):
            events.append("exit")

        def start(self):
            events.append("start")

        def stop(self):
            events.append("stop")

    monkeypatch.setattr(cli_ui, "_RICH", True)
    monkeypatch.setattr(cli_ui, "_rich_console_cls", lambda **_kwargs: _FakeRichConsole())
    monkeypatch.setattr(cli_ui, "_rich_progress_cls", Progress)
    monkeypatch.setattr(cli_ui, "_rich_spinner_column_cls", lambda: object())
    monkeypatch.setattr(cli_ui, "_rich_text_column_cls", lambda _text: object())

    with cli_ui.Console().spinner("Working"):
        events.append("body")

    assert events == ["enter", "start", "body", "stop", "exit"]


def test_chat_prompt_uses_toolkit_then_plain_fallback(monkeypatch) -> None:
    session = SimpleNamespace(prompt=lambda *_args, **_kwargs: "  hello  ")
    monkeypatch.setattr(cli_ui, "_RICH", False)
    monkeypatch.setattr(cli_ui, "_WARNED_NO_RICH", True)
    monkeypatch.setattr(cli_ui, "_PROMPT_TOOLKIT", True)
    monkeypatch.setattr(cli_ui, "PromptSession", lambda **_kwargs: session)
    monkeypatch.setattr(cli_ui, "InMemoryHistory", lambda: object())
    monkeypatch.setattr(cli_ui, "HTML", lambda value: value)
    monkeypatch.setattr(cli_ui.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(cli_ui.sys.stdout, "isatty", lambda: True)
    console = cli_ui.Console(no_color=True)

    assert console.chat_prompt("agent", [("/help", "Help")]) == "hello"

    monkeypatch.setattr(cli_ui, "_PROMPT_TOOLKIT", False)
    monkeypatch.setattr(builtins, "input", lambda _prompt: "  fallback  ")
    assert console.chat_prompt("chat") == "fallback"


def test_assistant_label_has_plain_fallback(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli_ui, "_RICH", False)
    monkeypatch.setattr(cli_ui, "_WARNED_NO_RICH", True)
    console = cli_ui.Console(no_color=True)

    console.assistant_label("Local")

    assert "● Local" in capsys.readouterr().out


def test_ui_remaining_rich_error_and_fallback_paths(monkeypatch, capsys) -> None:
    real_import = builtins.__import__

    def without_rich(name, *args, **kwargs):
        if name.startswith("rich"):
            raise ImportError("rich unavailable")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_rich)
    fallback_module = runpy.run_path(cli_ui.__file__, run_name="cli_ui_fallback")
    assert fallback_module["_RICH"] is False
    monkeypatch.setattr(builtins, "__import__", real_import)

    class RichConsole:
        def __init__(self) -> None:
            self.printed = []

        def print(self, value="", **kwargs) -> None:
            self.printed.append((value, kwargs))

    rich_console = RichConsole()
    constructor_calls = 0

    def old_rich_constructor(**kwargs):
        nonlocal constructor_calls
        constructor_calls += 1
        if "force_terminal" in kwargs:
            raise TypeError("old rich")
        return rich_console

    monkeypatch.setattr(cli_ui, "_RICH", True)
    monkeypatch.setattr(cli_ui, "_rich_console_cls", old_rich_constructor)
    monkeypatch.setattr(
        cli_ui,
        "_rich_progress_cls",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("progress")),
    )
    console = cli_ui.Console()
    assert constructor_calls == 2
    with console.spinner("Working"):
        pass

    console.failure("Request", TrinaxAPIError(400, "bad request"))
    monkeypatch.setattr(
        branding,
        "set_terminal_title",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("title")),
    )
    console.no_color = False
    console.set_title("ignored")

    monkeypatch.setattr(
        cli_ui,
        "_rich_prompt_cls",
        SimpleNamespace(ask=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("prompt"))),
    )
    monkeypatch.setattr(
        cli_ui,
        "_rich_confirm_cls",
        SimpleNamespace(ask=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("confirm"))),
    )
    answers = iter(["typed", ""])
    monkeypatch.setattr(builtins, "input", lambda _prompt: next(answers))
    assert console.prompt("Question") == "typed"
    assert console.confirm("Continue?") is False

    monkeypatch.setattr(cli_ui, "_PROMPT_TOOLKIT", True)
    monkeypatch.setattr(cli_ui.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(cli_ui.sys.stdout, "isatty", lambda: True)
    monkeypatch.setattr(
        cli_ui,
        "PromptSession",
        lambda **_kwargs: SimpleNamespace(
            prompt=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("terminal"))
        ),
    )
    monkeypatch.setattr(cli_ui, "InMemoryHistory", lambda: object())
    monkeypatch.setattr(cli_ui, "_RICH", False)
    monkeypatch.setattr(builtins, "input", lambda _prompt: "toolkit fallback")
    assert cli_ui.Console(no_color=True).chat_prompt("chat") == "toolkit fallback"
    monkeypatch.setattr(
        cli_ui,
        "PromptSession",
        lambda **_kwargs: SimpleNamespace(prompt=lambda *_args, **_kwargs: (_ for _ in ()).throw(EOFError())),
    )
    with pytest.raises(EOFError):
        cli_ui.Console(no_color=True).chat_prompt("chat")

    monkeypatch.setattr(cli_ui, "_RICH", True)
    monkeypatch.setattr(cli_ui, "_PROMPT_TOOLKIT", False)

    class RichPrompt:
        def __init__(self, _question, **_kwargs) -> None:
            self.prompt_suffix = ""

        def __call__(self) -> str:
            return "rich answer"

    monkeypatch.setattr(cli_ui, "_rich_prompt_cls", RichPrompt)
    colored_console = cli_ui.Console(no_color=False)
    colored_console._color_enabled = True
    assert colored_console.chat_prompt("chat") == "rich answer"
    assert cli_ui.Console(no_color=True).chat_prompt("chat") == "rich answer"

    class EofPrompt:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def __call__(self) -> str:
            raise EOFError

    monkeypatch.setattr(cli_ui, "_rich_prompt_cls", EofPrompt)
    with pytest.raises(EOFError):
        cli_ui.Console(no_color=True).chat_prompt("chat")

    class BrokenPrompt:
        def __init__(self, *_args, **_kwargs) -> None:
            raise RuntimeError("prompt construction")

    monkeypatch.setattr(cli_ui, "_rich_prompt_cls", BrokenPrompt)
    monkeypatch.setattr(builtins, "input", lambda _prompt: "plain answer")
    assert cli_ui.Console(no_color=False).chat_prompt("chat") == "plain answer"

    class FlakyConsole(RichConsole):
        def __init__(self) -> None:
            super().__init__()
            self.calls = 0

        def print(self, value="", **kwargs) -> None:
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("label")
            super().print(value, **kwargs)

    label_console = cli_ui.Console(no_color=False)
    label_console._color_enabled = True
    label_console._rich_console = FlakyConsole()
    label_console.assistant_label("Local")
    clean_label_console = cli_ui.Console(no_color=False)
    clean_label_console._color_enabled = True
    clean_label_console._rich_console = RichConsole()
    clean_label_console.assistant_label("Local")

    table_console = cli_ui.Console(no_color=True)
    table_console._rich_console = None

    class Table:
        def add_column(self, _value) -> None:
            pass

        def add_row(self, *_values) -> None:
            pass

    monkeypatch.setattr(cli_ui, "_rich_table_cls", lambda **_kwargs: Table())
    table_console.table(["name"], [["docs"]], "Rows")
    monkeypatch.setattr(
        cli_ui,
        "_rich_table_cls",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("table")),
    )
    table_console.table(["name"], [["docs"]], "Rows")

    monkeypatch.setattr(cli_ui, "_rich_panel_cls", SimpleNamespace(fit=lambda *_args, **_kwargs: "panel"))
    table_console.panel("body", "Panel")
    monkeypatch.setattr(
        cli_ui,
        "_rich_panel_cls",
        SimpleNamespace(fit=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("panel"))),
    )
    table_console.panel("body", "Panel")

    monkeypatch.setattr(cli_ui, "_rich_markdown_cls", lambda text: ("markdown", text))
    table_console.markdown("body")
    monkeypatch.setattr(
        cli_ui,
        "_rich_markdown_cls",
        lambda _text: (_ for _ in ()).throw(RuntimeError("markdown")),
    )
    table_console.markdown("body")

    monkeypatch.setattr(cli_ui, "_rich_syntax_cls", lambda text, *_args, **_kwargs: ("code", text))
    table_console.code("body")
    monkeypatch.setattr(
        cli_ui,
        "_rich_syntax_cls",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("code")),
    )
    table_console.code("body")

    assert "Rows" in capsys.readouterr().out
