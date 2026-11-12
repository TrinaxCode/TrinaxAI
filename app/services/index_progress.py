"""Measured progress for index jobs.

The indexer reports counters (bytes or files read, chunked and embedded), never
a percentage. This module folds those counters into one monotonic fraction and
derives the ETA from the throughput actually observed, so the bar only moves
when work really finished and no timer or fixed estimate drives it.

Bar layout (percent of the whole job): receiving and saving the upload owns the
first ``UPLOAD_SHARE``; the measured indexing work fills ``WORK_START`` to
``WORK_END``; publishing the new generation and reloading the engine own the
rest.
"""

from __future__ import annotations

import time

UPLOAD_SHARE = 10
WORK_START = UPLOAD_SHARE
WORK_END = 95
PUBLISH_PROGRESS = 96
FINISH_PROGRESS = 98

# Share of one document's cost spent in each stage. Embedding goes through the
# local model and dominates a CPU run (40 text files: 2.3 s to read and split,
# 10 min to embed the first batch); PDFs with many pages keep some room for
# reading. The values only decide how
# the bar is divided: every step inside a stage is still a real counter.
READ_WEIGHT = 0.04
CHUNK_WEIGHT = 0.02
EMBED_WEIGHT = 0.94

# Throughput is read over a short sliding window so a slow PDF does not
# poison the estimate for the rest of the run and a stall shows up honestly.
_WINDOW_SECONDS = 45.0
_MAX_SAMPLES = 40
_MIN_FRACTION_FOR_ETA = 0.03
_MIN_SECONDS_FOR_ETA = 4.0


def new_work() -> dict:
    """Fresh, JSON-friendly counters for one run (stored on the job)."""
    return {
        "unit": "",
        "total": 0,
        "read": 0,
        "chunk": 0,
        "embedded": 0,
        "embed_end": 0,
        "embed_frac": 0.0,
        "t0": None,
        "samples": [],
    }


def has_totals(work: dict | None) -> bool:
    return bool(work and work.get("total"))


def _event_units(event: dict, unit: str, key: str) -> int | None:
    value = event.get(f"{unit}_{key}")
    return max(0, value) if isinstance(value, int) and not isinstance(value, bool) else None


def record_event(work: dict, event: dict, now: float | None = None) -> None:
    """Fold one structured indexer event into ``work`` (counters only grow)."""
    if not work["total"]:
        for unit in ("bytes", "files"):
            total = event.get(f"{unit}_total")
            if isinstance(total, int) and not isinstance(total, bool) and total > 0:
                work["unit"], work["total"] = unit, total
                break
    if not work["total"]:
        return
    unit = work["unit"]
    done = _event_units(event, unit, "processed")
    if done is None:
        return
    done = min(done, work["total"])
    phase = event.get("phase")
    if phase == "extracting":
        work["read"] = max(work["read"], done)
    elif phase == "chunking":
        work["read"] = max(work["read"], done)
        work["chunk"] = max(work["chunk"], done)
    elif phase == "embedding":
        batches_done = event.get("batches_processed")
        batches_total = event.get("batches_total")
        if not isinstance(batches_done, int) or not isinstance(batches_total, int) or batches_total <= 0:
            return
        # Reading and splitting of this file batch finished before it embeds.
        work["read"] = max(work["read"], done)
        work["chunk"] = max(work["chunk"], done)
        work["embed_end"] = max(work["embed_end"], done)
        work["embed_frac"] = min(1.0, max(0, batches_done) / batches_total)
        if batches_done >= batches_total:
            work["embedded"] = max(work["embedded"], done)
    else:
        return
    stamp = time.time() if now is None else now
    if work["t0"] is None:
        work["t0"] = stamp
    _sample(work, stamp)


def _embedded_units(work: dict) -> float:
    pending = max(0, work["embed_end"] - work["embedded"])
    return work["embedded"] + pending * work["embed_frac"]


def stage_fractions(work: dict | None) -> dict[str, float]:
    """Completed share (0..1) of reading, splitting and embedding."""
    if not has_totals(work):
        return {"read": 0.0, "chunk": 0.0, "embed": 0.0}
    assert work is not None
    total = work["total"]
    return {
        "read": min(1.0, work["read"] / total),
        "chunk": min(1.0, work["chunk"] / total),
        "embed": min(1.0, _embedded_units(work) / total),
    }


def work_fraction(work: dict | None) -> float:
    """Overall share (0..1) of the indexing work that is really done."""
    if not has_totals(work):
        return 0.0
    stages = stage_fractions(work)
    return min(
        1.0,
        READ_WEIGHT * stages["read"] + CHUNK_WEIGHT * stages["chunk"] + EMBED_WEIGHT * stages["embed"],
    )


def progress_percent(work: dict | None) -> int:
    """Map the measured fraction onto the indexing span of the bar."""
    return WORK_START + int((WORK_END - WORK_START) * work_fraction(work))


def _sample(work: dict, stamp: float) -> None:
    fraction = work_fraction(work)
    samples = work["samples"]
    if samples and abs(samples[-1][1] - fraction) < 1e-9:
        return
    samples.append([stamp, fraction])
    if len(samples) > _MAX_SAMPLES:
        del samples[: len(samples) - _MAX_SAMPLES]


def eta_seconds(work: dict | None, now: float | None = None) -> int | None:
    """Seconds left at the observed pace, or ``None`` until it is trustworthy."""
    if not has_totals(work):
        return None
    assert work is not None
    samples = work["samples"]
    if not samples or work["t0"] is None:
        return None
    stamp = time.time() if now is None else now
    fraction = samples[-1][1]
    if fraction >= 1.0:
        return 0
    # Reading and splitting are a few percent of the work: the pace they show
    # says nothing about embedding, which is nearly all of the time. Until a
    # batch has really been embedded there is no evidence to extrapolate from.
    if stage_fractions(work)["embed"] <= 0.0:
        return None
    if fraction < _MIN_FRACTION_FOR_ETA or stamp - work["t0"] < _MIN_SECONDS_FOR_ETA:
        return None
    window_start = stamp - _WINDOW_SECONDS
    recent = [sample for sample in samples if sample[0] >= window_start] or samples[-1:]
    first_time, first_fraction = recent[0]
    # Measure up to *now*: a stalled run keeps lengthening the estimate.
    span = stamp - first_time
    gained = fraction - first_fraction
    if span < _MIN_SECONDS_FOR_ETA or gained <= 0:
        span, gained = stamp - work["t0"], fraction
    if gained <= 0:
        return None
    return max(1, int((1.0 - fraction) * span / gained))
