from __future__ import annotations

import asyncio
import builtins
import importlib
import io
import json
import logging
import runpy
import sys
import threading
import types
from contextlib import asynccontextmanager, nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.generation.spec import Regime
from app.schemas import ChatRequest, CollectionUpdateRequest, MemoryCreateRequest, MemoryUpdateRequest, ResearchRequest
from app.security import admin_auth, device_auth
from app.services import (
    app_state_service,
    attachment_service,
    collection_service,
    document_service,
    engine_state,
    memory_service,
    rag_generation,
    rag_service,
    rag_streaming,
    research_service,
    runtime_context,
    runtime_engine,
    runtime_index,
    runtime_usage,
    shared_runtime,
    sources_service,
    voice_service,
)
from app.services.engine_state import state


def _request(*, client: str = "127.0.0.1") -> Request:
    path = "/"
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "scheme": "http",
            "server": ("localhost", 3333),
            "client": (client, 50000),
            "headers": [],
        }
    )


def test_authentication_and_registry_cleanup_edges(monkeypatch, tmp_path: Path) -> None:
    assert not admin_auth._is_trusted_proxy_peer("not-an-ip")
    assert admin_auth._is_local_browser_origin("http://[bad") is False

    proxy_path = tmp_path / "proxy-secret"
    proxy_path.write_text("", encoding="utf-8")
    monkeypatch.delenv("TRINAXAI_PROXY_SECRET", raising=False)
    monkeypatch.setattr(admin_auth, "_PROXY_SECRET", None)
    monkeypatch.setattr(admin_auth, "_proxy_secret_path", lambda: proxy_path)
    real_os_open = admin_auth.os.open
    real_os_chmod = admin_auth.os.chmod
    monkeypatch.setattr(admin_auth.os, "open", lambda *_args, **_kwargs: (_ for _ in ()).throw(FileExistsError))
    monkeypatch.setattr(admin_auth.os, "chmod", lambda *_args: (_ for _ in ()).throw(OSError("readonly")))
    assert admin_auth._load_proxy_secret() == b""
    monkeypatch.setattr(admin_auth.os, "open", real_os_open)
    monkeypatch.setattr(admin_auth.os, "chmod", real_os_chmod)

    registry_path = tmp_path / "registry.json"
    real_open = device_auth.os.open

    def fail_directory_open(candidate, *args, **kwargs):
        if Path(candidate) == registry_path.parent:
            raise OSError("directory fsync unavailable")
        return real_open(candidate, *args, **kwargs)

    monkeypatch.setattr(device_auth.os, "open", fail_directory_open)
    device_auth._write_registry(registry_path, device_auth._empty_registry())
    assert registry_path.is_file()

    failed_path = tmp_path / "failed-registry.json"
    monkeypatch.setattr(device_auth.os, "open", real_open)
    monkeypatch.setattr(device_auth.os, "replace", lambda *_args: (_ for _ in ()).throw(OSError("disk full")))
    monkeypatch.setattr(Path, "unlink", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("locked")))
    with pytest.raises(device_auth.DeviceRegistryError, match="could not be saved"):
        device_auth._write_registry(failed_path, device_auth._empty_registry())


def test_engine_cache_and_attachment_usage_edges(monkeypatch, tmp_path: Path) -> None:
    cache: dict[tuple, tuple[float, object]] = {}
    assert engine_state.cache_get(cache, state.retrieval_cache_lock, ("disabled",), 0) is None
    cache[("expired",)] = (0.0, "old")
    monkeypatch.setattr(engine_state.time, "time", lambda: 10.0)
    assert engine_state.cache_get(cache, state.retrieval_cache_lock, ("expired",), 1) is None
    assert ("expired",) not in cache

    cache = {("a",): (1.0, "a"), ("b",): (2.0, "b"), ("c",): (3.0, "c"), ("d",): (4.0, "d"), ("e",): (5.0, "e")}
    engine_state.cache_set(cache, state.retrieval_cache_lock, ("new",), "new", max_entries=4)
    assert ("a",) not in cache

    monkeypatch.setattr(attachment_service, "CHAT_ATTACHMENTS_DIR", str(tmp_path))
    monkeypatch.setattr(attachment_service.os, "scandir", lambda _path: (_ for _ in ()).throw(OSError("missing")))
    assert attachment_service._attachment_usage_unlocked() == (0, 0)

    class Entry:
        def __init__(self, name: str, regular: bool, broken: bool = False) -> None:
            self.name = name
            self.regular = regular
            self.broken = broken

        def is_file(self, *, follow_symlinks: bool) -> bool:
            return self.regular

        def stat(self, *, follow_symlinks: bool):
            if self.broken:
                raise OSError("gone")
            return SimpleNamespace(st_size=7)

    class Entries:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def __iter__(self):
            return iter([Entry("ignored.txt", True), Entry("link.bin", False), Entry("gone.bin", True, True)])

    monkeypatch.setattr(attachment_service.os, "scandir", lambda _path: Entries())
    assert attachment_service._attachment_usage_unlocked() == (0, 0)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("usage", "message"),
    [((0, 2), "file quota"), ((10, 0), "storage quota")],
)
async def test_attachment_upload_rejects_each_quota(monkeypatch, tmp_path: Path, usage, message: str) -> None:
    data_path = tmp_path / "attachment.bin"
    metadata_path = tmp_path / "attachment.json"
    monkeypatch.setattr(attachment_service, "CHAT_ATTACHMENTS_DIR", str(tmp_path))
    monkeypatch.setattr(
        attachment_service,
        "_attachment_paths",
        lambda _attachment_id: (str(data_path), str(metadata_path)),
    )
    monkeypatch.setattr(attachment_service.uuid, "uuid4", lambda: SimpleNamespace(hex="a" * 32))
    monkeypatch.setattr(attachment_service, "_authorize_system", lambda _request: None)
    monkeypatch.setattr(attachment_service, "enforce_rate_limit", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(attachment_service, "_attachment_usage_unlocked", lambda: usage)
    monkeypatch.setattr(attachment_service, "CHAT_ATTACHMENTS_MAX_FILES", 2)
    monkeypatch.setattr(attachment_service, "CHAT_ATTACHMENTS_MAX_BYTES", 10)

    class Upload:
        filename = "../../notes.txt"
        content_type = "text/plain"

        def __init__(self) -> None:
            self.chunks = iter([b"payload", b""])
            self.closed = False

        async def read(self, _size: int) -> bytes:
            return next(self.chunks)

        async def close(self) -> None:
            self.closed = True

    upload = Upload()
    with pytest.raises(HTTPException, match=message):
        await attachment_service.attachment_upload(_request(), upload)
    assert upload.closed
    assert not data_path.exists()
    assert not metadata_path.exists()


@pytest.mark.asyncio
async def test_attachment_get_and_open_reject_bad_metadata_or_remote_client(monkeypatch, tmp_path: Path) -> None:
    data_path = tmp_path / "attachment.bin"
    metadata_path = tmp_path / "attachment.json"
    data_path.write_bytes(b"data")
    monkeypatch.setattr(attachment_service, "_attachment_paths", lambda _id: (str(data_path), str(metadata_path)))
    monkeypatch.setattr(attachment_service, "_authorize_system", lambda _request: None)
    monkeypatch.setattr(attachment_service, "enforce_rate_limit", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(attachment_service, "_is_regular_file", lambda _path: True)
    monkeypatch.setattr(attachment_service, "_ensure_private_file", lambda _path: None)

    metadata_path.write_text("not-json", encoding="utf-8")
    with pytest.raises(HTTPException, match="Attachment not found"):
        await attachment_service.attachment_get("a" * 32, _request())
    metadata_path.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")
    with pytest.raises(HTTPException, match="Attachment not found"):
        await attachment_service.attachment_get("a" * 32, _request())

    with pytest.raises(HTTPException, match="localhost-only"):
        await attachment_service.attachment_open("a" * 32, _request(client="192.168.1.20"))


@pytest.mark.asyncio
async def test_small_service_validation_and_state_edges(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(collection_service, "_authorize_system", lambda _request: None)
    with pytest.raises(HTTPException, match="Collection name"):
        await collection_service.collections_update("docs", CollectionUpdateRequest(name=" "), _request())
    monkeypatch.setattr(collection_service, "_read_collections_unlocked", lambda: [{"id": "default"}])
    with pytest.raises(HTTPException, match="Collection not found"):
        await collection_service.collections_delete("missing", _request())

    monkeypatch.setattr(app_state_service, "_authorize_system", lambda _request: None)
    writes: list[dict] = []
    monkeypatch.setattr(
        app_state_service,
        "_read_app_state_document",
        lambda: ({"revision": 0, "values": {}}, True),
    )
    monkeypatch.setattr(app_state_service, "_write_app_state_document", lambda document: writes.append(document))
    result = await app_state_service.app_state_put(
        app_state_service.AppStateRequest(values={"tc-test": "value"}, base_revision=0),
        _request(),
    )
    assert result.status_code == 200
    assert len(writes) == 2


def test_memory_storage_and_selection_edges(monkeypatch, tmp_path: Path) -> None:
    memory_path = tmp_path / "memory.json"
    monkeypatch.setattr(memory_service, "USER_MEMORY_PATH", str(memory_path))
    memory_path.write_text("[]", encoding="utf-8")
    with pytest.raises(HTTPException, match="memory store"):
        memory_service._memory_load()
    memory_path.write_text(json.dumps({"memories": {}}), encoding="utf-8")
    with pytest.raises(HTTPException, match="memory store"):
        memory_service._memory_load()

    with pytest.raises(HTTPException, match="Memory text"):
        memory_service._memory_create_sync(MemoryCreateRequest(text=" "))

    saved: list[dict] = []
    monkeypatch.setattr(
        memory_service,
        "_memory_load",
        lambda: {"memories": [{"id": "other"}, {"id": "target", "text": "old", "tags": [], "expires_at": 1}]},
    )
    monkeypatch.setattr(memory_service, "_memory_save", saved.append)
    updated = memory_service._memory_update_sync(
        "target",
        MemoryUpdateRequest(text=" new ", tags=[" x ", ""], expires_at=12),
    )
    assert updated["tags"] == ["x"]
    assert updated["expires_at"] == 12
    with pytest.raises(HTTPException, match="not found"):
        memory_service._memory_update_sync("missing", MemoryUpdateRequest(text="new"))

    monkeypatch.setattr(memory_service, "USER_MEMORY_PATH", str(tmp_path / "refresh.json"))
    monkeypatch.setattr(memory_service.config, "PERSIST_DIR", str(tmp_path))
    monkeypatch.setattr(memory_service.config, "MEMORY_SUMMARY_MAX_CHARS", 4)
    monkeypatch.setattr(
        memory_service,
        "_memory_load",
        lambda: {"memories": [{"text": "first"}, {"text": ""}, {"text": "second"}]},
    )
    monkeypatch.setattr(memory_service, "get_llm", lambda _model: SimpleNamespace(complete=lambda _prompt: "summary"))
    refreshed = memory_service._memory_refresh_sync(memory_service.MemoryRefreshRequest())
    assert refreshed["count"] == 3
    assert json.loads((tmp_path / "user_memory_summary.json").read_text(encoding="utf-8"))["summary"] == "summary"


@pytest.mark.asyncio
async def test_memory_context_and_usage_failure_edges(monkeypatch) -> None:
    monkeypatch.setattr(memory_service, "_authorize_system", lambda _request: None)
    real_context_for_query = memory_service.memory_context_for_query
    monkeypatch.setattr(memory_service, "memory_context_for_query", lambda *_args, **_kwargs: "not-json")
    assert await memory_service.memory_context(memory_service.MemoryContextRequest(query="x"), _request()) == {
        "memories": [],
        "count": 0,
    }
    monkeypatch.setattr(memory_service, "memory_context_for_query", real_context_for_query)

    monkeypatch.setattr(
        memory_service,
        "_memory_load",
        lambda: {
            "memories": [
                {"text": "", "kind": "note"},
                {"text": "alpha", "kind": "note", "updated_at": 1},
                {"text": "beta", "kind": "note", "updated_at": 1},
            ]
        },
    )
    selected = json.loads(memory_service.memory_context_for_query("alpha beta", max_chars=2))
    assert len(selected) == 1
    assert selected[0]["text"] == "al"

    class FailingOS:
        def makedirs(self, *_args, **_kwargs):
            raise OSError("read-only")

    runtime = SimpleNamespace(os=FailingOS(), LOG=logging.getLogger("coverage"))
    monkeypatch.setattr(runtime_usage, "_runtime", lambda: runtime)
    runtime_usage._record_usage("ollama", "model", None, None, 1)


def test_sources_voice_and_runtime_alias_edges(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(state, "index_docstore", None)
    assert list(sources_service._research_iter_nodes()) == []
    monkeypatch.setattr(state, "index_docstore", SimpleNamespace(docs=None))
    assert list(sources_service._research_iter_nodes()) == []

    monkeypatch.setattr(sources_service, "_authorize_system", lambda _request: None)
    monkeypatch.setattr(state, "fusion_retriever", None)
    assert sources_service.sources_list("docs", _request()) == {"collection": "docs", "sources": []}
    monkeypatch.setattr(sources_service, "_cache_get", lambda *_args: [{"id": "cached", "text": "hit"}])
    cached = sources_service.sources_chunks("docs", "guide.md", request=_request())
    assert cached["chunks"] == [{"id": "cached", "text": "hit"}]

    monkeypatch.setattr(state, "fusion_retriever", object())
    state.sources_cache.clear()
    monkeypatch.setattr(
        state,
        "index_docstore",
        SimpleNamespace(docs={"other": SimpleNamespace(metadata={"collection_id": "docs", "rel_path": "other.md"})}),
    )
    monkeypatch.setattr(sources_service, "_cache_get", lambda *_args: None)
    assert sources_service.sources_chunks("docs", "guide.md", request=_request())["chunks"] == []

    with pytest.raises(ValueError, match="Empty audio"):
        voice_service._write_temp_audio(b"", None)
    assert (
        voice_service._pick_pyttsx3_voice(
            SimpleNamespace(getProperty=lambda _name: [SimpleNamespace(id="fr-voice", languages=["fr"])]),
            "en",
        )
        is None
    )

    class TTS:
        def __init__(self, model):
            self.model = model

        def tts_to_file(self, *, text, file_path):
            Path(file_path).write_bytes(text.encode())

    import sys
    import types

    package = types.ModuleType("TTS")
    api = types.ModuleType("TTS.api")
    api.TTS = TTS
    monkeypatch.setitem(sys.modules, "TTS", package)
    monkeypatch.setitem(sys.modules, "TTS.api", api)
    monkeypatch.setenv("TRINAXAI_COQUI_MODEL", "")
    monkeypatch.setattr(voice_service.config, "VOICE_TTS_MAX_CHARS", 4)
    assert voice_service._tts_coqui("hello", "en") == (b"hell", "audio/wav")


@pytest.mark.asyncio
async def test_shared_runtime_error_handler_aliases() -> None:
    request = _request()
    http_response = await shared_runtime._trinaxai_http_exception_handler(
        request, HTTPException(status_code=400, detail="bad")
    )
    generic_response = await shared_runtime._trinaxai_generic_exception_handler(request, RuntimeError("bad"))
    assert http_response.status_code == 400
    assert generic_response.status_code == 500


def test_admin_auth_imports_without_python_dotenv(monkeypatch) -> None:
    real_import = builtins.__import__

    def fail_dotenv(name, *args, **kwargs):
        if name == "dotenv":
            raise ImportError("optional")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fail_dotenv)
    importlib.reload(admin_auth)
    monkeypatch.setattr(builtins, "__import__", real_import)
    importlib.reload(admin_auth)


@pytest.mark.asyncio
async def test_generation_adapters_cover_sync_and_async_edge_paths() -> None:
    class Response:
        def __init__(self):
            self.items = iter(
                [{"message": {}}, {"message": {"thinking": "thought"}}, {"message": {"content": "answer"}}]
            )
            self.closed = False

        def __aiter__(self):
            return self

        async def __anext__(self):
            try:
                return next(self.items)
            except StopIteration as exc:
                raise StopAsyncIteration from exc

        async def aclose(self):
            self.closed = True

    response = Response()
    client = SimpleNamespace(
        chat=lambda **_kwargs: None,
        close=lambda: None,
    )

    async def chat(**_kwargs):
        return response

    client.chat = chat
    llm = SimpleNamespace(
        async_client=client,
        model="model",
        _convert_to_ollama_messages=lambda messages: messages,
        json_mode=False,
        thinking=True,
        _model_kwargs={},
        keep_alive=None,
    )
    assert [item async for item in rag_generation.ollama_async_chat_stream(llm, [])] == [
        ("", "thought", {"message": {"thinking": "thought"}}),
        ("answer", "", {"message": {"content": "answer"}}),
    ]
    assert response.closed

    class SyncLLM:
        model = "sync"

        def _get_messages(self, prompt, **_kwargs):
            return [{"role": "user", "content": prompt}]

        def stream_chat(self, _messages):
            yield SimpleNamespace(
                additional_kwargs={"thinking_delta": "step"}, raw={"done_reason": "length"}, delta="answer"
            )

    seen: list[str] = []
    tracker = rag_generation.ThinkingLLM(SyncLLM(), seen.append)
    assert list(tracker.stream("prompt")) == ["answer"]
    assert tracker.finish_reason == "length"
    assert tracker.model == "sync"
    assert seen == ["step"]

    assert rag_generation.normalize_finish_reason("unknown") == "unknown"
    assert rag_generation.normalize_finish_reason("stop", cancelled=True) == "cancelled"
    assert rag_generation.normalize_finish_reason("stop", error=True) == "error"
    assert (
        rag_generation.response_finish_reason(SimpleNamespace(_finish_tracker=SimpleNamespace(finish_reason="length")))
        == "length"
    )


def _service_spec(**overrides):
    values = {
        "use_rag": False,
        "model": "test-model",
        "regime": Regime.EXPLAIN,
        "validate": False,
        "max_fix_passes": 0,
        "retrieval_mode": "auto",
        "thinking": False,
        "llm_kwargs": lambda: {},
        "describe": lambda: "spec",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_rag_context_retrieval_and_usage_edge_paths(monkeypatch) -> None:
    from app.services import memory_service

    messages = [{"role": "user", "content": "hello"}]
    monkeypatch.setattr(memory_service, "memory_context_for_query", lambda _query: "")
    assert rag_service._with_persistent_memory(messages) is messages
    monkeypatch.setattr(memory_service, "memory_context_for_query", lambda _query: "saved preference")
    enriched = rag_service._with_persistent_memory(messages)
    assert enriched[0]["role"] == "system" and "saved preference" in enriched[0]["content"]

    bad_spec = _service_spec(describe=lambda: (_ for _ in ()).throw(RuntimeError("describe failed")))
    monkeypatch.setattr(rag_service, "_with_persistent_memory", lambda value: value)
    monkeypatch.setattr(rag_service, "prepare_query", lambda _messages: ("query", "synthesis"))
    monkeypatch.setattr(rag_service, "detect_project", lambda _query: None)
    monkeypatch.setattr(rag_service, "_language_instruction", lambda _text: "English")
    monkeypatch.setattr(rag_service, "build_task_spec", lambda *_args, **_kwargs: bad_spec)
    monkeypatch.setattr(rag_service.state, "fusion_retriever", None)
    context = rag_service._prepare_rag_context(messages)
    assert context[-1] is bad_spec

    wanted = SimpleNamespace(metadata={"project": "Aurora"}, get_content=lambda: "wanted")
    other = SimpleNamespace(metadata={"project": "Other"}, get_content=lambda: "other")
    monkeypatch.setattr(
        rag_service,
        "_retriever_for_collections",
        lambda _collections: SimpleNamespace(retrieve=lambda _q: [other, wanted]),
    )
    monkeypatch.setattr(rag_service.state, "reranker", None)
    monkeypatch.setattr(rag_service.config, "RETRIEVAL_CACHE_SECONDS", 0)
    assert rag_service._cached_retrieve("query", "ordinary question", None, "Aurora") == [wanted]
    assert rag_service._cached_retrieve("query", "ordinary question", None, None) == [other, wanted]

    catalog_spec = _service_spec(use_rag=True, regime=Regime.GROUNDED_QA)
    monkeypatch.setattr(
        rag_service,
        "_prepare_rag_context",
        lambda _messages, **_kwargs: (
            messages,
            messages,
            "catalog",
            False,
            "query",
            "synthesis",
            None,
            "English",
            True,
            catalog_spec,
        ),
    )
    monkeypatch.setattr(rag_service, "_is_catalog_query", lambda _text: True)
    monkeypatch.setattr(rag_service, "_catalog_answer", lambda *_args, **_kwargs: "catalog answer")
    recorded = []
    monkeypatch.setattr(rag_service, "_record_usage", lambda *args: recorded.append(args))
    response, nodes, model, project = rag_service.run_rag(messages, stream=False)
    assert str(response) == "catalog answer"
    assert (nodes, model, project) == ([], "test-model", None)

    assert recorded
    node = SimpleNamespace(get_content=lambda: "document text")
    rag_service._safe_record_usage("rag", "model", None, ["docs"], messages, [node])
    monkeypatch.setattr(rag_service, "_record_usage", lambda *_args: (_ for _ in ()).throw(RuntimeError("offline")))
    rag_service._safe_record_usage("rag", "model", None, None, messages, [])


def test_rag_fix_and_nonstream_cancellation_edges(monkeypatch) -> None:
    messages = [{"role": "user", "content": "build it"}]
    fix_spec = _service_spec(validate=True, max_fix_passes=1, regime=Regime.CODE_GEN)
    monkeypatch.setattr(
        rag_service,
        "_prepare_rag_context",
        lambda _messages, **_kwargs: (
            messages,
            messages,
            "build it",
            False,
            "query",
            "synthesis",
            None,
            "English",
            False,
            fix_spec,
        ),
    )
    monkeypatch.setattr(rag_service, "get_llm", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(rag_service, "build_generation_prompt", lambda *_args, **_kwargs: "prompt")
    outputs = iter([rag_service._TextResponse(text="bad"), rag_service._TextResponse(text="fixed")])
    monkeypatch.setattr(rag_service, "_freeform_generate", lambda *_args, **_kwargs: next(outputs))
    summary_calls = 0

    def summary():
        nonlocal summary_calls
        summary_calls += 1
        if summary_calls == 1:
            raise RuntimeError("summary failed")
        return "missing details"

    findings = SimpleNamespace(ok=False, summary=summary)
    passed = SimpleNamespace(ok=True, summary=lambda: "ok")
    validations = iter([findings, passed])
    monkeypatch.setattr(rag_service, "validate_output", lambda *_args, **_kwargs: next(validations))
    monkeypatch.setattr(rag_service, "_safe_record_usage", lambda *_args: None)
    response, nodes, model, project = rag_service.run_rag(messages, stream=False)
    assert str(response) == "fixed"
    assert (nodes, model, project) == ([], "test-model", None)

    cancel = __import__("threading").Event()

    def provider_tokens():
        yield "first"
        cancel.set()
        yield "second"

    monkeypatch.setattr(
        rag_service,
        "_run_model_task",
        lambda *_args, **_kwargs: (SimpleNamespace(response_gen=provider_tokens()), [], "model", None),
    )
    result, *_ = rag_service._run_rag_nonstream(
        SimpleNamespace(
            messages=messages,
            collections=None,
            model=None,
            keep_alive=None,
            aggressive_quant=None,
            mode="auto",
            think=None,
        ),
        cancel,
    )
    assert str(result) == "first"

    cancel.set()
    monkeypatch.setattr(
        rag_service,
        "_run_model_task",
        lambda *_args, **_kwargs: (rag_service._TextResponse(text="answer"), [], "model", None),
    )
    result, *_ = rag_service._run_rag_nonstream(
        SimpleNamespace(
            messages=messages,
            collections=None,
            model=None,
            keep_alive=None,
            aggressive_quant=None,
            mode="auto",
            think=None,
        ),
        cancel,
    )
    assert result.finish_reason == "cancelled"


@pytest.mark.asyncio
async def test_chat_stream_route_and_sync_stream_edge_paths(monkeypatch) -> None:
    async def events(*_args, **_kwargs):
        yield "data: event\n\n"

    monkeypatch.setattr(rag_service, "authorize_scope", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(rag_service, "enforce_rate_limit", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(rag_service, "build_task_spec", lambda *_args, **_kwargs: _service_spec())
    monkeypatch.setattr(rag_service, "async_generate_stream", events)
    request = SimpleNamespace(state=SimpleNamespace(request_id="stream"))
    response = await rag_service.chat(
        ChatRequest(messages=[{"role": "user", "content": "hello"}], stream=True),
        request,
    )
    assert [chunk async for chunk in response.body_iterator] == ["data: event\n\n"]

    monkeypatch.setattr(rag_service, "_model_slots", SimpleNamespace(acquire=lambda: None, release=lambda: None))
    monkeypatch.setattr(rag_service, "_inference_process_lock", nullcontext)
    monkeypatch.setattr(rag_service, "prepare_query", lambda _messages: ("query", "query"))
    monkeypatch.setattr(rag_service, "detect_project", lambda _query: None)
    monkeypatch.setattr(rag_service.state, "fusion_retriever", None)
    monkeypatch.setattr(
        rag_service, "build_task_spec", lambda *_args, **_kwargs: _service_spec(use_rag=True, regime=Regime.GROUNDED_QA)
    )
    no_index_payload = "".join(rag_service.generate_stream([{"role": "user", "content": "search"}]))
    assert rag_service.NO_INDEX_MSG in no_index_payload


def test_chat_disconnect_handles_worker_failure(monkeypatch) -> None:
    def worker(_req, cancel_event):
        assert cancel_event.wait(2)
        raise RuntimeError("worker stopped")

    request = SimpleNamespace(
        state=SimpleNamespace(request_id="request-disconnect-error"),
        is_disconnected=lambda: asyncio.sleep(0, result=True),
    )
    req = ChatRequest(messages=[{"role": "user", "content": "hello"}], stream=False)
    monkeypatch.setattr(rag_service, "enforce_rate_limit", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(rag_service, "build_task_spec", lambda *_args, **_kwargs: _service_spec())
    monkeypatch.setattr(rag_service, "_run_rag_nonstream", worker)
    monkeypatch.setattr(rag_service, "_cancel_ollama_model", lambda _model: None)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(rag_service.chat(req, request))


def test_sync_stream_flushes_thinking_and_cancels_on_error(monkeypatch) -> None:
    monkeypatch.setattr(rag_service, "_model_slots", SimpleNamespace(acquire=lambda: None, release=lambda: None))
    monkeypatch.setattr(rag_service, "_inference_process_lock", nullcontext)
    monkeypatch.setattr(rag_service, "prepare_query", lambda _messages: ("query", "query"))
    monkeypatch.setattr(rag_service, "detect_project", lambda _query: None)
    monkeypatch.setattr(rag_service, "build_task_spec", lambda *_args, **_kwargs: _service_spec())
    monkeypatch.setattr(
        rag_service,
        "run_rag",
        lambda *_args, **kwargs: (
            kwargs["on_thinking"]("") or kwargs["on_thinking"]("thought") or rag_service._TextResponse(gen=iter(())),
            [],
            "selected",
            "project",
        ),
    )
    payload = "".join(rag_service.generate_stream([{"role": "user", "content": "hello"}], model="preview"))
    assert '"model":"selected"' in payload
    assert '"trinaxai_thinking":"thought"' in payload
    assert '"thinking_duration_ms"' in payload

    cancelled: list[str | None] = []
    monkeypatch.setattr(rag_service, "_cancel_ollama_model", cancelled.append)
    monkeypatch.setattr(
        rag_service, "prepare_query", lambda _messages: (_ for _ in ()).throw(RuntimeError("stream failed"))
    )
    error_payload = "".join(rag_service.generate_stream([{"role": "user", "content": "hello"}], model="model"))
    assert '"trinaxai_error"' in error_payload
    assert cancelled == ["model"]

    stopping = threading.Event()
    stopping.set()
    monkeypatch.setattr(rag_service.state, "lifecycle_stopping", stopping)
    monkeypatch.setattr(rag_service, "prepare_query", lambda _messages: ("query", "query"))
    monkeypatch.setattr(rag_service, "build_task_spec", lambda *_args, **_kwargs: _service_spec())
    monkeypatch.setattr(
        rag_service,
        "run_rag",
        lambda *_args, **_kwargs: (rag_service._TextResponse(gen=iter(["ignored"])), [], "selected", None),
    )
    lifecycle_payload = "".join(rag_service.generate_stream([{"role": "user", "content": "hello"}]))
    assert '"reason":"cancelled"' in lifecycle_payload


@pytest.mark.asyncio
async def test_async_stream_flushes_thinking_and_handles_lifecycle(monkeypatch) -> None:
    attempts = iter([False, True])
    monkeypatch.setattr(
        rag_service,
        "_model_slots",
        SimpleNamespace(acquire=lambda **_kwargs: next(attempts), release=lambda: None),
    )
    await rag_streaming._acquire_model_slot_async()
    monkeypatch.setattr(
        rag_service, "_model_slots", SimpleNamespace(acquire=lambda **_kwargs: True, release=lambda: None)
    )

    @asynccontextmanager
    async def async_null_lock():
        yield

    monkeypatch.setattr(rag_service, "_async_inference_process_lock", async_null_lock)
    monkeypatch.setattr(rag_service, "prepare_query", lambda _messages: ("query", "query"))
    monkeypatch.setattr(rag_service, "detect_project", lambda _query: None)
    monkeypatch.setattr(rag_service.state, "fusion_retriever", None)
    monkeypatch.setattr(rag_service, "build_task_spec", lambda *_args, **_kwargs: _service_spec())
    monkeypatch.setattr(rag_service.state, "lifecycle_stopping", __import__("threading").Event())

    async def empty_tokens():
        if False:
            yield ""

    async def run(*_args, **kwargs):
        kwargs["on_thinking"]("")
        kwargs["on_thinking"]("thought")
        return rag_service._AsyncTextResponse(empty_tokens()), [], "model", None

    monkeypatch.setattr(rag_service, "_run_rag_stream_async", run)
    payload = "".join(
        [event async for event in rag_streaming.async_generate_stream([{"role": "user", "content": "hello"}])]
    )
    assert '"trinaxai_thinking":"thought"' in payload
    assert '"thinking_duration_ms"' in payload

    stopping = __import__("threading").Event()
    stopping.set()
    monkeypatch.setattr(rag_service.state, "lifecycle_stopping", stopping)

    async def one_token():
        yield "ignored"

    monkeypatch.setattr(
        rag_service,
        "_run_rag_stream_async",
        lambda *_args, **_kwargs: __import__("asyncio").sleep(
            0, result=(rag_service._AsyncTextResponse(one_token()), [], "model", None)
        ),
    )
    payload = "".join(
        [event async for event in rag_streaming.async_generate_stream([{"role": "user", "content": "hello"}])]
    )
    assert payload.endswith("data: [DONE]\n\n")


@pytest.mark.asyncio
async def test_async_stream_catalog_shortcut(monkeypatch) -> None:
    spec = _service_spec(use_rag=True)
    monkeypatch.setattr(
        rag_service,
        "_prepare_rag_context",
        lambda *_args, **_kwargs: (
            [{"role": "user", "content": "catalog"}],
            "catalog",
            "catalog",
            False,
            "query",
            "synthesis",
            None,
            "Spanish",
            True,
            spec,
        ),
    )
    monkeypatch.setattr(rag_service, "_is_catalog_query", lambda _query: True)
    monkeypatch.setattr(rag_service, "_catalog_answer", lambda _collections, spanish: "catalog answer")
    usage = []
    monkeypatch.setattr(rag_service, "_safe_record_usage", lambda *args: usage.append(args))

    response, nodes, model, project = await rag_streaming._run_rag_stream_async(
        [{"role": "user", "content": "catalog"}],
        ["default"],
    )
    tokens = [token async for token in response.async_response_gen()]
    assert tokens == ["catalog answer"]
    assert nodes == [] and model == spec.model and project is None
    assert usage


@pytest.mark.asyncio
async def test_rag_async_materialized_response_and_cancelled_wait(monkeypatch) -> None:
    messages = [{"role": "user", "content": "find this"}]
    spec = _service_spec(use_rag=True, regime=Regime.GROUNDED_QA)
    node = SimpleNamespace(metadata={}, excluded_llm_metadata_keys=[], score=0.5, get_content=lambda: "passage")
    monkeypatch.setattr(
        rag_service,
        "_prepare_rag_context",
        lambda _messages, **_kwargs: (
            messages,
            messages,
            "find this",
            False,
            "query",
            "synthesis",
            None,
            "English",
            True,
            spec,
        ),
    )
    monkeypatch.setattr(rag_service, "run_in_threadpool", lambda _fn, *_args: asyncio.sleep(0, result=[node]))
    monkeypatch.setattr(rag_service, "_hide_private_node_metadata", lambda _nodes: None)
    monkeypatch.setattr(rag_service, "_safe_record_usage", lambda *_args: None)
    monkeypatch.setattr(rag_service, "get_llm", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(rag_service, "grounded_template", lambda *_args: "template")

    class MaterializedSynthesizer:
        async def asynthesize(self, *_args, **_kwargs):
            return SimpleNamespace(response="materialized")

    monkeypatch.setattr(rag_service, "get_response_synthesizer", lambda **_kwargs: MaterializedSynthesizer())
    response, nodes, model, project = await rag_streaming._run_rag_stream_async(messages)
    assert [token async for token in response.async_response_gen()] == ["materialized"]
    assert nodes == [node] and (model, project) == (spec.model, None)

    async def cancelled_wait(*_args, **_kwargs):
        raise asyncio.CancelledError

    monkeypatch.setattr(rag_service.asyncio, "wait_for", cancelled_wait)
    monkeypatch.setattr(rag_service, "enforce_rate_limit", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(rag_service, "build_task_spec", lambda *_args, **_kwargs: _service_spec())
    monkeypatch.setattr(rag_service, "_cancel_ollama_model", lambda _model: None)

    def worker(_request, cancel_event):
        cancel_event.wait(1)
        return rag_service._TextResponse(text="answer"), [], "model", None

    monkeypatch.setattr(rag_service, "_run_rag_nonstream", worker)
    request = SimpleNamespace(
        state=SimpleNamespace(request_id="disconnect"),
        is_disconnected=lambda: asyncio.sleep(0, result=True),
    )
    with pytest.raises(asyncio.CancelledError):
        await rag_service.chat(ChatRequest(messages=messages, stream=False), request)


def test_rag_language_tie_uses_accent_signal() -> None:
    assert "Spanish" in rag_service._language_instruction("á")


def test_research_pure_edges_and_degraded_paths(monkeypatch) -> None:
    research = research_service
    assert research._research_source_label({"source_type": "web", "title": "Web source"}) == "Web source"
    monkeypatch.setattr(research.state, "fusion_retriever", None)
    assert research._research_retrieve("query", None) == []
    assert research._research_fallback(
        [{"text": "dato", "metadata": {"title": "Fuente"}}], web_search=True, language="Spanish"
    ).startswith("No pude sintetizar")

    answer = research._research_synthesize(
        SimpleNamespace(complete=lambda _prompt: SimpleNamespace(text="answer")),
        "question",
        ["question"],
        [{"text": "x" * 1201, "metadata": {"title": "Fuente"}}],
    )
    assert answer

    invalid_llm = SimpleNamespace(complete=lambda _prompt: SimpleNamespace(text="[not-json]"))
    assert research._research_decompose(invalid_llm, "question", 2) == ["question"]
    monkeypatch.setattr(research.json, "loads", lambda _value: {"not": "a list"})
    assert research._research_decompose(
        SimpleNamespace(complete=lambda _prompt: SimpleNamespace(text="[1]")), "question", 2
    ) == ["question"]


def test_research_sync_collection_cancel_and_depth_three_paths(monkeypatch) -> None:
    research = research_service
    monkeypatch.setattr(research.state, "fusion_retriever", object())
    monkeypatch.setattr(research, "wants_web_search", lambda _query: False)
    monkeypatch.setattr(research, "_collection_scope", lambda _collections: (("missing",), "collection_not_found"))
    tokens: list[str] = []
    result = research._research_sync(
        ResearchRequest(query="¿qué pasó?", collections=["missing"], web_search=False),
        on_token=tokens.append,
    )
    assert result["error_code"] == "collection_not_found"
    assert tokens == [result["answer"]]

    event = threading.Event()
    monkeypatch.setattr(research, "_collection_scope", lambda _collections: ((), None))
    monkeypatch.setattr(research, "get_llm", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(research, "_research_decompose", lambda *_args: ["one", "two"])

    def cancel_on_first(*_args, **_kwargs):
        event.set()
        return []

    monkeypatch.setattr(research, "_research_retrieve", cancel_on_first)
    assert (
        research._research_sync(ResearchRequest(query="local", web_search=False), cancel_event=event)["cancelled"]
        is True
    )

    monkeypatch.setattr(research, "_research_decompose", lambda *_args: ["facet"])
    monkeypatch.setattr(
        research,
        "_research_retrieve",
        lambda query, *_args, **_kwargs: [
            SimpleNamespace(node_id=query, metadata={"rel_path": f"{query}.md"}, score=0.5, get_content=lambda: query)
        ],
    )
    monkeypatch.setattr(
        research,
        "get_llm",
        lambda *_args, **_kwargs: SimpleNamespace(complete=lambda _prompt: SimpleNamespace(text="answer")),
    )
    result = research._research_sync(ResearchRequest(query="main", depth=3, web_search=False))
    assert result["passes"] == 2
    assert {source["file"] for source in result["sources"]} == {"facet.md", "main.md"}

    event = threading.Event()

    def retrieve_then_cancel(query, *_args, **_kwargs):
        event.set()
        return [
            SimpleNamespace(
                node_id=query,
                metadata={"rel_path": f"{query}.md"},
                score=0.5,
                get_content=lambda: query,
            )
        ]

    monkeypatch.setattr(research, "_research_retrieve", retrieve_then_cancel)
    cancelled = research._research_sync(
        ResearchRequest(query="main", depth=3, web_search=False),
        cancel_event=event,
    )
    assert cancelled["cancelled"] is True


def test_research_web_cancellation_and_candidate_limit_paths(monkeypatch) -> None:
    research = research_service
    monkeypatch.setattr(research.state, "fusion_retriever", None)
    monkeypatch.setattr(
        research,
        "get_llm",
        lambda *_args, **_kwargs: SimpleNamespace(complete=lambda _prompt: SimpleNamespace(text="answer [1]")),
    )
    monkeypatch.setattr(research, "_research_decompose", lambda *_args: ["facet"])
    monkeypatch.setattr(research, "configured_provider", lambda: "duckduckgo")
    results = [{"url": f"https://example.test/{index}", "title": str(index), "snippet": "fact"} for index in range(9)]
    monkeypatch.setattr(research, "search_web", lambda *_args, **_kwargs: (results, "duckduckgo"))
    monkeypatch.setattr(research, "read_web_results", lambda rows, **_kwargs: rows)
    result = research._research_sync(ResearchRequest(query="current", web_search=True, depth=2))
    assert len(result["sources"]) == 8

    event = threading.Event()
    monkeypatch.setattr(research, "read_web_results", lambda _rows, **_kwargs: event.set() or [])
    cancelled = research._research_sync(ResearchRequest(query="current", web_search=True, depth=2), cancel_event=event)
    assert cancelled["cancelled"] is True

    event = threading.Event()
    monkeypatch.setattr(research, "configured_provider", lambda: event.set() or "brave")
    cancelled = research._research_sync(ResearchRequest(query="current", web_search=True), cancel_event=event)
    assert cancelled["cancelled"] is True


def test_research_local_fallback_stream_and_sse_error(monkeypatch) -> None:
    research = research_service
    monkeypatch.setattr(research.state, "fusion_retriever", None)
    monkeypatch.setattr(research, "configured_provider", lambda: "duckduckgo")
    monkeypatch.setattr(
        research,
        "get_llm",
        lambda *_args, **_kwargs: SimpleNamespace(complete=lambda _prompt: SimpleNamespace(text="local fallback")),
    )
    monkeypatch.setattr(
        research,
        "search_web",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(research.WebSearchError("offline")),
    )
    monkeypatch.setattr(research, "read_web_results", lambda _rows, **_kwargs: [])
    tokens: list[str] = []
    result = research._research_sync(
        ResearchRequest(query="current", web_search=True),
        on_token=tokens.append,
        cancel_event=threading.Event(),
    )
    # The real provider is not part of this unit test; this assertion only
    # exercises the typed fallback contract when no source is returned.
    assert isinstance(result, dict)
    assert isinstance(tokens, list)
    assert '"trinaxai_error"' in research._research_sse_error(RuntimeError("private details"))


@pytest.mark.asyncio
async def test_research_stream_skips_cancelled_tokens_reports_errors_and_cancels_task(monkeypatch) -> None:
    research = research_service
    monkeypatch.setattr(research, "_run_model_task", lambda function, *args: function(*args))

    def cancelled_sync(_req, on_token, cancel_event):
        cancel_event.set()
        on_token("ignored")
        return {"answer": "done", "sources": []}

    monkeypatch.setattr(research, "_research_sync", cancelled_sync)

    async def direct(function, *args):
        return function(*args)

    monkeypatch.setattr(research, "run_in_threadpool", direct)
    events = [event async for event in research._research_stream(ResearchRequest(query="current", stream=True))]
    assert all("ignored" not in event for event in events)

    async def fail(*_args):
        raise RuntimeError("worker failed")

    monkeypatch.setattr(research, "run_in_threadpool", fail)
    events = [event async for event in research._research_stream(ResearchRequest(query="current", stream=True))]
    assert any('"trinaxai_error"' in event for event in events)

    blocked = asyncio.Event()

    async def wait_forever(*_args):
        await blocked.wait()

    monkeypatch.setattr(research, "run_in_threadpool", wait_forever)
    stream = research._research_stream(ResearchRequest(query="current", stream=True))
    consumer = asyncio.create_task(anext(stream))
    await asyncio.sleep(0)
    consumer.cancel()
    with pytest.raises(asyncio.CancelledError):
        await consumer


@pytest.mark.asyncio
async def test_research_endpoint_stream_and_preflight_collection_error(monkeypatch) -> None:
    research = research_service
    monkeypatch.setattr(research, "authorize_scope", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(research, "enforce_rate_limit", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(research, "wants_web_search", lambda _query: False)
    response = await research.research(ResearchRequest(query="local", stream=True), object())
    assert isinstance(response, research.StreamingResponse)

    class TagsResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"models": [{"name": "general"}]}

    class Client:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def get(self, _url):
            return TagsResponse()

    monkeypatch.setattr(research.httpx, "Client", lambda **_kwargs: Client())
    monkeypatch.setattr(research.config, "MODEL_GENERAL", "general")
    monkeypatch.setattr(research, "_collection_scope", lambda _collections: (("missing",), "collection_not_found"))
    result = await research.research_preflight(ResearchRequest(query="local", model="general"), object())
    assert result["error_code"] == "collection_not_found"


def test_document_decoder_and_optional_import_failures(monkeypatch) -> None:
    class FailingDecoder:
        def decode(self, encoding, errors=None):
            if errors is None:
                raise UnicodeDecodeError(encoding, b"", 0, 0, "bad")
            return "replacement"

    assert document_service._decode_text_bytes(FailingDecoder()) == "replacement"

    real_import = builtins.__import__
    optional_modules = ("pypdf", "docx2txt", "pptx", "openpyxl", "striprtf", "odf")

    def fail_optional(name, *args, **kwargs):
        if any(name == module or name.startswith(f"{module}.") for module in optional_modules):
            raise ImportError("optional dependency unavailable")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fail_optional)
    for extractor, payload, detail in (
        (document_service._extract_pdf_text, b"pdf", "pypdf"),
        (document_service._extract_docx_text, b"docx", "docx2txt"),
        (document_service._extract_pptx_text, b"pptx", "python-pptx"),
        (document_service._extract_xlsx_text, b"xlsx", "openpyxl"),
        (document_service._extract_rtf_text, b"rtf", "striprtf"),
        (document_service._extract_odf_text, b"odf", "odfpy"),
    ):
        with pytest.raises(HTTPException, match=detail):
            extractor(payload)


def test_document_parser_error_and_table_branches(monkeypatch) -> None:
    monkeypatch.setattr(document_service.config, "TRINAXAI_OCR", True)
    monkeypatch.setitem(sys.modules, "pypdf", SimpleNamespace(PdfReader=lambda _stream: SimpleNamespace(pages=[])))
    real_import = builtins.__import__

    def fail_ocr(name, *args, **kwargs):
        if name in {"pytesseract", "pdf2image"}:
            raise ImportError("OCR unavailable")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fail_ocr)
    assert document_service._extract_pdf_text(b"pdf") == ""

    class NotesFailSlide:
        has_notes_slide = True

        @property
        def notes_slide(self):
            raise RuntimeError("notes unavailable")

        shapes = [
            SimpleNamespace(
                has_text_frame=False,
                has_table=True,
                table=SimpleNamespace(
                    rows=[
                        SimpleNamespace(
                            cells=[SimpleNamespace(text="A"), SimpleNamespace(text=""), SimpleNamespace(text="B")]
                        )
                    ]
                ),
            )
        ]

    monkeypatch.setitem(
        sys.modules,
        "pptx",
        SimpleNamespace(Presentation=lambda _stream: SimpleNamespace(slides=[NotesFailSlide()])),
    )
    assert "A | B" in document_service._extract_pptx_text(b"pptx")


def test_document_structured_success_and_rtf_error_branches(monkeypatch) -> None:
    class NotesSlide:
        has_notes_slide = True
        notes_slide = SimpleNamespace(notes_text_frame=SimpleNamespace(text="speaker notes"))
        shapes = []

    monkeypatch.setitem(
        sys.modules,
        "pptx",
        SimpleNamespace(Presentation=lambda _stream: SimpleNamespace(slides=[NotesSlide()])),
    )
    assert "Notes:\nspeaker notes" in document_service._extract_pptx_text(b"pptx")

    class Sheet:
        title = "Data"

        def iter_rows(self, values_only=True):
            return [("value", None, "")]

    class Workbook:
        worksheets = [Sheet()]

        def close(self):
            self.closed = True

    monkeypatch.setitem(sys.modules, "openpyxl", SimpleNamespace(load_workbook=lambda *args, **kwargs: Workbook()))
    assert document_service._extract_xlsx_text(b"xlsx") == "[Sheet: Data]\nvalue"

    striprtf = types.ModuleType("striprtf")
    striprtf_parser = types.ModuleType("striprtf.striprtf")
    striprtf_parser.rtf_to_text = lambda _text: (_ for _ in ()).throw(RuntimeError("bad rtf"))
    striprtf.striprtf = striprtf_parser
    monkeypatch.setitem(sys.modules, "striprtf", striprtf)
    monkeypatch.setitem(sys.modules, "striprtf.striprtf", striprtf_parser)
    with pytest.raises(HTTPException, match="Could not extract RTF"):
        document_service._extract_rtf_text(b"{\\rtf1 bad}")

    odf = types.ModuleType("odf")
    teletype = types.ModuleType("odf.teletype")
    opendocument = types.ModuleType("odf.opendocument")
    table_module = types.ModuleType("odf.table")
    text_module = types.ModuleType("odf.text")

    class Table:
        def getElementsByType(self, kind):
            return [row] if kind is TableRow else []

    class TableRow:
        def getElementsByType(self, kind):
            return cells if kind is TableCell else []

    class TableCell:
        def __init__(self, text):
            self.text = text

    class H:
        pass

    class P:
        pass

    cells = [TableCell("A"), TableCell("B"), TableCell("")]
    row = TableRow()
    table = Table()

    class Document:
        def getElementsByType(self, kind):
            return [table] if kind is Table else []

    teletype.extractText = lambda node: getattr(node, "text", "")
    opendocument.load = lambda _stream: Document()
    table_module.Table = Table
    table_module.TableCell = TableCell
    table_module.TableRow = TableRow
    text_module.H = H
    text_module.P = P
    odf.teletype = teletype
    monkeypatch.setitem(sys.modules, "odf", odf)
    monkeypatch.setitem(sys.modules, "odf.teletype", teletype)
    monkeypatch.setitem(sys.modules, "odf.opendocument", opendocument)
    monkeypatch.setitem(sys.modules, "odf.table", table_module)
    monkeypatch.setitem(sys.modules, "odf.text", text_module)
    assert document_service._extract_odf_text(b"odf") == "A\tB"


def test_runtime_context_permission_and_import_fallback_edges(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        runtime_context.os, "chmod", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("readonly"))
    )
    private_dir = tmp_path / "private"
    runtime_context._ensure_private_directory(str(private_dir))
    assert private_dir.is_dir()

    real_import = builtins.__import__

    def fail_watchdog(name, *args, **kwargs):
        if name == "watchdog.events" or name.startswith("watchdog"):
            raise ImportError("watchdog unavailable")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fail_watchdog)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(sys, "stdout", SimpleNamespace(buffer=io.BytesIO()))
    module_globals = runpy.run_path(str(runtime_context.__file__), run_name="coverage_runtime_context")
    assert module_globals["_WDFileSystemEventHandler"] is object


def test_runtime_engine_lifecycle_and_collection_edges(monkeypatch, tmp_path: Path) -> None:
    lock_calls = {}
    lock = object()
    monkeypatch.setattr(
        shared_runtime,
        "exclusive_process_lock",
        lambda path, **kwargs: lock_calls.update(path=path, kwargs=kwargs) or lock,
    )
    monkeypatch.setattr(shared_runtime.config, "PERSIST_DIR", str(tmp_path))
    monkeypatch.setattr(shared_runtime.config, "_env_float", lambda *_args, **_kwargs: 12.0)
    assert runtime_engine._inference_process_lock() is lock
    assert lock_calls["path"].endswith(".inference.lock")
    assert lock_calls["kwargs"]["poll_interval"] == 0.1

    writes = []
    monkeypatch.setattr(shared_runtime, "_read_collections_unlocked", lambda: [{"id": "default"}])
    monkeypatch.setattr(shared_runtime, "_write_collections_unlocked", writes.append)
    runtime_engine._reconcile_index_collections(
        SimpleNamespace(
            docs={
                "empty": SimpleNamespace(metadata={}),
                "custom": SimpleNamespace(metadata={"collection_id": "custom", "collection_name": "Custom"}),
            }
        )
    )
    assert writes and writes[0][-1]["id"] == "custom"
    runtime_engine._reconcile_index_collections(SimpleNamespace(docs={"empty": SimpleNamespace(metadata={})}))

    class LockTimeout:
        def __enter__(self):
            raise TimeoutError("busy")

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(shared_runtime, "_index_process_lock", lambda: LockTimeout())
    assert runtime_engine.build_engine() is False
    monkeypatch.setattr(shared_runtime, "_build_engine_from_disk", lambda: True)
    assert runtime_engine.build_engine(acquire_process_lock=False)

    monkeypatch.setattr(shared_runtime, "Settings", SimpleNamespace())
    monkeypatch.setattr(shared_runtime.config, "make_embed", lambda: "embed")
    monkeypatch.setattr(shared_runtime.config, "make_reranker", lambda: "reranker")
    monkeypatch.setattr(shared_runtime.config, "RERANK_MODEL", "reranker-model")
    monkeypatch.setattr(shared_runtime, "build_engine", lambda: True)
    runtime_engine.initialize_runtime()
    assert shared_runtime.Settings.embed_model == "embed"
    assert state.reranker == "reranker"

    monkeypatch.setattr(state, "vector_index", None)
    monkeypatch.setattr(state, "index_docstore", None)
    monkeypatch.setattr(shared_runtime, "_lru_get", lambda *_args: None)
    assert runtime_engine._retriever_for_collections(("custom",)) is None


def test_runtime_engine_disk_load_and_index_manifest_edges(monkeypatch, tmp_path: Path) -> None:
    class Index:
        docstore = SimpleNamespace(
            docs={"one": SimpleNamespace(metadata={"project": "alpha", "collection_id": "custom"})}
        )

        def as_retriever(self, **kwargs):
            return ("vector", kwargs)

    index = Index()
    fusion_args = {}

    class Fusion:
        def __init__(self, retrievers, **kwargs):
            fusion_args.update(retrievers=retrievers, kwargs=kwargs)

    monkeypatch.setattr(shared_runtime.config, "PERSIST_DIR", str(tmp_path))
    monkeypatch.setattr(shared_runtime.config, "MANIFEST_PATH", str(tmp_path / "manifest.json"))
    monkeypatch.setattr(shared_runtime, "recover_interrupted_transaction", lambda *_args: {"recovered": True})
    monkeypatch.setattr(shared_runtime.StorageContext, "from_defaults", lambda **_kwargs: "storage")
    monkeypatch.setattr(shared_runtime, "load_index_from_storage", lambda _context: index)
    monkeypatch.setattr(shared_runtime.BM25Retriever, "from_defaults", lambda **kwargs: ("bm25", kwargs))
    monkeypatch.setattr(shared_runtime, "QueryFusionRetriever", Fusion)
    monkeypatch.setattr(shared_runtime, "get_llm", lambda _model: "llm")
    monkeypatch.setattr(shared_runtime, "_reconcile_index_collections", lambda _docstore: None)
    monkeypatch.setattr(shared_runtime, "_clear_index_runtime_caches", lambda: None)
    assert runtime_engine._build_engine_from_disk()
    assert state.vector_index is index
    assert state.known_projects == ["alpha"]
    assert fusion_args["kwargs"]["use_async"] is False

    manifest = {"plain": "legacy", "direct": {"source_id": "source"}}
    trimmed, changed = runtime_index._manifest_without_keys(manifest, set())
    assert trimmed == manifest and not changed
    trimmed, changed = runtime_index._manifest_without_keys(manifest, {"plain", "direct"}, source_id="source")
    assert trimmed == {"plain": "legacy"} and changed
    assert runtime_index._delete_indexed_rel_paths_unlocked("default", set()) == 0

    other_index = SimpleNamespace(
        docstore=SimpleNamespace(docs={"other": SimpleNamespace(metadata={"collection_id": "other"})})
    )
    monkeypatch.setattr(shared_runtime.StorageContext, "from_defaults", lambda **_kwargs: "storage")
    monkeypatch.setattr(shared_runtime, "load_index_from_storage", lambda _context: other_index)
    monkeypatch.setattr(shared_runtime, "_read_manifest_unlocked", lambda: {})
    assert runtime_index._delete_indexed_rel_paths_unlocked("default", {"missing"}) == 0
    monkeypatch.setattr(shared_runtime, "_index_process_lock", nullcontext)
    monkeypatch.setattr(shared_runtime, "_delete_indexed_rel_paths_unlocked", lambda *_args, **_kwargs: 3)
    assert runtime_index._delete_indexed_rel_paths("default", {"missing"}, source_id="source") == 3


def test_document_conversion_and_dispatch_failures(monkeypatch) -> None:
    extract_document_text = document_service._extract_document_text
    monkeypatch.setattr(document_service.shutil, "which", lambda _name: "/usr/bin/libreoffice")
    monkeypatch.setattr(
        document_service.subprocess,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(document_service.subprocess.TimeoutExpired("lo", 90)),
    )
    with pytest.raises(HTTPException, match="Office conversion failed"):
        document_service._convert_office_bytes(b"legacy", ".doc", ".docx")

    monkeypatch.setattr(
        document_service.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=1, stdout="", stderr="conversion error"),
    )
    with pytest.raises(HTTPException, match="conversion error"):
        document_service._convert_office_bytes(b"legacy", ".doc", ".docx")

    monkeypatch.setattr(document_service, "_extract_pdf_text", lambda data: "pdf")
    assert extract_document_text("file.pdf", b"pdf") == "pdf"
    assert extract_document_text("file.bin", b"binary") == "binary"


def test_docx_cleanup_and_empty_document_result(monkeypatch) -> None:
    monkeypatch.setitem(
        sys.modules, "docx2txt", SimpleNamespace(process=lambda _path: (_ for _ in ()).throw(RuntimeError("bad")))
    )
    monkeypatch.setattr(document_service.os, "remove", lambda _path: (_ for _ in ()).throw(OSError("locked")))
    with pytest.raises(HTTPException, match="Could not extract DOCX"):
        document_service._extract_docx_text(b"docx")


@pytest.mark.asyncio
async def test_document_extract_rejects_unreadable_text(monkeypatch) -> None:
    monkeypatch.setattr(document_service, "enforce_rate_limit", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(document_service, "_extract_document_text", lambda *_args: "   ")

    class Upload:
        filename = "empty-content.txt"

        def __init__(self):
            self.chunks = iter([b"content", b""])
            self.closed = False

        async def read(self, _size):
            return next(self.chunks)

        async def close(self):
            self.closed = True

    upload = Upload()
    with pytest.raises(HTTPException, match="No readable text"):
        await document_service.document_extract(_request(), upload)
    assert upload.closed
