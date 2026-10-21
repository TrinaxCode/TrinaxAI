"""Edge cases of the agent terminal UI helpers: rules, todos, instructions, mentions and rendering."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from trinaxai_agent import Tool
from trinaxai_cli import agent_ui
from trinaxai_cli.agent_ui import (
    AgentRenderer,
    ApprovalPolicy,
    TodoStore,
    build_diff,
    command_rule,
    expand_file_mentions,
    load_project_instructions,
    summarize_result,
    tool_title,
)


def _tool(name: str, dangerous: bool = False) -> Tool:
    return Tool(name, name, {}, lambda *_a, **_k: "ok", dangerous)


def test_command_rule_rejects_unparseable_and_blank_commands() -> None:
    assert command_rule('echo "unterminated') is None  # shlex cannot split it
    assert command_rule("   ") is None


def test_rule_for_non_shell_tools_is_the_tool_name_and_unparseable_commands_are_never_remembered() -> None:
    policy = ApprovalPolicy()
    assert policy.rule_for(_tool("web_search", True), {}) == "web_search"
    shell = _tool("run_command", True)
    assert policy.rule_for(shell, {"command": "ls; rm -rf /"}) is None
    assert policy.remember(shell, {"command": "ls; rm -rf /"}) is None
    assert policy.remember(_tool("web_search", True), {}) == "web_search"
    assert policy.auto_decision(_tool("web_search", True), {}) is True


def test_todo_store_accepts_json_text_plain_lists_and_rejects_other_shapes() -> None:
    store = TodoStore()
    store.update('[{"content": "ship it", "status": "pending"}]')
    assert [item["content"] for item in store.items] == ["ship it"]
    store.update("- first thing\n* second thing\n\n")  # not JSON: one todo per line
    assert [item["content"] for item in store.items] == ["first thing", "second thing"]
    with pytest.raises(ValueError):
        store.update(42)


def test_project_instructions_skip_unreadable_empty_and_oversized_files(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "AGENTS.md").write_text("   \n")  # empty after strip
    (tmp_path / "CLAUDE.md").write_text("Use tabs.\n")
    block, names = load_project_instructions(tmp_path)
    assert names == ["CLAUDE.md"] and "Use tabs." in block

    huge = tmp_path / "TRINAXAI.md"
    huge.write_text("x" * (agent_ui._MAX_INSTRUCTION_CHARS + 500))
    block, names = load_project_instructions(tmp_path)
    assert "TRINAXAI.md" in names and "[... clipped]" in block

    original = Path.read_text

    def unreadable(self, *args, **kwargs):
        if self.name == "CLAUDE.md":
            raise OSError("denied")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", unreadable)
    _block, names = load_project_instructions(tmp_path)
    assert "CLAUDE.md" not in names

    empty = tmp_path / "empty"
    empty.mkdir()
    assert load_project_instructions(empty) == ("", [])


def test_file_mentions_skip_duplicates_binaries_oversized_files_and_clip_long_text(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("line one\nline two\n")
    (tmp_path / "bin.dat").write_bytes(b"\x00\x01")
    (tmp_path / "big.txt").write_text("y" * (agent_ui._MAX_MENTION_CHARS + 100))
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "visible.py").write_text("x")
    (tmp_path / "sub" / ".hidden").write_text("x")

    expanded, attached = expand_file_mentions("see @a.txt and @a.txt again, @bin.dat, @sub, @big.txt", tmp_path)
    assert [rel for rel, _ in attached] == ["a.txt", "sub", "big.txt"]  # duplicate + binary dropped
    assert expanded.count('<attached file="a.txt">') == 1
    assert "visible.py" in expanded and ".hidden" not in expanded
    assert "[... clipped 100 chars]" in expanded

    # Past the total budget nothing else is attached.
    many = {f"f{n}.txt": "z" * 20_000 for n in range(6)}
    for name, body in many.items():
        (tmp_path / name).write_text(body)
    _expanded, attached = expand_file_mentions(" ".join(f"@{name}" for name in many), tmp_path)
    assert 0 < len(attached) < len(many)


def test_tool_title_and_result_summaries_cover_every_tool_family() -> None:
    assert tool_title(_tool("grep"), {"pattern": "TODO", "path": "src"}) == "grep(TODO in src)"
    assert tool_title(_tool("read_file"), {"path": "a.py", "offset": 4}) == "read_file(a.py [5…])"
    assert tool_title(_tool("todo_write"), {"todos": []}) == "todo_write()"
    assert tool_title(_tool("mystery"), {"a": 1, "b": "two"}) == "mystery(a=1, b=two)"

    shell = _tool("run_command")
    lines, failed = summarize_result(shell, "[exit 0; sandboxed]\n" + "\n".join(f"out {n}" for n in range(12)))
    assert not failed and lines[0].startswith("[exit 0") and lines[-1] == "… +4 lines"
    assert summarize_result(shell, "[exit 0; sandboxed]")[0] == ["[exit 0; sandboxed]"]
    assert summarize_result(shell, "")[0] == ["done"]

    assert summarize_result(_tool("todo_write"), "")[0] == ["updated"]
    assert summarize_result(_tool("todo_write"), "3 todos\nrest")[0] == ["3 todos"]
    assert summarize_result(_tool("glob"), "a\nb\n... truncated")[0] == ["2 files"]
    assert summarize_result(_tool("grep"), "only\n")[0] == ["1 match"]
    assert summarize_result(_tool("grep"), "a\nb")[0] == ["2 matches"]
    assert summarize_result(_tool("other"), "\n\nfirst\nsecond")[0] == ["first (+3 lines)"]


def test_build_diff_handles_new_files_replacements_and_long_diffs(tmp_path: Path) -> None:
    write, edit = _tool("write_file", True), _tool("edit_file", True)
    (tmp_path / "f.txt").write_text("keep\nold\n")
    assert build_diff(tmp_path, write, {"path": "f.txt", "content": "keep\nold\n"}) == "(no changes)"
    assert "+new" in build_diff(tmp_path, edit, {"path": "f.txt", "old": "old", "new": "new"})
    # old text absent or ambiguous: fall back to a plain before/after preview
    assert build_diff(tmp_path, edit, {"path": "f.txt", "old": "missing", "new": "x"}).startswith("- missing")
    assert build_diff(None, write, {"path": "n.txt", "content": "a"}).startswith("--- /dev/null")
    long = build_diff(tmp_path, write, {"path": "g.txt", "content": "\n".join(str(n) for n in range(200))}, cap=10)
    assert long.splitlines()[-1].startswith("… +") and "more diff lines" in long


def _renderer(*, quiet: bool = False, live: bool = True) -> tuple[AgentRenderer, MagicMock]:
    ui = MagicMock()
    ui.language = "en"
    if not live:
        del ui.live_status
    return AgentRenderer(ui, ApprovalPolicy(), quiet=quiet), ui


def test_renderer_status_line_lifecycle_and_quiet_mode() -> None:
    renderer, ui = _renderer()
    renderer.begin_turn()
    ui.live_status.assert_called_once()
    status = renderer._status
    renderer.on_token("hello")  # first output stops the spinner
    status.stop.assert_called_once()
    assert renderer._mid_line is True

    renderer.begin_turn()
    renderer.abort_turn()  # interrupted: no footer, spinner stopped, line closed
    assert renderer._status is None and renderer._mid_line is False

    renderer, ui = _renderer(live=False)
    renderer.begin_turn()  # a UI without live_status must not crash
    assert renderer._status is None

    quiet, ui = _renderer(quiet=True)
    quiet.begin_turn()
    quiet.on_tool_start(_tool("read_file"), {"path": "a"})
    quiet.on_tool_result(_tool("read_file"), "x")
    quiet.on_token("silent")
    ui.say.assert_not_called()
    assert quiet.tool_calls == 1


def test_renderer_end_turn_footer_lists_tools_and_tokens() -> None:
    renderer, ui = _renderer()
    renderer.begin_turn()
    renderer.tool_calls = 2
    renderer.end_turn(usage_tokens=33)
    footer = str(ui.say.call_args.args[0])
    assert "2 tool calls" in footer and "33 tokens" in footer
    renderer.tool_calls = 1
    renderer.end_turn()
    assert "1 tool call" in str(ui.say.call_args.args[0]) and "calls" not in str(ui.say.call_args.args[0])


# ------------------------------------------------------------ commands.agent


def test_dynamic_callbacks_follow_the_live_yolo_toggle() -> None:
    from trinaxai_cli.commands import agent

    state = {"yolo": True}
    policy = ApprovalPolicy(mode="yolo")
    renderer = MagicMock()
    renderer.on_confirm.return_value = False
    renderer.callbacks.return_value = {"on_confirm": None}
    callbacks = agent.make_dynamic_callbacks(MagicMock(), lambda: state["yolo"], policy, renderer)
    shell = _tool("run_command", True)

    assert callbacks["on_confirm"](shell, {}) is True  # live yolo approves everything
    state["yolo"] = False
    assert callbacks["on_confirm"](shell, {}) is False  # switched off: ask again
    assert policy.mode == "default"  # and the stale yolo mode is dropped


def test_build_agent_engine_takes_callbacks_from_the_caller_the_renderer_or_a_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from trinaxai_cli.commands import agent

    monkeypatch.setattr(agent._system, "env_value", lambda _k: None)
    ui = MagicMock()
    ui.language = "en"
    explicit = agent.build_agent_engine(ui, workspace=str(tmp_path), model="m", num_ctx=2048, callbacks={})
    assert explicit.todos is not None and explicit.renderer is None

    renderer = AgentRenderer(ui, ApprovalPolicy(), quiet=True)
    wired = agent.build_agent_engine(ui, workspace=str(tmp_path), model="m", num_ctx=2048, renderer=renderer)
    assert wired.renderer is renderer and renderer.workspace_root == tmp_path.resolve()

    plain = agent.build_agent_engine(ui, workspace=str(tmp_path), model="m", num_ctx=2048)
    assert plain.policy is None and plain.project_files == []

    with pytest.raises(ValueError):
        agent.build_agent_engine(ui, workspace=str(tmp_path / "missing"), model="m", num_ctx=2048)


def test_task_from_args_ignores_unreadable_stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    from trinaxai_cli.commands import agent

    class Broken:
        def read(self, _size: int) -> str:
            raise OSError("closed")

    monkeypatch.setattr("sys.stdin", Broken())
    assert agent._task_from_args(SimpleNamespace(prompt=None, task=[], read_stdin=True)) == ""


def test_one_shot_reports_interrupts_failures_and_degraded_answers(tmp_path: Path) -> None:
    from trinaxai_cli.commands import agent

    def run_with(behaviour, **engine_extra):
        ui = MagicMock()
        engine = SimpleNamespace(workspace_root=tmp_path, model="m", run=behaviour, **engine_extra)
        session = MagicMock()
        args = SimpleNamespace(output_format="text")
        return agent._run_one_shot(engine, ui, [], "task", session, "s", args), ui

    def interrupted(_messages):
        raise KeyboardInterrupt

    def failing(_messages):
        raise RuntimeError("ollama down")

    code, ui = run_with(interrupted)
    assert code == 130 and "interrupted" in str(ui.warn.call_args.args[0])
    code, ui = run_with(failing)
    assert code == 1 and ui.failure.called
    code, ui = run_with(lambda _m: "partial", completion_status="degraded")
    assert code == 0 and "degraded" in str(ui.warn.call_args.args[0])
    quiet = AgentRenderer(MagicMock(), ApprovalPolicy(), quiet=True)
    code, ui = run_with(lambda _m: "only the answer", renderer=quiet)
    assert code == 0 and ui.say.call_args.args[0] == "only the answer"


# ------------------------------------------------------- approval prompts


def _confirming(mode: str = "default", *, interactive: bool = True, quiet: bool = False):
    ui = MagicMock()
    ui.language = "en"
    policy = ApprovalPolicy(mode=mode)
    return AgentRenderer(ui, policy, quiet=quiet, interactive=interactive), ui, policy


def test_confirm_runs_pre_approved_actions_and_refuses_in_plan_mode() -> None:
    shell = _tool("run_command", True)
    renderer, ui, policy = _confirming("yolo")
    assert renderer.on_confirm(shell, {"command": "rm -rf build"}) is True
    ui.choose.assert_not_called()

    renderer, ui, policy = _confirming("plan")
    assert renderer.on_confirm(shell, {"command": "ls"}) is False
    assert "Plan mode is on: nothing was changed" in str(ui.say.call_args.args[0])
    ui.choose.assert_not_called()

    quiet, ui, _ = _confirming("plan", quiet=True)
    assert quiet.on_confirm(shell, {"command": "ls"}) is False
    ui.say.assert_not_called()


def test_confirm_in_non_interactive_runs_never_asks_and_never_approves() -> None:
    renderer, ui, _policy = _confirming(interactive=False)
    assert renderer.on_confirm(_tool("run_command", True), {"command": "make"}) is False
    ui.choose.assert_not_called()
    assert "action refused" in str(ui.say.call_args.args[0])  # the refusal is explained

    quiet, ui, _ = _confirming(interactive=False, quiet=True)
    assert quiet.on_confirm(_tool("edit_file", True), {"path": "a"}) is False
    ui.say.assert_not_called()


def test_confirm_prompt_offers_yes_always_and_no_and_remembers_the_choice(tmp_path: Path) -> None:
    shell, edit = _tool("run_command", True), _tool("edit_file", True)
    renderer, ui, policy = _confirming()
    renderer.workspace_root = tmp_path
    ui.choose.return_value = "yes"
    assert renderer.on_confirm(shell, {"command": "make test"}) is True
    options = ui.choose.call_args.args[1]
    assert [value for value, _label in options] == ["yes", "always", "no"]
    ui.code.assert_called_with("make test", "bash")
    assert policy.allowed == set()  # a plain yes remembers nothing

    ui.choose.return_value = "always"
    assert renderer.on_confirm(shell, {"command": "make test"}) is True
    assert "run_command:make test" in policy.allowed

    ui.choose.return_value = "no"
    assert renderer.on_confirm(_tool("web_search", True), {"query": "q"}) is False

    ui.choose.return_value = "always"
    (tmp_path / "f.txt").write_text("a\n")
    assert renderer.on_confirm(edit, {"path": "f.txt", "old": "a", "new": "b"}) is True
    assert policy.mode == "accept-edits"  # "always" for edits switches the whole mode
    assert ui.code.call_args.args[1] == "diff"


def test_confirm_prompt_without_a_remembered_rule_offers_only_yes_or_no() -> None:
    renderer, ui, _policy = _confirming()
    ui.choose.return_value = "no"
    assert renderer.on_confirm(_tool("run_command", True), {"command": "echo hi | sh"}) is False  # compound: no rule
    assert [value for value, _label in ui.choose.call_args.args[1]] == ["yes", "no"]
