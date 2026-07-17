"""Cross-platform child-process groups with deterministic cleanup.

``subprocess.run(timeout=...)`` only terminates the direct child.  Lifecycle
scripts and indexers may in turn spawn workers, so CLI commands launch a fresh
process group and terminate the whole group on timeout or interruption.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from collections.abc import Sequence
from typing import Any


def process_group_options() -> dict[str, Any]:
    """Return safe ``Popen`` options for a new platform process group."""
    if sys.platform == "win32":
        return {"creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)}
    return {"start_new_session": True}


def spawn_process_group(command: Sequence[str], **kwargs: Any) -> subprocess.Popen:
    """Start *command* without a shell in its own process group."""
    if kwargs.get("shell"):
        raise ValueError("process-group commands must not use a shell")
    options = process_group_options()
    options.update(kwargs)
    options["shell"] = False
    return subprocess.Popen(list(command), **options)


def terminate_process_group(process: subprocess.Popen, *, grace_seconds: float = 3.0) -> None:
    """Terminate a child group, escalating to a force kill after a grace period."""
    if process.poll() is not None:
        return

    if sys.platform == "win32":
        try:
            taskkill = os.path.join(
                os.environ.get("SystemRoot", r"C:\Windows"),
                "System32",
                "taskkill.exe",
            )
            subprocess.run(  # noqa: S603 - fixed Windows system binary and argv
                [taskkill, "/PID", str(process.pid), "/T", "/F"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=grace_seconds,
            )
        except (OSError, ValueError, subprocess.TimeoutExpired):
            process.kill()
    else:
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        except (OSError, ProcessLookupError):
            process.terminate()

    try:
        process.wait(timeout=grace_seconds)
        return
    except subprocess.TimeoutExpired:
        pass

    if sys.platform == "win32":
        process.kill()
    else:
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except (OSError, ProcessLookupError):
            process.kill()
    try:
        process.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        # The OS owns final cleanup at this point; do not hide the original
        # timeout/interrupt behind another exception.
        pass


def wait_process_group(process: subprocess.Popen, *, timeout: float | None = None) -> int:
    """Wait for a child and clean up its complete group on timeout/interrupt."""
    try:
        return process.wait(timeout=timeout)
    except (KeyboardInterrupt, subprocess.TimeoutExpired):
        terminate_process_group(process)
        raise


def run_process_group(
    command: Sequence[str],
    *,
    cwd: str | os.PathLike[str] | None = None,
    env: dict[str, str] | None = None,
    capture_output: bool = False,
    text: bool = False,
    timeout: float | None = None,
    check: bool = False,
) -> subprocess.CompletedProcess:
    """``subprocess.run`` equivalent that cleans descendant processes too."""
    kwargs: dict[str, Any] = {"cwd": cwd, "env": env, "text": text}
    if capture_output:
        kwargs.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    process = spawn_process_group(command, **kwargs)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except (KeyboardInterrupt, subprocess.TimeoutExpired) as exc:
        terminate_process_group(process)
        stdout, stderr = process.communicate()
        if isinstance(exc, subprocess.TimeoutExpired):
            raise subprocess.TimeoutExpired(
                list(command), timeout, output=stdout, stderr=stderr
            ) from exc
        raise

    completed = subprocess.CompletedProcess(list(command), process.returncode, stdout, stderr)
    if check and completed.returncode:
        raise subprocess.CalledProcessError(
            completed.returncode,
            completed.args,
            output=completed.stdout,
            stderr=completed.stderr,
        )
    return completed
