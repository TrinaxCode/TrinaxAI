from __future__ import annotations

import json
from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DictionaryObject, NameObject, StreamObject

import index
from app.services import system_service
from app.services.engine_state import state


def make_text_pdf(path: Path, pages: int) -> None:
    writer = PdfWriter()
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    for number in range(1, pages + 1):
        page = writer.add_blank_page(width=612, height=792)
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
        )
        content = StreamObject()
        content.set_data(f"BT /F1 12 Tf 72 720 Td (TrinaxAI page {number} searchable text) Tj ET".encode())
        page[NameObject("/Contents")] = writer._add_object(content)
    with path.open("wb") as stream:
        writer.write(stream)


def test_text_pdf_160_pages_finishes_with_page_progress(tmp_path, capsys) -> None:
    pdf = tmp_path / "manual-160.pdf"
    make_text_pdf(pdf, 160)

    documents = index._load_pdf_documents(str(pdf))
    events = [
        json.loads(line.removeprefix("TRINAXAI_PROGRESS "))
        for line in capsys.readouterr().out.splitlines()
        if line.startswith("TRINAXAI_PROGRESS ")
    ]

    assert len(PdfReader(pdf).pages) == len(documents) == 160
    assert events[-1] == {"phase": "extracting", "pages_total": 160, "pages_processed": 160, "determinate": True}
    assert "page 160 searchable text" in documents[-1].text


def test_corrupt_and_empty_pdf_fail_at_extraction(tmp_path) -> None:
    corrupt = tmp_path / "corrupt.pdf"
    corrupt.write_bytes(b"%PDF-not-a-real-document")
    with pytest.raises(Exception):
        index._load_pdf_documents(str(corrupt))

    empty = tmp_path / "scanned.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    with empty.open("wb") as stream:
        writer.write(stream)
    with pytest.raises(ValueError, match="OCR may be required"):
        index._load_pdf_documents(str(empty))


def test_structured_job_progress_is_exact_and_stage_specific() -> None:
    event = system_service._structured_progress(
        'TRINAXAI_PROGRESS {"phase":"extracting","pages_total":160,"pages_processed":80,"determinate":true}\n'
    )
    assert event is not None
    changes = system_service._progress_changes(event)
    assert changes["phase"] == "extracting"
    assert changes["pages_processed"] == 80
    assert changes["progress"] == 42
    assert changes["progress_exact"] is True
    assert system_service._line_progress("ordinary log line", 42) == (42, "indexing")


def test_job_state_persists_for_frontend_reconnection(tmp_path, monkeypatch) -> None:
    jobs_path = tmp_path / "index_jobs.json"
    monkeypatch.setattr(system_service.config, "PERSIST_DIR", str(tmp_path))
    monkeypatch.setattr(system_service.config, "INDEX_JOBS_PATH", str(jobs_path))
    with state.index_jobs_lock:
        previous = state.index_jobs
        state.index_jobs = {}
    try:
        job = system_service._new_index_job("manual", str(tmp_path / "manual"), "default", "General")
        system_service._update_index_job(job["id"], phase="extracting", pages_total=160, pages_processed=37)
        stored = json.loads(jobs_path.read_text(encoding="utf-8"))[job["id"]]
        assert stored["phase"] == "extracting"
        assert stored["pages_processed"] == 37
        assert "process" not in stored
    finally:
        with state.index_jobs_lock:
            state.index_jobs = previous


def test_interrupted_jobs_are_restored_as_failed(tmp_path, monkeypatch) -> None:
    jobs_path = tmp_path / "index_jobs.json"
    jobs_path.write_text(
        json.dumps(
            {
                "running": {"status": "indexing", "phase": "embedding"},
                "complete": {"status": "completed", "phase": "done"},
                "invalid": "not-a-job",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(system_service.config, "INDEX_JOBS_PATH", str(jobs_path))
    with state.index_jobs_lock:
        previous = state.index_jobs
        state.index_jobs = {}
    try:
        system_service._restore_index_jobs()
        assert state.index_jobs["running"]["status"] == "failed"
        assert state.index_jobs["running"]["phase"] == "interrupted"
        assert state.index_jobs["running"]["process"] is None
        assert state.index_jobs["complete"]["status"] == "completed"
        assert "invalid" not in state.index_jobs
    finally:
        with state.index_jobs_lock:
            state.index_jobs = previous


def test_finished_index_jobs_are_pruned_after_one_hour(monkeypatch) -> None:
    persisted = []
    monkeypatch.setattr(system_service.time, "time", lambda: 10_000.0)
    monkeypatch.setattr(system_service, "_persist_index_jobs_locked", lambda: persisted.append(True))
    with state.index_jobs_lock:
        previous = state.index_jobs
        state.index_jobs = {
            "stale": {"finished_at": 6_000.0},
            "recent": {"finished_at": 9_000.0},
            "running": {"finished_at": None},
        }
    try:
        system_service._prune_old_jobs()
        assert set(state.index_jobs) == {"recent", "running"}
        assert persisted == [True]
    finally:
        with state.index_jobs_lock:
            state.index_jobs = previous


def test_index_job_helpers_bound_untrusted_names_output_and_progress(monkeypatch) -> None:
    assert system_service._safe_rel_path("../../manuales/plan?.pdf") == "manuales/plan_.pdf"
    assert system_service._safe_rel_path("/../") is None
    assert system_service._safe_label(" ..informe: julio.. ") == "informe_ julio"
    assert system_service._safe_label("???") == "import"
    assert system_service._estimate_index_seconds(0, 0) == 45
    assert system_service._estimate_index_seconds(10_000, 10_000_000_000) == 1800

    job = {
        "id": "bounded-job",
        "status": "saving",
        "progress": 10,
        "created_at": 900.0,
        "output": "",
    }
    monkeypatch.setattr(system_service, "_persist_index_jobs_locked", lambda: None)
    monkeypatch.setattr(system_service.time, "time", lambda: 1000.0)
    with state.index_jobs_lock:
        previous = state.index_jobs
        state.index_jobs = {job["id"]: job}
    try:
        system_service._append_index_output(job["id"], "x" * 9000)
        public = system_service._job_public(job)
        assert len(job["output"]) == 8000
        assert len(job["recent_activity"]) == 300
        assert public["progress"] == 10
        assert public["eta_seconds"] == 900
        assert public["elapsed_seconds"] == 100
    finally:
        with state.index_jobs_lock:
            state.index_jobs = previous

    assert system_service._line_progress("Troceando documento", 10) == (45, "chunking")
    assert system_service._line_progress("Embeddings lote 2/4", 10) == (76, "embedding")
    assert system_service._line_progress("Persistiendo índice", 10) == (88, "saving_index")
    assert system_service._line_progress("Completado", 10) == (96, "finishing")
    assert system_service._structured_progress("TRINAXAI_PROGRESS not-json") is None


@pytest.mark.asyncio
async def test_cancel_stops_process_and_retry_requeues(tmp_path, monkeypatch) -> None:
    class Process:
        terminated = False

        def poll(self):
            return None

        def terminate(self):
            self.terminated = True

    class Thread:
        started = False

        def __init__(self, **_kwargs):
            pass

        def start(self):
            self.started = True

    target = tmp_path / "upload"
    target.mkdir()
    process = Process()
    job = {
        "id": "job-1",
        "label": "manual",
        "path": str(target),
        "status": "indexing",
        "phase": "embedding",
        "progress": 70,
        "created_at": 1.0,
        "updated_at": 1.0,
        "process": process,
        "collection_id": "default",
        "collection_name": "General",
    }
    monkeypatch.setattr(system_service, "_authorize_system", lambda _request: None)
    monkeypatch.setattr(system_service, "_persist_index_jobs_locked", lambda: None)
    monkeypatch.setattr(system_service.threading, "Thread", Thread)
    with state.index_jobs_lock:
        previous = state.index_jobs
        state.index_jobs = {job["id"]: job}
    try:
        cancelled = await system_service.system_cancel_index_job(object(), job["id"])
        assert process.terminated is True
        assert cancelled["job"]["status"] == "cancelled"
        retried = await system_service.system_retry_index_job(object(), job["id"])
        assert retried["job"]["status"] == "indexing"
        assert retried["job"]["error"] == ""
    finally:
        with state.index_jobs_lock:
            state.index_jobs = previous
