from __future__ import annotations

from typing import Any

from trinaxai_cli.commands import _system


def run(args: Any, client: Any, ui: Any, config: Any) -> int:
    action = "stop-all" if getattr(args, "all", False) else "stop-ai"
    target = "all TrinaxAI services including the PWA" if action == "stop-all" else "AI services"
    if not getattr(args, "yes", False):
        if not ui.confirm(f"Stop {target}?", default=False):
            ui.info("Cancelled.")
            return 0
    ui.info(f"Stopping {target}...")
    return _system.run_service_action(action, ui, timeout=180)
