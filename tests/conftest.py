"""Shared pytest fixtures."""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Iterator

import pytest


def _descendant_pids() -> set[int]:
    """Every process started, directly or not, by this test run."""
    listing = subprocess.run(["ps", "-axo", "pid=,ppid="], capture_output=True, text=True, check=False).stdout
    parents: dict[int, int] = {}
    for line in listing.splitlines():
        fields = line.split()
        if len(fields) == 2 and all(field.isdigit() for field in fields):
            parents[int(fields[0])] = int(fields[1])
    found: set[int] = set()
    frontier = {os.getpid()}
    while frontier:
        frontier = {pid for pid, parent in parents.items() if parent in frontier} - found
        found |= frontier
    return found


@pytest.fixture(autouse=True)
def _tests_never_signal_processes_they_did_not_start(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """A test that reaches the real process table must not stop the developer's own services.

    ``trinaxai stop`` finds TrinaxAI's processes by program and install folder, so a test that
    calls it for real on a machine where TrinaxAI is running from the same checkout would shut
    that installation down. Every real signal (``os.kill``/``os.killpg``, however it is reached)
    must hit a process the test run started. Tests that need to signal something start it
    themselves, or replace ``os.kill`` with a fake, which overrides this guard.
    """
    if os.name != "posix":
        yield
        return

    real_kill = os.kill
    real_killpg = os.killpg

    def allowed(pid: int) -> bool:
        return pid == os.getpid() or pid in _descendant_pids()

    def refuse(pid: int) -> AssertionError:
        return AssertionError(
            f"a test tried to signal pid {pid}, which it did not start; "
            "replace service_manager._process_table with a fake so discovery stays inside the test"
        )

    def guarded_kill(pid: int, sig: int) -> None:
        # Signal 0 only asks whether the process exists.
        if sig != 0 and not allowed(pid):
            raise refuse(pid)
        real_kill(pid, sig)

    def guarded_killpg(pgid: int, sig: int) -> None:
        if sig != 0 and pgid != os.getpgrp() and not any(os.getpgid(p) == pgid for p in _descendant_pids()):
            raise refuse(pgid)
        real_killpg(pgid, sig)

    monkeypatch.setattr(os, "kill", guarded_kill)
    monkeypatch.setattr(os, "killpg", guarded_killpg)
    yield


@pytest.fixture(autouse=True)
def _tests_never_launch_the_real_service_manager(monkeypatch: pytest.MonkeyPatch) -> None:
    """The system endpoints spawn a detached ``service_manager.py stop-ai|stop-all`` process.

    Reaching that from a test stops the Ollama and API of whoever runs the suite, minutes
    later and from another process. Tests of those endpoints patch the spawner themselves.
    """
    system_service = sys.modules.get("app.services.system_service")
    if system_service is None:
        return

    real_spawn = system_service._spawn_service_manager
    real_popen = subprocess.Popen

    def guarded(script: str, action: str) -> None:
        # Tests of the spawner itself fake Popen; only a spawn that would really run is a leak.
        if subprocess.Popen is real_popen:
            raise AssertionError(
                f"a test tried to launch the real service manager ({action}); "
                "patch system_service._spawn_service_manager"
            )
        real_spawn(script, action)

    monkeypatch.setattr(system_service, "_spawn_service_manager", guarded)
