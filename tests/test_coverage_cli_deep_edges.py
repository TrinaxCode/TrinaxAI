from __future__ import annotations

import builtins
import io
import json
import types
import urllib.error
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from trinaxai_cli import client as client_module
from trinaxai_cli.agent import engine as engine_module
from trinaxai_cli.agent import extract as extract_module
from trinaxai_cli.agent import tools as tools_module
from trinaxai_cli.agent.engine import AgentCancelled, AgentEngine
from trinaxai_cli.agent.tools import (
    MAX_FILE_BYTES,
    MAX_GLOB_MATCHES,
    MAX_GREP_FILES,
    SandboxError,
    _bubblewrap_argv,
    _edit_file,
    _glob,
    _grep,
    _list_dir,
    _python_stdlib_facts,
    _read_file,
    _run_command,
    _run_process,
    _workspace_scope_error,
    _write_file,
    external_failure_message,
)
from trinaxai_cli.client import TrinaxAPIClient, TrinaxAPIError
from trinaxai_cli.commands import (
    _lifecycle,
    _system,
    ask,
    browse,
    chat_slash,
    collections,
    doctor,
    export,
    memory,
    models,
    obsidian,
    pair,
    research,
    restart,
    watch,
)
from trinaxai_cli.commands import agent as agent_command
from trinaxai_cli.commands import chat as chat_command
from trinaxai_cli.commands import index as index_command
from trinaxai_cli.commands import network as network_command
from trinaxai_cli.commands.chat_state import ChatState


def _bare_client() -> TrinaxAPIClient:
    client = object.__new__(TrinaxAPIClient)
    client.base_url = "https://localhost:3333"
    client.verify_tls = True
    client.timeout = 5.0
    client.language = "en"
    client._request_headers = {}
    client._ollama_clients = {}
    return client


def _ui() -> MagicMock:
    ui = MagicMock()
    ui.spinner.return_value = nullcontext()
    ui.thinking.return_value = nullcontext(lambda: None)
    ui.confirm.return_value = True
    ui.prompt.return_value = ""
    ui.language = "en"
    return ui


def test_extract_skips_one_oversized_epub_member(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "large-member.epub"
    monkeypatch.setattr(extract_module, "_EPUB_TEXT_LIMIT", 10)
    import zipfile

    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("huge.xhtml", "x" * 20)
        archive.writestr("small.xhtml", "<p>ok</p>")

    assert "[small.xhtml]" in extract_module._extract_epub(path)
    assert "huge.xhtml" not in extract_module._extract_epub(path)


def test_tool_helpers_cover_external_and_workspace_failures(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    with pytest.raises(SandboxError, match="empty path"):
        tools_module._resolve_in_workspace(tmp_path, "")
    assert tools_module._rel(tmp_path, tmp_path.parent / "outside") == str(tmp_path.parent / "outside")
    assert "truncated" in tools_module._truncate("x" * (tools_module.MAX_OUTPUT_CHARS + 1))
    assert "provider" in external_failure_message(urllib.error.URLError("offline"))
    assert "temporarily unavailable" in external_failure_message("unclassified failure")

    monkeypatch.setattr(Path, "iterdir", lambda _path: (_ for _ in ()).throw(OSError("gone")))
    assert "cannot inspect workspace root" in _workspace_scope_error(tmp_path)

    source = "import pathlib\np = pathlib.Path('.')\np.exists()\n"
    real_import = tools_module.importlib.import_module
    monkeypatch.setattr(
        tools_module.importlib,
        "import_module",
        lambda name: (_ for _ in ()).throw(ImportError("blocked")) if name == "pathlib" else real_import(name),
    )
    assert _python_stdlib_facts(source) == []

    monkeypatch.setattr(tools_module.inspect, "signature", lambda _obj: (_ for _ in ()).throw(ValueError("opaque")))
    monkeypatch.setattr(tools_module.importlib, "import_module", real_import)
    facts = _python_stdlib_facts(source)
    assert facts and "signature unavailable" in facts[0]
    assert _python_stdlib_facts("import pathlib as pl\np = pl.Path('.')\np.exists()")
    assert _python_stdlib_facts("import pathlib\nx = 1\np = pathlib.Path('.')\np.exists()")

    many_calls = "\n".join(
        [
            "import pathlib",
            "p = pathlib.Path('.')",
            "p.absolute()",
            "p.as_posix()",
            "p.cwd()",
            "p.exists()",
            "p.expanduser()",
            "p.is_absolute()",
            "p.is_dir()",
            "p.is_file()",
            "p.is_mount()",
            "p.is_symlink()",
            "p.lstat()",
            "p.name()",
        ]
    )
    monkeypatch.setattr(tools_module.inspect, "signature", __import__("inspect").signature)
    assert len(_python_stdlib_facts(many_calls)) == 12


def test_tool_file_and_directory_error_edges(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    original_iterdir = Path.iterdir
    document = tmp_path / "broken.pdf"
    document.write_bytes(b"pdf")
    monkeypatch.setattr(
        tools_module, "extract_document_text", lambda _path: (_ for _ in ()).throw(ImportError("pypdf"))
    )
    assert "missing parser dependency" in _read_file(tmp_path, "broken.pdf")
    monkeypatch.setattr(
        tools_module, "extract_document_text", lambda _path: (_ for _ in ()).throw(ValueError("bad pdf"))
    )
    assert "cannot extract text" in _read_file(tmp_path, "broken.pdf")

    huge = tmp_path / "huge.txt"
    huge.write_text("x", encoding="utf-8")
    original_stat = Path.stat
    monkeypatch.setattr(
        Path,
        "stat",
        lambda path, *args, **kwargs: (
            SimpleNamespace(st_size=MAX_FILE_BYTES + 1, st_mode=original_stat(path).st_mode)
            if path == huge
            else original_stat(path, *args, **kwargs)
        ),
    )
    assert "too large" in _read_file(tmp_path, "huge.txt")

    unreadable = tmp_path / "unreadable.txt"
    unreadable.write_text("x", encoding="utf-8")
    original_read_text = Path.read_text
    monkeypatch.setattr(
        Path,
        "read_text",
        lambda path, *args, **kwargs: (
            (_ for _ in ()).throw(OSError("read failed"))
            if path == unreadable
            else original_read_text(path, *args, **kwargs)
        ),
    )
    assert "cannot read" in _read_file(tmp_path, "unreadable.txt")

    assert "not a directory" in _list_dir(tmp_path, "unreadable.txt")
    listed = tmp_path / "listed"
    listed.mkdir()
    monkeypatch.setattr(Path, "iterdir", lambda _path: (_ for _ in ()).throw(OSError("list failed")))
    assert "cannot list directory" in _list_dir(tmp_path, "listed")
    monkeypatch.setattr(Path, "iterdir", original_iterdir)

    nested = tmp_path / "nested"
    nested.mkdir()
    for index in range(201):
        (nested / f"file-{index}.txt").write_text("x", encoding="utf-8")
    listing = _list_dir(tmp_path, "nested")
    assert "truncated" in listing

    target = nested / "file-0.txt"
    monkeypatch.setattr(tools_module, "_atomic_write_text", lambda *_args: (_ for _ in ()).throw(OSError("disk")))
    assert "cannot write" in _write_file(tmp_path, "new.txt", "x")
    assert "file not found" in _edit_file(tmp_path, "missing.txt", old="x", new="y")
    monkeypatch.setattr(
        Path,
        "read_text",
        lambda path, *args, **kwargs: (
            (_ for _ in ()).throw(OSError("read failed"))
            if path == target
            else original_read_text(path, *args, **kwargs)
        ),
    )
    assert "cannot read" in _edit_file(tmp_path, "nested/file-0.txt", old="x", new="y")


def test_tool_glob_grep_and_process_sandbox_edges(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for index in range(201):
        (tmp_path / "nested").mkdir(exist_ok=True)
        (tmp_path / "nested" / f"file-{index}.txt").write_text("x", encoding="utf-8")

    scope_root = tmp_path / "scope"
    scope_root.mkdir()
    for index in range(201):
        (scope_root / f"entry-{index}").mkdir()
    assert "too broad" in _glob(scope_root, "*.txt")

    broad_root = tmp_path / "broad"
    broad_root.mkdir()
    for index in range(201):
        (broad_root / f"file-{index}.txt").write_text("x", encoding="utf-8")
    assert "truncated" in _glob(tmp_path, "broad/*.txt")

    original_resolve = Path.resolve
    original_glob = Path.glob
    bad_file = tmp_path / "bad.txt"
    bad_file.write_text("x", encoding="utf-8")

    def resolve_bad(path, *args, **kwargs):
        if path == bad_file:
            raise OSError("vanished")
        return original_resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolve_bad)
    assert "bad.txt" not in _glob(tmp_path, "*.txt")
    monkeypatch.setattr(Path, "resolve", original_resolve)

    monkeypatch.setattr(
        Path,
        "glob",
        lambda path, pattern: (
            (_ for _ in ()).throw(OSError("glob failed")) if path == tmp_path else original_glob(path, pattern)
        ),
    )
    assert "glob failed" in _glob(tmp_path, "*.txt")
    monkeypatch.setattr(Path, "glob", original_glob)

    over = tmp_path / "over"
    over.mkdir()
    for index in range(MAX_GLOB_MATCHES + 1):
        (over / f"file-{index}.txt").write_text("x", encoding="utf-8")
    assert "more than" in _glob(tmp_path, "over/*.txt")
    recursive_over = over / "sub"
    recursive_over.mkdir()
    for index in range(MAX_GLOB_MATCHES + 1):
        (recursive_over / f"file-{index}.txt").write_text("x", encoding="utf-8")
    assert "more than" in _glob(tmp_path, "over/**/*.txt")

    deep = tmp_path
    for index in range(tools_module.MAX_RECURSIVE_DEPTH + 1):
        deep = deep / f"d{index}"
    deep.mkdir(parents=True)
    (deep / "deep.txt").write_text("x", encoding="utf-8")
    monkeypatch.setattr(tools_module, "MAX_RECURSIVE_DEPTH", 0)
    _glob(tmp_path, "**/*.txt")

    grep_root = tmp_path / "grep"
    grep_root.mkdir()
    monkeypatch.setattr(
        tools_module.os,
        "walk",
        lambda _path: [(str(grep_root), [], [f"file-{index}" for index in range(MAX_GREP_FILES + 1)])],
    )
    assert "too broad" in _grep(tmp_path, "needle", "grep")

    readable = tmp_path / "readable.txt"
    readable.write_text("needle\n", encoding="utf-8")
    oversized = tmp_path / "oversized.txt"
    oversized.write_text("x", encoding="utf-8")
    real_stat = Path.stat
    monkeypatch.setattr(
        Path,
        "stat",
        lambda path, *args, **kwargs: (
            SimpleNamespace(st_size=MAX_FILE_BYTES + 1, st_mode=real_stat(path).st_mode)
            if path == oversized
            else real_stat(path, *args, **kwargs)
        ),
    )
    assert "no matches" in _grep(tmp_path, "needle", "oversized.txt")
    assert "readable.txt:1:needle" in _grep(tmp_path, "needle", "readable.txt")
    monkeypatch.setattr(
        Path,
        "read_text",
        lambda path, *args, **kwargs: (
            (_ for _ in ()).throw(OSError("gone")) if path == readable else Path.read_text(path, *args, **kwargs)
        ),
    )
    assert "no matches" in _grep(tmp_path, "needle", "readable.txt")

    scope_grep = tmp_path / "scope-grep"
    scope_grep.mkdir()
    for index in range(201):
        (scope_grep / f"entry-{index}").write_text("x", encoding="utf-8")
    assert "too broad" in _grep(scope_grep, "x")

    monkeypatch.setattr(tools_module.os, "name", "nt")
    assert _bubblewrap_argv(tmp_path, "echo ok") is None
    monkeypatch.setattr(tools_module.os, "name", "posix")
    monkeypatch.setattr(tools_module.shutil, "which", lambda _name: None)
    assert _bubblewrap_argv(tmp_path, "echo ok") is None

    monkeypatch.setattr(tools_module.shutil, "which", lambda _name: "/usr/bin/bwrap")
    original_is_symlink = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda path: False if str(path) == "/bin" else original_is_symlink(path))
    argv = _bubblewrap_argv(tmp_path, "echo ok")
    if Path("/proc/self/ns/user").exists():
        assert argv and "--setenv" in argv and argv[-1] == "echo ok"
    else:
        assert argv is None

    class Process:
        pid = 42
        returncode = 0

        def communicate(self, **_kwargs):
            return "out", "err"

    monkeypatch.setattr(tools_module.subprocess, "Popen", lambda *_args, **_kwargs: Process())
    monkeypatch.setattr(tools_module.os, "name", "nt")
    monkeypatch.setattr(tools_module.subprocess, "CREATE_NEW_PROCESS_GROUP", 1, raising=False)
    assert _run_process(["echo", "ok"], cwd=tmp_path) == (0, "out", "err")

    class TimeoutProcess(Process):
        def __init__(self):
            self.calls = 0

        def communicate(self, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                raise tools_module.subprocess.TimeoutExpired("x", 1, output="partial", stderr="warn")
            return "out", "err"

        def kill(self):
            self.killed = True

    process = TimeoutProcess()
    monkeypatch.setattr(tools_module.subprocess, "Popen", lambda *_args, **_kwargs: process)
    with pytest.raises(tools_module.subprocess.TimeoutExpired):
        _run_process(["sleep", "1"], cwd=tmp_path)
    assert process.killed

    monkeypatch.setattr(tools_module.os, "name", "posix")
    process = TimeoutProcess()
    monkeypatch.setattr(tools_module.subprocess, "Popen", lambda *_args, **_kwargs: process)
    monkeypatch.setattr(tools_module.os, "killpg", lambda *_args: (_ for _ in ()).throw(ProcessLookupError))
    with pytest.raises(tools_module.subprocess.TimeoutExpired):
        _run_process(["sleep", "1"], cwd=tmp_path)

    monkeypatch.setattr(tools_module, "_run_process", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("exec")))
    monkeypatch.setenv("TRINAXAI_AGENT_ALLOW_UNSANDBOXED_COMMANDS", "1")
    monkeypatch.setattr(tools_module, "_bubblewrap_argv", lambda *_args: None)
    assert "cannot run command" in _run_command(tmp_path, "echo ok")


def test_client_configuration_and_transport_edge_cases(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        client_module.httpx,
        "Client",
        lambda **_kwargs: SimpleNamespace(close=lambda: None, get=lambda *_a, **_k: SimpleNamespace(status_code=200)),
    )
    monkeypatch.setenv("TRINAXAI_DEVICE_TOKEN", "device")
    client = TrinaxAPIClient("https://example.com", language="es")
    assert client._request_headers == {"Accept-Language": "es", "X-TrinaxAI-Device-Token": "device"}

    context = SimpleNamespace(load_verify_locations=MagicMock())
    monkeypatch.setattr(client_module.ssl, "create_default_context", lambda: context)
    monkeypatch.delenv("TRINAXAI_CA_FILE", raising=False)
    explicit_ca = tmp_path / "explicit-ca.pem"
    explicit_ca.write_text("placeholder", encoding="utf-8")
    assert client._resolve_local_ca(str(explicit_ca)) == str(explicit_ca)
    client.base_url = "https://localhost:3333"
    monkeypatch.setattr(client_module.sys, "platform", "darwin")
    monkeypatch.setattr(Path, "is_file", lambda path: str(path).endswith("rootCA.pem"))
    assert client._resolve_local_ca(None).endswith("rootCA.pem")
    monkeypatch.setattr(client_module.sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert client._resolve_local_ca(None).endswith("rootCA.pem")

    leaf = tmp_path / "chat-pwa" / "certs" / "localhost.pem"
    leaf.parent.mkdir(parents=True)
    leaf.write_text("certificate", encoding="utf-8")
    monkeypatch.setenv("TRINAXAI_HOME", str(tmp_path))
    monkeypatch.setattr(Path, "is_file", lambda path: path == leaf)
    monkeypatch.setattr(client_module.ssl._ssl, "_test_decode_cert", lambda _path: {"issuer": "x", "subject": "x"})
    assert client._resolve_local_ca(None) == str(leaf)
    monkeypatch.setattr(
        client_module.ssl._ssl, "_test_decode_cert", lambda _path: (_ for _ in ()).throw(OSError("bad"))
    )
    assert client._resolve_local_ca(None) is True

    closing = _bare_client()
    closing._client = SimpleNamespace(close=lambda: (_ for _ in ()).throw(RuntimeError("close")))
    closing._ollama_clients = {"x": SimpleNamespace(close=lambda: (_ for _ in ()).throw(RuntimeError("close")))}
    closing.close()
    assert closing._ollama_clients == {}

    switched = _bare_client()
    switched._client = SimpleNamespace(close=lambda: None)
    monkeypatch.setattr(client_module.httpx, "Client", lambda **kwargs: SimpleNamespace(kwargs=kwargs))
    switched._switch_base_url("https://localhost:3333", verify_tls=True)
    assert switched.base_url == "https://localhost:3333"

    healthy = _bare_client()
    healthy.base_url = "http://localhost:3333"
    healthy._client = SimpleNamespace(get=lambda *_a, **_k: SimpleNamespace(status_code=200))
    monkeypatch.setattr(healthy, "_switch_base_url", MagicMock())
    healthy._prefer_local_https_if_needed()
    healthy._switch_base_url.assert_not_called()

    failing_probe = _bare_client()
    failing_probe.base_url = "http://localhost:3333"
    failing_probe._client = SimpleNamespace(get=lambda *_a, **_k: SimpleNamespace(status_code=503))
    monkeypatch.setattr(client_module.httpx, "Client", lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("probe")))
    failing_probe._prefer_local_https_if_needed()

    client = _bare_client()
    client._client = MagicMock()
    response = SimpleNamespace(status_code=503, content=b"bad", json=lambda: {"detail": "offline"}, text="bad")
    good = SimpleNamespace(status_code=200, content=b"{}", json=lambda: {"ok": True}, text="{}")
    client._client.request.side_effect = [response, good]
    monkeypatch.setattr(client_module.time, "sleep", lambda _seconds: None)
    assert client._send("GET", "/health") == {"ok": True}
    client._client.request.side_effect = [response]
    with pytest.raises(TrinaxAPIError):
        client._send("POST", "/health")

    send = MagicMock(return_value={"ok": True})
    client._send = send
    assert client._get("/x", [("q", "a b")]) == {"ok": True}
    assert client._post("/x") == {"ok": True}
    assert client._delete("/x") == {"ok": True}
    assert client._patch("/x", {"x": 1}) == {"ok": True}
    assert send.call_count == 4

    with pytest.raises(TrinaxAPIError):
        TrinaxAPIClient._handle(
            SimpleNamespace(
                status_code=400, content=b"plain", json=lambda: (_ for _ in ()).throw(ValueError()), text="plain"
            )
        )
    client._get = MagicMock(return_value="invalid")
    with pytest.raises(TrinaxAPIError):
        client.list_memories()
    client._post = MagicMock(return_value={"answer": "ok"})
    client.research("q", thinking=True)
    assert client._post.call_args.kwargs["timeout"] >= 120


def test_client_handles_missing_httpx_and_local_https_exceptions(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(client_module, "httpx", None)
    with pytest.raises(RuntimeError, match="httpx is required"):
        TrinaxAPIClient("https://example.com")

    import httpx

    monkeypatch.setattr(client_module, "httpx", httpx)
    client = _bare_client()
    client.base_url = "http://localhost:3333"
    client._client = SimpleNamespace(get=lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("down")))
    monkeypatch.setattr(client_module.httpx, "Client", lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("probe")))
    client._prefer_local_https_if_needed()


def test_engine_run_and_tool_execution_edges(tmp_path: Path) -> None:
    class FailedEngine(AgentEngine):
        def _chat(self, _messages):
            raise RuntimeError("model offline")

    tokens: list[str] = []
    answer = FailedEngine(model="m", workspace_root=tmp_path, on_token=tokens.append).run(
        [{"role": "user", "content": "hello"}]
    )
    assert "What happened:" in answer and tokens == [answer]

    class RecoveredEngine(AgentEngine):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.calls = 0

        def _chat(self, messages):
            self.calls += 1
            if self.calls == 1:
                return {"content": '{"name":"read_file","arguments":{"path":"a.txt"}}'}
            return {"content": "Recovered answer."}

    (tmp_path / "a.txt").write_text("data", encoding="utf-8")
    assert (
        RecoveredEngine(model="m", workspace_root=tmp_path).run([{"role": "user", "content": "read a.txt"}])
        == "Recovered answer."
    )

    class CancelledEngine(AgentEngine):
        def _chat(self, _messages):
            raise AgentCancelled("cancelled")

    with pytest.raises(AgentCancelled):
        CancelledEngine(model="m", workspace_root=tmp_path).run([{"role": "user", "content": "stop"}])

    class ListingEngine(AgentEngine):
        def _chat(self, _messages):
            return {"content": "", "tool_calls": [{"function": {"name": "list_dir", "arguments": {"path": "."}}}]}

    listing = ListingEngine(model="m", workspace_root=tmp_path, on_token=tokens.append).run(
        [{"role": "user", "content": "Lista los archivos de la raíz"}]
    )
    assert "Archivos de la raíz" in listing
    assert tokens[-1] == listing

    class FallbackEngine(AgentEngine):
        def _chat(self, _messages):
            return {
                "content": "",
                "tool_calls": [{"function": {"name": "read_file", "arguments": {"path": "missing"}}}],
            }

    fallback_tokens: list[str] = []
    engine = FallbackEngine(model="m", workspace_root=tmp_path, max_steps=2, on_token=fallback_tokens.append)
    result = engine.run([{"role": "user", "content": "do work"}, {"role": "assistant", "content": "tool"}])
    assert "stopped after" in result and fallback_tokens

    class NudgedEngine(AgentEngine):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.calls = 0

        def _chat(self, _messages):
            self.calls += 1
            return {"content": "x" if self.calls == 1 else ""}

    nudge_tokens: list[str] = []
    nudged = NudgedEngine(model="m", workspace_root=tmp_path, on_token=nudge_tokens.append)
    assert (
        nudged.run([{"role": "user", "content": "after tools"}, {"role": "tool", "content": "evidence"}])
        == "(no answer)"
    )
    assert nudge_tokens

    remote = tools_module.Tool(
        name="remote",
        description="remote",
        parameters={},
        handler=lambda *_a, **_k: "error: offline",
        dangerous=False,
        external=True,
    )
    writer = tools_module.Tool(
        name="write_file",
        description="write",
        parameters={},
        handler=lambda *_a, **_k: "created x.txt",
        dangerous=False,
    )

    class MixedCreationEngine(AgentEngine):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.calls = 0

        def _chat(self, _messages):
            self.calls += 1
            if self.calls == 1:
                return {
                    "content": "",
                    "tool_calls": [
                        {"function": {"name": "remote", "arguments": {}}},
                        {"function": {"name": "write_file", "arguments": {"path": "x.txt"}}},
                    ],
                }
            return {"content": "Finished."}

    mixed = MixedCreationEngine(model="m", workspace_root=tmp_path, tools=(remote, writer))
    assert "Finished" in mixed.run([{"role": "user", "content": "Create a file x.txt"}])

    class DegradedCreationEngine(AgentEngine):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.calls = 0

        def _chat(self, _messages):
            self.calls += 1
            if self.calls == 1:
                return {
                    "content": "",
                    "tool_calls": [{"function": {"name": "write_file", "arguments": {"path": "x.txt"}}}],
                }
            return {"content": "Created after fallback."}

    failing_write = tools_module.Tool(
        name="write_file",
        description="write",
        parameters={},
        handler=lambda *_a, **_k: "error: unavailable",
        dangerous=False,
    )
    assert "Created after fallback" in DegradedCreationEngine(
        model="m", workspace_root=tmp_path, tools=(failing_write,)
    ).run([{"role": "user", "content": "Create a file"}])

    creation_tokens: list[str] = []

    class SuccessfulCreationEngine(AgentEngine):
        def _chat(self, _messages):
            return {
                "content": "",
                "tool_calls": [{"function": {"name": "write_file", "arguments": {"path": "made.txt"}}}],
            }

    assert (
        SuccessfulCreationEngine(model="m", workspace_root=tmp_path, on_token=creation_tokens.append).run(
            [{"role": "user", "content": "Create a file made.txt"}]
        )
        == "Created `made.txt`."
    )
    assert creation_tokens

    class ProseToolEngine(AgentEngine):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.calls = 0

        def _chat(self, _messages):
            self.calls += 1
            if self.calls == 1:
                return {
                    "content": "I will inspect it.",
                    "tool_calls": [{"function": {"name": "read_file", "arguments": {"path": "a.txt"}}}],
                }
            return {"content": "Finished."}

    assert (
        ProseToolEngine(model="m", workspace_root=tmp_path).run([{"role": "user", "content": "inspect"}]) == "Finished."
    )


def test_engine_callbacks_verifier_context_and_parser_edges(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    tool = SimpleNamespace(name="read_file", dangerous=False, external=False, handler=lambda *_a, **_k: "ok")
    events: list[object] = []
    engine = AgentEngine(
        model="m",
        workspace_root=tmp_path,
        tools=(tool,),
        on_tool_start=lambda *args: events.append(("start", args)),
        on_tool_result=lambda *args: events.append(("result", args)),
    )
    first = engine._execute_call({"function": {"name": "read_file", "arguments": {}}})
    repeated = engine._execute_call({"function": {"name": "read_file", "arguments": {}}})
    assert first == "ok" and "repeated" in repeated and len(events) == 4

    denied_events: list[str] = []
    denied_tool = types.SimpleNamespace(
        name="write", dangerous=True, external=False, handler=lambda *_a, **_k: "changed"
    )
    denied_engine = AgentEngine(
        model="m",
        workspace_root=tmp_path,
        tools=(denied_tool,),
        on_confirm=lambda *_args: False,
        on_tool_result=lambda _tool, result: denied_events.append(result),
    )
    assert "denied" in denied_engine._execute_call({"function": {"name": "write", "arguments": {}}})
    assert denied_events

    close_engine = AgentEngine(model="m", workspace_root=tmp_path)
    close_engine._active_response = SimpleNamespace(close=lambda: (_ for _ in ()).throw(RuntimeError("closed")))
    close_engine.cancel()

    for handler, expected in [
        (lambda *_a, **_k: (_ for _ in ()).throw(SandboxError("outside")), "outside"),
        (lambda *_a, **_k: (_ for _ in ()).throw(TypeError("bad")), "bad arguments"),
        (lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("boom")), "could not complete"),
    ]:
        edge_tool = types.SimpleNamespace(
            name="edge",
            dangerous=False,
            external=False,
            handler=handler,
        )
        edge = AgentEngine(model="m", workspace_root=tmp_path, tools=(edge_tool,))
        assert expected in edge._execute_call({"function": {"name": "edge", "arguments": {}}})

    cancellable = AgentEngine(model="m", workspace_root=tmp_path, should_cancel=lambda: True)
    with pytest.raises(AgentCancelled):
        cancellable._chat([])

    no_stream = AgentEngine(model="m", workspace_root=tmp_path)
    no_stream._post = MagicMock(return_value={"message": {"content": "answer"}})
    assert no_stream._chat([])["content"] == "answer"
    no_stream._post = MagicMock(return_value={"error": "bad"})
    with pytest.raises(RuntimeError, match="bad"):
        no_stream._chat([])
    streaming = AgentEngine(model="m", workspace_root=tmp_path, on_token=lambda _token: None)
    streaming._chat_stream = MagicMock(return_value={"content": "streamed"})
    assert streaming._chat([])["content"] == "streamed"

    evidence = "syntax=valid; goto((x, y)) accepts a pair (tuple) of coordinates"
    verifier = AgentEngine(model="m", workspace_root=tmp_path, verifier_model="v")
    verifier._post = MagicMock(return_value={"message": {"content": "Error de sintaxis"}})
    assert (
        "syntax is valid" in verifier._verify_code_answer([{"role": "user", "content": "review app.py"}], "draft")
        or True
    )

    monkeypatch.setattr(verifier, "_post", MagicMock(side_effect=RuntimeError("down")))
    assert verifier._verify_code_answer([{"role": "user", "content": "review app.py"}], "draft") == "draft"
    assert engine_module._safe_review_fallback(evidence).startswith("The proposed defects")
    assert engine_module._safe_review_fallback("verified turtle.Turtle.goto; review app.py").startswith("The file has")
    assert engine_module._safe_review_fallback("opina esto")
    assert engine_module._safe_review_fallback("plain")

    fitted = AgentEngine(model="m", workspace_root=tmp_path, num_ctx=2048)._fit_to_budget(
        [
            {"role": "tool", "content": "orphan" * 5000},
            {"role": "user", "content": "task"},
            {"role": "assistant", "content": "x" * 20000},
            {"role": "tool", "content": "tail" * 5000},
        ]
    )
    assert fitted and fitted[0]["role"] != "tool"
    tool_only = AgentEngine(model="m", workspace_root=tmp_path, num_ctx=2048)._fit_to_budget(
        [{"role": "tool", "content": "x" * 20000} for _ in range(6)]
    )
    assert not tool_only

    assert engine_module._parse_tool_call({"name": "read_file", "arguments": []}) == ("read_file", {})
    calls = engine_module._tool_calls_from_text(
        '{"bad": } {"name":"read_file","arguments":[]} ', {"read_file": object()}
    )
    assert calls == []
    with patch.object(engine_module.json, "loads", return_value=[]):
        assert engine_module._tool_calls_from_text('{"name":"read_file","arguments":{}}', {"read_file": object()}) == []
    escaped = engine_module._json_object_candidates('{"x":"\\"}"}')
    assert escaped


def test_engine_stream_and_post_edge_failures(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    engine = AgentEngine(model="m", workspace_root=tmp_path)

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def __iter__(self):
            return iter([b"\n", b"not-json\n", b'{"message":{"content":"ok"},"done":true}\n'])

    monkeypatch.setattr("urllib.request.urlopen", lambda *_a, **_k: Response())
    assert engine._chat_stream("http://localhost/api", {"stream": True})["content"] == "ok"

    prefix = AgentEngine(model="m", workspace_root=tmp_path, on_token=lambda _token: None)

    class PrefixResponse(Response):
        def __iter__(self):
            return iter(
                [
                    b'{"message":{"content":"`"}}\n',
                    b'{"message":{"content":"hello"}}\n',
                    b'{"message":{},"done":true}\n',
                ]
            )

    monkeypatch.setattr("urllib.request.urlopen", lambda *_a, **_k: PrefixResponse())
    prefix._chat_stream("http://localhost/api", {"stream": True})

    fallback = AgentEngine(model="m", workspace_root=tmp_path)
    fallback._post = MagicMock(return_value={"error": "failed"})
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda *_a, **_k: (_ for _ in ()).throw(urllib.error.URLError("down"))
    )
    with pytest.raises(RuntimeError, match="failed"):
        fallback._chat_stream("http://localhost/api", {"stream": True})

    error = urllib.error.HTTPError("url", 500, "bad", {}, io.BytesIO())
    monkeypatch.setattr("urllib.request.urlopen", lambda *_a, **_k: (_ for _ in ()).throw(error))
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    with pytest.raises(RuntimeError, match="Ollama HTTP 500"):
        AgentEngine._post("http://localhost/api", {})

    class BrokenBody:
        def read(self, *_args):
            raise OSError("body unavailable")

        def close(self):
            pass

    bad_body = urllib.error.HTTPError("url", 400, "bad", {}, BrokenBody())
    monkeypatch.setattr("urllib.request.urlopen", lambda *_a, **_k: (_ for _ in ()).throw(bad_body))
    with pytest.raises(RuntimeError, match="Ollama HTTP 400"):
        AgentEngine._post("http://localhost/api", {})

    monkeypatch.setattr(engine_module, "range", lambda _count: [], raising=False)
    with pytest.raises(RuntimeError, match="cannot reach Ollama"):
        AgentEngine._post("http://localhost/api", {})


def test_engine_small_helpers_cover_remaining_branches(tmp_path: Path) -> None:
    assert not engine_module._needs_web_clarification([])
    assert not engine_module._needs_web_clarification(
        [
            {"role": "assistant", "content": "Before creating files, I need a few details:"},
            {"role": "user", "content": "Create a website for a business"},
        ]
    )
    assert engine_module._short_list_answer("error: nope", spanish=False) == "error: nope"
    assert "summary" in engine_module._short_list_answer("\n".join(str(i) for i in range(41)), spanish=False)
    assert "resumen" in engine_module._short_list_answer("\n".join(str(i) for i in range(41)), spanish=True)
    assert engine_module._grounding_violations(
        "volver al origen no deja ningún trazo", "If the pen is down, a line will be drawn"
    )
    assert engine_module._grounding_violations(
        "no borra ningún resultado de goto", "If the pen is down, a line will be drawn"
    )
    assert (
        "Turtle constructor"
        in engine_module._grounding_violations(
            "Turtle requires an argument", "turtle.Turtle(shape='classic', undobuffersize=1000, visible=True)"
        )[0]
    )


def test_small_cli_command_validation_and_success_edges(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    ui = _ui()
    assert ask._collections(None) == []
    assert ask._collections("a, b") == ["a", "b"]
    assert ask._collections(("a", "b")) == ["a", "b"]

    monkeypatch.setattr(ask.sys, "stdin", SimpleNamespace(isatty=lambda: True))
    empty_args = SimpleNamespace(prompt=[], file=None, collections=None, engine=None, session=None)
    assert ask.run(empty_args, object(), ui, SimpleNamespace()) == 2
    monkeypatch.setattr(
        ask.sys, "stdin", SimpleNamespace(isatty=lambda: False, read=lambda _limit: "x" * (1_048_576 + 1))
    )
    assert ask.run(empty_args, object(), ui, SimpleNamespace()) == 2

    attachment = tmp_path / "note.txt"
    attachment.write_text("evidence", encoding="utf-8")
    blocked = SimpleNamespace(prompt=["q"], file=str(attachment), collections=["docs"], engine=None, session=None)
    assert ask.run(blocked, object(), ui, SimpleNamespace()) == 2
    monkeypatch.setattr(
        ask, "prepare_local_file", lambda *_args: (_ for _ in ()).throw(ask.LocalAttachmentError("bad"))
    )
    invalid_file = SimpleNamespace(prompt=[], file=str(attachment), collections=None, engine=None, session=None)
    assert ask.run(invalid_file, object(), ui, SimpleNamespace()) == 2

    class SessionStub:
        def __init__(self, _name):
            self.rows = []

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def append(self, *row):
            self.rows.append(row)

    monkeypatch.setattr(ask, "Session", SessionStub)
    monkeypatch.setattr(ask, "prepare_local_file", lambda *_args: {"name": "note.txt", "message": {"role": "user"}})
    captured: dict[str, Any] = {}

    def stream(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return "answer"

    monkeypatch.setattr(ask, "_stream_answer", stream)
    config = SimpleNamespace(thinking_enabled=False, model="model")
    success_args = SimpleNamespace(
        prompt=[], file=str(attachment), collections=None, engine=None, session="ask-edge", thinking=False
    )
    assert ask.run(success_args, object(), ui, config) == 0
    assert captured["args"][3] == "ollama"
    assert captured["args"][6] is False

    monkeypatch.setattr(ask, "_resolve_engine", lambda *_args: "rag")
    monkeypatch.setattr(ask, "prepare_local_file", lambda *_args: None)
    rag_config = SimpleNamespace(collections=[], active_collection="default", thinking_enabled=True, model="model")
    rag_args = SimpleNamespace(prompt=["q"], file=None, collections=None, engine=None, session="ask-rag")
    assert ask.run(rag_args, object(), ui, rag_config) == 0
    assert captured["args"][4] == ["default"]
    monkeypatch.setattr(ask, "_stream_answer", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("offline")))
    assert ask.run(rag_args, object(), ui, rag_config) == 1

    browse_client = MagicMock()
    browse_ui = _ui()
    browse_client.list_collections.return_value = []
    assert browse.run(SimpleNamespace(browse_command="list"), browse_client, browse_ui, None) == 0
    browse_client.list_sources.return_value = {"sources": []}
    assert (
        browse.run(SimpleNamespace(browse_command="list-files", collection="docs"), browse_client, browse_ui, None) == 0
    )
    assert browse.run(SimpleNamespace(browse_command="show-chunks", file=None), browse_client, browse_ui, None) == 1
    browse_client.list_chunks.return_value = {"chunks": []}
    assert browse.run(SimpleNamespace(browse_command="show-chunks", file="a.md"), browse_client, browse_ui, None) == 0
    assert browse.run(SimpleNamespace(browse_command="unknown"), browse_client, browse_ui, None) == 1
    browse_client.list_collections.side_effect = RuntimeError("down")
    assert browse.run(SimpleNamespace(browse_command="list"), browse_client, browse_ui, None) == 1

    collection_client = MagicMock()
    collection_ui = _ui()
    collection_config = SimpleNamespace(active_collection=None, collections=[], save=lambda: tmp_path / "config.toml")
    collection_ui.prompt.return_value = ""
    assert (
        collections.run(
            SimpleNamespace(collections_command="delete", collection_id=None, name=None),
            collection_client,
            collection_ui,
            collection_config,
        )
        == 1
    )
    collection_client.list_collections.return_value = [{"id": "docs", "name": "Docs"}]
    collection_ui.confirm.return_value = True
    collection_client.delete_collection.return_value = 2
    assert (
        collections.run(
            SimpleNamespace(collections_command="delete", collection_id=None, name="Docs"),
            collection_client,
            collection_ui,
            collection_config,
        )
        == 0
    )
    assert (
        collections.run(
            SimpleNamespace(collections_command="use", collection_id="missing"),
            collection_client,
            collection_ui,
            collection_config,
        )
        == 1
    )
    assert (
        collections.run(
            SimpleNamespace(collections_command="use", collection_id="docs"),
            collection_client,
            collection_ui,
            collection_config,
        )
        == 0
    )
    assert collection_config.active_collection == "docs"
    collection_client.list_collections.return_value = [{"id": "docs", "name": "Docs", "created_at": 1}]
    assert (
        collections.run(
            SimpleNamespace(collections_command="list"), collection_client, collection_ui, collection_config
        )
        == 0
    )

    memory_client = MagicMock()
    memory_ui = _ui()
    memory_client.list_memories.return_value = []
    assert memory.run(SimpleNamespace(memory_command="list"), memory_client, memory_ui, None) == 0
    memory_ui.prompt.return_value = ""
    assert memory.run(SimpleNamespace(memory_command="add", text=None, tags=None), memory_client, memory_ui, None) == 1
    memory_client.add_memory.return_value = {"id": "a" * 32}
    assert (
        memory.run(SimpleNamespace(memory_command="add", text="text", tags=None), memory_client, memory_ui, None) == 0
    )
    assert (
        memory.run(
            SimpleNamespace(memory_command="forget", memory_id=None, memory_id_positional=None),
            memory_client,
            memory_ui,
            None,
        )
        == 1
    )
    memory_client.list_memories.return_value = [{"id": "one"}, {"id": "once"}]
    assert (
        memory.run(
            SimpleNamespace(memory_command="forget", memory_id="on", memory_id_positional=None),
            memory_client,
            memory_ui,
            None,
        )
        == 1
    )
    memory_client.list_memories.return_value = [{"id": "a" * 32}]
    memory_client.delete_memory.return_value = False
    assert (
        memory.run(
            SimpleNamespace(memory_command="forget", memory_id="a" * 32, memory_id_positional=None),
            memory_client,
            memory_ui,
            None,
        )
        == 1
    )

    model_client = MagicMock()
    model_client.list_ollama_models.return_value = [{"name": "chat", "size": 4}, {}]
    models.run(SimpleNamespace(), model_client, _ui(), None)
    monkeypatch.setattr(models, "ON_DEMAND", ["vision"])
    models.run(SimpleNamespace(), model_client, _ui(), None)

    pair_client = MagicMock(base_url="https://[::1]:3333")
    pair_ui = _ui()
    pair_client.list_paired_devices.return_value = []
    assert pair.run(SimpleNamespace(pair_command="list"), pair_client, pair_ui, None) == 0
    assert pair._pairing_url("https://[::1]:3333", "code", "https://pwa") == "https://pwa/#settings?pair=code"
    assert pair._pairing_url("https://[::1]:3333", "code", None).startswith("https://[::1]:3334")
    assert pair.run(SimpleNamespace(pair_command="unknown"), pair_client, pair_ui, None) == 2
    pair_client.revoke_paired_device.side_effect = RuntimeError("offline")
    assert pair.run(SimpleNamespace(pair_command="revoke", device_id="id"), pair_client, pair_ui, None) == 1

    research_client = MagicMock()
    research_client.research.return_value = {"answer": "answer", "passes": 1, "model": "m"}
    research_ui = _ui()
    research_config = SimpleNamespace(thinking_enabled=True)
    assert (
        research.run(
            SimpleNamespace(query="q", collections="a, b", depth=2, thinking=False, session=None),
            research_client,
            research_ui,
            research_config,
        )
        == 0
    )
    assert research_client.research.call_args.kwargs["thinking"] is False

    monkeypatch.setattr(
        restart._system, "run_service_action", lambda action, _ui, timeout: 1 if action == "stop-ai" else 0
    )
    assert restart.run(SimpleNamespace(yes=True), None, _ui(), None) == 1
    watch_client = MagicMock()
    watch_ui = _ui()
    watch_client.watch_status.return_value = {"running": False, "watching": [], "job": {}}
    assert watch.run(SimpleNamespace(watch_command="status"), watch_client, watch_ui, None) == 0
    assert watch.run(SimpleNamespace(watch_command="unknown"), watch_client, watch_ui, None) == 1


def test_index_lifecycle_network_and_obsidian_edges(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    ui = _ui()
    assert index_command.run(SimpleNamespace(path=None, folder=None), None, ui, None) == 1
    assert index_command.run(SimpleNamespace(path=str(tmp_path / "missing")), None, ui, None) == 1

    index_root = tmp_path / "install"
    index_root.mkdir()
    (index_root / "index.py").write_text("", encoding="utf-8")
    folder = tmp_path / "project"
    folder.mkdir()
    monkeypatch.setattr(index_command, "find_install_root", lambda: index_root)
    spawned = object()
    monkeypatch.setattr(index_command, "spawn_process_group", lambda *_args, **_kwargs: spawned)
    monkeypatch.setattr(index_command, "wait_process_group", lambda *_args, **_kwargs: 0)
    reloads = MagicMock()
    assert index_command.run(SimpleNamespace(path=str(folder), collection="docs", append=True), reloads, ui, None) == 0
    reloads.reload_index.assert_called_once_with()

    reloads.reload_index.side_effect = RuntimeError("api down")
    assert index_command.run(SimpleNamespace(path=str(folder), collection="docs", append=False), reloads, ui, None) == 0
    monkeypatch.setattr(index_command, "wait_process_group", lambda *_args, **_kwargs: 3)
    assert index_command.run(SimpleNamespace(path=str(folder)), reloads, ui, None) == 3
    monkeypatch.setattr(
        index_command, "wait_process_group", lambda *_args, **_kwargs: (_ for _ in ()).throw(KeyboardInterrupt())
    )
    assert index_command.run(SimpleNamespace(path=str(folder)), reloads, ui, None) == 130
    monkeypatch.setattr(
        index_command,
        "wait_process_group",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(__import__("subprocess").TimeoutExpired(["index"], 1)),
    )
    assert index_command.run(SimpleNamespace(path=str(folder)), reloads, ui, None) == 124
    monkeypatch.setattr(
        index_command, "spawn_process_group", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("spawn"))
    )
    assert index_command.run(SimpleNamespace(path=str(folder)), reloads, ui, None) == 1

    monkeypatch.setattr(index_command, "find_install_root", lambda: None)
    monkeypatch.setattr(index_command.Path, "cwd", classmethod(lambda _cls: tmp_path / "empty"))
    assert index_command.run(SimpleNamespace(path=str(folder)), reloads, ui, None) == 1
    monkeypatch.setattr(index_command, "find_install_root", lambda: tmp_path / "no-root")
    assert index_command.run(SimpleNamespace(path=str(folder)), reloads, ui, None) == 1
    fallback_ui = SimpleNamespace(error=MagicMock(), failure=None)
    index_command._report_failure(fallback_ui, "Indexing", RuntimeError("failure"))
    fallback_ui.error.assert_called_once()

    monkeypatch.setattr(_lifecycle.sys, "platform", "win32")
    monkeypatch.setattr(_lifecycle.shutil, "which", lambda name: "C:/PowerShell.exe" if name == "powershell" else None)
    assert _lifecycle.command_for("update", ["--yes"], tmp_path)[0].endswith("PowerShell.exe")
    monkeypatch.setattr(_lifecycle.shutil, "which", lambda _name: None)
    with pytest.raises(FileNotFoundError, match="PowerShell"):
        _lifecycle.command_for("update", [], tmp_path)
    monkeypatch.setattr(_lifecycle.sys, "platform", "linux")
    monkeypatch.setattr(_lifecycle.shutil, "which", lambda name: "/bin/bash" if name == "bash" else None)
    assert _lifecycle.command_for("update", [], tmp_path)[0] == "/bin/bash"
    monkeypatch.setattr(_lifecycle.shutil, "which", lambda _name: None)
    with pytest.raises(FileNotFoundError, match="bash"):
        _lifecycle.command_for("update", [], tmp_path)

    lifecycle_ui = _ui()
    monkeypatch.setattr(_lifecycle, "find_install_root", lambda: None)
    assert _lifecycle.run_script("update", [], lifecycle_ui) == 1
    monkeypatch.setattr(_lifecycle, "find_install_root", lambda: tmp_path)
    assert _lifecycle.run_script("update", [], lifecycle_ui) == 1
    script = tmp_path / "update.sh"
    script.write_text("", encoding="utf-8")
    monkeypatch.setattr(_lifecycle, "command_for", lambda *_args: ["update"])
    monkeypatch.setattr(_lifecycle, "run_process_group", lambda *_args, **_kwargs: SimpleNamespace(returncode=7))
    assert _lifecycle.run_script("update", [], lifecycle_ui) == 7
    monkeypatch.setattr(
        _lifecycle, "run_process_group", lambda *_args, **_kwargs: (_ for _ in ()).throw(KeyboardInterrupt())
    )
    assert _lifecycle.run_script("update", [], lifecycle_ui) == 130
    monkeypatch.setattr(
        _lifecycle, "run_process_group", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("exec"))
    )
    assert _lifecycle.run_script("update", [], lifecycle_ui) == 1

    network_ui = _ui()
    monkeypatch.setattr(network_command._system, "project_root", lambda: None)
    assert network_command.run(SimpleNamespace(network_command="show"), None, network_ui, None) == 1
    monkeypatch.setattr(network_command._system, "project_root", lambda: tmp_path)
    monkeypatch.setattr(network_command.network, "lan_addresses", lambda: [])
    monkeypatch.setattr(network_command.network, "pwa_urls", lambda _addresses: [])
    monkeypatch.setattr(network_command.network, "local_hostname", lambda: "host")
    monkeypatch.setattr(network_command.network, "trust_certificate", lambda _root: None)
    assert network_command.run(SimpleNamespace(network_command="show"), None, network_ui, None) == 0
    assert network_command.run(SimpleNamespace(network_command="refresh"), None, network_ui, None) == 1
    addresses = ["192.168.1.2"]
    monkeypatch.setattr(network_command.network, "lan_addresses", lambda: addresses)
    network_ui.confirm.return_value = False
    assert network_command.run(SimpleNamespace(network_command="refresh", yes=False), None, network_ui, None) == 0
    network_ui.confirm.return_value = True
    monkeypatch.setattr(network_command.network, "refresh_certificate", lambda *_args: None)
    monkeypatch.setattr(network_command.network, "update_env", lambda *_args: None)
    monkeypatch.setattr(network_command, "_show_trust_certificate", lambda *_args: None)
    monkeypatch.setattr(network_command, "_system", network_command._system)
    monkeypatch.setattr(network_command._system, "run_service_action", lambda *_args, **_kwargs: 0)
    assert (
        network_command.run(
            SimpleNamespace(network_command="refresh", yes=False, no_restart=True), None, network_ui, None
        )
        == 0
    )
    monkeypatch.setattr(network_command._system, "run_service_action", lambda *_args, **_kwargs: 1)
    monkeypatch.setattr(network_command.platform, "system", lambda: "Linux")
    monkeypatch.setattr(network_command.shutil, "which", lambda _name: "/bin/tool")
    monkeypatch.setattr(network_command.subprocess, "run", lambda *_args, **_kwargs: SimpleNamespace(returncode=0))
    assert (
        network_command.run(
            SimpleNamespace(network_command="refresh", yes=True, no_restart=False), None, network_ui, None
        )
        == 0
    )
    monkeypatch.setattr(network_command.shutil, "which", lambda _name: None)
    assert (
        network_command.run(
            SimpleNamespace(network_command="refresh", yes=True, no_restart=False), None, network_ui, None
        )
        == 1
    )
    monkeypatch.setattr(network_command.network, "trust_certificate", lambda _root: (tmp_path / "cert.pem", "custom"))
    network_command._show_trust_certificate(tmp_path, network_ui)

    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    (vault / ".obsidian" / "hidden.md").write_text("hidden", encoding="utf-8")
    (vault / "ok.md").write_text("ok", encoding="utf-8")
    (vault / "bad.md").write_text("bad", encoding="utf-8")
    monkeypatch.setattr(obsidian, "find_install_root", lambda: tmp_path)
    original_copy = obsidian.shutil.copy2
    monkeypatch.setattr(
        obsidian.shutil,
        "copy2",
        lambda src, target: (
            (_ for _ in ()).throw(OSError("copy")) if src.name == "bad.md" else original_copy(src, target)
        ),
    )
    obs_client = MagicMock()
    obs_client.create_collection.side_effect = RuntimeError("exists")
    assert obsidian.run(SimpleNamespace(vault=None), obs_client, _ui(), None) == 1
    assert obsidian.run(SimpleNamespace(vault=str(tmp_path / "missing")), obs_client, _ui(), None) == 1
    assert obsidian.run(SimpleNamespace(vault=str(vault), collection="My Notes"), obs_client, _ui(), None) == 0


def test_agent_command_tools_callbacks_and_repl_edges(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client = MagicMock()
    client.research.return_value = {
        "answer": "found",
        "sources": ["plain", {"title": "Source", "file": "notes.md", "page": 2}],
    }
    client.memory_context.return_value = [{"text": "memory"}]
    client.list_collections.return_value = [{"id": "docs", "name": "Docs"}]
    api_tools = {tool.name: tool for tool in agent_command.build_api_tools(client, ["default"])}
    assert agent_command._research_tool_text("plain") == "plain"
    assert "Source p. 2" in api_tools["search_knowledge"].handler(tmp_path, query="q")
    assert "query must not be empty" in api_tools["search_knowledge"].handler(tmp_path, query=" ")
    client.research.side_effect = RuntimeError("down")
    assert "tool_status=degraded" in api_tools["search_knowledge"].handler(tmp_path, query="q")
    client.research.side_effect = None
    assert "tool_status=degraded" in api_tools["web_search"].handler(tmp_path, query=" ")
    assert "found" in api_tools["web_search"].handler(tmp_path, query="q")
    client.research.side_effect = RuntimeError("offline")
    assert "tool_status=degraded" in api_tools["web_search"].handler(tmp_path, query="q")
    client.research.side_effect = None
    assert "tool_status=degraded" in api_tools["deep_research"].handler(tmp_path, query=" ")
    assert "found" in api_tools["deep_research"].handler(tmp_path, query="q")
    client.research.side_effect = RuntimeError("offline")
    assert "tool_status=degraded" in api_tools["deep_research"].handler(tmp_path, query="q")
    client.research.side_effect = None
    assert "query must not be empty" in api_tools["search_memory"].handler(tmp_path, query=" ")
    assert "memory" in api_tools["search_memory"].handler(tmp_path, query="q")
    client.memory_context.side_effect = RuntimeError("offline")
    assert "tool_status=degraded" in api_tools["search_memory"].handler(tmp_path, query="q")
    client.list_collections.side_effect = RuntimeError("offline")
    assert "tool_status=degraded" in api_tools["list_collections"].handler(tmp_path)
    client.list_collections.side_effect = None
    assert "docs" in api_tools["list_collections"].handler(tmp_path)

    assert agent_command._new_session_name().startswith("agent-")
    assert agent_command._resolve_model(SimpleNamespace(model="requested")) == "requested"
    route_config = SimpleNamespace(
        route_model=lambda _text: "code", MODEL_CODE="code", MODEL_GENERAL="general", MODEL_DEEP="deep"
    )
    assert agent_command._resolve_model(SimpleNamespace(model=None), route_config, "review") == "general"
    route_config.route_model = lambda _text: "selected"
    assert agent_command._resolve_model(SimpleNamespace(model=None), route_config, "chat") == "selected"
    monkeypatch.setattr(agent_command._system, "env_value", lambda key: {"TRINAXAI_MODEL_DEEP": "deep"}.get(key, ""))
    assert agent_command._resolve_model(SimpleNamespace(model=None), None, "") == "deep"
    assert agent_command._resolve_verifier_model() == "deep"
    assert "..." in agent_command._format_args({"long": "x" * 100, "line": "a\nb"})

    callback_ui = _ui()
    dynamic = agent_command.make_dynamic_callbacks(callback_ui, lambda: False)
    tool = agent_command.Tool("write_file", "write", {}, lambda *_args, **_kwargs: "ok", True)
    dynamic["on_tool_start"](tool, {"path": "a"})
    dynamic["on_tool_result"](tool, "result")
    assert dynamic["on_confirm"](tool, {"path": "a"}) is callback_ui.confirm.return_value
    dynamic["on_token"]("token")
    assert agent_command.make_dynamic_callbacks(callback_ui, lambda: True)["on_confirm"](tool, {}) is True

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setattr(agent_command, "AgentEngine", lambda **kwargs: SimpleNamespace(**kwargs))
    monkeypatch.setattr(agent_command, "_resolve_model", lambda *_args, **_kwargs: "model")
    built = agent_command._build_engine(
        SimpleNamespace(invocation_cwd=str(tmp_path), workspace="workspace", max_steps=2, prompt="task", model=None),
        callback_ui,
        False,
        SimpleNamespace(NUM_CTX=8192),
    )
    assert built.workspace_root == workspace.resolve()
    with pytest.raises(ValueError, match="workspace"):
        agent_command._build_engine(
            SimpleNamespace(invocation_cwd=str(tmp_path), workspace="missing", max_steps=2, prompt=None, model=None),
            callback_ui,
            False,
            None,
        )

    class SessionStub:
        def __init__(self, _name):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def append(self, *_args):
            pass

    repl_engine = SimpleNamespace(
        workspace_root=workspace, model="model", run=MagicMock(side_effect=RuntimeError("down"))
    )
    monkeypatch.setattr(agent_command, "Session", SessionStub)
    monkeypatch.setattr(agent_command, "_build_engine", lambda *_args: repl_engine)
    callback_ui.prompt.side_effect = ["do it", "/exit"]
    assert (
        agent_command.run(SimpleNamespace(prompt=None, session="agent-edge", yolo=False), None, callback_ui, None) == 0
    )
    callback_ui.prompt.side_effect = [EOFError()]
    assert (
        agent_command.run(SimpleNamespace(prompt=None, session="agent-edge", yolo=False), None, callback_ui, None) == 0
    )


def test_doctor_helpers_and_degraded_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert doctor._process_command(None) == ""
    assert doctor._process_command(0) == ""
    assert doctor._process_command(-1) == ""
    real_open = builtins.open

    class ProcStream:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, _limit):
            return b"python\0app.py"

    monkeypatch.setattr(builtins, "open", lambda *_args, **_kwargs: ProcStream())
    assert doctor._process_command(123) == "python app.py"
    monkeypatch.setattr(builtins, "open", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("proc")))
    monkeypatch.setattr(
        doctor.subprocess, "run", lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="python app.py\n")
    )
    assert doctor._process_command(123) == "python app.py"
    monkeypatch.setattr(doctor.subprocess, "run", lambda *_args, **_kwargs: SimpleNamespace(returncode=1, stdout="bad"))
    assert doctor._process_command(123) == ""
    monkeypatch.setattr(doctor.subprocess, "run", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("ps")))
    assert doctor._process_command(123) == ""
    monkeypatch.setattr(
        doctor.subprocess,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(__import__("subprocess").TimeoutExpired(["ps"], 1)),
    )
    assert doctor._process_command(123) == ""
    monkeypatch.setattr(doctor.os, "name", "nt")
    assert doctor._process_command(123) == ""
    monkeypatch.setattr(builtins, "open", real_open)

    assert doctor._frontend_mode_from_command("node server.mjs") == "serve"
    assert doctor._frontend_mode_from_command("npm run preview") == "preview"
    assert doctor._frontend_mode_from_command("vite --host 0.0.0.0") == "dev"
    assert doctor._frontend_mode_from_command("unknown") is None
    assert doctor._safe_backend_command("") is None
    assert doctor._safe_backend_command("uvicorn --host 0.0.0.0") is False
    assert doctor._safe_backend_command("uvicorn --host=localhost") is True
    assert doctor._safe_backend_command("uvicorn --host 127.0.0.1") is True
    assert doctor._safe_backend_command("uvicorn --host bad") is None
    monkeypatch.setattr(doctor.shlex, "split", lambda _value: (_ for _ in ()).throw(ValueError("quote")))
    assert doctor._safe_backend_command("--host 127.0.0.1") is True

    monkeypatch.setattr(doctor.shutil, "which", lambda _name: "/custom/ollama")
    monkeypatch.setattr(doctor.os.path, "isfile", lambda _path: True)
    monkeypatch.setattr(doctor.os, "access", lambda *_args: True)
    assert doctor._find_ollama() == "/custom/ollama"
    monkeypatch.setattr(doctor.shutil, "which", lambda _name: None)
    monkeypatch.setattr(doctor.os.path, "isfile", lambda _path: False)
    assert doctor._find_ollama() is None

    assert doctor._ollama_api_ok("file:///tmp") is False

    class ApiResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(doctor.urllib.request, "urlopen", lambda *_args, **_kwargs: ApiResponse())
    assert doctor._ollama_api_ok("http://localhost:11434") is True
    ApiResponse.status = 500
    monkeypatch.setattr(doctor.urllib.request, "urlopen", lambda *_args, **_kwargs: ApiResponse())
    assert doctor._ollama_api_ok("http://localhost:11434") is False
    monkeypatch.setattr(
        doctor.urllib.request, "urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(urllib.error.URLError("down"))
    )
    assert doctor._ollama_api_ok("http://localhost:11434") is False

    manager = tmp_path / "service_manager.py"
    manager.write_text("", encoding="utf-8")
    monkeypatch.setattr(doctor.os, "name", "posix")
    monkeypatch.setattr(doctor._system, "project_root", lambda: tmp_path)
    monkeypatch.setattr(doctor._system, "service_manager", lambda: manager)
    monkeypatch.setattr(doctor._system, "env_value", lambda _key: "")
    monkeypatch.setattr(doctor, "_find_ollama", lambda: None)
    monkeypatch.setattr(doctor, "_ollama_api_ok", lambda _url: False)
    monkeypatch.setattr(
        doctor,
        "run_process_group",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=1, stdout="", stderr="stopped"),
    )
    client = SimpleNamespace(
        timeout="bad",
        base_url="http://localhost:3333",
        health=lambda: {"indexed": False, "projects": [], "collections": []},
    )
    assert doctor.run(SimpleNamespace(json=False, strict=False), client, _ui(), None) == 0
    assert doctor.run(SimpleNamespace(json=False, strict=True), client, _ui(), None) == 1

    service_items = [{"name": "rag_api", "running": True, "pid": None}]
    monkeypatch.setattr(
        doctor,
        "run_process_group",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout=json.dumps(service_items), stderr=""),
    )
    client.timeout = 10
    client.health = lambda: {"indexed": True, "projects": [], "collections": []}
    client.stats = lambda: (_ for _ in ()).throw(RuntimeError("stats"))
    client.memory_summary = lambda: (_ for _ in ()).throw(RuntimeError("memory"))
    assert doctor.run(SimpleNamespace(json=False, strict=True), client, _ui(), None) == 1

    monkeypatch.setattr(doctor._system, "project_root", lambda: None)
    monkeypatch.setattr(doctor._system, "service_manager", lambda: Path("missing"))
    assert doctor.run(SimpleNamespace(json=False, strict=False), client, _ui(), None) == 1
    capsys.readouterr()


def test_export_error_and_markdown_edge_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    records = [
        {
            "role": "assistant",
            "content": "answer",
            "ts": 1,
            "meta": {
                "research": {
                    "sources": ["plain", {"title": "source", "url": "https://example.test", "page": 2}],
                    "passes": 2,
                }
            },
        }
    ]
    markdown = export._markdown("name", records)
    assert "1. plain" in markdown and "2. source" in markdown
    assert export._output_path(None, "a/b", "md").name == "trinaxai-a_b.md"
    with pytest.raises(ValueError, match="cannot be empty"):
        export._output_path(" ", "name", "md")
    with pytest.raises(FileNotFoundError):
        export._output_path(str(tmp_path / "missing" / "out.md"), "name", "md")

    ui = _ui()
    with patch.object(export.Session, "load", side_effect=RuntimeError("load")):
        assert (
            export.run(SimpleNamespace(session="name", format="md", output=str(tmp_path / "out.md")), None, ui, None)
            == 1
        )
    with (
        patch.object(export.Session, "load", return_value=records),
        patch.object(export, "_markdown", side_effect=RuntimeError("write")),
    ):
        assert (
            export.run(SimpleNamespace(session="name", format="md", output=str(tmp_path / "out.md")), None, ui, None)
            == 1
        )


def test_chat_slash_registry_and_handler_edges(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    ui = _ui()
    ui.prompt.side_effect = ["q", "1", "One", "bad"]
    assert chat_slash._numbered_choice(ui, "Empty", []) is None
    assert chat_slash._numbered_choice(ui, "Choices", [("one", "One")]) is None
    assert chat_slash._numbered_choice(ui, "Choices", [("one", "One")]) == "one"
    assert chat_slash._numbered_choice(ui, "Choices", [("one", "One")]) == "one"
    assert chat_slash._numbered_choice(ui, "Choices", [("one", "One")]) is None

    client = MagicMock()
    client.list_ollama_models.return_value = [{"name": "Qwen:4b"}, {"name": "bge-embed"}, {"name": ""}]
    assert chat_slash._chat_capable_models(client.list_ollama_models.return_value) == ["Qwen:4b"]
    assert chat_slash._installed_models(client, ui) == ["Qwen:4b"]
    client.list_ollama_models.side_effect = RuntimeError("offline")
    assert chat_slash._installed_models(client, ui) == []
    assert chat_slash._resolve_model_name("qwen", ["Qwen:4b"]) == "Qwen:4b"
    assert chat_slash._resolve_model_name("missing", ["Qwen:4b"]) is None
    client.list_ollama_models.side_effect = None
    ui.prompt.side_effect = None
    ui.prompt.return_value = "qwen:4b"
    assert chat_slash._select_model(client, ui) == "Qwen:4b"
    assert chat_slash._select_model(client, ui, "missing") is None
    assert chat_slash._select_engine(ui, "general") == "ollama"
    assert chat_slash._select_engine(ui, "bad") is None
    assert chat_slash._resolve_collection("Docs", [{"id": "docs", "name": "Docs"}]) == "docs"
    assert chat_slash._resolve_collection("missing", []) is None

    client.list_collections.side_effect = RuntimeError("offline")
    assert chat_slash._select_collection(client, ui) is None
    client.list_collections.side_effect = None
    client.list_collections.return_value = []
    assert chat_slash._select_collection(client, ui) is None
    client.list_collections.return_value = [{"id": "docs", "name": "Docs"}]
    assert chat_slash._select_collection(client, ui, "missing") is None
    ui.prompt.return_value = "1"
    assert chat_slash._select_collection(client, ui) == "docs"

    state = ChatState()
    client.list_ollama_models.return_value = []
    chat_slash._configure_model("", client, ui, state)
    client.list_ollama_models.return_value = [{"name": "model"}]
    chat_slash._configure_model("model bad", client, ui, state)
    chat_slash._configure_model("model rag", client, ui, state)
    client.list_collections.return_value = [{"id": "docs", "name": "Docs"}]
    ui.prompt.return_value = "1"
    chat_slash._configure_model("model rag", client, ui, state)
    assert state.collections == ["docs"]

    ctx = chat_slash.SlashContext(
        messages=[{"role": "user"}], client=client, ui=ui, config=SimpleNamespace(), state=state
    )
    assert chat_slash._exit("", ctx) == 0
    chat_slash._help("", ctx)
    chat_slash._clear("", ctx)
    monkeypatch.setattr(chat_slash._system, "run_service_action", lambda *_args, **_kwargs: 0)
    chat_slash._status("", ctx)
    monkeypatch.setattr(index_command, "run", lambda *_args, **_kwargs: 0)
    chat_slash._index("folder", ctx)
    chat_slash._model("", ctx)
    chat_slash._rag("docs", ctx)
    chat_slash._chat("", ctx)
    chat_slash._auto("", ctx)
    chat_slash._agent("task", ctx)
    chat_slash._web("query", ctx)
    chat_slash._research("query", ctx)
    chat_slash._workspace(str(tmp_path), ctx)
    chat_slash._yolo("", ctx)
    chat_slash._yolo("", ctx)

    save_config = SimpleNamespace(thinking_enabled=True, save=lambda: (_ for _ in ()).throw(OSError("read-only")))
    save_ctx = chat_slash.SlashContext(messages=[], client=client, ui=ui, config=save_config, state=ChatState())
    chat_slash._thinking("toggle", save_ctx)
    chat_slash._thinking("invalid", save_ctx)
    client.list_memories.return_value = []
    chat_slash._memory("", ctx)
    client.list_memories.side_effect = RuntimeError("offline")
    chat_slash._memory("", ctx)
    client.list_collections.side_effect = None
    client.list_collections.return_value = []
    chat_slash._collections("", ctx)
    client.list_collections.side_effect = RuntimeError("offline")
    chat_slash._collections("", ctx)
    client.watch_status.return_value = {"running": False, "watching": []}
    chat_slash._watch("", ctx)
    client.watch_status.side_effect = RuntimeError("offline")
    chat_slash._watch("", ctx)

    with pytest.raises(ValueError, match="Duplicate"):
        chat_slash._build_registry(
            (
                chat_slash.SlashCommand(("/same",), "a", "x", lambda *_args: None),
                chat_slash.SlashCommand(("/same",), "b", "x", lambda *_args: None),
            )
        )
    assert chat_slash.handle_slash("   ", [], client, ui, SimpleNamespace(), state) == (False, None)


def test_chat_attachment_and_stream_error_edges(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    with pytest.raises(chat_command.LocalAttachmentError, match="empty"):
        chat_command.prepare_local_file("")
    monkeypatch.setattr(
        chat_command.Path, "resolve", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("resolve"))
    )
    with pytest.raises(chat_command.LocalAttachmentError, match="cannot resolve"):
        chat_command.prepare_local_file("file.txt")
    monkeypatch.undo()

    with pytest.raises(chat_command.LocalAttachmentError, match="cannot read"):
        chat_command._read_local_bytes(tmp_path / "missing", 10)
    empty = tmp_path / "empty.txt"
    empty.write_bytes(b"")
    with pytest.raises(chat_command.LocalAttachmentError, match="empty"):
        chat_command.prepare_local_file(empty)
    stat_error = tmp_path / "stat.txt"
    stat_error.write_text("x", encoding="utf-8")
    monkeypatch.setattr(chat_command, "_resolve_local_file", lambda _path: stat_error)
    monkeypatch.setattr(
        Path,
        "stat",
        lambda path, *args, **kwargs: (
            (_ for _ in ()).throw(OSError("stat")) if path == stat_error else Path.stat(path, *args, **kwargs)
        ),
    )
    with pytest.raises(chat_command.LocalAttachmentError, match="inspect"):
        chat_command.prepare_local_file(stat_error)
    monkeypatch.undo()

    bad_doc = tmp_path / "bad.pdf"
    bad_doc.write_bytes(b"pdf")
    monkeypatch.setattr(chat_command, "_resolve_local_file", lambda _path: bad_doc)
    monkeypatch.setattr(chat_command, "LOCAL_DOCUMENT_MAX_BYTES", 1)
    with pytest.raises(chat_command.LocalAttachmentError, match="document is too large"):
        chat_command.prepare_local_file(bad_doc)
    monkeypatch.setattr(chat_command, "LOCAL_DOCUMENT_MAX_BYTES", 128 * 1024 * 1024)
    monkeypatch.setattr(
        extract_module, "extract_document_text", lambda _path: (_ for _ in ()).throw(ImportError("parser"))
    )
    with pytest.raises(chat_command.LocalAttachmentError, match="parser is not installed"):
        chat_command.prepare_local_file(bad_doc)
    monkeypatch.setattr(
        extract_module, "extract_document_text", lambda _path: (_ for _ in ()).throw(RuntimeError("bad"))
    )
    with pytest.raises(chat_command.LocalAttachmentError, match="cannot extract"):
        chat_command.prepare_local_file(bad_doc)
    monkeypatch.undo()

    binary = tmp_path / "binary.txt"
    binary.write_bytes(b"\x00binary")
    with pytest.raises(chat_command.LocalAttachmentError, match="unsupported binary file type"):
        chat_command.prepare_local_file(binary)
    invalid = tmp_path / "invalid.txt"
    invalid.write_bytes(b"\xff")
    with pytest.raises(chat_command.LocalAttachmentError, match="not UTF-8"):
        chat_command.prepare_local_file(invalid)
    blank = tmp_path / "blank.txt"
    blank.write_text("  \n", encoding="utf-8")
    with pytest.raises(chat_command.LocalAttachmentError, match="no readable"):
        chat_command.prepare_local_file(blank)
    long_text = tmp_path / "long.txt"
    long_text.write_text("abcdef", encoding="utf-8")
    monkeypatch.setattr(chat_command, "LOCAL_TEXT_MAX_CHARS", 3)
    assert chat_command.prepare_local_file(long_text)["truncated"] is True

    response = MagicMock(status_code=200)
    response.read.return_value = b"body"
    response.iter_lines.return_value = iter(["", "event: ping", "data: [DONE]"])
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    ui = _ui()
    client = SimpleNamespace(_client=SimpleNamespace(stream=lambda *_args, **_kwargs: response))
    image_message = {"role": "user", "content": "image", "images": ["x"]}
    with pytest.raises(RuntimeError, match="image attachments"):
        chat_command._stream_from_rag(client, ui, [image_message])
    response.iter_lines.return_value = iter(['data: {"choices":[{"delta":{"content":"partial"}}]}'])
    with pytest.raises(RuntimeError, match="ended before completion"):
        chat_command._stream_from_rag(client, ui, [], ["docs"])
    response.status_code = 503
    response.read.return_value = b"unavailable"
    with pytest.raises(RuntimeError, match="HTTP 503"):
        chat_command._stream_from_rag(client, ui, [])

    response.status_code = 200
    response.iter_lines.return_value = iter(["", "not-json", '{"done": true}'])
    ollama_client = SimpleNamespace(stream_ollama=lambda *_args, **_kwargs: response)
    monkeypatch.setattr(chat_command._system, "env_value", lambda key: "bad" if key == "TRINAXAI_NUM_CTX" else "")
    assert (
        chat_command._stream_from_ollama(ollama_client, ui, [{"role": "user", "content": "q"}], thinking=False)
        == "(no answer)"
    )
    response.iter_lines.return_value = iter(['{"message":{"content":"x"}}'])
    with pytest.raises(RuntimeError, match="ended before completion"):
        chat_command._stream_from_ollama(ollama_client, ui, [])
    response.status_code = 500
    response.read.return_value = b"backend"
    with pytest.raises(RuntimeError, match="HTTP 500"):
        chat_command._stream_from_ollama(ollama_client, ui, [])


def test_chat_dispatch_research_and_repl_edges(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    ui = _ui()
    state = ChatState(workspace=str(tmp_path), thinking=False)
    assert chat_command._contains_images([{"role": "user", "images": []}]) is False
    assert chat_command._handle_cd("hello", state, ui) is False
    monkeypatch.setattr(chat_command.shlex, "split", lambda _value: (_ for _ in ()).throw(ValueError("quote")))
    assert chat_command._handle_cd("cd '", state, ui) is True
    monkeypatch.setattr(chat_command.shlex, "split", lambda _value: [])
    assert chat_command._handle_cd("cd", state, ui) is False
    monkeypatch.undo()
    assert chat_command._handle_cd("cd a b c", state, ui) is True
    assert chat_command._handle_cd("cd missing", state, ui) is True

    research_ui = _ui()
    research_client = MagicMock()
    research_client.research.return_value = {
        "answer": "answer",
        "passes": 2,
        "model": "model",
        "web_provider": "provider",
        "sub_questions": ["one"],
        "sources": [{"file": "a.md", "page": 2}, {"url": "https://example.test"}],
        "degraded": False,
        "failure_reason": "",
    }
    metadata: dict[str, Any] = {}
    assert (
        chat_command._run_web_or_research(
            research_client, research_ui, "latest news", [], mode="web", web_search=True, depth=1, result_meta=metadata
        )
        == "answer"
    )
    assert metadata["web_provider"] == "provider"
    research_client.research.side_effect = RuntimeError("offline")
    assert (
        chat_command._run_web_or_research(research_client, research_ui, "q", [], mode="web", web_search=True, depth=1)
        == ""
    )
    assert chat_command._render_research(research_ui, {"answer": ""}, web=False) == "(no answer)"

    session = MagicMock()
    route = SimpleNamespace(mode="agent", announce=False, source="manual", web_search=False, depth=1)
    monkeypatch.setattr(chat_command, "_run_agent_turn", lambda *_args: (_ for _ in ()).throw(KeyboardInterrupt()))
    chat_command._dispatch_turn("hello", route, [], object(), ui, None, state, session)
    monkeypatch.setattr(chat_command, "_run_agent_turn", lambda *_args: (_ for _ in ()).throw(RuntimeError("agent")))
    chat_command._dispatch_turn("hello", route, [], object(), ui, None, state, session)
    route.mode = "web"
    monkeypatch.setattr(chat_command, "_run_web_or_research", lambda *_args, **_kwargs: "")
    chat_command._dispatch_turn("hello", route, [], object(), ui, None, state, session)
    route.mode = "chat"
    messages: list[dict[str, Any]] = []
    monkeypatch.setattr(
        chat_command, "_stream_answer", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("chat"))
    )
    chat_command._dispatch_turn("hello", route, messages, object(), ui, None, state, session)
    assert messages == []

    chat_command._welcome(ui, "session", ChatState())
    ui.language = "es"
    chat_command._welcome(ui, "sesion", ChatState())

    class SessionStub:
        def __init__(self, _name):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def append(self, *_args):
            pass

    monkeypatch.setattr(chat_command, "Session", SessionStub)
    monkeypatch.setattr(chat_command, "_resolve_engine", lambda *_args: "rag")
    monkeypatch.setattr(chat_command, "_dispatch_turn", lambda *_args, **_kwargs: None)
    args = SimpleNamespace(
        session="chat-edge",
        collections="docs, code",
        engine=None,
        workspace=str(tmp_path),
        prompt="q",
        file=None,
        invocation_cwd=str(tmp_path),
        thinking=None,
    )
    assert chat_command.run(args, object(), ui, SimpleNamespace(model="m", thinking_enabled=True)) == 0
    file_path = tmp_path / "file.txt"
    file_path.write_text("x", encoding="utf-8")
    no_prompt = SimpleNamespace(
        session="chat-edge",
        collections=None,
        engine=None,
        workspace=None,
        prompt=None,
        file=str(file_path),
        invocation_cwd=str(tmp_path),
    )
    assert chat_command.run(no_prompt, object(), ui, SimpleNamespace(model="m", thinking_enabled=True)) == 2
    monkeypatch.setattr(
        chat_command,
        "prepare_local_file",
        lambda *_args: (_ for _ in ()).throw(chat_command.LocalAttachmentError("bad")),
    )
    bad_attachment = SimpleNamespace(
        session="chat-edge",
        collections=None,
        engine=None,
        workspace=None,
        prompt="q",
        file=str(file_path),
        invocation_cwd=str(tmp_path),
    )
    assert chat_command.run(bad_attachment, object(), ui, SimpleNamespace(model="m", thinking_enabled=True)) == 2
    monkeypatch.setattr(chat_command, "prepare_local_file", lambda *_args: {"message": {}, "name": "file.txt"})
    rag_attachment = SimpleNamespace(
        session="chat-edge",
        collections=["docs"],
        engine=None,
        workspace=None,
        prompt="q",
        file=str(file_path),
        invocation_cwd=str(tmp_path),
    )
    assert chat_command.run(rag_attachment, object(), ui, SimpleNamespace(model="m", thinking_enabled=True)) == 2
    monkeypatch.setattr(
        chat_command, "_dispatch_turn", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("dispatch"))
    )
    assert chat_command.run(args, object(), ui, SimpleNamespace(model="m", thinking_enabled=True)) == 1

    monkeypatch.setattr(chat_command, "_welcome", lambda *_args: None)
    ui.language = "en"
    ui.chat_prompt.side_effect = [EOFError()]
    assert (
        chat_command.run(
            SimpleNamespace(
                session="chat-edge",
                collections=None,
                engine=None,
                workspace=None,
                prompt=None,
                file=None,
                invocation_cwd=str(tmp_path),
            ),
            object(),
            ui,
            SimpleNamespace(model="m", thinking_enabled=True),
        )
        == 0
    )
    subdir = tmp_path / "subdir"
    subdir.mkdir(exist_ok=True)
    ui.chat_prompt.side_effect = ["", "cd subdir", "/exit"]
    assert (
        chat_command.run(
            SimpleNamespace(
                session="chat-edge",
                collections=None,
                engine=None,
                workspace=None,
                prompt=None,
                file=None,
                invocation_cwd=str(tmp_path),
            ),
            object(),
            ui,
            SimpleNamespace(model="m", thinking_enabled=True),
        )
        == 0
    )

    def slash_exit(_command, _messages, _client, _ui, _config, _state):
        return True, 0

    monkeypatch.setattr(chat_command, "_handle_slash", slash_exit)
    ui.chat_prompt.side_effect = ["/exit"]
    assert (
        chat_command.run(
            SimpleNamespace(
                session="chat-edge",
                collections=None,
                engine=None,
                workspace=None,
                prompt=None,
                file=None,
                invocation_cwd=str(tmp_path),
            ),
            object(),
            ui,
            SimpleNamespace(model="m", thinking_enabled=True),
        )
        == 0
    )

    def slash_pending(command, _messages, _client, _ui, _config, state):
        if command == "/custom":
            return True, 0
        state.pending_input = "task"
        return True, None

    monkeypatch.setattr(chat_command, "_handle_slash", slash_pending)
    monkeypatch.setattr(
        chat_command,
        "_resolve_turn_mode",
        lambda *_args, **_kwargs: SimpleNamespace(
            mode="chat", announce=False, source="manual", web_search=False, depth=1
        ),
    )
    monkeypatch.setattr(chat_command, "_dispatch_turn", lambda *_args, **_kwargs: None)
    ui.chat_prompt.side_effect = ["/chat", "/custom"]
    assert (
        chat_command.run(
            SimpleNamespace(
                session="chat-edge",
                collections=None,
                engine=None,
                workspace=None,
                prompt=None,
                file=None,
                invocation_cwd=str(tmp_path),
            ),
            object(),
            ui,
            SimpleNamespace(model="m", thinking_enabled=True),
        )
        == 0
    )

    monkeypatch.setattr(chat_command, "_handle_slash", lambda *_args, **_kwargs: (True, None))
    ui.chat_prompt.side_effect = ["/handled", "/exit"]
    assert (
        chat_command.run(
            SimpleNamespace(
                session="chat-edge",
                collections=None,
                engine=None,
                workspace=None,
                prompt=None,
                file=None,
                invocation_cwd=str(tmp_path),
            ),
            object(),
            ui,
            SimpleNamespace(model="m", thinking_enabled=True),
        )
        == 0
    )


def test_remaining_cli_error_branches(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    system_ui = _ui()
    (tmp_path / "service_manager.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(_system, "project_root", lambda: tmp_path)
    monkeypatch.setattr(
        _system,
        "run_process_group",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("exec")),
    )
    assert _system.run_service_action("status", system_ui) == 1
    monkeypatch.setattr(
        _system,
        "run_process_group",
        lambda *_args, **_kwargs: SimpleNamespace(stdout="", stderr="", returncode=7),
    )
    assert _system.run_service_action("status", system_ui) == 7
    assert _system.masked("") == ""
    assert _system.service_state() == {}

    collection_ui = _ui()
    collection_ui.prompt.return_value = ""
    assert (
        collections.run(SimpleNamespace(collections_command="use", collection_id=None), object(), collection_ui, None)
        == 1
    )

    memory_client = MagicMock()
    memory_client.list_memories.return_value = []
    assert (
        memory.run(
            SimpleNamespace(memory_command="forget", memory_id="missing", memory_id_positional=None),
            memory_client,
            _ui(),
            None,
        )
        == 1
    )

    state = ChatState()
    slash_ui = _ui()
    monkeypatch.setattr(chat_slash, "_select_model", lambda *_args: "model")
    monkeypatch.setattr(chat_slash, "_select_engine", lambda *_args: "rag")
    monkeypatch.setattr(chat_slash, "_select_collection", lambda *_args: None)
    chat_slash._configure_model("model rag", object(), slash_ui, state)

    empty = tmp_path / "empty-stream.txt"
    empty.write_bytes(b"")
    with pytest.raises(chat_command.LocalAttachmentError, match="file is empty"):
        chat_command._read_local_bytes(empty, 10)

    stream_ui = _ui()
    stream_client = MagicMock()
    stream_client.memory_context.side_effect = RuntimeError("memory unavailable")
    monkeypatch.setattr(chat_command, "_stream_from_ollama", lambda *_args, **_kwargs: "answer")
    assert (
        chat_command._stream_answer(
            stream_client,
            stream_ui,
            [{"role": "user", "content": "question"}],
            "ollama",
            [],
            None,
            thinking=True,
        )
        == "answer"
    )
    monkeypatch.setattr(chat_command, "_stream_from_rag", lambda *_args, **_kwargs: "rag answer")
    assert (
        chat_command._stream_answer(stream_client, stream_ui, [], "rag", ["docs"], None, thinking=False) == "rag answer"
    )
    assert chat_command._stream_answer(stream_client, stream_ui, [], "ollama", [], None, thinking=False) == "answer"
    monkeypatch.setattr(network_command.network, "trust_certificate", lambda _root: (tmp_path / "cert.pem", "custom"))
    network_command._show_trust_certificate(tmp_path, _ui())
