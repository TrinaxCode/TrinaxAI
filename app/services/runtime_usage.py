"""Persistent usage counters for the API services."""

from __future__ import annotations

import math
from collections import deque

_USAGE_MAX_RECORDS = 10_000
_USAGE_RETENTION_SECONDS = 90 * 24 * 60 * 60
_USAGE_MAX_DIMENSIONS = 1_000
_USAGE_MAX_LINE_BYTES = 256 * 1024
_USAGE_MAX_TOKENS = 10_000_000
_USAGE_OTHER_KEY = "__other__"


def _runtime():
    from . import shared_runtime

    return shared_runtime


def _usage_limits() -> tuple[int, int, int]:
    config = _runtime().config
    return (
        config._env_int("TRINAXAI_USAGE_MAX_RECORDS", _USAGE_MAX_RECORDS, minimum=1, maximum=100_000),
        config._env_int(
            "TRINAXAI_USAGE_RETENTION_SECONDS",
            _USAGE_RETENTION_SECONDS,
            minimum=1,
            maximum=10 * 365 * 24 * 60 * 60,
        ),
        config._env_int("TRINAXAI_USAGE_MAX_DIMENSIONS", _USAGE_MAX_DIMENSIONS, minimum=1, maximum=10_000),
    )


def _safe_int(value, default: int = 0, maximum: int = 10**12) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return min(maximum, max(0, parsed))


def _safe_timestamp(value, *, allow_missing: bool = False) -> float | None:
    if value is None and allow_missing:
        return 0.0
    try:
        timestamp = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return timestamp if math.isfinite(timestamp) and timestamp > 0 else None


def _bounded_key(value, maximum: int) -> str:
    key = str(value or "").strip()[:maximum]
    return key or "unknown"


def _increment_dimension(mapping: dict, key: str, count: int, limit: int) -> None:
    if key in mapping:
        mapping[key] = _safe_int(mapping[key]) + count
        return
    # Reserve one slot for a bounded overflow bucket.
    if limit > 1 and len(mapping) < limit - 1:
        mapping[key] = count
        return
    mapping[_USAGE_OTHER_KEY] = _safe_int(mapping.get(_USAGE_OTHER_KEY)) + count


def _normalize_summary(summary: dict | None) -> dict:
    source = summary if isinstance(summary, dict) else {}
    max_records, _retention, max_dimensions = _usage_limits()
    result = _empty_usage_summary()
    result["messages_total"] = min(max_records, _safe_int(source.get("messages_total")))
    result["tokens_estimated"] = _safe_int(source.get("tokens_estimated"), maximum=max_records * _USAGE_MAX_TOKENS)
    result["index_runs"] = _safe_int(source.get("index_runs"))
    for field, key_limit in (
        ("messages_by_engine", 40),
        ("model_counts", 120),
        ("collection_counts", 120),
    ):
        values = source.get(field)
        if isinstance(values, dict):
            for key, value in values.items():
                count = _safe_int(value)
                if count:
                    _increment_dimension(result[field], _bounded_key(key, key_limit), count, max_dimensions)
    first_seen = _safe_timestamp(source.get("first_seen"))
    last_seen = _safe_timestamp(source.get("last_seen"))
    result["first_seen"] = first_seen or 0.0
    result["last_seen"] = last_seen or 0.0
    return result


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


def _normalize_usage_record(rec: dict, *, allow_missing_timestamp: bool = False) -> dict | None:
    if not isinstance(rec, dict):
        return None
    timestamp = _safe_timestamp(rec.get("ts"), allow_missing=allow_missing_timestamp)
    if timestamp is None:
        return None
    raw_collections = rec.get("collections")
    collections = []
    if isinstance(raw_collections, (list, tuple, set, frozenset)):
        for value in raw_collections:
            key = _bounded_key(value, 120)
            if key != "unknown":
                collections.append(key)
            if len(collections) >= 50:
                break
    try:
        project = str(rec.get("project") or "").strip()[:120] or None
    except Exception:
        project = None
    return {
        "ts": timestamp,
        "engine": _bounded_key(rec.get("engine"), 40),
        "model": _bounded_key(rec.get("model"), 120),
        "project": project,
        "collections": collections,
        "est_tokens": _safe_int(rec.get("est_tokens"), maximum=_USAGE_MAX_TOKENS),
    }


def _apply_usage_record(summary: dict, rec: dict) -> None:
    normalized = _normalize_usage_record(rec, allow_missing_timestamp=True)
    if normalized is None:
        return
    current = _normalize_summary(summary)
    summary.clear()
    summary.update(current)
    max_records, _retention, max_dimensions = _usage_limits()
    summary["messages_total"] = min(max_records, summary["messages_total"] + 1)
    summary["tokens_estimated"] = min(
        max_records * _USAGE_MAX_TOKENS,
        summary["tokens_estimated"] + normalized["est_tokens"],
    )
    _increment_dimension(summary["messages_by_engine"], normalized["engine"], 1, max_dimensions)
    _increment_dimension(summary["model_counts"], normalized["model"], 1, max_dimensions)
    for collection_id in normalized["collections"]:
        _increment_dimension(summary["collection_counts"], collection_id, 1, max_dimensions)
    timestamp = normalized["ts"]
    if timestamp:
        first_seen = summary["first_seen"]
        summary["first_seen"] = timestamp if not first_seen else min(first_seen, timestamp)
        summary["last_seen"] = max(summary["last_seen"], timestamp)


def _read_usage_records_unlocked() -> list[dict]:
    runtime = _runtime()
    max_records, _retention, _max_dimensions = _usage_limits()
    records: deque[dict] = deque(maxlen=max_records)
    try:
        with open(runtime.USAGE_PATH, encoding="utf-8") as stream:
            for line in stream:
                if len(line.encode("utf-8", errors="ignore")) > _USAGE_MAX_LINE_BYTES:
                    continue
                try:
                    record = _normalize_usage_record(runtime.json.loads(line))
                except (TypeError, ValueError, OverflowError):
                    continue
                if record is not None:
                    records.append(record)
    except (OSError, UnicodeError):
        pass
    return list(records)


def _retained_usage_records(records: list[dict], now: float | None = None) -> list[dict]:
    runtime = _runtime()
    max_records, retention_seconds, _max_dimensions = _usage_limits()
    current = runtime.time.time() if now is None else now
    try:
        current = float(current)
    except (TypeError, ValueError, OverflowError):
        return []
    if not math.isfinite(current):
        return []
    cutoff = current - retention_seconds
    valid = []
    for record in records:
        normalized = _normalize_usage_record(record)
        if normalized is not None and normalized["ts"] >= cutoff:
            valid.append(normalized)
    valid.sort(key=lambda item: item["ts"])
    return valid[-max_records:]


def _write_usage_log_unlocked(records: list[dict], path: str | None = None) -> None:
    runtime = _runtime()
    path = path or runtime.USAGE_PATH
    directory = runtime.os.path.dirname(path) or "."
    runtime.os.makedirs(directory, exist_ok=True)
    temporary = None
    try:
        with runtime.tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=directory, prefix=".usage-", suffix=".tmp", delete=False
        ) as stream:
            temporary = stream.name
            for record in records:
                stream.write(runtime.json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
        runtime.os.replace(temporary, path)
        temporary = None
    finally:
        if temporary:
            try:
                runtime.os.unlink(temporary)
            except OSError:
                pass


def _read_usage_summary_unlocked() -> dict | None:
    runtime = _runtime()
    try:
        with open(runtime.USAGE_SUMMARY_PATH, encoding="utf-8") as stream:
            data = runtime.json.load(stream)
        return _normalize_summary(data) if isinstance(data, dict) else None
    except (OSError, ValueError, TypeError, UnicodeError):
        return None


def _write_usage_summary_unlocked(summary: dict) -> None:
    runtime = _runtime()
    runtime.atomic_write_json(runtime.USAGE_SUMMARY_PATH, _normalize_summary(summary))


def _record_usage(
    engine: str,
    model: str,
    project: str | None,
    collections: list[str] | None,
    est_tokens: int,
) -> None:
    """Append a bounded usage record. Fire-and-forget; never raises."""
    runtime = _runtime()
    try:
        timestamp = runtime.time.time()
        record = _normalize_usage_record(
            {
                "ts": timestamp,
                "engine": engine,
                "model": model,
                "project": project,
                "collections": list(collections or []),
                "est_tokens": est_tokens,
            }
        )
        if record is None:
            return
        runtime.os.makedirs(runtime.config.PERSIST_DIR, exist_ok=True)
        with runtime.state.usage_lock:
            # ponytail: one global lock and O(n) rewrite; the 10k-record ceiling keeps it bounded.
            records = _retained_usage_records([*_read_usage_records_unlocked(), record], now=timestamp)
            _write_usage_log_unlocked(records)
            previous = _read_usage_summary_unlocked() or _empty_usage_summary()
            summary = _empty_usage_summary()
            summary["index_runs"] = previous.get("index_runs", 0)
            for retained in records:
                _apply_usage_record(summary, retained)
            _write_usage_summary_unlocked(summary)
    except Exception:
        runtime.LOG.debug("Best-effort operation failed", exc_info=True)


__all__ = [name for name in globals() if not name.startswith("__")]
