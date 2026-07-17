from __future__ import annotations

import json
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

import config
import index
from trinaxai_core import exclusive_process_lock


def test_diff_manifest_detects_new_changed_and_deleted() -> None:
    old_state = {
        "default:old.py": 1,
        "default:changed.py": 1,
        "other:kept.py": 1,
    }
    new_state = {
        "default:changed.py": 2,
        "default:new.py": 1,
    }
    rel_to_path = {
        "default:changed.py": "/tmp/changed.py",
        "default:new.py": "/tmp/new.py",
    }

    new_files, changed, deleted = index.diff_manifest(old_state, new_state, rel_to_path)

    assert new_files == ["/tmp/new.py"]
    assert changed == ["/tmp/changed.py"]
    assert deleted == ["default:old.py"]


def test_env_int_clamps_values() -> None:
    with patch.dict(index.os.environ, {"TRINAXAI_INDEX_BATCH_SIZE": "9999"}):
        assert index._env_int("TRINAXAI_INDEX_BATCH_SIZE", 100, minimum=1, maximum=1000) == 1000
    with patch.dict(index.os.environ, {"TRINAXAI_INDEX_BATCH_SIZE": "bad"}):
        assert index._env_int("TRINAXAI_INDEX_BATCH_SIZE", 100, minimum=1, maximum=1000) == 100


def test_iter_batches_keeps_stable_order() -> None:
    assert list(index.iter_batches(["a", "b", "c", "d", "e"], batch_size=2)) == [
        ["a", "b"],
        ["c", "d"],
        ["e"],
    ]


def test_office_documents_use_the_document_size_limit() -> None:
    assert config.max_file_bytes("slides.pptx") == config.DOCUMENT_MAX_FILE_BYTES
    assert config.max_file_bytes("manual.PDF") == config.DOCUMENT_MAX_FILE_BYTES
    assert config.max_file_bytes("budget.xlsx") == config.DOCUMENT_MAX_FILE_BYTES
    assert config.max_file_bytes("records.csv") == config.MAX_FILE_BYTES


def test_collect_files_keeps_supported_special_names_and_env(tmp_path) -> None:
    expected = {"README", "LICENSE", "Makefile", "Gemfile", "Procfile", ".env", "Dockerfile"}
    for name in expected:
        (tmp_path / name).write_text("content", encoding="utf-8")

    names = {Path(path).name for path in index.collect_files(str(tmp_path))}

    assert expected <= names


def test_collect_files_accepts_unknown_text_but_rejects_binary(tmp_path) -> None:
    text = tmp_path / "knowledge.custom-format"
    binary = tmp_path / "archive.custom-format"
    text.write_text("Readable domain-specific knowledge", encoding="utf-8")
    binary.write_bytes(b"\x00\x01\x02\xff" * 100)

    names = {Path(path).name for path in index.collect_files(str(tmp_path))}

    assert text.name in names
    assert binary.name not in names


def test_document_content_extractors_cover_web_notebooks_email_and_epub(tmp_path) -> None:
    html = tmp_path / "page.html"
    html.write_text("<h1>Manual</h1><script>ignore me</script><p>Useful HTML text</p>", encoding="utf-8")
    notebook = tmp_path / "analysis.ipynb"
    notebook.write_text(
        json.dumps({"cells": [{"cell_type": "markdown", "source": ["Notebook insight"]}]}),
        encoding="utf-8",
    )
    email = tmp_path / "message.eml"
    email.write_text("Subject: Roadmap\nFrom: dev@example.com\n\nEmail body insight", encoding="utf-8")
    epub = tmp_path / "book.epub"
    with zipfile.ZipFile(epub, "w") as archive:
        archive.writestr("chapter.xhtml", "<html><body><h1>Chapter</h1><p>EPUB insight</p></body></html>")

    assert "Useful HTML text" in index._load_file_documents(str(html))[0].text
    assert "ignore me" not in index._load_file_documents(str(html))[0].text
    assert "Notebook insight" in index._load_file_documents(str(notebook))[0].text
    assert "Email body insight" in index._load_file_documents(str(email))[0].text
    assert "EPUB insight" in index._load_file_documents(str(epub))[0].text


def test_decode_text_bytes_falls_back_past_windows_charmap() -> None:
    assert index._decode_text_bytes(b"before \x90 after") == "before \x90 after"


def test_load_text_document_reads_bytes_without_locale(tmp_path) -> None:
    path = tmp_path / "sample.txt"
    path.write_bytes(b"caf\xe9 \x90")

    doc = index._load_text_document(str(path))

    assert doc.text == "café \x90"
    assert doc.metadata["file_path"] == str(path)


def test_remove_obsolete_nodes_supports_legacy_rel_path_metadata() -> None:
    class Node:
        def __init__(self, metadata: dict[str, str]) -> None:
            self.metadata = metadata

    class Docstore:
        docs = {
            "legacy": Node({"rel_path": "changed.py"}),
            "current": Node({"source_key": "default:deleted.py"}),
            "kept": Node({"rel_path": "kept.py"}),
        }

    class FakeIndex:
        docstore = Docstore()

        def __init__(self) -> None:
            self.deleted: list[str] = []

        def delete_nodes(self, node_ids: list[str], delete_from_docstore: bool = True) -> None:
            self.deleted = node_ids

    fake = FakeIndex()

    with patch.object(index, "_source_key", return_value="default:changed.py"):
        removed = index.remove_obsolete_nodes(fake, ["C:/repo/changed.py"], ["default:deleted.py"])

    assert removed == 2
    assert fake.deleted == ["legacy", "current"]


def test_remove_obsolete_nodes_never_deletes_same_path_from_other_collection() -> None:
    class Node:
        def __init__(self, metadata: dict[str, str]) -> None:
            self.metadata = metadata

    class Docstore:
        docs = {
            "active": Node({"source_key": "default:README.md", "rel_path": "README.md"}),
            "other": Node({"source_key": "other:README.md", "collection_id": "other", "rel_path": "README.md"}),
        }

    class FakeIndex:
        docstore = Docstore()

        def __init__(self) -> None:
            self.deleted: list[str] = []

        def delete_nodes(self, node_ids: list[str], delete_from_docstore: bool = True) -> None:
            self.deleted = node_ids

    fake = FakeIndex()
    with patch.object(index, "_source_key", return_value="default:README.md"):
        index.remove_obsolete_nodes(fake, ["README.md"], [])

    assert fake.deleted == ["active"]


def test_current_state_detects_subsecond_changes_and_size(tmp_path) -> None:
    path = tmp_path / "sample.txt"
    path.write_text("a", encoding="utf-8")
    first = index.current_state([str(path)])
    path.write_text("longer", encoding="utf-8")
    second = index.current_state([str(path)])
    assert first != second


def test_process_lock_rejects_a_second_writer(tmp_path) -> None:
    lock_path = tmp_path / "index.lock"
    with exclusive_process_lock(lock_path):
        with pytest.raises(TimeoutError):
            with exclusive_process_lock(lock_path, timeout=0.01, poll_interval=0.01):
                pass


def test_failed_changed_file_keeps_old_fingerprint_and_nodes(monkeypatch) -> None:
    changed = "/tmp/changed.pdf"
    old_state = {"default:changed.pdf": {"mtime_ns": 1, "size": 10}}
    new_state = {"default:changed.pdf": {"mtime_ns": 2, "size": 20}}
    removed: list[tuple[list[str], list[str]]] = []

    class FakeIndex:
        pass

    monkeypatch.setattr(
        index,
        "prepare_batch",
        lambda *_args, **_kwargs: index.PreparedBatch(failures={changed: "broken PDF"}),
    )
    monkeypatch.setattr(
        index,
        "remove_obsolete_nodes",
        lambda _index, changed_paths, deleted: removed.append((changed_paths, deleted)) or 0,
    )
    monkeypatch.setattr(index, "_source_key", lambda _path: "default:changed.pdf")

    result = index.apply_file_updates(FakeIndex(), [changed], changed={changed})
    effective = index._state_after_failures(old_state, new_state, set(result.failures))

    assert removed == []
    assert effective == old_state


def test_manifest_recovery_preserves_foreign_collection(monkeypatch, tmp_path) -> None:
    class Node:
        def __init__(self, source_key: str, collection_id: str, rel_path: str) -> None:
            self.metadata = {
                "source_key": source_key,
                "collection_id": collection_id,
                "rel_path": rel_path,
            }

    class Docstore:
        docs = {
            "active": Node("default:active.txt", "default", "active.txt"),
            "foreign": Node("other:foreign.txt", "other", "foreign.txt"),
        }

    class Storage:
        def persist(self, persist_dir: str) -> None:
            Path(persist_dir).mkdir(parents=True, exist_ok=True)
            (Path(persist_dir) / "docstore.json").write_text("{}", encoding="utf-8")

    class FakeIndex:
        docstore = Docstore()
        storage_context = Storage()

    import llama_index.core

    monkeypatch.setattr(config, "PERSIST_DIR", str(tmp_path))
    monkeypatch.setattr(config, "MANIFEST_PATH", str(tmp_path / "manifest.json"))
    monkeypatch.setattr(index, "COLLECTION_ID", "default")
    monkeypatch.setattr(index, "_source_key", lambda _path: "default:active.txt")
    monkeypatch.setattr(llama_index.core.StorageContext, "from_defaults", lambda **_kwargs: object())
    monkeypatch.setattr(llama_index.core, "load_index_from_storage", lambda _storage: FakeIndex())
    monkeypatch.setattr(
        index,
        "apply_file_updates",
        lambda *_args, **_kwargs: index.IndexUpdateResult(indexed_paths={"/src/active.txt"}),
    )
    new_state = {"default:active.txt": {"mtime_ns": 10, "size": 20}}

    assert index.run_manifest_recovery(new_state, {"default:active.txt": "/src/active.txt"}) == 0

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["default:active.txt"] == new_state["default:active.txt"]
    assert manifest["other:foreign.txt"] == {"unverified": True}
