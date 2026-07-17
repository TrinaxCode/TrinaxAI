"""Versioned app-state synchronization and concurrency regressions."""

from __future__ import annotations

import json

from starlette.testclient import TestClient

import rag_api
from app.services import app_state_service


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
    client, _state_path = _client(tmp_path, monkeypatch)

    created = _put(client, 0, [{"op": "set", "key": "tc-theme", "value": "dark"}])
    deleted = _put(client, 1, [{"op": "delete", "key": "tc-theme"}])
    current = client.get("/app-state")

    assert created.status_code == 200
    assert created.json()["revision"] == 1
    assert deleted.status_code == 200
    assert deleted.json()["revision"] == 2
    assert current.json()["values"] == {}
    assert current.headers["etag"] == '"trinaxai-app-state-v2-2"'


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
