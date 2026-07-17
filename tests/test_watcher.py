from __future__ import annotations

import asyncio
import json
import threading
import time

import rag_api
from app.services import watcher_service


def test_watcher_reindexes_the_changed_collection(tmp_path, monkeypatch) -> None:
    local_sources = tmp_path / "local_sources"
    collection_root = local_sources / "collections" / "docs"
    collection_root.mkdir(parents=True)
    changed = collection_root / "notes.txt"
    changed.write_text("updated", encoding="utf-8")
    storage = tmp_path / "storage"
    storage.mkdir()
    (storage / "collections.json").write_text(
        json.dumps({"collections": [{"id": "docs", "name": "Documents"}]}),
        encoding="utf-8",
    )

    monkeypatch.setattr(rag_api.config, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr(rag_api.config, "LOCAL_SOURCES_DIR", str(local_sources))
    monkeypatch.setattr(rag_api.config, "PERSIST_DIR", str(storage))
    monkeypatch.setattr(rag_api.config, "COLLECTIONS_PATH", str(storage / "collections.json"))
    calls: list[dict[str, str]] = []

    def fake_run(env):
        calls.append(env)
        return watcher_service._WatchRunResult(returncode=0)

    monkeypatch.setattr(watcher_service, "build_engine", lambda **_kwargs: True)
    handler = rag_api._watch_Handler([str(collection_root)])
    monkeypatch.setattr(handler, "_run_indexer", fake_run)
    monkeypatch.setattr(handler, "_reload_engine", lambda: True)
    handler._pending.add(str(changed))

    handler._fire()
    assert handler.wait_for_idle()
    handler.shutdown()

    assert len(calls) == 1
    env = calls[0]
    assert env["TRINAXAI_INDEX_DIR"] == str(collection_root)
    assert env["TRINAXAI_COLLECTION_ID"] == "docs"
    assert env["TRINAXAI_COLLECTION_NAME"] == "Documents"
    assert env["TRINAXAI_INDEX_APPEND"] == "0"


def test_watcher_coalesces_events_while_one_job_is_running(tmp_path, monkeypatch) -> None:
    source = tmp_path / "source"
    source.mkdir()
    files = [source / f"note-{number}.txt" for number in range(4)]
    for path in files:
        path.write_text("changed", encoding="utf-8")

    first_started = threading.Event()
    release_first = threading.Event()
    calls = 0
    active = 0
    max_active = 0
    calls_lock = threading.Lock()

    def fake_run(_env):
        nonlocal calls, active, max_active
        with calls_lock:
            calls += 1
            active += 1
            max_active = max(max_active, active)
            call_number = calls
        if call_number == 1:
            first_started.set()
            assert release_first.wait(timeout=3)
        with calls_lock:
            active -= 1
        return watcher_service._WatchRunResult(returncode=0)

    monkeypatch.setattr(watcher_service, "build_engine", lambda **_kwargs: True)
    handler = watcher_service._watch_Handler([str(source)], debounce_seconds=0.01)
    monkeypatch.setattr(handler, "_run_indexer", fake_run)
    monkeypatch.setattr(handler, "_reload_engine", lambda: True)
    handler._pending.add(str(files[0]))
    handler._fire()
    assert first_started.wait(timeout=2)

    handler._pending.update(str(path) for path in files[1:])
    handler._fire()
    handler._pending.update(str(path) for path in files[1:])
    handler._fire()
    release_first.set()

    assert handler.wait_for_idle(timeout=3)
    handler.shutdown()
    assert calls == 2
    assert max_active == 1


def test_watcher_mirror_removes_deleted_directory_tree(tmp_path) -> None:
    source = tmp_path / "source"
    mirror = tmp_path / "mirror"
    removed_source = source / "old-section"
    removed_mirror = mirror / "old-section"
    removed_source.mkdir(parents=True)
    removed_mirror.mkdir(parents=True)
    (removed_source / "old.txt").write_text("old", encoding="utf-8")
    (removed_mirror / "old.txt").write_text("old", encoding="utf-8")
    removed_source.rmdir() if not any(removed_source.iterdir()) else None
    (removed_source / "old.txt").unlink()
    removed_source.rmdir()

    handler = watcher_service._watch_Handler(
        [str(source)],
        mirror_roots={str(source): str(mirror)},
    )
    handler._sync_mirror(str(source), str(mirror), [str(removed_source)])
    handler.shutdown()

    assert not removed_mirror.exists()


def test_watcher_index_subprocess_times_out_and_captures_bounded_output(tmp_path, monkeypatch) -> None:
    index_script = tmp_path / "index.py"
    index_script.write_text(
        "import sys, time\nprint('X' * 5000, flush=True)\n"
        "print('waiting too long', file=sys.stderr, flush=True)\ntime.sleep(30)\n",
        encoding="utf-8",
    )
    source = tmp_path / "source"
    source.mkdir()
    monkeypatch.setattr(watcher_service.config, "BASE_DIR", str(tmp_path))
    monkeypatch.setenv("TRINAXAI_WATCH_INDEX_TIMEOUT", "1")
    monkeypatch.setenv("TRINAXAI_WATCH_OUTPUT_MAX_BYTES", "1024")
    handler = watcher_service._watch_Handler([str(source)])

    started = time.monotonic()
    result = handler._run_indexer(dict(watcher_service.os.environ))
    elapsed = time.monotonic() - started
    handler.shutdown()

    assert result.timed_out is True
    assert result.cancelled is False
    assert elapsed < 5
    assert len(result.stdout.encode("utf-8")) <= 1024
    assert "waiting too long" in result.stderr


def test_watcher_shutdown_cancels_active_index_process(tmp_path, monkeypatch) -> None:
    index_script = tmp_path / "index.py"
    index_script.write_text("import time\ntime.sleep(30)\n", encoding="utf-8")
    source = tmp_path / "source"
    source.mkdir()
    changed = source / "note.txt"
    changed.write_text("change", encoding="utf-8")
    monkeypatch.setattr(watcher_service.config, "BASE_DIR", str(tmp_path))
    monkeypatch.setenv("TRINAXAI_WATCH_INDEX_TIMEOUT", "60")
    handler = watcher_service._watch_Handler([str(source)])
    with watcher_service.state.watcher["lock"]:
        watcher_service.state.watcher["handler"] = handler
    handler._pending.add(str(changed))
    handler._fire()

    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        with handler._active_process_lock:
            if handler._active_process is not None:
                break
        time.sleep(0.01)
    started = time.monotonic()
    assert handler.shutdown(timeout=3)
    assert time.monotonic() - started < 5
    with watcher_service.state.watcher["lock"]:
        assert watcher_service.state.watcher["job_status"] == "cancelled"
        assert watcher_service.state.watcher["runs_cancelled"] >= 1
        watcher_service.state.watcher["handler"] = None


def test_watcher_status_exposes_last_job_cause(monkeypatch) -> None:
    monkeypatch.setattr(watcher_service, "_authorize_system", lambda _request: None)
    watcher = watcher_service.state.watcher
    with watcher["lock"]:
        previous = {key: value for key, value in watcher.items() if key != "lock"}
        watcher.update(
            {
                "observer": None,
                "paths": ["/knowledge"],
                "events_seen": 4,
                "started_at": 10.0,
                "job_status": "failed",
                "pending_events": 2,
                "active_root": None,
                "last_exit_code": 7,
                "last_error": "extractor failed",
                "last_stdout": "indexed 3 files",
                "last_stderr": "bad document",
                "runs_completed": 1,
                "runs_failed": 1,
                "runs_timed_out": 0,
                "runs_cancelled": 0,
            }
        )
    try:
        status = asyncio.run(watcher_service.watch_status(object()))
    finally:
        with watcher["lock"]:
            watcher.update(previous)

    assert status["job"]["status"] == "failed"
    assert status["job"]["pending_events"] == 2
    assert status["job"]["last_exit_code"] == 7
    assert status["job"]["last_error"] == "extractor failed"
    assert status["job"]["last_stderr"] == "bad document"


def test_watch_lifecycle_seeds_mirror_and_stops_worker(tmp_path, monkeypatch) -> None:
    source = tmp_path / "project"
    source.mkdir()
    (source / "notes.txt").write_text("knowledge", encoding="utf-8")
    local_sources = tmp_path / "local_sources"
    storage = tmp_path / "storage"
    storage.mkdir()
    collections_path = storage / "collections.json"
    collections_path.write_text(
        json.dumps({"collections": [{"id": "docs", "name": "Documents"}]}),
        encoding="utf-8",
    )

    class FakeObserver:
        def __init__(self):
            self.daemon = False
            self.alive = False
            self.scheduled: list[tuple[object, str, bool]] = []

        def schedule(self, handler, path, recursive=False):
            self.scheduled.append((handler, path, recursive))

        def start(self):
            self.alive = True

        def is_alive(self):
            return self.alive

        def stop(self):
            self.alive = False

        def join(self, timeout=None):
            return None

    monkeypatch.setattr(watcher_service, "_authorize_system", lambda _request: None)
    monkeypatch.setattr(watcher_service, "_watch_try_import", lambda: FakeObserver)
    monkeypatch.setattr(watcher_service.config, "LOCAL_SOURCES_DIR", str(local_sources))
    monkeypatch.setattr(watcher_service.config, "PERSIST_DIR", str(storage))
    monkeypatch.setattr(watcher_service.config, "COLLECTIONS_PATH", str(collections_path))

    result = watcher_service.watch_start(
        watcher_service.WatchStartRequest(paths=[str(source)], collection="docs"),
        object(),
    )
    status = asyncio.run(watcher_service.watch_status(object()))
    stopped = asyncio.run(watcher_service.watch_stop(object()))

    assert result["status"] == "started"
    assert status["running"] is True
    assert status["job"]["status"] == "idle"
    assert (local_sources / "collections" / "docs" / "watch-source" / "notes.txt").read_text(
        encoding="utf-8"
    ) == "knowledge"
    assert stopped == {"status": "stopped"}
    with watcher_service.state.watcher["lock"]:
        assert watcher_service.state.watcher["observer"] is None
        assert watcher_service.state.watcher["handler"] is None
