"""Versioned app-state synchronization and concurrency regressions."""

from __future__ import annotations

import json
import os
import stat

import pytest
from starlette.testclient import TestClient

import rag_api
from app.services import app_state_service, runtime_context, runtime_engine, shared_runtime
from app.services.engine_state import state


def _client(tmp_path, monkeypatch) -> tuple[TestClient, object]:
    state_path = tmp_path / "app_state.json"
    monkeypatch.setattr(app_state_service, "APP_STATE_PATH", str(state_path))
    return TestClient(rag_api.app, client=("127.0.0.1", 50100)), state_path


def _put(client: TestClient, revision: int, operations: list[dict], device: str = "device-alpha"):
    return client.put(
        "/app-state",
        headers={"If-Match": f'"trinaxai-app-state-v2-{revision}"'},
        json={
            "schema_version": 2,
            "device_id": device,
            "base_revision": revision,
            "operations": operations,
        },
    )


def test_persist_hardening_recurses_without_following_symlinks(tmp_path) -> None:
    storage = tmp_path / "storage"
    attachment_dir = storage / "chat_attachments"
    nested = storage / "index"
    attachment_dir.mkdir(parents=True, mode=0o755)
    nested.mkdir(mode=0o755)
    memory = storage / "user_memory.json"
    attachment = attachment_dir / "legacy.bin"
    index = nested / "docstore.json"
    external = tmp_path / "outside.json"
    for path in (memory, attachment, index, external):
        path.write_text("test", encoding="utf-8")
        path.chmod(0o644)
    storage.chmod(0o755)
    try:
        (storage / "outside-link").symlink_to(external)
    except OSError:
        symlink_supported = False
    else:
        symlink_supported = True

    runtime_context.harden_persist_directory(str(storage))

    if os.name == "posix":
        assert stat.S_IMODE(storage.stat().st_mode) == 0o700
        assert stat.S_IMODE(attachment_dir.stat().st_mode) == 0o700
        assert stat.S_IMODE(nested.stat().st_mode) == 0o700
        assert all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in (memory, attachment, index))
        if symlink_supported:
            assert stat.S_IMODE(external.stat().st_mode) == 0o644


def test_persist_hardening_rejects_a_symlinked_storage_root(tmp_path) -> None:
    actual = tmp_path / "actual"
    actual.mkdir()
    marker = actual / "keep.txt"
    marker.write_text("untouched", encoding="utf-8")
    link = tmp_path / "storage"
    try:
        link.symlink_to(actual, target_is_directory=True)
    except OSError:
        pytest.skip("Directory symlinks are unavailable on this host")

    with pytest.raises(RuntimeError, match="must be a real directory"):
        runtime_context.harden_persist_directory(str(link))
    assert marker.read_text(encoding="utf-8") == "untouched"


def test_persist_hardening_creates_private_storage_on_first_start(tmp_path) -> None:
    storage = tmp_path / "new-storage"

    runtime_context.harden_persist_directory(str(storage))

    assert storage.is_dir()
    if os.name == "posix":
        assert stat.S_IMODE(storage.stat().st_mode) == 0o700


def test_runtime_initialization_hardens_persistent_storage(tmp_path, monkeypatch) -> None:
    storage = tmp_path / "storage"
    storage.mkdir(mode=0o755)
    memory = storage / "user_memory.json"
    memory.write_text("test", encoding="utf-8")
    memory.chmod(0o644)
    monkeypatch.setattr(shared_runtime.config, "PERSIST_DIR", str(storage))
    monkeypatch.setattr(shared_runtime.config, "make_embed", lambda: "embed")
    monkeypatch.setattr(shared_runtime.config, "make_reranker", lambda: None)
    monkeypatch.setattr(shared_runtime, "build_engine", lambda: True)
    monkeypatch.setattr(state, "reranker", None)

    runtime_engine.initialize_runtime()

    if os.name == "posix":
        assert stat.S_IMODE(storage.stat().st_mode) == 0o700
        assert stat.S_IMODE(memory.stat().st_mode) == 0o600


def test_legacy_document_is_migrated_without_losing_values(tmp_path, monkeypatch) -> None:
    client, state_path = _client(tmp_path, monkeypatch)
    state_path.write_text(json.dumps({"tc-theme": "dark", "other": "ignored"}), encoding="utf-8")

    response = client.get("/app-state")

    assert response.status_code == 200
    assert response.headers["etag"] == '"trinaxai-app-state-v2-0"'
    assert response.json() == {
        "ok": True,
        "schema_version": 2,
        "revision": 0,
        "values": {"tc-theme": "dark"},
    }
    assert json.loads(state_path.read_text(encoding="utf-8")) == {
        "schema_version": 2,
        "revision": 0,
        "values": {"tc-theme": "dark"},
    }


def test_incremental_set_and_real_delete_advance_revision(tmp_path, monkeypatch) -> None:
    client, state_path = _client(tmp_path, monkeypatch)

    created = _put(client, 0, [{"op": "set", "key": "tc-theme", "value": "dark"}])
    deleted = _put(client, 1, [{"op": "delete", "key": "tc-theme"}])
    current = client.get("/app-state")

    assert created.status_code == 200
    assert created.json()["revision"] == 1
    assert deleted.status_code == 200
    assert deleted.json()["revision"] == 2
    assert current.json()["values"] == {}
    assert current.headers["etag"] == '"trinaxai-app-state-v2-2"'
    if os.name == "posix":
        assert stat.S_IMODE(state_path.parent.stat().st_mode) == 0o700
        assert stat.S_IMODE(state_path.stat().st_mode) == 0o600


def test_two_devices_conflict_then_rebase_on_server_revision(tmp_path, monkeypatch) -> None:
    client, _state_path = _client(tmp_path, monkeypatch)

    first = _put(
        client,
        0,
        [{"op": "set", "key": "tc-theme", "value": "dark"}],
        "device-alpha",
    )
    conflict = _put(
        client,
        0,
        [{"op": "set", "key": "tc-lang", "value": "es"}],
        "device-bravo",
    )

    assert first.status_code == 200
    assert conflict.status_code == 409
    assert conflict.json()["revision"] == 1
    assert conflict.json()["values"] == {"tc-theme": "dark"}

    rebased = _put(
        client,
        conflict.json()["revision"],
        [{"op": "set", "key": "tc-lang", "value": "es"}],
        "device-bravo",
    )
    assert rebased.status_code == 200
    assert rebased.json()["revision"] == 2
    assert client.get("/app-state").json()["values"] == {
        "tc-theme": "dark",
        "tc-lang": "es",
    }


def test_stale_snapshot_cannot_resurrect_a_deleted_key(tmp_path, monkeypatch) -> None:
    client, _state_path = _client(tmp_path, monkeypatch)
    _put(client, 0, [{"op": "set", "key": "tc-obsolete", "value": "old"}])
    _put(client, 1, [{"op": "delete", "key": "tc-obsolete"}])

    stale = client.put(
        "/app-state",
        headers={"If-Match": '"trinaxai-app-state-v2-1"'},
        json={"base_revision": 1, "values": {"tc-obsolete": "old"}},
    )

    assert stale.status_code == 409
    assert stale.json()["revision"] == 2
    assert "tc-obsolete" not in stale.json()["values"]
    assert client.get("/app-state").json()["values"] == {}


def test_legacy_merge_requires_cas_once_state_exists(tmp_path, monkeypatch) -> None:
    client, _state_path = _client(tmp_path, monkeypatch)
    pristine = client.put("/app-state", json={"values": {"tc-theme": "dark"}})
    unsafe = client.put("/app-state", json={"values": {"tc-lang": "es"}})

    assert pristine.status_code == 200
    assert unsafe.status_code == 428


def test_reset_revision_never_reuses_a_pre_reset_revision(tmp_path, monkeypatch) -> None:
    _client(tmp_path, monkeypatch)
    # Factory reset clears the whole configured persistence directory, so use
    # a self-contained project root for this integration assertion.
    base = tmp_path / "repo"
    storage = base / "storage"
    sources = base / "sources"
    storage.mkdir(parents=True)
    sources.mkdir()
    state_path = storage / "app_state.json"
    monkeypatch.setattr(app_state_service.config, "BASE_DIR", str(base))
    monkeypatch.setattr(app_state_service.config, "PERSIST_DIR", str(storage))
    monkeypatch.setattr(app_state_service.config, "LOCAL_SOURCES_DIR", str(sources))
    monkeypatch.setattr(app_state_service.config, "COLLECTIONS_PATH", str(storage / "collections.json"))
    monkeypatch.setattr(app_state_service, "APP_STATE_PATH", str(state_path))
    state_path.write_text(
        json.dumps({"schema_version": 2, "revision": 7, "values": {"tc-theme": "dark"}}),
        encoding="utf-8",
    )

    app_state_service._factory_reset_runtime_state({"tc-reset-at": "123"})
    document = json.loads(state_path.read_text(encoding="utf-8"))

    assert document["revision"] == 8
    assert document["values"] == {"tc-reset-at": "123"}


def test_unreadable_state_does_not_look_empty(tmp_path, monkeypatch) -> None:
    client, state_path = _client(tmp_path, monkeypatch)
    assert _put(client, 0, [{"op": "set", "key": "tc-chat-sessions", "value": "[1]"}]).status_code == 200
    real_open = open

    def flaky(path, *args, **kwargs):
        if str(path) == str(state_path):
            raise OSError(5, "Input/output error")
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr("builtins.open", flaky)
    assert client.get("/app-state").status_code == 503
    assert _put(client, 0, [{"op": "set", "key": "tc-lang", "value": "es"}]).status_code == 503
    monkeypatch.undo()
    assert json.loads(state_path.read_text())["values"] == {"tc-chat-sessions": "[1]"}


def test_corrupt_state_is_quarantined_not_overwritten(tmp_path, monkeypatch) -> None:
    client, state_path = _client(tmp_path, monkeypatch)
    state_path.write_text("{broken", encoding="utf-8")
    assert client.get("/app-state").json()["revision"] == 0
    assert list(tmp_path.glob("app_state.json.corrupt-*"))


def test_corrupt_state_that_cannot_be_quarantined_is_unavailable(tmp_path, monkeypatch) -> None:
    client, state_path = _client(tmp_path, monkeypatch)
    state_path.write_text("{broken", encoding="utf-8")

    def refuse(*_args, **_kwargs):
        raise OSError(30, "Read-only file system")

    monkeypatch.setattr(app_state_service.os, "replace", refuse)
    assert client.get("/app-state").status_code == 503
    assert state_path.read_text(encoding="utf-8") == "{broken"


def test_compat_reader_returns_empty_when_state_is_unreadable(tmp_path, monkeypatch) -> None:
    _client(tmp_path, monkeypatch)
    monkeypatch.setattr(
        app_state_service,
        "_read_app_state_document",
        lambda: (_ for _ in ()).throw(app_state_service.HTTPException(status_code=503, detail="x")),
    )
    assert app_state_service._read_app_state() == {}
