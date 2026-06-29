"""``trinaxai doctor`` — quick local health check."""
from __future__ import annotations

from typing import Any


def run(args: Any, client: Any, ui: Any, config: Any) -> int:
    try:
        health = client.health()
        indexed = bool(health.get("indexed"))
        projects = health.get("projects", []) or []
        collections = health.get("collections", []) or []

        ui.table(
            ["check", "status", "detail"],
            [
                ["API reachable", "OK" if health else "FAIL", ""],
                ["Index built", "OK" if indexed else "NO", "run: trinaxai index --folder <path>"],
                ["Projects", str(len(projects)), ", ".join(projects[:5]) + ("…" if len(projects) > 5 else "")],
                ["Collections", str(len(collections)), ", ".join(c.get("id", "") for c in collections[:5])],
            ],
            title="TrinaxAI health",
        )
        try:
            stats = client.stats()
            ui.info(f"Messages: {stats.get('messages_total', 0)} · est. tokens: {stats.get('tokens_estimated', 0)}")
        except Exception:
            pass
        try:
            mem = client.memory_summary()
            if mem.get("summary"):
                ui.panel(mem.get("summary", ""), title="Memory summary")
        except Exception:
            pass
        return 0
    except Exception as exc:
        ui.error(f"doctor: {exc}")
        return 1