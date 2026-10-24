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
    that installation down. Tests that need to signal something start it themselves (or replace
    ``_signal_process`` and ``_process_table`` with fakes, which overrides this guard).
    """
    if os.name != "posix":
        yield
        return
    from trinaxai.supervisor import service_manager

    real = service_manager._signal_process
    real_kill = os.kill

    def guarded(pid: int, sig: int) -> None:
        # A test that replaced os.kill with a fake cannot hurt anything.
        if os.kill is real_kill and pid not in _descendant_pids():
            raise AssertionError(
                f"a test tried to signal pid {pid}, which it did not start; "
                "replace service_manager._process_table with a fake so discovery stays inside the test"
            )
        real(pid, sig)

    monkeypatch.setattr(service_manager, "_signal_process", guarded)
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
