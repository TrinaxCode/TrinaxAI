"""Privileged lifecycle and indexing services."""

from __future__ import annotations

import hashlib
import queue
import re

import httpx

# ruff: noqa: F405
from .shared_runtime import *  # noqa: F403


def _persist_index_jobs_locked() -> None:
    os.makedirs(config.PERSIST_DIR, exist_ok=True)
    payload = {job_id: {k: v for k, v in job.items() if k != "process"} for job_id, job in state.index_jobs.items()}
    tmp = f"{config.INDEX_JOBS_PATH}.tmp"
    with open(tmp, "w", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
    os.replace(tmp, config.INDEX_JOBS_PATH)


def _restore_index_jobs() -> None:
    try:
        with open(config.INDEX_JOBS_PATH, encoding="utf-8") as stream:
            stored = json.load(stream)
    except (OSError, ValueError):
        return
    if not isinstance(stored, dict):
        return
    now = time.time()
    with state.index_jobs_lock:
        for job_id, raw in stored.items():
            if not isinstance(raw, dict):
                continue
            job = {**raw, "id": str(job_id), "process": None}
            if job.get("status") in {"saving", "indexing"}:
                job.update(
                    status="failed",
                    phase="interrupted",
                    error="The backend restarted while this job was running. Retry the job.",
                    finished_at=now,
                )
            state.index_jobs[str(job_id)] = job


_restore_index_jobs()


def _prune_old_jobs() -> None:
    """Remove completed/cancelled/failed index jobs older than 1 hour."""
    now = time.time()
    with state.index_jobs_lock:
        stale = [jid for jid, j in state.index_jobs.items() if j.get("finished_at") and (now - j["finished_at"]) > 3600]
        for jid in stale:
            del state.index_jobs[jid]
        if stale:
            _persist_index_jobs_locked()


def _safe_rel_path(filename: str) -> str | None:
    cleaned = filename.replace("\\", "/").lstrip("/")
    parts = []
    for raw in cleaned.split("/"):
        if raw in {"", ".", ".."}:
            continue
        part = _SAFE_SEGMENT.sub("_", raw).strip()
        if part:
            parts.append(part[:120])
    if not parts:
        return None
    return os.path.join(*parts)


def _safe_label(label: str) -> str:
    label = _SAFE_SEGMENT.sub("_", label).strip(" ._")
    return (label or "import")[:80]


def _ensure_collection(collection_id: str | None, name: str | None = None) -> dict:
    cid = sanitize_collection_id(
        collection_id,
        fallback=config.DEFAULT_COLLECTION_ID,
    )
    with state.collections_lock:
        collections = _read_collections_unlocked()
        for item in collections:
            if item["id"] == cid:
                return item
        now = time.time()
        created = {
            "id": cid,
            "name": (name or cid).strip()[:80] or cid,
            "created_at": now,
            "updated_at": now,
        }
        collections.append(created)
        _write_collections_unlocked(collections)
        return created


def _new_index_job(label: str, target: str, collection_id: str, collection_name: str) -> dict:
    now = time.time()
    job = {
        "id": uuid.uuid4().hex,
        "label": label,
        "path": target,
        "status": "saving",
        "phase": "saving",
        "progress": 2,
        "saved": 0,
        "skipped": 0,
        "bytes": 0,
        "output": "",
        "error": "",
        "projects": [],
        "collection_id": collection_id,
        "collection_name": collection_name,
        "indexed": False,
        "created_at": now,
        "updated_at": now,
        "started_at": None,
        "finished_at": None,
        "cancel_requested": False,
        "process": None,
        "pages_total": None,
        "pages_processed": 0,
        "chunks_generated": 0,
        "batches_total": None,
        "batches_processed": 0,
        "progress_exact": True,
        "recent_activity": "Upload job created",
    }
    with state.index_jobs_lock:
        state.index_jobs[job["id"]] = job
        _persist_index_jobs_locked()
    return job


def _update_index_job(job_id: str, **changes) -> None:
    with state.index_jobs_lock:
        job = state.index_jobs.get(job_id)
        if not job:
            return
        job.update(changes)
        job["updated_at"] = time.time()
        _persist_index_jobs_locked()


def _append_index_output(job_id: str, text: str) -> None:
    with state.index_jobs_lock:
        job = state.index_jobs.get(job_id)
        if not job:
            return
        job["output"] = (job.get("output", "") + text)[-8000:]
        job["updated_at"] = time.time()
        job["recent_activity"] = text.strip()[-300:]
        _persist_index_jobs_locked()


def _estimate_index_seconds(saved: int, total_bytes: int) -> int:
    mb = max(0.1, total_bytes / (1024 * 1024))
    # Local Ollama indexing cost is dominated by embeddings, not upload speed.
    # This deliberately favors a stable countdown over a volatile percent-based ETA.
    return int(max(45, min(1800, 35 + saved * 18 + mb * 12)))


def _job_public(job: dict) -> dict:
    now = time.time()
    started = job.get("started_at") or job.get("created_at") or now
    elapsed = max(0, now - started)
    progress = max(0, min(100, int(job.get("progress") or 0)))
    eta = None
    if job.get("status") == "saving" and 5 < progress < 30:
        eta = max(1, int(elapsed * (100 - progress) / progress))
    elif job.get("status") in {"indexing", "saving"} and job.get("estimated_total_seconds"):
        remaining = int(float(job["estimated_total_seconds"]) - elapsed)
        eta = remaining if remaining > 0 else None
    return {
        "id": job["id"],
        "label": job.get("label", ""),
        "path": job.get("path", ""),
        "status": job.get("status", "unknown"),
        "phase": job.get("phase", "unknown"),
        "progress": progress,
        "eta_seconds": eta,
        "elapsed_seconds": int(elapsed),
        "saved": job.get("saved", 0),
        "skipped": job.get("skipped", 0),
        "bytes": job.get("bytes", 0),
        "indexed": bool(job.get("indexed")),
        "projects": job.get("projects", []),
        "collection_id": job.get("collection_id", config.DEFAULT_COLLECTION_ID),
        "collection_name": job.get("collection_name", config.DEFAULT_COLLECTION_NAME),
        "output": job.get("output", ""),
        "error": job.get("error", ""),
        "cancel_requested": bool(job.get("cancel_requested")),
        "created_at": job.get("created_at"),
        "updated_at": job.get("updated_at"),
        "finished_at": job.get("finished_at"),
        "pages_total": job.get("pages_total"),
        "pages_processed": job.get("pages_processed", 0),
        "chunks_generated": job.get("chunks_generated", 0),
        "batches_total": job.get("batches_total"),
        "batches_processed": job.get("batches_processed", 0),
        "progress_exact": bool(job.get("progress_exact", False)),
        "recent_activity": job.get("recent_activity", ""),
    }


# index.py emits one "Embeddings lote N/M..." line per batch (see
# _emit_embed_progress). Embeddings dominate wall-clock, so we map that N/M
# across the bulk of the bar (65→88) instead of jumping to a flat 65 and
# stalling there while tqdm redraws a carriage-return bar the supervisor cannot
# see.
_EMBED_BATCH_RE = re.compile(r"lote\s+(\d+)\s*/\s*(\d+)")
_EMBED_PROGRESS_START = 65
_EMBED_PROGRESS_END = 88


def _line_progress(line: str, current: int) -> tuple[int, str]:
    lower = line.lower()
    if "troceando" in lower or "chunk" in lower:
        return max(current, 45), "chunking"
    batch_match = _EMBED_BATCH_RE.search(lower)
    if batch_match and "lote" in lower:
        done, total = int(batch_match.group(1)), int(batch_match.group(2))
        if total > 0:
            span = _EMBED_PROGRESS_END - _EMBED_PROGRESS_START
            mapped = _EMBED_PROGRESS_START + int(span * min(done, total) / total)
            return max(current, mapped), "embedding"
    if "embedding" in lower or "embed" in lower or "indexando" in lower:
        return max(current, _EMBED_PROGRESS_START), "embedding"
    if "persist" in lower or "guard" in lower or "publicando" in lower:
        return max(current, 88), "saving_index"
    if "complet" in lower or "done" in lower:
        return max(current, 96), "finishing"
    return current, "indexing"


def _structured_progress(line: str) -> dict | None:
    prefix = "TRINAXAI_PROGRESS "
    if not line.startswith(prefix):
        return None
    try:
        event = json.loads(line[len(prefix) :])
    except ValueError:
        return None
    return event if isinstance(event, dict) and isinstance(event.get("phase"), str) else None


def _progress_changes(event: dict) -> dict:
    phase = event["phase"]
    changes = {"phase": phase, "progress_exact": bool(event.get("determinate")), "recent_activity": phase}
    for key in ("pages_total", "pages_processed", "chunks_generated", "batches_total", "batches_processed"):
        if isinstance(event.get(key), int):
            changes[key] = max(0, event[key])
    if phase == "extracting" and changes.get("pages_total"):
        changes["progress"] = 30 + int(25 * changes.get("pages_processed", 0) / changes["pages_total"])
    elif phase == "chunking":
        changes["progress"] = 60
        changes["progress_exact"] = False
    elif phase == "embedding" and changes.get("batches_total"):
        changes["progress"] = 65 + int(23 * changes.get("batches_processed", 0) / changes["batches_total"])
    return changes


def _run_index_job(
    job_id: str,
    target: str,
    collection_id: str = config.DEFAULT_COLLECTION_ID,
    collection_name: str = config.DEFAULT_COLLECTION_NAME,
    embed_model: str | None = None,
    aggressive_quant: bool = False,
    append_only: bool = True,
) -> None:
    env = {
        **os.environ,
        "TRINAXAI_INDEX_DIR": target,
        "TRINAXAI_COLLECTION_ID": _collection_slug(collection_id),
        "TRINAXAI_COLLECTION_NAME": collection_name,
        "TRINAXAI_INDEX_APPEND": "1" if append_only else "0",
        "TRINAXAI_AGGRESSIVE_QUANT": "1" if aggressive_quant else "0",
    }
    if embed_model:
        env["TRINAXAI_EMBED"] = embed_model
    _update_index_job(job_id, status="indexing", phase="starting", progress=30, started_at=time.time())
    process = subprocess.Popen(
        [sys.executable, os.path.join(config.BASE_DIR, "index.py")],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        bufsize=1,
        env=env,
    )
    _update_index_job(job_id, process=process)
    try:
        if process.stdout is None:
            raise RuntimeError("subprocess stdout is None — Popen was not configured with PIPE")
        lines: queue.Queue[str | None] = queue.Queue()

        def read_output() -> None:
            try:
                for output_line in process.stdout:
                    lines.put(output_line)
            finally:
                lines.put(None)

        threading.Thread(target=read_output, daemon=True, name=f"trinaxai-index-output-{job_id[:8]}").start()
        job_started = last_activity = time.monotonic()
        timeout_error = ""
        while True:
            with state.index_jobs_lock:
                job = state.index_jobs.get(job_id)
                cancelled = bool(job and job.get("cancel_requested"))
                current = int(job.get("progress", 30)) if job else 30
            if cancelled:
                process.terminate()
                break
            now = time.monotonic()
            if now - job_started > config.INDEX_TOTAL_TIMEOUT:
                timeout_error = f"Total indexing timeout after {config.INDEX_TOTAL_TIMEOUT}s"
                process.terminate()
                break
            if now - last_activity > config.INDEX_STAGE_TIMEOUT:
                timeout_error = f"Stage '{job.get('phase', 'unknown') if job else 'unknown'}' timed out after {config.INDEX_STAGE_TIMEOUT}s without activity"
                process.terminate()
                break
            try:
                line = lines.get(timeout=1)
            except queue.Empty:
                if process.poll() is not None:
                    break
                continue
            if line is None:
                break
            last_activity = time.monotonic()
            _append_index_output(job_id, line)
            event = _structured_progress(line)
            if event:
                _update_index_job(job_id, **_progress_changes(event))
            else:
                progress, phase = _line_progress(line, current)
                _update_index_job(job_id, progress=progress, phase=phase, progress_exact=False)
        code = process.wait(timeout=20)
        if timeout_error:
            _update_index_job(
                job_id, status="failed", phase="timeout", error=timeout_error, progress=100, finished_at=time.time()
            )
            return
    except subprocess.TimeoutExpired:
        process.kill()
        code = process.wait()
    except Exception as exc:
        process.kill()
        _update_index_job(
            job_id,
            status="failed",
            phase="failed",
            error=str(exc),
            progress=100,
            finished_at=time.time(),
            process=None,
        )
        return
    finally:
        _update_index_job(job_id, process=None)

    with state.index_jobs_lock:
        job = state.index_jobs.get(job_id)
        cancelled = bool(job and job.get("cancel_requested"))

    if cancelled:
        _update_index_job(
            job_id,
            status="cancelled",
            phase="cancelled",
            progress=100,
            finished_at=time.time(),
        )
        return
    if code != 0:
        with state.index_jobs_lock:
            failed_job = state.index_jobs.get(job_id) or {}
            detail = str(failed_job.get("recent_activity") or "").strip()
        _update_index_job(
            job_id,
            status="failed",
            phase="failed",
            error=f"Indexing failed during {failed_job.get('phase', 'indexing')}: {detail or f'index.py exited with code {code}'}",
            progress=100,
            finished_at=time.time(),
        )
        return

    ok = build_engine()
    _prune_old_jobs()
    if ok:
        _record_index_run()
    _update_index_job(
        job_id,
        status="completed" if ok else "failed",
        phase="completed" if ok else "reload_failed",
        progress=100,
        indexed=state.fusion_retriever is not None,
        projects=state.known_projects,
        finished_at=time.time(),
    )


def _record_index_run() -> None:
    """Bump the persisted ``index_runs`` counter after a successful index build.

    Fire-and-forget; never raises. Without this, the ``index_runs`` field
    surfaced by ``/v1/stats`` stayed permanently at 0. / Incrementa el contador
    ``index_runs`` que expone ``/v1/stats`` tras un indexado correcto.
    """
    try:
        os.makedirs(config.PERSIST_DIR, exist_ok=True)
        with state.usage_lock:
            summary = _read_usage_summary_unlocked() or _empty_usage_summary()
            summary["index_runs"] = int(summary.get("index_runs") or 0) + 1
            _write_usage_summary_unlocked(summary)
    except Exception:
        LOG.debug("Best-effort operation failed", exc_info=True)


def _spawn_service_manager(script: str, action: str) -> None:
    kwargs: dict[str, Any] = {
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = (
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
        kwargs["startupinfo"] = startupinfo
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(
        [sys.executable, script, action, "--base-dir", config.BASE_DIR],
        **kwargs,
    )


async def system_shutdown(request: Request):
    """Stop the AI backend (Ollama services) while keeping the PWA available.

    Detiene el backend de IA (servicios de Ollama) manteniendo la PWA activa.
    """
    _authorize_system(request)
    script = os.path.join(config.BASE_DIR, "service_manager.py")
    _spawn_service_manager(script, "stop-ai")
    return {
        "ok": True,
        "output": "AI shutdown initiated. The PWA remains available for restart.",
    }


async def system_startup(request: Request):
    """Start the AI backend services and return the launcher's output.

    Inicia los servicios del backend de IA y devuelve la salida del lanzador.
    """
    _authorize_system(request)
    script = os.path.join(config.BASE_DIR, "service_manager.py")
    result = await run_in_threadpool(
        lambda: subprocess.run(
            [sys.executable, script, "start-ai", "--base-dir", config.BASE_DIR],
            capture_output=True,
            text=True,
            timeout=60,
        )
    )
    return {
        "ok": result.returncode == 0,
        "output": result.stdout,
        "error": result.stderr,
    }


async def system_stop_all(request: Request):
    """Stop the entire TrinaxAI stack, including the PWA/API service.

    Detiene toda la pila de TrinaxAI, incluido el servicio de la PWA/API.
    """
    _authorize_system(request)
    script = os.path.join(config.BASE_DIR, "service_manager.py")
    _spawn_service_manager(script, "stop-all")
    return {"ok": True, "output": "Full TrinaxAI shutdown initiated."}


async def system_reload(request: Request):
    """Recarga el índice tras index.py, sin reiniciar el servicio."""
    _authorize_system(request)
    ok = await run_in_threadpool(build_engine)
    return {
        "ok": ok,
        "indexed": state.fusion_retriever is not None,
        "projects": state.known_projects,
    }


async def system_index_upload(
    request: Request,
    label: str = Form("import"),
    collection_id: str = Form(config.DEFAULT_COLLECTION_ID),
    embed_model: str = Form(""),
    aggressive_quant: bool = Form(False),
    watch_id: str = Form(""),
    files: list[UploadFile] = File(...),
):
    """Importa una carpeta elegida en el navegador y la indexa localmente.

    Los navegadores no exponen la ruta absoluta de una carpeta por seguridad.
    Por eso copiamos los archivos enviados a local_sources/imports/<label-ts>
    y ejecutamos el indexador sobre esa copia local.
    """
    _authorize_system(request)
    if not files:
        raise HTTPException(status_code=400, detail="No files received.")
    if len(files) > config.UPLOAD_MAX_FILES:
        raise HTTPException(
            status_code=413,
            detail=f"Too many files. Limit: {config.UPLOAD_MAX_FILES}.",
        )

    stamp = time.strftime("%Y%m%d-%H%M%S")
    safe_collection_id = sanitize_collection_id(
        collection_id,
        fallback=config.DEFAULT_COLLECTION_ID,
    )
    collection = _ensure_collection(safe_collection_id)
    safe_label = _safe_label(label)
    safe_watch_id = _safe_label(watch_id) if watch_id.strip() else ""
    collections_root = os.path.realpath(os.path.join(config.LOCAL_SOURCES_DIR, "collections"))
    target = os.path.realpath(
        os.path.join(
            collections_root,
            collection["id"],
            "watchers" if safe_watch_id else "",
            f"{safe_label}-{safe_watch_id}" if safe_watch_id else f"{safe_label}-{stamp}",
        )
    )
    try:
        if os.path.commonpath([target, collections_root]) != collections_root:
            raise ValueError("unsafe upload path")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Unsafe collection path.") from exc
    os.makedirs(target, exist_ok=True)
    job = _new_index_job(safe_label, target, collection["id"], collection["name"])

    saved = 0
    skipped = 0
    total_bytes = 0
    incoming_paths: set[str] = set()
    upload_digest = hashlib.sha256()
    for upload in files:
        rel = _safe_rel_path(upload.filename or "")
        if not rel:
            skipped += 1
            continue
        incoming_paths.add(os.path.normpath(rel))
        dest = os.path.abspath(os.path.join(target, rel))
        if not dest.startswith(os.path.abspath(target) + os.sep):
            skipped += 1
            continue
        os.makedirs(os.path.dirname(dest), exist_ok=True)

        size = 0
        max_bytes = config.max_file_bytes(rel)
        with open(dest, "wb") as out:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    skipped += 1
                    out.close()
                    try:
                        os.remove(dest)
                    except OSError:
                        pass
                    break
                out.write(chunk)
                upload_digest.update(rel.encode("utf-8", "replace"))
                upload_digest.update(chunk)
                total_bytes += len(chunk)
                if total_bytes > config.UPLOAD_MAX_BYTES:
                    _update_index_job(
                        job["id"],
                        status="failed",
                        phase="upload_limit",
                        error="Upload size limit exceeded.",
                        progress=100,
                    )
                    shutil.rmtree(target, ignore_errors=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"Upload too large. Limit: {config.UPLOAD_MAX_BYTES} bytes.",
                    )
            else:
                pass
        await upload.close()
        if os.path.exists(dest):
            saved += 1
        _update_index_job(
            job["id"],
            saved=saved,
            skipped=skipped,
            bytes=total_bytes,
            progress=min(28, 4 + int(24 * saved / max(1, len(files)))),
        )

    if saved == 0:
        shutil.rmtree(target, ignore_errors=True)
        _update_index_job(
            job["id"],
            status="failed",
            phase="empty",
            error="No indexable files were saved.",
            progress=100,
            finished_at=time.time(),
        )
        raise HTTPException(status_code=400, detail="No indexable files were saved.")

    dedupe_key = f"{collection['id']}:{upload_digest.hexdigest()}"
    with state.index_jobs_lock:
        duplicate = next(
            (
                existing
                for existing in state.index_jobs.values()
                if existing.get("id") != job["id"]
                and existing.get("dedupe_key") == dedupe_key
                and existing.get("status") in {"saving", "indexing", "completed"}
            ),
            None,
        )
    if duplicate:
        shutil.rmtree(target, ignore_errors=True)
        _update_index_job(
            job["id"],
            status="cancelled",
            phase="duplicate",
            error=f"Duplicate of job {duplicate['id']}",
            progress=100,
            finished_at=time.time(),
        )
        return {
            "ok": True,
            "job_id": duplicate["id"],
            "duplicate": True,
            **{
                key: duplicate.get(key)
                for key in ("path", "saved", "skipped", "bytes", "projects", "collection_id", "collection_name")
            },
        }

    if safe_watch_id:
        # A watched folder is a mirror, so files deleted on the user's machine
        # must also disappear from local_sources before incremental indexing.
        for dirpath, _, filenames in os.walk(target):
            for filename in filenames:
                absolute = os.path.join(dirpath, filename)
                relative = os.path.normpath(os.path.relpath(absolute, target))
                if relative not in incoming_paths:
                    try:
                        os.remove(absolute)
                    except OSError:
                        pass

    _update_index_job(
        job["id"],
        saved=saved,
        skipped=skipped,
        bytes=total_bytes,
        phase="queued",
        progress=30,
        estimated_total_seconds=_estimate_index_seconds(saved, total_bytes),
        dedupe_key=dedupe_key,
    )
    threading.Thread(
        target=_run_index_job,
        args=(
            job["id"],
            target,
            collection["id"],
            collection["name"],
            (embed_model or "").strip() or None,
            bool(aggressive_quant),
            not bool(safe_watch_id),
        ),
        daemon=True,
        name=f"trinaxai-index-{job['id'][:8]}",
    ).start()
    return {
        "ok": True,
        "job_id": job["id"],
        "indexed": False,
        "path": target,
        "saved": saved,
        "skipped": skipped,
        "bytes": total_bytes,
        "projects": state.known_projects,
        "collection_id": collection["id"],
        "collection_name": collection["name"],
    }


async def system_delete_index_import(req: IndexImportDeleteRequest, request: Request):
    """Delete a browser-uploaded local source folder and its indexed chunks."""
    _authorize_system(request)
    raw_path = (req.path or "").strip()
    if not raw_path:
        raise HTTPException(status_code=400, detail="Missing import path.")
    root = os.path.abspath(os.path.join(config.LOCAL_SOURCES_DIR, "collections"))
    target = os.path.abspath(os.path.expanduser(raw_path))
    rel_to_root = os.path.relpath(target, root)
    parts = [] if rel_to_root in {".", ""} else rel_to_root.split(os.sep)
    if rel_to_root.startswith("..") or os.path.isabs(rel_to_root) or len(parts) < 2:
        raise HTTPException(status_code=400, detail="Refusing to delete unsafe import path.")
    collection_id = _collection_slug(req.collection_id or parts[0])
    rel_paths: set[str] = set()
    if os.path.isdir(target):
        for dirpath, _dirnames, filenames in os.walk(target):
            for filename in filenames:
                rel_paths.add(os.path.relpath(os.path.join(dirpath, filename), target).replace("\\", "/"))
    deleted = 0
    try:
        index_exists = os.path.exists(os.path.join(config.PERSIST_DIR, "docstore.json"))
        if rel_paths and index_exists:
            deleted = _delete_indexed_rel_paths(
                collection_id,
                rel_paths,
                source_id=source_id_for_root(target, explicit_id=os.getenv("TRINAXAI_SOURCE_ID")),
            )
    except Exception as exc:
        LOG.exception("Failed to delete indexed import for collection %s", collection_id)
        raise HTTPException(status_code=500, detail="Failed to delete indexed import.") from exc
    removed_path = False
    if os.path.isdir(target):
        shutil.rmtree(target, ignore_errors=True)
        removed_path = not os.path.exists(target)
    with state.sources_cache_lock:
        state.sources_cache.clear()
    with state.retrieval_cache_lock:
        state.retrieval_cache.clear()
    await run_in_threadpool(build_engine)
    return {
        "deleted": deleted,
        "removed_path": removed_path,
        "path": target,
        "collection": collection_id,
    }


async def system_index_job(request: Request, job_id: str):
    """Return the public status of a single indexing job. 404 if unknown.

    Devuelve el estado público de un trabajo de indexado. 404 si no existe.
    """
    _authorize_system(request)
    with state.index_jobs_lock:
        job = state.index_jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Index job not found.")
        return _job_public(dict(job))


async def system_cancel_index_job(request: Request, job_id: str):
    """Request cancellation of a running indexing job and mark it cancelled.

    Solicita la cancelación de un trabajo de indexado en curso y lo marca
    como cancelado.
    """
    _authorize_system(request)
    with state.index_jobs_lock:
        job = state.index_jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Index job not found.")
        job["cancel_requested"] = True
        job["updated_at"] = time.time()
        process = job.get("process")
        _persist_index_jobs_locked()
    if process and process.poll() is None:
        process.terminate()
    _update_index_job(
        job_id,
        status="cancelled",
        phase="cancelled",
        progress=100,
        finished_at=time.time(),
    )
    return {"ok": True, "job": _job_public(state.index_jobs[job_id])}


async def system_retry_index_job(request: Request, job_id: str):
    _authorize_system(request)
    with state.index_jobs_lock:
        job = state.index_jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Index job not found.")
        if job.get("status") not in {"failed", "cancelled"}:
            raise HTTPException(status_code=409, detail="Only failed or cancelled jobs can be retried.")
        target = str(job.get("path") or "")
        if not os.path.isdir(target):
            raise HTTPException(status_code=410, detail="The uploaded files are no longer available.")
        collection_id = str(job.get("collection_id") or config.DEFAULT_COLLECTION_ID)
        collection_name = str(job.get("collection_name") or config.DEFAULT_COLLECTION_NAME)
    _update_index_job(
        job_id,
        status="indexing",
        phase="queued",
        progress=30,
        error="",
        output="",
        cancel_requested=False,
        finished_at=None,
        pages_processed=0,
        chunks_generated=0,
        batches_processed=0,
        recent_activity="Retry queued",
    )
    threading.Thread(
        target=_run_index_job,
        args=(job_id, target, collection_id, collection_name),
        daemon=True,
        name=f"trinaxai-index-retry-{job_id[:8]}",
    ).start()
    with state.index_jobs_lock:
        return {"ok": True, "job": _job_public(dict(state.index_jobs[job_id]))}


def system_self_test(request: Request):
    """Prueba automática del sistema: Ollama, embedding, query básica.
    Útil para diagnóstico desde la PWA o CI/CD."""
    _authorize_system(request)
    results = {
        "ollama": False,
        "embedding": False,
        "rag_query": False,
        "rag_indexed": False,
        "document_extractors": False,
        "voice_routes": False,
        "watcher": False,
    }

    # 1. Verificar Ollama (uses config.OLLAMA_BASE_URL; no curl dependency)
    try:
        _ollama_tags = f"{config.OLLAMA_BASE_URL.rstrip('/')}/api/tags"
        # Ollama is local/configured infrastructure; proxy environment settings
        # can otherwise turn a healthy localhost service into a false failure.
        with httpx.Client(trust_env=False, timeout=8, follow_redirects=False) as _client:
            _resp = _client.get(_ollama_tags)
        _resp.raise_for_status()
        results["ollama"] = bool(_resp.json().get("models"))
    except Exception:
        LOG.debug("Best-effort operation failed", exc_info=True)

    # 2. Verificar el embedder configurado
    try:
        emb = Settings.embed_model
        test_vec = emb.get_text_embedding("TrinaxAI system test")
        results["embedding"] = bool(test_vec and len(test_vec) > 0)
    except Exception:
        LOG.debug("Best-effort operation failed", exc_info=True)

    # 3. Verificar RAG (índice + query)
    results["rag_indexed"] = state.fusion_retriever is not None
    if results["rag_indexed"] and results["ollama"]:
        try:
            query_bundle = QueryBundle("test")
            nodes = state.fusion_retriever.retrieve(query_bundle)
            results["rag_query"] = len(nodes) > 0
        except Exception:
            LOG.debug("Best-effort operation failed", exc_info=True)

    # 4. Verify capabilities that previously failed silently.
    try:
        import openpyxl  # noqa: F401
        import pptx  # noqa: F401
        import striprtf  # noqa: F401

        results["document_extractors"] = True
    except Exception:
        LOG.debug("Best-effort operation failed", exc_info=True)
    results["voice_routes"] = {"/v1/voice/capabilities", "/v1/voice/stt", "/v1/voice/tts"}.issubset(
        request.app.openapi()["paths"]
    )
    try:
        from watchdog.observers import Observer as _Observer  # noqa: F401

        results["watcher"] = True
    except Exception:
        LOG.debug("Best-effort operation failed", exc_info=True)

    # Voice is deliberately optional: installations without Whisper/Piper must
    # still report a healthy core. ``voice_routes`` remains visible as a
    # capability diagnostic without turning the entire self-test red.
    required = {key: value for key, value in results.items() if key != "voice_routes"}
    return {
        "ok": all(required.values()),
        "results": results,
        "optional": {"voice_routes": results["voice_routes"]},
        "profile": config.TRINAXAI_PROFILE,
    }


__all__ = [name for name in globals() if not name.startswith("__")]
