from __future__ import annotations

import json
import os
import stat
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, UploadFile

from app.schemas import CollectionCreateRequest, CollectionUpdateRequest
from app.services import attachment_service, collection_service, document_service, shared_runtime, sources_service


@pytest.mark.asyncio
async def test_collection_crud_validates_uniqueness_and_default_protection(monkeypatch) -> None:
    collections = [{"id": "default", "name": "Default", "created_at": 1, "updated_at": 1}]
    monkeypatch.setattr(collection_service, "_authorize_system", lambda _request: None)
    monkeypatch.setattr(collection_service, "_read_collections_unlocked", lambda: [dict(item) for item in collections])
    monkeypatch.setattr(
        collection_service,
        "_write_collections_unlocked",
        lambda items: collections.__setitem__(slice(None), [dict(item) for item in items]),
    )

    listed = await collection_service.collections_get(object())
    assert listed["collections"][0]["id"] == "default"
    with pytest.raises(HTTPException) as blank:
        await collection_service.collections_create(CollectionCreateRequest(name=" "), object())
    assert blank.value.status_code == 400

    first = await collection_service.collections_create(CollectionCreateRequest(name="Docs"), object())
    second = await collection_service.collections_create(CollectionCreateRequest(name="Docs"), object())
    assert first["collection"]["id"] == "docs"
    assert second["collection"]["id"] == "docs-2"

    updated = await collection_service.collections_update(
        "docs",
        CollectionUpdateRequest(name="Manuals"),
        object(),
    )
    assert updated["collection"]["name"] == "Manuals"
    with pytest.raises(HTTPException) as missing:
        await collection_service.collections_update(
            "missing",
            CollectionUpdateRequest(name="Missing"),
            object(),
        )
    assert missing.value.status_code == 404
    with pytest.raises(HTTPException) as protected:
        await collection_service.collections_delete("default", object())
    assert protected.value.status_code == 400

    async def run(function, *args):
        return function(*args)

    monkeypatch.setattr(collection_service, "run_in_threadpool", run)
    monkeypatch.setattr(collection_service, "_delete_collection_nodes", lambda _cid: 3)
    deleted = await collection_service.collections_delete("docs", object())
    assert deleted["deleted_nodes"] == 3
    assert all(item["id"] != "docs" for item in collections)


@pytest.mark.asyncio
async def test_collection_list_does_not_persist_default_collection(tmp_path: Path, monkeypatch) -> None:
    collections_path = tmp_path / "collections.json"
    monkeypatch.setattr(collection_service.config, "COLLECTIONS_PATH", str(collections_path))
    monkeypatch.setattr(collection_service, "_authorize_system", lambda _request: None)

    listed = await collection_service.collections_get(object())

    assert listed["collections"][0]["id"] == "default"
    assert not collections_path.exists()


def test_collection_storage_deletion_publishes_nodes_and_manifest_together(tmp_path: Path, monkeypatch) -> None:
    persist = tmp_path / "storage"
    source = tmp_path / "local" / "collections" / "docs"
    persist.mkdir()
    source.mkdir(parents=True)
    (persist / "docstore.json").write_text("{}", encoding="utf-8")
    manifest = persist / "manifest.json"
    manifest.write_text(json.dumps({"docs:one": 1, "other:two": 2}), encoding="utf-8")
    monkeypatch.setattr(collection_service.config, "PERSIST_DIR", str(persist))
    monkeypatch.setattr(collection_service.config, "MANIFEST_PATH", str(manifest))
    monkeypatch.setattr(collection_service.config, "LOCAL_SOURCES_DIR", str(tmp_path / "local"))

    nodes = {
        "one": SimpleNamespace(metadata={"collection_id": "docs"}),
        "two": SimpleNamespace(metadata={"collection_id": "other"}),
    }

    class Storage:
        def persist(self, persist_dir: str) -> None:
            root = Path(persist_dir)
            root.mkdir(parents=True, exist_ok=True)
            (root / "docstore.json").write_text(json.dumps(sorted(nodes)), encoding="utf-8")

    fake_index = SimpleNamespace(
        docstore=SimpleNamespace(docs=nodes),
        delete_nodes=lambda ids, **_kwargs: [nodes.pop(node_id) for node_id in ids],
        storage_context=Storage(),
    )
    monkeypatch.setattr(shared_runtime.StorageContext, "from_defaults", lambda **_kwargs: object())
    monkeypatch.setattr(shared_runtime, "load_index_from_storage", lambda _storage: fake_index)
    assert shared_runtime._delete_indexed_collection("docs") == 1
    assert json.loads(manifest.read_text(encoding="utf-8")) == {"other:two": 2}
    assert source.exists()


@pytest.mark.asyncio
async def test_attachment_upload_download_delete_and_validation(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(attachment_service, "CHAT_ATTACHMENTS_DIR", str(tmp_path))
    monkeypatch.setattr(attachment_service, "_authorize_system", lambda _request: None)
    monkeypatch.setattr(attachment_service, "_client_host", lambda _request: "127.0.0.1")
    monkeypatch.setattr(attachment_service, "enforce_rate_limit", lambda *_args, **_kwargs: None)
    upload = UploadFile(
        filename="../../photo.png",
        file=BytesIO(b"image"),
        headers={"content-type": "image/png"},
    )
    stored = await attachment_service.attachment_upload(object(), upload)
    attachment_id = stored["id"]
    assert stored["name"] == "photo.png" and stored["mime_type"] == "image/png"
    response = await attachment_service.attachment_get(attachment_id, object())
    assert response.media_type == "image/png"
    assert response.headers["content-disposition"].startswith("inline")

    def popen(*_args, **_kwargs):
        return None

    monkeypatch.setattr(attachment_service.subprocess, "Popen", popen)
    opened = await attachment_service.attachment_open(attachment_id, object())
    assert opened["opened"] == attachment_id

    with pytest.raises(HTTPException) as missing_open:
        await attachment_service.attachment_open("f" * 32, object())
    assert missing_open.value.status_code == 404
    monkeypatch.setattr(
        attachment_service.subprocess, "Popen", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("open failed"))
    )
    with pytest.raises(HTTPException) as open_error:
        await attachment_service.attachment_open(attachment_id, object())
    assert open_error.value.status_code == 503

    monkeypatch.setattr(attachment_service.subprocess, "Popen", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(attachment_service, "sys", SimpleNamespace(platform="darwin"))
    await attachment_service.attachment_open(attachment_id, object())
    monkeypatch.setattr(attachment_service, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(attachment_service.os, "startfile", lambda _path: None, raising=False)
    await attachment_service.attachment_open(attachment_id, object())
    assert (await attachment_service.attachment_delete(attachment_id, object()))["deleted"] == attachment_id
    with pytest.raises(HTTPException) as delete_missing:
        await attachment_service.attachment_delete(attachment_id, object())
    assert delete_missing.value.status_code == 404
    with pytest.raises(HTTPException) as gone:
        await attachment_service.attachment_get(attachment_id, object())
    assert gone.value.status_code == 404
    with pytest.raises(HTTPException) as invalid:
        attachment_service._attachment_paths("../escape")
    assert invalid.value.status_code == 404

    empty = UploadFile(filename="empty.txt", file=BytesIO(b""))
    with pytest.raises(HTTPException) as empty_error:
        await attachment_service.attachment_upload(object(), empty)
    assert empty_error.value.status_code == 400


@pytest.mark.asyncio
async def test_attachment_upload_keeps_private_modes_when_replacing_files(tmp_path: Path, monkeypatch) -> None:
    attachments = tmp_path / "chat_attachments"
    attachments.mkdir(mode=0o755)
    attachment_id = "b" * 32
    data_path = attachments / f"{attachment_id}.bin"
    metadata_path = attachments / f"{attachment_id}.json"
    data_path.write_bytes(b"old")
    metadata_path.write_text("{}", encoding="utf-8")
    if os.name == "posix":
        attachments.chmod(0o755)
        data_path.chmod(0o644)
        metadata_path.chmod(0o644)

    monkeypatch.setattr(attachment_service, "CHAT_ATTACHMENTS_DIR", str(attachments))
    monkeypatch.setattr(attachment_service, "_authorize_system", lambda _request: None)
    monkeypatch.setattr(attachment_service, "enforce_rate_limit", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(attachment_service.uuid, "uuid4", lambda: SimpleNamespace(hex=attachment_id))

    stored = await attachment_service.attachment_upload(
        object(),
        UploadFile(filename="private.txt", file=BytesIO(b"new"), headers={"content-type": "text/plain"}),
    )

    assert stored["id"] == attachment_id
    if os.name == "posix":
        assert stat.S_IMODE(attachments.stat().st_mode) == 0o700
        assert stat.S_IMODE(data_path.stat().st_mode) == 0o600
        assert stat.S_IMODE(metadata_path.stat().st_mode) == 0o600


@pytest.mark.asyncio
async def test_attachment_download_rejects_corrupt_metadata_and_symlink(tmp_path: Path, monkeypatch) -> None:
    attachments = tmp_path / "attachments"
    attachments.mkdir()
    attachment_id = "a" * 32
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"private")
    try:
        (attachments / f"{attachment_id}.bin").symlink_to(outside)
    except OSError:
        pytest.skip("symlinks are unavailable")
    (attachments / f"{attachment_id}.json").write_text("[]", encoding="utf-8")
    monkeypatch.setattr(attachment_service, "CHAT_ATTACHMENTS_DIR", str(attachments))
    monkeypatch.setattr(attachment_service, "_authorize_system", lambda _request: None)
    monkeypatch.setattr(attachment_service, "enforce_rate_limit", lambda *_args, **_kwargs: None)

    with pytest.raises(HTTPException) as missing:
        await attachment_service.attachment_get(attachment_id, object())
    assert missing.value.status_code == 404


@pytest.mark.parametrize(
    ("filename", "expected_type"),
    [
        ("report.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        ("slides.pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
        ("budget.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        ("notes.odt", "application/vnd.oasis.opendocument.text"),
        ("deck.odp", "application/vnd.oasis.opendocument.presentation"),
    ],
)
@pytest.mark.asyncio
async def test_office_attachment_keeps_client_mime_and_download_name(
    tmp_path: Path,
    monkeypatch,
    filename: str,
    expected_type: str,
) -> None:
    monkeypatch.setattr(attachment_service, "CHAT_ATTACHMENTS_DIR", str(tmp_path))
    monkeypatch.setattr(attachment_service, "_authorize_system", lambda _request: None)
    monkeypatch.setattr(attachment_service, "enforce_rate_limit", lambda *_args, **_kwargs: None)

    stored = await attachment_service.attachment_upload(
        object(),
        UploadFile(
            filename=f"reports\\{filename}",
            file=BytesIO(b"office"),
            headers={"content-type": "application/octet-stream"},
        ),
    )

    assert stored["mime_type"] == expected_type
    response = await attachment_service.attachment_get(stored["id"], object())
    assert response.media_type == stored["mime_type"]
    assert response.headers["content-disposition"].startswith("attachment")
    assert filename in response.headers["content-disposition"]


@pytest.mark.asyncio
async def test_document_extract_text_truncation_empty_and_limit(monkeypatch) -> None:
    monkeypatch.setattr(document_service, "enforce_rate_limit", lambda *_args, **_kwargs: None)

    async def run(function, *args):
        return function(*args)

    monkeypatch.setattr(document_service, "run_in_threadpool", run)
    monkeypatch.setattr(document_service, "DOC_EXTRACT_MAX_CHARS", 4)
    result = await document_service.document_extract(
        object(),
        UploadFile(filename="note.txt", file=BytesIO(b"abcdef")),
    )
    assert result["text"] == "abcd" and result["truncated"] is True

    with pytest.raises(HTTPException) as empty:
        await document_service.document_extract(
            object(),
            UploadFile(filename="empty.txt", file=BytesIO(b"")),
        )
    assert empty.value.status_code == 400

    monkeypatch.setattr(document_service, "DOC_EXTRACT_MAX_BYTES", 2)
    with pytest.raises(HTTPException) as large:
        await document_service.document_extract(
            object(),
            UploadFile(filename="large.txt", file=BytesIO(b"three")),
        )
    assert large.value.status_code == 413


def test_sources_manifest_trim_and_bulk_delete_failure(tmp_path: Path, monkeypatch) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"docs:a": 1, "other:b": 2}), encoding="utf-8")
    monkeypatch.setattr(sources_service.config, "MANIFEST_PATH", str(manifest))
    sources_service._trim_manifest_prefix("docs:")
    assert json.loads(manifest.read_text(encoding="utf-8")) == {"other:b": 2}
    manifest.write_text("{broken", encoding="utf-8")
    sources_service._trim_manifest_prefix("docs:")
