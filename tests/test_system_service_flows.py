from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, UploadFile

from app.schemas import IndexImportDeleteRequest
from app.services import system_service
from app.services.engine_state import state


@pytest.fixture
def isolated_jobs(monkeypatch):
    monkeypatch.setattr(system_service, "_persist_index_jobs_locked", lambda: None)
    with state.index_jobs_lock:
        previous = state.index_jobs
        state.index_jobs = {}
    previous_active = state.index_active_job_id
    state.index_active_job_id = None
    try:
        yield state.index_jobs
    finally:
        with state.index_jobs_lock:
            state.index_jobs = previous
        state.index_active_job_id = previous_active


@pytest.mark.asyncio
async def test_index_upload_saves_files_and_queues_background_index(tmp_path, monkeypatch, isolated_jobs) -> None:
    started = []

    class Thread:
        def __init__(self, *, target, args, **_kwargs):
            self.target = target
            self.args = args

        def start(self):
            started.append((self.target, self.args))

    monkeypatch.setattr(system_service, "_authorize_system", lambda _request: None)
    monkeypatch.setattr(system_service.config, "LOCAL_SOURCES_DIR", str(tmp_path))
    monkeypatch.setattr(system_service, "_ensure_collection", lambda _cid: {"id": "docs", "name": "Docs"})
    monkeypatch.setattr(system_service, "_external_indexer_pid", lambda: None)
    monkeypatch.setattr(system_service.threading, "Thread", Thread)
    upload = UploadFile(filename="../../manual?.md", file=BytesIO(b"release guide"))

    result = await system_service.system_index_upload(
        object(),
        label=" Release: Notes ",
        collection_id="docs",
        embed_model="",
        aggressive_quant=False,
        watch_id="",
        files=[upload],
    )

    assert result["saved"] == 1
    assert result["collection_id"] == "docs"
    assert Path(result["path"], "manual_.md").read_text(encoding="utf-8") == "release guide"
    assert started[0][0] is system_service._run_index_job
    assert isolated_jobs[result["job_id"]]["phase"] == "queued"


@pytest.mark.asyncio
async def test_index_upload_rejects_empty_and_oversized_batches(monkeypatch) -> None:
    monkeypatch.setattr(system_service, "_authorize_system", lambda _request: None)
    with pytest.raises(HTTPException) as empty:
        await system_service.system_index_upload(object(), files=[])
    assert empty.value.status_code == 400

    monkeypatch.setattr(system_service.config, "UPLOAD_MAX_FILES", 1)
    files = [
        UploadFile(filename="one.txt", file=BytesIO(b"one")),
        UploadFile(filename="two.txt", file=BytesIO(b"two")),
    ]
    with pytest.raises(HTTPException) as oversized:
        await system_service.system_index_upload(object(), files=files)
    assert oversized.value.status_code == 413


@pytest.mark.asyncio
async def test_delete_import_removes_only_managed_source_and_reloads(tmp_path, monkeypatch) -> None:
    root = tmp_path / "collections"
    target = root / "docs" / "manual"
    target.mkdir(parents=True)
    (target / "guide.md").write_text("guide", encoding="utf-8")
    deleted = []
    monkeypatch.setattr(system_service, "_authorize_system", lambda _request: None)
    monkeypatch.setattr(system_service.config, "LOCAL_SOURCES_DIR", str(tmp_path))
    monkeypatch.setattr(system_service.config, "PERSIST_DIR", str(tmp_path))
    (tmp_path / "docstore.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        system_service,
        "_delete_indexed_rel_paths",
        lambda collection, paths, source_id: deleted.append((collection, paths, source_id)) or 1,
    )
    monkeypatch.setattr(system_service, "source_id_for_root", lambda *_args, **_kwargs: "source-id")
    monkeypatch.setattr(system_service, "build_engine", lambda: True)

    result = await system_service.system_delete_index_import(
        IndexImportDeleteRequest(path=str(target), collection_id="docs"),
        object(),
    )

    assert result["deleted"] == 1
    assert result["removed_path"] is True
    assert deleted[0][:2] == ("docs", {"guide.md"})

    with pytest.raises(HTTPException) as unsafe:
        await system_service.system_delete_index_import(
            IndexImportDeleteRequest(path=str(tmp_path), collection_id="docs"),
            object(),
        )
    assert unsafe.value.status_code == 400


@pytest.mark.asyncio
async def test_lifecycle_routes_delegate_to_service_manager_and_engine(monkeypatch) -> None:
    spawned = []
    monkeypatch.setattr(system_service, "_authorize_system", lambda _request: None)
    monkeypatch.setattr(
        system_service, "_spawn_service_manager", lambda script, action: spawned.append((script, action))
    )
    monkeypatch.setattr(
        system_service.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="started", stderr=""),
    )
    monkeypatch.setattr(system_service, "build_engine", lambda: True)
    monkeypatch.setattr(state, "fusion_retriever", object())
    monkeypatch.setattr(state, "known_projects", ["project"])

    shutdown = await system_service.system_shutdown(object())
    startup = await system_service.system_startup(object())
    stopped = await system_service.system_stop_all(object())
    reloaded = await system_service.system_reload(object())

    assert shutdown["ok"] and stopped["ok"]
    assert startup == {"ok": True, "output": "started", "error": ""}
    assert reloaded == {"ok": True, "indexed": True, "projects": ["project"]}
    assert [action for _script, action in spawned] == ["stop-ai", "stop-all"]


def test_run_index_job_tracks_progress_and_completes(monkeypatch, isolated_jobs) -> None:
    class Process:
        stdout = iter(
            [
                'TRINAXAI_PROGRESS {"phase":"extracting","pages_total":2,"pages_processed":1,"determinate":true}\n',
                "Embeddings lote 1/1\n",
            ]
        )

        def poll(self):
            return 0

        def wait(self, timeout=None):
            return 0

        def terminate(self):
            raise AssertionError("successful job must not terminate")

        def kill(self):
            raise AssertionError("successful job must not be killed")

    class Thread:
        def __init__(self, *, target, **_kwargs):
            self.target = target

        def start(self):
            self.target()

    job = {
        "id": "job-run",
        "status": "saving",
        "phase": "saving",
        "progress": 2,
        "cancel_requested": False,
        "output": "",
    }
    isolated_jobs[job["id"]] = job
    monkeypatch.setattr(system_service.subprocess, "Popen", lambda *_args, **_kwargs: Process())
    monkeypatch.setattr(system_service.threading, "Thread", Thread)
    monkeypatch.setattr(system_service, "build_engine", lambda: True)
    monkeypatch.setattr(system_service, "_record_index_run", lambda: None)
    monkeypatch.setattr(system_service, "_prune_old_jobs", lambda: None)
    monkeypatch.setattr(state, "fusion_retriever", object())
    monkeypatch.setattr(state, "known_projects", ["docs"])

    system_service._run_index_job(job["id"], "/tmp/docs")

    assert job["status"] == "completed"
    assert job["progress"] == 100
    assert job["indexed"] is True
    assert "Embeddings lote" in job["output"]


def test_system_self_test_reports_available_core_capabilities(monkeypatch) -> None:
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"models": [{"name": "test"}]}

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
    monkeypatch.setattr(state, "fusion_retriever", SimpleNamespace(retrieve=lambda _query: [object()]))
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

    assert result["ok"] is True
    assert all(result["results"].values())


def test_index_job_persistence_restore_prune_and_public_helpers(tmp_path, monkeypatch) -> None:
    jobs_path = tmp_path / "jobs.json"
    monkeypatch.setattr(system_service.config, "INDEX_JOBS_PATH", str(jobs_path))
    monkeypatch.setattr(system_service.time, "time", lambda: 10_000)
    with state.index_jobs_lock:
        previous = state.index_jobs
        state.index_jobs = {
            "running": {"status": "indexing", "process": object(), "created_at": 1},
            "old": {"status": "completed", "process": None, "finished_at": 1},
            "fresh": {"status": "completed", "process": None, "finished_at": 9_999},
        }
    try:
        system_service._persist_index_jobs_locked()
        stored = json.loads(jobs_path.read_text(encoding="utf-8"))
        assert "process" not in stored["running"]

        state.index_jobs.clear()
        system_service._restore_index_jobs()
        assert state.index_jobs["running"]["phase"] == "interrupted"
        assert state.index_jobs["running"]["process"] is None
        system_service._prune_old_jobs()
        assert "old" not in state.index_jobs and "fresh" in state.index_jobs
    finally:
        with state.index_jobs_lock:
            state.index_jobs = previous

    assert system_service._safe_rel_path("../../a/../b?.md") == "a/b_.md"
    assert system_service._safe_rel_path("../..") is None
    assert system_service._safe_label(" .. ") == "import"
    assert system_service._estimate_index_seconds(0, 0) == 45
    assert system_service._structured_progress("noise") is None
    assert system_service._structured_progress("TRINAXAI_PROGRESS not-json") is None
    assert (
        system_service._progress_changes(
            {"phase": "embedding", "determinate": True, "batches_total": 4, "batches_processed": 2}
        )["progress"]
        == 76
    )


def test_collection_and_job_mutation_helpers(monkeypatch, isolated_jobs) -> None:
    collections = []
    monkeypatch.setattr(system_service, "_read_collections_unlocked", lambda: collections)
    monkeypatch.setattr(system_service, "_write_collections_unlocked", lambda items: collections.extend(items))
    monkeypatch.setattr(system_service, "_persist_index_jobs_locked", lambda: None)
    created = system_service._ensure_collection("docs", "Docs")
    assert created["id"] == "docs"
    assert system_service._ensure_collection("docs") is created

    job = system_service._new_index_job("Manual", "/tmp/manual", "docs", "Docs")
    system_service._update_index_job(job["id"], progress=50)
    system_service._append_index_output(job["id"], "indexed page\n")
    assert isolated_jobs[job["id"]]["progress"] == 50
    assert isolated_jobs[job["id"]]["recent_activity"] == "indexed page"
    system_service._update_index_job("missing", progress=1)
    system_service._append_index_output("missing", "ignored")

    public = system_service._job_public(
        {
            **isolated_jobs[job["id"]],
            "status": "saving",
            "progress": 10,
            "created_at": system_service.time.time() - 10,
        }
    )
    assert public["eta_seconds"] and public["elapsed_seconds"] >= 9


@pytest.mark.parametrize(
    ("line", "minimum", "phase"),
    [
        ("chunking documents", 45, "chunking"),
        ("Embeddings lote 2/4", 76, "embedding"),
        ("embedding started", 65, "embedding"),
        ("persisting index", 88, "saving_index"),
        ("completed", 96, "finishing"),
        ("other", 7, "indexing"),
    ],
)
def test_line_progress_states(line: str, minimum: int, phase: str) -> None:
    assert system_service._line_progress(line, 7) == (minimum, phase)


def test_run_index_job_handles_cancellation_failure_and_missing_stdout(monkeypatch, isolated_jobs) -> None:
    class Process:
        stdout = iter(())

        def __init__(self, code=0):
            self.code = code
            self.terminated = False
            self.killed = False

        def poll(self):
            return self.code

        def wait(self, timeout=None):
            return self.code

        def terminate(self):
            self.terminated = True

        def kill(self):
            self.killed = True

    class Thread:
        def __init__(self, *, target, **_kwargs):
            self.target = target

        def start(self):
            self.target()

    monkeypatch.setattr(system_service.threading, "Thread", Thread)
    monkeypatch.setattr(system_service, "_prune_old_jobs", lambda: None)
    monkeypatch.setattr(system_service, "_persist_index_jobs_locked", lambda: None)

    cancelled = Process()
    isolated_jobs["cancel"] = {
        "status": "saving",
        "progress": 2,
        "cancel_requested": True,
        "output": "",
    }
    monkeypatch.setattr(system_service.subprocess, "Popen", lambda *_args, **_kwargs: cancelled)
    system_service._run_index_job("cancel", "/tmp/docs")
    assert cancelled.terminated and isolated_jobs["cancel"]["status"] == "cancelled"

    failed = Process(code=3)
    isolated_jobs["failed"] = {
        "status": "saving",
        "phase": "saving",
        "progress": 2,
        "cancel_requested": False,
        "output": "",
    }
    monkeypatch.setattr(system_service.subprocess, "Popen", lambda *_args, **_kwargs: failed)
    system_service._run_index_job("failed", "/tmp/docs")
    assert isolated_jobs["failed"]["status"] == "failed"
    assert "code 3" in isolated_jobs["failed"]["error"]

    broken = Process()
    broken.stdout = None
    isolated_jobs["broken"] = {
        "status": "saving",
        "progress": 2,
        "cancel_requested": False,
        "output": "",
    }
    monkeypatch.setattr(system_service.subprocess, "Popen", lambda *_args, **_kwargs: broken)
    system_service._run_index_job("broken", "/tmp/docs")
    assert broken.killed and isolated_jobs["broken"]["phase"] == "failed"


@pytest.mark.asyncio
async def test_index_job_status_cancel_and_retry_contracts(tmp_path, monkeypatch, isolated_jobs) -> None:
    monkeypatch.setattr(system_service, "_authorize_system", lambda _request: None)
    monkeypatch.setattr(system_service, "_persist_index_jobs_locked", lambda: None)
    with pytest.raises(HTTPException) as missing:
        await system_service.system_index_job(object(), "missing")
    assert missing.value.status_code == 404

    class Process:
        terminated = False

        def poll(self):
            return None

        def terminate(self):
            self.terminated = True

    process = Process()
    target = tmp_path / "upload"
    target.mkdir()
    isolated_jobs["job"] = {
        "id": "job",
        "label": "job",
        "path": str(target),
        "status": "failed",
        "phase": "failed",
        "progress": 100,
        "process": process,
        "collection_id": "docs",
        "collection_name": "Docs",
        "created_at": system_service.time.time(),
    }
    cancelled = await system_service.system_cancel_index_job(object(), "job")
    assert cancelled["job"]["status"] == "cancelled" and process.terminated

    started = []

    class Thread:
        def __init__(self, *, target, args, **_kwargs):
            started.append((target, args))

        def start(self):
            return None

    monkeypatch.setattr(system_service.threading, "Thread", Thread)
    monkeypatch.setattr(system_service, "_external_indexer_pid", lambda: None)
    retried = await system_service.system_retry_index_job(object(), "job")
    assert retried["job"]["phase"] == "queued"
    assert started[0][0] is system_service._run_index_job
    assert started[0][1][4:] == (None, False, True, isolated_jobs["job"]["run_token"])

    isolated_jobs["job"]["status"] = "completed"
    with pytest.raises(HTTPException) as conflict:
        await system_service.system_retry_index_job(object(), "job")
    assert conflict.value.status_code == 409
    isolated_jobs["job"]["status"] = "failed"
    isolated_jobs["job"]["path"] = str(tmp_path / "gone")
    with pytest.raises(HTTPException):
        await system_service.system_retry_index_job(object(), "job")


def test_dispatcher_does_not_spawn_behind_an_external_index_lock(tmp_path, monkeypatch, isolated_jobs) -> None:
    lock = tmp_path / ".indexing.lock"
    lock.mkdir()
    (lock / "owner.json").write_text('{"pid": 123}', encoding="utf-8")
    monkeypatch.setattr(system_service.config, "PERSIST_DIR", str(tmp_path))
    monkeypatch.setattr(system_service, "_process_is_alive", lambda pid: pid == 123)
    started = []

    class Thread:
        def __init__(self, **kwargs):
            started.append(kwargs)

        def start(self):
            raise AssertionError("external lock must prevent a new indexer")

    monkeypatch.setattr(system_service.threading, "Thread", Thread)
    job = system_service._new_index_job("blocked", str(tmp_path / "upload"), "docs", "Docs")
    system_service._update_index_job(job["id"], status="queued", phase="queued")
    system_service._dispatch_next_index_job()

    assert not started
    assert isolated_jobs[job["id"]]["phase"] == "blocked"
    assert "PID 123" in isolated_jobs[job["id"]]["error"]


def test_system_helpers_cover_invalid_restore_eta_and_stale_runs(tmp_path, monkeypatch, isolated_jobs) -> None:
    jobs_path = tmp_path / "jobs.json"
    monkeypatch.setattr(system_service.config, "INDEX_JOBS_PATH", str(jobs_path))

    jobs_path.write_text("not-json", encoding="utf-8")
    system_service._restore_index_jobs()
    jobs_path.write_text("[]", encoding="utf-8")
    system_service._restore_index_jobs()

    job = system_service._new_index_job("job", str(tmp_path), "docs", "Docs")
    job["run_token"] = "current"
    assert system_service._job_run_is_current(job["id"], "current") is True
    assert system_service._job_run_is_current(job["id"], "stale") is False
    system_service._release_index_slot(job["id"], "stale")

    job.update(
        status="indexing",
        started_at=system_service.time.time() - 1,
        estimated_total_seconds=20,
        progress=40,
    )
    assert system_service._job_public(job)["eta_seconds"] is not None
    assert system_service._progress_changes({"phase": "chunking"})["progress_exact"] is False


def test_run_index_job_reports_total_and_stage_timeouts(monkeypatch, isolated_jobs) -> None:
    class Process:
        stdout = iter(())

        def __init__(self) -> None:
            self.terminated = False

        def poll(self):
            return None

        def terminate(self):
            self.terminated = True

        def wait(self, timeout=None):
            return 0

    total_process, stage_process = Process(), Process()
    processes = [total_process, stage_process]
    monkeypatch.setattr(system_service.subprocess, "Popen", lambda *_args, **_kwargs: processes.pop(0))
    monkeypatch.setattr(system_service, "build_engine", lambda: False)
    monkeypatch.setattr(system_service, "_persist_index_jobs_locked", lambda: None)

    for job_id in ("total", "stage"):
        isolated_jobs[job_id] = {
            "id": job_id,
            "status": "saving",
            "phase": "saving",
            "progress": 30,
            "cancel_requested": False,
            "output": "",
        }

    monkeypatch.setattr(system_service.config, "INDEX_TOTAL_TIMEOUT", 0)
    monkeypatch.setattr(system_service.config, "INDEX_STAGE_TIMEOUT", 999)
    ticks = iter((0.0, 1.0))
    monkeypatch.setattr(system_service.time, "monotonic", lambda: next(ticks))
    system_service._run_index_job("total", "/tmp/docs", embed_model="test-embed")
    assert isolated_jobs["total"]["phase"] == "timeout"
    assert total_process.terminated is True

    monkeypatch.setattr(system_service.config, "INDEX_TOTAL_TIMEOUT", 999)
    monkeypatch.setattr(system_service.config, "INDEX_STAGE_TIMEOUT", 0)
    ticks = iter((0.0, 1.0))
    monkeypatch.setattr(system_service.time, "monotonic", lambda: next(ticks))
    system_service._run_index_job("stage", "/tmp/docs")
    assert isolated_jobs["stage"]["phase"] == "timeout"
    assert stage_process.terminated is True


def test_run_index_job_handles_queue_empty_stale_token_and_wait_timeout(monkeypatch, isolated_jobs) -> None:
    class EmptyQueue:
        def put(self, _value):
            return None

        def get(self, timeout=None):
            raise system_service.queue.Empty

    class NoopThread:
        def __init__(self, **_kwargs):
            pass

        def start(self):
            return None

    class Process:
        stdout = iter(("progress\n",))

        def __init__(self, *, timeout=False) -> None:
            self.timeout = timeout
            self.terminated = False
            self.killed = False

        def poll(self):
            return 0

        def terminate(self):
            self.terminated = True

        def kill(self):
            self.killed = True

        def wait(self, timeout=None):
            if self.timeout and timeout is not None:
                raise system_service.subprocess.TimeoutExpired("index", timeout)
            return 0

    empty = Process(timeout=True)
    stale = Process()
    waited = Process(timeout=True)
    processes = [empty, stale, waited]
    monkeypatch.setattr(system_service.queue, "Queue", EmptyQueue)
    monkeypatch.setattr(system_service.threading, "Thread", NoopThread)
    monkeypatch.setattr(system_service.subprocess, "Popen", lambda *_args, **_kwargs: processes.pop(0))
    monkeypatch.setattr(system_service, "build_engine", lambda: False)
    monkeypatch.setattr(system_service, "_persist_index_jobs_locked", lambda: None)
    monkeypatch.setattr(system_service.time, "monotonic", lambda: 0.0)

    for job_id in ("empty", "stale", "waited"):
        isolated_jobs[job_id] = {
            "id": job_id,
            "status": "saving",
            "phase": "saving",
            "progress": 30,
            "cancel_requested": False,
            "output": "",
        }

    system_service._run_index_job("empty", "/tmp/docs")
    assert empty.killed is True

    class LineQueue(EmptyQueue):
        def get(self, timeout=None):
            return "progress\n"

    monkeypatch.setattr(system_service, "_job_run_is_current", lambda *_args: False)
    monkeypatch.setattr(system_service.queue, "Queue", LineQueue)
    system_service._run_index_job("stale", "/tmp/docs", run_token="stale-token")
    assert stale.terminated is True

    monkeypatch.undo()
    monkeypatch.setattr(system_service.queue, "Queue", EmptyQueue)
    monkeypatch.setattr(system_service.threading, "Thread", NoopThread)
    monkeypatch.setattr(system_service.subprocess, "Popen", lambda *_args, **_kwargs: waited)
    monkeypatch.setattr(system_service, "build_engine", lambda: False)
    monkeypatch.setattr(system_service.time, "monotonic", lambda: 0.0)
    system_service._run_index_job("waited", "/tmp/docs")
    assert waited.killed is True


def test_system_runtime_shutdown_spawn_upload_and_endpoint_error_edges(tmp_path, monkeypatch, isolated_jobs) -> None:
    written = []
    monkeypatch.setattr(system_service.config, "PERSIST_DIR", str(tmp_path))
    monkeypatch.setattr(system_service, "_read_usage_summary_unlocked", lambda: {"index_runs": 2})
    monkeypatch.setattr(system_service, "_write_usage_summary_unlocked", lambda value: written.append(value))
    system_service._record_index_run()
    assert written[-1]["index_runs"] == 3
    real_makedirs = system_service.os.makedirs
    monkeypatch.setattr(system_service.os, "makedirs", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError()))
    system_service._record_index_run()
    monkeypatch.setattr(system_service.os, "makedirs", real_makedirs)

    class Process:
        pid = 123

        def poll(self):
            return None

        def terminate(self):
            return None

    monkeypatch.setattr(system_service, "_watch_stop_sync", lambda: (_ for _ in ()).throw(RuntimeError()))
    monkeypatch.setattr(system_service, "_process_alive", lambda _process: True)
    monkeypatch.setattr(system_service.os, "name", "posix")
    monkeypatch.setattr(system_service.os, "getpgid", lambda _pid: 456, raising=False)
    killed = []
    monkeypatch.setattr(system_service.os, "killpg", lambda pgid, signal: killed.append((pgid, signal)), raising=False)
    monkeypatch.setattr(system_service, "_persist_index_jobs_locked", lambda: None)
    isolated_jobs["shutdown"] = {"process": Process(), "cancel_requested": False}
    was_stopping = state.lifecycle_stopping.is_set()
    try:
        system_service.shutdown_runtime()
    finally:
        if not was_stopping:
            state.lifecycle_stopping.clear()
    assert killed == [(456, 15)]

    class StartupInfo:
        dwFlags = 0
        wShowWindow = 0

    calls = []
    monkeypatch.setattr(system_service.sys, "platform", "win32")
    monkeypatch.setattr(system_service.subprocess, "STARTUPINFO", StartupInfo, raising=False)
    monkeypatch.setattr(system_service.subprocess, "STARTF_USESHOWWINDOW", 1, raising=False)
    monkeypatch.setattr(system_service.subprocess, "SW_HIDE", 0, raising=False)
    monkeypatch.setattr(system_service.subprocess, "Popen", lambda command, **kwargs: calls.append((command, kwargs)))
    system_service._spawn_service_manager("manager.py", "stop-all")
    assert calls[0][1]["startupinfo"].dwFlags == 1

    monkeypatch.setattr(system_service.sys, "platform", "linux")
    monkeypatch.setattr(system_service.config, "LOCAL_SOURCES_DIR", str(tmp_path))
    monkeypatch.setattr(system_service, "_ensure_collection", lambda _cid: {"id": "docs", "name": "Docs"})
    monkeypatch.setattr(system_service, "_dispatch_next_index_job", lambda: None)
    monkeypatch.setattr(system_service.config, "max_file_bytes", lambda _path: 1)
    monkeypatch.setattr(system_service.os, "remove", lambda _path: (_ for _ in ()).throw(OSError()))
    monkeypatch.setattr(system_service, "_authorize_system", lambda _request: None)
    import asyncio

    upload_result = asyncio.run(
        system_service.system_index_upload(
            object(),
            label="import",
            collection_id="docs",
            embed_model="",
            aggressive_quant=False,
            watch_id="",
            files=[UploadFile(filename="x.txt", file=BytesIO(b"xx"))],
        )
    )
    assert upload_result["saved"] == 1

    with state.index_jobs_lock:
        isolated_jobs["public"] = {"id": "public", "status": "completed", "progress": 100}
        isolated_jobs["cancel"] = {"id": "cancel", "status": "saving", "progress": 10, "process": None}
    assert asyncio.run(system_service.system_index_job(object(), "public"))["id"] == "public"
    with pytest.raises(HTTPException) as missing_cancel:
        asyncio.run(system_service.system_cancel_index_job(object(), "missing-cancel"))
    assert missing_cancel.value.status_code == 404

    class Hanging:
        def __init__(self):
            self.calls = 0

        def poll(self):
            return None

        def terminate(self):
            return None

        def kill(self):
            self.killed = True

        def wait(self, timeout=None):
            self.calls += 1
            if timeout and self.calls == 1:
                raise system_service.subprocess.TimeoutExpired("index", timeout)
            return 0

    isolated_jobs["cancel"]["process"] = Hanging()
    monkeypatch.setattr(system_service, "_release_index_slot", lambda *_args: None)
    cancelled = asyncio.run(system_service.system_cancel_index_job(object(), "cancel"))
    assert cancelled["job"]["status"] == "cancelled"

    with pytest.raises(HTTPException) as missing_retry:
        asyncio.run(system_service.system_retry_index_job(object(), "missing-retry"))
    assert missing_retry.value.status_code == 404
