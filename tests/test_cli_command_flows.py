from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from trinaxai_cli.commands import (
    browse,
    help,
    mcp,
    models,
    research,
    restart,
    start,
    status,
    stop,
    uninstall,
    update,
    watch,
)


@pytest.fixture
def ui() -> MagicMock:
    value = MagicMock()
    value.spinner.return_value = nullcontext()
    return value


def test_browse_lists_collections_files_and_bounded_chunks(ui) -> None:
    client = MagicMock()
    client.list_collections.return_value = [{"id": "docs", "name": "Docs"}]
    client.list_sources.return_value = {"sources": [{"file": "guide.md", "chunks": 2, "size": 10, "mtime": 20}]}
    client.list_chunks.return_value = {
        "chunks": [{"text": "x" * 1201, "score": 0.9}],
        "total": 1,
    }

    assert browse.run(SimpleNamespace(browse_command="list"), client, ui, None) == 0
    assert browse.run(SimpleNamespace(browse_command="list-files", collection="docs"), client, ui, None) == 0
    assert (
        browse.run(
            SimpleNamespace(browse_command="show-chunks", collection="docs", file="guide.md", limit=2),
            client,
            ui,
            None,
        )
        == 0
    )

    client.list_chunks.assert_called_once_with("docs", "guide.md", limit=2)
    assert ui.panel.call_args.args[0].endswith("…")


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (SimpleNamespace(browse_command="show-chunks", collection="docs", file=None), "File path required"),
        (SimpleNamespace(browse_command="unknown"), "Unknown subcommand"),
    ],
)
def test_browse_rejects_invalid_actions(args, message, ui) -> None:
    assert browse.run(args, MagicMock(), ui, None) == 1
    assert message in ui.error.call_args.args[0]


def test_browse_and_watch_convert_client_errors_to_failures(ui) -> None:
    client = MagicMock()
    client.list_collections.side_effect = RuntimeError("offline")
    client.watch_status.side_effect = RuntimeError("offline")

    assert browse.run(SimpleNamespace(browse_command="list"), client, ui, None) == 1
    assert watch.run(SimpleNamespace(watch_command="status"), client, ui, None) == 1
    assert ui.failure.call_count == 2


def test_research_validates_and_renders_results(ui) -> None:
    client = MagicMock()
    client.research.return_value = {
        "passes": 2,
        "model": "general",
        "sub_questions": ["one", "two"],
        "answer": "answer",
        "sources": [{"file": "guide.md", "page": 3}],
    }

    assert research.run(SimpleNamespace(query=None), client, ui, None) == 1
    assert (
        research.run(
            SimpleNamespace(query="topic", collections="docs, notes", depth=2),
            client,
            ui,
            None,
        )
        == 0
    )
    client.research.assert_called_once_with(query="topic", collections=["docs", "notes"], depth=2)
    ui.markdown.assert_called_once_with("answer")

    client.research.side_effect = RuntimeError("offline")
    assert research.run(SimpleNamespace(query="topic", collections=[], depth=1), client, ui, None) == 1


def test_research_can_persist_a_public_exportable_session(monkeypatch, ui) -> None:
    client = MagicMock()
    client.research.return_value = {
        "passes": 2,
        "model": "general",
        "answer": "answer",
        "sources": [{"title": "Guide", "url": "https://example.test"}],
        "api_key": "must-not-be-persisted",
    }
    rows: list[tuple[str, str, dict]] = []

    class CapturingSession:
        def __init__(self, name: str) -> None:
            assert name == "research"

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def append(self, role: str, content: str, meta: dict) -> None:
            rows.append((role, content, meta))

    monkeypatch.setattr(research, "Session", CapturingSession)
    assert (
        research.run(SimpleNamespace(query="topic", collections=[], depth=2, session="research"), client, ui, None) == 0
    )

    assert rows == [
        ("user", "topic", {"mode": "deep_research"}),
        (
            "assistant",
            "answer",
            {
                "mode": "deep_research",
                "research": {"passes": 2, "sources": [{"title": "Guide", "url": "https://example.test"}]},
            },
        ),
    ]
    assert any("https://example.test" in str(call.args[0]) for call in ui.info.call_args_list)


@pytest.mark.parametrize("action", ["start", "stop", "status"])
def test_watch_actions_report_state(action, ui) -> None:
    client = MagicMock()
    client.watch_start.return_value = {"status": "started", "watching": ["/docs"]}
    client.watch_stop.return_value = {"status": "stopped"}
    client.watch_status.return_value = {
        "running": True,
        "watching": ["/docs"],
        "events_seen": 3,
        "job": {"status": "indexing", "pending_events": 2, "active_root": "/docs", "last_error": "retrying"},
    }

    assert (
        watch.run(
            SimpleNamespace(watch_command=action, paths=["/docs"], collection="docs"),
            client,
            ui,
            None,
        )
        == 0
    )


def test_models_survives_ollama_outage_and_marks_missing_recommendations(monkeypatch, ui) -> None:
    client = MagicMock()
    client.list_ollama_models.side_effect = RuntimeError("offline")
    monkeypatch.setattr(models._system, "env_value", lambda _name: None)

    assert models.run(SimpleNamespace(), client, ui, None) == 0
    assert ui.failure.called
    rows = ui.table.call_args.args[1]
    assert {row[0] for row in rows} == set(models.RECOMMENDED)


def test_service_commands_confirm_and_forward_actions(monkeypatch, ui) -> None:
    actions: list[tuple[str, int]] = []
    monkeypatch.setattr(
        start._system,
        "run_service_action",
        lambda action, _ui, timeout: actions.append((action, timeout)) or 0,
    )
    monkeypatch.setattr(status._system, "service_state", lambda: {"ai_enabled": True})
    ui.confirm.return_value = False

    assert start.run(SimpleNamespace(), None, ui, None) == 0
    assert restart.run(SimpleNamespace(yes=False), None, ui, None) == 0
    assert stop.run(SimpleNamespace(yes=False, all=False), None, ui, None) == 0
    assert status.run(SimpleNamespace(), None, ui, None) == 0

    ui.confirm.return_value = True
    assert restart.run(SimpleNamespace(yes=False), None, ui, None) == 0
    assert stop.run(SimpleNamespace(yes=True, all=True), None, ui, None) == 0
    assert actions == [
        ("start", 180),
        ("status", 30),
        ("stop-ai", 180),
        ("start-ai", 180),
        ("stop-all", 180),
    ]


def test_lifecycle_commands_forward_platform_flags(monkeypatch, ui) -> None:
    calls: list[tuple[str, list[str]]] = []
    monkeypatch.setattr(
        uninstall,
        "run_script",
        lambda name, flags, _ui: calls.append((name, flags)) or 0,
    )
    monkeypatch.setattr(update, "run_script", lambda name, flags, _ui: calls.append((name, flags)) or 0)
    monkeypatch.setattr(uninstall.sys, "platform", "linux")
    monkeypatch.setattr(update.sys, "platform", "linux")

    assert (
        uninstall.run(
            SimpleNamespace(
                yes=True,
                purge=True,
                remove_data=False,
                remove_models=False,
                remove_ollama=False,
                keep_env=True,
            ),
            None,
            ui,
            None,
        )
        == 0
    )
    assert (
        update.run(
            SimpleNamespace(
                yes=True,
                no_backup=True,
                no_pull=False,
                models=False,
                no_models=False,
                restart=True,
                no_restart=False,
            ),
            None,
            ui,
            None,
        )
        == 0
    )
    assert calls == [
        ("uninstall", ["--yes", "--purge", "--keep-env"]),
        ("update", ["--non-interactive", "--no-backup", "--restart"]),
    ]


def test_help_and_mcp_have_stable_exit_contracts(monkeypatch, ui) -> None:
    monkeypatch.setattr(help, "_build_parser", lambda: SimpleNamespace(format_help=lambda: "usage"))

    assert help.run(SimpleNamespace(), None, ui, None) == 0
    assert mcp.run(SimpleNamespace(), None, ui, None) == 2
    ui.print.assert_called_once_with("usage")
