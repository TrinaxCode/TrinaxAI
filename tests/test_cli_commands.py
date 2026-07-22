from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import certifi

from trinaxai_cli.client import TrinaxAPIClient, TrinaxAPIError
from trinaxai_cli.commands import agent, ask, collections, index, memory
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


def test_cli_requires_verified_tls_and_accepts_a_ca_file(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    config.write_text("[api]\nverify_tls = false\n", encoding="utf-8")
    ca_file = certifi.where()

    rejected = run_cli("--config", str(config), "config")
    trusted = run_cli("--ca-file", ca_file, "config")
    with patch.dict(os.environ, {"TRINAXAI_CA_FILE": ca_file}):
        trusted_from_env = run_cli("--config", str(config), "config")

    assert rejected.returncode == 2
    assert "--ca-file or TRINAXAI_CA_FILE" in rejected.stderr
    assert "Traceback" not in rejected.stderr
    assert trusted.returncode == 0
    assert trusted_from_env.returncode == 0


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


def test_agent_auto_router_uses_fast_tool_model_for_simple_code_tasks() -> None:
    config = SimpleNamespace(
        MODEL_CODE="qwen2.5-coder:3b",
        MODEL_DEEP="qwen3.5:4b",
        MODEL_GENERAL="granite4:3b",
        route_model=lambda _text: "qwen2.5-coder:3b",
    )
    assert agent._resolve_model(SimpleNamespace(model=None), config, "crea un archivo README.md") == "granite4:3b"


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


def test_collections_delete_resolves_unique_name() -> None:
    client = MagicMock()
    client.list_collections.return_value = [{"id": "docs-123", "name": "Docs"}]
    client.delete_collection.return_value = 2
    ui = MagicMock()
    ui.confirm.return_value = True

    result = collections.run(
        SimpleNamespace(collections_command="delete", collection_id=None, name="Docs"), client, ui, CLIConfig()
    )

    assert result == 0
    client.delete_collection.assert_called_once_with("docs-123")


def test_memory_forget_rejects_disagreeing_ids() -> None:
    ui = MagicMock()
    result = memory.run(
        SimpleNamespace(memory_command="forget", memory_id="one", memory_id_positional="two"),
        MagicMock(),
        ui,
        CLIConfig(),
    )
    assert result == 1
    ui.error.assert_called_once()


def test_memory_list_parses_current_and_paginated_shapes() -> None:
    client = object.__new__(TrinaxAPIClient)
    client._get = MagicMock(return_value={"memories": [{"id": "one"}]})
    assert client.list_memories() == [{"id": "one"}]
    client._get.return_value = {"items": [{"id": "two"}], "next_cursor": None}
    assert client.list_memories() == [{"id": "two"}]
    client._get.return_value = {"unexpected": []}
    with __import__("pytest").raises(TrinaxAPIError):
        client.list_memories()


def test_ask_reads_unicode_stdin_when_prompt_is_omitted(monkeypatch) -> None:
    stdin = MagicMock()
    stdin.isatty.return_value = False
    stdin.read.return_value = "Explica café ☕\n"
    monkeypatch.setattr(ask.sys, "stdin", stdin)
    monkeypatch.setattr(ask, "_stream_answer", lambda *_args: "ok")
    ui = MagicMock()

    with patch("trinaxai_cli.commands.ask.Session"):
        result = ask.run(
            SimpleNamespace(prompt=[], collections=None, engine="ollama", session=None),
            MagicMock(),
            ui,
            CLIConfig(),
        )

    assert result == 0


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


def test_cli_export_produces_markdown_with_session_name(tmp_path: Path) -> None:
    from trinaxai_cli.commands import export
    from trinaxai_cli.session import Session

    session_records = [
        {"role": "user", "content": "hello", "ts": 1000},
        {"role": "assistant", "content": "hi there", "ts": 1001},
    ]
    with patch.object(Session, "load", return_value=session_records):
        ui = MagicMock()
        args = SimpleNamespace(session="test", format="md", output=str(tmp_path / "out.md"))
        result = export.run(args, MagicMock(), ui, MagicMock())

    assert result == 0
    output_file = tmp_path / "out.md"
    assert output_file.exists()
    content = output_file.read_text()
    assert "# TrinaxAI session: test" in content
    assert "hello" in content
    assert "hi there" in content
    ui.success.assert_called_once()


def test_cli_export_rejects_empty_session() -> None:
    from trinaxai_cli.commands import export
    from trinaxai_cli.session import Session

    with patch.object(Session, "load", return_value=[]):
        ui = MagicMock()
        args = SimpleNamespace(session="empty", format="md", output=None)
        result = export.run(args, MagicMock(), ui, MagicMock())

    assert result == 1
    ui.error.assert_called_once()


def test_cli_config_masks_secret_keys() -> None:
    from trinaxai_cli.commands import _system, config

    ui = MagicMock()
    cli_config = CLIConfig()
    with (
        patch.dict(os.environ, {"TRINAXAI_ADMIN_TOKEN": "secret123"}),
        patch.object(_system, "load_dotenv_values", return_value={}),
    ):
        result = config.run(SimpleNamespace(), MagicMock(), ui, cli_config)

    assert result == 0
    ui.table.assert_called_once()
    # ui.table(headers, rows, title=...): headers[0], rows[1]
    rows = ui.table.call_args[0][1]
    admin_row = next((r for r in rows if r[0] == "TRINAXAI_ADMIN_TOKEN"), None)
    assert admin_row is not None, f"TRINAXAI_ADMIN_TOKEN not found in rows: {[r[0] for r in rows]}"
    assert "secret123" not in admin_row[1]


def test_cli_version_prints_version_string() -> None:
    from trinaxai_cli.app import VERSION
    from trinaxai_cli.commands import version

    ui = MagicMock()
    result = version.run(SimpleNamespace(), MagicMock(), ui, MagicMock())

    assert result == 0
    ui.print.assert_called_once()
    printed = ui.print.call_args[0][0]
    assert "TrinaxAI CLI" in printed
    assert VERSION in printed
