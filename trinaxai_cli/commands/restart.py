from __future__ import annotations

from typing import Any

from trinaxai_cli.commands import _system


def run(args: Any, client: Any, ui: Any, config: Any) -> int:
    if not getattr(args, "yes", False):
        if not ui.confirm("Restart TrinaxAI AI services?", default=False):
            ui.info("Cancelled.")
            return 0
    stop_rc = _system.run_service_action("stop-ai", ui, timeout=180)
    if stop_rc != 0:
        return stop_rc
    return _system.run_service_action("start-ai", ui, timeout=180)
