"""``trinaxai watch`` — file watcher control."""

from __future__ import annotations

from typing import Any


def run(args: Any, client: Any, ui: Any, config: Any) -> int:
    action = getattr(args, "watch_command", None) or "status"
    try:
        if action == "start":
            paths = getattr(args, "paths", None)
            collection = getattr(args, "collection", None)
            res = client.watch_start(paths=paths, collection=collection)
            ui.success(res.get("status", "ok"))
            for p in res.get("watching", []):
                ui.info(f"  • {p}")
            return 0
        if action == "stop":
            res = client.watch_stop()
            ui.success(res.get("status", "stopped"))
            return 0
        if action == "status":
            res = client.watch_status()
            if res.get("running"):
                ui.success(f"Watching {len(res.get('watching', []))} path(s) — {res.get('events_seen', 0)} events")
                for p in res.get("watching", []):
                    ui.info(f"  • {p}")
            else:
                ui.warn("Watcher is not running.")
            job = res.get("job") if isinstance(res.get("job"), dict) else {}
            job_status = str(job.get("status") or "idle")
            if job_status != "idle":
                pending = int(job.get("pending_events") or 0)
                active_root = str(job.get("active_root") or "")
                detail = f"Indexer: {job_status}"
                if pending:
                    detail += f" · {pending} event(s) queued"
                if active_root:
                    detail += f" · {active_root}"
                ui.info(detail)
            if job.get("last_error"):
                ui.error(f"Last watcher error: {job['last_error']}")
            return 0
        ui.error(f"Unknown action: {action}")
        return 1
    except Exception as exc:
        ui.error(f"watch {action}: {exc}")
        return 1
