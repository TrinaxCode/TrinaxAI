from __future__ import annotations

import json

from starlette.testclient import TestClient

import rag_api


class _FakeNode:
    metadata = {"rel_path": "demo/file.py", "project": "demo"}

    def get_content(self) -> str:
        return "print('hello')"


class _FakeDocstore:
    docs = {"node-1": _FakeNode()}


def test_research_iter_nodes_reads_loaded_docstore(monkeypatch) -> None:
    monkeypatch.setattr(rag_api, "_fusion_retriever", object())
    monkeypatch.setattr(rag_api, "_index_docstore", _FakeDocstore())

    rows = list(rag_api._research_iter_nodes("default"))

    assert len(rows) == 1
    assert rows[0][0] == "node-1"
    assert rows[0][1] is _FakeDocstore.docs["node-1"]
    assert rows[0][1].metadata["rel_path"] == "demo/file.py"
    assert list(rag_api._research_iter_nodes("other")) == []


def test_factory_reset_clears_runtime_index_data(tmp_path, monkeypatch) -> None:
    base = tmp_path / "repo"
    storage = base / "storage"
    local_sources = base / "local_sources"
    storage.mkdir(parents=True)
    local_sources.mkdir(parents=True)
    (storage / "docstore.json").write_text("{}", encoding="utf-8")
    (storage / "usage.jsonl").write_text("{}", encoding="utf-8")
    (local_sources / "indexed.txt").write_text("indexed", encoding="utf-8")

    monkeypatch.setattr(rag_api.config, "BASE_DIR", str(base))
    monkeypatch.setattr(rag_api.config, "PERSIST_DIR", str(storage))
    monkeypatch.setattr(rag_api.config, "LOCAL_SOURCES_DIR", str(local_sources))
    monkeypatch.setattr(rag_api.config, "COLLECTIONS_PATH", str(storage / "collections.json"))
    monkeypatch.setattr(rag_api, "APP_STATE_PATH", str(storage / "app_state.json"))
    monkeypatch.setattr(rag_api, "_fusion_retriever", object())
    monkeypatch.setattr(rag_api, "_index_docstore", object())
    monkeypatch.setattr(rag_api, "KNOWN_PROJECTS", ["demo"])
    rag_api._retrieval_cache[("q",)] = (1.0, [])
    rag_api._sources_cache[("sources",)] = (1.0, [])

    result = rag_api._factory_reset_runtime_state({"tc-reset-at": "123"})

    assert result["indexed"] is False
    assert rag_api._fusion_retriever is None
    assert rag_api._index_docstore is None
    assert rag_api.KNOWN_PROJECTS == []
    assert rag_api._retrieval_cache == {}
    assert rag_api._sources_cache == {}
    assert not (storage / "docstore.json").exists()
    assert not (storage / "usage.jsonl").exists()
    assert not (local_sources / "indexed.txt").exists()
    assert json.loads((storage / "app_state.json").read_text(encoding="utf-8")) == {
        "tc-reset-at": "123"
    }
    collections = json.loads((storage / "collections.json").read_text(encoding="utf-8"))
    assert collections["collections"][0]["id"] == "default"


def test_app_state_get_uses_etag_for_unchanged_state(tmp_path, monkeypatch) -> None:
    state_path = tmp_path / "app_state.json"
    state_path.write_text(json.dumps({"tc-theme": "dark"}), encoding="utf-8")
    monkeypatch.setattr(rag_api, "APP_STATE_PATH", str(state_path))
    client = TestClient(rag_api.app)

    first = client.get("/app-state")
    etag = first.headers["etag"]
    second = client.get("/app-state", headers={"If-None-Match": etag})

    assert first.json()["values"] == {"tc-theme": "dark"}
    assert second.status_code == 304
    assert second.content == b""


def test_app_state_put_does_not_echo_large_state(tmp_path, monkeypatch) -> None:
    state_path = tmp_path / "app_state.json"
    monkeypatch.setattr(rag_api, "APP_STATE_PATH", str(state_path))
    monkeypatch.setattr(rag_api, "ADMIN_TOKEN", "test-token")
    client = TestClient(rag_api.app)

    response = client.put(
        "/app-state",
        headers={"X-Admin-Token": "test-token"},
        json={"values": {"tc-chat-sessions": "x" * 20_000}},
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert len(response.content) < 100


def test_chat_attachment_is_available_to_another_client(tmp_path, monkeypatch) -> None:
    attachments = tmp_path / "chat_attachments"
    monkeypatch.setattr(rag_api, "CHAT_ATTACHMENTS_DIR", str(attachments))
    client = TestClient(rag_api.app)

    uploaded = client.post(
        "/attachments",
        files={"file": ("manual.pdf", b"%PDF-shared", "application/pdf")},
    )

    assert uploaded.status_code == 200
    metadata = uploaded.json()
    assert metadata["storage_key"] == f"server:{metadata['id']}"
    downloaded = TestClient(rag_api.app).get(f"/attachments/{metadata['id']}")
    assert downloaded.status_code == 200
    assert downloaded.content == b"%PDF-shared"
    assert downloaded.headers["content-type"] == "application/pdf"
    assert downloaded.headers["content-disposition"].startswith("inline")


def test_chat_attachment_limit_removes_partial_file(tmp_path, monkeypatch) -> None:
    attachments = tmp_path / "chat_attachments"
    monkeypatch.setattr(rag_api, "CHAT_ATTACHMENTS_DIR", str(attachments))
    monkeypatch.setattr(rag_api, "CHAT_ATTACHMENT_MAX_BYTES", 4)

    response = TestClient(rag_api.app).post(
        "/attachments",
        files={"file": ("large.pptx", b"12345", "application/octet-stream")},
    )

    assert response.status_code == 413
    assert not list(attachments.glob("*"))


def test_chat_attachment_quota_removes_rejected_file(tmp_path, monkeypatch) -> None:
    attachments = tmp_path / "chat_attachments"
    monkeypatch.setattr(rag_api, "CHAT_ATTACHMENTS_DIR", str(attachments))
    monkeypatch.setattr(rag_api, "CHAT_ATTACHMENTS_MAX_BYTES", 4)

    response = TestClient(rag_api.app).post(
        "/attachments",
        files={"file": ("large.txt", b"12345", "text/plain")},
    )

    assert response.status_code == 507
    assert not list(attachments.glob("*"))


def test_legacy_unsafe_attachment_type_is_forced_to_download(tmp_path, monkeypatch) -> None:
    attachments = tmp_path / "chat_attachments"
    attachments.mkdir()
    attachment_id = "a" * 32
    (attachments / f"{attachment_id}.bin").write_bytes(b"<script>alert(1)</script>")
    (attachments / f"{attachment_id}.json").write_text(
        json.dumps({"name": "page.html", "mime_type": "text/html"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(rag_api, "CHAT_ATTACHMENTS_DIR", str(attachments))

    response = TestClient(rag_api.app).get(f"/attachments/{attachment_id}")

    assert response.headers["content-type"] == "application/octet-stream"
    assert response.headers["content-disposition"].startswith("attachment")
    assert response.headers["x-content-type-options"] == "nosniff"


def test_ensure_collection_sanitizes_path_segments(tmp_path, monkeypatch) -> None:
    collections_path = tmp_path / "collections.json"
    monkeypatch.setattr(rag_api.config, "COLLECTIONS_PATH", str(collections_path))
    monkeypatch.setattr(rag_api.config, "PERSIST_DIR", str(tmp_path))

    collection = rag_api._ensure_collection("../../outside")

    assert collection["id"] == "outside"
    assert ".." not in collection["id"]


def test_chat_rejects_empty_or_roleless_conversations() -> None:
    client = TestClient(rag_api.app)

    empty = client.post("/v1/chat/completions", json={"messages": []})
    roleless = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "system", "content": "instructions"}]},
    )

    assert empty.status_code == 422
    assert roleless.status_code == 422


def test_chat_rejects_oversized_messages() -> None:
    response = TestClient(rag_api.app).post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "x" * 100_001}]},
    )

    assert response.status_code == 422
