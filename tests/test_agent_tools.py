from __future__ import annotations

from pathlib import Path

import pytest

from trinaxai_cli.agent import tools as agent_tools
from trinaxai_cli.agent.tools import (
    SandboxError,
    _bubblewrap_argv,
    _edit_file,
    _glob,
    _grep,
    _list_dir,
    _python_stdlib_facts,
    _read_file,
    _run_command,
    _write_file,
    format_tool_failure,
    is_degraded_tool_result,
    normalize_tool_result,
)


def test_list_dir_rejects_an_accidentally_broad_root(tmp_path: Path) -> None:
    for index in range(201):
        (tmp_path / f"file-{index}.txt").write_text("x", encoding="utf-8")
    result = _list_dir(tmp_path)
    assert "too broad" in result
    assert "project folder" in result


def test_glob_is_root_only_unless_recursive_pattern_is_explicit(tmp_path: Path) -> None:
    (tmp_path / "root.py").write_text("x", encoding="utf-8")
    nested = tmp_path / "src"
    nested.mkdir()
    (nested / "nested.py").write_text("x", encoding="utf-8")
    assert _glob(tmp_path, "*.py") == "root.py"
    assert "src/nested.py" in _glob(tmp_path, "**/*.py").replace("\\", "/")


def test_directory_tools_do_not_disclose_symlink_entries(tmp_path: Path) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("secret", encoding="utf-8")
    try:
        (tmp_path / "linked.txt").symlink_to(outside / "secret.txt")
        (tmp_path / "linked-dir").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks are unavailable")

    assert "linked.txt" not in _list_dir(tmp_path)
    assert "linked.txt" not in _glob(tmp_path, "**/*.txt")
    assert "secret.txt" not in _glob(tmp_path, "linked-dir/*.txt")


def test_grep_marks_bounded_results(tmp_path: Path) -> None:
    for index in range(110):
        (tmp_path / f"file-{index}.txt").write_text("needle\n", encoding="utf-8")
    result = _grep(tmp_path, "needle")
    assert "truncated" in result


def test_edit_file_keeps_original_when_atomic_replace_fails(monkeypatch, tmp_path: Path) -> None:
    target = tmp_path / "important.txt"
    target.write_text("before", encoding="utf-8")
    monkeypatch.setattr(agent_tools.os, "replace", lambda *_args: (_ for _ in ()).throw(OSError("disk error")))

    result = _edit_file(tmp_path, "important.txt", old="before", new="after")

    assert result.startswith("error: cannot write")
    assert target.read_text(encoding="utf-8") == "before"
    assert list(tmp_path.glob(".important.txt.*.tmp")) == []


def test_tool_sandbox_file_edges_and_safe_messages(tmp_path: Path) -> None:
    with pytest.raises(SandboxError):
        _read_file(tmp_path, "../outside")
    assert _write_file(tmp_path, "nested/note.txt", "hello").startswith("created")
    assert "1\thello" in _read_file(tmp_path, "nested/note.txt")
    assert "partial" in _read_file(tmp_path, "nested/note.txt", offset=1, limit=1)
    assert "not found" in _read_file(tmp_path, "missing.txt")
    assert "replacement" in _edit_file(tmp_path, "nested/note.txt", old="hello", new="old")
    assert "must not be empty" in _edit_file(tmp_path, "nested/note.txt", old="", new="x")
    assert "not found" in _edit_file(tmp_path, "nested/note.txt", old="missing", new="x")
    (tmp_path / "nested" / "repeat.txt").write_text("x x", encoding="utf-8")
    assert "matches 2" in _edit_file(tmp_path, "nested/repeat.txt", old="x", new="y")
    assert "no matches" in _grep(tmp_path, "absent")
    with pytest.raises(SandboxError):
        _glob(tmp_path, "../*.py")

    (tmp_path / "hola_mundo.py").write_text("print('hola')\n", encoding="utf-8")
    assert "print('hola')" in _read_file(tmp_path, f"{tmp_path.name}/hola_mundo.py")
    assert "hola_mundo.py" in _list_dir(tmp_path, f"{tmp_path.name}/")

    safe = format_tool_failure("search/tool", "api_key=secret", external=False)
    assert is_degraded_tool_result(safe)
    assert "api_key=[redacted]" in safe
    for detail in (
        "Authorization: Bearer very-secret-token",
        '{"api_key":"very-secret-json"}',
        "apiKey = very-secret-camel",
    ):
        redacted = format_tool_failure("search", detail, external=False)
        assert "very-secret" not in redacted
        assert "[redacted]" in redacted
    assert is_degraded_tool_result(normalize_tool_result("search", "error: offline", external=True))
    assert normalize_tool_result("read", "normal") == "normal"


def test_tool_api_facts_and_command_fallbacks(monkeypatch, tmp_path: Path) -> None:
    source = "import pathlib\np = pathlib.Path('.')\np.exists()\n"
    facts = _python_stdlib_facts(source)
    assert facts and "verified pathlib.Path" in facts[0]
    assert _python_stdlib_facts("def broken(:") == []
    assert _bubblewrap_argv(tmp_path, "echo ok") is None or isinstance(_bubblewrap_argv(tmp_path, "echo ok"), list)

    assert _run_command(tmp_path, "") == "error: empty command"
    monkeypatch.delenv("TRINAXAI_AGENT_ALLOW_UNSANDBOXED_COMMANDS", raising=False)
    monkeypatch.setattr(agent_tools, "_bubblewrap_argv", lambda *_args: None)
    disabled = _run_command(tmp_path, "echo hi")
    assert "terminal execution is disabled" in disabled
    monkeypatch.setenv("TRINAXAI_AGENT_ALLOW_UNSANDBOXED_COMMANDS", "1")
    monkeypatch.setattr(agent_tools, "_run_process", lambda *_args, **_kwargs: (0, "ok", "warn"))
    result = _run_command(tmp_path, "echo hi")
    assert "UNSANDBOXED opt-in" in result and "warn" in result
    monkeypatch.setattr(
        agent_tools,
        "_run_process",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(agent_tools.subprocess.TimeoutExpired("x", 1)),
    )
    assert "timed out" in _run_command(tmp_path, "sleep 1")


def test_default_tool_schemas_are_machine_readable() -> None:
    schemas = [tool.schema() for tool in agent_tools.DEFAULT_TOOLS]
    assert schemas and all(item["function"]["parameters"]["type"] == "object" for item in schemas)
    assert {tool.name for tool in agent_tools.DEFAULT_TOOLS} >= {"read_file", "write_file", "run_command"}


def test_shell_sandbox_status_reports_each_host_state(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("TRINAXAI_AGENT_ALLOW_UNSANDBOXED_COMMANDS", raising=False)
    monkeypatch.setattr(agent_tools, "_bubblewrap_argv", lambda *_args: ["bwrap"])
    ok, detail = agent_tools.shell_sandbox_status()
    assert ok and "bubblewrap" in detail

    monkeypatch.setattr(agent_tools, "_bubblewrap_argv", lambda *_args: None)
    monkeypatch.setattr(agent_tools.sys, "platform", "linux")
    ok, detail = agent_tools.shell_sandbox_status()
    assert not ok and "install the 'bubblewrap' package" in detail

    monkeypatch.setattr(agent_tools.sys, "platform", "darwin")
    ok, detail = agent_tools.shell_sandbox_status()
    assert not ok and "Linux-only" in detail

    monkeypatch.setenv("TRINAXAI_AGENT_ALLOW_UNSANDBOXED_COMMANDS", "1")
    ok, detail = agent_tools.shell_sandbox_status()
    assert ok and "UNSANDBOXED" in detail


def test_write_tools_refuse_git_metadata(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("[core]\n")
    (tmp_path / "pkg" / ".git").mkdir(parents=True)
    for path in (
        ".git/config",
        ".git/hooks/pre-commit",
        "pkg/.git/config",
        ".GIT/config",
        ".git./config",
        ".git /config",
        ".gi\u200dt/config",
        "GIT~1/config",
        ".git::$INDEX_ALLOCATION/config",
    ):
        with pytest.raises(SandboxError):
            agent_tools._write_file(tmp_path, path, "x")
    with pytest.raises(SandboxError):
        agent_tools._edit_file(tmp_path, ".git/config", "[core]", "[evil]")
    assert (tmp_path / ".git" / "config").read_text() == "[core]\n"
    assert "created" in agent_tools._write_file(tmp_path, ".gitignore", "x\n")


def test_only_git_config_and_hooks_are_read_only_in_the_command_sandbox(tmp_path: Path) -> None:
    assert agent_tools._git_metadata_mounts(tmp_path) == ()

    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    assert agent_tools._git_metadata_mounts(tmp_path) == ()

    (git_dir / "config").write_text("[core]\n", encoding="utf-8")
    assert agent_tools._git_metadata_mounts(tmp_path) == ("--ro-bind", str(git_dir / "config"), str(git_dir / "config"))

    (git_dir / "hooks").mkdir()
    assert agent_tools._git_metadata_mounts(tmp_path) == (
        "--ro-bind",
        str(git_dir / "config"),
        str(git_dir / "config"),
        "--ro-bind",
        str(git_dir / "hooks"),
        str(git_dir / "hooks"),
    )

    other = tmp_path / "worktree"
    other.mkdir()
    (other / ".git").write_text("gitdir: ../elsewhere\n", encoding="utf-8")
    assert agent_tools._git_metadata_mounts(other) == ("--ro-bind", str(other / ".git"), str(other / ".git"))

    linked = tmp_path / "linked"
    linked.mkdir()
    (linked / ".git").symlink_to(git_dir)
    assert agent_tools._git_metadata_mounts(linked) == ()

    odd = tmp_path / "odd"
    (odd / ".git").mkdir(parents=True)
    (odd / ".git" / "config").symlink_to(git_dir / "config")
    assert agent_tools._git_metadata_mounts(odd) == ()


def test_git_identity_is_forwarded_into_the_command_sandbox(monkeypatch, tmp_path: Path) -> None:
    assert agent_tools._git_identity_env(tmp_path) == ()
    (tmp_path / ".git").mkdir()

    answers = {"user.name": "Ana Dev", "user.email": "ana@example.com"}

    def fake_run(argv, **_kwargs):
        value = answers.get(argv[-1], "")
        return agent_tools.subprocess.CompletedProcess(argv, 0 if value else 1, stdout=f"{value}\n", stderr="")

    monkeypatch.setattr(agent_tools.subprocess, "run", fake_run)
    assert agent_tools._git_identity_env(tmp_path) == (
        "--setenv",
        "GIT_AUTHOR_NAME",
        "Ana Dev",
        "--setenv",
        "GIT_COMMITTER_NAME",
        "Ana Dev",
        "--setenv",
        "GIT_AUTHOR_EMAIL",
        "ana@example.com",
        "--setenv",
        "GIT_COMMITTER_EMAIL",
        "ana@example.com",
    )

    answers.pop("user.name")
    assert agent_tools._git_identity_env(tmp_path)[2::3] == ("ana@example.com", "ana@example.com")
    answers.clear()
    assert agent_tools._git_identity_env(tmp_path) == ()

    def missing_git(*_args, **_kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(agent_tools.subprocess, "run", missing_git)
    assert agent_tools._git_identity_env(tmp_path) == ()


def test_command_sandbox_mounts_git_config_after_the_workspace_bind(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("[core]\n", encoding="utf-8")
    argv = _bubblewrap_argv(tmp_path, "true")
    if argv is None:
        pytest.skip("bubblewrap is not available on this host")
    root = str(tmp_path.resolve())
    workspace_bind = argv.index("--bind")
    assert argv[workspace_bind : workspace_bind + 3] == ["--bind", root, root]
    assert argv[workspace_bind + 3 : workspace_bind + 6] == ["--ro-bind", f"{root}/.git/config", f"{root}/.git/config"]


def test_terminal_can_commit_but_cannot_plant_git_config_or_hooks(tmp_path: Path) -> None:
    if _bubblewrap_argv(tmp_path, "true") is None or agent_tools.shutil.which("git") is None:
        pytest.skip("bubblewrap and git are required")
    agent_tools.subprocess.run(["git", "init", "-q", "."], cwd=tmp_path, check=True)
    for key, value in (("user.name", "Ana Dev"), ("user.email", "ana@example.com")):
        agent_tools.subprocess.run(["git", "config", key, value], cwd=tmp_path, check=True)
    before = (tmp_path / ".git" / "config").read_text(encoding="utf-8")

    result = _run_command(
        tmp_path,
        "echo ok > note.txt; git add note.txt; git commit -qm first; "
        "echo '[alias]' >> .git/config; echo x > .git/hooks/pre-commit; git log --format=%an",
    )

    assert "Ana Dev" in result
    assert "Read-only file system" in result
    assert (tmp_path / "note.txt").read_text(encoding="utf-8") == "ok\n"
    assert (tmp_path / ".git" / "config").read_text(encoding="utf-8") == before
    assert not (tmp_path / ".git" / "hooks" / "pre-commit").exists()
