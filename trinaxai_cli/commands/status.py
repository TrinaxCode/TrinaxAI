from __future__ import annotations

from typing import Any

from trinaxai_cli.commands import _system


def run(args: Any, client: Any, ui: Any, config: Any) -> int:
    rc = _system.run_service_action("status", ui, timeout=30)
    state = _system.service_state()
    if state:
        ui.info(f"AI boot preference: {'on' if state.get('ai_enabled') else 'off'}")
    return rc
