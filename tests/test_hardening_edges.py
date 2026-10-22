"""Edge cases of the agent engine accounting and of the device/git write guards."""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services import agent_service, watcher_service
from trinaxai_agent import AgentEngine, SandboxError
from trinaxai_agent import tools as agent_tools
from trinaxai_agent.engine import AgentCancelled


def test_usage_accounting_ignores_malformed_counters(tmp_path: Path) -> None:
    engine = AgentEngine(model="m", workspace_root=tmp_path)
    engine._record_usage({"prompt_eval_count": 4, "eval_count": 6})
    engine._record_usage({"prompt_eval_count": "not a number", "eval_count": 1})
    engine._record_usage({"prompt_eval_count": None, "eval_count": None})
    assert engine.usage == {"prompt": 4, "completion": 6, "requests": 2}  # the malformed record is skipped


def test_compact_is_best_effort_but_never_swallows_cancellation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    engine = AgentEngine(model="m", workspace_root=tmp_path)
    history = [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}]

    def broken(*_a, **_k):
        raise ConnectionError("ollama down")

    monkeypatch.setattr(engine, "_post_with_cancellation", broken)
    assert engine.compact(list(history)) is None

    def cancelled(*_a, **_k):
        raise AgentCancelled

    monkeypatch.setattr(engine, "_post_with_cancellation", cancelled)
    with pytest.raises(AgentCancelled):
        engine.compact(list(history))

    monkeypatch.setattr(engine, "_post_with_cancellation", lambda *_a, **_k: {"message": {"content": "   "}})
    untouched = list(history)
    assert engine.compact(untouched) is None and untouched == history  # an empty summary must not wipe history


def test_git_metadata_guard_checks_identity_and_tolerates_unreadable_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "docs").mkdir()
    real = os.path.samefile

    # A directory that *is* the git dir under another name (bind mount, hard link) is refused.
    monkeypatch.setattr(agent_tools.os.path, "samefile", lambda a, b: True if Path(a).name == "alias" else real(a, b))
    (tmp_path / "alias").mkdir()
    with pytest.raises(SandboxError):
        agent_tools._write_file(tmp_path, "alias/config", "x")

    def unreadable(_a, _b):
        raise OSError("stat failed")

    monkeypatch.setattr(agent_tools.os.path, "samefile", unreadable)
    assert "created" in agent_tools._write_file(tmp_path, "docs/readme.md", "ok")  # an OSError never blocks a safe path


def test_protected_paths_skip_unresolvable_locations(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(agent_service.config, "BASE_DIR", None)  # Path(None) raises TypeError
    monkeypatch.setattr(agent_service.config, "PERSIST_DIR", str(tmp_path / "storage"))
    monkeypatch.setattr(agent_service.config, "LOCAL_SOURCES_DIR", str(tmp_path / "storage"))  # duplicate entry
    monkeypatch.setattr(agent_service, "credential_files", lambda: (tmp_path / "r.json", tmp_path / ".s"))
    monkeypatch.setattr(agent_service, "proxy_secret_file", lambda: tmp_path / ".proxy")
    paths = agent_service._protected_state_paths()
    assert (tmp_path / "storage").resolve() in paths
    assert len(paths) == len(set(paths))


def test_device_browse_home_falls_back_to_a_navigable_root_or_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    protected = (tmp_path / "install").resolve()
    protected.mkdir()
    sibling = (tmp_path / "work").resolve()
    sibling.mkdir()
    monkeypatch.setattr(agent_service, "_protected_state_paths", lambda: (protected,))
    monkeypatch.setattr(agent_service, "_is_broad_workspace", lambda _root: False)
    # Every root contains protected files, so no safe default exists, but a root is still navigable.
    assert agent_service._device_browse_home((tmp_path.resolve(),)) == tmp_path.resolve()
    with pytest.raises(HTTPException):
        agent_service._device_browse_home((protected,))  # nothing the device may even navigate
    assert agent_service._device_browse_home((protected, sibling)) == sibling


def test_remote_watch_guard_skips_blank_entries(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(watcher_service.config, "PROJECTS_DIRS", [str(tmp_path)])
    device = SimpleNamespace(state=SimpleNamespace(trinaxai_identity={"kind": "device"}))
    watcher_service._enforce_remote_watch_paths(watcher_service.WatchStartRequest(paths=["", str(tmp_path)]), device)
