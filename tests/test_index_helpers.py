from __future__ import annotations

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
    assert config.max_file_bytes("records.csv") == config.MAX_FILE_BYTES


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
