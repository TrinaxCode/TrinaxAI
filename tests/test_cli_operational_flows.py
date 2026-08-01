from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from trinaxai_cli.agent import Tool
from trinaxai_cli.commands import _system, agent, collections, doctor, memory


class _Session:
    entries: list[tuple[str, str]] = []

    def __init__(self, _name: str) -> None:
        self.entries = []
        type(self).entries = self.entries

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def append(self, role: str, content: str) -> None:
        self.entries.append((role, content))


def test_agent_single_task_and_interactive_recovery(monkeypatch) -> None:
    engine = SimpleNamespace(
        workspace_root=Path("/workspace"),
        model="model",
        run=MagicMock(side_effect=["single answer", KeyboardInterrupt(), "interactive answer"]),
    )
    monkeypatch.setattr(agent, "_build_engine", lambda *_args: engine)
    monkeypatch.setattr(agent, "Session", _Session)
    ui = MagicMock()

    assert agent.run(SimpleNamespace(prompt="single", session="test"), None, ui, object()) == 0
    assert _Session.entries == [("user", "single"), ("assistant", "single answer")]

    ui.prompt.side_effect = ["", "/clear", "interrupted", "works", "/exit"]
    assert agent.run(SimpleNamespace(prompt=None, session="test"), None, ui, object()) == 0
    ui.success.assert_called_with("Conversation cleared.")
    ui.warn.assert_called_with("\ninterrupted.")
    assert _Session.entries[-2:] == [("user", "works"), ("assistant", "interactive answer")]


def test_agent_setup_task_failure_and_eof_are_safe(monkeypatch) -> None:
    ui = MagicMock()
    monkeypatch.setattr(agent, "_build_engine", MagicMock(side_effect=ValueError("bad workspace")))
    assert agent.run(SimpleNamespace(prompt="task"), None, ui, object()) == 1
    ui.failure.assert_called_once()

    engine = SimpleNamespace(
        workspace_root=Path("."), model="model", run=MagicMock(side_effect=RuntimeError("offline"))
    )
    monkeypatch.setattr(agent, "_build_engine", lambda *_args: engine)
    monkeypatch.setattr(agent, "Session", _Session)
    assert agent.run(SimpleNamespace(prompt="task", session="test"), None, ui, object()) == 1

    ui.prompt.side_effect = EOFError
    assert agent.run(SimpleNamespace(prompt=None, session="test"), None, ui, object()) == 0


def test_memory_commands_cover_success_validation_and_backend_failure() -> None:
    client = MagicMock()
    ui = MagicMock()
    long_text = "x" * 81
    client.list_memories.return_value = [
        {"id": "a" * 32, "text": long_text, "tags": ["work"], "created_at": 1},
        {"id": "ab" + "b" * 30, "text": "second"},
    ]

    assert memory.run(SimpleNamespace(memory_command="list"), client, ui, None) == 0
    assert ui.table.call_args.args[1][0][1].endswith("…")

    client.add_memory.return_value = {"id": "memory-id"}
    assert memory.run(SimpleNamespace(memory_command="add", text="remember", tags="work, local"), client, ui, None) == 0
    client.add_memory.assert_called_with("remember", ["work", "local"])

    assert (
        memory.run(
            SimpleNamespace(memory_command="forget", memory_id="one", memory_id_positional="two"),
            client,
            ui,
            None,
        )
        == 1
    )
    assert (
        memory.run(SimpleNamespace(memory_command="forget", memory_id="a", memory_id_positional=None), client, ui, None)
        == 1
    )

    client.list_memories.return_value = [{"id": "unique" + "0" * 26}]
    client.delete_memory.return_value = True
    assert (
        memory.run(
            SimpleNamespace(memory_command="forget", memory_id="unique", memory_id_positional=None),
            client,
            ui,
            None,
        )
        == 0
    )

    client.refresh_memory.return_value = {"count": 1, "summary": "summary"}
    assert memory.run(SimpleNamespace(memory_command="refresh"), client, ui, None) == 0
    client.memory_summary.return_value = {"summary": "summary"}
    assert memory.run(SimpleNamespace(memory_command="summary"), client, ui, None) == 0
    assert memory.run(SimpleNamespace(memory_command="unknown"), client, ui, None) == 1

    client.list_memories.side_effect = RuntimeError("offline")
    assert memory.run(SimpleNamespace(memory_command="list"), client, ui, None) == 1
    ui.failure.assert_called()


def test_service_helpers_read_state_and_run_actions(monkeypatch, tmp_path: Path) -> None:
    script = tmp_path / "service_manager.py"
    script.write_text("", encoding="utf-8")
    (tmp_path / ".env").write_text(
        "# comment\nOLLAMA_BASE_URL=http://localhost:11434/\nTOKEN='secret'\nINVALID\n",
        encoding="utf-8",
    )
    state_path = tmp_path / "storage" / "service_state.json"
    state_path.parent.mkdir()
    state_path.write_text('{"running": true}', encoding="utf-8")
    monkeypatch.setattr(_system, "project_root", lambda: tmp_path)
    ui = MagicMock()

    process = SimpleNamespace(returncode=0, stdout="started\n", stderr="warning\n")
    monkeypatch.setattr(_system, "run_process_group", lambda *_args, **_kwargs: process)
    assert _system.run_service_action("start", ui) == 0
    ui.print.assert_called_with("started")
    ui.warn.assert_called_with("warning")

    assert _system.load_dotenv_values()["TOKEN"] == "secret"
    assert _system.env_value("OLLAMA_BASE_URL") == "http://localhost:11434"
    assert _system.service_state() == {"running": True}
    assert _system.masked("short") == "*****"
    assert _system.masked("123456789") == "1234...6789"

    state_path.write_text("{broken", encoding="utf-8")
    assert _system.service_state() == {}

    monkeypatch.setattr(
        _system,
        "run_process_group",
        MagicMock(side_effect=subprocess.TimeoutExpired(["service"], 1)),
    )
    assert _system.run_service_action("status", ui) == 1

    monkeypatch.setattr(_system, "project_root", lambda: None)
    assert _system.run_service_action("status", ui) == 1
    assert _system.load_dotenv_values() == {}
    assert _system.service_state() == {}


def test_doctor_reports_healthy_services_and_optional_state(monkeypatch, tmp_path: Path) -> None:
    manager = tmp_path / "service_manager.py"
    manager.write_text("", encoding="utf-8")
    monkeypatch.setattr(doctor._system, "project_root", lambda: tmp_path)
    monkeypatch.setattr(doctor._system, "service_manager", lambda: manager)
    monkeypatch.setattr(doctor._system, "env_value", lambda _key: "http://localhost:11434")
    monkeypatch.setattr(doctor._system, "load_dotenv_values", lambda: {"TRINAXAI_FRONTEND_MODE": "serve"})
    monkeypatch.setattr(doctor, "_find_ollama", lambda: "/usr/bin/ollama")
    monkeypatch.setattr(doctor, "_ollama_api_ok", lambda _url: True)
    monkeypatch.setattr(
        doctor,
        "_process_command",
        lambda pid: "node server.mjs" if pid == 10 else "uvicorn rag_api:app --host 127.0.0.1",
    )
    services = [
        {"name": "trinaxai-frontend", "display_name": "Frontend", "running": True, "pid": 10},
        {"name": "rag_api", "display_name": "API", "running": True, "pid": 11},
    ]
    monkeypatch.setattr(
        doctor,
        "run_process_group",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout=json.dumps(services), stderr=""),
    )
    client = SimpleNamespace(
        base_url="https://localhost:3333",
        health=lambda: {"indexed": True, "projects": ["one"], "collections": [{"id": "docs"}]},
        stats=lambda: {"messages_total": 2, "tokens_estimated": 3},
        memory_summary=lambda: {"summary": "remembered"},
    )
    ui = MagicMock()

    assert doctor.run(SimpleNamespace(json=False, strict=True), client, ui, None) == 0
    rows = ui.table.call_args.args[1]
    assert all(row[1] == "OK" for row in rows)
    ui.panel.assert_called_with("remembered", title="Memory summary")


def test_doctor_degrades_cleanly_when_install_and_api_are_unavailable(monkeypatch, capsys) -> None:
    monkeypatch.setattr(doctor._system, "project_root", lambda: None)
    monkeypatch.setattr(doctor._system, "service_manager", lambda: Path("missing"))
    monkeypatch.setattr(doctor._system, "env_value", lambda _key: "")
    monkeypatch.setattr(doctor, "_find_ollama", lambda: None)
    monkeypatch.setattr(doctor, "_ollama_api_ok", lambda _url: False)
    client = MagicMock()
    client.health.side_effect = RuntimeError("private traceback")

    assert doctor.run(SimpleNamespace(json=True, strict=True), client, MagicMock(), None) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["healthy"] is False
    assert any(item["check"] == "RAG API" and not item["ok"] for item in payload["checks"])


def test_collections_cover_empty_create_delete_validation_and_failure(tmp_path: Path) -> None:
    client = MagicMock()
    ui = MagicMock()
    config = SimpleNamespace(active_collection=None, collections=[], save=lambda: tmp_path / "config.toml")

    client.list_collections.return_value = []
    assert collections.run(SimpleNamespace(collections_command="list"), client, ui, config) == 0
    ui.info.assert_called_with("No collections.")

    ui.prompt.return_value = ""
    assert collections.run(SimpleNamespace(collections_command="create", name=None), client, ui, config) == 1
    client.create_collection.return_value = {"id": "docs", "name": "Docs"}
    assert collections.run(SimpleNamespace(collections_command="create", name="Docs"), client, ui, config) == 0

    assert (
        collections.run(
            SimpleNamespace(collections_command="delete", collection_id="docs", name="Docs"),
            client,
            ui,
            config,
        )
        == 1
    )
    client.list_collections.return_value = [{"id": "a", "name": "Docs"}, {"id": "b", "name": "Docs"}]
    assert (
        collections.run(
            SimpleNamespace(collections_command="delete", collection_id=None, name="Docs"),
            client,
            ui,
            config,
        )
        == 1
    )
    assert (
        collections.run(
            SimpleNamespace(collections_command="delete", collection_id="default", name=None),
            client,
            ui,
            config,
        )
        == 1
    )
    ui.confirm.return_value = False
    assert (
        collections.run(
            SimpleNamespace(collections_command="delete", collection_id="docs", name=None),
            client,
            ui,
            config,
        )
        == 0
    )
    assert collections.run(SimpleNamespace(collections_command="unknown"), client, ui, config) == 1

    client.list_collections.side_effect = RuntimeError("offline")
    assert collections.run(SimpleNamespace(collections_command="list"), client, ui, config) == 1
    ui.failure.assert_called()


def test_agent_callbacks_preview_and_dynamic_approval() -> None:
    ui = MagicMock()
    ui.confirm.return_value = False

    def noop(*_args, **_kwargs):
        return "ok"

    write = Tool("write_file", "write", {}, noop, True)
    edit = Tool("edit_file", "edit", {}, noop, True)
    shell = Tool("run_command", "run", {}, noop, True)
    read = Tool("read_file", "read", {}, noop, False)

    callbacks = agent._make_callbacks(ui, False)
    callbacks["on_tool_start"](write, {"path": "a.txt", "content": "line"})
    callbacks["on_tool_result"](read, "first\nsecond")
    assert callbacks["on_confirm"](write, {"path": "a.txt", "content": "line"}) is False
    assert callbacks["on_confirm"](edit, {"path": "a.txt", "old": "x", "new": "y"}) is False
    assert callbacks["on_confirm"](shell, {"command": "pytest"}) is False
    callbacks["on_token"]("token")
    assert ui.code.call_count == 3

    enabled = {"value": False}
    dynamic = agent.make_dynamic_callbacks(ui, lambda: enabled["value"])
    assert dynamic["on_confirm"](write, {"path": "a", "content": ""}) is False
    enabled["value"] = True
    assert dynamic["on_confirm"](write, {"path": "a", "content": ""}) is True
    assert agent._make_callbacks(ui, True)["on_confirm"] is None


def test_agent_resolution_and_engine_construction(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(agent._system, "env_value", lambda key: {"OLLAMA_BASE_URL": "http://ollama"}.get(key))
    assert agent._resolve_num_ctx(SimpleNamespace(NUM_CTX=1000)) == 8192
    monkeypatch.setattr(agent._system, "env_value", lambda key: "999999" if key == "TRINAXAI_AGENT_NUM_CTX" else None)
    assert agent._resolve_num_ctx(SimpleNamespace(NUM_CTX=1000)) == 131072
    monkeypatch.setattr(agent._system, "env_value", lambda key: "bad" if key == "TRINAXAI_AGENT_NUM_CTX" else None)
    assert agent._resolve_num_ctx(SimpleNamespace(NUM_CTX=999999)) == 16384

    captured = {}

    class Engine:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(agent, "AgentEngine", Engine)
    monkeypatch.setattr(agent, "_resolve_verifier_model", lambda: "verifier")
    monkeypatch.setattr(agent, "_resolve_model", lambda *_args, **_kwargs: "model")
    built = agent.build_agent_engine(
        MagicMock(), workspace=str(tmp_path), max_steps=3, config=SimpleNamespace(NUM_CTX=8192)
    )
    assert isinstance(built, Engine)
    assert captured["workspace_root"] == tmp_path and captured["max_steps"] == 3
    with __import__("pytest").raises(ValueError, match="workspace"):
        agent.build_agent_engine(MagicMock(), workspace=str(tmp_path / "missing"))
