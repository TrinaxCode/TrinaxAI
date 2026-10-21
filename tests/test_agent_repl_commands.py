"""Slash commands, status surfaces and error paths of the ``trinaxai agent`` REPL."""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from trinaxai_cli.agent_ui import MODE_DEFAULT, MODE_PLAN, MODE_YOLO, ApprovalPolicy, TodoStore
from trinaxai_cli.commands import agent_repl
from trinaxai_cli.session import Session


class _Session:
    def __init__(self) -> None:
        self.entries: list[tuple[str, str]] = []

    def append(self, role: str, content: str) -> None:
        self.entries.append((role, content))


def _ui(language: str = "en") -> MagicMock:
    ui = MagicMock()
    ui.language = language
    return ui


def _ctx(
    tmp_path: Path, *, ui: MagicMock | None = None, mode: str = MODE_DEFAULT, **engine_extra
) -> agent_repl.ReplContext:
    engine = SimpleNamespace(
        workspace_root=tmp_path,
        model="m",
        num_ctx=1000,
        usage={"prompt": 5, "completion": 7, "requests": 2},
        todos=TodoStore(),
        **engine_extra,
    )
    return agent_repl.ReplContext(
        args=SimpleNamespace(model=None),
        client=MagicMock(),
        ui=ui or _ui(),
        config=None,
        engine=engine,
        session=_Session(),  # type: ignore[arg-type]
        session_name="agent-x",
        messages=[],
        policy=ApprovalPolicy(mode=mode),
    )


def _said(ui: MagicMock) -> str:
    return " ".join(str(call.args[0]) for call in ui.say.call_args_list if call.args)


def test_help_lists_every_command_in_both_languages(tmp_path: Path) -> None:
    for language, expected in (("en", "Show commands and shortcuts"), ("es", "Mostrar comandos y atajos")):
        ctx = _ctx(tmp_path, ui=_ui(language))
        agent_repl._cmd_help("", ctx)
        text = _said(ctx.ui)
        assert expected in text and "/compact" in text and "/resume" in text
    assert agent_repl._cmd_exit("", ctx) == 0


def test_compact_reports_success_failure_and_always_stops_the_spinner(tmp_path: Path) -> None:
    status = MagicMock()
    ctx = _ctx(tmp_path, compact=lambda messages: "summary text")
    ctx.ui.live_status.return_value = status
    ctx.messages.extend([{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}])
    agent_repl._cmd_compact("", ctx)
    status.stop.assert_called_once()
    assert "Compacted 2 messages" in str(ctx.ui.success.call_args.args[0])

    failing = _ctx(tmp_path, compact=lambda messages: None)
    failing.messages.append({"role": "user", "content": "a"})
    agent_repl._cmd_compact("", failing)
    assert "Could not compact" in str(failing.ui.warn.call_args.args[0])

    def boom(_messages):
        raise RuntimeError("model down")

    raising = _ctx(tmp_path, compact=boom)
    raising.ui.live_status.return_value = status
    raising.messages.append({"role": "user", "content": "a"})
    with pytest.raises(RuntimeError):
        agent_repl._cmd_compact("", raising)
    assert status.stop.call_count == 2  # stopped even when compaction raised


def test_mode_command_shows_validates_and_sets(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    agent_repl._cmd_mode("", ctx)
    assert "Current mode: default" in _said(ctx.ui)
    agent_repl._cmd_mode("PLAN", ctx)
    assert ctx.policy.mode == MODE_PLAN
    agent_repl._cmd_mode("accept_edits", ctx)
    assert ctx.policy.mode == "accept-edits"
    agent_repl._cmd_mode("bogus", ctx)
    assert "Unknown mode" in str(ctx.ui.warn.call_args.args[0])
    agent_repl._cmd_yolo("", ctx)
    assert ctx.policy.mode == MODE_YOLO
    agent_repl._cmd_yolo("", ctx)
    assert ctx.policy.mode == MODE_DEFAULT

    spanish = _ctx(tmp_path, ui=_ui("es"))
    agent_repl._cmd_mode("", spanish)
    assert "Modo actual" in _said(spanish.ui)


def test_tools_status_and_todos_surfaces(tmp_path: Path) -> None:
    tools = (
        SimpleNamespace(name="read_file", description="Read a file. More detail.", dangerous=False),
        SimpleNamespace(name="run_command", description="Run a command", dangerous=True),
    )
    ctx = _ctx(tmp_path, tools=tools, project_files=["AGENTS.md"], estimate_context_tokens=lambda _m: 250)
    ctx.pinned_model = "m"
    ctx.turns = 3
    agent_repl._cmd_tools("", ctx)
    agent_repl._cmd_status("", ctx)
    said = _said(ctx.ui)
    assert "[ ] read_file" in said and "[!] run_command" in said and "asks for approval" in said
    assert "m (pinned)" in said and "~250 / 1000 tokens" in said
    assert "5 in · 7 out · 2 requests" in said and "AGENTS.md" in said and "Turns" in said

    assert agent_repl._toolbar(ctx).count("ctx 25%") == 1

    empty = _ctx(tmp_path)
    agent_repl._cmd_todos("", empty)
    empty.ui.info.assert_called_with("No todos yet.")
    empty.engine.todos.update([{"content": "write tests", "status": "in_progress"}])
    agent_repl._cmd_todos("", empty)
    assert "write tests" in _said(empty.ui)

    bare = _ctx(tmp_path)
    bare.engine.num_ctx = 0
    assert agent_repl._context_bar(bare) == (0, 0)
    assert "ctx" not in agent_repl._toolbar(bare)


def test_toolbar_abbreviates_the_home_directory_and_names_modes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    for mode, label in ((MODE_YOLO, "YOLO"), (MODE_PLAN, "plan"), ("accept-edits", "accept edits")):
        ctx = _ctx(tmp_path, mode=mode)
        bar = agent_repl._toolbar(ctx)
        assert label in bar and "~" in bar


def test_welcome_mentions_instructions_and_resumed_messages(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, project_files=["TRINAXAI.md"])
    ctx.messages.extend([{"role": "user", "content": "x"}] * 4)
    agent_repl._welcome(ctx, resumed=True)
    panel = str(ctx.ui.panel.call_args.args[0])
    assert "TRINAXAI.md" in panel and "Resumed 4 messages." in panel
    ctx.ui.banner.assert_called_once()

    spanish = _ctx(tmp_path, ui=_ui("es"))
    agent_repl._welcome(spanish, resumed=False)
    assert "Permisos:" in str(spanish.ui.panel.call_args.args[0])


def _completed(code: int, out: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], code, stdout=out, stderr="")


def test_diff_covers_missing_git_clean_tree_and_long_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _ctx(tmp_path)

    def missing(*_a, **_k):
        raise FileNotFoundError("git")

    monkeypatch.setattr(agent_repl, "_git_diff", missing)
    agent_repl._cmd_diff("", ctx)
    assert "git is not available" in str(ctx.ui.warn.call_args.args[0])

    monkeypatch.setattr(agent_repl, "_git_diff", lambda *_a: _completed(0, "  \n"))
    agent_repl._cmd_diff("", ctx)
    ctx.ui.info.assert_called_with("No uncommitted changes.")

    long_diff = "\n".join(f"+line {n}" for n in range(250))
    monkeypatch.setattr(
        agent_repl, "_git_diff", lambda _w, *args: _completed(0, " a.py | 250 +\n" if "--stat" in args else long_diff)
    )
    agent_repl._cmd_diff("", ctx)
    shown, language = ctx.ui.code.call_args.args
    assert language == "diff" and "… +50 lines" in shown


def test_resume_restores_text_messages_and_reports_problems(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    ctx = _ctx(tmp_path)
    agent_repl._cmd_resume("", ctx)
    ctx.ui.info.assert_called_with("No earlier agent sessions.")

    with Session("agent-old") as old:
        old.append("user", "earlier question")
        old.append("assistant", "earlier answer")
        old.append("tool", "ignored tool output")
    with Session("agent-empty") as empty:
        empty.append("tool", "only tool output")

    agent_repl._cmd_resume("agent-old", ctx)
    assert [m["content"] for m in ctx.messages] == ["earlier question", "earlier answer"]
    assert "Loaded 2 messages from agent-old" in str(ctx.ui.success.call_args.args[0])

    agent_repl._cmd_resume("agent-empty", ctx)
    assert "Session not found or empty: agent-empty" in str(ctx.ui.warn.call_args.args[0])
    assert len(ctx.messages) == 2  # a failed resume leaves history untouched

    from trinaxai_cli.commands import chat_slash

    monkeypatch.setattr(chat_slash, "_numbered_choice", lambda *_a, **_k: "")
    agent_repl._cmd_resume("", ctx)  # picker cancelled
    monkeypatch.setattr(chat_slash, "_numbered_choice", lambda *_a, **_k: "agent-old")
    ctx.messages.clear()
    agent_repl._cmd_resume("", ctx)
    assert len(ctx.messages) == 2


def test_run_turn_aborts_the_renderer_and_ends_it_with_generated_tokens(tmp_path: Path) -> None:
    renderer = MagicMock()
    renderer.quiet = False
    engine = SimpleNamespace(
        workspace_root=tmp_path,
        renderer=renderer,
        usage={"completion": 10},
        run=lambda _m: "done",
    )
    ui = _ui()
    agent_repl.run_turn(engine, ui, [], "task", None)
    renderer.begin_turn.assert_called_once()
    renderer.end_turn.assert_called_once_with(usage_tokens=0)

    def fail(_messages):
        raise ValueError("boom")

    engine.run = fail
    with pytest.raises(ValueError):
        agent_repl.run_turn(engine, ui, [], "task", None)
    renderer.abort_turn.assert_called_once()


def test_repl_exit_words_unknown_errors_and_degraded_notice(tmp_path: Path) -> None:
    def run_with(inputs, run, **extra):
        ui = _ui()
        ui.agent_prompt.side_effect = inputs
        engine = SimpleNamespace(
            workspace_root=tmp_path,
            model="m",
            num_ctx=100,
            run=run,
            policy=ApprovalPolicy(),
            todos=TodoStore(),
            **extra,
        )
        code = agent_repl.run_repl(SimpleNamespace(model="m"), MagicMock(), ui, None, engine, _Session(), "s", [])  # type: ignore[arg-type]
        return code, ui

    code, ui = run_with(["", "   ", "quit"], lambda _m: "never")
    assert code == 0 and ui.info.call_args.args[0] == "bye."

    def explode(_messages):
        raise RuntimeError("ollama is down")

    code, ui = run_with(["do it", "/exit"], explode)
    assert code == 0
    ui.failure.assert_called_once()
    assert any("Is TrinaxAI running?" in str(call.args[0]) for call in ui.info.call_args_list)

    code, ui = run_with(["do it", "/exit"], lambda _m: "partial", completion_status="degraded")
    assert code == 0
    assert any("degraded" in str(call.args[0]) for call in ui.warn.call_args_list)

    code, ui = run_with([KeyboardInterrupt()], lambda _m: "x")
    assert code == 0 and ui.info.call_args.args[0] == "\nbye."
