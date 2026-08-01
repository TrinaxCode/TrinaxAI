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

    safe = format_tool_failure("search/tool", "api_key=secret", external=False)
    assert is_degraded_tool_result(safe)
    assert "api_key=[redacted]" in safe
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
