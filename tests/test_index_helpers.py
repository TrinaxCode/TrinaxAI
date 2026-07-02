from __future__ import annotations

from unittest.mock import patch

import index


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
