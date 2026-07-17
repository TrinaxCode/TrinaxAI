"""Filesystem watcher services."""

from __future__ import annotations

import signal
from dataclasses import dataclass

# ruff: noqa: F405
from .shared_runtime import *  # noqa: F403

_watch_lifecycle_lock = threading.Lock()


def _watch_try_import():
    """Return Observer or None if watchdog is missing."""
    try:
        from watchdog.observers import Observer  # type: ignore

        return Observer
    except Exception:
        return None


def _watch_default_paths(collection: str | None) -> list[str]:
    """Return the original source directories configured for indexing."""
    roots: list[str] = []
    for candidate in config.PROJECTS_DIRS:
        if candidate and os.path.isdir(candidate):
            roots.append(candidate)
    # Deduplicate while keeping order.
    seen: set[str] = set()
    out: list[str] = []
    for r in roots:
        ap = os.path.abspath(r)
        if ap not in seen:
            seen.add(ap)
            out.append(ap)
    return out


@dataclass(frozen=True)
class _WatchRunResult:
    """Bounded result captured from one watcher-owned index subprocess."""

    returncode: int | None
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float = 0.0
    timed_out: bool = False
    cancelled: bool = False


def _tail_stream(stream, limit: int) -> str:
    """Return at most ``limit`` bytes from the end of a temporary stream."""
    try:
        stream.flush()
        stream.seek(0, os.SEEK_END)
        size = stream.tell()
        stream.seek(max(0, size - limit))
        return stream.read(limit).decode("utf-8", errors="replace").strip()
    except (OSError, ValueError):
        return ""


def _terminate_process_tree(process, *, grace_seconds: float = 2.0) -> None:
    """Terminate the watcher subprocess group, then kill it if necessary."""
    if process.poll() is not None:
        return
    try:
        if os.name == "posix":
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        elif hasattr(signal, "CTRL_BREAK_EVENT"):
            process.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            process.terminate()
    except (OSError, ProcessLookupError):
        return
    try:
        process.wait(timeout=grace_seconds)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        if os.name == "posix":
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        elif os.name == "nt":
            taskkill = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "taskkill.exe")
            subprocess.run(  # noqa: S603 - fixed Windows system binary and argv
                [taskkill, "/PID", str(process.pid), "/T", "/F"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=grace_seconds,
            )
        else:
            process.kill()
    except (OSError, ProcessLookupError, subprocess.TimeoutExpired):
        return
    try:
        process.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        LOG.error("Watcher index process %s could not be killed", process.pid)


class _watch_Handler(_WDFileSystemEventHandler):
    """Debounce events and feed one cancellable, coalescing index worker."""

    def __init__(
        self,
        paths: list[str],
        *,
        mirror_roots: dict[str, str] | None = None,
        collection_ids: dict[str, str] | None = None,
        collection_names: dict[str, str] | None = None,
        debounce_seconds: float = 2.0,
    ):
        self.paths = paths
        self.mirror_roots = mirror_roots or {}
        self.collection_ids = collection_ids or {}
        self.collection_names = collection_names or {}
        self.debounce_seconds = debounce_seconds
        self._timer: threading.Timer | None = None
        self._pending: set[str] = set()
        self._lock = threading.Lock()
        self._queue_condition = threading.Condition()
        self._queued: set[str] = set()
        self._stop_event = threading.Event()
        self._busy_event = threading.Event()
        self._active_process_lock = threading.Lock()
        self._active_process = None
        self._timeout_seconds = config._env_float(
            "TRINAXAI_WATCH_INDEX_TIMEOUT",
            1800.0,
            minimum=1.0,
            maximum=86400.0,
        )
        self._output_limit = config._env_int(
            "TRINAXAI_WATCH_OUTPUT_MAX_BYTES",
            16384,
            minimum=1024,
            maximum=1024 * 1024,
        )
        self._reload_timeout = config._env_float(
            "TRINAXAI_WATCH_RELOAD_TIMEOUT",
            30.0,
            minimum=1.0,
            maximum=300.0,
        )
        self._worker = threading.Thread(
            target=self._worker_loop,
            name="trinaxai-watch-index-worker",
            daemon=True,
        )
        self._worker.start()

    def _schedule(self) -> None:
        with self._lock:
            if self._stop_event.is_set():
                return
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self.debounce_seconds, self._fire)
            self._timer.daemon = True
            self._timer.start()

    def _fire(self) -> None:
        with self._lock:
            pending = sorted(self._pending)
            self._pending.clear()
            self._timer = None
        if not pending or self._stop_event.is_set():
            return
        with state.watcher["lock"]:
            state.watcher["events_seen"] += len(pending)
        with self._queue_condition:
            if self._stop_event.is_set():
                return
            self._queued.update(pending)
            queued_count = len(self._queued)
            self._queue_condition.notify()
        self._publish_queue_depth(queued_count)

    def _publish_queue_depth(self, queued_count: int) -> None:
        with state.watcher["lock"]:
            if state.watcher.get("handler") not in (None, self):
                return
            state.watcher["pending_events"] = queued_count
            if queued_count and state.watcher.get("job_status") != "running":
                state.watcher["job_status"] = "queued"

    def _publish_result(self, root: str, result: _WatchRunResult, *, reload_ok: bool) -> None:
        finished_at = time.time()
        if result.cancelled:
            status = "cancelled"
            error = result.stderr or "Indexing cancelled because the watcher stopped."
            counter = "runs_cancelled"
        elif result.timed_out:
            status = "timed_out"
            error = result.stderr or f"Indexing exceeded {self._timeout_seconds:.0f}s."
            counter = "runs_timed_out"
        elif result.returncode != 0:
            status = "failed"
            error = result.stderr or f"index.py exited with code {result.returncode}."
            counter = "runs_failed"
        elif not reload_ok:
            status = "failed"
            error = "Index was written, but the backend could not reload it."
            counter = "runs_failed"
        else:
            status = "succeeded"
            error = None
            counter = "runs_completed"
        with self._queue_condition:
            queued_count = len(self._queued)
        with state.watcher["lock"]:
            if state.watcher.get("handler") not in (None, self):
                return
            state.watcher.update(
                {
                    "job_status": status,
                    "pending_events": queued_count,
                    "active_root": None,
                    "last_finished_at": finished_at,
                    "last_duration_seconds": round(result.duration_seconds, 3),
                    "last_exit_code": result.returncode,
                    "last_error": error,
                    "last_stdout": result.stdout,
                    "last_stderr": result.stderr,
                }
            )
            state.watcher[counter] = int(state.watcher.get(counter, 0)) + 1

    def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            with self._queue_condition:
                self._queue_condition.wait_for(lambda: self._queued or self._stop_event.is_set())
                if self._stop_event.is_set():
                    return
                pending = sorted(self._queued)
                self._queued.clear()
                self._busy_event.set()
            try:
                self._process_batch(pending)
            finally:
                self._busy_event.clear()

    def _events_by_root(self, pending: list[str]) -> dict[str, list[str]]:
        grouped: dict[str, list[str]] = {}
        for changed in pending:
            changed_abs = os.path.abspath(changed)
            matches: list[str] = []
            for root in self.paths:
                try:
                    if os.path.commonpath([changed_abs, root]) == os.path.abspath(root):
                        matches.append(root)
                except ValueError:
                    continue
            if matches:
                root = max(matches, key=len)
                grouped.setdefault(root, []).append(changed_abs)
        return grouped

    def _collection_for_root(self, root: str, target_root: str) -> tuple[str, str]:
        collection_id = self.collection_ids.get(root, config.DEFAULT_COLLECTION_ID)
        collection_name = self.collection_names.get(root, config.DEFAULT_COLLECTION_NAME)
        collections_root = os.path.abspath(os.path.join(config.LOCAL_SOURCES_DIR, "collections"))
        if root == target_root and os.path.dirname(root) == collections_root:
            collection_id = os.path.basename(root)
            collection_name = next(
                (
                    item.get("name", collection_name)
                    for item in _read_collections_unlocked()
                    if item.get("id") == collection_id
                ),
                collection_name,
            )
        return collection_id, collection_name

    def _sync_mirror(self, root: str, target_root: str, changed_paths: list[str]) -> None:
        root_abs = os.path.abspath(root)
        root_real = os.path.realpath(root_abs)
        target_abs = os.path.abspath(target_root)
        for changed_abs in changed_paths:
            relative = os.path.relpath(changed_abs, root_abs)
            destination = os.path.abspath(os.path.join(target_abs, relative))
            try:
                if os.path.commonpath([destination, target_abs]) != target_abs:
                    continue
            except ValueError:
                continue
            try:
                if destination == changed_abs:
                    continue
                if os.path.lexists(changed_abs):
                    changed_real = os.path.realpath(changed_abs)
                    if os.path.islink(changed_abs) or os.path.commonpath([changed_real, root_real]) != root_real:
                        LOG.warning("Watcher refused symlink or escaped path %s", changed_abs)
                        if os.path.lexists(destination):
                            os.remove(destination)
                        continue
                    if os.path.isdir(changed_abs):
                        if os.path.isdir(destination) and not os.path.islink(destination):
                            shutil.rmtree(destination)
                        elif os.path.lexists(destination):
                            os.remove(destination)
                        os.makedirs(destination, exist_ok=True)
                        _seed_watch_mirror(changed_abs, destination)
                    else:
                        os.makedirs(os.path.dirname(destination), exist_ok=True)
                        shutil.copy2(changed_abs, destination)
                elif os.path.lexists(destination):
                    if os.path.isdir(destination) and not os.path.islink(destination):
                        shutil.rmtree(destination)
                    else:
                        os.remove(destination)
                    self._remove_empty_parents(os.path.dirname(destination), target_abs)
            except (OSError, ValueError) as exc:
                LOG.warning("Watcher mirror failed for %s: %s", changed_abs, exc)

    @staticmethod
    def _remove_empty_parents(parent: str, target_root: str) -> None:
        while parent.startswith(target_root + os.sep):
            try:
                if os.listdir(parent):
                    return
                os.rmdir(parent)
            except OSError:
                return
            parent = os.path.dirname(parent)

    def _process_batch(self, pending: list[str]) -> None:
        grouped = self._events_by_root(pending)
        if not grouped:
            self._publish_queue_depth(0)
            return
        for root, changed_paths in grouped.items():
            if self._stop_event.is_set():
                return
            target_root = self.mirror_roots.get(root, root)
            collection_id, collection_name = self._collection_for_root(root, target_root)
            self._sync_mirror(root, target_root, changed_paths)
            os.makedirs(target_root, exist_ok=True)
            env = {
                **os.environ,
                "TRINAXAI_INDEX_DIR": target_root,
                "TRINAXAI_COLLECTION_ID": collection_id,
                "TRINAXAI_COLLECTION_NAME": collection_name,
                "TRINAXAI_INDEX_APPEND": "0",
            }
            with state.watcher["lock"]:
                if state.watcher.get("handler") in (None, self):
                    state.watcher.update(
                        {
                            "job_status": "running",
                            "active_root": target_root,
                            "last_started_at": time.time(),
                            "last_error": None,
                        }
                    )
            result = self._run_indexer(env)
            reload_ok = False
            if result.returncode == 0 and not result.cancelled and not result.timed_out:
                try:
                    reload_ok = self._reload_engine()
                except Exception:
                    LOG.exception("Watcher index reload failed for %s", target_root)
            elif result.stderr:
                LOG.error("Watcher reindex failed for %s: %s", target_root, result.stderr)
            self._publish_result(target_root, result, reload_ok=reload_ok)

    def _reload_engine(self) -> bool:
        """Reload after acquiring the index lock with a bounded, cancellable wait."""
        deadline = time.monotonic() + self._reload_timeout
        lock_path = os.path.join(config.PERSIST_DIR, ".indexing.lock")
        while not self._stop_event.is_set():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                LOG.error("Watcher index reload timed out after %.1fs", self._reload_timeout)
                return False
            try:
                with exclusive_process_lock(
                    lock_path,
                    timeout=min(0.5, remaining),
                    poll_interval=0.1,
                ):
                    return bool(build_engine(acquire_process_lock=False))
            except TimeoutError:
                continue
        return False

    def _run_indexer(self, env: dict[str, str]) -> _WatchRunResult:
        command = [sys.executable, os.path.join(config.BASE_DIR, "index.py")]
        started = time.monotonic()
        with tempfile.TemporaryFile(mode="w+b") as stdout, tempfile.TemporaryFile(mode="w+b") as stderr:
            kwargs: dict[str, Any] = {
                "stdout": stdout,
                "stderr": stderr,
                "env": env,
            }
            if os.name == "posix":
                kwargs["start_new_session"] = True
            elif hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
                kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
            try:
                process = subprocess.Popen(command, **kwargs)
            except Exception as exc:
                return _WatchRunResult(
                    returncode=None,
                    stderr=str(exc),
                    duration_seconds=time.monotonic() - started,
                )
            with self._active_process_lock:
                self._active_process = process
            timed_out = False
            cancelled = False
            deadline = started + self._timeout_seconds
            try:
                while process.poll() is None:
                    if self._stop_event.wait(0.1):
                        cancelled = True
                        _terminate_process_tree(process)
                        break
                    if time.monotonic() >= deadline:
                        timed_out = True
                        _terminate_process_tree(process)
                        break
                if process.poll() is None:
                    _terminate_process_tree(process)
                if self._stop_event.is_set():
                    cancelled = True
            finally:
                with self._active_process_lock:
                    if self._active_process is process:
                        self._active_process = None
            duration = time.monotonic() - started
            return _WatchRunResult(
                returncode=process.poll(),
                stdout=_tail_stream(stdout, self._output_limit),
                stderr=_tail_stream(stderr, self._output_limit),
                duration_seconds=duration,
                timed_out=timed_out,
                cancelled=cancelled,
            )

    def wait_for_idle(self, timeout: float = 10.0) -> bool:
        """Wait until no process or queued event remains (primarily for tests)."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._queue_condition:
                queued = bool(self._queued)
            with self._active_process_lock:
                active = self._active_process is not None
            if not queued and not active and not self._busy_event.is_set():
                return True
            time.sleep(0.01)
        return False

    def shutdown(self, timeout: float = 5.0) -> bool:
        """Cancel debounce, queued work and the active subprocess, then join."""
        self._stop_event.set()
        with self._lock:
            had_work = bool(self._pending) or self._timer is not None
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
            self._pending.clear()
        with self._queue_condition:
            had_work = had_work or bool(self._queued) or self._busy_event.is_set()
            self._queued.clear()
            self._queue_condition.notify_all()
        self._worker.join(timeout=timeout)
        stopped = not self._worker.is_alive()
        if had_work:
            with state.watcher["lock"]:
                if (
                    state.watcher.get("handler") in (None, self)
                    and state.watcher.get("job_status") not in {"cancelled", "timed_out"}
                ):
                    state.watcher["job_status"] = "cancelled"
                    state.watcher["pending_events"] = 0
                    state.watcher["active_root"] = None
                    state.watcher["last_finished_at"] = time.time()
                    state.watcher["last_error"] = "Indexing cancelled because the watcher stopped."
                    state.watcher["runs_cancelled"] = int(state.watcher.get("runs_cancelled", 0)) + 1
        return stopped

    def _ignored(self, path: str) -> bool:
        """Ignore generated mirrors and runtime state inside a source root."""
        absolute = os.path.abspath(path)
        ignored_roots = [config.LOCAL_SOURCES_DIR, config.PERSIST_DIR]
        for ignored_root in ignored_roots:
            if not ignored_root:
                continue
            ignored_abs = os.path.abspath(ignored_root)
            inside_ignored = absolute == ignored_abs or absolute.startswith(ignored_abs + os.sep)
            if not inside_ignored:
                continue
            explicitly_watched = any(
                absolute == os.path.abspath(root) or absolute.startswith(os.path.abspath(root) + os.sep)
                for root in self.paths
                if os.path.abspath(root) == ignored_abs or os.path.abspath(root).startswith(ignored_abs + os.sep)
            )
            if not explicitly_watched:
                return True
        return False

    # watchdog hooks
    def on_created(self, event):  # noqa: D401
        if self._ignored(event.src_path):
            return
        with self._lock:
            self._pending.add(event.src_path)
        self._schedule()

    def on_modified(self, event):
        if getattr(event, "is_directory", False) or self._ignored(event.src_path):
            return
        with self._lock:
            self._pending.add(event.src_path)
        self._schedule()

    def on_moved(self, event):
        dest = getattr(event, "dest_path", "") or event.src_path
        if self._ignored(event.src_path) or self._ignored(dest):
            return
        with self._lock:
            self._pending.add(event.src_path)
            self._pending.add(dest)
        self._schedule()

    def on_deleted(self, event):
        if self._ignored(event.src_path):
            return
        with self._lock:
            self._pending.add(event.src_path)
        self._schedule()


def _watch_paths(req: WatchStartRequest) -> list[str]:
    candidates = [path for path in (req.paths or []) if path] or _watch_default_paths(req.collection)
    paths = [
        os.path.abspath(os.path.expandvars(os.path.expanduser(path)))
        for path in candidates
        if os.path.isdir(os.path.expandvars(os.path.expanduser(path)))
        and not os.path.islink(os.path.expandvars(os.path.expanduser(path)))
    ]
    return list(dict.fromkeys(paths))


def _seed_watch_mirror(source_root: str, target_root: str) -> None:
    """Copy a source snapshot without following symlinks or runtime roots."""
    local_sources = os.path.abspath(config.LOCAL_SOURCES_DIR)
    persist_root = os.path.abspath(config.PERSIST_DIR)
    for dirpath, dirnames, filenames in os.walk(source_root):
        dirnames[:] = [
            name
            for name in dirnames
            if not name.startswith(".")
            and not os.path.islink(os.path.join(dirpath, name))
            and not os.path.abspath(os.path.join(dirpath, name)).startswith(local_sources + os.sep)
            and not os.path.abspath(os.path.join(dirpath, name)).startswith(persist_root + os.sep)
        ]
        relative_dir = os.path.relpath(dirpath, source_root)
        destination_dir = target_root if relative_dir == "." else os.path.join(target_root, relative_dir)
        os.makedirs(destination_dir, exist_ok=True)
        for filename in filenames:
            source_file = os.path.join(dirpath, filename)
            if filename.startswith(".") or os.path.islink(source_file):
                continue
            try:
                shutil.copy2(source_file, os.path.join(destination_dir, filename))
            except OSError as exc:
                LOG.warning("Could not seed watcher mirror %s: %s", source_file, exc)


def _prepare_watch_targets(
    req: WatchStartRequest,
    paths: list[str],
) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    collections_root = os.path.abspath(os.path.join(config.LOCAL_SOURCES_DIR, "collections"))
    collection_name_by_id = {
        item.get("id"): item.get("name", item.get("id", ""))
        for item in _read_collections_unlocked()
        if item.get("id")
    }
    mirror_roots: dict[str, str] = {}
    collection_ids: dict[str, str] = {}
    collection_names: dict[str, str] = {}
    for source_root in paths:
        collection_id = sanitize_collection_id(req.collection, fallback=config.DEFAULT_COLLECTION_ID)
        collection_name = collection_name_by_id.get(collection_id, config.DEFAULT_COLLECTION_NAME)
        if os.path.dirname(source_root) == collections_root:
            collection_id = os.path.basename(source_root)
            collection_name = collection_name_by_id.get(collection_id, config.DEFAULT_COLLECTION_NAME)
            target_root = source_root
        else:
            target_root = os.path.join(collections_root, collection_id, "watch-source")
            os.makedirs(target_root, exist_ok=True)
            with state.watcher["lock"]:
                state.watcher["active_root"] = source_root
            _seed_watch_mirror(source_root, target_root)
        mirror_roots[source_root] = target_root
        collection_ids[source_root] = collection_id
        collection_names[source_root] = collection_name
    return mirror_roots, collection_ids, collection_names


def _reset_watch_job_state() -> None:
    state.watcher.update(
        {
            "job_status": "idle",
            "pending_events": 0,
            "active_root": None,
            "last_started_at": None,
            "last_finished_at": None,
            "last_duration_seconds": None,
            "last_exit_code": None,
            "last_error": None,
            "last_stdout": "",
            "last_stderr": "",
            "runs_completed": 0,
            "runs_failed": 0,
            "runs_timed_out": 0,
            "runs_cancelled": 0,
        }
    )


def watch_start(req: WatchStartRequest, request: Request):
    """Start one observer and one coalescing index worker."""
    _authorize_system(request)
    Observer = _watch_try_import()
    if Observer is None:
        raise HTTPException(status_code=501, detail="watchdog is not installed. Run: pip install watchdog")
    with _watch_lifecycle_lock:
        with state.watcher["lock"]:
            current_observer = state.watcher["observer"]
            if current_observer is not None and current_observer.is_alive():
                return {
                    "status": "already_running",
                    "watching": list(state.watcher["paths"]),
                    "pid": os.getpid(),
                }
            stale_handler = state.watcher.get("handler")
            state.watcher.update(
                {
                    "observer": None,
                    "handler": None,
                    "paths": [],
                    "started_at": None,
                }
            )
        if stale_handler is not None and hasattr(stale_handler, "shutdown"):
            stale_handler.shutdown()
        with state.watcher["lock"]:
            _reset_watch_job_state()
            state.watcher.update(
                {
                    "job_status": "preparing",
                    "active_root": None,
                    "last_started_at": time.time(),
                    "last_error": None,
                }
            )
        paths = _watch_paths(req)
        if not paths:
            with state.watcher["lock"]:
                state.watcher.update({"job_status": "failed", "last_error": "No valid directories to watch."})
            raise HTTPException(status_code=400, detail="No valid directories to watch.")
        with state.watcher["lock"]:
            state.watcher["paths"] = paths
        try:
            mirror_roots, collection_ids, collection_names = _prepare_watch_targets(req, paths)
            handler = _watch_Handler(
                paths,
                mirror_roots=mirror_roots,
                collection_ids=collection_ids,
                collection_names=collection_names,
            )
            observer = Observer()
            for path in paths:
                observer.schedule(handler, path, recursive=True)
            observer.daemon = True
            observer.start()
        except Exception as exc:
            if "handler" in locals():
                handler.shutdown()
            with state.watcher["lock"]:
                state.watcher.update({"job_status": "failed", "active_root": None, "last_error": str(exc)})
            raise
        with state.watcher["lock"]:
            state.watcher["observer"] = observer
            state.watcher["handler"] = handler
            state.watcher["paths"] = paths
            state.watcher["started_at"] = time.time()
            state.watcher["events_seen"] = 0
            _reset_watch_job_state()
        return {"status": "started", "watching": paths, "pid": os.getpid()}


def _watch_stop_sync() -> dict[str, str]:
    with _watch_lifecycle_lock:
        with state.watcher["lock"]:
            observer = state.watcher["observer"]
            handler = state.watcher.get("handler")
            if observer is None and handler is None:
                state.watcher["paths"] = []
                state.watcher["started_at"] = None
                state.watcher["active_root"] = None
                return {"status": "not_running"}
        if observer is not None:
            try:
                observer.stop()
                observer.join(timeout=2)
            except Exception:
                LOG.debug("Best-effort operation failed", exc_info=True)
        worker_stopped = True
        if handler is not None and hasattr(handler, "shutdown"):
            worker_stopped = bool(handler.shutdown())
        with state.watcher["lock"]:
            if state.watcher.get("observer") is observer and state.watcher.get("handler") is handler:
                state.watcher["observer"] = None
                state.watcher["handler"] = None
                state.watcher["paths"] = []
                state.watcher["started_at"] = None
                state.watcher["pending_events"] = 0
                state.watcher["active_root"] = None
                if not worker_stopped:
                    state.watcher["job_status"] = "stopping"
        return {"status": "stopped"}


async def watch_stop(request: Request):
    """Stop the observer and cancel its active subprocess off the event loop."""
    _authorize_system(request)
    return await run_in_threadpool(_watch_stop_sync)


async def watch_status(request: Request):
    """Report the watcher's current state."""
    _authorize_system(request)
    with state.watcher["lock"]:
        observer = state.watcher["observer"]
        running = observer is not None and observer.is_alive()
        return {
            "running": running,
            "watching": list(state.watcher["paths"]),
            "events_seen": int(state.watcher["events_seen"]),
            "started_at": state.watcher["started_at"],
            "job": {
                "status": state.watcher.get("job_status", "idle"),
                "pending_events": int(state.watcher.get("pending_events", 0)),
                "active_root": state.watcher.get("active_root"),
                "last_started_at": state.watcher.get("last_started_at"),
                "last_finished_at": state.watcher.get("last_finished_at"),
                "last_duration_seconds": state.watcher.get("last_duration_seconds"),
                "last_exit_code": state.watcher.get("last_exit_code"),
                "last_error": state.watcher.get("last_error"),
                "last_stdout": state.watcher.get("last_stdout", ""),
                "last_stderr": state.watcher.get("last_stderr", ""),
                "runs_completed": int(state.watcher.get("runs_completed", 0)),
                "runs_failed": int(state.watcher.get("runs_failed", 0)),
                "runs_timed_out": int(state.watcher.get("runs_timed_out", 0)),
                "runs_cancelled": int(state.watcher.get("runs_cancelled", 0)),
            },
        }


__all__ = [name for name in globals() if not name.startswith("__")]
