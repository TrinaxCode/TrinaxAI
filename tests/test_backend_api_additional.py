from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, UploadFile

from app.schemas import CollectionCreateRequest, CollectionUpdateRequest
from app.services import attachment_service, collection_service, document_service, sources_service


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


def test_collection_storage_deletion_removes_nodes_manifest_and_files(tmp_path: Path, monkeypatch) -> None:
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
    fake_index = SimpleNamespace(
        docstore=SimpleNamespace(docs=nodes),
        delete_nodes=lambda ids, **_kwargs: nodes.pop(ids[0]),
        storage_context=SimpleNamespace(persist=lambda **_kwargs: None),
    )
    monkeypatch.setattr(
        collection_service.StorageContext,
        "from_defaults",
        lambda **_kwargs: object(),
    )
    monkeypatch.setattr(collection_service, "load_index_from_storage", lambda _storage: fake_index)
    assert collection_service._delete_collection_nodes_unlocked("docs") == 1
    assert json.loads(manifest.read_text(encoding="utf-8")) == {"other:two": 2}
    assert not source.exists()


@pytest.mark.asyncio
async def test_attachment_upload_download_delete_and_validation(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(attachment_service, "CHAT_ATTACHMENTS_DIR", str(tmp_path))
    monkeypatch.setattr(attachment_service, "_authorize_system", lambda _request: None)
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
    assert (await attachment_service.attachment_delete(attachment_id, object()))["deleted"] == attachment_id
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
