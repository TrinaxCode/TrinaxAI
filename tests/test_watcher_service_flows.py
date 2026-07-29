from __future__ import annotations

import io
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services import watcher_service
from app.services.engine_state import state


def test_watch_paths_defaults_deduplicate_and_reject_links(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    link = tmp_path / "link"
    link.symlink_to(source, target_is_directory=True)
    monkeypatch.setattr(watcher_service.config, "PROJECTS_DIRS", [str(source), str(source), str(tmp_path / "missing")])
    assert watcher_service._watch_default_paths(None) == [str(source)]

    req = watcher_service.WatchStartRequest(paths=[str(source), str(source), str(link)])
    assert watcher_service._watch_paths(req) == [str(source)]
    assert watcher_service._tail_stream(io.BytesIO(b"0123456789"), 4) == "6789"


@pytest.mark.parametrize(
    ("result", "reload_ok", "status", "counter"),
    [
        (watcher_service._WatchRunResult(0, duration_seconds=1), True, "succeeded", "runs_completed"),
        (watcher_service._WatchRunResult(2, stderr="failed"), False, "failed", "runs_failed"),
        (watcher_service._WatchRunResult(None, timed_out=True), False, "timed_out", "runs_timed_out"),
        (watcher_service._WatchRunResult(None, cancelled=True), False, "cancelled", "runs_cancelled"),
        (watcher_service._WatchRunResult(0), False, "failed", "runs_failed"),
    ],
)
def test_watcher_publishes_every_terminal_job_state(
    tmp_path: Path,
    result,
    reload_ok: bool,
    status: str,
    counter: str,
) -> None:
    handler = watcher_service._watch_Handler([str(tmp_path)])
    with state.watcher["lock"]:
        state.watcher["handler"] = handler
        watcher_service._reset_watch_job_state()
    handler._publish_result(str(tmp_path), result, reload_ok=reload_ok)
    with state.watcher["lock"]:
        assert state.watcher["job_status"] == status
        assert state.watcher[counter] == 1
        state.watcher["handler"] = None
    handler.shutdown()


def test_watcher_event_hooks_group_nested_roots_and_ignore_runtime(monkeypatch, tmp_path: Path) -> None:
    outer = tmp_path / "outer"
    inner = outer / "inner"
    inner.mkdir(parents=True)
    runtime = outer / "storage"
    runtime.mkdir()
    monkeypatch.setattr(watcher_service.config, "PERSIST_DIR", str(runtime))
    monkeypatch.setattr(watcher_service.config, "LOCAL_SOURCES_DIR", str(tmp_path / "local"))
    handler = watcher_service._watch_Handler([str(outer), str(inner)])
    monkeypatch.setattr(handler, "_schedule", lambda: None)
    changed = inner / "note.txt"
    event = SimpleNamespace(src_path=str(changed), dest_path=str(inner / "moved.txt"), is_directory=False)

    handler.on_created(event)
    handler.on_modified(event)
    handler.on_moved(event)
    handler.on_deleted(event)
    assert str(changed) in handler._pending
    assert handler._events_by_root([str(changed)]) == {str(inner): [str(changed)]}
    assert handler._ignored(str(runtime / "state.json")) is True
    handler.shutdown()


def test_watch_start_reports_missing_dependency_invalid_paths_and_existing_observer(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(watcher_service, "_authorize_system", lambda _request: None)
    monkeypatch.setattr(watcher_service, "_watch_try_import", lambda: None)
    with pytest.raises(HTTPException) as missing:
        watcher_service.watch_start(watcher_service.WatchStartRequest(paths=[str(tmp_path)]), object())
    assert missing.value.status_code == 501

    class Observer:
        def is_alive(self):
            return True

    monkeypatch.setattr(watcher_service, "_watch_try_import", lambda: Observer)
    with state.watcher["lock"]:
        state.watcher["observer"] = None
        state.watcher["handler"] = None
    with pytest.raises(HTTPException) as invalid:
        watcher_service.watch_start(
            watcher_service.WatchStartRequest(paths=[str(tmp_path / "missing")]),
            object(),
        )
    assert invalid.value.status_code == 400

    with state.watcher["lock"]:
        state.watcher["observer"] = Observer()
        state.watcher["paths"] = [str(tmp_path)]
    result = watcher_service.watch_start(watcher_service.WatchStartRequest(paths=[str(tmp_path)]), object())
    assert result["status"] == "already_running"
    with state.watcher["lock"]:
        state.watcher["observer"] = None
        state.watcher["paths"] = []


def test_seed_watch_mirror_skips_hidden_symlink_and_runtime_content(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    (source / "keep.txt").write_text("keep", encoding="utf-8")
    (source / ".secret").write_text("hidden", encoding="utf-8")
    (source / "link").symlink_to(source / "keep.txt")
    storage = source / "storage"
    storage.mkdir()
    (storage / "state.json").write_text("state", encoding="utf-8")
    monkeypatch.setattr(watcher_service.config, "PERSIST_DIR", str(storage))
    monkeypatch.setattr(watcher_service.config, "LOCAL_SOURCES_DIR", str(source / "local"))

    watcher_service._seed_watch_mirror(str(source), str(target))

    assert (target / "keep.txt").read_text(encoding="utf-8") == "keep"
    assert not (target / ".secret").exists()
    assert not (target / "link").exists()
    assert not (target / "storage").exists()


def test_terminate_process_tree_escalates_posix_and_ignores_exited(monkeypatch) -> None:
    class Process:
        pid = 44

        def __init__(self):
            self.polls = iter([None, None])

        def poll(self):
            return next(self.polls, 0)

        def wait(self, timeout=None):
            raise watcher_service.subprocess.TimeoutExpired("index", timeout)

    process = Process()
    signals = []
    monkeypatch.setattr(watcher_service.os, "name", "posix")
    monkeypatch.setattr(watcher_service.os, "getpgid", lambda pid: pid, raising=False)
    monkeypatch.setattr(
        watcher_service.os,
        "killpg",
        lambda pid, sig: signals.append((pid, sig)),
        raising=False,
    )
    watcher_service._terminate_process_tree(process, grace_seconds=0.01)
    assert [sig for _pid, sig in signals] == [watcher_service.signal.SIGTERM, watcher_service.signal.SIGKILL]

    process.polls = iter([0])
    signals.clear()
    watcher_service._terminate_process_tree(process)
    assert signals == []


def test_handler_queue_mirror_and_batch_processing(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "source"
    mirror = tmp_path / "mirror"
    source.mkdir()
    changed = source / "folder" / "note.txt"
    changed.parent.mkdir()
    changed.write_text("new", encoding="utf-8")
    handler = watcher_service._watch_Handler(
        [str(source)],
        mirror_roots={str(source): str(mirror)},
        collection_ids={str(source): "docs"},
        collection_names={str(source): "Docs"},
    )
    with state.watcher["lock"]:
        state.watcher["handler"] = handler
        watcher_service._reset_watch_job_state()
    try:
        handler._pending.add(str(changed))
        handler._fire()
        with handler._queue_condition:
            assert str(changed) in handler._queued
            handler._queued.clear()

        results = []
        monkeypatch.setattr(
            handler,
            "_run_indexer",
            lambda env: results.append(env) or watcher_service._WatchRunResult(0),
        )
        monkeypatch.setattr(handler, "_reload_engine", lambda: True)
        handler._process_batch([str(changed)])
        assert (mirror / "folder" / "note.txt").read_text(encoding="utf-8") == "new"
        assert results[0]["TRINAXAI_COLLECTION_ID"] == "docs"

        changed.unlink()
        handler._sync_mirror(str(source), str(mirror), [str(changed)])
        assert not (mirror / "folder").exists()
    finally:
        with state.watcher["lock"]:
            state.watcher["handler"] = None
        handler.shutdown()


def test_handler_reload_and_indexer_start_failure(monkeypatch, tmp_path: Path) -> None:
    handler = watcher_service._watch_Handler([str(tmp_path)])
    try:
        monkeypatch.setattr(
            watcher_service,
            "exclusive_process_lock",
            lambda *_args, **_kwargs: pytest.raises(AssertionError),
        )
        monkeypatch.setattr(watcher_service, "build_engine", lambda **_kwargs: True)

        class Lock:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        monkeypatch.setattr(watcher_service, "exclusive_process_lock", lambda *_args, **_kwargs: Lock())
        assert handler._reload_engine() is True

        monkeypatch.setattr(
            watcher_service.subprocess,
            "Popen",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("permission denied")),
        )
        result = handler._run_indexer({})
        assert result.returncode is None and "permission denied" in result.stderr
    finally:
        handler.shutdown()


def test_prepare_watch_targets_for_managed_and_external_roots(monkeypatch, tmp_path: Path) -> None:
    collections = tmp_path / "collections"
    managed = collections / "managed"
    external = tmp_path / "external"
    managed.mkdir(parents=True)
    external.mkdir()
    (external / "note.txt").write_text("note", encoding="utf-8")
    monkeypatch.setattr(watcher_service.config, "LOCAL_SOURCES_DIR", str(tmp_path))
    monkeypatch.setattr(
        watcher_service,
        "_read_collections_unlocked",
        lambda: [{"id": "managed", "name": "Managed"}, {"id": "docs", "name": "Docs"}],
    )
    req = watcher_service.WatchStartRequest(paths=[str(managed), str(external)], collection="docs")
    mirrors, ids, names = watcher_service._prepare_watch_targets(req, [str(managed), str(external)])
    assert mirrors[str(managed)] == str(managed)
    assert ids[str(managed)] == "managed" and names[str(managed)] == "Managed"
    assert Path(mirrors[str(external)], "note.txt").exists()
    assert ids[str(external)] == "docs"


@pytest.mark.asyncio
async def test_watch_lifecycle_success_status_and_stop(monkeypatch, tmp_path: Path) -> None:
    scheduled = []

    class Observer:
        alive = False

        def schedule(self, handler, path, recursive):
            scheduled.append((handler, path, recursive))

        def start(self):
            self.alive = True

        def is_alive(self):
            return self.alive

        def stop(self):
            self.alive = False

        def join(self, timeout=None):
            return None

    class Handler:
        def __init__(self, paths, **_kwargs):
            self.paths = paths

        def shutdown(self):
            return True

    monkeypatch.setattr(watcher_service, "_authorize_system", lambda _request: None)
    monkeypatch.setattr(watcher_service, "_watch_try_import", lambda: Observer)
    monkeypatch.setattr(watcher_service, "_watch_Handler", Handler)
    monkeypatch.setattr(
        watcher_service,
        "_prepare_watch_targets",
        lambda _req, paths: ({path: path for path in paths}, {}, {}),
    )
    with state.watcher["lock"]:
        state.watcher["observer"] = None
        state.watcher["handler"] = None
    started = watcher_service.watch_start(
        watcher_service.WatchStartRequest(paths=[str(tmp_path)]),
        object(),
    )
    assert started["status"] == "started" and scheduled[0][2] is True
    status = await watcher_service.watch_status(object())
    assert status["running"] is True and status["watching"] == [str(tmp_path)]
    stopped = await watcher_service.watch_stop(object())
    assert stopped == {"status": "stopped"}
    assert await watcher_service.watch_stop(object()) == {"status": "not_running"}
