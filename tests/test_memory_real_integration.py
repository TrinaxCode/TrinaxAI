from __future__ import annotations

import os

import pytest

import config
from app.schemas import MemoryCreateRequest, MemoryRefreshRequest
from app.services import memory_service

pytestmark = pytest.mark.skipif(
    os.getenv("TRINAXAI_RUN_REAL_MEMORY_TEST") != "1",
    reason="requires a running Ollama server and the configured general model",
)


def test_real_memory_persistence_and_summary(tmp_path, monkeypatch) -> None:
    """Exercise durable storage and summary generation through real Ollama."""
    storage = tmp_path / "storage"
    memory_path = storage / "user_memory.json"
    monkeypatch.setattr(config, "PERSIST_DIR", str(storage))
    monkeypatch.setattr(memory_service, "USER_MEMORY_PATH", str(memory_path))

    created = memory_service._memory_create_sync(
        MemoryCreateRequest(
            text="Mi proyecto Aurora usa el color turquesa y prefiere respuestas breves.",
            tags=["proyecto", "preferencia"],
        )
    )
    assert memory_path.is_file()
    assert memory_service._memory_load()["memories"][0]["id"] == created["id"]

    refreshed = memory_service._memory_refresh_sync(MemoryRefreshRequest())
    assert refreshed["count"] == 1
    assert refreshed["summary"].strip()
    assert memory_service.memory_summary_text() == refreshed["summary"]

    assert memory_service._memory_delete_sync(created["id"]) == {"deleted": True}
    cleared = memory_service._memory_refresh_sync(MemoryRefreshRequest())
    assert cleared["count"] == 0
    assert memory_service.memory_summary_text() == ""
