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
