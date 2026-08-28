from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.responses import JSONResponse

from app.routes.health import resources as health_resources_route
from app.schemas import UsageRecordRequest
from app.services import collection_service, health_service, shared_runtime, sources_service, usage_service
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
    state.sources_cache[("sources:list", "docs")] = (0, [])
    state.retrieval_cache[("query",)] = (0, [])
    with pytest.raises(HTTPException) as raised:
        await sources_service.sources_delete("docs", "guide.md", object())
    assert raised.value.status_code == 500
    assert "private storage path" not in str(raised.value.detail)
    assert state.sources_cache
    assert state.retrieval_cache

    monkeypatch.setattr(sources_service, "_delete_collection_sources_sync", lambda _collection: 4)
    assert await sources_service.sources_delete_collection(
        sources_service.config.DEFAULT_COLLECTION_ID,
        object(),
    ) == {"deleted": 4, "collection": sources_service.config.DEFAULT_COLLECTION_ID}
    assert await sources_service.sources_delete_collection("docs", object()) == {"deleted": 4, "collection": "docs"}

    def fail_collection(*_args, **_kwargs):
        raise RuntimeError("transaction failed")

    monkeypatch.setattr(sources_service, "_delete_collection_sources_sync", fail_collection)
    state.sources_cache[("sources:list", "docs")] = (0, [])
    state.retrieval_cache[("query",)] = (0, [])
    with pytest.raises(HTTPException) as bulk_error:
        await sources_service.sources_delete_collection("docs", object())
    assert bulk_error.value.status_code == 500
    assert state.sources_cache
    assert state.retrieval_cache


def test_empty_collection_clear_is_a_noop_without_an_index(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sources_service.config, "PERSIST_DIR", str(tmp_path))
    monkeypatch.setattr(sources_service.config, "MANIFEST_PATH", str(tmp_path / "manifest.json"))

    assert sources_service._delete_collection_sources_sync(sources_service.config.DEFAULT_COLLECTION_ID) == 0


def test_source_delete_publishes_docstore_index_and_manifest_together(monkeypatch, tmp_path: Path) -> None:
    persist = tmp_path / "storage"
    persist.mkdir()
    manifest = persist / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "docs:guide.md": {
                    "manifest_schema": 2,
                    "sources": {
                        "alpha": {"source_id": "alpha"},
                        "beta": {"source_id": "beta"},
                    },
                },
                "other:keep.md": {"content_hash": "keep"},
            }
        ),
        encoding="utf-8",
    )
    (persist / "docstore.json").write_text("old", encoding="utf-8")

    docs = {
        "alpha": _Node("alpha", "alpha", collection_id="docs", rel_path="guide.md", source_id="alpha"),
        "beta": _Node("beta", "beta", collection_id="docs", rel_path="guide.md", source_id="beta"),
    }

    class Storage:
        def persist(self, persist_dir: str) -> None:
            root = Path(persist_dir)
            root.mkdir(parents=True, exist_ok=True)
            (root / "docstore.json").write_text(json.dumps(sorted(docs)), encoding="utf-8")
            (root / "index_store.json").write_text("index", encoding="utf-8")

    class Index:
        def __init__(self) -> None:
            self.docstore = SimpleNamespace(docs=docs)
            self.storage_context = Storage()

        def delete_nodes(self, node_ids, delete_from_docstore=True) -> None:
            for node_id in node_ids:
                docs.pop(node_id, None)

    index = Index()
    monkeypatch.setattr(shared_runtime.config, "PERSIST_DIR", str(persist))
    monkeypatch.setattr(shared_runtime.config, "MANIFEST_PATH", str(manifest))
    monkeypatch.setattr(shared_runtime.StorageContext, "from_defaults", lambda **_kwargs: object())
    monkeypatch.setattr(shared_runtime, "load_index_from_storage", lambda _storage: index)

    assert shared_runtime._delete_indexed_rel_paths_unlocked("docs", {"guide.md"}, source_id="alpha") == 1
    assert json.loads((persist / "docstore.json").read_text(encoding="utf-8")) == ["beta"]
    stored_manifest = json.loads(manifest.read_text(encoding="utf-8"))
    assert set(stored_manifest["docs:guide.md"]["sources"]) == {"beta"}
    assert stored_manifest["other:keep.md"] == {"content_hash": "keep"}


def test_collection_delete_publishes_one_recoverable_generation(monkeypatch, tmp_path: Path) -> None:
    persist = tmp_path / "storage"
    persist.mkdir()
    manifest = persist / "manifest.json"
    manifest.write_text(json.dumps({"docs:a": 1, "other:b": 2}), encoding="utf-8")
    (persist / "docstore.json").write_text("old", encoding="utf-8")
    docs = {
        "docs": _Node("docs", "docs", collection_id="docs", rel_path="a"),
        "other": _Node("other", "other", collection_id="other", rel_path="b"),
    }

    class Storage:
        def persist(self, persist_dir: str) -> None:
            root = Path(persist_dir)
            root.mkdir(parents=True, exist_ok=True)
            (root / "docstore.json").write_text(json.dumps(sorted(docs)), encoding="utf-8")

    class Index:
        def __init__(self) -> None:
            self.docstore = SimpleNamespace(docs=docs)
            self.storage_context = Storage()

        def delete_nodes(self, node_ids, delete_from_docstore=True) -> None:
            for node_id in node_ids:
                docs.pop(node_id, None)

    index = Index()
    monkeypatch.setattr(sources_service.config, "PERSIST_DIR", str(persist))
    monkeypatch.setattr(sources_service.config, "MANIFEST_PATH", str(manifest))
    monkeypatch.setattr(shared_runtime.StorageContext, "from_defaults", lambda **_kwargs: object())
    monkeypatch.setattr(shared_runtime, "load_index_from_storage", lambda _storage: index)

    assert sources_service._delete_collection_sources_sync("docs") == 1
    assert json.loads((persist / "docstore.json").read_text(encoding="utf-8")) == ["other"]
    assert json.loads(manifest.read_text(encoding="utf-8")) == {"other:b": 2}


@pytest.mark.asyncio
async def test_collection_delete_keeps_metadata_sources_and_caches_on_publish_failure(
    monkeypatch,
    tmp_path: Path,
) -> None:
    collections_path = tmp_path / "collections.json"
    collections_path.write_text(
        json.dumps(
            {
                "collections": [
                    {"id": "default", "name": "Default"},
                    {"id": "docs", "name": "Docs"},
                ]
            }
        ),
        encoding="utf-8",
    )
    sources_root = tmp_path / "local" / "collections" / "docs"
    sources_root.mkdir(parents=True)
    (sources_root / "guide.md").write_text("keep", encoding="utf-8")
    monkeypatch.setattr(collection_service.config, "COLLECTIONS_PATH", str(collections_path))
    monkeypatch.setattr(collection_service.config, "LOCAL_SOURCES_DIR", str(tmp_path / "local"))
    monkeypatch.setattr(collection_service, "_authorize_system", lambda _request: None)

    async def run(function, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr(collection_service, "run_in_threadpool", run)

    def fail_publish(_collection: str) -> int:
        raise RuntimeError("publish failed")

    monkeypatch.setattr(collection_service, "_delete_indexed_collection", fail_publish)
    state.collection_retrievers[("docs",)] = object()
    state.retrieval_cache[("query",)] = (0, [])
    state.sources_cache[("sources:list", "docs")] = (0, [])
    try:
        with pytest.raises(RuntimeError, match="publish failed"):
            await collection_service.collections_delete("docs", object())

        assert {item["id"] for item in json.loads(collections_path.read_text(encoding="utf-8"))["collections"]} == {
            "default",
            "docs",
        }
        assert sources_root.exists()
        assert state.collection_retrievers
        assert state.retrieval_cache
        assert state.sources_cache
    finally:
        state.collection_retrievers.clear()
        state.retrieval_cache.clear()
        state.sources_cache.clear()


@pytest.mark.asyncio
async def test_collection_delete_cleans_post_commit_state_on_success(monkeypatch, tmp_path: Path) -> None:
    collections_path = tmp_path / "collections.json"
    collections_path.write_text(
        json.dumps(
            {
                "collections": [
                    {"id": "default", "name": "Default"},
                    {"id": "docs", "name": "Docs"},
                ]
            }
        ),
        encoding="utf-8",
    )
    sources_root = tmp_path / "local" / "collections" / "docs"
    sources_root.mkdir(parents=True)
    monkeypatch.setattr(collection_service.config, "COLLECTIONS_PATH", str(collections_path))
    monkeypatch.setattr(collection_service.config, "LOCAL_SOURCES_DIR", str(tmp_path / "local"))
    monkeypatch.setattr(collection_service, "_authorize_system", lambda _request: None)
    monkeypatch.setattr(collection_service, "_delete_indexed_collection", lambda _collection: 2)
    monkeypatch.setattr(collection_service, "build_engine", lambda: True)

    async def run(function, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr(collection_service, "run_in_threadpool", run)
    state.collection_retrievers[("docs",)] = object()
    state.retrieval_cache[("query",)] = (0, [])
    state.sources_cache[("sources:list", "docs")] = (0, [])
    try:
        result = await collection_service.collections_delete("docs", object())

        assert result == {"ok": True, "deleted_nodes": 2}
        assert {item["id"] for item in json.loads(collections_path.read_text(encoding="utf-8"))["collections"]} == {
            "default",
        }
        assert not sources_root.exists()
        assert not state.collection_retrievers
        assert not state.retrieval_cache
        assert not state.sources_cache
    finally:
        state.collection_retrievers.clear()
        state.retrieval_cache.clear()
        state.sources_cache.clear()


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
    monkeypatch.setattr(health_service, "_ollama_available_cached", lambda: True)
    assert (await health_service.ready())["ok"] is True

    virtual_memory = SimpleNamespace(total=100, available=60, used=40, percent=40.0)
    monkeypatch.setitem(sys.modules, "psutil", SimpleNamespace(virtual_memory=lambda: virtual_memory))
    assert (await health_service.resources())["ram"] == {
        "total": 100,
        "available": 60,
        "used": 40,
        "percent": 40.0,
    }


@pytest.mark.asyncio
async def test_public_health_and_resources_redact_host_details(monkeypatch) -> None:
    monkeypatch.setattr(health_service, "_health_authority", lambda _request: (False, set(), False))
    monkeypatch.setattr(health_service, "_ollama_available_cached", lambda: False)

    health = await health_service.health(object())
    resources = await health_service.resources(object())

    assert "projects" not in health
    assert "collections" not in health
    assert "hardware" not in health
    assert "models" not in health
    assert set(resources) == {"ok", "ram", "vram", "profile"}
    assert resources["ram"] is None or set(resources["ram"]) == {"percent"}


@pytest.mark.asyncio
async def test_paired_health_never_advertises_host_management(monkeypatch) -> None:
    monkeypatch.setattr(health_service, "_health_authority", lambda _request: (True, {"web"}, False))
    monkeypatch.setattr(health_service, "_ollama_available_cached", lambda: False)

    health = await health_service.health(object())

    assert health["capabilities"]["manage_system"] is False


@pytest.mark.parametrize(
    ("scopes", "private"),
    [(["chat"], False), (["web"], False), (["read_private"], True)],
)
def test_device_health_details_require_read_private_scope(monkeypatch, scopes, private) -> None:
    request = SimpleNamespace(
        headers={health_service.DEVICE_TOKEN_HEADER: "device-token"},
        client=SimpleNamespace(host="192.168.1.55"),
        state=SimpleNamespace(),
    )
    monkeypatch.setattr(health_service.admin_auth, "_client_host", lambda _request: "192.168.1.55")
    monkeypatch.setattr(health_service.admin_auth, "_is_local_client", lambda _host: False)
    monkeypatch.setattr(health_service.admin_auth, "_valid_admin_token", lambda _request: False)
    monkeypatch.setattr(health_service, "device_for_token", lambda _token: {"scopes": scopes})

    assert health_service._health_authority(request)[0] is private


def test_device_health_details_accept_http_only_cookie(monkeypatch) -> None:
    request = SimpleNamespace(
        headers={},
        cookies={health_service.admin_auth.DEVICE_TOKEN_COOKIE: "device-token"},
        client=SimpleNamespace(host="192.168.1.55"),
        state=SimpleNamespace(),
    )
    monkeypatch.setattr(health_service.admin_auth, "_client_host", lambda _request: "192.168.1.55")
    monkeypatch.setattr(health_service.admin_auth, "_is_local_client", lambda _host: False)
    monkeypatch.setattr(health_service.admin_auth, "_valid_admin_token", lambda _request: False)
    monkeypatch.setattr(
        health_service,
        "device_for_token",
        lambda token: {"scopes": ["read_private"]} if token == "device-token" else None,
    )

    assert health_service._health_authority(request)[0] is True


@pytest.mark.asyncio
async def test_private_resources_report_unified_memory_vram(monkeypatch) -> None:
    monkeypatch.setattr(
        health_service.config,
        "HARDWARE",
        {"gpu": {"unified_memory": True, "name": "integrated"}, "ram": {"total_bytes": 4096}},
    )
    monkeypatch.setattr(health_service, "_health_authority", lambda _request: (True, set(), True))

    resources = await health_service.resources(object())
    routed_resources = await health_resources_route(object())

    assert resources["vram"]["total"] == 4096
    assert resources["vram"]["unified_memory"] is True
    assert routed_resources["vram"]["total"] == 4096


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
    assert recorded[0][2] == "project"
    assert recorded[0][-1] == 0


@pytest.mark.asyncio
async def test_usage_stats_rebuilds_missing_or_unreadable_logs(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(usage_service, "USAGE_PATH", str(tmp_path / "usage.jsonl"))
    monkeypatch.setattr(usage_service, "_authorize_system", lambda _request: None)
    monkeypatch.setattr(usage_service, "_read_usage_summary_unlocked", lambda: None)
    assert usage_service._build_usage_summary_from_log_unlocked()["messages_total"] == 0

    usage_path = Path(usage_service.USAGE_PATH)
    usage_path.write_text("\n", encoding="utf-8")
    monkeypatch.setattr(usage_service, "_write_usage_summary_unlocked", lambda _summary: None)
    assert usage_service._build_usage_summary_from_log_unlocked()["messages_total"] == 0

    monkeypatch.setattr(usage_service.os.path, "isfile", lambda _path: True)

    def fail_open(*_args, **_kwargs):
        raise OSError("unavailable")

    monkeypatch.setattr(usage_service, "open", fail_open, raising=False)
    assert await usage_service.usage_stats(object()) == {
        "messages_total": 0,
        "messages_by_engine": {},
        "tokens_estimated": 0,
        "top_collections": [],
        "top_models": [],
        "index_runs": 0,
        "first_seen": 0.0,
        "last_seen": 0.0,
    }
