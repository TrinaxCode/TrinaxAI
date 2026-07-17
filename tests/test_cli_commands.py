from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from trinaxai_cli.commands import collections, index
from trinaxai_cli.config import CLIConfig


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


def test_cli_doctor_strict_json_is_machine_readable_and_fails() -> None:
    result = run_cli("--api-url", "http://127.0.0.1:9", "doctor", "--strict", "--json")
    payload = __import__("json").loads(result.stdout.strip())
    assert result.returncode == 1
    assert payload["healthy"] is False
    assert any(check["check"] == "RAG API" and not check["ok"] for check in payload["checks"])


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


def test_cli_mcp_placeholder_is_hidden_and_nonzero() -> None:
    result = run_cli("mcp")
    output = result.stdout + result.stderr
    assert result.returncode == 2
    assert "planned" in output.lower()
    assert "import" not in output.lower()


def test_collections_use_validates_and_persists_default(tmp_path: Path) -> None:
    client = MagicMock()
    client.list_collections.return_value = [{"id": "docs"}]
    ui = MagicMock()
    config = CLIConfig()
    config.save = MagicMock(return_value=tmp_path / "config.toml")

    result = collections.run(SimpleNamespace(collections_command="use", collection_id="docs"), client, ui, config)

    assert result == 0
    assert config.active_collection == "docs"
    assert config.collections == ["docs"]
    config.save.assert_called_once_with()


def test_collections_use_rejects_unknown_collection() -> None:
    client = MagicMock()
    client.list_collections.return_value = [{"id": "default"}]
    ui = MagicMock()
    config = CLIConfig()

    result = collections.run(SimpleNamespace(collections_command="use", collection_id="missing"), client, ui, config)

    assert result == 1
    ui.error.assert_called_once()


def test_index_success_reloads_live_rag_index(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (tmp_path / "index.py").write_text("# test\n")
    client = MagicMock()
    ui = MagicMock()
    args = SimpleNamespace(path=str(source), collection="docs", append=False)
    process = MagicMock()

    with (
        patch.object(index, "find_install_root", return_value=tmp_path),
        patch.object(index, "spawn_process_group", return_value=process),
        patch.object(index, "wait_process_group", return_value=0),
    ):
        result = index.run(args, client, ui, CLIConfig())

    assert result == 0
    client.reload_index.assert_called_once_with()
