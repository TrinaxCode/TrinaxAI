"""Usage accounting and statistics services."""

from __future__ import annotations

# ruff: noqa: F405
from .shared_runtime import *  # noqa: F403


def _usage_summary_response(summary: dict) -> dict:
    by_engine = {str(k): int(v) for k, v in (summary.get("messages_by_engine") or {}).items()}
    by_model = {str(k): int(v) for k, v in (summary.get("model_counts") or {}).items()}
    by_col = {str(k): int(v) for k, v in (summary.get("collection_counts") or {}).items()}
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


def _build_usage_summary_from_log_unlocked() -> dict:
    summary = _empty_usage_summary()
    if not os.path.isfile(USAGE_PATH):
        return summary
    try:
        with open(USAGE_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if isinstance(rec, dict):
                    _apply_usage_record(summary, rec)
        _write_usage_summary_unlocked(summary)
    except Exception:
        LOG.debug("Best-effort operation failed", exc_info=True)
    return summary


async def usage_record(req: UsageRecordRequest, request: Request):
    """Record local usage from frontend-only flows such as direct Ollama chat."""
    _authorize_system(request)
    engine = (req.engine or "unknown").strip()[:40]
    model = (req.model or "unknown").strip()[:120]
    collections = [str(c)[:120] for c in (req.collections or []) if str(c).strip()]
    _record_usage(engine, model, req.project, collections, max(0, int(req.est_tokens or 0)))
    return {"ok": True}


async def usage_stats(request: Request):
    """Aggregate local usage stats from storage/usage.jsonl."""
    _authorize_system(request)
    with state.usage_lock:
        summary = _read_usage_summary_unlocked()
        if summary is None:
            summary = _build_usage_summary_from_log_unlocked()
        return _usage_summary_response(summary)


__all__ = [name for name in globals() if not name.startswith("__")]
