"""`trinaxai stop` and `status` only ever see this installation's own processes."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from trinaxai.supervisor import service_manager as sm

posix_only = pytest.mark.skipif(sys.platform == "win32", reason="POSIX process model")


def _proc(pid: int, *argv: str) -> sm._Proc:
    return sm._Proc(pid, tuple(argv))


# ------------------------------------------------------------ pure helpers


@pytest.mark.parametrize(
    ("argv", "name"),
    [
        (("/usr/bin/python3.12", "-m", "x"), "python"),
        (("python3",), "python"),
        (("node",), "node"),
        (("/opt/ollama/bin/ollama", "serve"), "ollama"),
        (("npm run dev",), "npm run dev"),  # a whole command in argv[0] is not the program "npm"
        ((), ""),
    ],
)
def test_program_name_ignores_directory_and_version(argv, name) -> None:
    assert sm._program_name(argv) == name


def test_install_membership_uses_path_boundaries_and_working_directory(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "trinaxai"
    root.mkdir()
    monkeypatch.setattr(sm, "PROJECT_ROOT_RESOLVED", root)
    cwds = {1: str(root / "chat-pwa"), 2: str(tmp_path / "trinaxai-other"), 3: None, 4: str(root)}
    monkeypatch.setattr(sm, "_process_cwd", lambda pid: cwds.get(pid))

    assert sm._in_install(_proc(1, "node", "server.mjs"))  # runs from inside the install
    assert sm._in_install(_proc(4, "node", "server.mjs"))  # runs from the install root itself
    assert not sm._in_install(_proc(2, "node", "server.mjs"))  # a sibling folder with the same prefix
    assert not sm._in_install(_proc(3, "node", "server.mjs"))  # working directory unknown
    assert sm._in_install(_proc(3, str(root / ".venv" / "bin" / "python"), "rag_api.py"))  # path on the command line
    assert not sm._in_install(_proc(3, "python", str(tmp_path / "trinaxai-other" / "rag_api.py")))
    assert sm._in_install(_proc(3, "tool", str(root)))


def test_service_processes_pick_only_the_right_program_in_the_right_place(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "trinaxai"
    root.mkdir()
    monkeypatch.setattr(sm, "PROJECT_ROOT_RESOLVED", root)
    table = [
        _proc(10, "node", "server.mjs"),  # ours
        _proc(11, "node", "server.mjs"),  # another project's
        _proc(12, "vim", "server.mjs"),  # an editor with the same words
        _proc(13, "npm", "run", "dev"),  # another project's dev server
        _proc(14, "node", "server.mjs"),  # this very process (must be skipped)
    ]
    cwds = {
        10: str(root / "chat-pwa"),
        11: str(tmp_path / "other"),
        12: str(root),
        13: str(tmp_path / "other"),
        14: str(root),
    }
    monkeypatch.setattr(sm, "_process_table", lambda: table)
    monkeypatch.setattr(sm, "_process_cwd", lambda pid: cwds.get(pid))
    monkeypatch.setattr(sm, "_ancestors", lambda: {14})

    assert sm._service_processes("trinaxai-frontend") == [(10, "node server.mjs")]


def test_only_a_running_ollama_server_counts_not_its_clients(monkeypatch) -> None:
    table = [
        _proc(20, "/usr/local/bin/ollama", "run", "llama3"),
        _proc(21, "vim", "ollama-notes.md"),
        _proc(22, "/usr/local/bin/ollama", "serve"),
    ]
    monkeypatch.setattr(sm, "_process_table", lambda: table)
    monkeypatch.setattr(sm, "_ancestors", lambda: set())
    assert sm._service_processes("ollama") == [(22, "ollama serve")]
    assert sm._pgrep_status("ollama").pid == 22


def test_ancestors_always_include_this_process_and_its_parent() -> None:
    ancestors = sm._ancestors()
    assert os.getpid() in ancestors and os.getppid() in ancestors


def test_signalling_a_vanished_or_protected_process_is_harmless(monkeypatch) -> None:
    def vanished(_pid, _sig):
        raise ProcessLookupError

    def protected(_pid, _sig):
        raise PermissionError

    monkeypatch.setattr(sm.os, "kill", vanished)
    sm._signal_process(1, 15)
    assert sm._process_alive(1) is False
    monkeypatch.setattr(sm.os, "kill", protected)
    sm._signal_process(1, 15)
    assert sm._process_alive(1) is True
    monkeypatch.setattr(sm.os, "kill", lambda _pid, _sig: None)
    assert sm._process_alive(1) is True


def test_ancestor_walk_stops_on_unreadable_or_looping_parent_entries(monkeypatch) -> None:
    monkeypatch.setattr(sm.os, "getpid", lambda: 100)
    monkeypatch.setattr(sm.os, "getppid", lambda: 90)
    stats = {"90": "90 (sh) S 80 ", "80": "80 (bash) S 90 "}  # 80 points back at 90: a loop
    monkeypatch.setattr(sm.Path, "read_text", lambda self, **_k: stats[self.parent.name])
    assert sm._ancestors() == {100, 90, 80}
    monkeypatch.setattr(sm.Path, "read_text", lambda self, **_k: (_ for _ in ()).throw(OSError("gone")))
    assert sm._ancestors() == {100, 90}


# ------------------------------------------------- process listing branches


def test_process_table_on_linux_reads_proc_entries(monkeypatch, tmp_path: Path) -> None:
    table = sm._process_table()
    mine = next(proc for proc in table if proc.pid == os.getpid())
    assert mine.argv[0]

    monkeypatch.setattr(sm.os.path, "isdir", lambda path: path == "/proc/self")
    monkeypatch.setattr(sm.os, "listdir", lambda _path: ["12", "self", "13"])
    files = {"12": b"python\x00rag_api.py\x00", "13": b""}
    monkeypatch.setattr(
        sm.Path,
        "read_bytes",
        lambda self: files[self.parent.name] if self.parent.name in files else (_ for _ in ()).throw(OSError()),
    )
    assert sm._process_table() == [sm._Proc(12, ("python", "rag_api.py"))]


def test_process_table_and_cwd_fall_back_to_ps_and_lsof_off_linux(monkeypatch) -> None:
    monkeypatch.setattr(sm.os.path, "isdir", lambda _path: False)
    listing = "  1 /sbin/launchd\n  42 /usr/bin/python3 'a b' rag_api.py\n 77 broken \"quote\nnot-a-pid x\n"
    seen = []

    def fake_run(command, **_kwargs):
        seen.append(command[0])
        if command[0] == "ps":
            return SimpleNamespace(stdout=listing)
        return SimpleNamespace(stdout="p42\nfcwd\nn/Users/me/trinaxai\n")

    monkeypatch.setattr(sm.subprocess, "run", fake_run)
    table = sm._process_table()
    assert [proc.pid for proc in table] == [1, 42, 77]
    assert table[1].argv == ("/usr/bin/python3", "a b", "rag_api.py")
    assert table[2].argv == ("broken", '"quote')  # unbalanced quotes still produce an argv
    assert sm._process_cwd(42) == "/Users/me/trinaxai"
    assert seen == ["ps", "lsof"]

    monkeypatch.setattr(sm.subprocess, "run", lambda *_a, **_k: SimpleNamespace(stdout="p42\n"))
    assert sm._process_cwd(42) is None

    def missing(*_a, **_k):
        raise FileNotFoundError("lsof")

    monkeypatch.setattr(sm.subprocess, "run", missing)
    assert sm._process_cwd(42) is None


# ------------------------------------------------------ real child processes


def _spawn(marker: str, cwd: Path) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)", marker],
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _wait_until(predicate, timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


@posix_only
def test_stop_ends_the_installations_own_process_and_spares_look_alikes(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "install"
    elsewhere = tmp_path / "someone-elses-project"
    root.mkdir()
    elsewhere.mkdir()
    marker = "trinaxai-test-marker-7f3a"
    monkeypatch.setattr(sm, "PROJECT_ROOT_RESOLVED", root.resolve())
    monkeypatch.setattr(sm, "PROCESS_PATTERNS", {"decoy-service": [marker]})
    monkeypatch.setattr(sm, "_SERVICE_PROGRAMS", {})

    ours = _spawn(marker, root)
    other = _spawn(marker, elsewhere)
    try:
        assert _wait_until(lambda: any(pid == ours.pid for pid, _p in sm._service_processes("decoy-service")))
        found = {pid for pid, _pattern in sm._service_processes("decoy-service")}
        assert found == {ours.pid}  # the look-alike is invisible to status ...
        assert sm._pgrep_status("decoy-service").pid == ours.pid

        assert sm._stop_by_name("decoy-service").running is False
        assert ours.wait(timeout=10) is not None  # ... and untouched by stop, while ours is gone
        assert other.poll() is None
        assert sm._pgrep_status("decoy-service").running is False
    finally:
        for process in (ours, other):
            if process.poll() is None:
                process.kill()
            process.wait(timeout=10)
