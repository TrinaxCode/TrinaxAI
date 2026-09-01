"""Usage accounting and statistics services."""

from __future__ import annotations

from collections import deque

from .runtime_usage import (
    _USAGE_MAX_LINE_BYTES,
    _normalize_summary,
    _normalize_usage_record,
    _retained_usage_records,
    _usage_limits,
    _write_usage_log_unlocked,
)

# ruff: noqa: F405
from .shared_runtime import (
    LOG,
    USAGE_PATH,
    Request,
    UsageRecordRequest,
    _apply_usage_record,
    _authorize_system,
    _empty_usage_summary,
    _read_usage_summary_unlocked,
    _record_usage,
    _write_usage_summary_unlocked,
    json,
    os,
    state,
)


def _usage_summary_response(summary: dict) -> dict:
    summary = _normalize_summary(summary)
    by_engine = summary["messages_by_engine"]
    by_model = summary["model_counts"]
    by_col = summary["collection_counts"]
    return {
        "messages_total": int(summary.get("messages_total") or 0),
        "messages_by_engine": dict(sorted(by_engine.items(), key=lambda kv: -kv[1])),
        "tokens_estimated": int(summary.get("tokens_estimated") or 0),
        "top_collections": [{"id": k, "count": v} for k, v in sorted(by_col.items(), key=lambda kv: -kv[1])[:10]],
        "top_models": [{"model": k, "count": v} for k, v in sorted(by_model.items(), key=lambda kv: -kv[1])[:10]],
        "index_runs": int(summary.get("index_runs") or 0),
        "first_seen": float(summary.get("first_seen") or 0.0),
        "last_seen": float(summary.get("last_seen") or 0.0),
    }


def _build_usage_summary_from_log_unlocked(previous: dict | None = None) -> dict:
    summary = _empty_usage_summary()
    if previous:
        summary["index_runs"] = previous.get("index_runs", 0)
    if not os.path.isfile(USAGE_PATH):
        return summary
    try:
        max_records, _retention, _max_dimensions = _usage_limits()
        records: deque[dict] = deque(maxlen=max_records)
        with open(USAGE_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if len(line.encode("utf-8", errors="ignore")) > _USAGE_MAX_LINE_BYTES:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if isinstance(rec, dict):
                    normalized = _normalize_usage_record(rec)
                    if normalized is not None:
                        records.append(normalized)
        retained_records = _retained_usage_records(list(records))
        _write_usage_log_unlocked(retained_records, USAGE_PATH)
        for record in retained_records:
            _apply_usage_record(summary, record)
        _write_usage_summary_unlocked(summary)
    except Exception:
        LOG.debug("Best-effort operation failed", exc_info=True)
    return summary


async def usage_record(req: UsageRecordRequest, request: Request):
    """Record local usage from frontend-only flows such as direct Ollama chat."""
    _authorize_system(request)
    engine = (req.engine or "unknown").strip()[:40]
    model = (req.model or "unknown").strip()[:120]
    project = (req.project or "").strip()[:120] or None
    collections = [str(c)[:120] for c in (req.collections or []) if str(c).strip()][:50]
    est_tokens = min(10_000_000, max(0, int(req.est_tokens or 0)))
    _record_usage(engine, model, project, collections, est_tokens)
    return {"ok": True}


async def usage_stats(request: Request):
    """Aggregate local usage stats from storage/usage.jsonl."""
    _authorize_system(request)
    with state.usage_lock:
        previous = _read_usage_summary_unlocked()
        if os.path.isfile(USAGE_PATH):
            summary = _build_usage_summary_from_log_unlocked(previous)
        else:
            summary = previous or _build_usage_summary_from_log_unlocked()
        return _usage_summary_response(summary)


__all__ = [name for name in globals() if not name.startswith("__")]
