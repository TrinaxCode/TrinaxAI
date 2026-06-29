"""``trinaxai index`` — trigger indexing of a folder.

Wraps the existing ``index.py`` subprocess with the right env vars, mirroring
``_run_index_job`` in rag_api.py but without the job-tracking machinery.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def run(args: Any, client: Any, ui: Any, config: Any) -> int:
    folder = getattr(args, "path", None) or getattr(args, "folder", None)
    if not folder:
        ui.error("Usage: trinaxai index /path/to/project")
        return 1
    folder_path = Path(folder).expanduser().resolve()
    if not folder_path.is_dir():
        ui.error(f"Not a directory: {folder_path}")
        return 1
    collection = getattr(args, "collection", None) or "default"
    append = bool(getattr(args, "append", False))

    # Find index.py: prefer a sibling of the project root, otherwise cwd.
    project_root = Path(__file__).resolve().parents[2]
    candidates = [
        project_root / "index.py",
        Path.cwd() / "index.py",
    ]
    index_py = next((c for c in candidates if c.is_file()), None)
    if not index_py:
        ui.error("Cannot locate index.py. Run from the TrinaxAI project root.")
        return 1

    env = {**os.environ}
    # Ensure the indexer resolves relative paths against the project root so
    # `local_sources/...` is always found regardless of caller's CWD.
    env["TRINAXAI_PROJECT_ROOT"] = str(project_root)
    env["TRINAXAI_INDEX_DIR"] = str(folder_path)
    env["TRINAXAI_COLLECTION_ID"] = collection
    env["TRINAXAI_COLLECTION_NAME"] = collection
    if append:
        env["TRINAXAI_INDEX_APPEND"] = "1"

    ui.info(f"Indexing {folder_path} into collection '{collection}' (append={append})...")
    try:
        proc = subprocess.Popen(
            [sys.executable, str(index_py)],
            stdout=sys.stdout,
            stderr=sys.stderr,
            env=env,
        )
        rc = proc.wait()
        if rc == 0:
            ui.success("Indexing completed.")
            return 0
        ui.error(f"Indexer exited with code {rc}.")
        return rc or 1
    except KeyboardInterrupt:
        ui.warn("Interrupted.")
        return 130
    except Exception as exc:
        ui.error(f"index: {exc}")
        return 1
