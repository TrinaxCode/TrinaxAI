from __future__ import annotations

import subprocess
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
    monkeypatch.setattr(agent_tools, "_seatbelt_usable", lambda: False)
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
    monkeypatch.setattr(agent_tools, "_seatbelt_usable", lambda: False)
    monkeypatch.setattr(agent_tools.sys, "platform", "linux")
    ok, detail = agent_tools.shell_sandbox_status()
    assert not ok and "install the 'bubblewrap' package" in detail

    monkeypatch.setattr(agent_tools.sys, "platform", "darwin")
    ok, detail = agent_tools.shell_sandbox_status()
    assert not ok and "sandbox-exec" in detail

    monkeypatch.setattr(agent_tools.sys, "platform", "win32")
    ok, detail = agent_tools.shell_sandbox_status()
    assert not ok and "only on Linux and macOS" in detail

    monkeypatch.setattr(agent_tools.sys, "platform", "darwin")
    monkeypatch.setattr(agent_tools, "_seatbelt_usable", lambda: True)
    ok, detail = agent_tools.shell_sandbox_status()
    assert ok and "Seatbelt" in detail
    monkeypatch.setattr(agent_tools, "_seatbelt_usable", lambda: False)

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


def test_command_sandbox_keeps_debian_alternatives_so_python3_and_cc_resolve(tmp_path: Path, monkeypatch) -> None:
    real_is_dir = Path.is_dir
    monkeypatch.setattr(Path, "is_dir", lambda self: True if str(self) == "/etc/alternatives" else real_is_dir(self))
    argv = _bubblewrap_argv(tmp_path, "true")
    if argv is None:
        pytest.skip("bubblewrap is not available on this host")
    position = argv.index("/etc/alternatives")
    assert argv[position - 1 : position + 2] == ["--ro-bind", "/etc/alternatives", "/etc/alternatives"]
    # Only that directory of symlinks into /usr is added, never the rest of /etc.
    assert not any(item == "/etc" for item in argv)


def test_python3_runs_inside_the_command_sandbox(tmp_path: Path) -> None:
    argv = _bubblewrap_argv(tmp_path, "python3 -c 'print(6*7)'")
    if argv is None or not str(Path(agent_tools.shutil.which("python3") or "").resolve()).startswith("/usr/"):
        pytest.skip("bubblewrap and a system python3 are required")
    result = subprocess.run(argv, capture_output=True, text=True, check=False, timeout=60)
    assert result.stdout.strip() == "42", result.stderr


# ------------------------------------------------------------ macOS Seatbelt sandbox


def _seatbelt_params(argv: list[str]) -> dict[str, str]:
    params: dict[str, str] = {}
    for index, item in enumerate(argv):
        if item == "-D":
            name, _, value = argv[index + 1].partition("=")
            params[name] = value
    return params


def test_seatbelt_argv_confines_the_command(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(agent_tools, "_seatbelt_usable", lambda: True)
    monkeypatch.setenv("SECRET_TOKEN", "do-not-leak")
    workspace = tmp_path / "ws"
    (workspace / ".git" / "hooks").mkdir(parents=True)
    (workspace / ".git" / "config").write_text("[core]\n", encoding="utf-8")
    scratch = tmp_path / "scratch"
    scratch.mkdir()

    argv = agent_tools._seatbelt_argv(workspace, "echo $((6*7)); false", scratch)

    assert argv is not None
    assert argv[:2] == ["/usr/bin/env", "-i"]
    assert argv[-3:] == ["/bin/sh", "-c", "echo $((6*7)); false"]
    assert argv[argv.index("/usr/bin/sandbox-exec") + 1] == "-p"
    profile = argv[argv.index("-p") + 1]
    assert "(deny default)" in profile and "(deny network*)" in profile
    # Only the workspace and the scratch directory are writable.
    assert profile.count("(allow file-write*") == 1
    # Paths travel as -D parameters, never inside the profile text.
    assert str(workspace) not in profile and str(scratch) not in profile
    params = _seatbelt_params(argv)
    assert params["WORKSPACE"] == str(workspace.resolve())
    assert params["SCRATCH"] == str(scratch.resolve())
    assert {params["GITRO0"], params["GITRO1"]} == {
        str(workspace.resolve() / ".git" / "config"),
        str(workspace.resolve() / ".git" / "hooks"),
    }
    assert '(deny file-write* (subpath (param "GITRO0")) (subpath (param "GITRO1")))' in profile
    # ``.git`` itself cannot be renamed or removed (move aside, edit, move back).
    assert params["GITDIR"] == str(workspace.resolve() / ".git")
    assert '(deny file-write-unlink (literal (param "GITDIR")))' in profile
    # The environment is built from scratch: private HOME/TMPDIR, nothing inherited from the host.
    environment = argv[2 : argv.index("/usr/bin/sandbox-exec")]
    assert f"HOME={scratch.resolve()}/home" in environment
    assert f"TMPDIR={scratch.resolve()}" in environment
    assert "PIP_NO_INDEX=1" in environment
    assert not any(item.startswith("SECRET_TOKEN=") for item in environment)
    # The directories above the workspace can be stat()ed, nothing more.
    assert any(name.startswith("PARENT") for name in params)


def test_seatbelt_argv_has_no_git_rule_without_git_metadata(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(agent_tools, "_seatbelt_usable", lambda: True)
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    argv = agent_tools._seatbelt_argv(tmp_path / "ws", "true", scratch)
    assert argv is not None
    assert not any(name.startswith("GITRO") for name in _seatbelt_params(argv))
    assert "GITRO" not in argv[argv.index("-p") + 1]


def test_seatbelt_argv_is_none_when_seatbelt_cannot_be_applied(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(agent_tools, "_seatbelt_usable", lambda: False)
    assert agent_tools._seatbelt_argv(tmp_path, "true", tmp_path) is None


def test_seatbelt_usable_probes_the_host_once(monkeypatch) -> None:
    calls: list[list[str]] = []
    outcome: dict[str, object] = {"returncode": 0}

    def fake_run(argv, **_kwargs):
        calls.append(argv)
        if isinstance(outcome["returncode"], Exception):
            raise outcome["returncode"]
        return agent_tools.subprocess.CompletedProcess(argv, outcome["returncode"], stdout=b"", stderr=b"")

    monkeypatch.setattr(agent_tools.subprocess, "run", fake_run)
    monkeypatch.setattr(agent_tools.os, "access", lambda *_args: True)
    agent_tools._seatbelt_usable.cache_clear()
    try:
        monkeypatch.setattr(agent_tools.sys, "platform", "linux")
        assert agent_tools._seatbelt_usable() is False and calls == []

        monkeypatch.setattr(agent_tools.sys, "platform", "darwin")
        agent_tools._seatbelt_usable.cache_clear()
        assert agent_tools._seatbelt_usable() is True
        assert agent_tools._seatbelt_usable() is True
        assert len(calls) == 1 and calls[0][0] == "/usr/bin/sandbox-exec"

        # Already inside another sandbox: sandbox-exec exits with an error and the tool stays off.
        outcome["returncode"] = 71
        agent_tools._seatbelt_usable.cache_clear()
        assert agent_tools._seatbelt_usable() is False

        outcome["returncode"] = OSError("gone")
        agent_tools._seatbelt_usable.cache_clear()
        assert agent_tools._seatbelt_usable() is False

        monkeypatch.setattr(agent_tools.os, "access", lambda *_args: False)
        agent_tools._seatbelt_usable.cache_clear()
        assert agent_tools._seatbelt_usable() is False
    finally:
        agent_tools._seatbelt_usable.cache_clear()


def test_command_sandbox_prefers_bubblewrap_over_seatbelt(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(agent_tools, "_bubblewrap_argv", lambda *_args: ["bwrap", "x"])
    monkeypatch.setattr(agent_tools, "_seatbelt_usable", lambda: True)
    monkeypatch.setattr(agent_tools, "_seatbelt_argv", lambda *_args: pytest.fail("Seatbelt must not be used"))
    with agent_tools._command_sandbox(tmp_path, "true") as argv:
        assert argv == ["bwrap", "x"]


def test_command_sandbox_gives_each_macos_command_a_private_scratch_that_is_removed(
    monkeypatch, tmp_path: Path
) -> None:
    seen: list[Path] = []

    def fake_seatbelt(_root, _command, scratch):
        assert (scratch / "home").is_dir()
        seen.append(scratch)
        return ["sandbox-exec", "x"]

    monkeypatch.setattr(agent_tools, "_bubblewrap_argv", lambda *_args: None)
    monkeypatch.setattr(agent_tools, "_seatbelt_usable", lambda: True)
    monkeypatch.setattr(agent_tools, "_seatbelt_argv", fake_seatbelt)

    with agent_tools._command_sandbox(tmp_path, "true") as argv:
        assert argv == ["sandbox-exec", "x"]
        assert seen[0].is_dir()
    assert not seen[0].exists()

    # The scratch directory is removed even when the command raises.
    with pytest.raises(RuntimeError):
        with agent_tools._command_sandbox(tmp_path, "true"):
            raise RuntimeError("boom")
    assert len(seen) == 2 and not seen[1].exists()

    monkeypatch.setattr(agent_tools, "_seatbelt_usable", lambda: False)
    with agent_tools._command_sandbox(tmp_path, "true") as argv:
        assert argv is None


def test_run_command_reports_the_macos_sandbox_as_sandboxed(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("TRINAXAI_AGENT_ALLOW_UNSANDBOXED_COMMANDS", raising=False)
    monkeypatch.setattr(agent_tools, "_bubblewrap_argv", lambda *_args: None)
    monkeypatch.setattr(agent_tools, "_seatbelt_usable", lambda: True)
    monkeypatch.setattr(agent_tools, "_seatbelt_argv", lambda *_args: ["sandbox-exec", "x"])
    ran: list[list[str]] = []
    monkeypatch.setattr(agent_tools, "_run_process", lambda argv, **_kw: ran.append(argv) or (0, "42\n", ""))

    result = _run_command(tmp_path, "echo 42")

    assert ran == [["sandbox-exec", "x"]]
    assert result.startswith("[exit 0; sandboxed, network=off]") and "42" in result
    assert agent_tools._command_sandbox_available() is True


def test_command_sandbox_availability_follows_either_sandbox(monkeypatch) -> None:
    monkeypatch.setattr(agent_tools, "_bubblewrap_argv", lambda *_args: None)
    monkeypatch.setattr(agent_tools, "_seatbelt_usable", lambda: False)
    assert agent_tools._command_sandbox_available() is False
    monkeypatch.setattr(agent_tools, "_seatbelt_usable", lambda: True)
    assert agent_tools._command_sandbox_available() is True
    monkeypatch.setattr(agent_tools, "_seatbelt_usable", lambda: False)
    monkeypatch.setattr(agent_tools, "_bubblewrap_argv", lambda *_args: ["bwrap"])
    assert agent_tools._command_sandbox_available() is True


def test_git_protected_paths_cover_config_hooks_and_pointer_files(tmp_path: Path) -> None:
    assert agent_tools._git_protected_paths(tmp_path) == ()
    (tmp_path / ".git" / "hooks").mkdir(parents=True)
    (tmp_path / ".git" / "config").write_text("[core]\n", encoding="utf-8")
    assert set(agent_tools._git_protected_paths(tmp_path)) == {
        tmp_path / ".git" / "config",
        tmp_path / ".git" / "hooks",
    }
    pointer = tmp_path / "worktree"
    pointer.mkdir()
    (pointer / ".git").write_text("gitdir: ../elsewhere\n", encoding="utf-8")
    assert agent_tools._git_protected_paths(pointer) == (pointer / ".git",)


needs_macos_sandbox = pytest.mark.skipif(
    not agent_tools._seatbelt_usable(), reason="the macOS Seatbelt sandbox is not available on this host"
)


@needs_macos_sandbox
def test_macos_sandbox_enforces_isolation_for_real(monkeypatch, tmp_path: Path) -> None:
    """Runs only on macOS: the profile must actually deny what the tool promises to deny."""
    import socket

    monkeypatch.delenv("TRINAXAI_AGENT_ALLOW_UNSANDBOXED_COMMANDS", raising=False)
    monkeypatch.setenv("SECRET_TOKEN", "do-not-leak")
    workspace = tmp_path / "ws"
    outside = tmp_path / "outside"
    workspace.mkdir()
    outside.mkdir()
    (workspace / "a.txt").write_text("hello\n", encoding="utf-8")
    home = Path.home()
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    port = listener.getsockname()[1]

    try:
        ok = _run_command(workspace, 'pwd; cat a.txt; echo made > new.txt; cat new.txt; echo "[$SECRET_TOKEN]"')
        assert ok.startswith("[exit 0; sandboxed, network=off]"), ok
        assert "hello" in ok and "made" in ok and "[]" in ok and "do-not-leak" not in ok
        assert (workspace / "new.txt").read_text(encoding="utf-8") == "made\n"

        escaped = _run_command(workspace, f"echo leaked > {outside}/x.txt; echo rc=$?")
        assert "rc=1" in escaped and not (outside / "x.txt").exists()

        peek = _run_command(workspace, f"ls {home} {home}/.ssh /Applications /Users 2>&1; echo rc=$?")
        # Every listing is refused: the only lines are the status header, errors and the exit code.
        body = [line for line in peek.splitlines()[1:] if line.strip()]
        assert body and all("Operation not permitted" in line or line.startswith("rc=") for line in body), peek

        python = agent_tools.shutil.which("python3")
        if python:
            net = _run_command(
                workspace,
                f"python3 -c \"import socket; socket.create_connection(('127.0.0.1', {port}), timeout=3)\"; echo rc=$?",
            )
            assert "rc=0" not in net and "PermissionError" in net, net
        with socket.create_connection(("127.0.0.1", port), timeout=3):  # the same call works outside the sandbox
            pass
    finally:
        listener.close()


@needs_macos_sandbox
def test_macos_sandbox_lets_git_commit_but_not_plant_config_or_hooks(tmp_path: Path) -> None:
    if agent_tools.shutil.which("git") is None:
        pytest.skip("git is required")
    agent_tools.subprocess.run(["git", "init", "-q", "."], cwd=tmp_path, check=True)
    for key, value in (("user.name", "Ana Dev"), ("user.email", "ana@example.com")):
        agent_tools.subprocess.run(["git", "config", key, value], cwd=tmp_path, check=True)
    before = (tmp_path / ".git" / "config").read_text(encoding="utf-8")

    result = _run_command(
        tmp_path,
        "echo ok > note.txt; git add note.txt; git commit -qm first; git log --format=%an; "
        "echo '[alias]' >> .git/config; echo x > .git/hooks/pre-commit; "
        "mv .git .git-moved; mkdir .git; echo '[core]' > .git/config",
    )

    assert "Ana Dev" in result
    assert result.count("Operation not permitted") >= 3, result
    assert (tmp_path / ".git" / "config").read_text(encoding="utf-8") == before
    assert not (tmp_path / ".git" / "hooks" / "pre-commit").exists()
    assert (tmp_path / "note.txt").read_text(encoding="utf-8") == "ok\n"


@needs_macos_sandbox
def test_macos_sandbox_scratch_is_removed_and_timeouts_kill_the_command(monkeypatch, tmp_path: Path) -> None:
    before = set(Path(agent_tools.tempfile.gettempdir()).glob("trinaxai-sandbox-*"))
    monkeypatch.setattr(agent_tools, "RUN_TIMEOUT_SECONDS", 2)
    result = _run_command(tmp_path, "echo $TMPDIR > tmpdir.txt; sleep 30")
    assert "timed out" in result
    assert set(Path(agent_tools.tempfile.gettempdir()).glob("trinaxai-sandbox-*")) == before
    scratch = Path((tmp_path / "tmpdir.txt").read_text(encoding="utf-8").strip())
    assert scratch.name.startswith("trinaxai-sandbox-") and not scratch.exists()
