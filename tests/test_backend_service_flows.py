from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.responses import JSONResponse

from app.schemas import UsageRecordRequest
from app.services import health_service, sources_service, usage_service
from app.services.engine_state import state


class _Node:
    def __init__(self, node_id: str, text: str, **metadata) -> None:
        self.node_id = node_id
        self.text = text
        self.metadata = metadata
        self.score = 0.87654

    def get_content(self) -> str:
        return self.text


def test_source_browsing_groups_filters_paginates_and_uses_cache(monkeypatch) -> None:
    nodes = {
        "one": _Node(
            "one",
            "Alpha first",
            collection_id="docs",
            rel_path="guide.md",
            source_id="root-a",
            mtime=1,
        ),
        "two": _Node(
            "two",
            "Beta second",
            collection_id="docs",
            rel_path="guide.md",
            source_id="root-a",
            mtime=2,
        ),
        "other": _Node("other", "Other", collection_id="other", rel_path="other.md"),
    }
    monkeypatch.setattr(sources_service, "_authorize_system", lambda _request: None)
    monkeypatch.setattr(state, "fusion_retriever", object())
    monkeypatch.setattr(state, "index_docstore", SimpleNamespace(docs=nodes))
    state.sources_cache.clear()

    listed = sources_service.sources_list("docs", object())
    assert listed["sources"] == [
        {
            "file": "guide.md",
            "source_id": "root-a",
            "chunks": 2,
            "size": len(b"Alpha first") + len(b"Beta second"),
            "mtime": 2,
            "preview": "Alpha first",
        }
    ]
    assert sources_service.sources_list("docs", object()) == listed

    page = sources_service.sources_chunks(
        "docs",
        "guide.md",
        limit=999,
        offset=-2,
        q="beta",
        source_id="root-a",
        request=object(),
    )
    assert page["total"] == 1
    assert page["chunks"][0]["id"] == "two"
    assert page["chunks"][0]["score"] == 0.8765
    assert page["query"] == "beta"


@pytest.mark.asyncio
async def test_source_deletion_clears_caches_and_masks_backend_failures(monkeypatch) -> None:
    monkeypatch.setattr(sources_service, "_authorize_system", lambda _request: None)

    async def run(function, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr(sources_service, "run_in_threadpool", run)
    monkeypatch.setattr(sources_service, "_delete_indexed_rel_paths", lambda *_args, **_kwargs: 2)
    monkeypatch.setattr(sources_service, "build_engine", lambda: True)
    state.sources_cache.clear()
    state.sources_cache[("sources:list", "docs")] = (0, [])
    state.sources_cache[("sources:chunks", "docs", "guide.md", None)] = (0, [])
    state.retrieval_cache[("query",)] = (0, [])

    result = await sources_service.sources_delete("docs", "guide.md", object())
    assert result["deleted"] == 2
    assert not state.sources_cache
    assert not state.retrieval_cache

    def fail(*_args, **_kwargs):
        raise RuntimeError("private storage path")

    monkeypatch.setattr(sources_service, "_delete_indexed_rel_paths", fail)
    with pytest.raises(HTTPException) as raised:
        await sources_service.sources_delete("docs", "guide.md", object())
    assert raised.value.status_code == 500
    assert "private storage path" not in str(raised.value.detail)

    with pytest.raises(HTTPException) as protected:
        await sources_service.sources_delete_collection(sources_service.config.DEFAULT_COLLECTION_ID, object())
    assert protected.value.status_code == 400

    monkeypatch.setattr(sources_service, "_delete_collection_sources_sync", lambda _collection: 4)
    assert await sources_service.sources_delete_collection("docs", object()) == {"deleted": 4, "collection": "docs"}


@pytest.mark.asyncio
async def test_health_readiness_and_resources_cover_online_and_degraded_modes(monkeypatch) -> None:
    class Client:
        def __init__(self, **_kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def get(self, _url):
            return SimpleNamespace(status_code=200)

    monkeypatch.setattr(health_service.httpx, "Client", Client)
    monkeypatch.setattr(state, "health_ollama_checked_at", 0.0)
    assert health_service._ollama_available_cached() is True
    assert health_service._ollama_available_cached() is True

    monkeypatch.setattr(health_service, "_ollama_available_cached", lambda: False)
    readiness = await health_service.ready()
    assert isinstance(readiness, JSONResponse)
    assert readiness.status_code == 503

    virtual_memory = SimpleNamespace(total=100, available=60, used=40, percent=40.0)
    monkeypatch.setitem(sys.modules, "psutil", SimpleNamespace(virtual_memory=lambda: virtual_memory))
    assert (await health_service.resources())["ram"] == {
        "total": 100,
        "available": 60,
        "used": 40,
        "percent": 40.0,
    }


@pytest.mark.asyncio
async def test_usage_rebuilds_corrupt_log_and_records_sanitized_values(monkeypatch, tmp_path: Path) -> None:
    usage_path = tmp_path / "usage.jsonl"
    usage_path.write_text(
        "\n".join(
            [
                "{broken",
                json.dumps({"ts": 1, "engine": "rag", "model": "model", "collections": ["docs"], "est_tokens": 4}),
                "[]",
                "",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(usage_service, "USAGE_PATH", str(usage_path))
    monkeypatch.setattr(usage_service, "_authorize_system", lambda _request: None)
    monkeypatch.setattr(usage_service, "_write_usage_summary_unlocked", lambda _summary: None)

    summary = usage_service._build_usage_summary_from_log_unlocked()
    assert usage_service._usage_summary_response(summary)["messages_total"] == 1

    recorded = []
    monkeypatch.setattr(usage_service, "_record_usage", lambda *args: recorded.append(args))
    result = await usage_service.usage_record(
        UsageRecordRequest(
            engine=" e " * 30,
            model=" m " * 100,
            project="project",
            collections=["docs"],
            est_tokens=-10,
        ),
        object(),
    )
    assert result == {"ok": True}
    assert len(recorded[0][0]) <= 40
    assert len(recorded[0][1]) <= 120
    assert recorded[0][-1] == 0
