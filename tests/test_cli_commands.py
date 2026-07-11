from __future__ import annotations

import os
import subprocess
import sys


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "NO_COLOR": "1"}
    return subprocess.run(
        [sys.executable, "-c", "from trinaxai_cli.app import main; raise SystemExit(main())", *args],
        text=True,
        capture_output=True,
        env=env,
        timeout=20,
        check=False,
    )


def test_cli_help() -> None:
    result = run_cli("--help")
    assert result.returncode == 0
    assert "TrinaxAI CLI" in result.stdout


def test_cli_version() -> None:
    result = run_cli("version")
    assert result.returncode == 0
    assert "TrinaxAI CLI" in result.stdout


def test_cli_doctor_without_backend_has_human_error() -> None:
    result = run_cli("--api-url", "http://127.0.0.1:9", "doctor")
    output = result.stdout + result.stderr
    assert result.returncode == 0
    assert "RAG API" in output
    assert "trinaxai" in output
    assert "start" in output
    assert "Traceback" not in output


def test_cli_ask_help() -> None:
    result = run_cli("ask", "--help")
    assert result.returncode == 0
    assert "usage: trinaxai ask" in result.stdout
    assert "prompt" in result.stdout


def test_cli_index_help() -> None:
    result = run_cli("index", "--help")
    assert result.returncode == 0
    assert "usage: trinaxai index" in result.stdout
    assert "--collection" in result.stdout


def test_cli_lifecycle_help() -> None:
    update = run_cli("update", "--help")
    uninstall = run_cli("uninstall", "--help")
    assert update.returncode == 0
    assert "--no-backup" in update.stdout
    assert uninstall.returncode == 0
    assert "--purge" in uninstall.stdout
