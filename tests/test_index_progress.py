from __future__ import annotations

import pytest

import index
from app.services import system_service
from app.services.engine_state import state
from app.services.system_service import _append_index_output, _line_progress, _progress_changes

# ── Subprocess stdout → UI progress bar mapping ───────────────────────────
# index.py reports real work units as structured lines: files read, files
# chunked and embedding batches done. Each phase owns a slice of the bar, so the
# percentage keeps moving while the indexer works instead of staying frozen
# until a whole batch (up to 100 files) finishes.

_EMBED_START = system_service._EMBED_PROGRESS_START
_EMBED_END = system_service._EMBED_PROGRESS_END


def test_batch_marker_maps_proportionally_across_embedding_span():
    start, _ = _line_progress("🔨 Embeddings lote 1/10...", 40)
    mid, phase = _line_progress("🔨 Embeddings lote 5/10...", 40)
    end, _ = _line_progress("🔨 Embeddings lote 10/10...", 40)
    assert phase == "embedding"
    assert _EMBED_START <= start < mid < end <= _EMBED_END


def test_batch_progress_never_moves_backwards():
    # A later, smaller-looking line must not drag an already-higher bar down.
    value, _ = _line_progress("🔨 Embeddings lote 1/10...", 80)
    assert value == 80


def test_publish_line_reaches_saving_phase():
    value, phase = _line_progress("💾 Publicando primera generación atómica...", 80)
    assert phase == "saving_index"
    assert value >= system_service._PUBLISH_PROGRESS


def test_phase_announcements_never_invent_a_percentage():
    # "Troceando" is printed before the work starts, so it relabels the phase but
    # must not move the bar on its own.
    assert _line_progress("✂️  Troceando documentos...", 30) == (30, "chunking")
    assert _line_progress("indexando embeddings", 30) == (30, "embedding")


# ── Structured events: real counters per file and per embedding batch ─────


def test_read_and_chunk_bands_track_processed_files():
    reading = _progress_changes({"phase": "extracting", "files_total": 40, "files_processed": 10, "determinate": True})
    chunking = _progress_changes({"phase": "chunking", "files_total": 40, "files_processed": 30, "determinate": True})
    done = _progress_changes({"phase": "chunking", "files_total": 40, "files_processed": 40, "determinate": True})

    assert reading["progress"] == 34  # 30 → 48 by files read
    assert chunking["progress"] == 58  # 48 → 62 by files chunked
    assert done["progress"] == 62
    assert reading["progress_exact"] is True


def test_embedding_span_waits_for_the_last_file():
    # Streaming runs read, chunk and embed in the same pass: mapping the
    # embedding span while files are still pending would overstate the work.
    pending = _progress_changes(
        {
            "phase": "embedding",
            "batches_processed": 2,
            "batches_total": 4,
            "files_processed": 40,
            "files_total": 250,
            "determinate": True,
        }
    )
    assert "progress" not in pending
    assert pending["phase"] == "embedding"

    ready = _progress_changes(
        {
            "phase": "embedding",
            "batches_processed": 2,
            "batches_total": 4,
            "files_processed": 40,
            "files_total": 40,
            "determinate": True,
        }
    )
    assert ready["progress"] == 77  # 62 → 92


def test_embedding_start_flips_the_phase_and_marks_it_provisional():
    changes = _progress_changes(
        {
            "phase": "embedding",
            "batches_processed": 0,
            "batches_total": 5,
            "files_processed": 40,
            "files_total": 40,
            "determinate": False,
        }
    )
    assert changes["phase"] == "embedding"
    assert changes["progress"] == _EMBED_START
    assert changes["progress_exact"] is False


def test_chunking_without_counters_keeps_the_labelled_estimate():
    changes = _progress_changes({"phase": "chunking"})
    assert "progress" not in changes
    assert changes["progress_exact"] is False


@pytest.mark.parametrize(
    "banner",
    ["🆕 Indexado completo (primera vez)", "🆕 Full index (first run)"],
)
def test_first_run_banner_does_not_look_like_completion(banner: str):
    # Starts with "complet" but announces the opposite: it must not send the bar
    # to ~97% while the run is only getting started.
    assert _line_progress(banner, 30) == (30, "")


@pytest.mark.parametrize("line", ["✅ Indexado completado", "✅ Indexing completed"])
def test_real_completion_line_reaches_the_finish_band(line: str):
    assert _line_progress(line, 30) == (system_service._FINISH_PROGRESS, "finishing")


def run_fake_index_stream(monkeypatch, lines: tuple[str, ...]):
    """Drive the real supervisor over a fake subprocess stdout.

    Returns the stored job plus every (progress, phase, exact) state the
    supervisor published, so a test can assert the whole trace.
    """
    monkeypatch.setattr(system_service, "_persist_index_jobs_locked", lambda: None)
    monkeypatch.setattr(system_service, "_prune_old_jobs", lambda: None)
    monkeypatch.setattr(system_service, "_record_index_run", lambda: None)
    monkeypatch.setattr(system_service, "build_engine", lambda: True)

    class Process:
        stdout = iter(lines)

        def poll(self):
            return 0

        def wait(self, timeout=None):
            return 0

        def terminate(self):
            pass

        def kill(self):
            pass

    class Thread:
        def __init__(self, *, target, **_kwargs):
            self.target = target

        def start(self):
            self.target()

    snapshots: list[tuple[int, str, bool]] = []
    real_update = system_service._update_index_job

    def record_update(job_id, **changes):
        real_update(job_id, **changes)
        current = state.index_jobs.get(job_id) or {}
        snapshots.append(
            (
                int(current.get("progress") or 0),
                str(current.get("phase") or ""),
                bool(current.get("progress_exact")),
            )
        )

    monkeypatch.setattr(system_service.threading, "Thread", Thread)
    monkeypatch.setattr(system_service.subprocess, "Popen", lambda *_args, **_kwargs: Process())
    monkeypatch.setattr(system_service, "_update_index_job", record_update)

    with state.index_jobs_lock:
        previous = state.index_jobs
        state.index_jobs = {}
    try:
        job = system_service._new_index_job("job", "/tmp/docs", "docs", "Docs")
        system_service._run_index_job(job["id"], "/tmp/docs")
        stored = dict(state.index_jobs[job["id"]])
    finally:
        with state.index_jobs_lock:
            state.index_jobs = previous
    return stored, snapshots


def test_file_counter_never_walks_backwards_across_phases(monkeypatch):
    stored, snapshots = run_fake_index_stream(
        monkeypatch,
        (
            'TRINAXAI_PROGRESS {"phase": "extracting", "files_total": 35, '
            '"files_processed": 35, "determinate": true}\n',
            'TRINAXAI_PROGRESS {"phase": "chunking", "files_total": 35, '
            '"files_processed": 1, "chunks_generated": 4, "determinate": true}\n',
            'TRINAXAI_PROGRESS {"phase": "chunking", "files_total": 35, '
            '"files_processed": 35, "chunks_generated": 4, "determinate": true}\n',
            'TRINAXAI_PROGRESS {"phase": "embedding", "batches_processed": 1, '
            '"batches_total": 2, "files_processed": 35, "files_total": 35, "determinate": true}\n',
        ),
    )

    progress = [value for value, _, _ in snapshots]
    assert progress == sorted(progress)
    assert 48 in progress  # first file chunked
    assert 62 in progress  # every file chunked → embedding owns the bar
    assert 77 in progress  # 1 of 2 embedding batches
    assert snapshots[-1][0] == 100

    # Chunking reports earlier file positions than the reading phase already
    # reached; the counter shown next to the bar must not walk backwards.
    assert stored["files_processed"] == 35
    assert stored["chunks_generated"] == 4
    assert stored["status"] == "completed"


def test_plain_log_lines_keep_the_exact_percentage_and_phase(monkeypatch):
    stored, snapshots = run_fake_index_stream(
        monkeypatch,
        (
            'TRINAXAI_PROGRESS {"phase": "extracting", "files_total": 35, '
            '"files_processed": 35, "determinate": true}\n',
            "   📦 Batch 1: 35 documents, 35 files\n",
        ),
    )

    # The log line neither moved the bar nor downgraded it to an estimate, and
    # it did not relabel the phase.
    assert (48, "extracting", True) in snapshots
    assert all(exact for _, _, exact in snapshots)
    assert all(phase != "" for _, phase, _ in snapshots)
    assert stored["progress_exact"] is True


def test_machine_progress_lines_never_become_user_activity(monkeypatch):
    monkeypatch.setattr(system_service, "_persist_index_jobs_locked", lambda: None)
    job = {"id": "job", "output": "", "recent_activity": "Upload job created"}
    monkeypatch.setattr(state, "index_jobs", {"job": job})

    _append_index_output("job", 'TRINAXAI_PROGRESS {"phase": "chunking", "files_total": 40}\n')
    assert job["recent_activity"] == "Upload job created"

    _append_index_output("job", "🔨 Embeddings lote 2/5...\n")
    assert job["recent_activity"] == "🔨 Embeddings lote 2/5..."


# ── index.py batch helpers ────────────────────────────────────────────────


def test_total_batches_matches_iter_batches():
    for n in (0, 1, 7, 100, 101, 250):
        items = list(range(n))
        assert index.total_batches(items) == len(list(index.iter_batches(items)))


def test_emit_embed_progress_prints_parseable_line(capsys):
    index._emit_embed_progress(3, 12)
    out = capsys.readouterr().out

    assert "3/12" in out
    assert system_service._structured_progress(out.strip().splitlines()[-1]) == {
        "phase": "embedding",
        "batches_processed": 3,
        "batches_total": 12,
        "determinate": True,
    }


@pytest.mark.parametrize("label", ["batch", "lote"])
def test_embedding_batch_line_maps_in_both_languages(label: str) -> None:
    # The log line is localized, so the supervisor must recognise either spelling.
    value, phase = _line_progress(f"🔨 Embeddings {label} 3/12...", 40)
    assert phase == "embedding"
    assert value == 69  # 62 → 92 across the batch span


def test_degenerate_batch_line_does_not_move_the_bar():
    # "0/0" carries no information: label the phase, keep the percentage.
    assert _line_progress("🔨 Embeddings batch 0/0...", 40) == (40, "embedding")


def test_emit_embed_progress_reports_the_start_before_the_first_batch(capsys):
    index._emit_embed_progress(0, 5, True, files=(40, 40))
    out = capsys.readouterr().out

    assert "lote" not in out
    assert system_service._structured_progress(out.strip()) == {
        "phase": "embedding",
        "batches_processed": 0,
        "batches_total": 5,
        "determinate": False,
        "files_processed": 40,
        "files_total": 40,
    }


def test_emit_embed_progress_ignores_zero_total(capsys):
    index._emit_embed_progress(0, 0)
    assert capsys.readouterr().out == ""


def test_full_index_emits_per_file_and_embedding_progress(tmp_path, monkeypatch):
    context = index.SourceContext.create(str(tmp_path), source_id="source", collection_id="docs")
    paths = []
    for name in ("one.txt", "two.txt", "three.txt"):
        target = tmp_path / name
        target.write_text(f"content of {name} " + "more " * 30, encoding="utf-8")
        paths.append(str(target))

    events: list[dict] = []
    monkeypatch.setattr(index, "emit_progress", lambda phase, **values: events.append({"phase": phase, **values}))
    monkeypatch.setattr(index, "new_storage_context", lambda _path: object())
    monkeypatch.setattr(index, "publish_index_generation", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(index, "print_summary", lambda *_args: None)

    def fake_insert(current, nodes, **kwargs):
        report = kwargs["on_embed_progress"]
        report(0, 2, True)
        report(1, 2, False)
        report(2, 2, False)
        return current or object()

    monkeypatch.setattr(index, "insert_node_batches", fake_insert)

    new_state = {
        context.source_key(path): {"hash": "h" + str(position), "source_id": context.source_id}
        for position, path in enumerate(paths)
    }
    assert index.run_full_index(paths, new_state, context) == 0

    extracting = [event for event in events if event["phase"] == "extracting"]
    chunking = [event for event in events if event["phase"] == "chunking"]
    embedding = [event for event in events if event["phase"] == "embedding"]

    assert [event["files_processed"] for event in extracting] == [1, 2, 3]
    assert extracting[-1]["files_total"] == 3
    assert chunking[-1]["files_processed"] == 3
    assert chunking[-1]["chunks_generated"] > 0
    assert [event["batches_processed"] for event in embedding] == [0, 1, 2]
    assert embedding[0]["files_processed"] == 3
    assert embedding[0]["determinate"] is False


def test_incremental_updates_emit_the_same_progress(tmp_path, monkeypatch):
    from trinaxai_index_state import apply_file_updates

    context = index.SourceContext.create(str(tmp_path), source_id="source", collection_id="docs")
    paths = []
    for name in ("one.txt", "two.txt"):
        target = tmp_path / name
        target.write_text(f"content of {name} " + "more " * 30, encoding="utf-8")
        paths.append(str(target))

    events: list[dict] = []
    monkeypatch.setattr(index, "emit_progress", lambda phase, **values: events.append({"phase": phase, **values}))
    monkeypatch.setattr(index, "remove_obsolete_nodes", lambda *_args, **_kwargs: 0)

    def fake_insert(current, nodes, **kwargs):
        report = kwargs["on_embed_progress"]
        report(0, 1, True)
        report(1, 1, False)
        return current

    monkeypatch.setattr(index, "insert_node_batches", fake_insert)

    result = apply_file_updates(object(), paths, changed=set(paths), context=context)

    assert result.total_nodes > 0
    assert [event["files_processed"] for event in events if event["phase"] == "extracting"] == [1, 2]
    assert [event["batches_processed"] for event in events if event["phase"] == "embedding"] == [0, 1]
    assert result.indexed_paths == set(paths)


def test_load_docs_reports_every_file_as_it_is_read(tmp_path):
    context = index.SourceContext.create(str(tmp_path), source_id="source", collection_id="docs")
    paths = []
    for name in ("one.txt", "two.txt", "three.txt"):
        target = tmp_path / name
        target.write_text(f"content of {name}", encoding="utf-8")
        paths.append(str(target))

    seen: list[int] = []
    result = index.load_docs_with_status(paths, context, on_file_read=seen.append)

    assert len(result.documents) == 3
    assert seen == [1, 2, 3]


def test_prepare_batch_reports_files_as_they_are_chunked(tmp_path):
    context = index.SourceContext.create(str(tmp_path), source_id="source", collection_id="docs")
    paths = []
    for name in ("one.txt", "two.txt"):
        target = tmp_path / name
        target.write_text(f"content of {name}", encoding="utf-8")
        paths.append(str(target))

    read: list[int] = []
    chunked: list[tuple[int, int]] = []
    prepared = index.prepare_batch(
        paths,
        context=context,
        files_offset=10,
        on_file_read=read.append,
        on_file_chunked=lambda done, chunks: chunked.append((done, chunks)),
    )

    assert read == [11, 12]
    assert [done for done, _ in chunked] == [11, 12]
    assert all(chunks > 0 for _, chunks in chunked)
    assert prepared.nodes
