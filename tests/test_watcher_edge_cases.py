from __future__ import annotations

import subprocess
import threading
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services import watcher_service as watcher
from app.services.engine_state import state


def _handler(tmp_path: Path) -> watcher._watch_Handler:
    handler = watcher._watch_Handler.__new__(watcher._watch_Handler)
    handler.paths = [str(tmp_path)]
    handler.mirror_roots = {}
    handler.collection_ids = {}
    handler.collection_names = {}
    handler.debounce_seconds = 0
    handler._timer = None
    handler._pending = set()
    handler._lock = threading.Lock()
    handler._queue_condition = threading.Condition()
    handler._queued = set()
    handler._stop_event = threading.Event()
    handler._busy_event = threading.Event()
    handler._active_process_lock = threading.Lock()
    handler._active_process = None
    handler._timeout_seconds = 1
    handler._output_limit = 1024
    handler._reload_timeout = 1
    return handler


def test_watcher_import_and_windows_process_termination(monkeypatch):
    observers = types.ModuleType("watchdog.observers")

    class Observer:
        pass

    observers.Observer = Observer
    watchdog_package = types.ModuleType("watchdog")
    watchdog_package.__path__ = []
    monkeypatch.setitem(__import__("sys").modules, "watchdog", watchdog_package)
    monkeypatch.setitem(__import__("sys").modules, "watchdog.observers", observers)
    assert watcher._watch_try_import() is Observer

    class Process:
        pid = 7

        def __init__(self, *, wait_timeout=False):
            self.wait_timeout = wait_timeout
            self.wait_calls = 0

        def poll(self):
            return None

        def wait(self, timeout=None):
            self.wait_calls += 1
            if self.wait_timeout and self.wait_calls == 1:
                raise subprocess.TimeoutExpired(["index"], timeout)
            if self.wait_timeout and self.wait_calls == 2:
                raise subprocess.TimeoutExpired(["index"], timeout)

    calls = []
    monkeypatch.setattr(watcher.os, "name", "nt")
    monkeypatch.setenv("SystemRoot", "C:\\Windows")
    monkeypatch.setattr(watcher.subprocess, "run", lambda *args, **kwargs: calls.append((args, kwargs)))
    watcher._terminate_process_tree(Process(wait_timeout=True), grace_seconds=0.01)
    assert len(calls) == 2
    assert calls[0][0][0][0].endswith("taskkill.exe")

    monkeypatch.setattr(watcher.subprocess, "run", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("gone")))
    watcher._terminate_process_tree(Process())

    proc = Process(wait_timeout=True)
    run_count = 0

    def fail_on_second(*_args, **_kwargs):
        nonlocal run_count
        run_count += 1
        if run_count == 2:
            raise OSError("gone")

    monkeypatch.setattr(watcher.subprocess, "run", fail_on_second)
    watcher._terminate_process_tree(proc)
    assert run_count == 2


def test_watcher_schedule_fire_and_queue_publication(monkeypatch, tmp_path):
    handler = _handler(tmp_path)

    class Timer:
        def __init__(self, delay, callback):
            self.delay = delay
            self.callback = callback
            self.daemon = False
            self.cancelled = False
            self.started = False

        def cancel(self):
            self.cancelled = True

        def start(self):
            self.started = True

    previous = Timer(0, lambda: None)
    handler._timer = previous
    monkeypatch.setattr(watcher.threading, "Timer", Timer)
    handler._schedule()
    assert previous.cancelled and handler._timer.started and handler._timer.daemon

    handler._stop_event.set()
    handler._schedule()
    handler._pending.add(str(tmp_path / "note.txt"))
    handler._stop_event.clear()
    handler._stop_event.is_set = lambda: False
    handler._pending.clear()
    handler._fire()
    handler._pending.add(str(tmp_path / "note.txt"))
    handler._fire()
    with handler._queue_condition:
        assert str(tmp_path / "note.txt") in handler._queued
    with state.watcher["lock"]:
        state.watcher["handler"] = object()
    handler._publish_queue_depth(1)
    handler._publish_result("/root", watcher._WatchRunResult(0), reload_ok=True)
    with state.watcher["lock"]:
        state.watcher["handler"] = None

    handler._pending.add(str(tmp_path / "later.txt"))

    class FlipEvent:
        values = iter([False, True])

        def is_set(self):
            return next(self.values)

    handler._stop_event = FlipEvent()
    handler._fire()
    handler._stop_event = threading.Event()


def test_watcher_path_grouping_mirror_security_and_cleanup(monkeypatch, tmp_path):
    handler = _handler(tmp_path / "root")
    root = tmp_path / "root"
    root.mkdir()
    target = tmp_path / "mirror"
    target.mkdir()

    original_commonpath = watcher.os.path.commonpath
    monkeypatch.setattr(watcher.os.path, "commonpath", lambda *_args: (_ for _ in ()).throw(ValueError("drive")))
    assert handler._events_by_root([str(root / "file")]) == {}
    handler._sync_mirror(str(root), str(target), [str(tmp_path / "outside" / "file")])
    monkeypatch.setattr(watcher.os.path, "commonpath", original_commonpath)
    handler._sync_mirror(str(root), str(target), [str(tmp_path / "outside" / "file")])

    linked = root / "linked"
    linked.symlink_to(root, target_is_directory=True)
    (target / "linked").write_text("stale", encoding="utf-8")
    handler._sync_mirror(str(root), str(target), [str(linked)])
    assert not (target / "linked").exists()

    changed_dir = root / "folder"
    changed_dir.mkdir()
    (changed_dir / "new.txt").write_text("new", encoding="utf-8")
    destination = target / "folder"
    destination.mkdir()
    (destination / "old.txt").write_text("old", encoding="utf-8")
    seeded = []
    monkeypatch.setattr(watcher, "_seed_watch_mirror", lambda source, dest: seeded.append((source, dest)))
    handler._sync_mirror(str(root), str(target), [str(changed_dir)])
    assert seeded

    link_destination = target / "folder-link"
    link_destination.symlink_to(target, target_is_directory=True)
    changed_link_dir = root / "folder-link"
    changed_link_dir.mkdir()
    handler._sync_mirror(str(root), str(target), [str(changed_link_dir)])
    assert not link_destination.is_symlink()

    file_path = root / "file.txt"
    file_path.write_text("x", encoding="utf-8")
    monkeypatch.setattr(watcher.shutil, "copy2", lambda *_args: (_ for _ in ()).throw(OSError("copy")))
    handler._sync_mirror(str(root), str(target), [str(file_path)])

    nonempty = target / "nonempty"
    nonempty.mkdir()
    (nonempty / "file").write_text("x", encoding="utf-8")
    handler._remove_empty_parents(str(nonempty), str(target))
    monkeypatch.setattr(watcher.os, "listdir", lambda *_args: (_ for _ in ()).throw(OSError("closed")))
    handler._remove_empty_parents(str(target / "missing"), str(target))


def test_watcher_batch_reload_and_error_paths(monkeypatch, tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    changed = root / "file.txt"
    changed.write_text("changed", encoding="utf-8")
    handler = _handler(root)
    published = []
    depths = []
    monkeypatch.setattr(handler, "_publish_queue_depth", depths.append)
    handler._process_batch([])
    assert depths == [0]

    handler._events_by_root = lambda pending: {str(root): [str(changed)]}
    handler._stop_event.set()
    handler._process_batch([str(changed)])
    handler._stop_event.clear()
    handler._sync_mirror = lambda *_args: None
    handler._run_indexer = lambda env: watcher._WatchRunResult(0)
    original_reload = watcher._watch_Handler._reload_engine.__get__(handler, type(handler))
    handler._reload_engine = lambda: (_ for _ in ()).throw(RuntimeError("reload"))
    handler._publish_result = lambda *args, **kwargs: published.append((args, kwargs))
    handler._process_batch([str(changed)])
    assert published

    handler._run_indexer = lambda env: watcher._WatchRunResult(2, stderr="index failed")
    handler._process_batch([str(changed)])

    handler._reload_engine = original_reload
    handler._reload_timeout = 0
    assert handler._reload_engine() is False
    handler._reload_timeout = 1
    handler._stop_event.clear()

    def lock_timeout(*_args, **_kwargs):
        handler._stop_event.set()
        raise TimeoutError("busy")

    monkeypatch.setattr(watcher, "exclusive_process_lock", lock_timeout)
    assert handler._reload_engine() is False


def test_watcher_indexer_windows_and_double_termination(monkeypatch, tmp_path):
    handler = _handler(tmp_path)

    class Process:
        pid = 11

        def __init__(self):
            self.polls = iter([0])

        def poll(self):
            return next(self.polls, 0)

    calls = {}
    monkeypatch.setattr(watcher.os, "name", "nt")
    monkeypatch.setattr(watcher.subprocess, "CREATE_NEW_PROCESS_GROUP", 512, raising=False)
    monkeypatch.setattr(
        watcher.subprocess, "Popen", lambda command, **kwargs: calls.update(command=command, kwargs=kwargs) or Process()
    )
    result = handler._run_indexer({"TEST": "1"})
    assert result.returncode == 0
    assert calls["kwargs"]["creationflags"] == 512

    class SlowProcess:
        pid = 12

        def __init__(self):
            self.polls = iter([None, None, 0, 0])

        def poll(self):
            return next(self.polls, 0)

    terminate_calls = []
    monkeypatch.setattr(watcher.subprocess, "Popen", lambda *_args, **_kwargs: SlowProcess())
    monkeypatch.setattr(watcher, "_terminate_process_tree", lambda process: terminate_calls.append(process))
    handler._stop_event.set()
    result = handler._run_indexer({})
    assert result.cancelled and len(terminate_calls) == 2


def test_watcher_shutdown_timer_ignore_hooks_and_seed_failure(monkeypatch, tmp_path):
    handler = _handler(tmp_path)

    class Timer:
        def __init__(self):
            self.cancelled = False

        def cancel(self):
            self.cancelled = True

    class Worker:
        def join(self, timeout=None):
            return None

        def is_alive(self):
            return False

    handler._timer = Timer()
    handler._pending.add("pending")
    handler._worker = Worker()
    with state.watcher["lock"]:
        state.watcher["handler"] = handler
        state.watcher["job_status"] = "idle"
    assert handler.shutdown() is True
    assert handler._timer is None
    with state.watcher["lock"]:
        state.watcher["handler"] = None

    monkeypatch.setattr(watcher.config, "LOCAL_SOURCES_DIR", "")
    monkeypatch.setattr(watcher.config, "PERSIST_DIR", str(tmp_path / "persist"))
    assert handler._ignored(str(tmp_path / "ordinary")) is False
    handler._ignored = lambda _path: True
    event = SimpleNamespace(src_path=str(tmp_path / "file"), dest_path=str(tmp_path / "dest"), is_directory=False)
    handler.on_created(event)
    handler.on_modified(SimpleNamespace(src_path=event.src_path, is_directory=True))
    handler.on_modified(event)
    handler.on_moved(event)
    handler.on_deleted(event)

    source = tmp_path / "seed"
    source.mkdir()
    (source / "file.txt").write_text("x", encoding="utf-8")
    monkeypatch.setattr(watcher.shutil, "copy2", lambda *_args: (_ for _ in ()).throw(OSError("copy")))
    watcher._seed_watch_mirror(str(source), str(tmp_path / "seed-target"))


def test_watcher_start_stale_handler_and_start_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(watcher, "_authorize_system", lambda _request: None)
    source = tmp_path / "source"
    source.mkdir()
    stopped = []

    class Stale:
        def shutdown(self):
            stopped.append("stale")
            return True

    class Handler:
        def __init__(self, *args, **kwargs):
            pass

        def shutdown(self):
            stopped.append("new")
            return True

    class Observer:
        def __init__(self):
            self.daemon = False

        def is_alive(self):
            return False

        def schedule(self, *args, **kwargs):
            return None

        def start(self):
            return None

    monkeypatch.setattr(watcher, "_watch_try_import", lambda: Observer)
    monkeypatch.setattr(watcher, "_watch_Handler", Handler)
    monkeypatch.setattr(watcher, "_prepare_watch_targets", lambda _req, paths: ({}, {}, {}))
    with state.watcher["lock"]:
        state.watcher["observer"] = None
        state.watcher["handler"] = Stale()
    result = watcher.watch_start(watcher.WatchStartRequest(paths=[str(source)]), object())
    assert result["status"] == "started" and "stale" in stopped
    watcher._watch_stop_sync()

    class FailingObserver(Observer):
        def schedule(self, *args, **kwargs):
            raise RuntimeError("schedule failed")

    monkeypatch.setattr(watcher, "_watch_try_import", lambda: FailingObserver)
    with state.watcher["lock"]:
        state.watcher["observer"] = None
        state.watcher["handler"] = None
    with pytest.raises(RuntimeError, match="schedule failed"):
        watcher.watch_start(watcher.WatchStartRequest(paths=[str(source)]), object())
    with state.watcher["lock"]:
        assert state.watcher["job_status"] == "failed"


def test_watcher_stop_handles_observer_and_worker_failures(monkeypatch):
    class Observer:
        def stop(self):
            raise RuntimeError("observer")

        def join(self, timeout=None):
            raise RuntimeError("observer")

    class Handler:
        def shutdown(self):
            return False

    with state.watcher["lock"]:
        state.watcher.update({"observer": Observer(), "handler": Handler(), "job_status": "running"})
    result = watcher._watch_stop_sync()
    assert result == {"status": "stopped"}
    with state.watcher["lock"]:
        assert state.watcher["job_status"] == "stopping"
        state.watcher["job_status"] = "idle"
