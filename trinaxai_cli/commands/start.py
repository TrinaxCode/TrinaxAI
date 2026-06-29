from __future__ import annotations

from typing import Any

from trinaxai_cli.commands import _system


def run(args: Any, client: Any, ui: Any, config: Any) -> int:
    ui.info("Starting TrinaxAI services...")
    return _system.run_service_action("start", ui, timeout=180)
