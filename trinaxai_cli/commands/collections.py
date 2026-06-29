"""``trinaxai collections`` — manage collections."""
from __future__ import annotations

from typing import Any


def run(args: Any, client: Any, ui: Any, config: Any) -> int:
    action = getattr(args, "collections_command", None) or "list"
    try:
        if action == "list":
            cols = client.list_collections()
            if not cols:
                ui.info("No collections.")
                return 0
            ui.table(
                ["id", "name", "created"],
                [[c.get("id", ""), c.get("name", ""), c.get("created_at", 0)] for c in cols],
                title="Collections",
            )
            return 0
        if action == "create":
            name = getattr(args, "name", None) or ui.prompt("Collection name")
            if not name:
                ui.error("Name required.")
                return 1
            col = client.create_collection(name)
            ui.success(f"Created '{col.get('id')}' ({col.get('name')})")
            return 0
        if action == "delete":
            cid = getattr(args, "collection_id", None) or ui.prompt("Collection id")
            if not cid:
                ui.error("Collection id required.")
                return 1
            if cid == "default":
                ui.error("Cannot delete the 'default' collection.")
                return 1
            if not ui.confirm(f"Delete collection '{cid}' and its indexed files?", default=False):
                return 1
            n = client.delete_collection(cid)
            ui.success(f"Deleted '{cid}' (nodes removed: {n})")
            return 0
        if action == "use":
            cid = getattr(args, "collection_id", None) or ui.prompt("Collection id to activate")
            if not cid:
                ui.error("Collection id required.")
                return 1
            # Persist in shared config (best-effort; not enforced).
            try:
                config.ui["active_collection"] = cid  # type: ignore[index]
                config.save()
            except Exception:
                pass
            ui.success(f"Active collection set to '{cid}'.")
            return 0
        ui.error(f"Unknown action: {action}")
        return 1
    except Exception as exc:
        ui.error(f"collections {action}: {exc}")
        return 1