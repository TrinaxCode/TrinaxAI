"""``trinaxai browse`` — list collections, files, and chunks."""
from __future__ import annotations

from typing import Any


def run(args: Any, client: Any, ui: Any, config: Any) -> int:
    sub = getattr(args, "browse_command", None) or "list"
    try:
        if sub == "list-collections" or sub == "list":
            cols = client.list_collections()
            if not cols:
                ui.info("No collections.")
                return 0
            ui.table(["id", "name"], [[c.get("id", ""), c.get("name", "")] for c in cols], title="Collections")
            return 0

        if sub == "list-files":
            collection = getattr(args, "collection", None) or "default"
            data = client.list_sources(collection)
            sources = data.get("sources", []) or []
            if not sources:
                ui.info(f"No files in collection '{collection}'.")
                return 0
            ui.table(
                ["file", "chunks", "size", "mtime"],
                [
                    [
                        s.get("file", ""),
                        s.get("chunks", 0),
                        s.get("size", 0),
                        s.get("mtime", 0),
                    ]
                    for s in sources
                ],
                title=f"Files in '{collection}' ({len(sources)})",
            )
            return 0

        if sub == "show-chunks":
            collection = getattr(args, "collection", None) or "default"
            file = getattr(args, "file", None)
            if not file:
                ui.error("File path required (use --file).")
                return 1
            data = client.list_chunks(collection, file, limit=int(getattr(args, "limit", 50) or 50))
            chunks = data.get("chunks", []) or []
            if not chunks:
                ui.info("No chunks.")
                return 0
            for i, ch in enumerate(chunks, start=1):
                ui.panel(
                    (ch.get("text", "") or "")[:1200] + ("…" if len(ch.get("text", "")) > 1200 else ""),
                    title=f"#{i} score={ch.get('score')}",
                )
            ui.info(f"Total: {data.get('total', len(chunks))}")
            return 0

        ui.error(f"Unknown subcommand: {sub}")
        return 1
    except Exception as exc:
        ui.error(f"browse {sub}: {exc}")
        return 1