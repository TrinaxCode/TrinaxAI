from __future__ import annotations

import index
from app.services.system_service import _line_progress

# ── Subprocess stdout → UI progress bar mapping ───────────────────────────
# index.py emits one "Embeddings lote N/M..." line per batch instead of tqdm's
# carriage-return bar, so the supervisor can move the bar proportionally rather
# than jumping to 65% and stalling there until the whole run finishes.

def test_batch_marker_maps_proportionally_across_embedding_span():
    start, _ = _line_progress("🔨 Embeddings lote 1/10...", 40)
    mid, phase = _line_progress("🔨 Embeddings lote 5/10...", 40)
    end, _ = _line_progress("🔨 Embeddings lote 10/10...", 40)
    assert phase == "embedding"
    # 65 → 88 span, monotonically increasing with N/M.
    assert 65 <= start < mid < end <= 88


def test_batch_progress_never_moves_backwards():
    # A later, smaller-looking line must not drag an already-higher bar down.
    value, _ = _line_progress("🔨 Embeddings lote 1/10...", 80)
    assert value == 80


def test_publish_line_reaches_saving_phase():
    value, phase = _line_progress("💾 Publicando primera generación atómica...", 80)
    assert phase == "saving_index"
    assert value >= 88


def test_generic_embedding_line_still_recognised():
    value, phase = _line_progress("indexando embeddings", 30)
    assert phase == "embedding"
    assert value >= 65


# ── index.py batch helpers ────────────────────────────────────────────────

def test_total_batches_matches_iter_batches():
    for n in (0, 1, 7, 100, 101, 250):
        items = list(range(n))
        assert index.total_batches(items) == len(list(index.iter_batches(items)))


def test_emit_embed_progress_prints_parseable_line(capsys):
    index._emit_embed_progress(3, 12)
    out = capsys.readouterr().out
    assert "lote 3/12" in out
    # Must be re-parseable by the supervisor.
    value, phase = _line_progress(out.strip(), 40)
    assert phase == "embedding"
    assert value > 65


def test_emit_embed_progress_ignores_zero_total(capsys):
    index._emit_embed_progress(0, 0)
    assert capsys.readouterr().out == ""
