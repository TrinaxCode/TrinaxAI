from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from app.services import shared_runtime
from app.services.engine_state import state


def test_collection_normalization_and_usage_helpers(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "collections.json"
    path.write_text(
        json.dumps(
            {
                "collections": [
                    {"id": "Docs", "name": "Docs", "created_at": 1},
                    {"id": "docs", "name": "duplicate", "created_at": 2},
                    "bad",
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(shared_runtime.config, "COLLECTIONS_PATH", str(path))
    collections = shared_runtime._read_collections_unlocked()
    assert collections[0]["id"] == shared_runtime.config.DEFAULT_COLLECTION_ID
    assert collections[1]["id"] == "docs"
    shared_runtime._write_collections_unlocked(collections)
    assert json.loads(path.read_text(encoding="utf-8"))["collections"] == collections

    summary = shared_runtime._empty_usage_summary()
    shared_runtime._apply_usage_record(
        summary,
        {"engine": "rag", "model": "model", "collections": ["docs", "docs"], "est_tokens": 4, "ts": 20},
    )
    shared_runtime._apply_usage_record(summary, {"engine": "chat", "model": "other", "ts": 10})
    assert summary["messages_total"] == 2
    assert summary["tokens_estimated"] == 4
    assert summary["first_seen"] == 10 and summary["last_seen"] == 20
    assert summary["collection_counts"]["docs"] == 2


def test_llm_cache_key_includes_generation_knobs(monkeypatch) -> None:
    state.llm_cache.clear()
    created = []
    monkeypatch.setattr(shared_runtime.config, "make_llm", lambda **kwargs: created.append(kwargs) or object())
    first = shared_runtime.get_llm("model", temperature=0.1)
    assert shared_runtime.get_llm("model", temperature=0.1) is first
    second = shared_runtime.get_llm("model", temperature=0.2, num_ctx=2048)
    assert second is not first
    assert len(created) == 2
    state.llm_cache.clear()


def test_research_serialize_and_source_manifest_trimming(tmp_path: Path, monkeypatch) -> None:
    node = SimpleNamespace(
        node_id="node-1",
        text="ignored",
        score=0.12345,
        metadata={"rel_path": "docs.md", "collection_id": "docs", "page": 2, "secret": "no"},
        get_content=lambda: "content",
    )
    payload = shared_runtime._research_serialize_node(node)
    assert payload["id"] == "node-1" and payload["score"] == 0.1235
    assert "secret" not in payload["metadata"]

    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "docs:guide.md": {
                    "manifest_schema": 1,
                    "sources": {"source-a": {"hash": "a"}, "source-b": {"hash": "b"}},
                },
                "other:x": 1,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(shared_runtime.config, "MANIFEST_PATH", str(manifest))
    shared_runtime._trim_manifest_keys({"docs:guide.md"}, source_id="source-a")
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert set(data["docs:guide.md"]["sources"]) == {"source-b"}
    shared_runtime._trim_manifest_keys({"docs:guide.md"}, source_id="source-b")
    assert "docs:guide.md" not in json.loads(manifest.read_text(encoding="utf-8"))


def test_run_model_task_uses_slots_and_inference_lock(monkeypatch) -> None:
    calls = []

    class Lock:
        def __enter__(self):
            calls.append("enter")
            return self

        def __exit__(self, *_args):
            calls.append("exit")
            return False

    monkeypatch.setattr(shared_runtime, "_inference_process_lock", lambda: Lock())
    shared_runtime._model_slots = Lock()
    assert shared_runtime._run_model_task(lambda value: value + 1, 2) == 3
    assert calls == ["enter", "enter", "exit", "exit"]
