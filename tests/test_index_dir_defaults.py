from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _configured_index_dir(value: str | None, persist_dir: Path) -> str:
    (persist_dir.parent / "dotenv.py").write_text(
        "def load_dotenv(*args, **kwargs):\n    return False\n",
        encoding="utf-8",
    )
    environment = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join((str(persist_dir.parent), str(ROOT))),
        "TRINAXAI_PERSIST_DIR": str(persist_dir),
    }
    if value is None:
        environment.pop("TRINAXAI_INDEX_DIR", None)
    else:
        environment["TRINAXAI_INDEX_DIR"] = value
    result = subprocess.run(
        [sys.executable, "-c", "import config; print(config.PROJECTS_DIRS[0])"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def test_index_dir_defaults_to_local_sources_and_accepts_explicit_value(tmp_path: Path) -> None:
    expected = str(ROOT / "local_sources")
    assert _configured_index_dir(None, tmp_path / "unset") == expected
    assert _configured_index_dir("", tmp_path / "empty") == expected

    explicit = tmp_path / "documents"
    assert _configured_index_dir(str(explicit), tmp_path / "explicit") == str(explicit)
