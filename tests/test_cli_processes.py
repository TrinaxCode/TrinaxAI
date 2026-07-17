from __future__ import annotations

import signal
import subprocess
from types import SimpleNamespace
from typing import Any

import pytest

from trinaxai_cli import processes


def test_spawn_process_group_never_uses_shell(monkeypatch) -> None:
    calls: list[tuple[list[str], dict[str, Any]]] = []

    def fake_popen(command: list[str], **kwargs: Any) -> SimpleNamespace:
        calls.append((command, kwargs))
        return SimpleNamespace(pid=42)

    monkeypatch.setattr(processes.sys, "platform", "linux")
    monkeypatch.setattr(processes.subprocess, "Popen", fake_popen)

    process = processes.spawn_process_group(["python", "worker.py"])

    assert process.pid == 42
    assert calls == [
        (["python", "worker.py"], {"start_new_session": True, "shell": False})
    ]


def test_spawn_process_group_rejects_shell() -> None:
    with pytest.raises(ValueError, match="must not use a shell"):
        processes.spawn_process_group(["echo", "unsafe"], shell=True)


def test_wait_timeout_terminates_complete_posix_group(monkeypatch) -> None:
    class FakeProcess:
        pid = 314

        def __init__(self) -> None:
            self.wait_calls = 0

        def poll(self) -> None:
            return None

        def wait(self, timeout: float | None = None) -> int:
            self.wait_calls += 1
            if self.wait_calls == 1:
                raise subprocess.TimeoutExpired("index", timeout)
            return -signal.SIGTERM

        def terminate(self) -> None:
            raise AssertionError("group signal should be used")

        def kill(self) -> None:
            raise AssertionError("graceful termination should succeed")

    signals: list[tuple[int, signal.Signals]] = []
    monkeypatch.setattr(processes.sys, "platform", "linux")
    monkeypatch.setattr(processes.os, "getpgid", lambda pid: pid)
    monkeypatch.setattr(processes.os, "killpg", lambda pid, sig: signals.append((pid, sig)))
    process = FakeProcess()

    with pytest.raises(subprocess.TimeoutExpired):
        processes.wait_process_group(process, timeout=0.01)  # type: ignore[arg-type]

    assert signals == [(314, signal.SIGTERM)]
    assert process.wait_calls == 2
