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
