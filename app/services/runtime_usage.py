"""Persistent usage counters for the API services."""

from __future__ import annotations


def _runtime():
    from . import shared_runtime

    return shared_runtime


def _empty_usage_summary() -> dict:
    return {
        "messages_total": 0,
        "messages_by_engine": {},
        "tokens_estimated": 0,
        "model_counts": {},
        "collection_counts": {},
        "index_runs": 0,
        "first_seen": 0.0,
        "last_seen": 0.0,
    }


def _apply_usage_record(summary: dict, rec: dict) -> None:
    summary["messages_total"] = int(summary.get("messages_total") or 0) + 1
    summary["tokens_estimated"] = int(summary.get("tokens_estimated") or 0) + int(rec.get("est_tokens") or 0)

    by_engine = summary.setdefault("messages_by_engine", {})
    engine = str(rec.get("engine") or "unknown")
    by_engine[engine] = int(by_engine.get(engine) or 0) + 1

    by_model = summary.setdefault("model_counts", {})
    model = str(rec.get("model") or "unknown")
    by_model[model] = int(by_model.get(model) or 0) + 1

    by_collection = summary.setdefault("collection_counts", {})
    for collection_id in rec.get("collections") or []:
        key = str(collection_id)
        by_collection[key] = int(by_collection.get(key) or 0) + 1

    timestamp = float(rec.get("ts") or 0.0)
    if timestamp:
        first_seen = float(summary.get("first_seen") or 0.0)
        summary["first_seen"] = timestamp if first_seen == 0.0 else min(first_seen, timestamp)
        summary["last_seen"] = max(float(summary.get("last_seen") or 0.0), timestamp)


def _read_usage_summary_unlocked() -> dict | None:
    runtime = _runtime()
    try:
        with open(runtime.USAGE_SUMMARY_PATH, encoding="utf-8") as stream:
            data = runtime.json.load(stream)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def _write_usage_summary_unlocked(summary: dict) -> None:
    runtime = _runtime()
    runtime.atomic_write_json(runtime.USAGE_SUMMARY_PATH, summary)


def _record_usage(
    engine: str,
    model: str,
    project: str | None,
    collections: list[str] | None,
    est_tokens: int,
) -> None:
    """Append a single usage record. Fire-and-forget; never raises."""
    runtime = _runtime()
    try:
        runtime.os.makedirs(runtime.config.PERSIST_DIR, exist_ok=True)
        record = {
            "ts": runtime.time.time(),
            "engine": engine,
            "model": model,
            "project": project,
            "collections": list(collections or []),
            "est_tokens": int(est_tokens),
        }
        with runtime.state.usage_lock:
            with open(runtime.USAGE_PATH, "a", encoding="utf-8") as stream:
                stream.write(runtime.json.dumps(record, ensure_ascii=False) + "\n")
            summary = runtime._read_usage_summary_unlocked() or runtime._empty_usage_summary()
            runtime._apply_usage_record(summary, record)
            runtime._write_usage_summary_unlocked(summary)
    except Exception:
        runtime.LOG.debug("Best-effort operation failed", exc_info=True)


__all__ = [name for name in globals() if not name.startswith("__")]
