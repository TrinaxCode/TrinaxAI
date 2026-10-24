"""The Agent's host-side ``git`` tool: validation, risk classes, approvals and real repositories."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from trinaxai_agent import AgentEngine
from trinaxai_agent import tools as agent_tools
from trinaxai_agent.git_tool import (
    LOCAL,
    NETWORK,
    READ,
    GitUsageError,
    classify_git,
    git_argv,
    git_display,
    git_env,
    git_input,
    git_risk,
    hooks_enabled,
    parse_git_args,
)
from trinaxai_agent.tools import SandboxError, build_tool_map
from trinaxai_cli.agent_ui import (
    MODE_ACCEPT_EDITS,
    MODE_PLAN,
    MODE_YOLO,
    AgentRenderer,
    ApprovalPolicy,
    summarize_result,
    tool_title,
)

GIT = shutil.which("git")
needs_git = pytest.mark.skipif(GIT is None, reason="git is not installed")
GIT_TOOL = build_tool_map()["git"]


# ------------------------------------------------------------------ parsing


def test_arguments_accept_lists_and_shell_free_strings() -> None:
    assert parse_git_args(["log", "--oneline", 5]) == ("log", "--oneline", "5")
    assert parse_git_args("commit -m 'two words'") == ("commit", "-m", "two words")
    assert parse_git_args("git status") == ("status",)
    assert parse_git_args(["git", "status"]) == ("status",)
    assert git_input({"args": ["status"], "command": "log"}) == ["status"]
    assert git_input({"command": "log"}) == "log"
    assert git_display({"args": ["commit", "-m", "two words"]}) == "git commit -m 'two words'"
    assert git_display({"args": "a'b"}).startswith("git ")


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "",
        [],
        ["git"],
        "unterminated 'quote",
        {"a": 1},
        [None],
        [True],
        [["nested"]],
        ["a\x00b"],
        ["a"] * 201,
        ["x" * 9000],
    ],
)
def test_unusable_arguments_are_refused(raw) -> None:
    with pytest.raises(GitUsageError):
        parse_git_args(raw)
    assert git_risk(raw) == LOCAL  # never auto-approved


# ----------------------------------------------------------- classification


@pytest.mark.parametrize(
    ("raw", "kind"),
    [
        ("status", READ),
        ("diff HEAD~1 -- src", READ),
        (["log", "--oneline", "-5"], READ),
        ("blame app.py", READ),
        ("grep -n needle", READ),
        ("branch", READ),
        ("branch -a", READ),
        ("branch --sort=-committerdate", READ),
        ("tag", READ),
        ("tag -l v*", READ),
        ("stash list", READ),
        ("remote -v", READ),
        ("remote get-url origin", READ),
        ("add -A", LOCAL),
        (["commit", "-m", "fix: see https://example.test/x"], LOCAL),
        ("switch -c feature", LOCAL),
        ("checkout -b feature", LOCAL),
        ("branch new-feature", LOCAL),
        ("branch -D old", LOCAL),
        ("tag v1.0", LOCAL),
        ("tag -d v1.0", LOCAL),
        ("tag -l -d v1.0", LOCAL),
        ("stash", LOCAL),
        ("stash pop", LOCAL),
        ("reset --hard HEAD~1", LOCAL),
        ("rebase -i HEAD~3", LOCAL),
        ("remote add origin https://github.com/a/b.git", LOCAL),
        ("remote set-url origin git@github.com:a/b.git", LOCAL),
        ("remote rename origin upstream", LOCAL),
        ("init", LOCAL),
        ("push origin main", NETWORK),
        ("push -u origin feature", NETWORK),
        ("pull --rebase", NETWORK),
        ("fetch --all", NETWORK),
        ("remote update", NETWORK),
        ("remote show origin", NETWORK),
    ],
)
def test_commands_are_classified_by_what_they_can_do(raw, kind) -> None:
    assert classify_git(raw).kind == kind
    assert git_risk(raw) == kind


@pytest.mark.parametrize(
    "raw",
    [
        "-c core.pager=evil status",
        "-C /etc status",
        "--git-dir=/etc status",
        "config user.name x",
        "co",
        "clone https://example.test/r.git",
        "submodule update",
        "daemon",
        "diff --output=/tmp/out",
        "diff --no-index /etc/passwd /etc/hosts",
        "blame --contents /etc/passwd app.py",
        "log --ext-diff",
        "diff --textconv",
        "fetch --upload-pack=evil origin",
        "push --receive-pack=evil origin",
        "push --exec=evil origin",
        "pull --recurse-submodules",
        "rebase -x 'sh evil' main",
        "rebase --exec 'sh evil' main",
        "grep -Osh needle",
        "grep --open-files-in-pager=sh needle",
        "init --template=/tmp/hooks",
        "init --separate-git-dir=/tmp/x",
        "log --paginate",
        "push ext::sh -c evil",
        "fetch fd::3",
        "push http://insecure.example/r.git",
        "pull ftp://example.test/r.git",
        "remote add origin ext::sh -c evil",
        "remote add origin http://insecure.example/r.git",
        "remote add origin",
        "remote add -f origin https://example.test/r.git",
        "remote prune-everything",
        # git accepts any unambiguous abbreviation of a long option
        "diff --out=/tmp/out",
        "diff --ext-dif",
        "diff --no-ind /etc/passwd /etc/hosts",
        "fetch --upload-p=evil origin",
        "push --receive-p=evil origin",
        "pull --rec=x",
        "init --templ=/tmp/hooks",
        "log --paginat",
        "blame --content=/etc/passwd app.py",
        # ... and short options may be bundled
        "rebase -ix 'sh evil' main",
        "grep -nO sh needle",
    ],
)
def test_dangerous_invocations_are_refused(raw) -> None:
    with pytest.raises(GitUsageError):
        classify_git(raw)
    assert git_risk(raw) == LOCAL


def test_file_operands_are_collected_so_they_can_be_confined() -> None:
    assert classify_git("commit -F notes.txt").files == ("notes.txt",)
    assert classify_git("commit --file=notes.txt -m x").files == ("notes.txt",)
    assert classify_git("commit -Fnotes.txt").files == ("notes.txt",)
    assert classify_git("commit -t tmpl.txt -m x").files == ("tmpl.txt",)
    assert classify_git("tag -F msg.txt v1").files == ("msg.txt",)
    assert classify_git("grep -f patterns.txt").files == ("patterns.txt",)
    assert classify_git("grep -F fixed").files == ()
    assert classify_git("log -F text").files == ()
    assert classify_git("commit -m x -- -F").files == ()
    # abbreviated long options and bundled short options still name the file
    assert classify_git("commit --fil=/etc/passwd").files == ("/etc/passwd",)
    assert classify_git("commit --file /etc/passwd").files == ("/etc/passwd",)
    assert classify_git("commit --templ=/etc/x").files == ("/etc/x",)
    assert classify_git("commit -aF /etc/passwd").files == ("/etc/passwd",)
    assert classify_git("commit -sFmsg.txt").files == ("msg.txt",)
    assert classify_git("tag -aF m.txt v1").files == ("m.txt",)
    assert classify_git("merge --fi=/e topic").files == ("/e",)
    assert classify_git("grep -nf pat.txt needle").files == ("pat.txt",)
    # the value of -m is a message, not an option
    assert classify_git(["commit", "-m", "-F not a file"]).files == ()
    assert classify_git("commit -am 'fix test'").files == ()
    assert classify_git(["commit", "-F", "-m"]).files == ("-m",)
    assert classify_git("grep -e -O file").files == ()


@pytest.mark.parametrize(
    "raw",
    [
        "switch -c feat",
        "commit --amend --no-edit",
        "push --force-with-lease origin main",
        "log --no-merges --stat",
        "diff --staged --name-only",
        "pull --no-rebase",
        "fetch --prune --tags",
        "rebase --continue",
        "checkout -b feat origin/main",
        "branch --set-upstream-to=origin/main",
        "stash push -m wip",
        "reset --soft HEAD~1",
        "status --porcelain=v2",
    ],
)
def test_everyday_commands_are_not_caught_by_the_option_checks(raw) -> None:
    assert classify_git(raw).files == ()


def test_urls_in_commit_messages_do_not_trip_the_remote_checks() -> None:
    assert classify_git(["commit", "-m", "docs: http://insecure.example and ext::thing"]).kind == LOCAL
    assert classify_git(["tag", "-m", "see ftp://x", "v2"]).kind == LOCAL


# ----------------------------------------------------- hardened invocation


def test_environment_drops_git_redirection_and_never_prompts() -> None:
    env = git_env(
        {
            "PATH": "/usr/bin",
            "HOME": "/home/u",
            "GIT_DIR": "/etc",
            "git_work_tree": "/etc",
            "GIT_SSH_COMMAND": "ssh -i key",
            "GIT_ASKPASS": "/usr/bin/askpass",
            "GIT_EXEC_PATH": "/evil",
            "GIT_EDITOR": "vim",
            "LANGUAGE": "es",
            "LC_ALL": "es_ES.UTF-8",
            "LANG": "es_ES.UTF-8",
        }
    )
    # Git speaks English here, so the failure hints recognise its messages.
    assert env["LC_MESSAGES"] == "C" and "LANGUAGE" not in env and "LC_ALL" not in env
    assert env["LANG"] == "es_ES.UTF-8"
    assert env["PATH"] == "/usr/bin" and env["HOME"] == "/home/u"
    assert "GIT_DIR" not in env and "git_work_tree" not in env and "GIT_EXEC_PATH" not in env
    assert env["GIT_SSH_COMMAND"] == "ssh -i key" and env["GIT_ASKPASS"] == "/usr/bin/askpass"
    assert env["GIT_TERMINAL_PROMPT"] == "0"
    assert env["GIT_EDITOR"] == "true" and env["GIT_PAGER"] == "cat"
    assert env["GIT_ALLOW_PROTOCOL"] == "https:ssh:git:file"


def test_argv_turns_hooks_off_unless_the_user_opts_in(monkeypatch) -> None:
    quiet = git_argv("git", ("status",), hooks_dir="/empty")
    assert quiet[:2] == ["git", "--no-pager"] and quiet[-1] == "status"
    assert "core.hooksPath=/empty" in quiet and "core.fsmonitor=false" in quiet
    hooked = git_argv("git", ("status",), hooks_dir="/empty", hooks=True)
    assert not any(part.startswith("core.hooksPath") for part in hooked)

    for value, expected in (("1", True), (" Yes ", True), ("on", True), ("0", False), ("", False)):
        assert hooks_enabled({"TRINAXAI_AGENT_GIT_HOOKS": value}) is expected
    monkeypatch.setenv("TRINAXAI_AGENT_GIT_HOOKS", "true")
    assert hooks_enabled() is True


# ------------------------------------------------------------ the handler


def _identity(repo: Path) -> None:
    for key, value in (("user.name", "Ana Dev"), ("user.email", "ana@example.com")):
        subprocess.run([GIT, "config", key, value], cwd=repo, check=True)


def _run(repo: Path, *args: str) -> str:
    return agent_tools._git(repo, list(args))


@needs_git
def test_a_full_local_workflow_runs_through_the_tool(tmp_path: Path) -> None:
    assert "not a git repository" in _run(tmp_path, "status")
    assert "[exit 0" in _run(tmp_path, "init", "-q", "-b", "main")
    _identity(tmp_path)
    (tmp_path / "a.txt").write_text("hello\n", encoding="utf-8")

    assert "[exit 0" in _run(tmp_path, "add", "a.txt")
    commit = _run(tmp_path, "commit", "-m", "first commit")
    assert "[exit 0" in commit and "first commit" in commit
    assert "Ana Dev" in _run(tmp_path, "log", "--format=%an")
    assert "a.txt" in _run(tmp_path, "ls-files")
    assert "main" in _run(tmp_path, "branch", "--show-current")
    assert "outside the sandbox" in _run(tmp_path, "status", "--short")
    assert agent_tools._git(tmp_path, command="log --oneline").count("first commit") == 1


@needs_git
def test_a_commit_with_nothing_staged_tells_the_model_how_to_recover(tmp_path: Path) -> None:
    _run(tmp_path, "init", "-q", "-b", "main")
    _identity(tmp_path)
    (tmp_path / "a.txt").write_text("one\n", encoding="utf-8")
    _run(tmp_path, "add", "a.txt")
    _run(tmp_path, "commit", "-m", "first")
    (tmp_path / "a.txt").write_text("two\n", encoding="utf-8")  # modified, not staged

    unstaged = _run(tmp_path, "commit", "-m", "second")
    assert "[exit 1" in unstaged and "[hint] Nothing is staged" in unstaged and "add <file>" in unstaged
    assert "[exit 0" in _run(tmp_path, "commit", "-a", "-m", "second")  # the hint's second way works

    clean = _run(tmp_path, "commit", "-m", "third")
    assert "[exit 1" in clean and "[hint] There is nothing to commit" in clean


def test_failure_hints_are_only_given_for_a_failed_commit() -> None:
    hint = agent_tools._git_failure_hint
    staged_message = 'no changes added to commit (use "git add" and/or "git commit -a")'
    assert hint(("commit", "-m", "x"), 1, staged_message).startswith("Nothing is staged")
    assert hint(("commit",), 1, "On branch main\nChanges not staged for commit:").startswith("Nothing is staged")
    assert hint(("commit",), 1, "nothing to commit, working tree clean").startswith("There is nothing to commit")
    assert hint(("commit",), 1, "fatal: unable to auto-detect email address") == ""  # unrelated failure
    assert hint(("commit", "-m", "x"), 0, staged_message) == ""  # success is never annotated
    assert hint(("status",), 1, staged_message) == ""  # other subcommands are untouched
    assert hint((), 1, staged_message) == ""


@needs_git
def test_push_and_pull_use_a_remote_the_user_configured(tmp_path: Path) -> None:
    remote = tmp_path / "remote.git"
    subprocess.run([GIT, "init", "-q", "--bare", str(remote)], check=True)
    subprocess.run([GIT, "symbolic-ref", "HEAD", "refs/heads/main"], cwd=remote, check=True)
    work = tmp_path / "work"
    work.mkdir()
    _run(work, "init", "-q", "-b", "main")
    _identity(work)
    (work / "a.txt").write_text("one\n", encoding="utf-8")
    _run(work, "add", "-A")
    _run(work, "commit", "-m", "one")
    assert "[exit 0" in _run(work, "remote", "add", "origin", str(remote))
    assert "[exit 0" in _run(work, "push", "-u", "origin", "main")

    other = tmp_path / "other"
    subprocess.run([GIT, "clone", "-q", str(remote), str(other)], check=True)
    for key, value in (("user.name", "Bo"), ("user.email", "bo@example.com")):
        subprocess.run([GIT, "config", key, value], cwd=other, check=True)
    (other / "b.txt").write_text("two\n", encoding="utf-8")
    subprocess.run([GIT, "add", "-A"], cwd=other, check=True)
    subprocess.run([GIT, "commit", "-q", "-m", "two"], cwd=other, check=True)
    subprocess.run([GIT, "push", "-q", "origin", "HEAD"], cwd=other, check=True)

    assert "[exit 0" in _run(work, "fetch", "origin")
    assert "[exit 0" in _run(work, "pull", "--ff-only")
    assert (work / "b.txt").read_text(encoding="utf-8") == "two\n"


def test_remote_commands_are_refused_for_requests_that_are_not_from_the_host(tmp_path: Path) -> None:
    refused = agent_tools._git(tmp_path, ["push", "origin", "main"], allow_network=False)
    assert refused.startswith("error:") and "computer that hosts TrinaxAI" in refused
    assert agent_tools._git(tmp_path, ["fetch"], allow_network=False).startswith("error:")


@needs_git
def test_only_the_repository_root_is_a_valid_workspace(tmp_path: Path) -> None:
    _run(tmp_path, "init", "-q")
    inner = tmp_path / "packages" / "app"
    inner.mkdir(parents=True)
    result = _run(inner, "status")
    assert result.startswith("error:") and "repository root" in result


@needs_git
def test_files_read_by_git_must_stay_inside_the_workspace(tmp_path: Path) -> None:
    _run(tmp_path, "init", "-q")
    outside = tmp_path.parent / "outside-note.txt"
    outside.write_text("secret\n", encoding="utf-8")
    with pytest.raises(SandboxError):
        _run(tmp_path, "commit", "-F", str(outside))
    (tmp_path / "msg.txt").write_text("message\n", encoding="utf-8")
    _identity(tmp_path)
    (tmp_path / "x").write_text("x", encoding="utf-8")
    _run(tmp_path, "add", "x")
    assert "[exit 0" in _run(tmp_path, "commit", "-F", "msg.txt")


@needs_git
def test_hooks_do_not_run_unless_the_user_opts_in(tmp_path: Path, monkeypatch) -> None:
    if sys.platform == "win32":
        pytest.skip("hook scripts need a POSIX shell")
    _run(tmp_path, "init", "-q")
    _identity(tmp_path)
    hook = tmp_path / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\ntouch hook-ran\n", encoding="utf-8")
    hook.chmod(0o755)
    (tmp_path / "a").write_text("a", encoding="utf-8")
    _run(tmp_path, "add", "a")

    monkeypatch.delenv("TRINAXAI_AGENT_GIT_HOOKS", raising=False)
    assert "[exit 0" in _run(tmp_path, "commit", "-m", "one")
    assert not (tmp_path / "hook-ran").exists()

    (tmp_path / "b").write_text("b", encoding="utf-8")
    _run(tmp_path, "add", "b")
    monkeypatch.setenv("TRINAXAI_AGENT_GIT_HOOKS", "1")
    assert "[exit 0" in _run(tmp_path, "commit", "-m", "two")
    assert (tmp_path / "hook-ran").exists()


@needs_git
def test_a_git_environment_variable_cannot_redirect_the_repository(tmp_path: Path, monkeypatch) -> None:
    decoy = tmp_path / "decoy"
    decoy.mkdir()
    subprocess.run([GIT, "init", "-q"], cwd=decoy, check=True)
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.setenv("GIT_DIR", str(decoy / ".git"))
    assert "not a git repository" in _run(work, "status")


def test_failures_to_start_git_are_reported_not_raised(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(agent_tools.shutil, "which", lambda _name: None)
    assert "git is not installed" in _run(tmp_path, "status")

    monkeypatch.setattr(agent_tools.shutil, "which", lambda _name: "/usr/bin/git")
    monkeypatch.setattr(agent_tools, "_git_toplevel", lambda *_a: tmp_path.resolve())

    def timeout(*_a, **_k):
        raise subprocess.TimeoutExpired("git", 1)

    monkeypatch.setattr(agent_tools, "_git_run", timeout)
    assert "timed out" in _run(tmp_path, "status")

    def broken(*_a, **_k):
        raise OSError("exec format error")

    monkeypatch.setattr(agent_tools, "_git_run", broken)
    assert "cannot run git" in _run(tmp_path, "status")


def test_toplevel_lookup_handles_missing_and_failing_git(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(agent_tools, "_git_run", lambda *_a: (128, "", "fatal: not a git repository"))
    assert agent_tools._git_toplevel("git", tmp_path) is None
    monkeypatch.setattr(agent_tools, "_git_run", lambda *_a: (0, "  \n", ""))
    assert agent_tools._git_toplevel("git", tmp_path) is None
    monkeypatch.setattr(agent_tools, "_git_run", lambda *_a: (0, f"{tmp_path}\nignored\n", ""))
    assert agent_tools._git_toplevel("git", tmp_path) == tmp_path.resolve()

    def broken(*_a):
        raise OSError("gone")

    monkeypatch.setattr(agent_tools, "_git_run", broken)
    assert agent_tools._git_toplevel("git", tmp_path) is None


def test_the_empty_hooks_directory_is_recreated_when_it_disappears(monkeypatch) -> None:
    first = agent_tools._no_hooks_dir()
    assert Path(first).is_dir() and not any(Path(first).iterdir())
    assert agent_tools._no_hooks_dir() == first
    shutil.rmtree(first)
    again = agent_tools._no_hooks_dir()
    assert Path(again).is_dir()


def test_the_tool_is_registered_for_every_agent() -> None:
    assert GIT_TOOL.dangerous is True
    schema = GIT_TOOL.schema()["function"]
    assert schema["parameters"]["required"] == ["args"]
    assert "git" in {tool.name for tool in agent_tools.DEFAULT_TOOLS}


def test_the_process_runner_never_inherits_stdin_and_uses_a_given_environment(tmp_path: Path) -> None:
    code, out, _err = agent_tools._run_process(
        [sys.executable, "-c", "import os,sys; print(os.environ.get('PROBE'), repr(sys.stdin.read()))"],
        cwd=tmp_path,
        env={**os.environ, "PROBE": "yes"},
    )
    assert code == 0 and out.strip() == "yes ''"


# ---------------------------------------------------------- approval policy


def test_reading_git_never_asks_and_is_allowed_even_in_plan_mode() -> None:
    for mode in ("default", MODE_ACCEPT_EDITS, MODE_PLAN, MODE_YOLO):
        policy = ApprovalPolicy(mode=mode)
        assert policy.auto_decision(GIT_TOOL, {"args": ["status"]}) is True
        assert policy.auto_decision(GIT_TOOL, {"command": "log --oneline"}) is True


def test_changing_git_asks_each_time_unless_the_user_remembers_a_safe_command() -> None:
    policy = ApprovalPolicy()
    commit = {"args": ["commit", "-m", "x"]}
    assert policy.auto_decision(GIT_TOOL, commit) is None
    assert policy.rule_for(GIT_TOOL, commit) == "git:commit"
    assert policy.rule_for(GIT_TOOL, {"args": ["add", "-A"]}) == "git:add"
    for risky in (
        ["reset", "--hard"],
        ["branch", "-D", "x"],
        ["push", "origin"],
        ["pull"],
        ["checkout", "--", "."],
        "not valid (",
    ):
        assert policy.rule_for(GIT_TOOL, {"args": risky}) is None
        assert policy.auto_decision(GIT_TOOL, {"args": risky}) is None

    assert policy.remember(GIT_TOOL, commit) == "git:commit"
    assert policy.auto_decision(GIT_TOOL, commit) is True
    assert policy.auto_decision(GIT_TOOL, {"args": ["add", "-A"]}) is None  # a different rule
    assert ApprovalPolicy(mode=MODE_ACCEPT_EDITS).auto_decision(GIT_TOOL, commit) is None
    assert ApprovalPolicy(mode=MODE_PLAN).auto_decision(GIT_TOOL, commit) is False
    assert ApprovalPolicy(mode=MODE_YOLO).auto_decision(GIT_TOOL, {"args": ["push"]}) is True


def _renderer(tmp_path: Path):
    ui = MagicMock()
    ui.language = "en"
    policy = ApprovalPolicy()
    return ui, policy, AgentRenderer(ui, policy, workspace_root=tmp_path)


def test_the_prompt_shows_the_exact_command_and_warns_about_remotes(tmp_path: Path) -> None:
    ui, policy, renderer = _renderer(tmp_path)

    ui.choose.return_value = "yes"
    assert renderer.on_confirm(GIT_TOOL, {"args": ["push", "origin", "main"]}) is True
    ui.code.assert_called_with("git push origin main", "bash")
    options = ui.choose.call_args.args[1]
    assert [key for key, _label in options] == ["yes", "no"]  # no "don't ask again" for a remote
    assert any("remote" in str(call.args[0]) for call in ui.say.call_args_list)

    ui.reset_mock()
    ui.choose.return_value = "always"
    assert renderer.on_confirm(GIT_TOOL, {"args": ["commit", "-m", "message"]}) is True
    options = ui.choose.call_args.args[1]
    assert "git commit" in options[1][1]
    assert policy.auto_decision(GIT_TOOL, {"args": ["commit", "-m", "another"]}) is True

    ui.reset_mock()
    assert renderer.on_confirm(GIT_TOOL, {"args": ["log"]}) is True
    ui.choose.assert_not_called()


def test_git_calls_read_naturally_in_the_transcript() -> None:
    assert tool_title(GIT_TOOL, {"args": ["commit", "-m", "fix it"]}) == "git(commit -m 'fix it')"
    lines, failed = summarize_result(
        GIT_TOOL, "[exit 0; git on this computer, outside the sandbox]\nline one\nline two"
    )
    assert not failed and lines[0].startswith("[exit 0") and lines[1:] == ["line one", "line two"]


# --------------------------------------------------------- HTTP agent service


def test_http_sessions_read_git_without_asking_and_keep_remotes_on_the_host(monkeypatch, tmp_path: Path) -> None:
    from app.schemas import AgentRequest
    from app.services import agent_service

    captured: dict = {}

    class FakeEngine:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def cancel(self):
            pass

        def run(self, _messages):
            return "answer"

    monkeypatch.setattr(agent_service, "AgentEngine", FakeEngine)
    session_id, session = agent_service._register_session()
    try:
        agent_service._run_engine_worker(
            session, AgentRequest(messages=[{"role": "user", "content": "hello"}]), tmp_path, "model"
        )
        confirm = captured["on_confirm"]
        asked: list[str] = []
        monkeypatch.setattr(agent_service, "_wait_for_approval", lambda _s, tool, args: asked.append(tool.name) or True)
        assert confirm(GIT_TOOL, {"args": ["status"]}) is True and asked == []
        assert confirm(GIT_TOOL, {"args": ["commit", "-m", "x"]}) is True and asked == ["git"]
        session["closed"] = True
        assert confirm(GIT_TOOL, {"args": ["status"]}) is False
    finally:
        agent_service._drop_session(session_id)


def test_non_host_requests_get_a_git_tool_that_refuses_remote_commands(tmp_path: Path) -> None:
    from app.services import agent_service

    host = next(tool for tool in agent_service._agent_tools() if tool.name == "git")
    device = next(tool for tool in agent_service._agent_tools(allow_git_network=False) if tool.name == "git")
    assert host.handler is GIT_TOOL.handler
    assert "computer that hosts TrinaxAI" in device.handler(tmp_path, args=["pull"])
    assert "git" in {tool.name for tool in agent_service._agent_tools(allow_git_network=False)}

    safe = agent_service._safe_args({"args": ["commit", "-m", "two words"], "note": "plain"})
    assert safe == {"args": "commit -m 'two words'", "note": "plain"}


def test_the_git_tool_is_hidden_when_git_is_not_installed(monkeypatch, tmp_path: Path) -> None:
    from app.schemas import AgentRequest
    from app.services import agent_service

    request = SimpleNamespace(state=SimpleNamespace(trinaxai_identity={"kind": "local", "scopes": ["*"]}))
    req = AgentRequest(messages=[{"role": "user", "content": "hi"}])
    monkeypatch.setattr(agent_service.shutil, "which", lambda _name: "/usr/bin/git")
    assert "git" in agent_service._available_agent_tool_names(req, request, None)
    monkeypatch.setattr(agent_service.shutil, "which", lambda _name: None)
    assert "git" not in agent_service._available_agent_tool_names(req, request, None)


# ------------------------------------------------- impossible calls skip the prompt


def _call(*args: str) -> dict:
    return {"function": {"name": "git", "arguments": {"args": list(args)}}}


def test_a_call_that_cannot_succeed_is_reported_without_asking_the_user(tmp_path: Path) -> None:
    asked: list[str] = []
    seen: list[str] = []
    engine = AgentEngine(
        model="m",
        workspace_root=tmp_path,
        on_confirm=lambda tool, args: asked.append(tool.name) or False,
        on_tool_result=lambda _tool, result: seen.append(result),
    )

    refused = engine._execute_call(_call("-c", "core.pager=evil", "status"))
    assert asked == []
    assert "global options" in refused and "[tool_status=degraded" in refused
    assert seen == [refused]

    assert "denied by user" in engine._execute_call(_call("commit", "-m", "x"))
    assert asked == ["git"]  # a valid change still asks


def test_the_precheck_hook_only_blocks_when_it_reports_a_problem(tmp_path: Path) -> None:
    assert agent_tools._precheck_git({"args": ["status"]}) is None
    assert "not available" in agent_tools._precheck_git({"args": ["config", "user.name", "x"]})
    assert "no git arguments" in agent_tools._precheck_git({})


def test_tools_without_a_precheck_still_run(tmp_path: Path) -> None:
    from types import SimpleNamespace

    ran: list[dict] = []
    legacy = SimpleNamespace(
        name="legacy",
        dangerous=False,
        external=False,
        handler=lambda _root, **kwargs: ran.append(kwargs) or "ok",
        schema=lambda: {"type": "function", "function": {"name": "legacy", "parameters": {"type": "object"}}},
    )
    engine = AgentEngine(model="m", workspace_root=tmp_path, tools=(legacy,))
    assert "ok" in engine._execute_call({"function": {"name": "legacy", "arguments": {"a": 1}}})
    assert ran == [{"a": 1}]


# ------------------------------------- a doomed commit is refused before the user is asked


@pytest.mark.parametrize(
    ("args", "plain"),
    [
        (("commit", "-m", "msg"), True),
        (("commit", "--message", "msg", "-q"), True),
        (("commit", "--message=msg", "--no-verify", "-s"), True),
        (("commit", "-m", "-starts-with-dash"), True),
        (("commit",), False),  # no message: git would open an editor
        (("commit", "-m"), False),  # message missing
        (("commit", "-a", "-m", "x"), False),  # stages tracked files itself
        (("commit", "-am", "x"), False),  # combined short flags
        (("commit", "--amend", "-m", "x"), False),
        (("commit", "--allow-empty", "-m", "x"), False),
        (("commit", "-m", "x", "a.txt"), False),  # a pathspec commits those files directly
        (("commit", "-F", "notes.txt"), False),
        (("status",), False),
        ((), False),
    ],
)
def test_only_a_plain_commit_is_checked_for_staged_changes(args, plain) -> None:
    assert agent_tools._is_plain_commit(args) is plain


@needs_git
def test_a_plain_commit_with_nothing_staged_is_refused_in_advance(tmp_path: Path) -> None:
    check = agent_tools._git_state_check
    commit = {"args": ["commit", "-m", "x"]}
    assert check(tmp_path, commit) is None  # not a repository: the handler explains that

    _run(tmp_path, "init", "-q", "-b", "main")
    _identity(tmp_path)
    (tmp_path / "a.txt").write_text("one\n", encoding="utf-8")
    assert "nothing is staged" in check(tmp_path, commit)  # an untracked file is not staged either

    _run(tmp_path, "add", "a.txt")
    assert check(tmp_path, commit) is None  # first commit with a staged file
    _run(tmp_path, "commit", "-m", "first")
    assert "nothing is staged" in check(tmp_path, commit)  # clean tree

    (tmp_path / "a.txt").write_text("two\n", encoding="utf-8")
    assert "nothing is staged" in check(tmp_path, commit)  # modified but not staged
    assert check(tmp_path, {"args": ["commit", "-a", "-m", "x"]}) is None  # -a stages it
    assert check(tmp_path, {"args": ["status"]}) is None
    assert check(tmp_path, {"args": ["config", "user.name", "x"]}) is None  # refused elsewhere
    _run(tmp_path, "add", "a.txt")
    assert check(tmp_path, commit) is None

    # Concluding a merge can be valid with an empty index, so an operation in progress is never second-guessed.
    _run(tmp_path, "commit", "-m", "second")
    (tmp_path / ".git" / "MERGE_HEAD").write_text("0" * 40 + "\n", encoding="utf-8")
    assert check(tmp_path, commit) is None


@needs_git
def test_the_engine_does_not_ask_for_a_commit_that_cannot_work(tmp_path: Path) -> None:
    _run(tmp_path, "init", "-q", "-b", "main")
    _identity(tmp_path)
    (tmp_path / "a.txt").write_text("one\n", encoding="utf-8")
    asked: list[str] = []
    engine = AgentEngine(
        model="m", workspace_root=tmp_path, on_confirm=lambda tool, args: asked.append(tool.name) or True
    )

    refused = engine._execute_call(_call("commit", "-m", "first"))
    assert asked == [] and "nothing is staged" in refused and "[tool_status=degraded" in refused

    assert "[exit 0" in engine._execute_call(_call("add", "a.txt"))
    assert asked == ["git"]
    committed = engine._execute_call(_call("commit", "-m", "first"))
    assert asked == ["git", "git"] and "[exit 0" in committed and "first" in committed


def test_a_state_check_that_finds_nothing_wrong_lets_the_call_proceed(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(agent_tools.shutil, "which", lambda _name: None)
    assert agent_tools._git_state_check(tmp_path, {"args": ["commit", "-m", "x"]}) is None  # git not installed

    monkeypatch.setattr(agent_tools.shutil, "which", lambda _name: "/usr/bin/git")
    monkeypatch.setattr(agent_tools, "_git_toplevel", lambda *_a: (_ for _ in ()).throw(OSError("boom")))
    assert (
        agent_tools._git_state_check(tmp_path, {"args": ["commit", "-m", "x"]}) is None
    )  # git failing: stay out of the way
    assert agent_tools._git_state_check(tmp_path, {}) is None  # unusable arguments are the precheck's business

    legacy = SimpleNamespace(
        name="legacy",
        dangerous=False,
        external=False,
        handler=lambda _root, **kwargs: "ok",
        schema=lambda: {"type": "function", "function": {"name": "legacy", "parameters": {"type": "object"}}},
    )
    engine = AgentEngine(model="m", workspace_root=tmp_path, tools=(legacy,))
    assert "ok" in engine._execute_call(
        {"function": {"name": "legacy", "arguments": {}}}
    )  # tools without the hook still run
