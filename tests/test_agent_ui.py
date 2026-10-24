"""Claude-Code-style agent CLI: permissions, rendering, mentions, todos, REPL, one-shot."""

from __future__ import annotations

import io
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from trinaxai_agent import AgentEngine, Tool
from trinaxai_cli.agent_ui import (
    MODE_ACCEPT_EDITS,
    MODE_DEFAULT,
    MODE_PLAN,
    MODE_YOLO,
    AgentRenderer,
    ApprovalPolicy,
    TodoStore,
    build_diff,
    build_todo_tool,
    command_rule,
    expand_file_mentions,
    load_project_instructions,
    normalize_mode,
    summarize_result,
    tool_title,
)
from trinaxai_cli.commands import agent, agent_repl
from trinaxai_cli.session import Session
from trinaxai_cli.ui import Console


def _tool(name: str, dangerous: bool = False) -> Tool:
    return Tool(name, name, {}, lambda *_a, **_k: "ok", dangerous)


# ------------------------------------------------------------------ policy


@pytest.mark.parametrize(
    ("command", "rule"),
    [
        ("ls -la", "ls"),
        ("rg TODO src", "rg"),
        ("rg --pre ./evil TODO", "rg --pre ./evil TODO"),
        ("rg --search-zip x", "rg --search-zip x"),
        ("rg -iz TODO", "rg -iz TODO"),
        ("rg -n TODO", "rg"),
        ("pytest -q", "pytest -q"),
        ("mypy .", "mypy ."),
        ("git status --short", "git status"),
        ("git diff --stat", "git diff"),
        ("git diff --output=/tmp/x", "git diff --output=/tmp/x"),
        ("git -c core.pager=sh log", "git -c core.pager=sh log"),
        ("git push --force", "git push --force"),
        ("python -m pytest tests", "python -m pytest tests"),
        ("find . -exec rm {} +", "find . -exec rm {} +"),
        ("env sh", "env sh"),
        ("./pytest", "./pytest"),
        ("/tmp/evil/ls -la", "/tmp/evil/ls -la"),
        ("rm -rf build", "rm -rf build"),
        ("ls; rm -rf /", None),
        ("cat a | sh", None),
        ("echo $(whoami)", None),
        ("", None),
    ],
)
def test_command_rule_never_remembers_compound_commands(command: str, rule: str | None) -> None:
    assert command_rule(command) == rule


def test_policy_modes_and_remembered_rules() -> None:
    edit, shell, read = _tool("edit_file", True), _tool("run_command", True), _tool("read_file")
    policy = ApprovalPolicy()
    assert policy.auto_decision(edit, {}) is None

    policy.remember(shell, {"command": "ls -la"})
    assert policy.auto_decision(shell, {"command": "ls src"}) is True
    assert policy.auto_decision(shell, {"command": "ls; rm -rf ."}) is None
    # Runners that execute workspace code are remembered verbatim, never by program.
    policy.remember(shell, {"command": "pytest -q"})
    assert policy.auto_decision(shell, {"command": "pytest -q"}) is True
    assert policy.auto_decision(shell, {"command": "pytest tests/agent_wrote_this.py"}) is None
    assert policy.auto_decision(shell, {"command": "rm -rf ."}) is None

    policy.remember(edit, {"path": "a"})
    assert policy.mode == MODE_ACCEPT_EDITS
    assert policy.auto_decision(edit, {}) is True
    assert policy.auto_decision(shell, {"command": "make build"}) is None
    assert policy.auto_decision(shell, {"command": "./pytest"}) is None

    policy.mode = MODE_PLAN
    assert policy.auto_decision(edit, {}) is False
    policy.mode = MODE_YOLO
    assert policy.auto_decision(shell, {"command": "anything"}) is True
    assert policy.auto_decision(read, {}) is True


def test_policy_cycle_skips_yolo_and_recovers() -> None:
    policy = ApprovalPolicy()
    assert [policy.cycle() for _ in range(4)] == [MODE_ACCEPT_EDITS, MODE_PLAN, MODE_DEFAULT, MODE_ACCEPT_EDITS]
    policy.mode = MODE_YOLO
    assert policy.cycle() == MODE_DEFAULT  # leaving yolo never lands back on it


def test_normalize_mode() -> None:
    assert normalize_mode("accept_edits") == MODE_ACCEPT_EDITS
    assert normalize_mode("bogus") == MODE_DEFAULT
    assert normalize_mode("plan", yolo=True) == MODE_YOLO


# ------------------------------------------------------------ rendering


def test_tool_title_and_summaries() -> None:
    assert tool_title(_tool("read_file"), {"path": "a.py"}) == "read_file(a.py)"
    assert tool_title(_tool("grep"), {"pattern": "x", "path": "src"}) == "grep(x in src)"
    assert tool_title(_tool("custom"), {"a": 1}) == "custom(a=1)"

    read = "[read_file path=a.py; complete; lines=1-40/40; syntax=valid]\n1\tx"
    assert summarize_result(_tool("read_file"), read) == (["Read 40 lines (of 40)"], False)
    assert summarize_result(_tool("glob"), "a.py\nb.py")[0] == ["2 files"]
    assert summarize_result(_tool("grep"), "no matches for: x")[0] == ["no matches for: x"]
    assert summarize_result(_tool("list_dir"), "a/\nb.py")[0] == ["2 entries"]
    shell, _ = summarize_result(_tool("run_command"), "[exit 0; sandboxed]\n" + "\n".join(str(i) for i in range(20)))
    assert shell[0].startswith("[exit 0") and shell[-1] == "… +12 lines"
    failed = "[tool_status=degraded; tool=x]\nWhat happened: x failed.\nWhy: disk is full\nStill works: y"
    assert summarize_result(_tool("x"), failed) == (["Why: disk is full"], True)


def test_build_diff_uses_real_file_content(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("one\ntwo\nthree\n")
    diff = build_diff(tmp_path, _tool("edit_file"), {"path": "a.py", "old": "two", "new": "2"})
    assert "-two" in diff and "+2" in diff and "@@" in diff
    ambiguous = build_diff(tmp_path, _tool("edit_file"), {"path": "a.py", "old": "zzz", "new": "q"})
    assert ambiguous.startswith("- zzz")
    created = build_diff(tmp_path, _tool("write_file"), {"path": "new.py", "content": "x\n"})
    assert "/dev/null" in created and "+x" in created
    assert build_diff(tmp_path, _tool("write_file"), {"path": "a.py", "content": "one\ntwo\nthree\n"}) == "(no changes)"
    assert build_diff(tmp_path, _tool("write_file"), {"path": "../../etc/x", "content": "y"})  # sandbox: no crash


def test_ui_say_does_not_eat_bracketed_text(capsys: pytest.CaptureFixture[str]) -> None:
    console = Console(no_color=True)
    console.say("keep [bold]this[/bold] and [red]that[/red]")
    console.stream("[tail]")
    out = capsys.readouterr().out
    assert "[bold]this[/bold]" in out and "[red]that[/red]" in out and out.endswith("[tail]")


def test_choose_parses_numbers_labels_default_and_cancel(monkeypatch: pytest.MonkeyPatch) -> None:
    console = Console(no_color=True)
    options = [("yes", "Yes"), ("always", "Always"), ("no", "No")]
    for typed, expected in [("2", "always"), ("", "yes"), ("n", "no"), ("q", None), ("9", None), ("zzz", None)]:
        monkeypatch.setattr("builtins.input", lambda _prompt, typed=typed: typed)
        assert console.choose("Allow?", options) == expected
    monkeypatch.setattr("builtins.input", lambda _prompt: (_ for _ in ()).throw(EOFError))
    assert console.choose("Allow?", options) is None


def _renderer(tmp_path: Path, **kwargs):
    ui = MagicMock()
    ui.language = "en"
    policy = kwargs.pop("policy", ApprovalPolicy())
    return ui, policy, AgentRenderer(ui, policy, workspace_root=tmp_path, **kwargs)


def test_renderer_confirm_flow(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x\n")
    ui, policy, renderer = _renderer(tmp_path)
    edit = _tool("edit_file", True)
    args = {"path": "a.py", "old": "x", "new": "y"}

    ui.choose.return_value = "no"
    assert renderer.on_confirm(edit, args) is False
    ui.code.assert_called()  # a diff was shown before asking

    ui.choose.return_value = "always"
    assert renderer.on_confirm(edit, args) is True
    assert policy.mode == MODE_ACCEPT_EDITS
    ui.choose.reset_mock()
    assert renderer.on_confirm(edit, args) is True
    ui.choose.assert_not_called()  # remembered: no more prompts


def test_renderer_plan_mode_blocks_and_noninteractive_refuses(tmp_path: Path) -> None:
    ui, policy, renderer = _renderer(tmp_path, policy=ApprovalPolicy(mode=MODE_PLAN))
    assert renderer.on_confirm(_tool("write_file", True), {"path": "a"}) is False
    ui.choose.assert_not_called()

    ui2, _policy2, silent = _renderer(tmp_path, interactive=False)
    assert silent.on_confirm(_tool("run_command", True), {"command": "ls"}) is False
    ui2.choose.assert_not_called()


def test_renderer_turn_transcript_and_quiet_mode(tmp_path: Path) -> None:
    ui, _policy, renderer = _renderer(tmp_path)
    renderer.begin_turn()
    renderer.on_tool_start(_tool("read_file"), {"path": "a.py"})
    renderer.on_tool_result(_tool("read_file"), "[read_file path=a.py; complete; lines=1-2/2]\n1\ta")
    renderer.on_token("hello")
    renderer.end_turn(usage_tokens=7)
    said = [call.args[0] for call in ui.say.call_args_list if call.args]
    assert "● read_file(a.py)" in said
    assert any(line.startswith("  ⎿ Read 2 lines") for line in said)
    assert any(line.startswith("✻ ") and "1 tool call" in line and "7 tokens" in line for line in said)

    ui_q, _p, quiet = _renderer(tmp_path, quiet=True)
    quiet.begin_turn()
    quiet.on_tool_start(_tool("read_file"), {"path": "a.py"})
    quiet.on_token("answer")
    quiet.end_turn()
    ui_q.say.assert_not_called()
    ui_q.stream.assert_not_called()
    assert quiet.tool_calls == 1


# ---------------------------------------------------------------- todos


def test_todo_tool_normalizes_and_renders(tmp_path: Path) -> None:
    store = TodoStore()
    tool = build_todo_tool(store)
    result = tool.handler(
        tmp_path,
        todos=[
            {"content": "a", "status": "in_progress"},
            {"content": "b", "status": "weird"},
            "c",
            {"content": ""},
        ],
    )
    assert result == "Todos updated: 0/3 completed."
    assert [i["status"] for i in store.items] == ["in_progress", "pending", "pending"]
    assert tool.handler(tmp_path, todos='[{"content":"x","status":"completed"}]') == "Todos updated: 1/1 completed."
    assert tool.handler(tmp_path, todos=42).startswith("error:")

    ui, _policy, renderer = _renderer(tmp_path, todos=store)
    renderer.on_tool_result(tool, "Todos updated")
    lines = [call.args[0] for call in ui.say.call_args_list]
    assert lines == ["  ⎿ ☒ x"]


# ------------------------------------------------- project context & @files


def test_project_instructions_dedupe_symlink_and_clip(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text("Use pytest.\n")
    (tmp_path / "CLAUDE.md").symlink_to(tmp_path / "AGENTS.md")
    block, names = load_project_instructions(tmp_path)
    assert names == ["AGENTS.md"] and "Use pytest." in block

    (tmp_path / "TRINAXAI.md").write_text("x" * 20_000)
    block, names = load_project_instructions(tmp_path)
    assert names == ["TRINAXAI.md"] or names[0] == "TRINAXAI.md"
    assert len(block) < 9_500 and "[... clipped]" in block
    assert load_project_instructions(tmp_path / "missing") == ("", [])


def test_file_mentions_attach_only_workspace_files(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("print(1)\n")
    (tmp_path / "bin.dat").write_bytes(b"\x00\x01\x02")
    task = "fix @src/a.py, see @src and @bin.dat plus @../outside and mail me@example.com @nothing"
    expanded, attached = expand_file_mentions(task, tmp_path)
    assert [rel for rel, _ in attached] == ["src/a.py", "src"]
    assert '<attached file="src/a.py">' in expanded and "print(1)" in expanded
    assert '<attached directory="src">' in expanded
    assert "outside" not in expanded.split("</attached>")[-1].replace(task, "")
    assert expand_file_mentions("no mentions here", tmp_path) == ("no mentions here", [])


# ---------------------------------------------------------- engine additions


def test_engine_usage_and_compact(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    engine = AgentEngine(model="m", workspace_root=tmp_path)
    monkeypatch.setattr(
        engine,
        "_post",
        lambda url, payload, **_k: {"message": {"content": "SUMMARY"}, "prompt_eval_count": 5, "eval_count": 3},
    )
    messages = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "yo"}]
    assert engine.compact(messages) == "SUMMARY"
    assert engine.usage == {"prompt": 5, "completion": 3, "requests": 1}
    assert len(messages) == 2 and "SUMMARY" in messages[0]["content"]
    assert engine.estimate_context_tokens(messages) > 0

    monkeypatch.setattr(engine, "_post", lambda *_a, **_k: {"error": "boom"})
    before = [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}]
    snapshot = list(before)
    assert engine.compact(before) is None and before == snapshot
    assert engine.compact([{"role": "user", "content": "only"}]) is None


def test_user_denied_action_is_not_reported_as_degraded(tmp_path: Path) -> None:
    class Denying(AgentEngine):
        replies = [
            {"tool_calls": [{"function": {"name": "write_file", "arguments": {"path": "a", "content": "x"}}}]},
            {"content": "Understood, I will not write it."},
        ]

        def _chat(self, messages):
            return self.replies.pop(0)

    engine = Denying(model="m", workspace_root=tmp_path, on_confirm=lambda _t, _a: False)
    answer = engine.run([{"role": "user", "content": "write a"}])
    assert answer == "Understood, I will not write it."
    assert not (tmp_path / "a").exists()


# ------------------------------------------------------------- session


def test_session_list_recent(tmp_path: Path) -> None:
    with Session("agent-one", tmp_path) as one:
        one.append("user", "first task")
        one.append("assistant", "done")
    with Session("chat-two", tmp_path) as two:
        two.append("user", "ignored")
    recent = Session.list_recent("agent-", tmp_path)
    assert [item["name"] for item in recent] == ["agent-one"]
    assert recent[0]["turns"] == 1 and recent[0]["preview"] == "first task"
    assert Session.list_recent("", tmp_path / "missing") == []


# ---------------------------------------------------- run_turn and the REPL


class _FakeSession:
    def __init__(self) -> None:
        self.entries: list[tuple[str, str]] = []

    def append(self, role: str, content: str) -> None:
        self.entries.append((role, content))


def _engine(tmp_path: Path, run, **extra):
    return SimpleNamespace(workspace_root=tmp_path, model="m", run=run, num_ctx=8192, **extra)


def test_run_turn_rolls_back_on_interrupt(tmp_path: Path) -> None:
    ui = MagicMock()
    ui.language = "en"
    messages = [{"role": "user", "content": "old"}, {"role": "assistant", "content": "old answer"}]

    def interrupted(msgs):
        msgs.append({"role": "assistant", "content": "", "tool_calls": [{}]})
        raise KeyboardInterrupt

    engine = _engine(tmp_path, interrupted, cancel=MagicMock())
    with pytest.raises(KeyboardInterrupt):
        agent_repl.run_turn(engine, ui, messages, "new task", _FakeSession())
    assert [m["content"] for m in messages] == ["old", "old answer"]
    engine.cancel.assert_called_once()


def test_run_turn_attaches_mentions_and_plan_suffix(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x = 1\n")
    seen: list[str] = []
    engine = _engine(
        tmp_path,
        lambda msgs: seen.append(msgs[-1]["content"]) or "ok",
        policy=ApprovalPolicy(mode=MODE_PLAN),
    )
    ui, session, messages = MagicMock(), _FakeSession(), []
    assert agent_repl.run_turn(engine, ui, messages, "explain @a.py", session) == "ok"
    assert "x = 1" in seen[0] and "Plan mode is ON" in seen[0]
    assert session.entries == [("user", "explain @a.py"), ("assistant", "ok")]  # raw text is logged


def _run_repl(tmp_path: Path, inputs: list[str], engine=None, **args):
    ui = MagicMock()
    ui.language = "en"
    ui.agent_prompt.side_effect = inputs
    engine = engine or _engine(tmp_path, lambda _m: "answer", policy=ApprovalPolicy(), todos=TodoStore())
    messages: list = []
    code = agent_repl.run_repl(
        SimpleNamespace(model=None, **args), MagicMock(), ui, None, engine, _FakeSession(), "agent-x", messages
    )
    return code, ui, engine, messages


def test_repl_slash_commands(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(agent, "_resolve_model", lambda *_a, **_k: "routed")
    code, ui, engine, messages = _run_repl(
        tmp_path,
        [
            "/mode accept-edits",
            "/mode nope",
            "/yolo",
            "/yolo",
            "/todos",
            "/status",
            "/tools",
            "/bogus",
            "hi",
            "/clear",
            "/exit",
        ],
    )
    assert code == 0
    assert engine.policy.mode == MODE_DEFAULT  # yolo toggled on then off
    assert engine.model == "routed" and messages == []  # routed model used, /clear emptied history
    warnings = " ".join(str(call.args[0]) for call in ui.warn.call_args_list)
    assert "Unknown mode" in warnings and "Unknown command /bogus" in warnings and "yolo" in warnings
    assert any("Permissions:" in str(call.args[0]) for call in ui.say.call_args_list)


def test_repl_model_pin_and_path_like_input(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from trinaxai_cli.commands import chat_slash

    monkeypatch.setattr(chat_slash, "_select_model", lambda _c, _u, arg="": "pinned:1b")
    monkeypatch.setattr(agent, "_resolve_model", lambda *_a, **_k: "should-not-be-used")
    seen: list[str] = []
    engine = _engine(
        tmp_path, lambda m: seen.append(m[-1]["content"]) or "ok", policy=ApprovalPolicy(), todos=TodoStore()
    )
    _code, _ui, engine, _messages = _run_repl(tmp_path, ["/model", "/usr/bin/env is what?", "/exit"], engine=engine)
    assert engine.model == "pinned:1b"
    assert seen == ["/usr/bin/env is what?"]  # a path is a task, not an unknown command


def test_repl_init_sends_prompt_and_interrupt_recovers(tmp_path: Path) -> None:
    calls: list[str] = []

    def run(msgs):
        calls.append(msgs[-1]["content"])
        if len(calls) == 1:
            raise KeyboardInterrupt
        return "created"

    engine = _engine(tmp_path, run, policy=ApprovalPolicy(), todos=TodoStore())
    ui = MagicMock()
    ui.language = "en"
    ui.agent_prompt.side_effect = ["/init", "again", "/exit"]
    messages: list = []
    code = agent_repl.run_repl(SimpleNamespace(model="x"), MagicMock(), ui, None, engine, _FakeSession(), "s", messages)
    assert code == 0
    assert calls[0].startswith("Analyze this workspace") and calls[1] == "again"
    ui.warn.assert_any_call("\ninterrupted.")
    assert [m["content"] for m in messages] == ["again"]  # the interrupted request was rolled back


def test_repl_compact_and_diff(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    engine = _engine(tmp_path, lambda _m: "ok", policy=ApprovalPolicy(), todos=TodoStore(), compact=lambda m: "S")
    code, ui, _e, _m = _run_repl(tmp_path, ["/compact", "/diff", "/exit"], engine=engine)
    assert code == 0
    ui.info.assert_any_call("Nothing to compact yet.")  # empty history
    ui.info.assert_any_call("Not a git repository.")


def test_repl_eof_exits_cleanly(tmp_path: Path) -> None:
    code, ui, *_ = _run_repl(tmp_path, [EOFError()])
    assert code == 0
    ui.info.assert_any_call("\nbye.")


# -------------------------------------------------------- one-shot & resume


def test_one_shot_json_output(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    renderer = AgentRenderer(MagicMock(), ApprovalPolicy(), quiet=True)
    renderer.tool_calls = 2
    engine = _engine(
        tmp_path,
        lambda _m: (
            renderer.on_tool_start(_tool("read_file"), {"path": "a"})
            or renderer.on_tool_start(_tool("read_file"), {"path": "b"})
            or "the answer"
        ),
        renderer=renderer,
        usage={"prompt": 10, "completion": 4},
        completion_status="complete",
    )
    monkeypatch.setattr(agent, "_build_engine", lambda *_a: engine)
    monkeypatch.setattr(agent, "Session", lambda _n: _FakeCtx())
    ui = MagicMock()
    code = agent.run(
        SimpleNamespace(prompt="do it", session="s", output_format="json", resume=None, continue_last=False),
        None,
        ui,
        None,
    )
    assert code == 0
    payload = json.loads(ui.say.call_args.args[0])
    assert payload["result"] == "the answer" and payload["status"] == "complete"
    assert payload["tool_calls"] == 2 and payload["session"] == "s"


class _FakeCtx(_FakeSession):
    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return None


def test_task_sources_and_resume(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    assert agent._task_from_args(SimpleNamespace(prompt="p", task=["x"])) == "p"
    assert agent._task_from_args(SimpleNamespace(prompt=None, task=["fix", "it"])) == "fix it"
    monkeypatch.setattr("sys.stdin", io.StringIO("  piped task \n"))
    assert agent._task_from_args(SimpleNamespace(prompt=None, task=[], read_stdin=True)) == "piped task"
    assert agent._task_from_args(SimpleNamespace(prompt=None)) == ""

    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    with Session("agent-old") as old:
        old.append("user", "earlier")
        old.append("assistant", "reply")
    name, history = agent._load_resume(SimpleNamespace(resume=None, continue_last=True))
    assert name == "agent-old" and history == [
        {"role": "user", "content": "earlier"},
        {"role": "assistant", "content": "reply"},
    ]
    assert agent._load_resume(SimpleNamespace(resume=None, continue_last=False)) == (None, [])


def test_build_engine_wires_policy_todos_and_instructions(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text("Always run make test.\n")
    monkeypatch.setattr(agent._system, "env_value", lambda _k: None)
    ui = MagicMock()
    ui.language = "en"
    engine = agent._build_engine(
        SimpleNamespace(
            invocation_cwd=str(tmp_path),
            workspace=".",
            max_steps=3,
            prompt=None,
            model="m",
            permission_mode="accept-edits",
            output_format="text",
        ),
        ui,
        False,
        SimpleNamespace(NUM_CTX=8192),
    )
    assert engine.policy.mode == MODE_ACCEPT_EDITS
    assert "todo_write" in {t.name for t in engine.tools}
    assert "Always run make test." in engine.system_prompt and engine.project_files == ["AGENTS.md"]
    assert engine.renderer.todos is engine.todos and engine.renderer.workspace_root == tmp_path.resolve()

    yolo = agent._build_engine(
        SimpleNamespace(invocation_cwd=str(tmp_path), workspace=".", prompt=None, model="m"), ui, True, None
    )
    assert yolo.on_confirm is None and yolo.policy.mode == MODE_YOLO


def test_unified_chat_agent_turn_uses_shared_renderer(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from trinaxai_cli.commands import chat
    from trinaxai_cli.commands.chat_state import ChatState

    monkeypatch.setattr(agent._system, "env_value", lambda _k: None)
    ui = MagicMock()
    ui.language = "en"
    state = ChatState(workspace=str(tmp_path), model="m")
    built = {}
    real_build = agent.build_agent_engine

    def spy(*a, **kw):
        engine = real_build(*a, **kw)
        engine.run = lambda msgs: "chat agent answer"
        built["engine"] = engine
        return engine

    monkeypatch.setattr(agent, "build_agent_engine", spy)
    assert chat._run_agent_turn(state, MagicMock(), ui, "task", SimpleNamespace(NUM_CTX=8192)) == "chat agent answer"
    engine = built["engine"]
    assert engine.renderer is not None and engine.policy is not None
    state.yolo = True
    ui.choose.assert_not_called()
    assert engine.on_confirm(_tool("write_file", True), {"path": "a"}) is True  # /yolo still honoured live


def test_phantom_edit_claim_forces_a_real_attempt(tmp_path: Path) -> None:
    (tmp_path / "calc.py").write_text("def add(a, b):\n    return a - b\n")
    edit = {"function": {"name": "edit_file", "arguments": {"path": "calc.py", "old": "a - b", "new": "a + b"}}}

    class Lazy(AgentEngine):
        replies = [
            {"tool_calls": [{"function": {"name": "read_file", "arguments": {"path": "calc.py"}}}]},
            {"content": "I fixed it.\n\n**Change made:** replaced a - b with a + b."},  # claims, did nothing
            {"tool_calls": [edit]},
            {"content": "I changed `add` to return a + b."},
        ]

        def _chat(self, messages):
            return self.replies.pop(0)

    engine = Lazy(model="m", workspace_root=tmp_path, on_confirm=None)
    answer = engine.run([{"role": "user", "content": "Fix the bug in add in calc.py"}])
    assert "a + b" in (tmp_path / "calc.py").read_text()
    assert answer == "I changed `add` to return a + b."

    # A question (no change requested) or an honest read-only answer is left alone.
    class Reader(AgentEngine):
        replies = [
            {"tool_calls": [{"function": {"name": "read_file", "arguments": {"path": "calc.py"}}}]},
            {"content": "It adds two numbers."},
        ]

        def _chat(self, messages):
            return self.replies.pop(0)

    assert Reader(model="m", workspace_root=tmp_path).run([{"role": "user", "content": "What does calc.py do?"}]) == (
        "It adds two numbers."
    )


def test_failed_exploratory_read_is_not_appended_to_the_answer(tmp_path: Path) -> None:
    class Explorer(AgentEngine):
        replies = [
            {"tool_calls": [{"function": {"name": "read_file", "arguments": {"path": "missing.py"}}}]},
            {"tool_calls": [{"function": {"name": "write_file", "arguments": {"path": "../out", "content": "x"}}}]},
            {"content": "Done; the file did not exist so I skipped it."},
        ]

        def _chat(self, messages):
            return self.replies.pop(0)

    engine = Explorer(model="m", workspace_root=tmp_path, on_confirm=None)
    answer = engine.run([{"role": "user", "content": "look around"}])
    assert "What happened:" in answer  # the failed write (a real problem) is still reported
    assert "missing.py" not in answer  # the routine missing-file read is not

    class ReadOnly(Explorer):
        replies = [
            {"tool_calls": [{"function": {"name": "read_file", "arguments": {"path": "missing.py"}}}]},
            {"content": "There is no such file."},
        ]

    assert ReadOnly(model="m", workspace_root=tmp_path).run([{"role": "user", "content": "x"}]) == (
        "There is no such file."
    )


def test_workspace_code_rules_expire_after_an_edit_but_passive_rules_do_not() -> None:
    edit, shell = _tool("edit_file", True), _tool("run_command", True)
    policy = ApprovalPolicy()
    policy.remember(shell, {"command": "ls"})
    policy.remember(shell, {"command": "make test"})
    policy.remember(shell, {"command": "git status"})
    assert policy.auto_decision(shell, {"command": "make test"}) is True

    # The Agent edits a file (even when the user approves it by hand).
    policy.auto_decision(edit, {"path": "tests/test_new.py"})
    assert policy.auto_decision(shell, {"command": "make test"}) is None
    # git reads the repository's own config, which the Agent can edit: not passive.
    assert policy.auto_decision(shell, {"command": "git status"}) is None
    assert policy.auto_decision(shell, {"command": "ls src"}) is True

    # Re-approving one command must not silently re-arm the others.
    policy.remember(shell, {"command": "pytest -q"})
    assert policy.auto_decision(shell, {"command": "pytest -q"}) is True
    assert policy.auto_decision(shell, {"command": "make test"}) is None
    assert policy.auto_decision(shell, {"command": "git status"}) is None


def test_slash_diff_ignores_agent_written_git_config(tmp_path: Path) -> None:
    import shutil
    import subprocess

    from trinaxai_cli.commands.agent_repl import _git_diff

    if shutil.which("git") is None:
        pytest.skip("git is not installed")
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / "a.txt").write_text("one\n")
    marker = tmp_path / "ran"
    hook = tmp_path / "hook.sh"
    hook.write_text(f"#!/bin/sh\ntouch {marker}\n")
    hook.chmod(0o755)
    with (repo / ".git" / "config").open("a") as config:
        # as_posix: backslashes are escapes in git config and would make the file unparseable on Windows
        config.write(f"[core]\n\tfsmonitor = {hook.as_posix()}\n[diff]\n\texternal = {hook.as_posix()}\n")

    result = _git_diff(repo, "--stat")

    assert result.returncode == 0, result.stderr
    assert not marker.exists(), "/diff executed a program named in the workspace's .git/config"


def test_a_real_edit_is_not_second_guessed_as_a_phantom_claim(tmp_path: Path) -> None:
    (tmp_path / "calc.py").write_text("def add(a, b):\n    return a - b\n")
    edit = {"function": {"name": "edit_file", "arguments": {"path": "calc.py", "old": "a - b", "new": "a + b"}}}

    class Honest(AgentEngine):
        replies = [
            {"tool_calls": [{"function": {"name": "read_file", "arguments": {"path": "calc.py"}}}]},
            {"tool_calls": [edit]},
            {"content": "I fixed it: add now returns a + b."},
        ]

        def _chat(self, messages):
            return self.replies.pop(0)  # an unexpected extra nudge would run out of replies

    engine = Honest(model="m", workspace_root=tmp_path, on_confirm=None)
    answer = engine.run([{"role": "user", "content": "Fix the bug in add in calc.py"}])
    assert answer == "I fixed it: add now returns a + b."
    assert "a + b" in (tmp_path / "calc.py").read_text()


def test_the_agent_is_asked_once_to_run_what_it_was_asked_to_run(tmp_path: Path) -> None:
    write = {"function": {"name": "write_file", "arguments": {"path": "primos.py", "content": "x = 1\n"}}}
    seen: list[list[dict]] = []

    class Skipper(AgentEngine):
        replies = [
            {"tool_calls": [write]},
            {"content": "Created primos.py."},  # never ran anything
            {"content": "Created primos.py, I did not run it."},
        ]

        def _chat(self, messages):
            seen.append([dict(m) for m in messages])
            return self.replies.pop(0)

    task = "Create primos.py with is_prime and run the tests"
    answer = Skipper(model="m", workspace_root=tmp_path, on_confirm=None).run([{"role": "user", "content": task}])
    assert answer == "Created primos.py, I did not run it."
    assert any("no command has been run yet" in str(m.get("content")) for m in seen[-1])

    # Without a request to run anything, nothing extra is asked.
    seen.clear()
    Skipper.replies = [{"tool_calls": [write]}, {"content": "Created primos.py."}]
    quiet = Skipper(model="m", workspace_root=tmp_path, on_confirm=None).run(
        [{"role": "user", "content": "Create primos.py with is_prime"}]
    )
    assert quiet == "Created primos.py."
    assert not any("no command has been run yet" in str(m.get("content")) for m in seen[-1])


def test_one_file_request_ends_after_the_write_but_a_bigger_request_does_not(tmp_path: Path) -> None:
    from trinaxai_agent.engine import _is_simple_file_creation as simple

    def ask(text: str) -> list[dict]:
        return [{"role": "user", "content": text}]

    assert simple(ask("Crea un archivo clima.md que explique el calentamiento global"))
    assert simple(ask("create a file notes.md with a todo list"))
    for bigger in (
        "Crea un archivo primos.py con es_primo y un archivo test_primos.py con pruebas. Ejecuta las pruebas.",
        "Crea un archivo index.html y otro style.css",
        "write a file a.py and run it",
        "Crea un archivo app.py y pruébalo",
    ):
        assert not simple(ask(bigger)), bigger
