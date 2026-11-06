from __future__ import annotations

import os

import pytest

import index
from app.services import index_progress as model


def fold(events: list[dict], work: dict | None = None, start: float = 100.0, step: float = 1.0) -> dict:
    work = work or model.new_work()
    for position, event in enumerate(events):
        model.record_event(work, event, now=start + position * step)
    return work


def embed(done: int, total: int, files: int, files_total: int, **extra) -> dict:
    return {
        "phase": "embedding",
        "batches_processed": done,
        "batches_total": total,
        "files_processed": files,
        "files_total": files_total,
        **extra,
    }


def test_nothing_moves_before_the_indexer_reports_totals():
    work = fold([{"phase": "extracting", "pages_total": 10, "pages_processed": 5}])
    assert not model.has_totals(work)
    assert model.work_fraction(work) == 0.0
    assert model.progress_percent(work) == model.WORK_START
    assert model.eta_seconds(work, now=500.0) is None


def test_fraction_is_the_weighted_sum_of_real_stage_counters():
    work = fold(
        [
            {"phase": "extracting", "files_total": 10, "files_processed": 10},
            {"phase": "chunking", "files_total": 10, "files_processed": 10},
            embed(1, 2, 10, 10),
        ]
    )
    stages = model.stage_fractions(work)
    assert stages == {"read": 1.0, "chunk": 1.0, "embed": 0.5}
    expected = model.READ_WEIGHT + model.CHUNK_WEIGHT + model.EMBED_WEIGHT * 0.5
    assert model.work_fraction(work) == pytest.approx(expected)


def test_the_bar_reaches_the_end_of_the_work_span_only_when_everything_is_embedded():
    work = fold(
        [
            {"phase": "extracting", "files_total": 4, "files_processed": 4},
            {"phase": "chunking", "files_total": 4, "files_processed": 4},
            embed(3, 4, 4, 4),
        ]
    )
    assert model.progress_percent(work) < model.WORK_END
    model.record_event(work, embed(4, 4, 4, 4), now=200.0)
    assert model.work_fraction(work) == pytest.approx(1.0)
    assert model.progress_percent(work) == model.WORK_END


def test_counters_never_walk_backwards_when_events_arrive_out_of_order():
    work = fold(
        [
            {"phase": "extracting", "files_total": 10, "files_processed": 10},
            {"phase": "chunking", "files_total": 10, "files_processed": 8},
            {"phase": "chunking", "files_total": 10, "files_processed": 3},
        ]
    )
    assert work["read"] == 10 and work["chunk"] == 8


def test_a_failed_file_batch_does_not_stall_the_embedding_credit():
    # The first batch produced no chunks (nothing was embedded); the next one
    # catches the boundary up instead of leaving the bar short forever.
    work = fold(
        [
            {"phase": "chunking", "files_total": 200, "files_processed": 100},
            {"phase": "chunking", "files_total": 200, "files_processed": 200},
            embed(1, 1, 200, 200),
        ]
    )
    assert model.stage_fractions(work)["embed"] == pytest.approx(1.0)


def test_bytes_are_preferred_over_files_when_the_indexer_reports_them():
    work = fold(
        [
            {
                "phase": "extracting",
                "files_total": 3,
                "files_processed": 1,
                "bytes_total": 1000,
                "bytes_processed": 900,
            }
        ]
    )
    assert work["unit"] == "bytes"
    assert model.stage_fractions(work)["read"] == pytest.approx(0.9)


def test_events_without_the_chosen_unit_are_ignored():
    work = fold([{"phase": "extracting", "bytes_total": 100, "bytes_processed": 50}])
    model.record_event(work, {"phase": "extracting", "files_total": 5, "files_processed": 5}, now=200.0)
    assert work["read"] == 50


def test_unknown_phases_and_bad_batch_counters_are_harmless():
    work = fold([{"phase": "extracting", "files_total": 2, "files_processed": 1}])
    before = dict(work)
    model.record_event(work, {"phase": "warning", "files_total": 2, "files_processed": 2}, now=200.0)
    model.record_event(work, {"phase": "embedding", "batches_total": 0, "batches_processed": 0, "files_processed": 2})
    assert {key: work[key] for key in ("read", "chunk", "embedded")} == {
        key: before[key] for key in ("read", "chunk", "embedded")
    }


# ── ETA from the observed pace ────────────────────────────────────────────


def test_eta_waits_until_there_is_enough_evidence():
    work = fold([{"phase": "extracting", "files_total": 100, "files_processed": 1}], start=100.0)
    assert model.eta_seconds(work, now=101.0) is None  # too early and too little work done


def test_eta_follows_the_measured_throughput():
    # Completed embedding at a steady pace: 10% of the files every 10 seconds.
    work = model.new_work()
    for step in range(1, 4):
        done = step * 10
        event = embed(1, 1, done, 100, bytes_total=100, bytes_processed=done)
        model.record_event(work, event, now=100.0 + step * 10)

    eta = model.eta_seconds(work, now=130.0)
    first, last = work["samples"][0], work["samples"][-1]
    pace = (last[1] - first[1]) / (last[0] - first[0])
    assert eta is not None
    assert eta == pytest.approx((1.0 - model.work_fraction(work)) / pace, rel=0.2)


def test_eta_grows_while_the_run_is_stalled():
    work = fold(
        [
            {"phase": "extracting", "files_total": 100, "files_processed": 100},
            {"phase": "chunking", "files_total": 100, "files_processed": 100},
            embed(1, 10, 100, 100),
            embed(2, 10, 100, 100),
            embed(3, 10, 100, 100),
        ],
        start=100.0,
        step=5.0,
    )
    soon = model.eta_seconds(work, now=111.0)
    later = model.eta_seconds(work, now=170.0)
    assert soon is not None and later is not None
    assert later > soon


def test_eta_is_zero_when_the_work_is_complete():
    work = fold(
        [
            {"phase": "extracting", "files_total": 2, "files_processed": 2},
            {"phase": "chunking", "files_total": 2, "files_processed": 2},
            embed(1, 1, 2, 2),
        ]
    )
    assert model.eta_seconds(work, now=500.0) == 0


# ── What the indexer reports ─────────────────────────────────────────────


def test_run_meter_reports_bytes_as_a_prefix_sum(tmp_path):
    paths = []
    for name, size in (("a.txt", 100), ("b.txt", 300), ("c.txt", 600)):
        target = tmp_path / name
        target.write_bytes(b"x" * size)
        paths.append(str(target))
    meter = index.RunMeter(paths)

    assert meter.bytes_total == 1000
    assert meter.bytes_done(0) == 0
    assert meter.bytes_done(2) == 400
    assert meter.bytes_done(99) == 1000  # never past the total
    counters = meter.counters(2)
    assert counters == {"files_total": 3, "files_processed": 2, "bytes_total": 1000, "bytes_processed": 400}


def test_run_meter_names_the_file_in_progress_without_leaking_absolute_paths(tmp_path):
    target = tmp_path / "notes" / "plan.md"
    target.parent.mkdir()
    target.write_text("hola", encoding="utf-8")
    context = index.SourceContext.create(str(tmp_path), source_id="s", collection_id="docs")
    meter = index.RunMeter([str(target)], context)

    shown = meter.counters(1, current=True)["current_file"]
    assert shown == os.path.join("notes", "plan.md").replace("\\", "/")
    assert str(tmp_path) not in shown
    assert "current_file" not in meter.counters(1)


def test_run_meter_survives_files_that_vanish(tmp_path):
    meter = index.RunMeter([str(tmp_path / "missing.txt")])
    assert meter.bytes_total == 1  # an unreadable file still counts as one unit


def test_embed_progress_carries_the_byte_position(capsys):
    index._emit_embed_progress(1, 4, files=(10, 40), weight=(2048, 8192))
    line = capsys.readouterr().out.strip().splitlines()[-1]
    payload = __import__("json").loads(line.removeprefix("TRINAXAI_PROGRESS "))
    assert payload["bytes_processed"] == 2048 and payload["bytes_total"] == 8192
    assert payload["files_processed"] == 10 and payload["batches_processed"] == 1


def test_full_index_events_carry_bytes_and_a_current_file(tmp_path, monkeypatch):
    context = index.SourceContext.create(str(tmp_path), source_id="source", collection_id="docs")
    paths = []
    for name in ("one.txt", "two.txt"):
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
        report(0, 1, True)
        report(1, 1, False)
        return current or object()

    monkeypatch.setattr(index, "insert_node_batches", fake_insert)
    new_state = {context.source_key(path): {"hash": "h", "source_id": context.source_id} for path in paths}
    assert index.run_full_index(paths, new_state, context) == 0

    reading = [event for event in events if event["phase"] == "extracting"]
    assert [event["current_file"] for event in reading] == ["one.txt", "two.txt"]
    assert reading[-1]["bytes_processed"] == reading[-1]["bytes_total"] > 0
    embedding = [event for event in events if event["phase"] == "embedding"]
    assert embedding[-1]["bytes_processed"] == embedding[-1]["bytes_total"]


def test_files_are_reported_as_each_one_finishes_reading(tmp_path, monkeypatch):
    # The reader pool must be consumed lazily: the callback for the first file
    # has to run while a slow later file is still being read, otherwise progress
    # arrives as one burst when the whole batch ends.
    import threading

    context = index.SourceContext.create(str(tmp_path), source_id="source", collection_id="docs")
    paths = []
    for name in ("one.txt", "two.txt", "slow.txt"):
        target = tmp_path / name
        target.write_text(f"content of {name}", encoding="utf-8")
        paths.append(str(target))

    first_reported = threading.Event()
    slow_saw_report = []
    real_load = index._load_file_documents_result

    def traced(path):
        if os.path.basename(path) == "slow.txt":
            slow_saw_report.append(first_reported.wait(timeout=5))
        return real_load(path)

    monkeypatch.setattr(index, "_load_file_documents_result", traced)
    monkeypatch.setattr(index, "INDEX_LOAD_WORKERS", 3)
    index.load_docs_with_status(paths, context, on_file_read=lambda done: first_reported.set())
    assert slow_saw_report == [True]
