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
    assert calls == [(["python", "worker.py"], {"start_new_session": True, "shell": False})]


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
    monkeypatch.setattr(processes.os, "getpgid", lambda pid: pid, raising=False)
    monkeypatch.setattr(
        processes.os,
        "killpg",
        lambda pid, sig: signals.append((pid, sig)),
        raising=False,
    )
    process = FakeProcess()

    with pytest.raises(subprocess.TimeoutExpired):
        processes.wait_process_group(process, timeout=0.01)  # type: ignore[arg-type]

    assert signals == [(314, signal.SIGTERM)]
    assert process.wait_calls == 2


def test_process_group_options_use_windows_creation_flag(monkeypatch) -> None:
    monkeypatch.setattr(processes.sys, "platform", "win32")
    monkeypatch.setattr(processes.subprocess, "CREATE_NEW_PROCESS_GROUP", 512, raising=False)

    assert processes.process_group_options() == {"creationflags": 512}


def test_terminate_ignores_an_already_exited_process(monkeypatch) -> None:
    process = SimpleNamespace(poll=lambda: 0)
    monkeypatch.setattr(
        processes.os,
        "killpg",
        lambda *_args: (_ for _ in ()).throw(AssertionError("must not signal")),
        raising=False,
    )

    processes.terminate_process_group(process)  # type: ignore[arg-type]


def test_posix_termination_falls_back_and_escalates(monkeypatch) -> None:
    class FakeProcess:
        pid = 42

        def __init__(self) -> None:
            self.wait_calls = 0
            self.terminated = 0
            self.killed = 0

        def poll(self):
            return None

        def terminate(self):
            self.terminated += 1

        def kill(self):
            self.killed += 1

        def wait(self, timeout=None):
            self.wait_calls += 1
            raise subprocess.TimeoutExpired("worker", timeout)

    process = FakeProcess()
    monkeypatch.setattr(processes.sys, "platform", "linux")
    monkeypatch.setattr(processes.os, "getpgid", lambda _pid: 42, raising=False)
    monkeypatch.setattr(
        processes.os,
        "killpg",
        lambda *_args: (_ for _ in ()).throw(ProcessLookupError()),
        raising=False,
    )

    processes.terminate_process_group(process, grace_seconds=0.01)  # type: ignore[arg-type]

    assert process.terminated == 1
    assert process.killed == 1
    assert process.wait_calls == 2


def test_windows_termination_falls_back_when_taskkill_fails(monkeypatch) -> None:
    class FakeProcess:
        pid = 7

        def __init__(self) -> None:
            self.killed = 0

        def poll(self):
            return None

        def kill(self):
            self.killed += 1

        def wait(self, timeout=None):
            return 0

    process = FakeProcess()
    monkeypatch.setattr(processes.sys, "platform", "win32")
    monkeypatch.setattr(
        processes.subprocess,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("taskkill unavailable")),
    )

    processes.terminate_process_group(process)  # type: ignore[arg-type]

    assert process.killed == 1


def test_wait_keyboard_interrupt_terminates_then_reraises(monkeypatch) -> None:
    process = MagicProcess(wait_effect=KeyboardInterrupt())
    terminated: list[object] = []
    monkeypatch.setattr(processes, "terminate_process_group", terminated.append)

    with pytest.raises(KeyboardInterrupt):
        processes.wait_process_group(process)  # type: ignore[arg-type]

    assert terminated == [process]


class MagicProcess:
    def __init__(
        self,
        *,
        communicate_result: tuple[str | None, str | None] = (None, None),
        communicate_effect: Exception | None = None,
        wait_effect: BaseException | None = None,
        returncode: int = 0,
    ) -> None:
        self.communicate_result = communicate_result
        self.communicate_effect = communicate_effect
        self.wait_effect = wait_effect
        self.returncode = returncode
        self.communicate_calls = 0

    def wait(self, timeout=None):
        if self.wait_effect:
            raise self.wait_effect
        return self.returncode

    def communicate(self, timeout=None):
        self.communicate_calls += 1
        if self.communicate_effect and self.communicate_calls == 1:
            raise self.communicate_effect
        return self.communicate_result


def test_run_process_group_returns_output_and_honors_check(monkeypatch) -> None:
    process = MagicProcess(communicate_result=("out", "err"), returncode=3)
    spawned: list[tuple[list[str], dict[str, Any]]] = []

    def spawn(command, **kwargs):
        spawned.append((list(command), kwargs))
        return process

    monkeypatch.setattr(processes, "spawn_process_group", spawn)

    completed = processes.run_process_group(["worker"], capture_output=True, text=True)

    assert completed.returncode == 3
    assert completed.stdout == "out"
    assert spawned == [
        (
            ["worker"],
            {
                "cwd": None,
                "env": None,
                "text": True,
                "stdout": subprocess.PIPE,
                "stderr": subprocess.PIPE,
            },
        )
    ]

    with pytest.raises(subprocess.CalledProcessError) as exc:
        processes.run_process_group(["worker"], check=True)
    assert exc.value.returncode == 3


def test_run_process_group_timeout_cleans_up_and_preserves_output(monkeypatch) -> None:
    timeout = subprocess.TimeoutExpired("worker", 1)
    process = MagicProcess(
        communicate_result=("partial out", "partial err"),
        communicate_effect=timeout,
    )
    terminated: list[object] = []
    monkeypatch.setattr(processes, "spawn_process_group", lambda *_args, **_kwargs: process)
    monkeypatch.setattr(processes, "terminate_process_group", terminated.append)

    with pytest.raises(subprocess.TimeoutExpired) as exc:
        processes.run_process_group(["worker"], timeout=1)

    assert terminated == [process]
    assert exc.value.output == "partial out"
    assert exc.value.stderr == "partial err"
