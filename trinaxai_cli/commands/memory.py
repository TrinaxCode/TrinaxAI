"""``trinaxai memory`` — persistent memory management."""

from __future__ import annotations

from typing import Any


def run(args: Any, client: Any, ui: Any, config: Any) -> int:
    action = getattr(args, "memory_command", None) or "list"
    try:
        if action == "list":
            mems = client.list_memories()
            if not mems:
                ui.info("No memories.")
                return 0
            ui.table(
                ["id", "text", "tags", "created"],
                [
                    [
                        m.get("id", "")[:8],
                        (m.get("text", "")[:80] + ("…" if len(m.get("text", "")) > 80 else "")),
                        ", ".join(m.get("tags", []) or []),
                        m.get("created_at", 0),
                    ]
                    for m in mems
                ],
                title=f"Memories ({len(mems)})",
            )
            return 0
        if action == "add":
            text = getattr(args, "text", None) or ui.prompt("Memory text")
            if not text:
                ui.error("Text required.")
                return 1
            tags = getattr(args, "tags", None)
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",") if t.strip()]
            elif tags is None:
                tags = []
            mem = client.add_memory(text, tags)
            ui.success(f"Added memory {mem.get('id', '')[:8]}")
            return 0
        if action == "forget":
            flagged = getattr(args, "memory_id", None)
            positional = getattr(args, "memory_id_positional", None)
            if flagged and positional and flagged != positional:
                ui.error("Provide one memory id; the positional id and --memory-id disagree.")
                return 1
            mid = flagged or positional or ui.prompt("Memory id (or prefix)")
            if not mid:
                ui.error("Memory id required.")
                return 1
            # Allow prefix matching for convenience (UUIDs are 32 chars).
            if len(mid) < 32:
                matches = [m for m in client.list_memories() if m.get("id", "").startswith(mid)]
                if len(matches) == 1:
                    mid = matches[0]["id"]
                elif len(matches) > 1:
                    ui.error(f"Ambiguous id prefix; matches: {[m['id'][:8] for m in matches]}")
                    return 1
                else:
                    ui.error(f"No memory matches prefix '{mid}'.")
                    return 1
            ok = client.delete_memory(mid)
            ui.success("Deleted." if ok else "Not found.")
            return 0 if ok else 1
        if action == "refresh":
            res = client.refresh_memory()
            ui.success(f"Refreshed summary ({res.get('count', 0)} memories).")
            ui.panel(res.get("summary", "(empty)"), title="Memory summary")
            return 0
        if action == "summary":
            res = client.memory_summary()
            ui.panel(res.get("summary", "(empty)"), title="Current summary")
            return 0
        ui.error(f"Unknown action: {action}")
        return 1
    except Exception as exc:
        ui.error(f"memory {action}: {exc}")
        return 1
