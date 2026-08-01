from __future__ import annotations

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

import config
from app.schemas import MemoryContextRequest, MemoryCreateRequest, MemoryUpdateRequest
from app.services import memory_service, rag_service


def test_memory_request_limits_text_and_tags() -> None:
    with pytest.raises(ValidationError):
        MemoryCreateRequest(text="x" * (config.MEMORY_TEXT_MAX_CHARS + 1))
    with pytest.raises(ValidationError):
        MemoryCreateRequest(
            text="valid",
            tags=["x" * (config.MEMORY_TAG_MAX_CHARS + 1)],
        )


def test_corrupt_memory_store_is_preserved_and_reported(tmp_path, monkeypatch) -> None:
    path = tmp_path / "user_memory.json"
    original = "{not valid json"
    path.write_text(original, encoding="utf-8")
    monkeypatch.setattr(memory_service, "USER_MEMORY_PATH", str(path))

    with pytest.raises(HTTPException) as exc:
        memory_service._memory_load()

    assert exc.value.status_code == 500
    assert path.read_text(encoding="utf-8") == original


def test_memory_entry_limit_prevents_unbounded_store(tmp_path, monkeypatch) -> None:
    path = tmp_path / "user_memory.json"
    path.write_text(
        '{"memories":[{"id":"existing","text":"kept","tags":[]}]}',
        encoding="utf-8",
    )
    monkeypatch.setattr(memory_service, "USER_MEMORY_PATH", str(path))
    monkeypatch.setattr(config, "MEMORY_MAX_ENTRIES", 1)

    with pytest.raises(HTTPException) as exc:
        memory_service._memory_create_sync(MemoryCreateRequest(text="new"))

    assert exc.value.status_code == 413
    assert "existing" in path.read_text(encoding="utf-8")


def test_backend_injects_memory_once_for_non_pwa_clients(monkeypatch) -> None:
    monkeypatch.setattr(
        memory_service,
        "memory_context_for_query",
        lambda _query: '[{"kind":"preference","text":"Prefiere respuestas breves."}]',
    )
    original = [{"role": "user", "content": "Hola"}]

    injected = rag_service._with_persistent_memory(original)
    injected_again = rag_service._with_persistent_memory(injected)

    assert injected[0]["role"] == "system"
    assert "Prefiere respuestas breves" in injected[0]["content"]
    assert injected_again == injected
    assert len(injected_again) == 2


def test_memory_context_is_relevant_typed_and_ignores_expired(tmp_path, monkeypatch) -> None:
    now = memory_service.time.time()
    path = tmp_path / "user_memory.json"
    path.write_text(
        memory_service.json.dumps(
            {
                "memories": [
                    {"id": "pref", "text": "Prefiere respuestas breves", "kind": "preference", "created_at": now},
                    {"id": "api", "text": "El endpoint Aurora es /v1/aurora", "kind": "fact", "created_at": now},
                    {"id": "old", "text": "Aurora usaba /v0", "kind": "fact", "created_at": now, "expires_at": now - 1},
                    {"id": "other", "text": "La bicicleta es roja", "kind": "fact", "created_at": now},
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(memory_service, "USER_MEMORY_PATH", str(path))

    context = memory_service.memory_context_for_query("¿Cuál es el endpoint de Aurora?")

    assert '"id": "api"' in context
    assert '"id": "pref"' in context
    assert '"id": "old"' not in context
    assert '"id": "other"' not in context


def test_memory_update_preserves_provenance_and_supports_expiration_clear(tmp_path, monkeypatch) -> None:
    path = tmp_path / "user_memory.json"
    path.write_text(
        '{"memories":[{"id":"m1","text":"old","tags":[],"provenance":"manual","expires_at":123}]}',
        encoding="utf-8",
    )
    monkeypatch.setattr(memory_service, "USER_MEMORY_PATH", str(path))

    updated = memory_service._memory_update_sync(
        "m1",
        MemoryUpdateRequest(text="new", kind="decision", clear_expiration=True),
    )

    assert updated["text"] == "new"
    assert updated["kind"] == "decision"
    assert updated["provenance"] == "manual"
    assert updated["expires_at"] is None


def test_memory_update_rejects_whitespace_only_text(tmp_path, monkeypatch) -> None:
    path = tmp_path / "user_memory.json"
    path.write_text('{"memories":[{"id":"m1","text":"kept","tags":[]}]}', encoding="utf-8")
    monkeypatch.setattr(memory_service, "USER_MEMORY_PATH", str(path))

    with pytest.raises(HTTPException) as exc:
        memory_service._memory_update_sync("m1", MemoryUpdateRequest(text="   "))

    assert exc.value.status_code == 400
    assert memory_service._memory_load()["memories"][0]["text"] == "kept"


def test_malformed_expiration_is_ignored_in_context_and_refresh(tmp_path, monkeypatch) -> None:
    storage = tmp_path / "storage"
    path = storage / "user_memory.json"
    storage.mkdir()
    path.write_text(
        memory_service.json.dumps(
            {
                "memories": [
                    {"id": "bad", "text": "Aurora secret", "expires_at": "not-a-time"},
                    {"id": "good", "text": "Aurora uses blue", "created_at": memory_service.time.time()},
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(memory_service, "USER_MEMORY_PATH", str(path))
    monkeypatch.setattr(config, "PERSIST_DIR", str(storage))
    monkeypatch.setattr(
        memory_service,
        "get_llm",
        lambda *_args, **_kwargs: type(
            "LLM",
            (),
            {"complete": lambda self, _prompt: type("Response", (), {"text": "Aurora summary"})()},
        )(),
    )

    context = memory_service.memory_context_for_query("Aurora")
    refreshed = memory_service._memory_refresh_sync(memory_service.MemoryRefreshRequest())

    assert '"id": "bad"' not in context
    assert '"id": "good"' in context
    assert refreshed["count"] == 1
    assert refreshed["summary"] == "Aurora summary"


@pytest.mark.asyncio
async def test_memory_context_endpoint_returns_structured_relevant_entries(monkeypatch) -> None:
    monkeypatch.setattr(memory_service, "_authorize_system", lambda _request: None)
    monkeypatch.setattr(
        memory_service,
        "memory_context_for_query",
        lambda _query, max_entries: '[{"id":"m1","text":"relevant"}]',
    )

    result = await memory_service.memory_context(
        MemoryContextRequest(query="current turn", max_entries=3),
        object(),
    )

    assert result == {"memories": [{"id": "m1", "text": "relevant"}], "count": 1}


def test_memory_lifecycle_persists_normalized_records(tmp_path, monkeypatch) -> None:
    path = tmp_path / "user_memory.json"
    monkeypatch.setattr(memory_service, "USER_MEMORY_PATH", str(path))

    created = memory_service._memory_create_sync(
        MemoryCreateRequest(text="  Prefer concise answers.  ", tags=[" style ", ""], kind="preference")
    )
    loaded = memory_service._memory_load()
    deleted = memory_service._memory_delete_sync(created["id"])

    assert created["text"] == "Prefer concise answers."
    assert created["tags"] == ["style"]
    assert loaded["schema_version"] == 2
    assert loaded["memories"][0]["provenance"] == "manual"
    assert deleted == {"deleted": True}
    assert memory_service._memory_delete_sync("missing") == {"deleted": False}
    assert memory_service._memory_load()["memories"] == []


def test_memory_load_normalizes_legacy_records_and_skips_invalid_rows(tmp_path, monkeypatch) -> None:
    path = tmp_path / "user_memory.json"
    path.write_text(
        '{"memories":[null,{"id":"legacy","text":"kept","created_at":12}]}',
        encoding="utf-8",
    )
    monkeypatch.setattr(memory_service, "USER_MEMORY_PATH", str(path))

    loaded = memory_service._memory_load()

    assert loaded == {
        "schema_version": 2,
        "memories": [
            {
                "id": "legacy",
                "text": "kept",
                "created_at": 12,
                "kind": "note",
                "provenance": "manual",
                "updated_at": 12,
                "expires_at": None,
            }
        ],
    }


def test_memory_save_enforces_storage_limit(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(memory_service, "USER_MEMORY_PATH", str(tmp_path / "memory.json"))
    monkeypatch.setattr(config, "MEMORY_MAX_FILE_BYTES", 10)

    with pytest.raises(HTTPException) as exc:
        memory_service._memory_save({"memories": [{"text": "too large"}]})

    assert exc.value.status_code == 413


def test_memory_refresh_handles_empty_store_and_model_outage(tmp_path, monkeypatch) -> None:
    storage = tmp_path / "storage"
    path = storage / "user_memory.json"
    storage.mkdir()
    monkeypatch.setattr(memory_service, "USER_MEMORY_PATH", str(path))
    monkeypatch.setattr(config, "PERSIST_DIR", str(storage))

    empty = memory_service._memory_refresh_sync(memory_service.MemoryRefreshRequest())
    assert empty == {"status": "refreshed", "summary": "", "count": 0}

    path.write_text(
        '{"memories":[{"id":"m1","text":"First fact"},{"id":"m2","text":"Second fact"}]}',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        memory_service,
        "get_llm",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("model offline")),
    )

    degraded = memory_service._memory_refresh_sync(memory_service.MemoryRefreshRequest())

    assert degraded["count"] == 2
    assert degraded["summary"] == "First fact | Second fact"
    summary = memory_service.json.loads((storage / "user_memory_summary.json").read_text(encoding="utf-8"))
    assert summary["summary"] == degraded["summary"]


@pytest.mark.asyncio
async def test_memory_endpoints_authorize_and_delegate_without_blocking(monkeypatch) -> None:
    authorized: list[object] = []
    calls: list[str] = []
    monkeypatch.setattr(memory_service, "_authorize_system", authorized.append)

    async def direct(func, *args):
        calls.append(func.__name__)
        return func(*args)

    monkeypatch.setattr(memory_service, "run_in_threadpool", direct)
    monkeypatch.setattr(memory_service, "_run_model_task", lambda func, *args: func(*args))
    monkeypatch.setattr(memory_service, "_memory_create_sync", lambda _req: {"id": "new"})
    monkeypatch.setattr(memory_service, "_memory_update_sync", lambda _id, _req: {"id": "updated"})
    monkeypatch.setattr(memory_service, "_memory_delete_sync", lambda _id: {"deleted": True})
    monkeypatch.setattr(
        memory_service,
        "_memory_refresh_sync",
        lambda _req: {"status": "refreshed", "summary": "", "count": 0},
    )
    request = object()

    created = await memory_service.memory_create(MemoryCreateRequest(text="new"), request)
    updated = await memory_service.memory_update("m1", MemoryUpdateRequest(text="updated"), request)
    deleted = await memory_service.memory_delete("m1", request)
    refreshed = await memory_service.memory_refresh(memory_service.MemoryRefreshRequest(), request)

    assert created == {"id": "new"}
    assert updated == {"id": "updated"}
    assert deleted == {"deleted": True}
    assert refreshed["status"] == "refreshed"
    assert authorized == [request, request, request, request]
    assert calls == ["<lambda>", "<lambda>", "<lambda>", "<lambda>"]


@pytest.mark.asyncio
async def test_memory_read_endpoints_handle_missing_and_corrupt_summaries(tmp_path, monkeypatch) -> None:
    storage = tmp_path / "storage"
    storage.mkdir()
    monkeypatch.setattr(config, "PERSIST_DIR", str(storage))
    monkeypatch.setattr(memory_service, "_authorize_system", lambda _request: None)
    monkeypatch.setattr(memory_service, "_memory_load", lambda: {"memories": [{"id": "m1"}]})

    assert await memory_service.memory_list(object()) == {"memories": [{"id": "m1"}]}
    assert await memory_service.memory_summary(object()) == {
        "summary": "",
        "count": 0,
        "updated_at": 0.0,
    }

    summary_path = storage / "user_memory_summary.json"
    summary_path.write_text('{"summary":"ready","count":"2","updated_at":"3.5"}', encoding="utf-8")
    assert await memory_service.memory_summary(object()) == {
        "summary": "ready",
        "count": 2,
        "updated_at": 3.5,
    }

    summary_path.write_text("{broken", encoding="utf-8")
    with pytest.raises(HTTPException) as exc:
        await memory_service.memory_summary(object())
    assert exc.value.status_code == 500


def test_memory_context_is_bounded_and_survives_unreadable_store(monkeypatch) -> None:
    monkeypatch.setattr(
        memory_service,
        "_memory_load",
        lambda: (_ for _ in ()).throw(HTTPException(status_code=500, detail="unreadable")),
    )
    assert memory_service.memory_context_for_query("anything") == ""

    now = memory_service.time.time()
    monkeypatch.setattr(
        memory_service,
        "_memory_load",
        lambda: {
            "memories": [
                {
                    "id": "older",
                    "text": "Aurora first value",
                    "kind": "fact",
                    "updated_at": now - 100,
                },
                {
                    "id": "newer",
                    "text": "Aurora second value",
                    "kind": "decision",
                    "updated_at": now,
                },
            ]
        },
    )

    context = memory_service.memory_context_for_query("Aurora", max_entries=1, max_chars=8)

    assert memory_service.json.loads(context) == [
        {
            "id": "newer",
            "kind": "decision",
            "provenance": "manual",
            "relevance": 11.5,
            "text": "Aurora s",
        }
    ]
