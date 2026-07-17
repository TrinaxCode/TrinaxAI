"""Shared PWA state services."""

from __future__ import annotations

# ruff: noqa: F405
from .shared_runtime import *  # noqa: F403


def _clear_directory_contents(path: str, *, preserve_names: frozenset[str] = frozenset()) -> list[str]:
    """Remove generated runtime contents from a project-owned directory."""
    removed: list[str] = []
    base = os.path.abspath(config.BASE_DIR)
    target = os.path.abspath(path)
    if target == base or not target.startswith(base + os.sep):
        raise HTTPException(status_code=500, detail=f"Refusing to clear unsafe path: {path}")
    if not os.path.isdir(target):
        return removed
    for name in os.listdir(target):
        if name in preserve_names:
            continue
        item = os.path.join(target, name)
        try:
            if os.path.isdir(item) and not os.path.islink(item):
                shutil.rmtree(item)
            else:
                os.remove(item)
            removed.append(os.path.relpath(item, config.BASE_DIR))
        except OSError as exc:
            LOG.warning("Could not remove reset target %s: %s", item, exc)
    return removed


def _stop_watcher_for_reset() -> None:
    watcher = state.watcher
    with watcher["lock"]:
        observer = watcher.get("observer")
        handler = watcher.get("handler")
    if observer is not None:
        try:
            observer.stop()
            observer.join(timeout=2)
        except Exception:
            LOG.debug("Best-effort operation failed", exc_info=True)
    if handler is not None and hasattr(handler, "shutdown"):
        try:
            handler.shutdown()
        except Exception:
            LOG.debug("Best-effort watcher worker shutdown failed", exc_info=True)
    with watcher["lock"]:
        if watcher.get("observer") is observer:
            watcher.update(
                {
                    "observer": None,
                    "handler": None,
                    "paths": [],
                    "started_at": None,
                    "events_seen": 0,
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


def _cancel_index_jobs_for_reset() -> None:
    with state.index_jobs_lock:
        for job in state.index_jobs.values():
            process = job.get("process")
            if process and process.poll() is None:
                try:
                    process.terminate()
                except Exception:
                    LOG.debug("Best-effort operation failed", exc_info=True)
        state.index_jobs.clear()


def _factory_reset_runtime_state(reset_state: dict[str, str]) -> dict[str, Any]:
    """Reset TrinaxAI to a fresh-installed local state without deleting code/.env."""

    _stop_watcher_for_reset()
    _cancel_index_jobs_for_reset()
    with state.engine_lock:
        state.fusion_retriever = None
        state.index_docstore = None
        state.vector_index = None
        state.known_projects = []
        _clear_index_runtime_caches()

    removed = []
    removed.extend(_clear_directory_contents(config.LOCAL_SOURCES_DIR))
    # The gateway/backend HMAC key is installation identity, not user state.
    # Keeping it avoids desynchronising the two processes after a factory reset
    # followed by a one-sided service restart.
    with state.app_state_lock:
        previous_document, _legacy = _read_app_state_document()
        removed.extend(
            _clear_directory_contents(
                config.PERSIST_DIR,
                preserve_names=frozenset({".proxy_secret", ".inference.lock"}),
            )
        )
        os.makedirs(config.PERSIST_DIR, exist_ok=True)
        # Never reuse a revision after reset: a pre-reset offline device with a
        # stale base revision must conflict instead of restoring deleted data.
        _write_app_state_document(
            {
                "revision": int(previous_document["revision"]) + 1,
                "values": reset_state,
            }
        )

    with state.collections_lock:
        _write_collections_unlocked([_default_collection()])

    return {
        "removed": removed,
        "indexed": False,
        "collections": [_default_collection()],
    }


_APP_STATE_SCHEMA_VERSION = 2


def _clean_app_state_values(values: object) -> dict[str, str]:
    if not isinstance(values, dict):
        return {}
    return {
        key: value
        for key, value in values.items()
        if isinstance(key, str) and key.startswith("tc-") and isinstance(value, str)
    }


def _read_app_state_document() -> tuple[dict[str, Any], bool]:
    """Read v2 state and detect legacy ``{tc-*: value}`` documents."""
    try:
        with open(APP_STATE_PATH, encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError):
        return {"schema_version": _APP_STATE_SCHEMA_VERSION, "revision": 0, "values": {}}, False

    if isinstance(raw, dict) and raw.get("schema_version") == _APP_STATE_SCHEMA_VERSION:
        revision = raw.get("revision", 0)
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
            revision = 0
        return {
            "schema_version": _APP_STATE_SCHEMA_VERSION,
            "revision": revision,
            "values": _clean_app_state_values(raw.get("values")),
        }, False

    # Version 1 stored the values directly at the document root.  It becomes
    # revision zero so the first version-aware mutation can use normal CAS.
    return {
        "schema_version": _APP_STATE_SCHEMA_VERSION,
        "revision": 0,
        "values": _clean_app_state_values(raw),
    }, True


def _read_app_state() -> dict[str, str]:
    """Compatibility helper used by services that only need current values."""
    document, _legacy = _read_app_state_document()
    return dict(document["values"])


def _write_app_state_document(document: dict[str, Any]) -> None:
    parent = os.path.dirname(APP_STATE_PATH) or "."
    os.makedirs(parent, exist_ok=True)
    payload = {
        "schema_version": _APP_STATE_SCHEMA_VERSION,
        "revision": int(document["revision"]),
        "values": _clean_app_state_values(document["values"]),
    }
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > APP_STATE_MAX_BYTES:
        raise HTTPException(status_code=413, detail="Shared app state is too large.")
    tmp = f"{APP_STATE_PATH}.tmp-{uuid.uuid4().hex}"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(encoded)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, APP_STATE_PATH)
        try:
            directory_fd = os.open(parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError:
            # Windows and some filesystems do not support directory fsync.
            pass
    finally:
        try:
            os.remove(tmp)
        except FileNotFoundError:
            pass


def _write_app_state(values: dict[str, str]) -> None:
    """Replace all values as one new server revision (internal operations)."""
    current, _legacy = _read_app_state_document()
    _write_app_state_document(
        {
            "revision": int(current["revision"]) + 1,
            "values": values,
        }
    )


def _app_state_etag(revision: int) -> str:
    return f'"trinaxai-app-state-v2-{revision}"'


def _if_match_revision(request: Request) -> int | None:
    raw = (request.headers.get("if-match") or "").strip()
    if not raw:
        return None
    match = re.fullmatch(r'(?:W/)?"trinaxai-app-state-v2-(\d+)"', raw)
    if match:
        return int(match.group(1))
    if raw.isdigit():
        return int(raw)
    raise HTTPException(status_code=400, detail="Invalid If-Match app-state ETag.")


def _app_state_conflict(document: dict[str, Any]) -> JSONResponse:
    revision = int(document["revision"])
    return JSONResponse(
        {
            "ok": False,
            "error": "revision_conflict",
            "schema_version": _APP_STATE_SCHEMA_VERSION,
            "revision": revision,
            "values": document["values"],
        },
        status_code=409,
        headers={"ETag": _app_state_etag(revision), "Cache-Control": "no-cache"},
    )


async def app_state_get(request: Request):
    """Shared local PWA state for devices connected to this TrinaxAI host."""
    _authorize_system(request)
    with state.app_state_lock:
        document, legacy = _read_app_state_document()
        if legacy:
            _write_app_state_document(document)
        revision = int(document["revision"])
        etag = _app_state_etag(revision)
        headers = {"ETag": etag, "Cache-Control": "no-cache"}
        if request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers=headers)
        return JSONResponse(
            {
                "ok": True,
                "schema_version": _APP_STATE_SCHEMA_VERSION,
                "revision": revision,
                "values": document["values"],
            },
            headers=headers,
        )


async def app_state_put(req: AppStateRequest, request: Request):
    """Apply explicit mutations using server-revision optimistic concurrency."""
    _authorize_system(request)
    with state.app_state_lock:
        document, legacy = _read_app_state_document()
        if legacy:
            _write_app_state_document(document)
        revision = int(document["revision"])
        header_revision = _if_match_revision(request)

        if req.operations is not None:
            expected_revision = req.base_revision
            if header_revision is not None and header_revision != expected_revision:
                raise HTTPException(status_code=400, detail="If-Match and base_revision disagree.")
        else:
            expected_revision = req.base_revision if req.base_revision is not None else header_revision
            # A legacy full-values merge without a revision is safe only for a
            # completely pristine store. Existing v1 state must first be read
            # and retried with the ETag returned by GET.
            if expected_revision is None and (revision != 0 or document["values"]):
                raise HTTPException(
                    status_code=428,
                    detail="Legacy app-state updates require If-Match or base_revision.",
                )
            expected_revision = 0 if expected_revision is None else expected_revision

        if expected_revision != revision:
            return _app_state_conflict(document)

        next_values = dict(document["values"])
        if req.operations is not None:
            for operation in req.operations:
                if operation.op == "set":
                    next_values[operation.key] = operation.value or ""
                else:
                    next_values.pop(operation.key, None)
        else:
            next_values.update(_clean_app_state_values(req.values))

        changed = next_values != document["values"]
        if changed:
            revision += 1
            document = {"revision": revision, "values": next_values}
            _write_app_state_document(document)
        return JSONResponse(
            {
                "ok": True,
                "schema_version": _APP_STATE_SCHEMA_VERSION,
                "revision": revision,
                "applied": changed,
            },
            headers={"ETag": _app_state_etag(revision), "Cache-Control": "no-cache"},
        )


async def app_state_delete(request: Request):
    """Factory-reset local TrinaxAI runtime state from the host machine."""
    _authorize_system(request)
    if request.headers.get("X-TrinaxAI-Confirm") != "reset-app-state":
        raise HTTPException(
            status_code=409,
            detail="Reset requires X-TrinaxAI-Confirm: reset-app-state.",
        )
    reset_state = {"tc-reset-at": str(time.time())}
    result = _factory_reset_runtime_state(reset_state)
    with state.app_state_lock:
        document, _legacy = _read_app_state_document()
    return {
        "ok": True,
        "schema_version": _APP_STATE_SCHEMA_VERSION,
        "revision": document["revision"],
        "values": reset_state,
        **result,
    }


__all__ = [name for name in globals() if not name.startswith("__")]
