"""``trinaxai obsidian`` — import an Obsidian vault into a collection.

Copies ``*.md`` files (skipping ``.obsidian/``) from the vault into
``local_sources/collections/<id>/`` so the existing indexer picks them up.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any


def run(args: Any, client: Any, ui: Any, config: Any) -> int:
    vault = getattr(args, "vault", None)
    if not vault:
        ui.error("--vault PATH is required.")
        return 1
    collection = getattr(args, "collection", None) or "obsidian"
    vault_path = Path(vault).expanduser().resolve()
    if not vault_path.is_dir():
        ui.error(f"Not a directory: {vault_path}")
        return 1

    dest = Path("local_sources/collections") / collection
    dest.mkdir(parents=True, exist_ok=True)

    copied = 0
    skipped = 0
    src_files = list(vault_path.rglob("*.md"))
    for src in src_files:
        if any(part.startswith(".") for part in src.relative_to(vault_path).parts):
            continue
        rel = src.relative_to(vault_path)
        target = dest / rel
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
            copied += 1
        except Exception as exc:
            ui.warn(f"Skip {rel}: {exc}")
            skipped += 1

    # Ensure the collection exists server-side.
    try:
        client.create_collection(collection)
    except Exception:
        pass  # Likely already exists; ignore.

    ui.success(f"Copied {copied} note(s) from '{vault_path}' into collection '{collection}' (skipped: {skipped}).")
    ui.info(f"Run `trinaxai index --folder {dest}` to build the index.")
    return 0