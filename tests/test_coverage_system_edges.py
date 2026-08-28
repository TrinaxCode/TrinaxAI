from __future__ import annotations

import builtins
import json
import queue
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.schemas import IndexImportDeleteRequest
from app.services import agent_service, system_service
from app.services.engine_state import state


def _upload(filename: str, payload: bytes) -> SimpleNamespace:
    chunks = iter((payload, b""))

    async def read(_size):
        return next(chunks)

    async def close():
        return None

    return SimpleNamespace(filename=filename, read=read, close=close)


def test_system_dispatch_and_shutdown_state_edges(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(state, "index_jobs", {})
    monkeypatch.setattr(system_service, "_persist_index_jobs_locked", lambda: None)
    was_stopping = state.lifecycle_stopping.is_set()
    state.lifecycle_stopping.clear()

    previous_active = state.index_active_job_id
    state.index_active_job_id = "job"
    system_service._release_index_slot("job", None)
    assert state.index_active_job_id is None

    state.index_active_job_id = "missing"
    system_service._dispatch_next_index_job()

    state.index_active_job_id = "active"
    state.index_jobs["active"] = {"status": "queued", "process": None}
    system_service._dispatch_next_index_job()
    assert state.index_active_job_id == "active"
    state.index_active_job_id = previous_active

    state.lifecycle_stopping.set()
    system_service._dispatch_next_index_job()
    if not was_stopping:
        state.lifecycle_stopping.clear()

    jobs_path = tmp_path / "index-jobs.json"
    jobs_path.write_text(json.dumps({"bad": "not-a-job"}), encoding="utf-8")
    monkeypatch.setattr(system_service.config, "INDEX_JOBS_PATH", str(jobs_path))
    system_service._restore_index_jobs()
    monkeypatch.setattr(system_service.config, "PERSIST_DIR", "/tmp/nonexistent-persist")
    assert system_service._external_indexer_pid() is None
    assert (
        system_service._progress_changes({"phase": "chunking", "files_total": 2, "files_processed": 1})["progress"]
        == 60
    )


def test_system_index_job_handles_finished_process_after_empty_output(monkeypatch) -> None:
    monkeypatch.setattr(state, "index_jobs", {})
    job = {
        "id": "empty-output",
        "status": "saving",
        "phase": "saving",
        "progress": 30,
        "cancel_requested": False,
        "output": "",
    }
    state.index_jobs[job["id"]] = job

    class EmptyQueue:
        def put(self, _value):
            pass

        def get(self, timeout=None):
            raise queue.Empty

    class Process:
        stdout = iter(())

        def __init__(self):
            self.poll_calls = 0

        def poll(self):
            self.poll_calls += 1
            return None if self.poll_calls == 1 else 1

        def wait(self, timeout=None):
            return 1

        def kill(self):
            pass

    monkeypatch.setattr(system_service.queue, "Queue", EmptyQueue)
    monkeypatch.setattr(system_service.threading, "Thread", lambda **_kwargs: SimpleNamespace(start=lambda: None))
    monkeypatch.setattr(system_service.subprocess, "Popen", lambda *_args, **_kwargs: Process())
    monkeypatch.setattr(system_service, "_job_run_is_current", lambda *_args: True)
    monkeypatch.setattr(system_service, "_update_index_job", lambda job_id, **changes: job.update(changes))
    monkeypatch.setattr(system_service, "_release_index_slot", lambda *_args: None)
    monkeypatch.setattr(system_service, "build_engine", lambda: False)
    monkeypatch.setattr(system_service, "_prune_old_jobs", lambda: None)
    monkeypatch.setattr(system_service.time, "monotonic", lambda: 0.0)
    monkeypatch.setattr(system_service.config, "INDEX_TOTAL_TIMEOUT", 999)
    monkeypatch.setattr(system_service.config, "INDEX_STAGE_TIMEOUT", 999)

    system_service._run_index_job(job["id"], "/tmp/docs")
    assert job["status"] == "failed"


@pytest.mark.asyncio
async def test_system_upload_and_mirror_error_edges(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(system_service, "_authorize_system", lambda _request: None)
    monkeypatch.setattr(system_service.config, "LOCAL_SOURCES_DIR", str(tmp_path / "sources"))
    monkeypatch.setattr(system_service.config, "PERSIST_DIR", str(tmp_path / "persist"))
    monkeypatch.setattr(system_service, "_ensure_collection", lambda _cid: {"id": "docs", "name": "Docs"})
    monkeypatch.setattr(system_service, "_safe_rel_path", lambda _filename: "../escape")
    monkeypatch.setattr(state, "index_jobs", {})
    monkeypatch.setattr(system_service, "_persist_index_jobs_locked", lambda: None)

    class Upload:
        filename = "note.txt"

        def __init__(self):
            self.chunks = iter((b"payload", b""))

        async def read(self, _size):
            return next(self.chunks)

        async def close(self):
            pass

    with pytest.raises(system_service.HTTPException, match="No indexable files"):
        await system_service.system_index_upload(
            object(),
            label="import",
            collection_id="docs",
            embed_model="",
            aggressive_quant=False,
            watch_id="",
            files=[Upload()],
        )

    target = tmp_path / "sources" / "collections" / "docs" / "watchers" / "watch-watch"
    target.mkdir(parents=True)
    stale = target / "stale.txt"
    stale.write_text("old", encoding="utf-8")
    monkeypatch.setattr(system_service, "_safe_rel_path", lambda filename: filename)
    monkeypatch.setattr(system_service, "_dispatch_next_index_job", lambda: None)
    real_remove = system_service.os.remove

    def fail_stale(path):
        if Path(path) == stale:
            raise OSError("locked")
        return real_remove(path)

    monkeypatch.setattr(system_service.os, "remove", fail_stale)
    result = await system_service.system_index_upload(
        object(),
        label="watch",
        collection_id="docs",
        embed_model="",
        aggressive_quant=False,
        watch_id="watch",
        files=[Upload()],
    )
    assert result["saved"] == 1


@pytest.mark.asyncio
async def test_system_retry_rejects_running_process(monkeypatch) -> None:
    monkeypatch.setattr(system_service, "_authorize_system", lambda _request: None)
    monkeypatch.setattr(
        state, "index_jobs", {"running": {"status": "failed", "process": SimpleNamespace(poll=lambda: None)}}
    )
    with pytest.raises(system_service.HTTPException, match="still running"):
        await system_service.system_retry_index_job(object(), "running")


def test_system_shutdown_and_self_test_handle_optional_failures(monkeypatch) -> None:
    monkeypatch.setattr(system_service, "_watch_stop_sync", lambda: None)
    monkeypatch.setattr(system_service, "_persist_index_jobs_locked", lambda: None)

    class StoppingProcess:
        pid = 123

        def poll(self):
            return None

        def terminate(self):
            raise OSError("already stopped")

    monkeypatch.setattr(
        state,
        "index_jobs",
        {
            "queued": {"status": "queued", "process": None},
            "active": {"status": "indexing", "process": StoppingProcess()},
        },
    )
    monkeypatch.setattr(agent_service, "shutdown_runtime", lambda: (_ for _ in ()).throw(RuntimeError("agent")))
    monkeypatch.setattr(system_service.os, "name", "nt")
    was_stopping = state.lifecycle_stopping.is_set()
    system_service.shutdown_runtime()
    assert state.index_jobs["queued"]["status"] == "cancelled"
    if not was_stopping:
        state.lifecycle_stopping.clear()

    class FailingClient:
        def __init__(self, **_kwargs):
            raise RuntimeError("offline")

    monkeypatch.setattr(system_service.httpx, "Client", FailingClient)
    monkeypatch.setattr(system_service, "_authorize_system", lambda _request: None)
    request = SimpleNamespace(app=SimpleNamespace(openapi=lambda: {"paths": {}}))
    result = system_service.system_self_test(request)
    assert result["results"]["ollama"] is False

    calls = []
    monkeypatch.setattr(system_service.sys, "platform", "linux")
    monkeypatch.setattr(system_service.subprocess, "Popen", lambda *_args, **kwargs: calls.append(kwargs))
    system_service._spawn_service_manager("manager.py", "stop-ai")
    assert calls[-1]["start_new_session"] is True


def test_system_index_job_propagates_popen_timeout_before_start(monkeypatch) -> None:
    monkeypatch.setattr(system_service, "_update_index_job", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(system_service, "_release_index_slot", lambda *_args: None)
    monkeypatch.setattr(
        system_service.subprocess,
        "Popen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(system_service.subprocess.TimeoutExpired("index", 1)),
    )
    with pytest.raises(system_service.subprocess.TimeoutExpired):
        system_service._run_index_job("timeout", "/tmp/docs")


@pytest.mark.asyncio
async def test_system_upload_duplicate_limits_and_delete_errors(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(system_service, "_authorize_system", lambda _request: None)
    monkeypatch.setattr(system_service.config, "LOCAL_SOURCES_DIR", str(tmp_path / "sources"))
    monkeypatch.setattr(system_service.config, "PERSIST_DIR", str(tmp_path / "persist"))
    monkeypatch.setattr(system_service, "_ensure_collection", lambda _cid: {"id": "docs", "name": "Docs"})
    monkeypatch.setattr(system_service, "_persist_index_jobs_locked", lambda: None)
    monkeypatch.setattr(system_service, "_dispatch_next_index_job", lambda: None)
    monkeypatch.setattr(state, "index_jobs", {})

    real_realpath = system_service.os.path.realpath
    collections_root = real_realpath(str(tmp_path / "sources" / "collections"))
    calls = 0

    def unsafe_realpath(path):
        nonlocal calls
        calls += 1
        return collections_root if calls == 1 else str(tmp_path / "outside")

    monkeypatch.setattr(system_service.os.path, "realpath", unsafe_realpath)
    with pytest.raises(HTTPException, match="Unsafe collection path"):
        await system_service.system_index_upload(
            object(),
            label="import",
            collection_id="docs",
            embed_model="",
            aggressive_quant=False,
            watch_id="",
            files=[_upload("note.txt", b"data")],
        )

    monkeypatch.setattr(system_service.os.path, "realpath", real_realpath)
    with pytest.raises(HTTPException, match="No indexable files"):
        await system_service.system_index_upload(
            object(),
            label="import",
            collection_id="docs",
            embed_model="",
            aggressive_quant=False,
            watch_id="",
            files=[_upload("", b"data")],
        )

    monkeypatch.setattr(system_service.config, "UPLOAD_MAX_BYTES", 1)
    monkeypatch.setattr(system_service.config, "max_file_bytes", lambda _path: 100)
    with pytest.raises(HTTPException) as too_large:
        await system_service.system_index_upload(
            object(),
            label="import",
            collection_id="docs",
            embed_model="",
            aggressive_quant=False,
            watch_id="",
            files=[_upload("note.txt", b"data")],
        )
    assert too_large.value.status_code == 413

    state.index_jobs.clear()
    digest = system_service.hashlib.sha256()
    digest.update(b"note.txt")
    digest.update(b"data")
    state.index_jobs["existing"] = {
        "id": "existing",
        "dedupe_key": f"docs:{digest.hexdigest()}",
        "status": "completed",
        "path": str(tmp_path / "existing"),
        "saved": 1,
        "skipped": 0,
        "bytes": 4,
        "projects": [],
        "collection_id": "docs",
        "collection_name": "Docs",
    }
    monkeypatch.setattr(system_service.config, "UPLOAD_MAX_BYTES", 100)
    duplicate = await system_service.system_index_upload(
        object(),
        label="import",
        collection_id="docs",
        embed_model="",
        aggressive_quant=False,
        watch_id="",
        files=[_upload("note.txt", b"data")],
    )
    assert duplicate["duplicate"] is True and duplicate["job_id"] == "existing"

    with pytest.raises(HTTPException, match="Missing import path"):
        await system_service.system_delete_index_import(
            IndexImportDeleteRequest(path="", collection_id="docs"), object()
        )

    target = Path(system_service.config.LOCAL_SOURCES_DIR) / "collections" / "docs" / "import"
    target.mkdir(parents=True)
    (target / "note.txt").write_text("data", encoding="utf-8")
    persist = Path(system_service.config.PERSIST_DIR)
    persist.mkdir(parents=True)
    (persist / "docstore.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        system_service,
        "_delete_indexed_rel_paths",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("index unavailable")),
    )
    with pytest.raises(HTTPException, match="Failed to delete indexed import"):
        await system_service.system_delete_index_import(
            IndexImportDeleteRequest(path=str(target), collection_id="docs"), object()
        )


def test_system_self_test_handles_optional_dependency_failures(monkeypatch) -> None:
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"models": [{"name": "model"}]}

    class Client:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def get(self, _url):
            return Response()

    monkeypatch.setattr(system_service, "_authorize_system", lambda _request: None)
    monkeypatch.setattr(system_service.httpx, "Client", Client)
    monkeypatch.setattr(
        system_service.Settings,
        "_embed_model",
        SimpleNamespace(get_text_embedding=lambda _text: [1.0]),
    )
    monkeypatch.setattr(
        state,
        "fusion_retriever",
        SimpleNamespace(retrieve=lambda _query: (_ for _ in ()).throw(RuntimeError("query failed"))),
    )
    original_import = builtins.__import__

    def blocked_import(name, *args, **kwargs):
        if name.split(".", 1)[0] in {"openpyxl", "pptx", "striprtf", "watchdog"}:
            raise ImportError(name)
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked_import)
    request = SimpleNamespace(
        app=SimpleNamespace(
            openapi=lambda: {
                "paths": {
                    "/v1/voice/capabilities": {},
                    "/v1/voice/stt": {},
                    "/v1/voice/tts": {},
                }
            }
        )
    )
    result = system_service.system_self_test(request)
    assert result["results"]["rag_indexed"] is True
    assert result["results"]["rag_query"] is False
    assert result["results"]["document_extractors"] is False
    assert result["results"]["watcher"] is False
